"""tests/test_r1_golden_lines.py — R1 (a) goldens for the shared line / band checks (facts/validity.py, trendlines2/two_touch.py,
decision3/levels.find_bands). Design docs/design/CHART_READER_AGENT.md §10 (TA1–TA4) and KB K4 / K6 golden fixtures.

Two parts:
  1. Synthetic fixtures (always run, CI): hand-built 15M bars with a known 2-touch line, a known band, a flip, and the negative cases.
  2. Real data (private trade-data; skipped cleanly when absent): Abhi's NIFTY 12 Oct trade — the 30 Sep → 6 Oct line found from its 2
     touches alone (no look-ahead: data truncated at the decision bar), its projected 3rd touch on 12 Oct 09:15, the ≈22,667 FUT supply
     band and the band + line confluence. Prices / dates live only in this fixture, never in the modules. Holdout never loaded.
"""
import os

import numpy as np
import pandas as pd
import pytest

from decision3 import levels as LV
from facts import validity as V
from trendlines2 import two_touch as TT

TD = os.environ.get("TRADE_DATA", "/home/user/trade-data")
SPOT_1M = [os.path.join(TD, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"),
           os.path.join(TD, "upstox", "NIFTY_1m_illustration_2026-10-09_2026-10-09.csv.gz"),
           os.path.join(TD, "live_export", "2026-10-13", "NIFTY_1minute.parquet")]
FUT_5M = os.path.join(TD, "live_export", "2026-10-13", "oe_futures_5min_NIFTY.parquet")


# ================================================================================================ 1. synthetic fixtures (CI)
def _frame(path, start="2026-01-05 09:15", wick=2.0):
    """Closes along `path` (list of prices); open = previous close; high / low = body ± wick. 25 bars per session (09:15–15:15)."""
    c = np.asarray(path, float)
    o = np.r_[c[0], c[:-1]]
    ts, d, k = [], pd.Timestamp(start), 0
    for _ in range(len(c)):
        ts.append(d + pd.Timedelta(minutes=15 * k))
        k += 1
        if k == 25:
            d, k = d + pd.Timedelta(days=1), 0
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + wick, "low": np.minimum(o, c) - wick, "close": c})


def _zigzag(points):
    """Linear interpolation between (bar, close) waypoints."""
    out = []
    for (b0, p0), (b1, p1) in zip(points[:-1], points[1:]):
        out += list(np.linspace(p0, p1, b1 - b0 + 1)[:-1])
    out.append(points[-1][1])
    return out


# descending highs on a line 1100 − 1·bar (peaks at bars 10 and 30), lows near 1040; the last bar is 45.
LINE_PTS = [(0, 1060), (10, 1098), (20, 1045), (30, 1078), (40, 1048), (45, 1052)]


def _line_df():
    return _frame(_zigzag(LINE_PTS))


def _peak_line(df, a, b):
    return (a, float(df["high"].iloc[a])), (b, float(df["high"].iloc[b]))


def test_synthetic_two_touch_line_found_valid_and_projects():
    df = _line_df()
    t = len(df) - 1
    a1, a2 = _peak_line(df, 10, 30)
    x = V.check_line(df, t, a1, a2, V.RES)
    assert x["valid"], x["reasons"]
    assert x["touch_count"] == 2 and not x["established"]
    assert x["valid_from"] == str(df["timestamp"].iloc[30 + 2])                    # anchor 2 confirmed k = 2 bars later
    nxt = x["projected_zone"]["next"]
    exp = a1[1] + (a2[1] - a1[1]) / 20 * (t + 1 - 10)
    assert nxt["offset"] == 1 and abs(nxt["mid"] - exp) < 0.01 and nxt["lo"] < exp < nxt["hi"]
    assert x["projected_zone"]["touch_number"] == 3
    found = TT.find_lines(df, t)
    assert any(f["valid"] and f["anchor1"]["bar"] == 10 and f["anchor2"]["bar"] == 30 for f in found)
    shown = TT.display_lines(df, t)                                                  # with the 20 → 40 support line (2 touches)
    assert len(shown) == 2 and any(x["anchor1"]["bar"] == 10 and x["side"] == V.RES for x in shown)


