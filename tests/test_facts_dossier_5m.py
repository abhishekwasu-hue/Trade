"""tests/test_facts_dossier_5m.py — DECISIONS 37 / 51: the facts dossier follows the engine's 5M decision (L6-O7 / O8 / O9 / O12).

"Every output reads exactly what the engine read at the decision": with decision3 `trigger_tf = 5M` (the default) every dossier field
equals the engine's own read at the 5M close (V22.decide5 on the same bars) — the visit (a visit may start on a 5M candle inside the 15M
bar in progress, O-7), the required set on the visit's 5M candles (O-8), the E4 (b) objects with their lifecycle and revisit (O-9) and
the liquidity on the engine's levels with the Daily frame (O-12). `trigger_tf = 15M` (what-if) = the earlier dossier byte for byte
(pinned against the output of the code before this change, tests/fixtures/dossier_15m_pin.json.gz). Synthetic bars only (the 12-Oct
reference shape, tests/oct12_fixture.py), both price mirrors. No network, no API, no AI."""
import gzip
import json
import os

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import entry_models5 as EM5
from decision3 import liquidity as LQ
from decision3 import method as M
from facts import dossier as D
from tests import test_facts_dossier as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN = os.path.join(ROOT, "tests", "fixtures", "dossier_15m_pin.json.gz")
COLS = ["timestamp", "bar_end", "open", "high", "low", "close"]
S_AREA = {"entry_area_refine": "area"}       # an existing what-if setting under which the fixture's visit fires E2 / E3 on 5M


def _engine(m15, fut, ltf, as_of, s=None):
    """The engine itself on the bars closed at as_of (as the live loop feeds it) and its decision at the last 5M close."""
    V = E3.V22(T._cut(m15, as_of, 15)[COLS], None, None, ltf=T._cut(ltf, as_of, 5), futures=T._cut(fut, as_of, 5), s=s)
    F = V.trigger_frame()
    j = int(np.searchsorted(F.end, np.datetime64(as_of, "ns"), side="right")) - 1
    return V, F, j, V.decide5(j)


def _five(mirror, as_of_fn, s=None):
    m15, fut, ltf, one = T._inputs(mirror=mirror)
    as_of = as_of_fn(m15)
    cfg = {} if s is None else {"cfg": {"decision3": s}}
    return (m15, fut, ltf, one, as_of), T._dossier(m15, fut, ltf, one, as_of, **cfg)


def _at_5m(m15, minutes):
    """A 5M close inside the fixture's last session: the session open + `minutes`."""
    ts = pd.to_datetime(m15["timestamp"])
    return pd.Timestamp(ts[ts.dt.normalize() == ts.dt.normalize().iloc[-1]].iloc[0]) + pd.Timedelta(minutes=minutes)


@pytest.fixture(scope="module")
def fired():
    """The 09:30 5M close (the 5M candle 09:25): E2 + E3 fire at the supply area's visit (bear) / the mirrored demand (bull)."""
    return {mi: _five(mi, lambda m: _at_5m(m, 15), S_AREA) for mi in (False, True)}


@pytest.fixture(scope="module")
def in_progress():
    """The 09:25 5M close: the visit began at 09:15 on 5M, inside the 15M bar 09:15 still in progress."""
    return {mi: _five(mi, lambda m: _at_5m(m, 10)) for mi in (False, True)}


# ------------------------------------------------------------------------------------------------ 15M what-if = the earlier dossier
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("k", [1, 2])
def test_trigger_tf_15m_is_the_earlier_dossier_byte_for_byte(mirror, k):
    pin = json.loads(gzip.decompress(open(PIN, "rb").read()))
    m15, fut, ltf, one = T._inputs(mirror=mirror)
    d = T._dossier(m15, fut, ltf, one, T._asof(m15, k), cfg={"decision3": {"trigger_tf": "15M"}})
    assert set(d["sections"]) == set(D.SECTIONS) == set(D.sections_of("15M"))
    assert json.loads(json.dumps(d, sort_keys=True)) == pin[f"{mirror}|{k}"]


def test_trigger_tf_typo_fails_loudly():
    m15, fut, ltf, one = T._inputs()
    with pytest.raises(ValueError, match="trigger_tf"):
        T._dossier(m15, fut, ltf, one, T._asof(m15, 1), cfg={"decision3": {"trigger_tf": "1M"}})


