"""
tests/test_slippage.py
--------------------------
Slippage Modeling — backtest आर्थिक वास्तवता. slippage_pct=0 (डीफॉल्ट) दिल्यास पूर्णपणे
backward-compatible (जुने निकाल बदलत नाहीत), slippage_pct>0 दिल्यास व्यापाऱ्याच्याच विरोधात काम करतो.
"""
from backtest import apply_slippage


class TestApplySlippage:
    def test_zero_slippage_returns_unchanged_price(self):
        assert apply_slippage(24000, "BULLISH", "ENTRY", slippage_pct=0) == 24000

    def test_bullish_entry_costs_more(self):
        assert apply_slippage(24000, "BULLISH", "ENTRY", slippage_pct=0.05) > 24000

    def test_bullish_exit_receives_less(self):
        assert apply_slippage(24000, "BULLISH", "EXIT", slippage_pct=0.05) < 24000

    def test_bearish_entry_receives_less(self):
        assert apply_slippage(24000, "BEARISH", "ENTRY", slippage_pct=0.05) < 24000

    def test_bearish_exit_costs_more(self):
        assert apply_slippage(24000, "BEARISH", "EXIT", slippage_pct=0.05) > 24000
