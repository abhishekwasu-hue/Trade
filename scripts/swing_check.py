#!/usr/bin/env python3
"""🧭 SWING CHECK (थर 1, Abhi): शेवटच्या N trading days चे दिवस-अखेरचे charts — एकच DC swing engine (D0–D4). Abhi ✔ / ✘ देतो.

Code मध्ये तारीख नाही: "शेवटचे N दिवस" = data मध्ये (data-policy ने `annotation` purpose ला परवानगी असलेले) शेवटचे दिवस. Backtest नाही,
vision नाही, order / broker call नाही. Output फक्त --out-dir (private trade-data `review/swings/<run_id>/`).

  python3 scripts/swing_check.py --data <1m golden csv> [<1m illustration csv>] --out-dir <trade-data>/review/swings/<run_id> \\
      --run-id <run_id> [--daily-history <daily csv/parquet, फक्त दाखवायला>] [--k-options 3] [--send]
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from elliott import data_policy as DP  # noqa: E402
from pivots import charts as PC  # noqa: E402
from pivots import engine as PE  # noqa: E402
from pivots import settings as PS  # noqa: E402


def read(paths):
    paths = [paths] if isinstance(paths, str) else list(paths)
    raw = pd.concat([pd.read_parquet(p) if str(p).endswith(".parquet") else pd.read_csv(p, parse_dates=["timestamp"]) for p in paths],
                    ignore_index=True)
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    return raw.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)


def load_1m(paths):
    """Engine साठी: data-policy (annotation) — sealed holdout चा एकही row नाही. 1m data फक्त holdout instrument (NIFTY) चा आहे ⇒
    दुसरं instrument निवडलं असेल तर नकार (NIFTY data वर दुसरं नाव लागून holdout segment / पहारा बंद होऊ नये)."""
    if not INS.holdout():
        raise ValueError(f"1m data फक्त holdout instrument चा — {INS.label()} साठी TF csv (--tf-csv / mtf_check --tf-dir) वापरा")
    return DP.filter_allowed(read(paths), "annotation")


def load_history(path):
    """फक्त दाखवायला (display_only): जुन्या daily candles (holdout सह, Abhi ची परवानगी). चालू / अपूर्ण दिवस नाही (caller asof ने कापतो)."""
    if not path:
        return None
    d = read(path)
    d["timestamp"] = pd.to_datetime(d["timestamp"]).dt.normalize()
    return PC.display_only(d[["timestamp", "open", "high", "low", "close"]])


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True, default=str)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+", help="NIFTY 1m (golden + illustration files) — engine चा एकमेव input")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=PS.DEFAULTS["run_days"])
    ap.add_argument("--daily-history", default=None, help="जुन्या daily candles (फक्त Daily / Weekly chart वर राखाडी, display_only)")
    ap.add_argument("--k-options", type=int, default=0, help="पहिल्या run मध्येच द्या (उदा. 3): इतक्या दिवसांसाठी D1 / D2 चे तीन k शेजारी")
    ap.add_argument("--send", action="store_true", help="Telegram albums (VPS)")
    a = ap.parse_args(argv)
    m1 = load_1m(a.data)
    print(f"1m rows {len(m1)} वाचले · engine बांधतो (काही मिनिटं)…", flush=True)
    m15 = PE.bars_15m(m1)
    res = PE.build(m15, m1)
    hist = load_history(a.daily_history)
    full = PE.complete_sessions(m15)
    days = [d for d in sorted(full) if full[d]][-int(a.days):]                  # फक्त बंद झालेले sessions (अपूर्ण दिवस नाही)
    os.makedirs(a.out_dir, exist_ok=True)
    items, pages = [], []
    first = last = None
    for n, d in enumerate(days, 1):
        day_bars = m15[pd.to_datetime(m15["timestamp"]).dt.normalize() == d]
        asof = pd.Timestamp(day_bars["bar_end"].max())                      # दिवसाचा शेवटचा बंद candle
        first, last = first or asof, asof
        pngs, snap = PC.charts(res, asof, hist)
        tag = f"{pd.Timestamp(d):%Y-%m-%d}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        files = []
        for tf in ("15M", "1H", "D", "W"):
            open(os.path.join(cdir, f"{tf}.png"), "wb").write(pngs[tf])
            files.append(f"{tag}/{tf}.png")
        write_json(os.path.join(cdir, "swings.json"), {"asof": str(asof), "degrees": snap})
        cap = PC.caption(n, len(days), snap, asof)
        items.append({"n": n, "date": tag, "item": f"{a.run_id}|day:{tag}", "kind": "swing_check", "reading": cap, "caption": cap,
                      "files": files})
        pages.append(PC.grid(pngs))
        print(f"  {n}/{len(days)} {tag} ✓", flush=True)                           # VPS वर progress दिसावा
    rows = PE.measures(res, days[0], last) if days else []
    write_json(os.path.join(a.out_dir, "measures.json"), {"from": str(days[0]) if days else None, "to": str(last), "rows": rows,
                                                         "settings": {k: v for k, v in res["settings"].items()}})
    kpages = []
    if a.k_options and days:
        for d in days[-int(a.k_options):]:
            asof = pd.Timestamp(m15[pd.to_datetime(m15["timestamp"]).dt.normalize() == d]["bar_end"].max())
            for deg in (1, 2):
                b = PC.k_options_png(m15, m1, asof, deg, PS.K_OPTIONS[deg])
                fn = f"k_options/{pd.Timestamp(d):%Y-%m-%d}_D{deg}.png"
                os.makedirs(os.path.join(a.out_dir, "k_options"), exist_ok=True)
                open(os.path.join(a.out_dir, fn), "wb").write(b)
                kpages.append(b)
    PC.pdf([PC.table_png(rows, "थर 1: swings चं वर्णन (शेवटचा महिना; backtest नाही)")] + pages + kpages,
           os.path.join(a.out_dir, "swing_check.pdf"))
    write_json(os.path.join(a.out_dir, "manifest.json"), {"run_id": a.run_id, "title": "SWING CHECK", "unit": "दिवस", "items": items})
    print(f"दिवस {len(days)} · pivots: " + ", ".join(f"{r['degree']} {r['n']}" for r in rows))
    if a.send and items:
        from backtest_review import telegram as RT
        r = RT.send_document(os.path.join(a.out_dir, "swing_check.pdf"), f"🧭 SWING CHECK · PDF ({len(items)} दिवस) · खाली प्रत्येक दिवसाचा "
                             "album — ✔ / ✘ reply", a.run_id)
        print(f"Telegram PDF: {r}")
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
