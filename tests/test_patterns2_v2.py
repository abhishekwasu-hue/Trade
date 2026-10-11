"""थर 3 v2.1 (patterns2: rules2, enum2, score2, fold2, momentum) — synthetic data फक्त, कुठलीही तारीख नाही (थर 3 §11)."""
import ast
import json
import os

import numpy as np
import pytest

from legs2 import ik2 as LI
from patterns2 import enum2 as EN
from patterns2 import fold2 as F2
from patterns2 import momentum as MO
from patterns2 import rules2 as R2
from patterns2 import score as SC1
from patterns2 import score2 as SC
from patterns2 import settings2 as PS
from tests.test_legs2 import DATE_RX_I
from tests.test_legs2_v2 import built

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = PS.load()


# ---------------------------------------------------------------------------------------------------------------- प्रकार नियम
def test_zigzag_flat_type_boundaries():
    x = lambda ba: [100.0, 90.0, 90.0 + 10 * ba]                           # noqa: E731  A = 10 खाली, B = ba × A
    assert R2.zigzag(x(0.5), True, S)[0] and not R2.flat(x(0.5), True, S)[0]          # < 0.618 ⇒ फक्त zigzag
    assert R2.zigzag(x(0.7), True, S)[0] and R2.flat(x(0.7), True, S)[0]              # 0.618–0.90 ⇒ दोन्ही
    assert not R2.zigzag(x(0.95), True, S)[0] and R2.flat(x(0.95), True, S)[0]        # 0.90–1.0 ⇒ फक्त flat
    assert not R2.zigzag(x(1.2), False, S)[0]                                         # B पलीकडे A-start ⇒ flat


def test_flat_b_over_2a_is_strong_evidence_not_invalid():
    ok, strong, info = R2.flat([100.0, 90.0, 115.0], True, S)
    assert ok and strong == ["flat B > 2A"]
    ok, strong, info = R2.flat([100.0, 90.0, 102.0, 85.0], True, S)
    assert ok and info["sub"] == "expanded"


def test_wedge_strong_evidence_and_incomplete_valid():
    ok, strong, _ = R2.wedge([100, 110, 99, 107, 101], False, "contracting", S)
    assert ok and "wedge 2 पलीकडे 1-start" in strong                           # 2 (99) < 1-start (100)
    ok, strong, _ = R2.wedge([100, 110, 103, 108], False, "contracting", S)
    assert ok and not strong                                                      # अपूर्ण wedge valid
    assert not R2.wedge([100, 110, 103, 115], True, "contracting", S)[0]          # 3 ≥ 1 ⇒ contracting नाही
    ok, strong, _ = R2.wedge([100, 110, 103, 108, 102], True, "contracting", S)
    assert ok and "wedge 4 पलीकडे 2-end" in strong


def test_triangle_and_impulse_k_types():
    assert R2.triangle([100, 90, 98, 92, 96, 93], True, "contracting", 0.0, S)[0]
    assert not R2.triangle([100, 90, 98, 92, 99], False, "contracting", 0.0, S)[0]    # D (99) पलीकडे B (98)
    assert R2.triangle([100, 95, 99, 93, 101], True, "expanding", 0.0, S)[0]
    assert R2.impulse_k([100, 110, 105, 125, 115, 130], True, S)[0]
    assert not R2.impulse_k([100, 110, 105, 125, 109, 130], True, S)[0]               # 4 हा 1 च्या पट्ट्यात


def _P(prices):
    return [{"price": float(p), "bar": i * 4, "kind": "H" if (i % 2 == 0) == (prices[1] < prices[0]) else "L", "tent": False}
            for i, p in enumerate(prices)]


def test_enum_both_readings_for_mid_ba_and_names_order_not_alphabetical():
    P = _P([100, 90, 97, 85])
    hs, hit = EN.enumerate_hyps(P, S)
    fams = {h["family"] for h in hs if len(h["bounds"]) == 4}
    assert {"zigzag", "flat"} <= fams and not hit
    assert PS.ORDER.index("zigzag") < PS.ORDER.index("flat") and list(PS.ORDER) != sorted(PS.ORDER)


