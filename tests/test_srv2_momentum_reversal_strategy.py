"""
tests/test_srv2_momentum_reversal_strategy.py
--------------------------------------------------------------
srv2_momentum_reversal_strategy.py — वापरकर्त्याने दिलेल्या संपूर्ण blueprint वरून बांधलेली
"Nifty SRv2 Momentum-Filter Reversal" रणनीती — established SRv2 + 0.40% गती-फिल्टर +
established ATM+1/ATM+3 strike-निवड + One-Touch/Cooldown.
"""
from unittest.mock import MagicMock, patch

import datetime

import pandas as pd

import srv2_momentum_reversal_strategy as srv2
import cloud_db
from config import get_ist_now


class TestSrv2UsesSharedDualThresholdRsiFilter:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("RSI setting 60/40 अशी करा") — established single, सममित
    rsi_neutral_level (50) ऐवजी आता dynamic_sr_instant_trader.check_instant_rsi_filter() (established,
    सिद्ध — नवीन कॉपी नाही) पुनर्वापरलेला — Support<40/Resistance>60 (डीफॉल्ट, Dashboard वरून
    बदलण्याजोगे). प्रत्यक्ष RSI-गणिताच्या चाचण्या त्याच्याच test file मध्ये आधीच आहेत — इथे फक्त
    srv2 ने तेच फंक्शन वापरायला हवं, हे पडताळतो."""

    def test_srv2_module_reuses_check_instant_rsi_filter(self):
        from dynamic_sr_instant_trader import check_instant_rsi_filter
        assert srv2.check_instant_rsi_filter is check_instant_rsi_filter

    def test_custom_rsi_thresholds_actually_used(self):
        """🎓 वापरकर्त्याने पडताळणीत सापडवलेल्या तत्सम bugs (dynamic_sr_instant/target_pct साठी
        आधीच आढळलेल्या) टाळण्यासाठी — Dashboard वरचं rsi_support_max/rsi_resistance_min खरंच
        check_instant_rsi_filter() ला पाठवलं जातं, हार्डकोडेड डीफॉल्ट (40/60) कायम वापरला जात नाही."""
        candles_df = _fake_candles_df(last_close=23902)
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        custom_settings["rsi_support_max"] = 5
        custom_settings["rsi_resistance_min"] = 95
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "check_instant_rsi_filter", return_value=(True, 30.0)) as mock_rsi_filter, \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_rsi_filter.called
            assert mock_rsi_filter.call_args.args[2] == 5    # rsi_support_max
            assert mock_rsi_filter.call_args.args[3] == 95   # rsi_resistance_min


class TestComputeSLPctFromAbsolute:
    """🎓 Rule 3 -- established sl_pct_of_credit (%) मध्ये रूपांतरण, वापरकर्त्याने दिलेल्या ₹500 वरून."""

    def test_converts_rupees_to_percentage_correctly(self):
        sl_pct = srv2.compute_sl_pct_from_absolute(500, 2275)
        assert abs(sl_pct - (500 / 2275 * 100)) < 0.01

    def test_zero_credit_returns_none(self):
        assert srv2.compute_sl_pct_from_absolute(500, 0) is None

    def test_caps_at_100_percent(self):
        sl_pct = srv2.compute_sl_pct_from_absolute(500, 100)
        assert sl_pct == 100


class TestIsInCooldown:
    """🎓 Rule 4 (Cooldown) -- SL लागल्यावर established ३०-मिनिटांचा अनिवार्य विराम."""

    def test_no_previous_sl_not_in_cooldown(self):
        assert srv2.is_in_cooldown(None, get_ist_now()) is False

    def test_recent_sl_is_in_cooldown(self):
        now = get_ist_now()
        assert srv2.is_in_cooldown(now, now) is True

    def test_old_sl_not_in_cooldown(self):
        import datetime
        now = get_ist_now()
        old_sl = now - datetime.timedelta(minutes=45)
        assert srv2.is_in_cooldown(old_sl, now) is False


class TestIsRepeatedLevel:
    """🎓 Rule 4 (One-Touch) -- established, तोच level लगेच पुन्हा टेस्ट झाला का."""

    def test_no_previous_level_not_repeated(self):
        assert srv2.is_repeated_level(23900.0, None) is False

    def test_same_level_is_repeated(self):
        assert srv2.is_repeated_level(23900.0, 23900.0) is True

    def test_different_level_not_repeated(self):
        assert srv2.is_repeated_level(23900.0, 24500.0) is False


class TestDetermineDirectionWithHysteresis:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py मधलीच hysteresis पद्धत
    इथेही, पण 15M/30M/60M candles साठी वेगळा, अरुंद buffer — 0.015%. किंमत level पासून त्या
    (अरुंद) बँडच्या आतच wobble करत असेल, तर आधीचीच निश्चित दिशा कायम राहायला हवी."""

    LEVEL = 23353.1  # dynamic_sr_instant_trader.py च्या टेस्टमधलाच level, तुलना सोपी व्हावी म्हणून

    def test_sticky_bullish_when_dip_stays_within_buffer(self):
        """किंमत आधी स्पष्टपणे level च्या वर होती (confirmed BULLISH), नंतर level च्या किंचित खाली
        (पण 0.015% buffer च्या आतच) गेली — निश्चित BULLISH च राहायला हवं."""
        closes = [23400.0, 23351.0]  # 23351 < level(23353.1) पण lower buffer(~23349.6) च्या वरच
        assert srv2.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_flips_to_bearish_only_when_clearly_beyond_buffer(self):
        """किंमत खरंच buffer च्या पलीकडे (स्पष्टपणे) खाली गेली, तरच दिशा खऱ्या अर्थाने फ्लिप व्हायला हवी."""
        closes = [23400.0, 23340.0]  # 23340 < lower buffer (~23349.6) -- खरा breakdown
        assert srv2.determine_direction_with_hysteresis(self.LEVEL, closes) == "BEARISH"

    def test_falls_back_to_raw_comparison_when_never_left_band(self):
        """आजचा संपूर्ण इतिहास कधीच buffer च्या बाहेर गेलाच नसेल, तर सद्य किमतीची raw तुलनाच
        (जुनं वर्तन) सुरक्षित fallback म्हणून वापरली जायला हवी."""
        closes = [23353.1]  # बरोबर level वरच, buffer बाहेर कधीच नाही
        assert srv2.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_real_world_scenario_stays_bullish_through_momentary_dip(self):
        """किंमत स्पष्टपणे support च्या वर असतानाच, एका candle साठी किंचित खाली डोकावली (0.015%
        च्या आतच) आणि परत वर आली — संपूर्ण काळात BULLISH च राहायला हवं, उगाच फ्लिप नाही."""
        closes = [23400.0, 23352.0, 23350.5, 23355.0]  # सगळेच buffer (~23349.6-23356.6) च्या आत/वर
        for i in range(1, len(closes) + 1):
            assert srv2.determine_direction_with_hysteresis(self.LEVEL, closes[:i]) == "BULLISH"

    def test_uses_narrower_buffer_than_dynamic_sr_instant_trader(self):
        """🎓 वापरकर्त्याने स्पष्टपणे मागितलेला 0.015% (dynamic_sr_instant_trader.py च्या 0.10%
        पेक्षा वेगळा, अरुंद) buffer — एक हालचाल जी तिथल्या 0.10% buffer च्या आतच बसते, पण इथल्या
        0.015% buffer च्या बाहेर पडते, इथे मात्र दिशा खरंच फ्लिप करायला हवी."""
        closes = [23400.0, 23330.0]  # dynamic_sr_instant_trader.py च्या 0.10% lower(23329.75) पेक्षा वरच
        assert srv2.determine_direction_with_hysteresis(self.LEVEL, closes) == "BEARISH"


