"""KB K4 / G4 (Abhi's final flip rule, Z-1 final answers) — decision3 BROKEN / FLIPPED / DEAD and the in-zone study, mirrored.

  • a zone FLIPS only when price goes beyond it AND trades past the far-side swing (no swing beyond ⇒ the first CONFIRMED swing after the
    break, Z-1a); beyond it without that swing ⇒ BROKEN, not a trade location; a FLIPPED zone broken again past its far swing ⇒ DEAD;
  • G4 approach (a) shape / (b) volume = CONTEXT only (Z-1d): reported, never a no_trade / wait; the in-zone study (⑥ a2 + c0 + c1, RSI
    divergence as evidence) decides, end to end through V22.decide();
  • volume = per-bar FUT volume ÷ its time-of-day slot median (20 sessions); FUT missing ⇒ data problem: no entry (+ one Telegram line per
    symbol per day for NIFTY / BANKNIFTY) — no grade-B trade without volume (Z-1c);
  • no look-ahead: states and G4 facts at bar t equal those computed on data cut at t.
Real-day checks (12 Oct golden bear call, 13 Oct no bear call) need the private trade-data export and skip cleanly without it.
"""
import os

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import method as M
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

UP, DOWN = M.UP, M.DOWN
S = S3.load()
MID = 125.0                                                               # mirror: p ⇒ 2·MID − p

# Resistance zone R (D2 H 118, bar 20) between the far-side swing high 130 (bar 6) and the impulse origin 108 (bar 26).
BASE = [(0, 100), (6, 130), (14, 104), (20, 118), (26, 108)]
PIV2 = [("H", 130, 6, 8), ("L", 104, 14, 16), ("H", 118, 20, 22), ("L", 108, 26, 28)]
PATHS = {
    # impulse 108 ⇒ 134 (past the far swing 130 ⇒ FLIPPED), then zigzag 134 ⇒ 124 ⇒ 129 ⇒ into the zone, then a bullish commitment
    "flip_corrective": ([(40, 134), (46, 124), (50, 129), (58, 118.4), (59, 123)], [("L", 124, 46, 48), ("H", 129, 50, 52)]),
    # same flip, but the return is a 5-wave impulse 134 ⇒ 127 ⇒ 131 ⇒ 121 ⇒ 124 ⇒ zone
    "flip_impulsive": ([(40, 134), (44, 127), (46, 131), (51, 121), (53, 124), (58, 118.4), (59, 123)],
                       [("L", 127, 44, 46), ("H", 131, 46, 48), ("L", 121, 51, 53), ("H", 124, 53, 55)]),
    # break (3 closes above the zone) but only to 126 < 130 ⇒ BROKEN, then a retest of the zone
    "broken_only": ([(36, 126), (42, 121), (45, 124), (52, 118.4), (53, 123)], [("L", 121, 42, 44), ("H", 124, 45, 47)]),
    # the corrective flip, then the flipped support breaks again and price trades below the swing low 108 ⇒ DEAD (no second flip)
    "flip_then_dead": ([(40, 134), (46, 124), (50, 129), (58, 118.4), (59, 123), (63, 128), (80, 100)],
                       [("L", 124, 46, 48), ("H", 129, 50, 52)]),
}


def _build(name, mirror=False, vol_pullback=600.0, vol_impulse=1000.0, vol_start=1200.0):
    """15M bars + D2 / D1 pivots + per-bar FUT volume for one scenario. Volume: impulse bars `vol_impulse`, pullback `vol_pullback`
    (its first two bars `vol_start` — the pullback may start on rising volume), the last (commitment) bar 2× impulse."""
    pts, piv1 = PATHS[name]
    anchors = BASE + pts
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    closes = [f(c) for c in closes]
    zone_end = pts[4][0] - 1 if name == "flip_then_dead" else pts[-2][0]  # pullback end bar (inside the zone)
    lows = {zone_end: f(117.6)} if not mirror else {}
    highs = {zone_end: f(117.6)} if mirror else {}
    m = m15_from(closes, wick=0.3, lows=lows, highs=highs)
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    p2 = [P(sw(k), f(p), b, c) for k, p, b, c in PIV2]
    p1 = [P(sw(k), f(p), b, c) for k, p, b, c in piv1]
    ext = pts[0][0]
    n = len(m)
    vol = np.full(n, 800.0)
    vol[27:ext + 1] = vol_impulse
    vol[ext + 1:n - 1] = vol_pullback
    vol[ext + 1:ext + 3] = vol_start
    vol[n - 1] = 2 * vol_impulse
    return m, p2, p1, vol


# These synthetic fixtures build their breaks from closes beyond the band and give no finer swings, so they test the flip / dead /
# far-swing mechanics under the legacy break rule; the method's structural break (a close beyond + a swing formed beyond) has its own
# tests (test_structural_break_*).
LEGACY_BREAK = {"break_rule": "closes"}


def _levels(m, p2, p1, s=None):
    return LV.Levels(res_of(m, p2, p1), s={**LEGACY_BREAK, **(s or {})})


def _zone(lv, mirror):
    return [L for L in lv.L if abs(L.anchor - (2 * MID - 118 if mirror else 118)) < 1e-6][0]


def _v(m, p2, p1, vol=None, s=None):
    """V22 without the Daily / K machinery: only what the G4 context / in-zone read need (levels, pivots, settings, volume)."""
    res = res_of(m, p2, p1)
    V = E3.V22.__new__(E3.V22)
    s = {**LEGACY_BREAK, **(s or {})}
    V.s = S3.load(s)
    V.res = res
    V.levels = LV.Levels(res, s=s)
    if vol is not None:
        V.levels.A["volume"] = np.asarray(vol, float)                         # treated as already slot-normalised here
    V._legs_arr = None
    return V


def _row(lv, L, t):
    return [x for x in lv.snapshot(t) if x["id"] == L.id][0]


