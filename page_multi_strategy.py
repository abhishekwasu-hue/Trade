"""Multi-Strategy Orchestrator page — OI/PCR · ICT-FVG · BB Squeeze · VWAP · SR Bounce · MTF Gap Fill.
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Dashboard वरच्या tab-गर्दी कमी करण्यासाठी,
हे (established page_dashboard.py चं जुनं tab5) आता established Positions/Orders/Performance
सारखंच एक स्वतंत्र sidebar page आहे. established शेअर्ड संदर्भ (token/symbol/underlying_price/
raw_chain/atm_strike) established shared_context.py ने आधीच session_state मध्ये ठेवलेला असतो —
इथे तोच वाचला जातो, वेगळं काही मागवावं लागत नाही."""
import streamlit as st

from upstox_api import fetch_candles
from signals import find_support_resistance_levels, resample_to_1h


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]
    underlying_price = st.session_state["underlying_price"]
    raw_chain = st.session_state["raw_chain"]
    atm_strike = st.session_state["atm_strike"]

    st.subheader("🧩 Multi-Strategy Orchestrator")
    st.caption("OI/PCR · ICT-FVG · BB Squeeze · VWAP · SR Bounce · MTF Gap Fill — ६ रणनीती एकत्र")
    show_orchestrator = st.checkbox("दाखवा (प्रत्येक वेळी सर्व ६ strategies चालवल्या जातील)", value=False)
    if show_orchestrator:
        try:
            from loader import build_orchestrator
            from market_data_adapter import prepare_futures_ohlcv, prepare_options_chain, prepare_structure_data, compute_trend_direction_1h, apply_manual_sl_target
            from strategies.base import MarketSnapshot
            from config import get_ist_now
            import os as _os

            config_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "config.yaml")
            orch = build_orchestrator(config_path)

            # 🎓 वापरकर्त्याने "गर्दी" म्हणून निदर्शनास आणलेला मुद्दा — आधी १२ input boxes
            # (६ strategies × SL+Target) नेहमीच उघडे दिसायचे, स्क्रीन भरून टाकायचे. आता डीफॉल्ट-
            # बंद expander मध्ये — गरज असेल तेव्हाच उघडा, नाहीतर स्वच्छ, व्यावसायिक दिसणारं पान.
            default_sl_target = {
                "oi_pcr": (40, 80), "ict_fvg": (30, 60), "bb_squeeze": (40, 80),
                "vwap": (25, 40), "sr_bounce": (40, 80), "mtf_gap_fill": (55, 155),
            }
            strat_display_names = {
                "oi_pcr": "OI/PCR", "ict_fvg": "ICT-FVG", "bb_squeeze": "BB Squeeze",
                "vwap": "VWAP", "sr_bounce": "SR Bounce", "mtf_gap_fill": "MTF Gap Fill",
            }
            ms_sl_target = {}
            with st.expander("⚙️ Advanced — SL/Target स्वतः ठरवा (पॉइंट्स)", expanded=False):
                for strat_id, (default_sl, default_target) in default_sl_target.items():
                    strat_label = strat_display_names[strat_id]
                    mscol1, mscol2 = st.columns(2)
                    with mscol1:
                        sl_pts = st.number_input(f"{strat_label} — SL", min_value=1, value=default_sl, step=1, key=f"live_ms_sl_{strat_id}")
                    with mscol2:
                        target_pts = st.number_input(f"{strat_label} — Target", min_value=1, value=default_target, step=1, key=f"live_ms_target_{strat_id}")
                    ms_sl_target[strat_id] = (sl_pts, target_pts)

            df_for_orch = fetch_candles(token_input, symbol, underlying_price, interval="15minute")
            df_1h_for_orch = fetch_candles(token_input, symbol, underlying_price, interval="30minute")
            futures_ohlcv = prepare_futures_ohlcv(df_for_orch)
            options_chain_df = prepare_options_chain(raw_chain, symbol, atm_strike)
            structure_data = prepare_structure_data(df_for_orch)
            df_1h_resampled = resample_to_1h(df_1h_for_orch) if not df_1h_for_orch.empty else df_1h_for_orch
            trend_direction_1h = compute_trend_direction_1h(df_1h_resampled)

            sr_levels_1h = None
            if df_1h_resampled is not None and not df_1h_resampled.empty and len(df_1h_resampled) >= 10:
                sr_levels_1h = find_support_resistance_levels(df_1h_resampled, top_n=3)
            mtf_1h_ohlcv = None
            if df_1h_resampled is not None and not df_1h_resampled.empty:
                mtf_1h_ohlcv = df_1h_resampled.rename(columns={
                    "timestamp": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close",
                })

            snapshot = MarketSnapshot(
                timestamp=get_ist_now(), futures_ohlcv=futures_ohlcv,
                options_chain=options_chain_df, structure_data=structure_data,
                extra={"trend_direction_1h": trend_direction_1h, "sr_levels_1h": sr_levels_1h, "mtf_1h_ohlcv": mtf_1h_ohlcv},
            )

            raw_results = []
            for strat in orch.strategies:
                r = strat.check_gates(snapshot)
                sl_pts, target_pts = ms_sl_target.get(r.strategy_id, default_sl_target.get(r.strategy_id, (40, 80)))
                r = apply_manual_sl_target(r, sl_pts, target_pts, reference_price=underlying_price)
                raw_results.append(r)

            approved = orch.run_cycle(snapshot)
            for s in approved:
                sl_pts, target_pts = ms_sl_target.get(s.strategy_id, default_sl_target.get(s.strategy_id, (40, 80)))
                apply_manual_sl_target(s, sl_pts, target_pts, reference_price=underlying_price)

            # 🎓 सर्वात महत्त्वाचं (मंजूर सिग्नल्स) आधी दाखवणे — आधी हे तक्त्याच्या तळाशी लपलेलं होतं
            st.markdown("##### ✅ अंतिम मंजूर सिग्नल्स")
            if approved:
                approved_cols = st.columns(min(len(approved), 3))
                for i, s in enumerate(approved):
                    with approved_cols[i % 3]:
                        badge_color = "#089981" if s.direction.value == "LONG" else "#F23645" if s.direction.value == "SHORT" else "#787b86"
                        st.markdown(
                            f"""<div style="border:1px solid {badge_color};border-radius:8px;padding:10px 12px;margin-bottom:8px;">
                            <div style="font-weight:700;color:{badge_color};">● {s.strategy_id} — {s.direction.value}</div>
                            <div style="font-size:13px;color:#9598a1;margin-top:4px;">Entry: {s.entry_price} · SL: {s.stop_loss} · Target: {s.target}</div>
                            <div style="font-size:12px;color:#787b86;margin-top:4px;">{s.reason}</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
            else:
                st.info("या cycle मध्ये कोणताही सिग्नल मंजूर झाला नाही.")

            # 🎓 प्रत्येक strategy चा तपशील — आधी नेहमी उघडा dataframe होता, आता collapsed
            with st.expander(f"🔍 सर्व ६ Strategies चा स्वतंत्र निकाल (Orchestrator गेट्सआधी)", expanded=False):
                color_map = {"LONG": "🟢", "SHORT": "🔴", "NONE": "⚪"}
                for r in raw_results:
                    dot = color_map.get(r.direction.value, "⚪")
                    st.markdown(f"{dot} **{strat_display_names.get(r.strategy_id, r.strategy_id)}** — {r.direction.value} "
                                f"(Confidence: {round(r.confidence, 2)}) — {r.reason}")
                st.caption(f"1H Supertrend Direction: {trend_direction_1h or 'उपलब्ध नाही'} | "
                           f"Structure: swept_high={structure_data['swept_high']}, swept_low={structure_data['swept_low']}, "
                           f"bos_direction={structure_data['bos_direction']}")

            st.caption("⚠️ हे फक्त माहितीसाठी आहे — इथून auto-execute होत नाही, वरच्या A1 Engine पासून पूर्णपणे स्वतंत्र.")
        except ModuleNotFoundError as e:
            st.error(
                f"Multi-Strategy Orchestrator मध्ये चूक: {type(e).__name__}: {e}\n\n"
                "**बहुतेक कारण**: `strategies/` फोल्डर (सर्व ८ फाईल्स — `__init__.py`, `base.py`, `oi_pcr.py`, "
                "`ict_fvg.py`, `bb_squeeze.py`, `vwap.py`, `sr_bounce.py`, `mtf_gap_fill.py`) किंवा "
                "`orchestrator.py`/`loader.py`/`config.yaml` तुमच्या GitHub repo मध्ये गहाळ आहेत. "
                "Repo मध्ये जाऊन हे सर्व आहेत का तपासा."
            )
        except Exception as e:
            st.error(f"Multi-Strategy Orchestrator मध्ये चूक: {type(e).__name__}: {e}")
