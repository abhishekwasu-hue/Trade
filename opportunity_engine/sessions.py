"""opportunity_engine/sessions.py — NSE session calendar, session quality आणि NSE-anchored resamplers.

🎓 वापरकर्त्याने ठरवलेले bars (NSE):
  - 1H: 09:15, 10:15 … 15:15 (शेवटचा 15:15–15:30, फक्त 15 मिनिटांचा)
  - 4H: 09:15–13:15 आणि 13:15–15:30 (दुसरा 2h15m)
  - 5M/15M/30M: 09:15 पासूनचा grid.
जुनं `signals.resample_to_1h` bars ची सामग्री बरोबर देतं पण label `:00` (15 मि आधी) आणि `real_nifty_data` चे 240-bins 08:00/12:00 — म्हणून हे नवे resamplers.
`signals.resample_to_4h` (MCX) आणि जुने resamplers बदललेले नाहीत.

प्रत्येक bar चे columns:
  timestamp = bar_start (खरी सुरुवात — `:00` label नाही) · bar_start · bar_end (bar पूर्ण होण्याची वेळ; session-close ला मर्यादित) ·
  bar_is_full (bar चा नामित कालावधी पूर्ण आणि source डेटाने त्याला पूर्ण व्यापला) · bar_closed (source डेटाने bar_end पर्यंतचा पूर्ण कालावधी व्यापला —
  नाहीतर bar अजून चालू/अपूर्ण; Journal असे bars घेत नाही) · open/high/low/close/volume.
  Journal bar फक्त `bar_end ≤ t` झाल्यावरच वापरतो. `bar_is_full == False` bars (15:15 चा 30M/1H bar, 13:15 चा 4H bar, अपूर्ण/लहान session चा शेवट)
  ref_range/ADR च्या window मध्ये येत नाहीत, पण structure/zones मध्ये सामान्य candle म्हणून वापरले जातात.
Session quality: regular hours (09:15–15:29) बाहेरचे bars (Muhurat संध्याकाळ, 16:59 पर्यंत चालणारे दिवस) वगळले जातात; ज्या दिवशी डेटा 09:20 नंतर सुरू किंवा
15:25 आधी संपतो तो "short session" म्हणून flag होतो.
"""
import datetime

import numpy as np
import pandas as pd

from . import cas as CAS

SESSION_OPEN = datetime.time(9, 15)
SESSION_CLOSE = datetime.time(15, 30)
_OPEN_MIN = 9 * 60 + 15
_CLOSE_MIN = 15 * 60 + 30
_VOLUME = "volume"


def _step_minutes(ts):
    s = pd.Series(pd.to_datetime(ts)).sort_values()
    diffs = s.diff().dropna()
    diffs = diffs[(diffs > pd.Timedelta(0)) & (diffs < pd.Timedelta(hours=20))]
    if diffs.empty:
        return 1.0
    return max(float(diffs.median() / pd.Timedelta(minutes=1)), 1.0)


def filter_regular_hours(df):
    """09:15 ≤ bar-start < 15:30 असलेले bars फक्त (Muhurat संध्याकाळ, after-hours वगळले). इनपुट अबाधित."""
    if df is None or df.empty:
        return df
    mins = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    return df[(mins >= _OPEN_MIN) & (mins < _CLOSE_MIN)].reset_index(drop=True)


