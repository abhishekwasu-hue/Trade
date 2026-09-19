"""
tests/test_refresh_market_zones.py
--------------------------------------------------
🎓 वापरकर्त्याने Market Zones export मधून सापडवलेली bug -- fetch_candles() मधला एखादा historical
chunk अयशस्वी झाला तरी शांतपणे (Streamlit-only st.warning(), जे headless cron मध्ये no-op होतं)
फक्त तेवढाच भाग गाळून पुढे जायचं, त्यामुळे df_30m/df_15m मध्ये अंतर (gap) राहून mitigation-तपासणी
चुकीची व्हायची. आता fetch_candles() अशा अपयशाची नोंद df.attrs["failed_chunks"] मध्ये करतं, आणि
refresh_market_zones.py तो आढळल्यास त्या symbol साठी साठवणंच वगळतं.
"""
from unittest.mock import MagicMock, patch

import pandas as pd

import refresh_market_zones as rmz
import upstox_api


def _mock_response(status_code, candles=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"data": {"candles": candles or []}}
    return resp


class TestFetchCandlesFailedChunks:
    def setup_method(self):
        # 🎓 fetch_candles() @st.cache_data(ttl=60) आहे (Dashboard speed साठी) -- समान arguments
        # असलेल्या मागच्या टेस्टचा cached निकाल (attrs सकट) पुढच्या टेस्टला मिळू नये म्हणून
        # प्रत्येक टेस्टआधी cache रिकामी करणे.
        upstox_api.fetch_candles.clear()

    def test_marks_failed_chunks_when_a_historical_chunk_fails(self):
        """दुसरा (जुना) chunk अयशस्वी झाला, पहिला (अलीकडचा) यशस्वी -- तरीही मिळालेला डेटा परत यायला
        हवा, आणि failed_chunks attrs मध्ये स्पष्टपणे नोंदवलेला असायला हवा."""
        candle_row = ["2026-09-01T09:15:00+05:30", 100, 105, 95, 102, 1000, 0]

        def side_effect(url, **kwargs):
            if "historical-candle/intraday" in url:
                return _mock_response(200, [])
            if "historical-candle/" in url:
                # पहिला hist कॉल यशस्वी, बाकीचे सर्व अयशस्वी (500)
                side_effect.hist_calls += 1
                if side_effect.hist_calls == 1:
                    return _mock_response(200, [candle_row])
                return _mock_response(500)
            raise AssertionError(f"अनपेक्षित URL: {url}")
        side_effect.hist_calls = 0

        with patch.object(upstox_api, "_get_with_retry", side_effect=side_effect):
            df = upstox_api.fetch_candles("fake_token", "NIFTY", 0, interval="30minute", lookback_days=100)
            assert df.attrs.get("failed_chunks", 0) >= 1
            assert not df.empty

    def test_no_failed_chunks_when_everything_succeeds(self):
        candle_row = ["2026-09-01T09:15:00+05:30", 100, 105, 95, 102, 1000, 0]

        def side_effect(url, **kwargs):
            if "historical-candle/intraday" in url:
                return _mock_response(200, [])
            if "historical-candle/" in url:
                return _mock_response(200, [candle_row])
            raise AssertionError(f"अनपेक्षित URL: {url}")

        with patch.object(upstox_api, "_get_with_retry", side_effect=side_effect):
            df = upstox_api.fetch_candles("fake_token", "NIFTY", 0, interval="30minute", lookback_days=100)
            assert df.attrs.get("failed_chunks", 0) == 0
            assert not df.empty


def _fake_df(n=30, failed_chunks=0):
    dates = pd.date_range("2026-01-01 09:15", periods=n, freq="1h")
    df = pd.DataFrame({
        "timestamp": dates, "open": [100.0] * n, "high": [105.0] * n,
        "low": [95.0] * n, "close": [102.0] * n, "volume": [0] * n, "oi": [0] * n,
    })
    df.attrs["failed_chunks"] = failed_chunks
    return df


