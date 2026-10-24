"""Abhi 21 Oct — the entry models (decision3/entry_models.py, `entry_gate = models`), the visit-end fix and the both-side lines.
Synthetic only (CI-safe); mirrored where a side matters. The real days (29 Sep / 12 Oct / 13 Oct) stay pinned to `entry_gate =
legacy_k` in tests/test_decision3_flip.py (their old expectations unchanged); what the new default reads there is reported, not asserted.

  • E1 aggressive: the first bar of a NEW visit — once; invalidation = the area's far edge;
  • E2 confirmation: the commitment candle (c0 with its volume test) — once per visit; invalidation = the visit's extreme;
  • E3 structure: the LTF CHoCH (c1) — once per visit; invalidation = the visit's extreme;
  • E4 (a) sweep: beyond the far edge, back inside, the next push fails inside the sweep extreme; (b) a BROKEN area / line revisited
    and a rejection candle closing away — invalidation = the sweep / retest extreme;
  • up to four entries per visit; models disarm on a K4 break inside the visit, at the visit's end (they re-arm with the next visit)
    and on a trend-side change; a breakout bar never fires (H2);
  • a visit ends only by structure — one candle (a commitment) closing outside never ends it (legacy_k keeps the old end);
  • lines on both sides: rising / falling lines of highs AND lows, with anchors, touches and the K6.5 break state.
"""
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import entry_models as EM
from decision3 import levels as LV
from decision3 import method as M
from decision3 import settings as S3
from decision3 import trendline as TL
from tests.test_decision3 import P, m15_from, res_of

UP, DOWN = M.UP, M.DOWN
MID = 101.0
# The model mechanics below read ONE area as the trade location (`entry_area_refine = area`); the RC2 refined 15M base (research default
# `setup_tf`) and the inside-the-area rule have their own tests in tests/test_entry_models_inside_area.py.
AREA = {"entry_area_refine": "area"}
# The oct12 fixture's trigger bar spikes up through the area and closes below it (the trade side): under the 21 Oct RC3 wording
# (`inside`, #364) it was no entry; under Abhi's 22 Oct reading (`traded_inside`, default) it traded inside the area and its close away
# is the confirmation ⇒ E1 / E3 fire there, so the row-shape tests read it with the default trigger again (the 12 Oct conflict resolved).
LEGACY = {**AREA, "entry_trigger_rule": "legacy"}

# A supply 100–102 (bear call). (open, high, low, close, volume)
BEAR = [(97.0, 97.6, 96.8, 97.5, 1.0),       # 0  swing low (built away from the area) — the approach leg starts after it
        (97.5, 98.6, 97.4, 98.5, 1.0),       # 1  approach
        (98.5, 99.4, 98.4, 99.3, 1.0),       # 2  approach
        (99.3, 100.6, 99.2, 100.4, 1.0),     # 3  enters the area ⇒ a new visit (E1)
        (100.4, 101.2, 100.2, 101.0, 1.0),   # 4  green inside
        (101.0, 102.8, 100.9, 101.6, 1.0),   # 5  wick above the far edge 102, closes back inside ⇒ sweep (extreme 102.8)
        (101.6, 101.7, 100.0, 100.1, 5.0),   # 6  dominant red engulf on higher volume ⇒ commitment (E2)
        (100.1, 101.3, 100.0, 101.2, 1.0),   # 7  push up again
        (101.2, 101.9, 100.8, 100.9, 1.0),   # 8  the push fails below 102.8 (swing high, confirmed at 9)
        (100.9, 101.0, 100.05, 100.1, 1.0),  # 9  ⇒ E4 (a) at the swing's confirmation (closes inside the area: the models fire
                                             #    only while price is inside it, Abhi 21 Oct)
        (99.6, 99.7, 98.0, 98.1, 1.0)]       # 10
SWINGS = [("L", 96.8, 0, 1), ("H", 102.8, 5, 6), ("H", 101.9, 8, 9)]


def _mirror_rows(rows):
    return [(2 * MID - o, 2 * MID - lo, 2 * MID - h, 2 * MID - c, v) for o, h, lo, c, v in rows]


def _mirror_sw(sw):
    return [({"H": "L", "L": "H"}[k], 2 * MID - p, b, c) for k, p, b, c in sw]


def _bare(rows, swings=(), band=(100.0, 102.0), mirror=False, events=(), s=None, trend_at=None, ltf=None, snapshot=None, extra_L=()):
    """A bare V22 for the entry models: rows = (open, high, low, close, volume); swings = (kind, price, bar, confirm_bar) of the finest
    structure; one area (id 0) born at bar 0; trend_at(u) ⇒ the trend at bar u (default DOWN / UP mirrored)."""
    if mirror:
        rows, swings = _mirror_rows(rows), _mirror_sw(swings)
        band = (2 * MID - band[1], 2 * MID - band[0])
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load({**AREA, **(s or {})})
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    A["volume"] = np.array([r[4] for r in rows], float)
    A["volume_raw"] = A["volume"].copy()
    ts = pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min")
    L0 = NS(id=0, born_bar=0, state_at=lambda u: "ACTIVE", events=list(events), dead_bar=None)
    V.levels = NS(A=A, _known0=[NS(kind=k, price=float(p), bar=b, confirm_bar=c) for k, p, b, c in swings], L=[L0, *extra_L],
                  ts=pd.Series(ts), snapshot=snapshot or (lambda t: []), known_pivots=lambda t: [], _pv_sorted=[])
    V._ts = ts.to_numpy()
    V.bar_end = pd.Series(ts + pd.Timedelta(minutes=15))
    V.ltf, V.vol_reason, V.vol_roll, V.vol_hist = ltf, {}, set(), None
    trend = "UP" if mirror else "DOWN"
    V.step1 = lambda u: (True, "", None, {"trend": (trend_at(u) if trend_at else trend)})
    V.pb = NS(at=lambda t, d: None)
    role = LV.SUP if mirror else LV.RES
    lvl = {"id": 0, "lo": band[0], "hi": band[1], "role": role, "tf": "1H", "state": "ACTIVE", "births": ["a:D2"], "sweeps": 0,
           "fresh": True, "confluence": []}
    return V, lvl, (UP if mirror else DOWN)


