"""
tests/test_classic_sr_reversal_trader.py
------------------------------------------------
classic_sr_reversal_trader.py — वापरकर्त्याशी चर्चा करून बांधलेली, संपूर्णपणे नवीन, स्वतंत्र तिसरी
strategy (5M+15M pooled, symmetric RSI neutral=50, तीन ऐच्छिक Entry Refinement गेट्स — Swing
High/Low, Demand/Supply, Trendline — सर्व Bot Dynamic SR Algo वरून toggle करण्याजोगे). ही strategy
अजून backtest-टप्प्यातच असल्याने symbol_enabled डीफॉल्ट सर्व symbols (NIFTY सकट) साठी False आहे.
"""
import datetime
from unittest.mock import MagicMock, patch

import pandas as pd

import classic_sr_reversal_trader as csr
import cloud_db
from config import get_ist_now


class TestCheckLevelCrossed:
    """dynamic_sr_instant_trader.py मधल्याच check_level_crossed() ची जशीच्या तशी कॉपी — इथे फक्त
    सुनिश्चित करतो की तीच वागणूक कायम आहे (TOUCH + GAP_THROUGH)."""

    def test_direct_touch(self):
        candles = [{"open": 24010, "high": 24015, "low": 24000, "close": 24005},
                   {"open": 24000, "high": 24008, "low": 23895, "close": 23900}]
        hit, hit_type, price = csr.check_level_crossed(23900, candles)
        assert hit is True and hit_type == "TOUCH"

    def test_gap_through(self):
        candles = [{"open": 24010, "high": 24015, "low": 24000, "close": 24005},
                   {"open": 23750, "high": 23820, "low": 23700, "close": 23780}]
        hit, hit_type, price = csr.check_level_crossed(23900, candles)
        assert hit is True and hit_type == "GAP_THROUGH"

    def test_no_hit(self):
        candles = [{"open": 24010, "high": 24015, "low": 24000, "close": 24005}]
        hit, hit_type, price = csr.check_level_crossed(23900, candles)
        assert hit is False


