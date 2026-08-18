"""Dashboard page — Chart, Direction Engine, Option Chain/OI, Advanced OI Analysis, Manual Trading, A1 Signal Engine, PDF Report."""
import datetime
import re
import time
import uuid
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from config import TIMEFRAME_CONFIG, DB_PATH, get_ist_now, get_ist_today
from tradingview_chart import build_lightweight_chart_html
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
    detect_trendline, check_trend_signal, add_price_action_overlays, describe_price_action,
    classify_market_structure, detect_break,
    classify_sideways, detect_pullback_retest,
    rsi_momentum_and_divergence, confirm_5m, supply_demand_zone, check_pattern_rsi_gate,
    check_price_action_strategy, check_indicator_strategy,
)
from strategy import _pop_lookup, select_iron_condor, select_iron_butterfly, select_credit_spread, compute_position_size
from oi_analysis import (
    get_latest_oi_signal, check_oi_diff_entry_gate,
    get_previous_day_total_oi, compute_oi_price_matrix, compute_pcr_signal, compute_max_pain,
    compute_rollover_proxy, swing_oi_gate, find_psychological_level, check_oi_wall_confirmation,
    compute_oi_signal_with_hysteresis,
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

    st.markdown("---")
    st.subheader(f"📊 {symbol} TradingView Style Chart ({timeframe_option})")

    # --- ट्रेडिंगव्यू प्रो-चार्ट (Price + MA, Volume, RSI) ---

    # मूव्हिंग अॅव्हरेजेस (TradingView वर नेहमी दिसतात तशा)
    df_candles["ema20"] = df_candles["close"].ewm(span=20, adjust=False).mean()
    df_candles["ema50"] = df_candles["close"].ewm(span=50, adjust=False).mean()

    # व्हॉल्यूम बार्सचा रंग कँडल दिशेनुसार (rgba वापरलं, 8-digit hex plotly मध्ये चालत नाही)
    vol_colors = np.where(
        df_candles["close"] >= df_candles["open"],
        "rgba(8,153,129,0.5)",
        "rgba(242,54,69,0.5)",
    )

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.62, 0.16, 0.22],
        specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]],
    )

    # १. मुख्य प्राईस ट्रेस — Candlestick किंवा Line (युजरच्या निवडीनुसार)
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df_candles["timestamp"],
            open=df_candles["open"],
            high=df_candles["high"],
            low=df_candles["low"],
            close=df_candles["close"],
            name=symbol,
            increasing_line_color="#089981",
            decreasing_line_color="#F23645",
            increasing_fillcolor="#089981",
            decreasing_fillcolor="#F23645",
            line_width=1,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df_candles["timestamp"],
            y=df_candles["close"],
            mode="lines",
            name=symbol,
            line=dict(color="#2962FF", width=1.8),
            fill="tozeroy",
            fillcolor="rgba(41,98,255,0.08)",
        ), row=1, col=1)

    # EMA रेषा
    fig.add_trace(go.Scatter(
        x=df_candles["timestamp"], y=df_candles["ema20"],
        mode="lines", name="EMA 20",
        line=dict(color="#2962FF", width=1.3),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_candles["timestamp"], y=df_candles["ema50"],
        mode="lines", name="EMA 50",
        line=dict(color="#FF6D00", width=1.3),
    ), row=1, col=1)

    # शेवटच्या क्लोजची डॉटेड लाईन (TradingView प्राईस लाईन)
    if not df_candles.empty:
        last_close = df_candles["close"].iloc[-1]
        last_color = "#089981" if last_close >= df_candles["open"].iloc[-1] else "#F23645"
        fig.add_hline(
            y=last_close, line_dash="dot", line_color=last_color, line_width=1,
            row=1, col=1,
            annotation_text=f"{last_close:,.2f}",
            annotation_position="right",
            annotation_font_color="#131722",
            annotation_font_size=12,
            annotation_bgcolor=last_color,
        )

    # २. व्हॉल्यूम (Row 2)
    fig.add_trace(go.Bar(
        x=df_candles["timestamp"],
        y=df_candles["volume"],
        name="Volume",
        marker_color=vol_colors,
        marker_line_width=0,
    ), row=2, col=1)

    # ३. RSI इंडिकेटर (Row 3)
    fig.add_trace(go.Scatter(
        x=df_candles["timestamp"],
        y=df_candles["rsi"],
        mode="lines",
        name="RSI (14)",
        line=dict(color="#7e57c2", width=1.6),
    ), row=3, col=1)

    # RSI ओव्हरबॉट/ओव्हरसोल्ड झोन शेडिंग + रेषा
    fig.add_hrect(y0=70, y1=100, line_width=0, fillcolor="#F23645", opacity=0.06, row=3, col=1)
    fig.add_hrect(y0=0, y1=30, line_width=0, fillcolor="#089981", opacity=0.06, row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(242,54,69,0.5)", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(8,153,129,0.5)", line_width=1, row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#4b5563", line_width=1, row=3, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)

    # --- संपूर्ण TradingView-style लेआउट ---
    fig.update_layout(
        template="plotly_dark",
        height=800,
        xaxis_rangeslider_visible=False,
        paper_bgcolor="#131722",
        plot_bgcolor="#131722",
        font=dict(family="Trebuchet MS, Arial, sans-serif", color="#d1d4dc", size=12),
        margin=dict(l=10, r=60, t=70, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=11),
        ),
        dragmode="pan",
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1e222d", font_size=12, font_family="Trebuchet MS"),
        uirevision="keep_zoom",
        annotations=[dict(
            text=f"{symbol} · {timeframe_option}",
            xref="paper", yref="paper",
            x=0.01, y=0.985, showarrow=False,
            font=dict(size=26, color="#2a2e3d"),
            xanchor="left",
        )],
    )

    # --- TradingView स्टाईल OHLC रीडआउट (शेवटच्या कँडलचा O/H/L/C व % बदल, वर-डावीकडे) ---
    if not df_candles.empty:
        last_row = df_candles.iloc[-1]
        prev_close = (
            df_candles["close"].iloc[-2] if len(df_candles) > 1 else last_row["open"]
        )
        chg = last_row["close"] - prev_close
        chg_pct = (chg / prev_close * 100) if prev_close else 0.0
        ohlc_color = "#089981" if chg >= 0 else "#F23645"
        ohlc_text = (
            f"O <span style='color:#d1d4dc'>{last_row['open']:,.2f}</span>  "
            f"H <span style='color:#d1d4dc'>{last_row['high']:,.2f}</span>  "
            f"L <span style='color:#d1d4dc'>{last_row['low']:,.2f}</span>  "
            f"C <span style='color:{ohlc_color}'>{last_row['close']:,.2f}</span>  "
            f"<span style='color:{ohlc_color}'>{chg:+,.2f} ({chg_pct:+.2f}%)</span>"
        )
        fig.add_annotation(
            text=ohlc_text,
            xref="paper", yref="paper",
            x=0.01, y=0.965, showarrow=False,
            font=dict(size=13, color="#787b86", family="Trebuchet MS, Arial, sans-serif"),
            xanchor="left", yanchor="top",
            align="left",
        )

    # --- नॉन-ट्रेडिंग गॅप्स (वीकएंड + मार्केट बंद तास) अक्षातून काढणे ---
    # हेच स्क्रोल/झूम अडखळण्याचं मुख्य कारण असतं — गॅप्समुळे कँडल्स एका कोपऱ्यात दाटतात
    rangebreaks = [dict(bounds=["sat", "mon"])]  # शनिवार-रविवार वगळणे
    if timeframe_option != "day":
        # बाजार बंद तास वगळणे (संध्या. ३:३० नंतर ते सकाळी ९:१५ आधी)
        rangebreaks.append(dict(bounds=[15.5, 9.25], pattern="hour"))

    # क्रॉसहेअर + ग्रिड सर्व rows साठी
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#1e222d",
        zeroline=False,
        rangeslider=dict(visible=False),
        fixedrange=False,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#758696",
        spikethickness=1,
        spikedash="solid",
        rangebreaks=rangebreaks,
    )

    # --- TradingView स्टाईल क्विक-झूम बटणे (1D/5D/1M/... सर्वात वरच्या subplot वर) ---
    if timeframe_option == "day":
        selector_buttons = [
            dict(count=1, label="1M", step="month", stepmode="backward"),
            dict(count=3, label="3M", step="month", stepmode="backward"),
            dict(count=6, label="6M", step="month", stepmode="backward"),
            dict(count=1, label="YTD", step="year", stepmode="todate"),
            dict(count=1, label="1Y", step="year", stepmode="backward"),
            dict(step="all", label="All"),
        ]
    else:
        selector_buttons = [
            dict(count=1, label="1D", step="day", stepmode="backward"),
            dict(count=5, label="5D", step="day", stepmode="backward"),
            dict(count=1, label="1M", step="month", stepmode="backward"),
            dict(count=3, label="3M", step="month", stepmode="backward"),
            dict(count=6, label="6M", step="month", stepmode="backward"),
            dict(step="all", label="All"),
        ]

    fig.update_xaxes(
        row=1, col=1,
        rangeselector=dict(
            buttons=selector_buttons,
            bgcolor="#1e222d",
            activecolor="#2962FF",
            bordercolor="#2a2e3d",
            borderwidth=1,
            font=dict(color="#d1d4dc", size=11),
            x=0.99, xanchor="right",
            y=1.09, yanchor="top",
        ),
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#1e222d",
        side="right",
        zeroline=False,
        fixedrange=False,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#758696",
        spikethickness=1,
        tickformat=",.2f",
    )
    # व्हॉल्यूम आणि RSI axes ना कमी दशांश स्थळे
    fig.update_yaxes(tickformat=",.0f", row=2, col=1)
    fig.update_yaxes(tickformat=",.0f", row=3, col=1)

    # --- डीफॉल्ट झूम: सुरुवातीला अलीकडचेच candles दिसावेत (नाहीतर ९० दिवसांचा डेटा दाटीवाटीने दिसतो) ---
    if not df_candles.empty:
        visible_candles = {"1minute": 600, "15minute": 500, "30minute": 480, "day": 365}.get(timeframe_option, 120)
        if len(df_candles) > visible_candles:
            start_view = df_candles["timestamp"].iloc[-visible_candles]
            end_view = df_candles["timestamp"].iloc[-1]
            fig.update_xaxes(range=[start_view, end_view])

    # X-axis फक्त सर्वात खालच्या subplot वर लेबल दाखवा
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(showticklabels=True, row=3, col=1)

    # --- Price Action Overlays: Support/Resistance + Trendlines + Swing High/Low ---
    # टाईमफ्रेम (sidebar मधून) बदलल्यास df_candles आपोआप बदलतो, त्यामुळे हे overlays दर वेळी
    # त्याच नव्या टाईमफ्रेमच्या डेटावरून पुन्हा काढले जातात — वेगळी बटणं/कॅशिंग लागत नाही.
    chart_sr_levels, chart_trendline_support, chart_trendline_resistance = add_price_action_overlays(
        fig, df_candles, row=1, col=1
    )

    config = {
        "scrollZoom": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    }
    st.plotly_chart(fig, width='stretch', config=config)

    with st.expander("📖 Chart Description (Price Action)", expanded=False):
        st.markdown(describe_price_action(chart_sr_levels, chart_trendline_support, chart_trendline_resistance))
        st.caption(
            "हिरवी टिंब-रेषा = Support, लाल टिंब-रेषा = Resistance (कंसात किती वेळा टेस्ट झाला ते). "
            "कलर्ड सलग रेषा = Trendline (हिरवी=अजून कायम, लाल=तुटलेली). ▲/▼ मार्कर्स = Swing Low/High."
        )

    # =========================================================
    # ७.६ नवीन — खरा TradingView Chart (Lightweight Charts library, ऐच्छिक — प्रयोगिक)
    # Plotly ऐवजी TradingView च्याच open-source library चा वापर — खरं candle-रेंडरिंग, आणि मूलभूत
    # Drawing Tools (Trendline + Horizontal Line — fibonacci सारखे advanced tools नाहीत).
    # ऐच्छिक ठेवलाय (डीफॉल्ट बंद) कारण हा नवीन component आहे — browser मध्ये प्रत्यक्ष तपासून बघा.
    # =========================================================
    show_tv_chart = st.checkbox(
        "🆕 खरा TradingView Chart वापरून बघा (Drawing Tools सकट — प्रयोगिक, वरच्या chart ऐवजी नाही, सोबत)",
        value=False,
    )
    if show_tv_chart:
        rsi_for_tv = calculate_rsi(df_candles, period=14) if not df_candles.empty else pd.Series(dtype=float)
        sr_for_tv = find_support_resistance_levels(df_candles) if not df_candles.empty else None
        tv_html = build_lightweight_chart_html(
            df_candles, symbol=symbol, timeframe_label=timeframe_option,
            ema20_series=df_candles.get("ema20"), ema50_series=df_candles.get("ema50"),
            rsi_series=rsi_for_tv, sr_levels=sr_for_tv, height=650,
        )
        st.components.v1.html(tv_html, height=700, scrolling=False)
        st.caption(
            "⚠️ Drawing Tools ने काढलेल्या रेषा फक्त browser मध्येच राहतात (client-side) — auto-refresh किंवा "
            "page reload झाल्यावर मिटतात, साठवल्या जात नाहीत. Fibonacci सारखे advanced tools यात नाहीत — "
            "फक्त Trendline आणि Horizontal Line."
        )

    # =========================================================
    # ७.५ DIRECTION ENGINE — Intraday/Swing style नुसार टाईमफ्रेम बदलणारे → BULLISH / BEARISH
    # (मुख्य चार्टच्या टाईमफ्रेम निवडीपासून स्वतंत्र; Signal लॉजिक तेच पण टाईमफ्रेम style-driven)
    # =========================================================
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

    st.caption(
        f"Style: **{trading_style}** — Structure/Break/Pullback/Retest: {structure_tf_label} · "
        f"RSI Momentum/Divergence: {rsi_tf_label} · अंतिम पुष्टीकरण: {confirm_tf_label}. "
        "पूर्ण पाईपलाईन खाली 'A1 Signal Engine' सेक्शनमध्ये दाखवली आहे."
    )

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
    st.markdown("---")
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
    st.markdown("---")
    st.subheader("🧭 Nifty OI Put-Call Diff Tracker (ATM ±6 strikes · दर 10 मिनिटांनी)")

    total_call_oi = int(df["CE Total OI"].sum()) if not df.empty else 0
    total_put_oi = int(df["PE Total OI"].sum()) if not df.empty else 0
    current_diff = total_put_oi - total_call_oi

    # IST वेळ — इतर ठिकाणी (line 79, 1280) वापरलेल्याच बरोबर पद्धतीने (datetime.now() सर्व्हरच्या local
    # वेळेवर अवलंबून असतं, जी IST नसू शकते — विशेषतः Streamlit Cloud सारख्या UTC सर्व्हरवर चुकीची वेळ दाखवत होती)
    now_dt = get_ist_now()
    # खालच्या १० मिनिटांच्या स्लॉटवर राऊंड करणे (उदा. 13:47 -> 13:40)
    snapshot_minute = (now_dt.minute // 10) * 10
    snapshot_time = now_dt.replace(minute=snapshot_minute, second=0, microsecond=0).strftime("%H:%M")

    conn3 = sqlite3.connect(DB_PATH)
    cur3 = conn3.cursor()

    # आधीचा (या क्षणापर्यंतचा सर्वात अलीकडचा) snapshot घेणे, ΔDiff आणि hysteresis साठी
    cur3.execute(
        """SELECT diff, delta_diff, signal FROM oi_diff_snapshots
           WHERE symbol=? AND trade_date=? AND snapshot_time < ?
           ORDER BY snapshot_time DESC LIMIT 1""",
        (symbol, today_str, snapshot_time)
    )
    prev_row = cur3.fetchone()
    prev_diff = prev_row[0] if prev_row else None
    prev_signal = prev_row[2] if prev_row else None
    delta_diff = (current_diff - prev_diff) if prev_diff is not None else 0

    # सिग्नल — पातळी (level) + गती (momentum) वरून, आणि Diff मध्ये किमान 10% बदल असेल तरच आधीच्या
    # सिग्नलपेक्षा वेगळा दाखवला जातो (hysteresis — delta_diff फक्त माहितीसाठी, त्यावर buffer नाही)
    oi_signal = compute_oi_signal_with_hysteresis(current_diff, delta_diff, prev_diff, prev_signal)

    # या १० मिनिटांच्या स्लॉटसाठी snapshot फक्त एकदाच रेकॉर्ड करणे (त्या स्लॉटमधला पहिला पोल टिकतो)
    cur3.execute(
        """INSERT OR IGNORE INTO oi_diff_snapshots
           (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal, underlying_price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (symbol, today_str, snapshot_time, total_call_oi, total_put_oi, current_diff, delta_diff, oi_signal, underlying_price)
    )
    conn3.commit()

    # आजच्या दिवसाचा संपूर्ण इतिहास दाखवणे (अलीकडचा वेळ सर्वात वर, स्क्रीनशॉटसारखे)
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

    styled_hist = hist_df.style.map(style_oi_numeric, subset=["Diff", "Δ Diff"]) \
                                .map(style_oi_signal, subset=["Signal"]) \
                                .set_properties(**{'font-size': '15px', 'font-weight': 'bold'})

    st.dataframe(styled_hist, width='stretch', height=450)

    st.caption(
        "**लॉजिक सोपं करून:** Diff = एकूण Put OI − एकूण Call OI. Diff धन (positive) असेल तर Put जास्त लिहिले जातायत → बुल्स "
        "मजबूत. Diff ऋण (negative) असेल तर Call जास्त लिहिले जातायत → बेअर्स मजबूत. "
        "ΔDiff म्हणजे मागच्या 10 मिनिटांच्या तुलनेत Diff किती वाढला/घटला — म्हणजे ही दिशा 'अजून जोर धरतेय की कमी होतेय' हे सांगते.\n\n"
        "- 🟢 **BULLISH**: Diff धन + ΔDiff धन (वाढतोय) → बुलिश ट्रेंड मजबूत होतोय\n"
        "- 🔴 **BEARISH**: Diff ऋण + ΔDiff ऋण (आणखी घटतोय) → बेअरिश ट्रेंड मजबूत होतोय\n"
        "- 🔴 **BULLISH (Weakening)**: अजून Diff धन आहे, पण ΔDiff आता वाढत नाहीये → बुलिश जोर कमी होतोय, म्हणून रंग उलट "
        "(लाल) — पुढे बेअरिशकडे वळण्याचा इशारा\n"
        "- 🟢 **BEARISH (Weakening)**: अजून Diff ऋण आहे, पण ΔDiff आता घटत नाहीये → बेअरिश जोर कमी होतोय, म्हणून रंग उलट "
        "(हिरवा) — पुढे बुलिशकडे वळण्याचा इशारा\\n\\n"
        "⚙️ **Hysteresis:** सिग्नल फक्त तेव्हाच बदलतो जेव्हा Diff मागच्या Diff पेक्षा किमान 10% बदलतो — छोट्या, "
        "noise-सदृश चढ-उतारांमुळे सिग्नल उगाच वारंवार भिरभिरू (flip-flop) नये म्हणून. मागचा ΔDiff बरोबर 0 असेल तेव्हा "
        "सिग्नल सुरक्षित बाजूने बदलला जात नाही."
    )

    # =========================================================
    # ८.५ Advanced OI Analysis (Professional) — OI-Price Matrix, PCR, Max Pain, Rollover
    # =========================================================
    st.markdown("---")
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
            st.caption("टोकाच्या पातळीवर (>1.5 किंवा <0.5) Contrarian वाचला जातो — अति-एकतर्फी पोझिशनिंग अनेकदा उलटफेराचं लक्षण.")
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
        strategy_result = select_credit_spread(raw_chain, pipeline_direction, hedge_width_points, pop_threshold_pct)
    elif sideways_info and sideways_info["is_sideways"]:
        if sideways_info["strategy_type"] == "IRON_BUTTERFLY":
            strategy_result = select_iron_butterfly(raw_chain, atm_strike, hedge_width_points, pop_threshold_pct)
        else:
            strategy_result = select_iron_condor(raw_chain, atm_strike, step, hedge_width_points, pop_threshold_pct)

    if strategy_result:
        available_margin = get_available_margin(token_input)
        lots, risk_amount = compute_position_size(available_margin, risk_pct_per_trade, strategy_result["max_loss"], lot_size)

    st.markdown("---")
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
                    ok, resp = open_multi_leg_trade(
                        token_input, symbol, strategy_result, lots, lot_size,
                        sl_pct_of_max_loss, target_pct_of_max_profit, product_type,
                        trading_mode=trading_mode, trading_style=trading_style,
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

