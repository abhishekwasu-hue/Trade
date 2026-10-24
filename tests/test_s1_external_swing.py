"""DECISIONS 86 (S1, amends 82) / 87 (DP-1, DP-2) / 89 — synthetic, both mirrors, on the real readers:

  • BREAK-2's next swing = the most recent EXTERNAL own-TF swing beyond the object; a swing whose own-TF candle traded inside the
    object's band (made while price tested it, its false-break extremes included) is INTERNAL and never counts — break AND broken-back,
    areas AND lines;
  • internal extremes are labelled "FALSE BREAK extreme" (DECISIONS 89), never a swing high / low;
  • a Daily bar whose closing-auction print lies beyond the traded range keeps its official close, is flagged "auction-extended" and
    its high / low = the traded extreme (never a swing extreme / zone edge); such a print never counts as a close in a lifecycle;
  • the data flags apply wherever V22 is built (replays as live): `history.ensure_marked`.
"""
import numpy as np
import pandas as pd
import pytest

from decision3 import flip as FL
from decision3 import history as HI
from decision3 import levels as LV
from decision3 import trendline as TL
from tests.test_decision3_zone_answers import P, _mirror, m15_from, res_of
from tests.test_lifecycle_follow_through import HEAD, MIRRORS, PIVS, _case, _ev


@MIRRORS
def test_an_internal_false_break_extreme_is_never_the_next_swing(mirror):
    """A false break above the band makes a high 119.8 (bar 17) by a 1H candle that traded inside the band ⇒ INTERNAL. The later
    break closes above it but not above the EXTERNAL high 122 (bar 2) ⇒ BEYOND_NOT_BROKEN (under DECISIONS 82 alone: BROKEN)."""
    f = _mirror(mirror)[0]
    tail = [119.5, 117.5, 116.0, 117.0, 118.6, 119.2, 120.2, 120.6]          # 17 beyond, 18 back (false break), 21 … beyond again
    m, lv, Z = _case(mirror, tail, piv_extra=[("H", 119.8, 17, 19)])
    assert _ev(Z) == [(17, "beyond"), (18, "reclaim"), (21, "beyond")]
    assert Z.state_at(24) == FL.BEYOND                                     # closes above 119.8 (bars 23, 24): no break
    v = lv.flip_view(Z, 24)
    assert v["far_swing"]["price"] == pytest.approx(f(122.0)) and v["far_swing"]["source"] == "before_break"
    fbx = v["false_break_extremes"]                                        # DECISIONS 89: labelled, never a swing high / low
    assert [x["price"] for x in fbx] == [pytest.approx(f(119.8))] and fbx[0]["bar"] == 17
    assert fbx[0]["label"].startswith(LV.FALSE_BREAK_EXTREME) and "swing" not in fbx[0]["label"]
    m, lv, Z = _case(mirror, tail + [121.5, 122.6], piv_extra=[("H", 119.8, 17, 19)])
    assert _ev(Z)[-2:] == [(26, "broken"), (26, "flip")]                   # the close beyond the external 122 breaks it


@MIRRORS
def test_line_internal_swing_is_skipped_only_with_the_candle_ranges(mirror):
    """Lines (DECISIONS 86): a swing whose own candle traded through the line is internal; with the chart's highs / lows given the
    follow-through waits for the external swing."""
    f, sw = _mirror(mirror)
    closes = [f(c) for c in [99, 98, 99, 101, 100.5, 99.8, 101.2, 102.0, 103.5]]
    hi = np.array([max(a, b) + 0.3 for a, b in zip([closes[0]] + closes[:-1], closes)])
    lo = np.array([min(a, b) - 0.3 for a, b in zip([closes[0]] + closes[:-1], closes)])
    C = np.array(closes)
    line = (lambda b: f(100.0))                                            # noqa: E731
    side = -1 if mirror else 1
    ext = P(sw("H"), f(103.0), 0, 0)                                       # an earlier swing, its candle away from the line
    hi[0], lo[0] = (max(f(103.0), f(102.0)), min(f(103.0), f(102.0)))
    inn = P(sw("H"), f(101.3), 4, 5)                                       # bar 4: its candle traded through the line (internal)
    hi[4], lo[4] = (max(f(101.3), f(99.6)), min(f(101.3), f(99.6)))
    known = [ext, inn]
    assert TL.follow_through_break(C, known, line, side, 1, 8)[:2] == (6, 7)                 # without candles: the most recent (101.3)
    assert TL.follow_through_break(C, known, line, side, 1, 8, (hi, lo))[:2] == (6, 8)       # S1: only the external 103 counts