def _fake_chain(spot):
    atm = round(spot / 50) * 50
    chain = []
    for k in range(atm - 300, atm + 300, 50):
        dist = abs(k - atm)
        premium = max(150 - dist * 0.3, 5)
        chain.append({"strike_price": k, "underlying_spot_price": spot,
                      "call_options": {"instrument_key": f"CE{k}", "market_data": {"ltp": premium}, "option_greeks": {}},
                      "put_options": {"instrument_key": f"PE{k}", "market_data": {"ltp": premium}, "option_greeks": {}}})
    return chain


def _fake_candles_df(n=20, last_close=23930):
    # 🎓 वापरकर्त्याने सापडवलेली bug (कालचे candles मिसळणे) फिक्स केल्यानंतर — process_symbol() आता
    # आजचाच दिवस फिल्टर करतो, त्यामुळे fixture ला आता "आज" (srv2.get_ist_now(), जेणेकरून mock
    # केल्यास सुसंगत राहील) ला संपणाऱ्या timestamps हव्यात — हार्डकोड केलेली जुनी तारीख नाही.
    end_ts = srv2.get_ist_now().replace(hour=15, minute=15, second=0, microsecond=0)
    dates = pd.date_range(end=end_ts, periods=n, freq="15min")
    closes = [24100 - i * 10 for i in range(n - 1)] + [last_close]
    return pd.DataFrame({"timestamp": dates, "open": closes, "high": [c + 15 for c in closes],
                          "low": [c - 15 for c in closes], "close": closes, "volume": 0, "oi": 0})


