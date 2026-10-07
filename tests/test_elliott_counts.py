"""tests/test_elliott_counts.py — Elliott E1b: patterns (नियम R1–R10, invalidation बाजू, पुढची motive दिशा, Neely time flags),
real break (spec §7/§14 Q1, §12 test 7), count engine (truncation invariance, tentative ban, cross-degree R5, hysteresis, log)."""
import os

import numpy as np
import pandas as pd
import pytest

from elliott import breaks as B
from elliott import counts as C
from elliott import patterns as P
from elliott import settings as S
from elliott import swings as W

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T0 = pd.Timestamp("2019-01-02 09:15")


def _cfg(**k):
    c, e = S.validate(k)
    assert not e
    return c


def piv(prices, kinds=None, bars=None, start_kind=None, degree=1):
    """कृत्रिम pivots: prices क्रमाने; kind आपोआप (वर/खाली) — bars डीफॉल्ट 10 च्या अंतराने."""
    out = []
    for i, px in enumerate(prices):
        b = bars[i] if bars else i * 10
        if kinds:
            k = kinds[i]
        else:
            nxt = prices[i + 1] if i + 1 < len(prices) else None
            prv = prices[i - 1] if i else None
            k = ("L" if nxt > px else "H") if nxt is not None else ("H" if px > prv else "L")
        out.append(W.Pivot(degree, k, float(px), b, T0 + pd.Timedelta(minutes=5 * b), b + 2, T0 + pd.Timedelta(minutes=5 * (b + 3)),
                           "confirmed"))
    return out


def tent(price, bar, degree=1):
    return W.Pivot(degree, "X", float(price), bar, T0 + pd.Timedelta(minutes=5 * bar), None, None, "tentative")


S0 = _cfg()


# ---------------------------------------------------------------- patterns: नियम
def test_impulse_R1_R3_and_invalidation_sides():
    pts = piv([100, 120, 108])                                    # 1 वर, 2 खाली (origin च्या वर) ⇒ चालू 3
    n = P.build(1, "impulse", pts, tent(130, 30), S0)
    assert n.current_wave == "3" and n.invs[0] == (108.0, "below", "R1-lower") and n.next_motive_dir == 0
    assert P.build(1, "impulse", piv([100, 120, 98]), tent(130, 30), S0) is None            # R1: wave 2 origin च्या खाली
    n2 = P.build(1, "impulse", piv([100, 120]), tent(105, 20), S0)
    assert n2.current_wave == "2" and n2.invs[0] == (100.0, "below", "R1") and n2.next_motive_dir == 1   # 2 नंतर 3 वर
    four = piv([100, 120, 108, 150, 125])                          # wave 4 = 125 > wave1 end 120 ⇒ ठीक, चालू 5
    n5 = P.build(1, "impulse", four, tent(160, 50), S0)
    assert n5.current_wave == "5" and n5.invs[0][0] == 125.0 and n5.next_motive_dir == 0
    assert P.build(1, "impulse", piv([100, 120, 108, 150, 118]), tent(160, 50), S0) is None   # R3: wave 4 wave 1 मध्ये
    n4 = P.build(1, "impulse", piv([100, 120, 108, 150]), tent(130, 40), S0)
    assert n4.invs[0] == (120.0, "below", "R3") and n4.next_motive_dir == 1
    down = P.build(1, "impulse", piv([200, 180, 192]), tent(170, 30), S0)                    # खाली impulse: बाजू उलट
    assert down.direction == -1 and down.invs[0] == (192.0, "above", "R1-lower")


def test_impulse_wave3_inside_wave1_end_rejected_when_strict():
    assert P.build(1, "impulse", piv([100, 120, 105, 118]), tent(110, 40), S0) is None            # कुठलाही wave 4 R3 मोडेल
    assert P.build(1, "impulse", piv([100, 120, 105, 118]), tent(110, 40), _cfg(wave4_overlap_strict=False)) is not None


def test_diagonal_rules_R2_cap_and_no_pullback_entry_in_end_diag():
    n = P.build(1, "end_diag", piv([100, 140, 120, 145, 128]), tent(150, 50), S0)              # w1 40, w3 25 ⇒ w5 ≤ 25
    assert any(r == "R2" and lvl == 153.0 and side == "above" for lvl, side, r in n.invs)
    for pts, t_ in (([100, 130], (112, 20)), ([100, 130, 112, 140], (125, 40))):                  # end_diag wave 2 / 4 चालू
        e = P.build(1, "end_diag", piv(pts), tent(*t_), S0)
        assert e.current_wave in ("2", "4") and e.next_motive_dir == 0                            # spec §5 निषिद्ध #5
        i = P.build(1, "impulse", piv(pts), tent(*t_), S0)
        assert i.next_motive_dir == 1


