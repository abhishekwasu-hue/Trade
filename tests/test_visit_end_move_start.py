"""DECISIONS 64 (owner rule, gallery review B1 / B2): the visit ends by structure and the move start moves forward.

  • B1 — a visit ends when price leaves the area and builds swings away that do not reach it again: a structure-degree swing built
    away (as before), or, at the finest swings, a swing away and then the next turn that does not reach the area. No model fires and no
    RSI read belongs to the ended visit; the next touch is a NEW visit (the models re-arm). A finest dip whose next turn reaches the
    area again keeps the visit (the dip was part of it).
  • B2 — the move into the zone begins at the LAST swing built away from the area known at t; each new away swing moves it forward
    (also a dip inside the visit); the RSI read, the 5M reader, the broken-area / broken-line retests and the dossier read the same.
  • `visit_end_rule = single_swing` (what-if) = the earlier reading, unchanged.
  • No look-ahead: full data = data cut at the decision bar (15M and 5M); both mirrors; no numbers (comparisons of swings and the band).
Synthetic only (CI-safe).
"""
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import entry_models as EM
from decision3 import entry_models5 as EM5
from decision3 import settings as S3
from decision3 import trigger_frame as TF
from tests.test_decision3_entry_models import MID, _bare, _ltf_from, _mirror_rows, _mirror_sw

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
OLD = {"visit_end_rule": "single_swing"}

# A supply 100–102 (bear call). (open, high, low, close, volume)
ROWS = [(97.0, 97.6, 96.8, 97.5, 1.0),       # 0  swing low built away (structure + finest)
        (97.5, 98.6, 97.4, 98.5, 1.0),       # 1  approach
        (98.5, 99.4, 98.4, 99.3, 1.0),       # 2  approach
        (99.3, 100.6, 99.2, 100.4, 1.0),     # 3  enters the area ⇒ visit (E1)
        (100.4, 101.2, 100.2, 101.0, 1.0),   # 4
        (101.0, 101.3, 100.1, 100.2, 1.0),   # 5  finest swing high (inside)
        (100.2, 100.3, 99.0, 99.2, 1.0),     # 6  a dip: finest swing low BELOW the area (away)
        (99.2, 100.8, 99.1, 100.7, 1.0),     # 7  back into the area
        (100.7, 101.5, 100.5, 100.9, 1.0),   # 8  the next turn REACHES the area ⇒ same visit; the move start moved to 6
        (100.9, 101.0, 98.0, 98.1, 1.0),     # 9  leaves
        (98.1, 98.3, 97.5, 97.8, 1.0),       # 10 finest swing low away
        (97.8, 99.0, 97.7, 98.8, 1.0),       # 11 the next turn stays BELOW the area ⇒ the visit ended (known at its confirmation, 12)
        (98.8, 98.9, 97.0, 97.1, 1.0),       # 12 a new swing low away (the next move's start)
        (97.1, 99.5, 97.0, 99.4, 1.0),       # 13
        (99.4, 100.5, 99.3, 100.4, 1.0)]     # 14 back into the area ⇒ a NEW visit (E1 re-arms)
FINE = [("L", 96.8, 0, 1), ("H", 101.3, 5, 6), ("L", 99.0, 6, 7), ("H", 101.5, 8, 9), ("L", 97.5, 10, 11), ("H", 99.0, 11, 12),
        ("L", 97.0, 12, 13)]
STRUCT = [("L", 96.8, 0, 1)]                 # the structure degree (D1): no swing after the visit began


def _with_fine(V, fine, mirror):
    fine = _mirror_sw(fine) if mirror else fine
    V.levels.res = {"pivots": {0: [NS(kind=k, price=float(p), bar=b, confirm_bar=c) for k, p, b, c in fine]}}
    return V


def _case(mirror, s=None, rows=ROWS, fine=FINE, struct=STRUCT):
    V, lvl, d = _bare(rows, struct, mirror=mirror, s=s)
    return _with_fine(V, fine, mirror), lvl, d


