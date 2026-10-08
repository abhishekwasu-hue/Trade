"""research/golden_gallery.py — Golden Gallery G1–G6 (TRADE_GOLDEN_GALLERY_PROMPT). **Trade नाही, vision call नाही ($0).**

🎓 काळ (data policy): IS 2015–2021 आणि 1 Jul → 8 Oct 2026 (contaminated, पाहिलेला). **VAL (2022 → 2024-03) नाही** (gallery मधून नियम ठरतील
⇒ VAL ची स्वतंत्र चाचणी जपायची). Holdout ⇒ कधीच नाही (HoldoutError).
  Stage 1: backtest_review/gallery.scan (market_state + detectors, प्रत्येक बंद 15M bar; Elliott नाही) ⇒ hits.
  Stage 2: प्रति G cheap score नुसार शेवटचे `--shortlist` (default 30) ⇒ chart_reader.evaluate (code grade, सध्याचे settings) ⇒ rank =
           total + 5 × confluence. **Hindsight ranking मध्ये नाही** (फक्त नोंद). प्रति G ≤ 8 (वर्षं / बाजू / आठवडा विविधता).
  Charts: प्रत्येक उदाहरण 1H context + 15M entry (setup नाव, impulse, A-B-C(-D-E), areas, reversal, ENTRY/SL/TARGET/R:R, CAS राखाडी) +
          hindsight. PNG + gallery_index.json फक्त --out-dir. Telegram (--send): प्रति G एक (एकूण 6), "⭐ GALLERY".

    python3 research/golden_gallery.py --is-data data/nifty50_1min.parquet \\
        --recent-data /root/trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz --out-dir /root/trade-data/golden_gallery [--send]
"""
import argparse
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
from backtest_review import gallery as GL      # noqa: E402
from backtest_review import scan as SC         # noqa: E402
from backtest_review import store as BS        # noqa: E402
from chart_reader import evaluate as EV        # noqa: E402
from chart_reader import settings as CS        # noqa: E402
from elliott import data_policy as DP          # noqa: E402

PARTS = {"IS": ("2015-01-01", "2021-12-31", "research"), "2026_q3": ("2026-07-01", "2026-10-08", "golden")}


def load_part(raw, part):
    """IS / 2026_q3 फक्त. VAL ची तारीख इथे येऊच शकत नाही; holdout ⇒ check_range HoldoutError."""
    start, end, purpose = PARTS[part]
    DP.check_range(start, end, purpose=purpose)
    d = raw[(pd.to_datetime(raw["timestamp"]) >= pd.Timestamp(start) - pd.Timedelta(days=SC.WARMUP_DAYS if part != "IS" else 0))
            & (pd.to_datetime(raw["timestamp"]) < pd.Timestamp(end) + pd.Timedelta(days=1))]
    d = DP.filter_allowed(d.reset_index(drop=True), purpose)
    ts = pd.to_datetime(d["timestamp"])
    return d[(ts < DP.VAL_START) | (ts >= DP.CONTAMINATED_START)].reset_index(drop=True)      # VAL कधीच नाही (warm-up सुद्धा)


def evaluate_rank(m1, c, s):
    asof = pd.Timestamp(c["bar_end"])
    w = m1[(m1["timestamp"] >= asof - pd.Timedelta(days=SC.EVAL_DAYS)) & (m1["timestamp"] < asof)].reset_index(drop=True)
    r = EV.evaluate(w, "srv2", asof, s=s)
    act = r.get("active") or {}
    rank = float(r.get("total") or 0.0) + 5.0 * float(act.get("confluence_extra") or 0)
    return r, rank


