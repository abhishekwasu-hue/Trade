"""KB K4 / G4 (Abhi's final flip rule, Z-1 final answers) — decision3 BROKEN / FLIPPED / DEAD and the in-zone study, mirrored.

  • a zone FLIPS only when price goes beyond it AND trades past the far-side swing (no swing beyond ⇒ the first CONFIRMED swing after the
    break, Z-1a); beyond it without that swing ⇒ BROKEN, not a trade location; a FLIPPED zone broken again past its far swing ⇒ DEAD;
  • G4 approach (a) shape / (b) volume = CONTEXT only (Z-1d): reported, never a no_trade / wait; the in-zone study (⑥ a2 + c0 + c1, RSI
    divergence as evidence) decides, end to end through V22.decide();
  • volume = per-bar FUT volume ÷ its time-of-day slot median (20 sessions); FUT missing ⇒ data problem: no entry (+ one Telegram line per
    symbol per day for NIFTY / BANKNIFTY) — no grade-B trade without volume (Z-1c);
  • no look-ahead: states and G4 facts at bar t equal those computed on data cut at t.
Real-day checks (12 Oct golden bear call, 13 Oct no bear call) need the private trade-data export and skip cleanly without it.
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
    # the corrective flip, then the flipped support breaks again and price trades below the swing low 108 ⇒ DEAD (no second flip)
    "flip_then_dead": ([(40, 134), (46, 124), (50, 129), (58, 118.4), (59, 123), (63, 128), (80, 100)],
                       [("L", 124, 46, 48), ("H", 129, 50, 52)]),
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
    zone_end = pts[4][0] - 1 if name == "flip_then_dead" else pts[-2][0]  # pullback end bar (inside the zone)
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


def _v(m, p2, p1, vol=None, s=None):
    """V22 without the Daily / K machinery: only what the G4 context / in-zone read need (levels, pivots, settings, volume)."""
    res = res_of(m, p2, p1)
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load(s)
    V.res = res
    V.levels = LV.Levels(res, s=s)
    if vol is not None:
        V.levels.A["volume"] = np.asarray(vol, float)                         # treated as already slot-normalised here
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
    assert x["far_swing"]["price"] == pytest.approx(2 * MID - 130 if mirror else 130) and x["far_swing"]["source"] == "before_break"
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
    assert any(a["id"] == Z.id for a in lv.active(len(m) - 2, "DOWN" if mirror else "UP"))   # FLIPPED ⇒ a location (in-zone study decides)


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_first_confirmed_swing_after_the_break_when_no_swing_lies_beyond(mirror):
    """Abhi Z-1a: the zone is the top of the known structure (no swing above) ⇒ the far-side swing is the first CONFIRMED swing that
    forms after the break; the zone flips only once price trades past it."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    anchors = [(0, 100), (8, 118), (16, 106), (26, 126), (31, 121), (38, 130), (40, 129)]
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(106), 16, 18), P(sw("H"), f(126), 26, 29)]
    lv = _levels(m, p2, [])
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    t_brk = next(b for b, k, _ in Z.events if k == "broken")
    assert _row(lv, Z, 28)["state"] == FL.BROKEN and _row(lv, Z, 28)["far_swing"] is None          # swing 126 not confirmed yet
    x = _row(lv, Z, 30)
    assert x["state"] == FL.BROKEN and x["far_swing"]["price"] == pytest.approx(f(126))
    assert x["far_swing"]["source"] == "first_confirmed_after_break" and x["far_swing"]["bar"] >= x["exc_start"]
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    ext = (m["low"] if mirror else m["high"]).to_numpy()
    assert t_brk < t_flip and ((ext[t_flip] < f(126)) if mirror else (ext[t_flip] > 126))
    assert not any(((ext[i] < f(126)) if mirror else (ext[i] > 126)) for i in range(29, t_flip))
    assert Z.state_at(len(m) - 1) == FL.FLIPPED and Z.role_at(len(m) - 1) == (LV.RES if mirror else LV.SUP)


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_flipped_zone_broken_again_past_its_far_swing_is_dead_no_second_flip(mirror):
    """Abhi Z-1f: once flipped the old role ends; broken again (acceptance) ⇒ BROKEN; past ITS far-side swing ⇒ DEAD, logged."""
    m, p2, p1, _ = _build("flip_then_dead", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    kinds = [k for _, k, _ in Z.events if k in ("broken", "flip", "dead")]
    assert kinds == ["broken", "flip", "broken", "dead"]
    t_dead = Z.dead_bar
    far = 2 * MID - 108 if mirror else 108                                 # the D2 swing beyond the band on the new break side
    ext = (m["high"] if mirror else m["low"]).to_numpy()
    assert (ext[t_dead] > far) if mirror else (ext[t_dead] < far)
    assert "no second flip" in [d for b, k, d in Z.events if k == "dead"][0]
    assert Z.state_at(t_dead - 1) == FL.BROKEN and Z.state_at(t_dead) == FL.DEAD
    assert all(x["id"] != Z.id for x in lv.snapshot(len(m) - 1))           # dead ⇒ out of the snapshot / never a location
    assert Z.count("flip", len(m) - 1) == 1


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_sweep_keeps_the_old_role_and_reclaim_returns_a_broken_zone_logged_as_sweep(mirror):
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    closes = [f(c) for c in [100, 110, 120, 130, 120, 110, 104, 108, 112, 116, 118, 116, 112, 110, 114, 117, 119, 119.5, 116, 113, 110]]
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    p2 = [P(sw("H"), f(130), 3, 5), P(sw("L"), f(104), 6, 8), P(sw("H"), f(118), 10, 12)]
    m = m15_from(closes, wick=0.3)
    lv = _levels(m, p2, [])
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    t = len(m) - 1
    assert Z.count("sweep", t) >= 1 and Z.count("broken", t) == 0 and Z.state_at(t) in (FL.ACTIVE, FL.TESTED)
    assert Z.role_at(t) == (LV.SUP if mirror else LV.RES)
    closes2 = [f(c) for c in [100, 110, 120, 130, 120, 110, 104, 108, 112, 116, 118, 116, 112, 110, 114, 117, 119, 120, 121, 122,
                              119, 116, 115, 114, 113]]
    lv2 = _levels(m15_from(closes2, wick=0.3), p2, [])
    Z2 = [L for L in lv2.L if abs(L.anchor - f(118)) < 1e-6][0]
    ev = [k for _, k, _ in Z2.events if k in ("broken", "reclaim", "flip", "sweep")]
    assert ev[-3:] == ["broken", "reclaim", "sweep"] and Z2.state_at(len(closes2) - 1) in (FL.ACTIVE, FL.TESTED)
    assert _row(lv2, Z2, len(closes2) - 1)["sweeps"] >= 1                  # ★ / trap_sweep evidence kept


def test_a_dead_level_never_absorbs_a_new_swing():
    """Review: a new swing overlapping a DEAD level is born as its own level (DEAD levels are out of the merge and the snapshot). A swing
    in the area of a BROKEN level still merges into it (the same zone — Abhi's 12 Oct zone is such a merge; OPEN_QUESTIONS)."""
    m, p2, p1, _ = _build("flip_then_dead")
    lv0 = _levels(m, p2, p1)
    Z = _zone(lv0, False)
    td = Z.dead_bar
    lo, hi = Z.band_at(td)
    extra = P("L", (lo + hi) / 2, td + 1, td + 2)
    lv = _levels(m, p2 + [extra], p1)
    Zd = _zone(lv, False)
    born = [L for L in lv.L if L.id != Zd.id and L.born_bar == td + 2 and abs(L.anchor - (lo + hi) / 2) < 1e-6]
    assert Zd.dead_bar == td and born and all(b != "a:D2" or tm < td for tm, b in Zd.merged_from)
    assert any(x["id"] == born[0].id for x in lv.snapshot(td + 2)) and all(x["id"] != Zd.id for x in lv.snapshot(td + 2))


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


def test_settings_are_registered_and_cap_b_option_is_gone():
    assert S3.DEFAULTS["level_flip_rule"] == "far_swing" and S3.DEFAULTS["c0_volume_required"] is True
    for k in ("level_flip_rule", "flip_pullback_vol_ratio", "flip_vol_min_coverage", "flip_pullback_inner_degree", "vol_slot_sessions",
              "vol_slot_min_sessions", "c0_volume_required"):
        assert k in S3.REGISTER and k in S3.DEFAULTS
    assert "flip_volume_na" not in S3.DEFAULTS and S3.DEFAULTS["vol_slot_sessions"] == 20
    m, p2, p1, _ = _build("broken_only")
    with pytest.raises(ValueError):
        _levels(m, p2, p1, {"level_flip_rule": "strong_move"})


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_daily_trend_side_rule_keeps_a_flipped_zone_out_of_the_opposite_trade(mirror):
    """Abhi (26a0bfe): while the Daily trend is DOWN, a zone flipped to support inside the up-correction is NOT a bull location (no S4
    exception) — `Levels.active` (② / H1) only offers resistance in a DOWN trend; mirrored (UP trend ⇒ a flipped resistance is no bear
    location)."""
    m, p2, p1, _ = _build("flip_corrective", mirror)
    lv = _levels(m, p2, p1)
    Z = _zone(lv, mirror)
    t = len(m) - 2
    x = _row(lv, Z, t)
    assert x["state"] == FL.FLIPPED and x["role"] == (LV.RES if mirror else LV.SUP)
    against = "UP" if mirror else "DOWN"
    assert all(a["id"] != Z.id for a in lv.active(t, against))
    assert any(a["id"] == Z.id for a in lv.active(t, "DOWN" if mirror else "UP"))


# ------------------------------------------------------------------------------------------------ G4 = context only
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_approach_shape_and_volume_are_reported_as_context(mirror):
    for name, vp, a_kind, b_low in (("flip_corrective", 600.0, "corrective", True), ("flip_impulsive", 1500.0, "impulse", False)):
        m, p2, p1, vol = _build(name, mirror, vol_pullback=vp, vol_start=vp if vp > 1000 else 1200.0)
        V = _v(m, p2, p1, vol)
        t = len(m) - 1
        lvl = _row(V.levels, _zone(V.levels, mirror), t)
        g = V.flip_context(t, lvl)
        assert g["context_only"] and g["a_read"]["kind"] == a_kind and g["b"] is b_low
        assert g["impulse"]["to_bar"] == g["pullback"]["from_bar"] == 40 and "not a gate" in g["why"]
        assert "decision" not in g and "ok" not in g


@pytest.fixture(scope="module")
def abc():
    """tests/test_decision3_method._abc_m15 (downtrend, ABC pullbacks) under the DEFAULT flip rule: its supply retests at bars 739–743
    are at a FLIPPED zone (end-to-end G4 path through V22.decide). Volume-less fixture ⇒ c0_volume_required off except where tested."""
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    s = {"maturity_sigma_d": -1e6, "ltf_choch": False, "commit_dom_mult": 0.0}
    return m15, s, E3.V22(m15, s={**s, "c0_volume_required": False}), E3.V22(m15, s=s)


def _flipped_rows(V, bars=range(735, 746)):
    return [r for r in (V.decide(t) for t in bars) if (r.get("level") or {}).get("state") == FL.FLIPPED
            and (r["checklist"].get("③") or [None])[0]]


def test_end_to_end_flipped_zone_in_zone_study_decides_and_context_never_gates(abc, monkeypatch):
    m15, s, V, _ = abc
    rows = _flipped_rows(V)
    assert rows                                                            # the G4 path is really exercised through decide()
    for r in rows:
        assert r["checklist"]["G4"][0] is None and "not a gate" in r["checklist"]["G4"][1]   # context, never a gate
        assert "G4" not in str(r.get("why")) and r["flip"]["state"] == FL.FLIPPED and r["flip"]["far_swing"]   # outcome: ⑥ / conviction
        z = r["zone_read"]
        assert z and z["candles"] and z["summary"]["bars"] == len(z["candles"]) and "rsi_divergence" in z["summary"]
        assert r["flip_retest"]["context_only"]
    seen = {r["bar"]: (r["decision"], r["checklist"]["⑥"]) for r in rows}
    worst = {"context_only": True, "a": False, "b": False, "a_why": "forced", "b_why": "forced", "why": "G4 context (not a gate): forced",
             "pullback": None, "impulse": None, "a_read": None, "b_read": None}
    monkeypatch.setattr(FL, "approach_context", lambda *a, **k: dict(worst))
    V2 = E3.V22(m15, s={**s, "c0_volume_required": False})
    for r in _flipped_rows(V2):                                            # impulsive + high-volume approach ⇒ same decision
        assert (r["decision"], r["checklist"]["⑥"]) == seen[r["bar"]]


def test_end_to_end_fut_volume_missing_is_a_data_problem_not_a_grade_b_entry(abc):
    _, _, V_off, V = abc
    hit = [r for r in _flipped_rows(V) if "data problem" in str(r["checklist"]["⑥"][1])]
    assert hit and all(r["decision"] == "wait" and r["checklist"]["⑥"][0] is False for r in hit)
    assert all("FUT volume missing" in r["checklist"]["⑥"][1] for r in hit)
    assert not [r for r in V.run(range(700, len(V.m15))) if r["decision"] == "setup" and (r["commit"] or {}).get("vol_na")]


def test_engine3_nifty_banknifty_fut_missing_raises_data_error_and_one_telegram_line_per_day(tmp_path, monkeypatch):
    import engine3_live as L
    import engine_signal as ES
    from scripts import engine_signal_run as ESR
    from tests.test_one_bot import Feed
    now = pd.Timestamp("2030-03-25 15:31")
    for sym in L.FUT_REQUIRED:
        with pytest.raises(L.FutVolumeMissing, match="data problem: FUT volume missing"):
            L.build_inputs(Feed(fut=False), sym, now)
    m15, _, _, fut, note = L.build_inputs(Feed(fut=False), "SENSEX", now)    # not in FUT_REQUIRED ⇒ V22 c0 data problem instead
    assert fut is None and "data problem" in note
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []

    def run(sym, tok):
        raise L.FutVolumeMissing(f"{L.DATA_PROBLEM_FUT} (test)")
    for k in range(3):                                                     # three cycles, same day ⇒ one line per symbol
        ESR.main(["--symbols", "NIFTY,BANKNIFTY"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
                 alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-07 10:16") + pd.Timedelta(minutes=15 * k))
    assert len(sent) == 2 and all("data problem: FUT volume missing" in x for x in sent)
    ESR.main(["--symbols", "NIFTY"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
             alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-08 10:16"))
    assert len(sent) == 3                                                  # next day ⇒ again once
    assert ES.alert_data_problem("NIFTY", "x", send=sent.append, state_path=str(tmp_path / "a.json"),
                                 now=pd.Timestamp("2030-01-08 11:00")) is False


# ------------------------------------------------------------------------------------------------ volume: per bar, time-of-day normalised
def test_slot_normalised_volume_0915_bar_is_not_high_just_because_of_its_slot():
    days = pd.bdate_range("2030-01-01", periods=25)
    slots = [pd.Timedelta(hours=9, minutes=15), pd.Timedelta(hours=9, minutes=30), pd.Timedelta(hours=12)]
    ts = [d + x for d in days for x in slots]
    vol = np.array([3000.0 if (i % 3) == 0 else 1000.0 for i in range(len(ts))])
    vol[-1] = 2000.0                                                       # last day 12:00 = 2× its slot
    rel, cnt = M.slot_rel_volume(ts, vol, sessions=20, min_sessions=10)
    assert np.isnan(rel[: 3 * 10]).all() and cnt[3 * 10] == 10           # < 10 earlier sessions ⇒ NA
    assert rel[-3] == pytest.approx(1.0) and rel[-2] == pytest.approx(1.0) and rel[-1] == pytest.approx(2.0)
    assert cnt[-1] == 20                                                   # only the previous 20 sessions
    vol2 = vol.copy()
    vol2[-1] = 99999.0                                                     # today's own bar never enters its baseline
    assert M.slot_rel_volume(ts, vol2, 20, 10)[0][-2] == pytest.approx(1.0)
    A = {"open": np.r_[np.full(len(ts) - 1, 100.0), 100.0], "high": np.r_[np.full(len(ts) - 1, 101.0), 104.5],
         "low": np.r_[np.full(len(ts) - 1, 99.0), 99.8], "close": np.r_[np.full(len(ts) - 1, 100.5), 104.0]}
    t0 = len(ts) - 3                                                        # the last day's 09:15 bar: raw 3× the others, rel 1.0
    A9 = {k: v[: t0 + 1].copy() for k, v in A.items()}
    A9["open"][t0], A9["high"][t0], A9["low"][t0], A9["close"][t0] = 100.0, 104.5, 99.8, 104.0
    lvl = {"lo": 99.0, "hi": 100.6}
    A9["volume"] = vol[: t0 + 1]                                           # raw: 09:15 looks like 3× the window
    raw_ok, _, raw_cm = M.commitment(A9, t0, UP, lvl, {**S, "commit_dom_mult": 0.0}, win=t0 - 2)
    A9["volume"] = rel[: t0 + 1]                                           # normalised: just its usual slot volume
    ok, why, cm = M.commitment(A9, t0, UP, lvl, {**S, "commit_dom_mult": 0.0}, win=t0 - 2)
    assert raw_ok and raw_cm["vol_mult"] > 2.0
    assert not ok and cm.get("wait") == "low_volume" and cm["vol_mult"] <= 1.0


def test_v22_uses_the_slot_normalised_volume_for_a2_and_c0():
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    V = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    A = V.levels.A
    rel, _ = M.slot_rel_volume(m15["timestamp"], A["volume_raw"], 20, 10)
    assert np.allclose(np.nan_to_num(A["volume"], nan=-1), np.nan_to_num(rel, nan=-1)) and np.isfinite(A["volume"][-30:]).all()


# ------------------------------------------------------------------------------------------------ no look-ahead
@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_no_look_ahead_states_and_g4_facts_equal_on_data_cut_at_t(mirror):
    m, p2, p1, vol = _build("flip_then_dead", mirror)
    full = _v(m, p2, p1, vol)
    Z = _zone(full.levels, mirror)
    for k in range(30, len(m) + 1):
        cut = m.iloc[:k].reset_index(drop=True)
        part = _v(cut, [p for p in p2 if p.confirm_bar < k], [p for p in p1 if p.confirm_bar < k], vol[:k])
        t = k - 1
        assert part.levels.snapshot(t) == full.levels.snapshot(t)
        Zp = [L for L in part.levels.L if L.id == Z.id]
        if Zp and Zp[0].state_at(t) == FL.FLIPPED:
            assert part.flip_context(t, _row(part.levels, Zp[0], t)) == full.flip_context(t, _row(full.levels, Z, t))
    t_flip = next(b for b, k, _ in Z.events if k == "flip")
    assert _row(full.levels, Z, t_flip - 1)["flipped_at"] is None and Z.state_at(t_flip - 1) == FL.BROKEN
    assert Z.state_at(Z.dead_bar - 1) != FL.DEAD


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
    """tests/oct12_fixture.py (synthetic bear call): its supply is a support broken by acceptance with nothing below it; under Abhi's K4
    rule the far-side swing is the first CONFIRMED swing low after the break (Z-1a), which price has not passed ⇒ BROKEN, not a trade
    location ⇒ no setup there (the old spec §5.4 flip made it the setup level; the old tests pin "acceptance")."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    new = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    old = E3.V22(m15, s={"level_death_side": "role", "level_flip_rule": "acceptance", "a2_handover_required": False}, ltf=ltf,
                 futures=fut)
    ts = new.levels.ts
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == ts.dt.normalize().iloc[-1]]
    so = [r for r in (old.decide(t) for t in bars) if r["decision"] == "setup"]
    assert so
    t = so[0]["bar"]
    x = [y for y in new.levels.snapshot(t) if y["lo"] <= so[0]["level"]["hi"] and y["hi"] >= so[0]["level"]["lo"] and y["role"] == LV.SUP]
    assert x and x[0]["state"] == FL.BROKEN and x[0]["far_swing"]["source"] == "first_confirmed_after_break"
    assert m15["low"].iloc[x[0]["far_swing"]["known_bar"]:t + 1].min() >= x[0]["far_swing"]["price"]   # not passed yet
    assert all(y["id"] != x[0]["id"] for y in new.levels.active(t, "DOWN"))
    assert not [r for r in (new.decide(t) for t in bars) if r["decision"] == "setup" and (r["level"] or {}).get("id") == x[0]["id"]]


# ------------------------------------------------------------------------------------------------ real days (private data only)
TD = "/home/user/trade-data"
EOD = os.path.join(TD, "live_export", "2026-10-13-eod")
FILES = {"m1_hist": os.path.join(TD, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"), "m1_exp": os.path.join(EOD, "NIFTY_1minute.parquet"),
         "i5": os.path.join(EOD, "oe_index_5min_NIFTY.parquet"), "fut5": os.path.join(EOD, "oe_futures_5min_NIFTY.parquet")}
ZONE = (22543.75, 22621.8)                                                # decision3 1H level (spot) = Abhi's 22,667 FUT supply (Z-1e)
FAR_UP = 22731.8                                                          # D2 H 6 Oct 14:00 (known 7 Oct 13:45) — the 6 / 7 Oct high


def _read(path):
    from elliott import data_policy as DP
    df = pd.read_csv(path, parse_dates=["timestamp"]) if path.endswith(".csv.gz") else pd.read_parquet(path)
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return DP.filter_allowed(df.assign(timestamp=ts), "annotation")       # NIFTY holdout rows never used


def _to15(df5):
    """Complete 09:15-anchored 15M bins (3 × 5M) only — an unfinished bin is dropped, never filled (replay_day's no-1m path)."""
    d = df5.copy()
    day = d["timestamp"].dt.normalize()
    k = ((d["timestamp"] - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(minutes=15)).astype(int)
    d["k"] = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(minutes=15)
    g = d.groupby("k").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("close", "size"))
    return g[g["n"] == 3].reset_index().rename(columns={"k": "timestamp"})[["timestamp", "open", "high", "low", "close"]]


def real_inputs():
    """NIFTY SPOT 15M (decision3 runs on spot, as the live engine3 feed): 1m history (golden window) + the EOD export's 1m to 12 Oct ⇒
    market_state.core.frame 15M / 5M; 13 Oct = complete bins of the export's spot 5M. FUT = the export's near-month 5M. Daily = from
    the 15M (V22 default; the live feed uses Upstox Daily — a known difference). Returns (m15, ltf, fut, m1). Skips without the data."""
    if not all(os.path.exists(p) for p in FILES.values()):
        pytest.skip("private trade-data (2026-10-13-eod export / upstox 1m) not present")
    import market_state.core as MC
    h = _read(FILES["m1_hist"])[["timestamp", "open", "high", "low", "close"]]
    e = _read(FILES["m1_exp"])[["timestamp", "open", "high", "low", "close"]]
    m1 = pd.concat([h, e[e["timestamp"] > h["timestamp"].max()]], ignore_index=True)
    end = pd.Timestamp(m1["timestamp"].max().normalize()) + pd.Timedelta(hours=15, minutes=30)
    i5 = _read(FILES["i5"])
    i5 = i5[i5["timestamp"].dt.normalize() > m1["timestamp"].max().normalize()][["timestamp", "open", "high", "low", "close"]]
    m15 = pd.concat([MC.frame(m1, "15m", end)[["timestamp", "open", "high", "low", "close"]], _to15(i5)], ignore_index=True)
    m15 = m15.sort_values("timestamp").reset_index(drop=True)
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    ltf = pd.concat([MC.frame(m1, "5m", end)[["timestamp", "open", "high", "low", "close"]], i5], ignore_index=True)
    ltf["bar_end"] = ltf["timestamp"] + pd.Timedelta(minutes=5)
    return m15, ltf, _read(FILES["fut5"]), m1


@pytest.fixture(scope="module")
def real():
    m15, ltf, fut, m1 = real_inputs()
    # 1m intrabar order data where it exists (as the rsi2 phase-1 run and replay_day): swings2 D0 pivots — and so the RSI divergence
    # pairs — depend on it (without 1m the 12 Oct 09:15 swing high is not a D0 pivot). 13 Oct has no 1m (5M-built bars).
    return m15, ltf, fut, E3.V22(m15, m1, s=None, ltf=ltf, futures=fut)


def _day_bars(V, day):
    ix = [i for i in range(len(V.m15)) if pd.Timestamp(V.m15["timestamp"].iloc[i]).normalize() == pd.Timestamp(day)]
    if not ix:
        pytest.skip(f"{day} not in the data")
    return ix


def _zone_level(V, t):
    hits = [x for x in V.levels.snapshot(t) if x["lo"] <= sum(ZONE) / 2 <= x["hi"]]
    assert hits, f"no decision3 level at the {ZONE} zone (report, do not tune)"
    return hits[0]


def zone_table(r):
    """12 / 13 Oct report: the in-zone candles (time, side, body vs window, raw / normalised FUT volume, in zone)."""
    z = r.get("zone_read") or {}
    out = [f"{c['time'][5:16]} {c['side']:<12} body×{c['body_vs_window']} vol {c['vol_raw']} rel {c['vol_rel']} in_zone {c['in_zone']}"
           for c in z.get("candles", [])]
    return "\n".join(out + [f"summary: {z.get('summary')}"])


def test_real_12_oct_flipped_seller_zone_in_zone_study_and_golden_bear_call(real):
    """12 Oct NIFTY (Abhi Z-1e): the 22,544–22,622 spot zone is FLIPPED (demand broken 8 Oct past the 5 Oct low) ⇒ a seller area; the
    in-zone study decides. Abhi's bear call that day is the golden truth: if the code does not give it, the test reports the exact
    failing item (xfail with the numbers) — never tuned to pass."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-12")
    lvl = _zone_level(V, ix[0])
    assert lvl["state"] == FL.FLIPPED and lvl["role"] == LV.RES and lvl["flipped_ts"].startswith("2026-10-08")
    rows = [V.decide(t) for t in ix]
    at = [r for r in rows if (r.get("level") or {}).get("id") == lvl["id"] and (r["checklist"].get("③") or [None])[0]]
    for r in at:
        print(f"\n{r['ts']} {r['decision']} ⑥ {r['checklist'].get('⑥')} conv {r.get('conviction')} · G4 {r['checklist'].get('G4')}")
        print(zone_table(r))
    assert at and all(r["checklist"]["G4"][0] is None for r in at)        # context only
    bear = [r for r in at if r["decision"] == "setup" and r["trend_used"] == "DOWN"]
    if not bear:
        last = at[-1]
        pytest.xfail(f"golden 12 Oct bear call NOT produced: decision {last['decision']} · ⑥ {last['checklist'].get('⑥')} · "
                     f"conviction {last.get('conviction')} · missing {last.get('missing')}")


def test_real_13_oct_no_bear_call_then_flip_only_past_22731(real):
    """13 Oct NIFTY (Abhi): price entered the seller zone, small red candles on low volume, no fall, a sideways base, afternoon breakout
    ⇒ NO bear call; a flip only if spot passes 22,731.8. Abhi Z-1f: this zone already flipped once (8 Oct) ⇒ passing its far swing makes
    it DEAD (no second flip) — reported. No bull setup while the Daily trend is DOWN (Abhi 26a0bfe, H1)."""
    m15, ltf, fut, V = real
    ix = _day_bars(V, "2026-10-13")
    lvl = _zone_level(V, ix[0])
    rows = [V.decide(t) for t in ix]
    for r in rows:
        if (r.get("level") or {}).get("id") == lvl["id"] and (r["checklist"].get("③") or [None])[0]:
            print(f"\n{r['ts']} {r['decision']} ⑥ {r['checklist'].get('⑥')} · trend {r['trend_used']}")
            print(zone_table(r))
    assert not [r for r in rows if r["decision"] == "setup" and r["trend_used"] == "DOWN"
                and (r.get("level") or {}).get("lo", 0) <= ZONE[1] and (r.get("level") or {}).get("hi", 0) >= ZONE[0]]
    if all(r["trend_used"] == "DOWN" for r in rows):
        assert not [r for r in rows if r["decision"] == "setup" and (r.get("level") or {}).get("role") == LV.SUP]
    L = V.levels.L[lvl["id"]]
    t = ix[-1]
    hi = float(m15["high"].iloc[ix].max())
    st = L.state_at(t)
    print(f"\n13 Oct: {len(ix)} bars, spot high {hi:,.2f} vs far swing {FAR_UP:,.1f} ⇒ state {st}, role {L.role_at(t)}; "
          f"trend {[r['trend_used'] for r in rows][-1]}")
    nxt = [w for w in (rows[-1].get("watch_list") or []) if w["role"] == LV.RES]
    print(f"13 Oct close watch-list: {[(w['lo'], w['hi'], w['state']) for w in nxt]}")
    assert nxt and nxt[0]["lo"] > ZONE[1]                                  # Abhi B2: the next seller zones above are already armed
    if hi > FAR_UP and (m15["close"].iloc[ix] > ZONE[1]).any():
        assert st == FL.DEAD                                               # Z-1f / Z-1k (Abhi: DEAD): second break past the far swing
    else:
        assert st in (FL.BROKEN, FL.FLIPPED) and L.role_at(t) == LV.RES    # not past 22,731.8 ⇒ no flip to support


# ------------------------------------------------------------------------------------------------ Abhi A / B: in-zone study, watch-list
def _zone_bars(kind, mirror):
    """A seller zone 100–102 (bear call, DOWN) and 9 in-zone bars arm … t − 1, then the decision bar t. kind "absorption": the buying
    (counter) candles grow and their volume rises inside the zone; kind "takeover": the selling candles grow on rising volume, the buying
    candles shrink, then a dominant red candle on high volume. Mirror: prices reflected (p ⇒ 2·MID − p), bull put. Volume = already
    slot-normalised values."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    if kind == "absorption":
        seq = [(101.0, 100.6, 1.0), (100.6, 100.9, 0.8), (100.9, 100.5, 1.0), (100.5, 100.8, 0.8),
               (100.8, 100.5, 1.0), (100.5, 101.4, 1.4), (101.4, 101.0, 1.0), (101.0, 101.9, 1.6), (101.9, 101.6, 1.0),
               (101.6, 100.9, 1.0)]
    else:
        seq = [(101.0, 101.4, 1.2), (101.4, 101.1, 0.9), (101.1, 101.5, 1.1), (101.5, 101.2, 0.9),
               (101.2, 101.4, 0.8), (101.4, 100.8, 1.3), (100.8, 101.0, 0.7), (101.0, 100.2, 1.5), (100.2, 100.4, 0.6),
               (100.4, 98.6, 2.5)]
    o = np.array([f(x[0]) for x in seq])
    c = np.array([f(x[1]) for x in seq])
    A = {"open": o, "close": c, "high": np.maximum(o, c) + 0.3, "low": np.minimum(o, c) - 0.3, "volume": np.array([x[2] for x in seq])}
    lvl = {"lo": min(f(100.0), f(102.0)), "hi": max(f(100.0), f(102.0))}
    return A, lvl, (UP if mirror else DOWN)


def _tss(n):
    return pd.date_range("2030-01-07 09:15", periods=n, freq="15min").to_numpy()


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_in_zone_absorption_is_no_trade(mirror):
    A, lvl, d = _zone_bars("absorption", mirror)
    t = len(A["close"]) - 1
    cf = M.confirm(A, 0, t, d, lvl, {**S, "ltf_choch": False})
    assert not cf["ok"] and cf["wait"] == M.C_ABSORB                      # counter side strengthening inside the zone ⇒ no entry
    z = FL.zone_read(A, _tss(t + 1), 0, t, d, lvl, S)
    assert z["summary"]["absorption"] is True and z["summary"]["handover"] is False


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_in_zone_seller_takeover_plus_commitment_is_a_trade(mirror):
    A, lvl, d = _zone_bars("takeover", mirror)
    t = len(A["close"]) - 1
    cf = M.confirm(A, 0, t, d, lvl, {**S, "ltf_choch": False})
    assert cf["ok"] and cf["c0"] and not cf["absorption"], cf["why"]
    assert cf["commit"]["vol_mult"] > 1.0 and cf["commit"]["form"]
    z = FL.zone_read(A, _tss(t + 1), 0, t, d, lvl, S)
    assert z["summary"]["trade_side_growing"] is True and z["summary"]["absorption"] is False


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_zone_broken_the_next_zone_is_already_armed(mirror):
    """Abhi B2: in a downtrend every supply ahead of price is armed, nearest first; the nearest breaks (the correction extends) ⇒ the
    next one is already on the list — no reset, no gap. Mirror: uptrend, demand zones below."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    anchors = [(0, 140), (6, 110), (10, 130), (18, 104), (26, 118), (34, 100), (40, 106), (50, 124)]
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("L"), f(110), 6, 8), P(sw("H"), f(130), 10, 12), P(sw("L"), f(104), 18, 20), P(sw("H"), f(118), 26, 28),
          P(sw("L"), f(100), 34, 36)]
    lv = _levels(m, p2, [])
    trend = "UP" if mirror else "DOWN"
    before = [x["id"] for x in lv.active(40, trend)]
    R1, R2 = lv.L[before[0]], lv.L[before[1]]                             # nearest first, the next one already armed
    assert len(before) >= 2 and abs(R2.anchor - f(130)) < 1e-6 and (R1.hi < R2.lo if not mirror else R1.lo > R2.hi)
    t_brk = next(b for b, k, _ in R1.events if k == "broken" and b > 40)
    after = [x["id"] for x in lv.active(t_brk, trend)]
    assert R1.id not in after and after[0] == R2.id and R1.state_at(t_brk) == FL.BROKEN
    assert all(R2.id in [x["id"] for x in lv.active(t, trend)] for t in range(40, len(m)))   # no gap in watching R2


# ------------------------------------------------------------------------------------------------ Abhi Z-1j / Z-1h
def test_range_state_is_context_only_never_an_entry_gate(abc, monkeypatch):
    """Abhi Z-1j: overlapping / sideways candles inside the zone are the handover study, not a blocker — §5.3 range state is reported as
    a context fact and never changes the decision (the old gate only with `range_state_gate` = True, legacy)."""
    m15, s, V, _ = abc
    bars = range(735, 746)
    base = {t: V.decide(t) for t in bars}
    monkeypatch.setattr(M, "range_state", lambda A, t, s=None: True)
    monkeypatch.setattr(M, "range_broken_by", lambda A, t, d, s=None: False)
    V2 = E3.V22(m15, s={**s, "c0_volume_required": False})
    for t in bars:
        r = V2.decide(t)
        assert (r["decision"], r["checklist"]["⑥"]) == (base[t]["decision"], base[t]["checklist"]["⑥"])
        if (r["checklist"].get("③") or [None])[0]:
            assert r["range_state"] is True and "§5.3" not in str(r["checklist"]["⑥"][1])
    V3 = E3.V22(m15, s={**s, "c0_volume_required": False, "range_state_gate": True})
    hit = [V3.decide(t) for t in bars if (V3.decide(t)["checklist"].get("③") or [None])[0]]
    assert hit and all("§5.3" in str(r["checklist"]["⑥"][1]) and r["decision"] == "wait" for r in hit)


def test_short_fut_history_falls_back_to_raw_per_bar_volume_not_a_data_error():
    """Abhi Z-1h: < vol_slot_min_sessions sessions of slot history ⇒ "volume normalisation: insufficient history", the window's
    comparisons use the RAW per-bar FUT volume — labelled in the row / payload, never a data-problem wait. FUT missing entirely stays the
    data error (Z-1c)."""
    import engine3_live as L
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    last = pd.to_datetime(m15["timestamp"]).dt.normalize().iloc[-1]
    days = sorted(pd.to_datetime(fut["timestamp"]).dt.normalize().unique())
    short = fut[pd.to_datetime(fut["timestamp"]).dt.normalize() >= days[-5]]                    # 4 earlier sessions only
    sv = {"level_death_side": "role", "level_flip_rule": "acceptance", "a2_handover_required": False}   # fixture's setup level (old pins)
    V = E3.V22(m15, s=sv, ltf=ltf, futures=short)
    ts = V.levels.ts
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last]
    A, label = V.vol_view(bars[0], bars[-1])
    assert label.startswith(V.INSUFFICIENT) and np.allclose(A["volume"][bars], V.levels.A["volume_raw"][bars], equal_nan=True)
    rows = [V.decide(t) for t in bars]
    assert not [r for r in rows if "data problem" in str(r["checklist"].get("⑥"))]
    seen = [r for r in rows if (r["checklist"].get("③") or [None])[0]]
    assert seen and all(r["volume_measure"].startswith(V.INSUFFICIENT) for r in seen)
    row = L.row_from_v22("NIFTY", seen[0], lambda: pd.Timestamp("2030-03-04 10:00"))
    assert "insufficient history" in row["payload"]
    full = E3.V22(m15, s=sv, ltf=ltf, futures=fut)
    assert full.vol_view(bars[0], bars[-1])[1].startswith("slot-normalised")


# ------------------------------------------------------------------------------------------------ volume baseline: incomplete FUT / rollover
def test_fut_present_but_incomplete_bar_is_na_with_reason_and_gaps_are_counted():
    """Reviewer (Z-1 volume): a 15M bar with < 3 of 3 FUT 5M children is marked incomplete — NA with a reason, never an under-counted
    sum; FUT present but with gaps inside the in-zone window ⇒ the label carries the gap count and the reason (no silent averaging)."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    ts15 = pd.to_datetime(m15["timestamp"])
    last = ts15.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts15)) if ts15.dt.normalize().iloc[i] == last]
    hole, gone = bars[3], bars[5]
    ft = pd.to_datetime(fut["timestamp"])
    drop = (ft == ts15.iloc[hole] + pd.Timedelta(minutes=5)) | ((ft >= ts15.iloc[gone]) & (ft < ts15.iloc[gone] + pd.Timedelta(minutes=15)))
    V = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut[~drop.to_numpy()].reset_index(drop=True))
    full = E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)
    raw = V.levels.A["volume_raw"]
    assert np.isnan(raw[hole]) and np.isfinite(full.levels.A["volume_raw"][hole])          # NA, not 2/3 of the bar
    assert np.isnan(V.levels.A["volume"][hole])
    assert V.vol_reason[hole] == "incomplete 15M FUT bar (2 of 3 5M bars)" and V.vol_reason[gone] == "no FUT bar"
    assert "incomplete 15M FUT bar (2 of 3 5M bars)" in V.vol_na_reason(hole) and "no FUT bar" in V.vol_na_reason(gone)
    _, label = V.vol_view(bars[0], bars[-1])
    assert f"FUT volume gaps: 2/{len(bars)} bars" in label and "incomplete 15M FUT bar" in label and "no FUT bar" in label
    assert "gaps" not in full.vol_view(bars[0], bars[-1])[1]
    ok = [i for i in bars if i not in (hole, gone)]                         # complete bars keep their exact volume
    assert np.allclose(raw[ok], full.levels.A["volume_raw"][ok])


def test_slot_baseline_excludes_rollover_days():
    """Reviewer: slot_rel_volume leaves FUT rollover days out of every baseline, as legs2.volume.rvol does."""
    days = pd.bdate_range("2030-01-01", periods=14)
    ts = pd.Series([d + pd.Timedelta(hours=9, minutes=15) for d in days])
    vol = np.full(len(ts), 100.0)
    vol[5] = 10000.0                                                        # a rollover-day spike
    rel, cnt = M.slot_rel_volume(ts, vol, sessions=20, min_sessions=10, exclude_days=[days[5]])
    _, cnt0 = M.slot_rel_volume(ts, vol, sessions=20, min_sessions=10)
    assert cnt[-1] == 12 and cnt0[-1] == 13 and rel[-1] == pytest.approx(1.0)
    rel2, cnt2 = M.slot_rel_volume(ts, np.where(np.arange(len(ts)) < 7, 1000.0, 100.0), sessions=20, min_sessions=3,
                                   exclude_days=list(days[:4]))
    rel3, _ = M.slot_rel_volume(ts, np.where(np.arange(len(ts)) < 7, 1000.0, 100.0), sessions=20, min_sessions=3)
    assert cnt2[-1] == 9 and rel2[-1] == pytest.approx(1.0)                 # baseline = days 4..12 ⇒ median 100
    assert rel3[-1] == pytest.approx(0.1)                                   # with the rollover days in, the baseline is inflated


# ------------------------------------------------------------------------------------------------ Telegram data-problem line (review)
def test_data_problem_day_marked_sent_only_after_a_successful_send(tmp_path):
    import engine_signal as ES
    p, now = str(tmp_path / "a.json"), pd.Timestamp("2030-01-07 10:16")
    calls = []

    def boom(line):
        calls.append(line)
        raise RuntimeError("telegram down")
    assert ES.alert_data_problem("NIFTY", "x", send=boom, state_path=p, now=now) is False
    assert ES.alert_data_problem("NIFTY", "x", send=lambda line: calls.append(line) or False, state_path=p, now=now) is False
    sent = []
    assert ES.alert_data_problem("NIFTY", "x", send=sent.append, state_path=p, now=now + pd.Timedelta(minutes=15)) is True
    assert len(calls) == 2 and len(sent) == 1                               # retried until it went through
    assert ES.alert_data_problem("NIFTY", "x", send=sent.append, state_path=p, now=now + pd.Timedelta(minutes=30)) is False


def test_data_problem_line_only_for_nifty_banknifty_never_sensex(tmp_path, monkeypatch):
    import json

    from scripts import engine_signal_run as ESR
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []

    def run(sym, tok):
        return {"bar_ts": "2030-01-07 10:15:00", "decision": "wait", "skipped": "test",
                "payload": json.dumps({"engine": "decision3", "data_problem": "data problem: FUT volume missing"})}
    ESR.main(["--symbols", "NIFTY,BANKNIFTY,SENSEX"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
             alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-07 10:16"))
    assert len(sent) == 2 and not [x for x in sent if "SENSEX" in x]
    assert ESR._data_problem(run("SENSEX", None), "SENSEX") is None and ESR._data_problem(run("NIFTY", None), "NIFTY")


def test_payload_size_limit_never_drops_the_data_problem_flag():
    import json

    import engine3_live as L
    big = {"engine": "decision3", "checklist": {"x": "y" * 30000}, "zone_read": {"z": "w" * 30000},
           "data_problem": "data problem: FUT volume missing (test)", "volume_measure": "slot-normalised"}
    out = L.fit_payload(big)
    d = json.loads(out)                                                     # valid JSON (no blind cut)
    assert len(out) <= L.PAYLOAD_MAX and d["data_problem"] == big["data_problem"] and d["dropped"] == ["checklist", "zone_read"]
    huge = {**big, "volume_note": "v" * 30000}
    d2 = json.loads(L.fit_payload(huge))
    assert d2["data_problem"] == big["data_problem"] and "all context" in d2["dropped"]
    small = {"engine": "decision3", "data_problem": None}
    assert L.fit_payload(small) == json.dumps(small)


def test_band_flip_facts_new_highs_use_first_confirmed_swing_after_break():
    """Review: band_flip_facts applies Abhi Z-1a like the engine (flip.far_swing) — no swing beyond the band before the break (new highs)
    ⇒ the far swing is the FIRST CONFIRMED swing beyond the band after the break; FLIPPED once price trades past it."""
    from facts import validity as FV
    hi = [96.5, 97.0, 96.0, 97.5, 96.5, 97.2, 96.0, 97.4, 96.4, 97.0] * 2                     # bars 0-19: below the 95-98 band top
    hi += [100.5, 101.5, 102.5, 103.0, 104.0, 103.0, 102.0, 101.5, 102.5, 103.5, 105.0, 104.5]  # break at 20, swing 104 @24, past it @30
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    df = pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl})
    B = FV.bars_of(df)
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 20, "dir": "up"}]}
    before = LV.band_flip_facts(B, 25, x, start=0)                          # swing @24 not yet confirmed (k = 2)
    assert before["flip_state"] == FL.BROKEN and before["far_swing"] is None
    mid = LV.band_flip_facts(B, 29, x, start=0)
    assert mid["flip_state"] == FL.BROKEN and mid["far_swing"]["bar"] == 24 and mid["far_swing"]["price"] == 104.0
    assert mid["far_swing"]["source"] == "first_confirmed_after_break"
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flip_state"] == FL.FLIPPED and f["flipped_at"]["bar"] == 30 and f["far_swing"]["bar"] == 24


