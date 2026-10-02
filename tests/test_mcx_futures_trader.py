"""
tests/test_mcx_futures_trader.py
--------------------------------------------------------------
mcx_futures_trader.py — MCX Futures Trader (CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER). srv2_momentum_
reversal_strategy.py च्या TestProcessSymbol/TestMultiTimeframe/TestProcessSymbolMultiAccount च्याच
mocking पॅटर्नचं अनुकरण — पण options ऐवजी एकाच futures leg वर लक्ष केंद्रित (strike/premium/hedge
गणित नाही, फक्त sl_points/target_points सरळ max_loss/max_profit म्हणून पास होतात का, आणि दिशेनुसार
BUY/SELL बरोबर ठरतं का, हेच सर्वात जास्त धोक्याचं — म्हणून सर्वात कसून तपासलेलं).
"""
from unittest.mock import MagicMock, patch

import pytest

import pandas as pd

import cloud_db
import mcx_futures_trader as mft


def _fake_candles_df(n=20, last_close=6500.0, closes=None):
    """closes दिलं तर तेच वापरलं जातं (n/last_close दुर्लक्षित) -- hysteresis-संवेदनशील टेस्ट्ससाठी
    (उदा. test_bearish_touch_places_sell) आजची संपूर्ण candle-मालिका नियंत्रित करायला हवी असते."""
    end_ts = mft.get_ist_now().replace(hour=15, minute=15, second=0, microsecond=0)
    if closes is None:
        closes = [6600.0 - i for i in range(n - 1)] + [last_close]
    dates = pd.date_range(end=end_ts, periods=len(closes), freq="30min")
    return pd.DataFrame({"timestamp": dates, "open": closes, "high": [c + 5 for c in closes],
                          "low": [c - 5 for c in closes], "close": closes, "volume": 0, "oi": 0})


