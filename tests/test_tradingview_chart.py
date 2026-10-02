"""
tests/test_tradingview_chart.py
--------------------------------------------
Volume Profile व OI Profile (किंमतीनुसार horizontal histogram, प्रत्येकाच्या स्वतंत्र on/off बटणाने
toggle) — user requests: "Add volume profile indicator on both charts and give on off button" आणि
पुढे "Also add OI Profile on charts, and give on off button". दोन्ही charts (Dashboard तसंच MCX
Futures) एकाच build_lightweight_chart_html() वर अवलंबून असल्याने, त्याच फंक्शनला दिलेला df (Upstox
च्या historical-candle API मधून आधीपासूनच "oi" स्तंभासह येतो) वापरून compute_volume_profile()/
compute_oi_profile() मध्येच गणना होते — callers ना वेगळा parameter द्यावा लागत नाही.
"""
import pandas as pd
import pytest

from tradingview_chart import (
    build_lightweight_chart_html,
    compute_oi_profile,
    compute_volume_profile,
)


def _make_df(rows, oi=None):
    """rows: [(timestamp, open, high, low, close, volume), ...]; oi: वैकल्पिक समांतर यादी."""
    df = pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    if oi is not None:
        df["oi"] = oi
    return df


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


class TestComputeOIProfile:
    def test_empty_df_returns_empty_list(self):
        assert compute_oi_profile(pd.DataFrame()) == []

    def test_none_df_returns_empty_list(self):
        assert compute_oi_profile(None) == []

    def test_missing_oi_column_returns_empty_list(self):
        # "oi" स्तंभ नसेल तर (जुना/इतर स्त्रोताचा df) रिकामी यादी, त्रुटी नाही
        df = _make_df([(1, 100, 105, 98, 102, 1000)])
        assert compute_oi_profile(df) == []

    def test_all_zero_oi_returns_empty_list(self):
        # Index instruments (NIFTY/BANKNIFTY/SENSEX) साठी oi शून्यच असू शकतो — profile रिकामा, error नाही
        df = _make_df(
            [(1, 100, 105, 98, 102, 1000), (2, 102, 110, 101, 108, 2000)],
            oi=[0, 0],
        )
        assert compute_oi_profile(df) == []

    def test_total_oi_is_conserved_across_bins(self):
        df = _make_df(
            [
                (1, 100, 105, 98, 102, 1000),
                (2, 102, 110, 101, 108, 2000),
                (3, 108, 112, 104, 106, 1500),
            ],
            oi=[50000, 62000, 58000],
        )
        profile = compute_oi_profile(df, num_bins=10)
        assert profile
        total = sum(b["oi"] for b in profile)
        assert total == pytest.approx(170000, abs=0.5)

    def test_exactly_one_bin_marked_as_poc(self):
        df = _make_df(
            [
                (1, 100, 105, 98, 102, 1000),
                (2, 102, 110, 101, 108, 2000),
                (3, 108, 112, 104, 106, 1500),
            ],
            oi=[50000, 200000, 58000],  # दुसरी candle चा OI सर्वात मोठा -> POC इथेच असणार
        )
        profile = compute_oi_profile(df, num_bins=10)
        poc_bins = [b for b in profile if b["is_poc"]]
        assert len(poc_bins) >= 1
        max_oi = max(b["oi"] for b in profile)
        assert all(b["oi"] == max_oi for b in poc_bins)

    def test_oi_profile_independent_of_volume_profile(self):
        # एकाच df वर दोन्ही profiles स्वतंत्रपणे बरोबर यायला हव्यात (एकमेकांवर परिणाम नाही)
        df = _make_df(
            [(1, 100, 105, 98, 102, 1000), (2, 102, 110, 101, 108, 2000)],
            oi=[80000, 40000],
        )
        vol_profile = compute_volume_profile(df, num_bins=10)
        oi_profile = compute_oi_profile(df, num_bins=10)
        assert sum(b["volume"] for b in vol_profile) == pytest.approx(3000, abs=0.1)
        assert sum(b["oi"] for b in oi_profile) == pytest.approx(120000, abs=0.5)


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

    def test_html_includes_oi_profile_toggle_button_and_data(self):
        df = _make_df(
            [
                (pd.Timestamp("2026-09-22 09:15"), 100, 105, 98, 102, 1000),
                (pd.Timestamp("2026-09-22 09:16"), 102, 110, 101, 108, 2000),
            ],
            oi=[50000, 62000],
        )
        html = build_lightweight_chart_html(df, symbol="NIFTY", timeframe_label="1M")
        assert "toggleOIProfile" in html
        assert "btn_oiprofile" in html
        assert "OIProfilePrimitive" in html
        assert "oiProfileData" in html

    def test_empty_df_returns_placeholder_not_crash(self):
        html = build_lightweight_chart_html(pd.DataFrame())
        assert "चार्टसाठी डेटा उपलब्ध नाही" in html


# ---------------------------------------------------------------------------------------------------------------------
# 🎓 "EMA, VWAP, Bollinger, ADX चार्टवर" -- toolbar बटणाने on/off, सर्व डीफॉल्ट बंद.
# ---------------------------------------------------------------------------------------------------------------------
import numpy as np

from signals import calculate_adx, calculate_bollinger, calculate_ema, calculate_vwap
from tradingview_chart import compute_chart_indicators


