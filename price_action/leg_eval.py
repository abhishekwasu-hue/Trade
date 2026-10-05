"""
price_action/leg_eval.py
------------------------
🎓 T2.3 — Leg classifier चं मूल्यमापन आणि IS-calibration (फक्त अहवाल; bot वर परिणाम नाही).

परिणाम (outcome) — leg चं लेबल `known_at` (end pivot चा confirm bar) ला माहीत होतं; परिणाम त्यानंतरचाच:
  • fwd_mr  = (close[known_at + H] − close[known_at]) × leg दिशा ÷ median_range  — impulse: पुढे तीच दिशा चालू राहते का.
  • resume  = pullback नंतरचा पुढचा leg impulse चं टोक (pullback ची सुरुवात) ओलांडतो का — trend पुन्हा सुरू (फक्त मूल्यमापनासाठी भविष्य).
Calibration (आधीच ठरवलेले grids, प्रत्येकी 81, फक्त IS; प्रत्येक trial नोंदवला):
  1) impulse grid: e_hi × o_lo × d_k × d_body — उद्दिष्ट: STRONG वि. WEAK fwd_mr फरकाचा Welch t (STRONG वाटा 10–60%).
  2) pullback grid (impulse निवड निश्चित ठेवून): r_ok × r_warn × s_ratio × fvg_min — उद्दिष्ट: HEALTHY वि. DANGEROUS resume दराचा z (दोन्ही ≥ 10%).
"""
import itertools
import math
from dataclasses import replace

import numpy as np
import pandas as pd

from . import legs as LG

IS_END = pd.Timestamp("2021-12-31 23:59")
VAL_START = pd.Timestamp("2022-01-01")
HORIZON = 8

IMPULSE_GRID = {"e_hi": (0.35, 0.45, 0.55), "o_lo": (0.45, 0.55, 0.65), "d_k": (1.0, 1.5, 2.0), "d_body": (0.5, 0.6, 0.7)}
PULLBACK_GRID = {"r_ok": (0.4, 0.5, 0.6), "r_warn": (0.7, 0.85, 1.0), "s_ratio": (0.6, 0.8, 1.0), "fvg_min": (0.1, 0.25, 0.5)}
MIN_SHARE = 0.10
MAX_STRONG_SHARE = 0.60


def outcomes(df, legs, horizon=HORIZON):
    """legs -> DataFrame: label, role, direction, known_time, fwd_mr, resume (pullback साठी) + features."""
    df = df.reset_index(drop=True)
    c = df["close"].to_numpy(float)
    mr = LG.median_range(df)
    ts = pd.to_datetime(df["timestamp"])
    rows = []
    for i, lg in enumerate(legs):
        k = lg.known_at
        fwd = np.nan
        if k + horizon < len(c) and np.isfinite(mr[k]) and mr[k] > 0:
            fwd = (c[k + horizon] - c[k]) * lg.direction / mr[k]
        resume = np.nan
        if lg.role == LG.ROLE_PULLBACK and i + 1 < len(legs):
            imp_dir = -lg.direction
            resume = float((legs[i + 1].end_price - lg.start_price) * imp_dir > 0)
        rows.append({"known_time": ts.iloc[min(k, len(ts) - 1)], "label": lg.label, "role": lg.role, "direction": lg.direction, "fwd_mr": fwd,
                     "resume": resume, "score": lg.score, **{f: lg.features.get(f) for f in ("net_mr", "eff_range", "overlap", "disp_n", "fvg_n", "depth", "speed")}})
    return pd.DataFrame(rows)


def split_periods(out):
    t = pd.to_datetime(out["known_time"])
    return out[t <= IS_END], out[t >= VAL_START]


