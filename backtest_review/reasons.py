"""backtest_review/reasons.py — chart_reader.evaluate च्या निकालावरून candidate चे reason codes (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §2b).

प्रत्येक candidate ला किमान एक code (रिकामा कधीच नाही): entry ⇒ ENTRY_A / ENTRY_B; नाहीतर नकाराची कारणं (क्रमाने), काहीच जुळलं नाही ⇒ OTHER.
"""
CODES = {
    "ENTRY_A": "entry (grade A)",
    "ENTRY_B": "entry (grade B)",
    "GRADE_C": "grade C (गुण कमी)",
    "NO_IMPULSE": "trade-degree impulse नाही",
    "SIDE_UNCLEAR": "F4: trend / structure / Elliott विरोध",
    "NO_AREA": "active area नाही",
    "NO_PULLBACK_END": "pullback end (C / E) नाही",
    "NO_REVERSAL": "reversal candle नाही / अपुरी",
    "RR<3": "spot R:R < 1:3",
    "NO_INVALIDATION": "स्पष्ट invalidation नाही",
    "CHASE": "breakout / chase (चुकीची बाजू)",
    "OPENING_WINDOW": "09:15–09:30 opening window",
    "BAR_OPEN": "बंद candle नाही",
    "RISK_LIMIT": "risk मर्यादा",
    "VETO_A_END": "A3 व्हेटो: A-end / B च्या आत",
    "VETO_ORIGIN": "A3 व्हेटो: impulse origin पलीकडे acceptance",
    "VETO_MAGNET": "A3 व्हेटो: MAGNET level",
    "VETO_GAP_B": "A3 व्हेटो: gap B, pullback नाही",
    "OTHER": "इतर",
}
_PATTERNS = (                       # (substring in why line, code) — chart_reader मधल्या मजकुरानुसार
    ("impulse / बाजू नाही", "NO_IMPULSE"),
    ("active area नाही", "NO_AREA"),
    ("pullback end नाही", "NO_PULLBACK_END"),
    ("reversal:", "NO_REVERSAL"),
    ("R:R", "RR<3"),
    ("invalidation नाही", "NO_INVALIDATION"),
    ("breakout / chase", "CHASE"),
    ("opening window", "OPENING_WINDOW"),
    ("बंद candle नाही", "BAR_OPEN"),
    ("risk मर्यादा", "RISK_LIMIT"),
    ("A-end / B च्या आत", "VETO_A_END"),
    ("impulse origin पलीकडे acceptance", "VETO_ORIGIN"),
    ("MAGNET", "VETO_MAGNET"),
    ("gap setup B", "VETO_GAP_B"),
    ("grade C", "GRADE_C"),
)


def codes(r):
    """chart_reader.evaluate निकाल ⇒ reason codes (क्रम टिकवून, duplicates नाहीत). कधीच रिकामी यादी नाही."""
    if r.get("entry"):
        return ["ENTRY_A" if r.get("grade") == "A" else "ENTRY_B"]
    out = []
    if r.get("side_unclear"):
        out.append("SIDE_UNCLEAR")
    for line in r.get("why_no_entry") or []:
        for pat, code in _PATTERNS:
            if pat in str(line) and code not in out:
                out.append(code)
                break
        else:
            if "OTHER" not in out:
                out.append("OTHER")
    return out or ["OTHER"]


def status(r):
    """✅ entry / 🟡 grade C (बाकी नियम ठीक) / ✖ नाकारलेला."""
    if r.get("entry"):
        return "ENTRY"
    cs = codes(r)
    return "C" if cs == ["GRADE_C"] else "REJECTED"
