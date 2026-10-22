"""PA standard §1 + §2A (track t1): decision3/mtf_state.py — per-timeframe market state in one vocabulary, agreement, external /
internal structure with HH / HL / LH / LL and BOS / CHoCH. Synthetic data only (real-data checks run separately under the heavy lock)."""
import inspect
import re
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import daily as DD
from decision3 import mtf_state as MS


def P(kind, price, bar, confirm=None, eq=False):
    return MS.SP(kind, float(price), int(bar), pd.Timestamp("2030-01-01") + pd.Timedelta(minutes=15 * bar),
                 int(bar + 1 if confirm is None else confirm), eq)


# ------------------------------------------------------------------------------------------------ pure comparisons
def test_trend_of_vocabulary():
    up = [P("L", 100, 0), P("H", 120, 5), P("L", 110, 10), P("H", 130, 15)]
    dn = [P("H", 130, 0), P("L", 110, 5), P("H", 120, 10), P("L", 100, 15)]
    assert MS.trend_of(up) == MS.UP
    assert MS.trend_of(dn) == MS.DOWN
    assert MS.trend_of(up[:3]) == MS.UNKNOWN
    assert MS.trend_of([P("L", 100, 0), P("H", 120, 5), P("L", 90, 10), P("H", 130, 15)]) == MS.RANGE      # HH + LL
    assert MS.trend_of(up[:3] + [P("H", 120, 15, eq=True)]) == MS.RANGE                                     # equal high


def test_labels_hh_hl_lh_ll_eq():
    ps = [P("L", 100, 0), P("H", 120, 5), P("L", 110, 10), P("H", 130, 15), P("L", 105, 20), P("H", 125, 25),
          P("H", 125, 30, eq=True)]
    assert MS.labels(ps) == ["L", "H", "HL", "HH", "LL", "LH", "EQH"]


def test_alternate_keeps_more_extreme_and_respects_confirm():
    raw = [P("H", 120, 5, 6), P("H", 125, 7, 8), P("L", 100, 9, 10), P("H", 118, 12, 13)]
    seq = MS.alternate(raw)
    assert [(p.kind, p.price) for p in seq] == [("H", 125), ("L", 100), ("H", 118)]
    assert [(p.kind, p.price) for p in MS.alternate(raw, upto=6)] == [("H", 120)]                            # nothing after t


def _closes_from(points, per_leg=5):
    out = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        out += list(np.linspace(a, b, per_leg + 1)[1:])
    return np.array(out, float)


def test_dow_events_bos_then_choch_each_once_and_causal():
    # up structure L0 H5 L10 H15 L20, a close above H15 (BOS), H25 confirmed, then a close below L20 (CHoCH: the low before the
    # last high — swings2's strict low)
    C = _closes_from([100, 120, 110, 130, 115, 135, 104, 100])
    raw = [P("L", 100, 0, 1), P("H", 120, 5, 6), P("L", 110, 10, 11), P("H", 130, 15, 16), P("L", 115, 20, 21), P("H", 135, 25, 27)]
    ev = MS.dow_events(raw, C)
    bos = [e for e in ev if e["type"] == "BOS"]
    choch = [e for e in ev if e["type"] == "CHoCH"]
    assert bos and bos[0]["level"] == 130 and bos[0]["dir"] == 1 and C[bos[0]["bar"]] > 130
    assert choch and choch[0]["level"] == 115 and choch[0]["dir"] == -1 and C[choch[0]["bar"]] < 115
    assert len({(e["type"], e["pivot_bar"]) for e in ev}) == len(ev)                                         # each swing fires once
    for k in range(5, len(C)):                                                                               # no look-ahead
        part = MS.dow_events([p for p in raw if p.confirm_bar < k], C[:k])
        assert part == [e for e in ev if e["bar"] < k]


def test_swing_state_correction_vs_trending():
    C = _closes_from([100, 120, 110, 130, 122], per_leg=5)        # last bar 20 — the counter-move after H 130
    seq = [P("L", 100, 0), P("H", 120, 5), P("L", 110, 10), P("H", 130, 15)]
    s, side, why = MS.swing_state(MS.UP, seq, C, len(C) - 1, [])
    assert (s, side) == (MS.CORR_S, 1) and "130" in why
    C2 = np.r_[C, 131.0]                                           # a close above the high ⇒ BOS ⇒ trending again
    assert MS.swing_state(MS.UP, seq, C2, len(C2) - 1, [])[0] == MS.UP_S
    seq_hl = seq + [P("L", 122, 20)]                               # HL confirmed ⇒ impulse leg running
    assert MS.swing_state(MS.UP, seq_hl, C, len(C) - 1, [])[0] == MS.UP_S
    ch = [{"type": "BOS", "dir": 1, "level": 120.0}, {"type": "CHoCH", "dir": -1, "level": 110.0}]
    s, _, why = MS.swing_state(MS.UP, seq_hl, C, len(C) - 1, ch)
    assert s == MS.CORR_S and "CHoCH" in why
    assert MS.swing_state(MS.RANGE, seq, C, 3, [], band=(100, 130))[0] == MS.RANGE_S
    assert MS.swing_state(MS.UNKNOWN, seq[:2], C, 3, [])[0] == MS.UNCLEAR_S
    dn = [P("H", 130, 0), P("L", 110, 5), P("H", 120, 10), P("L", 100, 15)]
    Cd = _closes_from([130, 110, 120, 100, 108])
    assert MS.swing_state(MS.DOWN, dn, Cd, len(Cd) - 1, [])[:2] == (MS.CORR_S, -1)


