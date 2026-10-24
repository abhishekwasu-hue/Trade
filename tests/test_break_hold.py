"""BREAK-1 (Abhi, owner rule — owner-orders DECISIONS 60 / 61 / 63 / 69; gallery review A1–A4, A8): one lifecycle rule for areas AND
lines, both mirrors, synthetic (CI-safe), on the real readers (decision3/levels.py, decision3/trendline.py, decision3/entry_models.py):

  • BROKEN = a close beyond AND price HOLDS beyond: a swing of the hold side forms on the far side (a pullback LOW above a resistance /
    a line broken up; mirror: a pullback HIGH below) and is confirmed while every close is still beyond — the confirming bar too;
  • SWEEP = beyond and back without holding (the push's own extreme beyond is no hold): the object stays alive ("reclaimed"); reaching
    the far-side swing on such a push is no flip;
  • BROKEN BACK ⇒ DEAD by the same test in the opposite direction (areas as lines — no "reclaim" back to the old role);
  • the E4 (b) approach side allows a sweep: marginal closes on the original side without a swing held there still count as the
    approach from the break side (DECISIONS 61);
  • every state is stamped at the bar it became KNOWN, read with swings confirmed by that bar only (no look-ahead: a cut at any bar
    gives the same states up to it).
`break_hold_rule = swing_beyond` (what-if) = the earlier reading; it is asserted beside each case so the change is visible.
"""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import entry_models as EM
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import settings as S3
from decision3 import trendline as TL
from tests.test_decision3_entry_models import _bare
from tests.test_decision3_zone_answers import P, _mirror, m15_from, res_of

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["resistance_up", "support_down"])
OLD = {"break_hold_rule": "swing_beyond"}
# A resistance 117–118 (a D2 high at 118, bar 8). Bars 17 … 21 close above it (the push high 120.5 at bar 19, confirmed at 21);
# bar 21's low 118.1 stays above the band. Mirror: a support broken down (every price reflected, H ⇄ L).
BASE = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + [114, 116, 118.6, 119.4, 120.2, 119.0, 118.4]
HOLD_TAIL = [119.2, 120.4, 121.5, 122.0]                                   # bars 22 … 25: price stays above
SWEEP_TAIL = [117.0, 115.0, 113.0]                                         # bar 22 closes back inside: the push turned back
PUSH = ("H", 120.5, 19, 21)                                                # the push's own extreme beyond (no hold)
HOLD = ("L", 118.1, 21, 23)                                                # a pullback low formed ABOVE the band (the hold)
# … then back down through the band: bar 28 closes below 117, a pullback high 115.9 forms below it (bar 32, confirmed at 34)
BACK_TAIL = HOLD_TAIL + [120.5, 118.5, 116.0, 115.0, 114.0, 114.8, 115.6, 114.6, 113.5, 112.8]
BACK_HOLD = ("H", 115.9, 32, 34)


def _case(mirror, tail, p1=(), p2=(), s=None):
    f, sw = _mirror(mirror)
    m = m15_from([f(c) for c in BASE + tail], wick=0.3)
    piv1 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16)] + [P(sw(k), f(px), b, c) for k, px, b, c in p1]
    piv2 = [P(sw("H"), f(118), 8, 10)] + [P(sw(k), f(px), b, c) for k, px, b, c in p2]
    lv = LV.Levels(res_of(m, piv2, piv1), s=s)
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    return m, lv, Z


def _ev(Z, kinds=("broken", "flip", "reclaim", "dead")):
    return [(b, k) for b, k, _ in Z.events if k in kinds]


def test_break_hold_rule_is_registered_default_and_checked():
    assert S3.DEFAULTS["break_hold_rule"] == S3.REGISTER["break_hold_rule"][0] == "hold"
    assert FL.hold_kind(True) == "L" and FL.hold_kind(False) == "H"
    with pytest.raises(ValueError, match="break_hold_rule"):
        FL.hold_rule({"break_hold_rule": "extreme"})
    with pytest.raises(ValueError, match="break_hold_rule"):
        _case(False, HOLD_TAIL, [PUSH], s={"break_hold_rule": "extreme"})


