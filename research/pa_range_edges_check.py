"""research/pa_range_edges_check.py — PA standard §2L (track T7) real-data check of decision3/range_edges.py. Research only (no live path,
no API, no order). Dates / paths come from the CLI; charts and JSON go to the PRIVATE trade-data repo only.

  1. per 15M bar of the chosen days: the range state FROM STRUCTURE (`range_edges.range_state`: W / D from decision3.daily RANGE,
     1H / 15M from that timeframe's swings, C-13 equal highs + lows) vs the legacy §5.3 overlap + doji measure (`method.range_state`,
     what `range_state_rule` = "overlap" reports under verdict_rule = score) — bars where they differ are listed;
  2. charts (15M + 1H) of the decision bar and of sample bars: the range edge areas (lifecycle, trade side), the bars where each measure
     says "range" marked under the candles.

    python3 research/pa_range_edges_check.py --symbol NIFTY --m15 <m15.csv.gz> --daily <daily.csv.gz> --days 2026-10-21 \
        --out-dir ../trade-data/review/pa_standard/t7
"""
import argparse
import json
import os
import sys
import warnings

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _read(p):
    x = pd.read_csv(p)
    t = pd.to_datetime(x["timestamp"])
    x["timestamp"] = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None) if t.dt.tz is not None else t
    return x


def load(m15p, dp, upto=None):
    m15 = _read(m15p)[["timestamp", "open", "high", "low", "close"]]
    if upto is not None:
        m15 = m15[m15["timestamp"].dt.normalize() <= pd.Timestamp(upto)].reset_index(drop=True)
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    d = _read(dp)[["timestamp", "open", "high", "low", "close"]]
    d["timestamp"] = d["timestamp"].dt.normalize()
    extra = m15[m15["timestamp"].dt.normalize() > d["timestamp"].max()]
    if len(extra):
        g = extra.assign(_d=extra["timestamp"].dt.normalize()).groupby("_d").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index()
        d = pd.concat([d, g.rename(columns={"_d": "timestamp"})], ignore_index=True)
    d = d[d["timestamp"] <= m15["timestamp"].max().normalize()].reset_index(drop=True)
    d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    return m15, d


COL = {"fresh": "#1971c2", "tested": "#2f9e44", "broken": "#e8590c", "flipped": "#9c36b5", "dead": "#868e96"}


