"""थर 2 (legs: भूमिका, स्वभाव, I / K) — synthetic data फक्त, कुठलीही तारीख नाही (prompt §6)."""
import json
import os
import re

import numpy as np
import pandas as pd
import pytest

from elliott import data_policy as DP
from legs2 import charts as LC
from legs2 import ik as LI
from legs2 import measure as LM
from legs2 import settings as LS
from legs2 import volume as LV
from pivots import engine as PE
from pivots.dc import Pivot
from tests.test_pivots_dc import DATE_RX, SLOTS, _monday, m15_from, walk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BAR = pd.Timedelta(minutes=15)


# ---------------------------------------------------------------------------------------------------------------- मदत
def fake(points, n=None, tail=None, d0_extra=(), labels=None):
    """points = [(bar, price, kind)] ⇒ D1 (आणि D2) pivots; closes त्यांच्यामधून सरळ रेषेत. tail = (bar, price): शेवटचा चालू भाव.
    D0 = तेच pivots + d0_extra. confirm = bar + 2."""
    n = n or (tail[0] + 1 if tail else points[-1][0] + 4)
    allp = sorted(list(points) + list(d0_extra))
    xs, ys = [p[0] for p in allp], [p[1] for p in allp]
    if tail:
        xs.append(tail[0])
        ys.append(tail[1])
    m15 = m15_from(np.interp(np.arange(n), xs, ys), wick=0.0)
    ts = pd.to_datetime(m15["timestamp"])

    def pv(deg, b, price, kind):
        return Pivot(deg, kind, float(price), b, ts.iloc[b], b + 2, ts.iloc[b + 2] + BAR, 1.0, 4.0, "normal")
    p1 = [pv(1, b, pr, k) for b, pr, k in points]
    p0 = sorted([pv(0, b, pr, k) for b, pr, k in list(points) + list(d0_extra)], key=lambda p: p.bar)
    res = {"m15": m15, "pivots": {0: p0, 1: p1, 2: [pv(2, b, pr, k) for b, pr, k in points], 3: []},
           "segments": {pd.Timestamp(d): 0 for d in ts.dt.normalize().unique()}}
    lg = LM.build(res, None)
    for (d, i), lab in (labels or {}).items():
        lg["legs"][d][i]["label"] = lab
    return res, lg, m15


def asof_end(m15):
    return pd.Timestamp(m15["bar_end"].iloc[-1])


# ---------------------------------------------------------------------------------------------------------------- 1. no-lookahead
@pytest.mark.parametrize("seed", [3, 11])
def test_confirmed_leg_labels_and_current_leg_unchanged_by_truncation(seed):
    m15 = m15_from(walk(25 * 45, seed, 5.0))
    res = PE.build(m15)
    lg = LM.build(res)
    for cut in (25 * 38 + 7, 25 * 42 + 13):
        t = pd.Timestamp(m15["bar_end"].iloc[cut])
        r2 = PE.build(m15.iloc[:cut + 1].reset_index(drop=True))
        l2 = LM.build(r2)
        for d in (0, 1, 2):
            a = [LM.leg_json(L) for L in LM.known(lg, d, t)]
            b = [LM.leg_json(L) for L in LM.known(l2, d, t)]
            assert a == b
            ca, cb = LM.current(lg, d, t), LM.current(l2, d, t)
            assert (ca is None) == (cb is None)
            if ca is not None:
                assert LM.leg_json(ca) == LM.leg_json(cb)
        for d in (1, 2):
            assert json.dumps(LI.state_at(lg, d, t), default=str) == json.dumps(LI.state_at(l2, d, t), default=str)


# ---------------------------------------------------------------------------------------------------------------- 2. leg bars
def test_leg_bars_partition_no_bar_in_two_legs():
    m15 = m15_from(walk(25 * 40, 5, 5.0))
    lg = LM.build(PE.build(m15))
    for d in (0, 1):
        ls = lg["legs"][d]
        seen = []
        for L in ls:
            seen += list(range(L["a"].bar + 1, L["b"].bar + 1))
        assert len(seen) == len(set(seen))
        assert seen == list(range(ls[0]["a"].bar + 1, ls[-1]["b"].bar + 1))


