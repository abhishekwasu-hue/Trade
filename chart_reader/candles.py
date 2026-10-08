"""chart_reader/candles.py — प्रत्येक candle ची psychology (candlestick अहवाल §2): body, close location, wick pressure, MR च्या पटीत आकार,
कोणाचं नियंत्रण, आणि एका ओळीचं मराठी वर्णन. Pattern नावं निर्णयात नाहीत."""


def read(o, h, l, c, mr):
    o, h, l, c = float(o), float(h), float(l), float(c)
    rng = h - l
    if rng <= 0:
        return {"body": 0.0, "cl": 0.5, "upper_wick": 0.0, "lower_wick": 0.0, "size_mr": 0.0, "control": "indecision",
                "line": "range 0 (data) — अनिर्णय"}
    body, cl = abs(c - o) / rng, (c - l) / rng
    uw, lw = (h - max(o, c)) / rng, (min(o, c) - l) / rng
    size = round(rng / mr, 2) if mr and mr > 0 else None
    if 0.40 <= cl <= 0.60:
        ctrl = "indecision"
    elif cl > 0.60:
        ctrl = "buyers"
    else:
        ctrl = "sellers"
    big = size is not None and size >= 1.2
    if ctrl == "indecision":
        line = "अनिर्णय — close मधोमध, कोणीच ताबा घेतला नाही"
    elif ctrl == "buyers":
        line = ("मोठी bullish body, close वर — buyers चं पूर्ण नियंत्रण" if body >= 0.6 else
                "लांब lower wick, close वर — खाली sellers नाकारले, buyers नी परत ओढलं" if lw >= 0.5 else "close वरच्या भागात — buyers पुढे")
    else:
        line = ("मोठी bearish body, close तळाशी — sellers चं पूर्ण नियंत्रण" if body >= 0.6 else
                "लांब upper wick, close खाली — वर buyers नाकारले, sellers नी परत ढकललं" if uw >= 0.5 else "close खालच्या भागात — sellers पुढे")
    if size is not None:
        line += f" · आकार {size}× MR" + (" (ताकदीची)" if big else " (लहान)")
    return {"body": round(body, 3), "cl": round(cl, 3), "upper_wick": round(uw, 3), "lower_wick": round(lw, 3), "size_mr": size,
            "control": ctrl, "line": line}