# ------------------------------------------------------------------------------------------------ state machine
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_broken_not_flipped_retest_is_not_a_trade_location(mirror):
    m, p2, p1, _ = _build("broken_only", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    t = len(m) - 2                                                         # the retest bar (inside the zone)
    lo, hi = Z.band_at(t)
    assert m["low"].iloc[t] <= hi and m["high"].iloc[t] >= lo
    x = _row(lv, Z, t)
    assert x["state"] == FL.BROKEN and x["flipped_at"] is None and x["broken_at"] is not None
    assert x["role"] == (LV.SUP if mirror else LV.RES)                     # old role kept (Abhi: until the swing, the zone keeps its role)
    assert x["far_swing"]["price"] == pytest.approx(2 * MID - 130 if mirror else 130) and x["far_swing"]["source"] == "before_break"
    trend = "DOWN" if mirror else "UP"
    assert all(a["id"] != Z.id for a in lv.active(t, trend))               # ⇒ no entry at a BROKEN zone
    assert all(a["id"] != Z.id for a in lv.active(t, "UP" if mirror else "DOWN"))
    old = _levels(m, p2, p1, {"level_flip_rule": "acceptance"})            # old spec §5.4: acceptance flipped it ⇒ it WAS a location
    assert any(a["id"] == _zone(old, mirror).id for a in old.active(t, trend))


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flip_only_when_price_trades_past_the_far_side_swing(mirror):
    m, p2, p1, _ = _build("flip_corrective", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    kinds = [(b, k) for b, k, _ in Z.events if k in ("broken", "flip", "reclaim", "dead")]
    t_brk = next(b for b, k in kinds if k == "broken")
    t_flip = next(b for b, k in kinds if k == "flip")
    assert t_brk < t_flip and Z.dead_bar is None
    far = 2 * MID - 130 if mirror else 130
    ext = (m["low"] if mirror else m["high"]).to_numpy()
    assert all((ext[i] > far) == mirror for i in range(t_brk, t_flip))     # not past the swing before the flip bar
    assert (ext[t_flip] < far) if mirror else (ext[t_flip] > far)          # traded past it on the flip bar (no candle condition)
    assert _row(lv, Z, t_flip - 1)["state"] == FL.BROKEN
    x = _row(lv, Z, len(m) - 2)
    assert x["state"] == FL.FLIPPED and x["role"] == (LV.RES if mirror else LV.SUP)
    assert x["broken_at"] == t_brk and x["flipped_at"] == t_flip and x["far_swing"]["price"] == pytest.approx(far)
    assert x["far_swing"]["bar"] == 6 and x["broken_ts"] and x["flipped_ts"]
    assert any(a["id"] == Z.id for a in lv.active(len(m) - 2, "DOWN" if mirror else "UP"))   # FLIPPED ⇒ a location (in-zone study decides)


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_first_swing_after_the_break_flips_on_its_confirmation_when_no_swing_lies_beyond(mirror):
    """Abhi Z-1s (the corrected Z-1a wording): the zone is the top of the known structure (no swing above) ⇒ the far-side swing is the
    first swing FORMED after the break, and reaching it = that swing being CONFIRMED — it does not have to be broken. The zone flips on
    the confirmation bar; the move back from that swing into the zone is the pullback."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    anchors = [(0, 100), (8, 118), (16, 106), (26, 126), (31, 121), (38, 125), (41, 118.2)]
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(106), 16, 18), P(sw("H"), f(126), 26, 29)]
    lv = _levels(m, p2, [])
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    t_brk = next(b for b, k, _ in Z.events if k == "broken")
    assert _row(lv, Z, 28)["state"] == FL.BROKEN and _row(lv, Z, 28)["far_swing"] is None          # swing 126 not confirmed yet
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    assert t_brk < t_flip == 29                                            # flipped AT the confirmation bar of the post-break swing
    ext = (m["low"] if mirror else m["high"]).to_numpy()
    assert not any(((ext[i] < f(126) - 0.3) if mirror else (ext[i] > 126.3)) for i in range(27, len(m)))   # never traded through
    x = _row(lv, Z, 30)
    assert x["state"] == FL.FLIPPED and x["far_swing"]["price"] == pytest.approx(f(126)) and x["flipped_at"] == 29
    assert x["far_swing"]["source"] == "first_confirmed_after_break" and x["far_swing"]["bar"] >= x["exc_start"]
    assert "confirmed" in [d for b, k, d in Z.events if k == "flip"][0]
    assert Z.state_at(len(m) - 1) == FL.FLIPPED and Z.role_at(len(m) - 1) == (LV.RES if mirror else LV.SUP)
    t = len(m) - 1                                                         # the pullback back into the zone ⇒ a trade location
    lo, hi = Z.band_at(t)
    assert m["low"].iloc[t] <= hi and m["high"].iloc[t] >= lo
    assert any(a["id"] == Z.id for a in lv.active(t, "DOWN" if mirror else "UP"))


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flipped_zone_broken_again_with_no_swing_beyond_dies_when_the_first_swing_after_that_break_confirms(mirror):
    """Abhi Z-1s, the DEAD rule: a FLIPPED zone broken again, with no swing beyond it on the new break side ⇒ DEAD as soon as the first
    swing formed after that break is CONFIRMED (not traded through) — never a second flip."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    anchors = [(0, 100), (8, 118), (16, 110), (26, 126), (31, 121), (38, 125), (46, 112), (50, 116)]
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("H"), f(126), 26, 29), P(sw("L"), f(112), 46, 48)]   # no swing low below the zone before
    lv = _levels(m, p2, [])
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    kinds = [(b, k) for b, k, _ in Z.events if k in ("broken", "flip", "dead")]
    assert [k for _, k in kinds] == ["broken", "flip", "broken", "dead"]
    assert dict((k, b) for b, k in kinds)["flip"] == 29 and Z.dead_bar == 48     # flip and death both at a swing's confirmation bar
    ext = (m["high"] if mirror else m["low"]).to_numpy()
    assert not any(((ext[i] > f(112) + 0.3) if mirror else (ext[i] < 112 - 0.3)) for i in range(47, len(m)))   # never traded through
    assert "confirmed" in [d for b, k, d in Z.events if k == "dead"][0] and "no second flip" in [d for b, k, d in Z.events if k == "dead"][0]
    assert Z.state_at(47) == FL.BROKEN and Z.state_at(48) == FL.DEAD and Z.count("flip", len(m) - 1) == 1
    assert all(x["id"] != Z.id for x in lv.snapshot(len(m) - 1))


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_a_prior_swing_beyond_the_zone_must_still_be_passed_not_just_confirmed(mirror):
    """Abhi Z-1s: where a swing beyond the zone existed before the break, the rule is unchanged — price must trade past it. A swing that
    forms after the break and confirms does NOT flip the zone while the prior swing stands (BROKEN, not a trade location)."""
    m, p2, p1, _ = _build("broken_only", mirror)
    extra = P(("L" if mirror else "H"), 2 * MID - 126 if mirror else 126, 36, 38)   # a post-break swing that confirms (bar 38)
    lv = _levels(m, p2 + [extra], p1)
    Z = _zone(lv, mirror)
    t = len(m) - 2
    x = _row(lv, Z, t)
    assert x["state"] == FL.BROKEN and Z.count("flip", t) == 0
    assert x["far_swing"]["source"] == "before_break" and x["far_swing"]["price"] == pytest.approx(2 * MID - 130 if mirror else 130)
    assert all(a["id"] != Z.id for a in lv.active(t, "DOWN" if mirror else "UP"))


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flipped_zone_broken_again_past_its_far_swing_is_dead_no_second_flip(mirror):
    """Abhi Z-1f: once flipped the old role ends; broken again (acceptance) ⇒ BROKEN; past ITS far-side swing ⇒ DEAD, logged."""
    m, p2, p1, _ = _build("flip_then_dead", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    kinds = [k for _, k, _ in Z.events if k in ("broken", "flip", "dead")]
    assert kinds == ["broken", "flip", "broken", "dead"]
    t_dead = Z.dead_bar
    far = 2 * MID - 108 if mirror else 108                                 # the D2 swing beyond the band on the new break side
    ext = (m["high"] if mirror else m["low"]).to_numpy()
    assert (ext[t_dead] > far) if mirror else (ext[t_dead] < far)
    assert "no second flip" in [d for b, k, d in Z.events if k == "dead"][0]
    assert Z.state_at(t_dead - 1) == FL.BROKEN and Z.state_at(t_dead) == FL.DEAD
    assert all(x["id"] != Z.id for x in lv.snapshot(len(m) - 1))           # dead ⇒ out of the snapshot / never a location
    assert Z.count("flip", len(m) - 1) == 1


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_sweep_keeps_the_old_role_and_reclaim_returns_a_broken_zone_logged_as_sweep(mirror):
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    closes = [f(c) for c in [100, 110, 120, 130, 120, 110, 104, 108, 112, 116, 118, 116, 112, 110, 114, 117, 119, 119.5, 116, 113, 110]]
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    p2 = [P(sw("H"), f(130), 3, 5), P(sw("L"), f(104), 6, 8), P(sw("H"), f(118), 10, 12)]
    m = m15_from(closes, wick=0.3)
    lv = _levels(m, p2, [])
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    t = len(m) - 1
    assert Z.count("sweep", t) >= 1 and Z.count("broken", t) == 0 and Z.state_at(t) in (FL.ACTIVE, FL.TESTED)
    assert Z.role_at(t) == (LV.SUP if mirror else LV.RES)
    closes2 = [f(c) for c in [100, 110, 120, 130, 120, 110, 104, 108, 112, 116, 118, 116, 112, 110, 114, 117, 119, 120, 121, 122,
                              119, 116, 115, 114, 113]]
    lv2 = _levels(m15_from(closes2, wick=0.3), p2, [])
    Z2 = [L for L in lv2.L if abs(L.anchor - f(118)) < 1e-6][0]
    ev = [k for _, k, _ in Z2.events if k in ("broken", "reclaim", "flip", "sweep")]
    assert ev[-3:] == ["broken", "reclaim", "sweep"] and Z2.state_at(len(closes2) - 1) in (FL.ACTIVE, FL.TESTED)
    assert _row(lv2, Z2, len(closes2) - 1)["sweeps"] >= 1                  # ★ / trap_sweep evidence kept


def test_a_dead_level_never_absorbs_a_new_swing():
    """Review: a new swing overlapping a DEAD level is born as its own level (DEAD levels are out of the merge and the snapshot). A swing
    in the area of a BROKEN level still merges into it (the same zone — Abhi's 12 Oct zone is such a merge; OPEN_QUESTIONS)."""
    m, p2, p1, _ = _build("flip_then_dead")
    lv0 = _levels(m, p2, p1)
    Z = _zone(lv0, False)
    td = Z.dead_bar
    lo, hi = Z.band_at(td)
    extra = P("L", (lo + hi) / 2, td + 1, td + 2)
    lv = _levels(m, p2 + [extra], p1)
    Zd = _zone(lv, False)
    born = [L for L in lv.L if L.id != Zd.id and L.born_bar == td + 2 and abs(L.anchor - (lo + hi) / 2) < 1e-6]
    assert Zd.dead_bar == td and born and all(b != "a:D2" or tm < td for tm, b in Zd.merged_from)
    assert any(x["id"] == born[0].id for x in lv.snapshot(td + 2)) and all(x["id"] != Zd.id for x in lv.snapshot(td + 2))


def test_nine_oct_case_flips_at_the_far_swing_not_at_acceptance():
    """The 9 Oct blind-spot fixture (tests/test_decision3_level_death_side.py): support ≈ 96.5 broken by closes, then price trades below
    the swing low 90 ⇒ FLIPPED to supply there (not at acceptance), alive for the retest from below."""
    from tests.test_decision3_level_death_side import CLOSES, PIV, T_BREAK
    m = m15_from(CLOSES, lows={4: 90.0})
    lv = LV.Levels(res_of(m, [P(*x) for x in PIV]), s=LEGACY_BREAK)          # fixture breaks by closes (legacy rule)
    Z = [x for x in lv.L if abs(x.anchor - 96.5) < 1e-6][0]
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    t_brk = next(b for b, k, _ in Z.events if k == "broken")
    assert t_brk < t_flip == T_BREAK and m["low"].iloc[t_flip] < 90.0 <= m["low"].iloc[t_flip - 1]
    assert Z.dead_bar is None and Z.state_at(len(m) - 1) == FL.FLIPPED and Z.role_at(len(m) - 1) == LV.RES


def test_settings_are_registered_and_cap_b_option_is_gone():
    assert S3.DEFAULTS["level_flip_rule"] == "far_swing" and S3.DEFAULTS["c0_volume_required"] is True
    for k in ("level_flip_rule", "flip_pullback_vol_ratio", "flip_vol_min_coverage", "flip_pullback_inner_degree", "vol_slot_sessions",
              "vol_slot_min_sessions", "c0_volume_required"):
        assert k in S3.REGISTER and k in S3.DEFAULTS
    assert "flip_volume_na" not in S3.DEFAULTS and S3.DEFAULTS["vol_slot_sessions"] == 20
    m, p2, p1, _ = _build("broken_only")
    with pytest.raises(ValueError):
        _levels(m, p2, p1, {"level_flip_rule": "strong_move"})


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_daily_trend_side_rule_keeps_a_flipped_zone_out_of_the_opposite_trade(mirror):
    """Abhi (26a0bfe): while the Daily trend is DOWN, a zone flipped to support inside the up-correction is NOT a bull location (no S4
    exception) — `Levels.active` (② / H1) only offers resistance in a DOWN trend; mirrored (UP trend ⇒ a flipped resistance is no bear
    location)."""
    m, p2, p1, _ = _build("flip_corrective", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    t = len(m) - 2
    x = _row(lv, Z, t)
    assert x["state"] == FL.FLIPPED and x["role"] == (LV.RES if mirror else LV.SUP)
    against = "UP" if mirror else "DOWN"
    assert all(a["id"] != Z.id for a in lv.active(t, against))
    assert any(a["id"] == Z.id for a in lv.active(t, "DOWN" if mirror else "UP"))


# ------------------------------------------------------------------------------------------------ G4 = context only
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_approach_shape_and_volume_are_reported_as_context(mirror):
    for name, vp, a_kind, b_low in (("flip_corrective", 600.0, "corrective", True), ("flip_impulsive", 1500.0, "impulse", False)):
        m, p2, p1, vol = _build(name, mirror, vol_pullback=vp, vol_start=vp if vp > 1000 else 1200.0)
        V = _v(m, p2, p1, vol)
        t = len(m) - 1
        lvl = _row(V.levels, _zone(V.levels, mirror), t)
        g = V.flip_context(t, lvl)
        assert g["context_only"] and g["a_read"]["kind"] == a_kind and g["b"] is b_low
        assert g["impulse"]["to_bar"] == g["pullback"]["from_bar"] == 40 and "not a gate" in g["why"]
        assert "decision" not in g and "ok" not in g


@pytest.fixture(scope="module")
def abc():
    """tests/test_decision3_method._abc_m15 (downtrend, ABC pullbacks) under the DEFAULT flip rule: its supply retests at bars 739–743
    are at a FLIPPED zone (end-to-end G4 path through V22.decide). Volume-less fixture ⇒ c0_volume_required off except where tested."""
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    s = {"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_dominance": False}
    return m15, s, E3.V22(m15, s={**s, "c0_volume_required": False}), E3.V22(m15, s=s)


def _flipped_rows(V, bars=range(735, 746)):
    return [r for r in (V.decide(t) for t in bars) if (r.get("level") or {}).get("state") == FL.FLIPPED
            and (r["checklist"].get("③") or [None])[0]]


def test_end_to_end_flipped_zone_in_zone_study_decides_and_context_never_gates(abc, monkeypatch):
    m15, s, V, _ = abc
    rows = _flipped_rows(V)
    assert rows                                                            # the G4 path is really exercised through decide()
    for r in rows:
        assert r["checklist"]["G4"][0] is None and "not a gate" in r["checklist"]["G4"][1]   # context, never a gate
        assert "G4" not in str(r.get("why")) and r["flip"]["state"] == FL.FLIPPED and r["flip"]["far_swing"]   # outcome: ⑥ / conviction
        z = r["zone_read"]
        assert z and z["candles"] and z["summary"]["bars"] == len(z["candles"]) and "rsi_divergence" in z["summary"]
        assert r["flip_retest"]["context_only"]
    seen = {r["bar"]: (r["decision"], r["checklist"]["⑥"]) for r in rows}
    worst = {"context_only": True, "a": False, "b": False, "a_why": "forced", "b_why": "forced", "why": "G4 context (not a gate): forced",
             "pullback": None, "impulse": None, "a_read": None, "b_read": None}
    monkeypatch.setattr(FL, "approach_context", lambda *a, **k: dict(worst))
    V2 = E3.V22(m15, s={**s, "c0_volume_required": False})
    for r in _flipped_rows(V2):                                            # impulsive + high-volume approach ⇒ same decision
        assert (r["decision"], r["checklist"]["⑥"]) == seen[r["bar"]]


def test_end_to_end_fut_volume_missing_is_a_data_problem_not_a_grade_b_entry(abc):
    _, _, V_off, V = abc
    hit = [r for r in _flipped_rows(V) if "data problem" in str(r["checklist"]["⑥"][1])]
    assert hit and all(r["decision"] == "wait" and r["checklist"]["⑥"][0] is False for r in hit)
    assert all("FUT volume missing" in r["checklist"]["⑥"][1] for r in hit)
    assert not [r for r in V.run(range(700, len(V.m15))) if r["decision"] == "setup" and (r["commit"] or {}).get("vol_na")]


def test_engine3_nifty_banknifty_fut_missing_raises_data_error_and_one_telegram_line_per_day(tmp_path, monkeypatch):
    import engine3_live as L
    import engine_signal as ES
    from scripts import engine_signal_run as ESR
    from tests.test_one_bot import Feed
    now = pd.Timestamp("2030-03-25 15:31")
    for sym in L.FUT_REQUIRED:
        with pytest.raises(L.FutVolumeMissing, match="data problem: FUT volume missing"):
            L.build_inputs(Feed(fut=False), sym, now)
    m15, _, _, fut, note = L.build_inputs(Feed(fut=False), "SENSEX", now)    # not in FUT_REQUIRED ⇒ V22 c0 data problem instead
    assert fut is None and "data problem" in note
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []

    def run(sym, tok):
        raise L.FutVolumeMissing(f"{L.DATA_PROBLEM_FUT} (test)")
    for k in range(3):                                                     # three cycles, same day ⇒ one line per symbol
        ESR.main(["--symbols", "NIFTY,BANKNIFTY"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
                 alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-07 10:16") + pd.Timedelta(minutes=15 * k))
    assert len(sent) == 2 and all("data problem: FUT volume missing" in x for x in sent)
    ESR.main(["--symbols", "NIFTY"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
             alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-08 10:16"))
    assert len(sent) == 3                                                  # next day ⇒ again once
    assert ES.alert_data_problem("NIFTY", "x", send=sent.append, state_path=str(tmp_path / "a.json"),
                                 now=pd.Timestamp("2030-01-08 11:00")) is False


# ------------------------------------------------------------------------------------------------ volume: per bar, time-of-day normalised
def test_slot_normalised_volume_0915_bar_is_not_high_just_because_of_its_slot():
    days = pd.bdate_range("2030-01-01", periods=25)
    slots = [pd.Timedelta(hours=9, minutes=15), pd.Timedelta(hours=9, minutes=30), pd.Timedelta(hours=12)]
    ts = [d + x for d in days for x in slots]
    vol = np.array([3000.0 if (i % 3) == 0 else 1000.0 for i in range(len(ts))])
    vol[-1] = 2000.0                                                       # last day 12:00 = 2× its slot
    rel, cnt = M.slot_rel_volume(ts, vol, sessions=20, min_sessions=10)
    assert np.isnan(rel[: 3 * 10]).all() and cnt[3 * 10] == 10           # < 10 earlier sessions ⇒ NA
    assert rel[-3] == pytest.approx(1.0) and rel[-2] == pytest.approx(1.0) and rel[-1] == pytest.approx(2.0)
    assert cnt[-1] == 20                                                   # only the previous 20 sessions
    vol2 = vol.copy()
    vol2[-1] = 99999.0                                                     # today's own bar never enters its baseline
    assert M.slot_rel_volume(ts, vol2, 20, 10)[0][-2] == pytest.approx(1.0)
    A = {"open": np.r_[np.full(len(ts) - 1, 100.0), 100.0], "high": np.r_[np.full(len(ts) - 1, 101.0), 104.5],
         "low": np.r_[np.full(len(ts) - 1, 99.0), 99.8], "close": np.r_[np.full(len(ts) - 1, 100.5), 104.0]}
    t0 = len(ts) - 3                                                        # the last day's 09:15 bar: raw 3× the others, rel 1.0
    A9 = {k: v[: t0 + 1].copy() for k, v in A.items()}
    A9["open"][t0], A9["high"][t0], A9["low"][t0], A9["close"][t0] = 100.0, 104.5, 99.8, 104.0
    A9["open"][t0 - 2:t0], A9["close"][t0 - 2:t0] = 100.5, 100.0              # the window's candles = the opposite (selling) side
    lvl = {"lo": 99.0, "hi": 100.6}
    A9["volume"] = vol[: t0 + 1]                                           # raw: 09:15 looks like 3× the window
    raw_ok, _, raw_cm = M.commitment(A9, t0, UP, lvl, {**S, "c0_dominance": False}, win=t0 - 2)
    A9["volume"] = rel[: t0 + 1]                                           # normalised: just its usual slot volume
    ok, why, cm = M.commitment(A9, t0, UP, lvl, {**S, "c0_dominance": False}, win=t0 - 2)
    assert raw_ok and raw_cm["vol_mult"] > 2.0
    assert not ok and cm.get("wait") == "low_volume" and cm["vol_mult"] <= 1.0


def test_v22_reads_raw_volume_bars_by_default_and_the_slot_baseline_only_as_a_what_if():
    """Method §3 Volume: raw bars, no time-slot baselines (default `volume_baseline = raw`); the Z-1 slot baseline stays a what-if."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    V = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    A = V.levels.A
    assert S3.DEFAULTS["volume_baseline"] == "raw" and np.allclose(A["volume"], A["volume_raw"], equal_nan=True)
    assert V.vol_view(len(m15) - 5, len(m15) - 1)[1].startswith("raw FUT volume per bar")
    V = E3.V22(m15, s={"level_death_side": "role", "volume_baseline": "slot"}, ltf=ltf, futures=fut)
    A = V.levels.A
    rel, _ = M.slot_rel_volume(m15["timestamp"], A["volume_raw"], 20, 10)
    assert np.allclose(np.nan_to_num(A["volume"], nan=-1), np.nan_to_num(rel, nan=-1)) and np.isfinite(A["volume"][-30:]).all()
    with pytest.raises(ValueError, match="volume_baseline"):
        E3.V22(m15, s={"volume_baseline": "slots"}, ltf=ltf, futures=fut)


# ------------------------------------------------------------------------------------------------ no look-ahead
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_no_look_ahead_states_and_g4_facts_equal_on_data_cut_at_t(mirror):
    m, p2, p1, vol = _build("flip_then_dead", mirror)
    full = _v(m, p2, p1, vol)
    Z = _zone(full.levels, mirror)
    for k in range(30, len(m) + 1):
        cut = m.iloc[:k].reset_index(drop=True)
        part = _v(cut, [p for p in p2 if p.confirm_bar < k], [p for p in p1 if p.confirm_bar < k], vol[:k])
        t = k - 1
        assert part.levels.snapshot(t) == full.levels.snapshot(t)
        Zp = [L for L in part.levels.L if L.id == Z.id]
        if Zp and Zp[0].state_at(t) == FL.FLIPPED:
            assert part.flip_context(t, _row(part.levels, Zp[0], t)) == full.flip_context(t, _row(full.levels, Z, t))
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    assert _row(full.levels, Z, t_flip - 1)["flipped_at"] is None and Z.state_at(t_flip - 1) == FL.BROKEN
    assert Z.state_at(Z.dead_bar - 1) != FL.DEAD


# ------------------------------------------------------------------------------------------------ shared band facts (find_bands)
def test_band_flip_facts_broken_vs_flipped():
    from facts import validity as FV
    m, _, _, _ = _build("flip_corrective")
    B = FV.bars_of(m)
    x = {"lo": 117.0, "hi": 118.0, "breaks": [{"bar": 33, "dir": "up"}]}
    f = LV.band_flip_facts(B, len(m) - 1, x, start=0)
    assert f["flip_state"] == FL.FLIPPED and f["far_swing"]["price"] >= 129.0 and f["flipped_at"]["bar"] > 33
    mb, _, _, _ = _build("broken_only")
    fb = LV.band_flip_facts(FV.bars_of(mb), len(mb) - 1, {**x, "breaks": [{"bar": 33, "dir": "up"}]}, start=0)
    assert fb["flip_state"] == FL.BROKEN and fb["flipped_at"] is None
    assert LV.band_flip_facts(B, len(m) - 1, {"lo": 1, "hi": 2, "breaks": []})["flip_state"] == FL.ACTIVE


# ------------------------------------------------------------------------------------------------ synthetic 12-Oct fixture (oct12_fixture)
def test_oct12_synthetic_fixture_supply_flips_when_the_first_swing_after_the_break_is_confirmed():
    """tests/oct12_fixture.py (synthetic bear call): its 1H supply is a support broken by acceptance with nothing below it (new lows).
    Under Abhi Z-1s (the corrected Z-1a wording) the far-side swing is the first swing low formed after the break and the zone FLIPS when
    that swing is CONFIRMED — it is not traded through. The zone is then a seller location; on the last day the in-zone study decides
    (⑥ judged, never a ② / ③ refusal). Abhi Z-1u: its own 1H band (the overlapping Daily band is a separate level, not a location)."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    new = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    ts = new.levels.ts
    t = next(i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == ts.dt.normalize().iloc[-1])
    snap = new.levels.snapshot(t)
    x = [y for y in snap if y["tf"] == "1H" and y["role"] == LV.RES and y["state"] == FL.FLIPPED and y["far_swing"]
         and y["far_swing"]["source"] == "first_confirmed_after_break" and y["lo"] <= m15["high"].iloc[t] and y["hi"] >= m15["low"].iloc[t]]
    assert x
    fs = x[0]["far_swing"]
    assert x[0]["flipped_at"] == fs["known_bar"]                           # flipped AT its confirmation
    assert m15["low"].iloc[fs["known_bar"]:t + 1].min() >= fs["price"]     # never traded through (reaching = confirmation)
    assert any(y["id"] == x[0]["id"] for y in new.levels.active(t, "DOWN"))
    daily = [y for y in snap if y["tf"] == "D" and not (y["hi"] < x[0]["lo"] or y["lo"] > x[0]["hi"])]
    assert all(not y["trade_location"] for y in daily) and all(y["id"] not in {a["id"] for a in new.levels.active(t, "DOWN")} for y in daily)
    r = new.decide(t)
    assert (r["level"] or {}).get("id") == x[0]["id"] and r["checklist"]["③"][0] is True and r["checklist"]["⑥"][0] is not None


# ------------------------------------------------------------------------------------------------ real days (private data only)
TD = "/home/user/trade-data"
EOD = os.path.join(TD, "live_export", "2026-10-13-eod")
FILES = {"m1_hist": os.path.join(TD, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"), "m1_exp": os.path.join(EOD, "NIFTY_1minute.parquet"),
         "i5": os.path.join(EOD, "oe_index_5min_NIFTY.parquet"), "fut5": os.path.join(EOD, "oe_futures_5min_NIFTY.parquet")}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONE = (22543.75, 22621.8)                                                # decision3 1H level (spot) = Abhi's 22,667 FUT supply (Z-1e)
FAR_UP = 22731.8                                                          # D2 H 6 Oct 14:00 (known 7 Oct 13:45) — the 6 / 7 Oct high


def _read(path):
    from elliott import data_policy as DP
    df = pd.read_csv(path, parse_dates=["timestamp"]) if path.endswith(".csv.gz") else pd.read_parquet(path)
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return DP.filter_allowed(df.assign(timestamp=ts), "annotation")       # NIFTY holdout rows never used


def _to15(df5):
    """Complete 09:15-anchored 15M bins (3 × 5M) only — an unfinished bin is dropped, never filled (replay_day's no-1m path)."""
    d = df5.copy()
    day = d["timestamp"].dt.normalize()
    k = ((d["timestamp"] - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(minutes=15)).astype(int)
    d["k"] = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(minutes=15)
    g = d.groupby("k").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("close", "size"))
    return g[g["n"] == 3].reset_index().rename(columns={"k": "timestamp"})[["timestamp", "open", "high", "low", "close"]]


def daily_history(window_start, log_fn=None):
    """Abhi Z-1t: the Daily warm-up the replay harness feeds V22 (as live feeds Upstox Daily) — `history.repo_level_history`: IS / VAL
    1m ⇒ complete Daily sessions + the sealed holdout Daily file ONLY as level history and ONLY for a 15M window after the holdout end
    (refused otherwise; logged "holdout daily bars used as level history: n bars")."""
    from decision3 import history as HI
    return HI.repo_level_history("NIFTY", window_start, root=ROOT, log_fn=log_fn)


def real_inputs():
    """NIFTY SPOT 15M (decision3 runs on spot, as the live engine3 feed): 1m history (golden window) + the EOD export's 1m to 12 Oct ⇒
    market_state.core.frame 15M / 5M; 13 Oct = complete bins of the export's spot 5M. FUT = the export's near-month 5M. Daily = the
    Z-1t warm-up (`daily_history`: IS / VAL + holdout Daily as level history, before the 15M window) + the window's own days — the same
    role as live's Upstox Daily. Returns (m15, ltf, fut, m1, daily). Skips without the data."""
    if not all(os.path.exists(p) for p in FILES.values()):
        pytest.skip("private trade-data (2026-10-13-eod export / upstox 1m) not present")
    import market_state.core as MC
    h = _read(FILES["m1_hist"])[["timestamp", "open", "high", "low", "close"]]
    e = _read(FILES["m1_exp"])[["timestamp", "open", "high", "low", "close"]]
    m1 = pd.concat([h, e[e["timestamp"] > h["timestamp"].max()]], ignore_index=True)
    end = pd.Timestamp(m1["timestamp"].max().normalize()) + pd.Timedelta(hours=15, minutes=30)
    i5 = _read(FILES["i5"])
    i5 = i5[i5["timestamp"].dt.normalize() > m1["timestamp"].max().normalize()][["timestamp", "open", "high", "low", "close"]]
    m15 = pd.concat([MC.frame(m1, "15m", end)[["timestamp", "open", "high", "low", "close"]], _to15(i5)], ignore_index=True)
    m15 = m15.sort_values("timestamp").reset_index(drop=True)
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    ltf = pd.concat([MC.frame(m1, "5m", end)[["timestamp", "open", "high", "low", "close"]], i5], ignore_index=True)
    ltf["bar_end"] = ltf["timestamp"] + pd.Timedelta(minutes=5)
    from decision3 import history as HI
    hist, _n = daily_history(m15["timestamp"].min())
    return m15, ltf, _read(FILES["fut5"]), m1, HI.daily_warmup("NIFTY", m15, hist)


@pytest.fixture(scope="module")
def real():
    from decision3 import history as HI
    m15, ltf, fut, m1, daily = real_inputs()
    # 1m intrabar order data where it exists (as the rsi2 phase-1 run and replay_day): swings2 D0 pivots — and so the RSI divergence
    # pairs — depend on it (without 1m the 12 Oct 09:15 swing high is not a D0 pivot). 13 Oct has no 1m (5M-built bars).
    return m15, ltf, fut, E3.V22(m15, m1, daily, s=None, ltf=ltf, futures=fut, sealed=HI.sealed_fn("NIFTY"))


def _day_bars(V, day):
    ix = [i for i in range(len(V.m15)) if pd.Timestamp(V.m15["timestamp"].iloc[i]).normalize() == pd.Timestamp(day)]
    if not ix:
        pytest.skip(f"{day} not in the data")
    return ix


def _zone_level(V, t):
    """Abhi's 12 Oct seller zone = the 1H band 22,543.75–22,621.80 itself (Abhi Z-1u: built from its own candles, never merged / widened;
    the overlapping Weekly bands are separate, context-only levels)."""
    hits = [x for x in V.levels.snapshot(t) if x["tf"] == "1H" and abs(x["lo"] - ZONE[0]) < 0.01 and abs(x["hi"] - ZONE[1]) < 0.01]
    assert hits, f"no decision3 1H level {ZONE} (report, do not tune): " + \
        str([(x["id"], x["tf"], x["lo"], x["hi"]) for x in V.levels.snapshot(t) if not (x["hi"] < ZONE[0] or x["lo"] > ZONE[1])])
    return hits[0]


def zone_table(r):
    """12 / 13 Oct report: the in-zone candles (time, side, body vs window, raw / normalised FUT volume, in zone)."""
    z = r.get("zone_read") or {}
    out = [f"{c['time'][5:16]} {c['side']:<12} body×{c['body_vs_window']} vol {c['vol_raw']} rel {c['vol_rel']} in_zone {c['in_zone']}"
           for c in z.get("candles", [])]
    return "\n".join(out + [f"summary: {z.get('summary')}"])


def _rows_on(V, ix, lid):
    """decide() rows of bars ix with this level's own evaluation (`level_evals` + `_level_eval` facts when it is not the row's level)."""
    out = []
    for t in ix:
        r = V.decide(t)
        if (r.get("level") or {}).get("id") != lid:
            _, _, _, ctx = V.step1(t)
            lv = [x for x in V.levels.snapshot(t) if x["id"] == lid]
            if lv and ctx["trend"] in ("UP", "DOWN"):
                dd, part, extra = V._level_eval(t, ctx["trend"], lv[0], ctx["cap"], ctx["notes"])
                r = {**r, "decision": {"s": "setup", "w": "wait", "n": "no_trade"}[dd], "checklist": {**r["checklist"], **part},
                     "level": lv[0], "commit": extra.get("commit"), "zone_read": extra.get("zone_read"), "conviction": extra.get("conviction")}
        out.append(r)
    return out


def test_real_12_oct_seller_zone_in_zone_study_and_golden_bear_call(real):
    """12 Oct NIFTY (Abhi Z-1e / Z-1w): the 22,543.75–22,621.80 spot zone is a seller area that day (role resistance, not BROKEN / DEAD)
    and Abhi's bear call is the golden truth (handover in THIS visit + LTF CHoCH after the arrival + dominant commitment on higher FUT
    volume, Z-1p / Z-1q / Z-1r / Z-1v) — asserted on that band, never tuned. A miss xfails ONLY on its exact, asserted cause."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-12")
    lvl = _zone_level(V, ix[0])
    assert lvl["role"] == LV.RES and lvl["state"] in (FL.ACTIVE, FL.TESTED, FL.FLIPPED)   # Abhi Z-1w: a seller area on 12 Oct
    rows = _rows_on(V, ix, lvl["id"])
    at = [r for r in rows if (r["checklist"].get("③") or [None])[0]]
    for r in at:
        cm = r.get("commit") or {}
        print(f"\n{r['ts']} {r['decision']} ⑥ {r['checklist'].get('⑥')} conv {r.get('conviction')} · visit {cm.get('visit_start')} → "
              f"{cm.get('visit_end')} (previous ended {cm.get('visit_prev_end')}) · handover {cm.get('handover_state')} · "
              f"{cm.get('choch_vs_arm')} · {cm.get('form')} body×{cm.get('body_mult')} vol×{cm.get('vol_mult')} · gaps {cm.get('vol_gaps')}")
        print(zone_table(r))
    assert at
    bear = [r for r in at if r["decision"] == "setup" and r["trend_used"] == "DOWN"]
    if bear:                                                               # the golden bear call (never tuned)
        cm = bear[0]["commit"]
        assert cm["handover_present"] is True and cm["choch"]["done"] and not cm.get("data_problem")
        assert cm.get("vol_mult") is not None and cm["vol_mult"] > 1.0     # on real volume evidence (Abhi: never an automatic pass)
        return
    # the miss — each cause asserted (Abhi, L3-c: the approach leg runs across the gap from the last structure swing; no automatic
    # pass; the commitment's volume is compared with the AVERAGE of its comparison set). 09:30: fast-form handover ✅ and 5M CHoCH ✅,
    # but the commitment's volume is not higher than that average ⇒ no commitment ⇒ no bear call.
    by = {r["ts"][11:16]: r for r in rows}
    c930 = by["09:30"]["commit"] or {}
    hs = c930.get("handover_state") or {}
    assert c930.get("handover_present") is True and hs.get("form") == "sharp_reversal"
    assert (hs.get("sharp") or {}).get("parts") == {"c1_rejected": True, "c2_dominant": True, "c2_closes_beyond_push_body": True}
    assert (c930.get("choch") or {}).get("done") is True
    assert c930.get("confirm_wait") == "low_volume" and c930.get("vol_vs") == "the average of the approach leg's candles"
    assert str(c930.get("approach_from")).startswith("2026-10-09 09:15")   # across the gap — not cut at the session change
    assert c930.get("vol_mult") is not None and c930["vol_mult"] < 1.0 and c930.get("vol_ref_gaps") == 0
    A = V.levels.A
    print(f"\n09:30 commitment volume {A['volume'][int(by['09:30']['bar'])]:,.0f} vs the average of the approach leg "
          f"{c930['vol_ref_avg']:,.0f} over {c930['vol_ref_n']} candles (×{c930['vol_mult']})")
    pytest.xfail("golden 12 Oct bear call NOT produced on real volume evidence — fast-form handover ✅ + 5M CHoCH ✅ at 09:30, but the "
                 f"commitment's volume is ×{c930['vol_mult']} of the approach leg's average ({c930['vol_ref_n']} candles, across the "
                 "gap — Abhi, L3-c) — reported, never tuned")


def test_real_oct_1_to_12_lifecycle_of_the_22544_22622_band(real):
    """Abhi Z-1w: the 22,543.75–22,621.80 band is built from its own 1H swing candle (5 Oct, Z-1u — never widened); its full lifecycle
    from 1 Oct (incl. the narrower band it overlaps — lineage) is printed for the report; on 12 Oct it is a seller area."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-12")
    lvl = _zone_level(V, ix[0])
    Z = V.levels.L[lvl["id"]]
    T = lambda b: str(V.levels.ts.iloc[int(b)])[:16]                       # noqa: E731
    assert Z.tf == "1H" and len({(round(lo, 2), round(hi, 2)) for _, lo, hi in Z.bands}) == 1   # never widened
    for x in Z.lineage:
        o = V.levels.L[x["overlaps"]] if "overlaps" in x else None
        if o is not None:
            print(f"\nlineage L{o.id} {o.bands[0][1]:,.2f}–{o.bands[0][2]:,.2f} ({o.tf}):",
                  [(T(b), k, d) for b, k, d in o.events if k != "test" and T(b) >= "2026-10-01"])
    ev = [(T(b), k, d) for b, k, d in Z.events if k != "test" and "2026-10-01" <= T(b) <= "2026-10-12 23:59"]
    print(f"\nL{Z.id} {ZONE} born {T(Z.born_bar)} ({Z.births[0]}, {Z.role0}):", ev)
    assert Z.role_at(ix[0]) == LV.RES and Z.state_at(ix[0]) not in (FL.BROKEN, FL.DEAD)


def test_real_13_oct_no_bear_call(real):
    """13 Oct NIFTY (Abhi): price entered the seller zone, small red candles on low volume, no fall, a sideways base, afternoon breakout
    ⇒ NO bear call (golden). No bull setup while the Daily trend is DOWN. The zone's state that day (Abhi: still resistance while price
    stays below 22,731.8) is the separate strict-xfail test below (OPEN_QUESTIONS Z-1y)."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-13")
    lvl = _zone_level(V, ix[0])
    rows = [V.decide(t) for t in ix]
    for r in rows:
        if (r.get("level") or {}).get("id") == lvl["id"] and (r["checklist"].get("③") or [None])[0]:
            print(f"\n{r['ts']} {r['decision']} ⑥ {r['checklist'].get('⑥')} · trend {r['trend_used']}")
            print(zone_table(r))
    assert not [r for r in rows if r["decision"] == "setup" and r["trend_used"] == "DOWN"
                and (r.get("level") or {}).get("lo", 0) <= ZONE[1] and (r.get("level") or {}).get("hi", 0) >= ZONE[0]]
    if all(r["trend_used"] == "DOWN" for r in rows):
        assert not [r for r in rows if r["decision"] == "setup" and (r.get("level") or {}).get("role") == LV.SUP]
    nxt = [w for w in (rows[-1].get("watch_list") or []) if w["role"] == LV.RES]
    print(f"13 Oct close watch-list: {[(w['lo'], w['hi'], w['state']) for w in nxt]}")
    assert nxt and nxt[0]["lo"] > ZONE[1]                                  # Abhi B2: the next seller zones above are already armed


def test_real_13_oct_zone_stays_resistance_while_price_stays_below_22731(real):
    """Abhi Z-1y (a): the far-side swing is the prior STRUCTURAL swing of the same degree beyond the band — the lower high 22,731.8. The
    12 Oct 09:15 wick to 22,651.10 (its candle closed back inside the band) is a sweep, not a structural swing. 13 Oct never traded past
    22,731.8 ⇒ the 22,543.75–22,621.80 band is still resistance (BROKEN at most — not FLIPPED to support, not DEAD)."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-13")
    lvl = _zone_level(V, ix[0])
    L = V.levels.L[lvl["id"]]
    t = ix[-1]
    hi = float(m15["high"].iloc[ix].max())
    assert hi <= FAR_UP                                                    # the day this expectation is about
    f = V.levels.flip_view(L, t)
    fs = f.get("far_swing") or {}
    print(f"\n13 Oct: spot high {hi:,.2f} < 22,731.8 · state {L.state_at(t)}, role {L.role_at(t)}, far swing {fs.get('price')} "
          f"({str(fs.get('ts'))[:16]}, {fs.get('source')})")
    assert L.role_at(t) == LV.RES and L.state_at(t) not in (FL.FLIPPED, FL.DEAD) and L.count("flip", t) == 0
    # method §3 (layer 2): broken = a close beyond AND a swing formed beyond — on 13 Oct no swing formed above the area, so it is not
    # BROKEN (the old 3-close rule called it BROKEN); Abhi's expectation (resistance while price stays below the far swing) is unchanged
    assert L.state_at(t) in (FL.ACTIVE, FL.TESTED) and not [b for b, k, _ in L.events if k == "broken" and b <= t and b >= ix[0]]
    known = [p for p in V.levels._pv_sorted if p.confirm_bar <= t]          # the far-side swing an upward break would have to pass
    far = FL.far_swing(known, L.lo, L.hi, True, ix[0], V.levels.A["close"])
    assert far is not None and far.price == pytest.approx(FAR_UP, abs=0.1)


def test_real_29_sep_new_low_flip_on_the_swing_confirmation_with_the_daily_warmup(real):
    """29 Sep NIFTY (Abhi Z-1s / Z-1t): the 22,725–22,810 1H supply is a Q40 prior Daily level — born only with the Daily warm-up. It
    broke at 09:45 (new lows, no swing below it) and FLIPPED at 11:30 when the first swing low after the break (22,569.65) was CONFIRMED
    — never traded through. The 12:00 rally into the zone is the pullback; 12:00 / 12:15 are judged by the in-zone study (reported, not
    forced). 29 Sep has no FUT bar in trade-data ⇒ never a setup without volume (Z-1c / RF-2)."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-09-29")
    z = [x for x in V.levels.snapshot(ix[0]) if abs(x["lo"] - 22725.45) < 1.0 and abs(x["hi"] - 22809.9) < 1.0]
    assert z and "a:D-prior" in z[0]["births"] and z[0]["tf"] == "D"      # Abhi Z-1u: its own Daily band, no 1H zone over it
    L = V.levels.L[z[0]["id"]]
    ts = lambda b: str(V.levels.ts.iloc[b])[:16]                          # noqa: E731
    ev = [(ts(b), k) for b, k, _ in L.events if k in ("broken", "flip", "dead", "reclaim") and ts(b).startswith("2026-09-29")]
    print(f"\n29 Sep zone {z[0]['lo']:,.2f}–{z[0]['hi']:,.2f}: {ev}")
    brk = [x for x, k in ev if k == "broken"]                              # method §3: broken = a close beyond + a swing formed beyond
    assert brk and brk[0] == "2026-09-29 11:00" and ("2026-09-29 11:30", "flip") in ev   # broken when the D1 swing below confirmed (layer 2;
    # the old 3-close rule said 09:45); Abhi Z-1s: FLIPPED at 11:30 (unchanged)
    t_flip = next(b for b, k, _ in L.events if k == "flip")
    f = V.levels.flip_view(L, t_flip)
    assert f["far_swing"]["price"] == pytest.approx(22569.65) and f["far_swing"]["source"] == "first_confirmed_after_break"
    assert float(m15["low"].iloc[t_flip:ix[-1] + 1].min()) >= 22569.65 - 1e-6   # reached by confirmation, never traded through
    for t in ix:
        r = V.decide(t)
        if r["ts"][11:16] in ("12:00", "12:15"):
            cm = r.get("commit") or {}
            print(f"{r['ts'][11:16]} {r['decision']} lvl {(r.get('level') or {}).get('id')} ③ {r['checklist'].get('③')} "
                  f"⑥ {r['checklist'].get('⑥')} · visit {cm.get('visit_start')} (previous ended {cm.get('visit_prev_end')}) · handover "
                  f"{cm.get('handover_state')} · CHoCH {cm.get('choch_vs_arm') or cm.get('ltf_line')}")
            assert (r.get("level") or {}).get("id") == L.id and r["checklist"]["③"][0] is True   # the pullback into the flipped zone
        assert r["decision"] != "setup"                                    # no FUT that day ⇒ no entry


# ------------------------------------------------------------------------------------------------ Abhi A / B: in-zone study, watch-list
def _zone_bars(kind, mirror):
    """A seller zone 100–102 (bear call, DOWN) and 9 in-zone bars arm … t − 1, then the decision bar t. kind "absorption": the buying
    (counter) candles grow and their volume rises inside the zone; kind "takeover": the selling candles grow on rising volume, the buying
    candles shrink, then a dominant red candle on high volume. Mirror: prices reflected (p ⇒ 2·MID − p), bull put. Volume = already
    slot-normalised values."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    if kind == "absorption":
        seq = [(101.0, 100.6, 1.0), (100.6, 100.9, 0.8), (100.9, 100.5, 1.0), (100.5, 100.8, 0.8),
               (100.8, 100.5, 1.0), (100.5, 101.4, 1.4), (101.4, 101.0, 1.0), (101.0, 101.9, 1.6), (101.9, 101.6, 1.0),
               (101.6, 100.9, 1.0)]
    else:
        seq = [(101.0, 101.4, 1.2), (101.4, 101.1, 0.9), (101.1, 101.5, 1.1), (101.5, 101.2, 0.9),
               (101.2, 101.4, 0.8), (101.4, 100.8, 1.3), (100.8, 101.0, 0.7), (101.0, 100.2, 1.5), (100.2, 100.4, 0.6),
               (100.4, 98.6, 2.5)]
    o = np.array([f(x[0]) for x in seq])
    c = np.array([f(x[1]) for x in seq])
    A = {"open": o, "close": c, "high": np.maximum(o, c) + 0.3, "low": np.minimum(o, c) - 0.3, "volume": np.array([x[2] for x in seq])}
    lvl = {"lo": min(f(100.0), f(102.0)), "hi": max(f(100.0), f(102.0))}
    return A, lvl, (UP if mirror else DOWN)


def _tss(n):
    return pd.date_range("2030-01-07 09:15", periods=n, freq="15min").to_numpy()


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_in_zone_absorption_is_no_trade(mirror):
    """The #329 "strengthening" absorption read (what-if, `absorption_rule = strengthening`); the method's sideways-base absorption is
    tested in tests/test_decision3_zone_answers.py."""
    A, lvl, d = _zone_bars("absorption", mirror)
    t = len(A["close"]) - 1
    s = {**S, "absorption_rule": "strengthening"}
    cf = M.confirm(A, 0, t, d, lvl, {**s, "ltf_choch": False})
    assert not cf["ok"] and cf["wait"] == M.C_ABSORB                      # counter side strengthening inside the zone ⇒ no entry
    z = FL.zone_read(A, _tss(t + 1), 0, t, d, lvl, s)
    assert z["summary"]["absorption"] is True and z["summary"]["handover"] is False


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_in_zone_seller_takeover_plus_commitment_is_a_trade(mirror):
    A, lvl, d = _zone_bars("takeover", mirror)
    t = len(A["close"]) - 1
    cf = M.confirm(A, 0, t, d, lvl, {**S, "ltf_choch": False})
    assert cf["ok"] and cf["c0"] and not cf["absorption"], cf["why"]
    assert cf["commit"]["vol_mult"] > 1.0 and cf["commit"]["form"]
    z = FL.zone_read(A, _tss(t + 1), 0, t, d, lvl, S)
    assert z["summary"]["trade_side_growing"] is True and z["summary"]["absorption"] is False


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_zone_broken_the_next_zone_is_already_armed(mirror):
    """Abhi B2: in a downtrend every supply ahead of price is armed, nearest first; the nearest breaks (the correction extends) ⇒ the
    next one is already on the list — no reset, no gap. Mirror: uptrend, demand zones below."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    anchors = [(0, 140), (6, 110), (10, 130), (18, 104), (26, 118), (34, 100), (40, 106), (50, 124)]
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("L"), f(110), 6, 8), P(sw("H"), f(130), 10, 12), P(sw("L"), f(104), 18, 20), P(sw("H"), f(118), 26, 28),
          P(sw("L"), f(100), 34, 36)]
    lv = _levels(m, p2, [])
    trend = "UP" if mirror else "DOWN"
    before = [x["id"] for x in lv.active(40, trend)]
    # Abhi Z-1u: swing and BOS-base bands are separate 1H levels now (never merged / widened) ⇒ more, touching bands; the B2 rule is the
    # same: the zone that takes over after the nearest breaks was already armed before the break (no reset, no gap)
    R1 = lv.L[before[0]]
    assert len(before) >= 2
    t_brk = next(b for b, k, _ in R1.events if k == "broken" and b > 40)
    after = [x["id"] for x in lv.active(t_brk, trend)]
    assert R1.id not in after and R1.state_at(t_brk) in (FL.BROKEN, FL.DEAD)   # (a flipped zone may die on that bar, Z-1f)
    R2 = lv.L[after[0]]
    assert R2.id in before and (R2.lo > R1.lo if not mirror else R2.hi < R1.hi)
    assert all(R2.id in [x["id"] for x in lv.active(t, trend)] for t in range(40, len(m)))   # no gap in watching R2


# ------------------------------------------------------------------------------------------------ Abhi Z-1j / Z-1h
def test_range_state_is_context_only_never_an_entry_gate(abc, monkeypatch):
    """Abhi Z-1j: overlapping / sideways candles inside the zone are the handover study, not a blocker — §5.3 range state is reported as
    a context fact and never changes the decision (the old gate only with `range_state_gate` = True, legacy)."""
    m15, s, V, _ = abc
    s = {**s, "verdict_rule": "score"}                                     # §5.3 range state exists only in the legacy score rule (layer 6)
    bars = range(735, 746)
    V = E3.V22(m15, s={**s, "c0_volume_required": False})
    base = {t: V.decide(t) for t in bars}
    monkeypatch.setattr(M, "range_state", lambda A, t, s=None: True)
    monkeypatch.setattr(M, "range_broken_by", lambda A, t, d, s=None: False)
    V2 = E3.V22(m15, s={**s, "c0_volume_required": False})
    for t in bars:
        r = V2.decide(t)
        assert (r["decision"], r["checklist"]["⑥"]) == (base[t]["decision"], base[t]["checklist"]["⑥"])
        if (r["checklist"].get("③") or [None])[0]:
            assert r["range_state"] is True and "§5.3" not in str(r["checklist"]["⑥"][1])
    V3 = E3.V22(m15, s={**s, "c0_volume_required": False, "range_state_gate": True})
    hit = [V3.decide(t) for t in bars if (V3.decide(t)["checklist"].get("③") or [None])[0]]
    assert hit and all("§5.3" in str(r["checklist"]["⑥"][1]) and r["decision"] == "wait" for r in hit)


def test_short_fut_history_falls_back_to_raw_per_bar_volume_not_a_data_error():
    """Abhi Z-1h: < vol_slot_min_sessions sessions of slot history ⇒ "volume normalisation: insufficient history", the window's
    comparisons use the RAW per-bar FUT volume — labelled in the row / payload, never a data-problem wait. FUT missing entirely stays the
    data error (Z-1c)."""
    import engine3_live as L
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    last = pd.to_datetime(m15["timestamp"]).dt.normalize().iloc[-1]
    days = sorted(pd.to_datetime(fut["timestamp"]).dt.normalize().unique())
    short = fut[pd.to_datetime(fut["timestamp"]).dt.normalize() >= days[-5]]                    # 4 earlier sessions only
    sv = {"level_death_side": "role", "level_flip_rule": "acceptance", "a2_handover_required": False,   # fixture's setup level (old pins)
          "volume_baseline": "slot"}                                       # the Z-1h fallback exists only with the slot baseline (what-if)
    V = E3.V22(m15, s=sv, ltf=ltf, futures=short)
    ts = V.levels.ts
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last]
    A, label = V.vol_view(bars[0], bars[-1])
    assert label.startswith(V.INSUFFICIENT) and np.allclose(A["volume"][bars], V.levels.A["volume_raw"][bars], equal_nan=True)
    rows = [V.decide(t) for t in bars]
    assert not [r for r in rows if "data problem" in str(r["checklist"].get("⑥"))]
    seen = [r for r in rows if (r["checklist"].get("③") or [None])[0]]
    assert seen and all(r["volume_measure"].startswith(V.INSUFFICIENT) for r in seen)
    row = L.row_from_v22("NIFTY", seen[0], lambda: pd.Timestamp("2030-03-04 10:00"))
    assert "insufficient history" in row["payload"]
    full = E3.V22(m15, s=sv, ltf=ltf, futures=fut)
    assert full.vol_view(bars[0], bars[-1])[1].startswith("slot-normalised")


# ------------------------------------------------------------------------------------------------ volume baseline: incomplete FUT / rollover
def test_fut_present_but_incomplete_bar_is_na_with_reason_and_gaps_are_counted():
    """Reviewer (Z-1 volume): a 15M bar with < 3 of 3 FUT 5M children is marked incomplete — NA with a reason, never an under-counted
    sum; FUT present but with gaps inside the in-zone window ⇒ the label carries the gap count and the reason (no silent averaging)."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    ts15 = pd.to_datetime(m15["timestamp"])
    last = ts15.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts15)) if ts15.dt.normalize().iloc[i] == last]
    hole, gone = bars[3], bars[5]
    ft = pd.to_datetime(fut["timestamp"])
    drop = (ft == ts15.iloc[hole] + pd.Timedelta(minutes=5)) | ((ft >= ts15.iloc[gone]) & (ft < ts15.iloc[gone] + pd.Timedelta(minutes=15)))
    V = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut[~drop.to_numpy()].reset_index(drop=True))
    full = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    raw = V.levels.A["volume_raw"]
    assert np.isnan(raw[hole]) and np.isfinite(full.levels.A["volume_raw"][hole])          # NA, not 2/3 of the bar
    assert np.isnan(V.levels.A["volume"][hole])
    assert V.vol_reason[hole] == "incomplete 15M FUT bar (2 of 3 5M bars)" and V.vol_reason[gone] == "no FUT bar"
    assert "incomplete 15M FUT bar (2 of 3 5M bars)" in V.vol_na_reason(hole) and "no FUT bar" in V.vol_na_reason(gone)
    _, label = V.vol_view(bars[0], bars[-1])
    assert f"FUT volume gaps: 2/{len(bars)} bars" in label and "incomplete 15M FUT bar" in label and "no FUT bar" in label
    assert "gaps" not in full.vol_view(bars[0], bars[-1])[1]
    ok = [i for i in bars if i not in (hole, gone)]                         # complete bars keep their exact volume
    assert np.allclose(raw[ok], full.levels.A["volume_raw"][ok])


def test_slot_baseline_excludes_rollover_days():
    """Reviewer: slot_rel_volume leaves FUT rollover days out of every baseline, as legs2.volume.rvol does."""
    days = pd.bdate_range("2030-01-01", periods=14)
    ts = pd.Series([d + pd.Timedelta(hours=9, minutes=15) for d in days])
    vol = np.full(len(ts), 100.0)
    vol[5] = 10000.0                                                        # a rollover-day spike
    rel, cnt = M.slot_rel_volume(ts, vol, sessions=20, min_sessions=10, exclude_days=[days[5]])
    _, cnt0 = M.slot_rel_volume(ts, vol, sessions=20, min_sessions=10)
    assert cnt[-1] == 12 and cnt0[-1] == 13 and rel[-1] == pytest.approx(1.0)
    rel2, cnt2 = M.slot_rel_volume(ts, np.where(np.arange(len(ts)) < 7, 1000.0, 100.0), sessions=20, min_sessions=3,
                                   exclude_days=list(days[:4]))
    rel3, _ = M.slot_rel_volume(ts, np.where(np.arange(len(ts)) < 7, 1000.0, 100.0), sessions=20, min_sessions=3)
    assert cnt2[-1] == 9 and rel2[-1] == pytest.approx(1.0)                 # baseline = days 4..12 ⇒ median 100
    assert rel3[-1] == pytest.approx(0.1)                                   # with the rollover days in, the baseline is inflated


# ------------------------------------------------------------------------------------------------ Telegram data-problem line (review)
def test_data_problem_day_marked_sent_only_after_a_successful_send(tmp_path):
    import engine_signal as ES
    p, now = str(tmp_path / "a.json"), pd.Timestamp("2030-01-07 10:16")
    calls = []

    def boom(line):
        calls.append(line)
        raise RuntimeError("telegram down")
    assert ES.alert_data_problem("NIFTY", "x", send=boom, state_path=p, now=now) is False
    assert ES.alert_data_problem("NIFTY", "x", send=lambda line: calls.append(line) or False, state_path=p, now=now) is False
    sent = []
    assert ES.alert_data_problem("NIFTY", "x", send=sent.append, state_path=p, now=now + pd.Timedelta(minutes=15)) is True
    assert len(calls) == 2 and len(sent) == 1                               # retried until it went through
    assert ES.alert_data_problem("NIFTY", "x", send=sent.append, state_path=p, now=now + pd.Timedelta(minutes=30)) is False


def test_data_problem_line_only_for_nifty_banknifty_never_sensex(tmp_path, monkeypatch):
    import json

    from scripts import engine_signal_run as ESR
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []

    def run(sym, tok):
        return {"bar_ts": "2030-01-07 10:15:00", "decision": "wait", "skipped": "test",
                "payload": json.dumps({"engine": "decision3", "data_problem": "data problem: FUT volume missing"})}
    ESR.main(["--symbols", "NIFTY,BANKNIFTY,SENSEX"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
             alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-07 10:16"))
    assert len(sent) == 2 and not [x for x in sent if "SENSEX" in x]
    assert ESR._data_problem(run("SENSEX", None), "SENSEX") is None and ESR._data_problem(run("NIFTY", None), "NIFTY")


def test_payload_size_limit_never_drops_the_data_problem_flag():
    import json

    import engine3_live as L
    big = {"engine": "decision3", "checklist": {"x": "y" * 30000}, "zone_read": {"z": "w" * 30000},
           "data_problem": "data problem: FUT volume missing (test)", "volume_measure": "slot-normalised"}
    out = L.fit_payload(big)
    d = json.loads(out)                                                     # valid JSON (no blind cut)
    assert len(out) <= L.PAYLOAD_MAX and d["data_problem"] == big["data_problem"] and d["dropped"] == ["checklist", "zone_read"]
    huge = {**big, "volume_note": "v" * 30000}
    d2 = json.loads(L.fit_payload(huge))
    assert d2["data_problem"] == big["data_problem"] and "all context" in d2["dropped"]
    small = {"engine": "decision3", "data_problem": None}
    assert L.fit_payload(small) == json.dumps(small)


def test_band_flip_facts_new_highs_flip_when_the_first_swing_after_break_is_confirmed():
    """band_flip_facts applies Abhi Z-1s like the engine (flip.far_swing / flip.reached) — no swing beyond the band before the break (new
    highs) ⇒ the far swing is the FIRST swing beyond the band formed after the break; FLIPPED when it is CONFIRMED (not traded through)."""
    from facts import validity as FV
    hi = [96.5, 97.0, 96.0, 97.5, 96.5, 97.2, 96.0, 97.4, 96.4, 97.0] * 2                     # bars 0-19: below the 95-98 band top
    hi += [100.5, 101.5, 102.5, 103.0, 104.0, 103.0, 102.0, 101.5, 102.5, 103.5, 105.0, 104.5]  # break at 20, swing 104 @24, past it @30
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    df = pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl})
    B = FV.bars_of(df)
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 20, "dir": "up"}]}
    before = LV.band_flip_facts(B, 25, x, start=0)                          # swing @24 not yet confirmed (k = 2)
    assert before["flip_state"] == FL.BROKEN and before["far_swing"] is None
    mid = LV.band_flip_facts(B, 26, x, start=0)                             # confirmed at 26 (24 + k) ⇒ FLIPPED there
    assert mid["flip_state"] == FL.FLIPPED and mid["far_swing"]["bar"] == 24 and mid["far_swing"]["price"] == 104.0
    assert mid["far_swing"]["source"] == "first_confirmed_after_break" and mid["flipped_at"]["bar"] == 26
    assert max(B.H[24:27]) <= 104.0                                         # not traded through yet
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flip_state"] == FL.FLIPPED and f["flipped_at"]["bar"] == 26 and f["far_swing"]["bar"] == 24


