"""Abhi 22 Oct (consolidated, item 2) — sweep / fakeout behaviour of the entry models, synthetic fixtures (CI-safe), both mirrors:

  a. a close beyond the area WITHOUT a swing beyond, then back inside = a sweep / fakeout (K4): the area stays alive and the visit
     continues (the real K4 reader logs a "sweep", never "broken"; the models stay armed, same visit);
  b. E4 (a) fires when the next push fails inside the sweep extreme; invalidation beyond the sweep extreme;
  c. E2 / E3 may still fire later in the same visit (the trigger candle trades into the refined base) and their invalidation includes
     the sweep extreme;
  d. E1 does not come back after a sweep (the first touch only, once per visit);
  e. a close beyond + a swing beyond = the area broken (flip); a later return from the other side = the retest of the flipped area ⇒
     E4 (b), and the area's own models are disarmed;
  plus: base_broken after a single close beyond the REFINED BASE (inside the context area) only ends E1 — the area is not broken and
  E2 / E3 / E4 still fire in the same visit.

The context area is 100–104 (a supply; bull put = the mirror), the refined 15M base 103.0–103.5 (tests/test_entry_models_inside_area.py
REF). The entry-model tests read K4 events given to the bare reader (as every entry-model test does); the K4 reader itself is read on
the same shape in test_k4_* below (decision3/levels.py, default break rule)."""
import pandas as pd
import pytest

from decision3 import entry_models as EM
from decision3 import flip as FL
from decision3 import levels as LV
from tests.test_decision3_entry_models import MID, _bare, _ltf_from, _mirror_rows
from tests.test_entry_models_inside_area import REF, REF_SW

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
REFINE = {"entry_area_refine": "setup_tf"}
LEGACY = {**REFINE, "entry_trigger_rule": "legacy"}
SWEEP_EVENT = [(10, "sweep", "closed back inside before a swing formed beyond (K4)")]

# 0–8 = REF (bar 8 reaches the refined base ⇒ E1). Bar 9 CLOSES beyond the area's far edge (104) with its high at 104.6; bar 10 is back
# inside; bar 11 = the next push, failing inside the sweep extreme (a swing high 103.9 inside the area, known at 12) ⇒ E4 (a) at 12;
# bar 13 pushes back up into the base, bar 14 = the dominant red commitment (E2) trading into the base.
SWEEP = REF[:9] + [(103.1, 104.6, 103.0, 104.3, 1.0),   # 9  closes beyond the far edge (no swing beyond follows)
                   (104.3, 104.4, 103.3, 103.5, 1.0),   # 10 back inside the area
                   (103.5, 103.9, 103.3, 103.8, 1.0),   # 11 the next push fails inside 104.6 (swing high, known at 12)
                   (103.8, 103.85, 102.6, 102.7, 1.0),  # 12 ⇒ E4 (a): the confirmation bar trades into the base
                   (102.7, 103.85, 102.6, 103.8, 1.0),  # 13 back up into the base
                   (103.8, 103.85, 100.5, 100.6, 5.0),  # 14 dominant red on volume, trading into the base ⇒ E2
                   (100.6, 100.8, 100.2, 100.4, 1.0)]   # 15
SWEEP_SW = REF_SW + [("H", 103.9, 11, 12)]


def _v(rows, mirror, s=REFINE, events=SWEEP_EVENT, sw=SWEEP_SW, ltf=False):
    rr = _mirror_rows(rows) if mirror else rows
    return _bare(rows, sw, band=(100.0, 104.0), mirror=mirror, s=s, events=events, ltf=_ltf_from(rr) if ltf else None)


def _m(x, mirror):
    return 2 * MID - x if mirror else x


def _run(V, lvl, d, bars):
    R = EM.Reader(V)
    return {t: R.area(t, lvl, d) for t in bars}


# ------------------------------------------------------------------------------------------------ a / b / c / d on one visit
@MIRRORS
def test_sweep_close_beyond_without_swing_beyond_keeps_the_area_and_the_visit(mirror):
    V, lvl, d = _v(SWEEP, mirror)
    st = _run(V, lvl, d, range(8, len(SWEEP)))
    starts = {st[t][0]["visit_start_bar"] for t in st}
    assert starts == {6}                                                   # a: one visit across the sweep
    assert not any(st[t][0].get("disarmed") for t in st)                   # a: the area stays alive, the models stay armed
    assert st[9][1] == []                                                  # the bar closing beyond is never a trigger