# ------------------------------------------------------------------------------------------------ areas (A1)
@MIRRORS
def test_an_area_is_broken_only_when_price_holds_beyond(mirror):
    """The push's own extreme beyond (confirmed while the closes are still beyond) is no hold: not broken until the pullback low
    above the band (mirror: high below) is confirmed — then BROKEN, stamped at that confirmation (bar 23). The earlier reading broke
    it at the push extreme's confirmation (bar 21)."""
    m, lv, Z = _case(mirror, HOLD_TAIL, [PUSH])
    assert _ev(Z) == [] and Z.state_at(len(m) - 1) != FL.BROKEN          # no hold swing ⇒ not broken (price simply still beyond)
    m, lv, Z = _case(mirror, HOLD_TAIL, [PUSH, HOLD])
    assert _ev(Z) == [(23, "broken")] and Z.state_at(22) != FL.BROKEN and Z.state_at(23) == FL.BROKEN
    assert "swing formed beyond it (" + f"{(2 * 101.5 - 118.1) if mirror else 118.1:,.2f}" in [d for _b, k, d in Z.events if k == "broken"][0]
    _m, _lv, Zo = _case(mirror, HOLD_TAIL, [PUSH, HOLD], s=OLD)
    assert _ev(Zo) == [(21, "broken")]                                     # what-if: the earlier reading


@MIRRORS
def test_a_push_beyond_that_turns_back_is_a_sweep_and_the_area_stays_alive(mirror):
    """L5-X01 (11 Sep, Daily area 274: gap beyond, its low, straight back inside): a sweep — the area keeps its role, never BROKEN,
    so no E4 (b) object. The earlier reading called it BROKEN at the push extreme's confirmation."""
    m, lv, Z = _case(mirror, SWEEP_TAIL, [PUSH])
    n = len(m)
    assert _ev(Z) == [] and Z.count("sweep", n - 1) >= 1 and [b for b, k, _ in Z.events if k == "sweep"][0] == 22
    assert Z.role_at(n - 1) == (LV.SUP if mirror else LV.RES) and Z.alive(n - 1) and Z.state_at(n - 1) in (FL.ACTIVE, FL.TESTED)
    assert all(x.get("state") != FL.BROKEN for t in range(n) for x in lv.snapshot(t) if x["id"] == Z.id)
    _m, _lv, Zo = _case(mirror, SWEEP_TAIL, [PUSH], s=OLD)
    assert (21, "broken") in _ev(Zo)


@MIRRORS
def test_a_hold_known_on_a_bar_that_already_closed_back_is_no_break(mirror):
    """The #373 lesson for the break itself: the pullback low above is confirmed at bar 22, but bar 22 has already closed back inside
    the band ⇒ price did not hold ⇒ a sweep, not broken."""
    m, lv, Z = _case(mirror, SWEEP_TAIL, [PUSH, ("L", 118.1, 21, 22)])
    assert _ev(Z) == [] and [b for b, k, _ in Z.events if k == "sweep"][0] == 22


@MIRRORS
def test_reaching_the_far_swing_without_holding_is_no_flip(mirror):
    """The D2 high 120.5 (the first swing after the break) is the far-side swing. Pushed past and back without holding ⇒ a sweep, no
    flip (the earlier reading flipped at its confirmation, bar 21). With the hold (bar 23) the flip comes with the break, at 23."""
    m, lv, Z = _case(mirror, SWEEP_TAIL, [PUSH], [PUSH])
    assert _ev(Z) == [] and Z.count("flip", len(m) - 1) == 0
    _m, _lv, Zo = _case(mirror, SWEEP_TAIL, [PUSH], [PUSH], s=OLD)
    assert (21, "flip") in _ev(Zo)
    m, lv, Z = _case(mirror, HOLD_TAIL, [PUSH, HOLD], [PUSH])
    assert _ev(Z) == [(23, "broken"), (23, "flip")] and Z.role_at(23) == (LV.RES if mirror else LV.SUP)
    assert "held beyond" in [d for _b, k, d in Z.events if k == "flip"][0]


@MIRRORS
def test_a_broken_area_broken_back_is_dead_not_reclaimed(mirror):
    """BROKEN at 23; price comes back through the band (bar 28) and holds on the role side: the pullback high 115.9 below it (mirror:
    low above) is confirmed at 34 while every close is still back ⇒ DEAD at 34 (the same test opposite) — never a reclaim to the old
    role. The earlier reading reclaimed it (alive, role kept)."""
    m, lv, Z = _case(mirror, BACK_TAIL, [PUSH, HOLD, BACK_HOLD])
    n = len(m)
    assert _ev(Z) == [(23, "broken"), (34, "dead")] and Z.dead_bar == 34 and Z.state_at(33) == FL.BROKEN and Z.state_at(34) == FL.DEAD
    assert "broken back" in [d for _b, k, d in Z.events if k == "dead"][0]
    assert all(x["id"] != Z.id for t in range(34, n) for x in lv.snapshot(t))
    _m, _lv, Zo = _case(mirror, BACK_TAIL, [PUSH, HOLD, BACK_HOLD], s=OLD)
    assert ("reclaim" in [k for _b, k in _ev(Zo)]) and Zo.dead_bar is None


