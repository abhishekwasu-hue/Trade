#!/usr/bin/env python3
"""Degree निदान (फक्त मोजमाप; नियम नाही): प्रत्येक degree (D0–D4) चे k / σ, warm-up, confirmed pivots, आणि trend "unknown" राहण्याचं कारण
(कुठली अट अडते) — window मधल्या प्रत्येक 15M bar ला. Pivots-प्रति-आठवडा तक्ता + सारांश. Code मध्ये तारीख / किंमत नाही; window = CLI.

  python3 scripts/degree_diag.py --data <1m csv> [...] --out-dir <dir> [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--days N]
Output: degree_pivots.csv, degree_weeks.csv, degree_unknown_reasons.csv, degree_diag.json, degree_diag.md
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pivots import engine as PE  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from swings2 import engine as SE  # noqa: E402
from swings2 import settings as SS  # noqa: E402
from swings2 import structure as ST  # noqa: E402


def window(m15, start=None, end=None, days=None):
    """[t0, t1) 15M bar indices — --start/--end (समावेशक) नाहीतर शेवटचे --days पूर्ण sessions."""
    full = PE.complete_sessions(m15)
    alld = [d for d in sorted(full) if full[d]]
    if end:
        alld = [d for d in alld if pd.Timestamp(d) <= pd.Timestamp(end)]
    ds = [d for d in alld if pd.Timestamp(d) >= pd.Timestamp(start)] if start else alld[-int(days or SS.DEFAULTS["run_days"]):]
    day = pd.to_datetime(m15["timestamp"]).dt.normalize()
    sel = np.flatnonzero(day.isin(ds).to_numpy())
    return (int(sel[0]), int(sel[-1]) + 1, ds) if len(sel) else (0, 0, [])


def unknown_reason(ps):
    """trend_of ची अडलेली अट: non-warmup confirmed H / L (प्रत्येकी ≥ 2 हवे)."""
    nh = sum(1 for p in ps if p.kind == "H")
    nl = sum(1 for p in ps if p.kind == "L")
    if nh >= 2 and nl >= 2:
        return None
    if nh < 2 and nl < 2:
        return f"H {nh} आणि L {nl} (< 2)"
    return f"H {nh} (< 2)" if nh < 2 else f"L {nl} (< 2)"


def week_of(ts):
    return (ts - pd.Timedelta(days=ts.weekday())).normalize()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--days", type=int, default=None)
    a = ap.parse_args(argv)
    m1 = SC.load_1m(a.data)
    m15 = PE.bars_15m(m1)
    res = SE.build(m15, m1)
    t0, t1, ds = window(m15, a.start, a.end, a.days)
    ts = pd.to_datetime(m15["timestamp"])
    day = ts.dt.normalize()
    s = res["settings"]
    sig = np.array([res["sigma"].get(pd.Timestamp(x), np.nan) for x in day], float)
    degs = sorted(res["pivots"])
    struct, _ = ST.all_structure(res)                                            # D1/D2 चा खरा trend (Rhea RANGE सह) — review7 ① हाच वाचतो
    segs = np.array([res["segments"].get(pd.Timestamp(x)) for x in day])
    wk = (ts - pd.to_timedelta(ts.dt.weekday, unit="D")).dt.normalize().to_numpy()
    os.makedirs(a.out_dir, exist_ok=True)
    S = lambda t: str(ts.iloc[t])[:16]  # noqa: E731
    # pivots (data सुरुवातीपासून — warm-up दिसावा म्हणून)
    prow = [{"degree": f"D{d}", "kind": p.kind, "price": round(p.price, 2), "bar": S(p.bar), "confirm": S(p.confirm_bar),
             "warmup": bool(p.warmup), "eq": bool(p.eq), "theta_pts": round(float(s["k"][d]) * p.sigma, 1) if p.sigma else None}
            for d in degs for p in res["pivots"][d]]
    # प्रत्येक bar: trend + unknown कारण (degree-निहाय, window मध्ये)
    reasons = {d: Counter() for d in degs}
    runs = {d: [] for d in degs}
    known = {d: [] for d in degs}
    ptr = {d: 0 for d in degs}
    piv = {d: sorted([p for p in res["pivots"][d] if not p.warmup], key=lambda p: p.confirm_bar) for d in degs}
    pseg = {id(p): res["segments"].get(pd.Timestamp(p.ts).normalize()) for d in degs for p in piv[d]}
    for t in range(t1):
        for d in degs:
            while ptr[d] < len(piv[d]) and piv[d][ptr[d]].confirm_bar <= t:
                known[d].append(piv[d][ptr[d]])
                ptr[d] += 1
        if t < t0:
            continue
        for d in degs:
            ps = [p for p in known[d] if pseg[id(p)] == segs[t]]
            if not np.isfinite(sig[t]):
                why, tr = "σ नाही (σ warm-up)", "unknown"
            else:
                tr = struct[d]["states"][t]["trend"] if d in struct else ST.trend_of(ps)
                why = unknown_reason(ps) if tr == ST.UNK else None
            if why:
                reasons[d][why] += 1
            if not runs[d] or runs[d][-1][1] != tr:
                runs[d].append((S(t), tr))
    urow = [{"degree": f"D{d}", "कारण": k, "bars": v} for d in degs for k, v in reasons[d].most_common()]
    # आठवडे
    wrow = []
    for w in sorted(set(wk[:t1])):
        ti = np.flatnonzero(wk[:t1] == w)
        sg = [sig[t] for t in ti if np.isfinite(sig[t])]
        r = {"week_of": str(pd.Timestamp(w).date()), "range_pts": round(float(m15["high"].iloc[ti].max() - m15["low"].iloc[ti].min()), 1),
             "sigma15_median": round(float(np.median(sg)), 2) if sg else None}
        for d in degs:
            ps = [p for p in res["pivots"][d] if ti[0] <= p.confirm_bar <= ti[-1]]
            r[f"D{d}_all"] = len(ps)
            r[f"D{d}_nonwarmup"] = sum(1 for p in ps if not p.warmup)
            r[f"theta_D{d}_pts"] = round(float(s["k"][d]) * float(np.median(sg)), 1) if sg else None
        wrow.append(r)
    for nm, rws in (("degree_pivots.csv", prow), ("degree_weeks.csv", wrow), ("degree_unknown_reasons.csv", urow)):
        keys = list(dict.fromkeys(k for r in rws for k in r)) or ["—"]
        with open(os.path.join(a.out_dir, nm), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            [w.writerow(r) for r in rws]
    nb = t1 - t0
    summ = {"window": [str(pd.Timestamp(ds[0]).date()), str(pd.Timestamp(ds[-1]).date())] if ds else None, "bars_15m": nb,
            "first_sigma_bar": next((S(t) for t in range(len(sig)) if np.isfinite(sig[t])), None), "degrees": {}}
    lines = [f"# Degree निदान · {summ['window'][0]} – {summ['window'][1]} · {nb} bars (15M)" if ds else "# Degree निदान", ""]
    for d in degs:
        ps = res["pivots"][d]
        nw = [p for p in ps if not p.warmup]
        unk = sum(reasons[d].values())
        top = reasons[d].most_common(1)
        summ["degrees"][f"D{d}"] = {"k": s["k"][d], "warmup_sessions": s["warmup_sessions"][d], "pivots": len(ps), "nonwarmup": len(nw),
                                    "nonwarmup_H": sum(1 for p in nw if p.kind == "H"), "nonwarmup_L": sum(1 for p in nw if p.kind == "L"),
                                    "first_nonwarmup_confirm": S(min(p.confirm_bar for p in nw)) if nw else None,
                                    "unknown_bars": unk, "unknown_pct": round(100.0 * unk / nb, 1) if nb else None,
                                    "unknown_reasons": dict(reasons[d]), "trend_runs": runs[d]}
        lines.append(f"- **D{d}** (k {s['k'][d]} σ, warm-up {s['warmup_sessions'][d]} sessions): pivots {len(ps)} (non-warmup {len(nw)}: "
                     f"H {summ['degrees'][f'D{d}']['nonwarmup_H']}, L {summ['degrees'][f'D{d}']['nonwarmup_L']}); window मध्ये trend unknown "
                     f"{unk} / {nb} bars" + (f" — मुख्य कारण: {top[0][0]}" if top else ""))
    lines += ["", f"σ (15M) पहिला: {summ['first_sigma_bar']} (σ ला {s['sigma_sessions']} पूर्ण sessions). trend_of = शेवटचे 2 non-warmup H "
              "आणि 2 non-warmup L (त्याच segment मध्ये); EQ ⇒ RANGE."]
    json.dump(summ, open(os.path.join(a.out_dir, "degree_diag.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(a.out_dir, "degree_diag.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
