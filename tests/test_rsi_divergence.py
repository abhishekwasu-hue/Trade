"""K-RSI (KB K10.4, pending Abhi) — rsi2.engine.Divergence: regular RSI divergence facts on swings2 pivots.

Synthetic cases (always run): mirror bear / bull, equal-high double top, equal RSI counts / a new RSI extreme does not, bar window and the
cap-rejected log, hidden OFF by default, multiple-divergence count, commitment-candle confirmation, no look-ahead (real swings2 pivots,
data cut at many bars), JSON-safe output, the chart and the dashboard overlay. Real data (private trade-data; skipped cleanly when absent):
12-Oct NIFTY 15M spot — the module's reading of the 12-Oct spike high vs the 9-Oct push high is REPORTED, never asserted to pass
(thresholds are never tuned to make a golden day pass); 13 Oct — skipped with the reason when the export is missing or partial.
"""
import glob
import json
import os

import numpy as np
import pandas as pd
import pytest

from rsi2 import charts as RC
from rsi2 import engine as RE
from rsi2 import settings as RS
from swings2.engine import Pivot
from tests.test_pivots_dc import m15_from, walk

TD = os.environ.get("TRADE_DATA", "/home/user/trade-data")
S0 = {"div_degrees": (0,), "warmup_bars": 0}


# ------------------------------------------------------------------------------------------------ synthetic helpers
def frame(n, highs=None, lows=None):
    """Flat doji bars (open = close = 100, high 101, low 99 ⇒ MR 2, band tolerance 0.4) with chosen wicks; 25 bars per session."""
    df = m15_from([100.0] * n)
    for i, v in (highs or {}).items():
        df.loc[i, "high"] = v
    for i, v in (lows or {}).items():
        df.loc[i, "low"] = v
    return df


def piv(df, kind, bar, confirm=None, degree=0):
    price = float(df["high"].iloc[bar] if kind == "H" else df["low"].iloc[bar])
    ts = pd.Timestamp(df["timestamp"].iloc[bar])
    c = bar + 1 if confirm is None else confirm
    return Pivot(degree, kind, price, bar, ts, c, pd.Timestamp(df["bar_end"].iloc[c]), 1.0, 2.0, "normal")


def res_of(df, pivots):
    days = pd.to_datetime(df["timestamp"]).dt.normalize().unique()
    out = {0: [], 1: [], 2: []}
    for p in pivots:
        out[p.degree].append(p)
    return {"pivots": out, "segments": {pd.Timestamp(d): 0 for d in days}}


def rsi_with(n, vals, base=50.0):
    r = np.full(n, base)
    for i, v in vals.items():
        r[i] = v
    return r


def build(df, pivots, rsi, **s):
    return RE.Divergence(df, "15M", s={**S0, **s}, res=res_of(df, pivots), rsi=rsi, areas=False)


def bear_case(h2=112.0, r1=70.0, r2=65.0, n=40, b=25):
    """H 110 @ 10 · L 95 @ 15 · H h2 @ b; RSI r1 @ 10, r2 @ b."""
    df = frame(n, highs={10: 110.0, b: h2}, lows={15: 95.0})
    ps = [piv(df, "H", 10), piv(df, "L", 15), piv(df, "H", b)]
    return df, ps, rsi_with(n, {10: r1, b: r2})


def bull_case(l2=88.0, r1=30.0, r2=35.0, n=40, b=25):
    """Mirror: L 90 @ 10 · H 105 @ 15 · L l2 @ b; RSI r1 @ 10, r2 @ b."""
    df = frame(n, highs={15: 105.0}, lows={10: 90.0, b: l2})
    ps = [piv(df, "L", 10), piv(df, "H", 15), piv(df, "L", b)]
    return df, ps, rsi_with(n, {10: r1, b: r2})


def pair(D, t, d=0, side="bear"):
    return next(x["pair"] for x in D.read(t)["latest"] if x["degree"] == d and x["side"] == side)


# ------------------------------------------------------------------------------------------------ settings / API
def test_settings_defaults_match_the_spec():
    s = RS.load()
    assert s["period"] == 14 and s["div_rsi_window"] == 2 and s["div_hidden"] is False and s["div_show"] is True
    assert s["div_bars"] == {"15M": (3, 50), "1H": (3, 35), "5M": (3, 60)}             # legacy what-if only (div_bar_window)
    assert s["div_bar_window"] is False                                         # Abhi (final): no bar counts / minimum gaps
    for k in ("div_rsi_window", "div_bars", "div_hidden", "div_degrees", "div_show"):
        assert k in RS.REGISTER
    assert hasattr(RE.RSI, "known") and callable(RE.RSI.known)                   # facts.dossier API unchanged


