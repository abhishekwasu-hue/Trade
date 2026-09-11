"""
tests/test_dynamic_sr_instant_trader.py
------------------------------------------------
dynamic_sr_instant_trader.py — वापरकर्त्याशी चर्चा करून बांधलेली, वाढीव High-Frequency 1-मिनिट S/R
रणनीती. Chart वर दाखवला जाणारा Dynamic S/R — 1-मिनिट candles च्या [low,high] रेंज मधून, किंवा
candles मधल्या gap मधून (Gap Up/Down वापरकर्त्याने विचारलेला प्रश्न), level cross झाला की तात्काळ
PAPER trade + zone mitigation + Telegram + **संपूर्ण Signal Log** (hit झाला किंवा नाही तरीही).
"""
import datetime
from unittest.mock import patch

import pandas as pd

import dynamic_sr_instant_trader as dsr
from config import get_ist_now


class TestCheckLevelCrossed:
    """🎓 established 'फक्त सद्य LTP जवळ आहे का' या ऐवजी, candle-range + gap-through दोन्ही तपासणे."""

    def test_direct_touch_within_candle_range(self):
        candles = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24008, "low": 23895, "close": 23900},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is True
        assert hit_type == "TOUCH"
        assert price == 23900

    def test_gap_down_crosses_level_without_touching(self):
        """🎓 वापरकर्त्याने विचारलेला Gap Down प्रश्न -- level ला कुठलाच candle स्पर्श करत नाही,
        पण दोन candles मधल्या gap मध्ये level सापडतो, म्हणजे उडी मारून ओलांडला गेला."""
        candles = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is True
        assert hit_type == "GAP_THROUGH"
        assert price == 23750

    def test_gap_up_crosses_level_without_touching(self):
        candles = [
            {"open": 23800, "high": 23810, "low": 23790, "close": 23800},
            {"open": 24050, "high": 24080, "low": 24040, "close": 24060},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is True
        assert hit_type == "GAP_THROUGH"
        assert price == 24050

    def test_no_hit_when_price_never_near_level(self):
        candles = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24008, "low": 23995, "close": 24000},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is False
        assert hit_type is None

    def test_near_miss_within_buffer_counts_as_touch(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेला बफर (±0.02%) — candle ने level ला तंतोतंत स्पर्श केला
        नसला, तरी त्याच्या 0.02% च्या आत असेल तर established TOUCH established धरला जावा."""
        level = 24000.0
        buffer = level * 0.02 / 100  # = 4.8
        candles = [
            {"open": 24010, "high": 24015, "low": 24010, "close": 24012},
            # established candle चा high (level - buffer + 1) -- established बफरच्या आतच, established
            # established प्रत्यक्ष level ला स्पर्श establishedच केलेला नाही
            {"open": level - buffer - 5, "high": level - buffer + 1, "low": level - buffer - 8, "close": level - buffer - 2},
        ]
        hit, hit_type, price = dsr.check_level_crossed(level, candles)
        assert hit is True
        assert hit_type == "TOUCH"

    def test_stale_old_candle_in_10min_window_should_not_report_touch_if_only_last_2_checked(self):
        """🎓 वापरकर्त्याने Signal Log मधून सापडवलेली, खरी bug — 7-8 मिनिटांपूर्वीचा candle level ला
        स्पर्श करत होता, पण किंमत आता खूप दूर गेलीये. जुना recent_candles_count=10 वापरला असता, तर
        हा जुना candle अजूनही यादीत राहून खोटा TOUCH दाखवायचा. आता process_symbol() फक्त शेवटचे 2
        candles (recent_candles_count=2, नवीन डीफॉल्ट) वापरतो — म्हणजे हा जुना candle कधीच तपासलाच
        जात नाही, आणि योग्यरित्या NO_HIT मिळतो."""
        level = 23448.8
        # 8 मिनिटांपूर्वीचा candle -- level ला खरंच स्पर्श करत होता
        stale_touch_candle = {"open": 23450, "high": 23452, "low": 23447, "close": 23449}
        # शेवटचे 2 candles -- किंमत आता level पासून खूप दूर (~190 पॉइंट्स)
        recent_far_candles = [
            {"open": 23260, "high": 23262, "low": 23258, "close": 23261},
            {"open": 23252, "high": 23254, "low": 23249, "close": 23251.7},
        ]
        full_10min_window = [stale_touch_candle] + [
            {"open": 23300, "high": 23302, "low": 23298, "close": 23300}
        ] * 7 + recent_far_candles

        # established जुनी (bug असलेली) पद्धत -- संपूर्ण 10-candle विंडो दिली, तर खोटा TOUCH मिळायचा
        old_buggy_hit, _, _ = dsr.check_level_crossed(level, full_10min_window)
        assert old_buggy_hit is True  # हेच जुनं, चुकीचं वर्तन होतं

        # established नवीन (फिक्स केलेली) पद्धत -- फक्त शेवटचे 2 candles दिले, तर बरोबर NO_HIT
        new_correct_hit, _, _ = dsr.check_level_crossed(level, full_10min_window[-2:])
        assert new_correct_hit is False

    def test_beyond_buffer_still_no_hit(self):
        """बफर असला तरी त्याच्याही पलीकडे (खूप दूर) असलेला candle अजूनही NO_HIT च असायला हवं."""
        level = 24000.0
        candles = [
            {"open": 23980, "high": 23990, "low": 23975, "close": 23985},  # level पासून बरंच दूर
        ]
        hit, hit_type, price = dsr.check_level_crossed(level, candles)
        assert hit is False


def _fake_zones():
    return pd.DataFrame([
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": 23900.0, "zone_high": 23900.0,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_1M", "zone_low": 24500.0, "zone_high": 24500.0,
         "strength": 2.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


def _candles_with_rsi(touch_rows, declining=True):
    """RSI(14) साठी किमान 15 candles लागतात. touch_rows (शेवटचे, टच घडवणारे) च्या आधी घसरणारा
    (declining=True, Support/BULLISH साठी RSI<40) किंवा चढणारा (declining=False, Resistance/BEARISH
    साठी RSI>60) trend prepend करतो.

    🎓 वापरकर्त्याने सापडवलेली bug (lookback_days=1 मुळे कालचे candles मिसळणे) फिक्स केल्यानंतर —
    process_symbol() आता candles_df["timestamp"] वापरून आजचाच दिवस फिल्टर करतो, त्यामुळे सर्व test
    fixtures ना आता timestamp column (आजच्याच, test चालतानाच्या खऱ्या तारखेसह) हवा."""
    n = 25
    if declining:
        trend = [{"open": 24200 - i * 10, "high": 24210 - i * 10, "low": 24190 - i * 10, "close": 24195 - i * 10} for i in range(n)]
    else:
        trend = [{"open": 23600 + i * 10, "high": 23610 + i * 10, "low": 23590 + i * 10, "close": 23605 + i * 10} for i in range(n)]
    all_rows = trend + touch_rows
    # 🎓 pd.Timestamp.now() सर्व्हरच्या local (शक्यतो UTC) वेळेवर अवलंबून असतो — production code च्या
    # get_ist_now() शी दिवस-सीमेवर (विशेषतः संध्याकाळी UTC नुसार) न जुळण्याचा धोका आहे, म्हणून तेच
    # (dsr.get_ist_now, जेणेकरून mock केल्यास दोन्ही ठिकाणी तीच वेळ वापरली जाईल) वापरून सुसंगत ठेवतो.
    today_ist = dsr.get_ist_now().replace(hour=10, minute=0, second=0, microsecond=0)
    timestamps = pd.date_range(end=today_ist, periods=len(all_rows), freq="1min")
    df = pd.DataFrame(all_rows)
    df["timestamp"] = timestamps
    return df


def _fake_chain(spot):
    return [{"underlying_spot_price": spot, "strike_price": 24000, "expiry": "2026-09-10",
             "call_options": {"instrument_key": "CE1", "market_data": {"ltp": 50}, "option_greeks": {}},
             "put_options": {"instrument_key": "PE1", "market_data": {"ltp": 45}, "option_greeks": {}}}]


class TestProcessSymbol:
    def test_gap_through_executes_trade_and_logs_all_levels(self):
        """🎓 वापरकर्त्याने विचारलेला Gap Down प्रश्न + मागितलेला संपूर्ण Signal Log -- दोन्ही एकत्र."""
        candles_gap = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_gap), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23780.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True) as mock_telegram, \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "GAP_THROUGH" in result
            assert mock_trade.called
            assert mock_telegram.called
            # 🎓 दोन्ही levels (एक hit, एक no-hit) साठी log व्हायलाच हवं -- संपूर्ण Signal Log
            assert mock_log.call_count == 2
            logged_types = [c.args[0]["hit_type"] for c in mock_log.call_args_list]
            assert "GAP_THROUGH" in logged_types
            assert "NO_HIT" in logged_types

    def test_short_leg_selected_at_atm_not_otm(self):
        """🎓 वापरकर्त्याशी चर्चा करून सुधारित — Short leg आता ATM वरच (strikes_otm=0, आधी डीफॉल्ट
        ATM±2 होतं) — established SRv2 (ATM±1) शी strike-collision चा धोकाही यामुळे कमी होतो."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_select.called
            assert mock_select.call_args.kwargs.get("strikes_otm") == 0

    def test_direct_touch_executes_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "TOUCH" in result

    def test_yesterdays_candle_never_causes_false_touch_at_market_open(self):
        """🎓 वापरकर्त्याने सापडवलेली, खरी bug (केवळ candle-window छोटा करून सुटणारी नाही) —
        fetch_candles(..., lookback_days=1) कालच्या दिवसाचे शेवटचे candles सुद्धा (आजच्या सोबतच)
        परत करतो. बाजार उघडून अगदी काही मिनिटंच झालेली असताना, जुना कोड आपोआप कालचा (gap-पूर्वीचा)
        candle घ्यायचा — आणि आज बाजारात कधीच न आलेल्या किमतीवर खोटा TOUCH दाखवायचा. आता
        candles_df["timestamp"] वरून आजचाच दिवस आधी फिल्टर करतो, त्यामुळे कालचा candle कधीच
        या तपासणीत येतच नाही."""
        today_ist = get_ist_now()
        yesterday_ist = today_ist - datetime.timedelta(days=1)

        # कालचे 25 candles (RSI(14) साठी पुरेसा इतिहास) — यातला शेवटचा level (23448.8) ला
        # प्रत्यक्ष स्पर्श करतो (जुन्या कोड मध्ये हाच candle खोटा TOUCH दाखवायचा)
        yesterdays_candles = [
            {"timestamp": yesterday_ist.replace(hour=15, minute=max(0, i)), "open": 23450, "high": 23452, "low": 23447, "close": 23449}
            for i in range(1, 26)
        ]
        # आजचा पहिलाच candle — level पासून खूप दूर (मोठा gap-down)
        todays_first_candle = {"timestamp": today_ist.replace(hour=9, minute=15, second=0, microsecond=0), "open": 23260, "high": 23262, "low": 23258, "close": 23261}

        candles_df = pd.DataFrame(yesterdays_candles + [todays_first_candle])

        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=candles_df), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23261.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert "cross झाला नाही" in result  # आजचा candle level पासून दूर -- खरा NO_HIT, कालच्या candle चा प्रभाव नाही

    def test_no_hit_logs_but_does_not_trade(self):
        candles_no_hit = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24008, "low": 23995, "close": 24000},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=candles_no_hit), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(24000.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called  # तरीही log व्हायलाच हवं
            assert "cross झाला नाही" in result

    def test_zone_stays_active_after_hit_not_filled(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit) — established आता cross झाल्यावरही
        zone कायमचं FILLED होत नाही (जुनं वर्तन) — save_market_zones() ला कॉलच होत नाही, कारण
        gating आता established hit_count/cooldown (signal_log वरून) वरून होते, zone-status वरून नाही."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(dsr.cloud_db, "save_market_zones") as mock_save:
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_save.called


class TestMultiHitGating:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established एकाच zone ला दिवसातून जास्तीत जास्त
    २ वेळा trade करता येतो, established अटींसह: (अ) established आधीच्या hit पासून किमान ३० मिनिटांचं
    अंतर (cooldown), (ब) established आधीची position आधीच बंद (CLOSED) झालेली असावी."""

    def _touch_setup(self):
        touch_rows = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ]
        return _candles_with_rsi(touch_rows, declining=True)  # 🎓 Support/BULLISH -> RSI<40 हवा

    def test_no_new_entry_after_1445(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — 14:45 नंतर नवीन entry घ्यायचीच नाही."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 14, 50, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_TOO_LATE_FOR_NEW_ENTRY" in statuses

    def test_entry_allowed_just_before_1445(self):
        """14:44 ला (कटऑफच्या आधी), entry नेहमीसारखीच व्हायला हवी."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 14, 44, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T40"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_first_hit_of_the_day_trades_normally(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_third_hit_of_day_skipped_max_2_reached(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr, "send_telegram_message") as mock_telegram, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now())):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert not mock_telegram.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_second_hit_within_30min_cooldown_skipped(self):
        recent_hit_time = get_ist_now() - datetime.timedelta(minutes=10)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, recent_hit_time)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_COOLDOWN_30MIN" in statuses

    def test_second_hit_after_30min_but_previous_position_still_open_skipped(self):
        old_hit_time = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=45)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, old_hit_time)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_first_hit_of_level_still_skipped_if_any_other_position_open(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुधारणा — वापरकर्त्याने Order Log मधून
        सापडवलेली bug — established आधी ही तपासणी फक्त hit_count_so_far>=1 (म्हणजे "याच specific
        level ला आज दुसऱ्यांदा hit") असेल तरच चालायची. म्हणजे established एका वेगळ्या level वर आधीच
        उघडी असलेली position असतानाही, established दुसऱ्या (आजचा पहिलाच hit, hit_count_so_far=0)
        level वर established नवीन trade उघडली जायची. आता established कुठल्याही level साठी, established
        हा check बिनशर्त — established position उघडी असेल तर established कुठलाही (नवा असो वा जुना)
        level असो, entry होणारच नाही."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_second_hit_after_30min_and_previous_closed_trades_again(self):
        old_hit_time = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=45)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T2"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, old_hit_time)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=False):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_no_active_zones_handled_gracefully(self):
        empty_zones = pd.DataFrame(columns=["symbol", "zone_type", "zone_low", "zone_high", "strength", "formed_date", "status"])
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=empty_zones):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result or "नाहीत" in result

    def test_none_from_supabase_handled_gracefully(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=None):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result or "नाहीत" in result

    def test_no_candles_handled_gracefully(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=pd.DataFrame()):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "मिळाले नाहीत" in result


