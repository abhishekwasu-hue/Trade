"""थर v2.2 (decision3) — crafted data वर प्रत्येक नियम: ① Daily Dow, ② 1H levels जीवनक्रम, truncation, तारीख-मुक्त, register."""
import os
import re
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd

from decision3 import daily as DD
from decision3 import levels as LV
from decision3 import settings as S3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------------------ crafted Daily
def daily_from_path(points, legs=4, start="2030-01-01"):
    """turning points ⇒ Daily candles (प्रत्येक leg `legs` दिवस, सरळ रेषा). high/low = आदला–आताचा close + 0.5."""
    closes = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        closes += list(np.linspace(a, b, legs + 1)[1:])
    days = pd.bdate_range(start, periods=len(closes))
    rows = []
    prev = closes[0]
    for d, c in zip(days, closes):
        rows.append({"timestamp": d, "open": prev, "high": max(prev, c) + 0.5, "low": min(prev, c) - 0.5, "close": c,
                     "bar_end": d + pd.Timedelta(hours=15, minutes=30)})
        prev = c
    return pd.DataFrame(rows)


S = {"daily_min_sessions": 3, "daily_sigma_sessions": 3, "range_eq_sigma_d": 0.25}


def test_up_after_hh_hl_and_protected_is_hl():
    d = daily_from_path([100, 120, 110, 130, 118, 140])
    st = DD.fold(d, S)
    assert st[-1].trend == "UP"
    assert st[-1].protected.kind == "L" and abs(st[-1].protected.price - 117.5) < 1e-6        # L2 (HL) wick


def test_hl_close_break_neutral_then_new_lh_ll_down():
    d = daily_from_path([100, 120, 110, 130, 118, 140, 112])                                  # close < HL (118) ⇒ NEUTRAL
    st = DD.fold(d, S)
    trends = [x.trend for x in st]
    assert "UP" in trends and trends[-1] == "NEUTRAL"
    d2 = daily_from_path([100, 120, 110, 130, 118, 140, 112, 125, 100, 115, 92, 105])           # नवा LH (125 < 140) + LL
    st2 = DD.fold(d2, S)
    assert st2[-1].trend == "DOWN" and st2[-1].protected.kind == "H"


def test_deep_pullback_60pct_keeps_up():
    # 118 ⇒ 140 नंतर 60% retrace (≈ 126.8) — protected 118 तुटत नाही ⇒ UP कायम (net/H regime नाही)
    d = daily_from_path([100, 120, 110, 130, 118, 140, 126.8, 135])
    st = DD.fold(d, S)
    assert all(x.trend == "UP" for x in st[-10:])


def test_wick_below_protected_is_not_a_break():
    d = daily_from_path([100, 120, 110, 130, 118, 140, 119])
    d.loc[len(d) - 1, "low"] = 115.0                                                          # wick protected खाली, close वर
    assert DD.fold(d, S)[-1].trend == "UP"


def test_unknown_only_when_data_short():
    d = daily_from_path([100, 120, 110, 130, 118, 140])
    st = DD.fold(d, {**S, "daily_min_sessions": 10})
    assert all(x.trend == "UNKNOWN" for x in st[:10]) and st[10].trend != "UNKNOWN"


def test_range_from_neutral_equal_highs_lows():
    d = daily_from_path([100, 120, 110, 130, 118, 140, 112, 130, 112.2, 130.2, 112.1, 122])
    st = DD.fold(d, S)
    assert any(x.trend == "RANGE" for x in st)
    r = [x for x in st if x.trend == "RANGE"][0]
    assert r.band[0] < r.band[1]


def test_dc_method_also_finds_up():
    d = daily_from_path([100, 120, 110, 130, 118, 140])
    st = DD.fold(d, {**S, "daily_swing_method": "dc", "daily_dc_k": 1.0})
    assert st[-1].trend == "UP"


def test_daily_truncation_invariant():
    d = daily_from_path([100, 120, 110, 130, 118, 140, 112, 125, 100, 115, 92, 105])
    full = DD.fold(d, S)
    for k in range(5, len(d)):
        part = DD.fold(d.iloc[:k], S)
        assert [(x.trend, getattr(x.protected, "price", None)) for x in part] == \
               [(x.trend, getattr(x.protected, "price", None)) for x in full[:k]]