@MIRRORS
def test_a_close_back_that_does_not_hold_is_a_sweep_of_the_retest(mirror):
    """The same return, but bar 33 closes back inside the band before the pullback high is confirmed ⇒ the attempt ended: still
    BROKEN (an E4 (b) object)."""
    f, _sw = _mirror(mirror)
    tail = BACK_TAIL[:11] + [117.4, 114.6, 113.5]                          # bar 33 = 117.4 (inside the band 117–118)
    m, lv, Z = _case(mirror, tail, [PUSH, HOLD, BACK_HOLD])
    assert _ev(Z) == [(23, "broken")] and Z.state_at(len(m) - 1) == FL.BROKEN


@MIRRORS
def test_a_flipped_area_broken_again_with_a_hold_is_dead(mirror):
    """Flip once (DECISIONS 27) under BREAK-1: broken (hold) at 23, flipped at the D2 high 122.3 confirmed at 27; then broken again
    against its new role WITH a hold (the pullback high below, confirmed at 34) ⇒ DEAD at 34."""
    m, lv, Z = _case(mirror, BACK_TAIL, [PUSH, HOLD, BACK_HOLD], [("H", 122.3, 25, 27)])
    assert _ev(Z) == [(23, "broken"), (27, "flip"), (34, "broken"), (34, "dead")] and Z.dead_bar == 34


@MIRRORS
def test_area_states_are_read_without_look_ahead(mirror):
    """A cut at every bar (only the bars and the swings confirmed by then) gives the same events up to that bar as the full read."""
    f, sw = _mirror(mirror)
    closes = [f(c) for c in BASE + BACK_TAIL]
    full = m15_from(closes, wick=0.3)
    p1 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16)] + [P(sw(k), f(px), b, c) for k, px, b, c in (PUSH, HOLD, BACK_HOLD)]
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("H"), f(122.3), 25, 27)]

    def events(n):
        m = full.iloc[:n].reset_index(drop=True)
        lv = LV.Levels(res_of(m, [p for p in p2 if p.confirm_bar < n], [p for p in p1 if p.confirm_bar < n]))
        Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
        return [(b, k) for b, k, _ in Z.events if b < n]
    whole = events(len(full))
    for n in range(12, len(full) + 1):
        assert events(n) == [e for e in whole if e[0] < n], n


# ------------------------------------------------------------------------------------------------ lines (A1 / A2)
# A rising line of lows 95 + 0.5·bar (mirror: a falling line of highs). Closes below it from bar 2 (break DOWN).
LINE = lambda b: 95.0 + 0.5 * b                                            # noqa: E731
C_HOLD = [96.2, 96.1, 94.2, 93.2, 94.5, 94.0, 93.1, 92.4]                  # stays below; a pullback high 94.6 (bar 4) below the line
C_SWEEP = [96.2, 96.1, 94.2, 93.2, 94.5, 97.7, 99.9]                       # the low 93.0 (bar 3), then straight back above (bar 5)
# … broken (hold), then back above from bar 8 and a pullback low 100.1 above the line (bar 10, confirmed at 12) — broken back
C_BACK = C_HOLD + [100.0, 100.6, 100.3, 101.5, 102.4, 102.8]


def _mir(mirror, C, piv, line=LINE):
    if not mirror:
        return np.array(C, float), [NS(kind=k, price=float(p), bar=b, confirm_bar=c) for k, p, b, c in piv], line, -1
    return (np.array([203.0 - c for c in C], float), [NS(kind={"H": "L", "L": "H"}[k], price=203.0 - p, bar=b, confirm_bar=c)
                                                       for k, p, b, c in piv], (lambda b: 203.0 - line(b)), 1)