def test_synthetic_line_no_lookahead_truncation():
    df = _line_df()
    t = 40
    full = TT.find_lines(df, t)
    cut = TT.find_lines(df.iloc[:t + 1], t)
    key = [(x["anchor1"]["bar"], x["anchor2"]["bar"], x["valid"], x["touch_count"], (x["projected_zone"] or {}).get("next")) for x in full]
    assert key == [(x["anchor1"]["bar"], x["anchor2"]["bar"], x["valid"], x["touch_count"], (x["projected_zone"] or {}).get("next"))
                   for x in cut]
    assert not any(x["anchor2"]["bar"] > t - 2 for x in full)                       # unconfirmed pivots never anchor


def test_synthetic_line_third_touch_established():
    pts = [(0, 1060), (10, 1098), (20, 1045), (30, 1078), (40, 1048), (50, 1058), (56, 1030), (60, 1035)]   # bar 50 high = line
    df = _frame(_zigzag(pts))
    a1, a2 = _peak_line(df, 10, 30)
    x = V.check_line(df, len(df) - 1, a1, a2, V.RES)
    assert x["valid"] and x["touch_count"] == 3 and x["established"]


@pytest.mark.parametrize("case,reason", [
    ("between", "close_through_between_anchors"), ("steep", "too_steep"), ("broken", "broken"), ("spacing", "anchors_spacing_lt_min"),
    ("rising_highs", "against_trend_direction")])
def test_synthetic_line_rejections(case, reason):
    if case == "between":
        pts = [(0, 1060), (10, 1098), (15, 1060), (20, 1100), (25, 1050), (30, 1078), (40, 1048), (45, 1052)]
        df = _frame(_zigzag(pts))
        a1, a2 = _peak_line(df, 10, 30)
    elif case == "steep":
        pts = [(0, 1000), (10, 1200), (15, 1050), (20, 1100), (30, 1000)]
        df = _frame(_zigzag(pts))
        a1, a2 = _peak_line(df, 10, 20)
    elif case == "broken":
        pts = LINE_PTS[:-1] + [(44, 1100), (48, 1110)]
        df = _frame(_zigzag(pts))
        a1, a2 = _peak_line(df, 10, 30)
    elif case == "spacing":
        pts = [(0, 1060), (10, 1098), (12, 1080), (14, 1096), (20, 1050), (30, 1050)]
        df = _frame(_zigzag(pts))
        a1, a2 = _peak_line(df, 10, 14)
    else:
        pts = [(0, 1000), (10, 1050), (20, 1010), (30, 1070), (40, 1030), (45, 1035)]
        df = _frame(_zigzag(pts))
        a1, a2 = _peak_line(df, 10, 30)
    x = V.check_line(df, len(df) - 1, a1, a2, V.RES)
    assert not x["valid"] and reason in x["reasons"], x["reasons"]
    assert x["projected_zone"] is None


# band: two swing highs at ≈1080 (bars 10, 30) with price leaving below in between; t = 40.
BAND_PTS = [(0, 1040), (10, 1078), (20, 1040), (30, 1078), (40, 1045)]


def test_synthetic_band_two_reactions_valid():
    df = _frame(_zigzag(BAND_PTS))
    t = len(df) - 1
    bands = LV.find_bands(df, t)
    top = bands[0]
    assert top["valid"] and top["role"] == V.RES and top["touch_count"] == 2 and top["hi"] > top["lo"]
    assert [p["bar"] for p in top["touches"]] == [10, 30]
    assert top["width_mr"] <= V.DEFAULTS["band_max_mr"]
    shown = LV.display_bands(df, t)
    assert shown and shown[0] is not None and all(x["valid"] or x["broken"] for x in shown)


def test_synthetic_band_single_price_wide_and_one_touch_rejected():
    df = _frame(_zigzag(BAND_PTS))
    t = len(df) - 1
    hi = float(df["high"].iloc[10])
    assert "not_a_band" in V.check_band(df, t, hi, hi)["reasons"]
    mr = V.mr_at(V.bars_of(df), t)
    assert "too_wide" in V.check_band(df, t, hi - 2 * mr, hi)["reasons"]
    one = _frame(_zigzag([(0, 1040), (10, 1078), (20, 1040), (30, 1050)]))
    assert "lt2_reaction_touches" in V.check_band(one, len(one) - 1, hi - 3, hi)["reasons"]


