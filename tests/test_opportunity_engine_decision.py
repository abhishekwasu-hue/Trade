"""tests/test_opportunity_engine_decision.py -- validation (§5), risk/exit (§8), scoring (§6), selector (§7), commentary (§9), engine pipeline; कृत्रिम, network-free."""
import pandas as pd
import pytest

from opportunity_engine import commentary as cm
from opportunity_engine import risk as R
from opportunity_engine import scoring as S
from opportunity_engine import selector as SEL
from opportunity_engine import validation as V
from opportunity_engine.bias import resolve_bias
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import Context, TFState
from opportunity_engine.detectors.base import Candidate
from opportunity_engine.engine import Decision, evaluate

CFG = EngineConfig()
NOW = pd.Timestamp("2025-01-08 10:30")
UP_ALL = {"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND"}


def ctx_of(states=None, levels=(), price=24316.0, adr=200.0, extra=None):
    states = states or UP_ALL
    extra = extra or {}
    tfs = {tf: TFState(tf=tf, state=st, updated_at=NOW, **extra.get(tf, {})) for tf, st in states.items()}
    return Context(time=NOW, price=price, states=tfs, levels=list(levels), adr=adr)


GOOD = {"open": 24300.0, "high": 24318.0, "low": 24298.0, "close": 24316.0, "volume": 1700.0, "volume_median": 1000.0, "level": 24310.0, "ref_range": 10.0}


def cand(direction="LONG", setup="D7", kind="BREAKOUT", entry=24316.0, sl=24296.0, trigger=None, zone=None, quality=70.0, **kw):
    return Candidate(setup_id=setup, direction=direction, time=NOW, entry=entry, sl_ref=sl, kind=kind, setup_quality=quality,
                     trigger=dict(trigger or GOOD), zone=zone, **kw)


A_ZONE = {"kind": "DEMAND", "tf": "1h", "low": 24280.0, "high": 24300.0, "freshness": "FRESH", "quality_grade": "A", "mtf_count": 3}


# ---- validation -----------------------------------------------------------------------------------------------------------------------
def test_perfect_breakout_scores_100_and_passes():
    v = V.validate_breakout(GOOD, "LONG", 24310.0, 10.0, CFG, vol_median=1000.0, room_r=3.0)
    assert v.score == 100 and v.passed and not v.hard_fail and not v.volume_na


def test_wick_only_breakout_is_a_hard_fail():
    bar = {"open": 24300.0, "high": 24318.0, "low": 24298.0, "close": 24305.0, "volume": 1700.0}
    v = V.validate_breakout(bar, "LONG", 24310.0, 10.0, CFG, vol_median=1000.0, room_r=3.0)
    assert "WICK_ONLY" in v.hard_fail and not v.passed and any("Wick-only" in r for r in v.reasons)


def test_individual_checks_and_exhaustion():
    weak_body = {"open": 24306.0, "high": 24316.0, "low": 24296.0, "close": 24314.0, "volume": 1700.0}
    v = V.validate_breakout(weak_body, "LONG", 24310.0, 10.0, CFG, vol_median=1000.0, room_r=3.0)
    assert not v.checks["body"]["pass"] and v.checks["close_loc"]["pass"]
    huge = {"open": 24270.0, "high": 24330.0, "low": 24268.0, "close": 24328.0, "volume": 1700.0}
    vh = V.validate_breakout(huge, "LONG", 24310.0, 10.0, CFG, vol_median=1000.0, room_r=3.0)
    assert not vh.checks["exhaustion"]["pass"] and vh.score == 100 - CFG.val_weights["exhaustion"]
    low_vol = V.validate_breakout({**GOOD, "volume": 900.0}, "LONG", 24310.0, 10.0, CFG, vol_median=1000.0, room_r=3.0)
    assert low_vol.checks["volume"]["pass"] is False and low_vol.score == 100 - CFG.val_weights["volume"]