def _statuses(V, lvl, d, bars):
    out = {}
    for t in bars:
        a, fired = EM.Reader(V).area(t, lvl, d)
        out[t] = (a, fired)
    return out


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_each_model_fires_once_per_visit_with_its_invalidation(mirror):
    V, lvl, d = _bare(BEAR, SWINGS, mirror=mirror)
    st = _statuses(V, lvl, d, range(0, len(BEAR)))
    fired = {t: [f["model"] for f in st[t][1]] for t in st}
    assert st[2][0] is None                                                # not visiting ⇒ nothing armed
    assert fired[3] == ["E1"] and fired[6] == ["E2"] and fired[9] == ["E4"]   # E3 waits: no LTF data (fail-closed)
    assert sum(len(v) for v in fired.values()) == 3                         # each at most once in the visit
    inv = {f["model"]: f for t in st for f in st[t][1]}
    far = 2 * MID - 102.0 if mirror else 102.0
    assert inv["E1"]["invalidation"] == pytest.approx(far)                  # E1: beyond the area's far edge
    assert inv["E2"]["invalidation"] == pytest.approx(2 * MID - 102.8 if mirror else 102.8)   # E2: the visit's extreme
    e4 = inv["E4"]
    assert e4["invalidation"] == pytest.approx(2 * MID - 102.8 if mirror else 102.8) and e4["variant"] == "a"
    assert e4["facts"]["sweep_bar"] == 5 and e4["facts"]["push_bar"] == 8 and e4["facts"]["push_known_bar"] == 9
    last = st[10][0]["models"]
    assert last["E1"]["status"] == "fired_earlier" and last["E2"]["status"] == "fired_earlier" and last["E4"]["status"] == "fired_earlier"
    assert st[9][0]["models"]["E3"]["status"] == "waiting" and "LTF data missing" in st[9][0]["models"]["E3"]["waiting"]
    assert last["E3"]["status"] == "waiting" and "price has left the area" in last["E3"]["waiting"]   # bar 10 closes below the area
    assert st[10][0]["visit_id"].startswith("0@2030-01-07 10:00") and st[10][0]["side"] == ("bull_put" if mirror else "bear_call")


