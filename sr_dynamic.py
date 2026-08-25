"""
sr_dynamic.py
-----------------
TradingView Pine Script "Support Resistance - Dynamic v2" (© LonesomeTheBlue, MPL-2.0) चं तंतोतंत
Python रूपांतर — Pivot High/Low शोधून, जवळपासचे pivots एका zone मध्ये एकत्र (cluster) करून, त्या
zone मधल्या pivots च्या संख्येला (strength) 'touches' म्हणून वापरणे — जितके जास्त, तितकी जास्त
high-probability पातळी.

रिटर्न फॉरमॅट tradingview_chart.py च्या build_lightweight_chart_html() ला हवा तोच
({"support":[{"level":x,"touches":n},...], "resistance":[...]}) — त्यामुळे कुठलाही बदल न करता
थेट वापरता येतो.
"""


def find_pivots(df, prd=10):
    """
    Pine Script चा ta.pivothigh/pivotlow — bar i चा pivot high/low म्हणजे [i-prd, i+prd] या
    संपूर्ण window मध्ये तोच सर्वाधिक/सर्वात कमी. रिटर्न: कालानुक्रमे (जुने आधी) किमतींची यादी.
    """
    highs, lows = df["high"].values, df["low"].values
    n = len(df)
    pivots = []
    for i in range(prd, n - prd):
        window_h = highs[i - prd:i + prd + 1]
        window_l = lows[i - prd:i + prd + 1]
        if highs[i] == window_h.max():
            pivots.append(highs[i])
        if lows[i] == window_l.min():
            pivots.append(lows[i])
    return pivots


def compute_dynamic_sr(df, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2, current_price=None):
    """
    मूळ Pine Script च्या तंतोतंत तर्कानुसार — Pivot clustering वरून dynamic S/R zones काढणे.
    current_price दिल्यास, प्रत्येक zone आपोआप त्याच्या वर/खाली आहे यानुसार resistance/support मध्ये
    विभागला जातो (Pine मध्ये जसं mid>=close तर लाल/resistance, नाहीतर हिरवा/support, तेच तत्त्व).
    रिटर्न: {"support": [{"level":x,"touches":n},...], "resistance": [...]}
    """
    n = len(df)
    if n < 2 * prd + 10:
        return {"support": [], "resistance": []}

    all_pivots_chrono = find_pivots(df, prd)
    # Pine unshift करतो (नवीन array च्या पुढे), size>maxnumpp झाल्यास सर्वात जुनं (शेवटचं) काढतो
    # -> शेवटी सर्वात अलीकडचे maxnumpp pivots उरतात, नवीन->जुने क्रमाने
    pivotvals = list(reversed(all_pivots_chrono))[:maxnumpp]
    if len(pivotvals) < min_strength:
        return {"support": [], "resistance": []}

    recent_300 = df.tail(300)
    cwidth = (recent_300["high"].max() - recent_300["low"].min()) * channel_w_pct / 100

    def get_sr_vals(ind):
        lo = pivotvals[ind]
        hi = lo
        numpp = 0
        for cpp in pivotvals:
            wdth = (hi - cpp) if cpp <= lo else (cpp - lo)
            if wdth <= cwidth:
                if cpp <= hi:
                    lo = min(lo, cpp)
                else:
                    hi = max(hi, cpp)
                numpp += 1
        return hi, lo, numpp

    sr_up, sr_dn, sr_strength = [], [], []

    def find_loc(strength):
        ret = len(sr_strength)
        for i in range(len(sr_strength) - 1, -1, -1):
            if strength <= sr_strength[i]:
                break
            ret = i
        return ret

    def check_sr(hi, lo, strength):
        for i in range(len(sr_up)):
            if (lo <= sr_up[i] <= hi) or (lo <= sr_dn[i] <= hi):
                if strength >= sr_strength[i]:
                    sr_strength.pop(i); sr_up.pop(i); sr_dn.pop(i)
                    return True
                else:
                    return False
        return True

    for ind in range(len(pivotvals)):
        hi, lo, strength = get_sr_vals(ind)
        if check_sr(hi, lo, strength):
            loc = find_loc(strength)
            if loc < maxnumsr and strength >= min_strength:
                sr_strength.insert(loc, strength)
                sr_up.insert(loc, hi)
                sr_dn.insert(loc, lo)
                if len(sr_strength) > maxnumsr:
                    sr_strength.pop(); sr_up.pop(); sr_dn.pop()

    if current_price is None:
        current_price = float(df["close"].iloc[-1])

    result = {"support": [], "resistance": []}
    for i in range(len(sr_up)):
        mid = round((sr_up[i] + sr_dn[i]) / 2, 2)
        entry = {"level": mid, "touches": int(sr_strength[i])}
        if mid >= current_price:
            result["resistance"].append(entry)
        else:
            result["support"].append(entry)
    result["support"].sort(key=lambda x: -x["touches"])
    result["resistance"].sort(key=lambda x: -x["touches"])
    return result
