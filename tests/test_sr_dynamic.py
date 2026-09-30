"""
tests/test_sr_dynamic.py
--------------------------------
sr_dynamic.find_pivots()/compute_dynamic_sr() — वापरकर्त्याने दिलेल्या मूळ TradingView Pine Script
("Support Resistance - Dynamic v2" © LonesomeTheBlue) शी थेट ताडून सापडवलेली विसंगती (`ph ? ph : pl`
ternary — एकाच bar वर pivot high व pivot low दोन्ही आले तर फक्त high ठेवायला हवा) दुरुस्त झाली आहे
का, याची पडताळणी.
"""
import numpy as np
import pandas as pd

from sr_dynamic import find_pivots, find_pivots_indexed, compute_dynamic_sr


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


def _pine_bar_by_bar(df, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2):
    """मूळ Pine Script चं स्वतंत्र, bar-by-bar अनुकरण (test साठीच) — S/R state फक्त `if ph or pl`
    वर पुन्हा बनते, त्या bar वरचा cwidth (शेवटचे 300 bars) वापरून; मधल्या bars मध्ये तसंच राहतं."""
    H, L = df["high"].values, df["low"].values
    pivotvals, state = [], []
    for i in range(2 * prd, len(df)):
        c = i - prd
        ph = H[c] == H[c - prd:c + prd + 1].max()
        pl = (not ph) and L[c] == L[c - prd:c + prd + 1].min()
        if not (ph or pl):
            continue
        pivotvals.insert(0, H[c] if ph else L[c])
        pivotvals = pivotvals[:maxnumpp]
        cwidth = (H[max(0, i - 299):i + 1].max() - L[max(0, i - 299):i + 1].min()) * channel_w_pct / 100
        up, dn, st = [], [], []
        for ind in range(len(pivotvals)):
            lo = pivotvals[ind]; hi = lo; numpp = 0
            for cpp in pivotvals:
                wdth = (hi - cpp) if cpp <= lo else (cpp - lo)
                if wdth <= cwidth:
                    if cpp <= hi:
                        lo = min(lo, cpp)
                    else:
                        hi = max(hi, cpp)
                    numpp += 1
            ok = True
            for k in range(len(up)):
                if (lo <= up[k] <= hi) or (lo <= dn[k] <= hi):
                    if numpp >= st[k]:
                        st.pop(k); up.pop(k); dn.pop(k)
                    else:
                        ok = False
                    break
            if ok:
                loc = len(st)
                for k in range(len(st) - 1, -1, -1):
                    if numpp <= st[k]:
                        break
                    loc = k
                if loc < maxnumsr and numpp >= min_strength:
                    st.insert(loc, numpp); up.insert(loc, hi); dn.insert(loc, lo)
                    if len(st) > maxnumsr:
                        st.pop(); up.pop(); dn.pop()
        state = sorted(round((u + d) / 2, 2) for u, d in zip(up, dn))
    return state


class TestPineExactEventBasedCalculation:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("TradingView ची एक्झॅक्ट पद्धत") — S/R levels मूळ
    Pine प्रमाणे फक्त शेवटच्या pivot-event bar वर, त्या bar च्या cwidth सह मोजले जातात."""

    def _walk(self, seed, n=900):
        rng = np.random.default_rng(seed)
        close = 22000 + np.cumsum(rng.normal(0, 6, n))
        high = close + rng.uniform(1, 8, n)
        low = close - rng.uniform(1, 8, n)
        return pd.DataFrame({"high": np.round(high, 2), "low": np.round(low, 2), "close": np.round(close, 2)})

    def test_matches_bar_by_bar_pine_simulation_at_many_end_bars(self):
        checked = 0
        for seed in (1, 2, 3):
            df = self._walk(seed)
            for end in range(400, 900, 7):
                sub = df.iloc[:end + 1].reset_index(drop=True)
                res = compute_dynamic_sr(sub, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
                got = sorted(e["level"] for e in res["support"] + res["resistance"])
                assert got == _pine_bar_by_bar(sub), f"seed={seed} end={end}"
                checked += 1
        assert checked > 100

    def test_levels_do_not_change_between_pivot_events(self):
        # शेवटचा pivot confirm झाल्यानंतर आणखी bars आले, पण नवीन pivot नाही -> levels तसेच (Pine सारखे),
        # cwidth शेवटच्या bar वरचा वापरला जात नाही.
        df = self._walk(5, 700)
        pivots = find_pivots_indexed(df, 10)
        last_event = pivots[-1][0] + 10
        base = compute_dynamic_sr(df.iloc[:last_event + 1].reset_index(drop=True))
        # मागे-मागे कमीतकमी काही bars जोडणं: नवीन pivot न तयार होणारे bars (आधीच्याच पातळीवर सपाट)
        extra = pd.DataFrame({"high": [df["high"].iloc[last_event]] * 3, "low": [df["low"].iloc[last_event]] * 3,
                              "close": [df["close"].iloc[last_event]] * 3})
        extended = pd.concat([df.iloc[:last_event + 1], extra], ignore_index=True)
        assert len(find_pivots_indexed(extended, 10)) == len(find_pivots_indexed(df.iloc[:last_event + 1], 10))
        res = compute_dynamic_sr(extended)
        assert sorted(e["level"] for e in res["support"] + res["resistance"]) == \
            sorted(e["level"] for e in base["support"] + base["resistance"])

    def test_find_pivots_indexed_matches_find_pivots(self):
        df = self._walk(9, 300)
        assert [v for _, v in find_pivots_indexed(df, 10)] == find_pivots(df, 10)
        assert all(10 <= i < len(df) - 10 for i, _ in find_pivots_indexed(df, 10))

    def test_mintick_rounds_levels_to_nearest_tick(self):
        df = self._walk(11, 700)
        res = compute_dynamic_sr(df, mintick=0.05)
        levels = [e["level"] for e in res["support"] + res["resistance"]]
        assert levels
        for lvl in levels:
            assert abs(round(lvl / 0.05) * 0.05 - lvl) < 1e-6

    def test_without_mintick_keeps_two_decimals(self):
        df = self._walk(11, 700)
        res = compute_dynamic_sr(df)
        for e in res["support"] + res["resistance"]:
            assert e["level"] == round(e["level"], 2)
