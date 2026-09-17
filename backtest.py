"""Walk-forward, no-lookahead signal backtesting (directional accuracy + Risk:Reward Target/SL framing)."""
import datetime
import pandas as pd

from signals import (
    classify_market_structure, detect_break, detect_pullback_retest,
    calculate_supertrend, calculate_rsi, check_pattern_rsi_gate,
    check_price_action_strategy, check_indicator_strategy,
    find_swings, detect_trendline, analyze_chart_zones,
)
from sr_dynamic import compute_dynamic_sr

def limit_to_last_n_trading_days(df, n_days=100):
    """डेटाला शेवटच्या n_days ट्रेडिंग दिवसांपुरतं मर्यादित करणे — कॅलेंडर दिवस नाही, फक्त बाजार उघडलेले दिवस मोजून."""
    if df.empty:
        return df
    unique_dates = sorted(df["timestamp"].dt.date.unique())
    if len(unique_dates) <= n_days:
        return df
    cutoff_date = unique_dates[-n_days]
    return df[df["timestamp"].dt.date >= cutoff_date].reset_index(drop=True)

def run_signal_backtest(df, structure_order=3, forward_bars=5, min_move_pct=0.1, min_lookback=30, max_bars=None):
    """
    ऐतिहासिक इंडेक्स किंमत डेटावर walk-forward पद्धतीने (कोणतीही भविष्यातील माहिती न वापरता — no lookahead)
    Market Structure + Break + Pullback/Retest लॉजिक चालवून, प्रत्येक सिग्नलनंतर पुढच्या forward_bars
    बार्समध्ये किंमत खरंच अपेक्षित दिशेने सरकली का ते तपासणे.

    महत्त्वाची मर्यादा (हे स्पष्टपणे लक्षात ठेवा): हे फक्त दिशेच्या (directional) सिग्नलची अचूकता तपासतं —
    प्रत्यक्ष credit spread च्या पैशांचा backtest नाही, कारण जुन्या (expired) तारखांचा actual option
    premium डेटा Upstox कडून मिळत नाही (फक्त सध्याच्या/चालू expiry चा option chain उपलब्ध आहे).
    """
    if df.empty or len(df) < min_lookback + forward_bars + 1:
        return {"total": 0, "signals": []}

    n = len(df)
    end_idx = n - forward_bars
    start_idx = min_lookback
    if max_bars is not None and (end_idx - start_idx) > max_bars:
        start_idx = end_idx - max_bars  # फार मोठा डेटासेट असेल तर अलीकडच्या max_bars पुरतंच मर्यादित ठेवणे

    signals = []
    for i in range(start_idx, end_idx):
        window = df.iloc[:i + 1]  # फक्त आत्तापर्यंतचाच डेटा — lookahead टाळण्यासाठी हे अत्यावश्यक
        structure = classify_market_structure(window, order=structure_order)
        if structure["structure"] == "INSUFFICIENT_DATA":
            continue

        if structure["structure"].startswith("HH/HL"):
            direction = "BULLISH"
        elif structure["structure"].startswith("LH/LL"):
            direction = "BEARISH"
        else:
            continue  # RANGING मध्ये directional सिग्नल घेतला जात नाही

        broke, broken_level = detect_break(window, structure, direction)
        if not broke:
            continue
        pulled_back, retested = detect_pullback_retest(window, broken_level, direction)
        if not (pulled_back and retested):
            continue

        entry_price = float(window["close"].iloc[-1])
        entry_time = window["timestamp"].iloc[-1]
        future_price = float(df["close"].iloc[i + forward_bars])
        move_pct = round((future_price - entry_price) / entry_price * 100, 3)
        correct = (move_pct >= min_move_pct) if direction == "BULLISH" else (move_pct <= -min_move_pct)

        signals.append({
            "entry_time": entry_time, "direction": direction, "entry_price": round(entry_price, 2),
            "exit_price": round(future_price, 2), "move_pct": move_pct, "correct": bool(correct),
        })

    if not signals:
        return {"total": 0, "signals": []}

    sig_df = pd.DataFrame(signals)
    wins = sig_df[sig_df["correct"]]
    losses = sig_df[~sig_df["correct"]]

    return {
        "total": len(sig_df),
        "signals": signals,
        "win_rate": round(len(wins) / len(sig_df) * 100, 1),
        "avg_move_pct": round(sig_df["move_pct"].mean(), 3),
        "avg_win_move_pct": round(wins["move_pct"].mean(), 3) if not wins.empty else None,
        "avg_loss_move_pct": round(losses["move_pct"].mean(), 3) if not losses.empty else None,
        "bullish_count": int((sig_df["direction"] == "BULLISH").sum()),
        "bearish_count": int((sig_df["direction"] == "BEARISH").sum()),
    }

