"""
nifty_futures_swing_rsi_st.py
--------------------------------
NIFTY Futures Swing Trading Strategy — वापरकर्त्याच्या नेमक्या नियमांनुसार:

  इंडिकेटर्स: RSI(5), Supertrend(ATR period=7, multiplier=2.0)
  Setup: Support/Resistance + RSI Divergence — दोन्ही lookback=4 candles
  Entry:
    LONG  = Supertrend Bullish + (किंमत Support ± 0.2% वर आली किंवा Bullish RSI Divergence)
    SHORT = Supertrend Bearish + (किंमत Resistance ∓ 0.2% वर आली किंवा Bearish RSI Divergence)
  Exit: SL=0.5%, Target=Risk×3 (1:3 RR), किंवा Expiry-rollover (expiry च्या ४ ट्रेडिंग दिवस आधी, दुपारी
  3:15 ला जबरदस्तीने बंद — नवीन सिग्नल्स पुढच्या महिन्याच्या contract वर)

⚠️ डेटा मर्यादा: आपल्याकडे फक्त ३ महिन्यांचे (विखुरलेले, मधे मोठा gap असलेले) real contracts आहेत —
निकाल केवळ "logic बरोबर चालतंय" हे दाखवण्यासाठी आहेत, सांख्यिकीयदृष्ट्या अर्थपूर्ण नाहीत.
"""
import pandas as pd

from signals import calculate_rsi, calculate_supertrend

LOT_SIZE = 75  # NIFTY lot size


def find_support_resistance(df, i, lookback=4):
    """सद्य bar च्या आधीच्या lookback candles मधला support (min low) आणि resistance (max high)."""
    if i < lookback:
        return None, None
    window = df.iloc[i - lookback:i]
    return window["low"].min(), window["high"].max()


def check_bullish_divergence(df, rsi, i, lookback=4):
    """किंमतीने नवीन low केला, पण RSI ने केला नाही (Bullish Divergence)."""
    if i < lookback:
        return False
    idx = df["low"].iloc[i - lookback:i].idxmin()
    return df["low"].iloc[i] <= df["low"].iloc[idx] and rsi.iloc[i] > rsi.iloc[idx]


def check_bearish_divergence(df, rsi, i, lookback=4):
    """किंमतीने नवीन high केला, पण RSI ने केला नाही (Bearish Divergence)."""
    if i < lookback:
        return False
    idx = df["high"].iloc[i - lookback:i].idxmax()
    return df["high"].iloc[i] >= df["high"].iloc[idx] and rsi.iloc[i] < rsi.iloc[idx]


def get_rollover_date(trading_days, expiry_date, days_before=4):
    """expiry च्या 'days_before' ट्रेडिंग दिवस आधीची तारीख — त्या दिवशी जबरदस्तीने बंद करून shift करायचं."""
    trading_days = sorted(trading_days)
    earlier_or_eq = [d for d in trading_days if d <= expiry_date]
    if not earlier_or_eq:
        return None
    expiry_idx = trading_days.index(earlier_or_eq[-1])
    rollover_idx = expiry_idx - days_before
    if rollover_idx < 0:
        return trading_days[0]  # डेटा तितका मागे नसेल तर सुरुवातीपासूनच
    return trading_days[rollover_idx]


def check_entry_signal(df, rsi, st_dir, i, sr_lookback=4, retest_tolerance_pct=0.2):
    """दिलेल्या bar वर LONG/SHORT entry सिग्नल आहे का ते तपासणे. रिटर्न: (direction, reason) किंवा (None, reason)."""
    support, resistance = find_support_resistance(df, i, sr_lookback)
    if support is None:
        return None, "अपुरा इतिहास (S/R साठी)"

    last = df.iloc[i]
    direction_bias = "LONG" if st_dir.iloc[i] == 1 else "SHORT"

    if direction_bias == "LONG":
        sr_retest = last["low"] <= support * (1 + retest_tolerance_pct / 100)
        divergence = check_bullish_divergence(df, rsi, i, sr_lookback)
        if sr_retest or divergence:
            reason = "Support Retest" if sr_retest else "Bullish RSI Divergence"
            return "LONG", f"Supertrend Bullish + {reason}"
        return None, "Supertrend Bullish, पण Support Retest/Divergence नाही"
    else:
        sr_retest = last["high"] >= resistance * (1 - retest_tolerance_pct / 100)
        divergence = check_bearish_divergence(df, rsi, i, sr_lookback)
        if sr_retest or divergence:
            reason = "Resistance Retest" if sr_retest else "Bearish RSI Divergence"
            return "SHORT", f"Supertrend Bearish + {reason}"
        return None, "Supertrend Bearish, पण Resistance Retest/Divergence नाही"