def _intraday(prints, mirror=False):
    """One session of 15M bars (09:15 … 15:15) trading 100 ± 2 (mirror ⇒ reflected), the last bar = the flat value + the print."""
    f = _mirror(mirror)[0]
    ts = pd.date_range("2030-01-07 09:15", periods=25, freq="15min")
    c = [f(100.0 + (1.0 if i % 2 else -1.0)) for i in range(24)] + [f(prints)]
    o = [f(100.0)] + c[:-1]
    o[-1] = c[-2]                                                          # the flat value before the print
    h = [max(a, b) + 1.0 for a, b in zip(o, c)]
    lw = [min(a, b) - 1.0 for a, b in zip(o, c)]
    h[-1], lw[-1] = max(o[-1], c[-1]), min(o[-1], c[-1])
    d = pd.DataFrame({"timestamp": ts, "open": o, "high": h, "low": lw, "close": c})
    d["data_problem"] = [""] * 24 + [HI.CLOSE_PRINT]
    return d


@MIRRORS
def test_auction_extended_daily_keeps_the_close_and_takes_the_traded_extreme(mirror):
    f = _mirror(mirror)[0]
    m = _intraday(105.0, mirror)                                           # the print 105 lies beyond the traded high 102
    daily = pd.DataFrame({"timestamp": [pd.Timestamp("2030-01-07")], "open": [m["open"].iloc[0]], "high": [m["high"].max()],
                          "low": [m["low"].min()], "close": [m["close"].iloc[-1]]})
    out = HI.mark_auction_extended(daily, m)
    x = out.iloc[0]
    assert bool(x["auction_extended"]) and x["data_problem"] == HI.AUCTION_EXTENDED
    assert x["close"] == pytest.approx(f(105.0))                           # the official close stays the Daily close
    if mirror:
        assert x["low"] == pytest.approx(f(102.0)) and x["print_low"] == pytest.approx(f(105.0))   # the traded low
    else:
        assert x["high"] == pytest.approx(102.0) and x["print_high"] == pytest.approx(105.0)       # the traded high
    band = LV._band_swing("L" if mirror else "H", x["open"], x["high"], x["low"], x["close"], x["low" if mirror else "high"], 0)
    assert (band[0] >= f(102.0) - 1e-9) if mirror else (band[1] <= 102.0 + 1e-9)                  # never a zone edge
    assert HI.auction_extended_bars(m).tolist() == [False] * 24 + [True]
    m2 = _intraday(101.5, mirror)                                          # a print inside the traded range: the real close
    d2 = daily.assign(close=m2["close"].iloc[-1], high=m2["high"].max(), low=m2["low"].min())
    y = HI.mark_auction_extended(d2, m2).iloc[0]
    assert not bool(y["auction_extended"]) and y["high"] == d2["high"].iloc[0] and y["low"] == d2["low"].iloc[0]
    assert not HI.auction_extended_bars(m2).any()
    assert not HI.mark_auction_extended(daily, m.drop(columns="data_problem")).iloc[0]["auction_extended"]   # no evidence ⇒ no flag


