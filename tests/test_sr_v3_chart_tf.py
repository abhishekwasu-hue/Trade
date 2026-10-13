"""tests/test_sr_v3_chart_tf.py -- SR V3 chart levels chart च्या TF नुसार (network-मुक्त, कृत्रिम candles)."""
import numpy as np
import pandas as pd
import pytest

import sr_v3_chart as C


def _series(start, n, freq, seed, base=24500.0, step=15.0):
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, periods=n, freq=freq)
    c = base + np.cumsum(rng.normal(0, step, n)) + 120 * np.sin(np.arange(n) / 9)
    return pd.DataFrame({"timestamp": t, "open": c, "high": c + step, "low": c - step, "close": c, "volume": 1, "oi": 0})


def _fetch_factory(calls):
    def fetch(token, symbol, spot, interval="5minute", lookback_days=None):
        calls.append((interval, lookback_days))
        return {"5minute": _series("2026-09-25 09:15", 600, "5min", 1, step=4),
                "15minute": _series("2026-09-20 09:15", 400, "15min", 2, step=6),
                "30minute": _series("2026-07-25 09:15", 1400, "30min", 3, step=8),
                "day": _series("2025-08-20", 400, "1D", 4, step=60)}[interval]
    return fetch


@pytest.mark.parametrize("chart_tf,expect", [
    ("5minute", {"5minute", "15minute", "30minute"}),
    ("15minute", {"15minute", "30minute", "1hour"}),
    ("30minute", {"30minute", "1hour", "4hour"}),
    ("1hour", {"1hour", "4hour", "day"}),
    ("day", {"day", "week"}),
])
def test_frames_follow_chart_tf(chart_tf, expect):
    calls = []
    frames, daily = C.frames_for_chart_tf(_fetch_factory(calls), "tok", "NIFTY", chart_tf)
    assert set(frames) == expect and daily is not None
    if "4hour" in expect:
        assert ("30minute", 70) in calls                                          # 4H साठी जास्त इतिहास
    if "week" in expect:
        assert len(frames["week"]) < len(frames["day"]) / 4


def test_v3_chart_lines_differ_by_chart_tf_and_old_default_kept():
    # TA4 (Abhi, design §10): default view = only levels that pass the shared band rule; debug = every level (with the reason) — the
    # chart-TF level sets are compared on the debug view (these random candles rarely make a 2-reaction band).
    fetch = _fetch_factory([])
    price = 24500.0
    l5, n5 = C.v3_chart_lines(fetch, "tok", "NIFTY", price, chart_tf="5minute", debug=True)
    ld, nd = C.v3_chart_lines(fetch, "tok", "NIFTY", price, chart_tf="day", debug=True)
    assert n5 is None and nd is None and l5 and ld
    assert {round(l["price"], 1) for l in l5} != {round(l["price"], 1) for l in ld}
    assert any(" D" in l["title"] or "+D" in l["title"] or "W" in l["title"] for l in ld)
    old, note = C.v3_chart_lines(fetch, "tok", "NIFTY", price, debug=True)        # chart TF नाही ⇒ जुनं वर्तन
    assert note is None
    shown, note = C.v3_chart_lines(fetch, "tok", "NIFTY", price, chart_tf="5minute")     # these candles: no 5M level passes
    assert shown == [] and "band" in note
    shown, note = C.v3_chart_lines(fetch, "tok", "NIFTY", price, chart_tf="15minute")    # 15M: one valid band + the latest broken
    assert note is None and len(shown) == 4 and not any("invalid" in l["title"] for l in shown)
    assert sum(1 for l in shown if l["title"].endswith("broken")) == 1 and sum(1 for l in shown if " T" in l["title"]) == 1


def test_band_chart_lines_only_valid_bands_and_single_price_dropped():
    t = pd.date_range("2026-09-01 09:15", periods=80, freq="15min")
    path = np.r_[np.linspace(100, 120, 11), np.linspace(120, 100, 10)[1:], np.linspace(100, 120, 11)[1:], np.linspace(120, 104, 60)[1:]]
    c = path[:80]
    o = np.r_[c[0], c[:-1]]
    fr = pd.DataFrame({"timestamp": t, "open": o, "high": np.maximum(o, c) + 1, "low": np.minimum(o, c) - 1, "close": c})
    lv = [{"low": 119.0, "high": 121.0, "role": "RESISTANCE", "grade": "A", "score": 80, "tags": ["15M"]},     # 2 reactions ⇒ band
          {"low": 121.0, "high": 121.0, "role": "RESISTANCE", "grade": "B", "score": 60, "tags": ["15M"]}]     # single price
    lines = C.band_chart_lines(lv, fr, float(c[-1]))
    assert lines and all(l["title"].startswith("R A80") for l in lines) and {l["price"] for l in lines} == {119.0, 121.0}
    dbg = C.band_chart_lines(lv, fr, float(c[-1]), debug=True)
    assert any("not_a_band" in l["title"] for l in dbg)


def test_tf_set_label():
    assert C.tf_set_label("15minute") == "15M+30M+1H" and C.tf_set_label("day") == "D+W" and C.tf_set_label(None) == "5M+15M+30M+1H"
