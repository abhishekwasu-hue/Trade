"""थर 2 v2.1 (legs2: features, measure2, ik2) — synthetic data फक्त, कुठलीही तारीख नाही (थर 2 §9)."""
import ast
import json
import os

import numpy as np
import pandas as pd
import pytest

from legs2 import features as LF
from legs2 import ik2 as LI
from legs2 import measure as LM
from legs2 import measure2 as M2
from legs2 import settings2 as LS
from swings2 import engine as SE
from swings2 import structure as SST
from tests.test_legs2 import DATE_RX_I
from tests.test_pivots_dc import m15_from, walk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def built(seed, n_sess=45, step=5.0, trend=0.0):
    x = walk(25 * n_sess, seed, step) + trend * np.arange(25 * n_sess)
    m15 = m15_from(x)
    res = SE.build(m15)
    st, rr = SST.all_structure(res)
    lg = M2.build(res, None, rr=rr)
    return m15, res, st, lg


@pytest.fixture(scope="module")
def world():
    return built(11, trend=0.6)


def _A(o, h, l, c, first=None):
    n = len(o)
    return {"o": np.array(o, float), "h": np.array(h, float), "l": np.array(l, float), "c": np.array(c, float),
            "first": np.array(first if first is not None else [False] * n, bool)}


S = LS.load()


# ---------------------------------------------------------------------------------------------------------------- candle features
def test_clv_d_wick_opp_and_flat_candle():
    A = _A([100, 100], [110, 100], [100, 100], [108, 100])
    assert LF.clv_d(A, 0, 1) == pytest.approx(0.8) and LF.clv_d(A, 0, -1) == pytest.approx(0.2)
    assert LF.wick_opp_d(A, 0, 1) == pytest.approx(0.2)                    # up: high − max(o, c)
    assert LF.wick_opp_d(A, 0, -1) == pytest.approx(0.0)                   # down: min(o, c) − low
    assert LF.body_pct(A, 1) is None and LF.clv(A, 1) is None and LF.overlap(A, 1) is None   # H = L ⇒ NA


def test_overlap_session_pair_and_overlap3_union():
    A = _A([0] * 5, [10, 12, 14, 16, 13], [0, 2, 4, 6, 9], [0] * 5, first=[True, False, False, True, False])
    assert LF.overlap(A, 3) is None                                        # session ओलांडणारी जोडी नाही
    assert LF.overlap(A, 1) == pytest.approx(8 / 10)
    assert LF.overlap3(A, 2) == pytest.approx((12 - 4) / 10)               # union [0, 12] (दोन आधीच्या; session सुरुवात)
    assert LF.overlap3(A, 4) == pytest.approx((13 - 9) / 4)                # session च्या पहिल्या candle शीच


def test_climax_fvg_and_trend_candle():
    rr = np.array([1.0, 2.5, 2.5, 1.0])
    A = _A([100, 100, 110, 100], [101, 112, 111, 120], [99, 99, 100, 115], [100, 111, 101, 119])
    assert LF.climax_candle(A, rr, 1, 1, S) and not LF.climax_candle(A, rr, 2, 1, S)   # दिशेने बंद हवी
    assert LF.fvg(A, 3, 1)                                                  # low[3] 115 > high[1] 112
    assert LF.trend_candle(A, 3, 1, S) and not LF.trend_candle(A, 0, 1, S)


def test_er_clamp_gap_excluded_and_na():
    A = _A([100, 101, 130, 131], [0] * 4, [0] * 4, [100, 102, 131, 132], first=[False, False, True, False])
    assert LF.er(A, 0, 3) == pytest.approx(1.0)                            # gap (28) वजा; उरलेली चाल सरळ
    B = _A([100] * 3, [0] * 3, [0] * 3, [100, 100, 100])
    assert LF.er(B, 0, 2) is None                                          # denominator 0 ⇒ NA


