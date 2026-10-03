"""Opportunity Engine page (PR-1a) — Structure वही (Daily/4H/1H/15M/5M trend state), zones/levels (Level Quality सकट) आणि Structure accuracy CSV.
🎓 फक्त वाचन आणि प्रदर्शन: कुठलाही trade/order/DB write नाही, कुठलाही bot हे वापरत नाही; indicator-मुक्त (फक्त किंमत + ref_range मोजपट्टी).
PR-1a मध्ये पाया (trend state) बरोबर आहे का ते तुम्ही चार्टवर पडताळता — त्यानंतरच bias/detectors/backtest (PR-1b/1c)."""
import hashlib

import pandas as pd
import streamlit as st

import real_nifty_data
from opportunity_engine import report as R
from opportunity_engine import risk as RISK
from opportunity_engine.bias import apply_gate, resolve_bias
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import build_context
from opportunity_engine.detectors.base import Candidate
from opportunity_engine.config import TF_LABEL
from opportunity_engine.zones import build_levels
from safe_widgets import safe_number_input
from tradingview_chart import build_lightweight_chart_html
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE
from upstox_api import fetch_candles

SRC_OFFLINE = "Offline NIFTY (खरा डेटा, 2015 → 2024-03-27)"
SRC_LIVE = "Upstox (लाईव्ह, सध्याचा symbol)"
CHART_TFS = ["1d", "4h", "1h", "15m", "5m"]
SUPPORTED_SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")        # NSE/BSE index session (09:15–15:30); MCX (09:00–23:30) साठी session वेगळं — PR-1a मध्ये नाही


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