def test_non_strict_R3_running_and_completed_agree():
    s = _cfg(wave4_overlap_strict=False)
    mr = np.full(200, 8.0)                                                                       # allowance = 0.25 × 8 = 2
    run = P.build(1, "impulse", piv([100, 120, 108, 150]), tent(125, 40), s, mr_arr=mr)
    assert run.invs[0] == (118.0, "below", "R3")                                                   # P1 − allowance
    assert P.build(1, "impulse", piv([100, 120, 108, 150, 118.5]), tent(160, 50), s, mr_arr=mr) is not None
    assert P.build(1, "impulse", piv([100, 120, 108, 150, 117.5]), tent(160, 50), s, mr_arr=mr) is None


def test_impulse_R2_caps_wave5_when_w3_shorter():
    n = P.build(1, "impulse", piv([100, 140, 125, 155, 141]), tent(150, 50), S0)            # w1 40, w3 30 ⇒ w5 ≤ 30
    assert ("R2" in [r for _, _, r in n.invs]) and any(lvl == 171.0 and side == "above" for lvl, side, _ in n.invs)
    n2 = P.build(1, "impulse", piv([100, 120, 108, 150, 125]), tent(160, 50), S0)           # w3 > w1 ⇒ R2 मर्यादा नाही
    assert "R2" not in [r for _, _, r in n2.invs]


def test_diagonals_allow_overlap_but_not_w4_beyond_w2():
    n = P.build(1, "end_diag", piv([100, 130, 112, 140, 118]), tent(145, 50), S0)          # w4 118 < w1 end 130 (overlap)
    assert n is not None and n.guideline_hits["g_diag_overlap"] == 1
    assert P.build(1, "end_diag", piv([100, 130, 112, 140, 110]), tent(145, 50), S0) is None  # w4 < w2 end (R9)
    assert P.build(1, "impulse", piv([100, 130, 112, 140, 118]), tent(145, 50), S0) is None   # तोच impulse म्हणून R3 मोडतो


def test_zigzag_flat_rules_and_next_motive():
    a_only = P.build(1, "zigzag", piv([100], kinds=["L"]), tent(120, 10), S0)
    assert a_only.current_wave == "A" and a_only.next_motive_dir == 0                        # R4: A-end ⇒ पुढे B (corrective)
    zb = P.build(1, "zigzag", piv([100, 120]), tent(110, 20), S0)
    assert zb.current_wave == "B" and zb.invs[0] == (100.0, "below", "R6") and zb.next_motive_dir == 1
    zc = P.build(1, "zigzag", piv([100, 120, 110]), tent(125, 30), S0)
    assert zc.current_wave == "C" and zc.invs[0] == (110.0, "below", "start-of-C") and zc.next_motive_dir == -1
    assert P.build(1, "zigzag", piv([100, 120, 98]), tent(125, 30), S0) is None              # R6: B > A origin
    assert P.build(1, "flat", piv([100, 120, 110]), tent(125, 30), S0) is None               # R7: B 50% < 90%
    fe = P.build(1, "flat", piv([100, 120, 96]), tent(125, 30), S0)
    assert fe.subtype == "flat_exp" and fe.next_motive_dir == -1                             # B 120% ⇒ expanded
    assert P.build(1, "flat", piv([100, 120, 55]), tent(125, 30), S0) is None                # B > 2×A
    fb = P.build(1, "flat", piv([100, 120]), tent(105, 20), S0)
    assert fb.invs[0][2] == "flat_b_max" and fb.invs[0][0] == 120 - 2.0 * 20