def _dst(trend, phase=None, counter=None, band=None, prot=None):
    p = DD.DPivot("H", prot, 3, pd.Timestamp("2030-01-01"), 5, pd.Timestamp("2030-01-01")) if prot else None
    return DD.DState(10, pd.Timestamp("2030-01-10"), pd.Timestamp("2030-01-10 15:30"), trend, protected=p, band=band, phase=phase,
                     counter=counter, corr_label="b")


def test_daily_state_mapping():
    assert MS._daily_word(_dst("DOWN", "impulse", None, prot=200))[:2] == (MS.DOWN_S, -1)
    assert MS._daily_word(_dst("DOWN", "impulse", "pullback", prot=200))[:2] == (MS.CORR_S, -1)
    assert MS._daily_word(_dst("UP", "correction", "candidate"))[:2] == (MS.CORR_S, 1)
    assert MS._daily_word(_dst("UP", "correction", "correction"))[:2] == (MS.CORR_S, 1)
    assert MS._daily_word(_dst("UP", "origin_broken"))[:2] == (MS.CORR_S, 1)
    assert MS._daily_word(_dst("RANGE", band=(100, 120)))[0] == MS.RANGE_S
    assert MS._daily_word(_dst("NEUTRAL"))[0] == MS.UNCLEAR_S
    assert MS._daily_word(_dst("UNKNOWN"))[0] == MS.UNCLEAR_S


def test_agreement_lists():
    st = {"W": {"state": MS.RANGE_S, "side": 0}, "D": {"state": MS.DOWN_S, "side": -1},
          "1H": {"state": MS.DOWN_S, "side": -1}, "15M": {"state": MS.CORR_S, "side": -1}, "5M": {"state": MS.UP_S, "side": 1}}
    ag = MS.agreement(st)
    assert ag["side"] == "DOWN" and ag["relation"]["D"] == "reference"
    assert ag["agrees"] == ["1H"] and ag["correction"] == ["15M"] and ag["against"] == ["5M"] and ag["range"] == ["W"]
    assert not ag["all_agree"] and "agrees: 1H" in ag["line"]
    ag2 = MS.agreement(st, d=1)                                    # an explicit direction (e.g. a range edge) ⇒ D compared too
    assert ag2["side"] == "UP" and ag2["against"] == ["D", "1H", "15M"] and ag2["agrees"] == ["5M"]
    st0 = {**st, "D": {"state": MS.RANGE_S, "side": 0}}
    assert MS.agreement(st0)["side"] is None


# ------------------------------------------------------------------------------------------------ synthetic V22 (integration)
def _path(points, per_leg):
    out = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        out += list(np.linspace(a, b, per_leg + 1)[1:])
    return out


def _m15(closes, start="2030-01-07", per_day=25, wick=1.0):
    rows, prev = [], closes[0]
    days = pd.bdate_range(start, periods=(len(closes) + per_day - 1) // per_day)
    for i, c in enumerate(closes):
        d = days[i // per_day]
        ts = d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % per_day))
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": prev, "close": c,
                     "high": max(prev, c) + wick, "low": min(prev, c) - wick})
        prev = c
    return pd.DataFrame(rows)


def _ltf(m15):
    rows = []
    for r in m15.itertuples():
        mids = [r.open + k * (r.close - r.open) / 3 for k in range(4)]
        for k in range(3):
            ts = r.timestamp + pd.Timedelta(minutes=5 * k)
            a, b = mids[k], mids[k + 1]
            rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=5), "open": a, "close": b, "high": max(a, b) + 0.5,
                         "low": min(a, b) - 0.5})
    return pd.DataFrame(rows)


def synthetic_closes(n_legs=60):
    rng = np.random.default_rng(7)
    pts, x = [1000.0], 1000.0
    for k in range(n_legs):
        x += 120 if k % 2 == 0 else -70
        pts.append(x)
    out = []
    for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        out += list(np.linspace(a, b, (8 if b > a else 24) + 1)[1:])   # fast up legs, slow down legs
    return list(np.r_[pts[0], np.array(out)] + rng.normal(0, 0.6, len(out) + 1))


@pytest.fixture(scope="module")
def V():
    from decision3 import engine as E3
    m = _m15(synthetic_closes())
    return E3.V22(m, ltf=_ltf(m))


