"""
price_action/trendlines.py
----------------------------
🎓 वापरकर्त्याचं निरीक्षण (SILVER 30M, 25 Aug–23 Sep): "कधीकधी swings आडवे नसतात तर तिरके असतात — उतरती resistance trendline".
60M **पूर्ण** candles (45 दिवस) वर उतरती resistance (swing highs) आणि चढती support (swing lows) रेषा — opportunity_engine च्या आधीच tested
`find_trendline` वरून: A < B confirmed swings, A पासून शेवटच्या पूर्ण candle पर्यंत एकही close रेषेच्या पलीकडे नाही, उतार मर्यादित, किमान
`min_touches` swings रेषेवर (tolerance = 0.25 × median range). फक्त दाखवण्यासाठी आणि चाचणीसाठी (टप्पा 1) — trading नाही.
"""
import numpy as np
import pandas as pd

from opportunity_engine.detectors.patterns import find_trendline
from opportunity_engine.measures import ref_range
from signals import find_swings

KINDS = (("resistance", -1, "DESC_RESISTANCE"), ("support", +1, "ASC_SUPPORT"))


def completed_hours(df30, now):
    """30M (MCX, 09:00 पासून) -> फक्त पूर्ण झालेले 60M candles (timestamp = तासाची सुरुवात)."""
    if df30 is None or len(df30) == 0:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
    d = df30.copy()
    ts = pd.to_datetime(d["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["timestamp"] = ts
    h = d.set_index("timestamp").resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(subset=["open"]).reset_index()
    now_ts = pd.Timestamp(now)
    now_ts = now_ts.tz_convert("Asia/Kolkata").tz_localize(None) if now_ts.tzinfo else now_ts
    return h[h["timestamp"] + pd.Timedelta(minutes=60) <= now_ts].reset_index(drop=True)


def detect_trendlines(df60, min_touches=2, order=3, min_gap=5, max_slope_k=0.5):
    """df60 = पूर्ण 60M candles (जुनं ते नवं). रिटर्न [{kind, side, slope, a_ts, a_price, b_ts, b_price, end_ts, end_price, next_price, touches,
    touch_points, rr, line}] — प्रत्येक प्रकाराची सर्वात नवी वैध रेषा (नसेल तर वगळली)."""
    if df60 is None or len(df60) < 2 * order + min_gap + 2:
        return []
    df60 = df60.reset_index(drop=True)
    rr = ref_range(df60)
    if not np.isfinite(rr) or rr <= 0:
        return []
    sh, sl = find_swings(df60, order=order)
    n, out = len(df60), []
    for side, sign, kind in KINDS:
        tl = find_trendline(df60, rr, side, sign, order=order, min_gap=min_gap, max_slope_k=max_slope_k, min_touches=min_touches)
        if tl is None:
            continue
        y = df60["high" if side == "resistance" else "low"].to_numpy(float)
        idx = [i for i in (sh if side == "resistance" else sl) if tl.a <= i <= n - 1 - order]
        pts = [i for i in idx if abs(y[i] - tl.at(i)) <= 0.25 * rr]
        out.append({
            "kind": kind, "side": side, "slope": round(tl.m, 4), "rr": rr, "line": tl, "touches": len(pts),
            "a_ts": pd.Timestamp(df60["timestamp"].iloc[tl.a]), "a_price": round(tl.at(tl.a), 2),
            "b_ts": pd.Timestamp(df60["timestamp"].iloc[tl.b_idx]), "b_price": round(tl.at(tl.b_idx), 2),
            "end_ts": pd.Timestamp(df60["timestamp"].iloc[n - 1]), "end_price": round(tl.at(n - 1), 2),
            "next_price": round(tl.at(n), 2),
            "touch_points": [(pd.Timestamp(df60["timestamp"].iloc[i]), round(float(y[i]), 2)) for i in pts],
        })
    return out


def chart_segments(lines, df60, chart_start=None):
    """चार्टसाठी: प्रत्येक रेषेचे (वेळ, भाव) बिंदू — A पासून (चार्ट नंतर सुरू होत असेल तर तिथून) शेवटच्या पूर्ण तासापर्यंत + पुढचा तास.
    रिटर्न [{"kind", "title", "color", "points": [(ts, price), ...]}]."""
    out = []
    if not lines or df60 is None or len(df60) == 0:
        return out
    ts = pd.to_datetime(df60["timestamp"]).reset_index(drop=True)
    for ln in lines:
        tl = ln["line"]
        start = tl.a
        if chart_start is not None:
            later = np.nonzero((ts >= pd.Timestamp(chart_start)).to_numpy())[0]
            if len(later) == 0:
                continue
            start = max(start, int(later[0]))
        n = len(ts)
        if start >= n:
            continue
        pts = [(ts.iloc[start], round(tl.at(start), 2)), (ts.iloc[n - 1], round(tl.at(n - 1), 2)),
               (ts.iloc[n - 1] + pd.Timedelta(minutes=60), round(tl.at(n), 2))]
        res = ln["side"] == "resistance"
        out.append({"kind": ln["kind"], "color": "rgba(255,23,68,0.9)" if res else "rgba(0,200,83,0.9)",
                    "title": f"{'R' if res else 'S'} TL {ln['touches']}× · {ln['next_price']:,.2f}",
                    "points": pts})
    return out


def audit_touches(df60, min_touches=2, warmup=60, horizon=10, hold_rr=1.0, shifts=(-2.0, -1.0, 1.0, 2.0), recompute_every=1):
    """टिकण्याच्या दराची चाचणी (no-lookahead): प्रत्येक पूर्ण 60M candle i ला, फक्त [0, i) वरून रेषा शोधून, candle i ने रेषेला touch केला
    (resistance: आधीचा close रेषेखाली आणि high ≥ रेषा − tol) तर पुढच्या `horizon` candles मध्ये — आधी `hold_rr` × range इतकी उलटी चाल ⇒ HOLD,
    आधी रेषेपलीकडे close ⇒ BREAK, दोन्ही नाही ⇒ NONE. Control = त्याच उताराच्या समांतर रेषा (`shifts` × range ने सरकवलेल्या).
    रिटर्न DataFrame: ts, kind, group ("real"/"control"), outcome."""
    df60 = df60.reset_index(drop=True)
    hi, lo, cl = (df60[k].to_numpy(float) for k in ("high", "low", "close"))
    n, rows, seen, lines = len(df60), [], {}, []
    for i in range(warmup, n):
        if (i - warmup) % recompute_every == 0:
            lines = detect_trendlines(df60.iloc[:i], min_touches=min_touches)
        for ln in lines:
            tl, rr, res = ln["line"], ln["rr"], ln["side"] == "resistance"
            for group, shift in [("real", 0.0)] + [("control", s) for s in shifts]:
                off = shift * rr
                v = lambda x: tl.at(x) + off
                key = (ln["kind"], tl.a, tl.b_idx, shift)
                if i - seen.get(key, -99) <= 3:
                    continue
                tol = 0.25 * rr
                if res:
                    touch = cl[i - 1] < v(i - 1) and hi[i] >= v(i) - tol
                else:
                    touch = cl[i - 1] > v(i - 1) and lo[i] <= v(i) + tol
                if not touch:
                    continue
                seen[key] = i
                outcome = "NONE"
                for j in range(i, min(n, i + horizon)):
                    broke = cl[j] > v(j) if res else cl[j] < v(j)
                    held = lo[j] <= v(i) - hold_rr * rr if res else hi[j] >= v(i) + hold_rr * rr
                    if held and not broke:
                        outcome = "HOLD"
                        break
                    if broke:
                        outcome = "BREAK"
                        break
                rows.append({"ts": pd.Timestamp(df60["timestamp"].iloc[i]), "kind": ln["kind"], "group": group, "shift": shift, "outcome": outcome})
    return pd.DataFrame(rows, columns=["ts", "kind", "group", "shift", "outcome"])


def summarize_audit(events, is_frac=0.6):
    """real वि. control — touches, HOLD %, BREAK %, IS/OOS (तारखेनुसार पहिले is_frac दिवस IS)."""
    if events is None or events.empty:
        return pd.DataFrame()
    ev = events.copy()
    days = sorted(ev["ts"].dt.normalize().unique())
    cut = days[max(0, int(round(len(days) * is_frac)) - 1)]
    ev["set"] = np.where(ev["ts"].dt.normalize() <= cut, "IS", "OOS")
    rows = []
    for (st, kind, group), g in ev.groupby(["set", "kind", "group"]):
        rows.append({"set": st, "kind": kind, "group": group, "touches": len(g),
                     "HOLD %": round(100 * (g["outcome"] == "HOLD").mean(), 1), "BREAK %": round(100 * (g["outcome"] == "BREAK").mean(), 1)})
    return pd.DataFrame(rows).sort_values(["set", "kind", "group"], ascending=[True, True, False]).reset_index(drop=True)
