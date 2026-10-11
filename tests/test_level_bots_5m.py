"""tests/test_level_bots_5m.py — 5-Min Instant (dynamic_sr_instant) + SR V3 shadow: confirmation mode (Abhi: Daily trend च्या बाजूने,
बंद 5M candle वर commitment नंतरच; CONFIRMED ⇒ Vision ✅ मार्ग). Network / DB नाही — gate, vision, trade placement सगळे fakes."""
import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

import cloud_db
import dynamic_sr_instant_trader as dsr
import srv3_instant_shadow as SH
import upstox_api
import vision.gate as VG
from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from paper import journal as PJ
from tests.test_dynamic_sr_instant_trader import _fake_chain, _fake_zones
from tests.test_level_reaction import BULL_ENGULF, DOWN_CTX, PULL, SWEEP, TOUCH, UP_CTX

NOW = datetime.datetime(2026, 9, 11, 10, 0)
REAL_CYCLE_GATE = LGB.cycle_gate

CONFIRMED_BEAR = {"state": LR.CONFIRMED, "entry": True, "side": LR.BEAR, "reason": "confirmed", "entry_price": 23930.0, "sl": 23960.0,
                  "target": 23820.0, "rr": 3.67, "form": "engulf", "grade": "A", "commit_grade": "A", "evidence": {"sweep": True}}
ARMED_BULL = {"state": LR.ARMED, "entry": False, "side": LR.BULL, "reason": LR.R_NO_COMMIT, "bars_armed": 2, "max_armed_bars": 8}


class FakeGate:
    """CycleGate सारखा: results = {level: result} (area मध्ये level असेल तो); बाकी ⇒ IDLE (area वर नाही)."""
    ctx = UP_CTX

    def __init__(self, results=None):
        self.results = results or {}

    def result(self, lo, hi):
        for lv, r in self.results.items():
            if lo <= lv <= hi:
                return dict(r, area=(lo, hi))
        return {"state": LR.IDLE, "entry": False, "side": None, "reason": "price not at area", "events": [], "area": (lo, hi)}


def _one_min(rows, end=NOW):
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", pd.date_range(end=pd.Timestamp(end) - pd.Timedelta(minutes=1), periods=len(rows), freq="1min"))
    return df


AWAY = _one_min([(23930, 23935, 23925, 23930)] * 20)                                  # 23900 ला touch नाही (hysteresis: BULLISH)
TOUCHING = _one_min([(23930, 23935, 23925, 23930)] * 20 + [(23910, 23912, 23899, 23905)] * 2)   # जुना touch 23900
BELOW = _one_min([(23880, 23885, 23875, 23880)] * 20)                                 # hysteresis: BEARISH


def _settings(**kw):
    s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
    s.update({"symbol_enabled": True, "entry_mode": "confirmation", "naked_enabled": False, "pcr_bullish_min": 0.7, "pcr_bearish_max": 1.3})
    s.update(kw)
    return s


def _boom(*a, **k):
    raise AssertionError("confirmation mode मध्ये हे call व्हायला नको")


