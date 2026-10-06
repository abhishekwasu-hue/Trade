"""
strike_breach_model.py
----------------------
🎓 Strike breach probability model (वापरकर्त्याचा निर्णय, 2026-10-06 — report-only, level-based filter नाही).
प्रश्न: "X% breach धोका मानला तर short strike किती दूर हवा?" — NIFTY IS (2015–2021) वर fit, VAL (2022 → 2024-03) वर calibration. Sealed holdout बंद.

रचना (आधीच ठरवलेली, tuning नाही):
  • डेटा: NIFTY offline 1M → daily (VAL_END hard-cut).
  • Entry: प्रत्येक दिवशी open ला, दोन्ही बाजू (put: strike खाली, call: वर), दोन expiries (जवळची आणि पुढची weekly).
    Weekly expiry = त्या आठवड्याचा गुरुवार (सुट्टी असल्यास आधीचा trading दिवस). 2019 पूर्वी NIFTY weekly options नव्हते — तरीही ही फक्त किंमत-मार्गाची
    आकडेवारी आहे (premium नाही), म्हणून तीच कॅलेंडर-रचना सर्व वर्षांना.
  • h = entry दिवसापासून expiry पर्यंतची सत्रे (दोन्ही धरून); DTE = h − 1 (0 = expiry दिवशी entry).
  • अंतर: z_rv = |ln(K/open)| ÷ (σ20 · √h), σ20 = मागच्या 20 दिवसांच्या close-to-close log returns चं std (दिवस i−1 पर्यंत);
          z_atr = |K − open| ÷ (ATR14 · √h), ATR14 Wilder (दिवस i−1 पर्यंत).
    Strike grid: z_rv ∈ GRID (प्रत्येक दिवस × बाजू × expiry साठी). त्याच strikes चा z_atr वेगळा मोजला ⇒ दोन्ही models एकाच rows वर.
  • Outcome: close = expiry दिवसाचा close strike पलीकडे (expiry ला ITM — मुख्य); touch = i..expiry मध्ये कधीही high/low पलीकडे (दुय्यम).
  • घटक (सर्व दिवस i−1 पर्यंतच्या डेटावरून):
      - regime: ADX14 (Wilder) > 25 trend, < 20 range, मधला mid; trend दिशा = sign(+DI − −DI); align = दिशा × बाजू (put साठी uptrend = "सोबत").
      - structure: opportunity_engine StructureTracker("1d") ची state (UP/UP_PB ⇒ +1, DN/DN_PB ⇒ −1, इतर 0) × बाजू.
      - DTE: ln(h) + 0DTE indicator (√h scaling पलीकडचा परिणाम).
      - आठवड्याचा वार: entry weekday dummies (DTE शी पूर्ण collinear नाही — दोन expiries मुळे).
      - बाजू (put/call).
  • Model: logistic regression (numpy IRLS, ridge λ = 1, निश्चित). M0 = फक्त z, z²; M_RV = पूर्ण (z_rv); M_ATR = पूर्ण (z_atr).
    Benchmark: Φ(−z_rv) (lognormal random walk).
  • VAL: Brier, log-loss, reliability bins (actual दरावर महिना-cluster bootstrap 90% CI), आणि calibrated अंतर-तक्ता
    (X ∈ 5…30%, DTE 0–4 × regime) + त्या cell मध्ये VAL actual (predicted X ± 2.5pp rows).

    python3 strike_breach_model.py --report docs/reports/strike_breach_model.md
"""
import argparse
import json
import math
import os
import time

import numpy as np
import pandas as pd

import leg_level_validation as T3
import real_nifty_data
from opportunity_engine.structure import DN, DN_PB, UP, UP_PB, StructureTracker

GRID = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
TARGETS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
RIDGE = 1.0
N_BOOT = 500
SEED = 11
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
REGIMES = ("trend_with", "trend_against", "mid", "range")