def _fake_dyn_zones(symbol="NIFTY", support_level=23900.0):
    """SRv2 आता Supabase मध्ये साठवलेले DYNAMIC_SR_*_15M levels वापरतो (15-मिनिट डेटावरून काढलेले,
    Instant Trader च्या 1-मिनिट आवृत्तीपासून वेगळे)."""
    return pd.DataFrame([
        {"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": support_level, "zone_high": support_level,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


def _fake_dyn_zones_30m_only(symbol="NIFTY", support_level=23900.0):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Timeframe) — फक्त 30M level (15M/60M नाहीत)."""
    return pd.DataFrame([
        {"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": support_level, "zone_high": support_level,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


def _fake_dyn_zones_60m_only(symbol="NIFTY", support_level=23900.0):
    """फक्त 60M level (15M/30M नाहीत)."""
    return pd.DataFrame([
        {"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_60M", "zone_low": support_level, "zone_high": support_level,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


class TestCollectTouchCandidates60m:
    """🎓 वापरकर्त्याने सापडवलेली bug — "60minute" हा Upstox कडून थेट verified interval नाही
    (fetch_candles() मध्ये allowed_intervals यादीत नाही), त्यामुळे आधी शांतपणे "30minute" कडे पडायचं
    (पण RSI "60M" चाच आहे असं भासवत राहायचं). आता 30-मिनिट candles मागवून resample करायला हवं
    (fetch_timeframe_df() मध्ये आधीच वापरलेला पॅटर्न) — कधीच थेट interval="60minute"/"1hour" मागवला
    जाऊ नये."""

    def test_60m_candidate_fetches_30minute_and_resamples(self):
        df_30m = _fake_candles_df(n=60, last_close=23930)  # >=12 तासांचं, resample नंतरही >=12 hourly candles उरावेत

        def fetch_side_effect(access_token, symbol, current_spot, interval, lookback_days=None):
            assert interval != "60minute" and interval != "1hour"
            if interval == "30minute":
                return df_30m
            return pd.DataFrame(columns=df_30m.columns)

        with patch.object(srv2, "fetch_candles", side_effect=fetch_side_effect):
            candidates = srv2._collect_touch_candidates(
                "fake_token", "NIFTY", _fake_dyn_zones_60m_only(), srv2.get_ist_now(),
            )
        assert len(candidates) == 1
        level_price, suffix, candles_df, underlying_price, todays_closes = candidates[0]
        assert suffix == "60M"
        # resample_to_1h ने 30-मिनिट candles अर्ध्यावर आणायला हवेत (साधारण)
        assert len(candles_df) < len(df_30m)


class TestCollectTouchCandidatesActiveTimeframes:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("15 minute डीफॉल्ट, 30/60 optional") —
    active_timeframes दिलं की, फक्त त्यातल्याच timeframes चे ACTIVE zones candidates मध्ये यावेत,
    बाकीचे (जरी ACTIVE असले तरी) पूर्णपणे वगळले जावेत."""

    def _combined_15m_and_30m_zones(self):
        return pd.concat([_fake_dyn_zones(support_level=23900.0), _fake_dyn_zones_30m_only(support_level=24000.0)], ignore_index=True)

    def test_only_15m_returned_when_active_timeframes_is_15m_only(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2, "fetch_candles", return_value=candles_df):
            candidates = srv2._collect_touch_candidates(
                "fake_token", "NIFTY", self._combined_15m_and_30m_zones(), srv2.get_ist_now(), active_timeframes=["15M"],
            )
        assert len(candidates) == 1
        assert candidates[0][1] == "15M"

    def test_both_returned_when_both_active(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2, "fetch_candles", return_value=candles_df):
            candidates = srv2._collect_touch_candidates(
                "fake_token", "NIFTY", self._combined_15m_and_30m_zones(), srv2.get_ist_now(), active_timeframes=["15M", "30M"],
            )
        suffixes = {c[1] for c in candidates}
        assert suffixes == {"15M", "30M"}

    def test_default_none_means_all_timeframes(self):
        """active_timeframes न दिल्यास (established जुने कॉलर्स) established जुनंच वर्तन — तिन्ही एकत्र."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2, "fetch_candles", return_value=candles_df):
            candidates = srv2._collect_touch_candidates(
                "fake_token", "NIFTY", self._combined_15m_and_30m_zones(), srv2.get_ist_now(),
            )
        suffixes = {c[1] for c in candidates}
        assert suffixes == {"15M", "30M"}


class TestProcessSymbol:
    def test_cooldown_blocks_entry(self):
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": get_ist_now()}):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert "Cooldown" in result

    def test_successful_support_bounce_entry(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True) as mock_telegram, \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True) as mock_save:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_telegram.called
            assert mock_save.called
            assert "Bull Put Spread" in result

    def test_custom_target_pct_setting_is_actually_used(self):
        """🎓 वापरकर्त्याने पडताळणीत सापडवलेली bug (live trading आधी) — Dashboard वरचं "Target — %
        of Net Premium" setting (spread_target_pct_of_premium) आधी इथे कधीच वाचलंच जायचं नाही,
        नेहमी हार्डकोडेड 80% वापरला जायचा. वापरकर्त्याने 40% सेट केलं तरी bot शांतपणे 80% वरच
        थांबायचा -- आता settings चीच value खरोखर वापरली जायला हवी."""
        candles_df = _fake_candles_df(last_close=23902)
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        custom_settings["spread_target_pct_of_premium"] = 40.0
        custom_settings["naked_enabled"] = False  # फक्त spread call तपासण्यासाठी, naked leg (वेगळा target_pct_of_max_profit=100 वापरतो) वेगळी ठेवण्यासाठी
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_trade.call_args.kwargs["target_pct_of_max_profit"] == 40.0

    def test_atm_strike_rounds_to_symbol_own_strike_step_not_always_50(self):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — dynamic_sr_instant_trader.py/classic_sr_reversal_trader.py
        प्रमाणेच इथेही atm_strike कायम round(price/50)*50 वापरत होता, BANKNIFTY/SENSEX (strike step 100)
        साठी अनेकदा चुकीचा (raw_chain मध्ये सापडतच न येणाऱ्या ग्रिडवर strike). आता symbol च्या
        cloud_db.STRIKE_STEP नुसार राऊंड होतो."""
        candles_df = _fake_candles_df(last_close=51930)
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        custom_settings["symbol_enabled"] = True
        custom_settings["entry_rsi_gate_enabled"] = False
        custom_settings["naked_enabled"] = False
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones(symbol="BANKNIFTY", support_level=51930.0)), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(51930.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}) as mock_select, \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            srv2.process_symbol("fake_token", "BANKNIFTY")
            assert mock_select.called
            # round(51930/100)*100 = 51900 -- जुनी बग round(51930/50)*50 = 51950 देत होती
            assert mock_select.call_args.args[2] == 51900
            assert mock_select.call_args.kwargs.get("step") == 100

    def test_entry_uses_fresh_chain_price_not_stale_touch_detection_price(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा ("entry साठी touch-detection च्याच जुन्या किंमतीवर
        अवलंबून आहे, ताजी किंमत परत घ्या") — dynamic_sr_instant_trader.py प्रमाणेच, entry-क्षणी
        परत मागवलेल्या option chain मधली सद्य spot किंमत (touch-detection वेळच्या जुन्या candle-close
        ऐवजी) आता atm_strike आणि entry_spot_price (SL/TSL च्या Spot% आधारासाठी) दोन्हींसाठी वापरली
        जायला हवी."""
        candles_df = _fake_candles_df(last_close=23902)  # touch-detection वेळची (जुनी) किंमत
        fresh_spot = 23940.0  # entry-क्षणी परत मागवलेल्या chain मधली वेगळी, ताजी किंमत
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        custom_settings["entry_rsi_gate_enabled"] = False
        custom_settings["naked_enabled"] = False  # फक्त spread call तपासण्यासाठी, isolate करून
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(fresh_spot), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}) as mock_select, \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_trade.call_args.kwargs["entry_spot_price"] == fresh_spot
            # round(23940/50)*50 = 23950 -- जुन्या (stale) 23902 वरून round(23902/50)*50=23900 पेक्षा वेगळं
            assert mock_select.call_args.args[2] == 23950

    def test_get_zone_hits_today_called_with_role_from_level_type(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेला role-split max-2 counter — last_close=23902 >=
        support_level=23900 त्यामुळे level_type="SUPPORT" ठरतो, तोच role म्हणून पास व्हायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)) as mock_hits, \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_hits.called
            assert mock_hits.call_args.kwargs.get("role") == "SUPPORT"

    def test_multi_hit_max_2_per_level_skips_third(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit, One-Touch ऐवजी) — established
        established level ला आजच established 2 वेळा hit झालेला असेल, तर established 3रा वेळा
        established दुर्लक्षित व्हायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now(), get_ist_now())), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert "पात्र ठरला नाही" in result

    def test_first_hit_of_level_still_skipped_if_any_other_position_open(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (dynamic_sr_instant_trader.py मध्ये Order Log
        मधून सापडवलेल्याच bug ची इथेही दुरुस्ती) — एका (वेगळ्या) level वर आधीच position उघडी असताना,
        आजचा या level चा पहिलाच hit (hit_count_so_far=0) असला, तरी नवीन trade उघडली जाऊ नये."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=True), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert "पात्र ठरला नाही" in result

    def test_yesterdays_candle_never_used_for_underlying_price(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (1M Instant Trader मध्ये सापडलेल्याच पॅटर्नची) —
        आजचा पहिला 15-मिनिट candle अजून तयार झालेला नसताना, कालचा शेवटचा candle underlying_price
        साठी वापरला जायचा नाही — आजचेच candles नसतील तर स्पष्ट संदेश यायला हवा."""
        today_ist = srv2.get_ist_now()
        yesterday_ist = today_ist - datetime.timedelta(days=1)
        candles_df = pd.DataFrame([
            {"timestamp": yesterday_ist.replace(hour=15, minute=15), "open": 23900, "high": 23920,
             "low": 23880, "close": 23902, "volume": 0, "oi": 0}
        ] * 15)  # RSI(14) साठी पुरेसे, सर्व कालचेच
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert "आजचे" in result and "नाहीत" in result

    def test_resistance_converts_to_support_when_price_above_level(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — दिशा साठवलेल्या (ऐतिहासिक) zone_type लेबलवरून
        नाही, तर सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून ठरते. साठवलेला label RESISTANCE असला,
        तरी सद्य किंमत त्या level च्या वर असेल (support सारखी स्थिती), तर BULLISH (Bull Put) व्हायला हवं."""
        def _fake_resistance_zone(symbol="NIFTY", level=23900.0):
            return pd.DataFrame([
                {"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": level, "zone_high": level,
                 "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
            ])
        candles_df = _fake_candles_df(last_close=23902)  # किंमत level (23900) च्या वर -- आता Support सारखी
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_resistance_zone()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}) as mock_select, \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T50"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_select.call_args.args[1] == "BULLISH"  # saved label RESISTANCE असूनही, दिशा BULLISH
            logged_level_type = mock_log.call_args[0][0]["level_type"]
            assert logged_level_type == "SUPPORT"  # dynamic label -- साठवलेला RESISTANCE नाही

    def test_multi_hit_second_time_skipped_if_previous_position_still_open(self):
        """आजचा 1 वेळा hit झालेला आहे, आणि याच strategy ची position अजून उघडी (बंद झालेली नाही)
        असेल, तर 2रा hit दुर्लक्षित व्हायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(1, get_ist_now(), get_ist_now())), \
             patch.object(srv2, "has_open_trade_from_source", return_value=True), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert "पात्र ठरला नाही" in result

    def test_multi_hit_second_time_allowed_if_previous_position_closed(self):
        """आधीची position बंद (SL/Target लागलेली) असेल, तर 2रा hit यशस्वीरित्या घेता यायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(1, get_ist_now(), get_ist_now())), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T2"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert "Bull Put Spread" in result

    def test_rsi_filter_rejects_wrong_direction(self):
        """🎓 established जुनं "choppy market" टेस्ट established RSI-आधारित फिल्टरसाठी अद्ययावत केलं —
        established सलग वाढणाऱ्या (established RSI established 50 च्या वर) डेटावर established
        established BULLISH (Support Bounce, established RSI<50 हवा) established साठी established
        established नाकारलं जायला हवं — established जरी established किंमत established Support ला
        established प्रत्यक्ष स्पर्श करत असली तरी."""
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Signal Logging टेस्ट लिहिताना सापडलेली, वेगळी
        # bug) — हार्डकोड जुनी तारीख ("2026-09-05") वापरलेली होती, त्यामुळे _collect_touch_candidates()
        # आजचे candles रिकामे समजून हा candidate आधीच वगळत होता — म्हणजे RSI-गेट खरंच कधीच तपासलाच
        # जात नव्हता, आणि "not mock_trade.called" फक्त "कुठलाही candidate सापडला नाही" या (चुकीच्या)
        # कारणाने खरं ठरत होतं, RSI-नकारामुळे नाही. आता _fake_candles_df() सारखीच आजच्या तारखेला
        # संपणारी तारीख-रचना.
        end_ts = srv2.get_ist_now().replace(hour=15, minute=15, second=0, microsecond=0)
        dates = pd.date_range(end=end_ts, periods=30, freq="15min")
        # established सलग वाढ, established शेवटी established बरोब्बर established support_level (23900)
        # ला स्पर्श -- established RSI established establishedच्या established उभारीमुळे established >50 असेल.
        # 🎓 SRv2 साठी 0.015% hysteresis buffer जोडल्यानंतर सुधारित — शेवटचा close नुसता level बरोबरच
        # असेल (आणि आधीची सगळी history level च्या स्पष्टपणे खालीच), तर hysteresis दिशा BEARISH ठरवेल
        # (level ला खालून resistance सारखा टेस्ट केला असं मानून) — इथे मात्र उभारीतच अगदी शेवटच्या
        # आधीचा close स्पष्टपणे बँडच्या वर (23920) ठेवून, नंतर बरोब्बर level ला स्पर्श — त्यामुळे दिशा
        # अजूनही BULLISH च राहते (हाच टेस्टचा मूळ हेतू — जोरदार तेजीमुळे RSI>50, Support Bounce<50 शी
        # विसंगत ठरून नाकारलं जायला हवं), फक्त रचना hysteresis-सुसंगत केली.
        rising_closes = [23800 + i * (100 / 29) for i in range(28)] + [23920.0, 23900.0]
        candles_rising = pd.DataFrame({"timestamp": dates, "open": rising_closes, "high": [c + 5 for c in rising_closes],
                                        "low": [c - 5 for c in rising_closes], "close": rising_closes, "volume": 0, "oi": 0})
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_rising), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called

    def test_symbol_disabled_skips_entirely(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (symbol_enabled) — उपलब्ध भांडवलानुसार
        वापरकर्ता BANKNIFTY/SENSEX बंद ठेवू शकतो; बंद असल्यास state/cooldown/candles काहीही
        न वाचता थेट थांबायला हवं."""
        disabled_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        disabled_settings["symbol_enabled"] = False
        with patch.object(srv2.cloud_db, "get_strategy_settings", return_value=disabled_settings), \
             patch.object(srv2.cloud_db, "get_srv2_state") as mock_state:
            result = srv2.process_symbol("fake_token", "SENSEX")
            assert "बंद आहे" in result
            assert not mock_state.called

    def test_insufficient_candle_history_handled_gracefully(self):
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_candles", return_value=pd.DataFrame()):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result


class TestProcessSymbolMultiAccount:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) — आता "कुठलेही broker_accounts
    नोंदवलेले असतील तर सर्व सक्रिय accounts" ऐवजी, settings मधल्याच broker_account_ids (वापरकर्त्याने
    याच strategy+symbol साठी स्पष्ट निवडलेले) असतील तरच execute_trade_on_all_accounts() (replicated)
    वापरलं जातं."""

    def test_uses_multi_account_when_broker_account_ids_selected(self):
        candles_df = _fake_candles_df(last_close=23902)
        settings_with_broker = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        settings_with_broker["symbol_enabled"] = True
        settings_with_broker["broker_account_ids"] = ["A1"]
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=settings_with_broker), \
             patch("trading_engine.execute_trade_on_all_accounts", return_value=([{"account_id": "A1", "ok": True, "result": "OPENED"}], [])) as mock_multi, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_multi.called
            assert mock_multi.call_args.kwargs["account_ids"] == ["A1"]
            assert "A1" in result

    def test_uses_single_upstox_trade_when_no_broker_account_ids(self):
        """डीफॉल्ट (broker_account_ids रिकामी) — जुनंच शुद्ध Upstox, single trade वर्तन कायम."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch("trading_engine.execute_trade_on_all_accounts") as mock_multi, \
             patch.object(srv2, "open_multi_leg_trade", return_value=(True, "trade_id_123")) as mock_single, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_multi.called
            assert mock_single.called
            assert mock_single.call_args.kwargs["trading_mode"] == "PAPER"