def test_synthetic_band_break_flip_and_touches_on_new_side():
    up = BAND_PTS[:-1] + [(33, 1068), (38, 1110), (46, 1082), (54, 1115), (62, 1082), (68, 1110)]
    df = _frame(_zigzag(up))
    lo, hi = V.band_from_reactions(V.bars_of(df), 10, 30, "H")
    mid = V.check_band(df, 49, lo, hi)                                             # broken up, 1 touch on the new (support) side
    assert mid["broken"] and "broken" in mid["reasons"] and mid["breaks"][0]["dir"] == "up"
    end = V.check_band(df, len(df) - 1, lo, hi)                                    # 2 swing lows on the band from above ⇒ flipped
    assert end["valid"] and end["flipped"] and end["role"] == V.SUP and end["touch_count"] == 2
    assert len(end["earlier_side_touches"]) == 2


def test_synthetic_display_caps_and_latest_broken():
    bands = []
    for k in range(5):
        bands.append({"lo": 1100 + 10 * k, "hi": 1105 + 10 * k, "role": V.RES, "valid": True, "broken": False, "reasons": [],
                      "touch_count": 2, "touches": [{"bar": 1}], "last_break_bar": None})
        bands.append({"lo": 900 - 10 * k, "hi": 905 - 10 * k, "role": V.SUP, "valid": True, "broken": False, "reasons": [],
                      "touch_count": 2, "touches": [{"bar": 1}], "last_break_bar": None})
    bands += [{"lo": 1000 + 60, "hi": 1065, "role": V.SUP, "valid": False, "broken": True, "reasons": ["broken"], "touch_count": 0,
               "touches": [], "last_break_bar": b} for b in (5, 9)]
    shown = V.select_bands(bands, 1000.0)
    assert sum(1 for x in shown if x["valid"] and x["lo"] > 1000) == 3 and sum(1 for x in shown if x["valid"] and x["hi"] < 1000) == 3
    assert [x["last_break_bar"] for x in shown if x["broken"]] == [9]
    lines = [{"valid": True, "touch_count": n, "touches": [{"bar": n}], "anchor1": {"bar": n, "price": 1.0 + n},
              "anchor2": {"bar": n + 9, "price": 2.0 + n}, "slope_per_bar": 0.0, "mr": 1.0, "side": V.RES} for n in (2, 3, 4)]
    assert [x["touch_count"] for x in V.select_lines(lines)] == [4, 3]


def test_synthetic_confluence_flag():
    pts = [(0, 1060), (10, 1098), (20, 1045), (30, 1078), (40, 1040), (44, 1046), (49, 1030), (54, 1046), (60, 1036)]
    df = _frame(_zigzag(pts))
    t = len(df) - 1
    line = V.check_line(df, t, *_peak_line(df, 10, 30), V.RES)
    B = V.bars_of(df)
    lo, hi = V.band_from_reactions(B, 44, 54, "H")
    band = V.check_band(df, t, lo, hi)
    assert line["valid"] and band["valid"], (line["reasons"], band["reasons"])
    c = V.confluence(band, line)
    assert c is not None and c["role"] == V.RES and c["distance_mr"] <= V.DEFAULTS["confluence_mr"]
    far = dict(band, lo=band["lo"] - 200, hi=band["hi"] - 200)
    assert V.confluence(far, line) is None


def test_settings_cite_kb():
    for k in V.DEFAULTS:
        assert any(k in key for key in V.REGISTER), k


