import datetime
import hmac
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
import requests
import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None  # पॅकेज गहाळ असेल तर auto-refresh बंद राहील, बाकी सर्व app चालूच राहील

# --- १. पेज कॉन्फिगरेशन आणि CSS (TradingView Look) ---
st.set_page_config(
    page_title="AMW's A1 Option Trading Terminal",
    page_icon="📈",
    layout="wide",
)


# 🎓 वापरकर्त्याने सापडवलेली गंभीर सुरक्षा त्रुटी — संपूर्ण Dashboard (LIVE Trading toggle, Broker
# credentials/tokens, Bot lots/SL/Target सेटिंग्ज सकट) आधी कुठल्याही password/login शिवाय, VPS च्या
# public IP:port वरून कुणालाही उघडं होतं (server 0.0.0.0 वर बांधलेला). आता संपूर्ण app च्या अगदी
# सुरुवातीला (set_page_config नंतर लगेच, बाकी काहीही render होण्याआधी) हा gate — बरोबर पासवर्ड
# दिल्याशिवाय पुढे काहीच (charts, settings, काहीही) दिसणार नाही. Fail-closed: APP_PASSWORD/secrets
# configured नसेल, तरीही उघडं सोडत नाही — चुकून live trading उघडं राहण्यापेक्षा, ऑपरेटरला स्पष्ट
# सेटअप-सूचना देऊन थांबणं जास्त सुरक्षित.
def _get_configured_app_password():
    """पर्यावरण चल (VPS, systemd Environment=) किंवा secrets.toml (Streamlit Cloud) — दोन्ही
    मार्ग, established secrets_token च्या priority-pattern प्रमाणेच."""
    pwd = os.environ.get("APP_PASSWORD")
    if pwd:
        return pwd
    try:
        if "app_password" in st.secrets:
            return st.secrets["app_password"]
    except Exception:
        pass
    return None


def _require_app_password():
    if st.session_state.get("_app_authenticated"):
        return

    configured_password = _get_configured_app_password()
    _, gate_col, _ = st.columns([1, 1.3, 1])
    with gate_col:
        st.markdown(
            '<div style="font-size:1.6rem; font-weight:800; color:#2962FF; margin:20vh 0 1rem 0; '
            'text-align:center;">🔒 AMW\'s A1 Option Trading Terminal</div>',
            unsafe_allow_html=True,
        )
        if not configured_password:
            st.error(
                "⚠️ हा Dashboard अजून सुरक्षित नाही — APP_PASSWORD सेट केलेला नाही.\n\n"
                "VPS वर systemd service file मध्ये `Environment=\"APP_PASSWORD=तुमचा-मजबूत-पासवर्ड\"` "
                "जोडा (किंवा Streamlit Cloud वर secrets.toml मध्ये `app_password = \"...\"`), मग "
                "service restart करा — सेट केल्याशिवाय हे पान कुणालाही उघडता येणार नाही."
            )
            st.stop()

        with st.form("app_password_form"):
            entered_password = st.text_input("पासवर्ड", type="password")
            submitted = st.form_submit_button("प्रवेश करा", width="stretch")
        if submitted:
            if hmac.compare_digest(entered_password, configured_password):
                st.session_state["_app_authenticated"] = True
                st.rerun()
            else:
                st.error("❌ चुकीचा पासवर्ड — पुन्हा प्रयत्न करा.")
    st.stop()


_require_app_password()

