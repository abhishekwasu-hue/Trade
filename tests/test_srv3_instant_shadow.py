"""tests/test_srv3_instant_shadow.py -- 5-Min Instant Trader चा SR V3 PAPER shadow (network/DB-free; सर्व बाह्य कॉल monkeypatch)."""
import datetime

import numpy as np
import pandas as pd
import pytest

import cloud_db
import srv3_instant_shadow as SH
import trading_engine

NOW = datetime.datetime(2025, 3, 5, 11, 0)


def candles(n, start, freq_min, base=22000.0, seed=3):
    rng = np.random.default_rng(seed)
    out, px = [], base
    t = pd.Timestamp(start)
    for i in range(n):
        o, c = px, px + rng.normal(0, 6)
        out.append({"timestamp": t + pd.Timedelta(minutes=freq_min * i), "open": o, "high": max(o, c) + 3, "low": min(o, c) - 3, "close": c})
        px = c
    return pd.DataFrame(out)


def settings(**kw):
    s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
    s.update({"srv3_shadow_enabled": True, "symbol_enabled": True, "pcr_bullish_min": 0.7, "pcr_bearish_max": 1.3})
    s.update(kw)
    return s


def test_defaults_and_wiring():
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["srv3_shadow_enabled"] is False
    assert trading_engine.SHADOW_EXIT_PARENT_SOURCE[SH.SOURCE] == "dynamic_sr_instant"
    assert SH.SOURCE.endswith("_shadow") and all(not t.endswith(("_1M", "_5M", "_15M")) for t in SH.ZONE_TYPES)


def test_v3_levels_filters_grade_distance_and_splits_by_price():
    df5 = candles(900, "2025-02-17 09:15", 5)
    df15 = candles(300, "2025-02-17 09:15", 15, seed=4)
    lv = SH.v3_levels(df5, df15, None, float(df5["close"].iloc[-1]))
    price = float(df5["close"].iloc[-1])
    assert set(lv) == {"support", "resistance"}
    assert all(x["level"] < price for x in lv["support"]) and all(x["level"] >= price for x in lv["resistance"])
    assert all(x["touches"] >= 45 for x in lv["support"] + lv["resistance"])          # फक्त A/B (score ≥ 45)
    assert SH.v3_levels(None, None, None, price) == {"support": [], "resistance": []}


def test_refresh_is_throttled_and_uses_srv3_prefix(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cloud_db, "merge_dynamic_sr_zones", lambda sym, lv, suf, formed_date=None, type_prefix="DYNAMIC_SR": calls.append((sym, suf, type_prefix)) or True)

    def fetch(token, symbol, current_spot=0, interval="5minute", lookback_days=1):
        return {"5minute": candles(900, "2025-02-17 09:15", 5), "15minute": candles(300, "2025-02-17 09:15", 15),
                "day": candles(40, "2025-01-01", 1440)}[interval]
    state = str(tmp_path / "s.json")
    assert "merge" in SH.refresh_levels_if_due("t", "NIFTY", NOW, fetch=fetch, state_path=state)
    assert calls == [("NIFTY", "", "SRV3")]
    assert SH.refresh_levels_if_due("t", "NIFTY", NOW + datetime.timedelta(minutes=2), fetch=fetch, state_path=state) is None
    assert SH.refresh_levels_if_due("t", "NIFTY", NOW + datetime.timedelta(minutes=6), fetch=fetch, state_path=state) is not None
    assert len(calls) == 2


def test_merge_type_prefix_names(monkeypatch):
    """cloud_db.merge_dynamic_sr_zones: type_prefix + रिकामा suffix ⇒ SRV3_SUPPORT/SRV3_RESISTANCE (DB नाही ⇒ False, पण नाव तपासतो)."""
    seen = {}

    class Cur:
        def execute(self, sql, params=()):
            seen.setdefault("params", []).append(params)

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            pass

        def close(self):
            pass
    monkeypatch.setattr(cloud_db, "get_connection", lambda: Conn())
    assert cloud_db.merge_dynamic_sr_zones("NIFTY", {"support": [{"level": 100.0, "touches": 60}], "resistance": []}, "", type_prefix="SRV3")
    first = seen["params"][0]
    assert first[1:] == ("SRV3_SUPPORT", "SRV3_RESISTANCE")
    seen.clear()
    cloud_db.merge_dynamic_sr_zones("NIFTY", {"support": [{"level": 100.0, "touches": 3}], "resistance": []}, "5M")
    assert seen["params"][0][1:] == ("DYNAMIC_SR_SUPPORT_5M", "DYNAMIC_SR_RESISTANCE_5M")


def _touch_ctx(monkeypatch, entries=0, last_sl=None):
    monkeypatch.setattr(SH, "count_entries_at_level_today", lambda *a: entries)
    monkeypatch.setattr(SH, "get_last_sl_tsl_exit_time", lambda *a: last_sl)
    recent = [{"open": 22010.0, "high": 22012.0, "low": 22004.0, "close": 22008.0}, {"open": 22008.0, "high": 22009.0, "low": 21999.5, "close": 22006.0}]
    return recent, [22030.0, 22020.0, 22008.0, 22006.0]


