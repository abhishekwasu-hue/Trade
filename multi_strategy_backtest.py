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

import pandas as pd

from strategies.base import MarketSnapshot
from market_data_adapter import prepare_structure_data, apply_manual_sl_target
from signals import calculate_supertrend, find_support_resistance_levels

FUTURES_ONLY_STRATEGY_IDS = ("ict_fvg", "bb_squeeze", "vwap", "sr_bounce")


def _align_1h_direction(df_15m, df_1h):
    """
    df_1h वरून 1H Supertrend दिशा काढून, प्रत्येक df_15m बार ला no-lookahead पद्धतीने (merge_asof,
    direction='backward') जोडणे — आपल्याच मुख्य backtest.py मधल्याच established पद्धतीने.
    """
    if df_1h is None or df_1h.empty:
        return pd.Series([None] * len(df_15m))
    st_line, st_dir = calculate_supertrend(df_1h, period=10, multiplier=3)
    dir_lookup = pd.DataFrame({"timestamp": df_1h["timestamp"].values, "st_dir": st_dir.values})
    primary_ts = pd.DataFrame({"timestamp": df_15m["timestamp"].values})
    aligned = pd.merge_asof(
        primary_ts.sort_values("timestamp"), dir_lookup.sort_values("timestamp"), on="timestamp", direction="backward",
    )
    return aligned["st_dir"].map(lambda x: "LONG" if x == 1 else ("SHORT" if x == -1 else None))


def _align_1h_sr_levels(df_15m, df_1h, min_touches=3, sr_lookback_1h_bars=100):
    """
    sr_bounce strategy साठी — 1H वर प्रत्येक बार ला (no-lookahead, फक्त त्या क्षणापर्यंतच्या 1H इतिहासावरून)
    high-probability S/R levels काढून, प्रत्येक df_15m बार ला सर्वात अलीकडच्या 1H snapshot शी जोडणे.
    कामगिरीसाठी (performance) — प्रत्येक 1H बार ला संपूर्ण इतिहास न वापरता, फक्त अलीकडचे
    sr_lookback_1h_bars इतकेच bars वापरले जातात (ict_fvg च्याच आधीच्या performance-धड्याप्रमाणे).
    """
    if df_1h is None or df_1h.empty:
        return [None] * len(df_15m)

    n1h = len(df_1h)
    sr_at_1h = []  # प्रत्येक 1H बार साठी (timestamp, sr_dict)
    for i in range(n1h):
        win_start = max(0, i + 1 - sr_lookback_1h_bars)
        window = df_1h.iloc[win_start:i + 1]
        if len(window) < 10:
            sr_at_1h.append((df_1h["timestamp"].iloc[i], None))
            continue
        sr = find_support_resistance_levels(window, top_n=3)
        filtered = {
            "support": [s for s in sr["support"] if s["touches"] >= min_touches],
            "resistance": [r for r in sr["resistance"] if r["touches"] >= min_touches],
        }
        sr_at_1h.append((df_1h["timestamp"].iloc[i], filtered))

    sr_lookup_df = pd.DataFrame({"timestamp": [t for t, _ in sr_at_1h], "idx": range(len(sr_at_1h))})
    primary_ts = pd.DataFrame({"timestamp": df_15m["timestamp"].values})
    aligned = pd.merge_asof(
        primary_ts.sort_values("timestamp"), sr_lookup_df.sort_values("timestamp"), on="timestamp", direction="backward",
    )
    return [sr_at_1h[int(idx)][1] if pd.notna(idx) else None for idx in aligned["idx"]]