def _fake_zones(support_level=6500.0, suffix="30M"):
    return pd.DataFrame([
        {"symbol": "CRUDEOIL", "zone_type": f"DYNAMIC_SR_SUPPORT_{suffix}", "zone_low": support_level,
         "zone_high": support_level, "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


def _fake_resolved(instrument_key="MCX_FO|12345", lot_size=100):
    return True, {
        "symbol": "CRUDEOIL", "trading_symbol": "CRUDEOIL26SEPFUT", "instrument_key": instrument_key,
        "lot_size": lot_size, "tick_size": 1.0, "expiry": "2026-09-30", "freeze_quantity": 1000,
        "all_upcoming_expiries": ["2026-09-30"],
    }


# Min-Hold गेट डीफॉल्ट चालू आहे (बघा TestMinHoldGate::test_enabled_by_default) -- बाकी टेस्ट्स आपापल्या विषयावरच लक्ष ठेवतात,
# म्हणून इथे तो बंद; TestMinHoldGate मध्ये तो स्पष्टपणे चालू केला जातो.
_DEFAULT_SETTINGS = {**cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"], "entry_min_hold_gate_enabled": False}


class TestDetermineDirectionWithHysteresis:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py/srv2_momentum_reversal_
    strategy.py मधलीच hysteresis पद्धत इथेही. वापरकर्त्याने पुढे स्पष्टपणे MCX साठी वेगळा, रुंद
    buffer मागितला — 1% (srv2 च्या 0.015% पेक्षा रुंद — commodities च्या मोठ्या हालचालींसाठी)."""

    LEVEL = 6500.0  # buffer(1%) = ±65

    def test_sticky_bullish_when_dip_stays_within_buffer(self):
        closes = [6600.0, 6450.0]  # 6450 < level(6500) पण lower buffer (6435) च्या वरच
        assert mft.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_flips_to_bearish_only_when_clearly_beyond_buffer(self):
        closes = [6600.0, 6400.0]  # lower buffer (6435) च्या स्पष्टपणे खाली -- खरा breakdown
        assert mft.determine_direction_with_hysteresis(self.LEVEL, closes) == "BEARISH"

    def test_falls_back_to_raw_comparison_when_never_left_band(self):
        closes = [6500.0]  # बरोबर level वरच, buffer बाहेर कधीच नाही
        assert mft.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_real_world_scenario_stays_bullish_through_momentary_dip(self):
        closes = [6600.0, 6520.0, 6450.0, 6510.0]  # सगळेच buffer (6435-6565) च्या आत/वर
        for i in range(1, len(closes) + 1):
            assert mft.determine_direction_with_hysteresis(self.LEVEL, closes[:i]) == "BULLISH"


class TestProcessSymbolGates:
    def test_symbol_disabled_returns_early(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = False
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol") as mock_resolve:
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert "बंद आहे" in result
            assert not mock_resolve.called

    def test_resolve_symbol_failure_returns_early(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=(False, "काहीच सापडलं नाही")):
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert "सापडला नाही" in result

    def test_no_zones_returns_early(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=pd.DataFrame()):
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert "zones सापडले नाहीत" in result

    def test_no_touch_saves_no_hit_signal_log(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        candles_df = _fake_candles_df(last_close=7500.0)  # level (6500) पासून खूप दूर -- touch नाही
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert "पात्र ठरला नाही" in result
            assert mock_log.called
            assert mock_log.call_args.args[0]["hit_type"] == "NO_HIT"
            assert not mock_trade.called

    def test_touch_tolerance_widened_to_0_10_pct(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा — entry touch-buffer 0.05% वरून 0.10% केला. level=6500
        पासून 5 पॉइंट्स दूर (जुन्या 0.05% बफर — ~3.25 पॉइंट्स — च्या बाहेर, पण नव्या 0.10% — ~6.5
        पॉइंट्स — च्या आतच) — आता हा TOUCH म्हणून मोजायला हवा."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        candles_df = _fake_candles_df(last_close=6505.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")):
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_log.call_args.args[0]["hit_type"] == "TOUCH"

    def test_touch_tolerance_still_excludes_beyond_0_10_pct(self):
        """level=6500 पासून 7 पॉइंट्स दूर — नव्या 0.10% बफर (~6.5 पॉइंट्स) च्याही बाहेर — अजूनही
        NO_HIT च राहायला हवं (buffer अमर्याद रुंद झालेला नाही)."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        candles_df = _fake_candles_df(last_close=6507.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_log.call_args.args[0]["hit_type"] == "NO_HIT"

    def test_rsi_gate_blocks_entry(self):
        """किंमत level (6500) च्या वरच आहे -> BULLISH -> RSI support_max पेक्षा कमी हवा. सलग
        वाढणाऱ्या closes मुळे RSI जास्त असेल -> गेटने अडवायला हवं."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = True
        # 🎓 MCX साठी hysteresis buffer 1% (वापरकर्त्याने मागितल्याप्रमाणे, srv2 च्या 0.015% पेक्षा
        # रुंद — commodities च्या मोठ्या हालचालींसाठी) — त्यामुळे ±65 पॉइंट्सचा बँड, संपूर्ण उभारीचा
        # आवाका (range) त्याच्या आतच असेल असं धरलं, म्हणजे hysteresis बँडबाहेर कधीच जात नाही आणि
        # raw तुलनेचाच (जुनं वर्तन, BULLISH) safe fallback वापरला जातो.
        rising_closes = [6450.0 + i * 2.5 for i in range(20)]
        end_ts = mft.get_ist_now().replace(hour=15, minute=15, second=0, microsecond=0)
        candles_df = pd.DataFrame({
            "timestamp": pd.date_range(end=end_ts, periods=20, freq="30min"),
            "open": rising_closes, "high": [c + 5 for c in rising_closes],
            "low": [c - 5 for c in rising_closes], "close": rising_closes, "volume": 0, "oi": 0,
        })
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=rising_closes[-1] - 1)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            logged_statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_RSI_FILTER" in logged_statuses

    def test_get_zone_hits_today_called_with_role_from_level_type(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेला role-split max-2 counter — last_close==support_level
        त्यामुळे level_type="SUPPORT" ठरतो (current_price >= level_price), तोच role पास व्हायला हवा."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)) as mock_hits, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")):
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_hits.called
            assert mock_hits.call_args.kwargs.get("role") == "SUPPORT"

    def test_max_2_hits_blocks_entry(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(2, mft.get_ist_now(), mft.get_ist_now())), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            logged_statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in logged_statuses

    def test_max_hits_per_zone_configurable_higher_limit_allows_third_hit(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — max_hits_per_zone आता डॅशबोर्डवरून
        बदलता येतो. इथे तो ३ ठेवला आहे, त्यामुळे hit_count_so_far=2 असतानाही trade घ्यायला हवा."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["max_hits_per_zone"] = 3
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(2, mft.get_ist_now(), mft.get_ist_now())), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called

    def test_max_hits_per_zone_configurable_lower_limit_skips_second_hit(self):
        """🎓 max_hits_per_zone=1 ठेवल्यावर, डीफॉल्ट-२ लॉजिकमध्ये परवानगी असलेला दुसरा hit
        (hit_count_so_far=1) सुद्धा आता नाकारला जायला हवा."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["max_hits_per_zone"] = 1
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(1, mft.get_ist_now(), mft.get_ist_now())), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            logged_statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in logged_statuses

    def test_previous_open_position_blocks_entry(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            logged_statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in logged_statuses


class TestProcessSymbolEntry:
    def test_bullish_touch_places_buy_with_correct_strategy_result(self):
        """किंमत level च्या वर/बरोबर -> BULLISH -> BUY. strike हा दिखाव्यापुरता 0 (trading_engine.py
        च्या strikes_summary format-string साठी, त्या shared फाईलला अजिबात हात न लावता), max_loss/
        max_profit सरळ sl_points/target_points, net_credit ऋण (BUY = debit)."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["sl_points"] = 20.0
        settings["target_points"] = 40.0
        settings["lots"] = 2
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved(lot_size=100)), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True) as mock_telegram, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called
            assert mock_telegram.called
            kwargs = mock_trade.call_args.kwargs
            strategy_result = mock_trade.call_args.args[2]
            assert strategy_result["legs"][0]["transaction_type"] == "BUY"
            assert strategy_result["legs"][0]["strike"] == 0
            assert strategy_result["legs"][0]["instrument_key"] == "MCX_FO|12345"
            assert strategy_result["max_loss"] == 20.0
            assert strategy_result["max_profit"] == 40.0
            assert strategy_result["net_credit"] < 0  # BUY = debit = ऋण
            assert kwargs["sl_pct_of_max_loss"] == 100
            assert kwargs["target_pct_of_max_profit"] == 100
            assert kwargs["source"] == "mcx_futures"
            assert kwargs["lots"] == 2
            assert kwargs["lot_size"] == 100
            assert kwargs["trading_mode"] == "PAPER"
            assert "BUY" in result

    def test_bearish_touch_places_sell(self):
        """किंमत level च्या खाली -> BEARISH -> SELL, net_credit धन (SELL = credit)."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        # 🎓 MCX चा 1% hysteresis buffer (~64 पॉइंट्स इथे) — _fake_candles_df() चा जुना सपाट-सदृश
        # आकार (6600 पासून हळूहळू घसरत) buffer च्या वर राहतो, त्यामुळे इथे स्वतंत्र fixture — किंमत
        # आधीपासूनच स्पष्टपणे lower buffer (6337.98) च्या खाली (6300) राहून, शेवटीच level ला स्पर्श
        # (6400) — खरा Resistance test from below.
        candles_df = _fake_candles_df(closes=[6300.0] * 19 + [6400.0])  # level पेक्षा किंचित कमी, पण touch-tolerance च्या आत
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6402.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            mft.process_symbol("fake_token", "CRUDEOIL")
            strategy_result = mock_trade.call_args.args[2]
            assert strategy_result["legs"][0]["transaction_type"] == "SELL"
            assert strategy_result["net_credit"] > 0

    def test_timeframe_choice_30m_ignores_60m_zones(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["timeframe_choice"] = "30M"
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0, suffix="60M")), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft, "open_multi_leg_trade") as mock_trade, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            assert "कुठलेही ACTIVE Dynamic S/R levels" in result


def _hits_side_effect(support_hits=0, resistance_hits=0):
    """cloud_db.get_zone_hits_today() साठी role-अवलंबून fake -- MCX मध्ये role हा स्थिर
    zone_type column नाही, प्रत्येक cycle ला hysteresis-दिशेवरून ताजा काढला जातो, त्यामुळे
    SUPPORT/RESISTANCE दोन्ही role साठी स्वतंत्र hit-count देता यायला हवा."""
    def _fake(symbol, level_price, trade_date, role=None):
        if role == "SUPPORT":
            return (support_hits, None, None)
        return (resistance_hits, None, None)
    return _fake


class TestMcxBreakoutEntry:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Mcx comodity sathi suddha he feature add kra,
    Breakout buildup waril A and C mix logic") — dynamic_sr_instant_trader.py (NIFTY) मधलाच
    Breakout Entry आता MCX Futures साठीही. मूळ level (support, 6500) — support तुटून BEARISH
    breakout झाला तर SELL.

    🎓 MCX-विशिष्ट फरक (महत्त्वाचा) — role (level_type) हा स्थिर zone_type column नाही, प्रत्येक
    cycle ला त्याच candidate च्या hysteresis-दिशेवरूनच ताजा काढला जातो. त्यामुळे खरा breakout
    घडलाच असेल, तर hysteresis आधीच (नैसर्गिकपणे) नव्या दिशेकडे वळलेला असतो -- वेगळी flip-logic
    लागत नाही. "buildup" साठी उलट role (opposite_role) कडे आधीच 2 hits झालेले आहेत का, हे
    तपासलं जातं (support तुटला -> मूळ 2 touches "SUPPORT" role खालीच नोंदलेले असतील)."""

    LEVEL = 6500.0
    # 12 candles (30-मिनिट, 1 तास... प्रत्यक्षात 6 तास कारण डीफॉल्ट lookback=12) -- सगळे ±0.30%
    # (≈19.5 points) च्या आत
    CONSOLIDATED_WINDOW = [
        6495.0, 6505.0, 6498.0, 6502.0, 6490.0, 6500.0,
        6485.0, 6510.0, 6497.0, 6503.0, 6490.0, 6500.0,
    ]
    NOT_CONSOLIDATED_WINDOW = [
        6495.0, 6505.0, 6498.0, 6502.0, 6490.0, 6500.0,
        6485.0, 6300.0, 6497.0, 6503.0, 6490.0, 6500.0,
    ]  # 6300 बाहेर

    def _breakout_settings(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["entry_breakout_gate_enabled"] = True
        return settings

    def _candles(self, window, final_close):
        return _fake_candles_df(closes=window + [final_close])

    def test_disabled_by_default_stays_no_hit(self):
        """डीफॉल्ट settings मध्ये entry_breakout_gate_enabled=False -- सद्य किंमत level पासून दूर
        (breakout candle) असल्याने साधी proximity-आधारित touch-तपासणीही अयशस्वी -- established
        NO_HIT वर्तन (max-2-hits skip नाही, कारण तो touch च आढळला नाही)."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)) as mock_hits, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            hit_types = [c.args[0]["hit_type"] for c in mock_log.call_args_list]
            assert "NO_HIT" in hit_types
            # गेट बंद असल्याने opposite-role साठी दुसरी query अजिबात व्हायला नको
            assert mock_hits.call_count == 1

    def test_enabled_but_opposite_role_not_yet_hit_twice_stays_no_hit(self):
        settings = self._breakout_settings()
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=1)), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            hit_types = [c.args[0]["hit_type"] for c in mock_log.call_args_list]
            assert "NO_HIT" in hit_types

    def test_enabled_but_no_consolidation_stays_no_hit(self):
        settings = self._breakout_settings()
        candles_df = self._candles(self.NOT_CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            hit_types = [c.args[0]["hit_type"] for c in mock_log.call_args_list]
            assert "NO_HIT" in hit_types

    def test_consolidated_but_candle_not_closed_beyond_falls_through_to_max_2_hits(self):
        """Consolidation + opposite-role 2 hits दोन्ही खरे, पण शेवटचा candle level च्या पलीकडे
        निर्णायकपणे close झाला नाही (नेमकं level वरच) -- breakout confirm नाही. सध्याचा role
        (SUPPORT, कारण हा candle अजूनही raw तुलनेत level>=असल्याने BULLISH ठरतो) कडेही आधीच 2
        hits (max-2-hits) -- म्हणून established SKIPPED_MAX_2_HITS_REACHED."""
        settings = self._breakout_settings()
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, self.LEVEL)  # शेवटचा close नेमकं level वरच
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2, resistance_hits=2)), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(mft, "open_multi_leg_trade") as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_breakout_confirmed_fires_sell_and_skips_rsi_gate(self):
        settings = self._breakout_settings()
        settings["entry_rsi_gate_enabled"] = True  # मुद्दामच चालू -- तरी breakout trade साठी वगळला जायलाच हवा
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)  # निर्णायकपणे level (6500) च्या खाली
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T50"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True) as mock_telegram, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called
            assert not mock_rsi_gate.called
            strategy_result = mock_trade.call_args.args[2]
            # support तुटला (6500) -> breakout दिशा BEARISH -> SELL
            assert strategy_result["legs"][0]["transaction_type"] == "SELL"
            assert "SELL" in result
            entries = [c.args[0] for c in mock_log.call_args_list]
            breakout_entries = [e for e in entries if "Breakout Entry" in (e.get("reason") or "")]
            assert len(breakout_entries) == 1
            assert breakout_entries[0]["hit_type"] == "TOUCH"
            assert mock_telegram.called
            assert "Breakout Entry" in mock_telegram.call_args.args[0]

    def test_breakout_is_exempt_from_min_hold_gate(self):
        """Breakout म्हणजे किंमत level पासून दूर -- 'टिकली का' मोजलं तर नेहमी 0; म्हणून Min-Hold गेट breakout ला लागू नाही (1-मिनिट fetch सुद्धा नाही)."""
        settings = self._breakout_settings()
        settings["entry_min_hold_gate_enabled"] = True
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft, "fetch_mcx_todays_1m_candles", return_value=[{"low": 6290.0, "high": 6310.0}]) as mock_1m, \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T51"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called and not mock_1m.called

    def test_candle_close_confirmation_uses_no_buffer_not_nifty_default(self):
        """🎓 code-review द्वारे सापडवलेली bug — dynamic_sr_instant_trader.py मधल्या NIFTY-विशिष्ट
        "5 minute candle close Breakout beyond 0.010%" सुधारणेने check_breakout_candle_close() ला
        buffer_pct=0.010 (डीफॉल्ट) दिला — MCX साठी हे कधीच मागितलं/तपासलं गेलं नव्हतं, तरीही इथून
        buffer_pct न दिल्याने शांतपणे लागू झालं असतं. आता स्पष्टपणे buffer_pct=0.0 दिलेला आहे --
        हा टेस्ट तेच लॉक करतो (call बरोबर argument सह होतो)."""
        settings = self._breakout_settings()
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)), \
             patch.object(mft, "check_breakout_candle_close", wraps=mft.check_breakout_candle_close) as mock_close_check, \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T51"}, "OPENED")) as mock_trade:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called
            assert mock_close_check.called
            assert mock_close_check.call_args.kwargs.get("buffer_pct") == 0.0

    def test_breakout_trade_still_blocked_when_position_already_open(self):
        """established has_open_trade_from_source() सुरक्षा-तपासणी breakout trade लाही लागू व्हायला
        हवी."""
        settings = self._breakout_settings()
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)), \
             patch.object(mft, "has_open_trade_from_source", return_value=True), \
             patch.object(mft, "open_multi_leg_trade") as mock_trade, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_uses_settings_lookback_and_tolerance(self):
        """breakout_lookback_candles/breakout_tolerance_pct Dashboard settings वरून घेतले जायला
        हवेत (hardcoded नाही)."""
        settings = self._breakout_settings()
        settings["breakout_lookback_candles"] = 2
        settings["breakout_tolerance_pct"] = 0.20  # शेवटचे 2 (6490, 6500 -- 10 पॉइंट्स आत) च्या आत, पण 0.05% (3.25 पॉइंट्स) च्या बाहेर
        candles_df = self._candles(self.CONSOLIDATED_WINDOW, 6300.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", side_effect=_hits_side_effect(support_hits=2)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T51"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called


class TestBullishBearishEntryToggle:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
    सुद्धा पाहिजे") — इतर सर्व gates च्याही आधी — फक्त नवीन trades थांबतात."""

    def _bearish_candles(self):
        """level=6500 (support, _fake_zones डीफॉल्ट) -- स्पष्टपणे lower buffer (1%, 6435) च्या खाली
        जाऊन, शेवटी बरोब्बर level ला स्पर्श -- hysteresis दिशा BEARISH ठरवते."""
        return _fake_candles_df(closes=[6600.0] * 17 + [6400.0, 6498.0])

    def test_bullish_entry_disabled_skips_bullish_touch(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["bullish_entry_enabled"] = False
        candles_df = _fake_candles_df(last_close=6500.0)  # BULLISH (support test from above)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "open_multi_leg_trade") as mock_trade, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_BULLISH_ENTRY_DISABLED" in statuses

    def test_bearish_entry_disabled_skips_bearish_touch(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["bearish_entry_enabled"] = False
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=self._bearish_candles()), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "open_multi_leg_trade") as mock_trade, \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log:
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_BEARISH_ENTRY_DISABLED" in statuses

    def test_defaults_both_enabled_allows_trade(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_trade.called


class TestPercentMode:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("SL/Target/Trailing SL also on percentage, add other
    gate") — Points सोबतच Percentage mode. entry/सद्य किंमतीवरून points-समतुल्य आकडा काढून
    trading_engine ला (जो mode बद्दल काहीच जाणत नाही) नेहमीच points दिले जातात, हेच इथे तपासायचं."""

    def test_percent_mode_converts_sl_target_to_points_using_entry_price(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["sl_target_mode"] = "PERCENT"
        settings["sl_pct"] = 2.0
        settings["target_pct"] = 4.0
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            mft.process_symbol("fake_token", "CRUDEOIL")
            strategy_result = mock_trade.call_args.args[2]
            # entry ≈ 6500 (last candle close) -> SL 2% ≈ 130, Target 4% ≈ 260
            assert abs(strategy_result["max_loss"] - 6500.0 * 0.02) < 1.0
            assert abs(strategy_result["max_profit"] - 6500.0 * 0.04) < 1.0

    def test_points_mode_unaffected_by_percent_settings(self):
        """sl_target_mode="POINTS" (डीफॉल्ट) असेल, तर sl_pct/target_pct सेटिंग्ज असल्या तरीही
        वापरल्या जाऊ नयेत — जुनंच वर्तन (backward-compatible)."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["sl_target_mode"] = "POINTS"
        settings["sl_points"] = 20.0
        settings["target_points"] = 40.0
        settings["sl_pct"] = 99.0  # वापरलं गेलं तर चाचणी अयशस्वी होईल इतकं टोकाचं मूल्य
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            mft.process_symbol("fake_token", "CRUDEOIL")
            strategy_result = mock_trade.call_args.args[2]
            assert strategy_result["max_loss"] == 20.0
            assert strategy_result["max_profit"] == 40.0

    @pytest.fixture(autouse=True)
    def _clear_trailing_price_cache(self):
        mft._trailing_price_cache.clear()
        yield
        mft._trailing_price_cache.clear()

    def test_monitor_symbol_converts_trailing_pct_to_points_using_current_price(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["trailing_sl_enabled"] = True
        settings["sl_target_mode"] = "PERCENT"
        settings["trailing_pct"] = 1.0
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("fake_token", "CRUDEOIL")
            kwargs = mock_manage.call_args.kwargs
            assert abs(kwargs["atr_points"] - 6500.0 * 0.01) < 1.0
            assert kwargs["atr_multiplier"] == 1.0

    def test_monitor_symbol_percent_mode_resolve_failure_disables_trailing_safely(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["trailing_sl_enabled"] = True
        settings["sl_target_mode"] = "PERCENT"
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=(False, "सापडला नाही")), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("fake_token", "CRUDEOIL")
            kwargs = mock_manage.call_args.kwargs
            assert kwargs["atr_points"] is None


class TestProcessSymbolMultiAccount:
    def test_uses_multi_account_when_broker_account_ids_selected(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["broker_account_ids"] = ["A1"]
        candles_df = _fake_candles_df(last_close=6500.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=6500.0)), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch("trading_engine.execute_trade_on_all_accounts", return_value=([{"account_id": "A1", "result": "OPENED"}], [])) as mock_multi, \
             patch.object(mft, "open_multi_leg_trade") as mock_single, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True):
            result = mft.process_symbol("fake_token", "CRUDEOIL")
            assert mock_multi.called
            assert not mock_single.called
            assert mock_multi.call_args.kwargs["account_ids"] == ["A1"]
            assert "A1" in result


class TestMonitorSymbol:
    def test_calls_manage_open_trades_with_mcx_eod_and_trailing_settings(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["trailing_sl_enabled"] = True
        settings["trailing_distance_points"] = 15.0
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("fake_token", "CRUDEOIL")
            assert mock_manage.called
            args, kwargs = mock_manage.call_args
            assert args[1] == "CRUDEOIL"
            assert args[2] == mft.PRODUCT_TYPE
            assert kwargs["eod_squareoff_hour"] == mft.MCX_EOD_HOUR
            assert kwargs["eod_squareoff_minute"] == mft.MCX_EOD_MINUTE
            assert kwargs["trailing_sl_enabled"] is True
            assert kwargs["atr_points"] == 15.0
            assert kwargs["atr_multiplier"] == 1.0

    def test_trailing_disabled_passes_no_atr_points(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["trailing_sl_enabled"] = False
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("fake_token", "CRUDEOIL")
            kwargs = mock_manage.call_args.kwargs
            assert kwargs["trailing_sl_enabled"] is False
            assert kwargs["atr_points"] is None


class TestRunExitMonitorCycle:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("exit slippage") — established 3 bots च्या पॅटर्नप्रमाणेच,
    एका symbol चं monitor_symbol() अपयशी झालं तरी बाकीचे symbols तपासलेच जायला हवेत."""

    @pytest.fixture(autouse=True)
    def _all_symbols_have_open_paper_trades(self, monkeypatch):
        monkeypatch.setattr(
            mft.database, "get_open_trade_modes_by_symbol",
            lambda symbols: {s: {"PAPER"} for s in symbols},
        )

    def test_one_symbol_exception_does_not_block_others_in_cycle(self, monkeypatch):
        calls = []

        def fake_monitor(token, symbol, **kwargs):
            calls.append(symbol)
            if symbol == "GOLD":
                raise RuntimeError("boom")
            return []

        monkeypatch.setattr(mft, "monitor_symbol", fake_monitor)
        monkeypatch.setattr(mft, "notify_error", MagicMock())

        results, any_succeeded = mft.run_exit_monitor_cycle("tok", ["CRUDEOIL", "GOLD", "SILVER"])
        assert calls == ["CRUDEOIL", "GOLD", "SILVER"]
        assert any_succeeded is True
        assert any("GOLD" in r for r in results)

    def test_closed_positions_reported_in_results(self, monkeypatch):
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: [{"trade_id": "T1", "reason": "SL"}])
        monkeypatch.setattr(mft, "notify_exit", MagicMock())
        results, any_succeeded = mft.run_exit_monitor_cycle("tok", ["CRUDEOIL"])
        assert any_succeeded is True
        assert any("CRUDEOIL" in r and "बंद" in r for r in results)

    def test_exit_sends_telegram_notification(self, monkeypatch):
        """🎓 "Roj entri exit che sandesh" -- MCX exit वर Telegram (NSE च्या trade_monitor.py प्रमाणे)."""
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: [{"trade_id": "T9", "reason": "TARGET", "pnl": 1234.5}])
        notify = MagicMock()
        monkeypatch.setattr(mft, "notify_exit", notify)
        mft.run_exit_monitor_cycle("tok", ["GOLD"])
        notify.assert_called_once_with("mcx_futures_trader", "GOLD", "T9", "TARGET", 1234.5)

    def test_telegram_failure_does_not_break_exit_cycle(self, monkeypatch):
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: [{"trade_id": "T9", "reason": "SL", "pnl": -10.0}] if s == "GOLD" else [])
        monkeypatch.setattr(mft, "notify_exit", MagicMock(side_effect=RuntimeError("telegram down")))
        results, ok = mft.run_exit_monitor_cycle("tok", ["GOLD", "SILVER"])
        assert ok is True
        assert any("GOLD" in r and "बंद" in r for r in results)


class TestRunExitMonitorLoop:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("exit slippage") — trade_monitor.py च्याच
    run_monitor_loop() पॅटर्नची MCX आवृत्ती (बघा tests/test_trade_monitor.py::TestRunMonitorLoop) —
    fake clock/sleep वापरून वेळ न घालवता चाचणी. आधी हे monitoring cron invocation मध्ये फक्त
    एकदाच व्हायचं, आता interval_seconds च्या अंतराने loop_seconds पर्यंत पुन्हा-पुन्हा."""

    @pytest.fixture(autouse=True)
    def _all_symbols_have_open_paper_trades(self, monkeypatch):
        monkeypatch.setattr(
            mft.database, "get_open_trade_modes_by_symbol",
            lambda symbols: {s: {"PAPER"} for s in symbols},
        )

    def _fake_clock(self, start=0.0):
        state = {"now": start}

        def now_fn():
            return state["now"]

        def sleep_fn(seconds):
            state["now"] += seconds

        return now_fn, sleep_fn, state

    def test_runs_multiple_cycles_within_loop_budget(self, monkeypatch):
        now_fn, sleep_fn, _ = self._fake_clock()
        calls = []
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: calls.append(s) or [])

        any_succeeded = mft.run_exit_monitor_loop(
            "tok", ["CRUDEOIL"], interval_seconds=15, loop_seconds=30,
            sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
            has_open_trades_fn=lambda: False,
        )
        # instant fake-cycle (0 सेकंद घेतो) -> 0, 15, 30 सेकंदांना cycle चालतो (शेवटचा तंतोतंत
        # loop_seconds च्या सीमेवर), नंतर बजेट संपलेलं दिसून थांबतं.
        assert len(calls) == 3
        assert any_succeeded is True

    def test_single_cycle_when_it_alone_exceeds_loop_budget(self, monkeypatch):
        now_fn, sleep_fn, state = self._fake_clock()
        calls = []

        def slow_monitor(token, symbol, **kwargs):
            calls.append(symbol)
            state["now"] += 100  # loop_seconds (30) पेक्षा जास्त
            return []

        monkeypatch.setattr(mft, "monitor_symbol", slow_monitor)
        mft.run_exit_monitor_loop(
            "tok", ["CRUDEOIL"], interval_seconds=15, loop_seconds=30,
            sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
            has_open_trades_fn=lambda: False,
        )
        assert calls == ["CRUDEOIL"]

    def test_never_sleeps_past_loop_budget(self, monkeypatch):
        now_fn, _, state = self._fake_clock()
        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            state["now"] += seconds

        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: [])
        mft.run_exit_monitor_loop(
            "tok", ["CRUDEOIL"], interval_seconds=15, loop_seconds=28,
            sleep_fn=tracking_sleep, now_fn=now_fn, print_fn=lambda x: None,
            has_open_trades_fn=lambda: False,
        )
        assert sum(sleep_calls) <= 28
        assert all(s >= 0 for s in sleep_calls)

    def test_default_loop_seconds_is_30_narrower_than_trade_monitor(self):
        """🎓 MCX crontab च्या ओळीत आधीच `sleep 60` stagger आहे (trade_monitor.py च्या cron ओळीत
        नाही) — त्यामुळे उरलेला budget कमी, म्हणून डीफॉल्ट loop_seconds (30) trade_monitor.py च्या
        (50) पेक्षा जाणूनबुजून कमी ठेवलेला आहे."""
        import inspect
        sig = inspect.signature(mft.run_exit_monitor_loop)
        assert sig.parameters["loop_seconds"].default == 30
        assert sig.parameters["interval_seconds"].default == 15

    def test_open_trade_uses_tight_open_interval(self, monkeypatch):
        """कुठलाही MCX trade OPEN असताना cadence 5 s (idle 15 s ऐवजी)."""
        now_fn, sleep_fn, _ = self._fake_clock()
        calls = []
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: calls.append(s) or [])
        mft.run_exit_monitor_loop(
            "tok", ["GOLD"], interval_seconds=15, loop_seconds=30, open_interval_seconds=5,
            sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
            has_open_trades_fn=lambda: True,
        )
        assert len(calls) == 7  # 0,5,10,...,30

    def test_idle_uses_normal_interval(self, monkeypatch):
        now_fn, sleep_fn, _ = self._fake_clock()
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {})
        calls = []
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: calls.append(s) or [])
        mft.run_exit_monitor_loop(
            "tok", ["GOLD"], interval_seconds=15, loop_seconds=30,
            sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
        )
        assert calls == []  # OPEN trade नाही -> कुठलाही monitor_symbol() कॉल नाही

    def test_open_interval_default_is_5(self):
        import inspect
        assert inspect.signature(mft.run_exit_monitor_loop).parameters["open_interval_seconds"].default == 5


