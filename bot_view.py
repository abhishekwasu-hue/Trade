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
from htf_alignment import align_asof
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
SUPPORT_RGB = (0, 200, 83)          # हिरवा
RESISTANCE_RGB = (255, 23, 68)      # लाल
AUTOSCALE_MAX_PCT = 6.0
# chart चा interval -> त्या TF चे Dynamic S/R zone suffix (NIFTY Dashboard चा "—" view: chart च्या TF चे bot चे DB levels)
SRV3_SUFFIX = "SRV3"                                   # MCX SR V3 levels चं चार्टवरचं नाव (zone_type मध्ये TF suffix नसतो)
SRV3_ZONE_TYPES = ("SRV3_SUPPORT", "SRV3_RESISTANCE")  # srv3_instant_shadow.ZONE_TYPES सारखेच
CHART_TF_DYN_SUFFIX = {"1minute": "1M", "5minute": "5M", "15minute": "15M", "30minute": "30M", "1hour": "60M"}             # यापेक्षा दूरच्या S/R रेषा चार्टचा scale ताणत नाहीत


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
    return bool(BOT_VIEWS[bot]["supertrend"]) and (bool(settings.get("entry_supertrend_filter_enabled", False))
                                                    or settings.get("supertrend_filter_mode", "off") != "off")


def _role(zone_type):
    return "SUPPORT" if "SUPPORT" in str(zone_type) else ("RESISTANCE" if "RESISTANCE" in str(zone_type) else None)


def level_lines(zones_df, suffixes, hits, max_hits, price=None, role_by_price=False, max_distance_pct=3.0, nearest_n=0, info_suffixes=()):
    """bot चे ACTIVE Dynamic S/R levels -> चार्टच्या आडव्या रेषा. title: 'S 5M ★3 · 1/2' (S/R, timeframe, strength, आजचे hits/max). max-hits संपलेले
    फिके + बारीक. role_by_price (MCX: role प्रत्येक cycle ला किंमत-बाजूवरून ठरतो) असेल तर किंमत >= level => SUPPORT.
    price दिली तर किंमतीपासून max_distance_pct% पेक्षा दूरचे levels वगळले जातात (चार्टचा scale त्यांच्यामुळे ताणला जाऊन candles दबू नयेत).
    🎓 "chart war important level disaylach pahije" (NG: 299–300 चा resistance ±4% च्या बाहेर म्हणून लपत होता) -- `nearest_n` > 0 असेल तर त्या
    अंतराबाहेरचेही किंमतीच्या **वरचे n आणि खालचे n** सर्वात जवळचे levels दाखवले जातात (थोडे फिके, title मध्ये "· दूर X%"). bot ते levels
    नेहमीप्रमाणेच trade करतो -- हे बंधन फक्त चार्टसाठी. `info_suffixes` = bot trade **न** करत असलेल्या timeframes चे levels (उदा. MCX "30M"
    निवडलेलं असताना 60M) -- राखाडी, ठिपक्यांची रेषा, title "· माहिती" (फक्त पाहण्यासाठी)."""
    if zones_df is None or getattr(zones_df, "empty", True):
        return []
    cands = []
    for suffix, info in [(s_, False) for s_ in suffixes] + [(s_, True) for s_ in info_suffixes if s_ not in suffixes]:
        if suffix == SRV3_SUFFIX:                        # MCX level_engine SRV3 -- `SRV3_SUPPORT`/`SRV3_RESISTANCE` (TF suffix नसतो)
            kind = zones_df["zone_type"].isin(SRV3_ZONE_TYPES)
        else:
            kind = (zones_df["zone_type"].str.startswith("DYNAMIC_SR_")) & (zones_df["zone_type"].str.endswith(f"_{suffix}"))
        rows = zones_df[kind & (zones_df["status"] == "ACTIVE")]
        for row in rows.itertuples():
            cands.append((float(row.zone_low), suffix, info, row))
    far_keep = set()                                     # (level, info) -- trade होणारे आणि माहितीचे levels स्वतंत्रपणे (माहितीचे trade होणाऱ्यांना ढकलू नयेत)
    if price and max_distance_pct and nearest_n:
        for grp in (False, True):
            far = [c for c in cands if c[2] is grp and abs(c[0] - price) / price * 100 > max_distance_pct]
            above = sorted({c[0] for c in far if c[0] > price})[:nearest_n]
            below = sorted({c[0] for c in far if c[0] <= price}, reverse=True)[:nearest_n]
            far_keep |= {(lv, grp) for lv in above + below}
    lines = []
    for level, suffix, info, row in cands:
        dist_pct = abs(level - price) / price * 100 if price else 0.0
        is_far = bool(price and max_distance_pct and dist_pct > max_distance_pct)
        if is_far and (level, info) not in far_keep:
            continue
        role = _role(row.zone_type)
        if role_by_price and price is not None:
            role = "SUPPORT" if price >= level else "RESISTANCE"
        strength = float(row.strength) if row.strength is not None and not pd.isna(row.strength) else 0.0
        tag = "S" if role == "SUPPORT" else "R"
        r, g, b = SUPPORT_RGB if role == "SUPPORT" else RESISTANCE_RGB
        far_note = f" · दूर {dist_pct:.1f}%" if is_far else ""
        # 🎓 वापरकर्त्याची मागणी: resistance = लाल ठिपक्यांची रेषा, support = हिरवी ठिपक्यांची रेषा. timeframe title मध्ये ("R 30M ★4 · 0/2").
        # खूप दूरच्या (> AUTOSCALE_MAX_PCT) रेषा autoscale ताणत नाहीत -- candles दबू नयेत.
        common = {"price": level, "dotted": True, "dashed": True, "bounds": not (is_far and dist_pct > AUTOSCALE_MAX_PCT)}
        if info:
            lines.append({**common, "title": f"{tag} {suffix} ★{strength:g} · माहिती" + far_note, "color": f"rgba({r},{g},{b},0.4)", "width": 1})
            continue
        count = int(hits.get((round(level, 2), role), 0)) if hits else 0
        exhausted = count >= max_hits
        alpha = 0.35 if exhausted else (0.6 if is_far else 0.95)
        lines.append({**common, "title": f"{tag} {suffix} ★{strength:g} · {count}/{max_hits}" + far_note,
                      "color": f"rgba({r},{g},{b},{alpha})", "width": 1 if (exhausted or is_far) else 2})
    return lines


