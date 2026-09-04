"""Dashboard page — Chart, Direction Engine, Option Chain/OI, Advanced OI Analysis, Manual Trading, A1 Signal Engine, PDF Report."""
import datetime
import os
import re
import time
import uuid
import pandas as pd
import streamlit as st

from config import TIMEFRAME_CONFIG, DB_PATH, get_ist_now, get_ist_today, is_market_open
from tradingview_chart import build_lightweight_chart_html
from sr_dynamic import compute_dynamic_sr
import sqlite3
from database import (
    log_orders_batch, get_todays_realized_pnl,
)
from upstox_api import (
    fetch_candles, fetch_timeframe_df, fetch_india_vix, get_available_margin,
    execute_order_leg_set, get_static_ip_proxy_url, check_proxy_egress_ip,
    get_registered_static_ips, fetch_ltp_map, fetch_next_expiry_option_chain,
)
from signals import (
    calculate_rsi, calculate_supertrend, resample_to_1h, find_support_resistance_levels,
    detect_trendline, check_trend_signal,
    classify_market_structure, detect_break,
    classify_sideways, detect_pullback_retest,
    rsi_momentum_and_divergence, confirm_5m, supply_demand_zone, check_pattern_rsi_gate,
    check_price_action_strategy, check_indicator_strategy, find_significant_reversal_candles,
)
from strategy import _pop_lookup, select_iron_condor, select_iron_butterfly, select_credit_spread, select_credit_spread_fixed_strikes, compute_position_size
from oi_analysis import (
    get_latest_oi_signal, check_oi_diff_entry_gate,
    get_previous_day_total_oi, compute_oi_price_matrix, compute_pcr_signal, compute_max_pain,
    compute_rollover_proxy, swing_oi_gate, find_psychological_level, check_oi_wall_confirmation,
    compute_oi_signal_with_hysteresis, classify_oi_price_action, generate_oi_price_signal,
    fetch_and_save_oi_snapshot, compute_dte,
)
from trading_engine import normalize_legs, open_multi_leg_trade, track_manual_trade
from pdf_reports import generate_market_analysis_report_pdf
from upstox_api import fetch_market_news


