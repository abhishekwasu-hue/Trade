"""tests/test_level_validation.py — T3: bounce outcome (no-lookahead नियम), random zones, option breach, logistic, verdict; कृत्रिम डेटा."""
import numpy as np
import pandas as pd
import pytest

import leg_level_validation as T3
from price_action import level_validation as V


def arrs(c, spread=0.5):
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    return np.maximum(o, c) + spread, np.minimum(o, c) - spread, c, np.full(len(c), 1.0)


def test_bounce_break_and_none():
    h, l, c, mr = arrs([105, 104, 102.5, 103.5, 104.5, 106])                     # support 100–102: स्पर्श bar 2, नंतर close 103.5+ ⇒ bounce
    r = V.bounce_outcome(h, l, c, 100, 102, 1, 0, 5, 8, mr, 1.0)
    assert r["touched"] and r["touch_bar"] == 2 and r["outcome"] == V.BOUNCE
    h, l, c, mr = arrs([105, 104, 102.5, 101, 99, 98])
    assert V.bounce_outcome(h, l, c, 100, 102, 1, 0, 5, 8, mr, 1.0)["outcome"] == V.BREAK
    h, l, c, mr = arrs([105, 104, 102.5, 102.6, 102.4, 102.7])
    assert V.bounce_outcome(h, l, c, 100, 102, 1, 0, 5, 8, mr, 1.0)["outcome"] == V.NONE
    h, l, c, mr = arrs([95, 96, 97, 96])                                              # resistance 98–100 ला स्पर्श नाही
    assert not V.bounce_outcome(h, l, c, 98, 100, -1, 0, 3, 8, mr, 1.0)["touched"]


def test_touch_bar_itself_never_counts_as_bounce():
    h, l, c, mr = arrs([105, 104, 108])
    l[1] = 101.0                                                                        # स्पर्श bar 1, त्याच bar चा close 104 (> 102+1)
    r = V.bounce_outcome(h, l, c, 100, 102, 1, 1, 1, 0, mr, 1.0)
    assert r["outcome"] == V.NONE


def test_random_zones_keep_width_and_pool_distance():
    rng = np.random.default_rng(0)
    zs = V.random_zones(1000.0, 4.0, [0.5, -0.5], 50, rng)
    assert len(zs) == 50 and all(abs((z["high"] - z["low"]) - 4.0) < 1e-9 for z in zs)
    assert all(abs(abs((z["low"] + z["high"]) / 2 - 1000.0) - 5.0) < 1e-9 for z in zs)
    assert {z["side"] for z in zs} == {1, -1}
    assert V.random_zones(1000.0, 4.0, [], 5, rng) == []


def test_option_breach():
    dd = pd.DataFrame({"open": [100] * 7, "high": [101] * 7, "low": [99, 99, 97.5, 99, 99, 99, 99], "close": [100, 100, 98, 99.5, 99.2, 100, 100]})
    assert V.option_breach(dd, 0, 98.0, 1, 5) == (True, False)
    assert V.option_breach(dd, 0, 96.0, 1, 5) == (False, False)
    assert V.option_breach(dd, 3, 98.0, 1, 5) is None
    assert V.option_breach(dd, 0, 100.5, -1, 5) == (True, False)


def test_logistic_fit_recovers_sign():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(3000, 2))
    p = 1 / (1 + np.exp(-(1.5 * x[:, 0] - 1.0 * x[:, 1])))
    y = (rng.random(3000) < p).astype(float)
    coef, _ = V.logistic_fit(x, y, l2=0.1)
    assert coef[0] > 1.0 and coef[1] < -0.6


def test_two_prop_z_and_rate():
    assert V.two_prop_z(60, 100, 40, 100) > 2.5 and np.isnan(V.two_prop_z(1, 2, 1, 2))
    assert V.rate([V.BOUNCE, V.BREAK, None]) == pytest.approx(0.5)


def test_period_never_includes_holdout_and_verdict_rules():
    assert T3.period_of("2021-12-31") == "IS" and T3.period_of("2023-05-01") == "VAL" and T3.period_of("2024-04-01") is None
    assert T3.verdict(5.0, 3.0, 2.0, n_min=100) == "KEEP"
    assert T3.verdict(5.0, 3.0, 2.0, pbo=0.2).startswith("REJECT")
    assert T3.verdict(5.0, 3.0, 2.0, n_min=10).startswith("REVIEW")
    assert T3.verdict(-1.0, -1.0, -2.0, n_min=100) == "REJECT"
    assert T3.verdict(5.0, 1.0, 2.0, n_min=100) == "REVIEW"


def test_accuracy_table_reports_random_break_and_widths():
    rows = pd.DataFrame([
        {"engine": "E", "period": "IS", "kind": k, "touched": True, "outcome": o, "react_mr": 0.0, "width": w, "price0": 100.0}
        for k, o, w in [("REAL", V.BOUNCE, 1.0), ("REAL", V.BREAK, 1.0), ("RANDOM", V.BREAK, 1.0), ("RANDOM", V.BREAK, 1.0), ("RANDOM", V.BOUNCE, 1.0)]])
    acc = T3.accuracy_table(rows).iloc[0]
    assert acc["real_bounce_pct"] == 50.0 and acc["random_break_pct"] == pytest.approx(66.7) and acc["real_width_pct_med"] == 1.0