def mcx_info_suffixes(suffixes):
    """MCX: bot trade करत नसलेले Dynamic S/R timeframes (30M/60M पैकी) -- चार्टवर फक्त माहितीसाठी."""
    return tuple(s_ for s_ in ("30M", "60M") if s_ not in suffixes)


def mcx_level_suffixes(settings):
    """MCX चार्टवर कोणते levels bot चे (hits सकट) आणि कोणते फक्त माहितीचे -- symbol च्या `level_engine` प्रमाणे -> (traded, info).
    🎓 "1402 hi level chart war nahi disat" -- COPPER चा bot SR V3 levels वर trade करत होता, पण चार्ट नेहमी Dynamic 30M/60M दाखवायचा.
    SRV3 = bot SR V3 levels वर (Dynamic 30M/60M माहितीसाठी); SRV3_SHADOW = bot Dynamic वर, SR V3 (shadow) माहितीसाठी; DYNAMIC = आधीसारखं."""
    engine = settings.get("level_engine", "DYNAMIC")
    if engine == "SRV3":
        return [SRV3_SUFFIX], ("30M", "60M")
    dyn = zone_suffixes("MCX Futures", settings)
    return dyn, mcx_info_suffixes(dyn) + ((SRV3_SUFFIX,) if engine == "SRV3_SHADOW" else ())


def align_supertrend(chart_df, source_df, period, multiplier):
    """source_df (उदा. 1H) चा Supertrend chart_df शी no-lookahead अलाइन (HTF bar फक्त bar_end नंतर; htf_alignment.align_asof) -> (line, direction) Series, किंवा (None, None)."""
    if source_df is None or source_df.empty or chart_df is None or chart_df.empty:
        return None, None
    line, direction = calculate_supertrend(source_df, period=int(period), multiplier=float(multiplier))
    if len(line) == 0:
        return None, None
    cols = {"timestamp": source_df["timestamp"], "st_line": line, "st_dir": direction}
    if "bar_end" in source_df.columns:
        cols["bar_end"] = source_df["bar_end"]
    st_df = pd.DataFrame(cols).dropna(subset=["st_line", "st_dir"])
    if st_df.empty:
        return None, None
    # 🎓 fix/completed-bars-1h -- HTF bar चार्टच्या bar ला फक्त त्याच्या bar_end नंतरच जोडला जातो (आधी label वर merge_asof: चालू/अपूर्ण HTF bar चा अंतिम
    # Supertrend आधीच दिसायचा -- भविष्यातला डेटा). आता bot ज्या "शेवटच्या पूर्ण candle" ची दिशा वापरतो तीच चार्टवरही दिसते.
    aligned = align_asof(chart_df, st_df, ["st_line", "st_dir"])
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


