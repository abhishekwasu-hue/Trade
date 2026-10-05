"""
leg_level_validation.py
-----------------------
🎓 T3 — Leg आणि Level validation (Osler पद्धत; फक्त अहवाल, कुठलाही gate चालू करत नाही). NIFTY offline 1M डेटा (2015 → 2024-03); sealed holdout नाही.

  1. Level अचूकता: sr_dynamic (15M), SR V3, OE zones, OE zones + T2.4 ताकद — प्रत्येक दिवशी सकाळी (as-of आदल्या bar पर्यंत) levels; त्या दिवशी
     पहिल्या स्पर्शानंतर 8 bars (15M) मध्ये bounce दर, वि. तीच रुंदी/अंतर-वितरण असलेले ≥ 1000 यादृच्छिक zones. IS आणि VAL वेगळे.
     touches चं चिन्ह (sign) IS वर logistic fit ने — VAL वर तपासणी.
  2. Leg classifier: STRONG वि. WEAK वि. random (पुढचे 8 bars), HEALTHY वि. DANGEROUS (trend resume) — label-shuffle permutation p-value.
  3. PBO (CSCV S=16): leg impulse grid (81 trials) आणि level engines; Deflated Sharpe. PBO > 0.05 ⇒ REJECT.
  4. Option-seller: मजबूत zone च्या पलीकडची short strike वि. त्याच अंतरावरची यादृच्छिक-दिवस strike — 5 सत्र hold, breach दर.
  5. अहवाल docs/reports/leg_level_validation.md (KEEP / REVIEW / REJECT).

BANKNIFTY / MCX: offline डेटा repo मध्ये नाही ⇒ इथे फक्त NIFTY. (VPS वर Upstox डेटा वापरायचा तर तो 2024-03-31 पूर्वीचाच हवा — holdout नियम.)

    python3 leg_level_validation.py --out /tmp/t3 --report docs/reports/leg_level_validation.md
"""
import argparse
import bisect
import json
import os
import sys
import time

import numpy as np
import pandas as pd

import real_nifty_data
import research_stats as RS
import sr_dynamic
import sr_levels_v3
from price_action import leg_eval as E
from price_action import legs as LG
from price_action import level_strength as S
from price_action import level_validation as V

IS_END = pd.Timestamp("2021-12-31 23:59")
VAL_START, VAL_END = pd.Timestamp("2022-01-01"), pd.Timestamp("2024-03-31 23:59")
N_BARS = 8
BOUNCE_MR = 1.0
MAX_DIST_PCT = 1.5
RANDOM_K = 3
DYN_BAND_PCT = 0.10                 # sr_dynamic रेषा ⇒ zone = level ± 0.10% (bot चा TOUCH_TOLERANCE_PCT)
SEED = 7
ENGINES = ("DYN", "SRV3", "OE", "OE_T24")


def period_of(ts):
    ts = pd.Timestamp(ts)
    return "IS" if ts <= IS_END else ("VAL" if VAL_START <= ts <= VAL_END else None)


def resample(df1m, rule, offset=None):
    d = df1m.set_index("timestamp")[["open", "high", "low", "close"]]
    kw = {"offset": offset} if offset else {}
    return d.resample(rule, label="left", closed="left", **kw).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()


# ---------------------------------------------------------------------------------------------------------------------
# levels as-of (दिवस सुरू होण्याआधीचा डेटा)
# ---------------------------------------------------------------------------------------------------------------------
def dyn_levels(d15, g0):
    sub = d15.iloc[max(0, g0 - 300):g0].reset_index(drop=True)
    r = sr_dynamic.compute_dynamic_sr(sub, current_price=float(sub["close"].iloc[-1])) if len(sub) else {"support": [], "resistance": []}
    out = []
    for kind, key in (("SUPPORT", "support"), ("RESISTANCE", "resistance")):
        for z in r.get(key, []):
            lv = float(z["level"])
            out.append({"low": lv * (1 - DYN_BAND_PCT / 100), "high": lv * (1 + DYN_BAND_PCT / 100), "kind": kind, "formed_at": None})
    return out