@pytest.fixture
def env(monkeypatch):
    E = SimpleNamespace(logs=[], trades=[], tg=[], vision=[], gate_calls=[], fetches=[], forced=[], settings=_settings(), zones=_fake_zones(),
                        candles=AWAY, gate=FakeGate(), vg=VG.Gate("HOLD", status="SKIPPED_VISION_PENDING", note="pending"))
    monkeypatch.setattr(LGB, "_TOUCH_SEEN", set())
    monkeypatch.setattr(dsr.cloud_db, "get_strategy_settings", lambda name, sym: E.settings)
    monkeypatch.setattr(dsr.cloud_db, "get_market_zones", lambda sym: E.zones)
    monkeypatch.setattr(dsr.cloud_db, "save_signal_log", lambda e: E.logs.append(dict(e)) or True)
    monkeypatch.setattr(dsr.cloud_db, "get_zone_hits_today", lambda *a, **k: (0, None, None))
    monkeypatch.setattr(dsr, "get_ist_now", lambda: NOW)
    monkeypatch.setattr(dsr, "fetch_candles", lambda *a, **k: E.fetches.append(k.get("interval")) or E.candles.copy())
    monkeypatch.setattr(dsr, "has_open_trade_from_source", lambda *a: False)
    monkeypatch.setattr(dsr, "get_last_sl_tsl_exit_time", lambda *a: None)
    monkeypatch.setattr(dsr, "is_todays_expiry_day", lambda t, s: False)
    monkeypatch.setattr(dsr, "fetch_upstox_option_chain", lambda *a, **k: (_fake_chain(23930.0), "SUCCESS"))
    monkeypatch.setattr(dsr, "select_credit_spread_itm", lambda *a, **k: {"strategy": "SPREAD", "legs": []})
    monkeypatch.setattr(dsr, "open_multi_leg_trade", lambda *a, **k: E.trades.append(k) or ({"trade_id": "T1"}, "OPENED"))
    monkeypatch.setattr(dsr, "send_telegram_message", lambda m: E.tg.append(m) or True)
    monkeypatch.setattr(dsr, "check_instant_rsi_filter", _boom)                       # confirmation: RSI / PCR default बंद
    monkeypatch.setattr(dsr, "check_pcr_gate", _boom)

    def cycle_gate(bot, symbol, token, settings, areas, now):
        E.gate_calls.append((bot, symbol, list(areas)))
        if isinstance(E.gate, Exception):
            raise E.gate
        return E.gate
    monkeypatch.setattr(LGB, "cycle_gate", cycle_gate)

    def entry_gate(bot, symbol, mode, direction, level, role, tf, ts, spot, lots, naked_lots=None, tags=None, last_bar=None, forced=False,
                   **k):
        E.vision.append({"bot": bot, "mode": mode, "direction": direction, "level": level, "role": role, "tf": tf, "lots": lots,
                         "tags": tags, "forced": forced})
        return E.vg
    monkeypatch.setattr(VG, "entry_gate", entry_gate)
    monkeypatch.setattr(VG, "forced_levels", lambda bot, sym, mode="PAPER", path=None: list(E.forced))
    return E


def _log(E, level):
    return [e for e in E.logs if e["level_price"] == level]


# ------------------------------------------------------------------------------------------------ dynamic_sr_instant
def test_touch_without_reaction_no_entry_gate_skip_log_and_would_have_only(env):
    env.candles, env.gate = TOUCHING, FakeGate({23900.0: ARMED_BULL})
    dsr.process_symbol("tok", "NIFTY")
    assert not env.vision and not env.trades and not env.tg
    assert len(env.gate_calls) == 1 and env.gate_calls[0][0] == "dynamic_sr_instant" and len(env.gate_calls[0][2]) == 2
    (lg,) = _log(env, 23900.0)
    assert lg["trade_status"] == "SKIPPED_GATE_WAITING_COMMITMENT" and lg["reason"].startswith("[GATE]") and lg["hit_type"] == "TOUCH"
    assert _log(env, 24500.0)[0]["trade_status"] == "SKIPPED_GATE_NOT_AT_AREA"
    wh = [r for r in PJ.would_have_rows() if r["bot"] == "dynamic_sr_instant_touch_legacy"]
    assert len(wh) == 1 and wh[0]["level"] == 23900.0 and wh[0]["direction"] == "BULLISH" and wh[0]["setup_tf"] == "5M"
    assert wh[0]["orig_lots"] == 0 and wh[0]["status"] == "TOUCH_LEGACY"


def test_confirmed_reaches_vision_gate_with_gate_tags_and_gate_side(env):
    env.gate = FakeGate({23900.0: CONFIRMED_BEAR})              # hysteresis BULLISH आहे — दिशा gate चीच हवी
    dsr.process_symbol("tok", "NIFTY")
    (v,) = env.vision
    assert v["direction"] == "BEARISH" and v["role"] == "RESISTANCE" and v["level"] == 23900.0 and v["tf"] == "5M" and not v["forced"]
    assert v["tags"]["hit"] == "CONFIRMED" and v["tags"]["breakout_entry"] is False
    g = v["tags"]["gate"]
    assert g["side"] == "BEARISH" and g["rr"] == 3.67 and g["sl"] == 23960.0 and g["target"] == 23820.0 and g["tf"] == "5M"
    assert g["trend"] == "Daily UP"
    assert not env.trades and _log(env, 23900.0)[0]["trade_status"] == "SKIPPED_VISION_PENDING"   # ✅ ची वाट — थेट entry नाही


def test_confirmed_and_approved_places_paper_trade(env):
    env.gate, env.vg = FakeGate({23900.0: CONFIRMED_BEAR}), VG.Gate("ENTER", 1, 1, 1.0, signal_id="S1")
    out = dsr.process_symbol("tok", "NIFTY")
    (t,) = env.trades
    assert t["direction"] == "BEARISH" and t["trading_mode"] == "PAPER" and t["source"] == "dynamic_sr_instant"
    assert "CONFIRMED" in out and "confirmation" in env.tg[0]