# ---------------------------------------------------------------------------------------------------------------- 3. R
def test_role_dominant_iff_wick_beyond_and_eq_priority_and_first_unknown():
    pts = [(0, 120, "H"), (5, 100, "L"), (12, 130, "H"), (18, 110, "L"), (25, 129, "H"), (31, 105, "L")]
    _, lg, _ = fake(pts)
    ls = lg["legs"][1]
    assert ls[0]["role"] == LM.ROLE_UNK and ls[0]["label"] == "अज्ञात"
    for L in ls[1:]:
        beyond = (L["b"].price > L["prev"].price) if L["dir"] > 0 else (L["b"].price < L["prev"].price)
        assert (L["role"] == LM.ROLE_DOM) == beyond == (L["R"] > 1)
    assert ls[3]["role"] == LM.ROLE_RET and abs(ls[3]["R"] - 19 / 20) < 1e-9          # R = परताव्याचा टक्का
    res, lg2, _ = fake(pts)
    a, b = res["pivots"][1][3], res["pivots"][1][4]
    L = LM._leg(res, lg2["A"], 1, a, b.__class__(**{**b.__dict__, "eq": True}), res["pivots"][1][2], lg2["rv"], lg2["bad"], lg2["settings"])
    assert L["role"] == LM.ROLE_EQ


# ---------------------------------------------------------------------------------------------------------------- 4. C
def _A(o, h, lo, c, first):
    return {"o": np.array(o, float), "h": np.array(h, float), "l": np.array(lo, float), "c": np.array(c, float), "first": np.array(first)}


def test_er_between_0_and_1_and_gap_removed():
    rng = np.random.default_rng(1)
    for _ in range(50):
        c = 100 + np.cumsum(rng.normal(0, 1, 12))
        o = np.r_[c[0], c[:-1]] + rng.normal(0, 0.3, 12)
        A = _A(o, np.maximum(o, c) + 0.2, np.minimum(o, c) - 0.2, c, [i % 5 == 0 for i in range(12)])
        er = LM.candle_metrics(A, 0, 11, 1)[0]["er"]
        assert 0.0 <= er <= 1.0
    # session 1 मध्ये बाजूला, मग मोठा overnight gap, session 2 मध्ये बाजूला ⇒ gap वगळल्यावर ER = 1.5 / 3.5 (gap सह 0.96 झाला असता)
    c = [100, 100.5, 100, 100.5, 150, 150.5, 150, 150.5]
    o = [100, 100, 100.5, 100, 149.5, 150, 150.5, 150]
    A = _A(o, np.maximum(o, c), np.minimum(o, c), c, [True, False, False, False, True, False, False, False])
    m, gaps = LM.candle_metrics(A, 0, 7, 1)
    assert m["er"] == pytest.approx(1.5 / 3.5) and gaps == {4: pytest.approx(49.0)}


def test_overlap_skips_session_crossing_pair_and_body_skips_flat_candle():
    o = [100, 100, 101, 200, 201]
    c = [100, 101, 102, 201, 202]
    h = [100, 101, 102, 201, 202]
    lo = [100, 100, 101, 200, 201]
    A = _A(o, h, lo, c, [True, False, False, True, False])
    m = LM.candle_metrics(A, 0, 4, 1)[0]
    assert m["overlap"] == pytest.approx(0.0)                                       # (2,3) session ओलांडणारी जोडी नाही
    A2 = _A([100, 100, 101], [100, 100, 102], [100, 100, 101], [100, 100, 102], [True, False, False])
    m2 = LM.candle_metrics(A2, 0, 2, 1)[0]
    assert m2["body"] == pytest.approx(1.0)                                         # high = low candle वगळली


def test_overlap_counts_in_reverse_and_short_leg_neutral():
    base = [{"raw": {"er": 0.5, "overlap": x, "body": 0.5, "dirc": 0.5}, "warmup": False, "seg": 0, "known_at": pd.Timestamp(0)}
            for x in np.linspace(0, 1, 20)]
    hi = {"raw": {"er": 0.5, "overlap": 0.95, "body": 0.5, "dirc": 0.5}, "warmup": False, "seg": 0, "known_at": pd.Timestamp(1)}
    lo = {"raw": {"er": 0.5, "overlap": 0.05, "body": 0.5, "dirc": 0.5}, "warmup": False, "seg": 0, "known_at": pd.Timestamp(1)}
    LM._baseline(base + [hi], LS.load())
    LM._baseline(base + [lo], LS.load())
    assert hi["pct"]["overlap"] < 0.1 and lo["pct"]["overlap"] > 0.9                  # जास्त overlap ⇒ सुधारात्मक
    pts = [(0, 120, "H"), (5, 100, "L"), (7, 130, "H")]
    _, lg, _ = fake(pts)
    L = lg["legs"][1][1]
    assert L["bars"] == 2 and L["short"] and L["nature"] == LM.NEU


