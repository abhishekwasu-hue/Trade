"""tests/test_opportunity_engine_visual.py -- PR-V: render, auditor (fake client), consensus, scoring mode, store (mocked conn), evaluate, jobs/backfill (fake batches),
backtest consensus modes, EOD/backfill scripts. Network-free — एकही खरा API call नाही."""
import json
import os
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import run_visual_audit as RVA
import run_visual_backfill as RVB
from opportunity_engine import backtest as BT
from opportunity_engine import refresh as RF
from opportunity_engine import scoring as SC
from opportunity_engine import sessions
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import TFState
from opportunity_engine.detectors.base import Candidate
from opportunity_engine.visual_audit import auditor as A
from opportunity_engine.visual_audit import backfill as BF
from opportunity_engine.visual_audit import compare as CMP
from opportunity_engine.visual_audit import consensus as C
from opportunity_engine.visual_audit import evaluate as EV
from opportunity_engine.visual_audit import jobs as J
from opportunity_engine.visual_audit import render as R
from opportunity_engine.visual_audit import store as VS
from tests.test_opportunity_engine_backtest import ScriptedDetector, long_cand, walk_1m
from tests.test_opportunity_engine_store import FakeConn, factory

VCFG = A.VisualAuditConfig(model="test-vision-model", max_tokens=2000)


def lvl(lid, kind, low, high, tf="1h", grade="A", score=0.8, **kw):
    return {"level_id": lid, "kind": kind, "tf": tf, "low": low, "high": high, "core_low": low + 2, "core_high": high - 2, "outer_low": low, "outer_high": high,
            "quality_grade": grade, "quality_score": score, "status": "ACTIVE", "reject_reason": None, "quality_components": {"clean": 1.0, "origin": 0.5}, **kw}


LEVELS = [lvl("a1", "DEMAND", 100, 110), lvl("b2", "SUPPLY", 150, 160, grade="B", score=0.6), lvl("c3", "SUPPORT", 120, 125, grade="C", score=0.35),
          lvl("k1", "KEY", 140, 140, source="PDH"), lvl("old", "RESISTANCE", 170, 175, tf="1d")]
POOL = [lvl("p1", "SUPPORT", 128, 132, grade="REJECT", score=0.2), lvl("p2", "DEMAND", 112, 116, grade="REJECT", score=0.2)]


# ---- render -----------------------------------------------------------------------------------------------------------------------------------
def frame(n=40, start="2025-01-06 09:15", freq="60min", base=130.0):
    t = pd.date_range(start, periods=n, freq=freq)
    c = base + np.sin(np.arange(n) / 3.0) * 20
    return pd.DataFrame({"bar_start": t, "bar_end": t + pd.Timedelta(freq), "open": c - 1, "high": c + 3, "low": c - 3, "close": c, "bar_closed": True})


def test_assign_labels_filters_tf_kind_range_and_orders_top_down():
    labs = R.assign_labels(LEVELS + [lvl("br", "DEMAND", 90, 95, status="BROKEN")], "1h", lo=95.0, hi=165.0)
    assert [l["level_id"] for l in labs] == ["b2", "c3", "a1"] and [l["label"] for l in labs] == ["L1", "L2", "L3"]       # KEY, 1d, BROKEN वगळले
    assert labs[0]["outer_high"] == 160 and labs[2]["grade"] == "A"
    assert R.assign_labels(LEVELS, "1h", lo=300.0, hi=400.0) == []
    many = [lvl(f"z{i}", "DEMAND", 100 + i, 101 + i, score=i / 100) for i in range(20)]
    assert len(R.assign_labels(many, "1h", max_levels=5)) == 5


def test_build_figure_and_png_are_graceful():
    df = frame()
    labs = R.assign_labels(LEVELS, "1h", float(df["low"].min()), float(df["high"].max()))
    sw = [SimpleNamespace(time=df["bar_end"].iloc[5], price=float(df["high"].iloc[5]), label="HH", kind="H")]
    fig = R.build_figure(df, "1h", "NIFTY", labs, sw, overlay=True)
    texts = [a.text for a in fig.layout.annotations]
    assert any("L1" in t for t in texts) and "HH" in texts and len(fig.layout.shapes) == 2 * len(labs)
    plain = R.build_figure(df, "1h", "NIFTY", labs, sw, overlay=False)
    assert len(plain.layout.shapes) == 0 and len(plain.layout.annotations) == 0
    png = R.render_png(df, "1h", "NIFTY", labs, sw)
    assert png is None or png[:4] == b"\x89PNG"                                  # kaleido/Chrome नसेल तर None (CI)
    assert R.render_png(df.head(2), "1h", "NIFTY") is None


