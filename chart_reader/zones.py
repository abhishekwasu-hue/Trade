"""chart_reader/zones.py — selling (supply) आणि buying (demand) zones, प्रत्येक chart वर, प्रत्येक दिवशी (KB K4, K5, K6, K8;
TRADE_KB_FULL_IMPLEMENTATION_PROMPT §2).

`areas.tools` ची ठोस साधनं (a–f, j–l) इथे zone बनतात. भूमिका **जन्मावरून**, किंमतीच्या वर / खाली यावरून नाही:
  selling: downward displacement च्या आधीचा base · तुटलेला support (flip) · उतरती trendline · equal highs / swing high (liquidity) ·
           PDH / आठवड्याचा high · range चा वरचा edge · किंमतीच्या वरचा round number
  buying:  उलट.
मग जन्मापासून आत्तापर्यंत `price_action/levels_v2.lifecycle` (real break = close buffer पलीकडे + पुढचा bar reclaim नाही) ⇒ state
ACTIVE / TESTED / BROKEN / FLIPPED / DEAD / MAGNET आणि चालू भूमिका (तुटलेला selling zone retest नंतर buying — K4 flip).
प्रत्येक zone: id (S1, S2 … / B1, B2 … किंमतीपासूनच्या अंतरानुसार), प्रकार, साधन, पट्टा (low/high, MR मध्ये रुंदी), TF / degree,
freshness (fresh / tested / worn), state, touches, reaction (touch नंतर zone पासून दूर गेलेली कमाल चाल, MR), label.
HTF साधनं (a / b / d) ची state levels_v2 ने त्यांच्या TF वर आधीच ठरवलेली — तीच ठेवतो. Trendline (f) ची state `areas._line_state`.
Ruler (g / h / i: channel, Fibonacci, C = A) zone नाहीत — फक्त confluence. सगळं दिलेल्या बंद bars वरच (no-lookahead).
"""
import numpy as np
import pandas as pd

from price_action import levels_v2 as LV

DEFAULTS = {
    "zone_break_buffer_mr": 0.25,      # real break: close zone च्या पलीकडे हे × MR (levels_v2 सारखं)
    "zone_chop_window": 20,            # MAGNET: शेवटच्या इतक्या closes मध्ये
    "zone_chop_max_crossings": 4,      # … mid च्या इतक्यापेक्षा जास्त वेळा आरपार ⇒ MAGNET
    "zone_reaction_bars": 8,           # reaction = touch नंतरच्या इतक्या bars मधली zone पासूनची कमाल चाल
    "zone_worn_tests": 3,              # ≥ इतके tests ⇒ worn
    "zone_lookback_bars": 400,         # birth नसलेल्या (round / PDC) zones चा lifecycle शेवटच्या इतक्या bars वर (~16 sessions)
}

TYPE = {"a": "horizontal", "b": "flip", "c": "base", "d": "range edge", "e": "liquidity", "f": "trendline", "j": "round", "l": "gap"}
SELL_IDS = ("PDH", "PWH")
BUY_IDS = ("PDL", "PWL")


def _s(s):
    return {**DEFAULTS, **(s or {})}


def birth_role(z, price):
    """जन्मावरून भूमिका: RESISTANCE (selling) / SUPPORT (buying)."""
    t, zid = z.get("tool"), str(z.get("id") or "")
    if t in ("a", "b", "d", "c", "f") and z.get("role") in ("SUPPORT", "RESISTANCE"):
        return z["role"]                                   # base: displacement दिशेने; trendline: R/S; HTF: levels_v2 ची
    if t == "e":
        return "RESISTANCE" if z.get("pool") in ("equal_highs", "swing_high") else "SUPPORT"
    if t == "k" and zid in SELL_IDS:
        return "RESISTANCE"
    if t == "k" and zid in BUY_IDS:
        return "SUPPORT"
    return "SUPPORT" if (float(z["low"]) + float(z["high"])) / 2.0 < price else "RESISTANCE"   # round / PDC / gap: किंमतीवरून


def _start_bar(z, df, s):
    """lifecycle कुठून: zone जन्माचा bar; नसेल तर PDH/PDL ⇒ आजची सुरुवात, आठवडा ⇒ या आठवड्याची सुरुवात, बाकी ⇒ शेवटचे lookback bars."""
    n = len(df)
    if z.get("bar") is not None:
        return int(z["bar"]) + 1
    d = pd.to_datetime(df["timestamp"])
    zid = str(z.get("id") or "")
    if zid in ("PDH", "PDL", "PDC") or z.get("tool") == "l":
        day = d.dt.normalize()
        return int(np.argmax((day == day.iloc[-1]).to_numpy()))
    if zid in ("PWH", "PWL"):
        wk = d.dt.to_period("W")
        return int(np.argmax((wk == wk.iloc[-1]).to_numpy()))
    return max(0, n - int(s["zone_lookback_bars"]))


