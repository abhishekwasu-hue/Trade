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


import math


def find_pivots_indexed(df, prd=10):
    """find_pivots() सारखंच, पण प्रत्येक pivot सोबत त्याचा bar-index (pivot bar चा, पुष्टीचा नव्हे) —
    रिटर्न: कालानुक्रमे [(bar_index, value), ...]. Pine मध्ये pivot ची पुष्टी prd bars नंतर (bar_index +
    prd ला) होते — तोच "event bar" आहे, ज्यावर S/R levels पुन्हा मोजले जातात (compute_dynamic_sr बघा).

    🎓 वापरकर्त्याने दिलेल्या मूळ Pine Script शी थेट ताडून सापडवलेली, छोटी पण खरी विसंगती —
    Pine चं `array.unshift(pivotvals, ph ? ph : pl)` — म्हणजे एकाच bar वर pivot high आणि pivot low
    दोन्ही आले (शक्य आहे, prd सममित असल्याने), तर Pine **फक्त high** ठेवतो, low गाळतो (ternary,
    "else" कधीच दोन्ही नाही). आधी इथे दोन्ही स्वतंत्र if असल्याने दोन्ही जोडले जायचे — आता तोच
    ternary-सारखा प्राधान्यक्रम (high आधी तपासून, तोच नसेल तरच low).
    """
    highs, lows = df["high"].values, df["low"].values
    n = len(df)
    pivots = []
    for i in range(prd, n - prd):
        window_h = highs[i - prd:i + prd + 1]
        window_l = lows[i - prd:i + prd + 1]
        if highs[i] == window_h.max():
            pivots.append((i, highs[i]))
        elif lows[i] == window_l.min():
            pivots.append((i, lows[i]))
    return pivots


def find_pivots(df, prd=10):
    """
    Pine Script चा ta.pivothigh/pivotlow — bar i चा pivot high/low म्हणजे [i-prd, i+prd] या
    संपूर्ण window मध्ये तोच सर्वाधिक/सर्वात कमी. रिटर्न: कालानुक्रमे (जुने आधी) किमतींची यादी.
    (ternary `ph ? ph : pl` प्राधान्य — तपशील find_pivots_indexed() मध्ये.)
    """
    return [value for _, value in find_pivots_indexed(df, prd)]


def compute_dynamic_sr(df, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2, current_price=None, mintick=None):
    """
    मूळ Pine Script च्या तंतोतंत तर्कानुसार — Pivot clustering वरून dynamic S/R zones काढणे.
    current_price दिल्यास, प्रत्येक zone आपोआप त्याच्या वर/खाली आहे यानुसार resistance/support मध्ये
    विभागला जातो (Pine मध्ये जसं mid>=close तर लाल/resistance, नाहीतर हिरवा/support, तेच तत्त्व).
    रिटर्न: {"support": [{"level":x,"touches":n},...], "resistance": [...]}

    🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("TradingView ची एक्झॅक्ट पद्धत चार्ट, डॅशबोर्ड आणि
    डाटाबेसमधील लेव्हल्ससाठी" — TradingView वरचा SRv2 आणि आपला चार्ट/bot यांचे levels जुळत नव्हते) —
    मूळ Pine Script मध्ये S/R levels फक्त `if ph or pl` (नवीन pivot ची पुष्टी झालेल्या bar) वरच पुन्हा
    मोजले जातात (array.clear करून सगळे नव्याने), आणि त्या क्षणीचा `cwidth` (त्या bar पर्यंतचे
    शेवटचे 300 bars) वापरला जातो; पुढच्या pivot पर्यंत levels तसेच राहतात. आधी हे function मालिकेच्या
    शेवटच्या bar वर, शेवटच्या क्षणीचा cwidth वापरून मोजायचं, त्यामुळे चॅनेल-रुंदी वेगळी होऊन काही
    वेळा cluster चा mid बदलायचा. आता शेवटचा pivot-event bar (शेवटचा pivot bar + prd) शोधून, तोवरचे
    शेवटचे maxnumpp pivots आणि त्याच bar वरचा cwidth वापरला जातो — Pine मध्ये प्रत्येक event वर सगळं
    पुन्हा बनत असल्याने, फक्त शेवटच्या event ची गणनाच अंतिम निकालासाठी पुरेशी आणि तंतोतंत आहे.
    mintick दिला (उदा. NIFTY साठी 0.05) तर mid Pine च्या math.round_to_mintick() सारखा जवळच्या
    tick वर गोल केला जातो (फक्त दाखवण्याच्या जुळणीसाठी; नाही दिला तर आधीसारखे 2 दशांश).
    """
    n = len(df)
    if n < 2 * prd + 10:
        return {"support": [], "resistance": []}

    indexed_pivots = find_pivots_indexed(df, prd)
    if len(indexed_pivots) < min_strength:
        return {"support": [], "resistance": []}
    # Pine unshift करतो (नवीन array च्या पुढे), size>maxnumpp झाल्यास सर्वात जुनं (शेवटचं) काढतो
    # -> शेवटी सर्वात अलीकडचे maxnumpp pivots उरतात, नवीन->जुने क्रमाने
    pivotvals = [value for _, value in reversed(indexed_pivots)][:maxnumpp]
    last_pivot_bar = indexed_pivots[-1][0]
    event_bar = last_pivot_bar + prd  # ta.pivothigh/low ची पुष्टी prd bars नंतर -> `ph or pl` इथेच खरं
    window_300 = df.iloc[max(0, event_bar - 299):event_bar + 1]
    cwidth = (window_300["high"].max() - window_300["low"].min()) * channel_w_pct / 100

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
        mid_raw = (sr_up[i] + sr_dn[i]) / 2
        if mintick:
            mid = round(math.floor(mid_raw / mintick + 0.5) * mintick, 2)
        else:
            mid = round(mid_raw, 2)
        entry = {"level": mid, "touches": int(sr_strength[i])}
        if mid >= current_price:
            result["resistance"].append(entry)
        else:
            result["support"].append(entry)
    result["support"].sort(key=lambda x: -x["touches"])
    result["resistance"].sort(key=lambda x: -x["touches"])
    return result
