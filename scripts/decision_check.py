#!/usr/bin/env python3
"""🧭 DECISION CHECK (थर 7, Abhi): थर 1–6 एकत्र ⇒ regime, gates, commitment candle, risk, grade, size, `decision` (PAPER / shadow).
शेवटचे N trading days — दिवस-अखेर + कमाल 3 क्षण (setup / gate बदल). Vision call इथे नाही (model + run_vision_budget Abhi ठरवतो).
Code मध्ये तारीख नाही; backtest, order / broker call नाही; live engine ला हात नाही. Output फक्त --out-dir (`review/decision2/<run_id>/`).

  python3 scripts/decision_check.py --data <1m golden csv> [<1m illustration csv>] --out-dir <dir> --run-id <id> [--futures-dir <dir>]
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from decision2 import charts as DC  # noqa: E402
from decision2 import context as DX  # noqa: E402
from decision2 import engine as DE  # noqa: E402
from legs2 import charts as LC  # noqa: E402
from legs2 import volume as LV  # noqa: E402
from patterns2 import charts as CH1  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from rsi2 import engine as RE  # noqa: E402
from rsi2 import layer as RL  # noqa: E402
from scripts import leg_check as OLD  # noqa: E402
from scripts import leg_check2 as L2  # noqa: E402
from scripts import pattern_check2 as P2  # noqa: E402
from scripts import swing_check as SC  # noqa: E402
from scripts import zone_check as Z4  # noqa: E402
from swings2 import settings as SS  # noqa: E402
from trendlines2 import engine as TE  # noqa: E402
from trendlines2 import layer as TL  # noqa: E402


def ext_rows(m15, events=None, vix_csv=None, macro_csv=None):
    """VIX / event / macro rows (known_at सह; फक्त size / नोंद). नसतील ⇒ रिकामे (NA नोंद)."""
    be = m15["bar_end"]
    ev = DX.event_bars(DX.load_events(events), m15["timestamp"]) if events else {}
    vix, jump = DX.vix_map(pd.read_csv(vix_csv) if vix_csv else None, be)
    macro = DX.macro_map(pd.read_csv(macro_csv) if macro_csv else None, be)
    return {"event_bars": ev, "vix": vix, "vix_jump": jump, "macro": macro}


def build_ctx(m15, m1, fut, t0, smap=None, extra=None):
    res, struct, lg, trk = L2.build_all(m15, m1, fut, smap)
    f1, f2 = P2.build_folds(lg, trk)
    bars = range(t0, len(m15))
    Z, L4 = Z4.build_zones(lg, struct, trk, f1, f2, bars)
    E = TE.Engine(lg, struct)
    L5 = TL.run(E, trk, f1, Z, L4, bars=bars)
    R = RE.RSI(lg, struct)
    L6 = RL.run(R, trk, f1, L4, bars=bars)
    exp = None
    if fut is not None:
        nm = LV.near_month(fut)
        exp = sorted({pd.Timestamp(x).normalize() for x in nm["expiry"].dropna().unique()}) if len(nm) else None
    return DE.Ctx(lg, struct, trk, f1, f2, Z, L4, L5, L6, ext={"expiries": exp, **(extra or {})})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=SS.DEFAULTS["run_days"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--m1-status", default=None, help="थर 1 run चा stream.json (replay = live)")
    ap.add_argument("--events", default=DX.EVENTS_PATH, help="event calendar yaml (added_on = known_at)")
    ap.add_argument("--vix-csv", default=None, help="India VIX 15M candles (timestamp, close) — private data")
    ap.add_argument("--macro-csv", default=None, help="macro rows (fetched_at, value −1…1) — private data")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--instrument", default=None, choices=INS.names(), help="index (default: TRADE_INSTRUMENT / NIFTY)")
    a = ap.parse_args(argv)
    INS.set_current(a.instrument)
    m1 = SC.load_1m(a.data)
    print(f"1m rows {len(m1)} वाचले · सगळे थर बांधतो…", flush=True)
    m15 = PE.bars_15m(m1)
    fut = OLD.load_futures(a.futures_dir)
    smap = None
    if a.m1_status:
        import json
        smap = {x["ts"]: x for x in json.load(open(a.m1_status, encoding="utf-8"))}   # status + 1m निर्णय
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]
    ts = pd.to_datetime(m15["timestamp"])
    t0 = int((ts.dt.normalize() >= days[0]).to_numpy().argmax()) if days else 0
    C = build_ctx(m15, m1, fut, t0, smap, ext_rows(m15, a.events, a.vix_csv, a.macro_csv))
    D = DE.run(C, range(t0, len(m15)))
    os.makedirs(a.out_dir, exist_ok=True)
    picks = []
    for d in days:
        bars = [i for i in range(len(m15)) if ts.iloc[i].normalize() == d]
        picks += [(d, b, why) for b, why in DC.moments(D, bars, int(SS.DEFAULTS["moments_per_day"]))] + [(d, bars[-1], None)]
    items, pages = [], []
    for n, (d, t, why) in enumerate(picks, 1):
        dec = D[t]
        pngs = DC.charts(C, dec, t)
        asof = pd.Timestamp(m15["bar_end"].iloc[t])
        tag, hm = f"{pd.Timestamp(d):%Y-%m-%d}", f"{ts.iloc[t]:%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H"):
            open(os.path.join(cdir, f"{hm}_{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{hm}_{tf}.png")
        SC.write_json(os.path.join(cdir, f"{hm}_decision.json"), {"asof": str(asof), "decision": dec})
        cap = DC.caption(n, len(picks), asof, dec, why)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|{tag}|{hm}", "kind": "decision_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(CH1.pair(pngs))
        print(f"  {n}/{len(picks)} DECISION CHECK ✓", flush=True)
    t1 = picks[-1][1] if picks else 0
    rows = DC.rows(D, t0, t1) if days else []
    SC.write_json(os.path.join(a.out_dir, "measures.json"), {"rows": rows, "register": DC.register_rows()})
    PC.pdf([LC.table_png(rows, "थर 7: निर्णय (वर्णन; backtest नाही; PAPER)"), LC.table_png(DC.register_rows(), "थर 7: अंदाज register")]
           + pages, os.path.join(a.out_dir, "decision_check.pdf"))
    SC.write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "DECISION CHECK", "unit": "क्षण", "items": items})
    print(f"दिवस {len(days)} · क्षण {len(items)} · setups {sum(1 for x in D.values() if x['decision'] == 'setup')}")
    if a.send and items:
        from backtest_review import telegram as RT
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
