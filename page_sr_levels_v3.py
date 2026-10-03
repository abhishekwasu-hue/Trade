"""SR Levels V3 page — नवीन (प्रयोगिक) Support/Resistance इंजिन, फक्त चार्टवर दाखवण्यासाठी.
🎓 वापरकर्त्याशी चर्चा करून जोडलेलं: Recency + Reaction + MTF confluence + PDH/PDL/PWH/PWL + Role-reversal + Gaps एकत्र करून
गुणांकित (A/B/C) levels. हे पान कुठलाही trade/order करत नाही आणि कुठल्याही bot ला जोडलेलं नाही — जुने bots आणि जुना
Dynamic S/R (sr_dynamic.py) जसेच्या तसे चालू राहतात. पडताळणी -> paper -> live असा टप्पा-टप्प्याने वापर."""
import pandas as pd
import streamlit as st

from safe_widgets import safe_number_input
from sr_dynamic import compute_dynamic_sr
from sr_levels_v3 import SRConfig, TF_SHORT, compute_sr_v3, select_display_levels, to_chart_lines
from sr_v3_chart import CHART_TFS, load_frames
from tradingview_chart import build_lightweight_chart_html
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE
from upstox_api import fetch_candles

ROLE_LABEL = {"SUPPORT": "Support", "RESISTANCE": "Resistance", "ZONE": "झोनमध्ये"}


def _levels_table(levels):
    rows = []
    for z in levels:
        rows.append({
            "Level": round(z["level"], 2), "झोन": f"{z['low']:.2f} – {z['high']:.2f}",
            "भूमिका": ROLE_LABEL.get(z["role"], z["role"]), "Score": z["score"], "ग्रेड": z["grade"],
            "अंतर %": z["distance_pct"], "Timeframes": ", ".join(TF_SHORT[tf] for tf in z["tfs"]) or "—",
            "Pivots": z["pivot_count"], "Tags": " · ".join(z["tags"]) or "—",
            "Touch": z["components"]["touches"], "Reaction": z["components"]["reaction"],
            "MTF": z["components"]["confluence"], "Key": z["components"]["key_level"],
            "Polarity": z["components"]["polarity"], "Flip": z["components"]["role_reversal"], "Gap": z["components"]["gap"],
            "Rejections": z.get("rejections", 0), "Rej गुण": z["components"].get("rejections", 0.0),
            "Core झोन": f"{z['core_low']:.2f} – {z['core_high']:.2f}" if "core_low" in z else "—",
            "Anchor": (f"{z['anchor']['kind']} {TF_SHORT.get(z['anchor']['tf'], z['anchor']['tf'] or '')} {z['anchor']['name'] or ''}".strip()
                       if z.get("anchor") else "—"),
        })
    return pd.DataFrame(rows)


def levels_csv(levels):
    """सर्व levels (फिल्टरपूर्वीचे) CSV मजकूर — तपासणी/शेअर करण्यासाठी (pure function, चाचणीयोग्य)."""
    return _levels_table(levels).to_csv(index=False)


def candles_csv(df, max_rows=1500):
    """चार्टवरचे शेवटचे `max_rows` candles CSV मजकूर (timestamp, OHLC, volume)."""
    cols = [c for c in ("timestamp", "open", "high", "low", "close", "volume") if c in df.columns]
    return df[cols].tail(int(max_rows)).to_csv(index=False)


