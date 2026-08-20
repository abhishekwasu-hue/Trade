"""Positions page — real-time MTM P&L for all open trades."""
import streamlit as st
import pandas as pd

from database import get_live_positions_with_mtm
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
            "विशेषतः Manual Trading Panel मधून SL/Target न ठेवता उघडलेल्या पोझिशन्ससाठी उपयोगी — "
            "त्या आपोआप बंद होत नाहीत, इथूनच बंद कराव्या लागतील (किंवा EOD पर्यंत थांबावं लागेल)."
        )
        close_trade_id = st.selectbox(
            "बंद करण्यासाठी पोझिशन निवडा",
            options=positions_df["Trade ID"].tolist(),
            format_func=lambda tid: (
                f"{tid} — {positions_df.loc[positions_df['Trade ID']==tid, 'Strategy'].values[0]} "
                f"({positions_df.loc[positions_df['Trade ID']==tid, 'Legs'].values[0]})"
            ),
            key="close_trade_select",
        )
        if st.button("🔴 ही पोझिशन आत्ताच बंद करा"):
            with st.spinner("बंद करत आहे..."):
                ok, result = close_trade_manually(token_input, close_trade_id, symbol, product_type)
            if ok:
                st.success(f"✅ पोझिशन बंद झाली — Realized P&L: ₹{result:,.2f}")
                st.rerun()
            else:
                st.error(f"❌ बंद करता आलं नाही: {result}")

