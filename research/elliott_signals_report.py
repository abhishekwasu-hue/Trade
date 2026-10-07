"""
research/elliott_signals_report.py — Elliott E2: entry signals चं वर्णन (फक्त IS; P&L/edge नाही — तो E4 मध्ये)
-----------------------------------------------------------------------------------------------------------
🎓 Default settings, NIFTY spot IS 2015–2021, दर बंद 5m bar ला scanner.step(t):
  • signals: setup × tier × दिशा × degree × trigger TF, वर्षनिहाय संख्या
  • entry का नाही झाली: degree-निहाय कारणे (gray, count नाही, A-end, B आत, T1–T7 …)
हेतू: logic sane आहे का (signals फार कमी/जास्त नाहीत, एकाच setup/दिशेला झुकलेले नाहीत) — tuning नाही.

    python3 research/elliott_signals_report.py [--start 2015-01-01] [--end 2021-12-31]   → docs/reports/elliott_e2_signals.md
"""
import argparse
import collections
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP  # noqa: E402
from elliott import settings as S  # noqa: E402
from elliott import trigger as TR  # noqa: E402

OUT = os.path.join(ROOT, "docs", "reports", "elliott_e2_signals.md")


def _table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=str(DP.IS_END.date()))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    d = DP.load_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))                # F11: holdout files नकार + filter
    d = DP.filter_allowed(d, "research")
    d = d[(d["timestamp"] >= a.start) & (d["timestamp"] <= min(pd.Timestamp(a.end) + pd.Timedelta("23:59:59"), DP.IS_END))]
    d = d.reset_index(drop=True)
    s = S.DEFAULTS
    sc = TR.Scanner(d, s)
    ts = sc.md[0]["frame"]["bar_end"].iloc[300:]
    t0 = time.time()
    sc.run(ts)
    sec = time.time() - t0
    sig = sc.signals
    days = d["timestamp"].dt.normalize().nunique()
    L = [f"# Elliott E2 — entry signals (NIFTY spot, IS {a.start} – {a.end}, default settings)", "",
         f"Structure bars: {len(ts):,}; trading days: {days:,}; signals: **{len(sig):,}** "
         f"({len(sig) / max(days, 1):.2f} प्रति दिवस); scan वेळ {sec / 60:.1f} मिनिटं ({sec / max(len(ts), 1) * 1000:.1f} ms/bar).",
         "फक्त वर्णन — P&L, win-rate किंवा edge चा दावा नाही (तो E4 backtest मध्ये, costs सह). Settings hash: "
         f"`{sc.hash}`.", "", "## Setup × tier × दिशा", ""]
    c = collections.Counter((x.setup, x.tier, x.direction) for x in sig)
    L += _table(["Setup", "Tier", "दिशा", "Signals"], [(k[0], k[1], k[2], v) for k, v in sorted(c.items(), key=lambda kv: -kv[1])])
    L += ["", "## Degree × trigger TF", ""]
    c = collections.Counter((x.degree, x.ttf) for x in sig)
    L += _table(["Degree", "TTF", "Signals"], [(f"D{k[0]}", k[1], v) for k, v in sorted(c.items())])
    L += ["", "## वर्षनिहाय", ""]
    c = collections.Counter((x.t.year, x.direction) for x in sig)
    yrs = sorted({k[0] for k in c})
    L += _table(["वर्ष", "bull_put", "bear_call"], [(y, c[(y, "bull_put")], c[(y, "bear_call")]) for y in yrs])
    L += ["", "## Composite candles (N) आणि score", ""]
    c = collections.Counter(x.n for x in sig)
    L += _table(["N", "Signals"], sorted(c.items()))
    if sig:
        sc_ = pd.Series([x.score for x in sig])
        L += ["", f"Rejection score: median {sc_.median():.2f}, 10–90% {sc_.quantile(.1):.2f}–{sc_.quantile(.9):.2f}. "
              f"Recount (§14 Q6) signals: {sum(x.recount for x in sig)}."]
    L += ["", "## Entry का नाही — degree-निहाय कारणे (प्रत्येक बंद 5m bar वर एक)", "",
          "कारणांचा अर्थ: `no_count` = त्या degree वर valid count नाही; `gray` = vote < vote_min; `next_not_motive` = पुढची wave "
          "corrective (A-end R4 / triangle आत); `inside_B_X_triangle` = parent च्या B/X/triangle आत; `not_ttf_close` = trigger TF "
          "चा bar अजून बंद नाही; `tf_bars_min` = wave अजून 8 candles पेक्षा लहान; `R4_legs` = correction मध्ये < 3 sub-legs; "
          "`T7_breakout` = close शेवटच्या sub-leg च्या origin पलीकडे; `T_*` = composite candle अटी (touch/reclaim/strength/score).", ""]
    c = collections.Counter((r[1], r[3]) for r in sc.reasons)
    per = collections.Counter(r[1] for r in sc.reasons)
    rows = []
    for dd in sorted(per):
        for (k, why), v in sorted(((k, v) for k, v in c.items() if k[0] == dd), key=lambda kv: -kv[1])[:14]:
            rows.append((f"D{dd}", why, f"{v:,}", f"{v / per[dd]:.1%}"))
    L += _table(["Degree", "कारण", "bars", "वाटा"], rows)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
