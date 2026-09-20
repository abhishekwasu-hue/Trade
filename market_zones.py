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
        # 🎓 वापरकर्त्याच्या तक्रारीवरून (Confluence Table मधली Demand/Supply Zone values नेहमी
        # रिकामी/doubtful दिसत होती) सापडवलेली, आधीपासूनच अस्तित्वात असलेली bug — formed_date आधी
        # base range च्या *पहिल्या* candle चा असायचा (base_start), पण is_zone_mitigated() ला दिला
        # जाणारा "after formation" स्लाईस (`df[timestamp > formed_date]`) त्यामुळे त्याच zone च्या
        # *उरलेल्या* base candles (base_start नंतरचे, अजूनही zone_low/high च्याच आत) समाविष्ट करायचा
        # — म्हणजे प्रत्येक multi-candle zone स्वतःच्याच base वरून जवळपास तात्काळ "mitigated"
        # (FILLED) ठरायचा, base_lookback=1 (एकाच candle चा base) असेल तरच अपवाद. आता formed_date =
        # base range च्या *शेवटच्या* candle चा (impulsive move च्या ऐन आधीचा) — जेणेकरून mitigation
        # तपासणी फक्त प्रत्यक्ष breakout नंतरपासूनच सुरू होते, स्वतःच्याच base विरुद्ध नाही.
        zones.append({"zone_type": zone_type, "zone_low": zone_low, "zone_high": zone_high,
                       "formed_date": df["timestamp"].iloc[i - 1]})
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
                       df_15m_recent=None, df_1m_recent=None, df_5m_recent=None,
                       df_30m_recent=None, df_60m_recent=None):
    """
    संपूर्ण विश्लेषण एकत्र — S/R (1H वर), Order Blocks (1H वर), Demand/Supply Zones (1H वर),
    Unfilled Gaps (15M वर). प्रत्येक zone ला mitigation-स्थिती (FILLED/ACTIVE) सह.
    रिटर्न: DataFrame, saving/display दोन्हीसाठी सुसंगत रचनेत.

    🎓 वापरकर्त्याने चार्ट वि. प्रत्यक्ष trading मधल्या विसंगतीवरून सापडवलेली bug — df_15m_recent
    (ऐच्छिक) — Dynamic S/R (SRv2 Momentum-Filter Reversal साठी, जे स्वतः 15-मिनिट candles वर
    काम करतं) साठी df_15m (दीर्घकालीन Unfilled-Gap तपासणीसाठी योग्य असलेला, संपूर्ण १ वर्षाचा)
    ऐवजी वेगळा, Dashboard चार्टच्याच डीफॉल्ट (15-मिनिटसाठी २० दिवस) इतका **अलीकडचा** डेटा
    वापरणे. न दिल्यास df_15m वरच पडतो (backward-compatible).

    🎓 वापरकर्त्याशी चर्चा करून पुढे स्पष्ट केलेली रचना (Dynamic S/R Instant Trader — 1-मिनिट +
    5-मिनिट pooled) — df_1m_recent/df_5m_recent (दोन्ही ऐच्छिक), Instant Trader च्याच तात्काळ
    स्वभावासाठी जवळचे/बारीक levels, DYNAMIC_SR_*_1M/*_5M नावाने. दोन्ही इथेच, रोज रात्रीच्या
    nightly refresh ने ताज्या (अलीकडच्या काही दिवसांच्याच) डेटावरून पुन्हा-गणना होतात — जेणेकरून
    दिवसभराच्या दर-५-मिनिटांच्या merge-cron ने (refresh_dynamic_sr_1m.py/refresh_dynamic_sr_5m.py)
    जपलेले, पण आता आठवडाभर जुने झालेले levels रोज योग्यरित्या ताजे होतात — कायमचे गोठलेले (frozen)
    राहत नाहीत. वापरकर्त्याने स्पष्ट सांगितलेला नियम: "दुसऱ्या दिवशी नवीन लेव्हल्स कॅल्क्युलेट
    झाल्यानंतर आदल्या सर्व झोन अपडेट व्हायला पाहिजे."

    🎓 वापरकर्त्याने सापडवलेली bug (SRv2 Momentum-Reversal चा "15M/30M/60M एकत्र" — प्रत्यक्षात फक्त
    15M) — df_30m_recent/df_60m_recent हे दोन्ही पॅरामीटर आधी अस्तित्वातच नव्हते, त्यामुळे
    DYNAMIC_SR_*_30M/*_60M हे zone_types कधीच generate व्हायचेच नाहीत — srv2_momentum_reversal_strategy.py
    तिन्ही timeframes (15M/30M/60M) तपासतो असं म्हणत असला, तरी प्रत्यक्षात 30M/60M साठी कधीच कुठलाही
    ACTIVE level सापडायचाच नाही (Signal Log मध्येही ते कधीच दिसायचे नाहीत). आता df_15m_recent
    प्रमाणेच, DYNAMIC_SR_*_30M/*_60M नावाने साठवले जातात.
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

    # 🎓 Dynamic S/R (30-मिनिट, SRv2 Momentum-Filter Reversal साठी) — df_30m_recent वापरून,
    # DYNAMIC_SR_*_30M नावाने. df_15m_recent सारखाच पॅटर्न.
    if df_30m_recent is not None and len(df_30m_recent) >= 100:
        dyn_sr_30m = compute_dynamic_sr(df_30m_recent, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_30m.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_30m.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    # 🎓 Dynamic S/R (60-मिनिट, SRv2 Momentum-Filter Reversal साठी) — df_60m_recent वापरून,
    # DYNAMIC_SR_*_60M नावाने (Upstox कडून "1hour" थेट verified नसल्याने, caller ने 30-मिनिट
    # candles resample करून द्यायचे — fetch_timeframe_df() मध्ये आधीच वापरलेला पॅटर्न).
    if df_60m_recent is not None and len(df_60m_recent) >= 100:
        dyn_sr_60m = compute_dynamic_sr(df_60m_recent, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_60m.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_60M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_60m.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_60M", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    # 🎓 Dynamic S/R (1-मिनिट, Instant Reversal Trader साठी) — df_1m_recent वापरून,
    # DYNAMIC_SR_*_1M नावाने. रोज रात्री इथे ताजी पुन्हा-गणना होते (दिवसभराच्या merge-cron ने
    # जपलेले जुने levels कायमचे गोठलेले राहू नयेत म्हणून).
    if df_1m_recent is not None and len(df_1m_recent) >= 100:
        dyn_sr_1m = compute_dynamic_sr(df_1m_recent, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_1m.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_1m.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_1M", "zone_low": r["level"], "zone_high": r["level"],
                         "strength": r["touches"], "formed_date": now_date, "status": "ACTIVE"})

    # 🎓 Dynamic S/R (5-मिनिट, Instant Reversal Trader साठी) — df_5m_recent वापरून,
    # DYNAMIC_SR_*_5M नावाने. वापरकर्त्याने Market Zones export मधून सापडवलेली bug — याआधी इथे
    # 5-मिनिट गणना अस्तित्वातच नव्हती, त्यामुळे रोज रात्रीच्या पूर्ण refresh मध्ये हे zone_types
    # कधीच पुन्हा तयार होत नसत — फक्त पुसले जायचे (save_market_zones() चं DELETE) आणि दुसऱ्या
    # दिवशी सकाळपासून दर-५-मिनिटांच्या merge-cron ने पुन्हा हळूहळू शून्यातून तयार व्हायला लागायचे.
    if df_5m_recent is not None and len(df_5m_recent) >= 100:
        dyn_sr_5m = compute_dynamic_sr(df_5m_recent, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for s in dyn_sr_5m.get("support", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": s["level"], "zone_high": s["level"],
                         "strength": s["touches"], "formed_date": now_date, "status": "ACTIVE"})
        for r in dyn_sr_5m.get("resistance", []):
            rows.append({"symbol": symbol, "zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": r["level"], "zone_high": r["level"],
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


# =========================================================
# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Market Zones — "5M/15M Confluence Table") —
# वापरकर्त्याने Classical S/R Reversal backtest साठी चर्चा केलेल्या संकल्पना (Swing High/Low वरून
# Demand/Supply — signals.analyze_chart_zones(), Order Block) आता Market Zones पानावरही, 5-मिनिट व
# 15-मिनिट या दोन्ही टाईमफ्रेम्ससाठी वेगळ्या, सद्य किमतीच्या सर्वात जवळचे दाखवणारा एक संगम-तक्ता.
# Support/Resistance साठी backend मुळे आधीच रोज रात्री साठवलेले DYNAMIC_SR_SUPPORT/RESISTANCE_{TF}
# levels वापरले जातात (पुन्हा गणना नाही, जलद) — Demand/Supply व Order Block मात्र इथेच, थेट (त्या
# specific timeframe साठी backend कधीच पूर्वगणना/साठवण करत नाही, फक्त 1H वर करतो).
# =========================================================

def _pick_nearest_level(levels, current_price, want_below):
    """levels: [(level, extra_dict), ...]. current_price च्या दिलेल्या बाजूला (want_below=True->खाली
    (Support), False->वर (Resistance)) सर्वात जवळचा एक निवडणे. काहीच सापडलं नाही तर None."""
    side = [lv for lv in levels if (lv[0] <= current_price if want_below else lv[0] >= current_price)]
    if not side:
        return None
    return min(side, key=lambda lv: abs(lv[0] - current_price))


def _pick_nearest_n_levels(levels, current_price, want_below, n=2):
    """_pick_nearest_level() सारखंच, पण सर्वात जवळचे (अंतरानुसार क्रमवारी) कमाल n levels — "पुढचा"
    (R2/S2) level दाखवण्यासाठी. काहीच सापडलं नाही तर रिकामी यादी."""
    side = [lv for lv in levels if (lv[0] <= current_price if want_below else lv[0] >= current_price)]
    side.sort(key=lambda lv: abs(lv[0] - current_price))
    return side[:n]


def compute_5m_15m_confluence_row(timeframe_label, df_tf, current_price,
                                    swing_order=3, impulse_mult=1.5, avg_window=20,
                                    base_lookback=4, base_tightness_mult=0.7):
    """
    एका टाईमफ्रेमसाठी (5M किंवा 15M) — Support/Resistance (signals.find_support_resistance_levels() —
    major Swing High/Low वरून, याच टाईमफ्रेमच्या candles वरून थेट/ताजी गणना — established Classical
    S/R Reversal strategy सारखीच पद्धत; आधी साठवलेले Dynamic S/R नाही — ते TradingView chart levels शी
    जुळत नसल्याने वापरकर्त्याने बदलायला सांगितलं; सद्य किमतीच्या सर्वात जवळचे दोन्ही -- "1" व "2",
    फक्त एकच नाही), Demand/Supply Zone (detect_demand_supply_zones() — established compute_all_zones()
    (nightly, 1H) साठीच वापरलेली, प्रत्यक्ष "base" candles च्या रेंजवर आधारित पद्धत -- वापरकर्त्याने
    सापडवल्याप्रमाणे आधीची analyze_chart_zones() ची निव्वळ ±0.3% सरसकट पट्टी (न-प्रत्यक्ष, फक्त एका
    किमतीभोवतीची tolerance-band, इथे "zone" म्हणून दाखवल्यास दिशाभूल करणारी/खूप रुंद) होती, आता
    Order Block सारखीच खरी candle-आधारित रुंदी), आणि सद्य किमतीच्या सर्वात जवळचा, अजून ACTIVE
    (mitigated नसलेला) Order Block — एकत्र एका dict मध्ये (raw numbers — UI/CSV दोन्हीसाठी वापरता
    यावेत म्हणून, आधीच फॉरमॅट केलेला मजकूर नाही).
    """
    row = {
        "timeframe": timeframe_label, "current_price": round(float(current_price), 2),
        "support_level": None, "support_distance_pct": None,
        "support_level_2": None, "support_distance_pct_2": None,
        "resistance_level": None, "resistance_distance_pct": None,
        "resistance_level_2": None, "resistance_distance_pct_2": None,
        "demand_zone_low": None, "demand_zone_high": None, "demand_zone_distance_pct": None,
        "supply_zone_low": None, "supply_zone_high": None, "supply_zone_distance_pct": None,
        "order_block_type": None, "order_block_low": None, "order_block_high": None, "order_block_distance_pct": None,
    }

    # --- Support/Resistance — Classical (major Swing High/Low वरून, याच टाईमफ्रेमच्या ताज्या candles
    # वरून थेट/लाईव्ह गणना, cluster केलेल्या सर्व levels मधून सद्य किमतीच्या सर्वात जवळचे दोन्ही -- "1"
    # (सर्वात जवळचा) व "2" (त्यापुढचा) ---
    if df_tf is not None and len(df_tf) >= swing_order * 2 + 1:
        classical_sr = find_support_resistance_levels(df_tf, order=swing_order, top_n=10)
        support_levels = [(c["level"], c) for c in classical_sr["support"]]
        resistance_levels = [(c["level"], c) for c in classical_sr["resistance"]]
        nearest_supports = _pick_nearest_n_levels(support_levels, current_price, want_below=True)
        nearest_resistances = _pick_nearest_n_levels(resistance_levels, current_price, want_below=False)
        if len(nearest_supports) >= 1:
            row["support_level"] = round(nearest_supports[0][0], 2)
            row["support_distance_pct"] = round((nearest_supports[0][0] - current_price) / current_price * 100, 3)
        if len(nearest_supports) >= 2:
            row["support_level_2"] = round(nearest_supports[1][0], 2)
            row["support_distance_pct_2"] = round((nearest_supports[1][0] - current_price) / current_price * 100, 3)
        if len(nearest_resistances) >= 1:
            row["resistance_level"] = round(nearest_resistances[0][0], 2)
            row["resistance_distance_pct"] = round((nearest_resistances[0][0] - current_price) / current_price * 100, 3)
        if len(nearest_resistances) >= 2:
            row["resistance_level_2"] = round(nearest_resistances[1][0], 2)
            row["resistance_distance_pct_2"] = round((nearest_resistances[1][0] - current_price) / current_price * 100, 3)

    # --- Demand/Supply Zone — याच टाईमफ्रेमच्या ताज्या candles वरून, थेट (लाईव्ह गणना), mitigation
    # तपासून फक्त अजून ACTIVE असलेल्यांमधूनच सद्य किमतीच्या सर्वात जवळचा एक (Order Block सारखीच पद्धत,
    # प्रत्यक्ष "base" candles च्या high/low वरून -- सरसकट ±0.3% पट्टी नाही) ---
    if df_tf is not None and len(df_tf) >= avg_window + 1:
        zones = detect_demand_supply_zones(df_tf, impulse_mult, avg_window, base_lookback, base_tightness_mult)
        active_dz, active_sz = [], []
        for z in zones:
            after = df_tf[df_tf["timestamp"] > z["formed_date"]]
            if is_zone_mitigated(z["zone_low"], z["zone_high"], after.iloc[1:]):
                continue
            mid = (z["zone_low"] + z["zone_high"]) / 2
            (active_dz if z["zone_type"] == "DEMAND_ZONE" else active_sz).append((mid, z))
        nearest_dz = min(active_dz, key=lambda x: abs(x[0] - current_price)) if active_dz else None
        nearest_sz = min(active_sz, key=lambda x: abs(x[0] - current_price)) if active_sz else None
        if nearest_dz:
            dz = nearest_dz[1]
            row["demand_zone_low"], row["demand_zone_high"] = round(dz["zone_low"], 2), round(dz["zone_high"], 2)
            row["demand_zone_distance_pct"] = round((nearest_dz[0] - current_price) / current_price * 100, 3)
        if nearest_sz:
            sz = nearest_sz[1]
            row["supply_zone_low"], row["supply_zone_high"] = round(sz["zone_low"], 2), round(sz["zone_high"], 2)
            row["supply_zone_distance_pct"] = round((nearest_sz[0] - current_price) / current_price * 100, 3)

    # --- Order Block — याच टाईमफ्रेमच्या ताज्या candles वरून, थेट (लाईव्ह गणना), mitigation तपासून
    # फक्त अजून ACTIVE असलेल्यांमधूनच सद्य किमतीच्या सर्वात जवळचा एक ---
    if df_tf is not None and len(df_tf) >= avg_window + 1:
        obs = detect_order_blocks(df_tf, impulse_mult=impulse_mult, avg_window=avg_window)
        active_obs = []
        for ob in obs:
            after = df_tf[df_tf["timestamp"] > ob["formed_date"]]
            if not is_zone_mitigated(ob["zone_low"], ob["zone_high"], after.iloc[1:]):
                ob_mid = (ob["zone_low"] + ob["zone_high"]) / 2
                active_obs.append((ob_mid, ob))
        nearest_ob = min(active_obs, key=lambda x: abs(x[0] - current_price)) if active_obs else None
        if nearest_ob:
            ob = nearest_ob[1]
            row["order_block_type"] = ob["zone_type"]
            row["order_block_low"], row["order_block_high"] = round(ob["zone_low"], 2), round(ob["zone_high"], 2)
            row["order_block_distance_pct"] = round((nearest_ob[0] - current_price) / current_price * 100, 3)

    return row


def compute_5m_15m_confluence_table(current_price, timeframe_dfs,
                                      swing_order=3, impulse_mult=1.5, avg_window=20):
    """timeframe_dfs: {"5M": df_5m, "15M": df_15m} (क्रमाने) -> compute_5m_15m_confluence_row() च्या
    रांगांचा DataFrame, एक रांग प्रति टाईमफ्रेम."""
    rows = [
        compute_5m_15m_confluence_row(
            label, df, current_price,
            swing_order=swing_order, impulse_mult=impulse_mult, avg_window=avg_window,
        )
        for label, df in timeframe_dfs.items()
    ]
    return pd.DataFrame(rows)
