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
import database
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_PINK, HDR_GREEN, HDR_AMBER, HDR_CYAN

SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]
STRATEGY_LABELS = {
    "1m_instant": "1-मिनिट Instant Trader (1M + 5M)",
    "15m_dynamic_sr": "15M/30M/60M Dynamic SR Reversal",
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली, नवीन स्वतंत्र तिसरी strategy — "Classical Support/Resistance
    # Reversal" (5M+15M pooled). आधीच्या दोन strategies पूर्णपणे अबाधित — फक्त हा नवीन पर्याय जोडलेला.
    "classic_sr_reversal": "🎯 Classical S/R Reversal (5M + 15M)",
}


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


def _render_live_status_banner():
    # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("नवीन/novice वापरकर्त्यालाही हे पान सहज वापरता यावं") —
    # पानाच्या सर्वात वर, सध्या Strategy/Symbol dropdown मध्ये काहीही निवडलेलं असो, कुठलीही combo
    # LIVE आहे का हे एका दृष्टीक्षेपात दिसावं म्हणून. Dropdown खालीच बदलत राहतो — पण एखादी strategy
    # आधीच कधीतरी LIVE केलेली विसरली जाऊ नये (विशेषतः नवीन वापरकर्त्यासाठी) यासाठी ही स्वतंत्र, नेहमी
    # दिसणारी पट्टी.
    all_modes = cloud_db.get_all_strategy_trading_modes()
    live_combos = [
        (strategy_key, symbol) for (strategy_key, symbol), info in all_modes.items()
        if info.get("trading_mode") == "LIVE"
    ]
    if live_combos:
        lines = "; ".join(f"**{STRATEGY_LABELS.get(sk, sk)} ({sym})**" for sk, sym in live_combos)
        st.error(f"🔴 सध्या LIVE (खऱ्या पैशांनी) चालू आहे: {lines}")
    else:
        st.success("🟢 सर्व strategies सध्या PAPER मोडमध्ये आहेत — कुठलाही खरा पैसा वापरला जात नाही.")


