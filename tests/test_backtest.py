"""
tests/test_backtest.py
--------------------------------
वापरकर्त्याशी चर्चा करून प्रस्तावित तिसऱ्या strategy साठी ("Classical Support/Resistance Reversal",
5M+15M) जोडलेल्या backtest.run_classic_sr_reversal_backtest() साठी — sr_dynamic.compute_dynamic_sr()
आणि signals.calculate_rsi() स्टब करून (त्यांचं स्वतःचं अचूक वर्तन वेगळ्या मॉड्यूलचा भाग, इथे फक्त
Touch+RSI-गेट+SL/Target/Cooldown या नवीन लॉजिकवर लक्ष केंद्रित).
"""
import pandas as pd
import pytest

import backtest


def _row(ts, o, h, l, c):
    return {"timestamp": pd.Timestamp(ts), "open": o, "high": h, "low": l, "close": c}


def _stub_zones(monkeypatch):
    monkeypatch.setattr(backtest, "compute_dynamic_sr", lambda hist, **kw: {
        "support": [{"level": 100.0, "touches": 3}],
        "resistance": [{"level": 120.0, "touches": 3}],
    })


def _stub_rsi(monkeypatch, value):
    monkeypatch.setattr(backtest, "calculate_rsi", lambda df, period=14: pd.Series([value] * len(df)))


_HIST_DAY = [_row("2024-01-01 09:15:00", 100, 100, 100, 100)]


class TestRunClassicSrReversalBacktest:
    def test_empty_inputs_returns_empty(self):
        result = backtest.run_classic_sr_reversal_backtest(pd.DataFrame(), pd.DataFrame())
        assert result == {"total": 0, "signals": [], "funnel": {
            "touches_5m": 0, "rsi_passed_5m": 0, "swing_passed_5m": 0,
            "demand_supply_passed_5m": 0, "trendline_passed_5m": 0,
            "touches_15m": 0, "rsi_passed_15m": 0, "swing_passed_15m": 0,
            "demand_supply_passed_15m": 0, "trendline_passed_15m": 0,
        }}

    def test_support_touch_target_hit(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)  # BULLISH gate: RSI < rsi_neutral(50) हवं
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 101, 101.5, 99.8, 100.9),   # support(100) touch -> BULLISH candidate
            _row("2024-01-02 09:20:00", 100.9, 101.0, 100.5, 100.95),  # high>=target(100.8) -> TARGET
        ])
        result = backtest.run_classic_sr_reversal_backtest(df_5m, pd.DataFrame(), min_lookback_days=1)
        assert result["total"] == 1
        sig = result["signals"][0]
        assert sig["direction"] == "BULLISH"
        assert sig["timeframe"] == "5M"
        assert sig["level"] == 100.0
        assert sig["outcome"] == "TARGET"
        assert sig["bars_to_exit"] == 1
        assert result["target_count"] == 1
        assert result["win_rate"] == 100.0
        assert result["funnel"]["touches_5m"] >= 1
        assert result["funnel"]["rsi_passed_5m"] >= 1

    def test_resistance_touch_sl_hit(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 70)  # BEARISH gate: RSI > rsi_neutral(50) हवं
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 119, 120.2, 118.8, 119.5),  # resistance(120) touch -> BEARISH candidate
            _row("2024-01-02 09:20:00", 119.5, 120.6, 119.3, 120.5),  # high>=sl(120.48) -> SL
        ])
        result = backtest.run_classic_sr_reversal_backtest(df_5m, pd.DataFrame(), min_lookback_days=1)
        assert result["total"] == 1
        sig = result["signals"][0]
        assert sig["direction"] == "BEARISH"
        assert sig["level"] == 120.0
        assert sig["outcome"] == "SL"
        assert result["sl_count"] == 1
        assert result["win_rate"] == 0.0

    def test_rsi_filter_blocks_wrong_direction(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 70)  # support touch(BULLISH) ला RSI<50 हवं होतं, 70 आहे -> गेट अपयशी
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 101, 101.5, 99.8, 100.9),
            _row("2024-01-02 09:20:00", 100.9, 101.0, 100.5, 100.95),
        ])
        result = backtest.run_classic_sr_reversal_backtest(df_5m, pd.DataFrame(), min_lookback_days=1)
        assert result["total"] == 0
        assert result["funnel"]["touches_5m"] >= 1
        assert result["funnel"]["rsi_passed_5m"] == 0

    def test_cooldown_blocks_second_signal_while_position_open(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 101, 101.2, 99.9, 100.5),    # touch #1 -> candidate 1 (BULLISH)
            _row("2024-01-02 09:20:00", 100.5, 100.6, 99.95, 100.02),  # touch #2 (within cooldown of #1)
            _row("2024-01-02 09:25:00", 100.02, 100.05, 99.98, 100.0),  # neither SL(99.6) नाही Target(100.8) लागत नाही
        ])
        result = backtest.run_classic_sr_reversal_backtest(df_5m, pd.DataFrame(), min_lookback_days=1)
        # candidate 1 ने position उघडली (अजून OPEN, cooldown सक्रिय) -> candidate 2 skip झालाच पाहिजे
        assert result["total"] == 1
        assert result["signals"][0]["entry_time"] == pd.Timestamp("2024-01-02 09:15:00")
        assert result["open_count"] == 1

    def test_pools_5m_and_15m_chronologically(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:30:00", 101, 101.5, 99.8, 100.9),   # 15M candidate नंतरचा 5M touch
            _row("2024-01-02 09:35:00", 100.9, 101.6, 100.5, 101.5),  # target hit
        ])
        df_15m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 101, 101.5, 99.8, 100.9),   # आधी येणारा 15M touch
            _row("2024-01-02 09:30:00", 100.9, 101.6, 100.5, 101.5),  # target hit
        ])
        result = backtest.run_classic_sr_reversal_backtest(df_5m, df_15m, min_lookback_days=1, cooldown_minutes=5)
        # 15M candidate (09:15) आधी resolve होतो (exit ~09:30 + 5min cooldown = 09:35) -> 5M candidate
        # (09:30) त्या cooldown मध्येच येतो, त्यामुळे skip.
        assert result["total"] == 1
        assert result["signals"][0]["timeframe"] == "15M"
        assert result["touch_15m_count"] == 1
        assert result["touch_5m_count"] == 0


# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Refinement — Swing High/Low, Demand/Supply,
# Trendline) — इथे compute_dynamic_sr/calculate_rsi स्टब्ड आहेत (आधीसारखेच), पण
# find_swings/analyze_chart_zones/detect_trendline खऱ्याच वापरल्या जातात — त्यामुळे प्रत्यक्ष
# किंमत-रचना (zigzag) काळजीपूर्वक तयार करावी लागते जेणेकरून खरी swing/demand-supply/trendline
# अवस्था predictable राहील (स्क्रिप्टने आधी पडताळून घेतलेली).

# दोन खरे swing lows (100, 100) + शेवटी level=100 ला पुन्हा touch — find_swings/analyze_chart_zones
# दोघांनाही "level=100 च्या अगदी जवळ/आतला अलीकडचा confirmed swing/demand-zone" दाखवतात.
_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100 = [108, 104, 101, 100.0, 101, 104, 108.0, 104, 101, 100.0, 101, 104, 109.0, 104, 101, 100.0]

# तीन ascending swing lows (98 -> 99 -> 100.3) -> वैध ASCENDING_SUPPORT trendline, पण शेवटचा close
# (100.0, पुन्हा level=100 touch) त्या trendline च्या खाली -> BROKEN.
_ZIGZAG_WITH_BROKEN_ASCENDING_TRENDLINE = [
    108, 104, 101, 98.0, 101, 104, 108.0, 104, 101, 99.0, 101, 104, 109.0, 104, 101, 100.3,
    104, 108, 113.0, 108, 104, 100.0,
]


def _flat_bars(values, start_ts="2024-01-02 09:15:00"):
    start = pd.Timestamp(start_ts)
    return [_row(start + pd.Timedelta(minutes=5 * i), v, v, v, v) for i, v in enumerate(values)]


