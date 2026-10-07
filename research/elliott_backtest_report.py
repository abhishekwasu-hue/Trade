"""
research/elliott_backtest_report.py — Elliott E4: IS backtest + baseline + golden regression → docs/reports/elliott_pullback_backtest.md
-------------------------------------------------------------------------------------------------------------------------------------
🎓 फक्त IS (weekly options काळ: 11 Feb 2019 → 31 Dec 2021; swings warm-up Oct 2018 पासून). VAL आणि holdout उघडत नाही (G2 नंतर
तुमच्या निवडीने). Signals एकदाच (Scanner), मग variants फक्त trading settings बदलून replay:
  A  default (spec §11/§14 जसं)
  B  निदान: credit guard बंद (c_min 0, min_credit 0) — model premium वर guard ~90% signals अडवतो; signal ची अर्थव्यवस्था दिसावी
  C  निदान: B + progress-time exit बंद
  "निदान" = pre-registered, निवड/tuning नाही. Baselines (spec §13 #1): त्याच exits (structure-free: emergency, premium stop,
  profit %, expiry) वर (i) EW entries आणि (ii) random entries (त्याच TTF, 09:30–14:45, तीच दिशा व strike अंतर; seed 7, 5 पट).
Premium: trade-data मध्ये options data नसेल तर **model premium** (BS, IV = 20 दिवस realized vol) — ठळक इशारा.

    python3 research/elliott_backtest_report.py [--start 2019-02-11] [--end 2021-12-31] [--quick]
"""
import argparse
import collections
import dataclasses
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import backtest as BT  # noqa: E402
from elliott import data_policy as DP  # noqa: E402
from elliott import golden as GD  # noqa: E402
from elliott import settings as S  # noqa: E402
from elliott.trigger import Scanner  # noqa: E402

OUT = os.path.join(ROOT, "docs", "reports", "elliott_pullback_backtest.md")
VARIANTS = {
    "A_default": {},
    "B_guard_off": {"c_min_by_dte": [0.0] * 5, "min_credit_pts": 0.0},
    "C_guard_off_no_progress": {"c_min_by_dte": [0.0] * 5, "min_credit_pts": 0.0, "progress_bars_mult": 0.0},
}


def summarize(df, sized_only=False):
    d = df[df["sized"]] if sized_only else df
    if d.empty:
        return {"n": 0}
    r = d["R"].dropna()
    k = max(1, int(np.ceil(len(r) * 0.05)))
    return {"n": len(d), "win%": (d["pnl"] > 0).mean() * 100, "R सरासरी": r.mean(), "R median": r.median(),
            "R mean/sd": r.mean() / r.std() if len(r) > 1 and r.std() > 0 else np.nan,
            "CVaR5% R": r.nsmallest(k).mean(), "₹ एकूण": d["pnl"].sum() if sized_only else np.nan,
            "₹ सरासरी": d["pnl"].mean(), "breach%": d["breach"].mean() * 100, "max-loss%": d["max_loss_hit"].mean() * 100,
            "hard-inv%": d["reason"].isin(["hard_inv", "parent_inv_cascade"]).mean() * 100,
            "n<30": "निष्कर्ष नाही" if len(d) < 30 else ""}


def fmt(v):
    if isinstance(v, (float, np.floating)):
        return "—" if not np.isfinite(v) else (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}")
    return str(v)


def table(rows, cols):
    L = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        L.append("| " + " | ".join(fmt(r.get(c, "")) for c in cols) + " |")
    return L


def grouped(df, key):
    out = []
    for g, d in df.groupby(key):
        row = {"गट": " / ".join(map(str, g)) if isinstance(g, tuple) else str(g), **summarize(d)}
        row["निष्कर्ष"] = "n < 30 — नाही" if row["n"] < 30 else ""
        out.append(row)
    return sorted(out, key=lambda r: -r["n"])


def random_replay(sigs, sc, start, end, reps=5, seed=7):
    """EW signals ची नक्कल random वेळी: त्याच TTF चा 09:30–14:45 मधला bar, तीच दिशा, तेच strike-अंतर (inv spot पासून तितकाच)."""
    rng = np.random.default_rng(seed)
    out = collections.defaultdict(list)
    pools = {}
    for tf, fr in sc.frames.items():
        be = fr["bar_end"]
        m = (be >= start) & (be <= end) & (be.dt.time >= pd.Timestamp("09:30").time()) & (be.dt.time <= pd.Timestamp("14:45").time())
        pools[tf] = np.flatnonzero(m.to_numpy())[:-1]
    n = 0
    for t, lst in sigs.items():
        for sg in lst:
            pool = pools[sg.ttf]
            for _ in range(reps):
                j = int(pool[rng.integers(len(pool))])
                fr = sc.frames[sg.ttf]
                tj = pd.Timestamp(fr["bar_end"].iloc[j])
                c = float(fr["close"].iloc[j])
                inv = c - sg.trade_dir * abs(sg.comp[3] - sg.hard_inv)
                n += 1
                out[tj].append(dataclasses.replace(sg, t=tj, ttf_idx=j, hard_inv=inv, alt_invs=[], parent_invs=[],
                                                   wave_start_ts=tj + pd.Timedelta(microseconds=n)))
    return dict(out)


