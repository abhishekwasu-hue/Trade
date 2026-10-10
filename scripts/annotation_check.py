#!/usr/bin/env python3
"""🧭 ANNOTATION CHECK (Abhi): शेवटच्या N trading days चे charts, code च्या Correction Reader प्रमाणे annotate — Abhi ✔ / ✘ देतो.

प्रत्येक दिवसासाठी decision bars: दिवसाचा शेवटचा बंद 15M bar + reader चा निर्णय `setup` / `wait` झालेले bars (दिवसाला कमाल
annot_max_bars_per_day). Code मध्ये तारीख नाही: "शेवटचे N दिवस" = data मध्ये (data_policy ने परवानगी असलेले) शेवटचे दिवस.
Vision call नाही (खर्च 0). Backtest नाही (निकाल / P&L मोजत नाही). Output फक्त --out-dir मध्ये (private trade-data).

  python3 scripts/annotation_check.py --data <1m csv/parquet> --out-dir <trade-data>/review/annotation/<run_id> --run-id <run_id>
  … --send   (VPS: Telegram album प्रत्येक decision bar ला; replies backtest_review मध्ये प्रकार annotation_check)
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from correction import annotate as AN  # noqa: E402
from correction import reader as CR  # noqa: E402
from correction import settings as CRS  # noqa: E402
from elliott import data_policy as DP  # noqa: E402

FILES = ("15M", "1H", "D", "W")                                             # album क्रम (Abhi: 15M, 1H, Daily, Weekly)


def load(paths):
    """एक किंवा अनेक 1m files (उदा. golden + illustration) ⇒ एकत्र, duplicate वेळा एकदाच."""
    paths = [paths] if isinstance(paths, str) else list(paths)
    raw = pd.concat([pd.read_parquet(p) if str(p).endswith(".parquet") else pd.read_csv(p, parse_dates=["timestamp"]) for p in paths],
                    ignore_index=True)
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    raw = raw.drop_duplicates("timestamp", keep="last")
    return DP.filter_allowed(raw, "annotation").sort_values("timestamp").reset_index(drop=True)   # holdout कधीच नाही; illustration दिवस फक्त annotation साठी


def trading_days(m1, n):
    days = sorted(pd.to_datetime(m1["timestamp"]).dt.normalize().unique())
    return [pd.Timestamp(d) for d in days[-int(n):]]


def day_bars(m1, day, entry_start):
    """त्या दिवसाचे बंद 15M bars (start ≥ entry_start), bar start वेळा."""
    d = m1[pd.to_datetime(m1["timestamp"]).dt.normalize() == day]
    if not len(d):
        return []
    st = pd.to_datetime(d["timestamp"]).dt.floor("15min").unique()
    last_min = pd.to_datetime(d["timestamp"]).max()
    out = [pd.Timestamp(t) for t in st if pd.Timestamp(t).strftime("%H:%M") >= entry_start and pd.Timestamp(t) + pd.Timedelta(minutes=14) <= last_min]
    return sorted(out)


def select(reads, last_bar, k):
    """setup आधी, मग wait — सलग सारख्या निर्णयांच्या मालिकेतला पहिलाच bar; कमाल k. शिवाय दिवसाचा शेवटचा bar (नेहमी)."""
    picks, prev = [], None
    for t, R in reads:
        o = R["decision"]["outcome"]
        if o in ("setup", "wait") and o != prev:
            picks.append((0 if o == "setup" else 1, t))
        prev = o
    chosen = sorted(t for _, t in sorted(picks)[:int(k)])
    if last_bar not in chosen:
        chosen.append(last_bar)
    return sorted(chosen)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+", help="NIFTY 1m (csv / parquet) — data_policy annotation purpose ने कापला जातो")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--days", type=int, default=CRS.DEFAULTS["annot_days"])
    ap.add_argument("--max-bars", type=int, default=CRS.DEFAULTS["annot_max_bars_per_day"])
    ap.add_argument("--futures-dir", default=os.path.join(ROOT, "data"),
                    help="oe_futures_5min_NIFTY*.parquet ची जागा (collector) — futures फक्त volume साठी, वेळेने जोडलेला")
    ap.add_argument("--send", action="store_true", help="Telegram albums (VPS)")
    a = ap.parse_args(argv)
    from elliott import settings as ES
    es = dict(ES.DEFAULTS)
    m1 = load(a.data)
    from chart_reader import volume as VL
    fut5 = VL.load("NIFTY", a.futures_dir)
    if fut5 is not None:                                                   # holdout काळाचा futures volume सुद्धा नाही
        fut5 = DP.filter_allowed(VL._naive_ist(fut5), "annotation")
    print("futures volume: " + (f"{len(fut5)} 5M rows" if fut5 is not None else "नाही (volume NA)"))
    days = trading_days(m1, a.days)
    os.makedirs(a.out_dir, exist_ok=True)
    print(f"दिवस: {len(days)} ({days[0]:%d %b} → {days[-1]:%d %b})" if days else "दिवस नाहीत")
    chosen = []
    for day in days:
        bars = day_bars(m1, day, es["entry_start"])
        if not bars:
            continue
        reads = []
        for t in bars:
            R = CR.read(m1, t + pd.Timedelta(minutes=15), es=es, fut5=fut5)
            reads.append((t, R))
        reads = [(t, R) for t, R in reads if R.get("frames_ok") and R.get("decision_bar")]   # data अपुरा ⇒ chart नाही
        if not reads:
            print(f"  {day:%d %b}: data अपुरा (15M bars < 40) — वगळला")
            continue
        sel = select(reads, reads[-1][0], a.max_bars)
        byt = dict(reads)
        chosen += [(t, byt[t]) for t in sel]
        print(f"  {day:%d %b}: {len(bars)} bars · निवड {', '.join(f'{t:%H:%M}' for t in sel)} · "
              + ", ".join(f"{byt[t]['decision']['outcome']}" for t in sel))
    items, pages = [], []
    total = len(chosen)
    for n, (t, R) in enumerate(chosen, 1):
        tag = f"{t:%Y-%m-%d_%H%M}"
        cdir = os.path.join(a.out_dir, tag)
        os.makedirs(cdir, exist_ok=True)
        _, fr = CR.frames(m1, t + pd.Timedelta(minutes=15))
        pngs = AN.charts(fr, R, R.get("ms_swings"))
        files = []
        for tf in FILES:
            if tf in pngs:
                fn = f"{tf}.png"
                open(os.path.join(cdir, fn), "wb").write(pngs[tf])
                files.append(f"{tag}/{fn}")
        json.dump(R, open(os.path.join(cdir, "correction_read.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        cap = AN.caption(n, total, R)
        items.append({"n": n, "date": f"{t:%Y-%m-%d}", "item": f"{a.run_id}|bar:{t:%Y-%m-%d %H:%M}", "kind": "annotation_check",
                      "reading": cap, "caption": cap, "files": files, "outcome": R["decision"]["outcome"]})
        pg = AN.pdf_page(pngs, f"ANNOTATION CHECK {n}/{total} - {t:%d %b %Y %H:%M} - code: {R['decision']['outcome']}")
        if pg is not None:
            pages.append(pg)
    json.dump({"run_id": a.run_id, "title": "ANNOTATION CHECK", "unit": "bar", "items": items},
              open(os.path.join(a.out_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if pages:
        pages[0].save(os.path.join(a.out_dir, "annotation_check.pdf"), save_all=True, append_images=pages[1:], resolution=100)
    cnt = {o: sum(1 for i in items if i["outcome"] == o) for o in ("setup", "wait", "no_trade")}
    json.dump({"run_id": a.run_id, "days": [f"{d:%Y-%m-%d}" for d in days], "bars": len(items), "outcomes": cnt},
              open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"decision bars: {len(items)} · setup {cnt['setup']} · थांबा {cnt['wait']} · trade नाही {cnt['no_trade']}")
    if a.send and items:
        from backtest_review import telegram as RT
        pdf = os.path.join(a.out_dir, "annotation_check.pdf")
        if os.path.exists(pdf):
            r = RT.send_document(pdf, f"🧭 ANNOTATION CHECK · PDF ({len(items)} decision bars) · खाली प्रत्येक bar चा album — ✔ / ✘ reply", a.run_id)
            print(f"Telegram PDF: {r}")
        out = RT.send_run(a.out_dir, run_key=a.run_id)
        print(f"Telegram: पाठवले {out['sent']} · आधीच गेलेले {out['skipped']} · अयशस्वी {len(out['failed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