class TestProcessSymbolMultiAccount:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा -- established broker_accounts नोंदवलेले असतील तर
    established execute_trade_on_all_accounts() (replicated) वापरायला हवं."""

    def test_uses_multi_account_when_accounts_registered(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True)
        accounts_df = pd.DataFrame([{"account_id": "A1", "broker_type": "upstox", "nickname": "A", "is_active": True, "lot_multiplier": 1.0}])
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(dsr.cloud_db, "get_all_broker_accounts", return_value=accounts_df), \
             patch("trading_engine.execute_trade_on_all_accounts", return_value=([{"account_id": "A1", "ok": True, "result": "OPENED"}], [])) as mock_multi, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert mock_multi.called
            assert "A1" in result


class TestInstantRsiFilter:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेला RSI फिल्टर — Support touch + RSI<40 -> Bull Put Spread,
    Resistance touch + RSI>60 -> Bear Call Spread."""

    def test_bullish_passes_with_low_rsi(self):
        df = _candles_with_rsi([], declining=True)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BULLISH")
        assert passed is True
        assert rsi_value < 40

    def test_bullish_fails_with_high_rsi(self):
        df = _candles_with_rsi([], declining=False)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BULLISH")
        assert passed is False
        assert rsi_value > 60

    def test_bearish_passes_with_high_rsi(self):
        df = _candles_with_rsi([], declining=False)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BEARISH")
        assert passed is True
        assert rsi_value > 60

    def test_bearish_fails_with_low_rsi(self):
        df = _candles_with_rsi([], declining=True)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BEARISH")
        assert passed is False
        assert rsi_value < 40

    def test_entry_skipped_when_rsi_wrong_direction(self):
        """🎓 गाभा टेस्ट — Support ला स्पर्श झाला, पण RSI established जास्त (established चढता trend)
        असल्यामुळे established entry established दुर्लक्षित व्हायला हवी."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=False)  # established establishedच्या establishedउलट established दिशा
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_RSI_FILTER" in statuses

