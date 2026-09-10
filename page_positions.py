"""Positions page — real-time MTM P&L for all open trades."""
import streamlit as st
import pandas as pd

from database import get_live_positions_with_mtm, compute_portfolio_risk_summary, compute_portfolio_greeks, compute_per_position_greeks
from trading_engine import close_trade_manually


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]
    product_type = st.session_state.get("product_type", "I")

    st.subheader("💰 Positions — Real-Time MTM P&L")
    pos_mode_choice = st.radio("दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key="pos_mode_filter")
    pos_mode_f = None if pos_mode_choice == "सर्व" else ("LIVE" if "LIVE" in pos_mode_choice else "PAPER")
    positions_df = get_live_positions_with_mtm(token_input, symbol, mode_filter=pos_mode_f)
    if positions_df.empty:
        st.info("सद्य कोणतीही उघडी पोझिशन नाही.")
    else:
        # 🎓 Portfolio-level Risk Dashboard — सर्व उघड्या positions एकत्र घेऊन, एकूण जोखीम आणि
        # दिशा-केंद्रीकरण (सर्व एकाच दिशेने असतील तर correlated risk जास्त) दाखवणे.
        risk_summary = compute_portfolio_risk_summary(positions_df)
        st.markdown("##### 🎯 Portfolio Risk Summary")
        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
        with rcol1:
            st.metric("एकूण Positions", risk_summary["total_positions"])
        with rcol2:
            st.metric("एकूण जोखीम (worst-case)", f"₹{risk_summary['total_max_loss']:,.0f}")
        with rcol3:
            st.metric("एकूण जमा Credit", f"₹{risk_summary['total_net_credit']:,.0f}")
        with rcol4:
            st.metric("दिशा", f"🟢{risk_summary['bullish_count']} 🔴{risk_summary['bearish_count']} ⚪{risk_summary['neutral_count']}")
        if risk_summary["concentration_warning"]:
            st.warning(risk_summary["concentration_warning"])

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — संपूर्ण Portfolio चे निव्वळ Greeks (जागतिक prop
        # trading firms जसं सतत करतात तसंच). API अयशस्वी झालं तरी (network/token समस्या) पान क्रॅश होऊ
        # नये म्हणून सुरक्षित try/except.
        try:
            greeks = compute_portfolio_greeks(token_input, symbol, mode_filter=pos_mode_f)
            if greeks["positions_included"] > 0:
                st.markdown("##### 🧮 Portfolio Greeks (निव्वळ)")
                gcol1, gcol2, gcol3, gcol4 = st.columns(4)
                with gcol1:
                    st.metric("Net Delta", f"{greeks['net_delta']:,.2f}", help="दिशात्मक जोखीम — धन=Bullish bias, ऋण=Bearish bias")
                with gcol2:
                    st.metric("Net Gamma", f"{greeks['net_gamma']:,.4f}", help="Delta किती वेगाने बदलेल — मोठा (धन किंवा ऋण) असेल तर अचानक मोठे बदल शक्य")
                with gcol3:
                    st.metric("Net Theta", f"₹{greeks['net_theta']:,.2f}/दिवस", help="वेळेचा फायदा/तोटा — धन=विक्रेत्याला रोज फायदा")
                with gcol4:
                    st.metric("Net Vega", f"{greeks['net_vega']:,.2f}", help="Volatility जोखीम — ऋण असेल तर VIX वाढल्यास तोटा")
        except Exception:
            st.caption("⚠️ Portfolio Greeks मिळवता आले नाहीत (Upstox API अनुपलब्ध असू शकतं).")

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — प्रत्येक position साठी वेगळी, रणनीती-आधारित
        # Delta Health Check (Iron Condor: दिशाहीन असावा; Credit Spread: विशिष्ट दिशेतच असावा)
        try:
            per_position = compute_per_position_greeks(token_input, symbol, mode_filter=pos_mode_f)
            relevant = [p for p in per_position if p["strategy"] in ("IRON_CONDOR", "IRON_BUTTERFLY", "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD")]
            if relevant:
                st.markdown("##### 🩺 Position-निहाय Delta Health Check")
                for p in relevant:
                    st.markdown(f"**{p['trade_id']}** ({p['strategy']}): {p['health_emoji']} {p['health_message']}")
        except Exception:
            pass  # ऐच्छिक अतिरिक्त माहिती -- अयशस्वी झाली तरी मुख्य Positions page दाखवत राहणे
        st.markdown("---")

        total_mtm = positions_df["MTM (Rs)"].dropna().sum()
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            st.metric("एकूण पोझिशन्स", len(positions_df))
        with pcol2:
            st.metric("एकूण MTM P&L", f"₹{total_mtm:,.0f}")
        with pcol3:
            profitable = int((positions_df["MTM (Rs)"].dropna() > 0).sum())
            st.metric("नफ्यात असलेल्या पोझिशन्स", f"{profitable}/{len(positions_df)}")

        def _style_mtm_positions(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #089981; font-weight: bold;"
                elif val < 0:
                    return "color: #F23645; font-weight: bold;"
            return ""

        styled_positions = positions_df.style.map(_style_mtm_positions, subset=["MTM (Rs)", "MTM (%)"])
        st.dataframe(styled_positions, width='stretch', height=350)
        st.caption(
            "🔄 दर रनला आपोआप अपडेट होते — किंमती थेट Upstox च्या सद्य LTP वरून. "
            "**Peak P&L**: Trailing SL चालू असल्यास, या पोझिशनने आतापर्यंत गाठलेला सर्वोच्च नफा — "
            "SL याच्यापासून ATR-अंतर मागे राहून सतत वर सरकतो."
        )

        st.markdown("##### 🔴 पोझिशन मॅन्युअली बंद करा")
        st.caption(
            "एक, अनेक, किंवा सर्व पोझिशन्स एकाच वेळी निवडून बंद करता येतील — विशेषतः Manual Trading "
            "Panel मधून SL/Target न ठेवता उघडलेल्या पोझिशन्ससाठी उपयोगी (त्या आपोआप बंद होत नाहीत)."
        )

        all_trade_ids = positions_df["Trade ID"].tolist()

        def _format_trade(tid):
            row = positions_df.loc[positions_df["Trade ID"] == tid]
            return f"{tid} — {row['Strategy'].values[0]} ({row['Legs'].values[0]})"

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Select All + Exit All) — st.multiselect चा
        # `default` फक्त पहिल्याच वेळी काम करतो (Streamlit चं widget-state, key दिल्यावर, त्यानंतरच्या
        # rerun्सना default कडे दुर्लक्ष करतं) — म्हणून "सर्व निवडा" checkbox बदलल्यावर, on_change
        # callback मधून थेट session_state अपडेट करणे, हाच योग्य/विश्वासार्ह मार्ग.
        def _toggle_select_all():
            st.session_state["close_trade_multiselect"] = list(all_trade_ids) if st.session_state.get("close_select_all") else []

        st.checkbox("सर्व पोझिशन्स निवडा", key="close_select_all", on_change=_toggle_select_all)

        # आधीच्या rerun मध्ये बंद झालेले trade_ids आता positions_df मध्ये नसतील — multiselect ला
        # न-अस्तित्वात असलेले options दिल्यास तो error देतो, त्यामुळे साठवलेली निवड आधी फिल्टर करणे.
        st.session_state["close_trade_multiselect"] = [
            tid for tid in st.session_state.get("close_trade_multiselect", []) if tid in all_trade_ids
        ]

        selected_trade_ids = st.multiselect(
            "बंद करण्यासाठी पोझिशन(न्स) निवडा",
            options=all_trade_ids,
            format_func=_format_trade,
            key="close_trade_multiselect",
        )

        if st.button(f"🔴 निवडलेल्या {len(selected_trade_ids)} पोझिशन्स बंद करा", disabled=len(selected_trade_ids) == 0):
            with st.spinner(f"{len(selected_trade_ids)} पोझिशन्स बंद करत आहे..."):
                results = [(tid, *close_trade_manually(token_input, tid, symbol, product_type)) for tid in selected_trade_ids]
            for tid, ok, result in results:
                if ok:
                    st.success(f"✅ {tid} बंद झाली — Realized P&L: ₹{result:,.2f}")
                else:
                    st.error(f"❌ {tid} बंद करता आलं नाही: {result}")
            if any(ok for _, ok, _ in results):
                st.session_state["close_trade_multiselect"] = []
                st.session_state["close_select_all"] = False
                st.rerun()

