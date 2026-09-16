"""Bot Dynamic SR Algo — Settings page (नवीन नियम-संच, Word document प्रमाणे).

वापरकर्त्याशी चर्चा करून बांधलेली — दोन्ही strategies (1-मिनिट Instant Trader आणि 15M/30M/60M
Dynamic SR Reversal) साठी सर्व सेटिंग्ज (Lots, ITM Depth, Hedge Width, RSI/PCR Entry Gate,
SL/TSL/Target Exit Gate, Naked Option Trade toggle) — एकाच पानावर, Dashboard वरूनच बदलण्याजोगी
(hardcode नाही).

🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Gate / Exit Gate विभागणी) — आधी RSI उंबरठे
(Support<40/Resistance>60, किंवा 15m साठी neutral=50) module मध्ये hardcoded होते, आणि PCR गेट
कधीच पूर्णपणे बंद करता येत नव्हता. आता दोन्ही स्वतंत्र "🚪 Entry Gate" tab मध्ये — प्रत्येकाचा
स्वतःचा on/off checkbox सह, अ‍ॅडजस्टेबल उंबरठे सकट. सगळे SL/TSL/Target (Credit Spread + Naked
दोन्ही) आता स्वतंत्र "🚪 Exit Gate" tab मध्ये.
"""
import streamlit as st

import cloud_db

SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]
STRATEGY_LABELS = {"1m_instant": "1-मिनिट Instant Trader (1M + 5M)", "15m_dynamic_sr": "15M/30M/60M Dynamic SR Reversal"}


def _widget_key(strategy_key, symbol, field):
    # 🎓 वापरकर्त्याने सापडवलेली bug — आधी widget key फक्त "bdsr_<field>" असायचा (strategy/symbol
    # शिवाय), म्हणजे सर्व 2 strategies × 3 symbols साठी तोच एक key — Strategy/Symbol बदलल्यावर
    # cloud_db.get_strategy_settings() नवीन combo चे बरोबर settings आणायचं, पण Streamlit त्या
    # widget-key ला आधीच साठवलेली (आधीच्या combo ची) value दाखवत राहायचं (हेच established Streamlit
    # वर्तन — same key असेल तर नवीन `value=` कडे दुर्लक्ष होतं). आता प्रत्येक widget चा key स्वतः
    # strategy_key+symbol सकट असल्याने, combo बदलताच तो पूर्णपणे नवीन widget ठरतो — आणि cloud_db
    # वरून आलेलं बरोबर value लगेच दिसतं.
    return f"bdsr_{strategy_key}_{symbol}_{field}"


def _number_input(label, settings, key, strategy_key, symbol, **kwargs):
    # 🎓 वापरकर्त्याने सापडवलेली bug — आधी साठवलेल्या value च्या (int/float) प्रकारावरून casting
    # व्हायचं, पण caller ने दिलेले min_value/max_value/step मात्र नेहमी float — Streamlit ला हे
    # दोन्ही एकाच प्रकारचे (सर्व int किंवा सर्व float) हवेत, नाहीतर StreamlitMixedNumericTypesError.
    # आता caller च्या kwargs वरूनच (साठवलेल्या value च्या प्रकारावरून नाही) ठरवतो.
    is_float = isinstance(kwargs.get("step"), float) or isinstance(kwargs.get("min_value"), float) or isinstance(kwargs.get("max_value"), float)
    value = float(settings[key]) if is_float else int(settings[key])
    return st.number_input(label, value=value, key=_widget_key(strategy_key, symbol, key), **kwargs)