def _ltf_from(rows):
    """5M bars from the 15M rows: each 15M bar = open → (high, low in the candle's order) → close."""
    out = []
    for i, (o, h, lo, c, _v) in enumerate(rows):
        t0 = pd.Timestamp("2030-01-07 09:15") + pd.Timedelta(minutes=15 * i)
        path = [o, h, lo, c] if c < o else [o, lo, h, c]
        for j in range(3):
            a, b = path[j], path[j + 1]
            out.append({"timestamp": t0 + pd.Timedelta(minutes=5 * j), "open": a, "high": max(a, b), "low": min(a, b), "close": b})
    df = pd.DataFrame(out)
    df["bar_end"] = df["timestamp"] + pd.Timedelta(minutes=5)
    return M.ltf_frame(df, 5, "5M")


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_up_to_four_entries_in_one_visit_and_e3_fires_once_on_the_ltf_choch(mirror):
    rows = _mirror_rows(BEAR) if mirror else BEAR
    V, lvl, d = _bare(BEAR, SWINGS, mirror=mirror, ltf=_ltf_from(rows))
    st = _statuses(V, lvl, d, range(3, len(BEAR)))
    fired = [(t, f["model"]) for t in st for f in st[t][1]]
    assert sorted(m for _, m in fired) == ["E1", "E2", "E3", "E4"]           # four models, one visit, each once
    t3 = next(t for t, m in fired if m == "E3")
    e3 = next(f for f in st[t3][1] if f["model"] == "E3")
    ext = max(V.levels.A["high"][3:t3 + 1]) if not mirror else min(V.levels.A["low"][3:t3 + 1])
    assert e3["invalidation"] == pytest.approx(ext) and "CHoCH" in e3["facts"]["line"]
    assert st[len(BEAR) - 1][0]["models"]["E3"]["status"] in ("fired_earlier", "fired")


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_models_disarm_when_the_area_breaks_inside_the_visit(mirror):
    V, lvl, d = _bare(BEAR, SWINGS, mirror=mirror, events=[(7, "broken", "close beyond + swing beyond")])
    a, fired = EM.Reader(V).area(9, lvl, d)
    assert fired == [] and "broke inside this visit" in a["disarmed"] and all(x["status"] == "disarmed" for x in a["models"].values())
    a6, f6 = EM.Reader(V).area(6, lvl, d)                                    # before the break: still armed (E2 at 6)
    assert [f["model"] for f in f6] == ["E2"] and not a6.get("disarmed")


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_models_rearm_with_a_new_visit_after_a_swing_away(mirror):
    rows = BEAR + [(98.1, 98.2, 97.3, 97.4, 1.0),          # 11 swing low away from the area (confirmed at 12)
                   (97.4, 98.4, 97.35, 98.3, 1.0),         # 12
                   (98.3, 99.3, 98.2, 99.2, 1.0),          # 13
                   (99.2, 100.5, 99.1, 100.3, 1.0)]        # 14 back into the area ⇒ a new visit
    sw = SWINGS + [("L", 97.3, 11, 12)]
    V, lvl, d = _bare(rows, sw, mirror=mirror)
    a13, f13 = EM.Reader(V).area(13, lvl, d)
    assert a13 is None and f13 == []                                        # the visit ended by structure
    a14, f14 = EM.Reader(V).area(14, lvl, d)
    assert [f["model"] for f in f14] == ["E1"] and a14["visit_start_bar"] == 14   # a new key (area + visit start + model)
    assert a14["models"]["E2"]["status"] == "waiting"


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_models_disarm_on_a_trend_side_change_and_rearm_from_the_new_side(mirror):
    trend = "UP" if mirror else "DOWN"
    V, lvl, d = _bare(BEAR, SWINGS, mirror=mirror, trend_at=lambda u: "NEUTRAL" if u in (5, 6) else trend)
    a, fired = EM.Reader(V).area(7, lvl, d)
    assert a["side_since"].startswith("2030-01-07 11:00") and fired == []
    assert a["models"]["E1"]["status"] == "passed" and "trend side changed" in a["models"]["E1"]["waiting"]
    assert a["models"]["E2"]["status"] == "waiting"                        # the 10:45 commitment was read while no trade side ⇒ not counted
    _a9, f9 = EM.Reader(V).area(9, lvl, d)
    assert [f["model"] for f in f9] == ["E4"]


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_a_breakout_bar_never_fires_and_off_models_stay_off(mirror):
    rows = list(BEAR)
    rows[3] = (99.3, 102.9, 99.2, 102.5, 1.0)                              # the visit's first bar closes beyond the far edge (breakout)
    V, lvl, d = _bare(rows, SWINGS, mirror=mirror)
    a, fired = EM.Reader(V).area(3, lvl, d)
    assert fired == [] and a["models"]["E1"]["status"] == "passed"
    V2, lvl2, d2 = _bare(BEAR, SWINGS, mirror=mirror, s={"entry_models_on": ["E2"]})
    st = _statuses(V2, lvl2, d2, range(3, len(BEAR)))
    assert [f["model"] for t in st for f in st[t][1]] == ["E2"]
    assert st[10][0]["models"]["E1"] == {"status": "off"} and st[10][0]["models"]["E4"] == {"status": "off"}


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_e4b_broken_area_revisited_and_rejected(mirror):
    """A support 100–102 broken down (K4 BROKEN, break_dir −1 = the bear call's direction), revisited from below; a red engulf closes
    below it ⇒ E4 (b), invalidation = the retest extreme. Mirror: a resistance broken up, bull put."""
    rows = [(103.0, 103.2, 101.8, 102.0, 1.0), (102.0, 102.1, 99.0, 99.2, 1.0), (99.2, 99.3, 97.0, 97.2, 1.0),   # 0–2 break, swing low
            (97.2, 98.6, 97.1, 98.5, 1.0), (98.5, 99.6, 98.4, 99.5, 1.0), (99.5, 100.6, 99.4, 100.3, 1.0),         # 3–5 back up, touches
            (100.3, 100.4, 98.9, 99.0, 1.0), (99.0, 99.1, 98.0, 98.1, 1.0)]                                         # 6 rejection
    sw = [("L", 97.0, 2, 3)]
    br = {"id": 1, "lo": 100.0, "hi": 102.0, "role": LV.SUP, "state": "BROKEN", "break_dir": -1, "broken_at": 2,
          "trade_location": True, "tf": "1H", "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}
    if mirror:
        br = {**br, "lo": 2 * MID - 102.0, "hi": 2 * MID - 100.0, "role": LV.RES, "break_dir": 1}
    L1 = NS(id=1, born_bar=0, state_at=lambda u: "BROKEN", events=[], dead_bar=None)
    V, _lvl, d = _bare(rows, sw, mirror=mirror, snapshot=lambda t: [br], extra_L=[L1])
    R = EM.Reader(V)
    got = {t: R.broken(t, d) for t in range(3, len(rows))}
    fired = [(t, f) for t, (_a, fs) in got.items() for f in fs]
    assert [t for t, _ in fired] == [6] and fired[0][1]["variant"] == "b"
    f = fired[0][1]
    assert f["invalidation"] == pytest.approx(2 * MID - 100.6 if mirror else 100.6)   # the retest extreme (5's push)
    assert f["facts"]["object"] == "broken_area" and f["facts"]["form"]
    armed7 = got[7][0][0]
    assert armed7["object"] == "broken_area" and armed7["models"]["E4"]["status"] == "fired_earlier"


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_e4b_broken_line_revisited_and_rejected(mirror, monkeypatch):
    """A rising line of lows (95 + 0.5·bar) broken down (close beyond + swing beyond, known at bar 4); price comes back up to it
    (bar 7 wick reaches the line) and a red engulf closes below it ⇒ E4 (b) on the line. Mirror: a falling line of highs broken up."""
    rows = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 95.6, 96.1, 1.0), (96.1, 96.2, 94.0, 94.2, 1.0),    # 2: closes below 96
            (94.2, 94.3, 93.0, 93.2, 1.0), (93.2, 94.6, 93.1, 94.5, 1.0), (94.5, 96.1, 94.4, 96.0, 1.0),     # 3: swing low beyond
            (96.0, 97.3, 95.9, 97.2, 1.0), (97.2, 98.6, 97.1, 98.4, 1.0), (98.4, 98.5, 96.6, 96.7, 1.0)]     # 7 touches, 8 rejects
    ln = {"family": "rising line of lows", "kind": "L", "slope_dir": "rising", "p1": [0, 95.0], "p2": [1, 95.5], "slope": 0.5,
          "touches": 2, "touch_groups": [[0], [1]], "value_t": 0.0, "broken": True, "break_bar": 2, "break_side": "down",
          "state": "BROKEN", "id": "L+:0-1"}
    if mirror:
        rows = _mirror_rows(rows)
        ln = {**ln, "family": "falling line of highs", "kind": "H", "slope_dir": "falling", "p1": [0, 2 * MID - 95.0],
              "p2": [1, 2 * MID - 95.5], "slope": -0.5, "break_side": "up", "id": "H-:0-1"}
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [ln])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    V, _lvl, d = _bare(rows, [], mirror=False, trend_at=lambda u: "UP" if mirror else "DOWN")
    d = UP if mirror else DOWN
    R = EM.Reader(V)
    fired = [(t, f) for t in range(4, len(rows)) for f in R.broken(t, d)[1]]
    assert [t for t, _ in fired] == [8], [(t, f["facts"]) for t, f in fired]
    f = fired[0][1]
    assert f["kind"] == "line" and f["obj"]["object"] == "broken_line" and f["obj"]["area_id"] == "line:" + ln["id"]
    assert f["invalidation"] == pytest.approx(2 * MID - 98.6 if mirror else 98.6)


