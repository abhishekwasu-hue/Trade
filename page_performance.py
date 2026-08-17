"""Performance & Backtest page — trade analytics and the Risk:Reward signal checker."""
import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import get_ist_now, get_ist_today
from database import get_performance_summary, get_equity_curve_data, get_performance_by_group
from backtest import run_signal_backtest_rr, run_signal_backtest_v2
from upstox_api import fetch_candles_date_range
from signals import resample_to_1h
from yfinance_source import fetch_yfinance_candles, get_yfinance_max_days
from pdf_reports import generate_backtest_report_pdf_rr, generate_backtest_report_pdf_v2

def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]

    st.subheader("📈 Performance Analytics")
    perf_mode_choice = st.radio("दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key="perf_mode_filter")
    perf_mode_f = None if perf_mode_choice == "सर्व" else ("LIVE" if "LIVE" in perf_mode_choice else "PAPER")

    summary = get_performance_summary(symbol, mode_filter=perf_mode_f)
    if summary.get("total_trades", 0) == 0:
        st.info("अजून कोणतेही बंद झालेले ट्रेड्स नाहीत — Performance आकडे दिसण्यासाठी किमान एक ट्रेड बंद व्हायला हवा.")
    else:
        pcol1, pcol2, pcol3, pcol4 = st.columns(4)
        with pcol1:
            st.metric("Total Trades", summary["total_trades"])
        with pcol2:
            st.metric("Win Rate", f"{summary['win_rate']}%")
        with pcol3:
            st.metric("Total P&L", f"₹{summary['total_pnl']:,.0f}")
        with pcol4:
            pf_str = f"{summary['profit_factor']}" if summary["profit_factor"] is not None else "N/A"
            st.metric("Profit Factor", pf_str)

        pcol5, pcol6, pcol7, pcol8 = st.columns(4)
        with pcol5:
            st.metric("Avg P&L/Trade", f"₹{summary['avg_pnl']:,.0f}")
        with pcol6:
            st.metric("Avg Win", f"₹{summary['avg_win']:,.0f}" if summary["avg_win"] is not None else "N/A")
        with pcol7:
            st.metric("Avg Loss", f"₹{summary['avg_loss']:,.0f}" if summary["avg_loss"] is not None else "N/A")
        with pcol8:
            st.metric("Best / Worst", f"₹{summary['best_trade']:,.0f} / ₹{summary['worst_trade']:,.0f}")

        st.markdown("##### 📉 Equity Curve (संचयी वास्तविक P&L)")
        curve_df = get_equity_curve_data(symbol, mode_filter=perf_mode_f)
        if not curve_df.empty:
            eq_fig = go.Figure()
            eq_fig.add_trace(go.Scatter(
                x=curve_df["exit_time"], y=curve_df["cumulative_pnl"],
                mode="lines+markers", line=dict(color="#2962FF", width=2),
                fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
            ))
            eq_fig.update_layout(
                template="plotly_dark", height=350, margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="#131722", plot_bgcolor="#131722", yaxis_title="Cumulative P&L (₹)",
            )
            st.plotly_chart(eq_fig, width="stretch")
        else:
            st.info("Equity Curve साठी पुरेसा डेटा नाही.")

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            st.markdown("##### 📊 Strategy नुसार")
            by_strat = get_performance_by_group(symbol, "strategy", mode_filter=perf_mode_f)
            st.dataframe(by_strat, width="stretch", hide_index=True) if not by_strat.empty else st.caption("डेटा नाही.")
        with bcol2:
            st.markdown("##### ⏱️ Style नुसार (Intraday/Swing)")
            by_style = get_performance_by_group(symbol, "trading_style", mode_filter=perf_mode_f)
            st.dataframe(by_style, width="stretch", hide_index=True) if not by_style.empty else st.caption("डेटा नाही.")

        if perf_mode_f is None:
            st.markdown("##### 📝 PAPER वि LIVE तुलना")
            comp_rows = []
            for label in ("LIVE", "PAPER"):
                s = get_performance_summary(symbol, mode_filter=label)
                if s.get("total_trades", 0) > 0:
                    comp_rows.append({"Mode": label, "Trades": s["total_trades"], "Win Rate %": s["win_rate"], "Total P&L": s["total_pnl"], "Avg P&L": s["avg_pnl"]})
            if comp_rows:
                st.dataframe(pd.DataFrame(comp_rows), width="stretch", hide_index=True)

    st.markdown("---")
    st.subheader("🔬 Signal Check (Risk:Reward आधारित — Options P&L नाही)")
    st.warning(
        "⚠️ **मर्यादा**: हे फक्त Direction Engine + Market Structure सिग्नलची ऐतिहासिक अचूकता तपासतं "
        "(walk-forward, no lookahead) — दिलेल्या SL% व Risk:Reward गुणोत्तरावरून प्रत्येक सिग्नलनंतर "
        "आधी Target लागतो की Stop-Loss, हे बघितलं जातं. प्रत्यक्ष credit spread च्या पैशांचा backtest "
        "**नाही** (जुन्या option premium चा डेटा Upstox कडून मिळत नाही), आणि यात OI-आधारित गेट्सही "
        "नाहीत (जुना OI डेटा फक्त तुम्ही app वापरायला सुरुवात केल्यापासूनच साठलाय)."
    )

    bt_style_tab1, bt_style_tab2 = st.tabs(["⚡ Intraday (15M)", "🌙 Swing (Daily)"])

    for bt_style_tab, bt_style_name, bt_interval, bt_max_days, bt_key_prefix, default_lbs in [
        (bt_style_tab1, "INTRADAY", "15minute", 180, "bti", 3),
        (bt_style_tab2, "SWING", "day", 3650, "bts", 2),
    ]:
        with bt_style_tab:
            today_d = get_ist_today()

            data_source = st.radio(
                "डेटा स्रोत", ["Upstox (Token आवश्यक)", "Yahoo Finance (Token लागत नाही)"],
                horizontal=True, key=f"{bt_key_prefix}_source",
            )
            use_yfinance = "Yahoo" in data_source
            effective_max_days = get_yfinance_max_days(bt_interval) if use_yfinance else bt_max_days
            if use_yfinance and bt_interval != "day":
                st.caption(
                    f"⚠️ Yahoo Finance वर 15-मिनिटांचा डेटा फक्त गेल्या ~{effective_max_days} दिवसांपुरताच उपलब्ध असतो "
                    "(Yahoo चं स्वतःचं धोरण) — त्यामुळे इथे कमाल रेंज त्यानुसार मर्यादित केलेली आहे."
                )

            default_from = today_d - datetime.timedelta(days=min(60, effective_max_days))
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                bt_from = st.date_input("पासून", value=default_from, max_value=today_d, key=f"{bt_key_prefix}_from")
            with dcol2:
                bt_to = st.date_input("पर्यंत", value=today_d, max_value=today_d, key=f"{bt_key_prefix}_to")

            range_days = (bt_to - bt_from).days
            if range_days <= 0:
                st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
            elif range_days > effective_max_days:
                st.error(f"जास्तीत जास्त {effective_max_days} दिवसांची रेंज निवडता येईल (सध्या {range_days} दिवस निवडले आहेत).")
            else:
                rcol1, rcol2 = st.columns(2)
                with rcol1:
                    bt_sl_pct = st.number_input("SL % (एंट्रीपासूनचं अंतर)", min_value=0.05, value=0.5, step=0.05, key=f"{bt_key_prefix}_sl")
                with rcol2:
                    bt_rr = st.number_input("Risk:Reward गुणोत्तर", min_value=0.5, value=2.0, step=0.5, key=f"{bt_key_prefix}_rr")

                if bt_style_name == "INTRADAY":
                    st.markdown("##### 🧬 Signal Engine — दोन स्वतंत्र रणनीती (दिशा दोन्हीसाठी 1H Supertrend)")
                    strategy_choice = st.radio(
                        "कोणती रणनीती वापरायची?",
                        ["1️⃣ Price Action (BOS/CHoCH + Order Block + Retest + 15M Pattern)",
                         "2️⃣ Indicator Based (RSI 25-55/45-75 + Rejection/Engulfing)"],
                        key=f"{bt_key_prefix}_strategy",
                    )
                    strategy_mode = "price_action" if "1️⃣" in strategy_choice else "indicator"

                    ob_impulse_min_move_pct = 0.3
                    ob_order = 3
                    ob_lookback_swings = 3
                    ob_retest_tolerance_pct = 0.1
                    enable_kill_zone_filter = False
                    require_unmitigated_ob = False
                    require_displacement = False
                    require_fvg_confluence = False
                    if strategy_mode == "price_action":
                        st.caption(
                            "Order Block च्या पुष्टीसाठी लागणारी किमान impulsive हालचाल % — हे बाजाराच्या "
                            "अस्थिरतेनुसार बदलावं लागू शकतं (शांत बाजारात जास्त उंबरठा असेल तर Order Block "
                            "कधीच सापडणार नाही — Funnel मध्ये 'entry_passed' नेहमी 0 दिसत असेल तर हे कमी करा)."
                        )
                        pacol1, pacol2, pacol3 = st.columns(3)
                        with pacol1:
                            ob_order = st.number_input("Fractal Order (Swing शोधण्यासाठी)", min_value=1, value=3, step=1, key=f"{bt_key_prefix}_ob_order")
                        with pacol2:
                            ob_lookback_swings = st.number_input("Lookback Swings", min_value=2, value=3, step=1, key=f"{bt_key_prefix}_ob_lbs")
                        with pacol3:
                            ob_impulse_min_move_pct = st.number_input(
                                "Order Block Impulse किमान %", min_value=0.01, value=0.3, step=0.05, key=f"{bt_key_prefix}_ob_pct",
                            )
                        ob_retest_tolerance_pct = st.number_input(
                            "Retest Tolerance % (OB झोनच्या रुंदीच्या तुलनेत)", min_value=0.1, value=0.1, step=0.5, key=f"{bt_key_prefix}_ob_tol",
                        )
                        st.caption(
                            "0.1% म्हणजे किंमत जवळपास exact OB झोनच्या आतच यावी लागते (खूप कडक). वाढवल्यास "
                            "झोनच्या काठाबाहेरही थोडी 'सूट' मिळते — Funnel मध्ये retest फार कमी वेळा जुळत असेल तर हे वाढवा."
                        )
                        enable_kill_zone_filter = st.checkbox(
                            "Kill-Zone Filter (सुरुवातीचे/शेवटचे 15 मिनिट टाळा — ऐच्छिक)", value=False, key=f"{bt_key_prefix}_killzone",
                        )
                        st.markdown("##### 🎓 व्यावसायिक गुणवत्ता गेट्स (ऐच्छिक — एकत्र लावल्यास सिग्नल्स जवळपास शून्यावर येतात)")
                        require_unmitigated_ob = st.checkbox("Unmitigated Order Block आवश्यक", value=False, key=f"{bt_key_prefix}_unmit")
                        require_displacement = st.checkbox("Displacement Candle आवश्यक", value=False, key=f"{bt_key_prefix}_disp")
                        require_fvg_confluence = st.checkbox("Fair Value Gap Confluence आवश्यक", value=False, key=f"{bt_key_prefix}_fvg")
                        st.caption("डीफॉल्ट सर्व बंद — जास्त सिग्नल्स मिळतील. एकेक चालू करून Funnel Diagnostic ने फरक तपासा.")

                    if st.button(f"🔍 {range_days} दिवसांत किती सिग्नल्स आले ते तपासा", key=f"{bt_key_prefix}_run"):
                        with st.spinner(f"{bt_from} ते {bt_to} चा {bt_interval} + 1H डेटा फेच करून तपासत आहे..."):
                            if use_yfinance:
                                bt_df_range = fetch_yfinance_candles(symbol, bt_interval, bt_from, bt_to)
                                bt_df_1h = fetch_yfinance_candles(symbol, "hour", bt_from, bt_to)
                            else:
                                bt_df_range = fetch_candles_date_range(token_input, symbol, bt_interval, bt_from, bt_to)
                                bt_df_1h_raw = fetch_candles_date_range(token_input, symbol, "30minute", bt_from, bt_to)
                                bt_df_1h = resample_to_1h(bt_df_1h_raw) if not bt_df_1h_raw.empty else bt_df_1h_raw

                            bt_result_range = run_signal_backtest_v2(
                                bt_df_range, bt_df_1h, strategy=strategy_mode, sl_pct=bt_sl_pct, rr_ratio=bt_rr,
                                max_bars=None, max_hold_bars=50,
                                order=ob_order, lookback_swings=ob_lookback_swings,
                                ob_impulse_min_move_pct=ob_impulse_min_move_pct,
                                ob_retest_tolerance_pct=ob_retest_tolerance_pct,
                                enable_kill_zone_filter=enable_kill_zone_filter,
                                require_unmitigated_ob=require_unmitigated_ob, require_displacement=require_displacement,
                                require_fvg_confluence=require_fvg_confluence,
                            )
                        if bt_df_range.empty or bt_df_1h.empty:
                            st.error(
                                "❌ कोणताही डेटा मिळाला नाही (15M किंवा 1H) — " +
                                ("Yahoo Finance वरून (नेटवर्क/चुकीचा सिम्बॉल तपासा)." if use_yfinance else "Upstox token तपासा.")
                            )
                        st.session_state[f"{bt_key_prefix}_df"] = bt_df_range
                        st.session_state[f"{bt_key_prefix}_result"] = bt_result_range
                        st.session_state[f"{bt_key_prefix}_meta"] = (bt_from, bt_to, bt_interval, bt_sl_pct, bt_rr)
                        st.session_state[f"{bt_key_prefix}_v2"] = True
                        st.session_state[f"{bt_key_prefix}_strategy_mode"] = strategy_mode
                        st.session_state[f"{bt_key_prefix}_ob_params"] = {
                            "order": ob_order, "lookback_swings": ob_lookback_swings,
                            "ob_impulse_min_move_pct": ob_impulse_min_move_pct,
                        }

                    if f"{bt_key_prefix}_result" in st.session_state and st.session_state.get(f"{bt_key_prefix}_v2"):
                        r_df = st.session_state[f"{bt_key_prefix}_df"]
                        r_result = st.session_state[f"{bt_key_prefix}_result"]
                        r_from, r_to, r_interval, r_sl, r_rr = st.session_state[f"{bt_key_prefix}_meta"]

                        funnel = r_result.get("funnel", {})
                        if r_result["total"] == 0:
                            st.info(f"📭 {r_from} ते {r_to} या कालावधीत कोणतेही सिग्नल्स सापडले नाहीत.")
                        else:
                            st.success(f"✅ {r_from} ते {r_to} या कालावधीत {r_result['total']} सिग्नल्स सापडले.")

                        if funnel:
                            st.markdown("##### 🔍 Funnel Diagnostic")
                            fc1, fc2, fc3 = st.columns(3)
                            with fc1:
                                st.metric("तपासलेले Bars", funnel["bars_checked"])
                            with fc2:
                                pct = f"{funnel['structure_directional']/funnel['bars_checked']*100:.0f}%" if funnel["bars_checked"] else "0%"
                                st.metric("1H दिशा उपलब्ध", funnel["structure_directional"], pct)
                            with fc3:
                                pct2 = f"{funnel['entry_passed']/funnel['structure_directional']*100:.1f}%" if funnel["structure_directional"] else "N/A"
                                st.metric("Entry जुळले", funnel["entry_passed"], pct2)

                        if r_result["total"] > 0:
                            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                            with mcol1:
                                st.metric("एकूण सिग्नल्स", r_result["total"])
                            with mcol2:
                                win_rate_str = f"{r_result['win_rate']}%" if r_result["win_rate"] is not None else "N/A"
                                st.metric("Win Rate", win_rate_str)
                            with mcol3:
                                st.metric("Target / SL", f"{r_result['target_count']} / {r_result['sl_count']}")
                            with mcol4:
                                st.metric("अजून Open", r_result["open_count"])
                            st.dataframe(pd.DataFrame(r_result["signals"]), width="stretch", height=250)

                            if st.button("📄 Backtest PDF Report तयार करा", key=f"{bt_key_prefix}_pdf_v2"):
                                with st.spinner("PDF तयार होत आहे..."):
                                    saved_strategy_mode = st.session_state.get(f"{bt_key_prefix}_strategy_mode", "indicator")
                                    saved_ob_params = st.session_state.get(f"{bt_key_prefix}_ob_params", {})
                                    clean_strategy_name = "Price Action" if saved_strategy_mode == "price_action" else "Indicator Based"
                                    bt_pdf_bytes = generate_backtest_report_pdf_v2(
                                        symbol, clean_strategy_name, r_interval, r_from, r_to, r_sl, r_rr,
                                        saved_ob_params, r_df, r_result,
                                    )
                                bt_filename = f"A1_Backtest_{clean_strategy_name.replace(' ', '')}_{symbol}_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                st.download_button(
                                    "📥 Download Backtest PDF Report", data=bt_pdf_bytes,
                                    file_name=bt_filename, mime="application/pdf", key=f"{bt_key_prefix}_dl_v2",
                                )
                                st.success("✅ रिपोर्ट तयार झाला — वरील बटणावर क्लिक करून डाऊनलोड करा.")
                else:
                    bt_lookback_swings = st.slider(
                        "Structure Lookback Swings (कमी = जास्त सिग्नल्स)", min_value=2, max_value=5,
                        value=default_lbs, key=f"{bt_key_prefix}_lbs",
                    )
                    bt_tolerance = st.number_input(
                        "Pullback/Retest Tolerance %", min_value=0.1, value=0.4, step=0.1, key=f"{bt_key_prefix}_tol",
                    )

                    if st.button(f"🔍 {range_days} दिवसांत किती सिग्नल्स आले ते तपासा", key=f"{bt_key_prefix}_run"):
                        with st.spinner(f"{bt_from} ते {bt_to} चा {bt_interval} डेटा फेच करून तपासत आहे..."):
                            if use_yfinance:
                                bt_df_range = fetch_yfinance_candles(symbol, bt_interval, bt_from, bt_to)
                            else:
                                bt_df_range = fetch_candles_date_range(token_input, symbol, bt_interval, bt_from, bt_to)
                            bt_result_range = run_signal_backtest_rr(
                                bt_df_range, sl_pct=bt_sl_pct, rr_ratio=bt_rr,
                                lookback_swings=bt_lookback_swings, tolerance_pct=bt_tolerance, max_bars=None,
                                max_hold_bars=20,
                            )
                        if bt_df_range.empty:
                            st.error(
                                "❌ कोणताही डेटा मिळाला नाही — " +
                                ("Yahoo Finance वरून (नेटवर्क/चुकीचा सिम्बॉल तपासा)." if use_yfinance else "Upstox token तपासा.")
                            )
                        st.session_state[f"{bt_key_prefix}_df"] = bt_df_range
                        st.session_state[f"{bt_key_prefix}_result"] = bt_result_range
                        st.session_state[f"{bt_key_prefix}_meta"] = (bt_from, bt_to, bt_interval, bt_sl_pct, bt_rr)
                        st.session_state[f"{bt_key_prefix}_v2"] = False

                    if f"{bt_key_prefix}_result" in st.session_state and not st.session_state.get(f"{bt_key_prefix}_v2", True):
                        r_df = st.session_state[f"{bt_key_prefix}_df"]
                        r_result = st.session_state[f"{bt_key_prefix}_result"]
                        r_from, r_to, r_interval, r_sl, r_rr = st.session_state[f"{bt_key_prefix}_meta"]

                        funnel = r_result.get("funnel", {})
                        breakdown = r_result.get("structure_breakdown", {})

                        if r_result["total"] == 0:
                            st.info(f"📭 {r_from} ते {r_to} या कालावधीत ({r_interval}, {bt_style_name}) कोणतेही सिग्नल्स सापडले नाहीत.")
                            st.caption(
                                "याचा अर्थ: या कालावधीत Break + Pullback + Retest ही सगळी परिस्थिती एकत्र कधीच जुळली नाही. "
                                "खाली नेमकं कोणत्या टप्प्यावर अडलं ते बघा (अंदाज नाही, प्रत्यक्ष आकडे)."
                            )

                        if funnel:
                            st.markdown("##### 🔍 Funnel Diagnostic — नेमकं कुठे अडतंय?")
                            fcol1, fcol2, fcol3, fcol4 = st.columns(4)
                            with fcol1:
                                st.metric("तपासलेले Bars", funnel["bars_checked"])
                            with fcol2:
                                pct = f"{funnel['structure_directional']/funnel['bars_checked']*100:.0f}%" if funnel["bars_checked"] else "0%"
                                st.metric("Directional Structure", funnel["structure_directional"], pct)
                            with fcol3:
                                pct2 = f"{funnel['broke']/funnel['structure_directional']*100:.0f}%" if funnel["structure_directional"] else "N/A"
                                st.metric("त्यातले Break झालेले", funnel["broke"], pct2)
                            with fcol4:
                                pct3 = f"{funnel['pulled_back_and_retested']/funnel['broke']*100:.0f}%" if funnel["broke"] else "N/A"
                                st.metric("Pullback+Retest जुळलेले", funnel["pulled_back_and_retested"], pct3)

                            if breakdown:
                                st.caption(
                                    f"Structure breakdown — HH/HL (तेजी): {breakdown.get('HH/HL',0)} · "
                                    f"LH/LL (मंदी): {breakdown.get('LH/LL',0)} · "
                                    f"RANGING/MIXED: {breakdown.get('RANGING_or_MIXED',0)} · "
                                    f"अपुरा डेटा: {breakdown.get('INSUFFICIENT_DATA',0)}"
                                )
                            if funnel["bars_checked"] > 0 and funnel["structure_directional"] / funnel["bars_checked"] < 0.15:
                                st.warning(
                                    "⚠️ बहुतांश वेळ बाजार RANGING/MIXED दिसतोय (Directional Structure फार कमी वेळा जुळतंय) — "
                                    "structure_order किंवा lookback_swings कमी केल्यास जास्त संधी मिळू शकतात."
                                )

                        if r_result["total"] > 0:
                            st.success(f"✅ {r_from} ते {r_to} या कालावधीत {r_result['total']} सिग्नल्स सापडले.")
                            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                            with mcol1:
                                st.metric("एकूण सिग्नल्स", r_result["total"])
                            with mcol2:
                                win_rate_str = f"{r_result['win_rate']}%" if r_result["win_rate"] is not None else "N/A"
                                st.metric("Win Rate (Target vs SL)", win_rate_str)
                            with mcol3:
                                st.metric("Target / SL", f"{r_result['target_count']} / {r_result['sl_count']}")
                            with mcol4:
                                st.metric("अजून Open", r_result["open_count"])
                            st.dataframe(pd.DataFrame(r_result["signals"]), width="stretch", height=250)

                            if st.button("📄 Backtest PDF Report तयार करा", key=f"{bt_key_prefix}_pdf"):
                                with st.spinner("PDF तयार होत आहे..."):
                                    bt_pdf_bytes = generate_backtest_report_pdf_rr(
                                        symbol, bt_style_name, r_interval, r_from, r_to, r_sl, r_rr, r_df, r_result,
                                    )
                                bt_filename = f"A1_Backtest_{bt_style_name}_{symbol}_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                st.download_button(
                                    "📥 Download Backtest PDF Report", data=bt_pdf_bytes,
                                    file_name=bt_filename, mime="application/pdf", key=f"{bt_key_prefix}_dl",
                                )
                                st.success("✅ रिपोर्ट तयार झाला — वरील बटणावर क्लिक करून डाऊनलोड करा.")

