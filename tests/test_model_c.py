"""T-3 model C (owner-orders DECISIONS 32; handover Appendix A; docs/reports/model_c/COVERAGE.md) — the counter-trend C leg, built behind
its switch (default OFF). Synthetic only (CI-safe), mirrored (the Daily UP trend's down correction). A bare V22 (as
tests/test_decision3_entry_models.py) with the 1H structure and the Daily state given; the entry models and every reader under them are
the real ones. Plus: switch OFF ⇒ engine rows byte-identical to the pre-change code (pinned digests), the settings register, the live
switch / tag / statistics family, the Vision audit facts and the card story line.

The synthetic correction (bull put while the Daily is DOWN; × −1 + 2·MID for the mirror):
  bars 0–14  the Daily-side down leg: H1 124 (bar 2) · L1 112 (6) · H2 120 (8, the protected lower high) · O 104 (14, the lower low)
  bars 14–21 wave A: big green candles on high FUT volume, the close above 120.2 at bar 19 = the 1H CHoCH up; HA 130 at bar 21
  bars 21–33 wave B: small overlapping candles on low volume down into the 1H demand area 114–116 (base in A, bar 17)
"""
import hashlib
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import model_c as MC
from decision3 import mtf_state as MS
from decision3 import settings as S3

MID = 120.0
AREA = {"entry_area_refine": "area"}       # the model mechanics read the area itself (the refined base has its own tests)
ON = {**AREA, "model_c": "on"}


# ------------------------------------------------------------------------------------------------ the synthetic correction
def _path(points):
    """Waypoints [(bar, price, volume, wobble)] ⇒ 15M rows (open, high, low, close, volume): straight steps between waypoints; wobble
    > 0 ⇒ every other candle steps back (overlapping, corrective)."""
    p0, v0 = points[0][1], points[0][2]
    rows = [(p0, p0 + 0.2, p0 - 0.2, p0, v0)]                             # bar b closes at waypoint b
    for (b0, p0, _v0, _w0), (b1, p1, v1, w1) in zip(points, points[1:]):
        step = (p1 - p0) / (b1 - b0)
        c = p0
        for k in range(b1 - b0):
            o = c
            nxt = p0 + step * (k + 1)
            c = nxt + (w1 if (k % 2 == 0 and k < b1 - b0 - 1) else 0.0) * (1 if step < 0 else -1)
            rows.append((o, max(o, c) + 0.2, min(o, c) - 0.2, c, v1))
    return rows


BASE = [(0, 121.0, 1.0, 0), (2, 124.0, 1.5, 0), (6, 112.0, 1.5, 0), (8, 120.0, 1.5, 0), (14, 104.0, 1.5, 0),   # Daily-side leg
        (21, 130.0, 4.0, 0),                                                                                  # A (impulse)
        (33, 114.6, 1.0, 1.3), (37, 122.0, 1.0, 0)]                                                           # B (corrective) + bounce
D2 = [("H", 124.0, 2, 4), ("L", 112.0, 6, 8), ("H", 120.0, 8, 10), ("L", 104.0, 14, 16), ("H", 130.0, 21, 23)]


def _rows(points=BASE):
    rows = _path(points)
    return rows


def _swing_prices(rows, sw):
    """The swings at the rows' own extremes (the wick)."""
    out = []
    for k, _p, b, c in sw:
        px = rows[b][1] if k == "H" else rows[b][2]
        out.append((k, float(px), b, c))
    return out


def _mirror_rows(rows):
    return [(2 * MID - o, 2 * MID - lo, 2 * MID - h, 2 * MID - c, v) for o, h, lo, c, v in rows]


def _mirror_sw(sw):
    return [({"H": "L", "L": "H"}[k], 2 * MID - p, b, c) for k, p, b, c in sw]


def _band(lo, hi, mirror):
    return (2 * MID - hi, 2 * MID - lo) if mirror else (lo, hi)


