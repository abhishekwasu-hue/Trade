"""
market_zones.py
------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेलं module — "प्रत्येक वेळी पुन्हा गणना करण्याऐवजी, एकदाच संपूर्ण
विश्लेषण करून database मध्ये साठवणं, जेणेकरून भविष्यातलं trade-planning जलद होईल."

४ प्रकारचे zones, सर्व established/नव्याने-सिद्ध तर्कावर आधारित:
  १. Support/Resistance — signals.find_support_resistance_levels() (established, touch-count सह)
  २. Order Block — मोठ्या impulsive move च्याच आधीची शेवटची विरुद्ध candle
  ३. Demand/Supply Zone — impulsive move च्याच आधीचा संकुचित "base" (काही शांत candles)
  ४. Unfilled Gap — mtf_pullback_strategy.find_overnight_gaps() (established)

"Mitigation" (वापरकर्त्याने स्पष्ट सांगितल्याप्रमाणे) — किंमत त्या zone मध्ये परत आली की तो zone
"भरला/संपला" (FILLED) मानला जातो, पुन्हा active नाही.
"""
import pandas as pd

from signals import find_support_resistance_levels
from mtf_pullback_strategy import find_overnight_gaps
from sr_dynamic import compute_dynamic_sr


def detect_order_blocks(df, impulse_mult=1.5, avg_window=20):
    """
    🎓 वापरकर्त्याशी चर्चा करून ठरवलेली व्याख्या — Order Block = मोठ्या impulsive move च्याच आधीची
    शेवटची विरुद्ध दिशेची candle. Impulsive candle = body, मागच्या avg_window candles च्या सरासरी
    range पेक्षा impulse_mult पट मोठा.
    df स्तंभ अपेक्षित: timestamp/open/high/low/close (lowercase, established convention).
    """
    body = (df["close"] - df["open"]).abs()
    avg_range = (df["high"] - df["low"]).rolling(avg_window, min_periods=5).mean()
    is_impulsive_up = (df["close"] > df["open"]) & (body >= impulse_mult * avg_range)
    is_impulsive_down = (df["close"] < df["open"]) & (body >= impulse_mult * avg_range)

    blocks = []
    for i in range(avg_window, len(df)):
        if is_impulsive_up.iloc[i]:
            j = i - 1
            while j >= 0 and df["close"].iloc[j] >= df["open"].iloc[j]:
                j -= 1
            if j >= 0:
                blocks.append({"zone_type": "BULLISH_OB", "zone_low": float(df["low"].iloc[j]),
                                "zone_high": float(df["high"].iloc[j]), "formed_date": df["timestamp"].iloc[j]})
        elif is_impulsive_down.iloc[i]:
            j = i - 1
            while j >= 0 and df["close"].iloc[j] <= df["open"].iloc[j]:
                j -= 1
            if j >= 0:
                blocks.append({"zone_type": "BEARISH_OB", "zone_low": float(df["low"].iloc[j]),
                                "zone_high": float(df["high"].iloc[j]), "formed_date": df["timestamp"].iloc[j]})
    return blocks


def detect_demand_supply_zones(df, impulse_mult=1.5, avg_window=20, base_lookback=4, base_tightness_mult=0.7):
    """
    🎓 वापरकर्त्याशी चर्चा करून ठरवलेली व्याख्या — Demand/Supply Zone = impulsive move च्याच आधीचा
    संकुचित "base" (Order Block पेक्षा व्यापक — काही शांत, संकुचित-range candles चा एकत्रित range).
    """
    body = (df["close"] - df["open"]).abs()
    avg_range = (df["high"] - df["low"]).rolling(avg_window, min_periods=5).mean()
    candle_range = df["high"] - df["low"]
    is_impulsive_up = (df["close"] > df["open"]) & (body >= impulse_mult * avg_range)
    is_impulsive_down = (df["close"] < df["open"]) & (body >= impulse_mult * avg_range)

    zones = []
    for i in range(avg_window, len(df)):
        if not (is_impulsive_up.iloc[i] or is_impulsive_down.iloc[i]):
            continue
        base_start = i - 1
        count = 0
        while base_start >= 0 and count < base_lookback:
            if candle_range.iloc[base_start] > base_tightness_mult * avg_range.iloc[i]:
                break
            base_start -= 1
            count += 1
        base_start += 1
        if base_start > i - 1:
            continue
        zone_low = float(df["low"].iloc[base_start:i].min())
        zone_high = float(df["high"].iloc[base_start:i].max())
        zone_type = "DEMAND_ZONE" if is_impulsive_up.iloc[i] else "SUPPLY_ZONE"
        zones.append({"zone_type": zone_type, "zone_low": zone_low, "zone_high": zone_high,
                       "formed_date": df["timestamp"].iloc[base_start]})
    return zones