# ------------------------------------------------------------------------------------------------ renderers (drawing layer only)
def test_trendlines2_chart_draws_only_valid_lines():
    from trendlines2 import charts as TC
    df = _line_df()
    ts = df["timestamp"].astype(str)

    def lj(a, b, kind="H"):
        y = "high" if kind == "H" else "low"
        return {"name": "x", "kind": kind, "class": "trade-योग्य", "a1": {"ts": ts[a], "price": float(df[y].iloc[a])},
                "a2": {"ts": ts[b], "price": float(df[y].iloc[b])}}
    good, steep = lj(10, 30), lj(20, 30, "L")                                      # 20 → 30 lows: not even a pivot pair ⇒ fails
    shown = TC.shown_lines([good, steep], df)
    assert [x[0] for x in shown] == [good] and shown[0][1]["valid"]
    assert len(TC.shown_lines([good, steep], df, debug=True)) == 2


def test_zones2_chart_draws_only_valid_bands():
    from zones2 import charts as ZC
    df = _frame(_zigzag(BAND_PTS))
    lo, hi = V.band_from_reactions(V.bars_of(df), 10, 30, "H")
    zones = [{"bottom": lo, "top": hi}, {"bottom": hi, "top": hi}, {"bottom": 1000.0, "top": 1001.0}]
    shown = ZC.shown_zones(zones, df)
    assert [z for z, _, _ in shown] == [zones[0]]
    assert len(ZC.shown_zones(zones, df, debug=True)) == 3


def test_vision_chart_hides_single_price_majors():
    from vision import chart as VC
    assert VC.no_majors({"label": "M1↑", "kinds": ["major"], "price": 1.0}) is None
    assert VC.no_majors({"label": "PDH+M1↑", "kinds": ["major", "ref"], "price": 1.0})["label"] == "PDH"
    m1 = _frame(_zigzag(BAND_PTS))
    one = m1.loc[m1.index.repeat(15)].reset_index(drop=True)                     # each 15M bar as 15 identical 1m bars
    one["timestamp"] = [t + pd.Timedelta(minutes=k % 15) for k, t in enumerate(one["timestamp"])]
    bands = VC.chart_bands(one)
    assert bands and all(b["hi"] > b["lo"] and (b["valid"] or b["broken"]) for b in bands)


def test_setup_chart_k_line_label_and_validity():
    """The R1a legacy label (`k_line_facts_validity`); layer 6b draws the decision's own K line (next test)."""
    from types import SimpleNamespace
    from decision3 import setup_chart as SC
    df = _line_df()
    D = SimpleNamespace(m15=df)
    r = {"level": {"role": "support"}, "trendline": {"p1": [10, float(df["high"].iloc[10])], "p2": [30, float(df["high"].iloc[30])]}}
    k = SC.k_line_facts_validity(D, r, len(df) - 1)                                         # UP trade ⇒ K counter-move highs
    assert k["drawable"] and "2 touches" in k["label"] and "touch 3 zone" in k["label"]
    r["trendline"]["broken"], r["trendline"]["break_bar"] = True, 44                # V22's own break state is what the chart shows
    k = SC.k_line_facts_validity(D, r, len(df) - 1)
    assert k["drawable"] and ", broken " in k["label"] and "; no K5 real break" in k["label"] and "zone" not in k["label"]
    r["trendline"]["broken"] = False
    r["trendline"]["p2"] = [12, float(df["high"].iloc[12])]
    k = SC.k_line_facts_validity(D, r, len(df) - 1)
    assert not k["drawable"] and "fails K6" in k["label"]


def test_setup_chart_k_line_is_the_decisions_own_layer_6b():
    """Layer 6b: the setup chart shows the K line exactly as the decision read it (layer 4: touches by the candle; closed through by the
    commitment / gone before / intact) — no MR / K5 / K6 display check."""
    from types import SimpleNamespace
    from decision3 import setup_chart as SC
    df = _line_df()
    D = SimpleNamespace(m15=df)
    tl = {"p1": [10, float(df["high"].iloc[10])], "p2": [12, float(df["high"].iloc[12])], "touches": 2, "broken": False,
          "broken_before": None, "break_bar": None}
    k = SC.k_line_facts(D, {"level": {"role": "support"}, "trendline": tl}, len(df) - 1)
    assert k["drawable"] and k["label"] == "K line (2 touches, intact)" and "K6" not in k["label"]
    k = SC.k_line_facts(D, {"level": {"role": "support"}, "trendline": {**tl, "broken": True, "break_bar": 44}}, len(df) - 1)
    assert "closed through by the commitment" in k["label"]
    k = SC.k_line_facts(D, {"level": {"role": "support"}, "trendline": {**tl, "broken_before": 40, "break_bar": 40}}, len(df) - 1)
    assert "gone" in k["label"] and "no trigger" in k["label"]