class TestMultiTimeframe:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — 15M/30M/60M एकत्र, settings-चालित lots/hedge_width,
    Expiry-Day Logic."""

    def test_30m_only_level_still_triggers_entry(self):
        """फक्त 30M level (15M/60M नाहीत) असला, तरी 30M active_timeframes मध्ये असेल तर तोही तपासला
        जाऊन trade व्हायला हवा (🎓 active_timeframes डीफॉल्ट फक्त ["15M"] असल्याने, इथे स्पष्टपणे
        30M समाविष्ट करूनच वापरकर्त्याने निवड केल्याचं गृहीत धरलेलं)."""
        candles_df = _fake_candles_df(last_close=23902)
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        custom_settings["active_timeframes"] = ["15M", "30M", "60M"]
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones_30m_only()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T60"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert "30M" in result

    def test_settings_lots_and_hedge_width_passed_through(self):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Dashboard settings (lots=3, hedge_width=75)
        hardcoded मूल्यांऐवजी प्रत्यक्ष वापरली जायला हवीत. naked_enabled=False -- फक्त spread call
        तपासण्यासाठी (mock_trade.call_args शेवटचा कॉल पकडतो, आणि naked_lots आता स्वतंत्र सेटिंग
        असल्याने naked call इथे तपासायचा नाही)."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value={**cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"], "lots": 3, "hedge_width_points": 75.0, "naked_enabled": False}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}) as mock_select, \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T61"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_select.call_args.kwargs.get("hedge_width_points") == 75.0
            assert mock_trade.call_args.kwargs.get("lots") == 3

    def test_expiry_day_uses_next_expiry_index(self):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Expiry-Day Logic) — आज expiry day असेल, तर
        fetch_upstox_option_chain ला expiry_index=1 (पुढची expiry) द्यायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        today_str = srv2.get_ist_now().strftime("%Y-%m-%d")
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=[today_str]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")) as mock_chain, \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T62"}, "OPENED")), \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_chain.call_args.kwargs.get("expiry_index") == 1

    def test_non_expiry_day_uses_current_expiry_index(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")) as mock_chain, \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T63"}, "OPENED")), \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_chain.call_args.kwargs.get("expiry_index") == 0

    def test_is_todays_expiry_day_true_when_nearest_expiry_is_today(self):
        today_str = srv2.get_ist_now().strftime("%Y-%m-%d")
        with patch.object(srv2, "fetch_option_expiries", return_value=[today_str, "2099-01-01"]):
            assert srv2.is_todays_expiry_day("fake_token", "NIFTY") is True

    def test_is_todays_expiry_day_false_when_nearest_expiry_is_later(self):
        with patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]):
            assert srv2.is_todays_expiry_day("fake_token", "NIFTY") is False

    def test_is_todays_expiry_day_false_when_no_expiries_found(self):
        with patch.object(srv2, "fetch_option_expiries", return_value=[]):
            assert srv2.is_todays_expiry_day("fake_token", "NIFTY") is False

    def test_entry_level_price_passed_to_open_trade(self):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — entry_level_price आता trading_engine.py च्या
        Spot-SL/Next-Level-Exit साठी trade उघडतानाच साठवला जायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T64"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_args.kwargs.get("entry_level_price") == 23900.0
            assert mock_trade.call_args.kwargs.get("entry_timeframe") == "15M"

    def test_naked_trade_fires_alongside_spread_by_default(self):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Naked Option Trade) — SRv2 मध्येही Credit
        Spread सोबतच, समांतर, डीफॉल्ट सक्रिय."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23800, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}) as mock_naked_select, \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T80"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_naked_select.called
            assert mock_trade.call_count == 2  # स्प्रेड + Naked दोन्ही

    def test_naked_lots_used_independently_from_spread_lots(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py प्रमाणेच इथेही —
        Naked Option Trade आता Credit Spread पासून स्वतंत्र "naked_lots" वापरतो."""
        candles_df = _fake_candles_df(last_close=23902)
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        custom_settings["lots"] = 2
        custom_settings["naked_lots"] = 5
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23800, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}), \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T81"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 2
            spread_call, naked_call = mock_trade.call_args_list
            assert spread_call.kwargs.get("lots") == 2
            assert naked_call.kwargs.get("lots") == 5

    def test_naked_trade_skipped_when_disabled_in_settings(self):
        candles_df = _fake_candles_df(last_close=23902)
        disabled_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        disabled_settings["naked_enabled"] = False
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_strategy_settings", return_value=disabled_settings), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "select_naked_option_itm") as mock_naked_select, \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T81"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_naked_select.called
            assert mock_trade.call_count == 1  # फक्त स्प्रेड, Naked नाही