# ---- auditor --------------------------------------------------------------------------------------------------------------------------------
class Msg(SimpleNamespace):
    pass


def msg(payload, stop="end_turn", tin=1000, tout=300):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return Msg(stop_reason=stop, content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
               usage=SimpleNamespace(input_tokens=tin, output_tokens=tout), model="test-vision-model")


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(create=self._create, count_tokens=lambda **kw: SimpleNamespace(input_tokens=1234), batches=None)

    def _create(self, **params):
        self.calls.append(params)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


LABS = [{"label": "L1", "level_id": "b2", "kind": "SUPPLY"}, {"label": "L2", "level_id": "c3", "kind": "SUPPORT"}, {"label": "L3", "level_id": "a1", "kind": "DEMAND"}]
GOOD = {"verdicts": [{"label": "L1", "verdict": "VALID", "reason": "खरा sell-off"}, {"label": "L2", "verdict": "SPURIOUS", "reason": "एकच spike"},
                     {"label": "L3", "verdict": "SHIFT_UP", "reason": "थोडं वर"}],
        "missing": [{"approx_low": 127, "approx_high": 131, "kind": "SUPPORT", "reason": "दोनदा उसळी"}, {"approx_low": 99999, "approx_high": 99990, "kind": "DEMAND", "reason": "x"}],
        "trend_state": "UPTREND", "agrees_with_engine_state": True}
INDEP = {"zones": [{"approx_low": 152, "approx_high": 158, "kind": "SUPPLY", "reason": "वरचा अडथळा"}, {"approx_low": 113, "approx_high": 115, "kind": "DEMAND", "reason": "base"}],
         "trend_state": "UPTREND"}


def test_build_request_needs_model_and_carries_schema_effort_and_fewshot():
    with pytest.raises(ValueError):
        A.build_request(A.VisualAuditConfig(), "overlay", b"x", "NIFTY", "1h", LABS)
    p = A.build_request(VCFG, "overlay", b"png", "NIFTY", "1h", LABS, "UPTREND")
    assert p["model"] == "test-vision-model" and p["output_config"]["format"]["schema"] is A.OVERLAY_SCHEMA and "effort" not in p["output_config"]
    assert "temperature" not in p and p["messages"][-1]["content"][0]["type"] == "image" and "L1" in p["messages"][-1]["content"][1]["text"]
    ex = [{"image_b64": "aaa", "prompt": "p", "answer": GOOD}] * 3
    p2 = A.build_request(replace(VCFG, effort="low", fewshot=2), "independent", b"png", "NIFTY", "1d", fewshot=ex)
    assert p2["output_config"]["effort"] == "low" and p2["output_config"]["format"]["schema"] is A.INDEPENDENT_SCHEMA
    assert [m["role"] for m in p2["messages"]] == ["user", "assistant", "user", "assistant", "user"]


def test_validate_and_parse_message_paths():
    data, err = A.validate("overlay", json.loads(json.dumps(GOOD)), LABS, 90.0, 170.0)
    assert err is None and [v["label"] for v in data["verdicts"]] == ["L1", "L2", "L3"] and len(data["missing"]) == 1        # दूरचा पट्टा वगळला
    bad = {**GOOD, "verdicts": GOOD["verdicts"][:2]}
    assert A.validate("overlay", bad, LABS)[1].startswith("verdict नाही")
    swapped = A.validate("independent", {"zones": [{"approx_low": 160, "approx_high": 150, "kind": "SUPPLY", "reason": ""}], "trend_state": "RANGE"})[0]
    assert swapped["zones"][0]["approx_low"] == 150
    assert A.validate("independent", {"zones": [], "trend_state": "SIDEWAYS"})[1] == "trend_state अवैध"
    assert A.parse_message(msg(GOOD, stop="refusal"), "overlay", LABS)[1].startswith("model ने नकार")
    assert A.parse_message(msg(GOOD, stop="max_tokens"), "overlay", LABS)[1].startswith("max_tokens")
    assert A.parse_message(msg("not json"), "overlay", LABS)[1].startswith("JSON parse")
    d, e, tin, tout = A.parse_message(msg(GOOD), "overlay", LABS)
    assert e is None and tin == 1000 and tout == 300