def test_visit_end_rule_registered_validated_and_a_live_switch():
    import engine3_live as L
    assert S3.DEFAULTS["visit_end_rule"] == "away_not_reached"
    assert S3.REGISTER["visit_end_rule"][:3] == ("away_not_reached", "away_not_reached / single_swing (what-if)", "Abhi नियम")
    assert L.METHOD_SWITCHES["engine3_visit_end_rule"][:2] == ("visit_end_rule", ("away_not_reached", "single_swing"))
    assert L.method_switches({"engine3_visit_end_rule": "single_swing"}) == {"visit_end_rule": "single_swing"}
    assert L.method_switches({"engine3_visit_end_rule": ""}) == {}
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    with pytest.raises(ValueError, match="visit_end_rule"):
        E3.V22(m15, s={"visit_end_rule": "time"}, ltf=ltf, futures=fut)


@MIRRORS
def test_b1_visit_ends_when_price_leaves_and_the_next_turn_does_not_reach_the_area(mirror):
    V, lvl, d = _case(mirror)
    st = {t: V.visit(t, lvl, d) for t in range(len(ROWS))}
    assert all(st[t]["start"] == 3 for t in range(3, 12))                 # the dip at 6 (next turn reached it at 8) = the same visit
    assert st[12]["start"] is None and st[12]["prev_end"] == 11 and st[12]["left_at"] == 10 and st[12]["ended_by"] == "swing"
    assert "did not reach it again" in st[12]["why"] and st[13]["start"] is None
    assert st[14]["start"] == 14 and st[14]["approach_from"] == 13       # a new visit; its leg starts after the last away swing (12)
    old = _case(mirror, s=OLD)[0]                                         # the earlier reading: no D1 swing away ⇒ never ended
    assert all(old.visit(t, lvl, d)["start"] == 3 for t in range(3, len(ROWS)))


@MIRRORS
def test_b1_no_model_fires_in_an_ended_visit_and_the_next_visit_rearms(mirror):
    V, lvl, d = _case(mirror)
    R = EM.Reader(V)
    got = {t: R.area(t, lvl, d) for t in range(len(ROWS))}
    fired = [(t, f["model"]) for t, (_a, fs) in got.items() for f in fs]
    assert (3, "E1") in fired and (14, "E1") in fired                      # E1 once per visit: the first and the new visit
    assert got[12][0] is None and got[13][0] is None and not got[12][1] and not got[13][1]   # the ended visit: nothing armed
    assert got[14][0]["visit_id"] != got[11][0]["visit_id"]
    assert [m for t, m in fired if t in (7, 8)] == []                      # the dip inside the visit is not a new visit (no E1)
    Vo = _case(mirror, s=OLD)[0]                                          # what-if: the visit never ended ⇒ no second E1
    fo = [(t, f["model"]) for t in range(len(ROWS)) for f in EM.Reader(Vo).area(t, lvl, d)[1]]
    assert (3, "E1") in fo and (14, "E1") not in fo


@MIRRORS
def test_b1_a_structure_swing_built_away_still_ends_the_visit(mirror):
    V, lvl, d = _case(mirror, struct=STRUCT + [("L", 99.0, 6, 7)])        # the dip at 6 is a structure-degree swing too
    assert V.visit(6, lvl, d)["start"] == 3 and V.visit(7, lvl, d)["start"] == 7   # ended at 6 (known at 7); bar 7 touches ⇒ new
    assert V.visit(7, lvl, d)["approach_from"] == 7 and V.visit(7, lvl, d)["move_from"] == 6


@MIRRORS
def test_b2_the_move_start_is_the_last_away_swing_and_moves_forward(mirror):
    V, lvl, d = _case(mirror)
    mf = {t: V.visit(t, lvl, d)["move_from"] for t in range(3, len(ROWS))}
    assert mf[3] == 0 and mf[6] == 0                                       # the dip at 6 confirms at 7
    assert mf[7] == 6 and mf[8] == 6 and mf[11] == 10                      # each new away swing moves the start forward
    assert mf[12] is None and mf[14] == 12                                 # no visit ⇒ none; the new visit's move from 12
    for t in (8, 14):                                                      # the RSI read gets exactly this start (decision commit facts)
        cm = V._confirm(t, d, lvl, {})[2]
        assert cm["move_from_bar"] == mf[t]
    Vo = _case(mirror, s=OLD)[0]                                          # what-if: fixed at the visit's approach (bar 0)
    assert {Vo.visit(t, lvl, d)["move_from"] for t in range(3, len(ROWS))} == {0}


