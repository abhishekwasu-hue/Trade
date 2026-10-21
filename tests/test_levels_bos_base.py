"""Abhi 21 Oct (OPEN_QUESTIONS "BANKNIFTY replay reading checks", concept C) — decision3/levels.py BOS-origin (birth b) areas:

  C-1  the base is the candle(s) where buyers / sellers acted BEFORE the breakout (the base the impulse left) — never the breakout
       candle itself (the 1H candle holding the BOS bar);
  C-2  no wick on the area side ⇒ the body (Z-1x order, the same rule as `_band_swing`), never the whole candle.
Synthetic, both mirrors."""
from types import SimpleNamespace as NS

import numpy as np
import pytest

from decision3 import levels as LV

MID = 100.0


def _lv(rows):
    """A bare Levels with only what _base reads: 15M OHLC rows, 4 bars per 1H candle."""
    L = LV.Levels.__new__(LV.Levels)
    L.A = {k: np.array([r[i] for r in rows], float) for i, k in enumerate(("open", "high", "low", "close"))}
    L.n = len(rows)
    L.h1_of = np.arange(len(rows)) // 4
    return L


def _m(rows, mirror):
    return [(2 * MID - o, 2 * MID - lo, 2 * MID - h, 2 * MID - c) for o, h, lo, c in rows] if mirror else rows


# hour 0 = the origin swing (buyers acted: low 98, body bottom 100), hour 1 = red pullback, hour 2 = the breakout (BOS at bar 9)
ROWS = [(100.0, 100.4, 99.5, 99.8), (99.8, 100.0, 98.0, 99.9), (99.9, 100.6, 99.8, 100.5), (100.5, 101.0, 100.3, 100.5),
        (100.5, 100.6, 100.0, 100.1), (100.1, 100.2, 99.7, 99.9), (99.9, 100.0, 99.6, 99.8), (99.8, 99.9, 99.6, 99.8),
        (99.8, 101.5, 99.8, 101.4), (101.4, 103.0, 101.3, 102.9), (102.9, 103.2, 102.5, 103.1), (103.1, 103.3, 102.9, 103.2)]


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_bos_demand", "bear_bos_supply"])
def test_c1_the_breakout_candle_is_never_the_base(mirror):
    d = -1 if mirror else 1
    L = _lv(_m(ROWS, mirror))
    j, c4 = L._base(d, NS(bar=1), 9)
    assert j == 0                                                          # the origin's candle — not hour 2 (the breakout, bar 9)
    lo, hi = LV.bos_band(d, c4)
    want = (98.0, 100.0) if not mirror else (2 * MID - 100.0, 2 * MID - 98.0)
    assert (lo, hi) == pytest.approx(want)                                 # wick to body of the candle the impulse left


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_bos_demand", "bear_bos_supply"])
def test_c1_a_trend_candle_complete_before_the_breakout_hour_is_the_base(mirror):
    rows = list(ROWS)
    rows[4:8] = [(100.0, 100.3, 99.7, 100.2), (100.2, 100.5, 100.1, 100.4), (100.4, 100.6, 100.3, 100.5), (100.5, 100.7, 100.4, 100.6)]
    d = -1 if mirror else 1
    L = _lv(_m(rows, mirror))
    j, c4 = L._base(d, NS(bar=1), 9)
    assert j == 1                                                          # the departure candle after the origin, before the breakout
    lo, hi = LV.bos_band(d, c4)
    want = (99.7, 100.0) if not mirror else (2 * MID - 100.0, 2 * MID - 99.7)
    assert (lo, hi) == pytest.approx(want)


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_c2_no_wick_on_the_area_side_gives_the_body_not_the_whole_candle(mirror):
    c4 = (100.0, 105.0, 100.0, 104.0)                                      # bull candle opened at its low: no lower wick
    d = 1
    if mirror:
        c4, d = (2 * MID - 100.0, 2 * MID - 100.0, 2 * MID - 105.0, 2 * MID - 104.0), -1
    lo, hi = LV.bos_band(d, c4)
    want = (100.0, 104.0) if not mirror else (2 * MID - 104.0, 2 * MID - 100.0)
    assert (lo, hi) == pytest.approx(want)                                 # the body — before: the whole candle (to 105 / 95)
    assert LV.bos_band(d, c4) == LV._band_swing("L" if d > 0 else "H", *c4, c4[2] if d > 0 else c4[1], 0)
