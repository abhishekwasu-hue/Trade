"""
dynamic_sr_instant_trader.py
------------------------------------
1-मिनिट Instant Reversal Trader — Bot Dynamic SR Algo नवीन नियम-संच (Word document, वापरकर्त्याशी
चर्चा करून ठरवलेला):
  - Signal: 1-मिनिट + 5-मिनिट Dynamic S/R levels एकत्र (पूल केलेले, first-touch-wins, कुठल्याही
    timeframe ला प्राधान्य नाही).
  - RSI(14, 1-मिनिट) फिल्टर — जुनाच (Support<40/Resistance>60) — जसाच्या तसा ठेवलेला.
  - Multi-Hit (कमाल 2/level/दिवस) + 30-मिनिट Cooldown + बिनशर्त position-open check — जुनेच.
  - Strike Selection — Credit Spread: Short **ITM** (settings-चालित depth, डीफॉल्ट 50 points),
    Long hedge (डीफॉल्ट 150 points दूर) — आधीच्या ATM ऐवजी.
  - Naked Option Trade ("Long With Hedge") — त्याच सिग्नलवर, समांतर — डीफॉल्ट सक्रिय (Dashboard
    वरून बंद करता येतं), डीफॉल्ट hedge नाही (निव्वळ ITM खरेदी) — वापरकर्ता Dashboard वरून hedge
    सक्रिय करू शकतो.
  - Expiry Day (आज == चालू साप्ताहिक expiry) -> पुढच्या आठवड्याची expiry वापरणे (जास्त जोखीम टाळणे).
  - Lots/ITM-depth/Hedge-width/Naked-toggle — cloud_db.get_strategy_settings("1m_instant", symbol)
    वरून, Dashboard-बदलण्याजोगे (hardcode नाही).
  - Exit (SL/TSL/Target, स्पॉट% + प्रीमियम-पॉइंट्स एकत्र, TSL-to-Breakeven) — trading_engine.py
    मध्ये केंद्रीकृत (evaluate_point_spot_exit) — इथे फक्त entry_level_price/entry_timeframe
    साठवला जातो.

Gap Up/Down हाताळणी (check_level_crossed, TOUCH + GAP_THROUGH) आणि "आजचाच दिवस" फिल्टर (कालचे
candles चुकून न मिसळणे) — दोन्ही जुन्याच, आधीच सापडलेल्या bugs साठीचे फिक्स — जसेच्या तसे ठेवलेले.

🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Directional Flip on IV Breakout — "In trending I want
to block reversals trade, but trending trade should be continue") — Average IV Breakout Gate
(`entry_iv_gate_enabled`) आता, आढळल्यास (आजचा IV गेल्या सरासरीपेक्षा जास्त वाढलेला — trending regime),
trade पूर्णपणे **skip** करत नाही — त्याऐवजी दिशा **flip** करून, त्याच touch वर breakout-च्याच
दिशेने (reversal ऐवजी trend-continuation) trade घेतला जातो (structure तेच — Credit Spread + Naked,
फक्त उलट बाजूचं). अशा directional trades साठी RSI/PCR Gate मुद्दामच वगळले जातात (ते reversal-साठीच
tuned आहेत — उदा. RSI<40 चा अर्थ "oversold, वर bounce होईल" असा reversal-गृहीतक आहे, breakout-
continuation साठी उलटा/चुकीचा संकेत ठरेल). IV डेटाच उपलब्ध नसेल/जुना असेल (fail-safe — regime
माहीतच नाही) तरच पूर्वीसारखं trade skip होतं, flip नाही (अनिश्चित दिशेने directional bet घेणं
धोकादायक).

🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry) — `entry_breakout_gate_enabled` (डीफॉल्ट
बंद) — simple, स्वतंत्र breakout-based trade, कुठल्याही आजच्या hit-count वर अवलंबून नाही. अट: एक
5-मिनिट candle त्या level पासून किमान `breakout_close_buffer_pct`% (Dashboard-configurable, डीफॉल्ट
0.10%) तरी पलीकडे निर्णायकपणे close झाला (नुसता touch नाही, `check_breakout_candle_close`) — हीच
एकमेव अट. अट पूर्ण झाली तरच breakout-दिशेने trade — RSI/PCR Gate (directional trade असल्याने, IV-flip
सारखंच) आणि 30-मिनिट Cooldown (मुद्दामच लगेच यायला हवं म्हणून) दोन्ही वगळलेले.

🎓 वापरकर्त्याशी चर्चा करून सापडवलेली/सुधारलेली विसंगती ("5minute dynamic sr Breakout jhalyanantr ch
Breakout trade ghenyat yenar") — breakout confirm करणारे candles कायमच 5-मिनिट असतात, त्यामुळे
Breakout Entry फक्त `timeframe_choice` मध्ये सक्रिय असलेल्या **5M** Dynamic S/R levels (`zone_type`
मध्ये `_5M` असलेले) च्या touches वरच तपासला जातो — `timeframe_choice="BOTH"` (डीफॉल्ट) असताना
pooled_levels मध्ये असलेल्या 1M levels च्या touches वर हा गेट पूर्णपणे वगळला जातो (5M candle close
वरून 1M level "तुटला" ठरवणं विसंगत ठरलं असतं).

🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("Tya level war previous day che touches aahet, kiwa
level Breakout jhali mhanun trade hit jhala pahije, ashi simple condition Breakout trade ka lagu
kra, jast complex karu nka") — आधी हा फक्त "आजचे दोन्ही touch (max-2-hits) आधीच झालेले" (established
Multi-Hit counter, खाली) असतील तरच तपासला जायचा — प्रत्येक Dynamic S/R zone आधीच बहुदिवसीय ऐतिहासिक
price-clustering वरून तयार झालेला असल्याने ("previous day touches" आधीच गृहीत), ही अतिरिक्त अट
काढली — आता breakout फक्त candle-close अटीवरच, स्वतंत्रपणे, प्रत्येक touch वर तपासला जातो. max-2-hits
ची जुनी मर्यादा फक्त breakout **न** आढळलेल्या साध्या reversal touches साठीच अजूनही लागू आहे.

🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("Breakout sathi consolidation chi condition pn remove
kra") — price consolidation ("buildup" — breakout-candle च्या आधीच्या काही candles मध्ये किंमत level
जवळ टिकून होती का, `check_breakout_price_consolidation`) ही अट सुद्धा काढली — आता फक्त candle-close
buffer% हाच एकमेव निकष उरलेला आहे (वरती). हे function अजूनही MCX Futures च्या स्वतंत्र Breakout Entry
साठी वापरलं जातं, फक्त इथे (5-Min Instant Trader) यापुढे कॉल होत नाही.

🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute Breakout candle + Volume ashi condition ठेवता
yeil") — ऐच्छिक (`breakout_volume_confirm_enabled`, डीफॉल्ट बंद) Volume Confirmation —
`check_breakout_volume_confirmation` — breakout-candle चा volume त्याआधीच्या
`breakout_volume_lookback_candles` (डीफॉल्ट 10) candles च्या सरासरीपेक्षा किमान
`breakout_volume_multiplier` (डीफॉल्ट 1.5) पट जास्त असावा लागतो — कमी-volume (संभाव्य fake/whipsaw)
breakouts गाळण्यासाठी, candle-close अटीसोबतच (AND) तपासला जातो.

🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("option chain analysis oi snapshot every 5 minute save
kele जातात tech yethe use krta yeil") — ऐच्छिक (`breakout_oi_confirm_enabled`, डीफॉल्ट बंद) OI
Confirmation — established `oi_analysis.get_latest_oi_signal()`/`check_oi_diff_entry_gate()` (A1
Engine मध्ये आधीच वापरलेलं, नवीन logic नाही) चाच पुनर्वापर — `oi_snapshot_collector.py` ने दर 5
मिनिटांनी साठवलेला सर्वात अलीकडचा Put/Call OI-Price signal breakout_direction शी जुळतो (किंवा उलट
दिशा "Weakening" असेल) तरच पास, candle-close/volume अटींसोबतच (AND) तपासला जातो.
"""
import argparse

import pandas as pd

import cloud_db
from config import get_ist_now, DB_PATH
from database import init_sqlite_db, has_open_trade_from_source, get_last_sl_tsl_exit_time, run_auto_backup_if_due, get_first_target_exit_today, get_open_trades_brief
from notifications import send_telegram_message, write_heartbeat, notify_error
from signals import calculate_rsi, calculate_supertrend, resample_to_1h
from oi_analysis import check_pcr_gate, check_iv_change_gate, get_latest_oi_signal, check_oi_diff_entry_gate
from process_lock import ProcessLock, ProcessLockHeld
from strategy import select_credit_spread_itm, select_credit_spread_fixed_strikes, select_naked_option_itm
from trading_engine import open_multi_leg_trade, format_trade_result, close_trade_manually
from upstox_api import fetch_upstox_option_chain, fetch_candles, fetch_option_expiries

RSI_SUPPORT_MAX = 40     # Support touch + 1-मिनिट RSI < 40 -> Bull Put Spread
RSI_RESISTANCE_MIN = 60  # Resistance touch + 1-मिनिट RSI > 60 -> Bear Call Spread

# 14:45 नंतर नवीन entry नाही (आधीच्या उघड्या positions वर याचा परिणाम नाही, त्या EOD ला बंद होतील).
NO_NEW_ENTRY_AFTER_HOUR = 14
NO_NEW_ENTRY_AFTER_MINUTE = 45

# 🎓 वापरकर्त्याने मागितलेली सुधारणा — आधी ±0.02% होता, मग वापरकर्त्याने पूर्णपणे काढायला सांगितला
# (0), आणि लगेच पुढे "Keep level touch buffer 0.010% of spot" — म्हणजे पूर्णपणे तंतोतंत स्पर्शाऐवजी,
# आधीच्या निम्मा (0.02% -> 0.01%), छोटासा buffer परत ठेवायचा — level पासून ±0.01% च्या आत candle
# चा low/high आला तरी अजूनही "स्पर्श" (TOUCH) धरला जातो.
TOUCH_TOLERANCE_PCT = 0.01

# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("क्षणभर एखाद्या level च्या खाली/वरती गेल्यानंतर ताबडतोब
# support चा resistance किंवा resistance चा support असं नोंदवणं कितपत योग्य आहे... hysteresis
# लागू कर") — आधी direction (BULLISH/BEARISH) फक्त `current_price >= level` या raw तुलनेवर ठरायची
# — किंमत level च्या अगदी काठावर wobble करत असेल, तर प्रत्येक मिनिटाला direction उगाच फ्लिप व्हायची
# (उदा. RSI Entry Gate चुकीच्या rule कडे — Support<40 ऐवजी Resistance>60 — पडताळला जायचा). आता
# ±0.10% hysteresis buffer — किंमत level पासून स्पष्टपणे (buffer च्या पलीकडे) एका बाजूला जात नाही,
# तोपर्यंत मागची "निश्चित" दिशाच कायम राहते (बघा determine_direction_with_hysteresis()).
DIRECTION_HYSTERESIS_BUFFER_PCT = 0.10

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — 1M आता 5M सोबतच एकत्र, पूल केलेले (Instrument key/
# zone_type suffix -> "timeframe" लेबल, entry_timeframe column साठी).
POOLED_TIMEFRAMES = ["1M", "5M"]
_NOT_CHECKED = object()  # 'Target नंतर थांबवा' तपासणी अजून झालेली नाही, याची खूण (None म्हणजे 'Target लागलेला नाही')


def check_instant_rsi_filter(candles_df, direction, rsi_support_max=RSI_SUPPORT_MAX, rsi_resistance_min=RSI_RESISTANCE_MIN):
    """1-मिनिट RSI(14) फिल्टर — Support(BULLISH) -> RSI rsi_support_max च्या खाली.
    Resistance(BEARISH) -> RSI rsi_resistance_min च्या वर. रिटर्न: (pass: bool, rsi_value: float|None)
    उंबरठे आता Dashboard वरून (Entry Gate) बदलण्याजोगे — settings दिले नाहीत तर जुनेच डीफॉल्ट."""
    rsi_series = calculate_rsi(candles_df, period=14)
    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
        return False, None
    latest_rsi = round(float(rsi_series.iloc[-1]), 2)
    if direction == "BULLISH":
        return latest_rsi < rsi_support_max, latest_rsi
    return latest_rsi > rsi_resistance_min, latest_rsi


def check_level_crossed(level, candles, tolerance_pct=TOUCH_TOLERANCE_PCT):
    """अलीकडच्या candles च्या [low,high] रेंज मधून (±tolerance_pct% बफरसह), आणि सलग candles मधल्या
    gap मधूनही (मागच्या candle चा close ते पुढच्या candle चा open) level ओलांडला का तपासणे.
    candles: [{"open":.., "high":.., "low":.., "close":..}, ...] (जुनं ते नवीन क्रमाने).
    रिटर्न: (hit: bool, hit_type: "TOUCH"/"GAP_THROUGH"/None, approx_price: float/None)"""
    buffer = level * tolerance_pct / 100
    level_low, level_high = level - buffer, level + buffer

    prev_close = None
    for c in candles:
        if c["low"] <= level_high and c["high"] >= level_low:
            return True, "TOUCH", level
        if prev_close is not None:
            if (prev_close < level < c["open"]) or (prev_close > level > c["open"]):
                return True, "GAP_THROUGH", c["open"]
        prev_close = c["close"]
    return False, None, None


def count_consecutive_touch_minutes(level, candles, tolerance_pct=TOUCH_TOLERANCE_PCT):
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Minimum Level-Hold Duration Before Entry" —
    Performance Report वरून सापडलेल्या "level हिट होताच SL उडणं" या पॅटर्नवर, signal_log backtest
    केल्यावर) — सद्य क्षणापासून मागे मोजत, level ±tolerance_pct% च्या बफरमध्ये सलग किती मिनिटांचे
    (1-मिनिट) candles सतत आहेत हे मोजणे. candles: जुनं ते नवीन क्रमाने (todays_candles_df सारखे,
    प्रत्येक dict मध्ये किमान "low"/"high" key). मागे जाताना एकही candle बफरबाहेर सापडला की मोजणी
    थांबते — सलगपणा तुटल्यावर जुना (आधीचा, न-जोडलेला) इतिहास मोजला जात नाही.
    🎓 code-review द्वारे सापडवलेली दस्तऐवजीकरण-चूक (fix अगोदरची आवृत्ती "0 म्हणजे ताजाच touch" असं
    सांगायची, पण चालू candle स्वतःच बफरमध्ये overlap होत असल्याने त्याचीही मोजणी होतेच) — स्पष्ट करून:
    सद्य (चालू) candle स्वतःच बफरमध्ये overlap होत असेल, तर तोच पहिला मोजला जातो (सामान्य TOUCH साठी
    परिणाम नेहमी >=1, कधीच 0 नाही). फक्त GAP_THROUGH प्रकारच्या hit साठी (check_level_crossed()) चालू
    candle बफरच्या पूर्णपणे बाहेर असू शकतो (किंमत level च्याच पलीकडे एका झटक्यात गेलेली) — तेव्हाच हे
    फंक्शन 0 परत करतं.
    🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — GAP_THROUGH साठीही हा 0 result process_symbol() मध्ये
    मुद्दामच वेगळा हाताळला जात नाही (सुरुवातीला तसं सुचवलं गेलं होतं, नंतर उलट ठरवलं) — सकाळी बाजार
    उघडताच gap-down/gap-up होऊन आधीच साठवलेल्या level च्या पार गेलं, तर तो सगळ्यात अस्थिर, अपुष्ट
    क्षण असतो — त्याला "निर्णायक" मानून लगेच entry देणं धोकादायक. त्यामुळे gate/shadow दोन्ही ठिकाणी
    TOUCH आणि GAP_THROUGH एकाच नियमाने (held_minutes ची अटच) तपासले जातात — gap नंतर किंमत level
    जवळ खरोखर टिकून (TOUCH होऊन) राहिल्याशिवाय entry होणार नाही.
    रिटर्न: int (सलग मिनिटांची संख्या — TOUCH साठी नेहमी >=1, GAP_THROUGH साठी नेहमी 0)."""
    buffer = level * tolerance_pct / 100
    level_low, level_high = level - buffer, level + buffer
    count = 0
    for c in reversed(candles):
        if c["low"] <= level_high and c["high"] >= level_low:
            count += 1
        else:
            break
    return count


def determine_direction_with_hysteresis(level, closes, buffer_pct=DIRECTION_HYSTERESIS_BUFFER_PCT):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (hysteresis, ±0.10%) — किंमत level पासून ±buffer_pct% च्या
    आतच (borderline) असेल, तर आधीचीच "निश्चित" दिशा कायम ठेवायची (उगाच फ्लिप नाही). closes (आजच्या
    सर्व candles च्या close किमती, जुनं ते नवीन क्रमाने) मधून मागे जाऊन, ज्या पहिल्या candle चं close
    त्या बॅंडच्या (level±buffer) स्पष्टपणे बाहेर आहे, तीच शेवटची निश्चित दिशा मानली जाते — त्यामुळे
    कुठलंही वेगळं persisted state न ठेवताही (हा script दर मिनिटाला नव्याने चालतो), प्रत्येक वेळी
    सुसंगत उत्तर मिळतं. दिवसभर कधीच बॅंडबाहेर गेलं नसेल (उदा. दिवसाची सुरुवात, नवीनच level), तर
    सद्य किमतीची raw तुलनाच (जुनं वर्तन) सुरक्षित fallback म्हणून वापरली जाते.
    रिटर्न: "BULLISH"/"BEARISH" """
    buffer = level * buffer_pct / 100
    upper, lower = level + buffer, level - buffer
    for close in reversed(closes):
        if close >= upper:
            return "BULLISH"
        if close <= lower:
            return "BEARISH"
    return "BULLISH" if closes[-1] >= level else "BEARISH"


