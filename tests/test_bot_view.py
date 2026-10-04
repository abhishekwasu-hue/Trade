"""
tests/test_bot_view.py
------------------------
"Bot view" (चार्टवर bot चे प्रत्यक्ष ACTIVE levels + आजचे hits, bot चे RSI/Supertrend, गेट-स्थिती) -- bot_view.py चं गणित, cloud_db.get_zone_hits_today_bulk(),
चार्ट HTML मधले RSI-उंबरठे / 4H Supertrend, आणि Positions चार्टवरची 'trade जिथून घेतला तो level' रेषा.
"""
import numpy as np
import pandas as pd
import pytest

import bot_view as bv
import cloud_db
from position_chart import futures_lines, spot_rule_lines
from tradingview_chart import build_lightweight_chart_html


def _zones(rows):
    return pd.DataFrame(rows, columns=["zone_type", "zone_low", "strength", "status"])


class TestSuffixesAndThresholds:
    def test_5m_instant_follows_timeframe_choice(self):
        assert bv.zone_suffixes("5M Instant", {"timeframe_choice": "5M"}) == ["5M"]
        assert bv.zone_suffixes("5M Instant", {"timeframe_choice": "BOTH"}) == ["1M", "5M"]
        assert bv.zone_suffixes("5M Instant", {"timeframe_choice": "1M"}) == ["1M"]
        assert bv.zone_suffixes("5M Instant", {}) == ["5M"]

    def test_srv2_uses_active_timeframes(self):
        assert bv.zone_suffixes("15M SRv2", {"active_timeframes": ["15M", "30M"]}) == ["15M", "30M"]
        assert bv.zone_suffixes("15M SRv2", {}) == ["15M"]

    def test_classic_and_mcx(self):
        assert bv.zone_suffixes("Classic", {"timeframe_choice": "BOTH"}) == ["5M", "15M"]
        assert bv.zone_suffixes("Classic", {"timeframe_choice": "15M"}) == ["15M"]
        assert bv.zone_suffixes("MCX Futures", {"timeframe_choice": "ALL"}) == ["30M", "60M"]
        assert bv.zone_suffixes("MCX Futures", {"timeframe_choice": "60M"}) == ["60M"]

    def test_rsi_lines(self):
        assert bv.rsi_threshold_values("5M Instant", {"rsi_support_max": 35, "rsi_resistance_min": 65}) == [35.0, 65.0]
        assert bv.rsi_threshold_values("5M Instant", {}) == [40.0, 60.0]
        assert bv.rsi_threshold_values("Classic", {"rsi_neutral_level": 52}) == [52.0]

    def test_supertrend_specs_per_bot(self):
        s = {"supertrend_15m_period": 7, "supertrend_15m_multiplier": 2.0, "supertrend_1h_period": 10, "supertrend_1h_multiplier": 3.0}
        specs = bv.supertrend_specs("5M Instant", s)
        assert [(x["label"], x["minutes"], x["period"], x["multiplier"]) for x in specs] == [("15M", 15, 7, 2.0), ("1H", 60, 10, 3.0)]
        assert [x["label"] for x in bv.supertrend_specs("MCX Futures", {})] == ["1H", "4H"]
        assert bv.supertrend_specs("15M SRv2", {}) == [] and bv.supertrend_specs("Classic", {}) == []

    def test_filter_enabled_only_for_bots_that_have_it(self):
        assert bv.supertrend_filter_enabled("5M Instant", {"entry_supertrend_filter_enabled": True})
        assert not bv.supertrend_filter_enabled("5M Instant", {})
        assert not bv.supertrend_filter_enabled("15M SRv2", {"entry_supertrend_filter_enabled": True})


