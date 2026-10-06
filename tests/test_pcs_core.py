"""tests/test_pcs_core.py — Pullback Credit Spread: settings (validation, presets, snapshot, diff), expiry निवड, strike modes + guards +
rounding, credit, lots, blackout, आणि exits (hard stop सर्वात आधी, false break वर exit नाही). Network/DB नाही."""
import datetime as dt

import pandas as pd
import pytest

from pullback_credit_spread import core as C
from pullback_credit_spread import settings as S

D = S.DEFAULTS


def cfg(**kw):
    return {**D, **kw}


# ---- settings ------------------------------------------------------------------------------------------------------------------------
def test_defaults_mode_off_and_every_setting_has_marathi_label_help_and_section():
    assert D["mode"] == "OFF"
    secs = {k for k, _ in S.SECTIONS}
    for s in S.SCHEMA:
        assert s["label"] and s["section"] in secs and s["type"] in ("bool", "int", "float", "choice", "time", "text")
        if s["type"] in ("int", "float"):
            assert s["min"] is not None and s["max"] is not None and s["min"] <= s["default"] <= s["max"]
    assert {s["section"] for s in S.SCHEMA} == secs                     # 11 विभाग सर्व वापरलेले


def test_validate_rejects_bad_values_and_cross_rules():
    clean, errs = S.validate({"width_points": 99999, "mode": "LIVE", "strike_mode": "magic", "min_distance_pct": 5, "max_distance_pct": 2,
                              "max_open_spreads": 1, "max_open_spreads_per_symbol": 3, "time_exit": "25:00", "unknown": 1})
    assert clean["width_points"] == D["width_points"] and clean["mode"] == "OFF" and clean["strike_mode"] == D["strike_mode"]
    assert clean["min_distance_pct"] <= clean["max_distance_pct"] and clean["max_open_spreads_per_symbol"] == 1
    assert clean["time_exit"] == D["time_exit"] and len(errs) >= 5


def test_validate_coerces_types():
    clean, errs = S.validate({"max_lots": "3", "skip_on_weak": "false", "risk_per_trade_pct": "0.7", "time_exit": "9:05"})
    assert clean["max_lots"] == 3 and clean["skip_on_weak"] is False and clean["risk_per_trade_pct"] == 0.7 and clean["time_exit"] == "09:05"
    assert errs == []


def test_presets_fill_all_and_are_valid():
    for name in S.PRESETS:
        p = S.preset(name)
        assert set(p) == set(D)
        clean, errs = S.validate(p)
        assert errs == [] and clean == p
    assert S.preset("Conservative")["risk_per_trade_pct"] < S.preset("Aggressive")["risk_per_trade_pct"]
    with pytest.raises(KeyError):
        S.preset("YOLO")


def test_snapshot_and_diff():
    a = S.snapshot(D)
    b = S.snapshot(cfg(max_lots=3))
    assert a["hash"] != b["hash"] and a["settings"]["max_lots"] == D["max_lots"]
    assert S.diff(D, cfg(max_lots=3)) == [("max_lots", D["max_lots"], 3)]


# ---- expiry --------------------------------------------------------------------------------------------------------------------------
EXP = ["2026-10-06", "2026-10-13", "2026-10-20", "2026-10-27", "2026-11-03", "2026-11-24"]


def test_today_expiry_moves_to_next():
    e, _ = C.select_expiry(EXP, "2026-10-06", cfg(min_dte=0))
    assert e == dt.date(2026, 10, 13)


def test_min_dte_skips_near_expiry():
    assert C.select_expiry(EXP, "2026-10-12", cfg(min_dte=1))[0] == dt.date(2026, 10, 13)
    assert C.select_expiry(EXP, "2026-10-12", cfg(min_dte=2))[0] == dt.date(2026, 10, 20)


def test_holiday_shifted_expiry_comes_from_master_not_weekday():
    exp = ["2026-10-14", "2026-10-20"]                                 # सुट्टीमुळे बुधवारी — master प्रमाणेच
    assert C.select_expiry(exp, "2026-10-12", cfg(min_dte=1))[0] == dt.date(2026, 10, 14)


def test_monthly_expiry():
    assert C.select_expiry(EXP, "2026-10-12", cfg(expiry_type="monthly"))[0] == dt.date(2026, 10, 27)


def test_no_expiry():
    assert C.select_expiry(["2026-01-01"], "2026-10-12", D)[0] is None


# ---- strikes -------------------------------------------------------------------------------------------------------------------------
def test_strike_step_from_master():
    assert C.strike_step([24000, 24050, 24100, 24150, 24300]) == 50
    assert C.strike_step([50000, 50100, 50200, 50300]) == 100
    assert C.strike_step([], fallback=50) == 50


def test_round_far_side():
    assert C.round_far(24123, 50, "PUT") == 24100 and C.round_far(24123, 50, "CALL") == 24150


