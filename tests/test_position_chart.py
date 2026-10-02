"""
tests/test_position_chart.py
------------------------------
"Positions पानावर चार्ट: entry, stop, target ... रेषा" आणि "Dashboard वर mini NIFTY/BANKNIFTY chart" -- रेषा ठरवणारं गणित (position_chart.py),
चार्ट HTML मधल्या आडव्या रेषा, आणि mini चार्टचा HTML.
"""
import numpy as np
import pandas as pd
import pytest

from position_chart import futures_lines, spot_rule_lines
from tradingview_chart import build_lightweight_chart_html, build_mini_chart_html


def _titles(lines):
    return {l["title"]: l["price"] for l in lines}


class TestFuturesLines:
    def test_long_trade_sl_below_target_above(self):
        # BUY => net_credit ऋण: Entry = |net_credit| = 8000; qty = 1*100; SL -1500 => 8000 + (-1500)/100 = 7985; Target 3000 => 8030
        info = {"net_credit": -8000.0, "lots": 1, "lot_size": 100, "sl_pnl_level": -1500.0, "target_pnl_level": 3000.0, "manual_sl_override_pnl": None}
        t = _titles(futures_lines(info))
        assert t == {"Entry": 8000.0, "SL": 7985.0, "Target": 8030.0}

    def test_short_trade_sl_above_target_below(self):
        info = {"net_credit": 8000.0, "lots": 1, "lot_size": 100, "sl_pnl_level": -1500.0, "target_pnl_level": 3000.0, "manual_sl_override_pnl": None}
        t = _titles(futures_lines(info))
        assert t == {"Entry": 8000.0, "SL": 8015.0, "Target": 7970.0}

    def test_manual_override_replaces_sl_and_is_labelled(self):
        info = {"net_credit": -8000.0, "lots": 1, "lot_size": 100, "sl_pnl_level": -1500.0, "target_pnl_level": 3000.0, "manual_sl_override_pnl": -500.0}
        lines = futures_lines(info)
        assert _titles(lines)["SL (Manual Override)"] == 7995.0 and "SL" not in _titles(lines)
        assert [l for l in lines if l["title"].startswith("SL")][0]["color"] == "#ff9800"

    def test_missing_levels_give_only_entry_and_no_net_credit_gives_nothing(self):
        assert _titles(futures_lines({"net_credit": -8000.0, "lots": 1, "lot_size": 100})) == {"Entry": 8000.0}
        assert futures_lines({"net_credit": None}) == []


class TestSpotRuleLines:
    SETTINGS = {"spread_sl_spot_pct": 0.5, "spread_target_spot_pct": 1.0, "naked_sl_spot_pct": 0.4, "naked_target_spot_pct": 0.8}

    def _lines(self, strategy, source="dynamic_sr_instant", spot=24000.0, level=None, settings=None):
        info = {"source": source, "strategy": strategy, "entry_spot_price": spot, "entry_level_price": level}
        calls = []

        def get_settings(ns, sym):
            calls.append((ns, sym))
            return settings or self.SETTINGS

        lines, note = spot_rule_lines("NIFTY", info, get_settings=get_settings)
        return lines, note, calls

    def test_bullish_spread(self):
        lines, note, calls = self._lines("BULL_PUT_SPREAD")
        t = _titles(lines)
        assert t["Entry (spot)"] == 24000.0 and t["SL (Spot 0.5%)"] == 23880.0 and t["Target (Spot 1%)"] == 24240.0
        assert calls == [("1m_instant", "NIFTY")] and "अंदाजित" in note

    def test_bearish_spread_is_mirrored(self):
        t = _titles(self._lines("BEAR_CALL_SPREAD")[0])
        assert t["SL (Spot 0.5%)"] == 24120.0 and t["Target (Spot 1%)"] == 23760.0

    def test_naked_uses_naked_thresholds(self):
        t = _titles(self._lines("NAKED_PUT")[0])
        assert t["SL (Spot 0.4%)"] == 24096.0 and t["Target (Spot 0.8%)"] == 23808.0

    def test_namespace_follows_the_source(self):
        assert self._lines("BULL_PUT_SPREAD", source="classic_sr_reversal")[2] == [("classic_sr_reversal", "NIFTY")]
        assert self._lines("BULL_PUT_SPREAD", source="srv2_momentum_reversal")[2] == [("15m_dynamic_sr", "NIFTY")]

    def test_anchor_falls_back_to_entry_level_price(self):
        lines, _, _ = self._lines("BULL_PUT_SPREAD", spot=None, level=23990.0)
        assert _titles(lines)["Entry (spot)"] == 23990.0

    def test_other_sources_get_entry_only(self):
        lines, note, calls = self._lines("BULL_PUT_SPREAD", source="MANUAL")
        assert [l["title"] for l in lines] == ["Entry (spot)"] and calls == [] and "₹ P&L" in note

    def test_iron_condor_gets_entry_only(self):
        assert [l["title"] for l in self._lines("IRON_CONDOR")[0]] == ["Entry (spot)"]

    def test_no_anchor_no_lines(self):
        lines, note, _ = self._lines("BULL_PUT_SPREAD", spot=None, level=None)
        assert lines == [] and "साठवलेला नाही" in note

    def test_settings_failure_degrades_to_entry_only(self):
        info = {"source": "dynamic_sr_instant", "strategy": "BULL_PUT_SPREAD", "entry_spot_price": 24000.0}

        def boom(ns, sym):
            raise RuntimeError("supabase down")

        lines, note = spot_rule_lines("NIFTY", info, get_settings=boom)
        assert [l["title"] for l in lines] == ["Entry (spot)"] and "settings" in note