def render():
    st.subheader("🤖 Bot Dynamic SR Algo")
    st.caption("दोन्ही strategies (1-मिनिट Instant Trader, 15M/30M/60M Dynamic SR Reversal) चे सर्व सेटिंग्ज — इथूनच, कधीही बदलता येण्याजोगे.")

    col_a, col_b = st.columns(2)
    with col_a:
        strategy_key = st.selectbox("Strategy", list(STRATEGY_LABELS.keys()), format_func=lambda k: STRATEGY_LABELS[k], key="bdsr_strategy")
    with col_b:
        symbol = st.selectbox("Symbol", SYMBOLS, key="bdsr_symbol")

    settings = cloud_db.get_strategy_settings(strategy_key, symbol)

    tab_entry, tab_exit = st.tabs(["🚪 Entry Gate", "🚪 Exit Gate"])

    with tab_entry:
        st.markdown("##### 🔻 Strike व Size निवड (Credit Spread — मुख्य ट्रेड)")
        st.caption("Short leg ATM पासून ITM दिशेने (जास्त प्रीमियम, कमी अंतर) — OTM ऐवजी.")
        c1, c2, c3 = st.columns(3)
        with c1:
            lots = _number_input("Lots", settings, "lots", strategy_key, symbol, min_value=1, max_value=50, step=1)
        with c2:
            itm_depth_points = _number_input("ITM Depth (points)", settings, "itm_depth_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)
        with c3:
            hedge_width_points = _number_input("Hedge Width (points)", settings, "hedge_width_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)

        st.markdown("---")
        st.markdown("##### 🧭 RSI Gate")
        entry_rsi_gate_enabled = st.checkbox(
            "RSI Gate सक्रिय (बंद केल्यास — फक्त S/R Touch वरच entry, RSI तपासला जाणार नाही)",
            value=bool(settings.get("entry_rsi_gate_enabled", True)),
            key=_widget_key(strategy_key, symbol, "entry_rsi_gate_enabled"),
        )
        if strategy_key == "1m_instant":
            st.caption("Support/Bullish → RSI यापेक्षा कमी हवा. Resistance/Bearish → RSI यापेक्षा जास्त हवा.")
            r1, r2 = st.columns(2)
            with r1:
                rsi_support_max = _number_input(
                    "RSI Support Max (Bullish साठी यापेक्षा कमी)", settings, "rsi_support_max", strategy_key, symbol,
                    min_value=5, max_value=50, step=1, disabled=not entry_rsi_gate_enabled,
                )
            with r2:
                rsi_resistance_min = _number_input(
                    "RSI Resistance Min (Bearish साठी यापेक्षा जास्त)", settings, "rsi_resistance_min", strategy_key, symbol,
                    min_value=50, max_value=95, step=1, disabled=not entry_rsi_gate_enabled,
                )
        else:
            st.caption("Support/Bullish → RSI या neutral level पेक्षा कमी हवा. Resistance/Bearish → यापेक्षा जास्त हवा.")
            rsi_neutral_level = _number_input(
                "RSI Neutral Level", settings, "rsi_neutral_level", strategy_key, symbol,
                min_value=30, max_value=70, step=1, disabled=not entry_rsi_gate_enabled,
            )

        st.markdown("---")
        st.markdown("##### 🚦 PCR Gate")
        entry_pcr_gate_enabled = st.checkbox(
            "PCR Gate सक्रिय (बंद केल्यास — PCR तपासला जाणार नाही, फक्त डेटा गहाळ/जुना असतानाचं सुरक्षा-कवचही बंद होईल)",
            value=bool(settings.get("entry_pcr_gate_enabled", True)),
            key=_widget_key(strategy_key, symbol, "entry_pcr_gate_enabled"),
        )
        st.caption("दोन्ही trade-प्रकारांना (Credit Spread + Naked) एकत्र लागू — PCR डेटा गहाळ/जुना (>15 मिनिटं) असल्यास सुरक्षिततेसाठी trade थांबवला जातो (Gate सक्रिय असेल तरच).")
        p1, p2 = st.columns(2)
        with p1:
            pcr_bullish_min = _number_input(
                "PCR यापेक्षा कमी असेल तर Bullish नाही", settings, "pcr_bullish_min", strategy_key, symbol,
                min_value=0.10, max_value=2.0, step=0.05, format="%.2f", disabled=not entry_pcr_gate_enabled,
            )
        with p2:
            pcr_bearish_max = _number_input(
                "PCR यापेक्षा जास्त असेल तर Bearish नाही", settings, "pcr_bearish_max", strategy_key, symbol,
                min_value=0.10, max_value=2.0, step=0.05, format="%.2f", disabled=not entry_pcr_gate_enabled,
            )

        st.markdown("---")
        st.markdown("##### 🔺 Long With Hedge (Naked Option Trade)")
        st.caption("त्याच सिग्नलवर, Credit Spread सोबतच, समांतर घेतला जातो. डीफॉल्ट: hedge नाही (निव्वळ ITM खरेदी) — हवं असल्यास हेजिंग सक्रिय करा.")
        n0, n1 = st.columns(2)
        with n0:
            naked_enabled = st.checkbox("Naked Option Trade सक्रिय", value=bool(settings.get("naked_enabled", True)), key=_widget_key(strategy_key, symbol, "naked_enabled"))
        with n1:
            naked_hedge_enabled = st.checkbox("Hedge जोडा (Debit Spread) — डीफॉल्ट बंद", value=bool(settings.get("naked_hedge_enabled", False)), key=_widget_key(strategy_key, symbol, "naked_hedge_enabled"))
        naked_hedge_width_points = _number_input("Naked Hedge Width (points, hedge सक्रिय असेल तरच)", settings, "naked_hedge_width_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)

    with tab_exit:
        st.markdown("##### 🎯 SL / TSL / Target (Credit Spread)")
        if strategy_key == "1m_instant":
            st.caption("SL/TSL/Target — Spot% आणि Premium-Points दोन्ही एकत्र (जे आधी घडेल ते लागू).")
            s1, s2 = st.columns(2)
            with s1:
                spread_sl_spot_pct = _number_input("SL — Spot %", settings, "spread_sl_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
                spread_tsl_spot_pct = _number_input("TSL Activation — Spot %", settings, "spread_tsl_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
                spread_target_spot_pct = _number_input("Target — Spot %", settings, "spread_target_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
            with s2:
                spread_sl_premium_points = _number_input("SL — Premium Points", settings, "spread_sl_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
                spread_tsl_premium_points = _number_input("TSL Activation — Premium Points", settings, "spread_tsl_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
                spread_target_premium_points = _number_input("Target — Premium Points", settings, "spread_target_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
            st.caption("TSL सक्रिय झाल्यावर SL Entry/Breakeven वर घट्ट होतो (एकदाच, कायमचा).")
        else:
            st.caption("SL/TSL — Spot% + Premium-Points एकत्र. Target मात्र निव्वळ प्रीमियमच्या % (उदा. 80%).")
            s1, s2 = st.columns(2)
            with s1:
                spread_sl_spot_pct = _number_input("SL — Spot %", settings, "spread_sl_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
                spread_tsl_spot_pct = _number_input("TSL Activation — Spot %", settings, "spread_tsl_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
            with s2:
                spread_sl_premium_points = _number_input("SL — Premium Points", settings, "spread_sl_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
                spread_tsl_premium_points = _number_input("TSL Activation — Premium Points", settings, "spread_tsl_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
            s3, s4 = st.columns(2)
            with s3:
                spread_target_pct_of_premium = _number_input("Target — % of Net Premium", settings, "spread_target_pct_of_premium", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
            with s4:
                carry_forward_min_profit_pct = _number_input("Carry-Forward किमान नफा %", settings, "carry_forward_min_profit_pct", strategy_key, symbol, min_value=1.0, max_value=100.0, step=1.0)
            st.caption("3:10pm ला Target अजून गाठलेला नसेल — नफा वरील % पेक्षा जास्त तर पुढच्या दिवशी चालू, नाहीतर आजच बंद. Exit त्याच timeframe च्या पुढच्या level ला (entry_timeframe नुसार).")

        st.markdown("---")
        st.markdown("##### 🎯 SL / TSL / Target (Naked Option)")
        st.caption("Naked trade कधीच carry-forward नाही — नेहमी आजच (खालील EOD वेळेला) बंद.")
        m1, m2 = st.columns(2)
        with m1:
            naked_sl_spot_pct = _number_input("SL — Spot %", settings, "naked_sl_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
            naked_tsl_spot_pct = _number_input("TSL Activation — Spot %", settings, "naked_tsl_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
            naked_target_spot_pct = _number_input("Target — Spot %", settings, "naked_target_spot_pct", strategy_key, symbol, min_value=0.01, max_value=5.0, step=0.01, format="%.2f")
        with m2:
            naked_sl_premium_points = _number_input("SL — Premium Points", settings, "naked_sl_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
            naked_tsl_premium_points = _number_input("TSL Activation — Premium Points", settings, "naked_tsl_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)
            naked_target_premium_points = _number_input("Target — Premium Points", settings, "naked_target_premium_points", strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0)

        if strategy_key == "15m_dynamic_sr":
            e1, e2 = st.columns(2)
            with e1:
                naked_eod_hour = _number_input("Naked EOD तास (24-तास)", settings, "naked_eod_hour", strategy_key, symbol, min_value=9, max_value=15, step=1)
            with e2:
                naked_eod_minute = _number_input("Naked EOD मिनिट", settings, "naked_eod_minute", strategy_key, symbol, min_value=0, max_value=59, step=5)

    st.markdown("---")
    if st.button("💾 Settings जतन करा", key="bdsr_save_btn", type="primary"):
        new_settings = {
            "lots": int(lots), "itm_depth_points": float(itm_depth_points), "hedge_width_points": float(hedge_width_points),
            "entry_rsi_gate_enabled": bool(entry_rsi_gate_enabled),
            "entry_pcr_gate_enabled": bool(entry_pcr_gate_enabled),
            "pcr_bullish_min": float(pcr_bullish_min), "pcr_bearish_max": float(pcr_bearish_max),
            "spread_sl_spot_pct": float(spread_sl_spot_pct), "spread_sl_premium_points": float(spread_sl_premium_points),
            "spread_tsl_spot_pct": float(spread_tsl_spot_pct), "spread_tsl_premium_points": float(spread_tsl_premium_points),
            "naked_enabled": bool(naked_enabled), "naked_hedge_enabled": bool(naked_hedge_enabled),
            "naked_hedge_width_points": float(naked_hedge_width_points),
            "naked_sl_spot_pct": float(naked_sl_spot_pct), "naked_sl_premium_points": float(naked_sl_premium_points),
            "naked_tsl_spot_pct": float(naked_tsl_spot_pct), "naked_tsl_premium_points": float(naked_tsl_premium_points),
            "naked_target_spot_pct": float(naked_target_spot_pct), "naked_target_premium_points": float(naked_target_premium_points),
        }
        if strategy_key == "1m_instant":
            new_settings["rsi_support_max"] = int(rsi_support_max)
            new_settings["rsi_resistance_min"] = int(rsi_resistance_min)
            new_settings["spread_target_spot_pct"] = float(spread_target_spot_pct)
            new_settings["spread_target_premium_points"] = float(spread_target_premium_points)
        else:
            new_settings["rsi_neutral_level"] = int(rsi_neutral_level)
            new_settings["spread_target_pct_of_premium"] = float(spread_target_pct_of_premium)
            new_settings["carry_forward_min_profit_pct"] = float(carry_forward_min_profit_pct)
            new_settings["naked_eod_hour"] = int(naked_eod_hour)
            new_settings["naked_eod_minute"] = int(naked_eod_minute)

        ok = cloud_db.save_strategy_settings(strategy_key, symbol, new_settings)
        if ok:
            st.success(f"✅ {STRATEGY_LABELS[strategy_key]} ({symbol}) साठी settings जतन झाले — पुढच्या cycle पासून लागू होतील.")
        else:
            st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")
