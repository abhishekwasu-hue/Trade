"""tests/test_elliott_c3.py — candle merge C3 report मधली सांख्यिकी (numpy): Mann-Whitney, day-block CI, PBO (CSCV), Reality Check."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research"))
import elliott_candle_merge_report as CM  # noqa: E402


def _trades(mean, n=300, seed=0):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2019-03-01", periods=n, freq="B")
    return pd.DataFrame({"fill": days, "R": rng.normal(mean, 0.05, n), "pnl": 0.0})


def test_mann_whitney_detects_shift_and_not_noise():
    rng = np.random.default_rng(1)
    p, eff = CM.mann_whitney(rng.normal(1, 1, 200), rng.normal(0, 1, 200))
    assert p < 1e-6 and eff > 0.3
    p0, eff0 = CM.mann_whitney(rng.normal(0, 1, 200), rng.normal(0, 1, 200))
    assert p0 > 0.01 and abs(eff0) < 0.2


def test_day_block_ci_covers_mean():
    lo, hi = CM.day_block_ci(_trades(0.02))
    assert lo < 0.02 < hi


def test_pbo_low_for_true_winner_high_for_noise():
    rng = np.random.default_rng(2)
    noise = pd.DataFrame(rng.normal(0, 1, (10, 16)))
    assert CM.pbo_cscv(noise, max_combos=400) > 0.2
    real = noise.copy()
    real.iloc[0] += 3.0
    assert CM.pbo_cscv(real, max_combos=400) < 0.05


def test_reality_check_per_trade_not_fooled_by_fewer_trades():
    bench = _trades(-0.02, seed=3)
    fewer = bench.iloc[::3].copy()                                                # तेच trades, कमी — प्रति-trade R तोच
    assert CM.reality_check({"fewer": fewer}, bench, reps=300) > 0.2
    better = _trades(0.03, seed=4)
    assert CM.reality_check({"better": better}, bench, reps=300) < 0.05


def test_random_compare_uses_both_sampling_noises():
    rng = np.random.default_rng(5)
    pool = pd.DataFrame({"ep": np.repeat(np.arange(60), 5), "R": rng.normal(-0.02, 0.05, 300)})
    same = CM.random_compare(rng.normal(-0.02, 0.05, 80), pool, reps=400)
    assert same["lo"] < 0 < same["hi"]                                               # सारखं ⇒ CI 0 ओलांडतो
    worse = CM.random_compare(rng.normal(-0.08, 0.02, 200), pool, reps=400)
    assert worse["hi"] < 0 and worse["p"] > 0.95


def test_leg_kind_labels():
    k = CM.LEG_KIND
    assert k["impulse"][("impulse", "3")] == "impulsive" and k["impulse"][("impulse", "4")] == "corrective"
    assert k["zigzag"][("zigzag", "A")] == "impulsive" and k["zigzag"][("zigzag", "B")] == "corrective"
    assert ("flat", "A") not in k["flat"] and k["flat"][("flat", "C")] == "impulsive"


def test_mann_whitney_ties_do_not_break():
    p, eff = CM.mann_whitney([0] * 50 + [1] * 10, [0] * 55 + [1] * 5)
    assert 0 < p <= 1 and -1 <= eff <= 1
