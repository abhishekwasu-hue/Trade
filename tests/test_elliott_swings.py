"""tests/test_elliott_swings.py — Elliott E1a: causal multi-degree swings. Spec §12 no-repaint suite: truncation invariance,
signal (pivot) immutability, tentative-pivot ban, बंद bars फक्त; auto-TF (§14 Q3) फक्त बंद candles वरून; Similarity & Balance;
settings validation. Offline NIFTY 1m (IS) — network नाही."""
import os

import numpy as np
import pandas as pd
import pytest

from elliott import settings as S
from elliott import swings as W

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def nifty1m():
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    d = d[(d["timestamp"] >= "2019-01-01") & (d["timestamp"] < "2019-02-15")].reset_index(drop=True)
    return d[["timestamp", "open", "high", "low", "close"]]


def _cfg(**k):
    c, errs = S.validate(k)
    assert not errs
    return c


def _key(p):
    return (p.kind, p.price, p.ts, p.confirmed_at, p.bar_idx, p.confirmed_idx)


FIXED_CUTS = list(pd.to_datetime(["2019-01-10 11:00", "2019-01-22 15:30", "2019-02-01 09:16", "2019-02-08 15:29"]))


def _cuts(d):
    """निश्चित cuts + डेटामधले 6 random, सत्रातले, 5m grid बाहेरचे मिनिटं (seeded)."""
    ts = d["timestamp"]
    pool = ts[(ts.dt.minute % 5 != 0) & (ts >= "2019-01-08")].to_numpy()
    off = np.random.default_rng(11).choice(pool, 6, replace=False)
    assert all(pd.Timestamp(x).minute % 5 for x in off)
    return sorted(FIXED_CUTS + [pd.Timestamp(x) for x in off])


@pytest.mark.parametrize("mode,fixed", [("atr", False), ("pct", False), ("fractal", False), ("atr", True)])
def test_truncation_invariance_and_immutability(nifty1m, mode, fixed):
    """कुठल्याही वेळी (5m grid बाहेरसुद्धा) कापलेल्या डेटावरचे pivots = पूर्ण run मधले knowable_at ≤ t pivots (हुबेहूब);
    `now=` path तेच देतो; tentative सुद्धा तोच; जुने pivots पुढे कधीच बदलत नाहीत. fixed mode = 15m/1h/1d bars (बंद झाल्यावरच)."""
    s = _cfg(swing_mode=mode, **({"degree_tf_mode": "fixed", "degree_tf": "5m,15m,1h,1d"} if fixed else {}))
    full = W.multi_degree(nifty1m, s)
    prev = None
    for t in _cuts(nifty1m):
        part = W.multi_degree(nifty1m[nifty1m["timestamp"] < t], s)
        via_now = W.multi_degree(nifty1m, s, now=t)
        for d in full:
            exp = W.known_at(full[d]["confirmed"], t)
            assert [_key(p) for p in part[d]["confirmed"]] == [_key(p) for p in exp]
            assert [_key(p) for p in via_now[d]["confirmed"]] == [_key(p) for p in exp]
            tp, tn = part[d]["tentative"], via_now[d]["tentative"]
            assert (tp is None and tn is None) or (tp.kind, tp.price, tp.ts) == (tn.kind, tn.price, tn.ts)
            assert (part[d]["frame"]["bar_end"] <= t).all()
        if prev is not None:
            for d in full:                                                     # जुने pivots नव्या cut मध्ये prefix म्हणून जसेच्या तसे
                assert part[d]["confirmed"][:len(prev[d]["confirmed"])] == prev[d]["confirmed"]
        prev = part


def test_fractal_legs_point_the_right_way(nifty1m):
    s = _cfg(swing_mode="fractal")
    for d, v in W.multi_degree(nifty1m, s).items():
        conf = v["confirmed"]
        assert len(conf) > 3
        for a, b in zip(conf, conf[1:]):
            assert a.kind != b.kind and b.bar_idx > a.bar_idx
            assert (b.price > a.price) if b.kind == "H" else (b.price < a.price)


def test_pivot_semantics_and_tentative(nifty1m):
    s = _cfg()
    md = W.multi_degree(nifty1m, s)
    for d, v in md.items():
        fr, conf = v["frame"], v["confirmed"]
        assert len(conf) > 3
        assert all(a.kind != b.kind for a, b in zip(conf, conf[1:]))           # आलटून-पालटून
        for p in conf:
            assert p.status == "confirmed" and p.confirmed_idx > p.bar_idx
            assert p.confirmed_at == fr["bar_end"].iloc[p.confirmed_idx] > p.ts  # knowable_at = confirm bar चा शेवट
            col = "high" if p.kind == "H" else "low"
            assert p.price == fr[col].iloc[p.bar_idx]
        t = v["tentative"]
        assert t is not None and t.status == "tentative" and t.confirmed_at is None and t.kind != conf[-1].kind
        assert t.bar_idx > conf[-1].bar_idx and t not in conf
    counts = [len(md[d]["confirmed"]) for d in sorted(md)]
    assert counts == sorted(counts, reverse=True) and counts[0] > counts[-1]   # degree वाढली ⇒ swings कमी


