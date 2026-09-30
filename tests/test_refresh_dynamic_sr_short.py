"""
tests/test_refresh_dynamic_sr_short.py
--------------------------------------
refresh_dynamic_sr_5m.py / refresh_dynamic_sr_1m.py — "levels वारंवार DB मध्ये अद्ययावत" audit:
अर्धवट (failed_chunks > 0) डेटावरून गणना केलेले levels जुन्या चांगल्या ACTIVE levels ला STALE करू नयेत.
"""
from unittest.mock import patch

import pandas as pd

import refresh_dynamic_sr_1m as r1
import refresh_dynamic_sr_5m as r5


def _df(n=300, failed=0):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="5min")
    closes = [24000.0 + (20 if i % 10 < 5 else -20) for i in range(n)]
    df = pd.DataFrame({"timestamp": dates, "open": closes, "high": [c + 5 for c in closes],
                       "low": [c - 5 for c in closes], "close": closes, "volume": 0, "oi": 0})
    df.attrs["failed_chunks"] = failed
    return df


class TestFailedChunksGuard:
    def test_5m_failed_chunks_skips_merge(self):
        with patch.object(r5, "fetch_candles", return_value=_df(failed=2)), \
             patch.object(r5.cloud_db, "merge_dynamic_sr_zones") as mock_merge:
            ok, msg = r5.refresh_symbol_5m("tok", "NIFTY")
            assert ok is False and "chunk" in msg
            assert not mock_merge.called

    def test_1m_failed_chunks_skips_merge(self):
        with patch.object(r1, "fetch_candles", return_value=_df(failed=1)), \
             patch.object(r1.cloud_db, "merge_dynamic_sr_1m_zones") as mock_merge:
            ok, msg = r1.refresh_symbol_1m("tok", "NIFTY")
            assert ok is False and "chunk" in msg
            assert not mock_merge.called

    def test_5m_clean_fetch_merges(self):
        with patch.object(r5, "fetch_candles", return_value=_df(failed=0)), \
             patch.object(r5.cloud_db, "merge_dynamic_sr_zones", return_value=True) as mock_merge:
            ok, _ = r5.refresh_symbol_5m("tok", "NIFTY")
            assert ok is True
            assert mock_merge.call_args.args[2] == "5M"

    def test_1m_clean_fetch_merges(self):
        with patch.object(r1, "fetch_candles", return_value=_df(failed=0)), \
             patch.object(r1.cloud_db, "merge_dynamic_sr_1m_zones", return_value=True) as mock_merge:
            ok, _ = r1.refresh_symbol_1m("tok", "NIFTY")
            assert ok is True
            assert mock_merge.called
