"""KB K4 / G4 (Abhi's final flip rule, Z-1) — decision3 BROKEN vs FLIPPED and the flip retest, mirrored (bull put / bear call).

  • a zone FLIPS only when price goes beyond it AND trades past the far-side swing; beyond it without that swing ⇒ BROKEN, and a BROKEN
    zone's retest is NOT a trade location (`Levels.active` skips it);
  • FLIPPED retest = trade location only through (a) a corrective pullback (decision3.daily_legs.classify) and (b) pullback FUT volume
    lower than the flip impulse (as a whole), then (c) = ⑥ (a2 + c0 + c1, unchanged); impulsive / high-volume return ⇒ no trade;
  • missing FUT volume ⇒ (b) NA with a reason, never a silent pass (default `flip_volume_na` = "cap_b": decision3's volume-NA convention);
  • no look-ahead: states and G4 facts at bar t equal those computed on data cut at t.
Real-day fixtures (12 Oct sweep, 13 Oct flip) need the private trade-data export and skip cleanly without it.
"""
import os

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import method as M
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

UP, DOWN = M.UP, M.DOWN
S = S3.load()
MID = 125.0                                                               # mirror: p ⇒ 2·MID − p

# Resistance zone R (D2 H 118, bar 20) between the far-side swing high 130 (bar 6) and the impulse origin 108 (bar 26).
BASE = [(0, 100), (6, 130), (14, 104), (20, 118), (26, 108)]
PIV2 = [("H", 130, 6, 8), ("L", 104, 14, 16), ("H", 118, 20, 22), ("L", 108, 26, 28)]
PATHS = {
    # impulse 108 ⇒ 134 (past the far swing 130 ⇒ FLIPPED), then zigzag 134 ⇒ 124 ⇒ 129 ⇒ into the zone, then a bullish commitment
    "flip_corrective": ([(40, 134), (46, 124), (50, 129), (58, 118.4), (59, 123)], [("L", 124, 46, 48), ("H", 129, 50, 52)]),
    # same flip, but the return is a 5-wave impulse 134 ⇒ 127 ⇒ 131 ⇒ 121 ⇒ 124 ⇒ zone
    "flip_impulsive": ([(40, 134), (44, 127), (46, 131), (51, 121), (53, 124), (58, 118.4), (59, 123)],
                       [("L", 127, 44, 46), ("H", 131, 46, 48), ("L", 121, 51, 53), ("H", 124, 53, 55)]),
    # break (3 closes above the zone) but only to 126 < 130 ⇒ BROKEN, then a retest of the zone
    "broken_only": ([(36, 126), (42, 121), (45, 124), (52, 118.4), (53, 123)], [("L", 121, 42, 44), ("H", 124, 45, 47)]),
}


def _build(name, mirror=False, vol_pullback=600.0, vol_impulse=1000.0, vol_start=1200.0):
    """15M bars + D2 / D1 pivots + per-bar FUT volume for one scenario. Volume: impulse bars `vol_impulse`, pullback `vol_pullback`
    (its first two bars `vol_start` — the pullback may start on rising volume), the last (commitment) bar 2× impulse."""
    pts, piv1 = PATHS[name]
    anchors = BASE + pts
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    closes = [f(c) for c in closes]
    zone_end = pts[-2][0]                                                  # pullback end bar (inside the zone)
    lows = {zone_end: f(117.6)} if not mirror else {}
    highs = {zone_end: f(117.6)} if mirror else {}
    m = m15_from(closes, wick=0.3, lows=lows, highs=highs)
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    p2 = [P(sw(k), f(p), b, c) for k, p, b, c in PIV2]
    p1 = [P(sw(k), f(p), b, c) for k, p, b, c in piv1]
    ext = pts[0][0]
    n = len(m)
    vol = np.full(n, 800.0)
    vol[27:ext + 1] = vol_impulse
    vol[ext + 1:n - 1] = vol_pullback
    vol[ext + 1:ext + 3] = vol_start
    vol[n - 1] = 2 * vol_impulse
    return m, p2, p1, vol