# ------------------------------------------------------------------------------------------------ end to end on the DEFAULT path (review)
_HANDOVER = [(19436, 19458, 6e5), (19458, 19455, 2e5), (19455, 19466, 6e5), (19466, 19452, 5e5), (19452, 19455, 2e5), (19455, 19440, 7e5)]
_NO_HANDOVER = [(19436, 19458, 6e5), (19458, 19446, 4e5), (19446, 19462, 5e5), (19462, 19458, 3e5), (19458, 19468, 6e5),
                (19468, 19452, 3e5)]


def _default_case(window, commit_vol=1.2e6, with_fut=True):
    """tests.test_decision3_method._abc_m15 (Daily DOWN): its supply 19,432–19,472 is a support broken at bar 651 and FLIPPED at 659
    (price traded past the far swing before the break). Bars 735–740 are rewritten to sit in that zone (the in-zone study window), 741 is
    the bearish commitment. FUT 5M = 3 complete children per 15M bar (flat 3e5 elsewhere); LTF = 5M split of the same bars."""
    from tests.ltf_fixtures import split_bars
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    vol = np.full(len(m15), 3e5)
    for j, (o_, c_, v_) in enumerate(window):
        m15.loc[735 + j, ["open", "close", "high", "low"]] = [o_, c_, max(o_, c_) + 2, min(o_, c_) - 2]
        vol[735 + j] = v_
    m15.loc[741, ["open", "high"]] = [19440, 19443]
    vol[741] = commit_vol
    fut = pd.DataFrame({"timestamp": [t + pd.Timedelta(minutes=5 * j) for t in m15["timestamp"] for j in range(3)],
                        "volume": np.repeat(vol / 3.0, 3), "expiry": pd.Timestamp("2030-03-28")})
    return E3.V22(m15, ltf=split_bars(m15, 15, 3), futures=fut if with_fut else None)