# ------------------------------------------------------------------------------------------------ mirror cases
def test_regular_bearish_forming_then_confirmed_by_right_side_bars():
    df, ps, r = bear_case()
    D = build(df, ps, r)
    f = pair(D, 25)
    assert f["is_div"] and f["status"] == "forming" and f["type"] == "regular" and f["price_rel"] == "higher high"
    c = pair(D, 26)
    assert c["is_div"] and c["status"] == "confirmed" and c["status_by"] == "right_side_bars"
    assert (c["L1"]["bar"], c["L2"]["bar"], c["bars"]) == (10, 25, 15)
    assert (c["L1"]["rsi"], c["L2"]["rsi"], c["rsi_diff"]) == (70.0, 65.0, -5.0)
    assert c["count"] == 1 and c["L1"]["price"] == 110.0 and c["L2"]["price"] == 112.0
    assert RE.div_label(c) == "bear div · confirmed · 15 bars · RSI 70.00 → 65.00"
    assert [x["status"] for x in D.history(26)] == ["confirmed"]


def test_regular_bullish_mirror():
    df, ps, r = bull_case()
    D = build(df, ps, r)
    c = pair(D, 26, side="bull")
    assert c["is_div"] and c["type"] == "regular" and c["price_rel"] == "lower low" and c["rsi_diff"] == 5.0
    assert RE.div_label(c).startswith("bull div · confirmed · 15 bars")


def test_divergence_needs_a_new_price_extreme_no_tolerance_band():
    """Abhi (final): price makes a NEW extreme while RSI does not exceed its previous one — an equal or slightly lower high is not."""
    df, ps, r = bear_case(h2=110.0)
    c = pair(build(df, ps, r), 26)
    assert c["price_rel"] == "equal high" and not c["is_div"]
    df, ps, r = bear_case(h2=110.3)
    c = pair(build(df, ps, r), 26)
    assert c["price_rel"] == "higher high" and c["is_div"]
    df, ps, r = bear_case(h2=109.0)                                             # beyond the tolerance below ⇒ lower high
    c = pair(build(df, ps, r), 26)
    assert c["price_rel"] == "lower high" and not c["is_div"] and "price made a lower high" in c["reason"]


def test_equal_rsi_high_is_divergence_higher_rsi_is_not():
    df, ps, r = bear_case(r2=70.0)
    c = pair(build(df, ps, r), 26)
    assert c["is_div"] and c["rsi_diff"] == 0 and "RSI 70.00 = 70.00" in RE.div_label(c)
    df, ps, r = bear_case(r2=75.0)
    c = pair(build(df, ps, r), 26)
    assert not c["is_div"] and c["reason"] == "RSI made a new high with price (75.00 > 70.00)"
    st = next(x["statement"] for x in build(df, ps, r).read(26)["latest"] if x["side"] == "bear")
    assert st.startswith("no bear divergence") and "75.00 > 70.00" in st


def test_equal_rsi_low_is_divergence_lower_rsi_is_not():
    df, ps, r = bull_case(r2=30.0)
    c = pair(build(df, ps, r), 26, side="bull")
    assert c["is_div"] and c["rsi_diff"] == 0
    df, ps, r = bull_case(r2=25.0)
    c = pair(build(df, ps, r), 26, side="bull")
    assert not c["is_div"] and c["reason"] == "RSI made a new low with price (25.00 < 30.00)"


def test_no_minimum_rsi_difference():
    df, ps, r = bear_case(r2=69.99)
    c = pair(build(df, ps, r), 26)
    assert c["is_div"] and c["rsi_diff"] == -0.01


