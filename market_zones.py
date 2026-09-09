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

    🎓 वापरकर्त्याने प्रत्यक्ष Dashboard export मधून सापडवलेली bug — किंमत जर zone मधून थेट स्पर्श न
    करता "उडी मारून" (gap) पलीकडे गेली — म्हणजे एका candle चा close zone च्या एका बाजूला, पुढच्या
    candle चा open दुसऱ्या बाजूला, पण कुठल्याही candle चा [low,high] प्रत्यक्ष zone ला स्पर्शतच नाही —
    तर आधीचा फक्त-overlap तर्क हे कधीच ओळखायचा नाही, आणि zone कायमचा चुकीने "ACTIVE" दाखवायचा
    (उदा. NIFTY CMP च्या खूप वर असलेला जुना "Bullish Order Block/Demand Zone"). आता
    `dynamic_sr_instant_trader.py` च्या check_level_crossed() सारखाच gap-through तर्कही तपासतो —
    zone च्या कुठल्याही टोकाला (zone_low किंवा zone_high) gap-through झालं तरी पुरेसं आहे, कारण
    किंमत त्या संपूर्ण range च्या पलीकडे गेली म्हणजे तो zone यापुढे "untouched support/resistance"
    राहत नाही.
    """
    if df_after_formation.empty:
        return False

    overlap = (df_after_formation["high"] >= zone_low) & (df_after_formation["low"] <= zone_high)
    if bool(overlap.any()):
        return True

    # established दोन call-sites वेगळ्या column-casing सह येतात (Order Block/Demand-Supply: lowercase
    # "open"/"close"; Unfilled Gap: "Open"/"Close") — दोन्ही चालावं म्हणून जी उपलब्ध आहे ती वापरणे.
    open_col = "open" if "open" in df_after_formation.columns else ("Open" if "Open" in df_after_formation.columns else None)
    close_col = "close" if "close" in df_after_formation.columns else ("Close" if "Close" in df_after_formation.columns else None)
    if open_col is None or close_col is None:
        return False  # gap-through तपासण्यासाठी लागणारे स्तंभच उपलब्ध नाहीत — फक्त direct-overlap निकाल

    prev_close = None
    for _, row in df_after_formation.iterrows():
        if prev_close is not None:
            lo, hi = min(prev_close, row[open_col]), max(prev_close, row[open_col])
            # zone_low किंवा zone_high यापैकी कुठलंही टोक या gap-range मध्ये सापडलं, तरी gap-through
            if lo <= zone_low <= hi or lo <= zone_high <= hi:
                return True
        prev_close = row[close_col]
    return False


def compute_all_zones(df_1h, df_15m, symbol, impulse_mult=1.5, avg_window=20,
                       base_lookback=4, base_tightness_mult=0.7, min_gap_pct=0.30, sr_top_n=5,
                       df_15m_recent=None, df_1m_recent=None):
    """
    संपूर्ण विश्लेषण एकत्र — S/R (1H वर), Order Blocks (1H वर), Demand/Supply Zones (1H वर),
    Unfilled Gaps (15M वर, established). प्रत्येक zone ला mitigation-स्थिती (FILLED/ACTIVE) सह.
    रिटर्न: DataFrame, saving/display दोन्हीसाठी सुसंगत रचनेत.

    🎓 वापरकर्त्याने चार्ट वि. प्रत्यक्ष trading मधल्या विसंगतीवरून सापडवलेली bug — established
    df_15m_recent (ऐच्छिक) — established Dynamic S/R (established, SRv2 Momentum-Filter Reversal
    साठी, established जे स्वतः 15-मिनिट candles वर काम करतं) साठी established df_15m (established,
    दीर्घकालीन Unfilled-Gap तपासणीसाठी योग्य असलेला, संपूर्ण १ वर्षाचा) ऐवजी established वेगळा,
    established Dashboard चार्टच्याच डीफॉल्ट (established, 15-मिनिटसाठी established २० दिवस) इतका
    **अलीकडचा** डेटा वापरणे. न दिल्यास established df_15m वरच पडतो (backward-compatible).

    🎓 वापरकर्त्याशी चर्चा करून पुढे स्पष्ट केलेला भेद — established 1-मिनिट आणि established 15-मिनिट
    candles वरून established pivot-clustering established **वेगळेच** levels देतो (established, 1-मिनिट
    वर जास्त, established जवळचे, कमी-निर्णायक pivots; established 15-मिनिट वर कमी, established जास्त
    अर्थपूर्ण pivots) — established दोन वेगळ्या रणनींतींना (established Instant Trader — established
    तात्काळ स्वभावासाठी established 1-मिनिट स्वतःचे levels; established SRv2 — established स्वतःच
    15-मिनिट रचना असल्यामुळे established df_15m_recent) established वेगळे zone_type नावांखाली
    (established DYNAMIC_SR_*_1M विरुद्ध established DYNAMIC_SR_*_15M) established वेगळे साठवले
    जातात — established एकाच नावाखाली established गल्लत होऊ नये म्हणून.
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

    # 🎓 established Dynamic S/R (15-मिनिट, established SRv2 Momentum-Filter Reversal साठी) —
    # established df_15m_recent (अलीकडचा, established chart-सारखा डेटा) वापरून, established
    # DYNAMIC_SR_*_15M नावाने साठवलेला.
    df_dyn_sr_15m_source = df_15m_recent if df_15m_recent is not None else df_15m
    if len(df_dyn_sr_15m_source) >= 100:
        dyn_sr_15m = compute_dynamic_sr(df_dyn_sr_15m_source, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_15m.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_15m.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    # 🎓 established Dynamic S/R (1-मिनिट, established Instant Reversal Trader साठी) — established
    # df_1m_recent (दिलेला असल्यास) वापरून, established DYNAMIC_SR_*_1M नावाने वेगळा साठवलेला —
    # established तात्काळ (instant) स्वभावाला अनुसरून established स्वतःचे, established जास्त
    # जवळचे/बारीक levels.
    if df_1m_recent is not None and len(df_1m_recent) >= 100:
        dyn_sr_1m = compute_dynamic_sr(df_1m_recent, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_1m.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_1m.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_1M", "zone_low": r["level"], "zone_high": r["level"],
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
