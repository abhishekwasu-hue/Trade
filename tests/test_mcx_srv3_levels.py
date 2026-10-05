"""tests/test_mcx_srv3_levels.py -- MCX Futures bot: "Level engine" (DYNAMIC / SRV3_SHADOW / SRV3) — SR V3 levels (network/DB-free)."""
import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import cloud_db
import mcx_futures_trader as mft
import trading_engine
from sr_levels_v3 import session_reference_date
from tests.test_mcx_futures_trader import _DEFAULT_SETTINGS, _fake_candles_df, _fake_resolved


@pytest.fixture(autouse=True)
def _no_closed_trades(monkeypatch):
    monkeypatch.setattr(mft, "get_closed_trades_on_date", lambda *a, **k: [])
    # "नवीन entry बंद" वेळ (22:45 IST) खऱ्या घड्याळावर अवलंबून नको -- नाहीतर रात्री उशिरा चालवल्यावर हे tests अयशस्वी होतात
    monkeypatch.setattr(mft, "MCX_NO_NEW_ENTRY_AFTER", (24, 0))


@pytest.fixture(autouse=True)
def _isolated_contract_state(tmp_path, monkeypatch):
    """contract-roll state फाईल (data/mcx_contract_state.json) टेस्टमध्ये tmp मध्ये — repo मध्ये फाईल नको, टेस्ट्स एकमेकांवर अवलंबून नकोत."""
    monkeypatch.setattr(mft, "CONTRACT_STATE", str(tmp_path / "mcx_contract_state.json"))


def _zones(rows):
    return pd.DataFrame([{"symbol": "CRUDEOIL", "zone_type": zt, "zone_low": lv, "zone_high": lv, "strength": 60.0,
                          "formed_date": "2026-09-01", "status": "ACTIVE"} for zt, lv in rows])


def _settings(**kw):
    return {**_DEFAULT_SETTINGS, "symbol_enabled": True, "entry_rsi_gate_enabled": False, **kw}


def _run(settings, zones, open_trade=None, logs=None, entries=0, open_pos=False):
    open_trade = open_trade or MagicMock(return_value=(True, {"trade_id": "T1"}))
    logs = logs if logs is not None else MagicMock(return_value=True)
    with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
         patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
         patch.object(mft.cloud_db, "get_market_zones", return_value=zones), \
         patch.object(mft, "fetch_mcx_candles", return_value=_fake_candles_df(last_close=6500.0)), \
         patch.object(mft, "refresh_mcx_srv3_levels_if_due", return_value=None), \
         patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
         patch.object(mft, "count_entries_at_level_today", return_value=entries), \
         patch.object(mft, "has_open_trade_from_source", return_value=open_pos), \
         patch.object(mft.cloud_db, "save_signal_log", logs), \
         patch.object(mft.cloud_db, "save_mcx_last_check", return_value=True), \
         patch.object(mft, "send_telegram_message"), \
         patch.object(mft, "open_multi_leg_trade", open_trade):
        return mft.process_symbol("tok", "CRUDEOIL"), open_trade, logs


def test_defaults_and_engine_wiring():
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]["level_engine"] == "DYNAMIC"
    assert mft.LEVEL_ENGINES == ("DYNAMIC", "SRV3_SHADOW", "SRV3") and mft.SRV3_SHADOW_SOURCE.endswith("_shadow")
    assert trading_engine.SHADOW_EXIT_PARENT_SOURCE[mft.SRV3_SHADOW_SOURCE] == "mcx_futures"
    assert mft.SRV3_SHADOW_SOURCE in trading_engine.MCX_SOURCES and mft.SRV3_SHADOW_SOURCE in trading_engine.FILL_ANCHORED_SL_SOURCES
    assert mft.SRV3_CFG.session_end == "23:30"


def test_session_end_for_mcx_keeps_today_until_2330():
    at_16 = datetime.datetime(2026, 9, 2, 16, 0)                     # बुधवार
    assert session_reference_date(at_16) == datetime.date(2026, 9, 3)             # NSE: 15:15 नंतर पुढचा दिवस
    assert session_reference_date(at_16, "23:30") == datetime.date(2026, 9, 2)    # MCX: सत्र अजून चालू
    assert session_reference_date(datetime.datetime(2026, 9, 4, 23, 40), "23:30") == datetime.date(2026, 9, 7)   # शुक्रवार रात्री ⇒ सोमवार


def test_dynamic_engine_ignores_srv3_rows():
    result, trade, _ = _run(_settings(), _zones([("SRV3_SUPPORT", 6500.0)]))
    assert "Dynamic S/R levels" in result and not trade.called


def test_srv3_engine_trades_main_source_on_srv3_levels():
    result, trade, logs = _run(_settings(level_engine="SRV3"), _zones([("SRV3_SUPPORT", 6500.0), ("DYNAMIC_SR_SUPPORT_30M", 7000.0)]))
    assert trade.call_count == 1
    kw = trade.call_args.kwargs
    assert kw["source"] == "mcx_futures" and kw["entry_timeframe"] == "SRV3" and kw["entry_level_price"] == 6500.0
    assert logs.called and "6500" in result


