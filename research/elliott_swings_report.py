"""
research/elliott_swings_report.py — Elliott E1a: degree-निहाय swings चं वर्णन (फक्त IS; tuning नाही)
-------------------------------------------------------------------------------------------------
🎓 Default settings (spec §11) वर NIFTY spot 5m चे D0–D3 swings वर्षानुसार: दिवसाला pivots, leg चा median आकार (points, bars),
आणि Similarity & Balance (Neely 1/3) पाळणाऱ्या शेजारी-जोड्यांचा दर. हेतू: degrees खरंच वेगळ्या "आकाराच्या" आहेत का आणि auto-TF
(8–40 candles) कुठल्या degree ला कुठला TF देईल याचा अंदाज. Calibration E4 मध्ये pre-registered grid ने, फक्त IS वर.

    python3 research/elliott_swings_report.py      → docs/reports/elliott_e1a_swings.md
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP  # noqa: E402
from elliott import settings as S  # noqa: E402
from elliott import swings as W  # noqa: E402

OUT = os.path.join(ROOT, "docs", "reports", "elliott_e1a_swings.md")


def main():
    d = DP.load_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))                # F11: holdout files नकार + filter
    d = DP.filter_allowed(d, "research")
    d = d[d["timestamp"] <= DP.IS_END].reset_index(drop=True)                 # फक्त IS
    s = S.DEFAULTS
    md = W.multi_degree(d, s)
    fr = md[0]["frame"]
    days_by_year = fr.groupby(fr["timestamp"].dt.year)["timestamp"].apply(lambda x: x.dt.date.nunique())
    rows = []
    for deg, v in md.items():
        conf = v["confirmed"]
        lg = W.legs_of(conf)
        yrs = np.array([a.ts.year for a, _, _, _ in lg])
        for y, n_days in days_by_year.items():
            sel = [x for x, yy in zip(lg, yrs) if yy == y]
            piv_y = [p for p in conf if p.ts.year == y]
            rows.append({"degree": f"D{deg}", "year": int(y), "pivots_per_day": len(piv_y) / n_days,
                         "median_pts": float(np.median([x[2] for x in sel])) if sel else np.nan,
                         "median_bars_5m": float(np.median([x[3] for x in sel])) if sel else np.nan,
                         "sb_rate": W.balance_rate(piv_y, s["similarity_balance_min"])})
    t = pd.DataFrame(rows)
    agg = t.groupby("degree").agg(pivots_per_day=("pivots_per_day", "mean"), median_pts=("median_pts", "median"),
                                  median_bars_5m=("median_bars_5m", "median"), sb_rate=("sb_rate", "mean"))
    lines = ["# Elliott E1a — degree-निहाय swings (NIFTY spot 5m, IS 2015–2021, default settings)", "",
             f"Settings: swing_mode={s['swing_mode']}, ATR({s['atr_len']}) पट {s['swing_atr_mult']}, S&B किमान {s['similarity_balance_min']:.3f}. "
             "फक्त वर्णन — tuning नाही (calibration E4 मध्ये, IS वर, pre-registered grid).", "",
             "## सारांश (वर्षांची सरासरी/median)", "", "| Degree | pivots/दिवस | leg median (pts) | leg median (5m bars) | Similarity & Balance दर |",
             "|---|---|---|---|---|"]
    for deg, r in agg.iterrows():
        lines.append(f"| {deg} | {r.pivots_per_day:.2f} | {r.median_pts:.0f} | {r.median_bars_5m:.0f} | {r.sb_rate:.2f} |")
    lines += ["", "## वर्षानुसार", "", "| Degree | वर्ष | pivots/दिवस | leg median (pts) | leg median (bars) | S&B |", "|---|---|---|---|---|---|"]
    for r in t.itertuples():
        lines.append(f"| {r.degree} | {r.year} | {r.pivots_per_day:.2f} | {r.median_pts:.0f} | {r.median_bars_5m:.0f} | {r.sb_rate:.2f} |")
    lines += ["", "**वाचन:** degree वाढली की swings कमी आणि मोठे व्हायला हवेत (हेच degrees वेगळे असल्याचं लक्षण). Leg median bars हे auto-TF चा "
              "अंदाज देतात: 8–40 bars मध्ये बसणारा TF तो degree वापरेल (उदा. ~4 bars ⇒ 5m वरही रचना दिसत नाही ⇒ D0 वर entry फक्त "
              "जेव्हा correction पुरेशी लांब)."]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:12 + len(agg)]))


if __name__ == "__main__":
    main()