# ---------------------------------------------------------------------------------------------------------------- baseline / V
def _leg(raw, **kw):
    L = {"raw": raw, "warmup": False, "gap_leg_theta": False, "seg": 0}
    L.update(kw)
    return L


def test_baseline_excludes_self_short_gap_warmup_and_na_warmup_bands():
    raw = {"er": 0.5, "overlap": 0.5, "body": 0.5, "dirc": 0.5}
    base = [_leg(dict(raw)) for _ in range(9)]
    me = _leg(dict(raw))
    assert M2.c_score(me, base + [me], S)["C_na"]                          # स्वतः मोजला जात नाही ⇒ 9 < 10
    bad = [_leg(dict(raw), warmup=True), _leg(None), _leg(dict(raw), gap_leg_theta=True)]
    assert M2.c_score(me, base + bad, S)["n_base"] == 9
    r = M2.c_score(me, base + [_leg(dict(raw))], S)
    assert r["n_base"] == 10 and r["c_warmup"] and r["C"] == pytest.approx(0.5)     # बरोबरी ⇒ सरासरी rank 0.5
    r40 = M2.c_score(me, [_leg(dict(raw)) for _ in range(45)], S)
    assert r40["n_base"] == 40 and not r40["c_warmup"]
    short = _leg(None)
    assert M2.c_score(short, base, S)["c_cls"] == LM.NEU and not M2.c_score(short, base, S)["C_na"]


def test_v_needs_three_reliable_bars_each():
    a = {"rv_bars": (np.array([2.0, 2.0]), np.zeros(2, bool))}
    b = {"rv_bars": (np.array([1.0, 1.0, 1.0]), np.zeros(3, bool))}
    assert M2.v_score(a, b, S)["V"] is None and "reliable" in M2.v_score(a, b, S)["v_why"]
    a3 = {"rv_bars": (np.array([2.0, 2.0, 2.0]), np.zeros(3, bool))}
    out = M2.v_score(a3, b, S)
    assert out["V"] == pytest.approx(2.0) and out["v_cls"] == LM.IMP
    half_bad = {"rv_bars": (np.array([2.0] * 6), np.array([True] * 4 + [False] * 2))}
    assert M2.v_score(half_bad, b, S)["V"] is None


def test_cxv_table_all_nine_and_labels():
    want = {(LM.IMP, LM.IMP): LM.IMP, (LM.IMP, LM.NEU): LM.IMP, (LM.NEU, LM.IMP): LM.IMP, (LM.COR, LM.COR): LM.COR,
            (LM.COR, LM.NEU): LM.COR, (LM.NEU, LM.COR): LM.COR, (LM.IMP, LM.COR): LM.NEU, (LM.COR, LM.IMP): LM.NEU,
            (LM.NEU, LM.NEU): LM.NEU}
    for k, v in want.items():
        assert LM.nature(*k)[0] == v
    assert LM.nature(LM.NEU, LM.IMP)[1] and LM.nature(LM.NEU, LM.COR)[1]                   # कमकुवत
    assert LM.label(LM.ROLE_DOM, LM.COR) == "विरोध-1" and LM.label(LM.ROLE_RET, LM.IMP) == "विरोध-2"


# ---------------------------------------------------------------------------------------------------------------- legs
def test_legs_scope_labels_only_d1_d2_and_r_only_d3(world):
    _, res, st, lg = world
    for d, legs in lg["legs"].items():
        for L in legs:
            assert L["known_at"] == L["b"].known_at
            if d in (1, 2):
                assert L["label"] is not None
            else:
                assert L["label"] is None
            if d == 3:
                assert L["nature"] is None
        for a, b in zip(legs, legs[1:]):
            assert a["known_at"] <= b["known_at"]