class TestLevelLines:
    ZONES = _zones([
        ("DYNAMIC_SR_SUPPORT_5M", 24000.0, 3.0, "ACTIVE"),
        ("DYNAMIC_SR_RESISTANCE_5M", 24100.0, 2.0, "ACTIVE"),
        ("DYNAMIC_SR_SUPPORT_15M", 23950.0, 4.0, "ACTIVE"),
        ("DYNAMIC_SR_SUPPORT_5M", 23900.0, 2.0, "BROKEN"),
        ("SUPPORT", 23000.0, 9.0, "ACTIVE"),
    ])

    def test_only_active_dynamic_levels_of_the_bots_timeframes(self):
        lines = bv.level_lines(self.ZONES, ["5M"], {}, 2)
        assert sorted(l["price"] for l in lines) == [24000.0, 24100.0]

    def test_title_has_role_timeframe_strength_and_hits(self):
        lines = bv.level_lines(self.ZONES, ["5M"], {(24000.0, "SUPPORT"): 1}, 2)
        titles = {l["price"]: l["title"] for l in lines}
        assert titles[24000.0] == "S 5M ★3 · 1/2" and titles[24100.0] == "R 5M ★2 · 0/2"

    def test_exhausted_levels_are_faded_and_thin(self):
        lines = bv.level_lines(self.ZONES, ["5M"], {(24000.0, "SUPPORT"): 2}, 2)
        exhausted = [l for l in lines if l["price"] == 24000.0][0]
        fresh = [l for l in lines if l["price"] == 24100.0][0]
        assert exhausted["color"].endswith(",0.35)") and exhausted["width"] == 1
        assert fresh["color"].endswith(",0.95)") and fresh["width"] == 2

    def test_hits_are_per_role(self):
        # आज हा level resistance म्हणून 2 वेळा hit झाला => support म्हणून नाही
        lines = bv.level_lines(self.ZONES, ["5M"], {(24000.0, "RESISTANCE"): 2}, 2)
        assert [l for l in lines if l["price"] == 24000.0][0]["title"].endswith("0/2")

    def test_role_by_price_flips_the_label(self):
        lines = bv.level_lines(self.ZONES, ["5M"], {}, 2, price=24050.0, role_by_price=True)
        assert {l["price"]: l["title"][0] for l in lines} == {24000.0: "S", 24100.0: "R"}
        lines = bv.level_lines(self.ZONES, ["5M"], {}, 2, price=23990.0, role_by_price=True)
        assert {l["price"]: l["title"][0] for l in lines} == {24000.0: "R", 24100.0: "R"}

    def test_far_levels_are_hidden(self):
        # 24100 (+0.42%) ±0.3% च्या बाहेर => लपतो; 23950 (-0.21%) आणि 24000 राहतात
        lines = bv.level_lines(self.ZONES, ["5M", "15M"], {}, 2, price=24000.0, max_distance_pct=0.3)
        assert sorted(l["price"] for l in lines) == [23950.0, 24000.0]
        assert len(bv.level_lines(self.ZONES, ["5M", "15M"], {}, 2, price=24000.0, max_distance_pct=None)) == 3

    def test_empty_inputs(self):
        assert bv.level_lines(None, ["5M"], {}, 2) == [] and bv.level_lines(pd.DataFrame(), ["5M"], {}, 2) == []


def _frame(direction, n=80, freq="15min"):
    ts = pd.date_range("2026-10-01 09:15", periods=n, freq=freq)
    step = 1.0 if direction == "up" else -1.0
    close = 1000 + np.arange(n) * step * 3
    return pd.DataFrame({"timestamp": ts, "open": close - step, "high": close + 2, "low": close - 2, "close": close, "volume": 1, "oi": 0})


class TestSupertrendHelpers:
    def test_align_gives_series_aligned_to_the_chart(self):
        chart = _frame("up", freq="5min", n=200)
        line, direction = bv.align_supertrend(chart, _frame("up", freq="1h"), 10, 3.0)
        assert len(line) == len(chart) and len(direction) == len(chart)

    def test_align_with_no_data(self):
        assert bv.align_supertrend(_frame("up"), None, 10, 3.0) == (None, None)
        assert bv.align_supertrend(_frame("up"), pd.DataFrame(), 10, 3.0) == (None, None)

    def test_directions_use_completed_bars(self):
        specs = [{"label": "15M", "minutes": 15, "period": 10, "multiplier": 3.0}, {"label": "1H", "minutes": 60, "period": 10, "multiplier": 3.0}]
        frames = {"15M": _frame("down"), "1H": _frame("up", freq="1h")}
        out = bv.supertrend_directions(frames, specs, pd.Timestamp("2027-01-01"))
        assert out == {"15M": "BEARISH", "1H": "BULLISH"}
        assert bv.supertrend_directions({}, specs, pd.Timestamp("2027-01-01")) == {"15M": None, "1H": None}

    def test_last_rsi(self):
        assert bv.last_rsi(_frame("up")) > 70 and bv.last_rsi(_frame("down")) < 30
        assert bv.last_rsi(pd.DataFrame()) is None