# ------------------------------------------------------------------------------------------------ end to end on the DEFAULT path (review)
_HANDOVER = [(19436, 19458, 6e5), (19458, 19455, 2e5), (19455, 19466, 6e5), (19466, 19452, 5e5), (19452, 19455, 2e5), (19455, 19440, 7e5)]
_NO_HANDOVER = [(19436, 19458, 6e5), (19458, 19446, 4e5), (19446, 19462, 5e5), (19462, 19458, 3e5), (19458, 19468, 6e5),
                (19468, 19452, 3e5)]


def _default_case(window, commit_vol=1.2e6, with_fut=True):
    """tests.test_decision3_method._abc_m15 (Daily DOWN): its supply 19,432–19,472 is a support broken at bar 651 and FLIPPED at 659
    (price traded past the far swing before the break). Bars 735–740 are rewritten to sit in that zone (the in-zone study window), 741 is
    the bearish commitment. FUT 5M = 3 complete children per 15M bar (flat 3e5 elsewhere); LTF = 5M split of the same bars."""
    from tests.ltf_fixtures import split_bars
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    vol = np.full(len(m15), 3e5)
    for j, (o_, c_, v_) in enumerate(window):
        m15.loc[735 + j, ["open", "close", "high", "low"]] = [o_, c_, max(o_, c_) + 2, min(o_, c_) - 2]
        vol[735 + j] = v_
    m15.loc[741, ["open", "high"]] = [19440, 19443]
    vol[741] = commit_vol
    fut = pd.DataFrame({"timestamp": [t + pd.Timedelta(minutes=5 * j) for t in m15["timestamp"] for j in range(3)],
                        "volume": np.repeat(vol / 3.0, 3), "expiry": pd.Timestamp("2030-03-28")})
    return E3.V22(m15, ltf=split_bars(m15, 15, 3), futures=fut if with_fut else None)


