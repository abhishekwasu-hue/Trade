"""थर 3 (correction patterns) — synthetic data फक्त, कुठलीही तारीख नाही (prompt §9)."""
import json
import os
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from patterns2 import charts as PCH
from patterns2 import enum as EN
from patterns2 import fold as PF
from patterns2 import rules as R
from patterns2 import score as SC
from patterns2 import settings as PS
from tests.test_legs2 import DATE_RX_I, IMP_ZZ, asof_end, fake

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = PS.load()


def P(prices, tent=True, step=3):
    pts = [{"price": float(p), "bar": i * step, "kind": "H" if (i % 2 == 0) == (prices[1] < prices[0]) else "L", "tent": False}
           for i, p in enumerate(prices)]
    if tent:
        pts[-1]["tent"] = True
    return pts


def fams(prices, tent=True, sigma=1.0):
    hs, _ = EN.enumerate_hyps(P(prices, tent), S, sigma)
    return {(h["family"], h["kind"], tuple(h["bounds"]), h["t"]) for h in hs}, hs


def full(n, t=0):
    return tuple(range(n + 1)), t


# ---------------------------------------------------------------------------------------------------------------- 1. templates
@pytest.mark.parametrize("fam,kind,prices,bad", [
    ("zigzag", "", [100, 90, 95, 85], [100, 90, 101, 85]),
    ("flat", "", [100, 90, 99, 89], [100, 90, 98, 89]),
    ("triangle", "contracting", [100, 90, 98, 92, 97, 93], [100, 90, 98, 92, 99, 93]),
    ("triangle", "expanding", [100, 96, 101, 94, 103, 92], [100, 96, 101, 94, 103, 95]),
    ("wedge", "contracting", [100, 90, 97, 88, 93, 87], [100, 90, 97, 88, 93, 89]),
    ("wedge", "expanding", [100, 95, 98, 91, 97, 85], [100, 95, 98, 91, 97, 92]),
    ("impulse_k", "", [100, 90, 95, 80, 87, 75], [100, 90, 95, 80, 91, 75]),
])
def test_each_template_recognised_and_hard_rule_breaks_invalid(fam, kind, prices, bad):
    after = prices + [prices[-1] + (prices[-2] - prices[-1]) * 0.3]
    got, _ = fams(after)
    assert (fam, kind, tuple(range(len(prices))), 1) in got
    badafter = bad + [bad[-1] + (bad[-2] - bad[-1]) * 0.3]
    got2, _ = fams(badafter)
    assert (fam, kind, tuple(range(len(bad))), 1) not in got2


def test_flat_subtypes_and_b_over_two_is_valid_with_penalty():
    assert R.flat([100, 90, 99, 89], True)[1] == "regular"
    assert R.flat([100, 90, 101, 88], True)[1] == "expanded"
    assert R.flat([100, 90, 101, 92], True)[1] == "running"
    assert R.flat([100, 90, 99], False) == (True, "प्रलंबित")
    assert R.flat([100, 90, 98, 89], True)[0] is False                              # B < 0.90 A ⇒ invalid
    assert R.flat([100, 90, 112, 85], True)[0] is True                              # B > 2.0 A ⇒ valid (m 0.2)
    _, hs = fams([100, 90, 112, 85, 95])
    h = next(h for h in hs if h["family"] == "flat" and h["bounds"] == [0, 1, 2, 3])
    ctx = SC.Ctx(h_P := P([100, 90, 112, 85, 95]), [], np.zeros(20), np.zeros(20), [], 20, 1.0, S)
    SC.score(h, ctx)
    assert any(nm.startswith("B/A") and m == pytest.approx(0.2) for nm, m in h["lines"])


def test_double_zigzag_and_combination_rules():
    dz = [100, 90, 95, 85, 92, 84, 88, 80]
    got, _ = fams(dz + [83])
    assert ("double_zigzag", "", tuple(range(8)), 1) in got
    got, _ = fams([100, 90, 95, 85, 101, 84, 88, 80, 83])                          # X W च्या सुरुवातीपलीकडे
    assert not any(f == "double_zigzag" and len(b) == 8 for f, _, b, _ in got)
    got, _ = fams([100, 90, 95, 91, 93, 84, 88, 80, 83])                           # W चा C, A गाठत नाही ⇒ W invalid
    assert not any(f == "double_zigzag" and len(b) == 8 for f, _, b, _ in got)
    comb = [100, 90, 99, 89, 95, 88, 92, 84]                                       # W flat, X, Y zigzag
    got, _ = fams(comb + [87])
    assert ("combination", "", tuple(range(8)), 1) in got
    vs = EN.variants(S)
    assert not any(f == "combination" and getattr(c, "__name__", "") == "x" for f, _, _, c in vs)
    names = [(f, L) for f, _, L, _ in vs]
    assert ("combination", 3 + 1 + 5) in names                                     # Y triangle चालतो