def test_srv3_shadow_runs_main_on_dynamic_and_paper_shadow_on_srv3():
    zones = _zones([("DYNAMIC_SR_SUPPORT_30M", 7000.0), ("SRV3_SUPPORT", 6500.0)])          # जुना level दूर (touch नाही), SR V3 ला touch
    logs = MagicMock(return_value=True)
    result, trade, logs = _run(_settings(level_engine="SRV3_SHADOW", trading_mode="LIVE", broker_account_ids=["acc1"]), zones, logs=logs)
    assert trade.call_count == 1                                                          # फक्त shadow ने trade
    kw = trade.call_args.kwargs
    assert kw["source"] == mft.SRV3_SHADOW_SOURCE and kw["trading_mode"] == "PAPER" and kw["entry_timeframe"] == "SRV3"
    assert "🧪" in result
    logged_levels = {c.args[0]["level_price"] for c in logs.call_args_list}
    assert 6500.0 not in logged_levels and 7000.0 in logged_levels                        # shadow signal_log मध्ये लिहीत नाही


def test_srv3_shadow_respects_max_entries_and_open_position():
    zones = _zones([("DYNAMIC_SR_SUPPORT_30M", 7000.0), ("SRV3_SUPPORT", 6500.0)])
    _, trade, _ = _run(_settings(level_engine="SRV3_SHADOW"), zones, entries=2)
    assert not trade.called
    _, trade2, _ = _run(_settings(level_engine="SRV3_SHADOW"), zones, open_pos=True)
    assert not trade2.called


def test_srv3_shadow_error_never_breaks_main(monkeypatch):
    calls = []

    def core(token, symbol, check_info, level_source="DYNAMIC", shadow=False):
        calls.append((level_source, shadow))
        if shadow:
            raise RuntimeError("boom")
        return "main ok"
    monkeypatch.setattr(mft, "_process_symbol_core", core)
    monkeypatch.setattr(mft.cloud_db, "get_strategy_settings", lambda k, s: _settings(level_engine="SRV3_SHADOW"))
    monkeypatch.setattr(mft.cloud_db, "save_mcx_last_check", lambda *a, **k: True)
    out = mft.process_symbol("tok", "CRUDEOIL")
    assert out.startswith("main ok") and "shadow त्रुटी" in out and calls == [("DYNAMIC", False), ("SRV3", True)]


def _series(n, start, freq, seed):
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, periods=n, freq=freq)
    c = 6500 + np.cumsum(rng.normal(0, 8, n))
    return pd.DataFrame({"timestamp": t, "open": c, "high": c + 6, "low": c - 6, "close": c, "volume": 0, "oi": 0})


def test_refresh_mcx_srv3_throttled_with_srv3_prefix(tmp_path, monkeypatch):
    merged = []
    monkeypatch.setattr(mft.cloud_db, "merge_dynamic_sr_zones",
                        lambda sym, lv, suf, formed_date=None, type_prefix="DYNAMIC_SR": merged.append((sym, suf, type_prefix, lv)) or True)
    now = datetime.datetime(2026, 9, 2, 16, 1)

    def fetch(token, key, interval="30minute", lookback_days=None):
        return {"15minute": _series(600, "2026-08-25 09:00", "15min", 1), "30minute": _series(400, "2026-08-20 09:00", "30min", 2),
                "day": _series(40, "2026-07-20", "1D", 3)}[interval]
    state = str(tmp_path / "s.json")
    msg = mft.refresh_mcx_srv3_levels_if_due("tok", "CRUDEOIL", "MCX_FO|1", now, fetch=fetch, state_path=state)
    assert "merge" in msg and merged[0][:3] == ("CRUDEOIL", "", "SRV3")
    assert all(x["touches"] >= 45 for x in merged[0][3]["support"] + merged[0][3]["resistance"])
    assert mft.refresh_mcx_srv3_levels_if_due("tok", "CRUDEOIL", "MCX_FO|1", now + datetime.timedelta(minutes=3), fetch=fetch, state_path=state) is None
    assert len(merged) == 1


