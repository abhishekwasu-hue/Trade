"""थर v2.2 ⑤ — K ची आतली रेघ: फक्त confirmed बिंदू (known_at), ≥ 2 स्पर्श, trend-दिशेचा close-break ⇒ grade (gate नाही), आरसा, NA."""
from types import SimpleNamespace as NS

import numpy as np

from decision3 import settings as S3
from decision3 import trendline as TL

S = S3.load()


def _V(closes, pivots):
    c = np.array(closes, float)
    A = {"open": c, "high": c + 0.2, "low": c - 0.2, "close": c}
    return NS(s=S, levels=NS(A=A, sig1h=np.full(len(c), 10.0)), res={"pivots": {1: pivots}})


def _K(i_end, i_end_bar):
    return {"open": True, "i_end": i_end, "i_end_bar": i_end_bar}


# DOWN trend (bear call): K वर चढते; रेघ = I_end low 100 (bar 2) + L 103 (bar 6, confirm 8) ⇒ slope 0.75 / bar
CL = [110, 104, 100, 102, 104, 105, 103, 104.5, 106, 107, 108, 109, 107.0, 106]
PIV = [NS(kind="L", price=103.0, bar=6, confirm_bar=8), NS(kind="H", price=105.0, bar=5, confirm_bar=7)]


def test_line_only_after_second_point_confirmed():
    V = _V(CL, PIV)
    assert TL.k_line(V, 7, TL.DOWN, _K(100.0, 2)) is None                         # bar 7: L 103 अजून confirm नाही ⇒ रेघ नाही
    tl = TL.k_line(V, 8, TL.DOWN, _K(100.0, 2))
    assert tl and tl["touches"] >= 2 and tl["slope"] > 0 and not tl["broken"]


def test_break_by_close_in_trend_direction():
    V = _V(CL, PIV)
    tl11 = TL.k_line(V, 11, TL.DOWN, _K(100.0, 2))
    assert not tl11["broken"]                                                     # bar 11: close 109 > रेघ 106.75
    tl12 = TL.k_line(V, 12, TL.DOWN, _K(100.0, 2))
    assert tl12["broken"] and tl12["break_bar"] == 12                            # bar 12: close 107 < रेघ 107.5


def test_mirror_up_trend():
    cl = [200 - (x - 100) for x in CL]
    piv = [NS(kind="H", price=197.0, bar=6, confirm_bar=8), NS(kind="L", price=195.0, bar=5, confirm_bar=7)]   # mirror of PIV
    V = _V(cl, piv)
    assert not TL.k_line(V, 11, TL.UP, _K(200.0, 2))["broken"]
    tl = TL.k_line(V, 12, TL.UP, _K(200.0, 2))
    assert tl["broken"] and tl["slope"] < 0


def test_only_the_commitment_candle_closing_through_is_the_break():
    """Method §3 trigger form + K6.5 (line_rule = logic): the correction's own line triggers when bar t (the commitment candle) closes
    through it. Before t the line is gone only by a close beyond AND a swing formed beyond (broken_before); a close that came back is a
    throw-over and the line still stands; bar t merely staying beyond is not a new close through. Line here: 100 + 0.75 / bar from bar 2."""
    for mirror in (False, True):
        f = (lambda x: 200 - (x - 100)) if mirror else (lambda x: x)        # noqa: E731
        d, kind, opp = (TL.UP, "H", "L") if mirror else (TL.DOWN, "L", "H")
        piv = [NS(kind=kind, price=f(103.0), bar=6, confirm_bar=8), NS(kind=opp, price=f(105.0), bar=5, confirm_bar=7)]
        k = _K(f(100.0), 2)
        V = _V([f(x) for x in CL], piv)
        assert V.s["line_rule"] == "logic" and TL.k_line(V, 12, d, k)["broken"] is True   # bar 12: the first close through
        later = TL.k_line(V, 13, d, k)                                              # bar 13 stays beyond: not a new close through
        assert (later["broken"], later["broken_before"]) == (False, None)
        poke = list(CL)
        poke[10], poke[11] = 105.5, 109.0                                           # bar 10 closes beyond (line 106), bar 11 back
        V = _V([f(x) for x in poke], piv)
        tl = TL.k_line(V, 12, d, k)                                                 # throw-over ⇒ the commitment candle still triggers
        assert (tl["broken"], tl["broken_before"], tl["break_bar"]) == (True, None, 12)
        gone = list(poke)
        gone[10] = 99.2                                                             # a close beyond and a swing beyond (below the
        V = _V([f(x) for x in gone], piv + [NS(kind=kind, price=f(99.0), bar=10, confirm_bar=11)])   # first anchor ⇒ no newer line)
        tl = TL.k_line(V, 12, d, k)
        assert (tl["broken"], tl["broken_before"], tl["break_bar"]) == (False, 10, 10)


def test_one_reaction_is_not_a_line():
    """Method §3: the two anchors must be separate reactions — no swing of the opposite kind between them ⇒ no line (logic)."""
    V = _V(CL, [p for p in PIV if p.kind == "L"])
    assert TL.k_line(V, 12, TL.DOWN, _K(100.0, 2)) is None


def test_no_line_when_points_do_not_follow_k_or_k_closed():
    V = _V(CL, [NS(kind="L", price=99.0, bar=6, confirm_bar=8)])                # दुसरा low खाली ⇒ K ची रेघ नाही
    assert TL.k_line(V, 12, TL.DOWN, _K(100.0, 2)) is None
    assert TL.k_line(_V(CL, PIV), 12, TL.DOWN, {"open": False, "i_end": 100.0, "i_end_bar": 2}) is None


