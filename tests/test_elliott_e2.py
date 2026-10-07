"""tests/test_elliott_e2.py — Elliott E2: composite logical reversal (§6 T1–T4, §14 Q2), failed-retest real break (§14 Q1 c),
setup mapping / tiers / zones / hard inv (§4, §5, §7, §14 Q6), blocks (A-end, B/X/triangle आत, gray, alt block, wick recount),
signal invariants (breakout ban §12 test 8, fill/time/session), truncation invariance (§12 test 1–2)."""
import os
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from elliott import breaks as B
from elliott import reversal as RV
from elliott import settings as S
from elliott import setups as SU
from elliott import trigger as TR
from elliott.counts import DegreeView, Snapshot
from elliott.invalidation import level_events

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T0 = pd.Timestamp("2019-01-02 09:15")


def _cfg(**k):
    c, e = S.validate(k)
    assert not e, e
    return c


S0 = _cfg()


def frame(rows, base=30):
    """base bars (o=100 h=105 l=95 c=100, range 10) + rows [(o,h,l,c)]."""
    bars = [(100.0, 105.0, 95.0, 100.0)] * base + [tuple(map(float, r)) for r in rows]
    ts = [T0 + pd.Timedelta(minutes=5 * i) for i in range(len(bars))]
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    df.insert(1, "bar_end", [t + pd.Timedelta(minutes=5) for t in ts])
    return df


def bars_of(df, s=S0):
    return RV.Bars(df, B.median_range(df, s["median_range_n"]))


def mirror(df):
    m = df.copy()
    m["open"], m["high"], m["low"], m["close"] = -df["open"], -df["low"], -df["high"], -df["close"]
    return m


# ---------------------------------------------------------------- reversal (T1–T4)
def test_hammer_passes_and_score_components():
    df = frame([(101, 103, 88, 102)])
    j = len(df) - 1
    r = RV.evaluate(bars_of(df), j, 1, [100.0], 0.0, S0, extreme_idx=j, bars_last_subleg=1)
    assert r["ok"] and r["n"] == 1 and r["touched"] == 100.0
    exp = (0.3 * 13 / 15 + 0.3 * 14 / 15 + 0.2 * 1 / 15 + 0.2 * 1.0) / 1.0
    assert r["score"] == pytest.approx(exp)


def test_mirror_symmetry_bear_equals_bull():
    df = frame([(101, 103, 88, 102)])
    j = len(df) - 1
    a = RV.evaluate(bars_of(df), j, 1, [100.0], 0.0, S0, extreme_idx=j, bars_last_subleg=1)
    b = RV.evaluate(bars_of(mirror(df)), j, -1, [-100.0], 0.0, S0, extreme_idx=j, bars_last_subleg=1)
    assert b["ok"] and b["score"] == pytest.approx(a["score"]) and b["touched"] == -100.0 and b["n"] == a["n"]


@pytest.mark.parametrize("row,reason", [
    ((101, 103, 101, 102), RV.NO_TOUCH),          # low zone पर्यंत आला नाही
    ((101, 103, 88, 99), RV.NO_RECLAIM),           # close level च्या खाली
    ((101, 102, 92, 101.5), RV.WEAK),              # range 10 < 1.2 × MR
    ((101, 130, 88, 128), RV.EXHAUSTION),          # range 42 > 2.5 × MR
])
def test_single_candle_failures(row, reason):
    df = frame([row])
    r = RV.evaluate_window(bars_of(df), len(df) - 1, 1, 1, [100.0], 0.0, S0)
    assert not r["ok"] and r["reason"] == reason


def test_inv_beyond_rejects_and_mid_close_beyond_inv():
    df = frame([(101, 103, 88, 102)])
    r = RV.evaluate_window(bars_of(df), len(df) - 1, 1, 1, [100.0], 0.0, S0, inv=90.0)
    assert r["reason"] == RV.INV                                                    # low 88 ≤ inv 90
    df2 = frame([(100, 101, 91, 92), (92, 103, 91, 102)])
    r2 = RV.evaluate_window(bars_of(df2), len(df2) - 1, 2, 1, [100.0], 0.0, S0, inv=92.5)
    assert r2["reason"] == RV.INV                                                   # पहिल्या candle चा close inv खाली