def test_combination_never_two_zigzags_and_no_w_triangle():
    for fam, kind, L, chk in EN.variants(S):
        if fam != "combination":
            continue
        x = [100, 90, 95, 85, 92, 84, 88, 80]                                      # W zz + Y zz
        if L == 7:
            ok, info = chk(x, True, S, 0.0)
            assert not (ok and info and info["W"] == "zz" and info["Y"] == "zz")
        ok, info = chk([100, 90, 98, 92, 97, 93], False, S, 0.0)
        assert not (ok and info and str(info.get("W", "")).startswith("tri"))


# ---------------------------------------------------------------------------------------------------------------- 2. wave नियम
def test_wave_ends_hidden_extreme_odd_and_single_after_leg():
    pts = P([100, 90, 102, 85])
    assert EN.wave_ends(pts)[0] == [1]                                             # आत लपलेलं टोक (102 > 100) ⇒ 0→3 wave नाही
    ends = EN.wave_ends(P([100, 90, 95, 85, 92, 80]))
    assert all((j - i) % 2 == 1 for i, js in enumerate(ends) for j in js)
    got, _ = fams([100, 90, 95, 85, 92])
    assert ("zigzag", "", (0, 1, 2, 3), 1) in got
    got, _ = fams([100, 90, 95, 85, 92, 88])                                       # pattern नंतर दोन legs ⇒ नाही
    assert ("zigzag", "", (0, 1, 2, 3), 1) not in got
    got, _ = fams([100, 90, 95, 85, 96])                                           # उलट leg शेवटच्या wave च्या सुरुवातीपलीकडे
    assert ("zigzag", "", (0, 1, 2, 3), 1) not in got


# ---------------------------------------------------------------------------------------------------------------- 3 + 17. अवस्था
I_UP = {"end": SimpleNamespace(price=100.0), "dir": 1}


def _hyp(prices, fam, bounds, t):
    _, hs = fams(prices)
    return next(h for h in hs if h["family"] == fam and h["bounds"] == list(bounds) and h["t"] == t), P(prices)


def test_zigzag_c_short_in_progress_and_flag():
    h, pts = _hyp([100, 90, 95, 91, 94], "zigzag", (0, 1, 2, 3), 1)
    assert PF.hyp_state(h, pts, I_UP, S) == ("final_leg_in_progress", ["C_short_possible"])
    h, pts = _hyp([100, 90, 95, 91], "zigzag", (0, 1, 2, 3), 0)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "final_leg_in_progress"


def test_states_present_resuming_forming_and_fourth_subleg():
    h, pts = _hyp([100, 90, 95, 85], "zigzag", (0, 1, 2, 3), 0)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "final_leg_present"
    h, pts = _hyp([100, 90, 95, 85, 93], "zigzag", (0, 1, 2, 3), 1)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "complete_resuming"
    h, pts = _hyp([100, 90, 95], "zigzag", (0, 1, 2), 0)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "forming_B"
    h, pts = _hyp([100, 90, 95, 85, 88, 84, 86], "zigzag", (0, 1, 2, 5), 1)       # C: 3 sub-legs, भाव चौथ्यात
    assert PF.hyp_state(h, pts, I_UP, S) == ("final_leg_in_progress", ["C चा चौथा sub-leg"])
    h, pts = _hyp([100, 90, 98, 92, 97, 93, 94.5], "triangle", (0, 1, 2, 3, 4, 5), 1)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "final_leg_in_progress"            # E: पहिला sub-leg, भाव दुसऱ्यात
    h, pts = _hyp([100, 95, 98, 91, 97, 85], "wedge", (0, 1, 2, 3, 4, 5), 0)
    assert PF.hyp_state(h, pts, I_UP, S) == ("forming_A", ["wedge (leading A) ⇒ थांबा"])
    h, pts = _hyp([100, 90, 95, 80, 87, 75], "impulse_k", (0, 1, 2, 3, 4, 5), 0)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "impulse_K"
    h, pts = _hyp([100, 90, 95, 85, 92, 84, 88, 81, 86], "double_zigzag", tuple(range(8)), 1)
    assert PF.hyp_state(h, pts, I_UP, S)[0] in ("final_leg_present", "complete_resuming")
    h, pts = _hyp([100, 90, 95, 85, 92, 84, 88, 86], "double_zigzag", tuple(range(8)), 0)
    assert PF.hyp_state(h, pts, I_UP, S)[0] == "final_leg_in_progress"            # Y चा C, Y च्या A पर्यंत नाही


