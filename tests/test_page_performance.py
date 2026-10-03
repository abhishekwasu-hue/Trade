"""tests/test_page_performance.py -- Performance पानाचे Streamlit AppTest + शुद्ध helper tests (DB/नेटवर्क mock)."""
import builtins

import pandas as pd
from streamlit.testing.v1 import AppTest

import page_performance as pp


# ---------- शुद्ध helpers ----------
def test_source_labels_cover_classic_and_mcx():
    assert pp._SOURCE_LABELS["classic_sr_reversal"] == "Classical S/R Reversal (5M+15M)"
    assert pp._SOURCE_LABELS["mcx_futures"] == "MCX Futures Trader"


def _row(source, tf="5M", lvl=24000.0, strategy="BULL_PUT_SPREAD", tag=None):
    return {"source": source, "entry_timeframe": tf, "entry_level_price": lvl, "strategy": strategy, "entry_reason_tag": tag}


def test_entry_reason_mentions_sr_touch_for_bot_trades():
    assert "S/R level" in pp._entry_reason_text(_row("dynamic_sr_instant"))
    assert "S/R level" in pp._entry_reason_text_en(_row("classic_sr_reversal"))


def test_entry_reason_has_no_fake_sr_touch_for_manual_sources():
    for src in ("MANUAL", "DASHBOARD", "strategy_builder", "MULTI_ACCOUNT", "UNKNOWN"):
        r = _row(src, tf=None, lvl=float("nan"))
        assert "S/R level" not in pp._entry_reason_text(r) and "S/R level" not in pp._entry_reason_text_en(r)
        assert "BULL_PUT_SPREAD" in pp._entry_reason_text(r)


# ---------- AppTest ----------
def _app():
    import builtins as b
    import pandas as pd
    import streamlit as st
    from unittest.mock import patch
    import page_performance as page
    st.session_state["symbol"] = b._SYMBOL
    st.session_state["token_input"] = ""
    empty = pd.DataFrame()
    totals = {"total_trades": 0, "gross_pnl": 0, "total_charges": 0, "net_pnl": 0, "total_orders": 0,
              "charges_by_broker": {}, "charges_breakdown": {}}
    with patch.object(page, "generate_pnl_report", return_value=(empty, totals)), \
         patch.object(page, "get_performance_summary", return_value={"total_trades": 0}), \
         patch.object(page, "get_equity_curve_data", return_value=empty), \
         patch.object(page, "get_performance_by_group", return_value=empty), \
         patch.object(page, "get_performance_by_two_groups", return_value=empty), \
         patch.object(page, "get_closed_trades_detail", return_value=empty), \
         patch.object(page, "get_exit_reason_breakdown", return_value=empty), \
         patch.object(page, "get_live_vs_shadow_paper_pairs", return_value=empty), \
         patch.object(page, "get_sl_tsl_overshoot", return_value=empty):
        page.render()


def _run(symbol, mode=None):
    builtins._SYMBOL = symbol
    at = AppTest.from_function(_app, default_timeout=60)
    at.run()
    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    if mode:
        at.radio(key="perf_mode_filter").set_value(mode)
        at.run()
        assert not at.exception
    return at


def _warnings(at):
    return " ".join(w.value for w in at.warning)


def test_nifty_stored_data_is_allowed_and_buttons_enabled():
    at = _run("NIFTY")
    assert "साठवलेला डेटा फक्त" not in _warnings(at)
    run_buttons = [b for b in at.button if "सिग्नल्स आले ते तपासा" in b.label or "Backtest चालवा" in b.label]
    assert run_buttons and not any(b.disabled for b in run_buttons)


def test_non_nifty_with_stored_data_warns_and_disables_every_backtest_run_button():
    at = _run("BANKNIFTY")
    assert _warnings(at).count("साठवलेला डेटा फक्त") >= 3  # Intraday + Swing + Classical + Multi-Strategy (tabs)
    run_buttons = [b for b in at.button if "सिग्नल्स आले ते तपासा" in b.label or "Backtest चालवा" in b.label]
    assert run_buttons and all(b.disabled for b in run_buttons)


def test_pnl_report_tab_shows_which_mode_filter_is_applied():
    at = _run("NIFTY", mode="फक्त LIVE")
    captions = " ".join(c.value for c in at.caption)
    assert "दाखवलेला Mode: **फक्त LIVE**" in captions