def test_touched_is_deepest_level_and_reclaim_ref():
    df = frame([(96, 97, 88, 95.5)])
    b = bars_of(df)
    j = len(df) - 1
    r = RV.evaluate_window(b, j, 1, 1, [100.0, 92.0], 0.0, S0)
    assert r["touched"] == 92.0 and r["reason"] != RV.NO_RECLAIM                    # 95.5 > 92 (सर्वात खोल शिवलेला)
    r2 = RV.evaluate_window(b, j, 1, 1, [100.0, 92.0], 0.0, S0, reclaim_ref="zone_high")
    assert r2["reason"] == RV.NO_RECLAIM                                            # zone_high (100) वर close नाही


def test_composite_last_candle_must_close_in_trade_direction():
    df = frame([(100, 101, 88, 99), (99, 104, 98, 103), (103, 104, 101, 102)])       # शेवटची candle लाल
    r = RV.evaluate_window(bars_of(df), len(df) - 1, 3, 1, [100.0], 0.0, S0)
    assert r["reason"] == RV.LAST_AGAINST


def test_indecision_follow_through_allows_n4():
    # N=3 composite (j−1) अनिर्णयी (close-loc 0.58), मग हिरवी follow-through ⇒ फक्त N=4 पास (N=1 touch नाही, N=2/3 कमकुवत)
    rows = [(100, 101, 88, 95), (95, 97, 93, 94), (94, 98, 93, 95.5), (95.5, 104, 95, 103)]
    df = frame(rows)
    b = bars_of(df)
    j = len(df) - 1
    assert RV.evaluate_window(b, j - 1, 3, 1, [94.0], 0.0, S0)["reason"] == RV.INDECISIVE
    r = RV.evaluate(b, j, 1, [94.0], 0.0, S0)
    assert r["ok"] and r["n"] == 4
    df2 = frame(rows[:3] + [(95.5, 104, 95, 95.0)])                                  # follow-through लाल ⇒ N=4 नाही
    assert not RV.evaluate(bars_of(df2), j, 1, [94.0], 0.0, S0)["ok"]


def test_min_start_excludes_older_bars():
    df = frame([(101, 103, 88, 102)])
    j = len(df) - 1
    assert RV.evaluate_window(bars_of(df), j, 1, 1, [100.0], 0.0, S0, min_start=j + 1)["reason"] == RV.NO_DATA


# ---------------------------------------------------------------- failed retest break (§14 Q1 c)
RETEST_ROWS = [(93, 95, 86, 87),       # t: कमकुवत close 90 − buf खाली (range 9 < 12 ⇒ displacement नाही)
               (87, 98, 86, 91),       # t+1: reclaim (close ≥ 90), पण खालून सुरू होऊन 98 पर्यंत
               (91, 93, 85.5, 87)]     # t+2: पुन्हा buffer खाली close (कमकुवत) — composite (t+1,t+2) = खालून L ला लागून नकार


def test_failed_retest_confirms_break_and_off_switch():
    df = frame(RETEST_ROWS + [(100, 105, 95, 100)] * 5)
    t = 30
    s_on, s_off = _cfg(), _cfg(break_retest_confirm=False)
    c_on = B.BreakCache(df, s_on).confirm_index(t, 90.0, "below", len(df) - 1)
    c_off = B.BreakCache(df, s_off).confirm_index(t, 90.0, "below", len(df) - 1)
    assert c_on == t + 2 and c_off is None
    # causal: t+1 पर्यंतच डेटा ⇒ अजून नाही; t+2 ⇒ हो (truncation invariant)
    assert B.BreakCache(df.iloc[:t + 2].reset_index(drop=True), s_on).confirm_index(t, 90.0, "below", t + 1) is None
    assert B.BreakCache(df.iloc[:t + 3].reset_index(drop=True), s_on).confirm_index(t, 90.0, "below", t + 2) == t + 2


