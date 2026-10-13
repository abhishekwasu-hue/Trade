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
    for tf in ("15M", "1H"):
        for b in S["areas"]["by_tf"][tf]["bands"]:
            assert b["hi"] > b["lo"] and "touches" in b and "reasons" in b
        for ln in S["lines"]["by_tf"][tf]["lines"]:
            assert ln["valid"] and ln["projected_zone"]["next"] is not None
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
    for name in ("structure", "liquidity", "patterns", "divergence"):
        assert S[name]["status"] == D.NA and "swings2.engine.build failed" in S[name]["reason"], name
    for name in ("areas", "lines", "confluence", "legs", "volume", "candles", "gaps", "context"):
        assert S[name]["status"] == D.OK, (name, S[name].get("reason"))


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
    d = D.build_dossier("NIFTY", {"15M": fut15}, None, as_of=as_of, cfg={"legs_reader": RR.read})
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