# ------------------------------------------------------------------------------------------------ the visit ends only by structure
def _visit_rows():
    return [(98.0, 98.6, 97.8, 98.5), (98.5, 100.6, 98.4, 100.4), (100.4, 100.9, 100.1, 100.3), (100.3, 100.5, 97.6, 97.8),
            (97.8, 100.7, 97.7, 100.5)]


def test_a_commitment_closing_outside_no_longer_ends_the_visit_legacy_k_keeps_the_old_end(monkeypatch):
    """Abhi 21 Oct: a visit ends only by structure. Bar 3 = a dominant red candle after a handover, closing below the supply — under
    the old rule the visit ended there ("a commitment closed outside … no chasing"); now the same visit continues (no swing built away).
    entry_gate = legacy_k keeps the old end (exact old behaviour)."""
    rows = [(*r, 1.0) for r in _visit_rows()]
    V, lvl, d = _bare(rows, [])
    monkeypatch.setattr(V, "handover_episode", lambda A, a, t, d, l: {"present": True})
    vi = V.visit(4, lvl, DOWN)
    assert (vi["start"], vi["prev_end"], vi["ended_by"]) == (1, None, None)
    Vl, lvl_l, _ = _bare(rows, [], s={"entry_gate": "legacy_k"})
    monkeypatch.setattr(Vl, "handover_episode", lambda A, a, t, d, l: {"present": True})
    vl = Vl.visit(4, lvl_l, DOWN)
    assert (vl["start"], vl["prev_end"], vl["ended_by"]) == (4, 3, "commitment")


def test_the_sparse_visit_scan_equals_the_bar_by_bar_scan():
    """The fixed visit reads only touches and away swings — the same answer as the bar-by-bar loop on random walks (both sides)."""
    rng = np.random.default_rng(7)
    for trial in range(30):
        c = 100 + np.cumsum(rng.normal(0, 0.8, 60))
        o = np.r_[c[0], c[:-1]]
        rows = [(o[i], max(o[i], c[i]) + 0.3, min(o[i], c[i]) - 0.3, c[i], 1.0) for i in range(60)]
        sw = []
        for i in range(2, 58):
            if rows[i][2] < min(rows[i - 1][2], rows[i + 1][2], rows[i - 2][2], rows[i + 2][2]):
                sw.append(("L", rows[i][2], i, i + 2))
            if rows[i][1] > max(rows[i - 1][1], rows[i + 1][1], rows[i - 2][1], rows[i + 2][1]):
                sw.append(("H", rows[i][1], i, i + 2))
        band = (float(np.median(c)) - 0.5, float(np.median(c)) + 0.5)
        for dd in (DOWN, UP):
            V, lvl, _ = _bare(rows, sw, band=band)
            for t in range(5, 60, 7):
                fast = V._visit_structure(t, lvl, dd, 0)
                ref = _ref_visit(V, t, lvl, dd)
                assert (fast["start"], fast["prev_end"], fast["approach_from"]) == ref, (trial, dd, t)


def _ref_visit(V, t, lvl, d):
    A = V.levels.A
    lo, hi = lvl["lo"], lvl["hi"]
    every = V._away_swings(t, lo, hi, d)
    piv = set(every)
    start = prev_end = last_piv = approach = None
    for i in range(0, t + 1):
        if start is not None:
            if i in piv and i > start:
                start, prev_end, last_piv = None, i, i
            continue
        if A["low"][i] <= hi and A["high"][i] >= lo:
            start, approach = i, (last_piv + 1 if last_piv is not None else None)
            continue
        if i in piv:
            last_piv = i
    return start, prev_end, approach if start is not None else None


# ------------------------------------------------------------------------------------------------ lines on both sides
def _channel_case():
    pts = {0: 102.0, 5: 100.0, 10: 110.0, 15: 104.0, 20: 114.0, 25: 105.0, 27: 103.0, 30: 106.0, 34: 108.0}
    ks = sorted(pts)
    closes = list(np.interp(np.arange(35), ks, [pts[k] for k in ks]))
    m = m15_from(closes, wick=0.3)
    low, high = m["low"].to_numpy(), m["high"].to_numpy()
    p2 = [P("L", low[5], 5, 7), P("H", high[10], 10, 12), P("L", low[15], 15, 17), P("H", high[20], 20, 22),
          P("L", low[27], 27, 29)]
    lv = LV.Levels(res_of(m, p2, []))
    return NS(levels=lv, s=S3.load()), m


