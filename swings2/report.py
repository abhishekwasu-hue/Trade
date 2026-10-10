"""swings2/report.py — थर 1 §4 मोजमाप (वर्णन, backtest नाही) + अंदाज register (PDF चं पहिलं पान)."""
from collections import Counter

import numpy as np
import pandas as pd

from . import engine as SE
from . import settings as SS


def _q(x):
    return None if not len(x) else round(float(np.median(x)), 1)


def rows(res, struct, start, end):
    m15 = res["m15"]
    t = pd.to_datetime(m15["timestamp"])
    s = res["settings"]
    out = []
    counts = {}
    for d in SE.DEGREES:
        allp = res["pivots"][d]
        ps = [p for p in allp if pd.Timestamp(start) <= p.known_at <= pd.Timestamp(end)]
        counts[d] = len(ps)
        lb, ls = [], []
        for a, b in zip(allp, allp[1:]):
            if b in ps and not a.warmup and not b.warmup:
                lb.append(b.bar - a.bar)
                ls.append(abs(b.price - a.price) / b.sigma if b.sigma else np.nan)
        lag = [p.confirm_bar - p.bar for p in ps if not p.warmup]
        low = {(p.bar, p.kind, p.price) for p in res["pivots"][d - 1]} if d else None
        nest = sum(1 for p in allp if (p.bar, p.kind, p.price) not in low) if d else 0
        ev = Counter(e["type"] for e in struct.get(d, {}).get("events", []) if pd.Timestamp(start) <= pd.Timestamp(e["ts"]) <= pd.Timestamp(end))
        out.append({"Degree": f"D{d} (k {s['k'][d]:g})", "Pivots": len(ps), "Leg bars med": _q(lb), "Leg σ med": _q(ls), "Lag med": _q(lag),
                    "09:15 %": round(100.0 * sum(1 for p in ps if t.iloc[p.bar].strftime("%H:%M") == "09:15") / len(ps), 1) if ps else None,
                    "same-bar 1m / सावध %": (f"{100.0 * sum(p.rule == '1m' for p in ps) / len(ps):.1f} / "
                                              f"{100.0 * sum(p.rule == 'conservative' for p in ps) / len(ps):.1f}") if ps else "—",
                    "nesting उल्लंघन": nest, "gap legs": sum(p.gap_leg_theta for p in ps),
                    "घटना": "<br>".join(f"{k} {v}" for k, v in ev.most_common()) or "—"})
    if 1 in struct and 2 in struct:
        bars = [i for i in range(len(m15)) if pd.Timestamp(start) <= t.iloc[i] <= pd.Timestamp(end)]
        both = [(struct[1]["states"][i]["trend"], struct[2]["states"][i]["trend"]) for i in bars]
        known = [(a, b) for a, b in both if a not in ("unknown",) and b not in ("unknown",)]
        agree = round(100.0 * sum(a == b for a, b in known) / len(known), 1) if known else None
        out.append({"Degree": "D1–D2 trend एकमत %", "Pivots": agree})
        for d in (1, 2):                                                     # Abhi उत्तर 1: RANGE% D1 आणि D2 वेगळे (threshold फिरवत नाही)
            rng = round(100.0 * sum(struct[d]["states"][i]["trend"] == "RANGE" for i in bars) / len(bars), 1) if bars else None
            out.append({"Degree": f"D{d} RANGE मध्ये bars %", "Pivots": rng})
    ks = [float(s["k"][d]) for d in SE.DEGREES if counts.get(d)]
    cs = [counts[d] for d in SE.DEGREES if counts.get(d)]
    if len(ks) >= 3:
        slope = float(np.polyfit(np.log(ks), np.log(cs), 1)[0])
        out.append({"Degree": "scaling: log(count) vs log(k) slope (DC ⇒ ≈ −2)", "Pivots": round(slope, 2)})
    return out


def register_rows():
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in SS.REGISTER.items()]
