"""Walk-forward, no-lookahead signal backtesting (directional accuracy + Risk:Reward Target/SL framing)."""
import datetime
import pandas as pd

from signals import (
    classify_market_structure, detect_break, detect_pullback_retest,
    calculate_supertrend, calculate_rsi, check_pattern_rsi_gate,
    check_price_action_strategy, check_indicator_strategy,
)

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

        signals.append({
            "entry_time": entry_time, "direction": direction, "entry_price": round(entry_price, 2),
            "sl_price": round(sl_price, 2), "target_price": round(target_price, 2),
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None, "bars_to_exit": exit_bars,
        })

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel, "structure_breakdown": structure_breakdown}

    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"] == "OPEN"]
    decided = len(targets) + len(sls)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "bullish_count": int((sig_df["direction"] == "BULLISH").sum()),
        "bearish_count": int((sig_df["direction"] == "BEARISH").sum()),
        "funnel": funnel, "structure_breakdown": structure_breakdown,
    }


def run_signal_backtest_v2(df, df_direction, strategy="price_action", sl_pct=0.5, rr_ratio=2.0,
                             min_lookback=30, max_bars=None, max_hold_bars=50,
                             sr_window=20, rsi_oversold=30, rsi_overbought=70,
                             sl_buffer_pct=0.1, min_rr=2.0, retest_tolerance_pct=0.15, reversal_lookback=3,
                             is_intraday=True, eod_hour=15, eod_minute=15):
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


        signals.append({
            "entry_time": entry_time, "direction": direction, "entry_price": round(entry_price, 2),
            "sl_price": round(sl_price, 2), "target_price": round(target_price, 2),
            "outcome": outcome, "exit_price": round(exit_price, 2) if exit_price is not None else None,
            "bars_to_exit": exit_bars,
        })

    if not signals:
        return {"total": 0, "signals": [], "funnel": funnel}

    sig_df = pd.DataFrame(signals)
    targets = sig_df[sig_df["outcome"] == "TARGET"]
    sls = sig_df[sig_df["outcome"] == "SL"]
    opens = sig_df[sig_df["outcome"] == "OPEN"]
    decided = len(targets) + len(sls)
    return {
        "total": len(sig_df), "signals": signals,
        "target_count": len(targets), "sl_count": len(sls), "open_count": len(opens),
        "win_rate": round(len(targets) / decided * 100, 1) if decided > 0 else None,
        "bullish_count": int((sig_df["direction"] == "BULLISH").sum()),
        "bearish_count": int((sig_df["direction"] == "BEARISH").sum()),
        "funnel": funnel,
    }
