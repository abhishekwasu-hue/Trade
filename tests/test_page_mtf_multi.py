"""tests/test_page_mtf_multi.py -- MTF Pullback आणि Multi-Strategy पानांचे AppTest (नेटवर्कशिवाय, कृत्रिम candles)."""
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


def _candles(n, freq, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-09-01 09:15", periods=n, freq=freq)
    close = 24000 + np.cumsum(rng.normal(0, 25, n))
    open_ = close + rng.normal(0, 8, n)
    high = np.maximum(open_, close) + abs(rng.normal(0, 10, n))
    low = np.minimum(open_, close) - abs(rng.normal(0, 10, n))
    return pd.DataFrame({"timestamp": idx, "open": open_, "high": high, "low": low, "close": close, "volume": 1000, "oi": 0})


def _mtf_app():
    from unittest.mock import patch
    import streamlit as st
    import page_mtf_pullback as page
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", "x")
    st.session_state.setdefault("underlying_price", 24000.0)
    import builtins
    with patch.object(page, "fetch_timeframe_df", return_value=builtins._H1), \
         patch.object(page, "fetch_candles", return_value=builtins._M15):
        page.render()


def _run_mtf(h1=None, m15=None, fib_swap=False):
    import builtins
    builtins._H1 = _candles(400, "1h") if h1 is None else h1
    builtins._M15 = _candles(1600, "15min", seed=2) if m15 is None else m15
    at = AppTest.from_function(_mtf_app, default_timeout=60)
    at.run()
    at.checkbox(key="mtf_show").check().run()
    return at


def test_mtf_renders_gap_fill_and_fib_modes():
    at = _run_mtf()
    assert not at.exception and not at.error
    at.radio(key="mtf_strategy").set_value("fib_pullback").run()
    assert not at.exception and not at.error


def test_mtf_empty_data_warns_instead_of_crashing():
    at = _run_mtf(h1=pd.DataFrame(), m15=pd.DataFrame())
    assert not at.exception
    assert any("डेटा मिळाला नाही" in w.value for w in at.warning)


def test_mtf_fib_low_not_below_high_warns():
    at = _run_mtf()
    at.radio(key="mtf_strategy").set_value("fib_pullback").run()
    at.number_input(key="mtf_fib_lo").set_value(0.9).run()
    assert not at.exception
    assert any("Fib Low" in w.value for w in at.warning)


def test_mtf_irrelevant_inputs_disabled_per_mode():
    at = _run_mtf()
    assert at.number_input(key="mtf_fib_lo").disabled and not at.number_input(key="mtf_gap").disabled
    at.radio(key="mtf_strategy").set_value("fib_pullback").run()
    assert not at.number_input(key="mtf_fib_lo").disabled and at.number_input(key="mtf_gap").disabled


def _multi_app():
    from unittest.mock import patch
    import streamlit as st
    import page_multi_strategy as page
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", "x")
    st.session_state.setdefault("underlying_price", 24000.0)
    st.session_state.setdefault("raw_chain", {})
    st.session_state.setdefault("atm_strike", 24000)
    import builtins
    with patch.object(page, "fetch_candles", return_value=builtins._M15):
        page.render()


def test_multi_strategy_renders_with_checkbox_on():
    import builtins
    builtins._M15 = _candles(400, "15min")
    at = AppTest.from_function(_multi_app, default_timeout=60)
    at.run()
    assert not at.exception
    at.checkbox[0].check().run()
    assert not at.exception
    assert not at.error, [e.value for e in at.error]


def test_every_strategy_in_config_is_registered_and_built():
    """config.yaml मधली प्रत्येक strategy loader ने खरोखर बांधली पाहिजे (आधी mtf_gap_fill शांतपणे वगळली जायची)."""
    import os
    import yaml
    from loader import build_orchestrator
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(root, "config.yaml")
    with open(cfg_path, encoding="utf-8") as f:
        configured = set(yaml.safe_load(f)["strategies"])
    built = {s.strategy_id for s in build_orchestrator(cfg_path).strategies}
    assert built == configured
    assert not os.path.exists(os.path.join(root, "mtf_gap_fill.py")), "strategy फाईल strategies/ मध्येच हवी"

