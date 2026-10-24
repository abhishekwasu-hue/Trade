"""DECISIONS 76 / 77 (owner rule, R2 / R3): the follow-through lifecycle of areas AND lines, both mirrors, synthetic (CI-safe), on the
real readers (decision3/levels.py, decision3/trendline.py, decision3/entry_models.py):

  • ALIVE ──a close beyond──▶ BEYOND_NOT_BROKEN (not flipped, no entry of any model);
  • back inside before the follow-through ⇒ FALSE BREAK (a sweep ★; alive in the original role) — a wick beyond too;
  • BROKEN (code FLIPPED, role reversed) = after the close beyond, a 15M close beyond the most recent prior confirmed own-TF swing (DECISIONS 82; 1H = D1) on the
    far side; a wick through that swing that closes back is a sweep of the swing (still BEYOND_NOT_BROKEN); fresh ground ⇒ a new
    own-TF swing forms beyond (confirmed) and a close beyond it — its confirmation alone is no break;
  • a flipped object broken back by the same test ⇒ DEAD (no second flip, never restored);
  • known at the closing bar; a cut at any bar gives the same states up to it (no look-ahead).
"""
import numpy as np
import pytest

from decision3 import entry_models as EM
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import settings as S3
from decision3 import trendline as TL
from tests.test_decision3_entry_models import _bare
from tests.test_decision3_zone_answers import P, _mirror, m15_from, res_of

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["resistance_up", "support_down"])
# A prior own-TF (D2) high 122 (bar 2), a low 110 (bar 7), the resistance from the D2 high 118 (bar 11), a low 113 (bar 14); bars 15 …
# rise into the band. Mirror: every price reflected (a support broken down), H ⇄ L.
HEAD = [119.0, 121.0, 122.0, 120.0, 117.0, 114.0, 111.0, 110.0, 112.0, 114.0, 116.0, 118.0, 116.0, 114.0, 113.0, 114.0, 116.0]
PIVS = [("H", 122.0, 2, 4), ("L", 110.0, 7, 9), ("H", 118.0, 11, 13), ("L", 113.0, 14, 16)]


def _case(mirror, tail, piv_extra=(), highs=None, head=HEAD, pivs=PIVS, cut=None, s=None):
    f, sw = _mirror(mirror)
    closes = [f(c) for c in head + tail]
    wk = {i: f(v) for i, v in (highs or {}).items()}
    m = m15_from(closes, wick=0.3, **({"lows": wk} if mirror else {"highs": wk}))
    piv = [P(sw(k), f(px), b, c) for k, px, b, c in list(pivs) + list(piv_extra)]
    if cut is not None:
        m = m.iloc[:cut + 1].reset_index(drop=True)
        piv = [p for p in piv if p.confirm_bar <= cut]
    lv = LV.Levels(res_of(m, piv, piv), s=s)
    Z = [L for L in lv.L if abs(L.anchor - f(118.0)) < 1e-6][0]
    return m, lv, Z


def _ev(Z, kinds=("beyond", "reclaim", "broken", "flip", "dead")):
    return [(b, k) for b, k, _ in Z.events if k in kinds]


def test_follow_through_is_the_registered_default_and_hold_a_what_if():
    assert S3.DEFAULTS["break_hold_rule"] == S3.REGISTER["break_hold_rule"][0] == "follow_through"
    assert FL.hold_rule({}) == "follow_through" and set(FL.HOLD_RULES) == {"follow_through", "hold", "swing_beyond"}
    assert FL.lifecycle(FL.FLIPPED) == "BROKEN" and FL.lifecycle(FL.BEYOND) == "BEYOND_NOT_BROKEN" and FL.lifecycle(FL.TESTED) == "ALIVE"