def test_tentative_uses_only_bars_and_pivots_known_upto(nifty1m):
    s = _cfg()
    fr = W.build_frame(nifty1m, "5m")
    conf = W.degree_pivots(fr, 1, s)
    last = conf[-1]
    upto = last.confirmed_idx + 3
    t = W.tentative_pivot(fr, conf, 1, upto=upto)
    seg = fr.iloc[last.bar_idx + 1: upto + 1]
    assert t.price == (seg["low"].min() if t.kind == "L" else seg["high"].max()) and t.bar_idx <= upto
    early = W.tentative_pivot(fr, conf, 1, upto=last.confirmed_idx - 1)       # शेवटचा pivot अजून माहीत नाही ⇒ आधीच्या वरून
    assert early.kind == last.kind and early.bar_idx <= last.confirmed_idx - 1


def test_tentative_tie_picks_last_bar_like_zigzag():
    st = pd.date_range("2019-01-02 09:15", periods=8, freq="5min")
    hi = [10, 12, 11, 10, 9, 9.5, 9, 10]
    fr = pd.DataFrame({"timestamp": st, "bar_end": st + pd.Timedelta(minutes=5), "open": hi, "high": hi,
                       "low": [x - 0.5 for x in hi], "close": hi})
    h = W.Pivot(0, "H", 12.0, 1, st[1], 3, st[3], "confirmed")
    t = W.tentative_pivot(fr, [h], 0)
    assert t.kind == "L" and t.price == 8.5 and t.bar_idx == 6                  # 9 च्या low दोनदा (bar 4, 6) ⇒ शेवटचा


def test_build_frame_drops_unclosed_bar(nifty1m):
    d = nifty1m[nifty1m["timestamp"] < "2019-01-02 09:27"]                    # 09:25 चा 5m bar अपूर्ण
    fr = W.build_frame(d, "5m")
    assert fr["bar_end"].max() == pd.Timestamp("2019-01-02 09:25") and (fr["bar_end"] <= pd.Timestamp("2019-01-02 09:27")).all()
    f15 = W.asof(W.build_frame(nifty1m, "15m"), "2019-01-02 10:00")
    assert list(f15[f15["timestamp"] >= "2019-01-02"]["bar_end"].astype(str)) == [
        "2019-01-02 09:30:00", "2019-01-02 09:45:00", "2019-01-02 10:00:00"]


def test_atr_is_causal():
    rng = np.random.default_rng(3)
    px = 100 + np.cumsum(rng.normal(0, 1, 200))
    df = pd.DataFrame({"high": px + 1, "low": px - 1, "close": px})
    a_full, a_cut = W.atr(df, 14), W.atr(df.iloc[:120], 14)
    assert np.isnan(a_full[:13]).all() and np.allclose(a_full[:120], a_cut, equal_nan=True)


def test_fixed_degree_tf_mode_uses_listed_tfs(nifty1m):
    s = _cfg(degree_tf_mode="fixed", degree_tf="5m,15m,1h,1d")
    md = W.multi_degree(nifty1m, s)
    assert [md[d]["tf"] for d in range(4)] == ["5m", "15m", "1h", "1d"]
    assert all(p.tf == "15m" for p in md[1]["confirmed"])


def test_similarity_balance():
    assert W.similar_degree((None, None, 100, 10), (None, None, 30, 25), 1 / 3)        # price 0.3 < 1/3 पण time 10/25 = 0.4 ≥ 1/3
    assert not W.similar_degree((None, None, 100, 10), (None, None, 30, 40), 1 / 3)    # price 0.3, time 0.25 — दोन्ही कमी
    assert not W.similar_degree((None, None, 100, 50), (None, None, 20, 5), 1 / 3)     # price 0.2, time 0.1
    assert W.similar_degree((None, None, 100, 50), (None, None, 20, 20), 1 / 3)        # time 0.4 ≥ 1/3


def _frame(tf, start, n):
    st = pd.date_range(start, periods=n, freq=f"{S.TF_MIN[tf]}min")
    return pd.DataFrame({"timestamp": st, "bar_end": st + pd.Timedelta(minutes=S.TF_MIN[tf])})


