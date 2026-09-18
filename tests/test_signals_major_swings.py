"""
tests/test_signals_major_swings.py
------------------------------------------------
signals.filter_major_swings() — वापरकर्त्याने प्रत्यक्ष चार्ट screenshot वरून "major swings only"
(किरकोळ noise-स्विंग्स गाळून फक्त खरोखर लक्षणीय turning points) दाखवलं, आणि तीच कल्पना strategy मध्ये
(classic_sr_reversal_trader.py च्या Swing High/Low Confluence गेटमध्ये) आणायला सांगितलं — ही त्याची
मूळ, reusable, pure गणिती चाचणी (ZigZag-सारखा magnitude फिल्टर, find_swings() च्या raw आउटपुटवर).
"""
import pandas as pd

from signals import find_swings, filter_major_swings


def _df(values, wick=0.1):
    return pd.DataFrame({
        "open": values, "close": values,
        "high": [v + wick for v in values], "low": [v - wick for v in values],
    })


class TestFilterMajorSwings:
    def test_empty_input_returns_empty(self):
        df = _df([100, 101, 102])
        highs, lows = filter_major_swings(df, [], [], min_move_pct=1.0)
        assert highs == [] and lows == []

    def test_filters_out_minor_swing_near_a_major_low(self):
        # idx5 = major low (~89.9), idx9 = तिथून फक्त ~0.1% वरचा दुसरा (noise) low -> गाळला जायला हवा
        vals = [100, 98, 96, 94, 92, 90, 90.6, 90.2, 90.5, 90.1, 90.4, 92, 96, 100, 104, 108, 110]
        df = _df(vals)
        sh, sl = find_swings(df, order=2)
        assert 5 in sl and 9 in sl  # दोन्ही raw fractal स्विंग्स म्हणून सापडायलाच हवेत (baseline तपासणी)

        major_sh, major_sl = filter_major_swings(df, sh, sl, min_move_pct=1.0)
        assert 5 in major_sl
        assert 9 not in major_sl  # किरकोळ (< 1% हालचाल) स्विंग गाळला गेला

    def test_keeps_both_swings_when_move_exceeds_threshold(self):
        vals = [100, 98, 96, 94, 92, 90, 91.5, 93, 94.5, 96, 92, 88, 84, 80, 84, 88, 92, 96, 100]
        df = _df(vals)
        sh, sl = find_swings(df, order=2)
        major_sh, major_sl = filter_major_swings(df, sh, sl, min_move_pct=1.0)
        # दोन्ही खोल lows (idx5 ~90, idx13 ~80) मोठी हालचाल असल्याने कायम राहायला हवेत
        assert 5 in major_sl
        assert 13 in major_sl

    def test_consecutive_same_type_swings_keep_only_the_more_extreme(self):
        # दोन शेजारी swing lows (एकाच "downswing" मधले) -> फक्त जास्त खोल (अधिक extreme) तोच राहायला हवा
        vals = [100, 98, 96, 94, 92, 90, 91, 89.5, 91, 88, 92, 96, 100, 104, 108]
        df = _df(vals)
        sh, sl = find_swings(df, order=2)
        major_sh, major_sl = filter_major_swings(df, sh, sl, min_move_pct=0.5)
        # idx9 (88.0) हा idx5 (90.0) पेक्षा जास्त खोल -> राहायला हवा, idx5 गाळला जायला हवा
        assert 9 in major_sl
        assert 5 not in major_sl

    def test_zero_threshold_keeps_every_alternating_swing(self):
        vals = [100, 98, 96, 94, 92, 90, 92, 94, 96, 98, 100, 98, 96, 94, 92, 90]
        df = _df(vals)
        sh, sl = find_swings(df, order=2)
        major_sh, major_sl = filter_major_swings(df, sh, sl, min_move_pct=0.0)
        # threshold=0 सह, alternating (high/low/high/low...) सर्व स्विंग्स कायम राहायला हवेत
        assert len(major_sh) + len(major_sl) == len(sh) + len(sl)

    def test_result_is_subset_of_original_indices(self):
        vals = [100, 98, 96, 94, 92, 90, 90.6, 90.2, 90.5, 90.1, 90.4, 92, 96, 100, 104, 108, 110,
                108, 106, 104, 102]
        df = _df(vals)
        sh, sl = find_swings(df, order=2)
        major_sh, major_sl = filter_major_swings(df, sh, sl, min_move_pct=1.0)
        assert set(major_sh) <= set(sh)
        assert set(major_sl) <= set(sl)