def test_real_gate_with_trend_confirmed_vs_against_trend(env, monkeypatch):
    """खरा cycle_gate (फक्त data fakes): demand area 990–1000, UP trend ⇒ CONFIRMED BULLISH; DOWN trend ⇒ ignored (against trend)."""
    monkeypatch.setattr(LGB, "cycle_gate", REAL_CYCLE_GATE)
    env.zones = pd.DataFrame([
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 990.0, "zone_high": 1000.0, "strength": 3.0,
         "formed_date": "2026-09-01", "status": "ACTIVE"},
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 1090.0, "zone_high": 1100.0, "strength": 3.0,
         "formed_date": "2026-09-01", "status": "ACTIVE"}])
    env.candles = _one_min([(1008, 1009, 1006, 1008)] * 20)
    today = PULL + [TOUCH, SWEEP, BULL_ENGULF]                             # शेवटचा bar 09:55–10:00 = NOW ला बंद
    day0 = pd.Timestamp("2026-09-11 09:15")
    bars = pd.DataFrame([(1030.0, 1034.0, 1026.0, 1030.0)] * 30 + today, columns=["open", "high", "low", "close"])
    bars.insert(0, "timestamp", [day0 - pd.Timedelta(days=1) + pd.Timedelta(minutes=5 * i) for i in range(30)]
                + [day0 + pd.Timedelta(minutes=5 * i) for i in range(len(today))])
    monkeypatch.setattr(upstox_api, "fetch_candles", lambda *a, **k: bars.copy() if k.get("interval") == "5minute" else None)

    monkeypatch.setattr(LR, "daily_trend", lambda *a, **k: UP_CTX)
    dsr.process_symbol("tok", "NIFTY")
    (v,) = env.vision
    assert v["direction"] == "BULLISH" and v["level"] == 990.0 and v["tags"]["gate"]["entry"] == 1008.0
    assert v["tags"]["gate"]["target"] == 1090.0 and v["tags"]["gate"]["rr"] >= 3

    env.vision.clear()
    env.logs.clear()
    monkeypatch.setattr(LR, "daily_trend", lambda *a, **k: DOWN_CTX)
    dsr.process_symbol("tok", "NIFTY")
    assert not env.vision and not env.trades
    assert _log(env, 990.0)[0]["trade_status"] == "SKIPPED_GATE_AGAINST_TREND"


def test_breakout_paths_disabled_in_confirmation(env, monkeypatch):
    env.settings = _settings(entry_breakout_gate_enabled=True, breakout_direction_from_close=True)
    env.gate = FakeGate({23900.0: CONFIRMED_BEAR})
    monkeypatch.setattr(dsr, "check_breakout_candle_close", _boom)
    dsr.process_symbol("tok", "NIFTY")
    assert "5minute" not in env.fetches                                     # breakout / catch-up चे 5M candles सुद्धा नाहीत
    (v,) = env.vision
    assert v["tags"]["breakout_entry"] is False and v["tags"]["directional"] is False
    assert "breakout_eval" not in _log(env, 23900.0)[0]


def test_iv_breakout_does_not_flip_direction_in_confirmation(env, monkeypatch):
    env.settings = _settings(entry_iv_gate_enabled=True)
    env.gate = FakeGate({23900.0: CONFIRMED_BEAR})
    monkeypatch.setattr(dsr, "check_iv_change_gate", lambda *a: (False, 30.0, "IV jump"))
    dsr.process_symbol("tok", "NIFTY")
    assert not env.vision and not env.trades
    assert _log(env, 23900.0)[0]["trade_status"] == "SKIPPED_IV_GATE"


def test_rsi_gate_only_with_conf_key(env, monkeypatch):
    env.settings = _settings(conf_rsi_gate_enabled=True)
    env.gate = FakeGate({23900.0: CONFIRMED_BEAR})
    monkeypatch.setattr(dsr, "check_instant_rsi_filter", lambda *a: (False, 50.0))
    dsr.process_symbol("tok", "NIFTY")
    assert not env.vision and _log(env, 23900.0)[0]["trade_status"] == "SKIPPED_RSI_FILTER"


def test_gate_exception_fails_closed(env):
    env.candles, env.gate = TOUCHING, RuntimeError("upstox down")
    dsr.process_symbol("tok", "NIFTY")
    assert not env.vision and not env.trades and not env.tg
    assert {e["trade_status"] for e in env.logs} == {"SKIPPED_GATE_ERROR"}
    assert "RuntimeError" in _log(env, 23900.0)[0]["reason"]


