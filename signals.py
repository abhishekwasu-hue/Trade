"""Price-action signal engine: RSI/Supertrend, Market Structure, Break/Pullback/Retest, S/R, Trendlines."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

def calculate_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def calculate_supertrend(df, period=10, multiplier=3):
    """
    ATR-आधारित Supertrend. रिटर्न: (supertrend_series, direction_series)
    direction: 1 = अपट्रेंड (bullish), -1 = डाऊनट्रेंड (bearish)
    """
    if df.empty or len(df) < period + 1:
        return pd.Series(dtype=float), pd.Series(dtype=int)

    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    final_upper = upper_band.copy()
    final_lower = lower_band.copy()
    direction = pd.Series(1, index=df.index)
    supertrend = pd.Series(0.0, index=df.index)

    for i in range(1, len(df)):
        if close.iloc[i - 1] <= final_upper.iloc[i - 1]:
            final_upper.iloc[i] = min(upper_band.iloc[i], final_upper.iloc[i - 1])
        else:
            final_upper.iloc[i] = upper_band.iloc[i]

        if close.iloc[i - 1] >= final_lower.iloc[i - 1]:
            final_lower.iloc[i] = max(lower_band.iloc[i], final_lower.iloc[i - 1])
        else:
            final_lower.iloc[i] = lower_band.iloc[i]

        if close.iloc[i] > final_upper.iloc[i]:
            direction.iloc[i] = 1
        elif close.iloc[i] < final_lower.iloc[i]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        supertrend.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]

    return supertrend, direction

def resample_to_1h(df_30m):
    """30-मिनिटांच्या candles वरून 1H (1 तासाचे) OHLC candles तयार करणे (Supertrend Engine साठी)."""
    if df_30m.empty:
        return df_30m
    d = df_30m.set_index("timestamp")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "oi": "last"}
    d_1h = d.resample("1h", label="left", closed="left").agg(agg).dropna(subset=["open"]).reset_index()
    return d_1h

def find_swings(df, order=3):
    """साधी fractal swing high/low शोध पद्धत."""
    if df.empty or len(df) < order * 2 + 1:
        return [], []
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    swing_high_idx, swing_low_idx = [], []
    for i in range(order, n - order):
        window_h = highs[i - order:i + order + 1]
        window_l = lows[i - order:i + order + 1]
        if highs[i] == window_h.max():
            swing_high_idx.append(i)
        if lows[i] == window_l.min():
            swing_low_idx.append(i)
    return swing_high_idx, swing_low_idx

def find_support_resistance_levels(df, order=3, cluster_tolerance_pct=0.3, top_n=3):
    """
    सर्व swing highs/lows एकत्र करून, जवळपासचे एकत्र (cluster) करून, touch-count नुसार सगळ्यात
    मजबूत Support (किंमतीखालचे) व Resistance (किंमतीवरचे) levels काढणे — फक्त शेवटचा swing नाही तर
    संपूर्ण इतिहासातील सगळ्यात जास्त वेळा टेस्ट झालेले levels.
    """
    if df.empty:
        return {"support": [], "resistance": [], "current_price": None}
    sh_idx, sl_idx = find_swings(df, order)
    current_price = df["close"].iloc[-1]

    def cluster_points(prices):
        if not prices:
            return []
        prices_sorted = sorted(prices)
        clusters = [[prices_sorted[0]]]
        for p in prices_sorted[1:]:
            if abs(p - clusters[-1][-1]) / clusters[-1][-1] * 100 <= cluster_tolerance_pct:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        return [{"level": round(sum(c) / len(c), 2), "touches": len(c)} for c in clusters]

    high_prices = [df["high"].iloc[i] for i in sh_idx]
    low_prices = [df["low"].iloc[i] for i in sl_idx]

    resistance_clusters = sorted(
        [c for c in cluster_points(high_prices) if c["level"] > current_price],
        key=lambda c: (-c["touches"], c["level"] - current_price),
    )[:top_n]
    support_clusters = sorted(
        [c for c in cluster_points(low_prices) if c["level"] < current_price],
        key=lambda c: (-c["touches"], current_price - c["level"]),
    )[:top_n]

    return {"support": support_clusters, "resistance": resistance_clusters, "current_price": current_price}

def detect_trendline(df, swing_type="low", lookback_swings=4, order=3):
    """
    'low' -> शेवटच्या N swing lows मधून Ascending Support Trendline (उतार धन असेल तरच वैध).
    'high' -> शेवटच्या N swing highs मधून Descending Resistance Trendline (उतार ऋण असेल तरच वैध).
    सद्य किंमत या trendline च्या 'योग्य' बाजूला आहे (RESPECTED) की तिने ती तोडलीये (BROKEN) तेही सांगतो.
    चार्टवर प्रत्यक्ष रेषा काढता यावी म्हणून सुरुवातीचा (start) व शेवटचा (आताचा) बिंदूही परत केला जातो.
    """
    if df.empty:
        return None
    sh_idx, sl_idx = find_swings(df, order)
    idx_list = sl_idx if swing_type == "low" else sh_idx
    price_col = "low" if swing_type == "low" else "high"

    if len(idx_list) < 3:
        return None

    recent_idx = idx_list[-lookback_swings:]
    xs = np.array(recent_idx, dtype=float)
    ys = np.array([df[price_col].iloc[i] for i in recent_idx], dtype=float)

    slope, intercept = np.polyfit(xs, ys, 1)

    expected_slope_sign = 1 if swing_type == "low" else -1
    if np.sign(slope) != expected_slope_sign:
        return {"valid": False, "reason": "चुकीच्या दिशेचा उतार (trendline साठी अयोग्य)"}

    last_idx = len(df) - 1
    trendline_value_now = slope * last_idx + intercept
    current_close = df["close"].iloc[-1]

    if swing_type == "low":
        status = "RESPECTED" if current_close >= trendline_value_now else "BROKEN"
    else:
        status = "RESPECTED" if current_close <= trendline_value_now else "BROKEN"

    start_idx = int(recent_idx[0])
    start_value = float(slope * start_idx + intercept)

    return {
        "valid": True, "type": "ASCENDING_SUPPORT" if swing_type == "low" else "DESCENDING_RESISTANCE",
        "slope": round(float(slope), 4), "trendline_value_now": round(float(trendline_value_now), 2),
        "current_close": round(float(current_close), 2), "status": status,
        "start_idx": start_idx, "start_value": round(start_value, 2),
        "start_timestamp": df["timestamp"].iloc[start_idx] if "timestamp" in df.columns else None,
        "end_timestamp": df["timestamp"].iloc[last_idx] if "timestamp" in df.columns else None,
    }

def check_trend_signal(direction, trendline_support, trendline_resistance, sr_levels):
    """
    Trendline + Support/Resistance एकत्र करून दिशेला दोन प्रकारचं आउटपुट देणे:
    'gate_ok' (हार्ड गेट — दिशेच्या बाजूची trendline तुटली असेल तर ब्लॉक) आणि
    'caution' (सौम्य इशारा — प्रवेश एका मजबूत विरोधी S/R level च्या अगदी जवळ असेल तर, पण ब्लॉक करत नाही).
    """
    result = {"gate_ok": True, "gate_reason": "पुरेसा डेटा नाही — गेट वगळला", "caution": None}

    if direction == "BULLISH":
        if trendline_support and trendline_support.get("valid") and trendline_support["status"] == "BROKEN":
            result["gate_ok"] = False
            result["gate_reason"] = (
                f"Ascending Support Trendline तुटली आहे (किंमत {trendline_support['current_close']} < "
                f"ट्रेंडलाईन {trendline_support['trendline_value_now']})"
            )
        elif trendline_support and trendline_support.get("valid"):
            result["gate_reason"] = "Ascending Support Trendline अजूनही मान्य आहे (Respected)"

        if sr_levels and sr_levels.get("resistance"):
            nearest_res = sr_levels["resistance"][0]
            dist_pct = (nearest_res["level"] - sr_levels["current_price"]) / sr_levels["current_price"] * 100
            if dist_pct < 0.5:
                result["caution"] = f"सावधान: {nearest_res['touches']} वेळा टेस्ट झालेला Resistance ({nearest_res['level']}) फक्त {dist_pct:.2f}% वर आहे"

    elif direction == "BEARISH":
        if trendline_resistance and trendline_resistance.get("valid") and trendline_resistance["status"] == "BROKEN":
            result["gate_ok"] = False
            result["gate_reason"] = (
                f"Descending Resistance Trendline तुटली आहे (किंमत {trendline_resistance['current_close']} > "
                f"ट्रेंडलाईन {trendline_resistance['trendline_value_now']})"
            )
        elif trendline_resistance and trendline_resistance.get("valid"):
            result["gate_reason"] = "Descending Resistance Trendline अजूनही मान्य आहे (Respected)"

        if sr_levels and sr_levels.get("support"):
            nearest_sup = sr_levels["support"][0]
            dist_pct = (sr_levels["current_price"] - nearest_sup["level"]) / sr_levels["current_price"] * 100
            if dist_pct < 0.5:
                result["caution"] = f"सावधान: {nearest_sup['touches']} वेळा टेस्ट झालेला Support ({nearest_sup['level']}) फक्त {dist_pct:.2f}% खाली आहे"

    return result

def add_price_action_overlays(fig, df, row=None, col=None, order=3, show_swing_markers=True):
    """
    दिलेल्या plotly figure वर Support/Resistance levels, Trendlines व Swing High/Low markers जोडणे —
    मुख्य डॅशबोर्ड चार्ट (subplot, row/col सह) आणि PDF रिपोर्ट चार्ट (साधा figure, row/col शिवाय) दोन्हीसाठी
    वापरलेलं एकच फंक्शन, जेणेकरून लॉजिक दोनदा लिहावं लागणार नाही व दोन्हीकडे सुसंगत राहील.
    रिटर्न: (sr_levels, trendline_support, trendline_resistance) — वर्णन (description) मजकूर तयार करण्यासाठी.
    """
    if df is None or df.empty or len(df) < 10:
        return None, None, None

    sr_levels = find_support_resistance_levels(df, order=order)
    trendline_support = detect_trendline(df, swing_type="low", order=order)
    trendline_resistance = detect_trendline(df, swing_type="high", order=order)

    for s in sr_levels.get("support", []):
        fig.add_hline(
            y=s["level"], line_dash="dot", line_color="#089981", opacity=0.6, line_width=1,
            annotation_text=f"S {s['level']:.0f} ({s['touches']}x)", annotation_position="bottom left",
            annotation_font_size=9, annotation_font_color="#089981",
            row=row, col=col,
        )
    for r in sr_levels.get("resistance", []):
        fig.add_hline(
            y=r["level"], line_dash="dot", line_color="#F23645", opacity=0.6, line_width=1,
            annotation_text=f"R {r['level']:.0f} ({r['touches']}x)", annotation_position="top left",
            annotation_font_size=9, annotation_font_color="#F23645",
            row=row, col=col,
        )

    for tl in (trendline_support, trendline_resistance):
        if tl and tl.get("valid") and tl.get("start_timestamp") is not None:
            line_color = "#089981" if tl["status"] == "RESPECTED" else "#F23645"
            fig.add_shape(
                type="line",
                x0=tl["start_timestamp"], y0=tl["start_value"],
                x1=tl["end_timestamp"], y1=tl["trendline_value_now"],
                line=dict(color=line_color, width=1.6, dash="solid"),
                row=row, col=col,
            )

    if show_swing_markers:
        sh_idx, sl_idx = find_swings(df, order=order)
        if sh_idx:
            fig.add_trace(go.Scatter(
                x=[df["timestamp"].iloc[i] for i in sh_idx],
                y=[df["high"].iloc[i] for i in sh_idx],
                mode="markers", marker=dict(symbol="triangle-down", size=7, color="#F23645"),
                name="Swing High", showlegend=False,
            ), row=row, col=col)
        if sl_idx:
            fig.add_trace(go.Scatter(
                x=[df["timestamp"].iloc[i] for i in sl_idx],
                y=[df["low"].iloc[i] for i in sl_idx],
                mode="markers", marker=dict(symbol="triangle-up", size=7, color="#089981"),
                name="Swing Low", showlegend=False,
            ), row=row, col=col)

    return sr_levels, trendline_support, trendline_resistance

def describe_price_action(sr_levels, trendline_support, trendline_resistance, lang="mr"):
    """
    चार्टवर जे दाखवलंय त्याचं शब्दांत वर्णन तयार करणे — डॅशबोर्ड एक्सपांडर (lang='mr', ब्राउझर मराठी दाखवतो)
    व PDF कॅप्शन (lang='en', कारण PDF मध्ये वापरलेल्या फॉन्ट्समध्ये देवनागरी ग्लिफ्स नाहीत) या दोन्हीसाठी.
    """
    parts = []
    if lang == "en":
        if trendline_support and trendline_support.get("valid"):
            tag = "holding" if trendline_support["status"] == "RESPECTED" else "broken"
            parts.append(f"Ascending support trendline {tag} (price {trendline_support['current_close']} vs trendline {trendline_support['trendline_value_now']})")
        if trendline_resistance and trendline_resistance.get("valid"):
            tag = "holding" if trendline_resistance["status"] == "RESPECTED" else "broken"
            parts.append(f"Descending resistance trendline {tag} (price {trendline_resistance['current_close']} vs trendline {trendline_resistance['trendline_value_now']})")
        if sr_levels:
            if sr_levels.get("support"):
                parts.append("Nearest support: " + ", ".join(f"{s['level']:.0f} ({s['touches']}x tested)" for s in sr_levels["support"]))
            if sr_levels.get("resistance"):
                parts.append("Nearest resistance: " + ", ".join(f"{r['level']:.0f} ({r['touches']}x tested)" for r in sr_levels["resistance"]))
        return " | ".join(parts) if parts else "Not enough data yet (needs at least 3 swing points)."

    if trendline_support and trendline_support.get("valid"):
        tag = "✅ कायम आहे" if trendline_support["status"] == "RESPECTED" else "❌ तुटली आहे"
        parts.append(f"Ascending Support Trendline {tag} (सद्य किंमत {trendline_support['current_close']} वि. ट्रेंडलाईन {trendline_support['trendline_value_now']})")
    if trendline_resistance and trendline_resistance.get("valid"):
        tag = "✅ कायम आहे" if trendline_resistance["status"] == "RESPECTED" else "❌ तुटली आहे"
        parts.append(f"Descending Resistance Trendline {tag} (सद्य किंमत {trendline_resistance['current_close']} वि. ट्रेंडलाईन {trendline_resistance['trendline_value_now']})")
    if sr_levels:
        if sr_levels.get("support"):
            parts.append("जवळचा Support: " + ", ".join(f"{s['level']:.0f} ({s['touches']} वेळा टेस्ट)" for s in sr_levels["support"]))
        if sr_levels.get("resistance"):
            parts.append("जवळचा Resistance: " + ", ".join(f"{r['level']:.0f} ({r['touches']} वेळा टेस्ट)" for r in sr_levels["resistance"]))
    return " · ".join(parts) if parts else "पुरेसा डेटा नाही (किमान 3 swing points लागतात)."

def classify_market_structure(df, order=3, lookback_swings=4):
    """HH/HL (अपट्रेंड स्ट्रक्चर) किंवा LH/LL (डाऊनट्रेंड स्ट्रक्चर) ओळखणे."""
    sh_idx, sl_idx = find_swings(df, order)
    if len(sh_idx) < 2 or len(sl_idx) < 2:
        return {"structure": "INSUFFICIENT_DATA", "last_swing_high": None, "last_swing_low": None}

    last_highs = [df["high"].iloc[i] for i in sh_idx[-lookback_swings:]]
    last_lows = [df["low"].iloc[i] for i in sl_idx[-lookback_swings:]]
    hh = all(last_highs[i] > last_highs[i - 1] for i in range(1, len(last_highs)))
    hl = all(last_lows[i] > last_lows[i - 1] for i in range(1, len(last_lows)))
    lh = all(last_highs[i] < last_highs[i - 1] for i in range(1, len(last_highs)))
    ll = all(last_lows[i] < last_lows[i - 1] for i in range(1, len(last_lows)))

    if hh and hl:
        structure = "HH/HL (Uptrend)"
    elif lh and ll:
        structure = "LH/LL (Downtrend)"
    else:
        structure = "MIXED/RANGING"

    return {"structure": structure, "last_swing_high": last_highs[-1], "last_swing_low": last_lows[-1]}


def detect_choch(df, order=3, lookback_swings=3):
    """
    CHoCH (Change of Character) — प्रचलित संरचनेच्या (trend) विरुद्ध दिशेने होणारा पहिला ब्रेक, जो संभाव्य
    ट्रेंड-उलटफेराचं संकेत देतो. उदा. HH/HL (तेजी) चालू असताना किंमत शेवटच्या Higher Low च्या खाली गेली,
    तर ते बेअरिश CHoCH (तेजीच्या विरुद्ध पहिला ब्रेक).
    रिटर्न: "BULLISH_CHOCH" / "BEARISH_CHOCH" / None
    """
    sh_idx, sl_idx = find_swings(df, order)
    if len(sh_idx) < lookback_swings or len(sl_idx) < lookback_swings:
        return None

    recent_highs = [df["high"].iloc[i] for i in sh_idx[-lookback_swings:]]
    recent_lows = [df["low"].iloc[i] for i in sl_idx[-lookback_swings:]]

    was_uptrend = all(recent_highs[i] > recent_highs[i - 1] for i in range(1, len(recent_highs))) and \
        all(recent_lows[i] > recent_lows[i - 1] for i in range(1, len(recent_lows)))
    was_downtrend = all(recent_highs[i] < recent_highs[i - 1] for i in range(1, len(recent_highs))) and \
        all(recent_lows[i] < recent_lows[i - 1] for i in range(1, len(recent_lows)))

    last_close = df["close"].iloc[-1]
    last_swing_low = recent_lows[-1]
    last_swing_high = recent_highs[-1]

    if was_uptrend and last_close < last_swing_low:
        return "BEARISH_CHOCH"
    if was_downtrend and last_close > last_swing_high:
        return "BULLISH_CHOCH"
    return None


def find_order_block(df, direction, impulse_lookforward=5, impulse_min_move_pct=0.3, search_lookback=20):
    """
    दिलेल्या दिशेसाठी अलीकडचा Order Block शोधणे — मोठ्या व वेगाने होणाऱ्या (impulsive) हालचालीच्या आधीची
    शेवटची उलट-रंगाची candle (प्रमाणभूत ICT/Smart Money व्याख्या).
    BULLISH: शेवटची लाल (bearish) candle, त्यानंतर impulse_lookforward बार्समध्ये किमान impulse_min_move_pct% वर हलचाल.
    BEARISH: शेवटची हिरवी (bullish) candle, त्यानंतर तितक्याच बार्समध्ये किमान इतकी % खाली हलचाल.
    No lookahead सुरक्षित — फक्त दिलेल्या df च्या आतल्याच (walk-forward च्या त्या क्षणापर्यंतच्याच) डेटावरून
    impulse ची पुष्टी होते, भविष्यातील माहिती वापरली जात नाही.
    """
    n = len(df)
    if n < impulse_lookforward + 2:
        return None
    search_start = max(0, n - search_lookback - impulse_lookforward)
    search_end = n - impulse_lookforward - 1
    for i in range(search_end, search_start - 1, -1):
        candle = df.iloc[i]
        is_bearish_candle = candle["close"] < candle["open"]
        is_bullish_candle = candle["close"] > candle["open"]
        if direction == "BULLISH" and is_bearish_candle:
            future_high = df["high"].iloc[i + 1:i + 1 + impulse_lookforward].max()
            move_pct = (future_high - candle["close"]) / candle["close"] * 100
            if move_pct >= impulse_min_move_pct:
                return {"ob_high": float(candle["high"]), "ob_low": float(candle["low"]), "ob_index": i}
        elif direction == "BEARISH" and is_bullish_candle:
            future_low = df["low"].iloc[i + 1:i + 1 + impulse_lookforward].min()
            move_pct = (candle["close"] - future_low) / candle["close"] * 100
            if move_pct >= impulse_min_move_pct:
                return {"ob_high": float(candle["high"]), "ob_low": float(candle["low"]), "ob_index": i}
    return None


def is_retesting_order_block(df, ob, direction, tolerance_pct=0.1):
    """सद्य किंमत Order Block च्या झोनला (परत) स्पर्श करतेय का ते तपासणे (retest)."""
    if ob is None:
        return False
    last_low, last_high = df["low"].iloc[-1], df["high"].iloc[-1]
    tol = (ob["ob_high"] - ob["ob_low"]) * (tolerance_pct / 100) if ob["ob_high"] != ob["ob_low"] else 0.01
    if direction == "BULLISH":
        return last_low <= ob["ob_high"] + tol
    return last_high >= ob["ob_low"] - tol


def check_price_action_strategy(df, direction, order=3, lookback_swings=3,
                                  ob_impulse_lookforward=5, ob_impulse_min_move_pct=0.3,
                                  ob_search_lookback=20, ob_retest_tolerance_pct=0.1,
                                  require_unmitigated_ob=True, require_fvg_confluence=True,
                                  require_displacement=True, sweep_lookback=20,
                                  displacement_atr_multiplier=1.5,
                                  enable_kill_zone_filter=False, avoid_first_minutes=15, avoid_last_minutes=15):
    """
    Toggle 1: Price Action रणनीती — Professional/ICT-दर्जाची आवृत्ती (दिशा 1H Supertrend वरून बाहेरून
    दिली जाते). मूळ (BOS/CHoCH + Order Block + Retest + Pattern) सोबतच आता ५ व्यावसायिक सुधारणा:

    1. Liquidity Sweep — साध्या close-आधारित ब्रेकसोबतच, wick-sweep+reversal हाही वैध structural-shift
       मानला जातो (bos किंवा choch किंवा sweep — कोणतंही एक खरं असेल तरी पुरेसं).
    2. Unmitigated Order Block — OB आधीच एकदा टेस्ट झालेला (कमकुवत) नसावा (require_unmitigated_ob).
    3. Displacement Candle — impulse मध्ये किमान एक मोठ्या-body ची, ATR-सापेक्ष ठाम candle हवी, नुसती
       एकत्रित % हालचाल नाही (require_displacement).
    4. Fair Value Gap (FVG) Confluence — OB च्या impulse-हालचालीजवळच एक न भरलेला FVG हवा (require_fvg_confluence).
    5. Kill-Zone Filter (ऐच्छिक, डीफॉल्ट बंद) — दिवसाच्या सुरुवातीचे/शेवटचे काही मिनिट टाळता येतात.

    हे सर्व डीफॉल्ट चालू आहेत (व्यावसायिक-दर्जा हाच डीफॉल्ट) — प्रत्येक require_* पॅरामीटर False करून
    जुन्या (सैल) वर्तनाकडे मागे जाता येतं.
    """
    detail = {
        "bos": False, "choch": None, "liquidity_sweep": None, "order_block": None,
        "unmitigated": None, "displacement": None, "fvg": None, "ob_retest": False, "pattern": None,
        "kill_zone_blocked": False,
    }

    if enable_kill_zone_filter and not df.empty:
        last_ts = df["timestamp"].iloc[-1]
        if is_in_kill_zone(last_ts, avoid_first_minutes=avoid_first_minutes, avoid_last_minutes=avoid_last_minutes):
            detail["kill_zone_blocked"] = True
            return False, detail

    ob = find_order_block(df, direction, impulse_lookforward=ob_impulse_lookforward,
                           impulse_min_move_pct=ob_impulse_min_move_pct, search_lookback=ob_search_lookback)
    detail["order_block"] = ob
    if ob is None:
        return False, detail

    if require_unmitigated_ob:
        unmitigated = is_order_block_unmitigated(df, ob, direction)
        detail["unmitigated"] = unmitigated
        if not unmitigated:
            return False, detail

    prior_df = df.iloc[:ob["ob_index"] + 1]
    prior_structure = classify_market_structure(prior_df, order=order, lookback_swings=lookback_swings)
    if prior_structure["structure"] == "INSUFFICIENT_DATA":
        return False, detail

    swing_level = prior_structure["last_swing_high"] if direction == "BULLISH" else prior_structure["last_swing_low"]
    post_ob_closes = df["close"].iloc[ob["ob_index"] + 1:]
    bos = bool((post_ob_closes > swing_level).any()) if direction == "BULLISH" else bool((post_ob_closes < swing_level).any())
    detail["bos"] = bos

    choch = detect_choch(prior_df, order=order, lookback_swings=lookback_swings)
    detail["choch"] = choch
    choch_matches = (choch == "BULLISH_CHOCH" and direction == "BULLISH") or (choch == "BEARISH_CHOCH" and direction == "BEARISH")

    sweep = detect_liquidity_sweep(prior_df, direction, order=order, sweep_lookback=sweep_lookback)
    detail["liquidity_sweep"] = sweep

    structural_shift = bos or choch_matches or (sweep is not None)
    if not structural_shift:
        return False, detail

    if require_displacement:
        impulse_end = min(ob["ob_index"] + 1 + ob_impulse_lookforward, len(df))
        displacement_found = any(
            is_displacement_candle(df, idx, direction, body_atr_multiplier=displacement_atr_multiplier)
            for idx in range(ob["ob_index"] + 1, impulse_end)
        )
        detail["displacement"] = displacement_found
        if not displacement_found:
            return False, detail

    if require_fvg_confluence:
        fvg_end = min(ob["ob_index"] + ob_impulse_lookforward + 1, len(df))
        fvg = find_fair_value_gaps(df.iloc[:fvg_end], direction, lookback=ob_impulse_lookforward + 2)
        detail["fvg"] = fvg
        if fvg is None:
            return False, detail

    ob_retest = is_retesting_order_block(df, ob, direction, tolerance_pct=ob_retest_tolerance_pct)
    detail["ob_retest"] = ob_retest
    if not ob_retest:
        return False, detail

    pattern = detect_candlestick_pattern(df)
    detail["pattern"] = pattern
    pattern_ok = (pattern in ("HAMMER", "BULLISH_ENGULFING", "MORNING_STAR")) if direction == "BULLISH" else (pattern in ("SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR"))

    return bool(structural_shift and ob_retest and pattern_ok), detail


def detect_liquidity_sweep(df, direction, order=3, sweep_lookback=20, max_swings_checked=5):
    """
    Liquidity Sweep — किंमत अलीकडच्या swing high/low च्या पलीकडे wick ने गेली (stops sweep केले),
    पण लगेच close त्या पातळीच्या आतच परत आला — साधा break नाही, उच्च-गुणवत्तेचा "fake-out" reversal संकेत
    (professional/ICT पद्धतीत साध्या BOS पेक्षा जास्त विश्वासार्ह मानला जातो).
    """
    sh_idx, sl_idx = find_swings(df, order=order)
    n = len(df)
    if direction == "BEARISH":
        candidates = [i for i in sh_idx if i < n - 1][-max_swings_checked:]
        for sh_i in reversed(candidates):
            level = df["high"].iloc[sh_i]
            for j in range(sh_i + 1, min(sh_i + sweep_lookback, n)):
                if df["high"].iloc[j] > level and df["close"].iloc[j] < level:
                    return {"swept_level": float(level), "sweep_index": j, "swing_index": sh_i}
        return None
    else:
        candidates = [i for i in sl_idx if i < n - 1][-max_swings_checked:]
        for sl_i in reversed(candidates):
            level = df["low"].iloc[sl_i]
            for j in range(sl_i + 1, min(sl_i + sweep_lookback, n)):
                if df["low"].iloc[j] < level and df["close"].iloc[j] > level:
                    return {"swept_level": float(level), "sweep_index": j, "swing_index": sl_i}
        return None


def find_fair_value_gaps(df, direction, lookback=20):
    """
    Fair Value Gap (FVG/Imbalance) — ३ सलग candles मधली किंमत-पोकळी, जिथे मधल्या candle च्या वेगवान
    हालचालीमुळे पहिल्या व तिसऱ्या candle च्या range मध्ये आच्छादन राहत नाही — Order Block च्या पुष्टीसाठी
    सर्वात मानक confluence. सर्वात अलीकडचा, अजून "भरलेला नाही" (unfilled) असा FVG देतो.
    """
    n = len(df)
    if n < 3:
        return None
    start = max(2, n - lookback)
    fvgs = []
    for i in range(start, n):
        c1 = df.iloc[i - 2]
        c3 = df.iloc[i]
        if direction == "BEARISH":
            if c1["low"] > c3["high"]:
                fvgs.append({"fvg_top": float(c1["low"]), "fvg_bottom": float(c3["high"]), "index": i})
        else:
            if c1["high"] < c3["low"]:
                fvgs.append({"fvg_top": float(c3["low"]), "fvg_bottom": float(c1["high"]), "index": i})
    for fvg in reversed(fvgs):
        filled = False
        for j in range(fvg["index"] + 1, n):
            if direction == "BEARISH":
                if df["low"].iloc[j] <= fvg["fvg_bottom"]:
                    filled = True
                    break
            else:
                if df["high"].iloc[j] >= fvg["fvg_top"]:
                    filled = True
                    break
        if not filled:
            return fvg
    return None


def is_order_block_unmitigated(df, ob, direction, recent_lookback_bars=5):
    """
    Order Block अलीकडच्या recent_lookback_bars बार्समध्ये (शेवटचा bar, म्हणजे सद्य retest attempt, सोडून)
    आधी टच झालेला नाही का ते तपासणे — 'तयार झाल्यापासून कधीच स्पर्श नाही' (पूर्ण इतिहास) ऐवजी 'अलीकडे
    स्पर्श नाही' अशी सैल व्याख्या. कारण: noisy 15M डेटावर 'कधीच नाही' ही अट जवळजवळ अशक्य ठरते (backtest
    ने सिद्ध केलं — त्यामुळे सिग्नल्स जवळपास शून्यावर आले होते), आणि तरीही "आत्ताच वापरलेला/शिळा" OB
    वगळण्याचा मूळ उद्देश यातून साध्य होतो.
    """
    if ob is None:
        return False
    ob_index = ob["ob_index"]
    n = len(df)
    check_start = max(ob_index + 1, n - 1 - recent_lookback_bars)
    for j in range(check_start, n - 1):
        if direction == "BEARISH":
            if df["high"].iloc[j] >= ob["ob_low"]:
                return False
        else:
            if df["low"].iloc[j] <= ob["ob_high"]:
                return False
    return True


def is_displacement_candle(df, index, direction, body_atr_multiplier=1.5, atr_period=14):
    """
    दिलेल्या candle चा body ATR च्या तुलनेत मोठा (व दिशेने योग्य) आहे का — एकाच ठाम, मोठ्या-body च्या
    candle ने खरी संस्थात्मक गती (displacement) दाखवली, अनेक लहान/संथ candles नी नाही.
    """
    if index < atr_period:
        return False
    tr_list = []
    for i in range(index - atr_period, index):
        high, low = df["high"].iloc[i], df["low"].iloc[i]
        prev_close = df["close"].iloc[i - 1] if i > 0 else df["open"].iloc[i]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list)
    if atr <= 0:
        return False
    body = abs(df["close"].iloc[index] - df["open"].iloc[index])
    is_big_body = body >= atr * body_atr_multiplier
    is_directional = (df["close"].iloc[index] > df["open"].iloc[index]) if direction == "BULLISH" else (df["close"].iloc[index] < df["open"].iloc[index])
    return bool(is_big_body and is_directional)


def compute_atr(df, period=14):
    """
    दिलेल्या OHLC डेटाच्या शेवटच्या bar साठी Average True Range (ATR) काढणे — Trailing SL साठी वापरला जातो.
    पुरेसा डेटा (किमान period+1 bars) नसेल तर None परत करतो.
    """
    n = len(df)
    if n < period + 1:
        return None
    tr_list = []
    start = n - period
    for i in range(start, n):
        high, low = df["high"].iloc[i], df["low"].iloc[i]
        prev_close = df["close"].iloc[i - 1] if i > 0 else df["open"].iloc[i]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return sum(tr_list) / len(tr_list)


def is_in_kill_zone(timestamp, avoid_first_minutes=15, avoid_last_minutes=15, market_open="09:15", market_close="15:30"):
    """
    दिलेली वेळ दिवसाच्या पहिल्या/शेवटच्या काही मिनिटांत (जास्त fake move असणाऱ्या, low-quality वेळा) येते
    का ते तपासणे — professional traders सहसा या वेळा टाळतात (ऐच्छिक फिल्टर, डीफॉल्ट बंद).
    """
    import datetime as _dt
    t = timestamp.time() if hasattr(timestamp, "time") else timestamp
    open_t = _dt.datetime.strptime(market_open, "%H:%M").time()
    close_t = _dt.datetime.strptime(market_close, "%H:%M").time()
    anchor = _dt.date.today()
    open_dt = _dt.datetime.combine(anchor, open_t)
    close_dt = _dt.datetime.combine(anchor, close_t)
    t_dt = _dt.datetime.combine(anchor, t)
    avoid_start_end = open_dt + _dt.timedelta(minutes=avoid_first_minutes)
    avoid_end_start = close_dt - _dt.timedelta(minutes=avoid_last_minutes)
    return t_dt < avoid_start_end or t_dt > avoid_end_start


def check_indicator_strategy(df_pattern_tf, rsi_series, direction):
    """
    Toggle 2: Indicator Based रणनीती (दिशा 1H Supertrend वरून बाहेरून दिली जाते) — RSI(15M) 25-55
    (Bullish) / 45-75 (Bearish) च्या दरम्यान, आणि Candlestick Rejection Bar (Hammer/Shooting Star) किंवा
    Engulfing जुळणे — हे दोन्ही एकत्र खरं असेल तरच एंट्री (check_pattern_rsi_gate चाच पुनर्वापर, नवीन ranges सह).
    """
    gate_ok, pattern, rsi_val = check_pattern_rsi_gate(
        df_pattern_tf, rsi_series, direction, bullish_rsi_range=(25, 55), bearish_rsi_range=(45, 75)
    )
    return gate_ok, {"pattern": pattern, "rsi": rsi_val}

def analyze_chart_zones(df, order=3):
    """
    कोणत्याही एका टाईमफ्रेमसाठी स्ट्रक्चर + BOS/CHoCH + Demand/Supply झोन काढणे (चार्ट अ‍ॅनोटेशनसाठी).
    BOS (Break of Structure) = प्रचलित ट्रेंडच्याच दिशेने ब्रेक (ट्रेंड सुरू राहण्याचा इशारा).
    CHoCH (Change of Character) = प्रचलित ट्रेंडच्या उलट दिशेने ब्रेक (संभाव्य रिव्हर्सलचा इशारा).
    """
    structure = classify_market_structure(df, order=order)
    result = {"structure": structure, "bos_choch": None, "demand_zone": None, "supply_zone": None}
    if df.empty or structure["structure"] == "INSUFFICIENT_DATA":
        return result

    last_close = df["close"].iloc[-1]
    last_high = structure.get("last_swing_high")
    last_low = structure.get("last_swing_low")
    prevailing = structure["structure"]

    if last_high is not None and last_close > last_high:
        if "HH/HL" in prevailing:
            result["bos_choch"] = {"type": "BOS", "direction": "bullish", "level": last_high}
        elif "LH/LL" in prevailing:
            result["bos_choch"] = {"type": "CHoCH", "direction": "bullish", "level": last_high}
        else:
            result["bos_choch"] = {"type": "Range Break", "direction": "bullish", "level": last_high}
    elif last_low is not None and last_close < last_low:
        if "LH/LL" in prevailing:
            result["bos_choch"] = {"type": "BOS", "direction": "bearish", "level": last_low}
        elif "HH/HL" in prevailing:
            result["bos_choch"] = {"type": "CHoCH", "direction": "bearish", "level": last_low}
        else:
            result["bos_choch"] = {"type": "Range Break", "direction": "bearish", "level": last_low}

    if last_low is not None:
        result["demand_zone"] = (round(last_low * 0.997, 2), round(last_low * 1.003, 2))
    if last_high is not None:
        result["supply_zone"] = (round(last_high * 0.997, 2), round(last_high * 1.003, 2))
    return result

def detect_break(df, structure_info, direction):
    """दिशेच्या बाजूने स्ट्रक्चर ब्रेक झाली का ते तपासणे."""
    if df.empty or structure_info["structure"] == "INSUFFICIENT_DATA":
        return False, None
    last_close = df["close"].iloc[-1]
    if direction == "BULLISH" and structure_info.get("last_swing_high"):
        level = structure_info["last_swing_high"]
        return last_close > level, level
    elif direction == "BEARISH" and structure_info.get("last_swing_low"):
        level = structure_info["last_swing_low"]
        return last_close < level, level
    return False, None

def detect_any_break(df, structure_info):
    """कोणत्याही दिशेने (वर किंवा खाली) स्ट्रक्चर ब्रेक झाली आहे का — Sideways पुष्टीकरणासाठी दोन्ही बाजू तपासणे."""
    if df.empty or structure_info["structure"] == "INSUFFICIENT_DATA":
        return False, False
    last_close = df["close"].iloc[-1]
    broke_up = structure_info.get("last_swing_high") is not None and last_close > structure_info["last_swing_high"]
    broke_down = structure_info.get("last_swing_low") is not None and last_close < structure_info["last_swing_low"]
    return broke_up, broke_down

def compute_range_compression(df, lookback=20):
    """शेवटच्या N कँडल्समधील (उच्च−नीच) रेंज स्पॉट किंमतीच्या % मध्ये — Sideways किती 'घट्ट' आहे हे मोजण्यासाठी."""
    if df.empty or len(df) < 3:
        return None
    recent = df.tail(lookback)
    spot = recent["close"].iloc[-1]
    if spot <= 0:
        return None
    range_pct = (recent["high"].max() - recent["low"].min()) / spot * 100
    return round(range_pct, 3)

def classify_sideways(df_15m, structure_15m, rsi_check, india_vix, vix_max_threshold,
                       tight_range_pct=0.6, max_range_pct=1.5, rsi_low=40, rsi_high=60):
    """
    मार्केट खरोखरच Sideways (range-bound) आहे का हे ५ अटींनी तपासणे, आणि तसे असल्यास
    Iron Butterfly (खूप घट्ट रेंज) की Iron Condor (सैलसर रेंज) योग्य ते ठरवणे.
    """
    broke_up, broke_down = detect_any_break(df_15m, structure_15m)
    range_pct = compute_range_compression(df_15m)
    rsi_val = rsi_check.get("rsi")

    structure_ok = structure_15m["structure"] == "MIXED/RANGING"
    rsi_ok = (rsi_val is not None) and (rsi_low <= rsi_val <= rsi_high)
    no_break = (not broke_up) and (not broke_down)
    range_ok = (range_pct is not None) and (range_pct <= max_range_pct)
    vix_ok = (india_vix is not None) and (india_vix <= vix_max_threshold)

    is_sideways = structure_ok and rsi_ok and no_break and range_ok and vix_ok

    if not is_sideways:
        strategy_type = None
    elif range_pct is not None and range_pct <= tight_range_pct:
        strategy_type = "IRON_BUTTERFLY"
    else:
        strategy_type = "IRON_CONDOR"

    return {
        "is_sideways": is_sideways, "strategy_type": strategy_type, "range_pct": range_pct,
        "structure_ok": structure_ok, "rsi_ok": rsi_ok, "no_break": no_break,
        "range_ok": range_ok, "vix_ok": vix_ok,
    }

def detect_pullback_retest(df, broken_level, direction, tolerance_pct=0.3, lookback=10):
    """ब्रेकनंतर पुलबॅक व त्या लेव्हलचा रीटेस्ट झाला का ते तपासणे."""
    if broken_level is None or df.empty:
        return False, False
    recent = df.tail(lookback)
    tol = broken_level * (tolerance_pct / 100)
    if direction == "BULLISH":
        pulled_back = recent["low"].min() <= broken_level + tol
    else:
        pulled_back = recent["high"].max() >= broken_level - tol
    retested = abs(df["close"].iloc[-1] - broken_level) <= tol * 2
    return bool(pulled_back), bool(retested)

def rsi_momentum_and_divergence(df, rsi_series, direction):
    """RSI मोमेंटम दिशेशी जुळते का, आणि साधी (simplified) डायव्हर्जन्स तपासणे."""
    if rsi_series is None or len(rsi_series) < 5 or df.empty:
        return {"momentum_ok": False, "divergence": "NONE", "rsi": None}
    last_rsi = float(rsi_series.iloc[-1])
    momentum_ok = (last_rsi > 50) if direction == "BULLISH" else (last_rsi < 50)

    recent_price = df["close"].tail(20)
    recent_rsi = rsi_series.tail(20)
    divergence = "NONE"
    if len(recent_price) >= 2:
        price_trend = recent_price.iloc[-1] - recent_price.iloc[0]
        rsi_trend = recent_rsi.iloc[-1] - recent_rsi.iloc[0]
        if direction == "BULLISH" and price_trend < 0 and rsi_trend > 0:
            divergence = "BULLISH_DIVERGENCE"
        elif direction == "BEARISH" and price_trend > 0 and rsi_trend < 0:
            divergence = "BEARISH_DIVERGENCE"

    return {"momentum_ok": momentum_ok, "divergence": divergence, "rsi": last_rsi}

def detect_candlestick_pattern(df):
    """
    शेवटच्या (व त्याआधीच्या, Engulfing/Star साठी) candles वरून pattern ओळखणे.
    रिटर्न: "BULLISH_ENGULFING" / "MORNING_STAR" / "HAMMER" / "SHOOTING_STAR" / "EVENING_STAR" / "BEARISH_ENGULFING" / None
    """
    if len(df) < 2:
        return None
    curr = df.iloc[-1]
    prev = df.iloc[-2]

    c_open, c_close, c_high, c_low = curr["open"], curr["close"], curr["high"], curr["low"]
    p_open, p_close = prev["open"], prev["close"]

    body = abs(c_close - c_open)
    total_range = c_high - c_low
    upper_wick = c_high - max(c_open, c_close)
    lower_wick = min(c_open, c_close) - c_low

    prev_bearish = p_close < p_open
    prev_bullish = p_close > p_open
    curr_bullish = c_close > c_open
    curr_bearish = c_close < c_open

    # --- Engulfing patterns (मागच्या candle चा संपूर्ण body गिळणारी सध्याची candle) ---
    if prev_bearish and curr_bullish and c_open <= p_close and c_close >= p_open:
        return "BULLISH_ENGULFING"
    if prev_bullish and curr_bearish and c_open >= p_close and c_close <= p_open:
        return "BEARISH_ENGULFING"

    # --- Morning Star / Evening Star (३ candles चा उलटफेर पॅटर्न — Engulfing नंतर, एकाच-candle
    # पॅटर्न्सच्या आधी तपासला जातो, कारण ३-candle पॅटर्न साधारणपणे जास्त भक्कम संकेत मानला जातो) ---
    star_pattern = detect_morning_evening_star(df)
    if star_pattern:
        return star_pattern

    # --- Hammer / Shooting Star (एकाच candle वरून — लांब wick, छोटा body) ---
    if total_range <= 0 or body <= 0:
        return None
    if lower_wick >= 2 * body and upper_wick <= 0.5 * body:
        return "HAMMER"
    if upper_wick >= 2 * body and lower_wick <= 0.5 * body:
        return "SHOOTING_STAR"
    return None


def detect_morning_evening_star(df):
    """
    Morning Star (bullish reversal) / Evening Star (bearish reversal) — ३ candles चा पॅटर्न:
    1) पहिली candle: ठाम शरीराची (मोठा body), प्रचलित दिशेतली
    2) दुसरी candle: लहान शरीराची (indecision/तारा) — पहिलीच्या तुलनेत खूप लहान body
    3) तिसरी candle: उलट दिशेतली ठाम candle, जी पहिलीच्या body च्या मध्यापलीकडे बंद होते
    रिटर्न: "MORNING_STAR" / "EVENING_STAR" / None
    """
    if len(df) < 3:
        return None
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    def _body(c):
        return abs(c["close"] - c["open"])

    def _rng(c):
        return c["high"] - c["low"]

    body1, body2, body3 = _body(c1), _body(c2), _body(c3)
    range1, range3 = _rng(c1), _rng(c3)
    if range1 <= 0 or range3 <= 0:
        return None

    c1_bearish = c1["close"] < c1["open"]
    c1_bullish = c1["close"] > c1["open"]
    c3_bullish = c3["close"] > c3["open"]
    c3_bearish = c3["close"] < c3["open"]

    c1_strong_body = body1 >= 0.5 * range1
    c3_strong_body = body3 >= 0.5 * range3
    c2_small_body = body1 > 0 and body2 <= 0.3 * body1

    c1_mid = (c1["open"] + c1["close"]) / 2

    if c1_bearish and c1_strong_body and c2_small_body and c3_bullish and c3_strong_body and c3["close"] > c1_mid:
        return "MORNING_STAR"
    if c1_bullish and c1_strong_body and c2_small_body and c3_bearish and c3_strong_body and c3["close"] < c1_mid:
        return "EVENING_STAR"
    return None


def check_pattern_rsi_gate(df_pattern_tf, rsi_series, direction, bullish_rsi_range=(30, 50), bearish_rsi_range=(55, 75)):
    """
    Candlestick Pattern + RSI Range एकत्र तपासणारा गेट.
    BULLISH: शेवटची candle Hammer/Bullish Engulfing हवी, आणि RSI दिलेल्या bullish_rsi_range च्या दरम्यान.
    BEARISH: शेवटची candle Shooting Star/Bearish Engulfing हवी, आणि RSI दिलेल्या bearish_rsi_range च्या दरम्यान.
    RSI ranges पॅरामीटर म्हणून दिलेले आहेत (डीफॉल्ट जुनेच 30-50/55-75) — वेगवेगळ्या रणनीतींसाठी
    वेगवेगळ्या ranges वापरता याव्यात म्हणून (उदा. नवीन Indicator-Based रणनीती 25-55/45-75 वापरते).
    """
    if df_pattern_tf is None or df_pattern_tf.empty or rsi_series is None or len(rsi_series) == 0:
        return False, None, None

    pattern = detect_candlestick_pattern(df_pattern_tf)
    last_rsi = float(rsi_series.iloc[-1])

    if direction == "BULLISH":
        pattern_ok = pattern in ("HAMMER", "BULLISH_ENGULFING", "MORNING_STAR")
        rsi_ok = bullish_rsi_range[0] < last_rsi < bullish_rsi_range[1]
    elif direction == "BEARISH":
        pattern_ok = pattern in ("SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR")
        rsi_ok = bearish_rsi_range[0] < last_rsi < bearish_rsi_range[1]
    else:
        return False, pattern, last_rsi

    return bool(pattern_ok and rsi_ok), pattern, last_rsi


def confirm_5m(df_5m, direction):
    """5-मिनिट कँडल दिशेच्या बाजूने बंद झाली का (अंतिम पुष्टीकरण)."""
    if df_5m.empty:
        return False
    last = df_5m.iloc[-1]
    return (last["close"] > last["open"]) if direction == "BULLISH" else (last["close"] < last["open"])

def supply_demand_zone(structure_info, direction):
    """साधा सप्लाय/डिमांड झोन (शेवटच्या स्विंग लेव्हलभोवती छोटा बफर)."""
    if direction == "BULLISH" and structure_info.get("last_swing_low"):
        low = structure_info["last_swing_low"]
        return (round(low * 0.998, 2), round(low * 1.002, 2))
    elif direction == "BEARISH" and structure_info.get("last_swing_high"):
        high = structure_info["last_swing_high"]
        return (round(high * 0.998, 2), round(high * 1.002, 2))
    return None
def compute_atr(df, period=14):
    """Average True Range (ATR) मोजण्यासाठी फंक्शन."""
    if df is None or df.empty or len(df) < period:
        return None
    
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr
