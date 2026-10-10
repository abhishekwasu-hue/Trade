"""chart_reader/candles.py — प्रत्येक candle ची psychology (candlestick अहवाल §2): body, close location, wick pressure, MR च्या पटीत आकार,
कोणाचं नियंत्रण, आणि एका ओळीचं मराठी वर्णन. Pattern नावं निर्णयात नाहीत."""
import numpy as np



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


# ---------------------------------------------------------------------------------------------------------------------
# Candle-by-candle (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §5; KB K9, K10, K12) — गणनेसाठी data / log / narrative; chart वर फक्त zone
# वरच्या शेवटच्या 3–6 candles वर छोटे labels.
# ---------------------------------------------------------------------------------------------------------------------
DEFAULTS = {
    "cs_absorption_ratio": 3.0,    # effort (Σ range ÷ MR) ÷ result (|net| ÷ MR) ≥ हे ⇒ absorption (K12)
    "cs_absorption_min_mr": 1.2,   # absorption candle: range ≥ हे × MR पण body ≤ cs_absorption_body
    "cs_absorption_body": 0.3,
    "cs_wick_tag": 0.4,            # zone story: trade दिशेने rejection wick ≥ range च्या हे
    "cs_close_tag": 0.3,           # sellers close: CL ≤ हे (buyers: ≥ 1 − हे) आणि body ≥ 0.5
    "cs_zone_tol_mr": 0.3,         # zone ला "पोहोचला" = ± हे × MR
    "cs_story_min": 3,
    "cs_story_max": 6,
    "cs_tired_min": 3,             # leg मालिकेत इतक्या खुणा ⇒ "थकतोय"
}


def series(df, mr):
    """प्रत्येक बंद candle: CL, body %, wicks %, range ÷ MR, नियंत्रण, ओळ (data; chart वर नाही)."""
    out = []
    for r in df[["timestamp", "open", "high", "low", "close"]].itertuples(index=False):
        x = read(r.open, r.high, r.low, r.close, mr)
        x["ts"] = str(r.timestamp)
        out.append(x)
    return out


def _leg(df, a, b, direction, mr):
    o, h, lo, c = (df[x].to_numpy(float)[a:b + 1] for x in ("open", "high", "low", "close"))
    rng = np.maximum(h - lo, 1e-9)
    ov = [max(0.0, min(h[i], h[i - 1]) - max(lo[i], lo[i - 1])) / rng[i] for i in range(1, len(h))] or [0.0]
    counter = (h - np.maximum(o, c)) if direction > 0 else (np.minimum(o, c) - lo)       # leg दिशेविरुद्ध wick
    net = abs(c[-1] - o[0])
    return {"bars": int(b - a + 1), "size_mr": round(net / mr, 2), "spread_mr": round(float(rng.mean()) / mr, 2),
            "overlap": round(float(np.mean(ov)), 2), "counter_wick": round(float((counter / rng).mean()), 2),
            "effort_result": round(float(rng.sum()) / max(net, 1e-9), 2)}


def leg_read(df, legs, direction, mr, s=None, rvol=None):
    """legs = [(a, b)] त्याच दिशेचे legs (उदा. correction चे A आणि C). मालिका: legs लहान होत जाणं, spreads आकुंचन, overlap वाढ, विरुद्ध
    wicks वाढ, failed extension, absorption (effort वि. result), futures volume dry-up (rvol दिलं तर). ⇒ "थकतोय" निष्कर्ष."""
    s = {**DEFAULTS, **(s or {})}
    st = [_leg(df, a, b, direction, mr) for a, b in legs if b > a]
    out = {"legs": st, "signs": {}, "tired": False, "line": "leg मालिका: legs अपुरे"}
    if len(st) < 2:
        return out
    f, l = st[0], st[-1]
    signs = {"legs_shrinking": l["size_mr"] < f["size_mr"],
             "spreads_contracting": l["spread_mr"] < f["spread_mr"],
             "more_overlap": l["overlap"] > f["overlap"],
             "counter_wicks": l["counter_wick"] > f["counter_wick"],
             "failed_extension": l["size_mr"] < 0.382 * f["size_mr"],
             "absorption": l["effort_result"] >= s["cs_absorption_ratio"]}
    if rvol is not None:
        try:
            v = np.asarray(rvol, float)
            fa, fb = legs[0]
            la, lb = legs[-1]
            signs["volume_dryup"] = bool(np.nanmean(v[la:lb + 1]) < np.nanmean(v[fa:fb + 1]))
        except Exception:                                                    # noqa: BLE001 — volume नसेल तर ती खूण नाही
            pass
    out["signs"] = signs
    k = sum(bool(x) for x in signs.values())
    out["tired"] = k >= int(s["cs_tired_min"])
    names = {"legs_shrinking": "legs लहान", "spreads_contracting": "spreads आकुंचन", "more_overlap": "overlap वाढ",
             "counter_wicks": "विरुद्ध wicks", "failed_extension": "failed extension", "absorption": "absorption",
             "volume_dryup": "volume dry-up"}
    hit = [names[x] for x, v in signs.items() if v]
    out["line"] = (f"leg मालिका ({len(st)} legs): " + (", ".join(hit) or "थकव्याची खूण नाही")
                   + (" ⇒ चाल थकतोय" if out["tired"] else ""))
    return out