def test_state_at_uses_known_at_only():
    d = daily_from_path([100, 120, 110, 130, 118, 140])
    st = DD.fold(d, S)
    i = next(i for i, x in enumerate(st) if x.trend == "UP")
    before = st[i].known_at - pd.Timedelta(minutes=1)
    assert DD.state_at(st, before).trend != "UP" and DD.state_at(st, st[i].known_at).trend == "UP"


# ------------------------------------------------------------------------------------------------ crafted 15M + D2 pivots
def m15_from(closes, start="2030-01-07", per_day=25, wick=1.0, lows=None, highs=None):
    rows, prev = [], closes[0]
    days = pd.bdate_range(start, periods=(len(closes) + per_day - 1) // per_day)
    for i, c in enumerate(closes):
        d = days[i // per_day]
        ts = d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % per_day))
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": prev, "close": c,
                     "high": (highs or {}).get(i, max(prev, c) + wick), "low": (lows or {}).get(i, min(prev, c) - wick)})
        prev = c
    return pd.DataFrame(rows)


def res_of(m15, piv2, piv1=(), sig=10.0):
    days = pd.to_datetime(m15["timestamp"]).dt.normalize().unique()
    return {"m15": m15, "pivots": {0: [], 1: list(piv1), 2: list(piv2)}, "sigma_1h": {pd.Timestamp(x): sig for x in days}}


def P(kind, price, bar, confirm):
    return NS(kind=kind, price=float(price), bar=bar, confirm_bar=confirm)


def test_small_pivot_makes_no_level():
    m = m15_from([100 + (i % 5) for i in range(40)])
    lv = LV.Levels(res_of(m, piv2=[], piv1=[P("H", 104, 4, 6)]))
    assert lv.L == []


def _support_case(after):
    """D2 L 100 (bar 4) ⇒ support; नंतरचे closes `after`."""
    closes = [110, 106, 103, 101, 100.5, 104, 108, 112, 115, 113] + after
    m = m15_from(closes, lows={4: 100.0})
    piv = [P("H", 116, 0, 2), P("L", 100.0, 4, 6)]
    return m, LV.Levels(res_of(m, piv))


def test_close_beyond_is_flip_not_death_and_sweep_star():
    m, lv = _support_case([108, 104, 102, 105, 99, 95, 98])
    sup = [L for L in lv.L if "a:D2" in L.births and L.role0 == LV.SUP][0]
    t_end = len(m) - 1
    assert sup.alive(t_end)                                                    # close पलीकडे ⇒ मृत्यू नाही
    assert sup.role_at(t_end) == LV.RES and "c" in sup.births                  # flip ⇒ उलट भूमिका
    m2, lv2 = _support_case([108, 104, 103])
    m2.loc[len(m2) - 1, "low"] = sup.lo - 2.0                                   # wick पट्ट्याखाली, close परत
    lv2 = LV.Levels(res_of(m2, [P("H", 116, 0, 2), P("L", 100.0, 4, 6)]))
    s2 = [L for L in lv2.L if L.role0 == LV.SUP][0]
    assert s2.count("sweep", len(m2) - 1) == 1


def test_death_only_when_swing_beyond_breaks():
    # (i) support: एकाच candle चा close पट्टा आणि पलीकडचा swing (90) दोन्हीच्या खाली ⇒ मेला
    closes = [110, 104, 96, 92, 90.5, 95, 99, 103, 108, 112, 109, 104, 101, 99, 97, 101, 105, 110, 108, 104, 100, 98, 86]
    m = m15_from(closes, lows={4: 90.0})
    piv = [P("H", 113, 0, 1), P("L", 90.0, 4, 6), P("H", 113, 9, 11), P("L", 96.5, 14, 16)]
    lv = LV.Levels(res_of(m, piv))
    upper = [L for L in lv.L if L.role0 == LV.SUP and abs(L.anchor - 96.5) < 1e-6][0]
    assert upper.dead_bar == len(closes) - 1 and upper.count("flip", upper.dead_bar) == 0
    # (ii) close फक्त पट्ट्यापलीकडे ⇒ flip (resistance), जिवंत; नंतर पलीकडचा swing (90) close ने तुटला ⇒ मेला
    closes2 = closes[:-2] + [94, 93, 92, 91.5, 89]
    m2 = m15_from(closes2, lows={4: 90.0})
    lv2 = LV.Levels(res_of(m2, piv))
    up2 = [L for L in lv2.L if L.role0 == LV.SUP and abs(L.anchor - 96.5) < 1e-6][0]
    t_flip = next(b for b, k, _ in up2.events if k == "flip")
    assert closes2[t_flip] < up2.band_at(t_flip)[0] and up2.alive(len(closes2) - 2) and up2.role_at(len(closes2) - 2) == LV.RES
    assert up2.dead_bar == len(closes2) - 1 and closes2[-1] < 90


