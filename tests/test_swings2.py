"""थर 1 v2.1 (swings2) — synthetic data फक्त, कुठलीही तारीख नाही (थर 1 §6)."""
import ast
import json
import os
import re

import numpy as np
import pandas as pd
import pytest

from elliott import data_policy as DP
from pivots import charts as PC
from pivots import engine as PE
from pivots.dc import BAR
from swings2 import charts as WC
from swings2 import engine as SE
from swings2 import settings as SS
from swings2 import structure as ST
from tests.test_legs2 import DATE_RX_I
from tests.test_pivots_dc import SLOTS, _monday, m15_from, walk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def built(seed, n_sess=40, step=5.0):
    m15 = m15_from(walk(25 * n_sess, seed, step))
    return m15, SE.build(m15)


# ---------------------------------------------------------------------------------------------------------------- engine
@pytest.mark.parametrize("seed", [1, 2, 7, 13])
def test_nesting_and_known_at_monotone(seed):
    m15, res = built(seed)
    for d in range(1, 5):
        low = {(p.bar, p.kind, p.price): p for p in res["pivots"][d - 1]}
        for p in res["pivots"][d]:
            q = low.get((p.bar, p.kind, p.price))
            assert q is not None                                                   # D(n+1) ⊆ D(n)
            assert p.known_at >= q.known_at and p.confirm_bar >= q.confirm_bar
        kinds = [p.kind for p in res["pivots"][d]]
        assert all(a != b for a, b in zip(kinds, kinds[1:]))                       # H / L आलटून-पालटून


def test_confirmed_pivots_frozen_and_no_two_from_one_candle():
    m15, res = built(3)
    for d in range(5):
        cb = [p.confirm_bar for p in res["pivots"][d]]
        assert len(cb) == len(set(cb))
        with pytest.raises(Exception):
            res["pivots"][d][0].price = 1.0


@pytest.mark.parametrize("seed", [4, 9])
def test_truncation_pivots_and_structure(seed):
    m15, res = built(seed, 45)
    out, _ = ST.all_structure(res)
    for cut in (25 * 38 + 6, 25 * 42 + 17):
        r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
        o2, _ = ST.all_structure(r2)
        t = pd.Timestamp(m15["bar_end"].iloc[cut])
        for d in range(5):
            assert [SE.pivot_json(p) for p in SE.known(res, d, t)] == [SE.pivot_json(p) for p in SE.known(r2, d, t)]
        for d in (1, 2):
            assert json.dumps(out[d]["states"][:cut + 1], default=str) == json.dumps(o2[d]["states"], default=str)
            assert [e for e in out[d]["events"] if e["bar"] <= cut] == o2[d]["events"]


class _P:
    def __init__(self, kind, price, bar, cb, known):
        self.kind, self.price, self.bar, self.confirm_bar, self.known_at, self.rule = kind, price, bar, cb, known, "normal"
        self.ts = pd.Timestamp(0)


def _A(h, l):
    return {"h": np.array(h, float), "l": np.array(l, float), "split": np.zeros(len(h), dtype=bool)}


def _known(j):
    return pd.Timestamp(0) + pd.Timedelta(minutes=15 * (j + 1))


def test_upper_raw_crossing_known_at_and_candidate_guard():
    u = SE.Upper(1)
    u.mode = SE.UP
    A = _A([100, 110, 108, 106, 104], [99, 105, 103, 101, 98])
    th = np.full(5, 10.0)
    sg = np.ones(5)
    u.add(_P("H", 110, 1, 3, _known(3)))
    out = u.step(3, A, th, sg, _known)
    assert out == []                                                               # 110 − 101 < 10
    out = u.step(4, A, th, sg, _known)
    assert len(out) == 1 and out[0].confirm_bar == 4 and out[0].known_at == _known(4)
    u2 = SE.Upper(1)
    u2.mode = SE.UP
    A2 = _A([100, 110, 112, 106, 104], [99, 105, 103, 101, 98])
    u2.add(_P("H", 110, 1, 2, _known(2)))
    assert u2.step(4, A2, th, sg, _known) == []               # मध्ये 112 ⇒ 110 आता टोक नाही