def test_false_break_paths_unchanged_with_retest():
    s = _cfg()
    wick = frame([(96, 97, 80, 95)] + [(100, 105, 95, 100)] * 5)                      # (a) wick पलीकडे, close आत
    assert B.first_real_break(wick, 30, 90.0, "below", s) is None
    rec = frame([(93, 95, 86, 87), (87, 98, 86, 97)] + [(100, 105, 95, 100)] * 5)   # (b) close पलीकडे, पुढचा reclaim
    assert B.BreakCache(rec, s).confirm_index(30, 90.0, "below", len(rec) - 1) is None
    acc = frame([(93, 95, 86, 87), (87, 89, 85, 86)] + [(100, 105, 95, 100)] * 3)    # (c) acceptance ⇒ t+1
    assert B.BreakCache(acc, s).confirm_index(30, 90.0, "below", len(acc) - 1) == 31


def test_retest_needs_broken_side_start_and_close_beyond_buffer():
    # reclaim नंतर वरून (L च्या वर open) आलेला आणि buffer आत close ⇒ retest नाही (review: आधी हे break ठरत होतं)
    df = frame([(93, 95, 86, 87), (87, 92, 86, 91), (99, 101, 87.8, 88)] + [(100, 105, 95, 100)] * 4)
    assert B.BreakCache(df, _cfg()).confirm_index(30, 90.0, "below", len(df) - 1) is None


def test_earlier_confirm_beats_later_retest():
    # candidate t reclaim; retest t+3 ला सापडतो, पण t+2 ला स्वतंत्र displacement break ⇒ t+2 ("जे आधी")
    df = frame([(93, 95, 86, 87), (91, 92, 89.5, 91), (91, 92, 76, 77), (82, 91, 78.5, 79)] + [(100, 105, 95, 100)] * 3)
    fn = RV.retest_fn(df, _cfg(), B.median_range(df, 20))
    assert fn(df, 30, 90.0, "below", len(df) - 1) == 33
    assert B.BreakCache(df, _cfg()).confirm_index(30, 90.0, "below", len(df) - 1) == 32


# ---------------------------------------------------------------- setup mapping / tiers / zones / inv
def node(pattern, cw, direction=1, nm=1, prices=(100, 120), invs=None, tent=110.0, parent_key=None, cur_dir=None):
    pts = [NS(price=float(p), bar_idx=i * 10, ts=T0 + pd.Timedelta(minutes=50 * i)) for i, p in enumerate(prices)]
    return NS(pattern=pattern, current_wave=cw, direction=direction, next_motive_dir=nm, points=pts,
              invs=invs if invs is not None else [(float(prices[0]), "below" if nm > 0 else "above", "R")],
              tentative=NS(price=tent, ts=T0 + pd.Timedelta(minutes=50 * len(prices))), parent_key=parent_key,
              current_dir=cur_dir if cur_dir is not None else (-direction if len(prices) % 2 == 0 else direction),
              joint_score=1.0, key=("k", pattern, cw), time_flags={})


def par(pattern, cw, cur_dir=1, invs=None):
    return NS(pattern=pattern, current_wave=cw, current_dir=cur_dir, invs=invs or [(50.0, "below", "PR")], parent_key=None)


@pytest.mark.parametrize("pat,cw,ppat,pcw,code,tier", [
    ("impulse", "2", None, None, "S1", "A"),
    ("impulse", "2", "impulse", "1", "S1", "A"),
    ("impulse", "2", "impulse", "3", "S2", "A"),
    ("impulse", "2", "impulse", "5", "S2", "C"),          # (ii) of 5 ⇒ late stage
    ("impulse", "2", "zigzag", "C", "S13", "B"),
    ("lead_diag", "2", "impulse", "1", "S10", "A"),
    ("impulse", "4", "impulse", "3", "S4", "A"),
    ("impulse", "4", "impulse", "5", "S5", "C"),
    ("impulse", "4", "flat", "C", "S14", "C"),
    ("impulse", "4", "impulse", "1", "S3", "A"),
    ("zigzag", "B", "impulse", "2", "S12", "B"),
    ("zigzag", "B", "impulse", "3", "S6a", "B"),
    ("flat", "B", "impulse", "4", "S6b", "B"),
    ("triangle", "E", "zigzag", "B", "S6c", "B"),
    ("triangle", "E", "impulse", "4", "S9", "A"),
    ("zigzag", "C", "impulse", "2", "S7", "A"),
    ("flat", "C", "zigzag", "B", "S7", "B"),              # parent B मधला C संपला ⇒ parent चा C trade (bounded)
    ("wxy", "Y", "impulse", "4", "S7", "A"),
    ("wxy", "X", "impulse", "2", "S8", "B"),
])
def test_classify_table(pat, cw, ppat, pcw, code, tier):
    n = node(pat, cw)
    p = par(ppat, pcw) if ppat else None
    assert SU.classify(n, p, None) == (code, tier)


