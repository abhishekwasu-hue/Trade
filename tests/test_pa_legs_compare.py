"""PA standard §2B (track t1): decision3/legs_compare.py — impulse vs correction by comparison with the neighbouring legs, and the
correction form (zigzag / flat / triangle / channel) as evidence only. Synthetic data only."""
import inspect

import numpy as np
import pytest

from decision3 import legs_compare as LC
from decision3 import mtf_state as MS


def frame(rows, vol=None):
    o, h, l, c = (np.array([r[k] for r in rows], float) for k in range(4))
    return {"o": o, "h": h, "l": l, "c": c, "v": None if vol is None else np.array(vol, float)}


def impulse_bars(p0, n, step, d):
    """n bars, each a full body of `step` in direction d, no overlap with the previous bar."""
    out, x = [], p0
    for _ in range(n):
        y = x + d * step
        out.append((x, max(x, y), min(x, y), y))
        x = y
    return out


def chop_bars(p0, n, step, d):
    """n small, overlapping bars drifting by step / 4 per bar in direction d."""
    out, x = [], p0
    for k in range(n):
        y = x + d * step / 4
        o, c = (x + d * step / 8, y) if k % 2 else (y, x + d * step / 8)
        out.append((o, max(x, y) + step, min(x, y) - step, c))
        x = y
    return out


def test_leg_facts_measures():
    F = frame([(100, 100, 100, 100)] + impulse_bars(100, 4, 10, 1), vol=[1, 5, 5, 5, 5])
    f = LC.leg_facts(F, 0, 4, 1)
    assert f["bars"] == 4 and f["body"] == pytest.approx(10.0) and f["overlap"] == pytest.approx(0.0) and f["volume"] == 5
    G = frame([(100, 100, 100, 100)] + impulse_bars(100, 4, 10, 1), vol=[1, 5, np.nan, 5, 5])
    assert LC.leg_facts(G, 0, 4, 1)["volume"] is None and "no volume" in LC.leg_facts(G, 0, 4, 1)["volume_na"]
    assert LC.leg_facts(frame([(1, 1, 1, 1)]), 0, 0, 1) is None


def test_compare_impulse_correction_mixed_na():
    bars = [(100, 100, 100, 100)] + chop_bars(100, 8, 8, -1) + impulse_bars(84, 4, 10, 1) + chop_bars(124, 8, 8, -1)
    vol = [1] + [2] * 8 + [6] * 4 + [2] * 8
    F = frame(bars, vol)
    a, b, c = LC.leg_facts(F, 0, 8, -1), LC.leg_facts(F, 8, 12, 1), LC.leg_facts(F, 12, 20, -1)
    r = LC.compare(b, [a, c])
    assert r["verdict"] == LC.IMPULSE and r["clear"]
    assert "larger bodies" in r["why"] and "little overlap" in r["why"] and "expanding volume" in r["why"]
    r2 = LC.compare(c, [b])
    assert r2["verdict"] == LC.CORRECTION and "overlapping candles" in r2["why"] and "lower volume" in r2["why"]
    big_body_low_vol = dict(b, volume=1.0)                         # price says impulse, volume against ⇒ still the majority
    assert LC.compare(big_body_low_vol, [a, c])["verdict"] == LC.IMPULSE
    split = dict(b, volume=None, overlap=c["overlap"] * 2)         # bodies larger but more overlap, no volume ⇒ mixed
    assert LC.compare(split, [a, c])["verdict"] == LC.MIXED
    assert LC.compare(b, [])["verdict"] == LC.NA


def test_correction_forms():
    # corrections in an uptrend (counter direction −1): start = the high
    assert LC.correction_form([100], -1)["form"] is None
    assert LC.correction_form([100, 90], -1)["form"] == "one leg (A)"
    assert LC.correction_form([100, 90, 96], -1)["why"] == "B short of A's start"
    assert LC.correction_form([100, 90, 96, 85], -1)["form"] == "zigzag (ABC)"
    assert LC.correction_form([100, 90, 100.5, 89], -1)["form"] == "flat"
    assert LC.correction_form([100, 90, 99, 89], -1, start_edge=98.5)["form"] == "flat"      # B reached the start candle's area
    assert LC.correction_form([100, 90, 98, 89], -1, start_edge=98.5)["form"] == "zigzag (ABC)"
    assert LC.correction_form([100, 90, 98, 92, 96, 93], -1)["form"] == "triangle (contracting)"
    assert LC.correction_form([100, 90, 102, 88, 104, 86], -1)["form"] == "triangle (expanding)"
    assert LC.correction_form([100, 92, 97, 88, 93, 84], -1)["form"] == "channel"
    assert LC.correction_form([100, 92, 97, 94, 99, 84], -1)["form"] == "complex"
    # mirror: a correction up inside a downtrend
    assert LC.correction_form([100, 110, 104, 115], 1)["form"] == "zigzag (ABC)"
    assert LC.correction_form([100, 108, 103, 112, 107, 116], 1)["form"] == "channel"


