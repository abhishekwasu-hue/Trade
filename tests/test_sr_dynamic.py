"""
tests/test_sr_dynamic.py
----------------------------
sr_dynamic.py — TradingView Pine Script "Support Resistance - Dynamic v2" चं Python रूपांतर.
"""
import numpy as np
import pandas as pd

from sr_dynamic import find_pivots, compute_dynamic_sr


def test_find_pivots_detects_manual_peak():
    np.random.seed(5)
    n = 60
    prices = 24000 + np.cumsum(np.random.randn(n) * 5)
    prices[30] = prices[25:36].max() + 50  # मुद्दाम बनवलेलं स्पष्ट शिखर
    df = pd.DataFrame({"high": prices + 5, "low": prices - 5})
    pivots = find_pivots(df, prd=5)
    assert prices[30] + 5 in pivots


def test_nearby_pivots_cluster_into_one_zone():
    """३ जवळपासचे pivots एकाच high-strength zone मध्ये एकत्र यायला हवेत."""
    np.random.seed(3)
    n = 100
    base = 24000 + np.cumsum(np.random.randn(n) * 0.3)
    df = pd.DataFrame({
        "open": base, "close": base,
        "high": base + 3 + abs(np.random.randn(n) * 0.5),
        "low": base - 3 - abs(np.random.randn(n) * 0.5),
    })
    for idx, val in [(20, 24100), (50, 24102), (80, 24098)]:
        df.loc[idx, "high"] = val

    result = compute_dynamic_sr(df, prd=10, min_strength=2, current_price=24000)
    matching = [z for z in result["resistance"] if 24095 <= z["level"] <= 24105]
    assert len(matching) >= 1
    assert matching[0]["touches"] >= 3


def test_support_resistance_split_by_current_price():
    np.random.seed(9)
    n = 150
    walk = 24000 + np.cumsum(np.random.randn(n) * 8)
    df = pd.DataFrame({
        "open": walk, "close": walk + 1,
        "high": walk + abs(np.random.randn(n) * 4) + 2,
        "low": walk - abs(np.random.randn(n) * 4) - 2,
    })
    current_price = float(df["close"].iloc[-1])
    result = compute_dynamic_sr(df, current_price=current_price)
    for s in result["support"]:
        assert s["level"] < current_price
    for r in result["resistance"]:
        assert r["level"] >= current_price


def test_insufficient_data_returns_empty():
    df = pd.DataFrame({"high": [100, 101, 102], "low": [98, 99, 100]})
    result = compute_dynamic_sr(df)
    assert result == {"support": [], "resistance": []}
