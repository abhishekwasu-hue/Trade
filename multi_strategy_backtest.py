"""
multi_strategy_backtest.py
-----------------------------
नवीन Multi-Strategy Orchestrator (strategies/) साठी walk-forward, no-lookahead backtest —
आपल्याच existing backtest.py (run_signal_backtest_v2) च्याच पद्धतीने (SL/Target/EOD exit simulation).

महत्त्वाची मर्यादा: फक्त futures_ohlcv वापरणाऱ्या रणनीती इथे चालतात — ict_fvg, bb_squeeze, vwap.
oi_pcr इथे चालवता येत नाही — त्याला प्रत्येक ऐतिहासिक क्षणाचा खरा Option OI इतिहास लागतो, जो आपल्याकडे
साठवलेलाच नाही (OI Wall Confirmation च्या वेळी हीच अडचण आधी आली होती).
"""
import datetime

from strategies.base import MarketSnapshot
from market_data_adapter import prepare_structure_data

FUTURES_ONLY_STRATEGY_IDS = ("ict_fvg", "bb_squeeze", "vwap")


def run_strategy_backtest(df_prepared, strategy_obj, min_lookback=30, max_hold_bars=50,
                            is_intraday=True, eod_hour=15, eod_minute=15, min_confidence=0.5):
    """
    एका (futures-आधारित) strategy साठी walk-forward backtest — प्रत्येक bar ला check_gates() चालवून,
    actionable सिग्नल आल्यास पुढच्या bars मध्ये SL/Target/EOD (Intraday साठी) कोणतं आधी लागतं ते तपासणे.
    df_prepared: market_data_adapter.prepare_futures_ohlcv() मधून आधीच तयार केलेला DataFrame हवा
    (bb_upper/bb_lower/bb_width/atr/vwap/vwap_std सकट).
    ict_fvg साठी structure_data दर bar ला आपोआप (prepare_structure_data ने) काढला जातो.
    """
    empty_funnel = {"bars_checked": 0, "signals_raised": 0}
    if df_prepared is None or df_prepared.empty or len(df_prepared) < min_lookback + 2:
        return {"total": 0, "signals": [], "funnel": empty_funnel}

    n = len(df_prepared)
    funnel = {"bars_checked": 0, "signals_raised": 0}
    signals = []
    eod_cutoff_time = datetime.time(eod_hour, eod_minute)
    needs_structure = strategy_obj.strategy_id == "ict_fvg"

    for i in range(min_lookback, n - 1):
        window = df_prepared.iloc[:i + 1]
        funnel["bars_checked"] += 1

        snapshot = MarketSnapshot(
            timestamp=window["timestamp"].iloc[-1],
            futures_ohlcv=window,
            structure_data=prepare_structure_data(window) if needs_structure else None,
        )
        result = strategy_obj.check_gates(snapshot)
        if not (result.is_actionable() and result.confidence >= min_confidence):
            continue
        funnel["signals_raised"] += 1

        direction = result.direction.value
        entry_price, sl_price, target_price = result.entry_price, result.stop_loss, result.target
        entry_time = window["timestamp"].iloc[-1]
        entry_date = entry_time.date() if hasattr(entry_time, "date") else None

        outcome, exit_price, exit_bars = "OPEN", None, None
        hold_end = min(i + 1 + max_hold_bars, n)
        for j in range(i + 1, hold_end):
            bar_high, bar_low = df_prepared["high"].iloc[j], df_prepared["low"].iloc[j]
            if direction == "LONG":
                hit_sl, hit_target = bar_low <= sl_price, bar_high >= target_price
            else:
                hit_sl, hit_target = bar_high >= sl_price, bar_low <= target_price
            if hit_sl:
                outcome, exit_price, exit_bars = "SL", sl_price, j - i
                break
            elif hit_target:
                outcome, exit_price, exit_bars = "TARGET", target_price, j - i
                break
            elif is_intraday and entry_date is not None:
                bar_ts = df_prepared["timestamp"].iloc[j]
                if bar_ts.date() != entry_date or bar_ts.time() >= eod_cutoff_time:
                    outcome, exit_price, exit_bars = "EOD", float(df_prepared["close"].iloc[j]), j - i
                    break

        signals.append({
            "entry_time": entry_time, "direction": direction, "confidence": round(result.confidence, 3),
            "entry_price": round(entry_price, 2) if entry_price is not None else None,
            "sl_price": round(sl_price, 2) if sl_price is not None else None,
            "target_price": round(target_price, 2) if target_price is not None else None,
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None,
            "bars_to_exit": exit_bars, "reason": result.reason,
        })

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel}

    import pandas as pd
    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"].isin(["OPEN", "EOD"])]
    decided = len(targets) + len(sls)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "funnel": funnel,
    }
