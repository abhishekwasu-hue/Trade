"""Abhi's gallery review A5 / A7 (DECISIONS 62 / 63) — object identity and the refined 15M base.

A5: one place = one id for its life. `Level.id` is the list index of ONE build (it shifts when the 90-day data window moves, so the
same band showed as 281 / 280 / 278 and one number named different bands on different days); `Level.uid` is the place itself — the
band's timeframe, the side of its base and its base candle — and the visit id / the once-per-model-per-visit key / the cluster anchor
use it. Duplicates never bypass `max_hits_per_zone`: that count is by the band (overlap + role), never by an id.

A7: the refined base = the NEWEST 15M turn of the area's side inside the band, as its wick to body (every 15M turn the swing engine
confirms; a turn whose wick to body trades into the band — also one that pokes just beyond it), kept inside the band; bars ≤ u only.
Both mirrors; comparison only.
"""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

import engine_signal as ES
from decision3 import engine as E3
from decision3 import entry_models as EM
from decision3 import levels as LV


# ------------------------------------------------------------------------------------------------ A5: the place id
def _build(mirror, drop_days=0, **extra):
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=mirror)
    if drop_days:                                                          # the data window moved: the first sessions are gone
        day0 = pd.to_datetime(m15["timestamp"]).dt.normalize().drop_duplicates().iloc[drop_days]
        keep = pd.to_datetime(m15["timestamp"]) >= day0
        m15 = m15[keep].reset_index(drop=True)
        ltf = ltf[pd.to_datetime(ltf["timestamp"]) >= day0].reset_index(drop=True)
        fut = fut[pd.to_datetime(fut["timestamp"]) >= day0].reset_index(drop=True)
    return E3.V22(m15, s={"level_death_side": "role", **extra}, ltf=ltf, futures=fut)


@pytest.mark.parametrize("mirror", [False, True])
def test_the_same_place_keeps_its_uid_when_the_data_window_moves(mirror):
    full, moved = _build(mirror), _build(mirror, drop_days=2)
    t_full, t_moved = len(full.levels.ts) - 1, len(moved.levels.ts) - 1
    assert full.levels.ts.iloc[t_full] == moved.levels.ts.iloc[t_moved]   # the same decision bar
    band = lambda L, t: (L.tf, round(L.band_at(t)[0], 2), round(L.band_at(t)[1], 2), L.born_bar)   # noqa: E731
    by_band_full = {band(L, t_full)[:3] + (str(full.levels.ts.iloc[L.born_bar]),): L for L in full.levels.L}
    shared = [(by_band_full[k], L) for L in moved.levels.L
              for k in [band(L, t_moved)[:3] + (str(moved.levels.ts.iloc[L.born_bar]),)] if k in by_band_full]
    assert shared, "no level known in both windows"
    assert all(a.uid == b.uid for a, b in shared)                          # one place = one id, whatever the window
    assert any(a.id != b.id for a, b in shared)                            # ... while the list index moved (the bug)
    for V in (full, moved):                                                # one uid names one level in a build
        uids = [L.uid for L in V.levels.L]
        assert len(uids) == len(set(uids)) and all(uids)
        snap = V.levels.snapshot(len(V.levels.ts) - 1)
        assert all(x["uid"] == V.levels.L[x["id"]].uid for x in snap)
        assert all(V.levels.by_uid(L.uid) is L for L in V.levels.L)


@pytest.mark.parametrize("mirror", [False, True])
def test_a_reused_index_never_names_two_places(mirror):
    full, moved = _build(mirror), _build(mirror, drop_days=2)
    t1, t2 = len(full.levels.ts) - 1, len(moved.levels.ts) - 1
    for i in range(min(len(full.levels.L), len(moved.levels.L))):
        a, b = full.levels.L[i], moved.levels.L[i]
        if (round(a.band_at(t1)[0], 2), round(a.band_at(t1)[1], 2)) != (round(b.band_at(t2)[0], 2), round(b.band_at(t2)[1], 2)):
            assert a.uid != b.uid                                          # the same number, different bands ⇒ different places


