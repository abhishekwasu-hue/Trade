"""
शेअर्ड सेटअप — Sidebar (सर्व सेटिंग्ज) + Option Chain fetch, जे प्रत्येक page लोड होण्याआधी एकदाच चालतं.
सर्व निकाल st.session_state मध्ये साठवले जातात जेणेकरून प्रत्येक स्वतंत्र page त्यांना वाचू शकेल.
"""
import datetime
import streamlit as st

from upstox_api import fetch_upstox_option_chain, fetch_candles
try:
    from signals import compute_atr
except ImportError:
    # deployed signals.py जुनी असेल (compute_atr गहाळ) तर संपूर्ण app क्रॅश होण्याऐवजी,
    # फक्त Trailing SL feature बंद राहील — बाकी सर्व व्यवस्थित चालेल.
    compute_atr = None
from trading_engine import manage_open_trades


def setup_shared_context():
    st.sidebar.title("⚙️ डॅशबोर्ड सेटिंग्ज")
    symbol = st.sidebar.selectbox("इंडेक्स निवडा:", ["NIFTY", "BANKNIFTY", "SENSEX"])

    # --- नवीन टाइमफ्रेम निवडण्याची सुविधा ---
    timeframe_option = st.sidebar.selectbox("चार्ट टाईमफ्रेम (Timeframe):", ["1minute", "15minute", "30minute", "1hour", "day"], index=2)

    # --- चार्ट टाईप निवडण्याची सुविधा (Candlestick / Line) ---
    chart_type = st.sidebar.radio("चार्ट टाईप:", ["Candlestick", "Line"], index=0, horizontal=True)


    secrets_token = ""
    try:
        if "upstox" in st.secrets and "access_token" in st.secrets["upstox"]:
            secrets_token = st.secrets["upstox"]["access_token"]
    except Exception:
        pass  # secrets.toml अस्तित्वात नसेल तर st.secrets स्वतःच exception देतो — तेव्हा manual token entry वर पडणे

    token_input = st.sidebar.text_input("Upstox Access Token:", value=secrets_token, type="password")
    auto_refresh = st.sidebar.checkbox("ऑटो-रिफ्रेश (5 Minutes)", value=True)

    # --- ६.५ A1 स्ट्रॅटेजी व लाईव्ह एक्झिक्युशन सेटिंग्ज ---
    st.sidebar.markdown("---")
    st.sidebar.title("🎯 A1 Strategy Engine सेटिंग्ज")
    with st.sidebar.expander("🎯 A1 Strategy सेटिंग्ज (Lot/Risk/OI Gates/Signal Engine — क्लिक करून उघडा)", expanded=False):
        lot_size = st.sidebar.number_input("Lot Size (सध्या NIFTY = 65, अधिकृत NSE सर्क्युलर तपासा)", min_value=1, value=65, step=1)
        risk_pct_per_trade = st.sidebar.slider("Risk % per Trade (उपलब्ध मार्जिनपैकी)", 0.5, 10.0, 2.0, step=0.5)
        hedge_width_points = st.sidebar.number_input("Hedge Width (points, लाँग लेग शॉर्ट लेगपासून किती दूर)", min_value=50, value=100, step=50)
        pop_threshold_pct = st.sidebar.slider("PoP Threshold (%) — किमान Probability of Profit", 50, 95, 70, step=5)
        vix_max_threshold = st.sidebar.number_input("India VIX कमाल मर्यादा (यापेक्षा जास्त = No Trade)", min_value=10.0, value=20.0, step=0.5)

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — Price Action/Indicator (आपल्या २ मुख्य
        # strategies) साठी SL/Target आता निश्चित (fixed) 30%/30% (net_credit चे) आहेत, sidebar वरून
        # बदलता येत नाहीत (हार्डकोड). खालचे sliders आता फक्त Iron Condor/Butterfly (sideways) साठीच.
        st.sidebar.markdown("##### 🦋 Sideways (Iron Condor / Butterfly) सेटिंग्ज")
        st.sidebar.caption("⚠️ खालचे SL/Target फक्त Iron Condor/Butterfly साठी — Price Action/Indicator आता निश्चित 30% credit SL/Target वापरतात.")
        sl_pct_of_max_loss = st.sidebar.slider("Sideways SL (% of Max Loss)", 10, 100, 30, step=5)
        target_pct_of_max_profit = st.sidebar.slider("Sideways Profit Target (% of Max Profit)", 10, 100, 50, step=5)
        sideways_tight_range_pct = st.sidebar.number_input("घट्ट रेंज मर्यादा % (यापेक्षा कमी = Iron Butterfly)", min_value=0.1, value=0.6, step=0.1)
        sideways_max_range_pct = st.sidebar.number_input("कमाल Sideways रेंज % (यापेक्षा जास्त = अजिबात Sideways ट्रेड नाही)", min_value=0.5, value=1.5, step=0.1)
        st.sidebar.markdown("##### ⏱️ Trading Style")
        trading_style_choice = st.sidebar.radio(
            "Intraday की Swing?",
            ["⚡ Intraday (त्याच दिवशी स्क्वेअर-ऑफ)", "🌙 Swing (एक दिवसापेक्षा जास्त काळ होल्ड)"],
            index=0,
        )
        trading_style = "INTRADAY" if "Intraday" in trading_style_choice else "SWING"

        if trading_style == "INTRADAY":
            # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — Price Action/Indicator strategies आहे
            # तशाच (timeframes/logic सह) ठेवल्या, पण आता EOD Square-off होत नाही आणि product_type
            # "D" (Delivery/Carry-Forward) आहे — जेणेकरून position प्रत्यक्षात दुसऱ्या दिवशीही टिकेल
            # (आधी "I" (Intraday margin) होता — तो असता तर ब्रोकरच स्वतःहून त्याच दिवशी बंद करायचा,
            # आपला कोड EOD काढला तरी काही फरक पडला नसता).
            product_type = "D"
            eod_squareoff_time = None
            entry_cutoff_time = st.sidebar.time_input("नवीन एंट्री बंद करण्याची वेळ (IST)", value=datetime.time(15, 0))
            st.sidebar.caption(
                f"⚠️ EOD Square-off काढलं आहे — Position आता दुसऱ्या दिवशीही Continue राहील (Product Type "
                f"आपोआप 'D'/Delivery). नवीन एंट्री मात्र {entry_cutoff_time.strftime('%H:%M')} नंतर बंद."
            )

            st.sidebar.markdown("##### 🧭 OI Confirmation Gate (Intraday)")
            enable_oi_gate = st.sidebar.checkbox("OI Diff Tracker सिग्नल एंट्री गेट म्हणून वापरा", value=True)
            oi_gate_strictness_choice = st.sidebar.radio(
                "Strictness",
                ["A — Conflict Filter (शिफारस केलेले)", "B — Strict Confirmation"],
                index=0,
            )
            oi_gate_strictness = "A" if "A" in oi_gate_strictness_choice else "B"
            enable_oi_early_exit = st.sidebar.checkbox("OI उलट फिरल्यास लवकर Exit करा (फक्त Directional स्प्रेड्ससाठी)", value=True)
            enable_swing_oi_gate = False
            swing_max_opposing_signals = 1

            st.sidebar.markdown("##### 🧬 Signal Engine — दिशा 1H Supertrend वरून (दोन्ही रणनीतींसाठी)")
            intraday_strategy_choice = st.sidebar.radio(
                "कोणती रणनीती वापरायची?",
                ["1️⃣ Price Action (Support/Resistance + RSI + Candlestick)",
                 "2️⃣ Indicator Based (RSI 25-55/45-75 + Rejection/Engulfing)"],
            )
            intraday_strategy_mode = "price_action" if "1️⃣" in intraday_strategy_choice else "indicator"
            sr_window = 20
            rsi_oversold = 30
            rsi_overbought = 70
            sl_buffer_pct = 0.1
            min_rr = 2.0
            retest_tolerance_pct = 0.15
            reversal_lookback = 3
            if intraday_strategy_mode == "price_action":
                st.sidebar.caption(
                    "Support/Resistance (Rolling Window) जवळ RSI Oversold/Overbought/Divergence + Reversal "
                    "Candlestick (Hammer/Engulfing/Morning-Evening Star) + त्या candle च्या high/low पलीकडे "
                    "Breakout — हे सर्व जुळल्यावरच Entry."
                )
                sr_window = st.sidebar.number_input("S/R Rolling Window", min_value=6, value=20, step=2)
                rc1, rc2 = st.sidebar.columns(2)
                with rc1:
                    rsi_oversold = st.sidebar.number_input("RSI Oversold <", min_value=5, max_value=45, value=30, step=1)
                with rc2:
                    rsi_overbought = st.sidebar.number_input("RSI Overbought >", min_value=55, max_value=95, value=70, step=1)
                sl_buffer_pct = st.sidebar.number_input("SL Buffer %", min_value=0.01, value=0.1, step=0.05)
                min_rr = st.sidebar.number_input("किमान Risk:Reward", min_value=1.0, value=2.0, step=0.5)
                retest_tolerance_pct = st.sidebar.number_input("Retest Tolerance %", min_value=0.05, value=0.15, step=0.05)
                reversal_lookback = st.sidebar.number_input("Reversal Candle Lookback (bars)", min_value=1, max_value=10, value=3, step=1)
                st.sidebar.caption(
                    "S/R Rolling Window कमी असेल तर जास्त (पण कमी विश्वासार्ह) पातळ्या सापडतील. सिग्नल्स कमी वाटत "
                    "असतील तर Retest Tolerance वाढवा किंवा RSI मर्यादा सैल करा (उदा. Oversold 35, Overbought 65)."
                )
            st.sidebar.caption(
                "A: फक्त सक्रिय विरोध (उलट दिशेचा OI) असेल तरच ब्लॉक — Weakening/Neutral पास होतात. "
                "B: फक्त पूर्ण जुळणी असेल तरच पास (कमी पण जास्त खात्रीचे ट्रेड्स)."
            )
        else:
            product_type = "D"
            eod_squareoff_time = None
            entry_cutoff_time = None
            enable_oi_gate = False
            oi_gate_strictness_choice = "A — Conflict Filter (शिफारस केलेले)"
            oi_gate_strictness = "A"
            enable_oi_early_exit = False
            intraday_strategy_mode = "indicator"
            sr_window = 20
            rsi_oversold = 30
            rsi_overbought = 70
            sl_buffer_pct = 0.1
            min_rr = 2.0
            retest_tolerance_pct = 0.15
            reversal_lookback = 3
            st.sidebar.caption("Swing मोड: Product Type आपोआप 'D' (Carryforward) — पोझिशन्स SL/Target लागेपर्यंत अनेक दिवस उघड्या राहू शकतात, कोणताही EOD स्क्वेअर-ऑफ नाही.")

            st.sidebar.markdown("##### 🧭 OI+PCR+MaxPain+Rollover Gate (Swing)")
            enable_swing_oi_gate = st.sidebar.checkbox("चारही Professional OI सिग्नल्स एंट्री गेट म्हणून वापरा", value=True)
            swing_max_opposing_signals = st.sidebar.slider(
                "कमाल विरोधी सिग्नल्स (यापेक्षा जास्त विरोध असेल तरच ब्लॉक)", min_value=0, max_value=3, value=1,
            )
            st.sidebar.caption(
                "OI-Price Matrix (day-over-day) + PCR Contrarian + Max Pain + Rollover (Cost-of-Carry) — हे चार सिग्नल्स "
                "मोजून, दिशेच्या विरोधात जाणाऱ्या सिग्नल्सची संख्या वरील मर्यादेपेक्षा जास्त असेल तरच एंट्री ब्लॉक होते. "
                "Rollover फक्त वर 'Advanced OI Analysis' मध्ये बटण दाबून fetch केलेला असेल तरच या गेटमध्ये मोजला जातो."
            )

        max_trades_per_day = st.sidebar.number_input("दिवसाला जास्तीत जास्त ट्रेड्स", min_value=1, value=3, step=1)
        max_daily_loss = st.sidebar.number_input("दैनिक कमाल तोटा ₹ (Circuit Breaker)", min_value=500, value=5000, step=500)

    st.sidebar.markdown("### 📈 Trailing SL (ATR-आधारित)")
    with st.sidebar.expander("📈 Trailing SL तपशील (क्लिक करून उघडा)", expanded=False):
        trailing_sl_enabled = False
        atr_multiplier = 1.5
        if compute_atr is None:
            st.sidebar.warning(
                "⚠️ Trailing SL उपलब्ध नाही — deployed signals.py जुनी आहे (compute_atr गहाळ). "
                "नवीनतम सर्व फाईल्स पुन्हा अपलोड करून app reboot करा."
            )
        else:
            trailing_sl_enabled = st.sidebar.checkbox(
                "Trailing SL चालू करा (सर्व स्ट्रॅटेजींसाठी — Credit Spreads सकट)", value=False,
            )
            if trailing_sl_enabled:
                atr_multiplier = st.sidebar.number_input("ATR Multiplier (ट्रेलिंग अंतर)", min_value=0.5, value=1.5, step=0.25)
                st.sidebar.caption(
                    "पोझिशन नफ्यात गेल्यावर SL नफ्याच्या दिशेने सतत सरकतो, कधीच मागे सरकत नाही — पण मूळ स्थिर SL पेक्षा "
                    "कधीच वाईट होत नाही. ATR 15M underlying candles वरून काढला जातो."
                )

    st.sidebar.markdown("### 🎮 Trading Mode")
    trading_mode_choice = st.sidebar.radio(
        "मोड निवडा", ["📝 PAPER (Simulated — खरे पैसे नाहीत)", "🔴 LIVE (Real Money)"], index=0,
    )
    trading_mode = "LIVE" if "LIVE" in trading_mode_choice else "PAPER"

    if trading_mode == "PAPER":
        enable_live_trading = True
        confirm_live_trading = True
        st.sidebar.info(
            "📝 Paper Trading Mode चालू आहे — सर्व सिग्नल्स आपोआप execute होतील, पण **कोणताही खरा ऑर्डर Upstox कडे "
            "जाणार नाही**. Entry/Exit किंमती खऱ्या मार्केट LTP वरूनच घेतल्या जातात, त्यामुळे निकाल realistic असतील."
        )
    else:
        enable_live_trading = st.sidebar.checkbox("ENABLE LIVE TRADING (खरे पैसे, खरे ऑर्डर्स)", value=False)
        confirm_live_trading = False
        if enable_live_trading:
            confirm_live_trading = st.sidebar.checkbox("मला समजते — यामुळे माझ्या खऱ्या Upstox खात्यातून खरे ऑर्डर्स प्लेस होतील", value=False)
            if not confirm_live_trading:
                st.sidebar.warning("⚠️ वरील पुष्टीकरण टिक केल्याशिवाय कोणतेही लाईव्ह ऑर्डर्स जाणार नाहीत.")

    # --- ७. मुख्य डॅशबोर्ड लॉजिक ---


    st.session_state["symbol"] = symbol
    st.session_state["timeframe_option"] = timeframe_option
    st.session_state["chart_type"] = chart_type
    st.session_state["secrets_token"] = secrets_token
    st.session_state["token_input"] = token_input
    st.session_state["auto_refresh"] = auto_refresh
    st.session_state["lot_size"] = lot_size
    st.session_state["risk_pct_per_trade"] = risk_pct_per_trade
    st.session_state["hedge_width_points"] = hedge_width_points
    st.session_state["pop_threshold_pct"] = pop_threshold_pct
    st.session_state["sl_pct_of_max_loss"] = sl_pct_of_max_loss
    st.session_state["target_pct_of_max_profit"] = target_pct_of_max_profit
    st.session_state["vix_max_threshold"] = vix_max_threshold
    st.session_state["sideways_tight_range_pct"] = sideways_tight_range_pct
    st.session_state["sideways_max_range_pct"] = sideways_max_range_pct
    st.session_state["trading_style_choice"] = trading_style_choice
    st.session_state["trading_style"] = trading_style
    st.session_state["product_type"] = product_type
    st.session_state["eod_squareoff_time"] = eod_squareoff_time
    st.session_state["entry_cutoff_time"] = entry_cutoff_time
    st.session_state["enable_oi_gate"] = enable_oi_gate
    st.session_state["oi_gate_strictness_choice"] = oi_gate_strictness_choice
    st.session_state["oi_gate_strictness"] = oi_gate_strictness
    st.session_state["enable_oi_early_exit"] = enable_oi_early_exit
    st.session_state["enable_swing_oi_gate"] = enable_swing_oi_gate
    st.session_state["swing_max_opposing_signals"] = swing_max_opposing_signals
    st.session_state["intraday_strategy_mode"] = intraday_strategy_mode
    st.session_state["sr_window"] = sr_window
    st.session_state["rsi_oversold"] = rsi_oversold
    st.session_state["rsi_overbought"] = rsi_overbought
    st.session_state["sl_buffer_pct"] = sl_buffer_pct
    st.session_state["min_rr"] = min_rr
    st.session_state["retest_tolerance_pct"] = retest_tolerance_pct
    st.session_state["reversal_lookback"] = reversal_lookback
    st.session_state["max_trades_per_day"] = max_trades_per_day
    st.session_state["max_daily_loss"] = max_daily_loss
    st.session_state["trailing_sl_enabled"] = trailing_sl_enabled
    st.session_state["atr_multiplier"] = atr_multiplier
    st.session_state["trading_mode_choice"] = trading_mode_choice
    st.session_state["trading_mode"] = trading_mode
    st.session_state["enable_live_trading"] = enable_live_trading
    st.session_state["confirm_live_trading"] = confirm_live_trading

    # --- Option Chain Fetch + यशस्वी झाल्यास मूळ किंमत/ATM काढणे ---
    if not token_input.strip():
        return False

    raw_chain, status_msg = fetch_upstox_option_chain(token_input, symbol)
    st.session_state["raw_chain"] = raw_chain
    st.session_state["status_msg"] = status_msg

    if status_msg == "SUCCESS" and raw_chain:
        underlying_price = raw_chain[0].get("underlying_spot_price", 0) if raw_chain else 0
        step = 50 if symbol == "NIFTY" else 100
        atm_strike = round(underlying_price / step) * step if underlying_price > 0 else 0
        st.session_state["underlying_price"] = underlying_price
        st.session_state["step"] = step
        st.session_state["atm_strike"] = atm_strike

        # --- उघड्या ट्रेड्सचे SL/Target/EOD मॉनिटरिंग — इथे (shared_context) ठेवलेलं आहे, page_dashboard.py
        # मध्ये नाही, कारण हे प्रत्येक page-load वर चालायला हवं (Positions/Orders/Performance वर असतानाही),
        # आधी हे फक्त Dashboard page उघडी असतानाच चालायचं — म्हणजे इतर pages वर असताना EOD/SL/Target
        # अजिबात तपासलेच जात नव्हते, हा गंभीर gap होता.
        if enable_live_trading and confirm_live_trading:
            eod_hour = eod_squareoff_time.hour if eod_squareoff_time else 15
            eod_minute = eod_squareoff_time.minute if eod_squareoff_time else 15

            atr_points = None
            if trailing_sl_enabled:
                try:
                    df_for_atr = fetch_candles(token_input, symbol, underlying_price, interval="15minute", lookback_days=5)
                    atr_points = compute_atr(df_for_atr, period=14) if not df_for_atr.empty else None
                except Exception:
                    atr_points = None  # ATR मिळालं नाही तर ट्रेलिंग सक्रिय होणार नाही, मूळ स्थिर SL तसाच वापरला जाईल

            closed_now = manage_open_trades(
                token_input, symbol, product_type, eod_squareoff_hour=eod_hour, eod_squareoff_minute=eod_minute,
                oi_reversal_exit_enabled=enable_oi_early_exit,
                trailing_sl_enabled=trailing_sl_enabled, atr_points=atr_points, atr_multiplier=atr_multiplier,
            )
            for c in closed_now:
                emoji = "🟢" if c["pnl"] > 0 else "🔴"
                mode_tag = "📝" if c.get("mode") == "PAPER" else "💰"
                st.toast(f"{emoji}{mode_tag} Trade {c['trade_id']} बंद झाला ({c['reason']}) — P&L: ₹{c['pnl']:,.0f}")

        return True

    return False