def v3_levels(d15, d60, dd, day_start):
    f15 = d15[(d15["timestamp"] < day_start) & (d15["timestamp"] >= day_start - pd.Timedelta(days=8))]
    f60 = d60[(d60["timestamp"] < day_start) & (d60["timestamp"] >= day_start - pd.Timedelta(days=15))]
    fd = dd[dd["timestamp"] < day_start.normalize()].tail(260)
    try:
        r = sr_levels_v3.compute_sr_v3({"15minute": f15, "1hour": f60, "day": fd}, daily_df=fd)
    except Exception:
        return []
    out = []
    for z in r.get("levels", []):
        anc = (z.get("anchor") or {}).get("ts")
        out.append({"low": float(z["low"]), "high": float(z["high"]), "kind": z.get("role", ""), "formed_at": anc})
    return out


def oe_levels_by_date(df1m, log):
    from opportunity_engine import sessions
    from opportunity_engine.backtest import BacktestConfig, prepare_timeline
    t0 = time.time()
    tl = prepare_timeline(sessions.build_frames(df1m), BacktestConfig(variants=("V1",)))
    log(f"OE timeline: {len(tl.days)} दिवस ({time.time() - t0:.0f}s)")
    out = {}
    for d in tl.days:
        out[pd.Timestamp(d.date).normalize()] = [{"low": float(z["low"]), "high": float(z["high"]), "kind": z.get("kind", ""), "formed_at": z.get("formed_at")}
                                                 for z in d.levels if np.isfinite(z.get("low", np.nan)) and np.isfinite(z.get("high", np.nan))]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# 1. Level अचूकता
# ---------------------------------------------------------------------------------------------------------------------
def level_rows(d15, d60, dd, oe_by_date, legs, log, days_limit=None):
    bars = S.prep_bars(d15)
    h, l, c, o, mr = bars["h"], bars["l"], bars["c"], bars["o"], bars["mr"]
    starts = [lg.start_bar for lg in legs]
    day_idx = pd.Series(np.arange(len(d15))).groupby(d15["timestamp"].dt.normalize().to_numpy()).agg(["first", "last"])
    rows = []
    days = list(day_idx.index)[30:]
    if days_limit:
        days = days[:days_limit]
    for n_day, day in enumerate(days):
        per = period_of(day)
        if per is None:
            continue
        g0, g1 = int(day_idx.loc[day, "first"]), int(day_idx.loc[day, "last"])
        price0 = float(o[g0])
        engines = {"DYN": dyn_levels(d15, g0), "SRV3": v3_levels(d15, d60, dd, pd.Timestamp(d15["timestamp"].iloc[g0]))}
        oe = oe_by_date.get(pd.Timestamp(day).normalize(), []) if oe_by_date is not None else []
        engines["OE"] = oe
        for eng, zones in engines.items():
            for z in zones:
                lo, hi = z["low"], z["high"]
                if not (np.isfinite(lo) and np.isfinite(hi)) or hi < lo:
                    continue
                if lo <= price0 <= hi:
                    continue
                side = 1 if price0 > hi else -1
                mid = (lo + hi) / 2
                dist = (mid - price0) / price0 * 100
                if abs(dist) > MAX_DIST_PCT:
                    continue
                res = V.bounce_outcome(h, l, c, lo, hi, side, g0, g1, N_BARS, mr, BOUNCE_MR)
                oi = S.origin_index(d15, z, bars["ts"])
                near = []
                if oi is not None:
                    a, b = bisect.bisect_left(starts, oi - 3), bisect.bisect_right(starts, oi + 3)
                    near = legs[a:b]
                f = S.strength_features({**z, "kind": "SUPPORT" if side > 0 else "RESISTANCE"}, d15, g0 - 1, legs=near, bars=bars)
                rows.append({"engine": eng, "date": day, "period": per, "kind": "REAL", "side": side, "dist_pct": dist, "width": hi - lo, "price0": price0,
                             "g0": g0, "g1": g1, **res, **{f"f_{k}": v for k, v in f.items()}, "strength": S.strength_score(f)})
        if log and n_day % 250 == 0:
            log(f"  levels: {n_day}/{len(days)} दिवस")
    return pd.DataFrame(rows), bars


