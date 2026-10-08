"""Golden Gallery G1–G6 (TRADE_GOLDEN_GALLERY_PROMPT): detectors (synthetic market_state), निवड (विविधता, hindsight नाही), data policy (VAL /
holdout नाही), golden_gallery store round-trip, page गट."""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import pytest

from backtest_review import gallery as GL
from backtest_review import store as BS
from tests.test_backtest_review import _Conn

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research"))


def _trig(close_last=100.0, o=98.0, h=101.0, low=96.0, n=40):
    ts = pd.date_range("2019-03-11 09:15", periods=n, freq="15min")
    c = np.full(n, 100.0)
    df = pd.DataFrame({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": c, "high": c + 1, "low": c - 1, "close": c})
    df.loc[n - 1, ["open", "high", "low", "close"]] = [o, h, low, close_last]
    return df


def _lab(n, a, b, t0, t1):
    return {"label": n, "from": a, "to": b, "from_ts": pd.Timestamp(t0), "to_ts": pd.Timestamp(t1)}


def _ms(labels, retrace, trend_dir=1, bos=None, ext=None, overlap=0.7, side=1):
    return {"impulse": {"dir": side, "from": 80.0, "to": 120.0, "from_ts": pd.Timestamp("2019-03-11 09:15"),
                        "to_ts": pd.Timestamp("2019-03-11 12:00"), "bos": bos, "size_mr": 8.0},
            "correction": {"status": "correction", "retrace": retrace, "extreme": ext, "labels": labels, "overlap": overlap},
            "trend": {"dir": trend_dir, "state": "trend"}, "side": "bull_put"}


def test_g1_zigzag_and_g2_expanded_flat():
    t = _trig(close_last=101.0, o=97.0, h=101.5, low=96.5)                  # bull reversal candle
    zz = [_lab("A", 120, 108, "2019-03-11 12:00", "2019-03-11 13:00"), _lab("B", 108, 114, "2019-03-11 13:00", "2019-03-11 14:00"),
          _lab("C", 114, 100, "2019-03-11 14:00", "2019-03-11 18:00")]
    hits = {h["setup"] for h in GL.detect(_ms(zz, 0.5), t, len(t) - 1, 4.0)}
    assert "G1" in hits
    flat = [_lab("A", 120, 108, "2019-03-11 12:00", "2019-03-11 13:00"), _lab("B", 108, 121, "2019-03-11 13:00", "2019-03-11 14:00"),
            _lab("C", 121, 106.5, "2019-03-11 14:00", "2019-03-11 18:00")]           # B > 1.05 A, C ने A low 1.5 = 0.375 MR ने sweep
    t2 = _trig(close_last=109.0, o=107.0, h=109.5, low=106.5)
    hits2 = {h["setup"] for h in GL.detect(_ms(flat, 0.3), t2, len(t2) - 1, 4.0)}
    assert "G2" in hits2 and "G1" not in hits2


def test_g4_flip_g6_simple_and_no_hits_without_reversal():
    t = _trig(close_last=101.0, o=97.0, h=101.5, low=96.5)
    hits = {h["setup"] for h in GL.detect(_ms([_lab("A", 120, 100, "2019-03-11 12:00", "2019-03-11 18:00")], 0.5, bos=100.5, ext=100.0),
                                           t, len(t) - 1, 4.0)}
    assert {"G4", "G6"} <= hits
    weak = _trig(close_last=96.6, o=100.5, h=101.0, low=96.5)                # bear candle ⇒ bull reversal नाही
    assert GL.detect(_ms([_lab("A", 120, 100, "2019-03-11 12:00", "2019-03-11 18:00")], 0.5, bos=100.5, ext=100.0), weak, len(weak) - 1, 4.0) == []
    assert GL.detect({**_ms([], 0.5), "correction": {"status": "origin_broken"}}, t, len(t) - 1, 4.0) == []


def test_select_diversity_and_no_hindsight():
    cands = []
    for k in range(12):
        cands.append({"setup": "G1", "bar_start": pd.Timestamp("2016-01-04") + pd.Timedelta(days=7 * (k % 4)) + pd.DateOffset(years=k % 3),
                      "side": 1 if k % 2 else -1, "rank": 100 - k, "hindsight": {"result": "SL" if k < 6 else "TARGET"}})
    out = GL.select(cands, per_setup=8)
    weeks = [pd.Timestamp(c["bar_start"]).strftime("%G-%V") for c in out]
    assert len(out) <= 8 and len(set(weeks)) == len(weeks)                    # एका आठवड्यात एकच
    assert {c["side"] for c in out} == {1, -1} and len({pd.Timestamp(c["bar_start"]).year for c in out}) >= 2
    shuffled = [dict(c, hindsight={"result": "TARGET"}) for c in cands]
    assert [c["bar_start"] for c in GL.select(shuffled, 8)] == [c["bar_start"] for c in out]   # hindsight बदलला तरी निवड तीच


def test_gallery_data_policy_no_val_no_holdout():
    import golden_gallery as GG
    from elliott.data_policy import HoldoutError
    ts = pd.concat([pd.Series(pd.date_range("2021-12-27 09:15", periods=375 * 3, freq="1min")),
                    pd.Series(pd.date_range("2022-01-03 09:15", periods=375, freq="1min"))])
    raw = pd.DataFrame({"timestamp": ts.values, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    d = GG.load_part(raw, "IS")
    assert d["timestamp"].max() < pd.Timestamp("2022-01-01")                  # VAL rows नाहीत
    GG.PARTS["bad"] = ("2024-05-01", "2024-06-30", "golden")
    with pytest.raises(HoldoutError):
        GG.load_part(raw, "bad")
    GG.PARTS.pop("bad")


def test_gallery_store_and_page_groups():
    db = sqlite3.connect(":memory:")
    cf = lambda: _Conn(db)                                                   # noqa: E731
    gid = BS.gallery_id("G1", "2019-03-11 14:30", "bull_put")
    assert BS.save_gallery(gid, "G1", "2019-03-11 14:30", "bull_put", "WRONG", "G6", "हा साधा pullback", conn_factory=cf)
    assert BS.save_gallery(gid, "G1", "2019-03-11 14:30", "bull_put", "GOLDEN", None, "", conn_factory=cf)
    r = BS.load_gallery(conn_factory=cf)
    assert r[gid]["verdict"] == "GOLDEN" and r[gid]["corrected_setup"] is None
    with pytest.raises(ValueError):
        BS.save_gallery(gid, "G1", "2019-03-11 14:30", "bull_put", "MAYBE", conn_factory=cf)
    with pytest.raises(ValueError):
        BS.save_gallery(gid, "G1", "2019-03-11 14:30", "bull_put", "OK", "G10", conn_factory=cf)
    import page_backtest_review as P
    g = P.gallery_groups({"examples": [{"setup": "G3", "id": "x"}, {"setup": "G1", "id": "y"}]})
    assert list(g)[:9] == [f"G{i}" for i in range(1, 10)] and len(g["G3"]) == 1


def test_review_and_gallery_reports():
    import review_report as RR
    idx = [{"settings_hash": "h1", "days": [{"item_id": "day:2026-10-07", "trades": [{"item_id": "t1"}, {"item_id": "t2"}]}]}]
    rev = {"t1": {"verdict": "OK"}, "t2": {"verdict": "WRONG", "reason": "trendline सुटली, area चुकला"},
           "day:2026-10-07": {"verdict": "WRONG", "reason": "14:00 trade सुटला", "missed_trade": {"time": "14:00", "side": "bear_call"}}}
    md = RR.review_md(idx, rev)
    assert "Trades:** तपासले 2/2 · ✔ 50%" in md and "trendline सुटली" in md and "14:00 bear_call" in md
    assert RR.classify("काहीतरी") == ["इतर"]
    gi = {"counts": {"G1": 3}, "examples": [{"id": "g1", "setup": "G1", "bar_start": "2019-03-11 14:30", "hindsight": {"result": "SL"}}]}
    gm = RR.gallery_md(gi, {"g1": {"verdict": "WRONG", "corrected_setup": "G6", "reason": "साधा pullback"}})
    assert "| G1 | zigzag / ABC end | 3 | 1 | 0 | 0 | 1 | G6 | 0 / 1 / 0 |" in gm


def test_real_data_g3_g5_detectors_find_known_examples():
    """Jul–Oct 2026 (contaminated, regression फक्त): 18 Sep 11:15 G5 (C मध्ये ending diagonal) आणि 18 Sep 10:15 G3 सापडतात."""
    p = os.path.join(os.environ.get("TRADE_DATA", "/home/user/trade-data"), "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz")
    if not os.path.exists(p):
        pytest.skip("trade-data नाही")
    import market_state as MS
    from elliott import data_policy as DP
    m1 = DP.filter_allowed(pd.read_csv(p, parse_dates=["timestamp"]), "golden")
    fr = MS.full_frames(m1)
    hits = GL.scan(m1, fr["15m"], fr, start="2026-09-18 09:15", end="2026-09-18 12:00")
    got = {(h["setup"], f"{h['bar_start']:%H:%M}") for h in hits}
    assert ("G5", "11:15") in got and ("G3", "10:15") in got