@MIRRORS
def test_e4a_fires_when_the_next_push_fails_inside_the_sweep_extreme(mirror):
    V, lvl, d = _v(SWEEP, mirror)
    st = _run(V, lvl, d, range(8, len(SWEEP)))
    e4 = [(t, f) for t in st for f in st[t][1] if f["model"] == "E4"]
    assert [t for t, _ in e4] == [12]
    f = e4[0][1]
    assert f["invalidation"] == pytest.approx(_m(104.6, mirror)) and "sweep extreme" in f["invalidation_rule"]   # b
    assert f["facts"]["sweep_bar"] == 10 and f["facts"]["push_bar"] == 11


@MIRRORS
def test_e2_e3_after_the_sweep_trade_into_the_base_and_include_the_sweep_extreme(mirror, monkeypatch):
    monkeypatch.setattr(EM.Reader, "c1", lambda self, u, l, dd, st: {"done": u >= 14, "line": "LTF CHoCH (test)"})
    V, lvl, d = _v(SWEEP, mirror)
    st = _run(V, lvl, d, range(8, len(SWEEP)))
    fired = {t: {f["model"]: f for f in st[t][1]} for t in st}
    assert "E2" in fired[14] and "E3" in fired[14]                         # c: later in the same visit
    assert not any(m in fired[t] for t in range(8, 14) for m in ("E2", "E3"))
    for m in ("E2", "E3"):
        assert fired[14][m]["invalidation"] == pytest.approx(_m(104.6, mirror))   # c: includes the sweep extreme
    A = V.levels.A
    rb = fired[14]["E2"]["refined"]
    assert float(A["low"][14]) <= float(rb["hi"]) and float(A["high"][14]) >= float(rb["lo"])   # the candle trades into the base
    # the same commitment candle trading into the context area only (not the base) never fires after the sweep (control: legacy)
    short = SWEEP[:14] + [(103.5, 103.6, 100.5, 100.6, 5.0)] + SWEEP[15:]
    V2, lvl2, d2 = _v(short, mirror)
    a14, f14 = EM.Reader(V2).area(14, lvl2, d2)
    assert not {"E2", "E3"} & {f["model"] for f in f14} and "refined 15M base" in a14["models"]["E2"]["waiting"]
    V0, lvl0, d0 = _v(short, mirror, s=LEGACY)
    assert "E2" in {f["model"] for f in EM.Reader(V0).area(14, lvl0, d0)[1]}


@MIRRORS
def test_e1_does_not_come_back_after_a_sweep(mirror):
    V, lvl, d = _v(SWEEP, mirror)
    st = _run(V, lvl, d, range(8, len(SWEEP)))
    assert [t for t in st for f in st[t][1] if f["model"] == "E1"] == [8]  # d: the first touch only, once
    assert all(st[t][0]["models"]["E1"]["status"] == "fired_earlier" for t in range(9, len(SWEEP)))
    # the first bar at the base IS the sweep candle (closing beyond): no E1 there, and none when price comes back inside
    first = REF[:8] + [(102.0, 104.6, 101.9, 104.3, 1.0), (104.3, 104.4, 103.2, 103.4, 1.0)] + SWEEP[11:]
    V, lvl, d = _v(first, mirror, events=[(9, "sweep", "K4")])
    st = _run(V, lvl, d, range(8, len(first)))
    assert not [t for t in st for f in st[t][1] if f["model"] == "E1"]
    assert "E1 re-arms with the next visit" in st[10][0]["models"]["E1"]["waiting"]
    assert not any(st[t][0].get("disarmed") for t in st)