def run_signal_backtest_rr(df, structure_order=3, lookback_swings=4, tolerance_pct=0.3, retest_lookback=10,
                            sl_pct=0.5, rr_ratio=2.0, min_lookback=30, max_bars=None, max_hold_bars=50,
                            df_direction=None, use_pattern_rsi_gate=False):
    """
    Risk:Reward आधारित walk-forward backtest (no lookahead) — प्रत्येक सिग्नलनंतर, दिलेल्या SL% (एंट्री
    किमतीपासूनचं अंतर) व Risk:Reward गुणोत्तरावरून Target ठरवून, पुढे बार-बार-बार चालत जाऊन आधी काय
    touch होतं — SL आधी लागला (तोटा) की Target आधी लागला (नफा) — हे तपासणे. max_hold_bars च्या आत
    काहीच न लागल्यास 'OPEN' गणलं जातं. एकाच बारमध्ये दोन्ही touch झाल्यास पुराणमतवादी गृहीतक: SL आधी लागला असं मानणे
    (OHLC वरून intra-bar क्रम कळत नाही, त्यामुळे सुरक्षित बाजूने गृहीत धरणे).

    lookback_swings: Market Structure साठी किती सलग swing highs/lows एकाच दिशेने हवेत (कमी = सैल, जास्त
    सिग्नल्स). tolerance_pct/retest_lookback: Pullback-Retest किती काटेकोर असावा.

    df_direction (ऐच्छिक): वेगळी (उदा. 1H) टाईमफ्रेम — दिली तर दिशा तिच्यावरील Supertrend वरून ठरते
    (Live pipeline शी सुसंगत), Market Structure (HH/HL) वरून नाही. no-lookahead राखण्यासाठी प्रत्येक df
    च्या बारला merge_asof (direction='backward') ने फक्त त्या क्षणी आधीच बंद झालेला शेवटचा df_direction
    बार जोडला जातो. दिली नाही तर आधीचंच वर्तन (Market Structure वरून दिशा) — मागील टेस्ट्सशी सुसंगत.

    use_pattern_rsi_gate: True असेल तर Break+Pullback+Retest नंतर, अतिरिक्त गेट म्हणून Candlestick
    Pattern (Hammer/Engulfing/Shooting Star) + RSI(df वरून, 30-50 BULLISH / 55-75 BEARISH) हेही तपासलं
    जातं (जागा घेत नाही, अतिरिक्त अट).

    'funnel' आणि 'structure_breakdown' निकालात नेहमी असतात (सिग्नल्स सापडले नाहीत तरीही).
    """
    empty_funnel = {"bars_checked": 0, "structure_directional": 0, "broke": 0, "pulled_back_and_retested": 0, "pattern_rsi_passed": 0}
    empty_breakdown = {"RANGING_or_MIXED": 0, "INSUFFICIENT_DATA": 0, "HH/HL": 0, "LH/LL": 0}
    if df.empty or len(df) < min_lookback + 2:
        return {"total": 0, "signals": [], "funnel": empty_funnel, "structure_breakdown": empty_breakdown}

    n = len(df)
    end_idx = n - 1
    start_idx = min_lookback
    if max_bars is not None and (end_idx - start_idx) > max_bars:
        start_idx = end_idx - max_bars

    # --- दुहेरी-टाईमफ्रेम दिशा (ऐच्छिक) — फक्त एकदाच पूर्ण df_direction वर Supertrend काढून, no-lookahead align ---
    direction_series = None
    if df_direction is not None and not df_direction.empty:
        st_line_dir, st_dir_dir = calculate_supertrend(df_direction, period=10, multiplier=3)
        dir_lookup = pd.DataFrame({"timestamp": df_direction["timestamp"].values, "st_dir": st_dir_dir.values})
        primary_ts = pd.DataFrame({"timestamp": df["timestamp"].values})
        aligned = pd.merge_asof(
            primary_ts.sort_values("timestamp"), dir_lookup.sort_values("timestamp"),
            on="timestamp", direction="backward",
        )
        direction_series = aligned["st_dir"]

    # --- Pattern+RSI गेटसाठी RSI (df वरूनच, जी टाईमफ्रेम पास केली तीच वापरली जाते) ---
    rsi_for_pattern_gate = calculate_rsi(df, period=14) if use_pattern_rsi_gate else None

    funnel = {"bars_checked": 0, "structure_directional": 0, "broke": 0, "pulled_back_and_retested": 0, "pattern_rsi_passed": 0}
    structure_breakdown = {"RANGING_or_MIXED": 0, "INSUFFICIENT_DATA": 0, "HH/HL": 0, "LH/LL": 0}

    signals = []
    for i in range(start_idx, end_idx):
        window = df.iloc[:i + 1]
        funnel["bars_checked"] += 1
        structure = classify_market_structure(window, order=structure_order, lookback_swings=lookback_swings)

        if direction_series is not None:
            # दिशा 1H Supertrend वरून (Market Structure फक्त break-level साठी वापरली जाते, दिशा ठरवायला नाही)
            st_dir_now = direction_series.iloc[i]
            if pd.isna(st_dir_now) or structure["structure"] == "INSUFFICIENT_DATA":
                structure_breakdown["INSUFFICIENT_DATA"] += 1
                continue
            direction = "BULLISH" if st_dir_now == 1 else "BEARISH"
            structure_breakdown["HH/HL" if direction == "BULLISH" else "LH/LL"] += 1
        else:
            # जुनं वर्तन — Market Structure (HH/HL/LH-LL) वरूनच दिशा
            if structure["structure"] == "INSUFFICIENT_DATA":
                structure_breakdown["INSUFFICIENT_DATA"] += 1
                continue
            if structure["structure"].startswith("HH/HL"):
                direction = "BULLISH"
                structure_breakdown["HH/HL"] += 1
            elif structure["structure"].startswith("LH/LL"):
                direction = "BEARISH"
                structure_breakdown["LH/LL"] += 1
            else:
                structure_breakdown["RANGING_or_MIXED"] += 1
                continue
        funnel["structure_directional"] += 1

        broke, broken_level = detect_break(window, structure, direction)
        if not broke:
            continue
        funnel["broke"] += 1

        # नवीन एकत्रित रणनीतीत (1H दिशा + Pattern गेट दोन्ही एकत्र) Pullback+Retest तपासलं जात नाही —
        # युजरने स्पष्ट सांगितल्याप्रमाणे. इतर सर्व स्थितींमध्ये (डीफॉल्ट backtest, फक्त एकच टॉगल चालू)
        # Pullback+Retest पूर्वीसारखंच लागू होतं — इथे काहीही बदल नाही.
        combined_new_strategy = (direction_series is not None) and use_pattern_rsi_gate
        if combined_new_strategy:
            pulled_back, retested = True, True
        else:
            pulled_back, retested = detect_pullback_retest(window, broken_level, direction, tolerance_pct=tolerance_pct, lookback=retest_lookback)
        if not (pulled_back and retested):
            continue
        funnel["pulled_back_and_retested"] += 1

        if use_pattern_rsi_gate:
            rsi_window = rsi_for_pattern_gate.iloc[:i + 1]
            gate_ok, _pattern, _rsi_val = check_pattern_rsi_gate(window, rsi_window, direction)
            if not gate_ok:
                continue
            funnel["pattern_rsi_passed"] += 1

        entry_price = float(window["close"].iloc[-1])
        entry_time = window["timestamp"].iloc[-1]
        if direction == "BULLISH":
            sl_price = entry_price * (1 - sl_pct / 100)
            risk = entry_price - sl_price
            target_price = entry_price + risk * rr_ratio
        else:
            sl_price = entry_price * (1 + sl_pct / 100)
            risk = sl_price - entry_price
            target_price = entry_price - risk * rr_ratio

        outcome = "OPEN"
        exit_price = None
        exit_bars = None
        hold_end = min(i + 1 + max_hold_bars, n)
        for j in range(i + 1, hold_end):
            bar_high = df["high"].iloc[j]
            bar_low = df["low"].iloc[j]
            if direction == "BULLISH":
                hit_target = bar_high >= target_price
                hit_sl = bar_low <= sl_price
            else:
                hit_target = bar_low <= target_price
                hit_sl = bar_high >= sl_price
            if hit_sl:
                outcome, exit_price, exit_bars = "SL", sl_price, j - i
                break
            elif hit_target:
                outcome, exit_price, exit_bars = "TARGET", target_price, j - i
                break

        # P&L पॉइंट्स मध्ये (index अंतर) — दिशेनुसार समायोजित; exit_price नसेल (खरंच अजून OPEN) तर None
        if exit_price is not None:
            pnl_points = round(exit_price - entry_price, 2) if direction == "BULLISH" else round(entry_price - exit_price, 2)
        else:
            pnl_points = None

        signals.append({
            "entry_time": entry_time, "direction": direction, "entry_price": round(entry_price, 2),
            "sl_price": round(sl_price, 2), "target_price": round(target_price, 2),
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None, "bars_to_exit": exit_bars,
            "pnl_points": pnl_points,
        })

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel, "structure_breakdown": structure_breakdown}

    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"] == "OPEN"]
    total_pnl_points = round(sig_df["pnl_points"].dropna().sum(), 2)
    decided = len(targets) + len(sls)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "bullish_count": int((sig_df["direction"] == "BULLISH").sum()),
        "bearish_count": int((sig_df["direction"] == "BEARISH").sum()),
        "total_pnl_points": total_pnl_points,
        "funnel": funnel, "structure_breakdown": structure_breakdown,
    }


