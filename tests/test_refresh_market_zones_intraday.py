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

    def test_successful_refresh_calls_save_with_scoped_true(self):
        df = _fake_candles_df(n=200)

        def _fake_fetch(*args, **kwargs):
            return df

        with patch.object(rmzi, "fetch_candles", side_effect=_fake_fetch), \
             patch.object(rmzi.cloud_db, "save_market_zones", return_value=True) as mock_save:
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is True
            assert "NIFTY" in msg
            assert mock_save.called
            call = mock_save.call_args
            saved_df, saved_symbol = call.args
            assert saved_symbol == "NIFTY"
            # हाच सगळ्यात महत्त्वाचा तपासणी-मुद्दा -- scoped=True नसेल तर 1M/5M live zones धोक्यात येतात.
            assert call.kwargs.get("scoped") is True
            zone_types = set(saved_df["zone_type"])
            assert zone_types <= {
                "DYNAMIC_SR_SUPPORT_15M", "DYNAMIC_SR_RESISTANCE_15M",
                "DYNAMIC_SR_SUPPORT_30M", "DYNAMIC_SR_RESISTANCE_30M",
                "DYNAMIC_SR_SUPPORT_60M", "DYNAMIC_SR_RESISTANCE_60M",
            }
            assert not any(zt.endswith("_1M") or zt.endswith("_5M") for zt in zone_types)

    def test_save_failure_returns_false(self):
        df = _fake_candles_df(n=200)
        with patch.object(rmzi, "fetch_candles", return_value=df), \
             patch.object(rmzi.cloud_db, "save_market_zones", return_value=False):
            ok, msg = rmzi.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "साठवता आलं नाही" in msg

    def test_default_symbols_are_nse_only(self):
        assert rmzi.INTRADAY_SR_SYMBOLS == ["NIFTY", "BANKNIFTY", "SENSEX"]