def caption(c, n):
    side = {1: "bull_put", -1: "bear_call"}[c["side"]]
    return (f"⭐ GALLERY {n}/6 · {c['setup']} {GL.SETUPS[c['setup']]} · {pd.Timestamp(c['bar_start']):%d %b %Y %H:%M} · {side}\n"
            f"{c['why']}\ncode grade {c.get('grade')} ({c.get('total')}) · R:R {('1:%.1f' % c['rr']) if c.get('rr') else '—'} · "
            f"hindsight {c.get('hindsight', {}).get('result')} (फक्त माहिती)\n(1) 1H (2) 15M entry (3) hindsight · ⭐ / ✔ / ✘ dashboard वर.")[:1024]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--recent-data", default=None)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--shortlist", type=int, default=30)
    ap.add_argument("--per-setup", type=int, default=8)
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--parts", default="IS,2026_q3")
    a = ap.parse_args(argv)
    s = CS.load()
    os.makedirs(a.out_dir, exist_ok=True)
    allc, data = [], {}
    for part in a.parts.split(","):
        path = a.is_data if part == "IS" else a.recent_data
        if not path or not os.path.exists(path):
            print(f"⚠️ {part}: data नाही ({path}) — वगळलं")
            continue
        raw = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path, parse_dates=["timestamp"])
        m1 = load_part(raw, part)
        frames = MS.full_frames(m1)
        start, end, _ = PARTS[part]
        t0 = time.monotonic()
        hits = GL.scan(m1, frames["15m"], frames, start=start, end=end, log=print)
        print(f"{part}: hits {len(hits)} ({time.monotonic() - t0:.0f}s)")
        for h in hits:
            h["part"] = part
        allc += hits
        data[part] = (m1, frames)
    short = []
    for g in GL.SETUPS:
        pool = sorted([c for c in allc if c["setup"] == g], key=lambda c: -c["score"])[: a.shortlist]
        for c in pool:
            m1, frames = data[c["part"]]
            r, rank = evaluate_rank(m1, c, s)
            rk = r.get("risk") or {}
            c.update(rank=rank, grade=r.get("grade"), total=r.get("total"), rr=rk.get("rr"), entry_px=rk.get("entry"), inv=rk.get("invalidation"),
                     targets=rk.get("targets"), area=(r.get("active") or {}).get("area"), confluence=(r.get("active") or {}).get("confluence") or [],
                     top_points=SC._top_points(r), ctype=(r.get("structure") or {}).get("correction_type"), codes=SC.RC.codes(r),
                     inv_src=SC.inv_source(r), rev_comp=(r.get("reversal") or {}).get("comp"), mr=r.get("mr"),
                     elliott=(r.get("elliott") or {}).get("line"), areas=SC.compact_areas(r))
            short.append(c)
    chosen = GL.select(short, a.per_setup)
    index = {"settings_hash": SC.settings_hash(s), "created": str(pd.Timestamp.utcnow()), "counts": {g: sum(c["setup"] == g for c in allc)
                                                                                                     for g in GL.SETUPS}, "examples": []}
    send = None
    if a.send:
        from vision_led.telegram import send_album
        send = send_album
    sent = set()
    for c in chosen:
        m1, frames = data[c["part"]]
        c["hindsight"] = SC.hindsight(frames["15m"], c, days=3)                       # फक्त नोंद — निवड आधीच झाली
        gid = BS.gallery_id(c["setup"], c["bar_start"], {1: "bull_put", -1: "bear_call"}[c["side"]])
        d = os.path.join(a.out_dir, c["setup"])
        os.makedirs(d, exist_ok=True)
        tag = f"{pd.Timestamp(c['bar_start']):%Y%m%d_%H%M}"
        head = f"{c['setup']} · {GL.SETUPS[c['setup']]} · {pd.Timestamp(c['bar_start']):%d %b %Y %H:%M}"
        cut = m1[(m1["timestamp"] >= pd.Timestamp(c["bar_start"]) - pd.Timedelta(days=8)) & (m1["timestamp"] < pd.Timestamp(c["bar_end"]) + pd.Timedelta(days=5))]
        m15 = frames["15m"]
        pngs = {"1h": _png(BC.context_1h(frames["1h"], c, head + " · 1H", c.get("elliott"), c.get("areas")), d, tag + "_1h.png"),
                "15m": _png(BC.entry_15m(m15[m15["bar_end"] <= c["bar_end"]], c, head + " · 15M entry", cut[cut["timestamp"] < c["bar_end"]]),
                            d, tag + "_15m.png"),
                "hind": _png(BC.hindsight_15m(m15, c, c["hindsight"], head + " · HINDSIGHT (फक्त माहिती)", cut=cut), d, tag + "_hind.png")}
        index["examples"].append({"id": gid, "setup": c["setup"], "bar_start": str(c["bar_start"]), "side": c["side"], "why": c["why"],
                                  "grade": c.get("grade"), "total": c.get("total"), "rr": c.get("rr"), "rank": c.get("rank"),
                                  "hindsight": c["hindsight"], "part": c["part"], "dir": c["setup"], "pngs": pngs})
        if send is not None and c["setup"] not in sent:
            sent.add(c["setup"])
            imgs = [open(os.path.join(d, p), "rb").read() for p in pngs.values() if p]
            send(imgs, caption(c, len(sent)))
    with open(os.path.join(a.out_dir, "gallery_index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({"counts": index["counts"], "chosen": {g: sum(e["setup"] == g for e in index["examples"]) for g in GL.SETUPS},
                      "telegram": len(sent)}, ensure_ascii=False))


def _png(fig, d, name):
    from vision_led import charts as VCH
    img = VCH.png(fig)
    if not img:
        return None
    with open(os.path.join(d, name), "wb") as fh:
        fh.write(img)
    return name


if __name__ == "__main__":
    main()