@MIRRORS
def test_a_line_is_broken_only_when_price_holds_beyond(mirror):
    C, piv, ln, side = _mir(mirror, C_HOLD, [("L", 93.0, 3, 4), ("H", 94.6, 4, 6)])
    hk = FL.hold_kind(side > 0)
    assert TL._broken_at(C, piv, hk, ln, side, 1, len(C) - 1, hold=True) == 2           # held: the pullback high below, known at 6
    assert TL._broken_at(C, piv, hk, ln, side, 1, 5, hold=True) is None                 # not known yet at bar 5 (no look-ahead)
    A = {"close": C}
    assert TL.broken_by(A, piv, "H" if mirror else "L", ln, side, 1, len(C) - 1) == 2
    assert TL.broken_by(A, piv, "H" if mirror else "L", ln, side, 1, 5) is None
    C2, piv2, ln2, side2 = _mir(mirror, C_SWEEP, [("L", 93.0, 3, 4)])
    assert TL._broken_at(C2, piv2, FL.hold_kind(side2 > 0), ln2, side2, 1, len(C2) - 1, hold=True) is None   # a sweep
    assert TL._broken_at(C2, piv2, "H" if mirror else "L", ln2, side2, 1, len(C2) - 1) == 2                 # the earlier reading
    assert TL.broken_by({"close": C2}, piv2, "H" if mirror else "L", ln2, side2, 1, len(C2) - 1, "swing_beyond") == 2
    # the pullback high is confirmed on the bar that already closed back above (bar 5) ⇒ no hold (the #373 lesson, mirrored)
    C3, piv3, ln3, side3 = _mir(mirror, C_SWEEP, [("L", 93.0, 3, 4), ("H", 94.6, 4, 5)])
    assert TL._broken_at(C3, piv3, FL.hold_kind(side3 > 0), ln3, side3, 1, len(C3) - 1, hold=True) is None


@MIRRORS
def test_a_broken_line_broken_back_is_dead_stamped_when_known(mirror):
    """Broken (hold) from bar 2; closes back above from bar 8; the pullback low 100.1 above the line (bar 10) confirmed at 12 while every
    close is still back ⇒ broken back (dead): attempt 8, KNOWN at 12 — the chart stamp is 12, never before the break is known (6)."""
    C, piv, ln_f, side = _mir(mirror, C_BACK, [("L", 93.0, 3, 4), ("H", 94.6, 4, 6), ("L", 100.1, 10, 12)])
    y0, y1 = ln_f(0), ln_f(1)
    ln = {"kind": "H" if mirror else "L", "p1": [0, y0], "p2": [1, y1], "slope": y1 - y0, "broken": True, "break_bar": 2,
          "break_side": "up" if mirror else "down"}
    assert TL.broken_back_on(C, piv, ln, 11) is None                                      # not confirmed yet
    assert TL.broken_back_on(C, piv, ln, 12) == 8 and TL.broken_back_on(C, piv, ln, 12, known_bar=True) == 12
    # the confirming bar has already closed back below the line ⇒ no hold there (a sweep of the retest): still broken
    C2 = C.copy()
    C2[12] = ln_f(12) + (1.0 if mirror else -1.0)
    assert TL.broken_back_on(C2, piv, ln, 12) is None
    # a push back above whose only swing there is its own extreme (a high above the line) is no hold — the earlier reading took it
    pivx = [p for p in piv if p.bar != 10] + [NS(kind="L" if mirror else "H", price=203.0 - 102.9 if mirror else 102.9, bar=11,
                                                  confirm_bar=12)]
    assert TL.broken_back_on(C, pivx, ln, 13) is None and TL.broken_back_on(C, pivx, ln, 13, "swing_beyond") == 8


# ------------------------------------------------------------------------------------------------ the approach side (A3, DECISIONS 61)
# A bear call at an object broken DOWN, its original-side edge 100 (above = original side). Bars 1 – 2 close marginally above it;
# the revisit starts at bar 3; the rejection (an engulfing pair) at bars 3 – 4. Mirror: a bull put, the edge reflected.
APPR = [(99.0, 99.3, 98.6, 99.0, 1.0), (99.0, 100.6, 98.9, 100.4, 1.0), (100.4, 100.7, 100.1, 100.3, 1.0),
        (100.3, 100.5, 99.6, 99.8, 1.0), (99.8, 99.9, 98.8, 98.9, 1.0)]


