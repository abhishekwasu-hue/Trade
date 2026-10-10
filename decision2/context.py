"""decision2/context.py — थर 7 बाह्य rows (Abhi उत्तर 14), सगळे `known_at` सह; फक्त size_weight / नोंद (gate नाही).

- VIX: Upstox India VIX 15M candles (timestamp = candle सुरुवात); known_at = candle close (timestamp + 15 मिनिटं). bar t ला = bar_end[t]
  पर्यंत बंद झालेल्या शेवटच्या VIX candle चा close.
- Event calendar: `decision2/events.yaml` (data file); entry फक्त `added_on` ≤ त्या दिवशी दिसते. Size window (Abhi निर्णय 5): kind
  `event_size_kinds` (rbi / fomc / budget) ⇒ event दिवस (`ist_date` असेल तर तो) + आधीचे `event_sessions_before` sessions. expiry /
  holiday = calendar data.
- Macro row: `macro_daily` (वेगळा prompt, नंतर). आत्ता `macro_source = none` ⇒ NA, grade / size वर परिणाम नाही; `MacroDailyProvider`
  फक्त interface (रिकामा). Provider आल्यावर: value −1 … 1, `fetched_at` = known_at; bar t ला fetched_at ≤ bar_end[t] असलेली शेवटची row.
- Timestamps tz-aware असतील (उदा. +05:30 / UTC) ⇒ IST naive (m15 सारखे). जुनी row: VIX फक्त त्याच session ची; macro ≤ macro_max_age_h
  तास — त्यापलीकडे NA (नोंद "data नाही").
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS_PATH = os.path.join(HERE, "events.yaml")
KINDS = ("rbi", "fomc", "budget", "expiry", "holiday", "other")
VIX_BAR = pd.Timedelta(minutes=15)


class MacroDailyProvider:
    """`macro_daily` table साठी interface (Abhi निर्णय 4). आत्ता रिकामा: rows() ⇒ रिकामी DataFrame (fetched_at, value)."""

    source = "none"

    def rows(self, start=None, end=None):
        return pd.DataFrame({"fetched_at": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype=float)})


def load_events(path=EVENTS_PATH):
    """yaml ⇒ [{date, ist_date, name, kind, added_on, verify, symbol, series}] (तपासणीसह). फाईल नाही ⇒ []."""
    if not path or not os.path.exists(path):
        return []
    import yaml
    raw = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("events") or []
    out = []
    for e in raw:
        if not isinstance(e, dict) or not e.get("date") or not e.get("name") or not e.get("added_on"):
            raise ValueError(f"event entry अपूर्ण (date, name, added_on हवे): {e!r}")
        kind = str(e.get("kind") or "other")
        if kind not in KINDS:
            raise ValueError(f"event kind {kind!r} — {KINDS} पैकी हवं")
        d = pd.Timestamp(str(e["date"])).normalize()
        out.append({"date": d, "ist_date": pd.Timestamp(str(e["ist_date"])).normalize() if e.get("ist_date") else d,
                    "name": str(e["name"]), "kind": kind, "added_on": pd.Timestamp(str(e["added_on"])).normalize(),
                    "window": str(e.get("window") or "day"), "verify": bool(e.get("verify")), "symbol": e.get("symbol"),
                    "series": e.get("series")})
    return out


def event_bars(events, ts, kinds=None, before=None):
    """{bar: नाव} — size-kind event चा परिणाम-दिवस (ist_date) आणि त्याआधीचे `before` sessions (data मधले trading days); प्रत्येक bar ला
    entry फक्त added_on ≤ त्या bar चा दिवस (known_at)."""
    from . import settings as DS
    kinds = tuple(DS.DEFAULTS["event_size_kinds"] if kinds is None else kinds)
    before = int(DS.DEFAULTS["event_sessions_before"] if before is None else before)
    day = pd.to_datetime(pd.Series(ts)).dt.normalize()
    days = sorted(day.unique())
    dv = day.to_numpy()
    out = {}
    for e in events:
        if e["window"] != "day" or e["kind"] not in kinds:
            continue
        D = np.datetime64(e["ist_date"])
        prev = [d for d in days if d < D][-before:] if before else []
        for wd in prev + [D]:
            for t in np.flatnonzero(dv == np.datetime64(wd)):
                if e["added_on"] <= pd.Timestamp(dv[t]):
                    out[int(t)] = e["name"] if int(t) not in out else out[int(t)] + " + " + e["name"]
    return out


def _ist(x):
    x = pd.to_datetime(pd.Series(x))
    if getattr(x.dt, "tz", None) is not None:
        x = x.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return x


def vix_map(vix, bar_end):
    """vix = DataFrame(timestamp, close) — 15M candles. {bar: VIX} (known_at = candle close ≤ bar_end) + {bar: jump (आदल्या दिवशीच्या
    शेवटच्या close पासून %)}."""
    if vix is None or not len(vix):
        return {}, {}
    ts = _ist(vix["timestamp"]).reset_index(drop=True)
    v = pd.DataFrame({"ts": ts, "close": vix["close"].to_numpy(float)}).sort_values("ts").reset_index(drop=True)
    k = (v["ts"] + VIX_BAR).to_numpy()
    c = v["close"].to_numpy(float)
    vd = v["ts"].dt.normalize().to_numpy()
    last_prev = np.full(len(v), -1)                                                  # आदल्या session चा शेवटचा row (O(n))
    for i in range(1, len(v)):
        last_prev[i] = (i - 1) if vd[i - 1] < vd[i] else last_prev[i - 1]
    be = _ist(bar_end)
    bd = be.dt.normalize().to_numpy()
    idx = np.searchsorted(k, be.to_numpy(), side="right") - 1
    out, jump = {}, {}
    for t, i in enumerate(idx):
        if i < 0 or vd[i] != bd[t]:
            continue                                                                 # त्याच session चा VIX नाही ⇒ NA
        out[t] = float(c[i])
        p = last_prev[i]
        if p >= 0 and c[p] > 0:
            jump[t] = float(c[i] / c[p] - 1.0)
    return out, jump


def macro_map(rows, bar_end, max_age_h=None):
    """rows = DataFrame(fetched_at, value). {bar: value} (fetched_at ≤ bar_end, वय ≤ max_age_h तास)."""
    if rows is None or not len(rows):
        return {}
    from . import settings as DS
    age = float(DS.DEFAULTS["macro_max_age_h"] if max_age_h is None else max_age_h)
    r = pd.DataFrame({"k": _ist(rows["fetched_at"]).to_numpy(), "v": rows["value"].to_numpy(float)}).sort_values("k")
    k = r["k"].to_numpy()
    val = r["v"].to_numpy(float)
    be = _ist(bar_end).to_numpy()
    idx = np.searchsorted(k, be, side="right") - 1
    lim = np.timedelta64(int(age * 3600), "s")
    return {t: float(val[i]) for t, i in enumerate(idx) if i >= 0 and be[t] - k[i] <= lim}