def test_vision_default_image_unchanged_and_bands_only_with_setting(monkeypatch):
    """Review 🔴1: vision_chart_bands default OFF ⇒ build_figure gets bands=None (the main drawing: majors drawn, no bands), ctx has no
    "bands" and chart_bands is never called; ON ⇒ bands drawn in non-L colours and the signal text carries the legend + prices."""
    from tests import test_vision_v2 as TV
    from vision import chart as VCH
    from vision import config as VCF
    from vision import signal_audit as SA
    df = TV.bars()
    got = {}
    real = VCH.build_figure
    monkeypatch.setattr(VCH, "build_figure", lambda *a, **k: got.update(bands=a[7] if len(a) > 7 else k.get("bands")) or real(*a, **k))
    monkeypatch.setattr(VCH, "chart_bands", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called with setting OFF")))
    cs = {**{k: VCF.BOT_DEFAULTS[k] for k in VCF.CTX_KEYS}, "events": {}}
    assert VCF.BOT_DEFAULTS["vision_chart_bands"] is False
    for s in (TV.sig(), TV.sig(ctx_settings=cs)):
        png, meta = VCH.render(df, s)
        assert meta["error"] is None and got["bands"] is None and "bands" not in meta["ctx"] and "bands_error" not in meta
        assert "Chart note" not in SA.signal_text({**s, "ctx": meta["ctx"]})
    monkeypatch.undo()
    s = TV.sig(ctx_settings={**cs, "vision_chart_bands": True})
    png, meta = VCH.render(df, s)
    assert meta["error"] is None and isinstance(meta["ctx"].get("bands"), list)
    txt = SA.signal_text({**s, "ctx": meta["ctx"]})
    assert "Chart note" in txt and "M1 / M2 are NOT drawn" in txt
    for b in meta["ctx"]["bands"]:
        assert f"{b['lo']:,.2f} - {b['hi']:,.2f}" in txt
    cols = {c for c, _ in VCH.BAND_COLOR.values()}
    assert not cols & {"#26a69a", "#ef5350"}                                       # L green / red never used for bands


def _highs_frame(highs, n=50, base=1050.0):
    """Bars whose highs are given at {bar: high}; other bars sit at `base` (range 4, closes mid)."""
    t = pd.date_range("2026-01-05 09:15", periods=n, freq="15min")
    hi = np.full(n, base + 2.0)
    for b, h in highs.items():
        hi[b] = h
    lo = np.minimum(hi - 4.0, base - 2.0)
    c = (hi + lo) / 2 - 0.5
    return pd.DataFrame({"timestamp": t, "open": c + 0.5, "high": hi, "low": lo, "close": c})


@pytest.mark.parametrize("mirror", [False, True])
def test_review_twin_pivot_before_anchor2_does_not_kill_the_line(mirror):
    """Review 🔴2 repro: highs 10 = 1098, 30 = 1094, a twin pivot 27 = 1093.9 (< 6 bars before 30, on the line) ⇒ the 10 → 30 line is valid and found."""
    df = _highs_frame({10: 1098.0, 27: 1093.9, 30: 1094.0, 9: 1080.0, 11: 1080.0, 26: 1080.0, 28: 1085.0, 29: 1086.0, 31: 1080.0})
    side = V.RES
    if mirror:                                                                     # supports: the same picture upside down
        df = df.assign(high=2000 - df["low"], low=2000 - df["high"], open=2000 - df["open"], close=2000 - df["close"])
        side = V.SUP
    t = len(df) - 1
    y = df["high" if side == V.RES else "low"]
    ref = V.check_line(df, t, (10, float(y.iloc[10])), (30, float(y.iloc[30])), side)
    assert ref["valid"], ref["reasons"]
    found = [x for x in TT.find_lines(df, t) if x["valid"] and x["side"] == side]
    assert any(x["anchor1"]["bar"] == 10 and x["anchor2"]["bar"] == 30 for x in found), [(x["anchor1"]["bar"], x["anchor2"]["bar"]) for x in found]


def test_review_acceptance_on_a_sloped_line_uses_the_next_bar_value():
    """Review 🟡4: the acceptance close (i + 1) is compared with the line at i + 1. Falling line v(i) = 100 − 0.8 i, MR = 2, buf = 0.5:
    close 5 = v(5) + 0.6, close 6 = v(6) + 0.6 (above v(6) + buf, below v(5) + buf) ⇒ a real break at 5."""
    n = 12
    v = 100 - 0.8 * np.arange(n)
    c = v - 3.0
    c[5], c[6] = v[5] + 0.6, v[6] + 0.6
    df = pd.DataFrame({"timestamp": pd.date_range("2026-01-05 09:15", periods=n, freq="15min"), "open": c, "high": c + 1, "low": c - 1,
                       "close": c})
    B = V.bars_of(df)
    assert V.mr_at(B, n - 1) == 2.0
    assert V._real_break(B, n - 1, 5, lambda i: 100 - 0.8 * i, True, 2.0, V.DEFAULTS)
    assert not V._real_break(B, n - 1, 5, float(v[5]), True, 2.0, V.DEFAULTS)     # horizontal level at v(5): close 6 not beyond


def test_review_band_magnet_ignores_rows_after_t():
    """Review 🟡5: magnet closes are clipped to the end of bar t even if the caller passes later rows."""
    df = _frame(_zigzag(BAND_PTS))
    t = 25
    lo, hi = 1050.0, 1060.0
    fut = df.copy()
    fut.loc[t + 1:, "close"] = np.where(np.arange(len(fut) - t - 1) % 2, 1040.0, 1070.0)   # many crossings after t
    a = V.check_band(df.iloc[:t + 1], t, lo, hi, magnet_df=df.iloc[:t + 1])
    b = V.check_band(df.iloc[:t + 1], t, lo, hi, magnet_df=fut)
    assert a["crossings_session"] == b["crossings_session"] and a["reasons"] == b["reasons"]


def test_review_bands_no_lookahead_truncation():
    pts = BAND_PTS[:-1] + [(33, 1068), (38, 1110), (46, 1082), (54, 1115), (62, 1082), (68, 1110)]
    df = _frame(_zigzag(pts))
    for t in (35, 49, 60, 66):
        full = LV.find_bands(df, t)
        cut = LV.find_bands(df.iloc[:t + 1], t)
        key = [(x["lo"], x["hi"], x["valid"], x["broken"], x["touch_count"], x["role"]) for x in full]
        assert key == [(x["lo"], x["hi"], x["valid"], x["broken"], x["touch_count"], x["role"]) for x in cut], t


def test_review_check_band_default_window_is_the_finder_lookback():
    df = _frame(_zigzag(BAND_PTS))
    t = len(df) - 1
    lo, hi = V.band_from_reactions(V.bars_of(df), 10, 30, "H")
    assert V.check_band(df, t, lo, hi) == V.check_band(df, t, lo, hi, start=V.session_start(V.bars_of(df), t, 8))
    assert V.lookback("1H")["lookback_sessions"] == 15 and V.lookback("D")["lookback_sessions"] == 126


# ================================================================================================ 2. real data (private; skip in CI)
need_data = pytest.mark.skipif(not all(os.path.exists(p) for p in SPOT_1M + [FUT_5M]), reason="private trade-data not present")


def _read(p):
    d = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p)
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if getattr(d["timestamp"].dt, "tz", None) is not None:
        d["timestamp"] = d["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return d


def _no_holdout(d):
    from elliott import data_policy as DP
    d = DP.filter_allowed(d, purpose="annotation")
    assert not any(DP.period(x) == "HOLDOUT" for x in pd.to_datetime(d["timestamp"]).dt.normalize().unique())
    return d.reset_index(drop=True)


def load_spot15():
    from pivots import engine as PE
    d = pd.concat([_read(p)[["timestamp", "open", "high", "low", "close"]] for p in SPOT_1M])
    d = _no_holdout(d.drop_duplicates("timestamp", keep="last").sort_values("timestamp"))
    return PE.bars_15m(d)[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)


def load_fut15():
    d = _no_holdout(_read(FUT_5M))
    t = d["timestamp"]
    day = t.dt.normalize()
    key = day + pd.Timedelta(hours=9, minutes=15) + ((t - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(minutes=15)) * \
        pd.Timedelta(minutes=15)
    g = d.assign(_k=key).groupby("_k", sort=True).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                     close=("close", "last")).reset_index().rename(columns={"_k": "timestamp"})
    return g[g["timestamp"].dt.strftime("%H:%M") <= "15:15"].reset_index(drop=True)


@pytest.fixture(scope="module")
def spot15():
    return load_spot15()


@pytest.fixture(scope="module")
def fut15():
    return load_fut15()


A1_DAY, A2_DAY, CHECK = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-06"), pd.Timestamp("2026-10-12 09:15")
CLOSES = ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]