def test_triangle_B_bound_C_start_and_frozen_tolerance():
    assert P.build(1, "triangle", piv([100, 120, 55]), tent(90, 30), S0) is None                 # B > 2×A
    b = P.build(1, "triangle", piv([100, 120]), tent(105, 20), S0)
    assert b.invs[0] == (80.0, "below", "tri_b_max")                                               # चालू B ची मर्यादा तीच
    c = P.build(1, "triangle", piv([100, 120, 104]), tent(116, 30), S0)
    assert c.invs[0] == (104.0, "below", "start-of-C")                                             # C संपेपर्यंत contracting/expanding अज्ञात
    s = _cfg(barrier_d_tol_atr=1.0)
    atr = np.full(200, 2.0)
    pts = piv([100, 120, 104, 116])
    d1 = P.build(1, "triangle", pts, tent(108, 40), s, atr_now=0.5, atr_arr=atr)
    d2 = P.build(1, "triangle", pts, tent(108, 40), s, atr_now=9.0, atr_arr=atr)
    assert d1.invs == d2.invs and d1.invs[0][0] == 104 - 2.0                                       # ATR C च्या confirm bar वर गोठलेला
    e = P.build(1, "triangle", piv([100, 110, 96, 118, 90]), tent(110, 50), S0)
    assert e.subtype == "tri_exp" and e.current_wave == "E" and e.next_motive_dir == 0            # expanding ⇒ entry नाही


def test_triangle_contracting_barrier_expanding():
    c = P.build(1, "triangle", piv([100, 120, 104, 116, 108]), tent(112, 50), S0)          # C<A end, D>B end ⇒ चालू E
    assert c.subtype == "tri_contr" and c.current_wave == "E" and c.invs[0] == (116.0, "above", "R8") and c.next_motive_dir == -1
    assert P.build(1, "triangle", piv([100, 120, 104, 116, 102]), tent(110, 50), S0) is None   # D B च्या पलीकडे
    s = _cfg(barrier_d_tol_atr=1.0)
    bar = P.build(1, "triangle", piv([100, 120, 104, 116, 103.5]), tent(110, 50), s, atr_now=2.0, atr_arr=np.full(200, 2.0))
    assert bar is not None and bar.subtype == "tri_barrier"
    e = P.build(1, "triangle", piv([100, 110, 96, 118]), tent(90, 40), S0)                 # C > A end ⇒ expanding
    assert e.subtype == "tri_exp" and e.next_motive_dir == 0
    inside = P.build(1, "triangle", piv([100, 120, 104]), tent(116, 30), S0)
    assert inside.next_motive_dir == 0                                                       # triangle च्या आत entry नाही


def test_c_time_violation_flag_and_rule():
    pts = piv([100, 120, 110], bars=[0, 10, 15])                                             # t(a)=10, t(b)=5
    n = P.build(1, "zigzag", pts, tent(125, 20), S0, now_idx=40)                            # t(c)=25 > 15
    assert n.time_flags["c_time_violation"] and "g_c_time" not in n.guideline_hits          # delay ⇒ फक्त flag
    n2 = P.build(1, "zigzag", pts, tent(125, 20), _cfg(c_time_rule="score"), now_idx=22)
    assert not n2.time_flags["c_time_violation"] and n2.guideline_hits["g_c_time"] == 1


def test_neely_impulse_time_filter():
    pts = piv([100, 120, 110, 150, 130], bars=[0, 20, 25, 45, 48])                          # t2<t1 आणि t4<t3
    assert P.build(1, "impulse", pts, tent(160, 60), _cfg(impulse_time_rule="filter")) is None
    n = P.build(1, "impulse", pts, tent(160, 60), S0)
    assert n.time_flags["impulse_time_ok"] is False and n.guideline_hits["g_time_neely"] == 0


def test_running_wave_rules_never_read_tentative():
    """Tentative ban: चालू wave चा extreme (tentative) origin च्या पलीकडे wick ने गेला तरी build तो नियम म्हणून वापरत नाही — त्याचा
    निर्णय फक्त invalidation (real break / wick basis) ने engine मध्ये."""
    n = P.build(1, "impulse", piv([100, 120]), tent(99, 20), S0)
    assert n is not None and n.invs[0] == (100.0, "below", "R1")


def test_cross_degree_family_R5():
    assert "triangle" not in P.CHILD_FAMILY[("impulse", "2")] and "triangle" in P.CHILD_FAMILY[("impulse", "4")]
    assert P.CHILD_FAMILY[("zigzag", "A")] == ("impulse", "lead_diag")                     # A = 5 waves (zigzag)
    assert all(set(P.CHILD_FAMILY[("end_diag", w)]) <= set(P.CORRECTIVE_PATTERNS) for w in "12345")


# ---------------------------------------------------------------- real break (spec §12 test 7)
def _frame(rows):
    st = pd.date_range("2019-01-02 09:15", periods=len(rows), freq="5min")
    o, h, l, c = zip(*rows)
    return pd.DataFrame({"timestamp": st, "bar_end": st + pd.Timedelta(minutes=5), "open": o, "high": h, "low": l, "close": c})