def test_volume_na_moves_its_points_to_range_expansion():
    v = V.validate_breakout({**GOOD, "volume": None}, "LONG", 24310.0, 10.0, CFG, vol_median=None, room_r=3.0)
    assert v.volume_na and v.score == 100 and v.checks["volume"]["pass"] is None
    small = {"open": 24306.0, "high": 24314.0, "low": 24305.0, "close": 24313.0}               # expansion फेल (range 9 < 12)
    v2 = V.validate_breakout(small, "LONG", 24310.0, 10.0, CFG, vol_median=None, room_r=3.0)
    assert not v2.checks["expansion"]["pass"] and v2.score <= 100 - (CFG.val_weights["expansion"] + CFG.val_weights["volume"])


def test_room_below_1_5r_is_a_hard_fail_and_missing_data_is_rejected():
    v = V.validate_breakout(GOOD, "LONG", 24310.0, 10.0, CFG, vol_median=1000.0, room_r=1.2)
    assert "NO_ROOM" in v.hard_fail and not v.passed
    assert V.validate_breakout(GOOD, "LONG", 24310.0, float("nan"), CFG).hard_fail == ["DATA"]
    assert V.validate_breakout({"open": 1}, "LONG", 24310.0, 10.0, CFG).hard_fail == ["DATA"]


def test_short_breakout_mirror():
    bar = {"open": 24300.0, "high": 24302.0, "low": 24282.0, "close": 24284.0, "volume": 2000.0}
    v = V.validate_breakout(bar, "SHORT", 24290.0, 10.0, CFG, vol_median=1000.0, room_r=3.0)
    assert v.score == 100 and v.passed


def test_reversal_validation_components():
    bar = {"open": 24290.0, "high": 24312.0, "low": 24270.0, "close": 24308.0}            # लांब खालची wick, bullish close
    v = V.validate_reversal(bar, "LONG", {"high": 24300.0, "low": 24285.0}, {"low": 24265.0, "high": 24285.0}, 10.0, CFG)
    assert v.passed and v.score == 100 and v.kind == "REVERSAL"
    no_break = V.validate_reversal(bar, "LONG", {"high": 24320.0, "low": 24285.0}, {"low": 24265.0, "high": 24285.0}, 10.0, CFG)
    assert no_break.score == 75 and not no_break.checks["trigger_break"]["pass"]
    bearish = V.validate_reversal({"open": 24300.0, "high": 24302.0, "low": 24290.0, "close": 24291.0}, "LONG", {"high": 24310.0}, None, 10.0, CFG)
    assert not bearish.passed
    short = V.validate_reversal({"open": 24310.0, "high": 24330.0, "low": 24306.0, "close": 24308.0}, "SHORT", {"low": 24312.0}, {"low": 24320.0, "high": 24340.0}, 10.0, CFG)
    assert short.passed


# ---- risk: plan -------------------------------------------------------------------------------------------------------------------------
def test_plan_trade_buffer_t1_t2_and_adr_bounds():
    p = R.plan_trade(cand(), ctx_of(), CFG, rr=10.0, adr=200.0)
    assert p.sl == pytest.approx(24296 - 2.5) and p.risk == pytest.approx(22.5) and p.t1 == pytest.approx(24316 + 22.5) and p.t2 == pytest.approx(24316 + 45)
    assert p.ok and p.adr_ratio == pytest.approx(22.5 / 200)
    tight = R.plan_trade(cand(sl=24310.0), ctx_of(), CFG, rr=1.0, adr=200.0)                   # risk ~6 < 0.1×ADR (20)
    assert "SL_TOO_TIGHT" in tight.rejects
    wide = R.plan_trade(cand(sl=24150.0), ctx_of(), CFG, rr=10.0, adr=200.0)                    # risk ~168 > 0.6×ADR (120)
    assert "SL_TOO_WIDE" in wide.rejects
    no_adr = R.plan_trade(cand(), ctx_of(), CFG, rr=10.0, adr=float("nan"))
    assert no_adr.ok and no_adr.adr_ratio is None
    assert "SL_INVALID" in R.plan_trade(cand(sl=24400.0), ctx_of(), CFG, rr=10.0, adr=200.0).rejects


