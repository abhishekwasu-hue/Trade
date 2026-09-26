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
import upstox_api
from config import get_ist_today
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_PINK, HDR_GREEN, HDR_AMBER, HDR_CYAN

SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]
STRATEGY_LABELS = {
    "1m_instant": "5-मिनिट Instant Trader (1M + 5M)",
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
        (strategy_key, symbol, info.get("trading_mode")) for (strategy_key, symbol), info in all_modes.items()
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("LIVE" ऐवजी "LIVE+PAPER" mode) — LIVE_PAPER मध्येही
        # खराच पैसा वापरला जातो (सोबत फक्त तुलनेसाठी एक शॅडो PAPER trade), त्यामुळे हा banner LIVE
        # प्रमाणेच LIVE_PAPER लाही दाखवतो.
        if info.get("trading_mode") in ("LIVE", "LIVE_PAPER")
    ]
    if live_combos:
        lines = "; ".join(
            f"**{STRATEGY_LABELS.get(sk, sk)} ({sym})** ({'LIVE+PAPER' if mode == 'LIVE_PAPER' else 'LIVE'})"
            for sk, sym, mode in live_combos
        )
        st.error(f"🔴 सध्या LIVE (खऱ्या पैशांनी) चालू आहे: {lines}")
    else:
        st.success("🟢 सर्व strategies सध्या PAPER मोडमध्ये आहेत — कुठलाही खरा पैसा वापरला जात नाही.")