def _close_bar(df, day):
    ts = pd.to_datetime(df["timestamp"])
    return int(np.flatnonzero((ts.dt.normalize() == pd.Timestamp(day)).to_numpy())[-1])


def _day_high_bar(df, day):
    ts = pd.to_datetime(df["timestamp"])
    idx = np.flatnonzero((ts.dt.normalize() == day).to_numpy())
    return int(idx[np.argmax(df["high"].to_numpy()[idx])])


def _golden(df, upto_day):
    """The golden line as the finder returns it at the close of `upto_day`, on data truncated there (no look-ahead)."""
    t = _close_bar(df, upto_day)
    cut = df.iloc[:t + 1].reset_index(drop=True)
    b1, b2 = _day_high_bar(df, A1_DAY), _day_high_bar(df, A2_DAY)
    ref = V.check_line(cut, t, (b1, float(df["high"].iloc[b1])), (b2, float(df["high"].iloc[b2])), V.RES)
    found = [x for x in TT.find_lines(cut, t) if x["valid"] and V.same_line(x, ref, ref["mr"], V.DEFAULTS["touch_mr"])]
    return t, cut, ref, found


def _check_golden_line(df, line_at_check, tol_pts):
    b1, b2 = _day_high_bar(df, A1_DAY), _day_high_bar(df, A2_DAY)
    t5 = _close_bar(df, "2026-10-05")                                              # before anchor 2 exists: not found
    assert not any(x["valid"] and x["anchor1"]["bar"] == b1 and x["anchor2"]["bar"] == b2 for x in TT.find_lines(df.iloc[:t5 + 1], t5))
    t, cut, ref, found = _golden(df, "2026-10-06")                                 # found from the 2 touches alone at the 6 Oct close
    assert ref["valid"], ref["reasons"]
    assert any(x["anchor1"]["bar"] == b1 and x["anchor2"]["bar"] == b2 and x["touch_count"] == 2 for x in found)
    for d in CLOSES:                                                               # valid at every close before 12 Oct
        t, cut, ref, found = _golden(df, d)
        assert ref["valid"] and found, (d, ref["reasons"])
    t, cut, ref, found = _golden(df, "2026-10-09")
    assert ref["established"]                                                       # 7 Oct high = 3rd touch
    full = V.check_line(df, t, (b1, ref["anchor1"]["price"]), (b2, ref["anchor2"]["price"]), V.RES)
    assert full["projected_zone"] == ref["projected_zone"]                         # truncation never changes the result
    shown = TT.display_lines(cut, t)
    assert any(V.same_line(x, ref, ref["mr"], V.DEFAULTS["touch_mr"]) for x in shown)   # drawn at the 9 Oct close (TA1 cap 2)
    nxt = ref["projected_zone"]["next"]
    k = int(np.flatnonzero((pd.to_datetime(df["timestamp"]) == CHECK).to_numpy())[0])
    assert k == t + 1                                                               # offset 1 = 12 Oct 09:15
    assert abs(nxt["mid"] - line_at_check) <= tol_pts
    return ref, nxt, df.iloc[k]