def test_leg_measure_frozen_under_truncation(world):
    m15, res, st, lg = world
    cut = len(m15) - 80
    r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
    st2, rr2 = SST.all_structure(r2)
    lg2 = M2.build(r2, None, rr=rr2)
    t = pd.Timestamp(m15["bar_end"].iloc[cut])
    for d in (0, 1, 2):
        a = [json.dumps(M2.leg_json(L), default=str) for L in M2.known(lg, d, t)]
        b = [json.dumps(M2.leg_json(L), default=str) for L in M2.known(lg2, d, t)]
        assert a == b


def test_current_leg(world):
    m15, res, st, lg = world
    t = pd.Timestamp(m15["bar_end"].iloc[-1])
    L = M2.current(lg, 1, t)
    if L is not None:
        assert L["current"] and L["b"] is None and L["label"] is not None


# ---------------------------------------------------------------------------------------------------------------- I / K
@pytest.fixture(scope="module")
def tracker(world):
    _, res, st, lg = world
    return LI.Tracker(lg, st, 1)


def test_I_direction_matches_parent_trend_and_sticky_end(world, tracker):
    m15, res, st, lg = world
    seen = 0
    for b, I in tracker.timeline:
        if I is None or b < 0:
            continue
        seen += 1
        tr = tracker.ctx(b)[0]                                              # पालक (unknown ⇒ स्वतःचा, उत्तर 5)
        if I["mode"] == LI.MODE_TREND and b == I["since"]:
            assert tr == (SST.UPT if I["dir"] > 0 else SST.DNT)
        if I["mode"] == LI.MODE_RANGE:
            assert tr == SST.RNG
        A = lg["A"]
        for prev, nxt in zip(I["ends"], I["ends"][1:]):                   # I_end सरकला ⇒ त्या leg मध्ये close पलीकडे
            cl = A["c"][prev.bar + 1:nxt.bar + 1]
            assert (cl > prev.price).any() if I["dir"] > 0 else (cl < prev.price).any()
    assert seen > 0


