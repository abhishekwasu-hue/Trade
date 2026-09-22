"""
tests/test_tradingview_chart.py
--------------------------------------------
Volume Profile (किंमतीनुसार horizontal volume histogram, on/off बटणाने toggle) — user request:
"Add volume profile indicator on both charts and give on off button". दोन्ही charts (Dashboard तसंच
MCX Futures) एकाच build_lightweight_chart_html() वर अवलंबून असल्याने, त्याच फंक्शनला दिलेला df वापरून
compute_volume_profile() मध्येच गणना होते — callers ना वेगळा parameter द्यावा लागत नाही.
"""
import pandas as pd
import pytest

from tradingview_chart import build_lightweight_chart_html, compute_volume_profile


def _make_df(rows):
    """rows: [(timestamp, open, high, low, close, volume), ...]"""
    return pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )


class TestComputeVolumeProfile:
    def test_empty_df_returns_empty_list(self):
        assert compute_volume_profile(pd.DataFrame()) == []

    def test_none_df_returns_empty_list(self):
        assert compute_volume_profile(None) == []

    def test_missing_volume_column_returns_empty_list(self):
        df = pd.DataFrame({"timestamp": [1], "open": [1], "high": [1], "low": [1], "close": [1]})
        assert compute_volume_profile(df) == []

    def test_flat_price_range_returns_empty_list(self):
        # high == low प्रत्येक candle साठी, म्हणजे price_max == price_min -> bin करता येत नाही
        df = _make_df([(1, 100, 100, 100, 100, 500)])
        assert compute_volume_profile(df) == []

    def test_total_volume_is_conserved_across_bins(self):
        df = _make_df([
            (1, 100, 105, 98, 102, 1000),
            (2, 102, 110, 101, 108, 2000),
            (3, 108, 112, 104, 106, 1500),
        ])
        profile = compute_volume_profile(df, num_bins=10)
        assert profile  # काहीतरी bins आले पाहिजेत
        total = sum(b["volume"] for b in profile)
        # प्रत्येक bin स्वतंत्रपणे 2 दशांशांपर्यंत round केल्याने किरकोळ (<0.1) फरक अपेक्षित
        assert total == pytest.approx(4500, abs=0.1)

    def test_exactly_one_bin_marked_as_poc(self):
        df = _make_df([
            (1, 100, 105, 98, 102, 1000),
            (2, 102, 110, 101, 108, 5000),  # सर्वात मोठा volume -> POC इथेच असणार
            (3, 108, 112, 104, 106, 1500),
        ])
        profile = compute_volume_profile(df, num_bins=10)
        poc_bins = [b for b in profile if b["is_poc"]]
        assert len(poc_bins) >= 1
        max_vol = max(b["volume"] for b in profile)
        assert all(b["volume"] == max_vol for b in poc_bins)

    def test_zero_volume_candle_contributes_nothing(self):
        df = _make_df([
            (1, 100, 105, 98, 102, 0),
            (2, 102, 110, 101, 108, 2000),
        ])
        profile = compute_volume_profile(df, num_bins=10)
        total = sum(b["volume"] for b in profile)
        assert total == pytest.approx(2000, rel=1e-6)

    def test_single_price_candle_lands_in_one_bin(self):
        # ही candle चा high == low (उदा. एकाच किंमतीला संपूर्ण candle) -- तरीही overall range मध्ये असल्याने
        # bins तयार होतात (दुसऱ्या candle मुळे range शून्येतर आहे)
        df = _make_df([
            (1, 100, 100, 100, 100, 500),
            (2, 100, 110, 100, 105, 1000),
        ])
        profile = compute_volume_profile(df, num_bins=10)
        total = sum(b["volume"] for b in profile)
        assert total == pytest.approx(1500, rel=1e-6)

    def test_bins_are_price_ordered_and_non_overlapping(self):
        df = _make_df([
            (1, 100, 105, 98, 102, 1000),
            (2, 108, 112, 106, 110, 800),
        ])
        profile = compute_volume_profile(df, num_bins=8)
        for a, b in zip(profile, profile[1:]):
            assert a["price_high"] <= b["price_low"] + 1e-6


class TestBuildLightweightChartHtmlWithVolumeProfile:
    def test_html_includes_volume_profile_toggle_button_and_data(self):
        df = _make_df([
            (pd.Timestamp("2026-09-22 09:15"), 100, 105, 98, 102, 1000),
            (pd.Timestamp("2026-09-22 09:16"), 102, 110, 101, 108, 2000),
        ])
        html = build_lightweight_chart_html(df, symbol="NIFTY", timeframe_label="1M")
        assert "toggleVolumeProfile" in html
        assert "btn_volprofile" in html
        assert "VolumeProfilePrimitive" in html
        assert "volumeProfileData" in html

    def test_empty_df_returns_placeholder_not_crash(self):
        html = build_lightweight_chart_html(pd.DataFrame())
        assert "चार्टसाठी डेटा उपलब्ध नाही" in html