# ---------------------------------------------------------------------------------------------------------------- गुण
class _Ctx(SC1.Ctx):
    pass


def _ctx(P, t=None):
    n = P[-1]["bar"] + 1
    h = np.array([max(p["price"] for p in P)] * n, float)
    lo = np.array([min(p["price"] for p in P)] * n, float)
    c = _Ctx(P, [], h, lo, [], t if t is not None else n - 1, 1.0, S)
    c.extra = {}
    return c


def test_score_strong_line_once_and_geo_mean_and_vol_time_not_identity():
    P = _P([100, 90, 112, 80])
    h = {"family": "flat", "kind": "", "L": 3, "bounds": [0, 1, 2, 3], "x": [100, 90, 112, 80], "t": 0, "done": False,
         "info": {"sub": "expanded", "strong": ["flat B > 2A", "flat B > 2A"]}}
    ctx = _ctx(P)
    ctx.extra = {"rv": np.ones(P[-1]["bar"] + 1), "bad": np.zeros(P[-1]["bar"] + 1, bool), "i_leg_bars": 4}
    SC.score(h, ctx)
    names = [n for n, _ in h["lines"]]
    assert names.count("मजबूत: flat B > 2A") == 1
    ms = [m for _, m in h["lines"]]
    assert h["score"] == pytest.approx(float(np.exp(np.mean(np.log(ms)))), rel=1e-4)
    assert not any("RVOL" in n or "I-leg" in n for n in names)                    # volume / वेळ ओळख-गुणात नाहीत
    assert any("RVOL" in n for n, _ in h["completion"])


def test_flat_ba_mid_band_rising_and_wedge_three_push_guideline():
    P = _P([100, 90, 97, 85])
    h = {"family": "flat", "kind": "", "L": 3, "bounds": [0, 1, 2, 3], "x": [100, 90, 97, 85], "t": 0, "done": False, "info": {}}
    SC.score(h, _ctx(P))
    m = dict(h["lines"])["B/A 0.70"]
    assert S["strong_penalty"] < m < 1.0
    P2 = _P([100, 110, 104, 109, 106, 108])
    w = {"family": "wedge", "kind": "contracting", "L": 5, "bounds": [0, 1, 2, 3, 4, 5], "x": [100, 110, 104, 109, 106, 108],
         "t": 0, "done": True, "info": {}}
    SC.score(w, _ctx(P2))
    assert dict(w["lines"])["3 पलीकडे 1-end"] == pytest.approx(S["three_push_m"])
    assert dict(w["completion"])["5 ने 3 गाठलं"] == pytest.approx(S["short_final_m"])


def test_apex_math():
    assert SC.apex([0, 10, 20, 30, 40], [0, 110, 90, 108, 92]) == pytest.approx(115.0)
    assert SC.apex([0, 10, 20, 30, 40], [0, 110, 90, 110, 90]) is None           # समांतर


# ---------------------------------------------------------------------------------------------------------------- अवस्था
def _h(fam, x, t, L=3):
    b = list(range(len(x)))
    return {"family": fam, "kind": "", "L": L, "bounds": b, "x": x, "t": t, "done": t == 1, "info": {}}


def test_states_complete_resuming_needs_cisd_or_llsb():
    P = _P([100, 110, 104, 113, 108])
    I = {"end": {"price": 100.0}, "dir": -1}                                        # I खाली, K वर
    h = _h("zigzag", [100, 110, 104, 113], 1)
    assert F2.hyp_state(h, P, I, {"cisd": None, "last_leg_start_broken": None}, S)[0] == "final_leg_present"
    assert F2.hyp_state(h, P, I, {"cisd": 7, "last_leg_start_broken": None}, S)[0] == "complete_resuming"
    assert F2.hyp_state(h, P, I, {"cisd": None, "last_leg_start_broken": 110.0}, S)[0] == "complete_resuming"
    h0 = _h("zigzag", [100, 110, 104, 113], 0)
    assert F2.hyp_state(h0, P[:4], I, {"cisd": 7}, S)[0] == "final_leg_in_progress"