# ---------------------------------------------------------------------------------------------------------------- 5. baseline
def _legs(n, seg=0, warm=False):
    return [{"raw": {"er": 0.1 * (i % 10), "overlap": 0.5, "body": 0.5, "dirc": 0.5}, "warmup": warm, "seg": seg,
             "known_at": pd.Timestamp(i)} for i in range(n)]


def test_baseline_past_only_no_warmup_no_other_segment_and_min_count():
    s = LS.load()
    ls = _legs(5, warm=True) + _legs(5, seg=7) + _legs(9)
    LM._baseline(ls, s)
    assert ls[-1]["n_base"] == 8 and ls[-1]["C_na"] and ls[-1]["C"] is None and ls[-1]["c_cls"] == LM.NEU
    ls = _legs(12)
    LM._baseline(ls, s)
    assert ls[-1]["n_base"] == 11 and not ls[-1]["C_na"] and ls[-1]["c_warmup"]
    assert ls[0]["n_base"] == 0                                                       # भविष्यातले legs कधीच नाहीत
    ls = _legs(60)
    LM._baseline(ls, s)
    assert ls[-1]["n_base"] == 40 and not ls[-1]["c_warmup"]


def test_tie_average_rank_and_degrees_not_mixed():
    assert LM.pct_rank(5, [5, 5]) == 0.5 and LM.pct_rank(5, [1, 5, 9]) == 0.5
    m15 = m15_from(walk(25 * 40, 8, 5.0))
    lg = LM.build(PE.build(m15))
    for d, ls in lg["legs"].items():
        assert all(L["degree"] == d for L in ls)


# ---------------------------------------------------------------------------------------------------------------- 6. volume
def _days(n=30):
    return list(pd.bdate_range(_monday(500), periods=n))


def _fut(days, exp_idx, mult=None, far=True):
    """5M futures: near contract (expiry = days[exp_idx]) आणि पुढचा; 09:15 slot 10×."""
    e1, e2 = days[exp_idx], days[-1] + pd.Timedelta(days=28)
    rows = []
    for i, d in enumerate(days):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=25), freq="5min"):
            v = 1000.0 if t - d < pd.Timedelta(hours=9, minutes=30) else 100.0
            v *= (mult or {}).get(i, 1.0)
            if d <= e1:
                rows.append((t, v, f"NIFTY FUT {e1:%d %b %y}".upper()))
                if far:
                    rows.append((t, 5 * v, f"NIFTY FUT {e2:%d %b %y}".upper()))
            else:
                rows.append((t, v, f"NIFTY FUT {e2:%d %b %y}".upper()))
    return pd.DataFrame(rows, columns=["timestamp", "volume", "contract"])


def _m15_days(days):
    rows = []
    for d in days:
        for sl in SLOTS:
            t = d + sl
            rows.append((t, t + BAR, 100.0, 101.0, 99.0, 100.5))
    return pd.DataFrame(rows, columns=["timestamp", "bar_end", "open", "high", "low", "close"])


def test_expiry_from_contract_field_rollover_unreliable_and_out_of_baseline():
    days = _days()
    m15 = _m15_days(days)
    s = LS.load({"rvol_sessions": 3, "rvol_min_sessions": 3})
    fut = _fut(days, 20, mult={18: 50.0, 19: 50.0, 20: 50.0})
    rv, bad = LV.rvol(m15, fut, s)
    day = pd.to_datetime(m15["timestamp"]).dt.normalize()
    assert set(day[bad].unique()) == {days[18], days[19], days[20]}                 # expiry + आधीचे 2 sessions
    same_wd = [d for d in days[:18] if d.dayofweek == days[20].dayofweek]
    assert same_wd and not bad[day.isin(same_wd).to_numpy()].any()                     # वारावरून नियम नाही (weekly expiry baseline मध्ये)
    i21 = np.flatnonzero((day == days[21]).to_numpy())
    assert np.allclose(rv[i21], 1.0)                                                   # baseline मध्ये rollover दिवस नाहीत
    i10 = np.flatnonzero((day == days[10]).to_numpy())
    assert np.allclose(rv[i10], 1.0)                                                   # slot-wise median (09:15 = 10× असूनही 1)


