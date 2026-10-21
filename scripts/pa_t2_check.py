"""PA standard track T2 — real-data check + verification charts (private: write them to trade-data, never to this repo).

Reads (never decides): decision3/area_types (base type + departure), decision3/liquidity_pa (obvious extremes + inducement),
decision3/confluence_pa (imbalances, Fib only as confluence, HTF levels, per-area confluence list).

  python3 scripts/pa_t2_check.py nifty --inputs <dir with engine_NIFTY_*.csv.gz> --out <dir>
  python3 scripts/pa_t2_check.py banknifty --data <trade-data/banknifty> --out <dir> [--n 8]
"""
import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from decision3 import area_types as AT  # noqa: E402
from decision3 import confluence_pa as CP  # noqa: E402
from decision3 import levels as LV  # noqa: E402
from decision3 import liquidity_pa as LP  # noqa: E402


# ------------------------------------------------------------------------------------------------ data
def _read(path):
    f = pd.read_csv(path)
    for c in ("timestamp", "bar_end"):
        if c in f.columns:
            f[c] = pd.to_datetime(f[c])
    return f


def nifty_inputs(d):
    rd = lambda n: _read(os.path.join(d, f"engine_NIFTY_{n}.csv.gz"))  # noqa: E731
    m15 = rd("m15")
    return {"m15": m15.drop(columns=[c for c in ("volume",) if c in m15.columns]), "m1": rd("m1"), "daily": rd("daily"),
            "ltf": rd("ltf5"), "fut": rd("fut5")}