# ---------------------------------------------------------------------------------------------------------------- 4–5
def test_flat_subtype_not_in_identity():
    _, hs = fams([100, 90, 101, 88])
    h = next(x for x in hs if x["family"] == "flat" and x["bounds"] == [0, 1, 2, 3])
    pid = EN.identity(h, P([100, 90, 101, 88]))
    assert pid == ("flat", "", 0, (3, 6))                                          # उप-प्रकार नाही; tentative टोक नाही


def _ctx(prices, inner=(), n=60):
    pts = P(prices)
    h = np.interp(np.arange(n), [p["bar"] for p in pts], [p["price"] for p in pts])
    return SC.Ctx(pts, list(inner), h.copy(), h.copy(), [], n, 1.0, S), pts


def test_triangle_five_leg_penalty_wave2_evidence_and_c_beyond_a_allowed():
    prices = [100, 90, 98, 92, 97, 93, 94.5]
    _, hs = fams(prices)
    h = next(x for x in hs if x["family"] == "triangle" and x["kind"] == "contracting" and x["t"] == 1)
    ctx, _ = _ctx(prices)
    ctx.structure = lambda i, j, in_progress=False: {"struct": "5" if i == 0 else "3", "m1": "5", "m2": "5", "sub_legs": 5}
    ctx.wave2_evidence = True
    SC.score(h, ctx)
    names = dict(h["lines"])
    assert names["A रचना"] == pytest.approx(0.2) and names["K हा wave 2 असण्याचा पुरावा"] == pytest.approx(0.2)
    assert R.triangle([100, 90, 98, 89, 96, 91], True, "contracting")[0]            # C, A पलीकडे तरी contracting चालतो


# ---------------------------------------------------------------------------------------------------------------- 8. impulse-K
def test_impulse_k_does_not_win_on_empty_guidelines():
    _, hs = fams([100, 90, 95, 80])
    ctx, _ = _ctx([100, 90, 95, 80])
    imp = next(h for h in hs if h["family"] == "impulse_k" and h["bounds"] == [0, 1, 2, 3])
    SC.score(imp, ctx)
    assert imp["lines"]                                                            # Tier B ओळी लागू
    empty = dict(imp, bounds=[0, 1], x=[100, 90])
    assert SC.score(empty, ctx) == pytest.approx(S["empty_m"] * S["simplicity"]["5"])
    assert SC.score(empty, ctx) < 1.0


# ---------------------------------------------------------------------------------------------------------------- 9. आतली रचना
COMBO = [("अज्ञात", "अज्ञात", "अज्ञात"), ("अज्ञात", "3", "3"), ("अज्ञात", "5", "5"), ("अज्ञात", "diagonal", "diagonal"),
         ("3", "अज्ञात", "3"), ("3", "3", "3"), ("3", "5", "3 किंवा 5"), ("3", "diagonal", "3 किंवा diagonal"),
         ("5", "अज्ञात", "5"), ("5", "3", "3 किंवा 5"), ("5", "5", "5"), ("5", "diagonal", "5 किंवा diagonal"),
         ("diagonal", "अज्ञात", "diagonal"), ("diagonal", "3", "3 किंवा diagonal"), ("diagonal", "5", "5 किंवा diagonal"),
         ("diagonal", "diagonal", "diagonal")]


@pytest.mark.parametrize("m1,m2,want", COMBO)
def test_two_measure_table_all_sixteen(m1, m2, want):
    assert SC.combine(m1, m2) == want