# ------------------------------------------------------------------------------------------------ window / cap log
@pytest.mark.parametrize("b,ok,cap", [(12, False, "min"), (13, True, None), (60, True, None), (61, False, "max")])   # Abhi RSI-2: min 3
def test_bar_window_and_cap_rejected_log(b, ok, cap):
    n = 70
    df = frame(n, highs={10: 110.0, b: 112.0}, lows={11: 95.0})
    ps = [piv(df, "H", 10), piv(df, "L", 11), piv(df, "H", b)]
    D = build(df, ps, rsi_with(n, {10: 70.0, b: 65.0}), div_bar_window=True)   # legacy what-if
    c = pair(D, b + 1)
    assert c["bars"] == b - 10 and c["is_div"] is ok and c["cap"] == cap
    assert pair(build(df, ps, rsi_with(n, {10: 70.0, b: 65.0})), b + 1)["is_div"]   # Abhi (final): no bar window by default
    logged = [x for x in D.cap_log() if x["L2"]["bar"] == b]
    assert bool(logged) is (cap is not None) and (not logged or logged[0]["reason"].startswith("rejected only by the bar window"))
    assert all(x["L2"]["bar"] != b for x in D.history()) is (not ok)


def test_window_per_timeframe_from_settings():
    n = 70
    df = frame(n, highs={10: 110.0, 50: 112.0}, lows={20: 95.0})
    ps = [piv(df, "H", 10), piv(df, "L", 20), piv(df, "H", 50)]
    r = rsi_with(n, {10: 70.0, 50: 65.0})
    one_h = RE.Divergence(df, "1H", s={**S0, "div_bar_window": True}, res=res_of(df, ps), rsi=r, areas=False)
    assert one_h.win == (3, 35) and pair(one_h, 51)["cap"] == "max"           # 40 bars > 35
    assert pair(build(df, ps, r), 51)["is_div"]                                  # 15M: 40 ≤ 50


def test_a_higher_high_between_breaks_consecutiveness():
    df, ps, r = bear_case()
    df.loc[20, "high"] = 115.0                                                    # a more extreme price between the two pivots
    c = pair(build(df, ps, r), 26)
    assert not c["is_div"] and not c["consecutive"]


# ------------------------------------------------------------------------------------------------ types / count / status
def test_hidden_divergence_off_by_default_and_reported_when_on():
    df, ps, r = bear_case(h2=105.0, r2=75.0)                                      # lower high + higher RSI
    c = pair(build(df, ps, r), 26)
    assert not c["is_div"] and c["type"] is None
    c = pair(build(df, ps, r, div_hidden=True), 26)
    assert c["is_div"] and c["type"] == "hidden" and RE.div_label(c).startswith("hidden bear div")


def test_multiple_divergence_count():
    n = 60
    df = frame(n, highs={10: 110.0, 25: 112.0, 40: 114.0}, lows={15: 95.0, 30: 96.0})
    ps = [piv(df, "H", 10), piv(df, "L", 15), piv(df, "H", 25), piv(df, "L", 30), piv(df, "H", 40)]
    D = build(df, ps, rsi_with(n, {10: 70.0, 25: 65.0, 40: 60.0}))
    assert [x["count"] for x in D.history()] == [1, 2]


def test_dominant_commitment_candle_confirms_before_the_right_side_bars():
    n = 40
    df = frame(n, highs={10: 110.0}, lows={15: 95.0})
    df.loc[25, ["open", "high", "low", "close"]] = [100.0, 112.0, 99.5, 103.0]    # the push high (up candle)
    df.loc[26, ["open", "high", "low", "close"]] = [104.0, 104.5, 97.5, 98.0]     # bearish engulfing close away from it
    ps = [piv(df, "H", 10), piv(df, "L", 15), piv(df, "H", 25, confirm=30)]
    D = build(df, ps, rsi_with(n, {10: 70.0, 25: 65.0}))
    assert pair(D, 25)["status"] == "forming"
    c = pair(D, 26)
    assert c["status"] == "confirmed" and c["status_by"] == "commitment_candle" and c["commitment"]["form"] == "engulf"
    assert c["is_div"] and c["known_bar"] == 26
    assert len([x for x in D.history() if x["L2"]["bar"] == 25]) == 1             # the later swings2 confirmation adds no duplicate
    log = D.read(26)["status_log"]
    assert {"degree": 0, "side": "bear", "status": "confirmed", "status_by": "commitment_candle"} in log