def test_upper_theta_change_alone_does_not_confirm():
    u = SE.Upper(1)
    u.mode = SE.UP
    A = _A([100, 110, 105, 105, 105], [99, 105, 101, 101, 101])
    th = np.array([10, 10, 10, 10, 5.0])                                            # θ फक्त लहान झाला, नवा low नाही
    u.add(_P("H", 110, 1, 2, _known(2)))
    assert u.step(4, A, th, np.ones(5), _known) == []


def _with_1m(m15, drop=()):
    rows = []
    for i, r in m15.iterrows():
        if i in drop:
            continue
        t0 = pd.Timestamp(r["timestamp"])
        for k in range(15):
            hi = r["high"] if k == 3 else min(r["high"], max(r["open"], r["close"]))
            lo = r["low"] if k == 9 else max(r["low"], min(r["open"], r["close"]))
            rows.append((t0 + pd.Timedelta(minutes=k), r["open"], hi, lo, r["close"]))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def test_m1_status_stream_replay_equals_live():
    m15 = m15_from(walk(25 * 30, 5, 6.0))
    drop = set(range(25 * 25, 25 * 27))
    live = SE.build(m15, _with_1m(m15, drop))
    st = {x["ts"]: x["m1_status"] for x in live["stream"]}
    assert sum(v == "absent" for v in st.values()) == len(drop)
    replay = SE.build(m15, _with_1m(m15), m1_status_map=st)                         # नंतर 1m backfill झाला तरी
    for d in range(5):
        assert [SE.pivot_json(p) for p in live["pivots"][d]] == [SE.pivot_json(p) for p in replay["pivots"][d]]


def test_holdout_and_display_only_never_in_engine():
    m15 = m15_from(walk(25 * 3, 2), start=DP.HOLDOUT_START + pd.Timedelta(days=10))
    with pytest.raises(DP.HoldoutError):
        SE.build(m15)
    ok = m15_from(walk(25 * 3, 2))
    with pytest.raises(DP.HoldoutError):
        SE.build(PC.display_only(ok))


def test_eq_flag_consecutive_same_type_within_tolerance():
    m15, res = built(6, 45)
    for d in range(3):
        last = {}
        for p in res["pivots"][d]:
            q = last.get(p.kind)
            want = q is not None and abs(p.price - q.price) <= SS.DEFAULTS["eq_tol_sigma"] * p.sigma
            assert p.eq == want
            last[p.kind] = p


def test_warmup_flags_deterministic():
    m15, r1 = built(8)
    r2 = SE.build(m15)
    for d in range(5):
        assert [p.warmup for p in r1["pivots"][d]] == [p.warmup for p in r2["pivots"][d]]
        if r1["pivots"][d]:
            assert r1["pivots"][d][0].warmup


# ---------------------------------------------------------------------------------------------------------------- structure
def _p(kind, price, i, eq=False):
    return SE.Pivot(1, kind, float(price), i, pd.Timestamp(0), i + 1, pd.Timestamp(0), 1.0, 4.0, "normal", eq=eq)


@pytest.mark.parametrize("seq,want", [
    ([("L", 1), ("H", 5)], "unknown"),
    ([("L", 1), ("H", 5), ("L", 2), ("H", 6)], "UP"),
    ([("H", 6), ("L", 2), ("H", 5), ("L", 1)], "DOWN"),
    ([("L", 1), ("H", 5), ("L", 2), ("H", 4)], "RANGE"),
])
def test_trend_state(seq, want):
    assert ST.trend_of([_p(k, v, i) for i, (k, v) in enumerate(seq)]) == want


def test_equal_high_gives_range():
    ps = [_p("L", 1, 0), _p("H", 5, 1), _p("L", 2, 2), _p("H", 5.05, 3, eq=True)]
    assert ST.trend_of(ps) == "RANGE"


def test_rhea_touch_tolerance_and_min_bars():
    s = SS.load()
    H = np.array([10, 12, 11.9, 11, 11.8, 10.5, 11, 11.95, 10.9, 11.0])
    L = np.array([9, 9.1, 9.0, 9.5, 9.2, 9.6, 9.05, 9.4, 9.3, 9.2])
    sig = np.ones(10)
    r = ST.rhea(H, L, sig, 9, 1, s)
    assert r is not None and r[2] >= 8
    L2 = np.array([9, 9.1, 9.6, 9.6, 9.6, 9.6, 9.6, 9.6, 9.6, 9.6])               # खालच्या कडेला फक्त एक स्पर्श
    assert ST.rhea(H, L2, sig, 9, 1, s) is None
    assert ST.rhea(H[:7], L[:7], sig[:7], 6, 1, s) is None                          # 8 पेक्षा कमी bars