def test_call_retries_once_then_fails_and_sums_usage():
    ok = A.call(FakeClient([msg("{}"), msg(GOOD)]), {"x": 1}, "overlay", LABS, retries=1)
    assert ok.status == "OK" and ok.attempts == 2 and ok.input_tokens == 2000
    bad = A.call(FakeClient([msg("{}"), msg("{}")]), {"x": 1}, "overlay", LABS, retries=1)
    assert bad.status == "FAILED" and bad.attempts == 2 and "trend_state" in bad.error
    err = A.call(FakeClient([RuntimeError("down"), RuntimeError("down")]), {}, "overlay", LABS, retries=1)
    assert err.status == "FAILED" and err.error.startswith("API चूक")


def test_snap_band_and_agreement_and_audit_chart():
    assert A.snap_band(127, 131, POOL)["level_id"] == "p1" and A.snap_band(200, 210, POOL) is None
    assert A.snap_band(127, 131, POOL, exclude_ids={"p1"}) is None
    assert A.agreement(GOOD, GOOD) == 100.0 and A.agreement(GOOD, None) is None
    other = {**GOOD, "verdicts": [{**GOOD["verdicts"][0], "verdict": "SPURIOUS"}] + GOOD["verdicts"][1:]}
    assert A.agreement(GOOD, other) == pytest.approx(66.7)
    client = FakeClient([msg(GOOD), msg(other), msg(INDEP)])
    rec = A.audit_chart(client, replace(VCFG, repeat=2), "NIFTY", "1h", "2025-01-07", b"png", b"png", LABS, POOL, "UPTREND", 90.0, 170.0)
    assert rec["overlay"]["status"] == "OK" and rec["independent"]["status"] == "OK" and rec["agreement_pct"] == pytest.approx(66.7)
    assert rec["usage"]["calls"] == 3 and rec["usage"]["input_tokens"] == 3000
    assert rec["suggestions"][0]["snapped_level_id"] == "p1" and json.dumps(rec, default=str)
    skipped = A.audit_chart(FakeClient([msg(INDEP)]), VCFG, "NIFTY", "1d", "2025-01-07", b"png", b"png", [], POOL)
    assert skipped["overlay"]["status"] == "SKIPPED" and skipped["independent"]["status"] == "OK"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("VISUAL_AUDIT_MODEL", "m-x")
    monkeypatch.setenv("VISUAL_AUDIT_REPEAT", "2")
    monkeypatch.delenv("VISUAL_AUDIT_EFFORT", raising=False)
    c = A.VisualAuditConfig.from_env()
    assert c.model == "m-x" and c.repeat == 2 and c.effort is None and c.fewshot == 0


# ---- consensus -------------------------------------------------------------------------------------------------------------------------------
def record(overlay=GOOD, indep=INDEP, labels=None, tf="1h", status="OK"):
    labels = labels or [{**l, "outer_low": next(z for z in LEVELS if z["level_id"] == l["level_id"])["outer_low"],
                         "outer_high": next(z for z in LEVELS if z["level_id"] == l["level_id"])["outer_high"]} for l in LABS]
    return {"audit_date": "2025-01-07", "symbol": "NIFTY", "tf": tf, "labels": labels, "overlay": {"status": status, "data": overlay},
            "independent": {"status": status, "data": indep}}