def test_t2_is_the_nearer_of_hint_zone_and_default_2r():
    zone = {"kind": "SUPPLY", "tf": "1h", "low": 24350.0, "high": 24370.0, "freshness": "FRESH", "quality_grade": "A", "status": "ACTIVE", "level_id": "z"}
    p = R.plan_trade(cand(), ctx_of(levels=[zone]), CFG, rr=10.0, adr=200.0)
    assert p.t2 == 24350.0 and p.rr_to_opposing == pytest.approx((24350 - 24316) / 22.5)           # zone, 2R (24361) पेक्षा जवळ
    hint = R.plan_trade(cand(targets_hint=[24345.0]), ctx_of(), CFG, rr=10.0, adr=200.0)
    assert hint.t2 == 24345.0
    short = R.plan_trade(cand("SHORT", entry=24300.0, sl=24320.0), ctx_of(), CFG, rr=10.0, adr=200.0)
    assert short.sl == pytest.approx(24322.5) and short.t1 < short.entry and short.t2 < short.t1


# ---- risk: exits ----------------------------------------------------------------------------------------------------------------------------
def pos_long(kind="BREAKOUT", level=24310.0):
    plan = R.plan_trade(cand(), ctx_of(), CFG, rr=10.0, adr=200.0)
    return R.open_position(plan, kind, level), plan


def bar(h, l, c, o=None):
    return {"open": c if o is None else o, "high": h, "low": l, "close": c}


def t(hhmm):
    return pd.Timestamp(f"2025-01-08 {hhmm}")


def test_same_bar_sl_and_target_resolves_to_sl_first():
    pos, plan = pos_long()
    R.on_bar(pos, bar(plan.t1 + 5, plan.sl - 1, plan.entry), CFG, t("10:35"))
    assert pos.closed and pos.exit_reason == "SL" and pos.pnl_pts < 0


def test_t1_books_half_moves_sl_to_breakeven_then_be_exit():
    pos, plan = pos_long()
    R.on_bar(pos, bar(plan.t1 + 1, plan.entry + 5, plan.t1), CFG, t("10:35"))
    assert pos.t1_done and pos.remaining == 0.5 and pos.sl == plan.entry and not pos.closed
    R.on_bar(pos, bar(plan.entry + 10, plan.entry - 1, plan.entry + 2), CFG, t("10:40"))
    assert pos.closed and pos.exit_reason == "BE"
    assert pos.pnl_pts == pytest.approx(0.5 * (plan.t1 - plan.slippage - plan.entry - plan.slippage) + 0.5 * (plan.entry - plan.slippage - plan.entry - plan.slippage))


def test_t2_exit_and_structure_trailing_only_ratchets_forward():
    pos, plan = pos_long()
    R.on_bar(pos, bar(plan.t1 + 1, plan.entry + 5, plan.t1), CFG, t("10:35"))
    R.on_bar(pos, bar(plan.t1 + 8, plan.t1 - 2, plan.t1 + 4), CFG, t("10:40"), trail_stop=plan.entry + 10)
    assert pos.sl == plan.entry + 10
    R.on_bar(pos, bar(plan.t1 + 9, plan.t1 - 1, plan.t1 + 5), CFG, t("10:45"), trail_stop=plan.entry + 3)       # पाठी सरकत नाही
    assert pos.sl == plan.entry + 10
    R.on_bar(pos, bar(plan.t2 + 1, plan.t1, plan.t2), CFG, t("10:50"))
    assert pos.closed and pos.exit_reason == "T2" and pos.r_multiple > 0.5


def test_time_stop_failed_breakout_and_eod():
    pos, plan = pos_long()
    for i in range(CFG.time_stop_bars):
        R.on_bar(pos, bar(plan.entry + 2, plan.entry - 3, plan.entry + 1), CFG, NOW + pd.Timedelta(minutes=5 * (i + 1)))
    assert pos.closed and pos.exit_reason == "TIME_STOP"
    pos2, plan2 = pos_long()
    R.on_bar(pos2, bar(plan2.entry + 1, plan2.entry - 5, 24308.0), CFG, t("10:35"))              # level (24310) च्या आत close
    R.on_bar(pos2, bar(plan2.entry, plan2.entry - 6, 24307.0), CFG, t("10:40"))
    assert pos2.closed and pos2.exit_reason == "FAILED_BREAKOUT"
    pos3, plan3 = pos_long(kind="PULLBACK_END", level=None)
    R.on_bar(pos3, bar(plan3.entry + 3, plan3.entry - 3, plan3.entry + 1), CFG, t("15:15"))
    assert pos3.closed and pos3.exit_reason == "EOD"


