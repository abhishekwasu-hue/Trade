"""PA standard §2H chart patterns + §2K breakout vs fakeout (decision3/patterns_pa.py) — synthetic, both mirrors, no look-ahead.

The builder draws a price path through given swing points (linear closes between them); each swing candle's extreme is the swing price
and its body stops `W` short of it, so its C-13 area (wick to body) is [price − W, price] for a high and mirror for a low.
"""
from types import SimpleNamespace as NS

import numpy as np
import pytest

from decision3 import patterns_pa as PP

W = 1.0          # the swing candle's wick (its C-13 area)
TINY = 0.1       # ordinary candles' wicks


def build(points, n=None, confirm=2):
    """points = [(bar, kind, price)] (kind "H" / "L" / "" for a plain waypoint). Returns (A, pivots)."""
    pts = sorted(points)
    n = max(n or 0, pts[-1][0] + 1)
    if n > pts[-1][0] + 1:                                                 # beyond the last point: retrace a third of the last leg
        (b0, _, y0), (b1, _, y1) = pts[-2], pts[-1]
        pts = pts + [(n - 1, "", y1 - (y1 - y0) / 3.0)]
    bars = [b for b, _, _ in pts]
    mids = np.interp(np.arange(n), bars, [p for _, _, p in pts])
    c = mids.copy()
    for b, k, p in pts:
        if k == "H":
            c[b] = p - W
        elif k == "L":
            c[b] = p + W
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) + TINY
    lo = np.minimum(o, c) - TINY
    for b, k, p in pts:
        if k == "H":
            hi[b] = p
        elif k == "L":
            lo[b] = p
    A = {"open": o, "high": hi, "low": lo, "close": c}
    piv = [NS(kind=k, price=float(p), bar=int(b), confirm_bar=int(b) + confirm) for b, k, p in pts if k]
    return A, piv


def mirror(points, axis=100.0):
    return [(b, {"H": "L", "L": "H", "": ""}[k], 2 * axis - p) for b, k, p in points]


def find(points, t, fam=None, n=None, d=None):
    A, piv = build(points, n=max(n or 0, t + 1))
    out = PP.find_patterns(A, piv, piv, t, tf="1H", d=d)
    return [p for p in out if fam is None or p["family"] == fam]


def one(points, t, fam, n=None, d=None):
    xs = find(points, t, fam, n=n, d=d)
    assert xs, f"{fam} not found at t={t}: {[p['family'] for p in find(points, t, n=n)]}"
    return xs[0]


# ------------------------------------------------------------------------------------------------ §2K breakout vs fakeout
def _flat(cl):
    c = np.array(cl, float)
    return {"open": np.r_[c[0], c[:-1]], "high": np.maximum(np.r_[c[0], c[:-1]], c) + 0.2, "low": np.minimum(np.r_[c[0], c[:-1]], c) - 0.2,
            "close": c}


def test_breakout_accepted_needs_close_and_swing_beyond_then_retest():
    for m in (1, -1):
        f = (lambda x: 100 + m * (x - 100))                                # noqa: E731
        cl = [f(x) for x in [98, 99, 99.5, 101, 103, 104, 103, 101.5, 100.1, 101, 103]]
        A = _flat(cl)
        kind = "H" if m > 0 else "L"
        piv = [NS(kind=kind, price=f(104.2), bar=5, confirm_bar=7)]
        line = lambda b: 100.0                                             # noqa: E731
        assert PP.breakout_state(A, piv, line, m, 0, 4)["state"] == "beyond"     # closed beyond, no swing yet
        assert PP.breakout_state(A, piv, line, m, 0, 6)["state"] == "beyond"     # swing at 5 not confirmed until 7 (no look-ahead)
        st = PP.breakout_state(A, piv, line, m, 0, 7)
        assert st["state"] == "accepted" and st["accepted_bar"] == 7 and st["first_close"] == 3
        # bar 8: wick back to 100 (low 99.9 / mirror), body stays beyond ⇒ retest
        A["low" if m > 0 else "high"][8] = 100 - m * 0.1
        st = PP.breakout_state(A, piv, line, m, 0, 9)
        assert st["state"] == "retested" and st["retests"][0] == 8 and st["outcome"] == "breakout"