@pytest.mark.parametrize("over", [{"trading_mode": "LIVE", "entry_mode": None}, {"entry_mode": "touch"}])
def test_touch_mode_unchanged_and_gate_never_built(env, monkeypatch, over):
    from bots_common import level_gate_bot as _LGB
    monkeypatch.setattr(_LGB, "entry_mode", _LGB._entry_mode_orig)        # review 🟡7: खरा default (conftest चा touch नाही)
    env.settings = _settings(**over)
    env.candles, env.gate = TOUCHING, AssertionError("touch mode मध्ये gate नाही")
    env.vg = VG.Gate("ENTER", 1, 1, 1.0)
    monkeypatch.setattr(dsr, "check_instant_rsi_filter", lambda *a: (True, 30.0))
    monkeypatch.setattr(dsr, "check_pcr_gate", lambda *a: (True, 1.0, "ok"))
    monkeypatch.setattr(LGB, "record_touch_legacy", _boom)
    dsr.process_symbol("tok", "NIFTY")
    assert not env.gate_calls
    (v,) = env.vision
    assert v["direction"] == "BULLISH" and v["tags"] == {"breakout_entry": False, "directional": False, "hit": "TOUCH"}
    (t,) = env.trades
    assert t["direction"] == "BULLISH" and t["trading_mode"] == env.settings["trading_mode"]
    assert _log(env, 24500.0)[0]["trade_status"] is None and _log(env, 24500.0)[0]["hit_type"] == "NO_HIT"


def test_forced_level_uses_recorded_direction_without_new_confirmation(env):
    env.candles, env.forced = BELOW, [(23900.0, "5M", "SUPPORT")]          # hysteresis BEARISH, gate IDLE — ✅ हीच confirmation
    env.vg = VG.Gate("ENTER", 1, 1, 1.0, signal_id="S1")
    dsr.process_symbol("tok", "NIFTY")
    (v,) = env.vision
    assert v["forced"] and v["direction"] == "BULLISH" and v["role"] == "SUPPORT"
    (t,) = env.trades
    assert t["direction"] == "BULLISH" and _log(env, 23900.0)[0]["hit_type"] == "VISION_FORCED"


def test_forced_level_without_known_direction_is_skipped(env):
    env.candles, env.forced = BELOW, [(23900.0, "5M", "?")]
    dsr.process_symbol("tok", "NIFTY")
    assert not env.vision and not env.trades
    assert _log(env, 23900.0)[0]["trade_status"] == "SKIPPED_VISION_FORCED_STALE"


def test_grade_lots():
    st = {"gate_grade_b_lot_mult": 0.5}
    assert dsr._grade_lots(3, {"grade": "A"}, st) == 3
    assert dsr._grade_lots(3, {"grade": "B"}, st) == 2
    assert dsr._grade_lots(1, {"grade": "B"}, st) == 1                    # चालू leg कधीच 0 नाही
    assert dsr._grade_lots(0, {"grade": "B"}, st) == 0                    # बंद leg बंदच
    assert dsr._grade_lots(3, {"grade": "B"}, {}) == 3                    # default 1.0 ⇒ बदल नाही


# ------------------------------------------------------------------------------------------------ SR V3 shadow
SNOW = datetime.datetime(2025, 3, 5, 11, 0)
STODAY = pd.DataFrame([{"timestamp": pd.Timestamp("2025-03-05 10:58"), "open": 22010.0, "high": 22012.0, "low": 22004.0, "close": 22008.0},
                       {"timestamp": pd.Timestamp("2025-03-05 10:59"), "open": 22008.0, "high": 22009.0, "low": 21999.5, "close": 22006.0}])