@MIRRORS
def test_close_beyond_then_back_inside_is_a_false_break_alive_in_its_role(mirror):
    m, lv, Z = _case(mirror, [119.0, 119.5, 117.0])                       # bar 17 closes beyond, bar 19 back inside
    assert _ev(Z) == [(17, "beyond"), (19, "reclaim")]
    assert Z.state_at(16) in (FL.ACTIVE, FL.TESTED) and Z.state_at(17) == FL.BEYOND and Z.state_at(18) == FL.BEYOND
    assert Z.state_at(19) in (FL.ACTIVE, FL.TESTED) and Z.role_at(19) == Z.role0 and Z.count("sweep", 19) >= 1
    assert all(x["id"] != Z.id for x in lv.active(18, "UP" if mirror else "DOWN"))   # BEYOND_NOT_BROKEN: never a location
    assert any(x["id"] == Z.id for x in lv.active(19, "UP" if mirror else "DOWN"))
    x = next(x for x in lv.snapshot(18) if x["id"] == Z.id)
    assert x["lifecycle"] == "BEYOND_NOT_BROKEN" and x["beyond_at"] == 17 and x["far_swing"]["price"] == pytest.approx(_mirror(mirror)[0](122.0))


@MIRRORS
def test_broken_by_a_close_beyond_the_prior_own_tf_swing_a_wick_through_it_is_a_sweep(mirror):
    f = _mirror(mirror)[0]
    m, lv, Z = _case(mirror, [119.0, 120.0, 121.0, 121.5, 122.6], highs={19: 122.5})   # bar 19 wicks past 122, closes 121
    assert _ev(Z) == [(17, "beyond"), (21, "broken"), (21, "flip")]
    assert Z.state_at(19) == FL.BEYOND and Z.state_at(20) == FL.BEYOND     # the wick through 122 = a sweep of the swing
    assert Z.state_at(21) == FL.FLIPPED and Z.role_at(21) != Z.role0      # known at the closing bar
    v = lv.flip_view(Z, 21)
    assert FL.lifecycle(v["state"]) == "BROKEN" and v["break_dir"] == (-1 if mirror else 1) and v["exc_start"] == 17
    assert v["far_swing"]["price"] == pytest.approx(f(122.0)) and v["far_swing"]["source"] == "before_break"


@MIRRORS
def test_fresh_ground_needs_a_new_swing_beyond_and_a_close_beyond_it_not_its_confirmation(mirror):
    head = [110.0, 111.0] + HEAD[2:]                                       # no prior own-TF swing above the band
    pivs = [p for p in PIVS if p[1] != 122.0]
    # DECISIONS 86 (S1): the new high 121.3 (bar 19) is made by a 1H candle that traded inside the band (bars 16–19) ⇒ INTERNAL, never
    # the next swing; the next new high 121.7 (bar 22, its 1H candle 20–23 entirely beyond) is EXTERNAL ⇒ the close above it breaks
    tail = [119.0, 120.0, 121.0, 120.0, 120.5, 121.4, 120.8, 121.0, 121.9]
    m, lv, Z = _case(mirror, tail, piv_extra=[("H", 121.3, 19, 21), ("H", 121.7, 22, 24)], head=head, pivs=pivs)
    assert Z.state_at(22) == FL.BEYOND                                     # a close above the internal 121.3: no break
    assert Z.state_at(24) == FL.BEYOND                                     # the external swing confirmed at 24: no break yet (Z-1s)
    assert _ev(Z) == [(17, "beyond"), (25, "broken"), (25, "flip")]
    fs = lv.flip_view(Z, 25)["far_swing"]
    assert fs["source"] == "formed_after_break" and fs["price"] == pytest.approx(_mirror(mirror)[0](121.7)) and fs["bar"] == 22


