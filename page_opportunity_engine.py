"""Opportunity Engine page (PR-1a) — Structure वही (Daily/4H/1H/15M/5M trend state), zones/levels (Level Quality सकट) आणि Structure accuracy CSV.
🎓 फक्त वाचन आणि प्रदर्शन: कुठलाही trade/order/DB write नाही, कुठलाही bot हे वापरत नाही; indicator-मुक्त (फक्त किंमत + ref_range मोजपट्टी).
PR-1a मध्ये पाया (trend state) बरोबर आहे का ते तुम्ही चार्टवर पडताळता — त्यानंतरच bias/detectors/backtest (PR-1b/1c)."""
import hashlib

import pandas as pd
import streamlit as st

import real_nifty_data
from opportunity_engine import report as R
from opportunity_engine.config import TF_LABEL
from opportunity_engine.zones import build_levels
from safe_widgets import safe_number_input
from tradingview_chart import build_lightweight_chart_html
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE
from upstox_api import fetch_candles

SRC_OFFLINE = "Offline NIFTY (खरा डेटा, 2015 → 2024-03-27)"
SRC_LIVE = "Upstox (लाईव्ह, सध्याचा symbol)"
CHART_TFS = ["1d", "4h", "1h", "15m", "5m"]


@st.cache_resource(show_spinner=False, max_entries=4)
def _offline_bundle(start, end):
    df = real_nifty_data.load_nifty_1min(start, end)
    if df is None or df.empty:
        return None, None
    return R.bundle_from_fine(df)


@st.cache_resource(show_spinner=False, ttl=300, max_entries=4)
def _live_bundle(token_hash, token, symbol, days):
    df5 = fetch_candles(token, symbol, 0, interval="5minute", lookback_days=int(days))
    daily = fetch_candles(token, symbol, 0, interval="day", lookback_days=900)
    if df5 is None or df5.empty:
        return None, None
    return R.bundle_from_live(df5, daily)