def test_measure2_finds_diagonal_with_only_three_d0_sublegs_and_in_progress_uses_confirmed():
    path = [(0, 100), (4, 110), (7, 104), (11, 113), (13, 109), (16, 116)]
    n = 20
    xs, ys = zip(*path)
    h = np.interp(np.arange(n), xs, ys)
    pts = [{"price": 100.0, "bar": 0, "kind": "L", "tent": False}, {"price": 116.0, "bar": 16, "kind": "H", "tent": False}]
    inner = [{"price": 113.0, "bar": 11, "kind": "H", "tent": False}, {"price": 109.0, "bar": 13, "kind": "L", "tent": False}]
    ctx = SC.Ctx(pts, inner, h.copy(), h.copy(), [], n, 1.0, S)
    st = ctx.structure(0, 1)
    assert st["m1"] == "3" and st["m2"] == "diagonal" and st["struct"] == "3 किंवा diagonal"
    st2 = ctx.structure(0, 1, in_progress=True)
    assert st2["m1"] == "अज्ञात"                                                  # चालू wave: फक्त confirmed sub-pivots


def test_contradicting_structure_keeps_hypothesis_valid():
    _, hs = fams([100, 90, 95, 85, 93])
    h = next(x for x in hs if x["family"] == "zigzag" and x["t"] == 1)
    ctx, _ = _ctx([100, 90, 95, 85, 93])
    ctx.structure = lambda i, j, in_progress=False: {"struct": "3", "m1": "3", "m2": "3", "sub_legs": 3}
    SC.score(h, ctx)
    assert dict(h["lines"])["A: रचना 3"] == pytest.approx(0.2) and h["score"] > 0


# ---------------------------------------------------------------------------------------------------------------- 10–11. गुण
def test_geometric_mean_fair_incomplete_and_evidence_once():
    ctx, _ = _ctx([100, 90, 95, 85, 93])
    _, hs = fams([100, 90, 95, 85, 93])
    done = next(x for x in hs if x["family"] == "zigzag" and x["t"] == 1)
    _, hs2 = fams([100, 90, 95, 85])
    prog = next(x for x in hs2 if x["family"] == "zigzag" and x["bounds"] == [0, 1, 2, 3])
    ctx2, _ = _ctx([100, 90, 95, 85])
    SC.score(done, ctx)
    SC.score(prog, ctx2)
    ms = [m for _, m in done["lines"]]
    assert done["score"] == pytest.approx(float(np.exp(np.mean(np.log(ms)))))
    assert done["score"] == pytest.approx(prog["score"])                          # पूर्णता-ओळी क्रमात नाहीत
    assert sum(1 for nm, _ in done["lines"] if nm.startswith("A")) == 1          # रचना / label एकच ओळ


def test_layer2_label_only_when_ends_match_and_known():
    ctx, pts = _ctx([100, 90, 95, 85])
    leg = {"a": SimpleNamespace(bar=0), "b": SimpleNamespace(bar=3, confirm_bar=10), "nature": "आवेगी", "label": "आवेग"}
    ctx.legs = [leg]
    ctx.structure = lambda i, j, in_progress=False: {"struct": "अज्ञात", "m1": "अज्ञात", "m2": "अज्ञात", "sub_legs": 1}
    ctx.t = 5
    m, why = SC._wave_m(ctx, 0, 1, "5", "आवेगी")
    assert m == pytest.approx(S["unknown_m"])                                      # known_at > decision bar ⇒ अज्ञात 0.7
    ctx.t = 12
    m, why = SC._wave_m(ctx, 0, 1, "5", "आवेगी")
    assert m == 1.0 and "label" in why


# ---------------------------------------------------------------------------------------------------------------- 12–14. क्रम / स्थिरता / identity
def _h(fam, score, ends, kind="", group=0):
    return {"family": fam, "kind": kind, "score": score, "id": (fam, kind, group, tuple(ends)), "bounds": [0, 1], "group": group}


def _fold():
    f = PF.Fold.__new__(PF.Fold)
    f.s, f.log = PS.load(), []
    return f


def test_order_not_alphabetical():
    order = {k: i for i, k in enumerate(PS.ORDER)}
    hs = [_h("combination", 0.8, (1,)), _h("flat", 0.8, (2,))]
    hs.sort(key=lambda h: (-h["score"], order[h["family"]]))
    assert hs[0]["family"] == "flat"
    assert list(PS.ORDER) != sorted(PS.ORDER)