def test_tl_break_is_evidence_not_gate():
    w = S["evidence_weights"]
    assert w["tl_break"] > 0
    from decision3 import method as M
    ev = {k: False for k in w}
    ev.update(power_shift=True, trap_sweep=True, commit_strong=True, second_attempt=True, level_star=True)
    a = M.conviction({**ev, "tl_break": None}, S)
    b = M.conviction({**ev, "tl_break": False}, S)
    assert a[1] >= b[1]                                                          # NA बेरजेत नाही; अखंड रेघ फक्त grade कमी, नकार नाही
    assert M.conviction({**ev, "tl_break": True}, S)[1] >= a[1]


def test_broken_by_names_the_close_that_began_the_excursion_the_swing_confirmed():
    """K6.5: poke beyond, back, then a close beyond that a swing beyond confirms ⇒ the break is that second close (not the earlier
    throw-over); no swing beyond ⇒ never broken. Mirror (side −1)."""
    for side in (1, -1):
        f = (lambda x: 100 + side * (x - 100))                                  # noqa: E731
        A = {"close": np.array([f(x) for x in (99, 101, 99, 101, 102, 99.0)])}
        piv = [NS(kind="H" if side > 0 else "L", price=f(103.0), bar=4)]
        assert TL.broken_by(A, piv, piv[0].kind, lambda b: 100.0, side, 0, 5) == 3
        assert TL.broken_by(A, [], piv[0].kind, lambda b: 100.0, side, 0, 5) is None


def _rt_V(highs, pivots, mirror):
    """A line of highs 120 → 110 (bars 0 → 10, −1 / bar); closes 100. Mirror: a line of lows (200 − x)."""
    f = (lambda x: 200.0 - x) if mirror else (lambda x: float(x))
    n = 20
    c = np.full(n, f(100.0))
    hi = np.array([f(h) for h in highs]) if not mirror else np.full(n, f(100.5))
    lo = np.full(n, f(99.5)) if not mirror else np.array([f(h) for h in highs])
    A = {"open": c.copy(), "close": c.copy(), "high": np.maximum(hi, c) if not mirror else np.full(n, f(99.5)),
         "low": np.minimum(lo, c) if mirror else np.full(n, f(99.5))}
    if mirror:
        A["high"] = np.full(n, 100.5)
    lv = NS(A=A, _known0=[NS(kind=("L" if k == "H" else "H") if mirror else k, price=f(p), bar=b, confirm_bar=cb) for k, p, b, cb in pivots])
    ln = {"p1": [0, f(120.0)], "p2": [10, f(110.0)], "slope": -1.0 if not mirror else 1.0}
    return NS(levels=lv), ln, f


def test_a_reaction_rising_out_of_an_area_and_turning_at_the_line_is_a_touch():
    """Abhi (layer 4 B): the reaction rises out of the area (98–102), turns at the line short of it — the closest approach since the
    previous touch, no close beyond — and goes away (the swing is confirmed) ⇒ a touch; that area is labelled "confluence: line".
    An earlier closer turn, a close beyond, a later turn, or a turn that never left the area ⇒ no reaction touch. Mirror."""
    for mirror in (False, True):
        d = TL.UP if mirror else TL.DOWN
        highs = [100.5] * 20
        highs[14] = 104.0                                                   # line at bar 14 = 106 ⇒ turns 2 short of it
        piv = [("L", 99.0, 12, 13), ("H", 104.0, 14, 16)]
        V, ln, f = _rt_V(highs, piv, mirror)
        area = {"id": 7, "lo": min(f(98.0), f(102.0)), "hi": max(f(98.0), f(102.0)), "births": ["a:D2"]}
        far = {**area, "id": 8, "lo": min(f(90.0), f(94.0)), "hi": max(f(90.0), f(94.0))}
        rt = TL.reaction_touch(V, 17, d, ln)
        assert rt == {"bar": 14, "price": f(104.0), "leg_from": 12}
        assert [x["id"] for x in TL.areas_out_of(V, rt, d, [area, far])] == [7]
        assert TL._labelled(area, ln, rt)["confluence_label"] == "confluence: line"
        assert TL._labelled({**area, "confluence_label": "confluence: Daily 1–2"}, ln, rt)["confluence_label"] == "confluence: Daily 1–2; line"
        assert TL.reaction_touch(V, 15, d, ln) is None                      # not yet confirmed (the move has not gone away)
        h2 = list(highs); h2[12] = 105.0                                    # an earlier turn came closer (line 108 at bar 12 ⇒ 3 short)
        V2, ln2, _ = _rt_V(h2, [("H", 107.5, 11, 12), ("L", 99.0, 12, 13), ("H", 104.0, 14, 16)], mirror)
        assert TL.reaction_touch(V2, 17, d, ln2) is None                    # 107.5 at bar 11 (line 109) was 1.5 short — closer
        V3, ln3, _ = _rt_V(highs, piv, mirror)
        V3.levels.A["close"][13] = f(108.0)                                 # a close beyond the line (107 at bar 13)
        assert TL.reaction_touch(V3, 17, d, ln3) is None
        V4, ln4, _ = _rt_V(highs, piv + [("H", 101.0, 17, 18)], mirror)    # a later turn ⇒ the touch has been left behind
        assert TL.reaction_touch(V4, 18, d, ln4) is None
        h5 = list(highs); h5[14] = 101.5                                    # the turn stays inside the area ⇒ it never rose out of it
        V5, ln5, _ = _rt_V(h5, [("L", 99.0, 12, 13), ("H", 101.5, 14, 16)], mirror)
        assert TL.areas_out_of(V5, TL.reaction_touch(V5, 17, d, ln5), d, [area]) == []