def tag(o, h, l, c, side, zone, mr, s=None):
    """एका candle चं छोटं label (zone वर पोहोचल्यानंतर). side = trade बाजू (bear −1: selling zone वर)."""
    s = {**DEFAULTS, **(s or {})}
    x = read(o, h, l, c, mr)
    rng = max(h - l, 1e-9)
    if zone is not None:
        lo_, hi_ = float(zone["low"]), float(zone["high"])
        if (side < 0 and h > hi_ and c < hi_) or (side > 0 and l < lo_ and c > lo_):
            return "sweep"
    wick = x["upper_wick"] if side < 0 else x["lower_wick"]
    if wick >= s["cs_wick_tag"] and x["body"] < 0.5:
        return "wick rejection"
    if (x["size_mr"] or 0) >= s["cs_absorption_min_mr"] and x["body"] <= s["cs_absorption_body"]:
        return "absorption"                                                # मोठी effort (range), result (body) नाही
    if side < 0 and x["cl"] <= s["cs_close_tag"] and x["body"] >= 0.5:
        return "sellers close"
    if side > 0 and x["cl"] >= 1 - s["cs_close_tag"] and x["body"] >= 0.5:
        return "buyers close"
    if wick >= s["cs_wick_tag"]:
        return "wick rejection"
    if (side < 0 and c > o) or (side > 0 and c < o):
        return "buyers push" if side < 0 else "sellers push"
    return "indecision" if rng / mr < 0.7 else "small"


def zone_story(df, zone, side, mr, s=None):
    """zone वर पोहोचल्यानंतरच्या शेवटच्या 3–6 बंद candles ची गोष्ट + प्रत्येकाचं label (chart वर फक्त हेच)."""
    s = {**DEFAULTS, **(s or {})}
    if zone is None or not len(df) or not mr:
        return {"bars": [], "line": "zone नाही ⇒ गोष्ट नाही"}
    tol = s["cs_zone_tol_mr"] * mr
    lo_, hi_ = float(zone["low"]) - tol, float(zone["high"]) + tol
    tail = df.tail(int(s["cs_story_max"]))
    h, l = tail["high"].to_numpy(float), tail["low"].to_numpy(float)
    hit = [i for i in range(len(tail)) if l[i] <= hi_ and h[i] >= lo_]
    k0 = hit[0] if hit else len(tail) - 1
    k0 = min(k0, len(tail) - int(s["cs_story_min"])) if len(tail) >= int(s["cs_story_min"]) else 0
    seg = tail.iloc[max(0, k0):]
    bars = []
    slope = float(zone.get("slope") or 0.0)                                   # trendline: त्या bar वरच्या रेषेचं मूल्य (शेवटच्या bar पासून मागे)
    for back, r in zip(range(len(seg) - 1, -1, -1), seg.itertuples(index=False)):
        zk = {**zone, "low": float(zone["low"]) - slope * back, "high": float(zone["high"]) - slope * back} if slope else zone
        bars.append({"ts": str(r.timestamp), "tag": tag(r.open, r.high, r.low, r.close, side, zk, mr, s)})
    tags = [b["tag"] for b in bars]
    rej = sum(t in ("wick rejection", "sweep", "absorption") for t in tags)
    last = tags[-1] if tags else ""
    who = "sellers" if side < 0 else "buyers"
    close_tag = "sellers close" if side < 0 else "buyers close"
    if last == close_tag and rej:
        concl = f"{who} परत (rejection नंतर ताकदीचा close)"
    elif last == close_tag:
        concl = f"{who} चा close, पण आधी rejection नाही"
    elif rej:
        concl = "rejection दिसतोय, पुष्टीचा close अजून नाही"
    else:
        concl = "zone मध्ये प्रतिक्रिया नाही"
    out_line = f"zone {zone.get('zid') or zone.get('id')} वर {len(bars)} candles: " + ", ".join(tags) + f" ⇒ {concl}"
    return {"bars": bars, "tags": tags, "line": out_line, "conclusion": concl, "confirmed": bool(last == close_tag and rej)}
