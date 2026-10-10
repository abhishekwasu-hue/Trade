#!/usr/bin/env python3
"""🧭 RSI CHECK (थर 6, Abhi): pivot-based RSI divergence, Cardwell rsi_range, on_K / regular_in_K / at_impulse_end / cascade.
शेवटचे N trading days — दिवस-अखेर + कमाल 3 क्षण. Code मध्ये तारीख नाही; backtest, vision, order नाही. निर्णय थर 7.
Output फक्त --out-dir (private trade-data `review/rsi2/<run_id>/`).

  python3 scripts/rsi_check.py --data <1m golden csv> [<1m illustration csv>] --out-dir <dir> --run-id <id> [--futures-dir <dir>]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from legs2 import charts as LC  # noqa: E402
from patterns2 import charts as CH1  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from rsi2 import charts as RC  # noqa: E402
from rsi2 import engine as RE  # noqa: E402
from rsi2 import layer as RL  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import leg_check2 as L2  # noqa: E402
from scripts import pattern_check2 as P2  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from scripts import zone_check as Z4  # noqa: E402
from swings2 import settings as SS  # noqa: E402


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
    fut = OLD.load_futures(a.futures_dir)
    smap = None
    if a.m1_status:
        import json
        smap = {x["ts"]: x["m1_status"] for x in json.load(open(a.m1_status, encoding="utf-8"))}
    res, struct, lg, trk = L2.build_all(m15, m1, fut, smap)
    f1, f2 = P2.build_folds(lg, trk)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    ts = pd.to_datetime(m15["timestamp"])
    t0 = int((ts.dt.normalize() >= days[0]).to_numpy().argmax()) if days else 0
    Z, L4 = Z4.build_zones(lg, struct, trk, f1, f2, range(t0, len(m15)))
    R = RE.RSI(lg, struct)
    L6 = RL.run(R, trk, f1, L4, bars=range(t0, len(m15)))
    os.makedirs(a.out_dir, exist_ok=True)
    picks = []
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks += [(d, b, why) for b, why in RC.moments(L6, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(d, bars[-1], None)]
    items, pages = [], []
    for n, (d, t, why) in enumerate(picks, 1):
        r = L6[t]
        pngs = RC.charts(R, r, t)
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        tag, hm = f"{pd.Timestamp(d):%Y-%m-%d}", f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        SC.write_json(os.path.join(cdir, f"{hm}_rsi.json"), {"asof": str(asof), "layer": r, "divergences": R.known(t)[-10:]})
        cap = RC.caption(n, len(picks), asof, r, why)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "rsi_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(CH1.pair(pngs))
        print(f"  {n}/{len(picks)} RSI CHECK ✓", flush=True)
    t1 = picks[-1][1] if picks else 0
    rows = RC.rows(R, L6, t0, t1) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"rows": rows, "register": RC.register_rows()})
    PC.pdf([LC.table_png(rows, "थर 6: RSI divergence (वर्णन; backtest नाही)"), LC.table_png(RC.register_rows(), "थर 6: अंदाज register")]
           + pages, os.path.join(a.out_dir, "rsi_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "RSI CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)}")
    if a.send and items:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