# ------------------------------------------------------------------------------------------------ RSI window (± div_rsi_window bars)
def _second_rsi(peak_at, val=68.0, confirm=30, n=40):
    """H 110 @ 10 · L 95 @ 15 · H 112 @ 25 (confirmed at `confirm`); RSI 70 @ 10, 60 @ 25 and `val` at bar `peak_at`."""
    df = frame(n, highs={10: 110.0, 25: 112.0}, lows={15: 95.0})
    ps = [piv(df, "H", 10), piv(df, "L", 15), piv(df, "H", 25, confirm=confirm)]
    D = build(df, ps, rsi_with(n, {10: 70.0, 25: 60.0, peak_at: val}))
    return pair(D, confirm)["L2"]


@pytest.mark.parametrize("off", [1, 2, -2, 3, -3])
def test_rsi_at_the_swing_is_its_extreme_inside_the_swings_own_span(off):
    """Abhi (final): RSI AT the swing — the RSI extreme inside the swing's own span (after the opposite swing, up to the bar the swing is
    known), no ±bar count."""
    x = _second_rsi(25 + off, confirm=30)
    assert x["rsi"] == 68.0 and x["rsi_bar"] == 25 + off


def test_rsi_before_the_opposite_swing_is_not_this_swings():
    x = _second_rsi(14)                                                          # bar 14 is before the low at 15 ⇒ another swing's RSI
    assert x["rsi"] == 60.0 and x["rsi_bar"] == 25


def test_rsi_window_capped_at_the_swings2_confirm_bar():
    x = _second_rsi(27, confirm=26)                                              # peak 2 bars right, but the pivot confirmed 1 bar right
    assert x["rsi"] == 60.0 and x["rsi_bar"] == 25
    x = _second_rsi(26, confirm=26)                                              # the confirm bar itself is closed ⇒ used
    assert x["rsi"] == 68.0 and x["rsi_bar"] == 26


def test_with_area_never_mutates_stored_records(walk_frame):
    D = RE.Divergence(walk_frame, "15M")
    a = D.history(areas=True)
    assert a and all("area" in x for x in a)
    b = D.history(areas=False)
    assert all("area" not in x for x in b)
    assert all("area" not in x for x in D.events)
    r = D.read(D.events[-1]["known_bar"])
    assert all("area" not in x for x in D.events)
    assert all("area" in x for x in r["divergences"])


def test_absence_statements_when_no_pivots():
    df = frame(30)
    D = build(df, [], rsi_with(30, {}))
    r = D.read(29)
    assert r["divergences"] == [] and all(x["statement"].startswith("no ") for x in r["latest"])


# ------------------------------------------------------------------------------------------------ no look-ahead (real swings2 pivots)
def _canon(x):
    return json.dumps(x, sort_keys=True, allow_nan=False)


@pytest.fixture(scope="module")
def walk_frame():
    return m15_from(walk(25 * 40, 3, step=3.0))


def test_no_lookahead_cut_at_any_bar_never_changes_earlier_outputs(walk_frame):
    m15 = walk_frame
    full = RE.Divergence(m15, "15M", areas=False)
    assert full.events                                                           # (rejects: only the legacy bar-window what-if)
    n = len(m15)
    for c in (n - 1 - 7 * k for k in range(0, 40, 4)):
        cut = RE.Divergence(m15.iloc[:c + 1], "15M", areas=False)
        for t in range(c - 30, c + 1):
            assert _canon(cut.read(t)) == _canon(full.read(t)), (c, t)
            assert _canon(cut.history(t)) == _canon(full.history(t)), (c, t)
            assert _canon(cut.cap_log(t)) == _canon(full.cap_log(t)), (c, t)


def test_only_forming_turns_into_confirmed(walk_frame):
    """A confirmed divergence never changes or disappears later; before its known bar the same pair can only have been forming."""
    D = RE.Divergence(walk_frame, "15M", areas=False)
    for e in D.events:
        k = e["known_bar"]
        for t in range(k, min(k + 40, D.n)):
            assert any(x is e for x in D.history(t))
        for t in range(max(e["L2"]["bar"], k - 10), k):
            x = (D.latest.get(t) or {}).get((e["degree"], e["side"]))
            if x is not None and x["L1"]["bar"] == e["L1"]["bar"] and x["L2"]["bar"] == e["L2"]["bar"]:
                assert x["status"] == "forming"