def _render_kill_switch_panel():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — तिन्ही bots साठी एकत्रित, संपूर्ण-खात्यासाठीचं (per-strategy/symbol
    नाही) सुरक्षा-सेटिंग. आजचा एकूण LIVE तोटा किंवा ट्रेड-संख्या इथल्या मर्यादेपलीकडे गेली, तर पुढचे
    सर्व LIVE trades (कुठल्याही bot/symbol चे) trading_engine.open_multi_leg_trade() कडूनच आपोआप
    थांबतात (PAPER trades वर कुठलाही परिणाम नाही).
    🎓 वापरकर्त्याने मागितलेली सुधारणा ("Kill switch madhe loss limit... ekun capital chya respected
    te asayla pahije both loss and profit, certain profit book jhalyanantr, automatic trading stop
    karne awashyak") — max_daily_loss/max_daily_profit आता flat ₹ ऐवजी **एकूण capital च्या %**
    (capital = Upstox कडून available_margin + used_margin, trading_engine.check_kill_switch() मध्येच
    प्रत्यक्ष वेळी काढलं जातं). इथे फक्त preview/display साठी तोच आकडा वापरला आहे. नवीन — नफ्याची
    बाजूही (max_daily_profit_pct) — ठराविक नफा गाठल्यावर उरलेल्या दिवसासाठी नवीन LIVE trades आपोआप
    थांबतात."""
    ks_settings = cloud_db.get_kill_switch_settings()
    total_pnl, total_trades = database.get_todays_live_total_pnl_and_count()
    token_input = st.session_state.get("token_input", "")
    total_capital = upstox_api.get_total_capital(token_input) if token_input else None
    max_daily_loss_amount = (total_capital * ks_settings["max_daily_loss_pct"] / 100) if total_capital else None
    max_daily_profit_amount = (total_capital * ks_settings["max_daily_profit_pct"] / 100) if total_capital else None

    with st.expander("🛑 LIVE Kill Switch (सर्व Bots + Dashboard साठी एकत्रित)", expanded=False):
        st.caption(
            "आजचा एकूण खऱ्या पैशांचा (LIVE) तोटा किंवा नफा (दोन्ही — एकूण capital च्या % म्हणून) किंवा "
            "ट्रेड-संख्या इथल्या मर्यादेपलीकडे गेली, तर तिन्ही bots + Dashboard कडून पुढचे कुठलेही "
            "नवीन LIVE trade घेतले जाणार नाहीत (PAPER trades नेहमीप्रमाणेच चालू राहतील) — जोपर्यंत "
            "तुम्ही स्वतः इथून सेटिंग्ज बदलत नाही. नफ्याची मर्यादा मुद्दाम — आजचा नफा आधीच लक्ष्य "
            "गाठलेला असेल, तर तो परत \"दिला\" जाऊ नये म्हणून."
        )
        if total_capital is None:
            st.warning(
                "⚠️ एकूण capital (Upstox Funds & Margin वरून) सध्या मिळालं नाही — token/नेटवर्क तपासा. "
                "खरी trading वेळी हेच कारण असेल, तर Kill Switch सुरक्षिततेसाठी नवीन LIVE trades आपोआप थांबवतो."
            )
        else:
            st.caption(f"सध्याचं एकूण capital (Upstox, available+used margin): ₹{total_capital:,.0f}")

        peak_pnl_today = database.get_todays_live_peak_pnl()
        locked_floor = (peak_pnl_today * ks_settings["profit_lock_pct"] / 100) if peak_pnl_today > 0 else None
        profit_locked_tripped = (
            ks_settings["profit_lock_enabled"] and locked_floor is not None and total_pnl < locked_floor
        )
        tripped = ks_settings["enabled"] and (
            total_capital is None
            or total_pnl <= -max_daily_loss_amount
            or total_pnl >= max_daily_profit_amount
            or profit_locked_tripped
            or total_trades >= ks_settings["max_trades_per_day"]
        )
        if not ks_settings["enabled"]:
            st.warning("⚪ Kill Switch सध्या बंद आहे — LIVE ट्रेड्सवर कुठलीही स्वयंचलित मर्यादा नाही.")
        elif tripped:
            if profit_locked_tripped and not (total_capital is None or total_pnl <= -max_daily_loss_amount or total_pnl >= max_daily_profit_amount):
                st.error(
                    f"🔴 Profit-Lock Kill Switch ट्रिप झालं आहे — आजचा सर्वोच्च LIVE नफा ₹{peak_pnl_today:,.0f} होता, "
                    f"त्यातला {ks_settings['profit_lock_pct']:.0f}% (₹{locked_floor:,.0f}) लॉक होता, सद्य नफा ₹{total_pnl:,.0f} "
                    f"त्याखाली घसरला. नवीन LIVE trade ब्लॉक केला जातोय."
                )
            else:
                st.error(f"🔴 Kill Switch ट्रिप झालं आहे — आजचा एकूण LIVE P&L ₹{total_pnl:,.0f}, ट्रेड्स {total_trades}. नवीन LIVE trade ब्लॉक केला जातोय.")
        else:
            lock_caption = f", profit-lock मजला ₹{locked_floor:,.0f}" if ks_settings["profit_lock_enabled"] and locked_floor is not None else ""
            st.success(
                f"🟢 Kill Switch OK — आजचा एकूण LIVE P&L ₹{total_pnl:,.0f} (तोटा-मर्यादा ₹{-max_daily_loss_amount:,.0f}, "
                f"नफा-लक्ष्य ₹{max_daily_profit_amount:,.0f}{lock_caption}), ट्रेड्स {total_trades}/{ks_settings['max_trades_per_day']}."
            )

        ks_enabled = st.checkbox("Kill Switch सक्रिय", value=ks_settings["enabled"], key="bdsr_ks_enabled")
        c1, c2, c3 = st.columns(3)
        with c1:
            ks_max_loss_pct = st.number_input(
                "कमाल दैनिक तोटा % (एकूण capital चा)", min_value=0.1, max_value=100.0,
                value=float(ks_settings["max_daily_loss_pct"]), step=0.5, key="bdsr_ks_max_loss_pct",
            )
        with c2:
            ks_max_profit_pct = st.number_input(
                "दैनिक नफा-लक्ष्य % (एकूण capital चा)", min_value=0.1, max_value=100.0,
                value=float(ks_settings["max_daily_profit_pct"]), step=0.5, key="bdsr_ks_max_profit_pct",
            )
        with c3:
            ks_max_trades = st.number_input(
                "कमाल दैनिक LIVE ट्रेड्स (सर्व bots मिळून)", min_value=1,
                value=int(ks_settings["max_trades_per_day"]), step=1, key="bdsr_ks_max_trades",
            )
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("1 trade profit मध्ये exit जाला, दुसरा उघडा
        # असेल, तर काही नफा नेहमी लॉक व्हावा, जेणेकरून नफ्यातून तोटा होणार नाही") — डीफॉल्ट बंद,
        # वरच्या स्थिर नफा-लक्ष्यापेक्षा वेगळं, गतिशील (ratchet) संरक्षण.
        st.caption(
            "🔒 Profit-Lock (ऐच्छिक) — दिवसभरात कधीही गाठलेल्या सर्वोच्च नफ्यातला ठराविक % कायमचा "
            "\"मजला\" म्हणून लॉक होतो (वरच्या स्थिर नफा-लक्ष्याआधीही) — सद्य नफा त्याखाली घसरला की "
            "नवीन LIVE trades थांबतात. आधीच उघडे trades यामुळे कधीच जबरदस्तीने बंद होत नाहीत."
        )
        pc1, pc2 = st.columns(2)
        with pc1:
            ks_profit_lock_enabled = st.checkbox(
                "Profit-Lock सक्रिय", value=ks_settings["profit_lock_enabled"], key="bdsr_ks_profit_lock_enabled",
            )
        with pc2:
            ks_profit_lock_pct = st.number_input(
                "लॉक करायचा % (आजच्या सर्वोच्च नफ्यापैकी)", min_value=1.0, max_value=99.0,
                value=float(ks_settings["profit_lock_pct"]), step=5.0, key="bdsr_ks_profit_lock_pct",
            )
        if st.button("💾 Kill Switch सेव्ह करा", key="bdsr_ks_save_btn"):
            ok = cloud_db.save_kill_switch_settings(
                ks_enabled, ks_max_loss_pct, ks_max_profit_pct, ks_max_trades,
                ks_profit_lock_enabled, ks_profit_lock_pct,
            )
            if ok:
                st.success("✅ Kill Switch सेटिंग्ज जतन झाल्या.")
            else:
                st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")


def _render_vix_spike_halt_panel():
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("India VIX ने पहिल्या 5 मिनिटांत ठराविक% level
    क्रॉस केली तर त्या दिवशी NIFTY साठी bot ने trading थांबवावी") — फक्त NIFTY साठी, फक्त LIVE
    (PAPER trades वर परिणाम नाही). check_vix_spike_halt.py (सकाळी 9:20 IST cron, बाजार उघडून ~5
    मिनिटांनी) रोज एकदा तपासून आजचा निकाल साठवतं — इथे तोच निकाल + enabled/threshold सेटिंग्ज
    दाखवली/बदलता येतात (established Kill Switch पॅनेलसारखंच)."""
    vh_settings = cloud_db.get_vix_spike_halt_settings()
    today_str = get_ist_today().strftime("%Y-%m-%d")

    with st.expander("🌪️ India VIX Spike Halt (फक्त NIFTY, फक्त LIVE)", expanded=False):
        st.caption(
            "सकाळी 9:20 IST ला (बाजार उघडून ~5 मिनिटांनी) India VIX आदल्या दिवसाच्या close च्या "
            "तुलनेत किती% बदलला हे एकदाच तपासलं जातं (check_vix_spike_halt.py cron) — मर्यादेपलीकडे "
            "गेला, तर आजच्या उर्वरित दिवसासाठी फक्त NIFTY चे नवीन LIVE trades थांबतात (PAPER नेहमीप्रमाणेच "
            "चालू राहतं, इतर symbols वर परिणाम नाही)."
        )
        if not vh_settings["enabled"]:
            st.warning("⚪ VIX Spike Halt सध्या बंद आहे — VIX कितीही वाढला तरी NIFTY LIVE trading वर परिणाम नाही.")
        elif vh_settings.get("trade_date") != today_str:
            st.info("ℹ️ आजची तपासणी अजून झालेली नाही (cron अजून चालला नाही, किंवा बाजार उघडून 5 मिनिटं झालेली नाहीत).")
        elif vh_settings.get("halted"):
            pct = vh_settings.get("pct_change")
            pct_str = f"{pct:+.1f}%" if pct is not None else "अज्ञात (VIX किंमत मिळाली नाही)"
            st.error(
                f"🔴 आज VIX Spike Halt ट्रिप झालं — India VIX {pct_str} बदलला (मर्यादा "
                f"{vh_settings['threshold_pct']:.0f}%). NIFTY साठी नवीन LIVE trades ब्लॉक केले जात आहेत."
            )
        else:
            pct = vh_settings.get("pct_change")
            pct_str = f"{pct:+.1f}%" if pct is not None else "N/A"
            st.success(f"🟢 आजची तपासणी OK — India VIX {pct_str} बदलला (मर्यादा {vh_settings['threshold_pct']:.0f}%). NIFTY LIVE trading नेहमीप्रमाणे चालू.")

        vh_enabled = st.checkbox("VIX Spike Halt सक्रिय", value=vh_settings["enabled"], key="bdsr_vh_enabled")
        vh_threshold = st.number_input(
            "Threshold % (आदल्या दिवसाच्या VIX close च्या तुलनेत)", min_value=0.5, max_value=100.0,
            value=float(vh_settings["threshold_pct"]), step=0.5, key="bdsr_vh_threshold",
        )
        if st.button("💾 VIX Spike Halt सेव्ह करा", key="bdsr_vh_save_btn"):
            ok = cloud_db.save_vix_spike_halt_settings(vh_enabled, vh_threshold)
            if ok:
                st.success("✅ VIX Spike Halt सेटिंग्ज जतन झाल्या.")
            else:
                st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")


def render():
    mega_header("🤖 Bot Dynamic SR Algo", HDR_BLUE)
    st.caption("तिन्ही strategies (5-मिनिट Instant Trader, 15M/30M/60M Dynamic SR Reversal, Classical S/R Reversal) चे सर्व सेटिंग्ज — इथूनच, कधीही बदलता येण्याजोगे.")

    _render_live_status_banner()
    _render_kill_switch_panel()
    _render_vix_spike_halt_panel()

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
    if _current_mode == "LIVE_PAPER":
        _mode_caption = "🔴📝 सध्याचा मोड: **LIVE+PAPER** (खरे पैसे + तुलनेसाठी शॅडो PAPER trade)"
    elif _current_mode == "LIVE":
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
        elif strategy_key == "15m_dynamic_sr":
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("3 वेगवेगळे timeframe आहेत, selection user friendly
            # असू द्या, डीफॉल्ट 15 मिनिट ठेवा, 30 आणि 60 मिनिट optional राहील") — इतर दोन strategies
            # च्या "दोन पैकी एक/दोन्ही" radio पेक्षा वेगळं (इथे 3 टाईमफ्रेम्स, कुठलंही combination
            # हवं असू शकतं) — प्रत्येक टाईमफ्रेमसाठी स्वतंत्र checkbox, 15M डीफॉल्ट चालू.
            sub_header("⏱️ Touch Timeframe (एक किंवा अनेक निवडा)", HDR_TEAL)
            st.caption("15M डीफॉल्ट सक्रिय — 30M आणि 60M ऐच्छिक (हव्या तितक्या एकत्र निवडता येतील, किमान एक हवाच).")
            _srv2_active_tf = settings.get("active_timeframes", ["15M"])
            tf1, tf2, tf3 = st.columns(3)
            with tf1:
                srv2_tf_15m = st.checkbox("15M (डीफॉल्ट)", value="15M" in _srv2_active_tf, key=_widget_key(strategy_key, symbol, "tf_15m"))
            with tf2:
                srv2_tf_30m = st.checkbox("30M (ऐच्छिक)", value="30M" in _srv2_active_tf, key=_widget_key(strategy_key, symbol, "tf_30m"))
            with tf3:
                srv2_tf_60m = st.checkbox("60M (ऐच्छिक)", value="60M" in _srv2_active_tf, key=_widget_key(strategy_key, symbol, "tf_60m"))
            active_timeframes = [tf for tf, checked in [("15M", srv2_tf_15m), ("30M", srv2_tf_30m), ("60M", srv2_tf_60m)] if checked]
            if not active_timeframes:
                st.warning("⚠️ किमान एक टाईमफ्रेम निवडायलाच हवा — काहीही निवडलं नसेल, तर जतन करताना आपोआप 15M निवडला जाईल.")
            st.markdown("---")

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
        # kiman 15 minute same level war trade ghewu naye, cooldown") — तिन्ही strategies साठी
        # समान — पहिल्या trade चा SL/TSL लागल्यावर, त्याच exact level वर किती वेळ पुढचा trade
        # थांबवायचा. established generic 30-मिनिट cooldown (कुठल्याही exit-प्रकारावर, entry-वेळेवर
        # आधारित) आधीपासूनच आहे — हा त्यापेक्षा वेगळा, फक्त SL/TSL exits साठीच, exit-वेळेवर आधारित.
        sub_header("🕐 SL/TSL Cooldown (त्याच level वर)", HDR_TEAL)
        st.caption(
            "पहिल्या trade चा SL किंवा TSL लागल्यावर, त्याच exact level वर किमान इतकी मिनिटं पुढचा "
            "trade घेतला जाणार नाही (whipsaw/fakeout नंतरचं संरक्षण) — Target/इतर फायदेशीर exits ला "
            "लागू नाही. 0 केलं की हा गेट पूर्णपणे बंद."
        )
        sl_tsl_cooldown_minutes = _number_input(
            "Cooldown (मिनिटं)", settings, "sl_tsl_cooldown_minutes", strategy_key, symbol,
            min_value=0, max_value=120, step=5,
        )
        st.markdown("---")

        sub_header("🔻 Strike व Size निवड (Credit Spread)", HDR_PURPLE)
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("नेकेड ऑप्शन बाय हे ऑप्शनल आहे... क्रेडिट स्प्रेड सुद्धा
        # ऑप्शनल ठेवा — ज्या user कडे कमी कॅपिटल आहे तो नेकेड ऑप्शन बाय करणे पसंत करतो") — आधी Credit
        # Spread नेहमीच (toggle शिवाय) चालायचा, फक्त Naked Option ऐच्छिक होता. आता दोन्ही स्वतंत्रपणे
        # on/off करता येतात — कमी कॅपिटल असलेला वापरकर्ता फक्त Naked Option सक्रिय ठेवून, हा (जास्त
        # margin लागणारा) Credit Spread बंद करू शकतो.
        credit_spread_enabled = st.checkbox(
            "Credit Spread Trade सक्रिय", value=bool(settings.get("credit_spread_enabled", True)),
            key=_widget_key(strategy_key, symbol, "credit_spread_enabled"),
        )
        st.caption("Short leg ATM पासून ITM दिशेने (जास्त प्रीमियम, कमी अंतर) — OTM ऐवजी.")
        c1, c2, c3 = st.columns(3)
        with c1:
            lots = _number_input("Lots", settings, "lots", strategy_key, symbol, min_value=1, max_value=50, step=1)
        with c2:
            itm_depth_points = _number_input("ITM Depth (points)", settings, "itm_depth_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)
        with c3:
            hedge_width_points = _number_input("Hedge Width (points)", settings, "hedge_width_points", strategy_key, symbol, min_value=25.0, max_value=500.0, step=25.0)

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (ITM वि. OTM Credit Spread तुलना — "profit loss
        # आणि charges विचारात घेऊन कुठला strike फायदेशीर") — जुन्या expired तारखांचा actual option
        # premium डेटा मिळत नसल्याने खरा historical backtest शक्य नाही, त्यामुळे हे forward-test:
        # खऱ्या (ITM) trade सोबतच, याच सिग्नलवर, एक स्वतंत्र निव्वळ PAPER-only OTM पर्याय समांतर लॉग
        # होतो (वेगळ्याच source ने — मूळ strategy च्या आकडेवारीत कधीच मिसळत नाही). सुरुवातीला
        # (वापरकर्त्याच्या सूचनेनुसार) फक्त "5-Min Instant Trader" (1m_instant, फक्त 5M touches) पुरतंच.
        if strategy_key == "1m_instant":
            otm_shadow_enabled = st.checkbox(
                "🔬 OTM Shadow (फक्त 5M touches, तुलनेसाठी — निव्वळ PAPER, खऱ्या trade वर परिणाम नाही)",
                value=bool(settings.get("otm_shadow_enabled", False)),
                key=_widget_key(strategy_key, symbol, "otm_shadow_enabled"),
            )
            st.caption(
                "चालू केल्यास, वरच्याच ITM trade सोबत, त्याच सिग्नलवर, ATM पासून OTM स्ट्राइक्स "
                "वापरून एक स्वतंत्र, निव्वळ PAPER trade समांतर नोंदवला जातो — Performance Report वर "
                "वेगळ्या source ने (dynamic_sr_instant_otm_shadow) दोन्हींची तुलना करता येईल."
            )
            if otm_shadow_enabled:
                otm_shadow_strikes_count = _number_input(
                    "OTM Strikes (ATM पासून किती strikes दूर)", settings, "otm_shadow_strikes_count",
                    strategy_key, symbol, min_value=1, max_value=10, step=1,
                )
            else:
                otm_shadow_strikes_count = settings.get("otm_shadow_strikes_count", 2)

        st.markdown("---")
        sub_header("🧭 RSI Gate", HDR_ORANGE)
        entry_rsi_gate_enabled = st.checkbox(
            "RSI Gate सक्रिय (बंद केल्यास — फक्त S/R Touch वरच entry, RSI तपासला जाणार नाही)",
            value=bool(settings.get("entry_rsi_gate_enabled", True)),
            key=_widget_key(strategy_key, symbol, "entry_rsi_gate_enabled"),
        )
        if strategy_key in ("1m_instant", "15m_dynamic_sr"):
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
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — सगळ्या strategies साठी सामायिक — फक्त त्या दिशेचे नवीन trades थांबतात
        # (आधीच उघडलेले चालूच राहतात).
        sub_header("↕️ Bullish / Bearish Entry", HDR_GREEN)
        be1, be2 = st.columns(2)
        with be1:
            bullish_entry_enabled = st.checkbox(
                "📈 Bullish Entry सक्रिय (डीफॉल्ट चालू)",
                value=bool(settings.get("bullish_entry_enabled", True)),
                key=_widget_key(strategy_key, symbol, "bullish_entry_enabled"),
            )
        with be2:
            bearish_entry_enabled = st.checkbox(
                "📉 Bearish Entry सक्रिय (डीफॉल्ट चालू)",
                value=bool(settings.get("bearish_entry_enabled", True)),
                key=_widget_key(strategy_key, symbol, "bearish_entry_enabled"),
            )
        st.caption("बंद केलेल्या दिशेचे नवीन trades घेतले जाणार नाहीत (आधीच उघडलेल्या trades वर परिणाम नाही).")

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

        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("5 minute instant dynamic sr strategy work
        # better in sideways, low iv or average iv market, but in trending when Breakout happen it
        # books loss") — Average IV Breakout Gate, फक्त 1m_instant साठी (हीच strategy चर्चेत होती).
        if strategy_key == "1m_instant":
            st.markdown("---")
            sub_header("📈 Average IV Breakout Gate", HDR_CYAN)
            entry_iv_gate_enabled = st.checkbox(
                "IV Gate सक्रिय (डीफॉल्ट बंद — किमान काही दिवस iv_snapshot_collector.py चा इतिहास जमल्याशिवाय चालू करू नका)",
                value=bool(settings.get("entry_iv_gate_enabled", False)),
                key=_widget_key(strategy_key, symbol, "entry_iv_gate_enabled"),
            )
            st.caption("आजचा ATM IV, गेल्या N **sideways (Marubozu body_ratio<0.8 daily candle — trending दिवस वगळलेले)** दिवसांच्या सरासरीपेक्षा किती% वाढला (breakout) तर — reversal trade (मूळ S/R touch दिशा) थांबवून, त्याऐवजी उलट (breakout-following, directional) दिशेने trade घेतला जातो (RSI/PCR Gate त्या trade साठी वगळले जातात — ते reversal-साठीच tuned आहेत). IV डेटा गहाळ/जुना/अपुरा sideways-दिवसांचा इतिहास असल्यास मात्र सुरक्षिततेसाठी trade पूर्णपणे थांबवला जातो (regime माहीतच नसल्याने directional bet घेणं धोकादायक). ⚠️ फक्त NIFTY साठी.")
            iv1, iv2, iv3 = st.columns(3)
            with iv1:
                iv_change_max_pct = _number_input(
                    "IV % वाढ मर्यादा (यापेक्षा जास्त वाढ = breakout)", settings, "iv_change_max_pct", strategy_key, symbol,
                    min_value=5.0, max_value=100.0, step=1.0, format="%.1f", disabled=not entry_iv_gate_enabled,
                )
            with iv2:
                iv_lookback_days = _number_input(
                    "सरासरीसाठी किती मागचे sideways दिवस", settings, "iv_lookback_days", strategy_key, symbol,
                    min_value=1, max_value=30, step=1, disabled=not entry_iv_gate_enabled,
                )
            with iv3:
                # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("All should be user friendly gate, no
                # hardcoded") — Marubozu threshold (आधी module-level हार्डकोड 0.8) आता इथून बदलण्याजोगा.
                iv_marubozu_threshold = _number_input(
                    "Marubozu threshold (day trending कधी धरायचा — जास्त = कडक)", settings, "iv_marubozu_threshold", strategy_key, symbol,
                    min_value=0.3, max_value=0.95, step=0.05, format="%.2f", disabled=not entry_iv_gate_enabled,
                )

            # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Max 2 trade on same level hit, he honar
            # donhi sl or tsl hit jhalet, ani nantr jar Breakout buildup and 5 minute candle closed
            # happen then take entry in the same direction") — max-2-hits च्या पलीकडचा, तिसरा trade.
            st.markdown("---")
            sub_header("💥 Breakout Entry (max-2-hits नंतरचा 3रा trade)", HDR_AMBER)
            entry_breakout_gate_enabled = st.checkbox(
                "Breakout Entry सक्रिय (डीफॉल्ट बंद)",
                value=bool(settings.get("entry_breakout_gate_enabled", False)),
                key=_widget_key(strategy_key, symbol, "entry_breakout_gate_enabled"),
            )
            st.caption(
                "त्याच level वर आजचे दोन्ही touch (max-2-hits) आधीच झालेले असतील, breakout-candle च्या आधीच्या काही "
                "5-मिनिट candles मध्ये price level च्या जवळच (खालील tolerance% च्या आत) consolidate झालेला असावा "
                "(हाच price-action \"buildup\" — trade प्रत्यक्ष open झाला/नाही यावर अवलंबून नाही, IV/RSI/PCR Gate ने "
                "आधीचे touches block केले तरी काम करतं) — आणि नंतर एक 5-मिनिट candle त्या level च्या पलीकडे "
                "(breakout-दिशेने — मूळ 2 trades च्या उलट) निर्णायकपणे close झाला, तरच तिसरा trade घेतला जातो. "
                "RSI/PCR Gate (directional trade असल्याने) आणि 30-मिनिट Cooldown (मुद्दामच लगेच यायला हवं म्हणून) दोन्ही वगळलेले."
            )
            bo1, bo2 = st.columns(2)
            with bo1:
                breakout_lookback_candles = _number_input(
                    "Consolidation window (5-मिनिट candles)", settings, "breakout_lookback_candles", strategy_key, symbol,
                    min_value=2, max_value=24, step=1, disabled=not entry_breakout_gate_enabled,
                )
            with bo2:
                breakout_tolerance_pct = _number_input(
                    "Level पासून tolerance% (consolidation मानण्यासाठी)", settings, "breakout_tolerance_pct", strategy_key, symbol,
                    min_value=0.05, max_value=1.0, step=0.05, format="%.2f", disabled=not entry_breakout_gate_enabled,
                )

        if strategy_key == "classic_sr_reversal":
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Ya strategy mdhe swing high swing low,
            # demand supply, trend line he sarv concept include kra and entry refine kra" — तीन
            # ऐच्छिक, स्वतंत्र confluence गेट्स (सर्व डीफॉल्ट बंद). RSI गेट (वर) आणि हे तिन्ही गेट्स
            # मिळून — Credit Spread व Naked दोन्हीला एकच, सामायिक सिग्नल (वेगळे गेट्स नाहीत).
            with st.expander("🔍 Entry Refinement (ऐच्छिक Confluence गेट्स)", expanded=False):
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
        st.caption("त्याच सिग्नलवर, Credit Spread सक्रिय असेल तर त्यासोबतच — दोन्ही स्वतंत्रपणे on/off करता येतात (वर बघा). डीफॉल्ट: hedge नाही (निव्वळ ITM खरेदी) — हवं असल्यास हेजिंग सक्रिय करा.")
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

        with st.expander("📈 Trailing Stop Loss (Premium Points, सतत, ऐच्छिक — डीफॉल्ट बंद)", expanded=False):
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

        with st.expander("⚡ Broker-Side SL — Phase 2 (फक्त Upstox, डीफॉल्ट बंद)", expanded=False):
            # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", "PAPER mode
            # मध्ये आधी test करूया") — Performance Report मध्ये सापडलेल्या SL slippage चा फेज १
            # (trade_monitor.py, 60s->~20s polling) आधीच मर्ज झालेला आहे. हा फेज २ — entry नंतर लगेच
            # Upstox कडेच resting SL-M order ठेवला जातो, exchange level वरच trigger होण्यासाठी.
            st.caption(
                "चालू केल्यास — entry नंतर लगेच Upstox कडेच SL-M (Stop-Loss Market) order ठेवला जातो "
                "(वरचा 'SL — Premium Points' थ्रेशोल्ड वापरून) — trade_monitor.py च्या 20-सेकंद "
                "polling ची वाट न बघताच exchange level वर SL trigger होऊ शकतो. Credit Spread साठी "
                "फक्त SHORT leg वर (hedge leg स्थिर आहे असं worst-case गृहीत धरून — प्रत्यक्षात SL "
                "आवश्यकतेपेक्षा किंचित आधीच लागू शकतो, कधीच उशिरा नाही). "
                "**PAPER/LIVE+PAPER मोड मध्ये खरा order कधीच जात नाही** — फक्त trigger price ची गणना "
                "होऊन log मध्ये (`monitor.log`) दिसते, जेणेकरून LIVE करण्याआधी गणित पडताळता येईल. "
                "**फक्त शुद्ध Upstox** (कुठलाही विशिष्ट broker account न निवडलेला, किंवा Upstox "
                "account निवडलेला) — Shoonya/Stocko/Fyers अजून support करत नाहीत, त्यांच्यावर काहीही परिणाम नाही."
            )
            broker_side_sl_enabled = st.checkbox(
                "Broker-Side SL (Phase 2) सक्रिय", value=bool(settings.get("broker_side_sl_enabled", False)),
                key=_widget_key(strategy_key, symbol, "broker_side_sl_enabled"),
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

        sub_header("पायरी १ — Trading Mode (PAPER / LIVE / LIVE+PAPER)", HDR_ORANGE)
        st.caption(
            "PAPER = फक्त सराव/सिम्युलेशन, खरे पैसे अजिबात वापरले जात नाहीत. LIVE = खरे पैसे, खरे "
            "ऑर्डर्स. LIVE+PAPER = खरा LIVE ऑर्डर + त्याच वेळी, त्याच सिग्नलवर एक शॅडो PAPER trade "
            "सुद्धा स्वतंत्रपणे नोंदवला जातो (फक्त तुलनेसाठी — प्रत्यक्ष/सिम्युलेटेड निकाल शेजारी-शेजारी "
            "बघता यावेत म्हणून, त्याचे स्वतःचे खरे पैसे वापरले जात नाहीत). हा bot VPS वर आपोआप (दर काही "
            "मिनिटांनी) चालतो."
        )
        _mode_options = [
            "📝 PAPER (सराव, सुरक्षित — शिफारस)", "🔴 LIVE (खरे पैसे)", "🔴📝 LIVE+PAPER (खरे पैसे + शॅडो PAPER तुलना)",
        ]
        _saved_mode = settings.get("trading_mode", "PAPER")
        _saved_index = {"PAPER": 0, "LIVE": 1, "LIVE_PAPER": 2}.get(_saved_mode, 0)
        trading_mode_choice = st.radio(
            "मोड निवडा", _mode_options, index=_saved_index,
            key=_widget_key(strategy_key, symbol, "trading_mode_radio"), horizontal=True,
            help="नवीन असाल तर PAPER वरच ठेवा. काही दिवस Performance पानावर निकाल बघून, समाधान झाल्यावरच LIVE किंवा LIVE+PAPER करा.",
        )
        if trading_mode_choice == _mode_options[2]:
            trading_mode_selected = "LIVE_PAPER"
        elif trading_mode_choice == _mode_options[1]:
            trading_mode_selected = "LIVE"
        else:
            trading_mode_selected = "PAPER"
        live_confirmed = True
        if trading_mode_selected in ("LIVE", "LIVE_PAPER"):
            _confirm_label = (
                f"मला समजते — {STRATEGY_LABELS[strategy_key]} ({symbol}) आता खऱ्या पैशांनी, VPS वर आपोआप "
                f"(कुठलाही manual क्लिक न करता) ट्रेड करेल"
                + (" (सोबत तुलनेसाठी एक शॅडो PAPER trade सुद्धा नोंदवला जाईल)" if trading_mode_selected == "LIVE_PAPER" else "")
            )
            live_confirmed = st.checkbox(
                _confirm_label, value=False, key=_widget_key(strategy_key, symbol, "trading_mode_confirm"),
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
        if effective_mode == "LIVE_PAPER":
            st.error(
                f"📋 **सारांश** — 'Settings जतन करा' दाबल्यावर: {STRATEGY_LABELS[strategy_key]} ({symbol}) "
                f"🔴📝 **LIVE+PAPER** — {broker_summary} खरा ऑर्डर, + सोबत तुलनेसाठी स्वतंत्र शॅडो PAPER trade."
            )
        elif effective_mode == "LIVE":
            st.error(f"📋 **सारांश** — 'Settings जतन करा' दाबल्यावर: {STRATEGY_LABELS[strategy_key]} ({symbol}) 🔴 **LIVE** — {broker_summary}, खऱ्या पैशांनी ट्रेड करेल.")
        else:
            st.success(f"📋 **सारांश** — 'Settings जतन करा' दाबल्यावर: {STRATEGY_LABELS[strategy_key]} ({symbol}) 📝 **PAPER** — {broker_summary}, फक्त सिम्युलेशन (सुरक्षित).")

    st.markdown("---")
    if st.button("💾 Settings जतन करा", key="bdsr_save_btn", type="primary"):
        new_settings = {
            "symbol_enabled": bool(symbol_enabled),
            "lots": int(lots), "itm_depth_points": float(itm_depth_points), "hedge_width_points": float(hedge_width_points),
            "credit_spread_enabled": bool(credit_spread_enabled),
            "bullish_entry_enabled": bool(bullish_entry_enabled), "bearish_entry_enabled": bool(bearish_entry_enabled),
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
            "broker_side_sl_enabled": bool(broker_side_sl_enabled),
            "sl_tsl_cooldown_minutes": int(sl_tsl_cooldown_minutes),
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
            new_settings["entry_iv_gate_enabled"] = bool(entry_iv_gate_enabled)
            new_settings["iv_change_max_pct"] = float(iv_change_max_pct)
            new_settings["iv_lookback_days"] = int(iv_lookback_days)
            new_settings["iv_marubozu_threshold"] = float(iv_marubozu_threshold)
            new_settings["entry_breakout_gate_enabled"] = bool(entry_breakout_gate_enabled)
            new_settings["breakout_lookback_candles"] = int(breakout_lookback_candles)
            new_settings["breakout_tolerance_pct"] = float(breakout_tolerance_pct)
            new_settings["otm_shadow_enabled"] = bool(otm_shadow_enabled)
            new_settings["otm_shadow_strikes_count"] = int(otm_shadow_strikes_count)
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
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("RSI setting 60/40" + "timeframe selection user
            # friendly, 15M डीफॉल्ट, 30/60 ऐच्छिक") — फक्त "15m_dynamic_sr" (SRv2) याच else-शाखेत
            # पोहोचतो (STRATEGY_LABELS मध्ये फक्त हे तीनच strategy keys आहेत).
            new_settings["rsi_support_max"] = int(rsi_support_max)
            new_settings["rsi_resistance_min"] = int(rsi_resistance_min)
            new_settings["active_timeframes"] = active_timeframes if active_timeframes else ["15M"]
            new_settings["spread_target_pct_of_premium"] = float(spread_target_pct_of_premium)
            new_settings["carry_forward_min_profit_pct"] = float(carry_forward_min_profit_pct)
            new_settings["naked_eod_hour"] = int(naked_eod_hour)
            new_settings["naked_eod_minute"] = int(naked_eod_minute)

        ok = cloud_db.save_strategy_settings(strategy_key, symbol, new_settings)
        if ok:
            st.success(f"✅ {STRATEGY_LABELS[strategy_key]} ({symbol}) साठी settings जतन झाले — पुढच्या cycle पासून लागू होतील.")
        else:
            st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")
