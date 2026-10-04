"""
srv3_instant_shadow.py
------------------------
🎓 वापरकर्त्याचा निर्णय ("फक्त 5-Min bot ला SR V3 देऊन PAPER मध्ये चाचणी") — backtest (run_sr_bot_level_backtest.py) मध्ये
5-Min Instant Trader साठी SR V3 (grade A/B) levels चा OOS निकाल जुन्या Dynamic levels पेक्षा किंचित बरा (≈ शून्य फरक) आला,
म्हणून आता forward PAPER चाचणी. मूळ bot (dynamic_sr_instant_trader.py) आणि त्याचे levels **अजिबात बदलत नाहीत** — हा
त्याच्यासोबत (त्याच cron cycle मध्ये, स्वतंत्र try/except मध्ये) चालणारा निव्वळ PAPER "shadow":

  • Levels: SR V3 (sr_levels_v3.compute_sr_v3) — 5M + 15M pivots + PDH/PDL/PDC/PWH/PWL + gaps, फक्त पूर्ण झालेले candles,
    फक्त grade A/B आणि किंमतीपासून 3% आत. दर 5 मिनिटांनी (मूळ 5M levels प्रमाणे) पुन्हा मोजून market_zones मध्ये
    `SRV3_SUPPORT` / `SRV3_RESISTANCE` नावाने merge (शेवटी "_5M" नाही ⇒ इतर कुठल्याही bot ला हे levels दिसत नाहीत).
  • Entry नियम — मूळ bot चेच, त्याच्याच settings (cloud_db "1m_instant") मधून, आणि मूळ bot चीच functions:
    touch (शेवटचे 2 × 1-मिनिट candles, ±0.01%, gap-through सकट), hysteresis-दिशा (0.10%), Bullish/Bearish entry toggles,
    RSI Gate (1-मिनिट RSI, Support < rsi_support_max / Resistance > rsi_resistance_min), PCR Gate, एका level वर दिवसात कमाल
    `max_hits_per_zone` entries, SL/TSL नंतर `sl_tsl_cooldown_minutes` cooldown, एका वेळी एकच position, 14:45 नंतर नवीन
    entry नाही, expiry दिवशी पुढची expiry. मूळ bot चे डीफॉल्ट-बंद पर्याय (Breakout/IV/Supertrend/Min-hold/Fast-move/
    Strength/Defer-to-15M/Stop-after-target) इथे लागू नाहीत.
  • Trade: Credit Spread (ITM) आणि/किंवा Naked — मूळ settings प्रमाणे — पण **नेहमी PAPER**, broker accounts कधीच नाहीत,
    source="dynamic_sr_instant_srv3_shadow" (नाव "_shadow" ने संपतं ⇒ एकत्रित P&L/Kill Switch मधून आपोआप वगळलं जातं;
    Performance Report वर स्वतंत्र रांग). Exit नियम मूळ bot चेच (trading_engine.SHADOW_EXIT_PARENT_SOURCE); Next-Level
    exit फक्त "5M" entries ला असल्याने इथे लागू नाही (entry_timeframe="SRV3").
  • चालू/बंद: Bot Dynamic SR Algo → 5-Min Instant Trader → "🧪 SR V3 PAPER Shadow" (डीफॉल्ट बंद).
"""
import json
import os

import pandas as pd

import cloud_db
from config import get_ist_now
from database import count_entries_at_level_today, get_last_sl_tsl_exit_time, has_open_trade_from_source
from dynamic_sr_instant_trader import (NO_NEW_ENTRY_AFTER_HOUR, NO_NEW_ENTRY_AFTER_MINUTE, RSI_RESISTANCE_MIN, RSI_SUPPORT_MAX,
                                       _completed_bars_only, check_instant_rsi_filter, check_level_crossed,
                                       determine_direction_with_hysteresis, is_todays_expiry_day)