def test_classify_all_classes():
    res = C.classify(LEVELS, POOL, [record()])
    cls = {k: v["class"] for k, v in res["classes"].items()}
    assert cls["b2"] == C.CONSENSUS                          # B + VALID (+ स्वतंत्र पट्टा छेदतो)
    assert cls["c3"] == C.MATH_ONLY                          # SPURIOUS
    assert cls["a1"] == C.CONFLICT                           # SHIFT_UP ⇒ वरचा p2 (112–116) CONSENSUS उमेदवार म्हणून जोडला
    added = {z["level_id"]: z["consensus"] for z in res["added"]}
    assert added == {"p2": C.CONSENSUS}
    vis = {r["matched_level_id"]: r["consensus_class"] for r in res["visual_rows"]}
    assert vis["b2"] == C.CONSENSUS and "p2" in vis
    c_valid = {**GOOD, "verdicts": [{**v, "verdict": "VALID"} for v in GOOD["verdicts"]]}
    res2 = C.classify(LEVELS, POOL, [record(overlay=c_valid, indep={"zones": [], "trend_state": "UPTREND"})])
    assert res2["classes"]["c3"]["class"] == C.MATH_ONLY and res2["classes"]["a1"]["class"] == C.CONSENSUS     # grade C VALID ⇒ CONSENSUS नाही (spec: A/B)
    only_ind = C.classify(LEVELS, POOL, [record(status="FAILED")])
    assert only_ind["classes"] == {} and only_ind["added"] == []
    fb = C.classify(LEVELS, POOL, [record()], feedback={"b2": "WRONG", "c3": "CORRECT"})
    assert fb["classes"]["b2"]["class"] == C.REJECT and fb["classes"]["c3"]["class"] == C.CONSENSUS


def test_apply_modes_off_score_gate_and_fallback():
    recs = [record()]
    off, info = C.apply(LEVELS, POOL, recs, "off")
    assert off is LEVELS and info["mode"] == "off"
    score, si = C.apply(LEVELS, POOL, recs, "score")
    tags = {z["level_id"]: z.get("consensus") for z in score}
    assert tags["b2"] == C.CONSENSUS and tags["c3"] == C.MATH_ONLY and tags["a1"] == C.MATH_ONLY and tags["k1"] is None and tags["p2"] == C.CONSENSUS
    assert si["counts"]["ADDED"] == 1
    gate, gi = C.apply(LEVELS, POOL, recs, "gate")
    ids = {z["level_id"] for z in gate}
    assert ids == {"b2", "k1", "p2"} and not gi["fallback"]                     # KEY राहतो; 1d 'old' audit झाला नाही ⇒ gate मध्ये गेला
    fb_gate, fi = C.apply(LEVELS, POOL, [], "gate")
    assert fb_gate is LEVELS and fi["fallback"] and fi["mode_used"] == "score"
    rej, _ = C.apply(LEVELS, POOL, recs, "score", feedback={"a1": "WRONG"})
    assert "a1" not in {z["level_id"] for z in rej}


def test_summary_text():
    res = C.classify(LEVELS, POOL, [record()])
    txt = C.summary_text("NIFTY", record(), res["classes"])
    assert txt.startswith("NIFTY 1H: 3 levels → 1 VALID, 1 SPURIOUS (L2: एकच spike), 1 SHIFT.") and "missing भाग" in txt and "CONSENSUS: 1" in txt
    assert "FAILED" in C.summary_text("NIFTY", {"tf": "1d", "overlay": {"status": "FAILED", "error": "x"}}, {})


def test_location_score_consensus_only_in_score_mode():
    cfg = EngineConfig()
    z = lvl("b2", "SUPPLY", 150, 160, grade="B", freshness="FRESH", mtf_count=1)
    cand = Candidate(setup_id="D6", direction="SHORT", time=pd.Timestamp("2025-01-07 10:00"), entry=150, sl_ref=161, zone={**z, "consensus": "CONSENSUS"})
    base = SC.location_score(cand, cfg)[0]
    assert base == SC.location_score(cand)[0] == 7.0 + 6.0
    score_cfg = replace(cfg, consensus_mode="score")
    assert SC.location_score(cand, score_cfg)[0] == 23.0
    cand.zone["consensus"] = "MATH_ONLY"
    assert SC.location_score(cand, score_cfg)[0] == 3.0
    cand.zone = {**z, "consensus": "MATH_ONLY", "quality_grade": "C", "freshness": "TESTED_2+"}
    assert SC.location_score(cand, score_cfg)[0] == 0.0                          # 0..25 मध्येच


