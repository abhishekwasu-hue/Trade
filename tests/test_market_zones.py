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


# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Market Zones पानावरचा नवीन "5M/15M Confluence
# Table" (Support/Resistance + Demand/Supply + Order Block, सद्य किमतीच्या सापेक्ष).

def _row(ts, o, h, l, c):
    return {"timestamp": pd.Timestamp(ts), "open": o, "high": h, "low": l, "close": c}


def _quiet_then_impulsive_bars(start_ts="2024-01-02 09:15:00"):
    """२१ शांत bars + एक विरुद्ध (bearish, Order Block उमेदवार) candle + एक मोठी impulsive तेजीची
    candle + काही bars नंतर (mitigation-तपासणीसाठी) — detect_order_blocks() ला खरा BULLISH_OB
    (99.4-100.6 भोवती) सापडावा म्हणून, प्रत्यक्ष चालवून पडताळलेला डेटा."""
    ts0 = pd.Timestamp(start_ts)
    rows = []
    for i in range(21):
        v = 100.0 + (i % 3) * 0.2
        rows.append(_row(ts0 + pd.Timedelta(minutes=5 * i), v, v + 0.3, v - 0.3, v))
    rows.append(_row(ts0 + pd.Timedelta(minutes=5 * 21), 100.5, 100.6, 99.4, 99.5))
    rows.append(_row(ts0 + pd.Timedelta(minutes=5 * 22), 99.5, 115.5, 99.3, 115.0))
    for j, v in enumerate([116, 117]):
        rows.append(_row(ts0 + pd.Timedelta(minutes=5 * (23 + j)), v, v + 0.3, v - 0.3, v))
    return pd.DataFrame(rows).reset_index(drop=True)


class TestCompute5m15mConfluenceRow:
    def test_support_resistance_from_stored_dynamic_sr_zones(self):
        dyn_sr = pd.DataFrame([
            {"zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 23000.0, "zone_high": 23000.0, "status": "ACTIVE"},
            {"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 23100.0, "zone_high": 23100.0, "status": "ACTIVE"},
            {"zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 22900.0, "zone_high": 22900.0, "status": "FILLED"},  # FILLED -> दुर्लक्षित
        ])
        row = mz.compute_5m_15m_confluence_row("5M", None, dyn_sr, current_price=23050.0)
        assert row["support_level"] == 23000.0
        assert row["resistance_level"] == 23100.0
        assert row["support_distance_pct"] < 0  # support नेहमी सद्य किमतीच्या खाली -> ऋण अंतर
        assert row["resistance_distance_pct"] > 0

    def test_order_block_and_demand_supply_computed_live(self):
        df = _quiet_then_impulsive_bars()
        row = mz.compute_5m_15m_confluence_row("5M", df, None, current_price=116.0)
        assert row["order_block_type"] == "BULLISH_OB"
        assert row["order_block_low"] == 99.4
        assert row["order_block_high"] == 100.6
        assert row["order_block_distance_pct"] < 0  # OB सद्य किमतीच्या खाली आहे
        # Demand/Supply zones (swing-आधारित) — काहीतरी सापडलं पाहिजे, नेमकं मूल्य data-specific
        assert row["demand_zone_low"] is not None
        assert row["supply_zone_low"] is not None

    def test_insufficient_data_returns_none_fields(self):
        df = _quiet_then_impulsive_bars().head(3)  # order/avg_window साठी खूपच कमी
        row = mz.compute_5m_15m_confluence_row("5M", df, None, current_price=100.0)
        assert row["demand_zone_low"] is None
        assert row["order_block_type"] is None
        assert row["support_level"] is None  # dynamic_sr_zones_df=None दिलेला


class TestCompute5m15mConfluenceTable:
    def test_returns_one_row_per_timeframe_in_order(self):
        df_5m = _quiet_then_impulsive_bars()
        df_15m = _quiet_then_impulsive_bars(start_ts="2024-01-02 09:15:00")
        table = mz.compute_5m_15m_confluence_table(116.0, {"5M": df_5m, "15M": df_15m}, None)
        assert list(table["timeframe"]) == ["5M", "15M"]
        assert len(table) == 2
