"""tests/test_facts_dossier.py — R1b: facts/dossier.build_dossier (design docs/design/CHART_READER_AGENT.md §3, §13).

Synthetic bars only for the CI part (tests/oct12_fixture.py — the 12-Oct reference shape, dates far from the holdout; 1m / 5M split
from its 15M bars). No network, no API, no AI. The real-data golden part reuses the R1a fixture of tests/test_r1_golden_lines.py
(private trade-data; skipped cleanly when absent) and only its own expectations (the 30 Sep → 6 Oct line, the ≈22,667 supply band).
"""
import ast
import json
import os

import pandas as pd
import pytest

from elliott import data_policy as DP
from facts import dossier as D
from facts import validity as V
from reader2 import reader as RR
from tests import oct12_fixture as F
from tests import test_r1_golden_lines as G
from tests.ltf_fixtures import split_bars
from tests.test_legs2 import DATE_RX_I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _inputs(mirror=False):
    m15, fut, ltf = F.build(mirror=mirror)
    one = split_bars(m15, 15, 15)
    return m15, fut, ltf, one


def _asof(m15, k=2):
    """Close of the k-th 15M bar of the fixture's last session (k = 2 ⇒ the 09:45 bar closes at 10:00)."""
    ts = pd.to_datetime(m15["timestamp"])
    last = ts.dt.normalize().iloc[-1]
    return pd.Timestamp(m15[ts.dt.normalize() == last]["bar_end"].iloc[k])


def _dossier(m15, fut, ltf, one, as_of, **kw):
    bars = {"15M": m15, "5M": ltf, "1m": one}
    for k in kw.pop("drop", ()):
        bars.pop(k, None)
    cfg = {"legs_reader": RR.read, **kw.pop("cfg", {})}                     # reader2 is research-only: the test injects it (R1b-6)
    return D.build_dossier("SYNTH", bars, {"5M": fut} if fut is not None else None, as_of=as_of, cfg=cfg, **kw)


def _cut(df, as_of, minutes):
    end = pd.to_datetime(df["bar_end"]) if "bar_end" in df.columns else pd.to_datetime(df["timestamp"]) + pd.Timedelta(minutes=minutes)
    return df[end <= as_of].reset_index(drop=True)


@pytest.fixture(scope="module")
def world():
    m15, fut, ltf, one = _inputs()
    as_of = _asof(m15)
    return m15, fut, ltf, one, as_of, _dossier(m15, fut, ltf, one, as_of)


