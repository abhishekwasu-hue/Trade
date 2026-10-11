"""थर 6 (rsi2) — synthetic data फक्त, कुठलीही तारीख नाही (थर 6 §7)."""
import ast
import json
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from chart_reader import evidence as EV
from legs2 import ik2 as LI
from patterns2 import fold2 as F2
from rsi2 import engine as RE
from rsi2 import layer as RL
from rsi2 import settings as RS
from tests.test_legs2 import DATE_RX_I
from tests.test_legs2_v2 import built

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


@pytest.fixture(scope="module")
def world():
    m15, res, st, lg = built(11, trend=0.6)
    trk = {d: LI.Tracker(lg, st, d) for d in (1, 2)}
    f2 = F2.Fold(lg, trk[2])
    f2.run()
    f1 = F2.Fold(lg, trk[1], parent=f2)
    f1.run()
    R = RE.RSI(lg, st)
    L6 = RL.run(R, trk, f1)
    return m15, res, st, lg, trk, f1, R, L6


def test_rsi_equals_evidence_and_segmented(world):
    m15, res, st, lg, trk, f1, R, L6 = world
    c = lg["A"]["c"]
    if len(set(R.segs)) == 1:
        assert np.allclose(R.r15, EV.rsi(c, 14), equal_nan=True)
    segs = np.array([0] * 30 + [1] * 30)
    x = np.arange(60, dtype=float)
    out = RE.rsi_segmented(x, segs, 14)
    assert np.isnan(out[30:44]).all() and np.isfinite(out[44:]).all()            # नव्या segment ला warm-up पुन्हा
    assert R.warm[0] and not R.warm[-1]


def _R(close, low=None, sig=10.0):
    n = len(close)
    R = object.__new__(RE.RSI)
    R.s = RS.load()
    R.A = {"c": np.array(close, float), "l": np.array(low if low is not None else close, float)}
    R.r15 = EV.rsi(R.A["c"], 14)
    R.warm = np.zeros(n, bool)
    R.sig = np.full(n, sig)
    R.ts = pd.Series(pd.to_datetime(np.arange(n) * 900, unit="s"))
    R.res = {"gap_bar_2s": []}
    R.bar_to_h1 = np.arange(n) // 4
    R.h1_end = np.arange(n // 4 + 1) * 4 + 3
    return R


def P(kind, price, bar, cb=None):
    return SimpleNamespace(kind=kind, price=price, bar=bar, confirm_bar=bar + 2 if cb is None else cb, ts=None)


def test_four_types_thresholds_and_grade():
    rng = np.random.default_rng(3)
    c = list(100 + np.cumsum(rng.normal(0, 1, 80)))
    R = _R(c)
    a, b = P("L", 100.0, 30), P("L", 95.0, 60)
    R.r15[30], R.r15[60] = 25.0, 35.0
    x = R.pair(a, b, 0, "L")
    assert x["type"] == RE.REG_BULL and x["grade"] == "मजबूत" and x["known_bar"] == 62
    R.r15[30] = 45.0
    R.r15[60] = 49.0
    assert R.pair(a, b, 0, "L")["grade"] == "कमकुवत"
    R.r15[60] = 47.0                                                               # Δr 2 < 3 ⇒ नाही
    assert R.pair(a, b, 0, "L") is None
    b2 = P("L", 104.0, 60)
    R.r15[60] = 40.0
    assert R.pair(a, b2, 0, "L")["type"] == RE.HID_BULL
    h1, h2 = P("H", 110.0, 30), P("H", 115.0, 60)
    R.r15[30], R.r15[60] = 75.0, 65.0
    assert R.pair(h1, h2, 0, "H")["type"] == RE.REG_BEAR
    R.r15[60] = 80.0
    assert R.pair(h1, P("H", 105.0, 60), 0, "H")["type"] == RE.HID_BEAR
    assert R.pair(a, P("L", 99.0, 60), 0, "L") is None                             # |Δp| 1 < 0.25 σ (2.5)


def test_line_and_price_clear():
    c = [100.0] * 40
    R = _R(c)
    R.r15 = np.full(40, 50.0)
    R.r15[5], R.r15[30] = 30.0, 40.0
    a, b = P("L", 100.0, 5), P("L", 95.0, 30)
    lc, pc = R._clear(a, b, "L")
    assert lc and pc
    R.r15[15] = 20.0                                                               # मध्ये RSI रेघेखाली
    assert not R._clear(a, b, "L")[0]
    R.A["c"][15] = 80.0                                                            # मध्ये close price रेघेखाली
    assert not R._clear(a, b, "L")[1]


def test_detector_dedupe_highest_degree_and_known_at(world):
    m15, res, st, lg, trk, f1, R, L6 = world
    keys = [(x["L1"]["bar"], x["L2"]["bar"]) for x in R.divs]
    assert len(keys) == len(set(keys))
    for x in R.divs:
        assert x["line_clear"] and x["price_clear"]
        lo, hi = R.s["gaps"][x["degree"]]
        if x["degree"] != 2:
            assert lo <= x["gap"] <= hi
        L2 = next(p for p in res["pivots"][0] if p.bar == x["L2"]["bar"])
        assert x["known_bar"] >= L2.confirm_bar


def test_classifier_bands_and_shift():
    R = _R([100.0] * 100)
    R.st = {1: {"events": []}}
    R.r15 = np.r_[np.full(50, 45.0), np.linspace(45, 70, 50)]
    R.rpiv15 = R._rsi_pivots(R.r15, None)
    out = R.classify(99, "15M")
    assert out["range"] in (RE.BULL, RE.NEUTRAL)
    R.r15 = np.full(100, 50.0)
    R.r15[60:70] = 30.0
    R.rpiv15 = R._rsi_pivots(R.r15, None)
    assert R.classify(99, "15M")["range"] == RE.BEAR                              # max 50 ≤ 62, min 30 ≤ 35
    R.r15[80:85] = 64.0
    R.rpiv15 = R._rsi_pivots(R.r15, None)
    assert R.classify(99, "15M")["range"] == RE.NEUTRAL                           # max 64 > 62
    R.r15 = np.r_[np.full(40, 50.0), np.full(10, 33.0), np.full(50, 55.0)]
    R.r15[45] = 30.0
    R.r15[70] = 58.0
    R.rpiv15 = R._rsi_pivots(R.r15, None)
    w = R.classify(99, "15M")
    assert w["warn"] in (None, "bull→bear") and not w["confirmed"]                # CHoCH नाही ⇒ confirmed नाही


def test_mapping_reversal_priority_and_1h_first():
    s = RS.load()
    on_k = {"type": RE.HID_BULL, "rsi2": 45.0}
    sp = {"on_K": on_k, "regular_in_K": {"type": RE.REG_BULL}, "at_impulse_end": None}
    labels, final = RE.mapping({"range": RE.BULL}, {"range": RE.BULL}, sp, [], False, False, s)
    assert final == "K संपतोय" and labels[0][0] == "1H"
    labels, final = RE.mapping({"range": RE.NEUTRAL}, {"range": RE.NEUTRAL}, {"on_K": None, "regular_in_K": None,
                                                                             "at_impulse_end": None}, [], True, True, s)
    assert final == "range-fade पुरावा"
    _, final = RE.mapping({"range": RE.BULL}, None, {"on_K": None, "regular_in_K": None, "at_impulse_end": {"type": RE.REG_BEAR}},
                          [{"type": RE.REG_BEAR}], False, False, s)
    assert final in ("continuation trap / risk", "trend मजबूत")


def test_layer_truncation_and_fields(world):
    m15, res, st, lg, trk, f1, R, L6 = world
    from legs2 import measure2 as M2
    from swings2 import engine as SE
    from swings2 import structure as SST
    cut = len(m15) - 30
    r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
    st2, rr2 = SST.all_structure(r2)
    lg2 = M2.build(r2, None, rr=rr2)
    t2 = {d: LI.Tracker(lg2, st2, d) for d in (1, 2)}
    g2 = F2.Fold(lg2, t2[2])
    g2.run()
    g1 = F2.Fold(lg2, t2[1], parent=g2)
    g1.run()
    R2 = RE.RSI(lg2, st2)
    L62 = RL.run(R2, t2, g1)
    for t in (cut - 20, cut - 3, cut):
        a = json.dumps(L6[t], default=str, sort_keys=True)
        b = json.dumps(L62[t], default=str, sort_keys=True)
        assert a == b
    for r in L6.values():
        if r["on_K"]:
            assert r["on_K"]["ref"] in ("I_origin", "I_strict_HL") and r["on_K"]["type"] in (RE.HID_BULL, RE.HID_BEAR)
            assert r["on_K"]["on_K_known_bar"] <= r["bar"]


def test_caption_and_rows(world):
    from rsi2 import charts as RC
    m15, res, st, lg, trk, f1, R, L6 = world
    t = len(m15) - 1
    cap = RC.caption(1, 2, m15["bar_end"].iloc[t], L6[t])
    assert len(cap.splitlines()) <= 8 and len(cap.encode("utf-16-le")) // 2 <= 1024 and "_" not in cap
    assert RC.rows(R, L6, t - 300, t)


def test_script_rerun_identical(tmp_path):
    import importlib.util

    from tests.test_pivots_dc import SLOTS, _monday
    spec = importlib.util.spec_from_file_location("rc", os.path.join(ROOT, "scripts", "rsi_check.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(10)
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
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "rsi/t", "--days", "1",
                       "--futures-dir", str(tmp_path / "nofut")]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert outs[0] == outs[1] and outs[0]


def test_register_numbers_dates_shadow():
    reg = " ".join(RS.REGISTER)
    for k in RS.DEFAULTS:
        assert k in reg, k
    allowed = {0, 1, -1, 2, 3, 100, 1e-9, 100.0}
    for f in ("engine.py", "layer.py"):
        tree = ast.parse(open(os.path.join(ROOT, "rsi2", f), encoding="utf-8").read())
        nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)}
        assert nums <= allowed, (f, nums - allowed)
    paths = [os.path.join(ROOT, "rsi2", f) for f in os.listdir(os.path.join(ROOT, "rsi2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "rsi_check.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    src = open(os.path.join(ROOT, "rsi2", "engine.py"), encoding="utf-8").read()
    assert "def divergence" not in src and "EV.divergence" not in src                  # सध्याचं evidence.divergence() तसंच (shadow)


def test_line_skip_two_accepted_with_strict_flag():
    """Abhi उत्तर 12: L2 शेजारची RSI 2 bars पर्यंत रेघ ओलांडते ⇒ line_clear ✓, line_clear_strict ✗."""
    R = _R([100.0] * 40)
    R.r15 = np.full(40, 50.0)
    R.r15[5], R.r15[30] = 30.0, 40.0
    a, b = P("L", 100.0, 5), P("L", 95.0, 30)
    R.r15[29] = 30.0                                                               # L2 च्या आधीची candle रेघेखाली
    assert R._clear(a, b, "L")[0] is True
    assert R._clear(a, b, "L", skip=0)[0] is False
    x = R.pair(a, b, 0, "L")
    assert x["line_clear"] and not x["line_clear_strict"]
    assert RS.DEFAULTS["line_skip"] == 2


def test_cascade_is_degree_wise():
    """Abhi निर्णय: cascade = एकाच degree tag च्या regular divergences; degrees मिसळत नाहीत."""
    piv = {0: [P("L", 90.0, 25, 26), P("L", 80.0, 45, 46)], 1: [P("L", 80.0, 45, 46)]}
    divs = [{"type": RE.REG_BULL, "degree": 0, "L2": {"bar": 20, "price": 95.0}, "known_bar": 22},
            {"type": RE.REG_BULL, "degree": 1, "L2": {"bar": 40, "price": 85.0}, "known_bar": 42}]
    R = SimpleNamespace(res={"pivots": piv}, known=lambda t: [x for x in divs if x["known_bar"] <= t])
    assert RE.cascade(R, 60) == []                                                 # D0 + D1 मिसळले असते तर 2
    divs.append({"type": RE.REG_BULL, "degree": 0, "L2": {"bar": 40, "price": 85.0}, "known_bar": 42})
    out = RE.cascade(R, 60)
    assert out == [{"type": RE.REG_BULL, "degree": 0, "n": 2, "known_bar": 46}]