from notifications import send_telegram_message
from oi_analysis import check_pcr_gate
from sr_levels_v3 import compute_sr_v3
from strategy import select_credit_spread_itm, select_naked_option_itm
from trading_engine import format_trade_result, open_multi_leg_trade
from upstox_api import fetch_candles, fetch_upstox_option_chain

SOURCE = "dynamic_sr_instant_srv3_shadow"
ZONE_PREFIX = "SRV3"
ZONE_TYPES = ("SRV3_SUPPORT", "SRV3_RESISTANCE")
ENTRY_TIMEFRAME = "SRV3"
GRADES = ("A", "B")
MAX_DISTANCE_PCT = 3.0
REFRESH_MINUTES = 5
REFRESH_STATE = os.path.join("data", "srv3_shadow_refresh.json")


# ---------------------------------------------------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------------------------------------------------
def v3_levels(df5, df15, daily, price):
    """SR V3 (5M + 15M, key levels, gaps) -> merge_dynamic_sr_zones() चा फॉरमॅट: {"support": [{level, touches}], "resistance": [...]}.
    फक्त grade A/B, किंमतीपासून ≤ 3%. Support/Resistance = सध्याच्या किंमतीच्या खाली/वर (bot दिशा पुन्हा किंमतीवरूनच ठरवतो)."""
    frames = {}
    if df5 is not None and len(df5):
        frames["5minute"] = df5
    if df15 is not None and len(df15):
        frames["15minute"] = df15
    if not frames:
        return {"support": [], "resistance": []}
    res = compute_sr_v3(frames, daily_df=daily, current_price=price)
    out = {"support": [], "resistance": []}
    for z in res["levels"]:
        if z["grade"] not in GRADES or abs(z["distance_pct"]) > MAX_DISTANCE_PCT:
            continue
        side = "support" if z["level"] < res["meta"]["price"] else "resistance"
        out[side].append({"level": round(float(z["level"]), 2), "touches": float(z["score"])})
    return out


def _naive(ts):
    """timestamps -> naive IST (Upstox tz-aware देतो; tests naive)."""
    t = pd.to_datetime(ts)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t


def _load_state(path=REFRESH_STATE):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_state(state, path=REFRESH_STATE):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except OSError:
        pass


def refresh_levels_if_due(access_token, symbol, now, fetch=fetch_candles, state_path=REFRESH_STATE):
    """शेवटच्या यशस्वी गणनेला ≥ 5 मिनिटं झाली असतील तर SR V3 पुन्हा मोजून merge. रिटर्न: संदेश (किंवा None — गरज नव्हती)."""
    state = _load_state(state_path)
    last = state.get(symbol)
    if last is not None and (pd.Timestamp(now) - pd.Timestamp(last)).total_seconds() < REFRESH_MINUTES * 60:
        return None
    df5 = fetch(access_token, symbol, current_spot=0, interval="5minute", lookback_days=10)
    df15 = fetch(access_token, symbol, current_spot=0, interval="15minute", lookback_days=10)
    daily = fetch(access_token, symbol, current_spot=0, interval="day", lookback_days=60)
    if df5 is None or df5.empty:
        return f"{symbol}: SR V3 — 5-मिनिट डेटा मिळाला नाही (जुने levels कायम)"
    if any(d is not None and getattr(d, "attrs", {}).get("failed_chunks", 0) > 0 for d in (df5, df15, daily)):
        return f"{symbol}: SR V3 — इतिहास अपूर्ण (failed chunks), या वेळी levels अद्ययावत केले नाहीत"
    df5 = _completed_bars_only(df5, 5, now)
    df15 = _completed_bars_only(df15, 15, now) if df15 is not None and not df15.empty else df15
    if daily is not None and not daily.empty:
        days = _naive(daily["timestamp"]).dt.normalize()
        daily = daily[(days < pd.Timestamp(now).normalize()).to_numpy()]                # फक्त पूर्ण झालेले (आधीचे) दिवस
    price = float(df5["close"].iloc[-1])
    levels = v3_levels(df5, df15, daily, price)
    ok = cloud_db.merge_dynamic_sr_zones(symbol, levels, "", formed_date=now, type_prefix=ZONE_PREFIX)
    if ok:
        state[symbol] = pd.Timestamp(now).isoformat()
        _save_state(state, state_path)
    n = len(levels["support"]) + len(levels["resistance"])
    return f"{symbol}: SR V3 levels {'merge झाले' if ok else 'नाहीत / merge अयशस्वी — जुने कायम'} ({n} A/B)"


