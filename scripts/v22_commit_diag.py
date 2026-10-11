#!/usr/bin/env python3
"""🧭 v2.2 ⑥ DIAG (फक्त अहवाल): ③ ✔ असलेल्या प्रत्येक bar साठी Q16 commitment निकाल — कोणता reversal form (grade A / B), वाट
(pullback-दिशेची / doji / inside), किंवा का नाही. Engine चंच `commitment` वापरतो (वेगळं गणित नाही). Order / broker / AI call नाही.

  python3 scripts/v22_commit_diag.py --symbol NIFTY --data <1m csv.gz> --out <json> [--from ..] [--to ..]
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from decision3 import engine as E3  # noqa: E402
from decision3 import method as M  # noqa: E402
from scripts import v22_check as VC  # noqa: E402


def explain(A, t, d, lvl, s, tss=None):
    """Q16: एका bar चा ⑥ निकाल engine च्याच `commitment` मधून + माहिती (close / extreme पलीकडे, form). रिटर्न dict."""
    ok, why, cm = M.commitment(A, t, d, lvl, s, tss)
    c, pc = float(A["close"][t]), float(A["close"][t - 1]) if t >= 1 else float("nan")
    ext = float(A["high"][t - 1] if d == M.UP else A["low"][t - 1]) if t >= 1 else float("nan")
    return {"ok": bool(ok), "why": why, "form": (cm or {}).get("form"), "grade": (cm or {}).get("grade"),
            "wait": (cm or {}).get("wait"), "beyond_close": bool((c - pc) * d > 0), "beyond_extreme": bool((c - ext) * d > 0)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--data", nargs="*")
    ap.add_argument("--m15")
    ap.add_argument("--daily", nargs="+")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    m15, m1, daily = VC.load_inputs(a)
    from decision3 import history as HI
    V = E3.V22(m15, m1, daily, sealed=HI.sealed_fn(a.symbol))
    ts = pd.to_datetime(V.m15["timestamp"])
    lo = pd.Timestamp(a.frm) if a.frm else ts.min()
    hi = pd.Timestamp(a.to) + pd.Timedelta(days=1) if a.to else ts.max() + pd.Timedelta(days=1)
    A = V.levels.A
    rows, fail = [], {}
    for t in [i for i in range(len(ts)) if lo <= ts.iloc[i] < hi]:
        r = V.decide(t)
        if not r["checklist"]["③"][0]:
            continue
        lvl = r["level"]
        d = M.UP if lvl["role"] == "support" else M.DOWN
        hm = ts.iloc[t].strftime("%H:%M")
        tss = V.m15["timestamp"].to_numpy()
        x = explain(A, t, d, lvl, V.s, tss)
        key = f"✔ {x['form']} ({x['grade']})" if x["ok"] else (f"वाट: {x['wait']}" if x["wait"] else x["why"])
        fail[key] = fail.get(key, 0) + 1
        rows.append({"ts": str(ts.iloc[t])[:16], "side": "bull put" if d == M.UP else "bear call", "window": V.s["entry_start"] <= hm < V.s["entry_end"],
                     "checklist6": r["checklist"]["⑥"], "decision": r["decision"], "explain": x})
    out = {"symbol": a.symbol, "bars_step3_ok": len(rows), "outcomes": fail, "rows": rows}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"③ ✔ bars {len(rows)} · ⑥ निकाल: {json.dumps(fail, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
