"""tests/test_price_action_trendlines.py -- तिरक्या trendlines (टप्पा 1: चार्ट + चाचणी). synthetic only."""
import numpy as np
import pandas as pd
import pytest

import bot_view as bv
import mcx_trendline_audit as AUD
from price_action import trendlines as TL
from tradingview_chart import build_lightweight_chart_html


def _desc_df(n=300, slope=-0.5, start=1000.0, period=24, amp=30.0, seed=1):
    """उतरती resistance: high च्या शिखरांवर रेषा L(t) = start + slope × t; बाकी भाव रेषेखाली."""
    t = np.arange(n)
    line = start + slope * t
    close = line - 2 - amp * (1 - np.cos(2 * np.pi * t / period)) / 2 + np.random.default_rng(seed).normal(0, 0.3, n)
    high = np.minimum(close + 2, line)
    df = pd.DataFrame({"timestamp": pd.date_range("2026-08-03 09:00", periods=n, freq="60min"),
                       "open": close + 0.5, "high": high, "low": close - 3, "close": close})
    return df, line


def test_detects_descending_resistance_through_lower_highs():
    df, line = _desc_df()
    lines = TL.detect_trendlines(df, min_touches=3)
    res = [ln for ln in lines if ln["kind"] == "DESC_RESISTANCE"]
    assert res and res[0]["slope"] == pytest.approx(-0.5, abs=0.05) and res[0]["touches"] >= 3
    assert res[0]["next_price"] == pytest.approx(1000 - 0.5 * len(df), abs=3)
    assert not any(ln["kind"] == "ASC_SUPPORT" for ln in lines)                # lows पण उतरते ⇒ चढती support नाही


def test_line_with_close_beyond_is_not_valid():
    df, line = _desc_df()
    df.loc[len(df) - 2, ["high", "close"]] = [line[-2] + 15, line[-2] + 10]   # रेषेपलीकडे close ⇒ ती रेषा तुटली
    for ln in TL.detect_trendlines(df):
        tl = ln["line"]
        assert not any(df["close"].iloc[i] > tl.at(i) + 1e-9 for i in range(tl.a, len(df))) or ln["kind"] != "DESC_RESISTANCE"


def test_completed_hours_only_full_hours():
    rows = [{"timestamp": pd.Timestamp(f"2026-10-05 {h}"), "open": 1, "high": 2, "low": 0, "close": 1}
            for h in ("09:00", "09:30", "10:00", "10:30", "11:00")]
    h = TL.completed_hours(pd.DataFrame(rows), pd.Timestamp("2026-10-05 11:40"))
    assert list(h["timestamp"].dt.strftime("%H:%M")) == ["09:00", "10:00"]


def test_audit_real_lines_hold_more_than_shifted_controls():
    df, _ = _desc_df(n=320)
    ev = TL.audit_touches(df, min_touches=2, warmup=60)
    real, ctrl = ev[ev["group"] == "real"], ev[ev["group"] == "control"]
    assert len(real) >= 3
    hold = lambda g: (g["outcome"] == "HOLD").mean() if len(g) else 0.0
    assert hold(real) >= 0.8 and hold(real) > hold(ctrl)
    summ = TL.summarize_audit(ev)
    assert set(summ["set"]) <= {"IS", "OOS"} and {"real", "control"} <= set(summ["group"])


def test_audit_no_lookahead():
    df, _ = _desc_df(n=200)
    full = TL.audit_touches(df, warmup=60)
    part = TL.audit_touches(df.iloc[:150], warmup=60)
    cut = df["timestamp"].iloc[149]
    pd.testing.assert_frame_equal(full[(full["ts"] <= cut - pd.Timedelta(hours=10))].reset_index(drop=True),
                                  part[(part["ts"] <= cut - pd.Timedelta(hours=10))].reset_index(drop=True))


def test_chart_segments_clip_and_render():
    df, _ = _desc_df()
    lines = TL.detect_trendlines(df)
    start = df["timestamp"].iloc[-50]
    segs = TL.chart_segments(lines, df, chart_start=start)
    seg = next(s for s in segs if s["kind"] == "DESC_RESISTANCE")
    assert seg["points"][0][0] >= start and seg["points"][-1][0] == df["timestamp"].iloc[-1] + pd.Timedelta(minutes=60)
    assert seg["title"].startswith("R TL")
    html = build_lightweight_chart_html(df.assign(volume=0), symbol="SILVER", timeframe_label="60M", trend_lines=segs)
    assert "R TL" in html and "LineStyle.Dotted" in html


def test_mcx_overlay_from_30m(monkeypatch):
    df, _ = _desc_df(n=300)
    df30 = pd.concat([df, df.assign(timestamp=df["timestamp"] + pd.Timedelta(minutes=30))]).sort_values("timestamp").reset_index(drop=True)
    now = df30["timestamp"].iloc[-1] + pd.Timedelta(minutes=30)
    segs, cap = bv.mcx_trendline_overlay(df30, df30.tail(80), now)
    assert segs and "उतरती resistance" in cap


def test_audit_cli_offline(tmp_path, capsys):
    df, _ = _desc_df(n=300)
    df30 = pd.concat([df, df.assign(timestamp=df["timestamp"] + pd.Timedelta(minutes=30))]).sort_values("timestamp").reset_index(drop=True)
    rc = AUD.main(["--symbol", "SILVER", "--out", str(tmp_path)], fetch=lambda *a, **k: df30, token="t",
                  resolve=lambda t, s: (True, {"instrument_key": "k", "trading_symbol": "SILVER FUT"}),
                  now=df30["timestamp"].iloc[-1] + pd.Timedelta(minutes=30))
    out = capsys.readouterr().out
    assert rc == 0 and "DESC_RESISTANCE" in out and "टिकण्याचा दर" in out