def test_areas_are_causal_and_na_with_reason(walk_frame):
    m15 = walk_frame
    full = RE.Divergence(m15, "15M")
    e = full.events[-1]
    k = e["known_bar"]
    cut = RE.Divergence(m15.iloc[:k + 1], "15M")
    a, b = full.with_area(dict(e)), cut.with_area(dict(next(x for x in cut.events if x["known_bar"] == k and x["L2"] == e["L2"])))
    assert a["area"] == b["area"] and a["area"]["status"] in ("in", "at", "away", "NA")
    if a["area"]["status"] == "NA":
        assert a["area"]["reason"]


def test_json_safe(walk_frame):
    D = RE.Divergence(walk_frame, "15M", areas=False)
    for t in range(0, D.n, 9):
        json.dumps(D.read(t), allow_nan=False)
    json.dumps(D.history(), allow_nan=False)
    json.dumps(D.cap_log(), allow_nan=False)
    json.dumps(D.with_area(dict(D.events[0])), allow_nan=False)


# ------------------------------------------------------------------------------------------------ chart + dashboard (display only)
def test_review_chart_has_rsi_pane_70_30_labels_and_cap_lines():
    n = 40
    df = frame(n, highs={10: 110.0, 25: 112.0, 29: 113.0}, lows={15: 95.0, 27: 96.0})
    ps = [piv(df, "H", 10), piv(df, "L", 15), piv(df, "H", 25), piv(df, "L", 27), piv(df, "H", 29)]
    D = build(df, ps, rsi_with(n, {10: 70.0, 25: 65.0, 29: 60.0}), div_bars={"15M": (5, 50)}, div_bar_window=True)   # legacy cap line
    divs, caps = D.history(), D.cap_log()
    assert len(divs) == 1 and len(caps) == 1
    fig = RC.div_figure(D.df, D.rsi, divs, caps, "t")
    ys = sorted(s.y0 for s in fig.layout.shapes)
    assert ys == [30, 70]
    texts = [a.text for a in fig.layout.annotations]
    assert "bear div · confirmed · 15 bars · RSI 70.00 → 65.00" in texts and "cap 4 bars" in texts
    rows = RC.div_rows(divs, caps)
    assert rows[0]["pivot 2"].endswith("112.00 · RSI 65.00") and rows[1]["kind"].startswith("cap-rejected")
    fig = RC.div_figure(D.df, D.rsi, [], [], "t")
    assert "no divergence" in [a.text for a in fig.layout.annotations]


def test_dashboard_overlay_display_only(walk_frame):
    from bot_view import rsi_div_overlay
    from tradingview_chart import build_lightweight_chart_html
    df = walk_frame.drop(columns=["bar_end"]).assign(volume=0)
    now = pd.Timestamp(df["timestamp"].iloc[-1]) + pd.Timedelta(hours=1)
    lines, rsi, cap = rsi_div_overlay(df, "15minute", now)
    assert lines and len(rsi) == len(df) and cap.startswith("RSI divergences")
    assert {"t0", "t1", "p0", "p1", "rt0", "rt1", "r0", "r1", "color", "label"} <= set(lines[0])
    assert rsi_div_overlay(df, "30minute", now) == ([], None, None)
    html = build_lightweight_chart_html(df, rsi_series=rsi, rsi_divs=lines, rsi_levels=(30, 70))
    assert lines[0]["label"].split(" · ")[0] in html


def test_chart_html_unchanged_without_divergences(walk_frame):
    from tradingview_chart import build_lightweight_chart_html
    df = walk_frame.drop(columns=["bar_end"]).assign(volume=0)
    base = build_lightweight_chart_html(df)
    assert build_lightweight_chart_html(df, rsi_divs=None) == base == build_lightweight_chart_html(df, rsi_divs=[])
    assert "K-RSI" not in base and "__RSI_DIVS__" not in base
    one = [{"t0": df["timestamp"].iloc[10], "t1": df["timestamp"].iloc[30], "p0": 1.0, "p1": 2.0, "rt0": df["timestamp"].iloc[10],
            "rt1": df["timestamp"].iloc[30], "r0": 70.0, "r1": 65.0, "color": "#ef5350", "label": "bear div"}]
    html = build_lightweight_chart_html(df, rsi_series=pd.Series(50.0, index=df.index), rsi_divs=one)
    assert html.count("K-RSI divergences") == 2 and "__RSI_DIVS__" not in html