def test_final_leg_short_flag_and_forming_states():
    P = _P([100, 110, 104, 108, 105])
    I = {"end": {"price": 100.0}, "dir": -1}
    st, fl = F2.hyp_state(_h("zigzag", [100, 110, 104, 108], 1), P, I, {"cisd": 3}, S)
    assert st == "complete_resuming" and "final_leg_short" in fl and "C_short_possible" in fl
    assert F2.hyp_state(_h("zigzag", [100, 110], 0), P[:2], I, {}, S)[0] == "forming_A"
    assert F2.hyp_state(_h("zigzag", [100, 110, 104], 0), P[:3], I, {}, S)[0] == "forming_B"
    assert F2.hyp_state(_h("impulse_k", [100, 110, 104, 120], 0, 5), P[:4], I, {}, S)[0] == "impulse_K"
    assert F2.hyp_state(_h("wedge", [100, 110, 104, 108], 0, 5), P[:4], I, {}, S)[0] == "forming_wedge"


def test_c_equals_a_and_lines():
    import pandas as pd
    P = _P([100, 110, 104, 113])
    h = _h("zigzag", [100, 110, 104, 113], 0)
    assert F2.c_equals_a(h, P) == pytest.approx(114.0)
    ts = pd.Series(pd.to_datetime(range(20), unit="h"))
    assert [ln["name"] for ln in F2.pattern_lines(h, P, ts)] == ["0–B"]


# ---------------------------------------------------------------------------------------------------------------- momentum
def test_hysteresis_two_bars_and_danger_immediate():
    hy = MO.Hysteresis(2)
    assert hy.step(MO.UNCLEAR) == MO.UNCLEAR
    assert hy.step(MO.WEAK) == MO.UNCLEAR
    assert hy.step(MO.WEAK) == MO.WEAK
    assert hy.step(MO.NOT, danger=True) == MO.NOT


def test_pushes_and_converge():
    P = _P([100, 110, 104, 109, 106, 108])
    h = _h("wedge", [100, 110, 104, 109, 106, 108], 0, 5)
    pu = MO.pushes_of(h, P, 1)
    assert len(pu) == 3 and pu[0][3] == 110
    assert MO.converge(pu, P, h, 1) is True                                       # टोकं घटतात, तळ वाढतात


@pytest.fixture(scope="module")
def folds():
    m15, res, st, lg = built(11, trend=0.6)
    trk = {d: LI.Tracker(lg, st, d) for d in (1, 2)}
    f2 = F2.Fold(lg, trk[2])
    f2.run()
    f1 = F2.Fold(lg, trk[1], parent=f2)
    f1.run()
    return m15, res, st, lg, trk, f1, f2


def test_momentum_items_verdict_rules(folds):
    *_, f1, f2 = folds
    got = 0
    for t, r in f1.out.items():
        m = r.get("momentum")
        if not m:
            continue
        got += 1
        assert len(m["items"]) == 12 and set(m["items"]) <= {MO.YES, MO.NO, MO.NA}
        assert m["items"][8] == MO.NA                                             # थर 4 आधी absorption NA
        rv = m["raw_verdict"]
        if m["danger"]:
            assert rv == MO.NOT
        elif m["non_na"] < S["m_min_non_na"]:
            assert rv == MO.NA_V                                                  # Abhi उत्तर 6: non-NA < 6 ⇒ NA
        elif m["pushes"] < 2:
            assert rv == MO.EARLY
        elif m["ratio"] >= S["m_hi"]:
            assert rv == MO.WEAK
        elif m["ratio"] <= S["m_lo"]:
            assert rv == MO.NOT
        else:
            assert rv == MO.UNCLEAR
        if r["pref"] is not None and r["agg"] != "none" and r["pref"]["family"] in ("wedge", "triangle"):
            assert m["items"][10] == MO.YES
        for note in m["notes"]:
            assert "danger नाही" in note
    assert got > 0