def run_swing_backtest(all_contracts_df, sl_pct=0.5, rr_ratio=3.0, rsi_period=5, st_period=7, st_multiplier=2.0,
                        sr_lookback=4, rollover_days_before=4, rollover_exit_hour=15, rollover_exit_minute=15):
    """
    सर्व contracts (expiry-labeled) वर walk-forward, rollover-aware backtest. प्रत्येक contract स्वतःच्या
    RSI/Supertrend सह स्वतंत्रपणे evaluate होतो; rollover-तारखेला जर position उघडी असेल, तर ती त्याच
    दिवशी पुढच्या महिन्याच्या contract च्या किमतीत (उपलब्ध असल्यास) "shift" केली जाते.
    """
    trades = []
    contracts = sorted(all_contracts_df["contract"].unique(), key=lambda c: all_contracts_df[all_contracts_df["contract"] == c]["expiry"].iloc[0])

    open_position = None  # {"direction","entry_price","sl","target","entry_date","contract"}

    for ci, contract in enumerate(contracts):
        df = all_contracts_df[all_contracts_df["contract"] == contract].sort_values("timestamp").reset_index(drop=True)
        if len(df) < st_period + 2:
            continue
        expiry_date = df["expiry"].iloc[0].date()
        trading_days = df["timestamp"].dt.date.tolist()
        rollover_date = get_rollover_date(trading_days, expiry_date, rollover_days_before)

        rsi = calculate_rsi(df, period=rsi_period)
        _, st_dir = calculate_supertrend(df, period=st_period, multiplier=st_multiplier)

        next_contract_df = all_contracts_df[all_contracts_df["contract"] == contracts[ci + 1]].sort_values("timestamp").reset_index(drop=True) if ci + 1 < len(contracts) else None

        for i in range(st_period + 1, len(df)):
            bar_date = df["timestamp"].iloc[i].date()
            bar = df.iloc[i]

            # --- सद्य position असल्यास आधी SL/Target/Rollover तपासणे ---
            if open_position is not None and open_position["contract"] == contract:
                hit_sl = (bar["low"] <= open_position["sl"]) if open_position["direction"] == "LONG" else (bar["high"] >= open_position["sl"])
                hit_target = (bar["high"] >= open_position["target"]) if open_position["direction"] == "LONG" else (bar["low"] <= open_position["target"])
                if hit_sl:
                    _close_trade(trades, open_position, open_position["sl"], bar_date, "SL")
                    open_position = None
                elif hit_target:
                    _close_trade(trades, open_position, open_position["target"], bar_date, "TARGET")
                    open_position = None
                elif rollover_date is not None and bar_date >= rollover_date:
                    closing_direction = open_position["direction"]  # None करण्याआधीच दिशा जपून ठेवणे
                    _close_trade(trades, open_position, bar["close"], bar_date, "ROLLOVER_EXIT")
                    open_position = None
                    # जर पुढचा contract उपलब्ध असेल, तर त्याच दिवशी त्याच दिशेने नवीन position "shift" करणे
                    if next_contract_df is not None:
                        next_row = next_contract_df[next_contract_df["timestamp"].dt.date == bar_date]
                        if not next_row.empty:
                            shift_price = float(next_row["close"].iloc[0])
                            open_position = _open_trade(closing_direction, shift_price, sl_pct, rr_ratio, bar_date, contracts[ci + 1])
                    continue

            # --- नवीन signal (रोलओव्हर तारखेनंतर नवीन entry घ्यायची नाही, फक्त शिफ्ट होणारी जुनी) ---
            if open_position is None and (rollover_date is None or bar_date < rollover_date):
                direction, reason = check_entry_signal(df, rsi, st_dir, i, sr_lookback)
                if direction:
                    open_position = _open_trade(direction, bar["close"], sl_pct, rr_ratio, bar_date, contract)
                    open_position["reason"] = reason

        # contract संपला तरी position उघडी राहिली (rollover_date नंतरचा डेटाच संपला) -> शेवटच्या bar वर बंद
        if open_position is not None and open_position["contract"] == contract:
            _close_trade(trades, open_position, df["close"].iloc[-1], df["timestamp"].iloc[-1].date(), "DATA_END")
            open_position = None

    return _compute_stats(trades)


def _open_trade(direction, entry_price, sl_pct, rr_ratio, entry_date, contract):
    sl_distance = entry_price * (sl_pct / 100)
    sl = entry_price - sl_distance if direction == "LONG" else entry_price + sl_distance
    target = entry_price + sl_distance * rr_ratio if direction == "LONG" else entry_price - sl_distance * rr_ratio
    return {"direction": direction, "entry_price": entry_price, "sl": sl, "target": target,
            "entry_date": entry_date, "contract": contract, "reason": ""}


def _close_trade(trades, position, exit_price, exit_date, outcome):
    pnl_points = (exit_price - position["entry_price"]) if position["direction"] == "LONG" else (position["entry_price"] - exit_price)
    trades.append({
        "contract": position["contract"], "direction": position["direction"],
        "entry_date": position["entry_date"], "exit_date": exit_date,
        "entry_price": round(position["entry_price"], 2), "exit_price": round(exit_price, 2),
        "outcome": outcome, "pnl_points": round(pnl_points, 2), "pnl_rupees": round(pnl_points * LOT_SIZE, 2),
        "reason": position.get("reason", ""),
    })


def _compute_stats(trades):
    if not trades:
        return {"total_trades": 0, "trades": []}
    df = pd.DataFrame(trades)
    wins = df[df["pnl_points"] > 0]
    losses = df[df["pnl_points"] <= 0]
    total_pnl_points = df["pnl_points"].sum()
    total_pnl_rupees = df["pnl_rupees"].sum()

    # Drawdown: cumulative P&L (रुपयांत) वरून running peak-to-trough
    cum_pnl = df["pnl_rupees"].cumsum()
    running_peak = cum_pnl.cummax()
    drawdown = cum_pnl - running_peak
    max_drawdown_rupees = drawdown.min()
    max_drawdown_pct = (max_drawdown_rupees / running_peak.max() * 100) if running_peak.max() > 0 else 0.0

    avg_win = wins["pnl_points"].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses["pnl_points"].mean()) if len(losses) > 0 else 0
    actual_rr = (avg_win / avg_loss) if avg_loss > 0 else None

    return {
        "total_trades": len(df),
        "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(df) * 100, 1) if len(df) > 0 else None,
        "total_pnl_points": round(total_pnl_points, 2),
        "total_pnl_rupees": round(total_pnl_rupees, 2),
        "max_drawdown_rupees": round(max_drawdown_rupees, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "avg_win_points": round(avg_win, 2), "avg_loss_points": round(avg_loss, 2),
        "actual_risk_reward": round(actual_rr, 2) if actual_rr else None,
        "trades": trades,
    }
