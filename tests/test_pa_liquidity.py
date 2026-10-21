"""PA standard §2D (track T2): obvious swing extremes + inducement (decision3/liquidity_pa.py)."""
from types import SimpleNamespace as NS

from decision3 import levels as LV
from decision3 import liquidity_pa as LP
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

SCHEMA = {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}


def V_of(m, piv2, piv1=()):
    res = res_of(m, piv2, piv1)
    return NS(levels=LV.Levels(res), s=S3.load(), res=res)


# ------------------------------------------------------------------------------------------------ obvious extremes (D.2)
def _obvious_case():
    closes = [110, 113, 116, 118, 119, 120, 117, 114, 111, 108, 105, 108, 111, 113, 114.5, 115, 113, 111, 109, 108.5, 108, 110, 112,
              111, 110]
    m = m15_from(closes, highs={5: 121.0, 15: 116.0, 22: 117.0}, lows={10: 104.0, 20: 107.0})
    piv = [P("H", 121, 5, 7), P("L", 104, 10, 12), P("H", 116, 15, 17), P("L", 107, 20, 22)]
    return m, V_of(m, piv)


def test_untaken_swing_extremes_rest_and_outer_nearest_are_marked():
    m, V = _obvious_case()
    xs = {x["price"]: x for x in LP.obvious_extremes(V, 21) if x["side"] == "buy"}
    assert set(xs) == {121.0, 116.0}
    assert xs[121.0]["outer"] and not xs[121.0]["nearest"] and xs[116.0]["nearest"]
    assert all(x["state"] == "resting" for x in xs.values())


def test_a_taken_extreme_no_longer_rests_and_says_how_it_was_taken():
    m, V = _obvious_case()
    t = len(m) - 1
    rest = {x["price"] for x in LP.obvious_extremes(V, t) if x["side"] == "buy"}
    assert rest == {121.0}                                                     # 116 traded beyond at bar 22
    taken = [x for x in LP.obvious_extremes(V, t, include_taken=True) if x["price"] == 116.0][0]
    assert taken["state"] == "taken" and taken["taken_by"] == "wick" and taken["taken_bar"] == 22   # closed back below


def test_equal_highs_are_tagged():
    closes = [110, 113, 116, 118, 119, 120, 117, 114, 111, 108, 105, 108, 111, 114, 117, 120.2, 117, 114]
    m = m15_from(closes, highs={5: 121.0, 15: 120.6, 16: 120.3})
    V = V_of(m, [P("H", 121, 5, 7), P("L", 104, 10, 12), P("H", 120.6, 15, 17)])
    xs = [x for x in LP.obvious_extremes(V, len(m) - 1) if x["side"] == "buy"]
    assert {x["src"] for x in xs} == {"equal"}


# ------------------------------------------------------------------------------------------------ inducement (D.5)
def _induce_case():
    closes = [110, 112, 114, 116, 118, 120, 117, 114, 111, 108, 105, 102, 100.5, 103, 106, 109, 110.5, 108, 106, 105.5, 108, 110, 112,
              115, 118, 120]
    m = m15_from(closes, highs={5: 121.0, 16: 111.0, 17: 110.8}, lows={12: 100.0})
    piv2 = [P("H", 121, 5, 7), P("L", 100, 12, 14)]
    piv1 = piv2 + [P("H", 111, 16, 18), P("L", 105, 19, 21)]
    return m, V_of(m, piv2, sorted(piv1, key=lambda p: p.bar))


def _supply(V, t):
    return [a for a in V.levels.snapshot(t) if a["role"] == LV.RES and a["births"][0] == "a:D2"][0]


def test_inducement_none_then_resting_then_taken_first():
    m, V = _induce_case()
    x = LP.inducement(V, 17, _supply(V, 17))
    assert x["state"] == "none"                                               # the minor high is not confirmed yet
    x = LP.inducement(V, 20, _supply(V, 20))
    assert x["state"] == "resting" and x["minor"]["price"] == 111.0 and x["minor"]["degree"] == "minor"
    t = len(m) - 1
    x = LP.inducement(V, t, _supply(V, t))
    assert x["state"] == "taken" and x["taken_by"] == "close" and x["taken_bar"] == 22
    assert x["area_reached"] and x["taken_first"]
    r = LP.read_liquidity(V, t)
    assert any("inducement taken first" in i["evidence"] for i in r["inducement"])


def test_inducement_no_lookahead():
    m, V = _induce_case()
    piv2 = [P("H", 121, 5, 7), P("L", 100, 12, 14)]
    piv1 = sorted(piv2 + [P("H", 111, 16, 18), P("L", 105, 19, 21)], key=lambda p: p.bar)
    for t in (18, 21, 23):
        mt = m.iloc[:t + 1].reset_index(drop=True)
        Vt = V_of(mt, [p for p in piv2 if p.confirm_bar <= t], [p for p in piv1 if p.confirm_bar <= t])
        assert LP.read_liquidity(V, t) == LP.read_liquidity(Vt, t)


def test_draw_objects_schema():
    m, V = _induce_case()
    objs = LP.draw_objects(V, len(m) - 1)
    assert objs and all(set(o) == SCHEMA for o in objs)
    assert {"liquidity_extreme", "inducement"} <= {o["kind"] for o in objs}