def add_oe_t24(real, threshold):
    oe = real[(real["engine"] == "OE") & (real["kind"] == "REAL")]
    keep = oe[oe["strength"] >= threshold].copy()
    keep["engine"] = "OE_T24"
    return pd.concat([real, keep], ignore_index=True)


def random_rows(real, bars, seed=SEED):
    """प्रत्येक खऱ्या zone साठी RANDOM_K यादृच्छिक zones (त्याच दिवशी, तीच रुंदी; अंतर = त्या engine च्या IS खऱ्या अंतरांच्या वितरणातून)."""
    rng = np.random.default_rng(seed)
    h, l, c, mr = bars["h"], bars["l"], bars["c"], bars["mr"]
    out = []
    for eng, g in real.groupby("engine"):
        pool = g[g["period"] == "IS"]["dist_pct"].to_numpy()
        if not len(pool):
            continue
        for r in g.itertuples(index=False):
            for z in V.random_zones(r.price0, r.width, pool, RANDOM_K, rng):
                res = V.bounce_outcome(h, l, c, z["low"], z["high"], z["side"], r.g0, r.g1, N_BARS, mr, BOUNCE_MR)
                out.append({"engine": eng, "date": r.date, "period": r.period, "kind": "RANDOM", "side": z["side"], "dist_pct": ((z["low"] + z["high"]) / 2 - r.price0) / r.price0 * 100,
                            "width": r.width, "price0": r.price0, "g0": r.g0, "g1": r.g1, **res})
    return pd.DataFrame(out)


def accuracy_table(allrows):
    rows = []
    for (eng, per), g in allrows.groupby(["engine", "period"]):
        t = g[g["touched"]]
        real, rnd = t[t["kind"] == "REAL"], t[t["kind"] == "RANDOM"]
        kr, nr = int((real["outcome"] == V.BOUNCE).sum()), len(real)
        kn, nn = int((rnd["outcome"] == V.BOUNCE).sum()), len(rnd)
        rows.append({"engine": eng, "period": per, "real_zones": int((g["kind"] == "REAL").sum()), "real_touched": nr, "real_bounce_pct": round(100 * kr / nr, 1) if nr else None,
                     "random_touched": nn, "random_bounce_pct": round(100 * kn / nn, 1) if nn else None,
                     "edge_pp": round(100 * (kr / nr - kn / nn), 1) if nr and nn else None, "z": round(V.two_prop_z(kr, nr, kn, nn), 2),
                     "real_break_pct": round(100 * float((real["outcome"] == V.BREAK).mean()), 1) if nr else None,
                     "random_break_pct": round(100 * float((rnd["outcome"] == V.BREAK).mean()), 1) if nn else None,
                     "real_width_pct_med": round(float((real["width"] / real["price0"] * 100).median()), 3) if nr else None,
                     "random_width_pct_med": round(float((rnd["width"] / rnd["price0"] * 100).median()), 3) if nn else None,
                     "real_react_mr": round(float(real["react_mr"].mean()), 3) if nr else None, "random_react_mr": round(float(rnd["react_mr"].mean()), 3) if nn else None})
    return pd.DataFrame(rows)


FEATS = ("f_touches", "f_departure_mr", "f_base_bars", "f_recency", "f_round_dist_mr", "f_role_reversal", "f_width_mr")