def _chart_df(frames, tf, bars):
    df = frames[tf].tail(int(bars)).copy()
    df["timestamp"] = df["bar_start"]
    df["oi"] = 0
    return df[["timestamp", "open", "high", "low", "close", "volume", "oi"]]


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]

    mega_header(f"🎯 {symbol} — Opportunity Engine (PR-1a: Structure + Levels)", HDR_BLUE)
    st.caption(
        "Price-action structure (HH/HL/LH/LL, BOS/CHoCH/Reversal) + Supply/Demand/S-R/Gap levels + Level Quality grade — **फक्त वाचन आणि प्रदर्शन**. "
        "कुठलाही trade/order होत नाही, कुठलाही bot हे वापरत नाही. Indicator-मुक्त (EMA/RSI/ATR/Supertrend नाही). "
        "पाया (trend state) चार्टवर तुम्ही पडताळल्यावरच पुढचे टप्पे."
    )
    c1, c2 = st.columns([2, 3])
    with c1:
        source = st.radio("डेटा स्रोत", [SRC_OFFLINE, SRC_LIVE], key="oe_source")
    with c2:
        if source == SRC_OFFLINE:
            sc1, sc2 = st.columns(2)
            start = sc1.date_input("पासून", value=pd.Timestamp("2023-04-01").date(), min_value=pd.Timestamp("2015-01-09").date(),
                                   max_value=pd.Timestamp("2024-03-27").date(), key="oe_start")
            end = sc2.date_input("पर्यंत", value=pd.Timestamp("2024-03-27").date(), min_value=pd.Timestamp("2015-01-09").date(),
                                 max_value=pd.Timestamp("2024-03-27").date(), key="oe_end")
        else:
            days = safe_number_input("किती दिवसांचा 5M इतिहास", value=120, min_value=30, max_value=400, step=10, key="oe_days")

    try:
        with st.spinner("Structure journal मोजत आहे..."):
            if source == SRC_OFFLINE:
                if symbol != "NIFTY":
                    st.warning(f"Offline डेटा फक्त NIFTY चा आहे — {symbol} साठी 'Upstox (लाईव्ह)' निवडा.")
                    return
                frames, journal = _offline_bundle(pd.Timestamp(start), pd.Timestamp(end))
            else:
                if not token_input:
                    st.info("⬅️ सुरू करण्यासाठी साईडबारमध्ये तुमचा Upstox Access Token टाका.")
                    return
                frames, journal = _live_bundle(hashlib.sha1(token_input.encode()).hexdigest()[:8], token_input, symbol, days)
        if journal is None:
            st.warning("या कालावधीचा डेटा मिळाला नाही.")
            return
        price = float(frames["15m"]["close"].iloc[-1]) if len(frames.get("15m", [])) else float(frames["5m"]["close"].iloc[-1])
        tab_state, tab_chart, tab_events, tab_quality = st.tabs(["🧭 Structure वही", "📊 चार्ट + Levels", "📋 Events / CSV", "🔎 डेटा गुणवत्ता"])

        with tab_state:
            sub_header("प्रत्येक Timeframe चा सद्य trend state", HDR_TEAL)
            st.dataframe(R.state_rows(journal), width="stretch", hide_index=True)
            st.caption(
                "State: Uptrend/Downtrend (HH-HL / LH-LL), Pullback (नवीन high नंतर खाली, protected अबाधित), कमजोर = CHoCH (protected level खाली/वर **close**), "
                "Reversal confirm = CHoCH नंतर LH + CHoCH low खाली close, Range = अडकलेले swings. सर्व break फक्त CLOSE ने; wick = SWEEP."
            )
            swing_tf = st.radio("Swings दाखवा", CHART_TFS[:4], index=1, horizontal=True, key="oe_swing_tf", format_func=lambda t: TF_LABEL[t])
            st.dataframe(R.swings_table(journal, swing_tf), width="stretch", hide_index=True)

        with tab_chart:
            tf = st.radio("चार्ट Timeframe", CHART_TFS, index=2, horizontal=True, key="oe_chart_tf", format_func=lambda t: TF_LABEL[t])
            m1, m2, m3 = st.columns(3)
            max_levels = int(m1.number_input("जास्तीत जास्त levels", min_value=2, max_value=30, value=12, step=1, key="oe_max_levels"))
            max_dist = float(m2.number_input("कमाल अंतर %", min_value=0.5, max_value=10.0, value=3.0, step=0.5, key="oe_max_dist"))
            grades = m3.multiselect("Grades", ["A", "B", "C"], default=["A", "B"], key="oe_grades")
            result = build_levels(journal, frames, symbol, price, fine=frames.get("5m"))
            lines, near = R.chart_lines(result["levels"], price, max_levels, max_dist, tuple(grades) or ("A", "B"))
            bars = {"1d": 250, "4h": 300, "1h": 400, "15m": 500, "5m": 500}[tf]
            html = build_lightweight_chart_html(_chart_df(frames, tf, bars), symbol=symbol, timeframe_label=TF_LABEL[tf], height=600, trade_lines=lines)
            st.components.v1.html(html, height=650, scrolling=False)
            st.caption("रेषा: **L#** (क्रमांक खालच्या तक्त्याशी जुळतो) + Grade + TF + प्रकार (DEM/SUP/SR-S/SR-R/KEY/RND/GAP) + Freshness. जाड = A, ठिपक्यांची = B/C. "
                       "रुंद zones ची दुसरी किनार ('↔ outer') बारीक ठिपक्यांत.")
            sub_header("📋 Levels (किंमतीजवळचे, चार्टवर दाखवलेले)", HDR_PURPLE)
            st.dataframe(R.levels_table(near, price), width="stretch", hide_index=True)
            with st.expander("सर्व गुणांकित levels", expanded=False):
                st.dataframe(R.levels_table(result["levels"], price), width="stretch", hide_index=True)
            with st.expander(f"नाकारलेले levels ({len(result['rejected'])}) — का नाकारले", expanded=False):
                st.dataframe(R.levels_table(result["rejected"], price), width="stretch", hide_index=True)
            if result["sweeps"]:
                with st.expander(f"SWEEP (spike wicks) — {len(result['sweeps'])}", expanded=False):
                    st.dataframe(pd.DataFrame(result["sweeps"]), width="stretch", hide_index=True)
            st.download_button("⬇️ Levels CSV", data=R.levels_table(result["levels"] + result["rejected"], price).to_csv(index=False),
                               file_name=f"opportunity_levels_{symbol}.csv", mime="text/csv", key="oe_dl_levels")

        with tab_events:
            sub_header("Structure accuracy CSV (Daily / 4H / 1H)", HDR_ORANGE)
            st.caption("प्रत्येक structure बदल: तारीख (bar_end), TF, event, नवीन state, किंमत, `trigger_bar` (प्रत्यक्ष trigger झालेला bar; reversal मध्ये confirmation bar पेक्षा आधीचा असू शकतो). हे चार्टवर पडताळा.")
            ev_tfs = st.multiselect("TF", ["1d", "4h", "1h", "15m"], default=["1d", "4h", "1h"], key="oe_ev_tfs", format_func=lambda t: TF_LABEL[t])
            table = journal.structure_table(tuple(ev_tfs))
            table = table[table["event"] != "SWEEP"].sort_values("time", ascending=False)
            st.dataframe(table.head(300), width="stretch", hide_index=True)
            st.download_button("⬇️ Structure CSV (Daily/4H/1H)", data=R.structure_csv(journal), file_name=f"opportunity_structure_{symbol}.csv", mime="text/csv", key="oe_dl_structure")

        with tab_quality:
            sub_header("डेटा गुणवत्ता", HDR_TEAL)
            per_tf, short = R.quality_report(frames)
            st.dataframe(per_tf, width="stretch", hide_index=True)
            st.caption("अपूर्ण (bar_is_full=False) bars: 15:15 चा 30M/1H bar, 13:15 चा 4H bar, आणि लहान/अपूर्ण session चा शेवट — हे ref_range/ADR मध्ये धरले जात नाहीत, पण structure मध्ये सामान्य candle.")
            if len(short):
                st.warning(f"लहान/अपूर्ण sessions ({len(short)}): ADR/ref_range मधून वगळले.")
                st.dataframe(short, width="stretch", hide_index=True)
    except Exception as e:
        st.error(f"Opportunity Engine मध्ये चूक: {type(e).__name__}: {e}")