class TestLightExitCycle:
    """🎓 Slippage -- trade_monitor.py प्रमाणेच हलकी cycle: idle symbols वगळणे, positions एकदाच, overlap-safe lock."""

    def test_idle_symbols_are_skipped(self, monkeypatch):
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {"GOLD": {"PAPER"}})
        calls = []
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: calls.append(s) or [])
        results, ok = mft.run_exit_monitor_cycle("tok", ["CRUDEOIL", "GOLD", "SILVER"])
        assert calls == ["GOLD"]
        assert ok is True

    def test_no_open_trades_is_alive_not_failure(self, monkeypatch):
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {})
        fetch = MagicMock()
        monkeypatch.setattr(mft, "fetch_broker_positions", fetch)
        monkeypatch.setattr(mft, "monitor_symbol", MagicMock())
        results, ok = mft.run_exit_monitor_cycle("tok", ["GOLD"])
        assert ok is True and results == []
        fetch.assert_not_called()
        mft.monitor_symbol.assert_not_called()

    def test_positions_fetched_once_only_when_live_trade_exists(self, monkeypatch):
        monkeypatch.setattr(
            mft.database, "get_open_trade_modes_by_symbol",
            lambda symbols: {"GOLD": {"LIVE"}, "SILVER": {"PAPER"}},
        )
        fetch = MagicMock(return_value=[{"instrument_token": "X", "pnl": 1}])
        monkeypatch.setattr(mft, "fetch_broker_positions", fetch)
        seen = []
        monkeypatch.setattr(
            mft, "monitor_symbol",
            lambda t, s, broker_positions=None, record_timing=False: seen.append((s, broker_positions, record_timing)) or [],
        )
        mft.run_exit_monitor_cycle("tok", ["GOLD", "SILVER"])
        assert fetch.call_count == 1
        assert seen == [("GOLD", fetch.return_value, True), ("SILVER", fetch.return_value, True)]

    def test_paper_only_does_not_fetch_positions(self, monkeypatch):
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {"GOLD": {"PAPER"}})
        fetch = MagicMock()
        monkeypatch.setattr(mft, "fetch_broker_positions", fetch)
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: [])
        mft.run_exit_monitor_cycle("tok", ["GOLD"])
        fetch.assert_not_called()

    def test_db_error_falls_back_to_checking_all_symbols(self, monkeypatch):
        def boom(symbols):
            raise RuntimeError("db down")

        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", boom)
        calls = []
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: calls.append(s) or [])
        mft.run_exit_monitor_cycle("tok", ["GOLD", "SILVER"])
        assert calls == ["GOLD", "SILVER"]

    def test_cycle_skipped_when_exit_lock_held(self, monkeypatch):
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {"GOLD": {"PAPER"}})
        monitor = MagicMock(return_value=[])
        monkeypatch.setattr(mft, "monitor_symbol", monitor)
        with mft.ProcessLock(mft.EXIT_MONITOR_LOCK_NAME):
            results, ok = mft.run_exit_monitor_cycle("tok", ["GOLD"])
        monitor.assert_not_called()
        assert ok is False
        assert any("वगळली" in r for r in results)

    def test_monitor_symbol_passes_shared_positions_and_timing_to_manage(self):
        settings = dict(_DEFAULT_SETTINGS)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("tok", "GOLD", broker_positions=[{"x": 1}], record_timing=True)
            kwargs = mock_manage.call_args.kwargs
            assert kwargs["broker_positions"] == [{"x": 1}]
            assert kwargs["record_timing"] is True

    def test_monitor_symbol_default_keeps_old_manage_call(self):
        settings = dict(_DEFAULT_SETTINGS)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("tok", "GOLD")
            kwargs = mock_manage.call_args.kwargs
            assert "broker_positions" not in kwargs and "record_timing" not in kwargs


