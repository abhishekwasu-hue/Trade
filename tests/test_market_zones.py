"""
tests/test_market_zones.py
--------------------------------------------------
🎓 वापरकर्त्याने Market Zones export मधून सापडवलेली bug -- compute_all_zones() (nightly full
refresh_market_zones.py कडून वापरलं जाणारं) DYNAMIC_SR_*_5M zones कधीच generate करायचं नाही
(5-मिनिट गणना तिथे अस्तित्वातच नव्हती), त्यामुळे रोज रात्री सर्व 5-मिनिट Dynamic S/R levels
कायमचे रिकामे व्हायचे.

🎓 वापरकर्त्याशी चर्चा करून पुढे स्पष्ट केलेला नियम — त्यावर पहिला प्रयत्न (DYNAMIC_SR_*_1M/*_5M
ला nightly DELETE मधून पूर्णपणे वगळणे) चुकीचा ठरला: त्यामुळे जुने, अनेक दिवस/आठवडे जुने झालेले
1-मिनिट/5-मिनिट levels कधीच refresh न होता कायमचे ACTIVE राहून, प्रत्यक्ष trade घेऊ शकत होते.
वापरकर्त्याचा स्पष्ट नियम: "दुसऱ्या दिवशी नवीन लेव्हल्स कॅल्क्युलेट झाल्यानंतर आदल्या सर्व झोन
अपडेट व्हायला पाहिजे." आता दोन्ही (1M आणि 5M) रोज रात्री इथेच ताज्या डेटावरून पुन्हा-गणना होतात
(DYNAMIC_SR_*_15M प्रमाणेच), आणि cloud_db.save_market_zones() चं DELETE आता कुठलाही zone_type
वगळत नाही (साधा, पूर्ण replace-on-refresh).
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


class TestComputeAllZonesDailyRefresh:
    def test_generates_1m_and_5m_zones_when_recent_data_given(self):
        df_1h = _fake_ohlc(300)
        df_15m = _fake_ohlc(300, freq="15min")
        df_15m_recent = _fake_ohlc(150, freq="15min")
        df_1m_recent = _fake_ohlc(150, freq="1min")
        df_5m_recent = _fake_ohlc(150, freq="5min")
        zones_df = mz.compute_all_zones(
            df_1h, df_15m, symbol="NIFTY", df_15m_recent=df_15m_recent,
            df_1m_recent=df_1m_recent, df_5m_recent=df_5m_recent,
        )
        zone_types = set(zones_df["zone_type"])
        assert "DYNAMIC_SR_SUPPORT_1M" in zone_types or "DYNAMIC_SR_RESISTANCE_1M" in zone_types
        assert "DYNAMIC_SR_SUPPORT_5M" in zone_types or "DYNAMIC_SR_RESISTANCE_5M" in zone_types
        assert "DYNAMIC_SR_SUPPORT_15M" in zone_types or "DYNAMIC_SR_RESISTANCE_15M" in zone_types

    def test_no_1m_or_5m_zones_when_recent_data_not_given(self):
        """df_1m_recent/df_5m_recent न दिल्यास (backward-compatible) ते zone_types generate होऊ नयेत."""
        df_1h = _fake_ohlc(300)
        df_15m = _fake_ohlc(300, freq="15min")
        df_15m_recent = _fake_ohlc(150, freq="15min")
        zones_df = mz.compute_all_zones(df_1h, df_15m, symbol="NIFTY", df_15m_recent=df_15m_recent)
        zone_types = set(zones_df["zone_type"])
        assert "DYNAMIC_SR_SUPPORT_1M" not in zone_types and "DYNAMIC_SR_RESISTANCE_1M" not in zone_types
        assert "DYNAMIC_SR_SUPPORT_5M" not in zone_types and "DYNAMIC_SR_RESISTANCE_5M" not in zone_types

    def test_insufficient_1m_or_5m_history_skips_gracefully(self):
        """1म/5म recent data दिलेला असला, पण खूपच कमी (<100 candles) असला, तर तो zone_type गाळला
        जावा, पण उर्वरित गणना (15M/SUPPORT/RESISTANCE) थांबू नये."""
        df_1h = _fake_ohlc(300)
        df_15m = _fake_ohlc(300, freq="15min")
        df_15m_recent = _fake_ohlc(150, freq="15min")
        zones_df = mz.compute_all_zones(
            df_1h, df_15m, symbol="NIFTY", df_15m_recent=df_15m_recent,
            df_1m_recent=_fake_ohlc(10, freq="1min"), df_5m_recent=_fake_ohlc(10, freq="5min"),
        )
        zone_types = set(zones_df["zone_type"])
        assert "DYNAMIC_SR_SUPPORT_1M" not in zone_types and "DYNAMIC_SR_SUPPORT_5M" not in zone_types
        assert "DYNAMIC_SR_SUPPORT_15M" in zone_types or "DYNAMIC_SR_RESISTANCE_15M" in zone_types