def test_short_mirror_and_slippage_by_symbol():
    plan = R.plan_trade(cand("SHORT", entry=24300.0, sl=24320.0), ctx_of(), CFG, rr=10.0, adr=200.0, symbol="BANKNIFTY")
    assert plan.slippage == 3.0
    pos = R.open_position(plan, "PULLBACK_END")
    R.on_bar(pos, bar(plan.entry - 1, plan.t1 - 1, plan.t1), CFG, t("10:35"))
    assert pos.t1_done and pos.sl == plan.entry
    R.on_bar(pos, bar(plan.entry + 1, plan.t1, plan.entry), CFG, t("10:40"))
    assert pos.closed and pos.exit_reason == "BE"
    assert R.plan_trade(cand(), ctx_of(), CFG, rr=10.0, adr=200.0).slippage == 1.0
    assert R.on_bar(pos, bar(1, 0, 0), CFG, t("10:45")) == []                                     # बंद position वर काहीच नाही


# ---- scoring --------------------------------------------------------------------------------------------------------------------------------
def scored(c=None, ctx=None, validation=None, plan=None):
    c = c or cand(zone=A_ZONE)
    ctx = ctx or ctx_of()
    bias = resolve_bias(ctx, CFG)
    plan = plan or R.plan_trade(c, ctx, CFG, rr=10.0, adr=200.0)
    validation = validation or V.validate_breakout(c.trigger, c.direction, c.trigger["level"], 10.0, CFG, vol_median=1000.0, room_r=3.0)
    return S.score_candidate(c, validation, plan, bias, ctx, CFG), bias


def test_score_components_sum_and_max_100():
    ctx = ctx_of(extra={"4h": {"pullbacks_since_break": 0}})
    sc, _ = scored(ctx=ctx)
    assert set(sc.components) == {"structure", "location", "setup", "trigger", "rr"}
    assert sc.total == pytest.approx(sum(sc.components.values()), abs=0.01) and sc.total <= 100
    assert sc.components["setup"] == 14.0 and sc.components["trigger"] == 15.0 and sc.components["rr"] == 10.0


def test_structure_context_rules():
    pb = ctx_of({"1d": "UPTREND", "4h": "UPTREND_PULLBACK", "1h": "UPTREND"}, extra={"4h": {"pullbacks_since_break": 1}})
    sc, _ = scored(ctx=pb)
    assert sc.detail["structure"] == {"aligned": 15.0, "fresh_bos_pullback": 10.0, "not_weak_range": 5.0}
    second = ctx_of({"1d": "UPTREND", "4h": "UPTREND_PULLBACK", "1h": "UPTREND"}, extra={"4h": {"pullbacks_since_break": 3}})
    assert scored(ctx=second)[0].detail["structure"]["fresh_bos_pullback"] == 5.0
    early = ctx_of({"1d": "DOWNTREND_WEAK", "4h": "UPTREND", "1h": "UPTREND"})
    d = scored(ctx=early)[0].detail["structure"]
    assert d["aligned"] == 12.5 and d["daily_early_reversal"] is True                           # Daily aligned अर्धे (5 → 2.5)
    weak_1h = ctx_of({"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND_WEAK"})
    assert scored(ctx=weak_1h)[0].detail["structure"]["not_weak_range"] == 0.0


def test_location_score_grade_freshness_confluence_overlap():
    pts, d = S.location_score(cand(zone=A_ZONE))
    assert pts == 10 + 6 + 5 and d["overlap"] == 0
    flip = {**A_ZONE, "status": "BROKEN", "quality_grade": "C", "freshness": "TESTED_2+", "mtf_count": 2}
    assert S.location_score(cand(zone=flip))[0] == 4 + 2 + 3 + 4
    assert S.location_score(cand(zone=None))[0] == 0.0
    assert S.location_score(cand(zone=A_ZONE, meta={"gap_overlap": True}))[0] == 25.0