def touches_fit(real):
    """IS वर: bounce ~ standardised features (logistic). touches चं चिन्ह data ठरवतं. VAL वर bucket-निहाय bounce दर तपासणी."""
    t = real[(real["kind"] == "REAL") & real["touched"] & (real["engine"].isin(["DYN", "SRV3", "OE"]))].copy()
    if not len(t):
        return pd.DataFrame(), pd.DataFrame()
    X = t[list(FEATS)].astype(float).fillna(0.0)                       # उगम माहीत नसेल (DYN) तर departure/base = 0 — मर्यादा, अहवालात नोंद
    y = (t["outcome"] == V.BOUNCE).astype(float)
    is_m = t["period"] == "IS"
    mu, sd = X[is_m].mean(), X[is_m].std().replace(0, 1.0)
    coef, b0 = V.logistic_fit(((X[is_m] - mu) / sd).to_numpy(), y[is_m].to_numpy())
    fit = pd.DataFrame({"feature": FEATS, "coef_IS(standardised)": np.round(coef, 3)})
    t["touch_bucket"] = pd.cut(t["f_touches"], [-1, 0, 1, 2, 4, 1e9], labels=["0", "1", "2", "3–4", "5+"]).astype(str)
    bk = t.groupby(["engine", "period", "touch_bucket"]).apply(lambda g: pd.Series({"n": int(len(g)), "bounce_pct": round(100 * float((g["outcome"] == V.BOUNCE).mean()), 1)}),
                                                                include_groups=False).reset_index()            # engine-निहाय (engines चे base rates वेगळे)
    bk["n"] = bk["n"].astype(int)
    return fit, bk


# ---------------------------------------------------------------------------------------------------------------------
# 2. Leg classifier
# ---------------------------------------------------------------------------------------------------------------------
def leg_tests(d15, cfg, horizon=E.HORIZON, n_perm=2000):
    legs, _, _ = LG.build_legs(d15, cfg)
    out = E.outcomes(d15, legs, horizon)
    c = d15["close"].to_numpy(float)
    mr = LG.median_range(d15)
    rng = np.random.default_rng(SEED)
    rows = []
    for per, part in zip(("IS", "VAL"), E.split_periods(out)):
        if per == "VAL":
            part = part[pd.to_datetime(part["known_time"]) <= VAL_END]
        s = part[part["label"] == LG.STRONG_IMPULSE]["fwd_mr"].dropna().to_numpy()
        w = part[part["label"] == LG.WEAK_IMPULSE]["fwd_mr"].dropna().to_numpy()
        # random: यादृच्छिक bars, मागच्या H bars च्या हालचालीच्या दिशेने (momentum baseline)
        ts = pd.to_datetime(d15["timestamp"])
        idx = np.flatnonzero(((ts <= IS_END) if per == "IS" else ((ts >= VAL_START) & (ts <= VAL_END))).to_numpy())
        idx = idx[(idx > horizon + 20) & (idx < len(c) - horizon - 1)]
        pick = rng.choice(idx, size=min(2000, len(idx)), replace=False)
        rnd = np.array([np.sign(c[k] - c[k - horizon]) * (c[k + horizon] - c[k]) / mr[k] for k in pick if np.isfinite(mr[k]) and mr[k] > 0])
        diff = lambda a, b: float(np.mean(a) - np.mean(b)) if len(a) and len(b) else np.nan        # noqa: E731
        both = np.r_[s, w]
        lab = np.r_[np.ones(len(s)), np.zeros(len(w))]
        stat, p = RS.shuffle_pvalue(lambda x, yl: diff(x[yl == 1], x[yl == 0]), both, lab, n_perm=n_perm, seed=SEED) if len(s) > 5 and len(w) > 5 else (np.nan, np.nan)
        pb = part[part["role"] == LG.ROLE_PULLBACK]
        hh = pb[pb["label"] == LG.HEALTHY_PULLBACK]["resume"].dropna().to_numpy()
        dg = pb[pb["label"] == LG.DANGEROUS_PULLBACK]["resume"].dropna().to_numpy()
        both2 = np.r_[hh, dg]
        lab2 = np.r_[np.ones(len(hh)), np.zeros(len(dg))]
        stat2, p2 = RS.shuffle_pvalue(lambda x, yl: diff(x[yl == 1], x[yl == 0]), both2, lab2, n_perm=n_perm, seed=SEED) if len(hh) > 5 and len(dg) > 5 else (np.nan, np.nan)
        rows.append({"period": per, "n_strong": len(s), "fwd_strong": round(float(s.mean()), 3) if len(s) else None, "n_weak": len(w), "fwd_weak": round(float(w.mean()), 3) if len(w) else None,
                     "fwd_random_momentum": round(float(rnd.mean()), 3) if len(rnd) else None, "strong_minus_weak": round(stat, 3) if np.isfinite(stat) else None,
                     "p_perm": round(p, 4) if np.isfinite(p) else None, "n_healthy": len(hh), "resume_healthy": round(float(hh.mean()), 3) if len(hh) else None,
                     "n_danger": len(dg), "resume_danger": round(float(dg.mean()), 3) if len(dg) else None,
                     "healthy_minus_danger": round(stat2, 3) if np.isfinite(stat2) else None, "p_perm_pullback": round(p2, 4) if np.isfinite(p2) else None})
    return pd.DataFrame(rows), out