class TestStreamLivePrices:
    """🎓 WebSocket (position_stream_monitor.py --market mcx) -- live_prices exit cycle आणि monitor_symbol मार्गे manage_open_trades पर्यंत."""

    def test_cycle_passes_live_prices_and_skips_rest_positions(self, monkeypatch):
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {"GOLD": {"LIVE"}})
        fetch = MagicMock()
        monkeypatch.setattr(mft, "fetch_broker_positions", fetch)
        seen = []
        monkeypatch.setattr(
            mft, "monitor_symbol",
            lambda t, s, broker_positions=None, record_timing=False, live_prices=None, live_price_age=None:
            seen.append((s, broker_positions, live_prices, live_price_age)) or [],
        )
        mft.run_exit_monitor_cycle("tok", ["GOLD", "SILVER"], live_prices={"K": 1.0}, live_price_age={"K": 0.3})
        fetch.assert_not_called()       # stream मार्गात positions REST ने नाहीत (REST monitor reconciliation करतो)
        assert seen == [("GOLD", [], {"K": 1.0}, {"K": 0.3})]

    def test_cycle_without_live_prices_unchanged(self, monkeypatch):
        monkeypatch.setattr(mft.database, "get_open_trade_modes_by_symbol", lambda symbols: {"GOLD": {"LIVE"}})
        fetch = MagicMock(return_value=[{"x": 1}])
        monkeypatch.setattr(mft, "fetch_broker_positions", fetch)
        calls = []
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s, **kw: calls.append(kw) or [])
        mft.run_exit_monitor_cycle("tok", ["GOLD"])
        fetch.assert_called_once()
        assert "live_prices" not in calls[0] and calls[0]["broker_positions"] == [{"x": 1}]

    def test_monitor_symbol_forwards_live_prices_to_manage_open_trades(self):
        settings = dict(_DEFAULT_SETTINGS)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("tok", "GOLD", live_prices={"K": 5.0}, live_price_age={"K": 0.1})
            kwargs = mock_manage.call_args.kwargs
            assert kwargs["live_prices"] == {"K": 5.0} and kwargs["live_price_age"] == {"K": 0.1}

    def test_monitor_symbol_default_has_no_live_prices_kwarg(self):
        settings = dict(_DEFAULT_SETTINGS)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft, "manage_open_trades", return_value=[]) as mock_manage:
            mft.monitor_symbol("tok", "GOLD")
            assert "live_prices" not in mock_manage.call_args.kwargs


