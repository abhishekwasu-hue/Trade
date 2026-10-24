"""Abhi (C lifecycle) — an area flips only once: a FLIPPED area broken again (a close beyond + a swing formed beyond) is DEAD at once;
a dead area is never armed and no E4 (b) retest may use it (`flip_dead_rule = broken_again`; "far_swing" = the earlier reading, what-if).
And one signal per model per place for E4 (b): overlapping BROKEN areas revisited together give one E4 (b) (Z-1u count only).

Synthetic fixtures (CI-safe), both mirrors, on the REAL K4 reader (decision3/levels.py, default structural break rule):
a resistance 117–118 (a D2 high at 118) is broken up (close beyond + a swing beyond, bar 22) and flips at the far-side swing (bar 27,
now a support); price then falls back through it (closes below) and a swing low forms below it (confirmed at bar 33) = broken again;
price comes back up to the band from below (bar 35) and a rejection closes away below it (bar 36). Mirror: a support broken down."""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import entry_models as EM
from decision3 import flip as FL
from decision3 import levels as LV
from decision3 import settings as S3
from tests.test_decision3_entry_models import MID, _bare
from tests.test_decision3_zone_answers import P, _mirror, m15_from, res_of

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])

CLOSES = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + [114, 116, 118.6, 119.4, 120.2, 119.0, 118.4] + \
    [119.5, 121.0, 122.6, 121.5, 120.0, 118.5, 116.8, 115.2, 114.0, 113.8, 114.6, 115.5, 116.2, 116.9, 115.0, 113.6, 112.5]
REJECT = 36                                                                # the rejection bar after the retest from the other side


def _case(mirror, rule=None):
    f, sw = _mirror(mirror)
    m = m15_from([f(c) for c in CLOSES], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("H"), f(122.6), 25, 27)]
    p1 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16), P(sw("H"), f(120.5), 20, 22), P(sw("H"), f(122.6), 25, 27),
          P(sw("L"), f(113.8), 31, 33)]
    lv = LV.Levels(res_of(m, p2, p1), s={"flip_dead_rule": rule} if rule else None)
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    return m, lv, Z


def _reader(m, lv, mirror):
    rows = list(zip(m["open"], m["high"], m["low"], m["close"], [1.0] * len(m)))
    V, _l, _d = _bare(rows, [], s={"entry_area_refine": "area"})
    V.levels = lv
    V._ts = pd.to_datetime(m["timestamp"]).to_numpy()
    V.bar_end = pd.to_datetime(m["bar_end"]).reset_index(drop=True)
    V.step1 = lambda u: (True, "", None, {"trend": "UP" if mirror else "DOWN"})
    return V


@MIRRORS
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_flipped_area_broken_again_with_a_swing_beyond_is_dead_no_second_flip(mirror):
    m, lv, Z = _case(mirror)
    assert S3.DEFAULTS["flip_dead_rule"] == "broken_again"
    kinds = [(b, k) for b, k, _ in Z.events if k in ("broken", "flip", "reclaim", "dead")]
    assert kinds == [(22, "broken"), (27, "flip"), (33, "broken"), (33, "dead")]
    assert Z.dead_bar == 33 and Z.state_at(32) == FL.FLIPPED and Z.state_at(33) == FL.DEAD   # never BROKEN after its flip
    assert "flips only once" in [d for b, k, d in Z.events if k == "dead"][0]
    assert Z.count("flip", len(m) - 1) == 1
    assert all(x["id"] != Z.id for t in range(33, len(m)) for x in lv.snapshot(t))     # dead ⇒ never a location / object again
    assert all(x["id"] != Z.id for t in range(33, len(m)) for tr in ("UP", "DOWN") for x in lv.active(t, tr))   # never armed


@MIRRORS
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_flipped_area_swept_back_without_a_swing_beyond_stays_flipped(mirror):
    """Handover T-2: flip → a sweep back (a close beyond the flipped area, no swing formed beyond, then back) ⇒ still FLIPPED, alive."""
    f, sw = _mirror(mirror)
    closes = CLOSES[:28] + [120.0, 118.6, 116.6, 118.8, 120.4, 121.8, 123.0, 123.8, 123.2, 124.4, 125.0]   # bar 30 closes beyond
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("H"), f(122.6), 25, 27)]
    p1 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16), P(sw("H"), f(120.5), 20, 22), P(sw("H"), f(122.6), 25, 27)]
    lv = LV.Levels(res_of(m, p2, p1))
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    kinds = [(b, k) for b, k, _ in Z.events if k in ("broken", "flip", "sweep", "dead")]
    assert kinds == [(22, "broken"), (27, "flip"), (31, "sweep")]
    assert Z.dead_bar is None and all(Z.state_at(t) == FL.FLIPPED for t in range(27, len(m)))
    assert any(x["id"] == Z.id for x in lv.snapshot(len(m) - 1))


