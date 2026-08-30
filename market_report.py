"""
market_report.py
--------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — दररोज दुपारी ४ वाजता, दुसऱ्या दिवसाच्या Intraday +
Positional Option Selling साठी संक्षिप्त, कृतीयोग्य अहवाल. यात कच्चा डेटा (संपूर्ण Option Chain, संपूर्ण
OI इतिहास table, संपूर्ण Trades Log) समाविष्ट नाही — फक्त सारांशित, निर्णय-उपयुक्त माहिती:
  १) उद्याचा Outlook (1D/1H/15M Supertrend दिशा एकत्रित करून)
  २) महत्त्वाचे S/R levels
  ३) आजचे ठळक Chart Patterns (मागच्या 2-3 candles पेक्षा मोठे Hammer/Shooting Star)
  ४) OI Buildup सारांश (आजचा शेवटचा Put/Call Writing/Buying कल)
  ५) VIX + शिफारस केलेली रणनीती (Intraday + Positional दोन्ही)
  ६) उघड्या positions असल्यास त्यांची Greeks स्थिती

हे module फक्त डेटा गोळा करतं (dict स्वरूपात) — PDF/Telegram रेंडरिंग वेगळ्या ठिकाणी (pdf_reports.py,
eod_market_report.py) होतं, जेणेकरून प्रत्येक भाग स्वतंत्रपणे टेस्ट करता येईल.
"""
import sqlite3

from config import DB_PATH, get_ist_today
from signals import calculate_supertrend, resample_to_1h, find_significant_reversal_candles
from sr_dynamic import compute_dynamic_sr
from oi_analysis import classify_oi_price_action, generate_oi_price_signal
from database import compute_per_position_greeks

VIX_NO_TRADE_THRESHOLD = 20
VIX_IRON_CONDOR_THRESHOLD = 16


def compute_multi_tf_outlook(df_15m, df_1h, df_1d):
    """
    1D/1H/15M Supertrend दिशा एकत्रित करून एकच Outlook ("BULLISH"/"BEARISH"/"MIXED") ठरवणे —
    तिन्ही एकाच दिशेत असतील तरच स्पष्ट Outlook, नाहीतर "MIXED" (सावधगिरीचा इशारा).
    रिटर्न: {"outlook": .., "daily_dir": .., "hourly_dir": .., "min15_dir": ..}
    """
    directions = {}
    for label, df, period, mult in [("daily_dir", df_1d, 10, 3), ("hourly_dir", df_1h, 10, 3), ("min15_dir", df_15m, 10, 3)]:
        if df is None or df.empty or len(df) < period + 2:
            directions[label] = None
            continue
        _, dir_series = calculate_supertrend(df, period=period, multiplier=mult)
        last_dir = dir_series.dropna()
        directions[label] = "BULLISH" if (not last_dir.empty and int(last_dir.iloc[-1]) == 1) else ("BEARISH" if not last_dir.empty else None)

    valid_dirs = [d for d in directions.values() if d is not None]
    if not valid_dirs:
        outlook = "INSUFFICIENT DATA"
    elif all(d == "BULLISH" for d in valid_dirs):
        outlook = "BULLISH"
    elif all(d == "BEARISH" for d in valid_dirs):
        outlook = "BEARISH"
    else:
        outlook = "MIXED"
    return {"outlook": outlook, **directions}


def _translate_oi_trend_to_english(marathi_trend_text):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — oi_analysis.classify_oi_price_action() Dashboard साठी
    (मराठी मिश्रित) मजकूर देतं, पण हा EOD Report आता इंग्रजीत हवा आहे. मूळ Dashboard-सेवा देणाऱ्या
    function ला अजिबात स्पर्श न करता (त्याचा Marathi Dashboard वर परिणाम होऊ नये), फक्त इथेच भाषांतर.
    """
    if "अपुरा डेटा" in marathi_trend_text:
        return "Insufficient data"
    if "Writing" in marathi_trend_text:
        return "Writing (new selling increasing)"
    if "Buying" in marathi_trend_text:
        return "Buying (new buying increasing)"
    if "Short Covering" in marathi_trend_text:
        return "Short Covering (sellers exiting)"
    if "Long Unwinding" in marathi_trend_text:
        return "Long Unwinding (buyers exiting)"
    return marathi_trend_text  # सुरक्षित fallback, ओळखता न आलेला मजकूर तसाच


def get_today_oi_buildup_summary(symbol):
    """
    आजच्या दिवसाच्या पहिल्या व शेवटच्या oi_diff_snapshots वरून — दिवसभरातला निव्वळ Put/Call
    Writing/Buying कल आणि शेवटचा signal. रिटर्न: dict, किंवा डेटा नसेल तर None.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    today_str = get_ist_today().strftime("%Y-%m-%d")
    cur.execute(
        """SELECT total_put_oi, total_call_oi, total_put_premium, total_call_premium, signal
           FROM oi_diff_snapshots WHERE symbol=? AND trade_date=? ORDER BY snapshot_time ASC""",
        (symbol, today_str),
    )
    rows = cur.fetchall()
    conn.close()
    if len(rows) < 2:
        return None

    first, last = rows[0], rows[-1]
    put_class = classify_oi_price_action(last[0], first[0], last[2], first[2])
    call_class = classify_oi_price_action(last[1], first[1], last[3], first[3])
    day_direction, day_message = generate_oi_price_signal(put_class, call_class)
    return {
        "day_put_trend": _translate_oi_trend_to_english(put_class),
        "day_call_trend": _translate_oi_trend_to_english(call_class),
        "day_direction": day_direction, "day_message": day_message,
        "latest_signal": last[4], "snapshot_count": len(rows),
    }


