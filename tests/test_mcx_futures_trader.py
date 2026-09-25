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


_DEFAULT_SETTINGS = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"])


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

    def test_one_symbol_exception_does_not_block_others_in_cycle(self, monkeypatch):
        calls = []

        def fake_monitor(token, symbol):
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
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s: [{"trade_id": "T1", "reason": "SL"}])
        results, any_succeeded = mft.run_exit_monitor_cycle("tok", ["CRUDEOIL"])
        assert any_succeeded is True
        assert any("CRUDEOIL" in r and "बंद" in r for r in results)


class TestRunExitMonitorLoop:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("exit slippage") — trade_monitor.py च्याच
    run_monitor_loop() पॅटर्नची MCX आवृत्ती (बघा tests/test_trade_monitor.py::TestRunMonitorLoop) —
    fake clock/sleep वापरून वेळ न घालवता चाचणी. आधी हे monitoring cron invocation मध्ये फक्त
    एकदाच व्हायचं, आता interval_seconds च्या अंतराने loop_seconds पर्यंत पुन्हा-पुन्हा."""

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
        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s: calls.append(s) or [])

        any_succeeded = mft.run_exit_monitor_loop(
            "tok", ["CRUDEOIL"], interval_seconds=15, loop_seconds=30,
            sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
        )
        # instant fake-cycle (0 सेकंद घेतो) -> 0, 15, 30 सेकंदांना cycle चालतो (शेवटचा तंतोतंत
        # loop_seconds च्या सीमेवर), नंतर बजेट संपलेलं दिसून थांबतं.
        assert len(calls) == 3
        assert any_succeeded is True

    def test_single_cycle_when_it_alone_exceeds_loop_budget(self, monkeypatch):
        now_fn, sleep_fn, state = self._fake_clock()
        calls = []

        def slow_monitor(token, symbol):
            calls.append(symbol)
            state["now"] += 100  # loop_seconds (30) पेक्षा जास्त
            return []

        monkeypatch.setattr(mft, "monitor_symbol", slow_monitor)
        mft.run_exit_monitor_loop(
            "tok", ["CRUDEOIL"], interval_seconds=15, loop_seconds=30,
            sleep_fn=sleep_fn, now_fn=now_fn, print_fn=lambda x: None,
        )
        assert calls == ["CRUDEOIL"]

    def test_never_sleeps_past_loop_budget(self, monkeypatch):
        now_fn, _, state = self._fake_clock()
        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            state["now"] += seconds

        monkeypatch.setattr(mft, "monitor_symbol", lambda t, s: [])
        mft.run_exit_monitor_loop(
            "tok", ["CRUDEOIL"], interval_seconds=15, loop_seconds=28,
            sleep_fn=tracking_sleep, now_fn=now_fn, print_fn=lambda x: None,
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
