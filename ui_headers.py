"""
ui_headers.py
--------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — आधी Performance टॅबवर लागू केलेली रंगीत, मोठ्या फॉन्टची
heading पद्धत (Performance टॅब "crowded"/एकसुरी दिसत होता, ती सुधारल्यावर वापरकर्त्याने "हीच पद्धत
Dashboard च्या सर्व टॅब्सवर लावा" असं सांगितलं) — इथे एकाच जागी, जेणेकरून प्रत्येक page_*.py फाईलमध्ये
वेगळी copy-paste करावी लागू नये. तीन पातळ्या: mega (पानाच्या आतले मुख्य विभाग), mid (उप-विभाग),
sub (उप-उप-विभाग) — प्रत्येकाला वेगळा रंग (पॅलेटमधून सायकल करत) व मोठा फॉन्ट, जेणेकरून आधीच्या
एकाच फिकट राखाडी रंगाच्या/छोट्या headings मुळे येणारा crowded feel जावा.
"""
import streamlit as st

HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE = "#2962FF", "#00BFA5", "#AB47BC", "#FF6D00"
HDR_PINK, HDR_GREEN, HDR_AMBER, HDR_CYAN, HDR_RED = "#EC407A", "#66BB6A", "#FFC107", "#26C6DA", "#E64A19"

# क्रमाने वापरण्यासाठी — एका पानावर अनेक sub_header/mid_header लागोपाठ आले, तर प्रत्येकाला वेगळा
# रंग देण्यासाठी cycle_color(i) वापरता येतो (i = त्या पानावरचा त्या पातळीचा अनुक्रमांक).
_PALETTE = [HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE, HDR_PINK, HDR_GREEN, HDR_AMBER, HDR_CYAN, HDR_RED]


def cycle_color(i):
    return _PALETTE[i % len(_PALETTE)]


def mega_header(text, color):
    """पानावरचे मुख्य विभाग (आधीच्या st.subheader/st.header ऐवजी) — मोठा, ठळक, रंगीत, खालून जाड
    रंगीत रेषेसकट heading."""
    st.markdown(
        f'<div style="font-size:2.1rem; font-weight:800; color:{color}; '
        f'margin:2.4rem 0 1.1rem 0; padding-bottom:0.5rem; border-bottom:4px solid {color};">'
        f'{text}</div>',
        unsafe_allow_html=True,
    )


def mid_header(text, color):
    """मुख्य विभागाच्या आतले उप-विभाग (आधीच्या "### ..." ऐवजी) — मध्यम मोठा, रंगीत heading."""
    st.markdown(
        f'<div style="font-size:1.55rem; font-weight:750; color:{color}; '
        f'margin:1.8rem 0 0.9rem 0;">{text}</div>',
        unsafe_allow_html=True,
    )


def sub_header(text, color):
    """सर्वात आतले उप-उप-विभाग (आधीच्या "##### ..." ऐवजी) — रंगीत पण तुलनेने छोटा heading."""
    st.markdown(
        f'<div style="font-size:1.2rem; font-weight:700; color:{color}; '
        f'margin:1.3rem 0 0.5rem 0;">{text}</div>',
        unsafe_allow_html=True,
    )
