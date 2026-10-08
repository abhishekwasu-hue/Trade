"""simple_core/flags.py — G8 flag channel area (Abhi 2026-10-08, 28 Sep): मजबूत impulse (wave 3) नंतरचा उथळ, overlapping flag.

G8 ला जुना horizontal zone लागत नाही — area = flag channel स्वतः (समांतर रेषा, प्रत्येक बाजूस ≥ flag_min_touches touches).
अटी (फक्त बंद bars, bar k = निर्णयाचा bar; flag = impulse टोकानंतर k − 1 पर्यंत):
  • flag bars ≥ flag_min_bars; retrace ≤ flag_retrace_max (50%) × impulse; overlap (K10.1) ≥ flag_overlap_min;
  • channel: (high + low) / 2 वर slope; वरची / खालची रेषा = त्या slope ने सगळ्या highs / lows ला वेढणारी; touches = रेषेच्या
    area_tol_mr आत; slope trend विरुद्ध किंवा सपाट (bear flag वर / बाजूला चढतो);
  • commitment candle flag च्या रेषेबाहेर close (bear ⇒ खालच्या रेषेखाली) — engine तपासतो (`breakout_ok`).
Futures volume (flag मध्ये कमी) — engine कडे नाही ⇒ shadow / context मध्ये [पुढे].
"""
import numpy as np
import pandas as pd

from . import settings as SS


def flag_zone(df, impulse, side, mr, s=None):
    """df = trigger बंद bars (शेवटचा = k). impulse = market_state impulse (to_ts, from, to). रिटर्न zone dict किंवा None."""
    s = SS.engine_settings(s)
    if not impulse or not side or not mr or impulse.get("to_ts") is None or len(df) < 6:
        return None
    if int(impulse.get("dir") or side) != side:
        return None
    ts = pd.to_datetime(df["timestamp"]).to_numpy()
    e = int(np.searchsorted(ts, np.datetime64(pd.Timestamp(impulse["to_ts"]))))
    k = len(df) - 1
    h, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    if e >= k and impulse.get("from_ts") is not None:                       # breakout bar नेच नवं टोक केलं ⇒ flag आधीचं टोक (k आधी)
        s0 = int(np.searchsorted(ts, np.datetime64(pd.Timestamp(impulse["from_ts"]))))
        if s0 < k - 1:
            e = s0 + (int(np.argmin(lo[s0:k])) if side < 0 else int(np.argmax(h[s0:k])))
            impulse = {**impulse, "to": float(lo[e] if side < 0 else h[e])}
    a, b = e + 1, k - 1                                                     # flag bars (commitment bar k वगळून)
    if e >= len(df) or b - a + 1 < int(s["flag_min_bars"]):
        return None
    size = abs(float(impulse["to"]) - float(impulse["from"]))
    end = float(impulse["to"])
    far = float(h[a:b + 1].max()) if side < 0 else float(lo[a:b + 1].min())
    if size <= 0 or abs(far - end) / size > float(s["flag_retrace_max"]):
        return None
    hh, ll = h[a:b + 1], lo[a:b + 1]
    ov = np.maximum(0.0, np.minimum(hh[1:], hh[:-1]) - np.maximum(ll[1:], ll[:-1])) / np.maximum(hh[1:] - ll[1:], 1e-9)
    if float((ov > 0.5).mean()) < float(s["flag_overlap_min"]):
        return None
    i = np.arange(len(hh), dtype=float)
    slope = float(np.polyfit(i, (hh + ll) / 2.0, 1)[0])
    if slope * side > float(s["flag_slope_tol_mr"]) * float(mr):            # trend दिशेने उतरणारा / चढणारा flag नाही
        return None
    up_off, lo_off = float((hh - slope * i).max()), float((ll - slope * i).min())
    tol = float(s["area_tol_mr"]) * float(mr)
    tu = int((hh >= up_off + slope * i - tol).sum())
    tl = int((ll <= lo_off + slope * i + tol).sum())
    if tu < int(s["flag_min_touches"]) or tl < int(s["flag_min_touches"]):
        return None
    n = float(k - a)                                                        # bar k वर रेषांचं मूल्य
    return {"id": f"FLAG-{a}", "zid": "F", "side": "sell" if side < 0 else "buy", "role": "RESISTANCE" if side < 0 else "SUPPORT",
            "tool": "g", "type": "flag channel", "kind": "solid", "state": "ACTIVE", "bar": int(e), "role_since": int(e), "slope": slope,
            "low": round(lo_off + slope * n, 2), "high": round(up_off + slope * n, 2), "touches": {"upper": tu, "lower": tl},
            "flag_bars": int(b - a + 1), "retrace": round(abs(far - end) / size, 3)}


def breakout_ok(area, close, side):
    """Flag channel area ⇒ commitment close रेषेबाहेर (bear ⇒ खालच्या रेषेखाली, bull ⇒ वरच्या वर). इतर areas ⇒ True."""
    if "flag channel" not in str(area.get("type", "")):
        return True
    return close < area["low"] if side < 0 else close > area["high"]
