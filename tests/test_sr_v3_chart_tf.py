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
    fetch = _fetch_factory([])
    price = 24500.0
    l5, n5 = C.v3_chart_lines(fetch, "tok", "NIFTY", price, chart_tf="5minute")
    ld, nd = C.v3_chart_lines(fetch, "tok", "NIFTY", price, chart_tf="day")
    assert n5 is None and nd is None and l5 and ld
    assert {round(l["price"], 1) for l in l5} != {round(l["price"], 1) for l in ld}
    assert any(" D" in l["title"] or "+D" in l["title"] or "W" in l["title"] for l in ld)
    old, note = C.v3_chart_lines(fetch, "tok", "NIFTY", price)                    # chart TF नाही ⇒ जुनं वर्तन
    assert note is None


def test_tf_set_label():
    assert C.tf_set_label("15minute") == "15M+30M+1H" and C.tf_set_label("day") == "D+W" and C.tf_set_label(None) == "5M+15M+30M+1H"
