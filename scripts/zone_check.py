#!/usr/bin/env python3
"""🧭 ZONE CHECK (थर 4, Abhi): buyer / seller areas, liquidity, sweep / accept, ★, "K area मध्ये" आणि momentum re-emit.
शेवटचे N trading days — दिवस-अखेर + कमाल 3 क्षण. Code मध्ये तारीख नाही; backtest, vision, order नाही. निर्णय थर 7.
Output फक्त --out-dir (private trade-data `review/zones2/<run_id>/`).

  python3 scripts/zone_check.py --data <1m golden csv> [<1m illustration csv>] --out-dir <dir> --run-id <id> [--futures-dir <dir>]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from legs2 import charts as LC  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import leg_check2 as L2  # noqa: E402
from scripts import pattern_check2 as P2  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from swings2 import settings as SS  # noqa: E402
from zones2 import charts as ZC  # noqa: E402
from zones2 import engine as ZE  # noqa: E402
from zones2 import layer as ZL  # noqa: E402


def build_zones(lg, struct, trk, f1, f2, bars):
    Z = ZE.Zones(lg, struct, trk).run(snap_bars=bars)
    return Z, ZL.run(Z, f1, f2)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=SS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--m1-status", default=None)
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
    res, struct, lg, trk = L2.build_all(m15, m1, fut, smap)
    f1, f2 = P2.build_folds(lg, trk)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    ts = pd.to_datetime(m15["timestamp"])
    t0 = int((ts.dt.normalize() >= days[0]).to_numpy().argmax()) if days else 0
    print("zones fold…", flush=True)
    Z, L = build_zones(lg, struct, trk, f1, f2, range(t0, len(m15)))
    os.makedirs(a.out_dir, exist_ok=True)
    picks = []
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks += [(d, b, why) for b, why in ZC.moments(Z, L, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(d, bars[-1], None)]
    items, pages = [], []
    for n, (d, t, why) in enumerate(picks, 1):
        r = L[t]
        I = trk[1].I_at(t)
        pngs = ZC.charts(Z, t, r, None if I is None else I["end"].bar)
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        tag, hm = f"{pd.Timestamp(d):%Y-%m-%d}", f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H", "D"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        zmap = {z["id"]: z for z in Z.snap[t]}
        SC.write_json(os.path.join(cdir, f"{hm}_zones.json"), {"asof": str(asof), "layer": r,
                                                               "zones": [ZL.zone_json(z) for z in Z.snap[t]]})
        cap = ZC.caption(n, len(picks), asof, r, zmap, why)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "zone_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(LC.grid3(pngs))
        print(f"  {n}/{len(picks)} ZONE CHECK ✓", flush=True)
    t1 = picks[-1][1] if picks else 0
    rows = ZC.rows(Z, L, t0, t1) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"rows": rows, "register": ZC.register_rows(),
                                                            "events": [e for e in Z.events if e["bar"] >= t0]})
    PC.pdf([LC.table_png(rows, "थर 4: zones (वर्णन; backtest नाही)"), LC.table_png(ZC.register_rows(), "थर 4: अंदाज register")] + pages,
           os.path.join(a.out_dir, "zone_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "ZONE CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)}")
    if a.send and items:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
