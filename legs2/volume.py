"""legs2/volume.py — futures 15M volume ⇒ RVOL (थर 2 prompt §1.2 V). Futures फक्त volume साठी; spot candle शी वेळेनुसार जोडणी.

- Near-month continuous: प्रत्येक 5M row साठी, त्या दिवशी चालू असलेला सगळ्यात जवळचा contract (expiry ≥ दिवस). Expiry data मधल्या
  `expiry` field वरून, तो नसेल तर contract नावातल्या शेवटच्या तीन शब्दांतून (दिवस, महिना, वर्ष). वार / तारखेचा नियम नाही.
- "आधीचे sessions" एकाच trading calendar वरून (`elliott.contracts.TradingCalendar`: data मधले दिवस, त्यापुढे weekdays − NSE सुट्ट्या)
  ⇒ replay आणि live मध्ये तेच rollover दिवस.
- Rollover दिवस = monthly expiry चा दिवस आणि त्याआधीचे `roll_sessions_before` sessions ⇒ नेहमी `vol_unreliable`, baseline बाहेर.
- RVOL = candle चं volume ÷ त्याच 15-मिनिटांच्या slot चा, मागच्या `rvol_sessions` पात्र sessions चा median (त्याच segment मध्ये;
  sealed holdout चा एकही row नाही).
"""
import numpy as np
import pandas as pd

from elliott import data_policy as DP

BAR = pd.Timedelta(minutes=15)
OPEN = pd.Timedelta(hours=9, minutes=15)


def _segment(day):
    """Holdout एकच सलग block ⇒ त्याआधीचे sessions segment 0, नंतरचे 1 (baseline holdout ओलांडत नाही)."""
    return 0 if pd.Timestamp(day) < DP.HOLDOUT_START else 1


def no_holdout(df):
    ts = pd.to_datetime(df["timestamp"])
    return df[~((ts >= DP.HOLDOUT_START) & (ts < DP.CONTAMINATED_START))]


def expiry_of(fut):
    """`expiry` column, नाहीतर contract नावाचे शेवटचे तीन शब्द (DD MON YY). ओळखता न आलेला ⇒ NaT."""
    if "expiry" in fut.columns:
        return pd.to_datetime(fut["expiry"], errors="coerce").dt.normalize()
    tail = fut["contract"].astype(str).str.split().str[-3:].str.join(" ")
    return pd.to_datetime(tail, format="%d %b %y", errors="coerce").dt.normalize()


def near_month(fut5):
    """5M futures ⇒ फक्त near-month contract चे rows (timestamp, volume, expiry)."""
    if fut5 is None or not len(fut5):
        return pd.DataFrame(columns=["timestamp", "volume", "expiry"])
    f = no_holdout(fut5).copy()
    f["timestamp"] = pd.to_datetime(f["timestamp"])
    if "contract" not in f.columns:
        f["contract"] = ""
    f["expiry"] = expiry_of(f)
    if len(f) and f["expiry"].isna().all():
        import warnings
        warnings.warn("futures: एकाही row ची contract-expiry ओळखता आली नाही ⇒ volume नाही (V तटस्थ)")
    f = f[f["expiry"].notna() & (f["expiry"] >= f["timestamp"].dt.normalize())]
    near = f.groupby(f["timestamp"].dt.normalize())["expiry"].transform("min")
    f = f[f["expiry"] == near]
    return f[["timestamp", "volume", "expiry"]].sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)


def to_15m(nm):
    """5M ⇒ 15M (09:15-anchored) volume बेरीज. timestamp = 15M bar ची सुरुवात."""
    if not len(nm):
        return pd.DataFrame(columns=["timestamp", "volume", "expiry"])
    t = pd.to_datetime(nm["timestamp"])
    day = t.dt.normalize()
    start = day + OPEN + ((t - day - OPEN) // BAR) * BAR
    return nm.assign(timestamp=start).groupby("timestamp").agg(volume=("volume", "sum"), expiry=("expiry", "max")).reset_index()


def rollover_days(expiries, sessions, before=2):
    """Monthly expiry चा दिवस + त्याआधीचे `before` trading sessions (एकच calendar: replay = live)."""
    import datetime as dt

    from elliott import contracts as EC
    try:
        import config
        hol = set().union(*[set(v) for k, v in vars(config).items() if k.startswith("NSE_HOLIDAYS") and isinstance(v, (set, frozenset, list, tuple))])
    except Exception:                                           # noqa: BLE001 — config नसल्यास सुट्ट्या नाहीत
        hol = set()
    cal = EC.TradingCalendar(sessions, hol)
    out = set()
    for e in sorted({pd.Timestamp(x).normalize() for x in expiries if pd.notna(x)}):
        out.add(e)
        day, got = e.date(), 0
        while got < int(before):
            day -= dt.timedelta(days=1)
            if cal.is_trading(day):
                out.add(pd.Timestamp(day))
                got += 1
    return out


def rvol(m15, fut5, s):
    """Spot 15M bars शी जुळणारे arrays: rv (NaN = volume / baseline नाही), unreliable (bool)."""
    n = len(m15)
    rv, bad = np.full(n, np.nan), np.zeros(n, dtype=bool)
    nm = near_month(fut5)
    ts = pd.to_datetime(m15["timestamp"])
    days = ts.dt.normalize()
    sessions = sorted(days.unique())
    roll = rollover_days(nm["expiry"].unique() if len(nm) else [], sessions, int(s["roll_sessions_before"]))
    bad[:] = days.isin(list(roll)).to_numpy()
    v15 = to_15m(nm)
    if not len(v15):
        return rv, bad
    vol = pd.Series(v15["volume"].to_numpy(float), index=pd.to_datetime(v15["timestamp"]))
    mat = vol.groupby([vol.index.normalize(), vol.index - vol.index.normalize()]).sum().unstack()   # दिवस × slot
    need, keep = int(s["rvol_min_sessions"]), int(s["rvol_sessions"])
    ok_day = np.array([d not in roll for d in mat.index])
    seg = np.array([_segment(d) for d in mat.index])
    base = {}
    for slot in mat.columns:                                            # slot-wise: पात्र (rollover नाही, त्याच segment) आधीचे दिवस
        col = mat[slot].to_numpy(float)
        good = ok_day & np.isfinite(col)
        for i, d in enumerate(mat.index):
            prev = np.flatnonzero(good[:i] & (seg[:i] == seg[i]))[-keep:]
            base[(d, slot)] = float(np.median(col[prev])) if len(prev) >= need else np.nan
    pos = {d: i for i, d in enumerate(mat.index)}
    for i, (t, d) in enumerate(zip(ts, days)):
        slot = t - d
        if d not in pos or slot not in mat.columns:
            continue
        v, b = mat.at[d, slot], base.get((d, slot), np.nan)
        if np.isfinite(v) and np.isfinite(b) and b > 0:
            rv[i] = float(v) / b
    return rv, bad
