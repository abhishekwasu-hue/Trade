"""tests/test_opportunity_engine_bias.py -- HTF bias resolver, alignment gate, Daily veto (a/b/c), RANGE location, pullback watch (spec §3, plan v2 §0.2)."""
import pandas as pd
import pytest

from opportunity_engine import bias as B
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import Context, TFState
from opportunity_engine.detectors.base import Candidate

NOW = pd.Timestamp("2025-01-08 10:30")


def ctx_of(states, levels=(), price=24300.0, adr=200.0, protected=None):
    protected = protected or {}
    tfs = {tf: TFState(tf=tf, state=st, protected=protected.get(tf), range_high=(24500.0 if st == "RANGE" else None),
                       range_low=(24100.0 if st == "RANGE" else None), updated_at=NOW) for tf, st in states.items()}
    return Context(time=NOW, price=price, states=tfs, levels=list(levels), adr=adr)


def cand(direction="LONG", setup="D6", kind="PULLBACK_END", entry=24300.0, sl=24280.0):
    return Candidate(setup_id=setup, direction=direction, time=NOW, entry=entry, sl_ref=sl, kind=kind)


def zone(kind, low, high, tf="1d", grade="A", freshness="FRESH", source="", status="ACTIVE", reject=None, **kw):
    return {"kind": kind, "low": low, "high": high, "core_low": low, "core_high": high, "tf": tf, "quality_grade": grade, "freshness": freshness,
            "source": source, "status": status, "reject_reason": reject, "level_id": f"{kind}{low}", **kw}


CFG = EngineConfig()
UP_ALL = {"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND"}


# ---- bias table -------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("states,label,mode", [
    ({"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND"}, B.LONG_ONLY, "FULL"),
    ({"1d": "UPTREND", "4h": "UPTREND_PULLBACK", "1h": "UPTREND"}, B.LONG_ONLY, "FULL"),
    ({"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND_PULLBACK"}, B.LONG_WAIT, "PULLBACK_END"),
    ({"1d": "UPTREND", "4h": "UPTREND", "1h": "DOWNTREND"}, B.LONG_WAIT, "PULLBACK_END"),
    ({"1d": "UPTREND", "4h": "UPTREND", "1h": "RANGE"}, B.LONG_WAIT, "PULLBACK_END"),
    ({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, B.SHORT_ONLY, "FULL"),
    ({"1d": "DOWNTREND", "4h": "DOWNTREND_PULLBACK", "1h": "UPTREND"}, B.SHORT_WAIT, "PULLBACK_END"),
    ({"1d": "UPTREND", "4h": "UPTREND_WEAK", "1h": "UPTREND"}, B.NO_TRADE, "NONE"),
    ({"1d": "UPTREND", "4h": "DOWNTREND_WEAK", "1h": "DOWNTREND"}, B.NO_TRADE, "NONE"),
    ({"1d": "UPTREND", "4h": "RANGE", "1h": "UPTREND"}, B.RANGE_EDGES, "RANGE"),
    ({"1d": "UPTREND", "4h": "INIT", "1h": "UPTREND"}, B.NO_TRADE, "NONE"),
])
def test_bias_table_with_4h_primary(states, label, mode):
    b = B.resolve_bias(ctx_of(states), CFG)
    assert b.label == label and b.mode == mode and b.reasons


def test_weak_half_size_option_and_daily_as_primary():
    weak = {"1d": "UPTREND", "4h": "UPTREND_WEAK", "1h": "UPTREND"}
    b = B.resolve_bias(ctx_of(weak), EngineConfig(weak_half_size=True))
    assert b.label == B.LONG_WAIT and b.size_factor == 0.5 and b.direction == 1
    daily_primary = B.resolve_bias(ctx_of({"1d": "DOWNTREND", "4h": "UPTREND", "1h": "UPTREND"}), EngineConfig(primary_htf="1d"))
    assert daily_primary.label == B.SHORT_WAIT and daily_primary.primary_tf == "1d"
    missing = B.resolve_bias(ctx_of({"1h": "UPTREND"}), CFG)
    assert missing.label == B.NO_TRADE


def test_daily_early_reversal_flags():
    b = B.resolve_bias(ctx_of({"1d": "DOWNTREND_WEAK", "4h": "UPTREND", "1h": "UPTREND"}), CFG)
    assert b.daily_early_reversal_long and not b.daily_early_reversal_short
    b2 = B.resolve_bias(ctx_of({"1d": "UPTREND_WEAK", "4h": "DOWNTREND", "1h": "DOWNTREND"}), CFG)
    assert b2.daily_early_reversal_short


