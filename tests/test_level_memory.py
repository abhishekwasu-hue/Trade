"""tests/test_level_memory.py -- MCX Dynamic S/R level memory: महत्त्वाचे levels त्याच किंमतीवर राहतात (network/DB-मुक्त)."""
from unittest.mock import patch

import json

import numpy as np
import pandas as pd
import pytest

import level_memory as LM
import refresh_market_zones_mcx as rmzm


def _df(prices, start="2026-09-01 09:00", spread=1.0):
    t = pd.date_range(start, periods=len(prices), freq="30min")
    p = np.asarray(prices, float)
    return pd.DataFrame({"timestamp": t, "open": p, "high": p + spread, "low": p - spread, "close": p, "volume": 0, "oi": 0})


NOW = pd.Timestamp("2026-10-02 23:00")


def test_tolerance_bounded_by_pct():
    flat = _df([288.0] * 50, spread=0.01)
    assert abs(LM.zone_tolerance(flat, 288.0) - 288 * 0.0008) < 1e-9          # किमान 0.08%
    wild = _df([288.0] * 50, spread=20.0)
    assert abs(LM.zone_tolerance(wild, 288.0) - 288 * 0.004) < 1e-9          # कमाल 0.40%


def test_fresh_level_near_old_keeps_old_price_and_max_strength():
    df = _df([290.0] * 60, start="2026-09-30 09:00")
    existing = [{"level": 300.0, "strength": 5, "formed_date": "2026-09-10"}]
    out = LM.merge_levels(existing, [{"level": 300.4, "touches": 3}], df, 290.0, NOW)
    assert [(z["level"], z["strength"], z["role"], z["fresh"]) for z in out] == [(300.0, 5.0, "RESISTANCE", True)]
    assert out[0]["formed_date"] == "2026-09-10"


def test_old_level_kept_if_touched_recently_retired_if_not():
    recent = _df(list(np.linspace(300, 288, 60)), start="2026-09-28 09:00")      # 300 ला 28 Sep ला स्पर्श
    existing = [{"level": 300.0, "strength": 3, "formed_date": "2026-08-01"},
                {"level": 330.0, "strength": 4, "formed_date": "2026-08-01"}]      # 330 ला शेवटच्या 30 दिवसांत स्पर्श नाही
    out = LM.merge_levels(existing, [{"level": 286.4, "touches": 5}], recent, 288.1, NOW)
    levels = {z["level"]: z for z in out}
    assert 300.0 in levels and not levels[300.0]["fresh"] and 330.0 not in levels
    assert levels[286.4]["role"] == "SUPPORT" and levels[300.0]["role"] == "RESISTANCE"


def test_recently_formed_untouched_level_kept_far_level_dropped():
    df = _df([288.0] * 60, start="2026-09-28 09:00")
    existing = [{"level": 305.0, "strength": 2, "formed_date": "2026-09-25"},
                {"level": 340.0, "strength": 6, "formed_date": "2026-09-25"}]      # 18% दूर
    out = LM.merge_levels(existing, [], df, 288.0, NOW)
    assert [z["level"] for z in out] == [305.0]


def test_broken_support_becomes_resistance_not_deleted():
    df = _df(list(np.linspace(292, 284, 60)), start="2026-09-30 09:00")
    out = LM.merge_levels([{"level": 290.0, "strength": 4, "formed_date": "2026-09-20"}], [], df, 284.0, NOW)
    assert out[0]["level"] == 290.0 and out[0]["role"] == "RESISTANCE"


def test_crowded_levels_deduped_and_capped():
    df = _df([300.0] * 60, start="2026-09-30 09:00", spread=0.01)                 # tol = 0.08% = 0.24
    fresh = [{"level": 300.0 + i, "touches": 2} for i in range(15)] + [{"level": 300.1, "touches": 9}]
    out = LM.merge_levels([], fresh, df, 300.0, NOW, max_levels=12)
    lv = [z["level"] for z in out]
    assert len(out) == 12 and 300.1 in lv and 300.0 not in lv                   # जवळचे दोन ⇒ जास्त strength चा एक


def _resolved():
    return True, {"symbol": "NATURALGAS", "trading_symbol": "NATURALGAS FUT 27 OCT 26", "instrument_key": "MCX_FO|NG", "lot_size": 1250,
                  "tick_size": 0.1, "expiry": "2026-10-27"}


def _osc(n=300, base=288.0):
    c = [base + (3 if i % 8 < 4 else -3) for i in range(n)]
    df = _df(c, start="2026-08-01 09:00", spread=1.5)
    df.attrs["failed_chunks"] = 0
    return df