def _trend_30m_df(days=8, direction="up"):
    """30-मिनिट candles (MCX सत्र ९:००-२३:०० IST) -- सलग `days` दिवस, सतत वर किंवा सतत खाली जाणारी किंमत; शेवटचा दिवस दुपारपर्यंत."""
    rows = []
    price = 6000.0
    step = 4.0 if direction == "up" else -4.0
    base = mft.get_ist_now().replace(hour=0, minute=0, second=0, microsecond=0) - pd.Timedelta(days=days - 1)
    for d in range(days):
        day = base + pd.Timedelta(days=d)
        for slot in range(29):  # ९:०० ते २३:०० = २९ x 30 मिनिट
            ts = day + pd.Timedelta(hours=9) + pd.Timedelta(minutes=30 * slot)
            o, c = price, price + step
            rows.append({"timestamp": ts, "open": o, "high": max(o, c) + 1, "low": min(o, c) - 1, "close": c, "volume": 1, "oi": 0})
            price = c
    return pd.DataFrame(rows)


class TestResampleTo4h:
    def test_bins_start_at_mcx_session_hours(self):
        from signals import resample_to_4h
        df = _trend_30m_df(days=2)
        out = resample_to_4h(df)
        hours = sorted(set(out["timestamp"].dt.hour))
        assert hours == [9, 13, 17, 21]
        first = out.iloc[0]
        assert first["timestamp"].hour == 9
        assert first["open"] == df.iloc[0]["open"] and first["close"] == df.iloc[7]["close"]   # ९:०० ते १२:३० = ८ x 30 मिनिट

    def test_empty_input(self):
        from signals import resample_to_4h
        assert resample_to_4h(pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])).empty