def render():
    symbol = st.session_state["symbol"]
    timeframe_option = st.session_state["timeframe_option"]
    chart_type = st.session_state["chart_type"]
    token_input = st.session_state["token_input"]
    auto_refresh = st.session_state["auto_refresh"]
    lot_size = st.session_state["lot_size"]
    risk_pct_per_trade = st.session_state["risk_pct_per_trade"]
    hedge_width_points = st.session_state["hedge_width_points"]
    pop_threshold_pct = st.session_state["pop_threshold_pct"]
    sl_pct_of_max_loss = st.session_state["sl_pct_of_max_loss"]
    target_pct_of_max_profit = st.session_state["target_pct_of_max_profit"]
    vix_max_threshold = st.session_state["vix_max_threshold"]
    sideways_tight_range_pct = st.session_state["sideways_tight_range_pct"]
    sideways_max_range_pct = st.session_state["sideways_max_range_pct"]
    trading_style = st.session_state["trading_style"]
    product_type = st.session_state["product_type"]
    eod_squareoff_time = st.session_state["eod_squareoff_time"]
    entry_cutoff_time = st.session_state["entry_cutoff_time"]
    enable_oi_gate = st.session_state["enable_oi_gate"]
    oi_gate_strictness = st.session_state["oi_gate_strictness"]
    enable_oi_early_exit = st.session_state["enable_oi_early_exit"]
    enable_swing_oi_gate = st.session_state["enable_swing_oi_gate"]
    swing_max_opposing_signals = st.session_state["swing_max_opposing_signals"]
    max_trades_per_day = st.session_state["max_trades_per_day"]
    max_daily_loss = st.session_state["max_daily_loss"]
    trading_mode = st.session_state["trading_mode"]
    enable_live_trading = st.session_state["enable_live_trading"]
    confirm_live_trading = st.session_state["confirm_live_trading"]
    raw_chain = st.session_state["raw_chain"]
    status_msg = st.session_state["status_msg"]
    underlying_price = st.session_state["underlying_price"]
    step = st.session_state["step"]
    atm_strike = st.session_state["atm_strike"]

    # 🎓 वापरकर्त्याने प्रत्यक्ष Streamlit वरच्या UnboundLocalError सह दाखवलेला खरा bug —
    # df_structure_tf (आणि इतर संबंधित variables) tab1 च्या आतच तयार होतात, पण नंतरच्या tabs
    # (tab3 वगैरे) मध्ये वापरले जातात. जर tab1 च्या कोडमध्ये कुठेतरी अनपेक्षित अडथळा आला (उदा. Upstox
    # API चा तात्पुरता network/rate-limit त्रास), तर हे variables कधीच तयारच होत नाहीत, आणि नंतरच्या
    # tab मध्ये वापरताना UnboundLocalError येतो. आता इथे, सर्व tabs सुरू होण्याआधीच, सुरक्षित रिकामे
    # डीफॉल्ट देऊन ठेवले आहेत — कारण काहीही असो, हे variables कधीच "undefined" राहणार नाहीत.
    df_structure_tf = pd.DataFrame()
    df_rsi_tf = pd.DataFrame()
    df_1h = pd.DataFrame()
    rsi_series = pd.Series(dtype=float)
    supertrend_source_df = pd.DataFrame()
    st_line, st_dir = pd.Series(dtype=float), pd.Series(dtype=float)

    st.title(f"📈 Upstox Option Terminal ({symbol})")

    last_updated_ist = get_ist_now().strftime("%H:%M:%S")
    col_live1, col_live2 = st.columns([1, 3])
    with col_live1:
        st.markdown(
            f"""
            <div style="background-color:#1e222d;border:1px solid #2a2e3d;border-radius:6px;padding:10px 14px;">
                <div style="font-size:12px;color:#787b86;letter-spacing:0.5px;">
                    🟢 {symbol} 50 · LIVE DATA
                </div>
                <div style="font-size:26px;font-weight:bold;color:#d1d4dc;font-variant-numeric:tabular-nums;">
                    ₹{underlying_price:,.2f}
                </div>
                <div style="font-size:11px;color:#9598a1;">Last updated {last_updated_ist} IST</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # निवडलेल्या टाइमफ्रेमनुसार डेटा फेच करणे
    df_candles = fetch_candles(token_input, symbol, underlying_price, interval=timeframe_option)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Chart व Direction", "📋 Option Chain व OI", "🧬 Signal Engine व Trading",
        "📄 Reports", "🧩 Multi-Strategy", "🌉 MTF Pullback + Gap Fill", "🗺️ Market Zones",
        "🎯 Strategy Builder",
    ])
    with tab1:
        st.markdown("---")
        st.subheader(f"📊 {symbol} TradingView Style Chart ({timeframe_option})")

        # --- ट्रेडिंगव्यू प्रो-चार्ट (Price + MA, Volume, RSI) ---

        # =========================================================
        # ७.६ TradingView Chart (Lightweight Charts library) — खरं candle-रेंडरिंग, Drawing Tools
        # (Trendline, H-Line, Fibonacci, Rectangle, Measure). जुना Plotly chart काढून, हाच आता एकमेव,
        # डीफॉल्ट chart आहे.
        # =========================================================
        rsi_for_tv = calculate_rsi(df_candles, period=14) if not df_candles.empty else pd.Series(dtype=float)
        # 🎓 वापरकर्त्याने दिलेल्या TradingView Pine Script ("Support Resistance - Dynamic v2" by
        # LonesomeTheBlue) च्याच तर्कानुसार — Pivot High/Low clustering वरून dynamic S/R (आधीच्या
        # साध्या rolling-window S/R ऐवजी, जास्त अचूक व त्याच indicator शी जुळणारं)
        sr_for_tv = compute_dynamic_sr(df_candles, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2) if not df_candles.empty else None

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — EMA20/EMA50 काढून, त्याऐवजी डीफॉल्ट 1-Day, 1-Hour
        # व 15-Minute Supertrend (period=10, multiplier=3, आपल्याच A1 Engine सारखेच). तिन्ही मुख्य
        # chart च्या timeframe शी no-lookahead (merge_asof, backward) अलाइन केले जातात — established
        # पद्धत, sr_bounce/multi_strategy_backtest मध्ये आधीच वापरलेली.
        st1d_line_aligned = st1d_dir_aligned = st1h_line_aligned = st1h_dir_aligned = None
        st15m_line_aligned = st15m_dir_aligned = None
        pattern_markers_tv = []
        if not df_candles.empty:
            try:
                df_1d_tv = fetch_candles(token_input, symbol, underlying_price, interval="day")
                if df_1d_tv is not None and not df_1d_tv.empty:
                    st1d_line, st1d_dir = calculate_supertrend(df_1d_tv, period=10, multiplier=3)
                    df_1d_st = pd.DataFrame({"timestamp": df_1d_tv["timestamp"], "st_line": st1d_line, "st_dir": st1d_dir}).dropna()
                    aligned_1d = pd.merge_asof(
                        df_candles[["timestamp"]].sort_values("timestamp"), df_1d_st.sort_values("timestamp"),
                        on="timestamp", direction="backward",
                    )
                    st1d_line_aligned, st1d_dir_aligned = aligned_1d["st_line"], aligned_1d["st_dir"]

                df_1h_tv = resample_to_1h(fetch_candles(token_input, symbol, underlying_price, interval="30minute"))
                if df_1h_tv is not None and not df_1h_tv.empty:
                    st1h_line, st1h_dir = calculate_supertrend(df_1h_tv, period=10, multiplier=3)
                    df_1h_st = pd.DataFrame({"timestamp": df_1h_tv["timestamp"], "st_line": st1h_line, "st_dir": st1h_dir}).dropna()
                    aligned_1h = pd.merge_asof(
                        df_candles[["timestamp"]].sort_values("timestamp"), df_1h_st.sort_values("timestamp"),
                        on="timestamp", direction="backward",
                    )
                    st1h_line_aligned, st1h_dir_aligned = aligned_1h["st_line"], aligned_1h["st_dir"]

                df_15m_tv = fetch_candles(token_input, symbol, underlying_price, interval="15minute")
                if df_15m_tv is not None and not df_15m_tv.empty:
                    st15m_line, st15m_dir = calculate_supertrend(df_15m_tv, period=10, multiplier=3)
                    df_15m_st = pd.DataFrame({"timestamp": df_15m_tv["timestamp"], "st_line": st15m_line, "st_dir": st15m_dir}).dropna()
                    aligned_15m = pd.merge_asof(
                        df_candles[["timestamp"]].sort_values("timestamp"), df_15m_st.sort_values("timestamp"),
                        on="timestamp", direction="backward",
                    )
                    st15m_line_aligned, st15m_dir_aligned = aligned_15m["st_line"], aligned_15m["st_dir"]
            except Exception:
                pass  # 1D/1H/15M डेटा मिळाला नाही तरी मुख्य chart दाखवत राहणे (सुरक्षित fallback)

            # 🎓 मागच्या 2-3 candles पेक्षा मोठे Hammer/Shooting Star — chart वर मार्करने ठळक
            pattern_markers_tv = find_significant_reversal_candles(df_candles, lookback_compare=3)

        tv_html = build_lightweight_chart_html(
            df_candles, symbol=symbol, timeframe_label=timeframe_option,
            supertrend_1d_series=st1d_line_aligned, supertrend_1d_direction=st1d_dir_aligned,
            supertrend_1h_series=st1h_line_aligned, supertrend_1h_direction=st1h_dir_aligned,
            supertrend_15m_series=st15m_line_aligned, supertrend_15m_direction=st15m_dir_aligned,
            rsi_series=rsi_for_tv, sr_levels=sr_for_tv, pattern_markers=pattern_markers_tv, height=650,
        )
        st.components.v1.html(tv_html, height=700, scrolling=False)
        st.caption("⚠️ Drawing Tools चा डेटा browser मध्येच राहतो — refresh झाल्यावर मिटतो.")

        # =========================================================
        # ७.५ DIRECTION ENGINE — Intraday/Swing style नुसार टाईमफ्रेम बदलणारे → BULLISH / BEARISH
        # (मुख्य चार्टच्या टाईमफ्रेम निवडीपासून स्वतंत्र; Signal लॉजिक तेच पण टाईमफ्रेम style-driven)
        # =========================================================
    with tab1:
        st.markdown("---")
        tf_cfg = TIMEFRAME_CONFIG[trading_style]
        structure_interval, structure_tf_label = tf_cfg["structure"]
        rsi_interval, rsi_tf_label = tf_cfg["rsi"]
        confirm_interval, confirm_tf_label = tf_cfg["confirm"]
        intraday_strategy_mode = st.session_state.get("intraday_strategy_mode", "indicator")
        sr_window = st.session_state.get("sr_window", 20)
        rsi_oversold = st.session_state.get("rsi_oversold", 30)
        rsi_overbought = st.session_state.get("rsi_overbought", 70)
        sl_buffer_pct = st.session_state.get("sl_buffer_pct", 0.1)
        min_rr = st.session_state.get("min_rr", 2.0)
        retest_tolerance_pct = st.session_state.get("retest_tolerance_pct", 0.15)
        reversal_lookback = st.session_state.get("reversal_lookback", 3)

        # Intraday साठी दिशा नेहमी 1H Supertrend वरून (दोन्ही नवीन रणनीतींसाठी सामायिक), आणि RSI 15M वर —
        # जुनी 15M Market Structure-आधारित दिशा व 5M RSI आता Intraday साठी वापरली जात नाही (Swing अपरिवर्तित).
        if trading_style == "INTRADAY":
            rsi_interval, rsi_tf_label = "15minute", "15M"

        supertrend_tf_label = "1H" if trading_style == "INTRADAY" else structure_tf_label
        st.subheader(f"🧭 Direction Engine ({trading_style}) — Supertrend {supertrend_tf_label} + RSI-14 {rsi_tf_label}")

        df_structure_tf = fetch_timeframe_df(token_input, symbol, underlying_price, structure_interval)

        df_rsi_tf = df_structure_tf if rsi_interval == structure_interval else fetch_timeframe_df(
            token_input, symbol, underlying_price, rsi_interval
        )
        rsi_series = calculate_rsi(df_rsi_tf, period=14) if not df_rsi_tf.empty else pd.Series(dtype=float)

        # df_1h पुढे चार्ट्स/रिपोर्टसाठी नेहमी लागतो (Style सेटिंग्जपासून स्वतंत्र) — आधीच fetch झाला असल्यास तोच वापरणे
        if structure_interval == "1hour":
            df_1h = df_structure_tf
        elif rsi_interval == "1hour":
            df_1h = df_rsi_tf
        else:
            df_1h = resample_to_1h(fetch_candles(token_input, symbol, underlying_price, interval="30minute"))

        supertrend_source_df = df_1h if trading_style == "INTRADAY" else df_structure_tf
        st_line, st_dir = calculate_supertrend(supertrend_source_df, period=10, multiplier=3)

        supertrend_ok = len(st_dir) > 0
        rsi_ok = len(rsi_series) > 0

        if supertrend_ok and rsi_ok:
            last_st_dir = int(st_dir.iloc[-1])          # 1 = up, -1 = down
            last_st_val = float(st_line.iloc[-1])
            last_rsi = float(rsi_series.iloc[-1])

            st_label = "🟢 UP" if last_st_dir == 1 else "🔴 DOWN"

            if trading_style == "INTRADAY":
                # नवीन Signal Engine: दिशा फक्त 1H Supertrend वरून — RSI इथे दिशा-गेट म्हणून वापरलं जात नाही
                # (RSI पुढे प्रत्येक रणनीतीच्या स्वतःच्या entry-तपासणीत वापरलं जातं — Indicator रणनीतीसाठी विशेषतः).
                direction_final = "BULLISH" if last_st_dir == 1 else "BEARISH"
                direction_color = "#089981" if last_st_dir == 1 else "#F23645"
            elif last_st_dir == 1 and last_rsi > 50:
                direction_final = "BULLISH"
                direction_color = "#089981"
            elif last_st_dir == -1 and last_rsi < 50:
                direction_final = "BEARISH"
                direction_color = "#F23645"
            else:
                direction_final = "NEUTRAL / MIXED"
                direction_color = "#d68a00"

            dcol1, dcol2, dcol3 = st.columns(3)
            with dcol1:
                st.metric(f"Supertrend ({supertrend_tf_label})", st_label, f"Level: {last_st_val:,.2f}")
            with dcol2:
                rsi_zone = "Overbought" if last_rsi >= 70 else ("Oversold" if last_rsi <= 30 else "Neutral zone")
                st.metric(f"RSI-14 ({rsi_tf_label})", f"{last_rsi:.1f}", rsi_zone)
            with dcol3:
                st.markdown(
                    f"""
                    <div style="background-color:#1e222d;border:1px solid {direction_color};border-radius:6px;
                                padding:14px;text-align:center;">
                        <div style="font-size:12px;color:#787b86;">DIRECTION ENGINE OUTPUT</div>
                        <div style="font-size:22px;font-weight:bold;color:{direction_color};">{direction_final}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info(f"Direction Engine साठी पुरेसा {structure_tf_label} / {rsi_tf_label} डेटा अजून उपलब्ध नाही (मार्केट सुरू झाल्यावर किंवा काही मिनिटांनी पुन्हा तपासा).")

        st.caption(f"**{trading_style}**: {structure_tf_label} Structure · {rsi_tf_label} RSI · {confirm_tf_label} Confirm")

        # --- डेटाबेस बेसलाइनवरून OI Change कॅल्क्युलेट करणे ---
        # IST तारीख वापरणे (local सर्व्हर तारीख नाही — UTC सर्व्हरवर मध्यरात्रीच्या आसपास चुकीची तारीख येऊ शकते)
        today_str = get_ist_now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        chain_data = []
        for item in raw_chain:
            strike = item.get("strike_price", 0)
            if (atm_strike - 6 * step) <= strike <= (atm_strike + 6 * step):
                call_opt = item.get("call_options", {}) or {}
                put_opt = item.get("put_options", {}) or {}

                ce_mkt = call_opt.get("market_data", {}) or {}
                pe_mkt = put_opt.get("market_data", {}) or {}

                ce_oi = int(ce_mkt.get("oi") or 0)
                pe_oi = int(pe_mkt.get("oi") or 0)
                ce_ltp = float(ce_mkt.get("ltp") or 0.0)
                pe_ltp = float(pe_mkt.get("ltp") or 0.0)

                cursor.execute(
                    "SELECT initial_ce_oi, initial_pe_oi FROM day_baseline_oi WHERE symbol=? AND strike=? AND trade_date=?",
                    (symbol, strike, today_str)
                )
                row = cursor.fetchone()

                if row:
                    init_ce, init_pe = row
                    if init_ce == 0 and ce_oi > 0:
                        cursor.execute(
                            "UPDATE day_baseline_oi SET initial_ce_oi=?, initial_pe_oi=? WHERE symbol=? AND strike=? AND trade_date=?",
                            (ce_oi, pe_oi, symbol, strike, today_str)
                        )
                        conn.commit()
                        init_ce, init_pe = ce_oi, pe_oi
                else:
                    init_ce, init_pe = ce_oi, pe_oi
                    cursor.execute(
                        "INSERT OR REPLACE INTO day_baseline_oi (symbol, strike, trade_date, initial_ce_oi, initial_pe_oi) VALUES (?, ?, ?, ?, ?)",
                        (symbol, strike, today_str, init_ce, init_pe)
                    )
                    conn.commit()

                ce_chg = ce_oi - init_ce
                pe_chg = pe_oi - init_pe
                diff = pe_chg - ce_chg

                dom = "🟢 Bulls" if diff > 0 else ("🔴 Bears" if diff < 0 else "⚪ Neutral")
                strike_label = f"➡️ {strike} (ATM)" if strike == atm_strike else str(strike)

                chain_data.append({
                    "CE Chg OI": ce_chg,
                    "CE Total OI": ce_oi,
                    "CE LTP": ce_ltp,
                    "Strike Price": strike_label,
                    "PE LTP": pe_ltp,
                    "PE Total OI": pe_oi,
                    "PE Chg OI": pe_chg,
                    "Net Diff": diff,
                    "Dominance": dom,
                })

        conn.close()

        df = pd.DataFrame(chain_data)

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — PCR (Put-Call Ratio) आणि एकूण Total OI,
        # आधी option chain table मध्ये कुठेच दिसत नव्हते — व्यावसायिक Platforms (Sensibull इ.) प्रमाणे
        # PCR ठळक metric म्हणून वर, आणि Total एक वेगळी row म्हणून table च्या तळाशी.
        if not df.empty:
            total_ce_oi = df["CE Total OI"].sum()
            total_pe_oi = df["PE Total OI"].sum()
            total_ce_chg = df["CE Chg OI"].sum()
            total_pe_chg = df["PE Chg OI"].sum()
            pcr = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else 0.0
            pcr_label = "🟢 Bullish (PCR>1)" if pcr > 1 else ("🔴 Bearish (PCR<1)" if pcr < 1 else "⚪ तटस्थ")

            pcol1, pcol2, pcol3, pcol4 = st.columns(4)
            pcol1.metric("PCR (Put-Call Ratio)", f"{pcr:.2f}", pcr_label)
            pcol2.metric("एकूण Call OI", f"{total_ce_oi:,.0f}")
            pcol3.metric("एकूण Put OI", f"{total_pe_oi:,.0f}")
            pcol4.metric("एकूण Net Diff", f"{total_pe_chg - total_ce_chg:,.0f}")

            total_row = pd.DataFrame([{
                "CE Chg OI": total_ce_chg, "CE Total OI": total_ce_oi, "CE LTP": None,
                "Strike Price": "TOTAL", "PE LTP": None, "PE Total OI": total_pe_oi,
                "PE Chg OI": total_pe_chg, "Net Diff": total_pe_chg - total_ce_chg, "Dominance": "",
            }])
            df = pd.concat([df, total_row], ignore_index=True)

    with tab2:
        st.markdown("---")
        st.subheader("📋 Option Chain & Calculated Change in OI Table")

        def style_option_chain(val):
            color = ""
            if isinstance(val, (int, float)):
                if val > 0:
                    color = "color: #089981; font-weight: bold; font-size: 16px;"
                elif val < 0:
                    color = "color: #F23645; font-weight: bold; font-size: 16px;"
            return color

        styled_df = df.style.map(style_option_chain, subset=["CE Chg OI", "PE Chg OI", "Net Diff"]) \
                            .set_properties(**{'font-size': '16px', 'font-weight': 'bold'})

        # क्लिक-टू-ट्रेड: टेबलमधील कोणतीही row निवडल्यास तो strike खाली Manual Trading Panel मध्ये आपोआप भरला जातो.
        # जुन्या Streamlit व्हर्जनमध्ये on_select उपलब्ध नसल्यास साध्या टेबलवर आपोआप fallback होतो.
        try:
            chain_select_event = st.dataframe(
                styled_df, width='stretch', height=500,
                on_select="rerun", selection_mode="single-row", key="chain_table_select",
            )
            selected_rows = chain_select_event.get("selection", {}).get("rows", []) if chain_select_event else []
            if selected_rows:
                sel_idx = selected_rows[0]
                sel_strike_label = df.iloc[sel_idx]["Strike Price"]
                _m = re.search(r"(\d+(?:\.\d+)?)", str(sel_strike_label))
                if _m:
                    st.session_state["clicked_strike_from_chain"] = float(_m.group(1))
                    st.success(f"✅ निवडलेला Strike: {st.session_state['clicked_strike_from_chain']:.0f} — खाली Manual Trading Panel मध्ये आपोआप भरला.")
        except TypeError:
            st.dataframe(styled_df, width='stretch', height=500)

        # =========================================================
        # ७.४ Static IP Proxy Diagnostics — UDAPI1154 (Static IP) सेटअप तपासण्यासाठी
        # =========================================================
        st.markdown("---")
        with st.expander("🔌 Static IP Proxy Diagnostics (UDAPI1154 त्रुटीसाठी)"):
            st.caption(
                "Upstox ला ऑर्डर-प्लेसमेंटसाठी नोंदणीकृत Static IP लागतो. खाली तपासा की तुमचा Proxy "
                "प्रत्यक्षात कोणता IP दाखवतोय, आणि तो Upstox कडे नोंदवलेल्या IP शी जुळतो का."
            )
            configured_proxy_url = get_static_ip_proxy_url()
            if not configured_proxy_url:
                st.warning(
                    "कोणताही Proxy कॉन्फिगर केलेला नाही. `.streamlit/secrets.toml` मध्ये खालीलप्रमाणे जोडा:\n\n"
                    "```toml\n[proxy]\nurl = \"http://username:password@static.quotaguard.com:9293\"\n```"
                )
            else:
                st.success("Proxy कॉन्फिगर केलेला आढळला (secrets.toml मध्ये).")

            if st.button("🔍 Static IP सेटअप तपासा"):
                with st.spinner("तपासत आहे..."):
                    registered = get_registered_static_ips(token_input) if token_input.strip() else None
                    egress_ip = check_proxy_egress_ip(configured_proxy_url) if configured_proxy_url else None

                dcol1, dcol2 = st.columns(2)
                with dcol1:
                    st.markdown("**Upstox कडे नोंदवलेले IPs:**")
                    if registered:
                        st.write(f"Primary: `{registered.get('primary_ip', '—')}`")
                        st.write(f"Secondary: `{registered.get('secondary_ip', '—')}`")
                    else:
                        st.write("मिळाले नाहीत (टोकन तपासा).")
                with dcol2:
                    st.markdown("**Proxy चा सध्याचा Egress IP:**")
                    if egress_ip:
                        st.write(f"`{egress_ip}`")
                    else:
                        st.write("Proxy कॉन्फिगर नाही किंवा अनुपलब्ध.")

                if registered and egress_ip:
                    registered_ips = {registered.get("primary_ip"), registered.get("secondary_ip")}
                    if egress_ip in registered_ips:
                        st.success("✅ जुळते! Proxy चा IP Upstox कडे नोंदवलेला आहे — ऑर्डर्स जायला हव्यात.")
                    else:
                        st.error(
                            f"❌ जुळत नाही — Proxy चा IP (`{egress_ip}`) Upstox कडे नोंदवलेला नाही. "
                            "हा IP Upstox च्या Developer Console मध्ये (My Apps → Static IP) नोंदवा "
                            "(आठवड्यातून एकदाच बदलता येतो)."
                        )

        # =========================================================
        # ७.५ Manual Trading Panel — Option Chain मधून थेट ऑर्डर + Basket Orders
        # (place_multi_leg_order हेच आधीच वापरलेले व verified Upstox Multi Order API वापरते)
        # =========================================================
    with tab3:
        st.markdown("---")
        with st.expander("🖐️ Manual Trading Panel (क्लिक करून उघडा — Option विकत घेणे/विकणे)", expanded=False):
            st.subheader("🖐️ Manual Trading Panel")
            st.caption(
                "वरील Option Chain मधून कोणताही strike/CE/PE निवडून थेट ऑर्डर द्या, किंवा अनेक legs Basket मध्ये "
                "जमा करून एकत्र प्लेस करा. Order Types: MARKET, LIMIT, SL, SL-M. लाईव्ह प्लेसमेंटसाठी साईडबारमधील "
                "'ENABLE LIVE TRADING' + पुष्टीकरण दोन्ही आवश्यक आहेत."
            )

            if "order_basket" not in st.session_state:
                st.session_state.order_basket = []

            available_strikes = sorted({item.get("strike_price") for item in raw_chain if item.get("strike_price") is not None})

            if not available_strikes:
                st.warning("Option chain मधून strikes उपलब्ध नाहीत.")
            else:
                mtc1, mtc2, mtc3, mtc4 = st.columns(4)
                with mtc1:
                    default_strike = st.session_state.get("clicked_strike_from_chain")
                    if default_strike is not None and default_strike in available_strikes:
                        default_idx = available_strikes.index(default_strike)
                    elif atm_strike in available_strikes:
                        default_idx = available_strikes.index(atm_strike)
                    else:
                        default_idx = 0
                    manual_strike = st.selectbox("Strike", available_strikes, index=default_idx, key="manual_strike")
                with mtc2:
                    manual_side = st.selectbox("Option", ["CE", "PE"], key="manual_side")
                with mtc3:
                    manual_txn = st.selectbox("Action", ["BUY", "SELL"], key="manual_txn")
                with mtc4:
                    manual_order_type = st.selectbox("Order Type", ["MARKET", "LIMIT", "SL", "SL-M"], key="manual_order_type")

                mtc5, mtc6, mtc7 = st.columns(3)
                with mtc5:
                    manual_lots = st.number_input("Lots", min_value=1, value=1, step=1, key="manual_lots")
                with mtc6:
                    manual_price = st.number_input(
                        "Price (LIMIT / SL साठी आवश्यक)", min_value=0.0, value=0.0, step=0.05,
                        key="manual_price", disabled=manual_order_type not in ("LIMIT", "SL"),
                    )
                with mtc7:
                    manual_trigger = st.number_input(
                        "Trigger Price (SL / SL-M साठी आवश्यक)", min_value=0.0, value=0.0, step=0.05,
                        key="manual_trigger", disabled=manual_order_type not in ("SL", "SL-M"),
                    )

                manual_set_sl_target = st.checkbox("SL/Target सेट करा (ऐच्छिक — नाही तर फक्त EOD/मॅन्युअल Close ने बंद होईल)", key="manual_set_sltgt")
                manual_sl_amount, manual_target_amount = None, None
                if manual_set_sl_target:
                    sltc1, sltc2 = st.columns(2)
                    with sltc1:
                        manual_sl_amount = st.number_input("SL (₹ तोटा, संपूर्ण पोझिशन)", min_value=0.0, value=1000.0, step=100.0, key="manual_sl_amt")
                    with sltc2:
                        manual_target_amount = st.number_input("Target (₹ नफा, संपूर्ण पोझिशन)", min_value=0.0, value=2000.0, step=100.0, key="manual_target_amt")

                side_key = "call_options" if manual_side == "CE" else "put_options"
                manual_lookup = _pop_lookup(raw_chain, side_key, manual_strike)

                if not manual_lookup or not manual_lookup.get("instrument_key"):
                    st.warning("या strike/option साठी instrument सापडला नाही.")
                else:
                    ltp_display = f"₹{manual_lookup['ltp']:.2f}" if manual_lookup.get("ltp") is not None else "अनुपलब्ध"
                    st.caption(
                        f"LTP: {ltp_display} · Instrument: {manual_lookup['instrument_key']} · "
                        f"Qty: {manual_lots * lot_size} ({manual_lots} lot × {lot_size})"
                    )

                    order_valid = True
                    if manual_order_type in ("LIMIT", "SL") and manual_price <= 0:
                        st.error("LIMIT / SL ऑर्डरसाठी Price > 0 असणे आवश्यक आहे.")
                        order_valid = False
                    if manual_order_type in ("SL", "SL-M") and manual_trigger <= 0:
                        st.error("SL / SL-M ऑर्डरसाठी Trigger Price > 0 असणे आवश्यक आहे.")
                        order_valid = False

                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        if st.button("➕ Basket मध्ये जोडा", disabled=not order_valid):
                            st.session_state.order_basket.append({
                                "Strike": manual_strike, "Option": manual_side, "Action": manual_txn,
                                "Order Type": manual_order_type, "Lots": manual_lots,
                                "Price": manual_price if manual_order_type in ("LIMIT", "SL") else 0,
                                "Trigger": manual_trigger if manual_order_type in ("SL", "SL-M") else 0,
                                "instrument_key": manual_lookup["instrument_key"],
                            })
                            st.success("Basket मध्ये leg जोडला गेला.")
                            st.rerun()
                    with bcol2:
                        single_btn_label = "⚡ आत्ताच Single Order प्लेस करा (PAPER)" if trading_mode == "PAPER" else "⚡ आत्ताच Single Order प्लेस करा (LIVE)"
                        if st.button(single_btn_label, disabled=not order_valid):
                            if not (enable_live_trading and confirm_live_trading):
                                st.error("साईडबारमध्ये 'ENABLE LIVE TRADING' + पुष्टीकरण दोन्ही आधी टिक करा.")
                            else:
                                order = {
                                    "quantity": manual_lots * lot_size, "product": product_type, "validity": "DAY",
                                    "price": manual_price if manual_order_type in ("LIMIT", "SL") else 0,
                                    "tag": "MANUAL", "instrument_token": manual_lookup["instrument_key"],
                                    "order_type": manual_order_type, "transaction_type": manual_txn,
                                    "disclosed_quantity": 0,
                                    "trigger_price": manual_trigger if manual_order_type in ("SL", "SL-M") else 0,
                                    "is_amo": False,
                                }
                                status_code, resp = execute_order_leg_set(token_input, [order], trading_mode)
                                if status_code == 200 and resp.get("status") == "success":
                                    order_ids = resp.get("data", {}).get("order_ids", [])
                                    tag = "📝 PAPER" if trading_mode == "PAPER" else "✅"
                                    st.success(f"{tag} ऑर्डर प्लेस झाला — Order ID: {order_ids}")

                                    # Positions tab मध्ये MTM दिसण्यासाठी व (ऐच्छिक) SL/Target मॉनिटरिंगसाठी live_trades मध्ये नोंदवणे
                                    entry_ltps = resp.get("paper_fills", {}) if trading_mode == "PAPER" else fetch_ltp_map(token_input, [manual_lookup["instrument_key"]])
                                    leg_for_tracking = [{
                                        "instrument_key": manual_lookup["instrument_key"], "transaction_type": manual_txn,
                                        "role": f"{manual_txn}_{manual_side}", "strike": manual_strike,
                                    }]
                                    track_ok, track_trade_id, track_err = track_manual_trade(
                                        symbol, leg_for_tracking, manual_lots, lot_size, entry_ltps, trading_mode, trading_style,
                                        sl_amount=manual_sl_amount, target_amount=manual_target_amount, tag_prefix="MANUAL",
                                    )
                                    # order_log व live_trades मध्ये एकच trade_id वापरणे (traceability साठी) — track झालं तरच
                                    # खरा trade_id वापरता येईल, नाहीतर वेगळा (untracked) tag वापरणे
                                    log_orders_batch(order_ids, track_trade_id or "MANUAL_UNTRACKED", symbol, trading_mode, [order], status="COMPLETE")
                                    if track_ok:
                                        st.caption(f"📍 Positions tab मध्ये ट्रॅक होत आहे (Trade ID: {track_trade_id}).")
                                    else:
                                        st.warning(f"⚠️ ऑर्डर यशस्वी झाला, पण Positions tab मध्ये ट्रॅक करता आला नाही: {track_err}")
                                else:
                                    st.error(f"❌ ऑर्डर अयशस्वी: {resp}")

            if st.session_state.order_basket:
                st.markdown("##### 🧺 सद्य Basket")
                basket_df = pd.DataFrame(st.session_state.order_basket).drop(columns=["instrument_key"])
                st.dataframe(basket_df, width='stretch')

                remove_idx = st.selectbox(
                    "काढून टाकण्यासाठी leg निवडा (ऐच्छिक)",
                    options=list(range(len(st.session_state.order_basket))),
                    format_func=lambda i: (
                        f"{i+1}. {st.session_state.order_basket[i]['Action']} "
                        f"{st.session_state.order_basket[i]['Strike']} {st.session_state.order_basket[i]['Option']} "
                        f"({st.session_state.order_basket[i]['Order Type']})"
                    ),
                    key="remove_idx",
                )
                rcol1, rcol2, rcol3 = st.columns(3)
                with rcol1:
                    if st.button("🗑️ ही Leg काढा"):
                        st.session_state.order_basket.pop(remove_idx)
                        st.rerun()
                with rcol2:
                    if st.button("🧹 संपूर्ण Basket रिकामी करा"):
                        st.session_state.order_basket = []
                        st.rerun()

                basket_set_sl_target = st.checkbox("Basket साठी SL/Target सेट करा (ऐच्छिक)", key="basket_set_sltgt")
                basket_sl_amount, basket_target_amount = None, None
                if basket_set_sl_target:
                    bsltc1, bsltc2 = st.columns(2)
                    with bsltc1:
                        basket_sl_amount = st.number_input("SL (₹ तोटा, संपूर्ण Basket)", min_value=0.0, value=1000.0, step=100.0, key="basket_sl_amt")
                    with bsltc2:
                        basket_target_amount = st.number_input("Target (₹ नफा, संपूर्ण Basket)", min_value=0.0, value=2000.0, step=100.0, key="basket_target_amt")

                with rcol3:
                    basket_btn_label = "🚀 संपूर्ण Basket प्लेस करा (PAPER)" if trading_mode == "PAPER" else "🚀 संपूर्ण Basket प्लेस करा (LIVE)"
                    if st.button(basket_btn_label):
                        if not (enable_live_trading and confirm_live_trading):
                            st.error("साईडबारमध्ये 'ENABLE LIVE TRADING' + पुष्टीकरण दोन्ही आधी टिक करा.")
                        else:
                            basket_orders = [
                                {
                                    "quantity": leg["Lots"] * lot_size, "product": product_type, "validity": "DAY",
                                    "price": leg["Price"], "tag": "BASKET", "instrument_token": leg["instrument_key"],
                                    "order_type": leg["Order Type"], "transaction_type": leg["Action"],
                                    "disclosed_quantity": 0, "trigger_price": leg["Trigger"], "is_amo": False,
                                }
                                for leg in st.session_state.order_basket
                            ]
                            status_code, resp = execute_order_leg_set(token_input, basket_orders, trading_mode)
                            if status_code == 200 and resp.get("status") == "success":
                                order_ids = resp.get("data", {}).get("order_ids", [])
                                tag = "📝 PAPER" if trading_mode == "PAPER" else "✅"
                                st.success(f"{tag} Basket प्लेस झाला — Order IDs: {order_ids}")

                                # Positions tab मध्ये MTM दिसण्यासाठी व (ऐच्छिक) SL/Target मॉनिटरिंगसाठी live_trades मध्ये नोंदवणे
                                basket_keys = [leg["instrument_key"] for leg in st.session_state.order_basket]
                                entry_ltps = resp.get("paper_fills", {}) if trading_mode == "PAPER" else fetch_ltp_map(token_input, basket_keys)
                                legs_for_tracking = [
                                    {
                                        "instrument_key": leg["instrument_key"], "transaction_type": leg["Action"],
                                        "role": f"{leg['Action']}_{leg['Option']}", "strike": leg["Strike"],
                                    }
                                    for leg in st.session_state.order_basket
                                ]
                                basket_lots = st.session_state.order_basket[0]["Lots"] if st.session_state.order_basket else 1
                                track_ok, track_trade_id, track_err = track_manual_trade(
                                    symbol, legs_for_tracking, basket_lots, lot_size, entry_ltps, trading_mode, trading_style,
                                    sl_amount=basket_sl_amount, target_amount=basket_target_amount, tag_prefix="BASKET",
                                )
                                log_orders_batch(order_ids, track_trade_id or "BASKET_UNTRACKED", symbol, trading_mode, basket_orders, status="COMPLETE")
                                if track_ok:
                                    st.caption(f"📍 Positions tab मध्ये ट्रॅक होत आहे (Trade ID: {track_trade_id}).")
                                else:
                                    st.warning(f"⚠️ ऑर्डर यशस्वी झाला, पण Positions tab मध्ये ट्रॅक करता आला नाही: {track_err}")
                                st.session_state.order_basket = []
                            else:
                                st.error(f"❌ Basket अयशस्वी: {resp}")
            else:
                st.caption("सद्य Basket रिकामी आहे.")

            # =========================================================
            # ८. Put-Call OI Diff Tracker — दर १० मिनिटांनी snapshot (Bullish/Bearish)
            #    Strike range: existing option chain टेबलप्रमाणेच ATM ± 6 (एकूण १३ strikes)
            # =========================================================
    with tab2:
        st.markdown("---")
        st.subheader("🧭 Nifty OI Put-Call Diff Tracker (ATM ±6 strikes · दर १० मिनिटांनी)")

        # 🎓 वापरकर्त्याच्या विनंतीनुसार — Expiry पर्यंत किती दिवस उरले (DTE) हे table वर दाखवणे.
        # raw_chain मधल्या प्रत्येक strike-item मध्ये स्वतःच 'expiry' field असते (Upstox चं standard
        # response) — त्यामुळे fetch_upstox_option_chain चं signature बदलावं लागलं नाही (५०+ ठिकाणी
        # वापरलेलं, ते बदलणं धोकादायक ठरलं असतं). expiry सापडली नाही तर शांतपणे काहीच दाखवत नाही.
        expiry_date, dte = compute_dte(raw_chain, get_ist_now().date())
        if expiry_date is not None:
            dte_label = "आजच Expiry! 🔥" if dte == 0 else f"{dte} दिवस उरले"
            dte_color = "#F23645" if dte is not None and dte <= 1 else "#d1d4dc"
            st.markdown(
                f"<span style='color:{dte_color}; font-size:14px; font-weight:600;'>"
                f"📅 Expiry: {expiry_date.strftime('%d-%b-%Y')} ({dte_label})</span>",
                unsafe_allow_html=True,
            )

        # 🎓 वापरकर्त्याशी चर्चा करून काढलेली सुधारणा — ही संपूर्ण गणना+साठवण आता एकाच, पुनर्वापर
        # करण्याजोग्या function मध्ये आहे (oi_analysis.fetch_and_save_oi_snapshot) — तेच नवीन
        # oi_snapshot_collector.py (browser बंद असतानाही चालणारी unattended script) वापरतं, त्यामुळे
        # Dashboard उघडलं की मधल्या काळात collector ने साठवलेले सर्व snapshots आपोआप टेबलमध्ये दिसतील.
        #
        # 🎓 वापरकर्त्याने प्रत्यक्ष screenshot दाखवून निदर्शनास आणलेला खरा bug — unattended scripts
        # साठी is_market_open() तपासणी जोडली होती, पण Dashboard चं स्वतःचं (browser उघडं असतानाचं)
        # snapshot-घेणं त्याच तपासणीशिवाय राहिलं होतं — त्यामुळे बाजार उघडण्याआधीही (उदा. 08:10, 08:20)
        # snapshots साठवले जात होते. आता इथेही तीच तपासणी.
        if not is_market_open():
            st.info(f"⏸️ बाजार बंद आहे (वेळेबाहेर/सुट्टी) — नवीन snapshot घेतला जाणार नाही. खालचा इतिहास पाहू शकता.")
            total_call_oi = total_put_oi = current_diff = 0
            oi_price_direction, oi_price_message = "NEUTRAL", "⚪ बाजार बंद आहे"
            put_oi_price_class = call_oi_price_class = "अपुरा डेटा"
        else:
            snapshot_result, snapshot_status = fetch_and_save_oi_snapshot(
                token_input, symbol, lambda t, s: (raw_chain, "OK"), get_ist_now, DB_PATH, atm_range=6,
            )
            if snapshot_result is None:
                st.warning(f"⚠️ OI Snapshot घेता आला नाही: {snapshot_status}")
                total_call_oi = total_put_oi = current_diff = 0
                oi_price_direction, oi_price_message = "NEUTRAL", "⚪ Snapshot अयशस्वी"
                put_oi_price_class = call_oi_price_class = "अपुरा डेटा"
            else:
                total_call_oi = snapshot_result["total_call_oi"]
                total_put_oi = snapshot_result["total_put_oi"]
                current_diff = snapshot_result["diff"]
                oi_price_direction = snapshot_result["oi_price_direction"]
                oi_price_message = snapshot_result["oi_price_message"]
                put_oi_price_class = snapshot_result["put_oi_price_class"]
                call_oi_price_class = snapshot_result["call_oi_price_class"]

        # 🎓 नवीन — ठळक, रंगीत Banner (Put/Call Writing/Buying/Covering वरून actionable संदेश)
        banner_bg = {"BULLISH": "#0d3320", "BEARISH": "#3a0d12", "MIXED": "#3a3410", "NEUTRAL": "#1e222d"}[oi_price_direction]
        banner_border = {"BULLISH": "#089981", "BEARISH": "#F23645", "MIXED": "#c9a227", "NEUTRAL": "#4b5563"}[oi_price_direction]
        st.markdown(
            f"""<div style="background-color:{banner_bg}; border-left: 5px solid {banner_border}; padding: 14px 18px;
            border-radius: 6px; margin: 10px 0;">
            <span style="font-size: 17px; font-weight: 700; color: #f0f0f0;">{oi_price_message}</span><br/>
            <span style="font-size: 12px; color: #aaa;">Put: {put_oi_price_class} · Call: {call_oi_price_class}</span>
            </div>""",
            unsafe_allow_html=True,
        )
        st.caption("⚠️ पहिल्याच snapshot ला 'अपुरा डेटा' दिसेल — इतिहास लागतो.")



        # आजच्या दिवसाचा संपूर्ण इतिहास दाखवणे (अलीकडचा वेळ सर्वात वर, स्क्रीनशॉटसारखे)
        # 🎓 Cloud DB (Supabase) configured असेल तर तिथून वाचणे — local unattended collector ने
        # साठवलेला डेटाही (browser बंद असतानाचा) इथे आपोआप दिसेल. नसेल तर जुन्याच local SQLite कडे वळणे.
        from cloud_db import is_cloud_db_configured, get_oi_history_cloud
        if is_cloud_db_configured():
            cloud_rows = get_oi_history_cloud(symbol, today_str)
            hist_df = pd.DataFrame([
                {"Time": r["snapshot_time"], "Total Call OI": r["total_call_oi"], "Total Put OI": r["total_put_oi"],
                 "Diff": r["diff"], "Δ Diff": r["delta_diff"], "Signal": r["signal"]}
                for r in cloud_rows
            ])
        else:
            conn3 = sqlite3.connect(DB_PATH)
            hist_df = pd.read_sql_query(
                """SELECT snapshot_time AS Time, total_call_oi AS "Total Call OI",
                          total_put_oi AS "Total Put OI", diff AS Diff,
                          delta_diff AS "Δ Diff", signal AS Signal
                   FROM oi_diff_snapshots
                   WHERE symbol=? AND trade_date=?
                   ORDER BY snapshot_time DESC""",
                conn3, params=(symbol, today_str)
            )
            conn3.close()

        def style_oi_numeric(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #089981; font-weight: bold;"
                elif val < 0:
                    return "color: #F23645; font-weight: bold;"
            return ""

        def style_oi_signal(val):
            s = str(val)
            if "BULLISH" in s and "Weak" not in s:
                return "color: #089981; font-weight: bold;"      # पूर्ण BULLISH → हिरवा
            if "BEARISH" in s and "Weak" not in s:
                return "color: #F23645; font-weight: bold;"      # पूर्ण BEARISH → लाल
            if "BULLISH" in s and "Weakening" in s:
                return "color: #F23645; font-weight: bold;"      # Bullish कमजोर होतोय → उलट (लाल) रंग, बेअरिशकडे झुकण्याचा इशारा
            if "BEARISH" in s and "Weakening" in s:
                return "color: #089981; font-weight: bold;"      # Bearish कमजोर होतोय → उलट (हिरवा) रंग, बुलिशकडे झुकण्याचा इशारा
            return "color: #9598a1; font-weight: bold;"

        # 🎓 वापरकर्त्याच्या विनंतीनुसार — मोठे आकडे वाचायला सोपे व्हावेत म्हणून लाखांत (1 लाख = 1,00,000)
        # दाखवणे. .style.format() वापरल्याने फक्त DISPLAY बदलतो — रंग-कोडिंग (style_oi_numeric) अजूनही
        # मूळ (न-बदललेल्या) संख्येवरच आधारित राहतं, त्यामुळे रंग बरोबरच राहतील.
        def format_lakh_unsigned(val):
            return f"{val/100000:,.2f} L" if isinstance(val, (int, float)) else val

        def format_lakh_signed(val):
            return f"{val/100000:+,.2f} L" if isinstance(val, (int, float)) else val

        styled_hist = hist_df.style.map(style_oi_numeric, subset=["Diff", "Δ Diff"]) \
                                    .map(style_oi_signal, subset=["Signal"]) \
                                    .format({
                                        "Total Call OI": format_lakh_unsigned, "Total Put OI": format_lakh_unsigned,
                                        "Diff": format_lakh_signed, "Δ Diff": format_lakh_signed,
                                    }) \
                                    .set_properties(**{'font-size': '15px', 'font-weight': 'bold'})

        st.dataframe(styled_hist, width='stretch', height=450)

        with st.expander("📈 Advanced OI Charts (PCR + Multi-Strike + Replay) — क्लिक करून उघडा", expanded=False):
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "Option OI vs Time" सारखा
            # chart (PCR + NIFTY किंमत, वेळेनुसार) — established get_oi_price_history_cloud() (आधीच
            # साठवलेला underlying_price वापरून) पुनर्वापर करून.
            st.markdown("##### 📈 PCR + किंमत — वेळेनुसार (Sensibull-सारखं)")
            try:
                if is_cloud_db_configured():
                    from cloud_db import get_oi_price_history_cloud
                    price_history_rows = get_oi_price_history_cloud(symbol, today_str)
                else:
                    conn_ph = sqlite3.connect(DB_PATH)
                    price_history_rows = pd.read_sql_query(
                        """SELECT snapshot_time, total_call_oi, total_put_oi, underlying_price
                           FROM oi_diff_snapshots WHERE symbol=? AND trade_date=?
                           ORDER BY snapshot_time ASC""",
                        conn_ph, params=(symbol, today_str),
                    ).to_dict("records")
                    conn_ph.close()

                if not price_history_rows:
                    st.caption("अजून पुरेसा इतिहास नाही (किमान २ snapshots हवेत).")
                else:
                    ph_df = pd.DataFrame(price_history_rows)
                    ph_df["pcr"] = ph_df.apply(lambda r: (r["total_put_oi"] / r["total_call_oi"]) if r["total_call_oi"] else 0, axis=1)

                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots
                    fig_pcr = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_pcr.add_trace(go.Bar(x=ph_df["snapshot_time"], y=ph_df["total_put_oi"], name="Put OI", marker_color="#089981", opacity=0.5), secondary_y=False)
                    fig_pcr.add_trace(go.Bar(x=ph_df["snapshot_time"], y=ph_df["total_call_oi"], name="Call OI", marker_color="#F23645", opacity=0.5), secondary_y=False)
                    fig_pcr.add_trace(go.Scatter(x=ph_df["snapshot_time"], y=ph_df["pcr"], name="PCR", line=dict(color="#2962ff", width=2)), secondary_y=True)
                    if ph_df["underlying_price"].notna().any():
                        fig_pcr.add_trace(go.Scatter(x=ph_df["snapshot_time"], y=ph_df["underlying_price"], name=symbol, line=dict(color="#787b86", width=2)), secondary_y=True)
                    fig_pcr.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=30, b=10), barmode="group")
                    fig_pcr.update_yaxes(title_text="OI", secondary_y=False)
                    fig_pcr.update_yaxes(title_text="PCR / किंमत", secondary_y=True)
                    st.plotly_chart(fig_pcr, use_container_width=True)
            except Exception as e:
                st.caption(f"PCR chart मध्ये चूक: {type(e).__name__}: {e}")

            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "Multi Strike OI" सारखं —
            # निवडलेल्या strikes चा OI, वेळेनुसार. आजपासूनच डेटा जमा होईल (आधी per-strike इतिहास साठवलाच
            # जात नव्हता), त्यामुळे सुरुवातीला थोडा (काही तासांचा) इतिहासच दिसेल.
            st.markdown("##### 📊 Multi-Strike OI (वेळेनुसार) — आजपासूनचा इतिहास")
            # 🎓 वापरकर्त्याने आधी दाखवलेल्या UnboundLocalError शीच सुसंगत, डीफेन्सिव्ह default —
            # खालच्या try-block मध्ये कुठेही exception आलं (assignment आधीच), तरी पुढच्या (Replay)
            # विभागात हा variable कधीच "undefined" राहणार नाही.
            all_strike_oi = None
            try:
                if is_cloud_db_configured():
                    from cloud_db import get_strike_oi_history
                    all_strike_oi = get_strike_oi_history(symbol, today_str)
                else:
                    all_strike_oi = None
                    st.caption("Cloud DB configured नाही — Multi-Strike OI साठी Supabase हवाच.")

                if all_strike_oi is None or all_strike_oi.empty:
                    st.caption("अजून कुठलाही per-strike इतिहास नाही — collector काही वेळ चालल्यावर इथे दिसेल.")
                else:
                    available_msoi_strikes = sorted(all_strike_oi["strike"].unique())
                    default_strikes = [s for s in available_msoi_strikes if abs(s - atm_strike) <= 100]
                    selected_strikes = st.multiselect("कुठले Strikes बघायचे", available_msoi_strikes, default=default_strikes or available_msoi_strikes[:4])

                    if selected_strikes:
                        filtered = all_strike_oi[all_strike_oi["strike"].isin(selected_strikes)]
                        import plotly.graph_objects as go
                        fig_msoi = go.Figure()
                        for (strike_val, opt_type), grp in filtered.groupby(["strike", "option_type"]):
                            grp_sorted = grp.sort_values("snapshot_time")
                            fig_msoi.add_trace(go.Scatter(
                                x=grp_sorted["snapshot_time"], y=grp_sorted["oi"],
                                name=f"{strike_val:.0f} {opt_type}", mode="lines+markers",
                            ))
                        fig_msoi.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=30, b=10),
                                                xaxis_title="वेळ", yaxis_title="Open Interest")
                        st.plotly_chart(fig_msoi, use_container_width=True)
            except Exception as e:
                st.caption(f"Multi-Strike OI मध्ये चूक: {type(e).__name__}: {e}")

            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "OI Change Replay" सारखं —
            # दिवसभरातल्या प्रत्येक strike च्या OI बदलाचं animated playback (Plotly frames वापरून).
            st.markdown("##### 🎬 OI Change Replay (दिवसभराचं Playback)")
            try:
                if is_cloud_db_configured() and all_strike_oi is not None and not all_strike_oi.empty:
                    replay_times = sorted(all_strike_oi["snapshot_time"].unique())
                    if len(replay_times) < 2:
                        st.caption("Replay साठी किमान २ snapshots हवेत — अजून पुरेसा इतिहास जमा झालेला नाही.")
                    else:
                        import plotly.graph_objects as go
                        all_replay_strikes = sorted(all_strike_oi["strike"].unique())
                        frames = []
                        for t in replay_times:
                            snap = all_strike_oi[all_strike_oi["snapshot_time"] == t]
                            ce_vals = [snap[(snap["strike"] == s) & (snap["option_type"] == "CE")]["oi"].sum() for s in all_replay_strikes]
                            pe_vals = [snap[(snap["strike"] == s) & (snap["option_type"] == "PE")]["oi"].sum() for s in all_replay_strikes]
                            frames.append(go.Frame(
                                data=[go.Bar(x=all_replay_strikes, y=ce_vals, name="Call OI", marker_color="#F23645"),
                                      go.Bar(x=all_replay_strikes, y=pe_vals, name="Put OI", marker_color="#089981")],
                                name=t,
                            ))
                        fig_replay = go.Figure(data=frames[0].data, frames=frames)
                        fig_replay.update_layout(
                            template="plotly_dark", height=400, margin=dict(l=10, r=10, t=30, b=10), barmode="group",
                            xaxis_title="Strike", yaxis_title="Open Interest",
                            updatemenus=[{"type": "buttons", "buttons": [
                                {"label": "▶️ Play", "method": "animate", "args": [None, {"frame": {"duration": 700, "redraw": True}, "fromcurrent": True}]},
                                {"label": "⏸️ Pause", "method": "animate", "args": [[None], {"frame": {"duration": 0}, "mode": "immediate"}]},
                            ]}],
                            sliders=[{"steps": [{"args": [[t], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                                                  "label": t, "method": "animate"} for t in replay_times]}],
                        )
                        st.plotly_chart(fig_replay, use_container_width=True)
                else:
                    st.caption("Replay साठी Multi-Strike OI डेटा हवा (वर बघा).")
            except Exception as e:
                st.caption(f"OI Change Replay मध्ये चूक: {type(e).__name__}: {e}")


        with st.expander("ℹ️ Signal Logic कसं काम करतं"):
            st.caption(
                "Diff = एकूण Put OI − एकूण Call OI. धन (+) = Put जास्त लिहिले → बुल्स मजबूत. ऋण (−) = Call जास्त लिहिले → बेअर्स मजबूत.\n\n"
                "**Strong vs Weakening** (मागच्या ~३० मिनिटांच्या तुलनेत):\n"
                "- 🟢 BULLISH (Strong): Diff+ आणि Put OI खरंच वाढतोय\n"
                "- 🟡 BULLISH (Weakening): Diff+ पण Put OI वाढत नाही (रंग उलट)\n"
                "- 🔴 BEARISH (Strong): Diff− आणि Call OI खरंच वाढतोय\n"
                "- 🟠 BEARISH (Weakening): Diff− पण Call OI वाढत नाही (रंग उलट)\n\n"
                "**स्थिरता**: दिशा बदलण्यासाठी सलग ३ स्नॅपशॉट्समध्ये तीच नवीन दिशा हवी — भिरभिरणं (flip-flop) टाळण्यासाठी."
            )

        # =========================================================
        # ८.५ Advanced OI Analysis (Professional) — OI-Price Matrix, PCR, Max Pain, Rollover
        # =========================================================
        st.markdown("---")
    with tab2:
        st.subheader("📐 Advanced OI Analysis (Professional)")

        matrix_mode = "SWING" if trading_style == "SWING" else "INTRADAY"

        if matrix_mode == "SWING":
            prev_total_oi = get_previous_day_total_oi(symbol)
            # आजचा नवीनतम snapshot (किंमतीसह) — OI Diff Tracker सेक्शनने आत्ताच रेकॉर्ड केलेला
            prev_price = None
            conn_pm = sqlite3.connect(DB_PATH)
            cur_pm = conn_pm.cursor()
            cur_pm.execute(
                "SELECT underlying_price FROM oi_diff_snapshots WHERE symbol=? AND trade_date < ? ORDER BY trade_date DESC, snapshot_time DESC LIMIT 1",
                (symbol, today_str),
            )
            row_pm = cur_pm.fetchone()
            conn_pm.close()
            if row_pm:
                prev_price = row_pm[0]
            current_total_oi_for_matrix = total_call_oi + total_put_oi
            oi_matrix_display = compute_oi_price_matrix(current_total_oi_for_matrix, prev_total_oi, underlying_price, prev_price)
            matrix_period_label = "आजचा वि. आधीचा ट्रेडिंग दिवस"
        else:
            # Intraday: गेल्या दोन 10-मिनिटांच्या snapshots मधून
            conn_pm = sqlite3.connect(DB_PATH)
            cur_pm = conn_pm.cursor()
            cur_pm.execute(
                "SELECT total_call_oi, total_put_oi, underlying_price FROM oi_diff_snapshots WHERE symbol=? AND trade_date=? ORDER BY snapshot_time DESC LIMIT 2",
                (symbol, today_str),
            )
            rows_pm = cur_pm.fetchall()
            conn_pm.close()
            if len(rows_pm) >= 2:
                (call_now, put_now, price_now), (call_prev, put_prev, price_prev) = rows_pm[0], rows_pm[1]
                oi_matrix_display = compute_oi_price_matrix(call_now + put_now, call_prev + put_prev, price_now, price_prev)
            else:
                oi_matrix_display = None
            matrix_period_label = "गेल्या 10 मिनिटांत"

        pcr_val, pcr_bias = compute_pcr_signal(total_put_oi, total_call_oi)
        max_pain_strike_val = compute_max_pain(raw_chain)

        adv1, adv2 = st.columns(2)
        with adv1:
            st.markdown(f"##### 🔄 OI-Price Matrix ({trading_style})")
            if oi_matrix_display and oi_matrix_display["category"] != "INSUFFICIENT_DATA":
                m_color = "#089981" if oi_matrix_display["bias"] == "BULLISH" else "#F23645"
                st.markdown(
                    f"**{oi_matrix_display['category'].replace('_',' ').title()}** — "
                    f"<span style='color:{m_color};font-weight:bold;'>{oi_matrix_display['bias']}</span> "
                    f"({oi_matrix_display['strength']})",
                    unsafe_allow_html=True,
                )
                st.caption(f"एकूण (Call+Put) OI व किंमत बदल ({matrix_period_label}) वरून काढलेलं.")
            else:
                st.info("पुरेसा डेटा अजून नाही" + (" (Swing साठी किमान एक आधीचा ट्रेडिंग दिवस लागतो)." if matrix_mode == "SWING" else "."))

        with adv2:
            st.markdown("##### ⚖️ PCR (Put-Call Ratio)")
            if pcr_val is not None:
                pcr_color = "#089981" if pcr_bias == "BULLISH" else ("#F23645" if pcr_bias == "BEARISH" else "#787b86")
                st.markdown(f"**PCR: {pcr_val}** — <span style='color:{pcr_color};font-weight:bold;'>{pcr_bias}</span>", unsafe_allow_html=True)
                st.caption("PCR<0.70 Bullish(Oversold) · 0.70-0.90 Bearish · 0.90-1.0 Sideways · 1.0-1.3 Bullish · >1.3 Bearish(Overbought)")
            else:
                st.info("PCR काढण्यासाठी पुरेसा OI डेटा नाही.")

        adv3, adv4 = st.columns(2)
        with adv3:
            st.markdown("##### 🎯 Max Pain")
            if max_pain_strike_val is not None:
                diff_from_spot = max_pain_strike_val - underlying_price
                st.metric("Max Pain Strike", f"{max_pain_strike_val:.0f}", f"स्पॉटपासून {diff_from_spot:+,.0f}")
                st.caption("Expiry जवळ किंमत या strike कडे झुकण्याची शक्यता असते (सर्व उपलब्ध strikes वापरून काढलेलं).")
            else:
                st.info("Max Pain काढण्यासाठी पुरेसा OI डेटा नाही.")

        with adv4:
            st.markdown("##### 📅 Rollover Analysis")
            st.caption("पुढच्या expiry चा डेटा लागतो म्हणून हे on-demand आहे (extra API कॉल्स).")
            if st.button("🔍 Rollover काढा", key="rollover_btn"):
                with st.spinner("पुढच्या expiry चा डेटा फेच होत आहे..."):
                    near_chain_ro = raw_chain
                    next_chain_ro, next_expiry_ro = fetch_next_expiry_option_chain(token_input, symbol)
                    rollover_display = compute_rollover_proxy(near_chain_ro, next_chain_ro, atm_strike) if next_chain_ro else None
                    st.session_state["rollover_cache"] = rollover_display
                if rollover_display:
                    st.metric("Rollover %", f"{rollover_display['rollover_pct']}%")
                    coc_str = f"₹{rollover_display['cost_of_carry']:+,.2f}" if rollover_display["cost_of_carry"] is not None else "N/A"
                    st.caption(
                        f"Cost-of-Carry (पुढची − जवळची synthetic future): {coc_str} → Bias: {rollover_display['bias']}\n\n"
                        f"Near OI: {rollover_display['near_expiry_total_oi']:,} · Next OI: {rollover_display['next_expiry_total_oi']:,}"
                    )
                else:
                    st.warning("Rollover डेटा मिळाला नाही (पुढची expiry उपलब्ध नसेल किंवा API त्रुटी).")


        # =========================================================
        # ९. A1 SIGNAL ENGINE — Market Structure → Break/Pullback/Retest → RSI →
        #    Confirmation → VIX Filter → Strategy Selection → Risk/PoP → LIVE EXECUTION
        #    (सर्व टाईमफ्रेम्स Intraday/Swing style नुसार बदलतात — वर Direction Engine मध्ये सेट केलेले tf_cfg वापरून)
        # =========================================================
        st.markdown("---")
    with tab3:
        st.subheader(f"🧬 A1 Signal Engine ({trading_style}) — पूर्ण पाईपलाईन")

        pipeline_direction = direction_final if "direction_final" in locals() and direction_final in ("BULLISH", "BEARISH") else None

        pattern_rsi_ok = True
        pattern_detected = None
        pattern_rsi_value = None
        intraday_strategy_detail = None

        # Structure टाईमफ्रेम डेटा (आधीच Direction Engine साठी fetch केलेला df_structure_tf पुन्हा वापरणे)
        structure_info = classify_market_structure(df_structure_tf) if not df_structure_tf.empty else {"structure": "INSUFFICIENT_DATA", "last_swing_high": None, "last_swing_low": None}

        broke, broken_level = (False, None)
        pulled_back, retested = (False, False)
        confirmed_5m = False
        zone = None
        df_confirm_tf = pd.DataFrame()
        sr_levels = None
        trendline_support = None
        trendline_resistance = None
        trend_signal = {"gate_ok": True, "gate_reason": "पुरेसा डेटा नाही — गेट वगळला", "caution": None}

        # rsi_check नेहमी काढणे (दिशा NEUTRAL असली तरी) — Sideways Detection ला rsi_check["rsi"] लागतेच;
        # आधी हे फक्त pipeline_direction असेल तेव्हाच काढले जायचे, त्यामुळे Sideways मार्ग कधीच खरा ठरत नव्हता.
        rsi_check = rsi_momentum_and_divergence(df_structure_tf, rsi_series, pipeline_direction or "BULLISH")

        if pipeline_direction and trading_style == "INTRADAY":
            # नवीन Signal Engine — दोन्ही रणनीतींसाठी एकच संपूर्ण entry-तपासणी (Market Structure/Break/
            # Pullback/Retest ऐवजी). broke/pulled_back/retested तिन्ही याच एका निकालाशी जोडलेली आहेत,
            # जेणेकरून खालचं all_gates_passed चं सूत्र बदलावं लागणार नाही.
            if intraday_strategy_mode == "price_action":
                entry_ok, intraday_strategy_detail = check_price_action_strategy(
                    df_structure_tf, pipeline_direction, rsi_series=rsi_series,
                    sr_window=sr_window, rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
                    sl_buffer_pct=sl_buffer_pct, min_rr=min_rr,
                    retest_tolerance_pct=retest_tolerance_pct, reversal_lookback=reversal_lookback,
                    df_1h=df_1h,
                )
            else:
                entry_ok, intraday_strategy_detail = check_indicator_strategy(df_structure_tf, rsi_series, pipeline_direction)
            broke, pulled_back, retested = entry_ok, entry_ok, entry_ok
            confirmed_5m = entry_ok

            sr_levels = find_support_resistance_levels(df_structure_tf)
            trendline_support = detect_trendline(df_structure_tf, swing_type="low")
            trendline_resistance = detect_trendline(df_structure_tf, swing_type="high")
            trend_signal = check_trend_signal(pipeline_direction, trendline_support, trendline_resistance, sr_levels)

        elif pipeline_direction:
            broke, broken_level = detect_break(df_structure_tf, structure_info, pipeline_direction)
            pulled_back, retested = detect_pullback_retest(df_structure_tf, broken_level, pipeline_direction)
            zone = supply_demand_zone(structure_info, pipeline_direction)
            df_confirm_tf = df_rsi_tf if confirm_interval == rsi_interval else fetch_timeframe_df(
                token_input, symbol, underlying_price, confirm_interval
            )
            confirmed_5m = confirm_5m(df_confirm_tf, pipeline_direction) if not df_confirm_tf.empty else False

            # --- Multi-level Support/Resistance + Trendline (Structure टाईमफ्रेमवर) ---
            sr_levels = find_support_resistance_levels(df_structure_tf)
            trendline_support = detect_trendline(df_structure_tf, swing_type="low")
            trendline_resistance = detect_trendline(df_structure_tf, swing_type="high")
            trend_signal = check_trend_signal(pipeline_direction, trendline_support, trendline_resistance, sr_levels)

        india_vix = fetch_india_vix(token_input)
        vix_ok = (india_vix is not None) and (india_vix <= vix_max_threshold)

        # --- OI Confirmation Gate — Intraday (10-min snapshot) किंवा Swing (OI-Price Matrix + PCR + Max Pain + Rollover) ---
        oi_signal_latest = None
        oi_confirmation_ok = True
        oi_gate_note = "N/A (गेट बंद आहे)"
        swing_gate_detail = None

        if trading_style == "INTRADAY" and enable_oi_gate and pipeline_direction:
            oi_signal_latest = get_latest_oi_signal(symbol)
            oi_confirmation_ok = check_oi_diff_entry_gate(pipeline_direction, oi_signal_latest)
            oi_gate_note = oi_signal_latest or "OI डेटा उपलब्ध नाही"
        elif trading_style == "SWING" and enable_swing_oi_gate and pipeline_direction:
            _prev_total_oi_g = get_previous_day_total_oi(symbol)
            _conn_g = sqlite3.connect(DB_PATH)
            _cur_g = _conn_g.cursor()
            _cur_g.execute(
                "SELECT underlying_price FROM oi_diff_snapshots WHERE symbol=? AND trade_date < ? ORDER BY trade_date DESC, snapshot_time DESC LIMIT 1",
                (symbol, today_str),
            )
            _row_g = _cur_g.fetchone()
            _conn_g.close()
            _prev_price_g = _row_g[0] if _row_g else None

            _oi_matrix_g = compute_oi_price_matrix(total_call_oi + total_put_oi, _prev_total_oi_g, underlying_price, _prev_price_g)
            _pcr_val_g, _pcr_bias_g = compute_pcr_signal(total_put_oi, total_call_oi)
            _max_pain_g = compute_max_pain(raw_chain)
            _rollover_g = st.session_state.get("rollover_cache")  # वरील Advanced OI Analysis सेक्शनमधील बटणाने कॅश केलेला (ऐच्छिक)

            oi_confirmation_ok, swing_gate_detail = swing_oi_gate(
                pipeline_direction, _oi_matrix_g, _pcr_bias_g, _max_pain_g, underlying_price, _rollover_g,
                max_opposing=swing_max_opposing_signals,
            )
            oi_gate_note = (
                f"Supporting: {len(swing_gate_detail['supporting'])}, Opposing: {len(swing_gate_detail['opposing'])} "
                f"of {swing_gate_detail['total_signals']} signals"
            )

        with st.expander("🔍 Signal Engine — प्रत्येक पायरीचा तपशील (Diagnostic)", expanded=False):
            # --- पाईपलाईन चेकलिस्ट दाखवणे ---
            pc1, pc2 = st.columns(2)
            with pc1:
                st.markdown(f"**Direction Engine:** {pipeline_direction or 'NEUTRAL / अपुरा डेटा'}")
                st.markdown(f"**Market Structure ({structure_tf_label}):** {structure_info['structure']}")
                st.markdown(f"**Break Detection:** {'✅ ब्रेक झाली' if broke else '❌ अजून नाही'}" + (f" (level: {broken_level:,.2f})" if broken_level else ""))
                st.markdown(f"**Pullback:** {'✅' if pulled_back else '❌'}   **Retest:** {'✅' if retested else '❌'}")
            with pc2:
                rsi_val_str = f"{rsi_check['rsi']:.1f}" if rsi_check["rsi"] is not None else "—"
                st.markdown(f"**RSI Momentum ({rsi_tf_label}):** {'✅ जुळते' if rsi_check['momentum_ok'] else '❌ जुळत नाही'} (RSI: {rsi_val_str})")
                st.markdown(f"**RSI Divergence:** {rsi_check['divergence']}")
                st.markdown(f"**Confirmation ({confirm_tf_label}):** {'✅' if confirmed_5m else '❌'}")
                st.markdown(f"**Supply/Demand Zone:** {zone if zone else '—'}")

            st.markdown(
                f"**Trendline Gate ({structure_tf_label}):** {'✅ ' + trend_signal['gate_reason'] if trend_signal['gate_ok'] else '❌ ' + trend_signal['gate_reason']}"
            )
            if trend_signal["caution"]:
                st.warning(f"⚠️ {trend_signal['caution']}")
            if sr_levels and (sr_levels.get("support") or sr_levels.get("resistance")):
                sr_parts = []
                if sr_levels["support"]:
                    sr_parts.append("Support: " + ", ".join(f"{s['level']:.0f} ({s['touches']}x)" for s in sr_levels["support"]))
                if sr_levels["resistance"]:
                    sr_parts.append("Resistance: " + ", ".join(f"{r['level']:.0f} ({r['touches']}x)" for r in sr_levels["resistance"]))
                st.caption(" · ".join(sr_parts))

            if trading_style == "INTRADAY" and pipeline_direction and intraday_strategy_detail:
                strategy_label = "Price Action (Support/Resistance + RSI + Candlestick)" if intraday_strategy_mode == "price_action" else "Indicator (RSI 25-55/45-75+Pattern)"
                st.markdown(f"**Signal Engine — {strategy_label}:** {'✅ जुळलं' if broke else '❌ जुळलं नाही'}")
                if intraday_strategy_mode == "price_action":
                    rc = intraday_strategy_detail.get("reversal_candle")
                    rsi_v = intraday_strategy_detail.get("rsi_value")
                    st.caption(
                        f"S/R Retest: {'✅' if intraday_strategy_detail.get('sr_retest') else '❌'} · "
                        f"Trendline Retest: {'✅' if intraday_strategy_detail.get('trendline_retest') else '❌'} · "
                        f"RSI: {f'{rsi_v:.1f}' if rsi_v is not None else '—'} ({intraday_strategy_detail.get('divergence')}) · "
                        f"Reversal Candle: {rc['pattern'] if rc else 'नाही'} · "
                        f"Breakout: {'✅' if intraday_strategy_detail.get('breakout_confirmed') else '❌'}"
                    )
                    trade_plan = intraday_strategy_detail.get("trade_plan")
                    if trade_plan:
                        st.caption(
                            f"🎯 Entry: **{trade_plan['entry']:,}** · SL: {trade_plan['sl']:,} · "
                            f"Target: {trade_plan['target']:,} · R:R = 1:{trade_plan['rr']}"
                        )
                else:
                    st.caption(f"Pattern: {intraday_strategy_detail.get('pattern') or '—'} · RSI(15M): {intraday_strategy_detail.get('rsi'):.1f}" if intraday_strategy_detail.get("rsi") is not None else f"Pattern: {intraday_strategy_detail.get('pattern') or '—'}")

            vix_str = f"{india_vix:.2f}" if india_vix is not None else "उपलब्ध नाही"
            st.markdown(f"**India VIX:** {vix_str} — {'✅ ट्रेडिंगसाठी ठीक' if vix_ok else '🚫 NO TRADE (VIX जास्त / अनुपलब्ध)'}")

            if trading_style == "INTRADAY" and enable_oi_gate:
                oi_display = oi_signal_latest if oi_signal_latest else "अनुपलब्ध"
                st.markdown(
                    f"**OI Diff Entry Gate (Price Action + Indicator दोन्हीसाठी सामायिक):** {'✅ जुळते' if oi_confirmation_ok else '❌ OI विरोधात'} "
                    f"— सद्य OI सिग्नल: {oi_display}"
                )
            elif trading_style == "SWING" and enable_swing_oi_gate:
                st.markdown(
                    f"**OI+PCR+MaxPain+Rollover Gate (Swing):** {'✅ जुळते' if oi_confirmation_ok else '❌ विरोधात'} — {oi_gate_note}"
                )
                if swing_gate_detail:
                    if swing_gate_detail["supporting"]:
                        st.caption("समर्थन देणारे: " + ", ".join(f"{name} ({bias})" for name, bias in swing_gate_detail["supporting"]))
                    if swing_gate_detail["opposing"]:
                        st.caption("विरोध करणारे: " + ", ".join(f"{name} ({bias})" for name, bias in swing_gate_detail["opposing"]))


        # --- सर्व गेट्स एकत्र तपासणे (डायरेक्शनल मार्ग) ---
        all_gates_passed = bool(
            pipeline_direction and broke and pulled_back and retested
            and rsi_check["momentum_ok"] and confirmed_5m and vix_ok and oi_confirmation_ok
            and trend_signal["gate_ok"] and pattern_rsi_ok
        )

        # --- Sideways मार्ग — डायरेक्शन Engine NEUTRAL/MIXED असेल तेव्हाच तपासले जाते ---
        sideways_info = None
        if not pipeline_direction:
            sideways_info = classify_sideways(
                df_structure_tf, structure_info, rsi_check, india_vix, vix_max_threshold,
                tight_range_pct=sideways_tight_range_pct, max_range_pct=sideways_max_range_pct,
            )

        strategy_result = None
        lots, risk_amount = 0, 0.0
        available_margin = None

        if all_gates_passed:
            # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — Price Action/Indicator (आपल्या २ मुख्य
            # strategies) साठी आता PoP-आधारित शोध ऐवजी निश्चित (fixed) ATM+2/Hedge+4(100pt) strike
            # selection वापरलं जातं. Iron Condor/Butterfly (sideways मार्ग, खाली) याला स्पर्श केलेला
            # नाही — तो अजूनही जुन्याच PoP-आधारित पद्धतीने चालतो.
            strategy_result = select_credit_spread_fixed_strikes(raw_chain, pipeline_direction, atm_strike)
        elif sideways_info and sideways_info["is_sideways"]:
            if sideways_info["strategy_type"] == "IRON_BUTTERFLY":
                strategy_result = select_iron_butterfly(raw_chain, atm_strike, hedge_width_points, pop_threshold_pct)
            else:
                strategy_result = select_iron_condor(raw_chain, atm_strike, step, hedge_width_points, pop_threshold_pct)

        if strategy_result:
            available_margin = get_available_margin(token_input)
            lots, risk_amount = compute_position_size(available_margin, risk_pct_per_trade, strategy_result["max_loss"], lot_size)

        st.markdown("---")
    with tab3:
        st.subheader("📐 Strategy Selection & Risk Sizing")

        if sideways_info is not None:
            st.markdown(
                f"**Sideways Check (Range: {sideways_info['range_pct']}%):** "
                f"Structure {'✅' if sideways_info['structure_ok'] else '❌'} · "
                f"RSI 40-60 {'✅' if sideways_info['rsi_ok'] else '❌'} · "
                f"No Break {'✅' if sideways_info['no_break'] else '❌'} · "
                f"Range ≤ threshold {'✅' if sideways_info['range_ok'] else '❌'} · "
                f"VIX {'✅' if sideways_info['vix_ok'] else '❌'}"
                + (f" → **{sideways_info['strategy_type']}**" if sideways_info["is_sideways"] else "")
            )

        sideways_qualified = bool(sideways_info and sideways_info["is_sideways"])

        if not all_gates_passed and not sideways_qualified:
            st.info("🚫 **FINAL A1 SIGNAL: NO TRADE** — ना directional गेट्स पूर्ण झाले, ना Sideways अटी जुळल्या.")
        elif strategy_result is None:
            st.warning(f"🚫 **NO TRADE** — दिलेल्या PoP ≥ {pop_threshold_pct}% अटीनुसार योग्य स्ट्रॅटेजी सापडली नाही.")
        else:
            legs = normalize_legs(strategy_result)
            pop_display = strategy_result.get("short_pop_pct", strategy_result.get("combined_pop_pct"))

            scol1, scol2, scol3 = st.columns(3)
            with scol1:
                st.metric("Strategy", strategy_result["strategy"].replace("_", " "))
                st.caption(f"PoP (approx): {pop_display}%")
                for leg in legs:
                    st.caption(f"{leg['role'].replace('_',' ').title()}: **{leg['strike']:.0f}** ({leg['transaction_type']})")
            with scol2:
                st.metric("Net Credit (per unit)", f"₹{strategy_result['net_credit']:.2f}")
                st.metric("Max Profit / lot", f"₹{strategy_result['max_profit'] * lot_size:,.0f}")
                st.metric("Max Loss / lot", f"₹{strategy_result['max_loss'] * lot_size:,.0f}")
            with scol3:
                margin_str = f"₹{available_margin:,.0f}" if available_margin is not None else "अनुपलब्ध"
                st.metric("Available Margin", margin_str)
                st.metric(f"Risk Amount ({risk_pct_per_trade}%)", f"₹{risk_amount:,.0f}")
                st.metric("Position Size", f"{lots} lot(s)")

            todays_pnl, todays_trade_count = get_todays_realized_pnl(symbol, trading_mode)
            circuit_breaker_ok = (todays_pnl > -max_daily_loss) and (todays_trade_count < max_trades_per_day)

            ist_now_time = get_ist_now().time()
            entry_cutoff_ok = True
            if trading_style == "INTRADAY" and entry_cutoff_time is not None:
                entry_cutoff_ok = ist_now_time < entry_cutoff_time

            st.caption(
                f"आजचा वास्तविक P&L: ₹{todays_pnl:,.0f} · आजचे ट्रेड्स: {todays_trade_count}/{max_trades_per_day} · "
                f"Circuit Breaker: {'🟢 OK' if circuit_breaker_ok else '🔴 BREACHED — नवीन ट्रेड ब्लॉक'} · "
                f"Style: {trading_style}"
            )

            if lots < 1:
                st.warning("🚫 **NO TRADE** — दिलेल्या Risk % नुसार 1 लॉटसाठीही पुरेसे मार्जिन उपलब्ध नाही.")
            elif not circuit_breaker_ok:
                st.error("🚫 **NO TRADE** — दैनिक सर्किट ब्रेकर (कमाल तोटा / कमाल ट्रेड्स) गाठला गेला आहे.")
            elif not entry_cutoff_ok:
                st.warning(f"🚫 **NO TRADE** — Intraday एंट्री कटऑफ वेळ ({entry_cutoff_time.strftime('%H:%M')} IST) उलटून गेली आहे.")
            else:
                mode_label = "PAPER (Simulated)" if trading_mode == "PAPER" else "LIVE"
                st.success(f"✅ **FINAL A1 SIGNAL: {mode_label}** — {strategy_result['strategy'].replace('_',' ')}, {lots} lot(s), सर्व गेट्स पास.")
                if enable_live_trading and confirm_live_trading:
                    spinner_text = "Paper ऑर्डर सिम्युलेट होत आहे..." if trading_mode == "PAPER" else "लाईव्ह ऑर्डर प्लेस होत आहे..."
                    with st.spinner(spinner_text):
                        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — Price Action/Indicator strategies
                        # आहे तशाच (त्याच timeframes/logic सह) ठेवल्या, पण आता EOD Square-off होत नाही —
                        # trading_style="SWING" पाठवलं जातं (manage_open_trades चा EOD check फक्त
                        # trading_style=="INTRADAY" असेल तरच लागू होतो), जेणेकरून position दुसऱ्या
                        # दिवशीही continue राहील. Sidebar वरचा "Intraday" label मात्र तसाच आहे (फक्त
                        # timeframe/strategy निवडीसाठी वापरला जातो).
                        # 🎓 नवीन risk management नियम (वापरकर्त्याशी चर्चा करून ठरवलेला) — SL = net_credit
                        # च्या 30%, Target सुद्धा 30% (max_profit==net_credit असल्याने आपोआप). हे फक्त
                        # BULL_PUT_SPREAD/BEAR_CALL_SPREAD (Price Action/Indicator) साठीच — Iron
                        # Condor/Butterfly (sideways) असल्यास जुनीच sidebar-टक्केवारी पद्धत वापरली जाते.
                        is_directional_2strategy = strategy_result["strategy"] in ("BULL_PUT_SPREAD", "BEAR_CALL_SPREAD")
                        ok, resp = open_multi_leg_trade(
                            token_input, symbol, strategy_result, lots, lot_size,
                            sl_pct_of_max_loss, 30 if is_directional_2strategy else target_pct_of_max_profit,
                            product_type, trading_mode=trading_mode, trading_style="SWING",
                            sl_pct_of_credit=30 if is_directional_2strategy else None,
                            source="DASHBOARD",
                        )
                    if ok:
                        result_emoji = "📝" if trading_mode == "PAPER" else "🟢"
                        st.success(f"{result_emoji} {mode_label} ऑर्डर प्लेस झाला — Trade ID: {resp['trade_id']}, Order IDs: {resp['order_ids']}")
                    else:
                        st.error(f"❌ ऑर्डर प्लेसमेंट अयशस्वी: {resp}")
                else:
                    st.info("ℹ️ लाईव्ह एक्झिक्युशनसाठी साईडबारमध्ये 'ENABLE LIVE TRADING' + पुष्टीकरण दोन्ही टिक करा.")

        # (उघड्या ट्रेड्सचे SL/Target/EOD मॉनिटरिंग आता shared_context.py मध्ये हलवलेलं आहे — जेणेकरून हे
        # प्रत्येक page वर चालेल, फक्त Dashboard उघडी असतानाच नाही — आधीचा गंभीर gap इथेच होता.)

        conn_lt = sqlite3.connect(DB_PATH)
        open_df = pd.read_sql_query(
            """SELECT trade_id AS "Trade ID", mode AS "Mode", strategy AS Strategy, short_strike AS "Short", long_strike AS "Long",
                      lots AS Lots, net_credit AS "Credit/unit", max_profit AS "Max Profit",
                      max_loss AS "Max Loss", entry_time AS "Entry Time"
               FROM live_trades WHERE symbol=? AND status='OPEN' ORDER BY entry_time DESC""",
            conn_lt, params=(symbol,),
        )
        closed_df = pd.read_sql_query(
            """SELECT trade_id AS "Trade ID", mode AS "Mode", strategy AS Strategy, exit_reason AS "Exit Reason",
                      realized_pnl AS "Realized P&L", entry_time AS "Entry Time", exit_time AS "Exit Time"
               FROM live_trades WHERE symbol=? AND trade_date=? ORDER BY exit_time DESC""",
            conn_lt, params=(symbol, get_ist_today().strftime("%Y-%m-%d")),
        )
        conn_lt.close()

        if not open_df.empty:
            st.markdown("##### 📂 सद्य उघडे (OPEN) ट्रेड्स")
            st.dataframe(open_df, width='stretch')
        if not closed_df.empty:
            st.markdown("##### 📁 आजचे बंद झालेले ट्रेड्स")
            st.dataframe(closed_df, width='stretch')

        # =========================================================
        # 10. Full Market Analysis Report — download button
        # (kept as an audit trail for every decision, since the system trades live and unattended)
        # =========================================================
        st.markdown("---")
    with tab4:
        # 🎓 Health Check — unattended auto-trader scripts (credit_spread_auto_trader.py,
        # oi_signal_auto_trader.py) कधी शेवटचं यशस्वीरित्या चालल्या ते इथेच दिसेल — cron server
        # बंद पडली, किंवा script अडकली, तर लगेच कळावं म्हणून.
        st.subheader("🩺 Auto-Trader Scripts — Health Check")
        try:
            from notifications import check_heartbeat_stale, HEARTBEAT_DIR
            import os as _os
            hb_col1, hb_col2, hb_col3, hb_col4, hb_col5 = st.columns(5)
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — eod_market_report दिवसातून फक्त एकदाच
            # (दुपारी ४ वाजता) चालतो, त्यामुळे इतर (दर १० मिनिटांनी चालणाऱ्या) scripts सारखी ३०-मिनिट
            # मर्यादा इथे उगाचच सतत "स्टेल/लाल" दाखवत राहील — या एका script साठी वेगळी, जास्त वेळेची
            # मर्यादा (२५ तास — दुसऱ्या दिवशी ४ वाजेपर्यंत थोडी सूट).
            for col, script_name, label, max_age_min in [
                (hb_col1, "credit_spread_auto_trader", "Credit Spread Auto-Trader", 30),
                (hb_col2, "oi_signal_auto_trader", "OI Signal Auto-Trader", 30),
                (hb_col3, "oi_snapshot_collector", "OI Snapshot Collector", 30),
                (hb_col4, "oi_greeks_vix_strategy", "OI+Greeks+VIX Strategy", 30),
                (hb_col5, "eod_market_report", "EOD Market Report (4pm)", 25 * 60),
            ]:
                with col:
                    hb_path = _os.path.join(HEARTBEAT_DIR, f"{script_name}.txt")
                    if not _os.path.exists(hb_path):
                        st.info(f"⚪ {label}: कधीच चालली नाही (किंवा या मशीनवर चालत नाही)")
                    else:
                        with open(hb_path) as f:
                            last_run = f.read().strip()
                        is_stale = check_heartbeat_stale(script_name, max_age_minutes=max_age_min)
                        limit_label = f"{max_age_min} मिनिटांपेक्षा" if max_age_min < 60 else f"{max_age_min // 60} तासांपेक्षा"
                        if is_stale:
                            st.error(f"🔴 {label}: शेवटचं {last_run} — {limit_label} जुनं, तपासा!")
                        else:
                            st.success(f"🟢 {label}: शेवटचं {last_run}")
        except Exception:
            st.caption("Health check उपलब्ध नाही (notifications.py सापडलं नाही).")
        st.markdown("---")

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — दुपारी ४ वाजता स्वयंचलितपणे तयार होणारे EOD
        # Market Reports (eod_market_report.py) इथे साठवलेले (data/reports/) दाखवणे व डाउनलोड करता येणे.
        st.subheader("📅 EOD Market Reports (दुपारी ४ ची स्वयंचलित तयारी)")
        eod_reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reports")
        if os.path.exists(eod_reports_dir):
            eod_files = sorted(
                [f for f in os.listdir(eod_reports_dir) if f.startswith("eod_report_") and f.endswith(".pdf")],
                reverse=True,
            )
            if eod_files:
                for fname in eod_files[:10]:  # शेवटचे १० पर्यंत, फार गर्दी नको
                    fpath = os.path.join(eod_reports_dir, fname)
                    with open(fpath, "rb") as f:
                        st.download_button(
                            label=f"📥 {fname}", data=f.read(), file_name=fname, mime="application/pdf",
                            key=f"eod_dl_{fname}",
                        )
            else:
                st.caption("अजून कुठलाही EOD Report तयार झालेला नाही (eod_market_report.py चालवली नसेल).")
        else:
            st.caption("अजून कुठलाही EOD Report तयार झालेला नाही (eod_market_report.py चालवली नसेल).")
        st.markdown("---")

        st.subheader("📄 Full Market Analysis Report (PDF)")
        st.caption(
            "OI data, multi-timeframe (1 Day / 1H / style timeframe) market structure, charts, technical analysis, "
            "VIX/strategy/risk sizing, and the live trades log — all in one PDF. "
            "(Requires 'kaleido==0.2.1' in requirements.txt for charts to render.)"
        )

        if st.button("📊 Generate PDF Report"):
            with st.spinner("Building PDF report — fetching daily chart & news..."):
                df_day_report = fetch_candles(token_input, symbol, underlying_price, interval="day")
                structure_day = classify_market_structure(df_day_report, order=3)
                structure_1h_report = classify_market_structure(df_1h, order=3)
                structure_style_tf_report = structure_info  # already computed above in the A1 Engine, for the current style's timeframe
                news_data = fetch_market_news()

                # Safe fallback if Direction Engine's Supertrend/RSI aren't available yet
                report_st_label = st_label if "st_label" in locals() else "N/A"
                report_st_val = last_st_val if "last_st_val" in locals() else 0.0
                report_rsi = last_rsi if "last_rsi" in locals() else 0.0

                if strategy_result and lots >= 1 and 'circuit_breaker_ok' in locals() and circuit_breaker_ok:
                    mode_label = "PAPER (Simulated)" if trading_mode == "PAPER" else "LIVE"
                    final_signal_text = f"FINAL A1 SIGNAL: {mode_label} - {strategy_result['strategy'].replace('_',' ')}, {lots} lot(s)"
                elif strategy_result and lots < 1:
                    final_signal_text = "NO TRADE - insufficient margin for even 1 lot (position size < 1 lot)"
                elif (all_gates_passed or sideways_qualified) and strategy_result is None:
                    final_signal_text = f"NO TRADE - no strategy found meeting the PoP >= {pop_threshold_pct}% condition"
                else:
                    final_signal_text = "NO TRADE - neither directional gates nor sideways conditions were met"

                pdf_bytes = generate_market_analysis_report_pdf(
                    symbol, underlying_price, atm_strike,
                    df_day_report, df_1h, df_structure_tf, structure_tf_label,
                    structure_day, structure_1h_report, structure_style_tf_report,
                    pipeline_direction, sideways_info, report_st_label, report_st_val, report_rsi,
                    broke, broken_level, pulled_back, retested, rsi_check, confirmed_5m, zone,
                    india_vix, vix_ok, vix_max_threshold,
                    strategy_result, lots, lot_size, risk_amount, available_margin, risk_pct_per_trade, pop_threshold_pct,
                    final_signal_text,
                    df, hist_df, open_df, closed_df,
                    news_data,
                )

            report_filename = f"A1_Market_Report_{symbol}_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.pdf"
            st.download_button(
                label="📥 Download Full Market Analysis Report (.pdf)",
                data=pdf_bytes,
                file_name=report_filename,
                mime="application/pdf",
            )
            st.success("✅ रिपोर्ट तयार झाला — वरील बटणावर क्लिक करून डाऊनलोड करा.")

        # =========================================================
        # ९. नवीन — Multi-Strategy Orchestrator (OI/PCR, ICT-FVG, BB Squeeze, VWAP)
        # हा A1 Engine पासून पूर्णपणे स्वतंत्र, समांतर pipeline आहे — वेगळ्या chat मध्ये बांधलेला, आता
        # खऱ्या Upstox डेटावर इथे जोडलेला. इथला कुठलाही निकाल वरच्या A1 Engine च्या ट्रेड-निर्णयावर परिणाम
        # करत नाही (फक्त माहितीसाठी — auto-execute होत नाही, फक्त सिग्नल्स दाखवतो).
        # =========================================================
        st.markdown("---")
    with tab5:
        st.subheader("🧩 Multi-Strategy Orchestrator")
        st.caption("OI/PCR · ICT-FVG · BB Squeeze · VWAP · SR Bounce · MTF Gap Fill — ६ रणनीती एकत्र")
        show_orchestrator = st.checkbox("दाखवा (प्रत्येक वेळी सर्व ६ strategies चालवल्या जातील)", value=False)
        if show_orchestrator:
            try:
                from loader import build_orchestrator
                from market_data_adapter import prepare_futures_ohlcv, prepare_options_chain, prepare_structure_data, compute_trend_direction_1h, apply_manual_sl_target
                from strategies.base import MarketSnapshot
                import os as _os

                config_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "config.yaml")
                orch = build_orchestrator(config_path)

                # 🎓 वापरकर्त्याने "गर्दी" म्हणून निदर्शनास आणलेला मुद्दा — आधी १२ input boxes
                # (६ strategies × SL+Target) नेहमीच उघडे दिसायचे, स्क्रीन भरून टाकायचे. आता डीफॉल्ट-
                # बंद expander मध्ये — गरज असेल तेव्हाच उघडा, नाहीतर स्वच्छ, व्यावसायिक दिसणारं पान.
                default_sl_target = {
                    "oi_pcr": (40, 80), "ict_fvg": (30, 60), "bb_squeeze": (40, 80),
                    "vwap": (25, 40), "sr_bounce": (40, 80), "mtf_gap_fill": (55, 155),
                }
                strat_display_names = {
                    "oi_pcr": "OI/PCR", "ict_fvg": "ICT-FVG", "bb_squeeze": "BB Squeeze",
                    "vwap": "VWAP", "sr_bounce": "SR Bounce", "mtf_gap_fill": "MTF Gap Fill",
                }
                ms_sl_target = {}
                with st.expander("⚙️ Advanced — SL/Target स्वतः ठरवा (पॉइंट्स)", expanded=False):
                    for strat_id, (default_sl, default_target) in default_sl_target.items():
                        strat_label = strat_display_names[strat_id]
                        mscol1, mscol2 = st.columns(2)
                        with mscol1:
                            sl_pts = st.number_input(f"{strat_label} — SL", min_value=1, value=default_sl, step=1, key=f"live_ms_sl_{strat_id}")
                        with mscol2:
                            target_pts = st.number_input(f"{strat_label} — Target", min_value=1, value=default_target, step=1, key=f"live_ms_target_{strat_id}")
                        ms_sl_target[strat_id] = (sl_pts, target_pts)

                df_for_orch = fetch_candles(token_input, symbol, underlying_price, interval="15minute")
                df_1h_for_orch = fetch_candles(token_input, symbol, underlying_price, interval="30minute")
                futures_ohlcv = prepare_futures_ohlcv(df_for_orch)
                options_chain_df = prepare_options_chain(raw_chain, symbol, atm_strike)
                structure_data = prepare_structure_data(df_for_orch)
                df_1h_resampled = resample_to_1h(df_1h_for_orch) if not df_1h_for_orch.empty else df_1h_for_orch
                trend_direction_1h = compute_trend_direction_1h(df_1h_resampled)

                from signals import find_support_resistance_levels
                sr_levels_1h = None
                if df_1h_resampled is not None and not df_1h_resampled.empty and len(df_1h_resampled) >= 10:
                    sr_levels_1h = find_support_resistance_levels(df_1h_resampled, top_n=3)
                mtf_1h_ohlcv = None
                if df_1h_resampled is not None and not df_1h_resampled.empty:
                    mtf_1h_ohlcv = df_1h_resampled.rename(columns={
                        "timestamp": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close",
                    })

                snapshot = MarketSnapshot(
                    timestamp=get_ist_now(), futures_ohlcv=futures_ohlcv,
                    options_chain=options_chain_df, structure_data=structure_data,
                    extra={"trend_direction_1h": trend_direction_1h, "sr_levels_1h": sr_levels_1h, "mtf_1h_ohlcv": mtf_1h_ohlcv},
                )

                raw_results = []
                for strat in orch.strategies:
                    r = strat.check_gates(snapshot)
                    sl_pts, target_pts = ms_sl_target.get(r.strategy_id, default_sl_target.get(r.strategy_id, (40, 80)))
                    r = apply_manual_sl_target(r, sl_pts, target_pts, reference_price=underlying_price)
                    raw_results.append(r)

                approved = orch.run_cycle(snapshot)
                for s in approved:
                    sl_pts, target_pts = ms_sl_target.get(s.strategy_id, default_sl_target.get(s.strategy_id, (40, 80)))
                    apply_manual_sl_target(s, sl_pts, target_pts, reference_price=underlying_price)

                # 🎓 सर्वात महत्त्वाचं (मंजूर सिग्नल्स) आधी दाखवणे — आधी हे तक्त्याच्या तळाशी लपलेलं होतं
                st.markdown("##### ✅ अंतिम मंजूर सिग्नल्स")
                if approved:
                    approved_cols = st.columns(min(len(approved), 3))
                    for i, s in enumerate(approved):
                        with approved_cols[i % 3]:
                            badge_color = "#089981" if s.direction.value == "LONG" else "#F23645" if s.direction.value == "SHORT" else "#787b86"
                            st.markdown(
                                f"""<div style="border:1px solid {badge_color};border-radius:8px;padding:10px 12px;margin-bottom:8px;">
                                <div style="font-weight:700;color:{badge_color};">● {s.strategy_id} — {s.direction.value}</div>
                                <div style="font-size:13px;color:#9598a1;margin-top:4px;">Entry: {s.entry_price} · SL: {s.stop_loss} · Target: {s.target}</div>
                                <div style="font-size:12px;color:#787b86;margin-top:4px;">{s.reason}</div>
                                </div>""",
                                unsafe_allow_html=True,
                            )
                else:
                    st.info("या cycle मध्ये कोणताही सिग्नल मंजूर झाला नाही.")

                # 🎓 प्रत्येक strategy चा तपशील — आधी नेहमी उघडा dataframe होता, आता collapsed
                with st.expander(f"🔍 सर्व ६ Strategies चा स्वतंत्र निकाल (Orchestrator गेट्सआधी)", expanded=False):
                    color_map = {"LONG": "🟢", "SHORT": "🔴", "NONE": "⚪"}
                    for r in raw_results:
                        dot = color_map.get(r.direction.value, "⚪")
                        st.markdown(f"{dot} **{strat_display_names.get(r.strategy_id, r.strategy_id)}** — {r.direction.value} "
                                    f"(Confidence: {round(r.confidence, 2)}) — {r.reason}")
                    st.caption(f"1H Supertrend Direction: {trend_direction_1h or 'उपलब्ध नाही'} | "
                               f"Structure: swept_high={structure_data['swept_high']}, swept_low={structure_data['swept_low']}, "
                               f"bos_direction={structure_data['bos_direction']}")

                st.caption("⚠️ हे फक्त माहितीसाठी आहे — इथून auto-execute होत नाही, वरच्या A1 Engine पासून पूर्णपणे स्वतंत्र.")
            except ModuleNotFoundError as e:
                st.error(
                    f"Multi-Strategy Orchestrator मध्ये चूक: {type(e).__name__}: {e}\n\n"
                    "**बहुतेक कारण**: `strategies/` फोल्डर (सर्व ८ फाईल्स — `__init__.py`, `base.py`, `oi_pcr.py`, "
                    "`ict_fvg.py`, `bb_squeeze.py`, `vwap.py`, `sr_bounce.py`, `mtf_gap_fill.py`) किंवा "
                    "`orchestrator.py`/`loader.py`/`config.yaml` तुमच्या GitHub repo मध्ये गहाळ आहेत. "
                    "Repo मध्ये जाऊन हे सर्व आहेत का तपासा."
                )
            except Exception as e:
                st.error(f"Multi-Strategy Orchestrator मध्ये चूक: {type(e).__name__}: {e}")

    with tab6:
        st.markdown("---")
        st.subheader(f"🌉 {symbol} — MTF Pullback + Gap Fill (नवीन, प्रयोगिक)")
        st.caption(
            "दोन स्वतंत्र रणनीती: (१) Fibonacci Pullback — 1H swing → 38.2-61.8% झोन → 15M Reversal + RSI. "
            "(२) Gap Fill — फक्त खरा overnight gap, पूर्णपणे भरला गेला की कुठलीही पुष्टी न घेता Entry."
        )
        show_mtf = st.checkbox("दाखवा (1H + 15M डेटा नव्याने मागवला जाईल)", value=False, key="mtf_show")
        if show_mtf:
            try:
                import mtf_pullback_strategy as mtf

                mtf_strategy_choice = st.radio("रणनीती निवडा", ["gap_fill", "fib_pullback"], horizontal=True, key="mtf_strategy")
                col1, col2, col3 = st.columns(3)
                with col1:
                    mtf_sl_pct = st.number_input("SL %", value=0.25, step=0.05, key="mtf_sl")
                    mtf_target_pct = st.number_input("Target %", value=0.70, step=0.05, key="mtf_target")
                with col2:
                    mtf_min_swing_pct = st.number_input("किमान Swing %", value=1.0, step=0.1, key="mtf_swing")
                    mtf_min_gap_pct = st.number_input("किमान Gap %", value=0.30, step=0.05, key="mtf_gap")
                with col3:
                    mtf_fib_low = st.number_input("Fib Low", value=0.50, step=0.01, key="mtf_fib_lo")
                    mtf_fib_high = st.number_input("Fib High", value=0.80, step=0.01, key="mtf_fib_hi")

                # 🎓 established fetch pattern (आधीच्या lookback_days दुरुस्तीशी सुसंगत) -- 1H साठी
                # पुरेसा इतिहास (swings ओळखण्यासाठी), 15M साठी अलीकडचा (entry/gap-fill शोधण्यासाठी).
                df_1h_mtf = fetch_candles(token_input, symbol, underlying_price, interval="1hour")
                df_15m_mtf = fetch_candles(token_input, symbol, underlying_price, interval="15minute")

                if df_1h_mtf is None or df_1h_mtf.empty or df_15m_mtf is None or df_15m_mtf.empty:
                    st.warning("1H/15M डेटा मिळाला नाही.")
                else:
                    h1_mtf = df_1h_mtf.rename(columns={"timestamp": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close"}).reset_index(drop=True)
                    m15_mtf = df_15m_mtf.rename(columns={"timestamp": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close"}).reset_index(drop=True)
                    ps_mtf = mtf.pivots(h1_mtf, min_swing_pct=mtf_min_swing_pct)
                    st.caption(f"1H candles: {len(h1_mtf)} | 15M candles: {len(m15_mtf)} | Swings सापडले: {len(ps_mtf)}")

                    if mtf_strategy_choice == "gap_fill":
                        st.markdown("##### 🎯 सध्या अजून न भरलेले Gaps (Live Monitoring)")
                        open_gaps = mtf.find_open_gaps_now(h1_mtf, m15_mtf, ps_mtf, min_gap_pct=mtf_min_gap_pct)
                        if open_gaps.empty:
                            st.info("सध्या कुठलेही उघडे (unfilled) gaps नाहीत.")
                        else:
                            st.dataframe(open_gaps, width="stretch")
                            st.caption("किंमत 'FillTriggerPrice' पर्यंत पोहोचली की, गोल्ड लगेच Entry घेतली जाईल.")
                        sig_mtf = mtf.make_gap_fill_signals(h1_mtf, m15_mtf, ps_mtf, mtf_sl_pct, mtf_target_pct, min_gap_pct=mtf_min_gap_pct)
                    else:
                        sig_mtf = mtf.make_signals(h1_mtf, m15_mtf, ps_mtf, mtf_fib_low, mtf_fib_high, mtf_sl_pct, mtf_target_pct)

                    sig_mtf = mtf.evaluate(m15_mtf, sig_mtf)
                    st.markdown("##### 📜 अलीकडचे Signals")
                    if sig_mtf.empty:
                        st.info("या कालखंडात कुठलेही signals सापडले नाहीत.")
                    else:
                        display_cols = ["SignalDate", "Signal", "ReversalPattern", "Entry", "StopLoss", "Target", "Outcome"]
                        st.dataframe(sig_mtf[display_cols].tail(15).sort_values("SignalDate", ascending=False), width="stretch")
                        closed = sig_mtf[(sig_mtf.Outcome == "SL") | (sig_mtf.Outcome.str.startswith("TARGET_"))]
                        if not closed.empty:
                            wins = closed.Outcome.str.startswith("TARGET_").sum()
                            wr = 100 * wins / len(closed)
                            st.caption(f"एकूण Closed: {len(closed)} | Win Rate: {wr:.1f}% | Net R: {closed.R_Result.sum():.2f}")
                st.caption("⚠️ हे फक्त माहितीसाठी आहे — इथून auto-execute होत नाही, इतर रणनीतींपासून पूर्णपणे स्वतंत्र.")
            except Exception as e:
                st.error(f"MTF Pullback + Gap Fill मध्ये चूक: {type(e).__name__}: {e}")

    with tab7:
        st.markdown("---")
        st.subheader(f"🗺️ {symbol} — Market Zones (S/R + Order Block + Demand/Supply + Unfilled Gap)")
        st.caption(
            "शेवटच्या १ वर्षाच्या डेटावरून पूर्वगणना करून Supabase मध्ये साठवलेलं संपूर्ण विश्लेषण — "
            "GitHub Actions (साप्ताहिक) द्वारे अद्ययावत होतं. इथून प्रत्येक वेळी पुन्हा गणना होत नाही, फक्त वाचलं जातं."
        )
        try:
            import cloud_db
            if not cloud_db.is_cloud_db_configured():
                st.warning("Cloud DB (Supabase) configured नाही — Market Zones फक्त तिथूनच वाचता येतात. कृपया SUPABASE_DB_URL सेट करा.")
            else:
                zones_status_filter = st.radio("दाखवा", ["फक्त ACTIVE (अजून अबाधित)", "सर्व (ACTIVE + FILLED)"], horizontal=True, key="zones_status")
                status_arg = "ACTIVE" if zones_status_filter.startswith("फक्त") else None
                zones_df = cloud_db.get_market_zones(symbol, status=status_arg)

                if zones_df is None:
                    st.error("Supabase मधून वाचता आलं नाही — जोडणी तपासा.")
                elif zones_df.empty:
                    st.info(
                        f"{symbol} साठी अजून कुठलेही zones साठवलेले नाहीत — "
                        "GitHub Actions मधून 'Market Zones Refresh' workflow एकदा हातानेच चालवा (Actions टॅब → Run workflow)."
                    )
                else:
                    st.caption(f"एकूण {len(zones_df)} zones")
                    zone_type_order = ["SUPPORT", "RESISTANCE", "DYNAMIC_SR_SUPPORT", "DYNAMIC_SR_RESISTANCE",
                                       "BULLISH_OB", "BEARISH_OB", "DEMAND_ZONE", "SUPPLY_ZONE", "UP_GAP", "DOWN_GAP"]
                    zone_labels = {
                        "SUPPORT": "🟢 Support (established, 1H)", "RESISTANCE": "🔴 Resistance (established, 1H)",
                        "DYNAMIC_SR_SUPPORT": "🟢🎯 Dynamic S/R Support (Chart-सारखाच)",
                        "DYNAMIC_SR_RESISTANCE": "🔴🎯 Dynamic S/R Resistance (Chart-सारखाच)",
                        "BULLISH_OB": "🟩 Bullish Order Block", "BEARISH_OB": "🟥 Bearish Order Block",
                        "DEMAND_ZONE": "🔵 Demand Zone", "SUPPLY_ZONE": "🟠 Supply Zone",
                        "UP_GAP": "⬆️ Unfilled Up-Gap", "DOWN_GAP": "⬇️ Unfilled Down-Gap",
                    }

                    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — LTP ने Dynamic S/R ला स्पर्श केला की
                    # dynamic_sr_instant_trader.py तो zone आपोआप FILLED करतो — तीच "notification" इथे
                    # ठळकपणे दाखवणे (वरच्या फिल्टर-निवडीशी स्वतंत्रपणे, नेहमी संपूर्ण डेटा वाचून).
                    all_zones_for_notif = cloud_db.get_market_zones(symbol, status=None)
                    if all_zones_for_notif is not None and not all_zones_for_notif.empty:
                        dyn_filled = all_zones_for_notif[
                            all_zones_for_notif["zone_type"].isin(["DYNAMIC_SR_SUPPORT", "DYNAMIC_SR_RESISTANCE"])
                            & (all_zones_for_notif["status"] == "FILLED")
                        ]
                        if not dyn_filled.empty:
                            st.markdown("##### 🎯 अलीकडे Hit झालेले Dynamic S/R Levels (Notification)")
                            st.dataframe(
                                dyn_filled[["zone_type", "zone_low", "strength", "formed_date"]].sort_values("formed_date", ascending=False),
                                width="stretch",
                            )
                            st.caption("हेच levels `dynamic_sr_instant_trader.py` ने PAPER trade घेण्यासाठी वापरले (Positions page वर Source='dynamic_sr_instant' पहा).")
                            st.markdown("---")

                    for zt in zone_type_order:
                        subset = zones_df[zones_df["zone_type"] == zt]
                        if subset.empty:
                            continue
                        with st.expander(f"{zone_labels.get(zt, zt)} ({len(subset)})", expanded=(status_arg == "ACTIVE")):
                            display_cols = ["zone_low", "zone_high", "strength", "formed_date", "status"]
                            st.dataframe(subset[display_cols].sort_values("formed_date", ascending=False), width="stretch")
        except Exception as e:
            st.error(f"Market Zones मध्ये चूक: {type(e).__name__}: {e}")

    with tab8:
        st.markdown("---")
        st.subheader(f"🎯 {symbol} — Strategy Builder (Multi-Leg Payoff + Combined Greeks)")
        st.caption("Sensibull-सारखं — एकाहून अधिक legs जोडून, एकत्रित P&L payoff diagram आणि Greeks बघा.")
        try:
            import strategy_payoff as sp

            st.session_state.setdefault("strategy_builder_legs", [])

            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull-सारखं Ready-Made Templates,
            # एका क्लिकवर संपूर्ण रणनीती (योग्य strikes + live premium + instrument_key सह) लोड होते.
            st.markdown("##### 🚀 Ready-Made Strategy (एका क्लिकवर लोड करा)")
            rm_category = st.radio("प्रकार", list(sp.READY_MADE_CATEGORIES.keys()), horizontal=True, key="rm_category")
            rm_cols = st.columns(len(sp.READY_MADE_CATEGORIES[rm_category]))
            for rm_i, rm_name in enumerate(sp.READY_MADE_CATEGORIES[rm_category]):
                with rm_cols[rm_i]:
                    if st.button(rm_name, key=f"rm_{rm_name}", width="stretch"):
                        template_legs = sp.build_ready_made_strategy(rm_name, atm_strike, hedge_width=hedge_width_points)
                        new_legs = []
                        for tleg in template_legs:
                            matched = next((r for r in raw_chain if r["strike_price"] == tleg["strike"]), None)
                            premium, instr_key = 0.0, None
                            if matched:
                                opt_data = matched.get("call_options" if tleg["option_type"] == "CE" else "put_options", {})
                                premium = float(opt_data.get("market_data", {}).get("ltp") or 0.0)
                                instr_key = opt_data.get("instrument_key")
                            new_legs.append({**tleg, "premium": premium, "lot_size": int(lot_size), "instrument_key": instr_key})
                        st.session_state["strategy_builder_legs"] = new_legs
                        st.rerun()
            st.markdown("---")

            available_strikes = sorted({row["strike_price"] for row in raw_chain}) if raw_chain else []
            if not available_strikes:
                st.warning("Option chain डेटा उपलब्ध नाही.")
            else:
                st.markdown("##### ➕ नवीन Leg जोडा")
                lc1, lc2, lc3, lc4 = st.columns(4)
                with lc1:
                    leg_direction = st.selectbox("दिशा", ["BUY", "SELL"], key="sb_direction")
                with lc2:
                    leg_option_type = st.selectbox("प्रकार", ["CE", "PE"], key="sb_option_type")
                default_strike_idx = min(range(len(available_strikes)), key=lambda i: abs(available_strikes[i] - atm_strike)) if available_strikes else 0
                with lc3:
                    leg_strike = st.selectbox("Strike", available_strikes, index=default_strike_idx, key="sb_strike")
                with lc4:
                    leg_lots = st.number_input("Lots", min_value=1, value=1, step=1, key="sb_lots")

                # 🎓 Strike निवडल्यावर, त्याच strike/type ची सद्य LTP आपोआप premium म्हणून भरणे
                auto_premium = 0.0
                matched_row = next((r for r in raw_chain if r["strike_price"] == leg_strike), None)
                if matched_row:
                    opt_data = matched_row.get("call_options" if leg_option_type == "CE" else "put_options", {})
                    auto_premium = float(opt_data.get("market_data", {}).get("ltp") or 0.0)
                leg_premium = st.number_input("Premium (आपोआप भरलेला, हवं तर बदला)", min_value=0.0, value=auto_premium, step=0.05, key="sb_premium")

                if st.button("➕ Leg जोडा"):
                    instrument_key = None
                    if matched_row:
                        opt_data = matched_row.get("call_options" if leg_option_type == "CE" else "put_options", {})
                        instrument_key = opt_data.get("instrument_key")
                    st.session_state["strategy_builder_legs"].append({
                        "direction": leg_direction, "option_type": leg_option_type, "strike": float(leg_strike),
                        "premium": float(leg_premium), "lots": int(leg_lots), "lot_size": int(lot_size),
                        "instrument_key": instrument_key,
                    })
                    st.rerun()

            legs = st.session_state["strategy_builder_legs"]
            if not legs:
                st.info("अजून कुठलेही legs जोडलेले नाहीत — वरून जोडा.")
            else:
                st.markdown("##### 📜 सद्य Legs")
                for i, leg in enumerate(legs):
                    lcol1, lcol2 = st.columns([5, 1])
                    with lcol1:
                        st.write(f"{leg['direction']} {leg['option_type']} {leg['strike']:.0f} @ ₹{leg['premium']:.2f} × {leg['lots']} lot(s)")
                    with lcol2:
                        if st.button("🗑️", key=f"sb_remove_{i}"):
                            st.session_state["strategy_builder_legs"].pop(i)
                            st.rerun()

                if st.button("🧹 सर्व Legs काढा"):
                    st.session_state["strategy_builder_legs"] = []
                    st.rerun()

                # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "Strike Controls" सारखं
                # Shift control — सर्व legs चे strikes एकत्रितपणे वर/खाली हलवणे (नवीन premium/
                # instrument_key त्याच strike वर live chain मधून पुन्हा भरून).
                st.markdown("##### 🎛️ Strike Controls")
                shift_amount = st.number_input("Shift (सर्व strikes एकत्र हलवा, पॉइंट्समध्ये)", value=0, step=50, key="sb_shift")
                if shift_amount != 0 and st.button("↔️ Shift लागू करा"):
                    shifted_legs = []
                    for leg in legs:
                        new_strike = leg["strike"] + shift_amount
                        matched = next((r for r in raw_chain if r["strike_price"] == new_strike), None)
                        premium, instr_key = leg["premium"], leg.get("instrument_key")
                        if matched:
                            opt_data = matched.get("call_options" if leg["option_type"] == "CE" else "put_options", {})
                            premium = float(opt_data.get("market_data", {}).get("ltp") or 0.0)
                            instr_key = opt_data.get("instrument_key")
                        shifted_legs.append({**leg, "strike": new_strike, "premium": premium, "instrument_key": instr_key})
                    st.session_state["strategy_builder_legs"] = shifted_legs
                    st.rerun()

                # --- Payoff Diagram (OI Overlay सह) ---
                price_range = sp.build_default_price_range(underlying_price, num_points=100, range_pct=5.0)
                payoff_curve = sp.compute_strategy_payoff_curve(legs, price_range)
                max_profit, max_loss = sp.compute_max_profit_loss(payoff_curve)
                breakevens = sp.find_breakeven_points(price_range, payoff_curve)

                gcol1, gcol2, gcol3 = st.columns(3)
                gcol1.metric("कमाल नफा (या range मध्ये)", f"₹{max_profit:,.0f}")
                gcol2.metric("कमाल तोटा (या range मध्ये)", f"₹{max_loss:,.0f}")
                gcol3.metric("Breakeven", ", ".join(f"{b:,.0f}" for b in breakevens) if breakevens else "—")

                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                fig = make_subplots(specs=[[{"secondary_y": True}]])

                # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या payoff chart मागे दिसणारे
                # OI bars (प्रत्येक strike ला किती Call/Put OI आहे) -- कुठल्या strikes ला जास्त
                # "रोध"/"आधार" आहे हे दृश्य स्वरूपात कळण्यासाठी.
                oi_strikes = [r["strike_price"] for r in raw_chain if price_range[0] <= r["strike_price"] <= price_range[-1]]
                if oi_strikes:
                    # 🎓 established _extract_oi_ltp() च्याच defensive (.get()) पॅटर्नने -- direct
                    # indexing (r["call_options"]["market_data"]) टाळून, गहाळ keys मुळे crash होऊ नये.
                    from oi_analysis import _extract_oi_ltp
                    ce_oi_vals = [next((_extract_oi_ltp(r, "call_options")[0] for r in raw_chain if r["strike_price"] == s), 0) for s in oi_strikes]
                    pe_oi_vals = [next((_extract_oi_ltp(r, "put_options")[0] for r in raw_chain if r["strike_price"] == s), 0) for s in oi_strikes]
                    fig.add_trace(go.Bar(x=oi_strikes, y=ce_oi_vals, name="Call OI", marker_color="#F23645", opacity=0.3), secondary_y=True)
                    fig.add_trace(go.Bar(x=oi_strikes, y=pe_oi_vals, name="Put OI", marker_color="#089981", opacity=0.3), secondary_y=True)

                fig.add_trace(go.Scatter(x=price_range, y=payoff_curve, mode="lines", name="P&L", line=dict(color="#2962ff", width=2), fill="tozeroy"), secondary_y=False)
                fig.add_hline(y=0, line_dash="dash", line_color="#787b86")
                fig.add_vline(x=underlying_price, line_dash="dot", line_color="#f0b90b", annotation_text="सद्य किंमत")
                fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=30, b=10), barmode="group")
                fig.update_yaxes(title_text="P&L (₹)", secondary_y=False)
                fig.update_yaxes(title_text="Open Interest", secondary_y=True)
                st.plotly_chart(fig, use_container_width=True)

                # --- Combined Greeks (established fetch_option_greeks पुनर्वापर) ---
                instrument_keys = [leg["instrument_key"] for leg in legs if leg.get("instrument_key")]
                if instrument_keys and token_input.strip():
                    greeks_map = fetch_option_greeks(token_input, instrument_keys)
                    legs_with_greeks = []
                    for leg in legs:
                        g = greeks_map.get(leg.get("instrument_key"), {})
                        legs_with_greeks.append({**leg, **g})
                    combined_greeks = sp.compute_combined_greeks(legs_with_greeks)
                    st.markdown("##### 🧮 Combined Greeks (संपूर्ण Strategy)")
                    ecol1, ecol2, ecol3, ecol4 = st.columns(4)
                    ecol1.metric("Delta", f"{combined_greeks['delta']:.2f}")
                    ecol2.metric("Gamma", f"{combined_greeks['gamma']:.4f}")
                    ecol3.metric("Theta", f"{combined_greeks['theta']:.2f}")
                    ecol4.metric("Vega", f"{combined_greeks['vega']:.2f}")
                else:
                    st.caption("Greeks दाखवण्यासाठी वैध Token हवा.")
        except Exception as e:
            st.error(f"Strategy Builder मध्ये चूक: {type(e).__name__}: {e}")