# ---- gate: alignment / mode ----------------------------------------------------------------------------------------------------------
def test_aligned_pullback_end_long_passes_in_long_only():
    ctx = ctx_of(UP_ALL)
    g = B.apply_gate(cand(), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert g.passed and g.codes == [] and not g.pullback_in_progress


def test_counter_trend_candidate_is_misaligned():
    ctx = ctx_of(UP_ALL)
    g = B.apply_gate(cand("SHORT", "D7", "BREAKOUT", 24300, 24330), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert not g.passed and g.primary_code == "HTF_MISALIGNED" and g.reasons


def test_wait_pullback_end_blocks_breakouts_but_allows_pullback_setups():
    ctx = ctx_of({"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND_PULLBACK"})
    bias = B.resolve_bias(ctx, CFG)
    assert B.apply_gate(cand("LONG", "D7", "BREAKOUT"), bias, ctx, CFG).primary_code == "HTF_WAIT_PULLBACK"
    for setup in ("D3", "D4", "D6", "D10"):
        assert B.apply_gate(cand("LONG", setup, "PULLBACK_END"), bias, ctx, CFG).passed, setup


def test_no_trade_bias_rejects_everything():
    ctx = ctx_of({"1d": "UPTREND", "4h": "UPTREND_WEAK", "1h": "UPTREND"})
    g = B.apply_gate(cand(), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert g.primary_code == "NO_TRADE"


# ---- Daily veto ---------------------------------------------------------------------------------------------------------------------------
def test_daily_veto_a_opposing_trend_but_not_downtrend_weak():
    for daily, expect in (("DOWNTREND", "DAILY_VETO_A"), ("DOWNTREND_PULLBACK", "DAILY_VETO_A"), ("DOWNTREND_WEAK", None)):
        ctx = ctx_of({"1d": daily, "4h": "UPTREND", "1h": "UPTREND"})
        g = B.apply_gate(cand(), B.resolve_bias(ctx, CFG), ctx, CFG)
        assert (expect in g.codes) if expect else ("DAILY_VETO_A" not in g.codes and g.passed), (daily, g.codes)


def test_daily_veto_b_same_direction_weak():
    ctx = ctx_of({"1d": "UPTREND_WEAK", "4h": "UPTREND", "1h": "UPTREND"})
    assert "DAILY_VETO_B" in B.apply_gate(cand(), B.resolve_bias(ctx, CFG), ctx, CFG).codes


def test_daily_veto_c_fresh_supply_or_ab_resistance_within_1_5r():
    # R = 20; Daily FRESH supply 24320 => अंतर 20 < 1.5R (30) => veto c
    ctx = ctx_of(UP_ALL, levels=[zone("SUPPLY", 24320, 24340, tf="1d")])
    g = B.apply_gate(cand(), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert "DAILY_VETO_C" in g.codes and "NO_ROOM" in g.codes
    far = ctx_of(UP_ALL, levels=[zone("SUPPLY", 24500, 24520, tf="1d")])
    assert B.apply_gate(cand(), B.resolve_bias(far, CFG), far, CFG).passed
    c_grade = ctx_of(UP_ALL, levels=[zone("RESISTANCE", 24325, 24330, tf="1d", grade="B", freshness="TESTED_2+")])
    assert "DAILY_VETO_C" in B.apply_gate(cand(), B.resolve_bias(c_grade, CFG), c_grade, CFG).codes
    weak_grade = ctx_of(UP_ALL, levels=[zone("RESISTANCE", 24325, 24330, tf="1d", grade="C", freshness="TESTED_2+")])
    assert B.apply_gate(cand(), B.resolve_bias(weak_grade, CFG), weak_grade, CFG).passed


def test_daily_veto_can_be_turned_off_and_not_applied_when_daily_is_primary():
    ctx = ctx_of({"1d": "DOWNTREND", "4h": "UPTREND", "1h": "UPTREND"})
    g = B.apply_gate(cand(), B.resolve_bias(ctx, EngineConfig(daily_veto=False)), ctx, EngineConfig(daily_veto=False))
    assert g.passed
    cfg1d = EngineConfig(primary_htf="1d")
    ctx2 = ctx_of({"1d": "UPTREND", "4h": "DOWNTREND", "1h": "UPTREND"})
    assert B.apply_gate(cand(), B.resolve_bias(ctx2, cfg1d), ctx2, cfg1d).passed


def test_daily_range_needs_2_5r_from_the_range_edge():
    base = {"1d": "RANGE", "4h": "UPTREND", "1h": "UPTREND"}
    near = ctx_of(base, price=24300)                       # range_high 24500; R=20 => 2.5R=50; entry 24300 => 200 दूर => ठीक
    assert B.apply_gate(cand(), B.resolve_bias(near, CFG), near, CFG).passed
    close = ctx_of(base, price=24480)
    g = B.apply_gate(cand(entry=24480, sl=24460), B.resolve_bias(close, CFG), close, CFG)
    assert "DAILY_RANGE_LOCATION" in g.codes
    short_close = ctx_of({"1d": "RANGE", "4h": "DOWNTREND", "1h": "DOWNTREND"}, price=24120)
    g2 = B.apply_gate(cand("SHORT", "D6", "PULLBACK_END", 24120, 24140), B.resolve_bias(short_close, CFG), short_close, CFG)
    assert "DAILY_RANGE_LOCATION" in g2.codes


# ---- room / protected level / range location ---------------------------------------------------------------------------------------
def test_no_room_uses_htf_zones_only_and_ignores_broken_or_weak_ones():
    ctx = ctx_of(UP_ALL, levels=[zone("SUPPLY", 24310, 24330, tf="1h")])
    assert "NO_ROOM" in B.apply_gate(cand(), B.resolve_bias(ctx, CFG), ctx, CFG).codes
    ltf = ctx_of(UP_ALL, levels=[zone("SUPPLY", 24310, 24330, tf="15m")])
    assert B.apply_gate(cand(), B.resolve_bias(ltf, CFG), ltf, CFG).passed
    broken = ctx_of(UP_ALL, levels=[zone("SUPPLY", 24310, 24330, tf="1h", status="BROKEN", reject="तुटलेला")])
    assert B.apply_gate(cand(), B.resolve_bias(broken, CFG), broken, CFG).passed
    below = ctx_of(UP_ALL, levels=[zone("SUPPLY", 24100, 24120, tf="1h")])
    assert B.apply_gate(cand(), B.resolve_bias(below, CFG), below, CFG).passed
    short_ctx = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, levels=[zone("DEMAND", 24260, 24290, tf="4h")])
    g = B.apply_gate(cand("SHORT", "D6", "PULLBACK_END", 24300, 24320), B.resolve_bias(short_ctx, CFG), short_ctx, CFG)
    assert "NO_ROOM" in g.codes


def test_protected_level_rule_rejects_sl_beyond_primary_protected_low():
    ctx = ctx_of(UP_ALL, protected={"4h": 24285.0})
    g = B.apply_gate(cand(sl=24280.0), B.resolve_bias(ctx, CFG), ctx, CFG)                  # SL 24280 < protected 24285
    assert "PROTECTED_LEVEL" in g.codes and g.details["protected"] == 24285.0
    ok = B.apply_gate(cand(sl=24290.0), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert "PROTECTED_LEVEL" not in ok.codes
    s_ctx = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, protected={"4h": 24320.0})
    s = B.apply_gate(cand("SHORT", "D6", "PULLBACK_END", 24300, 24330), B.resolve_bias(s_ctx, CFG), s_ctx, CFG)
    assert "PROTECTED_LEVEL" in s.codes


def test_range_bias_requires_entry_near_the_edge():
    ctx = ctx_of({"1d": "RANGE", "4h": "RANGE", "1h": "RANGE"}, price=24300)              # 24100–24500, मध्य 24300
    bias = B.resolve_bias(ctx, CFG)
    mid = B.apply_gate(cand(entry=24300, sl=24280), bias, ctx, CFG)
    assert "RANGE_LOCATION" in mid.codes
    low_edge = B.apply_gate(cand(entry=24150, sl=24130), bias, ctx, CFG)
    assert "RANGE_LOCATION" not in low_edge.codes
    short_edge = B.apply_gate(cand("SHORT", "D2", "REVERSAL", 24450, 24470), bias, ctx, CFG)
    assert "RANGE_LOCATION" not in short_edge.codes
    short_mid = B.apply_gate(cand("SHORT", "D2", "REVERSAL", 24300, 24320), bias, ctx, CFG)
    assert "RANGE_LOCATION" in short_mid.codes


# ---- pullback watch ----------------------------------------------------------------------------------------------------------------------
def test_counter_trend_breakout_becomes_pullback_in_progress_with_a_watch_zone():
    levels = [zone("DEMAND", 24210, 24250, tf="1h", freshness="FRESH"), zone("DEMAND", 24000, 24040, tf="4h"),
              zone("GAP", 24100, 24160, tf="1d", gap_status="UNFILLED"), zone("SUPPLY", 24600, 24640, tf="1d")]
    ctx = ctx_of(UP_ALL, levels=levels, price=24300)
    g = B.apply_gate(cand("SHORT", "D7", "BREAKOUT", 24300, 24330), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert g.primary_code == "HTF_MISALIGNED" and g.pullback_in_progress
    assert g.watch["zone_low"] == 24210 and g.watch["zone_high"] == 24250 and g.watch["tf"] == "1h" and not g.watch["flip"]
    reversal = B.apply_gate(cand("SHORT", "D2", "REVERSAL", 24300, 24330), B.resolve_bias(ctx, CFG), ctx, CFG)
    assert not reversal.pullback_in_progress and reversal.watch is None                   # फक्त breakout counter-trend = pullback


def test_watch_zone_can_be_a_flip_zone_and_mirrors_for_downtrend():
    flip = zone("SUPPLY", 24220, 24260, tf="1h", status="BROKEN", reject="तुटलेला", flipped=True)
    ctx = ctx_of(UP_ALL, levels=[flip], price=24300)
    w = B.pullback_watch_zone(ctx, 1)
    assert w and w["flip"] and w["zone_low"] == 24220
    dn = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, levels=[zone("SUPPLY", 24350, 24380, tf="1h")], price=24300)
    assert B.pullback_watch_zone(dn, -1)["zone_low"] == 24350
    assert B.pullback_watch_zone(ctx_of(UP_ALL, levels=[], price=24300), 1) is None

