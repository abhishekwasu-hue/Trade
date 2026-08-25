"""
tests/test_signals.py
-------------------------
signals.py चे सर्वात महत्त्वाचे functions — विशेषतः जिथे या संभाषणात खरे bugs सापडले होते
(RSI, ATR, Supertrend — सर्व Wilder's Smoothing न वापरता साधी सरासरी वापरत होते, दुरुस्त केलं होतं).
इथले tests त्याच दुरुस्त्या राखल्या जातात याची कायमची खात्री देतात.
"""
import numpy as np
import pandas as pd
import pytest

from signals import (
    calculate_rsi, calculate_supertrend, compute_atr, detect_candlestick_pattern,
    find_support_resistance_levels, find_swing_sr_levels_rolling, get_nearest_sr,
)


class TestCalculateRSI:
    """RSI — Wilder's Smoothing Method (साधी rolling mean नाही — इथेच खरा bug सापडला होता)."""

    def test_pure_uptrend_approaches_100(self, ):
        df = pd.DataFrame({"close": [100 + i for i in range(30)]})
        rsi = calculate_rsi(df, period=14)
        assert rsi.iloc[-1] > 99

    def test_pure_downtrend_approaches_0(self):
        df = pd.DataFrame({"close": [100 - i for i in range(30)]})
        rsi = calculate_rsi(df, period=14)
        assert rsi.iloc[-1] < 1

    def test_alternating_prices_near_50(self):
        prices = [100]
        for i in range(30):
            prices.append(prices[-1] + (5 if i % 2 == 0 else -5))
        df = pd.DataFrame({"close": prices})
        rsi = calculate_rsi(df, period=14)
        assert 45 < rsi.iloc[-1] < 55

    def test_matches_classic_textbook_example(self):
        """Wilder च्या प्रसिद्ध textbook उदाहरणाशी जुळतं का — हाच सर्वात कडक, प्रमाणित तपासणी."""
        classic_prices = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                           45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
        df = pd.DataFrame({"close": classic_prices})
        rsi = calculate_rsi(df, period=14)
        assert 68 < rsi.iloc[14] < 73    # अपेक्षित ~70.5
        assert 63 < rsi.iloc[15] < 69    # अपेक्षित ~66.3

    def test_bounded_between_0_and_100(self):
        np.random.seed(1)
        prices = 100 + np.cumsum(np.random.randn(200))
        df = pd.DataFrame({"close": prices})
        rsi = calculate_rsi(df, period=14).dropna()
        assert rsi.min() >= 0 and rsi.max() <= 100


class TestComputeATR:
    """ATR (Trailing SL साठी वापरला जातो — खरे पैसे) — Wilder's Smoothing."""

    def test_insufficient_data_returns_none(self):
        df = pd.DataFrame([{"open": 100, "high": 105, "low": 95, "close": 102} for _ in range(5)])
        assert compute_atr(df, period=14) is None

    def test_constant_range_converges_to_range(self):
        rows = [{"open": 100, "high": 110, "low": 90, "close": 100} for _ in range(50)]
        df = pd.DataFrame(rows)
        atr_val = compute_atr(df, period=14)
        assert 19.5 < atr_val < 20.5  # स्थिर २०-पॉइंट range -> ATR तेच जवळपास असायला हवं


class TestCalculateSupertrend:
    """Supertrend दिशा — ATR-आधारित, Wilder's Smoothing."""

    def test_strong_uptrend_gives_bullish_direction(self, trending_up_df):
        _, direction = calculate_supertrend(trending_up_df, period=10, multiplier=3)
        assert int(direction.iloc[-1]) == 1

    def test_strong_downtrend_gives_bearish_direction(self, trending_down_df):
        _, direction = calculate_supertrend(trending_down_df, period=10, multiplier=3)
        assert int(direction.iloc[-1]) == -1


class TestCandlestickPatterns:
    """Hammer/Engulfing/Star पॅटर्न ओळख — निश्चित भूमितीय निकषांवर आधारित."""

    def test_hammer_detected(self):
        rows = [{"open": 100, "high": 102, "low": 98, "close": 101} for _ in range(5)]
        # स्पष्ट Hammer: छोटा body, मोठी खालची wick, नगण्य वरची wick
        rows.append({"open": 99, "high": 100, "low": 85, "close": 100})
        df = pd.DataFrame(rows)
        assert detect_candlestick_pattern(df) == "HAMMER"

    def test_no_pattern_on_plain_candle(self):
        rows = [{"open": 100, "high": 102, "low": 98, "close": 100.5} for _ in range(5)]
        df = pd.DataFrame(rows)
        assert detect_candlestick_pattern(df) is None


class TestSupportResistance:
    """S/R शोध आणि जवळचा S/R निवड — get_nearest_sr चं इनपुट-फॉरमॅट (साध्या संख्यांची यादी) राखलं जातं."""

    def test_get_nearest_sr_picks_correct_levels(self):
        sr_levels = {"support": [23800, 24000, 24200], "resistance": [24600, 24800, 25000]}
        support, resistance = get_nearest_sr(sr_levels, current_price=24300)
        assert support == 24200  # सर्वात जवळचा, किमतीच्या खालचा
        assert resistance == 24600  # सर्वात जवळचं, किमतीच्या वरचं

    def test_get_nearest_sr_handles_empty(self):
        support, resistance = get_nearest_sr({"support": [], "resistance": []}, current_price=24300)
        assert support is None and resistance is None

    def test_rolling_sr_returns_dict_with_both_keys(self, trending_up_df):
        result = find_swing_sr_levels_rolling(trending_up_df, window=20)
        assert "support" in result and "resistance" in result