def leg_grid_pbo(d15, base_cfg):
    """impulse grid (81) — प्रत्येक trial चा दैनिक "signal" R: STRONG_IMPULSE leg माहीत झाल्यावर त्या दिशेने H bars (fwd_mr). IS वर CSCV PBO + DSR."""
    is_df = d15[d15["timestamp"] <= IS_END].reset_index(drop=True)
    piv = LG.pivots_for(is_df, base_cfg)
    days = pd.DatetimeIndex(sorted(is_df["timestamp"].dt.normalize().unique()))
    cols, names = [], []
    for p in E._grid(E.IMPULSE_GRID):
        cfg = LG.LegConfig(**{**base_cfg.__dict__, **p})
        legs, _, _ = LG.build_legs(is_df, cfg, pivots=piv)
        o = E.outcomes(is_df, legs)
        o = o[o["label"] == LG.STRONG_IMPULSE].dropna(subset=["fwd_mr"])
        s = o.groupby(pd.to_datetime(o["known_time"]).dt.normalize())["fwd_mr"].sum().reindex(days).fillna(0.0)
        cols.append(s.to_numpy())
        names.append(json.dumps(p))
    M = np.column_stack(cols)
    pbo = RS.pbo_cscv(M, S=16)
    shp = [RS.sharpe(M[:, j]) for j in range(M.shape[1])]
    best = int(np.argmax(shp))
    return {"pbo": pbo["pbo"], "n_splits": pbo["n_splits"], "N": pbo["N"], "best": names[best], "dsr": RS.deflated_sharpe(M[:, best], shp)}


def engine_pbo(real):
    """level engines हे trials: दैनिक R = त्या दिवशीच्या स्पर्श झालेल्या zones चा react_mr बेरीज (IS)."""
    t = real[(real["kind"] == "REAL") & real["touched"] & (real["period"] == "IS")]
    if not len(t):
        return {"pbo": None}
    days = pd.DatetimeIndex(sorted(real[real["period"] == "IS"]["date"].unique()))
    engs = sorted(t["engine"].unique())
    M = np.column_stack([t[t["engine"] == e].groupby("date")["react_mr"].sum().reindex(days).fillna(0.0).to_numpy() for e in engs])
    pbo = RS.pbo_cscv(M, S=16)
    shp = [RS.sharpe(M[:, j]) for j in range(M.shape[1])]
    best = int(np.argmax(shp))
    return {"pbo": pbo["pbo"], "n_splits": pbo["n_splits"], "N": pbo["N"], "engines": engs, "best": engs[best], "sharpe": {e: round(float(v), 4) for e, v in zip(engs, shp)},
            "dsr": RS.deflated_sharpe(M[:, best], shp)}