def compute_current_role(zone_low, zone_high, current_ltp):
    """
    🎓 वापरकर्त्याने स्पष्ट, थेट सांगितलेलं आणि महत्त्वाचं तत्त्व — zone चा ऐतिहासिक प्रकार (Order
    Block/Demand Zone/Supply Zone/इ.) काहीही असो, सद्य LTP च्या तुलनेत त्याची भूमिका ठरते:
    LTP पेक्षा zone वर असेल -> Resistance/Supply. LTP पेक्षा खाली असेल -> Support/Demand.
    (ऐतिहासिक "Bullish Order Block" लेबल असूनही, तो सद्य LTP च्या वर असेल तर तो आत्ता विक्री-दबावाचा
    (Resistance) भाग असू शकतो — फक्त तो कसा तयार झाला हे दाखवतो, आत्ताची भूमिका दाखवत नाही.)
    """
    zone_mid = (zone_low + zone_high) / 2
    return "RESISTANCE_SUPPLY" if zone_mid > current_ltp else "SUPPORT_DEMAND"


def is_zone_mitigated(zone_low, zone_high, df_after_formation):
    """
    🎓 वापरकर्त्याशी चर्चा करून ठरवलेला नियम — किंमत त्या zone मध्ये परत आली (range overlap झाला)
    की तो zone "mitigated" (भरला/संपला) मानायचा.
    """
    if df_after_formation.empty:
        return False
    overlap = (df_after_formation["high"] >= zone_low) & (df_after_formation["low"] <= zone_high)
    return bool(overlap.any())


def compute_all_zones(df_1h, df_15m, symbol, impulse_mult=1.5, avg_window=20,
                       base_lookback=4, base_tightness_mult=0.7, min_gap_pct=0.30, sr_top_n=5):
    """
    संपूर्ण विश्लेषण एकत्र — S/R (1H वर), Order Blocks (1H वर), Demand/Supply Zones (1H वर),
    Unfilled Gaps (15M वर, established). प्रत्येक zone ला mitigation-स्थिती (FILLED/ACTIVE) सह.
    रिटर्न: DataFrame, saving/display दोन्हीसाठी सुसंगत रचनेत.
    """
    rows = []
    now_date = df_1h["timestamp"].iloc[-1] if not df_1h.empty else None

    # --- Support/Resistance (established, संपूर्ण १ वर्षावरची) ---
    if len(df_1h) >= 20:
        sr = find_support_resistance_levels(df_1h, top_n=sr_top_n)
        for s in sr.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "SUPPORT", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in sr.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "RESISTANCE", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Chart वर दाखवला जाणारा Dynamic S/R
    # (sr_dynamic.compute_dynamic_sr — Pivot clustering, min_strength=2 आधीच फिल्टर) आतापर्यंत कुठेही
    # साठवला जात नव्हता, प्रत्येक वेळी Dashboard उघडल्यावर नव्याने मोजला जायचा. आता इथेही साठवतो —
    # जेणेकरून LTP-आधारित instant-trigger monitoring script याच साठवलेल्या levels वापरू शकेल.
    if len(df_15m) >= 100:
        dyn_sr = compute_dynamic_sr(df_15m, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    # --- Order Blocks (mitigation-तपासणीसह) ---
    for ob in detect_order_blocks(df_1h, impulse_mult, avg_window):
        after = df_1h[df_1h["timestamp"] > ob["formed_date"]]
        status = "FILLED" if is_zone_mitigated(ob["zone_low"], ob["zone_high"], after.iloc[1:]) else "ACTIVE"
        rows.append({"symbol": symbol, "zone_type": ob["zone_type"], "zone_low": ob["zone_low"],
                     "zone_high": ob["zone_high"], "strength": None, "formed_date": ob["formed_date"], "status": status})

    # --- Demand/Supply Zones (mitigation-तपासणीसह) ---
    for z in detect_demand_supply_zones(df_1h, impulse_mult, avg_window, base_lookback, base_tightness_mult):
        after = df_1h[df_1h["timestamp"] > z["formed_date"]]
        status = "FILLED" if is_zone_mitigated(z["zone_low"], z["zone_high"], after.iloc[1:]) else "ACTIVE"
        rows.append({"symbol": symbol, "zone_type": z["zone_type"], "zone_low": z["zone_low"],
                     "zone_high": z["zone_high"], "strength": None, "formed_date": z["formed_date"], "status": status})

    # --- Unfilled Gaps (established, 15M वर) ---
    if len(df_15m) >= 2:
        m15_std = df_15m.rename(columns={"timestamp": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close"})
        for g in find_overnight_gaps(m15_std, min_gap_pct):
            after = m15_std[m15_std["Date"] > g["gap_time"]]
            status = "FILLED" if is_zone_mitigated(g["gap_low"], g["gap_high"], after.rename(columns={"High": "high", "Low": "low"})) else "ACTIVE"
            rows.append({"symbol": symbol, "zone_type": g["kind"], "zone_low": g["gap_low"],
                         "zone_high": g["gap_high"], "strength": None, "formed_date": g["gap_time"], "status": status})

    return pd.DataFrame(rows)