def test_momentum_reemit_with_zone_fills_item9(folds):
    m15, res, st, lg, trk, f1, f2 = folds
    t = next(t for t, r in f1.out.items() if r.get("momentum"))
    r = f1.out[t]
    I = trk[1].I_at(t)
    lg2 = dict(lg, vol=np.ones(len(m15)), rv=np.ones(len(m15)))
    f1.lg, keep = lg2, f1.lg
    try:
        m = f1.momentum(r, r["l2"], I, t, zone_fn=lambda price, tt: True, hyst=False)
    finally:
        f1.lg = keep
    assert m["item9_zone"] and m["items"][8] in (MO.YES, MO.NO)


def test_fold_replay_equals_truncated(folds):
    m15, res, st, lg, trk, f1, f2 = folds
    from legs2 import measure2 as M2
    from swings2 import engine as SE
    from swings2 import structure as SST
    cut = len(m15) - 40
    r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
    st2, rr2 = SST.all_structure(r2)
    lg2 = M2.build(r2, None, rr=rr2)
    t2 = {d: LI.Tracker(lg2, st2, d) for d in (1, 2)}
    g2 = F2.Fold(lg2, t2[2])
    g2.run()
    g1 = F2.Fold(lg2, t2[1], parent=g2)
    g1.run()
    for t in range(cut - 60, cut + 1, 7):
        a = json.dumps(F2.rec_json(f1.out[t], f1.ts), default=str, sort_keys=True)
        b = json.dumps(F2.rec_json(g1.out[t], g1.ts), default=str, sort_keys=True)
        assert a == b


def test_no_pattern_while_impulse_and_kstart_forming_a(folds):
    *_, f1, f2 = folds
    for r in f1.out.values():
        if r["phase"] == LI.ST_IMP:
            assert r["pref"] is None and r["agg"] == "impulse"
        if r["phase"] == LI.ST_KSTART:
            assert r["agg"] == "forming_A"


def test_position_ban_states(folds):
    *_, f1, f2 = folds
    for t, r in f1.out.items():
        p = r.get("position")
        if p and p.get("inside"):
            assert p["ban"] == (p["parent_state"] in F2.BAN_STATES)


def test_caption_and_box(folds):
    from patterns2 import charts2 as PC2
    m15, res, st, lg, trk, f1, f2 = folds
    t = len(m15) - 1
    j1, j2 = PC2.item_json(f1, f2, t)
    cap = PC2.caption(2, 9, m15["bar_end"].iloc[t], j1, j2, "momentum कमकुवत")
    assert len(cap.splitlines()) <= 8 and len(cap.encode("utf-16-le")) // 2 <= 1024
    for key in ("final_leg", "complete_resuming", "position_ban", "_"):
        assert key not in cap
    assert "momentum" in PC2.box_text(j1, j2)
    json.dumps(j1, default=str)
    rows = PC2.rows({1: f1, 2: f2}, t - 300, t)
    assert len(rows) == 2


