"""
market_data_adapter.py
-------------------------
आपल्या खऱ्या Upstox-आधारित लाईव्ह डेटा (candles, option chain) पासून नवीन multi-strategy
orchestrator (orchestrator.py + strategies/) ला लागणारा MarketSnapshot बनवणे — demo_test.py च्या
synthetic generators ऐवजी, प्रत्यक्ष live डेटावर. दिशा-निरपेक्ष, कुठल्याही page वरून वापरता येईल.
"""
import datetime
import sqlite3

import pandas as pd

from config import DB_PATH, get_ist_today
from signals import detect_liquidity_sweep, detect_choch, find_fair_value_gaps, classify_market_structure, calculate_supertrend


def prepare_futures_ohlcv(df_candles, bb_period=20, atr_period=14):
    """
    BB(20)/ATR(14)/VWAP/vwap_std columns जोडून, bb_squeeze/vwap strategies ला हवा तसा DataFrame बनवणे.
    pandas rolling() वापरून vectorized — मोठ्या डेटावरही जलद (आधीच्या S/R performance धड्यानुसार).
    """
    if df_candles is None or df_candles.empty:
        return pd.DataFrame()

    df = df_candles.copy()
    df["bb_middle"] = df["close"].rolling(bb_period).mean()
    df["bb_std"] = df["close"].rolling(bb_period).std()
    df["bb_upper"] = df["bb_middle"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_middle"] - 2 * df["bb_std"]
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_period).mean()

    if "volume" not in df.columns:
        df["volume"] = 0

    # VWAP रोज नव्याने (त्या दिवसाच्या पहिल्या bar पासून) सुरू व्हायला हवा — खरा intraday VWAP असाच असतो.
    # आधी संपूर्ण DataFrame वर एकत्र cumsum होत होतं (दिवसागणिक reset न होता) — त्यामुळे VWAP दिवसागणिक
    # जास्तच stale/lagging होत गेला, आणि जवळपास प्रत्येक bar ला (मीन-रिव्हर्जन + ट्रेंड दोन्ही मोड मध्ये)
    # सिग्नल यायचा — हाच "backtest खूप विपरीत" दिसण्याचं खरं कारण होतं.
    trade_date = df["timestamp"].dt.date
    cum_pv = (df["close"] * df["volume"]).groupby(trade_date).cumsum()
    cum_vol = df["volume"].groupby(trade_date).cumsum().replace(0, 1)
    df["vwap"] = cum_pv / cum_vol
    df["vwap_std"] = (df["close"] - df["vwap"]).groupby(trade_date).transform(lambda s: s.rolling(20, min_periods=5).std())

    # vwap_std फक्त intraday granularity (एका दिवसात अनेक bars) असेल तरच अर्थपूर्ण असतो — daily bars साठी
    # (Swing backtest) प्रत्येक 'दिवस' group मध्ये फक्त १च row असतो, त्यामुळे rolling std कधीच पूर्ण होत
    # नाही (कायम NaN) — हे स्वाभाविक आहे, त्यामुळे त्यावर आधारित संपूर्ण row वगळणं चुकीचं आहे. फक्त खरे
    # आवश्यक columns (BB/ATR) NaN असतील तरच row वगळायचं.
    return df.dropna(subset=["bb_upper", "bb_lower", "bb_width", "atr"]).reset_index(drop=True)


def prepare_options_chain(raw_chain, symbol, atm_strike, atm_range=5, step=None):
    """raw_chain (Upstox) पासून oi_pcr strategy ला हवा तसा DataFrame — day_baseline_oi वरून oi_prev."""
    if not raw_chain or atm_strike is None:
        return pd.DataFrame()
    if step is None:
        step = 50 if symbol == "NIFTY" else 100

    rows = []
    today_str = get_ist_today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    valid_strikes = set(range(int(atm_strike - atm_range * step), int(atm_strike + atm_range * step) + 1, step))

    for item in raw_chain:
        strike = item.get("strike_price")
        if strike not in valid_strikes:
            continue
        for side, opt_type in [("call_options", "CE"), ("put_options", "PE")]:
            opt = item.get(side, {}) or {}
            mkt = opt.get("market_data", {}) or {}
            current_oi = int(mkt.get("oi") or 0)
            col = "initial_ce_oi" if opt_type == "CE" else "initial_pe_oi"
            cur.execute(
                f"SELECT {col} FROM day_baseline_oi WHERE symbol=? AND strike=? AND trade_date=?",
                (symbol, strike, today_str),
            )
            row = cur.fetchone()
            baseline = row[0] if row else current_oi
            rows.append({
                "strike": strike, "option_type": opt_type, "oi": current_oi,
                "oi_prev": baseline, "ltp": mkt.get("ltp", 0),
            })
    conn.close()
    return pd.DataFrame(rows)


