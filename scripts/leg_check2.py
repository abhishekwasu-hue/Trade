#!/usr/bin/env python3
"""🧭 LEG CHECK v2.1 (थर 2, Abhi): थर 1 v2 (swings2) च्या pivots वर legs (भूमिका, स्वभाव, label) आणि D1 / D2 चे I आणि K.
शेवटचे N trading days — दिवस-अखेर + दिवसातले कमाल 3 महत्त्वाचे क्षण (I बदल / रद्द / CHoCH strict / cisd).

Code मध्ये तारीख नाही; backtest, vision, order / broker call नाही. Futures फक्त volume साठी. Output फक्त --out-dir (private trade-data
`review/legs2/<run_id>/`). पाठवणं VPS वरून (send_run); charts इथे बनवून push.

  python3 scripts/leg_check2.py --data <1m golden csv> [<1m illustration csv>] --out-dir <dir> --run-id <id> [--futures-dir <dir>]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from legs2 import charts as LC  # noqa: E402
from legs2 import charts2 as L2C  # noqa: E402
from legs2 import ik2 as LI  # noqa: E402
from legs2 import measure2 as M2  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from swings2 import engine as SE  # noqa: E402
from swings2 import settings as SS  # noqa: E402
from swings2 import structure as ST  # noqa: E402


def build_all(m15, m1, fut, smap=None):
    res = SE.build(m15, m1, m1_status_map=smap)
    struct, rr = ST.all_structure(res)
    lg = M2.build(res, fut, rr=rr)
    trk = {d: LI.Tracker(lg, struct, d) for d in lg["settings"]["ik_degrees"]}
    return res, struct, lg, trk


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=SS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--m1-status", default=None, help="थर 1 run चा stream.json (replay = live)")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    m1 = SC.load_1m(a.data)
    print(f"1m rows {len(m1)} वाचले · engine बांधतो…", flush=True)
    m15 = PE.bars_15m(m1)
    smap = None
    if a.m1_status:
        import json
        smap = {x["ts"]: x for x in json.load(open(a.m1_status, encoding="utf-8"))}   # status + 1m निर्णय
    fut = OLD.load_futures(a.futures_dir)
    print("futures volume: " + (f"{len(fut)} 5M rows" if fut is not None else "नाही (V तटस्थ)"), flush=True)
    res, struct, lg, trk = build_all(m15, m1, fut, smap)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    os.makedirs(a.out_dir, exist_ok=True)
    ts = pd.to_datetime(m15["timestamp"])
    picks = []
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks += [(d, b, why) for b, why in L2C.moments(trk, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(d, bars[-1], None)]
    items, pages = [], []
    for n, (d, t, why) in enumerate(picks, 1):
        pngs, sts = L2C.charts(lg, trk, t)
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        tag, hm = f"{pd.Timestamp(d):%Y-%m-%d}", f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H", "D"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        legs_json = {f"D{x}": [M2.leg_json(L) for L in M2.known(lg, x, asof)][-30:] for x in lg["settings"]["degrees"]}
        cur = {f"D{x}": (M2.leg_json(c) if (c := M2.current(lg, x, asof)) else None) for x in (1, 2)}
        SC.write_json(os.path.join(cdir, f"{hm}_legs.json"), {"asof": str(asof), "legs": legs_json, "current": cur,
                                                              "ik": {"D1": sts[1], "D2": sts[2]}})
        cap = L2C.caption(n, len(picks), asof, sts, why)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "leg_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(LC.grid3(pngs))
        print(f"  {n}/{len(picks)} LEG CHECK ✓", flush=True)
    t0 = int((ts.dt.normalize() >= days[0]).to_numpy().argmax()) if days else 0
    t1 = picks[-1][1] if picks else 0
    rows = L2C.rows(lg, trk, t0, t1) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"rows": rows, "register": L2C.register_rows(), "settings": lg["settings"],
                                                            "log": {f"D{d}": trk[d].log for d in trk}})
    PC.pdf([LC.table_png(rows, "थर 2 v2: legs + I / K (वर्णन; backtest नाही)"),
            LC.table_png(L2C.register_rows(), "थर 2: अंदाज register")] + pages, os.path.join(a.out_dir, "leg_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "LEG CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)}")
    if a.send and items:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
