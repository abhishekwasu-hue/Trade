"""
tests/test_oi_analysis.py
-----------------------------
OI Signal Confirmation logic — इथेच खरा "flip-flop" bug सापडला होता (screenshot दाखवून तुम्ही
दाखवून दिला होता), आणि इथेच Put/Call Writing/Buying/Covering classification आहे.
"""
import pandas as pd
import pytest
import sqlite3
import tempfile
from unittest.mock import patch

import oi_analysis
from oi_analysis import (
    compute_oi_signal_with_hysteresis, classify_oi_price_action, generate_oi_price_signal,
    check_oi_diff_entry_gate, reconcile_with_diff_level, is_genuine_rotation, rotation_confirmed_for_2_snapshots,
    compute_pcr_signal, compute_pcr_zone_label, aggregate_oi_history, get_latest_pcr, check_pcr_gate,
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
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — आता फक्त सलग ३ वेळा नवीन Diff-दिशा पुरेशी नाही,
        Call/Put OI चं खरं rotation (विरुद्ध दिशेने, सलग २ वेळा, २%+ बदल) सुद्धा असायलाच हवं. Call OI
        615->610->600->580 (मोठी घट) आणि Put OI 508->520->545->570 (मोठी वाढ) -- स्पष्ट Bullish rotation."""
        history = pd.DataFrame([
            {"diff": -50, "total_put_oi": 508, "total_call_oi": 615, "signal": "🔴 BEARISH (Strong)"},
            {"diff": 10, "total_put_oi": 520, "total_call_oi": 600, "signal": "🔴 BEARISH (Strong)"},
            {"diff": 15, "total_put_oi": 545, "total_call_oi": 580, "signal": "🔴 BEARISH (Strong)"},
        ])
        result = compute_oi_signal_with_hysteresis(25, 570, 555, history)
        assert "BULLISH" in result  # सलग ३ वेळा नवीन दिशा + खरं rotation दोन्ही -> आता खरंच बदलायला हवं
        assert "Weakening" not in result

    def test_real_screenshot_sequence_stays_stable(self):
        """वापरकर्त्याच्याच screenshot मधली खरी परिस्थिती -- एकदाच धन Diff आलं तरी सिग्नल स्थिरच राहायला हवा."""
        history = pd.DataFrame(columns=["diff", "total_put_oi", "total_call_oi", "signal"])
        seq = [(-13093015, 121990765, 149084395), (4930510, 81855150, 76924640)]
        for diff, put_oi, call_oi in seq:
            sig = compute_oi_signal_with_hysteresis(diff, put_oi, call_oi, history)
            history = pd.concat([history, pd.DataFrame([{"diff": diff, "total_put_oi": put_oi, "total_call_oi": call_oi, "signal": sig}])], ignore_index=True)
        assert "BEARISH" in history["signal"].iloc[-1]  # BULLISH कडे उगाच उडी मारली नाही

    def test_held_signal_never_shows_strong_when_contradicted(self):
        """
        🎓 वापरकर्त्याने खऱ्या Dashboard च्या screenshot मध्ये सापडवलेला खरा bug — held (अजून पुष्टी न
        झालेल्या) स्थितीत, Diff खोलवर उलट दिशेत गेला असतानाही (उदा. -50L), जुनं संपूर्ण "Strong" string
        जसंच्या तसं दाखवलं जायचं. आता 'Weakening' दाखवायला हवं, कधीच 'Strong' नाही, जोपर्यंत खरी पुष्टी
        (सलग confirm_count वेळा) होत नाही.
        """
        history = pd.DataFrame([
            {"diff": 26.90e5, "total_put_oi": 134.13e5, "total_call_oi": 107.24e5, "signal": "🟢 BULLISH (Strong)"},
            {"diff": 14.96e5, "total_put_oi": 111.32e5, "total_call_oi": 96.36e5, "signal": "🟢 BULLISH (Strong)"},
            {"diff": 3.13e5, "total_put_oi": 152.58e5, "total_call_oi": 149.45e5, "signal": "🟢 BULLISH (Strong)"},
        ])
        # 12:20 -- मोठा ऋण Diff, पहिल्यांदाच (अजून पुष्टी झालेली नाही)
        result = compute_oi_signal_with_hysteresis(-45.44e5, 135.40e5, 180.85e5, history)
        assert "Strong" not in result
        assert "Weakening" in result
        assert "BULLISH" in result  # दिशा अजूनही जुनीच (BULLISH), फक्त आत्मविश्वास कमी दाखवला

    def test_full_real_sequence_never_contradicts_diff_sign(self):
        """
        🎓 वापरकर्त्याच्याच दुसऱ्या screenshot मधली संपूर्ण, खरी सलगता (08:50 ते 09:40, दिशा दोनदा
        उलटण्याचा प्रयत्न करणारी, एक खरी same-direction पुष्टी (09:20) सहित) — कुठल्याही क्षणी धन Diff
        असताना 'BEARISH (Strong)' किंवा ऋण Diff असताना 'BULLISH (Strong)' दिसता कामा नये.
        """
        sequence = [
            ("08:50", -15.10e5, 285.56e5, 300.67e5), ("09:00", -15.10e5, 285.56e5, 300.67e5),
            ("09:10", 44.33e5, 405.41e5, 361.07e5), ("09:20", -28.25e5, 385.24e5, 413.49e5),
            ("09:30", 11.18e5, 457.15e5, 445.97e5), ("09:40", 70.71e5, 511.57e5, 440.85e5),
        ]
        history = pd.DataFrame(columns=["diff", "total_put_oi", "total_call_oi", "signal"])
        for _, diff, put_oi, call_oi in sequence:
            sig = compute_oi_signal_with_hysteresis(diff, put_oi, call_oi, history)
            if diff > 0:
                assert not ("BEARISH" in sig and "Strong" in sig), f"धन Diff={diff} तरी BEARISH(Strong): {sig}"
            elif diff < 0:
                assert not ("BULLISH" in sig and "Strong" in sig), f"ऋण Diff={diff} तरी BULLISH(Strong): {sig}"
            history = pd.concat([history, pd.DataFrame([{"diff": diff, "total_put_oi": put_oi, "total_call_oi": call_oi, "signal": sig}])], ignore_index=True)


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

    def test_bearish_advice_is_not_logically_backwards(self):
        """
        🎓 वापरकर्त्याने खऱ्या Dashboard च्या screenshot मध्ये सापडवलेला खरा bug — Bearish संदेशात
        चुकून 'Don't Long Put' लिहिलं होतं, जे उलटं (logically backwards) आहे — Bearish असेल तर
        Put खरेदी करणे हीच योग्य कृती आहे, टाळायची नाही. योग्य सल्ला 'Don't Short Put' आहे (BULLISH च्या
        'Don't Short Call' शी सममित तर्क — ज्या दिशेने नफा होईल ती बाजू विकू नका).
        """
        direction, message = generate_oi_price_signal("Put Buying वाढतंय", "अपुरा डेटा")
        assert direction == "BEARISH"
        assert "Don't Short Put" in message
        assert "Long Put" not in message  # जुनी, चुकीची (उलट) फ्रेजिंग आता कुठेच नसावी


class TestReconcileWithDiffLevel:
    """
    🎓 वापरकर्त्याने प्रत्यक्ष Dashboard च्या screenshot मध्ये दाखवलेली खरी विसंगती — गती (momentum,
    Call Writing वाढतंय → Bearish) आणि एकूण पातळी (Diff, Put OI कडे मोठा कल → Bullish) परस्परविरोधी
    असतानाही banner एकतर्फी BEARISH दाखवत होता. आता असा मोठा (क्षुल्लक नाही) फरक असेल तर MIXED दाखवायला हवं.
    """

    def test_users_exact_screenshot_scenario_gives_mixed(self):
        direction, message = reconcile_with_diff_level(
            "BEARISH", "🔴 Call Writing वाढतंय → Don't Short Put, Nifty is Bearish",
            current_diff=71246000, total_call_oi=182521000, total_put_oi=253767000,
        )
        assert direction == "MIXED"
        assert "संमिश्र" in message

    def test_consistent_direction_and_diff_stays_unchanged(self):
        """गती आणि Diff दोन्ही एकाच दिशेने असतील (सुसंगत) तर बदलता कामा नये."""
        direction, message = reconcile_with_diff_level(
            "BEARISH", "मूळ संदेश", current_diff=-50000000, total_call_oi=200000000, total_put_oi=150000000,
        )
        assert direction == "BEARISH"
        assert message == "मूळ संदेश"

    def test_trivial_disagreement_below_threshold_stays_unchanged(self):
        """फरक threshold पेक्षा कमी (क्षुल्लक) असेल तर बदलता कामा नये."""
        direction, message = reconcile_with_diff_level(
            "BEARISH", "मूळ संदेश", current_diff=5000000, total_call_oi=200000000, total_put_oi=210000000,
        )
        assert direction == "BEARISH"

    def test_neutral_direction_never_gets_overridden(self):
        """NEUTRAL स्थितीत reconciliation लागूच होता कामा नये (contradiction फक्त BULLISH/BEARISH साठी)."""
        direction, message = reconcile_with_diff_level(
            "NEUTRAL", "मूळ संदेश", current_diff=100000000, total_call_oi=100000000, total_put_oi=300000000,
        )
        assert direction == "NEUTRAL"

    def test_zero_total_oi_does_not_crash(self):
        direction, message = reconcile_with_diff_level("BEARISH", "मूळ संदेश", current_diff=0, total_call_oi=0, total_put_oi=0)
        assert direction == "BEARISH"

    def test_users_second_screenshot_banner_vs_stable_signal_gives_mixed(self):
        """
        🎓 वापरकर्त्याने दुसऱ्या screenshot मध्ये दाखवलेली विसंगती — Banner "Bullish" म्हणत असतानाच,
        Signal column मध्ये सलग ३ स्नॅपशॉट्स "BEARISH (Strong)" (hysteresis-confirmed, जास्त
        विश्वासार्ह) दाखवत होते. आता हे स्थिर, पुष्टी झालेल्या Signal शीही तपासलं जातं.
        """
        direction, message = reconcile_with_diff_level(
            "BULLISH", "🟢 Put Unwinding + Call Short Covering → Don't Short Call, Nifty is Bullish",
            current_diff=-50000000, total_call_oi=200000000, total_put_oi=150000000,
            stable_signal="🔴 BEARISH (Strong)",
        )
        assert direction == "MIXED"
        assert "स्थिर" in message

    def test_stable_signal_agreeing_does_not_override(self):
        """Banner आणि स्थिर Signal एकाच दिशेने असतील तर बदलता कामा नये."""
        direction, message = reconcile_with_diff_level(
            "BULLISH", "मूळ संदेश", current_diff=50000000, total_call_oi=150000000, total_put_oi=200000000,
            stable_signal="🟢 BULLISH (Strong)",
        )
        assert direction == "BULLISH"
        assert message == "मूळ संदेश"

    def test_no_stable_signal_provided_falls_back_to_diff_only_check(self):
        """stable_signal दिलं नाही (जुने callers) तर आधीचीच (फक्त Diff-आधारित) तपासणी चालायला हवी."""
        direction, message = reconcile_with_diff_level(
            "BEARISH", "मूळ संदेश", current_diff=71246000, total_call_oi=182521000, total_put_oi=253767000,
        )
        assert direction == "MIXED"  # जुनी Diff-आधारित तपासणीच लागू झाली


class TestRotationLogic:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Signal ची दिशा तेव्हाच खरंच बदलावी जेव्हा Call OI
    आणि Put OI विरुद्ध दिशेने (एक वाढतोय, दुसरा घटतोय), सलग २ स्नॅपशॉट्समध्ये, आणि क्षुल्लक (noise)
    नसलेला बदल दाखवतात — नुसती Diff ची दिशा सलग ३ वेळा दिसणं (जुना नियम) आता पुरेसं नाही.
    """

    def test_call_up_put_down_is_bearish_rotation(self):
        assert is_genuine_rotation(call_oi_now=1100, call_oi_prev=1000, put_oi_now=1400, put_oi_prev=1500) == "BEARISH"

    def test_call_down_put_up_is_bullish_rotation(self):
        assert is_genuine_rotation(call_oi_now=900, call_oi_prev=1000, put_oi_now=1600, put_oi_prev=1500) == "BULLISH"

    def test_both_increasing_is_not_rotation(self):
        assert is_genuine_rotation(call_oi_now=1100, call_oi_prev=1000, put_oi_now=1600, put_oi_prev=1500) is None

    def test_both_decreasing_is_not_rotation(self):
        assert is_genuine_rotation(call_oi_now=900, call_oi_prev=1000, put_oi_now=1400, put_oi_prev=1500) is None

    def test_trivial_change_below_threshold_is_not_rotation(self):
        """०.५% सारखा क्षुल्लक बदल -- खरं rotation मानता कामा नये (noise)."""
        assert is_genuine_rotation(call_oi_now=1005, call_oi_prev=1000, put_oi_now=1497, put_oi_prev=1500) is None

    def test_missing_previous_data_returns_none_safely(self):
        assert is_genuine_rotation(call_oi_now=1000, call_oi_prev=None, put_oi_now=1500, put_oi_prev=1500) is None
        assert is_genuine_rotation(call_oi_now=1000, call_oi_prev=0, put_oi_now=1500, put_oi_prev=1500) is None

    def test_rotation_confirmed_needs_both_consecutive_comparisons_to_agree(self):
        """सलग दोन्ही तुलनांमध्ये (t-2->t-1, t-1->t) तीच rotation दिशा दिसली तरच confirmed."""
        history = [(1000, 1500), (950, 1560), (900, 1620)]  # दोन्ही वेळा स्पष्ट Bullish rotation
        assert rotation_confirmed_for_2_snapshots(history) == "BULLISH"

    def test_rotation_confirmed_fails_if_only_one_comparison_shows_rotation(self):
        history = [(1000, 1500), (950, 1560), (970, 1540)]  # पहिली तुलना Bullish, दुसरी उलट
        assert rotation_confirmed_for_2_snapshots(history) is None

    def test_rotation_confirmed_needs_minimum_3_rows(self):
        history = [(1000, 1500), (950, 1560)]  # फक्त २ रांगा, १ तुलनाच शक्य
        assert rotation_confirmed_for_2_snapshots(history) is None

    def test_full_signal_flip_requires_both_diff_confirmation_and_rotation(self):
        """
        🎓 मुख्य एकत्रित चाचणी — Diff सलग ३ वेळा नवीन दिशेत आहे, पण Call/Put OI चं rotation खरं
        नाही (क्षुल्लक बदल) -- अशावेळी दिशा बदलता कामा नये, जुनीच दिशा (Weakening सह) कायम राहायला हवी.
        """
        history = pd.DataFrame([
            {"diff": -50, "total_put_oi": 508, "total_call_oi": 615, "signal": "🔴 BEARISH (Strong)"},
            {"diff": 10, "total_put_oi": 509, "total_call_oi": 614, "signal": "🔴 BEARISH (Strong)"},  # क्षुल्लक बदल
            {"diff": 15, "total_put_oi": 510, "total_call_oi": 613, "signal": "🔴 BEARISH (Strong)"},  # क्षुल्लक बदल
        ])
        result = compute_oi_signal_with_hysteresis(25, 511, 612, history)
        assert "BULLISH" not in result  # Diff सलग ३ वेळा बदलला असला तरी, खरं rotation नसल्याने दिशा बदलली नाही
        assert "Weakening" in result


class TestComputePCRSignal:
    """
    🎓 वापरकर्त्याशी चर्चा करून अंतिम ठरवलेली ५-पट्ट्यांची PCR Logic ("Neutral" नाही, SIDEWAYS):
    <0.70 Bullish(Oversold) . 0.70-0.90 Bearish . 0.90-1.0 Sideways . 1.0-1.3 Bullish . >1.3 Bearish(Overbought)
    """

    def test_below_0_70_is_bullish_oversold(self):
        pcr, bias = compute_pcr_signal(total_put_oi=600, total_call_oi=1000)
        assert pcr == 0.6
        assert bias == "BULLISH"

    def test_0_70_to_0_90_is_bearish(self):
        pcr, bias = compute_pcr_signal(total_put_oi=800, total_call_oi=1000)
        assert pcr == 0.8
        assert bias == "BEARISH"

    def test_0_90_to_1_0_is_sideways(self):
        pcr, bias = compute_pcr_signal(total_put_oi=950, total_call_oi=1000)
        assert pcr == 0.95
        assert bias == "SIDEWAYS"

    def test_1_0_to_1_3_is_bullish(self):
        pcr, bias = compute_pcr_signal(total_put_oi=1150, total_call_oi=1000)
        assert pcr == 1.15
        assert bias == "BULLISH"

    def test_above_1_3_is_bearish_overbought(self):
        pcr, bias = compute_pcr_signal(total_put_oi=1500, total_call_oi=1000)
        assert pcr == 1.5
        assert bias == "BEARISH"

    def test_boundary_0_70_is_bearish(self):
        pcr, bias = compute_pcr_signal(total_put_oi=700, total_call_oi=1000)
        assert pcr == 0.7
        assert bias == "BEARISH"

    def test_boundary_0_90_is_sideways(self):
        pcr, bias = compute_pcr_signal(total_put_oi=900, total_call_oi=1000)
        assert pcr == 0.9
        assert bias == "SIDEWAYS"

    def test_boundary_1_00_is_sideways(self):
        pcr, bias = compute_pcr_signal(total_put_oi=1000, total_call_oi=1000)
        assert pcr == 1.0
        assert bias == "SIDEWAYS"

    def test_boundary_1_30_is_bullish(self):
        pcr, bias = compute_pcr_signal(total_put_oi=1300, total_call_oi=1000)
        assert pcr == 1.3
        assert bias == "BULLISH"

    def test_zero_call_oi_returns_none_safely(self):
        pcr, bias = compute_pcr_signal(total_put_oi=1000, total_call_oi=0)
        assert pcr is None
        assert bias == "NEUTRAL"


class TestComputePcrZoneLabel:
    """🎓 वापरकर्त्याने Dashboard वरून सापडवलेली bug — banner established bias (फक्त BULLISH/BEARISH)
    बघून संदेश निवडायचा, त्यामुळे PCR 0.70-0.90 (सौम्य Bearish) लाही चुकून "Overbought" दिसायचं.
    compute_pcr_zone_label() आता प्रत्यक्ष PCR किमतीवरून (५ वेगळ्या पट्ट्या) अचूक संदेश देतं."""

    def test_below_0_70_says_oversold_not_generic_bullish(self):
        label = compute_pcr_zone_label(0.6)
        assert "Oversold" in label
        assert "Bullish" not in label  # 🎓 contrarian इशारा आहे, ठाम दिशा-निश्चिती नाही

    def test_0_70_to_0_90_says_mild_bearish_pointing_to_oversold(self):
        # 🎓 गाभा टेस्ट — नेमकी वापरकर्त्याने सापडवलेली bug (PCR=0.88) + दिशा-फिक्स (PCR=0.78)
        label = compute_pcr_zone_label(0.88)
        assert label != compute_pcr_zone_label(1.5)  # खरा Overbought (>1.3) पेक्षा वेगळाच संदेश हवा
        assert "सौम्य" in label
        assert "Oversold" in label  # established योग्य (जवळचं) टोक — Overbought नाही
        assert "Overbought" not in label

    def test_0_90_to_1_0_says_sideways(self):
        label = compute_pcr_zone_label(0.95)
        assert "Sideways" in label or "श्रेणीबद्ध" in label

    def test_1_0_to_1_3_says_mild_bullish_pointing_to_overbought(self):
        label = compute_pcr_zone_label(1.15)
        assert label != compute_pcr_zone_label(0.6)  # खरा Oversold (<0.70) पेक्षा वेगळाच संदेश हवा
        assert "सौम्य" in label
        assert "Overbought" in label  # established योग्य (जवळचं) टोक — Oversold नाही
        assert "Oversold" not in label

    def test_above_1_3_says_true_overbought(self):
        label = compute_pcr_zone_label(1.5)
        assert "Overbought" in label
        assert "Bearish" not in label  # 🎓 contrarian इशारा आहे, ठाम दिशा-निश्चिती नाही

    def test_none_pcr_returns_insufficient_data(self):
        label = compute_pcr_zone_label(None)
        assert "अपुरा डेटा" in label


class TestAggregateOIHistory:
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Dashboard वर 5/10/15-मिनिट selectable views साठी,
    established ५-मिनिट snapshots ना पुन्हा-गटबद्ध करणे. OI "cumulative" असल्याने, प्रत्येक bucket
    साठी शेवटची (सर्वात अलीकडची) value घ्यायची -- बेरीज नाही.
    """

    def _sample_df(self):
        return pd.DataFrame([
            {"Time": "10:15", "Total Call OI": 5300, "Total Put OI": 6300, "Diff": 1000, "Signal": "BULLISH"},
            {"Time": "10:10", "Total Call OI": 5200, "Total Put OI": 6200, "Diff": 1000, "Signal": "BULLISH"},
            {"Time": "10:05", "Total Call OI": 5100, "Total Put OI": 6100, "Diff": 1000, "Signal": "BULLISH"},
            {"Time": "10:00", "Total Call OI": 5000, "Total Put OI": 6000, "Diff": 1000, "Signal": "BULLISH"},
        ])

    def test_5_minute_returns_unchanged(self):
        hist_df = self._sample_df()
        result = aggregate_oi_history(hist_df, 5)
        assert len(result) == 4

    def test_10_minute_aggregates_into_buckets_with_last_value(self):
        hist_df = self._sample_df()
        result = aggregate_oi_history(hist_df, 10)
        assert len(result) == 2
        latest_bucket = result[result["Time"] == "10:10"].iloc[0]
        assert latest_bucket["Total Call OI"] == 5300  # bucket [10:10,10:15] मधली शेवटची (10:15 ची) value

    def test_15_minute_aggregates_correctly(self):
        hist_df = self._sample_df()
        result = aggregate_oi_history(hist_df, 15)
        assert len(result) == 2

    def test_empty_dataframe_handled_safely(self):
        result = aggregate_oi_history(pd.DataFrame(), 10)
        assert result.empty

    def test_columns_preserved_after_aggregation(self):
        hist_df = self._sample_df()
        result = aggregate_oi_history(hist_df, 10)
        assert set(result.columns) == set(hist_df.columns)


@pytest.fixture
def oi_temp_db(monkeypatch):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PCR Gate) — get_latest_pcr()/check_pcr_gate()
    साठी वेगळा, तात्पुरता SQLite DB (oi_diff_snapshots table सह)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE oi_diff_snapshots (
            symbol TEXT, trade_date TEXT, snapshot_time TEXT,
            total_call_oi INTEGER, total_put_oi INTEGER, diff INTEGER, delta_diff INTEGER, signal TEXT,
            PRIMARY KEY (symbol, trade_date, snapshot_time)
        )
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(oi_analysis, "DB_PATH", path)
    yield path


class TestGetLatestPCR:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PCR Gate — Bot Dynamic SR Algo) — आजचा सर्वात
    अलीकडचा (ATM-जवळचा) PCR मिळवणे, आणि जुना/गहाळ डेटा असल्यास None.

    🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug (test-only, production मध्ये अप्रत्यक्ष) — हे टेस्ट्स आधी
    real get_ist_now()/get_ist_today() (म्हणजे test चालवतानाची खरी घड्याळ-वेळ) वापरून "N मिनिटं
    आधीचा" snapshot-time बनवायचे, पण फक्त HH:MM:SS भाग घेऊन trade_date मात्र कायम "आज" (मूळ, न
    सरकलेलं) ठेवायचे — मध्यरात्री (IST) च्या आसपास चाचणी चालवली, तर "N मिनिटं आधी" प्रत्यक्षात
    कालच्या दिवसात सरकतो, पण trade_date तरीही आजचाच राहतो — त्यामुळे रो अंतर्गत विसंगत (चुकीचा) बनतो
    आणि "सर्वात अलीकडचा कोणता"/"किती जुना" या दोन्ही तपासण्या चुकीच्या निकालाकडे नेतात (production
    कोड स्वतः बरोबर आहे — oi_snapshot_collector.py कधीच मध्यरात्रीच्या आसपास चालत नाही, त्यामुळे
    असा विसंगत रो प्रत्यक्षात कधीच तयार होत नाही — पण चाचणी घड्याळाच्या वेळेवर अवलंबून राहणं
    (मध्यरात्रीच्या ~१ तासाच्या खिडकीत अनिश्चित) स्वतःच चुकीचं आहे). आता स्थिर, गोठवलेली दुपारची
    वेळ (मध्यरात्रीपासून दूर) — चाचणी केव्हाही चालवली तरी तोच निकाल."""

    _FROZEN_NOW = pd.Timestamp("2026-01-15 11:00:00")  # गुरुवार, दुपार — मध्यरात्री-सीमेपासून दूर

    @pytest.fixture(autouse=True)
    def _freeze_time(self, monkeypatch):
        monkeypatch.setattr(oi_analysis, "get_ist_now", lambda: self._FROZEN_NOW.to_pydatetime())
        monkeypatch.setattr(oi_analysis, "get_ist_today", lambda: self._FROZEN_NOW.date())

    def _insert_snapshot(self, path, symbol, trade_date, snapshot_time, call_oi, put_oi):
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO oi_diff_snapshots (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal) VALUES (?,?,?,?,?,?,?,?)",
            (symbol, trade_date, snapshot_time, call_oi, put_oi, put_oi - call_oi, 0, "NEUTRAL"),
        )
        conn.commit()
        conn.close()

    def test_returns_correct_pcr_from_latest_snapshot(self, oi_temp_db):
        today = oi_analysis.get_ist_today()
        now = oi_analysis.get_ist_now()
        recent_time = (now - pd.Timedelta(minutes=2)).strftime("%H:%M:%S")
        self._insert_snapshot(oi_temp_db, "NIFTY", today.strftime("%Y-%m-%d"), recent_time, call_oi=100000, put_oi=75000)
        pcr = get_latest_pcr("NIFTY")
        assert pcr == 0.75

    def test_returns_none_when_no_snapshot_today(self, oi_temp_db):
        pcr = get_latest_pcr("NIFTY")
        assert pcr is None

    def test_returns_none_when_snapshot_too_old(self, oi_temp_db):
        today = oi_analysis.get_ist_today()
        now = oi_analysis.get_ist_now()
        old_time = (now - pd.Timedelta(minutes=45)).strftime("%H:%M:%S")
        self._insert_snapshot(oi_temp_db, "NIFTY", today.strftime("%Y-%m-%d"), old_time, call_oi=100000, put_oi=75000)
        pcr = get_latest_pcr("NIFTY", max_age_minutes=15)
        assert pcr is None

    def test_picks_most_recent_when_multiple_snapshots(self, oi_temp_db):
        today = oi_analysis.get_ist_today()
        now = oi_analysis.get_ist_now()
        self._insert_snapshot(oi_temp_db, "NIFTY", today.strftime("%Y-%m-%d"), (now - pd.Timedelta(minutes=10)).strftime("%H:%M:%S"), call_oi=100000, put_oi=50000)
        self._insert_snapshot(oi_temp_db, "NIFTY", today.strftime("%Y-%m-%d"), (now - pd.Timedelta(minutes=2)).strftime("%H:%M:%S"), call_oi=100000, put_oi=120000)
        pcr = get_latest_pcr("NIFTY")
        assert pcr == 1.2  # जुना (50000) नाही, नवीनच (120000) वापरला जायला हवा


