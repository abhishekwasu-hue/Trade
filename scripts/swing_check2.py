#!/usr/bin/env python3
"""🧭 SWING CHECK (थर 1 v2.1, Abhi): शेवटचे N trading days — दिवस-अखेर + दिवसातले कमाल 3 महत्त्वाचे क्षण (BOS / CHoCH / reversal /
range_break). एकच swing engine (`swings2/`) + market structure. Code मध्ये तारीख नाही; backtest, vision, order नाही.
Output फक्त --out-dir (private trade-data `review/swings2/<run_id>/`). पाठवणं VPS वरून (send_run), charts इथे बनवून push.

  python3 scripts/swing_check2.py --data <1m golden csv> [<1m illustration csv>] --out-dir <dir> --run-id <id> [--daily-history <csv>]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from legs2 import charts as LC  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from swings2 import charts as WC  # noqa: E402
from swings2 import engine as SE  # noqa: E402
from swings2 import report as SR  # noqa: E402
from swings2 import settings as SS  # noqa: E402
from swings2 import structure as ST  # noqa: E402

KEY = ("reversal", "CHoCH", "BOS", "range_break")                     # क्रम = महत्त्व (D1 आणि D2 दोन्ही)


def moments(struct, bars, k):
    """दिवसातले कमाल k क्षण: आधी महत्त्वाने (reversal > CHoCH > BOS > range_break; बरोबरीत D2 आधी), मग वेळेनुसार."""
    bs = set(bars)
    ev = [e for d in sorted(struct) for e in struct[d]["events"] if e["bar"] in bs and e["type"] in KEY and e["bar"] != bars[-1]]
    ev.sort(key=lambda e: (KEY.index(e["type"]), -e["degree"], e["bar"]))
    out, seen = [], set()
    for e in ev:
        if e["bar"] in seen:
            continue
        seen.add(e["bar"])
        out.append((e["bar"], e["type"]))
        if len(out) >= k:
            break
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=SS.DEFAULTS["run_days"])
    ap.add_argument("--daily-history", default=None)
    ap.add_argument("--m1-status", default=None, help="आधीच्या run चा stream.json (replay = live: त्यातलाच 1m_status)")
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
    res = SE.build(m15, m1, m1_status_map=smap)
    struct, rr = ST.all_structure(res)
    hist = SC.load_history(a.daily_history)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    os.makedirs(a.out_dir, exist_ok=True)
    SC.write_json(os.path.join(a.out_dir, "stream.json"), res["stream"])
    ts = pd.to_datetime(m15["timestamp"])
    picks = []
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks += [(d, b, why) for b, why in moments(struct, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(d, bars[-1], None)]
    items, pages = [], []
    for n, (d, t, why) in enumerate(picks, 1):
        pngs, sn = WC.charts(res, struct, t, hist, "क्षण" if why else "दिवस-अखेर")
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        tag, hm = f"{pd.Timestamp(d):%Y-%m-%d}", f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H", "D", "W"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        evs = {f"D{x}": [e for e in struct[x]["events"] if e["bar"] <= t][-12:] for x in struct}
        SC.write_json(os.path.join(cdir, f"{hm}_swings.json"), {"asof": str(asof), "degrees": {k: {kk: vv for kk, vv in v.items()}
                                                                                              for k, v in sn.items()}, "events": evs,
                                                                "m1_status": res["stream"][t]["m1_status"]})
        cap = WC.caption(n, len(picks), sn, struct, t, asof, why)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "swing_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(PC.grid(pngs))
        print(f"  {n}/{len(picks)} SWING CHECK ✓", flush=True)
    last = pd.Timestamp(m15["bar_end"].iloc[picks[-1][1]]) if picks else None
    rows = SR.rows(res, struct, days[0], last) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"from": str(days[0]) if days else None, "to": str(last), "rows": rows,
                                                            "register": SR.register_rows(), "notes": SS.NOTES,
                                                            "settings": res["settings"]})
    kpages = []
    for dk in days[-int(SS.DEFAULTS["k_compare_days"]):]:                          # k-तुलना शेवटचे 3 दिवस (थर 1 §5)
        asof = pd.Timestamp(m15[ts.dt.normalize() == dk]["bar_end"].max())
        for deg in (1, 2):
            kpages.append(WC.k_options_png(m15, m1, asof, deg, SS.K_OPTIONS[deg]))
    PC.pdf([LC.table_png(rows, "थर 1 v2: swings + market structure (वर्णन; backtest नाही)"),
            LC.table_png(SR.register_rows(), "थर 1: अंदाज register")] + pages + kpages, os.path.join(a.out_dir, "swing_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "SWING CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)}")
    if a.send and items:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