def test_near_month_picks_nearest_and_holdout_rows_never_used():
    days = _days(8)
    fut = _fut(days, 3)
    hold = fut.copy()
    hold["timestamp"] = DP.HOLDOUT_START + (pd.to_datetime(hold["timestamp"]) - pd.Timestamp(days[0]))
    nm = LV.near_month(pd.concat([fut, hold], ignore_index=True))
    ts = pd.to_datetime(nm["timestamp"])
    assert not ((ts >= DP.HOLDOUT_START) & (ts < DP.CONTAMINATED_START)).any()
    assert (nm[ts.dt.normalize() <= days[3]]["expiry"] == days[3]).all()
    assert (nm[ts.dt.normalize() > days[3]]["expiry"] > days[3]).all()


def test_volume_neutral_when_more_than_half_unreliable():
    s = LS.load()
    L = {"rv_bars": (np.array([2.0, 2.0, 2.0, 2.0]), np.array([True, True, True, False]))}
    P = {"rv_bars": (np.array([1.0, 1.0]), np.array([False, False]))}
    LM._volume(L, P, s)
    assert L["V"] is None and L["v_cls"] == LM.NEU
    L = {"rv_bars": (np.array([2.0, 2.0, np.nan, 2.0]), np.array([False] * 4))}
    LM._volume(L, P, s)
    assert L["V"] == pytest.approx(2.0) and L["v_cls"] == LM.IMP


# ---------------------------------------------------------------------------------------------------------------- 7–8. तक्ते
NAT = {("आवेगी", "आवेगी"): ("आवेगी", False), ("आवेगी", "तटस्थ"): ("आवेगी", False), ("आवेगी", "सुधारात्मक"): ("तटस्थ", False),
       ("तटस्थ", "आवेगी"): ("आवेगी", True), ("तटस्थ", "तटस्थ"): ("तटस्थ", False), ("तटस्थ", "सुधारात्मक"): ("सुधारात्मक", True),
       ("सुधारात्मक", "आवेगी"): ("तटस्थ", False), ("सुधारात्मक", "तटस्थ"): ("सुधारात्मक", False),
       ("सुधारात्मक", "सुधारात्मक"): ("सुधारात्मक", False)}


@pytest.mark.parametrize("c,v", list(NAT))
def test_nature_table_all_nine(c, v):
    assert LM.nature(c, v) == NAT[(c, v)]


LAB = {("प्रबळ", "आवेगी"): "आवेग", ("प्रबळ", "तटस्थ"): "आवेग (कमकुवत)", ("प्रबळ", "सुधारात्मक"): "विरोध-1",
       ("परतावा", "आवेगी"): "विरोध-2", ("परतावा", "तटस्थ"): "सुधार (कमकुवत)", ("परतावा", "सुधारात्मक"): "सुधार",
       ("बरोबरी", "आवेगी"): "बरोबरी-आवेगी", ("बरोबरी", "तटस्थ"): "बरोबरी", ("बरोबरी", "सुधारात्मक"): "बरोबरी-सुधारात्मक",
       ("अज्ञात", "आवेगी"): "अज्ञात", ("अज्ञात", "तटस्थ"): "अज्ञात", ("अज्ञात", "सुधारात्मक"): "अज्ञात"}


@pytest.mark.parametrize("r,n", list(LAB))
def test_label_table_all_twelve(r, n):
    assert LM.label(r, n) == LAB[(r, n)]


def test_weak_nature_counts_as_neutral_in_label():
    assert LM.label("प्रबळ", "आवेगी", weak=True) == "आवेग (कमकुवत)"
    assert LM.label("परतावा", "सुधारात्मक", weak=True) == "सुधार (कमकुवत)"


# ---------------------------------------------------------------------------------------------------------------- 9. रचना
def _pp(prices):
    return [Pivot(0, "L" if i % 2 == 0 else "H", float(p), i, pd.Timestamp(0), i, pd.Timestamp(0), 1.0, 1.0, "normal")
            for i, p in enumerate(prices)]