def _df(n=40, days=2):
    rng = np.random.default_rng(4)
    ts = []
    for d in range(days):
        ts += list(pd.date_range(f"2026-09-{28 + d} 09:15", periods=n // days, freq="5min"))
    close = 24000 + np.cumsum(rng.normal(0, 4, len(ts)))
    return pd.DataFrame({"timestamp": ts, "open": close - 1, "high": close + 3, "low": close - 3, "close": close, "volume": 100, "oi": 0})


class TestTradeLinesInChartHtml:
    def test_lines_and_autoscale_helper_present(self):
        lines = [{"price": 23900, "title": "SL", "color": "#F23645"}, {"price": 24100, "title": "Target", "color": "#089981", "dashed": False}]
        html = build_lightweight_chart_html(_df(), symbol="NIFTY", timeframe_label="5M", trade_lines=lines)
        assert '"title": "SL"' in html and '"price": 24100.0' in html and "tradeLineBounds" in html
        assert '"lo": 23900.0' in html and '"hi": 24100.0' in html

    def test_no_lines_means_empty_and_no_bounds(self):
        html = build_lightweight_chart_html(_df(), symbol="NIFTY", timeframe_label="5M")
        assert "const tradeLines = [];" in html and "const tradeLineBounds = null;" in html

    def test_malformed_line_items_are_skipped(self):
        html = build_lightweight_chart_html(_df(), symbol="NIFTY", timeframe_label="5M", trade_lines=[{"title": "no price"}, {"price": "x"}])
        assert "const tradeLines = [];" in html


class TestMiniChartHtml:
    def test_empty_or_none(self):
        assert "डेटा उपलब्ध नाही" in build_mini_chart_html(None, "NIFTY")
        assert "डेटा उपलब्ध नाही" in build_mini_chart_html(pd.DataFrame(), "NIFTY")

    def test_shows_symbol_last_price_and_change_vs_previous_day(self):
        df = _df(n=40, days=2)
        html = build_mini_chart_html(df, "NIFTY")
        last = df["close"].iloc[-1]
        prev = df[df["timestamp"].dt.day == 28]["close"].iloc[-1]
        assert "NIFTY" in html and f"{last:,.2f}" in html and f"{(last - prev) / prev * 100:+.2f}%" in html

    def test_single_day_has_no_change_text(self):
        html = build_mini_chart_html(_df(n=20, days=1), "BANKNIFTY")
        assert "BANKNIFTY" in html and "%</span>" not in html

    def test_only_last_bars_are_sent(self):
        html = build_mini_chart_html(_df(n=400, days=2), "NIFTY", max_bars=50)
        assert html.count('"open":') == 50
