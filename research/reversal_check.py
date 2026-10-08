"""research/reversal_check.py — POSSIBLE_REVERSAL v2 overfit तपासणी (Abhi 2026-10-08): IS मधून 5 खरे reversal आणि 5 खोल-pullback-नंतर-
trend-चालू दिवस. दिवसाच्या close ला market_state (no-lookahead) ⇒ flag स्थिती; वर्ग hindsight ने (फक्त निवडीसाठी, नियमात नाही):
  reversal      पुढच्या 10 sessions मध्ये impulse origin close ने आधी तुटला;
  continuation  impulse टोकापलीकडे (trend दिशेने) close आधी.
उमेदवार = correction retrace ≥ 38.2% असलेले दिवस. Seed नोंदवलेला. Charts (1H + 15M) out-dir मध्ये + review manifest (Telegram).

    python3 research/reversal_check.py --is-data data/nifty50_1min.parquet --out-dir /root/trade-data/review/reversal/run1
"""
import argparse
import json
import os
import random
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402

SEED = 20261009


def classify(m15, close_ts, imp, horizon=10):
    """hindsight: पुढच्या horizon sessions मध्ये आधी काय — impulse origin तुटला (reversal) की impulse टोक पार (continuation)."""
    f = m15[pd.to_datetime(m15["timestamp"]) > close_ts]
    days = pd.to_datetime(f["timestamp"]).dt.normalize().unique()[:horizon]
    f = f[pd.to_datetime(f["timestamp"]).dt.normalize().isin(days)]
    d, org, end = int(imp["dir"]), float(imp["from"]), float(imp["to"])
    for c in f["close"].to_numpy(float):
        if (c - org) * d < 0:
            return "reversal"
        if (c - end) * d > 0:
            return "continuation"
    return "unresolved"


def scan(m1, start, end, log=print):
    import market_state as MS
    frames = MS.full_frames(m1)
    m15 = frames["15m"]
    days = sorted(pd.to_datetime(m15["timestamp"]).dt.normalize().unique())
    out = []
    for n, d in enumerate(days):
        d = pd.Timestamp(d)
        if d < pd.Timestamp(start) or d > pd.Timestamp(end) or not DP.allowed(d, "golden"):
            continue
        close = d + pd.Timedelta(hours=15, minutes=30)
        ms = MS.read(m1, close, run_elliott=False, frames=frames)
        imp, corr = ms.get("impulse"), ms.get("correction") or {}
        if not imp or (corr.get("retrace") or 0) < 0.382 or corr.get("status") == "origin_broken":
            continue
        rev = ms.get("possible_reversal")
        out.append({"date": f"{d:%Y-%m-%d}", "dir": imp["dir"], "impulse": [imp["from"], imp["to"]], "retrace": corr.get("retrace"),
                    "trend": f"{ms['trend']['dir']} {ms['trend']['state']}", "flag": (rev or {}).get("state"),
                    "reason": (rev or {}).get("reason"), "class": classify(m15, close, imp)})
        if log and n % 200 == 0:
            log(f"  {d:%Y-%m-%d}: candidates {len(out)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start", default="2015-03-01")
    ap.add_argument("--end", default="2021-12-31")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--per-class", type=int, default=5)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args(argv)
    raw = pd.read_parquet(a.is_data) if a.is_data.endswith(".parquet") else pd.read_csv(a.is_data, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    raw = DP.filter_allowed(raw, "golden")
    os.makedirs(a.out_dir, exist_ok=True)
    cache = os.path.join(a.out_dir, "candidates.json")
    if os.path.exists(cache):
        cands = json.load(open(cache, encoding="utf-8"))
    else:
        cands = scan(raw, a.start, a.end)
        json.dump(cands, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    rng = random.Random(a.seed)
    pick = []
    for cl in ("reversal", "continuation"):
        pool = [c for c in cands if c["class"] == cl]
        pick += rng.sample(pool, min(a.per_class, len(pool)))
    tab = pd.DataFrame(cands)
    summary = {"seed": a.seed, "n_candidates": len(cands),
               "crosstab": ({f"{k[0]}|{k[1]}": int(v) for k, v in tab.groupby(["class", tab["flag"].fillna("none")]).size().items()}
                            if len(tab) else {}), "picked": pick}
    json.dump(summary, open(os.path.join(a.out_dir, "reversal_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              default=str)
    print(json.dumps(summary["crosstab"], ensure_ascii=False))
    if a.no_render:
        return
    import market_state as MS
    from backtest_review import charts as BC
    items = []
    frames = MS.full_frames(raw)
    for n, c in enumerate(pick, 1):
        d = pd.Timestamp(c["date"])
        close = d + pd.Timedelta(hours=15, minutes=30)
        ms = MS.read(raw, close, run_elliott=False, frames=frames)
        sub = os.path.join(a.out_dir, c["date"])
        os.makedirs(sub, exist_ok=True)
        m15, h1 = frames["15m"], frames["1h"]
        m15_ts = pd.to_datetime(m15["timestamp"]).to_numpy(dtype="datetime64[ns]")
        bars = [{"bar_start": str(d + pd.Timedelta(hours=15)), "signal": None, "why": c.get("reason") or "flag नाही", "zones": []}]
        BC.core_day_15m(m15[m15["bar_end"] <= close], d, bars, f"{c['date']} · 15M · {c['class']} · flag {c['flag']}", m15_ts=m15_ts,
                        ms_close=ms).write_image(os.path.join(sub, "day_15m.png"), format="png", scale=1)
        cc = {"bar_end": close, "trend": ms["trend"], "impulse": ms["impulse"], "labels": (ms.get("correction") or {}).get("labels"),
              "zones": []}
        BC.context_1h(h1, cc, f"{c['date']} · 1H · {c['class']}", m15_ts=m15_ts).write_image(os.path.join(sub, "day_1h.png"), format="png",
                                                                                           scale=1)
        items.append({"n": n, "date": c["date"], "item": f"reversal/run1|day:{c['date']}",
                      "reading": (f"hindsight: {c['class']} · impulse {c['impulse'][0]:,.0f} → {c['impulse'][1]:,.0f} · retrace "
                                  f"{c['retrace']:.0%} · नियम: {c['flag'] or 'flag नाही'}" + (f" — {c['reason']}" if c.get("reason") else "")),
                      "files": [f"{c['date']}/day_1h.png", f"{c['date']}/day_15m.png"]})
    json.dump({"run_id": "reversal/run1", "title": "POSSIBLE_REVERSAL तपासणी", "items": items},
              open(os.path.join(a.out_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