@MIRRORS
def test_a_flipped_object_broken_back_by_the_same_test_is_dead_and_never_restored(mirror):
    up = [119.0, 120.0, 121.0, 121.5, 122.6]                               # BROKEN at 21 (as above)
    m, lv, Z = _case(mirror, up + [121.0, 119.5, 117.5, 115.0, 112.5])     # 24 closes below the band, 26 below the prior low 113 —
    assert _ev(Z) == [(17, "beyond"), (21, "broken"), (21, "flip"), (24, "beyond")]   # but the lows 113 / 110 were made by 1H
    assert Z.state_at(26) == FL.BEYOND and Z.dead_bar is None              # candles that traded inside the band: INTERNAL (S1)
    m, lv, Z = _case(mirror, up + [121.0, 119.5, 117.5, 115.0, 113.0, 114.5, 115.0, 114.0, 112.5], piv_extra=[("L", 113.0, 26, 28)])
    assert _ev(Z) == [(17, "beyond"), (21, "broken"), (21, "flip"), (24, "beyond"), (30, "broken"), (30, "dead")]   # an EXTERNAL low
    assert Z.state_at(29) == FL.BEYOND and Z.role_at(29) != Z.role0 and Z.state_at(30) == FL.DEAD and Z.dead_bar == 30
    m, lv, Z = _case(mirror, up + [121.0, 119.5, 117.5, 119.0, 120.0])     # back above first ⇒ a false break of the flipped object
    assert _ev(Z)[-2:] == [(24, "beyond"), (25, "reclaim")] and Z.state_at(24) == FL.BEYOND
    assert Z.state_at(26) == FL.FLIPPED and Z.role_at(26) != Z.role0 and Z.dead_bar is None   # retest of the flipped object, not restored


@MIRRORS
def test_no_look_ahead_a_cut_at_every_bar_gives_the_same_states(mirror):
    tail = [119.0, 120.0, 121.0, 121.5, 122.6, 121.0, 119.5, 117.5, 115.0, 112.5]
    _m, _lv, full = _case(mirror, tail, highs={19: 122.5})
    for cut in range(17, len(HEAD) + len(tail)):
        _m, _lv, Z = _case(mirror, tail, highs={19: 122.5}, cut=cut)
        assert [Z.state_at(b) for b in range(cut + 1)] == [full.state_at(b) for b in range(cut + 1)], cut
        assert [e for e in _ev(Z)] == [e for e in _ev(full) if e[0] <= cut], cut