# ---------------------------------------------------------------------------------------------------------------------
# 4. Option-seller
# ---------------------------------------------------------------------------------------------------------------------
def option_seller(real, dd, threshold, hold=5, k_random=5, seed=SEED):
    """मजबूत (strength ≥ threshold) zone च्या दूरच्या कडेवर short strike (support ⇒ put, resistance ⇒ call), दिवसाच्या open ला; `hold` सत्र.
    प्रत्येक (engine, दिवस, बाजू) साठी किंमतीच्या सर्वात जवळचा मजबूत zone एवढाच (एकाच दिवशी अनेक जवळजवळ सारख्या strikes ने आकडे फुगू नयेत).
    baseline: त्याच % अंतरावर, यादृच्छिक इतर दिवस (त्याच period मधले) — बिनशर्त breach दर."""
    rng = np.random.default_rng(seed)
    dd = dd.reset_index(drop=True)
    dpos = {pd.Timestamp(t).normalize(): i for i, t in enumerate(dd["timestamp"])}
    per_of_day = [period_of(t) for t in dd["timestamp"]]
    per_days = {p: [j for j in range(len(dd) - hold) if per_of_day[j] == p] for p in ("IS", "VAL")}
    zones = real[(real["kind"] == "REAL") & (real["engine"].isin(["OE", "SRV3"])) & (real["strength"] >= threshold)].copy()
    # option seller प्रत्येक दिवशी प्रत्येक बाजूला एकच strike विकतो: किंमतीच्या सर्वात जवळचा मजबूत zone (त्याची दूरची कड)
    zones["absd"] = zones["dist_pct"].abs()
    zones = zones.sort_values("absd").groupby(["engine", "date", "side"], as_index=False).head(1)
    rows = []
    for r in zones.itertuples(index=False):
        i = dpos.get(pd.Timestamp(r.date).normalize())
        if i is None:
            continue
        mid = r.price0 * (1 + r.dist_pct / 100)
        strike = mid - r.width / 2 if r.side > 0 else mid + r.width / 2
        dist = abs(strike - r.price0) / r.price0
        b = V.option_breach(dd, i, strike, r.side, hold)
        if b is None:
            continue
        pool = per_days.get(r.period, [])
        for j in (rng.choice(pool, size=min(k_random, len(pool)), replace=False) if pool else []):
            p0 = float(dd["open"].iloc[j])
            rs = p0 * (1 - dist) if r.side > 0 else p0 * (1 + dist)
            rb = V.option_breach(dd, int(j), rs, r.side, hold)
            if rb is not None:
                rows.append({"engine": r.engine, "period": r.period, "kind": "RANDOM", "side": r.side, "touch": rb[0], "close": rb[1], "dist_pct": dist * 100})
        rows.append({"engine": r.engine, "period": r.period, "kind": "ZONE", "side": r.side, "touch": b[0], "close": b[1], "dist_pct": dist * 100})
    df = pd.DataFrame(rows)
    if not len(df):
        return df
    return df.groupby(["engine", "period", "kind"]).agg(n=("touch", "size"), touch_breach_pct=("touch", lambda x: round(100 * x.mean(), 1)),
                                                         close_breach_pct=("close", lambda x: round(100 * x.mean(), 1)), avg_dist_pct=("dist_pct", "mean")).round(2).reset_index()


# ---------------------------------------------------------------------------------------------------------------------
# अहवाल
# ---------------------------------------------------------------------------------------------------------------------
MIN_N = 30


def verdict(edge_is, z_is, edge_val, pbo=None, n_min=None):
    if pbo is not None and pbo > 0.05:
        return "REJECT (PBO > 0.05)"
    if edge_is is None or edge_val is None or (isinstance(edge_val, float) and np.isnan(edge_val)):
        return "REVIEW (डेटा अपुरा)"
    if n_min is not None and n_min < MIN_N:
        return f"REVIEW (नमुना लहान: n={int(n_min)} < {MIN_N})"
    if edge_is > 0 and z_is is not None and z_is >= 2 and edge_val > 0:
        return "KEEP"
    if edge_is <= 0 and edge_val <= 0:
        return "REJECT"
    return "REVIEW"