def banknifty_inputs(d):
    m15 = _read(os.path.join(d, "BANKNIFTY_15M.csv.gz"))[["timestamp", "open", "high", "low", "close"]]
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    daily = _read(os.path.join(d, "BANKNIFTY_D.csv.gz"))[["timestamp", "open", "high", "low", "close"]]
    daily["timestamp"] = daily["timestamp"].dt.normalize()
    daily = daily[daily["timestamp"] < m15["timestamp"].max().normalize() + pd.Timedelta(days=1)]
    daily["bar_end"] = daily["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    return {"m15": m15, "m1": None, "daily": daily.reset_index(drop=True), "ltf": None, "fut": None}


def build(inp, upto=None, symbol=None):
    from decision3 import engine as E3
    from decision3 import history as HI
    m15 = inp["m15"]
    kw = {"sealed": HI.sealed_fn(symbol)} if symbol else {}
    if upto is not None:                                                   # truncated inputs (no-look-ahead check)
        end = m15["bar_end"].iloc[upto]
        m15 = m15.iloc[:upto + 1].reset_index(drop=True)
        cut = lambda f, col="timestamp": None if f is None else f[f[col] < end].reset_index(drop=True)  # noqa: E731
        inp = {**inp, "m1": cut(inp["m1"]), "ltf": cut(inp["ltf"]), "fut": cut(inp["fut"]),
               "daily": inp["daily"][inp["daily"]["bar_end"] <= end].reset_index(drop=True)}
    if inp.get("ltf") is not None:
        kw["ltf"] = inp["ltf"]
    if inp.get("fut") is not None:
        kw["futures"] = inp["fut"]
    return E3.V22(m15, inp.get("m1"), inp["daily"], **kw)


def read_all(V, t):
    return {"areas": AT.read_area_types(V, t), "liq": LP.read_liquidity(V, t), "conf": CP.read_confluence(V, t)}


# ------------------------------------------------------------------------------------------------ chart
ROLE_COL = {LV.SUP: "#2f9e44", LV.RES: "#e03131"}


def _frame(V, t, tf, sessions):
    lv = V.levels
    if tf == "1H":
        j = int(lv.h1_of[t])
        fr = lv.h1.iloc[:j + 1].copy().reset_index(drop=True)
        fr.loc[len(fr) - 1, ["open", "high", "low", "close"]] = list(lv._h1_upto(j, t))
    else:
        fr = V.m15.iloc[:t + 1][["timestamp", "open", "high", "low", "close"]].copy().reset_index(drop=True)
    days = pd.to_datetime(fr["timestamp"]).dt.normalize()
    keep = sorted(days.unique())[-sessions:]
    return fr[days.isin(keep)].reset_index(drop=True)


def _x(fr, ts):
    if ts is None:
        return 0
    ix = np.searchsorted(pd.to_datetime(fr["timestamp"]).to_numpy(), np.datetime64(pd.Timestamp(ts)), side="right") - 1
    return max(int(ix), 0)


def render(V, t, tf, title, path, layers=("areas", "liquidity", "confluence"), sessions=None, rd=None):
    sessions = sessions or (8 if tf == "1H" else 3)
    rd = rd or read_all(V, t)
    fr = _frame(V, t, tf, sessions)
    n = len(fr)
    fig, ax = plt.subplots(figsize=(15, 7.5))
    for i, r in fr.iterrows():
        up = r["close"] >= r["open"]
        col = "#2f9e44" if up else "#e03131"
        ax.plot([i, i], [r["low"], r["high"]], color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((i - 0.3, min(r["open"], r["close"])), 0.6, max(abs(r["close"] - r["open"]), 1e-6), color=col))
    lo, hi = float(fr["low"].min()), float(fr["high"].max())
    pad = (hi - lo) * 0.15
    ylo, yhi = lo - pad, hi + pad
    vis = lambda a, b: not (max(a, b) < ylo or min(a, b) > yhi)  # noqa: E731
    right = n + 0.5
    texts = []
    c = float(V.levels.A["close"][t])
    if "confluence" in layers:
        for x in rd["conf"]["htf_levels"]:
            if x["kind"] == "band" and vis(x["lo"], x["hi"]):                # HTF band: a strip at the right edge (no full-width clutter)
                ax.add_patch(plt.Rectangle((right - 1.2, x["lo"]), 1.0, max(x["hi"] - x["lo"], (yhi - ylo) / 400),
                                           color="#495057" if x["tf"] == "W" else "#868e96", alpha=0.6, lw=0))
                texts.append(((x["lo"] + x["hi"]) / 2, f"{LV.TF_WORD[x['tf']]} {'supply' if x['role'] == LV.RES else 'demand'} "
                              f"{x['lo']:,.0f}–{x['hi']:,.0f}", "#495057"))
        for g in rd["conf"]["fvg"]:
            if g["tf"] != tf:
                continue
            a, b = g["remaining"] or (g["lo"], g["hi"])
            if not vis(a, b) or _x(fr, g["ts"]) == 0 and pd.Timestamp(g["ts"]) < pd.Timestamp(fr["timestamp"].iloc[0]):
                continue
            x0 = _x(fr, g["ts"])
            ax.add_patch(plt.Rectangle((x0, a), right - x0, b - a, color="#7048e8", alpha=0.25 if g["state"] == "open" else 0.12, lw=0))
            ax.text(x0, b, f"FVG {g['state']}", fontsize=6, color="#5f3dc4", va="bottom")
        imp = rd["conf"]["fib"]["impulse"]
        for lvl in rd["conf"]["fib"]["levels"]:
            if vis(lvl["price"], lvl["price"]):
                ax.axhline(lvl["price"], color="#f08c00", ls="-.", lw=1.2)
                on = ", ".join("area" if o["what"] == "area" else "liquidity" for o in lvl["on"])
                texts.append((lvl["price"], f"Fib {lvl['ratio'] * 100:g}% on {on} ({imp['from_price']:,.0f}→{imp['to_price']:,.0f})",
                              "#e67700"))
    if "areas" in layers:
        for x in rd["areas"]:
            if x["tf"] != "1H" or not vis(x["lo"], x["hi"]):
                continue
            b = x["base"]
            x0 = _x(fr, b.get("from_ts")) if b.get("from_ts") else 0
            col = ROLE_COL.get(x["role"], "#495057")
            dashed = x["state"] in ("BROKEN",)
            ax.add_patch(plt.Rectangle((x0, x["lo"]), right - x0, x["hi"] - x["lo"], facecolor=col, alpha=0.12 if not dashed else 0.04,
                                       edgecolor=col, ls="--" if dashed else "-", lw=0.8))
            dep = x["departure"]
            lab = (b.get("type") or b.get("type_partial") or "?") + (f" · {dep['strength']}" if dep.get("strength") else "") + \
                (" · BOS" if dep.get("bos") else "") + (f" · {x['state']}" if x["state"] != "ACTIVE" else "")
            fb = x.get("flip_base")
            if fb and fb.get("type"):
                lab += f" · flip {fb['type']}"
            texts.append(((x["lo"] + x["hi"]) / 2, lab, col))
    if "liquidity" in layers:
        for x in rd["liq"]["obvious"]:
            if x["tf"] != "15M" or not vis(x["price"], x["price"]):
                continue
            x0 = _x(fr, x["ts"])
            ax.plot([x0, right], [x["price"], x["price"]], color="#1c7ed6", ls=":", lw=1.1)
            texts.append((x["price"], f"{'BSL' if x['side'] == 'buy' else 'SSL'}" + (" EQ" if x["src"] == "equal" else "") +
                          (" outer" if x["outer"] else "") + (" nearest" if x["nearest"] else ""), "#1c7ed6"))
        ahead = {}
        for x in rd["liq"]["inducement"]:
            if x["tf"] != "1H" or not x.get("minor"):
                continue
            k = x["role"]
            dist = abs((x["lo"] if k == LV.RES else x["hi"]) - c)
            if k not in ahead or dist < ahead[k][0]:
                ahead[k] = (dist, x)
        for _, x in ahead.values():
            m = x["minor"]
            if not vis(m["price"], m["price"]):
                continue
            x0, x1 = _x(fr, m["ts"]), (_x(fr, x["taken_at"]) if x.get("taken_at") else n - 1)
            ax.plot([x0, x1], [m["price"], m["price"]], color="#d6336c", lw=1.6)
            ax.text(x0, m["price"], f" IDM {x['state']}" + (" → area reached" if x.get("taken_first") else ""), fontsize=7,
                    color="#c2255c", va="bottom")
    texts = sorted((z for z in texts if ylo <= z[0] <= yhi), key=lambda z: z[0])
    step = (yhi - ylo) / 48
    placed = []
    for y, s, col in texts:                                                # stack upward, never past the top (then dropped)
        yy = y if not placed or y - placed[-1] > step else placed[-1] + step
        if yy > yhi:
            continue
        ax.text(right + 0.3, yy, s, fontsize=6.3, color=col, va="center")
        placed.append(yy)
    ax.axhline(c, color="#212529", lw=0.6)
    ax.set_xlim(-1, right + max(14, n * 0.22))
    ax.set_ylim(ylo, yhi)
    every = max(1, n // 12)
    ax.set_xticks(range(0, n, every))
    ax.set_xticklabels([pd.Timestamp(x).strftime("%d %b %H:%M") for x in fr["timestamp"].iloc[::every]], rotation=30, fontsize=7)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ summaries
def summary(V, t, rd):
    c = float(V.levels.A["close"][t])
    near = sorted([x for x in rd["areas"] if x["tf"] == "1H" and x["state"] not in ("BROKEN",)],
                  key=lambda x: min(abs(x["lo"] - c), abs(x["hi"] - c)))[:6]
    return {"t": int(t), "ts": str(V.levels.ts.iloc[t]), "close": c,
            "areas_1h_nearest": [{"id": x["id"], "lo": x["lo"], "hi": x["hi"], "state": x["state"], "evidence": x["evidence"]} for x in near],
            "obvious_15m": [x["evidence"] for x in rd["liq"]["obvious"] if x["tf"] == "15M"],
            "inducement_1h": [x["evidence"] for x in rd["liq"]["inducement"] if x["tf"] == "1H"],
            "fvg_open_partly": {tf: sum(1 for g in rd["conf"]["fvg"] if g["tf"] == tf) for tf in ("15M", "1H")},
            "fib": rd["conf"]["fib"],
            "area_confluence_1h": [{"id": a["id"], "label": a["label"]} for a in rd["conf"]["areas"] if a["tf"] == "1H" and a["label"]
                                   and a["id"] in {x["id"] for x in near}]}


def _strip(x):
    """A read with the bar-index fields dropped (a truncated rebuild re-indexes nothing, but keep the comparison to facts)."""
    return json.loads(json.dumps(x, default=str))


def run_nifty(a):
    warnings.filterwarnings("ignore")
    inp = nifty_inputs(a.inputs)
    V = build(inp, symbol="NIFTY")
    os.makedirs(a.out, exist_ok=True)
    ts = pd.to_datetime(V.m15["timestamp"])
    day = ts.iloc[-1].normalize()
    bars = [i for i in range(len(ts)) if ts.iloc[i].normalize() == day]
    t = bars[-1]
    rd = read_all(V, t)
    title = f"NIFTY {day.date()} {ts.iloc[t]:%H:%M} — PA T2: base type · departure · liquidity · inducement · FVG · Fib-on-area · HTF"
    render(V, t, "1H", title + " (1H)", os.path.join(a.out, "nifty_21oct_1H.png"), rd=rd)
    render(V, t, "15M", title + " (15M)", os.path.join(a.out, "nifty_21oct_15M.png"), rd=rd)
    for name, lay in (("areas", ("areas",)), ("liquidity", ("liquidity",)), ("confluence", ("confluence",))):
        render(V, t, "1H", f"NIFTY {day.date()} {ts.iloc[t]:%H:%M} — {name} only (1H)", os.path.join(a.out, f"nifty_21oct_1H_{name}.png"),
               layers=lay, rd=rd)
    out = {"symbol": "NIFTY", "day": str(day.date()), "last": summary(V, t, rd), "per_bar": []}
    for i in bars:
        r = read_all(V, i)
        out["per_bar"].append({"ts": str(ts.iloc[i]), "inducement_taken_first": sum(1 for x in r["liq"]["inducement"] if x.get("taken_first")),
                               "fib_levels": [(x["ratio"], x["price"]) for x in r["conf"]["fib"]["levels"]],
                               "fib_why": r["conf"]["fib"]["why"]})
    checks = []
    for i in (bars[len(bars) // 2], bars[-1]):                             # no-look-ahead on real data: a rebuild on bars ≤ i
        Vi = build(inp, upto=i, symbol="NIFTY")
        same = _strip(read_all(V, i)) == _strip(read_all(Vi, i))
        checks.append({"ts": str(ts.iloc[i]), "same_as_truncated_rebuild": same})
    out["no_lookahead"] = checks
    json.dump(out, open(os.path.join(a.out, "nifty_21oct_summary.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(out["last"], indent=1, ensure_ascii=False, default=str)[:6000])
    print("no-look-ahead:", checks)


def run_banknifty(a):
    warnings.filterwarnings("ignore")
    V = build(banknifty_inputs(a.data), symbol="BANKNIFTY")
    os.makedirs(a.out, exist_ok=True)
    ts = pd.to_datetime(V.m15["timestamp"])
    cand = [i for i in range(300, len(ts)) if ts.iloc[i].minute == 15 and 10 <= ts.iloc[i].hour <= 14]   # one look per hour
    picks = {"areas": [], "inducement": [], "confluence": []}
    seen = {k: set() for k in picks}
    stats = {"inducement_taken_first": 0, "fib_on_area": 0, "looks": 0}
    for i in cand:
        day = ts.iloc[i].normalize()
        rl = LP.read_liquidity(V, i)
        rc = CP.read_confluence(V, i)
        stats["looks"] += 1
        fresh = [x for x in rl["inducement"] if x["tf"] == "1H" and x.get("taken_first") and x.get("reached_at")
                 and pd.Timestamp(x["reached_at"]).normalize() == day]          # the area visit began this session
        stats["inducement_taken_first"] += bool(fresh)
        stats["fib_on_area"] += bool(rc["fib"]["levels"])
        if fresh and day not in seen["inducement"] and len(picks["inducement"]) < a.n:
            picks["inducement"].append(i)
            seen["inducement"].add(day)
        if rc["fib"]["levels"] and day not in seen["confluence"] and len(picks["confluence"]) < a.n:
            picks["confluence"].append(i)
            seen["confluence"].add(day)
    spare = [i for i in cand[::25] if ts.iloc[i].normalize() not in seen["inducement"]]
    for i in spare:                                                        # fill up with taken-not-reached / resting looks
        if len(picks["inducement"]) >= a.n:
            break
        rl = LP.read_liquidity(V, i)
        near = [x for x in rl["inducement"] if x["tf"] == "1H" and x["state"] in ("taken", "resting")]
        if near:
            picks["inducement"].append(i)
            seen["inducement"].add(ts.iloc[i].normalize())
    picks["inducement"].sort()
    days = sorted(set(ts.iloc[cand].dt.normalize()))
    for k in range(a.n):                                                   # base types / departure: evenly spread looks
        day = days[min(len(days) - 1, k * len(days) // a.n)]
        picks["areas"].append(max(i for i in cand if ts.iloc[i].normalize() == day))
    out = {"symbol": "BANKNIFTY", "stats": stats, "charts": {}}
    for k, idx in picks.items():
        out["charts"][k] = []
        lay = {"areas": ("areas",), "inducement": ("areas", "liquidity"), "confluence": ("areas", "confluence")}[k]
        for i in idx:
            rd = read_all(V, i)
            name = f"bn_{k}_{ts.iloc[i]:%Y%m%d_%H%M}.png"
            render(V, i, "1H", f"BANKNIFTY {ts.iloc[i]:%Y-%m-%d %H:%M} — PA T2 {k} (1H)", os.path.join(a.out, name), layers=lay, rd=rd)
            out["charts"][k].append({"chart": name, **summary(V, i, rd)})
    json.dump(out, open(os.path.join(a.out, "banknifty_summary.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(stats), {k: len(v) for k, v in picks.items()})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("nifty")
    n.add_argument("--inputs", required=True)
    n.add_argument("--out", required=True)
    b = sub.add_parser("banknifty")
    b.add_argument("--data", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--n", type=int, default=8)
    a = ap.parse_args(argv)
    (run_nifty if a.cmd == "nifty" else run_banknifty)(a)


if __name__ == "__main__":
    main()