def active_levels(symbol):
    zones = cloud_db.get_market_zones(symbol, status="ACTIVE")
    if zones is None or zones.empty:
        return []
    z = zones[zones["zone_type"].isin(ZONE_TYPES)]
    return sorted({round(float(x), 2) for x in z["zone_low"]})


# ---------------------------------------------------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------------------------------------------------
def evaluate_touch(level, recent, closes, candles_df, settings, symbol, trade_date, now, rsi_fn=check_instant_rsi_filter, pcr_fn=check_pcr_gate):
    """एका level वर मूळ bot चे (डीफॉल्ट-चालू) gates. रिटर्न (direction किंवा None, कारण)."""
    hit, hit_type, _ = check_level_crossed(level, recent)
    if not hit:
        return None, "touch नाही"
    direction = determine_direction_with_hysteresis(level, closes)
    if direction == "BULLISH" and not settings.get("bullish_entry_enabled", True):
        return None, "Bullish entries बंद"
    if direction == "BEARISH" and not settings.get("bearish_entry_enabled", True):
        return None, "Bearish entries बंद"
    max_hits = int(settings.get("max_hits_per_zone", 2))
    if count_entries_at_level_today(symbol, level, SOURCE, trade_date) >= max_hits:
        return None, f"या level वर आज कमाल {max_hits} entries झाल्या"
    last_sl = get_last_sl_tsl_exit_time(symbol, level, SOURCE, trade_date)
    cooldown = float(settings.get("sl_tsl_cooldown_minutes", 15))
    if last_sl is not None and pd.Timestamp(now) - pd.Timestamp(last_sl) < pd.Timedelta(minutes=cooldown):
        return None, f"SL/TSL नंतर {cooldown:.0f} मिनिटांचा cooldown"
    if settings.get("entry_rsi_gate_enabled", True):
        ok, rsi = rsi_fn(candles_df, direction, settings.get("rsi_support_max", RSI_SUPPORT_MAX), settings.get("rsi_resistance_min", RSI_RESISTANCE_MIN))
        if not ok:
            return None, f"RSI gate ({rsi})"
    if settings.get("entry_pcr_gate_enabled", True):
        ok, _, reason = pcr_fn(symbol, direction, settings["pcr_bullish_min"], settings["pcr_bearish_max"])
        if not ok:
            return None, f"PCR gate ({reason})"
    return direction, hit_type


def _open_paper(access_token, symbol, settings, direction, level, lot_size):
    expiry_index = 1 if is_todays_expiry_day(access_token, symbol) else 0
    raw_chain, chain_status = fetch_upstox_option_chain(access_token, symbol, expiry_index=expiry_index)
    if not raw_chain:
        return [f"option chain नाही ({chain_status})"], None
    spot = raw_chain[0].get("underlying_spot_price")
    step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
    atm = round(spot / step) * step
    common = dict(sl_pct_of_max_loss=None, target_pct_of_max_profit=100, product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                  sl_pct_of_credit=100, source=SOURCE, entry_level_price=level, entry_timeframe=ENTRY_TIMEFRAME, entry_spot_price=spot,
                  direction=direction)
    out = []
    if settings.get("credit_spread_enabled", True):
        spread = select_credit_spread_itm(raw_chain, direction, atm, step=step, itm_depth_points=settings["itm_depth_points"],
                                          hedge_width_points=settings["hedge_width_points"])
        if spread is not None:
            ok, resp = open_multi_leg_trade(access_token, symbol, spread, lots=settings["lots"], lot_size=lot_size, **common)
            out.append(f"Credit Spread {spread.get('strategy', direction)}: {format_trade_result(ok, resp)}")
    if settings.get("naked_enabled", True):
        naked = select_naked_option_itm(raw_chain, direction, atm, itm_depth_points=settings.get("naked_itm_depth_points", settings["itm_depth_points"]),
                                        step=step, hedge_enabled=settings.get("naked_hedge_enabled", False),
                                        hedge_width_points=settings.get("naked_hedge_width_points", 150))
        if naked is not None:
            ok, resp = open_multi_leg_trade(access_token, symbol, naked, lots=settings.get("naked_lots", settings["lots"]), lot_size=lot_size, **common)
            out.append(f"Naked {naked.get('strategy', direction)}: {format_trade_result(ok, resp)}")
    return out or ["Credit Spread आणि Naked दोन्ही बंद / strike सापडला नाही"], spot