# ---------------------------------------------------------------------------------------------------------------------
# indicators (दिवस i च्या open ला माहीत: फक्त ≤ i−1)
# ---------------------------------------------------------------------------------------------------------------------
def wilder(x, n):
    out = np.full(len(x), np.nan)
    x = np.asarray(x, float)
    if len(x) < n:
        return out
    out[n - 1] = np.nanmean(x[:n])
    for i in range(n, len(x)):
        out[i] = out[i - 1] + (x[i] - out[i - 1]) / n
    return out


def daily_features(dd):
    """dd (timestamp/open/high/low/close) → प्रत्येक दिवस i साठी, **दिवस i−1 पर्यंतच्या** डेटावरून: sigma20, atr14, adx, di_dir, struct."""
    h, l, c = dd["high"].to_numpy(float), dd["low"].to_numpy(float), dd["close"].to_numpy(float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    tr[0] = h[0] - l[0]
    up, dn = np.r_[np.nan, np.diff(h)], np.r_[np.nan, -np.diff(l)]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr = wilder(tr, 14)
    pdi = 100 * wilder(pdm, 14) / atr
    ndi = 100 * wilder(ndm, 14) / atr
    dx = 100 * np.abs(pdi - ndi) / (pdi + ndi)
    adx = np.full(len(dx), np.nan)
    first = np.where(np.isfinite(dx))[0]
    if len(first) >= 14:
        adx[first[0]:] = wilder(dx[first[0]:], 14)
    lr = np.r_[np.nan, np.diff(np.log(c))]
    sig = pd.Series(lr).rolling(20, min_periods=20).std(ddof=1).to_numpy()
    tracker = StructureTracker("1d")
    st = np.zeros(len(dd))
    for i, r in enumerate(dd.itertuples(index=False)):
        tracker.on_bar(r.timestamp, r.open, r.high, r.low, r.close)
        st[i] = 1 if tracker.state in (UP, UP_PB) else (-1 if tracker.state in (DN, DN_PB) else 0)
    lag = lambda a: np.r_[np.nan, a[:-1]]                                               # noqa: E731 — दिवस i ला i−1 चं मूल्य
    return pd.DataFrame({"sigma20": lag(sig), "atr14": lag(atr), "adx": lag(adx), "di_dir": lag(np.sign(pdi - ndi)), "struct": lag(st)})


def expiry_days(ts):
    """trading दिवसांच्या यादीतून weekly expiry दिवस: प्रत्येक आठवड्यातला गुरुवारपर्यंतचा शेवटचा trading दिवस."""
    t = pd.Series(pd.to_datetime(ts)).dt.normalize()
    wk = t - pd.to_timedelta(t.dt.weekday, unit="D")
    ok = t.dt.weekday <= 3
    return set(t[ok].groupby(wk[ok]).max())


# ---------------------------------------------------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------------------------------------------------
def build_rows(dd, grid=GRID):
    dd = dd.reset_index(drop=True)
    f = daily_features(dd)
    days = pd.to_datetime(dd["timestamp"]).dt.normalize()
    exp = sorted(expiry_days(days))
    exp_idx = [int(np.searchsorted(days.to_numpy(), np.datetime64(e))) for e in exp]
    o, h, l, c = (dd[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    per = [T3.period_of(t) for t in days]
    rows = []
    for i in range(len(dd)):
        p = per[i]
        s20, atr = f.at[i, "sigma20"], f.at[i, "atr14"]
        if p is None or not (np.isfinite(s20) and np.isfinite(atr) and s20 > 0 and atr > 0 and np.isfinite(f.at[i, "adx"])):
            continue
        k = int(np.searchsorted(exp_idx, i))
        for which, ei in (("near", k), ("next", k + 1)):
            if ei >= len(exp_idx):
                continue
            e = exp_idx[ei]
            if per[e] != p:                                                               # hold-window IS/VAL सीमा ओलांडू नये
                continue
            n = e - i + 1
            adx, ddir, stc = f.at[i, "adx"], f.at[i, "di_dir"], f.at[i, "struct"]
            for side in (1, -1):                                                          # +1 put (खाली), −1 call (वर)
                for z in grid:
                    K = o[i] * math.exp(-side * z * s20 * math.sqrt(n))
                    seg_l, seg_h = l[i:e + 1].min(), h[i:e + 1].max()
                    touch = seg_l <= K if side > 0 else seg_h >= K
                    close = c[e] < K if side > 0 else c[e] > K
                    rows.append({"date": days[i], "period": p, "expiry": which, "h": n, "dte": n - 1, "weekday": int(days[i].weekday()),
                                 "side": side, "z_rv": z, "z_atr": abs(K - o[i]) / (atr * math.sqrt(n)), "dist_pct": abs(K / o[i] - 1) * 100,
                                 "adx": adx, "align_adx": ddir * side, "align_struct": stc * side, "sigma20": s20, "atr14": atr, "spot": o[i],
                                 "touch": float(touch), "close": float(close)})
    return pd.DataFrame(rows)


def regime_of(adx, align):
    if adx > 25:
        return "trend_with" if align > 0 else ("trend_against" if align < 0 else "mid")
    return "range" if adx < 20 else "mid"


# ---------------------------------------------------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------------------------------------------------
def design(df, zcol, full=True):
    z = df[zcol].to_numpy(float)
    cols = {"z": z, "z2": z ** 2}
    if full:
        cols["ln_h"] = np.log(df["h"].to_numpy(float))
        cols["dte0"] = (df["dte"] == 0).astype(float).to_numpy()
        for wd in range(1, 5):                                                            # Mon = base
            cols[f"wd_{WEEKDAYS[wd]}"] = (df["weekday"] == wd).astype(float).to_numpy()
        reg = np.array([regime_of(a, s) for a, s in zip(df["adx"], df["align_adx"])])
        for r in ("trend_with", "trend_against", "range"):                                # mid = base
            cols[f"reg_{r}"] = (reg == r).astype(float)
        cols["struct_with"] = (df["align_struct"] > 0).astype(float).to_numpy()
        cols["struct_against"] = (df["align_struct"] < 0).astype(float).to_numpy()
        cols["call"] = (df["side"] < 0).astype(float).to_numpy()
    X = np.column_stack([np.ones(len(df))] + list(cols.values()))
    return X, ["const"] + list(cols)


def fit_logit(X, y, ridge=RIDGE, iters=50):
    b = np.zeros(X.shape[1])
    P = np.eye(X.shape[1]) * ridge
    P[0, 0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -35, 35)))
        W = p * (1 - p)
        g = X.T @ (y - p) - P @ b
        Hm = (X * W[:, None]).T @ X + P
        step = np.linalg.solve(Hm, g)
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return b


def predict(X, b):
    return 1 / (1 + np.exp(-np.clip(X @ b, -35, 35)))


FROZEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "reports", "strike_breach_model_coef.json")