# ------------------------------------------------------------------------------------------------ base_broken ends only E1
@MIRRORS
def test_a_close_beyond_the_refined_base_only_ends_e1(mirror, monkeypatch):
    """Bar 6 enters the area ABOVE the refined base and closes beyond its far edge (103.9 > 103.5, still inside the context 100–104):
    base_broken ⇒ E1 never fires in this visit. The area is NOT broken (no K4 event, models armed) and E2 / E3 / E4 (a) still fire."""
    monkeypatch.setattr(EM.Reader, "c1", lambda self, u, l, dd, st: {"done": u >= 8, "line": "LTF CHoCH (test)"})
    rows = REF[:6] + [(103.8, 103.95, 103.6, 103.9, 1.0),     # 6  closes beyond the base's far edge (inside the context)
                      (103.9, 103.95, 103.2, 103.3, 1.0),     # 7  back into the base
                      (103.3, 103.4, 100.5, 100.6, 5.0),      # 8  dominant red trading into the base ⇒ E2 + E3
                      (100.6, 101.0, 100.3, 100.9, 1.0),      # 9
                      (100.9, 104.4, 100.8, 103.8, 1.0),      # 10 sweep beyond the area's far edge, closes back inside
                      (103.8, 103.9, 102.9, 103.0, 1.0),      # 11
                      (103.0, 103.6, 102.8, 103.4, 1.0),      # 12 the next push fails inside 104.4 (swing high, known at 13)
                      (103.4, 103.45, 102.0, 102.1, 1.0),     # 13 ⇒ E4 (a), trading into the (newer) base
                      (102.1, 102.2, 101.0, 101.1, 1.0)]      # 14
    V, lvl, d = _v(rows, mirror, events=[], sw=REF_SW + [("H", 103.6, 12, 13)])
    st = _run(V, lvl, d, range(6, len(rows)))
    fired = {t: [f["model"] for f in st[t][1]] for t in st}
    assert not any("E1" in v for v in fired.values())
    assert "closed through in this visit" in st[7][0]["models"]["E1"]["waiting"]
    assert not any(st[t][0].get("disarmed") for t in st) and {st[t][0]["visit_start_bar"] for t in st} == {6}
    assert "E2" in fired[8] and "E3" in fired[8] and fired[13] == ["E4"]
    e4 = st[13][1][0]
    assert e4["invalidation"] == pytest.approx(_m(104.4, mirror))


# ------------------------------------------------------------------------------------------------ e: broken (flip) ⇒ disarmed; E4 (b)
@MIRRORS
def test_close_beyond_plus_swing_beyond_disarms_the_area_models(mirror):
    V, lvl, d = _v(SWEEP, mirror, events=[(12, "broken", "close beyond + swing beyond (K4)")])
    a, f = EM.Reader(V).area(14, lvl, d)
    assert f == [] and "broke inside this visit" in a["disarmed"]
    assert all(x["status"] == "disarmed" for x in a["models"].values())


@MIRRORS
def test_return_to_the_flipped_area_from_the_other_side_is_e4b(mirror, monkeypatch):
    """The supply 100–104 broken UP (close beyond + swing beyond ⇒ BROKEN / flipped to demand, break_dir +1 = the bull put's direction);
    price comes back down to it from above and a green rejection closes above it ⇒ E4 (b) for the bull put, invalidation = the retest
    extreme. Mirror: a demand broken down, revisited from below, bear call."""
    rows = [(103.0, 103.2, 101.8, 102.0, 1.0), (102.0, 105.5, 101.9, 105.3, 1.0), (105.3, 107.2, 105.2, 107.0, 1.0),   # 0–2 break up
            (107.0, 107.1, 106.0, 106.2, 1.0), (106.2, 106.3, 105.4, 105.5, 1.0), (105.5, 105.6, 104.4, 104.6, 1.0),   # 3–5 back down
            (104.6, 104.7, 103.6, 103.8, 1.0),                                                                       # 6 at the area
            (103.8, 105.1, 103.7, 105.0, 1.0), (105.0, 106.0, 104.9, 105.9, 1.0)]                                    # 7 rejection up
    sw = [("H", 107.2, 2, 3)]
    br = {"id": 1, "lo": 100.0, "hi": 104.0, "role": LV.RES, "state": FL.BROKEN, "break_dir": 1, "broken_at": 1,
          "trade_location": True, "tf": "1H", "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}
    if mirror:
        br = {**br, "lo": 2 * MID - 104.0, "hi": 2 * MID - 100.0, "role": LV.SUP, "break_dir": -1}
    from types import SimpleNamespace as NS
    L1 = NS(id=1, born_bar=0, state_at=lambda u: FL.BROKEN, events=[], dead_bar=None)
    # the bull put side for the original (bear-call-shaped) rows: the broken supply is the bull put's retest; mirror = bear call
    V, _lvl, _d = _bare(rows, sw, mirror=mirror, snapshot=lambda t: [br], extra_L=[L1], s=REFINE,
                        trend_at=lambda u: "DOWN" if mirror else "UP")
    d = -1 if mirror else 1
    import decision3.method as M
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1) if t == 7 else None)
    got = {t: EM.Reader(V).broken(t, d) for t in range(2, len(rows))}
    fired = [(t, f) for t, (_a, fs) in got.items() for f in fs]
    assert [t for t, _ in fired] == [7] and fired[0][1]["variant"] == "b" and fired[0][1]["facts"]["object"] == "broken_area"
    assert fired[0][1]["invalidation"] == pytest.approx(_m(103.6, mirror))   # the retest extreme


