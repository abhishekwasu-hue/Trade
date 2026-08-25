"""
tests/test_strategy_selection.py
------------------------------------
strategy.py — Strike Selection (PoP-आधारित + निश्चित ATM+2/Hedge+4) आणि Position Sizing.
"""
from strategy import select_credit_spread, select_credit_spread_fixed_strikes, compute_position_size


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