def scenario():
    """UP trend: L100 H120 L110 H130 L118, मग BOS (close > 130), मग CHoCH (close < 118 ⇒ strict = 118?), LH, reversal."""
    anchors = [(0, 105), (4, 100), (10, 120), (16, 110), (22, 130), (28, 118), (33, 136), (40, 112), (46, 126), (52, 104), (56, 106)]
    xs, ys = zip(*anchors)
    n = 57
    c = np.interp(np.arange(n), xs, ys)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.1
    lo = np.minimum(o, c) - 0.1
    days = pd.bdate_range(_monday(300), periods=3)
    ts = [days[i // 25] + SLOTS[i % 25] for i in range(n)]
    m15 = pd.DataFrame({"timestamp": ts, "bar_end": [t + BAR for t in ts], "open": o, "high": h, "low": lo, "close": c})
    piv = []
    for b, kind in ((4, "L"), (10, "H"), (16, "L"), (22, "H"), (28, "L"), (33, "H"), (40, "L"), (46, "H")):
        price = h[b] if kind == "H" else lo[b]
        piv.append(SE.Pivot(1, kind, float(price), b, pd.Timestamp(ts[b]), b + 2, pd.Timestamp(ts[b + 2]) + BAR, 1.0, 4.0, "normal"))
    day = pd.to_datetime(m15["timestamp"]).dt.normalize()
    res = {"m15": m15, "A": {"o": o, "h": h, "l": lo, "c": c}, "pivots": {1: piv}, "settings": SS.load(),
           "segments": {pd.Timestamp(d): 0 for d in day.unique()}, "sigma": {pd.Timestamp(d): 1.0 for d in day.unique()},
           "first": np.r_[True, day.to_numpy()[1:] != day.to_numpy()[:-1]], "sessions": [pd.Timestamp(d) for d in day.unique()],
           "sigma_1h": {}}
    return res


def test_bos_choch_sweep_reversal_three_steps():
    res = scenario()
    out = ST.fold(res, 1, rr=np.full(len(res["m15"]), np.nan))
    ev = [(e["type"], e["bar"], e["level"], e["dir"]) for e in out["events"]]
    types = [e[0] for e in ev]
    assert "BOS" in types and "CHoCH" in types
    bos = next(e for e in out["events"] if e["type"] == "BOS")
    assert bos["dir"] == 1 and res["m15"]["close"].iloc[bos["bar"]] > bos["level"]
    ch = next(e for e in out["events"] if e["type"] == "CHoCH")
    st = out["states"][ch["bar"] - 1]
    assert ch["level"] == pytest.approx(st["strict"]) and ch["dir"] == -1          # strict_HL चा plain-close break
    rv = [e for e in out["events"] if e["type"] == "reversal"]
    lh = [e for e in out["events"] if e["type"] == "LH"]
    if rv:
        assert lh and lh[0]["bar"] <= rv[0]["bar"] and rv[0]["bar"] > ch["bar"]      # पायरी 3 फक्त LH नंतर
        assert any(e["type"] == "always_in_flip" and e["bar"] == rv[0]["bar"] for e in out["events"])


def test_no_bos_choch_inside_range_and_strict_is_hl_before_last_h():
    m15, res = built(11, 45)
    out, _ = ST.all_structure(res)
    for d in (1, 2):
        sts = out[d]["states"]
        for e in out[d]["events"]:
            if e["type"] in ("BOS", "CHoCH"):
                assert sts[e["bar"] - 1]["trend"] in ("UP", "DOWN") or sts[e["bar"]]["trend"] in ("UP", "DOWN")
        piv = res["pivots"][d]
        for t, s in enumerate(sts):
            if s["trend"] == "UP" and s["strict_bar"] is not None:
                ps = [p for p in piv if p.confirm_bar <= t and not p.warmup]
                lastH = [p for p in ps if p.kind == "H"][-1]
                assert s["strict_bar"] == [p for p in ps if p.kind == "L" and p.bar < lastH.bar][-1].bar


def test_always_in_three_opposite_trend_candles():
    res = scenario()
    A = res["A"]
    for i in (34, 35, 36):                                                          # UP मध्ये तीन मोठ्या खाली trend candles
        A["o"][i], A["c"][i] = A["c"][i - 1], A["c"][i - 1] - 2.0
        A["h"][i], A["l"][i] = A["o"][i] + 0.1, A["c"][i] - 0.1
    out = ST.fold(res, 1, rr=np.full(len(res["m15"]), np.nan))
    assert any(e["type"] == "always_in_flip" and "trend candles" in e.get("why", "") for e in out["events"])


def test_gap_bar_flag_and_gap_leg():
    m15 = m15_from(walk(25 * 30, 3, 3.0), gaps={26: 80.0, 28: -90.0})
    res = SE.build(m15)
    assert 26 * 25 in res["gap_bar_2s"] and 28 * 25 in res["gap_bar_2s"]
    for d in range(3):                                                              # gap_leg_theta: leg च्या दिशेनेच gap ≥ θ
        ps = res["pivots"][d]
        for a, b in zip(ps, ps[1:]):
            dirn = 1 if b.price > a.price else -1
            js = [j for j in range(a.bar + 1, b.bar + 1) if res["first"][j]]
            want = any(res["gap"][j] * dirn >= res["theta"][d][j] for j in js if np.isfinite(res["theta"][d][j]))
            assert b.gap_leg_theta == want
    assert any(p.gap_leg_theta for p in res["pivots"][0])


def test_incomplete_1h_never_drawn():
    m15 = m15_from(walk(25 * 2, 1))
    m = m15.iloc[:25 + 6]                                                           # दुसऱ्या दिवशी 10:45 पर्यंत
    h1 = WC.complete_1h(m, pd.Timestamp(m["bar_end"].iloc[-1]))
    t = pd.to_datetime(h1["timestamp"])
    last_day = t.dt.normalize().max()
    assert (t[t.dt.normalize() == last_day].dt.strftime("%H:%M") == "09:15").all()


# ---------------------------------------------------------------------------------------------------------------- register / नियम
def test_register_complete_and_no_unregistered_numbers():
    for k in SS.DEFAULTS:
        assert k in SS.REGISTER, k
    allowed = {0, 1, -1, 2, 4, 15, 30, 1e-9, 0.5}       # 4 = D4; 15 / 30 = वेळ (मिनिटं)
    for f in ("engine.py", "structure.py", "candles.py"):
        tree = ast.parse(open(os.path.join(ROOT, "swings2", f), encoding="utf-8").read())
        nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)}
        extra = {v for v in nums if v not in allowed and not (isinstance(v, int) and v in (9, 12, 14, 3))}
        assert not extra, (f, extra)


