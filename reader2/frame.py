"""reader2/frame.py — कोणत्याही timeframe चा OHLC(V) ⇒ `Chart` (legs2 features चा A, median range MR, known_at, volume).

MR[i] = (H − L) चा median, शेवटचे `mr_bars` bars (i सकट) — causal. Bar i ची मापं MR[i − 1] ने (त्या bar आधी माहीत), leg ची MR[i0] ने.
Volume: `volume` column (index ला जुळणाऱ्या futures चा — `with_futures_volume`); नाही / ≤ 0 ⇒ NaN ⇒ volume features NA.
Intraday ⇒ `first` = session चा पहिला bar (legs2: overnight gap वगळून); Daily व वरचे ⇒ gap leg चाच भाग (decision3.daily_legs सारखं).
"""
import numpy as np
import pandas as pd

from decision3 import daily as DD
from legs2 import volume as LV

from . import settings as RS


def _spacing(ts):
    if len(ts) < 2:
        return pd.Timedelta(days=1)
    return pd.Series(ts).diff().dropna().median()


class Chart:
    """एका frame चा context (truncate केलेल्या data वरच बनवा: look-ahead नाही)."""

    def __init__(self, df, s=None):
        self.s = s if RS.is_loaded(s) else RS.load(s)
        d = df.copy()
        d["timestamp"] = pd.to_datetime(d["timestamp"])
        d = d.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
        self.d = d
        ts = d["timestamp"]
        step = _spacing(ts)
        self.intraday = step < pd.Timedelta(hours=float(self.s["intraday_max_spacing_hours"]))
        day = ts.dt.normalize().to_numpy()
        first = np.r_[True, day[1:] != day[:-1]] if self.intraday else np.zeros(len(d), bool)
        self.A = {"o": d["open"].to_numpy(float), "h": d["high"].to_numpy(float), "l": d["low"].to_numpy(float),
                  "c": d["close"].to_numpy(float), "first": first}
        rng = self.A["h"] - self.A["l"]
        self.rng = rng
        self.mr = pd.Series(rng).rolling(int(self.s["mr_bars"]), min_periods=int(self.s["mr_min_bars"])).median().to_numpy()
        mr_prev = np.r_[np.nan, self.mr[:-1]]
        with np.errstate(divide="ignore", invalid="ignore"):
            self.rr = np.where(mr_prev > 0, rng / mr_prev, np.nan)          # legs2 displacement / climax चा rng_ratio (MR units)
        if "bar_end" in d.columns:
            self.kat = [pd.Timestamp(x) for x in d["bar_end"]]
        elif self.intraday:
            self.kat = [pd.Timestamp(x) + step for x in ts]
        else:
            self.kat = DD.known_at_of(d)
        vol = None
        if "volume" in d.columns:
            v = pd.to_numeric(d["volume"], errors="coerce").to_numpy(float).copy()
            v[~(v > 0)] = np.nan
            vol = v if np.isfinite(v).any() else None
        self.vol = vol
        self._pv = {}

    def __len__(self):
        return len(self.d)

    def pivots(self, k):
        """Directional-change pivots, threshold k × MR (decision3.daily.pivots_dc — causal: confirm_bar ला माहीत)."""
        k = round(float(k), 6)
        if k not in self._pv:
            self._pv[k] = DD.pivots_dc(self.d, k, self.mr, self.kat)
        return self._pv[k]


def with_futures_volume(spot, fut):
    """Spot (index) bars ला futures volume: प्रत्येक spot bar [t_i, t_(i+1)) मधल्या futures rows ची बेरीज. `expiry` / `contract`
    असेल तर त्या दिवशीचा near-month contract च (legs2.volume.expiry_of). Futures row नाही ⇒ NaN (NA-safe)."""
    out = spot.copy()
    out["volume"] = np.nan
    if fut is None or not len(fut) or "volume" not in fut.columns:
        return out
    f = fut.copy()
    f["timestamp"] = pd.to_datetime(f["timestamp"])
    if "expiry" in f.columns or "contract" in f.columns:
        f["expiry"] = LV.expiry_of(f)
        day = f["timestamp"].dt.normalize()
        f = f[f["expiry"].notna() & (f["expiry"] >= day)]
        f = f[f["expiry"] == f.groupby(f["timestamp"].dt.normalize())["expiry"].transform("min")]
    st = pd.to_datetime(out["timestamp"]).to_numpy()
    pos = np.searchsorted(st, f["timestamp"].to_numpy(), side="right") - 1
    step = _spacing(pd.to_datetime(out["timestamp"]))
    ok = pos >= 0
    ok &= f["timestamp"].to_numpy() < st[np.clip(pos, 0, len(st) - 1)] + step.to_timedelta64()
    sums = pd.Series(pd.to_numeric(f["volume"], errors="coerce").to_numpy(float)[ok]).groupby(pos[ok]).sum()
    vals = np.full(len(out), np.nan)
    vals[sums.index.to_numpy()] = sums.to_numpy()
    out["volume"] = vals
    return out
