#!/usr/bin/env python3
"""🧭 PATTERN CHECK (थर 3, Abhi): शेवटच्या N trading days मध्ये थर 2 च्या K चा correction pattern — दिवस-अखेरीस आणि दिवसातले कमाल 3
महत्त्वाचे क्षण (preferred 'शेवटचा leg हजर' झाला, 'pattern पूर्ण, resumption' झाला, किंवा preferred बदलला). Abhi ✔ / ✘ देतो.

Code मध्ये तारीख नाही. Backtest नाही, vision नाही, order / broker call नाही. Output फक्त --out-dir (private trade-data
`review/patterns/<run_id>/`).

  python3 scripts/pattern_check.py --data <1m golden csv> [<1m illustration csv>] --out-dir <trade-data>/review/patterns/<run_id> \\
      --run-id <run_id> [--futures-dir <dir>] [--k 1=4,2=8] [--send]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from legs2 import measure as LM  # noqa: E402
from patterns2 import charts as PCH  # noqa: E402
from patterns2 import fold as PF  # noqa: E402
from patterns2 import report as PR  # noqa: E402
from patterns2 import settings as PS  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from pivots import settings as PVS  # noqa: E402
from scripts import leg_check as LGC  # noqa: E402
from scripts import swing_check as SC  # noqa: E402

KEY_STATES = ("final_leg_present", "complete_resuming")


def moments(f, bars, k):
    """दिवसातले महत्त्वाचे क्षण (क्रमाने, कमाल k): preferred बदलला, किंवा preferred ची अवस्था 'हजर' / 'resumption' झाली."""
    out = []
    p0 = f.out.get(bars[0] - 1, {}).get("pref") if bars else None              # आदल्या bar ची अवस्था (दिवसाचा पहिला bar सुद्धा क्षण होऊ शकतो)
    prev = (p0["id"], p0["state"]) if p0 else None
    for t in bars:
        r = f.out[t]
        p = r.get("pref")
        cur = (p["id"], p["state"]) if p else None
        changed = r.get("change") and r["change"].get("why") in ("challenger", "preferred invalid")
        if p and prev is not None and (changed or (p["state"] in KEY_STATES and prev[1] != p["state"])):
            out.append(t)
        prev = cur
        if len(out) >= k:
            break
    return out


def item_json(f1, f2, t):
    j1, j2 = PF.rec_json(f1.out[t], f1.ts), PF.rec_json(f2.out[t], f2.ts)
    for j, f in ((j1, f1), (j2, f2)):
        I = f.tr.I_at(t)
        if I is not None:
            j["I_full"] = {"origin": I["origin"].price, "origin_ts": str(I["origin"].ts), "end": I["end"].price, "end_ts": str(I["end"].ts)}
    return j1, j2, PF.position(f1, f2, t)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=PVS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--k", default="")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    m1 = SC.load_1m(a.data)
    print(f"1m rows {len(m1)} वाचले · engine बांधतो (काही मिनिटं)…", flush=True)
    m15 = PE.bars_15m(m1)
    kk = LGC.parse_k(a.k)
    res = PE.build(m15, m1, {"k": kk} if kk else None)
    lg = LM.build(res, LGC.load_futures(a.futures_dir))
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    os.makedirs(a.out_dir, exist_ok=True)
    if not days:
        SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "PATTERN CHECK", "unit": "क्षण", "items": []})
        return 0
    last = pd.Timestamp(m15[pd.to_datetime(m15["timestamp"]).dt.normalize() == days[-1]]["bar_end"].max())
    f2 = PF.Fold(lg, 2, last)
    f2.run()
    f1 = PF.Fold(lg, 1, last, parent=f2)
    f1.run()
    print("fold पूर्ण · charts बनवतो…", flush=True)
    ts = pd.to_datetime(m15["timestamp"])
    picks = []
    for d in days:
        bars = [t for t in range(f1.end + 1) if ts.iloc[t].normalize() == d]
        mm = moments(f1, bars, int(PS.DEFAULTS["moments_per_day"]))
        picks += [(d, t) for t in mm if t != bars[-1]] + [(d, bars[-1])]
    items, pages = [], []
    for n, (d, t) in enumerate(picks, 1):
        j1, j2, pos = item_json(f1, f2, t)
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        pngs = PCH.charts(res, f1, f2, t, j1, j2, pos)
        tag = f"{pd.Timestamp(d):%Y-%m-%d}"
        hm = f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        SC.write_json(os.path.join(cdir, f"{hm}_patterns.json"), {"asof": str(asof), "D1": j1, "D2": j2, "position": pos})
        cap = PCH.caption(n, len(picks), asof, j1, j2)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "pattern_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(PCH.pair(pngs))
        print(f"  {n}/{len(picks)} PATTERN CHECK ✓", flush=True)
    sens = {}
    for nm, ov in (("struct_r 0.18", {"struct_r": 0.18}), ("struct_r 0.3", {"struct_r": 0.3}), ("hysteresis 1.1", {"hysteresis": 1.1}),
                   ("hysteresis 1.3", {"hysteresis": 1.3})):
        g2 = PF.Fold(lg, 2, last, ov)
        g2.run()
        g1 = PF.Fold(lg, 1, last, ov, parent=g2)
        g1.run()
        sens[nm] = {1: g1, 2: g2}
    rows = PR.rows({1: f1, 2: f2}, days[0], last, sens)
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"from": str(days[0]), "to": str(last), "rows": rows,
                                                            "settings": f1.s, "k": res["settings"]["k"],
                                                            "changes": {"D1": f1.log, "D2": f2.log}})
    PC.pdf([LC_table(rows)] + pages, os.path.join(a.out_dir, "pattern_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "PATTERN CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)}")
    if a.send and items:
        from backtest_review import telegram as RT
        r = RT.send_document(os.path.join(a.out_dir, "pattern_check.pdf"), f"🧭 PATTERN CHECK · PDF ({len(days)} दिवस, {len(items)} क्षण) · "
                             "खाली प्रत्येक क्षणाचा album — ✔ / ✘ reply", a.run_id)
        print(f"Telegram PDF: {r}")
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


def LC_table(rows):
    from legs2 import charts as LC
    return LC.table_png(rows, "थर 3: correction patterns चं वर्णन (शेवटचा महिना; backtest नाही)")


if __name__ == "__main__":
    sys.exit(main())
