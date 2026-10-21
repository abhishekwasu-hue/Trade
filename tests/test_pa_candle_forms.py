"""PA standard §2G — decision3/candle_forms.py (synthetic: forms in both directions, only at a location, reuse of method readers)."""
import numpy as np

from decision3 import candle_forms as CF
from decision3 import method as M

UP, DOWN = 1, -1
DEMAND = {"kind": "area", "id": 1, "tf": "1H", "role": "support", "lo": 95.0, "hi": 100.0}
SUPPLY = {"kind": "area", "id": 2, "tf": "1H", "role": "resistance", "lo": 120.0, "hi": 125.0}
FAR = {"kind": "area", "id": 3, "tf": "1H", "role": "support", "lo": 10.0, "hi": 12.0}


def frame(rows):
    a = np.array(rows, float)
    return {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}


def names(r):
    return [f["name"] for f in r["forms"]]


def test_bullish_engulfing_at_demand_is_with_and_bearish_is_against():
    A = frame([(105, 106, 103, 104), (103, 103.5, 99, 100), (99.5, 104, 98, 103.5)])   # red, then green covering it, at demand
    r = CF.forms_at(A, 2, [DEMAND])
    eng = [f for f in r["forms"] if f["form"] == "engulf"]
    assert eng and eng[0]["dir"] == UP and eng[0]["name"] == "bullish engulfing"
    assert eng[0]["at"][0]["relation"] == "with"
    assert "bullish engulfing at a location — with: demand 95–100 (1H)" in r["evidence"]
    B = frame([(99, 101, 98, 100.5), (100.4, 101.5, 99, 101), (101.2, 101.6, 96, 98.5)])   # green, then red covering it, at demand
    rb = CF.forms_at(B, 2, [DEMAND, SUPPLY], d=UP)
    assert "bearish engulfing at a location — against: demand 95–100 (1H) (against the trade)" in rb["evidence"]
    e2 = [f for f in rb["forms"] if f["form"] == "engulf"]
    assert e2 and e2[0]["dir"] == DOWN and e2[0]["at"][0]["relation"] == "against" and e2[0]["trade"] == "against"


def test_form_off_location_is_not_evidence():
    A = frame([(105, 106, 103, 104), (103, 103.5, 99, 100), (99.5, 104, 98, 103.5)])
    r = CF.forms_at(A, 2, [FAR])
    assert not r["forms"] and not r["evidence"]
    assert "bullish engulfing" in r["off_location"]


def test_rejection_both_directions_reuses_method_pin():
    A = frame([(100, 101, 99, 100.5), (100, 100.6, 95, 100.4)])            # long lower wick at demand
    r = CF.forms_at(A, 1, [DEMAND])
    assert "bullish rejection (long lower wick)" in names(r)
    assert M._one_candle_form(A, 1, UP) == "pin"
    B = frame([(121, 122, 120, 121), (121, 126, 120.5, 120.8)])            # long upper wick at supply
    rb = CF.forms_at(B, 1, [SUPPLY])
    f = [x for x in rb["forms"] if x["form"] == "rejection"][0]
    assert f["dir"] == DOWN and f["at"][0]["relation"] == "with"


def test_morning_and_evening_star():
    A = frame([(106, 106.5, 99.5, 100), (99.8, 100.4, 99, 100.1), (100.2, 104, 100, 103.8)])   # strong red, small, back up
    r = CF.forms_at(A, 2, [DEMAND])
    assert "morning star" in names(r)
    B = frame([(119, 125.5, 118.8, 125), (125.1, 125.6, 124.5, 124.9), (124.8, 125, 120, 120.5)])
    rb = CF.forms_at(B, 2, [SUPPLY])
    assert "evening star" in names(rb)
    st = [x for x in rb["forms"] if x["form"] == "star"][0]
    assert st["bars"] == [0, 2] and st["n"] == 3


def test_tweezer_bottom_and_top():
    A = frame([(103, 103.5, 101, 102), (102, 102.5, 97, 98), (98.2, 100, 97, 98.6)])     # same low, t does not engulf
    r = CF.forms_at(A, 2, [DEMAND])
    assert "tweezer bottom" in names(r)
    B = frame([(121, 122, 120.5, 121.5), (121.5, 124, 121, 123.5), (123.2, 124, 122.5, 123)])
    rb = CF.forms_at(B, 2, [SUPPLY])
    assert "tweezer top" in names(rb)