class TestFetchMcxTrendFilterDirections:
    NOW = None

    def _now(self):
        return mft.get_ist_now().replace(hour=23, minute=59)

    def test_uptrend_gives_bullish_both(self):
        with patch.object(mft, "fetch_mcx_candles", return_value=_trend_30m_df(direction="up")):
            assert mft.fetch_mcx_trend_filter_directions("tok", "MCX_FO|1", self._now()) == ("BULLISH", "BULLISH")

    def test_downtrend_gives_bearish_both(self):
        with patch.object(mft, "fetch_mcx_candles", return_value=_trend_30m_df(direction="down")):
            assert mft.fetch_mcx_trend_filter_directions("tok", "MCX_FO|1", self._now()) == ("BEARISH", "BEARISH")

    def test_no_data_or_error_gives_none(self):
        with patch.object(mft, "fetch_mcx_candles", return_value=pd.DataFrame()):
            assert mft.fetch_mcx_trend_filter_directions("tok", "MCX_FO|1", self._now()) == (None, None)
        with patch.object(mft, "fetch_mcx_candles", side_effect=RuntimeError("api down")):
            assert mft.fetch_mcx_trend_filter_directions("tok", "MCX_FO|1", self._now()) == (None, None)

    def test_too_little_history_for_4h_gives_none_for_4h_only(self):
        df = _trend_30m_df(days=1, direction="down")   # एका दिवसात ४H चे फक्त ४ bars -- ATR(10) साठी अपुरे
        with patch.object(mft, "fetch_mcx_candles", return_value=df):
            d1h, d4h = mft.fetch_mcx_trend_filter_directions("tok", "MCX_FO|1", self._now())
        assert d1h == "BEARISH" and d4h is None


