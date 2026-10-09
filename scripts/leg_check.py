#!/usr/bin/env python3
"""🧭 LEG CHECK (थर 2, Abhi): शेवटच्या N trading days चे दिवस-अखेरचे charts — प्रत्येक leg ची भूमिका (R), स्वभाव (C, V), label, आणि
D1 / D2 वर I आणि K. Abhi ✔ / ✘ देतो.

Code मध्ये तारीख नाही ("शेवटचे N दिवस" = data मधले शेवटचे पूर्ण sessions). Backtest नाही, vision नाही, order / broker call नाही.
Output फक्त --out-dir (private trade-data `review/legs/<run_id>/`). Futures फक्त volume साठी.

  python3 scripts/leg_check.py --data <1m golden csv> [<1m illustration csv>] --out-dir <trade-data>/review/legs/<run_id> \\
      --run-id <run_id> [--futures-dir <oe_futures_5min_NIFTY*.parquet ची जागा>] [--k 1=4,2=8] [--send]
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP  # noqa: E402
from legs2 import charts as LC  # noqa: E402
from legs2 import ik as LI  # noqa: E402
from legs2 import measure as LM  # noqa: E402
from legs2 import report as LR  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from pivots import settings as PS  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from simple_core import count_source as CS  # noqa: E402


def load_futures(d):
    """Futures फक्त volume साठी; holdout काळाचा volume सुद्धा नाही (data-policy annotation)."""
    if not d:
        return None
    from chart_reader import volume as VL
    f = VL.load("NIFTY", d)
    return None if f is None else DP.filter_allowed(VL._naive_ist(f), "annotation")


def parse_k(txt):
    """'1=4,2=8' ⇒ {1: 4.0, 2: 8.0} (Abhi ची k निवड; नसेल ⇒ थर 1 चे defaults)."""
    if not txt:
        return {}
    out = {}
    for part in txt.split(","):
        a, b = part.split("=")
        out[int(a)] = float(b)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=PS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--k", default="", help="थर 1 चा k (Abhi ची निवड), उदा. 1=4,2=8")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    m1 = SC.load_1m(a.data)
    print(f"1m rows {len(m1)} वाचले · engine बांधतो (काही मिनिटं)…", flush=True)
    m15 = PE.bars_15m(m1)
    kk = parse_k(a.k)
    res = PE.build(m15, m1, {"k": kk} if kk else None)
    fut = load_futures(a.futures_dir)
    print("futures volume: " + (f"{len(fut)} 5M rows" if fut is not None else "नाही (V तटस्थ)"))
    lg = LM.build(res, fut)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    os.makedirs(a.out_dir, exist_ok=True)
    items, pages, last = [], [], None
    for n, d in enumerate(days, 1):
        asof = pd.Timestamp(m15[pd.to_datetime(m15["timestamp"]).dt.normalize() == d]["bar_end"].max())
        last = asof
        sts = {1: LI.state_at(lg, 1, asof), 2: LI.state_at(lg, 2, asof)}
        day_legs = [L for L in LM.known(lg, 1, asof) if pd.Timestamp(L["known_at"]).normalize() == pd.Timestamp(d)]
        sts["conflicts"] = sum(1 for L in day_legs if L["label"] in LM.CONFLICT_LABELS)
        pngs = LC.charts(lg, asof, sts)
        tag = f"{pd.Timestamp(d):%Y-%m-%d}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H", "D"):
            open(os.path.join(cdir, f"{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{tf}.png")
        legs_json = {f"D{x}": [LM.leg_json(L) for L in LM.known(lg, x, asof)] for x in lg["settings"]["degrees"]}
        cur = {f"D{x}": (LM.leg_json(c) if (c := LM.current(lg, x, asof)) else None) for x in (1, 2)}
        md, snap = CS.engine(m1, asof)                                           # §3.4: टप्पा B चा count फक्त तुलना म्हणून
        stage_b = CS.degrees_brief(snap) if md is not None else {"error": snap}
        SC.write_json(os.path.join(cdir, "legs.json"), {"asof": str(asof), "legs": legs_json, "current": cur,
                                                        "ik": {"D1": sts[1], "D2": sts[2]}, "stage_b_count_compare_only": stage_b})
        cap = LC.caption(n, len(days), asof, sts)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|day:{tag}", "kind": "leg_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(LC.grid3(pngs))
        print(f"  {n}/{len(days)} {tag} ✓", flush=True)                           # VPS वर progress दिसावा
    logs = {}
    for x in (1, 2):
        if last is not None:
            t = LI.Tracker(lg, x, last)
            t.run()
            logs[x] = [e for e in t.log if pd.Timestamp(m15["timestamp"].iloc[e["bar"]]).normalize() >= pd.Timestamp(days[0])]
    rows = LR.rows(lg, days[0], last, logs) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"from": str(days[0]) if days else None, "to": str(last), "rows": rows,
                                                            "settings": lg["settings"], "k": res["settings"]["k"]})
    PC.pdf([LC.table_png(rows, "थर 2: legs चं वर्णन (शेवटचा महिना; backtest नाही)")] + pages, os.path.join(a.out_dir, "leg_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "LEG CHECK", "unit": "दिवस", "items": items})
    print(f"दिवस {len(days)} · legs: " + ", ".join(f"{r['Degree']} {r['Legs']}" for r in rows))
    if a.send and items:
        from backtest_review import telegram as RT
        r = RT.send_document(os.path.join(a.out_dir, "leg_check.pdf"), f"🧭 LEG CHECK · PDF ({len(items)} दिवस) · खाली प्रत्येक दिवसाचा "
                             "album — ✔ / ✘ reply", a.run_id)
        print(f"Telegram PDF: {r}")
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