def test_hysteresis_rules():
    f = _fold()
    st = {"pref": None, "chal": None, "n": 0}
    a, b, c = _h("zigzag", 0.5, (3,)), _h("flat", 0.58, (4,)), _h("triangle", 0.9, (5,))
    assert f._choose(st, [a, b], 0)[0] is a
    assert f._choose(st, [b, a], 1)[0] is a                                        # 1.2 पटीपेक्षा कमी ⇒ तोच
    assert f._choose(st, [c, a], 2)[0] is a                                        # 1 candle ⇒ तोच
    assert f._choose(st, [c, a], 3)[0] is c                                        # तोच challenger 2 candles ⇒ बदल
    st = {"pref": None, "chal": None, "n": 0}
    f._choose(st, [a], 0)
    d = _h("wedge", 0.9, (7,))
    assert f._choose(st, [c, a], 1)[0] is a and f._choose(st, [d, a], 2)[0] is a   # दोन वेगळे challengers ⇒ बदल नाही
    assert f._choose(st, [c], 3)[0] is c                                           # invalid ⇒ लगेच बदल


def test_identity_survives_tentative_confirm_prefix_and_coarse():
    f = _fold()
    st = {"pref": None, "chal": None, "n": 0}
    a = _h("zigzag", 0.5, (3,))
    f._choose(st, [a], 0)
    a2 = _h("zigzag", 0.5, (3, 6))                                                 # tentative ⇒ confirmed / पुढचा wave
    other = _h("flat", 0.55, (4,))
    assert f._choose(st, [other, a2], 1)[0] is a2
    a3 = _h("zigzag", 0.5, (3, 6, 9))                                              # coarse: तेच bars (nested pivots)
    assert f._choose(st, [a3], 2)[0] is a3 and not f.log


# ---------------------------------------------------------------------------------------------------------------- 15 + 18 + 20. fold
def _run_fold(points, tail, cut=None, labels=None, s=None):
    res, lg, m15 = fake(points, tail=tail, labels=labels)
    t = asof_end(m15) if cut is None else pd.Timestamp(m15["bar_end"].iloc[cut])
    f2 = PF.Fold(lg, 2, t, s)
    f2.run()
    f1 = PF.Fold(lg, 1, t, s, parent=f2)
    f1.run()
    return f1, f2, m15


def _sig(f, t):
    j = PF.rec_json(f.out[t], f.ts)
    return json.dumps(j, sort_keys=True, default=str)


def test_replay_equals_live_and_no_lookahead_truncation():
    f1, f2, m15 = _run_fold(IMP_ZZ, (72, 158))
    for cut in (55, 63, 70):
        g1, g2, _ = _run_fold(IMP_ZZ, (72, 158), cut=cut)
        for t in range(cut + 1):
            assert _sig(f1, t) == _sig(g1, t)
            assert _sig(f2, t) == _sig(g2, t)


def test_fold_finds_zigzag_k_after_impulse_and_d2_runs():
    f1, f2, m15 = _run_fold(IMP_ZZ, (72, 158))
    r = f1.out[f1.end]
    assert r["phase"] == "k" and r["pref"] is not None
    fam = {h["family"] for h in r["hyps"]}
    assert "zigzag" in fam
    assert f2.out[f2.end]["phase"] in ("k", "kstart", "impulse")


def test_coarse_only_by_pivot_count_and_sticky():
    pts = IMP_ZZ[:7]
    res, lg, m15 = fake(pts, tail=(60, 140), d0_extra=[(50, 150, "L"), (52, 155, "H"), (55, 146, "L"), (57, 152, "H")])
    t = asof_end(m15)
    f = PF.Fold(lg, 1, t, {"max_points": 3})
    f.run()
    flags = [g["coarse"] for r in f.out.values() for g in r.get("groups", [])[:1]]
    assert flags and any(flags)
    first = flags.index(True)
    assert all(flags[first:])