class TestRefreshSymbolSkipsOnGap:
    def test_skips_save_when_30m_data_has_failed_chunks(self):
        with patch.object(rmz, "fetch_candles", return_value=_fake_df(failed_chunks=2)) as mock_fetch, \
             patch.object(rmz, "notify_error", return_value=True) as mock_notify, \
             patch.object(rmz.cloud_db, "save_market_zones") as mock_save:
            ok, message = rmz.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "chunk" in message
            assert mock_notify.called
            assert not mock_save.called
            # 15-मिनिट fetch पर्यंत कधीच पोहोचायला नको -- 30-मिनिटच्याच gap वर लगेच थांबायला हवं
            assert mock_fetch.call_count == 1

    def test_skips_save_when_15m_data_has_failed_chunks(self):
        def fetch_side_effect(access_token, symbol, current_spot, interval, lookback_days=None):
            if interval == "30minute":
                return _fake_df(failed_chunks=0)
            if interval == "15minute" and lookback_days is not None:
                return _fake_df(failed_chunks=3)
            return _fake_df(failed_chunks=0)

        with patch.object(rmz, "fetch_candles", side_effect=fetch_side_effect), \
             patch.object(rmz, "notify_error", return_value=True) as mock_notify, \
             patch.object(rmz.cloud_db, "save_market_zones") as mock_save:
            ok, message = rmz.refresh_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "chunk" in message
            assert mock_notify.called
            assert not mock_save.called

    def test_proceeds_normally_when_no_gap(self):
        with patch.object(rmz, "fetch_candles", return_value=_fake_df(failed_chunks=0)), \
             patch.object(rmz, "notify_error", return_value=True) as mock_notify, \
             patch.object(rmz, "compute_all_zones", return_value=pd.DataFrame([
                 {"symbol": "NIFTY", "zone_type": "SUPPORT", "zone_low": 100.0, "zone_high": 100.0,
                  "strength": 3, "formed_date": "2026-01-01", "status": "ACTIVE"},
             ])), \
             patch.object(rmz.cloud_db, "save_market_zones", return_value=True) as mock_save:
            ok, message = rmz.refresh_symbol("fake_token", "NIFTY")
            assert ok is True
            assert mock_save.called
            assert not mock_notify.called

    def test_passes_30m_recent_and_resampled_60m_recent_to_compute_all_zones(self):
        """🎓 वापरकर्त्याने सापडवलेली bug (SRv2 चं 30M/60M कधीच काम करायचं नाही) — df_30m_recent
        थेट मागवला जायला हवा, आणि df_60m_recent त्याच्याच resample वरून (interval="60minute"/"1hour"
        थेट कधीच मागवला जाऊ नये -- fetch_candles() मध्ये तो verified/allowed नाही)."""
        df_30m_recent = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01 09:15", periods=200, freq="30min"),
            "open": [100.0] * 200, "high": [105.0] * 200, "low": [95.0] * 200,
            "close": [102.0] * 200, "volume": [0] * 200, "oi": [0] * 200,
        })

        def fetch_side_effect(access_token, symbol, current_spot, interval, lookback_days=None):
            if interval == "30minute" and lookback_days is None:
                return df_30m_recent
            return _fake_df(failed_chunks=0)

        with patch.object(rmz, "fetch_candles", side_effect=fetch_side_effect) as mock_fetch, \
             patch.object(rmz, "compute_all_zones", return_value=pd.DataFrame([
                 {"symbol": "NIFTY", "zone_type": "SUPPORT", "zone_low": 100.0, "zone_high": 100.0,
                  "strength": 3, "formed_date": "2026-01-01", "status": "ACTIVE"},
             ])) as mock_compute, \
             patch.object(rmz.cloud_db, "save_market_zones", return_value=True):
            ok, message = rmz.refresh_symbol("fake_token", "NIFTY")
            assert ok is True
            assert all(call.kwargs.get("interval") != "60minute" and call.kwargs.get("interval") != "1hour"
                       for call in mock_fetch.call_args_list)
            _, compute_kwargs = mock_compute.call_args
            assert compute_kwargs["df_30m_recent"] is df_30m_recent
            assert compute_kwargs["df_60m_recent"] is not None
            assert len(compute_kwargs["df_60m_recent"]) < len(df_30m_recent)