# ---- store / jsonl ---------------------------------------------------------------------------------------------------------------------------
def test_store_save_record_merge_safe_python_values_and_feedback():
    conn = FakeConn()
    rec = {**record(), "run_id": "r1", "model": "m", "usage": {"input_tokens": np.int64(5), "output_tokens": 3, "calls": 2},
           "suggestions": [{"approx_low": np.float64(127.0), "approx_high": 131.0, "kind": "SUPPORT", "reason": "x", "snapped_level_id": "p1"}]}
    res = C.classify(LEVELS, POOL, [rec])
    assert VS.save_record(rec, {z["level_id"]: z for z in LEVELS}, res["classes"], res["visual_rows"], conn_factory=factory(conn))
    sql = [s for s, _ in conn.executed]
    assert sum("INSERT INTO level_audit " in s for s in sql) == 3 and any("DELETE FROM level_audit_suggestions" in s for s in sql)
    assert any("DELETE FROM visual_levels" in s for s in sql) and any("ON CONFLICT (audit_date, symbol, tf, level_id)" in s for s in sql)
    for _, params in conn.executed:
        for v in params or ():
            assert not isinstance(v, (np.generic,))
    assert conn.committed
    c2 = FakeConn()
    assert VS.save_feedback("b2", "NIFTY", "1h", "WRONG", "spike", conn_factory=factory(c2)) and "INSERT INTO level_feedback" in c2.executed[0][0]
    assert VS.save_feedback("b2", "NIFTY", "1h", "MAYBE", conn_factory=factory(c2)) is False
    rows = [("b2", "NIFTY", "1h", "WRONG", None, pd.Timestamp("2025-01-07")), ("b2", "NIFTY", "1h", "CORRECT", None, pd.Timestamp("2025-01-08"))]
    fb, df = VS.load_feedback("NIFTY", conn_factory=factory(FakeConn(rows=rows)))
    assert fb == {"b2": "CORRECT"} and len(df) == 2
    assert VS.ensure_tables(factory(FakeConn())) is True


def test_jsonl_roundtrip_latest_wins_and_skips_broken_lines(tmp_path):
    p = str(tmp_path / "c.jsonl")
    VS.append_jsonl(p, {"audit_date": "2025-01-07", "symbol": "NIFTY", "tf": "1h", "v": 1})
    VS.append_jsonl(p, {"audit_date": "2025-01-07", "symbol": "NIFTY", "tf": "1h", "v": 2})
    with open(p, "a") as fh:
        fh.write('{"broken": \n')
    VS.append_jsonl(p, {"audit_date": "2025-01-08", "symbol": "NIFTY", "tf": "1d", "v": 3})
    recs = VS.read_jsonl(p)
    assert sorted(r["v"] for r in recs) == [2, 3] and VS.read_jsonl(str(tmp_path / "none.jsonl")) == []
    assert set(VS.records_by_date(recs)) == {pd.Timestamp("2025-01-07"), pd.Timestamp("2025-01-08")}


# ---- evaluate --------------------------------------------------------------------------------------------------------------------------------
def test_level_reaction_touch_hold_and_tables():
    bars = frame(60, start="2025-01-07 09:15")
    lo, hi = float(bars["low"].min()), float(bars["low"].min()) + 4
    row = {"audit_date": "2025-01-07", "zone_low": lo, "zone_high": hi, "kind": "DEMAND"}
    r = EV.level_reaction(row, bars, adr=50.0)
    assert r["touched"] and r["reaction_pts"] > 0 and r["reaction_adr"] == pytest.approx(r["reaction_pts"] / 50.0) and r["held"] in (True, False)
    far = EV.level_reaction({**row, "zone_low": 1000, "zone_high": 1010}, bars)
    assert far["touched"] is False
    audit = pd.DataFrame([{**row, "model_verdict": "VALID", "level_id": "x", "engine_grade": "A"},
                          {**row, "zone_low": 1000, "zone_high": 1010, "model_verdict": "SPURIOUS", "level_id": "y", "engine_grade": "B"}])
    rx = EV.reactions(audit, bars, adr_lookup=lambda d: 50.0)
    t = EV.reaction_table(rx).set_index("model_verdict")
    assert t.loc["VALID", "स्पर्श_%"] == 100.0 and t.loc["SPURIOUS", "स्पर्श_%"] == 0.0
    m = EV.agreement_matrix(audit, {"x": "WRONG"})
    assert m["grade_vs_model"].loc["A", "VALID"] == 1 and m["model_vs_user"].loc["VALID", "WRONG"] == 1
    trades = pd.DataFrame({"zone_id": ["x", "y", None], "r": [1.0, -1.0, 0.5]})
    tb = EV.trades_by_class(trades, audit.assign(consensus_class=["CONSENSUS", "MATH_ONLY"])).set_index("consensus_class")
    assert tb.loc["CONSENSUS", "trades"] == 1 and tb.loc["MATH_ONLY", "expectancy_r"] == -1.0
    ok, text = EV.readiness(audit)
    assert not ok and "200+" in text
    tr = EV.tuning_report([{**record(), "components": {"c3": {"clean": 0.0, "origin": 0.2}, "b2": {"clean": 1.0, "origin": 0.8}}}], {"c3": "WRONG"})
    assert "दोघांनी SPURIOUS/WRONG" in tr.index and "VALID" in tr.index