def run_shadow(access_token, symbol, now=None, settings=None, lot_size=65, fetch=fetch_candles):
    """एका symbol साठी एक cycle. setting बंद / symbol बंद / बाजाराबाहेर ⇒ None (काहीच नाही). रिटर्न: एक ओळ सारांश."""
    settings = settings if settings is not None else cloud_db.get_strategy_settings("1m_instant", symbol)
    if not settings.get("srv3_shadow_enabled", False) or not settings.get("symbol_enabled", symbol == "NIFTY"):
        return None
    now = now or get_ist_now()
    hm = (now.hour, now.minute)
    if hm < (9, 15) or hm > (15, 30):
        return None
    notes = []
    msg = refresh_levels_if_due(access_token, symbol, now, fetch=fetch)
    if msg:
        notes.append(msg)
    if hm >= (NO_NEW_ENTRY_AFTER_HOUR, NO_NEW_ENTRY_AFTER_MINUTE):
        return "🧪 " + "; ".join(notes + [f"{symbol}: SR V3 shadow — 14:45 नंतर नवीन entry नाही"])
    if has_open_trade_from_source(symbol, SOURCE):
        return "🧪 " + "; ".join(notes + [f"{symbol}: SR V3 shadow — आधीची PAPER position उघडी"])
    levels = active_levels(symbol)
    if not levels:
        return "🧪 " + "; ".join(notes + [f"{symbol}: SR V3 shadow — ACTIVE A/B levels नाहीत"])
    candles_df = fetch(access_token, symbol, current_spot=0, interval="1minute", lookback_days=1)
    if candles_df is None or candles_df.empty:
        return "🧪 " + "; ".join(notes + [f"{symbol}: SR V3 shadow — 1-मिनिट candles नाहीत"])
    today = candles_df[(_naive(candles_df["timestamp"]).dt.date == now.date()).to_numpy()]
    if len(today) < 2:
        return "🧪 " + "; ".join(notes + [f"{symbol}: SR V3 shadow — आजचे पुरेसे candles नाहीत"])
    recent = today.tail(2).to_dict("records")
    closes = today["close"].tolist()
    trade_date = now.strftime("%Y-%m-%d")
    for level in levels:
        direction, why = evaluate_touch(level, recent, closes, candles_df, settings, symbol, trade_date, now)
        if direction is None:
            if why != "touch नाही":
                notes.append(f"{symbol} SR V3 {level:,.2f}: {why}")
            continue
        results, spot = _open_paper(access_token, symbol, settings, direction, level, lot_size)
        role = "Support" if direction == "BULLISH" else "Resistance"
        send_telegram_message(f"🧪 [SR V3 PAPER shadow] {symbol} {role} {level:,.2f} ({why})\n" + "\n".join(results) +
                              f"\nवेळ: {now.strftime('%H:%M:%S')} — फक्त चाचणी, खरा पैसा नाही.")
        notes.append(f"{symbol} SR V3 {role} {level:,.2f} → " + "; ".join(results))
        break                                                   # एका वेळी एकच position
    return "🧪 " + "; ".join(notes) if notes else f"🧪 {symbol}: SR V3 shadow — कुठल्याही A/B level ला touch नाही"
