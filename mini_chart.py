"""
mini_chart.py
--------------
🎓 "Dashboard वर mini NIFTY/BANKNIFTY chart" -- लहान candlestick चार्ट दोन बाजूला (5-मिनिट candles). आता live: live_chart.py चा एकच fragment (दर 3 सेकंदांनी
एकच LTP कॉल दोन्ही symbols साठी) चालू candle हलवतो आणि वरचा भाव / बदल% लाइव्ह करतो. candles fetch_candles() (ttl=60 cache) वरून, म्हणून html दर मिनिटाला
ताजा होतो (त्या वेळी फक्त हे लहान iframe पुन्हा लोड होतात) -- Upstox वर नवीन candle कॉल जास्तीत जास्त मिनिटाला एकदा.
"""
import streamlit as st

from live_chart import infer_tf_seconds, render_live_charts
from tradingview_chart import build_mini_chart_html
from upstox_api import fetch_candles, get_instrument_key

MINI_CHART_SYMBOLS = ("NIFTY", "BANKNIFTY")


def _mini_html(token, symbol):
    try:
        # current_spot फक्त cache key आहे (fetch_candles मध्ये वापरत नाही) -- 0 => स्थिर key, spot बदलल्यावर cache-miss नाही.
        df = fetch_candles(token, symbol, 0, interval="5minute", lookback_days=5)
    except Exception:
        df = None
    return build_mini_chart_html(df, symbol, height=220, live_tf_seconds=infer_tf_seconds(df) if df is not None and not df.empty else None)


def render_mini_charts():
    token = st.session_state.get("token_input", "")
    if not token.strip():
        return
    # दोन चार्ट दोन बाजूला (side_by_side); एक fragment, एकच LTP कॉल.
    charts = [
        {"key": f"mini_{sym}", "html_fn": (lambda s=sym: _mini_html(token, s)), "instrument_key": get_instrument_key(sym), "height": 225}
        for sym in MINI_CHART_SYMBOLS
    ]
    render_live_charts("mini", charts, token, "NSE", side_by_side=True)