def _fake_zones():
    return pd.DataFrame([
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 23900.0, "zone_high": 23900.0,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": 24500.0, "zone_high": 24500.0,
         "strength": 2.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


def _candles_with_rsi(touch_rows, declining=True, today_ist=None):
    """RSI(14, neutral=50) साठी किमान 15 candles — घसरणारा (Support/BULLISH -> RSI<50) किंवा
    चढणारा (Resistance/BEARISH -> RSI>50) trend prepend करून."""
    n = 25
    if declining:
        trend = [{"open": 24200 - i * 10, "high": 24210 - i * 10, "low": 24190 - i * 10, "close": 24195 - i * 10} for i in range(n)]
    else:
        trend = [{"open": 23600 + i * 10, "high": 23610 + i * 10, "low": 23590 + i * 10, "close": 23605 + i * 10} for i in range(n)]
    all_rows = trend + touch_rows
    today_ist = (today_ist or csr.get_ist_now()).replace(hour=10, minute=0, second=0, microsecond=0)
    timestamps = pd.date_range(end=today_ist, periods=len(all_rows), freq="5min")
    df = pd.DataFrame(all_rows)
    df["timestamp"] = timestamps
    return df


def _fake_chain(spot):
    return [{"underlying_spot_price": spot, "strike_price": 24000, "expiry": "2026-09-10",
             "call_options": {"instrument_key": "CE1", "market_data": {"ltp": 50}, "option_greeks": {}},
             "put_options": {"instrument_key": "PE1", "market_data": {"ltp": 45}, "option_greeks": {}}}]


def _row(ts, o, h, l, c):
    return {"timestamp": pd.Timestamp(ts), "open": o, "high": h, "low": l, "close": c}


def _flat_bars(values, start_ts="2026-09-01 09:15:00"):
    start = pd.Timestamp(start_ts)
    return [_row(start + pd.Timedelta(minutes=5 * i), v, v, v, v) for i, v in enumerate(values)]


# 🎓 tests/test_backtest.py च्या TestClassicSrReversalEntryRefinement मध्ये आधीच स्क्रिप्टने खऱ्या
# find_swings/analyze_chart_zones/detect_trendline विरुद्ध पडताळून घेतलेला, तोच zigzag डेटा — इथे तीच
# डेटासेट्स गेट-फंक्शन्स थेट (backtest.py मार्गे नाही) तपासण्यासाठी वापरलेली.
_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100 = [108, 104, 101, 100.0, 101, 104, 108.0, 104, 101, 100.0, 101, 104, 109.0, 104, 101, 100.0]
_ZIGZAG_WITH_BROKEN_ASCENDING_TRENDLINE = [
    108, 104, 101, 98.0, 101, 104, 108.0, 104, 101, 99.0, 101, 104, 109.0, 104, 101, 100.3,
    104, 108, 113.0, 108, 104, 100.0,
]


class TestClassicSrRsiFilter:
    """symmetric RSI(14) neutral=50 — Support(BULLISH)<50, Resistance(BEARISH)>50 (dynamic_sr_instant
    च्या असममित 40/60 उंबरठ्यांऐवजी srv2_momentum_reversal सारखाच symmetric तर्क)."""

    def test_bullish_passes_with_low_rsi(self):
        df = _candles_with_rsi([], declining=True)
        passed, rsi_value = csr.check_classic_sr_rsi_filter(df, "BULLISH")
        assert passed is True and rsi_value < 50

    def test_bullish_fails_with_high_rsi(self):
        df = _candles_with_rsi([], declining=False)
        passed, rsi_value = csr.check_classic_sr_rsi_filter(df, "BULLISH")
        assert passed is False and rsi_value > 50

    def test_bearish_passes_with_high_rsi(self):
        df = _candles_with_rsi([], declining=False)
        passed, rsi_value = csr.check_classic_sr_rsi_filter(df, "BEARISH")
        assert passed is True and rsi_value > 50

    def test_bearish_fails_with_low_rsi(self):
        df = _candles_with_rsi([], declining=True)
        passed, rsi_value = csr.check_classic_sr_rsi_filter(df, "BEARISH")
        assert passed is False and rsi_value < 50


class TestEntryRefinementGateFunctions:
    """तीन ऐच्छिक Entry Refinement गेट्स — सर्व डीफॉल्ट बंद, backtest.py मधल्याच तर्काशी सुसंगत."""

    def test_swing_confluence_passes_near_confirmed_swing(self):
        df = pd.DataFrame(_flat_bars(_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100))
        ok, nearest = csr.check_swing_confluence(df, 100.0, "BULLISH")
        assert ok is True

    def test_swing_confluence_fails_on_insufficient_data(self):
        df = pd.DataFrame(_flat_bars([101, 100.9, 100.95]))
        ok, nearest = csr.check_swing_confluence(df, 100.0, "BULLISH")
        assert ok is False

    def test_swing_min_move_pct_filters_minor_swing(self):
        """🎓 वापरकर्त्याने प्रत्यक्ष चार्ट screenshot वरून "major swings only" दाखवलं — swing_min_move_pct
        डीफॉल्ट (0.0) सह किरकोळ (मागच्या high पासून फक्त ~2.9% हालचालीचा) स्विंग लो गेट पास करतो, पण
        जास्त threshold दिल्यास तो किरकोळ स्विंग गाळला जाऊन उरलेला एकमेव major स्विंग लो (90.0) दूर
        असल्याने गेट अडवतो."""
        vals = [108, 104, 101, 90.0, 95, 99, 103.0, 102, 101, 100.05, 101, 102, 103.5, 101, 100.5, 100.0]
        df = pd.DataFrame(_flat_bars(vals))
        baseline_ok, baseline_nearest = csr.check_swing_confluence(df, 100.0, "BULLISH")
        assert baseline_ok is True
        assert baseline_nearest == 100.05

        filtered_ok, filtered_nearest = csr.check_swing_confluence(df, 100.0, "BULLISH", swing_min_move_pct=3.5)
        assert filtered_ok is False
        assert filtered_nearest == 90.0

    def test_demand_supply_passes_when_level_inside_zone(self):
        df = pd.DataFrame(_flat_bars(_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100))
        ok, zone = csr.check_demand_supply_confluence(df, 100.0, "BULLISH")
        assert bool(ok) is True
        assert zone is not None

    def test_demand_supply_fails_on_insufficient_data(self):
        df = pd.DataFrame(_flat_bars([101, 100.9, 100.95]))
        ok, zone = csr.check_demand_supply_confluence(df, 100.0, "BULLISH")
        assert ok is False
        assert zone is None

    def test_trendline_not_broken_blocks_when_broken(self):
        df = pd.DataFrame(_flat_bars(_ZIGZAG_WITH_BROKEN_ASCENDING_TRENDLINE))
        ok, tl = csr.check_trendline_not_broken(df, "BULLISH")
        assert ok is False
        assert tl["status"] == "BROKEN"

    def test_trendline_not_broken_passes_when_no_valid_trendline(self):
        df = pd.DataFrame(_flat_bars(_ZIGZAG_WITH_CONFIRMED_SWING_NEAR_100))
        ok, tl = csr.check_trendline_not_broken(df, "BULLISH")
        assert ok is True


class TestCollectPooledLevels:
    def test_default_pools_5m_and_15m(self):
        pooled = csr._collect_pooled_levels(_fake_zones())
        suffixes = sorted(s for _, s in pooled)
        assert suffixes == ["15M", "5M"]

    def test_5m_only(self):
        pooled = csr._collect_pooled_levels(_fake_zones(), ["5M"])
        assert [s for _, s in pooled] == ["5M"]


class TestProcessSymbolSymbolEnabled:
    def test_symbol_disabled_by_default_even_for_nifty(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेला सुरक्षिततेचा नियम — नवीन strategy backtest-टप्प्यातच
        असल्याने NIFTY सकट सर्व symbols साठी symbol_enabled डीफॉल्ट False."""
        with patch.object(csr.cloud_db, "get_market_zones") as mock_zones:
            result = csr.process_symbol("fake_token", "NIFTY")
            assert "बंद आहे" in result
            assert not mock_zones.called


class TestProcessSymbolCoreFlow:
    def _settings(self, **overrides):
        s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["classic_sr_reversal"])
        s["symbol_enabled"] = True
        s.update(overrides)
        return s

    def test_direct_touch_executes_trade_with_all_gates_off_default(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "fetch_option_expiries", return_value=[]), \
             patch.object(csr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(csr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(csr, "select_naked_option_itm", return_value=None), \
             patch.object(csr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(csr, "send_telegram_message", return_value=True), \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            result = csr.process_symbol("fake_token", "NIFTY")
            assert "TOUCH" in result
            assert mock_trade.called
            assert mock_trade.call_args.kwargs.get("source") == "classic_sr_reversal"

    def test_rsi_gate_blocks_wrong_direction(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=False, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "open_multi_leg_trade") as mock_trade, \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_RSI_FILTER" in statuses

    def test_rsi_gate_disabled_skips_check(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=False, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(entry_rsi_gate_enabled=False)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "fetch_option_expiries", return_value=[]), \
             patch.object(csr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(csr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(csr, "select_naked_option_itm", return_value=None), \
             patch.object(csr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(csr, "send_telegram_message", return_value=True), \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            csr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_atm_strike_rounds_to_symbol_own_strike_step_not_always_50(self):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — dynamic_sr_instant_trader.py प्रमाणेच इथेही
        atm_strike कायम round(price/50)*50 वापरत होता, BANKNIFTY/SENSEX (strike step 100) साठी
        अनेकदा चुकीचा (raw_chain मध्ये सापडतच न येणाऱ्या ग्रिडवर strike). आता symbol च्या
        cloud_db.STRIKE_STEP नुसार राऊंड होतो."""
        banknifty_zones = pd.DataFrame([
            {"symbol": "BANKNIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 51930.0, "zone_high": 51930.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        candles_touch = _candles_with_rsi([
            {"open": 51960, "high": 51970, "low": 51950, "close": 51955},
            {"open": 51950, "high": 51955, "low": 51920, "close": 51930},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(entry_rsi_gate_enabled=False)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=banknifty_zones), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "fetch_option_expiries", return_value=[]), \
             patch.object(csr, "fetch_upstox_option_chain", return_value=(_fake_chain(51930.0), "SUCCESS")), \
             patch.object(csr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}) as mock_select, \
             patch.object(csr, "select_naked_option_itm", return_value=None), \
             patch.object(csr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(csr, "send_telegram_message", return_value=True), \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            csr.process_symbol("fake_token", "BANKNIFTY")
            assert mock_select.called
            # round(51930/100)*100 = 51900 -- जुनी बग round(51930/50)*50 = 51950 देत होती
            assert mock_select.call_args.args[2] == 51900
            assert mock_select.call_args.kwargs.get("step") == 100

    def test_swing_gate_enabled_blocks_entry_without_confluence(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(swing_confluence_enabled=True)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "open_multi_leg_trade") as mock_trade, \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_SWING_CONFLUENCE_GATE" in statuses

    def test_demand_supply_gate_enabled_blocks_entry_without_zone(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(demand_supply_gate_enabled=True)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "open_multi_leg_trade") as mock_trade, \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_DEMAND_SUPPLY_GATE" in statuses

    def test_trendline_gate_enabled_blocks_entry_when_broken(self):
        broken_trendline_candles = pd.DataFrame(_flat_bars(_ZIGZAG_WITH_BROKEN_ASCENDING_TRENDLINE,
                                                             start_ts="2026-09-11 05:15:00"))
        zone_matching_zigzag = pd.DataFrame([
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 100.0, "zone_high": 100.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(trendline_gate_enabled=True, entry_rsi_gate_enabled=False, swing_order=3)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=zone_matching_zigzag), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=broken_trendline_candles), \
             patch.object(csr, "open_multi_leg_trade") as mock_trade, \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_TRENDLINE_BROKEN" in statuses

    def test_naked_trade_uses_same_already_passed_gates_no_recheck(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — "एकत्रित — दोन्हीला एकच गेट" — गेट्स (RSI +
        Entry Refinement) एकदाच तपासले जातात, त्यानंतर Credit Spread आणि Naked दोन्ही व्यवहार त्याच
        सिग्नलवर पुढे जातात (naked साठी गेट्स पुन्हा वेगळे तपासले जात नाहीत)."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "fetch_option_expiries", return_value=[]), \
             patch.object(csr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(csr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(csr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}) as mock_naked_select, \
             patch.object(csr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(csr, "send_telegram_message", return_value=True), \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            csr.process_symbol("fake_token", "NIFTY")
            assert mock_naked_select.called
            assert mock_trade.call_count == 2  # स्प्रेड + Naked, दोन्ही एकाच पास झालेल्या गेट्सवर

    def test_naked_lots_used_independently_from_spread_lots(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा — dynamic_sr_instant_trader.py प्रमाणेच इथेही —
        Naked Option Trade आता Credit Spread पासून स्वतंत्र "naked_lots" वापरतो."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(lots=2, naked_lots=5)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "fetch_option_expiries", return_value=[]), \
             patch.object(csr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(csr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(csr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}), \
             patch.object(csr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(csr, "send_telegram_message", return_value=True), \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            csr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 2
            spread_call, naked_call = mock_trade.call_args_list
            assert spread_call.kwargs.get("lots") == 2
            assert naked_call.kwargs.get("lots") == 5

    def test_naked_disabled_only_spread_trades(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings(naked_enabled=False)), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "fetch_option_expiries", return_value=[]), \
             patch.object(csr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(csr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(csr, "select_naked_option_itm") as mock_naked_select, \
             patch.object(csr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(csr, "send_telegram_message", return_value=True), \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)):
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_naked_select.called
            assert mock_trade.call_count == 1

    def test_max_2_hits_reached_skipped(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "open_multi_leg_trade") as mock_trade, \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now())):
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_previous_open_position_blocks_entry(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(csr, "fetch_candles", return_value=candles_touch), \
             patch.object(csr, "open_multi_leg_trade") as mock_trade, \
             patch.object(csr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(csr.cloud_db, "get_zone_hits_today", return_value=(0, None)), \
             patch.object(csr, "has_open_trade_from_source", return_value=True):
            csr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_no_zones_handled_gracefully(self):
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=None):
            result = csr.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result or "नाहीत" in result

    def test_no_candles_handled_gracefully(self):
        with patch.object(csr.cloud_db, "get_strategy_settings", return_value=self._settings()), \
             patch.object(csr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(csr, "fetch_candles", return_value=pd.DataFrame()):
            result = csr.process_symbol("fake_token", "NIFTY")
            assert "मिळाले नाहीत" in result


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

        monkeypatch.setattr(csr, "process_symbol", fake_process_symbol)
        mock_notify = MagicMock()
        monkeypatch.setattr(csr, "notify_error", mock_notify)

        result = csr.run_all_symbols("fake_token", ["NIFTY", "BANKNIFTY", "SENSEX"])

        assert calls == ["NIFTY", "BANKNIFTY", "SENSEX"]
        assert result is True
        assert mock_notify.called
        assert "BANKNIFTY" in mock_notify.call_args.args[1]

    def test_all_symbols_failing_returns_false(self, monkeypatch):
        def fake_process_symbol(token, symbol):
            raise RuntimeError("boom")

        monkeypatch.setattr(csr, "process_symbol", fake_process_symbol)
        monkeypatch.setattr(csr, "notify_error", MagicMock())

        result = csr.run_all_symbols("fake_token", ["NIFTY", "BANKNIFTY"])
        assert result is False