def test_tier_against_D2_and_late_for_S7():
    n = node("impulse", "2", nm=1)
    assert SU.classify(n, par("impulse", "3"), par("impulse", "1", cur_dir=-1)) == ("S2", "B")     # D+2 विरुद्ध
    c = node("zigzag", "C", nm=1)
    assert SU.classify(c, par("impulse", "4"), par("impulse", "5", cur_dir=1)) == ("S7", "C")       # 4 of 5
    assert SU.classify(c, par("impulse", "4"), par("impulse", "3", cur_dir=1)) == ("S7", "A")


def test_zone_levels_retrace_and_projection():
    w2 = node("impulse", "2", prices=(100, 200), cur_dir=-1)
    assert SU.zone_levels(w2, "S1", S0) == pytest.approx([200 - r * 100 for r in S0["zone_fibs_w2"]])
    c = node("zigzag", "C", direction=-1, nm=1, prices=(300, 200, 260), cur_dir=-1)                   # A 100 खाली, B 60 वर
    assert SU.zone_levels(c, "S7", S0) == pytest.approx([260 - r * 100 for r in S0["zone_fibs_c"]])


def test_trade_inv_rules():
    zz = node("zigzag", "B", invs=[(100.0, "below", "R6")])
    assert SU.trade_inv(zz, None, "S6a", S0, 10.0) == (100.0, "below", "R6")
    fb = node("flat", "B", tent=95.0)
    lvl, side, rule = SU.trade_inv(fb, None, "S6b", S0, 10.0)
    assert lvl == pytest.approx(95.0 - 0.25 * 10.0) and side == "below" and rule == "B_extreme"
    c = node("zigzag", "C")
    assert SU.trade_inv(c, par("impulse", "2", invs=[(40.0, "below", "R1")]), "S7", S0, 10.0) == (40.0, "below", "R1")
    lvl2, _, rule2 = SU.trade_inv(node("zigzag", "C", tent=97.0), par("flat", "B"), "S7", S0, 10.0)
    assert rule2 == "B_extreme" and lvl2 == pytest.approx(97.0 - 2.5)


# ---------------------------------------------------------------- degree_setup blocks (fake engine)
def fake_eng(s=S0, lows=None, highs=None, n=60):
    lows = np.full(n, 105.0) if lows is None else np.asarray(lows, float)
    highs = np.full(n, 130.0) if highs is None else np.asarray(highs, float)
    ts = [T0 + pd.Timedelta(minutes=5 * i) for i in range(n)]
    fr = pd.DataFrame({"timestamp": ts, "bar_end": [x + pd.Timedelta(minutes=5) for x in ts], "low": lows, "high": highs})
    md = {0: {"frame": fr, "tf": "5m"}, 1: {"frame": fr, "tf": "5m"}}
    return NS(s=s, md=md, cache={0: NS(mr=np.full(n, 10.0)), 1: NS(mr=np.full(n, 10.0))}, known=lambda d, t: ([], 0),
              _same_pivot=lambda a, b: False), fr["bar_end"].iloc[-1]


def view(nodes, d=0, vu=1.0, vd=0.0, gray=False, pm=False):
    return DegreeView(d, nodes, nodes[0] if nodes else None, vu, vd, gray, pm)