def test_end_to_end_default_path_flipped_zone_handover_choch_commitment_with_volume_is_a_setup():
    """DEFAULT settings, no pins: far_swing flip rule + c0_volume_required + mandatory handover (a2) + LTF CHoCH, through V22.decide()."""
    V = _default_case(_HANDOVER)
    assert (V.s["level_flip_rule"], V.s["c0_volume_required"], V.s["a2_handover_required"], V.s["ltf_choch"], V.s["wave_gates"]) == \
        ("far_swing", True, True, True, False)
    r = V.decide(741)
    lv = r["level"]
    assert lv["state"] == FL.FLIPPED and lv["far_swing"]["source"] == "before_break" and lv["broken_at"] <= lv["flipped_at"] < 735   # rule
    # change (layer 2, was <): flipped = beyond the area AND beyond the far swing — the swing beyond may form on the flip bar itself, so a
    # separate, earlier BROKEN bar is no longer required
    assert r["decision"] == "setup" and r["checklist"]["⑥"][0] is True and r["conviction"] in ("A", "B")
    cm = r["commit"]
    assert cm["handover_present"] is True and cm["arm_bar"] == 735 and cm["choch"]["done"] and cm["vol_mult"] > 1.0
    assert r["volume_measure"].startswith("raw FUT volume per bar") and not cm.get("data_problem")   # method §3: raw bars
    assert cm["vol_vs"] == "the average of the approach leg and the visit's opposite-side candles" and cm["approach_from"] < cm["visit_start"]
    assert r["zone_read"]["summary"]["handover"] is True and r["checklist"]["G4"][0] is None
    early = V.decide(736)                                                  # inside the visit, handover not yet ⇒ wait (a2 first). Z-1x: the BOS
    # base band is no longer widened, so it is the same zone as the 1H band (lineage) and bars 737–738 open above it (③ gap breakout)
    assert early["decision"] == "wait" and "no handover" in early["checklist"]["⑥"][1]