def test_ensure_marked_marks_from_the_ltf_and_keeps_existing_marks():
    """DP-2: a replay's 15M (no column) is marked from its 5M exactly as live marks it at the source; marks already there are kept."""
    ts5 = pd.date_range("2030-01-07 09:15", "2030-01-07 15:25", freq="5min")
    c5 = np.r_[np.linspace(100, 101, len(ts5) - 3), [101.0, 101.0, 103.0]]
    o5 = np.r_[c5[0], c5[:-1]]
    m5 = pd.DataFrame({"timestamp": ts5, "open": o5, "high": np.maximum(o5, c5), "low": np.minimum(o5, c5), "close": c5})
    m5.loc[len(m5) - 3:len(m5) - 2, ["open", "high", "low", "close"]] = 101.0
    ts15 = pd.date_range("2030-01-07 09:15", "2030-01-07 15:15", freq="15min")
    m15 = pd.DataFrame({"timestamp": ts15, "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5})
    out = HI.ensure_marked(m15, [m5])
    want = HI.mark_data_problems(m15, None, "15M", finer=m5)
    assert out["data_problem"].tolist() == want["data_problem"].tolist()
    assert out["data_problem"].iloc[-1] == HI.CLOSE_PRINT and (out["data_problem"].iloc[:-1] == "").all()   # the 15:15 bar only
    pre = m15.assign(data_problem=[""] * (len(m15) - 1) + ["DP-1"])
    assert HI.ensure_marked(pre, [m5])["data_problem"].iloc[-1] == "DP-1"                       # a listed id wins
    assert HI.ensure_marked(m15, [None])["data_problem"].tolist() == HI.mark_data_problems(m15, None, "15M")["data_problem"].tolist()


@MIRRORS
def test_an_auction_extended_close_never_counts_in_the_lifecycle(mirror):
    """DP-1 / DECISIONS 87: the 15:15 bar of day 2 closes beyond the band only through the closing-auction print (beyond the day's
    traded range) ⇒ no 'beyond'; the same print inside the traded range is the session's real close ⇒ 'beyond'."""
    f = _mirror(mirror)[0]
    day2 = [116.0, 116.5, 117.0, 116.5] * 6                                # bars 25 … 48: below the band (118–118.3)
    tail = [116.0] * 8 + day2 + [119.0]                                    # bars 17 … 24 (day 1), 25 … 48, 49 = 15:15 of day 2
    for traded_up, want in ((False, []), (True, [(49, "beyond")])):
        closes = [f(c) for c in HEAD + tail]
        hk = {30: f(119.5)} if traded_up else {}                           # bar 30 trades up to 119.5 ⇒ the print is inside the range
        m = m15_from(closes, wick=0.3, **({"lows": hk} if mirror else {"highs": hk}))
        m.loc[49, "open"] = f(117.0)
        m.loc[49, ["high", "low"]] = [max(f(117.0), f(119.0)), min(f(117.0), f(119.0))]
        m["data_problem"] = ""
        m.loc[49, "data_problem"] = HI.CLOSE_PRINT
        piv = [P(_mirror(mirror)[1](k), f(px), b, c) for k, px, b, c in PIVS]
        lv = LV.Levels(res_of(m, piv, piv))
        Z = [L for L in lv.L if abs(L.anchor - f(118.0)) < 1e-6][0]
        assert [e for e in _ev(Z) if e[0] >= 25] == want
        assert bool(lv.ax[49]) is (not traded_up)


@MIRRORS
def test_a_false_break_extreme_is_internal_only_from_its_close_back(mirror):
    """DECISIONS 94 (2): a high made during an excursion above the band (its 1H candle 20–23 stays entirely above it — no visit) is
    EXTERNAL while the excursion runs and INTERNAL from the 15M close back inside on (no look-ahead); the same extreme on a copy of
    the object whose base comes after it is never internal (made before the object existed); an auction-extended close back never
    ends the excursion."""
    import dataclasses
    from types import SimpleNamespace as NS
    f, sw = _mirror(mirror)
    tail = [119.0, 120.0, 121.0, 121.5, 121.7, 121.2, 120.5, 119.0, 117.5, 117.0]   # 17 … 24 above (below the external 122), 25 back
    m, lv, Z = _case(mirror, tail)
    lo, hi = Z.lo, Z.hi
    assert Z.role_at(25) == Z.role0 and Z.count("flip", 26) == 0
    x = NS(kind=sw("H"), price=f(121.9), bar=21, confirm_bar=23, close=f(121.7), clo=None, chi=None, h1=None, xbar=21)
    clo, chi = lv._candle_range(NS(**{**vars(x), "h1": int(lv.h1_of[21])}), 24)
    assert not (clo <= hi and chi >= lo)                                  # its 1H candle never traded inside: no visit
    assert not lv._internal(x, Z, lo, hi, 24)                             # still running at 24 ⇒ external
    assert lv._internal(x, Z, lo, hi, 25)                                 # closed back at 25 ⇒ a false-break extreme
    late = dataclasses.replace(Z, base_ts=None, base_bar=22, events=[])    # the object's base after the extreme
    assert not lv._internal(x, late, lo, hi, 26)
    ax = lv.ax.copy()
    lv.ax[25] = True                                                       # the close back is an auction-extended print
    lv.__dict__.pop("_back_memo", None)
    try:
        assert not lv._internal(x, Z, lo, hi, 25) and lv._internal(x, Z, lo, hi, 26)
    finally:
        lv.ax[:] = ax
        lv.__dict__.pop("_back_memo", None)