class TestPCRGate:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PCR Gate) — SRv2 मध्येही, RSI नंतर लगेच,
    दोन्ही trade-प्रकारांना एकत्र लागू."""

    def test_pcr_gate_blocks_entry(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(False, 0.72, "PCR 0.72 < 0.80")), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called

    def test_pcr_gate_allows_entry_when_passed(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_option_expiries", return_value=[]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T91"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called


class TestSignalLogging:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Market Zones tab वर 1m_instant सारखाच संपूर्ण
    Signal Log, SRv2 साठीही) — याआधी फक्त प्रत्यक्ष trade झाला तरच save_signal_log() व्हायचं;
    आता touch न झालेले आणि कुठल्याही gate ने अडवलेले candidates सुद्धा (reason सह) साठवले
    जातात, जेणेकरून entry/exit cross-verify करता येईल."""

    def test_no_hit_logs_but_does_not_trade(self):
        candles_df = _fake_candles_df(last_close=24500)  # level (23900) पासून खूप दूर -- touch नाही
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade, \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called
            logged = mock_log.call_args[0][0]
            assert logged["hit_type"] == "NO_HIT"

    def test_rsi_filter_rejection_is_logged(self):
        # 🎓 आजच्याच तारखेला संपणारे candles हवेत (_fake_candles_df सारखे) -- हार्डकोड जुनी तारीख
        # वापरली तर _collect_touch_candidates() todays_candles_df रिकामं समजून हा candidate आधीच
        # वगळतो, आणि RSI-गेट कधीच तपासलाच जात नाही.
        end_ts = srv2.get_ist_now().replace(hour=15, minute=15, second=0, microsecond=0)
        dates = pd.date_range(end=end_ts, periods=30, freq="15min")
        # 🎓 SRv2 साठी 0.015% hysteresis buffer जोडल्यानंतर सुधारित (बघा
        # test_rsi_filter_rejects_wrong_direction मधली तीच टीप) — शेवटच्या touch आधी एक close
        # बँडच्या स्पष्टपणे वर (23920) ठेवून दिशा BULLISH च राहील याची खात्री.
        rising_closes = [23800 + i * (100 / 29) for i in range(28)] + [23920.0, 23900.0]
        candles_rising = pd.DataFrame({"timestamp": dates, "open": rising_closes, "high": [c + 5 for c in rising_closes],
                                        "low": [c - 5 for c in rising_closes], "close": rising_closes, "volume": 0, "oi": 0})
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_rising), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade, \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called
            logged = mock_log.call_args[0][0]
            assert logged["trade_status"] == "SKIPPED_RSI_FILTER"

    def test_pcr_gate_rejection_is_logged(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(False, 0.72, "PCR 0.72 < 0.80")), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade, \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called
            logged = mock_log.call_args[0][0]
            assert logged["trade_status"] == "SKIPPED_PCR_GATE"

    def test_multi_hit_limit_is_logged(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now(), get_ist_now())), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade, \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called
            logged = mock_log.call_args[0][0]
            assert logged["trade_status"] == "SKIPPED_MAX_2_HITS_REACHED"

    def test_open_position_skip_is_logged(self):
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=True), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade, \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called
            logged = mock_log.call_args[0][0]
            assert logged["trade_status"] == "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"


