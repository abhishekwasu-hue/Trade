"""mtf/adapter.py — timeframe च्या स्वतःच्या candles वर सगळे थर.

15M: खरे 15M candles (session = दिवस, थरांचे नियम जसेच्या तसे; 1m नसल्याने same-bar ला सावध नियम).
W / D / 1H: प्रत्येक candle = एक स्वतंत्र "session" (कृत्रिम business-दिवस, वेळ 10:00, bar_end 15:30) ⇒ σ = मागच्या `sigma_sessions`
candles चा median range (त्याच TF चा), warm-up = candles; थरांच्या code मध्ये बदल नाही. PDH / PDL सारखे session-स्रोत (k) zones बंद
(प्रत्येक candle session असल्याने अर्थहीन). खरी वेळ `real_ts` / `real_end` मध्ये (charts, top-down, known_at तुलना). Volume = NA.
Instrument चा holdout नियम (NIFTY sealed) खऱ्या वेळांवर इथेच लागू — holdout row engine पर्यंत जात नाही.
"""
import numpy as np
import pandas as pd

import instruments as INS
from decision2 import engine as DE
from elliott import data_policy as DP
from pivots import engine as PE
from rsi2 import engine as RE
from rsi2 import layer as RL
from scripts import leg_check2 as L2
from scripts import pattern_check2 as P2
from trendlines2 import engine as TE
from trendlines2 import layer as TL
from zones2 import engine as ZE
from zones2 import layer as ZL

TFS = ("W", "D", "1H", "15M")
TF_MR = {"W": "Weekly", "D": "Daily", "1H": "1H", "15M": "15M"}


def load_tf(path):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True)


def real_end(ts, tf):
    """त्या candle चा खरा बंद होण्याचा क्षण (known_at तुलनेसाठी)."""
    t = pd.to_datetime(ts)
    day_close = t.dt.normalize() + pd.Timedelta(hours=15, minutes=30)
    if tf == "W":
        return t.dt.normalize() + pd.to_timedelta(4 - t.dt.weekday, unit="D") + pd.Timedelta(hours=15, minutes=30)
    if tf == "D":
        return day_close
    step = pd.Timedelta(hours=1) if tf == "1H" else pd.Timedelta(minutes=15)
    return pd.concat([t + step, day_close], axis=1).min(axis=1)


def guard_real(df, instrument, tf=None):
    """instrument holdout नियम खऱ्या वेळांवर: holdout instrument (NIFTY) ⇒ ज्या candle चा [सुरुवात, बंद] काळ sealed holdout ला
    स्पर्शतो ती काढतो, आणि holdout च्या दोन्ही बाजूंचा data असेल तर फक्त नंतरची बाजू (gap ओलांडून candles जोडत नाही)."""
    if not INS.holdout(instrument):
        return df
    ts = pd.to_datetime(df["timestamp"])
    end = real_end(ts, tf) if tf else ts
    bad = [DP.period(a) == "HOLDOUT" or DP.period(b) == "HOLDOUT" for a, b in zip(ts, end)]
    d = df[[not x for x in bad]]
    after = pd.to_datetime(d["timestamp"]) >= DP.HOLDOUT_START
    if after.any() and (~after).any():
        d = d[after]
    return d.reset_index(drop=True)


SYN_EPOCH = (pd.Timestamp.min + pd.Timedelta(days=9000)).normalize()        # कृत्रिम sessions: pandas च्या सर्वात जुन्या काळाजवळ (वजाबाकीला जागा) ⇒ holdout / IS तारखांपर्यंत कधीच नाही


def check_tf_allowed(instrument, tf):
    """holdout instrument (NIFTY) ⇒ W / D फक्त display (थर नाहीत)."""
    if INS.holdout(instrument) and tf in ("W", "D"):
        raise DP.HoldoutError(f"{INS.label(instrument)} {tf}: holdout sealed ⇒ W / D वर थर नाहीत (फक्त display)")