class TestGateLines:
    def test_rsi_pair_marks_each_side(self):
        s = {"entry_rsi_gate_enabled": True, "rsi_support_max": 40, "rsi_resistance_min": 60}
        line = bv.rsi_gate_line("5M Instant", s, {"5M": 35.0})
        assert "Bullish ✅" in line and "Bearish ❌" in line and "(5M)" in line
        line = bv.rsi_gate_line("5M Instant", s, {"5M": 65.0})
        assert "Bullish ❌" in line and "Bearish ✅" in line
        assert "Bullish ❌" in bv.rsi_gate_line("5M Instant", s, {"5M": 50.0}) and "Bearish ❌" in bv.rsi_gate_line("5M Instant", s, {"5M": 50.0})

    def test_rsi_classic_uses_one_level(self):
        s = {"rsi_neutral_level": 50}
        assert "Bullish ✅" in bv.rsi_gate_line("Classic", s, {"5M": 45.0}) and "Bearish ❌" in bv.rsi_gate_line("Classic", s, {"5M": 45.0})

    def test_rsi_gate_off_and_missing_data(self):
        assert "बंद" in bv.rsi_gate_line("5M Instant", {"entry_rsi_gate_enabled": False}, {"5M": 10.0})
        assert "डेटा नाही" in bv.rsi_gate_line("5M Instant", {}, {"5M": None})

    def test_supertrend_both_bearish_blocks_bullish(self):
        s = {"entry_supertrend_filter_enabled": True}
        line = bv.supertrend_gate_line("5M Instant", s, {"15M": "BEARISH", "1H": "BEARISH"})
        assert "चालू" in line and "Bullish ❌ थांबेल" in line and "Bearish ✅" in line

    def test_supertrend_mixed_or_missing_blocks_nothing(self):
        s = {"entry_supertrend_filter_enabled": True}
        mixed = bv.supertrend_gate_line("MCX Futures", s, {"1H": "BEARISH", "4H": "BULLISH"})
        assert "Bullish ✅" in mixed and "Bearish ✅" in mixed and "1H=BEARISH" in mixed
        assert "डेटा नाही" in bv.supertrend_gate_line("MCX Futures", s, {"1H": None, "4H": "BULLISH"})

    def test_supertrend_filter_off_is_stated(self):
        line = bv.supertrend_gate_line("5M Instant", {}, {"15M": "BEARISH", "1H": "BEARISH"})
        assert "बंद" in line and "प्रत्यक्षात काहीही थांबत नाही" in line

    def test_bots_without_the_filter_give_none(self):
        assert bv.supertrend_gate_line("15M SRv2", {}, {}) is None and bv.supertrend_gate_line("Classic", {}, {}) is None


class FakeCursor:
    def __init__(self, rows):
        self.rows, self.executed = rows, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, rows):
        self.cur, self.closed = FakeCursor(rows), False

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