def test_dashboard_overlay_is_cached_per_data_and_settings(walk_frame, monkeypatch):
    import page_dashboard as PD
    calls = []
    monkeypatch.setattr(PD, "rsi_div_overlay", lambda df, tf, now, s=None: calls.append(len(df)) or ([], None, "cap"))
    PD._rsi_div_overlay_cached.clear()
    df = walk_frame.drop(columns=["bar_end"]).assign(volume=0)
    now = pd.Timestamp(df["timestamp"].iloc[-1]) + pd.Timedelta(hours=1)
    for _ in range(3):
        assert PD._rsi_div_overlay_keyed("NIFTY", df, "15minute", now) == ([], None, "cap")
    assert len(calls) == 1
    df2 = df.copy()
    df2.loc[df2.index[-1], "close"] += 1.0                                       # new data ⇒ recomputed
    PD._rsi_div_overlay_keyed("NIFTY", df2, "15minute", now)
    PD._rsi_div_overlay_keyed("BANKNIFTY", df, "15minute", now)
    assert len(calls) == 3
    PD._rsi_div_overlay_cached.clear()


def test_owner_has_no_dates_and_no_second_rsi():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "rsi2", "engine.py"), encoding="utf-8").read()
    assert "def divergence" not in src and src.count("def rsi_segmented") == 1


# ------------------------------------------------------------------------------------------------ real data (private; skipped when absent)
NIFTY_INPUTS = [os.path.join(TD, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"),
                os.path.join(TD, "upstox", "NIFTY_1m_illustration_2026-10-09_2026-10-09.csv.gz"),
                os.path.join(TD, "live_export", "2026-10-13", "NIFTY_1minute.parquet")]
NIFTY_13 = sorted(glob.glob(os.path.join(TD, "live_export", "*", "oe_index_5min_NIFTY.parquet")))


@pytest.fixture(scope="module")
def nifty():
    if not all(os.path.exists(p) for p in NIFTY_INPUTS):
        pytest.skip("private trade-data NIFTY 1m files not present")
    from scripts import rsi_divergence_check as CHK
    m15, m1 = CHK.load(NIFTY_INPUTS + NIFTY_13[-1:])
    return m15, RE.Divergence(m15, "15M", df1m=m1)


def _bar(m15, ts):
    hit = np.flatnonzero(pd.to_datetime(m15["timestamp"]).to_numpy() == np.datetime64(pd.Timestamp(ts)))
    return int(hit[0]) if len(hit) else None


def test_golden_12_oct_nifty_15m_spike_high_vs_9_oct_push_high_reported(nifty):
    """Reports (prints) the bear-side facts at the 12-Oct 09:15 spike high and the next bar. No expected pass is hard-coded: whether this
    is a divergence is Abhi's call (✅ / ✏️ on the review chart); the bar window is never tuned to make it pass."""
    m15, D = nifty
    t = _bar(m15, "2026-10-12 09:15")
    if t is None:
        pytest.skip("12-Oct 09:15 bar not in the data")
    for k in (t, t + 1):
        r = D.read(k)
        json.dumps(r, allow_nan=False)
        bear = [x for x in r["latest"] if x["side"] == "bear"]
        assert len(bear) == len(D.degrees)
        print(f"\n12-Oct read at {r['asof']} (RSI {r['rsi']}):")
        for x in bear:
            p = x.get("pair") or {}
            print(f"  D{x['degree']}: {x['statement']}" + (f" | L1 {p['L1']['time']} {p['L1']['price']} RSI {p['L1']['rsi']} · L2 "
                                                            f"{p['L2']['time']} {p['L2']['price']} RSI {p['L2']['rsi']} · {p['bars']} bars"
                                                            if p else ""))


def test_golden_13_oct_skipped_unless_full_session(nifty):
    m15, D = nifty
    ts = pd.to_datetime(m15["timestamp"])
    day = ts[ts.dt.normalize() == pd.Timestamp("2026-10-13")]
    if not len(day):
        pytest.skip("no 13-Oct data exported yet")
    r = D.read(int(day.index[-1]))
    print(f"\n13-Oct read at {r['asof']} (RSI {r['rsi']}): " + " | ".join(x["statement"] for x in r["latest"] if x["side"] == "bear"))
    if day.iloc[-1].strftime("%H:%M") < "15:00":
        pytest.skip(f"13-Oct export is partial (data to {day.iloc[-1] + pd.Timedelta(minutes=15):%H:%M}); the golden 13-Oct read "
                    "(RSI ≈ 80 with price, no divergence in the zone) needs the full session")