def pseudo15(df, tf):
    """थरांचा input frame. 15M ⇒ खरा; बाकी ⇒ कृत्रिम sessions (एक candle = एक session)."""
    d = df.reset_index(drop=True).copy()
    d["real_ts"] = pd.to_datetime(d["timestamp"])
    d["real_end"] = real_end(d["real_ts"], tf)
    if tf == "15M":
        d["bar_end"] = d["real_ts"] + pd.Timedelta(minutes=15)
        return d, False
    days = pd.bdate_range(SYN_EPOCH, periods=len(d))
    d["timestamp"] = days + pd.Timedelta(hours=10)
    d["bar_end"] = days + pd.Timedelta(hours=15, minutes=30)
    return d, True


def build(df, tf, instrument=None, bars=None):
    """एका TF चे सगळे थर + engine निर्णय. रिटर्न C (decision2.engine.Ctx; + tf, real_ts, real_end, synthetic, D)."""
    ins = INS.get(instrument)["name"]
    check_tf_allowed(ins, tf)
    m15, syn = pseudo15(guard_real(df, ins, tf), tf)
    PE.guard(m15.rename(columns={"timestamp": "_syn", "real_ts": "timestamp"}), instrument=ins)   # खऱ्या वेळांवर पहारा
    prev = INS._current["name"]
    INS.set_current(ins)                                                       # थरांच्या आतला पहारा / segments याच instrument चे
    try:
        res, struct, lg, trk = L2.build_all(m15, None, None, None)
        f1, f2 = P2.build_folds(lg, trk)
        n = len(m15)
        bars = range(n) if bars is None else bars
        Z = ZE.Zones(lg, struct, trk, s={"k_atoms": False} if syn else None).run(snap_bars=bars)
        L4 = ZL.run(Z, f1, f2)
        E = TE.Engine(lg, struct)
        L5 = TL.run(E, trk, f1, Z, L4, bars=bars)
        R = RE.RSI(lg, struct)
        L6 = RL.run(R, trk, f1, L4, bars=bars)
        C = DE.Ctx(lg, struct, trk, f1, f2, Z, L4, L5, L6, ext={"expiries": None})
        C.tf, C.instrument, C.synthetic = tf, ins, syn
        C.real_ts = pd.to_datetime(m15["real_ts"]).reset_index(drop=True)
        C.real_end = pd.to_datetime(m15["real_end"]).reset_index(drop=True)
        C.D = DE.run(C, bars)
    finally:
        INS._current["name"] = prev
    return C


def bar_at(C, asof):
    """asof पर्यंत **बंद** झालेली शेवटची candle (known_at): real_end ≤ asof. नाही ⇒ None."""
    ok = np.flatnonzero((C.real_end <= pd.Timestamp(asof)).to_numpy())
    return int(ok[-1]) if len(ok) else None


def frame(path, tf, instrument=None):
    """dump scripts साठी: TF csv ⇒ (थरांचा input frame, खरी वेळ series)."""
    ins = INS.get(instrument)["name"]
    check_tf_allowed(ins, tf)
    m15, _ = pseudo15(guard_real(load_tf(path), ins, tf), tf)
    return m15, pd.to_datetime(m15["real_ts"]).reset_index(drop=True)


def window_real(real_ts, start=None, end=None, days=None):
    """खऱ्या तारखांवर [t0, t1) — --start / --end (समावेशक) नाहीतर शेवटच्या --days तारखा. रिटर्न (t0, t1, तारखा)."""
    day = pd.to_datetime(real_ts).dt.normalize()
    ds = sorted(day.unique())
    if end:
        ds = [d for d in ds if d <= pd.Timestamp(end)]
    if start:
        ds = [d for d in ds if d >= pd.Timestamp(start)]
    elif days:
        ds = ds[-int(days):]
    sel = np.flatnonzero(day.isin(ds).to_numpy())
    return (int(sel[0]), int(sel[-1]) + 1, ds) if len(sel) else (0, 0, [])


def tf_of_path(path):
    """<INS>_<TF>.csv.gz ⇒ TF. ओळखता न आल्यास ValueError (15M असं गृहीत धरत नाही)."""
    import os
    import re
    m = re.search(r"_(W|D|1H|15M)\.csv(\.gz)?$", os.path.basename(str(path)))
    if not m:
        raise ValueError(f"{path}: TF ओळखता आला नाही — --tf द्या")
    return m.group(1)