def test_evaluate_touch_gates(monkeypatch):
    recent, closes = _touch_ctx(monkeypatch)
    ok_rsi = lambda df, d, lo, hi: (True, 30.0)                                       # noqa: E731
    ok_pcr = lambda sym, d, a, b: (True, 1.0, "")                                     # noqa: E731
    d, why = SH.evaluate_touch(22000.0, recent, closes, None, settings(), "NIFTY", "2025-03-05", NOW, rsi_fn=ok_rsi, pcr_fn=ok_pcr)
    assert d == "BULLISH" and why == "TOUCH"
    assert SH.evaluate_touch(21900.0, recent, closes, None, settings(), "NIFTY", "2025-03-05", NOW, rsi_fn=ok_rsi, pcr_fn=ok_pcr)[0] is None
    assert "RSI" in SH.evaluate_touch(22000.0, recent, closes, None, settings(), "NIFTY", "2025-03-05", NOW,
                                      rsi_fn=lambda *a: (False, 55.0), pcr_fn=ok_pcr)[1]
    assert SH.evaluate_touch(22000.0, recent, closes, None, settings(entry_rsi_gate_enabled=False), "NIFTY", "2025-03-05", NOW,
                             rsi_fn=lambda *a: (False, 55.0), pcr_fn=ok_pcr)[0] == "BULLISH"
    assert "PCR" in SH.evaluate_touch(22000.0, recent, closes, None, settings(), "NIFTY", "2025-03-05", NOW, rsi_fn=ok_rsi,
                                      pcr_fn=lambda *a: (False, 0.5, "low"))[1]
    assert "Bullish" in SH.evaluate_touch(22000.0, recent, closes, None, settings(bullish_entry_enabled=False), "NIFTY", "2025-03-05", NOW,
                                          rsi_fn=ok_rsi, pcr_fn=ok_pcr)[1]
    _touch_ctx(monkeypatch, entries=2)
    assert "कमाल" in SH.evaluate_touch(22000.0, recent, closes, None, settings(), "NIFTY", "2025-03-05", NOW, rsi_fn=ok_rsi, pcr_fn=ok_pcr)[1]
    _touch_ctx(monkeypatch, last_sl=NOW - datetime.timedelta(minutes=5))
    assert "cooldown" in SH.evaluate_touch(22000.0, recent, closes, None, settings(), "NIFTY", "2025-03-05", NOW, rsi_fn=ok_rsi, pcr_fn=ok_pcr)[1]


def test_run_shadow_off_outside_hours_and_paper_only(monkeypatch):
    assert SH.run_shadow("t", "NIFTY", now=NOW, settings=settings(srv3_shadow_enabled=False)) is None
    assert SH.run_shadow("t", "NIFTY", now=NOW.replace(hour=8), settings=settings()) is None
    monkeypatch.setattr(SH, "refresh_levels_if_due", lambda *a, **k: None)
    monkeypatch.setattr(SH, "has_open_trade_from_source", lambda sym, src: False)
    monkeypatch.setattr(SH, "active_levels", lambda sym: [22000.0])
    today = pd.DataFrame([{"timestamp": pd.Timestamp("2025-03-05 10:58"), "open": 22010.0, "high": 22012.0, "low": 22004.0, "close": 22008.0},
                          {"timestamp": pd.Timestamp("2025-03-05 10:59"), "open": 22008.0, "high": 22009.0, "low": 21999.5, "close": 22006.0}])
    monkeypatch.setattr(SH, "evaluate_touch", lambda *a, **k: ("BULLISH", "TOUCH"))
    opened, sent = [], []
    monkeypatch.setattr(SH, "is_todays_expiry_day", lambda t, s: False)
    monkeypatch.setattr(SH, "fetch_upstox_option_chain", lambda t, s, expiry_index=0: ([{"underlying_spot_price": 22006.0}], "ok"))
    monkeypatch.setattr(SH, "select_credit_spread_itm", lambda *a, **k: {"strategy": "BULL_PUT_SPREAD"})
    monkeypatch.setattr(SH, "select_naked_option_itm", lambda *a, **k: {"strategy": "NAKED_CALL"})
    monkeypatch.setattr(SH, "open_multi_leg_trade", lambda *a, **k: opened.append(k) or (True, {"trade_id": "x"}))
    monkeypatch.setattr(SH, "format_trade_result", lambda ok, r: "OPENED")
    monkeypatch.setattr(SH, "send_telegram_message", lambda m: sent.append(m))
    out = SH.run_shadow("t", "NIFTY", now=NOW, settings=settings(), fetch=lambda *a, **k: today)
    assert "SR V3 Support 22,000.00" in out and len(opened) == 2 and len(sent) == 1
    assert all(k["trading_mode"] == "PAPER" and k["source"] == SH.SOURCE and k["entry_timeframe"] == "SRV3" and k["entry_level_price"] == 22000.0
               and "account_ids" not in k for k in opened)
    assert "14:45" in SH.run_shadow("t", "NIFTY", now=NOW.replace(hour=14, minute=50), settings=settings(), fetch=lambda *a, **k: today)
    monkeypatch.setattr(SH, "has_open_trade_from_source", lambda sym, src: True)
    assert "उघडी" in SH.run_shadow("t", "NIFTY", now=NOW, settings=settings(), fetch=lambda *a, **k: today)


def test_main_bot_runs_shadow_isolated(monkeypatch):
    import dynamic_sr_instant_trader as D
    monkeypatch.setattr(D, "process_symbol", lambda token, sym: f"{sym}: ok")

    def boom(token, sym):
        raise RuntimeError("shadow fail")
    monkeypatch.setattr(SH, "run_shadow", boom)
    assert D.run_all_symbols("t", ["NIFTY", "BANKNIFTY"]) is True                     # shadow ची चूक मूळ bot ला अडवत नाही
    assert "dynamic_sr_instant_srv3_shadow" in D.FIVE_MIN_FAMILY_SOURCES
