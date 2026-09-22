"""
page_mcx_futures.py
--------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेलं, संपूर्णपणे नवीन, स्वतंत्र पान — MCX Futures Trader
(CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER). NIFTY/BANKNIFTY/SENSEX च्या तिन्ही existing bots (Bot
Dynamic SR Algo पान) ला अजिबात हात लावलेला नाही — इथून फक्त हाच नवीन strategy चालतो.

✅ अद्ययावत — प्रत्यक्ष trading script (`mcx_futures_trader.py`) व Dynamic S/R refresh script
(`refresh_market_zones_mcx.py`) दोन्ही आता बांधलेले आहेत (existing 3 bots — options — यांच्याच
`trading_engine.open_multi_leg_trade()`/`manage_open_trades()` वापरून, एकाच futures leg सह — तिथे
कुठलाही बदल न करता). ⚠️ तरीही VPS crontab वर अजून सक्रिय केलेले नाहीत — `resolve_mcx_futures_instruments.py`
ने खरा instrument_key/lot_size प्रत्यक्ष पडताळून, `refresh_market_zones_mcx.py`/`mcx_futures_trader.py`
हाताने एकदा चालवून निकाल तपासल्याशिवाय (`deploy/README.md` मधली चेकलिस्ट) ते सुरक्षित नाही —
तोपर्यंत Order Log/Dynamic S/R/Performance Report टॅब रिकामेच दिसतील, तिथेही तसं नमूद केलेलं आहे.

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
    get_live_vs_shadow_paper_pairs, OPTION_STRUCTURE_GROUP_SQL,
)
from page_performance import _render_group_breakdown, _build_recommendations, _entry_reason_text, _entry_reason_text_en, _EXIT_REASON_LABELS, _exit_reason_label_with_tag
from pdf_reports import generate_performance_report_pdf
from pnl_reports import generate_pnl_report
from sr_dynamic import compute_dynamic_sr
from tradingview_chart import build_lightweight_chart_html
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_GREEN, HDR_AMBER, HDR_PINK
from upstox_api import fetch_mcx_candles

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


def render():
    mega_header("🛢️ MCX Futures Trader", HDR_BLUE)
    st.caption(
        "CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER — Support/Resistance touch झाला की सरळ Futures "
        "contract खरेदी/विक्री (options नाही — Upstox चा Option Chain API MCX साठी उपलब्धच नाही). "
        "इतर NIFTY/BANKNIFTY/SENSEX bots (Bot Dynamic SR Algo पान) पासून पूर्णपणे स्वतंत्र."
    )
    st.warning(
        "⚠️ `mcx_futures_trader.py`/`refresh_market_zones_mcx.py` script आता बांधलेल्या आहेत, पण "
        "VPS crontab वर अजून सक्रिय केलेल्या नाहीत — Upstox कडून खरे instrument_key/lot_size प्रत्यक्ष "
        "पडताळल्याशिवाय (`resolve_mcx_futures_instruments.py` VPS वर चालवून) आणि दोन्ही scripts "
        "हाताने एकदा चालवून निकाल तपासल्याशिवाय (`deploy/README.md` मधली चेकलिस्ट) ते सुरक्षित नाही. "
        "इथले settings आधीच जतन करून ठेवता येतात — strategy सक्रिय झाल्यावर तीच वापरेल. VPS crontab "
        "entry सुद्धा (NSE bots पासून पूर्णपणे वेगळी, `deploy/README.md` मध्ये तयार करून ठेवलेली) "
        "वरची पडताळणी झाल्याशिवाय जोडलेली नाही."
    )

    _render_status_banner()

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

        if st.button("💾 Entry Gate सेव्ह करा", key=_widget_key(symbol, "save_entry")):
            new_settings = dict(settings)
            new_settings.update({
                "symbol_enabled": bool(symbol_enabled), "lots": int(lots),
                "timeframe_choice": timeframe_choice,
                "entry_rsi_gate_enabled": bool(entry_rsi_gate_enabled),
                "rsi_support_max": int(rsi_support_max), "rsi_resistance_min": int(rsi_resistance_min),
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
                    "या कालावधीत कोणतेही ऑर्डर्स नाहीत — strategy अजून प्रत्यक्ष चालू केलेली नसल्याने "
                    "(वर बघा) हे अपेक्षितच आहे."
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
                    "या कालावधीत कोणतेही बंद ट्रेड्स नाहीत — strategy अजून प्रत्यक्ष चालू केलेली नसल्याने "
                    "(वर बघा) हे अपेक्षितच आहे."
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
                    "या कालावधीत कुठलाही level touch तपासला गेलेला नाही — strategy अजून प्रत्यक्ष चालू "
                    "केलेली नसल्याने (वर बघा) हे अपेक्षितच आहे."
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
