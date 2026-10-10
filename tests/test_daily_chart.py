"""Daily (आजोबा degree) chart तथ्ये — Abhi 2026-10-09: no-lookahead, न भरलेले gaps, P1 ओळ, count gray ⇒ labels नाहीत."""
import numpy as np
import pandas as pd

from backtest_review import charts as BC
from backtest_review import daily as DL


def _daily(rows):
    ts = pd.date_range("2026-01-01", periods=len(rows), freq="D")
    return pd.DataFrame({"timestamp": ts, "open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                         "close": [r[3] for r in rows]})


def test_unfilled_gaps_full_partial_and_filled():
    up = _daily([(100, 102, 98, 101), (105, 108, 104, 107), (107, 109, 103.5, 108)])   # gap up 102–104: नंतर low 103.5 ⇒ उरला 102–103.5
    assert [(x["dir"], x["low"], x["high"]) for x in DL.unfilled_gaps(up)] == [("up", 102.0, 103.5)]
    dn = _daily([(108, 110, 106, 109), (95, 96, 94, 95), (95, 97, 93, 96)])              # gap down 96–106: नंतर high 97 ⇒ उरला 97–106
    assert [(x["dir"], x["low"], x["high"]) for x in DL.unfilled_gaps(dn)] == [("down", 97.0, 106.0)]
    fr2 = _daily([(100, 102, 98, 101), (105, 108, 104, 107), (103, 104, 101, 102)])      # पूर्ण भरला
    assert DL.unfilled_gaps(fr2) == []


def test_p1_line_gray_and_wave5():
    tr = {"dir": -1, "state": "trend", "protected": {"price": 23489.0, "kind": "H"}}
    s = DL.p1_line(tr, "LH / LL", {"gray": True, "why": "vote gray"})
    assert "DOWN" in s and "23,489" in s and "count gray" in s and "LH / LL" in s
    w5 = {"gray": False, "preferred": {"pattern": "impulse", "current_wave": "5"}}
    assert "wave 5 शक्य ⇒ कमी विश्वास" in DL.p1_line({**tr, "state": "testing"}, None, w5)


def _m1(days=45, seed=7):
    rng = np.random.default_rng(seed)
    out, px = [], 20000.0
    for d in pd.bdate_range("2026-01-05", periods=days):
        for m in range(375):
            px += rng.normal(0, 6)
            t = d + pd.Timedelta(hours=9, minutes=15 + m)
            out.append((t, px, px + abs(rng.normal(0, 3)), px - abs(rng.normal(0, 3)), px))
    return pd.DataFrame(out, columns=["timestamp", "open", "high", "low", "close"])


def test_facts_no_lookahead_and_chart_renders():
    m1 = _m1()
    asof = pd.bdate_range("2026-01-05", periods=45)[35] + pd.Timedelta(hours=15, minutes=30)
    a = DL.facts(m1[m1["timestamp"] < asof], asof)
    b = DL.facts(m1, asof)                                                  # भविष्याचा data असूनही तेच
    assert len(a["frame"]) == len(b["frame"]) and a["frame"]["timestamp"].iloc[-1] < asof
    assert a["line"] == b["line"] and a["struct"] == b["struct"]
    assert [(g["low"], g["high"]) for g in a["gaps"]] == [(g["low"], g["high"]) for g in b["gaps"]]
    fig = BC.daily_1d(b, "t")
    texts = " ".join(str(x.text) for x in fig.layout.annotations)
    assert "आजोबा (Daily)" in texts
    if b["count"].get("gray"):
        assert "count gray" in texts and "(1)" not in texts and "(A)" not in texts
