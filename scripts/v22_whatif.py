#!/usr/bin/env python3
"""🧭 v2.2 WHAT-IF (फक्त अहवाल, Abhi च्या Q15 / Q16 निर्णयासाठी): तेच data, register मधले पर्याय एकेक बदलून funnel + setups + Abhi च्या
खुणा (E-days) — defaults बदलत नाही, thresholds फिरवत नाही. Holdout rows कधीच नाहीत (v22_check.load_inputs चे guard). Order / broker /
AI call नाही.

  python3 scripts/v22_whatif.py --symbol NIFTY --data <1m csv.gz> --out <report.json> [--from ..] [--to ..] [--moments YYYY-MM-DD ...]
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from decision3 import engine as E3  # noqa: E402
from scripts import v22_check as VC  # noqa: E402

# (नाव, overrides, कोणता प्रश्न) — फक्त register मध्ये नोंदलेले पर्याय
VARIANTS = (
    ("default", {}, "—"),
    ("daily_minor (जुना)", {"daily_trend_mode": "minor"}, "Q15 आधी"),
    ("daily_pivot_n=1", {"daily_pivot_n": 1}, "Q15 (ii) नाकारला"),
    ("daily_dc", {"daily_swing_method": "dc"}, "Q15 (iii) नाकारला"),
    ("commit_beyond=extreme", {"commit_beyond": "extreme"}, "Q16 आधी"),
)
STEPS = ("①", "②", "③", "④", "⑥", "⑦")
GATES = ("①", "②", "③", "⑥", "⑦")                                        # ④ = पुरावा (gate नाही) ⇒ "कुठे अडलं" मध्ये नाही


def summarize(rows, moments):
    fun = {k: {"ok": 0, "no": 0} for k in STEPS}
    for r in rows:
        for k in STEPS:
            v = r["checklist"][k][0]
            if v is not None:
                fun[k]["ok" if v else "no"] += 1
    setups = [{"ts": r["ts"][:16], "mark": r["mark"], "side": "bull put" if r["level"]["role"] == "support" else "bear call",
               "conviction": r["conviction"], "rr": (r["risk"] or {}).get("rr")} for r in rows if r["decision"] == "setup"]
    marks = {}
    for m in moments:
        day = pd.Timestamp(m).normalize()
        dr = [r for r in rows if pd.Timestamp(r["ts"]).normalize() == day]
        hit = [f"{r['ts'][11:16]} {r['mark']}" for r in dr if r["decision"] == "setup"]
        far = max(dr, key=lambda r: (sum(1 for k in STEPS if r["checklist"][k][0]), r["bar"]), default=None)
        stop = None
        if far is not None and not hit:
            stop = next((f"{k} {far['checklist'][k][1]}" for k in GATES if far["checklist"][k][0] is False), None) or far.get("why")
        marks[m] = {"setups": hit, "trend": None if far is None else far["daily_trend"], "stop": stop}
    trend = {}
    for r in rows:
        trend[r["daily_trend"]] = trend.get(r["daily_trend"], 0) + 1
    return {"funnel": fun, "setups": setups, "marks": marks, "trend": trend}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--data", nargs="*")
    ap.add_argument("--m15")
    ap.add_argument("--daily")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--moments", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    m15, m1, daily = VC.load_inputs(a)
    from swings2 import engine as SE
    res = SE.build(m15, m1)                                             # थर 1 एकदाच (variants मध्ये बदलत नाही)
    ts = pd.to_datetime(res["m15"]["timestamp"])
    lo = pd.Timestamp(a.frm) if a.frm else ts.min()
    hi = pd.Timestamp(a.to) + pd.Timedelta(days=1) if a.to else ts.max() + pd.Timedelta(days=1)
    bars = [i for i in range(len(ts)) if lo <= ts.iloc[i] < hi]
    out = {"symbol": a.symbol, "window": [str(lo.date()), str((hi - pd.Timedelta(days=1)).date())], "bars": len(bars), "variants": []}
    for name, ov, q in VARIANTS:
        V = E3.V22(m15, m1, daily, s=ov, res=res)
        sm = summarize(V.run(bars), a.moments)
        out["variants"].append({"name": name, "question": q, "overrides": ov, **sm})
        print(f"{name:22s} {q:16s} ①{sm['funnel']['①']['ok']:4d} ③{sm['funnel']['③']['ok']:4d} ④{sm['funnel']['④']['ok']:4d} "
              f"⑥{sm['funnel']['⑥']['ok']:4d} ⑦{sm['funnel']['⑦']['ok']:4d} setups {len(sm['setups'])} · "
              + " | ".join(f"{m[5:]}: {', '.join(v['setups']) or (v['stop'] or '—')[:40]}" for m, v in sm["marks"].items()), flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
