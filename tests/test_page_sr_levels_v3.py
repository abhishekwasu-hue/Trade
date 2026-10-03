"""tests/test_page_sr_levels_v3.py -- SR Levels V3 पानाचा AppTest (नेटवर्कशिवाय, कृत्रिम candles)."""
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


def _frames(days=10, seed=3):
    rng = np.random.default_rng(seed)
    stamps = []
    for d in pd.bdate_range("2026-09-01", periods=days):
        stamps += list(pd.date_range(d + pd.Timedelta(hours=9, minutes=15), periods=75, freq="5min"))
    n = len(stamps)
    close = 24100 + 100 * np.sin(np.arange(n) * 2 * np.pi / 150) + rng.normal(0, 3, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    f5 = pd.DataFrame({"timestamp": stamps, "open": open_, "high": np.maximum(open_, close) + 2,
                       "low": np.minimum(open_, close) - 2, "close": close, "volume": 1000, "oi": 0})

    def resample(rule):
        d = f5.set_index("timestamp").resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "oi": "last"}).dropna(subset=["open"])
        return d.reset_index()

    daily = f5.assign(date=f5["timestamp"].dt.normalize()).groupby("date").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
        oi=("oi", "last")).reset_index().rename(columns={"date": "timestamp"})
    return {"5minute": f5, "15minute": resample("15min"), "30minute": resample("30min"), "day": daily}


def _app():
    from unittest.mock import patch
    import builtins
    import pandas as pd
    import streamlit as st
    import page_sr_levels_v3 as page
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", builtins._SRV3_TOKEN)
    st.session_state.setdefault("underlying_price", 24100.0)

    def fake_fetch(token, symbol, spot, interval="30minute", lookback_days=None):
        return builtins._SRV3_FRAMES.get(interval, pd.DataFrame())

    with patch.object(page, "fetch_candles", side_effect=fake_fetch):
        page.render()


def _run(frames=None, token="x"):
    import builtins
    builtins._SRV3_FRAMES = _frames() if frames is None else frames
    builtins._SRV3_TOKEN = token
    at = AppTest.from_function(_app, default_timeout=90)
    at.run()
    return at


def test_page_renders_chart_table_and_metrics_without_error():
    at = _run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert any("जवळचा Resistance" in m.label for m in at.metric)
    assert any("जवळचा Support" in m.label for m in at.metric)
    assert at.dataframe, "levels चा तक्ता दिसला पाहिजे"


def test_page_switches_timeframe_and_old_sr_comparison_without_error():
    at = _run()
    for tf in ("5minute", "30minute", "15minute"):
        at.radio(key="srv3_tf").set_value(tf).run()
        assert not at.exception and not at.error, (tf, [e.value for e in at.error])
    at.checkbox(key="srv3_compare_old").check().run()
    assert not at.exception and not at.error


def test_page_without_token_only_asks_for_token():
    at = _run(token="")
    assert not at.exception and not at.dataframe
    assert any("Access Token" in i.value for i in at.info)


def test_page_with_no_data_does_not_crash():
    at = _run(frames={})
    assert not at.exception
    assert any("डेटा मिळाला नाही" in w.value for w in at.warning)


def test_page_survives_extreme_parameter_values():
    at = _run()
    at.number_input(key="srv3_min_score").set_value(100.0).run()
    assert not at.exception and not at.error
    at.number_input(key="srv3_min_score").set_value(0.0).run()
    at.number_input(key="srv3_max_levels").set_value(2).run()
    at.number_input(key="srv3_half_life").set_value(0.5).run()
    assert not at.exception and not at.error, [e.value for e in at.error]
