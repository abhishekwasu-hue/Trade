"""
page_mcx_futures.py
--------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेलं, संपूर्णपणे नवीन, स्वतंत्र पान — MCX Futures Trader
(CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER). NIFTY/BANKNIFTY/SENSEX च्या तिन्ही existing bots (Bot
Dynamic SR Algo पान) ला अजिबात हात लावलेला नाही — इथून फक्त हाच नवीन strategy चालतो.

✅ अद्ययावत (2026-09-22) — प्रत्यक्ष trading script (`mcx_futures_trader.py`) व Dynamic S/R refresh
script (`refresh_market_zones_mcx.py`) दोन्ही बांधलेले आहेत, आणि VPS crontab वर आता **प्रत्यक्ष सक्रिय
आहेत** (`crontab -l` ने पडताळलेलं — दर मिनिटाला entry bot, रात्री zones refresh). PRE_LIVE_CHECKLIST.md
§5 मध्ये नोंदवल्याप्रमाणे, resolver/zones च्या स्वतंत्र spot-check पायऱ्या (क्रम-अनुसार) झाल्याची खात्री
नाही — पण crontab स्वतःच दर cycle ला दोन्ही वापरतोच, त्यामुळे काहीही चुकीचं असेल तर लगेच log/Signal
Log मध्ये दिसेल. Trading Mode प्रत्येक symbol साठी स्वतंत्र (डीफॉल्ट PAPER — खालचा हिरवा/लाल बॅनर
सद्य स्थिती दाखवतो).

🎓 वापरकर्त्याने स्पष्ट केलेली, या project मधल्या सर्वच bots ना लागू असलेली सामायिक रचना ("Max 2 entry
per level this setting is common for all bot in this project") — Multi-Hit मर्यादा: एकाच S/R level
वर एका दिवसात जास्तीत जास्त 2 वेळाच entry (`cloud_db.get_zone_hits_today()`, srv2_momentum_reversal_strategy.py/
dynamic_sr_instant_trader.py/classic_sr_reversal_trader.py प्रमाणेच — hardcoded, Dashboard वरून
बदलण्याजोगी नाही) — mcx_futures_trader.py मध्येही हाच नियम, तोच helper वापरून लागू केलेला आहे.
"""
import datetime

import pandas as pd
import streamlit as st

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from config import get_ist_today
from database import (
    get_order_log_full, get_performance_summary, get_closed_trades_detail,
    get_live_vs_shadow_paper_pairs, get_live_positions_with_mtm, get_todays_mcx_live_pnl_and_count,
    get_todays_mcx_live_peak_pnl, OPTION_STRUCTURE_GROUP_SQL,
)
from page_performance import _render_group_breakdown, _build_recommendations, _entry_reason_text, _entry_reason_text_en, _EXIT_REASON_LABELS, _exit_reason_label_with_tag
from pdf_reports import generate_performance_report_pdf
from pnl_reports import generate_pnl_report
from sr_dynamic import compute_dynamic_sr
from tradingview_chart import build_lightweight_chart_html
from trading_engine import close_trade_manually, set_manual_sl_override, clear_manual_sl_override
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_GREEN, HDR_AMBER, HDR_PINK
from upstox_api import fetch_mcx_candles, get_total_capital
from mcx_futures_trader import PRODUCT_TYPE

MCX_SYMBOLS = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]
STRATEGY_KEY = "mcx_futures"

CHART_TIMEFRAME_OPTIONS = {
    "5minute": "5 मिनिट", "15minute": "15 मिनिट", "30minute": "30 मिनिट",
    "1hour": "1 तास", "day": "Daily",
}


def _widget_key(symbol, field):
    return f"mcxf_{symbol}_{field}"


def _render_level_hit_log_by_date(df):
    """🎓 page_dashboard.py च्या `_render_signal_log_by_date()` (Market Zones टॅबवरचा Signal Log,
    SRv2/Dynamic SR Instant Trader साठी) याच पॅटर्नचं MCX साठी स्वतंत्र अनुकरण — तारीख-निहाय (date-wise)
    वेगळं दाखवला जातो, सर्वात अलीकडची तारीख सर्वात वर. `cloud_db.signal_log` table symbol-निरपेक्ष
    आहे (कुठलाही strategy_key/exchange column नाही) — त्यामुळे mcx_futures_trader.py (बांधल्यावर)
    established `cloud_db.save_signal_log()` याच table मध्ये थेट वापरू शकेल, वेगळी table लागणार नाही."""
    signal_time = pd.to_datetime(df["signal_time"])
    dates = signal_time.dt.date
    for d in sorted(dates.unique(), reverse=True):
        day_df = df[dates == d]
        st.markdown(f"**📅 {d}** — {len(day_df)} तपासण्या, {(day_df['hit_type'] != 'NO_HIT').sum()} वेळा touch")
        st.dataframe(day_df, width="stretch", height=min(300, 60 + 35 * len(day_df)))


@st.cache_data(ttl=300)
def _resolve_mcx_instrument_cached(access_token, symbol):
    """🎓 resolve_mcx_futures_instruments.resolve_symbol() स्वतः cache करत नाही (तो एक standalone,
    वाचन-फक्त script आहे) — इथे Chart टॅब उघडताना प्रत्येक rerun (उदा. टाईमफ्रेम बदल) ला Upstox च्या
    Search Instruments API ला पुन्हा-पुन्हा हिट न करता, ५ मिनिटांसाठी तोच resolved contract वापरणे."""
    return mcx_resolver.resolve_symbol(access_token, symbol)


def _number_input(label, settings, key, symbol, **kwargs):
    is_float = isinstance(kwargs.get("step"), float) or isinstance(kwargs.get("min_value"), float) or isinstance(kwargs.get("max_value"), float)
    value = float(settings[key]) if is_float else int(settings[key])
    return st.number_input(label, value=value, key=_widget_key(symbol, key), **kwargs)


def _render_status_banner():
    all_modes = cloud_db.get_all_strategy_trading_modes()
    live_combos = [
        symbol for (strategy_key, symbol), info in all_modes.items()
        if strategy_key == STRATEGY_KEY and info.get("trading_mode") in ("LIVE", "LIVE_PAPER")
    ]
    if live_combos:
        st.error(f"🔴 सध्या LIVE (खऱ्या पैशांनी) चालू आहे: {', '.join(live_combos)}")
    else:
        st.success("🟢 सर्व MCX commodities सध्या PAPER मोडमध्ये आहेत — कुठलाही खरा पैसा वापरला जात नाही.")