def test_channel_lines_build_both_sides_with_touches_and_the_k65_break():
    V, m = _channel_case()
    t = 34
    lines = TL.channel_lines(V, t)
    by = {(x["family"], x["state"]): x for x in lines}
    hi_line = by[("rising line of highs", "ACTIVE")]                      # the up-channel's upper line (was never built before)
    assert (hi_line["p1"][0], hi_line["p2"][0]) == (10, 20) and hi_line["touches"] >= 2
    cur = by[("rising line of lows", "ACTIVE")]
    old = by[("rising line of lows", "BROKEN")]                            # broken by a close below + the swing low 27 below it
    assert (cur["p1"][0], cur["p2"][0]) == (5, 27) and (old["p1"][0], old["p2"][0]) == (5, 15)
    assert old["broken"] and old["break_side"] == "down" and 15 < old["break_bar"] <= 27
    assert TL.break_known_at(V, old) == 29                                 # known when the swing beyond is confirmed (no look-ahead)
    before = TL.channel_lines(NS(levels=V.levels, s=V.s), 28)               # at 28 the swing low 27 is not known: the line stands
    assert not [x for x in before if x["family"] == "rising line of lows" and x["state"] == "BROKEN"]
    up = TL.swing_line(V, t, UP)                                           # the trade-side line the decision uses: unchanged
    assert up is not None and up["p2"][0] == 27


def test_fast_break_read_equals_broken_by():
    rng = np.random.default_rng(3)
    for trial in range(40):
        c = 100 + np.cumsum(rng.normal(0, 1.0, 50))
        A = {"close": c}
        piv = [NS(kind="L" if rng.random() < 0.5 else "H", price=float(c[b] + rng.normal(0, 1.0)), bar=int(b), confirm_bar=int(b) + 2)
               for b in sorted(rng.choice(50, 10, replace=False))]
        y1, sl = float(c[0]), float(rng.normal(0, 0.3))

        def line(b):
            return y1 + sl * b
        for kind, side in (("L", -1), ("H", 1)):
            for st, en in ((1, 49), (10, 30), (5, 5)):
                assert TL._broken_at(c, piv, kind, line, side, st, en) == TL.broken_by(A, piv, kind, line, side, st, en), (trial, kind, st)


# ------------------------------------------------------------------------------------------------ settings + the decide row
def test_entry_gate_settings_are_registered_and_validated():
    assert S3.DEFAULTS["entry_gate"] == "models" and S3.DEFAULTS["zone_visit_rule"] == "structure"
    for k in ("entry_gate", "entry_models_on"):
        assert k in S3.REGISTER and S3.REGISTER[k][2] == "Abhi नियम" and S3.REGISTER[k][3].startswith("Abhi 21 Oct")
    assert tuple(S3.DEFAULTS["entry_models_on"]) == EM.MODELS
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    with pytest.raises(ValueError, match="entry_gate"):
        E3.V22(m15, s={"entry_gate": "k"}, ltf=ltf, futures=fut)
    with pytest.raises(ValueError, match="entry_models_on"):
        E3.V22(m15, s={"entry_models_on": ["E5"]}, ltf=ltf, futures=fut)


@pytest.fixture(scope="module", params=[False, True], ids=["bear_call", "bull_put_mirror"])
def oct12(request):
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=request.param)
    s = {"level_death_side": "role", **AREA}                               # the default trigger (traded_inside)
    V = E3.V22(m15, s=s, ltf=ltf, futures=fut)
    Vk = E3.V22(m15, s={**s, "entry_gate": "legacy_k"}, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last]
    return request.param, V, Vk, bars


def test_decide_row_carries_entries_armed_and_the_legacy_k_diagnostic(oct12):
    mirror, V, Vk, bars = oct12
    rows = [V.decide(t) for t in bars]
    st = [r for r in rows if r["decision"] == "setup"]
    assert st and all(r["entries"] for r in st) and all(not r["entries"] for r in rows if r["decision"] != "setup")
    e = st[0]["entries"][0]
    assert set(e) >= {"model", "name", "direction", "side", "area", "visit_id", "key", "trigger_bar", "trigger_ts", "entry_ref",
                      "invalidation", "invalidation_rule", "evidence", "evidence_list", "label", "confirming", "facts"}
    assert e["side"] == ("bull_put" if mirror else "bear_call") and e["label"] in ("A", "B", None)
    assert st[0]["conviction"] == e["label"] and st[0]["mark"] == {"A": "✅", "B": "🟡", None: "⚪"}[e["label"]]
    for x in (x for r in rows for x in r["entries"]):                       # DECISIONS 58: no A / B label — the evidence count
        el = x["evidence_list"]
        assert x["label"] is None and el["required"] == "present", (x["model"], x["label"])
        assert el["evidence_count"] == sum(1 for v in x["confirming"].values() if v is True)
    assert e["evidence"][0][1] in ("✓", "✗") and {k for k in e["area"]} >= {"id", "tf", "lo", "hi", "state"}
    keys = [x["key"] for r in rows for x in r["entries"]]
    assert len(keys) == len(set(keys))                                       # one fire per (area, visit, model)
    for r in rows:
        assert set(r) >= {"entries", "armed", "legacy_k_gate", "channel_lines", "entry_gate"} and r["entry_gate"] == "models"
        assert set(r["legacy_k_gate"]) >= {"pass", "reason", "direction", "values"}
        json.dumps(r, default=str, ensure_ascii=False)
    old = Vk.decide(bars[0])
    assert "entries" not in old and "legacy_k_gate" not in old              # legacy_k: the exact old row
    w = [r for r in rows if r["decision"] == "wait"]
    assert w and all(r["why"] for r in w)                                    # a wait says what the armed models wait for


