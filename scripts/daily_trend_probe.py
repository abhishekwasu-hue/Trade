"""Daily trend probe (dump फक्त, नियम नाही): Daily candles वर DC swings (k पर्याय), confirmed H / L, Daily trend कोणता आणि कधीपासून,
आणि 1H trend शी जुळतो का (त्याच दिवशी --asof-time पर्यंत बंद candles).

उदा.: python3 scripts/daily_trend_probe.py --instrument BANKNIFTY --tf-dir <trade-data>/banknifty --out-dir <out>
Output: daily_pivots_k.csv, daily_trend_segments.csv, daily_vs_1h.csv, daily_trend_probe.json, daily_trend_probe.md
k पर्याय = swings2 K_OPTIONS (D1 / D2 कमी · default · जास्त); default k (D1 = 4, D2 = 6) बदलत नाही.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instruments as INS  # noqa: E402
from decision2 import charts7 as D7  # noqa: E402
from mtf import adapter as MA  # noqa: E402
from review7 import method as RM  # noqa: E402
from swings2 import engine as SE  # noqa: E402
from swings2 import settings as SS  # noqa: E402
from swings2 import structure as ST  # noqa: E402


def k_sets():
    """(नाव, {degree: k}) — K_OPTIONS मधले D1 / D2 चे कमी · default · जास्त (इतर degrees default)."""
    base = dict(SS.DEFAULTS["k"])
    out = []
    for i, nm in enumerate(("कमी", "default", "जास्त")):
        k = dict(base)
        k[1], k[2] = SS.K_OPTIONS[1][i], SS.K_OPTIONS[2][i]
        out.append((f"{nm} (D1 {k[1]:g} / D2 {k[2]:g})", k))
    return out


def d3_trend(res, t):
    seg = res["segments"].get(pd.Timestamp(res["m15"]["timestamp"].iloc[t]).normalize())
    return ST.trend_of([p for p in res["pivots"].get(3, []) if p.confirm_bar <= t and not p.warmup
                        and res["segments"].get(pd.Timestamp(p.ts).normalize()) == seg])


def runs(states, real, deg, kname):
    out, cur = [], None
    for t, st in enumerate(states):
        tr = st["trend"]
        if cur is None or cur["trend"] != tr:
            if cur is not None:
                out.append(cur)
            cur = {"k": kname, "degree": f"D{deg}", "trend": tr, "from": str(real[t].date()), "to": str(real[t].date()), "candles": 0}
        cur["to"] = str(real[t].date())
        cur["candles"] += 1
    if cur is not None:
        out.append(cur)
    return out


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r)) or ["—"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default=None, choices=INS.names())
    ap.add_argument("--tf-dir", required=True, help="<INSTR>_D.csv.gz आणि <INSTR>_1H.csv.gz असलेला folder")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--asof-time", default="15:30")
    a = ap.parse_args(argv)
    ins = INS.set_current(a.instrument)
    MA.check_tf_allowed(ins, "D")
    m15, real = MA.frame(os.path.join(a.tf_dir, f"{ins}_D.csv.gz"), "D", ins)
    os.makedirs(a.out_dir, exist_ok=True)
    prow, srow, summ = [], [], {"instrument": ins, "daily_candles": len(m15), "first": str(real.iloc[0].date()),
                                "last": str(real.iloc[-1].date()), "k_options": {}}
    default_struct = None
    for kname, k in k_sets():
        res = SE.build(m15, None, s={"k": k})
        struct, _ = ST.all_structure(res)
        n = len(m15)
        for d in sorted(res["pivots"]):
            ps = [p for p in res["pivots"][d] if not p.warmup]
            for p in res["pivots"][d]:
                prow.append({"k": kname, "degree": f"D{d}", "kind": p.kind, "label": "warm-up" if p.warmup else D7._lbl(ps, p),
                             "price": round(p.price, 2), "date": str(real[p.bar].date()), "confirmed_on": str(real[p.confirm_bar].date()),
                             "warmup": bool(p.warmup)})
        cur = {}
        for d in sorted(struct):
            rr = runs(struct[d]["states"], real, d, kname)
            srow += rr
            cur[f"D{d}"] = {"trend": rr[-1]["trend"], "since": rr[-1]["from"], "candles": rr[-1]["candles"],
                            "protected": struct[d]["states"][n - 1].get("protected")}
        cur["D3"] = {"trend": d3_trend(res, n - 1)}
        nw = {f"D{d}": {"H": sum(1 for p in res["pivots"][d] if not p.warmup and p.kind == "H"),
                        "L": sum(1 for p in res["pivots"][d] if not p.warmup and p.kind == "L")} for d in sorted(res["pivots"])}
        last = {}
        for d in (1, 2):
            for kind in ("H", "L"):
                ps = [p for p in res["pivots"].get(d, []) if not p.warmup and p.kind == kind]
                if ps:
                    last[f"D{d}_{kind}"] = {"price": round(ps[-1].price, 2), "date": str(real[ps[-1].bar].date()),
                                            "confirmed_on": str(real[ps[-1].confirm_bar].date())}
        summ["k_options"][kname] = {"k": {f"D{d}": k[d] for d in (1, 2, 3)}, "now": cur, "confirmed_nonwarmup": nw, "last_confirmed": last}
        if kname.startswith("default"):
            default_struct = (res, struct)
    # 1H शी जुळणी (default k)
    C1 = MA.build(MA.load_tf(os.path.join(a.tf_dir, f"{ins}_1H.csv.gz")), "1H", ins)
    res, struct = default_struct
    vrow, cnt = [], Counter()
    h0 = pd.Timestamp(C1.real_ts.iloc[0]).normalize()
    d_end = pd.to_datetime(m15["real_end"]).reset_index(drop=True)
    for day in sorted(set(pd.to_datetime(real).dt.normalize())):
        if day < h0:
            continue
        asof = day + pd.Timedelta(a.asof_time + ":00")
        th = MA.bar_at(C1, asof)
        ok = (d_end <= asof).to_numpy().nonzero()[0]                             # Daily: asof पर्यंत **बंद** candle (अपूर्ण दिवस नाही)
        if th is None or not len(ok):
            continue
        t = int(ok[-1])
        dd = {d: struct[d]["states"][t]["trend"] for d in sorted(struct)}
        hdeg, htr, hdir = RM.trend(C1, th)
        dtr = dd.get(2, "unknown")
        dtr = dtr if dtr != "unknown" else dd.get(1, "unknown")
        if dtr == "unknown" or htr == "unknown":
            ag = "NA"
        else:
            ag = "हो" if dtr == htr else "नाही"
        cnt[ag] += 1
        vrow.append({"date": str(day.date()), "D_D1": dd.get(1), "D_D2": dd.get(2), "D_D3": d3_trend(res, t), "daily_used": dtr,
                     "1H_trend": htr, "1H_degree": f"D{hdeg}" if hdeg else "—", "1H_state": C1.trk[1].state(th).get("state"), "जुळतं": ag})
    summ["vs_1h"] = {"days": len(vrow), "हो": cnt["हो"], "नाही": cnt["नाही"], "NA": cnt["NA"],
                     "rule": "Daily D2 trend (unknown ⇒ D1) vs 1H सर्वोच्च ओळखलेला degree trend (review7 ①), त्याच दिवशी "
                             f"{a.asof_time} पर्यंत बंद candles"}
    write_csv(os.path.join(a.out_dir, "daily_pivots_k.csv"), prow)
    write_csv(os.path.join(a.out_dir, "daily_trend_segments.csv"), srow)
    write_csv(os.path.join(a.out_dir, "daily_vs_1h.csv"), vrow)
    json.dump(summ, open(os.path.join(a.out_dir, "daily_trend_probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# Daily trend probe · {ins} · {summ['first']} – {summ['last']} ({summ['daily_candles']} Daily candles)", ""]
    for kname, x in summ["k_options"].items():
        now = x["now"]
        md.append(f"- **k {kname}**: " + " · ".join(f"{d} {v['trend']}" + (f" ({v['since']} पासून, {v['candles']} candles)" if "since" in v else "")
                                                    for d, v in now.items())
                  + " · confirmed (warm-up नंतर) " + ", ".join(f"{d} H{v['H']}/L{v['L']}" for d, v in x["confirmed_nonwarmup"].items()))
    v = summ["vs_1h"]
    md += ["", f"- **1H शी जुळणी** ({v['days']} दिवस): हो {v['हो']} · नाही {v['नाही']} · NA {v['NA']} — {v['rule']}"]
    open(os.path.join(a.out_dir, "daily_trend_probe.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))
    return summ


if __name__ == "__main__":
    main()
