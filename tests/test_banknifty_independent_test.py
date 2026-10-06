"""tests/test_banknifty_independent_test.py — VPS वर चालणारी BANKNIFTY स्क्रिप्ट: synthetic CSV वर end-to-end, ≤ 40 ओळी, CSVs, holdout cut,
H-BR1 नियम. Network/DB नाही."""
import importlib.util
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("bn_test", os.path.join(ROOT, "research", "banknifty_independent_test.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)


def _csv(tmp_path, start="2021-09-01", end="2024-06-28", seed=3):
    rng = np.random.default_rng(seed)
    ts = pd.bdate_range(start, end)
    c = 30000 * np.exp(np.cumsum(rng.normal(0, 0.012, len(ts))))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.002, len(ts)))
    df = pd.DataFrame({"date": ts.strftime("%Y-%m-%d"), "open": o, "high": np.maximum(o, c) * 1.005, "low": np.minimum(o, c) * 0.995, "close": c})
    p = tmp_path / "bn.csv"
    df.to_csv(p, index=False)
    return str(p)


def test_end_to_end_short_report_and_csvs(tmp_path, capsys):
    out = tmp_path / "res"
    assert T.main(["--csv", _csv(tmp_path), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    lines = text.strip().splitlines()
    assert len(lines) <= 40
    assert "2021-09-01 → 2024-03-29" in lines[0] and "2024-06" not in lines[0]  # ISO तारखा बरोबर; holdout कापला (synthetic: 29 मार्च शुक्रवार)
    assert "H-PB1" in text and "लागू नाही" in text and "H-BR1" in text and ("PASS" in text or "FAIL" in text)
    for f in ("a_positional_table.csv", "a_positional_rows.csv", "c_breach_summary.csv", "c_breach_reliability.csv", "c_breach_rows.csv.gz"):
        assert (out / f).exists()
    rows = pd.read_csv(out / "c_breach_rows.csv.gz")
    assert pd.to_datetime(rows["date"]).max() <= pd.Timestamp("2024-03-31") and set(rows["period"]) <= {"IS", "VAL"}


def test_missing_csv_returns_error(tmp_path, capsys):
    assert T.main(["--csv", str(tmp_path / "nope.csv"), "--out", str(tmp_path)]) == 2


def test_hbr1_rule():
    summ = pd.DataFrame([{"period": p, "outcome": "close", "logloss_model": 0.30, "logloss_normal": 0.31} for p in ("IS", "VAL")])
    rel = pd.DataFrame([{"period": p, "outcome": "close", "predicted": "5%–10%", "n": 400, "mean_pred%": 7.0, "actual%": 9.0} for p in ("IS", "VAL")])
    assert T.hbr1_verdict(summ, rel) == (True, [])
    rel.loc[1, "actual%"] = 13.0                                                      # VAL bin 6pp दूर
    ok, why = T.hbr1_verdict(summ, rel)
    assert not ok and "VAL" in why[0]
    rel.loc[1, "n"] = 100                                                             # लहान bin ⇒ मोजत नाही
    assert T.hbr1_verdict(summ, rel)[0]
    summ.loc[0, "logloss_model"] = 0.32
    assert not T.hbr1_verdict(summ, rel)[0]


def test_frozen_coefficients_match_design():
    import json
    import strike_breach_model as M
    with open(M.FROZEN_PATH, encoding="utf-8") as f:
        frozen = json.load(f)
    rng = np.random.default_rng(0)
    n = 300
    ts = pd.bdate_range("2021-01-04", periods=n)
    c = 15000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    dd = pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) * 1.004, "low": np.minimum(o, c) * 0.996, "close": c})
    rows = M.build_rows(dd, grid=(0.5, 1.0, 2.0))
    for oc in ("close", "touch"):
        p = M.predict_frozen(rows, frozen["models"][oc][T.MODEL])
        assert ((p > 0) & (p < 1)).all()
        # दूर strike ⇒ कमी धोका (त्याच दिवस/बाजू/expiry)
        r = rows.assign(p=p).groupby(["date", "side", "expiry"])
        assert all((g.sort_values("z_rv")["p"].diff().dropna() < 0).all() for _, g in r)