def _render_kill_switch_panel():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — तिन्ही bots साठी एकत्रित, संपूर्ण-खात्यासाठीचं (per-strategy/symbol
    नाही) सुरक्षा-सेटिंग. आजचा एकूण LIVE तोटा किंवा ट्रेड-संख्या इथल्या मर्यादेपलीकडे गेली, तर पुढचे
    सर्व LIVE trades (कुठल्याही bot/symbol चे) trading_engine.open_multi_leg_trade() कडूनच आपोआप
    थांबतात (PAPER trades वर कुठलाही परिणाम नाही)."""
    ks_settings = cloud_db.get_kill_switch_settings()
    total_pnl, total_trades = database.get_todays_live_total_pnl_and_count()

    with st.expander("🛑 LIVE Kill Switch (सर्व Bots + Dashboard साठी एकत्रित)", expanded=False):
        st.caption(
            "आजचा एकूण खऱ्या पैशांचा (LIVE) तोटा किंवा ट्रेड-संख्या इथल्या मर्यादेपलीकडे गेली, तर "
            "तिन्ही bots + Dashboard कडून पुढचे कुठलेही नवीन LIVE trade घेतले जाणार नाहीत (PAPER "
            "trades नेहमीप्रमाणेच चालू राहतील) — जोपर्यंत तुम्ही स्वतः इथून सेटिंग्ज बदलत नाही."
        )
        tripped = ks_settings["enabled"] and (
            total_pnl <= -ks_settings["max_daily_loss"] or total_trades >= ks_settings["max_trades_per_day"]
        )
        if not ks_settings["enabled"]:
            st.warning("⚪ Kill Switch सध्या बंद आहे — LIVE ट्रेड्सवर कुठलीही स्वयंचलित मर्यादा नाही.")
        elif tripped:
            st.error(f"🔴 Kill Switch ट्रिप झालं आहे — आजचा एकूण LIVE P&L ₹{total_pnl:,.0f}, ट्रेड्स {total_trades}. नवीन LIVE trade ब्लॉक केला जातोय.")
        else:
            st.success(f"🟢 Kill Switch OK — आजचा एकूण LIVE P&L ₹{total_pnl:,.0f}, ट्रेड्स {total_trades}/{ks_settings['max_trades_per_day']}.")

        ks_enabled = st.checkbox("Kill Switch सक्रिय", value=ks_settings["enabled"], key="bdsr_ks_enabled")
        c1, c2 = st.columns(2)
        with c1:
            ks_max_loss = st.number_input(
                "कमाल दैनिक तोटा ₹ (सर्व LIVE bots मिळून)", min_value=500.0,
                value=float(ks_settings["max_daily_loss"]), step=500.0, key="bdsr_ks_max_loss",
            )
        with c2:
            ks_max_trades = st.number_input(
                "कमाल दैनिक LIVE ट्रेड्स (सर्व bots मिळून)", min_value=1,
                value=int(ks_settings["max_trades_per_day"]), step=1, key="bdsr_ks_max_trades",
            )
        if st.button("💾 Kill Switch सेव्ह करा", key="bdsr_ks_save_btn"):
            ok = cloud_db.save_kill_switch_settings(ks_enabled, ks_max_loss, ks_max_trades)
            if ok:
                st.success("✅ Kill Switch सेटिंग्ज जतन झाल्या.")
            else:
                st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")


def render():
    mega_header("🤖 Bot Dynamic SR Algo", HDR_BLUE)
    st.caption("तिन्ही strategies (1-मिनिट Instant Trader, 15M/30M/60M Dynamic SR Reversal, Classical S/R Reversal) चे सर्व सेटिंग्ज — इथूनच, कधीही बदलता येण्याजोगे.")

    _render_live_status_banner()
    _render_kill_switch_panel()

    with st.expander("❓ हे पान पहिल्यांदाच वापरताय? इथे क्लिक करा"):
        st.markdown(
            "- खाली **Strategy** आणि **Symbol** (NIFTY/BANKNIFTY/SENSEX) निवडा — प्रत्येक जोडीचे सेटिंग्ज स्वतंत्र असतात.\n"
            "- **🚪 Entry Gate** — कधी trade घ्यायचा (RSI/PCR सारखे नियम).\n"
            "- **🚪 Exit Gate** — कधी बंद करायचा (SL/Target/Trailing SL).\n"
            "- **🎮 Mode & Broker** — खरे पैसे वापरायचे की नाही (PAPER/LIVE), आणि कुठल्या broker खात्यावर.\n"
            "- **नवीन असाल तर**: सुरुवातीला सर्व काही PAPER वरच ठेवा (डीफॉल्ट), काही दिवस निकाल बघा (Performance पानावर), आणि समाधान झाल्यावरच हळूहळू LIVE करा.\n"
            "- शेवटी नेहमी **💾 Settings जतन करा** बटण दाबायला विसरू नका — नाहीतर बदल जतन होणार नाहीत."
        )

    col_a, col_b = st.columns(2)
    with col_a:
        strategy_key = st.selectbox("Strategy", list(STRATEGY_LABELS.keys()), format_func=lambda k: STRATEGY_LABELS[k], key="bdsr_strategy")
    with col_b:
        symbol = st.selectbox("Symbol", SYMBOLS, key="bdsr_symbol")

    settings = cloud_db.get_strategy_settings(strategy_key, symbol)

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (symbol_enabled) — "Symbol selection optional
    # ठेवा, उपलब्ध भांडवलानुसार वापरकर्ता निवडणार" — त्यामुळे प्रत्येक symbol साठी स्वतंत्र मास्टर
    # चालू/बंद स्विच (NIFTY डीफॉल्ट चालू — आधीपासूनचं वर्तन कायम; BANKNIFTY/SENSEX डीफॉल्ट बंद —
    # वापरकर्त्याने भांडवल असल्यासच स्पष्टपणे सक्रिय करायचं). बंद असल्यास हा symbol या strategy
    # साठी पूर्णपणे वगळला जातो — कुठलाही PAPER/LIVE trade घेतला जात नाही.
    symbol_enabled = st.checkbox(
        f"✅ {symbol} साठी {STRATEGY_LABELS[strategy_key]} सक्रिय (उपलब्ध भांडवलानुसार निवडा)",
        value=bool(settings.get("symbol_enabled", symbol == "NIFTY")),
        key=_widget_key(strategy_key, symbol, "symbol_enabled"),
    )
    if not symbol_enabled:
        st.warning(f"⚠️ {symbol} सध्या बंद आहे — या symbol वर कुठलाही नवीन trade (Credit Spread किंवा Naked) घेतला जाणार नाही.")

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — सध्या निवडलेल्या Strategy+Symbol चा मोड/broker "🎮 Mode &
    # Broker" tab उघडल्याशिवायही इथेच लगेच दिसावा (नवीन वापरकर्त्याला tab शोधावा लागू नये).
    _current_mode = settings.get("trading_mode", "PAPER")
    _current_broker_ids = settings.get("broker_account_ids") or []
    if _current_mode == "LIVE":
        _mode_caption = "🔴 सध्याचा मोड: **LIVE** (खरे पैसे)"
    else:
        _mode_caption = "📝 सध्याचा मोड: **PAPER** (सिम्युलेटेड, सुरक्षित)"
    _broker_caption = f"🏦 {len(_current_broker_ids)} broker account(s) निवडलेले" if _current_broker_ids else "🏦 Broker: डीफॉल्ट (शुद्ध Upstox)"
    st.caption(f"{_mode_caption} · {_broker_caption} — बदलण्यासाठी खालचं '🎮 Mode & Broker' tab बघा.")

    tab_entry, tab_exit, tab_mode = st.tabs(["🚪 Entry Gate", "🚪 Exit Gate", "🎮 Mode & Broker"])

    with tab_entry:
        if strategy_key in ("1m_instant", "classic_sr_reversal"):
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — या strategies मध्ये दोन्ही टाईमफ्रेमचे
            # touch levels डीफॉल्ट एकत्र तपासले जातात — वापरकर्त्याला हवं असल्यास फक्त एकाच
            # टाईमफ्रेमवर मर्यादित ठेवता येईल.
            sub_header("⏱️ Touch Timeframe", HDR_TEAL)
            if strategy_key == "1m_instant":
                _TF_OPTIONS = {"BOTH": "1M + 5M (दोन्ही, डीफॉल्ट)", "1M": "फक्त 1M", "5M": "फक्त 5M"}
            else:
                _TF_OPTIONS = {"BOTH": "5M + 15M (दोन्ही, डीफॉल्ट)", "5M": "फक्त 5M", "15M": "फक्त 15M"}
            _tf_keys = list(_TF_OPTIONS.keys())
            timeframe_choice = st.radio(
                "कोणत्या टाईमफ्रेमचे touch levels तपासायचे?",
                _tf_keys, format_func=lambda k: _TF_OPTIONS[k], horizontal=True,
                index=_tf_keys.index(settings.get("timeframe_choice", "BOTH")),
                key=_widget_key(strategy_key, symbol, "timeframe_choice"),
            )
            st.markdown("---")

        sub_header("🔻 Strike व Size निवड (Credit Spread — मुख्य ट्रेड)", HDR_PURPLE)
        st.caption("Short leg ATM पासून ITM दिशेने (जास्त प्रीमियम, कमी अंतर) — OTM ऐवजी.")
        c1, c2, c3 = st.columns(3)
        with c1:
            lots = _number_input("Lots", settings, "lots", strategy_key, symbol, min_value=1, max_value=50, step=1)
        with c2:
            itm_depth_points = _number_input("ITM Depth (points)", settings, "itm_depth_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)
        with c3:
            hedge_width_points = _number_input("Hedge Width (points)", settings, "hedge_width_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)

        st.markdown("---")
        sub_header("🧭 RSI Gate", HDR_ORANGE)
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

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — classic_sr_reversal साठी PCR गेट मुद्दामच नाही
        # ("फक्त शुद्ध classical S/R" कल्पना — RSI गेटच फक्त, backtest मध्येही तेच वापरलेलं).
        if strategy_key != "classic_sr_reversal":
            st.markdown("---")
            sub_header("🚦 PCR Gate", HDR_PINK)
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

        if strategy_key == "classic_sr_reversal":
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Ya strategy mdhe swing high swing low,
            # demand supply, trend line he sarv concept include kra and entry refine kra" — तीन
            # ऐच्छिक, स्वतंत्र confluence गेट्स (सर्व डीफॉल्ट बंद). RSI गेट (वर) आणि हे तिन्ही गेट्स
            # मिळून — Credit Spread व Naked दोन्हीला एकच, सामायिक सिग्नल (वेगळे गेट्स नाहीत).
            st.markdown("---")
            sub_header("🔍 Entry Refinement (ऐच्छिक Confluence गेट्स)", HDR_PINK)
            st.caption("तिन्ही डीफॉल्ट बंद — सक्रिय केल्यास, त्या गेटची अट पूर्ण झाली तरच entry घेतली जाते (RSI Gate नंतर लगेच, Credit Spread + Naked दोन्हींना एकत्र लागू).")

            sw1, sw2 = st.columns([1, 2])
            with sw1:
                swing_confluence_enabled = st.checkbox(
                    "Swing High/Low Confluence", value=bool(settings.get("swing_confluence_enabled", False)),
                    key=_widget_key(strategy_key, symbol, "swing_confluence_enabled"),
                )
            with sw2:
                st.caption("touch झालेला level हा नुकत्याच झालेल्या खऱ्या (confirmed) Swing Low/High च्या जवळ असावा — वापरकर्त्याने प्रत्यक्ष चार्टवरून दाखवलेल्या \"major swings only\" कल्पनेप्रमाणे, खालचे दोन्ही पॅरामीटर्स किरकोळ (noise) स्विंग्स आपोआप गाळतात.")
            sw3, sw4, sw5 = st.columns(3)
            with sw3:
                swing_tolerance_pct = _number_input(
                    "Swing Tolerance %", settings, "swing_tolerance_pct", strategy_key, symbol,
                    min_value=0.05, max_value=1.0, step=0.05, format="%.2f", disabled=not swing_confluence_enabled,
                )
            with sw4:
                swing_order = _number_input(
                    "Swing Order (bars दोन्ही बाजूला)", settings, "swing_order", strategy_key, symbol,
                    min_value=2, max_value=10, step=1, disabled=not swing_confluence_enabled,
                )
            with sw5:
                swing_min_move_pct = _number_input(
                    "Major Swing किमान % हालचाल", settings, "swing_min_move_pct", strategy_key, symbol,
                    min_value=0.0, max_value=5.0, step=0.1, format="%.1f", disabled=not swing_confluence_enabled,
                )

            ds1, ds2 = st.columns([1, 2])
            with ds1:
                demand_supply_gate_enabled = st.checkbox(
                    "Demand/Supply Zone", value=bool(settings.get("demand_supply_gate_enabled", False)),
                    key=_widget_key(strategy_key, symbol, "demand_supply_gate_enabled"),
                )
            with ds2:
                st.caption("touch झालेला level Demand Zone (Support) / Supply Zone (Resistance) च्या आतच असावा.")

            tl1, tl2 = st.columns([1, 2])
            with tl1:
                trendline_gate_enabled = st.checkbox(
                    "Trendline (BROKEN नसावी)", value=bool(settings.get("trendline_gate_enabled", False)),
                    key=_widget_key(strategy_key, symbol, "trendline_gate_enabled"),
                )
            with tl2:
                st.caption("त्याच दिशेची trendline (Ascending Support/Descending Resistance) अस्तित्वात असून BROKEN असेल, तरच अडवते.")
            trendline_lookback_swings = _number_input(
                "Trendline Lookback Swings", settings, "trendline_lookback_swings", strategy_key, symbol,
                min_value=3, max_value=8, step=1, disabled=not trendline_gate_enabled,
            )

        st.markdown("---")
        sub_header("🔺 Long With Hedge (Naked Option Trade)", HDR_GREEN)
        st.caption("त्याच सिग्नलवर, Credit Spread सोबतच, समांतर घेतला जातो. डीफॉल्ट: hedge नाही (निव्वळ ITM खरेदी) — हवं असल्यास हेजिंग सक्रिय करा.")
        n0, n1 = st.columns(2)
        with n0:
            naked_enabled = st.checkbox("Naked Option Trade सक्रिय", value=bool(settings.get("naked_enabled", True)), key=_widget_key(strategy_key, symbol, "naked_enabled"))
        with n1:
            naked_hedge_enabled = st.checkbox("Hedge जोडा (Debit Spread) — डीफॉल्ट बंद", value=bool(settings.get("naked_hedge_enabled", False)), key=_widget_key(strategy_key, symbol, "naked_hedge_enabled"))
        n2, n3 = st.columns(2)
        with n2:
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — आधी Naked Option Trade नेहमी वरच्याच Credit Spread
            # "Lots" इतकेच lots घ्यायचा (वेगळं सेटिंगच नव्हतं) — दोन्ही वेगळ्या जोखीम/भांडवल-गरजेचे
            # trade-प्रकार असल्याने आता स्वतंत्रपणे ठरवता येतं.
            naked_lots = _number_input("Naked Option — Lots (Credit Spread पासून स्वतंत्र)", settings, "naked_lots", strategy_key, symbol, min_value=1, max_value=50, step=1)
        with n3:
            naked_hedge_width_points = _number_input("Naked Hedge Width (points, hedge सक्रिय असेल तरच)", settings, "naked_hedge_width_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)

    with tab_exit:
        sub_header("🎯 SL / TSL / Target (Credit Spread)", HDR_AMBER)
        if strategy_key in ("1m_instant", "classic_sr_reversal"):
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
        sub_header("🎯 SL / TSL / Target (Naked Option)", HDR_CYAN)
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

        st.markdown("---")
        sub_header("📈 Trailing Stop Loss (Premium Points, सतत)", HDR_PURPLE)
        # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("user defined trailing stop loss for all
        # strategies") — डीफॉल्ट TSL Activation गाठल्यावर SL कायमचा Entry/Breakeven वर अडकतो. इथे
        # चालू केल्यास, त्याऐवजी SL नफ्याच्या मागे-मागे (Peak Premium Points - खालचं अंतर) सतत
        # सरकत राहतो — कधीच Breakeven पेक्षा सैल होत नाही. डीफॉल्ट बंद (जुनं वर्तन कायम).
        st.caption("TSL Activation (वर) गाठल्यावर लागू — चालू केल्यास SL Breakeven वर न अडकता, नफ्याच्या मागे-मागे (Peak Premium Points - खालचं Trailing Distance) सतत सरकत राहतो.")
        tsl1, tsl2 = st.columns(2)
        with tsl1:
            spread_trailing_sl_enabled = st.checkbox(
                "Credit Spread — Trailing SL सक्रिय", value=bool(settings.get("spread_trailing_sl_enabled", False)),
                key=_widget_key(strategy_key, symbol, "spread_trailing_sl_enabled"),
            )
            spread_trailing_distance_points = _number_input(
                "Credit Spread — Trailing Distance (Premium Points)", settings, "spread_trailing_distance_points",
                strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0, disabled=not spread_trailing_sl_enabled,
            )
        with tsl2:
            naked_trailing_sl_enabled = st.checkbox(
                "Naked Option — Trailing SL सक्रिय", value=bool(settings.get("naked_trailing_sl_enabled", False)),
                key=_widget_key(strategy_key, symbol, "naked_trailing_sl_enabled"),
            )
            naked_trailing_distance_points = _number_input(
                "Naked Option — Trailing Distance (Premium Points)", settings, "naked_trailing_distance_points",
                strategy_key, symbol, min_value=1.0, max_value=200.0, step=1.0, disabled=not naked_trailing_sl_enabled,
            )

        if strategy_key == "15m_dynamic_sr":
            e1, e2 = st.columns(2)
            with e1:
                naked_eod_hour = _number_input("Naked EOD तास (24-तास)", settings, "naked_eod_hour", strategy_key, symbol, min_value=9, max_value=15, step=1)
            with e2:
                naked_eod_minute = _number_input("Naked EOD मिनिट", settings, "naked_eod_minute", strategy_key, symbol, min_value=0, max_value=59, step=5)

    with tab_mode:
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("PAPER/LIVE टॉगल + broker selection, प्रत्येक strategy
        # साठी स्वतंत्र, जेणेकरून भविष्यात हळूहळू LIVE trading सुरू करता येईल") — आधी bot scripts मध्ये
        # trading_mode="PAPER" hardcoded होतं, आणि broker निवड नव्हतीच (कुठलाही account नोंदवला की
        # आपोआप सर्व सक्रिय accounts वर replicate व्हायचं). आता दोन्ही इथूनच, strategy+symbol निहाय.
        # 🎓 वापरकर्त्याने मागितलेली, नवीन-वापरकर्ता-सुलभ सुधारणा — पायरी-निहाय मांडणी + शेवटी
        # "सध्या सेव्ह केलं तर काय होईल" हा स्पष्ट सारांश, जेणेकरून एखादा नवीन वापरकर्ताही न गोंधळता
        # हे पान वापरू शकेल.
        st.info(f"सध्या तुम्ही **{STRATEGY_LABELS[strategy_key]}** ({symbol}) साठी सेटिंग्ज बदलताय — इतर strategies/symbols यावर परिणाम होणार नाही.")

        sub_header("पायरी १ — Trading Mode (PAPER / LIVE)", HDR_ORANGE)
        st.caption("PAPER = फक्त सराव/सिम्युलेशन, खरे पैसे अजिबात वापरले जात नाहीत. LIVE = खरे पैसे, खरे ऑर्डर्स — हा bot VPS वर आपोआप (दर काही मिनिटांनी) चालतो.")
        trading_mode_choice = st.radio(
            "मोड निवडा", ["📝 PAPER (सराव, सुरक्षित — शिफारस)", "🔴 LIVE (खरे पैसे)"],
            index=0 if settings.get("trading_mode", "PAPER") != "LIVE" else 1,
            key=_widget_key(strategy_key, symbol, "trading_mode_radio"), horizontal=True,
            help="नवीन असाल तर PAPER वरच ठेवा. काही दिवस Performance पानावर निकाल बघून, समाधान झाल्यावरच LIVE करा.",
        )
        trading_mode_selected = "LIVE" if "LIVE" in trading_mode_choice else "PAPER"
        live_confirmed = True
        if trading_mode_selected == "LIVE":
            live_confirmed = st.checkbox(
                f"मला समजते — {STRATEGY_LABELS[strategy_key]} ({symbol}) आता खऱ्या पैशांनी, VPS वर आपोआप (कुठलाही manual क्लिक न करता) ट्रेड करेल",
                value=False, key=_widget_key(strategy_key, symbol, "trading_mode_confirm"),
            )
            if not live_confirmed:
                st.warning("⚠️ वरील पुष्टीकरण टिक केल्याशिवाय जतन केलं तरी मोड PAPER वरच राहील (सुरक्षिततेसाठी) — हा एक जाणीवपूर्वक निर्णय असायला हवा.")

        st.markdown("---")
        sub_header("पायरी २ — Broker Account (ऐच्छिक)", HDR_TEAL)
        st.caption(
            "हे पूर्णपणे ऐच्छिक आहे — **रिकामं ठेवलं तर काहीही करावं लागत नाही**, नेहमीप्रमाणे तुमच्या "
            "मुख्य Upstox खात्यावरच एकच trade उघडला जातो. फक्त तुम्हाला या strategy साठी वेगळं (किंवा "
            "अनेक) broker खातं वापरायचं असेल, तरच इथून निवडा."
        )
        accounts_df = cloud_db.get_all_broker_accounts(active_only=False)
        if accounts_df is None or accounts_df.empty:
            st.info("💡 कुठलेही broker accounts अजून नोंदवलेले नाहीत — त्यामुळे सध्या नेहमी शुद्ध Upstox वापरला जाईल (हेच बरोबर आहे, जोपर्यंत तुम्हाला वेगळा broker वापरायचा नाही). वेगळा broker हवा असल्यास आधी \"Broker Accounts\" पानावरून तो नोंदवा, मग इथे परत या.")
            broker_account_ids = []
        else:
            account_options = {
                row["account_id"]: f"{row['nickname'] or row['account_id']} ({row['broker_type']})" + ("" if row["is_active"] else " ⚪ निष्क्रिय")
                for _, row in accounts_df.iterrows()
            }
            current_selection = [aid for aid in (settings.get("broker_account_ids") or []) if aid in account_options]
            broker_account_ids = st.multiselect(
                "Broker Account(s) — एक किंवा अनेक निवडा (तुमच्या भांडवलानुसार)", list(account_options.keys()),
                default=current_selection, format_func=lambda aid: account_options[aid],
                key=_widget_key(strategy_key, symbol, "broker_account_ids"),
                help="एकही निवडलं नाही तर शुद्ध Upstox (डीफॉल्ट). एक निवडलं तर तेवढ्याच खात्यावर trade होईल. अनेक निवडली तर प्रत्येकावर स्वतंत्र trade — प्रत्येकाचं SL/TSL/Target स्वतंत्रपणे त्याच broker वर सांभाळलं जातं.",
            )
            st.caption("(Signal-गणना — candles/RSI/S-R levels — नेहमीच Upstox वरूनच होते; फक्त प्रत्यक्ष ऑर्डर निवडलेल्या broker कडे जातो.)")

        st.markdown("---")
        # 🎓 "सध्या सेव्ह केलं तर काय होईल" — widget च्या आत्ताच्या (अजून जतन न केलेल्या) स्थितीवरून थेट,
        # जेणेकरून वापरकर्त्याला Save दाबण्याआधीच नेमका परिणाम कळेल.
        effective_mode = trading_mode_selected if (trading_mode_selected == "PAPER" or live_confirmed) else "PAPER"
        if broker_account_ids:
            broker_summary = f"{len(broker_account_ids)} निवडलेल्या broker account(s) वर ({', '.join(account_options[aid] for aid in broker_account_ids)})"
        else:
            broker_summary = "तुमच्या मुख्य Upstox खात्यावर"
        if effective_mode == "LIVE":
            st.error(f"📋 **सारांश** — 'Settings जतन करा' दाबल्यावर: {STRATEGY_LABELS[strategy_key]} ({symbol}) 🔴 **LIVE** — {broker_summary}, खऱ्या पैशांनी ट्रेड करेल.")
        else:
            st.success(f"📋 **सारांश** — 'Settings जतन करा' दाबल्यावर: {STRATEGY_LABELS[strategy_key]} ({symbol}) 📝 **PAPER** — {broker_summary}, फक्त सिम्युलेशन (सुरक्षित).")

    st.markdown("---")
    if st.button("💾 Settings जतन करा", key="bdsr_save_btn", type="primary"):
        new_settings = {
            "symbol_enabled": bool(symbol_enabled),
            "lots": int(lots), "itm_depth_points": float(itm_depth_points), "hedge_width_points": float(hedge_width_points),
            "entry_rsi_gate_enabled": bool(entry_rsi_gate_enabled),
            "spread_sl_spot_pct": float(spread_sl_spot_pct), "spread_sl_premium_points": float(spread_sl_premium_points),
            "spread_tsl_spot_pct": float(spread_tsl_spot_pct), "spread_tsl_premium_points": float(spread_tsl_premium_points),
            "naked_enabled": bool(naked_enabled), "naked_lots": int(naked_lots), "naked_hedge_enabled": bool(naked_hedge_enabled),
            "naked_hedge_width_points": float(naked_hedge_width_points),
            "naked_sl_spot_pct": float(naked_sl_spot_pct), "naked_sl_premium_points": float(naked_sl_premium_points),
            "naked_tsl_spot_pct": float(naked_tsl_spot_pct), "naked_tsl_premium_points": float(naked_tsl_premium_points),
            "naked_target_spot_pct": float(naked_target_spot_pct), "naked_target_premium_points": float(naked_target_premium_points),
            "spread_trailing_sl_enabled": bool(spread_trailing_sl_enabled), "spread_trailing_distance_points": float(spread_trailing_distance_points),
            "naked_trailing_sl_enabled": bool(naked_trailing_sl_enabled), "naked_trailing_distance_points": float(naked_trailing_distance_points),
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — LIVE निवडलं तरी पुष्टीकरण टिक केलेलं नसेल, तर
            # सुरक्षिततेसाठी PAPER वरच जतन होतं (शांतपणे LIVE जतन होऊन खरे ऑर्डर्स सुरू होता कामा नयेत).
            "trading_mode": trading_mode_selected if (trading_mode_selected == "PAPER" or live_confirmed) else "PAPER",
            "broker_account_ids": broker_account_ids,
        }
        # 🎓 classic_sr_reversal साठी PCR गेट मुद्दामच नाही (वर पहा) — त्यामुळे हे fields save करायचे नाहीत.
        if strategy_key != "classic_sr_reversal":
            new_settings["entry_pcr_gate_enabled"] = bool(entry_pcr_gate_enabled)
            new_settings["pcr_bullish_min"] = float(pcr_bullish_min)
            new_settings["pcr_bearish_max"] = float(pcr_bearish_max)

        if strategy_key == "1m_instant":
            new_settings["timeframe_choice"] = timeframe_choice
            new_settings["rsi_support_max"] = int(rsi_support_max)
            new_settings["rsi_resistance_min"] = int(rsi_resistance_min)
            new_settings["spread_target_spot_pct"] = float(spread_target_spot_pct)
            new_settings["spread_target_premium_points"] = float(spread_target_premium_points)
        elif strategy_key == "classic_sr_reversal":
            new_settings["timeframe_choice"] = timeframe_choice
            new_settings["rsi_neutral_level"] = int(rsi_neutral_level)
            new_settings["spread_target_spot_pct"] = float(spread_target_spot_pct)
            new_settings["spread_target_premium_points"] = float(spread_target_premium_points)
            new_settings["swing_confluence_enabled"] = bool(swing_confluence_enabled)
            new_settings["swing_tolerance_pct"] = float(swing_tolerance_pct)
            new_settings["swing_order"] = int(swing_order)
            new_settings["swing_min_move_pct"] = float(swing_min_move_pct)
            new_settings["demand_supply_gate_enabled"] = bool(demand_supply_gate_enabled)
            new_settings["trendline_gate_enabled"] = bool(trendline_gate_enabled)
            new_settings["trendline_lookback_swings"] = int(trendline_lookback_swings)
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
