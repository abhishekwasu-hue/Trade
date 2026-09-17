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
            "touches_5m": 0, "rsi_passed_5m": 0, "touches_15m": 0, "rsi_passed_15m": 0,
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