def test_end_to_end_default_path_no_handover_or_no_fut_is_no_entry():
    r = _default_case(_NO_HANDOVER).decide(741)                             # same zone, CHoCH + commitment, but no handover: the buyers
    assert r["decision"] == "wait" and (r["commit"] or {}).get("handover_present") is False   # keep coming in smaller candles and
    assert M.REASON[M.C_ABSORB] in r["checklist"]["⑥"][1]                  # price stays in the area ⇒ method §3 absorption (no trade)
    assert r["commit"]["confirm_wait"] == M.C_ABSORB
    nf = _default_case(_HANDOVER, with_fut=False).decide(741)               # FUT missing ⇒ data problem, never a grade-B entry
    assert nf["decision"] == "wait" and "data problem" in nf["checklist"]["⑥"][1]
    lo = _default_case(_HANDOVER, commit_vol=1e5).decide(741)              # commitment without volume ⇒ no entry
    assert lo["decision"] == "wait" and "low volume" in lo["checklist"]["⑥"][1]


# ------------------------------------------------------------------------------------------------ re-review (282d484) fixes
def test_band_flip_facts_flipped_then_passed_again_is_dead_like_the_engine():
    """A 95–98 band breaks up (bar 20) with nothing above it ⇒ FLIPPED when the first swing after the break (104 @ 24) is confirmed
    (bar 26, Z-1s); then it breaks down (bar 36) with nothing below it ⇒ DEAD when that break's first swing (the low @ 39) is confirmed
    (bar 41) — never a second flip (Z-1f / Z-1k / Z-1s, the DEAD rule under the corrected wording)."""
    from facts import validity as FV
    hi = [96.5, 97.0, 96.0, 97.5, 96.5, 97.2, 96.0, 97.4, 96.4, 97.0] * 2
    hi += [100.5, 101.5, 102.5, 103.0, 104.0, 103.0, 102.0, 101.5, 102.5, 103.5, 105.0, 104.5]
    hi += [103.0, 101.0, 99.0, 97.5, 95.5, 94.5, 93.8, 93.0, 94.0, 94.6, 93.5, 91.5, 91.0]
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    B = FV.bars_of(pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl}))
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 20, "dir": "up"}, {"bar": 36, "dir": "down"}]}
    assert LV.band_flip_facts(B, 35, x, start=0)["flip_state"] == FL.FLIPPED
    mid = LV.band_flip_facts(B, 40, x, start=0)
    assert mid["flip_state"] == FL.BROKEN and mid["flipped_at"]["bar"] == 26 and mid["broken_at"]["bar"] == 36
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flip_state"] == FL.DEAD and f["dead_at"]["bar"] == 41 and f["flipped_at"]["bar"] == 26
    assert min(B.L[39:42]) >= 92.0                                          # the low @ 39 was confirmed, never traded through
    assert "dead" in LV.band_label({**f, "role": "resistance", "lo": 95.0, "hi": 98.0, "touch_count": 2, "valid": True})