def test_e4b_arms_only_on_a_broken_object_never_on_beyond_not_broken(monkeypatch):
    """DECISIONS 77: E4 (b) only after BROKEN (code FLIPPED, break_dir = the trade direction); an object in BEYOND_NOT_BROKEN (or the
    BREAK-1 state BROKEN) is no E4 (b) object."""
    rows = [(103.0, 103.2, 101.8, 102.0, 1.0), (102.0, 105.5, 101.9, 105.3, 1.0), (105.3, 107.2, 105.2, 107.0, 1.0)]
    for state, want in ((FL.FLIPPED, 1), (FL.BEYOND, 0), (FL.BROKEN, 0)):
        snap = [{"id": 1, "lo": 100.0, "hi": 104.0, "role": LV.SUP, "state": state, "break_dir": 1, "broken_at": 1, "trade_location": True,
                 "tf": "1H", "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}]
        V, _l, _d = _bare(rows, [("H", 107.2, 2, 3)], snapshot=lambda t, snap=snap: snap, s={"entry_area_refine": "setup_tf"},
                          trend_at=lambda u: "UP")
        objs = [o for o in EM.Reader(V).broken_objects(2, 1) if o[0] == "area"]
        assert len(objs) == want, state


# ------------------------------------------------------------------------------------------------ lines (as areas)
def _line_case(mirror, closes):
    f, sw = _mirror(mirror)
    C = np.array([f(c) for c in closes], float)
    return C, f, sw, (lambda b: f(100.0)), (-1 if mirror else 1)


@MIRRORS
def test_line_false_break_sweep_of_the_swing_follow_through_and_dead(mirror):
    # a horizontal line at 100 (a line of highs), a prior swing high 103 (bar 1) beyond it; bars 5 … : 101 (beyond), 99 (back = false
    # break), 101, 102, 103.5 (> 103 ⇒ broken at 9, excursion from 7); then back below: 99 (beyond back), 96.5 (< the prior low 97) ⇒ dead
    closes = [99, 103, 98, 97, 98, 101, 99, 101, 102, 103.5, 102, 99, 96.5]
    C, f, sw, line, side = _line_case(mirror, closes)
    known = [P(sw("H"), f(103), 1, 2), P(sw("L"), f(97), 3, 5)]
    assert TL.follow_through_break(C, known, line, side, 4, 6) == (None, None, None)       # 5 beyond, 6 back: a false break
    assert TL.follow_through_break(C, known, line, side, 4, 8) == (None, None, 7)          # BEYOND_NOT_BROKEN since 7
    assert TL.follow_through_break(C, known, line, side, 4, 12) == (7, 9, None)            # broken at 9's close
    ln = {"broken": True, "break_bar": 7, "break_known_bar": 9, "break_side": "down" if mirror else "up", "kind": sw("H"),
          "p1": [0, f(100.0)], "slope": 0.0}
    assert TL.broken_back_on(C, known, ln, 11, rule="follow_through") is None              # back below, no follow-through yet
    assert TL.broken_back_on(C, known, ln, 12, rule="follow_through") == 11                # dead: close beyond the prior low 97
    assert TL.broken_back_on(C, known, ln, 12, rule="follow_through", known_bar=True) == 12


@MIRRORS
def test_line_fresh_ground_waits_for_a_new_swing_and_a_close_beyond_it(mirror):
    closes = [99, 98, 99, 101, 102.5, 101.5, 102.0, 102.6]
    C, f, sw, line, side = _line_case(mirror, closes)
    known = [P(sw("H"), f(102.5), 4, 6)]                                   # formed beyond at 4, confirmed at 6
    assert TL.follow_through_break(C, known, line, side, 1, 6) == (None, None, 3)
    assert TL.follow_through_break(C, known, line, side, 1, 7) == (3, 7, None)


def test_a_daily_object_reads_daily_swings_mapped_to_the_15m_bar_they_are_known_at():
    """Own TF (DECISIONS 76): a Daily object's far swing is a Daily swing (the Daily fold's pivots), known at the 15M bar of its
    known_at; one known before the 15M window is known from its start; a 1H swing never stands in for it."""
    import pandas as pd
    from types import SimpleNamespace as NS
    m, lv, Z = _case(False, [119.0, 120.0])
    day0 = pd.Timestamp(m["timestamp"].iloc[0]).normalize()
    dd = pd.DataFrame({"timestamp": [day0 - pd.Timedelta(days=3), day0 - pd.Timedelta(days=2), day0],
                       "open": [120.0, 123.0, 119.0], "high": [125.0, 124.0, 121.0], "low": [119.0, 118.5, 118.6],
                       "close": [124.0, 119.0, 120.0]})                   # every Daily swing candle stays beyond the band (external)
    piv = [NS(kind="H", price=125.0, bar=0, known_at=day0 - pd.Timedelta(days=1)),          # known before the window
           NS(kind="H", price=121.0, bar=2, known_at=pd.Timestamp(m["bar_end"].iloc[18]))]  # known at 15M bar 18
    lv.daily_states, lv.daily_df = [NS(pivots=piv)], dd
    own = lv._own_swings("D")
    assert [(p.price, p.bar, p.confirm_bar) for p in own] == [(125.0, -1, -1), (121.0, 0, 18)]
    D = LV.Level(id=99, role0=LV.RES, lo=118.0, hi=118.3, born_bar=0, tf="D")
    assert lv._ft_target(D, True, 17, 17)[0].price == 125.0                # only the pre-window Daily swing is known at 17
    assert lv._ft_target(D, True, 17, 18)[0].price == 121.0                # the nearer one from its known bar (formed before 17)
    assert lv._ft_target(Z, True, 17, 18)[0].price == 122.0                # the 1H object reads its own (D2) swings


@MIRRORS
def test_range_is_edge_fades_only_a_flipped_object_is_not_retested_until_the_trend_tf_confirms(mirror):
    """DECISIONS 80 (R6): with no trend side (RANGE) only edge fades — a flipped object's retest is a breakout-retest, not a location;
    with the trend side its retest is (the break in the trend direction: break_dir = the side's direction)."""
    m, lv, Z = _case(mirror, [119.0, 120.0, 121.0, 121.5, 122.6, 121.0, 120.0])
    t = len(m) - 1
    assert Z.state_at(t) == FL.FLIPPED
    with_trend = "DOWN" if mirror else "UP"                                # broken up ⇒ a support ⇒ the bull put side (mirror: bear call)
    assert any(x["id"] == Z.id for x in lv.active(t, with_trend))
    assert all(x["id"] != Z.id for x in lv.active(t, "RANGE"))
    assert all(x["id"] != Z.id for x in lv.active(t, "UP" if mirror else "DOWN"))   # never on the counter-trend side


@pytest.mark.parametrize("trend,calls", [("UP", [1]), ("DOWN", [-1]), ("RANGE", []), ("NEUTRAL", [])])
def test_e4b_reads_only_the_trend_side_on_both_readers(monkeypatch, trend, calls):
    """DECISIONS 80 (R6) audit: E4 (b) is asked only on the Daily side's direction (break_dir = d in `broken_objects`), never in a
    range / without a side — the 15M Reader (EM.read) and the 5M Reader5 (EM5.read5) alike."""
    from types import SimpleNamespace as NS
    from decision3 import entry_models5 as EM5
    seen = []
    fake = NS(A={}, area=lambda t, lvl, d: (None, []), broken=lambda t, d, *a: seen.append(d) or ([], []),
              range_edge_areas=lambda t, trend, act: [])
    monkeypatch.setattr(EM, "Reader", lambda V, *a: fake)
    EM.read(NS(s={"entry_cluster_rule": "area"}), 5, trend, [])
    assert seen == calls
    seen.clear()
    fake5 = NS(A={}, k=5, F=NS(A={}), area5=lambda lvl, d: (None, []), broken5=lambda d, *a: seen.append(d) or ([], []),
               range_edge_areas=lambda t, trend, act: [])
    monkeypatch.setattr(EM5, "Reader5", lambda V, j, *a: fake5)
    EM5.read5(NS(s={"entry_cluster_rule": "area"}), 7, trend, [])
    assert seen == calls


@MIRRORS
def test_the_far_swing_is_the_most_recent_own_tf_swing_beyond_and_a_1h_object_reads_d1_swings(mirror):
    """DECISIONS 82 (Q1): the next swing = the MOST RECENT confirmed own-TF swing lying beyond the object (not the nearest price), and a
    1H object's own swing is the ordinary 1H swing D1, not the zone degree D2. Here a D1-only high 123 (bar 3) is more recent than the
    D2 high 122 (bar 2): a close above 122 is no break; the close above 123 is."""
    f, sw = _mirror(mirror)
    head = [119.0, 121.0, 122.0, 123.0, 117.0, 114.0, 111.0, 110.0, 112.0, 114.0, 116.0, 118.0, 116.0, 114.0, 113.0, 114.0, 116.0]
    tail = [119.0, 120.0, 122.5, 122.8, 123.4]                             # (the 1H candle of bars 0–3 stays above the band: external)
    m = m15_from([f(c) for c in head + tail], wick=0.3)
    d2 = [P(sw(k), f(px), b, c) for k, px, b, c in PIVS]
    d1 = d2 + [P(sw("H"), f(123.0), 3, 6)]
    lv = LV.Levels(res_of(m, d2, d1))
    Z = [L for L in lv.L if abs(L.anchor - f(118.0)) < 1e-6][0]
    assert Z.state_at(19) == FL.BEYOND and Z.state_at(20) == FL.BEYOND    # closes above 122 (the D2 high, nearer in price): no break
    assert _ev(Z)[-2:] == [(21, "broken"), (21, "flip")]                   # the close above the most recent D1 high 123
    assert lv.flip_view(Z, 21)["far_swing"]["price"] == pytest.approx(f(123.0))