class TestSupertrendEntryGate:
    """🎓 "add Supertrend entry gate for MCX futures" -- 1H आणि 4H दोन्ही Supertrend च्या खाली => Bullish नाही; दोन्हींच्या वर => Bearish नाही."""

    def _run(self, directions, bullish=True, enabled=True):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = False
        settings["entry_supertrend_filter_enabled"] = enabled
        if bullish:
            candles_df = _fake_candles_df(last_close=6500.0)
            zones = _fake_zones(support_level=6500.0)
        else:
            candles_df = _fake_candles_df(closes=[6300.0] * 19 + [6400.0])
            zones = _fake_zones(support_level=6402.0)
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=zones), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft, "fetch_mcx_trend_filter_directions", return_value=directions) as mock_dirs, \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log:
            mft.process_symbol("fake_token", "CRUDEOIL")
        statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
        return mock_trade, mock_dirs, statuses

    def test_bullish_blocked_when_price_below_both(self):
        trade, _, statuses = self._run(("BEARISH", "BEARISH"), bullish=True)
        assert not trade.called and "SKIPPED_MCX_TREND_FILTER" in statuses

    def test_bullish_allowed_when_only_one_is_bearish(self):
        trade, _, _ = self._run(("BEARISH", "BULLISH"), bullish=True)
        assert trade.called
        trade, _, _ = self._run(("BULLISH", "BEARISH"), bullish=True)
        assert trade.called

    def test_bullish_allowed_when_price_above_both(self):
        trade, _, _ = self._run(("BULLISH", "BULLISH"), bullish=True)
        assert trade.called

    def test_bearish_blocked_when_price_above_both(self):
        trade, _, statuses = self._run(("BULLISH", "BULLISH"), bullish=False)
        assert not trade.called and "SKIPPED_MCX_TREND_FILTER" in statuses

    def test_bearish_allowed_when_price_below_both_or_mixed(self):
        trade, _, _ = self._run(("BEARISH", "BEARISH"), bullish=False)
        assert trade.called
        trade, _, _ = self._run(("BULLISH", "BEARISH"), bullish=False)
        assert trade.called

    def test_missing_data_does_not_block(self):
        trade, _, _ = self._run((None, "BEARISH"), bullish=True)
        assert trade.called
        trade, _, _ = self._run((None, None), bullish=False)
        assert trade.called

    def test_disabled_by_default_never_fetches_or_blocks(self):
        assert _DEFAULT_SETTINGS["entry_supertrend_filter_enabled"] is False
        trade, dirs, statuses = self._run(("BEARISH", "BEARISH"), bullish=True, enabled=False)
        assert trade.called and not dirs.called and "SKIPPED_MCX_TREND_FILTER" not in statuses

    def test_blocked_touch_is_not_counted_as_a_hit(self):
        import cloud_db as cdb
        assert "SKIPPED_MCX_TREND_FILTER" in cdb._NON_HIT_TRADE_STATUSES


