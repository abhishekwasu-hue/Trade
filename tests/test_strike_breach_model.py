"""tests/test_strike_breach_model.py — strike breach model: expiry calendar, no-lookahead features, logistic fit/invert, rows. Network नाही."""
import math

import numpy as np
import pandas as pd

import strike_breach_model as M


def _series(n=320, start="2021-01-04", seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.bdate_range(start, periods=n)
    c = 15000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.002, n))
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) * 1.004, "low": np.minimum(o, c) * 0.996, "close": c})


def test_expiry_is_thursday_or_previous_trading_day_on_holiday():
    days = pd.bdate_range("2023-01-02", "2023-01-20")
    days = days[days != pd.Timestamp("2023-01-12")]                       # गुरुवार सुट्टी ⇒ बुधवार expiry
    exp = M.expiry_days(days)
    assert pd.Timestamp("2023-01-05") in exp and pd.Timestamp("2023-01-11") in exp and pd.Timestamp("2023-01-19") in exp
    assert pd.Timestamp("2023-01-12") not in exp and len(exp) == 3


def test_features_have_no_lookahead():
    dd = _series()
    f1 = M.daily_features(dd)
    dd2 = dd.copy()
    i = 250
    dd2.loc[i:, ["high", "close"]] *= 1.2                                  # दिवस i आणि नंतर बदलले
    f2 = M.daily_features(dd2)
    pd.testing.assert_frame_equal(f1.iloc[:i + 1], f2.iloc[:i + 1])       # दिवस i चे features फक्त ≤ i−1 वर


def test_wilder_matches_simple_recursion():
    x = np.arange(1, 21, dtype=float)
    w = M.wilder(x, 5)
    assert np.isnan(w[3]) and w[4] == 3.0 and abs(w[5] - (3.0 + (6 - 3.0) / 5)) < 1e-12


def test_logit_fit_recovers_coefficients():
    rng = np.random.default_rng(1)
    X = np.c_[np.ones(20000), rng.normal(size=20000)]
    y = (rng.random(20000) < 1 / (1 + np.exp(-(-1.0 + 2.0 * X[:, 1])))).astype(float)
    b = M.fit_logit(X, y, ridge=0.0)
    assert abs(b[0] + 1.0) < 0.08 and abs(b[1] - 2.0) < 0.1


def test_required_z_inverts_model():
    names = ["const", "z", "z2", "ln_h"]
    b = np.array([0.5, -2.0, 0.0, 0.3])
    for target in (0.05, 0.2):
        z = M.required_z(b, names, target, h=3, weekday=0, regime="mid")
        p = 1 / (1 + math.exp(-(0.5 - 2.0 * z + 0.3 * math.log(3))))
        assert abs(p - target) < 1e-6
    assert np.isnan(M.required_z(b, names, 0.99, h=3, weekday=0, regime="mid"))


def test_build_rows_basic_properties():
    dd = _series(n=260, start="2021-06-01")                               # IS → VAL सीमा ओलांडते
    rows = M.build_rows(dd, grid=(0.5, 1.0, 2.0))
    assert len(rows) and set(rows["period"]) <= {"IS", "VAL"}
    assert (rows["dte"] == rows["h"] - 1).all() and rows["dte"].between(0, 9).all()
    # दूरचा strike कधीही जवळच्यापेक्षा जास्त वेळा तुटत नाही (त्याच दिवस/बाजू/expiry)
    g = rows.groupby(["date", "side", "expiry"])
    assert all((grp.sort_values("z_rv")["touch"].diff().dropna() <= 0).all() for _, grp in g)
    # hold-window period ओलांडत नाही: 2021 अखेरीस entry असलेल्या rows ची expiry 2021 मध्येच
    last_is = rows[rows["period"] == "IS"]["date"].max()
    assert last_is <= pd.Timestamp("2021-12-31")


def test_reliability_and_scores_shapes():
    y = np.array([0, 1, 0, 0, 1, 0, 0, 0, 1, 0] * 20, float)
    p = np.linspace(0.01, 0.6, len(y))
    months = np.repeat(np.arange(10), 20)
    rel = M.reliability(y, p, months)
    assert rel["n"].sum() == len(y)
    s = M.scores(y, p)
    assert 0 < s["brier"] < 1 and s["logloss"] > 0