@MIRRORS
def test_marginal_closes_on_the_original_side_without_a_hold_are_a_sweep_approach(mirror):
    d = 1 if mirror else -1
    held = [("L", 100.1, 1, 2)]                                            # a pullback low formed above the edge, confirmed at bar 2
    for swings, blocked in (([], False), (held, True)):
        V, _l, _d = _bare(APPR, swings, mirror=mirror)
        R = EM.Reader(V)
        e0 = 2 * 101.0 - 100.0 if mirror else 100.0
        edge = (lambda i, e0=e0: e0)
        sw = (lambda b, V=V: [p for p in V.levels._known0 if p.confirm_bar <= b])
        acc = (lambda i, R=R, edge=edge, sw=sw: R.accepted_on_original_side(int(i), edge, d, sw))
        assert acc(2) is blocked and acc(0) is False
        why = R.approach_side(4, {"form": "engulf"}, 3, edge, d, accepted=acc)
        assert (why is not None) is blocked, why
        assert R.approach_side(4, {"form": "engulf"}, 3, edge, d, accepted=None) is not None   # what-if: any close there blocks
    V, _l, _d = _bare(APPR, held, mirror=mirror)                           # the swing is confirmed only at bar 3 ⇒ not known at 2
    V.levels._known0[0].confirm_bar = 3
    R = EM.Reader(V)
    e0 = 2 * 101.0 - 100.0 if mirror else 100.0
    assert R.accepted_on_original_side(2, lambda i: e0, d, lambda b: [p for p in V.levels._known0 if p.confirm_bar <= b]) is False


# ------------------------------------------------------------------------------------------------ E4 (b) on the real K4 reader
@MIRRORS
def test_e4b_fires_at_an_area_broken_with_a_hold_and_not_at_a_sweep(mirror, monkeypatch):
    """The retest of an area broken WITH a hold (bar 23) from the break side, rejection at bar 28 ⇒ E4 (b); the same bars where
    price never held beyond (no pullback swing there) ⇒ never broken ⇒ no E4 (b) (L5-X01)."""
    import decision3.method as M
    from tests.test_decision3_zone_answers import _break_case, _zone
    tail = [119.5, 121.0, 122.0, 121.0, 119.5, 118.3, 119.8, 121.5]
    d = -1 if mirror else 1
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1) if t == 28 else None)
    out = {}
    for name, last in (("hold", ("L", 118.1, 21, 23)), ("no_hold", None)):
        m, lv, f = _break_case(True, mirror, tail=tail, last=last)
        Z = _zone(lv, f)
        rows = list(zip(m["open"], m["high"], m["low"], m["close"], [1.0] * len(m)))
        V, _l, _d = _bare(rows, [], s={"entry_area_refine": "area"})
        V.levels = lv
        V._ts = pd.to_datetime(m["timestamp"]).to_numpy()
        V.bar_end = pd.to_datetime(m["bar_end"]).reset_index(drop=True)
        V.step1 = lambda u: (True, "", None, {"trend": "DOWN" if mirror else "UP"})
        out[name] = ([b for b, k, _ in Z.events if k == "broken"],
                     [t for t in range(20, len(m)) for x in EM.Reader(V).broken(t, d)[1] if x["obj"]["area_id"] == Z.id])
    assert out["hold"] == ([23], [28])
    assert out["no_hold"] == ([], [])


@MIRRORS
def test_the_hold_is_read_on_the_structures_finest_degree(mirror):
    """BREAK-1 hold degree (OPEN_QUESTIONS A-L1, provisional default): the pullback that proves the hold is a swing of the structure's
    finest degree (Abhi's approved D1 — the swings the K4 break always read; D0 = wiggles inside a leg). A pullback low above the band
    that only D0 shows is no hold (not broken); the same turn at D1 is (BROKEN at its confirmation, 23)."""
    f, sw = _mirror(mirror)
    m = m15_from([f(c) for c in BASE + HOLD_TAIL], wick=0.3)
    piv1 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16), P(sw("H"), f(120.5), 19, 21)]
    hold = P(sw(HOLD[0]), f(HOLD[1]), HOLD[2], HOLD[3])
    res = res_of(m, [P(sw("H"), f(118), 8, 10)], piv1)
    res["pivots"][0] = piv1 + [hold]
    Z = [L for L in LV.Levels(res).L if abs(L.anchor - f(118)) < 1e-6][0]
    assert _ev(Z) == []
    res["pivots"][1] = piv1 + [hold]
    Z = [L for L in LV.Levels(res).L if abs(L.anchor - f(118)) < 1e-6][0]
    assert _ev(Z) == [(23, "broken")]
