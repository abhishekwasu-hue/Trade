"""
tests/test_fetch_mcx_candles.py
--------------------------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा ("In chart add mcx symbols") — MCX Futures Trader पानावर नवीन
Chart टॅब जोडताना, upstox_api.fetch_mcx_candles() (fetch_candles() सारखंच chunked candle-fetching,
पण symbol->hardcoded index-key ऐवजी थेट resolve_mcx_futures_instruments.resolve_symbol() कडून
मिळालेला instrument_key वापरणारं, स्वतंत्र फंक्शन — established fetch_candles()/NIFTY कॉल-साईट्सना
अजिबात हात न लावता) साठी tests — tests/test_refresh_market_zones.py मधल्याच
TestFetchCandlesFailedChunks पॅटर्नचं अनुकरण.
"""
from unittest.mock import MagicMock, patch

import upstox_api


def _mock_response(status_code, candles=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"data": {"candles": candles or []}}
    return resp


class TestFetchMcxCandles:
    def setup_method(self):
        upstox_api.fetch_mcx_candles.clear()

    def test_uses_given_instrument_key_directly_not_symbol_lookup(self):
        """🎓 MCX commodities (CRUDEOIL इ.) SYMBOL_INSTRUMENT_KEYS मध्ये नाहीत — त्यामुळे इथे थेट
        दिलेला instrument_key (resolve_symbol() कडून) URL मध्ये वापरला जायला हवा, get_instrument_key()
        कडून नाही."""
        candle_row = ["2026-09-01T09:15:00+05:30", 100, 105, 95, 102, 1000, 0]
        seen_urls = []

        def side_effect(url, **kwargs):
            seen_urls.append(url)
            if "historical-candle/intraday" in url:
                return _mock_response(200, [])
            return _mock_response(200, [candle_row])

        with patch.object(upstox_api, "_get_with_retry", side_effect=side_effect):
            df = upstox_api.fetch_mcx_candles("fake_token", "MCX_FO|12345", interval="30minute", lookback_days=10)
            assert not df.empty
            assert all("MCX_FO%7C12345" in url for url in seen_urls)

    def test_marks_failed_chunks_when_a_historical_chunk_fails(self):
        candle_row = ["2026-09-01T09:15:00+05:30", 100, 105, 95, 102, 1000, 0]

        def side_effect(url, **kwargs):
            if "historical-candle/intraday" in url:
                return _mock_response(200, [])
            if "historical-candle/" in url:
                side_effect.hist_calls += 1
                if side_effect.hist_calls == 1:
                    return _mock_response(200, [candle_row])
                return _mock_response(500)
            raise AssertionError(f"अनपेक्षित URL: {url}")
        side_effect.hist_calls = 0

        with patch.object(upstox_api, "_get_with_retry", side_effect=side_effect):
            df = upstox_api.fetch_mcx_candles("fake_token", "MCX_FO|12345", interval="30minute", lookback_days=100)
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
            df = upstox_api.fetch_mcx_candles("fake_token", "MCX_FO|12345", interval="30minute", lookback_days=100)
            assert df.attrs.get("failed_chunks", 0) == 0
            assert not df.empty
            assert "rsi" in df.columns

    def test_empty_when_no_candles_at_all(self):
        with patch.object(upstox_api, "_get_with_retry", return_value=_mock_response(200, [])):
            df = upstox_api.fetch_mcx_candles("fake_token", "MCX_FO|12345", interval="30minute", lookback_days=10)
            assert df.empty

    def test_invalid_interval_falls_back_to_30minute(self):
        """🎓 fetch_candles() प्रमाणेच — allowed_intervals (1minute/5minute/15minute/30minute/day)
        यादीत नसलेला interval (उदा. "1hour", जो Upstox कडून थेट verified नाही) शांतपणे "30minute" कडे
        पडायला हवा, क्रॅश न होता."""
        candle_row = ["2026-09-01T09:15:00+05:30", 100, 105, 95, 102, 1000, 0]
        seen_urls = []

        def side_effect(url, **kwargs):
            seen_urls.append(url)
            if "historical-candle/intraday" in url:
                return _mock_response(200, [])
            return _mock_response(200, [candle_row])

        with patch.object(upstox_api, "_get_with_retry", side_effect=side_effect):
            df = upstox_api.fetch_mcx_candles("fake_token", "MCX_FO|12345", interval="1hour", lookback_days=10)
            assert not df.empty
            assert any("/minutes/30/" in url for url in seen_urls)