def test_21_oct_like_no_bos_k_blocks_the_old_gate_the_models_still_read_the_visit(oct12, monkeypatch):
    """21 Oct (REPORT_EN §2e): ① DOWN, price at a valid resistance area, but no fresh DOWN BOS ⇒ K = None ⇒ the old ③ waits all day.
    Same bars with K forced to None: legacy_k ⇒ wait ③ "BOS नाही"; the models read the visit (E1 on the visit's first bar) and log the
    old ③ as legacy_k_gate (fail, never deciding)."""
    mirror, V, Vk, bars = oct12
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=mirror)
    s = {"level_death_side": "role", **AREA}                               # the default trigger (traded_inside)
    V2 = E3.V22(m15, s=s, ltf=ltf, futures=fut)
    Vk2 = E3.V22(m15, s={**s, "entry_gate": "legacy_k"}, ltf=ltf, futures=fut)
    for x in (V2, Vk2):
        monkeypatch.setattr(x.pb, "at", lambda t, d: None)
    old = [Vk2.decide(t) for t in bars]
    assert all(r["decision"] != "setup" for r in old)
    assert any("BOS" in str((r["checklist"].get("③") or [None, ""])[1]) for r in old)
    new = [V2.decide(t) for t in bars]
    assert all(r["legacy_k_gate"]["pass"] is False and "BOS" in r["legacy_k_gate"]["reason"] for r in new)
    fired = [e["model"] for r in new for e in r["entries"]]
    assert "E1" in fired and fired.count("E1") == len({e["visit_id"] for r in new for e in r["entries"] if e["model"] == "E1"})


def test_channels_parallel_through_the_opposite_extreme_and_the_broken_counter_channel():
    """Abhi 21 Oct: each line has its parallel through the opposite extreme of the same move; the up-channel's lower line broken (close
    below + swing below) ⇒ "lower line broken" / its retest, broken_side "down" — the bear call's handover evidence (a rising channel broken
    down); lines are drawn on each structure (the trend degree D2 = 1H, and D1 = 15M; none here)."""
    V, m = _channel_case()
    t = 34
    assert TL.line_degrees(V) == (2, 1) and TL.channel_lines(V, t, 1) == []
    ch = {c["base"]: c for c in TL.channels(V, t)}
    up = next(c for c in ch.values() if c["base_line"]["family"] == "rising line of highs")
    low15 = float(m["low"].iloc[10:21].min())
    assert up["parallel"]["kind"] == "L" and up["parallel"]["p1"][1] == pytest.approx(round(low15, 2))   # the move's opposite extreme
    assert up["parallel"]["slope"] == up["base_line"]["slope"] and up["upper_t"] > up["lower_t"]
    broken = [c for c in ch.values() if c["slope_dir"] == "rising" and c["broken_side"] == "down"]
    assert broken and all(("lower line broken" in c["state"]) or ("retest of the broken lower line" in c["state"]) for c in broken)
    assert all(c["state"] in ("inside", "outside (no break)") or c["broken_lines"] for c in ch.values())


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_pattern_hook_feeds_e4b_as_a_broken_line(mirror, monkeypatch):
    rows = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 95.6, 96.1, 1.0), (96.1, 96.2, 94.0, 94.2, 1.0),
            (94.2, 94.3, 93.0, 93.2, 1.0), (93.2, 94.6, 93.1, 94.5, 1.0), (94.5, 96.1, 94.4, 96.0, 1.0),
            (96.0, 97.3, 95.9, 97.2, 1.0), (97.2, 98.6, 97.1, 98.4, 1.0), (98.4, 98.5, 96.6, 96.7, 1.0)]
    neck = {"kind": "L", "p1": [0, 95.0], "slope": 0.5, "broken": True, "break_bar": 2, "break_side": "down", "id": "pat:neckline",
            "family": "pattern neckline"}
    if mirror:
        rows = _mirror_rows(rows)
        neck = {**neck, "kind": "H", "p1": [0, 2 * MID - 95.0], "slope": -0.5, "break_side": "up"}
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    monkeypatch.setattr(EM, "PATTERN_HOOK", lambda V, t, d: [neck])
    V, _lvl, _d = _bare(rows, [], trend_at=lambda u: "UP" if mirror else "DOWN")
    d = UP if mirror else DOWN
    fired = [(t, f) for t in range(4, len(rows)) for f in EM.Reader(V).broken(t, d)[1]]
    assert [t for t, _ in fired] == [8] and fired[0][1]["obj"]["area_id"] == "line:pat:neckline"


@pytest.mark.parametrize("mirror", [False, True], ids=["upper_edge_bear_call", "lower_edge_bull_put"])
def test_range_state_edges_are_the_areas_and_the_models_apply_there(mirror):
    """Abhi's method L (range): the existing Daily RANGE (Q27) — `Levels.active(t, "RANGE", band)` offers the nearest support in the
    band's lower half and resistance in its upper half; the models read those edge areas by their role (bear call at the upper edge,
    bull put at the lower)."""
    V, lvl, d = _bare(BEAR, SWINGS, mirror=mirror, trend_at=lambda u: "RANGE")
    assert M._dir("RANGE", lvl["role"]) == d
    st = _statuses(V, lvl, d, range(3, len(BEAR)))
    assert [f["model"] for t in st for f in st[t][1]] == ["E1", "E2", "E4"]


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_a_visit_with_the_fut_data_problem_never_gives_an_entry(mirror):
    """Abhi RF-2 (b) / Z-1c (existing rule, every model): FUT volume given but missing on more than vol_gap_max_frac of the visit ⇒
    data problem, no entry — the model is consumed and listed (29 Sep has no FUT bar: never a setup)."""
    V, lvl, d = _bare(BEAR, SWINGS, mirror=mirror)
    V.levels.A["volume_raw"][3:] = np.nan
    a, fired = EM.Reader(V).area(3, lvl, d)
    assert fired == [] and a["models"]["E1"]["status"] == "blocked_data_problem" and "data problem" in a["models"]["E1"]["note"]