@pytest.fixture
def sh(monkeypatch):
    E = SimpleNamespace(opened=[], vision=[], gate_calls=[], gate=FakeGate(), forced=[])
    monkeypatch.setattr(LGB, "_TOUCH_SEEN", set())
    monkeypatch.setattr(SH, "refresh_levels_if_due", lambda *a, **k: None)
    monkeypatch.setattr(SH, "has_open_trade_from_source", lambda sym, src: False)
    monkeypatch.setattr(SH, "active_levels", lambda sym: [22000.0, 22300.0])
    monkeypatch.setattr(SH, "count_entries_at_level_today", lambda *a: 0)
    monkeypatch.setattr(SH, "get_last_sl_tsl_exit_time", lambda *a: None)
    monkeypatch.setattr(SH, "is_todays_expiry_day", lambda t, s: False)
    monkeypatch.setattr(SH, "fetch_upstox_option_chain", lambda t, s, expiry_index=0: ([{"underlying_spot_price": 22006.0}], "ok"))
    monkeypatch.setattr(SH, "select_credit_spread_itm", lambda *a, **k: {"strategy": "SPREAD"})
    monkeypatch.setattr(SH, "select_naked_option_itm", lambda *a, **k: {"strategy": "NAKED"})
    monkeypatch.setattr(SH, "open_multi_leg_trade", lambda *a, **k: E.opened.append(k) or (True, {"trade_id": "x"}))
    monkeypatch.setattr(SH, "format_trade_result", lambda ok, r: "OPENED")
    monkeypatch.setattr(SH, "send_telegram_message", lambda m: None)

    def cycle_gate(bot, symbol, token, settings, areas, now):
        E.gate_calls.append((bot, list(areas)))
        if isinstance(E.gate, Exception):
            raise E.gate
        return E.gate
    monkeypatch.setattr(LGB, "cycle_gate", cycle_gate)

    def gate_fn(bot, symbol, mode, direction, level, role, tf, ts, spot, lots, naked, tags=None, last_bar=None, forced=False):
        E.vision.append({"bot": bot, "mode": mode, "direction": direction, "level": level, "tags": tags, "forced": forced})
        return VG.Gate("ENTER", lots, naked, 1.0, signal_id="S")
    E.gate_fn = gate_fn

    def run(**kw):
        s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        s.update({"srv3_shadow_enabled": True, "symbol_enabled": True, "entry_mode": "confirmation"})
        s.update(kw)
        return SH.run_shadow("t", "NIFTY", now=SNOW, settings=s, fetch=lambda *a, **k: STODAY, gate_fn=gate_fn,
                             forced_fn=lambda *a: list(E.forced))
    E.run = run
    return E


def test_srv3_confirmed_goes_through_vision_with_gate_tags_and_paper_only(sh):
    sh.gate = FakeGate({22300.0: dict(CONFIRMED_BEAR, entry_price=22290.0)})
    sh.run()
    assert sh.gate_calls[0][0] == "srv3_instant" and len(sh.gate_calls[0][1]) == 2
    (v,) = sh.vision
    assert v["bot"] == "srv3_instant" and v["direction"] == "BEARISH" and v["level"] == 22300.0 and v["mode"] == "PAPER"
    assert v["tags"]["srv3"] is True and v["tags"]["gate"]["side"] == "BEARISH" and not v["forced"]
    assert sh.opened and all(k["trading_mode"] == "PAPER" and k["source"] == SH.SOURCE and k["direction"] == "BEARISH" for k in sh.opened)


def test_srv3_touch_without_reaction_would_have_only(sh):
    sh.gate = FakeGate({22000.0: ARMED_BULL})                             # 22000 ला जुना touch (STODAY low 21999.5)
    out = sh.run()
    assert not sh.vision and not sh.opened and "waiting for a bullish commitment" in out
    wh = [r for r in PJ.would_have_rows() if r["bot"] == "srv3_instant_touch_legacy"]
    assert len(wh) == 1 and wh[0]["level"] == 22000.0 and wh[0]["orig_lots"] == 0


def test_srv3_gate_exception_fails_closed(sh):
    sh.gate = RuntimeError("no candles")
    out = sh.run()
    assert not sh.vision and not sh.opened and "fail-closed" in out


def test_srv3_forced_level_still_enters_with_recorded_direction(sh):
    sh.forced = [(22000.0, "5M", "Support")]
    sh.run()
    (v,) = sh.vision
    assert v["forced"] and v["direction"] == "BULLISH" and sh.opened


def test_srv3_follows_parent_live_touch_mode_but_orders_stay_paper(sh, monkeypatch):
    from bots_common import level_gate_bot as _LGB
    monkeypatch.setattr(_LGB, "entry_mode", _LGB._entry_mode_orig)        # review 🟡7: खरा default
    sh.gate = AssertionError("touch mode मध्ये gate नाही")
    monkeypatch.setattr(SH, "evaluate_touch", lambda *a, **k: ("BULLISH", "TOUCH") if a[0] == 22000.0 else (None, "touch नाही"))
    sh.run(trading_mode="LIVE", entry_mode=None)
    assert not sh.gate_calls
    (v,) = sh.vision
    assert v["tags"] == {"srv3": True}
    assert sh.opened and all(k["trading_mode"] == "PAPER" for k in sh.opened)