def predict_frozen(rows, spec):
    """NIFTY IS वर fit केलेले गोठवलेले coefs (`strike_breach_model_coef.json`) दुसऱ्या instrument च्या rows वर — पुन्हा fit नाही."""
    X, names = design(rows, spec["zcol"], spec["full"])
    if list(names) != list(spec["names"]):
        raise ValueError(f"design स्तंभ जुळत नाहीत: {names} वि. {spec['names']}")
    return predict(X, np.asarray(spec["coef"], float))


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def scores(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {"brier": float(np.mean((p - y) ** 2)), "logloss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))}


def month_boot_ci(y, months, n_boot=N_BOOT, seed=SEED, q=(5, 95)):
    y, months = np.asarray(y, float), np.asarray(months)
    keys, inv = np.unique(months, return_inverse=True)
    if len(keys) < 3:
        return (np.nan, np.nan)
    s, n = np.bincount(inv, y, len(keys)), np.bincount(inv, minlength=len(keys)).astype(float)
    rng = np.random.default_rng(seed)
    w = np.stack([np.bincount(rng.integers(0, len(keys), len(keys)), minlength=len(keys)) for _ in range(n_boot)])
    rates = (w @ s) / np.maximum(w @ n, 1)
    return tuple(float(np.percentile(rates, x)) for x in q)


BINS = (0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0001)


def reliability(y, p, months):
    out = []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum() == 0:
            continue
        ci = month_boot_ci(y[m], months[m])
        out.append({"predicted": f"{lo:.0%}–{min(hi, 1):.0%}", "n": int(m.sum()), "mean_pred%": round(100 * p[m].mean(), 1),
                    "actual%": round(100 * y[m].mean(), 1), "actual_CI90": f"{100 * ci[0]:.1f}–{100 * ci[1]:.1f}"})
    return pd.DataFrame(out)


def required_z(b, names, target, h, weekday, regime, struct=0, call=0, zmax=3.0):
    """model invert: दिलेल्या घटकांवर P(breach) = target होईल असा z (bisection; z वाढला की p कमी). grid (≤ 3) बाहेर extrapolation नाही ⇒ सापडला नाही तर NaN."""
    def p_at(z):
        x = {"const": 1.0, "z": z, "z2": z * z, "ln_h": math.log(h), "dte0": float(h == 1), "call": float(call),
             "struct_with": float(struct > 0), "struct_against": float(struct < 0)}
        for wd in range(1, 5):
            x[f"wd_{WEEKDAYS[wd]}"] = float(weekday == wd)
        for r in ("trend_with", "trend_against", "range"):
            x[f"reg_{r}"] = float(regime == r)
        v = np.array([x.get(n, 0.0) for n in names])
        return 1 / (1 + math.exp(-float(np.clip(v @ b, -35, 35))))
    lo, hi = 0.0, zmax
    if p_at(lo) < target or p_at(hi) > target:
        return np.nan
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if p_at(mid) > target else (lo, mid)
    return (lo + hi) / 2


# ---------------------------------------------------------------------------------------------------------------------
def run(dd, log=print):
    rows = build_rows(dd)
    rows["month"] = rows["date"].dt.year * 100 + rows["date"].dt.month
    rows["regime"] = [regime_of(a, s) for a, s in zip(rows["adx"], rows["align_adx"])]
    IS, VAL = rows[rows["period"] == "IS"].reset_index(drop=True), rows[rows["period"] == "VAL"].reset_index(drop=True)
    log(f"rows: IS {len(IS)}, VAL {len(VAL)}")
    res = {"rows": rows, "metrics": [], "reliability": {}, "coef": {}, "tables": {}}
    for outcome in ("close", "touch"):
        yI, yV = IS[outcome].to_numpy(), VAL[outcome].to_numpy()
        models = {}
        for name, zcol, full in (("M0 (z_rv, z²)", "z_rv", False), ("M_RV (पूर्ण)", "z_rv", True), ("M_ATR (पूर्ण)", "z_atr", True)):
            XI, names = design(IS, zcol, full)
            b = fit_logit(XI, yI)
            pV = predict(design(VAL, zcol, full)[0], b)
            models[name] = (b, names, pV)
            res["metrics"].append({"outcome": outcome, "model": name, **{f"VAL_{k}": round(v, 5) for k, v in scores(yV, pV).items()},
                                   **{f"IS_{k}": round(v, 5) for k, v in scores(yI, predict(XI, b)).items()}})
        if outcome == "close":
            pN = np.array([norm_sf(z) for z in VAL["z_rv"]])
            res["metrics"].append({"outcome": outcome, "model": "Φ(−z) random walk", **{f"VAL_{k}": round(v, 5) for k, v in scores(yV, pN).items()}})
        b, names, pV = models["M_RV (पूर्ण)"]
        lo, hi = coef_boot_ci(IS, "z_rv", outcome)
        res.setdefault("frozen", {})[outcome] = {nm: {"zcol": zc, "full": fl, "names": models[nm][1], "coef": [float(x) for x in models[nm][0]]}
                                                 for nm, zc, fl in (("M0 (z_rv, z²)", "z_rv", False), ("M_RV (पूर्ण)", "z_rv", True),
                                                                    ("M_ATR (पूर्ण)", "z_atr", True))}
        res["coef"][outcome] = pd.DataFrame({"घटक": names, "coef": np.round(b, 3), "odds_ratio": np.round(np.exp(b), 3),
                                             "OR_CI90": [f"{math.exp(a):.2f}–{math.exp(c):.2f}" for a, c in zip(lo, hi)],
                                             "CI 1 ओलांडतो?": ["हो" if a <= 0 <= c else "नाही" for a, c in zip(lo, hi)]})
        res["reliability"][outcome] = reliability(yV, pV, VAL["month"].to_numpy())
        res["tables"][outcome] = distance_table(b, names, VAL, pV, yV, IS)
        res.setdefault("shift", {})[outcome] = regime_shift_table(b, names)
    return res


N_COEF_BOOT = 200


def coef_boot_ci(IS, zcol, outcome, n_boot=N_COEF_BOOT, seed=SEED):
    """महिना-cluster bootstrap (IS महिने replacement सह, पुन्हा fit) ⇒ प्रत्येक coef चा 90% CI. rows स्वतंत्र नाहीत (एका दिवसाचे अनेक strikes)."""
    X, _ = design(IS, zcol, True)
    y = IS[outcome].to_numpy()
    months = IS["month"].to_numpy()
    keys = np.unique(months)
    idx = {k: np.where(months == k)[0] for k in keys}
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        pick = np.concatenate([idx[k] for k in rng.choice(keys, len(keys), replace=True)])
        bs.append(fit_logit(X[pick], y[pick], iters=25))
    bs = np.array(bs)
    return np.percentile(bs, 5, axis=0), np.percentile(bs, 95, axis=0)


def distance_table(b, names, VAL, pV, yV, IS):
    """मुख्य तक्ता: X% धोका ⇒ लागणारं अंतर — DTE 0–4 (जवळची expiry; weekday DTE वरून) × बाजू, regime = mid, structure तटस्थ.
    z, ≈ % spot (IS median σ20), ≈ ATR14-पट (IS median ATR ÷ (σ20·spot)). VAL actual: त्याच DTE × बाजू मधले rows ज्यांचा predicted X ± 2.5pp
    (महिना-cluster 90% CI). Regime चा परिणाम वेगळ्या तक्त्यात (regime_shift_table)."""
    med_sig = float(IS["sigma20"].median())
    atr_ratio = float((IS["atr14"] / (IS["sigma20"] * IS["spot"])).median())
    wd_of = {0: 3, 1: 2, 2: 1, 3: 0, 4: 4}                                                  # जवळची expiry (गुरुवार): DTE → weekday
    out = []
    dte, side, months = VAL["dte"].to_numpy(), VAL["side"].to_numpy(), VAL["month"].to_numpy()
    for d in range(5):
        hh = d + 1
        for sd, sname in ((1, "put"), (-1, "call")):
            for X in TARGETS:
                z = required_z(b, names, X, hh, wd_of[d], "mid", call=int(sd < 0))
                m = (dte == d) & (side == sd) & (np.abs(pV - X) <= 0.025)
                ok = np.isfinite(z)
                ci = month_boot_ci(yV[m], months[m]) if m.sum() >= 30 else (np.nan, np.nan)
                out.append({"DTE": d, "बाजू": sname, "धोका": f"{X:.0%}", "z (σ20·√h)": round(z, 2) if ok else None,
                            "≈ % spot": round((1 - math.exp(-z * med_sig * math.sqrt(hh))) * 100, 2) if ok else None,
                            "≈ ATR14-पट": round(z * math.sqrt(hh) / atr_ratio, 2) if ok else None,
                            "VAL n": int(m.sum()), "VAL actual%": round(100 * yV[m].mean(), 1) if m.sum() >= 30 else None,
                            "VAL CI90": f"{100 * ci[0]:.1f}–{100 * ci[1]:.1f}" if m.sum() >= 30 else None})
    return pd.DataFrame(out)


def regime_shift_table(b, names, target=0.10):
    """Regime / structure बदलल्यास 10% धोक्यासाठी लागणारं z किती बदलतं (DTE 2, put; mid / तटस्थ च्या तुलनेत)."""
    base = required_z(b, names, target, 3, 1, "mid")
    out = []
    for r in REGIMES:
        for st, sname in ((0, "तटस्थ"), (1, "सोबत"), (-1, "विरुद्ध")):
            z = required_z(b, names, target, 3, 1, r, struct=st)
            out.append({"ADX regime": r, "structure": sname, "z (10%)": round(z, 2), "Δz वि. mid/तटस्थ": round(z - base, 2)})
    return pd.DataFrame(out)


def _md(df):
    if df is None or not len(df):
        return "_(रिकामं)_\n"
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v) for v in r.tolist()) + " |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    df1m = real_nifty_data.load_nifty_1min()
    df1m = df1m[df1m["timestamp"] <= T3.VAL_END].reset_index(drop=True)                            # holdout कधीही नाही
    dd = T3.resample(df1m, "1D")
    res = run(dd, log=lambda m: print(m, flush=True))
    print(f"पूर्ण ({time.time() - t0:.0f}s)")
    if a.report:
        base = os.path.splitext(a.report)[0]
        pd.DataFrame(res["metrics"]).to_csv(base + "_metrics.csv", index=False)
        with open(os.path.join(os.path.dirname(a.report) or ".", "strike_breach_model_coef.json"), "w", encoding="utf-8") as f:
            json.dump({"fit": "NIFTY IS 2015–2021 (daily, offline 1M)", "ridge": RIDGE, "grid": list(GRID), "models": res["frozen"]},
                      f, ensure_ascii=False, indent=1)
        for oc in ("close", "touch"):
            res["tables"][oc].to_csv(f"{base}_table_{oc}.csv", index=False)
        cpath = base + "_conclusions.md"
        concl = open(cpath, encoding="utf-8").read() if os.path.exists(cpath) else "_(निष्कर्ष अजून लिहिलेला नाही.)_\n"
        txt = ["# Strike breach probability model — NIFTY (report-only)\n",
               "IS 2015–2021 वर fit, VAL 2022 → 2024-03 वर calibration. Sealed holdout बंद. Level-based filter नाही. रचना: `strike_breach_model.py` docstring.\n",
               "## 1. VAL वर models ची तुलना (कमी = चांगलं)\n", _md(pd.DataFrame(res["metrics"])),
               "\n## 2. Calibration — VAL, M_RV (expiry close breach)\n", _md(res["reliability"]["close"]),
               "\n## 3. Calibration — VAL, M_RV (touch breach)\n", _md(res["reliability"]["touch"]),
               "\n## 4. घटकांचा परिणाम (M_RV, IS fit; odds_ratio > 1 ⇒ breach जास्त)\n",
               "### expiry close\n", _md(res["coef"]["close"]), "\n### touch\n", _md(res["coef"]["touch"]),
               "\n## 5. Calibrated तक्ता — X% expiry-close breach धोक्यासाठी लागणारं अंतर (जवळची weekly expiry, ADX mid, structure तटस्थ)\n",
               "z = strike अंतर ÷ (σ20 · √h); h = DTE + 1. '% spot' आणि 'ATR-पट' = IS median σ20 / ATR वर अंदाजे (प्रत्यक्ष वापरात **चालू** σ20 ने "
               "z × σ20 × √h मोजावं). VAL actual = VAL मधले त्याच DTE × बाजू चे rows ज्यांचा predicted धोका X ± 2.5pp (n ≥ 30 असेल तरच; CI महिना-cluster).\n",
               _md(res["tables"]["close"]),
               "\n## 6. Regime / structure चा परिणाम (10% close-breach, DTE 2, put)\n", _md(res["shift"]["close"]),
               "\n## 7. तोच तक्ता — touch breach (SL-आधारित management साठी)\n", _md(res["tables"]["touch"]),
               "\n## 8. Regime / structure — touch (10%, DTE 2, put)\n", _md(res["shift"]["touch"]),
               "\n## निष्कर्ष\n", concl]
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("\n".join(txt))
        print(f"report: {a.report}")
    return res


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
