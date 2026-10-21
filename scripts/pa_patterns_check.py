"""scripts/pa_patterns_check.py — PA standard §2H / §2K verification (decision3/patterns_pa.py): read the chart patterns at chosen bars on
real data and draw them (1H candles / 15M candles) for Abhi's eye check. Evidence only — no decision, no order. Charts are private: write
them to trade-data (never the public repo).

  python3 scripts/pa_patterns_check.py --symbol NIFTY --inputs <dir with engine_NIFTY_m15 / m1 / daily .csv.gz> --at last --out <dir>
  python3 scripts/pa_patterns_check.py --symbol BANKNIFTY --m15 <BANKNIFTY_15M.csv.gz> --daily <BANKNIFTY_D.csv.gz> --at auto:8 --out <dir>
"""
import argparse
import json
import os
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decision3 import engine as E3  # noqa: E402
from decision3 import levels as LV  # noqa: E402
from decision3 import patterns_pa as PP  # noqa: E402

STATE_COLOR = {"forming": "#adb5bd", "complete": "#1c7ed6", "broken": "#e8590c", "retested": "#2f9e44", "failed": "#c92a2a"}


def load(a):
    if a.inputs:
        rd = (lambda n: pd.read_csv(os.path.join(a.inputs, f"engine_{a.symbol}_{n}.csv.gz")))   # noqa: E731
        m15, daily = rd("m15"), rd("daily")
        m1 = rd("m1") if os.path.exists(os.path.join(a.inputs, f"engine_{a.symbol}_m1.csv.gz")) else None
    else:
        m15 = pd.read_csv(a.m15)
        m1 = None
        daily = pd.read_csv(a.daily) if a.daily else None
    m15["timestamp"] = pd.to_datetime(m15["timestamp"])
    if "bar_end" not in m15:
        m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    if a.last_days:
        days = sorted(m15["timestamp"].dt.normalize().unique())[-a.last_days:]
        m15 = m15[m15["timestamp"].dt.normalize() >= days[0]].reset_index(drop=True)
    if m1 is not None:
        m1["timestamp"] = pd.to_datetime(m1["timestamp"])
        m1 = m1[m1["timestamp"] >= m15["timestamp"].iloc[0]].reset_index(drop=True)
    if daily is not None:
        daily["timestamp"] = pd.to_datetime(daily["timestamp"]).dt.normalize()
        daily["bar_end"] = daily["timestamp"] + pd.Timedelta(hours=15, minutes=30)
        daily = daily[daily["timestamp"] < m15["timestamp"].iloc[-1].normalize() + pd.Timedelta(days=1)]
        daily = daily[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)
    return m15[["timestamp", "bar_end", "open", "high", "low", "close"]], m1, daily


