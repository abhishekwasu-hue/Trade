"""
tests/test_real_data_integration.py
----------------------------------------
खऱ्या साठवलेल्या NIFTY डेटावर (data/nifty50_1min.parquet) चालणारे integration tests — Backtest
Engine मध्ये कधी crash होत नाही, आणि known bugs (उदा. VWAP daily-reset, ict_fvg performance)
परत येत नाहीत याची खात्री. डेटा उपलब्ध नसल्यास आपोआप skip होतात (उदा. वेगळ्या मशीनवर चालवताना).
"""
import time

import pytest


pytestmark = pytest.mark.skipif(
    __import__("os").path.exists(
        __import__("os").path.join(
            __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))),
            "data", "nifty50_1min.parquet",
        )
    ) is False,
    reason="खरा साठवलेला NIFTY डेटा (data/nifty50_1min.parquet) उपलब्ध नाही",
)


def test_price_action_backtest_runs_without_crash():
    from real_nifty_data import load_nifty_resampled
    from backtest import run_signal_backtest_v2

    df_15m = load_nifty_resampled(15, "2024-01-01", "2024-03-27")
    df_1h = load_nifty_resampled(60, "2024-01-01", "2024-03-27")
    result = run_signal_backtest_v2(df_15m, df_1h, strategy="price_action", max_hold_bars=50)
    assert "total" in result
    assert result["total"] >= 0


def test_ict_fvg_backtest_completes_within_reasonable_time():
    """कामगिरी regression टाळण्यासाठी -- हा backtest आधी O(n²) मुळे 257 सेकंद लागायचा, आता <30 असायला हवा."""
    from real_nifty_data import load_nifty_resampled
    from market_data_adapter import prepare_futures_ohlcv
    from multi_strategy_backtest import run_strategy_backtest
    from strategies.ict_fvg import ICTFVGStrategy

    df_15m = load_nifty_resampled(15, "2024-01-01", "2024-03-27")
    df_prepared = prepare_futures_ohlcv(df_15m)
    strat = ICTFVGStrategy(config={"fvg_entry_buffer_pct": 1.0})

    start = time.time()
    result = run_strategy_backtest(df_prepared, strat, min_lookback=30, max_hold_bars=50)
    elapsed = time.time() - start

    assert elapsed < 30, f"ict_fvg backtest खूप संथ झाला ({elapsed:.1f}s) -- performance regression!"
    assert "total" in result


def test_daily_data_combines_seamlessly_across_1min_and_extension():
    """1-मिनिट + दैनिक extension दोन्ही स्रोत gap/duplicate शिवाय जोडले जातात याची खात्री."""
    from real_nifty_data import load_nifty_resampled

    df = load_nifty_resampled("day", "2024-01-01", "2024-06-30")
    assert df["timestamp"].duplicated().sum() == 0
    assert df["timestamp"].is_monotonic_increasing


def test_vwap_strategy_resets_daily():
    """
    VWAP दिवसागणिक reset होतो (जुना bug: संपूर्ण इतिहासावर cumsum होत होता). आपल्या खऱ्या साठवलेल्या
    1-मिनिट डेटाला Volume नाहीच (नेहमी 0, आधीच दस्तऐवजीकरण केलेली मर्यादा) — त्यामुळे VWAP गणित तिथे
    नेहमीच सुरक्षित 0/1 divide होतं (योग्य वि चुकीच्या daily-reset मध्ये फरकच दाखवत नाही). म्हणून इथे
    खऱ्या (शून्य नसलेल्या) Volume सह synthetic डेटा वापरून योग्य तपासणी.
    """
    import numpy as np
    import pandas as pd
    from market_data_adapter import prepare_futures_ohlcv

    rows = []
    for day_offset in range(3):
        day_start = pd.Timestamp("2026-03-01") + pd.Timedelta(days=day_offset)
        base_price = 24000 + day_offset * 500  # प्रत्येक दिवशी वेगळी सुरुवातीची किंमत
        for k in range(25):
            ts = day_start.replace(hour=9, minute=15) + pd.Timedelta(minutes=15 * k)
            price = base_price + k * 2
            rows.append({"timestamp": ts, "open": price, "high": price + 5, "low": price - 5,
                         "close": price, "volume": 1000 + k * 10})
    df = pd.DataFrame(rows)
    prepared = prepare_futures_ohlcv(df)

    prepared["date_only"] = prepared["timestamp"].dt.date
    first_bars = prepared.groupby("date_only").first()
    # Day 1 चे सुरुवातीचे काही bars BB/ATR warmup (min_periods=20) मुळे वगळले जातात -- तो दिवस
    # चाचणीसाठी अयोग्य (VWAP reset शी संबंधित नाही). पूर्ण उपलब्ध असलेले नंतरचे दिवसच तपासणे.
    later_days = first_bars.iloc[1:]
    assert len(later_days) >= 1
    assert (abs(later_days["vwap"] - later_days["close"]) < 0.01).all()