def test_fakeout_close_back_inside_before_any_swing_and_sweep():
    for m in (1, -1):
        f = (lambda x: 100 + m * (x - 100))                                # noqa: E731
        A = _flat([f(x) for x in [98, 99, 100.5, 99.0, 98.5, 98.0]])
        st = PP.breakout_state(A, [], lambda b: 100.0, m, 0, 5)
        assert st["state"] == "fakeout" and st["fakeouts"] == [[2, 3]] and st["outcome"] == "fakeout"
        A = _flat([f(x) for x in [98, 99, 99.5, 99.0, 98.5]])
        A["high" if m > 0 else "low"][3] = f(100.6)                        # wick beyond, close inside
        st = PP.breakout_state(A, [], lambda b: 100.0, m, 0, 4)
        assert st["state"] == "sweep" and st["sweeps"] == [3]


def test_failed_after_acceptance_is_reclaim_close_and_swing_inside():
    for m in (1, -1):
        f = (lambda x: 100 + m * (x - 100))                                # noqa: E731
        cl = [f(x) for x in [98, 101, 103, 102, 99, 97, 96, 98]]
        A = _flat(cl)
        hk, lk = ("H", "L") if m > 0 else ("L", "H")
        piv = [NS(kind=hk, price=f(103.2), bar=2, confirm_bar=3), NS(kind=lk, price=f(95.8), bar=6, confirm_bar=7)]
        line = lambda b: 100.0                                             # noqa: E731
        assert PP.breakout_state(A, piv, line, m, 0, 5)["state"] == "accepted"   # closes back inside (bar 4) but no swing inside yet
        st = PP.breakout_state(A, piv, line, m, 0, 7)
        assert st["state"] == "failed" and st["failed_bar"] == 7 and st["outcome"] == "fakeout"


def test_level_breakout_band_edges():
    A = _flat([98, 99, 101, 103, 104, 102])
    piv = [NS(kind="H", price=104.2, bar=4, confirm_bar=5)]
    assert PP.level_breakout(A, piv, 99.5, 100.0, 1, 0, 5)["state"] == "accepted"
    assert PP.level_breakout(A, piv, 99.5, 100.0, -1, 3, 5)["state"] == "inside"


# ------------------------------------------------------------------------------------------------ double / triple top-bottom
DT = [(0, "L", 80), (6, "H", 110), (12, "L", 95), (18, "H", 109.5)]       # H2 in H1's area (109–110), N 95 well above L0 80


@pytest.mark.parametrize("mir", [False, True])
def test_double_top_named_only_after_neckline_close_then_broken_retested(mir):
    pts = DT + [(21, "", 100), (26, "L", 90), (30, "H", 95.5), (34, "L", 85)]
    if mir:
        pts = mirror(pts)
    fam = "double_bottom" if mir else "double_top"
    p = one(pts, 20, fam)                                                  # bar 20: H2 confirmed, close still above the neckline
    assert p["state"] == "forming" and not p["named"] and p["evidence"] is None
    assert p["lines"][0]["p0"][1] == (105.0 if mir else 95.0)
    p = one(pts, 25, fam)                                                  # bar 24 closes below 95; the swing at 26 not known yet
    assert p["state"] == "complete" and p["named"]
    p = one(pts, 28, fam)                                                  # the swing beyond (L 90 at 26) confirmed at 28
    assert p["state"] == "broken"
    p = one(pts, 33, fam)                                                  # H 95.5 at 30: wick to the neckline, body below
    assert p["state"] == "retested" and p["boundaries"]["neckline"]["retests"]
    assert p["bias"] == (1 if mir else -1)


@pytest.mark.parametrize("mir", [False, True])
def test_double_top_neckline_fakeout_cancels_name(mir):
    pts = DT + [(21, "", 96), (22, "", 94), (24, "", 99), (27, "", 103)]
    if mir:
        pts = mirror(pts)
    p = one(pts, 27, "double_bottom" if mir else "double_top")
    assert p["state"] == "failed" and "false break" in p["why"]


@pytest.mark.parametrize("mir", [False, True])
def test_double_top_acceptance_beyond_tops_is_continuation(mir):
    pts = DT + [(21, "L", 104), (25, "", 112), (27, "H", 116), (31, "L", 111)]   # a low between the tops and the new high
    if mir:
        pts = mirror(pts)
    p = one(pts, 30, "double_bottom" if mir else "double_top")
    assert p["state"] == "failed" and "continuation" in p["why"]