def session_quality(df, min_start_min=_OPEN_MIN + 5, min_end_min=_CLOSE_MIN - 5):
    """प्रत्येक दिवसाचा अहवाल: date, first, last_end, bars, short (डेटा 09:20 नंतर सुरू किंवा 15:25 आधी संपला). df आधी regular-hours फिल्टर केलेला असावा."""
    cols = ["date", "first", "last_end", "bars", "short"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    step = pd.Timedelta(minutes=_step_minutes(df["timestamp"]))
    d = df.assign(_date=df["timestamp"].dt.normalize())
    g = d.groupby("_date")["timestamp"].agg(first="min", last="max", bars="count").reset_index()
    g["last_end"] = g["last"] + step
    first_min = g["first"].dt.hour * 60 + g["first"].dt.minute
    end_min = g["last_end"].dt.hour * 60 + g["last_end"].dt.minute
    g["short"] = (first_min > min_start_min) | (end_min < min_end_min)
    return g.rename(columns={"_date": "date"})[cols]


def _mask_cas(d, cas):
    """CAS bars (opportunity_engine/cas.py) चे OHLC NaN ⇒ aggregation मध्ये वगळले जातात; `_close_all` = official close साठी मूळ close."""
    m = CAS.cas_mask(d["timestamp"], cas).to_numpy()
    d = d.assign(_close_all=d["close"].to_numpy(float), _cas=m)
    if m.any():
        d.loc[m, ["open", "high", "low", "close"]] = np.nan
    return d


def _finish_cas(out, cas_bars):
    """पूर्ण CAS bins: "drop" ⇒ काढा (structure); "flat" ⇒ आधीच्या clean close वर flat bar, cas=True (chart grey)."""
    allcas = out["close"].isna()
    if not allcas.any():
        return out
    if cas_bars == "drop":
        return out[~allcas]
    prev = out["close"].ffill()
    for c in ("open", "high", "low", "close"):
        out.loc[allcas, c] = prev[allcas]
    return out[out["close"].notna()]


def resample_nse(df, minutes, cas=None, cas_bars="drop"):
    """NSE session-anchored (09:15) resample; bins दिवस ओलांडत नाहीत. df = कुठल्याही बारीक TF चा (1M/5M/15M/30M) OHLC.
    रिटर्न: timestamp(=bar_start), bar_start, bar_end, bar_is_full, open, high, low, close[, volume], official_close, cas.
    CAS (`cas` = setting / False): CAS bars चे OHLC वगळून high/low/close; `official_close` = bin चा शेवटचा मूळ close; `cas` = bin मध्ये CAS bar होता.
    पूर्ण CAS bins `cas_bars` नुसार ("drop" structure साठी / "flat" chart साठी). bar_end / bar_closed मूळ data वरूनच."""
    cols = ["timestamp", "bar_start", "bar_end", "bar_is_full", "bar_closed", "open", "high", "low", "close", _VOLUME, "official_close", "cas"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    minutes = int(minutes)
    d = filter_regular_hours(df)
    if d.empty:
        return pd.DataFrame(columns=cols)
    step = pd.Timedelta(minutes=_step_minutes(d["timestamp"]))
    d = _mask_cas(d, cas)
    day = d["timestamp"].dt.normalize()
    since_open = ((d["timestamp"] - day) / pd.Timedelta(minutes=1)).astype("int64") - _OPEN_MIN
    work = pd.DataFrame({"day": day, "bin": since_open // minutes, "open": d["open"], "high": d["high"], "low": d["low"], "close": d["close"],
                         "src_end": d["timestamp"] + step, "official_close": d["_close_all"], "cas": d["_cas"]})
    if _VOLUME in d.columns:
        work[_VOLUME] = d[_VOLUME].values
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "src_end": "max", "official_close": "last", "cas": "any"}
    if _VOLUME in work.columns:
        agg[_VOLUME] = "sum"
    out = work.groupby(["day", "bin"], sort=True).agg(agg).reset_index()
    open_t = out["day"] + pd.Timedelta(minutes=_OPEN_MIN)
    close_t = out["day"] + pd.Timedelta(minutes=_CLOSE_MIN)
    start = open_t + pd.to_timedelta(out["bin"] * minutes, unit="min")
    nominal_end = (start + pd.Timedelta(minutes=minutes)).where(start + pd.Timedelta(minutes=minutes) <= close_t, close_t)
    full_length = (start + pd.Timedelta(minutes=minutes)) <= close_t
    result = pd.DataFrame({
        "timestamp": start.astype("datetime64[ns]"), "bar_start": start.astype("datetime64[ns]"),
        "bar_end": nominal_end.astype("datetime64[ns]"),
        "bar_is_full": (full_length & (out["src_end"] >= nominal_end)).values,
        "bar_closed": (out["src_end"] >= nominal_end).values,
        "open": out["open"], "high": out["high"], "low": out["low"], "close": out["close"],
    })
    result[_VOLUME] = out[_VOLUME].values if _VOLUME in out.columns else 0.0
    result["official_close"] = out["official_close"].values
    result["cas"] = out["cas"].astype(bool).values
    return _finish_cas(result, cas_bars)[cols].reset_index(drop=True)


def resample_nse_1h(df):
    return resample_nse(df, 60)


def resample_nse_4h(df):
    return resample_nse(df, 240)


def resample_nse_daily(df, cas=None):
    """प्रत्येक session चा एक bar: timestamp = तारीख (00:00), bar_start 09:15, bar_end 15:30, bar_is_full = डेटाने पूर्ण session (09:20 पर्यंत सुरू, 15:25 पर्यंत शेवट) व्यापला.
    CAS: high/low/close CAS bars वगळून (structure); `official_close` = दिवसाचा official close (auction) ⇒ PDC / gap गणित यावरून."""
    cols = ["timestamp", "bar_start", "bar_end", "bar_is_full", "bar_closed", "open", "high", "low", "close", _VOLUME, "official_close", "cas"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    d = filter_regular_hours(df)
    if d.empty:
        return pd.DataFrame(columns=cols)
    quality = session_quality(d).set_index("date")
    d = _mask_cas(d, cas)
    day = d["timestamp"].dt.normalize()
    g = d.assign(_day=day).groupby("_day").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                               official_close=("_close_all", "last"), cas=("_cas", "any"))
    if _VOLUME in d.columns:
        g[_VOLUME] = d.assign(_day=day).groupby("_day")[_VOLUME].sum()
    else:
        g[_VOLUME] = 0.0
    g = g.reset_index().rename(columns={"_day": "timestamp"})
    g["bar_start"] = g["timestamp"] + pd.Timedelta(minutes=_OPEN_MIN)
    g["bar_end"] = g["timestamp"] + pd.Timedelta(minutes=_CLOSE_MIN)
    g["bar_is_full"] = ~g["timestamp"].map(quality["short"]).fillna(True).astype(bool)
    g["bar_closed"] = (g["timestamp"].map(quality["last_end"]) >= g["timestamp"] + pd.Timedelta(minutes=_CLOSE_MIN)).fillna(False).astype(bool)    # शेवटचा bar 15:30 ला संपलेला
    for c in ("timestamp", "bar_start", "bar_end"):
        g[c] = g[c].astype("datetime64[ns]")
    g["cas"] = g["cas"].astype(bool)
    g = g[g["close"].notna()]                                            # (सगळे bars CAS — व्यवहारात नाही)
    return g[cols].reset_index(drop=True)


def daily_from_daily_bars(daily, now=None):
    """ज्या स्रोतात फक्त दैनिक candles आहेत (उदा. NSE bhav-copy extension, Upstox daily) — engine चे Daily bar columns जोडा.
    `now` (naive IST) दिला तर `bar_end > now` असलेला (आजचा अजून चालू) दैनिक bar bar_closed=False."""
    cols = ["timestamp", "bar_start", "bar_end", "bar_is_full", "bar_closed", "open", "high", "low", "close", _VOLUME]
    if daily is None or daily.empty:
        return pd.DataFrame(columns=cols)
    g = daily.copy()
    g["timestamp"] = pd.to_datetime(g["timestamp"]).dt.normalize().astype("datetime64[ns]")
    g["bar_start"] = (g["timestamp"] + pd.Timedelta(minutes=_OPEN_MIN)).astype("datetime64[ns]")
    g["bar_end"] = (g["timestamp"] + pd.Timedelta(minutes=_CLOSE_MIN)).astype("datetime64[ns]")
    g["bar_is_full"] = True
    g["bar_closed"] = True if now is None else (g["bar_end"] <= pd.Timestamp(now))
    if _VOLUME not in g.columns:
        g[_VOLUME] = 0.0
    return g[cols].reset_index(drop=True)


def build_frames(df_fine, daily_extra=None):
    """बारीक TF डेटा (1M/5M) -> {tf: engine frame} (5m, 15m, 1h, 4h, 1d). `daily_extra` = ऐच्छिक दैनिक-फक्त डेटा (fine डेटा संपल्यानंतरचा) Daily मध्ये जोडला जातो."""
    frames = {"5m": resample_nse(df_fine, 5), "15m": resample_nse(df_fine, 15), "1h": resample_nse_1h(df_fine),
              "4h": resample_nse_4h(df_fine), "1d": resample_nse_daily(df_fine)}
    if daily_extra is not None and len(daily_extra) and len(frames["1d"]):
        last = frames["1d"]["timestamp"].max()
        extra = daily_from_daily_bars(daily_extra)
        extra = extra[extra["timestamp"] > last]
        frames["1d"] = pd.concat([frames["1d"], extra], ignore_index=True)
    return frames
