#!/usr/bin/env python3
"""🧭 PATTERN CHECK v2.1 (थर 3, Abhi): थर 2 v2 च्या K चा pattern, अवस्था आणि "momentum कमकुवत होतोय का" (12 लक्षणं).
शेवटचे N trading days — दिवस-अखेर + कमाल 3 महत्त्वाचे क्षण. Code मध्ये तारीख नाही; backtest, vision, order नाही. निर्णय थर 7.
Output फक्त --out-dir (private trade-data `review/patterns2/<run_id>/`).

  python3 scripts/pattern_check2.py --data <1m golden csv> [<1m illustration csv>] --out-dir <dir> --run-id <id> [--futures-dir <dir>]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from legs2 import charts as LC  # noqa: E402
from patterns2 import charts as CH1  # noqa: E402
from patterns2 import charts2 as PC2  # noqa: E402
from patterns2 import fold2 as F2  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import leg_check2 as L2  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from swings2 import settings as SS  # noqa: E402


def build_folds(lg, trk):
    f2 = F2.Fold(lg, trk[2])
    f2.run()
    f1 = F2.Fold(lg, trk[1], parent=f2)
    f1.run()
    return f1, f2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=SS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--m1-status", default=None)
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--instrument", default=None, choices=INS.names(), help="index (default: TRADE_INSTRUMENT / NIFTY)")
    a = ap.parse_args(argv)
    INS.set_current(a.instrument)
    m1 = SC.load_1m(a.data)
    print(f"1m rows {len(m1)} वाचले · engine बांधतो…", flush=True)
    m15 = PE.bars_15m(m1)
    smap = None
    if a.m1_status:
        import json
        smap = {x["ts"]: x for x in json.load(open(a.m1_status, encoding="utf-8"))}   # status + 1m निर्णय
    fut = OLD.load_futures(a.futures_dir)
    res, struct, lg, trk = L2.build_all(m15, m1, fut, smap)
    print("patterns fold (D2, D1)…", flush=True)
    f1, f2 = build_folds(lg, trk)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    os.makedirs(a.out_dir, exist_ok=True)
    ts = pd.to_datetime(m15["timestamp"])
    picks = []
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks += [(d, b, why) for b, why in PC2.moments(f1, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(d, bars[-1], None)]
    items, pages = [], []
    for n, (d, t, why) in enumerate(picks, 1):
        j1, j2 = PC2.item_json(f1, f2, t)
        pngs = PC2.charts(res, f1, f2, t, j1, j2)
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        tag, hm = f"{pd.Timestamp(d):%Y-%m-%d}", f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        SC.write_json(os.path.join(cdir, f"{hm}_patterns.json"), {"asof": str(asof), "D1": j1, "D2": j2})
        cap = PC2.caption(n, len(picks), asof, j1, j2, why)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "pattern_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(CH1.pair(pngs))
        print(f"  {n}/{len(picks)} PATTERN CHECK ✓", flush=True)
    t0 = int((ts.dt.normalize() >= days[0]).to_numpy().argmax()) if days else 0
    t1 = picks[-1][1] if picks else 0
    rows = PC2.rows({1: f1, 2: f2}, t0, t1) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"rows": rows, "register": PC2.register_rows(),
                                                            "log": {"D1": f1.log, "D2": f2.log}})
    PC.pdf([LC.table_png(rows, "थर 3 v2: patterns + momentum (वर्णन; backtest नाही)"),
            LC.table_png(PC2.register_rows(), "थर 3: अंदाज register")] + pages, os.path.join(a.out_dir, "pattern_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "PATTERN CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)}")
    if a.send and items:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
