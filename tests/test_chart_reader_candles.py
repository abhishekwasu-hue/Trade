"""Candle-by-candle (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §5): synthetic candles ⇒ बरोबर labels, leg मालिका, zone story."""
import pandas as pd

from chart_reader import candles as CC

MR = 1.0
SELL_ZONE = {"id": "S1", "zid": "S1", "low": 109.5, "high": 110.5}


def df(rows, start="2026-03-10 09:15"):
    ts = pd.date_range(start, periods=len(rows), freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                         "close": [r[3] for r in rows]})


def test_series_reads_every_closed_candle():
    out = CC.series(df([(100, 101, 99.8, 100.9), (100.9, 101, 99, 99.1), (99.1, 99.6, 98.6, 99.1)]), MR)
    assert [x["control"] for x in out] == ["buyers", "sellers", "indecision"]
    assert all({"cl", "body", "upper_wick", "lower_wick", "size_mr", "line", "ts"} <= set(x) for x in out)


def test_tags_for_bear_side_at_selling_zone():
    assert CC.tag(110, 110.9, 109.8, 110.2, -1, SELL_ZONE, MR) == "sweep"                 # zone वर wick, close परत आत
    assert CC.tag(109.8, 110.3, 108.4, 108.5, -1, SELL_ZONE, MR) == "sellers close"
    assert CC.tag(109.0, 110.2, 108.9, 109.2, -1, SELL_ZONE, MR) == "wick rejection"
    assert CC.tag(109.0, 109.6, 108.2, 109.05, -1, SELL_ZONE, MR) == "absorption"          # मोठी range, body छोटी
    assert CC.tag(109.0, 109.6, 108.9, 109.5, -1, SELL_ZONE, MR) == "buyers push"
    assert CC.tag(100, 100.9, 98.4, 100.5, 1, None, MR) == "wick rejection"               # bull: lower wick


def test_leg_series_correction_tiring():
    # correction वर: पहिला leg मोठा आणि स्वच्छ, शेवटचा leg लहान, overlapping, वरचे wicks, जास्त effort कमी result
    rows = [(100, 101.2, 99.9, 101), (101, 102.2, 100.9, 102), (102, 103.3, 101.9, 103), (103, 104.2, 102.9, 104),
            (104, 104.1, 102.5, 102.6), (102.6, 102.7, 101.8, 101.9),
            (101.9, 103.4, 101.7, 102.3), (102.3, 103.5, 101.9, 102.4), (102.4, 103.6, 102.0, 102.6)]
    r = CC.leg_read(df(rows), [(0, 3), (6, 8)], 1, MR)
    sg = r["signs"]
    assert sg["legs_shrinking"] and sg["more_overlap"] and sg["counter_wicks"] and sg["failed_extension"] and sg["absorption"]
    assert r["tired"] and "थकतोय" in r["line"]
    clean = CC.leg_read(df(rows[:4] + rows[:4]), [(0, 3), (4, 7)], 1, MR)
    assert not clean["tired"]


def test_zone_story_three_to_six_candles_and_conclusion():
    rows = [(105, 106, 104.8, 105.9), (105.9, 107.5, 105.8, 107.4), (107.4, 109.7, 107.3, 109.6),     # zone कडे
            (109.6, 110.9, 109.4, 110.2),                                                                # sweep
            (110.2, 110.4, 109.3, 109.6),                                                                # wick / small
            (109.6, 109.8, 107.9, 108.0)]                                                                # sellers close
    st = CC.zone_story(df(rows), SELL_ZONE, -1, MR)
    assert 3 <= len(st["bars"]) <= 6 and st["tags"][-1] == "sellers close" and "sweep" in st["tags"]
    assert "sellers परत" in st["line"]
    assert CC.zone_story(df(rows), None, -1, MR)["bars"] == []
