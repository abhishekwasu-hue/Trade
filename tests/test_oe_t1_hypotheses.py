"""tests/test_oe_t1_hypotheses.py — T1 runner: IS/VAL विभाग, दैनिक R, H5 निवड नियम, H2 तक्ते, अहवाल; कृत्रिम डेटा, network-free."""
import json
import os

import numpy as np
import pandas as pd

import oe_t1_hypotheses as T1
from opportunity_engine import sessions
from tests.test_opportunity_engine_backtest import walk_1m


def test_split_uses_permanent_is_val_boundary():
    df = pd.DataFrame({"date": ["2021-12-31", "2022-01-03", "2015-02-02"], "r": [1.0, 2.0, 3.0]})
    is_, val = T1.split(df)
    assert list(is_["r"]) == [1.0, 3.0] and list(val["r"]) == [2.0]


def test_daily_r_fills_no_trade_days_with_zero():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    tr = pd.DataFrame({"date": ["2020-01-02", "2020-01-02", "2020-01-03"], "r": [1.0, -0.5, 2.0]})
    s = T1.daily_r(tr, dates)
    assert s.tolist() == [0.0, 0.5, 2.0]
    assert T1.daily_r(pd.DataFrame(), dates).tolist() == [0.0, 0.0, 0.0]


def test_pick_best_keeps_base_when_no_candidate_beats_it():
    assert T1.pick_best(("A", "B"), {"BASE": 0.2, "A": 0.1, "B": 0.15}) is None
    assert T1.pick_best(("A", "B"), {"BASE": 0.2, "A": 0.1, "B": 0.25}) == "B"


def test_h2_tables_buckets_scores_and_long_only_rejections():
    tr = pd.DataFrame({"date": ["2016-01-04", "2016-01-05", "2023-01-02"], "setup": ["D2", "D2", "D2"], "score": [55.0, 82.0, 65.0],
                       "bias": ["LONG_ONLY", "SHORT_ONLY", "LONG_ONLY"], "r": [1.0, -1.0, 0.5], "exit_time": [1, 2, 3]})
    dec = pd.DataFrame({"date": ["2016-01-04", "2016-01-06"], "setup": ["D2", "D2"], "bias": ["LONG_ONLY", "LONG_ONLY"], "status": ["REJECTED_GATE", "REJECTED_GATE"],
                        "reasons": ["Gate: counter | x", "Gate: counter"], "direction": ["SHORT", "SHORT"]})
    h2 = T1.h2_tables({"trades": tr, "virtual": pd.DataFrame(), "decisions": dec})
    sc = h2["d2_score"]
    assert set(sc["score"]) >= {"50–60", "≥80", "60–70"} and set(sc["period"]) == {T1.PERIOD_IS, T1.PERIOD_VAL}
    lo = h2["d2_long_only"]
    assert len(lo) == 1 and lo.iloc[0]["candidates"] == 2 and "Gate: counter (2)" in lo.iloc[0]["मुख्य कारणं"]


def test_run_end_to_end_small_grid(tmp_path, monkeypatch):
    monkeypatch.setattr(T1, "TRIALS", {k: T1.TRIALS[k] for k in ("BASE", "H1", "H3_020", "H4c_or_reentry")})
    monkeypatch.setattr(T1, "H3_KEYS", ("H3_020",))
    monkeypatch.setattr(T1, "H4_KEYS", ("H4c_or_reentry",))
    frames = sessions.build_frames(walk_1m(days=40, seed=5, start="2021-11-15"))
    rep = tmp_path / "r.md"
    out = T1.run(frames, str(tmp_path / "o"), str(rep), log=lambda m: None)
    assert set(out["results"]) == {"BASE", "H1", "H3_020", "H4c_or_reentry", "H5"}
    s = out["summary"]
    assert set(s["period"]) == {T1.PERIOD_IS, T1.PERIOD_VAL} and set(s["setup"]) == {"ALL", "D1", "D2"}
    st = json.loads((tmp_path / "o" / "t1_stats.json").read_text(encoding="utf-8"))
    assert st["best"] in out["results"] and "d2_allowed_biases" in st["choice"]["h5_knobs"]
    assert os.path.exists(tmp_path / "o" / "t1_trials.csv") and "PBO" in rep.read_text(encoding="utf-8")
    assert np.isfinite(st["is_daily_sharpe"]["BASE"])


def test_val_split_never_includes_sealed_holdout():
    df = pd.DataFrame({"date": ["2024-03-28", "2024-04-01", "2025-01-02"], "r": [1.0, 2.0, 3.0]})
    _, val = T1.split(df)
    assert list(val["r"]) == [1.0]