def welch_t(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return np.nan
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else np.nan


def prop_z(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return np.nan
    p = (a.sum() + b.sum()) / (len(a) + len(b))
    se = math.sqrt(p * (1 - p) * (1 / len(a) + 1 / len(b)))
    return float((a.mean() - b.mean()) / se) if se > 0 else np.nan


def impulse_stats(out):
    imp = out[out["label"].isin([LG.STRONG_IMPULSE, LG.WEAK_IMPULSE])]
    s, w = imp[imp["label"] == LG.STRONG_IMPULSE]["fwd_mr"], imp[imp["label"] == LG.WEAK_IMPULSE]["fwd_mr"]
    share = len(s) / len(imp) if len(imp) else 0.0
    return {"n_impulse": len(imp), "strong_share": round(share, 3), "fwd_strong": round(float(s.mean()), 3) if len(s) else None,
            "fwd_weak": round(float(w.mean()), 3) if len(w) else None, "t": welch_t(s, w)}


def pullback_stats(out):
    pb = out[out["role"] == LG.ROLE_PULLBACK]
    pb = pb[pb["label"] != LG.RANGE]
    h, d = pb[pb["label"] == LG.HEALTHY_PULLBACK]["resume"], pb[pb["label"] == LG.DANGEROUS_PULLBACK]["resume"]
    n = len(pb)
    return {"n_pullback": n, "healthy_share": round(len(h) / n, 3) if n else 0.0, "danger_share": round(len(d) / n, 3) if n else 0.0,
            "resume_healthy": round(float(h.mean()), 3) if len(h.dropna()) else None, "resume_danger": round(float(d.mean()), 3) if len(d.dropna()) else None,
            "z": prop_z(h, d)}


def _grid(g):
    keys = list(g)
    return [dict(zip(keys, v)) for v in itertools.product(*(g[k] for k in keys))]


def calibrate(df, base=None, horizon=HORIZON, log=None):
    """IS वर दोन grids. रिटर्न dict: cfg (निवडलेला LegConfig), trials (DataFrame — सर्व 162), impulse_pick, pullback_pick."""
    base = base or LG.LegConfig()
    df = df.reset_index(drop=True)
    ts = pd.to_datetime(df["timestamp"])
    is_df = df[ts <= IS_END].reset_index(drop=True)
    piv = LG.pivots_for(is_df, base)
    rows = []

    def run(cfg, grid_name, params):
        legs, _, _ = LG.build_legs(is_df, cfg, pivots=piv)
        out = outcomes(is_df, legs, horizon)
        r = {"grid": grid_name, **params, **impulse_stats(out), **pullback_stats(out)}
        rows.append(r)
        return r

    best_i, best_ti = None, -np.inf
    for p in _grid(IMPULSE_GRID):
        r = run(replace(base, **p), "impulse", p)
        ok = MIN_SHARE <= r["strong_share"] <= MAX_STRONG_SHARE and np.isfinite(r["t"])
        if ok and r["t"] > best_ti:
            best_i, best_ti = p, r["t"]
    cfg_i = replace(base, **(best_i or {}))
    best_p, best_z = None, -np.inf
    for p in _grid(PULLBACK_GRID):
        if p["r_warn"] <= p["r_ok"]:
            continue
        r = run(replace(cfg_i, **p), "pullback", p)
        ok = r["healthy_share"] >= MIN_SHARE and r["danger_share"] >= MIN_SHARE and np.isfinite(r["z"])
        if ok and r["z"] > best_z:
            best_p, best_z = p, r["z"]
    cfg = replace(cfg_i, **(best_p or {}))
    if log:
        log(f"impulse निवड {best_i} (t={best_ti:.2f}) · pullback निवड {best_p} (z={best_z:.2f})")
    return {"cfg": cfg, "trials": pd.DataFrame(rows), "impulse_pick": best_i, "pullback_pick": best_p}


def evaluate(df, cfg, horizon=HORIZON):
    """निवडलेल्या cfg ने पूर्ण डेटावर legs (एकदाच, सलग) — IS आणि VAL वेगळे आकडे + लेबल वाटा."""
    df = df.reset_index(drop=True)
    legs, _, _ = LG.build_legs(df, cfg)
    out = outcomes(df, legs, horizon)
    rows = []
    for name, part in zip(("IS 2015→2021", "VAL 2022→2024-03"), split_periods(out)):
        lab = part["label"].value_counts(normalize=True).round(3).to_dict()
        rows.append({"period": name, "legs": len(part), **impulse_stats(part), **pullback_stats(part), **{f"share_{k}": v for k, v in lab.items()}})
    by_label = []
    for name, part in zip(("IS", "VAL"), split_periods(out)):
        for lab, g in part.groupby("label"):
            by_label.append({"period": name, "label": lab, "n": len(g), "fwd_mr_mean": round(float(g["fwd_mr"].mean()), 3),
                             "fwd_pos_pct": round(float((g["fwd_mr"] > 0).mean() * 100), 1), "resume_pct": round(float(g["resume"].mean() * 100), 1) if g["resume"].notna().any() else None})
    return {"summary": pd.DataFrame(rows), "by_label": pd.DataFrame(by_label), "legs": legs, "outcomes": out}


def sample_days(out, n=10, seed=11, period="IS"):
    """G1 साठी नमुना दिवस: प्रत्येक लेबल किमान एकदा दिसेल असे (स्थिर seed) — IS मधून (holdout नाही)."""
    part = split_periods(out)[0 if period == "IS" else 1].copy()
    part["day"] = pd.to_datetime(part["known_time"]).dt.normalize()
    rng = np.random.default_rng(seed)
    picked = []
    for lab in LG.LABELS:
        days = sorted(set(part[part["label"] == lab]["day"]) - set(picked))
        if days:
            picked.append(days[int(rng.integers(len(days)))])
    rest = sorted(set(part["day"]) - set(picked))
    while len(picked) < n and rest:
        picked.append(rest.pop(int(rng.integers(len(rest)))))
    return sorted(picked[:n])