def test_degree_setup_blocks():
    eng, t = fake_eng()
    z = node("zigzag", "B", invs=[(100.0, "below", "R6")], parent_key="P")
    p = NS(**{**vars(par("impulse", "3")), "key": "P"})
    up = view([p], d=1)
    assert SU.degree_setup(eng, Snapshot(t, {0: view([])}), 0, t) == "no_count"
    assert SU.degree_setup(eng, Snapshot(t, {0: view([z], gray=True)}), 0, t) == "gray"
    assert SU.degree_setup(eng, Snapshot(t, {0: view([z], pm=True)}), 0, t) == "parent_missing"
    a_end = node("zigzag", "A", nm=0)
    assert SU.degree_setup(eng, Snapshot(t, {0: view([a_end])}), 0, t) == "next_not_motive"      # R4 A-end
    opp = node("impulse", "2", nm=-1)
    opp.joint_score = 0.6
    assert SU.degree_setup(eng, Snapshot(t, {0: view([z, opp], vu=0.62, vd=0.38)}), 0, t) == "alt_block"
    st = SU.degree_setup(eng, Snapshot(t, {0: view([z]), 1: up}), 0, t)
    assert isinstance(st, SU.Setup) and st.code == "S6a" and st.tier == "B" and st.hard_inv == 100.0 and st.direction == "bull_put"
    inner = node("zigzag", "A", parent_key="Q")                                    # parent B च्या आत, शेवटचा भाग नाही
    inner.next_motive_dir = 1
    qb = NS(**{**vars(par("zigzag", "B")), "key": "Q"})
    assert SU.degree_setup(eng, Snapshot(t, {0: view([inner]), 1: view([qb], d=1)}), 0, t) == "inside_B_X_triangle"


def test_wick_beyond_inv_recount_and_skip():
    lows = np.full(60, 105.0)
    lows[-5] = 99.0                                                                  # wick A origin (100) खाली, count जिवंत
    eng, t = fake_eng(lows=lows)
    z = node("zigzag", "B", invs=[(100.0, "below", "R6")], prices=(100, 120))
    f = node("flat", "B", prices=(100, 120), tent=99.0)
    f.joint_score = 0.8
    st = SU.degree_setup(eng, Snapshot(t, {0: view([z, f])}), 0, t)
    assert isinstance(st, SU.Setup) and st.code == "S6b" and st.recount and st.hard_inv == pytest.approx(99.0 - 2.5)
    eng2, _ = fake_eng(s=_cfg(wick_beyond_inv_action="skip"), lows=lows)
    assert SU.degree_setup(eng2, Snapshot(t, {0: view([z, f])}), 0, t) == "wick_beyond_inv"


def test_c3_c_time_delay_and_terminal_c():
    eng, t = fake_eng()
    c = node("zigzag", "C", direction=-1, nm=1, prices=(130, 110, 120), invs=[(120.0, "below", "start-of-C")], parent_key="P",
             tent=106.0)
    c.time_flags = {"c_time_violation": True}
    p = NS(**{**vars(par("impulse", "2", cur_dir=-1, invs=[(100.0, "below", "R1")])), "key": "P"})
    snap = {0: view([c]), 1: view([p], d=1)}
    assert SU.degree_setup(eng, Snapshot(t, dict(snap)), 0, t) == "C3_c_time"
    eng1 = NS(**{**vars(eng), "_same_pivot": lambda a, b: a is b})
    term = view([NS(pattern="end_diag", points=[c.points[-1]])], d=-1)
    st = SU.degree_setup(eng1, Snapshot(t, {**snap, -1: term}), 0, t)                # हाच C ending diagonal ⇒ सूट
    assert isinstance(st, SU.Setup) and st.code == "S7" and st.hard_inv == 100.0
    other = view([NS(pattern="end_diag", points=[c.points[0]])], d=-1)               # दुसऱ्या ठिकाणचा diagonal ⇒ सूट नाही
    assert SU.degree_setup(eng1, Snapshot(t, {**snap, -1: other}), 0, t) == "C3_c_time"
    eng2, _ = fake_eng(s=_cfg(c_time_rule="score"))
    assert isinstance(SU.degree_setup(eng2, Snapshot(t, dict(snap)), 0, t), SU.Setup)


