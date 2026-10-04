"""tests/test_opportunity_engine_forward.py -- PR-V forward testing: label ↔ level overlap-matching, forward अहवाल (records → audit rows, खर्च, reaction, 3 modes).
Network-free, API call नाही."""
import os

import pandas as pd

import run_visual_forward_report as FR
from opportunity_engine import backtest as BT
from opportunity_engine import sessions
from opportunity_engine.visual_audit import consensus as C
from opportunity_engine.visual_audit import store as VS
from tests.test_opportunity_engine_backtest import walk_1m
from tests.test_opportunity_engine_visual import LEVELS, POOL, record, synth_records


def test_match_label_by_id_then_overlap_same_kind_and_tf():
    by_id = {z["level_id"]: z for z in LEVELS}
    assert C.match_label({"level_id": "a1"}, LEVELS, by_id)["level_id"] == "a1"
    moved = {"level_id": "zzz", "kind": "DEMAND", "tf": "1h", "outer_low": 101.0, "outer_high": 111.0}
    assert C.match_label(moved, LEVELS, by_id)["level_id"] == "a1"
    assert C.match_label({**moved, "kind": "SUPPLY"}, LEVELS, by_id) is None
    assert C.match_label({**moved, "outer_low": 108.5, "outer_high": 130.0}, LEVELS, by_id) is None          # overlap < 50%
    assert C.match_label({"level_id": "zzz"}, LEVELS, by_id) is None


def test_classify_survives_level_id_drift():
    rec = record()
    for lab in rec["labels"]:
        lab["level_id"] = "drift-" + lab["level_id"]
        lab["tf"] = "1h"
    res = C.classify(LEVELS, POOL, [rec])
    assert res["classes"]["b2"]["class"] == C.CONSENSUS and res["classes"]["c3"]["class"] == C.MATH_ONLY


def test_records_to_audit_df_and_cost_summary():
    recs = [{**record(), "usage": {"input_tokens": 2000, "output_tokens": 500, "calls": 2}},
            {**record(tf="1d", status="FAILED"), "audit_date": "2025-01-08", "usage": {"input_tokens": 1000, "output_tokens": 0, "calls": 1}}]
    df = FR.records_to_audit_df(recs)
    assert len(df) == 6 and set(df["model_verdict"].dropna()) == {"VALID", "SPURIOUS", "SHIFT_UP"} and df["model_verdict"].isna().sum() == 3
    c = FR.cost_summary(recs, 4, 20)
    assert c["calls"] == 3 and c["दिवस"] == 2 and c["cost_usd"] == round(3000 / 1e6 * 4 + 500 / 1e6 * 20, 2)
    assert FR.cost_summary(recs)["cost_usd"] is None


def test_forward_report_end_to_end(tmp_path):
    one = walk_1m(days=60, seed=6)
    frames = sessions.build_frames(one)
    daily = one.assign(d=one["timestamp"].dt.normalize()).groupby("d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                                          close=("close", "last")).reset_index().rename(columns={"d": "timestamp"})
    tl = BT.prepare_timeline(frames, BT.BacktestConfig(variants=("V1",)))
    recs = synth_records(tl, [d for d in tl.days if d.levels][-10:])
    cache = str(tmp_path / "c.jsonl")
    for day_recs in recs.values():
        for r in day_recs:
            VS.append_jsonl(cache, r)
    out = str(tmp_path / "out")
    assert FR.main(["--cache", cache, "--out", out, "--price-in", "4", "--price-out", "20"], frames=frames, daily=daily) == 0
    for name in ("forward_cost.csv", "forward_reaction_by_verdict.csv", "forward_reaction_by_class.csv", "forward_consensus_modes.csv"):
        assert os.path.exists(os.path.join(out, name))
    modes = pd.read_csv(os.path.join(out, "forward_consensus_modes.csv"))
    assert list(modes["mode"]) == ["off", "score", "gate"]
    assert FR.main(["--cache", str(tmp_path / "none.jsonl"), "--out", out]) == 0
    assert FR.main(["--cache", cache, "--out", out, "--symbol", "BANKNIFTY"]) == 0                     # त्या symbol चे records नाहीत