def test_setup_chart_notes_for_maturity_and_origin_are_context_only_in_english():
    import inspect

    from decision3 import setup_chart as SC
    notes = ["context: impulse mature — target जवळ (Q44) (gate / downgrade नाही — Abhi B1)",
             "context: correction protected origin जवळ (gate नाही — Abhi B1)"]
    src = inspect.getsource(E3)
    for n in notes:
        assert n in src                                                    # the exact notes the engine writes by default
        en = SC.note_en(n)
        assert en.startswith("context only") and "no cap, no gate" in en and en.isascii()
        assert "weak" not in en and "cap B" not in en and "(gate" not in en


def test_no_entry_reason_never_names_origin_risk():
    from bots_common import plain_text as PT
    base = {"trend": "UP", "origin_risk": True, "ok": False}
    assert PT.unclear_words({**base, "counter": "correction"}) == "Daily UP is inside a bigger correction"
    w = PT.unclear_words({**base, "structure_against": True, "counter": "correction"})
    assert "structure" in w and "starting point" not in w
    assert "starting point" not in PT.unclear_words(base) and "origin" not in PT.unclear_words(base)
    assert "broke on a daily close" in PT.unclear_words({**base, "phase": "origin_broken"})


def test_fut_children_use_the_fut_bar_step_and_the_legs2_session_anchor():
    from legs2 import volume as LVOL
    day = pd.Timestamp("2030-01-07")
    t5 = [day + LVOL.OPEN + pd.Timedelta(minutes=5 * j) for j in range(9)]
    kids, need, step = E3.fut_children(t5)
    assert (need, step) == (3, pd.Timedelta(minutes=5)) and int(kids[day + LVOL.OPEN]) == 3 and len(kids) == 3
    t1 = [day + LVOL.OPEN + pd.Timedelta(minutes=j) for j in range(30) if j != 7]
    kids1, need1, step1 = E3.fut_children(t1)
    assert (need1, step1) == (15, pd.Timedelta(minutes=1)) and int(kids1[day + LVOL.OPEN]) == 14   # 1M FUT ⇒ 15 children, not 3
    kids15, need15, _ = E3.fut_children([day + LVOL.OPEN + pd.Timedelta(minutes=15 * j) for j in range(4)])
    assert need15 == 1 and (kids15 == 1).all()