def check_breakout_candle_close(level, breakout_direction, candles_5m, buffer_pct=0.10):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "Breakout buildup and 5 minute
    candle closed happen then take entry in the same direction") — नुकताच पूर्ण झालेला (शेवटचा,
    आजच्याच दिवसाचा) 5-मिनिट candle त्या level च्या पलीकडे निर्णायकपणे **close** झाला आहे का (नुसता
    touch/wick नाही, candle close) — breakout_direction नुसार (BULLISH = level च्या वर close,
    BEARISH = level च्या खाली close). candles_5m: [{"close":..}, ...] (जुनं ते नवीन क्रमाने, फक्त
    आजचेच).

    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute candle close Breakout beyond 0.10%") —
    फक्त level च्या अगदी काठावर (0.001 पॉइंटनेही) close होणं "निर्णायक" मानलं जाऊ नये (noise/whipsaw
    असू शकतं) — आता close level पासून किमान `buffer_pct`% (Dashboard-configurable, डीफॉल्ट 0.10%,
    वापरकर्त्याशी चर्चा करून 0.010% वरून वाढवलेला) तरी पलीकडे असावा लागतो. रिटर्न: bool"""
    if not candles_5m:
        return False
    last_close = candles_5m[-1]["close"]
    buffer = level * buffer_pct / 100
    if breakout_direction == "BULLISH":
        return last_close > level + buffer
    return last_close < level - buffer


def _completed_bars_only(df, bar_minutes, now):
    """शेवटचा bar अजून पूर्ण झालेला (त्याचा कालावधी संपलेला) नसेल तर तो वगळतो — Supertrend दिशा फक्त पूर्ण
    झालेल्या candle ची घ्यायची (चालू candle वारंवार फिरते). timestamp = bar ची सुरुवात (IST)."""
    if df is None or df.empty:
        return df
    last_ts = pd.Timestamp(df["timestamp"].iloc[-1])
    now_ts = pd.Timestamp(now)
    if last_ts.tzinfo is not None:
        last_ts = last_ts.tz_localize(None)
    if now_ts.tzinfo is not None:
        now_ts = now_ts.tz_localize(None)
    if last_ts + pd.Timedelta(minutes=bar_minutes) > now_ts:
        return df.iloc[:-1]
    return df


def get_supertrend_direction(df, period, multiplier):
    """df चा (शेवटच्या bar वरचा) Supertrend दिशा: "BULLISH" (किंमत Supertrend च्या वर) / "BEARISH" (खाली) / None."""
    if df is None or df.empty:
        return None
    _, direction = calculate_supertrend(df, period=int(period), multiplier=float(multiplier))
    if direction is None or len(direction) == 0:
        return None
    return "BULLISH" if int(direction.iloc[-1]) == 1 else "BEARISH"


def fetch_trend_filter_directions(access_token, symbol, now, st15_period=10, st15_multiplier=3.0,
                                  st1h_period=10, st1h_multiplier=3.0):
    """🎓 "1 hr Supertrend and 15 Minute Supertrend price donhi supertrend chya khali aslyas stop Bullish trade" —
    (15M दिशा, 1H दिशा), दोन्ही शेवटच्या **पूर्ण झालेल्या** candle ची. 1H candles 30M वरून resample (बाकी
    प्रोजेक्ट प्रमाणेच). डेटा मिळाला नाही/चूक झाली तर त्या टाईमफ्रेमसाठी None (गेट fail-open)."""
    dir_15m = dir_1h = None
    try:
        df15 = fetch_candles(access_token, symbol, current_spot=0, interval="15minute", lookback_days=5)
        if df15 is not None and not df15.empty:
            dir_15m = get_supertrend_direction(_completed_bars_only(df15, 15, now), st15_period, st15_multiplier)
    except Exception:
        dir_15m = None
    try:
        df30 = fetch_candles(access_token, symbol, current_spot=0, interval="30minute", lookback_days=10)
        if df30 is not None and not df30.empty:
            df30 = df30.copy()
            for col in ("volume", "oi"):
                if col not in df30.columns:
                    df30[col] = 0
            df1h = resample_to_1h(df30)
            dir_1h = get_supertrend_direction(_completed_bars_only(df1h, 60, now), st1h_period, st1h_multiplier)
    except Exception:
        dir_1h = None
    return dir_15m, dir_1h


def check_supertrend_trend_filter(direction, dir_15m, dir_1h):
    """Bullish trade फक्त तेव्हा थांबतो जेव्हा 15M **आणि** 1H दोन्ही Supertrend BEARISH (किंमत दोन्हीच्या खाली);
    Bearish trade फक्त तेव्हा जेव्हा दोन्ही BULLISH (किंमत दोन्हीच्या वर). एक सहमत नसेल, किंवा डेटा नसेल
    (None) तर काहीच अडवत नाही (fail-open). रिटर्न: (ok: bool, reason: str|None)."""
    if dir_15m is None or dir_1h is None:
        return True, None
    if direction == "BULLISH" and dir_15m == "BEARISH" and dir_1h == "BEARISH":
        return False, "किंमत 15M आणि 1H दोन्ही Supertrend च्या खाली आहे (दोन्ही BEARISH) — Bullish trade थांबवला"
    if direction == "BEARISH" and dir_15m == "BULLISH" and dir_1h == "BULLISH":
        return False, "किंमत 15M आणि 1H दोन्ही Supertrend च्या वर आहे (दोन्ही BULLISH) — Bearish trade थांबवला"
    return True, None


def is_level_formed_in_session(formed_date, now):
    """🎓 "intraday new form" level -- zone आज बाजार चालू झाल्यानंतर (09:15 नंतर) तयार झाला का. रात्रीचा/सकाळच्या
    पूर्व-बाजार refresh चे levels (जुने, आधीच अनेक तासांचे) 'नवीन' मानले जात नाहीत. formed_date समजला नाही
    (None/अवैध) तर False (म्हणजे level जुना समजला जातो -- fail-open, trade अडवला जात नाही)."""
    if formed_date is None:
        return False
    try:
        ts = pd.to_datetime(formed_date)
        if pd.isna(ts):
            return False
        if ts.tzinfo is not None:
            ts = ts.tz_convert("Asia/Kolkata").tz_localize(None)
    except Exception:
        return False
    return ts.date() == now.date() and (ts.hour, ts.minute) >= (9, 15)


def check_level_strength_gate(strength, formed_date, now, min_strength, new_levels_only=True):
    """🎓 Level Strength Gate -- strength (एकत्र आलेल्या pivots ची संख्या) < min_strength असलेल्या कमकुवत level वर
    reversal trade नाही. new_levels_only=True (डीफॉल्ट) असेल तर फक्त आज intraday तयार झालेल्या कमकुवत levels ला
    लागू -- जुने बहुदिवसीय levels strength 2 असले तरी आधीच टिकलेले आहेत, ते चालतात. strength समजली नाही (None)
    तर अडवत नाही. रिटर्न: (ok: bool, reason: str|None)."""
    try:
        strength_value = float(strength)
    except (TypeError, ValueError):
        return True, None
    if pd.isna(strength_value) or strength_value >= min_strength:
        return True, None
    if new_levels_only and not is_level_formed_in_session(formed_date, now):
        return True, None
    kind = "आज नवीन तयार झालेला" if new_levels_only else "कमकुवत"
    return False, (f"{kind} level -- strength {strength_value:.0f} < किमान {min_strength} "
                   f"(पुन्हा टिकून strength वाढेपर्यंत trade नाही)")


def check_fast_move_into_level(direction, closes, lookback_minutes, threshold_pct):
    """🎓 "Huge slippages" -- किंमत level कडे खूप वेगाने येत असेल (मागच्या `lookback_minutes` 1-मिनिट closes मध्ये
    `threshold_pct`% पेक्षा जास्त हालचाल, level च्या दिशेने) तर reversal (bounce) entry घेऊ नये: BULLISH (support वर
    बाउन्स) साठी किंमत जोरात खाली आली असेल, BEARISH (resistance वरून परतणे) साठी जोरात वर. अशा वेळी level
    टिकण्याची शक्यता कमी आणि SL लागताना slippage जास्त. closes कमी असतील / पुरेशी माहिती नसेल तर अडवत नाही.
    रिटर्न: (ok: bool, reason: str|None)."""
    try:
        lookback = int(lookback_minutes)
        if lookback < 1 or not closes or len(closes) < lookback + 1:
            return True, None
        start, end = float(closes[-(lookback + 1)]), float(closes[-1])
        if start <= 0:
            return True, None
    except (TypeError, ValueError):
        return True, None
    move_pct = (end - start) / start * 100
    toward_level_pct = -move_pct if direction == "BULLISH" else move_pct
    if toward_level_pct >= threshold_pct:
        word = "खाली" if direction == "BULLISH" else "वर"
        return False, (f"मागच्या {lookback} मिनिटांत किंमत {toward_level_pct:.2f}% वेगाने level कडे {word} आली "
                       f"(मर्यादा {threshold_pct}%) -- वेगवान हालचालीत reversal entry टाळला")
    return True, None


def check_breakout_supertrend_alignment(direction, dir_15m, dir_1h):
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Breakout दोन्ही Supertrend च्या दिशेनेच झालेला असावा") —
    Breakout trade फक्त तेव्हा जेव्हा 15M **आणि** 1H दोन्ही Supertrend ची दिशा breakout च्या दिशेशी जुळते
    (Bullish breakout => दोन्ही BULLISH; Bearish breakout => दोन्ही BEARISH). reversal filter
    (`check_supertrend_trend_filter`, fail-open) पेक्षा उलट — इथे डेटा नसेल (None) तर trade **थांबतो**
    (वापरकर्त्याचा निर्णय). रिटर्न: (ok: bool, reason: str|None)."""
    if dir_15m is None or dir_1h is None:
        return False, f"Supertrend डेटा उपलब्ध नाही (15M={dir_15m or 'N/A'}, 1H={dir_1h or 'N/A'}) — Breakout थांबवला"
    if dir_15m == direction and dir_1h == direction:
        return True, None
    return False, f"Supertrend दिशा जुळत नाही (15M={dir_15m}, 1H={dir_1h}; breakout={direction}) — Breakout थांबवला"


