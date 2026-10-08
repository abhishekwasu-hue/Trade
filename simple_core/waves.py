"""simple_core/waves.py — Motive wave context (KB भाग H: G1 / G8 / G9). Entry ठरवत नाही — Simple Core चे 4 टप्पे तसेच; हे फक्त
setup label, wave 1 चं टोक (flip area) आणि reference levels (projections) देतं.

Trade-degree swings (market_state, 15M ATR × 3) + चालू pullback, "x-space" मध्ये (trend दिशा = वर; bear ⇒ किंमत उलटी):
  origin O    = lookback मधला सगळ्यात खालचा start-kind pivot (त्यानंतरचं सगळं त्याच्या वर). Pullback O च्या खाली ⇒ count gray.
  W2          = O नंतरचा पहिला start-kind pivot जो O च्या वर, नंतरचे सगळे pullbacks त्याच्या वर (R1: (ii) of 3 सुद्धा W2 खाली नाही),
                आणि त्याआधीचं टोक W1 (O→W2 मधला सगळ्यात वरचा end pivot) नंतर पार झालं.
  W2 नाही     ⇒ चालू pullback = wave 2 ⇒ G1 (W1 = O नंतरचं टोक X).
  W2 आहे     ⇒ wave 3 चं टोक X3; त्याआधी पूर्ण झालेली wave 4 (W1 overlap नाही, खोल, wave 3 ≥ wave 1) आणि नवा high ⇒ wave 5 नंतर ⇒ gray.
                चालू pullback: W1 च्या भागात (R3) ⇒ gray; उथळ (≤ g8_retrace_max + tol) आणि जलद (≤ g8_max_bars) ⇒ G8;
                नाहीतर wave 3 ≥ wave 1 ⇒ G9 (wave 4 end); नाहीतर gray.
Reference levels (KB भाग H; [अनुभव / guideline], K7 — फक्त माहिती, target / SL dashboard ठरवतं):
  wave3_projection = wave 2 end + w3_proj × wave 1 (पर्याय w3_proj_alts) · wave5_projection = wave 4 end + w5_proj_w1 × wave 1
  (पर्याय: + w5_proj_w13 × (wave 1 start → wave 3 end)) · wave1_origin · wave1_extreme · subwave_origin (G8: (i) of 3 ची सुरुवात = W2).
Gray / लागू नसलेली level ⇒ None आणि notes[key] = "लागू नाही — कारण".
"""
import numpy as np
import pandas as pd

REF_KEYS = ("wave3_projection", "wave5_projection", "wave1_origin", "wave1_extreme", "subwave_origin")


def _xs(df, side):
    """x-space: trend दिशा वर. up = trend दिशेचं टोक (bull high / bear −low), dn = counter टोक."""
    h, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    return (h, lo) if side > 0 else (-lo, -h)


def pivots_on(df, pivots):
    """pivots (dict: idx किंवा ts, price, kind H/L) ⇒ df च्या index वर, k पर्यंतचे, वेळेनुसार."""
    out = []
    ts = pd.to_datetime(df["timestamp"]).to_numpy() if "timestamp" in df else None
    for p in pivots or []:
        if p.get("idx") is not None and p.get("ts") is None:
            i = int(p["idx"])
        elif ts is not None and p.get("ts") is not None:
            t = np.datetime64(pd.Timestamp(p["ts"]))
            i = int(np.searchsorted(ts, t))
            if i >= len(ts) or ts[i] != t:
                continue                                                   # frame च्या बाहेरचा pivot
        else:
            continue
        if 0 <= i < len(df):
            out.append({"i": i, "price": float(p["price"]), "kind": p["kind"]})
    return sorted(out, key=lambda q: q["i"])


