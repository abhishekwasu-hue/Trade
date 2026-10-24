"""Abhi DECISIONS 79 (owner rule, OWNER ORDER 24 Oct R5): the refined base = the ORIGIN base of the area on 15M — the 15M candle(s)
inside the higher-TF base candle from which the departure move started (the candle(s) holding that base candle's extreme on the base's
side), wick to body, kept inside the band; never a later test / turn candle that merely touched the area; invalidation = its far edge.
It replaces the A7 newest-15M-turn reading (DECISIONS 63, now the what-if `entry_area_refine_base = newest_turn`).

Both mirrors (bear call at a supply / bull put at a demand), both trigger modes (15M `Reader`, 5M `Reader5`), and cut = full: the origin
candles are known at the area's birth, so a V cut at bar u reads the same base as the full V at u (no look-ahead).
"""
import numpy as np
import pandas as pd
import pytest

from decision3 import entry_models as EM
from decision3 import entry_models5 as EM5
from decision3 import settings as S3
from decision3 import trigger_frame as TF
from tests.test_decision3_entry_models import MID, _bare, _ltf_from, _mirror_rows

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])

#        o      h      l      c     v      a 1H supply built from the 09:15 hour (bars 0–3): O 100.0 H 103.5 L 99.8 C 100.4 ⇒ its
ORG = [(100.0, 101.0, 99.8, 100.8, 1.0),   # 0  wick to body 100.4 … 103.5 (the area); mirror ⇒ a demand (bull put)
       (100.8, 103.5, 100.7, 103.2, 1.0),  # 1  the hour's HIGH ⇒ the origin 15M candle: wick to body 103.2 … 103.5
       (103.2, 103.3, 101.0, 101.2, 1.0),  # 2  the departure
       (101.2, 101.4, 100.2, 100.4, 1.0),  # 3  the hour closes ⇒ the area is born (bar 3)
       (100.4, 100.5, 98.0, 98.2, 1.0),    # 4  away
       (98.2, 98.3, 97.0, 97.1, 1.0),      # 5  swing low away
       (97.1, 99.0, 97.0, 98.9, 1.0),      # 6
       (98.9, 101.6, 98.8, 101.0, 1.0),    # 7  a LATER 15M turn that merely touched the area: wick to body 101.0 … 101.6 (A7's base)
       (101.0, 101.1, 99.0, 99.2, 1.0),    # 8
       (99.2, 99.3, 98.0, 98.1, 1.0),      # 9  swing low away ⇒ that visit ended
       (98.1, 100.9, 98.0, 100.8, 1.0),    # 10 enters the area again
       (100.8, 102.2, 100.7, 102.0, 1.0),  # 11 through the later turn's band (not the base)
       (102.0, 103.4, 101.9, 103.3, 1.0),  # 12 reaches the origin base, closes inside it ⇒ E1, invalidation 103.5
       (103.3, 103.4, 102.0, 102.1, 1.0)]  # 13
ORG_SW = [("H", 103.5, 1, 2), ("L", 97.0, 5, 6), ("H", 101.6, 7, 8), ("L", 98.0, 9, 10)]
BAND = (100.4, 103.5)
BORN = 3


def _org(mirror, rows=ORG, s=None, ltf=False):
    V, lvl, d = _bare(rows, [x for x in ORG_SW if x[3] < len(rows)], band=BAND, mirror=mirror,
                      s={"entry_area_refine": "setup_tf", **(s or {})}, ltf=_ltf_from(_mirror_rows(rows) if mirror else rows) if ltf else None)
    L = V.levels.L[0]
    L.born_bar, L.tf, L.base_ts = BORN, "1H", pd.Timestamp(V._ts[0])
    L.uid = f"1H:{'L' if mirror else 'H'}:2030-01-07 09:15"
    lvl["born_bar"] = BORN
    return V, lvl, d


def _p(x, mirror):
    return 2 * MID - x if mirror else x


def _band(rb, mirror):
    return (rb["lo"], rb["hi"]) if not mirror else (2 * MID - rb["hi"], 2 * MID - rb["lo"])


def test_setting_registered_default_origin_and_validated():
    assert S3.DEFAULTS["entry_area_refine_base"] == "origin"
    assert S3.REGISTER["entry_area_refine_base"][1] == "origin / newest_turn (what-if)"
    assert "DECISIONS 79" in S3.REGISTER["entry_area_refine_base"][3]
    V, lvl, d = _org(False, s={"entry_area_refine_base": "bogus"})
    with pytest.raises(ValueError):
        EM.Reader(V).refined(5, lvl, d)