def _bars_from_highs(hi, lows=None):
    """lows = {bar: low} overrides (e.g. a swing low below the band that existed BEFORE a later down break — Z-1s: it must be passed)."""
    from facts import validity as FV
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    for i, v in (lows or {}).items():
        lo[i] = v
        cl[i] = v + 0.4                                                     # a REAL swing low: its candle closes down there too (Abhi Z-1y)
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    return FV.bars_of(pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl}))


def test_band_flip_facts_flipped_then_broken_then_reclaimed_stays_flipped_not_dead():
    """Re-review: flip (26, the first swing after the up break confirmed) → break down (36; a swing low 90 below the band existed before
    that break ⇒ it must be PASSED, Z-1s; 92.8 never reaches it) → back above the band (up break 42 = reclaim) → rally past 104 ⇒ the
    engine keeps FLIPPED demand + a sweep (Levels._step_far_swing reclaim) — never DEAD, never a second flip."""
    hi = [96.5, 97.0, 96.0, 97.5, 96.5, 97.2, 96.0, 97.4, 96.4, 97.0] * 2
    hi += [100.5, 101.5, 102.5, 103.0, 104.0, 103.0, 102.0, 101.5, 102.5, 103.5, 105.0, 104.5]
    hi += [103.0, 101.0, 99.0, 97.5, 95.5, 94.5, 93.8, 94.5, 96.0, 97.8, 99.5, 101.5, 103.0, 104.0, 105.5]
    B = _bars_from_highs(hi, {5: 90.0})
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 20, "dir": "up"}, {"bar": 36, "dir": "down"}, {"bar": 42, "dir": "up"}]}
    mid = LV.band_flip_facts(B, 41, x, start=0)
    assert mid["flip_state"] == FL.BROKEN and mid["flipped_at"]["bar"] == 26 and mid["broken_at"]["bar"] == 36
    assert mid["far_swing"]["source"] == "before_break" and mid["far_swing"]["price"] == 90.0
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flip_state"] == FL.FLIPPED and f["flipped_at"]["bar"] == 26 and f["dead_at"] is None
    assert [w["bar"] for w in f["sweeps"]] == [42]
    lab = LV.band_label({**f, "role": "support", "lo": 95.0, "hi": 98.0, "touch_count": 2, "valid": True})
    assert "flipped" in lab and "swept" in lab and "dead" not in lab