st.markdown(
    """
    <style>
    .stApp { background-color: #131722; color: #d1d4dc; }
    .stMetric { background-color: #1e222d; padding: 12px; border-radius: 6px; border: 1px solid #2a2e3d; }
    /* 🎓 वापरकर्त्याने मागितलेली सुधारणा ("सर्व टॅबमध्ये फॉन्ट वाढवा, multicolor वापरा") — dataframe/
    table फॉन्ट आधीच्या 15px वरून 16.5px — वाचनीयता आणखी वाढावी म्हणून. */
    dataframe, table, th, td { font-size: 16.5px !important; }
    .stDataFrame { font-size: 16.5px !important; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.9rem !important; }
    .stMetric [data-testid="stMetricLabel"] { font-size: 0.95rem !important; }

    /* 🎓 डिझाईन सुधारणा — Tab फॉन्ट आणखी मोठा व ठळक (16px -> 17.5px), आणि प्रत्येक tab ला वेगळा
    रंग (multicolor — cycle through, ui_headers.py च्या mega/mid/sub_header पॅलेटशी सुसंगत) —
    त्यामुळे कुठला tab निवडलेला आहे हे लगेच, रंगानेच वेगळं दिसतं (आधी सर्व tabs एकाच फिकट रंगात). */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #2a2e3d; }
    .stTabs [data-baseweb="tab"] {
        font-size: 17.5px !important; font-weight: 650 !important; padding: 10px 18px !important;
        color: #9598a1 !important;
    }
    .stTabs [aria-selected="true"] { color: #d1d4dc !important; border-bottom: 3px solid #2962ff !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+1)[aria-selected="true"] { border-bottom-color: #2962FF !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+2)[aria-selected="true"] { border-bottom-color: #00BFA5 !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+3)[aria-selected="true"] { border-bottom-color: #AB47BC !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+4)[aria-selected="true"] { border-bottom-color: #FF6D00 !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+5)[aria-selected="true"] { border-bottom-color: #EC407A !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+6)[aria-selected="true"] { border-bottom-color: #66BB6A !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+7)[aria-selected="true"] { border-bottom-color: #FFC107 !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+8)[aria-selected="true"] { border-bottom-color: #26C6DA !important; }
    .stTabs [data-baseweb="tab-list"] button:nth-child(9n+9)[aria-selected="true"] { border-bottom-color: #E64A19 !important; }

    /* Headers/subheaders - एकसंध scale, आधीपेक्षा थोडे मोठे */
    h1 { font-size: 27px !important; font-weight: 700 !important; }
    h2, .stApp [data-testid="stHeader"] { font-size: 22px !important; font-weight: 650 !important; }
    h3 { font-size: 19px !important; font-weight: 600 !important; }

    /* Caption - छोटा, फिकट, जागा कमी घेणारा (जेणेकरून मुख्य डेटावर लक्ष केंद्रित राहील) */
    .stCaption, [data-testid="stCaptionContainer"] { font-size: 13px !important; color: #7a7f8a !important; line-height: 1.4 !important; }

    /* 🎓 वापरकर्त्याने मागितलेली सुधारणा ("sidebar catchy आणि attractive बनवा, गर्दी कमी करा") —
    मुख्य पानापेक्षा किंचित वेगळी (थोडी गडद) पार्श्वभूमी, उजवीकडे रंगीत सीमारेषा — sidebar एक
    वेगळा, दृष्टीस पडणारा "पॅनल" वाटावा म्हणून. Labels थोडे मोठे, अधिक वाचनीय. Expanders मधली
    शीर्षकं ठळक + रंगीत डावी सीमारेषा — विभागांमध्ये स्पष्ट, आकर्षक फरक दिसावा म्हणून. */
    section[data-testid="stSidebar"] {
        background-color: #171b26 !important; border-right: 2px solid #2962FF33 !important;
    }
    section[data-testid="stSidebar"] label { font-size: 14.5px !important; }
    section[data-testid="stSidebar"] .stExpander {
        border: 1px solid #2a2e3d !important; border-left: 3px solid #2962FF !important;
        border-radius: 6px !important; margin-bottom: 6px !important;
    }
    section[data-testid="stSidebar"] .stExpander summary { font-weight: 600 !important; }

    /* 🎓 वापरकर्त्याने मागितलेली सुधारणा ("sidebar वरचे ७-८ पानं multicolor करा, पहिलं अक्षर capital,
    फॉन्ट मोठा करा") — st.navigation() ने बनवलेली page-list (Dashboard/Positions/Orders/Performance/
    Multi-Strategy/MTF Pullback/Bot Dynamic SR Algo/Settings) आधी .stTabs सारखी multicolor नव्हती —
    इथे तोच रंगीत-सायकल पॅटर्न (वरच्याच पॅलेटशी सुसंगत) आणि मोठा, ठळक फॉन्ट. */
    [data-testid="stSidebarNavLink"] {
        font-size: 17px !important; font-weight: 650 !important; text-transform: capitalize !important;
        border-radius: 6px !important; margin-bottom: 3px !important; padding: 8px 10px !important;
    }
    /* 🎓 प्रत्यक्ष चालवून पडताळलं (Playwright screenshot) — stSidebarNavLinkContainer प्रत्येक <li>
    च्या आतच एकुलता एक असतो (nth-of-type कायम 1 राहतं, cycling साठी निरुपयोगी) आणि लेबल मजकुराचा
    रंग वेगळ्या (stMarkdownContainer च्या आतल्या <p>) rule ने आधीच ठरलेला असतो, त्यामुळे बाहेरून
    रंग दिला तरी inherit होत नाही — म्हणून खरी सायकल <li> siblings वर (stSidebarNavItems च्या आत)
    आणि रंग थेट त्या <p> वरच लावला आहे. */
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+1) [data-testid="stMarkdownContainer"] p { color: #2962FF !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+2) [data-testid="stMarkdownContainer"] p { color: #00BFA5 !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+3) [data-testid="stMarkdownContainer"] p { color: #AB47BC !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+4) [data-testid="stMarkdownContainer"] p { color: #FF6D00 !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+5) [data-testid="stMarkdownContainer"] p { color: #EC407A !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+6) [data-testid="stMarkdownContainer"] p { color: #66BB6A !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+7) [data-testid="stMarkdownContainer"] p { color: #FFC107 !important; }
    [data-testid="stSidebarNavItems"] > li:nth-of-type(8n+8) [data-testid="stMarkdownContainer"] p { color: #26C6DA !important; }
    [data-testid="stSidebarNavLink"][aria-current="page"] {
        background-color: #1e222d !important; font-weight: 750 !important; box-shadow: inset 3px 0 0 currentColor !important;
    }
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

from shared_context import setup_shared_context

context_ok = setup_shared_context()

# 🎓 दुरुस्ती — auto_refresh आता pg.run() च्या आधी नोंदवला जातो (component जास्त विश्वासार्हपणे
# काम करण्यासाठी), आणि "शेवटचं कधी रिफ्रेश झालं" हे साईडबारमध्ये दिसतं — जेणेकरून प्रत्यक्ष काम
# करतंय की नाही ते लगेच पडताळता येईल (आधी कुठलाही दृश्य संकेतच नव्हता).
# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established बाजार तासांबाहेर (established रोजच्या
# 9:15-15:30 च्या दोन्ही बाजूला ५/१० मिनिटांची सूट — established 9:10 ते 15:40) दर मिनिटाला उगाच
# auto-refresh चालू ठेवायची गरज नाही (ना नवीन डेटा, ना trading decision) — फक्त वायफळ Upstox API
# कॉल्स + CPU load (established 1GB droplet साठी विशेष महत्त्वाचं). बाजार बंद असताना established
# फक्त हाताने (mouse click ने) refresh व्हावं.
from config import is_market_open, get_ist_now
import datetime as _dt

auto_refresh = st.session_state.get("auto_refresh", False)
market_hours_now = is_market_open(open_time=_dt.time(9, 10), close_time=_dt.time(15, 40))

if auto_refresh and market_hours_now:
    if st_autorefresh is not None:
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Professional Grade — Blink फिक्स) — आधी दर १
        # मिनिटाला **संपूर्ण पान** पुन्हा चालायचं (लक्षणीय "blink" — chart/tabs सगळं क्षणभर नाहीसं होऊन
        # परत यायचं, अव्यावसायिक दिसायचं). किंमत/P&L टिकर (established live_ticker.py, स्वतंत्र
        # `@st.fragment(run_every="60s")`) आता दर ६० सेकंदाला **स्वतःच, बाकीचं पान न हलवता** ताजा
        # होतो — म्हणून संपूर्ण पानाचं auto-refresh आता दर ५ मिनिटांनी पुरेसं आहे (established
        # चार्ट/Direction Engine/Signal Engine इतक्या वारंवार बदलायची गरजच नाही — 15-मिनिट candle
        # तसंही १५ मिनिटांनीच बदलतो).
        st_autorefresh(interval=300000, key="dashboard_autorefresh")  # 300000ms = ५ मिनिट
    else:
        st.sidebar.warning("⚠️ Auto-refresh साठी 'streamlit-autorefresh' पॅकेज इंस्टॉल नाही — requirements.txt तपासा.")
    st.sidebar.caption(f"🔄 शेवटचं पूर्ण-पान रिफ्रेश: {get_ist_now().strftime('%H:%M:%S')} (दर ५ मिनिटांनी आपोआप — किंमत/P&L टिकर मात्र दर ६० सेकंदाला स्वतंत्रपणे ताजा होतो)")
elif auto_refresh and not market_hours_now:
    st.sidebar.caption("⏸️ बाजार बंद (9:10-15:40 बाहेर) — Auto-refresh थांबवला, फक्त हाताने Refresh करा (माऊस/F5).")
    if st.sidebar.button("🔄 आत्ता Refresh करा"):
        st.rerun()

if context_ok:
    import page_dashboard
    import page_positions
    import page_orders
    import page_performance
    import page_multi_strategy
    import page_mtf_pullback
    import page_broker_accounts
    import page_bot_dynamic_sr_algo

    pages = [
        st.Page(page_dashboard.render, title="Dashboard", icon="📊", default=True, url_path="dashboard"),
        st.Page(page_positions.render, title="Positions", icon="💰", url_path="positions"),
        st.Page(page_orders.render, title="Orders", icon="📝", url_path="orders"),
        st.Page(page_performance.render, title="Performance", icon="📈", url_path="performance"),
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Dashboard वरची tab-गर्दी कमी करण्यासाठी, हे
        # तीन (आधी page_dashboard.py चे tabs) आता Positions/Orders/Performance सारखेच स्वतंत्र
        # sidebar pages आहेत.
        st.Page(page_multi_strategy.render, title="Multi-Strategy", icon="🧩", url_path="multi-strategy"),
        st.Page(page_mtf_pullback.render, title="MTF Pullback + Gap Fill", icon="🌉", url_path="mtf-pullback"),
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेलं नवीन page (Bot Dynamic SR Algo — नवीन नियम-संच) —
        # 1M Instant Trader आणि 15M/30M/60M Dynamic SR Reversal या दोन्ही strategies चे सर्व
        # settings (Lots, ITM Depth, Hedge Width, SL/TSL/Target, Naked Option Trade toggle).
        st.Page(page_bot_dynamic_sr_algo.render, title="Bot Dynamic SR Algo", icon="🤖", url_path="bot-dynamic-sr-algo"),
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Broker Accounts" हे स्वतंत्र नाव sidebar मधून
        # काढून "Settings" केलं (आतलं काम तेच — पान/फाईल तीच आहे, फक्त नाव/जागा बदलली).
        st.Page(page_broker_accounts.render, title="Settings", icon="⚙️", url_path="settings"),
    ]
    pg = st.navigation(pages)
    pg.run()
else:
    token_input = st.session_state.get("token_input", "")
    status_msg = st.session_state.get("status_msg")
    if not token_input.strip():
        st.info("⬅️ सुरू करण्यासाठी साईडबारमध्ये तुमचा Upstox Access Token टाका.")
    else:
        st.error(f"❌ Upstox API Error: {status_msg}")