def test_disabled_setup_and_htf_gate():
    eng, t = fake_eng(s=_cfg(setups_enabled=["S1"]))
    z = node("zigzag", "B", invs=[(100.0, "below", "R6")])
    assert SU.degree_setup(eng, Snapshot(t, {0: view([z])}), 0, t) == "disabled_S6a"
    eng2, _ = fake_eng(s=_cfg(htf_gate_enabled=True))
    assert SU.degree_setup(eng2, Snapshot(t, {0: view([z])}), 0, t) == "htf_gate"


# ---------------------------------------------------------------- real data: signal invariants + truncation invariance
def _data(a, b):
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    return d[(d["timestamp"] >= a) & (d["timestamp"] <= b)].reset_index(drop=True)


@pytest.fixture(scope="module")
def run2019():
    d = _data("2019-01-01", "2019-03-31 23:59")
    sc = TR.Scanner(d, S0)
    ts = sc.md[0]["frame"]["bar_end"].iloc[300:]
    sc.run(ts)
    return d, sc, ts


def test_signal_invariants_breakout_ban(run2019):
    _, sc, _ = run2019
    assert sc.signals, "3 महिन्यांत एकही signal नाही — engine तपासा"
    allowed = set(S0["setups_enabled"])
    for x in sc.signals:
        fr = sc.frames[x.ttf]
        assert fr["bar_end"].iloc[x.ttf_idx] == x.t                                  # signal = TTF bar close
        o, h, l, c = x.comp
        if x.trade_dir > 0:
            assert c < x.sub_origin and l > x.hard_inv and c > x.touched              # T7 breakout ban, inv आत, reclaim
            assert x.soft_stop < l
        else:
            assert c > x.sub_origin and h < x.hard_inv and c < x.touched
            assert x.soft_stop > h
        ws = fr["timestamp"].iloc[x.ttf_idx - x.n + 1]
        assert ws.normalize() == x.t.normalize() and ws >= x.t.normalize() + pd.Timedelta("09:30:00")   # gap candle नाही
        assert pd.Timedelta("09:30:00") <= x.t - x.t.normalize() <= pd.Timedelta("14:45:00")
        assert x.setup in allowed and x.tier in "ABC" and x.degree in S0["trade_degrees_enabled"]
        assert x.touched in x.levels and x.vote >= S0["vote_min"] and x.opp_max < S0["alt_block_weight"]
        assert not (x.setup == "S7" and x.current_wave not in ("C", "Y"))
        if x.degree >= 1:                                                             # §12 test 8: H स्वतंत्रपणे D−1 pivots वरून
            lower, _ = sc.eng.known(x.degree - 1, x.t)
            want = "H" if x.trade_dir > 0 else "L"
            opp = [p for p in lower if x.wave_start_ts < p.ts < x.extreme_ts and p.kind == want]
            if opp:
                assert x.sub_origin == opp[-1].price
                assert (c < opp[-1].price) if x.trade_dir > 0 else (c > opp[-1].price)