@MIRRORS
def test_refined_base_is_the_origin_15m_candle_of_the_base_candle_as_its_wick_to_body(mirror):
    V, lvl, d = _org(mirror)
    R = EM.Reader(V)
    for u in range(BORN, len(ORG)):                                        # known at the area's birth, never moved by a later turn
        rb = R.refined(u, lvl, d)
        assert rb["origin"] is True and rb["bar"] == 1 and rb["bars"] == [1] and rb["tf"] == "15M"
        assert _band(rb, mirror) == pytest.approx((103.2, 103.5))
        assert rb["kind"] == ("L" if mirror else "H") and rb["price"] == pytest.approx(_p(103.5, mirror))
    assert R.rb_far(R.refined(13, lvl, d), d) == pytest.approx(_p(103.5, mirror))   # invalidation = the base's far edge


@MIRRORS
def test_a_later_turn_that_merely_touched_the_area_is_never_the_refined_base(mirror):
    V, lvl, d = _org(mirror)
    assert EM.Reader(V).refined(13, lvl, d)["bar"] == 1                    # the origin, not the bar-7 turn
    Vw, lvlw, dw = _org(mirror, s={"entry_area_refine_base": "newest_turn"})   # the replaced A7 reading (what-if) took the bar-7 turn
    rb = EM.Reader(Vw).refined(13, lvlw, dw)
    assert rb["bar"] == 7 and _band(rb, mirror) == pytest.approx((101.0, 101.6))


@MIRRORS
def test_cut_equals_full_the_origin_is_known_at_the_birth(mirror):
    Vf, lvl, d = _org(mirror)
    full = EM.Reader(Vf)
    for u in range(BORN, len(ORG)):
        Vc, lc, dc = _org(mirror, rows=ORG[:u + 1])
        assert EM.Reader(Vc).refined(u, lc, dc) == full.refined(u, lvl, d)


@MIRRORS
def test_tied_extreme_candles_are_the_origin_together(mirror):
    rows = list(ORG)
    rows[2] = (103.2, 103.5, 101.0, 101.2, 1.0)                            # the hour's high printed twice (bars 1 and 2)
    V, lvl, d = _org(mirror, rows=rows)
    rb = EM.Reader(V).refined(5, lvl, d)
    assert rb["bars"] == [1, 2] and rb["bar"] == 2
    assert _band(rb, mirror) == pytest.approx((103.2, 103.5))              # bar 2's wick to body 103.2 … 103.5 joins bar 1's


@MIRRORS
def test_no_15m_bars_of_the_base_candle_the_area_band_itself(mirror):
    V, lvl, d = _org(mirror)
    V.levels.L[0].base_ts = pd.Timestamp("2029-12-31 09:15")               # a prior area from before the 15M window
    rb = EM.Reader(V).refined(5, lvl, d)
    assert rb["origin"] is False and (rb["lo"], rb["hi"]) == pytest.approx((lvl["lo"], lvl["hi"]))


@MIRRORS
def test_15m_e1_fires_at_the_origin_base_with_its_far_edge_as_invalidation(mirror):
    V, lvl, d = _org(mirror)
    fired = {t: [f for f in EM.Reader(V).area(t, lvl, d)[1]] for t in range(len(ORG))}
    e1 = [(t, f) for t, fs in fired.items() for f in fs if f["model"] == "E1"]
    assert [t for t, _ in e1] == [12]                                      # the later turn's band (bar 11) is not the base
    assert e1[0][1]["invalidation"] == pytest.approx(_p(103.5, mirror))


@MIRRORS
def test_5m_e1_is_the_first_5m_candle_trading_into_the_origin_base(mirror):
    V, lvl, d = _org(mirror, ltf=True)
    F = TF.of(V)
    st = {j: EM5.Reader5(V, j).area5(lvl, d) for j in range(F.n)}
    e1 = [(j, f) for j, (_a, fs) in st.items() for f in fs if f["model"] == "E1"]
    assert len(e1) == 1
    j, f = e1[0]
    assert j // 3 == 12 and f["invalidation"] == pytest.approx(_p(103.5, mirror))
    rb = f["refined"]
    assert rb["origin"] is True and rb["bar"] == 1
    A5 = F.A
    assert float(A5["low"][j]) <= rb["hi"] and float(A5["high"][j]) >= rb["lo"]
    assert not any(float(A5["low"][i]) <= rb["hi"] and float(A5["high"][i]) >= rb["lo"] for i in range(30, j))