def test_auto_tf_smallest_in_range_and_closed_only():
    s = _cfg()
    frames = {tf: _frame(tf, "2019-01-02 09:15", 400 // S.TF_MIN[tf] * 5) for tf in ("5m", "15m", "30m", "1h")}
    a, b = pd.Timestamp("2019-01-02 09:15"), pd.Timestamp("2019-01-02 12:15")              # 3 तास
    s = _cfg(auto_tfs="5m,15m,30m,1h")
    tf, c, ok = W.auto_tf(frames, a, b, s)
    assert c["5m"] == 36 and tf == "5m" and ok                                              # 36 ∈ [8, 40]
    tf, c, ok = W.auto_tf(frames, a, pd.Timestamp("2019-01-02 15:15"), s)                   # 6 तास: 5m 72, 15m 24
    assert tf == "15m" and c["15m"] == 24 and ok
    tf, c, _ = W.auto_tf(frames, a, pd.Timestamp("2019-01-02 15:22"), s)                    # 15:30 चा 15m bar अजून बंद नाही
    assert c["15m"] == 24
    tf, _, ok = W.auto_tf(frames, a, pd.Timestamp("2019-01-02 09:35"), s)                   # 4 bars ⇒ कुठलाच ≥ 8 नाही
    assert tf == "5m" and not ok
    s2 = _cfg(tf_bars_min=8, tf_bars_max=10, auto_tfs="5m,15m,30m,1h")
    tf, c, ok = W.auto_tf(frames, a, pd.Timestamp("2019-01-02 15:15"), s2)                  # 72/24/12/6 ⇒ range मध्ये नाही
    assert tf == "30m" and not ok                                                           # ≥ 8 पैकी सर्वात मोठा
    with pytest.raises(ValueError):
        W.auto_tf(frames, a, b, _cfg())                                                     # 1d frame नाही ⇒ गुपचूप वगळत नाही


def test_settings_validation():
    c, e = S.validate({"swing_atr_mult": "1,2,4,8", "degree_levels": "4"})
    assert c["swing_atr_mult"] == [1.0, 2.0, 4.0, 8.0] and not e
    c, e = S.validate({"swing_atr_mult": "3,2,4,8"})
    assert c["swing_atr_mult"] == S.DEFAULTS["swing_atr_mult"] and e                        # degree वाढताना वाढायला हवं
    c, e = S.validate({"swing_atr_mult": "1,2"})
    assert c["swing_atr_mult"] == S.DEFAULTS["swing_atr_mult"] and e                        # 4 degrees साठी 2 मूल्यं
    c, e = S.validate({"tf_bars_min": 50, "tf_bars_max": 40})
    assert (c["tf_bars_min"], c["tf_bars_max"]) == (8, 40) and e
    c, e = S.validate({"degree_levels": 2})
    assert c["trade_degrees_enabled"] == [0, 1] and e
    c, e = S.validate({"degree_tf": "5m,7m,1h,1d", "swing_mode": "magic", "swing_atr_mult": "nan,1,2,3"})
    assert len(e) == 3 and c["swing_mode"] == "atr"
    assert S.snapshot(c)["hash"] == S.snapshot(dict(c))["hash"] and len(S.snapshot(c)["hash"]) == 12
    # review: उलट-क्रम reset नंतर लांबी पुन्हा तपासली जाते (आधी pct mode मध्ये IndexError)
    c, e = S.validate({"degree_levels": 5, "swing_mode": "pct", "swing_pct": "0.5,0.4,0.3,0.2,0.1"})
    assert c["degree_levels"] == len(c["swing_pct"]) == 4 and e
    c, e = S.validate({"degree_levels": 5, "swing_atr_mult": "1,2,3,4,5"})                  # atr mode मध्ये फक्त ATR यादी लागते
    assert c["degree_levels"] == 5 and not e
    c, e = S.validate({"swing_fractal_r": "1.4,2,3,4"})
    assert c["swing_fractal_r"] == S.DEFAULTS["swing_fractal_r"] and e                      # पूर्णांक हवा
    c, e = S.validate({"degree_tf_mode": "fixed", "degree_tf": "1h,15m,1h,1d"})
    assert c["degree_tf"] == S.DEFAULTS["degree_tf"] and e                                  # TF degree सोबत लहान होऊ नये
    c, e = S.validate({"trade_degrees_enabled": "0,0,1", "auto_tfs": "1m,5m"})
    assert c["trade_degrees_enabled"] == [0, 1] and c["auto_tfs"] == S.DEFAULTS["auto_tfs"] and e