def test_truncation_invariance(run2019):
    d, sc, ts = run2019
    cut = ts.iloc[len(ts) // 2]
    d2 = d[d["timestamp"] < cut].reset_index(drop=True)
    sc2 = TR.Scanner(d2, S0)
    sc2.run([t for t in ts if t <= cut])
    a = [(x.t, x.degree, x.setup, x.direction, x.tier, x.ttf, round(x.hard_inv, 6), round(x.score, 9), x.n) for x in sc.signals if x.t <= cut]
    b = [(x.t, x.degree, x.setup, x.direction, x.tier, x.ttf, round(x.hard_inv, 6), round(x.score, 9), x.n) for x in sc2.signals]
    assert a == b


def test_settings_new_types():
    c, e = S.validate({"setups_enabled": "S1,S5,S1", "entry_start": "9:31"})
    assert c["setups_enabled"] == ["S1", "S5"] and c["entry_start"] == "09:31" and not e
    c, e = S.validate({"setups_enabled": "S99", "entry_end": "24:00", "rejection_weights": "0.5,0.5"})
    assert c["setups_enabled"] == S.DEFAULTS["setups_enabled"] and c["entry_end"] == "14:45" and len(e) == 3
    c, e = S.validate({"entry_start": "15:00"})
    assert c["entry_start"] == "09:30" and e
    assert set(S.DEFAULTS["setups_enabled"]).isdisjoint({"S5", "S8", "S11", "S14"})


# ---------------------------------------------------------------- T7 breakout ban (synthetic, §12 test 8)
def _to_1m(bars5, start):
    rows = []
    for i, (o, h, l, c) in enumerate(bars5):
        t = start + pd.Timedelta(minutes=5 * i)
        for k, (a, b_, c_, d_) in enumerate([(o, o, o, o), (o, h, o, h), (h, h, l, l), (l, l, l, l), (l, max(l, c), min(l, c), c)]):
            rows.append((t + pd.Timedelta(minutes=k), a, b_, c_, d_))
    return rows


def _t7_scanner(rev, after=None, reflect=False):
    """Correction (खाली) + reversal candle `rev`; reflect ⇒ 200 − किंमत (bear call mirror)."""
    base = (100.0, 105.0, 95.0, 100.0)
    corr = [base] * 3 + [(110, 120, 108, 118), (118, 119, 110, 111), (111, 112, 104, 105), (105, 113, 104.5, 112),
                         (112, 112.5, 100, 101), (101, 102, 96, 97), rev] + (after or [base] * 5)
    day1 = [base] * 75
    if reflect:
        f = lambda r: (200 - r[0], 200 - r[2], 200 - r[1], 200 - r[3])           # noqa: E731
        corr, day1 = [f(r) for r in corr], [f(r) for r in day1]
    d = pd.DataFrame(_to_1m(day1, pd.Timestamp("2019-01-07 09:15")) + _to_1m(corr, pd.Timestamp("2019-01-08 09:15")),
                     columns=["timestamp", "open", "high", "low", "close"])
    s = _cfg(trigger_tf_mode="fixed", trigger_tf_fixed="5m")
    sc = TR.Scanner(d, s)
    ts0 = pd.Timestamp("2019-01-08 09:30")
    k = -1 if reflect else 1
    lv = [100.0, 102.0] if reflect else [100.0, 98.0]
    st = SU.Setup("S1", 0, "A", k, NS(pattern="impulse", current_wave="2"), None, lv, 110.0 if reflect else 90.0, "R1",
                  NS(ts=ts0, price=200 - 120.0 if reflect else 120.0),
                  NS(ts=ts0 + pd.Timedelta(minutes=25), price=104.0 if reflect else 96.0), 1.0, 0.0)
    return sc, st, pd.Timestamp("2019-01-08 10:05")


def test_T7_breakout_ban_synthetic():
    sc, st, t = _t7_scanner((97, 115, 96.5, 114))                     # close 114 > sub-leg origin 113 ⇒ breakout
    assert sc.trigger(st, t) == "T7_breakout"
    sc, st, t = _t7_scanner((97, 111, 96.5, 110))                     # close 110 < 113 ⇒ correction च्या आत
    sig = sc.trigger(st, t)
    assert isinstance(sig, TR.Signal), sig
    assert sig.sub_origin == 113.0 and sig.touched == 98.0 and sig.bars_last_subleg == 2 and sig.t == t
    assert sig.soft_stop == sig.comp[2] - S0["soft_buffer_pts"] and sig.comp[2] in (96.0, 96.5)
    assert sc.trigger(st, t + pd.Timedelta(minutes=1)) == "not_ttf_close"            # फक्त TTF bar close वर


def test_T7_bear_call_mirror():
    sc, st, t = _t7_scanner((97, 115, 96.5, 114), reflect=True)
    assert sc.trigger(st, t) == "T7_breakout"
    sc, st, t = _t7_scanner((97, 111, 96.5, 110), reflect=True)
    sig = sc.trigger(st, t)
    assert isinstance(sig, TR.Signal), sig
    assert sig.direction == "bear_call" and sig.sub_origin == 87.0 and sig.touched == 102.0
    assert sig.soft_stop == sig.comp[1] + S0["soft_buffer_pts"] and sig.comp[1] in (104.0, 103.5)


def test_hard_break_events_and_no_reentry():
    base = (100.0, 105.0, 95.0, 100.0)
    after = [base, (95, 96, 80, 81)] + [(81, 90, 79, 88)] * 2 + [base] * 3       # 10:10 चा bar 90 खाली displacement
    sc, st, t = _t7_scanner((97, 111, 96.5, 110), after=after)
    sig = sc.trigger(st, t)
    assert isinstance(sig, TR.Signal)
    assert level_events(sc, sig, t) == []
    ev = level_events(sc, sig, pd.Timestamp("2019-01-08 10:20"))
    assert ev and ev[0][0] == "hard" and ev[0][1] == 90.0                          # hard (soft सुद्धा, पण hard आधी क्रमात)
    assert level_events(sc, sig, pd.Timestamp("2019-01-08 10:10")) == []           # causal: break bar (10:10–10:15) बंद होण्याआधी नाही
    st2 = SU.Setup(**{**vars(st), "hard_inv": 70.0})                               # S6b सारखा inv हलला — तरी re-entry नाही
    assert sc.trigger(st2, pd.Timestamp("2019-01-08 10:35")) == "hard_broken_no_reentry"


def test_review_fixes_s8_end_diag_no_fallthrough_s7_under_y():
    eng, t = fake_eng()
    # S8: parent wxy X चा शेवटचा भाग ⇒ S8 (default बंद), S7 नाही
    c = node("zigzag", "C", parent_key="X1")
    x = NS(**{**vars(par("wxy", "X")), "key": "X1"})
    assert SU.classify(c, x, None)[0] == "S8"
    assert SU.degree_setup(eng, Snapshot(t, {0: view([c]), 1: view([x], d=1)}), 0, t) == "disabled_S8"
    # ending diagonal च्या आत pullback ⇒ block
    z = node("zigzag", "B", parent_key="E1")
    e = NS(**{**vars(par("end_diag", "3")), "key": "E1"})
    assert SU.degree_setup(eng, Snapshot(t, {0: view([z]), 1: view([e], d=1)}), 0, t) == "inside_end_diag"
    # preferred B आत ⇒ दुसऱ्या valid count कडे घसरत नाही
    inner = node("zigzag", "A", parent_key="Q")
    inner.next_motive_dir = 1
    other = node("impulse", "2", parent_key=None)
    other.joint_score = 0.9
    qb = NS(**{**vars(par("zigzag", "B")), "key": "Q"})
    assert SU.degree_setup(eng, Snapshot(t, {0: view([inner, other]), 1: view([qb], d=1)}), 0, t) == "inside_B_X_triangle"
    # S7 चा parent wxy Y (तोही संपतोय) ⇒ grandparent चा नियम-स्तर
    y = NS(**{**vars(par("wxy", "Y", invs=[(130.0, "above", "start-of-Y")])), "key": "Y1", "parent_key": "G"})
    g = NS(**{**vars(par("impulse", "4", invs=[(95.0, "below", "R3")])), "key": "G"})
    c2 = node("zigzag", "C", parent_key="Y1")
    st = SU.degree_setup(eng, Snapshot(t, {0: view([c2]), 1: view([y], d=1), 2: view([g], d=2)}), 0, t)
    assert isinstance(st, SU.Setup) and st.code == "S7" and st.hard_inv == 95.0 and st.inv_rule == "R3"
    assert st.wave_start is c2.points[0]                                         # S7: पूर्ण correction वरून TF/legs


def test_settings_entry_start_floor_and_weights():
    c, e = S.validate({"entry_start": "09:15"})
    assert c["entry_start"] == "09:30" and e
    c, e = S.validate({"rejection_weights": "0,0,0,1,0"})
    assert c["rejection_weights"] == S.DEFAULTS["rejection_weights"] and e
    import datetime
    c, e = S.validate({"entry_end": datetime.time(14, 30)})
    assert c["entry_end"] == "14:30" and not e