def test_structure_note_clean_five_overlap_and_odd_counts():
    assert LM.structure(_pp([100, 110, 105, 125, 115, 130]), 1)["note"] == "5✓"
    assert LM.structure(_pp([100, 110, 105, 125, 108, 130]), 1)["note"] == "5 overlap"
    assert LM.structure(_pp([100, 110, 105, 125, 115, 130, 120, 140]), 1)["note"] == "7"
    assert LM.structure([Pivot(0, "H", -p, i, pd.Timestamp(0), i, pd.Timestamp(0), 1.0, 1.0, "normal")
                         for i, p in enumerate([100, 110, 105, 125, 115, 130])], -1)["note"] == "5✓"   # आरसा
    m15 = m15_from(walk(25 * 40, 9, 5.0))
    lg = LM.build(PE.build(m15))
    for d in (1, 2):
        for L in lg["legs"][d]:
            assert L["structure"]["n"] % 2 == 1
    assert all(L["structure"] is None for L in lg["legs"][0])                         # D0 ला रचना नाही (अपेक्षित)


def test_structure_never_changes_label():
    m15 = m15_from(walk(25 * 40, 9, 5.0))
    lg = LM.build(PE.build(m15))
    for L in lg["legs"][1]:
        before = L["label"]
        L["structure"] = {"n": 5, "note": "5✓"}
        LM._label(L, lg["settings"])
        assert L["label"] == before


# ---------------------------------------------------------------------------------------------------------------- 10. I / K
IMP_ZZ = [(0, 170, "H"), (6, 100, "L"), (12, 120, "H"), (17, 110, "L"), (27, 150, "H"), (32, 140, "L"), (42, 160, "H"),
          (48, 145, "L"), (53, 152, "H"), (61, 138, "L")]


def test_zigzag_c_does_not_replace_i_and_wave1_in_origin_and_resumption_not_k():
    res, lg, m15 = fake(IMP_ZZ, tail=(72, 158))
    labs = [L["label"] for L in lg["legs"][1]]
    assert labs[-1] in LM.IMPULSE_LABELS and lg["legs"][1][-1]["dir"] < 0              # C चा label "आवेग" असला तरी
    st = LI.state_at(lg, 1, asof_end(m15))
    assert st["I"]["dir"] == 1 and st["I"]["end"]["price"] == 160 and st["I"]["origin"]["price"] == 100
    assert not st["I"]["origin_open"]
    assert st["state"] == LI.ST_K and st["K"]["depth_pct"] == pytest.approx(100 * 22 / 60, abs=0.1)
    assert st["K"]["counter_impulse"]                                                  # विरुद्ध दिशेचा आवेग ⇒ नोंद, gate नाही
    _, lg2, m2 = fake(IMP_ZZ, tail=(78, 166))                                           # resumption I_end पलीकडे (D1 अपुष्ट)
    st2 = LI.state_at(lg2, 1, asof_end(m2))
    assert st2["state"] in (LI.ST_IMP, LI.ST_KSTART) and st2["state"] != LI.ST_K


def test_i_end_moves_on_any_label_and_conflict_legs_never_become_i():
    pts = IMP_ZZ + [(75, 166, "H")]
    _, lg, m15 = fake(pts, labels={(1, 9): "विरोध-1"})
    st = LI.state_at(lg, 1, asof_end(m15))
    assert st["I"]["end"]["price"] == 166 and st["I"]["origin"]["price"] == 100
    assert any("सरकला" in e["event"] for e in st["log"])
    lab = {(1, i): "विरोध-2" for i in range(len(IMP_ZZ) - 1)}
    _, lg3, m3 = fake(IMP_ZZ, labels=lab)
    st3 = LI.state_at(lg3, 1, asof_end(m3))
    assert st3["I"] is None and st3["state"] == "I नाही" and st3["alt_I"]


def test_origin_real_break_cancels_i_then_new_i():
    pts = IMP_ZZ + [(70, 150, "H"), (100, 60, "L"), (106, 75, "H")]
    _, lg, m15 = fake(pts, tail=(115, 70))
    st = LI.state_at(lg, 1, asof_end(m15))
    ev = [e["event"] for e in st["log"]]
    assert any("रद्द" in e for e in ev) and "नवा I" in ev
    assert st["I"]["dir"] == -1 and st["I"]["end"]["price"] == 60