def build_breakout_eval_note(direction, level, last_close, close_pct, buffer_pct, candle_close_ok,
                             volume_enabled, volume_ratio, volume_multiplier, volume_ok,
                             oi_enabled, oi_signal, oi_ok, st_enabled, st_dir_15m, st_dir_1h, st_ok,
                             direction_from_close, final_ok):
    """🎓 "Breakout ची नोंद सविस्तर करा" — प्रत्येक Breakout तपासणीची (Breakout झाला किंवा नाही) नोंद.
    `[BRK:...]` हा सुरुवातीचा तुकडा फक्त स्थिर निकाल-चिन्हं (✓/✗/-) असतो, जिवंत आकडे नाहीत —
    `cloud_db.save_signal_log()` च्या dedup मध्ये तोच वापरला जातो (अटींचा निकाल बदलला तरच नवीन नोंद);
    त्यापुढे वाचनीय तपशील (आकडे सकट). ✓ = अट पूर्ण, ✗ = अपूर्ण, - = सेटिंग बंद / तपासलीच नाही."""
    def mark(enabled, ok):
        if not enabled:
            return "-"
        return "-" if ok is None else ("✓" if ok else "✗")
    sig = (f"[BRK:{direction} C{mark(True, candle_close_ok)} V{mark(volume_enabled, volume_ok)} "
           f"O{mark(oi_enabled, oi_ok)} S{mark(st_enabled, st_ok)}"
           + (f"(15M={st_dir_15m or 'N/A'},1H={st_dir_1h or 'N/A'})" if st_enabled and st_ok is not None else "")
           + f" => {'BREAKOUT' if final_ok else 'NO'}]")
    parts = [f"दिशा {direction}" + (" (5M close वरून)" if direction_from_close else " (level भूमिकेवरून)"),
             f"level {level:.2f}"]
    if close_pct is not None:
        parts.append(f"5M close {last_close:.2f} ({close_pct:+.3f}% पलीकडे; किमान {buffer_pct:.3f}% हवं) "
                     f"{'✓' if candle_close_ok else '✗'}")
    if volume_enabled:
        parts.append(f"Volume {volume_ratio if volume_ratio is not None else 'N/A'}x (किमान {volume_multiplier:.1f}x) "
                     f"{mark(True, volume_ok)}")
    if oi_enabled:
        parts.append(f"OI Signal {oi_signal or 'N/A'} {mark(True, oi_ok)}")
    if st_enabled:
        if st_ok is None:
            parts.append("Supertrend तपासलं नाही (वरच्या अटी आधीच अपूर्ण)")
        else:
            parts.append(f"Supertrend 15M={st_dir_15m or 'N/A'}, 1H={st_dir_1h or 'N/A'} {mark(True, st_ok)}")
    return sig + " " + "; ".join(parts) + f" => {'Breakout trade' if final_ok else 'Breakout नाही'}."


def determine_breakout_direction_from_close(level, candles_5m, buffer_pct, lookback_candles=3):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("22538 support Breakout trade ka execute jhala nahi" ->
    "Breakout ची दिशा 5M close च्या बाजूवरून ठरवा") — आधी breakout ची दिशा नेहमी level च्या *भूमिकेवरून*
    (SUPPORT => BEARISH, RESISTANCE => BULLISH) ठरायची, आणि ती भूमिका १-मिनिट close च्या ±०.१०% hysteresis ने
    ठरते. पण breakout confirm मात्र ५-मिनिट close फक्त `buffer_pct` (उदा. ०.०१०%) पलीकडे गेला की होतो. वेगवान
    घसरणीत (उदा. ३ मिनिटांत ०.१२%) भूमिका SUPPORT -> RESISTANCE अशी आधीच बदलते, मग breakout ची दिशा उलटून
    BULLISH शोधली जाते — आणि खरा breakdown कधीच पकडला जात नाही.

    आता: शेवटचा ५-मिनिट close level पेक्षा `buffer_pct` इतका खाली असेल आणि मागच्या `lookback_candles` candles
    पैकी कोणताही एक close level च्या वर असेल => BEARISH (support तुटला). उलट बाजूसाठी BULLISH. म्हणजे
    "level खरोखर ओलांडला गेला" हे ५-मिनिट close वरूनच ठरतं, १-मिनिट भूमिकेवरून नाही. ओलांडलेलं नसेल (किंवा
    आधीचे candles नसतील) तर None — caller जुनी भूमिका-आधारित दिशा वापरतो. रिटर्न: "BULLISH"/"BEARISH"/None."""
    if not candles_5m or len(candles_5m) < 2:
        return None
    last_close = candles_5m[-1]["close"]
    buffer = level * buffer_pct / 100
    previous_closes = [c["close"] for c in candles_5m[-(lookback_candles + 1):-1]]
    if last_close < level - buffer and any(c > level for c in previous_closes):
        return "BEARISH"
    if last_close > level + buffer and any(c < level for c in previous_closes):
        return "BULLISH"
    return None


def get_breakout_volume_ratio(candles_5m, lookback_candles=10):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("candle-close %, volume ratio, OI signal Signal Log मध्ये
    स्वतंत्रपणे दाखवायचे") — खालच्या check_breakout_volume_confirmation() मधलाच ratio, फक्त bool
    ऐवजी नेमकी संख्या (लॉगिंग/audit साठी). रिटर्न: round केलेला float, किंवा पुरेसे candles नसतील/
    सरासरी volume शून्य असेल तर None."""
    if not candles_5m or len(candles_5m) < lookback_candles + 1:
        return None
    window = candles_5m[-(lookback_candles + 1):-1]
    avg_volume = sum(c.get("volume", 0) for c in window) / len(window)
    if avg_volume <= 0:
        return None
    last_volume = candles_5m[-1].get("volume", 0)
    return round(last_volume / avg_volume, 2)


def check_breakout_volume_confirmation(candles_5m, lookback_candles=10, multiplier=1.5):
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute Breakout candle + Volume ashi condition
    ठेवता yeil") — breakout-confirm करणाऱ्या (शेवटच्या) 5-मिनिट candle चा volume, त्याआधीच्या
    `lookback_candles` candles च्या सरासरी volume पेक्षा किमान `multiplier` पट जास्त असावा — कमी
    volume वरचा close हा अनेकदा खोटा/whipsaw breakout ठरतो, जास्त volume खऱ्या सहभागाचा पुरावा.
    candles_5m: [{"close":.., "volume":..}, ...] (जुनं ते नवीन क्रमाने, फक्त आजचेच). रिटर्न: bool"""
    if not candles_5m or len(candles_5m) < lookback_candles + 1:
        return False
    window = candles_5m[-(lookback_candles + 1):-1]
    avg_volume = sum(c.get("volume", 0) for c in window) / len(window)
    if avg_volume <= 0:
        return False
    last_volume = candles_5m[-1].get("volume", 0)
    return last_volume >= avg_volume * multiplier


def check_breakout_price_consolidation(level, candles_5m, lookback_candles=12, tolerance_pct=0.30):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "buildup" साठी वेगळं, gate/trade-
    outcome-independent logic — "A" (max-2-hits touch-count, आधीच hit_count_so_far>=2 वरून established)
    आणि "C" (price consolidation) एकत्र) — शेवटच्या (breakout-confirm करणाऱ्या) candle च्या **आधीच्या**
    `lookback_candles` 5-मिनिट candles मध्ये price level च्या ±tolerance_pct% च्या आतच राहिला होता का
    — level किती वेळ प्रत्यक्षात "test/defend" झाला याचा शुद्ध price-action पुरावा (कुठलाही indicator
    नाही, फक्त close किमती). candles_5m: [{"close":..}, ...] (जुनं ते नवीन क्रमाने, फक्त आजचेच,
    शेवटचा candle = breakout-confirm candle, त्या आधीचे consolidation window साठी). रिटर्न: bool"""
    window = candles_5m[-(lookback_candles + 1):-1]
    if len(window) < lookback_candles:
        return False
    tolerance_points = level * tolerance_pct / 100
    return all(abs(c["close"] - level) <= tolerance_points for c in window)


def is_todays_expiry_day(access_token, symbol):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Expiry-Day Logic) — आज चालू (सर्वात जवळची)
    साप्ताहिक expiry आहे का, प्रत्यक्ष option-chain expiry-यादीवरून (गृहीत धरलेला वार नाही)."""
    expiries = fetch_option_expiries(access_token, symbol)
    if not expiries:
        return False
    return expiries[0] == get_ist_now().strftime("%Y-%m-%d")


def _collect_pooled_levels(all_zones, timeframes=None):
    """दिलेल्या timeframes (डीफॉल्ट दोन्ही — 1M व 5M) च्या ACTIVE levels एकाच यादीत —
    [(zone_row, timeframe_suffix), ...]. वापरकर्त्याने settings मधून फक्त एकच टाईमफ्रेम
    (timeframe_choice="1M"/"5M") निवडली असेल, तर तेवढंच पूल केलं जातं."""
    pooled = []
    for suffix in (timeframes or POOLED_TIMEFRAMES):
        dyn_levels = all_zones[(all_zones["zone_type"].str.endswith(f"_{suffix}")) & (all_zones["status"] == "ACTIVE")]
        for _, row in dyn_levels.iterrows():
            pooled.append((row, suffix))
    return pooled


def find_overlapping_15m_level(all_zones, level, distance_pct, current_price, direction):
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (5M+15M ओव्हरलॅप -> 15M strategy) — दिलेल्या 5M `level`
    च्या `distance_pct`% च्या आत असलेला, सर्वात जवळचा ACTIVE 15M Dynamic S/R level शोधतो, जर त्याची दिशा
    `direction` शी जुळत असेल. 15M level ची दिशा (srv2_momentum_reversal_strategy.py सारखीच) सद्य
    किमतीच्या त्या level च्या सापेक्ष स्थितीवरून: किंमत level च्या वर/बरोबर = Support/BULLISH, खाली =
    Resistance/BEARISH (साठवलेल्या label वरून नाही). रिटर्न: (level_15m, अंतर_%) किंवा None."""
    if all_zones is None or all_zones.empty or not level:
        return None
    zones_15m = all_zones[(all_zones["zone_type"].str.endswith("_15M")) & (all_zones["status"] == "ACTIVE")]
    best = None
    for _, zone in zones_15m.iterrows():
        level_15m = float(zone["zone_low"])
        distance = abs(level_15m - level) / level * 100
        if distance > distance_pct:
            continue
        direction_15m = "BULLISH" if current_price >= level_15m else "BEARISH"
        if direction_15m != direction:
            continue
        if best is None or distance < best[1]:
            best = (level_15m, distance)
    return best


def is_15m_strategy_ready_for(symbol, direction, trading_mode):
    """15M strategy (`15m_dynamic_sr`) या symbol साठी सक्रिय आहे का, याच trading_mode मध्ये आहे का,
    15M timeframe निवडलेला आहे का, आणि या दिशेची entry चालू आहे का — तरच 5M ने बाजूला व्हावं (नाहीतर
    कुणीच trade घेत नाही आणि level वाया जातो). settings वाचता आल्या नाहीत तर False (fail-open —
    5M स्वतः trade घेतो). रिटर्न: (ready: bool, कारण: str)."""
    try:
        s15 = cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)
    except Exception:
        return False, "15M settings वाचता आल्या नाहीत"
    if not s15.get("symbol_enabled", False):
        return False, "15M strategy या symbol साठी बंद आहे"
    if s15.get("trading_mode", "PAPER") != trading_mode:
        return False, f"15M चा trading_mode ({s15.get('trading_mode', 'PAPER')}) 5M शी ({trading_mode}) जुळत नाही"
    if "15M" not in (s15.get("active_timeframes") or ["15M"]):
        return False, "15M timeframe 15M strategy मध्ये निवडलेला नाही"
    if direction == "BULLISH" and not s15.get("bullish_entry_enabled", True):
        return False, "15M चा Bullish Entry बंद आहे"
    if direction == "BEARISH" and not s15.get("bearish_entry_enabled", True):
        return False, "15M चा Bearish Entry बंद आहे"
    return True, ""


FIVE_MIN_FAMILY_SOURCES = ("dynamic_sr_instant", "dynamic_sr_instant_otm_shadow", "dynamic_sr_instant_min_hold_shadow")