def chart(V, t, edges, title, path, tf, bars, struct=None, overlap=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from decision3 import charts as CH
    lv = V.levels
    if tf == "1H":
        j1 = int(lv.h1_of[t])
        j0 = max(0, j1 - bars)
        fr = lv.h1.iloc[j0:j1 + 1].reset_index(drop=True)
        pos = lambda b: int(lv.h1_of[b]) - j0  # noqa: E731
    else:
        j0 = max(0, t - bars)
        fr = lv.m15.iloc[j0:t + 1].reset_index(drop=True)
        pos = lambda b: b - j0  # noqa: E731
    fig, ax = plt.subplots(figsize=(14, 6.5))
    CH._candles(ax, fr)
    CH._xticks(ax, fr["timestamp"].to_numpy(), max(1, len(fr) // 14))
    lo_y = float(fr["low"].min())
    span = float(fr["high"].max()) - lo_y
    for e in edges:
        x0 = max(0, pos(e["born_bar"]))
        c = COL.get(e["lifecycle"], "#1971c2")
        ax.add_patch(plt.Rectangle((x0, e["lo"]), len(fr) - x0, max(e["hi"] - e["lo"], span * 0.002), color=c, alpha=0.25))
        side = (e["trade_side"] or "no side").replace("_", " ")
        ax.text(x0, e["hi"] if e["range_edge"] == "upper" else e["lo"],
                f"{e['tf']} range {e['range_edge']} edge {e['lo']:,.0f}-{e['hi']:,.0f} - {e['lifecycle']}"
                + (f" x{e['tests']}" if e["lifecycle"] == "tested" else "") + (f" sweeps {e['sweeps']}" if e["sweeps"] else "")
                + f" - {side}" + ("" if e["current"] else " (range over)"),
                fontsize=8, color=c, va="bottom" if e["range_edge"] == "upper" else "top")
        if e["tf"] in ("1H", "15M"):
            for m in e["members"]:
                if 0 <= pos(m["bar"]) < len(fr):
                    ax.plot(pos(m["bar"]), m["price"], "v" if m["kind"] == "H" else "^", color=c, ms=7)
    if tf == "15M":                                                        # which bars each measure calls "range"
        for b in range(j0, t + 1):
            if struct and struct.get(b):
                ax.plot(pos(b), lo_y - span * 0.03, "s", color="#1971c2", ms=3)
            if overlap and overlap.get(b):
                ax.plot(pos(b), lo_y - span * 0.06, "s", color="#e8590c", ms=3)
        ax.text(0, lo_y - span * 0.03, "structure range ", fontsize=7, color="#1971c2", ha="right", va="center")
        ax.text(0, lo_y - span * 0.06, "overlap+doji ", fontsize=7, color="#e8590c", ha="right", va="center")
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.2)
    fig.savefig(path, dpi=105, bbox_inches="tight")
    plt.close(fig)


def all_edges(rs_full):
    return [e for x in rs_full.values() for e in (x["edges"] or (x.get("last_range") or {}).get("edges") or [])]


def main(argv=None):
    ap = argparse.ArgumentParser(description="§2L range edges / range state from structure — real-data check (research)")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--m15", required=True)
    ap.add_argument("--daily", required=True)
    ap.add_argument("--days", nargs="+", required=True, help="sessions to scan (YYYY-MM-DD)")
    ap.add_argument("--charts", type=int, default=4, help="sample charts of differing bars (besides each day's last bar)")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    from decision3 import engine as E3
    from decision3 import history as HI
    from decision3 import method as M
    from decision3 import range_edges as RE
    m15, d = load(a.m15, a.daily, upto=max(a.days))
    V = E3.V22(m15, daily_df=d, sealed=HI.sealed_fn(a.symbol))           # Abhi Z-1t: no 15M bar on a sealed (holdout) date
    os.makedirs(a.out_dir, exist_ok=True)
    ts = pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)
    days = {pd.Timestamp(x) for x in a.days}
    bars = [i for i in range(len(ts)) if ts.iloc[i].normalize() in days]
    rows, struct, overlap = [], {}, {}
    A = V.levels.A
    for t in bars:
        rs = RE.range_state(V, t)
        ov = bool(M.range_state(A, t, V.s))
        struct[t], overlap[t] = rs["in_range"], ov
        rows.append({"bar": str(ts.iloc[t]), "structure": rs["in_range"], "structure_tf": rs["tf"], "overlap": ov,
                     "differ": rs["in_range"] != ov,
                     "by_tf": {k: v["state"] for k, v in rs["by_tf"].items()},
                     "bands": {k: v["band"] for k, v in rs["by_tf"].items() if v["band"]}})
    diff = [r for r in rows if r["differ"]]
    rep = {"symbol": a.symbol, "days": a.days, "bars": len(rows), "structure_range_bars": sum(r["structure"] for r in rows),
           "overlap_range_bars": sum(r["overlap"] for r in rows), "differ_bars": len(diff),
           "daily_range_episodes_known": len(RE.episodes(V.daily, V.bar_end[bars[-1]])) if bars else 0,
           "weekly_range_episodes_known": len(RE.episodes(V.weekly, V.bar_end[bars[-1]])) if bars else 0,
           "rows": rows, "charts": []}
    picks = []
    for day in sorted(days):
        db = [t for t in bars if ts.iloc[t].normalize() == day]
        if db:
            picks.append(db[-1])
    dbars = [t for t in bars if struct[t] != overlap[t]]
    step = max(1, len(dbars) // max(1, a.charts))
    picks += [t for t in dbars[::step][:a.charts] if t not in picks]
    for t in picks:
        by = {tf: (RE.read_tf(V, t, tf) if tf in ("D", "W") else RE.read_intraday(V, t, tf)) for tf in ("W", "D", "1H", "15M")}
        edges = all_edges(by)
        rs = RE.range_state(V, t)
        word = ", ".join(f"{k} {v['state'].replace('_', ' ')}" for k, v in rs["by_tf"].items())
        name = f"{a.symbol}_{str(ts.iloc[t])[:16].replace(' ', '_').replace(':', '')}"
        title = f"{a.symbol} {ts.iloc[t]:%d %b %H:%M} - structure: {word} - overlap+doji: {'range' if overlap.get(t) else 'no'}"
        chart(V, t, [e for e in edges if e["tf"] in ("1H", "15M", "D")], title, os.path.join(a.out_dir, name + "_15M.png"), "15M", 150,
              struct, overlap)
        chart(V, t, [e for e in edges if e["tf"] in ("1H", "D")], title, os.path.join(a.out_dir, name + "_1H.png"), "1H", 110)
        rep["charts"].append({"bar": str(ts.iloc[t]), "files": [name + "_15M.png", name + "_1H.png"], "range_state": rs,
                              "draw_objects": RE.draw_objects(V, t)})
    json.dump(rep, open(os.path.join(a.out_dir, f"{a.symbol}_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              default=str)
    print(json.dumps({k: rep[k] for k in ("symbol", "bars", "structure_range_bars", "overlap_range_bars", "differ_bars",
                                          "daily_range_episodes_known", "weekly_range_episodes_known")}))
    for c in rep["charts"]:
        print(" chart", c["bar"], c["range_state"]["tf"], {k: v["state"] for k, v in c["range_state"]["by_tf"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
