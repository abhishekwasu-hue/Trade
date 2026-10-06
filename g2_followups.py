"""
g2_followups.py
---------------
🎓 G2 नंतरच्या (वापरकर्त्याच्या 2026-10-06 च्या निर्णयानुसार) तीन report-only चाचण्या. NIFTY offline 1M (2015 → 2024-03). Sealed holdout बंद (VAL_END hard-cut).
कोणताही gate/engine चालू करत नाही.

  (a) Positional short-strike breach: Daily/Weekly levels (SR V3 [day+week], sr_dynamic [daily bars], OE 1d zones) — प्रत्येक दिवशी open ला,
      प्रत्येक बाजूला (put खाली / call वर) किंमतीपासून 0.5–4% मधला सर्वात जवळचा level; strike = त्याची दूरची कड. 5 सत्र hold:
      touch breach (कधीही पलीकडे) आणि close breach (5व्या सत्राचा close पलीकडे). Baseline: त्याच period मधले यादृच्छिक दिवस, तेच % अंतर, तीच बाजू.
      अंतर-buckets (0.5–1%, 1–2%, 2–4%) वेगळे — breach दर अंतरावर खूप अवलंबून.
  (b) HEALTHY वि. DANGEROUS pullback — 15M आणि 1H, सर्व IS (आणि VAL वेगळा); T2 चा calibrated LegConfig तोच (नवीन tuning नाही); label-shuffle permutation.
  (c) Retested वि. fresh zones (OE) — touches-bucket निहाय, **random baseline सह**: प्रत्येक खऱ्या zone मागे 3 random zones (तीच रुंदी, IS अंतर-वितरण,
      बाजू यादृच्छिक) आणि त्यांचे touches **त्याच उगम-खिडकीत** (zone च्या formed_at पासून दिवसाच्या आधीपर्यंत) मोजले ⇒ bucket-निहाय खरे वि. random.

    python3 g2_followups.py --out /tmp/g2 --report docs/reports/g2_followups.md
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

import leg_level_validation as T3
import real_nifty_data
import research_stats as RS
import sr_dynamic
import sr_levels_v3
from price_action import leg_eval as E
from price_action import legs as LG
from price_action import level_strength as S
from price_action import level_validation as V

DIST_MIN, DIST_MAX = 0.5, 4.0
DIST_BUCKETS = [(0.5, 1.0), (1.0, 2.0), (2.0, 4.0)]
HOLD = 5
K_RANDOM = 5
SEED = 11
CAL_CFG = dict(e_hi=0.35, o_lo=0.65, d_k=1.5, d_body=0.5)          # T2.3 IS calibration (leg_classifier_g1.md) — बदल नाही
TOUCH_BUCKETS = [-1, 0, 1, 2, 4, 1e9]
TOUCH_LABELS = ["0", "1", "2", "3–4", "5+"]
SESSION_CLOSE = pd.Timedelta(hours=15, minutes=30)
N_BOOT = 1000
FAILS = {}                                                          # engine -> किती दिवस levels काढता आले नाहीत (report मध्ये)


def month_key(ts):
    """cluster = कॅलेंडर महिना (review: overlapping hold-windows / एकच zone अनेक दिवस ⇒ rows स्वतंत्र नाहीत)."""
    t = pd.Timestamp(ts)
    return t.year * 100 + t.month


def cluster_z(a_val, a_cl, b_val, b_cl, n_boot=N_BOOT, seed=SEED):
    """दोन गटांच्या सरासरीतला फरक / cluster-bootstrap SE (clusters = a आणि b चे एकत्रित महिने, replacement सह). rows स्वतंत्र नसताना
    two_prop_z पेक्षा प्रामाणिक. n < 5 किंवा SE 0 ⇒ NaN."""
    a_val, b_val = np.asarray(a_val, float), np.asarray(b_val, float)
    if min(len(a_val), len(b_val)) < 5:
        return np.nan
    keys = np.unique(np.r_[np.asarray(a_cl), np.asarray(b_cl)])
    idx = {k: n for n, k in enumerate(keys)}
    K = len(keys)
    ai, bi = np.array([idx[k] for k in a_cl]), np.array([idx[k] for k in b_cl])
    sa, na = np.bincount(ai, a_val, K), np.bincount(ai, minlength=K).astype(float)
    sb, nb = np.bincount(bi, b_val, K), np.bincount(bi, minlength=K).astype(float)
    rng = np.random.default_rng(seed)
    w = np.stack([np.bincount(rng.integers(0, K, K), minlength=K) for _ in range(n_boot)])   # प्रत्येक boot मध्ये cluster किती वेळा
    NA, NB = w @ na, w @ nb
    ok = (NA > 0) & (NB > 0)
    diffs = (w @ sa)[ok] / NA[ok] - (w @ sb)[ok] / NB[ok]
    se = diffs.std(ddof=1) if len(diffs) > 1 else 0.0
    return float((a_val.mean() - b_val.mean()) / se) if se > 0 else np.nan


def _bucket(d):
    for lo, hi in DIST_BUCKETS:
        if lo <= d < hi:
            return f"{lo}–{hi}%"
    return None


# ---------------------------------------------------------------------------------------------------------------------
# (a) Positional strike breach
# ---------------------------------------------------------------------------------------------------------------------
def weekly(dd):
    w = dd.set_index("timestamp").resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    w["timestamp"] = w["timestamp"] - pd.Timedelta(days=4)            # आठवड्याची सुरुवात (सोमवार) label
    return w


def positional_levels(dd, wk, i, oe_day):
    """दिवस i च्या open आधी माहीत असलेले levels: {engine: [(low, high), ...]}. फक्त i पूर्वीचे daily/weekly bars."""
    day = pd.Timestamp(dd["timestamp"].iloc[i]).normalize()
    past_d = dd.iloc[max(0, i - 300):i].reset_index(drop=True)
    past_w = wk[wk["timestamp"] + pd.Timedelta(days=7) <= day].tail(150).reset_index(drop=True)   # पूर्ण आठवडेच
    out = {"SRV3_DW": [], "DYN_D": [], "OE_1D": []}
    if len(past_d) > 30:
        # review: daily bar चा timestamp मध्यरात्रीचा ⇒ compute_sr_v3 ला "सत्र अजून चालू" वाटून PDH/PDL एक दिवस जुने येत. सत्र-अखेर (15:30) stamp
        # दिल्यावर session_reference_date = दिवस i ⇒ PDH/PDL = दिवस i−1 (i च्या open ला माहीत). फक्त भूतकाळातले bars ⇒ lookahead नाही.
        closed_d = past_d.assign(timestamp=past_d["timestamp"].dt.normalize() + SESSION_CLOSE)
        try:
            r = sr_levels_v3.compute_sr_v3({"day": closed_d, "week": past_w}, daily_df=closed_d)
            out["SRV3_DW"] = [(float(z["low"]), float(z["high"])) for z in r.get("levels", [])]
        except Exception:
            FAILS["SRV3_DW"] = FAILS.get("SRV3_DW", 0) + 1
        d = sr_dynamic.compute_dynamic_sr(past_d, prd=5, current_price=float(past_d["close"].iloc[-1]))
        out["DYN_D"] = [(lv * 0.999, lv * 1.001) for lv in (float(z["level"]) for k in ("support", "resistance") for z in d.get(k, []))]
    out["OE_1D"] = [(float(z["low"]), float(z["high"])) for z in (oe_day or []) if z.get("tf") == "1d" and z.get("status") != "BROKEN"]
    return out


def positional_test(dd, oe_full, log):
    rng = np.random.default_rng(SEED)
    dd = dd.reset_index(drop=True)
    wk = weekly(dd)
    per = [T3.period_of(t) for t in dd["timestamp"]]
    same = [i + HOLD - 1 < len(dd) and per[i] is not None and per[i + HOLD - 1] == per[i] for i in range(len(dd))]   # review: hold-window period ओलांडू नये
    pools = {p: [j for j in range(len(dd)) if same[j] and per[j] == p] for p in ("IS", "VAL")}
    rows = []
    for i in range(60, len(dd)):
        p = per[i]
        if p is None or not same[i]:
            continue
        o = float(dd["open"].iloc[i])
        levels = positional_levels(dd, wk, i, oe_full.get(pd.Timestamp(dd["timestamp"].iloc[i]).normalize()))
        for eng, zs in levels.items():
            for side in (1, -1):                                   # +1 = put (support खाली), −1 = call (resistance वर)
                cands = []
                for lo, hi in zs:
                    strike = lo if side > 0 else hi
                    dist = (o - strike) / o * 100 * side
                    if DIST_MIN <= dist < DIST_MAX and ((hi < o) if side > 0 else (lo > o)):
                        cands.append((dist, strike))
                if not cands:
                    continue
                dist, strike = min(cands)
                b = V.option_breach(dd, i, strike, side, HOLD)
                if b is None:
                    continue
                rows.append({"engine": eng, "period": p, "kind": "LEVEL", "side": side, "dist": dist, "touch": b[0], "close": b[1],
                             "cl": month_key(dd["timestamp"].iloc[i])})
                for j in rng.choice(pools[p], size=min(K_RANDOM, len(pools[p])), replace=False):
                    o2 = float(dd["open"].iloc[int(j)])
                    s2 = o2 * (1 - side * dist / 100)
                    b2 = V.option_breach(dd, int(j), s2, side, HOLD)
                    if b2 is not None:
                        rows.append({"engine": eng, "period": p, "kind": "RANDOM", "side": side, "dist": dist, "touch": b2[0], "close": b2[1],
                                     "cl": month_key(dd["timestamp"].iloc[int(j)])})
        if log and i % 500 == 0:
            log(f"  positional: {i}/{len(dd)}")
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(), df
    df["bucket"] = df["dist"].map(_bucket)
    tab = []
    for (eng, p, bk), g in df.groupby(["engine", "period", "bucket"]):
        lv, rd = g[g["kind"] == "LEVEL"], g[g["kind"] == "RANDOM"]
        if not len(lv) or not len(rd):
            continue
        z_t = cluster_z(lv["touch"], lv["cl"], rd["touch"], rd["cl"])
        z_c = cluster_z(lv["close"], lv["cl"], rd["close"], rd["cl"])
        tab.append({"engine": eng, "period": p, "अंतर": bk, "n_level": len(lv), "touch_level%": round(100 * lv["touch"].mean(), 1),
                    "touch_random%": round(100 * rd["touch"].mean(), 1), "z_touch": round(z_t, 2), "close_level%": round(100 * lv["close"].mean(), 1),
                    "close_random%": round(100 * rd["close"].mean(), 1), "z_close": round(z_c, 2)})
    return pd.DataFrame(tab), df


# ---------------------------------------------------------------------------------------------------------------------
# (b) HEALTHY वि. DANGEROUS — 15M + 1H
# ---------------------------------------------------------------------------------------------------------------------
def pullback_test(frames, n_perm=2000):
    cfg = LG.LegConfig(**CAL_CFG)
    rows = []
    for tf, df in frames.items():
        legs, _, _ = LG.build_legs(df, cfg)
        out = E.outcomes(df, legs, E.HORIZON)
        for per, part in zip(("IS", "VAL"), E.split_periods(out)):
            if per == "VAL":
                part = part[pd.to_datetime(part["known_time"]) <= T3.VAL_END]
            pb = part[part["role"] == LG.ROLE_PULLBACK]
            h = pb[pb["label"] == LG.HEALTHY_PULLBACK]["resume"].dropna().to_numpy()
            d = pb[pb["label"] == LG.DANGEROUS_PULLBACK]["resume"].dropna().to_numpy()
            m = pb[pb["label"] == LG.MIXED_PULLBACK]["resume"].dropna().to_numpy()
            allp = pb["resume"].dropna().to_numpy()
            p = None
            if len(h) > 5 and len(d) > 5:
                x, y = np.r_[h, d], np.r_[np.ones(len(h)), np.zeros(len(d))]
                _, p = RS.shuffle_pvalue(lambda a, b: float(a[b == 1].mean() - a[b == 0].mean()), x, y, n_perm=n_perm, seed=SEED)
            rows.append({"TF": tf, "period": per, "pullbacks": len(pb), "n_healthy": len(h), "resume_healthy%": round(100 * h.mean(), 1) if len(h) else None,
                         "n_dangerous": len(d), "resume_dangerous%": round(100 * d.mean(), 1) if len(d) else None,
                         "n_mixed": len(m), "resume_mixed%": round(100 * m.mean(), 1) if len(m) else None,
                         "resume_सर्व%": round(100 * allp.mean(), 1) if len(allp) else None, "p_perm": None if p is None else round(p, 4)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------------------
# (c) Retested वि. fresh — random baseline सह
# ---------------------------------------------------------------------------------------------------------------------
def _touches(h, l, lo, hi, a, t):
    """bars a..t मध्ये zone ला वेगळ्या visits — सुरुवातीचा (उगमानंतर लगेचचा) overlap वगळून (level_strength सारखाच नियम)."""
    if a > t:
        return 0
    while a <= t and l[a] <= hi and h[a] >= lo:
        a += 1
    if a > t:
        return 0
    inside = (l[a:t + 1] <= hi) & (h[a:t + 1] >= lo)
    return int((inside & ~np.r_[False, inside[:-1]]).sum())


def retest_test(d15, oe_full, log):
    rng = np.random.default_rng(SEED)
    bars = S.prep_bars(d15)
    h, l, c, o, mr, ts = bars["h"], bars["l"], bars["c"], bars["o"], bars["mr"], bars["ts"]
    day_idx = pd.Series(np.arange(len(d15))).groupby(d15["timestamp"].dt.normalize().to_numpy()).agg(["first", "last"])
    real, pool_is = [], []
    for day in list(day_idx.index)[30:]:
        per = T3.period_of(day)
        if per is None:
            continue
        g0, g1 = int(day_idx.loc[day, "first"]), int(day_idx.loc[day, "last"])
        p0 = float(o[g0])
        for z in oe_full.get(pd.Timestamp(day).normalize(), []):
            lo, hi = z["low"], z["high"]
            if not (np.isfinite(lo) and np.isfinite(hi)) or hi < lo or lo <= p0 <= hi:
                continue
            dist = ((lo + hi) / 2 - p0) / p0 * 100
            if abs(dist) > T3.MAX_DIST_PCT:
                continue
            oi = S.origin_index(d15, z, ts)
            if oi is None or oi >= g0:
                continue
            side = 1 if p0 > hi else -1
            res = V.bounce_outcome(h, l, c, lo, hi, side, g0, g1, T3.N_BARS, mr, T3.BOUNCE_MR)
            real.append({"period": per, "day": day, "cl": month_key(day), "g0": g0, "g1": g1, "p0": p0, "width": hi - lo, "oi": oi, "dist": dist,
                         "touches": _touches(h, l, lo, hi, oi + 1, g0 - 1), **res})
            if per == "IS":
                pool_is.append(dist)
    log(f"  retest: खरे zones {len(real)}")
    rnd = []
    for r in real:
        for z in V.random_zones(r["p0"], r["width"], pool_is, 3, rng):
            res = V.bounce_outcome(h, l, c, z["low"], z["high"], z["side"], r["g0"], r["g1"], T3.N_BARS, mr, T3.BOUNCE_MR)
            rnd.append({"period": r["period"], "cl": r["cl"], "touches": _touches(h, l, z["low"], z["high"], r["oi"] + 1, r["g0"] - 1), **res})
    R, Q = pd.DataFrame(real), pd.DataFrame(rnd)
    if R.empty or Q.empty:
        return pd.DataFrame()
    for df in (R, Q):
        df["bucket"] = pd.cut(df["touches"], TOUCH_BUCKETS, labels=TOUCH_LABELS).astype(str)
    tab = []
    for per in ("IS", "VAL"):
        for bk in TOUCH_LABELS:
            a = R[(R["period"] == per) & (R["bucket"] == bk) & R["touched"]]
            b = Q[(Q["period"] == per) & (Q["bucket"] == bk) & Q["touched"]]
            ka, kb = int((a["outcome"] == V.BOUNCE).sum()), int((b["outcome"] == V.BOUNCE).sum())
            tab.append({"period": per, "touches": bk, "n_real": len(a), "bounce_real%": round(100 * ka / len(a), 1) if len(a) else None,
                        "n_random": len(b), "bounce_random%": round(100 * kb / len(b), 1) if len(b) else None,
                        "edge_pp": round(100 * (ka / len(a) - kb / len(b)), 1) if len(a) and len(b) else None,
                        "z_cluster": round(cluster_z((a["outcome"] == V.BOUNCE).astype(float), a["cl"], (b["outcome"] == V.BOUNCE).astype(float), b["cl"]), 2)
                        if len(a) and len(b) else None})
    return pd.DataFrame(tab)


def _md(df):
    if df is None or not len(df):
        return "_(रिकामं)_\n"
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v) for v in r.tolist()) + " |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="g2_out")
    ap.add_argument("--report", default=None)
    a = ap.parse_args(argv)
    log = lambda m: print(m, flush=True)                                                           # noqa: E731
    t0 = time.time()
    df1m = real_nifty_data.load_nifty_1min()
    df1m = df1m[df1m["timestamp"] <= T3.VAL_END].reset_index(drop=True)                            # holdout कधीही नाही
    d15 = T3.resample(df1m, "15min")
    d60 = T3.resample(df1m, "60min", offset="15min")
    dd = T3.resample(df1m, "1D")
    oe_full = {}
    from opportunity_engine import sessions
    from opportunity_engine.backtest import BacktestConfig, prepare_timeline
    tl = prepare_timeline(sessions.build_frames(df1m), BacktestConfig(variants=("V1",)))
    for d in tl.days:
        oe_full[pd.Timestamp(d.date).normalize()] = [{"low": float(z["low"]), "high": float(z["high"]), "kind": z.get("kind", ""), "tf": z.get("tf"),
                                                      "formed_at": z.get("formed_at"), "status": z.get("status")} for z in d.levels
                                                     if np.isfinite(z.get("low", np.nan)) and np.isfinite(z.get("high", np.nan))]
    log(f"डेटा + OE timeline ({time.time() - t0:.0f}s)")
    pos, pos_rows = positional_test(dd, oe_full, log)
    log(f"(a) झाले ({time.time() - t0:.0f}s)")
    pb = pullback_test({"15M": d15, "1H": d60})
    log(f"(b) झाले ({time.time() - t0:.0f}s)")
    rt = retest_test(d15, oe_full, log)
    log(f"(c) झाले ({time.time() - t0:.0f}s)")
    os.makedirs(a.out, exist_ok=True)
    for name, tbl in (("positional", pos), ("pullbacks", pb), ("retest", rt)):
        tbl.to_csv(os.path.join(a.out, f"g2_{name}.csv"), index=False)
    if a.report:
        cpath = os.path.splitext(a.report)[0] + "_conclusions.md"
        concl = open(cpath, encoding="utf-8").read() if os.path.exists(cpath) else "_(निष्कर्ष अजून लिहिलेला नाही.)_\n"
        txt = ["# G2 नंतरच्या चाचण्या — positional strikes, pullbacks, retested zones (NIFTY, report-only)\n",
               "डेटा: NIFTY offline 1M (2015 → 2024-03). IS 2015–2021, VAL 2022 → 2024-03. Sealed holdout बंद. कोणताही gate चालू नाही.\n",
               f"## (a) Positional short strike — {HOLD} सत्र hold (Daily/Weekly levels वि. यादृच्छिक दिवस, तेच अंतर)\n",
               f"Strike = किंमतीपासून {DIST_MIN}–{DIST_MAX}% मधल्या सर्वात जवळच्या level ची दूरची कड (put: support चा low, call: resistance चा high). "
               f"touch = {HOLD} सत्रांत कधीही पलीकडे; close = {HOLD}व्या सत्राचा close पलीकडे. RANDOM = त्याच period चे {K_RANDOM} यादृच्छिक दिवस, तेच % अंतर, तीच बाजू."
               f"z = cluster-bootstrap (कॅलेंडर महिना, {N_BOOT} पुनरावृत्ती) — लगतच्या दिवसांचे hold-windows एकमेकांवर येतात म्हणून साधा two-proportion z फुगतो. "
               f"Hold-window IS/VAL सीमा ओलांडत नाही. OE 1d मध्ये BROKEN zones वगळले. levels काढता न आलेले दिवस: {FAILS or 'नाहीत'}.\n",
               _md(pos), "\n## (b) HEALTHY वि. DANGEROUS pullback — trend resume (15M आणि 1H)\n",
               "LegConfig = T2.3 चं IS calibration (बदल नाही). resume = पुढचा leg impulse चं टोक ओलांडतो. p = label-shuffle permutation (एकतर्फी).\n",
               _md(pb), "\n## (c) Retested वि. fresh zones (OE, 15M) — touches-bucket निहाय, random baseline सह\n",
               "Random zones चे touches त्याच उगम-खिडकीत (खऱ्या zone च्या formed_at पासून दिवसाच्या आधीपर्यंत) मोजले. Bounce व्याख्या T3 सारखीच. z_cluster = महिना-cluster bootstrap (एकच zone अनेक दिवस येतो ⇒ rows स्वतंत्र नाहीत).\n",
               _md(rt), "\n## निष्कर्ष\n", concl]
        os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write("\n".join(txt))
    log(f"पूर्ण ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
