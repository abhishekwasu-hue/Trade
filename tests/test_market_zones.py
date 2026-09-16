"""
tests/test_market_zones.py
--------------------------------------------------
🎓 वापरकर्त्याने Market Zones export मधून सापडवलेली bug -- compute_all_zones() (nightly full
refresh_market_zones.py कडून वापरलं जाणारं) DYNAMIC_SR_*_1M zones आधी स्वतःच generate करायचं,
त्यामुळे refresh_dynamic_sr_1m.py च्या दर-५-मिनिटांच्या merge-cron ने जपलेला इतिहास रोज रात्री
बदलून टाकला जायचा. आता 1M पूर्णपणे त्या dedicated cron कडेच सोपवलेलं आहे -- इथे generate होत नाही.
"""
import pandas as pd

import market_zones as mz


def _fake_ohlc(n, freq="1h", start_price=24000.0):
    dates = pd.date_range("2026-01-01 09:15", periods=n, freq=freq)
    closes = [start_price + (i % 20) * 5 - (i % 7) * 3 for i in range(n)]
    return pd.DataFrame({
        "timestamp": dates,
        "open": closes,
        "high": [c + 8 for c in closes],
        "low": [c - 8 for c in closes],
        "close": closes,
        "volume": [1000] * n,
        "oi": [0] * n,
    })


class TestComputeAllZonesNo1M:
    def test_signature_no_longer_accepts_df_1m_recent(self):
        df_1h = _fake_ohlc(30)
        df_15m = _fake_ohlc(30, freq="15min")
        try:
            mz.compute_all_zones(df_1h, df_15m, symbol="NIFTY", df_1m_recent=_fake_ohlc(150, freq="1min"))
            assert False, "df_1m_recent kwarg स्वीकारला गेला -- पूर्णपणे काढून टाकलेला असायला हवा होता"
        except TypeError:
            pass

    def test_never_generates_1m_zone_types(self):
        df_1h = _fake_ohlc(300)
        df_15m = _fake_ohlc(300, freq="15min")
        df_15m_recent = _fake_ohlc(150, freq="15min")
        zones_df = mz.compute_all_zones(df_1h, df_15m, symbol="NIFTY", df_15m_recent=df_15m_recent)
        assert not zones_df.empty
        assert not zones_df["zone_type"].str.endswith("_1M").any()

    def test_still_generates_15m_zones(self):
        """15M (SRv2 साठी) अजूनही इथेच generate व्हायला हवं -- फक्त 1M काढलं आहे, 15M नाही."""
        df_1h = _fake_ohlc(300)
        df_15m = _fake_ohlc(300, freq="15min")
        df_15m_recent = _fake_ohlc(150, freq="15min")
        zones_df = mz.compute_all_zones(df_1h, df_15m, symbol="NIFTY", df_15m_recent=df_15m_recent)
        zone_types = set(zones_df["zone_type"])
        assert "DYNAMIC_SR_SUPPORT_15M" in zone_types or "DYNAMIC_SR_RESISTANCE_15M" in zone_types