def run_golden(s):
    p = GD.golden_csv()
    if p is None:
        return ["**Data नाही:** `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-06.csv.gz` अजून नाही (VPS export block चालायचा आहे). "
                "Checker (`elliott/golden.py`) आणि test तयार; data आल्यावर हाच script golden निकाल भरेल."]
    d = GD.load_golden(p)
    d = DP.filter_allowed(d, "golden")
    sc = Scanner(d, s)
    ts = [t for t in sc.times() if t.date() >= GD.GOLDEN_FROM]
    sigs = []
    for t in sc.times():
        out = sc.step(t)
        if t.date() >= GD.GOLDEN_FROM:
            sigs += out
    rows = GD.evaluate(sigs, reasons=sc.reasons)
    L = [f"Golden काळ ({len(ts):,} scan वेळा) — signals {len(sigs)}. CONTAMINATED काळ: फक्त regression, edge चा पुरावा नाही.", ""]
    L += table(rows, ["id", "level", "status", "setup", "detail"])
    fails = [r for r in rows if r["status"] == "FAIL"]
    L += ["", f"**FAIL: {len(fails)}** (must चुकले / must_not घेतले). FAIL चं कारण bot ची चूक की screenshot वाचनाची — वर तपशील; "
              "फक्त pass करण्यासाठी logic बदललेलं नाही."]
    return L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-02-11")
    ap.add_argument("--end", default=str(DP.IS_END.date()))
    ap.add_argument("--warmup", default="2018-10-01")
    ap.add_argument("--quick", action="store_true", help="फक्त A व B, random 2 पट (चाचणीसाठी)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if pd.Timestamp(a.start) < pd.Timestamp("2019-02-11"):
        raise SystemExit("--start 2019-02-11 आधी नाही: weekly options नव्हते (spec §13 — त्या काळात फक्त spot-structure चाचण्या)")
    end = min(pd.Timestamp(a.end) + pd.Timedelta("23:59:59"), DP.IS_END)
    DP.check_range(a.warmup, end, "research")
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    d = d[(d["timestamp"] >= a.warmup) & (d["timestamp"] <= end)]
    d = DP.filter_allowed(d, "research").reset_index(drop=True)
    entry_until = end - pd.Timedelta(days=7)                                       # split सीमेवर एका weekly expiry चं embargo
    s = S.DEFAULTS
    t0 = time.time()
    sc = Scanner(d, s)
    times = sc.times()
    sigs = BT.collect_signals(sc, times)
    t_sig = time.time() - t0
    shared = dict(scanner=sc, trade_from=a.start, entry_until=entry_until)
    proto = BT.Backtest(d, s, replay={}, **shared)
    common = dict(pricer=proto.pricer, cal=proto.cal, book=proto.book, **shared)
    n_sig = sum(len(v) for t, v in sigs.items() if t >= pd.Timestamp(a.start))
    res, skips = {}, {}
    for name, ov in VARIANTS.items():
        if a.quick and name.startswith("C"):
            continue
        bt = BT.Backtest(d, {**s, **ov}, replay=sigs, **common)
        bt.run(times)
        res[name] = bt.results()
        skips[name] = collections.Counter(x[1] for x in bt.skipped)
    ovB = VARIANTS["B_guard_off"]
    ew_sfe = BT.Backtest(d, {**s, **ovB}, replay=sigs, structure_free_exits=True, entry_filters=False, **common)
    ew_sfe.run(times)
    rnd = random_replay({t: v for t, v in sigs.items() if t >= pd.Timestamp(a.start)}, sc, pd.Timestamp(a.start), end,
                        reps=2 if a.quick else 5)
    rb = BT.Backtest(d, {**s, **ovB}, replay=rnd, structure_free_exits=True, entry_filters=False, **common)
    rb.run(times)
    sec = time.time() - t0

    L = [f"# Elliott Pullback Credit Spread — E4 backtest (NIFTY, IS {a.start} – {end.date()})", "",
         "> ⚠️ **Model premium.** trade-data मध्ये अजून options data (bhavcopy / Upstox expired) नाही. सगळे premiums "
         "**Black-Scholes, IV = आधीच्या 20 दिवसांचा realized vol** (उत्तर 4 (b)). Realized vol सहसा IV पेक्षा कमी ⇒ credit कमी दिसतो. "
         "₹ आकडे **अंदाज** आहेत; निर्णय R-multiples आणि तुलनांवरून, आणि खऱ्या data वर पुन्हा चालवल्यानंतरच.", "",
         f"Signals (E2) या काळात: **{n_sig}**. Scan + backtest वेळ {sec / 60:.1f} मि (signals {t_sig / 60:.1f} मि). "
         f"Settings hash `{sc.hash}`. Capital ₹{s['capital']:,.0f}, risk {s['risk_per_trade_pct']}% × tier (A 1.0 / B 0.5 / C 0.25).",
         "VAL (2022–Mar 2024) आणि holdout **उघडलेले नाहीत**.", "",
         "## 1. Variants — एकूण (सगळे trades: sized + shadow 1-lot)", "",
         "Shadow = default sizing वर 0 lot आलेले (Tier B/C — E3 शोध) पण R मोजण्यासाठी 1 lot ने simulate; ₹ एकूण फक्त sized trades चा.", ""]
    rows = []
    for name, df in res.items():
        rows.append({"variant": name, **summarize(df), "sized n": int(df["sized"].sum()) if len(df) else 0,
                     "₹ एकूण (sized)": summarize(df, True).get("₹ एकूण", np.nan) if len(df) else np.nan})
    L += table(rows, ["variant", "n", "sized n", "win%", "R सरासरी", "R median", "R mean/sd", "CVaR5% R", "breach%", "max-loss%",
                      "hard-inv%", "₹ एकूण (sized)", "n<30"])
    L += ["", "R mean/sd = प्रति-trade Sharpe-सारखं गुणोत्तर (वार्षिक नाही). hard-inv% मध्ये parent cascade सुद्धा. "
              f"शेवटचे 7 दिवस नवीन entries नाहीत (split embargo); data संपताना उघडे trades \"end_of_data\" ने बंद."]
    L += ["", "**Skip कारणं (signal → trade नाही):**", ""]
    for name, c in skips.items():
        L.append(f"- {name}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    L += ["", "## 2. Entry तुलना — त्याच exits (structure-free) वर EW वि. random (spec §13 baseline 1)", "",
          "दोन्ही guard बंद (variant B), exits: emergency, premium stop, profit %, expiry; **दोन्ही बाजूंना entry filters बंद** "
          "(max_open, daily loss, एक-trade-प्रति-setup) — सारखी तुलना. Random = त्याच TTF चे random bars (09:30–14:45), तीच दिशा व "
          f"strike-अंतर (inv पासून; spec चा 'same delta/DTE' नाही — फरक नोंद), {2 if a.quick else 5} पट, seed 7.", ""]
    L += table([{"entry": "Elliott (E2 signals)", **summarize(ew_sfe.results())}, {"entry": "Random", **summarize(rb.results())}],
               ["entry", "n", "win%", "R सरासरी", "R median", "R mean/sd", "CVaR5% R", "breach%", "max-loss%", "n<30"])
    for name, df in res.items():
        if df.empty:
            continue
        L += ["", f"## 3. {name} — setup × tier", ""]
        L += table(grouped(df, ["setup", "tier"]), ["गट", "n", "win%", "R सरासरी", "CVaR5% R", "breach%", "hard-inv%", "निष्कर्ष"])
        L += ["", f"### {name} — degree / DTE / वर्ष / exit कारण", ""]
        L += table(grouped(df, ["degree"]), ["गट", "n", "win%", "R सरासरी", "CVaR5% R", "breach%", "निष्कर्ष"])
        L += [""] + table(grouped(df, ["dte_b"]), ["गट", "n", "win%", "R सरासरी", "CVaR5% R", "breach%", "निष्कर्ष"])
        df = df.assign(year=pd.to_datetime(df["t"]).dt.year)
        L += [""] + table(grouped(df, ["year"]), ["गट", "n", "win%", "R सरासरी", "CVaR5% R", "निष्कर्ष"])
        rc = df["reason"].value_counts()
        L += ["", "Exit कारणं: " + ", ".join(f"{k} {v}" for k, v in rc.items()),
              f"Premium नसल्याने पुढे ढकललेले exits: {int(df['deferred'].sum())}."]
        L += ["", f"### {name} — spec §13 grid (setup × degree × tier × DTE)", ""]
        L += table(grouped(df, ["setup", "degree", "tier", "dte_b"]), ["गट", "n", "R सरासरी", "₹ सरासरी", "breach%", "निष्कर्ष"])
    L += ["", "## 4. Golden-file regression (25 Sep – 6 Oct 2026)", ""] + run_golden(s)
    L += ["", "## 5. वाचताना", "",
          "- n < 30 असलेल्या cells वर निष्कर्ष नाही (spec §13). Win rate > 60% **आणि** Sharpe > 2 दिसलं तर आधी bug शोधायचा.",
          "- Variants B/C निदानासाठी — VAL साठी ≤ 3 configurations **तुम्ही** निवडायच्या (G2).",
          "- खऱ्या premiums (bhavcopy) शिवाय c_min calibration करता येत नाही (spec §8)."]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
