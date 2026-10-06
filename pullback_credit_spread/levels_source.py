"""
pullback_credit_spread/levels_source.py
---------------------------------------
🎓 Level engines → एकसारखं स्वरूप [{price, low, high, role ("SUPPORT"/"RESISTANCE"/"ZONE"), role_reversal}]. फक्त दिलेल्या (पूर्ण) bars वरून.
  • srv3          — sr_levels_v3.compute_sr_v3 (FLIP tag ⇒ role reversal).
  • major_levels  — price_action.major_levels (प्रायोगिक; ground-truth पडताळणी चालू).
  • oe_zones      — v1 मध्ये उपलब्ध नाही (Opportunity Engine zones Supabase store मधून; PAPER runner मध्ये जोडू) ⇒ रिकामी यादी + कारण.
"""
import pandas as pd

TF_TO_SRV3 = {"5m": "5minute", "15m": "15minute", "30m": "30minute", "1h": "1hour", "4h": "4hour", "1d": "day"}


def _resample(df, rule):
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    return d.set_index("timestamp").resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()


def srv3_levels(frames, spot):
    import sr_levels_v3
    fr = {TF_TO_SRV3[tf]: df for tf, df in frames.items() if tf in TF_TO_SRV3 and df is not None and len(df)}
    daily = fr.get("day")
    if daily is not None and len(daily) > 10 and "week" not in fr:
        fr["week"] = _resample(daily, "W-MON")
    res = sr_levels_v3.compute_sr_v3(fr, daily_df=daily, current_price=spot)
    out = []
    for z in res.get("levels", []):
        out.append({"price": float(z.get("level", (z["low"] + z["high"]) / 2)), "low": float(z["low"]), "high": float(z["high"]),
                    "role": z.get("role", "ZONE"), "role_reversal": any(str(t).startswith("FLIP") for t in z.get("tags", []))})
    return out, None if out else (res.get("meta", {}).get("reason") or "SR V3 levels नाहीत")


def major_levels(df, spot, exchange="NSE"):
    from price_action import major_levels as ML
    lv, _, info = ML.major_levels(df, exchange=exchange)
    tol = info.get("tol") or 0.0
    out = []
    for x in lv:
        lo, hi = x["price"] - tol, x["price"] + tol
        role = "RESISTANCE" if spot < lo else "SUPPORT" if spot > hi else "ZONE"
        out.append({"price": x["price"], "low": lo, "high": hi, "role": role, "role_reversal": bool(x["role_reversal"])})
    return out, None if out else "major levels नाहीत"


def get_levels(engine, frames, level_tf, spot):
    if engine == "srv3":
        return srv3_levels(frames, spot)
    if engine == "major_levels":
        df = frames.get(level_tf)
        return major_levels(df, spot) if df is not None and len(df) else ([], "level TF डेटा नाही")
    return [], f"{engine}: v1 मध्ये उपलब्ध नाही"
