"""
live_chart.py
--------------
🎓 "Live updates" (चार्टवरची शेवटची candle हलणे) -- REST LTP polling, दर LIVE_CHART_REFRESH_SECONDS (3) सेकंदांनी. WebSocket वापरलेला नाही:
Upstox च्या normal account ला फक्त 2 WebSocket connections मिळतात आणि दोन्ही आधीच position stream monitors (NSE + MCX) वापरतात -- तिसरा उघडला
तर exit monitor बंद पडू शकतो.

रचना:
  - चार्ट HTML (tradingview_chart) आतल्या iframe मध्ये एकदाच लोड होतो; Python (एक `st.fragment`, run_every=3s) फक्त सद्य LTP आणून `tick` पाठवतो,
    आतला JS शेवटची candle बदलतो / वेळ झाली की नवीन candle सुरू करतो. म्हणून zoom / Drawing Tools / indicator बटणं कायम राहतात.
  - html फक्त बदलल्यावर पाठवला जातो (hash), प्रत्येक tick बरोबर ~200KB नाही.
  - बाजार बंद असेल तर किंमत आणलीच जात नाही ("बाजार बंद" badge), आणि LTP मिळाला नाही तर "जुना डेटा" badge -- खोटी live किंमत कधीच नाही.
  - Indicators (EMA/BB/ADX/Supertrend) आणि चालू candle चा volume live बदलत नाहीत; ते पुढच्या पूर्ण refresh (REST candles) मध्ये दुरुस्त होतात.
"""
import hashlib
import os

import streamlit as st
import streamlit.components.v1 as components

from config import get_ist_now, is_market_open, is_mcx_market_open
from tradingview_chart import _to_unix_time
from upstox_api import fetch_ltp_map

LIVE_CHART_REFRESH_SECONDS = 3
_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "live_chart_component")
_KNOWN_TF_SECONDS = (60, 300, 900, 1800, 3600)
_MARKET_OPEN_FNS = {"NSE": is_market_open, "MCX": is_mcx_market_open}

_component = None


def infer_tf_seconds(df):
    """चार्टच्या **प्रत्यक्ष** candles वरून कालावधी (सेकंद) -- शेवटच्या ~30 candles मधलं मध्यमान अंतर, जवळच्या ज्ञात timeframe ला. मागवलेल्या interval
    वर विश्वास ठेवत नाही (उदा. MCX साठी '1hour' मागितलं तरी fetch_mcx_candles प्रत्यक्षात 30-मिनिट देतो). Daily / अपुरा डेटा => None (live candle बदल नाही)."""
    try:
        diffs = df["timestamp"].diff().dropna().tail(30).dt.total_seconds()
        if diffs.empty:
            return None
        median = float(diffs.median())
    except Exception:
        return None
    best = min(_KNOWN_TF_SECONDS, key=lambda t: abs(t - median))
    return best if abs(best - median) <= best * 0.1 else None


def _component_fn():
    global _component
    if _component is None:
        _component = components.declare_component("live_chart", path=_COMPONENT_DIR)
    return _component


def build_tick(price, status):
    """आतल्या चार्टला पाठवायचा संदेश. status: 'live' | 'stale' | 'closed'. time = चार्टच्या candles सारख्याच convention मध्ये (IST wall-clock)."""
    now = get_ist_now()
    return {
        "type": "live_tick", "status": status, "price": float(price) if price else None,
        "time": _to_unix_time(now), "label": now.strftime("%H:%M:%S"),
    }


def fetch_group_ticks(token, market, instrument_keys, market_open_fn=None, ltp_fn=None):
    """{instrument_key: tick} -- एकाच LTP कॉलमध्ये सर्व keys. बाजार बंद => कॉलच नाही; fetch अयशस्वी / key गहाळ => 'stale'."""
    market_open_fn = market_open_fn or _MARKET_OPEN_FNS.get(market, is_market_open)
    if not market_open_fn():
        return {k: build_tick(None, "closed") for k in instrument_keys}
    ltp_fn = ltp_fn or fetch_ltp_map
    try:
        ltp_map = ltp_fn(token, list(instrument_keys)) or {}
    except Exception:
        ltp_map = {}
    return {k: build_tick(ltp_map.get(k), "live" if ltp_map.get(k) else "stale") for k in instrument_keys}


