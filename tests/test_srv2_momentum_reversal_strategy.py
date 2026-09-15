"""
tests/test_srv2_momentum_reversal_strategy.py
--------------------------------------------------------------
srv2_momentum_reversal_strategy.py — वापरकर्त्याने दिलेल्या संपूर्ण blueprint वरून बांधलेली
"Nifty SRv2 Momentum-Filter Reversal" रणनीती — established SRv2 + 0.40% गती-फिल्टर +
established ATM+1/ATM+3 strike-निवड + One-Touch/Cooldown.
"""
from unittest.mock import patch

import datetime

import pandas as pd

import srv2_momentum_reversal_strategy as srv2
from config import get_ist_now


class TestCheckRsiFilter:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Momentum Filter (0.40% स्विंग-हालचाल)
    काढून, established 15-मिनिट RSI(14)-आधारित फिल्टर: Resistance/Bearish साठी RSI>50, established
    Support/Bullish साठी RSI<50."""

    def _rising_df(self, n=30, start=100):
        # established सलग वाढणाऱ्या closes -> established RSI established 50 च्या वर जायला हवा
        closes = [start + i for i in range(n)]
        return pd.DataFrame({"close": closes})

    def _falling_df(self, n=30, start=200):
        closes = [start - i for i in range(n)]
        return pd.DataFrame({"close": closes})

    def test_bullish_passes_when_rsi_below_50(self):
        df = self._falling_df()  # established सलग घसरण -> established RSI established कमी (established <50)
        passed, rsi_value = srv2.check_rsi_filter(df, "BULLISH")
        assert passed is True
        assert rsi_value < 50

    def test_bullish_fails_when_rsi_above_50(self):
        df = self._rising_df()  # established सलग वाढ -> established RSI established जास्त (established >50)
        passed, rsi_value = srv2.check_rsi_filter(df, "BULLISH")
        assert passed is False
        assert rsi_value > 50

    def test_bearish_passes_when_rsi_above_50(self):
        df = self._rising_df()
        passed, rsi_value = srv2.check_rsi_filter(df, "BEARISH")
        assert passed is True
        assert rsi_value > 50

    def test_bearish_fails_when_rsi_below_50(self):
        df = self._falling_df()
        passed, rsi_value = srv2.check_rsi_filter(df, "BEARISH")
        assert passed is False
        assert rsi_value < 50

    def test_insufficient_candles_returns_false(self):
        df = pd.DataFrame({"close": [100, 101, 102]})  # established RSI(14) साठी अपुरा इतिहास
        passed, rsi_value = srv2.check_rsi_filter(df, "BULLISH")
        assert passed is False
        assert rsi_value is None


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
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True) as mock_telegram, \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True) as mock_save:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_telegram.called
            assert mock_save.called
            assert "Bull Put Spread" in result

    def test_multi_hit_max_2_per_level_skips_third(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit, One-Touch ऐवजी) — established
        established level ला आजच established 2 वेळा hit झालेला असेल, तर established 3रा वेळा
        established दुर्लक्षित व्हायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now())), \
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
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
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
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_fixed_strikes", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}) as mock_select, \
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
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(1, get_ist_now())), \
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
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(1, get_ist_now())), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
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
        dates = pd.date_range("2026-09-05 09:15", periods=30, freq="15min")
        # established सलग वाढ, established शेवटी established बरोब्बर established support_level (23900)
        # ला स्पर्श -- established RSI established establishedच्या established उभारीमुळे established >50 असेल.
        rising_closes = [23800 + i * (100 / 29) for i in range(29)] + [23900.0]
        candles_rising = pd.DataFrame({"timestamp": dates, "open": rising_closes, "high": [c + 5 for c in rising_closes],
                                        "low": [c - 5 for c in rising_closes], "close": rising_closes, "volume": 0, "oi": 0})
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_rising), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "open_multi_leg_trade") as mock_trade:
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called

    def test_insufficient_candle_history_handled_gracefully(self):
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_candles", return_value=pd.DataFrame()):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result


class TestProcessSymbolMultiAccount:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा -- established broker_accounts नोंदवलेले असतील तर
    established execute_trade_on_all_accounts() (replicated) वापरायला हवं."""

    def test_uses_multi_account_when_accounts_registered(self):
        import pandas as pd
        candles_df = _fake_candles_df(last_close=23902)
        accounts_df = pd.DataFrame([{"account_id": "A1", "broker_type": "upstox", "nickname": "A", "is_active": True, "lot_multiplier": 1.0}])
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_fixed_strikes", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=accounts_df), \
             patch("trading_engine.execute_trade_on_all_accounts", return_value=([{"account_id": "A1", "ok": True, "result": "OPENED"}], [])) as mock_multi, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True):
            result = srv2.process_symbol("fake_token", "NIFTY")
            assert mock_multi.called
            assert "A1" in result


class TestMultiTimeframe:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — 15M/30M/60M एकत्र, settings-चालित lots/hedge_width,
    Expiry-Day Logic."""

    def test_30m_only_level_still_triggers_entry(self):
        """फक्त 30M level (15M/60M नाहीत) असला, तरी तोही तपासला जाऊन trade व्हायला हवा."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_srv2_settings", return_value={"lots": 1, "hedge_width_points": 100.0}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones_30m_only()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
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
        hardcoded मूल्यांऐवजी प्रत्यक्ष वापरली जायला हवीत."""
        candles_df = _fake_candles_df(last_close=23902)
        with patch.object(srv2.cloud_db, "get_srv2_state", return_value={"last_tested_level": None, "last_sl_hit_time": None}), \
             patch.object(srv2.cloud_db, "get_srv2_settings", return_value={"lots": 3, "hedge_width_points": 75.0}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2, "select_credit_spread_fixed_strikes", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}) as mock_select, \
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
             patch.object(srv2.cloud_db, "get_srv2_settings", return_value={"lots": 1, "hedge_width_points": 100.0}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
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
             patch.object(srv2.cloud_db, "get_srv2_settings", return_value={"lots": 1, "hedge_width_points": 100.0}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
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
             patch.object(srv2.cloud_db, "get_srv2_settings", return_value={"lots": 1, "hedge_width_points": 100.0}), \
             patch.object(srv2, "fetch_candles", return_value=candles_df), \
             patch.object(srv2.cloud_db, "get_market_zones", return_value=_fake_dyn_zones()), \
             patch.object(srv2.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(srv2, "has_open_trade_from_source", return_value=False), \
             patch.object(srv2, "fetch_option_expiries", return_value=["2099-01-01"]), \
             patch.object(srv2, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(srv2.cloud_db, "get_all_broker_accounts", return_value=None), \
             patch.object(srv2, "open_multi_leg_trade", return_value=({"trade_id": "T64"}, "OPENED")) as mock_trade, \
             patch.object(srv2, "send_telegram_message", return_value=True), \
             patch.object(srv2.cloud_db, "save_srv2_state", return_value=True), \
             patch.object(srv2.cloud_db, "save_signal_log", return_value=True):
            srv2.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_args.kwargs.get("entry_level_price") == 23900.0
