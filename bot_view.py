"""
bot_view.py
------------
🎓 "Strategy ला लागणारे indicators आपोआप plot" -- चार्टवर "Bot view": निवडलेल्या bot चे **प्रत्यक्ष ACTIVE levels** (Supabase `market_zones`, जे bot खरंच trade करतो --
Dashboard चार्टचा स्वतःचा compute_dynamic_sr() वेगळा असतो), त्यांचे आजचे hits (max-hits संपलेले फिके), bot च्या settings प्रमाणे RSI उंबरठे / Supertrend timeframes,
आणि "आत्ता entry का थांबेल" गेट-स्थिती ओळी (फक्त RSI + Supertrend; PCR / min-hold / breakout इ. इथे नाहीत). फक्त दाखवतो -- कुठलाही trade / setting बदलत नाही.

हा module UI-मुक्त आणि चाचणीयोग्य: डेटा (zones, settings, hits, candles) बाहेरून येतो; पान (page_dashboard / page_mcx_futures) तो आणतं.
"""
import pandas as pd

from dynamic_sr_instant_trader import _completed_bars_only, check_supertrend_trend_filter, get_supertrend_direction
from signals import calculate_rsi, calculate_supertrend

NO_BOT = "—"
BOT_VIEWS = {
    "5M Instant": {"strategy_key": "1m_instant", "supertrend": (("15M", 15, "supertrend_15m"), ("1H", 60, "supertrend_1h")), "rsi": "pair"},
    "15M SRv2": {"strategy_key": "15m_dynamic_sr", "supertrend": (), "rsi": "pair"},
    "Classic": {"strategy_key": "classic_sr_reversal", "supertrend": (), "rsi": "neutral"},
    "MCX Futures": {"strategy_key": "mcx_futures", "supertrend": (("1H", 60, "supertrend_1h"), ("4H", 240, "supertrend_4h")), "rsi": "pair"},
}
NSE_BOTS = ("5M Instant", "15M SRv2", "Classic")

# timeframe suffix -> (Upstox interval, रेषेचा रंग). 60M साठी 30-मिनिट candles वरून 1H resample करावं लागतं (interval None).
TF_INTERVAL = {"1M": "1minute", "5M": "5minute", "15M": "15minute", "30M": "30minute", "60M": None}
TF_COLORS = {"1M": (176, 190, 197), "5M": (255, 183, 77), "15M": (79, 195, 247), "30M": (186, 104, 200), "60M": (129, 199, 132)}


def zone_suffixes(bot, settings):
    """bot खरंच कोणत्या timeframes चे levels trade करतो (त्याच्या settings प्रमाणे)."""
    choice = settings.get("timeframe_choice")
    if bot == "5M Instant":
        return ["1M", "5M"] if choice == "BOTH" else (["1M"] if choice == "1M" else ["5M"])
    if bot == "15M SRv2":
        return list(settings.get("active_timeframes") or ["15M"])
    if bot == "Classic":
        return ["5M", "15M"] if choice in (None, "BOTH") else [choice]
    if bot == "MCX Futures":
        return ["30M", "60M"] if choice == "ALL" else [choice or "30M"]
    return []


def rsi_threshold_values(bot, settings):
    """RSI pane वरच्या आडव्या रेषा. Classic = एकच neutral रेषा (Support<N / Resistance>N); बाकी = (support_max, resistance_min)."""
    if BOT_VIEWS[bot]["rsi"] == "neutral":
        return [float(settings.get("rsi_neutral_level", 50))]
    return [float(settings.get("rsi_support_max", 40)), float(settings.get("rsi_resistance_min", 60))]


def supertrend_specs(bot, settings):
    """bot चे Supertrend filter timeframes: [{"label","minutes","period","multiplier"}] (filter बंद असला तरी माहितीसाठी)."""
    specs = []
    for label, minutes, prefix in BOT_VIEWS[bot]["supertrend"]:
        specs.append({
            "label": label, "minutes": minutes,
            "period": int(settings.get(f"{prefix}_period", 10)), "multiplier": float(settings.get(f"{prefix}_multiplier", 3.0)),
        })
    return specs


def supertrend_filter_enabled(bot, settings):
    return bool(BOT_VIEWS[bot]["supertrend"]) and bool(settings.get("entry_supertrend_filter_enabled", False))


def _role(zone_type):
    return "SUPPORT" if "SUPPORT" in str(zone_type) else ("RESISTANCE" if "RESISTANCE" in str(zone_type) else None)