def apply_slippage(price, direction, action, slippage_pct=0.05):
    """
    🎓 Slippage Modeling — वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (backtest आर्थिक वास्तवता).
    Slippage नेहमी व्यापाऱ्याच्याच विरोधात काम करतो (bid-ask spread + market impact):
      - BULLISH Entry (विकत घेणे) / BEARISH Exit (विकत घेणे परत) -> थोडं जास्त द्यावं लागतं
      - BULLISH Exit (विकणे) / BEARISH Entry (विकणे) -> थोडं कमी मिळतं
    slippage_pct=0 (डीफॉल्ट) दिल्यास कुठलाही बदल नाही — पूर्णपणे backward-compatible, जुने backtest
    निकाल याच फंक्शनने बदलत नाहीत जोपर्यंत स्पष्टपणे slippage_pct>0 दिला जात नाही.
    """
    if slippage_pct == 0:
        return price
    factor = slippage_pct / 100
    is_buy = (direction == "BULLISH" and action == "ENTRY") or (direction == "BEARISH" and action == "EXIT")
    return price * (1 + factor) if is_buy else price * (1 - factor)


def run_signal_backtest_v2(df, df_direction, strategy="price_action", sl_pct=0.5, rr_ratio=2.0,
                             min_lookback=30, max_bars=None, max_hold_bars=50,
                             sr_window=20, rsi_oversold=30, rsi_overbought=70,
                             sl_buffer_pct=0.1, min_rr=2.0, retest_tolerance_pct=0.15, reversal_lookback=3,
                             is_intraday=True, eod_hour=15, eod_minute=15, slippage_pct=0):
    """
    नवीन Signal Engine (V2) — दोन स्वतंत्र, संपूर्ण रणनीती (दिशा दोन्हीसाठी 1H Supertrend वरून,
    no-lookahead merge_asof ने अलाइन केलेली):

    "price_action": Support/Resistance (Rolling Window) + RSI Oversold/Overbought/Divergence +
                    Candlestick Reversal + Breakout Entry (check_price_action_strategy)
    "indicator": RSI(15M, 25-55 Bullish / 45-75 Bearish) + Candlestick Rejection/Engulfing (check_indicator_strategy)
    """
    empty_funnel = {"bars_checked": 0, "structure_directional": 0, "entry_passed": 0}
    if df.empty or df_direction is None or df_direction.empty or len(df) < min_lookback + 2:
        return {"total": 0, "signals": [], "funnel": empty_funnel}

    n = len(df)
    end_idx = n - 1
    start_idx = min_lookback
    if max_bars is not None and (end_idx - start_idx) > max_bars:
        start_idx = end_idx - max_bars

    st_line_dir, st_dir_dir = calculate_supertrend(df_direction, period=10, multiplier=3)
    dir_lookup = pd.DataFrame({"timestamp": df_direction["timestamp"].values, "st_dir": st_dir_dir.values})
    primary_ts = pd.DataFrame({"timestamp": df["timestamp"].values})
    aligned = pd.merge_asof(
        primary_ts.sort_values("timestamp"), dir_lookup.sort_values("timestamp"), on="timestamp", direction="backward",
    )
    direction_series = aligned["st_dir"]

    rsi_series_full = calculate_rsi(df, period=14)  # दोन्ही रणनीतींना आता RSI लागतो

    funnel = {"bars_checked": 0, "structure_directional": 0, "entry_passed": 0}
    signals = []
    for i in range(start_idx, end_idx):
        # कामगिरीसाठी (performance) — संपूर्ण वाढणारा इतिहास प्रत्येक bar ला पुन्हा स्कॅन करण्याऐवजी (जे O(n²)
        # होतं आणि मोठ्या backtest मध्ये अत्यंत संथ ठरत होतं), फक्त अलीकडच्या MAX_LOOKBACK_BARS bars इतकाच
        # window strategy-check ला दिला जातो — S/R/RSI/Trendline साठी हे पुरेसं आहे.
        MAX_LOOKBACK_BARS = 150
        win_start = max(0, i + 1 - MAX_LOOKBACK_BARS)
        window = df.iloc[win_start:i + 1]
        funnel["bars_checked"] += 1
        st_dir_now = direction_series.iloc[i]
        if pd.isna(st_dir_now):
            continue
        direction = "BULLISH" if st_dir_now == 1 else "BEARISH"
        funnel["structure_directional"] += 1
        rsi_window = rsi_series_full.iloc[win_start:i + 1]

        if strategy == "price_action":
            entry_ok, _detail = check_price_action_strategy(
                window, direction, rsi_series=rsi_window, sr_window=sr_window,
                rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
                sl_buffer_pct=sl_buffer_pct, min_rr=min_rr,
                retest_tolerance_pct=retest_tolerance_pct, reversal_lookback=reversal_lookback,
            )
        else:
            entry_ok, _detail = check_indicator_strategy(window, rsi_window, direction)

        if not entry_ok:
            continue
        funnel["entry_passed"] += 1

        entry_price = float(window["close"].iloc[-1])
        entry_price = apply_slippage(entry_price, direction, "ENTRY", slippage_pct)
        entry_time = window["timestamp"].iloc[-1]
        if direction == "BULLISH":
            sl_price = entry_price * (1 - sl_pct / 100)
            risk = entry_price - sl_price
            target_price = entry_price + risk * rr_ratio
        else:
            sl_price = entry_price * (1 + sl_pct / 100)
            risk = sl_price - entry_price
            target_price = entry_price - risk * rr_ratio

        outcome = "OPEN"
        exit_price = None
        exit_bars = None
        eod_cutoff_time = datetime.time(eod_hour, eod_minute)
        entry_date = entry_time.date() if hasattr(entry_time, "date") else None
        hold_end = min(i + 1 + max_hold_bars, n)
        for j in range(i + 1, hold_end):
            bar_high = df["high"].iloc[j]
            bar_low = df["low"].iloc[j]
            if direction == "BULLISH":
                hit_target = bar_high >= target_price
                hit_sl = bar_low <= sl_price
            else:
                hit_target = bar_low <= target_price
                hit_sl = bar_high >= sl_price
            if hit_sl:
                outcome, exit_price, exit_bars = "SL", sl_price, j - i
                break
            elif hit_target:
                outcome, exit_price, exit_bars = "TARGET", target_price, j - i
                break
            elif is_intraday and entry_date is not None:
                # Intraday साठी -- SL/Target दोन्ही चुकले, आणि EOD कट-ऑफ (उदा. 15:15) पार केला किंवा
                # दुसऱ्याच दिवशी पोहोचलो, तर इथेच force-close (खऱ्या trading सारखं -- रात्रभर उघडं नाही).
                bar_ts = df["timestamp"].iloc[j]
                bar_date = bar_ts.date()
                bar_time = bar_ts.time()
                if bar_date != entry_date or bar_time >= eod_cutoff_time:
                    outcome, exit_price, exit_bars = "EOD", float(df["close"].iloc[j]), j - i
                    break

        if exit_price is not None:
            exit_price = apply_slippage(exit_price, direction, "EXIT", slippage_pct)

        # P&L पॉइंट्स मध्ये (index अंतर) — दिशेनुसार समायोजित; exit_price नसेल (खरंच अजून OPEN) तर None
        if exit_price is not None:
            pnl_points = round(exit_price - entry_price, 2) if direction == "BULLISH" else round(entry_price - exit_price, 2)
        else:
            pnl_points = None

        signals.append({
            "entry_time": entry_time, "direction": direction, "entry_price": round(entry_price, 2),
            "sl_price": round(sl_price, 2), "target_price": round(target_price, 2),
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None,
            "bars_to_exit": exit_bars, "pnl_points": pnl_points,
        })

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel}

    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"] == "OPEN"]
    decided = len(targets) + len(sls)
    total_pnl_points = round(sig_df["pnl_points"].dropna().sum(), 2)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "bullish_count": int((sig_df["direction"] == "BULLISH").sum()),
        "bearish_count": int((sig_df["direction"] == "BEARISH").sum()),
        "total_pnl_points": total_pnl_points,
        "funnel": funnel,
    }