def _render_bias_tab(ctx, symbol, price):
    """आजचा bias, Daily veto स्थिती, pullback watch, आणि "candidate tester" (detectors PR-1c मध्ये; तोपर्यंत गृहीत candidate वर gate/risk तपासा)."""
    cfg = EngineConfig()
    bias = resolve_bias(ctx, cfg)
    sub_header("आजचा Bias", HDR_TEAL)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bias", bias.label)
    m2.metric("Primary HTF", f"{TF_LABEL[cfg.primary_htf]}: {R.STATE_LABEL.get(bias.primary_state, bias.primary_state)}")
    m3.metric("1H पुष्टी", R.STATE_LABEL.get(bias.one_h_state, bias.one_h_state or "—"))
    m4.metric("Daily (veto)", R.STATE_LABEL.get(bias.daily_state, bias.daily_state or "—"))
    st.write(" · ".join(bias.reasons))
    if bias.daily_early_reversal_long or bias.daily_early_reversal_short:
        st.info("Daily CHoCH च्या स्थितीत (early reversal) — veto नाही, पण Structure score मध्ये Daily-aligned गुण अर्धे आणि Daily resistance/supply location rule कडक.")
    watch = None
    if bias.direction:
        from opportunity_engine.bias import pullback_watch_zone
        watch = pullback_watch_zone(ctx, bias.direction)
    if watch:
        st.caption(f"Pullback watch zone (counter-trend breakout आला तर इथे वाट): {watch['zone_low']:,.2f} – {watch['zone_high']:,.2f} ({watch['reason']})")
    sub_header("🧪 Candidate tester (गृहीत trade वर gate + risk plan)", HDR_PURPLE)
    st.caption("Detectors (Gap/Trendline/Zone-Pullback…) PR-1c मध्ये येतील; तोपर्यंत एखादा गृहीत trade टाकून Bias/Gate/Daily-veto/Risk नियम तपासा. कुठलाही order होत नाही.")
    c1, c2, c3, c4, c5 = st.columns(5)
    direction = c1.selectbox("दिशा", ["LONG", "SHORT"], key="oe_t_dir")
    setup = c2.selectbox("Setup", ["D6", "D3", "D4", "D10", "D2", "D7", "D8", "D1", "D5", "D9"], key="oe_t_setup")
    entry = float(c3.number_input("Entry", value=float(round(price, 2)), step=1.0, key="oe_t_entry"))
    default_sl = round(price - 25.0, 2) if direction == "LONG" else round(price + 25.0, 2)
    sl_ref = float(c4.number_input("SL (structural level)", value=float(default_sl), step=1.0, key=f"oe_t_sl_{direction}"))
    kind = c5.selectbox("प्रकार", ["PULLBACK_END", "BREAKOUT", "REVERSAL"], key="oe_t_kind")
    cand = Candidate(setup_id=setup, direction=direction, time=ctx.time, entry=entry, sl_ref=sl_ref, kind=kind)
    gate = apply_gate(cand, bias, ctx, cfg)
    if gate.passed:
        st.success("Gate: पास ✅")
    else:
        st.warning("Gate: नाकारला ❌ — " + " · ".join(f"{c} ({t})" for c, t in zip(gate.codes, gate.reasons)))
        if gate.pullback_in_progress:
            st.info("हा pullback मानला (trade नाही) — PULLBACK_IN_PROGRESS" + (f"; watch zone {gate.watch['zone_low']:,.0f}–{gate.watch['zone_high']:,.0f}" if gate.watch else ""))
    ref = ctx.get("15m").ref_range if ctx.get("15m") else None
    plan = RISK.plan_trade(cand, ctx, cfg, ref, ctx.adr, symbol)
    st.dataframe(pd.DataFrame([{"Entry": plan.entry, "SL (buffer सह)": round(plan.sl, 2), "T1 (1R)": round(plan.t1, 2), "T2": round(plan.t2, 2), "Risk pts": round(plan.risk, 2),
                                "ADR": None if ctx.adr != ctx.adr else round(ctx.adr, 1), "Risk/ADR": None if plan.adr_ratio is None else round(plan.adr_ratio, 2),
                                "HTF अडथळा (R)": None if plan.rr_to_opposing is None else round(plan.rr_to_opposing, 2),
                                "Risk नियम": "ठीक" if plan.ok else ", ".join(plan.rejects)}]), width="stretch", hide_index=True)


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]

    mega_header(f"🎯 {symbol} — Opportunity Engine (PR-1a: Structure + Levels)", HDR_BLUE)
    st.caption(
        "Price-action structure (HH/HL/LH/LL, BOS/CHoCH/Reversal) + Supply/Demand/S-R/Gap levels + Level Quality grade — **फक्त वाचन आणि प्रदर्शन**. "
        "कुठलाही trade/order होत नाही, कुठलाही bot हे वापरत नाही. Indicator-मुक्त (EMA/RSI/ATR/Supertrend नाही). "
        "पाया (trend state) चार्टवर तुम्ही पडताळल्यावरच पुढचे टप्पे."
    )
    if symbol not in SUPPORTED_SYMBOLS:
        st.warning(f"Opportunity Engine (PR-1a) फक्त {', '.join(SUPPORTED_SYMBOLS)} साठी (NSE/BSE session 09:15–15:30). {symbol} साठी session वेगळं असल्याने इथे दाखवलं जात नाही.")
        return
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
        result = build_levels(journal, frames, symbol, price, fine=frames.get("5m"))
        ctx = build_context(journal, levels=result["levels"], daily_df=frames.get("1d"), price=price, flips=result["rejected"])
        tab_state, tab_bias, tab_chart, tab_events, tab_quality = st.tabs(["🧭 Structure वही", "🎯 Bias / Gate", "📊 चार्ट + Levels", "📋 Events / CSV", "🔎 डेटा गुणवत्ता"])

        with tab_state:
            sub_header("प्रत्येक Timeframe चा सद्य trend state", HDR_TEAL)
            st.dataframe(R.state_rows(journal), width="stretch", hide_index=True)
            st.caption(
                "State: Uptrend/Downtrend (HH-HL / LH-LL), Pullback (नवीन high नंतर खाली, protected अबाधित), कमजोर = CHoCH (protected level खाली/वर **close**), "
                "Reversal confirm = CHoCH नंतर LH + CHoCH low खाली close, Range = अडकलेले swings. सर्व break फक्त CLOSE ने; wick = SWEEP."
            )
            swing_tf = st.radio("Swings दाखवा", CHART_TFS[:4], index=1, horizontal=True, key="oe_swing_tf", format_func=lambda t: TF_LABEL[t])
            st.dataframe(R.swings_table(journal, swing_tf), width="stretch", hide_index=True)

        with tab_bias:
            _render_bias_tab(ctx, symbol, price)

        with tab_chart:
            tf = st.radio("चार्ट Timeframe", CHART_TFS, index=2, horizontal=True, key="oe_chart_tf", format_func=lambda t: TF_LABEL[t])
            m1, m2, m3 = st.columns(3)
            max_levels = int(m1.number_input("जास्तीत जास्त levels", min_value=2, max_value=30, value=12, step=1, key="oe_max_levels"))
            max_dist = float(m2.number_input("कमाल अंतर %", min_value=0.5, max_value=10.0, value=3.0, step=0.5, key="oe_max_dist"))
            grades = m3.multiselect("Grades", ["A", "B", "C"], default=["A", "B"], key="oe_grades")
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
