"""थर v2.2 ⑤ — K ची आतली रेघ: फक्त confirmed बिंदू (known_at), ≥ 2 स्पर्श, trend-दिशेचा close-break ⇒ grade (gate नाही), आरसा, NA."""
from types import SimpleNamespace as NS

import numpy as np
import pytest

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


@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
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


@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
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
    hi = np.array([f(h) for h in highs])
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
    Abhi L4-g (2): the touch is the reaction's own turn (the closest approach since the previous touch) — an earlier closer turn is the
    touch, and a later turn that stays away does not remove it. A close beyond, or a turn that never left the area ⇒ no confluence.
    L4-g (1): the touch number (anchors 1, 2; this reaction 3 — an opposite swing lies between) is information. Mirror."""
    for mirror in (False, True):
        d = TL.UP if mirror else TL.DOWN
        highs = [100.5] * 20
        highs[14] = 104.0                                                   # line at bar 14 = 106 ⇒ turns 2 short of it
        piv = [("L", 99.0, 12, 13), ("H", 104.0, 14, 16)]
        V, ln, f = _rt_V(highs, piv, mirror)
        area = {"id": 7, "lo": min(f(98.0), f(102.0)), "hi": max(f(98.0), f(102.0)), "births": ["a:D2"]}
        far = {**area, "id": 8, "lo": min(f(90.0), f(94.0)), "hi": max(f(90.0), f(94.0))}
        rt = TL.reaction_touch(V, 17, d, ln)
        assert rt == {"bar": 14, "price": f(104.0), "leg_from": 12, "touch_no": 3, "trade_location": True}
        assert [x["id"] for x in TL.areas_out_of(V, rt, d, [area, far])] == [7]
        assert TL._labelled(area, ln, rt)["confluence_label"] == "confluence: line (touch 3)"
        assert TL._labelled(area, ln, None)["confluence_label"] == "confluence: line"
        assert TL._labelled({**area, "confluence_label": "confluence: Daily 1–2"}, ln, rt)["confluence_label"] == \
            "confluence: Daily 1–2; line (touch 3)"
        assert TL.reaction_touch(V, 15, d, ln) is None                      # not yet confirmed (the move has not gone away)
        V2, ln2, _ = _rt_V(highs, [("H", 107.5, 11, 12), ("L", 99.0, 12, 13), ("H", 104.0, 14, 16)], mirror)   # an earlier turn came
        assert TL.reaction_touch(V2, 17, d, ln2)["bar"] == 14               # bar 11 (closer) belongs to the reaction before the low at 12:
                                                                            # this reaction's own turn is 14 (L4-g: one reaction per swing)
        V6, ln6, _ = _rt_V(highs, [("H", 109.5, 11, 12), ("L", 99.0, 12, 13), ("H", 104.0, 14, 16)], mirror)   # bar 11 reached the
        assert TL.reaction_touch(V6, 17, d, ln6)["bar"] == 14               # line (109.5 ≥ 109) ⇒ a new previous touch; 14 is then the closest
        V3, ln3, _ = _rt_V(highs, piv, mirror)
        V3.levels.A["close"][13] = f(108.0)                                 # a close beyond the line (107 at bar 13)
        assert TL.reaction_touch(V3, 17, d, ln3) is None
        V4, ln4, _ = _rt_V(highs, piv + [("H", 100.0, 17, 18)], mirror)    # a later turn that stays away (3 short) does not remove the
        assert TL.reaction_touch(V4, 18, d, ln4)["bar"] == 14               # touch (Abhi L4-g 2)
        V7, ln7, _ = _rt_V(highs, piv, mirror)
        V7.levels.A["close"][16] = f(105.0)                                 # after the turn, a close beyond the line (104 at bar 16)
        assert TL.reaction_touch(V7, 17, d, ln7) is None                    # ⇒ price has gone through; the meeting is over
        h5 = list(highs); h5[14] = 101.5                                    # the turn stays inside the area ⇒ it never rose out of it
        V5, ln5, _ = _rt_V(h5, [("L", 99.0, 12, 13), ("H", 101.5, 14, 16)], mirror)
        assert TL.areas_out_of(V5, TL.reaction_touch(V5, 17, d, ln5), d, [area]) == []


def test_touches_are_counted_by_reactions_not_contacts():
    """Abhi L4-g (1): contacts with no real opposite swing of the line's structure between them are one touch. A line of highs 120 → 110
    (bars 0 → 10): wick contacts at 11 and 12 with no swing low between ⇒ one touch with anchor 10; a low at 14, then a contact at 16 ⇒
    a new touch (the third). Mirror."""
    for mirror in (False, True):
        f = (lambda x: 200.0 - x) if mirror else (lambda x: float(x))        # noqa: E731
        kind, opp = ("L", "H") if mirror else ("H", "L")
        n = 18
        c = np.full(n, f(100.0))
        A = {"open": c.copy(), "close": c.copy(), "high": np.full(n, f(100.5)), "low": np.full(n, f(99.5))}
        if mirror:
            A["high"], A["low"] = np.full(n, 100.5), np.full(n, 99.5)
        for b in (0, 10, 11, 12, 16):
            y = 120.0 - b
            if mirror:
                A["low"][b] = f(y + 0.2)
            else:
                A["high"][b] = y + 0.2
        line = (lambda b: f(120.0 - b))                                     # noqa: E731
        known = [NS(kind=opp, price=f(95.0), bar=5), NS(kind=opp, price=f(96.0), bar=14)]
        g = TL.touch_groups(A, known, kind, line, 0, 10, 17)
        assert g == [[0], [10, 11, 12], [16]]


def test_reactions_are_split_by_the_lines_structure_and_counted():
    """Abhi L4-g with the line's own structure (D2, `known_pivots`) apart from the finest turns: a reaction out of the area turns at 14
    (touch 3); a structure low at 20 starts a new reaction, which turns at 30 ⇒ touch 4, and the touch / label move to it — the bar-14
    touch is history even when the new turn stays farther from the line (a later visit). Within one reaction, a later turn that stays
    away keeps the earlier, closer one. Mirror."""
    for mirror in (False, True):
        f = (lambda x: 200.0 - x) if mirror else (lambda x: float(x))       # noqa: E731
        kind, opp = ("L", "H") if mirror else ("H", "L")
        d = TL.UP if mirror else TL.DOWN
        n = 40
        for h30, h33 in ((116.0, None), (113.0, None), (113.0, 111.0)):
            c = np.full(n, f(100.0))
            hi, lo = np.full(n, 100.5), np.full(n, 99.5)
            hi[0], hi[10], hi[14], hi[30], lo[20] = 120.0, 119.0, 116.6, h30, 90.0
            if h33:
                hi[33] = h33
            H, L = ([f(x) for x in lo], [f(x) for x in hi]) if mirror else (hi, lo)
            A = {"open": c.copy(), "close": c.copy(), "high": np.array(H), "low": np.array(L)}
            k0 = [NS(kind=opp, price=f(99.0), bar=12, confirm_bar=13), NS(kind=kind, price=f(116.6), bar=14, confirm_bar=16),
                  NS(kind=opp, price=f(90.0), bar=20, confirm_bar=22), NS(kind=kind, price=f(h30), bar=30, confirm_bar=32)]
            if h33:
                k0.append(NS(kind=kind, price=f(h33), bar=33, confirm_bar=35))
            d2 = [NS(kind=kind, price=f(120.0), bar=0), NS(kind=opp, price=f(95.0), bar=5), NS(kind=kind, price=f(119.0), bar=10),
                  NS(kind=opp, price=f(99.0), bar=12), NS(kind=opp, price=f(90.0), bar=20)]
            area = {"id": 7, "lo": min(f(98.0), f(102.0)), "hi": max(f(98.0), f(102.0)), "role": "support" if mirror else "resistance"}
            lv = NS(A=A, _known0=k0, known_pivots=lambda t, d2=d2: d2, snapshot=lambda t, a=area: [a])
            V = NS(levels=lv, s={"line_rule": "logic"})
            line = (lambda b: f(120.0 - 0.1 * b))                           # noqa: E731
            g = TL.touch_groups(A, d2, kind, line, 0, 10, 36)
            ln = {"p1": [0, f(120.0)], "p2": [10, f(119.0)], "slope": -0.1 if not mirror else 0.1, "touch_groups": g}
            assert g == [[0], [10]]
            r17 = TL.reaction_touch(V, 17, d, ln)
            assert r17["bar"] == 14 and r17["touch_no"] == 3 and r17["trade_location"] is True
            assert TL.reaction_touch(V, 25, d, ln) is None                  # the low at 20 ended that reaction; no new turn yet
            r = TL.reaction_touch(V, 36, d, ln)
            assert r["bar"] == 30 and r["touch_no"] == 4                    # the new reaction (a later visit) is the touch now