def rejection_markers(chart_df, level_prices, settings):
    """🎓 Candle confirmation (MCX): **दाखवलेल्या** chart TF च्या पूर्ण candles वर bot च्या levels जवळचे rejection markers + score
    (price_action.candles.scan_markers). चार्टची शेवटची (चालू) candle वगळली. फक्त दाखवण्यासाठी — bot चा निर्णय नेहमी level च्या TF वर."""
    from price_action import candles as PA
    if chart_df is None or len(chart_df) < 2 or not level_prices:
        return []
    s = settings or {}
    return PA.scan_markers(chart_df.iloc[:-1].reset_index(drop=True), level_prices, k=max(1.0, float(s.get("candle_k", 1.2))),
                           min_score=float(s.get("candle_min_score", 60)))


def mcx_trendline_overlay(df30_long, chart_df, now, min_touches=2):
    """🎓 तिरक्या trendlines (टप्पा 1 — फक्त दाखवण्यासाठी): 45 दिवसांच्या 30M वरून पूर्ण 60M candles, त्यावर उतरती resistance / चढती support
    (price_action.trendlines). रिटर्न (chart segments, caption). चार्ट daily असेल किंवा डेटा नसेल तर ([], None)."""
    from price_action import trendlines as TL
    if df30_long is None or len(df30_long) == 0 or chart_df is None or len(chart_df) == 0:
        return [], None
    df60 = TL.completed_hours(df30_long, now)
    lines = TL.detect_trendlines(df60, min_touches=min_touches)
    if not lines:
        return [], "Trendline (60M, 45 दिवस): सध्या वैध तिरकी रेषा नाही."
    start = pd.Timestamp(pd.to_datetime(chart_df["timestamp"]).min())
    start = start.tz_convert("Asia/Kolkata").tz_localize(None) if start.tzinfo else start     # df60 naive IST
    segs = TL.chart_segments(lines, df60, chart_start=start)
    cap = "Trendline (60M, 45 दिवस, फक्त माहिती — trading नाही): " + "; ".join(
        f"{'उतरती resistance' if ln['side'] == 'resistance' else 'चढती support'} {ln['touches']} touches "
        f"({ln['a_ts']:%d %b} → {ln['b_ts']:%d %b}), आत्ता ≈ {ln['next_price']:,.2f}" for ln in lines)
    return segs, cap


LEG_TF_MINUTES = {"1minute": 1, "5minute": 5, "15minute": 15, "30minute": 30, "1hour": 60}


def leg_overlay(chart_df, chart_tf, now, cfg=None):
    """🎓 T2 legs (फक्त माहिती): चार्टच्या **पूर्ण** candles वरून swings → legs → लेबल (price_action.legs). चालू (provisional) leg तुटक रेषा.
    रिटर्न (chart legs, caption). डेटा अपुरा ⇒ ([], None). Daily चार्टवर आजचा candle 15:30 पूर्वी वगळतो."""
    from price_action import legs as LG
    if chart_df is None or len(chart_df) < 30:
        return [], None
    mins = LEG_TF_MINUTES.get(chart_tf)
    if mins:
        df = _completed_bars_only(chart_df, mins, now)
    else:                                                            # daily: आजचा candle बाजार बंद होईपर्यंत अपूर्ण ⇒ वगळा
        df = chart_df
        now_ts = pd.Timestamp(now)
        now_ts = now_ts.tz_localize(None) if now_ts.tzinfo else now_ts
        last = pd.Timestamp(df["timestamp"].iloc[-1])
        last = last.tz_localize(None) if last.tzinfo else last
        if last.normalize() >= now_ts.normalize() and now_ts.time() < pd.Timestamp("15:30").time():
            df = df.iloc[:-1]
    df = df.reset_index(drop=True)
    legs, swing, internal = LG.build_legs(df, cfg)
    cur = LG.current_leg(df, cfg, legs, swing, internal)
    segs = LG.chart_legs(df, legs, cur)
    if not segs:
        return [], "Legs: पुरेसे confirmed swings नाहीत."
    last = legs[-1] if legs else None
    cap = ("Legs (T2, फक्त माहिती — trading नाही): गडद = impulse, फिकट = pullback, राखाडी = range, जांभळा = उलटफेर, तुटक = चालू leg. "
           + (f"शेवटचा पूर्ण leg: {LG.leg_info(last)}" if last else "") + (f" · चालू: {LG.LABEL_MR.get(cur.label, cur.label)}" if cur else ""))
    return segs, cap
