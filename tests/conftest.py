"""
tests/conftest.py
---------------------
सर्व test files साठी सामायिक fixtures — synthetic OHLC डेटा जनरेटर्स आणि खऱ्या साठवलेल्या NIFTY
डेटाचा प्रवेश. pytest आपोआप हे file शोधतो, वेगळा import करावा लागत नाही.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def trending_up_df():
    """६० bars चा स्पष्ट, सतत वाढणारा (bullish) OHLC डेटा — Supertrend/RSI/S/R साठी नियंत्रित चाचणी."""
    np.random.seed(42)
    n = 60
    walk = 24000 + np.cumsum(abs(np.random.randn(n)) * 15)  # नेहमी वाढणारा
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 09:15", periods=n, freq="15min"),
        "open": walk, "close": walk + 2,
        "high": walk + abs(np.random.randn(n) * 5) + 3,
        "low": walk - abs(np.random.randn(n) * 5) - 3,
        "volume": np.random.randint(1000, 5000, n),
    })


@pytest.fixture
def trending_down_df():
    """६० bars चा स्पष्ट, सतत घटणारा (bearish) OHLC डेटा."""
    np.random.seed(43)
    n = 60
    walk = 24000 - np.cumsum(abs(np.random.randn(n)) * 15)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 09:15", periods=n, freq="15min"),
        "open": walk, "close": walk - 2,
        "high": walk + abs(np.random.randn(n) * 5) + 3,
        "low": walk - abs(np.random.randn(n) * 5) - 3,
        "volume": np.random.randint(1000, 5000, n),
    })


@pytest.fixture
def sideways_df():
    """६० bars चा अरुंद, दिशाहीन (sideways/choppy) OHLC डेटा."""
    np.random.seed(44)
    n = 60
    walk = 24000 + np.random.randn(n) * 5  # दिशाहीन, फक्त छोटे चढ-उतार
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 09:15", periods=n, freq="15min"),
        "open": walk, "close": walk + np.random.randn(n),
        "high": walk + abs(np.random.randn(n) * 3) + 2,
        "low": walk - abs(np.random.randn(n) * 3) - 2,
        "volume": np.random.randint(1000, 5000, n),
    })


@pytest.fixture
def real_nifty_data_available():
    """आपला खरा साठवलेला NIFTY डेटा (data/nifty50_1min.parquet) उपलब्ध आहे का ते तपासणे."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "nifty50_1min.parquet")
    return os.path.exists(path)


@pytest.fixture
def sample_option_chain():
    """टेस्टसाठी साधा, नियंत्रित Option Chain (ATM=24500, 50-पॉइंट strikes)."""
    chain = []
    for k in range(23600, 25600, 50):
        chain.append({
            "strike_price": k, "underlying_spot_price": 24500.0,
            "call_options": {
                "instrument_key": f"CE{k}",
                "market_data": {"ltp": max(200 - (k - 24500) * 0.5, 5), "oi": 10000 + abs(k - 24500) * 10},
                "option_greeks": {"pop": 0.6},
            },
            "put_options": {
                "instrument_key": f"PE{k}",
                "market_data": {"ltp": max(200 - (24500 - k) * 0.5, 5), "oi": 12000 + abs(k - 24500) * 10},
                "option_greeks": {"pop": 0.6},
            },
        })
    return chain