def test_bos_origin_becomes_level():
    closes = [104, 102, 100.5, 101, 103, 105, 107, 109, 108, 106, 107, 109, 111, 113]
    m = m15_from(closes, lows={2: 100.0}, highs={7: 110.0})
    piv = [P("L", 100.0, 2, 4), P("H", 110.0, 7, 9)]
    lv = LV.Levels(res_of(m, piv))
    t_bos = next(i for i, c in enumerate(closes) if c > 110.0)
    assert any("b" in L.births and (L.born_bar == t_bos or (t_bos, "b") in L.merged_from) and L.role0 == LV.SUP for L in lv.L)


def test_self_level_valid_on_second_test():
    m, lv = _support_case([108, 102, 106, 110, 101.8, 106])
    sup = [L for L in lv.L if L.role0 == LV.SUP and abs(L.anchor - 100.0) < 1e-6][0]
    t = len(m) - 2
    assert sup.count("test", t) >= 2 and sup.alive(t)
    assert any(x["id"] == sup.id for x in lv.active(t, "UP"))                  # दुसऱ्या चाचणीलाही active


def test_levels_truncation_invariant():
    m, lv = _support_case([108, 104, 102, 105, 99, 95, 98, 103, 106])
    for k in range(12, len(m)):
        part = LV.Levels(res_of(m.iloc[:k].reset_index(drop=True), [p for p in [P("H", 116, 0, 2), P("L", 100.0, 4, 6)] if p.confirm_bar < k]))
        assert [(L.band_at(k - 1), L.born_bar, list(L.events)) for L in part.L] == \
               [(L.band_at(k - 1), L.born_bar, [e for e in L.events if e[0] < k]) for L in lv.L if L.born_bar < k]
        assert part.snapshot(k - 1) == lv.snapshot(k - 1)


def test_no_prune_far_levels_stay_in_snapshot():
    m, lv = _support_case([130 + i for i in range(30)])
    t = len(m) - 1
    assert any(x["role"] == LV.SUP for x in lv.snapshot(t))


# ------------------------------------------------------------------------------------------------ hygiene
def test_register_covers_every_default_and_no_dates_in_code():
    keys = set()
    for k in S3.REGISTER:
        keys |= {x.strip() for x in k.split("/")}
    for k in S3.DEFAULTS:
        assert k in keys, f"register मध्ये नाही: {k}"
    for v in S3.REGISTER.values():
        assert v[2] in ("Abhi नियम", "व्याख्या", "अंदाज", "setting", "अंदाज (फक्त chart)")
    for f in os.listdir(os.path.join(ROOT, "decision3")):
        if f.endswith(".py"):
            src = open(os.path.join(ROOT, "decision3", f), encoding="utf-8").read()
            assert not re.search(r"20\d\d-\d\d-\d\d", src), f


def test_two_closes_beyond_then_back_is_sweep_three_is_flip_and_failed_flip_returns():
    # support पट्टा ≈ 100–101.5
    m, lv = _support_case([105, 99, 98.5, 103, 106])                         # 2 closes खाली, परत ⇒ sweep, flip नाही
    sup = [L for L in lv.L if L.role0 == LV.SUP and abs(L.anchor - 100.0) < 1e-6][0]
    t = len(m) - 1
    assert sup.count("flip", t) == 0 and sup.count("sweep", t) >= 1 and sup.role_at(t) == LV.SUP
    m, lv = _support_case([105, 99, 98.5, 98, 97, 103, 104, 105])          # 3 closes ⇒ flip; मग 3 closes वर ⇒ flip अयशस्वी ⇒ support
    sup = [L for L in lv.L if L.role0 == LV.SUP and abs(L.anchor - 100.0) < 1e-6][0]
    flips = [e for e in sup.events if e[1] == "flip"]
    assert len(flips) == 2 and "अयशस्वी" in flips[1][2] and sup.role_at(len(m) - 1) == LV.SUP and sup.alive(len(m) - 1)
