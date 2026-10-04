"""
level_memory.py
-----------------
🎓 वापरकर्त्याची मागणी ("Dynamic S/R चे levels पाहिजे तेवढे परफेक्ट नाहीत … chart वरच्या महत्त्वाच्या levels तिथेच असायला पाहिजेत,
बदलायला नकोत — म्हणजे trading decision चुकणार नाही आणि level hit झाल्यावर proper exit होईल"): MCX Futures चे Dynamic S/R levels रोजच्या
refresh मध्ये **स्मरणात ठेवणे** (level memory). शुद्ध functions — DB/network नाही.

आधीचं वर्तन: रोज रात्री compute_dynamic_sr() चे फक्त ताजे "top 5" (शेवटच्या 20 pivots वरून) साठवले जायचे आणि बाकी सर्व पुसले जायचे —
त्यामुळे cluster चा mid थोडा सरकला तरी level ची किंमत बदलायची, आणि top-5 मधून बाहेर पडलेला (पण chart वर स्पष्ट दिसणारा) level नाहीसा व्हायचा.

नवीन नियम (प्रत्येक timeframe साठी स्वतंत्र):
  1. ताजा level जुन्या ACTIVE level च्या `tol` (≈ 0.5×ATR, किंमतीच्या 0.08–0.40%) आत ⇒ **जुनीच किंमत कायम**, strength = दोन्हींपैकी जास्त,
     formed_date जुनीच (म्हणजे levels "उड्या" मारत नाहीत; आजचे hit-count/Hit Log त्याच किंमतीवर राहतात).
  2. ताज्या यादीत नसलेला जुना level **ठेवला जातो**, जोपर्यंत: किंमत त्याच्या `tol` मध्ये शेवटच्या `retire_days` दिवसांत आलेली आहे किंवा तो
     त्याच काळात तयार झाला आहे, आणि तो सद्य किंमतीपासून `max_distance_pct` पेक्षा दूर नाही.
  3. Level तुटला तरी पुसला जात नाही — सद्य किंमतीच्या बाजूवरून त्याची भूमिका (SUPPORT/RESISTANCE) ठरते (support तुटला ⇒ resistance).
  4. एकमेकांच्या `tol` मध्ये आलेल्या दोन levels पैकी जास्त प्राधान्याचा एकच; प्रत्येक TF साठी कमाल `max_levels`.
     प्राधान्य: आज पुन्हा सापडलेला > जास्त strength > किंमतीच्या जवळ.
"""
import pandas as pd

ATR_PERIOD = 14


def zone_tolerance(df, price, atr_mult=0.5, min_pct=0.08, max_pct=0.40):
    """किंमत-एककात tolerance: atr_mult × ATR(14) (त्या TF च्या candles वरून), किंमतीच्या [min_pct, max_pct]% मध्ये बांधलेली."""
    price = float(price)
    lo, hi = price * min_pct / 100, price * max_pct / 100
    if df is None or len(df) < ATR_PERIOD + 1:
        return lo
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(ATR_PERIOD).mean().iloc[-1])
    if atr != atr:                                                   # NaN
        return lo
    return min(max(atr * atr_mult, lo), hi)


def last_touch_time(df, level, tol):
    """level ± tol ला स्पर्श केलेल्या (low ≤ level+tol आणि high ≥ level−tol) शेवटच्या candle ची वेळ, किंवा None."""
    if df is None or not len(df):
        return None
    hit = df[(df["low"].astype(float) <= level + tol) & (df["high"].astype(float) >= level - tol)]
    return pd.Timestamp(hit["timestamp"].iloc[-1]) if len(hit) else None


def _ts(x):
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return None
    if t is pd.NaT:
        return None
    return t.tz_convert(None) if t.tzinfo is not None else t


def merge_levels(existing, fresh, df, price, now, retire_days=30, max_distance_pct=15.0, max_levels=12):
    """existing: [{"level", "strength", "formed_date"}] (त्या TF चे ACTIVE). fresh: [{"level", "touches"}] (आजची गणना, support+resistance).
    df: त्या TF चे candles (touch तपासण्यासाठी). रिटर्न: [{"level", "strength", "formed_date", "role", "fresh"}] (किंमतीनुसार क्रमाने)."""
    price, now = float(price), _ts(now)
    tol = zone_tolerance(df, price)
    cutoff = now - pd.Timedelta(days=retire_days)
    out, used = [], set()
    for f in fresh:
        lv = float(f["level"])
        match = None
        for i, e in enumerate(existing):
            if i not in used and abs(float(e["level"]) - lv) <= tol and (match is None or
                                                                          abs(float(e["level"]) - lv) < abs(float(existing[match]["level"]) - lv)):
                match = i
        if match is not None:
            used.add(match)
            e = existing[match]
            out.append({"level": float(e["level"]), "strength": max(float(e.get("strength") or 0), float(f.get("touches") or 0)),
                        "formed_date": e.get("formed_date") or now, "fresh": True})
        else:
            out.append({"level": lv, "strength": float(f.get("touches") or 0), "formed_date": now, "fresh": True})
    for i, e in enumerate(existing):
        if i in used:
            continue
        lv = float(e["level"])
        if abs(lv - price) / price * 100 > max_distance_pct:
            continue
        formed = _ts(e.get("formed_date"))
        touched = last_touch_time(df, lv, tol)
        if (touched is not None and _ts(touched) >= cutoff) or (formed is not None and formed >= cutoff):
            out.append({"level": lv, "strength": float(e.get("strength") or 0), "formed_date": e.get("formed_date") or now, "fresh": False})
    out.sort(key=lambda z: (not z["fresh"], -z["strength"], abs(z["level"] - price)))
    kept = []
    for z in out:
        if all(abs(z["level"] - k["level"]) > tol for k in kept):
            kept.append(z)
        if len(kept) >= max_levels:
            break
    for z in kept:
        z["role"] = "SUPPORT" if z["level"] <= price else "RESISTANCE"
    return sorted(kept, key=lambda z: z["level"])
