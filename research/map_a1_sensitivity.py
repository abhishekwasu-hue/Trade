"""research/map_a1_sensitivity.py — नकाशा A1: "अंदाज" आकड्यांची IS sensitivity (किमान 3 मूल्ये). **फक्त अहवाल; मूल्य निवडत नाही.**

IS मधून random दिवस (seed नोंद, data_policy ने). प्रत्येक बंद 15M bar वर Simple Core चा context (zones, trend, MR) **एकदाच** मोजून,
मग प्रत्येक मूल्यासाठी फक्त detect पुन्हा (दिवसाला नवा Tracker). निकाल (फक्त गट पाडण्यासाठी, hindsight): spot SL =
structural_invalidation ∓ 0.25 MR, target = 3R, पुढचे ≤ 3 sessions (15M) — TARGET / SL / TIME; expectancy R (TARGET +3, SL −1, TIME
close वरून).

    python3 research/map_a1_sensitivity.py --is-data data/nifty50_1min.parquet --days 40 --out docs/reports/situation_map
"""
import argparse
import json
import os
import random
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP            # noqa: E402

SEED = 20261009
GRID = {"commitment_vs_pause": (1.3, 1.5, 2.0), "area_tol_mr": (0.2, 0.3, 0.4), "commit_strength_min_mr": (1.0, 1.2, 1.5),
        "pause_range_max_mr": (0.8, 1.0, 1.2), "pause_body_max": (0.4, 0.5, 0.6), "commit_close_max": (0.2, 0.3, 0.4)}


def outcome(m15, t_end, sig, mr, buf_mr=0.25, horizon=3):
    side, e = int(sig["side"]), float(sig["trigger_price"])
    sl = float(sig["ref_levels"]["structural_invalidation"]) + (buf_mr * float(mr) if side < 0 else -buf_mr * float(mr))
    risk = abs(e - sl)
    if risk <= 0:
        return "BAD", 0.0
    tg = e + side * 3 * risk
    f = m15[pd.to_datetime(m15["timestamp"]) >= pd.Timestamp(t_end)]
    days = pd.to_datetime(f["timestamp"]).dt.normalize().unique()[:horizon]
    f = f[pd.to_datetime(f["timestamp"]).dt.normalize().isin(days)]
    for r in f.itertuples():
        if (r.high >= sl) if side < 0 else (r.low <= sl):
            return "SL", -1.0
        if (r.low <= tg) if side < 0 else (r.high >= tg):
            return "TARGET", 3.0
    last = float(f["close"].iloc[-1]) if len(f) else e
    return "TIME", round((last - e) * side / risk, 2)


def contexts(raw, days, log=print):
    """प्रत्येक दिवस ⇒ [(asof, trig, zones, ctx, mr)] (signal_at एकदाच)."""
    from chart_reader import setups as SU
    from simple_core import engine as EN
    out = {}
    for n, d in enumerate(days):
        m1 = raw[(raw["timestamp"] >= d - pd.Timedelta(days=130)) & (raw["timestamp"] < d + pd.Timedelta(days=1))].reset_index(drop=True)
        mem, bars = SU.LineMemory(), []
        for t in pd.date_range(d + pd.Timedelta(hours=9, minutes=15), d + pd.Timedelta(hours=15, minutes=15), freq="15min"):
            asof = t + pd.Timedelta(minutes=15)
            r = EN.signal_at(m1, asof, memory=mem)
            if r.get("ctx") is not None:
                bars.append((asof, r["trig"], r["zones"], r["ctx"], r["mr"]))
        out[d] = bars
        log(f"  {n + 1}/{len(days)} {d:%Y-%m-%d}: {len(bars)} bars")
    return out