@MIRRORS
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_dead_area_gives_no_e4b_retest_while_the_far_swing_what_if_still_does(mirror, monkeypatch):
    """The replayed worst loss: a flipped area broken back, then retested from the other side with a rejection. Default ⇒ dead, no
    E4 (b). The earlier reading (`flip_dead_rule = far_swing`) keeps it BROKEN and fires the E4 (b) at the rejection bar."""
    import decision3.method as M
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1) if t == REJECT else None)
    d = 1 if mirror else -1                                                # broken back down ⇒ bear call; mirror: bull put
    m, lv, Z = _case(mirror, "far_swing")
    snap = next(x for x in lv.snapshot(len(m) - 1) if x["id"] == Z.id)
    assert snap["state"] == FL.BROKEN and snap["break_dir"] == d and Z.dead_bar is None
    V = _reader(m, lv, mirror)
    fired = [(t, f) for t in range(33, len(m)) for f in EM.Reader(V).broken(t, d)[1] if f["obj"]["area_id"] == Z.id]
    assert [t for t, _ in fired] == [REJECT] and fired[0][1]["variant"] == "b"      # the what-if reproduces the replayed E4 (b)
    m, lv, Z = _case(mirror)
    V = _reader(m, lv, mirror)
    for t in range(33, len(m)):
        armed, fired = EM.Reader(V).broken(t, d)
        assert all(a["area_id"] != Z.id for a in armed) and all(f["obj"]["area_id"] != Z.id for f in fired)


@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_flip_dead_rule_is_registered_and_checked():
    assert S3.REGISTER["flip_dead_rule"][0] == S3.DEFAULTS["flip_dead_rule"] == "broken_again"
    m = m15_from(CLOSES, wick=0.3)
    with pytest.raises(ValueError, match="flip_dead_rule"):
        LV.Levels(res_of(m, [P("H", 118, 8, 10), P("H", 122.6, 25, 27)],
                         [P("H", 118, 8, 10), P("L", 112, 14, 16), P("H", 120.5, 20, 22), P("H", 122.6, 25, 27)]),
                  s={"flip_dead_rule": "twice"})


# ------------------------------------------------------------------------------------------------ one E4 (b) per place (Z-1u count)
# Two overlapping BROKEN supplies (100–104 and 102.5–104.4, both broken UP ⇒ the bull put's retest), revisited together at bar 6 and
# rejected at bar 7 ⇒ ONE E4 (b) (the first visit's area keeps its own band and invalidation); mirror: demands broken down, bear call.
ROWS = [(103.0, 103.2, 101.8, 102.0, 1.0), (102.0, 105.5, 101.9, 105.3, 1.0), (105.3, 107.2, 105.2, 107.0, 1.0),
        (107.0, 107.1, 106.0, 106.2, 1.0), (106.2, 106.3, 105.4, 105.5, 1.0), (105.5, 105.6, 104.4, 104.6, 1.0),
        (104.6, 104.7, 103.6, 103.8, 1.0), (103.8, 105.1, 103.7, 105.0, 1.0), (105.0, 106.0, 104.9, 105.9, 1.0)]


