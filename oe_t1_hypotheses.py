"""
oe_t1_hypotheses.py
-------------------
🎓 T1 — निदान गृहीतकं H1–H5 (फक्त अहवाल; bot/डीफॉल्ट बदलत नाही). Opportunity Engine, V1 variant, खऱ्या offline NIFTY डेटावर.

डेटा विभाग (कायमचा): IS = 2015–2021 (निवड/tuning फक्त इथे) · Validation = 2022 → 2024-03 (फक्त दाखवणे, निवडीसाठी वापर नाही) ·
Sealed holdout (Upstox 2024-04 →) इथे **वापरत नाही** (G4 पर्यंत बंद).

Trials (आधीच ठरवलेला grid — 7 + H5 = 8 ≤ 81):
    BASE        — सध्याचे डीफॉल्ट
    H1          — D2 फक्त bias ∈ {LONG_ONLY, SHORT_ONLY}
    H3_020/025  — SL किमान अंतर 0.2 / 0.25 × ADR (डीफॉल्ट 0.1)
    H4a/H4b/H4c — D1 time stop: (a) नाही (b) 12 bars (c) OR-reentry exit (close परत OR च्या आत ⇒ exit)
    H5          — H1 + IS-सर्वोत्तम H3 + IS-सर्वोत्तम H4 (निवड नियम आधीच ठरलेला: IS दैनिक-R Sharpe; BASE पेक्षा चांगला नसेल तर तो भाग BASE)
H2 — BASE मधील D2: score bucket नुसार expectancy (घेतलेले + gate-rejected counterfactual), आणि LONG_ONLY bias मधले D2 candidates का नाकारले.
PBO (CSCV, S=16) आणि Deflated Sharpe — IS दैनिक R वर, सर्व trials मिळून.

    python3 oe_t1_hypotheses.py --out /tmp/t1 --report docs/reports/t1_hypotheses.md
"""
import argparse
import json
import os
import sys
import time
from dataclasses import replace

import numpy as np
import pandas as pd

import real_nifty_data
import research_stats as RS
from opportunity_engine import sessions
from opportunity_engine.backtest import IS_END, OOS_START, BacktestConfig, prepare_timeline, run_variant, summarize
from opportunity_engine.config import EngineConfig

VARIANT = "V1"
PERIOD_IS, PERIOD_VAL = "IS 2015→2021", "VAL 2022→2024-03"
TRIALS = {
    "BASE": {},
    "H1": {"d2_allowed_biases": ("LONG_ONLY", "SHORT_ONLY")},
    "H3_020": {"adr_min_frac": 0.2},
    "H3_025": {"adr_min_frac": 0.25},
    "H4a_none": {"d1_exit_rule": "none"},
    "H4b_12bars": {"d1_exit_rule": "bars", "d1_time_stop_bars": 12},
    "H4c_or_reentry": {"d1_exit_rule": "or_reentry"},
}
H3_KEYS, H4_KEYS = ("H3_020", "H3_025"), ("H4a_none", "H4b_12bars", "H4c_or_reentry")
SCORE_BINS = [-np.inf, 50, 60, 70, 80, np.inf]
SCORE_LABELS = ["<50", "50–60", "60–70", "70–80", "≥80"]


def split(df, col="date"):
    if df is None or len(df) == 0:
        return df, df
    d = pd.to_datetime(df[col])
    return df[d <= IS_END], df[d >= OOS_START]


def daily_r(trades, dates, col="r"):
    """सर्व trading दिवसांवर दैनिक R (ट्रेड नाही ⇒ 0) — PBO/DSR साठी एकसमान काळ-अक्ष."""
    s = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    if trades is not None and len(trades):
        g = trades.groupby(pd.to_datetime(trades["date"]))[col].sum()
        s = s.add(g.reindex(s.index).fillna(0.0), fill_value=0.0)
    return s


def trial_rows(name, knobs, res):
    rows = []
    for period, part in zip((PERIOD_IS, PERIOD_VAL), split(res["trades"])):
        for setup in ("ALL", "D1", "D2"):
            p = part if setup == "ALL" or part is None or not len(part) else part[part["setup"] == setup]
            rows.append({"trial": name, "period": period, "setup": setup, **summarize(p, "r"), "knobs": json.dumps({k: list(v) if isinstance(v, tuple) else v for k, v in knobs.items()}, ensure_ascii=False)})
    return rows


def pick_best(names, is_sharpe):
    """BASE सह उमेदवारांपैकी IS दैनिक Sharpe सर्वात जास्त — BASE जिंकला तर None (तो भाग बदलत नाही)."""
    best = max(("BASE",) + tuple(names), key=lambda n: is_sharpe[n])
    return None if best == "BASE" else best


