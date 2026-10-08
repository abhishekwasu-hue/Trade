"""Chart Reader — areas: KB टप्पा 3 ची 12 साधनं (a–l) प्रत्येक signal साठी candidate; active area (K6.4); confluence (K7: मोजपट्टी फक्त
ठोस area सोबत); targets."""
import numpy as np
import pandas as pd

from chart_reader import areas as AR
from chart_reader import settings as CS

S = dict(CS.DEFAULTS)


def bars(closes, wick=1.0, tf="15min", start="2021-03-01 09:15"):
    o = [closes[0]] + list(closes[:-1])
    ts = pd.date_range(start, periods=len(closes), freq=tf)
    return pd.DataFrame({"timestamp": ts, "open": o, "high": [max(a, b) + wick for a, b in zip(o, closes)],
                         "low": [min(a, b) - wick for a, b in zip(o, closes)], "close": list(closes)})


def zig(points, step=2.0):
    out = [float(points[0])]
    for a, b in zip(points[:-1], points[1:]):
        n = max(int(round(abs(b - a) / step)), 1)
        out += list(np.linspace(a, b, n + 1)[1:])
    return out


# ------------------------------------------------------------------------------------------------ f: sloping (K6.1)
def test_trendline_candidate_always_built_with_three_pivots():
    df = bars(zig([150, 180, 150, 172, 142, 164, 140, 158]))                                  # lower highs 180 / 172 / 164 (समान अंतर)
    res = [x for x in AR.sloping(df, S, mr=3.0) if x["role"] == "RESISTANCE"]
    assert res and res[0]["tool"] == "f" and res[0]["touches"] >= 3 and res[0]["slope"] < 0 and res[0]["valid"]
    df2 = bars(zig([150, 180, 150, 160, 146, 175, 140, 158]))                                 # highs 180 / 160 / 175 — ओळीत नाहीत
    res2 = [x for x in AR.sloping(df2, S, mr=3.0) if x["role"] == "RESISTANCE"]
    assert res2 and not res2[0]["valid"]                                                      # candidate तयार, पण valid नाही (गुण नाहीत)


def test_sloping_truncation_and_real_break():
    pts = [150, 180, 150, 172, 146, 164, 140]
    df = bars(zig(pts))
    cut = AR.sloping(df.iloc[: len(df) - 3].reset_index(drop=True), S, mr=3.0)
    again = AR.sloping(df, S, mr=3.0, upto=len(df) - 4)
    assert [(x["id"], round(x["value"], 2)) for x in cut] == [(x["id"], round(x["value"], 2)) for x in again]
    br = bars(zig([150, 180, 150, 172, 146, 164, 140, 150]) + [168, 170, 171])
    res = [x for x in AR.sloping(br, S, mr=3.0) if x["role"] == "RESISTANCE"]
    assert res and res[0]["state"] == "BROKEN"


# ------------------------------------------------------------------------------------------------ all 12 tools
def _struct():
    return {"impulse": {"dir": 1, "origin": 100.0, "end": 160.0, "start_bar": 10, "end_bar": 40}, "correction": [160.0, 140.0, 150.0, 132.0],
            "side": 1}


def test_all_twelve_tools_present_as_candidates():
    df = bars(zig([150, 180, 150, 172, 146, 164, 140, 158]))
    ctx = {"pdh": 175.0, "pdl": 120.0, "pdc": 150.0, "week_high": 185.0, "week_low": 110.0, "gap_edges": [(149.0, 151.0)]}
    horiz = [{"id": "1h-L1", "low": 139.0, "high": 141.0, "state": "TESTED", "role": "SUPPORT", "quality_n": 2, "flipped": False,
              "edge": False, "degree": 2, "score": 4.0, "role_reversal": False},
             {"id": "1h-F1", "low": 129.0, "high": 131.0, "state": "FLIPPED", "role": "SUPPORT", "quality_n": 1, "flipped": True,
              "edge": False, "degree": 2, "score": 3.0, "role_reversal": True},
             {"id": "1h-E1", "low": 179.0, "high": 181.0, "state": "ACTIVE", "role": "RESISTANCE", "quality_n": 1, "flipped": False,
              "edge": True, "degree": 3, "score": 3.0, "role_reversal": False}]
    cands = AR.tools(df, horiz, _struct(), ctx, S, mr=3.0)
    got = {c["tool"] for c in cands}
    assert {"a", "b", "d", "e", "f", "g", "h", "i", "j", "k", "l"} <= got                       # c (base) displacement असेल तेव्हाच
    assert all(c["kind"] in ("solid", "ruler") for c in cands)
    assert {c["tool"] for c in cands if c["kind"] == "ruler"} <= {"g", "h", "i"}


def test_base_before_displacement_is_tool_c():
    flat = [100.0, 100.5, 100.2, 100.4, 100.1]
    disp = [104.0, 108.5, 113.0]                                                              # मोठ्या bodies, ≥ 1.5 MR
    rest = [112.0, 113.0, 112.5, 113.5]
    df = bars([100.0] * 25 + flat + disp + rest, wick=0.3)
    c = [x for x in AR.base_zones(df, S, mr=1.5) if x["tool"] == "c"]
    assert c and c[0]["role"] == "SUPPORT" and c[0]["high"] - c[0]["low"] <= 1.5 * 1.5 + 1e-9