def test_rr_score_linear_and_open_room():
    assert S.rr_score(1.5, CFG) == 0 and S.rr_score(3.0, CFG) == 10 and S.rr_score(4.5, CFG) == 10 and S.rr_score(2.25, CFG) == 5 and S.rr_score(None, CFG) == 10


def test_decision_thresholds_sizes_and_setup_override():
    sc, bias = scored(c=cand(zone=A_ZONE, quality=100.0), ctx=ctx_of(extra={"4h": {"pullbacks_since_break": 0}}))
    assert sc.decision == "FULL" and sc.size_factor == 1.0 and sc.confidence == pytest.approx(sc.total / 100)
    low, _ = scored(c=cand(zone=None, quality=10.0))
    assert low.decision == "NO_TRADE" and low.size_factor == 0.0 and low.notes
    c = cand(zone=A_ZONE, quality=60.0)
    mid = scored(c=c)[0]
    cfg_strict = EngineConfig(setup_thresholds={"D7": {"full": 99, "half": 40}})
    assert S.thresholds("D7", cfg_strict) == (99.0, 40.0) and S.thresholds("D1", cfg_strict) == (75.0, 60.0)
    assert mid.decision in ("FULL", "HALF")
    half_cfg = EngineConfig(score_full=200.0, score_half=50.0)
    ctx = ctx_of()
    bias = resolve_bias(ctx, half_cfg)
    v = V.validate_breakout(c.trigger, c.direction, c.trigger["level"], 10.0, half_cfg, vol_median=1000.0, room_r=3.0)
    sc2 = S.score_candidate(c, v, R.plan_trade(c, ctx, half_cfg, 10.0, 200.0), bias, ctx, half_cfg)
    assert sc2.decision == "HALF" and sc2.size_factor == 0.5


# ---- selector -------------------------------------------------------------------------------------------------------------------------------
def passing(setup="D7", direction="LONG", entry=24316.0, total=80.0, quality=70.0, ctx=None):
    ctx = ctx or ctx_of()
    c = cand(direction=direction, setup=setup, entry=entry, sl=entry - 20 if direction == "LONG" else entry + 20, quality=quality)
    plan = R.plan_trade(c, ctx, CFG, 10.0, 200.0)
    sc = S.Score(total=total, components={}, decision="FULL", size_factor=1.0)
    return Decision(candidate=c, bias=resolve_bias(ctx, CFG), plan=plan, score=sc, status="PASS", size_factor=1.0)


@pytest.mark.parametrize("day,now,reason", [
    (SEL.DayState(open_positions=1), "10:30", "POSITION_OPEN"),
    (SEL.DayState(trades_today=2), "10:30", "MAX_TRADES"),
    (SEL.DayState(sl_today=2), "10:30", "MAX_SL_HIT"),
    (SEL.DayState(last_sl_time=pd.Timestamp("2025-01-08 10:10"), sl_today=1), "10:30", "SL_COOLDOWN"),
    (SEL.DayState(htf_weak=True), "10:30", "HTF_WEAK"),
    (SEL.DayState(), "14:45", "TIME_LATE"),
])
def test_day_limits_block_all_new_entries(day, now, reason):
    sel = SEL.select([passing()], t(now), day, CFG)
    assert sel.chosen is None and sel.day_block == reason and sel.dropped[0][1] == reason


def test_cooldown_expires_after_30_minutes_and_late_entry_boundary():
    day = SEL.DayState(last_sl_time=pd.Timestamp("2025-01-08 10:00"), sl_today=1)
    assert SEL.select([passing()], t("10:31"), day, CFG).chosen is not None
    assert SEL.select([passing()], t("14:44"), SEL.DayState(), CFG).chosen is not None


def test_opening_window_allows_only_gap_setups():
    sel = SEL.select([passing("D7"), passing("D1", entry=24500.0)], t("09:20"), SEL.DayState(), CFG)
    assert sel.chosen.candidate.setup_id == "D1" and ("OPENING_WINDOW" in [r for _, r in sel.dropped])