def test_models_invariants_direction_no_breakout_and_no_look_ahead():
    """End to end (tests.test_decision3_method._abc_m15, Daily DOWN, default entry_gate): every entry is on the trend side, never a
    breakout bar at an area (trigger close / open not beyond the far edge), keys unique, and the same read on data cut at the bar."""
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    s = {"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_volume_required": False}
    V = E3.V22(m15, s=s)
    rows = V.run()
    A = V.levels.A
    ents = [(r, e) for r in rows for e in r["entries"]]
    assert ents                                                            # non-vacuous
    for r, e in ents:
        assert r["decision"] == "setup" and r["trend_used"] in ("UP", "DOWN", "RANGE")
        assert e["direction"] == M._dir(r["trend_used"], e["area"]["role"] if e["object"] == "area" else None) or e["object"] != "area"
        t = e["trigger_bar"]
        if e["object"] == "area":
            far = e["area"]["hi"] if e["direction"] < 0 else e["area"]["lo"]
            assert (A["close"][t] - far) * e["direction"] >= 0 and (A["open"][t] - far) * e["direction"] >= 0
    assert all(r["decision"] == "no_trade" for r in rows if r["trend_used"] in ("NEUTRAL", "UNKNOWN"))
    keys = [e["key"] for _, e in ents]
    assert len(keys) == len(set(keys))
    k = ents[0][1]["trigger_bar"] + 1
    Vt = E3.V22(m15.iloc[:k].reset_index(drop=True), s=s)
    for t in range(max(0, k - 60), k):
        a, b = rows[t], Vt.decide(t)
        assert (a["decision"], [x["key"] for x in a["entries"]], [(x["area_id"], x.get("models")) for x in a["armed"]]) == \
            (b["decision"], [x["key"] for x in b["entries"]], [(x["area_id"], x.get("models")) for x in b["armed"]]), t


# Abhi 21 Oct (13 Oct principle): a supply 100–102; the buyers keep coming in small candles and price does not move away (absorption)
# with no handover — the dominant red at bar 8 is a commitment and the 5M CHoCH is done, yet E2 / E3 must not fire there.
ABSORB_ROWS = [(97.0, 97.6, 96.8, 97.5, 1.0), (97.5, 98.6, 97.4, 98.5, 1.0), (98.5, 99.4, 98.4, 99.3, 1.0),
               (99.3, 100.6, 99.2, 100.4, 1.0),        # 3 enters (E1)
               (100.4, 101.4, 100.3, 101.3, 1.0),      # 4 green
               (101.3, 101.4, 100.4, 100.45, 1.0),     # 5 red, closes no lower than the earlier part
               (100.45, 100.8, 100.4, 100.75, 1.0),    # 6 small green
               (100.75, 100.95, 100.7, 100.9, 1.0),    # 7 small green — absorption, no handover
               (100.9, 101.0, 99.0, 99.1, 5.0),        # 8 dominant red on volume (c0) + 5M CHoCH (c1)
               (99.1, 99.2, 98.0, 98.1, 1.0)]          # 9
ABSORB_SW = [("L", 96.8, 0, 1)]


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_e2_e3_never_fire_while_absorption_shows_no_handover_e1_unaffected(mirror, monkeypatch):
    rows = _mirror_rows(ABSORB_ROWS) if mirror else ABSORB_ROWS
    V, lvl, d = _bare(ABSORB_ROWS, ABSORB_SW, mirror=mirror, ltf=_ltf_from(rows), s=LEGACY)   # bar 8 closes below the area
    st = _statuses(V, lvl, d, range(3, len(ABSORB_ROWS)))
    fired = {t: [f["model"] for f in st[t][1]] for t in st}
    R = EM.Reader(V)
    assert fired[3] == ["E1"]                                              # E1 never reads the zone study (no "no entry" forced)
    for t in st:                                                           # the principle, bar by bar
        if R.absorbing(t, lvl, d, 3):
            assert not {"E2", "E3"} & set(fired[t]), (t, fired[t])
    m8 = st[8][0]["models"]
    assert R.absorbing(8, lvl, d, 3) and "absorption" in R.absorbing(8, lvl, d, 3)
    assert m8["E2"]["status"] == "waiting" and "absorption without a handover" in m8["E2"]["waiting"]
    assert m8["E3"]["status"] == "waiting" and "absorption without a handover" in m8["E3"]["waiting"]
    # control: without the absorption read the same bar is a commitment and a CHoCH ⇒ E2 and E3 would fire there
    V2, lvl2, d2 = _bare(ABSORB_ROWS, ABSORB_SW, mirror=mirror, ltf=_ltf_from(rows), s=LEGACY)
    monkeypatch.setattr(EM.Reader, "absorbing", lambda self, *a: None)
    fired2 = {t: [f["model"] for f in EM.Reader(V2).area(t, lvl2, d2)[1]] for t in range(3, len(ABSORB_ROWS))}
    assert {"E2", "E3"} <= set(fired2[8])


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_absorption_with_a_handover_present_does_not_stop_e2(mirror, monkeypatch):
    """The principle is 'absorption WITHOUT a handover': a handover present (sticky, handover_episode) ⇒ the read stays silent."""
    rows = _mirror_rows(ABSORB_ROWS) if mirror else ABSORB_ROWS
    V, lvl, d = _bare(ABSORB_ROWS, ABSORB_SW, mirror=mirror, ltf=_ltf_from(rows))
    orig = V.handover_episode
    monkeypatch.setattr(V, "handover_episode", lambda A, a, t, dd, l: {**orig(A, a, t, dd, l), "present": True}, raising=False)
    assert EM.Reader(V).absorbing(8, lvl, d, 3) is None