@MIRRORS
def test_b2_the_rsi_read_frame_follows_the_visit(mirror):
    from decision3 import rsi_hidden as RH
    V, lvl, d = _case(mirror)
    V.pb = NS(at=lambda t, dd: None)
    assert RH.frame_of(V, 8, d, lvl=lvl)["move_from"] == 6
    assert RH.frame_of(V, 12, d, lvl=lvl)["move_from"] is None             # the visit ended ⇒ no move into the zone (NA)


@MIRRORS
def test_no_look_ahead_full_equals_cut_at_every_bar(mirror):
    V, lvl, d = _case(mirror)
    for t in range(len(ROWS)):
        Vc, lc, dc = _bare(ROWS[:t + 1], [x for x in STRUCT if x[3] <= t], mirror=mirror)
        _with_fine(Vc, [x for x in FINE if x[3] <= t], mirror)
        full, cut = V.visit(t, lvl, d), Vc.visit(t, lc, dc)
        assert full == cut, t
        assert json.dumps(EM.Reader(V).area(t, lvl, d), default=str, sort_keys=True) == \
            json.dumps(EM.Reader(Vc).area(t, lc, dc), default=str, sort_keys=True), t


# ------------------------------------------------------------------------------------------------ 5M reader
def _v5(mirror, rows=ROWS, fine=FINE, struct=STRUCT, s=None, ltf=None):
    rr = _mirror_rows(rows) if mirror else rows
    V, lvl, d = _bare(rows, struct, mirror=mirror, s=s, ltf=ltf if ltf is not None else _ltf_from(rr))
    return _with_fine(V, fine, mirror), lvl, d


@MIRRORS
def test_5m_reader_reads_the_same_visit_end_and_move_start(mirror):
    V, lvl, d = _v5(mirror)
    F = TF.of(V)
    for j in range(F.n):
        R = EM5.Reader5(V, j)
        v5, k = R.visit5(j, lvl, d), R.k
        if k < 0:
            continue
        v15 = V.visit(k, lvl, d)
        if v15["start"] is not None:
            assert v5["move_from15"] == v15["move_from"], j
    ends = [j for j in range(F.n) if EM5.Reader5(V, j).k == 12]
    assert all(EM5.Reader5(V, j).area5(lvl, d)[0] is None for j in ends)   # the ended visit: nothing armed on 5M either
    fired = [(F.T(j), f["model"]) for j in range(F.n) for f in EM5.Reader5(V, j).area5(lvl, d)[1]]
    assert [m for _t, m in fired].count("E1") == 2                         # the first visit and the new one


@MIRRORS
def test_5m_no_look_ahead_full_equals_cut_at_the_5m_close(mirror):
    V, lvl, d = _v5(mirror)
    F = TF.of(V)
    rr = _mirror_rows(ROWS) if mirror else ROWS
    full5 = _ltf_from(rr)
    ends15 = (pd.date_range("2030-01-07 09:15", periods=len(ROWS), freq="15min") + pd.Timedelta(minutes=15)).to_numpy()
    for j in range(F.n):
        k = int(np.searchsorted(ends15, full5["end"][j], side="right")) - 1
        cut5 = {**{kk: v[:j + 1] for kk, v in full5.items() if isinstance(v, np.ndarray)}, "minutes": 5, "label": "5M"}
        Vc, lc, dc = _v5(mirror, rows=ROWS[:k + 1], fine=[x for x in FINE if x[3] <= k], struct=[x for x in STRUCT if x[3] <= k],
                         ltf=cut5)
        full = EM5.Reader5(V, j).area5(lvl, d)
        cut = EM5.Reader5(Vc, TF.of(Vc).n - 1).area5(lc, dc)
        assert json.dumps(full, default=str, sort_keys=True) == json.dumps(cut, default=str, sort_keys=True), j