# ---- jobs / estimate ---------------------------------------------------------------------------------------------------------------------------
def test_estimate_and_as_of_no_lookahead():
    e = J.estimate(10, price_in=4, price_out=20, out_tokens=1000)
    assert e["calls"] == 20 and e["output_tokens"] == 20000 and e["cost_usd"] == pytest.approx(round(e["input_tokens"] / 1e6 * 4 + 20000 / 1e6 * 20, 2))
    eb = J.estimate(10, 4, 20, 1000, batch=True)
    assert eb["cost_usd"] == pytest.approx(round(e["cost_usd"] / 2, 2), abs=0.011) and J.estimate(1)["cost_usd"] is None
    assert 1100 < J.image_tokens() < 1250
    df = frame(30)
    cut = df["bar_end"].iloc[9]
    assert J.as_of(df, cut)["bar_end"].max() == cut and len(J.as_of(df, cut)) == 10
    tr = SimpleNamespace(swings=[SimpleNamespace(confirmed_time=cut, time=cut), SimpleNamespace(confirmed_time=cut + pd.Timedelta("1h"), time=cut)])
    assert len(J.swings_asof(SimpleNamespace(trackers={"1h": tr}), "1h", cut)) == 1
    assert J.exact_input_tokens(FakeClient([]), {"model": "m", "system": "s", "messages": []}) == 1234


# ---- backtest / backfill / compare ---------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tl_bundle():
    frames = sessions.build_frames(walk_1m(days=60, seed=6))
    bcfg = BT.BacktestConfig(variants=("V1",))
    tl = BT.prepare_timeline(frames, bcfg)
    return frames, tl, bcfg


def test_timeline_keeps_pool_and_journal(tl_bundle):
    frames, tl, bcfg = tl_bundle
    assert tl.journal is not None and any(d.levels for d in tl.days)
    for d in tl.days:
        assert all(z.get("status") != "BROKEN" and z["kind"] in R.ZONE_KINDS for z in d.pool)


def synth_records(tl, days):
    recs = {}
    for d in days:
        labs = R.assign_labels(d.levels, "1h")
        if not labs:
            continue
        ov = {"verdicts": [{"label": l["label"], "verdict": "VALID" if i % 2 == 0 else "SPURIOUS", "reason": "-"} for i, l in enumerate(labs)], "missing": [],
              "trend_state": "UPTREND", "agrees_with_engine_state": True}
        recs[pd.Timestamp(d.date).normalize()] = [{"audit_date": str(d.date.date()), "symbol": "NIFTY", "tf": "1h", "labels": labs,
                                                   "overlay": {"status": "OK", "data": ov}, "independent": {"status": "OK", "data": {"zones": [], "trend_state": "UPTREND"}}}]
    return recs


