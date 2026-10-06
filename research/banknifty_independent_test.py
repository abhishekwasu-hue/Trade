"""
research/banknifty_independent_test.py
--------------------------------------
🎓 BANKNIFTY स्वतंत्र-डेटा चाचण्या (वापरकर्त्याचा निर्णय 2026-10-06). नियम `docs/reports/preregistered_hypotheses.md` मध्ये **आधीच** नोंदवलेले.
Report-only: फक्त CSV वाचतो. Network, orders आणि DB write काहीच नाही. 2024-03-31 नंतरचा भाग load करतानाच कापला जातो (sealed holdout बंद).
IS = 2015–2021, VAL = 2022 → 2024-03 (NIFTY सारखेच).

  (a) H-POS1 — positional short strike (Daily/Weekly levels: SR V3 day+week, sr_dynamic daily) वि. random strike, अंतर-buckets, 5 सत्र hold.
  (b) H-PB1  — "DANGEROUS नसलेले वि. DANGEROUS pullback": 15M साठी नोंदवलेलं ⇒ daily डेटावर **लागू नाही** (चालवत नाही).
  (c) H-BR1  — NIFTY IS वर fit केलेलं strike-breach model (गोठवलेले coefs) BANKNIFTY वर: predicted वि. actual.

छोटा अहवाल (≤ 40 ओळी) stdout वर; पूर्ण निकाल `--out` (डीफॉल्ट data/research/banknifty_results/) मध्ये CSV.

    python3 research/banknifty_independent_test.py --csv data/research/BANKNIFTY_daily_2015_2024-03.csv
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np            # noqa: E402
import pandas as pd           # noqa: E402

import banknifty_positional as B       # noqa: E402
import strike_breach_model as M        # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "data", "research", "banknifty_results")
BIN_MIN_N, BIN_TOL = 300, 0.05                                     # H-BR1 नियम
MODEL = "M_RV (पूर्ण)"


def positional(dd):
    tab, rows = B.run(dd)
    return tab, rows, B.level_edge_cells(tab)


def breach_calibration(dd, frozen):
    rows = M.build_rows(dd)
    rows["month"] = rows["date"].dt.year * 100 + rows["date"].dt.month
    for oc in ("close", "touch"):
        rows[f"p_{oc}"] = M.predict_frozen(rows, frozen["models"][oc][MODEL])
    rows["p_normal"] = [M.norm_sf(z) for z in rows["z_rv"]]
    summary, rel = [], []
    for per in ("IS", "VAL"):
        r = rows[rows["period"] == per]
        if not len(r):
            continue
        for oc in ("close", "touch"):
            y, p = r[oc].to_numpy(), r[f"p_{oc}"].to_numpy()
            sc = M.scores(y, p)
            row = {"period": per, "outcome": oc, "n": len(r), "mean_pred%": round(100 * p.mean(), 1), "actual%": round(100 * y.mean(), 1),
                   "logloss_model": round(sc["logloss"], 4), "brier_model": round(sc["brier"], 4)}
            if oc == "close":
                row["logloss_normal"] = round(M.scores(y, r["p_normal"].to_numpy())["logloss"], 4)
            summary.append(row)
            t = M.reliability(y, p, r["month"].to_numpy())
            t.insert(0, "outcome", oc)
            t.insert(0, "period", per)
            rel.append(t)
    return rows, pd.DataFrame(summary), (pd.concat(rel, ignore_index=True) if rel else pd.DataFrame())


def hbr1_verdict(summary, rel):
    """H-BR1: IS आणि VAL दोन्हींत (1) logloss_model ≤ logloss_normal (2) n ≥ 300 bins मध्ये |actual − pred| ≤ 5pp. (pass, कारणे)."""
    why = []
    for per in ("IS", "VAL"):
        s = summary[(summary["period"] == per) & (summary["outcome"] == "close")]
        if not len(s):
            why.append(f"{per}: डेटा नाही")
            continue
        s = s.iloc[0]
        if s["logloss_model"] > s["logloss_normal"]:
            why.append(f"{per}: log-loss model {s['logloss_model']} > Φ(−z) {s['logloss_normal']}")
        b = rel[(rel["period"] == per) & (rel["outcome"] == "close") & (rel["n"] >= BIN_MIN_N)]
        for _, x in b.iterrows():
            if abs(x["actual%"] - x["mean_pred%"]) > 100 * BIN_TOL:
                why.append(f"{per} bin {x['predicted']}: actual {x['actual%']}% वि. predicted {x['mean_pred%']}%")
    return not why, why


def report_lines(dd, tab, edges, summary, rel, ok, why, out):
    L = [f"BANKNIFTY daily: {len(dd)} दिवस {dd['timestamp'].min():%Y-%m-%d} → {dd['timestamp'].max():%Y-%m-%d} (holdout कापला)",
         "", "(a) H-POS1 positional strike — touch-breach% level/random (cluster z), 5 सत्र"]
    if len(tab):
        for (eng, bk), g in tab.groupby(["engine", "अंतर"], sort=True):
            cells = []
            for per in ("IS", "VAL"):
                r = g[g["period"] == per]
                cells.append(f"{per} {r.iloc[0]['touch_level%']}/{r.iloc[0]['touch_random%']} z{r.iloc[0]['z_touch']} n{r.iloc[0]['n_level']}"
                             if len(r) else f"{per} —")
            L.append(f"  {eng:8s} {bk:9s} " + " | ".join(cells))
    L.append("  ⇒ " + (("LEVEL EDGE: " + ", ".join(f"{e} {b}" for e, b in edges)) if edges else "null टिकला (pre-registered नियमानुसार level edge नाही)"))
    L += ["", "(b) H-PB1: 15M साठी नोंदवलेलं; हा daily डेटा ⇒ लागू नाही, चालवलं नाही (BANKNIFTY 15M/1M अधिकृत डेटा लागेल)", "",
          "(c) H-BR1 NIFTY-fit model (गोठवलेले coefs) BANKNIFTY वर — predicted वि. actual"]
    for _, s in summary.iterrows():
        extra = f" | Φ(−z) {s['logloss_normal']}" if s["outcome"] == "close" else ""
        L.append(f"  {s['period']:3s} {s['outcome']:5s} n{s['n']} pred {s['mean_pred%']}% act {s['actual%']}% | logloss {s['logloss_model']}{extra}")
    c = rel[rel["outcome"] == "close"] if len(rel) else rel
    if len(c):
        L.append("  close bins (pred→act, n):")
        for per in ("IS", "VAL"):
            r = c[c["period"] == per]
            L.append(f"  {per}: " + "; ".join(f"{x['predicted']} {x['mean_pred%']}→{x['actual%']} ({x['n']})" for _, x in r.iterrows()))
    L.append("  ⇒ H-BR1 " + ("PASS" if ok else "FAIL: " + "; ".join(why[:3]) + (" …" if len(why) > 3 else "")))
    L += ["", f"पूर्ण निकाल: {out}"]
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--coef", default=M.FROZEN_PATH)
    a = ap.parse_args(argv)
    if not os.path.exists(a.csv):
        print(f"CSV सापडली नाही: {a.csv}")
        return 2
    np.seterr(all="ignore")
    dd = B.load_banknifty_daily(a.csv)
    with open(a.coef, encoding="utf-8") as f:
        frozen = json.load(f)
    tab, pos_rows, edges = positional(dd)
    rows, summary, rel = breach_calibration(dd, frozen)
    ok, why = hbr1_verdict(summary, rel)
    os.makedirs(a.out, exist_ok=True)
    tab.to_csv(os.path.join(a.out, "a_positional_table.csv"), index=False)
    pos_rows.to_csv(os.path.join(a.out, "a_positional_rows.csv"), index=False)
    summary.to_csv(os.path.join(a.out, "c_breach_summary.csv"), index=False)
    rel.to_csv(os.path.join(a.out, "c_breach_reliability.csv"), index=False)
    rows.to_csv(os.path.join(a.out, "c_breach_rows.csv.gz"), index=False, compression="gzip")
    lines = report_lines(dd, tab, edges, summary, rel, ok, why, a.out)
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