def _first_away(df, lo, hi, start):
    """start पासून पहिला bar जो zone ला शिवत नाही — जन्माला चिकटलेले bars test नाहीत (किंमत दूर जाऊन परत यायला हवी)."""
    h, l = df["high"].to_numpy(float), df["low"].to_numpy(float)
    j = max(0, int(start))
    while j < len(h) and l[j] <= hi and h[j] >= lo:
        j += 1
    return j


def reaction(df, lo, hi, role, start, mr, s):
    """प्रत्येक touch (zone ला लागलेला bar, आधीचा bar बाहेर) नंतरच्या zone_reaction_bars मध्ये zone पासून दूरची कमाल चाल (MR). कमाल."""
    h, lo_ = df["high"].to_numpy(float), df["low"].to_numpy(float)
    n = len(h)
    best, prev_touch = 0.0, False
    m = int(s["zone_reaction_bars"])
    for j in range(max(0, start), n):
        touch = lo_[j] <= hi and h[j] >= lo
        if touch and not prev_touch and j + 1 < n:
            seg = slice(j + 1, min(n, j + 1 + m))
            away = (h[seg].max() - hi) if role == "SUPPORT" else (lo - lo_[seg].min())
            best = max(best, float(away) / mr if mr else 0.0)
        prev_touch = touch
    return round(best, 2)


def annotate(cands, df, s, mr, tf="15M"):
    """areas.tools candidates ⇒ zones (नवी यादी; ruler वगळून). df = trigger TF बंद bars (मोठा lookback)."""
    s = _s(s)
    if df is None or not len(df) or not mr:
        return []
    price = float(df["close"].iloc[-1])
    ls = {"break_buffer_mr": s["zone_break_buffer_mr"], "chop_window": s["zone_chop_window"], "chop_max_crossings": s["zone_chop_max_crossings"],
          "accept_closes": LV.DEFAULTS["accept_closes"]}                  # B2 time acceptance — levels_v2 / breaks शी एकच व्याख्या
    out = []
    for z in cands or []:
        if z.get("kind") != "solid":
            continue
        z = dict(z)
        born = birth_role(z, price)
        z["birth_role"] = born
        t = z.get("tool")
        start = _first_away(df, float(z["low"]), float(z["high"]), _start_bar(z, df, s)) if z.get("bar") is not None else _start_bar(z, df, s)
        if t in ("a", "b", "d"):                           # HTF levels_v2: त्यांच्या TF वर lifecycle आधीच
            z.setdefault("tf", z.get("tf") or "HTF")
            tests = int(z.get("tests") or 0)
        elif t == "f":
            z["tf"] = tf
            tests = max(0, int(z.get("touches") or 0) - 2)  # दोन anchors नंतरचे touches = tests
        else:
            lc = LV.lifecycle(df, (float(z["low"]), float(z["high"])), born, start, mr, ls)
            z.update(state=lc["state"], role=lc["role"], tf=tf)
            if lc.get("broken_at") is not None:
                z["role_since"] = int(lc["broken_at"])           # तुटल्यानंतरची भूमिका या bar पासून (Simple Core pause ह्याआधी नाही)
            tests = int(lc["tests"])
        z["tests"] = tests
        z["touches"] = int(z.get("touches") or tests)
        z["fresh"] = "fresh" if tests == 0 else ("worn" if tests >= int(s["zone_worn_tests"]) else "tested")
        z["band_mr"] = round((float(z["high"]) - float(z["low"])) / mr, 2)
        z["reaction_mr"] = None if t == "f" else reaction(df, float(z["low"]), float(z["high"]), z["role"], start, mr, s)   # तिरकी रेषा: आडवा पट्टा चुकीचा
        z["side"] = "sell" if z["role"] == "RESISTANCE" else "buy"
        name = TYPE.get(t)
        if t == "k":
            name = {"PDH": "PDH", "PDL": "PDL", "PDC": "PDC", "PWH": "week H", "PWL": "week L"}.get(str(z.get("id")), "level")
        if z.get("state") == "FLIPPED" or (born != z["role"] and t != "f"):
            name = f"flip ({name})" if name != "flip" else name
        z["type"] = name
        out.append(z)
    for side, pfx in (("sell", "S"), ("buy", "B")):
        zs = sorted([z for z in out if z["side"] == side], key=lambda z: abs((float(z["low"]) + float(z["high"])) / 2.0 - price))
        for k, z in enumerate(zs, 1):
            z["zid"] = f"{pfx}{k}"
            deg = f" D{z['degree']}" if z.get("degree") else ""
            z["label"] = f"{z['zid']} · {z['type']} · {z['tf']}{deg} · {z.get('state', 'ACTIVE')} · {z['touches']} touches"
    return out


def nearest(zones, side, price, n=3):
    """trade बाजूचे (bear ⇒ sell, bull ⇒ buy) जिवंत zones, किंमतीपासून जवळचे n."""
    want = "sell" if side < 0 else "buy"
    ok = [z for z in zones if z["side"] == want and z.get("state") not in ("BROKEN", "DEAD", "MAGNET")]
    return sorted(ok, key=lambda z: abs((float(z["low"]) + float(z["high"])) / 2.0 - price))[:n]
