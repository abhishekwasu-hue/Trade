"""tests/test_dashboard_strategy_builder.py -- Strategy Builder: premium आपोआप अपडेट आणि सुरक्षित Shift."""
from streamlit.testing.v1 import AppTest


def _chain():
    rows = []
    for i, k in enumerate([23900.0, 23950.0, 24000.0, 24050.0, 24100.0]):
        rows.append({
            "strike_price": k,
            "call_options": {"instrument_key": f"CE{int(k)}", "market_data": {"ltp": 200.0 - 10 * i, "oi": 1000}},
            "put_options": {"instrument_key": f"PE{int(k)}", "market_data": {"ltp": 50.0 + 10 * i, "oi": 1000}},
        })
    return rows


def _app():
    import streamlit as st
    import page_dashboard as page
    import builtins
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("raw_chain", builtins._CHAIN)
    st.session_state.setdefault("underlying_price", 24000.0)
    st.session_state.setdefault("atm_strike", 24000.0)
    st.session_state.setdefault("hedge_width_points", 200)
    st.session_state.setdefault("lot_size", 75)
    st.session_state.setdefault("token_input", "")
    page._render_strategy_builder()


def _run():
    import builtins
    builtins._CHAIN = _chain()
    at = AppTest.from_function(_app, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_premium_follows_selected_strike_and_type():
    at = _run()
    assert at.number_input(key="sb_premium_CE_24000.0").value == 180.0
    at.selectbox(key="sb_strike").set_value(24100.0).run()
    assert at.number_input(key="sb_premium_CE_24100.0").value == 160.0
    at.selectbox(key="sb_option_type").set_value("PE").run()
    assert at.number_input(key="sb_premium_PE_24100.0").value == 90.0


def test_shift_to_strike_missing_from_chain_is_refused():
    at = _run()
    at.session_state["strategy_builder_legs"] = [
        {"direction": "SELL", "option_type": "CE", "strike": 24000.0, "premium": 180.0, "lots": 1, "lot_size": 75, "instrument_key": "CE24000"},
    ]
    at.run()
    at.number_input(key="sb_shift").set_value(25).run()
    at.button[[b.label for b in at.button].index("↔️ Shift लागू करा")].click().run()
    assert any("Shift लागू केला नाही" in e.value for e in at.error)
    leg = at.session_state["strategy_builder_legs"][0]
    assert leg["strike"] == 24000.0 and leg["instrument_key"] == "CE24000"


def test_shift_to_valid_strike_refreshes_premium_and_instrument():
    at = _run()
    at.session_state["strategy_builder_legs"] = [
        {"direction": "SELL", "option_type": "CE", "strike": 24000.0, "premium": 180.0, "lots": 1, "lot_size": 75, "instrument_key": "CE24000"},
    ]
    at.run()
    at.number_input(key="sb_shift").set_value(50).run()
    at.button[[b.label for b in at.button].index("↔️ Shift लागू करा")].click().run()
    leg = at.session_state["strategy_builder_legs"][0]
    assert leg["strike"] == 24050.0 and leg["instrument_key"] == "CE24050" and leg["premium"] == 170.0


def _spread_legs(lots):
    return [
        {"direction": "SELL", "option_type": "CE", "strike": 24000.0, "premium": 100.0, "lots": lots, "lot_size": 75, "instrument_key": "A"},
        {"direction": "BUY", "option_type": "CE", "strike": 24100.0, "premium": 40.0, "lots": lots, "lot_size": 75, "instrument_key": "B"},
    ]


def test_strategy_result_is_per_lot_regardless_of_leg_lots():
    import strategy_payoff as sp
    rng = sp.build_default_price_range(24000.0, num_points=200, range_pct=5.0)
    res = {}
    for lots in (1, 3):
        legs = _spread_legs(lots)
        res[lots] = sp.build_strategy_result_from_legs(legs, sp.compute_strategy_payoff_curve(legs, rng))
    for key in ("net_credit", "max_profit", "max_loss"):
        assert abs(res[1][key] - res[3][key]) < 1e-9, key


def test_strategy_result_rejects_uneven_leg_lots():
    import pytest
    import strategy_payoff as sp
    legs = _spread_legs(1)
    legs[1]["lots"] = 2
    with pytest.raises(ValueError):
        sp.build_strategy_result_from_legs(legs, [0.0, 1.0])


def test_execute_panel_blocks_uneven_leg_lots():
    at = _run()
    legs = _spread_legs(1)
    legs[1]["lots"] = 2
    at.session_state["strategy_builder_legs"] = legs
    at.run()
    assert not at.exception
    assert any("Lots सारखे हवेत" in w.value for w in at.warning)