@pytest.fixture
def mcx_state(tmp_path):
    path = str(tmp_path / "levels_contract.json")
    with open(path, "w") as f:
        json.dump({"NATURALGAS": "NATURALGAS FUT 27 OCT 26"}, f)
    return path


def test_refresh_symbol_keeps_remembered_level_and_scopes_delete(mcx_state):
    df = _osc()
    old = pd.DataFrame([{"symbol": "NATURALGAS", "zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 299.5, "zone_high": 299.5, "strength": 4,
                         "formed_date": pd.Timestamp(df["timestamp"].iloc[-20]), "status": "ACTIVE"}])
    with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_resolved()), \
         patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
         patch.object(rmzm.cloud_db, "get_strategy_settings", return_value={}), \
         patch.object(rmzm.cloud_db, "get_market_zones", return_value=old), \
         patch.object(rmzm.cloud_db, "save_market_zones", return_value=True) as save:
        ok, msg = rmzm.refresh_symbol("tok", "NATURALGAS", state_path=mcx_state)
    saved = save.call_args.args[0]
    assert ok and "level memory" in msg
    assert 299.5 in set(saved.loc[saved["zone_type"] == "DYNAMIC_SR_RESISTANCE_30M", "zone_low"])
    assert save.call_args.kwargs["scoped"] is True and set(save.call_args.kwargs["zone_types"]) == set(rmzm.DYNAMIC_TYPES)


def test_refresh_symbol_reset_and_disabled_forget_old_levels(mcx_state):
    df = _osc()
    old = pd.DataFrame([{"symbol": "NATURALGAS", "zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 299.5, "zone_high": 299.5, "strength": 4,
                         "formed_date": pd.Timestamp(df["timestamp"].iloc[-20]), "status": "ACTIVE"}])
    for kwargs, settings, note in (({"reset": True}, {}, "contract roll"), ({}, {"level_memory_enabled": False}, "level memory बंद")):
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_resolved()), \
             patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
             patch.object(rmzm.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(rmzm.cloud_db, "get_market_zones", return_value=old), \
             patch.object(rmzm.cloud_db, "save_market_zones", return_value=True) as save:
            ok, msg = rmzm.refresh_symbol("tok", "NATURALGAS", state_path=mcx_state, **kwargs)
        assert ok and note in msg and 299.5 not in set(save.call_args.args[0]["zone_low"])


# ---- NIFTY (स्थिर भूमिका) ----------------------------------------------------------------------------------------------
def _nifty_df(prices, start="2026-10-01 09:15"):
    return _df(prices, start=start, spread=3.0)


def test_role_kept_for_remembered_levels_when_not_by_price():
    df = _nifty_df(list(np.linspace(24550, 24480, 80)))                         # 24500 ला 1 Oct ला स्पर्श, आता भाव 24480 (खाली)
    existing = [{"level": 24500.0, "strength": 3, "formed_date": "2026-09-30", "role": "SUPPORT"}]
    out = LM.merge_levels(existing, [], df, 24480.0, pd.Timestamp("2026-10-01 15:00"), retire_days=5, role_by_price=False)
    assert [(z["level"], z["role"]) for z in out] == [(24500.0, "SUPPORT")]      # role DB मध्ये स्थिर (by-price नसता तर RESISTANCE)


def test_remember_dyn_sr_feeds_merge_format():
    df = _nifty_df(list(np.linspace(24600, 24500, 80)))
    zones = pd.DataFrame([{"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 24580.0, "strength": 4, "formed_date": "2026-09-30",
                           "status": "ACTIVE"},
                          {"zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": 24400.0, "strength": 4, "formed_date": "2026-09-30",
                           "status": "ACTIVE"}])
    dyn = {"support": [{"level": 24498.0, "touches": 2}], "resistance": [{"level": 24581.5, "touches": 5}]}
    out = LM.remember_dyn_sr(dyn, zones, "5M", df, pd.Timestamp("2026-10-01 15:00"))
    assert out["resistance"] == [{"level": 24580.0, "touches": 5.0}]             # जुनी किंमत, जास्त strength
    assert out["support"] == [{"level": 24498.0, "touches": 2.0}]                # 15M चा level 5M मध्ये मिसळत नाही


def test_memory_enabled_reads_bot_settings():
    calls = []

    def gs(key, sym):
        calls.append(key)
        return {"level_memory_enabled": key != "15m_dynamic_sr"}
    assert LM.memory_enabled("NIFTY", "5M", gs) is True and LM.memory_enabled("NIFTY", "15M", gs) is False
    assert calls == ["1m_instant", "15m_dynamic_sr"]
    assert LM.memory_enabled("NIFTY", "5M", lambda *a: (_ for _ in ()).throw(RuntimeError())) is True


def test_nightly_apply_keeps_formed_date_and_other_zone_types():
    df5 = _nifty_df(list(np.linspace(24600, 24500, 80)))
    zones_df = pd.DataFrame([
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 24498.0, "zone_high": 24498.0, "strength": 2,
         "formed_date": "2026-10-01", "status": "ACTIVE"},
        {"symbol": "NIFTY", "zone_type": "ORDER_BLOCK_BULLISH", "zone_low": 24300.0, "zone_high": 24320.0, "strength": 1,
         "formed_date": "2026-10-01", "status": "ACTIVE"}])
    existing = pd.DataFrame([{"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 24580.0, "strength": 4, "formed_date": "2026-09-30",
                              "status": "ACTIVE"}])
    out = LM.apply_memory_to_zone_rows(zones_df, existing, {"5M": df5, "15M": None}, pd.Timestamp("2026-10-01 15:30"), lambda s: True,
                                       symbol="NIFTY")
    by = {(r.zone_type, r.zone_low): r for r in out.itertuples()}
    assert ("ORDER_BLOCK_BULLISH", 24300.0) in by and ("DYNAMIC_SR_SUPPORT_5M", 24498.0) in by
    assert by[("DYNAMIC_SR_RESISTANCE_5M", 24580.0)].formed_date == "2026-09-30"
    off = LM.apply_memory_to_zone_rows(zones_df, existing, {"5M": df5}, pd.Timestamp("2026-10-01 15:30"), lambda s: False)
    assert off.equals(zones_df)


