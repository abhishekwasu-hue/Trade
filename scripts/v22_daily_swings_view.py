#!/usr/bin/env python3
"""🧭 v2.2 Daily swing review (Abhi): engine ने Daily वर कोणते swings मांडले — Dow minor (Q15 आधी) वि. degree-aware (Q15) + elliott
सल्ला. Engine पूर्ण उपलब्ध history वर; chart शेवटच्या `--years` वर्षांचा. फक्त दृश्य तपासणी — parameter बदल नाही, order / broker /
AI call नाही. Holdout: NIFTY चे sealed holdout (elliott.data_policy) — Q33: engine warm-up मध्ये holdout candles चालतात, पण
chart / JSON / caption / log मध्ये holdout तारीख कधीच नाही (NIFTY chart फक्त holdout नंतरचा, Q31).

  python3 scripts/v22_daily_swings_view.py --symbol BANKNIFTY --daily <D csv.gz> --out-dir <trade-data>/review/v22/daily_swings [--years 2]

Output: <out-dir>/<SYMBOL>/daily_swings.png + daily_swings.json + caption.txt; <out-dir>/manifest.json (Telegram sender साठी,
NIFTY आधी). पाठवणं फक्त VPS वरून: scripts/send_review_to_telegram.py --run review/v22/daily_swings
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from decision3 import charts as CH  # noqa: E402
from decision3 import daily_swings as DS  # noqa: E402
from decision3 import history as HI  # noqa: E402

ORDER = ("NIFTY", "BANKNIFTY")                                             # Telegram क्रम: NIFTY आधी


is_nifty = HI.is_nifty
sealed_fn = HI.sealed_fn


def load_daily(paths, symbol=None):
    """Q33 (Abhi): engine पूर्ण उपलब्ध history वर (NIFTY holdout candles सुद्धा — फक्त warm-up input); output साठी `sealed_fn`."""
    return HI.load_daily(paths, prepare=DS.prepare)


def window_of(d, years):
    """शेवटच्या Daily पासून `years` वर्षं मागे (data वरून; तारीख code मध्ये नाही) ⇒ sessions संख्या."""
    t0 = d["timestamp"].iloc[-1] - pd.DateOffset(years=float(years)) if float(years) == int(years) else \
        d["timestamp"].iloc[-1] - pd.Timedelta(days=365.25 * float(years))
    return int((d["timestamp"] >= t0).sum())


def update_manifest(out_dir, item):
    p = os.path.join(out_dir, "manifest.json")
    m = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"run_id": "v22_daily_swings", "title": "v2.2 Daily swings",
                                                                     "unit": "chart", "items": []}
    items = [x for x in m["items"] if x.get("symbol") != item["symbol"]] + [item]
    items.sort(key=lambda x: ORDER.index(x["symbol"]) if x["symbol"] in ORDER else len(ORDER))
    for i, x in enumerate(items, 1):
        x["n"] = i
    m["items"] = items
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    return m


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--daily", required=True, nargs="+",
                    help="Daily OHLC files (csv / csv.gz / parquet; timestamp, open, high, low, close) — जुने आधी, नवे नंतर")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--years", type=float, default=2.0)
    ap.add_argument("--no-elliott", action="store_true")
    a = ap.parse_args(argv)
    sym = a.symbol.upper()
    d = load_daily(a.daily, sym)
    w = window_of(d, a.years)
    v = DS.build(d, window=w, with_elliott=not a.no_elliott, sealed=sealed_fn(sym))
    v["full_window"] = v["i0"] == len(d) - w and (d["timestamp"].iloc[-1] - d["timestamp"].iloc[0]).days >= 365.25 * a.years - 7
    sd = os.path.join(a.out_dir, sym)
    os.makedirs(sd, exist_ok=True)
    png = CH.daily_swings_png(v, sym)
    open(os.path.join(sd, "daily_swings.png"), "wb").write(png)
    cap = DS.caption(v, sym, audit_line="Vision audit: pending (runs before Telegram send)", years=int(a.years) if a.years == int(a.years) else a.years)
    js = DS.to_json(v, sym)
    js["caption"] = cap
    with open(os.path.join(sd, "daily_swings.json"), "w", encoding="utf-8") as fh:
        json.dump(js, fh, ensure_ascii=False, indent=1, default=str)
    open(os.path.join(sd, "caption.txt"), "w", encoding="utf-8").write(cap + "\n")
    m = update_manifest(a.out_dir, {"symbol": sym, "date": v["last_day"], "item": f"v22_daily_swings|{sym}|{v['last_day']}",
                                    "reading": cap.splitlines()[0], "caption": cap, "kind": "v22_daily_swings",
                                    "files": [f"{sym}/daily_swings.png"], "json": f"{sym}/daily_swings.json"})
    print(cap)
    print(f"pivots in window {len(js['pivots'])} · legs {len(js['legs'])} · elliott degree {v['elliott_degree']} · "
          f"manifest items {[x['symbol'] for x in m['items']]}")
    print(f"PNG: {os.path.join(sd, 'daily_swings.png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
