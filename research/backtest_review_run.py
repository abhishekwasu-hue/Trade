"""research/backtest_review_run.py — Backtest visual review run (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT). **Trade नाही, order नाही, vision call नाही ($0).**

🎓 काळ (data policy): 2026_q3 = 1 Jul → 8 Oct 2026 (contaminated, पाहिलेला) · 2024_q1 = 1 Jan → 31 Mar 2024 (VAL शेवट). Holdout ⇒ HoldoutError.
Logic पडताळणी फक्त — नफ्याचे आकडे / tuning नाही. Engine = दुरुस्तीनंतरचा chart_reader (code grade), सध्याचे settings (hash नोंद).
प्रत्येक दिवस: 1H + 15M (सगळे candidates ✅ / 🟡 / ✖ + reason code, "code ची गोष्ट"). प्रत्येक trade (A/B): 1H context + 15M entry +
15M hindsight. PNG + run_index.json फक्त --out-dir (trade-data / VPS archive). Telegram (--send): फक्त trades, "🔎 REVIEW", Approve नाही,
दिवसाला ≤ 10. Review dashboard वर ("Backtest Review" पान) ⇒ Supabase `backtest_review`.

    python3 research/backtest_review_run.py --period 2026_q3 --data /root/trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz \\
        --out-dir /root/trade-data/backtest_review/2026_q3 [--send]
    python3 research/backtest_review_run.py --period 2024_q1 --data data/nifty50_1min.parquet --out-dir /root/trade-data/backtest_review/2024_q1
2 GB RAM: charts एकाच kaleido / Chrome session मध्ये, दिवसागणिक (batch), PNG लिहून लगेच सोडतो.
"""
import argparse
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import market_state as MS                      # noqa: E402
from backtest_review import charts as BC       # noqa: E402
from backtest_review import scan as SC         # noqa: E402
from backtest_review import store as BS        # noqa: E402
from chart_reader import evaluate as EV        # noqa: E402
from chart_reader import settings as CS        # noqa: E402
from chart_reader import setups as SU          # noqa: E402
from opportunity_engine import cas as CAS      # noqa: E402
from vision_led import charts as VCH           # noqa: E402
from vision_led import validate as VA          # noqa: E402

MAX_TG_PER_DAY = 10


def read_data(path):
    return pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])


def trade_item(c):
    return BS.item_id("trade", c["bar_start"], f"{pd.Timestamp(c['bar_start']):%H:%M}", {1: "bull_put", -1: "bear_call"}[c["side"]])


def caption(day, c, h, n, total):
    side = {1: "bull_put", -1: "bear_call"}[c["side"]]
    tg = (c.get("targets") or [{}])[0].get("price")
    return (f"🔎 REVIEW {n}/{total} · {pd.Timestamp(c['bar_start']):%d %b %Y %H:%M} · {side} · "
            f"area {c.get('area_label') or '—'} · grade {c.get('grade')} ({c.get('total')}, नोंद)\n"
            f"{c.get('checklist_summary') or ''}\n"
            f"ENTRY {c.get('entry_px') or 0:,.0f} · SL {c.get('inv') or 0:,.0f} ({c.get('inv_src') or '—'}) · TARGET {tg or 0:,.0f} · "
            f"R:R {('1:%.1f' % c['rr']) if c.get('rr') else '—'}\n"
            f"hindsight: {h.get('result')} · MFE {h.get('mfe', '—')} / MAE {h.get('mae', '—')} pts\n"
            "(1) 1H context (2) 15M entry (3) hindsight · ✔ / ✘ / ? dashboard वर (Backtest Review). Approve नाही.")[:1024]


