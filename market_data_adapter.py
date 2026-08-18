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
from signals import detect_liquidity_sweep, detect_choch, find_fair_value_gaps, classify_market_structure


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
    cum_vol = df["volume"].cumsum().replace(0, 1)
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / cum_vol
    df["vwap_std"] = (df["close"] - df["vwap"]).rolling(20).std()

    return df.dropna().reset_index(drop=True)


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