def h2_tables(res):
    """H2: BASE मधले D2 — score bucket नुसार expectancy (real + virtual), आणि LONG_ONLY मधले D2 नकार."""
    out = {}
    frames = []
    for kind, df in (("घेतलेले", res["trades"]), ("gate-rejected (counterfactual)", res["virtual"])):
        if df is None or not len(df):
            continue
        d2 = df[df["setup"] == "D2"].copy()
        if not len(d2):
            continue
        d2["score_bucket"] = pd.cut(pd.to_numeric(d2["score"], errors="coerce"), SCORE_BINS, labels=SCORE_LABELS, right=False).astype(str)
        for period, part in zip((PERIOD_IS, PERIOD_VAL), split(d2)):
            for b, g in part.groupby("score_bucket"):
                frames.append({"प्रकार": kind, "period": period, "score": b, "bias": "सर्व", **summarize(g, "r")})
            for b, g in part.groupby("bias"):
                frames.append({"प्रकार": kind, "period": period, "score": "सर्व", "bias": b, **summarize(g, "r")})
    out["d2_score"] = pd.DataFrame(frames)
    dec = res["decisions"]
    rows = []
    if dec is not None and len(dec):
        d2 = dec[(dec["setup"] == "D2") & dec["bias"].astype(str).str.startswith("LONG_ONLY")]
        for period, part in zip((PERIOD_IS, PERIOD_VAL), split(d2)):
            for (bias, status), g in part.groupby(["bias", "status"]):
                first = g["reasons"].astype(str).str.split(" | ", regex=False).str[0].value_counts().head(3)
                rows.append({"period": period, "bias": bias, "status": status, "candidates": len(g), "दिवस": g["date"].nunique(),
                             "दिशा": ",".join(sorted(g["direction"].unique())), "मुख्य कारणं": " ; ".join(f"{k} ({v})" for k, v in first.items())})
    out["d2_long_only"] = pd.DataFrame(rows)
    return out


def _md(df):
    if df is None or not len(df):
        return "_(रिकामं)_\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) or v is None else str(v) for v in r.tolist()) + " |")
    return "\n".join(lines) + "\n"


def write_report(path, summary, h2, stats, choice, meta):
    show = summary[summary["setup"] == "ALL"][["trial", "period", "trades", "win_pct", "expectancy_r", "profit_factor", "total_r", "max_dd_r"]]
    by_setup = summary[summary["setup"] != "ALL"][["trial", "period", "setup", "trades", "win_pct", "expectancy_r", "total_r"]]
    txt = [f"# T1 — निदान गृहीतकं H1–H5 (Opportunity Engine, {VARIANT})\n",
           f"तयार: {meta['generated']} · डेटा: `data/nifty50_1min.parquet` ({meta['data_from']} → {meta['data_to']}) · दिवस: IS {meta['is_days']}, VAL {meta['val_days']}.",
           "R = साइज-विना (प्रति ट्रेड risk एककात), slippage सह. **फक्त अहवाल — कुठलाही डीफॉल्ट बदललेला नाही.** Sealed holdout वापरलेला नाही.\n",
           "## 1. सर्व trials — IS वि. Validation (V1, सर्व setups)\n", _md(show),
           "\n## 2. D1 / D2 वेगळे\n", _md(by_setup),
           "\n## 3. H5 निवड (फक्त IS वरून, नियम आधीच ठरलेला: IS दैनिक-R Sharpe; BASE पेक्षा चांगला नसेल तर तो भाग BASE)\n",
           f"- H3 निवड: **{choice['h3'] or 'BASE (बदल नाही)'}** · H4 निवड: **{choice['h4'] or 'BASE (बदल नाही)'}** · H5 knobs: `{choice['h5_knobs']}`\n",
           "\n## 4. Overfitting तपासणी (IS दैनिक R, सर्व trials)\n",
           f"- PBO (CSCV, S=16, {stats['pbo']['n_splits']} splits, N={stats['pbo']['N']} trials, T={stats['pbo']['T']} दिवस): **{stats['pbo']['pbo']}** (> 0.05 ⇒ निवड overfit मानावी)",
           f"- IS-सर्वोत्तम trial: **{stats['best']}** · Deflated Sharpe: SR={stats['dsr']['sr']} (दैनिक), अपेक्षित कमाल SR0={stats['dsr']['sr0']}, **DSR={stats['dsr']['dsr']}** (≥ 0.95 हवा)\n",
           "\n## 5. H2 — D2 score bucket / bias नुसार (BASE)\n", _md(h2["d2_score"]),
           "\n### LONG_ONLY bias मधले D2 candidates — status आणि मुख्य कारणं (BASE)\n", _md(h2["d2_long_only"]),
           "\n## 6. निष्कर्ष\n", "_(खालील भाग अहवाल वाचून हाताने लिहिला — `docs/WORK_LOG.md` पाहा.)_\n"]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(txt))


