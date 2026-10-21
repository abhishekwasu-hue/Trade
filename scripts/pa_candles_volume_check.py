#!/usr/bin/env python3
"""PA standard T5 verification (read-only): decision3/candle_forms.py (§2G) and decision3/volume_read.py (§2I) on real data.

  NIFTY day chart (1H + 15M, forms only at a location, FUT volume reads):
    python3 scripts/pa_candles_volume_check.py --symbol NIFTY --inputs <vps_run3/inputs> --day 2026-10-21 --out <dir>
  BANKNIFTY examples (one grid per concept, up to --examples panels each):
    python3 scripts/pa_candles_volume_check.py --symbol BANKNIFTY --m15 <BANKNIFTY_15M.csv.gz> --daily <BANKNIFTY_D.csv.gz>
        --futures <fut5 parquet …> --out <dir>

Charts + JSON go to --out (a private trade-data folder — never the public repo). No order, no broker, no network. Dates come from the CLI
only. Every read at bar t uses bars ≤ t (the panels show a few later candles greyed, after the marked bar, for the reviewer only).
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from decision3 import candle_forms as CF  # noqa: E402
from decision3 import engine as E3  # noqa: E402
from decision3 import volume_read as VR  # noqa: E402

S = {"ltf_choch": False, "level_death_side": "role"}                      # LTF is not read here; role = the live K4 death side


def _naive(x):
    t = pd.to_datetime(x)
    return t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None) if getattr(t.dt, "tz", None) is not None else t


def _read(p):
    x = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p)
    x["timestamp"] = _naive(x["timestamp"])
    return x


def load_nifty(inputs):
    m15 = _read(os.path.join(inputs, "engine_NIFTY_m15.csv.gz"))
    m15["bar_end"] = _naive(m15["bar_end"])
    daily = pd.read_csv(os.path.join(inputs, "engine_NIFTY_daily.csv.gz"))
    fut = _read(os.path.join(inputs, "engine_NIFTY_fut5.csv.gz"))
    return m15, daily, fut


def load_bn(m15p, dailyp, futp):
    m15 = pd.concat([_read(p) for p in m15p]).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    m15 = m15[["timestamp", "open", "high", "low", "close"]]
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    d = pd.concat([_read(p) for p in dailyp])[["timestamp", "open", "high", "low", "close"]]
    d["timestamp"] = d["timestamp"].dt.normalize()
    d = d.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    fut = pd.concat([_read(p) for p in futp], ignore_index=True)
    fut = fut.drop_duplicates(["timestamp", "contract"], keep="last").sort_values("timestamp").reset_index(drop=True)
    return m15, d.reset_index(drop=True), fut


def build(m15, daily, fut):
    return E3.V22(m15, daily_df=daily, futures=fut, s=S)


def touching_areas(V, t):
    A = V.levels.A
    return [x for x in V.levels.snapshot(t) if x["tf"] == "1H" and A["low"][t] <= x["hi"] and A["high"][t] >= x["lo"]]


def read_bar(V, t):
    f15 = CF.read_candle_forms(V, t)
    vr = VR.read_volume(V, t)
    area_reads = []
    for a in touching_areas(V, t):
        ab = VR.absorption(V, t, a)
        cv = VR.commitment_volume(V, t, a)
        pv = VR.read_volume(V, t, area=a)["pullback_vs_impulse"]
        area_reads.append({"area": {k: a[k] for k in ("id", "tf", "role", "lo", "hi")}, "absorption": ab, "commitment_volume": cv,
                           "pullback_into_area": pv})
    return f15, vr, area_reads


# ------------------------------------------------------------------------------------------------ drawing
def candles(ax, A, ix, x0=0, grey_after=None):
    for k, i in enumerate(ix):
        o, h, lo, c = (float(A[q][i]) for q in ("open", "high", "low", "close"))
        late = grey_after is not None and i > grey_after
        col = "#9a9a9a" if late else ("#2e7d32" if c >= o else "#c62828")
        ax.plot([x0 + k, x0 + k], [lo, h], color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((x0 + k - 0.3, min(o, c)), 0.6, max(abs(c - o), 1e-6), color=col, alpha=0.5 if late else 1.0))


def bands(ax, locs, n, y0, y1):
    for x in locs:
        if x.get("kind") == "line":
            continue
        if x["hi"] < y0 or x["lo"] > y1:
            continue
        col = "#1565c0" if x["role"] == "support" else "#ef6c00"
        ax.axhspan(x["lo"], x["hi"], color=col, alpha=0.12 if x["tf"] == "1H" else 0.06)
        ax.text(n - 0.5, x["hi"], f"{x['tf']} {'demand' if x['role'] == 'support' else 'supply'}", fontsize=6, color=col, va="bottom",
                ha="right")


def lines(ax, locs, ix):
    for x in locs:
        if x.get("kind") != "line":
            continue
        ys = [x["p1"][1] + x["slope"] * (i - x["p1"][0]) for i in ix]
        ax.plot(range(len(ix)), ys, color="#6a1b9a", lw=0.8, ls="--")


def vol_pane(ax, vol, ix, marks=()):
    v = [float(vol[i]) if vol is not None and np.isfinite(vol[i]) else 0.0 for i in ix]
    ax.bar(range(len(ix)), v, color="#90a4ae", width=0.7)
    for k, col in marks:
        if 0 <= k < len(ix):
            ax.bar([k], [v[k]], color=col, width=0.7)
    ax.set_yticks([])


def day_charts(V, day, out, sym):
    A = V.levels.A
    ts = pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)
    ix = [i for i in range(len(ts)) if str(ts[i].date()) == day]
    if not ix:
        raise SystemExit(f"no bars on {day}")
    pre = list(range(max(0, ix[0] - 26), ix[0]))
    win = pre + ix
    rows, labels, vmarks = [], {}, []
    for t in win:
        f15, vr, ar = read_bar(V, t)
        rows.append({"t": int(t), "ts": str(ts[t]), "forms_15m": CF.public(f15), "volume": VR.public(vr), "areas": ar})
        for f in f15["forms"] + f15["states"]:
            if f["bars"][1] == t:
                labels.setdefault(t, []).append((f["name"], f["dir"], f["at"][0]["relation"]))
        cl = vr["climax"]
        for key in ("completed", "current"):
            r = cl.get(key)
            if r and r.get("found"):
                vmarks.append(r["bar"])
    t_last = win[-1]
    locs = CF.locations(V, t_last)
    vr_last = VR.read_volume(V, t_last)
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(18, 9), gridspec_kw={"height_ratios": [4, 1]}, sharex=True)
    candles(ax, A, win)
    y0, y1 = float(min(A["low"][win])), float(max(A["high"][win]))
    bands(ax, locs, len(win), y0, y1)
    lines(ax, locs, win)
    for k, t in enumerate(win):
        for n, (name, d, rel) in enumerate(labels.get(t, [])):
            y = (A["high"][t] if d <= 0 else A["low"][t])
            off = (1 + n) * (y1 - y0) * 0.025 * (1 if d <= 0 else -1)
            col = {"with": "#1b5e20", "against": "#b71c1c"}.get(rel, "#424242")
            ax.annotate(name.replace(" (long lower wick)", "").replace(" (long upper wick)", ""), (k, y), (k, y + off), fontsize=6,
                        color=col, ha="center", rotation=90 if len(name) > 14 else 0, va="bottom" if d <= 0 else "top")
    pv = vr_last["pullback_vs_impulse"]
    if pv.get("impulse") and pv.get("pullback"):
        pos = {t: k for k, t in enumerate(win)}
        im = pv["impulse"]
        if im["from_bar"] in pos and im["to_bar"] in pos:
            ax.plot([pos[im["from_bar"]], pos[im["to_bar"]]], [im["from_price"], im["to_price"]], color="#00838f", lw=1.5)
        pb = pv["pullback"]
        if pb["from_bar"] in pos:
            ax.plot([pos[pb["from_bar"]], pos[pb["to_bar"]]], [im["to_price"], float(A["close"][pb["to_bar"]])], color="#00838f", lw=1.5,
                    ls=":")
    ax.set_xlim(-1, len(win))
    ax.set_ylim(y0 - (y1 - y0) * 0.12, y1 + (y1 - y0) * 0.12)
    ev = "; ".join(vr_last["evidence"]) or "no volume evidence at the last bar"
    ax.set_title(f"{sym} 15M {day} — candle forms at a location (green = with the location, red = against, grey = indecision)\n"
                 f"volume at {str(ts[t_last])[11:16]}: {ev}", fontsize=9)
    pos = {t: k for k, t in enumerate(win)}
    vol_pane(axv, VR.volume_of(A), win, [(pos[b], "#d84315") for b in vmarks if b in pos])
    axv.set_xticks(range(0, len(win), 4))
    axv.set_xticklabels([str(ts[win[k]])[5:16] for k in range(0, len(win), 4)], rotation=60, fontsize=6)
    axv.set_title("near-month FUT volume per 15M bar (orange = climax candle)", fontsize=7)
    fig.tight_layout()
    p15 = os.path.join(out, f"{sym}_{day}_15M_candles_volume.png")
    fig.savefig(p15, dpi=110)
    plt.close(fig)
    # 1H: completed 1H candles, forms per candle (read when the hour completes)
    seen = {}
    for t in range(max(0, ix[0] - 26 * 4), ix[-1] + 1):
        r = CF.read_candle_forms(V, t, tf="1H")
        if r["candle"] >= 0 and r["candle"] not in seen:
            seen[r["candle"]] = r
    A1, span, j, ts1 = CF.h1_view(V, ix[-1])
    js = [x for x in range(max(0, j - 40), j + 1)]
    fig, ax = plt.subplots(figsize=(16, 7))
    candles(ax, A1, js)
    y0, y1 = float(min(A1["low"][js])), float(max(A1["high"][js]))
    bands(ax, locs, len(js), y0, y1)
    for k, jj in enumerate(js):
        r = seen.get(jj)
        for n, f in enumerate((r["forms"] + r["states"]) if r else []):
            d = f["dir"]
            y = A1["high"][jj] if d <= 0 else A1["low"][jj]
            off = (1 + n) * (y1 - y0) * 0.03 * (1 if d <= 0 else -1)
            col = {"with": "#1b5e20", "against": "#b71c1c"}.get(f["at"][0]["relation"], "#424242")
            ax.annotate(f["name"].split(" (")[0], (k, y), (k, y + off), fontsize=6, color=col, ha="center",
                        va="bottom" if d <= 0 else "top")
    ax.set_xticks(range(0, len(js), 3))
    ax.set_xticklabels([str(ts1[js[k]])[5:16] for k in range(0, len(js), 3)], rotation=60, fontsize=6)
    ax.set_ylim(y0 - (y1 - y0) * 0.12, y1 + (y1 - y0) * 0.12)
    ax.set_title(f"{sym} 1H to {day} — candle forms at a location (completed 1H candles only)", fontsize=9)
    fig.tight_layout()
    p1 = os.path.join(out, f"{sym}_{day}_1H_candles.png")
    fig.savefig(p1, dpi=110)
    plt.close(fig)
    jp = os.path.join(out, f"{sym}_{day}_reads.json")
    with open(jp, "w") as fh:
        json.dump({"rows": rows, "h1": {str(k): CF.public(v) for k, v in seen.items()}}, fh, default=str, indent=1)
    return [p15, p1, jp]


CONCEPTS = ["bullish engulfing", "bearish engulfing", "rejection", "momentum", "morning / evening star", "tweezer", "inside bar",
            "doji", "pullback lower volume", "pullback higher volume", "climax", "effort without result", "absorption",
            "commitment volume"]


def concept_hits(f15, vr, ar):
    hit = set()
    for f in f15["forms"] + f15["states"]:
        k = {"engulf": "bullish engulfing" if f["dir"] > 0 else "bearish engulfing", "rejection": "rejection", "momentum": "momentum",
             "star": "morning / evening star", "tweezer": "tweezer", "inside_bar": "inside bar", "doji": "doji"}.get(f["form"])
        if k:
            hit.add(k)
    st = vr["pullback_vs_impulse"]["state"]
    if st == "lower":
        hit.add("pullback lower volume")
    if st == "higher":
        hit.add("pullback higher volume")
    if vr["climax"]["state"] == "found":
        hit.add("climax")
    if str(vr["effort_result"]["state"]).startswith("effort without result"):
        hit.add("effort without result")
    if any(x["absorption"]["state"] == "absorbing" for x in ar):
        hit.add("absorption")
    if any(x["commitment_volume"]["state"] in ("above", "not_above") for x in ar):
        hit.add("commitment volume")
    return hit


def examples(V, out, sym, n_max, start_day=None):
    A = V.levels.A
    ts = pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)
    vol = VR.volume_of(A)
    have = [i for i in range(len(ts)) if vol is not None and np.isfinite(vol[i]) and vol[i] > 0]
    t0 = max(40, have[0] + 20) if have else 40
    found = {c: [] for c in CONCEPTS}
    last_t = {c: -99 for c in CONCEPTS}
    summary = []
    for t in range(t0, len(ts)):
        f15, vr, ar = read_bar(V, t)
        hits = concept_hits(f15, vr, ar)
        for c in hits:
            if len(found[c]) < n_max and t - last_t[c] >= 8:                # spread the examples (display choice, not a rule)
                found[c].append((t, f15, vr, ar))
                last_t[c] = t
        if all(len(v) >= n_max for v in found.values()):
            break
    paths = []
    for c, ex in found.items():
        if not ex:
            continue
        cols = 2
        rws = (len(ex) + 1) // 2
        fig, axs = plt.subplots(rws * 2, cols, figsize=(16, 4.2 * rws), gridspec_kw={"height_ratios": [3, 1] * rws})
        axs = np.atleast_2d(axs)
        for n, (t, f15, vr, ar) in enumerate(ex):
            r, k = (n // cols) * 2, n % cols
            ax, axv = axs[r][k], axs[r + 1][k]
            ix = list(range(max(0, t - 30), min(len(ts), t + 6)))
            candles(ax, A, ix, grey_after=t)
            pos = ix.index(t)
            ax.axvline(pos, color="#616161", lw=0.6, ls=":")
            y0, y1 = float(min(A["low"][ix])), float(max(A["high"][ix]))
            bands(ax, CF.locations(V, t), len(ix), y0, y1)
            lines(ax, CF.locations(V, t), ix)
            ev = [e for e in f15["evidence"]] + vr["evidence"] + [x["absorption"]["evidence"] for x in ar if x["absorption"].get("evidence")]
            ev += [f"commitment volume {x['commitment_volume']['state']} ({x['commitment_volume'].get('vol_vs')}, x"
                   f"{x['commitment_volume'].get('vol_mult')})" for x in ar if x["commitment_volume"]["state"] in ("above", "not_above")]
            pv = vr["pullback_vs_impulse"]
            if pv.get("impulse") and c.startswith("pullback"):
                im, pb = pv["impulse"], pv["pullback"]
                if im["from_bar"] in ix:
                    ax.plot([ix.index(im["from_bar"]), ix.index(im["to_bar"])], [im["from_price"], im["to_price"]], color="#00838f", lw=1.5)
                ax.plot([ix.index(im["to_bar"]) if im["to_bar"] in ix else 0, pos], [im["to_price"], float(A["close"][t])], color="#00838f",
                        lw=1.5, ls=":")
            marks = [(pos, "#d84315")]
            for key in ("completed", "current"):
                rr = vr["climax"].get(key)
                if c == "climax" and rr and rr.get("found") and rr["bar"] in ix:
                    marks.append((ix.index(rr["bar"]), "#6a1b9a"))
            ax.set_title(f"{str(ts[t])[:16]} · " + " | ".join(ev)[:230], fontsize=6)
            ax.set_xticks([])
            ax.set_ylim(y0 - (y1 - y0) * 0.1, y1 + (y1 - y0) * 0.1)
            vol_pane(axv, vol, ix, marks)
            axv.set_xticks([])
        for n in range(len(ex), rws * cols):
            r, k = (n // cols) * 2, n % cols
            axs[r][k].axis("off")
            axs[r + 1][k].axis("off")
        fig.suptitle(f"{sym} 15M — {c}: {len(ex)} examples (marked bar = read at its close; grey = later candles, shown for review only)",
                     fontsize=10)
        fig.tight_layout()
        p = os.path.join(out, f"{sym}_{c.replace(' / ', '_').replace(' ', '_')}.png")
        fig.savefig(p, dpi=100)
        plt.close(fig)
        paths.append(p)
        summary.append({"concept": c, "examples": [str(ts[t]) for t, *_ in ex]})
    with open(os.path.join(out, f"{sym}_examples.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    missing = [c for c, v in found.items() if not v]
    return paths, summary, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--inputs")
    ap.add_argument("--day")
    ap.add_argument("--m15", nargs="*")
    ap.add_argument("--daily", nargs="*")
    ap.add_argument("--futures", nargs="*")
    ap.add_argument("--out", required=True)
    ap.add_argument("--examples", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.inputs:
        m15, daily, fut = load_nifty(a.inputs)
    else:
        m15, daily, fut = load_bn(a.m15, a.daily, a.futures)
    V = build(m15, daily, fut)
    print("volume:", V.vol_src)
    if a.day:
        print("\n".join(day_charts(V, a.day, a.out, a.symbol)))
    if a.examples and not a.day:
        paths, summary, missing = examples(V, a.out, a.symbol, a.examples)
        print("\n".join(paths))
        print("missing concepts:", missing)


if __name__ == "__main__":
    main()