# Lead's provisional rule (entry_cluster_rule = cluster): overlapping same-role areas visited together = ONE location.
def _two_areas(mirror):
    L1 = NS(id=1, born_bar=0, state_at=lambda u: "ACTIVE", events=[], dead_bar=None)
    V, lvl0, d = _bare(BEAR, SWINGS, mirror=mirror, extra_L=(L1,))
    b1 = (2 * MID - 103.0, 2 * MID - 101.0) if mirror else (101.0, 103.0)       # overlaps 100–102 (mirror 100–102 as well)
    lvl1 = {**lvl0, "id": 1, "lo": b1[0], "hi": b1[1], "tf": "15M"}
    return V, lvl0, lvl1, d


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_overlapping_areas_in_one_visit_give_one_signal_per_model(mirror):
    V, lvl0, lvl1, d = _two_areas(mirror)
    per_area, per_cluster = {}, {}
    for t in range(3, len(BEAR)):
        R = EM.Reader(V)
        armed, ents = [], []
        for lv in (lvl0, lvl1):
            a, f = R.area(t, lv, d)
            if a is not None:
                armed.append(a)
                ents += [(x, lv, d, a) for x in f]
        per_area[t] = [(e[0]["model"], e[3]["area_id"]) for e in ents]
        kept = EM.clusters(armed, ents, [(lvl0, d), (lvl1, d)])
        per_cluster[t] = kept
        for a in armed:                                                   # a consumed firing is listed on the member, never lost
            for m, st in a["models"].items():
                if st["status"] == "cluster_consumed":
                    assert "one place, one signal per model" in st["note"]
    assert per_area[3] == [("E1", 0)] and per_area[4] == [("E1", 1)]           # per area: E1 twice (old reading)
    assert per_area[6] == [("E2", 0), ("E2", 1)]   # the commitment traded inside both areas (closes inside area 0, below area 1 on
                                                # the trade side — allowed, Abhi 22 Oct traded_inside) ⇒ each area's own trigger holds;
                                                # the cluster below keeps one (the trigger check reads the ACTUAL area — Z-1u)
    got = {t: [(e[0]["model"], e[3]["area_id"]) for e in k] for t, k in per_cluster.items()}
    assert got[3] == [("E1", 0)] and got[4] == [] and got[6] == [("E2", 0)]    # one signal per model per cluster
    e1 = per_cluster[3][0][0]
    far = 2 * MID - 102.0 if mirror else 102.0                                # Abhi 21 Oct (Z-1u): the cluster only COUNTS — E1's
    assert e1["invalidation"] == pytest.approx(far) and "the area's far edge" in e1["invalidation_rule"]   # invalidation = its OWN area
    assert "cluster" not in e1["invalidation_rule"]
    cl = per_cluster[6][0][0]["cluster"]
    assert cl["n"] == 2 and {m["area_id"] for m in cl["members"]} == {0, 1} and cl["visit_id"].startswith("0@")   # the card lists both
    assert "lo" not in cl and "hi" not in cl and "far_edge" not in cl and "visit_extreme" not in cl   # no union band anywhere
    own = next(f for f in EM.Reader(V).area(6, lvl0, d)[1] if f["model"] == "E2")
    assert per_cluster[6][0][0]["invalidation"] == pytest.approx(own["invalidation"])   # E2: area 0's own visit extreme


def test_separate_areas_and_the_other_side_are_never_merged():
    a = {"object": "area", "area_id": 0, "role": "resistance", "direction": -1, "lo": 100.0, "hi": 102.0, "visit_start_bar": 3,
         "visit_id": "0@x", "visit_start": "x", "models": {"E1": {"status": "fired"}}}
    b = {**a, "area_id": 1, "lo": 103.0, "hi": 104.0, "visit_id": "1@y", "models": {"E1": {"status": "fired"}}}   # no overlap
    c = {**a, "area_id": 2, "role": "support", "direction": 1, "models": {"E1": {"status": "fired"}}}            # other side
    f = {"model": "E1", "invalidation": 1.0, "invalidation_rule": "r"}
    kept = EM.clusters([a, b, c], [(dict(f), None, -1, a), (dict(f), None, -1, b), (dict(f), None, 1, c)])
    assert [k[3]["area_id"] for k in kept] == [0, 1, 2] and all(k[0]["cluster"]["n"] == 1 for k in kept)
    assert all(k[0]["invalidation"] == 1.0 for k in kept)                       # a cluster of one: unchanged


def test_entry_cluster_rule_registered_and_validated():
    assert S3.DEFAULTS["entry_cluster_rule"] == "cluster" and S3.REGISTER["entry_cluster_rule"][1] == "cluster / area"
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    with pytest.raises(ValueError, match="entry_cluster_rule"):
        E3.V22(m15, s={"entry_cluster_rule": "x"}, ltf=ltf, futures=fut)
