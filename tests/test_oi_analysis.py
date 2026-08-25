"""
tests/test_oi_analysis.py
-----------------------------
OI Signal Confirmation logic — इथेच खरा "flip-flop" bug सापडला होता (screenshot दाखवून तुम्ही
दाखवून दिला होता), आणि इथेच Put/Call Writing/Buying/Covering classification आहे.
"""
import pandas as pd
import pytest

from oi_analysis import (
    compute_oi_signal_with_hysteresis, classify_oi_price_action, generate_oi_price_signal,
    check_oi_diff_entry_gate,
)


class TestOISignalStability:
    """दिशा बदलण्यासाठी सलग ३ स्नॅपशॉट्स तीच नवीन दिशा हवी — नुसती एकदाच उलट दिशा दिसली की जुनाच सिग्नल कायम."""

    def test_first_snapshot_no_history_gives_safe_default(self):
        empty = pd.DataFrame(columns=["diff", "total_put_oi", "total_call_oi", "signal"])
        result = compute_oi_signal_with_hysteresis(5000000, 100, 90, empty)
        assert result == "🟡 BULLISH (Weakening)"  # baseline नाही -> सुरक्षित डीफॉल्ट

    def test_same_direction_updates_immediately(self):
        history = pd.DataFrame([
            {"diff": -100, "total_put_oi": 500, "total_call_oi": 600, "signal": "🔴 BEARISH (Strong)"},
            {"diff": -110, "total_put_oi": 505, "total_call_oi": 620, "signal": "🔴 BEARISH (Strong)"},
            {"diff": -105, "total_put_oi": 508, "total_call_oi": 615, "signal": "🟠 BEARISH (Weakening)"},
        ])
        result = compute_oi_signal_with_hysteresis(-108, 512, 610, history)
        assert "BEARISH" in result

    def test_single_reversal_does_not_flip_signal(self):
        """हाच तो bug -- एकदाच उलट दिशा (BULLISH) दिसली, पण जुनाच (BEARISH) सिग्नल कायम राहायला हवा."""
        history = pd.DataFrame([
            {"diff": -100, "total_put_oi": 500, "total_call_oi": 600, "signal": "🔴 BEARISH (Strong)"},
            {"diff": -80, "total_put_oi": 505, "total_call_oi": 620, "signal": "🔴 BEARISH (Strong)"},
            {"diff": -50, "total_put_oi": 508, "total_call_oi": 615, "signal": "🔴 BEARISH (Strong)"},
        ])
        result = compute_oi_signal_with_hysteresis(20, 520, 610, history)
        assert "BEARISH" in result  # फक्त १ वेळा धन झालं म्हणून लगेच BULLISH कडे उडी मारायला नको

    def test_three_consecutive_new_direction_confirms_flip(self):
        history = pd.DataFrame([
            {"diff": -50, "total_put_oi": 508, "total_call_oi": 615, "signal": "🔴 BEARISH (Strong)"},
            {"diff": 10, "total_put_oi": 515, "total_call_oi": 610, "signal": "🔴 BEARISH (Strong)"},
            {"diff": 15, "total_put_oi": 518, "total_call_oi": 608, "signal": "🔴 BEARISH (Strong)"},
        ])
        result = compute_oi_signal_with_hysteresis(25, 522, 605, history)
        assert "BULLISH" in result  # सलग ३ वेळा नवीन दिशा -> आता खरंच बदलायला हवं

    def test_real_screenshot_sequence_stays_stable(self):
        """वापरकर्त्याच्याच screenshot मधली खरी परिस्थिती -- एकदाच धन Diff आलं तरी सिग्नल स्थिरच राहायला हवा."""
        history = pd.DataFrame(columns=["diff", "total_put_oi", "total_call_oi", "signal"])
        seq = [(-13093015, 121990765, 149084395), (4930510, 81855150, 76924640)]
        for diff, put_oi, call_oi in seq:
            sig = compute_oi_signal_with_hysteresis(diff, put_oi, call_oi, history)
            history = pd.concat([history, pd.DataFrame([{"diff": diff, "total_put_oi": put_oi, "total_call_oi": call_oi, "signal": sig}])], ignore_index=True)
        assert "BEARISH" in history["signal"].iloc[-1]  # BULLISH कडे उगाच उडी मारली नाही


class TestOIEntryGateCompatibility:
    """नवीन signal-string फॉरमॅट (Strong/Weakening) सह check_oi_diff_entry_gate अजूनही बरोबर वाचतो का."""

    @pytest.mark.parametrize("signal,bullish_expected,bearish_expected", [
        ("🟢 BULLISH (Strong)", True, False),
        ("🟡 BULLISH (Weakening)", False, True),
        ("🔴 BEARISH (Strong)", False, True),
        ("🟠 BEARISH (Weakening)", True, False),
        ("⚪ NEUTRAL", False, False),
    ])
    def test_entry_gate_reads_signal_correctly(self, signal, bullish_expected, bearish_expected):
        assert check_oi_diff_entry_gate("BULLISH", signal) == bullish_expected
        assert check_oi_diff_entry_gate("BEARISH", signal) == bearish_expected


class TestOIPriceActionClassification:
    """Put/Call Writing/Buying/Short-Covering/Long-Unwinding — OI+Premium Matrix."""

    def test_oi_up_premium_down_is_writing(self):
        result = classify_oi_price_action(current_oi=90000000, prev_oi=85000000, current_premium=4000, prev_premium=4200)
        assert "Writing" in result

    def test_oi_up_premium_up_is_buying(self):
        result = classify_oi_price_action(current_oi=90000000, prev_oi=85000000, current_premium=4200, prev_premium=4000)
        assert "Buying" in result

    def test_put_writing_plus_call_covering_is_bullish(self):
        """वापरकर्त्याच्याच उदाहरणाशी जुळणारा -- Don't Short Call, Nifty is Bullish."""
        put_class = classify_oi_price_action(90000000, 85000000, 4000, 4200)
        call_class = classify_oi_price_action(70000000, 75000000, 3200, 3000)
        direction, message = generate_oi_price_signal(put_class, call_class)
        assert direction == "BULLISH"
        assert "Don't Short" in message