def _structure(df, pivots, side, k, s):
    """bar k पर्यंतची रचना (x-space) ⇒ dict(O, W1, W2, X3, P, …) किंवा {"gray": कारण}."""
    up, dn = _xs(df, side)
    endk, startk = ("H", "L") if side > 0 else ("L", "H")
    x = lambda q: q["price"] * side                                        # noqa: E731
    pv = [q for q in pivots_on(df, pivots) if q["i"] < k][-int(s["wave_lookback_pivots"]):]
    if not pv:
        return {"gray": "swings अपुरे"}
    if pv[-1]["kind"] == endk:                                             # शेवटचं टोक: शेवटच्या end pivot पासून k पर्यंतचा max
        base, a = pv[:-1], pv[-1]["i"]
    else:
        base, a = pv, pv[-1]["i"] + 1
    if a > k:
        return {"gray": "swings अपुरे"}
    xi = a + int(np.argmax(up[a:k + 1]))
    if xi >= k:
        return {"gray": "pullback नाही (चालू bar च टोक)"}
    X = {"i": xi, "x": float(up[xi])}
    P = {"i": xi + 1 + int(np.argmin(dn[xi + 1:k + 1])), "x": float(dn[xi + 1:k + 1].min())}
    seq = [{"i": q["i"], "x": x(q), "kind": "s" if q["kind"] == startk else "e"} for q in base] + [{**X, "kind": "e"}]
    starts = [q for q in seq if q["kind"] == "s"]
    if not starts:
        return {"gray": "origin (wave 1 ची सुरुवात) दिसत नाही"}
    O = min(starts, key=lambda q: q["x"])
    after = [q for q in seq if q["i"] > O["i"]]
    if not after or any(q["x"] <= O["x"] for q in after):
        return {"gray": "origin नंतर रचना नाही"}
    if P["x"] <= O["x"]:
        return {"gray": "pullback wave 1 च्या origin खाली (R1) — count gray"}
    out = {"O": O, "X": X, "P": P, "bars": int(k - xi)}
    inner = [q for q in after if q["kind"] == "s"]
    w2 = None
    for j, q in enumerate(inner):
        later = [r["x"] for r in inner[j + 1:]] + [P["x"]]
        e_before = [r["x"] for r in after if r["kind"] == "e" and r["i"] < q["i"]]
        e_after = [r["x"] for r in after if r["kind"] == "e" and r["i"] > q["i"]]
        if e_before and e_after and all(v > q["x"] for v in later) and max(e_after) > max(e_before):
            w2 = q
            w1 = max((r for r in after if r["kind"] == "e" and r["i"] < q["i"]), key=lambda r: r["x"])
            break
    if w2 is None:
        top = max((r for r in after if r["kind"] == "e"), key=lambda r: r["x"])
        if top["i"] != X["i"]:
            return {"gray": "wave 1 नंतर नवं टोक नाही — correction चालू"}
        out.update(phase=2, W1=X)
        return out
    ends3 = [r for r in after if r["kind"] == "e" and r["i"] > w2["i"]]
    x3 = max(ends3, key=lambda r: r["x"])
    leg1, leg3 = w1["x"] - O["x"], x3["x"] - w2["x"]
    for q in [r for r in after if r["kind"] == "s" and w2["i"] < r["i"] < x3["i"]]:
        e_j = max((r for r in ends3 if r["i"] < q["i"]), key=lambda r: r["x"], default=None)
        if e_j is None:
            continue
        lg = e_j["x"] - w2["x"]
        deep = lg > 0 and (e_j["x"] - q["x"]) / lg > s["g8_retrace_max"] + s["g8_retrace_tol"]
        if q["x"] > w1["x"] and deep and lg >= leg1:
            return {"gray": "wave 4 आधीच पूर्ण, नवं टोक = wave 5 — motive पूर्ण असू शकते"}
    p4 = min([r["x"] for r in after if r["kind"] == "s" and r["i"] > x3["i"]] + [P["x"]])
    out.update(phase=3, W1=w1, W2=w2, X3=x3, P4=p4, leg1=leg1, leg3=leg3, bars=int(k - x3["i"]))
    return out


