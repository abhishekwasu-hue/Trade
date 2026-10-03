"""tests/test_page_positions.py -- Positions पानाचे Streamlit AppTest (नेटवर्क/DB शिवाय, सर्व data mock)."""
import pandas as pd
from streamlit.testing.v1 import AppTest


def _positions_df():
    return pd.DataFrame([{
        "Trade ID": "T1", "Mode": "PAPER", "Style": "INTRADAY", "Strategy": "NAKED_CALL", "Direction": "BULLISH", "Legs": "x",
        "Legs (Strike & Entry Price)": "x", "Lots": 1, "Source": "dynamic_sr_instant", "Entry Time": "2026-10-02 10:00:00",
        "MTM (Rs)": -500.0, "MTM (%)": -5.0, "Max Loss (Rs)": 1000.0, "Net Credit (Rs)": 0.0, "Peak P&L (Rs)": None,
        "Manual SL Override (Rs)": None,
    }])


def _app():
    from unittest.mock import patch
    import streamlit as st
    import page_positions as page
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", "")
    st.session_state.setdefault("product_type", "D")
    import builtins
    with patch.object(page, "get_live_positions_with_mtm", return_value=builtins._POS_DF), \
         patch.object(page, "count_open_trades_by_symbol", side_effect=lambda syms: builtins._OTHERS if "BANKNIFTY" in syms else {}), \
         patch.object(page, "compute_portfolio_greeks", return_value={"positions_included": 0}), \
         patch.object(page, "compute_per_position_greeks", return_value=[]), \
         patch.object(page, "get_open_trade_chart_info", return_value={}), \
         patch.object(page, "set_manual_sl_override", side_effect=lambda tid, lvl: (builtins._CALLS.append((tid, lvl)) or True, None)):
        page.render()


def _run(others=None):
    import builtins
    builtins._POS_DF = _positions_df()
    builtins._OTHERS = others or {}
    builtins._CALLS = []
    at = AppTest.from_function(_app, default_timeout=30)
    at.run()
    return at, builtins


def test_page_renders_without_exception():
    at, _ = _run()
    assert not at.exception


def test_hint_lists_open_positions_in_other_symbols():
    at, _ = _run(others={"BANKNIFTY": 2})
    assert any("BANKNIFTY: 2" in w.value for w in at.warning)


def test_no_hint_when_nothing_open_elsewhere():
    at, _ = _run(others={})
    assert not any("इतर उघड्या positions" in w.value for w in at.warning)


def test_override_at_or_above_mtm_needs_confirmation_before_it_can_be_set():
    """default 0.0 > MTM (-500) => सेट केल्यास लगेच बंद होईल => पुष्टी-टिक शिवाय बटण disabled."""
    at, b = _run()
    assert any("लगेच बंद होईल" in w.value for w in at.warning)
    btn = [x for x in at.button if "SL Override सेट करा" in x.label][0]
    assert btn.disabled
    confirm = [c for c in at.checkbox if "trade लगेच बंद झाला तरी चालेल" in c.label][0]
    confirm.check()
    at.run()
    btn = [x for x in at.button if "SL Override सेट करा" in x.label][0]
    assert not btn.disabled


def test_override_below_mtm_needs_no_confirmation():
    at, _ = _run()
    at.number_input(key="tsl_override_new_level").set_value(-800.0)
    at.run()
    assert not any("लगेच बंद होईल" in w.value for w in at.warning)
    btn = [x for x in at.button if "SL Override सेट करा" in x.label][0]
    assert not btn.disabled
