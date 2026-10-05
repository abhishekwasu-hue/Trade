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
from safe_widgets import safe_number_input
import mcx_filters
import resolve_mcx_futures_instruments as mcx_resolver
from config import get_ist_today, get_ist_now
from database import (
    get_order_log_full, get_performance_summary, get_closed_trades_detail,
    get_live_vs_shadow_paper_pairs, get_live_positions_with_mtm, get_todays_mcx_live_pnl_and_count,
    get_todays_mcx_live_peak_pnl, OPTION_STRUCTURE_GROUP_SQL, get_margin_used_details, get_open_trade_levels, get_open_trade_chart_info, get_orders_with_account,
)
from page_performance import _render_group_breakdown, _build_recommendations, _entry_reason_text, _entry_reason_text_en, _EXIT_REASON_LABELS, _exit_reason_label_with_tag
from pdf_reports import generate_performance_report_pdf
from pnl_reports import generate_pnl_report, add_charges_to_trades_df
from charges import compare_with_upstox
from mcx_margin import compute_margin_rows, total_worst_case_margin, MARGIN_COLUMNS
from sr_dynamic import compute_dynamic_sr
from tradingview_chart import build_lightweight_chart_html, chart_indicator_controls, compute_chart_indicators
from position_chart import SL_KIND_LABELS, futures_lines, mcx_sl_price
from live_chart import infer_tf_seconds, render_live_charts
from bot_view import (
    TF_INTERVAL, align_supertrend, last_rsi, level_lines, rsi_gate_line, rsi_threshold_values, supertrend_directions,
    mcx_level_suffixes, supertrend_gate_line, supertrend_specs, zone_suffixes,
)
from signals import resample_to_1h, resample_to_4h
from trading_engine import close_trade_manually, set_manual_sl_override, clear_manual_sl_override, futures_price_for_pnl_level
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_GREEN, HDR_AMBER, HDR_PINK
from upstox_api import fetch_ltp_map, fetch_mcx_candles, get_total_capital, get_available_margin, fetch_brokerage_charges
from mcx_futures_trader import PRODUCT_TYPE
from mcx_quantity_check import is_mcx_live_quantity_verified

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
    return safe_number_input(label, value=settings.get(key), key=_widget_key(symbol, key), **kwargs)


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

    with st.expander("🛑 MCX-विशिष्ट Kill Switch (5 Commodities मिळून, ग्लोबलपेक्षा स्वतंत्र/कडक, LIVE + PAPER दोन्ही)", expanded=False):
        st.caption(
            "MCX ही brand-new रणनीती आहे (अजून एकही खरा LIVE order गेलेला नाही) — त्यामुळे ग्लोबल Kill "
            "Switch (Bot Dynamic SR Algo पान) सोबतच, इथे फक्त MCX साठीच स्वतंत्र, जास्त कडक मर्यादा — "
            "आजचा MCX-पुरताच तोटा किंवा एकाच वेळी उघडी असलेल्या commodities ची संख्या इथल्या मर्यादेपलीकडे "
            "गेली, तर नवीन MCX trade (LIVE आणि PAPER दोन्ही) आपोआप थांबतो (बाकी bots वर परिणाम नाही)."
        )
        if total_capital is None:
            st.warning("⚠️ एकूण capital मिळालं नाही (token/नेटवर्क तपासा) — तोटा-मर्यादा मोजता येत नाही, यावेळी Kill Switch नवीन MCX trades (LIVE + PAPER) आपोआप थांबवेल.")
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
                    f"त्याखाली घसरला. नवीन MCX trade (LIVE + PAPER) ब्लॉक केला जातोय."
                )
            else:
                st.error(f"🔴 MCX Kill Switch ट्रिप झालं आहे — आजचा MCX LIVE P&L ₹{total_pnl:,.0f}, उघडी positions {open_positions}. नवीन MCX trade (LIVE + PAPER) ब्लॉक केला जातोय.")
        else:
            # tripped=False इथे फक्त ks["enabled"] आणि total_capital दोन्ही असतील तरच पोहोचतं (वरच्या
            # `or` chain प्रमाणे) — म्हणजे max_daily_loss_amount इथे नेहमीच उपलब्ध असतो.
            lock_caption = f", profit-lock मजला ₹{locked_floor:,.0f}" if ks["profit_lock_enabled"] and locked_floor is not None else ""
            st.success(f"🟢 MCX Kill Switch OK — आजचा MCX LIVE P&L ₹{total_pnl:,.0f} (तोटा-मर्यादा ₹{-max_daily_loss_amount:,.0f}{lock_caption})")
            st.caption(f"उघडी positions {open_positions}/{ks['max_open_positions']}")

        mks_enabled = st.checkbox("MCX Kill Switch सक्रिय", value=ks["enabled"], key="mcx_ks_enabled")
        c1, c2 = st.columns(2)
        with c1:
            mks_max_loss_pct = safe_number_input(
                "कमाल दैनिक तोटा % (एकूण capital चा, फक्त MCX)", min_value=0.1, max_value=100.0,
                value=float(ks["max_daily_loss_pct"]), step=0.25, key="mcx_ks_max_loss_pct",
            )
        with c2:
            mks_max_open = safe_number_input(
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
            mks_profit_lock_pct = safe_number_input(
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
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Mcx मध्ये stop loss fixed pnl based दिसतो, futures च्या price वर
        # आधारित नाही का") — SL/Target futures भावातच: Entry भाव, SL भाव, Target भाव. (SL भाव = सध्या लागू SL: Manual Override > Trailing > मूळ SL, खाली.)
        _levels = get_open_trade_levels(combined_open["Trade ID"].tolist())

        def _level_price(tid, key):
            lv = _levels.get(tid)
            if not lv:
                return None
            level = lv["manual_sl_override_pnl"] if key == "sl_pnl_level" and lv.get("manual_sl_override_pnl") is not None else lv[key]
            price = futures_price_for_pnl_level(lv["net_credit"], level, lv["lots"], lv["lot_size"])
            return round(price, 2) if price is not None else None

        combined_open["Entry भाव"] = combined_open["Trade ID"].map(
            lambda t: round(abs(_levels[t]["net_credit"]), 2) if t in _levels and _levels[t]["net_credit"] is not None else None
        )
        # 🎓 "MCX SL भाव मध्ये trailing पण दाखवा" -- सध्या लागू SL (Manual Override > Trailing > मूळ SL), chart सारखाच position_chart.mcx_sl_price(); "SL प्रकार" स्तंभात कोणता ते.
        _sl_info = get_open_trade_chart_info(combined_open["Trade ID"].tolist())
        _sl_settings, _sl_refs = {}, {}

        def _sl_ref_price(sym):
            # PERCENT mode मध्ये trailing अंतर = सद्य किंमत x % (engine सारखं) -- फक्त तेव्हाच LTP आणतो; आणता आला नाही तर None (trailing दाखवत नाही).
            if sym not in _sl_refs:
                price = None
                try:
                    ok, resolved = _resolve_mcx_instrument_cached(token, sym)
                    if ok:
                        price = fetch_ltp_map(token, [resolved["instrument_key"]]).get(resolved["instrument_key"])
                except Exception:
                    price = None
                _sl_refs[sym] = price
            return _sl_refs[sym]

        def _sl_for(tid, sym):
            info = _sl_info.get(tid)
            if not info:
                return None, "SL"
            if sym not in _sl_settings:
                try:
                    _sl_settings[sym] = cloud_db.get_strategy_settings(STRATEGY_KEY, sym)
                except Exception:
                    _sl_settings[sym] = {}
            settings = _sl_settings[sym]
            needs_ref = settings.get("trailing_sl_enabled") and settings.get("sl_target_mode", "POINTS") == "PERCENT" and info.get("peak_pnl")
            price, kind = mcx_sl_price(info, settings, _sl_ref_price(sym) if needs_ref else None)
            return (round(price, 2) if price is not None else None), kind

        _sl_results = [_sl_for(tid, sym) for tid, sym in zip(combined_open["Trade ID"], combined_open["Symbol"])]
        combined_open["SL भाव"] = [r[0] for r in _sl_results]
        combined_open["SL प्रकार"] = [SL_KIND_LABELS.get(r[1], "") for r in _sl_results]
        combined_open["Target भाव"] = combined_open["Trade ID"].map(lambda t: _level_price(t, "target_pnl_level"))
        st.dataframe(combined_open, width="stretch", height=min(400, 60 + 35 * len(combined_open)))
        total_open_mtm = combined_open["MTM (Rs)"].dropna().sum()
        st.metric("सर्व Commodities मिळून एकूण Open MTM", f"₹{total_open_mtm:,.0f}")

        # 🎓 "Positions पानावर चार्ट: entry, stop, target ... रेषा" -- निवडलेल्या MCX position साठी futures चार्टवर Entry / SL / Target (futures भावात,
        # अचूक; Manual Override सेट असेल तर तोच SL, नारिंगी). Trailing SL (settings चालू असेल तर) 'SL (Trailing)' रेषा, live (बघा position_chart.py).
        with st.expander("📈 Position चार्ट (Entry / SL / Target रेषा)", expanded=False):
            _pc_tid = st.selectbox(
                "Position निवडा", options=combined_open["Trade ID"].tolist(),
                format_func=lambda tid: f"{combined_open.loc[combined_open['Trade ID'] == tid, 'Symbol'].values[0]} — {tid}",
                key="mcx_pos_chart_trade",
            )
            _pc_tf = st.radio("Timeframe", ["5minute", "15minute", "30minute"], index=0, horizontal=True, key="mcx_pos_chart_tf")
            _pc_sym = combined_open.loc[combined_open["Trade ID"] == _pc_tid, "Symbol"].values[0]
            _pc_token = st.session_state.get("token_input", "")
            _pc_info = get_open_trade_chart_info([_pc_tid]).get(_pc_tid)
            if not _pc_token:
                st.info("Upstox token उपलब्ध नाही -- चार्टसाठी वैध token लागतो.")
            elif _pc_info is None:
                st.info("या trade ची माहिती मिळाली नाही.")
            else:
                _pc_ok, _pc_resolved = _resolve_mcx_instrument_cached(_pc_token, _pc_sym)
                if not _pc_ok:
                    st.warning(f"⚠️ {_pc_sym} चा सध्याचा Futures contract सापडला नाही: {_pc_resolved}")
                else:
                    _pc_df = fetch_mcx_candles(_pc_token, _pc_resolved["instrument_key"], interval=_pc_tf, lookback_days=5)
                    if _pc_df is None or _pc_df.empty:
                        st.info("चार्टसाठी candle डेटा मिळाला नाही.")
                    else:
                        # 🎓 Trailing SL (settings चालू असेल तर) -- engine चंच compute_trailing_sl_level() वापरून; peak वाढला की रेषा live हलते (lines_fn, दर 3 सेकंदांनी).
                        _pc_settings = cloud_db.get_strategy_settings(STRATEGY_KEY, _pc_sym)
                        _pc_ref = float(_pc_df["close"].iloc[-1])

                        def _pc_lines(price, _tid=_pc_tid, _settings=_pc_settings, _ref=_pc_ref, _fallback=_pc_info):
                            fresh = get_open_trade_chart_info([_tid]).get(_tid) or _fallback
                            return futures_lines(fresh, _settings, price or _ref)

                        _pc_html = build_lightweight_chart_html(
                            _pc_df, symbol=_pc_sym, timeframe_label=_pc_tf, height=450, trade_lines=futures_lines(_pc_info, _pc_settings, _pc_ref),
                            live_tf_seconds=infer_tf_seconds(_pc_df),
                        )
                        if infer_tf_seconds(_pc_df):
                            render_live_charts(
                                "mcx_pos", [{
                                    "key": "mcx_pos", "html": _pc_html, "instrument_key": _pc_resolved["instrument_key"], "height": 500, "lines_fn": _pc_lines,
                                }],
                                _pc_token, "MCX",
                            )
                        else:
                            st.components.v1.html(_pc_html, height=500, scrolling=False)
                        st.caption(f"Entry वेळ: {_pc_info.get('entry_time')} · Contract: {_pc_resolved['trading_symbol']}. Trailing SL: settings मध्ये चालू असेल तर पिवळ्या 'SL (Trailing)' रेषेत (peak वाढला की हलते).")

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

            mcx_new_override_level = safe_number_input(
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
            closed_frames.append(df)

    if not closed_frames:
        st.info("या कालावधीत कुठल्याही MCX commodity चा एकही trade बंद झालेला नाही.")
    else:
        combined_closed = pd.concat(closed_frames, ignore_index=True).sort_values("Exit Time", ascending=False)
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Mcx Trade che brokerage and other charges add kele nahit,
        # upstox brokerage calculator nusar") — प्रत्येक trade चे Charges (entry+exit, charges.py चे
        # Upstox दर) आणि Net P&L स्तंभ.
        combined_closed = add_charges_to_trades_df(combined_closed)
        st.dataframe(combined_closed, width="stretch", height=min(400, 60 + 35 * len(combined_closed)))
        total_realized = combined_closed["Realized P&L"].sum()
        total_trade_charges = combined_closed["Charges"].sum()
        tm1, tm2, tm3 = st.columns(3)
        with tm1:
            st.metric(f"{ex_from} ते {ex_to}: Gross Realized P&L", f"₹{total_realized:,.0f}")
        with tm2:
            st.metric("एकूण Charges", f"₹{total_trade_charges:,.0f}")
        with tm3:
            st.metric("Net P&L", f"₹{total_realized - total_trade_charges:,.0f}")
        st.caption(f"एकूण {len(combined_closed)} बंद झालेले trades (सर्व commodities मिळून, नवीनतम आधी).")


@st.cache_data(ttl=60)
def _margin_rows_cached(access_token, lots_tuple):
    """Margin Calculator API कॉल्स (प्रत्येक commodity साठी BUY+SELL) 60 सेकंद cache — rerun वर पुन्हा-पुन्हा नाही."""
    return compute_margin_rows(access_token, MCX_SYMBOLS, dict(lots_tuple), product=PRODUCT_TYPE)


def _render_required_margin_panel():
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Commodity nusar Required Margin pn dakhwa") — प्रत्येक
    commodity साठी (सेव्ह केलेल्या Lots नुसार) BUY आणि SELL दोन्हीची आवश्यक margin, Upstox च्या अधिकृत Margin
    Calculator API वरून (bot trade उघडण्याआधी तोच वापरतो). बटण दाबल्यावरच API कॉल्स होतात."""
    token = st.session_state.get("token_input", "")
    if not token:
        st.info("Upstox token उपलब्ध नाही — sidebar मधून token टाका.")
        return
    st.caption(
        "प्रत्येक commodity चे सध्याचे (front-month) Futures contract, तिथे सेव्ह केलेल्या Lots नुसार — Upstox Margin "
        "Calculator (SPAN + Exposure). API ने आकडा दिला नाही तर रिकामा राहतो; अंदाज दाखवला जात नाही."
    )
    if st.button("💰 Required Margin मोजा / रिफ्रेश करा", key="mcxf_margin_calc_btn"):
        lots_by_symbol = {sym: int(cloud_db.get_strategy_settings(STRATEGY_KEY, sym).get("lots", 1)) for sym in MCX_SYMBOLS}
        with st.spinner("Upstox Margin Calculator ला विचारत आहे..."):
            rows = _margin_rows_cached(token, tuple(sorted(lots_by_symbol.items())))
        st.session_state["mcxf_margin_rows"] = rows
    rows = st.session_state.get("mcxf_margin_rows")
    if not rows:
        st.info("वरचं बटण दाबा.")
        return
    st.dataframe(pd.DataFrame(rows, columns=MARGIN_COLUMNS), width="stretch", hide_index=True)
    total = total_worst_case_margin(rows)
    available = get_available_margin(token)
    m1, m2 = st.columns(2)
    with m1:
        st.metric("सर्व commodities एकाच वेळी (मोठी बाजू) — एकूण Margin", f"₹{total:,.0f}" if total is not None else "N/A")
    with m2:
        st.metric("Upstox मधील उपलब्ध Margin", f"₹{available:,.0f}" if available is not None else "N/A")
    st.caption("एकूण = प्रत्येक commodity ची BUY/SELL पैकी मोठी margin जोडलेली (worst-case). Lots बदलल्यावर पुन्हा 'मोजा' दाबा.")


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

    with st.expander("💰 Required Margin — Commodity नुसार (BUY + SELL)", expanded=False):
        _render_required_margin_panel()

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
                    # 🎓 Bot view (MCX Futures bot) -- bot चे प्रत्यक्ष ACTIVE levels (+आजचे hits), 1H/4H Supertrend, RSI उंबरठे, गेट-स्थिती. डीफॉल्ट बंद.
                    bot_on = st.checkbox(
                        "Bot view: MCX Futures bot चे levels / Supertrend 1H+4H / गेट-स्थिती", value=False, key=_widget_key(symbol, "chart_bot_view"),
                    )
                    bot_lines, bot_gate_lines, bot_rsi_levels, bot_note = [], [], (40, 60), None
                    bot_st = {"1H": (None, None), "4H": (None, None)}
                    if bot_on:
                        try:
                            _bs = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)
                            _suffixes = zone_suffixes("MCX Futures", _bs)
                            _zones = cloud_db.get_market_zones(symbol, status="ACTIVE")
                            _hits = cloud_db.get_zone_hits_today_bulk(symbol, get_ist_today().strftime("%Y-%m-%d"))
                            _price = float(df_mcx["close"].iloc[-1])
                            _lv_sfx, _info_sfx = mcx_level_suffixes(_bs)      # level_engine SRV3 ⇒ bot चे SR V3 levels (Dynamic माहितीसाठी)
                            bot_lines = level_lines(
                                _zones, _lv_sfx, _hits, int(_bs.get("max_hits_per_zone", 2)), price=_price, role_by_price=True, max_distance_pct=4.0,
                                nearest_n=3, info_suffixes=_info_sfx,
                            )
                            bot_rsi_levels = tuple(rsi_threshold_values("MCX Futures", _bs))
                            _df30 = fetch_mcx_candles(token, resolved["instrument_key"], interval="30minute", lookback_days=20)
                            _frames, _rsi_by_tf = {}, {}
                            if _df30 is not None and not _df30.empty:
                                _df30 = _df30.copy()
                                for _c in ("volume", "oi"):
                                    if _c not in _df30.columns:
                                        _df30[_c] = 0
                                _frames = {"1H": resample_to_1h(_df30), "4H": resample_to_4h(_df30)}
                                for _sfx in _suffixes[:2]:
                                    _rsi_by_tf[_sfx] = last_rsi(_df30 if TF_INTERVAL.get(_sfx) else _frames["1H"])
                            _specs = supertrend_specs("MCX Futures", _bs)
                            for _sp in _specs:
                                bot_st[_sp["label"]] = align_supertrend(df_mcx, _frames.get(_sp["label"]), _sp["period"], _sp["multiplier"])
                            bot_gate_lines = [
                                ln for ln in (
                                    rsi_gate_line("MCX Futures", _bs, _rsi_by_tf),
                                    supertrend_gate_line("MCX Futures", _bs, supertrend_directions(_frames, _specs, get_ist_now()), _specs),
                                ) if ln
                            ]
                            bot_note = (
                                f"Bot view: MCX Futures bot ({'/'.join(_lv_sfx)}) चे ACTIVE levels — S/R, timeframe, ★strength, · आजचे trades/कमाल (फक्त खरे entries; role किंमत-बाजूवरून). "
                                "फिके = आजचे max-hits संपलेले; किंमतीपासून ±4% बाहेरचे लपवले. गेट-ओळीत फक्त RSI आणि Supertrend (Breakout / Min-Hold इ. नाहीत)."
                                + ("" if bot_lines else " ⚠️ ACTIVE levels सापडले नाहीत (आधी refresh_market_zones_mcx.py चालवा).")
                            )
                        except Exception as _bve:
                            bot_note = f"Bot view लोड करता आला नाही ({type(_bve).__name__}) — साधा चार्ट दाखवला आहे."
                    # 🎓 EMA / VWAP / Bollinger / ADX -- chart toolbar वर on/off बटणं (डीफॉल्ट सर्व बंद); periods इथे बदलता येतात.
                    ind_params = chart_indicator_controls(_widget_key(symbol, "chart_ind"))
                    chart_indicators = compute_chart_indicators(df_mcx, intraday=chart_tf != "day", **ind_params)
                    tv_html = build_lightweight_chart_html(
                        df_mcx, symbol=symbol, timeframe_label=CHART_TIMEFRAME_OPTIONS[chart_tf],
                        rsi_series=rsi_series, sr_levels=None if bot_on else sr_levels, height=550, indicators=chart_indicators,
                        live_tf_seconds=infer_tf_seconds(df_mcx), trade_lines=bot_lines or None, rsi_levels=bot_rsi_levels,
                        supertrend_1h_series=bot_st["1H"][0], supertrend_1h_direction=bot_st["1H"][1],
                        supertrend_4h_series=bot_st["4H"][0], supertrend_4h_direction=bot_st["4H"][1],
                    )
                    # 🎓 Live updates (REST LTP, दर 3 सेकंदांनी; बघा live_chart.py). Daily असेल तर स्थिर चार्ट.
                    if infer_tf_seconds(df_mcx):
                        render_live_charts(
                            f"mcx_chart_{symbol}", [{"key": f"mcx_chart_{symbol}", "html": tv_html, "instrument_key": resolved["instrument_key"], "height": 600}],
                            token, "MCX",
                        )
                    else:
                        st.components.v1.html(tv_html, height=600, scrolling=False)
                    for _gl in bot_gate_lines:
                        st.caption(_gl)
                    if bot_note:
                        st.caption(bot_note)
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
        _mrow = next((r for r in (st.session_state.get("mcxf_margin_rows") or []) if r.get("Commodity") == symbol), None)
        if _mrow and _mrow.get("BUY / lot (Rs)") is not None and _mrow.get("SELL / lot (Rs)") is not None:
            st.caption(
                f"💰 1 lot ≈ BUY ₹{_mrow['BUY / lot (Rs)']:,.0f} / SELL ₹{_mrow['SELL / lot (Rs)']:,.0f} — "
                f"तुमचे {int(lots)} lots ≈ BUY ₹{_mrow['BUY / lot (Rs)'] * int(lots):,.0f} / SELL ₹{_mrow['SELL / lot (Rs)'] * int(lots):,.0f} "
                "(वरच्या 'Required Margin' expander चा शेवटचा आकडा)."
            )
        else:
            st.caption("💰 1 lot ला किती margin लागते हे बघण्यासाठी वरच्या 'Required Margin' expander मध्ये 'मोजा' दाबा.")
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Max trade on same level yachi setting sidhha द्या,
        # default 2") — आधी ही मर्यादा hardcoded (2) आणि "बदलण्याजोगी नाही" असं स्पष्ट म्हटलेलं होतं —
        # आता इतर सर्व bots सारखीच Dashboard वरून बदलता येते, डीफॉल्ट मात्र आधीसारखाच 2.
        max_hits_per_zone = _number_input(
            "🔁 Max Trades on Same Level (एकाच S/R level वर एका दिवसात कमाल किती entries)",
            settings, "max_hits_per_zone", symbol, min_value=1, max_value=10, step=1,
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
        # 🎓 वापरकर्त्याचा निर्णय ("MCX bot मध्ये सुद्धा SR V3 levels — Setting ने निवड") — बघा mcx_futures_trader.LEVEL_ENGINES.
        sub_header("🧱 Level engine (levels कुठून)", HDR_TEAL)
        _LE_OPTIONS = {
            "DYNAMIC": "जुने Dynamic S/R (30M/60M) — डीफॉल्ट",
            "SRV3_SHADOW": "🧪 जुने + SR V3 PAPER shadow (तुलना)",
            "SRV3": "SR V3 levels (मुख्य bot)",
        }
        _le_keys = list(_LE_OPTIONS.keys())
        _le_stored = settings.get("level_engine", "DYNAMIC")
        level_engine = st.radio(
            "Bot कोणत्या levels वर touch तपासेल?", _le_keys, format_func=lambda k: _LE_OPTIONS[k], horizontal=True,
            index=_le_keys.index(_le_stored) if _le_stored in _le_keys else 0, key=_widget_key(symbol, "level_engine"),
        )
        st.caption(
            "SR V3 (MCX): 15M+30M+1H swing pivots, PDH/PDL/PWH/PWL (सत्र-अंत 23:30), gaps — फक्त grade A/B, किंमतीपासून 3% आत, "
            "दर 5 मिनिटांनी ताजे. 'PAPER shadow' मध्ये मूळ bot जुन्याच levels वर चालतो आणि शेजारी SR V3 levels वर तेच नियम निव्वळ "
            "PAPER (वेगळा source, Performance वर तुलना). MCX चा जुना डेटा नसल्याने backtest झालेला नाही — आधी shadow ने तपासा. "
            "V3.2: मागच्या 5 दिवसांत भावाने 6 पेक्षा जास्त वेळा ओलांडलेला (range च्या मधला, 'चुंबक') level grade C — त्यावर trade नाही."
        )
        srv3_grade_a_only = st.checkbox(
            "SR V3: फक्त grade A levels वर trade (score ≥ 65; बंद = A+B)", value=bool(settings.get("srv3_grade_a_only", False)),
            key=_widget_key(symbol, "srv3_grade_a_only"), disabled=level_engine == "DYNAMIC",
        )
        if level_engine == "SRV3" and settings.get("trading_mode", "PAPER") != "PAPER":
            st.warning("⚠️ SR V3 levels backtest न झालेले आहेत आणि या symbol चा trading mode PAPER नाही — खरे orders SR V3 levels वर जातील.")

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

        st.markdown("---")
        sub_header("📊 Supertrend Trend Filter (1H + 4H)", HDR_ORANGE)
        _ST_MODES = {
            "off": "बंद",
            "both_against": "1H आणि 4H दोन्ही विरुद्ध असतील तर थांबव (जुना नियम)",
            "htf_against": "4H विरुद्ध असेल तर थांबव (डीफॉल्ट — trend च्या विरुद्ध trade नाही)",
        }
        _st_keys = list(_ST_MODES.keys())
        _st_stored = mcx_filters.effective_supertrend_mode(settings)
        supertrend_filter_mode = st.radio(
            "Supertrend Filter mode", _st_keys, format_func=lambda k: _ST_MODES[k],
            index=_st_keys.index(_st_stored) if _st_stored in _st_keys else 0, key=_widget_key(symbol, "supertrend_filter_mode"),
        )
        entry_supertrend_filter_enabled = supertrend_filter_mode != "off"
        st.caption(
            "**दोन्ही विरुद्ध:** किंमत 1H **आणि** 4H दोन्ही Supertrend च्या **खाली** असेल तर Bullish trade नाही. दोन्हींच्या **वर** असेल तर "
            "Bearish trade नाही. **4H विरुद्ध:** फक्त 4H Supertrend उलट दिशेला असला तरी trade नाही. "
            "हा filter Breakout सकट सर्व entries ला लागू होतो. दिशा शेवटच्या **पूर्ण झालेल्या** 1H/4H candle ची घेतली जाते "
            "(4H candles सकाळी ९:०० पासून). डेटा मिळाला नाही तर काहीच अडवलं जात नाही. "
            "थांबवलेला touch Signal Log मध्ये `SKIPPED_MCX_TREND_FILTER` दिसेल (हा max-hits मोजत नाही). "
            "कुठला mode निवडायचा ते ठरवण्याआधी `mcx_trade_replay.py` चा निकाल पाहा."
        )
        st1, st2, st3, st4 = st.columns(4)
        with st1:
            supertrend_1h_period = _number_input(
                "1H ATR Period", settings, "supertrend_1h_period", symbol,
                min_value=2, max_value=50, step=1, disabled=not entry_supertrend_filter_enabled,
            )
        with st2:
            supertrend_1h_multiplier = _number_input(
                "1H Multiplier", settings, "supertrend_1h_multiplier", symbol,
                min_value=0.5, max_value=10.0, step=0.5, format="%.1f", disabled=not entry_supertrend_filter_enabled,
            )
        with st3:
            supertrend_4h_period = _number_input(
                "4H ATR Period", settings, "supertrend_4h_period", symbol,
                min_value=2, max_value=50, step=1, disabled=not entry_supertrend_filter_enabled,
            )
        with st4:
            supertrend_4h_multiplier = _number_input(
                "4H Multiplier", settings, "supertrend_4h_multiplier", symbol,
                min_value=0.5, max_value=10.0, step=0.5, format="%.1f", disabled=not entry_supertrend_filter_enabled,
            )

        st.markdown("---")
        sub_header("🧊 SL नंतरचा Cooldown आणि Cascade Filter", HDR_ORANGE)
        cd1, cd2 = st.columns(2)
        with cd1:
            sl_cooldown_minutes = _number_input(
                "SL तोट्यानंतर cooldown (मिनिटं, 0 = बंद)", settings, "sl_cooldown_minutes", symbol, min_value=0, max_value=240, step=15,
            )
        with cd2:
            sl_level_direction_block_enabled = st.checkbox(
                "आज SL लागलेल्या level वर त्याच दिशेने पुन्हा entry नाही (डीफॉल्ट चालू)",
                value=bool(settings.get("sl_level_direction_block_enabled", True)),
                key=_widget_key(symbol, "sl_level_direction_block_enabled"),
            )
        cascade_filter_enabled = st.checkbox(
            "Broken-support cascade filter (डीफॉल्ट बंद)",
            value=bool(settings.get("cascade_filter_enabled", False)),
            key=_widget_key(symbol, "cascade_filter_enabled"),
        )
        st.caption(
            "**Cooldown:** SL किंवा Trailing-SL **तोट्याने** बंद झाल्यावर या symbol वर इतकी मिनिटं नवीन entry घेतली जात नाही. "
            "**त्याच level/दिशा:** आज ज्या level वर ज्या दिशेने SL लागला, त्या level वर (±0.05%) त्याच दिशेने आज पुन्हा entry नाही. "
            "**Cascade:** मागच्या 2 sessions मध्ये एखादा support 30M close ने तुटला असेल, तर त्याच्या खालच्या level वर LONG फक्त "
            "30M bullish CHoCH नंतर घेतला जातो. CHoCH म्हणजे break नंतरचा शेवटचा lower-high 30M close ने वर तुटणं. Resistance साठी उलट. "
            "Breakout trades ना cascade लागू नाही. Signal Log मध्ये हे touch `SKIPPED_SL_COOLDOWN` / "
            "`SKIPPED_SL_LEVEL_SAME_DIRECTION` / `SKIPPED_CASCADE_NO_CHOCH` म्हणून दिसतील. यातलं कुठलंही max-hits मध्ये मोजलं जात नाही."
        )

        st.markdown("---")
        sub_header("🔄 Contract Roll (expiry आधी पुढचा contract)", HDR_ORANGE)
        roll_trading_days_before_expiry = _number_input(
            "उरलेले ट्रेडिंग दिवस ≤ इतके झाले की पुढचा contract", settings, "roll_trading_days_before_expiry", symbol,
            min_value=1, max_value=15, step=1,
        )
        _stag = mcx_resolver.STAGGERED_DELIVERY_TRADING_DAYS.get(symbol, 0)
        st.caption(
            "ट्रेडिंग दिवस म्हणजे आज ते expiry (दोन्ही धरून) सोम–शुक्र. MCX सुट्ट्या वजा केलेल्या नाहीत, म्हणून 1-2 दिवसांची सवलत ठेवा. "
            + (f"{symbol} compulsory-delivery आहे: MCX चा staggered delivery period हे expiry धरून शेवटचे **{_stag}** ट्रेडिंग दिवस. "
               "त्या काळात delivery-period margin (किमान 25%) लागतो, आणि broker positions square-off करतात. म्हणून इथे कितीही कमी आकडा दिला, "
               f"तरी roll किमान **{_stag + 1}** दिवसांवर होतो (period सुरू होण्याआधी 1 ट्रेडिंग दिवस). "
               if _stag else f"{symbol} cash-settled आहे (delivery नाही). फक्त expiry च्या आधी liquidity पुढच्या contract कडे सरकते, म्हणून roll. ")
            + "Roll झाल्यावर Telegram सूचना येते. नव्या contract चे zones तयार होईपर्यंत त्या symbol वर नवीन entry घेतली जात नाही. "
            "उघड्या positions चे exits त्यांच्याच contract वर होतात."
        )

        st.markdown("---")
        sub_header("📌 Level Memory (महत्त्वाचे levels त्याच किंमतीवर)", HDR_ORANGE)
        lm1, lm2 = st.columns(2)
        with lm1:
            level_memory_enabled = st.checkbox(
                "Level memory चालू (डीफॉल्ट चालू)", value=bool(settings.get("level_memory_enabled", True)),
                key=_widget_key(symbol, "level_memory_enabled"),
            )
        with lm2:
            level_memory_retire_days = _number_input(
                "इतके दिवस किंमत जवळ आली नाही तर जुना level निवृत्त", settings, "level_memory_retire_days", symbol,
                min_value=5, max_value=120, step=5, disabled=not level_memory_enabled,
            )
        st.caption(
            "रोजच्या Dynamic S/R refresh मध्ये जुने levels **त्याच किंमतीवर** ठेवले जातात. ताजी गणना जुन्या level च्या जवळ आली (साधारण 0.5×ATR, "
            "किंमतीच्या 0.08–0.40%) तर जुनीच किंमत कायम राहते. ताज्या top-5 मध्ये नसलेला level पण ठेवला जातो, जर किंमत गेल्या इतक्या दिवसांत "
            "त्याच्याजवळ आली असेल. तुटलेला support resistance बनतो, तो पुसला जात नाही. भावापासून 15% पेक्षा दूरचे levels निवृत्त होतात. "
            "प्रत्येक timeframe साठी कमाल 12 levels. Contract roll झाल्यावर जुने levels विसरले जातात. बदल पुढच्या रात्रीच्या refresh पासून लागू होतो."
        )

        st.markdown("---")
        sub_header("⏱️ Minimum Level-Hold Duration (पहिल्या trade साठी)", HDR_ORANGE)
        entry_min_hold_gate_enabled = st.checkbox(
            "Minimum Level-Hold सक्रिय (डीफॉल्ट चालू)",
            value=bool(settings.get("entry_min_hold_gate_enabled", True)),
            key=_widget_key(symbol, "entry_min_hold_gate_enabled"),
        )
        st.caption(
            "किंमत level ला पहिल्यांदा टेकल्यावर लगेच trade नाही -- किमान खालील मिनिटं (1-मिनिट candles वर) level जवळ सलग टिकली तरच entry. "
            "Breakout trades ला लागू नाही. 1-मिनिट डेटा मिळाला नाही तर काहीच अडवलं जात नाही. थांबवलेला touch Signal Log मध्ये "
            "`SKIPPED_MIN_HOLD_DURATION` दिसेल (हा max-hits मोजत नाही)."
        )
        mh1, mh2 = st.columns(2)
        with mh1:
            entry_min_hold_minutes = _number_input(
                "किमान मिनिटं (level जवळ टिकणं)", settings, "entry_min_hold_minutes", symbol,
                min_value=1, max_value=30, step=1, disabled=not entry_min_hold_gate_enabled,
            )
        with mh2:
            entry_min_hold_first_trade_only = st.checkbox(
                "फक्त पहिल्या trade ला लागू (त्याच level+role वर आज खरा trade झाल्यावर नाही)",
                value=bool(settings.get("entry_min_hold_first_trade_only", True)),
                key=_widget_key(symbol, "entry_min_hold_first_trade_only"),
                disabled=not entry_min_hold_gate_enabled,
            )

        if st.button("💾 Entry Gate सेव्ह करा", key=_widget_key(symbol, "save_entry")):
            new_settings = dict(settings)
            new_settings.update({
                "symbol_enabled": bool(symbol_enabled), "lots": int(lots),
                "max_hits_per_zone": int(max_hits_per_zone),
                "timeframe_choice": timeframe_choice,
                "level_engine": level_engine, "srv3_grade_a_only": bool(srv3_grade_a_only),
                "bullish_entry_enabled": bool(bullish_entry_enabled), "bearish_entry_enabled": bool(bearish_entry_enabled),
                "entry_rsi_gate_enabled": bool(entry_rsi_gate_enabled),
                "rsi_support_max": int(rsi_support_max), "rsi_resistance_min": int(rsi_resistance_min),
                "entry_breakout_gate_enabled": bool(entry_breakout_gate_enabled),
                "breakout_lookback_candles": int(breakout_lookback_candles),
                "breakout_tolerance_pct": float(breakout_tolerance_pct),
                "entry_supertrend_filter_enabled": bool(entry_supertrend_filter_enabled),
                "supertrend_filter_mode": supertrend_filter_mode,
                "sl_cooldown_minutes": int(sl_cooldown_minutes),
                "sl_level_direction_block_enabled": bool(sl_level_direction_block_enabled),
                "cascade_filter_enabled": bool(cascade_filter_enabled),
                "roll_trading_days_before_expiry": int(roll_trading_days_before_expiry),
                "level_memory_enabled": bool(level_memory_enabled),
                "level_memory_retire_days": int(level_memory_retire_days),
                "supertrend_1h_period": int(supertrend_1h_period), "supertrend_1h_multiplier": float(supertrend_1h_multiplier),
                "supertrend_4h_period": int(supertrend_4h_period), "supertrend_4h_multiplier": float(supertrend_4h_multiplier),
                "entry_min_hold_gate_enabled": bool(entry_min_hold_gate_enabled),
                "entry_min_hold_minutes": int(entry_min_hold_minutes),
                "entry_min_hold_first_trade_only": bool(entry_min_hold_first_trade_only),
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

        next_level_target_enabled = st.checkbox(
            "🎯 Target = पुढचा S/R level (डीफॉल्ट बंद)", value=bool(settings.get("next_level_target_enabled", False)),
            key=_widget_key(symbol, "next_level_target_enabled"),
        )
        st.caption(
            "चालू केल्यास LONG चा target = entry च्या **वरचा** पुढचा level, SHORT चा = **खालचा** पुढचा level. Bot ज्या levels वर trade करतो तेच "
            "(Level engine प्रमाणे). पुढचा level entry पासून किमान 0.2% आणि SL च्या निम्म्याइतका दूर हवा. तसा नसेल तर वरचा नेहमीचा target वापरला "
            "जातो. SL आणि Trailing बदलत नाहीत. Telegram आणि Signal Log मध्ये target चा level दिसतो."
        )

        if st.button("💾 Exit Gate सेव्ह करा", key=_widget_key(symbol, "save_exit")):
            new_settings = dict(settings)
            new_settings.update({
                "sl_target_mode": sl_target_mode,
                "sl_points": float(sl_points), "target_points": float(target_points),
                "sl_pct": float(sl_pct), "target_pct": float(target_pct),
                "trailing_sl_enabled": bool(trailing_sl_enabled),
                "trailing_distance_points": float(trailing_distance_points),
                "trailing_pct": float(trailing_pct),
                "next_level_target_enabled": bool(next_level_target_enabled),
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
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Mcx che performance Mcx tab madhech disayla pahije, user
        # friendly thewa") — आधी सर्व-MCX-एकत्र दृश्य फक्त Performance पानावरच्या checkbox मागे होतं. आता
        # इथेच, सुरुवातीलाच स्पष्ट निवड — default "सर्व Commodities एकत्र" (एकत्रित रिपोर्ट + PDF हवाच असतो).
        perf_scope_choice = st.radio(
            "कशाचा रिपोर्ट?", ["🌐 सर्व Commodities एकत्र", f"📌 फक्त {symbol}"], horizontal=True, key="mcxf_perf_scope",
        )
        perf_all_combined = perf_scope_choice.startswith("🌐")
        if perf_all_combined:
            perf_symbol, perf_symbol_label, perf_symbol_title = list(MCX_SYMBOLS), "ALL_MCX", "All MCX Commodities"
        else:
            perf_symbol, perf_symbol_label, perf_symbol_title = symbol, symbol, symbol
        sub_header(f"📊 {'सर्व MCX Commodities' if perf_all_combined else symbol} — Performance Report", HDR_PINK)
        st.caption(
            "वर निवडलेल्या commodity साठी (किंवा सर्व एकत्र) Performance पानासारखाच संपूर्ण विश्लेषण (Strategy/Timeframe breakdown, प्रत्येक Trade चं Entry+Exit "
            "कारण, शिफारसी) आणि तोच प्रिंट-योग्य PDF (इंग्रजीत — PDF fonts मध्ये मराठी glyphs उपलब्ध नाहीत). "
            "'Option Structure नुसार' विभाग MCX Futures ला लागू होत नाही (इथे options नाहीत, सरळ futures) — "
            "तो रिकामाच दिसेल, ते अपेक्षितच आहे."
        )
        perf_mode_choice = st.radio(
            "दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key=_widget_key("ALL", "perf_mode_filter"),
        )
        perf_mode_f = None if perf_mode_choice == "सर्व" else ("LIVE" if "LIVE" in perf_mode_choice else "PAPER")

        perf_today = get_ist_today()
        perf_range_choice = st.radio(
            "कालावधी", ["आज", "गेले 7 दिवस", "गेला महिना", "संपूर्ण इतिहास", "कस्टम रेंज"], horizontal=True,
            key=_widget_key("ALL", "perf_range"),
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
                perf_from = st.date_input("पासून", value=perf_today - datetime.timedelta(days=30), key=_widget_key("ALL", "perf_from"))
            with pc2:
                perf_to = st.date_input("पर्यंत", value=perf_today, key=_widget_key("ALL", "perf_to"))

        if perf_from > perf_to:
            st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
        else:
            st.caption(f"निवडलेली रेंज: {perf_from} ते {perf_to}")
            summary = get_performance_summary(perf_symbol, mode_filter=perf_mode_f, start_date=perf_from, end_date=perf_to)
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
                    st.metric(
                        "Win Rate (शुद्ध SL/Target)",
                        f"{summary['win_rate']}%" if summary.get("win_rate") is not None else "N/A",
                        help="फक्त शुद्ध SL/Target ने बंद झालेल्या trades वर. Trailing SL/Breakeven/EOD/Manual ने बंद झालेले "
                             "यात धरत नाहीत — म्हणून असे trades असतील तर 'N/A' दिसतं (बग नाही).",
                    )
                    if summary.get("win_rate") is None and summary.get("win_rate_all_exits") is not None:
                        st.caption(f"सर्व exits धरून: {summary['win_rate_all_exits']}% ({summary['win_count']} नफ्यात / {summary['loss_count']} तोट्यात)")
                with scol3:
                    st.metric("Gross P&L", f"₹{summary['total_pnl']:,.0f}")
                with scol4:
                    st.metric("ROI %", f"{summary['roi_pct']}%" if summary.get("roi_pct") is not None else "N/A")

            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (MCX brokerage/charges) — Upstox दरांनुसार (charges.py):
            # Gross − Charges = Net, आणि Charges चं घटकनिहाय breakdown.
            _, perf_pnl_totals = generate_pnl_report(perf_symbol, "Daily", perf_from, perf_to, mode_filter=perf_mode_f)
            if perf_pnl_totals.get("total_orders", 0) > 0 or perf_pnl_totals.get("total_trades", 0) > 0:
                ncol1, ncol2, ncol3 = st.columns(3)
                with ncol1:
                    st.metric("Gross P&L (charges आधी)", f"₹{perf_pnl_totals['gross_pnl']:,.0f}")
                with ncol2:
                    st.metric("एकूण Charges", f"₹{perf_pnl_totals['total_charges']:,.0f}")
                with ncol3:
                    st.metric("Net P&L (charges नंतर)", f"₹{perf_pnl_totals['net_pnl']:,.0f}")
                _bd = perf_pnl_totals.get("charges_breakdown") or {}
                if _bd:
                    with st.expander("🧾 Charges चं breakdown (Upstox दरांनुसार)"):
                        st.dataframe(
                            pd.DataFrame([
                                {"घटक": "Brokerage (₹20 किंवा 0.05%, जे कमी / order)", "रक्कम (₹)": _bd.get("brokerage", 0.0)},
                                {"घटक": "CTT (0.01%, फक्त SELL)", "रक्कम (₹)": _bd.get("stt", 0.0)},
                                {"घटक": "Exchange Txn Charge (MCX 0.0021%)", "रक्कम (₹)": _bd.get("exchange_txn", 0.0)},
                                {"घटक": "SEBI Turnover Fee (0.0001%)", "रक्कम (₹)": _bd.get("sebi_fee", 0.0)},
                                {"घटक": "Stamp Duty (0.002%, फक्त BUY)", "रक्कम (₹)": _bd.get("stamp_duty", 0.0)},
                                {"घटक": "GST 18% (brokerage+exchange+SEBI वर)", "रक्कम (₹)": _bd.get("gst", 0.0)},
                                {"घटक": "एकूण Charges", "रक्कम (₹)": perf_pnl_totals["total_charges"]},
                            ]),
                            width="stretch", hide_index=True,
                        )
                        st.caption(
                            f"{perf_pnl_totals.get('total_orders', 0)} orders वर आधारित. दर: Upstox brokerage calculator "
                            "(MCX Commodity Futures) — charges.py. निवडलेल्या कालावधीत ज्या दिवशी order झाले त्या "
                            "दिवसांचे charges, आणि ज्या दिवशी trade बंद झाला त्या दिवसांचा Gross P&L मोजलेला आहे."
                        )

            # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Upstox चे खरे brokerage calculator") — वरचे Charges आपल्या
            # स्वतःच्या दरांवरून (charges.py) मोजलेले आहेत; हा विभाग त्याच orders साठी Upstox च्या अधिकृत
            # Brokerage API शी ते ताडून फरक दाखवतो. बटण दाबल्यावरच API कॉल्स (कमाल 10 orders).
            with st.expander("🔎 Charges पडताळणी — Upstox Brokerage API शी तुलना"):
                st.caption(
                    "सर्वात अलीकडचे 10 orders (निवडलेल्या कालावधीतले) — आपल्या दरांनी मोजलेले charges विरुद्ध Upstox चे खरे. "
                    "दर बदलले (Budget/exchange परिपत्रक) तर इथे फरक दिसेल. Upstox कडून आकडा न आल्यास रकाना रिकामा राहतो."
                )
                _tok = st.session_state.get("token_input", "")
                if not _tok:
                    st.info("Upstox token उपलब्ध नाही — sidebar मधून token टाका.")
                elif st.button("🔎 Upstox शी तुलना करा", key="mcxf_charges_verify_btn"):
                    _ord = get_orders_with_account(perf_symbol, perf_from, perf_to, mode_filter=perf_mode_f)
                    with st.spinner("Upstox Brokerage API ला विचारत आहे..."):
                        _rows, _sum = compare_with_upstox(
                            _ord, lambda k, q, p, side, prod: fetch_brokerage_charges(_tok, k, q, p, side, prod),
                            max_orders=10, product=PRODUCT_TYPE,
                        )
                    st.session_state["mcxf_charges_verify"] = (_rows, _sum)
                _res = st.session_state.get("mcxf_charges_verify")
                if _res:
                    _rows, _sum = _res
                    if not _rows:
                        st.info("तुलना करण्यासारखे orders (instrument + किंमत असलेले) या कालावधीत सापडले नाहीत.")
                    else:
                        v1, v2, v3 = st.columns(3)
                        with v1:
                            st.metric("तपासलेले orders", _sum["checked"])
                        with v2:
                            st.metric("Upstox कडून आकडा आलेले", _sum["compared"])
                        with v3:
                            st.metric("सरासरी फरक / order", f"₹{_sum['avg_abs_diff']:,.2f}" if _sum["avg_abs_diff"] is not None else "N/A")
                        st.dataframe(pd.DataFrame(_rows), width="stretch", hide_index=True)
                        if _sum["compared"] == 0:
                            st.warning("Upstox Brokerage API ने कुठल्याही order साठी आकडा दिला नाही (token/प्रतिसाद तपासा).")

            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (ROI% साठी 'margin used' अवास्तव मोठा आला) — ROI% चा
            # भाजक (peak concurrent margin) नेमका कसा आला हे पारदर्शक दिसावं म्हणून: peak ची वेळ, त्या क्षणी
            # उघडे असलेले trades, आणि प्रत्येकाची margin Upstox API ची आहे की ढोबळ अंदाजाची.
            _md = get_margin_used_details(perf_symbol, mode_filter=perf_mode_f, start_date=perf_from, end_date=perf_to)
            if _md is not None:
                with st.expander("🔍 Margin गणना तपशील (ROI% चा भाजक)"):
                    mm1, mm2, mm3 = st.columns(3)
                    with mm1:
                        st.metric("वापरलेली Margin (peak)", f"₹{_md['margin_used']:,.0f}")
                    with mm2:
                        st.metric("Peak ची वेळ", str(_md["peak_time"])[:19] if _md["peak_time"] is not None else "N/A")
                    with mm3:
                        st.metric("त्या क्षणी उघडे trades", int(_md["trades"]["open_at_peak"].sum()))
                    _mt = _md["trades"]
                    st.caption(
                        f"एकूण {len(_mt)} trades — Upstox Margin API ची margin: {int((_mt['margin_source'] == 'API').sum())}, "
                        f"ढोबळ अंदाज (max_loss×lots×lot_size): {int((_mt['margin_source'] == 'ESTIMATE').sum())}. "
                        "ROI% = Realized P&L ÷ Peak margin (एकाच वेळी उघड्या असलेल्या trades ची बेरीज)."
                    )
                    _cols = {"trade_id": "Trade ID", "symbol": "Symbol", "lots": "Lots", "lot_size": "Lot Size",
                             "trade_margin": "Margin (₹)", "margin_source": "स्रोत", "entry_time": "Entry", "exit_time": "Exit"}
                    st.markdown("**त्या Peak क्षणी उघडे असलेले trades**")
                    _peak_df = _mt[_mt["open_at_peak"]][list(_cols)].rename(columns=_cols)
                    st.dataframe(_peak_df, width="stretch", hide_index=True) if not _peak_df.empty else st.caption("—")
                    st.markdown("**सर्वात मोठी margin असलेले 10 trades**")
                    st.dataframe(
                        _mt.sort_values("trade_margin", ascending=False).head(10)[list(_cols)].rename(columns=_cols),
                        width="stretch", hide_index=True,
                    )

            perf_by_symbol_pdf = None
            if perf_all_combined:
                sub_header("🛢️ Commodity नुसार तुलना", HDR_TEAL)
                perf_by_symbol_pdf = _render_group_breakdown(
                    perf_symbol, "symbol", perf_mode_f, perf_from, perf_to, "Commodity-wise P&L",
                )

            st.markdown("---")
            perf_tab1, perf_tab2, perf_tab3 = st.tabs(
                ["🎯 Algo Strategy नुसार", "⏱️ Timeframe नुसार", "🧩 Option Structure नुसार"]
            )
            with perf_tab1:
                perf_by_source = _render_group_breakdown(perf_symbol, "source", perf_mode_f, perf_from, perf_to, "Strategy-wise P&L")
            with perf_tab2:
                perf_by_timeframe = _render_group_breakdown(perf_symbol, "entry_timeframe", perf_mode_f, perf_from, perf_to, "Timeframe-wise P&L")
            with perf_tab3:
                perf_by_structure = _render_group_breakdown(
                    perf_symbol, OPTION_STRUCTURE_GROUP_SQL, perf_mode_f, perf_from, perf_to,
                    "Option Structure-wise P&L (MCX Futures साठी लागू नाही)",
                )

            sub_header("📋 Trade Log — प्रत्येक Trade चं Entry व Exit कारण", HDR_PURPLE)
            perf_trade_log_df = get_closed_trades_detail(perf_symbol, mode_filter=perf_mode_f, start_date=perf_from, end_date=perf_to)
            perf_trade_log_df = add_charges_to_trades_df(perf_trade_log_df)
            perf_trade_log_pdf_df = None
            if perf_trade_log_df.empty:
                st.caption("या कालावधीत कोणतेही बंद ट्रेड्स नाहीत.")
            else:
                perf_trade_log_display = perf_trade_log_df.copy()
                perf_trade_log_display["Entry Reason"] = perf_trade_log_display.apply(_entry_reason_text, axis=1)
                perf_trade_log_display["Exit Reason"] = perf_trade_log_display["exit_reason"].map(lambda r: _EXIT_REASON_LABELS.get(r, r))
                perf_trade_log_display["Exit Reason (नेमकं कारण)"] = perf_trade_log_display["exit_reason_detail"].fillna("—")
                perf_trade_log_display = perf_trade_log_display[[
                    "Trade ID", "Symbol", "Entry Time", "Entry Reason", "Exit Time", "Exit Reason",
                    "Exit Reason (नेमकं कारण)", "Realized P&L", "Charges", "Net P&L", "Margin", "mode",
                ]].rename(columns={"mode": "Mode", "Margin": "Margin (Rs)"})
                st.dataframe(perf_trade_log_display, width="stretch", height=350, hide_index=True)
                perf_trade_log_csv = perf_trade_log_display.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Trade Log CSV डाऊनलोड करा (Entry+Exit कारणांसकट)", data=perf_trade_log_csv,
                    file_name=f"{perf_symbol_label}_MCX_TradeLog_Reasons_{perf_from}_{perf_to}.csv",
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
                    "Trade ID", "Symbol", "Entry Time", "Entry Reason", "Exit Time", "Exit Reason",
                    "Exit Reason Detail", "Realized P&L", "Charges", "Net P&L", "Margin", "mode", "Entry Timeframe",
                ]].rename(columns={"mode": "Mode"})

            perf_slippage_pairs_df = (
                get_live_vs_shadow_paper_pairs(perf_symbol, perf_from, perf_to) if perf_mode_f is None else pd.DataFrame()
            )

            st.markdown("---")
            sub_header("📄 संपूर्ण Performance Report (PDF)", HDR_AMBER)
            if st.button("📄 Performance Report PDF तयार करा", key=_widget_key(symbol, "perf_pdf_generate")):
                mode_label_en = {"सर्व": "All", "फक्त LIVE": "LIVE only", "फक्त PAPER": "PAPER only"}.get(perf_mode_choice, perf_mode_choice)
                pdf_cache_key = (perf_symbol_label, mode_label_en, str(perf_from), str(perf_to))
                perf_pdf_state_key = _widget_key(perf_symbol_label, "perf_pdf_cache_key")
                perf_pdf_bytes_key = _widget_key(perf_symbol_label, "perf_pdf_bytes")
                if st.session_state.get(perf_pdf_state_key) == pdf_cache_key and st.session_state.get(perf_pdf_bytes_key):
                    st.info("ℹ️ याच कालावधी/मोडसाठी PDF आधीच तयार आहे — खाली थेट डाऊनलोड करा (पुन्हा तयार करायची गरज नाही).")
                else:
                    with st.spinner("PDF तयार होत आहे..."):
                        perf_recs_en = (
                            _build_recommendations(perf_symbol, "source", "Strategy", perf_mode_f, perf_from, perf_to, english=True)
                            + _build_recommendations(perf_symbol, "entry_timeframe", "Timeframe", perf_mode_f, perf_from, perf_to, english=True)
                            + _build_recommendations(perf_symbol, OPTION_STRUCTURE_GROUP_SQL, "Option Structure", perf_mode_f, perf_from, perf_to, english=True)
                        )
                        perf_pdf_bytes = generate_performance_report_pdf(
                            perf_symbol_title, mode_label_en, perf_from, perf_to, summary, perf_pnl_totals,
                            perf_by_source, perf_by_timeframe, perf_by_structure, perf_trade_log_pdf_df, perf_recs_en,
                            slippage_pairs_df=perf_slippage_pairs_df, by_symbol_df=perf_by_symbol_pdf,
                        )
                    st.session_state[perf_pdf_bytes_key] = perf_pdf_bytes
                    st.session_state[_widget_key(perf_symbol_label, "perf_pdf_filename")] = f"{perf_symbol_label}_MCX_Performance_Report_{perf_from}_{perf_to}.pdf"
                    st.session_state[perf_pdf_state_key] = pdf_cache_key
            if st.session_state.get(_widget_key(perf_symbol_label, "perf_pdf_bytes")):
                st.download_button(
                    "📥 Performance Report PDF डाऊनलोड करा", data=st.session_state[_widget_key(perf_symbol_label, "perf_pdf_bytes")],
                    file_name=st.session_state.get(_widget_key(perf_symbol_label, "perf_pdf_filename"), f"{perf_symbol_label}_MCX_Performance_Report.pdf"),
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
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Crude oil hit log not working", "Same problem silver gold") — Hit Log
        # मध्ये न-बदललेली NO_HIT स्थिती पुन्हा साठवली जात नाही (जुनी "repeat" तक्रार), म्हणून शांत काळात log स्थिर दिसतं.
        # येथे trader ची अखेरची तपासणी (प्रत्येक cycle ला अद्ययावत) दाखवली जाते — bot जिवंत आहे हे कळावं म्हणून.
        _lc = cloud_db.get_mcx_last_check(symbol)
        if _lc is None:
            st.info("ℹ️ या commodity साठी trader ची अखेरची तपासणी अजून नोंदली गेलेली नाही (VPS वर नवीन कोड आल्यानंतर पहिल्या cycle पासून दिसेल).")
        else:
            try:
                _checked = datetime.datetime.strptime(_lc["checked_at"], "%Y-%m-%d %H:%M:%S")
                _age_min = (get_ist_now().replace(tzinfo=None) - _checked).total_seconds() / 60
            except Exception:
                _checked, _age_min = None, None
            _near = (
                f" — सर्वात जवळचा level ₹{_lc['nearest_level']:,.1f} ({_lc.get('nearest_level_type')}, {_lc.get('nearest_timeframe')}), "
                f"अंतर ₹{abs(_lc['nearest_level'] - _lc['price']):,.1f}"
                if _lc.get("nearest_level") is not None and _lc.get("price") is not None else ""
            )
            _price = f" — भाव ₹{_lc['price']:,.1f}" if _lc.get("price") is not None else ""
            _age_txt = f" ({_age_min:.0f} मिनिटांपूर्वी)" if _age_min is not None else ""
            _line = f"🕒 अखेरची तपासणी: {_lc['checked_at']}{_age_txt}{_price}{_near}\n\nस्थिती: {_lc['status']}"
            _market_hours = _checked is not None and 9 <= get_ist_now().hour < 23 and get_ist_now().weekday() < 5
            if _age_min is not None and _age_min > 5 and _market_hours:
                st.warning(_line + "\n\n⚠️ 5 मिनिटांपेक्षा जास्त वेळ तपासणी नाही — trader (VPS cron) चालू आहे का ते `mcx_futures.log` मध्ये तपासा.")
            else:
                st.success(_line)
        st.caption(
            "ℹ️ Hit Log मध्ये न-बदललेली NO_HIT स्थिती पुन्हा नोंदली जात नाही (एका दिवसात एका level ची एकच NO_HIT ओळ) — "
            "म्हणून भाव level जवळ नसताना खालचा log स्थिर/रिकामा दिसणं सामान्य आहे. नवीन ओळ तेव्हाच येते जेव्हा स्थिती बदलते "
            "(level ला स्पर्श, RSI/Max-hits मुळे skip, किंवा zones refresh होऊन नवीन level येतो)."
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

        if trading_mode_selected in ("LIVE", "LIVE_PAPER") and not is_mcx_live_quantity_verified():
            st.error(
                "🛑 MCX LIVE अजून बंद आहे (सुरक्षा-गेट): Upstox च्या MCX order quantity चं एकक (units की lots) पडताळलेलं नाही — "
                "चुकीचं असल्यास 1 lot ऐवजी lot_size पट मोठा order जाईल. VPS वर `python3 verify_mcx_order_quantity_units.py` चालवा; "
                "तो OK म्हणेपर्यंत LIVE order नाकारले जातील (PAPER वर परिणाम नाही)."
            )
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