def _md(df):
    if df is None or not len(df):
        return "_(रिकामं)_\n"
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v) for v in r.tolist()) + " |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="t3_out")
    ap.add_argument("--report", default=None)
    ap.add_argument("--days-limit", type=int, default=None, help="जलद चाचणीसाठी फक्त पहिले N दिवस")
    ap.add_argument("--no-oe", action="store_true", help="OE timeline वगळा (जलद)")
    a = ap.parse_args(argv)
    log = lambda m: print(m, flush=True)                                                           # noqa: E731
    t0 = time.time()
    df1m = real_nifty_data.load_nifty_1min()
    df1m = df1m[df1m["timestamp"] <= VAL_END].reset_index(drop=True)                               # holdout कधीही नाही
    d15 = resample(df1m, "15min")
    d60 = resample(df1m, "60min", offset="15min")
    dd = resample(df1m, "1D")
    os.makedirs(a.out, exist_ok=True)
    cal_cfg = LG.LegConfig(e_hi=0.35, o_lo=0.65, d_k=1.5, d_body=0.5)                             # T2.3 IS-calibration चा निकाल (leg_classifier_g1.md)
    legs, _, _ = LG.build_legs(d15, cal_cfg)
    log(f"डेटा: 15M {len(d15)} bars, legs {len(legs)} ({time.time() - t0:.0f}s)")
    oe = None if a.no_oe else oe_levels_by_date(df1m, log)
    real, bars = level_rows(d15, d60, dd, oe, legs, log, a.days_limit)
    thr = float(real[(real["engine"] == "OE") & (real["period"] == "IS")]["strength"].median()) if (real["engine"] == "OE").any() else 50.0
    real = add_oe_t24(real, thr)
    rnd = random_rows(real, bars)
    allrows = pd.concat([real, rnd], ignore_index=True)
    allrows.drop(columns=[c for c in allrows.columns if c.startswith("f_origin")], errors="ignore").to_csv(os.path.join(a.out, "t3_level_rows.csv"), index=False)
    acc = accuracy_table(allrows)
    fit, bk = touches_fit(real)
    log(f"levels झाले ({time.time() - t0:.0f}s): real {int((allrows['kind'] == 'REAL').sum())}, random {int((allrows['kind'] == 'RANDOM').sum())}")
    lt, _ = leg_tests(d15, cal_cfg)
    lg_pbo = leg_grid_pbo(d15, LG.LegConfig())
    en_pbo = engine_pbo(real)
    opt = option_seller(real, dd, thr)
    log(f"सर्व चाचण्या झाल्या ({time.time() - t0:.0f}s)")
    for name, tbl in (("accuracy", acc), ("touches_fit", fit), ("touch_buckets", bk), ("leg_tests", lt), ("option_seller", opt)):
        tbl.to_csv(os.path.join(a.out, f"t3_{name}.csv"), index=False)
    with open(os.path.join(a.out, "t3_pbo.json"), "w", encoding="utf-8") as fh:
        json.dump({"leg_grid": lg_pbo, "engines": en_pbo, "oe_t24_threshold": thr}, fh, ensure_ascii=False, indent=1, default=str)
    ver = []
    for eng in sorted(acc["engine"].unique()):
        g = acc[acc["engine"] == eng].set_index("period")
        e_is = g.loc["IS", "edge_pp"] if "IS" in g.index else None
        z_is = g.loc["IS", "z"] if "IS" in g.index else None
        e_val = g.loc["VAL", "edge_pp"] if "VAL" in g.index else None
        n_min = min(int(g.loc[p, "real_touched"]) if p in g.index else 0 for p in ("IS", "VAL"))
        ver.append({"घटक": f"Level engine {eng} (वि. random)", "IS edge": f"{e_is} pp", "IS z / p": z_is, "VAL edge": f"{e_val} pp", "निर्णय": verdict(e_is, z_is, e_val, None, n_min)})
    ep = en_pbo.get("pbo")
    ver.append({"घटक": "Engines मधून IS-सर्वोत्तम निवड", "IS edge": f"सर्वोत्तम {en_pbo.get('best')}", "IS z / p": f"PBO={ep}", "VAL edge": "",
                "निर्णय": "REJECT (PBO > 0.05)" if ep is not None and ep > 0.05 else "KEEP"})
    lis, lval = lt.set_index("period").loc["IS"], lt.set_index("period").loc["VAL"]
    ver.append({"घटक": "Leg: STRONG वि. WEAK impulse (fwd, × range)", "IS edge": lis["strong_minus_weak"], "IS z / p": f"p={lis['p_perm']}", "VAL edge": lval["strong_minus_weak"],
                "निर्णय": verdict(lis["strong_minus_weak"], 2.0 if (lis["p_perm"] or 1) < 0.05 else 0.0, lval["strong_minus_weak"], lg_pbo["pbo"],
                                 min(lis["n_strong"], lis["n_weak"], lval["n_strong"], lval["n_weak"]))})
    ver.append({"घटक": "Leg: HEALTHY वि. DANGEROUS pullback (resume दर)", "IS edge": lis["healthy_minus_danger"], "IS z / p": f"p={lis['p_perm_pullback']}", "VAL edge": lval["healthy_minus_danger"],
                "निर्णय": verdict(lis["healthy_minus_danger"], 2.0 if (lis["p_perm_pullback"] or 1) < 0.05 else 0.0, lval["healthy_minus_danger"],
                                 n_min=min(lis["n_healthy"], lis["n_danger"], lval["n_healthy"], lval["n_danger"]))})
    if a.report:
        cpath = os.path.splitext(a.report)[0] + "_conclusions.md"          # हाताने लिहिलेले निष्कर्ष वेगळ्या फाईलमध्ये — पुन्हा चालवल्यावर पुसले जात नाहीत
        conclusions = open(cpath, encoding="utf-8").read() if os.path.exists(cpath) else "_(निष्कर्ष: `" + os.path.basename(cpath) + "` अजून लिहिलेला नाही.)_\n"
        txt = ["# T3 — Leg आणि Level validation (Osler पद्धत, NIFTY)\n",
               f"डेटा: NIFTY offline 1M → 15M ({len(d15)} bars), IS 2015→2021, VAL 2022→2024-03. Sealed holdout वापरलेला नाही. BANKNIFTY/MCX offline डेटा उपलब्ध नाही ⇒ फक्त NIFTY.",
               f"Bounce = पहिल्या स्पर्शानंतर {N_BARS} bars (15M) मध्ये close दूरच्या कडेपलीकडे जाण्याआधी zone पासून ≥ {BOUNCE_MR} × median_range close-अंतर. zones दिवसाच्या open पासून ±{MAX_DIST_PCT}%.",
               f"Random: प्रत्येक खऱ्या zone मागे {RANDOM_K} यादृच्छिक zones (तीच रुंदी, अंतर त्या engine च्या IS अंतर-वितरणातून, बाजू यादृच्छिक). OE_T24 = OE zones ज्यांची T2.4 ताकद ≥ IS median ({thr:.1f}).\n",
               "## निर्णय सारांश (KEEP / REVIEW / REJECT)\n", _md(pd.DataFrame(ver)),
               "\n## 1. Level अचूकता — खरे वि. यादृच्छिक\n", _md(acc),
               "\n### touches चं चिन्ह (IS logistic, standardised) आणि touches-bucket नुसार bounce\n", _md(fit), "\n", _md(bk),
               "\n## 2. Leg classifier चाचण्या\n", _md(lt),
               "\n## 3. PBO / Deflated Sharpe\n",
               f"- Leg impulse grid (81 trials, IS दैनिक signal-R): PBO = **{lg_pbo['pbo']}**, IS-सर्वोत्तम {lg_pbo['best']}, DSR = {lg_pbo['dsr'].get('dsr')}",
               f"- Level engines (trials = {en_pbo.get('engines')}, IS दैनिक react-R): PBO = **{en_pbo.get('pbo')}**, सर्वोत्तम {en_pbo.get('best')}, Sharpe {en_pbo.get('sharpe')}, DSR = {(en_pbo.get('dsr') or {}).get('dsr')}\n",
               "## 4. Option-seller चाचणी (5 सत्र hold; ZONE = मजबूत zone ची दूरची कड, RANDOM = त्याच % अंतरावर यादृच्छिक दिवस)\n", _md(opt),
               "\n## 5. निष्कर्ष\n", conclusions]
        os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write("\n".join(map(str, txt)))
    log(f"पूर्ण ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