def prepare_structure_data(df):
    """
    आपलंच existing Liquidity Sweep / CHoCH / FVG detection वापरून ict_fvg strategy ला हवा तसा
    structure_data dict बनवणे — दोन्ही दिशा तपासून, जी आधी सापडेल ती दिशा घेणे.
    """
    empty = {"swept_high": False, "swept_low": False, "bos_confirmed": False, "choch_confirmed": False, "bos_direction": None, "fvg_zones": []}
    if df is None or df.empty or len(df) < 20:
        return empty

    sweep_bull = detect_liquidity_sweep(df, "BULLISH")
    sweep_bear = detect_liquidity_sweep(df, "BEARISH")

    choch_result = detect_choch(df)
    choch_bull = choch_result == "BULLISH_CHOCH"
    choch_bear = choch_result == "BEARISH_CHOCH"

    structure = classify_market_structure(df)
    # BOS (Break of Structure) — 'सद्य bar चा close अजूनही जुन्या high/low च्या पलीकडे आहे का' असं न
    # तपासता, 'गेल्या bos_lookback bars पैकी कुठल्याही bar ने संरचना तोडली होती का' हे तपासणे. आधीची
    # पद्धत सद्य close वरच अवलंबून होती — पण Retracement (जे entry साठी आवश्यक असतं, आणि किंमत परत
    # खाली/वर आणतं) झाल्यावर BOS "एक्सपायर" व्हायचं, नेमकं त्याच क्षणी जेव्हा entry हवी असते.
    bos_lookback = 10
    if len(df) >= bos_lookback + 10:
        reference_df = df.iloc[:-bos_lookback]
        ref_structure = classify_market_structure(reference_df)
        ref_swing_high = ref_structure.get("last_swing_high")
        ref_swing_low = ref_structure.get("last_swing_low")
        recent = df.iloc[-bos_lookback:]
        bos_bull = ref_swing_high is not None and (recent["high"] > ref_swing_high).any()
        bos_bear = ref_swing_low is not None and (recent["low"] < ref_swing_low).any()
    else:
        bos_bull = structure.get("last_swing_high") is not None and df["close"].iloc[-1] > structure["last_swing_high"]
        bos_bear = structure.get("last_swing_low") is not None and df["close"].iloc[-1] < structure["last_swing_low"]

    bos_direction = None
    if sweep_bull or choch_bull or bos_bull:
        bos_direction = "LONG"
    elif sweep_bear or choch_bear or bos_bear:
        bos_direction = "SHORT"

    fvg_zones = []
    if bos_direction:
        fvg_dir = "BULLISH" if bos_direction == "LONG" else "BEARISH"
        fvg = find_fair_value_gaps(df, fvg_dir)
        if fvg:
            fvg_zones.append({
                "start": fvg["fvg_bottom"], "end": fvg["fvg_top"],
                "direction": bos_direction, "candle_idx": fvg["index"],
            })

    return {
        "swept_high": bool(sweep_bear), "swept_low": bool(sweep_bull),
        "bos_confirmed": bool(bos_bull or bos_bear),
        "choch_confirmed": bool(choch_bull or choch_bear),
        "bos_direction": bos_direction,
        "fvg_zones": fvg_zones,
    }


def compute_trend_direction_1h(df_1h):
    """
    1H Supertrend वरून सद्य दिशा ("LONG"/"SHORT"/None) काढणे — vwap strategy साठी (आपल्याच मुख्य
    A1 Engine शी सुसंगत दिशा-स्रोत). df_1h: 1-तासाच्या candles चा DataFrame (OHLC सह).
    """
    if df_1h is None or df_1h.empty:
        return None
    st_line, st_dir = calculate_supertrend(df_1h, period=10, multiplier=3)
    if st_dir.empty or st_dir.isna().iloc[-1]:
        return None
    return "LONG" if int(st_dir.iloc[-1]) == 1 else "SHORT"


def apply_manual_sl_target(result, sl_points, target_points, reference_price=None):
    """
    दिलेल्या SignalResult वर, strategy च्या स्वतःच्या (auto) SL/Target ऐवजी, वापरकर्त्याने दिलेले
    ठराविक पॉइंट्स-अंतराचे SL/Target लावणे (entry_price तेच राहतं/reference_price होतं, फक्त SL/Target
    बदलतं). reference_price दिलं नसेल तर result.entry_price वापरला जातो — दोन्हीपैकी काहीच नसेल (उदा.
    oi_pcr ज्याला स्वतःची entry_price नसते, तिथे underlying spot हा reference_price म्हणून द्यावा
    लागतो) तर override शक्य नाही, मूळ result जसाच्या तसा परत जातो.
    """
    if result.direction.value == "NONE":
        return result
    entry = result.entry_price if result.entry_price is not None else reference_price
    if entry is None:
        return result
    if result.direction.value == "LONG":
        new_sl = entry - sl_points
        new_target = entry + target_points
    else:
        new_sl = entry + sl_points
        new_target = entry - target_points
    result.entry_price = round(entry, 2)
    result.stop_loss = round(new_sl, 2)
    result.target = round(new_target, 2)
    return result