def test_not_double_when_second_top_beyond_or_short_or_no_prior_rise():
    assert not find([(0, "L", 80), (6, "H", 110), (12, "L", 95), (18, "H", 111)], 20, "double_top")     # HH
    assert not find([(0, "L", 80), (6, "H", 110), (12, "L", 95), (18, "H", 107)], 20, "double_top")     # LH (short of the area)
    assert not find([(0, "L", 95.5), (6, "H", 110), (12, "L", 95), (18, "H", 109.5)], 20, "double_top")  # N in L0's area ⇒ range


@pytest.mark.parametrize("mir", [False, True])
def test_triple_top_neckline_is_the_lower_trough(mir):
    pts = [(0, "L", 80), (6, "H", 110), (12, "L", 96), (18, "H", 109.4), (24, "L", 94), (30, "H", 109.6)]
    if mir:
        pts = mirror(pts)
    p = one(pts, 32, "triple_bottom" if mir else "triple_top")
    assert p["lines"][0]["p0"][1] == (106.0 if mir else 94.0) and p["state"] == "forming"
    assert all(q["end_bar"] != 30 for q in find(pts, 32, "double_bottom" if mir else "double_top"))   # the triple wins at its end


# ------------------------------------------------------------------------------------------------ head & shoulders
HS = [(0, "L", 80), (6, "H", 105), (12, "L", 95), (18, "H", 115), (24, "L", 96), (30, "H", 104)]


@pytest.mark.parametrize("mir", [False, True])
def test_head_and_shoulders_and_inverse(mir):
    pts = HS + [(34, "", 93), (37, "L", 88)]
    if mir:
        pts = mirror(pts)
    fam = "hs_bottom" if mir else "hs_top"
    p = one(pts, 32, fam)
    assert p["state"] == "forming" and p["bias"] == (1 if mir else -1)
    nl = p["lines"][0]
    assert nl["p0"] == [12, 105.0 if mir else 95.0] and nl["p1"] == [24, 104.0 if mir else 96.0]   # through the two troughs
    assert one(pts, 35, fam)["state"] == "complete"
    assert one(pts, 39, fam)["state"] == "broken"


def test_hs_needs_head_beyond_and_right_shoulder_short():
    bad = [(0, "L", 80), (6, "H", 105), (12, "L", 95), (18, "H", 115), (24, "L", 96), (30, "H", 114.5)]   # RS in the head's area
    assert not find(bad, 32, "hs_top")
    low_rs = [(0, "L", 80), (6, "H", 105), (12, "L", 100), (18, "H", 115), (24, "L", 92), (30, "H", 98)]   # RS below N1
    assert not find(low_rs, 32, "hs_top")


# ------------------------------------------------------------------------------------------------ triangles / broadening
@pytest.mark.parametrize("mir", [False, True])
def test_symmetrical_triangle_forming_then_complete(mir):
    pts = [(0, "L", 60), (8, "H", 120), (14, "L", 80), (19, "H", 110), (23, "L", 88), (26, "H", 104), (29, "L", 92)]
    if mir:
        pts = mirror(pts)
    p = one(pts, 28, "sym_triangle")                                       # O = 120 high, A..D: 4 legs ⇒ candidate
    assert p["state"] == "forming" and p["facts"]["legs"] == 4
    p = one(pts, 31, "sym_triangle")                                       # E confirmed ⇒ 5 legs ⇒ named
    assert p["state"] == "complete" and p["bias"] == 0
    names = {ln["name"] for ln in p["lines"]}
    assert names == {"upper", "lower"}


@pytest.mark.parametrize("mir", [False, True])
def test_ascending_triangle_flat_top_rising_lows(mir):
    pts = [(0, "L", 50), (8, "H", 101), (14, "L", 80), (19, "H", 100.5), (23, "L", 88), (26, "H", 100.3), (29, "L", 94)]
    if mir:
        pts = mirror(pts)
    fam = "desc_triangle" if mir else "asc_triangle"
    p = one(pts, 31, fam)
    assert p["bias"] == (-1 if mir else 1)
    flat = [ln for ln in p["lines"] if ln["slope"] == 0]
    assert len(flat) == 1 and flat[0]["p0"][1] == (99.5 if mir else 100.5)              # the barrier side, at its first swing


@pytest.mark.parametrize("mir", [False, True])
def test_broadening_expanding_legs(mir):
    pts = [(0, "H", 100), (3, "L", 95), (7, "H", 103), (12, "L", 90), (18, "H", 108), (25, "L", 84)]
    if mir:
        pts = mirror(pts)
    p = one(pts, 27, "broadening")
    assert p["state"] == "complete" and p["role"] is None
    assert one(pts, 27, "broadening", d=1)["role"] == "E"