def run_variant(ctxs, m15, s):
    from simple_core import engine as EN
    sigs = []
    for d, bars in ctxs.items():
        tr = EN.Tracker()
        for asof, trig, zones, ctx, mr in bars:
            r = EN.detect(trig, zones, ctx, mr, s, tr)
            if r.get("signal"):
                res, R = outcome(m15, asof, r["signal"], mr)
                sigs.append({"date": f"{d:%Y-%m-%d}", "t": f"{asof:%H:%M}", "side": r["signal"]["side"], "result": res, "R": R})
    return sigs


def summarize(sigs):
    n = len(sigs)
    c = pd.Series([x["result"] for x in sigs]).value_counts().to_dict() if n else {}
    return {"signals": n, "TARGET": c.get("TARGET", 0), "SL": c.get("SL", 0), "TIME": c.get("TIME", 0),
            "exp_R": round(float(np.mean([x["R"] for x in sigs])), 2) if n else None}


def main(argv=None):
    import market_state as MS
    from simple_core import settings as SS
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--days", type=int, default=40)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    raw = pd.read_parquet(a.is_data) if a.is_data.endswith(".parquet") else pd.read_csv(a.is_data, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    raw = DP.filter_allowed(raw, "golden")
    all_days = sorted(pd.to_datetime(raw["timestamp"]).dt.normalize().unique())
    pool = [pd.Timestamp(d) for d in all_days if pd.Timestamp("2015-06-01") <= pd.Timestamp(d) <= pd.Timestamp("2021-12-31")]
    days = sorted(random.Random(a.seed).sample(pool, a.days))
    ctxs = contexts(raw, days)
    m15 = MS.full_frames(raw[(raw["timestamp"] >= days[0] - pd.Timedelta(days=5)) & (raw["timestamp"] < days[-1] + pd.Timedelta(days=8))])["15m"]
    base = SS.engine_settings()
    res = {"seed": a.seed, "days": [f"{d:%Y-%m-%d}" for d in days], "baseline": base, "grid": {}}
    base_sigs = run_variant(ctxs, m15, base)
    bkey = {(x["date"], x["t"]) for x in base_sigs}
    for k, vals in GRID.items():
        res["grid"][k] = {}
        for v in vals:
            sg = run_variant(ctxs, m15, {**base, k: v})
            keys = {(x["date"], x["t"]) for x in sg}
            jac = round(len(keys & bkey) / len(keys | bkey), 2) if (keys | bkey) else 1.0
            res["grid"][k][str(v)] = {**summarize(sg), "jaccard_vs_base": jac}
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "A1_sensitivity.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    L = ["# नकाशा A1: \"अंदाज\" आकड्यांची IS sensitivity (फक्त अहवाल)", "",
         f"IS random {a.days} दिवस (seed {a.seed}). निकाल hindsight फक्त गटांसाठी: SL = structural invalidation ∓ 0.25 MR, target 3R, ≤ 3 "
         "sessions. **कोणतंही मूल्य निवडलं नाही.**", "", f"Baseline: {summarize(base_sigs)}", ""]
    for k, d in res["grid"].items():
        L += [f"## `{k}` (आत्ता {base[k]})", "", "| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |", "|---|---|---|---|---|---|---|"]
        L += [f"| {v} | {x['signals']} | {x['TARGET']} | {x['SL']} | {x['TIME']} | {x['exp_R']} | {x['jaccard_vs_base']} |" for v, x in d.items()]
        L.append("")
    L += ["**सापेक्ष तुलनेचा प्रस्ताव (Abhi निर्णय):** area_tol / commit strength / pause range आधीच MR (median range, अलीकडच्या 20 bars) च्या पटीत "
          "आहेत — म्हणजे बाजाराच्या अलीकडच्या चालीशी सापेक्ष. commitment_vs_pause हा pause bars शी सापेक्ष. उरलेला प्रश्न: MR ऐवजी impulse "
          "आकाराशी (उदा. touch = impulse च्या x%) तुलना हवी का — अहवालानंतर ठरवायचं."]
    open(os.path.join(a.out, "A1_sensitivity.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:6]))


if __name__ == "__main__":
    main()