def test_sweep_of_I_end_keeps_end():
    I = {"dir": 1, "end": SimpleP(110, 5), "ends": [SimpleP(110, 5)], "sweeps": []}
    tr = object.__new__(LI.Tracker)
    tr.A = _A([100] * 10, [100] * 10, [90] * 10, [100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
    tr.log = []
    tr._extend(I, {"a": SimpleP(100, 6), "b": SimpleP(112, 9), "dir": 1}, 9)
    assert I["end"].price == 110 and I["sweeps"][-1].price == 112           # closes ≤ 110 ⇒ फक्त wick
    tr.A["c"][8] = 111
    tr._extend(I, {"a": SimpleP(100, 6), "b": SimpleP(113, 9), "dir": 1}, 9)
    assert I["end"].price == 113


class SimpleP:
    def __init__(self, price, bar, kind="H"):
        self.price, self.bar, self.kind = price, bar, kind


def test_origin_break_end_equals_decision_bar(world, tracker):
    m15, res, st, lg = world
    for b, I in tracker.timeline:
        if I is None or b < 0:
            continue
        c = tracker.origin_break(I["origin"], I["dir"])
        if c is not None:
            assert tracker.origin_break(I["origin"], I["dir"], end=c) == c
            assert tracker.origin_break(I["origin"], I["dir"], end=c - 1) is None
        break


def test_cancel_reasons_logged_and_no_same_I_after_cancel(tracker):
    ends = {}
    for e in tracker.log:
        if e["event"].startswith("I रद्द"):
            assert e["event"] in ("I रद्द: I_origin real break", "I रद्द: थर 1 reversal (I-विरुद्ध)")
    prev = None
    for b, I in tracker.timeline:
        if prev is not None and I is not None and prev is not None and I["since"] == b and prev["end"].bar >= I["end"].bar \
                and any(x["bar"] == b and x["event"].startswith("I रद्द") for x in tracker.log):
            raise AssertionError("रद्द नंतर तोच / जुना I")
        prev = I if I is not None else prev
    assert isinstance(ends, dict)


def test_state_replay_equals_truncated_build(world, tracker):
    m15, res, st, lg = world
    cut = len(m15) - 60
    r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
    st2, rr2 = SST.all_structure(r2)
    lg2 = M2.build(r2, None, rr=rr2)
    t2 = LI.Tracker(lg2, st2, 1)
    for t in (cut - 30, cut - 7, cut):
        a = json.dumps(tracker.state(t), default=str, sort_keys=True)
        b = json.dumps(t2.state(t), default=str, sort_keys=True)
        assert a == b


def test_states_and_k_fields(world, tracker):
    m15, res, st, lg = world
    got = set()
    for t in range(len(m15) - 200, len(m15), 3):
        x = tracker.state(t)
        got.add(x["state"])
        assert x["state"] in (LI.ST_NONE, LI.ST_IMP, LI.ST_KSTART, LI.ST_K)
        if x["state"] in (LI.ST_K, LI.ST_KSTART):
            K = x["K"]
            assert "depth_secondary" in K and "rvol_K" in K
            assert set(x["flags"]) >= {"pullback_quiet", "pullback_heavy", "choch_strict", "choch_disp", "cisd", "last_leg_start_broken"}
        if x["I"] is not None:
            assert x["I"]["quality"] in ("spike", "channel")
    assert len(got) >= 2


def test_d2_tracker_runs(world):
    _, res, st, lg = world
    t2 = LI.Tracker(lg, st, 2)
    x = t2.state(len(res["m15"]) - 1)
    assert x["degree"] == 2


def test_range_alt_mode(world, monkeypatch):
    _, res, st, lg = world
    def fake_parent(self, t):
        return SST.RNG, (20400.0, 19600.0), None
    monkeypatch.setattr(LI.Tracker, "parent", fake_parent)
    tr = LI.Tracker(lg, st, 1)
    modes = {I["mode"] for b, I in tr.timeline if I is not None}
    assert modes <= {LI.MODE_RANGE}
    for b, I in tr.timeline:
        if I is not None:
            c = lg["A"]["c"][b]                                                # जवळची कड = t च्या close ला (K तिकडे येते)
            near_bot = abs(c - 19600.0) <= abs(c - 20400.0)
            assert I["dir"] == (1 if near_bot else -1) and I["edge"] == ("bottom" if near_bot else "top")


def test_unknown_parent_and_own_unknown_no_I(world, monkeypatch):
    _, res, st, lg = world
    monkeypatch.setattr(LI.Tracker, "parent", lambda self, t: (SST.UNK, None, None))
    monkeypatch.setattr(LI.Tracker, "ctx", lambda self, t: (SST.UNK, None, None, True))
    tr = LI.Tracker(lg, st, 1)
    assert all(I is None for _, I in tr.timeline)
    assert tr.state(len(res["m15"]) - 1)["why"] == "trend unknown (पालक आणि स्वतःचा)"


def test_unknown_parent_uses_own_trend_with_htf_unknown(world, monkeypatch):
    """Abhi उत्तर 5: पालक unknown ⇒ स्वतःच्या degree चा Dow trend + htf_unknown; RANGE ⇒ range_alt."""
    _, res, st, lg = world
    monkeypatch.setattr(LI.Tracker, "parent", lambda self, t: (SST.UNK, None, None))
    tr = LI.Tracker(lg, st, 1)
    Is = [(b, I) for b, I in tr.timeline if I is not None]
    assert Is
    for b, I in Is:
        assert I["htf_unknown"] is True
        own = st[1]["states"][b]["trend"]
        if I["mode"] == LI.MODE_RANGE:
            assert own == SST.RNG
        elif I["since"] == b:
            assert own == (SST.UPT if I["dir"] > 0 else SST.DNT)
    t = Is[-1][0]
    assert tr.state(t)["I"]["htf_unknown"] is True


def test_I_mode_follows_parent_state_every_candle(world, monkeypatch):
    """Abhi उत्तर 4: I_mode = प्रत्येक candle ला पालक trend चं function. पालक RANGE (पट्ट्यासह) ⇒ I नाही किंवा range_alt; पालक trend
    ⇒ I नाही किंवा trend-mode; RANGE तुटल्यावर trend I पुन्हा शोधला जातो."""
    m15, res, st, lg = world
    n = len(m15)

    def par(self, t):                                                      # trend / RANGE / trend पट्टे
        if (t // 150) % 2 == 1:
            return SST.RNG, (float(np.max(self.A["h"][:t + 1])), float(np.min(self.A["l"][:t + 1]))), None
        return SST.UPT, None, float(np.min(self.A["l"][max(t - 100, 0):t + 1]))     # protected = खरा low (origin_bounded)
    monkeypatch.setattr(LI.Tracker, "parent", par)
    tr = LI.Tracker(lg, st, 1)
    n_rng = n_tr = 0
    for t in range(n):
        I = tr.I_at(t)
        if I is None:
            continue
        if (t // 150) % 2 == 1:
            assert I["mode"] == LI.MODE_RANGE
            n_rng += 1
        else:
            assert I["mode"] == LI.MODE_TREND and I["dir"] > 0
            n_tr += 1
    assert n_rng and n_tr
    ev = {e["event"] for e in tr.log}
    assert "mode बदल: पालक RANGE ⇒ range_alt" in ev and "range_alt संपला (पालक trend)" in ev


def test_range_alt_rediscovers_when_near_edge_changes(world, monkeypatch):
    """Review: पालक RANGE तसाच, नवा leg नाही, पण close दुसऱ्या कडेजवळ गेला ⇒ range_alt पुन्हा शोधला जातो (I नाही अडकत नाही)."""
    m15, res, st, lg = world
    band = (float(np.max(lg["A"]["h"])), float(np.min(lg["A"]["l"])))
    monkeypatch.setattr(LI.Tracker, "parent", lambda self, t: (SST.RNG, band, None))
    tr = LI.Tracker(lg, st, 1)
    for t in range(len(m15)):
        I = tr.I_at(t)
        want = 1 if tr.near_edge(t, band) == "bottom" else -1
        if I is not None:
            assert I["dir"] == want
    flips = [t for t in range(1, len(m15)) if tr.near_edge(t, band) != tr.near_edge(t - 1, band)]
    assert flips
    snaps = {b for b, _ in tr.timeline}
    assert all(t in snaps for t in flips)                                      # प्रत्येक कड-बदलाला पुन्हा शोध


def test_range_alt_mid_band_no_edge_and_parent_flip(world, monkeypatch):
    """Abhi batch 2: (1-a) close मध्यापासून ±1 σ_1H ⇒ कड नाही ⇒ I नाही; (3) पालक थेट उलटला ⇒ parent_flip रद्द."""
    m15, res, st, lg = world
    tr = LI.Tracker(lg, st, 1)
    t = len(m15) - 1
    c = float(lg["A"]["c"][t])
    s1 = res["sigma_1h"].get(pd.Timestamp(tr.ts.iloc[t]).normalize())
    assert tr.near_edge(t, (c + 0.5 * s1, c - 0.5 * s1)) is None                # मध्यावर
    assert tr.near_edge(t, (c + 10 * s1, c - 0.5 * s1)) == "bottom"
    n = len(m15)

    def up(self, t):
        return SST.UPT, None, float(np.min(self.A["l"][max(t - 100, 0):t + 1]))
    monkeypatch.setattr(LI.Tracker, "parent", up)
    tu = LI.Tracker(lg, st, 1)
    flip = next(t for t in range(n // 2, n) if tu.I_at(t) is not None and tu.I_at(t)["dir"] > 0) + 1   # UP I चालू असताना उलट

    def par(self, t):
        return (SST.UPT if t < flip else SST.DNT), None, float(np.min(self.A["l"][max(t - 100, 0):t + 1]))
    monkeypatch.setattr(LI.Tracker, "parent", par)
    tr2 = LI.Tracker(lg, st, 1)
    for t in range(flip, n):
        I = tr2.I_at(t)
        if I is not None and I["mode"] == LI.MODE_TREND:
            assert I["dir"] < 0                                                # उलटल्यावर जुना UP I टिकत नाही
    assert any(e["event"] == "I रद्द: parent_flip" for e in tr2.log)


def test_I_mode_real_parent_consistent(world, tracker):
    _, res, st, lg = world
    for t in range(len(res["m15"])):
        I = tracker.I_at(t)
        tr, band, _, hu = tracker.ctx(t)
        if I is None:
            continue
        if tr == SST.RNG and band is not None:
            assert I["mode"] == LI.MODE_RANGE and I["band"] == band
        if tr in (SST.UPT, SST.DNT):
            assert I["mode"] == LI.MODE_TREND


def test_origin_bounded_uses_parent_protected():
    tr = object.__new__(LI.Tracker)
    tr.res = {"segments": {pd.Timestamp(0).normalize(): 0}}
    tr.segs = np.zeros(10, int)
    tr.A = _A([0] * 10, [0] * 10, [5, 4, 3, 2, 1, 6, 7, 8, 9, 9], [0] * 10)
    tr.ts = pd.Series([pd.Timestamp(0)] * 10)
    end = type("P", (), {"price": 50.0, "bar": 8, "kind": "H", "ts": pd.Timestamp(0), "sigma": 1.0})()
    o, bounded = tr.origin_of([], end, 1, 9, 1.0)
    assert bounded and o.price == 1.0 and o.bar == 4
    assert tr.origin_of([], end, 1, 9, None) == (None, True)


def test_cisd_body_close_beyond_counter_run_open():
    # I वर; K: तीन लाल candles (पहिल्याचा open 105), मग हिरवी close 106 ⇒ cisd
    A = _A([0, 105, 103, 101, 100, 102], [0] * 6, [0] * 6, [0, 103, 101, 99, 104, 106])
    assert LI.cisd(A, 0, 4, 1) is None                                      # 104 < 105
    assert LI.cisd(A, 0, 5, 1) == 5
    A2 = _A([0, 105, 103, 101, 100, 101, 100.5], [0] * 7, [0] * 7, [0, 103, 101, 99, 101, 100, 102])
    assert LI.cisd(A2, 0, 6, 1) == 6                                        # 101→100 नवा counter run (open 101); 102 > 101
    assert LI.cisd(A2, 0, 5, 1) is None


def test_last_leg_start_broken():
    class P:
        def __init__(self, kind, price, bar, cb):
            self.kind, self.price, self.bar, self.confirm_bar = kind, price, bar, cb
    A = _A([0] * 8, [0] * 8, [0] * 8, [0, 0, 0, 0, 0, 0, 104, 107])
    lower = [P("H", 110, 2, 3), P("L", 100, 3, 4), P("H", 106, 4, 5), P("L", 101, 5, 6)]
    assert LI.last_leg_start_broken(A, lower, 2, 6, 1) is None              # 104 < 106
    assert LI.last_leg_start_broken(A, lower, 2, 7, 1) == 106


def test_quality_spike_and_sot(world, tracker):
    for b, I in tracker.timeline:
        if I is not None:
            tracker._now = len(tracker.F) - 1
            q = tracker.quality(I)
            assert q["kind"] in ("spike", "channel") and q["SOT_trend"] in (None, True, False)
            break


# ---------------------------------------------------------------------------------------------------------------- register / shadow / तारीख
def test_register_covers_defaults_and_numbers():
    reg = " ".join(LS.REGISTER)
    for k in LS.DEFAULTS:
        if k in ("nature_degrees", "label_degrees", "degrees", "ik_degrees"):
            continue
        assert k in reg or k.split("_")[0] in reg, k
    allowed = {0, 1, -1, 2, 3, 4, 100.0, 1e-9, 0.5, 1.0, 0.0}
    for f in ("features.py", "measure2.py", "ik2.py"):
        tree = ast.parse(open(os.path.join(ROOT, "legs2", f), encoding="utf-8").read())
        nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)}
        assert nums <= allowed, (f, nums - allowed)


def test_no_date_literals_and_no_live_imports():
    paths = [os.path.join(ROOT, "legs2", f) for f in ("features.py", "measure2.py", "ik2.py", "settings2.py")]
    paths.append(os.path.abspath(__file__))
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    for p in paths[:-1]:
        src = open(p, encoding="utf-8").read()
        for bad in ("broker", "place_order", "telegram", "market_state", "chart_reader", "levels_v2"):
            assert f"import {bad}" not in src and f"from {bad}" not in src


def test_caption_limits_and_no_code_keys(world, tracker):
    from legs2 import charts2 as L2C
    m15, res, st, lg = world
    t = len(m15) - 1
    trk = {1: tracker, 2: LI.Tracker(lg, st, 2)}
    sts = {d: trk[d].state(t) for d in trk}
    cap = L2C.caption(3, 9, m15["bar_end"].iloc[t], sts, "cisd")
    assert len(cap.splitlines()) <= 8 and len(cap.encode("utf-16-le")) // 2 <= 1024
    for key in ("choch_strict", "pullback_quiet", "I_strict_HL", "origin_bounded", "range_alt", "_"):
        assert key not in cap
    box = L2C.ik_line(sts[1], "15M")
    assert "I" in box
    rows = L2C.rows(lg, trk, t - 300, t)
    assert {r["degree"] for r in rows} == {"D1", "D2"}


def test_script_writes_only_out_dir_and_rerun_is_byte_identical(tmp_path):
    import importlib.util
    from tests.test_pivots_dc import SLOTS, _monday
    spec = importlib.util.spec_from_file_location("lc2", os.path.join(ROOT, "scripts", "leg_check2.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(4)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=25):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0.05, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    before = set(os.listdir(tmp_path))
    outs = []
    for k in ("a", "b"):
        od = tmp_path / k
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "legs2/t", "--days", "1",
                       "--futures-dir", str(tmp_path / "nofut")]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert set(os.listdir(tmp_path)) - before == {"a", "b"}
    assert outs[0] == outs[1] and outs[0]


@pytest.mark.parametrize("seed", [12, 16])
def test_audit11_k_state_not_stuck_after_sweep_of_I_end(seed):
    """Audit #11 (🔴): I_end पलीकडे फक्त wick (sweep) ⇒ tentative टोक eb ≠ I_end; त्यानंतर confirmed D1 leg / उलट D1 pivot आला तरी
    आधी "K सुरू झाला असावा" कायम राहायचा. आता eb नंतर सुरू होणारा confirmed D1 leg (किंवा उलट D1 pivot) ⇒ "K चालू"."""
    m15, res, st, lg = built(seed, trend=0.0)                                # या seeds मध्ये I_end पलीकडे फक्त wick (sweep) येतो
    tr = LI.Tracker(lg, st, 1)
    checked = swept = 0
    for t in range(len(m15) // 3, len(m15)):
        x = tr.state(t)
        if x["state"] not in (LI.ST_K, LI.ST_KSTART) or x["I"] is None:
            continue
        eb = x["k_from_bar"]
        I = tr.I_at(t)
        legs_after = [L for L in tr.legs if L["a"].bar >= max(eb, I["end"].bar) and L["b"].confirm_bar <= t]
        opp = "L" if I["dir"] > 0 else "H"
        piv_after = [p for p in tr.piv if p.kind == opp and p.bar > eb and p.confirm_bar <= t] if eb != I["end"].bar else []
        if legs_after or piv_after:
            assert x["state"] == LI.ST_K, (t, eb)
            checked += 1
            swept += eb != I["end"].bar
    assert checked and swept                                                   # sweep-नंतरचे प्रसंग खरंच तपासले