def test_legs_of_complete_and_running():
    ext = [MS.SP("L", 100, 0, None, 1), MS.SP("H", 130, 5, None, 7), MS.SP("L", 110, 9, None, 11)]
    legs = LC.legs_of(ext, 14)
    assert [(g["dir"], g["complete"]) for g in legs] == [(1, True), (-1, True), (1, False)]
    assert legs[-1]["i0"] == 9 and legs[-1]["i1"] == 13


def test_module_uses_no_percentile_numbers():
    """legs2.settings2 percentiles (c_hi / c_lo / baseline_legs) are not reused: no legs2 / patterns2 import, no such name in the code."""
    import ast
    tree = ast.parse(inspect.getsource(LC))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
        {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(m.startswith(("legs2", "patterns2")) for m in mods)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
        {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 20}
    assert not names & {"c_hi", "c_lo", "baseline_legs", "baseline_min", "pct_rank", "c_class"}


# ------------------------------------------------------------------------------------------------ synthetic V22 (integration)
@pytest.fixture(scope="module")
def V():
    from decision3 import engine as E3
    from tests.test_pa_mtf_state import _ltf, _m15, synthetic_closes
    m = _m15(synthetic_closes())
    return E3.V22(m, ltf=_ltf(m))


def test_read_legs_on_synthetic_trend(V):
    """Fast up legs, slow down legs ⇒ on the swing timeframes the complete up legs read impulse, the down legs correction."""
    t = len(V.m15) - 1
    r = LC.read_legs_compare(V, t)
    assert set(r["tfs"]) == set(MS.TFS) and r["evidence_only"]
    for tf in ("15M", "5M"):
        x = r["tfs"][tf]
        assert x["legs"], tf
        done = [g for g in x["legs"] if g["complete"] and g["verdict"] != LC.NA]
        assert done and all(g["verdict"] == (LC.IMPULSE if g["dir"] == "up" else LC.CORRECTION) for g in done), (tf, done)
        assert x["volume"].startswith("NA")
        assert x["last_correction"] is not None and x["last_correction"]["form"]
    objs = LC.draw_objects(V, t, read=r)
    keys = {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}
    assert objs and all(set(o) == keys for o in objs) and {"leg", "correction_form"} <= {o["kind"] for o in objs}
    assert LC.evidence(r)


def test_legs_no_look_ahead(V):
    from decision3 import engine as E3
    from tests.test_pa_mtf_state import _ltf
    t = len(V.m15) - 40
    cut = V.m15.iloc[:t + 1].reset_index(drop=True)
    V2 = E3.V22(cut, ltf=_ltf(cut))
    a, b = LC.read_legs_compare(V, t, tfs=("1H", "15M", "5M")), LC.read_legs_compare(V2, t, tfs=("1H", "15M", "5M"))
    assert a == b


def test_fut_volume_path_15m_and_1h():
    """With FUT volume (levels.A volume_raw): the 15M / 1H legs read volume per bar; a 15M bar without volume makes the 1H candle
    and the leg holding it NA (never under-counted)."""
    from decision3 import engine as E3
    from tests.test_pa_mtf_state import _ltf, _m15, synthetic_closes
    m = _m15(synthetic_closes())
    W = E3.V22(m, ltf=_ltf(m))
    c = m["close"].to_numpy(float)
    vol = np.where(np.r_[0.0, np.diff(c)] > 0, 300.0, 100.0)               # up bars heavier
    vol[len(vol) - 5] = np.nan                                             # inside the last closed 1H candle
    W.levels.A["volume_raw"] = vol
    t = len(m) - 1
    r = LC.read_legs_compare(W, t, tfs=("15M", "1H"))
    for tf in ("15M", "1H"):
        x = r["tfs"][tf]
        assert x["volume"].startswith("FUT"), tf
        done = [g for g in x["legs"] if g["complete"]]
        assert all(g["measures"]["volume"] in (LC.IMPULSE, LC.CORRECTION, "between") for g in done), tf
        run = x["legs"][-1]
        assert not run["complete"] and run["facts"]["volume"] is None and run["measures"]["volume"] is None
    up = [g for g in r["tfs"]["15M"]["legs"] if g["complete"] and g["dir"] == "up"]
    assert up and all(g["measures"]["volume"] == LC.IMPULSE for g in up)