def _render_mcx_kill_switch_panel():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (MCX LIVE करण्याआधी — "MCX साठी वेगळा Kill Switch/capital
    cap") — page_bot_dynamic_sr_algo.py च्या ग्लोबल Kill Switch पॅनेलसारखंच, पण फक्त MCX (5
    commodities मिळून) पुरतं — trading_engine.check_mcx_kill_switch() जे प्रत्यक्षात वापरतं तेच
    settings इथून बदलता येतात. ग्लोबल Kill Switch (Bot Dynamic SR Algo पान) सुद्धा MCX ला लागू
    होतोच — हा फक्त त्याहून कडक, MCX-विशिष्ट दुसरा थर आहे."""
    ks = cloud_db.get_mcx_kill_switch_settings()
    total_pnl, open_positions = get_todays_mcx_live_pnl_and_count()
    token_input = st.session_state.get("token_input", "")
    total_capital = get_total_capital(token_input) if token_input else None
    max_daily_loss_amount = (total_capital * ks["max_daily_loss_pct"] / 100) if total_capital else None

    with st.expander("🛑 MCX-विशिष्ट Kill Switch (5 Commodities मिळून, ग्लोबलपेक्षा स्वतंत्र/कडक)", expanded=False):
        st.caption(
            "MCX ही brand-new रणनीती आहे (अजून एकही खरा LIVE order गेलेला नाही) — त्यामुळे ग्लोबल Kill "
            "Switch (Bot Dynamic SR Algo पान) सोबतच, इथे फक्त MCX साठीच स्वतंत्र, जास्त कडक मर्यादा — "
            "आजचा MCX-पुरताच तोटा किंवा एकाच वेळी उघडी असलेल्या commodities ची संख्या इथल्या मर्यादेपलीकडे "
            "गेली, तर नवीन MCX LIVE trade आपोआप थांबतो (PAPER trades वर परिणाम नाही, बाकी bots वरही नाही)."
        )
        if total_capital is None:
            st.warning("⚠️ एकूण capital मिळालं नाही (token/नेटवर्क तपासा) — तोटा-मर्यादा मोजता येत नाही, यावेळी Kill Switch नवीन MCX LIVE trades आपोआप थांबवेल.")
        else:
            st.caption(f"सध्याचं एकूण capital (Upstox): ₹{total_capital:,.0f}")

        peak_pnl_today = get_todays_mcx_live_peak_pnl()
        locked_floor = (peak_pnl_today * ks["profit_lock_pct"] / 100) if peak_pnl_today > 0 else None
        profit_locked_tripped = ks["profit_lock_enabled"] and locked_floor is not None and total_pnl < locked_floor
        tripped = ks["enabled"] and (
            total_capital is None
            or open_positions >= ks["max_open_positions"]
            or total_pnl <= -(max_daily_loss_amount or 0)
            or profit_locked_tripped
        )
        if not ks["enabled"]:
            st.warning("⚪ MCX Kill Switch सध्या बंद आहे — फक्त ग्लोबल Kill Switch लागू आहे.")
        elif tripped:
            if profit_locked_tripped and not (total_capital is None or open_positions >= ks["max_open_positions"] or total_pnl <= -(max_daily_loss_amount or 0)):
                st.error(
                    f"🔴 MCX Profit-Lock Kill Switch ट्रिप झालं आहे — आजचा सर्वोच्च MCX LIVE नफा ₹{peak_pnl_today:,.0f} "
                    f"होता, त्यातला {ks['profit_lock_pct']:.0f}% (₹{locked_floor:,.0f}) लॉक होता, सद्य नफा ₹{total_pnl:,.0f} "
                    f"त्याखाली घसरला. नवीन MCX LIVE trade ब्लॉक केला जातोय."
                )
            else:
                st.error(f"🔴 MCX Kill Switch ट्रिप झालं आहे — आजचा MCX LIVE P&L ₹{total_pnl:,.0f}, उघडी positions {open_positions}. नवीन MCX LIVE trade ब्लॉक केला जातोय.")
        else:
            # tripped=False इथे फक्त ks["enabled"] आणि total_capital दोन्ही असतील तरच पोहोचतं (वरच्या
            # `or` chain प्रमाणे) — म्हणजे max_daily_loss_amount इथे नेहमीच उपलब्ध असतो.
            lock_caption = f", profit-lock मजला ₹{locked_floor:,.0f}" if ks["profit_lock_enabled"] and locked_floor is not None else ""
            st.success(f"🟢 MCX Kill Switch OK — आजचा MCX LIVE P&L ₹{total_pnl:,.0f} (तोटा-मर्यादा ₹{-max_daily_loss_amount:,.0f}{lock_caption})")
            st.caption(f"उघडी positions {open_positions}/{ks['max_open_positions']}")

        mks_enabled = st.checkbox("MCX Kill Switch सक्रिय", value=ks["enabled"], key="mcx_ks_enabled")
        c1, c2 = st.columns(2)
        with c1:
            mks_max_loss_pct = st.number_input(
                "कमाल दैनिक तोटा % (एकूण capital चा, फक्त MCX)", min_value=0.1, max_value=100.0,
                value=float(ks["max_daily_loss_pct"]), step=0.25, key="mcx_ks_max_loss_pct",
            )
        with c2:
            mks_max_open = st.number_input(
                "कमाल एकाच वेळी उघडी positions (सर्व 5 commodities मिळून)", min_value=1, max_value=5,
                value=int(ks["max_open_positions"]), step=1, key="mcx_ks_max_open",
            )
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — ग्लोबल Kill Switch (Bot Dynamic SR Algo पान)
        # सारखंच Profit-Lock, पण फक्त MCX पुरतं. डीफॉल्ट बंद.
        st.caption(
            "🔒 Profit-Lock (ऐच्छिक) — आजचा MCX चा सर्वोच्च नफा गाठला की त्यातला ठराविक % कायमचा "
            "\"मजला\" म्हणून लॉक होतो — सद्य MCX नफा त्याखाली घसरला की नवीन MCX LIVE trades थांबतात."
        )
        pc1, pc2 = st.columns(2)
        with pc1:
            mks_profit_lock_enabled = st.checkbox(
                "MCX Profit-Lock सक्रिय", value=ks["profit_lock_enabled"], key="mcx_ks_profit_lock_enabled",
            )
        with pc2:
            mks_profit_lock_pct = st.number_input(
                "लॉक करायचा % (आजच्या MCX सर्वोच्च नफ्यापैकी)", min_value=1.0, max_value=99.0,
                value=float(ks["profit_lock_pct"]), step=5.0, key="mcx_ks_profit_lock_pct",
            )
        if st.button("💾 MCX Kill Switch सेव्ह करा", key="mcx_ks_save_btn"):
            ok = cloud_db.save_mcx_kill_switch_settings(
                mks_enabled, mks_max_loss_pct, mks_max_open, mks_profit_lock_enabled, mks_profit_lock_pct,
            )
            if ok:
                st.success("✅ MCX Kill Switch सेटिंग्ज जतन झाल्या.")
            else:
                st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")


def _render_all_commodities_positions():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("1 common position tab पाहिजे, ज्यामध्ये सर्व commodity
    च्या live and exited position ची summary असेल") — मुख्य Dashboard चा Positions टॅप
    (page_positions.py) `st.session_state["symbol"]` (फक्त NIFTY/BANKNIFTY/SENSEX निवडता येणारा
    sidebar dropdown) वापरतो — MCX commodities त्या dropdown मध्ये कधीच नसतात, त्यामुळे MCX चे
    trades तिथे कधीच दिसतच नव्हते. इथे प्रत्येक commodity साठी (वरच्या per-commodity dropdown ची
    वाट न बघता) established get_live_positions_with_mtm()/get_closed_trades_detail() तेच, सिद्ध
    फंक्शन्स वापरून एकत्र केलेलं आहे — कुठलाही नवीन query-पॅटर्न नाही."""
    token = st.session_state.get("token_input", "")
    if not token:
        st.info("Upstox token उपलब्ध नाही — sidebar मधून token टाका.")
        return

    sub_header("💼 सर्व Commodities — Open Positions (Live MTM)", HDR_TEAL)
    open_frames = []
    for sym in MCX_SYMBOLS:
        try:
            df = get_live_positions_with_mtm(token, sym)
        except Exception:
            continue  # एका commodity साठी LTP मिळाला नाही तरी बाकीच्या दिसायला हव्यात
        if not df.empty:
            df.insert(0, "Symbol", sym)
            open_frames.append(df)

    if not open_frames:
        st.info("सध्या कुठल्याही MCX commodity ची उघडी (OPEN) position नाही.")
    else:
        combined_open = pd.concat(open_frames, ignore_index=True)
        st.dataframe(combined_open, width="stretch", height=min(400, 60 + 35 * len(combined_open)))
        total_open_mtm = combined_open["MTM (Rs)"].dropna().sum()
        st.metric("सर्व Commodities मिळून एकूण Open MTM", f"₹{total_open_mtm:,.0f}")

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Algo bot ni घेतलेले trade Position tab मधून manually
        # close करता यायला पाहिजे") — page_positions.py (NIFTY/BANKNIFTY/SENSEX) मध्ये हे आधीच आहे,
        # पण MCX commodities साठी कुठेच नव्हतं (तिथला Positions टॅब फक्त sidebar च्या symbol-निवडीवर
        # चालतो, MCX त्यात कधीच नसतो). तोच established close_trade_manually() (broker-side SL आधी
        # cancel करूनच सुरक्षितपणे बंद करतो) इथेही — फक्त प्रत्येक निवडलेल्या trade_id साठी त्याच्या
        # स्वतःच्या "Symbol" स्तंभावरून योग्य commodity ठरवून (एकाच combined table मध्ये 5 commodities
        # असल्याने, page_positions.py सारखा एकच सामायिक symbol गृहीत धरता येत नाही). MCX नेहमी
        # PRODUCT_TYPE="D" वापरतो (mcx_futures_trader.py, established) — sidebar च्या product_type शी
        # गल्लत होऊ नये म्हणून तोच थेट इथे वापरला आहे.
        sub_header("🔴 पोझिशन मॅन्युअली बंद करा", HDR_BLUE)
        st.caption("एक, अनेक, किंवा सर्व commodities च्या पोझिशन्स एकाच वेळी निवडून बंद करता येतील.")

        all_trade_ids = combined_open["Trade ID"].tolist()

        def _format_trade(tid):
            row = combined_open.loc[combined_open["Trade ID"] == tid]
            return f"{row['Symbol'].values[0]} — {tid} — {row['Strategy'].values[0]} ({row['Legs'].values[0]})"

        if st.session_state.pop("_mcx_pending_multiselect_clear", False):
            st.session_state["mcx_close_trade_multiselect"] = []
            st.session_state["mcx_close_select_all"] = False

        def _toggle_select_all():
            st.session_state["mcx_close_trade_multiselect"] = list(all_trade_ids) if st.session_state.get("mcx_close_select_all") else []

        st.checkbox("सर्व पोझिशन्स निवडा", key="mcx_close_select_all", on_change=_toggle_select_all)

        st.session_state["mcx_close_trade_multiselect"] = [
            tid for tid in st.session_state.get("mcx_close_trade_multiselect", []) if tid in all_trade_ids
        ]

        selected_trade_ids = st.multiselect(
            "बंद करण्यासाठी पोझिशन(न्स) निवडा",
            options=all_trade_ids, format_func=_format_trade, key="mcx_close_trade_multiselect",
        )

        if st.button(f"🔴 निवडलेल्या {len(selected_trade_ids)} पोझिशन्स बंद करा", disabled=len(selected_trade_ids) == 0, key="mcx_close_btn"):
            with st.spinner(f"{len(selected_trade_ids)} पोझिशन्स बंद करत आहे..."):
                results = []
                for tid in selected_trade_ids:
                    row_symbol = combined_open.loc[combined_open["Trade ID"] == tid, "Symbol"].values[0]
                    ok, result = close_trade_manually(token, tid, row_symbol, PRODUCT_TYPE)
                    results.append((tid, ok, result))
            for tid, ok, result in results:
                if ok:
                    st.success(f"✅ {tid} बंद झाली — Realized P&L: ₹{result:,.2f}")
                else:
                    st.error(f"❌ {tid} बंद करता आलं नाही: {result}")
            if any(ok for _, ok, _ in results):
                st.session_state["_mcx_pending_multiselect_clear"] = True
                st.rerun()

        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("सध्या उघड्या trade चा TSL तात्पुरता बदलायचाय — घट्ट
        # आणि सैल दोन्ही") — page_positions.py सारखाच established pattern, MCX साठीही — निवडलेल्या
        # एका trade साठी established automatic SL/TSL/Target लॉजिक पूर्णपणे वगळून (Target अजूनही
        # लागू), फक्त हा एक threshold तपासला जातो. ⚠️ सैल केल्यास जोखीम वाढते — प्रत्येक बदलावर
        # Telegram अलर्ट (trading_engine.set_manual_sl_override()/clear_manual_sl_override()).
        st.markdown("---")
        sub_header("🎯 Trailing SL तात्पुरता बदला (Manual Override)", HDR_ORANGE)
        st.caption(
            "एका विशिष्ट trade चा SL/TSL तात्पुरता घट्ट किंवा सैल करा (कुठल्याही commodity चा) — "
            "established automatic SL/TSL/Trailing लॉजिक त्या trade साठी पूर्णपणे वगळलं जातं (Target "
            "मात्र नेहमीप्रमाणेच लागू राहतो). ⚠️ सैल केल्यास जोखीम वाढते."
        )
        mcx_override_trade_id = st.selectbox(
            "Trade निवडा", options=all_trade_ids, format_func=_format_trade, key="mcx_tsl_override_trade_select",
        )
        if mcx_override_trade_id:
            override_row = combined_open.loc[combined_open["Trade ID"] == mcx_override_trade_id].iloc[0]
            current_override = override_row.get("Manual SL Override (Rs)")
            has_override = pd.notna(current_override)
            mocol1, mocol2 = st.columns(2)
            with mocol1:
                mtm_val = override_row["MTM (Rs)"]
                st.metric("सद्य MTM P&L", f"₹{mtm_val:,.0f}" if pd.notna(mtm_val) else "N/A")
            with mocol2:
                st.metric("सध्याचा Manual Override", f"₹{current_override:,.0f}" if has_override else "नाही (established logic लागू)")

            mcx_new_override_level = st.number_input(
                "नवीन SL पातळी (₹ एकूण trade P&L)",
                value=float(current_override) if has_override else 0.0, step=100.0, key="mcx_tsl_override_new_level",
            )
            moc1, moc2 = st.columns(2)
            with moc1:
                if st.button("⚠️ SL Override सेट करा", key="mcx_tsl_override_set_btn"):
                    ok, err = set_manual_sl_override(mcx_override_trade_id, mcx_new_override_level)
                    if ok:
                        st.success(f"✅ {mcx_override_trade_id} चा SL आता ₹{mcx_new_override_level:,.0f} वर सेट झाला — Telegram अलर्ट पाठवला.")
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")
            with moc2:
                if has_override and st.button("🗑️ Override काढा (established logic परत लागू करा)", key="mcx_tsl_override_clear_btn"):
                    ok, err = clear_manual_sl_override(mcx_override_trade_id)
                    if ok:
                        st.success(f"✅ {mcx_override_trade_id} चा Override काढला.")
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")

    st.markdown("---")
    sub_header("📜 सर्व Commodities — Exit झालेले Trades", HDR_PURPLE)
    today_d = get_ist_today()
    range_choice = st.radio(
        "कालावधी", ["आज", "गेले 7 दिवस", "गेला महिना", "कस्टम रेंज"], horizontal=True, key="mcxf_allpos_range",
    )
    if range_choice == "आज":
        ex_from, ex_to = today_d, today_d
    elif range_choice == "गेले 7 दिवस":
        ex_from, ex_to = today_d - datetime.timedelta(days=7), today_d
    elif range_choice == "गेला महिना":
        ex_from, ex_to = today_d - datetime.timedelta(days=30), today_d
    else:
        c1, c2 = st.columns(2)
        with c1:
            ex_from = st.date_input("पासून", value=today_d, key="mcxf_allpos_from")
        with c2:
            ex_to = st.date_input("पर्यंत", value=today_d, key="mcxf_allpos_to")

    if ex_from > ex_to:
        st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
        return

    closed_frames = []
    for sym in MCX_SYMBOLS:
        df = get_closed_trades_detail(sym, start_date=ex_from, end_date=ex_to)
        if not df.empty:
            df.insert(0, "Symbol", sym)
            closed_frames.append(df)

    if not closed_frames:
        st.info("या कालावधीत कुठल्याही MCX commodity चा एकही trade बंद झालेला नाही.")
    else:
        combined_closed = pd.concat(closed_frames, ignore_index=True).sort_values("Exit Time", ascending=False)
        st.dataframe(combined_closed, width="stretch", height=min(400, 60 + 35 * len(combined_closed)))
        total_realized = combined_closed["Realized P&L"].sum()
        st.metric(f"{ex_from} ते {ex_to}: एकूण Realized P&L", f"₹{total_realized:,.0f}")
        st.caption(f"एकूण {len(combined_closed)} बंद झालेले trades (सर्व commodities मिळून, नवीनतम आधी).")


def render():
    mega_header("🛢️ MCX Futures Trader", HDR_BLUE)
    st.caption(
        "CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER — Support/Resistance touch झाला की सरळ Futures "
        "contract खरेदी/विक्री (options नाही — Upstox चा Option Chain API MCX साठी उपलब्धच नाही). "
        "इतर NIFTY/BANKNIFTY/SENSEX bots (Bot Dynamic SR Algo पान) पासून पूर्णपणे स्वतंत्र."
    )
    st.info(
        "ℹ️ `mcx_futures_trader.py`/`refresh_market_zones_mcx.py` VPS crontab वर **सक्रिय आहेत** "
        "(दर मिनिटाला entry-तपासणी, रात्री zones refresh) — प्रत्येक commodity साठी वरचा "
        "'trading सक्रिय' checkbox (Entry Gate टॅब) चालू असेल तरच प्रत्यक्ष तपासणी/trade होते. "
        "resolver/zones च्या स्वतंत्र spot-check पायऱ्या (`PRE_LIVE_CHECKLIST.md` §5) अजून "
        "स्वतंत्रपणे पडताळलेल्या नाहीत — काही चुकीचं वाटल्यास `mcx_futures.log`/Signal Log आधी तपासा."
    )

    _render_status_banner()
    _render_mcx_kill_switch_panel()

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — हा भाग मुद्दामच खालच्या "Commodity निवडा" dropdown च्या
    # बाहेर (वर) आहे — सर्व 5 commodities एकत्र, एकाच वेळी दाखवण्यासाठी, प्रत्येकासाठी वेगळं निवडावं
    # न लागता.
    with st.expander("💼 सर्व Positions (सर्व Commodities एकत्र) — Live + Exit झालेले", expanded=True):
        _render_all_commodities_positions()

    st.markdown("---")
    symbol = st.selectbox("Commodity निवडा", MCX_SYMBOLS, key="mcxf_symbol")
    settings = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)

    tab_chart, tab_entry, tab_exit, tab_orders, tab_perf, tab_zones, tab_mode = st.tabs([
        "📈 Chart", "🚪 Entry Gate", "🚪 Exit Gate", "📜 Order Log", "📊 Performance Report", "📐 Dynamic S/R", "🎮 Mode & Broker",
    ])

    with tab_chart:
        sub_header(f"📈 {symbol} — Futures Price Chart", HDR_BLUE)
        chart_tf = st.radio(
            "टाईमफ्रेम", list(CHART_TIMEFRAME_OPTIONS.keys()), format_func=lambda k: CHART_TIMEFRAME_OPTIONS[k],
            index=2, horizontal=True, key=_widget_key(symbol, "chart_tf"),
        )
        token = st.session_state.get("token_input", "")
        if not token:
            st.info("Upstox token उपलब्ध नाही — चार्टसाठी वैध token लागतो (sidebar वरून टाकलेला/cron ने refresh केलेला).")
        else:
            ok, resolved = _resolve_mcx_instrument_cached(token, symbol)
            if not ok:
                st.warning(f"⚠️ {symbol} चा सध्याचा (current/continuous) Futures contract सापडला नाही: {resolved}")
            else:
                df_mcx = fetch_mcx_candles(token, resolved["instrument_key"], interval=chart_tf)
                if df_mcx is None or df_mcx.empty:
                    st.info("चार्टसाठी candle डेटा मिळाला नाही.")
                else:
                    rsi_series = df_mcx["rsi"] if "rsi" in df_mcx.columns else None
                    sr_levels = compute_dynamic_sr(df_mcx, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
                    tv_html = build_lightweight_chart_html(
                        df_mcx, symbol=symbol, timeframe_label=CHART_TIMEFRAME_OPTIONS[chart_tf],
                        rsi_series=rsi_series, sr_levels=sr_levels, height=550,
                    )
                    st.components.v1.html(tv_html, height=600, scrolling=False)
                    st.caption(
                        f"📄 Contract: **{resolved['trading_symbol']}** (expiry {resolved['expiry']}) — Upstox च्या "
                        "Search Instruments API कडून थेट, कायम आपोआप current/continuous front-month."
                    )

    with tab_entry:
        symbol_enabled = st.checkbox(
            f"{symbol} साठी trading सक्रिय (बंद असल्यास — PAPER सुद्धा कुठलाही trade घेतला जाणार नाही)",
            value=bool(settings.get("symbol_enabled", False)),
            key=_widget_key(symbol, "symbol_enabled"),
        )
        lots = _number_input("Lots (× commodity चा स्वतःचा lot_size)", settings, "lots", symbol, min_value=1, max_value=50, step=1)
        st.caption(
            "🔁 Multi-Hit मर्यादा (या project च्या सर्व bots सारखीच, बदलण्याजोगी नाही) — एकाच S/R "
            "level वर एका दिवसात जास्तीत जास्त 2 वेळाच entry घेतली जाईल."
        )

        st.markdown("---")
        sub_header("⏱️ Touch Timeframe", HDR_TEAL)
        st.caption("15M हा पर्यायच नाही (कधीच नाही) — फक्त 30M, 60M, किंवा दोन्ही एकत्र.")
        _TF_OPTIONS = {"30M": "फक्त 30M (डीफॉल्ट)", "60M": "फक्त 60M", "ALL": "30M + 60M (दोन्ही एकत्र)"}
        _tf_keys = list(_TF_OPTIONS.keys())
        _tf_stored = settings.get("timeframe_choice", "30M")
        _tf_index = _tf_keys.index(_tf_stored) if _tf_stored in _tf_keys else 0
        timeframe_choice = st.radio(
            "कोणत्या टाईमफ्रेमचे touch levels तपासायचे?",
            _tf_keys, format_func=lambda k: _TF_OPTIONS[k], horizontal=True,
            index=_tf_index, key=_widget_key(symbol, "timeframe_choice"),
        )

        st.markdown("---")
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — फक्त त्या दिशेचे नवीन trades थांबतात (आधीच उघडलेले चालूच राहतात).
        sub_header("↕️ Bullish / Bearish Entry", HDR_GREEN)
        be1, be2 = st.columns(2)
        with be1:
            bullish_entry_enabled = st.checkbox(
                "📈 Bullish Entry सक्रिय (डीफॉल्ट चालू)",
                value=bool(settings.get("bullish_entry_enabled", True)),
                key=_widget_key(symbol, "bullish_entry_enabled"),
            )
        with be2:
            bearish_entry_enabled = st.checkbox(
                "📉 Bearish Entry सक्रिय (डीफॉल्ट चालू)",
                value=bool(settings.get("bearish_entry_enabled", True)),
                key=_widget_key(symbol, "bearish_entry_enabled"),
            )
        st.caption("बंद केलेल्या दिशेचे नवीन trades घेतले जाणार नाहीत (आधीच उघडलेल्या trades वर परिणाम नाही).")

        st.markdown("---")
        sub_header("🧭 RSI Gate", HDR_ORANGE)
        entry_rsi_gate_enabled = st.checkbox(
            "RSI Gate सक्रिय (बंद केल्यास — फक्त S/R Touch वरच entry, RSI तपासला जाणार नाही)",
            value=bool(settings.get("entry_rsi_gate_enabled", True)),
            key=_widget_key(symbol, "entry_rsi_gate_enabled"),
        )
        st.caption("Support/Bullish → RSI यापेक्षा कमी हवा. Resistance/Bearish → RSI यापेक्षा जास्त हवा (दरम्यान कुठलीच दिशा पात्र ठरत नाही).")
        r1, r2 = st.columns(2)
        with r1:
            rsi_support_max = _number_input(
                "RSI Support Max (Bullish साठी यापेक्षा कमी)", settings, "rsi_support_max", symbol,
                min_value=5, max_value=50, step=1, disabled=not entry_rsi_gate_enabled,
            )
        with r2:
            rsi_resistance_min = _number_input(
                "RSI Resistance Min (Bearish साठी यापेक्षा जास्त)", settings, "rsi_resistance_min", symbol,
                min_value=50, max_value=95, step=1, disabled=not entry_rsi_gate_enabled,
            )

        st.markdown("---")
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Mcx comodity sathi suddha he feature add
        # kra, Breakout buildup waril A and C mix logic") — dynamic_sr_instant_trader.py (NIFTY
        # Bot Dynamic SR Algo) मधलाच Breakout Entry आता इथेही — max-2-hits च्या पलीकडचा, तिसरा trade.
        sub_header("💥 Breakout Entry (max-2-hits नंतरचा 3रा trade)", HDR_PINK)
        entry_breakout_gate_enabled = st.checkbox(
            "Breakout Entry सक्रिय (डीफॉल्ट बंद)",
            value=bool(settings.get("entry_breakout_gate_enabled", False)),
            key=_widget_key(symbol, "entry_breakout_gate_enabled"),
        )
        st.caption(
            "त्याच level वर आजचे दोन्ही touch (max-2-hits) आधीच झालेले असतील, breakout-candle च्या आधीच्या काही "
            "(वरच्या Touch Timeframe च्याच — 30M/60M) candles मध्ये price level च्या जवळच (खालील tolerance% च्या आत) "
            "consolidate झालेला असावा — आणि नंतर एक candle त्या level च्या पलीकडे (breakout-दिशेने — मूळ 2 trades च्या उलट) "
            "निर्णायकपणे close झाला, तरच तिसरा trade घेतला जातो. "
            "RSI Gate (directional trade असल्याने) वगळलेला (MCX मध्ये PCR/IV Gate/Cooldown मुळातच नाहीत)."
        )
        bo1, bo2 = st.columns(2)
        with bo1:
            breakout_lookback_candles = _number_input(
                "Consolidation window (candles, याच Touch Timeframe च्या)", settings, "breakout_lookback_candles", symbol,
                min_value=2, max_value=24, step=1, disabled=not entry_breakout_gate_enabled,
            )
        with bo2:
            breakout_tolerance_pct = _number_input(
                "Level पासून tolerance% (consolidation मानण्यासाठी)", settings, "breakout_tolerance_pct", symbol,
                min_value=0.05, max_value=1.0, step=0.05, format="%.2f", disabled=not entry_breakout_gate_enabled,
            )

        if st.button("💾 Entry Gate सेव्ह करा", key=_widget_key(symbol, "save_entry")):
            new_settings = dict(settings)
            new_settings.update({
                "symbol_enabled": bool(symbol_enabled), "lots": int(lots),
                "timeframe_choice": timeframe_choice,
                "bullish_entry_enabled": bool(bullish_entry_enabled), "bearish_entry_enabled": bool(bearish_entry_enabled),
                "entry_rsi_gate_enabled": bool(entry_rsi_gate_enabled),
                "rsi_support_max": int(rsi_support_max), "rsi_resistance_min": int(rsi_resistance_min),
                "entry_breakout_gate_enabled": bool(entry_breakout_gate_enabled),
                "breakout_lookback_candles": int(breakout_lookback_candles),
                "breakout_tolerance_pct": float(breakout_tolerance_pct),
            })
            ok = cloud_db.save_strategy_settings(STRATEGY_KEY, symbol, new_settings)
            st.success(f"✅ {symbol} Entry Gate जतन झालं.") if ok else st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")

    with tab_exit:
        sub_header("🎯 SL / Target / Trailing SL", HDR_AMBER)
        st.caption("Options प्रमाणे premium नाही — सरळ underlying futures वर, Points किंवा Percentage — दोन्हीपैकी एक निवडा.")

        _MODE_OPTIONS = {"POINTS": "Points (ठराविक futures points)", "PERCENT": "Percentage (entry किंमतीच्या %)"}
        _mode_keys = list(_MODE_OPTIONS.keys())
        _mode_stored = settings.get("sl_target_mode", "POINTS")
        _mode_index = _mode_keys.index(_mode_stored) if _mode_stored in _mode_keys else 0
        sl_target_mode = st.radio(
            "SL/Target/Trailing कशावर आधारित असावं?", _mode_keys, format_func=lambda k: _MODE_OPTIONS[k],
            horizontal=True, index=_mode_index, key=_widget_key(symbol, "sl_target_mode"),
        )
        is_percent_mode = sl_target_mode == "PERCENT"

        # 🎓 वापरकर्त्याने सापडवलेली गोंधळाची रचना ("repeat setting... confusion") — आधी Points आणि
        # Percentage दोन्ही fields एकाच वेळी दिसायचे (न-निवडलेला फक्त disabled/greyed-out) — SL/Target/
        # Trailing प्रत्येकी 2, म्हणजे 6 fields दिसायचे जिथे खरंच फक्त 2-3 लागतात. आता निवडलेल्या mode
        # चंच field दाखवलं जातं — दुसऱ्याची जतन केलेली value settings मधून तशीच वाचली/जपली जाते
        # (mode बदलला तरी हरवत नाही), फक्त UI मध्ये दिसत नाही इतकंच.
        e1, e2 = st.columns(2)
        if is_percent_mode:
            with e1:
                sl_pct = _number_input(
                    "Stop Loss (% of entry price)", settings, "sl_pct", symbol, min_value=0.1, max_value=50.0, step=0.1,
                )
            with e2:
                target_pct = _number_input(
                    "Target (% of entry price)", settings, "target_pct", symbol, min_value=0.1, max_value=100.0, step=0.1,
                )
            sl_points, target_points = float(settings["sl_points"]), float(settings["target_points"])
        else:
            with e1:
                sl_points = _number_input(
                    "Stop Loss (futures points)", settings, "sl_points", symbol, min_value=1.0, max_value=1000.0, step=1.0,
                )
            with e2:
                target_points = _number_input(
                    "Target (futures points)", settings, "target_points", symbol, min_value=1.0, max_value=2000.0, step=1.0,
                )
            sl_pct, target_pct = float(settings["sl_pct"]), float(settings["target_pct"])

        trailing_sl_enabled = st.checkbox(
            "Trailing Stop Loss सक्रिय (ऐच्छिक — डीफॉल्ट बंद)", value=bool(settings.get("trailing_sl_enabled", False)),
            key=_widget_key(symbol, "trailing_sl_enabled"),
        )
        if trailing_sl_enabled and is_percent_mode:
            trailing_pct = _number_input(
                "Trailing Distance (% of सद्य किंमत)", settings, "trailing_pct", symbol, min_value=0.1, max_value=20.0, step=0.1,
            )
            trailing_distance_points = float(settings["trailing_distance_points"])
        elif trailing_sl_enabled:
            trailing_distance_points = _number_input(
                "Trailing Distance (futures points)", settings, "trailing_distance_points", symbol, min_value=1.0, max_value=500.0, step=1.0,
            )
            trailing_pct = float(settings["trailing_pct"])
        else:
            trailing_distance_points = float(settings["trailing_distance_points"])
            trailing_pct = float(settings["trailing_pct"])

        if st.button("💾 Exit Gate सेव्ह करा", key=_widget_key(symbol, "save_exit")):
            new_settings = dict(settings)
            new_settings.update({
                "sl_target_mode": sl_target_mode,
                "sl_points": float(sl_points), "target_points": float(target_points),
                "sl_pct": float(sl_pct), "target_pct": float(target_pct),
                "trailing_sl_enabled": bool(trailing_sl_enabled),
                "trailing_distance_points": float(trailing_distance_points),
                "trailing_pct": float(trailing_pct),
            })
            ok = cloud_db.save_strategy_settings(STRATEGY_KEY, symbol, new_settings)
            st.success(f"✅ {symbol} Exit Gate जतन झालं.") if ok else st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")

    with tab_orders:
        sub_header(f"📜 {symbol} — Order Log", HDR_PURPLE)
        today_d = get_ist_today()
        range_choice = st.radio(
            "कालावधी", ["आज", "गेले 7 दिवस", "गेला महिना", "कस्टम रेंज"], horizontal=True, key=_widget_key(symbol, "order_range"),
        )
        if range_choice == "आज":
            ord_from, ord_to = today_d, today_d
        elif range_choice == "गेले 7 दिवस":
            ord_from, ord_to = today_d - datetime.timedelta(days=7), today_d
        elif range_choice == "गेला महिना":
            ord_from, ord_to = today_d - datetime.timedelta(days=30), today_d
        else:
            c1, c2 = st.columns(2)
            with c1:
                ord_from = st.date_input("पासून", value=today_d, key=_widget_key(symbol, "order_from"))
            with c2:
                ord_to = st.date_input("पर्यंत", value=today_d, key=_widget_key(symbol, "order_to"))

        if ord_from > ord_to:
            st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
        else:
            orders_df = get_order_log_full(symbol, start_date=ord_from, end_date=ord_to)
            if orders_df.empty:
                st.info(
                    "या कालावधीत कोणतेही ऑर्डर्स नाहीत — म्हणजे अजून कुठलाही trade झालेला नाही "
                    "(symbol बंद असेल, किंवा RSI/Multi-Hit गेटमुळे candidate qualify झालेला नाही — "
                    "Level Hit Log टॅबवर नेमकं कारण दिसेल)."
                )
            else:
                st.dataframe(orders_df, width="stretch", height=400)
                st.caption(f"{ord_from} ते {ord_to}: एकूण {len(orders_df)} ऑर्डर्स (नवीनतम आधी).")
                dl_csv = orders_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Order Log CSV डाऊनलोड करा", data=dl_csv,
                    file_name=f"{symbol}_MCX_OrderLog_{ord_from}_{ord_to}.csv",
                    mime="text/csv", key=_widget_key(symbol, "order_dl"),
                )

    with tab_perf:
        sub_header(f"📊 {symbol} — Performance Report", HDR_PINK)
        st.caption(
            "Performance पानासारखाच संपूर्ण विश्लेषण (Strategy/Timeframe breakdown, प्रत्येक Trade चं Entry+Exit "
            "कारण, शिफारसी) आणि तोच प्रिंट-योग्य PDF (इंग्रजीत — PDF fonts मध्ये मराठी glyphs उपलब्ध नाहीत). "
            "'Option Structure नुसार' विभाग MCX Futures ला लागू होत नाही (इथे options नाहीत, सरळ futures) — "
            "तो रिकामाच दिसेल, ते अपेक्षितच आहे."
        )
        perf_mode_choice = st.radio(
            "दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key=_widget_key(symbol, "perf_mode_filter"),
        )
        perf_mode_f = None if perf_mode_choice == "सर्व" else ("LIVE" if "LIVE" in perf_mode_choice else "PAPER")

        perf_today = get_ist_today()
        perf_range_choice = st.radio(
            "कालावधी", ["आज", "गेले 7 दिवस", "गेला महिना", "संपूर्ण इतिहास", "कस्टम रेंज"], horizontal=True,
            key=_widget_key(symbol, "perf_range"),
        )
        if perf_range_choice == "आज":
            perf_from, perf_to = perf_today, perf_today
        elif perf_range_choice == "गेले 7 दिवस":
            perf_from, perf_to = perf_today - datetime.timedelta(days=7), perf_today
        elif perf_range_choice == "गेला महिना":
            perf_from, perf_to = perf_today - datetime.timedelta(days=30), perf_today
        elif perf_range_choice == "संपूर्ण इतिहास":
            perf_from, perf_to = datetime.date(2020, 1, 1), perf_today
        else:
            pc1, pc2 = st.columns(2)
            with pc1:
                perf_from = st.date_input("पासून", value=perf_today - datetime.timedelta(days=30), key=_widget_key(symbol, "perf_from"))
            with pc2:
                perf_to = st.date_input("पर्यंत", value=perf_today, key=_widget_key(symbol, "perf_to"))

        if perf_from > perf_to:
            st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
        else:
            st.caption(f"निवडलेली रेंज: {perf_from} ते {perf_to}")
            summary = get_performance_summary(symbol, mode_filter=perf_mode_f, start_date=perf_from, end_date=perf_to)
            if summary.get("total_trades", 0) == 0:
                st.info(
                    "या कालावधीत कोणतेही बंद ट्रेड्स नाहीत — म्हणजे अजून कुठलाही trade उघडून बंद "
                    "झालेला नाही (Order Log/Level Hit Log टॅबवर नेमकं कारण दिसेल)."
                )
            else:
                scol1, scol2, scol3, scol4 = st.columns(4)
                with scol1:
                    st.metric("बंद ट्रेड्स", summary["total_trades"])
                with scol2:
                    st.metric("Win Rate", f"{summary['win_rate']}%" if summary.get("win_rate") is not None else "N/A")
                with scol3:
                    st.metric("Gross P&L", f"₹{summary['total_pnl']:,.0f}")
                with scol4:
                    st.metric("ROI %", f"{summary['roi_pct']}%" if summary.get("roi_pct") is not None else "N/A")

            st.markdown("---")
            perf_tab1, perf_tab2, perf_tab3 = st.tabs(
                ["🎯 Algo Strategy नुसार", "⏱️ Timeframe नुसार", "🧩 Option Structure नुसार"]
            )
            with perf_tab1:
                perf_by_source = _render_group_breakdown(symbol, "source", perf_mode_f, perf_from, perf_to, "Strategy-wise P&L")
            with perf_tab2:
                perf_by_timeframe = _render_group_breakdown(symbol, "entry_timeframe", perf_mode_f, perf_from, perf_to, "Timeframe-wise P&L")
            with perf_tab3:
                perf_by_structure = _render_group_breakdown(
                    symbol, OPTION_STRUCTURE_GROUP_SQL, perf_mode_f, perf_from, perf_to,
                    "Option Structure-wise P&L (MCX Futures साठी लागू नाही)",
                )

            sub_header("📋 Trade Log — प्रत्येक Trade चं Entry व Exit कारण", HDR_PURPLE)
            perf_trade_log_df = get_closed_trades_detail(symbol, mode_filter=perf_mode_f, start_date=perf_from, end_date=perf_to)
            perf_trade_log_pdf_df = None
            if perf_trade_log_df.empty:
                st.caption("या कालावधीत कोणतेही बंद ट्रेड्स नाहीत.")
            else:
                perf_trade_log_display = perf_trade_log_df.copy()
                perf_trade_log_display["Entry Reason"] = perf_trade_log_display.apply(_entry_reason_text, axis=1)
                perf_trade_log_display["Exit Reason"] = perf_trade_log_display["exit_reason"].map(lambda r: _EXIT_REASON_LABELS.get(r, r))
                perf_trade_log_display["Exit Reason (नेमकं कारण)"] = perf_trade_log_display["exit_reason_detail"].fillna("—")
                perf_trade_log_display = perf_trade_log_display[[
                    "Trade ID", "Entry Time", "Entry Reason", "Exit Time", "Exit Reason",
                    "Exit Reason (नेमकं कारण)", "Realized P&L", "mode",
                ]].rename(columns={"mode": "Mode"})
                st.dataframe(perf_trade_log_display, width="stretch", height=350, hide_index=True)
                perf_trade_log_csv = perf_trade_log_display.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Trade Log CSV डाऊनलोड करा (Entry+Exit कारणांसकट)", data=perf_trade_log_csv,
                    file_name=f"{symbol}_MCX_TradeLog_Reasons_{perf_from}_{perf_to}.csv",
                    mime="text/csv", key=_widget_key(symbol, "trade_log_reasons_download"),
                )

                perf_trade_log_pdf_df = perf_trade_log_df.copy()
                perf_trade_log_pdf_df["Entry Reason"] = perf_trade_log_pdf_df.apply(_entry_reason_text_en, axis=1)
                perf_trade_log_pdf_df["Exit Reason"] = perf_trade_log_pdf_df.apply(
                    lambda r: _exit_reason_label_with_tag(r["exit_reason"], r["exit_reason_detail"]), axis=1,
                )
                perf_trade_log_pdf_df["Exit Reason Detail"] = perf_trade_log_pdf_df["exit_reason_detail"].fillna("-")
                perf_trade_log_pdf_df["Entry Timeframe"] = perf_trade_log_pdf_df["entry_timeframe"].where(
                    perf_trade_log_pdf_df["entry_timeframe"].notna() & (perf_trade_log_pdf_df["entry_timeframe"] != "UNKNOWN"), "N/A",
                )
                perf_trade_log_pdf_df = perf_trade_log_pdf_df[[
                    "Trade ID", "Entry Time", "Entry Reason", "Exit Time", "Exit Reason",
                    "Exit Reason Detail", "Realized P&L", "mode", "Entry Timeframe",
                ]].rename(columns={"mode": "Mode"})

            perf_slippage_pairs_df = (
                get_live_vs_shadow_paper_pairs(symbol, perf_from, perf_to) if perf_mode_f is None else pd.DataFrame()
            )

            st.markdown("---")
            sub_header("📄 संपूर्ण Performance Report (PDF)", HDR_AMBER)
            if st.button("📄 Performance Report PDF तयार करा", key=_widget_key(symbol, "perf_pdf_generate")):
                mode_label_en = {"सर्व": "All", "फक्त LIVE": "LIVE only", "फक्त PAPER": "PAPER only"}.get(perf_mode_choice, perf_mode_choice)
                pdf_cache_key = (symbol, mode_label_en, str(perf_from), str(perf_to))
                perf_pdf_state_key = _widget_key(symbol, "perf_pdf_cache_key")
                perf_pdf_bytes_key = _widget_key(symbol, "perf_pdf_bytes")
                if st.session_state.get(perf_pdf_state_key) == pdf_cache_key and st.session_state.get(perf_pdf_bytes_key):
                    st.info("ℹ️ याच कालावधी/मोडसाठी PDF आधीच तयार आहे — खाली थेट डाऊनलोड करा (पुन्हा तयार करायची गरज नाही).")
                else:
                    with st.spinner("PDF तयार होत आहे..."):
                        _, perf_pnl_totals = generate_pnl_report(symbol, "Daily", perf_from, perf_to, mode_filter=perf_mode_f)
                        perf_recs_en = (
                            _build_recommendations(symbol, "source", "Strategy", perf_mode_f, perf_from, perf_to, english=True)
                            + _build_recommendations(symbol, "entry_timeframe", "Timeframe", perf_mode_f, perf_from, perf_to, english=True)
                            + _build_recommendations(symbol, OPTION_STRUCTURE_GROUP_SQL, "Option Structure", perf_mode_f, perf_from, perf_to, english=True)
                        )
                        perf_pdf_bytes = generate_performance_report_pdf(
                            symbol, mode_label_en, perf_from, perf_to, summary, perf_pnl_totals,
                            perf_by_source, perf_by_timeframe, perf_by_structure, perf_trade_log_pdf_df, perf_recs_en,
                            slippage_pairs_df=perf_slippage_pairs_df,
                        )
                    st.session_state[perf_pdf_bytes_key] = perf_pdf_bytes
                    st.session_state[_widget_key(symbol, "perf_pdf_filename")] = f"{symbol}_MCX_Performance_Report_{perf_from}_{perf_to}.pdf"
                    st.session_state[perf_pdf_state_key] = pdf_cache_key
            if st.session_state.get(_widget_key(symbol, "perf_pdf_bytes")):
                st.download_button(
                    "📥 Performance Report PDF डाऊनलोड करा", data=st.session_state[_widget_key(symbol, "perf_pdf_bytes")],
                    file_name=st.session_state.get(_widget_key(symbol, "perf_pdf_filename"), f"{symbol}_MCX_Performance_Report.pdf"),
                    mime="application/pdf", key=_widget_key(symbol, "perf_pdf_download"),
                )

    with tab_zones:
        sub_header(f"📐 {symbol} — Dynamic Support/Resistance", HDR_GREEN)
        zones_df = cloud_db.get_market_zones(symbol, status="ACTIVE")
        if zones_df is None or zones_df.empty:
            st.info(
                "अजून कुठलेही ACTIVE zones नाहीत — MCX साठी Market Zones Refresh अजून सुरू केलेला "
                "नाही (existing NIFTY/BANKNIFTY/SENSEX साठीचा refresh_market_zones.py MCX करत नाही, "
                "त्यासाठी वेगळं जोडावं लागेल)."
            )
        else:
            st.dataframe(
                zones_df[["zone_type", "zone_low", "zone_high", "strength", "formed_date"]].sort_values("zone_type"),
                width="stretch",
            )
            st.caption(f"एकूण {len(zones_df)} ACTIVE zones.")

        st.markdown("---")
        sub_header(f"📜 {symbol} — Level Hit Log", HDR_PURPLE)
        st.caption(
            "Dashboard च्या Market Zones टॅबवरच्या Signal Log सारखंच — प्रत्येक तपासलेला S/R level touch "
            "(trade झाला किंवा न झाला तरीही). `cloud_db.signal_log` symbol-निरपेक्ष table आहे, त्यामुळे "
            "mcx_futures_trader.py बांधल्यावर हीच table वापरेल — वेगळी table लागणार नाही."
        )
        hit_log_today = get_ist_today()
        hit_log_range_choice = st.radio(
            "कालावधी", ["आज", "गेले 7 दिवस", "कस्टम रेंज"], horizontal=True, key=_widget_key(symbol, "hit_log_range"),
        )
        if hit_log_range_choice == "आज":
            hit_log_from, hit_log_to = hit_log_today, hit_log_today
        elif hit_log_range_choice == "गेले 7 दिवस":
            hit_log_from, hit_log_to = hit_log_today - datetime.timedelta(days=7), hit_log_today
        else:
            hl1, hl2 = st.columns(2)
            with hl1:
                hit_log_from = st.date_input("पासून", value=hit_log_today, key=_widget_key(symbol, "hit_log_from"))
            with hl2:
                hit_log_to = st.date_input("पर्यंत", value=hit_log_today, key=_widget_key(symbol, "hit_log_to"))

        if hit_log_from > hit_log_to:
            st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
        else:
            hit_log_df = cloud_db.get_signal_log_range(symbol, hit_log_from, hit_log_to)
            if hit_log_df is None or hit_log_df.empty:
                st.info(
                    "या कालावधीत कुठलाही level touch तपासला गेलेला नाही — बहुतेक हे symbol साठी "
                    "'trading सक्रिय' (Entry Gate टॅब) अजून चालू केलेलं नसल्यामुळे असेल — तो checkbox "
                    "आणि 'Entry Gate सेव्ह करा' बटण तपासा. सक्रिय असूनही रिकामं दिसत असेल, तर "
                    "`mcx_futures.log` मध्ये (VPS) नेमकं कारण दिसेल."
                )
            else:
                hit_log_filter = st.radio(
                    "दाखवा", ["सर्व", "फक्त Hit झालेले"], horizontal=True, key=_widget_key(symbol, "hit_log_filter"),
                )
                display_hit_log = hit_log_df if hit_log_filter == "सर्व" else hit_log_df[hit_log_df["hit_type"] != "NO_HIT"]
                st.caption(f"एकूण {len(hit_log_df)} तपासण्या — {(hit_log_df['hit_type'] != 'NO_HIT').sum()} वेळा level ला स्पर्श (touch) झाला.")
                _render_level_hit_log_by_date(display_hit_log)

    with tab_mode:
        st.info(f"सध्या तुम्ही **MCX Futures Trader** ({symbol}) साठी सेटिंग्ज बदलताय — इतर commodities यावर परिणाम होणार नाही.")
        _mode_options = [
            "📝 PAPER (सराव, सुरक्षित — शिफारस)", "🔴 LIVE (खरे पैसे)", "🔴📝 LIVE+PAPER (खरे पैसे + शॅडो PAPER तुलना)",
        ]
        _saved_mode = settings.get("trading_mode", "PAPER")
        _saved_index = {"PAPER": 0, "LIVE": 1, "LIVE_PAPER": 2}.get(_saved_mode, 0)
        trading_mode_choice = st.radio(
            "मोड निवडा", _mode_options, index=_saved_index, horizontal=True,
            key=_widget_key(symbol, "trading_mode_radio"),
        )
        if trading_mode_choice == _mode_options[2]:
            trading_mode_selected = "LIVE_PAPER"
        elif trading_mode_choice == _mode_options[1]:
            trading_mode_selected = "LIVE"
        else:
            trading_mode_selected = "PAPER"

        live_confirmed = True
        if trading_mode_selected in ("LIVE", "LIVE_PAPER"):
            live_confirmed = st.checkbox(
                f"मला समजते — MCX Futures Trader ({symbol}) आता खऱ्या पैशांनी ट्रेड करेल",
                value=False, key=_widget_key(symbol, "trading_mode_confirm"),
            )
            if not live_confirmed:
                st.warning("⚠️ वरील पुष्टीकरण टिक केल्याशिवाय जतन केलं तरी मोड PAPER वरच राहील (सुरक्षिततेसाठी).")

        st.markdown("---")
        accounts_df = cloud_db.get_all_broker_accounts(active_only=False)
        if accounts_df is None or accounts_df.empty:
            st.info("💡 कुठलेही broker accounts अजून नोंदवलेले नाहीत — त्यामुळे सध्या नेहमी शुद्ध Upstox वापरला जाईल.")
            broker_account_ids = []
        else:
            account_options = {
                row["account_id"]: f"{row['nickname'] or row['account_id']} ({row['broker_type']})" + ("" if row["is_active"] else " ⚪ निष्क्रिय")
                for _, row in accounts_df.iterrows()
            }
            current_selection = [aid for aid in (settings.get("broker_account_ids") or []) if aid in account_options]
            broker_account_ids = st.multiselect(
                "Broker Account(s) — ऐच्छिक", list(account_options.keys()),
                default=current_selection, format_func=lambda aid: account_options[aid],
                key=_widget_key(symbol, "broker_account_ids"),
            )

        if st.button("💾 Mode & Broker सेव्ह करा", key=_widget_key(symbol, "save_mode")):
            new_settings = dict(settings)
            new_settings.update({
                "trading_mode": trading_mode_selected if (trading_mode_selected == "PAPER" or live_confirmed) else "PAPER",
                "broker_account_ids": broker_account_ids,
            })
            ok = cloud_db.save_strategy_settings(STRATEGY_KEY, symbol, new_settings)
            st.success(f"✅ {symbol} Mode & Broker जतन झालं.") if ok else st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")
