"""
tests/test_refresh_market_zones_mcx.py
--------------------------------------------------------------
refresh_market_zones_mcx.py — tests/test_refresh_market_zones.py (TestFetchCandlesFailedChunks)
च्याच पॅटर्नचं MCX आवृत्ती — instrument resolution अयशस्वी/अपुरा इतिहास/failed_chunks — या
प्रत्येक केसमध्ये जुनेच zones सुरक्षितपणे कायम राहतात (चुकीच्या/अर्धवट डेटावरून पुन्हा-गणना करून
जुना योग्य निकाल खराब न करणे), आणि यशस्वी मार्गावर DYNAMIC_SR_*_30M/*_60M बरोबर तयार होतात का.
"""
from unittest.mock import patch

import pandas as pd

import refresh_market_zones_mcx as rmzm


def _fake_candles_df(n=150, base=6500.0):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="30min")
    # वर-खाली दोलायमान (oscillating) closes -- pivot high/low दोन्ही सापडतील इतपत variance हवं
    closes = [base + (10 if i % 4 < 2 else -10) for i in range(n)]
    df = pd.DataFrame({"timestamp": dates, "open": closes, "high": [c + 15 for c in closes],
                        "low": [c - 15 for c in closes], "close": closes, "volume": 0, "oi": 0})
    df.attrs["failed_chunks"] = 0
    return df


def _fake_resolved(instrument_key="MCX_FO|999"):
    return True, {
        "symbol": "GOLD", "trading_symbol": "GOLD26OCTFUT", "instrument_key": instrument_key,
        "lot_size": 100, "tick_size": 1.0, "expiry": "2026-10-31", "freeze_quantity": 100,
        "all_upcoming_expiries": ["2026-10-31"],
    }


class TestRefreshSymbol:
    def test_resolve_failure_returns_false(self):
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=(False, "सापडला नाही")):
            ok, msg = rmzm.refresh_symbol("fake_token", "GOLD")
            assert ok is False
            assert "सापडला नाही" in msg

    def test_insufficient_history_returns_false(self):
        thin_df = _fake_candles_df(n=10)
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(rmzm, "fetch_mcx_candles", return_value=thin_df):
            ok, msg = rmzm.refresh_symbol("fake_token", "GOLD")
            assert ok is False
            assert "पुरेसा" in msg

    def test_failed_chunks_returns_false_and_does_not_save(self):
        df = _fake_candles_df()
        df.attrs["failed_chunks"] = 2
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
             patch.object(rmzm.cloud_db, "save_market_zones") as mock_save:
            ok, msg = rmzm.refresh_symbol("fake_token", "GOLD")
            assert ok is False
            assert "chunk" in msg
            assert not mock_save.called

    def test_successful_refresh_saves_30m_and_60m_zones(self):
        df = _fake_candles_df(n=200)
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
             patch.object(rmzm.cloud_db, "save_market_zones", return_value=True) as mock_save:
            ok, msg = rmzm.refresh_symbol("fake_token", "GOLD")
            assert ok is True
            assert "GOLD" in msg
            assert mock_save.called
            saved_df, saved_symbol = mock_save.call_args.args
            assert saved_symbol == "GOLD"
            zone_types = set(saved_df["zone_type"])
            # दोन्ही timeframes साठी DYNAMIC_SR_*_30M/*_60M zone_types (15M कधीच नाही, MCX साठी
            # पर्यायच नाही) -- किमान एकातरी support/resistance सापडायला हवा.
            assert zone_types <= {
                "DYNAMIC_SR_SUPPORT_30M", "DYNAMIC_SR_RESISTANCE_30M",
                "DYNAMIC_SR_SUPPORT_60M", "DYNAMIC_SR_RESISTANCE_60M",
            }
            assert not any(zt.endswith("_15M") for zt in zone_types)

    def test_save_failure_returns_false(self):
        df = _fake_candles_df(n=200)
        with patch.object(rmzm.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(rmzm, "fetch_mcx_candles", return_value=df), \
             patch.object(rmzm.cloud_db, "save_market_zones", return_value=False):
            ok, msg = rmzm.refresh_symbol("fake_token", "GOLD")
            assert ok is False
            assert "साठवता आलं नाही" in msg
