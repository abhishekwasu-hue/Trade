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
    return t.tz_convert("Asia/Kolkata").tz_localize(None) if t.tzinfo is not None else t      # सर्व वेळा IST, tz-शिवाय


def merge_levels(existing, fresh, df, price, now, retire_days=30, max_distance_pct=15.0, max_levels=12, role_by_price=True):
    """existing: [{"level", "strength", "formed_date"}] (त्या TF चे ACTIVE). fresh: [{"level", "touches"}] (आजची गणना, support+resistance).
    df: त्या TF चे candles (touch तपासण्यासाठी). रिटर्न: [{"level", "strength", "formed_date", "role", "fresh"}] (किंमतीनुसार क्रमाने).
    role_by_price=False (NIFTY bots -- तिथे zone ची भूमिका DB मध्ये स्थिर असते, breakout तर्क त्यावर अवलंबून) ⇒ ताज्या level ची भूमिका ताज्या
    गणनेची (`fresh[i]["role"]`), स्मरणातल्या जुन्या level ची त्याचीच जुनी (`existing[i]["role"]`) -- भूमिका बदलण्याचं वर्तन जुन्यासारखंच."""
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
                        "formed_date": e.get("formed_date") or now, "fresh": True, "role": f.get("role")})
        else:
            out.append({"level": lv, "strength": float(f.get("touches") or 0), "formed_date": now, "fresh": True, "role": f.get("role")})
    for i, e in enumerate(existing):
        if i in used:
            continue
        lv = float(e["level"])
        if abs(lv - price) / price * 100 > max_distance_pct:
            continue
        formed = _ts(e.get("formed_date"))
        touched = last_touch_time(df, lv, tol)
        if (touched is not None and _ts(touched) >= cutoff) or (formed is not None and formed >= cutoff):
            out.append({"level": lv, "strength": float(e.get("strength") or 0), "formed_date": e.get("formed_date") or now, "fresh": False,
                        "role": e.get("role")})
    out.sort(key=lambda z: (not z["fresh"], -z["strength"], abs(z["level"] - price)))
    kept = []
    for z in out:
        if all(abs(z["level"] - k["level"]) > tol for k in kept):
            kept.append(z)
        if len(kept) >= max_levels:
            break
    for z in kept:
        if role_by_price or z.get("role") not in ("SUPPORT", "RESISTANCE"):
            z["role"] = "SUPPORT" if z["level"] <= price else "RESISTANCE"
    return sorted(kept, key=lambda z: z["level"])


# ---------------------------------------------------------------------------------------------------------------------
# NIFTY/BANKNIFTY/SENSEX (5-Min Instant: 1M/5M, 15M SRv2: 15M/30M/60M) -- तेच स्मरण, वापरकर्त्याचा निर्णय "डीफॉल्ट चालू"
# ---------------------------------------------------------------------------------------------------------------------
# इतके दिवस किंमत जवळ आली नाही (आणि ताज्या गणनेत नाही) तर जुना level निवृत्त -- लहान TF चे levels लवकर जुने होतात
NSE_RETIRE_DAYS = {"1M": 2, "5M": 5, "15M": 15, "30M": 30, "60M": 30}
NSE_SETTINGS_KEY = {"1M": "1m_instant", "5M": "1m_instant", "15M": "15m_dynamic_sr", "30M": "15m_dynamic_sr", "60M": "15m_dynamic_sr"}


def _role_of(zone_type):
    return "SUPPORT" if "SUPPORT" in str(zone_type) else "RESISTANCE"


def existing_from_zones(zones_df, suffix, type_prefix="DYNAMIC_SR"):
    """market_zones (ACTIVE) मधून त्या TF चे levels -> merge_levels चा `existing` फॉरमॅट."""
    if zones_df is None or getattr(zones_df, "empty", True):
        return []
    types = (f"{type_prefix}_SUPPORT_{suffix}", f"{type_prefix}_RESISTANCE_{suffix}")
    rows = zones_df[zones_df["zone_type"].isin(types)]
    if "status" in rows.columns:
        rows = rows[rows["status"] == "ACTIVE"]
    return [{"level": float(r.zone_low), "strength": r.strength, "formed_date": r.formed_date, "role": _role_of(r.zone_type)}
            for r in rows.itertuples()]


