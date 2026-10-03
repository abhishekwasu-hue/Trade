"""tests/test_safe_widgets.py -- साठवलेली चुकीची/out-of-range value आल्यावर settings पाने कोसळू नयेत."""
import pytest
from streamlit.testing.v1 import AppTest

from safe_widgets import clamp_number


class TestClampNumber:
    def test_inside_range_unchanged(self):
        assert clamp_number(5, 1, 10) == 5

    def test_below_min_and_above_max(self):
        assert clamp_number(-3, 1, 10) == 1
        assert clamp_number(99, 1, 10) == 10

    @pytest.mark.parametrize("bad", [None, "abc", float("nan"), float("inf")])
    def test_garbage_falls_back_to_default_then_min(self, bad):
        assert clamp_number(bad, 1, 10, default=4) == 4
        assert clamp_number(bad, 2, 10) == 2

    def test_no_bounds(self):
        assert clamp_number("7.5") == 7.5


def _widget_app():
    import streamlit as st
    from safe_widgets import safe_number_input
    st.session_state["out"] = [
        safe_number_input("int out of range", value=500, min_value=1, max_value=50, step=1, key="a"),
        safe_number_input("float stored as int", value=3, min_value=0.5, max_value=9.0, step=0.5, key="b"),
        safe_number_input("none value", value=None, min_value=1, max_value=5, key="c"),
        safe_number_input("below min", value=-4, min_value=-10, max_value=5, step=1, key="d"),
        safe_number_input("no bounds", value="12", key="e"),
    ]


def test_safe_number_input_never_raises_and_clamps():
    at = AppTest.from_function(_widget_app, default_timeout=30)
    at.run()
    assert not at.exception
    assert at.session_state["out"] == [50, 3.0, 1, -4, 12]


def _page_app():
    import streamlit as st
    import builtins
    from unittest.mock import patch
    import cloud_db
    mod = __import__(builtins._PAGE_MODULE)
    real = cloud_db.get_strategy_settings

    def bad_settings(strategy_name, symbol):
        s = dict(real(strategy_name, symbol))
        for k, v in list(s.items()):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            s[k] = 10 ** 7  # सर्व आकडे max च्या पलीकडे
        s["timeframe_choice"] = "BOGUS"
        s["itm_depth_points"] = 100000
        s["naked_itm_depth_points"] = -100000
        return s

    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", "")
    st.session_state.setdefault("product_type", "D")
    with patch.object(cloud_db, "get_strategy_settings", side_effect=bad_settings):
        mod.render()


@pytest.mark.parametrize("module", ["page_bot_dynamic_sr_algo", "page_mcx_futures"])
def test_settings_pages_survive_out_of_range_stored_values(module):
    import builtins
    builtins._PAGE_MODULE = module
    at = AppTest.from_function(_page_app, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