def test_run_variant_applies_consensus_only_when_mode_set(tl_bundle):
    frames, tl, bcfg = tl_bundle
    days = [d for d in tl.days if d.levels][-15:]
    recs = synth_records(tl, days)
    assert recs
    plan = {(d.date, 8): [long_cand] for d in days}
    fac = lambda e: [ScriptedDetector(plan)]                                                   # noqa: E731
    off = BT.run_variant(tl, "V1", replace(bcfg, visual_records=recs), detector_factory=fac)
    assert "consensus" not in off
    gate_cfg = replace(bcfg, visual_records=recs, engine=replace(bcfg.engine, consensus_mode="gate"))
    g = BT.run_variant(tl, "V1", gate_cfg, detector_factory=fac)
    cons = g["consensus"]
    assert len(cons) == len(tl.days) and int((~cons["fallback"]).sum()) == len(recs)
    hit = cons[~cons["fallback"]]
    assert (hit["levels_after"] <= hit["levels_before"]).all() and (hit["levels_after"] < hit["levels_before"]).any()
    assert {"zone_id", "zone_consensus"} <= set(g["trades"].columns) if len(g["trades"]) else True
    table, results = CMP.modes_table(tl, bcfg, recs, ("off", "score", "gate"))
    assert list(table["mode"]) == ["off", "score", "gate"] and table["दिवस"].iloc[0] >= len(recs)
    rt, rx = CMP.reaction_by_class(tl, frames, recs)
    assert len(rx) > 0 and set(rx["consensus_class"]) <= {"CONSENSUS", "MATH_ONLY", "CONFLICT", "VISUAL_ONLY"}


class FakeBatches:
    def __init__(self, reply_for):
        self.reply_for, self.created = reply_for, []

    def create(self, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"b{len(self.created)}")

    def retrieve(self, bid):
        return SimpleNamespace(processing_status="ended")

    def results(self, bid):
        reqs = self.created[int(bid[1:]) - 1]
        out = []
        for r in reqs:
            out.append(SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(type="succeeded", message=self.reply_for(r))))
        return out


def test_backfill_sync_batch_resume_and_scripts(tl_bundle, tmp_path, monkeypatch):
    frames, tl, bcfg = tl_bundle
    monkeypatch.setattr(R, "render_png", lambda *a, **k: b"\x89PNGfake")
    days = [d for d in tl.days if d.levels][-3:]
    start, end = days[0].date, days[-1].date
    items = BF.plan_items(tl, start, end, ("1h",))
    assert len(items) == 3 and BF.custom_id(days[0].date, "1h", "overlay").endswith("_1h_overlay")
    assert BF.parse_custom_id(BF.custom_id(days[0].date, "1h", "independent"))[2] == "independent"

    def reply(params):
        text = params["messages"][-1]["content"][1]["text"]
        if "Labelled zones" in text:
            labels = json.loads(text.split("\n")[1])
            return msg({"verdicts": [{"label": l["label"], "verdict": "VALID", "reason": "-"} for l in labels], "missing": [], "trend_state": "UPTREND",
                        "agrees_with_engine_state": True})
        return msg({"zones": [], "trend_state": "UPTREND"})

    cache = str(tmp_path / "bf.jsonl")
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **p: reply(p)))
    assert BF.run_sync(client, VCFG, tl, frames, items[:1], cache, log=None) == 1
    done = BF.done_keys(cache)
    assert len(done) == 1 and len(BF.plan_items(tl, start, end, ("1h",), done)) == 2
    fb = FakeBatches(lambda r: reply(r["params"]))
    bclient = SimpleNamespace(messages=SimpleNamespace(batches=fb))
    rest = BF.plan_items(tl, start, end, ("1h",), done)
    reqs = BF.build_requests(VCFG, tl, frames, rest)
    assert len(reqs) == 4
    state = cache + ".batches.json"
    BF.submit(bclient, reqs, state, chunk=3, log=None)
    assert len(fb.created) == 2
    written, pending = BF.collect(bclient, tl, frames, cache, state, log=None)
    assert written == 2 and pending == 0 and len(BF.done_keys(cache)) == 3
    assert BF.collect(bclient, tl, frames, cache, state, log=None) == (0, 0)                  # पुन्हा गोळा होत नाही
    # script: अंदाज फक्त (client नाही), --run विना --yes ⇒ 1
    called = []
    assert RVB.main(["--start", str(start.date()), "--end", str(end.date()), "--tfs", "1h", "--cache", str(tmp_path / "x.jsonl"), "--price-in", "4",
                     "--price-out", "20"], client_factory=lambda: called.append(1), frames=frames) == 0 and not called
    monkeypatch.setenv("VISUAL_AUDIT_MODEL", "test-vision-model")
    assert RVB.main(["--start", str(start.date()), "--end", str(end.date()), "--tfs", "1h", "--cache", str(tmp_path / "x.jsonl"), "--run"],
                    client_factory=lambda: object(), frames=frames) == 1