def _walk(x, path=()):
    if isinstance(x, dict):
        for k, v in x.items():
            yield path + (k,), k, v
            yield from _walk(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _walk(v, path + (i,))


# ------------------------------------------------------------------------------------------------ shape
def test_every_section_present_with_status_and_owner(world):
    *_, as_of, d = world
    assert d["schema"] == D.SCHEMA and d["as_of"] == str(as_of)
    assert set(d["sections"]) == set(D.SECTIONS) == set(D.OWNERS)
    for name, sec in d["sections"].items():
        assert sec["status"] in (D.OK, D.NA), name
        assert sec["owner"], name
        if sec["status"] == D.NA:
            assert sec["reason"], name
    assert [n for n, s in d["sections"].items() if s["status"] != D.OK] == [], \
        {n: s.get("reason") for n, s in d["sections"].items() if s["status"] != D.OK}   # all inputs given ⇒ every owner answers


def test_output_is_json_serialisable(world):
    *_, d = world
    s = json.dumps(d, allow_nan=False)
    assert json.loads(s) == d


def test_no_vote_score_or_grade_anywhere(world):
    *_, d = world
    bad = [p for p, k, _ in _walk(d) if k in D.NOT_FACTS]
    assert not bad, bad[:5]
    for st in d["sections"]["candles"]["area_studies"]:
        assert "grade" not in st["commitment"]["reason"]


def test_asof_bar_and_inputs_are_closed_bars_only(world):
    m15, fut, ltf, one, as_of, d = world
    for tf, info in d["inputs"].items():
        if info != "missing":
            assert pd.Timestamp(info["last_close_at"]) <= as_of, tf
    assert d["asof_bar"]["ts"] == str(pd.Timestamp(as_of) - pd.Timedelta(minutes=15))
    assert d["inputs"]["D"] == "missing"


def test_sections_carry_evidence(world):
    m15, *_, as_of, d = world
    S = d["sections"]
    st = S["structure"]["degrees"]
    assert {f"D{k}" for k in range(5)} == set(st) and "state" in st["D1"] and "state" in st["D2"]
    for p in st["D1"]["pivots"]:
        assert pd.Timestamp(p["known_at"]) <= as_of and {"price", "ts", "kind"} <= set(p)
    A = S["areas"]                                                           # layer 6b: the decision's own areas + K4 state
    assert A["areas"] and all(a["hi"] >= a["lo"] and a["state"] and a["tf"] in ("1H", "D", "W") and a["born_ts"] for a in A["areas"])
    assert A["trend"]["used"] in ("UP", "DOWN", "RANGE", "NEUTRAL", "UNKNOWN") and set(A["armed"]) <= {a["id"] for a in A["areas"]}
    assert S["lines"]["lines"] and S["lines"]["rule"] == "logic"
    for ln in S["lines"]["lines"]:                                           # two separate reactions; touches counted by reactions
        assert ln["p1"]["bar"] < ln["p2"]["bar"] and ln["touches"] == len(ln["touch_points"]) >= 2
    for tf in ("15M", "1H"):
        assert S["legs"]["by_tf"][tf]["legs"]
    assert S["volume"]["last_bar"]["volume"] > 0
    assert S["context"]["prev_day"]["high"] >= S["context"]["prev_day"]["low"]
    assert S["candles"]["last_bar"]["ts"] == d["asof_bar"]["ts"]


# ------------------------------------------------------------------------------------------------ no look-ahead
def test_truncating_future_bars_does_not_change_the_dossier(world):
    m15, fut, ltf, one, as_of, d = world
    cut = _dossier(_cut(m15, as_of, 15), _cut(fut, as_of, 5), _cut(ltf, as_of, 5), _cut(one, as_of, 1), as_of)
    assert cut == d
    assert _dossier(_cut(m15, as_of, 15), _cut(fut, as_of, 5), _cut(ltf, as_of, 5), _cut(one, as_of, 1), None) == d   # default as_of


def test_mid_bar_asof_ignores_the_running_bar(world):
    m15, fut, ltf, one, as_of, _ = world
    mid = as_of + pd.Timedelta(minutes=5)                                     # the 10:00 15M bar is still running at 10:05
    full = _dossier(m15, fut, ltf, one, mid)
    assert full["asof_bar"]["ts"] == str(as_of - pd.Timedelta(minutes=15))
    assert full == _dossier(_cut(m15, mid, 15), _cut(fut, mid, 5), _cut(ltf, mid, 5), _cut(one, mid, 1), mid)


def test_changing_a_future_bar_changes_nothing(world):
    m15, fut, ltf, one, as_of, d = world
    m2, f2 = m15.copy(), fut.copy()
    later = pd.to_datetime(m2["bar_end"]) > as_of
    m2.loc[later, ["high", "close"]] = m2.loc[later, ["high", "close"]] + 500.0
    f2.loc[pd.to_datetime(f2["timestamp"]) + pd.Timedelta(minutes=5) > as_of, "volume"] = 9e9
    assert _dossier(m2, f2, ltf, one, as_of) == d


# ------------------------------------------------------------------------------------------------ NA paths (never a silent pass)
def test_fut_volume_missing_is_na(world):
    m15, fut, ltf, one, as_of, _ = world
    d = _dossier(m15, None, ltf, one, as_of)
    v = d["sections"]["volume"]
    assert v["status"] == D.NA and "FUT volume missing" in v["reason"]
    assert d["sections"]["candles"]["status"] == D.OK and d["sections"]["candles"]["volume_source"].startswith("NA")
    shifted = fut.assign(timestamp=pd.to_datetime(fut["timestamp"]) + pd.Timedelta(hours=7))    # FUT rows only outside the session
    v2 = _dossier(m15, shifted, ltf, one, as_of)["sections"]["volume"]
    assert v2["status"] == D.NA and "FUT volume missing" in v2["reason"]


def test_missing_ltf_and_1m_are_na(world):
    m15, fut, ltf, one, as_of, _ = world
    d = _dossier(m15, fut, ltf, one, as_of, drop=("5M", "1m"))
    S = d["sections"]
    assert S["ltf_choch"]["status"] == D.NA and "5M" in S["ltf_choch"]["reason"]
    assert S["gaps"]["status"] == D.NA and "1m" in S["gaps"]["reason"]
    assert S["context"]["status"] == D.NA and "1m" in S["context"]["reason"]
    assert S["structure"]["status"] == D.OK and S["areas"]["status"] == D.OK


def test_legs_na_without_injected_reader2(world):
    m15, fut, ltf, one, as_of, d = world
    x = _dossier(m15, fut, ltf, one, as_of, cfg={"legs_reader": None})
    assert x["sections"]["legs"]["status"] == D.NA and "research-only" in x["sections"]["legs"]["reason"]
    assert {k: v for k, v in x["sections"].items() if k != "legs"} == {k: v for k, v in d["sections"].items() if k != "legs"}


def test_owner_failure_is_na_with_reason(world, monkeypatch):
    m15, fut, ltf, one, as_of, _ = world
    from decision3 import liquidity as LQ

    def boom(*a, **k):
        raise RuntimeError("synthetic owner failure")
    monkeypatch.setattr(LQ, "pools", boom)
    d = _dossier(m15, fut, ltf, one, as_of)
    lq = d["sections"]["liquidity"]
    assert lq["status"] == D.NA and "RuntimeError" in lq["reason"] and "synthetic owner failure" in lq["reason"]
    assert all(s["status"] == D.OK for n, s in d["sections"].items() if n != "liquidity")


def test_shared_engine_failure_marks_every_dependent_section_na(world, monkeypatch):
    m15, fut, ltf, one, as_of, _ = world
    from swings2 import engine as SE

    def boom(*a, **k):
        raise ValueError("engine down")
    monkeypatch.setattr(SE, "build", boom)
    S = _dossier(m15, fut, ltf, one, as_of)["sections"]
    for name in ("structure", "liquidity", "patterns", "divergence", "areas", "lines", "confluence", "ltf_choch"):
        assert S[name]["status"] == D.NA and "swings2.engine.build failed" in S[name]["reason"], name
    for name in ("legs", "volume", "candles", "gaps", "context"):
        assert S[name]["status"] == D.OK, (name, S[name].get("reason"))
    assert S["candles"]["area_studies"] is None and "swings2.engine.build failed" in S["candles"]["area_studies_reason"]


def test_short_history_structure_is_na_not_empty_ok(world):
    m15, fut, ltf, one, as_of, _ = world
    ts = pd.to_datetime(m15["timestamp"]).dt.normalize()
    keep = ts >= ts.unique()[-5]                                              # 5 sessions: σ (20 sessions) not available
    first = pd.to_datetime(m15.loc[keep, "timestamp"]).min()
    sub = [x[pd.to_datetime(x["timestamp"]) >= first].reset_index(drop=True) for x in (m15, fut, ltf, one)]
    S = _dossier(*sub, as_of)["sections"]
    assert S["structure"]["status"] == D.NA and "σ" in S["structure"]["reason"]


def test_15m_required_and_holdout_never_swallowed(world):
    m15, fut, ltf, one, as_of, _ = world
    with pytest.raises(ValueError):
        D.build_dossier("SYNTH", {"5M": ltf}, None)
    shift = DP.HOLDOUT_START - pd.to_datetime(m15["timestamp"]).dt.normalize().iloc[0]
    hold = m15.assign(timestamp=pd.to_datetime(m15["timestamp"]) + shift, bar_end=pd.to_datetime(m15["bar_end"]) + shift)
    with pytest.raises(DP.HoldoutError):
        D.build_dossier("NIFTY", {"15M": hold}, None)


def _to_holdout(df):
    shift = DP.HOLDOUT_START - pd.to_datetime(df["timestamp"]).dt.normalize().iloc[0]
    out = df.assign(timestamp=pd.to_datetime(df["timestamp"]) + shift)
    if "bar_end" in df.columns:
        out["bar_end"] = pd.to_datetime(df["bar_end"]) + shift
    return out


def _daily(m15):
    d = m15.assign(day=pd.to_datetime(m15["timestamp"]).dt.normalize()).groupby("day").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    return d.reset_index().rename(columns={"day": "timestamp"})


def test_holdout_guard_uses_the_dossier_symbol_not_the_global_instrument(world, monkeypatch):
    import instruments as INS
    m15, *_ = world
    monkeypatch.setitem(INS._current, "name", "BANKNIFTY")                   # process-global instrument has no holdout
    with pytest.raises(DP.HoldoutError):
        D.build_dossier("NIFTY", {"15M": _to_holdout(m15)}, None)


@pytest.mark.parametrize("where", ["5M", "1m", "D", "1H", "FUT"])
def test_holdout_rows_in_any_single_input_frame_raise(world, where):
    m15, fut, ltf, one, as_of, _ = world
    bars = {"15M": m15, "5M": ltf, "1m": one, "D": _daily(m15)}
    futs = {"5M": fut}
    if where == "FUT":
        futs["5M"] = _to_holdout(fut)
    elif where == "1H":
        bars["1H"] = _to_holdout(m15.assign(bar_end=pd.to_datetime(m15["timestamp"]) + pd.Timedelta(hours=1)))
    else:
        bars[where] = _to_holdout(bars[where])
    with pytest.raises(DP.HoldoutError, match=where):
        D.build_dossier("NIFTY", bars, futs, as_of=as_of, cfg={"legs_reader": RR.read})


# ------------------------------------------------------------------------------------------------ FUT data quality
def _last_bar_rows(fut, as_of):
    t = pd.Timestamp(as_of) - pd.Timedelta(minutes=15)
    ft = pd.to_datetime(fut["timestamp"])
    return fut[(ft >= t) & (ft < as_of)]


def test_fut_roll_day_uses_near_month_only_and_order_does_not_matter(world):
    """Abhi (R1b-3): roll च्या दिवशी FUT volume = फक्त near-month; next-month rows बेरजेत येत नाहीत, row क्रम निकाल बदलत नाही."""
    m15, fut, ltf, one, as_of, d = world
    rows = _last_bar_rows(fut, as_of)
    nxt = rows.assign(volume=1000.0, expiry=rows["expiry"] + pd.Timedelta(days=28))
    two = pd.concat([fut, nxt], ignore_index=True)
    a = _dossier(m15, two, ltf, one, as_of)["sections"]["volume"]
    b = _dossier(m15, two.iloc[::-1].reset_index(drop=True), ltf, one, as_of)["sections"]["volume"]
    assert a == b                                                               # stable: row order never picks a contract
    assert a["status"] == D.OK and a["multi_contract_bars"] == []
    assert a["last_bar"]["volume"] == d["sections"]["volume"]["last_bar"]["volume"]   # next-month volume ignored
    c = _dossier(m15, two.drop(columns=["expiry"]), ltf, one, as_of)["sections"]["volume"]   # no contract info ⇒ cannot pick ⇒ sum
    assert c["last_bar"]["volume"] == d["sections"]["volume"]["last_bar"]["volume"] + 3 * 1000.0


def test_near_month_rows_keeps_expiring_contract_on_its_expiry_day():
    from opportunity_engine import volume as OV
    ts = pd.to_datetime(["2026-09-29 09:15", "2026-09-29 09:15", "2026-09-30 09:15", "2026-09-30 09:15"])
    f = pd.DataFrame({"timestamp": ts, "volume": [5.0, 1.0, 7.0, 2.0],
                      "expiry": pd.to_datetime(["2026-09-29", "2026-10-27", "2026-09-29", "2026-10-27"])})
    got = OV.near_month_rows(f)
    assert got["volume"].tolist() == [5.0, 2.0]                                   # expiry day: expiring; next day: next month
    assert OV.near_month_rows(f.drop(columns=["expiry"])) is not None and len(OV.near_month_rows(f.drop(columns=["expiry"]))) == 4


def test_fut_bar_with_missing_5m_children_is_na_with_reason(world):
    m15, fut, ltf, one, as_of, d = world
    drop = _last_bar_rows(fut, as_of).index[:1]
    v = _dossier(m15, fut.drop(index=drop), ltf, one, as_of)["sections"]["volume"]
    assert v["status"] == D.OK
    assert v["last_bar"]["volume"] is None and "incomplete FUT 5M children (2 of 3)" in v["last_bar"]["reason"]
    assert v["incomplete_bars"] == [{"ts": d["asof_bar"]["ts"], "fut_5m_children": 2, "expected": 3}]
    assert d["sections"]["volume"]["incomplete_bars"] == [] and "reason" not in d["sections"]["volume"]["last_bar"]


def test_candles_tell_fut_missing_from_attach_failure(world, monkeypatch):
    m15, fut, ltf, one, as_of, _ = world
    assert "FUT volume missing" in _dossier(m15, None, ltf, one, as_of)["sections"]["candles"]["volume_source"]
    from opportunity_engine import volume as OV

    def boom(*a, **k):
        raise KeyError("bar_start")
    monkeypatch.setattr(OV, "attach_futures_volume", boom)
    S = _dossier(m15, fut, ltf, one, as_of)["sections"]
    assert "FUT attach failed" in S["candles"]["volume_source"] and "KeyError" in S["candles"]["volume_source"]
    assert S["volume"]["status"] == D.NA and "KeyError" in S["volume"]["reason"]


# ------------------------------------------------------------------------------------------------ stale feed, empty-but-OK pieces
def test_stale_15m_feed_is_flagged_in_structure_and_candles(world):
    m15, fut, ltf, one, as_of, d = world
    late = as_of + pd.Timedelta(minutes=50)                                    # no newer bar exists in the cut frames
    x = _dossier(_cut(m15, as_of, 15), _cut(fut, as_of, 5), _cut(ltf, as_of, 5), _cut(one, as_of, 1), late)
    for sec in ("structure", "candles"):
        assert x["sections"][sec]["stale_by_minutes"] == 50 and "stale" in x["sections"][sec]["stale_reason"], sec
        assert "stale_by_minutes" not in d["sections"][sec]
    assert x["asof_bar"]["stale_by_minutes"] == 50 and "stale_by_minutes" not in d["asof_bar"]


def test_context_missing_parts_carry_a_reason(world):
    m15, fut, ltf, one, as_of, _ = world
    today = pd.to_datetime(one["timestamp"]).dt.normalize() == pd.Timestamp(as_of).normalize()
    c = _dossier(m15, fut, ltf, one[today].reset_index(drop=True), as_of)["sections"]["context"]
    assert c["status"] == D.OK and c["opening"] is not None
    assert c["prev_day"] is None and c["missing"]["prev_day"] and c["prev_week"] is None and c["missing"]["prev_week"]
    assert "opening" not in c["missing"]


@pytest.fixture(scope="module")
def visit_world():
    """The 12-Oct reference shape at the 09:30 bar's close (k = 1): the bear-call visit to the supply area, and its price mirror."""
    out = {}
    for mirror in (False, True):
        m15, fut, ltf, one = _inputs(mirror=mirror)
        as_of = _asof(m15, 1)
        out[mirror] = (m15, fut, ltf, one, as_of, _dossier(m15, fut, ltf, one, as_of))
    return out


def test_visit_study_is_the_decisions_own_read(visit_world):
    """Layer 6b: the Vision facts read the SAME method as the decision — the visit by structure (V22.visit), its approach leg, the
    handover episode, the commitment (approach leg + opposite side, push excluded) and the LTF change of character (V22._confirm)."""
    from decision3 import engine as E3
    m15, fut, ltf, one, as_of, d = visit_world[False]
    S = d["sections"]
    st = S["candles"]["area_studies"]
    assert len(st) == 1
    x = st[0]
    assert x["role"] == V.RES and x["reaction_side"] == "down" and x["armed"] and x["approach_from"] is not None
    assert x["commitment"]["present"] and x["handover"]["present"] and "grade" not in x["commitment"]["reason"]
    lt = S["ltf_choch"]["visits"]
    assert len(lt) == 1 and lt[0]["done"] and lt[0]["area_id"] == x["area_id"] and lt[0]["study_from"] == x["arrival"]["ts"]
    cut = _cut(m15, as_of, 15)                                                 # the engine itself on the same bars
    Ve = E3.V22(cut[["timestamp", "bar_end", "open", "high", "low", "close"]], None, None, ltf=_cut(ltf, as_of, 5),
                futures=_cut(fut, as_of, 5))
    r = Ve.decide(len(Ve.m15) - 1)
    assert r["decision"] == "setup" and r["level"]["id"] == x["area_id"]
    assert r["commit"]["visit_start"] == x["arrival"]["ts"] and r["commit"]["approach_from"] == x["approach_from"]
    assert r["commit"]["commit_present"] and r["commit"]["choch"]["done"]


def test_visit_mirror_holds(visit_world):
    a, b = visit_world[False][-1]["sections"], visit_world[True][-1]["sections"]
    sa, sb = a["candles"]["area_studies"], b["candles"]["area_studies"]
    assert len(sa) == len(sb) == 1 and sb[0]["role"] == V.SUP and sb[0]["reaction_side"] == "up"
    for k in ("arrival", "approach_from", "bars_in_study"):
        assert sa[0][k] == sb[0][k], k
    assert sa[0]["commitment"]["present"] == sb[0]["commitment"]["present"] and \
        sa[0]["handover"]["present"] == sb[0]["handover"]["present"]
    assert a["ltf_choch"]["visits"][0]["done"] == b["ltf_choch"]["visits"][0]["done"]


def test_visit_is_by_structure_never_a_bar_count(visit_world):
    """The old `touch_window_bars` count is gone from the facts: changing it changes nothing (the visit ends only by structure)."""
    m15, fut, ltf, one, as_of, d = visit_world[False]
    x = _dossier(m15, fut, ltf, one, as_of, cfg={"decision3": {"touch_window_bars": 1}})
    assert x["sections"]["candles"]["area_studies"] == d["sections"]["candles"]["area_studies"]
    src = open(os.path.join(ROOT, "facts", "dossier.py"), encoding="utf-8").read()
    assert "touch_window_bars" not in src and "RE.RSI(" not in src                # layer 6b: no bar window, no old Cardwell RSI


def test_divergence_is_the_method_read_at_the_visit(visit_world):
    """Layer 5 at the visit: the pushes inside the move into the zone (highest degree with two pushes), the zone's own degree too."""
    *_, d = visit_world[False]
    dv = d["sections"]["divergence"]
    assert dv["status"] == D.OK and len(dv["at_visits"]) == 1
    v = dv["at_visits"][0]
    assert v["zone_side"] == "bear" and "pushes" in v and "zone_degree" in v and v["found"] in (True, False)
    assert dv["latest"] and all(isinstance(x, str) for x in dv["latest"])


def test_validity_display_finder_kept_as_the_legacy_switch(world):
    m15, fut, ltf, one, as_of, d = world
    x = _dossier(m15, fut, ltf, one, as_of, cfg={"display_finder": "validity"})
    S = x["sections"]
    for tf in ("15M", "1H"):
        for b in S["areas"]["by_tf"][tf]["bands"]:
            assert b["hi"] > b["lo"] and "touches" in b and "reasons" in b
        for ln in S["lines"]["by_tf"][tf]["lines"]:
            assert ln["valid"] and ln["projected_zone"]["next"] is not None
    assert {k: v for k, v in S.items() if k not in ("areas", "lines", "confluence")} == \
        {k: v for k, v in d["sections"].items() if k not in ("areas", "lines", "confluence")}
    with pytest.raises(ValueError, match="display_finder"):
        _dossier(m15, fut, ltf, one, as_of, cfg={"display_finder": "sigma"})


def test_json_helper_maps_nat_and_na_to_none():
    assert D._j({"a": pd.NaT, "b": pd.NA, "c": [pd.NaT, 1.5], "d": float("nan")}) == {"a": None, "b": None, "c": [None, 1.5], "d": None}


def test_daily_frame_path_closed_days_only_and_used_by_gaps(world):
    m15, fut, ltf, one, as_of, d = world
    daily = _daily(m15)                                                         # includes the as_of day (closes after as_of)
    bars = {"15M": m15, "5M": ltf, "1m": one}
    x = D.build_dossier("SYNTH", {**bars, "D": daily}, {"5M": fut}, as_of=as_of, cfg={"legs_reader": RR.read})
    info = x["inputs"]["D"]
    assert info != "missing" and pd.Timestamp(info["last_close_at"]) <= as_of
    assert pd.Timestamp(info["to"]) < pd.Timestamp(as_of).normalize()
    assert x["sections"]["gaps"]["status"] == D.OK and x["sections"]["gaps"]["trend_source"] == "daily"
    assert d["sections"]["gaps"]["trend_source"] == "1m"
    cut = D.build_dossier("SYNTH", {**bars, "D": daily.iloc[:-1]}, {"5M": fut}, as_of=as_of, cfg={"legs_reader": RR.read})
    assert cut == x                                                             # the running day's daily bar is never read


def test_1h_bars_are_complete_nse_hours_only(world):
    m15, fut, ltf, one, as_of, d = world
    assert pd.Timestamp(d["inputs"]["1H"]["last_close_at"]) <= as_of
    h = D._hours_from_15m(_cut(m15, as_of, 15))
    hm = pd.to_datetime(h["timestamp"]).dt.strftime("%H:%M")
    assert set(hm) <= {"09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"} and "15:15" in set(hm)
    assert pd.Timestamp(h[hm == "15:15"]["bar_end"].iloc[-1]).strftime("%H:%M") == "15:30"
    assert pd.Timestamp(h["bar_end"].iloc[-1]) <= as_of                         # the running 09:15 hour of the as_of day is not a bar


TRANSITIVE_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
from tests import oct12_fixture as F
from tests.ltf_fixtures import split_bars
from facts import dossier as D
m15, fut, ltf = F.build()
D.build_dossier("SYNTH", {{"15M": m15, "5M": ltf, "1m": split_bars(m15, 15, 15)}}, {{"5M": fut}})
print(" ".join(sorted(sys.modules)))
"""


def test_dossier_run_loads_no_frozen_decision_engine():
    """Transitive check (fresh interpreter, full dossier run): decision2, simple_core, mtf, reader2 and the frozen decision paths are
    never loaded, and facts' own code imports no chart module. Known owner chain (not facts' code; open question R1b-7): the swings2 /
    rsi2 σ_1H helpers import pivots.charts ⇒ backtest_review.charts ⇒ vision_led.charts (plotting helpers only) — any OTHER vision_led
    module fails this test."""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", TRANSITIVE_SCRIPT.format(root=ROOT)], capture_output=True, text=True, cwd=ROOT,
                         timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    mods = set(out.stdout.split())
    assert "facts.dossier" in mods
    banned = ("decision2", "simple_core", "mtf", "reader2", "opportunity_engine.detectors", "opportunity_engine.bias",
              "opportunity_engine.gate", "opportunity_engine.scoring", "opportunity_engine.selector", "opportunity_engine.engine",
              "chart_reader.grade", "chart_reader.rules", "chart_reader.risk", "chart_reader.evaluate", "chart_reader.narrative",
              "chart_reader.checklist")
    assert not [m for m in mods if any(m == b or m.startswith(b + ".") for b in banned)]
    assert {m for m in mods if m.split(".")[0] == "vision_led"} <= {"vision_led", "vision_led.charts"}
    tree = ast.parse(open(os.path.join(ROOT, "facts", "dossier.py"), encoding="utf-8").read())
    own = {f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module for a in n.names}
    assert not [m for m in own if m.endswith(".charts") or m.endswith(".chart")]


# ------------------------------------------------------------------------------------------------ 12-Oct reference fixture: golden shape
def test_oct12_fixture_golden_shape_bear_and_mirror(world):
    """Shape only (no invented values): the bear case and its price mirror (tests/oct12_fixture.py, `mirror=True` = the same case for a
    bull put) give the same sections, the mirrored swing trend, the mirrored candle facts and identical FUT volume facts."""
    m15, fut, ltf, one, as_of, d = world
    mm15, mfut, mltf, mone = _inputs(mirror=True)
    m = _dossier(mm15, mfut, mltf, mone, _asof(mm15))
    assert {k: v["status"] for k, v in m["sections"].items()} == {k: v["status"] for k, v in d["sections"].items()}
    flip = {"UP": "DOWN", "DOWN": "UP", "RANGE": "RANGE", "unknown": "unknown"}
    for deg in ("D1", "D2"):
        assert m["sections"]["structure"]["degrees"][deg]["state"]["trend"] == \
            flip[d["sections"]["structure"]["degrees"][deg]["state"]["trend"]]
    a, b = d["sections"]["candles"]["reversal_form_at_last_bar"], m["sections"]["candles"]["reversal_form_at_last_bar"]
    assert a["up"] == b["down"] and a["down"] == b["up"]
    assert m["sections"]["volume"]["last_bar"] == d["sections"]["volume"]["last_bar"]
    assert m["sections"]["volume"]["session"]["up_bars"] == d["sections"]["volume"]["session"]["down_bars"]
    pd_bear, pd_bull = d["sections"]["context"]["prev_day"], m["sections"]["context"]["prev_day"]
    assert abs((pd_bear["high"] + pd_bull["low"]) / 2 - F.MID) < 1e-3                    # mirror p ⇒ 2·MID − p


# ------------------------------------------------------------------------------------------------ module boundary
def test_dossier_imports_no_frozen_engine_ai_or_broker_and_no_dates():
    path = os.path.join(ROOT, "facts", "dossier.py")
    src = open(path, encoding="utf-8").read()
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods |= {node.module} | {f"{node.module}.{a.name}" for a in node.names}
    frozen = ("decision2", "simple_core", "mtf", "vision_led", "chart_reader", "opportunity_engine.detectors", "opportunity_engine.bias",
              "opportunity_engine.gate", "opportunity_engine.scoring", "opportunity_engine.selector", "opportunity_engine.engine")
    ai_broker = ("anthropic", "openai", "requests", "upstox", "fyers", "shoonya", "stocko", "broker", "notifications", "order_execution")
    for m in mods:
        assert not any(m == f or m.startswith(f + ".") for f in frozen), m
        assert not any(x in m.lower() for x in ai_broker), m
    assert not [ln for ln in src.splitlines() if any(rx.search(ln) for rx in DATE_RX_I)]


# ------------------------------------------------------------------------------------------------ real data (R1a fixture; private, skip in CI)
@G.need_data
def test_golden_dossier_nifty_fut_9oct_close_carries_the_r1a_line_band_and_confluence():
    """The dossier at the 9 Oct close (the full FUT 15M frame incl. 12 Oct is passed; the dossier cuts it) carries the R1a golden line
    with the same projected 3rd-touch zone as R1a's truncated check, the R1a ≈22,667 supply band and their confluence."""
    fut15 = G.load_fut15()
    t, cut, ref, _ = G._golden(fut15, "2026-10-09")
    as_of = pd.Timestamp(cut["timestamp"].iloc[-1]) + pd.Timedelta(minutes=15)
    d = D.build_dossier("NIFTY", {"15M": fut15}, None, as_of=as_of, cfg={"legs_reader": RR.read, "display_finder": "validity"})   # R1a finder
    S = d["sections"]
    lines = [x for x in S["lines"]["by_tf"]["15M"]["lines"] if V.same_line(x, ref, ref["mr"], V.DEFAULTS["touch_mr"])]
    assert lines and lines[0]["projected_zone"]["next"] == ref["projected_zone"]["next"]
    near = G._band_near(S["areas"]["by_tf"]["15M"]["bands"], 22667.0, S["areas"]["by_tf"]["15M"]["mr"])
    assert near
    conf = [c for c in S["confluence"]["items"] if c["band_tf"] == "15M" and c["line_tf"] == "15M" and c["band"] == [near[0]["lo"], near[0]["hi"]]
            and [p["ts"] for p in c["line_anchors"]] == [lines[0]["anchor1"]["ts"], lines[0]["anchor2"]["ts"]]]
    assert conf
    assert S["volume"]["status"] == D.NA                                       # no FUT 5M passed ⇒ NA, never a guess
    json.dumps(d, allow_nan=False)