def nearest_level_distance(levels, manual_price):
    """तुमच्या हाताने काढलेल्या level जवळची इंजिन level आणि अंतर (pts). levels रिकामी किंवा manual_price<=0 => None."""
    try:
        manual = float(manual_price)
    except (TypeError, ValueError):
        return None
    if not levels or not manual > 0:
        return None
    nearest = min(levels, key=lambda z: abs(z["level"] - manual))
    return {"level": nearest["level"], "points": round(nearest["level"] - manual, 2), "zone": (nearest["low"], nearest["high"]),
            "inside_zone": nearest["low"] <= manual <= nearest["high"], "grade": nearest["grade"], "score": nearest["score"]}


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]
    underlying_price = st.session_state["underlying_price"]

    mega_header(f"🧭 {symbol} — SR Levels V3 (नवीन, प्रयोगिक)", HDR_BLUE)
    st.caption(
        "Recency + Reaction + MTF confluence + मागचा दिवस/आठवडा High-Low + Role-reversal + Gaps — सर्व एकत्र, गुणांकित. "
        "⚠️ हे फक्त चार्टवर दाखवण्यासाठी आहे — इथून कुठलाही trade होत नाही, कुठलाही bot हे वापरत नाही."
    )
    if not token_input:
        st.info("⬅️ सुरू करण्यासाठी साईडबारमध्ये तुमचा Upstox Access Token टाका.")
        return

    c1, c2 = st.columns([2, 3])
    with c1:
        chart_tf = st.radio("चार्ट Timeframe", CHART_TFS, index=1, horizontal=True, key="srv3_tf")
    with c2:
        compare_old = st.checkbox("जुने Dynamic SR v2 levels सुद्धा दाखवा (तुलनेसाठी)", value=False, key="srv3_compare_old")

    defaults = SRConfig()
    with st.expander("⚙️ Advanced — पॅरामीटर्स (तपासणीसाठी)", expanded=False):
        st.caption("प्रत्येक TF चे किती दिवसांचे pivots विचारात घ्यायचे (डीफॉल्ट: 5M=3, 15M=5, 30M=8, 1H=10 दिवस).")
        lb_cols = st.columns(4)
        lookback = {}
        for col, tf in zip(lb_cols, ("5minute", "15minute", "30minute", "1hour")):
            with col:
                lookback[tf] = safe_number_input(
                    f"{TF_SHORT[tf]} दिवस", value=defaults.lookback_days[tf], min_value=1, max_value=30, step=1, key=f"srv3_lb_{tf}",
                )
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            half_life = safe_number_input("Recency half-life (दिवस)", value=defaults.recency_half_life_days, min_value=0.5,
                                          max_value=30.0, step=0.5, key="srv3_half_life")
        with p2:
            min_score = safe_number_input("किमान Score", value=defaults.min_score, min_value=0.0, max_value=100.0, step=5.0, key="srv3_min_score")
        with p3:
            max_levels = safe_number_input("जास्तीत जास्त levels", value=defaults.max_levels, min_value=2, max_value=30, step=1, key="srv3_max_levels")
        with p4:
            max_distance = safe_number_input("कमाल अंतर %", value=defaults.max_distance_pct, min_value=0.5, max_value=10.0, step=0.5, key="srv3_max_dist")

    cfg = SRConfig(
        lookback_days={**defaults.lookback_days, **lookback}, recency_half_life_days=half_life,
        min_score=min_score, max_levels=int(max_levels), max_distance_pct=max_distance,
    )

    try:
        with st.spinner("5M/15M/30M/1H/Daily डेटा आणि levels मोजत आहे..."):
            frames, daily_df = load_frames(fetch_candles, token_input, symbol)
            if chart_tf not in frames:
                st.warning(f"{chart_tf} चा डेटा मिळाला नाही.")
                return
            chart_df = frames[chart_tf]
            price = float(chart_df["close"].iloc[-1])
            result = compute_sr_v3(frames, daily_df=daily_df, current_price=price, cfg=cfg)
        levels = result["levels"]
        meta = result["meta"]
        if not levels:
            st.info("पुरेशा डेटामुळे levels सापडले नाहीत.")
            return
        shown = select_display_levels(levels, price, cfg)

        sub_header("🎯 जवळचे Levels", HDR_TEAL)
        above = sorted([z for z in shown if z["level"] > price], key=lambda z: z["level"])
        below = sorted([z for z in shown if z["level"] <= price], key=lambda z: -z["level"])
        m1, m2, m3 = st.columns(3)
        m1.metric("सध्याची किंमत", f"{price:,.2f}")
        if above:
            m2.metric("जवळचा Resistance", f"{above[0]['level']:,.2f}", f"{above[0]['distance_pct']:+.2f}% · {above[0]['grade']}{above[0]['score']:.0f}")
        else:
            m2.metric("जवळचा Resistance", "—")
        if below:
            m3.metric("जवळचा Support", f"{below[0]['level']:,.2f}", f"{below[0]['distance_pct']:+.2f}% · {below[0]['grade']}{below[0]['score']:.0f}")
        else:
            m3.metric("जवळचा Support", "—")

        sub_header("📊 चार्ट", HDR_PURPLE)
        old_sr = None
        if compare_old:
            old_sr = compute_dynamic_sr(chart_df, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2,
                                        mintick=0.05 if symbol in ("NIFTY", "BANKNIFTY") else None)
        html = build_lightweight_chart_html(
            chart_df, symbol=symbol, timeframe_label=chart_tf, height=600,
            trade_lines=to_chart_lines(shown), sr_levels=old_sr,
        )
        st.components.v1.html(html, height=650, scrolling=False)
        st.caption(
            "रेषेचं नाव: **S/R** (Support/Resistance) + **ग्रेड व Score** + स्रोत (TF / PDH-PDL-PWH-PWL / GAP / FLIP). "
            "जाड रेषा = जास्त Score (A). ठिपक्यांची रेषा = कमी Score (C) किंवा स्वतंत्र Gap झोन."
            + (" जुने Dynamic SR v2 levels चार्टच्या स्वतःच्या R/S रेषांमध्ये (touches सह) दिसतात." if compare_old else "")
        )
        st.caption(
            f"वापरलेले TF: {', '.join(TF_SHORT[tf] for tf in meta['frames'])} · Zone tolerance ±{meta['tol']} pts "
            f"({TF_SHORT.get(meta['ref_tf'], meta['ref_tf'])} ATR {meta['atr_ref']}) · एकूण pivots: {meta['pivot_count']} · एकूण levels: {len(levels)}"
        )

        sub_header("📏 तुमच्या हाताच्या level शी तुलना", HDR_TEAL)
        manual_price = safe_number_input("तुम्ही हाताने काढलेली level (0 = वापरू नका)", value=0.0, min_value=0.0, step=0.05, key="srv3_manual_level")
        near = nearest_level_distance(levels, manual_price)
        if near:
            x1, x2, x3 = st.columns(3)
            x1.metric("इंजिनची जवळची level", f"{near['level']:,.2f}", f"{near['grade']}{near['score']:.0f}")
            x2.metric("तुमची level vs इंजिन (pts)", f"{near['points']:+.2f}")
            x3.metric("तुमची level इंजिनच्या झोनमध्ये?", "होय" if near["inside_zone"] else "नाही",
                      f"झोन {near['zone'][0]:.2f} – {near['zone'][1]:.2f}")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("⬇️ Levels CSV", data=levels_csv(levels), file_name=f"sr_v3_levels_{symbol}_{chart_tf}.csv", mime="text/csv", key="srv3_dl_levels")
        with d2:
            st.download_button("⬇️ Candles CSV", data=candles_csv(chart_df), file_name=f"sr_v3_candles_{symbol}_{chart_tf}.csv", mime="text/csv", key="srv3_dl_candles")

        sub_header("📋 Levels (दाखवलेले)", HDR_BLUE)
        st.dataframe(_levels_table(sorted(shown, key=lambda z: -z["score"])), width="stretch", hide_index=True)
        with st.expander("सर्व levels (फिल्टर करण्याआधीचे)", expanded=False):
            st.dataframe(_levels_table(levels), width="stretch", hide_index=True)
        with st.expander("ℹ️ Score कसा ठरतो (कमाल 100)", expanded=False):
            st.markdown(
                "- **Touch (30):** झोनमधले ताजे pivots — नवीन pivot जास्त वजनाचा (half-life), मोठ्या TF चा जास्त वजनाचा. एकच swing अनेक TF मध्ये दिसला तर बेरीज होत नाही.\n"
                "- **Reaction (20):** त्या pivot पासून किंमत ATR च्या किती पट उलटली (खरी विक्री/खरेदी कुठून आली).\n"
                "- **MTF (25):** 5M=3, 15M=5, 30M=7, 1H=10 गुण — जितके जास्त वेगळे TF, तितका जास्त.\n"
                "- **Key (40 पर्यंत):** PDH/PDL=30, PDC=15, PWH/PWL=35.\n"
                "- **Polarity (5):** झोनवर आधी high आणि low दोन्ही pivots झालेले (दोन्ही बाजूंनी पाळलेला).\n"
                "- **Flip (10 + 5):** Resistance तुटून वर टिकला (आता Support) / उलट; retest झाला तर +5.\n"
                "- **Gap (10):** न भरलेल्या gap ची किनार या झोनवर. स्वतंत्र Gap झोनला 30 पाया.\n"
                "- **Rejections (10):** swing नंतर किंमत दूर जाऊन परत level जवळ आली आणि नाकारली गेली — वेगळ्या घटनांची संख्या (नाकारल्यानंतर ≥1 ATR चाल = strong).\n\n"
                "**रेषा कुठे?** झोनमधल्या सर्वात निर्णायक (मोठा TF × मोठी reaction; बरोबरीत सर्वात जुना) swing च्या **अचूक** किंमतीवर — सरासरीवर नाही. "
                "झोनची दुसरी किनार A/B साठी बारीक ठिपक्यांच्या रेषेत. किंमत झोनच्या ~5 pts आत असेल तर भूमिका \"झोनमध्ये\".\n\n"
                "ग्रेड: **A** ≥ 65 · **B** ≥ 45 · **C** बाकी. हा गुण *क्रमवारीसाठी* आहे — नफ्याची हमी/संभाव्यता नव्हे."
            )
    except Exception as e:
        st.error(f"SR Levels V3 मध्ये चूक: {type(e).__name__}: {e}")