def _base(n=25):
    return [(100, 101, 99, 100)] * n                                                         # MR = 2 ⇒ buf 0.5


def test_real_break_false_break_cases():
    s = _cfg()
    wick = _frame(_base() + [(100, 100.5, 94, 99.5), (99.5, 100, 99, 99.8)])
    assert B.first_real_break(wick, 20, 98, "below", s) is None                              # (a) wick पलीकडे, close आत
    reclaim = _frame(_base() + [(98.8, 99.2, 97.3, 97.4), (97.4, 99, 97.3, 98.5)])          # कमकुवत close (range 1.9 < 2.4)
    assert B.first_real_break(reclaim, 20, 98, "below", s) is None                           # (b) एक close पलीकडे, पुढे reclaim
    accept = _frame(_base() + [(98.8, 99.2, 97.3, 97.4), (97.4, 97.6, 96.8, 97.1)])
    assert B.first_real_break(accept, 20, 98, "below", s) == 26                              # (c) पुढचा close सुद्धा पलीकडे
    disp = _frame(_base() + [(100, 100.2, 96, 96.3)])                                        # range 4.2 ≥ 1.2×2, close तळाशी
    assert B.first_real_break(disp, 20, 98, "below", s) == 25                                # displacement ⇒ त्याच bar वर
    weak = _frame(_base() + [(98.6, 99.0, 97.3, 97.45)])                                    # कमकुवत, आणि पुढचा bar अजून नाही
    assert B.first_real_break(weak, 20, 98, "below", s) is None                              # ⇒ अजून ठरलं नाही (भविष्य नाही)
    strong_mid = _frame(_base() + [(99, 99.5, 96.4, 97.4), (97.4, 99, 97.3, 98.4)])        # ताकदीची पण close मध्यावर ⇒ disp नाही
    assert B.first_real_break(strong_mid, 20, 98, "below", s) is None
    one = _cfg(break_no_reclaim_bars=0)
    assert B.first_real_break(reclaim, 20, 98, "below", one) == 25                           # 0 ⇒ एका close वर (फक्त तुलना)
    up = _frame(_base() + [(101, 103, 100.8, 102.8), (102.8, 103, 102.5, 102.9)])
    assert B.first_real_break(up, 20, 102, "above", s) == 26
    up_disp = _frame(_base() + [(100, 104.2, 99.9, 104.0)])                                  # वरच्या बाजूला displacement
    assert B.first_real_break(up_disp, 20, 102, "above", s) == 25
    k2 = _cfg(break_no_reclaim_bars=2)                                                        # window मधली displacement — जे आधी
    win = _frame(_base() + [(98.8, 99.2, 97.3, 97.4), (97.4, 97.5, 94.9, 95.1), (95.1, 98.6, 95.0, 98.5)])
    assert B.first_real_break(win, 20, 98, "below", k2) == 26
    assert B.first_wick_break(wick, 20, 98, "below") == 25


def test_break_cache_is_causal():
    s = _cfg()
    fr = _frame(_base() + [(98.8, 99.2, 97.3, 97.4), (97.4, 97.6, 96.8, 97.1)])
    cache = B.BreakCache(fr, s)
    assert not cache.broken_by(20, 98, "below", 25) and cache.broken_by(20, 98, "below", 26)
    part = B.BreakCache(fr.iloc[:26].reset_index(drop=True), s)
    assert not part.broken_by(20, 98, "below", 25)


# ---------------------------------------------------------------- engine
@pytest.fixture(scope="module")
def nifty1m():
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    return d[(d["timestamp"] >= "2019-01-01") & (d["timestamp"] < "2019-03-01")].reset_index(drop=True)[
        ["timestamp", "open", "high", "low", "close"]]


def _sig(snap):
    return {d: [(n.key, round(n.joint_score, 9), n.parent_key, n.tentative.price, n.tentative.ts, tuple(n.invs))
                for n in v.nodes] for d, v in snap.degrees.items()}