# ------------------------------------------------------------------------------------------------ active area + confluence (K6.4, K7)
def test_fibonacci_alone_scores_zero():
    df = bars([140.0, 138.0, 136.0, 137.0, 136.5])
    cands = [{"id": "fib0.382", "tool": "h", "kind": "ruler", "low": 135.0, "high": 137.5, "role": "SUPPORT", "state": "ACTIVE", "quality": 0.5}]
    a = AR.active(df, cands, side=1, s=S, mr=3.0)
    assert a["area"] is None and a["quality"] == 0.0 and a["confluence_extra"] == 0


def test_ruler_counts_only_with_solid_area_and_intersection_bonus():
    df = bars([140.0, 138.0, 136.0, 137.0, 136.5])
    cands = [{"id": "1h-L1", "tool": "a", "kind": "solid", "low": 135.0, "high": 137.0, "role": "SUPPORT", "state": "TESTED", "quality": 0.8},
             {"id": "TL-S1", "tool": "f", "kind": "solid", "low": 135.5, "high": 136.7, "role": "SUPPORT", "state": "TESTED", "quality": 0.8,
              "valid": True},
             {"id": "fib0.618", "tool": "h", "kind": "ruler", "low": 135.8, "high": 137.3, "role": "SUPPORT", "state": "ACTIVE", "quality": 0.5},
             {"id": "C=A", "tool": "i", "kind": "ruler", "low": 136.0, "high": 136.9, "role": "SUPPORT", "state": "ACTIVE", "quality": 0.5},
             {"id": "far", "tool": "j", "kind": "solid", "low": 120.0, "high": 121.0, "role": "SUPPORT", "state": "ACTIVE", "quality": 0.3}]
    a = AR.active(df, cands, side=1, s=S, mr=3.0)
    assert a["area"]["id"] in ("1h-L1", "TL-S1") and a["quality"] == 1.0                     # horizontal ∩ sloping ⇒ सर्वोच्च (K6.4)
    assert set(a["confluence"]) >= {"h", "i"} and a["confluence_extra"] >= 3


def test_no_active_area_when_recent_bars_far_and_targets():
    cands = [{"id": "1h-L1", "tool": "a", "kind": "solid", "low": 99.0, "high": 101.0, "role": "SUPPORT", "state": "TESTED", "quality": 0.8},
             {"id": "1h-H1", "tool": "a", "kind": "solid", "low": 119.0, "high": 121.0, "role": "RESISTANCE", "state": "ACTIVE", "quality": 0.8},
             {"id": "fibX", "tool": "h", "kind": "ruler", "low": 109.0, "high": 110.0, "role": "RESISTANCE", "state": "ACTIVE", "quality": 0.5},
             {"id": "1h-H2", "tool": "d", "kind": "solid", "low": 129.0, "high": 131.0, "role": "RESISTANCE", "state": "ACTIVE", "quality": 0.6}]
    assert AR.active(bars([115, 116, 117, 118]), cands, side=1, s=S, mr=3.0)["area"] is None
    tg = AR.targets(cands, side=1, entry=102.5)
    assert [t[1] for t in tg][:2] == ["1h-H1", "1h-H2"]                                      # मोजपट्टी target नाही


def test_targets_are_impulse_end_then_htf_solid_beyond_and_internal_pools_are_obstacles():
    """KB टप्पा 7: target = impulse चं टोक, मग त्यापलीकडचा ठोस (a/b/c/d/k) area. Correction च्या आतले लहान pools (e swing / equal,
    j round, l gap edge, PDC) target नाहीत — फक्त obstacles (R:R ला अर्थ राहावा)."""
    cands = [{"id": "SWH-1", "tool": "e", "kind": "solid", "low": 104.0, "high": 104.4, "role": "RESISTANCE", "state": "ACTIVE"},
             {"id": "RN110", "tool": "j", "kind": "solid", "low": 109.8, "high": 110.2, "role": "RESISTANCE", "state": "ACTIVE"},
             {"id": "PDH", "tool": "k", "kind": "solid", "low": 129.8, "high": 130.2, "role": "RESISTANCE", "state": "ACTIVE"},
             {"id": "1h-H1", "tool": "a", "kind": "solid", "low": 112.0, "high": 114.0, "role": "RESISTANCE", "state": "ACTIVE"}]
    tg, obst = AR.trade_targets(cands, side=1, entry=102.5, impulse_end=120.0)
    assert [t[1] for t in tg] == ["IMPULSE-END", "PDH"]                                      # 1h-H1 impulse टोकाच्या आत ⇒ obstacle
    assert [o[1] for o in obst] == ["SWH-1", "RN110", "1h-H1"]
    tg, _ = AR.trade_targets(cands, side=1, entry=102.5, impulse_end=None)
    assert tg[0][1] == "1h-H1"                                                               # impulse नाही ⇒ पुढचा ठोस HTF area