def test_place_uid_is_built_from_the_base_candle_only():
    assert LV.place_uid("1H", "H", "2026-09-25 14:00") == "1H:H:2026-09-25 14:00"
    assert LV.place_uid("D", "L", pd.Timestamp("2026-07-08 00:00")) == "D:L:2026-07-08"
    assert LV.place_uid("W", "H", pd.Timestamp("2026-06-01")) == "W:H:2026-06-01"


@pytest.mark.usefixtures("earlier_break_reading")   # integ51: written on the 12 Oct synthetic fixture (A-L6, conftest)
@pytest.mark.parametrize("mirror", [False, True])
def test_visit_ids_carry_the_place_uid_and_match_across_windows(mirror):
    full, moved = _build(mirror, entry_area_refine="area"), _build(mirror, drop_days=2, entry_area_refine="area")
    day = full.levels.ts.dt.normalize().iloc[-1]
    rows = {}
    for V in (full, moved):
        ts = V.levels.ts
        rows[id(V)] = [e for t in range(len(ts)) if ts.dt.normalize().iloc[t] == day for e in V.decide(t).get("entries") or []]
    a, b = rows[id(full)], rows[id(moved)]
    assert a and any(e["object"] == "area" for e in a)
    assert [(e["visit_id"], e["model"]) for e in a] == [(e["visit_id"], e["model"]) for e in b]   # the claim key does not move
    for V, es in ((full, a), (moved, b)):
        for e in es:
            if e["object"] == "area":
                L = V.levels.L[e["area"]["id"]]
                assert e["visit_id"].split("@")[0] == L.uid == e["area"]["uid"]


def test_cluster_anchor_and_order_never_depend_on_the_list_index():
    def armed(aid, uid, lo, hi):
        return {"object": "area", "area_id": aid, "area_uid": uid, "role": "resistance", "lo": lo, "hi": hi, "direction": -1,
                "visit_start_bar": 10, "visit_start": "x", "visit_id": f"{uid}@x", "models": {"E1": {"status": "fired"}}}
    for ids in ((5, 9), (9, 5)):                                           # the same two places, their indices swapped
        a = armed(ids[0], "1H:H:2026-09-25 14:00", 100.0, 110.0)
        b = armed(ids[1], "1H:H:2026-09-26 10:15", 105.0, 115.0)
        kept = EM.clusters([a, b], [({"model": "E1"}, {}, -1, a), ({"model": "E1"}, {}, -1, b)])
        assert len(kept) == 1                                              # one place ⇒ one E1
        f, _l, _d, x = kept[0]
        assert x["area_uid"] == "1H:H:2026-09-25 14:00"
        assert f["cluster"]["visit_id"] == "1H:H:2026-09-25 14:00@x" and f["cluster"]["id"] == "C1H:H:2026-09-25 14:00"


def test_duplicate_ids_cannot_bypass_max_hits_per_zone(tmp_path):
    """The dashboard limit counts the BAND (overlap + role) — two ids for one place count together."""
    path = str(tmp_path / "es.db")
    for vid in ("281@2026-10-15 10:00:00", "280@2026-10-15 10:00:00"):
        assert ES.claim_entry("bot", "BANKNIFTY", vid, "E1", "EXECUTED", "2026-10-15 10:05:00", path, zone=(-1, 55699.45, 55970.15))
    assert ES.zone_entries_today("bot", "BANKNIFTY", "2026-10-15", -1, 55699.45, 55970.15, path) == 2


# ------------------------------------------------------------------------------------------------ A7: the refined base
def _P(kind, bar, price, conf):
    return NS(kind=kind, bar=bar, price=price, confirm_bar=conf)