# ---------------------------------------------------------------------------------------------------------------- 16. expanded flat
def test_expanded_flat_from_old_i_end_and_b_label_line():
    pts = [(0, 170, "H"), (6, 100, "L"), (12, 120, "H"), (17, 110, "L"), (27, 150, "H"), (32, 140, "L"), (42, 160, "H"),
           (48, 150, "L"), (56, 166, "H")]
    res, lg, m15 = fake(pts, tail=(66, 155), labels={(1, 7): "आवेग"})
    lg["legs"][1][7]["nature"] = "आवेगी"
    t = asof_end(m15)
    f = PF.Fold(lg, 1, t)
    f.run()
    r = f.out[f.end]
    old = [h for h in r["hyps"] if h["gi"] == 1 and h["family"] == "flat"]
    assert old, [h["family"] for h in r["hyps"]]
    assert any(nm.startswith("B चा label आवेग") and m == pytest.approx(0.3) for nm, m in old[0]["lines"])
    assert r["groups"][0]["start"] == 166 and r["groups"][1]["start"] == 160


# ---------------------------------------------------------------------------------------------------------------- 21. prototype
def test_prototype_wedge_and_abc_readings_both_present():
    got, _ = fams([100, 90, 97, 88, 93, 87, 91])
    assert ("wedge", "contracting", (0, 1, 2, 3, 4, 5), 1) in got                  # (ब) संपूर्ण K = पाच legs
    assert ("zigzag", "", (0, 1, 2, 5), 1) in got                                  # (अ) a, b, c (c = wedge)


# ---------------------------------------------------------------------------------------------------------------- §10.2: elliott शी तुलना
def _ep(price, i):
    return SimpleNamespace(price=float(price), bar_idx=i * 3, confirmed_idx=i * 3 + 1, ts=pd.Timestamp(0) + pd.Timedelta(minutes=i))


@pytest.mark.parametrize("seed", range(40))
def test_rules_match_elliott_patterns_on_shared_rules(seed):
    from elliott import patterns as EP
    from elliott import settings as ES
    es = dict(ES.DEFAULTS, count_inv_basis="wick", wave4_overlap_strict=True, impulse_time_rule="score", barrier_d_tol_atr=0.0)
    rng = np.random.default_rng(seed)
    d = 1 if seed % 2 else -1
    for nc in (2, 3, 4):
        x = [100.0]
        for k in range(nc + 1):
            step = rng.uniform(2, 12) * (d if k % 2 == 0 else -d)
            x.append(x[-1] + step)
        pts = [_ep(v, i) for i, v in enumerate(x[:-1])]
        tent = _ep(x[-1], len(x) - 1)
        L = [abs(x[i + 1] - x[i]) for i in range(len(x) - 1)]
        xc = x[:-1]                                                            # पूर्ण waves (elliott: चालू wave चे नियम invalidation levels ने)
        if nc <= 2:
            assert (EP.build(1, "zigzag", pts, tent, es) is not None) == R.zigzag(xc, True)
            if L[1] <= 2.0 * L[0]:
                assert (EP.build(1, "flat", pts, tent, es) is not None) == R.flat(xc, True)[0]
        assert (EP.build(1, "impulse", pts, tent, es) is not None) == R.impulse(xc, True)
        if nc >= 3 and L[1] <= 2.0 * L[0] and (x[3] - x[1]) * d <= 0:
            assert (EP.build(1, "triangle", pts, tent, es) is not None) == R.triangle(xc, True, "contracting")[0]


# ---------------------------------------------------------------------------------------------------------------- 22–24
def test_shadow_old_modules_unchanged():
    from tests.test_pivots_dc import shadow_fingerprint
    fx = json.load(open(os.path.join(HERE, "fixtures", "pivots_shadow_baseline.json"), encoding="utf-8"))
    assert shadow_fingerprint() == fx


def test_caption_limits_and_no_code_keys():
    f1, f2, m15 = _run_fold(IMP_ZZ, (72, 158))
    j1, j2 = PF.rec_json(f1.out[f1.end], f1.ts), PF.rec_json(f2.out[f2.end], f2.ts)
    cap = PCH.caption(2, 30, asof_end(m15), j1, j2)
    assert len(cap.encode("utf-16-le")) // 2 <= 1024 and len(cap.splitlines()) <= 8
    assert cap.startswith("🧭 PATTERN CHECK 2/30") and "Reply" in cap
    for key in ("_", "{", "}", "None", "D1"):
        assert key not in cap