@pytest.mark.parametrize("basis", ["real_break", "wick"])
def test_engine_truncation_invariance(nifty1m, basis):
    s = _cfg(count_inv_basis=basis)
    full = C.CountEngine(W.multi_degree(nifty1m, s), s)
    ts = nifty1m["timestamp"]
    cuts = [pd.Timestamp(x) for x in np.random.default_rng(5).choice(ts[(ts >= "2019-01-20") & (ts.dt.minute % 5 != 0)].to_numpy(),
                                                                        5, replace=False)]
    for t in sorted(cuts) + [pd.Timestamp("2019-02-14 15:30")]:
        part = C.CountEngine(W.multi_degree(nifty1m[nifty1m["timestamp"] < t], s), s)
        a, b = full.snapshot(t), part.snapshot(t)
        full.prev = part.prev = None
        assert _sig(a) == _sig(b)
        for d in a.degrees:
            va, vb = a.degrees[d], b.degrees[d]
            assert (va.gray, va.parent_missing, getattr(va.preferred, "key", None)) == (vb.gray, vb.parent_missing,
                                                                                        getattr(vb.preferred, "key", None))
            assert np.allclose([va.vote_up, va.vote_down], [vb.vote_up, vb.vote_down], equal_nan=True)
        for d, v in a.degrees.items():
            for n in v.nodes:
                assert all(p.confirmed_at <= t for p in n.points[1:])                       # completed waves फक्त confirmed


def test_engine_votes_cross_degree_and_hysteresis(nifty1m):
    s = _cfg()
    eng = C.CountEngine(W.multi_degree(nifty1m, s), s)
    fr = eng.md[0]["frame"]
    seen_vote, seen_child = False, False
    for t in fr["bar_end"].iloc[1500:2400:5]:
        sn = eng.snapshot(t)
        for d, v in sn.degrees.items():
            assert len(v.nodes) <= s["beam_k"]
            js = [n.joint_score for n in v.nodes]
            assert js == sorted(js, reverse=True)
            if v.nodes and np.isfinite(v.vote_up):
                assert 0 <= v.vote_up + v.vote_down <= 1 + 1e-9
                seen_vote = True
            top = max(sn.degrees)
            if d < top and not v.parent_missing:
                if not sn.degrees[d + 1].nodes:
                    assert not v.nodes                                                       # parent कडे डेटा पण count नाही ⇒ child नाही
                parents = {p.key: p for p in sn.degrees[d + 1].nodes}
                for n in v.nodes:                                                            # strict: प्रत्येक child चा parent
                    p = parents[n.parent_key]
                    assert n.pattern in P.CHILD_FAMILY[(p.pattern, p.current_wave)] and n.direction == p.current_dir
                    if n.pattern == "end_diag" or n.subtype == "tri_exp":
                        assert n.next_motive_dir == 0                                        # S11 / P8: parent कडून दिशा नाही
                    elif n.current_wave == P.LAST_WAVE[n.pattern]:
                        assert n.next_motive_dir == p.next_motive_dir                        # शेवटची wave ⇒ parent ची दिशा
                    seen_child = True
    assert seen_vote and seen_child and eng.log
    for e in eng.log[:20]:
        assert {"t", "break_at", "degree", "pattern", "current_wave", "level", "rule"} <= set(e) and e["break_at"] <= e["t"]
        assert isinstance(e["level"], float) and e["rule"] in {"origin", "R1", "R1-lower", "R2", "R3", "R6", "R8", "R9", "flat_b_max",
                                                               "tri_b_max", "X_W_origin", "start", "start-of-5", "start-of-C",
                                                               "start-of-Y"}


def test_hysteresis_keeps_previous_preferred(nifty1m):
    s = _cfg(hysteresis_margin=1.0)                                                         # कधीच बदलू नये (जुना टिकला तर)
    eng = C.CountEngine(W.multi_degree(nifty1m, s), s)
    fr = eng.md[0]["frame"]
    kept = 0
    prev = None
    for t in fr["bar_end"].iloc[1500:1900:2]:
        sn = eng.snapshot(t)
        v = sn.degrees[3]
        if prev is not None and prev.preferred is not None and v.preferred is not None:
            if prev.preferred.key in {n.key for n in v.nodes}:
                assert v.preferred.key == prev.preferred.key
                kept += 1
        prev = v
    assert kept > 10
    eng0 = C.CountEngine(W.multi_degree(nifty1m, _cfg(hysteresis_margin=0.0)), _cfg(hysteresis_margin=0.0))
    for t in fr["bar_end"].iloc[1500:1700:2]:                                              # margin 0 ⇒ नेहमी सर्वोत्तम
        v = eng0.snapshot(t).degrees[3]
        if v.nodes:
            assert v.preferred.joint_score == v.nodes[0].joint_score