def test_end_to_end_default_path_flipped_zone_handover_choch_commitment_with_volume_is_a_setup():
    """DEFAULT settings, no pins: far_swing flip rule + c0_volume_required + mandatory handover (a2) + LTF CHoCH, through V22.decide()."""
    V = _default_case(_HANDOVER)
    assert (V.s["level_flip_rule"], V.s["c0_volume_required"], V.s["a2_handover_required"], V.s["ltf_choch"], V.s["wave_gates"]) == \
        ("far_swing", True, True, True, False)
    r = V.decide(741)
    lv = r["level"]
    assert lv["state"] == FL.FLIPPED and lv["far_swing"]["source"] == "before_break" and lv["broken_at"] < lv["flipped_at"] < 735
    assert r["decision"] == "setup" and r["checklist"]["⑥"][0] is True and r["conviction"] in ("A", "B")
    cm = r["commit"]
    assert cm["handover_present"] is True and cm["arm_bar"] == 735 and cm["choch"]["done"] and cm["vol_mult"] > 1.0
    assert r["volume_measure"].startswith("slot-normalised") and not cm.get("data_problem")
    assert r["zone_read"]["summary"]["handover"] is True and r["checklist"]["G4"][0] is None
    early = V.decide(738)                                                  # CHoCH already done, handover not yet ⇒ wait (order: a2 first)
    assert early["decision"] == "wait" and "no handover" in early["checklist"]["⑥"][1]


def test_end_to_end_default_path_no_handover_or_no_fut_is_no_entry():
    r = _default_case(_NO_HANDOVER).decide(741)                             # same zone, CHoCH + commitment, but no handover
    assert r["decision"] == "wait" and (r["commit"] or {}).get("handover_present") is False
    assert "no handover" in r["checklist"]["⑥"][1]
    nf = _default_case(_HANDOVER, with_fut=False).decide(741)               # FUT missing ⇒ data problem, never a grade-B entry
    assert nf["decision"] == "wait" and "data problem" in nf["checklist"]["⑥"][1]
    lo = _default_case(_HANDOVER, commit_vol=1e5).decide(741)              # commitment without volume ⇒ no entry
    assert lo["decision"] == "wait" and "low volume" in lo["checklist"]["⑥"][1]
