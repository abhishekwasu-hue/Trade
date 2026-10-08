"""Backtest visual review (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §5): reason codes, holdout, no-lookahead, review store round-trip, page filters."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from backtest_review import charts as BC
from backtest_review import reasons as RC
from backtest_review import scan as SC
from backtest_review import store as BS
from elliott.data_policy import HoldoutError


# ------------------------------------------------------------------ reason codes
@pytest.mark.parametrize("r,expect", [
    ({"entry": True, "grade": "A"}, ["ENTRY_A"]),
    ({"entry": True, "grade": "B"}, ["ENTRY_B"]),
    ({"why_no_entry": ["spot R:R 1:2.1 < 1:3", "reversal: no_touch"]}, ["RR<3", "NO_REVERSAL"]),
    ({"why_no_entry": ["active area नाही (ताज्या bars नी …)"]}, ["NO_AREA"]),
    ({"why_no_entry": ["09:15–09:30 opening window — entry नाही"]}, ["OPENING_WINDOW"]),
    ({"why_no_entry": ["⛔ [K3] count स्पष्ट: A-end / B च्या आत ⇒ pullback संपलेला नाही"]}, ["VETO_A_END"]),
    ({"why_no_entry": ["grade C (31)"]}, ["GRADE_C"]),
    ({"side_unclear": ["Elliott vote विरुद्ध (D1)"], "why_no_entry": ["grade C (40)"]}, ["SIDE_UNCLEAR", "GRADE_C"]),
    ({"why_no_entry": ["काहीतरी नवीन"]}, ["OTHER"]),
    ({}, ["OTHER"]),
])
def test_every_candidate_has_reason_codes(r, expect):
    assert RC.codes(r) == expect and all(c in RC.CODES for c in RC.codes(r))


def test_status_mapping():
    assert RC.status({"entry": True, "grade": "A"}) == "ENTRY"
    assert RC.status({"why_no_entry": ["grade C (30)"]}) == "C"
    assert RC.status({"why_no_entry": ["spot R:R 1:2 < 1:3"]}) == "REJECTED"


# ------------------------------------------------------------------ data policy
def _m1(start, days, base=100.0):
    ts = np.concatenate([pd.date_range(f"{d:%Y-%m-%d} 09:15", periods=375, freq="1min") for d in pd.bdate_range(start, periods=days)])
    c = base + np.sin(np.arange(len(ts)) / 50.0) * 5
    return pd.DataFrame({"timestamp": pd.to_datetime(ts), "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 0.0})


def test_holdout_period_raises():
    with pytest.raises(HoldoutError):
        SC.DP.check_range("2024-05-01", "2024-06-30", purpose="golden")
    with pytest.raises(HoldoutError):
        SC.load_period(_m1("2026-05-01", 5), "2026-05-04", "2026-05-08")


def test_warmup_never_includes_holdout_rows():
    df = pd.concat([_m1("2026-06-15", 10), _m1("2026-07-01", 5)], ignore_index=True)       # जून 2026 = holdout
    out = SC.load_period(df, "2026-07-01", "2026-07-07")
    assert len(out) and out["timestamp"].min() >= pd.Timestamp("2026-07-01")
    assert len(SC.load_period(_m1("2024-01-01", 5), "2024-01-01", "2024-01-05"))           # VAL चा शेवट ठीक


# ------------------------------------------------------------------ scan (stub evaluate / market_state)
def _trig(day="2026-10-07"):
    ts = pd.date_range(f"{day} 09:15", periods=24, freq="15min")
    c = np.linspace(100, 90, 24)
    return pd.DataFrame({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": c + 0.5, "high": c + 1, "low": c - 1, "close": c})


MS_OK = {"side": "bear_call", "side_reasons": [], "impulse": {"dir": -1, "from": 120.0, "to": 95.0, "from_ts": pd.Timestamp("2026-10-06 10:00"),
                                                           "to_ts": pd.Timestamp("2026-10-06 14:00"), "size_mr": 9.0},
         "correction": {"status": "correction", "retrace": 0.5, "extreme": 107.5, "labels": []}, "trend": {"dir": -1, "state": "trend"}}


def test_scan_day_candidates_trades_and_codes():
    trig = _trig()
    m1 = pd.DataFrame({"timestamp": pd.date_range("2026-10-01 09:15", "2026-10-07 15:29", freq="1min")})
    calls = []

    def ev(w, asof):
        calls.append(asof)
        k = len(calls)
        if k == 3:
            return {"entry": True, "grade": "A", "side": -1, "total": 64, "risk": {"entry": 98.0, "invalidation": 101.0,
                                                                                   "targets": [{"price": 88.0, "id": "IMPULSE-END"}], "rr": 3.3}}
        if k == 4:
            return {"entry": True, "grade": "B", "side": -1, "total": 50}                  # तोच impulse ⇒ trade पुन्हा नाही
        return {"entry": False, "side": -1, "why_no_entry": ["spot R:R 1:2.0 < 1:3"]}
    cands = SC.scan_day(m1, "2026-10-07", {}, trig=trig, eval_fn=ev, state_fn=lambda asof: MS_OK)
    assert len(cands) == len(trig) and all(c["codes"] for c in cands)
    assert cands[2]["status"] == "ENTRY" and cands[0]["codes"] == ["RR<3"]
    trs = SC.trades(cands)
    assert len(trs) == 1 and trs[0]["grade"] == "A"
    shallow = dict(MS_OK, correction={**MS_OK["correction"], "retrace": 0.2})
    assert SC.scan_day(m1, "2026-10-07", {}, trig=trig, eval_fn=ev, state_fn=lambda a: shallow) == []
    assert "candidates 24" in SC.day_story(cands, MS_OK)


def test_hindsight_target_sl_time():
    trig = _trig()
    c = {"side": -1, "bar_start": trig["timestamp"].iloc[2], "entry_px": 99.0, "inv": 101.5, "targets": [{"price": 95.0, "id": "x"}]}
    h = SC.hindsight(trig, c)
    assert h["result"] == "TARGET" and h["mfe"] > 0
    assert SC.hindsight(trig, dict(c, inv=99.2))["result"] == "SL"
    assert SC.hindsight(trig, dict(c, targets=[{"price": 10.0, "id": "x"}]))["result"] == "TIME"


# ------------------------------------------------------------------ charts: no-lookahead
def test_entry_chart_refuses_future_bars_and_renders():
    trig = _trig()
    c = {"side": -1, "bar_start": trig["timestamp"].iloc[10], "bar_end": trig["bar_end"].iloc[10], "entry_px": 95.0, "inv": 97.0,
         "targets": [{"price": 90.0, "id": "IMPULSE-END"}], "rr": 2.5, "grade": "B", "total": 50, "codes": ["ENTRY_B"], "impulse": None,
         "labels": [], "area": {"id": "TL-R1", "tool": "f", "low": 96.0, "high": 97.0, "slope": -0.4,
                                "anchors": [(str(trig["timestamp"].iloc[1]), 100.5), (str(trig["timestamp"].iloc[8]), 97.8)]},
         "trend": {"dir": -1, "state": "trend", "protected": {"kind": "H", "price": 101.0}}, "top_points": [("AQ", 16.0)]}
    fig = BC.entry_15m(trig, c, "x", strike=22700)                                         # पूर्ण दिवस दिला तरी…
    assert len(fig.data[0].x) == 11 and fig.layout.title.text == "x"                      # …chart entry bar वरच संपतो
    BC.assert_upto(trig.iloc[:11], c["bar_end"])
    with pytest.raises(AssertionError):
        BC.assert_upto(trig, c["bar_end"])                                                 # entry नंतरचे bars ⇒ lookahead


# ------------------------------------------------------------------ store round-trip (sqlite मध्ये Postgres SQL चं भाषांतर)
class _Cur:
    def __init__(self, c):
        self.c = c.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?").replace("DEFAULT NOW()", "DEFAULT CURRENT_TIMESTAMP")
        return self.c.execute(sql, tuple(str(p) if not isinstance(p, (int, float, str, type(None))) else p for p in params))

    def fetchall(self):
        return self.c.fetchall()


class _Conn:
    def __init__(self, c):
        self.c = c

    def cursor(self):
        return _Cur(self.c)

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()

    def close(self):
        pass


def test_review_buttons_saved_and_shown_again():
    db = sqlite3.connect(":memory:")
    cf = lambda: _Conn(db)                                                                 # noqa: E731
    assert BS.save_review("day:2026-10-07", "2026-10-07", "day", "WRONG", "14:00 bear_call सुटला",
                          {"time": "14:00", "side": "bear_call"}, "abc123", conn_factory=cf)
    t = BS.item_id("trade", "2026-10-07", "14:30", "bear_call")
    assert BS.save_review(t, "2026-10-07", "trade", "OK", "", None, "abc123", conn_factory=cf)
    assert BS.save_review(t, "2026-10-07", "trade", "UNCLEAR", "SL?", None, "abc123", conn_factory=cf)   # upsert: शेवटचं उत्तर
    r = BS.load_reviews(conn_factory=cf)
    assert r["day:2026-10-07"]["missed_trade"] == {"time": "14:00", "side": "bear_call"} and r[t]["verdict"] == "UNCLEAR"
    with pytest.raises(ValueError):
        BS.save_review("x", "2026-10-07", "day", "MAYBE", conn_factory=cf)
    with pytest.raises(ValueError):
        BS.save_review("x", "2026-10-07", "day", "WRONG", missed={"time": "", "side": "bear_call"}, conn_factory=cf)
    index = {"days": [{"date": "2026-10-07", "item_id": "day:2026-10-07", "trades": [{"item_id": t}]},
                      {"date": "2026-10-08", "item_id": "day:2026-10-08", "trades": []}]}
    pg = BS.progress(index, r)
    assert pg["days"] == (1, 2) and pg["trades"] == (1, 1)


def test_page_filters():
    import page_backtest_review as P
    index = {"days": [{"date": "a", "item_id": "day:a", "trades": [{"item_id": "t1"}]}, {"date": "b", "item_id": "day:b", "trades": []}]}
    rev = {"t1": {"verdict": "WRONG"}}
    assert [d["date"] for d in P.filter_days(index, rev, "फक्त trades")] == ["a"]
    assert [d["date"] for d in P.filter_days(index, rev, "फक्त ✘")] == ["a"]
    assert [d["date"] for d in P.filter_days(index, rev, "फक्त न तपासलेले")] == ["a", "b"]
    assert [d["date"] for d in P.filter_days(index, {**rev, "day:a": {"verdict": "OK"}, "day:b": {"verdict": "OK"}}, "फक्त न तपासलेले")] == []