def test_no_date_literals_and_no_order_imports():
    paths = [os.path.join(ROOT, "patterns2", f) for f in os.listdir(os.path.join(ROOT, "patterns2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "pattern_check.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    for p in paths:
        assert not re.search(r"^\s*(?:from|import)\s+(?:broker|order|upstox_api|kite|shoonya|stocko)", open(p, encoding="utf-8").read(), re.M)


def test_script_writes_only_out_dir_and_rerun_is_byte_identical(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("pc", os.path.join(ROOT, "scripts", "pattern_check.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    from tests.test_pivots_dc import SLOTS, _monday
    rng = np.random.default_rng(4)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=26):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    before = set(os.listdir(tmp_path))
    outs = []
    for k in ("a", "b"):
        od = tmp_path / k
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "patterns/t", "--days", "1", "--futures-dir", ""]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert set(os.listdir(tmp_path)) - before == {"a", "b"}
    assert outs[0] == outs[1] and outs[0]
    man = json.loads(outs[0]["manifest.json"])
    assert all(it["kind"] == "pattern_check" for it in man["items"])


# ---------------------------------------------------------------------------------------------------------------- review नंतरचे tests
def test_dedupe_keeps_complete_wxy_apart_from_longer_prefix():
    prices = [100, 90, 99, 89, 96, 91, 94, 86, 90, 84]
    _, hs = fams(prices)
    nine = [h for h in hs if h["family"] == "combination" and h["L"] == 9 and h["bounds"] == list(range(10))]
    assert nine and nine[0]["info"]["X"].startswith("3")
    st = PF.hyp_state(nine[0], P(prices), I_UP, S)[0]
    assert st.startswith("final_leg") or st == "complete_resuming"


def test_change_record_keeps_old_family():
    f = _fold()
    st = {"pref": None, "chal": None, "n": 0}
    f._choose(st, [_h("flat", 0.5, (3,))], 0)
    _, ch = f._choose(st, [_h("triangle", 0.6, (5,))], 1)
    assert ch["from"] == "flat" and ch["to"] == "triangle"


def test_c_extension_is_same_hypothesis_not_change():
    f = _fold()
    st = {"pref": None, "chal": None, "n": 0}
    f._choose(st, [_h("flat", 0.5, (3, 6, 9))], 0)
    ext = _h("flat", 0.5, (3, 6, 12))                                              # C चं confirmed टोक पुढे
    got, ch = f._choose(st, [_h("zigzag", 0.55, (4,)), ext], 1)
    assert got is ext and ch is None and f.log[-1]["event"] == "extension"


def test_coarse_projection_keeps_identity():
    f = _fold()
    st = {"pref": None, "chal": None, "n": 0}
    f._choose(st, [_h("zigzag", 0.5, (3, 5, 7))], 0)                              # 5 हा फक्त D0 pivot
    c = dict(_h("zigzag", 0.5, (3, 7, 11)), coarse=True, P=[{"bar": b} for b in (0, 3, 7, 11)])
    got, ch = f._choose(st, [_h("flat", 0.55, (4,)), c], 1)
    assert got is c and ch is None


def test_kstart_and_impulse_phases_keep_k_history():
    f1, f2, m15 = _run_fold(IMP_ZZ, (72, 158))
    ph = [r["phase"] for r in f1.out.values()]
    firsts = [t for t, r in f1.out.items() if (r.get("change") or {}).get("why") == "पहिला preferred"]
    for t in firsts:                                                               # "पहिला preferred" फक्त नव्या I origin नंतर
        prev = [u for u in range(t) if f1.out[u].get("pref")]
        assert not prev or f1.out[prev[-1]]["I"]["origin"] != f1.out[t]["I"]["origin"]
    assert ph


def test_flat_subtype_pending_until_c_reaches_a():
    assert R.flat([100, 90, 101, 93], False) == (True, "प्रलंबित")
    assert R.flat([100, 90, 101, 93], True) == (True, "running")
    assert R.flat([100, 90, 101, 88], False) == (True, "expanded")


def test_tie_prefers_new_i_end_group():
    a = dict(_h("zigzag", 0.8, (1,), group=5), gi=1, bounds=[0, 1], t=0)
    b = dict(_h("triangle", 0.8, (2,), group=9), gi=0, bounds=[0, 1], t=0)
    order = {k: i for i, k in enumerate(PS.ORDER)}
    hs = sorted([a, b], key=lambda h: (-h["score"], h["gi"], order[h["family"]], tuple(h["bounds"]), h["t"]))
    assert hs[0] is b