def build(rows, d2=None, fine=None, areas=(), s=None, mirror=False, daily="DOWN", snapshot=None, events=None):
    """A bare V22 for model C: rows (open, high, low, close, volume); d2 / fine = (kind, price, bar, confirm_bar) swings (the 1H D2
    structure / the finest structure — default the same list); areas = [(id, lo, hi, base_bar, role, state, born_bar)]."""
    d2 = list(D2 if d2 is None else d2)
    d2 = _swing_prices(rows, d2)
    fine = d2 if fine is None else _swing_prices(rows, fine)
    if mirror:
        rows, d2, fine = _mirror_rows(rows), _mirror_sw(d2), _mirror_sw(fine)
        daily = {"DOWN": "UP", "UP": "DOWN"}.get(daily, daily)
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load({**ON, **(s or {})})
    MC.validate(V.s)
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    A["volume"] = np.array([r[4] for r in rows], float)
    A["volume_raw"] = A["volume"].copy()
    ts = pd.DatetimeIndex([pd.Timestamp("2030-01-07 09:30") + pd.Timedelta(days=i // 20, minutes=15 * (i % 20))   # every bar inside
                           for i in range(len(rows))])                                                     # the entry hours
    Ls, act = [], []
    for (lid, lo, hi, bb, role, state, born) in areas:
        if mirror:
            lo, hi = 2 * MID - hi, 2 * MID - lo
            role = LV.RES if role == LV.SUP else LV.SUP
        ev = []
        Ls.append(NS(id=lid, born_bar=born, base_bar=bb, role0=role, tf="1H", lo=lo, hi=hi, band_at=lambda u, lo=lo, hi=hi: (lo, hi),
                     state_at=lambda u, st=state: st, events=ev, dead_bar=None))
        act.append({"id": lid, "lo": lo, "hi": hi, "role": role, "tf": "1H", "state": state, "births": ["a:D2"], "sweeps": 0,
                    "fresh": state == FL.ACTIVE, "confluence": [], "trade_location": True, "born_bar": born})
    piv = [NS(kind=k, price=float(p), bar=b, confirm_bar=c, warmup=False) for k, p, b, c in d2]
    V.levels = NS(A=A, _known0=sorted((NS(kind=k, price=float(p), bar=b, confirm_bar=c) for k, p, b, c in fine),
                                      key=lambda p: p.confirm_bar),
                  L=Ls, ts=pd.Series(ts), known_pivots=lambda t: [], _pv_sorted=[],
                  snapshot=snapshot or (lambda t: []),
                  active=lambda t, trend, band=None: [x for x in act if x["born_bar"] <= t and
                                                      x["role"] == (LV.SUP if trend == "UP" else LV.RES)])
    V._ts = ts.to_numpy()
    V.bar_end = pd.Series(ts + pd.Timedelta(minutes=15))
    V.ltf, V.vol_reason, V.vol_roll, V.vol_hist = None, {}, set(), None
    V.step1 = lambda u: (True, "", None, {"trend": daily})
    V.pb = NS(at=lambda t, d: None)
    V.res = {"pivots": {2: piv, 1: [NS(kind=k, price=float(p), bar=b, confirm_bar=c, warmup=False) for k, p, b, c in fine]}}
    evs = MS.dow_events(piv, A["close"]) if events is None else events
    V._mc_inputs = (piv, evs, daily)
    return V


@pytest.fixture(autouse=True)
def _inputs(monkeypatch):
    """The bare V carries its own 1H structure and Daily state (the real readers are mtf_state / daily, pinned elsewhere)."""
    real_s, real_d = MC.structure, MC.dstate

    def structure(V):
        return (V._mc_inputs[0], V._mc_inputs[1], None) if hasattr(V, "_mc_inputs") else real_s(V)

    def dstate(V, t):
        if not hasattr(V, "_mc_inputs"):
            return real_d(V, t)
        tr = V._mc_inputs[2]
        tr = tr(t) if callable(tr) else tr
        return (NS(trend=tr, phase="correction", counter=None, corr_label=None, rev=None, protected=NS(price=150.0), wave_a=None),
                NS(trend=tr))
    monkeypatch.setattr(MC, "structure", structure)
    monkeypatch.setattr(MC, "dstate", dstate)


C_AREA = [(0, 114.0, 116.0, 17, LV.SUP, FL.ACTIVE, 18)]


def fired(V, bars, d):
    out = {}
    for t in bars:
        cyc = MC.cycle(V, t, d)
        ents = MC.entries_at(V, t, cyc)[0] if cyc.get("alive") and any(cyc["windows"].values()) else []
        if ents:
            out[t] = ents
    return out


def _dir(mirror):
    return -1 if mirror else 1


# ------------------------------------------------------------------------------------------------ the cycle
@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_a_needs_a_choch_then_b_window_opens_and_c_a_e1_fires(mirror):
    rows = _rows()
    V = build(rows, areas=C_AREA, mirror=mirror)
    d = _dir(mirror)
    assert MC.cycle(V, 18, d)["phase"] == "none" and "CHoCH" in MC.cycle(V, 18, d)["why"]   # no close beyond 120.2 yet ⇒ no A
    c19 = MC.cycle(V, 19, d)
    assert c19["phase"] == "A running" and c19["choch"]["bar"] == 19 and c19["O"]["bar"] == 14 and not c19["windows"]["b"]
    assert MC.cycle(V, 22, d)["phase"] == "A running"                     # HA (bar 21) is read only from its confirm bar (23)
    c = MC.cycle(V, 30, d)
    assert c["phase"] == "B in progress" and c["HA"]["bar"] == 21 and c["a_nature"]["verdict"] == "impulse", c
    assert c["b_nature"]["verdict"] == "correction" and c["windows"]["b"], c
    got = fired(V, range(15, len(rows)), d)
    assert got, "non-vacuous: the B pullback into the A demand fires model C"
    e = [x for t in got for x in got[t]]
    assert all(x["family"] == "C" and x["sub_model"] == "C-a" and x["direction"] == d for x in e)
    assert [x["model"] for x in e][0] == "E1" and len({x["key"] for x in e}) == len(e)
    first = e[0]
    assert first["visit_id"].startswith("C:0@") and first["key"].startswith("C:") and first["c_label"] == "C · E1"
    assert first["side"] == ("bear_call" if mirror else "bull_put")
    assert "Counter C leg — Daily " + ("UP" if mirror else "DOWN") in first["story"] and "invalidated if B closes" in first["story"]
    assert first["model_c"]["O"]["bar"] == 14 and first["model_c"]["HA"]["bar"] == 21
    assert first["model_c"]["end_zone"]["use"].startswith("context only")


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_no_choch_no_model_c(mirror):
    """A needs a CHoCH: the same up leg that stays below the protected lower high (no close beyond it) is no wave A."""
    pts = [(0, 121.0, 1.0, 0), (2, 124.0, 1.5, 0), (6, 112.0, 1.5, 0), (8, 120.0, 1.5, 0), (14, 104.0, 1.5, 0),
           (21, 119.0, 4.0, 0), (33, 108.0, 1.0, 1.0), (37, 114.0, 1.0, 0)]
    rows = _rows(pts)
    V = build(rows, areas=[(0, 107.0, 109.0, 16, LV.SUP, FL.ACTIVE, 17)], mirror=mirror)
    d = _dir(mirror)
    assert all(MC.cycle(V, t, d)["phase"] == "none" for t in range(len(rows)))
    assert fired(V, range(len(rows)), d) == {}


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_daily_side_not_against_gives_no_model_c(mirror):
    rows = _rows()
    V = build(rows, areas=C_AREA, mirror=mirror, daily="RANGE")
    assert all(not MC.cycle(V, t, _dir(mirror))["alive"] for t in range(len(rows)))


# ------------------------------------------------------------------------------------------------ B death
DIP = [(0, 121.0, 1.0, 0), (2, 124.0, 1.5, 0), (6, 112.0, 1.5, 0), (8, 120.0, 1.5, 0), (14, 104.0, 1.5, 0),
       (21, 130.0, 4.0, 0), (29, 103.0, 1.0, 1.3), (30, 105.0, 1.0, 0), (36, 115.5, 1.0, 0), (40, 113.0, 1.0, 0)]


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_b_beyond_o_with_a_swing_kills_the_cycle(mirror):
    """B closes below O (104) AND a swing of the finest structure forms below O (103, bar 29) ⇒ dead: no more model C entries, even
    when price later comes back to the A demand area."""
    rows = _rows(DIP)
    fine = D2 + [("L", 103.0, 29, 31)]
    V = build(rows, fine=fine, areas=[(0, 114.0, 116.0, 17, LV.SUP, FL.ACTIVE, 18)], mirror=mirror)
    d = _dir(mirror)
    assert MC.cycle(V, 30, d)["alive"]                                     # the swing below O is not known before its confirm bar
    c = MC.cycle(V, 31, d)
    assert c["phase"] == "dead" and not c["alive"] and c["dead"]["swing"]["bar"] == 29
    assert all(MC.cycle(V, t, d)["phase"] == "dead" for t in range(31, len(rows)))
    assert not [t for t in fired(V, range(len(rows)), d) if t >= 31]


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_one_candle_beyond_o_without_a_swing_keeps_b_alive(mirror):
    """The same dip below O without a swing formed beyond it (no finest-structure swing below 104) ⇒ a sweep, B alive (C-c)."""
    rows = _rows(DIP)
    V = build(rows, fine=D2 + [("L", 110.0, 34, 36)], areas=[(0, 114.0, 116.0, 17, LV.SUP, FL.ACTIVE, 18)], mirror=mirror)
    d = _dir(mirror)
    assert all(MC.cycle(V, t, d)["phase"] != "dead" for t in range(len(rows)))
    assert MC.cycle(V, 33, d)["alive"]


# ------------------------------------------------------------------------------------------------ the window: never after / on a break of HA
HA_BAND = (129.0, 130.2)                                                    # HA's own 1H supply (base = HA's bar 21)
AFTER_HA = [(130.0, 130.1, 127.9, 128.1, 1.0), (128.1, 128.5, 125.8, 126.0, 1.0), (126.0, 126.6, 124.3, 124.6, 1.0),   # 22–24 B
            (124.6, 127.5, 124.5, 127.3, 2.0), (127.3, 129.6, 127.1, 129.4, 2.0),                                       # 25–26
            (129.4, 131.2, 129.2, 131.0, 2.5),                                                                          # 27 BREAK of HA
            (131.0, 133.4, 130.8, 133.2, 2.5), (133.2, 135.6, 133.0, 135.4, 2.5), (135.4, 136.2, 134.6, 134.8, 1.0),     # 28–30 push
            (134.8, 135.0, 133.0, 133.2, 1.0), (133.2, 133.4, 131.4, 131.6, 1.0), (131.6, 131.8, 130.4, 130.6, 1.0),     # 31–33
            (130.6, 130.8, 129.3, 129.6, 1.0),                                                                          # 34 first return
            (129.6, 131.6, 129.4, 131.5, 3.0),                                                                          # 35 rejection
            (131.5, 133.5, 131.3, 133.3, 2.0), (133.3, 135.5, 133.1, 135.3, 2.0), (135.3, 137.6, 135.1, 137.4, 2.0),     # 36–38
            (137.4, 137.6, 136.0, 136.2, 1.0), (136.2, 136.4, 134.0, 134.2, 1.0), (134.2, 134.4, 132.0, 132.2, 1.0),     # 39–41
            (132.2, 132.4, 130.3, 130.5, 1.0), (130.5, 130.6, 129.2, 129.5, 1.0),                                       # 42–43 2nd return
            (129.5, 131.6, 129.4, 131.5, 3.0),                                                                          # 44 rejection
            (131.5, 131.6, 128.0, 128.2, 1.0), (128.2, 128.3, 124.0, 124.2, 1.0), (124.2, 124.3, 120.0, 120.2, 1.0),     # 45–47 down
            (120.2, 120.3, 117.0, 117.2, 1.0), (117.2, 117.3, 115.2, 115.5, 1.0), (115.5, 116.0, 114.3, 114.6, 1.0),     # 48–50 into
            (114.6, 116.8, 114.5, 116.6, 3.0), (116.6, 118.8, 116.4, 118.6, 2.0)]                                       # the A area
HA_FINE = D2 + [("L", 124.3, 24, 26), ("H", 136.2, 30, 32), ("L", 129.3, 34, 36), ("H", 137.6, 38, 40), ("L", 129.2, 43, 45),
                ("L", 114.3, 50, 52)]


def _ha_case(mirror, s=None, broken_from=33):
    rows = _rows()[:22] + AFTER_HA
    lo, hi = HA_BAND
    role, bd = (LV.SUP, -1) if mirror else (LV.RES, 1)
    blo, bhi = _band(lo, hi, mirror)
    br = {"id": 1, "lo": blo, "hi": bhi, "role": role, "state": FL.BROKEN, "break_dir": bd, "broken_at": broken_from, "tf": "1H",
          "trade_location": True, "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}
    areas = C_AREA + [(1, lo, hi, 21, LV.RES, FL.BROKEN, 23)]
    V = build(rows, fine=HA_FINE, areas=areas, mirror=mirror, s=s, snapshot=lambda t: [br] if t >= broken_from else [])
    return rows, V


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_no_model_c_entry_after_a_close_beyond_ha_b_only(mirror):
    """b_only (default): the first close beyond HA (bar 27) closes the window — the later pullback into the A demand area (bars 50–51)
    and the returns to HA give no model C entry; before the break the window was open (B in progress). Appendix A: "With C-e ON,
    c_window = b_and_ha_retest" — so with the C-e switch on, the first HA return (and only it) is the one entry after the break."""
    no_e = [x for x in S3.MODEL_C_SUBS if x != "C-e"]
    rows, V = _ha_case(mirror, s={"model_c_subs": no_e})
    d = _dir(mirror)
    assert MC.cycle(V, 26, d)["windows"]["b"]
    c = MC.cycle(V, 27, d)
    assert c["phase"] == "C underway" and c["ha_close"]["bar"] == 27 and not any(c["windows"].values())
    got = fired(V, range(len(rows)), d)
    assert not [t for t in got if t >= 27], got
    rows, V = _ha_case(mirror)                                              # every sub on (C-e forces the HA-return window)
    got = fired(V, range(len(rows)), d)
    assert {t: [e["sub_model"] for e in got[t]] for t in got if t >= 27} == {35: ["C-e"]}


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_never_an_entry_on_the_break_of_ha_only_the_first_return(mirror):
    """C-e (c_window b_and_ha_retest): the breakout candle of HA (27) and the push (28–33) never fire; the FIRST return to HA's broken
    area (34) is rejected at 35 ⇒ one E4 (b) labelled C-e; the second return (43–44) is not model C (the first return ended by the
    swing away at 38, known at 40)."""
    rows, V = _ha_case(mirror, s={"c_window": "b_and_ha_retest"})
    d = _dir(mirror)
    got = fired(V, range(len(rows)), d)
    after = {t: [(e["sub_model"], e["model"], e["object"]) for e in got[t]] for t in got if t >= 27}
    assert after == {35: [("C-e", "E4", "broken_area")]}, after
    e = got[35][0]
    assert e["family"] == "C" and e["visit_id"].startswith("C:1@") and "first return to HA" in e["story"]
    assert e["model_c"]["window"] == "first return to HA"
    c40 = MC.cycle(V, 40, d)
    assert c40["ha_return"]["end_known"] == 40 and not c40["windows"]["e"]
    assert 27 not in got                                                   # H2: never on the candle that breaks HA


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_c_e_needs_its_own_switch(mirror):
    rows, V = _ha_case(mirror, s={"c_window": "b_and_ha_retest", "model_c_subs": ["C-a", "C-b"]})
    got = fired(V, range(len(rows)), _dir(mirror))
    assert not [t for t in got if t >= 27]


# ------------------------------------------------------------------------------------------------ no look-ahead
def _sig(V, t, d):
    cyc = MC.cycle(V, t, d)
    ents = MC.entries_at(V, t, cyc)[0] if cyc.get("alive") and any(cyc["windows"].values()) else []
    return (json.dumps(MC.brief(cyc), sort_keys=True, default=str),
            [(e["key"], e["model"], e["sub_model"], e["invalidation"], e["trigger_bar"]) for e in ents])


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
@pytest.mark.parametrize("case", ["b_pullback", "ha_return"])
def test_no_look_ahead_the_read_at_t_equals_the_read_on_data_cut_at_t(mirror, case):
    """Truncation-safe (as tests/test_pa_candle_forms.py): the cycle and the C entries at bar t are the same whether the data runs on
    or ends at t (swings known only from their confirm bar, the 1H events by close, legs on bars ≤ t)."""
    d = _dir(mirror)
    if case == "b_pullback":
        rows, fine, areas, s, snap = _rows(), D2, C_AREA, None, None
        V = build(rows, areas=areas, mirror=mirror)
    else:
        rows, V = _ha_case(mirror, s={"c_window": "b_and_ha_retest"})
        fine, s = HA_FINE, {"c_window": "b_and_ha_retest"}
        areas = C_AREA + [(1, HA_BAND[0], HA_BAND[1], 21, LV.RES, FL.BROKEN, 23)]
        snap = V.levels.snapshot
    seen = 0
    for k in range(14, len(rows)):
        cut = [x for x in D2 if x[3] <= k]
        Vk = build(rows[:k + 1], d2=cut, fine=[x for x in fine if x[3] <= k], areas=areas, mirror=mirror, s=s, snapshot=snap)
        full, part = _sig(V, k, d), _sig(Vk, k, d)
        assert full == part, (k, full, part)
        seen += bool(full[1])
    assert seen, "non-vacuous: an entry bar was compared"


# ------------------------------------------------------------------------------------------------ sub-model switches, labels
def test_sub_model_switches_are_independent():
    rows = _rows()
    base = fired(build(rows, areas=C_AREA), range(len(rows)), 1)
    assert base and all(e["sub_model"] == "C-a" for t in base for e in base[t])
    only_a = fired(build(rows, areas=C_AREA, s={"model_c_subs": ["C-a"]}), range(len(rows)), 1)
    assert {t: [e["key"] for e in v] for t, v in only_a.items()} == {t: [e["key"] for e in v] for t, v in base.items()}
    for other in (["C-b"], ["C-c"], ["C-d"], ["C-e"], ["C-f"], []):
        assert fired(build(rows, areas=C_AREA, s={"model_c_subs": other}), range(len(rows)), 1) == {}, other
    rows, V = _ha_case(False, s={"model_c_subs": ["C-e"]})
    got = fired(V, range(len(rows)), 1)
    assert {t: [e["sub_model"] for e in v] for t, v in got.items()} == {35: ["C-e"]}


def test_c_c_wins_over_c_a_for_a_sweep_beyond_o_and_lines_are_c_b_or_c_d():
    cyc = {"d": 1, "O": {"price": 104.0}}
    e4a = {"object": "area", "model": "E4", "facts": {"sweep_extreme": 103.5}, "area": {"id": 0}}
    assert MC._sub_of(e4a, cyc) == "C-c"
    assert MC._sub_of({**e4a, "facts": {"sweep_extreme": 104.5}}, cyc) == "C-a"
    assert MC._sub_of({"object": "area", "model": "E2", "facts": {}, "area": {"id": 0}}, cyc) == "C-a"
    assert MC._sub_of({"object": "broken_line", "model": "E4", "area": {"id": "line:pat:sym_triangle:upper:30"}}, cyc) == "C-d"
    assert MC._sub_of({"object": "broken_line", "model": "E4", "area": {"id": "line:D2:H-:21-27"}}, cyc) == "C-b"
    assert MC._sub_of({**e4a, "facts": {"sweep_extreme": 104.5}}, {"d": -1, "O": {"price": 104.0}}) == "C-c"   # mirror


def test_b_channel_and_triangle_objects_must_lie_inside_b(monkeypatch):
    cyc = {"d": 1, "HA": {"bar": 21}}
    ln = {"id": "D2:H-:22-28", "p1": [22, 128.0], "p2": [28, 125.0], "slope": -0.5}
    assert MC.keep_b(None, 30, cyc)("line", ln)
    assert not MC.keep_b(None, 30, cyc)("line", {**ln, "p1": [12, 128.0]})        # anchored before HA: not B's line
    assert not MC.keep_b(None, 30, cyc)("area", {"id": 3})
    base = {"id": "D2:L-:23-29", "p1": [23, 124.0], "p2": [29, 121.0], "slope": -0.5}
    monkeypatch.setattr(MC.TL, "channel_lines", lambda V, t, degree=None: [base])
    assert MC.keep_b(None, 30, cyc)("line", {"id": "D2:L-:23-29|par", "parallel_of": base["id"], "p1": [25, 127.0], "p2": [26, 126.5]})
    tri = {"id": "pat:sym_triangle:upper:22", "swing_bars": [21, 24, 26, 28]}
    assert MC.keep_d(cyc)("line", tri) and not MC.keep_d(cyc)("line", {**tri, "swing_bars": [18, 24, 26, 28]})
    assert not MC.keep_d(cyc)("line", ln)


def test_projections_are_display_only_never_read_on_an_entry_path():
    """C-7: `c_projections` changes only the end-zone context (and its words), never an entry, its trigger or its invalidation; the
    source reads it only in model_c.end_zone (and its validation)."""
    import inspect
    import pathlib
    import re
    rows = _rows()
    a = fired(build(rows, areas=C_AREA), range(len(rows)), 1)
    b = fired(build(rows, areas=C_AREA, s={"c_projections": (0.618, 1.0, 1.618)}), range(len(rows)), 1)
    sig = lambda g: {t: [(e["key"], e["invalidation"], e["trigger_bar"], e["model"]) for e in v] for t, v in g.items()}   # noqa: E731
    assert sig(a) == sig(b) and a
    e0, e1 = a[min(a)][0], b[min(b)][0]
    assert len(e0["model_c"]["end_zone"]["projections"]) == 1 and len(e1["model_c"]["end_zone"]["projections"]) == 3
    d3 = pathlib.Path(MC.__file__).parent
    readers = {f.name for f in d3.glob("*.py") if re.search(r"[\"']c_projections[\"']", f.read_text(encoding="utf-8"))}
    assert readers == {"settings.py", "model_c.py"}
    src = inspect.getsource(MC)
    allowed = inspect.getsource(MC.end_zone) + inspect.getsource(MC.validate)
    assert src.count('"c_projections"') == allowed.count('"c_projections"')


# ------------------------------------------------------------------------------------------------ settings + the switch
def test_settings_registered_default_off_and_validated():
    d = S3.DEFAULTS
    assert (d["model_c"], d["c_a_nature"], d["c_window"], tuple(d["c_projections"])) == ("off", "impulse", "b_only", (1.0,))
    assert tuple(d["model_c_subs"]) == ("C-a", "C-b", "C-c", "C-d", "C-e", "C-f")
    for k in ("model_c", "model_c_subs", "c_a_nature", "c_window"):
        assert S3.REGISTER[k][2] == "Abhi नियम" and ("Appendix A" in S3.REGISTER[k][3] or "DECISIONS 32" in S3.REGISTER[k][3])
    assert S3.REGISTER["c_projections"][2] == "setting" and "display" in S3.REGISTER["c_projections"][1]
    for bad in ({"model_c": "yes"}, {"model_c_subs": ["C-z"]}, {"model_c_subs": "C-a"}, {"c_a_nature": "five"},
                {"c_window": "c_only"}, {"c_projections": (0.0,)}, {"c_projections": "1.0"}):
        with pytest.raises(ValueError):
            MC.validate(S3.load(bad))
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    with pytest.raises(ValueError, match="model_c"):
        E3.V22(m15, s={"model_c": "maybe"}, ltf=ltf, futures=fut)


DISPLAY_ONLY = ("channels_htf",)            # PA T3 / T9 display keys added after the pin (tests/test_pa_evidence.py pins them apart)


def _digest(rows, drop=()):
    rows = [{k: (v if k != "entries" else [{a: b for a, b in e.items() if a != "pa_evidence"} for e in v])
             for k, v in r.items() if k not in drop and k not in DISPLAY_ONLY} for r in rows]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


# the engine rows of the pre-change code (git bf280a8, before model C), computed on these fixtures
PIN = {"abc": "ffca376184284461cef1a5eca17648ddc56d24349c7dd09a6f8c6320a46fd35c",
       "oct12_bear": "a2671001dc3a16da5eb9b4b8ca0c32cdc9c9a0617c261cc18e6ac5b55412e61d",
       "oct12_bull": "e80cb1a7f9001d3a9d416435af8f1825119579433b56f49b817bafd10f3f16fd"}


def _fixture_rows(name, extra):
    if name == "abc":
        from tests.test_decision3_method import _abc_m15
        s = {"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_volume_required": False, **extra}
        return E3.V22(_abc_m15(), s=s).run()
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=name == "oct12_bull")
    V = E3.V22(m15, s={"level_death_side": "role", **extra}, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    return [V.decide(t) for t in range(len(ts)) if ts.dt.normalize().iloc[t] == last]


@pytest.mark.parametrize("name", sorted(PIN))
def test_switch_off_engine_rows_are_byte_identical_to_the_pre_change_code(name):
    """model_c = off (default, and set explicitly) ⇒ every engine row byte-identical to the code before model C (pinned digests); ON ⇒
    the same rows plus the `model_c` key only (no CHoCH-up cycle in these fixtures ⇒ no C entry, the Daily side untouched)."""
    assert _digest(_fixture_rows(name, {})) == PIN[name]
    assert _digest(_fixture_rows(name, {"model_c": "off"})) == PIN[name]
    on = _fixture_rows(name, {"model_c": "on"})
    assert all("model_c" in r and not r["model_c"].get("error") for r in on if r.get("entry_gate") == "models")
    assert _digest(on, drop=("model_c",)) == PIN[name]


# ------------------------------------------------------------------------------------------------ the real readers end to end
def _real_m15(n_cycles=16, impulse=900.0, pb=0.7, a_mult=1.6, b_frac=0.88, seed=1):
    """A synthetic Daily DOWN trend (fast impulses, single-leg pullbacks on lower FUT volume), then the counter-trend correction: an
    impulsive up leg A, a deep corrective B, a C push and the Daily side back."""
    rng = np.random.default_rng(seed)
    path, px = [], 22000.0
    for _ in range(n_cycles):
        low = px - impulse
        px = low + impulse * pb
        path += [(low, 40, "imp"), (px, 40, "pb")]
    low = px - impulse
    A = low + impulse * a_mult
    path += [(low, 40, "imp"), (A, 30, "imp"), (A - impulse * a_mult * b_frac, 50, "pb"), (A + impulse * 0.8, 50, "pb"),
             (A - impulse, 40, "imp")]
    closes, styles, cur = [], [], 22000.0
    for tgt, nb, st in path:
        for x in np.linspace(cur, tgt, nb + 1)[1:]:
            closes.append(x)
            styles.append(st)
        cur = tgt
    days = pd.bdate_range("2030-01-07", periods=len(closes) // 25 + 2)
    rows, prev = [], 22000.0
    for i, (c0, st) in enumerate(zip(closes, styles)):
        ts = days[i // 25] + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % 25))
        c = c0 + rng.normal(0, 6 if st == "pb" else 3)
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": prev, "high": max(prev, c) + abs(rng.normal(0, 5)),
                     "low": min(prev, c) - abs(rng.normal(0, 5)), "close": c, "volume": 3000.0 if st == "imp" else 1000.0})
        prev = c
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def real_v():
    s = {"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_volume_required": False, "model_c": "on"}
    return E3.V22(_real_m15(), s=s)


def test_real_readers_read_the_cycle_and_the_c_areas(real_v):
    """The real chain (swings2 D2 swings + mtf_state events, the 1H candles for the leg comparison, Levels.base_bar, Levels.active):
    the up correction reads A = the CHoCH up with an impulse nature, B corrective in progress, the C areas = O's own swing area and the
    CHoCH BOS-origin base (base inside A) — the FLIPPED old lower-high supply is not a C area (Q6); after the close above HA the cycle
    is C underway and the first return to HA's area opens the C-e window. Decide rows carry `model_c` with no error."""
    V = real_v
    ch = [e for e in MC.structure(V)[1] if e["type"] == "CHoCH" and e["dir"] == 1]
    assert ch, "non-vacuous: the synthetic correction makes a 1H CHoCH up"
    cb = ch[-1]["bar"]
    b_bars = [t for t in range(cb, len(V.m15)) if MC.cycle(V, t, 1)["phase"] == "B in progress"]
    assert b_bars
    t = b_bars[-1]
    c = MC.cycle(V, t, 1)
    assert c["a_nature"]["verdict"] == "impulse" and c["b_nature"]["verdict"] == "correction" and c["windows"]["b"]
    assert c["O"]["bar"] < c["choch"]["bar"] <= c["HA"]["bar"] < c["HA"]["known_bar"] <= t
    ca = MC.areas(V, t, c, c["O"]["bar"], c["HA"]["bar"])
    assert ca and all(x["tf"] == "1H" and x["state"] in ("ACTIVE", "TESTED") for x in ca)
    births = {b for x in ca for b in x["births"]}
    assert "b" in births and "a:D2" in births
    assert not [x for x in V.levels.active(t, "UP") if x["state"] == FL.FLIPPED and x in ca]
    later = [MC.cycle(V, u, 1) for u in range(t + 1, len(V.m15))]
    assert any(x["phase"] == "C underway" for x in later) and any(x["windows"]["e"] for x in later)
    r = V.decide(t)
    assert r["model_c"]["cycle"]["id"] == c["id"] and "error" not in r["model_c"]
    ez = MC.end_zone(V, t, c)
    assert ez["first_htf_area"] is None or float(ez["first_htf_area"]["lo"]) > c["HA"]["price"]
    assert MC.evidence(V, t, c)["b_volume_vs_a"] == "lower"


# ------------------------------------------------------------------------------------------------ independent review fixes (PR #370)
def test_ha_area_is_read_as_known_at_t_no_look_ahead():
    """Review (MEDIUM 2): Levels builds the whole series, so HA's area is only a level born by t and alive at t; a level with the same
    base bar born later (e.g. a later 'd' pair on HA's swing) is never used before its birth; when HA's own birth fell inside an alive
    band (lineage only — Level.inside_bases), that band is the area at HA from the merge bar on."""
    later = NS(id=5, tf="1H", base_bar=21, role0=LV.RES, born_bar=40, dead_bar=None, lo=129.5, hi=130.2, births=["d"],
               band_at=lambda u: (129.5, 130.2))
    host = NS(id=3, tf="1H", base_bar=8, role0=LV.RES, born_bar=10, dead_bar=None, lo=128.8, hi=130.4, births=["a:D2"],
              inside_bases=[(23, 21, LV.RES)], band_at=lambda u: (128.8, 130.4))
    dead = NS(id=6, tf="1H", base_bar=21, role0=LV.RES, born_bar=23, dead_bar=30, lo=129.0, hi=130.2, band_at=lambda u: (129.0, 130.2))
    V = NS(levels=NS(L=[later, host, dead]))
    assert MC._ha_area(V, 22, 21, 1) is None                              # nothing known yet
    assert MC._ha_area(V, 25, 21, 1)["id"] == 6                           # HA's own area (born at 23)
    a = MC._ha_area(V, 35, 21, 1)                                         # 6 died at 30; 5 is not born yet ⇒ the host band (lineage)
    assert a["id"] == 3 and "lineage" in a["how"]
    assert MC._ha_area(V, 41, 21, 1)["id"] == 5                           # from its birth on, the band born at HA's swing wins
    assert MC._ha_area(V, 35, 21, -1) is None                             # the mirror role only


def test_real_levels_record_a_birth_inside_an_alive_band():
    """Levels._born: a birth wholly inside an alive same-role band is lineage only — the additive inside_bases keeps its base bar."""
    lv = LV.Levels.__new__(LV.Levels)
    lv.s, lv.L = S3.load({}), []
    host = lv._born(10, LV.RES, 128.0, 131.0, "a:D2", 130.5, base_bar=8)
    same = lv._born(23, LV.RES, 129.0, 130.2, "a:D2", 130.2, base_bar=21)
    assert same is host and host.inside_bases == [(23, 21, LV.RES)] and host.base_bar == 8 and len(lv.L) == 1
    assert MC._ha_area(NS(levels=lv), 23, 21, 1)["id"] == host.id and MC._ha_area(NS(levels=lv), 22, 21, 1) is None


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_c_e_object_unchanged_by_a_later_level_at_ha_truncation(mirror):
    """The C-e read at the first return (35) with a later-born level on HA's swing (born 44, listed first) is the same as on data cut
    at 35 (where that level does not exist yet)."""
    rows = _rows()[:22] + AFTER_HA
    areas = [(2, 129.6, 130.2, 21, LV.RES, FL.ACTIVE, 44)] + C_AREA + [(1, HA_BAND[0], HA_BAND[1], 21, LV.RES, FL.BROKEN, 23)]
    lo, hi = _band(*HA_BAND, mirror)
    br = {"id": 1, "lo": lo, "hi": hi, "role": LV.SUP if mirror else LV.RES, "state": FL.BROKEN, "break_dir": -1 if mirror else 1,
          "broken_at": 33, "tf": "1H", "trade_location": True, "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}
    snap = lambda t: [br] if t >= 33 else []                                # noqa: E731
    s = {"c_window": "b_and_ha_retest"}
    d = _dir(mirror)
    V = build(rows, fine=HA_FINE, areas=areas, mirror=mirror, s=s, snapshot=snap)
    Vk = build(rows[:36], d2=[x for x in D2 if x[3] <= 35], fine=[x for x in HA_FINE if x[3] <= 35],
               areas=[a for a in areas if a[6] <= 35], mirror=mirror, s=s, snapshot=snap)
    assert MC.cycle(V, 35, d)["ha_area"]["id"] == 1 == MC.cycle(Vk, 35, d)["ha_area"]["id"]
    assert _sig(V, 35, d) == _sig(Vk, 35, d) and _sig(V, 35, d)[1]


def test_attach_rolls_back_when_c_f_fails(monkeypatch):
    """Review (LOW 4): a model C error after the C entries were read leaves the row's entries exactly as they were (fail closed)."""
    rows = _rows()
    V = build(rows, areas=C_AREA)
    t = min(fired(V, range(len(rows)), 1))
    daily = {"model": "E1", "direction": -1, "visit_id": "9@x", "area": {"lo": 140.0, "hi": 141.0}}
    row = {"entries": [daily]}
    MC.attach(V, t, row)
    assert len(row["entries"]) > 1 and row["entries"][0] == daily and "error" not in row["model_c"]

    def boom(*a, **k):
        raise RuntimeError("c-f")
    monkeypatch.setattr(MC, "tag_cf", boom)
    row = {"entries": [daily]}
    MC.attach(V, t, row)
    assert row["entries"] == [daily] and row["entries"][0] is daily and "c-f" in row["model_c"]["error"]


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_c_pullbacks_window_never_opens_on_the_break_candle(mirror):
    """Review (LOW 5): c_pullbacks (what-if) opens from the bar AFTER the first close beyond HA — never on the break candle (H2)."""
    rows, V = _ha_case(mirror, s={"c_window": "c_pullbacks", "model_c_subs": ["C-a"]})
    d = _dir(mirror)
    assert not MC.cycle(V, 27, d)["windows"]["cp"] and MC.cycle(V, 28, d)["windows"]["cp"]
    assert 27 not in fired(V, range(len(rows)), d)


@pytest.mark.parametrize("mirror", [False, True], ids=["bull_put", "bear_call_mirror"])
def test_b_and_ha_retest_without_c_e_reads_as_b_only(mirror):
    """Review (LOW 6, provisional — REGISTER): b_and_ha_retest opens the HA first return for the C-e sub-way only; without C-e the
    entries equal b_only's and the HA-return window stays shut."""
    no_e = [x for x in S3.MODEL_C_SUBS if x != "C-e"]
    d = _dir(mirror)
    rows, Vb = _ha_case(mirror, s={"model_c_subs": no_e})
    _, Vr = _ha_case(mirror, s={"model_c_subs": no_e, "c_window": "b_and_ha_retest"})
    sig = lambda g: {t: [e["key"] for e in v] for t, v in g.items()}       # noqa: E731
    assert sig(fired(Vb, range(len(rows)), d)) == sig(fired(Vr, range(len(rows)), d))
    assert not any(MC.cycle(Vr, t, d)["windows"]["e"] for t in range(len(rows)))
    assert "C-e sub-way ONLY" in S3.REGISTER["c_window"][3]