@need_data
def test_golden_k6_nifty_spot_2026_10_12_two_touch_line_projects_third_touch(spot15):
    ref, nxt, bar = _check_golden_line(spot15, 22654.0, 1.0)                       # audit: line 22,654 at 09:15
    assert nxt["lo"] <= bar["high"] <= nxt["hi"]                                    # high 22,651.10 inside the 3rd-touch zone
    assert bar["close"] < nxt["mid"]


@need_data
def test_golden_k6_nifty_fut_2026_10_12_two_touch_line_projects_third_touch(fut15):
    ref, nxt, bar = _check_golden_line(fut15, 22709.6, 1.0)                        # audit: FUT line 22,709.6 at 09:15
    mr = ref["mr"]
    # FUT high 22,720 pokes 0.27 MR above the line (outside the ±0.2 MR touch zone) and closes back below: a K5 sweep of the
    # projected touch (0.1–1.0 MR beyond, close inside) — the zone itself is not widened to include it.
    assert bar["high"] >= nxt["lo"]
    beyond = (bar["high"] - nxt["mid"]) / mr
    assert nxt["lo"] <= bar["high"] <= nxt["hi"] or (0.1 <= beyond <= 1.0 and bar["close"] < nxt["mid"])


def _band_near(bands, price, mr):
    tol = V.DEFAULTS["band_tol_mr"] * mr
    return [b for b in bands if b["valid"] and b["role"] == V.RES and b["lo"] - tol <= price <= b["hi"] + tol]