def level_lines(zones_df, suffixes, hits, max_hits, price=None, role_by_price=False, max_distance_pct=3.0):
    """bot चे ACTIVE Dynamic S/R levels -> चार्टच्या आडव्या रेषा. title: 'S 5M ★3 · 1/2' (S/R, timeframe, strength, आजचे hits/max). max-hits संपलेले
    फिके + बारीक. role_by_price (MCX: role प्रत्येक cycle ला किंमत-बाजूवरून ठरतो) असेल तर किंमत >= level => SUPPORT.
    price दिली तर किंमतीपासून max_distance_pct% पेक्षा दूरचे levels वगळले जातात (चार्टचा scale त्यांच्यामुळे ताणला जाऊन candles दबू नयेत; bot तिथे आत्ता trade करणारच नाही)."""
    if zones_df is None or getattr(zones_df, "empty", True):
        return []
    lines = []
    for suffix in suffixes:
        rows = zones_df[(zones_df["zone_type"].str.startswith("DYNAMIC_SR_")) & (zones_df["zone_type"].str.endswith(f"_{suffix}")) & (zones_df["status"] == "ACTIVE")]
        for row in rows.itertuples():
            level = float(row.zone_low)
            if price and max_distance_pct and abs(level - price) / price * 100 > max_distance_pct:
                continue
            role = _role(row.zone_type)
            if role_by_price and price is not None:
                role = "SUPPORT" if price >= level else "RESISTANCE"
            count = int(hits.get((round(level, 2), role), 0)) if hits else 0
            exhausted = count >= max_hits
            r, g, b = TF_COLORS.get(suffix, (200, 200, 200))
            strength = float(row.strength) if row.strength is not None and not pd.isna(row.strength) else 0.0
            lines.append({
                "price": level, "title": f"{'S' if role == 'SUPPORT' else 'R'} {suffix} ★{strength:g} · {count}/{max_hits}",
                "color": f"rgba({r},{g},{b},{0.35 if exhausted else 0.95})", "dashed": exhausted or role == "RESISTANCE", "width": 1 if exhausted else 2,
            })
    return lines


def align_supertrend(chart_df, source_df, period, multiplier):
    """source_df (उदा. 1H) चा Supertrend chart_df च्या timestamps शी no-lookahead (merge_asof, backward) अलाइन -> (line, direction) Series, किंवा (None, None)."""
    if source_df is None or source_df.empty or chart_df is None or chart_df.empty:
        return None, None
    line, direction = calculate_supertrend(source_df, period=int(period), multiplier=float(multiplier))
    if len(line) == 0:
        return None, None
    st_df = pd.DataFrame({"timestamp": source_df["timestamp"], "st_line": line, "st_dir": direction}).dropna()
    if st_df.empty:
        return None, None
    aligned = pd.merge_asof(chart_df[["timestamp"]].sort_values("timestamp"), st_df.sort_values("timestamp"), on="timestamp", direction="backward")
    return aligned["st_line"], aligned["st_dir"]


def supertrend_directions(frames, specs, now):
    """frames: {label: DataFrame}. bot प्रमाणेच -- शेवटच्या **पूर्ण** candle ची दिशा; डेटा नसेल तर None. रिटर्न {label: 'BULLISH'|'BEARISH'|None}."""
    out = {}
    for spec in specs:
        df = frames.get(spec["label"])
        try:
            out[spec["label"]] = get_supertrend_direction(_completed_bars_only(df, spec["minutes"], now), spec["period"], spec["multiplier"]) if df is not None and not df.empty else None
        except Exception:
            out[spec["label"]] = None
    return out


def last_rsi(df, period=14):
    """df चा शेवटचा RSI(14) (bot सारखाच calculate_rsi), नसेल तर None."""
    try:
        series = calculate_rsi(df, period=period)
        return None if series.empty or pd.isna(series.iloc[-1]) else round(float(series.iloc[-1]), 2)
    except Exception:
        return None


def rsi_gate_line(bot, settings, rsi_by_tf):
    """rsi_by_tf: {'5M': 47.1, ...}. 'RSI 47.1 (5M) -> Bullish ✅ / Bearish ❌' ओळ; गेट बंद असेल तर तसं."""
    if not settings.get("entry_rsi_gate_enabled", True):
        return "RSI गेट: बंद (RSI मुळे कोणतीही entry थांबत नाही)"
    neutral = BOT_VIEWS[bot]["rsi"] == "neutral"
    sup_max = float(settings.get("rsi_neutral_level", 50)) if neutral else float(settings.get("rsi_support_max", 40))
    res_min = float(settings.get("rsi_neutral_level", 50)) if neutral else float(settings.get("rsi_resistance_min", 60))
    parts = []
    for tf, value in rsi_by_tf.items():
        if value is None:
            parts.append(f"RSI ({tf}): डेटा नाही")
            continue
        parts.append(f"RSI {value:g} ({tf}) → Bullish {'✅' if value < sup_max else '❌'} (<{sup_max:g}) · Bearish {'✅' if value > res_min else '❌'} (>{res_min:g})")
    return "RSI गेट: " + " | ".join(parts)


def supertrend_gate_line(bot, settings, dirs, specs=None):
    """'Supertrend filter: बंद/चालू · 15M=BEARISH, 1H=BEARISH → Bullish ❌ थांबेल / Bearish ✅' ओळ, किंवा None (या bot ला filter नाही)."""
    specs = specs if specs is not None else supertrend_specs(bot, settings)
    if not specs:
        return None
    labels = [s["label"] for s in specs]
    state = "चालू" if supertrend_filter_enabled(bot, settings) else "बंद (फक्त माहिती)"
    shown = ", ".join(f"{label}={dirs.get(label) or 'डेटा नाही'}" for label in labels)
    ok_bull, _ = check_supertrend_trend_filter("BULLISH", dirs.get(labels[0]), dirs.get(labels[1]))
    ok_bear, _ = check_supertrend_trend_filter("BEARISH", dirs.get(labels[0]), dirs.get(labels[1]))
    return (
        f"Supertrend filter: {state} · {shown} → Bullish {'✅' if ok_bull else '❌ थांबेल'} · Bearish {'✅' if ok_bear else '❌ थांबेल'}"
        + ("" if supertrend_filter_enabled(bot, settings) else " (filter बंद असल्याने प्रत्यक्षात काहीही थांबत नाही)")
    )