def test_caption_limits_no_code_keys_and_no_order_imports():
    m15, res = built(5, 30)
    out, _ = ST.all_structure(res)
    t = len(m15) - 1
    asof = pd.Timestamp(m15["bar_end"].iloc[t])
    sn = WC.snap(res, out, asof, t)
    cap = WC.caption(3, 40, sn, out, t, asof, "BOS")
    assert len(cap.encode("utf-16-le")) // 2 <= 1024 and len(cap.splitlines()) <= 8
    assert cap.startswith("🧭 SWING CHECK 3/40") and "Reply" in cap
    for key in ("_", "{", "}", "None"):
        assert key not in cap
    paths = [os.path.join(ROOT, "swings2", f) for f in os.listdir(os.path.join(ROOT, "swings2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "swing_check2.py")]
    for p in paths:
        assert not re.search(r"^\s*(?:from|import)\s+(?:broker|order|upstox_api|kite|shoonya|stocko)", open(p, encoding="utf-8").read(), re.M)


def test_no_date_literals_in_new_code():
    paths = [os.path.join(ROOT, "swings2", f) for f in os.listdir(os.path.join(ROOT, "swings2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "swing_check2.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits


def test_shadow_old_modules_unchanged():
    from tests.test_pivots_dc import shadow_fingerprint
    fx = json.load(open(os.path.join(HERE, "fixtures", "pivots_shadow_baseline.json"), encoding="utf-8"))
    assert shadow_fingerprint() == fx


def test_script_writes_only_out_dir_and_rerun_is_byte_identical(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("sw2", os.path.join(ROOT, "scripts", "swing_check2.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(4)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=25):
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
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "swings2/t", "--days", "1"]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert set(os.listdir(tmp_path)) - before == {"a", "b"}
    assert outs[0] == outs[1] and outs[0]


# ---------------------------------------------------------------------------------------------------------------- review नंतरचे tests
def test_upper_skips_split_candles():
    u = SE.Upper(1)
    u.mode = SE.UP
    A = _A([100, 110, 108, 106], [99, 105, 95, 104])
    A["split"][2] = True                                                            # D0 ने या candle चा भाग वापरला नाही
    u.add(_P("H", 110, 1, 2, _known(2)))
    assert u.step(3, A, np.full(4, 10.0), np.ones(4), _known) == []


@pytest.mark.parametrize("seed", [21, 22, 23])
def test_upper_pivot_is_extreme_of_lower_pivots_in_its_leg(seed):
    m15, res = built(seed, 40, 6.0)
    for d in range(1, 4):
        ps, low = res["pivots"][d], res["pivots"][d - 1]
        for a, b in zip(ps, ps[1:]):
            inside = [q for q in low if a.bar < q.bar <= b.bar and q.kind == b.kind]
            if b.kind == "H":
                assert all(q.price <= b.price for q in inside)
            else:
                assert all(q.price >= b.price for q in inside)


@pytest.mark.parametrize("seed", [4, 9])
def test_d2_rhea_never_uses_forming_1h_candle(seed):
    m15, res = built(seed, 45)
    out, _ = ST.all_structure(res)
    for cut in range(25 * 40 + 1, 25 * 40 + 9):                                    # तासाच्या मध्ये कापलं
        r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
        o2, _ = ST.all_structure(r2)
        assert json.dumps(out[2]["states"][:cut + 1], default=str) == json.dumps(o2[2]["states"], default=str)


def test_sweep_checked_on_both_sides_in_down_trend():
    res = scenario()
    A = res["A"]
    n = len(res["m15"])
    out = ST.fold(res, 1, rr=np.full(n, np.nan))
    downs = [t for t, st in enumerate(out["states"]) if st["trend"] == "DOWN" and st["lastL"] is not None]
    if downs:
        t = downs[-1]
        lv = out["states"][t]["lastL"]
        A["l"][t] = lv - 1.0
        A["c"][t] = max(A["c"][t], lv + 0.05)
        A["h"][t] = max(A["h"][t], A["c"][t])
        out2 = ST.fold(res, 1, rr=np.full(n, np.nan))
        assert any(e["type"] == "sweep" and e["dir"] == -1 and e["bar"] == t for e in out2["events"])


def test_always_in_fires_once_per_streak():
    res = scenario()
    A = res["A"]
    for i in (34, 35, 36, 37, 38):
        A["o"][i], A["c"][i] = A["c"][i - 1], A["c"][i - 1] - 2.0
        A["h"][i], A["l"][i] = A["o"][i] + 0.1, A["c"][i] - 0.1
    out = ST.fold(res, 1, rr=np.full(len(res["m15"]), np.nan))
    ai = [e for e in out["events"] if e["type"] == "always_in_flip" and "trend candles" in e.get("why", "") and 34 <= e["bar"] <= 38]
    assert len(ai) == 1


def test_weekly_drops_unfinished_week():
    m15 = m15_from(walk(25 * 8, 1))
    asof_mid = pd.Timestamp(m15["bar_end"].iloc[25 * 7 - 1])                         # दुसऱ्या आठवड्याचा मधला दिवस
    daily = PC.daily_from_15m(m15[pd.to_datetime(m15["bar_end"]) <= asof_mid], asof_mid)
    w = WC.complete_weekly(daily, asof_mid)
    assert len(w) == len(PC.weekly_from_daily(daily, asof_mid)) - 1


# ---------------------------------------------------------------------------------------------------------------- audit (v2.1) थर 1
def _with_1m_swapped(m15):
    """तेच OHLC, पण 1m मध्ये low आधी (मिनिट 3) आणि high नंतर (मिनिट 9) — नंतरचा 'backfill दुरुस्ती' क्रम बदलतो."""
    df = _with_1m(m15)
    out = []
    for i, r in m15.iterrows():
        t0 = pd.Timestamp(r["timestamp"])
        for k in range(15):
            hi = r["high"] if k == 9 else min(r["high"], max(r["open"], r["close"]))
            lo = r["low"] if k == 3 else max(r["low"], min(r["open"], r["close"]))
            out.append((t0 + pd.Timedelta(minutes=k), r["open"], hi, lo, r["close"]))
    assert len(out) == len(df)
    return pd.DataFrame(out, columns=["timestamp", "open", "high", "low", "close"])


def test_audit6_stream_stores_1m_decision_and_replay_ignores_backfill():
    """Audit #6: stream मध्ये 1m चा निर्णय (order); replay त्यावरच — 1m backfill ने क्रम बदलला तरी pivots तेच."""
    m15 = m15_from(walk(25 * 30, 5, 6.0))
    live = SE.build(m15, _with_1m(m15))
    used = [x for x in live["stream"] if x["order"]]
    assert used                                                                    # same-bar candles ला 1m निर्णय वापरला
    smap = {x["ts"]: json.loads(json.dumps(x)) for x in live["stream"]}             # stream.json सारखं (tuple ⇒ list)
    replay = SE.build(m15, _with_1m_swapped(m15), m1_status_map=smap)
    for d in range(5):
        assert [SE.pivot_json(p) for p in live["pivots"][d]] == [SE.pivot_json(p) for p in replay["pivots"][d]]
    fresh = SE.build(m15, _with_1m_swapped(m15))                                   # rows पुन्हा वाचले असते तर वेगळं
    assert any(a["order"] != b["order"] for a, b in zip(live["stream"], fresh["stream"]) if a["order"])


def test_audit9_first_rev_same_bar_marks_split():
    """Audit #9: 1m ने first_rev ⇒ आधीचं टोक confirm (p.bar ≠ b) ⇒ त्या candle चं नवं टोक D0 ला दिसलं नाही ⇒ split."""
    m15 = m15_from(walk(25 * 30, 5, 6.0))
    res = SE.build(m15, _with_1m_swapped(m15))
    hits = [p for p in res["pivots"][0] if p.rule == "1m" and p.bar != p.confirm_bar]
    assert hits
    assert all(res["A"]["split"][p.confirm_bar] for p in hits)


def test_audit1_reversal_step2_uses_confirmed_lh():
    """Audit #1: CHoCH आधीच्या bar चा, पण CHoCH नंतर confirm झालेला LH ⇒ पायरी 2 (आधी `p.bar > choch_bar` ने सुटायचा)."""
    res = scenario()
    rr = np.full(len(res["m15"]), np.nan)
    out = ST.fold(res, 1, rr=rr)
    ch = next(e for e in out["events"] if e["type"] == "CHoCH")["bar"]
    h1 = out["states"][ch]["lastH"] if out["states"][ch]["lastH"] is not None else 136.0
    b = ch - 1
    price = float(res["A"]["h"][b])
    assert price < h1
    extra = SE.Pivot(1, "H", price, b, pd.Timestamp(res["m15"]["timestamp"].iloc[b]), ch + 2,
                     pd.Timestamp(res["m15"]["timestamp"].iloc[ch + 2]) + BAR, 1.0, 4.0, "normal")
    res["pivots"][1] = sorted(res["pivots"][1] + [extra], key=lambda p: p.bar)
    out2 = ST.fold(res, 1, rr=rr)
    lh = [e for e in out2["events"] if e["type"] == "LH" and e["bar"] >= ch]
    assert lh and lh[0]["bar"] == ch + 2 and lh[0]["level"] == pytest.approx(price, abs=0.01)


def test_audit2_3_strong_is_confirmed_pivot_and_weak_high():
    P = _p
    ls = [P("L", 100, 4), P("L", 118, 28)]
    hs = [P("H", 120, 10), P("H", 130, 22)]
    assert ST.strong_price((1, 22, 31), "UP", hs, ls) == 118                       # ext 22 नंतरचा confirmed L
    assert ST.strong_price((1, 22, 31), "UP", hs, ls[:1]) is None                  # अजून confirm नाही ⇒ caller strict
    assert ST.strong_price((1, 22, 31), "DOWN", hs, ls) is None
    assert ST.weak_level("UP", hs, ls) is None                                     # शेवटचा H = HH ⇒ weak नाही
    assert ST.weak_level("UP", hs + [P("H", 128, 40)], ls) == 128                  # आधीचा high न ओलांडलेला
    assert ST.weak_level("DOWN", hs, [P("L", 90, 5), P("L", 95, 9)]) == 95


def test_audit2_protected_waits_for_confirmed_low_in_fold():
    res = scenario()
    out = ST.fold(res, 1, rr=np.full(len(res["m15"]), np.nan))
    bos = [e for e in out["events"] if e["type"] == "BOS" and e["dir"] == 1]
    assert bos
    for e in bos:
        st = out["states"][e["bar"]]
        conf = [p.price for p in res["pivots"][1] if p.kind == "L" and p.confirm_bar <= e["bar"] and p.bar < e["bar"]]
        assert st["protected"] in conf or st["protected"] == st["strict"]          # raw (tentative) low नाही


def test_audit4_d2_rhea_on_15m_scaled_by_k():
    s = SS.load()
    s2 = ST.rhea_settings(s, 2)
    r = s["k"][2] / s["k"][1]
    assert s2["rhea_band_sigma"] == pytest.approx(3.0 * r) and s2["rhea_min_bars"] == round(8 * r)
    assert ST.rhea_settings(s, 1) is s
    H = np.array([10, 12, 11.9, 11, 11.8, 10.5, 11, 11.95, 10.9, 11.0])
    L = np.array([9, 9.1, 9.0, 9.5, 9.2, 9.6, 9.05, 9.4, 9.3, 9.2])
    sig = np.ones(10)
    assert ST.rhea(H, L, sig, 9, 1, s) is not None and ST.rhea(H, L, sig, 9, 1, s2) is None   # D2 ला 12 bars हवे
    m15, res = built(11, 45)
    out, _ = ST.all_structure(res)
    starts = [e for e in out[2]["events"] if e["type"] == "range_start"]
    assert all(e["bar"] >= 0 for e in starts)                                      # 15M वर (1H close ची वाट नाही) — crash नाही


def test_audit7_8_k_options_and_three_day_compare(tmp_path, monkeypatch):
    assert SS.K_OPTIONS[2] == (4.0, 6.0, 8.0) and SS.DEFAULTS["k"][2] == 6.0
    import importlib.util
    spec = importlib.util.spec_from_file_location("sw2k", os.path.join(ROOT, "scripts", "swing_check2.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="PNG")
    png = buf.getvalue()
    calls = []
    monkeypatch.setattr(M.WC, "k_options_png", lambda m15, m1, asof, deg, ks: calls.append((asof.normalize(), deg)) or png)
    monkeypatch.setattr(M.PC, "pdf", lambda pages, path: None)
    monkeypatch.setattr(M.WC, "charts", lambda *a, **k: ({"15M": png, "1H": png, "D": png, "W": png}, {}))
    monkeypatch.setattr(M.WC, "caption", lambda *a, **k: "x")
    monkeypatch.setattr(M.LC, "table_png", lambda *a, **k: png)
    rng = np.random.default_rng(4)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=25):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    assert M.main(["--data", str(data), "--out-dir", str(tmp_path / "o"), "--run-id", "swings2/k", "--days", "5"]) == 0
    assert len({d for d, _ in calls}) == 3 and len(calls) == 6                    # 3 दिवस × D1, D2


def _flat_res(c, h=None, lo=None, piv=()):
    n = len(c)
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.1 if h is None else np.asarray(h, float)
    lo = np.minimum(o, c) - 0.1 if lo is None else np.asarray(lo, float)
    days = pd.bdate_range(_monday(300), periods=n // 25 + 1)
    ts = [days[i // 25] + SLOTS[i % 25] for i in range(n)]
    m15 = pd.DataFrame({"timestamp": ts, "bar_end": [t + BAR for t in ts], "open": o, "high": h, "low": lo, "close": c})
    day = pd.to_datetime(m15["timestamp"]).dt.normalize()
    return {"m15": m15, "A": {"o": o, "h": h, "l": lo, "c": c}, "pivots": {1: list(piv), 2: []}, "settings": SS.load(),
            "segments": {pd.Timestamp(d): 0 for d in day.unique()}, "sigma": {pd.Timestamp(d): 1.0 for d in day.unique()},
            "first": np.r_[True, day.to_numpy()[1:] != day.to_numpy()[:-1]], "sessions": [pd.Timestamp(d) for d in day.unique()],
            "sigma_1h": {}}


def test_audit10_rhea_end_to_end_start_known_at_break_and_always_in_clause3():
    c = [100, 102, 100, 102, 100.5, 101.8, 100.2, 101.9, 100.1, 101.5, 101, 101.2, 103.5, 104.5, 105]   # 2σ पट्टा, मग वर break
    res = _flat_res(c)
    out = ST.fold(res, 1, rr=np.full(len(c), np.nan))
    ev = out["events"]
    rs = next(e for e in ev if e["type"] == "range_start")
    assert pd.Timestamp(rs["known_at"]) == pd.Timestamp(res["m15"]["timestamp"].iloc[rs["bar"]]) + BAR
    assert out["states"][rs["bar"]]["range"] is not None and out["states"][rs["bar"]]["trend"] == "RANGE"
    rb = next(e for e in ev if e["type"] == "range_break")
    assert rb["dir"] == 1 and rb["bar"] > rs["bar"]
    assert any(e["type"] == "always_in_flip" and e["bar"] == rb["bar"] + 1 and "range_break" in e["why"] for e in ev)   # clause 3
    out2 = ST.fold(res, 2, rr=np.full(len(c), np.nan))
    rs2 = [e for e in out2["events"] if e["type"] == "range_start"]
    assert all(e["bar"] > rs["bar"] for e in rs2)                                       # D2: ≥ 12 bars ⇒ D1 पेक्षा उशिरा


def test_audit10_pivot_range_break_and_reversal_negative_cases():
    c = np.r_[np.linspace(100, 110, 10), np.linspace(110, 95, 10), np.linspace(95, 115, 10), np.linspace(115, 90, 10), [92, 118, 119]]
    res = _flat_res(c)
    tsr = res["m15"]["timestamp"]
    P = lambda k, pr, b: SE.Pivot(1, k, pr, b, pd.Timestamp(tsr.iloc[b]), b + 1, pd.Timestamp(tsr.iloc[b + 1]), 1.0, 4.0, "normal")  # noqa: E731
    res["pivots"][1] = [P("H", 110.1, 9), P("L", 94.9, 19), P("H", 115.1, 29), P("L", 89.9, 39)]   # HH + LL ⇒ pivot-RANGE
    res["settings"]["rhea_min_bars"] = 99                                              # Rhea बंद ⇒ फक्त pivot पट्टा
    out = ST.fold(res, 1, rr=np.full(len(c), np.nan))
    assert out["states"][41]["trend"] == "RANGE"
    rb = [e for e in out["events"] if e["type"] == "range_break" and e.get("source") == "pivots"]
    assert rb and rb[0]["bar"] == 41 and rb[0]["level"] == pytest.approx(115.1)        # वरचा = दोन H पैकी मोठा
    res = scenario()
    out = ST.fold(res, 1, rr=np.full(len(res["m15"]), np.nan))
    ev = out["events"]
    ch = next(e for e in ev if e["type"] == "CHoCH")
    lh = [e for e in ev if e["type"] == "LH"]
    rv = [e for e in ev if e["type"] == "reversal"]
    assert not [e for e in rv if not lh or e["bar"] < lh[0]["bar"]]                     # LH आधी पायरी 3 नाही
    A = res["A"]
    t = ch["bar"] + 1
    A["c"][t] = A["h"][t] = 140.0                                                       # नवा HH (H1 136 पलीकडे close) ⇒ रद्द
    out2 = ST.fold(res, 1, rr=np.full(len(res["m15"]), np.nan))
    assert any(e["type"] == "reversal_cancel" and e["bar"] == t for e in out2["events"])


def test_audit10_m1_partial_status_and_sigma_1h_excludes_short_candles():
    rows = pd.DataFrame({"high": [10.0] * 10, "low": [9.0] * 10})
    assert SE.m1_status(rows, 10.0, 9.0) == "partial"                                  # < 15 rows
    assert SE.m1_status(None, 10.0, 9.0) == "absent"
    m15, res = built(3, 30)
    days = res["sessions"]
    d = days[-1]
    from pivots import charts as PC2
    h1 = PC2.agg_1h(m15)
    t = pd.to_datetime(h1["timestamp"])
    prev = [x for x in days[:-1]][-20:]
    m = t.dt.normalize().isin(prev) & ~t.dt.strftime("%H:%M").isin(["09:15", "15:15"])
    want = float(np.median((h1["high"] - h1["low"])[m]))
    assert res["sigma_1h"][d] == pytest.approx(want)
