"""
tests/test_refresh_market_zones_intraday.py
--------------------------------------------------------------
refresh_market_zones_intraday.py — MCX intraday-refresh script च्याच पॅटर्नची NIFTY/BANKNIFTY/SENSEX
आवृत्ती, पण एक अतिरिक्त, इथला सगळ्यात महत्त्वाचा तपासणी-मुद्दा: हे script `cloud_db.save_market_zones()`
ला नेहमी `scoped=True` देऊनच बोलावतं का — कारण तेच NIFTY साठी बाजार चालू असताना, प्रत्यक्ष live trade
घेणाऱ्या dynamic_sr_instant_trader.py चे 1M/5M zones सुरक्षित (अबाधित) ठेवतं.
"""
from unittest.mock import patch

import pandas as pd

import refresh_market_zones_intraday as rmzi


def _fake_candles_df(n=150, base=24000.0):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="15min")
    closes = [base + (10 if i % 4 < 2 else -10) for i in range(n)]
    df = pd.DataFrame({"timestamp": dates, "open": closes, "high": [c + 15 for c in closes],
                        "low": [c - 15 for c in closes], "close": closes, "volume": 0, "oi": 0})
    df.attrs["failed_chunks"] = 0
    return df


class TestRefreshSymbol:
    def test_15m_failed_chunks_returns_false_and_does_not_save(self):
        bad_15m = _fake_candles_df()
        bad_15m.attrs["failed_chunks"] = 3
        with patch.object(rmzi, "fetch_candles", return_value=bad_15m), \
             patch.object(rmzi.cloud_db, "save_market_zones") as mock_save:
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "chunk" in msg
            assert not mock_save.called

    def test_30m_failed_chunks_returns_false_and_does_not_save(self):
        good_15m = _fake_candles_df()
        bad_30m = _fake_candles_df()
        bad_30m.attrs["failed_chunks"] = 1
        calls = {"n": 0}

        def _fake_fetch(*args, **kwargs):
            calls["n"] += 1
            return good_15m if kwargs.get("interval") == "15minute" else bad_30m

        with patch.object(rmzi, "fetch_candles", side_effect=_fake_fetch), \
             patch.object(rmzi.cloud_db, "save_market_zones") as mock_save:
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "chunk" in msg
            assert not mock_save.called

    def test_insufficient_history_returns_false(self):
        thin_df = _fake_candles_df(n=10)
        with patch.object(rmzi, "fetch_candles", return_value=thin_df), \
             patch.object(rmzi.cloud_db, "save_market_zones") as mock_save:
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "पुरेसा" in msg
            assert not mock_save.called

    def test_successful_refresh_merges_each_timeframe_and_never_replaces(self):
        df = _fake_candles_df(n=500)  # 60M (1h resample) साठीही >=100 bars हवेत

        with patch.object(rmzi, "fetch_candles", return_value=df), \
             patch.object(rmzi.cloud_db, "merge_dynamic_sr_zones", return_value=True) as mock_merge, \
             patch.object(rmzi.cloud_db, "save_market_zones") as mock_save:
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is True
            assert "NIFTY" in msg
            # हाच मुख्य तपासणी-मुद्दा -- delete+insert (level_price churn -> hit-counter/cooldown reset) नाही, फक्त merge.
            assert not mock_save.called
            suffixes = [c.args[2] for c in mock_merge.call_args_list]
            assert suffixes == ["15M", "30M", "60M"]
            assert all(c.args[0] == "NIFTY" for c in mock_merge.call_args_list)

    def test_merge_failure_returns_false(self):
        df = _fake_candles_df(n=500)
        with patch.object(rmzi, "fetch_candles", return_value=df), \
             patch.object(rmzi.cloud_db, "merge_dynamic_sr_zones", return_value=False):
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "merge अयशस्वी" in msg

    def test_default_symbols_are_nse_only(self):
        assert rmzi.INTRADAY_SR_SYMBOLS == ["NIFTY", "BANKNIFTY", "SENSEX"]