def test_impulse_running_and_k_may_have_started():
    pts = [(0, 120, "H"), (8, 100, "L"), (24, 150, "H")]
    _, lg, m15 = fake(pts, tail=(34, 158))
    st = LI.state_at(lg, 1, asof_end(m15))
    assert st["I"]["end"]["price"] == 150 and st["state"] == LI.ST_IMP
    _, lg2, m2 = fake(pts, tail=(40, 150), d0_extra=[(34, 158, "H")], n=41)
    lg2["res"]["pivots"][0] = lg2["res"]["pivots"][0] + [Pivot(0, "L", 152.0, 36, m2["timestamp"].iloc[36], 37,
                                                                m2["timestamp"].iloc[37] + BAR, 1.0, 2.0, "normal")]
    st2 = LI.state_at(lg2, 1, asof_end(m2))
    assert st2["state"] == LI.ST_KSTART and st2["retrace_pct"] == pytest.approx(100 * 8 / 58, abs=0.2)


def test_d2_tracker_runs_with_same_rules():
    _, lg, m15 = fake(IMP_ZZ, tail=(72, 158))
    st = LI.state_at(lg, 2, asof_end(m15))
    assert st["degree"] == 2 and st["I"]["end"]["price"] == 160 and st["state"] == LI.ST_K


# ---------------------------------------------------------------------------------------------------------------- 11. caption
def test_caption_limits_and_no_code_keys():
    _, lg, m15 = fake(IMP_ZZ, tail=(72, 158))
    t = asof_end(m15)
    sts = {1: LI.state_at(lg, 1, t), 2: LI.state_at(lg, 2, t), "conflicts": 2}
    cap = LC.caption(3, 22, t, sts)
    assert len(cap.encode("utf-16-le")) // 2 <= 1024 and len(cap.splitlines()) <= 8
    assert cap.startswith("🧭 LEG CHECK 3/22") and "Reply" in cap
    for key in ("_", "{", "}", "D1", "known", "None"):
        assert key not in cap


# ---------------------------------------------------------------------------------------------------------------- 12–14
def test_leg_check_kinds_not_measured_and_no_order_imports():
    from backtest_review import store as BS
    for k in ("leg_check", "pattern_check"):
        assert k in BS.KINDS and k in BS.NOT_MEASURED
    files = [os.path.join(ROOT, "legs2", f) for f in os.listdir(os.path.join(ROOT, "legs2")) if f.endswith(".py")]
    for f in files + [os.path.join(ROOT, "scripts", "leg_check.py")]:
        if f.endswith(".py"):
            src = open(f, encoding="utf-8").read()
            assert not re.search(r"^\s*(?:from|import)\s+(?:broker|order|upstox_api|kite|shoonya|stocko)", src, re.M)


DATE_RX_I = [re.compile(rx.pattern, re.I) for rx in DATE_RX]                   # "OCT" सारखे मोठ्या अक्षरांतले महिने सुद्धा