def run_period(raw, period, out_dir, s, send=None, max_days=None, render=True, log=print, only=None, span=None):
    start, end = span or SC.PERIODS[period]
    m1 = SC.load_period(raw, start, end)
    if m1.empty:
        raise RuntimeError(f"{period}: data नाही")
    frames = MS.full_frames(m1)
    m15, h1 = frames["15m"], frames["1h"]
    daily_close = CAS.daily_levels(m1)["close"]
    days = SC.days_of(m1, start, end)
    if only:
        days = [d for d in days if f"{pd.Timestamp(d):%Y-%m-%d}" in set(only)]
    days = days[: max_days or None]
    index = {"period": period, "start": start, "end": end, "settings_hash": SC.settings_hash(s), "created": str(pd.Timestamp.utcnow()),
             "days": []}
    os.makedirs(out_dir, exist_ok=True)
    session = _kaleido()
    mem = SU.LineMemory()                                                  # trendline स्थिर ओळख, संपूर्ण period भर
    m15_ts = pd.to_datetime(m15["timestamp"]).to_numpy(dtype="datetime64[ns]")
    timing = {"eval_s": [], "render_s": []}
    try:
        for k, day in enumerate(days):
            t0 = time.monotonic()
            cands = SC.scan_day(m1, day, s, frames=frames, trig=m15, memory=mem)
            timing["eval_s"] += [c["eval_s"] for c in cands if c.get("eval_s") is not None]
            trs = SC.trades(cands, m15)
            day_end = pd.Timestamp(day) + pd.Timedelta(hours=15, minutes=30)
            ms_close = MS.read(m1, day_end, run_elliott=False, frames=frames)
            tsv = pd.to_datetime(m1["timestamp"]).to_numpy(dtype="datetime64[ns]")
            a_ = int(np.searchsorted(tsv, np.datetime64(day_end - pd.Timedelta(days=SC.EVAL_DAYS), "ns")))
            b_ = int(np.searchsorted(tsv, np.datetime64(day_end, "ns")))
            r_end = EV.evaluate(m1.iloc[a_:b_].reset_index(drop=True), "srv2", day_end, s=s, run_elliott=False)   # दिवस अखेर: phase timeline, zones, gap
            end_rec = SC.candidate_record(r_end, ms_close, m15[m15["bar_end"] <= day_end].iloc[-1]) if r_end.get("side") or r_end.get("zones") else {}
            story = SC.day_story(cands, ms_close)
            ddir = os.path.join(out_dir, f"{pd.Timestamp(day):%Y-%m-%d}")
            os.makedirs(ddir, exist_ok=True)
            cut = m1[(m1["timestamp"] >= pd.Timestamp(day) - pd.Timedelta(days=4)) & (m1["timestamp"] < pd.Timestamp(day) + pd.Timedelta(days=4))]
            timeline = []                                                  # story phases (P1–P5) काढले — Abhi 2026-10-08
            rec = {"date": f"{pd.Timestamp(day):%Y-%m-%d}", "story": story, "n_candidates": len(cands), "item_id": BS.item_id("day", day),
                   "candidates": [_compact(c) for c in cands], "trades": [], "pngs": {},
                   "tl_log": list(mem.log)[-5:]}
            last = cands[-1] if cands else {"areas": [], "elliott": None}
            if render:
                t1 = time.monotonic()
                day15 = BC.adaptive_window(m15, day_end, {"impulse": ms_close.get("impulse"),
                                                          "labels": (ms_close.get("correction") or {}).get("labels")})
                rec["pngs"]["day_1h"] = _png(BC.context_1h(h1, {"bar_end": day_end, "trend": ms_close["trend"], "impulse": ms_close["impulse"],
                                                                 "labels": (ms_close.get("correction") or {}).get("labels")},
                                                           f"{rec['date']} · 1H context (दिवस अखेर)", last.get("elliott"), last.get("areas")),
                                             ddir, "day_1h.png")
                rec["pngs"]["day_15m"] = _png(BC.day_15m(day15, cands, story, f"{rec['date']} · 15M · code ची सगळी वाचनं, candidates आणि story",
                                                         ms_close, cut, last.get("areas"), zones=end_rec.get("zones"), gap=end_rec.get("gap"),
                                                         timeline=timeline, m15_ts=m15_ts, day=day), ddir, "day_15m.png")
                timing["render_s"].append(round(time.monotonic() - t1, 2))
            for c in trs:
                h = c.get("hindsight") or SC.hindsight(m15, c, days=3)
                strike = None
                dc = daily_close[daily_close.index < pd.Timestamp(c["bar_start"]).normalize()]
                if c.get("entry_px") is not None and c.get("inv") is not None and len(dc):
                    strike = VA.strike_info(c["side"], c["entry_px"], c["inv"], c.get("mr") or 0.0, dc.to_numpy(), c["bar_end"], VA.DEFAULTS)["strike"]
                tr = {"item_id": trade_item(c), "time": f"{pd.Timestamp(c['bar_start']):%H:%M}", "side": c["side"], "grade": c.get("grade"),
                      "checklist": c.get("checklist"),
                      "checklist_summary": c.get("checklist_summary"), "area_label": c.get("area_label"),
                      "total": c.get("total"), "rr": c.get("rr"), "entry": c.get("entry_px"), "inv": c.get("inv"), "inv_src": c.get("inv_src"),
                      "target": (c.get("targets") or [{}])[0].get("price"), "strike": strike, "hindsight": h, "codes": c["codes"], "pngs": {}}
                if render:
                    tag = f"trade_{pd.Timestamp(c['bar_start']):%H%M}"
                    head = f"{rec['date']} {tr['time']} · {'bull_put' if c['side'] > 0 else 'bear_call'} · grade {c.get('grade')}"
                    t1 = time.monotonic()
                    tr["pngs"]["1h"] = _png(BC.context_1h(h1, c, head + " · 1H context", c.get("elliott"), c.get("areas"), m15_ts=m15_ts),
                                            ddir, tag + "_1h.png")
                    tr["pngs"]["15m"] = _png(BC.entry_15m(m15[m15["bar_end"] <= c["bar_end"]], c, head + " · 15M entry (entry bar पर्यंतच)",
                                                          cut[cut["timestamp"] < c["bar_end"]], strike, m15_ts=m15_ts), ddir, tag + "_15m.png")
                    timing["render_s"].append(round((time.monotonic() - t1) / 2, 2))
                    tr["pngs"]["hind"] = _png(BC.hindsight_15m(m15, c, h, head + " · HINDSIGHT (फक्त अहवाल)", cut=cut), ddir, tag + "_hind.png")
                rec["trades"].append(tr)
            index["days"].append(rec)
            _write(out_dir, index)
            log(f"  {rec['date']}: candidates {len(cands)}, trades {len(trs)} ({time.monotonic() - t0:.0f}s)")
            gc.collect()
            if send is not None:
                for n, tr in enumerate(rec["trades"][:MAX_TG_PER_DAY], 1):
                    imgs = [open(os.path.join(ddir, tr["pngs"][k]), "rb").read() for k in ("1h", "15m", "hind") if tr["pngs"].get(k)]
                    send(imgs, caption(day, next(c for c in trs if trade_item(c) == tr["item_id"]), tr["hindsight"], n, len(rec["trades"])))
    finally:
        if session is not None:
            session.__exit__(None, None, None)
    index["timing"] = {k: {"n": len(v), "p50": float(np.median(v)) if v else None, "max": max(v) if v else None} for k, v in timing.items()}
    _write(out_dir, index)
    return index


