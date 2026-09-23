"""
tests/test_mcx_futures_trader.py
--------------------------------------------------------------
mcx_futures_trader.py — MCX Futures Trader (CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER). srv2_momentum_
reversal_strategy.py च्या TestProcessSymbol/TestMultiTimeframe/TestProcessSymbolMultiAccount च्याच
mocking पॅटर्नचं अनुकरण — पण options ऐवजी एकाच futures leg वर लक्ष केंद्रित (strike/premium/hedge
गणित नाही, फक्त sl_points/target_points सरळ max_loss/max_profit म्हणून पास होतात का, आणि दिशेनुसार
BUY/SELL बरोबर ठरतं का, हेच सर्वात जास्त धोक्याचं — म्हणून सर्वात कसून तपासलेलं).
"""
from unittest.mock import patch

import pandas as pd

import cloud_db
import mcx_futures_trader as mft


def _fake_candles_df(n=20, last_close=6500.0):
    end_ts = mft.get_ist_now().replace(hour=15, minute=15, second=0, microsecond=0)
    dates = pd.date_range(end=end_ts, periods=n, freq="30min")
    closes = [6600.0 - i for i in range(n - 1)] + [last_close]
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


_DEFAULT_SETTINGS = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"])


class TestDetermineDirectionWithHysteresis:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py/srv2_momentum_reversal_
    strategy.py मधलीच hysteresis पद्धत इथेही, तोच 0.015% buffer (srv2 सारखाच — MCX सुद्धा फक्त
    30M/60M candles वापरतो, 15M कधीच नाही)."""

    LEVEL = 6500.0

    def test_sticky_bullish_when_dip_stays_within_buffer(self):
        closes = [6600.0, 6499.5]  # 6499.5 < level(6500) पण lower buffer (~6499.025) च्या वरच
        assert mft.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_flips_to_bearish_only_when_clearly_beyond_buffer(self):
        closes = [6600.0, 6480.0]  # lower buffer (~6499.025) च्या स्पष्टपणे खाली -- खरा breakdown
        assert mft.determine_direction_with_hysteresis(self.LEVEL, closes) == "BEARISH"

    def test_falls_back_to_raw_comparison_when_never_left_band(self):
        closes = [6500.0]  # बरोबर level वरच, buffer बाहेर कधीच नाही
        assert mft.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_real_world_scenario_stays_bullish_through_momentary_dip(self):
        closes = [6600.0, 6499.3, 6499.1, 6500.4]  # सगळेच buffer (~6499.025-6500.975) च्या आत/वर
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

    def test_rsi_gate_blocks_entry(self):
        """किंमत level (6500) च्या वरच आहे -> BULLISH -> RSI support_max पेक्षा कमी हवा. सलग
        वाढणाऱ्या closes मुळे RSI जास्त असेल -> गेटने अडवायला हवं."""
        settings = dict(_DEFAULT_SETTINGS)
        settings["symbol_enabled"] = True
        settings["entry_rsi_gate_enabled"] = True
        rising_closes = [6400.0 + i * 5 for i in range(20)]
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
        candles_df = _fake_candles_df(last_close=6400.0)  # level पेक्षा किंचित कमी, पण touch-tolerance च्या आत
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