# ---- EOD script / refresh ---------------------------------------------------------------------------------------------------------------------
def test_audit_date_and_disabled_gate(monkeypatch, capsys):
    assert RVA.audit_date_for(pd.Timestamp("2025-01-07 08:45"), False) == pd.Timestamp("2025-01-07").date()
    assert RVA.audit_date_for(pd.Timestamp("2025-01-07 16:10"), False) == pd.Timestamp("2025-01-08").date()
    assert RVA.audit_date_for(pd.Timestamp("2025-01-10 16:10"), False) == pd.Timestamp("2025-01-13").date()        # शुक्र ⇒ सोम
    monkeypatch.delenv("VISUAL_AUDIT_ENABLED", raising=False)
    assert RVA.main([]) == 0 and "VISUAL_AUDIT_ENABLED" in capsys.readouterr().out


def _live_data():
    one = walk_1m(days=80, seed=12)
    five = one.set_index("timestamp").resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
    daily = one.assign(d=one["timestamp"].dt.normalize()).groupby("d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                                          close=("close", "last"), volume=("volume", "sum")).reset_index().rename(columns={"d": "timestamp"})
    return five, daily


def test_run_symbol_full_with_fake_client_and_store(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "render_png", lambda *a, **k: b"\x89PNGfake")
    five, daily = _live_data()
    fetch = lambda tok, sym, interval, days: (five if interval == "5minute" else daily).copy()        # noqa: E731
    saved = []
    store = SimpleNamespace(load_feedback=lambda s: ({}, None), ensure_tables=lambda: True, save_record=lambda *a, **k: saved.append(a) or True)

    def reply(**params):
        text = params["messages"][-1]["content"][1]["text"]
        if "Labelled zones" in text:
            labels = json.loads(text.split("\n")[1])
            return msg({"verdicts": [{"label": l["label"], "verdict": "VALID", "reason": "-"} for l in labels], "missing": [], "trend_state": "UPTREND",
                        "agrees_with_engine_state": True})
        return msg({"zones": [], "trend_state": "RANGE"})

    client = SimpleNamespace(messages=SimpleNamespace(create=reply))
    now = pd.Timestamp(five["timestamp"].max()) + pd.Timedelta(minutes=10)
    ok, lines, usage = RVA.run_symbol("NIFTY", "tok", VCFG, client, now, now.date(), ("1d", "1h", "15m"), fetch, store, cache=str(tmp_path / "c.jsonl"),
                                      png_root=str(tmp_path / "png"), log=lambda s: None)
    assert ok and len(saved) == 3 and usage["calls"] >= 3 and all(l.startswith("NIFTY") for l in lines)
    assert len(VS.read_jsonl(str(tmp_path / "c.jsonl"))) == 3
    ok2, lines2, est = RVA.run_symbol("NIFTY", "tok", VCFG, None, now, now.date(), ("1d", "1h"), fetch, store, dry_run=True, png_root=str(tmp_path / "png2"),
                                      log=lambda s: None)
    assert ok2 and "dry-run" in lines2[0] and est["calls"] == 4


def test_compute_snapshot_gate_without_visual_run_falls_back():
    five, daily = _live_data()
    now = pd.Timestamp(five["timestamp"].max()) + pd.Timedelta(minutes=10)
    snap = RF.compute_snapshot(five, daily, "NIFTY", replace(EngineConfig(), consensus_mode="gate"), now=now, visual_records=[])
    assert snap.consensus["fallback"] and snap.consensus["mode_used"] == "score"
    off = RF.compute_snapshot(five, daily, "NIFTY", EngineConfig(), now=now)
    assert off.consensus is None and [z["level_id"] for z in off.context.levels[:len(off.levels)]] == [z["level_id"] for z in off.levels]