class TestRunAllSymbols:
    """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — dynamic_sr_instant_trader.py प्रमाणेच इथेही — एका
    symbol मधल्या अनपेक्षित exception मुळे उरलेले symbols त्याच cycle मध्ये कधीच तपासलेच जायचे
    नाहीत, आणि heartbeat/अलर्टही कधीच पोहोचायचा नाही. आता प्रत्येक symbol स्वतंत्र."""

    def test_one_symbol_exception_does_not_block_the_rest(self, monkeypatch):
        calls = []

        def fake_process_symbol(token, symbol):
            calls.append(symbol)
            if symbol == "BANKNIFTY":
                raise RuntimeError("database is locked")
            return f"{symbol}: ok"

        monkeypatch.setattr(srv2, "process_symbol", fake_process_symbol)
        mock_notify = MagicMock()
        monkeypatch.setattr(srv2, "notify_error", mock_notify)

        result = srv2.run_all_symbols("fake_token", ["NIFTY", "BANKNIFTY", "SENSEX"])

        assert calls == ["NIFTY", "BANKNIFTY", "SENSEX"]
        assert result is True
        assert mock_notify.called
        assert "BANKNIFTY" in mock_notify.call_args.args[1]

    def test_all_symbols_failing_returns_false(self, monkeypatch):
        def fake_process_symbol(token, symbol):
            raise RuntimeError("boom")

        monkeypatch.setattr(srv2, "process_symbol", fake_process_symbol)
        monkeypatch.setattr(srv2, "notify_error", MagicMock())

        result = srv2.run_all_symbols("fake_token", ["NIFTY", "BANKNIFTY"])
        assert result is False
