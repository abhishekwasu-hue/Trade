"""
research/elliott_counts_report.py — Elliott E1b: count engine चं वर्णन (फक्त IS; tuning नाही)
--------------------------------------------------------------------------------------------
🎓 Default settings वर NIFTY spot (IS 2015–2021) — दर `--every` बंद 5m bars नी snapshot: प्रत्येक degree वर
  • count नसलेले snapshots (gray कारण "count नाही"), vote स्पष्ट (≥ vote_min) असलेले snapshots, वर/खाली वाटा
  • preferred count चा pattern / चालू wave (top 8)
  • invalidation log: कुठल्या नियमाने counts मेले
हेतू: engine sane आहे का (सगळीकडे gray नाही, एकाच दिशेला झुकलेला नाही) — edge चा दावा नाही; तो E4 मध्ये.

    python3 research/elliott_counts_report.py [--every 6]     → docs/reports/elliott_e1b_counts.md
"""
import argparse
import collections
import os
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import counts as C  # noqa: E402
from elliott import data_policy as DP  # noqa: E402
from elliott import settings as S  # noqa: E402
from elliott import swings as W  # noqa: E402

OUT = os.path.join(ROOT, "docs", "reports", "elliott_e1b_counts.md")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=6)
    a = ap.parse_args(argv)
    d = DP.load_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))                # F11: holdout files नकार + filter
    d = DP.filter_allowed(d, "research")
    d = d[d["timestamp"] <= DP.IS_END].reset_index(drop=True)
    s = S.DEFAULTS
    md = W.multi_degree(d, s)
    eng = C.CountEngine(md, s)
    ts = md[0]["frame"]["bar_end"].iloc[500::a.every]
    st = {k: collections.Counter() for k in md}
    pref = {k: collections.Counter() for k in md}
    t0 = time.time()
    for t in ts:
        sn = eng.snapshot(t)
        for k, v in sn.degrees.items():
            c = st[k]
            c["n"] += 1
            c["empty"] += not v.nodes
            c["clear"] += not v.gray
            c["up"] += (not v.gray) and v.vote_up >= s["vote_min"]
            c["down"] += (not v.gray) and v.vote_down >= s["vote_min"]
            if v.preferred is not None:
                pref[k][f"{v.preferred.pattern}/{v.preferred.current_wave}"] += 1
    sec = (time.time() - t0) / max(len(ts), 1)
    inv = collections.Counter((e["degree"], e["rule"]) for e in eng.log)
    L = [f"# Elliott E1b — count engine (NIFTY spot, IS 2015–2021, default settings, दर {a.every} × 5m bars snapshot)", "",
         f"Snapshots: {len(ts):,}; सरासरी {sec * 1000:.1f} ms/snapshot. फक्त वर्णन — edge चा दावा नाही (तो E4 मध्ये).", "",
         "| Degree | count नाही | vote स्पष्ट (≥ vote_min) | पुढे motive वर | पुढे motive खाली |", "|---|---|---|---|---|"]
    for k in sorted(st, reverse=True):
        c = st[k]
        n = max(c["n"], 1)
        L.append(f"| D{k} | {c['empty'] / n:.1%} | {c['clear'] / n:.1%} | {c['up'] / n:.1%} | {c['down'] / n:.1%} |")
    L += ["", "## Preferred count (pattern / चालू wave) — degree-निहाय top 8", ""]
    for k in sorted(pref, reverse=True):
        tot = max(sum(pref[k].values()), 1)
        L.append(f"- **D{k}:** " + ", ".join(f"{p} {v / tot:.0%}" for p, v in pref[k].most_common(8)))
    L += ["", "## Invalidation log (नियमानुसार)", "", "| Degree | नियम | counts मेले |", "|---|---|---|"]
    for (k, r), v in sorted(inv.items(), key=lambda x: (-x[0][0], -x[1])):
        L.append(f"| D{k} | {r} | {v:,} |")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
