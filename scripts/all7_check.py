#!/usr/bin/env python3
"""🧭 सातही थर (Abhi): थर 1–7 च्या मराठी खुणा एकाच chart वर — **दिवस-निहाय** folders (प्रत्येक दिवसाचं स्वतःचं manifest), म्हणजे VPS वरून
एका वेळी एकच दिवस पाठवता येतो (एकत्रित सगळं नाही). Charts / Telegram फक्त दाखवणं; order / broker नाही; code मध्ये तारीख नाही.
Output फक्त --out-dir (`review/all7/<run_id>/<YYYY-MM-DD>/`).

  python3 scripts/all7_check.py --data <1m csv> [<1m csv> …] --out-dir <dir> --run-id <id> [--days 22] [--futures-dir <dir>]
  VPS: python3 scripts/send_review_to_telegram.py --run review/all7/<run_id>/<YYYY-MM-DD>     (एक दिवस)
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from decision2 import charts as DC  # noqa: E402
from decision2 import charts7 as D7  # noqa: E402
from decision2 import engine as DE  # noqa: E402
from pivots import engine as PE  # noqa: E402
from scripts import decision_check as DCK  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from swings2 import settings as SS  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=SS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--m1-status", default=None, help="थर 1 run चा stream.json (replay = live)")
    a = ap.parse_args(argv)
    m1 = SC.load_1m(a.data)
    m15 = PE.bars_15m(m1)
    fut = OLD.load_futures(a.futures_dir)
    smap = None
    if a.m1_status:
        import json
        smap = {x["ts"]: x for x in json.load(open(a.m1_status, encoding="utf-8"))}
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    ts = pd.to_datetime(m15["timestamp"])
    t0 = int((ts.dt.normalize() >= days[0]).to_numpy().argmax()) if days else 0
    C = DCK.build_ctx(m15, m1, fut, t0, smap, DCK.ext_rows(m15))
    D = DE.run(C, range(t0, len(m15)))
    os.makedirs(a.out_dir, exist_ok=True)
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks = [(b, why) for b, why in DC.moments(D, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(bars[-1], None)]
        tag = f"{pd.Timestamp(d):%Y-%m-%d}"
        ddir = os.path.join(a.out_dir, tag)
        os.makedirs(ddir, exist_ok=True)
        items = []
        for n, (t, why) in enumerate(picks, 1):
            dec = D[t]
            pngs = D7.charts(C, dec, t)
            asof = pd.Timestamp(m15["bar_end"].iloc[t])
            hm = f"{ts.iloc[t]:%H%M}"
            files = []
            for tf in ("15M", "1H"):
                open(os.path.join(ddir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
                files.append(f"{hm}_{tf}.png")
            SC.write_json(os.path.join(ddir, f"{hm}_decision.json"), {"asof": str(asof), "decision": dec})
            cap = D7.caption(n, len(picks), asof, dec, why)
            items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "all7_check", "reading": cap, "caption": cap,
                          "files": files})
        SC.write_json(os.path.join(ddir, "manifest.json"), {"run_id": f"{a.run_id}/{tag}", "title": "सातही थर", "unit": "क्षण",
                                                            "items": items})
        print(f"  {tag}: {len(items)} क्षण ✓", flush=True)
    SC.write_json(os.path.join(a.out_dir, "days.json"), {"run_id": a.run_id, "days": [f"{pd.Timestamp(d):%Y-%m-%d}" for d in days]})
    print(f"दिवस {len(days)} · setups {sum(1 for x in D.values() if x['decision'] == 'setup')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