class TestHitsBulk:
    def test_groups_by_level_and_role_with_one_query(self, monkeypatch):
        rows = [(24000.0, "SUPPORT_5M"), (24000.0, "DYNAMIC_SR_SUPPORT_5M"), (24000.004, "RESISTANCE"), (24100.0, "RESISTANCE"), (24100.0, "weird"), (None, "SUPPORT")]
        conn = FakeConn(rows)
        monkeypatch.setattr(cloud_db, "get_connection", lambda: conn)
        out = cloud_db.get_zone_hits_today_bulk("NIFTY", "2026-10-02")
        assert out == {(24000.0, "SUPPORT"): 2, (24000.0, "RESISTANCE"): 1, (24100.0, "RESISTANCE"): 1}
        assert len(conn.cur.executed) == 1 and conn.closed
        sql, params = conn.cur.executed[0]
        assert "NO_HIT" in sql and params == ("NIFTY", "2026-10-02") and "NOT LIKE 'SKIPPED%%'" in sql  # फक्त खरे entries

    def test_no_database_gives_empty(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
        assert cloud_db.get_zone_hits_today_bulk("NIFTY", "2026-10-02") == {}

    def test_failure_gives_empty(self, monkeypatch):
        class Boom(FakeConn):
            def cursor(self):
                raise RuntimeError("db down")
        conn = Boom([])
        monkeypatch.setattr(cloud_db, "get_connection", lambda: conn)
        assert cloud_db.get_zone_hits_today_bulk("NIFTY", "2026-10-02") == {} and conn.closed


class TestChartHtmlBotViewHooks:
    def _html(self, **kw):
        return build_lightweight_chart_html(_frame("up", freq="5min", n=60), symbol="NIFTY", timeframe_label="5M", rsi_series=pd.Series(np.linspace(30, 70, 60)), **kw)

    def test_default_rsi_lines_are_40_and_60(self):
        assert "[40.0, 60.0].forEach" in self._html()

    def test_custom_rsi_lines(self):
        assert "[35.0, 65.0].forEach" in self._html(rsi_levels=(35, 65))
        assert "[50.0].forEach" in self._html(rsi_levels=(50,))

    def test_4h_supertrend_gets_legend_and_segments(self):
        df = _frame("up", freq="5min", n=60)
        source = _frame("up", freq="1h", n=200)
        source["timestamp"] = pd.date_range("2026-09-10 09:15", periods=200, freq="1h")   # चार्टच्या आधीपासूनचा इतिहास (ATR warm-up)
        line, direction = bv.align_supertrend(df, source, 10, 3.0)
        html = self._html(supertrend_4h_series=line, supertrend_4h_direction=direction)
        assert "4H Supertrend" in html
        assert "4H Supertrend" not in self._html()


class TestTriggerLevelLine:
    def test_nse_extra_line_only_when_level_differs_from_entry(self):
        info = {"source": "MANUAL", "strategy": "BULL_PUT_SPREAD", "entry_spot_price": 24010.0, "entry_level_price": 24000.0}
        lines, _ = spot_rule_lines("NIFTY", info, get_settings=lambda n, s: {})
        assert [l["title"] for l in lines] == ["Entry (spot)", "Level (trade जिथून घेतला)"] and lines[1]["price"] == 24000.0
        info["entry_level_price"] = 24010.0
        assert [l["title"] for l in spot_rule_lines("NIFTY", info, get_settings=lambda n, s: {})[0]] == ["Entry (spot)"]

    def test_mcx_extra_line(self):
        info = {"net_credit": -8000.0, "lots": 1, "lot_size": 100, "sl_pnl_level": -1500.0, "target_pnl_level": 3000.0, "entry_level_price": 7990.0}
        titles = {l["title"]: l["price"] for l in futures_lines(info)}
        assert titles["Level (trade जिथून घेतला)"] == 7990.0 and titles["Entry"] == 8000.0
        info["entry_level_price"] = None
        assert "Level (trade जिथून घेतला)" not in {l["title"] for l in futures_lines(info)}


class TestImportantFarLevels:
    """🎓 "chart war important level disaylach pahije" -- NG 288 वर 299–300 चा resistance ±4% बाहेर म्हणून लपत होता."""
    Z = pd.DataFrame([
        {"zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": 286.4, "strength": 5, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 293.65, "strength": 4, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 300.0, "strength": 3, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 305.5, "strength": 2, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 310.0, "strength": 2, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": 318.0, "strength": 2, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": 270.0, "strength": 3, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_60M", "zone_low": 301.0, "strength": 4, "status": "ACTIVE"},
    ])

    def test_default_still_hides_far_levels(self):
        lines = bv.level_lines(self.Z, ["30M"], {}, 2, price=288.1, max_distance_pct=4.0)
        assert sorted(l["price"] for l in lines) == [286.4, 293.65]

    def test_nearest_three_each_side_shown_faint(self):
        lines = bv.level_lines(self.Z, ["30M"], {}, 2, price=288.1, role_by_price=True, max_distance_pct=4.0, nearest_n=3)
        by = {l["price"]: l for l in lines}
        assert sorted(by) == [270.0, 286.4, 293.65, 300.0, 305.5, 310.0]          # 318 (4था वरचा) नाही
        assert by[300.0]["title"].startswith("R 30M ★3 · 0/2 · दूर 4.1%") and by[300.0]["color"].endswith(",0.6)") and by[300.0]["width"] == 1
        assert by[293.65]["title"] == "R 30M ★4 · 0/2" and by[293.65]["width"] == 2      # जवळचे पूर्वीसारखेच
        assert by[270.0]["title"].startswith("S 30M")

    def test_info_suffix_levels_are_grey_and_marked(self):
        lines = bv.level_lines(self.Z, ["30M"], {}, 2, price=288.1, role_by_price=True, max_distance_pct=4.0, nearest_n=3,
                               info_suffixes=bv.mcx_info_suffixes(["30M"]))
        info = [l for l in lines if "माहिती" in l["title"]]
        assert [l["price"] for l in info] == [301.0] and info[0]["color"].startswith("rgba(158,158,158")
        assert 310.0 in {l["price"] for l in lines}                       # माहितीचा 301 trade होणाऱ्या 310 ला बाहेर ढकलत नाही
        assert bv.mcx_info_suffixes(["30M", "60M"]) == () and bv.mcx_info_suffixes(["60M"]) == ("30M",)
