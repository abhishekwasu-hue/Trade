"""patterns2/report.py — थर 3 §8 मोजमाप (वर्णन, backtest नाही; PDF चं पहिलं पान)."""
from collections import Counter

import numpy as np
import pandas as pd

from . import fold as PF


def _q(x):
    return "—" if not x else f"{np.percentile(x, 25):.2f} / {np.median(x):.2f} / {np.percentile(x, 75):.2f}"


def rows(folds, start, end, sens=None):
    """folds = {d: Fold}. sens = {नाव: {d: Fold}} ("अंदाज" मर्यादा बदलून) ⇒ day-end preferred बदलणारे दिवस."""
    out = []
    for d, f in sorted(folds.items()):
        bars = [t for t, r in f.out.items() if pd.Timestamp(start) <= pd.Timestamp(r["ts"]).normalize() <= pd.Timestamp(end)]
        recs = [f.out[t] for t in bars]
        agg = Counter(PF.STATE_MR.get(r["agg"], r["agg"]) for r in recs if r["phase"] == "k")
        fam = Counter(r["pref"]["family"] for r in recs if r.get("pref"))
        ratios = [r["ratio"] for r in recs if r.get("ratio")]
        t0 = bars[0] if bars else 0
        ch = [e for e in f.log if e["bar"] >= t0 and e["event"] in ("challenger ⇒ बदल", "preferred invalid ⇒ बदल")]
        ks = sorted({r["I"]["end_bar"] for r in recs if r.get("I") and r["phase"] == "k"})
        per_k = Counter()
        for e in ch:
            kk = max([k for k in ks if k <= e["bar"]], default=None)
            per_k[kk] += 1
        ext = sum(1 for e in f.log if e["bar"] >= t0 and e["event"] == "extension")
        coarse = sum(1 for r in recs for g in r.get("groups", []) if g["coarse"])
        st = Counter()
        pen = Counter()
        ends = day_ends(f, bars)
        for t in ends:
            r = f.out[t]
            if r.get("pref"):
                for x in r["pref"].get("structs", []):
                    st[f"{x['m1']} × {x['m2']}"] += 1
            for h in r.get("hyps") or []:
                for nm, m in h["lines"]:
                    if m < 1:
                        pen[nm.split(" ")[0].rstrip(":")] += 1
        sv = []
        for nm, fs in (sens or {}).items():
            g = fs.get(d)
            if g is None:
                continue
            diff = sum(1 for t in ends if _fam(f.out.get(t)) != _fam(g.out.get(t)))
            sv.append(f"{nm}: {diff}/{len(ends)}")
        out.append({"Degree": f"D{d}", "अवस्था (K bars)": "<br>".join(f"{k} {v}" for k, v in agg.most_common()) or "—",
                    "preferred patterns": "<br>".join(f"{PF.FAMILY_MR[k]} {v}" for k, v in fam.most_common()) or "—",
                    "ओळखता येत नाही": agg.get(PF.STATE_MR["none"], 0),
                    "K संख्या / preferred बदल": f"{len(ks)} / {len(ch)} (प्रति K: {', '.join(str(v) for v in per_k.values()) or '0'}; "
                                                f"extension {ext}; triple मोजत नाही — 'ओळखता येत नाही' मध्ये)",
                    "top1/top2 (q1/med/q3)": _q(ratios), "coarse bars": coarse,
                    "रचना माप1 × माप2": "<br>".join(f"{k} {v}" for k, v in st.most_common(8)) or "—",
                    "अंदाज sensitivity (बदललेले दिवस)": "<br>".join(sv) or "—",
                    "गुण-घट (guideline)": "<br>".join(f"{k} {v}" for k, v in pen.most_common(8)) or "—"})
    return out


def _fam(r):
    return None if not r or not r.get("pref") else (r["pref"]["family"], r["pref"]["kind"])


def day_ends(f, bars):
    out = {}
    for t in bars:
        out[pd.Timestamp(f.out[t]["ts"]).normalize()] = t
    return sorted(out.values())