def _classic_sr_touch_candidates(df, timeframe_label, rsi_series, rsi_neutral, touch_tolerance_pct,
                                   sr_prd, sr_channel_w_pct, sr_maxnumsr, sr_min_strength, min_lookback_days,
                                   swing_order=3, swing_confluence_enabled=False, swing_tolerance_pct=0.15,
                                   demand_supply_gate_enabled=False, trendline_gate_enabled=False,
                                   trendline_lookback_swings=4):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Classical Support/Resistance Reversal strategy —
    प्रस्तावित तिसरी strategy, 5M+15M) — एका टाईमफ्रेमच्या df वर, दर ट्रेडिंग-दिवशी (आदल्या
    दिवसापर्यंतच्याच डेटावरून, lookahead नाही — नेमकं जसं प्रत्यक्ष nightly cron रोज रात्री करतो)
    sr_dynamic.compute_dynamic_sr() (तोच classical Pivot-clustering अल्गोरिदम जो लाईव्ह Market Zones
    साठी वापरला जातो) ने S/R levels पुन्हा काढून, त्या दिवसाच्या प्रत्येक bar वर कुठला level touch
    झाला आणि RSI(त्याच टाईमफ्रेमचा 14-period) दिशेशी सुसंगत होता (Support/BULLISH -> RSI<rsi_neutral,
    Resistance/BEARISH -> RSI>rsi_neutral) ते सापडणे. दिशा साठवलेल्या classification वरून नाही, तर
    प्रत्येक touch-बारच्या close किमतीवरून ठरते (dynamic_sr_instant_trader.py सारखंच — "stale" label
    टाळण्यासाठी).

    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Refinement — Swing High/Low, Demand/Supply,
    Trendline) — RSI गेट नंतर, तीन अतिरिक्त, स्वतंत्रपणे togglable confluence गेट्स (सर्व डीफॉल्ट बंद
    — backward-compatible, चालू केल्याशिवाय जुनाच निकाल):
      - swing_confluence_enabled: touch झालेला level हा नुकत्याच झालेल्या खऱ्या swing low (Support)
        / swing high (Resistance) च्या (signals.find_swings) जवळ (swing_tolerance_pct% च्या आत) आहे
        का — म्हणजे नुसता clustered pivot-zone नाही, तर ताजा, खरा structural point.
      - demand_supply_gate_enabled: level हा signals.analyze_chart_zones() च्या Demand zone (Support)
        / Supply zone (Resistance) च्या आत आहे का (शेवटच्या swing low/high भोवतीचा ±0.3% पट्टा).
      - trendline_gate_enabled: त्याच दिशेची trendline (signals.detect_trendline — Support साठी
        Ascending, Resistance साठी Descending) अस्तित्वात असून BROKEN असेल, तरच signal अडवला जातो
        (पुरेसा डेटा नसेल/trendline सापडली नसेल तर गेट आपोआप पास — check_trend_signal() च्या
        फॉलबॅक-तत्त्वासारखंच).
    प्रत्येक गेट फक्त RSI-पास झालेल्या (आधीच लहान संख्येच्या) candidates वरच चालतो — कामगिरीसाठी
    प्रत्येक बारवर नाही.
    रिटर्न: (candidates: [{"timestamp","row_idx","direction","level","timeframe"}, ...], funnel dict).
    """
    candidates = []
    funnel = {
        "touches": 0, "rsi_passed": 0, "swing_passed": 0, "demand_supply_passed": 0, "trendline_passed": 0,
    }
    if df is None or df.empty:
        return candidates, funnel

    df = df.reset_index(drop=True)
    dates = df["timestamp"].dt.date
    unique_dates = sorted(dates.unique())
    if len(unique_dates) <= min_lookback_days:
        return candidates, funnel

    for d in unique_dates[min_lookback_days:]:
        hist = df[dates < d]
        if hist.empty:
            continue
        zones = compute_dynamic_sr(
            hist, prd=sr_prd, channel_w_pct=sr_channel_w_pct, maxnumsr=sr_maxnumsr,
            min_strength=sr_min_strength, current_price=float(hist["close"].iloc[-1]),
        )
        levels = [z["level"] for z in zones["support"]] + [z["level"] for z in zones["resistance"]]
        if not levels:
            continue

        for i in df.index[dates == d]:
            rsi_val = rsi_series.iloc[i]
            if pd.isna(rsi_val):
                continue
            bar_high, bar_low, bar_close = df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
            for level in levels:
                buffer = level * touch_tolerance_pct / 100
                if not (bar_low <= level + buffer and bar_high >= level - buffer):
                    continue
                funnel["touches"] += 1
                direction = "BULLISH" if bar_close >= level else "BEARISH"
                rsi_ok = (rsi_val < rsi_neutral) if direction == "BULLISH" else (rsi_val > rsi_neutral)
                if not rsi_ok:
                    continue
                funnel["rsi_passed"] += 1

                window = None  # lazily तयार — फक्त एखादा confluence गेट चालू असेल तरच लागतो

                if swing_confluence_enabled:
                    window = df.iloc[:i + 1]
                    sh_idx, sl_idx = find_swings(window, order=swing_order)
                    ref_idx = sl_idx if direction == "BULLISH" else sh_idx
                    if not ref_idx:
                        continue
                    nearest_swing_price = window["low" if direction == "BULLISH" else "high"].iloc[ref_idx[-1]]
                    if abs(nearest_swing_price - level) > level * swing_tolerance_pct / 100:
                        continue
                funnel["swing_passed"] += 1

                if demand_supply_gate_enabled:
                    window = window if window is not None else df.iloc[:i + 1]
                    chart_zones = analyze_chart_zones(window, order=swing_order)
                    zone = chart_zones["demand_zone"] if direction == "BULLISH" else chart_zones["supply_zone"]
                    if zone is None or not (zone[0] <= level <= zone[1]):
                        continue
                funnel["demand_supply_passed"] += 1

                if trendline_gate_enabled:
                    window = window if window is not None else df.iloc[:i + 1]
                    tl = detect_trendline(
                        window, swing_type=("low" if direction == "BULLISH" else "high"),
                        lookback_swings=trendline_lookback_swings, order=swing_order,
                    )
                    if tl is not None and tl.get("valid") and tl["status"] == "BROKEN":
                        continue
                funnel["trendline_passed"] += 1

                candidates.append({
                    "timestamp": df["timestamp"].iloc[i], "row_idx": i, "direction": direction,
                    "level": round(float(level), 2), "timeframe": timeframe_label,
                })
    return candidates, funnel


def run_classic_sr_reversal_backtest(df_5m, df_15m, sl_spot_pct=0.4, target_spot_pct=0.8, rsi_neutral=50,
                                       touch_tolerance_pct=0.05, sr_prd=10, sr_channel_w_pct=10,
                                       sr_maxnumsr=5, sr_min_strength=2, min_lookback_days=5,
                                       max_hold_bars=50, cooldown_minutes=30, swing_order=3,
                                       swing_confluence_enabled=False, swing_tolerance_pct=0.15,
                                       demand_supply_gate_enabled=False, trendline_gate_enabled=False,
                                       trendline_lookback_swings=4):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — प्रस्तावित तिसरी strategy ("Classical Support/
    Resistance Reversal", 5M+15M) साठी walk-forward, no-lookahead backtest. Support touch (RSI<
    rsi_neutral) -> BULLISH (लाईव्हमध्ये Bull Put Spread); Resistance touch (RSI>rsi_neutral) ->
    BEARISH (Bear Call Spread) — दोन्ही टाईमफ्रेम्स "first touch wins" पद्धतीने एकत्र पूल केलेल्या
    (dynamic_sr_instant_trader.py सारखंच), एकाच वेळी फक्त एकच उघडी position + SL/Target नंतर
    cooldown_minutes (डीफॉल्ट 30, इतर दोन्ही strategies प्रमाणेच).

    🎓 Entry Refinement (सर्व डीफॉल्ट बंद — चालू केल्याशिवाय आधीचाच निकाल) — RSI गेटनंतर तीन अतिरिक्त,
    स्वतंत्र confluence गेट्स (तपशील _classic_sr_touch_candidates() च्या docstring मध्ये):
    swing_confluence_enabled (नुकत्याच झालेल्या खऱ्या Swing High/Low जवळ आहे का), demand_supply_gate_enabled
    (Demand/Supply zone च्या आत आहे का), trendline_gate_enabled (त्याच दिशेची Trendline BROKEN नाहीये ना).

    entry_spot (SL/Target %-गणनेचा आधार) हा नेमका touch झालेला level आहे — trading_engine.py च्या
    evaluate_point_spot_exit() मध्ये entry_level_price कसा वापरला जातो, त्याच पद्धतीने (नेमकी
    fill-किंमत नाही).

    महत्त्वाच्या मर्यादा:
      1. हे फक्त INDEX स्पॉट %-वरचं SL/Target सिम्युलेशन आहे — प्रत्यक्ष credit-spread च्या ₹ P&L चा
         backtest नाही (इतर सर्व backtest प्रमाणेच — जुन्या expiry चा खरा option-premium इतिहास
         Upstox कडून मिळत नाही).
      2. TSL-to-Breakeven इथे सिम्युलेट केलेलं नाही (bar-level OHLC वरून त्याची नेमकी वेळ/किंमत
         विश्वासार्हपणे ठरवता येत नाही) — फक्त सरळ SL/Target. प्रत्यक्ष PAPER/LIVE आवृत्तीत मात्र
         इतर दोन्ही strategies प्रमाणेच केंद्रीकृत evaluate_point_spot_exit() (पूर्ण TSL-to-Breakeven
         सकट) वापरलं जाईल.

    रिटर्न (run_signal_backtest_rr() च्या shape शी सुसंगत, पण pnl_points ऐवजी pnl_pct — कारण इथे
    entry किंमत level-नुसार खूप वेगवेगळी असते, % हीच योग्य तुलना): {"total","signals","target_count",
    "sl_count","open_count","win_rate","bullish_count","bearish_count","touch_5m_count",
    "touch_15m_count","total_pnl_pct","funnel"}.
    """
    empty_funnel = {
        "touches_5m": 0, "rsi_passed_5m": 0, "swing_passed_5m": 0, "demand_supply_passed_5m": 0, "trendline_passed_5m": 0,
        "touches_15m": 0, "rsi_passed_15m": 0, "swing_passed_15m": 0, "demand_supply_passed_15m": 0, "trendline_passed_15m": 0,
    }
    df_5m = df_5m if df_5m is not None else pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
    df_15m = df_15m if df_15m is not None else pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
    if df_5m.empty and df_15m.empty:
        return {"total": 0, "signals": [], "funnel": empty_funnel}

    df_5m = df_5m.reset_index(drop=True)
    df_15m = df_15m.reset_index(drop=True)
    rsi_5m = calculate_rsi(df_5m, period=14) if not df_5m.empty else pd.Series(dtype=float)
    rsi_15m = calculate_rsi(df_15m, period=14) if not df_15m.empty else pd.Series(dtype=float)

    refinement_kwargs = dict(
        swing_order=swing_order, swing_confluence_enabled=swing_confluence_enabled,
        swing_tolerance_pct=swing_tolerance_pct, demand_supply_gate_enabled=demand_supply_gate_enabled,
        trendline_gate_enabled=trendline_gate_enabled, trendline_lookback_swings=trendline_lookback_swings,
    )
    cand_5m, funnel_5m = _classic_sr_touch_candidates(
        df_5m, "5M", rsi_5m, rsi_neutral, touch_tolerance_pct, sr_prd, sr_channel_w_pct, sr_maxnumsr,
        sr_min_strength, min_lookback_days, **refinement_kwargs,
    )
    cand_15m, funnel_15m = _classic_sr_touch_candidates(
        df_15m, "15M", rsi_15m, rsi_neutral, touch_tolerance_pct, sr_prd, sr_channel_w_pct, sr_maxnumsr,
        sr_min_strength, min_lookback_days, **refinement_kwargs,
    )
    funnel = {}
    for key, val in funnel_5m.items():
        funnel[f"{key}_5m"] = val
    for key, val in funnel_15m.items():
        funnel[f"{key}_15m"] = val

    all_candidates = sorted(cand_5m + cand_15m, key=lambda c: c["timestamp"])
    if not all_candidates:
        return {"total": 0, "signals": [], "funnel": funnel}

    df_by_tf = {"5M": df_5m, "15M": df_15m}
    cooldown_delta = datetime.timedelta(minutes=cooldown_minutes)

    signals = []
    blocked_until = None
    for cand in all_candidates:
        if blocked_until is not None and cand["timestamp"] < blocked_until:
            continue  # आधीची position अजून उघडी/cooldown मध्ये — पुढचा candidate बघा

        tf_df = df_by_tf[cand["timeframe"]]
        i = cand["row_idx"]
        direction = cand["direction"]
        entry_spot = cand["level"]
        entry_time = cand["timestamp"]

        if direction == "BULLISH":
            sl_price = entry_spot * (1 - sl_spot_pct / 100)
            target_price = entry_spot * (1 + target_spot_pct / 100)
        else:
            sl_price = entry_spot * (1 + sl_spot_pct / 100)
            target_price = entry_spot * (1 - target_spot_pct / 100)

        outcome, exit_price, exit_time, bars_to_exit = "OPEN", None, None, None
        n = len(tf_df)
        hold_end = min(i + 1 + max_hold_bars, n)
        for j in range(i + 1, hold_end):
            bar_high, bar_low = tf_df["high"].iloc[j], tf_df["low"].iloc[j]
            if direction == "BULLISH":
                hit_target, hit_sl = bar_high >= target_price, bar_low <= sl_price
            else:
                hit_target, hit_sl = bar_low <= target_price, bar_high >= sl_price
            if hit_sl:
                outcome, exit_price, exit_time, bars_to_exit = "SL", sl_price, tf_df["timestamp"].iloc[j], j - i
                break
            elif hit_target:
                outcome, exit_price, exit_time, bars_to_exit = "TARGET", target_price, tf_df["timestamp"].iloc[j], j - i
                break

        if exit_time is None:
            exit_time = tf_df["timestamp"].iloc[hold_end - 1] if hold_end > i + 1 else entry_time

        if exit_price is not None:
            pnl_pct = (
                round((exit_price - entry_spot) / entry_spot * 100, 3) if direction == "BULLISH"
                else round((entry_spot - exit_price) / entry_spot * 100, 3)
            )
        else:
            pnl_pct = None

        signals.append({
            "entry_time": entry_time, "timeframe": cand["timeframe"], "direction": direction,
            "level": entry_spot, "sl_price": round(sl_price, 2), "target_price": round(target_price, 2),
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None,
            "exit_time": exit_time, "bars_to_exit": bars_to_exit, "pnl_pct": pnl_pct,
        })
        blocked_until = exit_time + cooldown_delta

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel}

    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"] == "OPEN"]
    decided = len(targets) + len(sls)
    total_pnl_pct = round(sig_df["pnl_pct"].dropna().sum(), 2)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "bullish_count": int((sig_df["direction"] == "BULLISH").sum()),
        "bearish_count": int((sig_df["direction"] == "BEARISH").sum()),
        "touch_5m_count": int((sig_df["timeframe"] == "5M").sum()),
        "touch_15m_count": int((sig_df["timeframe"] == "15M").sum()),
        "total_pnl_pct": total_pnl_pct,
        "funnel": funnel,
    }
