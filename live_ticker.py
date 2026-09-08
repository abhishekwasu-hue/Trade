"""
live_ticker.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Professional Grade — Blink फिक्स) — established आधी
संपूर्ण Dashboard पान दर १ मिनिटाला पूर्णपणे पुन्हा चालायचं (chart/tabs क्षणभर नाहीसं होऊन परत यायचं —
लक्षणीय "blink", अव्यावसायिक दिसायचं). आता फक्त किंमत/P&L टिकर इथे, established स्वतंत्र
`@st.fragment(run_every="60s")` मध्ये — दर ६० सेकंदाला **फक्त हाच छोटा भाग** नव्याने रेंडर होतो,
बाकीचं संपूर्ण पान (chart, tabs, sidebar) अजिबात हलत नाही. संपूर्ण पानाचं रिफ्रेश आता established
दर ५ मिनिटांनी (app.py) — chart/Direction Engine/Signal Engine इतक्या वारंवार बदलायची गरजच नाही.

Fragment established बाकीच्या script-execution पासून स्वतंत्र चालत असल्यामुळे, याला लागणारा डेटा
(LTP, positions) established स्वतःच, हलकेपणाने (पूर्ण Option Chain न मागवता — फक्त underlying चा
LTP) मागवतो.
"""
import streamlit as st

from upstox_api import get_instrument_key, fetch_ltp_map
from database import get_live_positions_with_mtm
from config import get_ist_now


def _render_ticker_body():
    token_input = st.session_state.get("token_input", "")
    symbol = st.session_state.get("symbol", "NIFTY")
    if not token_input.strip():
        return

    current_ltp = None
    try:
        instrument_key = get_instrument_key(symbol)
        ltp_map = fetch_ltp_map(token_input, [instrument_key])
        current_ltp = ltp_map.get(instrument_key)
    except Exception:
        pass  # LTP मिळाला नाही तरी टिकर क्रॅश होऊ नये — "—" दाखवेल

    total_mtm = None
    try:
        positions_df = get_live_positions_with_mtm(token_input, symbol)
        if not positions_df.empty and "MTM (Rs)" in positions_df.columns:
            valid_mtm = positions_df["MTM (Rs)"].dropna()
            if not valid_mtm.empty:
                total_mtm = valid_mtm.sum()
    except Exception:
        pass  # Positions मिळाले नाहीत तरी टिकर क्रॅश होऊ नये

    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        st.metric(f"{symbol} LTP", f"₹{current_ltp:,.2f}" if current_ltp is not None else "—")
    with tcol2:
        st.metric("उघड्या Positions चा एकूण MTM", f"₹{total_mtm:,.0f}" if total_mtm is not None else "—")
    with tcol3:
        st.caption(f"🟢 Live — शेवटचं: {get_ist_now().strftime('%H:%M:%S')} (दर ६० सेकंदाला स्वतंत्रपणे ताजा)")


if hasattr(st, "fragment"):
    @st.fragment(run_every="60s")
    def render_live_ticker():
        _render_ticker_body()
else:
    def render_live_ticker():
        # established जुनी Streamlit आवृत्ती (fragment उपलब्ध नाही, established >=1.37 लागतो) —
        # क्रॅश होण्याऐवजी established जुन्याच (पूर्ण-पान रिफ्रेशवर अवलंबून) पद्धतीने दाखवणे.
        st.caption("⚠️ Live ticker fragment साठी Streamlit >=1.37 लागतो — सध्याची आवृत्ती जुनी आहे, पूर्ण-पान रिफ्रेशवरच अवलंबून.")
        _render_ticker_body()
