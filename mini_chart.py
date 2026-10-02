"""
mini_chart.py
--------------
🎓 "Dashboard वर mini NIFTY/BANKNIFTY chart" -- लहान candlestick चार्ट दोन बाजूला (आजचे 5-मिनिट candles), live_ticker.py सारखाच स्वतंत्र
`st.fragment` -- दर MINI_CHART_REFRESH_SECONDS ला फक्त हा भाग पुन्हा रेंडर होतो (संपूर्ण पान हलत नाही). खरा live tick नाही (तो वेगळा टप्पा);
fetch_candles() चा ttl=60 cache असल्याने प्रत्येक रिफ्रेशला Upstox वर नवीन कॉल जास्तीत जास्त मिनिटाला एकदा.
"""
import streamlit as st

from tradingview_chart import build_mini_chart_html
from upstox_api import fetch_candles

MINI_CHART_REFRESH_SECONDS = 60
MINI_CHART_SYMBOLS = ("NIFTY", "BANKNIFTY")


def _render_mini_charts_body():
    token = st.session_state.get("token_input", "")
    if not token.strip():
        return
    cols = st.columns(len(MINI_CHART_SYMBOLS))
    for col, symbol in zip(cols, MINI_CHART_SYMBOLS):
        with col:
            try:
                # current_spot फक्त cache key आहे (fetch_candles मध्ये वापरत नाही) -- 0 => स्थिर key, spot बदलल्यावर cache-miss नाही.
                df = fetch_candles(token, symbol, 0, interval="5minute", lookback_days=5)
            except Exception:
                df = None
            st.components.v1.html(build_mini_chart_html(df, symbol, height=220), height=225, scrolling=False)


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{MINI_CHART_REFRESH_SECONDS}s")
    def render_mini_charts():
        _render_mini_charts_body()
else:
    def render_mini_charts():
        _render_mini_charts_body()