# ------------------------------------------------------------------------------------------------ the REAL K4 reader feeding the models
# tests/test_decision3_zone_answers._break_case: a resistance 117–118 (mirror: support), price closes above it; with `beyond` a finer
# swing forms above the band (K4 "broken" when it is confirmed), otherwise price returns inside first (K4 "sweep"). Here the real
# Levels object is the reader's levels, so the area's lifecycle comes from decision3/levels.py itself, not from given events.
def _real(beyond, mirror, tail=None):
    from tests.test_decision3_zone_answers import _break_case, _zone
    m, lv, f = _break_case(beyond, mirror, tail=tail)
    Z = _zone(lv, f)
    rows = list(zip(m["open"], m["high"], m["low"], m["close"], [1.0] * len(m)))
    V, _l, _d = _bare(rows, [], s={"entry_area_refine": "area"})
    V.levels = lv
    V._ts = pd.to_datetime(m["timestamp"]).to_numpy()
    V.bar_end = pd.to_datetime(m["bar_end"]).reset_index(drop=True)
    return V, Z, m


@MIRRORS
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_real_k4_sweep_keeps_the_area_armed_and_the_visit_while_broken_disarms_it(mirror):
    d = 1 if mirror else -1                                                # resistance ⇒ bear call; mirror: support ⇒ bull put
    V, Z, m = _real(False, mirror)
    n = len(m)
    assert [k for _, k, _ in Z.events if k in ("broken", "flip", "dead")] == [] and Z.count("sweep", n - 1) >= 1   # a (K4)
    lvl = {"id": Z.id, "lo": Z.band_at(n - 1)[0], "hi": Z.band_at(n - 1)[1], "role": Z.role_at(n - 1), "tf": "1H"}
    st = {t: EM.Reader(V).area(t, lvl, d)[0] for t in range(17, n)}
    assert {a["visit_start_bar"] for a in st.values()} == {17} and not any(a.get("disarmed") for a in st.values())   # a
    V, Z, m = _real(True, mirror)
    brk = [b for b, k, _ in Z.events if k == "broken"]
    assert brk == [22]                                                     # e: close beyond + swing beyond = broken
    lvl = {"id": Z.id, "lo": Z.band_at(21)[0], "hi": Z.band_at(21)[1], "role": Z.role_at(21), "tf": "1H"}
    assert not EM.Reader(V).area(21, lvl, d)[0].get("disarmed")
    a = EM.Reader(V).area(22, lvl, d)[0]
    assert "broke inside this visit" in a["disarmed"] and all(x["status"] == "disarmed" for x in a["models"].values())


@MIRRORS
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_real_k4_broken_area_retested_from_the_other_side_is_e4b(mirror, monkeypatch):
    """e: after the real K4 break (bar 22), price stays beyond, then comes back to the band from the other side (bar 27) and a rejection
    candle closes away (bar 28) ⇒ E4 (b) in the break direction (bull put for a resistance broken up; mirror: bear call)."""
    import decision3.method as M
    V, Z, m = _real(True, mirror, tail=[119.5, 121.0, 122.0, 121.0, 119.5, 118.3, 119.8, 121.5])
    d = -1 if mirror else 1
    V.step1 = lambda u: (True, "", None, {"trend": "DOWN" if mirror else "UP"})
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1) if t == 28 else None)
    snap = next(x for x in V.levels.snapshot(len(m) - 1) if x["id"] == Z.id)
    assert snap["state"] == FL.BROKEN and snap["break_dir"] == d
    fired = [(t, f) for t in range(22, len(m)) for f in EM.Reader(V).broken(t, d)[1]]
    assert [t for t, _ in fired] == [28] and fired[0][1]["variant"] == "b" and fired[0][1]["facts"]["object"] == "broken_area"
    ext = float(m["low"].iloc[27:29].min()) if not mirror else float(m["high"].iloc[27:29].max())
    assert fired[0][1]["invalidation"] == pytest.approx(ext)              # beyond the retest extreme