# ------------------------------------------------------------------------------------------------ wedges
@pytest.mark.parametrize("mir", [False, True])
def test_falling_wedge_needs_5th_push_and_close_beyond_2_4_line(mir):
    pts = [(0, "H", 130), (8, "L", 100), (12, "H", 116), (18, "L", 94), (21, "H", 106), (25, "L", 91), (32, "", 104), (35, "H", 108)]
    if mir:
        pts = mirror(pts)
    fam = "rising_wedge" if mir else "falling_wedge"
    p = one(pts, 24, fam)                                                  # O + W1..W4 ⇒ forming (incomplete wedge)
    assert p["state"] == "forming"
    p = one(pts, 27, fam)                                                  # W5 confirmed, no close beyond the 2–4 line yet
    assert p["state"] == "forming" and p["facts"]["pushes"] == 3
    p = one(pts, 32, fam)                                                  # closes above the 2–4 line (116 → 106, slope −10/9)
    assert p["state"] in ("complete", "broken") and p["bias"] == (-1 if mir else 1)
    assert one(pts, 37, fam)["state"] in ("broken", "retested")


def test_wedge_roles_counter_trend_is_pullback_with_trend_is_warning():
    pts = [(0, "H", 130), (8, "L", 100), (12, "H", 116), (18, "L", 94), (21, "H", 106), (25, "L", 91)]
    assert one(pts, 27, "falling_wedge", d=1)["role"] == "P"
    assert one(pts, 27, "falling_wedge", d=-1)["role"] == "E"


# ------------------------------------------------------------------------------------------------ flags / pennants
@pytest.mark.parametrize("mir", [False, True])
def test_bull_flag_after_pole_that_broke_structure(mir):
    pts = [(0, "H", 100), (4, "L", 90), (12, "H", 130), (15, "L", 122), (18, "H", 127), (21, "L", 119)]
    if mir:
        pts = mirror(pts)
    fam = "bear_flag" if mir else "bull_flag"
    p = one(pts, 23, fam)
    assert p["state"] == "complete" and p["facts"]["pole"] == ([110.0, 70.0] if mir else [90.0, 130.0])
    assert p["role"] is None and one(pts, 23, fam, d=-1 if mir else 1)["role"] == "P"


def test_no_flag_without_structure_break_or_too_deep():
    nob = [(0, "H", 135), (4, "L", 90), (12, "H", 130), (15, "L", 122), (18, "H", 127), (21, "L", 119)]   # pole top below 135
    assert not find(nob, 23, "bull_flag")
    deep = [(0, "H", 100), (4, "L", 90), (12, "H", 130), (15, "L", 112), (18, "H", 127), (21, "L", 89)]    # back past the origin
    assert not find(deep, 23, "bull_flag")


@pytest.mark.parametrize("mir", [False, True])
def test_pennant_converging_after_pole(mir):
    pts = [(0, "H", 100), (4, "L", 90), (12, "H", 130), (15, "L", 118), (18, "H", 127), (21, "L", 121)]
    if mir:
        pts = mirror(pts)
    assert one(pts, 23, "bear_pennant" if mir else "bull_pennant")["state"] == "complete"


# ------------------------------------------------------------------------------------------------ rectangles
@pytest.mark.parametrize("mir", [False, True])
def test_rectangle_equal_highs_and_lows_edges_and_fakeout_keeps_range(mir):
    pts = [(0, "L", 90), (6, "H", 110), (12, "L", 90.5), (18, "H", 109.6), (24, "L", 90.4), (27, "", 100), (30, "", 111.5),
           (31, "", 108), (34, "", 100)]
    if mir:
        pts = mirror(pts)
    p = one(pts, 26, "rectangle")
    assert p["state"] == "complete" and (p["facts"]["touches_high"], p["facts"]["touches_low"]) == ((3, 2) if mir else (2, 3))
    assert p["facts"]["upper_band"] == [109.0, 110.0]        # the first high's C-13 area (edge band)
    edges = sorted(ln["p0"][1] for ln in p["lines"])
    assert edges == [90.0, 110.0]
    p = one(pts, 34, "rectangle")                                          # closed above 110 at 30, back inside at 31, no swing
    assert p["state"] == "complete" and "fakeout" in p["why"]


# ------------------------------------------------------------------------------------------------ no look-ahead, evidence, E4(b) hook
def test_no_look_ahead_unconfirmed_swing_is_not_read():
    pts = DT
    assert not find(pts, 19, "double_top")                                 # H2 at 18 confirms at 20
    assert find(pts, 20, "double_top")