def _ohlcv(n=120, step=0.0, volume=1000, days=1, seed=3):
    """5-मिनिट candles; step>0 => सतत वाढता (trend), step=0 => आडव्या रेंजमध्ये."""
    rng = np.random.default_rng(seed)
    per_day = n // days
    ts = []
    for d in range(days):
        ts += list(pd.date_range(f"2026-09-{28 + d} 09:15", periods=per_day, freq="5min"))
    close = 100 + np.arange(len(ts)) * step + rng.normal(0, 0.3, len(ts))
    return pd.DataFrame({
        "timestamp": ts, "open": close - 0.1, "high": close + 0.5, "low": close - 0.5, "close": close,
        "volume": volume, "oi": 0,
    })


class TestIndicatorMath:
    def test_ema_first_values_are_nan_then_follows_price(self):
        s = pd.Series(np.arange(1.0, 31.0))
        ema = calculate_ema(s, 10)
        assert ema.iloc[:9].isna().all() and ema.iloc[9:].notna().all()
        assert ema.iloc[-1] < s.iloc[-1]          # वाढत्या मालिकेत EMA मागे राहतो

    def test_bollinger_bands_are_symmetric_around_the_mean(self):
        close = pd.Series(np.sin(np.arange(60) / 5.0) * 5 + 100)
        mid, upper, lower = calculate_bollinger(close, 20, 2.0)
        assert mid.iloc[:19].isna().all()
        diff_up, diff_dn = (upper - mid).dropna(), (mid - lower).dropna()
        assert np.allclose(diff_up, diff_dn) and (diff_up > 0).all()

    def test_bollinger_uses_population_std(self):
        close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        mid, upper, _ = calculate_bollinger(close, 5, 1.0)
        assert upper.iloc[-1] - mid.iloc[-1] == pytest.approx(np.std([1, 2, 3, 4, 5]))   # ddof=0

    def test_vwap_resets_every_day(self):
        df = _ohlcv(n=120, days=2)
        vwap = calculate_vwap(df)
        day2_first = df.index[df["timestamp"].dt.day == 29][0]
        typical = (df["high"] + df["low"] + df["close"]) / 3
        assert vwap.iloc[day2_first] == pytest.approx(typical.iloc[day2_first])   # नव्या दिवसाचा पहिला bar = त्याचाच typical price
        assert vwap.iloc[0] == pytest.approx(typical.iloc[0])

    def test_vwap_is_nan_without_volume_not_zero(self):
        vwap = calculate_vwap(_ohlcv(volume=0))
        assert vwap.isna().all()

    def test_adx_high_in_strong_trend_low_in_range(self):
        trend = calculate_adx(_ohlcv(n=200, step=0.5))[0].iloc[-1]
        rng = calculate_adx(_ohlcv(n=200, step=0.0))[0].iloc[-1]
        assert trend > 40 and rng < 25 and 0 <= rng <= 100 and trend <= 100

    def test_adx_plus_di_dominates_in_uptrend(self):
        _, plus_di, minus_di = calculate_adx(_ohlcv(n=200, step=0.5))
        assert plus_di.iloc[-1] > minus_di.iloc[-1]


class TestComputeChartIndicators:
    def test_all_four_present_with_labels(self):
        ind = compute_chart_indicators(_ohlcv(n=200), ema_fast=9, ema_slow=21, bb_period=20, bb_std=2.0, adx_period=14)
        assert set(ind) == {"ema", "vwap", "bb", "adx"}
        assert ind["ema"]["label"] == "EMA 9/21" and ind["bb"]["label"] == "BB 20,2" and ind["adx"]["label"] == "ADX 14"
        assert ind["ema"]["fast"] and ind["ema"]["slow"] and ind["vwap"]["line"]
        assert all(set(p) == {"time", "value"} for p in ind["ema"]["fast"][:3])

    def test_no_volume_drops_vwap_only(self):
        ind = compute_chart_indicators(_ohlcv(n=200, volume=0))
        assert "vwap" not in ind and {"ema", "bb", "adx"} <= set(ind)

    def test_daily_timeframe_drops_vwap(self):
        assert "vwap" not in compute_chart_indicators(_ohlcv(n=200), intraday=False)

    def test_too_little_data_drops_indicators_that_cannot_be_computed(self):
        ind = compute_chart_indicators(_ohlcv(n=10), ema_fast=20, ema_slow=50)
        assert "ema" not in ind and "bb" not in ind and "adx" not in ind

    def test_empty_or_none(self):
        assert compute_chart_indicators(None) == {} and compute_chart_indicators(pd.DataFrame()) == {}


class TestChartHtmlIndicatorButtons:
    def _html(self, **kw):
        return build_lightweight_chart_html(_ohlcv(n=200), symbol="NIFTY", timeframe_label="5M", **kw)

    def test_no_indicators_means_no_buttons_old_behaviour(self):
        assert 'id="btn_ind_' not in self._html()
        assert 'id="btn_ind_' not in self._html(indicators={})

    def test_buttons_exist_only_for_available_indicators(self):
        ind = compute_chart_indicators(_ohlcv(n=200, volume=0))     # VWAP नाही
        html = self._html(indicators=ind)
        for key in ("ema", "bb", "adx"):
            assert f'id="btn_ind_{key}"' in html
        assert 'id="btn_ind_vwap"' not in html

    def test_indicator_lines_start_hidden(self):
        html = self._html(indicators=compute_chart_indicators(_ohlcv(n=200)))
        assert "visible: false" in html and "toggleIndicator" in html and "removePane" in html
