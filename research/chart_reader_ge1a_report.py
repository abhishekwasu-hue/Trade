"""research/chart_reader_ge1a_report.py — G-E1a (KB) अहवाल, report-only, फक्त IS (2015–2021) + golden (असेल तर).

  1. Calibration (KB भाग G: MR = 20 बंद bars): equal highs/lows tolerance 0.15 MR, sweep 0.1–1.0 MR, Fibonacci band ± 0.25 MR —
     IS 15m वर वितरण आणि परिणाम. **बदल नाही** — आकडे दाखवणे; बदल Abhi च्या मंजुरीने.
  2. IS grade वितरण (KB भाग D ⚠️): pullback-end उमेदवारांवर (structure entry point) पूर्ण evaluate ⇒ A / B / C %, entries, व्हेटो, सरासरी गुण.
  3. स्पष्ट reversal दिवस (2018-02-02, LTCG budget — लांब तेजीनंतर मोठी घसरण): bull put बाजूचे signals ⇒ अपेक्षित C.
  4. 7 Oct 2026 golden (contaminated, illustration only) — trade-data मध्ये file असेल तर; अपेक्षित A.

    python3 research/chart_reader_ge1a_report.py [--sample 400] [--trade-data /home/user/trade-data]
अहवाल: docs/reports/chart_reader_ge1a_kb.md · JSON: data/research/chart_reader_ge1a_kb.json (gitignored).
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chart_reader import evaluate as EV       # noqa: E402
from chart_reader import grade as G           # noqa: E402
from chart_reader import measures as M        # noqa: E402
from chart_reader import settings as CS       # noqa: E402
from chart_reader import structure as ST      # noqa: E402
from elliott import data_policy as DP         # noqa: E402

REPORT = os.path.join(ROOT, "docs", "reports", "chart_reader_ge1a_kb.md")
OUT_JSON = os.path.join(ROOT, "data", "research", "chart_reader_ge1a_kb.json")
FIBS = (0.382, 0.5, 0.618, 0.786)


def _window(m1, asof, days=90):
    t = pd.Timestamp(asof)
    return m1[(m1["timestamp"] >= t - pd.Timedelta(days=days)) & (m1["timestamp"] < t)].reset_index(drop=True)


# ---------------------------------------------------------------------------------------------------------------------
# 1. calibration
# ---------------------------------------------------------------------------------------------------------------------
def calibration(trig, s):
    h, lo, c = (trig[k].to_numpy(float) for k in ("high", "low", "close"))
    mr = M.mr_array(trig)
    atr = pd.Series(h - lo).rolling(14).mean().to_numpy()
    med50 = pd.Series(h - lo).shift(1).rolling(50).median().to_numpy()
    ok = np.isfinite(mr) & np.isfinite(atr) & np.isfinite(med50)
    out = {"mr20_over_atr14": np.round(np.quantile(mr[ok] / atr[ok], [0.1, 0.5, 0.9]), 3).tolist(),
           "mr20_over_med50": np.round(np.quantile(mr[ok] / med50[ok], [0.1, 0.5, 0.9]), 3).tolist()}
    piv = M.pivots(trig, s["internal_atr_mult"])
    n = len(c)
    # (a) equal highs / lows: जोडी अंतर (MR) आणि pool वर पुढची प्रतिक्रिया (rejection वि. break)
    rows = []
    for kind in ("H", "L"):
        P = [p for p in piv if p[2] == kind]
        for jj in range(1, len(P)):
            b, px, _, cb = P[jj]
            cb = cb if cb is not None else b
            m = mr[cb] if cb < n else np.nan
            if not np.isfinite(m) or m <= 0:
                continue
            prev = [q for q in P[max(0, jj - 8):jj] if b - q[0] >= s["eq_min_bars"]]
            if not prev:
                continue
            d = min(abs(px - q[1]) for q in prev) / m
            lvl = max(px, min(prev, key=lambda q: abs(px - q[1]))[1]) if kind == "H" else min(px, min(prev, key=lambda q: abs(px - q[1]))[1])
            outcome = None
            for k in range(cb + 1, min(n, cb + 200)):
                touched = h[k] >= lvl - 0.1 * m if kind == "H" else lo[k] <= lvl + 0.1 * m
                if not touched:
                    continue
                beyond = c[k] > lvl + 0.25 * m if kind == "H" else c[k] < lvl - 0.25 * m
                nxt = k + 1 < n and ((c[k + 1] > lvl) if kind == "H" else (c[k + 1] < lvl))
                outcome = "break" if beyond and nxt else "reject"
                break
            rows.append((d, outcome))
    eq = []
    tol_grid = (0.10, 0.15, 0.20, 0.25, 0.35, 0.50)
    ds = np.array([r[0] for r in rows])
    for tol in tol_grid:
        sel = [r for r in rows if r[0] <= tol and r[1] is not None]
        rej = np.mean([r[1] == "reject" for r in sel]) if sel else np.nan
        eq.append({"tol_mr": tol, "pivots_with_equal_partner_pct": round(100 * float((ds <= tol).mean()), 1) if len(ds) else None,
                   "pools_retested": len(sel), "reject_pct": round(100 * float(rej), 1) if sel else None})
    far = [r for r in rows if r[0] > 1.0 and r[1] is not None]
    out["equal_pools"] = {"pairs": len(rows), "dist_quantiles_mr": np.round(np.quantile(ds, [0.1, 0.25, 0.5]), 3).tolist() if len(ds) else [],
                          "by_tol": eq, "baseline_far_pivots_reject_pct": round(100 * float(np.mean([r[1] == "reject" for r in far])), 1)
                          if far else None}
    # (b) sweep depth: confirmed swing pivot च्या पलीकडे पहिली wick; reclaim (त्याच / पुढच्या 2 bars close आत) आणि यश
    #     (reclaim नंतर 20 bars मध्ये pivot ± 1 MR आत जाणं, sweep extreme तुटण्याआधी)
    buckets = [(0.0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 9e9)]
    stats = {b: [0, 0, 0] for b in buckets}
    for b, px, kind, cb in piv:
        cb = cb if cb is not None else b
        for k in range(cb + 1, min(n, cb + 150)):
            hit = lo[k] < px if kind == "L" else h[k] > px
            if not hit:
                continue
            m = mr[k]
            if not np.isfinite(m) or m <= 0:
                break
            depth = (px - lo[k]) / m if kind == "L" else (h[k] - px) / m
            ext = lo[k] if kind == "L" else h[k]
            rec = None
            for q in range(k, min(n, k + 3)):
                if (c[q] > px) if kind == "L" else (c[q] < px):
                    rec = q
                    break
            win = False
            if rec is not None:
                tgt = px + m if kind == "L" else px - m
                for q in range(rec + 1, min(n, rec + 21)):
                    if (lo[q] < ext) if kind == "L" else (h[q] > ext):
                        break
                    if (h[q] >= tgt) if kind == "L" else (lo[q] <= tgt):
                        win = True
                        break
            for bk in buckets:
                if bk[0] <= depth < bk[1]:
                    stats[bk][0] += 1
                    stats[bk][1] += rec is not None
                    stats[bk][2] += win
            break
    out["sweep_depth"] = [{"depth_mr": f"{a:g}–{(b if b < 1e9 else '∞')}", "n": v[0], "reclaim_pct": round(100 * v[1] / v[0], 1) if v[0] else None,
                           "success_after_reclaim_pct": round(100 * v[2] / v[1], 1) if v[1] else None} for (a, b), v in stats.items()]
    # (c) Fibonacci band: impulse leg (≥ fib_min_impulse_mr) नंतरच्या counter-leg चं टोक ⇒ जवळच्या fib पासून अंतर (MR), null = uniform retrace
    sw = [(p[0], p[1]) for p in M.pivots(trig, s["swing_atr_mult"])]
    dist, null = [], []
    rng_ = np.random.default_rng(1)
    for i in range(len(sw) - 2):
        (b0, p0), (b1, p1), (b2, p2) = sw[i], sw[i + 1], sw[i + 2]
        m = mr[b2] if b2 < n else np.nan
        imp = abs(p1 - p0)
        if not np.isfinite(m) or m <= 0 or imp < s["fib_min_impulse_mr"] * m:
            continue
        r = abs(p2 - p1) / imp
        if not 0.2 <= r <= 1.0:
            continue
        dist.append(min(abs(r - f) for f in FIBS) * imp / m)
        u = rng_.uniform(0.2, 1.0)
        null.append(min(abs(u - f) for f in FIBS) * imp / m)
    fib = []
    for band in (0.15, 0.25, 0.35, 0.5):
        fib.append({"band_mr": band, "within_pct": round(100 * float(np.mean(np.array(dist) <= band)), 1) if dist else None,
                    "uniform_null_pct": round(100 * float(np.mean(np.array(null) <= band)), 1) if null else None})
    out["fib_band"] = {"pullbacks": len(dist), "by_band": fib}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# 2. IS grade distribution
# ---------------------------------------------------------------------------------------------------------------------
def candidates(trig, s, step=1):
    found = []
    for j in range(300, len(trig), step):
        w = trig.iloc[j - 300:j + 1].reset_index(drop=True)
        r = ST.read(w, s)
        if r["entry_point"]:
            found.append((trig["bar_end"].iloc[j], r["correction_type"]))
    return found


def distribution(m1, cands, s, sample):
    stride = max(len(cands) // sample, 1)
    rows = []
    for t, ctype in cands[::stride][:sample]:
        r = EV.evaluate(_window(m1, t), "srv2", t, s=s)
        rows.append({"asof": str(t), "ctype": ctype, "side": r["side"], "grade": r["grade"], "total": r.get("total"), "entry": r["entry"],
                     "points": r.get("points", {}), "vetoes": r.get("vetoes", []), "hard": r.get("hard_rules", []),
                     "reversal": (r.get("reversal") or {}).get("status")})
    n = len(rows)
    out = {"n": n, "grade_pct": {g: round(100 * sum(x["grade"] == g for x in rows) / n, 1) for g in "ABC"} if n else {},
           "entries": sum(x["entry"] for x in rows), "vetoed": sum(bool(x["vetoes"]) for x in rows),
           "mean_points": {k: round(float(np.mean([x["points"].get(k, 0) for x in rows])), 2) for k in G.KEYS} if n else {},
           "total_quantiles": np.round(np.quantile([x["total"] or 0 for x in rows], [0.1, 0.25, 0.5, 0.75, 0.9]), 1).tolist() if n else [],
           "by_type": {}}
    for ct in sorted({x["ctype"] for x in rows}):
        sub = [x for x in rows if x["ctype"] == ct]
        out["by_type"][ct] = {"n": len(sub), **{g: round(100 * sum(x["grade"] == g for x in sub) / len(sub), 1) for g in "ABC"},
                              "entries": sum(x["entry"] for x in sub)}
    vc = {}
    for x in rows:
        for v in x["vetoes"]:
            key = (v.split("]")[0] + "]") if "]" in v else v[:24]
            vc[key] = vc.get(key, 0) + 1
    out["veto_counts"] = vc
    out["rows"] = rows
    return out


def day_check(m1, day, s, side_want):
    rows = []
    for t in pd.date_range(f"{day} 09:45", f"{day} 15:30", freq="15min"):
        r = EV.evaluate(_window(m1, t), "srv2", t, s=s)
        rows.append({"asof": str(t)[11:16], "side": r["side"], "grade": r["grade"], "total": r.get("total"), "entry": r["entry"],
                     "pb": (r.get("points") or {}).get("PB"), "vetoes": r.get("vetoes", []), "why": r["why_no_entry"][:2]})
    want = [x for x in rows if x["side"] == side_want]
    return {"day": day, "rows": rows, "side_want": side_want, "n_side": len(want), "entries_side": sum(x["entry"] for x in want),
            "grades_side": {g: sum(x["grade"] == g for x in want) for g in "ABC"}}


def golden(path, s):
    if not os.path.exists(path):
        return None
    g = DP.filter_allowed(pd.read_csv(path, parse_dates=["timestamp"]), "golden")
    best = None
    for t in pd.date_range("2026-10-07 09:45", "2026-10-07 15:15", freq="15min"):
        r = EV.evaluate(_window(g, t), "srv2", t, s=s)
        key = (r["side"] == -1, r["entry"], r.get("total") or 0)
        if best is None or key > best[0]:
            best = (key, r)
    r = best[1]
    return {"asof": r["asof"], "side": r["side"], "grade": r["grade"], "total": r.get("total"), "entry": r["entry"], "lines": r["lines"],
            "story": r["story"]}


# ---------------------------------------------------------------------------------------------------------------------
def _md(res):
    c = res["calibration"]
    L = ["# Chart Reader G-E1a — Knowledge Base अहवाल (report-only)", "",
         "> IS 2015–2021 (15m, NIFTY). MR = 20 बंद bars (चालू bar वगळून, KB भाग G). Weights / A ≥ 60 · B 45–59 · C < 45 — Abhi ने मंजूर, "
         "tuning नाही. VL (futures volume) आणि VX (VIX) ला IS मध्ये data नाही ⇒ 0 (त्यांचं मूल्य फक्त PAPER scorecard मधून).", "",
         "## 1. MR-आधारित आकड्यांचं calibration (बदल नाही — Abhi चा निर्णय)", "",
         f"- MR20 ÷ ATR14 (p10 / p50 / p90): {c['mr20_over_atr14']} · MR20 ÷ median-50: {c['mr20_over_med50']}", "",
         f"### (a) Equal highs / lows tolerance (सध्या {CS.DEFAULTS['eq_tol_mr']} MR)", "",
         f"Same-kind pivot जोड्या: {c['equal_pools']['pairs']} · जवळच्या जोडीचं अंतर (p10 / p25 / p50, MR): "
         f"{c['equal_pools']['dist_quantiles_mr']} · baseline (अंतर > 1 MR) retest वर reject: {c['equal_pools']['baseline_far_pivots_reject_pct']}%", "",
         "| tol (MR) | equal partner असलेले pivots % | pool retests | retest वर reject % |", "|---|---|---|---|"]
    L += [f"| {r['tol_mr']} | {r['pivots_with_equal_partner_pct']} | {r['pools_retested']} | {r['reject_pct']} |" for r in c["equal_pools"]["by_tol"]]
    L += ["", f"### (b) Sweep खोली (सध्या {CS.DEFAULTS['sweep_min_mr']}–{CS.DEFAULTS['sweep_max_mr']} MR)", "",
          "Confirmed swing pivot च्या पलीकडची पहिली wick. Reclaim = त्याच / पुढच्या 2 bars पैकी close परत आत. यश = reclaim नंतर 20 bars मध्ये "
          "pivot ± 1 MR आत, sweep चं टोक तुटण्याआधी.", "",
          "| खोली (MR) | n | reclaim % | reclaim नंतर यश % |", "|---|---|---|---|"]
    L += [f"| {r['depth_mr']} | {r['n']} | {r['reclaim_pct']} | {r['success_after_reclaim_pct']} |" for r in c["sweep_depth"]]
    L += ["", f"### (c) Fibonacci band (सध्या ± {CS.DEFAULTS['fib_band_mr']} MR)", "",
          f"Impulse (≥ {CS.DEFAULTS['fib_min_impulse_mr']} MR) नंतरचे pullbacks: {c['fib_band']['pullbacks']}. जवळच्या 38.2/50/61.8/78.6 पासून "
          "अंतर ≤ band, विरुद्ध uniform retrace (null).", "", "| band (MR) | pullback टोकं band मध्ये % | uniform null % |", "|---|---|---|"]
    L += [f"| ± {r['band_mr']} | {r['within_pct']} | {r['uniform_null_pct']} |" for r in c["fib_band"]["by_band"]]
    d = res["distribution"]
    L += ["", "## 2. IS grade वितरण (pullback-end उमेदवार, पूर्ण evaluate, Elliott सह)", "",
          f"उमेदवार: {res['n_candidates']} (scan {res['scan_sec']} s) · नमुना {d['n']} · grade %: {d['grade_pct']} · entries {d['entries']} · "
          f"व्हेटो {d['vetoed']} {d['veto_counts']}", "", f"Total (p10 / p25 / p50 / p75 / p90): {d['total_quantiles']}", "",
          "| प्रकार | n | A % | B % | C % | entries |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {v['n']} | {v['A']} | {v['B']} | {v['C']} | {v['entries']} |" for k, v in d["by_type"].items()]
    L += ["", "सरासरी गुण: " + " · ".join(f"{k} {v:+g}" for k, v in d["mean_points"].items()), ""]
    rd = res["reversal_day"]
    L += [f"## 3. स्पष्ट reversal दिवस {rd['day']} (अपेक्षित: bull put बाजूला C / entry नाही)", "",
          f"bull put बाजूचे bars {rd['n_side']} · grades {rd['grades_side']} · entries {rd['entries_side']}", "",
          "| वेळ | बाजू | grade | total | PB | entry | व्हेटो / कारण |", "|---|---|---|---|---|---|---|"]
    L += [f"| {x['asof']} | {x['side']:+d} | {x['grade']} | {x['total']} | {x['pb']} | {'हो' if x['entry'] else 'नाही'} | "
          f"{'; '.join(x['vetoes'] or x['why'])[:120]} |" for x in rd["rows"]]
    gd = res.get("golden")
    L += ["", "## 4. 7 Oct 2026 golden (contaminated, illustration only; अपेक्षित A)", ""]
    if gd is None:
        L.append("**Data अजून नाही:** `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz` — VPS export block चालल्यावर हा अहवाल पुन्हा.")
    else:
        L += [f"- {gd['asof']} · grade **{gd['grade']}** ({gd['total']}) · entry {'हो' if gd['entry'] else 'नाही'}", ""] + \
             [f"  - {x}" for x in gd["lines"]] + ["", "Story:", ""] + [f"  - {x}" for x in gd["story"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=400)
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA", "/home/user/trade-data"))
    a = ap.parse_args(argv)
    s = CS.load()
    m1 = DP.load_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"), "research")
    m1 = m1[m1["timestamp"] < DP._IS_END_X].reset_index(drop=True)
    trig = EV.frame(m1, "15m", m1["timestamp"].iloc[-1] + pd.Timedelta(minutes=1))
    res = {}
    t0 = time.time()
    res["calibration"] = calibration(trig, s)
    res["calib_sec"] = round(time.time() - t0, 1)
    t0 = time.time()
    cands = candidates(trig, s)
    res["n_candidates"], res["scan_sec"] = len(cands), round(time.time() - t0, 1)
    t0 = time.time()
    res["distribution"] = distribution(m1, cands, s, a.sample)
    res["dist_sec"] = round(time.time() - t0, 1)
    res["reversal_day"] = day_check(m1, "2018-02-02", s, side_want=1)
    res["golden"] = golden(os.path.join(a.trade_data, "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"), s)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(res, open(OUT_JSON, "w"), ensure_ascii=False, default=str, indent=1)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w").write(_md(res))
    print(json.dumps({k: v for k, v in res.items() if k not in ("distribution", "reversal_day", "calibration")} |
                     {"grade_pct": res["distribution"]["grade_pct"], "entries": res["distribution"]["entries"],
                      "rev_day": res["reversal_day"]["grades_side"]}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
