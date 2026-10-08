"""chart_reader/volume.py — KB K10.3: NIFTY futures चा volume ⇒ `rel_vol` ⇒ VL पुरावा (−5…+5).

🎓 Abhi (2026-10-08): pullback मध्ये volume कमी असतो. Index ला volume नाही ⇒ near-month NIFTY futures चे 5M candles
(`collect_index_futures_volume.py`, रोज VPS वर; आता पुढचा contract सुद्धा साठवला जातो).
  continuous  रोज एकच contract (causal roll): पहिल्या दिवशी जास्त volume चा; दिवस D ला दुसऱ्या (अजून न वापरलेल्या) contract चा volume
              चालू contract पेक्षा जास्त झाला ⇒ D+1 पासून तो (D चा निर्णय D संपल्यावरच — no-lookahead). मागे परत नाही.
              Roll नंतरचा पहिला दिवस `roll_day` ⇒ त्या दिवसाची rel_vol तुलना टाळतो (NaN).
  rel_vol     bar volume ÷ मागच्या vl_slot_days (20) **आधीच्या** दिवसांच्या त्याच वेळेच्या slot चा median (NSE U-shape, K14).
              < 5 आधीचे दिवस ⇒ NaN.
  VL          pullback dry-up (pullback rel_vol ÷ impulse rel_vol) < 0.8 ⇒ +3 · > 1.0 ⇒ −5 · C-end absorption spike (rel_vol ≥ 1.5,
              निव्वळ प्रगती ≤ 0.3 MR, close परत आत) किंवा reversal candle rel_vol ≥ 1.2 ⇒ +2 · C चा rel_vol A पेक्षा कमी ⇒ फक्त ओळ ·
              data नाही ⇒ 0 (trade अडत नाही).
⚠️ [NIFTY] मर्यादा: expired futures चा जुना volume मिळत नाही ⇒ IS / VAL मध्ये volume नाही; VL चं मूल्य फक्त live PAPER scorecard मधून.
"""
import numpy as np
import pandas as pd

OPEN = pd.Timedelta(hours=9, minutes=15)
MIN_PRIOR_DAYS = 5
COVERAGE_MIN = 0.6


def continuous(fut):
    """fut: timestamp, volume [, contract]. रिटर्न timestamp, volume, contract, roll_day (क्रमाने)."""
    if fut is None or not len(fut):
        return pd.DataFrame(columns=["timestamp", "volume", "contract", "roll_day"])
    f = fut.copy()
    f["timestamp"] = pd.to_datetime(f["timestamp"])
    if "contract" not in f.columns:
        f["contract"] = "FUT"
    f["contract"] = f["contract"].fillna("FUT").astype(str)
    f["day"] = f["timestamp"].dt.normalize()
    dv = f.groupby(["day", "contract"])["volume"].sum().unstack(fill_value=0.0).sort_index()
    used, cur, pick, roll = set(), None, {}, {}
    switch_next = None
    for day, row in dv.iterrows():
        rolled = False
        if switch_next is not None:
            cur, switch_next, rolled = switch_next, None, True
        if cur is None or row.get(cur, 0.0) <= 0:                     # सुरुवात / चालू contract चा data नाही (expired)
            avail = row[[c for c in row.index if c not in used and row[c] > 0]]
            if avail.empty:
                continue
            rolled = cur is not None
            cur = avail.idxmax()
        used.add(cur)
        pick[day], roll[day] = cur, rolled
        others = row[[c for c in row.index if c not in used]]
        if len(others) and others.max() > row[cur]:                      # D संपल्यावर ठरवलेलं ⇒ D+1 पासून
            switch_next = others.idxmax()
    f = f[f.apply(lambda r: pick.get(r["day"]) == r["contract"], axis=1)].copy()
    f["roll_day"] = f["day"].map(roll).fillna(False).astype(bool)
    return f.drop(columns="day").sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)


