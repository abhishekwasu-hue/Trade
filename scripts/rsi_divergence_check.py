#!/usr/bin/env python3
"""K-RSI verification run (spec §8a): 15M SPOT charts with every RSI divergence the owner (`rsi2.engine.Divergence`) finds, a facts table
under each chart, and a Telegram "requested review" manifest. Code मध्ये तारीख नाही (दिवस फक्त CLI वरून); output फक्त --out-dir
(private trade-data `review/rsi_divergence/<run>/`). Backtest, order, API call नाही. Telegram पाठवणं फक्त VPS वरून:
`scripts/send_review_to_telegram.py --run review/rsi_divergence/<run>`.

    python3 scripts/rsi_divergence_check.py --out-dir <trade-data>/review/rsi_divergence/run1 --run-id rsi_divergence/run1 \
        --input NIFTY=<1m csv/parquet> [NIFTY=<5m / 15m file> …] --input BANKNIFTY=<15m file> … [--day YYYY-MM-DD] [--sessions 10]

Input files: 1m / 5m / 15m bars (frequency read from the timestamps). 15M bars: from 1m (pivots.engine.bars_15m) first, then 15m files,
then complete 15M groups of 5m files (a partial last session, e.g. a morning export). Holdout rows never loaded
(elliott.data_policy.filter_allowed, purpose "annotation"; NIFTY holdout guard in swings2 too). CAS (closing auction) candles dropped.
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
from opportunity_engine import cas as CAS  # noqa: E402
from pivots import engine as PE  # noqa: E402
from rsi2 import charts as RC  # noqa: E402
from rsi2 import engine as RE  # noqa: E402

HEADLINE = "Check: are these the divergences you see? ✅ / ✏️ per chart"
DECISION = "Decision needed: reply ✅ (right) or ✏️ + what is wrong / missing, per chart"
BAR15 = pd.Timedelta(minutes=15)


def read_any(path):
    df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if getattr(df["timestamp"].dt, "tz", None) is not None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    return DP.filter_allowed(df[["timestamp", "open", "high", "low", "close"]], purpose="annotation")


def step_of(df):
    t = df["timestamp"].sort_values()
    g = t.diff()[t.dt.normalize().diff() == pd.Timedelta(0)]
    return g.mode().iloc[0] if len(g) else None


def agg15(df, end):
    """Finer bars ⇒ complete 15M bars (09:15-anchored), only groups whose last finer bar closes by `end`."""
    st = step_of(df)
    k = df["timestamp"].dt.floor("15min")
    g = df.assign(_k=k).groupby("_k").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                          last=("timestamp", "max"), n=("timestamp", "size")).reset_index()
    ok = (g["last"] + st >= g["_k"] + BAR15) & (g["last"] + st <= end)
    g = g[ok].rename(columns={"_k": "timestamp"})
    g["bar_end"] = g["timestamp"] + BAR15
    return g[["timestamp", "bar_end", "open", "high", "low", "close"]]


def load(paths):
    """⇒ (15M frame, 1m frame or None, sources text)."""
    by = {"1m": [], "5m": [], "15m": []}
    for p in paths:
        df = read_any(p)
        st = step_of(df)
        key = {pd.Timedelta(minutes=1): "1m", pd.Timedelta(minutes=5): "5m", BAR15: "15m"}.get(st)
        if key is None:
            raise SystemExit(f"{p}: bar step {st} — 1m / 5m / 15m हवं")
        by[key].append(df)
    m1 = None
    parts = []
    if by["1m"]:
        m1 = pd.concat(by["1m"]).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        parts.append(PE.bars_15m(m1))
    if by["15m"]:
        f = pd.concat(by["15m"]).drop_duplicates("timestamp")
        f["bar_end"] = f["timestamp"] + BAR15
        parts.append(f[["timestamp", "bar_end", "open", "high", "low", "close"]])
    if by["5m"]:
        f = pd.concat(by["5m"]).drop_duplicates("timestamp").sort_values("timestamp")
        parts.append(agg15(f, f["timestamp"].max() + pd.Timedelta(minutes=5)))
    m15 = pd.concat(parts).drop_duplicates("timestamp", keep="first").sort_values("timestamp").reset_index(drop=True)
    m15 = m15[~CAS.cas_mask(m15["timestamp"]).to_numpy()].reset_index(drop=True)
    return m15, m1


def chart(D, out_dir, name, title, f0, f1, t, ctx, note):
    png, divs, caps = RC.div_chart(D, t, f0, f1, title, context_bars=ctx, note=note)
    with open(os.path.join(out_dir, name), "wb") as fh:
        fh.write(png)
    return {"file": name, "title": title, "divergences": divs, "cap_rejected": caps}


def run_symbol(sym, paths, a):
    INS.set_current(sym)
    m15, m1 = load(paths)
    D = RE.Divergence(m15, "15M", df1m=m1)
    ts = pd.to_datetime(m15["timestamp"])
    day = ts.dt.normalize()
    full = PE.complete_sessions(m15)
    done = [d for d in sorted(full) if full[d]]
    last10 = done[-int(a.sessions):]
    partial = [d for d in sorted(full) if not full[d] and d > (done[-1] if done else pd.Timestamp.min)]
    first = {d: int((day == d).to_numpy().argmax()) for d in sorted(full)}
    lastb = {d: int(len(day) - 1 - (day == d).to_numpy()[::-1].argmax()) for d in sorted(full)}
    per = int(a.per_chart)
    out = []
    groups = [last10[i:i + per] for i in range(0, len(last10), per)]
    for k, g in enumerate(groups):
        f0, f1 = first[g[0]], lastb[g[-1]]
        out.append(chart(D, a.out_dir, f"{sym}_15m_sessions_{k + 1}.png",
                         f"{sym} 15M spot · RSI divergence · {g[0]:%d %b} → {g[-1]:%d %b %Y} ({len(g)} sessions)", f0, f1, f1, 0, None))
    for dd in [pd.Timestamp(x) for x in (a.day or [])] + partial:
        if dd not in first:
            print(f"   {sym}: {dd:%d %b %Y} — data नाही (chart नाही)")
            continue
        f0, f1 = first[dd], lastb[dd]
        tag = "" if full.get(dd) else f" · PARTIAL session: data to {pd.Timestamp(m15['bar_end'].iloc[f1]):%H:%M}"
        out.append(chart(D, a.out_dir, f"{sym}_15m_{dd:%Y%m%d}.png", f"{sym} 15M spot · RSI divergence · {dd:%d %b %Y}{tag}",
                         f0, f1, f1, int(a.context_bars), "earlier bars = context; table = divergences whose 2nd pivot is on this day"))
    reads = {}
    for dd in [pd.Timestamp(x) for x in (a.day or [])] + partial:
        if dd in first:
            reads[f"{dd:%Y-%m-%d}"] = [D.read(t) for t in range(first[dd], lastb[dd] + 1)]
    win = [x for x in D.history(areas=True) if x["L2"]["bar"] >= first[last10[0]]] if last10 else []
    caps = [x for x in D.cap_log() if x["L2"]["bar"] >= first[last10[0]]] if last10 else []
    return {"symbol": sym, "sessions": [f"{d:%Y-%m-%d}" for d in last10], "partial": [f"{d:%Y-%m-%d}" for d in partial],
            "charts": out, "divergences_last_sessions": win, "cap_rejected_last_sessions": caps, "reads": reads,
            "counts": {"divergences": len(win), "bear": sum(x["side"] == "bear" for x in win), "bull": sum(x["side"] == "bull" for x in win),
                       "by_degree": {f"D{d}": sum(x["degree"] == d for x in win) for d in D.degrees},
                       "pairs_merged_across_degrees": len(RC.merge_degrees(win)), "cap_rejected": len(caps)}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--input", action="append", required=True, help="SYMBOL=path (repeat)")
    ap.add_argument("--day", action="append", help="extra focus day (YYYY-MM-DD), e.g. a golden day")
    ap.add_argument("--sessions", type=int, default=10)
    ap.add_argument("--per-chart", type=int, default=5, help="sessions per overview chart")
    ap.add_argument("--context-bars", type=int, default=50, help="day charts: bars of context before the day")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    jobs = {}
    for s in a.input:
        sym, p = s.split("=", 1)
        jobs.setdefault(sym.upper(), []).append(p)
    res, items = [], []
    for sym, paths in jobs.items():
        r = run_symbol(sym, paths, a)
        res.append(r)
        c = r["counts"]
        reading = (f"{sym} 15M spot: {c['divergences']} divergences in the last {len(r['sessions'])} sessions "
                   f"(bear {c['bear']}, bull {c['bull']}; {c['pairs_merged_across_degrees']} distinct pairs; "
                   + ", ".join(f"{k} {v}" for k, v in c["by_degree"].items()) + f"); {c['cap_rejected']} pairs rejected only by the "
                   "bar cap (grey dotted). Red = bear, green = bull, dashed = forming. Table under each chart: both pivots (time, price, "
                   "RSI), bars apart, status." + (f" Partial session: {', '.join(r['partial'])}." if r["partial"] else ""))
        items.append({"date": r["sessions"][-1] if r["sessions"] else "", "item": f"{a.run_id}|{sym}", "kind": "rsi_check",
                      "headline": HEADLINE, "decision": DECISION, "reading": reading, "files": [x["file"] for x in r["charts"]][:10]})
        print(f"{sym}: " + reading)
    with open(os.path.join(a.out_dir, "facts.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=str)
    m = {"run_id": a.run_id, "title": "RSI divergence check", "unit": "symbol", "items": items}
    with open(os.path.join(a.out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    print(f"लिहिलं: {a.out_dir} ({sum(len(r['charts']) for r in res)} charts, manifest.json, facts.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