def live_chart(html, tick, key, height, component_fn=None):
    """एक चार्ट. html फक्त पहिल्यांदा (किंवा बदलल्यावर / शेलने मागितल्यावर) पाठवतो. component_fn फक्त टेस्टसाठी बदलता येतो."""
    component_fn = component_fn or _component_fn()
    html_hash = hashlib.md5(html.encode("utf-8")).hexdigest()
    sent = st.session_state.setdefault("_live_chart_sent", {})
    handled = st.session_state.setdefault("_live_chart_need_handled", {})
    previous_value = st.session_state.get(f"_lc_{key}")
    # शेल remount झाला / hash माहित नाही => तो प्रत्येक विनंतीला नवीन (अद्वितीय) "need_html:..." value पाठवतो. component ची value पुढच्या रनमध्ये तशीच राहते, म्हणून
    # प्रत्येक विनंती **एकदाच** हाताळतो (handled मध्ये नोंद) -- नाहीतर प्रत्येक tick ला html पुन्हा पाठवला जाऊन चार्ट सतत reload होतो (zoom / drawings जातात).
    if isinstance(previous_value, str) and previous_value.startswith("need_html") and handled.get(key) != previous_value:
        handled[key] = previous_value
        sent.pop(key, None)
    send_html = sent.get(key) != html_hash
    if send_html:
        sent[key] = html_hash
    return component_fn(
        html=html if send_html else "", html_hash=html_hash, tick=tick, height=height, key=f"_lc_{key}", default=None,
    )


def _render_group(group_id):
    spec = st.session_state.get(f"_live_group_{group_id}")
    if not spec:
        return
    charts = spec["charts"]
    ticks = fetch_group_ticks(spec["token"], spec["market"], [c["instrument_key"] for c in charts]) if spec["token"] else {}
    # columns fragment च्या **आत** बनवतो -- fragment च्या बाहेर बनवलेल्या container मध्ये fragment ने लिहिलं तर प्रत्येक रनला element जमा होत जातात.
    slots = st.columns(len(charts)) if spec.get("side_by_side") and len(charts) > 1 else [st.container() for _ in charts]
    for slot, chart in zip(slots, charts):
        # html_fn दिलं असेल तर प्रत्येक रनला ताजा html बनवतो (उदा. mini charts -- fetch_candles cached असल्याने हलकं; html बदलला तरच iframe पुन्हा लोड होतो).
        html_fn = chart.get("html_fn")
        try:
            html = html_fn() if html_fn else chart["html"]
        except Exception:
            html = chart.get("html")
        if not html:
            continue
        tick = ticks.get(chart["instrument_key"])
        # lines_fn(price) -> Positions चार्टच्या सद्य रेषा (उदा. MCX Trailing SL) -- tick बरोबर पाठवल्या जातात, आतला चार्ट रेषा हलवतो (html बदलत नाही => zoom/drawings कायम).
        lines_fn = chart.get("lines_fn")
        if lines_fn is not None:
            try:
                lines = lines_fn(tick.get("price") if tick else None)
            except Exception:
                lines = None
            if lines is not None:
                tick = {**(tick or build_tick(None, "stale")), "lines": lines}
        with slot:
            live_chart(html, tick, chart["key"], chart["height"])


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{LIVE_CHART_REFRESH_SECONDS}s")
    def _live_group_fragment(group_id):
        _render_group(group_id)
else:
    def _live_group_fragment(group_id):
        _render_group(group_id)


def render_live_charts(group_id, charts, token, market, side_by_side=False):
    """charts: [{"key", "html" (किंवा "html_fn"), "instrument_key", "height", "lines_fn" (वैकल्पिक: price -> सद्य रेषांची यादी)}].
    सर्व charts मिळून एकच fragment आणि एकच LTP कॉल (दर 3 सेकंदांनी)."""
    st.session_state[f"_live_group_{group_id}"] = {"charts": charts, "token": token, "market": market, "side_by_side": side_by_side}
    _live_group_fragment(group_id)