# ------------------------------------------------------------------------------------------------ the engine's row = the trigger section
@pytest.mark.parametrize("mirror", [False, True])
def test_trigger_section_is_the_engines_own_5m_row(fired, mirror):
    (m15, fut, ltf, one, as_of), d = fired[mirror]
    S = d["sections"]
    assert set(S) == set(D.SECTIONS_5M) and all(x["status"] == D.OK for x in S.values()), {k: x.get("reason") for k, x in S.items()}
    V, F, j, row = _engine(m15, fut, ltf, as_of, S_AREA)
    tg = S["trigger"]
    assert tg["candle"]["bar_end"] == F.E(j) == str(as_of) and tg["context_bar"]["ts"] == row["context_ts"]
    assert tg["entries"] == D._j([D._entry_facts(e) for e in row["entries"]]) and tg["armed"] == D._j(row["armed"])
    assert {e["model"] for e in tg["entries"]} == {"E2", "E3"}                 # the fixture's visit fires on 5M
    assert S["areas"]["asof_bar"] == row["context_ts"]                          # areas at the decision's own 15M bar k(j)


# ------------------------------------------------------------------------------------------------ O-7 visit / O-8 required set
@pytest.mark.parametrize("mirror", [False, True])
def test_visit_and_required_set_are_the_engines_5m_reads(fired, mirror):
    (m15, fut, ltf, one, as_of), d = fired[mirror]
    V, F, j, row = _engine(m15, fut, ltf, as_of, S_AREA)
    R = EM5.Reader5(V, j)
    st = d["sections"]["candles"]["area_studies"]
    for e in row["entries"]:
        x = next(s for s in st if s["visit_id"] == e["area_visit_id"])
        assert x["arrival"]["ts"] == e["area_visit_start"] and x["arrival"]["ts5"] == e["visit_start5"]
        de = next(y for y in x["entries"] if y["model"] == e["model"])
        assert de["evidence_list"] == D._j(e["evidence_list"]) and de["refined_base"] == D._j(e["refined_base"])
        assert x["required_set"]["by_model"][e["model"]] == e["evidence_list"]["required"]   # the entry's required set as the engine wrote it
        lvl = next(a for a in row["active_levels"] if a["id"] == e["area"]["id"])
        d_ = int(e["direction"])
        vi = R.visit5(j, lvl, d_)
        ok5, cm5 = R.confirm5(lvl, d_, int(vi["start5"]), R.appr5(vi))
        assert x["required_set"]["read"] == ("present" if ok5 else "absent")
        assert x["required_set"]["ltf_choch"] == cm5["choch"]["done"] and x["handover"]["present"] == cm5["handover_state"]["present"]
        lc = next(y for y in d["sections"]["ltf_choch"]["visits"] if y["visit_id"] == x["visit_id"])
        assert lc["done"] == cm5["choch"]["done"] and lc["study_from"] == e["visit_start5"] and lc["study_to"] == str(as_of)
        a = next(y for y in row["armed"] if y.get("visit_id") == e["area_visit_id"])
        assert x["models"] == D._j(a["models"])


@pytest.mark.parametrize("mirror", [False, True])
def test_a_visit_starting_inside_the_15m_bar_in_progress_is_seen(in_progress, mirror):
    """L6-O7: the 5M visit begins inside the 15M bar in progress — the 15M dossier (last closed 15M bar) finds no visit for the area; the
    5M dossier has it, with the engine's visit id and 5M start."""
    (m15, fut, ltf, one, as_of), d = in_progress[mirror]
    V, F, j, row = _engine(m15, fut, ltf, as_of)
    live = [a for a in row["armed"] if a.get("object") == "area"]
    assert live, "the fixture's visit is armed at this 5M close"
    st = {x["visit_id"]: x for x in d["sections"]["candles"]["area_studies"]}
    for a in live:
        x = st[a["visit_id"]]
        assert x["arrival"]["ts5"] == a["visit_start5"] and x["arrival"]["ts"] == a["visit_start"] and x["arrival"]["bin15_in_progress"]
    old = T._dossier(m15, fut, ltf, one, as_of, cfg={"decision3": {"trigger_tf": "15M"}})
    assert not [x for x in old["sections"]["candles"]["area_studies"] if str(x["area_id"]) in {str(a["area_id"]) for a in live}]