def test_refresh_5m_uses_memory_when_enabled():
    import refresh_dynamic_sr_5m as r5
    df = _nifty_df([24500 + (8 if i % 6 < 3 else -8) for i in range(300)], start="2026-09-25 09:15")
    df.attrs["failed_chunks"] = 0
    zones = pd.DataFrame([{"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 24509.0, "strength": 3, "formed_date": "2026-09-30",
                           "status": "ACTIVE"}])
    with patch.object(r5, "fetch_candles", return_value=df), \
         patch.object(r5.cloud_db, "get_strategy_settings", return_value={}), \
         patch.object(r5.cloud_db, "get_market_zones", return_value=zones), \
         patch.object(r5.cloud_db, "merge_dynamic_sr_zones", return_value=True) as merge:
        ok, _ = r5.refresh_symbol_5m("tok", "NIFTY")
    passed = merge.call_args.args[1]
    assert ok and 24509.0 in [z["level"] for z in passed["resistance"] + passed["support"]]


def test_refresh_symbol_resets_memory_when_contract_changes_or_first_run(tmp_path):
    df = _osc()
    old = pd.DataFrame([{"symbol": "NATURALGAS", "zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 299.5, "zone_high": 299.5, "strength": 4,
                         "formed_date": pd.Timestamp(df["timestamp"].iloc[-20]), "status": "ACTIVE"}])
    path = str(tmp_path / "s.json")
    with open(path, "w") as f:
        json.dump({"NATURALGAS": "NATURALGAS FUT 25 SEP 26"}, f)                    # जुना contract ⇒ roll झाला
    for _ in range(2):                                                              # 1: roll ⇒ reset; 2: त्याच contract ⇒ memory
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_resolved()), \
             patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
             patch.object(rmzm.cloud_db, "get_strategy_settings", return_value={}), \
             patch.object(rmzm.cloud_db, "get_market_zones", return_value=old), \
             patch.object(rmzm.cloud_db, "save_market_zones", return_value=True) as save:
            ok, msg = rmzm.refresh_symbol("tok", "NATURALGAS", state_path=path)
        levels = set(save.call_args.args[0]["zone_low"])
        if _ == 0:
            assert ok and "जुने levels विसरले" in msg and 299.5 not in levels
        else:
            assert ok and "त्याच किंमतीवर" in msg and 299.5 in levels
    assert json.load(open(path))["NATURALGAS"] == "NATURALGAS FUT 27 OCT 26"
    first = str(tmp_path / "none.json")                                             # नोंदच नाही ⇒ reset
    with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_resolved()), \
         patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
         patch.object(rmzm.cloud_db, "get_strategy_settings", return_value={}), \
         patch.object(rmzm.cloud_db, "get_market_zones", return_value=old), \
         patch.object(rmzm.cloud_db, "save_market_zones", return_value=True) as save:
        ok, msg = rmzm.refresh_symbol("tok", "NATURALGAS", state_path=first)
    assert 299.5 not in set(save.call_args.args[0]["zone_low"])
