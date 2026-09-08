"""MTF Pullback + Gap Fill page.
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Dashboard वरच्या tab-गर्दी कमी करण्यासाठी,
हे (established page_dashboard.py चं जुनं tab6) आता एक स्वतंत्र sidebar page आहे."""
import streamlit as st

from upstox_api import fetch_candles, fetch_timeframe_df


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]
    underlying_price = st.session_state["underlying_price"]

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

            df_1h_mtf = fetch_timeframe_df(token_input, symbol, underlying_price, "1hour")
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
