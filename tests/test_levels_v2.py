"""Levels v2 (L1–L8, TRADE_LEVEL_ENGINE_V2_PROMPT §6): lifecycle, selection, degree lookback, no-lookahead."""
import numpy as np
import pandas as pd

from price_action import levels_v2 as LV

S = dict(LV.DEFAULTS)


def bars(rows, start="2021-02-01 09:15", tf="60min"):
    ts = pd.date_range(start, periods=len(rows), freq=tf)
    return pd.DataFrame({"timestamp": ts, "open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                         "close": [r[3] for r in rows]})


FLAT = (105.0, 107.0, 103.0, 105.0)                                  # range 4 ⇒ MR 4


def life(rows, zone=(99.0, 101.0), role="SUPPORT"):
    f = bars([FLAT] * 25 + rows)
    return LV.lifecycle(f, zone, role, 25, 4.0, S)


# ------------------------------------------------------------------------------------------------ L3 lifecycle
def test_wick_beyond_is_only_tested():
    st = life([(103, 104, 97, 102.5)])                               # wick 97 < zone, close परत वर
    assert st["state"] == "TESTED" and st["tests"] == 1 and st["role"] == "SUPPORT"


def test_displacement_close_is_broken_and_role_flips_on_retest_rejection():
    st = life([(102, 102.5, 92, 93), (93, 94, 90, 91)])             # buffer पलीकडे close, पुढचा bar reclaim नाही ⇒ BROKEN
    assert st["state"] == "BROKEN" and st["role"] == "RESISTANCE"
    st = life([(102, 102.5, 92, 93), (93, 94, 90, 91), (91, 100.5, 90.5, 96), (96, 97, 92, 93)])   # खालून retest, नकार ⇒ FLIPPED
    assert st["state"] == "FLIPPED" and st["role"] == "RESISTANCE"


def test_close_beyond_then_reclaim_is_not_broken():
    st = life([(102, 102.5, 96, 97), (97, 103, 96.5, 102.5)])       # पुढच्या bar ने reclaim ⇒ false break ⇒ TESTED
    assert st["state"] == "TESTED"


def test_chop_is_magnet():
    rows = []
    for k in range(6):                                                # आरपार closes, वारंवार
        rows += [(100, 104, 96, 103), (103, 104, 96, 97)]
    assert life(rows)["state"] == "MAGNET"


# ------------------------------------------------------------------------------------------------ L6 selection
def test_selection_per_side_and_total_and_reason():
    cands = [{"id": f"S{i}", "low": 100.0 - 10 * i, "high": 101.0 - 10 * i, "state": "ACTIVE", "quality_n": 3 - (i % 2), "score": 5 - i,
              "role": "SUPPORT", "edge": False, "flipped": False} for i in range(4)]
    cands += [{"id": f"R{i}", "low": 120.0 + 10 * i, "high": 121.0 + 10 * i, "state": "TESTED", "quality_n": 2, "score": 4 - i,
               "role": "RESISTANCE", "edge": False, "flipped": False} for i in range(4)]
    cands += [{"id": "M", "low": 110.0, "high": 111.0, "state": "MAGNET", "quality_n": 5, "score": 0, "role": "RESISTANCE", "edge": False,
               "flipped": False}]
    sel = LV.select(cands, price=112.0, tol=1.0, s=S)
    assert len(sel) <= 4 and sum(z["side"] == "below" for z in sel) <= 2 and sum(z["side"] == "above" for z in sel) <= 2
    assert all(z["reason"] for z in sel) and "M" not in [z["id"] for z in sel]


def test_flipped_beats_active():
    cands = [{"id": "A", "low": 100.0, "high": 101.0, "state": "ACTIVE", "quality_n": 3, "score": 9, "role": "SUPPORT", "edge": False,
              "flipped": False},
             {"id": "F", "low": 104.0, "high": 105.0, "state": "FLIPPED", "quality_n": 1, "score": 2, "role": "SUPPORT", "edge": False,
              "flipped": True},
             {"id": "B", "low": 90.0, "high": 91.0, "state": "ACTIVE", "quality_n": 2, "score": 5, "role": "SUPPORT", "edge": False,
              "flipped": False}]
    sel = LV.select(cands, price=110.0, tol=1.0, s=S)
    assert [z["id"] for z in sel][:1] == ["F"]


# ------------------------------------------------------------------------------------------------ build: degree lookback, invariance
def _waves(n_weeks=10, seed=3):
    rng = np.random.default_rng(seed)
    hrs = n_weeks * 5 * 7
    t = np.arange(hrs)
    base = 100 + 12 * np.sin(t / 25.0) + np.cumsum(rng.normal(0, 0.3, hrs))
    rows = [(b, b + abs(rng.normal(1.2, 0.3)), b - abs(rng.normal(1.2, 0.3)), b + rng.normal(0, 0.5)) for b in base]
    return bars([(o, max(o, c, h), min(o, c, lo), c) for o, h, lo, c in rows])


def test_build_returns_zones_with_ids_states_and_is_truncation_invariant():
    f = _waves()
    out = LV.build(f, s=S, tf="1h")
    assert out["levels"] and all({"id", "low", "high", "state", "role", "degree", "score", "reason"} <= set(z) for z in out["levels"])
    assert all(z["high"] - z["low"] >= S["zone_min_mr"] * out["mr"] - 0.01 for z in out["levels"])        # किंमती 2 decimals ला rounded
    cut = len(f) - 40
    a = LV.build(f.iloc[:cut].reset_index(drop=True), s=S, tf="1h")
    b = LV.build(f, s=S, tf="1h", upto=cut - 1)
    assert [(z["id"], z["state"]) for z in a["levels"]] == [(z["id"], z["state"]) for z in b["levels"]]


def test_old_unbroken_level_survives_six_weeks_within_degree_lookback():
    up = [(100 + i, 101.5 + i, 99.5 + i, 101 + i) for i in range(30)]                       # वर
    dn = [(130 - i, 131 - i, 128.5 - i, 129 - i) for i in range(30)]                          # 100 पर्यंत खाली (major low)
    flat = [(115 + (i % 2), 117 + (i % 2), 113 + (i % 2), 115 + (i % 2)) for i in range(7 * 5 * 6)]   # सहा आठवडे वरच
    f = bars(up + dn + flat)
    out = LV.build(f, s=S, tf="1h")
    lows = [z for z in out["candidates"] if z["low"] <= 100.5 <= z["high"] + 1.0]
    assert lows and lows[0]["state"] in ("ACTIVE", "TESTED")                                  # वेळेने कमकुवत होत नाही