def test_band_flip_facts_never_flipped_break_then_reclaim_is_active_with_a_sweep():
    """Re-review: a support band 95–98 never flipped, broken down (37); a swing low 90 below the band existed before the break (bar 5) ⇒
    it must be PASSED (Z-1s), the later low 93 @ 39 does not flip it; price back above the band (up break 44 = reclaim) and on to new
    highs ⇒ ACTIVE + sweep (role kept) — not FLIPPED."""
    hi = [101.0, 101.5, 100.8, 101.6, 101.2, 100.9, 101.4, 101.0, 100.7, 101.3] * 3
    hi += [101.0, 100.6, 100.4, 100.2, 100.0, 99.5, 97.5, 95.5, 94.5, 94.0, 95.0, 96.5, 97.5, 98.5, 99.8, 101.0, 103.0]
    B = _bars_from_highs(hi, {5: 90.0})
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 37, "dir": "down"}, {"bar": 44, "dir": "up"}]}
    mid = LV.band_flip_facts(B, 43, x, start=0)
    assert mid["flip_state"] == FL.BROKEN and mid["far_swing"]["bar"] == 5 and mid["far_swing"]["source"] == "before_break"
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flip_state"] == FL.ACTIVE and f["flipped_at"] is None and [w["bar"] for w in f["sweeps"]] == [44]
    lab = LV.band_label({**f, "role": "support", "lo": 95.0, "hi": 98.0, "touch_count": 2, "valid": True})
    assert "swept" in lab and "flipped" not in lab


def test_band_flip_facts_far_swing_passed_on_the_reclaim_bar_flips_first_like_the_engine():
    """Re-review (6153269): the engine checks the far swing before a reclaim on every bar. A support 95–98 broken down (37), far swing
    = the swing low 93 that existed before the break (bar 5; must be passed, Z-1s); bar 44 wicks to 92.0 (past 93) and closes back above
    the band (the band check's up break) ⇒ FLIPPED at 44 (not a reclaim sweep), and the up break at 44 is against the new resistance
    role ⇒ BROKEN with the flip kept."""
    from facts import validity as FV
    hi = [101.0, 101.5, 100.8, 101.6, 101.2, 100.9, 101.4, 101.0, 100.7, 101.3] * 3
    hi += [101.0, 100.6, 100.4, 100.2, 100.0, 99.5, 97.5, 95.5, 94.5, 94.0, 95.0, 96.5, 97.5, 98.5, 99.8, 101.0, 103.0]
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    lo[44], cl[44] = 92.0, 99.5                                            # reclaim bar trades past the far swing first
    lo[5], cl[5] = 93.0, 93.4                                              # a REAL swing low below the band before the break (Z-1y)
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    B = FV.bars_of(pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl}))
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 37, "dir": "down"}, {"bar": 44, "dir": "up"}]}
    f = LV.band_flip_facts(B, 44, x, start=0)
    assert f["flipped_at"]["bar"] == 44 and f["sweeps"] == []
    assert f["flip_state"] == FL.BROKEN and f["broken_at"]["bar"] == 44
    end = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert end["flip_state"] in (FL.BROKEN, FL.DEAD) and end["flip_state"] != FL.ACTIVE and end["sweeps"] == []


def test_band_flip_facts_reclaim_to_flipped_restores_the_flip_facts():
    hi = [96.5, 97.0, 96.0, 97.5, 96.5, 97.2, 96.0, 97.4, 96.4, 97.0] * 2
    hi += [100.5, 101.5, 102.5, 103.0, 104.0, 103.0, 102.0, 101.5, 102.5, 103.5, 105.0, 104.5]
    hi += [103.0, 101.0, 99.0, 97.5, 95.5, 94.5, 93.8, 94.5, 96.0, 97.8, 99.5, 101.5, 103.0, 104.0, 105.5]
    B = _bars_from_highs(hi, {5: 90.0})                                      # a swing below the band before the down break (Z-1s)
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 20, "dir": "up"}]}
    flip = LV.band_flip_facts(B, 35, x, start=0)
    f = LV.band_flip_facts(B, len(hi) - 1, {**x, "breaks": x["breaks"] + [{"bar": 36, "dir": "down"}, {"bar": 42, "dir": "up"}]},
                           start=0)
    assert f["flip_state"] == FL.FLIPPED and f["broken_at"] == flip["broken_at"] and f["far_swing"] == flip["far_swing"]


def test_band_flip_facts_flip_bar_is_never_also_the_dead_bar():
    """Re-review (9bc7524): an outside reclaim bar that passes the far swing (flip) and, with its other extreme, the new break's far
    swing must not flip AND die on the same bar — the engine returns right after a flip (no double-counting of one bar)."""
    from facts import validity as FV
    hi = [101.0, 101.5, 100.8, 101.6, 101.2, 100.9, 101.4, 101.0, 100.7, 101.3] * 3
    hi += [101.0, 100.6, 100.4, 100.2, 100.0, 99.5, 97.5, 95.5, 94.5, 94.0, 95.0, 96.5, 97.5, 98.5, 102.5, 99.6, 99.6, 99.6]
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    lo[44], cl[44] = 92.0, 99.5                                            # outside bar: past 93 (flip) and above every earlier high
    lo[5], cl[5] = 93.0, 93.4                                              # a REAL swing low below the band before the break (Z-1s / Z-1y)
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    B = FV.bars_of(pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl}))
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 37, "dir": "down"}, {"bar": 44, "dir": "up"}]}
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flipped_at"]["bar"] == 44 and f["flip_state"] == FL.BROKEN and f["dead_at"] is None


def test_real_12_oct_third_touch_reads_as_confluence_line(real):
    """Abhi (layer 4 B, golden third-touch case): on 12 Oct the reaction rose out of the 1H supply and turned at the descending line
    short of it at 09:15 — the closest approach since the line's previous touch, no close beyond, then away. That is a touch; the area
    and the line meet there ⇒ the supply is labelled "confluence: line" (the same band, never a new one)."""
    from decision3 import trendline as TL
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-12")
    lvl = _zone_level(V, ix[0])
    t = ix[1]                                                              # 09:30 — the 09:15 turn is a confirmed swing by now
    _, _, act = V.step2(t, "DOWN")
    got = next(x for x in act if x["id"] == lvl["id"])
    assert got.get("confluence_line") is True and got["confluence_label"].endswith("line") and "tl" in got["births"]
    assert (got["lo"], got["hi"]) == (lvl["lo"], lvl["hi"])                # the area itself, never a new band
    rt = got["line_touch"]
    assert str(V.levels.ts.iloc[rt["bar"]])[:16] == "2026-10-12 09:15" and rt["price"] > lvl["hi"]
    ln = TL.swing_line(V, t, M.DOWN)
    assert rt["price"] < ln["p1"][1] + ln["slope"] * (rt["bar"] - ln["p1"][0])   # it turned short of the line: a reaction, not a wick touch


def test_real_12_oct_rsi_read_one_degree_below_the_zone(real):
    """Abhi L5-a on the golden case (reported, not tuned): at the 1H zone (D2) the pushes of the move into it are read at D1. On 12 Oct
    the D1 / D2 highs before the 09:15 high are higher (7 Oct) ⇒ no divergence at D1 or D2; the D0 pair Abhi read (9 Oct 14:15 push high
    → 12 Oct 09:15, RSI lower) exists only at D0 — kept in the history, not the evidence (OPEN_QUESTIONS L5-a)."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-12")
    r = V.decide(ix[1])
    rd = r["zone_read"]["summary"]["rsi_divergence"]
    assert rd["degree"] == 1 and rd["found"] is False and rd["zone_degree"] == []
    assert any("D1" in x and "lower high" in x for x in rd["statements"])
    d0 = [x for x in V._rsi.history(ix[1]) if x["degree"] == 0 and x["side"] == "bear" and str(x["L2"]["time"])[:16] == "2026-10-12 09:15"]
    assert d0 and str(d0[0]["L1"]["time"])[:16] == "2026-10-09 14:15" and d0[0]["L2"]["rsi"] < d0[0]["L1"]["rsi"]


def test_real_12_oct_method_verdict_and_label(real):
    """Layer 6a (method §4 / §5) on the golden case: 12 Oct 09:30 = setup on the required set, label A because confirming evidence is
    present (confluence: line; the RSI divergence Abhi read is D0 — not the evidence under L5-a, still A); the evidence is listed, never scored; a wait carries no label."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-12")
    r915, r930 = V.decide(ix[0]), V.decide(ix[1])
    assert r930["decision"] == "setup" and r930["verdict_rule"] == "method" and r930["conv_score"] is None
    assert r930["evidence_list"]["required"] == "present" and r930["conviction"] == "A"
    assert r930["confirming"]["rsi_divergence"] is False and r930["confirming"]["confluence"] is True
    assert r915["decision"] == "wait" and r915["conviction"] is None