@pytest.mark.parametrize("side, expect", [("PUT", 23800.0), ("CALL", 24350.0)])
def test_beyond_level(side, expect):
    level = 23900.0 if side == "PUT" else 24250.0
    k, why = C.short_strike(side, 24100.0, cfg(beyond_level_buffer_pct=0.3, min_distance_pct=0.5), 50, level=level)
    assert why is None and k == expect


def test_min_distance_guard_pushes_strike_further():
    k, _ = C.short_strike("PUT", 24100.0, cfg(beyond_level_buffer_pct=0.0, min_distance_pct=1.0), 50, level=24050.0)
    assert k == 23850.0                                                 # 24100 × 0.99 = 23859 → खाली 23850


def test_max_distance_guard_blocks():
    k, why = C.short_strike("PUT", 24100.0, cfg(distance_pct=5.0, strike_mode="distance_pct", max_distance_pct=4.0), 50)
    assert k is None and "कमाल" in why


def test_strikes_otm_and_level_missing():
    k, _ = C.short_strike("CALL", 24110.0, cfg(strike_mode="strikes_otm", strikes_otm=6, min_distance_pct=0.0), 50)
    assert k == 24400.0
    assert C.short_strike("PUT", 24100.0, D, 50, level=None)[0] is None


def test_delta_and_premium_modes_use_chain():
    chain = pd.DataFrame({"strike": [23700, 23800, 23900, 24300], "type": ["PE", "PE", "PE", "CE"],
                          "ltp": [8.0, 14.0, 25.0, 30.0], "delta": [-0.08, -0.14, -0.22, 0.2]})
    k, _ = C.short_strike("PUT", 24100.0, cfg(strike_mode="delta", target_delta=0.15, min_distance_pct=0.0), 50, chain=chain)
    assert k == 23800.0
    k, _ = C.short_strike("PUT", 24100.0, cfg(strike_mode="premium", target_premium=24.0, min_distance_pct=0.0), 50, chain=chain)
    assert k == 23900.0


def test_long_strike_width_modes():
    assert C.long_strike("PUT", 23800, cfg(width_mode="points", width_points=200), 50) == 23600
    assert C.long_strike("CALL", 24400, cfg(width_mode="strikes", width_strikes=3), 50) == 24550
    assert C.long_strike("PUT", 23800, cfg(width_mode="points", width_points=230), 50) == 23550     # step ला वर गोल


def test_credit_guards():
    assert C.credit_check(30, 8, 23800, 23600, cfg(min_credit=5, min_credit_to_width_ratio=0.1))[2] is None
    assert "किमान" in C.credit_check(9, 6, 23800, 23600, cfg(min_credit=5))[2]
    assert "credit/width" in C.credit_check(20, 5, 23800, 23600, cfg(min_credit=5, min_credit_to_width_ratio=0.1))[2]


# ---- risk / events -------------------------------------------------------------------------------------------------------------------
def test_lots_sizing_cap_and_event():
    lots, per_lot, why = C.lots_for(1_000_000, 30, 200, 75, cfg(risk_per_trade_pct=2.0, max_lots=10))
    assert per_lot == 170 * 75 and lots == 1 and why is None             # 20000 / 12750 = 1.56 → 1
    assert C.lots_for(10_000_000, 30, 200, 75, cfg(risk_per_trade_pct=2.0, max_lots=4))[0] == 4
    assert C.lots_for(10_000_000, 30, 200, 75, cfg(risk_per_trade_pct=1.0, max_lots=10), event_day=True)[0] == 3     # floor(7.8)=7 × 0.5 ⇒ 3
    assert C.lots_for(100_000, 30, 200, 75, D)[0] == 0


def test_capacity():
    assert C.capacity_ok(0, 0, 0, D)[0]
    assert not C.capacity_ok(2, 0, 0, cfg(max_open_spreads=2))[0]
    assert not C.capacity_ok(0, 1, 0, cfg(max_open_spreads_per_symbol=1))[0]
    assert not C.capacity_ok(0, 0, 6000, cfg(daily_loss_cap=5000))[0]


def test_blackout_event_window_and_expiry_morning():
    s = cfg(event_dates="2026-10-09", event_blackout_start="09:15", event_blackout_end="11:30", blackout_expiry_morning_until="10:30")
    assert C.blackout("2026-10-09 11:00", [], s)[0] and not C.blackout("2026-10-09 12:00", [], s)[0]     # window बाहेर ⇒ entry चालते
    assert C.is_event_day("2026-10-09 12:00", s)                                                         # ⇒ size × गुणक
    assert C.blackout("2026-10-13 10:00", EXP + ["2026-10-13"], s)[0] and not C.blackout("2026-10-13 10:45", ["2026-10-13"], s)[0]
    assert not C.blackout("2026-10-09 11:00", [], cfg(event_blackout_enabled=False, event_dates="2026-10-09"))[0]


