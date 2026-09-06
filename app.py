import datetime
import io
import json
import os
import re
import uuid
import xml.etree.ElementTree as ET
import sqlite3
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import supabase
from dotenv import load_dotenv
import requests
import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None  # पॅकेज गहाळ असेल तर auto-refresh बंद राहील, बाकी सर्व app चालूच राहील

# --- १. पेज कॉन्फिगरेशन आणि CSS (TradingView Look) ---
st.set_page_config(
    page_title="Upstox Option Terminal Pro (TradingView Style)",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #131722; color: #d1d4dc; }
    .stMetric { background-color: #1e222d; padding: 12px; border-radius: 6px; border: 1px solid #2a2e3d; }
    dataframe, table, th, td { font-size: 15px !important; }
    .stDataFrame { font-size: 15px !important; }

    /* 🎓 डिझाईन सुधारणा — Tab फॉन्ट मोठा व ठळक, एकसंध typography, कमी दृश्य गोंधळ */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #2a2e3d; }
    .stTabs [data-baseweb="tab"] {
        font-size: 16px !important; font-weight: 600 !important; padding: 10px 18px !important;
        color: #9598a1 !important;
    }
    .stTabs [aria-selected="true"] { color: #d1d4dc !important; border-bottom: 2px solid #2962ff !important; }

    /* Headers/subheaders - एकसंध scale, आधी विसंगत होते */
    h1 { font-size: 26px !important; font-weight: 700 !important; }
    h2, .stApp [data-testid="stHeader"] { font-size: 21px !important; font-weight: 650 !important; }
    h3 { font-size: 18px !important; font-weight: 600 !important; }

    /* Caption - छोटा, फिकट, जागा कमी घेणारा (जेणेकरून मुख्य डेटावर लक्ष केंद्रित राहील) */
    .stCaption, [data-testid="stCaptionContainer"] { font-size: 12.5px !important; color: #7a7f8a !important; line-height: 1.4 !important; }

    /* Sidebar labels - थोडे मोठे, वाचनीय */
    section[data-testid="stSidebar"] label { font-size: 14px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- १.२ Indian Standard Time Live Clock (ब्राउझर-साईड JS — दर सेकंदाला टिक होते) ---
components.html(
    """
    <div id="ist-clock" style="
        font-family: 'Trebuchet MS', Arial, sans-serif;
        background-color: #1e222d;
        border: 1px solid #2a2e3d;
        border-radius: 6px;
        padding: 10px 16px;
        display: flex;
        align-items: center;
        gap: 14px;
        color: #d1d4dc;
        width: fit-content;
    ">
        <span style="font-size: 20px;">🕐</span>
        <div>
            <div style="font-size: 12px; color: #787b86; letter-spacing: 0.5px;">INDIAN STANDARD TIME (IST)</div>
            <div id="ist-time" style="font-size: 22px; font-weight: bold; color: #2962FF; font-variant-numeric: tabular-nums;">--:--:--</div>
        </div>
        <div id="ist-date" style="font-size: 13px; color: #9598a1; border-left: 1px solid #2a2e3d; padding-left: 14px;">--</div>
        <div id="market-status" style="font-size: 12px; font-weight: bold; padding: 4px 10px; border-radius: 4px;">--</div>
    </div>
    <script>
        function updateISTClock() {
            const now = new Date();
            const istString = now.toLocaleString("en-US", { timeZone: "Asia/Kolkata", hour12: false });
            const istNow = new Date(istString);

            const timeStr = istNow.toLocaleTimeString("en-IN", { hour12: false });
            const dateStr = istNow.toLocaleDateString("en-IN", { weekday: "long", day: "2-digit", month: "short", year: "numeric" });

            document.getElementById("ist-time").innerText = timeStr;
            document.getElementById("ist-date").innerText = dateStr;

            // NSE कॅश मार्केट तास: सोम-शुक्र, 09:15 - 15:30 IST
            const day = istNow.getDay();
            const mins = istNow.getHours() * 60 + istNow.getMinutes();
            const isWeekday = day >= 1 && day <= 5;
            const isMarketHours = mins >= (9 * 60 + 15) && mins <= (15 * 60 + 30);
            const statusEl = document.getElementById("market-status");

            if (isWeekday && isMarketHours) {
                statusEl.innerText = "🟢 MARKET OPEN";
                statusEl.style.backgroundColor = "rgba(8,153,129,0.15)";
                statusEl.style.color = "#089981";
            } else {
                statusEl.innerText = "🔴 MARKET CLOSED";
                statusEl.style.backgroundColor = "rgba(242,54,69,0.15)";
                statusEl.style.color = "#F23645";
            }
        }
        updateISTClock();
        setInterval(updateISTClock, 1000);
    </script>
    """,
    height=70,
)


# डॅशबोर्ड लोड होण्यापूर्वी Supabase मधून लेटेस्ट टोकन थेट st.session_state मध्ये सेट करा
try:
    import os
    import supabase
    from dotenv import load_dotenv
    load_dotenv()
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    if url and key:
        db = supabase.create_client(url, key)
        res = db.table('upstox_tokens').select('access_token').order('created_at', desc=True).limit(1).execute()
        if res.data and len(res.data) > 0:
            st.session_state["token_input"] = res.data[0]['access_token']
except Exception:
    pass

from shared_context import setup_shared_context
context_ok = setup_shared_context()

# 🎓 दुरुस्ती — auto_refresh आता pg.run() च्या आधी नोंदवला जातो (component जास्त विश्वासार्हपणे
# काम करण्यासाठी), आणि "शेवटचं कधी रिफ्रेश झालं" हे साईडबारमध्ये दिसतं — जेणेकरून प्रत्यक्ष काम
# करतंय की नाही ते लगेच पडताळता येईल (आधी कुठलाही दृश्य संकेतच नव्हता).
auto_refresh = st.session_state.get("auto_refresh", False)
if auto_refresh:
    if st_autorefresh is not None:
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा -- 5 मिनिटांवरून 1 मिनिटावर (Upstox API
        # rate-limit चा धोका कमी करण्यासाठी, "दर सेकंदाला" ऐवजी हा सुरक्षित, तरीही जलद मध्यबिंदू).
        st_autorefresh(interval=60000, key="dashboard_autorefresh")  # 60000ms = 1 मिनिट
    else:
        st.sidebar.warning("⚠️ Auto-refresh साठी 'streamlit-autorefresh' पॅकेज इंस्टॉल नाही — requirements.txt तपासा.")
    from config import get_ist_now
    st.sidebar.caption(f"🔄 शेवटचं रिफ्रेश: {get_ist_now().strftime('%H:%M:%S')} (दर १ मिनिटाने आपोआप)")

if context_ok:
    import page_dashboard
    import page_positions
    import page_orders
    import page_performance

    pages = [
        st.Page(page_dashboard.render, title="Dashboard", icon="📊", default=True, url_path="dashboard"),
        st.Page(page_positions.render, title="Positions", icon="💰", url_path="positions"),
        st.Page(page_orders.render, title="Orders", icon="📝", url_path="orders"),
        st.Page(page_performance.render, title="Performance", icon="📈", url_path="performance"),
    ]
    pg = st.navigation(pages)
    pg.run()
else:
    # Supabase मधून ऑटोमॅटिक टोकन फेच करणारे लॉजिक
    if not st.session_state.get("token_input"):
        try:
            import os
            import supabase
            from dotenv import load_dotenv
            load_dotenv()
            url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
            if url and key:
                db = supabase.create_client(url, key)
                res = db.table('upstox_tokens').select('access_token').order('created_at', desc=True).limit(1).execute()
                if res.data and len(res.data) > 0:
                    st.session_state["token_input"] = res.data[0]['access_token']
                    st.rerun()
        except Exception:
            pass

    token_input = st.session_state.get("token_input", "")
    status_msg = st.session_state.get("status_msg")
    if not token_input.strip():
        st.info("⬅️ सुरू करण्यासाठी साईडबारमध्ये तुमचा Upstox Access Token टाका.")
    else:
        st.error(f"❌ Upstox API Error: {status_msg}")