def to_tf(cont, tf_min):
    """5M ⇒ tf_min (09:15-anchored bins) volume बेरीज. रिटर्न timestamp (bar start), volume, roll_day."""
    if cont is None or not len(cont):
        return pd.DataFrame(columns=["timestamp", "volume", "roll_day"])
    t = pd.to_datetime(cont["timestamp"])
    day = t.dt.normalize()
    k = ((t - day - OPEN) // pd.Timedelta(minutes=int(tf_min))).astype(int)
    start = day + OPEN + k * pd.Timedelta(minutes=int(tf_min))
    g = cont.assign(timestamp=start).groupby("timestamp").agg(volume=("volume", "sum"), roll_day=("roll_day", "max"))
    return g.reset_index()


def rel_vol(v, days=20):
    """v: timestamp, volume [, roll_day]. रिटर्न Series (index = timestamp): volume ÷ त्याच slot च्या आधीच्या `days` दिवसांचा median
    (चालू दिवस वगळून; < MIN_PRIOR_DAYS ⇒ NaN; roll_day ⇒ NaN)."""
    if v is None or not len(v):
        return pd.Series(dtype=float)
    d = v.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    d = d.sort_values("timestamp").reset_index(drop=True)
    d["slot"] = d["timestamp"] - d["timestamp"].dt.normalize()
    vol = d["volume"].astype(float).where(d["volume"] > 0)
    base = vol.groupby(d["slot"]).transform(lambda x: x.shift(1).rolling(int(days), min_periods=MIN_PRIOR_DAYS).median())
    out = (vol / base).replace([np.inf, -np.inf], np.nan)
    if "roll_day" in d.columns:
        out[d["roll_day"].astype(bool).to_numpy()] = np.nan
    out.index = pd.DatetimeIndex(d["timestamp"])
    return out


def series_for(trig, fut5, tf_min, days=20):
    """trigger TF bars (timestamp = bar start) साठी rel_vol array (data नसेल तिथे NaN)."""
    if fut5 is None or not len(fut5):
        return np.full(len(trig), np.nan)
    rv = rel_vol(to_tf(continuous(_naive_ist(fut5)), tf_min), days)
    return _naive_ist(trig[["timestamp"]])["timestamp"].map(rv).to_numpy(float)


def _naive_ist(df):
    """timestamp tz-aware असेल तर IST मध्ये नेऊन naive (store naive IST आहे) — नाहीतर map सगळं NaN होऊन VL शांतपणे 0."""
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        df = df.copy()
        df["timestamp"] = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return df


def _mean(x):
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else None


def evidence(trig, st, rv, side, s, mr):
    """VL पुरावा. rv = trig bars शी जुळणारा rel_vol array (series_for). रिटर्न {pts, line, ratio, …}."""
    imp = st.get("impulse")
    if rv is None or not side or not imp or not np.isfinite(np.asarray(rv, float)).any():
        return {"pts": 0.0, "line": "VL 0 [K10.3]: futures volume data नाही ⇒ 0 (trade अडत नाही)", "ratio": None}
    rv = np.asarray(rv, float)
    n = len(trig)
    ib = np.arange(imp["start_bar"] + 1, imp["end_bar"] + 1)
    pb = np.arange(imp["end_bar"] + 1, n)
    cov = lambda ix: np.isfinite(rv[ix]).mean() if len(ix) else 0.0      # noqa: E731
    if cov(ib) < COVERAGE_MIN or cov(pb) < COVERAGE_MIN:
        return {"pts": 0.0, "line": "VL 0 [K10.3]: impulse / pullback ला पुरेसा futures volume नाही ⇒ 0", "ratio": None}
    ratio = _mean(rv[pb]) / max(_mean(rv[ib]), 1e-9)
    pts, why = 0.0, [f"pullback ÷ impulse rel_vol {ratio:.2f}"]
    if ratio < s["vl_dryup_max"]:
        pts += s["w_vl_dryup"]
        why.append("dry-up (healthy)")
    elif ratio > s["vl_rising_min"]:
        pts += s["w_vl_rising"]
        why.append("pullback मध्ये वाढता volume (धोका)")
    o, h, lo, c = (trig[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    cdir = -side
    bonus = None
    for j in range(max(imp["end_bar"] + 1, n - 3), n):
        if not np.isfinite(rv[j]):
            continue
        rng = max(h[j] - lo[j], 1e-9)
        cl = (c[j] - lo[j]) / rng
        prog = (c[j] - o[j]) * cdir
        if rv[j] >= s["vl_spike_min"] and prog <= s["vl_spike_prog_mr"] * mr and (cl >= 0.5 if side > 0 else cl <= 0.5):
            bonus = f"absorption spike (rel_vol {rv[j]:.2f})"
    if np.isfinite(rv[-1]) and (c[-1] - o[-1]) * side > 0 and rv[-1] >= s["vl_rev_min"]:
        bonus = bonus or f"reversal candle ला volume (rel_vol {rv[-1]:.2f})"
    if bonus:
        pts += s["w_vl_spike"]
        why.append(bonus)
    cb = st.get("correction_bars") or []
    if len(cb) >= 4:
        a_rv, c_rv = _mean(rv[cb[0] + 1:cb[1] + 1]), _mean(rv[cb[2] + 1:cb[3] + 1])
        if a_rv is not None and c_rv is not None and c_rv < a_rv:
            why.append(f"C चा volume A पेक्षा कमी ({c_rv:.2f} < {a_rv:.2f}) ⇒ थकवा")
    pts = float(np.clip(pts, -5.0, 5.0))
    return {"pts": pts, "line": f"VL {pts:+g} [K10.3]: " + "; ".join(why), "ratio": round(ratio, 3)}


def load(symbol="NIFTY", data_dir="data"):
    """Collector चे दोन्ही files एकत्र: front-only (जुना पूर्ण इतिहास, `contract` सह) + `_all` (front + पुढचा contract, नवीन).
    Key = (timestamp, contract), आधीचा row ठेवतो. नसेल ⇒ None."""
    import os
    from opportunity_engine.volume import merge_store_by_contract
    out = None
    for name in (f"oe_futures_5min_{symbol}.parquet", f"oe_futures_5min_{symbol}_all.parquet"):
        p = os.path.join(data_dir, name)
        if os.path.exists(p):
            d = pd.read_parquet(p)
            if "contract" not in d.columns:
                d["contract"] = "FUT"
            out = merge_store_by_contract(out, d)
    return out