def test_nan_and_bad_event_dates_rejected():
    clean, errs = S.validate({"hard_stop_credit_multiple": float("nan"), "risk_per_trade_pct": "inf", "event_dates": "2026-10-09, 9 Oct"})
    assert clean["hard_stop_credit_multiple"] == D["hard_stop_credit_multiple"] and clean["risk_per_trade_pct"] == D["risk_per_trade_pct"]
    assert clean["event_dates"] == "" and len(errs) == 3


def test_tie_break_and_beyond_level_wrong_side_and_points():
    chain = pd.DataFrame({"strike": [24300, 24350], "type": ["CE", "CE"], "ltp": [20.0, 20.0], "delta": [0.15, 0.15]})
    k, _ = C.short_strike("CALL", 24100.0, cfg(strike_mode="premium", target_premium=20.0, min_distance_pct=0.0), 50, chain=chain)
    assert k == 24350.0                                                  # बरोबरी ⇒ दूरचा
    assert C.short_strike("PUT", 24100.0, D, 50, level=24200.0)[0] is None            # support spot च्या वर ⇒ नाही
    k, _ = C.short_strike("PUT", 24100.0, cfg(beyond_level_unit="points", beyond_level_buffer_points=60, min_distance_pct=0.5), 50, level=23950.0)
    assert k == 23850.0                                                  # 23950 − 60 = 23890 → खाली 23850


def test_call_side_spot_stop_real_break_rounding():
    pos = {"side": "CALL", "short_k": 24400.0, "credit": 30.0, "expiry": "2026-10-13", "level_lo": 24280.0, "level_hi": 24320.0}
    assert C.exit_decision(pos, 25.0, 24300.0, "2026-10-10 10:00", cfg(spot_stop_distance_pct=0.5))[0] == "SPOT_STOP"
    assert C.exit_decision(pos, 25.0, 24000.0, "2026-10-10 10:00", cfg(spot_stop_distance_pct=0.5))[0] is None
    s = cfg(break_buffer_pct=0.1, no_reclaim_bars=3)
    assert C.real_break(_bars([24250, 24360, 24370, 24380, 24390]), 24280, 24320, "CALL", s)[0]
    assert not C.real_break(_bars([24250, 24360, 24300, 24290, 24280]), 24280, 24320, "CALL", s)[0]
    assert C.round_far(24301, 50, "CALL") == 24350


def test_hard_stop_beats_target_and_break_together():
    real = _bars([23950, 23840, 23830, 23820, 23810])
    assert C.exit_decision(POS, 75.0, 23500.0, "2026-10-13 15:00", D, break_bars=real)[0] == "HARD_STOP"


def test_time_exit_after_missed_expiry_day():
    assert C.exit_decision(POS, 25.0, 24500.0, "2026-10-14 09:20", D)[0] == "TIME_EXIT"


# ---- exits ---------------------------------------------------------------------------------------------------------------------------
POS = {"side": "PUT", "short_k": 23800.0, "credit": 30.0, "expiry": "2026-10-13", "level_lo": 23880.0, "level_hi": 23920.0}


def _bars(closes):
    return pd.DataFrame({"close": closes})


def test_hard_stop_bypasses_everything():
    # profit/spot/time सगळं "ठीक" दिसलं तरी spread ≥ 2× credit ⇒ HARD_STOP
    r, _ = C.exit_decision(POS, 61.0, 24500.0, "2026-10-10 10:00", cfg(real_break_exit=False))
    assert r == "HARD_STOP"


def test_profit_target_and_spot_stop_and_time():
    assert C.exit_decision(POS, 11.0, 24500.0, "2026-10-10 10:00", D)[0] == "TARGET"
    assert C.exit_decision(POS, 25.0, 23900.0, "2026-10-10 10:00", cfg(spot_stop_distance_pct=0.5))[0] == "SPOT_STOP"
    assert C.exit_decision(POS, 25.0, 24500.0, "2026-10-13 14:31", D)[0] == "TIME_EXIT"
    assert C.exit_decision(POS, 25.0, 24500.0, "2026-10-13 14:00", D)[0] is None


def test_false_break_no_exit_real_break_exit():
    s = cfg(break_buffer_pct=0.1, no_reclaim_bars=3)
    false_break = _bars([23950, 23840, 23900, 23930, 23950])            # खाली close, मग परत आत ⇒ false break
    assert C.real_break(false_break, 23880, 23920, "PUT", s)[0] is False
    assert C.exit_decision(POS, 25.0, 24500.0, "2026-10-10 10:00", s, break_bars=false_break)[0] is None
    real = _bars([23950, 23840, 23830, 23820, 23810])                   # 3 bars reclaim नाही ⇒ खरा break
    assert C.real_break(real, 23880, 23920, "PUT", s)[0] is True
    assert C.exit_decision(POS, 25.0, 24500.0, "2026-10-10 10:00", s, break_bars=real)[0] == "REAL_BREAK"
    pending = _bars([23950, 23840, 23830])                              # अजून 3 bars झाले नाहीत ⇒ अजून नाही
    assert C.real_break(pending, 23880, 23920, "PUT", s)[0] is False