# ------------------------------------------------------------------------------------------------ O-9 E4 (b) objects
@pytest.mark.parametrize("mirror", [False, True])
def test_e4b_objects_are_the_engines_broken_objects_with_lifecycle_and_revisit(in_progress, mirror):
    (m15, fut, ltf, one, as_of), d = in_progress[mirror]
    V, F, j, row = _engine(m15, fut, ltf, as_of)
    R = EM5.Reader5(V, j)
    ob = d["sections"]["e4b_objects"]
    dd = M._dir(row["trend_used"])
    want = [(o["id"] if k == "area" else f"line:{o['id']}", k) for k, o, *_ in R.broken_objects(int(F.k_of[j]), dd)]
    assert [(x["id"], x["object"].split("_")[1]) for x in ob["objects"]] == want and want
    eng = {a["area_id"]: a for a in row["armed"] if str(a.get("object", "")).startswith("broken_")}
    assert eng, "the fixture has a broken line being revisited at this 5M close"
    for x in ob["objects"]:
        assert x["lifecycle"] and x["broken_at"]
        if x["id"] in eng:
            a = eng[x["id"]]
            assert x["revisit"]["visit_id"] == a["visit_id"] and x["revisit"]["visit_start5"] == a["visit_start5"]
            assert x["revisit"]["models"] == D._j(a["models"]) and x["required_set"]["tf"] == "5M"
            if x["object"] == "broken_line":
                assert x["value_at_decision"] == pytest.approx(a["lo"], abs=0.01)
        else:
            assert x["revisit"] is None and x["revisit_why"]
    other = in_progress[not mirror][1]["sections"]["e4b_objects"]["objects"]
    assert len(other) == len(ob["objects"]) and [x["object"] for x in other] == [x["object"] for x in ob["objects"]]


# ------------------------------------------------------------------------------------------------ O-12 liquidity with the Daily frame
@pytest.mark.parametrize("mirror", [False, True])
def test_liquidity_reads_the_engines_levels(fired, mirror):
    (m15, fut, ltf, one, as_of), d = fired[mirror]
    V, F, j, row = _engine(m15, fut, ltf, as_of, S_AREA)
    k = int(F.k_of[j])
    lq = d["sections"]["liquidity"]
    assert lq["pools"] == D._j(LQ.pools(V, k)) and lq["daily_frame"]["daily_bars"] == len(V.daily_df)
    for e in row["entries"]:
        v = next(x for x in lq["at_visits"] if x["visit_id"] == e["area_visit_id"])
        arm15 = min(int(F.b_of[F.first_at_or_after(e["visit_start5"])]), k)
        sw, tr = LQ.sweeps_and_traps(V, k, start=arm15)
        assert [{kk: y[kk] for kk in y if kk != "ts"} for y in v["sweeps"]] == D._j(sw)
        assert [{kk: y[kk] for kk in y if kk != "ts"} for y in v["traps"]] == D._j(tr)


def test_liquidity_uses_the_daily_frame_when_given():
    """O-12: with Daily bars the dossier's liquidity is read on the engine's levels built WITH the Daily frame (Q40 prior levels)."""
    m15, fut, ltf, one = T._inputs()
    as_of = _at_5m(m15, 15)
    days = pd.to_datetime(m15["timestamp"]).dt.normalize()
    daily = m15.assign(timestamp=days).groupby("timestamp").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                                close=("close", "last")).reset_index()
    x = D.build_dossier("SYNTH", {"15M": m15, "5M": ltf, "1m": one, "D": daily}, {"5M": fut}, as_of=as_of,
                        cfg={"legs_reader": T.RR.read})
    lq = x["sections"]["liquidity"]
    assert lq["status"] == D.OK and lq["daily_frame"]["daily_bars"] == int((daily["timestamp"] < as_of.normalize()).sum())


# ------------------------------------------------------------------------------------------------ no look-ahead
@pytest.mark.parametrize("mirror", [False, True])
def test_5m_dossier_never_reads_after_as_of(fired, mirror):
    (m15, fut, ltf, one, as_of), d = fired[mirror]
    cut = T._dossier(T._cut(m15, as_of, 15), T._cut(fut, as_of, 5), T._cut(ltf, as_of, 5), T._cut(one, as_of, 1), as_of,
                     cfg={"decision3": S_AREA})
    assert cut == d
    later = ltf.copy()
    nxt = pd.to_datetime(later["timestamp"]) >= as_of                         # change every 5M bar after as_of: nothing moves
    later.loc[nxt, ["high", "close"]] = later.loc[nxt, ["high", "close"]] + 500.0
    assert T._dossier(m15, fut, later, one, as_of, cfg={"decision3": S_AREA}) == d


def test_5m_bars_missing_is_said_never_a_15m_reread():
    m15, fut, ltf, one = T._inputs()
    x = T._dossier(m15, fut, ltf, one, T._asof(m15, 1), drop=("5M", "1m"))   # (the engine builds 5M from 1m when given)
    S = x["sections"]
    assert S["trigger"]["status"] == D.NA and "5M spot bars missing" in S["trigger"]["reason"]
    assert S["candles"]["area_studies"] is None and "5M" in S["candles"]["area_studies_reason"]
    assert S["e4b_objects"]["status"] == D.NA