class TestMinHoldGate:
    """🎓 "First time level hit, level hold Minimum period for 1st trade, hi condition mcx future sathi lagu kra, default on thewa" --
    level ला किंमत टेकल्यावर किमान N मिनिटं (1-मिनिट candles वर) सलग level जवळ टिकली तरच entry; फक्त त्या level+role वरच्या पहिल्या खऱ्या trade ला."""

    LEVEL = 6500.0

    @staticmethod
    def _candles_1m(touching, far=0):
        """जुनं ते नवीन: आधी `far` candles level पासून दूर, मग `touching` candles level ला overlap करणारे."""
        return [{"low": 6400.0, "high": 6410.0}] * far + [{"low": 6498.0, "high": 6502.0}] * touching

    def _run(self, candles_1m, enabled=True, last_trade_time=None, first_trade_only=True, minutes=5):
        settings = dict(_DEFAULT_SETTINGS)
        settings.update({
            "symbol_enabled": True, "entry_rsi_gate_enabled": False, "entry_min_hold_gate_enabled": enabled,
            "entry_min_hold_minutes": minutes, "entry_min_hold_first_trade_only": first_trade_only,
        })
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones(support_level=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_candles", return_value=_fake_candles_df(last_close=self.LEVEL)), \
             patch.object(mft, "fetch_mcx_todays_1m_candles", return_value=candles_1m) as mock_1m, \
             patch.object(mft.cloud_db, "get_zone_hits_today", return_value=(0 if last_trade_time is None else 1, None, last_trade_time)), \
             patch.object(mft, "has_open_trade_from_source", return_value=False), \
             patch.object(mft, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(mft, "send_telegram_message", return_value=True), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True) as mock_log:
            mft.process_symbol("fake_token", "CRUDEOIL")
        statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
        return mock_trade, mock_1m, statuses, mock_log

    def test_enabled_by_default_with_5_minutes_first_trade_only(self):
        d = cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"]
        assert d["entry_min_hold_gate_enabled"] is True
        assert d["entry_min_hold_minutes"] == 5
        assert d["entry_min_hold_first_trade_only"] is True

    def test_fresh_touch_is_blocked(self):
        trade, _, statuses, log = self._run(self._candles_1m(touching=2, far=10))
        assert not trade.called and "SKIPPED_MIN_HOLD_DURATION" in statuses
        reason = [c.args[0]["reason"] for c in log.call_args_list if c.args[0]["trade_status"] == "SKIPPED_MIN_HOLD_DURATION"][0]
        assert "फक्त 2 मिनिटं" in reason and "किमान 5" in reason

    def test_held_long_enough_trades(self):
        trade, _, statuses, _ = self._run(self._candles_1m(touching=5, far=10))
        assert trade.called and "SKIPPED_MIN_HOLD_DURATION" not in statuses

    def test_minutes_setting_is_respected(self):
        trade, _, _, _ = self._run(self._candles_1m(touching=3, far=10), minutes=3)
        assert trade.called
        trade, _, _, _ = self._run(self._candles_1m(touching=3, far=10), minutes=4)
        assert not trade.called

    def test_second_trade_on_same_level_skips_the_gate_when_first_trade_only(self):
        trade, mock_1m, _, _ = self._run(self._candles_1m(touching=1, far=10), last_trade_time=mft.get_ist_now())
        assert trade.called and not mock_1m.called

    def test_second_trade_still_gated_when_first_trade_only_is_off(self):
        trade, _, statuses, _ = self._run(self._candles_1m(touching=1, far=10), last_trade_time=mft.get_ist_now(), first_trade_only=False)
        assert not trade.called and "SKIPPED_MIN_HOLD_DURATION" in statuses

    def test_missing_one_minute_data_does_not_block(self):
        trade, _, _, _ = self._run(None)
        assert trade.called
        trade, _, _, _ = self._run([])
        assert trade.called

    def test_disabled_never_fetches_or_blocks(self):
        trade, mock_1m, statuses, _ = self._run(self._candles_1m(touching=1, far=10), enabled=False)
        assert trade.called and not mock_1m.called and "SKIPPED_MIN_HOLD_DURATION" not in statuses

    def test_blocked_touch_is_not_counted_as_a_hit(self):
        import cloud_db as cdb
        assert "SKIPPED_MIN_HOLD_DURATION" in cdb._NON_HIT_TRADE_STATUSES


class TestFetchMcxTodays1mCandles:
    def _now(self):
        return mft.get_ist_now().replace(hour=15, minute=30)

    def _df(self, days_back_rows=3, today_rows=4):
        now = self._now()
        old = pd.date_range(end=now - pd.Timedelta(days=1), periods=days_back_rows, freq="1min")
        today = pd.date_range(end=now, periods=today_rows, freq="1min")
        ts = list(old) + list(today)
        return pd.DataFrame({"timestamp": ts, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 0, "oi": 0})

    def test_returns_only_todays_candles_as_low_high_records(self):
        with patch.object(mft, "fetch_mcx_candles", return_value=self._df()) as m:
            out = mft.fetch_mcx_todays_1m_candles("tok", "MCX_FO|1", self._now())
        assert m.call_args.kwargs["interval"] == "1minute"
        assert out == [{"low": 0.5, "high": 2.0}] * 4

    def test_none_on_empty_error_or_no_candles_today(self):
        with patch.object(mft, "fetch_mcx_candles", return_value=pd.DataFrame()):
            assert mft.fetch_mcx_todays_1m_candles("tok", "k", self._now()) is None
        with patch.object(mft, "fetch_mcx_candles", side_effect=RuntimeError("api down")):
            assert mft.fetch_mcx_todays_1m_candles("tok", "k", self._now()) is None
        with patch.object(mft, "fetch_mcx_candles", return_value=self._df(today_rows=0)):
            assert mft.fetch_mcx_todays_1m_candles("tok", "k", self._now()) is None


class TestTrailingPriceCache:
    @pytest.fixture(autouse=True)
    def _clear(self):
        mft._trailing_price_cache.clear()
        yield
        mft._trailing_price_cache.clear()

    def test_reference_price_cached_within_ttl(self):
        calls = {"n": 0}

        def fake_fetch(*a, **k):
            calls["n"] += 1
            return _fake_candles_df(last_close=6500.0)

        with patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft, "fetch_mcx_candles", side_effect=fake_fetch):
            t = [100.0]
            p1 = mft._get_trailing_reference_price("tok", "GOLD", now_fn=lambda: t[0])
            t[0] = 110.0
            p2 = mft._get_trailing_reference_price("tok", "GOLD", now_fn=lambda: t[0])
            assert p1 == p2 == 6500.0 and calls["n"] == 1
            t[0] = 125.0  # TTL (20 s) संपला
            mft._get_trailing_reference_price("tok", "GOLD", now_fn=lambda: t[0])
            assert calls["n"] == 2

    def test_failure_is_not_cached(self):
        with patch.object(mft.mcx_resolver, "resolve_symbol", return_value=(False, "x")):
            assert mft._get_trailing_reference_price("tok", "GOLD") is None
        assert "GOLD" not in mft._trailing_price_cache


class TestLastCheckHeartbeat:
    """🎓 "Crude oil hit log not working" / "Same problem silver gold" — Hit Log मध्ये NO_HIT dedup मुळे शांत काळात कोणतीच
    नवीन ओळ येत नाही; म्हणून प्रत्येक cycle ला अखेरची तपासणी (वेळ/भाव/जवळचा level/स्थिती) वेगळी साठवली जाते."""

    def _run(self, candles_df, settings_updates=None, zones=None, resolved=None):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings.update(settings_updates or {})
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=resolved or _fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=zones if zones is not None else _fake_zones()), \
             patch.object(mft, "fetch_mcx_candles", return_value=candles_df), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True), \
             patch.object(mft.cloud_db, "save_mcx_last_check", return_value=True) as mock_hb:
            result = mft.process_symbol("fake_token", "CRUDEOIL")
        return result, mock_hb

    def test_no_touch_records_price_and_nearest_level(self):
        result, hb = self._run(_fake_candles_df(last_close=7500.0))
        assert hb.call_count == 1
        args, kwargs = hb.call_args
        assert args[0] == "CRUDEOIL" and args[2] == result
        assert kwargs["price"] == 7500.0 and kwargs["nearest_level"] == 6500.0
        assert kwargs["nearest_level_type"] == "SUPPORT" and kwargs["nearest_timeframe"] == "30M"

    def test_disabled_symbol_still_records_status(self):
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=dict(_DEFAULT_SETTINGS)), \
             patch.object(mft.cloud_db, "save_mcx_last_check", return_value=True) as hb:
            result = mft.process_symbol("fake_token", "CRUDEOIL")
        assert "बंद आहे" in result and hb.call_args.args[2] == result
        assert hb.call_args.kwargs["price"] is None

    def test_heartbeat_failure_never_breaks_trading(self):
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(mft.mcx_resolver, "resolve_symbol", return_value=_fake_resolved()), \
             patch.object(mft.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(mft, "fetch_mcx_candles", return_value=_fake_candles_df(last_close=7500.0)), \
             patch.object(mft.cloud_db, "save_signal_log", return_value=True), \
             patch.object(mft.cloud_db, "save_mcx_last_check", side_effect=RuntimeError("db down")):
            result = mft.process_symbol("fake_token", "CRUDEOIL")
        assert "पात्र ठरला नाही" in result


class TestMcxLastCheckStorage:
    def test_save_and_get_round_trip(self):
        store = {}

        def fake_save(strategy, symbol, payload):
            store[(strategy, symbol)] = payload
            return True

        def fake_get(strategy, symbol):
            return dict(store.get((strategy, symbol), {}), symbol_enabled=False)

        with patch.object(cloud_db, "save_strategy_settings", side_effect=fake_save), \
             patch.object(cloud_db, "get_strategy_settings", side_effect=fake_get):
            import datetime as dt
            import numpy as np
            assert cloud_db.get_mcx_last_check("GOLD") is None  # कधीच नोंद नाही
            cloud_db.save_mcx_last_check("GOLD", dt.datetime(2026, 9, 30, 14, 42, 27), "स्थिती", price=np.float64(147623.0),
                                         nearest_level=147828, nearest_level_type="RESISTANCE", nearest_timeframe="30M")
            got = cloud_db.get_mcx_last_check("GOLD")
        assert got["checked_at"] == "2026-09-30 14:42:27" and got["price"] == 147623.0 and got["nearest_level"] == 147828.0
        assert got["nearest_level_type"] == "RESISTANCE" and got["status"] == "स्थिती"