class TestClassicSrReversalEntryRefinement:
    def test_swing_confluence_gate_blocks_on_insufficient_data(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 101, 101.5, 99.8, 100.9),
            _row("2024-01-02 09:20:00", 100.9, 101.0, 100.5, 100.95),
        ])
        result = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, swing_confluence_enabled=True,
        )
        # window मध्ये find_swings() साठी पुरेसा डेटा नाही (order*2+1 पेक्षा कमी बार) -> गेट अडवतो
        assert result["total"] == 0

    def test_swing_confluence_gate_passes_with_confirmed_swing_near_level(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + _flat_bars(_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100))
        result = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, swing_confluence_enabled=True,
        )
        assert result["total"] == 1
        assert result["signals"][0]["direction"] == "BULLISH"
        assert result["funnel"]["swing_passed_5m"] >= 1

    def test_swing_min_move_pct_filters_minor_swing_and_blocks_entry(self, monkeypatch):
        """🎓 वापरकर्त्याने प्रत्यक्ष चार्ट screenshot वरून "major swings only" दाखवलं, आणि तीच कल्पना
        strategy मध्ये आणायला सांगितलं — swing_min_move_pct=0 (डीफॉल्ट) सह, level(100) पासून फक्त
        0.05 दूर असलेला किरकोळ (मागच्या high पासून फक्त ~2.9% हालचालीचा) स्विंग लो गेट पास करतो. पण
        swing_min_move_pct=3.5 सह तो किरकोळ स्विंग गाळला जातो, आणि उरलेला एकमेव major स्विंग लो (90.0)
        tolerance च्या खूप बाहेर असल्याने गेट संपूर्ण signal अडवतो — नेमकं हेच फरक दाखवण्यासाठी दोन्ही
        बाजू (baseline pass + filtered block) एकाच डेटासेटवर तपासलेल्या."""
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        zigzag = [108, 104, 101, 90.0, 95, 99, 103.0, 102, 101, 100.05, 101, 102, 103.5, 101, 100.5, 100.0]
        df_5m = pd.DataFrame(_HIST_DAY + _flat_bars(zigzag))

        baseline = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, swing_confluence_enabled=True,
        )
        assert baseline["total"] == 1

        filtered = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, swing_confluence_enabled=True, swing_min_move_pct=3.5,
        )
        assert filtered["total"] == 0

    def test_demand_supply_gate_blocks_on_insufficient_data(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + [
            _row("2024-01-02 09:15:00", 101, 101.5, 99.8, 100.9),
            _row("2024-01-02 09:20:00", 100.9, 101.0, 100.5, 100.95),
        ])
        result = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, demand_supply_gate_enabled=True,
        )
        # structure_15m सारखीच classify_market_structure() ला किमान 2+2 confirmed swings लागतात,
        # इथे अजिबातच नाहीत -> demand_zone=None -> गेट अडवतो
        assert result["total"] == 0

    def test_demand_supply_gate_passes_when_level_inside_zone(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + _flat_bars(_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100))
        result = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, demand_supply_gate_enabled=True,
        )
        assert result["total"] == 1
        assert result["funnel"]["demand_supply_passed_5m"] >= 1

    def test_trendline_gate_blocks_when_broken(self, monkeypatch):
        _stub_zones(monkeypatch)
        _stub_rsi(monkeypatch, 30)
        df_5m = pd.DataFrame(_HIST_DAY + _flat_bars(_ZIGZAG_WITH_BROKEN_ASCENDING_TRENDLINE))
        result_gated = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1, trendline_gate_enabled=True,
        )
        assert result_gated["total"] == 0

        # हाच डेटा, गेट बंद असताना — बेसलाइन वर्तन अबाधित (गेट खरंच काहीतरी अडवत होता, योगायोगाने रिकामं नाही)
        result_ungated = backtest.run_classic_sr_reversal_backtest(
            df_5m, pd.DataFrame(), min_lookback_days=1,
        )
        assert result_ungated["total"] == 1
        assert result_ungated["signals"][0]["direction"] == "BULLISH"