def test_result_at_t_does_not_change_with_future_bars():
    pts = DT + [(21, "", 100), (26, "L", 90), (30, "H", 94.8), (34, "L", 85)]
    A, piv = build(pts)
    full = PP.find_patterns(A, piv, piv, 24)
    cut = {k: v[:25] for k, v in A.items()}
    assert PP.find_patterns(cut, piv, piv, 24) == full


def _V(points, n=None):
    A, piv = build(points, n=n)
    return NS(s={"level_degree": 2}, levels=NS(A=A, ts=None), res={"pivots": {1: piv, 2: piv}, "settings": {"structure_degrees": (1, 2)}})


def test_read_patterns_evidence_only_named_and_retest_levels_hook():
    pts = DT + [(21, "", 100), (26, "L", 90), (30, "H", 95.5), (34, "L", 85)]
    V = _V(pts, n=36)
    r = PP.read_patterns(V, 20, d=1)
    assert r["degree"] == 2 and not r["evidence"] and r["candidates"] and not r["retest_levels"]
    r = PP.read_patterns(V, 33, d=1)
    assert any("double top" in e and "[E]" in e for e in r["evidence"])
    lv = [x for x in r["retest_levels"] if x["pattern"] == "double_top"]
    assert lv and lv[0]["role"] == "resistance" and lv[0]["boundary"] == "neckline" and lv[0]["value_t"] == 95.0
    assert PP.retest_levels(V, 33) == r["retest_levels"]
    assert PP.degree_of(V, "15M") == 1


def test_draw_objects_shape():
    V = _V(DT + [(21, "", 100), (26, "L", 90)], n=29)
    objs = PP.draw_objects(V, 28)
    keys = {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}
    assert objs and all(keys <= set(o) for o in objs)
    assert {o["kind"] for o in objs} >= {"pattern", "pattern_boundary"}


def test_no_numbers_registered():
    from decision3 import settings as S3
    assert not [k for k in S3.DEFAULTS if k.startswith("pa_pattern")]          # the reading needs no new setting


def test_triangle_expires_at_apex_without_a_break():
    pts = [(0, "L", 60), (8, "H", 120), (14, "L", 80), (19, "H", 110), (23, "L", 88), (26, "H", 104), (29, "L", 95), (31, "", 97),
           (33, "", 97.5), (60, "", 97.5)]                                 # lines meet at bar 33; price sits inside them until then
    p = one(pts, 31, "sym_triangle")
    assert p["state"] == "complete"
    assert p["apex_bar"] is not None and p["apex_bar"] > 29
    late = one(pts, 60, "sym_triangle")
    assert late["lines"][0]["until_bar"] == late["apex_bar"] < 60
    assert late["state"] == "failed" and "apex" in late["why"]


def test_candidate_line_break_keeps_the_shape_unnamed():
    """K11.0 / KP4: a forming (4-leg) wedge whose line breaks is still a candidate — its line state is reported, no evidence."""
    pts = [(0, "H", 130), (8, "L", 100), (12, "H", 116), (18, "L", 94), (21, "H", 106), (24, "L", 101), (27, "", 110), (29, "H", 113),
           (33, "L", 108)]                                                 # W4 at 21; the 2–4 line (116 → 106) closed through, swing 113
    V = _V(pts, n=36)
    r = PP.read_patterns(V, 35)
    w = [p for p in r["patterns"] if p["family"] == "falling_wedge"]
    assert w and not w[0]["named"] and w[0]["state"] in ("broken", "retested")
    assert not any("wedge" in e for e in r["evidence"]) and any("wedge" in c for c in r["candidates"])


@pytest.mark.parametrize("mir", [False, True])
def test_neckline_fakeout_stays_cancelled_after_a_later_sweep(mir):
    pts = DT + [(21, "", 96), (22, "", 94), (24, "", 99), (27, "", 103), (30, "", 96), (33, "", 100)]
    if mir:
        pts = mirror(pts)
    A, piv = build(pts, n=36)
    lo = A["low" if not mir else "high"]
    lo[30] = 94.5 if not mir else 105.5                                    # a wick through the neckline later, close inside
    p = [x for x in PP.find_patterns(A, piv, piv, 35) if x["family"] == ("double_bottom" if mir else "double_top")][0]
    assert p["boundaries"]["neckline"]["state"] == "sweep" and p["state"] == "failed" and p["named"]
    assert not PP._retest([p], 35)
