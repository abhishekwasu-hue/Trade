"""Orders page — order book (date-range filter, LIVE/PAPER filter, CSV download).

🎓 वापरकर्त्याशी चर्चा करून (Production-grade page arrangement) — System Diagnostics, Data Safety & Broker
Reconciliation आणि NIFTY History -> Google Drive ही सिस्टीम-साधनं Settings पानाच्या tabs मध्ये हलवली आहेत
(page_system_tools.py); हे पान आता फक्त ऑर्डर्ससाठी."""
import datetime
import streamlit as st

from config import get_ist_today
from database import get_order_log_full
from ui_headers import mega_header, HDR_BLUE


def render():
    symbol = st.session_state["symbol"]

    mega_header("📝 Order Book", HDR_BLUE)
    ord_mode_choice = st.radio("दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key="ord_mode_filter")
    ord_mode_f = None if ord_mode_choice == "सर्व" else ("LIVE" if "LIVE" in ord_mode_choice else "PAPER")

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Order Book आता तारीख-रेंज निवडता येतो
    # (डीफॉल्ट: आजचीच तारीख) — आधी फक्त "अलीकडचे २००" दिसायचे, तारीख फिल्टर नव्हता.
    today_d = get_ist_today()
    ord_range_choice = st.radio(
        "कालावधी", ["आज", "गेले 7 दिवस", "गेला महिना", "कस्टम रेंज"], horizontal=True, key="orders_range_choice",
    )
    if ord_range_choice == "आज":
        ord_from, ord_to = today_d, today_d
    elif ord_range_choice == "गेले 7 दिवस":
        ord_from, ord_to = today_d - datetime.timedelta(days=7), today_d
    elif ord_range_choice == "गेला महिना":
        ord_from, ord_to = today_d - datetime.timedelta(days=30), today_d
    else:
        odcol1, odcol2 = st.columns(2)
        with odcol1:
            ord_from = st.date_input("पासून", value=today_d, key="orders_from")
        with odcol2:
            ord_to = st.date_input("पर्यंत", value=today_d, key="orders_to")

    if ord_from > ord_to:
        st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
    else:
        orders_df = get_order_log_full(symbol, start_date=ord_from, end_date=ord_to, mode_filter=ord_mode_f)
        if orders_df.empty:
            st.info("या कालावधीत कोणतेही ऑर्डर्स नाहीत.")
        else:
            st.dataframe(orders_df, width='stretch', height=400)
            st.caption(f"{ord_from} ते {ord_to}: एकूण {len(orders_df)} ऑर्डर्स (नवीनतम आधी) — Single, Basket, A1 Engine व SL/Target/EOD close या सर्वांच्या नोंदी.")
            order_dl_csv = orders_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Order Log CSV डाऊनलोड करा", data=order_dl_csv,
                file_name=f"{symbol}_OrderLog_{ord_from}_{ord_to}.csv",
                mime="text/csv", key="orders_dl_download",
            )