def close_open_5m_positions(access_token, symbol, detail):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (5M+15M "एका वेळी एकच position"; 5M थांबतो तेव्हा त्याचे उघडे
    trades लगेच बंद) — या symbol चे सर्व OPEN 5M-कुटुंबातले trades (मूळ + शॅडो) established
    trading_engine.close_trade_manually() ने बंद (exit_reason "YIELDED_TO_15M"; LIVE मध्ये खरे MARKET orders).
    रिटर्न: (सर्व_बंद: bool, बंद_ids: list, अयशस्वी: [(trade_id, कारण), ...])."""
    closed, failed = [], []
    for trade_id, source, _mode in get_open_trades_brief(symbol, FIVE_MIN_FAMILY_SOURCES):
        if source not in FIVE_MIN_FAMILY_SOURCES:  # defensive — फक्त 5M-कुटुंबातले
            continue
        ok, result = close_trade_manually(access_token, trade_id, symbol, "D", exit_reason="YIELDED_TO_15M", exit_reason_detail=detail)
        (closed if ok else failed).append(trade_id if ok else (trade_id, result))
    return (not failed), closed, failed


def open_15m_position_exists(symbol, trading_mode):
    """या symbol वर, याच trading_mode मध्ये, 15M SRv2 चा trade सध्या OPEN आहे का (भांडवल एकच म्हणून)."""
    return any(
        src == "srv2_momentum_reversal" and mode == trading_mode
        for _tid, src, mode in get_open_trades_brief(symbol, ("srv2_momentum_reversal",))
    )


def process_symbol(access_token, symbol, lot_size=65):
    """एका symbol साठी — 1M+5M levels एकत्र, RSI-फिल्टर, Multi-Hit/Cooldown, Expiry-Day Logic, आणि
    आढळल्यास Credit-Spread (ITM) + (सक्रिय असल्यास) समांतर Naked Option PAPER trade."""
    settings = cloud_db.get_strategy_settings("1m_instant", symbol)
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (symbol_enabled) — उपलब्ध भांडवलानुसार वापरकर्ता
    # Bot Dynamic SR Algo पानावरून प्रत्येक symbol स्वतंत्रपणे चालू/बंद करू शकतो — बंद असलेल्या
    # symbol वर इथेच थांबतो, पुढचं काहीही (zones/candles fetch, trade) होत नाही.
    if not settings.get("symbol_enabled", symbol == "NIFTY"):
        return f"{symbol}: बंद आहे (symbol_enabled=False, Bot Dynamic SR Algo सेटिंग्जमधून सक्रिय करा)"
    lots = settings["lots"]
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — Naked Option Trade आधी नेहमी Credit Spread च्याच lots
    # (वेगळं सेटिंगच नव्हतं) घ्यायचा — आता स्वतंत्र, Bot Dynamic SR Algo पानावरून बदलण्याजोगं.
    naked_lots = settings.get("naked_lots", lots)
    bullish_entry_enabled = settings.get("bullish_entry_enabled", True)
    bearish_entry_enabled = settings.get("bearish_entry_enabled", True)
    entry_rsi_gate_enabled = settings.get("entry_rsi_gate_enabled", True)
    rsi_support_max = settings.get("rsi_support_max", RSI_SUPPORT_MAX)
    rsi_resistance_min = settings.get("rsi_resistance_min", RSI_RESISTANCE_MIN)
    entry_pcr_gate_enabled = settings.get("entry_pcr_gate_enabled", True)
    entry_iv_gate_enabled = settings.get("entry_iv_gate_enabled", False)
    iv_change_max_pct = settings.get("iv_change_max_pct", 15.0)
    iv_lookback_days = settings.get("iv_lookback_days", 10)
    iv_marubozu_threshold = settings.get("iv_marubozu_threshold", 0.8)
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Max trade on same level yachi setting sidhha द्या, default
    # 2") — established "आजच्या या zone साठी कमाल 2 वेळा" ही मर्यादा आधी hardcoded (2) होती.
    max_hits_per_zone = int(settings.get("max_hits_per_zone", 2))
    entry_breakout_gate_enabled = settings.get("entry_breakout_gate_enabled", False)
    breakout_close_buffer_pct = settings.get("breakout_close_buffer_pct", 0.10)
    entry_supertrend_filter_enabled = settings.get("entry_supertrend_filter_enabled", False)
    breakout_supertrend_filter_enabled = settings.get("breakout_supertrend_filter_enabled", False)
    entry_min_level_strength_enabled = settings.get("entry_min_level_strength_enabled", False)
    entry_fast_move_guard_enabled = settings.get("entry_fast_move_guard_enabled", False)
    fast_move_lookback_minutes = settings.get("fast_move_lookback_minutes", 5)
    fast_move_threshold_pct = settings.get("fast_move_threshold_pct", 0.12)
    min_level_strength = settings.get("min_level_strength", 3)
    level_strength_new_levels_only = settings.get("level_strength_new_levels_only", True)
    supertrend_15m_period = settings.get("supertrend_15m_period", 10)
    supertrend_15m_multiplier = settings.get("supertrend_15m_multiplier", 3.0)
    supertrend_1h_period = settings.get("supertrend_1h_period", 10)
    supertrend_1h_multiplier = settings.get("supertrend_1h_multiplier", 3.0)
    supertrend_directions_cache = []  # प्रति-symbol, प्रति-cycle एकदाच (सर्व levels साठी सारखं) — lazily
    breakout_direction_from_close = settings.get("breakout_direction_from_close", False)
    breakout_cross_lookback_candles = int(settings.get("breakout_cross_lookback_candles", 3))
    breakout_volume_confirm_enabled = settings.get("breakout_volume_confirm_enabled", False)
    breakout_volume_lookback_candles = settings.get("breakout_volume_lookback_candles", 10)
    breakout_volume_multiplier = settings.get("breakout_volume_multiplier", 1.5)
    breakout_oi_confirm_enabled = settings.get("breakout_oi_confirm_enabled", False)
    entry_min_hold_gate_enabled = settings.get("entry_min_hold_gate_enabled", False)
    entry_min_hold_minutes = settings.get("entry_min_hold_minutes", 3)
    entry_min_hold_first_trade_only = settings.get("entry_min_hold_first_trade_only", True)
    min_hold_shadow_enabled = settings.get("min_hold_shadow_enabled", False)
    stop_after_target_enabled = settings.get("stop_after_target_enabled", False)
    defer_to_15m_enabled = settings.get("defer_to_15m_enabled", False)
    defer_to_15m_distance_pct = float(settings.get("defer_to_15m_distance_pct", 0.10))
    timeframe_choice = settings.get("timeframe_choice", "BOTH")
    active_timeframes = POOLED_TIMEFRAMES if timeframe_choice == "BOTH" else [timeframe_choice]

    all_zones = cloud_db.get_market_zones(symbol)
    if all_zones is None or all_zones.empty:
        return f"{symbol}: कुठलेही zones सापडले नाहीत (आधी refresh_market_zones.py चालवा)"

    pooled_levels = _collect_pooled_levels(all_zones, active_timeframes)
    if not pooled_levels:
        return f"{symbol}: कुठलेही ACTIVE Dynamic S/R levels ({'/'.join(active_timeframes)}) नाहीत"

    candles_df = fetch_candles(access_token, symbol, current_spot=0, interval="1minute", lookback_days=1)
    if candles_df is None or candles_df.empty:
        return f"{symbol}: 1-मिनिट candles मिळाले नाहीत"

    # lookback_days=1 म्हणजे "मागचे १ कॅलेंडर दिवस" — कालच्या दिवसाचे शेवटचे candles सुद्धा येतात.
    # दिवसाच्या सुरुवातीला (आजचे candles अजून पुरेसे तयार नसताना) कालचा candle चुकून वापरला जाऊ नये
    # म्हणून आजच्याच तारखेचे candles आधी वेगळे काढून, त्यातूनच शेवटचे तपासतो.
    today_date = get_ist_now().date()
    candles_df["_date"] = candles_df["timestamp"].dt.date
    todays_candles_df = candles_df[candles_df["_date"] == today_date]
    if todays_candles_df.empty:
        return f"{symbol}: आजचे 1-मिनिट candles अजून तयार झालेले नाहीत"

    recent_candles = todays_candles_df.tail(2).to_dict("records")  # फक्त शेवटचे 2 (सद्य किंमत + gap-check)
    current_price = recent_candles[-1]["close"]

    now = get_ist_now()
    trade_date = now.strftime("%Y-%m-%d")

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (hysteresis) — सर्व levels साठी एकच, प्रति-symbol एकदाच
    # काढलेली आजच्या close किमतींची यादी (प्रत्येक level साठी पुन:पुन्हा tolist() करायची गरज नाही).
    todays_closes = todays_candles_df["close"].tolist()
    # "Minimum Level-Hold Duration" गेटसाठी — सर्व levels साठी एकच, प्रति-symbol एकदाच काढलेले
    # आजचे सर्व 1-मिनिट candles (low/high सकट) — count_consecutive_touch_minutes() ला हवेत.
    todays_candle_records = todays_candles_df.to_dict("records")

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Breakout Entry — "missed window" catch-up, खाली
    # पहा) — entry_breakout_gate_enabled असेल तर आजचे 5-मिनिट candles इथेच एकदाच (प्रति-symbol,
    # प्रति-cycle) आणून ठेवले — प्रत्येक 5M level साठी खालच्या breakout तपासणीत पुन्हा वापरले जातात
    # (आधी प्रत्येक level साठी हा API कॉल स्वतंत्रपणे व्हायचा — एकच किंमत असूनही).
    todays_5m_candles_all = []
    if entry_breakout_gate_enabled and "5M" in active_timeframes:
        candles_5m_df = fetch_candles(access_token, symbol, current_spot=0, interval="5minute", lookback_days=1)
        if candles_5m_df is not None and not candles_5m_df.empty:
            candles_5m_df = candles_5m_df.copy()
            candles_5m_df["_date"] = candles_5m_df["timestamp"].dt.date
            todays_5m_df = candles_5m_df[candles_5m_df["_date"] == today_date]
            # 🎓 bug-review (वापरकर्त्याचा निर्णय: "नेहमी पूर्ण झालेला candle") -- Upstox चा intraday डेटा चालू (अजून न
            # संपलेला) 5-मिनिट candle सुद्धा देतो. "5-मिनिट candle close" म्हणून तो वापरला तर breakout candle संपण्याआधीच
            # मध्येच entry होऊ शकते आणि volume अर्धवट मोजला जातो. आता फक्त पूर्ण झालेले candles (Supertrend प्रमाणेच).
            todays_5m_candles_all = _completed_bars_only(todays_5m_df, 5, now).to_dict("records")

    outcomes = []
    target_hit_today = _NOT_CHECKED
    for row, timeframe_suffix in pooled_levels:
        hit, hit_type, approx_price = check_level_crossed(row["zone_low"], recent_candles)
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Breakout Entry — "missed window" catch-up,
        # फक्त Breakout साठीच, established reversal-touch मार्गाला अजिबात स्पर्श न करता) — साधारण
        # परिस्थितीत 1-मिनिट touch आणि 5-मिनिट candle-close जवळजवळ एकाच वेळी येतात. पण अतिशय
        # वेगवान, एकाच झटक्यातल्या हालचालीत (उदा. दिवसाच्या पहिल्याच 5-मिनिट candle मध्ये किंमत
        # एकाच दिशेने खूप दूर निघून जाणे — वापरकर्त्याने प्रत्यक्ष उदाहरणासह दाखवलेली स्थिती) —
        # 1-मिनिट touch लवकर मिळतो (candle अजून बंदच झालेला नसतो, breakout तपासताच येत नाही), आणि
        # candle बंद होईपर्यंत किंमत आधीच level पासून खूप दूर निघून गेलेली असते — नवीन touch-eventच
        # मिळत नाही, आणि पूर्ण झालेला breakout कायमचा हुकतो. हा catch-up — फक्त timeframe_suffix==
        # "5M" आणि entry_breakout_gate_enabled असेल, आणि साधा 1-मिनिट touch सापडलाच नसेल, तरच —
        # शेवटच्या दोन 5-मिनिट candles मध्येच स्वतंत्रपणे तपासतो (त्याच established
        # check_level_crossed() ने) की level ओलांडला गेला का. सापडला, तरच खाली Breakout Entry ची
        # पूर्ण अट (candle-close buffer%/Volume/OI) तपासली जाते — ती अपुरी पडली, तर हा "hit" साध्या
        # reversal trade मध्ये कधीच वापरला जात नाही (खाली स्पष्ट guard, breakout_catchup_hit).
        breakout_catchup_hit = False
        if not hit and entry_breakout_gate_enabled and timeframe_suffix == "5M" and todays_5m_candles_all:
            hit, hit_type, approx_price = check_level_crossed(row["zone_low"], todays_5m_candles_all[-2:])
            breakout_catchup_hit = hit

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — दिशा आता row["zone_type"] च्या साठवलेल्या
        # (मागच्या रात्रीच्या/मागच्या merge-cron cycle च्या) SUPPORT/RESISTANCE label वरून नाही, तर
        # सद्य किमतीच्या (current_price) level च्या सापेक्ष स्थितीवरून ठरते — srv2_momentum_reversal_strategy.py
        # मध्ये आधीच वापरलेल्या नियमाप्रमाणेच ("दिशा सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून
        # ठरते, साठवलेल्या ऐतिहासिक label वरून नाही"). किंमत level च्या वर = Resistance/BEARISH,
        # खाली किंवा बरोबर = Support/BULLISH — साठवलेला label जुना/स्टेल असला (उदा. gap-open नंतर
        # किंमत level च्या दुसऱ्याच बाजूला गेली) तरी प्रत्यक्ष trade नेहमी सद्य किमतीशी सुसंगतच घेतला
        # जातो, आधीच्या रात्रीच्या किमतीशी नाही.
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("क्षणभर level च्या खाली/वर गेल्यावर लगेच direction फ्लिप
        # करणं योग्य नाही... hysteresis लागू कर, 0.10% buffer") — आता raw तुलनेऐवजी hysteresis सह
        # (बघा determine_direction_with_hysteresis()) — किंमत level पासून ±0.10% च्या आतच wobble
        # करत असेल, तर आधीचीच निश्चित दिशा कायम राहते, प्रत्येक मिनिटाला उगाच फ्लिप होत नाही.
        direction = determine_direction_with_hysteresis(row["zone_low"], todays_closes)
        # 🎓 वापरकर्त्याने सापडवलेली bug ("SR flip साठी hysteresis 0.10% ठेवला, त्यानुसार हा level
        # resistance व्हायलाच नको होता") — role (SUPPORT/RESISTANCE, hit-counting आणि Breakout Entry
        # च्या दिशेसाठी वापरला जाणारा) आधी वरच्या `direction` ला अजिबात न जुमानता, थेट `row["zone_type"]`
        # (DB मध्ये साठवलेला, दर ५-मिनिटांच्या merge-cron ने वारंवार पुन्हा-गणना होणारा raw label)
        # मधून यायचा — त्यामुळे किंमत level च्या अगदी जवळ wobble करत असतानाही role फ्लिप व्हायचा,
        # जो नेमका hysteresis ने टाळायचा होता (तो फक्त इथल्याच RSI Gate/Telegram च्या `direction` ला
        # जोडला गेला होता, इथे कधीच नाही). आता srv2_momentum_reversal_strategy.py सारखाच, वरच्याच
        # hysteresis-संरक्षित `direction` वरून role/level_type काढला जातो — त्यामुळे hit-counting,
        # Breakout Entry ची दिशा, आणि Signal Log — तिन्ही सुसंगत राहतात.
        role = "SUPPORT" if direction == "BULLISH" else "RESISTANCE"
        # 🎓 Execution-testing मध्ये सापडवलेली गंभीर bug — rsi_value आधी फक्त "if entry_rsi_gate_enabled:"
        # च्या आतच ठरायचा, पण खाली (यशस्वी trade नंतरच्या Telegram संदेशात) कायम वापरला जायचा — RSI Gate
        # Dashboard वरून बंद केला की इथे NameError येऊन entire script क्रॅश व्हायचा, अगदी order
        # यशस्वीरित्या प्लेस झाल्यानंतरही (Naked leg, Telegram, पुढच्या levels साठीचा loop — सगळं तिथेच
        # अर्धवट थांबायचं). आता आधीच None ने सुरुवात — गेट बंद असेल तर संदेशातही तेच स्पष्ट दिसेल.
        rsi_value = None
        log_entry = {
            "symbol": symbol, "trade_date": trade_date, "signal_time": now,
            "level_type": f"DYNAMIC_SR_{role}_{timeframe_suffix}",
            "level_price": row["zone_low"], "hit_type": hit_type or "NO_HIT", "direction": direction if hit else "NONE",
            # 🎓 वापरकर्त्याने सापडवलेली bug — हा संदेश "level cross आढळला नाही" असायचा, पण प्रत्यक्ष
            # निकष (check_level_crossed वरचा docstring बघा) TOUCH किंवा GAP_THROUGH आहे — "cross" या
            # शब्दाने असं वाटायचं की entry साठी level पूर्ण ओलांडून पलीकडे बंद व्हावी लागते, जे खरं
            # नाही (नुसता स्पर्श पुरेसा आहे) — फक्त संदेशाचा शब्द चुकीचा होता, प्रत्यक्ष तर्कशास्त्र
            # (TOUCH रांगा log मध्ये दिसतात, फक्त RSI गेटने पुढे थांबवलेल्या) बरोबरच आहे.
            "ltp_at_signal": None, "trade_status": None, "reason": "level ला स्पर्श (touch) आढळला नाही (शेवटच्या candles मध्ये)" if not hit else "",
        }

        if not hit:
            cloud_db.save_signal_log(log_entry)
            continue

        if (now.hour, now.minute) >= (NO_NEW_ENTRY_AFTER_HOUR, NO_NEW_ENTRY_AFTER_MINUTE):
            log_entry["trade_status"] = "SKIPPED_TOO_LATE_FOR_NEW_ENTRY"
            log_entry["reason"] = f"{NO_NEW_ENTRY_AFTER_HOUR}:{NO_NEW_ENTRY_AFTER_MINUTE:02d} नंतर नवीन entry नाही"
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("कोणताही एक सिग्नल ... टार्गेट गाठल्यास बॉटने पुढील
        # ट्रेडिंग थांबवावे — आपला उद्देश प्रॉफिट कमावणे आहे, ट्रेड करणे नव्हे") — आज या bot चा (सर्व
        # symbols मिळून, याच trading_mode चा — PAPER/LIVE स्वतंत्र) कुठलाही खरा trade (Credit Spread किंवा
        # Naked) शुद्ध 'TARGET' ने बंद झाला असेल, तर उरलेल्या दिवसासाठी नवीन entry नाही (Breakout/
        # Directional सकट कुठलीही) — इतर सर्व गेट्सच्या आधी, जेणेकरून बाकीचे API/DB कॉल्स वाया जात नाहीत.
        # आधीच उघडे trades चालू राहतात. Shadow trades (source '_shadow' अंत्य) कधीच ट्रिगर होत नाहीत.
        # DB मधून तपासलं जातं (memory वर नाही), त्यामुळे bot restart झाला तरी नियम कायम राहतो.
        if stop_after_target_enabled:
            if target_hit_today is _NOT_CHECKED:
                target_hit_today = get_first_target_exit_today(
                    "dynamic_sr_instant", settings.get("trading_mode", "PAPER"), trade_date,
                )
            if target_hit_today is not None:
                hit_trade_id, hit_symbol, hit_exit_time, hit_pnl = target_hit_today
                pnl_text = f" (P&L ₹{hit_pnl:,.0f})" if hit_pnl is not None else ""
                log_entry["trade_status"] = "SKIPPED_TARGET_ALREADY_HIT_TODAY"
                log_entry["reason"] = (
                    f"आज {hit_symbol} चा trade {hit_trade_id} Target ने बंद झाला ({str(hit_exit_time)[11:16]}){pnl_text} — "
                    "'Target नंतर थांबवा' नियमानुसार आजचे नवीन trades बंद"
                )
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("Tya level war previous day che touches aahet,
        # kiwa level Breakout jhali mhanun trade hit jhala pahije, ashi simple condition Breakout
        # trade ka lagu kra, jast complex karu nka") — आधी Breakout Entry फक्त hit_count_so_far>=2
        # (आजचे दोन्ही touch आधीच झालेले) असेल तरच तपासला जायचा. पण प्रत्येक Dynamic S/R zone हा
        # आधीच बहुदिवसीय ऐतिहासिक price-clustering वरून तयार झालेला ("previous day touches" आधीच
        # गृहीत धरलेलं) — त्यामुळे "आजचे 2 hits आधी झालेच पाहिजेत" ही अतिरिक्त अट काढली. आता Breakout
        # Entry (5-मिनिट candle close, खालीच) प्रत्येक touch वर स्वतंत्रपणे तपासला जातो, hit_count_so_far
        # कितीही असो — फक्त "level breakout झाला का" हाच निकष. max-2-hits ची जुनी मर्यादा फक्त breakout
        # **न** आढळलेल्या (साध्या reversal) touches साठीच अजूनही लागू आहे (established behavior,
        # अपरिवर्तित).
        # 🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("Breakout sathi consolidation chi condition pn
        # remove kra") — price consolidation ("buildup") ही अट सुद्धा काढली — आता breakout मूळ
        # निकषावर: 5-मिनिट candle level पासून किमान buffer_pct% तरी पलीकडे निर्णायकपणे close झाला का
        # (`check_breakout_candle_close`). त्याआधीच्या candles मध्ये किंमत level जवळ किती वेळ "टिकून"
        # होती याचा पुरावा (`check_breakout_price_consolidation`) आता या bot साठी गरजेचा नाही (हे
        # function अजूनही MCX Futures च्या स्वतंत्र Breakout Entry साठी वापरलं जातं).
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute Breakout candle + Volume ashi
        # condition ठेवता yeil") — ऐच्छिक (डीफॉल्ट बंद) Volume Confirmation — चालू असेल तर,
        # candle-close अटीसोबतच breakout-candle चा volume त्याआधीच्या breakout_volume_lookback_candles
        # candles च्या सरासरीपेक्षा किमान breakout_volume_multiplier पट जास्त असावा लागतो
        # (`check_breakout_volume_confirmation`) — कमी-volume (संभाव्य fake/whipsaw) breakouts
        # गाळण्यासाठी.
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("option chain analysis oi snapshot every 5
        # minute save kele जातात tech yethe use krta yeil") — ऐच्छिक (डीफॉल्ट बंद) OI Confirmation —
        # `oi_snapshot_collector.py` ने दर 5 मिनिटांनी साठवलेला सर्वात अलीकडचा OI-Price signal
        # (`get_latest_oi_signal` — Put/Call Writing/Buying/Short-Covering/Long-Unwinding च्या
        # संयोगातून आधीच ठरलेला BULLISH/BEARISH/MIXED/NEUTRAL) breakout_direction शी जुळतो (किंवा
        # उलट दिशा "Weakening" असेल) तरच पास — established `check_oi_diff_entry_gate` (A1 Engine मध्ये
        # आधीच वापरलेलं) चाच पुनर्वापर, नवीन logic नाही. Index candles चा स्वतःचा "oi" column
        # (indices ना Open Interest नसतोच) इथे वापरलेला नाही — हा signal option chain (Call+Put OI)
        # वरून येतो.
        # (role वर आधीच hysteresis-संरक्षित `direction` वरून ठरलेला आहे — बघा वरची टिप्पणी.)
        # 🎓 वापरकर्त्याशी चर्चा करून सापडवलेली/सुधारलेली विसंगती ("5minute dynamic sr Breakout
        # jhalyanantr ch Breakout trade ghenyat yenar") — breakout confirm करणारे candles कायमच
        # 5-मिनिट असतात (वर), पण timeframe_choice="BOTH" (डीफॉल्ट) असेल तर pooled_levels मध्ये 1M
        # levels सुद्धा असतात — आधी त्यांच्यावरच्याही touch वर हाच 5-मिनिट-आधारित Breakout Entry
        # चालायचा, जे विसंगत आहे (1M level "तुटला" हे 5M candle close वरून ठरवणं चुकीचं). आता फक्त
        # timeframe_suffix=="5M" असलेल्या levels साठीच Breakout Entry तपासला जातो — 1M levels च्या
        # touches वर हा गेट पूर्णपणे वगळला जातो (established साध्या reversal-touch मार्गानेच जातात).
        hit_count_so_far, _, last_trade_time = cloud_db.get_zone_hits_today(
            symbol, row["zone_low"], trade_date, role=role,
        )
        is_breakout_trade = False
        breakout_actual_close_pct = breakout_actual_volume_ratio = breakout_oi_signal_used = None
        if entry_breakout_gate_enabled and timeframe_suffix == "5M":
            breakout_direction = "BEARISH" if role == "SUPPORT" else "BULLISH"
            # 🎓 "Breakout ची दिशा 5M close च्या बाजूवरून" (Dashboard सेटिंग, डीफॉल्ट बंद) — बघा
            # determine_breakout_direction_from_close(). ओलांडलं गेल्याचं आढळलं नाही तर वरची जुनी भूमिका-आधारित दिशा.
            if breakout_direction_from_close:
                crossed_direction = determine_breakout_direction_from_close(
                    row["zone_low"], todays_5m_candles_all, breakout_close_buffer_pct, breakout_cross_lookback_candles)
                if crossed_direction is not None:
                    breakout_direction = crossed_direction
            # 🎓 आता वरती (loop च्या आधी) प्रति-symbol एकदाच आणलेले candles पुन्हा वापरले जातात —
            # इथे स्वतंत्र API कॉल नाही (पहिल्यांदा वरचीच टिप्पणी बघा, breakout_catchup_hit).
            todays_5m_candles = todays_5m_candles_all
            candle_close_confirmed = check_breakout_candle_close(row["zone_low"], breakout_direction, todays_5m_candles, breakout_close_buffer_pct)
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — प्रत्यक्ष मोजलेलं buffer% (gate चं bool निकाल नाही,
            # Signal Log मध्ये नेमकं मूल्य दाखवण्यासाठी). level च्या ज्या बाजूला breakout अपेक्षित आहे
            # त्याच बाजूने अंतर मोजलं — उलट दिशेला close झाल्यास ऋण (negative) दिसेल.
            if todays_5m_candles:
                last_close = todays_5m_candles[-1]["close"]
                signed_diff = (last_close - row["zone_low"]) if breakout_direction == "BULLISH" else (row["zone_low"] - last_close)
                breakout_actual_close_pct = round(signed_diff / row["zone_low"] * 100, 4)
            volume_confirmed = (
                not breakout_volume_confirm_enabled
                or check_breakout_volume_confirmation(todays_5m_candles, breakout_volume_lookback_candles, breakout_volume_multiplier)
            )
            if breakout_volume_confirm_enabled:
                breakout_actual_volume_ratio = get_breakout_volume_ratio(todays_5m_candles, breakout_volume_lookback_candles)
            oi_confirmed = True
            if breakout_oi_confirm_enabled:
                breakout_oi_signal_used = get_latest_oi_signal(symbol)
                oi_confirmed = check_oi_diff_entry_gate(breakout_direction, breakout_oi_signal_used)
            # 🎓 "Breakout दोन्ही Supertrend च्या दिशेनेच" (Dashboard सेटिंग, डीफॉल्ट बंद) — बाकीच्या सर्व
            # अटी पूर्ण झाल्या असतील तरच (अनावश्यक API कॉल टाळण्यासाठी) 15M + 1H दिशा आणली जाते; दोन्ही
            # breakout च्या दिशेशी जुळाव्या, डेटा नसेल तर Breakout थांबतो.
            st_breakout_ok = True
            st_dir_15m = st_dir_1h = None
            if breakout_supertrend_filter_enabled:
                if candle_close_confirmed and volume_confirmed and oi_confirmed:
                    if not supertrend_directions_cache:
                        supertrend_directions_cache.append(fetch_trend_filter_directions(
                            access_token, symbol, now, supertrend_15m_period, supertrend_15m_multiplier,
                            supertrend_1h_period, supertrend_1h_multiplier,
                        ))
                    st_dir_15m, st_dir_1h = supertrend_directions_cache[0]
                    st_breakout_ok, _st_breakout_reason = check_breakout_supertrend_alignment(
                        breakout_direction, st_dir_15m, st_dir_1h)
                else:
                    st_breakout_ok = None  # तपासलंच नाही
            breakout_final_ok = bool(candle_close_confirmed and volume_confirmed and oi_confirmed
                                     and st_breakout_ok is True)
            log_entry["breakout_eval"] = build_breakout_eval_note(
                breakout_direction, row["zone_low"], todays_5m_candles[-1]["close"] if todays_5m_candles else None,
                breakout_actual_close_pct, breakout_close_buffer_pct, candle_close_confirmed,
                breakout_volume_confirm_enabled, breakout_actual_volume_ratio, breakout_volume_multiplier, volume_confirmed,
                breakout_oi_confirm_enabled, breakout_oi_signal_used, oi_confirmed,
                breakout_supertrend_filter_enabled, st_dir_15m, st_dir_1h, st_breakout_ok,
                breakout_direction_from_close, breakout_final_ok,
            )
            if breakout_final_ok:
                direction = breakout_direction
                log_entry["direction"] = direction
                is_breakout_trade = True
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("candle-close %, volume ratio, OI signal Signal Log
        # मध्ये स्वतंत्रपणे दाखवायचे") — फक्त enabled असलेल्या sub-gates चीच मूल्यं दिसतील; इथेच एकदाच
        # बनवलेला तयार तुकडा credit-spread आणि naked दोन्ही Breakout-reason ठिकाणी वापरला जातो.
        breakout_detail_parts = []
        if breakout_actual_close_pct is not None:
            breakout_detail_parts.append(f"candle close {breakout_actual_close_pct:+.3f}% (किमान {breakout_close_buffer_pct:.3f}% हवं)")
        if breakout_actual_volume_ratio is not None:
            breakout_detail_parts.append(f"Volume {breakout_actual_volume_ratio:.2f}x (किमान {breakout_volume_multiplier:.1f}x हवं)")
        if breakout_oi_signal_used is not None:
            breakout_detail_parts.append(f"OI Signal: {breakout_oi_signal_used}")
        breakout_detail_str = f" [{', '.join(breakout_detail_parts)}]" if breakout_detail_parts else ""
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Breakout Entry catch-up — बघा वरची
        # breakout_catchup_hit टिप्पणी) — हा "hit" खरा 1-मिनिट किंमत-स्पर्श नव्हता, फक्त breakout
        # तपासणीपुरता (5-मिनिट candle वरून) होता. Breakout ची पूर्ण अट (candle-close buffer%/
        # Volume/OI) शेवटी पूर्ण झाली नाही, तर हा "hit" कुठल्याही परिस्थितीत साध्या reversal
        # trade मध्ये (max-hits/RSI/PCR मार्गाने) पुढे जाऊ द्यायचा नाही — किंमत आधीच level पासून
        # दूर निघून गेलेली असू शकते, तिथे नुसता reversal-touch गृहीत धरणं चुकीचं ठरेल.
        if breakout_catchup_hit and not is_breakout_trade:
            log_entry["trade_status"] = "SKIPPED_BREAKOUT_CATCHUP_CONDITIONS_NOT_MET"
            log_entry["reason"] = (
                "5-मिनिट candle मध्ये level ओलांडलेलं आढळलं (नवीन 1-मिनिट touch न मिळताही, "
                f"catch-up तपासणी){breakout_detail_str}, पण Breakout Entry च्या पूर्ण अटी पूर्ण "
                "झाल्या नाहीत — हा touch खरा किंमत-स्पर्श नसल्याने साधा reversal trade सुद्धा घेतला नाही"
            )
            cloud_db.save_signal_log(log_entry)
            continue
        if hit_count_so_far >= max_hits_per_zone and not is_breakout_trade:
            log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
            log_entry["reason"] = f"आजच्या या zone साठी (याच role — support/resistance) कमाल {max_hits_per_zone} वेळा मर्यादा आधीच गाठलेली"
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Directional Flip on IV Breakout — बघा वरची
        # फाईल-टिप्पणी) — Breakout trade आधीच ठरलेला असेल (वर), तर हा block पूर्णपणे वगळला जातो
        # (दिशा आधीच ठरलेली आहे, दुसऱ्यांदा फ्लिप/तपासणी नको). आजचा IV गेल्या सरासरीपेक्षा खरंच जास्त
        # वाढलेला (मोजलेला, डेटा-गहाळ नाही) आढळला, तरच दिशा उलटते — डेटाच अनुपलब्ध/जुना असेल
        # (iv_change_pct is None, regime माहीतच नाही) तर पूर्वीसारखंच fail-safe skip, flip नाही.
        is_directional_trade = is_breakout_trade
        if entry_iv_gate_enabled and not is_directional_trade:
            iv_ok, iv_change_pct, iv_reason = check_iv_change_gate(symbol, iv_change_max_pct, iv_lookback_days, iv_marubozu_threshold)
            if not iv_ok:
                if iv_change_pct is None:
                    log_entry["trade_status"] = "SKIPPED_IV_GATE"
                    log_entry["reason"] = iv_reason
                    cloud_db.save_signal_log(log_entry)
                    continue
                direction = "BEARISH" if direction == "BULLISH" else "BULLISH"
                log_entry["direction"] = direction
                is_directional_trade = True

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — इथे (सगळे direction-निश्चित करणारे टप्पे — मूळ touch + IV-flip +
        # Breakout-flip — झाल्यावर, अंतिम `direction` वरच) तपासलं जातं, जेणेकरून कुठल्याही उगमाची
        # (reversal/directional/breakout) या दिशेची trade अडवली जाईल — RSI/PCR Gate च्याही आधी. फक्त
        # नवीन trades थांबतात, आधीच उघडलेले चालूच राहतात.
        if direction == "BULLISH" and not bullish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BULLISH_ENTRY_DISABLED"
            log_entry["reason"] = "Bullish Entry सेटिंग्जमधून बंद आहे"
            cloud_db.save_signal_log(log_entry)
            continue
        if direction == "BEARISH" and not bearish_entry_enabled:
            log_entry["trade_status"] = "SKIPPED_BEARISH_ENTRY_DISABLED"
            log_entry["reason"] = "Bearish Entry सेटिंग्जमधून बंद आहे"
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 "5 minute mdhe intraday new form support resistance strength 2x asalyas ... high probability che
        # nasatat" -- Level Strength Gate (Dashboard, डीफॉल्ट बंद). फक्त साध्या reversal trades साठी; Breakout/IV
        # (directional) वगळलेले. SKIPPED_WEAK_LEVEL हा no-hit status (cloud_db._NON_HIT_TRADE_STATUSES) --
        # level नंतर मजबूत झाल्यावर max-hits/cooldown आधीच खर्च झालेले नसावेत.
        if entry_min_level_strength_enabled and not is_directional_trade:
            strength_ok, strength_reason = check_level_strength_gate(
                row.get("strength"), row.get("formed_date"), now, min_level_strength, level_strength_new_levels_only)
            if not strength_ok:
                log_entry["trade_status"] = "SKIPPED_WEAK_LEVEL"
                log_entry["reason"] = strength_reason
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 "Huge slippages" -- Fast-Move Guard (Dashboard, डीफॉल्ट बंद): किंमत level कडे वेगाने येत असेल तर
        # साधा reversal entry नाही. Breakout/IV (directional) वगळलेले. SKIPPED_FAST_MOVE no-hit status.
        if entry_fast_move_guard_enabled and not is_directional_trade:
            fast_ok, fast_reason = check_fast_move_into_level(
                direction, todays_closes, fast_move_lookback_minutes, fast_move_threshold_pct)
            if not fast_ok:
                log_entry["trade_status"] = "SKIPPED_FAST_MOVE"
                log_entry["reason"] = fast_reason
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Minimum Level-Hold Duration Before Entry" —
        # बघा वरची count_consecutive_touch_minutes() ची टिप्पणी) — level ला दिवसाचा पहिलाच, ताजा
        # touch झाला असेल (शून्य किंवा फार कमी आधीचा buildup), तर तो क्षणिक noise/whipsaw असण्याची
        # शक्यता जास्त — किमान entry_min_hold_minutes इतकी मिनिटं सलग टिकून राहिलेला असेल तरच entry.
        # Directional (IV/Breakout) trades साठी वगळलेला — त्यांचं स्वतःचं वेगळं confirmation आधीच आहे.
        # held_minutes इथेच (गेट बंद असतानाही) कायम काढला जातो — पुढे Min-Hold Shadow ब्लॉकलाही
        # (बघा तिथली टिप्पणी) हाच वापरायचा आहे, entry_min_hold_gate_enabled वर अवलंबून नाही.
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय (मुद्दामच, code-review च्या सुरुवातीच्या सूचनेच्या
        # उलट) — GAP_THROUGH ला मुद्दामच सूट दिली नव्हती, ती काढली. सकाळी बाजार उघडताच gap-down/
        # gap-up झाला, तर तो आदल्या रात्रीच्या बातम्या/जागतिक संकेतांमुळे — पहिल्या काही मिनिटांत बाजार
        # अजून स्थिरावलेलाच नसतो, त्यामुळे असा gap "निर्णायक" न मानता उलट सगळ्यात जास्त अस्थिर, अपुष्ट
        # क्षण मानायला हवा — डेटाबेसमधल्या आधीच साठवलेल्या (मागच्या दिवसांच्या) level वर, कुठलीही
        # पडताळणी न होता थेट entry देणं, हेच मूळ backtest मध्ये सापडलेल्या "शून्य-buildup, जलद SL"
        # समस्येचीच पुनरावृत्ती ठरेल. म्हणून GAP_THROUGH साठीही held_minutes तोच (0, कारण hit candle
        # स्वतःच बफरमध्ये कधीच overlap होत नाही) राहतो, आणि गेट तोच नियम एकसमान लावतो — gap नंतर
        # किंमत त्या level जवळ खरोखर टिकून (TOUCH म्हणून) राहिल्याशिवाय entry होणारच नाही.
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5M आणि 15M levels ओव्हरलॅप/जवळ आले तर 15 मिनिट
        # strategy execute व्हावी, 5 मिनिट थांबावी") — फक्त 5M levels ची साधी reversal entry (Breakout/IV
        # directional नाही; 1M levels ना लागू नाही). 0.10% (डीफॉल्ट, Dashboard-configurable) च्या आत, दिशा
        # जुळणारा ACTIVE 15M level असेल, आणि 15M strategy या symbol साठी सक्रिय + याच trading_mode मध्ये +
        # ही दिशा चालू असेल, तरच 5M बाजूला होतो; 15M स्वतःच्या touch/नियमांनी तिथे trade घेतो (5M level आणि
        # 15M level मधलं अंतर 15M च्या touch सहनशीलतेपेक्षा जास्त असेल तर 15M त्याच्या स्वतःच्या level
        # वर किंमत पोहोचल्यावरच trade घेतो — तोवर कुणीच नाही, हे मान्य केलेलं). settings/DB वाचता आल्या
        # नाहीत तर 5M स्वतः trade घेतो (fail-open).
        if defer_to_15m_enabled and timeframe_suffix == "5M" and not is_directional_trade:
            overlap = find_overlapping_15m_level(all_zones, row["zone_low"], defer_to_15m_distance_pct, current_price, direction)
            if overlap is not None:
                ready_15m, not_ready_reason = is_15m_strategy_ready_for(symbol, direction, settings.get("trading_mode", "PAPER"))
                if ready_15m:
                    log_entry["trade_status"] = "SKIPPED_DEFERRED_TO_15M"
                    log_entry["reason"] = (
                        f"5M level {row['zone_low']:.2f} च्या {overlap[1]:.3f}% अंतरावर 15M level {overlap[0]:.2f} आहे "
                        f"(मर्यादा {defer_to_15m_distance_pct:.2f}%) — 15 मिनिट strategy स्वतःच्या touch/नियमांनुसार तिथे trade घेईल"
                    )
                    cloud_db.save_signal_log(log_entry)
                    # 🎓 5M थांबतो तेव्हा त्याचे उघडे trades लगेच बंद (वापरकर्त्याचा निर्णय) — भांडवल 15M साठी मोकळं.
                    try:
                        _all_closed, closed_ids, failed_ids = close_open_5m_positions(
                            access_token, symbol,
                            f"5M level {row['zone_low']:.2f} is within {defer_to_15m_distance_pct:.2f}% of 15M level {overlap[0]:.2f}; "
                            "5M stopped and its open trades were closed so the 15M strategy can take over.",
                        )
                    except Exception as e:
                        closed_ids, failed_ids = [], [("?", str(e))]
                    if closed_ids or failed_ids:
                        send_telegram_message(
                            f"🔀 <b>{symbol}: 5M → 15M हस्तांतरण</b>\n5M level {row['zone_low']:.2f} हा 15M level {overlap[0]:.2f} च्या जवळ आहे.\n"
                            f"बंद केलेले 5M trades: {len(closed_ids)}" + (f"\n⚠️ बंद होऊ शकले नाहीत: {len(failed_ids)}" if failed_ids else "")
                        )
                    continue

        held_minutes = count_consecutive_touch_minutes(row["zone_low"], todays_candle_records)
        # 🎓 "level ला आज पहिल्यांदा touch झाल्यावर 3 मिनिट hold अट, त्याच level च्या 2ऱ्या trade साठी नको" —
        # last_trade_time = याच level+role वर आज झालेला शेवटचा **खरा** trade attempt (नाकारलेला touch नाही,
        # म्हणून गेटने नाकारलेला touch "पहिला trade" मोजला जात नाही — पुढच्या मिनिटांतही गेट लागू राहतो).
        min_hold_applies = not (entry_min_hold_first_trade_only and last_trade_time is not None)
        if (entry_min_hold_gate_enabled and min_hold_applies and not is_directional_trade
                and held_minutes < entry_min_hold_minutes):
            log_entry["trade_status"] = "SKIPPED_MIN_HOLD_DURATION"
            log_entry["reason"] = f"Level फक्त {held_minutes} मिनिटं टिकून आहे (किमान {entry_min_hold_minutes} हवीत) — ताजा/अस्थिर touch"
            cloud_db.save_signal_log(log_entry)
            continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("1 hr Supertrend and 15 Minute Supertrend price donhi
        # supertrend chya khali aslyas stop Bullish trade, and vice versa") — Trend Filter, डीफॉल्ट बंद. फक्त साध्या
        # reversal trades साठी; Directional (Breakout/IV) trades वगळलेले (RSI/PCR प्रमाणेच). Supertrend दिशा
        # शेवटच्या पूर्ण candle ची; डेटा न मिळाल्यास trade अडवत नाही (fail-open).
        if entry_supertrend_filter_enabled and not is_directional_trade:
            if not supertrend_directions_cache:
                supertrend_directions_cache.append(fetch_trend_filter_directions(
                    access_token, symbol, now, supertrend_15m_period, supertrend_15m_multiplier,
                    supertrend_1h_period, supertrend_1h_multiplier,
                ))
            st_dir_15m, st_dir_1h = supertrend_directions_cache[0]
            st_ok, st_reason = check_supertrend_trend_filter(direction, st_dir_15m, st_dir_1h)
            if not st_ok:
                log_entry["trade_status"] = "SKIPPED_TREND_FILTER"
                log_entry["reason"] = f"{st_reason} [15M: {st_dir_15m}, 1H: {st_dir_1h}]"
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Gate — on/off) — RSI Gate आता Dashboard
        # वरून पूर्णपणे बंद करता येतो (उदा. फक्त S/R touch वरच trade घ्यायचं असेल तर). Directional
        # trade (IV breakout/Breakout Entry, वर) साठी मुद्दामच वगळलेला — RSI उंबरठे reversal-
        # गृहीतकासाठी tuned आहेत (उदा. RSI<40 = "oversold, वर bounce होईल"), breakout-continuation
        # साठी उलटा संकेत ठरेल.
        if entry_rsi_gate_enabled and not is_directional_trade:
            rsi_ok, rsi_value = check_instant_rsi_filter(candles_df, direction, rsi_support_max, rsi_resistance_min)
            if not rsi_ok:
                log_entry["trade_status"] = "SKIPPED_RSI_FILTER"
                log_entry["reason"] = f"RSI {rsi_value} दिशेशी जुळत नाही (Support<{rsi_support_max} / Resistance>{rsi_resistance_min} हवं होतं)"
                cloud_db.save_signal_log(log_entry)
                continue

        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PCR Gate — on/off) — दोन्ही trade-प्रकारांना
        # (Credit Spread + Naked) एकत्र लागू, पण आता Dashboard वरून पूर्णपणे बंदही करता येतो. बंद
        # नसेल तरच — डेटा गहाळ/जुना असल्यास सुरक्षिततेसाठी trade थांबवणे (fail-safe). Directional
        # trade साठी वगळलेला (वरचंच कारण — RSI Gate प्रमाणेच PCR उंबरठेही reversal-गृहीतकासाठी).
        if entry_pcr_gate_enabled and not is_directional_trade:
            pcr_ok, pcr_value, pcr_reason = check_pcr_gate(
                symbol, direction, settings["pcr_bullish_min"], settings["pcr_bearish_max"],
            )
            if not pcr_ok:
                log_entry["trade_status"] = "SKIPPED_PCR_GATE"
                log_entry["reason"] = pcr_reason
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — cooldown आता फक्त खऱ्या trade नंतरच सुरू होतो
        # (last_trade_time), नुसत्या नाकारलेल्या (RSI/PCR gate ने) touch मुळे नाही — आधी सलग
        # RSI-नाकारलेले touches सुद्धा घड्याळ रीसेट करत राहायचे, खरा trade कधीच न होता. Breakout
        # trade साठी वगळलेला — established design नुसार तो मुद्दामच लगेच (2ऱ्या SL/TSL नंतर लवकरच,
        # 5-मिनिट candle close होताच) यायला हवा, 30 मिनिटांची अतिरिक्त वाट नाही.
        if last_trade_time is not None and not is_breakout_trade:
            elapsed_minutes = (now - last_trade_time).total_seconds() / 60
            if elapsed_minutes < 30:
                log_entry["trade_status"] = "SKIPPED_COOLDOWN_30MIN"
                log_entry["reason"] = f"मागच्या trade ला फक्त {elapsed_minutes:.1f} मिनिटं झालीत (किमान 30 हवीत)"
                cloud_db.save_signal_log(log_entry)
                continue

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
        # kiman 15 minute same level war trade ghewu naye, cooldown") — वरचा 30-मिनिट cooldown
        # entry-signal-वेळेवर आधारित आहे (max-2-hits च्या आतल्या दुसऱ्या touch साठीही लागू व्हायला
        # हवा), पण याहून वेगळा, थेट exit-वेळेवर (live_trades.exit_time) आधारित हा गेट — त्याच exact
        # level वर आधीचा SL/TSL-प्रकारचा exit नक्की किती मिनिटांपूर्वी झाला हे स्वतंत्रपणे तपासतो —
        # whipsaw/fakeout नंतरचं आणखी एक थर संरक्षण. TARGET/इतर profitable exits ला लागू नाही.
        # Breakout trade साठी वगळलेला (established कारण वरच्याच cooldown प्रमाणे).
        sl_tsl_cooldown_minutes = settings.get("sl_tsl_cooldown_minutes", 15)
        if sl_tsl_cooldown_minutes > 0 and not is_breakout_trade:
            last_sl_tsl_exit = get_last_sl_tsl_exit_time(symbol, row["zone_low"], "dynamic_sr_instant", trade_date)
            if last_sl_tsl_exit is not None:
                elapsed_since_sl = (now - last_sl_tsl_exit).total_seconds() / 60
                if elapsed_since_sl < sl_tsl_cooldown_minutes:
                    log_entry["trade_status"] = "SKIPPED_SL_TSL_COOLDOWN"
                    log_entry["reason"] = f"याच level वर मागचा SL/TSL फक्त {elapsed_since_sl:.1f} मिनिटांपूर्वी लागला (किमान {sl_tsl_cooldown_minutes} हवीत)"
                    cloud_db.save_signal_log(log_entry)
                    continue

        # 🎓 "एका वेळी एकच position (5M किंवा 15M)" — 15M ची position (याच symbol, याच mode) उघडी असताना 5M नवीन
        # entry घेत नाही (भांडवल एकच). फक्त हा नियम (defer_to_15m_enabled) चालू असतानाच.
        if defer_to_15m_enabled and open_15m_position_exists(symbol, settings.get("trading_mode", "PAPER")):
            log_entry["trade_status"] = "SKIPPED_15M_POSITION_OPEN"
            log_entry["reason"] = "15M strategy ची position अजून उघडी आहे — एका वेळी एकच position (5M किंवा 15M)"
            cloud_db.save_signal_log(log_entry)
            continue

        if has_open_trade_from_source(symbol, "dynamic_sr_instant"):
            log_entry["trade_status"] = "SKIPPED_PREVIOUS_POSITION_STILL_OPEN"
            log_entry["reason"] = "आधीची position (या strategy ची, कुठल्याही level वरची) अजून बंद झालेली नाही"
            cloud_db.save_signal_log(log_entry)
            continue

        # --- सर्व अटी पूर्ण! Entry ---
        expiry_index = 1 if is_todays_expiry_day(access_token, symbol) else 0
        raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol, expiry_index=expiry_index)
        if not raw_chain:
            return f"{symbol}: Option chain मिळाली नाही ({chain_status})"
        underlying_price = raw_chain[0].get("underlying_spot_price")
        strike_step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
        atm_strike = round(underlying_price / strike_step) * strike_step
        log_entry["ltp_at_signal"] = underlying_price

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Naked Option Buy आणि Credit Spread दोन्ही independently
        # optional असायला पाहिजेत — कमी कॅपिटल असलेला user फक्त naked करणं पसंत करतो") — आधी credit
        # spread नेहमीच (toggle शिवाय) चालायचा, फक्त naked ऐच्छिक होता (naked_enabled). आता दोन्ही
        # स्वतंत्रपणे on/off करता येतात — हा नवीन credit_spread_enabled (डीफॉल्ट True, backward-compatible).
        credit_spread_enabled = settings.get("credit_spread_enabled", True)
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (PAPER/LIVE टॉगल + per-strategy Broker Selection) — आधी
        # इथे "कुठलेही broker_accounts नोंदवलेले असतील तर सर्व सक्रिय accounts वर replicate" असं होतं
        # (म्हणजे कुठल्याही एका strategy साठी account जोडला की सगळ्याच bots ला लागू व्हायचं) — आता
        # settings मधल्याच trading_mode/broker_account_ids वरून (Bot Dynamic SR Algo वरून वापरकर्त्याने
        # याच strategy+symbol साठी स्पष्ट निवडलेले) — रिकामी यादी (डीफॉल्ट) = जुनंच शुद्ध Upstox वर्तन.
        # credit_spread_enabled=False असतानाही naked trade ला हेच trading_mode/broker_account_ids
        # लागतात, म्हणून आता credit-spread-specific block च्या आधीच वाचलेले.
        trading_mode = settings.get("trading_mode", "PAPER")
        broker_account_ids = settings.get("broker_account_ids") or []

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("trade entry reason same disat aahe, actually trade 3
        # ha Breakout trade aahe") — Performance Report च्या Entry Reason स्तंभात हा भेद दिसावा
        # म्हणून live_trades मध्येच कायमचा साठवला जातो (आधी फक्त Signal Log च्या reason मध्ये होता,
        # जो Trade Log/PDF शी कधीच जोडलेला नव्हता).
        entry_reason_tag = "BREAKOUT_ENTRY" if is_breakout_trade else ("IV_BREAKOUT_DIRECTIONAL" if is_directional_trade else None)

        spread_result = None
        defer_spread_disabled_log = False
        trade_status = ""
        if credit_spread_enabled:
            spread_result = select_credit_spread_itm(
                raw_chain, direction, atm_strike, step=strike_step,
                itm_depth_points=settings["itm_depth_points"], hedge_width_points=settings["hedge_width_points"],
            )
            if spread_result is None:
                log_entry["trade_status"] = "STRATEGY_SELECTION_FAILED"
                cloud_db.save_signal_log(log_entry)
                continue

            # 🎓 code-review द्वारे सापडवलेली bug (Min-Hold Shadow जोडताना, OTM Shadow मध्येही आधीपासूनच
            # असलेली) — शॅडो trades (खाली, दोन्ही) खऱ्या ITM trade च्या प्रत्यक्ष यश/अपयशाची पर्वा न
            # करता फायर व्हायचे — फक्त strike-selection (spread_result is not None) यशस्वी झालं की
            # पुरे होतं, प्रत्यक्ष ऑर्डर broker-कडून नाकारला/अयशस्वी झाला तरीही. यामुळे "तात्काळ entry
            # वि. confirmed entry" तुलना अशा सिग्नल्सनी दूषित व्हायची जिथे खरा trade मुळात उघडलाच नाही.
            # आता real_trade_succeeded दोन्ही मार्गांसाठी (multi-account: किमान एक account यशस्वी;
            # single-account: open_multi_leg_trade चा bool परिणाम) स्पष्टपणे काढून, खालच्या दोन्ही
            # शॅडो ब्लॉक्सना त्यावरच अट घातलेली आहे.
            real_trade_succeeded = False
            if broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                results, factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=spread_result, base_lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,  # 🎓 Target आता trading_engine.py च्या evaluate_point_spot_exit मध्येच ठरतं
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    account_ids=broker_account_ids, entry_reason_tag=entry_reason_tag,
                    direction=direction, is_directional_trade=is_directional_trade,
                )
                trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
                if factory_errors:
                    trade_status += " | वगळलेले: " + "; ".join(factory_errors)
                real_trade_succeeded = any(r.get("ok") for r in results)
            else:
                trade_result, trade_response = open_multi_leg_trade(
                    access_token, symbol, spread_result, lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    entry_reason_tag=entry_reason_tag, direction=direction, is_directional_trade=is_directional_trade,
                )
                real_trade_succeeded = trade_result
                # 🎓 code-review द्वारे सापडवलेली bug (बघा trading_engine.format_trade_result() ची
                # टिप्पणी) — open_multi_leg_trade() चं दुसरं मूल्य dict असतं, plain string नाही —
                # raw dict signal_log.trade_status (TEXT column) मध्ये साठवायचा प्रयत्न केला की
                # DB insert चुपचाप अपयशी ठरायचा (except-सर्व-गिळणारं wrapper), आणि नेमकी entry-
                # क्षणाचीच signal_log रांग हरवायची.
                trade_status = format_trade_result(trade_result, trade_response)
            log_entry["trade_status"] = trade_status
            # 🎓 Directional trade (IV Breakout Gate — दिशा-flip, किंवा नवीन Breakout Entry) असल्यास
            # Signal Log मध्येच स्पष्ट नोंद — नंतर Performance Report/Signal Log मधून reversal विरुद्ध
            # directional trades वेगळे शोधता यावेत.
            if is_breakout_trade:
                log_entry["reason"] = f"Directional (trend-continuation) trade — Breakout Entry (5-मिनिट candle close, buffer% सह){breakout_detail_str}, RSI/PCR Gate वगळले"
            elif is_directional_trade:
                log_entry["reason"] = f"Directional (trend-continuation) trade — IV breakout ({iv_change_pct:+.1f}%), RSI/PCR Gate वगळले"
            cloud_db.save_signal_log(log_entry)

            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (ITM वि. OTM Credit Spread — "profit loss
            # आणि charges विचारात घेऊन कुठला strike फायदेशीर, OTM निवडावा का" यावर चर्चा, नंतर
            # "आधी 5-Min Instant Trader वर सुरू करा") — जुन्या expired तारखांचा actual option
            # premium डेटा Upstox कडून मिळत नसल्याने खरा historical backtest शक्य नाही (बघा
            # backtest.py ची स्वतःचीच मर्यादा-टिप्पणी) — त्याऐवजी हे forward-test: खऱ्या (ITM) trade
            # सोबतच, याच सिग्नलवर, एक स्वतंत्र निव्वळ PAPER-only OTM पर्याय
            # (select_credit_spread_fixed_strikes()) समांतर लॉग होतो — पूर्णपणे वेगळ्याच
            # source="dynamic_sr_instant_otm_shadow" ने, त्यामुळे मूळ strategy च्या PAPER/LIVE
            # आकडेवारीत (Performance Report, Kill Switch, max-trades) कधीच मिसळत नाही — फक्त
            # निरीक्षण/तुलनेसाठी. डीफॉल्ट बंद, आणि सुरुवातीला (वापरकर्त्याच्या स्पष्ट सूचनेनुसार)
            # फक्त "5M" touches पुरतंच मर्यादित — 1M वर अजून नाही.
            if settings.get("otm_shadow_enabled", False) and timeframe_suffix == "5M" and real_trade_succeeded:
                try:
                    otm_spread_result = select_credit_spread_fixed_strikes(
                        raw_chain, direction, atm_strike, step=strike_step,
                        strikes_otm=int(settings.get("otm_shadow_strikes_count", 2)),
                        hedge_width_points=settings["hedge_width_points"],
                    )
                    if otm_spread_result is not None:
                        open_multi_leg_trade(
                            access_token, symbol, otm_spread_result, lots=lots, lot_size=lot_size,
                            sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                            product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                            sl_pct_of_credit=100, source="dynamic_sr_instant_otm_shadow",
                            entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix,
                            entry_spot_price=underlying_price, entry_reason_tag=entry_reason_tag,
                            direction=direction, is_directional_trade=is_directional_trade,
                        )
                except Exception as exc:
                    print(f"⚠️ OTM Shadow trade अयशस्वी (मूळ ITM trade वर परिणाम नाही) — {symbol}: {exc}")

            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Shadow entry PDF मध्ये दिसायला पाहिजे, 10
            # दिवस forward test करतो" — Min-Hold Duration Gate प्रत्यक्ष वापरण्याआधी, OTM Shadow
            # च्याच सुरक्षित पॅटर्नने forward-test) — मूळ (ITM) trade सोबतच, याच सिग्नलवर (RSI/PCR/
            # Cooldown/Max-Hits आधीच पार केलेले, वर) — फक्त entry_min_hold_minutes इतका वेळ level
            # त्याच क्षणी आधीच टिकून होता (held_minutes, वर) तरच, एक स्वतंत्र, निव्वळ PAPER shadow
            # trade समांतर नोंदवला जातो. entry_min_hold_gate_enabled (blocking गेट, वर) पासून
            # पूर्णपणे स्वतंत्र — तो बंद असला (जुनं वर्तन 100% तसंच) तरीही हा शॅडो चालू शकतो, फक्त
            # निरीक्षणासाठी. Directional trades साठी वगळलेला (गेट प्रमाणेच). आधीच उघडलेला शॅडो trade
            # असेल तर पुन्हा stack होऊ नये म्हणून has_open_trade_from_source तपासणी — त्याच exact
            # spread_result (ITM structure) चा पुनर्वापर — इथे फक्त timing (कधी शिरायचं) वेगळी आहे,
            # strike-निवड नाही (त्यासाठी OTM Shadow, वर, वेगळाच आहे).
            # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — GAP_THROUGH ला इथेही सूट नाही (बघा वरच्या
            # Gate च्या टिप्पणीतलं कारण — सकाळी market-open gap सारखा अस्थिर, अपुष्ट क्षण शॅडोतही
            # "confirmed entry" म्हणून मोजला जाऊ नये).
            if (min_hold_shadow_enabled and real_trade_succeeded and not is_directional_trade
                    and held_minutes >= entry_min_hold_minutes
                    and not has_open_trade_from_source(symbol, "dynamic_sr_instant_min_hold_shadow")):
                try:
                    open_multi_leg_trade(
                        access_token, symbol, spread_result, lots=lots, lot_size=lot_size,
                        sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                        product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                        sl_pct_of_credit=100, source="dynamic_sr_instant_min_hold_shadow",
                        entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix,
                        entry_spot_price=underlying_price, entry_reason_tag=entry_reason_tag,
                        direction=direction,
                    )
                except Exception as exc:
                    print(f"⚠️ Min-Hold Shadow trade अयशस्वी (मूळ ITM trade वर परिणाम नाही) — {symbol}: {exc}")
        else:
            log_entry["trade_status"] = "SKIPPED_CREDIT_SPREAD_DISABLED"
            log_entry["reason"] = "credit_spread_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
            # 🎓 entry-gate review मध्ये सापडलेली bug — naked-only मोडमध्ये (credit_spread_enabled=False)
            # naked trade चा निकाल कधीच signal_log मध्ये जायचा नाही, फक्त हा SKIPPED_* 'no-action' शिक्का
            # जायचा — त्यामुळे 30-मिनिट cooldown / "पहिला trade" गेट / max-hits ला खरा trade दिसायचाच
            # नाही. naked चालणार असेल तर ही नोंद खाली naked निकालासह (खरा trade_status घेऊन) साठवली जाते.
            defer_spread_disabled_log = bool(settings.get("naked_enabled", True))
            if not defer_spread_disabled_log:
                cloud_db.save_signal_log(log_entry)
            print(f"ℹ️ Credit Spread trade बंद आहे (credit_spread_enabled=False, settings — symbol={symbol}, strategy=1m_instant)")

        naked_status = ""
        naked_result = None
        # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("naked trade execute झाला नाही") सोडवण्यासाठी जोडलेली
        # सुधारणा — आधी हे फक्त print() (फक्त GitHub Actions/VPS logs मध्ये दिसायचं) होतं, आता
        # signal_log मध्येही नोंदवलं जातं — त्यामुळे Dashboard वरच्या Market Zones → Signal Log
        # मध्ये (कुठल्याही log-access शिवाय) नेमकं कारण दिसेल.
        naked_diag_entry = dict(log_entry)
        if settings.get("naked_enabled", True):
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Credit Spread income strategy साठी ITM
            # श्रेयस्कर, Naked Option स्वस्त 'lottery' buy साठी बरेचदा OTM श्रेयस्कर — दोन्हीसाठी एकच
            # setting असणं चुकीचं") — आधी हेच itm_depth_points (Credit Spread चं) naked leg साठीही
            # वापरलं जायचं. आता स्वतंत्र naked_itm_depth_points — नसेल (जुनी, अजून customize न केलेली
            # नोंद) तर fallback म्हणून जुनाच itm_depth_points (backward-compatible, वर्तन बदलत नाही).
            naked_itm_depth_points = settings.get("naked_itm_depth_points", settings["itm_depth_points"])
            naked_result = select_naked_option_itm(
                raw_chain, direction, atm_strike, itm_depth_points=naked_itm_depth_points, step=strike_step,
                hedge_enabled=settings.get("naked_hedge_enabled", False),
                hedge_width_points=settings.get("naked_hedge_width_points", 150),
            )
            if naked_result is None:
                naked_diag_entry["trade_status"] = "SKIPPED_NAKED_STRIKE_NOT_FOUND"
                naked_diag_entry["reason"] = (
                    f"Naked trade साठी आवश्यक ITM strike (atm={atm_strike}, डेप्थ "
                    f"{naked_itm_depth_points}) raw_chain मध्ये सापडला नाही"
                )
                cloud_db.save_signal_log(naked_diag_entry)
                print(f"⚠️ {naked_diag_entry['reason']} — symbol={symbol}, direction={direction}")
        else:
            naked_diag_entry["trade_status"] = "SKIPPED_NAKED_DISABLED"
            naked_diag_entry["reason"] = "naked_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
            cloud_db.save_signal_log(naked_diag_entry)
            print(f"ℹ️ Naked trade बंद आहे (naked_enabled=False, settings — symbol={symbol}, strategy=1m_instant)")
        if naked_result is not None:
            if broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                naked_results, naked_factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=naked_result, base_lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    account_ids=broker_account_ids, entry_reason_tag=entry_reason_tag,
                    direction=direction, is_directional_trade=is_directional_trade,
                )
                naked_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in naked_results) or "कुठलाही account उपलब्ध नाही"
            else:
                naked_ok, naked_response = open_multi_leg_trade(
                    access_token, symbol, naked_result, lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    entry_reason_tag=entry_reason_tag, direction=direction, is_directional_trade=is_directional_trade,
                )
                # 🎓 बघा वरची credit-spread ब्लॉकमधली format_trade_result() ची टिप्पणी — इथेही तोच
                # dict-as-string bug (Telegram संदेशात raw dict दिसायचा, DB write नसली तरी).
                naked_status = format_trade_result(naked_ok, naked_response)

        # 🎓 naked-only मोड (बघा वरची टिप्पणी) — naked trade ने प्रत्यक्ष order प्रयत्न केला असेल तर तोच
        # निकाल (उदा. "OPENED") खरा trade_status म्हणून signal_log मध्ये; नाहीतर (strike सापडला नाही / naked
        # बंद) पूर्वीचाच SKIPPED_CREDIT_SPREAD_DISABLED शिक्का, पण naked निदान-नोंदीनंतर.
        if defer_spread_disabled_log:
            if naked_result is not None and naked_status:
                log_entry["trade_status"] = naked_status
                log_entry["reason"] = "credit_spread_enabled=False — फक्त Naked Option trade (निकाल trade_status मध्ये)"
            cloud_db.save_signal_log(log_entry)

        level_label = "Support" if direction == "BULLISH" else "Resistance"
        hit_label = "थेट स्पर्श" if hit_type == "TOUCH" else "⚡ Gap ने उडी मारून ओलांडला"
        if is_breakout_trade:
            rsi_display = f"📈 Breakout Entry (5-मिनिट candle close, buffer% सह){breakout_detail_str} — RSI/PCR Gate वगळले."
        elif is_directional_trade:
            rsi_display = f"📈 Directional trade (IV breakout {iv_change_pct:+.1f}%) — RSI/PCR Gate वगळले."
        elif entry_rsi_gate_enabled:
            rsi_display = f"RSI {rsi_value}."
        else:
            rsi_display = "RSI Gate बंद (तपासलं नाही)."
        naked_line = f"Naked Option: {naked_result.get('strategy', direction)} — {naked_status}\n" if naked_result is not None else ""
        # 🎓 credit_spread_enabled=False असेल (spread_result=None) तर ही ओळच वगळली जाते — "Credit
        # Spread बंद आहे" असं दाखवण्यापेक्षा, ती trade प्रकारच झालाच नाही हे संदेशातून स्पष्ट व्हावं.
        credit_spread_line = f"Credit Spread: {spread_result.get('strategy', direction)} — {trade_status}\n" if spread_result is not None else ""
        # 🎓 Breakout Entry हा max-2-hits च्या पलीकडचा, वेगळा (तिसरा) trade आहे -- "X/2 वा hit" हा
        # शीर्षक-भाग breakout साठी दिशाभूल करणारा ठरेल, म्हणून वेगळा हेडर.
        hit_label_header = "🎯 Breakout Entry" if is_breakout_trade else f"🎯 Dynamic S/R Cross (आजचा {hit_count_so_far + 1}/{max_hits_per_zone} वा hit)"
        message = (
            f"{hit_label_header} <b>{symbol} ({timeframe_suffix})!</b>\n"
            f"{level_label} {row['zone_low']:.2f} (strength {row['strength']:.0f}) — {hit_label} (≈{approx_price:.2f}). {rsi_display}\n"
            + credit_spread_line
            + naked_line
            + f"वेळ: {now.strftime('%H:%M:%S')}"
        )
        send_telegram_message(message)
        # 🎓 credit_spread_enabled=False असताना trade_status रिकामा असतो — naked_status (असल्यास)
        # किंवा स्पष्ट "both disabled" संदेश दाखवला जातो, रिकामी ओळ नाही.
        combined_status = trade_status or naked_status or "कुठलाही trade प्रकार सक्रिय नाही (credit_spread_enabled व naked_enabled दोन्ही बंद)"
        outcomes.append(f"{level_label} {row['zone_low']:.2f} ({timeframe_suffix}, {hit_type}) -> {combined_status}")

    if not outcomes:
        return f"{symbol}: सद्य 1-मिनिट candles मध्ये कुठलाही साठवलेला Dynamic S/R level (1M/5M) cross झाला नाही"
    return f"{symbol}: 🎯 " + "; ".join(outcomes)


def run_all_symbols(token, symbols):
    """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — trade_monitor.py प्रमाणेच प्रत्येक symbol स्वतंत्रपणे
    try/except मध्ये असायला हवा होता, पण आधी थेट `__main__` मध्ये एकच बिनसंरक्षित loop होता — एका
    symbol मध्ये अनपेक्षित exception (उदा. SQLite "database is locked", network glitch) आलं की
    उरलेले symbols त्याच cycle मध्ये कधीच तपासलेच जायचे नाहीत (loop तिथेच थांबायचा), आणि हे function
    कॉल करणाऱ्या कडचा write_heartbeat() सुद्धा कधीच पोहोचायचा नाही — कुठलाही Telegram अलर्टही नाही,
    म्हणजे bot शांतपणे तास-न्-तास "मृत" राहू शकत होता, कुणालाही न कळता. आता स्वतंत्र function (test
    करता यावं म्हणून) — प्रत्येक symbol वेगळा, एकाची चूक बाकीच्यांना अडवत नाही, अपयशी झाल्यास
    Telegram अलर्ट. रिटर्न: किमान एक symbol यशस्वी झाला का (heartbeat लिहायचा का ठरवण्यासाठी)."""
    any_symbol_succeeded = False
    for symbol in symbols:
        try:
            print(process_symbol(token, symbol.strip()))
            any_symbol_succeeded = True
        except Exception as e:
            notify_error("dynamic_sr_instant_trader", f"{symbol.strip()}: {e}")
            print(f"⚠️ {symbol.strip()}: अनपेक्षित त्रुटी — {e}")
    return any_symbol_succeeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — इथला डीफॉल्ट आता refresh_market_zones.py सारखाच
    # तिन्ही symbols — प्रत्यक्ष कोणत्या symbol वर trade घ्यायचा हे आता process_symbol() च्या आतल्या
    # symbol_enabled सेटिंगवरून ठरतं (Bot Dynamic SR Algo पानावरून, उपलब्ध भांडवलानुसार), या CLI
    # यादीवरून नाही — त्यामुळे VPS crontab मध्ये --symbols बदलावं लागत नाही.
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    args = parser.parse_args()

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Duplicate-Order Protection, गंभीर
    # यादीतला पाचवा मुद्दा) — VPS crontab वर दर १ मिनिटाला चालणारी ही script मंद network/retry
    # मुळे १ मिनिटापेक्षा जास्त वेळ घेऊ शकते; अशा वेळी cron ची पुढची invocation समांतर सुरू होऊन
    # डुप्लिकेट (खरे) ऑर्डर पाठवू शकते. आधीचीच invocation अजून चालू असेल, तर इथेच थांबतो.
    try:
        with ProcessLock("dynamic_sr_instant_trader"):
            init_sqlite_db()
            cloud_db.init_cloud_table()
            token = cloud_db.get_effective_upstox_token(args.token)
            if not token:
                print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
                exit(1)
            any_symbol_succeeded = run_all_symbols(token, args.symbols.split(","))
            if any_symbol_succeeded:
                write_heartbeat("dynamic_sr_instant_trader")  # 🎓 Production-readiness सुधारणा — याआधी हे script कधीच heartbeat नोंदवत नव्हतं
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Crash Recovery / DB Backup) —
            # आधी हे फक्त Dashboard उघडं असतानाच चालायचं; VPS crontab वर दिवसांदिवस Dashboard न
            # उघडताही चालणाऱ्या या bot कडून आता दर तासाला (Google Drive configured असेल तरच) आपोआप.
            run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        print(f"⏭️ मागची invocation अजून चालू आहे, ही वगळली — डुप्लिकेट ऑर्डर टाळण्यासाठी ({e})")
