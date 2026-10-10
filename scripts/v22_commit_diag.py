#!/usr/bin/env python3
"""🧭 v2.2 ⑥ DIAG (फक्त अहवाल, Q16 साठी): ③ ✔ असलेल्या प्रत्येक bar साठी commitment च्या प्रत्येक अटीचा निकाल (k = 1 / 2 merged) —
दिशा, body ≥ commit_body, मागच्या extreme / close पलीकडे close, level-बाजू, close तृतीयांश, उलट wick, वेळ-खिडकी. कोणती अट किती वेळा
अडवते ते मोजतो. Defaults बदलत नाही. Order / broker / AI call नाही.

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


INFO = ("beyond_extreme", "beyond_close")                            # माहिती; निर्णयाची अट = "beyond" (settings नुसार)


def conditions(A, t, d, lvl, s, k, tss=None):
    """एका (t, k) साठी अटी ⇒ dict (True = पास). i0 < 1 किंवा merged bar engine ने नाकारलेला (दुसरा दिवस / entry_start आधी) ⇒ None.
    "beyond" = settings चा `commit_beyond` (engine सारखा); beyond_extreme / beyond_close दोन्ही माहितीसाठी."""
    i0 = t - k + 1
    if i0 < 1:
        return None
    if k > 1 and tss is not None:
        t0, t1 = pd.Timestamp(tss[i0]), pd.Timestamp(tss[t])
        if t0.normalize() != t1.normalize() or t0.strftime("%H:%M") < s["entry_start"]:
            return None
    o, c = A["open"][i0], A["close"][t]
    h, lo = max(A["high"][i0:t + 1]), min(A["low"][i0:t + 1])
    rng = max(h - lo, 1e-9)
    body = (c - o) * d
    ext = A["high"][i0 - 1] if d == M.UP else A["low"][i0 - 1]
    pos = (c - lo) / rng if d == M.UP else (h - c) / rng
    opp = (h - max(o, c)) / rng if d == M.UP else (min(o, c) - lo) / rng
    bx, bc = (c - ext) * d > 0, (c - A["close"][i0 - 1]) * d > 0
    out = {"direction": body > 0, "body": body / rng >= float(s["commit_body"]),
           "beyond": bc if s["commit_beyond"] == "close" else bx, "beyond_extreme": bx, "beyond_close": bc, "level_side": (c >= lvl["lo"]) if d == M.UP else (c <= lvl["hi"]),
            "close_third": pos >= float(s["commit_close_frac"]), "opp_wick": body <= 0 or opp < body / rng}
    return {k: bool(v) for k, v in out.items()}                          # numpy bool ⇒ JSON मध्ये खरा true / false


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--data", nargs="*")
    ap.add_argument("--m15")
    ap.add_argument("--daily")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    m15, m1, daily = VC.load_inputs(a)
    V = E3.V22(m15, m1, daily)
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
        per_k = {k: conditions(A, t, d, lvl, V.s, k, tss) for k in range(1, int(V.s["commit_merge_max"]) + 1)}
        gate = lambda x: {kk: v for kk, v in x.items() if kk not in INFO}                     # noqa: E731
        best = max((gate(x) for x in per_k.values() if x), key=lambda x: sum(x.values()), default=None)
        if best:
            for key, ok in best.items():
                if not ok:
                    fail[key] = fail.get(key, 0) + 1
        rows.append({"ts": str(ts.iloc[t])[:16], "side": "bull put" if d == M.UP else "bear call", "window": V.s["entry_start"] <= hm < V.s["entry_end"],
                     "checklist6": r["checklist"]["⑥"], "per_k": per_k})
    out = {"symbol": a.symbol, "bars_step3_ok": len(rows), "blocking_counts_best_k": fail, "rows": rows}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"③ ✔ bars {len(rows)} · सर्वात जवळच्या k ला अडवणाऱ्या अटी: {json.dumps(fail, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