def draw(V, t, tf, read, title, path, sessions):
    ts = pd.to_datetime(V.levels.ts)
    day0 = sorted(ts.iloc[:t + 1].dt.normalize().unique())[-sessions]
    if tf == "1H":
        h1, of = LV.h1_frame(V.m15.iloc[:t + 1])
        x_of = of
        frame = h1
    else:
        x_of = np.arange(t + 1)
        frame = V.m15.iloc[:t + 1].reset_index(drop=True)
    i0 = int(np.flatnonzero(ts.iloc[:t + 1].dt.normalize() >= day0)[0])
    j0 = int(x_of[i0])
    fr = frame.iloc[j0:].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(15, 7))
    for i, r in enumerate(fr.itertuples()):
        col = "#2b8a3e" if r.close >= r.open else "#c92a2a"
        ax.plot([i, i], [r.low, r.high], color=col, lw=0.7)
        ax.add_patch(plt.Rectangle((i - 0.3, min(r.open, r.close)), 0.6, max(abs(r.close - r.open), 1e-6), color=col))
    lo, hi = fr["low"].min(), fr["high"].max()
    pad = (hi - lo) * 0.08
    shown = 0
    for p in read["patterns"]:
        if p["end_bar"] < i0 and max(ln["until_bar"] for ln in p["lines"]) < i0:
            continue
        col = STATE_COLOR.get(p["state"], "#495057")
        ls = "-" if p["named"] else ":"
        xs = [int(x_of[s["bar"]]) - j0 for s in p["swings"]]
        ys = [s["price"] for s in p["swings"]]
        ax.plot(xs, ys, ls, color=col, lw=1.2, alpha=0.9, marker="o", ms=3)
        for ln in p["lines"]:
            if ln["until_bar"] < i0:
                continue
            b0 = max(ln["p0"][0], i0)
            y0 = ln["p0"][1] + ln["slope"] * (b0 - ln["p0"][0])
            ax.plot([int(x_of[b0]) - j0, int(x_of[ln["until_bar"]]) - j0], [y0, ln["value_until"]], ls, color=col,
                    lw=1.6 if p["named"] else 0.9)
        bst = {k: v["state"] for k, v in p["boundaries"].items() if v["state"] != "inside"}
        lab = f"{p['name']} [{p['state']}]" + (f" {bst}" if bst else "")
        ax.annotate(lab, (xs[-1], ys[-1]), fontsize=7, color=col, xytext=(4, 6 if p["bias"] >= 0 else -10), textcoords="offset points")
        shown += 1
    ax.set_ylim(lo - pad, hi + pad)
    step = max(1, len(fr) // 12)
    ax.set_xticks(range(0, len(fr), step))
    ax.set_xticklabels([pd.Timestamp(fr["timestamp"].iloc[i]).strftime("%d %b %H:%M") for i in range(0, len(fr), step)], rotation=45,
                       fontsize=7)
    ax.set_title(f"{title} · {tf} patterns (swings D{read['degree']}) at {ts.iloc[t]:%d %b %H:%M} · solid = named, dotted = candidate",
                 fontsize=9)
    handles = [plt.Line2D([], [], color=c, lw=2, label=s) for s, c in STATE_COLOR.items()]
    ax.legend(handles=handles, fontsize=7, loc="upper left")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return shown


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--inputs")
    ap.add_argument("--m15")
    ap.add_argument("--daily")
    ap.add_argument("--last-days", type=int, default=0)
    ap.add_argument("--at", default="last", help="last · comma list of timestamps · auto:N (N bars with a named pattern change)")
    ap.add_argument("--sessions", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    m15, m1, daily = load(a)
    t0 = time.time()
    V = E3.V22(m15, m1, daily)
    print(f"V22 built in {time.time() - t0:.1f}s · bars {len(m15)} · pivots " +
          ", ".join(f"D{d}={len(v)}" for d, v in sorted(V.res['pivots'].items())))
    ts = pd.to_datetime(V.levels.ts)
    n = len(ts)
    if a.at == "last":
        ats = [n - 1]
    elif a.at.startswith("auto:"):
        k = int(a.at.split(":")[1])
        cands, prev = [], None
        for t in range(n // 3, n, 4):                                     # sample bars; keep those where a named 1H pattern changed
            r = PP.read_patterns(V, t, tf="1H")
            sig = tuple(sorted((p["family"], p["state"], p["end_bar"]) for p in r["patterns"] if p["named"]))
            if sig and sig != prev:
                cands.append(t)
            prev = sig
        pick = np.linspace(0, len(cands) - 1, min(k, len(cands))).round().astype(int) if cands else []
        ats = sorted({cands[i] for i in pick})
    else:
        want = [pd.Timestamp(x) for x in a.at.split(",")]
        ats = [int(np.flatnonzero(ts <= w)[-1]) for w in want]
    os.makedirs(a.out, exist_ok=True)
    summary = []
    for t in ats:
        for tf in ("1H", "15M"):
            t1 = time.time()
            r = PP.read_patterns(V, t, tf=tf)
            dt = time.time() - t1
            name = f"{a.symbol}_{ts[t]:%Y%m%d_%H%M}_{tf}.png"
            shown = draw(V, t, tf, r, a.symbol, os.path.join(a.out, name), a.sessions if tf == "1H" else max(3, a.sessions // 2))
            print(f"\n{a.symbol} {ts[t]} {tf} (D{r['degree']}) — {len(r['patterns'])} patterns ({shown} drawn) "
                  f"in {dt * 1000:.0f} ms ⇒ {name}")
            for p in r["patterns"]:
                bs = {k: v["state"] for k, v in p["boundaries"].items()}
                print(f"  {p['name']:<26} {p['state']:<9} swings {p['swings'][0]['ts'][:16]} → {p['swings'][-1]['ts'][:16]}  "
                      f"{bs}  — {p['why']}")
            for e in r["evidence"]:
                print(f"  evidence: {e}")
            for x in r["retest_levels"]:
                print(f"  E4(b) retest level: {x['pattern']} {x['boundary']} {x['value_t']:,.2f} ({x['role']}, {x['state']})")
            summary.append({"ts": str(ts[t]), "tf": tf, "chart": name, "ms": round(dt * 1000),
                            "patterns": [{k: p[k] for k in ("family", "state", "named", "why", "start_bar", "end_bar", "lines")}
                                         for p in r["patterns"]],
                            "evidence": r["evidence"], "retest_levels": r["retest_levels"]})
    with open(os.path.join(a.out, f"{a.symbol}_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
