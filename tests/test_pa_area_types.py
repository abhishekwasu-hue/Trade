"""PA standard §2C (track T2): base types RBD / DBR / RBR / DBD + departure strength / structure break (decision3/area_types.py)."""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd

from decision3 import area_types as AT
from decision3 import levels as LV
from decision3 import pa_frames as PF
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

SCHEMA = {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}


def frame(closes, wick=0.3, fine=(), ext=(), vol=None):
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    h, lo = np.maximum(o, c) + wick, np.minimum(o, c) - wick
    ts = list(pd.date_range("2030-01-07 09:15", periods=len(c), freq="15min"))
    return PF.Frame("15M", o, h, lo, c, None if vol is None else np.asarray(vol, float), ts, len(c) - 1, list(fine), list(ext))


def V_of(m, piv2, piv1=()):
    res = res_of(m, piv2, piv1)
    return NS(levels=LV.Levels(res), s=S3.load(), res=res)


# ------------------------------------------------------------------------------------------------ base type (C.1)
def _demand_case(rally):
    closes = [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100.5, 103] + rally
    m = m15_from(closes, lows={10: 100.0}, highs={0: 121.0})
    return m, V_of(m, [P("H", 121, 0, 2), P("L", 100.0, 10, 12)])


def test_swing_low_demand_is_drop_base_rally():
    m, V = _demand_case([107, 111, 115, 119, 123])
    t = len(m) - 1
    x = [a for a in AT.read_area_types(V, t) if a["births"][0] == "a:D2" and a["role"] == LV.SUP][0]
    assert x["base"]["type"] == "DBR" and x["base"]["family"] == AT.REVERSAL and x["base"]["consistent_with_role"]
    assert "drop-base-rally" in x["evidence"]


def test_swing_high_supply_is_rally_base_drop():
    closes = [80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 99.5, 97, 93, 89, 85, 81]
    m = m15_from(closes, highs={10: 100.0}, lows={0: 79.0})
    V = V_of(m, [P("L", 79, 0, 2), P("H", 100.0, 10, 12)])
    x = [a for a in AT.read_area_types(V, len(m) - 1) if a["births"][0] == "a:D2" and a["role"] == LV.RES][0]
    assert x["base"]["type"] == "RBD" and x["base"]["family"] == AT.REVERSAL and x["base"]["consistent_with_role"]


def test_continuation_bases_rbr_and_dbd():
    up = [100, 102, 104, 106, 108, 110, 110.5, 110, 110.6, 113, 116, 119, 122]
    F = frame(up)
    base, _ = AT.read_base(F, 109.8, 111.0, 7, 7)
    assert base["type"] == "RBR" and base["family"] == AT.CONTINUATION
    F = frame([220 - x for x in up])
    base, _ = AT.read_base(F, 220 - 111.0, 220 - 109.8, 7, 7)
    assert base["type"] == "DBD" and base["family"] == AT.CONTINUATION


def test_still_inside_the_base_has_no_out_leg():
    F = frame([100, 102, 104, 106, 108, 110, 110.5, 110, 110.6, 110.2])
    base, dep = AT.read_base(F, 109.8, 111.0, 7, 7)
    assert base["type"] is None and base["type_partial"] == "RB?" and dep["strength"] is None


# ------------------------------------------------------------------------------------------------ departure (C.5)
def test_departure_stronger_and_weaker_than_the_approach():
    m, V = _demand_case([107, 111, 115, 119, 123])                            # leaves faster / bigger bodies than it came in
    x = [a for a in AT.read_area_types(V, len(m) - 1) if a["births"][0] == "a:D2" and a["role"] == LV.SUP][0]
    assert x["departure"]["strength"] == "strong" and x["departure"]["vs_approach"]["verdict"] == "stronger"
    m, V = _demand_case([103.5, 104, 104.5, 105, 105.5, 106, 106.5, 107])    # crawls out
    x = [a for a in AT.read_area_types(V, len(m) - 1) if a["births"][0] == "a:D2" and a["role"] == LV.SUP][0]
    assert x["departure"]["strength"] == "weak"


def test_departure_volume_is_compared_when_known():
    up = [110, 108, 106, 104, 102, 100.6, 101, 104, 108, 112, 116]
    vol = [100] * 6 + [100, 300, 300, 300, 300]
    F = frame(up, fine=[NS(kind="H", price=110.3, bar=0, confirm_bar=2)], vol=vol)
    _, dep = AT.read_base(F, 100.3, 101.2, 5, 5)
    assert dep["vs_approach"]["measures"]["volume"] == "a"
    _, dep0 = AT.read_base(frame(up, fine=[NS(kind="H", price=110.3, bar=0, confirm_bar=2)]), 100.3, 101.2, 5, 5)
    assert dep0["vs_approach"]["measures"]["volume"] is None                  # no FUT volume ⇒ the measure is absent, not guessed


def test_departure_broke_structure_only_when_it_closed_beyond_the_swing():
    m, V = _demand_case([107, 111, 115, 119, 123])                            # closes above the D2 H 121
    x = [a for a in AT.read_area_types(V, len(m) - 1) if a["births"][0] == "a:D2" and a["role"] == LV.SUP][0]
    assert x["departure"]["bos"] is not None and x["departure"]["bos"]["swing"] == 121.0
    m, V = _demand_case([107, 111, 115, 117, 116])                            # stops below it
    x = [a for a in AT.read_area_types(V, len(m) - 1) if a["births"][0] == "a:D2" and a["role"] == LV.SUP][0]
    assert x["departure"]["bos"] is None and "did not break structure" in x["evidence"]


def test_departure_lists_the_imbalance_it_left():
    c = [110, 108, 106, 104, 102, 100.6, 101, 106, 112, 113, 114]
    F = frame(c, wick=0.2, fine=[NS(kind="H", price=110.2, bar=0, confirm_bar=2)])
    _, dep = AT.read_base(F, 100.3, 101.2, 5, 5)
    assert dep["fvg"] and all(g["dir"] == 1 for g in dep["fvg"])


# ------------------------------------------------------------------------------------------------ hygiene
def test_no_lookahead_and_levels_untouched():
    closes = [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100.5, 103, 107, 111, 115, 112, 109, 113, 118, 124]
    piv2 = [P("H", 121, 0, 2), P("L", 100.0, 10, 12), P("H", 116, 14, 16)]
    m = m15_from(closes, lows={10: 100.0}, highs={0: 121.0, 14: 116.0})
    V = V_of(m, piv2)
    before = V.levels.snapshot(len(m) - 1)
    for t in (13, 16, 19):
        full = AT.read_area_types(V, t)
        mt = m.iloc[:t + 1].reset_index(drop=True)
        Vt = V_of(mt, [p for p in piv2 if p.confirm_bar <= t])
        assert full == AT.read_area_types(Vt, t)
    assert V.levels.snapshot(len(m) - 1) == before


def test_draw_objects_schema():
    m, V = _demand_case([107, 111, 115, 119, 123])
    objs = AT.draw_objects(V, len(m) - 1)
    assert objs and all(set(o) == SCHEMA for o in objs) and all(o["kind"] == "area_base" for o in objs)
