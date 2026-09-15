"""
tests/test_strategy_selection.py
------------------------------------
strategy.py — Strike Selection (PoP-आधारित + निश्चित ATM+2/Hedge+4) आणि Position Sizing.
"""
from strategy import select_credit_spread, select_credit_spread_fixed_strikes, select_credit_spread_itm, select_naked_option_itm, compute_position_size


class TestFixedStrikeSelection:
    """ATM+2 Short / +100pt Hedge — Price Action/Indicator साठी (वापरकर्त्याशी चर्चा करून ठरवलेलं)."""

    def test_bullish_gives_bull_put_spread_with_correct_strikes(self, sample_option_chain):
        result = select_credit_spread_fixed_strikes(sample_option_chain, "BULLISH", atm_strike=24500)
        assert result["strategy"] == "BULL_PUT_SPREAD"
        assert result["short_leg"]["strike"] == 24400  # ATM - 2*50
        assert result["long_leg"]["strike"] == 24300    # short - 100

    def test_bearish_gives_bear_call_spread_with_correct_strikes(self, sample_option_chain):
        result = select_credit_spread_fixed_strikes(sample_option_chain, "BEARISH", atm_strike=24500)
        assert result["strategy"] == "BEAR_CALL_SPREAD"
        assert result["short_leg"]["strike"] == 24600  # ATM + 2*50
        assert result["long_leg"]["strike"] == 24700    # short + 100

    def test_max_profit_equals_net_credit(self, sample_option_chain):
        """हे तत्त्व critical आहे -- target_pct_of_max_profit=30 दिल्यास आपोआप 'credit च्या 30%' ठरतं."""
        result = select_credit_spread_fixed_strikes(sample_option_chain, "BULLISH", atm_strike=24500)
        assert result["max_profit"] == result["net_credit"]

    def test_invalid_direction_returns_none(self, sample_option_chain):
        assert select_credit_spread_fixed_strikes(sample_option_chain, "SIDEWAYS", atm_strike=24500) is None

    def test_missing_strike_returns_none(self, sample_option_chain):
        result = select_credit_spread_fixed_strikes(sample_option_chain, "BULLISH", atm_strike=99999)
        assert result is None


class TestPoPBasedStrikeSelection:
    """Iron Condor/Butterfly साठी अजूनही वापरली जाणारी जुनी PoP-आधारित पद्धत."""

    def test_pop_based_selection_respects_threshold(self, sample_option_chain):
        result = select_credit_spread(sample_option_chain, "BULLISH", hedge_width_points=100, pop_threshold_pct=50)
        if result:  # sample_option_chain मध्ये सर्व pop=0.6 आहे, त्यामुळे मिळायला हवं
            assert result["short_pop_pct"] >= 50


class TestPositionSizing:
    def test_normal_calculation(self):
        lots, risk_amount = compute_position_size(available_margin=100000, risk_pct=2, max_loss_per_unit=50, lot_size=75)
        assert risk_amount == 2000  # 100000 * 2%
        assert lots == 0  # 2000 / (50*75=3750) = 0.53 -> floor -> 0

    def test_zero_margin_returns_zero(self):
        lots, risk_amount = compute_position_size(available_margin=0, risk_pct=2, max_loss_per_unit=50, lot_size=75)
        assert lots == 0


class TestITMCreditSpreadSelection:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) — Short leg
    आता ATM पासून ITM दिशेने (OTM ऐवजी)."""

    def test_bullish_short_put_is_above_atm_itm(self, sample_option_chain):
        result = select_credit_spread_itm(sample_option_chain, "BULLISH", atm_strike=24500,
                                           itm_depth_points=100, hedge_width_points=150)
        assert result["strategy"] == "BULL_PUT_SPREAD"
        assert result["short_leg"]["strike"] == 24600  # ATM + 100 (Put ITM -- strike ATM पेक्षा वर)
        assert result["long_leg"]["strike"] == 24450    # short - 150 (hedge, existing दिशेनेच)

    def test_bearish_short_call_is_below_atm_itm(self, sample_option_chain):
        result = select_credit_spread_itm(sample_option_chain, "BEARISH", atm_strike=24500,
                                           itm_depth_points=100, hedge_width_points=150)
        assert result["strategy"] == "BEAR_CALL_SPREAD"
        assert result["short_leg"]["strike"] == 24400  # ATM - 100 (Call ITM -- strike ATM पेक्षा खाली)
        assert result["long_leg"]["strike"] == 24550    # short + 150

    def test_invalid_direction_returns_none(self, sample_option_chain):
        assert select_credit_spread_itm(sample_option_chain, "SIDEWAYS", atm_strike=24500, itm_depth_points=100) is None

    def test_missing_strike_returns_none(self, sample_option_chain):
        result = select_credit_spread_itm(sample_option_chain, "BULLISH", atm_strike=99999, itm_depth_points=100)
        assert result is None


class TestNakedOptionSelection:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Naked Option Trade / "Long With Hedge") —
    डीफॉल्ट hedge_enabled=False (निव्वळ खरेदी), वापरकर्त्याने सक्रिय केल्यासच hedge जोडली जाते."""

    def test_bullish_naked_buys_itm_call(self, sample_option_chain):
        result = select_naked_option_itm(sample_option_chain, "BULLISH", atm_strike=24500, itm_depth_points=100)
        assert result["strategy"] == "NAKED_CALL"
        assert result["buy_leg"]["strike"] == 24400  # ATM - 100 (Call ITM)
        assert "hedge_leg" not in result
        assert result["net_credit"] < 0  # ऋण (debit) -- खरेदीसाठी दिलेली रक्कम

    def test_bearish_naked_buys_itm_put(self, sample_option_chain):
        result = select_naked_option_itm(sample_option_chain, "BEARISH", atm_strike=24500, itm_depth_points=100)
        assert result["strategy"] == "NAKED_PUT"
        assert result["buy_leg"]["strike"] == 24600  # ATM + 100 (Put ITM)
        assert "hedge_leg" not in result

    def test_hedge_enabled_adds_sell_leg(self, sample_option_chain):
        result = select_naked_option_itm(sample_option_chain, "BULLISH", atm_strike=24500,
                                          itm_depth_points=100, hedge_enabled=True, hedge_width_points=150)
        assert result["strategy"] == "NAKED_CALL"
        assert "hedge_leg" in result
        assert result["hedge_leg"]["strike"] == 24550  # buy_strike(24400) + 150
        assert result["net_credit"] < 0  # अजूनही debit (buy_leg महाग, hedge_leg स्वस्त)

    def test_hedge_disabled_by_default(self, sample_option_chain):
        result = select_naked_option_itm(sample_option_chain, "BEARISH", atm_strike=24500, itm_depth_points=100)
        assert "hedge_leg" not in result  # hedge_enabled डीफॉल्ट False

    def test_invalid_direction_returns_none(self, sample_option_chain):
        assert select_naked_option_itm(sample_option_chain, "SIDEWAYS", atm_strike=24500, itm_depth_points=100) is None