def test_dedupe_confluence_bonus_and_resize():
    a, b = passing("D7", total=72.0), passing("D8", entry=24318.0, total=70.0)
    a.score.decision, a.score.size_factor = "HALF", 0.5
    sel = SEL.select([b, a], t("10:30"), SEL.DayState(), CFG)
    assert sel.chosen is a and a.score.total == 77.0 and a.score.decision == "FULL" and a.score.size_factor == 1.0
    assert (b, "DEDUPED") in sel.dropped and any("Confluence" in n for n in a.score.notes)
    capped = SEL.select([passing("D7", total=98.0), passing("D8", total=90.0)], t("10:30"), SEL.DayState(), CFG)
    assert capped.chosen.score.total == 100.0


def test_opposite_directions_both_dropped_and_highest_score_wins_otherwise():
    both = SEL.select([passing("D7", "LONG", 24316.0), passing("D8", "SHORT", 24100.0)], t("10:30"), SEL.DayState(), CFG)
    assert both.chosen is None and {r for _, r in both.dropped} == {"OPPOSITE_SIGNALS"}
    far = SEL.select([passing("D7", entry=24316.0, total=78.0), passing("D6", entry=24500.0, total=85.0)], t("10:30"), SEL.DayState(), CFG)
    assert far.chosen.candidate.setup_id == "D6" and ("LOWER_SCORE" in [r for _, r in far.dropped])
    assert SEL.select([], t("10:30"), SEL.DayState(), CFG).chosen is None


# ---- engine + commentary ------------------------------------------------------------------------------------------------------------------------
def test_engine_takes_a_good_aligned_candidate_with_marathi_commentary():
    ctx = ctx_of(extra={"4h": {"pullbacks_since_break": 1, "protected": 24100.0}})
    res = evaluate([cand(zone=A_ZONE, quality=90.0)], ctx, CFG, now=NOW)
    d = res.decisions[0]
    assert d.status == "TAKEN" and res.selection.chosen is d and d.size_factor in (0.5, 1.0) and d.confidence > 0.6
    assert "Score" in d.commentary and "entry" in d.commentary and "UPTREND" in d.commentary
    assert cm.summary(res).startswith("Bias: LONG_ONLY")


def test_engine_gate_rejection_pullback_commentary_and_each_failure_stage():
    levels = [{"kind": "DEMAND", "tf": "1h", "low": 24210.0, "high": 24250.0, "freshness": "FRESH", "quality_grade": "A", "status": "ACTIVE", "reject_reason": None,
               "level_id": "d1", "source": ""}]
    ctx = ctx_of(levels=levels, price=24300.0)
    bearish = cand("SHORT", "D7", "BREAKOUT", entry=24300.0, sl=24320.0, trigger={**GOOD, "open": 24310.0, "high": 24312.0, "low": 24292.0, "close": 24294.0, "level": 24300.0})
    res = evaluate([bearish], ctx, CFG, now=NOW)
    d = res.decisions[0]
    assert d.status == "REJECTED_GATE" and d.gate.pullback_in_progress and "pullback" in d.commentary and "Watch zone" in d.commentary
    # risk stage
    risk = evaluate([cand(sl=24150.0)], ctx_of(), CFG, now=NOW).decisions[0]
    assert risk.status == "REJECTED_RISK" and risk.reasons == ["Risk: SL_TOO_WIDE"]
    # validation stage (wick-only)
    wick = evaluate([cand(trigger={**GOOD, "close": 24305.0})], ctx_of(), CFG, now=NOW).decisions[0]
    assert wick.status == "REJECTED_VALIDATION"
    # score stage
    weak = evaluate([cand(quality=0.0, zone=None)], ctx_of(), CFG, now=NOW).decisions[0]
    assert weak.status == "REJECTED_SCORE" and "Score" in weak.commentary
    # selector stage (दिवसाची मर्यादा)
    blocked = evaluate([cand(zone=A_ZONE, quality=90.0)], ctx_of(), CFG, now=NOW, day=SEL.DayState(trades_today=2))
    assert blocked.decisions[0].status == "DROPPED" and blocked.selection.day_block == "MAX_TRADES"


def test_engine_with_no_candidates_and_no_trade_bias():
    res = evaluate([], ctx_of({"1d": "UPTREND", "4h": "UPTREND_WEAK", "1h": "UPTREND"}), CFG, now=NOW)
    assert res.selection.chosen is None and res.bias.label == "NO_TRADE" and "NO_TRADE" in cm.summary(res)