class TestCheckPCRGate:
    """वापरकर्त्याशी चर्चा करून ठरवलेला नियम — PCR < pcr_bullish_min -> Bullish नाही.
    PCR > pcr_bearish_max -> Bearish नाही. डेटा नसेल तर सुरक्षिततेसाठी trade थांबवणे."""

    def test_bullish_blocked_when_pcr_below_threshold(self, monkeypatch):
        monkeypatch.setattr(oi_analysis, "get_latest_pcr", lambda symbol, **k: 0.75)
        allowed, pcr, reason = check_pcr_gate("NIFTY", "BULLISH", pcr_bullish_min=0.80, pcr_bearish_max=1.10)
        assert allowed is False
        assert pcr == 0.75

    def test_bullish_allowed_when_pcr_above_threshold(self, monkeypatch):
        monkeypatch.setattr(oi_analysis, "get_latest_pcr", lambda symbol, **k: 0.95)
        allowed, pcr, reason = check_pcr_gate("NIFTY", "BULLISH", pcr_bullish_min=0.80, pcr_bearish_max=1.10)
        assert allowed is True

    def test_bearish_blocked_when_pcr_above_threshold(self, monkeypatch):
        monkeypatch.setattr(oi_analysis, "get_latest_pcr", lambda symbol, **k: 1.20)
        allowed, pcr, reason = check_pcr_gate("NIFTY", "BEARISH", pcr_bullish_min=0.80, pcr_bearish_max=1.10)
        assert allowed is False
        assert pcr == 1.20

    def test_bearish_allowed_when_pcr_below_threshold(self, monkeypatch):
        monkeypatch.setattr(oi_analysis, "get_latest_pcr", lambda symbol, **k: 0.95)
        allowed, pcr, reason = check_pcr_gate("NIFTY", "BEARISH", pcr_bullish_min=0.80, pcr_bearish_max=1.10)
        assert allowed is True

    def test_blocked_when_pcr_data_unavailable(self, monkeypatch):
        """वापरकर्त्याने ठरवलेला निर्णय (पर्याय अ) — डेटा नसेल/जुना असेल तर trade थांबवणे."""
        monkeypatch.setattr(oi_analysis, "get_latest_pcr", lambda symbol, **k: None)
        allowed, pcr, reason = check_pcr_gate("NIFTY", "BULLISH", pcr_bullish_min=0.80, pcr_bearish_max=1.10)
        assert allowed is False
        assert pcr is None