_TL = None          # fork workers साठी (copy-on-write; timeline एकदाच)


def _worker(args):
    name, bcfg = args
    t1 = time.time()
    return name, run_variant(_TL, VARIANT, bcfg), time.time() - t1


def run(frames, out, report=None, start=None, end=None, log=print, jobs=1):
    global _TL
    t0 = time.time()
    base_cfg = BacktestConfig(start=start, end=end, variants=(VARIANT,))
    tl = _TL = prepare_timeline(frames, base_cfg)
    dates = [pd.Timestamp(d.date) for d in tl.days]
    is_dates = [d for d in dates if d <= IS_END]
    log(f"timeline तयार: {len(dates)} दिवस ({time.time() - t0:.0f}s)")
    results, rows = {}, []

    def cfg_of(knobs):
        return replace(base_cfg, engine=replace(EngineConfig(), **knobs))

    def record(name, knobs, res, secs):
        results[name] = res
        rows.extend(trial_rows(name, knobs, res))
        log(f"  {name}: {len(res['trades'])} trades ({secs:.0f}s)")

    def run_trial(name, knobs):
        record(*(lambda r: (name, knobs, r[1], r[2]))(_worker((name, cfg_of(knobs)))))

    if jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(jobs) as pool:
            for name, res, secs in pool.imap(_worker, [(n, cfg_of(k)) for n, k in TRIALS.items()]):
                record(name, TRIALS[name], res, secs)
    else:
        for name, knobs in TRIALS.items():
            run_trial(name, knobs)
    is_daily = {n: daily_r(split(r["trades"])[0], is_dates) for n, r in results.items()}
    is_sharpe = {n: RS.sharpe(s) for n, s in is_daily.items()}
    h3, h4 = pick_best(H3_KEYS, is_sharpe), pick_best(H4_KEYS, is_sharpe)
    h5 = {**TRIALS["H1"], **(TRIALS[h3] if h3 else {}), **(TRIALS[h4] if h4 else {})}
    run_trial("H5", h5)
    is_daily["H5"] = daily_r(split(results["H5"]["trades"])[0], is_dates)
    is_sharpe["H5"] = RS.sharpe(is_daily["H5"])
    names = list(results)
    M = np.column_stack([is_daily[n].to_numpy() for n in names])
    pbo = RS.pbo_cscv(M, S=16)
    best = max(names, key=lambda n: is_sharpe[n])
    dsr = RS.deflated_sharpe(is_daily[best].to_numpy(), [is_sharpe[n] for n in names])
    summary = pd.DataFrame(rows)
    h2 = h2_tables(results["BASE"])
    os.makedirs(out, exist_ok=True)
    summary.to_csv(os.path.join(out, "t1_trials.csv"), index=False)
    for k, v in h2.items():
        v.to_csv(os.path.join(out, f"t1_{k}.csv"), index=False)
    for n, r in results.items():
        r["trades"].to_csv(os.path.join(out, f"t1_trades_{n}.csv"), index=False)
    stats = {"pbo": {k: v for k, v in pbo.items() if k != "logits"}, "best": best, "dsr": dsr,
             "is_daily_sharpe": {n: round(v, 4) for n, v in is_sharpe.items()}}
    choice = {"h3": h3, "h4": h4, "h5_knobs": json.dumps({k: list(v) if isinstance(v, tuple) else v for k, v in h5.items()}, ensure_ascii=False)}
    with open(os.path.join(out, "t1_stats.json"), "w", encoding="utf-8") as fh:
        json.dump({**stats, "choice": choice}, fh, ensure_ascii=False, indent=1, default=str)
    if report:
        meta = {"generated": pd.Timestamp.now().strftime("%Y-%m-%d"), "data_from": str(dates[0].date()) if dates else "-", "data_to": str(dates[-1].date()) if dates else "-",
                "is_days": len(is_dates), "val_days": len(dates) - len(is_dates)}
        write_report(report, summary, h2, stats, choice, meta)
    log(f"पूर्ण ({time.time() - t0:.0f}s). PBO={pbo['pbo']}, IS-सर्वोत्तम={best}, DSR={dsr['dsr']}")
    return {"summary": summary, "h2": h2, "stats": stats, "choice": choice, "results": results}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="t1_out")
    ap.add_argument("--report", default=None, help="Markdown अहवाल (उदा. docs/reports/t1_hypotheses.md)")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--jobs", type=int, default=1, help="समांतर trials (fork; Linux)")
    a = ap.parse_args(argv)
    df = real_nifty_data.load_nifty_1min()
    if df.empty:
        print("❌ offline NIFTY डेटा सापडला नाही (data/nifty50_1min.parquet).")
        return 1
    run(sessions.build_frames(df), a.out, a.report, a.start, a.end, log=lambda m: print(m, flush=True), jobs=a.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
