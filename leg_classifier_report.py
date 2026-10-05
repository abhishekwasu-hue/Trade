"""
leg_classifier_report.py
------------------------
🎓 T2.3 / G1 — Leg classifier चा अहवाल: NIFTY (offline 1M → 15M) वर IS-calibration (दोन आधीच ठरलेले grids), IS वि. VAL आकडे, लेबल-निहाय
पुढचे परिणाम, आणि G1 साठी 10 नमुना दिवस (IS मधून; holdout नाही) — प्रत्येकाचा legs-रंगीत चार्ट HTML (`--out`) मध्ये.
फक्त अहवाल; कुठलाही bot/डीफॉल्ट बदलत नाही.

    python3 leg_classifier_report.py --out /tmp/legs --report docs/reports/leg_classifier_g1.md --trials docs/reports/leg_calibration_trials.csv
"""
import argparse
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

import real_nifty_data
from price_action import leg_eval as E
from price_action import legs as L

TF = "15min"


def resample(df1m, rule=TF):
    """1M → rule (NSE 09:15 grid: 15M साठी 09:15 हा 15 च्या पटीत). timestamp = bar ची सुरुवात."""
    d = df1m.set_index("timestamp")[["open", "high", "low", "close"]]
    return d.resample(rule, label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()


def _md(df, cols=None):
    if df is None or not len(df):
        return "_(रिकामं)_\n"
    df = df[cols] if cols else df
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) or v is None else (f"{v:.3f}" if isinstance(v, float) else str(v)) for v in r.tolist()) + " |")
    return "\n".join(out) + "\n"


def day_chart(df15, legs, day, path):
    """एका दिवसाचा (+ मागचे 2 दिवस संदर्भ) legs-रंगीत चार्ट HTML."""
    from tradingview_chart import build_lightweight_chart_html
    ts = pd.to_datetime(df15["timestamp"])
    days = sorted(ts.dt.normalize().unique())
    i = days.index(pd.Timestamp(day))
    lo, hi = days[max(i - 2, 0)], days[i] + pd.Timedelta(days=1)
    idx = np.where((ts >= lo) & (ts < hi))[0]
    a, b = int(idx[0]), int(idx[-1])
    sub = df15.iloc[a:b + 1].reset_index(drop=True).assign(volume=0)
    shifted = []
    for lg in legs:
        if lg.start_bar >= a and lg.end_bar <= b and lg.known_at <= b:
            shifted.append(dataclasses.replace(lg, start_bar=lg.start_bar - a, end_bar=lg.end_bar - a, known_at=lg.known_at - a))
    html = build_lightweight_chart_html(sub, symbol="NIFTY", timeframe_label="15M", legs=L.chart_legs(sub, shifted, max_legs=200), height=560)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return shifted


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="legs_out")
    ap.add_argument("--report", default=None)
    ap.add_argument("--trials", default=None, help="सर्व calibration trials CSV (commit साठी)")
    a = ap.parse_args(argv)
    df = real_nifty_data.load_nifty_1min()
    if df.empty:
        print("❌ offline NIFTY डेटा सापडला नाही.")
        return 1
    d15 = resample(df)
    print(f"15M bars: {len(d15)} ({d15['timestamp'].min():%Y-%m-%d} → {d15['timestamp'].max():%Y-%m-%d})", flush=True)
    cal = E.calibrate(d15, log=lambda m: print(m, flush=True))
    ev = E.evaluate(d15, cal["cfg"])
    os.makedirs(a.out, exist_ok=True)
    trials = cal["trials"]
    trials.to_csv(a.trials or os.path.join(a.out, "leg_calibration_trials.csv"), index=False)
    days = E.sample_days(ev["outcomes"], n=10)
    sample_rows = []
    for day in days:
        path = os.path.join(a.out, f"legs_{pd.Timestamp(day):%Y-%m-%d}.html")
        shown = day_chart(d15, ev["legs"], day, path)
        labs = pd.Series([lg.label for lg in shown], dtype=object).value_counts().to_dict()
        sample_rows.append({"दिवस": f"{pd.Timestamp(day):%Y-%m-%d (%a)}", "legs (3 दिवसांत)": len(shown), "लेबल्स": ", ".join(f"{k} {v}" for k, v in labs.items())})
    print(f"नमुना दिवस: {[f'{pd.Timestamp(x):%Y-%m-%d}' for x in days]}", flush=True)
    if a.report:
        cfg = cal["cfg"]
        imp, pb = trials[trials["grid"] == "impulse"], trials[trials["grid"] == "pullback"]
        txt = ["# T2.1–T2.3 — Leg classifier: IS calibration आणि G1 नमुने (NIFTY 15M)\n",
               f"डेटा: `data/nifty50_1min.parquet` → 15M ({len(d15)} bars). IS = 2015→2021 (calibration फक्त इथे), VAL = 2022→2024-03 (फक्त दाखवणे). Sealed holdout वापरलेला नाही.",
               f"परिणाम-क्षितिज H = {E.HORIZON} bars (15M ⇒ 2 तास). fwd_mr = leg माहीत झाल्यापासून (confirm bar) H bars नंतरचा close-बदल, leg दिशेने, ÷ median_range.\n",
               "## 1. आधीच ठरलेले grids (प्रत्येकी 81) आणि निवड\n",
               f"- Impulse grid {E.IMPULSE_GRID} — उद्दिष्ट: STRONG वि. WEAK fwd_mr फरकाचा Welch t (STRONG वाटा {E.MIN_SHARE:.0%}–{E.MAX_STRONG_SHARE:.0%}).",
               f"  - निवड: **{cal['impulse_pick']}** · पात्र trials: {int(((imp['strong_share'] >= E.MIN_SHARE) & (imp['strong_share'] <= E.MAX_STRONG_SHARE)).sum())}/{len(imp)} · t ची रेंज {imp['t'].min():.2f} → {imp['t'].max():.2f}",
               f"- Pullback grid {E.PULLBACK_GRID} — उद्दिष्ट: HEALTHY वि. DANGEROUS resume दराचा z (दोन्ही वाटे ≥ {E.MIN_SHARE:.0%}).",
               f"  - निवड: **{cal['pullback_pick'] or 'एकही trial अट पूर्ण करत नाही ⇒ डीफॉल्ट ठेवले'}** · HEALTHY वाटा रेंज {pb['healthy_share'].min():.3f} → {pb['healthy_share'].max():.3f},"
               f" DANGEROUS {pb['danger_share'].min():.3f} → {pb['danger_share'].max():.3f}",
               f"- अंतिम LegConfig: `{dataclasses.asdict(cfg)}`\n",
               "## 2. IS वि. VAL (निवडलेल्या cfg ने, एकाच सलग चालवणीत)\n", _md(ev["summary"].T.reset_index().rename(columns={"index": "मापक", 0: "IS", 1: "VAL"})),
               "\n## 3. लेबलनिहाय पुढचे परिणाम\n", _md(ev["by_label"]),
               "\n## 4. G1 — 10 नमुना दिवस (IS, स्थिर seed; प्रत्येक लेबल किमान एकदा)\n", _md(pd.DataFrame(sample_rows)),
               "\nचार्ट: `--out` folder मधील `legs_YYYY-MM-DD.html` (गडद = impulse, फिकट = pullback, राखाडी = range, जांभळा = उलटफेर; hover वर features + कारण).\n",
               "## 5. निष्कर्ष\n", "_(`docs/WORK_LOG.md` मध्ये हाताने लिहिलेला.)_\n"]
        os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write("\n".join(txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
