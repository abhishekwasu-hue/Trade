"""tests/test_price_action_level_strength.py — T2.4 ताकद features (as-of), T2.5 approach नियम, T2.6 घटना (no-lookahead); कृत्रिम डेटा."""
import numpy as np
import pandas as pd
import pytest

from price_action import legs as L
from price_action import level_strength as S


def frame(closes, spread=1.0, start="2019-01-01 09:15", opens=None):
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]] if opens is None else np.asarray(opens, float)
    return pd.DataFrame({"timestamp": pd.date_range(start, periods=len(c), freq="15min"), "open": o,
                         "high": np.maximum(o, c) + spread, "low": np.minimum(o, c) - spread, "close": c})


def demand_df():
    # 30 bars सपाट 100 जवळ, मग जोरदार वर (departure), मग दोनदा परत 100–102 zone ला स्पर्श
    flat = [100 + (i % 2) * 0.5 for i in range(30)]
    up = [104, 109, 114, 118, 120, 121, 120, 119]
    back = list(np.linspace(118, 101.5, 10)) + list(np.linspace(103, 115, 8)) + list(np.linspace(114, 101.8, 8)) + [106, 110]
    return frame(flat + up + back)


ZONE = {"low": 99.0, "high": 102.0, "kind": "DEMAND"}


def test_side_of_and_round_distance():
    assert S.side_of({"low": 1, "high": 2, "kind": "SUPPLY"}, 0.5) == -1
    assert S.side_of({"low": 1, "high": 2, "kind": "KEY"}, 3.0) == 1 and S.side_of({"low": 1, "high": 2, "kind": "KEY"}, 1.5) == 0
    assert S.round_distance(22480, "NIFTY") == 20 and S.round_distance(48700, "BANKNIFTY") == 200


def test_strength_features_departure_base_touches():
    df = demand_df()
    z = {**ZONE, "formed_at": df["timestamp"].iloc[29]}
    f = S.strength_features(z, df, len(df) - 1)
    assert f["origin_known"] and f["departure_mr"] > 3 and f["base_bars"] >= 20 and f["touches"] == 2 and f["side"] == 1
    assert 0 < f["recency"] <= 1 and not f["role_reversal"]
    score = S.strength_score(f)
    assert 0 <= score <= 100


def test_features_are_as_of_t_and_ignore_future_bars():
    df = demand_df()
    z = {**ZONE, "formed_at": df["timestamp"].iloc[29]}
    t = 45
    a = S.strength_features(z, df, t)
    df2 = df.copy()
    df2.loc[t + 1:, ["open", "high", "low", "close"]] = 50.0
    b = S.strength_features(z, df2, t)
    assert a == b
    fut = {**ZONE, "formed_at": df["timestamp"].iloc[60]}
    assert not S.strength_features(fut, df, 40)["origin_known"]                      # भविष्यात बनलेला zone


def test_role_reversal_detected():
    c = [110, 108, 105, 101, 97, 95, 96, 98, 100.5, 98, 96, 94]                       # support 99–102 तुटला, मग खालून retest करून नाकारला
    df = frame(c, spread=0.6)
    f = S.strength_features({"low": 99.0, "high": 102.0, "kind": "SUPPORT", "formed_at": df["timestamp"].iloc[0]}, df, len(df) - 1)
    assert f["role_reversal"]


def test_touches_weight_zero_by_default():
    f = {"departure_mr": 0, "origin_label": None, "base_bars": None, "recency": 0.0, "tpo_share": 1.0, "role_reversal": False, "touches": 5}
    assert S.strength_score(f) == 0.0
    assert S.strength_score(f, {"touches": 1.0}) > 0


def test_tpo_share():
    fine = frame([100.0] * 10 + [110.0] * 10, spread=0.1, start="2019-01-01 09:15")
    assert S.tpo_share(fine, 99, 101, fine["timestamp"].iloc[-1]) == pytest.approx(0.5)
    assert S.tpo_share(None, 99, 101, fine["timestamp"].iloc[-1]) is None


def _leg(label, direction, end_price):
    return L.Leg(0, 5, 6, direction, 0.0, end_price, {}, label=label)


def test_approach_rule():
    sup = {"low": 99, "high": 102, "kind": "SUPPORT"}
    assert S.approach(_leg(L.HEALTHY_PULLBACK, -1, 103), sup, 70)[0] == S.REACTION_CANDIDATE
    assert S.approach(_leg(L.HEALTHY_PULLBACK, -1, 103), sup, 30)[0] is None                       # कमकुवत zone
    assert S.approach(_leg(L.STRONG_IMPULSE, -1, 103), sup, 90)[0] == S.BREAK_CANDIDATE
    assert S.approach(_leg(L.HEALTHY_PULLBACK, 1, 103), sup, 90)[0] is None                         # zone पासून दूर जातोय
    res = {"low": 120, "high": 122, "kind": "RESISTANCE"}
    assert S.approach(_leg(L.HEALTHY_PULLBACK, 1, 119), res, 60)[0] == S.REACTION_CANDIDATE
    assert S.approach(None, res, 60)[0] is None


def test_zone_events_sweep_failed_break_and_no_lookahead():
    sup = {"low": 99.0, "high": 102.0, "kind": "SUPPORT"}
    c = [105, 104, 103, 101, 100.5, 103, 101, 98.5, 100.5, 101, 104, 103, 97, 96, 95, 94]
    o = [105, 105, 104, 103, 101, 100.5, 103, 101, 98.5, 100.5, 101, 104, 103, 97, 96, 95]
    df = frame(c, spread=0.3, opens=o)
    df.loc[4, "low"] = 98.0                                                          # wick पलीकडे, close आत ⇒ SWEEP
    ev = S.zone_events(sup, df, 1, len(df) - 1, n_reclaim=2)
    types = [e["type"] for e in ev]
    assert types[0] == S.SWEEP and S.FAILED_BREAKOUT in types and types[-1] in (S.BREAK, S.BREAK_CASCADE)
    fb = next(e for e in ev if e["type"] == S.FAILED_BREAKOUT)
    assert fb["bar"] == 7 and fb["known_at"] == 9
    br = ev[-1]
    assert br["bar"] == 12 and br["known_at"] == 14
    cut = S.zone_events(sup, df, 1, 13, n_reclaim=2)                                # break bar नंतर फक्त 1 bar ⇒ अजून निर्णय नाही
    assert all(e["bar"] < 12 for e in cut)


def test_break_cascade_on_displacement():
    sup = {"low": 99.0, "high": 102.0, "kind": "SUPPORT"}
    c = [104 + (i % 2) * 0.4 for i in range(25)] + [90, 89, 88]
    df = frame(c, spread=0.3)
    ev = S.zone_events(sup, df, 20, len(df) - 1, n_reclaim=2)
    assert ev and ev[-1]["type"] == S.BREAK_CASCADE
