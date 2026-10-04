"""tests/test_page_opportunity_engine.py -- Opportunity Engine पानाचा AppTest (नेटवर्कशिवाय, कृत्रिम 1M/5M candles) + report helpers."""
import builtins

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from opportunity_engine import report as R
from opportunity_engine.zones import build_levels


def _fine_1m(days=70, seed=11, start="2023-10-02"):
    rng = np.random.default_rng(seed)
    ds = pd.bdate_range(start, periods=days)
    ts = pd.DatetimeIndex([d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=m) for d in ds for m in range(375)])
    close = 21000 + np.cumsum(rng.normal(0, 2.5, len(ts))) + 250 * np.sin(np.arange(len(ts)) / 900.0)
    return pd.DataFrame({"timestamp": ts, "open": close - 0.4, "high": close + 1.5, "low": close - 1.5, "close": close, "volume": 0})


def _app():
    from unittest.mock import patch
    import builtins
    import pandas as pd
    import streamlit as st
    import page_opportunity_engine as page
    st.session_state.setdefault("symbol", builtins._OE_SYMBOL)
    st.session_state.setdefault("token_input", builtins._OE_TOKEN)
    st.session_state.setdefault("underlying_price", 21000.0)
    page._offline_bundle.clear()
    page._live_bundle.clear()

    def fake_fetch(token, symbol, spot, interval="30minute", lookback_days=None):
        if interval == "5minute":
            return builtins._OE_FINE5.copy()
        if interval == "day":
            return builtins._OE_DAILY.copy()
        return pd.DataFrame()

    with patch.object(page.real_nifty_data, "load_nifty_1min", side_effect=lambda a=None, b=None: builtins._OE_FINE.copy()), \
            patch.object(page, "fetch_candles", side_effect=fake_fetch):
        page.render()


def _run(symbol="NIFTY", token="x", live=False):
    fine = _fine_1m()
    five = fine.set_index("timestamp").resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
    daily = fine.assign(d=fine["timestamp"].dt.normalize()).groupby("d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum")).reset_index().rename(columns={"d": "timestamp"})
    builtins._OE_FINE, builtins._OE_FINE5, builtins._OE_DAILY = fine, five, daily
    builtins._OE_SYMBOL, builtins._OE_TOKEN = symbol, token
    at = AppTest.from_function(_app, default_timeout=180)
    at.run()
    if live:
        at.radio(key="oe_source").set_value("Upstox (लाईव्ह, सध्याचा symbol)").run()
    return at


def test_offline_page_renders_all_tabs_without_error():
    at = _run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert len(at.tabs) == 7
    assert at.dataframe, "Structure वही / levels चे तक्ते दिसले पाहिजेत"


def test_chart_timeframe_switch_and_grades_filter_do_not_crash():
    at = _run()
    for tf in ("1d", "4h", "15m", "5m", "1h"):
        at.radio(key="oe_chart_tf").set_value(tf).run()
        assert not at.exception and not at.error, (tf, [e.value for e in at.error])
    at.multiselect(key="oe_grades").set_value(["A", "B", "C"]).run()
    assert not at.exception and not at.error
    at.multiselect(key="oe_grades").set_value([]).run()
    assert not at.exception and not at.error


def test_non_nifty_symbol_on_offline_source_warns_and_live_without_token_asks_for_token():
    at = _run(symbol="BANKNIFTY")
    assert not at.exception and any("फक्त NIFTY" in w.value for w in at.warning)
    at = _run(token="", live=True)
    assert not at.exception and any("Access Token" in i.value for i in at.info)


def test_live_source_with_patched_fetch_renders():
    at = _run(live=True)
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert at.dataframe


def test_report_helpers_chart_lines_and_tables():
    fine = _fine_1m()
    frames, journal = R.bundle_from_fine(fine)
    price = float(frames["15m"]["close"].iloc[-1])
    result = build_levels(journal, frames, "NIFTY", price, fine=frames["5m"])
    lines, near = R.chart_lines(result["levels"], price, max_levels=5, grades=("A", "B", "C"))
    assert len(near) <= 5 and all({"price", "title", "color", "dashed", "width"} <= set(line) for line in lines)
    assert all(line["title"].startswith("L") for line in lines)
    table = R.levels_table(result["levels"], price)
    assert table.empty or {"level_id", "Grade", "Freshness", "Status", "Core", "Outer"} <= set(table.columns)
    csv = R.structure_csv(journal)
    assert csv.splitlines()[0].startswith("time,tf,event")
    states = R.state_rows(journal)
    assert list(states["TF"]) == ["Daily", "4H", "1H", "15M", "5M"]
    per_tf, short = R.quality_report(frames)
    assert len(per_tf) == 5 and (per_tf["Bars"] > 0).all()
    assert R.chart_lines(result["levels"], None) == ([], [])


def test_unsupported_symbol_like_mcx_shows_a_clear_warning_and_nothing_else():
    at = _run(symbol="CRUDEOIL")
    assert not at.exception and not at.error
    assert any("फक्त NIFTY" in w.value and "CRUDEOIL" in w.value for w in at.warning)
    assert not at.dataframe


def test_bias_tab_and_candidate_tester_respond_to_inputs_without_error():
    at = _run()
    assert any(m.label == "Bias" for m in at.metric)
    for direction in ("SHORT", "LONG"):
        at.selectbox(key="oe_t_dir").set_value(direction).run()
        assert not at.exception and not at.error, [e.value for e in at.error]
    at.selectbox(key="oe_t_kind").set_value("BREAKOUT").run()
    at.number_input(key="oe_t_entry").set_value(21000.0).run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert any("Gate:" in w.value for w in list(at.warning) + list(at.success))


def test_backtest_tab_runs_on_synthetic_data_and_shows_tables():
    import builtins
    at = _run()
    builtins._OE_FINE = _fine_1m(days=90, seed=4, start="2023-10-02")
    at.run()
    at.date_input(key="oe_bt_start").set_value(pd.Timestamp("2024-01-15").date())
    at.date_input(key="oe_bt_end").set_value(pd.Timestamp("2024-03-27").date())
    at.multiselect(key="oe_bt_variants").set_value(["V1", "V3"])
    at.button(key="oe_bt_run").click().run(timeout=300)
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert any("Variants तुलना" in str(m.value) for m in at.markdown) or at.dataframe
    assert any("V1" in str(h.value) for h in at.markdown)


def test_backtest_tab_with_diagnostics_renders_tables():
    import builtins
    at = _run()
    builtins._OE_FINE = _fine_1m(days=90, seed=4, start="2023-10-02")
    at.run()
    at.date_input(key="oe_bt_start").set_value(pd.Timestamp("2024-01-15").date())
    at.date_input(key="oe_bt_end").set_value(pd.Timestamp("2024-03-27").date())
    at.checkbox(key="oe_bt_diag").check()
    at.button(key="oe_bt_run").click().run(timeout=300)
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert any("निदान" in str(e.label) for e in at.expander)
    assert any("Funnel" in str(m.value) for m in at.markdown)