# 🎓 SR V3.2 ("1402.2 हा level chart war yayalach nko" -- COPPER 5 Oct): range च्या मधल्या chop-किंमतीला खोटे गुण.
def _range_frames(seed=7):
    from signals import resample_to_1h
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-09-24 09:00", periods=8 * 58, freq="15min")
    t = np.arange(len(idx))
    c = 1400 + 7 * np.sin(t / 23.0) + 4 * np.sin(t / 4.3) + rng.normal(0, 1.0, len(t))
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) + rng.uniform(0.3, 1.5, len(t)), np.minimum(o, c) - rng.uniform(0.3, 1.5, len(t))
    d15 = pd.DataFrame({"timestamp": idx, "open": o, "high": h, "low": l, "close": c, "volume": 1, "oi": 0})
    d30 = d15.set_index("timestamp").resample("30min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "oi": "last"}).dropna().reset_index()
    return {"15minute": d15, "30minute": d30, "1hour": resample_to_1h(d30)}, float(c[-1]), float(l.min()), float(h.max())


def test_v32_demotes_mid_range_chop_levels_but_keeps_range_edges():
    from sr_levels_v3 import SRConfig, compute_sr_v3
    frames, price, lo, hi = _range_frames()
    old = compute_sr_v3(frames, current_price=price, cfg=SRConfig(session_end="23:30"))["levels"]
    new = compute_sr_v3(frames, current_price=price, cfg=mft.SRV3_CFG)["levels"]
    mid = lambda z: lo + 0.2 * (hi - lo) < z["level"] < hi - 0.2 * (hi - lo)
    assert any(mid(z) and z["grade"] in "AB" for z in old)                      # जुनं: range-मधले levels A/B (हीच तक्रार)
    assert not any(mid(z) and z["grade"] in "AB" for z in new)                  # V3.2: सगळे मधले C (bot trade करत नाही)
    assert all(z["crossings"] > mft.SRV3_CFG.chop_max_crossings and "CHOP" in " ".join(z["tags"]) for z in new if mid(z) and z["tfs"])
    edges = sorted(z["level"] for z in new if z["grade"] == "A")
    assert len(edges) == 2 and edges[0] - lo < 2.0 and hi - edges[1] < 2.0       # range च्या दोन्ही कडा A राहतात


def test_v32_flags_off_by_default_so_nifty_unchanged():
    from sr_levels_v3 import SRConfig
    d = SRConfig()
    assert (d.chop_filter, d.reject_redepart, d.flip_min_break_atr, d.min_base_points) == (False, False, 0.0, 0.0)
    c = mft.SRV3_CFG
    assert c.chop_filter and c.reject_redepart and c.flip_min_break_atr == 0.5 and c.min_base_points == 10.0 and c.reject_follow_atr == 1.5


def test_count_crossings_ignores_wobble_inside_band():
    from sr_levels_v3 import count_crossings
    df = pd.DataFrame({"timestamp": pd.date_range("2026-10-01", periods=8, freq="15min"),
                       "close": [99.0, 100.1, 101.0, 100.05, 99.0, 101.0, 100.0, 101.2]})
    assert count_crossings(df, 100.0, 0.2, pd.Timestamp("2026-09-30")) == 3     # 99→101→99→101 (100.1/100.05/100.0 band मध्ये)


def test_reject_redepart_counts_one_rejection_per_excursion():
    from sr_levels_v3 import SRConfig, count_rejections
    # दूर (90) -> level ला तीनदा wick करून परत, पण मध्ये दूर न जाता (chop) -> नवीन नियमात 1 नकार
    rows = [(90, 90.5, 89.5, 90)] + [(99, 100.2, 98.8, 99)] + [(99, 99.2, 98.6, 99)] + [(99, 100.2, 98.8, 99)] + [(99, 99.2, 98.6, 99)] \
        + [(99, 100.2, 98.8, 99)]
    df = pd.DataFrame([{"timestamp": pd.Timestamp("2026-10-01 09:00") + pd.Timedelta(minutes=15 * i), "open": o, "high": h, "low": l, "close": c}
                       for i, (o, h, l, c) in enumerate(rows)])
    since = pd.Timestamp("2026-09-30")
    assert count_rejections(df, 100.0, 0.5, since, 2.0, SRConfig())["count"] == 3
    assert count_rejections(df, 100.0, 0.5, since, 2.0, SRConfig(reject_redepart=True))["count"] == 1


def test_min_base_points_drops_bonuses_for_weak_pivot():
    from sr_levels_v3 import SRConfig, _score_zone
    z = {"touches_raw": 0.63, "reaction": 0.7, "tfs": ["15minute", "30minute"], "keys": [], "polarity": True, "flipped": True,
         "retested": True, "gap": None, "rejections": 8, "rej_strong": 8}
    a, b = dict(z), dict(z)
    _score_zone(a, SRConfig()); _score_zone(b, SRConfig(min_base_points=10.0))
    assert a["grade"] == "B" and b["grade"] == "C"                               # COPPER 1402.2 सारखा: touches 6.3 => bonus नाहीत
    assert b["components"]["role_reversal"] == b["components"]["rejections"] == b["components"]["polarity"] == 0.0


def test_srv3_grade_a_only_setting_filters_b_levels():
    zones = pd.DataFrame([{"symbol": "CRUDEOIL", "zone_type": "SRV3_SUPPORT", "zone_low": 6500.0, "zone_high": 6500.0, "strength": 62.0,
                           "formed_date": "2026-09-01", "status": "ACTIVE"}])
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]["srv3_grade_a_only"] is False
    _, trade, _ = _run(_settings(level_engine="SRV3"), zones)
    assert trade.call_count == 1                                                  # डीफॉल्ट: B (62) वरही trade
    result, trade2, _ = _run(_settings(level_engine="SRV3", srv3_grade_a_only=True), zones)
    assert not trade2.called and "SR V3" in result