def recommend_strategy(india_vix, oi_signal_direction):
    """
    🎓 oi_greeks_vix_strategy.py च्याच (वापरकर्त्याशी चर्चा करून अंतिम ठरवलेल्या) decision tree नुसार
    — इथे फक्त शिफारस (माहितीसाठी), प्रत्यक्ष trade नाही.
    """
    if india_vix is None:
        return "VIX data unavailable — cannot make a recommendation."
    if india_vix > VIX_NO_TRADE_THRESHOLD:
        return f"VIX={india_vix} > {VIX_NO_TRADE_THRESHOLD} -> Avoid new entries tomorrow (too risky)."
    if india_vix < VIX_IRON_CONDOR_THRESHOLD:
        return f"VIX={india_vix} (<{VIX_IRON_CONDOR_THRESHOLD}, calm market) -> Favourable for Iron Condor (higher chance of range-bound movement)."
    if oi_signal_direction == "BULLISH":
        return f"VIX={india_vix} ({VIX_IRON_CONDOR_THRESHOLD}-{VIX_NO_TRADE_THRESHOLD}), OI trend BULLISH -> Favourable for Bull Put Spread."
    if oi_signal_direction == "BEARISH":
        return f"VIX={india_vix} ({VIX_IRON_CONDOR_THRESHOLD}-{VIX_NO_TRADE_THRESHOLD}), OI trend BEARISH -> Favourable for Bear Call Spread."
    return f"VIX={india_vix} ({VIX_IRON_CONDOR_THRESHOLD}-{VIX_NO_TRADE_THRESHOLD}), but OI trend unclear -> Wait cautiously tomorrow."


def format_telegram_summary(symbol_outlooks):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — दुपारी ४ वाजताच्या PDF सोबतच, त्वरित वाचता येईल असा
    संक्षिप्त Telegram संदेश (HTML parse_mode शी सुसंगत — notifications.send_telegram_message).
    """
    lines = ["📊 <b>EOD Market Report — Tomorrow's Prep</b>\n"]
    for outlook in symbol_outlooks:
        symbol = outlook["symbol"]
        mtf = outlook["multi_tf_outlook"]
        lines.append(f"\n<b>{symbol}</b>")
        lines.append(f"Outlook: {mtf['outlook']} (1D/1H/15M: {mtf.get('daily_dir') or 'N/A'}/{mtf.get('hourly_dir') or 'N/A'}/{mtf.get('min15_dir') or 'N/A'})")
        lines.append(f"VIX: {outlook['india_vix']}")
        lines.append(f"Recommendation: {outlook['recommendation']}")
        if outlook["sr_levels"]:
            res = outlook["sr_levels"].get("resistance", [])
            sup = outlook["sr_levels"].get("support", [])
            if res:
                lines.append(f"R: {res[0]['level']:.0f}")
            if sup:
                lines.append(f"S: {sup[0]['level']:.0f}")
        if outlook["oi_summary"]:
            lines.append(f"OI trend: {outlook['oi_summary']['day_direction']}")
    return "\n".join(lines)


def generate_symbol_outlook(access_token, symbol, df_15m, df_1h, df_1d, india_vix, trading_mode="PAPER"):
    """
    दिलेल्या symbol साठी संपूर्ण उद्याचा Outlook एका dict मध्ये एकत्र करणे — PDF/Telegram दोन्हीसाठी
    वापरता येईल असा, तटस्थ (rendering-agnostic) फॉरमॅट.
    """
    multi_tf = compute_multi_tf_outlook(df_15m, df_1h, df_1d)

    sr_levels = None
    if df_1h is not None and not df_1h.empty:
        current_price = float(df_1h["close"].iloc[-1])
        sr_levels = compute_dynamic_sr(df_1h, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2, current_price=current_price)

    patterns = []
    if df_15m is not None and not df_15m.empty:
        markers = find_significant_reversal_candles(df_15m, lookback_compare=3)
        for idx, pattern in markers[-5:]:  # आजचे शेवटचे ५ पर्यंत, फार गर्दी नको
            row = df_15m.iloc[idx]
            patterns.append({"time": row["timestamp"], "pattern": pattern, "price": float(row["close"])})

    oi_summary = get_today_oi_buildup_summary(symbol)
    oi_direction = oi_summary["day_direction"] if oi_summary else None
    recommendation = recommend_strategy(india_vix, oi_direction)

    greeks_positions = []
    try:
        greeks_positions = compute_per_position_greeks(access_token, symbol, mode_filter=trading_mode)
    except Exception:
        pass

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — PDF मध्ये प्रत्यक्ष chart image दाखवण्यासाठी,
    # आजचा 15M candle डेटा + त्यावरचा Supertrend (line, फक्त दिशा नाही) इथेच सोबत ठेवणे.
    chart_supertrend_line = None
    if df_15m is not None and not df_15m.empty and len(df_15m) > 12:
        chart_supertrend_line, _ = calculate_supertrend(df_15m, period=10, multiplier=3)

    return {
        "symbol": symbol, "multi_tf_outlook": multi_tf, "sr_levels": sr_levels,
        "chart_patterns": patterns, "oi_summary": oi_summary, "india_vix": india_vix,
        "recommendation": recommendation, "open_positions_greeks": greeks_positions,
        "chart_df": df_15m, "chart_supertrend_line": chart_supertrend_line,
    }