def _reader(bars, piv0, piv1, mirror):
    """A stub V: bars = [(o, h, l, c)], pivots per degree (D0 = every 15M turn, D1 = the structure list). mirror ⇒ p ⇒ −p."""
    a = np.array(bars, float)
    if mirror:
        a = -a[:, [0, 2, 1, 3]]
        flip = lambda ps: [_P("L" if p.kind == "H" else "H", p.bar, -p.price, p.confirm_bar) for p in ps]   # noqa: E731
        piv0, piv1 = flip(piv0), flip(piv1)
    A = {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}
    ts = pd.date_range("2030-01-07 09:15", periods=len(a), freq="15min")
    L = NS(born_bar=1, uid="1H:H:2030-01-07 09:15" if not mirror else "1H:L:2030-01-07 09:15", base_ts=ts[0])
    levels = NS(A=A, L=[L], _known0=piv1)
    V = NS(levels=levels, _ts=ts, s={}, res={"pivots": {0: piv0, 1: piv1}})
    return EM.Reader(V)


#        o      h      l      c        the supply area = [100, 110] (bear call); mirror ⇒ demand [−110, −100] (bull put)
BARS = [(95.0, 110.0, 94.0, 100.0),    # 0  the area's birth turn (1H swing candle: wick to body 100 … 110)
        (100.0, 101.0, 90.0, 91.0),    # 1  away
        (91.0, 92.0, 85.0, 86.0),      # 2
        (86.0, 104.0, 85.0, 102.0),    # 3  rally into the band
        (102.0, 106.0, 97.0, 98.0),    # 4  a 15M turn inside the band (D0 only): wick to body 102 … 106
        (98.0, 99.0, 90.0, 91.0),      # 5
        (91.0, 92.0, 88.0, 89.0),      # 6
        (89.0, 111.5, 88.0, 108.0),    # 7  a turn poking just beyond the band: wick to body 108 … 111.5 ⇒ 108 … 110 inside
        (108.0, 109.0, 95.0, 96.0),    # 8
        (96.0, 97.0, 90.0, 91.0),      # 9
        (91.0, 130.0, 91.0, 125.0),    # 10 a gap / spike far above: wick to body 125 … 130 — wholly beyond the band
        (125.0, 126.0, 112.0, 113.0),  # 11
        (113.0, 114.0, 111.0, 112.0)]  # 12
LVL = {"id": 0, "lo": 100.0, "hi": 110.0, "tf": "1H", "role": "resistance"}
LVL_M = {"id": 0, "lo": -110.0, "hi": -100.0, "tf": "1H", "role": "support"}
D0 = [_P("H", 0, 110.0, 1), _P("H", 4, 106.0, 5), _P("H", 7, 111.5, 8), _P("H", 10, 130.0, 11)]
D1 = [_P("H", 0, 110.0, 1)]                                                # the structure list misses the 15M turns


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.usefixtures("turn_base_reading")   # DECISIONS 79: written for the replaced A7 reading (what-if)
def test_refined_base_is_the_newest_15m_turn_inside_the_band_as_its_wick_to_body(mirror):
    R = _reader(BARS, D0, D1, mirror)
    lvl, d = (LVL_M, 1) if mirror else (LVL, -1)
    band = lambda rb: (rb["lo"], rb["hi"]) if not mirror else (-rb["hi"], -rb["lo"])   # noqa: E731
    rb = R.refined(3, lvl, d)                                              # only the birth turn known
    assert rb["bar"] == 0 and band(rb) == (100.0, 110.0)
    rb = R.refined(5, lvl, d)                                              # the 15M turn at bar 4 confirmed ⇒ the newest base
    assert rb["bar"] == 4 and band(rb) == (102.0, 106.0)
    assert R.refined(4, lvl, d)["bar"] == 0                                # no look-ahead: not before its confirmation
    rb = R.refined(8, lvl, d)                                              # a turn poking just beyond the band still counts,
    assert rb["bar"] == 7 and band(rb) == (108.0, 110.0)                   # kept inside the band (never beyond the area, Z-1u)
    rb = R.refined(12, lvl, d)                                             # a turn wholly beyond the band is not a turn inside it
    assert rb["bar"] == 7 and band(rb) == (108.0, 110.0)


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.usefixtures("turn_base_reading")   # DECISIONS 79: written for the replaced A7 reading (what-if)
def test_refined_base_reads_every_15m_turn_not_only_the_structure_list(mirror):
    R = _reader(BARS, D0, D1, mirror)
    lvl, d = (LVL_M, 1) if mirror else (LVL, -1)
    assert R.refined(6, lvl, d)["bar"] == 4                                # D1 alone would have stayed on the birth turn (bar 0)
    R1 = _reader(BARS, [], D1, mirror)                                     # no 15M degree in the stub ⇒ the structure list
    R1.V.res = {"pivots": {}}
    R1.memo.clear()
    assert R1.refined(6, lvl, d)["bar"] == 0