def count(df, pivots, side, k=None, s=None):
    """bar k (default शेवटचा) वर motive wave context. रिटर्न {setup: G1/G8/G9/None, gray: कारण|None, ref: {REF_KEYS}, notes, story}."""
    from . import settings as SS
    s = SS.engine_settings(s)
    k = len(df) - 1 if k is None else int(k)
    out = {"setup": None, "gray": None, "ref": {key: None for key in REF_KEYS}, "notes": {}, "story": ""}
    st = _structure(df, pivots, side, k, s) if side else {"gray": "trend बाजू नाही"}
    px = lambda v: round(float(v) * side, 2)                               # noqa: E731
    if st.get("gray"):
        out["gray"] = st["gray"]
        out["notes"] = {key: f"लागू नाही — {st['gray']}" for key in REF_KEYS}
        out["story"] = f"wave count gray: {st['gray']}"
        return out
    O = st["O"]["x"]
    if st["phase"] == 2:                                                   # चालू pullback = wave 2 ⇒ G1
        w1, w2 = st["W1"]["x"], st["P"]["x"]
        leg1 = w1 - O
        out["setup"] = "G1"
        out["ref"].update(wave3_projection=px(w2 + s["w3_proj"] * leg1), wave1_origin=px(O), wave1_extreme=px(w1))
        out["alts"] = {"wave3_projection": {str(m): px(w2 + m * leg1) for m in s["w3_proj_alts"]}}
        out["notes"] = {"wave5_projection": "लागू नाही — wave 4 अजून नाही (G1 = wave 2 end)",
                        "subwave_origin": "लागू नाही — G1 मध्ये sub-wave (i) of 3 नाही"}
        out["story"] = f"G1: wave 2 end ⇒ wave 3 · wave 1 {px(O):,.1f} → {px(w1):,.1f}"
        return out
    w1, w2, x3, p4, leg1, leg3 = st["W1"]["x"], st["W2"]["x"], st["X3"]["x"], st["P4"], st["leg1"], st["leg3"]
    r = (x3 - p4) / leg3 if leg3 > 0 else 1.0
    base = dict(wave1_origin=px(O), wave1_extreme=px(w1))
    if p4 <= w1:
        g = "pullback wave 1 च्या भागात (R3 overlap) — wave 4 नाही, count gray"
        out.update(gray=g, notes={key: f"लागू नाही — {g}" for key in REF_KEYS}, story=f"wave count gray: {g}")
        return out
    if r <= s["g8_retrace_max"] + s["g8_retrace_tol"] and st["bars"] <= int(s["g8_max_bars"]):
        out["setup"] = "G8"
        out["ref"].update(base, wave3_projection=px(w2 + s["w3_proj"] * leg1), subwave_origin=px(w2))
        out["alts"] = {"wave3_projection": {str(m): px(w2 + m * leg1) for m in s["w3_proj_alts"]}}
        out["notes"] = {"wave5_projection": "लागू नाही — wave 3 चालू (G8), wave 4 अजून नाही"}
        out["story"] = f"G8: wave 3 मधला उथळ pullback ({r:.0%}, {st['bars']} bars) · wave 2 end {px(w2):,.1f}"
        return out
    if leg3 >= leg1:
        out["setup"] = "G9"
        out["ref"].update(base, wave5_projection=px(p4 + s["w5_proj_w1"] * leg1))
        out["alts"] = {"wave5_projection": {"w13": px(p4 + s["w5_proj_w13"] * (x3 - O))}}
        out["notes"] = {"wave3_projection": "लागू नाही — wave 3 पूर्ण (G9 = wave 4 end)",
                        "subwave_origin": "लागू नाही — G9 मध्ये sub-wave (i) of 3 नाही"}
        out["story"] = f"G9: wave 4 end ⇒ wave 5 (retrace {r:.0%}) · wave 3 टोक {px(x3):,.1f} · Tier C"
        return out
    g = "wave 3 wave 1 पेक्षा लहान आणि pullback उथळ / जलद नाही — wave 4 म्हणता येत नाही"
    out.update(gray=g, notes={key: f"लागू नाही — {g}" for key in REF_KEYS}, story=f"wave count gray: {g}")
    return out


def wave1_zone(df, pivots, side, mr, s=None):
    """Wave 3 ने wave 1 चं टोक पार केलं ⇒ ते टोक flip area (G8 / G9 साठी). जन्म = पार केलेला पहिला bar. नाहीतर None."""
    from . import settings as SS
    s = SS.engine_settings(s)
    k = len(df) - 1
    st = _structure(df, pivots, side, k, s) if side else {"gray": "x"}
    if st.get("gray") or st.get("phase") != 3 or not mr:
        return None
    up, _ = _xs(df, side)
    w1 = st["W1"]
    beyond = np.nonzero(up[w1["i"] + 1:k + 1] > w1["x"])[0]
    if not len(beyond):
        return None
    px, half = w1["x"] * side, float(s["wave1_zone_mr"]) * float(mr)
    return {"id": f"W1-{int(w1['i'])}", "zid": "W1", "side": "buy" if side > 0 else "sell",
            "role": "SUPPORT" if side > 0 else "RESISTANCE", "tool": "w", "type": "wave1 flip", "kind": "solid",
            "low": round(px - half, 2), "high": round(px + half, 2), "state": "ACTIVE", "bar": int(w1["i"] + 1 + beyond[0])}