def _two_broken(mirror, monkeypatch, bands=((100.0, 104.0), (102.5, 104.4))):
    import decision3.method as M
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1) if t == 7 else None)
    snap = []
    for i, (lo, hi) in enumerate(bands, start=1):
        x = {"id": i, "lo": lo, "hi": hi, "role": LV.RES, "state": FL.BROKEN, "break_dir": 1, "broken_at": 1, "trade_location": True,
             "tf": "1H", "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}
        if mirror:
            x = {**x, "lo": 2 * MID - hi, "hi": 2 * MID - lo, "role": LV.SUP, "break_dir": -1}
        snap.append(x)
    Ls = [NS(id=i, born_bar=0, state_at=lambda u: FL.BROKEN, events=[], dead_bar=None) for i in (1, 2)]
    V, _l, _d = _bare(ROWS, [("H", 107.2, 2, 3)], mirror=mirror, snapshot=lambda t: snap, extra_L=Ls,
                      s={"entry_area_refine": "setup_tf"}, trend_at=lambda u: "DOWN" if mirror else "UP")
    return V, (-1 if mirror else 1)


@MIRRORS
def test_overlapping_broken_areas_give_one_e4b_per_place(mirror, monkeypatch):
    V, d = _two_broken(mirror, monkeypatch)
    armed, fired = EM.Reader(V).broken(7, d)
    assert sorted(f["obj"]["area_id"] for f in fired) == [1, 2]          # the reader alone: both members fire (the replayed duplicate)
    kept = EM.clusters(armed, [(f, None, d, f["obj"]) for f in fired], obj=("broken_area", "broken_line"), prefix="CB")
    assert len(kept) == 1                                                  # one place ⇒ one E4 (b)
    f, _lvl, _d, a = kept[0]
    assert f["cluster"]["id"].startswith("CB") and f["cluster"]["n"] == 2 and f["cluster"]["visit_id"] == a["visit_id"]
    assert f["invalidation"] == pytest.approx(103.6 if not mirror else 2 * MID - 103.6)   # its own retest extreme, never a union
    other = next(x for x in armed if x["area_id"] != a["area_id"])
    assert other["models"]["E4"]["status"] == "cluster_consumed"


@MIRRORS
def test_separate_broken_areas_still_fire_their_own_e4b(mirror, monkeypatch):
    V, d = _two_broken(mirror, monkeypatch, bands=((100.0, 104.0), (90.0, 92.0)))   # not overlapping ⇒ two places
    armed, fired = EM.Reader(V).broken(7, d)
    kept = EM.clusters(armed, [(f, None, d, f["obj"]) for f in fired], obj=("broken_area", "broken_line"), prefix="CB")
    assert [k[0]["obj"]["area_id"] for k in kept] == [f["obj"]["area_id"] for f in fired]


def test_read_applies_the_e4b_place_count(monkeypatch):
    """EM.read routes the E4 (b) firings through clusters(obj="broken_area") under `entry_cluster_rule = cluster` (and not under
    `area`)."""
    calls = []
    real = EM.clusters
    monkeypatch.setattr(EM, "clusters", lambda *a, **k: calls.append(k.get("obj", "area")) or real(*a, **k))
    fake = NS(A={}, area=lambda t, lvl, d: (None, []), broken=lambda t, d: ([], []))
    monkeypatch.setattr(EM, "Reader", lambda V: fake)
    V = NS(s={"entry_cluster_rule": "cluster"})
    EM.read(V, 5, "DOWN", [])
    assert calls == ["area", ("broken_area", "broken_line")]
    calls.clear()
    V = NS(s={"entry_cluster_rule": "area"})
    EM.read(V, 5, "DOWN", [])
    assert calls == []


def test_a_broken_line_at_the_broken_area_is_the_same_place():
    """A BROKEN line whose value at the bar lies on a BROKEN area (same role, same break direction), both firing E4 (b) at that bar ⇒
    one signal (the earlier revisit's object); a line away from the area stays its own place."""
    def armed(oid, kind, lo, hi, start):
        return {"object": "broken_" + kind, "area_id": oid, "tf": "1H" if kind == "area" else "line", "role": LV.SUP, "lo": lo,
                "hi": hi, "state": "BROKEN", "direction": -1, "visit_id": f"{oid}@{start}", "visit_start": str(start),
                "visit_start_bar": start, "models": {"E4": {"status": "fired", "at": "x"}}}
    for line_at, n_kept in ((101.5, 1), (95.0, 2)):
        a, ln = armed(7, "area", 100.0, 102.0, 3), armed("line:D2:L+:1-2", "line", line_at, line_at, 4)
        fired = [({"model": "E4", "variant": "b", "obj": x}, None, -1, x) for x in (a, ln)]
        kept = EM.clusters([a, ln], fired, obj=("broken_area", "broken_line"), prefix="CB")
        assert len(kept) == n_kept
        if n_kept == 1:
            assert kept[0][3] is a and ln["models"]["E4"]["status"] == "cluster_consumed"