def test_read_shape_vocabulary_and_story(V):
    t = len(V.m15) - 1
    r = MS.read_mtf_state(V, t)
    assert set(r["tfs"]) == set(MS.TFS) and r["evidence_only"] is True
    words = {MS.UP_S, MS.DOWN_S, MS.RANGE_S, MS.CORR_S, MS.UNCLEAR_S}
    for tf in MS.TFS:
        x = r["tfs"][tf]
        assert x["state"] in words and x["side"] in (-1, 0, 1)
        assert "external" in x["structure"] and "internal" in x["structure"]
    for tf in ("1H", "15M", "5M"):                                 # the synthetic market climbs: HH / HL on the swing timeframes
        assert r["tfs"][tf]["trend"] == MS.UP
        labs = [p["label"] for p in r["tfs"][tf]["structure"]["external"]["pivots"]]
        assert set(labs) <= {"HH", "HL", "H", "L"} and "HH" in labs and "HL" in labs
        assert any(e["type"] == "BOS" and e["dir"] == "up" for e in r["tfs"][tf]["structure"]["external"]["events"])
    assert r["tfs"]["1H"]["structure"]["external"]["degree"] == "D2"
    assert r["tfs"]["15M"]["structure"]["external"]["degree"] == "D1"
    assert r["tfs"]["15M"]["structure"]["internal"]["degree"] == "D0"
    assert len(r["story"]) == len(MS.TFS) + 1 and r["story"][-1].startswith("agreement:")
    assert MS.evidence(r)[-1] == r["agreement"]["line"]


def test_draw_objects_shape(V):
    t = len(V.m15) - 1
    objs = MS.draw_objects(V, t)
    keys = {"kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "evidence"}
    assert objs and all(set(o) == keys for o in objs)
    kinds = {o["kind"] for o in objs}
    assert {"tf_state", "swing", "bos"} <= kinds
    assert {o["tf"] for o in objs if o["kind"] == "tf_state"} == set(MS.TFS)


def test_no_look_ahead_truncation(V):
    """Reading at bar t on the full data = reading at t on data cut at t (the last bar of a Friday session ⇒ the Weekly bar is complete
    in both)."""
    from decision3 import engine as E3
    ts = pd.to_datetime(V.m15["timestamp"])
    fri = [i for i in range(len(ts) - 1) if ts.iloc[i].dayofweek == 4 and ts.iloc[i + 1].normalize() != ts.iloc[i].normalize()]
    t = fri[-2]
    cut = V.m15.iloc[:t + 1].reset_index(drop=True)
    V2 = E3.V22(cut, ltf=_ltf(cut))
    a, b = MS.read_mtf_state(V, t), MS.read_mtf_state(V2, t)
    for tf in MS.TFS:
        assert a["tfs"][tf]["state"] == b["tfs"][tf]["state"], tf
        assert a["tfs"][tf]["detail"] == b["tfs"][tf]["detail"], tf
        assert a["tfs"][tf]["structure"] == b["tfs"][tf]["structure"], tf
    assert a["agreement"] == b["agreement"]


def test_method_pure_no_dates_no_new_settings():
    src = inspect.getsource(MS)
    assert not re.search(r"20\d\d-\d\d-\d\d", src)
    assert "settings2" not in src and "c_hi" not in src
    from decision3 import settings as S3
    assert not any(k.startswith("mtf") for k in S3.DEFAULTS)


def test_range_detail_says_when_price_closed_beyond_an_edge_without_a_swing_beyond():
    """Reading check (BANKNIFTY 09–11 Jun, §1 MTF state / DECISIONS 16 / T4): a contracting 15M range (LH + HL) that price leaves by
    closes above its high with no swing formed beyond stays "range" (not a confirmed break), but the detail says price closed above
    the high since the last swing. Mirror below the low. Bars after j are never read (no look-ahead)."""
    seq = [P("H", 130, 0), P("L", 100, 5), P("H", 125, 10), P("L", 105, 15)]          # LH + HL ⇒ RANGE 100–130
    assert MS.trend_of(seq) == MS.RANGE
    band = MS._band(seq)
    assert band == (100.0, 130.0)
    C = _closes_from([130, 100, 125, 105, 128], per_leg=5)                                # back inside: no close beyond
    s, side, why = MS.swing_state(MS.RANGE, seq, C, len(C) - 1, [], band=band)
    assert (s, side) == (MS.RANGE_S, 0) and "closed" not in why
    Cu = np.r_[C, 131.0, 140.0]                                                           # closes above the high, no swing beyond
    s, side, why = MS.swing_state(MS.RANGE, seq, Cu, len(Cu) - 1, [], band=band)
    assert (s, side) == (MS.RANGE_S, 0) and "closed above its high 130.00" in why and "not a confirmed break" in why
    assert "closed" not in MS.swing_state(MS.RANGE, seq, Cu, len(C) - 1, [], band=band)[2]   # at j before the closes: unchanged
    Cd = np.r_[C, 99.0]                                                                   # mirror: a close below the low
    assert "closed below its low 100.00" in MS.swing_state(MS.RANGE, seq, Cd, len(Cd) - 1, [], band=band)[2]
    Cb = np.r_[C, 131.0, 99.0]                                                            # both sides ⇒ the newest close decides
    assert "below its low" in MS.swing_state(MS.RANGE, seq, Cb, len(Cb) - 1, [], band=band)[2]
