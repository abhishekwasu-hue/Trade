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

🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "Max 2 trade on same level hit, he
honar donhi sl or tsl hit jhalet, ani nantr jar Breakout buildup and 5 minute candle closed happen
then take entry in the same direction") — `entry_breakout_gate_enabled` (डीफॉल्ट बंद) — established
max-2-hits च्या पलीकडचा, तिसरा trade. अट: (१) आजचे दोन्ही touch (max-2-hits) आधीच झालेले (हाच "A" —
signal_log वरचा hit_count), (२) breakout-candle च्या आधीच्या काही 5-मिनिट candles मध्ये price level
च्या जवळच (tolerance% च्या आत) consolidate झालेला — हाच "buildup" चा price-action पुरावा (हाच "C" —
`check_breakout_price_consolidation`, कुठलाही trade-outcome/indicator लागत नाही, फक्त candle close
किमती), आणि (३) एक 5-मिनिट candle त्या level च्या पलीकडे (breakout-दिशेने — मूळ 2 trades च्या
**उलट**) निर्णायकपणे close झाला (नुसता touch नाही). 🎓 वापरकर्त्याने सापडवलेली मर्यादा — आधीची
आवृत्ती `live_trades` मधले actual CLOSED SL/TSL trades शोधायची, त्यामुळे जर IV/RSI/PCR Gate ने आधीचे
touches block केले (trade कधीच open न होता), तर buildup कधीच खरं ठरायचं नाही — आता पूर्णपणे
price-data वरून (कुठल्याही gate/trade-outcome वर अवलंबून नाही), त्यामुळे हा problem राहत नाही. तिन्ही
अटी पूर्ण झाल्या तरच breakout-दिशेने 3रा trade — RSI/PCR Gate (directional trade असल्याने, IV-flip
सारखंच) आणि 30-मिनिट Cooldown (मुद्दामच लगेच यायला हवं म्हणून) दोन्ही वगळलेले.
"""
import argparse

import pandas as pd

import cloud_db
from config import get_ist_now, DB_PATH
from database import init_sqlite_db, has_open_trade_from_source, get_last_sl_tsl_exit_time, run_auto_backup_if_due
from notifications import send_telegram_message, write_heartbeat, notify_error
from signals import calculate_rsi
from oi_analysis import check_pcr_gate, check_iv_change_gate
from process_lock import ProcessLock, ProcessLockHeld
from strategy import select_credit_spread_itm, select_naked_option_itm
from trading_engine import open_multi_leg_trade
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


def check_breakout_candle_close(level, breakout_direction, candles_5m):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "Breakout buildup and 5 minute
    candle closed happen then take entry in the same direction") — नुकताच पूर्ण झालेला (शेवटचा,
    आजच्याच दिवसाचा) 5-मिनिट candle त्या level च्या पलीकडे निर्णायकपणे **close** झाला आहे का (नुसता
    touch/wick नाही, candle close) — breakout_direction नुसार (BULLISH = level च्या वर close,
    BEARISH = level च्या खाली close). candles_5m: [{"close":..}, ...] (जुनं ते नवीन क्रमाने, फक्त
    आजचेच). रिटर्न: bool"""
    if not candles_5m:
        return False
    last_close = candles_5m[-1]["close"]
    if breakout_direction == "BULLISH":
        return last_close > level
    return last_close < level


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
    entry_breakout_gate_enabled = settings.get("entry_breakout_gate_enabled", False)
    breakout_lookback_candles = settings.get("breakout_lookback_candles", 12)
    breakout_tolerance_pct = settings.get("breakout_tolerance_pct", 0.30)
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

    outcomes = []
    for row, timeframe_suffix in pooled_levels:
        hit, hit_type, approx_price = check_level_crossed(row["zone_low"], recent_candles)

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

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "Max 2 trade on same level
        # hit, he honar donhi sl or tsl hit jhalet, ani nantr jar Breakout buildup and 5 minute
        # candle closed happen then take entry in the same direction") — max-2-hits तपासणी आता
        # इतर सर्व gates च्याही आधी (RSI/PCR/IV Gate ला लागू करायचं की वगळायचं हे ठरवण्यासाठी).
        # hit_count_so_far>=2 असेल तर established behavior (skip) चालूच राहतो — Breakout Gate चालू
        # असेल आणि "buildup" (A: hit_count_so_far>=2 आधीच इथे, + C: price consolidation, बघा वरची
        # फाईल-टिप्पणी) + 5-मिनिट candle त्या level पलीकडे (breakout-दिशेने — मूळ 2 trades च्या उलट)
        # close झाला, तरच हा तिसरा, वेगळा (max-2 च्या पलीकडचा) trade घेतला जातो.
        # (role वर आधीच hysteresis-संरक्षित `direction` वरून ठरलेला आहे — बघा वरची टिप्पणी.)
        hit_count_so_far, _, last_trade_time = cloud_db.get_zone_hits_today(
            symbol, row["zone_low"], trade_date, role=role,
        )
        is_breakout_trade = False
        if hit_count_so_far >= 2:
            if entry_breakout_gate_enabled:
                breakout_direction = "BEARISH" if role == "SUPPORT" else "BULLISH"
                candles_5m_df = fetch_candles(access_token, symbol, current_spot=0, interval="5minute", lookback_days=1)
                todays_5m_candles = []
                if candles_5m_df is not None and not candles_5m_df.empty:
                    candles_5m_df = candles_5m_df.copy()
                    candles_5m_df["_date"] = candles_5m_df["timestamp"].dt.date
                    todays_5m_candles = candles_5m_df[candles_5m_df["_date"] == today_date].to_dict("records")
                if (check_breakout_price_consolidation(row["zone_low"], todays_5m_candles, breakout_lookback_candles, breakout_tolerance_pct)
                        and check_breakout_candle_close(row["zone_low"], breakout_direction, todays_5m_candles)):
                    direction = breakout_direction
                    log_entry["direction"] = direction
                    is_breakout_trade = True
            if not is_breakout_trade:
                log_entry["trade_status"] = "SKIPPED_MAX_2_HITS_REACHED"
                log_entry["reason"] = "आजच्या या zone साठी (याच role — support/resistance) कमाल 2 वेळा मर्यादा आधीच गाठलेली"
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

            if broker_account_ids:
                from trading_engine import execute_trade_on_all_accounts
                results, factory_errors = execute_trade_on_all_accounts(
                    symbol=symbol, strategy_result=spread_result, base_lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,  # 🎓 Target आता trading_engine.py च्या evaluate_point_spot_exit मध्येच ठरतं
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    account_ids=broker_account_ids, entry_reason_tag=entry_reason_tag,
                )
                trade_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in results) or "कुठलाही account उपलब्ध नाही"
                if factory_errors:
                    trade_status += " | वगळलेले: " + "; ".join(factory_errors)
            else:
                trade_result, trade_status = open_multi_leg_trade(
                    access_token, symbol, spread_result, lots=lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    entry_reason_tag=entry_reason_tag,
                )
            log_entry["trade_status"] = trade_status
            # 🎓 Directional trade (IV Breakout Gate — दिशा-flip, किंवा नवीन Breakout Entry) असल्यास
            # Signal Log मध्येच स्पष्ट नोंद — नंतर Performance Report/Signal Log मधून reversal विरुद्ध
            # directional trades वेगळे शोधता यावेत.
            if is_breakout_trade:
                log_entry["reason"] = "Directional (trend-continuation) trade — Breakout Entry (price consolidation + 5-मिनिट candle close), RSI/PCR Gate वगळले"
            elif is_directional_trade:
                log_entry["reason"] = f"Directional (trend-continuation) trade — IV breakout ({iv_change_pct:+.1f}%), RSI/PCR Gate वगळले"
            cloud_db.save_signal_log(log_entry)
        else:
            log_entry["trade_status"] = "SKIPPED_CREDIT_SPREAD_DISABLED"
            log_entry["reason"] = "credit_spread_enabled=False (Bot Dynamic SR Algo सेटिंग्जमध्ये बंद)"
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
            naked_result = select_naked_option_itm(
                raw_chain, direction, atm_strike, itm_depth_points=settings["itm_depth_points"], step=strike_step,
                hedge_enabled=settings.get("naked_hedge_enabled", False),
                hedge_width_points=settings.get("naked_hedge_width_points", 150),
            )
            if naked_result is None:
                naked_diag_entry["trade_status"] = "SKIPPED_NAKED_STRIKE_NOT_FOUND"
                naked_diag_entry["reason"] = (
                    f"Naked trade साठी आवश्यक ITM strike (atm={atm_strike}, डेप्थ "
                    f"{settings['itm_depth_points']}) raw_chain मध्ये सापडला नाही"
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
                )
                naked_status = "; ".join(f"{r['account_id']}:{r['result']}" for r in naked_results) or "कुठलाही account उपलब्ध नाही"
            else:
                _, naked_status = open_multi_leg_trade(
                    access_token, symbol, naked_result, lots=naked_lots, lot_size=lot_size,
                    sl_pct_of_max_loss=None, target_pct_of_max_profit=100,
                    product_type="D", trading_mode=trading_mode, trading_style="INTRADAY",
                    sl_pct_of_credit=100, source="dynamic_sr_instant",
                    entry_level_price=row["zone_low"], entry_timeframe=timeframe_suffix, entry_spot_price=underlying_price,
                    entry_reason_tag=entry_reason_tag,
                )

        level_label = "Support" if direction == "BULLISH" else "Resistance"
        hit_label = "थेट स्पर्श" if hit_type == "TOUCH" else "⚡ Gap ने उडी मारून ओलांडला"
        if is_breakout_trade:
            rsi_display = "📈 Breakout Entry (price consolidation + 5-मिनिट candle close) — RSI/PCR Gate वगळले."
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
        hit_label_header = "🎯 Breakout Entry" if is_breakout_trade else f"🎯 Dynamic S/R Cross (आजचा {hit_count_so_far + 1}/2 वा hit)"
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