def _compact(c):
    return {"time": f"{pd.Timestamp(c['bar_start']):%H:%M}", "side": c["side"], "code_side": c.get("code_side"), "status": c["status"],
            "codes": c["codes"], "grade": c.get("grade"), "total": c.get("total"), "rr": c.get("rr"), "area": (c.get("area") or {}).get("id"),
            "area_label": c.get("area_label"), "checklist_summary": c.get("checklist_summary"), "checklist": c.get("checklist")}


def _png(fig, ddir, name):
    img = VCH.png(fig)
    if not img:
        return None
    with open(os.path.join(ddir, name), "wb") as fh:
        fh.write(img)
    return name


def _write(out_dir, index):
    tmp = os.path.join(out_dir, "run_index.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, os.path.join(out_dir, "run_index.json"))


def _kaleido():
    try:
        from opportunity_engine.visual_audit.render import KaleidoSession
        k = KaleidoSession()
        k.__enter__()
        return k
    except Exception:
        return None


def summary(index):
    days = index["days"]
    trades = [t for d in days for t in d["trades"]]
    codes = pd.Series([c for d in days for x in d["candidates"] for c in x["codes"]]).value_counts().to_dict() if days else {}
    return {"period": index["period"], "days": len(days), "candidates": sum(d["n_candidates"] for d in days), "trades": len(trades),
            "codes": codes, "settings_hash": index["settings_hash"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=sorted(SC.PERIODS), required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--send", action="store_true", help="Telegram: फक्त trades (🔎 REVIEW, दिवसाला ≤ 10)")
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--days", default=None, help="फक्त या तारखा (comma; उदा. 2026-10-07)")
    a = ap.parse_args(argv)
    s = CS.load()
    send = None
    if a.send:
        from vision_led.telegram import send_album
        send = send_album
    idx = run_period(read_data(a.data), a.period, a.out_dir, s, send=send, max_days=a.max_days, render=not a.no_render,
                      only=a.days.split(",") if a.days else None)
    print(json.dumps(summary(idx), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