def remember_dyn_sr(dyn_sr, zones_df, suffix, df, now, retire_days=None):
    """compute_dynamic_sr() चा निकाल + DB मधले जुने levels ⇒ स्मरणासह तोच {"support": [...], "resistance": [...]} फॉरमॅट (मग
    cloud_db.merge_dynamic_sr_zones ला दिला की जुळणारे जुने rows जसेच्या तसे राहतात, नवीन जोडले जातात, स्मरणात न राहिलेले STALE होतात).
    भूमिका स्थिर (role_by_price=False) -- NIFTY bots चं breakout/role वर्तन बदलत नाही."""
    if df is None or not len(df):
        return dyn_sr
    fresh = [{"level": z["level"], "touches": z["touches"], "role": role}
             for key, role in (("support", "SUPPORT"), ("resistance", "RESISTANCE")) for z in (dyn_sr or {}).get(key, [])]
    merged = merge_levels(existing_from_zones(zones_df, suffix), fresh, df, float(df["close"].iloc[-1]), now,
                          retire_days=NSE_RETIRE_DAYS.get(suffix, 30) if retire_days is None else retire_days, role_by_price=False)
    out = {"support": [], "resistance": []}
    for z in merged:
        out["support" if z["role"] == "SUPPORT" else "resistance"].append({"level": z["level"], "touches": z["strength"]})
    return out


def memory_enabled(symbol, suffix, get_settings):
    """त्या TF चा bot (1M/5M ⇒ 5-Min Instant, 15M+ ⇒ 15M SRv2) च्या settings मधलं level_memory_enabled (डीफॉल्ट चालू)."""
    try:
        return bool(get_settings(NSE_SETTINGS_KEY.get(suffix, "15m_dynamic_sr"), symbol).get("level_memory_enabled", True))
    except Exception:
        return True


def apply_memory_to_zone_rows(zones_df, existing_zones, frames_by_suffix, now, enabled_fn, symbol=None):
    """रोजचा पूर्ण (nightly) refresh: zones_df मधल्या DYNAMIC_SR_*_{TF} रांगा स्मरणासह बदलतो (formed_date जुनीच राहते -- म्हणून इथे थेट
    merge_levels). frames_by_suffix: {"5M": df, ...} (त्या TF चे candles). enabled_fn(suffix) -> bool. इतर zone_types ना हात नाही."""
    import pandas as _pd
    if zones_df is None or zones_df.empty:
        return zones_df
    out = zones_df
    for suffix, df in frames_by_suffix.items():
        if df is None or not len(df) or not enabled_fn(suffix):
            continue
        types = (f"DYNAMIC_SR_SUPPORT_{suffix}", f"DYNAMIC_SR_RESISTANCE_{suffix}")
        mask = out["zone_type"].isin(types)
        fresh = [{"level": float(r.zone_low), "touches": float(r.strength or 0), "role": _role_of(r.zone_type)} for r in out[mask].itertuples()]
        merged = merge_levels(existing_from_zones(existing_zones, suffix), fresh, df, float(df["close"].iloc[-1]), now,
                              retire_days=NSE_RETIRE_DAYS.get(suffix, 30), role_by_price=False)
        rows = [{"symbol": symbol if symbol is not None else (out["symbol"].iloc[0] if "symbol" in out.columns and len(out) else None),
                 "zone_type": f"DYNAMIC_SR_{z['role']}_{suffix}", "zone_low": z["level"], "zone_high": z["level"], "strength": z["strength"],
                 "formed_date": z["formed_date"], "status": "ACTIVE"} for z in merged]
        out = _pd.concat([out[~mask], _pd.DataFrame(rows, columns=out.columns.tolist())], ignore_index=True) if rows else out[~mask]
    return out