def run_strategy_backtest(df_prepared, strategy_obj, df_1h=None, min_lookback=30, max_hold_bars=50,
                            is_intraday=True, eod_hour=15, eod_minute=15, min_confidence=0.5,
                            sl_points=None, target_points=None):
    """
    एका (futures-आधारित) strategy साठी walk-forward backtest — प्रत्येक bar ला check_gates() चालवून,
    actionable सिग्नल आल्यास पुढच्या bars मध्ये SL/Target/EOD (Intraday साठी) कोणतं आधी लागतं ते तपासणे.
    df_prepared: market_data_adapter.prepare_futures_ohlcv() मधून आधीच तयार केलेला DataFrame हवा
    (bb_upper/bb_lower/bb_width/atr/vwap/vwap_std सकट).
    ict_fvg साठी structure_data दर bar ला आपोआप (prepare_structure_data ने) काढला जातो.
    df_1h: vwap strategy साठी दिशा 1H Supertrend वरून हवी असल्यास (आपल्याच मुख्य A1 Engine शी सुसंगत) —
    दिलं नाही तर vwap strategy आपोआप जुनी पद्धत (close vs vwap) वापरेल.
    sl_points/target_points: दिले असल्यास, strategy च्या स्वतःच्या (auto) SL/Target ऐवजी वापरकर्त्याने
    ठरवलेले ठराविक पॉइंट्स-अंतराचे SL/Target वापरले जातात.
    is_intraday: False दिल्यास (Swing style) — EOD force-close होत नाही, position SL/Target/max_hold_bars
    लागेपर्यंत अनेक दिवस उघडी राहू शकते (आपल्याच मुख्य A1 Engine च्या Swing स्टाईलशी सुसंगत).
    """
    empty_funnel = {"bars_checked": 0, "signals_raised": 0}
    if df_prepared is None or df_prepared.empty or len(df_prepared) < min_lookback + 2:
        return {"total": 0, "signals": [], "funnel": empty_funnel}

    n = len(df_prepared)
    funnel = {"bars_checked": 0, "signals_raised": 0}
    signals = []
    eod_cutoff_time = datetime.time(eod_hour, eod_minute)
    needs_structure = strategy_obj.strategy_id == "ict_fvg"
    needs_1h_direction = strategy_obj.strategy_id == "vwap" and df_1h is not None and not df_1h.empty
    needs_1h_sr = strategy_obj.strategy_id == "sr_bounce" and df_1h is not None and not df_1h.empty
    apply_manual_levels = sl_points is not None and target_points is not None

    # कामगिरीसाठी (performance) — संपूर्ण वाढणारा इतिहास प्रत्येक bar ला prepare_structure_data/check_gates
    # ला पुन्हा देण्याऐवजी (जे O(n²) होतं आणि 1 वर्षाच्या ict_fvg backtest ला ~257 सेकंद लागत होते),
    # फक्त अलीकडच्या MAX_LOOKBACK_BARS bars इतकाच window दिला जातो — Sweep/BOS/CHoCH/FVG/Extension साठी
    # हे पुरेसं आहे (सर्व मूळतः 'अलीकडची संरचना' या संकल्पनेवर आधारित आहेत).
    MAX_LOOKBACK_BARS = 150

    direction_1h_series = _align_1h_direction(df_prepared, df_1h) if needs_1h_direction else None
    sr_1h_list = _align_1h_sr_levels(df_prepared, df_1h, min_touches=strategy_obj.config.get("min_touches", 3)) if needs_1h_sr else None

    for i in range(min_lookback, n - 1):
        win_start = max(0, i + 1 - MAX_LOOKBACK_BARS)
        window = df_prepared.iloc[win_start:i + 1]
        funnel["bars_checked"] += 1

        extra = {}
        if needs_1h_direction:
            extra["trend_direction_1h"] = direction_1h_series.iloc[i]
        if needs_1h_sr:
            extra["sr_levels_1h"] = sr_1h_list[i]

        snapshot = MarketSnapshot(
            timestamp=window["timestamp"].iloc[-1],
            futures_ohlcv=window,
            structure_data=prepare_structure_data(window) if needs_structure else None,
            extra=extra,
        )
        result = strategy_obj.check_gates(snapshot)
        if not (result.is_actionable() and result.confidence >= min_confidence):
            continue
        funnel["signals_raised"] += 1

        if apply_manual_levels:
            ref_price = float(window["close"].iloc[-1])
            result = apply_manual_sl_target(result, sl_points, target_points, reference_price=ref_price)

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

        # P&L पॉइंट्स मध्ये (index अंतर) — दिशेनुसार समायोजित; exit_price नसेल (खरंच अजून OPEN) तर None
        if exit_price is not None:
            pnl_points = round(exit_price - entry_price, 2) if direction == "LONG" else round(entry_price - exit_price, 2)
        else:
            pnl_points = None

        signals.append({
            "entry_time": entry_time, "direction": direction, "confidence": round(result.confidence, 3),
            "entry_price": round(entry_price, 2) if entry_price is not None else None,
            "sl_price": round(sl_price, 2) if sl_price is not None else None,
            "target_price": round(target_price, 2) if target_price is not None else None,
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None,
            "bars_to_exit": exit_bars, "pnl_points": pnl_points, "reason": result.reason,
        })

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel}

    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"].isin(["OPEN", "EOD"])]
    decided = len(targets) + len(sls)
    total_pnl_points = round(sig_df["pnl_points"].dropna().sum(), 2)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "total_pnl_points": total_pnl_points,
        "funnel": funnel,
    }