def test_script_rerun_identical(tmp_path):
    import importlib.util

    import pandas as pd

    from tests.test_pivots_dc import SLOTS, _monday
    spec = importlib.util.spec_from_file_location("pc2", os.path.join(ROOT, "scripts", "pattern_check2.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(6)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=25):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0.05, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    outs = []
    for k in ("a", "b"):
        od = tmp_path / k
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "patterns2/t", "--days", "1",
                       "--futures-dir", str(tmp_path / "nofut")]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert outs[0] == outs[1] and outs[0]


def test_register_and_numbers_and_dates():
    for k in PS.DEFAULTS:
        assert k in " ".join(PS.REGISTER) or k in ("node_budget", "unknown_m", "one_match_m", "empty_m", "hysteresis_bars",
                                                   "fib_tol", "barrier_sigma", "flat_expanded_min", "moments_per_day"), k
    allowed = {0, 1, -1, 2, 3, 4, 5, 6, 7, 12, 40, 0.5, 1.0, 0.0, 1e9, 2e9, 0.146, 0.236, 0.382, 0.618, 0.786, 1.382, 1.618,
               2.618, 3.0}
    for f in ("rules2.py", "enum2.py", "score2.py", "fold2.py", "momentum.py"):
        tree = ast.parse(open(os.path.join(ROOT, "patterns2", f), encoding="utf-8").read())
        nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)}
        assert nums <= allowed, (f, nums - allowed)
    paths = [os.path.join(ROOT, "patterns2", f) for f in ("rules2.py", "enum2.py", "score2.py", "fold2.py", "momentum.py",
                                                          "settings2.py", "charts2.py")]
    paths += [os.path.join(ROOT, "scripts", "pattern_check2.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    for p in paths[:-2]:
        src = open(p, encoding="utf-8").read()
        for bad in ("broker", "place_order", "market_state", "chart_reader", "levels_v2", "import elliott"):
            assert f"import {bad}" not in src and f"from {bad}" not in src


def test_momentum_ratio_only_non_na_and_na_verdict():
    """Abhi उत्तर 6: ratio = ✓ ÷ non-NA (NA = ✗ नाही)."""
    items = [MO.YES] * 4 + [MO.NO] * 2 + [MO.NA] * 6
    non_na = [x for x in items if x != MO.NA]
    assert sum(x == MO.YES for x in non_na) / len(non_na) >= S["m_hi"]    # 4/6 = 0.67 ⇒ कमकुवत (NA मोजले असते तर 4/12)


def test_final_flag_measured_move():
    from types import SimpleNamespace as N

    from patterns2 import fold2 as F2
    A = {"h": np.array([100.0, 110, 108, 112, 120, 118]), "l": np.array([90.0, 100, 104, 105, 112, 114])}
    o = N(price=90.0, bar=0)
    e0, e1 = N(price=110.0, bar=1), N(price=126.0, bar=4)
    I = {"dir": 1, "origin": o, "ends": [e0, e1], "end": e1}
    mm = F2.measured_move(I, A, 120.0, 2.0, 1.0)                            # टोक = 104 (bars 2–4 चा low) ⇒ 104 + 20 = 124
    assert mm["target"] == 124.0 and mm["ok"]                                # चालू K पट्टा 120–126 ⇒ ✓
    I1 = {"dir": 1, "origin": o, "ends": [e0], "end": e0}
    assert F2.measured_move(I1, A, 104.0, 2.0, 1.0)["ok"] is False           # पहिला K अजून चालू ⇒ ✗
    far = {"dir": 1, "origin": o, "ends": [e0, N(price=160.0, bar=4)], "end": N(price=160.0, bar=4)}
    assert F2.measured_move(far, A, 150.0, 2.0, 1.0)["ok"] is False          # पट्टा 150–160, target 124 ⇒ ✗


def test_audit21_impulse_k_danger_not_suppressed_by_agg_none(folds, monkeypatch):
    """Audit #21 (🔴): सगळ्या hyps forming ⇒ agg "none" ⇒ आधी pref_family None ⇒ "impulse-K preferred" danger कधीच लागत नव्हता."""
    *_, f1, f2 = folds
    t = next(t for t, r in f1.out.items() if r.get("pref") is not None and r.get("momentum") is not None)
    rec = dict(f1.out[t], agg="none", pref=dict(f1.out[t]["pref"], family="impulse_k"))
    seen = {}
    real = MO.evaluate

    def spy(ctx, zone_fn=None):
        seen["fam"] = ctx["pref_family"]
        return real(ctx, zone_fn)
    monkeypatch.setattr(MO, "evaluate", spy)
    m = f1.momentum(rec, rec["l2"], f1.trk.I_at(t), t, hyst=False)
    assert seen["fam"] == "impulse_k" and "impulse-K preferred" in m["danger"] and m["verdict"] == MO.NOT
    assert "impulse_K" not in F2.FORMING
