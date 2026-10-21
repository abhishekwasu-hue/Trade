"""PA standard §2F (track T2): imbalances, Fib only as confluence, HTF levels, the per-area confluence list (decision3/confluence_pa.py)."""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd

from decision3 import confluence_pa as CP
from decision3 import levels as LV
from decision3 import pa_frames as PF
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

SCHEMA = {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}


def bars(rows):
    o, h, lo, c = (np.array(x, float) for x in zip(*rows))
    ts = list(pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min"))
    return PF.Frame("15M", o, h, lo, c, None, ts, len(rows) - 1, [], [])


GAP = [(100, 101.5, 99.5, 101), (101, 106.5, 100.8, 106), (106, 107.5, 103, 107)]   # low 103 > high 101.5, bullish middle


# ------------------------------------------------------------------------------------------------ imbalance (F.2)
def test_bullish_gap_open_partly_filled():
    g = CP.scan_fvgs(bars(GAP + [(107, 108, 104, 107.5)]))
    assert len(g) == 1 and g[0]["dir"] == 1 and (g[0]["lo"], g[0]["hi"]) == (101.5, 103.0) and g[0]["state"] == "open"
    assert g[0]["middle_largest"]
    g = CP.scan_fvgs(bars(GAP + [(107, 108, 102.5, 104)]))[0]
    assert g["state"] == "partly" and g["remaining"] == (101.5, 102.5)
    g = CP.scan_fvgs(bars(GAP + [(107, 108, 102.5, 104), (104, 104.5, 101, 102)]))[0]
    assert g["state"] == "filled" and g["remaining"] is None and g["filled_at"] is not None


def test_bearish_gap_and_no_gap_without_a_one_sided_middle_candle():
    mirror = [(200 - o, 200 - lo, 200 - h, 200 - c) for o, h, lo, c in GAP]
    g = CP.scan_fvgs(bars(mirror))
    assert len(g) == 1 and g[0]["dir"] == -1 and (g[0]["lo"], g[0]["hi"]) == (97.0, 98.5)
    against = [GAP[0], (106, 106.5, 100.8, 101.2), GAP[2]]                    # bearish middle candle ⇒ not an imbalance left upward
    assert CP.scan_fvgs(bars(against)) == []


def test_state_reads_only_bars_up_to_t():
    F = bars(GAP + [(107, 108, 104, 107.5), (107, 108, 100, 101)])
    F.last = 3                                                                 # at t = bar 3 the later fill is unknown
    assert CP.scan_fvgs(F)[0]["state"] == "open"


# ------------------------------------------------------------------------------------------------ Fib only as confluence (F.3)
def _impulse_case(tail, lows=None):
    closes = [130, 138, 146, 149, 145, 140, 135, 125, 115, 106, 101, 105, 110, 120, 130, 140, 148, 155, 162, 170, 178, 185, 190, 194,
              197, 199] + tail
    m = m15_from(closes, highs={3: 150.0, 25: 200.0}, lows={10: 100.0, **(lows or {})})
    piv = [P("H", 150, 3, 5), P("L", 100, 10, 12), P("H", 200, 25, 27)]
    res = res_of(m, piv)
    return m, NS(levels=LV.Levels(res), s=S3.load(), res=res)


PULLBACK = [195, 190, 184, 178, 172, 166, 160, 155, 152, 150]
AREA = {"id": 99, "tf": "1H", "role": LV.SUP, "lo": 137.0, "hi": 139.0, "state": "ACTIVE"}


def test_fib_reported_only_where_it_lands_on_an_area():
    m, V = _impulse_case(PULLBACK)
    t = len(m) - 1
    f = CP.fib_on_areas(V, t, snap=[AREA], obvious=[])
    assert f["impulse"]["from_price"] == 100.0 and f["impulse"]["to_price"] == 200.0
    assert [x["ratio"] for x in f["levels"]] == [0.618] and f["levels"][0]["on"][0]["id"] == 99
    f = CP.fib_on_areas(V, t, snap=[], obvious=[])                             # nothing there ⇒ no Fib at all (never alone)
    assert f["levels"] == [] and "never read alone" in f["why"]


def test_fib_lands_on_resting_liquidity_band():
    m, V = _impulse_case(PULLBACK)
    t = len(m) - 1
    pool = {"tf": "15M", "kind": "H", "side": "buy", "price": 150.0, "bar": 3, "state": "resting"}
    f = CP.fib_on_areas(V, t, snap=[], obvious=[pool])
    assert [x["ratio"] for x in f["levels"]] == [0.5] and f["levels"][0]["on"][0]["what"] == "liquidity"


def test_no_fib_before_the_end_is_confirmed_or_after_price_passed_the_origin():
    m, V = _impulse_case(PULLBACK)
    assert CP.fib_on_areas(V, 26, snap=[AREA], obvious=[])["impulse"] is None   # H 200 confirms at bar 27
    m, V = _impulse_case(PULLBACK + [140, 125, 110, 102], lows={39: 99.0})   # a wick beyond the origin (a close there = a new BOS)
    f = CP.fib_on_areas(V, len(m) - 1, snap=[AREA], obvious=[])
    assert f["impulse"] is None and f["levels"] == [] and "origin" in f["why"]


def test_fib_ratios_are_a_registered_declared_exception():
    assert S3.DEFAULTS["pa_fib_ratios"] == (0.382, 0.5, 0.618, 0.786)
    reg = S3.REGISTER["pa_fib_ratios"]
    assert reg[2] == "व्याख्या" and "declared exception" in reg[3] and "never alone" in reg[3]


# ------------------------------------------------------------------------------------------------ confluence list (F.4) + output
def test_area_confluence_lists_pieces_at_the_same_place():
    m, V = _impulse_case(PULLBACK)
    t = len(m) - 1
    r = CP.read_confluence(V, t)
    assert set(r) == {"htf_levels", "fvg", "fib", "areas"}
    for a in r["areas"]:
        assert (a["label"] is None) == (not a["pieces"])
        for p in a["pieces"]:
            if p["what"] == "imbalance":
                assert not (p["hi"] < a["lo"] or p["lo"] > a["hi"])


def test_no_lookahead_and_schema():
    m, V = _impulse_case(PULLBACK)
    piv = [P("H", 150, 3, 5), P("L", 100, 10, 12), P("H", 200, 25, 27)]
    for t in (20, 28, 33):
        mt = m.iloc[:t + 1].reset_index(drop=True)
        res = res_of(mt, [p for p in piv if p.confirm_bar <= t])
        Vt = NS(levels=LV.Levels(res), s=S3.load(), res=res)
        assert CP.read_confluence(V, t) == CP.read_confluence(Vt, t)
    objs = CP.draw_objects(V, len(m) - 1)
    assert objs and all(set(o) == SCHEMA for o in objs)