def test_doji_and_inside_bar_are_neutral_states():
    A = frame([(100, 104, 96, 101), (100, 101.5, 98.5, 100.1)])            # inside the previous candle, and a doji
    r = CF.forms_at(A, 1, [DEMAND])
    st = {x["form"] for x in r["states"]}
    assert st == {"doji", "inside_bar"}
    assert all(x["at"][0]["relation"] == "neutral" for x in r["states"])
    assert "indecision (doji) at a location — indecision: demand 95–100 (1H)" in r["evidence"]


def test_momentum_needs_a_large_body_vs_neighbours():
    rows = [(100, 101, 99, 100.5)] * 4 + [(100, 106, 99.8, 105.8)]       # strong close, body far above the neighbours'
    A = frame(rows)
    r = CF.forms_at(A, 4, [DEMAND], ctx=0)
    assert "bullish momentum candle" in names(r)
    r0 = CF.forms_at(A, 4, [DEMAND], ctx=None)                              # no neighbours ⇒ not read (NA), never assumed
    assert "bullish momentum candle" not in names(r0) and r0["na"]
    rows2 = [(100, 109, 99, 108)] * 4 + [(100, 106, 99.8, 105.8)]         # same candle, neighbours larger ⇒ no momentum
    assert "bullish momentum candle" not in names(CF.forms_at(frame(rows2), 4, [DEMAND], ctx=0))


def test_line_location():
    line = {"kind": "line", "id": "l", "role": "support", "p1": [0, 90.0], "slope": 2.0}   # value 98 at bar 4
    A = frame([(110, 111, 109, 110)] * 4 + [(99, 100, 97, 99.8)])
    assert CF.touches(line, 97, 100, 4, 4)
    assert not CF.touches(line, 99, 100, 4, 4)
    r = CF.forms_at(A, 4, [line])
    assert r["forms"] or r["states"]
    assert all("rising support line" in e for e in r["evidence"])


def test_no_lookahead_and_settings_do_not_switch_to_ratios():
    rng = np.random.default_rng(3)
    c = 100 + np.cumsum(rng.normal(0, 1, 60))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 1, 60)
    lo = np.minimum(o, c) - rng.uniform(0, 1, 60)
    A = {"open": o, "high": h, "low": lo, "close": c}
    wide = {"kind": "area", "role": "support", "lo": -1e9, "hi": 1e9}
    for j in range(2, 60):
        cut = {k: v[:j + 1] for k, v in A.items()}
        full = CF.forms_at(A, j, [wide], ctx=j - 5)
        part = CF.forms_at(cut, j, [wide], ctx=j - 5, s={"candle_rule": "ratio"})
        assert names(full) == names(part) and [x["form"] for x in full["states"]] == [x["form"] for x in part["states"]]


def test_draw_objects_shape():
    A = frame([(105, 106, 103, 104), (103, 103.5, 99, 100), (99.5, 104, 98, 103.5)])
    r = CF.forms_at(A, 2, [DEMAND])
    r.update(tf="15M", _frame={"A": A, "ts": ["a", "b", "c"]})
    objs = CF.draw_objects(r)
    assert objs and set(objs[0]) == {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}
    eng = [o for o in objs if o["label"] == "bullish engulfing"][0]
    assert eng["t0"] == "b" and eng["t1"] == "c" and eng["p0"] == 98 and eng["p1"] == 104


# ------------------------------------------------------------------------------------------------ on a V22 state (synthetic fixture)
def _v22(m15):
    import pandas as pd
    from decision3 import engine as E3
    ts5 = pd.date_range(m15["timestamp"].min(), m15["bar_end"].max(), freq="5min")
    fut = pd.DataFrame({"timestamp": ts5, "volume": np.arange(len(ts5)) % 7 * 10.0 + 100.0, "contract": "FUT",
                        "expiry": pd.Timestamp(m15["timestamp"].max()).normalize() + pd.Timedelta(days=30)})
    return E3.V22(m15, s={"ltf_choch": False}, futures=fut)


def test_v22_reads_only_at_locations_and_truncation_safe():
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    V = _v22(m15)
    hits = []
    for t in range(len(m15)):
        for tf in ("15M", "1H"):
            r = CF.read_candle_forms(V, t, tf=tf)
            assert all(f["at"] for f in r["forms"] + r["states"])
            assert all(o["kind"] == "candle_form" for o in CF.draw_objects(r))
            if tf == "15M" and r["forms"]:
                hits.append(t)
    assert hits                                                            # not vacuous
    for t in hits[:: max(1, len(hits) // 4)][:4]:
        Vt = _v22(m15.iloc[:t + 1].reset_index(drop=True))
        for tf in ("15M", "1H"):
            a, b = CF.public(CF.read_candle_forms(V, t, tf=tf)), CF.public(CF.read_candle_forms(Vt, t, tf=tf))
            assert a == b