def test_no_date_literals_in_new_code():
    paths = [os.path.join(ROOT, "legs2", f) for f in os.listdir(os.path.join(ROOT, "legs2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "leg_check.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits


def test_script_writes_only_out_dir_and_rerun_is_byte_identical(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("lgc", os.path.join(ROOT, "scripts", "leg_check.py"))
    SC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(SC)
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
        assert SC.main(["--data", str(data), "--out-dir", str(od), "--run-id", "legs/t", "--days", "2", "--futures-dir", ""]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert set(os.listdir(tmp_path)) - before == {"a", "b"}
    assert outs[0] == outs[1] and outs[0]
    man = json.loads(outs[0]["manifest.json"])
    assert all(it["kind"] == "leg_check" for it in man["items"])


# ---------------------------------------------------------------------------------------------------------------- review नंतरचे tests
def test_k_running_once_i_end_confirmed_and_kstart_only_beyond_i_end():
    pts = [(0, 120, "H"), (8, 100, "L"), (24, 150, "H")]
    _, lg, m15 = fake(pts, tail=(34, 140))
    st = LI.state_at(lg, 1, asof_end(m15))
    assert st["state"] == LI.ST_K and st["K"]["legs"] == [] and st["K"]["depth_pct"] == pytest.approx(20.0)


def test_d2_impulse_running_uses_d1_not_d0_reversal():
    pts = [(0, 120, "H"), (8, 100, "L"), (24, 150, "H")]
    _, lg, m2 = fake(pts, tail=(40, 154), d0_extra=[(34, 158, "H")], n=41)
    lg["res"]["pivots"][0] = lg["res"]["pivots"][0] + [Pivot(0, "L", 152.0, 36, m2["timestamp"].iloc[36], 37,
                                                              m2["timestamp"].iloc[37] + BAR, 1.0, 2.0, "normal")]
    t = asof_end(m2)
    assert LI.state_at(lg, 1, t)["state"] == LI.ST_KSTART                          # D1: D0 चा उलट pivot
    assert LI.state_at(lg, 2, t)["state"] == LI.ST_IMP                             # D2: D1 चा उलट pivot नाही


def test_rollover_days_same_in_replay_and_live_with_holiday(monkeypatch):
    import config
    days = _days(25)
    exp = days[20]
    hol = days[19]                                                                 # expiry च्या आदल्या दिवशी सुट्टी
    monkeypatch.setattr(config, "NSE_HOLIDAYS_TEST", {hol.date()}, raising=False)
    sess = [d for d in days if d != hol]
    full = LV.rollover_days([exp], sess, 2)
    cut = [d for d in sess if d <= days[17]]                                       # live: expiry अजून data च्या पलीकडे
    live = LV.rollover_days([exp], cut, 2)
    assert full == live == {exp, days[18], days[17]}


def test_futures_volume_truncation_no_lookahead():
    days = _days(32)
    m15 = m15_from(walk(25 * 32, 7, 5.0), start=days[0])
    fut = _fut(days, 22)
    s = LS.load({"rvol_sessions": 5, "rvol_min_sessions": 3})
    rv, bad = LV.rvol(m15, fut, s)
    cut = 25 * 26 + 9
    t = pd.Timestamp(m15["bar_end"].iloc[cut])
    rv2, bad2 = LV.rvol(m15.iloc[:cut + 1], fut[pd.to_datetime(fut["timestamp"]) < t], s)
    assert np.allclose(rv[:cut + 1], rv2, equal_nan=True) and (bad[:cut + 1] == bad2).all()


def test_current_leg_and_tracker_never_cross_holdout_segment():
    pre = m15_from(walk(25 * 40, 12, 5.0), start=DP.HOLDOUT_START - pd.Timedelta(days=70))
    pre = pre[pd.to_datetime(pre["timestamp"]) < DP.HOLDOUT_START]
    post = m15_from(walk(25 * 4, 13, 5.0) + 3000, start=DP.CONTAMINATED_START + pd.Timedelta(days=3))
    m15 = pd.concat([pre, post], ignore_index=True)
    lg = LM.build(PE.build(m15))
    t = asof_end(m15)
    for d in (0, 1, 2):
        c = LM.current(lg, d, t)
        assert c is None or pd.Timestamp(c["a"].ts) >= DP.CONTAMINATED_START
    for d in (1, 2):
        st = LI.state_at(lg, d, t)
        assert st["I"] is None or pd.Timestamp(st["I"]["origin"]["ts"]) >= DP.CONTAMINATED_START


def test_gap_noted_on_short_legs_and_weak_nature_visible():
    pts = [(0, 120, "H"), (5, 100, "L"), (26, 140, "H")]
    res, lg, m15 = fake(pts)
    L = lg["legs"][1][1]
    L2 = LM._leg(res, lg["A"], 1, res["pivots"][1][1], res["pivots"][1][2], res["pivots"][1][0], lg["rv"], lg["bad"], lg["settings"])
    assert "gaps" in L2
    L = {"R": 1.5, "C": None, "C_na": False, "V": 1.4, "structure": None, "gap": True, "gap_sigma": 1.2, "weak": True,
         "nature": LM.IMP, "short": False}
    why = LM.reasons(L)
    assert "स्वभाव आवेगी (कमकुवत)" in why and "gap 1.2σ" in why


def test_shadow_old_modules_unchanged():
    from tests.test_pivots_dc import shadow_fingerprint
    fx = json.load(open(os.path.join(HERE, "fixtures", "pivots_shadow_baseline.json"), encoding="utf-8"))
    assert shadow_fingerprint() == fx
