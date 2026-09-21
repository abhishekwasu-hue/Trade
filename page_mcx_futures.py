"""
page_mcx_futures.py
--------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेलं, संपूर्णपणे नवीन, स्वतंत्र पान — MCX Futures Trader
(CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER). NIFTY/BANKNIFTY/SENSEX च्या तिन्ही existing bots (Bot
Dynamic SR Algo पान) ला अजिबात हात लावलेला नाही — इथून फक्त हाच नवीन strategy चालतो.

⚠️ सध्याची स्थिती (प्रामाणिक टीप) — हे पान settings साठवतं/दाखवतं, पण प्रत्यक्ष trading script
(mcx_futures_trader.py) अजून बांधलेली नाही — Upstox कडून खरे instrument_key/lot_size/tick_size
(resolve_mcx_futures_instruments.py ने) पडताळल्याशिवाय ते सुरक्षित नाही. तोपर्यंत Order Log/Dynamic
S/R टॅब रिकामेच दिसतील — तिथेच तसं स्पष्ट नमूद केलेलं आहे.
"""
import datetime

import streamlit as st

import cloud_db
from config import get_ist_today
from database import get_order_log_full
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_GREEN, HDR_AMBER

MCX_SYMBOLS = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]
STRATEGY_KEY = "mcx_futures"


def _widget_key(symbol, field):
    return f"mcxf_{symbol}_{field}"


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
        "⚠️ सध्या ही strategy अजून प्रत्यक्ष trading साठी सुरू केलेली नाही — Upstox कडून खरे "
        "instrument_key/lot_size पडताळल्याशिवाय (`resolve_mcx_futures_instruments.py`) ती सुरक्षित "
        "नाही. इथले settings आधीच जतन करून ठेवता येतात — strategy प्रत्यक्ष सुरू झाल्यावर तीच वापरेल."
    )

    _render_status_banner()

    symbol = st.selectbox("Commodity निवडा", MCX_SYMBOLS, key="mcxf_symbol")
    settings = cloud_db.get_strategy_settings(STRATEGY_KEY, symbol)

    tab_entry, tab_exit, tab_orders, tab_zones, tab_mode = st.tabs([
        "🚪 Entry Gate", "🚪 Exit Gate", "📜 Order Log", "📐 Dynamic S/R", "🎮 Mode & Broker",
    ])

    with tab_entry:
        symbol_enabled = st.checkbox(
            f"{symbol} साठी trading सक्रिय (बंद असल्यास — PAPER सुद्धा कुठलाही trade घेतला जाणार नाही)",
            value=bool(settings.get("symbol_enabled", False)),
            key=_widget_key(symbol, "symbol_enabled"),
        )
        lots = _number_input("Lots (× commodity चा स्वतःचा lot_size)", settings, "lots", symbol, min_value=1, max_value=50, step=1)

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
        st.caption("Options प्रमाणे premium नाही — सरळ underlying futures points मध्ये.")
        e1, e2 = st.columns(2)
        with e1:
            sl_points = _number_input("Stop Loss (futures points)", settings, "sl_points", symbol, min_value=1.0, max_value=1000.0, step=1.0)
        with e2:
            target_points = _number_input("Target (futures points)", settings, "target_points", symbol, min_value=1.0, max_value=2000.0, step=1.0)

        trailing_sl_enabled = st.checkbox(
            "Trailing Stop Loss सक्रिय (डीफॉल्ट बंद)", value=bool(settings.get("trailing_sl_enabled", False)),
            key=_widget_key(symbol, "trailing_sl_enabled"),
        )
        trailing_distance_points = _number_input(
            "Trailing Distance (futures points, सक्रिय असेल तरच)", settings, "trailing_distance_points", symbol,
            min_value=1.0, max_value=500.0, step=1.0, disabled=not trailing_sl_enabled,
        )

        if st.button("💾 Exit Gate सेव्ह करा", key=_widget_key(symbol, "save_exit")):
            new_settings = dict(settings)
            new_settings.update({
                "sl_points": float(sl_points), "target_points": float(target_points),
                "trailing_sl_enabled": bool(trailing_sl_enabled),
                "trailing_distance_points": float(trailing_distance_points),
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