@pytest.mark.parametrize("mirror", [False, True])
def test_refined_base_never_reads_a_turn_from_before_the_area_birth_turn(mirror):
    bars = [(100.0, 105.0, 99.0, 104.0)] + BARS                            # bar 0: an older turn inside the band, before the birth
    shift = [_P(p.kind, p.bar + 1, p.price, p.confirm_bar + 1) for p in D0]
    R = _reader(bars, [_P("H", 0, 105.0, 1)] + shift, [_P("H", 1, 110.0, 2)], mirror)
    R.V.levels.L[0].born_bar = 2
    R.V.levels.L[0].base_ts = R.V._ts[1]                                   # the area's base candle = bar 1
    lvl, d = (LVL_M, 1) if mirror else (LVL, -1)
    assert R.refined(3, lvl, d)["bar"] == 1                                # the birth turn, never the older bar-0 turn


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.usefixtures("turn_base_reading")   # DECISIONS 79: written for the replaced A7 reading (what-if)
def test_refined_base_never_takes_a_turn_from_before_the_area_base_candle_as_its_birth_turn(mirror):
    """L5-N08: a support flipped to resistance — the newest swing HIGH inside its band known at its birth was weeks older than the area
    itself; that old turn is never the area's birth turn (the models wait for a turn of their own)."""
    bars = [(104.0, 108.0, 103.0, 105.0)] + [(90.0, 91.0, 89.0, 90.0)] * 2 + BARS
    shift = [_P(p.kind, p.bar + 3, p.price, p.confirm_bar + 3) for p in D0]
    R = _reader(bars, [_P("H", 0, 108.0, 1)] + shift, [], mirror)
    R.V.levels.L[0].born_bar = 4
    R.V.levels.L[0].base_ts = R.V._ts[3]
    lvl, d = (LVL_M, 1) if mirror else (LVL, -1)
    assert R.refined(4, lvl, d)["bar"] == 3                                # its own base turn, not the bar-0 high from before
    R.V.levels.L[0].base_ts = R.V._ts[3] + pd.Timedelta(minutes=1)         # no turn of its own at birth ⇒ from the birth bar on
    R.memo.clear()
    assert R.refined(4, lvl, d) is None and R.refined(8, lvl, d)["bar"] == 7


# ------------------------------------------------------------------------------------------------ A6: the band rule
@pytest.mark.parametrize("mirror", [False, True])
def test_a_swing_band_is_its_own_candle_wick_to_body_never_a_union(mirror):
    """L5-E41 / area 298: the 1H swing candle O 54,840.65 H 55,192.65 L 54,719.35 C 54,886.20 ⇒ wick to body 54,886.20 … 55,192.65 —
    its own upper wick (no other level joined)."""
    o, h, l, c = 54840.65, 55192.65, 54719.35, 54886.20
    if not mirror:
        assert LV._band_swing("H", o, h, l, c, h, 0) == (54886.20, 55192.65)
    else:
        lo, hi = LV._band_swing("L", -o, -l, -h, -c, -h, 0)
        assert (lo, hi) == (-55192.65, -54886.20)