def _levels(m, p2, p1, s=None):
    return LV.Levels(res_of(m, p2, p1), s=s)


def _zone(lv, mirror):
    return [L for L in lv.L if abs(L.anchor - (2 * MID - 118 if mirror else 118)) < 1e-6][0]


def _v(m, p2, p1, vol, s=None):
    """V22 without the Daily / K machinery: only what flip_gate reads (levels, pivots, settings, FUT volume)."""
    res = res_of(m, p2, p1)
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load(s)
    V.res = res
    V.levels = LV.Levels(res, s=s)
    V.fut15, V.fut15_src = (None, None) if vol is None else (np.asarray(vol, float), "test FUT volume")
    V._legs_arr = None
    return V


def _row(lv, L, t):
    return [x for x in lv.snapshot(t) if x["id"] == L.id][0]


# ------------------------------------------------------------------------------------------------ state machine
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_broken_not_flipped_retest_is_not_a_trade_location(mirror):
    m, p2, p1, _ = _build("broken_only", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    t = len(m) - 2                                                         # the retest bar (inside the zone)
    lo, hi = Z.band_at(t)
    assert m["low"].iloc[t] <= hi and m["high"].iloc[t] >= lo
    x = _row(lv, Z, t)
    assert x["state"] == FL.BROKEN and x["flipped_at"] is None and x["broken_at"] is not None
    assert x["role"] == (LV.SUP if mirror else LV.RES)                     # old role kept (Abhi: until the swing, the zone keeps its role)
    assert x["far_swing"]["price"] == pytest.approx(2 * MID - 130 if mirror else 130)   # the swing still to pass
    trend = "DOWN" if mirror else "UP"
    assert all(a["id"] != Z.id for a in lv.active(t, trend))               # ⇒ no entry at a BROKEN zone
    assert all(a["id"] != Z.id for a in lv.active(t, "UP" if mirror else "DOWN"))
    old = _levels(m, p2, p1, {"level_flip_rule": "acceptance"})            # old spec §5.4: acceptance flipped it ⇒ it WAS a location
    assert any(a["id"] == _zone(old, mirror).id for a in old.active(t, trend))


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flip_only_when_price_trades_past_the_far_side_swing(mirror):
    m, p2, p1, _ = _build("flip_corrective", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    kinds = [(b, k) for b, k, _ in Z.events if k in ("broken", "flip", "reclaim", "dead")]
    t_brk = next(b for b, k in kinds if k == "broken")
    t_flip = next(b for b, k in kinds if k == "flip")
    assert t_brk < t_flip and Z.dead_bar is None
    far = 2 * MID - 130 if mirror else 130
    ext = (m["low"] if mirror else m["high"]).to_numpy()
    assert all((ext[i] > far) == mirror for i in range(t_brk, t_flip))     # not past the swing before the flip bar
    assert (ext[t_flip] < far) if mirror else (ext[t_flip] > far)          # traded past it on the flip bar (no candle condition)
    assert _row(lv, Z, t_flip - 1)["state"] == FL.BROKEN
    x = _row(lv, Z, len(m) - 2)
    assert x["state"] == FL.FLIPPED and x["role"] == (LV.RES if mirror else LV.SUP)
    assert x["broken_at"] == t_brk and x["flipped_at"] == t_flip and x["far_swing"]["price"] == pytest.approx(far)
    assert x["far_swing"]["bar"] == 6 and x["broken_ts"] and x["flipped_ts"]
    assert any(a["id"] == Z.id for a in lv.active(len(m) - 2, "DOWN" if mirror else "UP"))   # FLIPPED ⇒ a location (checks follow)


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_sweep_keeps_the_old_role_and_reclaim_returns_a_broken_zone(mirror):
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    # 2 closes above the zone and back ⇒ sweep, old role, ACTIVE / TESTED
    closes = [f(c) for c in [100, 110, 120, 130, 120, 110, 104, 108, 112, 116, 118, 116, 112, 110, 114, 117, 119, 119.5, 116, 113, 110]]
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    p2 = [P(sw("H"), f(130), 3, 5), P(sw("L"), f(104), 6, 8), P(sw("H"), f(118), 10, 12)]
    m = m15_from(closes, wick=0.3)
    lv = _levels(m, p2, [])
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    t = len(m) - 1
    assert Z.count("sweep", t) >= 1 and Z.count("broken", t) == 0 and Z.state_at(t) in (FL.ACTIVE, FL.TESTED)
    assert Z.role_at(t) == (LV.SUP if mirror else LV.RES)
    # 3 closes above (BROKEN), swing 130 not reached, then 3 closes back below ⇒ reclaim ⇒ old role, a location again
    closes2 = [f(c) for c in [100, 110, 120, 130, 120, 110, 104, 108, 112, 116, 118, 116, 112, 110, 114, 117, 119, 120, 121, 122,
                              119, 116, 115, 114, 113]]
    lv2 = _levels(m15_from(closes2, wick=0.3), p2, [])
    Z2 = [L for L in lv2.L if abs(L.anchor - f(118)) < 1e-6][0]
    ev = [k for _, k, _ in Z2.events if k in ("broken", "reclaim", "flip")]
    assert ev == ["broken", "reclaim"] and Z2.state_at(len(closes2) - 1) in (FL.ACTIVE, FL.TESTED)


def test_nine_oct_case_flips_at_the_far_swing_not_at_acceptance():
    """The 9 Oct blind-spot fixture (tests/test_decision3_level_death_side.py): support ≈ 96.5 broken by closes, then price trades below
    the swing low 90 ⇒ FLIPPED to supply there (not at acceptance), alive for the retest from below."""
    from tests.test_decision3_level_death_side import CLOSES, PIV, T_BREAK
    m = m15_from(CLOSES, lows={4: 90.0})
    lv = LV.Levels(res_of(m, [P(*x) for x in PIV]))
    Z = [x for x in lv.L if abs(x.anchor - 96.5) < 1e-6][0]
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    t_brk = next(b for b, k, _ in Z.events if k == "broken")
    assert t_brk < t_flip == T_BREAK and m["low"].iloc[t_flip] < 90.0 <= m["low"].iloc[t_flip - 1]
    assert Z.dead_bar is None and Z.state_at(len(m) - 1) == FL.FLIPPED and Z.role_at(len(m) - 1) == LV.RES


def test_flip_rule_setting_is_checked_and_registered():
    assert S3.DEFAULTS["level_flip_rule"] == "far_swing"
    for k in ("level_flip_rule", "flip_pullback_vol_ratio", "flip_vol_min_coverage", "flip_volume_na", "flip_pullback_inner_degree"):
        assert k in S3.REGISTER
    assert S3.DEFAULTS["flip_pullback_vol_ratio"] == 1.0 and S3.DEFAULTS["flip_volume_na"] == "cap_b"
    m, p2, p1, _ = _build("broken_only")
    with pytest.raises(ValueError):
        _levels(m, p2, p1, {"level_flip_rule": "strong_move"})


# ------------------------------------------------------------------------------------------------ G4 flip retest
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flipped_corrective_low_volume_pullback_with_commitment_is_an_entry_location(mirror):
    m, p2, p1, vol = _build("flip_corrective", mirror)
    V = _v(m, p2, p1, vol)
    Z = _zone(V.levels, mirror)
    t = len(m) - 1                                                         # commitment bar
    lvl = _row(V.levels, Z, t)
    assert lvl["state"] == FL.FLIPPED
    d = DOWN if mirror else UP
    assert M.at_level(V.levels.A, t, d, lvl, int(S["touch_window_bars"]))[0]
    g, cap, notes = V.flip_gate(t, lvl)
    assert g["ok"] is True and g["a"] is True and g["b"] is True and cap is None, g["why"]
    assert g["a_read"]["kind"] == "corrective" and g["a_read"]["form"] == "zigzag"
    assert g["b_read"]["ratio"] < 1.0 and g["b_read"]["pullback_avg"] < g["b_read"]["impulse_avg"]
    assert g["impulse"]["to_bar"] == g["pullback"]["from_bar"] == 40
    A = {**V.levels.A, "volume": vol}                                      # (c): ⑥ shared confirmation (a2 + c0; c1 off — no LTF here)
    arm = next(i for i in range(41, t + 1) if A["low"][i] <= lvl["hi"] and A["high"][i] >= lvl["lo"])
    cf = M.confirm(A, arm, t, d, lvl, {**S, "ltf_choch": False})
    assert cf["ok"] and cf["c0"], cf["why"]


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flipped_impulsive_high_volume_return_is_no_trade(mirror):
    m, p2, p1, vol = _build("flip_impulsive", mirror, vol_pullback=1500.0, vol_start=1500.0)
    V = _v(m, p2, p1, vol)
    Z = _zone(V.levels, mirror)
    t = len(m) - 1
    lvl = _row(V.levels, Z, t)
    assert lvl["state"] == FL.FLIPPED
    g, _, _ = V.flip_gate(t, lvl)
    assert g["a"] is False and g["a_read"]["kind"] == "impulse"
    assert g["b"] is False and g["b_read"]["ratio"] > 1.0
    assert g["ok"] is False and g["decision"] == E3.M_NO and "no trade" in g["why"]
    # each check alone is enough: corrective but high volume ⇒ no trade; impulsive on low volume ⇒ no trade
    m2, q2, q1, v2 = _build("flip_corrective", mirror, vol_pullback=1500.0, vol_start=1500.0)
    V2 = _v(m2, q2, q1, v2)
    g2, _, _ = V2.flip_gate(len(m2) - 1, _row(V2.levels, _zone(V2.levels, mirror), len(m2) - 1))
    assert g2["a"] is True and g2["b"] is False and g2["decision"] == E3.M_NO
    m3, r2, r1, v3 = _build("flip_impulsive", mirror)
    V3 = _v(m3, r2, r1, v3)
    g3, _, _ = V3.flip_gate(len(m3) - 1, _row(V3.levels, _zone(V3.levels, mirror), len(m3) - 1))
    assert g3["a"] is False and g3["b"] is True and g3["decision"] == E3.M_NO


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_missing_fut_volume_is_na_with_reason_never_a_silent_pass(mirror):
    m, p2, p1, vol = _build("flip_corrective", mirror)
    t = len(m) - 1
    V = _v(m, p2, p1, None)
    lvl = _row(V.levels, _zone(V.levels, mirror), t)
    g, cap, notes = V.flip_gate(t, lvl, cap=None, notes=["x"])
    assert g["b"] is None and "FUT volume missing" in g["b_why"] and g["a"] is True
    assert g["ok"] is True and cap == "B" and any("कमाल B" in x for x in notes)     # default cap_b = decision3 volume-NA convention
    Vb = _v(m, p2, p1, None, {"flip_volume_na": "block"})
    gb, capb, _ = Vb.flip_gate(t, lvl)
    assert gb["ok"] is False and gb["decision"] == E3.M_WAIT and capb is None
    holes = vol.copy()
    holes[45] = np.nan                                                     # one pullback bar without FUT volume ⇒ NA (coverage 1.0)
    Vh = _v(m, p2, p1, holes)
    gh, caph, _ = Vh.flip_gate(t, lvl)
    assert gh["b"] is None and "coverage" in gh["b_why"] and caph == "B"


def test_fut_volume_15m_uses_near_month_and_marks_incomplete_bars_na():
    ts = pd.to_datetime(["2030-01-07 09:15", "2030-01-07 09:30", "2030-01-07 09:45"])
    m15 = pd.DataFrame({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15)})
    near, far = pd.Timestamp("2030-01-30"), pd.Timestamp("2030-02-27")
    rows = [(t, 10.0, near) for t in pd.date_range("2030-01-07 09:15", periods=5, freq="5min")]        # 09:15 bar full, 09:30 bar 2/3
    rows += [(t, 999.0, far) for t in pd.date_range("2030-01-07 09:15", periods=9, freq="5min")]       # far month ⇒ ignored
    fut = pd.DataFrame(rows, columns=["timestamp", "volume", "expiry"])
    v = FL.fut_volume_15m(m15, fut)
    assert v[0] == pytest.approx(30.0) and np.isnan(v[1]) and np.isnan(v[2])
    assert FL.fut_volume_15m(m15, None) is None


# ------------------------------------------------------------------------------------------------ no look-ahead
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_no_look_ahead_states_and_g4_facts_equal_on_data_cut_at_t(mirror):
    m, p2, p1, vol = _build("flip_corrective", mirror)
    full = _v(m, p2, p1, vol)
    Z = _zone(full.levels, mirror)
    for k in range(30, len(m) + 1):
        cut = m.iloc[:k].reset_index(drop=True)
        part = _v(cut, [p for p in p2 if p.confirm_bar < k], [p for p in p1 if p.confirm_bar < k], vol[:k])
        t = k - 1
        assert part.levels.snapshot(t) == full.levels.snapshot(t)
        Zp = [L for L in part.levels.L if L.id == Z.id]
        if Zp and Zp[0].state_at(t) == FL.FLIPPED:
            lp, lf = _row(part.levels, Zp[0], t), _row(full.levels, Z, t)
            assert part.flip_gate(t, lp)[0] == full.flip_gate(t, lf)[0]
    # the state at the bar before the flip does not know the flip
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    assert _row(full.levels, Z, t_flip - 1)["flipped_at"] is None and Z.state_at(t_flip - 1) == FL.BROKEN


# ------------------------------------------------------------------------------------------------ shared band facts (find_bands)
def test_band_flip_facts_broken_vs_flipped():
    from facts import validity as FV
    m, _, _, _ = _build("flip_corrective")
    B = FV.bars_of(m)
    x = {"lo": 117.0, "hi": 118.0, "breaks": [{"bar": 33, "dir": "up"}]}
    f = LV.band_flip_facts(B, len(m) - 1, x, start=0)
    assert f["flip_state"] == FL.FLIPPED and f["far_swing"]["price"] >= 129.0 and f["flipped_at"]["bar"] > 33
    mb, _, _, _ = _build("broken_only")
    fb = LV.band_flip_facts(FV.bars_of(mb), len(mb) - 1, {**x, "breaks": [{"bar": 33, "dir": "up"}]}, start=0)
    assert fb["flip_state"] == FL.BROKEN and fb["flipped_at"] is None
    assert LV.band_flip_facts(B, len(m) - 1, {"lo": 1, "hi": 2, "breaks": []})["flip_state"] == FL.ACTIVE


# ------------------------------------------------------------------------------------------------ synthetic 12-Oct fixture (oct12_fixture)
def test_oct12_synthetic_fixture_supply_is_broken_not_flipped_under_k4():
    """tests/oct12_fixture.py (synthetic bear call): its supply is a support broken by acceptance with NO swing low below it (the trend
    is making new lows) ⇒ under Abhi's K4 rule it is BROKEN (no far-side swing to pass), not a trade location; the old spec §5.4 flip
    made it the setup level. Reported as open question Z-1a (no far-side swing ⇒ can the zone ever flip?)."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    new = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    old = E3.V22(m15, s={"level_death_side": "role", "level_flip_rule": "acceptance"}, ltf=ltf, futures=fut)
    ts = new.levels.ts
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == ts.dt.normalize().iloc[-1]]
    so = [r for r in (old.decide(t) for t in bars) if r["decision"] == "setup"]
    assert so                                                               # old rule: the fixture's setup
    lid = so[0]["level"]["id"]
    x = [y for y in new.levels.snapshot(so[0]["bar"]) if y["id"] == lid][0]
    assert x["state"] == FL.BROKEN and x["far_swing"] is None and x["role"] == LV.SUP
    assert all(y["id"] != lid for y in new.levels.active(so[0]["bar"], "DOWN"))
    assert not [r for r in (new.decide(t) for t in bars) if r["decision"] == "setup" and (r["level"] or {}).get("id") == lid]


# ------------------------------------------------------------------------------------------------ real days (private data only)
TD = "/home/user/trade-data"
EXPORT = os.path.join(TD, "live_export", "2026-10-13")
FILES = {"m1_hist": os.path.join(TD, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"),
         "m1_exp": os.path.join(EXPORT, "NIFTY_1minute.parquet"), "i5": os.path.join(EXPORT, "oe_index_5min_NIFTY.parquet"),
         "fut5": os.path.join(EXPORT, "oe_futures_5min_NIFTY.parquet")}
SUPPLY_FUT = 22667.0                                                      # Abhi's supply, a NIFTY FUT price


def _read(path):
    from elliott import data_policy as DP
    df = pd.read_csv(path, parse_dates=["timestamp"]) if path.endswith(".csv.gz") else pd.read_parquet(path)
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return DP.filter_allowed(df.assign(timestamp=ts), "annotation")       # NIFTY holdout rows never used


def _to15(df5):
    """Complete 09:15-anchored 15M bins (3 × 5M) only — an unfinished bin is dropped, never filled."""
    d = df5.copy()
    day = d["timestamp"].dt.normalize()
    k = ((d["timestamp"] - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(minutes=15)).astype(int)
    d["k"] = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(minutes=15)
    g = d.groupby("k").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("close", "size"))
    return g[g["n"] == 3].reset_index().rename(columns={"k": "timestamp"})[["timestamp", "open", "high", "low", "close"]]


@pytest.fixture(scope="module")
def real():
    """NIFTY SPOT 15M (decision3 levels run on spot, as the live engine3 feed): 1m history (golden window) + the live export's 1m to
    12 Oct ⇒ market_state.core.frame 15M; 13 Oct = complete 15M bins from the export's 5M spot (partial day). FUT = near-month 5M."""
    if not all(os.path.exists(p) for p in FILES.values()):
        pytest.skip("private trade-data (live export / upstox 1m) not present")
    import market_state.core as MC
    from opportunity_engine import volume as OV
    from swings2 import engine as SE
    h = _read(FILES["m1_hist"])[["timestamp", "open", "high", "low", "close"]]
    e = _read(FILES["m1_exp"])[["timestamp", "open", "high", "low", "close"]]
    m1 = pd.concat([h, e[e["timestamp"] > h["timestamp"].max()]], ignore_index=True)
    m15 = MC.frame(m1, "15m", pd.Timestamp(m1["timestamp"].max().normalize()) + pd.Timedelta(hours=15, minutes=30))
    i5 = _read(FILES["i5"])
    i5 = i5[i5["timestamp"].dt.normalize() > m15["timestamp"].max().normalize()]
    m15 = pd.concat([m15[["timestamp", "open", "high", "low", "close"]], _to15(i5)], ignore_index=True)
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    m15 = m15.sort_values("timestamp").reset_index(drop=True)
    res = SE.build(m15, None)
    return m15, OV.near_month_rows(_read(FILES["fut5"])), LV.Levels(res)


def _basis(m15, fut, day):
    """Median (near-month FUT close − SPOT close) on the day's 15M bars (FUT 5M bar ending with the 15M bar)."""
    md = m15[m15["timestamp"].dt.normalize() == pd.Timestamp(day)]
    f = fut.drop_duplicates("timestamp").set_index("timestamp")["close"]
    fc = f.reindex((md["timestamp"] + pd.Timedelta(minutes=10)).to_numpy()).to_numpy(float)
    dd = fc - md["close"].to_numpy(float)
    dd = dd[np.isfinite(dd)]
    if not len(dd):
        pytest.skip(f"no FUT closes match the {day} spot bars")
    return float(np.median(dd))


def _last_bar(m15, day):
    ix = np.flatnonzero((m15["timestamp"].dt.normalize() == pd.Timestamp(day)).to_numpy())
    if not len(ix):
        pytest.skip(f"{day} not in the data")
    return ix, int(ix[-1])


def _zone_at(lv, t, spot):
    hits = [x for x in lv.snapshot(t) if x["lo"] <= spot <= x["hi"]]
    assert hits, f"no decision3 level contains spot {spot:,.1f} (report, do not tune)"
    return hits[0]


def test_real_12_oct_supply_kept_as_sweep_not_flipped(real):
    """12 Oct NIFTY (Abhi): the ≈22,667 FUT supply was swept, not flipped (supply kept). Searched at its SPOT equivalent
    (22,667 − the day's median FUT−spot basis)."""
    m15, fut, lv = real
    ix, t = _last_bar(m15, "2026-10-12")
    basis = _basis(m15, fut, "2026-10-12")
    spot = SUPPLY_FUT - basis
    x = _zone_at(lv, t, spot)
    L = lv.L[x["id"]]
    ev12 = [(str(lv.ts.iloc[b]), k) for b, k, _ in L.events if b in set(ix.tolist()) and k != "test"]
    print(f"\n12 Oct: basis {basis:.1f} ⇒ spot {spot:,.1f}; level {x['id']} {x['role']} {x['lo']:,.1f}-{x['hi']:,.1f} {x['state']} "
          f"(flipped {x['flipped_ts']} past {x['far_swing']}); day high {m15['high'].iloc[ix].max():,.1f}; 12 Oct events {ev12}")
    assert x["role"] == LV.RES                                              # supply kept
    assert not any(k in ("flip", "broken") for _, k in ev12)               # no break / flip on 12 Oct
    assert any(k == "sweep" for _, k in ev12) and m15["high"].iloc[ix].max() > x["hi"]   # wick above, close back ⇒ sweep


def test_real_13_oct_far_swing_is_the_6_7_oct_high_and_flip_needs_it(real):
    """13 Oct NIFTY (Abhi): the supply flips to support once price is past the 6 / 7 Oct swing high. The export's 13 Oct is PARTIAL
    (to the last complete 15M bin); the code's state must match what those bars show — FLIPPED support only if they closed above the
    band and traded past the far-side swing; nothing is filled in."""
    m15, fut, lv = real
    _, t12 = _last_bar(m15, "2026-10-12")
    ix, t = _last_bar(m15, "2026-10-13")
    spot = SUPPLY_FUT - _basis(m15, fut, "2026-10-12")
    x12 = _zone_at(lv, t12, spot)
    L = lv.L[x12["id"]]
    lo, hi = L.band_at(t)
    fs = FL.far_swing(lv.known_pivots(t), lo, hi, True, int(ix[0]))
    assert fs is not None and str(lv.ts.iloc[fs.bar].date()) in ("2026-10-06", "2026-10-07")      # the 6 / 7 Oct swing high
    closed_above = bool((m15["close"].iloc[ix] > hi).any())
    past = bool((m15["high"].iloc[ix] > fs.price).any())
    st = L.state_at(t)
    print(f"\n13 Oct: {len(ix)} complete 15M bars to {lv.ts.iloc[t]} (partial); band {lo:,.1f}-{hi:,.1f}; far-side swing {fs.price:,.1f} "
          f"({lv.ts.iloc[fs.bar]}, known {lv.ts.iloc[fs.confirm_bar]}); 13 Oct high {m15['high'].iloc[ix].max():,.1f}; "
          f"closed above band {closed_above}, past swing {past} ⇒ state {st} role {L.role_at(t)}")
    if closed_above and past:
        assert st == FL.FLIPPED and L.role_at(t) == LV.SUP
    else:
        assert L.role_at(t) == LV.RES and not any(k == "flip" for b, k, _ in L.events if b >= ix[0])