@need_data
def test_golden_k4_nifty_fut_2026_10_12_supply_band_22667(fut15):
    t = _close_bar(fut15, "2026-10-09")
    cut = fut15.iloc[:t + 1].reset_index(drop=True)
    bands = LV.find_bands(cut, t)
    near = _band_near(bands, 22667.0, V.mr_at(V.bars_of(cut), t))
    assert near, [LV.band_label(b) for b in bands if b["valid"]]
    b = near[0]
    assert b["touch_count"] >= 2 and b["hi"] > b["lo"]
    assert any(V.select_bands(bands, float(cut["close"].iloc[-1]))[i] is b for i in range(len(V.select_bands(bands, float(cut["close"].iloc[-1])))))


@need_data
def test_golden_k4_k6_nifty_fut_2026_10_12_confluence(fut15):
    t, cut, line, _ = _golden(fut15, "2026-10-09")
    bands = LV.find_bands(cut, t)
    near = _band_near(bands, 22667.0, line["mr"])
    c = V.confluence(near[0], line)
    assert c is not None and c["role"] == V.RES                                    # the ≈22,667 supply meets the projected line ...
    day12 = np.flatnonzero((pd.to_datetime(fut15["timestamp"]).dt.normalize() == CHECK.normalize()).to_numpy())
    assert t + c["offset"] in set(day12)                                            # ... on 12 Oct (before any 12 Oct bar is read)
    at_open = [x for x in V.confluences([b for b in bands if b["valid"]], [line]) if x["offset"] <= 1]
    assert at_open                                                                  # and a supply band meets it at the 09:15 bar


@need_data
def test_golden_k4_k6_nifty_spot_2026_10_12_confluence(spot15, fut15):
    t, cut, line, _ = _golden(spot15, "2026-10-09")
    bands = LV.find_bands(cut, t)
    at_open = [x for x in V.confluences([b for b in bands if b["valid"]], [line]) if x["offset"] <= 1]
    assert at_open                                                                  # spot: a valid supply band meets the line at 09:15
    tf = _close_bar(fut15, "2026-10-09")
    fb = _band_near(LV.find_bands(fut15.iloc[:tf + 1].reset_index(drop=True), tf), 22667.0, V.mr_at(V.bars_of(fut15), tf))[0]
    times = {p["ts"] for p in fb["touches"]}                                       # spot equivalent = the band of the same reactions
    eq = [b for b in bands if b["valid"] and {p["ts"] for p in b["touches"]} == times]
    assert eq and eq[0]["role"] == V.RES
