"""
live_ticker.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Professional Grade — Blink फिक्स) — आधी संपूर्ण
Dashboard पान दर १ मिनिटाला पूर्णपणे पुन्हा चालायचं (chart/tabs क्षणभर नाहीसं होऊन परत यायचं —
लक्षणीय "blink", अव्यावसायिक दिसायचं). आता फक्त किंमत/P&L टिकर इथे, स्वतंत्र `@st.fragment`
मध्ये — दर काही सेकंदांनी **फक्त हाच छोटा भाग** नव्याने रेंडर होतो, बाकीचं संपूर्ण पान (chart,
tabs, sidebar) अजिबात हलत नाही. संपूर्ण पानाचं रिफ्रेश आता दर ५ मिनिटांनी (app.py) —
chart/Direction Engine/Signal Engine इतक्या वारंवार बदलायची गरजच नाही.

Fragment बाकीच्या script-execution पासून स्वतंत्र चालत असल्यामुळे, याला लागणारा डेटा (LTP,
positions) स्वतःच, हलकेपणाने (पूर्ण Option Chain न मागवता — फक्त underlying चा LTP) मागवतो.

🎓 वापरकर्त्याने सापडवलेली bug (Dashboard वरचा NIFTY LTP Upstox च्या live LTP च्या तुलनेत laggy
दिसत होता) — आधी page_dashboard.py मध्ये headline "🟢 SYMBOL LIVE DATA" कार्ड वेगळाच, static
होता (फक्त दर ५-मिनिटांच्या पूर्ण-पान रिफ्रेशवर अद्ययावत होणाऱ्या underlying_price वर अवलंबून),
तर हाच fragment त्याच्याच शेजारी वेगळी, ताजी किंमत st.metric() मध्ये दाखवायचा — एकाच पानावर
दोन वेगवेगळ्या वेगाने अपडेट होणारे LTP, कधीकधी वेगळे आकडे. आता headline कार्ड इथेच, याच
fragment चा भाग — एकच स्रोत, कुठलाही duplicate/स्टेल display उरलेला नाही. रिफ्रेश गतीही ६०
वरून १५ सेकंदांवर आणली (fetch_ltp_map() एकाच instrument साठीचा हलका कॉल — इतक्या वारंवार
चालवणं सुरक्षित).
"""
import streamlit as st

from upstox_api import get_instrument_key, fetch_ltp_map
from database import get_live_positions_with_mtm, get_todays_realized_pnl
from config import get_ist_now

TICKER_REFRESH_SECONDS = 15


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

    ltp_display = f"₹{current_ltp:,.2f}" if current_ltp is not None else "—"
    st.markdown(
        f"""
        <div style="background-color:#1e222d;border:1px solid #2a2e3d;border-radius:6px;padding:10px 14px;">
            <div style="font-size:12px;color:#787b86;letter-spacing:0.5px;">
                🟢 {symbol} · LIVE DATA
            </div>
            <div style="font-size:26px;font-weight:bold;color:#d1d4dc;font-variant-numeric:tabular-nums;">
                {ltp_display}
            </div>
            <div style="font-size:11px;color:#9598a1;">
                शेवटचं: {get_ist_now().strftime('%H:%M:%S')} IST (दर {TICKER_REFRESH_SECONDS} सेकंदांनी स्वतंत्रपणे ताजा)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 🎓 वापरकर्त्याने मागितलेली सुधारणा — आधी फक्त उघड्या (OPEN) positions चा MTM दिसायचा, आज
    # आधीच बंद (exit) झालेल्या trades चा realized P&L त्यात धरलाच जायचा नाही. आता दोन्ही एकत्र —
    # उघड्या positions चा सद्य MTM + आजच बंद झालेल्या (LIVE व PAPER दोन्ही, symbol हाच) trades चा
    # realized P&L — म्हणजे आजचा खरा संपूर्ण (एकत्रित) profit/loss.
    total_today_pnl = None
    try:
        open_mtm = 0.0
        positions_df = get_live_positions_with_mtm(token_input, symbol)
        if not positions_df.empty and "MTM (Rs)" in positions_df.columns:
            valid_mtm = positions_df["MTM (Rs)"].dropna()
            if not valid_mtm.empty:
                open_mtm = valid_mtm.sum()
        live_realized, _ = get_todays_realized_pnl(symbol, "LIVE")
        paper_realized, _ = get_todays_realized_pnl(symbol, "PAPER")
        total_today_pnl = open_mtm + live_realized + paper_realized
    except Exception:
        pass  # Positions/P&L मिळाले नाहीत तरी टिकर क्रॅश होऊ नये

    st.metric("आजच्या Position चा MTM (Exit सह, एकूण P&L)", f"₹{total_today_pnl:,.0f}" if total_today_pnl is not None else "—")


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{TICKER_REFRESH_SECONDS}s")
    def render_live_ticker():
        _render_ticker_body()
else:
    def render_live_ticker():
        # established जुनी Streamlit आवृत्ती (fragment उपलब्ध नाही, established >=1.37 लागतो) —
        # क्रॅश होण्याऐवजी established जुन्याच (पूर्ण-पान रिफ्रेशवर अवलंबून) पद्धतीने दाखवणे.
        st.caption("⚠️ Live ticker fragment साठी Streamlit >=1.37 लागतो — सध्याची आवृत्ती जुनी आहे, पूर्ण-पान रिफ्रेशवरच अवलंबून.")
        _render_ticker_body()
