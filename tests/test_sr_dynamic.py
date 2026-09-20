"""
tests/test_sr_dynamic.py
--------------------------------
sr_dynamic.find_pivots()/compute_dynamic_sr() — वापरकर्त्याने दिलेल्या मूळ TradingView Pine Script
("Support Resistance - Dynamic v2" © LonesomeTheBlue) शी थेट ताडून सापडवलेली विसंगती (`ph ? ph : pl`
ternary — एकाच bar वर pivot high व pivot low दोन्ही आले तर फक्त high ठेवायला हवा) दुरुस्त झाली आहे
का, याची पडताळणी.
"""
import pandas as pd

from sr_dynamic import find_pivots, compute_dynamic_sr


def _df(highs, lows):
    return pd.DataFrame({"high": highs, "low": lows})


class TestFindPivots:
    def test_pivot_high_and_low_on_same_bar_keeps_only_high(self):
        # prd=2, केंद्र bar (index 2) एकाच वेळी pivot high (10) आणि pivot low (1) दोन्ही —
        # Pine चं `ph ? ph : pl` — फक्त high ठेवायला हवा, low गाळायला हवा.
        highs = [1.0, 2.0, 10.0, 2.0, 1.0]
        lows = [9.0, 8.0, 1.0, 8.0, 9.0]
        pivots = find_pivots(_df(highs, lows), prd=2)
        assert pivots == [10.0]

    def test_pivot_low_only_when_no_pivot_high(self):
        highs = [5.0, 6.0, 7.0, 6.0, 5.0]  # केंद्र bar high नाही (उजवीकडे तेवढाच 7 नाही, पण max आहेच खरंतर)
        lows = [9.0, 8.0, 1.0, 8.0, 9.0]
        pivots = find_pivots(_df(highs, lows), prd=2)
        # केंद्र bar इथे pivot high सुद्धा आहे (7 हा window मधला max) — त्यामुळे शुद्ध "फक्त low"
        # केस साठी high केंद्रस्थानी max नसेल असं बनवू.
        highs2 = [10.0, 6.0, 7.0, 6.0, 5.0]
        pivots2 = find_pivots(_df(highs2, lows), prd=2)
        assert pivots2 == [1.0]

    def test_no_pivot_when_neither_extreme(self):
        highs = [10.0, 6.0, 5.0, 6.0, 5.0]
        lows = [1.0, 8.0, 9.0, 8.0, 9.0]
        pivots = find_pivots(_df(highs, lows), prd=2)
        assert pivots == []


class TestComputeDynamicSr:
    def test_returns_empty_when_too_little_data(self):
        df = pd.DataFrame({"high": [1.0] * 5, "low": [1.0] * 5, "close": [1.0] * 5})
        result = compute_dynamic_sr(df, prd=10)
        assert result == {"support": [], "resistance": []}

    def test_splits_levels_by_current_price(self):
        # साधा, स्पष्ट दोलायमान (oscillating) pattern — किमान काही pivots तयार होण्याइतका मोठा.
        n = 200
        highs, lows = [], []
        for i in range(n):
            base = 100.0 + (i % 20) * 0.5
            highs.append(base + 5)
            lows.append(base - 5)
        df = pd.DataFrame({"high": highs, "low": lows, "close": [100.0] * n})
        result = compute_dynamic_sr(df, prd=5, maxnumpp=20, channel_w_pct=50, maxnumsr=5, min_strength=1, current_price=100.0)
        for entry in result["resistance"]:
            assert entry["level"] >= 100.0
        for entry in result["support"]:
            assert entry["level"] < 100.0