# ------------------------------------------------------------------------------------------------ E4 (b) revisit end
def test_revisit_start_ends_by_swings_away_that_do_not_reach_the_object():
    tb = {3, 4, 7, 14}
    assert EM.revisit_start(tb, [(5, False), (6, True), (8, False)]) == 3          # a turn reached it again ⇒ the same revisit
    assert EM.revisit_start({3, 4}, [(10, True), (11, True)]) is None              # two swings away not reaching ⇒ over
    assert EM.revisit_start(tb, [(10, True), (11, True)]) == 14                    # a later touch ⇒ a new revisit
    assert EM.revisit_start({3, 4}, [(10, True)]) == 3                             # one finest swing alone: not yet
    assert EM.revisit_start({3, 4}, [(10, True)], struct={10}) is None             # a structure swing away: over (as before)
    assert EM.revisit_start({3}, [(3, True), (4, True)]) == 3                      # swings on / before the start never end it


@MIRRORS
def test_line_retest_move_start_moves_forward(mirror, monkeypatch):
    from tests.test_rsi_l5bc import _line_case
    V, ln, d = _line_case(mirror, monkeypatch)
    kind = "H" if mirror else "L"
    p = (2 * MID - 93.0) if mirror else 93.0
    V.levels.res = {"pivots": {0: [NS(kind=kind, price=p, bar=3, confirm_bar=4),
                                   NS(kind=kind, price=(2 * MID - 96.5) if mirror else 96.5, bar=6, confirm_bar=7)]}}
    R = EM.Reader(V)
    assert R.line_move_from(5, ln, d, 5) == 3 and R.line_move_from(8, ln, d, 5) == 6   # a new away swing (below the line at 6)
    V.s = {**V.s, **OLD}
    assert R.line_move_from(8, ln, d, 5) == 3                                          # what-if: before the revisit only


# A visit that leaves on the FAR side: beyond the area, a swing there, and the next turn does not come back into the area (it held
# beyond — the lifecycle's break); a sweep (the next turn comes back inside) keeps the visit (CLAUDE.md "Sweep / fakeout").
FAR = [(97.0, 97.6, 96.8, 97.5, 1.0),        # 0  swing low (approach)
       (97.5, 99.4, 97.4, 99.3, 1.0),        # 1
       (99.3, 100.6, 99.2, 100.4, 1.0),      # 2  visit
       (100.4, 102.9, 100.3, 102.8, 1.0),    # 3  beyond the far edge
       (102.8, 103.6, 102.7, 103.5, 1.0),    # 4  finest swing high beyond
       (103.5, 103.5, 102.4, 102.5, 1.0),    # 5  the next turn stays above 102 ⇒ held beyond ⇒ the visit ended (known at 6)
       (102.5, 103.0, 102.3, 102.9, 1.0)]    # 6
FAR_FINE = [("L", 96.8, 0, 1), ("H", 103.6, 4, 5), ("L", 102.4, 5, 6)]


@MIRRORS
def test_b1_holding_beyond_the_far_side_ends_the_visit_a_sweep_does_not(mirror):
    V, lvl, d = _case(mirror, rows=FAR, fine=FAR_FINE)
    assert V.visit(5, lvl, d)["start"] == 2 and V.visit(6, lvl, d)["start"] is None
    sweep = [("L", 96.8, 0, 1), ("H", 103.6, 4, 5), ("L", 101.0, 5, 6)]     # the next turn back inside the area
    rows = FAR[:5] + [(103.5, 103.5, 101.0, 101.2, 1.0), (101.2, 101.6, 100.8, 101.4, 1.0)]
    V2, lvl2, d2 = _case(mirror, rows=rows, fine=sweep)
    assert V2.visit(6, lvl2, d2)["start"] == 2
