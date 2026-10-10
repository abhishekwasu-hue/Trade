"""review7/method.py — Abhi पद्धत: (B1) मागे कुठे trade शक्य होता, (B2) पुढच्या दिवशी कुठे शक्य.

B1: प्रत्येक बंद 15M bar ला फक्त त्या bar पर्यंत known थर-outputs (C.st / C.trk / C.f1 / C.Z.snap / C.L4 / C.L5 / C.L6, सगळे known_at ≤ t)
वरून checklist: ① trend (सर्वोच्च ओळखलेला degree + दिशा) ② trade-बाजूच्या area ला स्पर्श (zone / trade-योग्य तिरकी रेघ; `self` खूण)
③ pullback = थर 2 K (I दिशा = trend) ④ correction संपतेय (candle shrink / momentum "कमकुवत होतोय" / RSI divergence) ⑤ K आधार-रेघ
break ⑥ commitment candle G1–G8 (decision2.engine.commitment — फक्त वाचन).
एका चाचणीला (एकाच area ची सलग ①②③ खिडकी) एकच बाण: ①②③④⑥ पूर्ण झाले की ✅ (त्या bar ला), न होता चाचणी संपली तर 🟡 (चाचणीच्या पहिल्या
bar ला). प्रत्येक बाणाला `known_at` (तो ठरला तो bar) — causal: शेवटचे bars कापले तरी `final` बाण बदलत नाहीत. नफा / तोटा / win-rate नाही.
B2: शेवटच्या बंद bar पर्यंतच्या माहितीवरून अटींची योजना (भविष्यवाणी नाही).
"""
import numpy as np
import pandas as pd

from decision2 import engine as DE
from legs2 import ik2 as IK

from . import settings as RS

SIDE = {1: "bull put", -1: "bear call"}
RSI_END = ("K संपतोय", "K thinning")                     # ④: correction संपतेय असे RSI labels फक्त (trap / trend मजबूत / range-fade नाही)


def _sig(C, t):
    return float(C.res["sigma"].get(pd.Timestamp(C.day[t]), np.nan))


def trend(C, t):
    """① सर्वोच्च ओळखलेला degree (unknown नसलेला): D3 (d3_trend) → D2 → D1. रिटर्न (degree, trend, दिशा ±1 / 0)."""
    for d in (3, 2, 1):
        tr = DE.d3_trend(C, t) if d == 3 else C.st[d]["states"][t]["trend"]
        if tr in ("UP", "DOWN", "RANGE"):
            return d, tr, (1 if tr == "UP" else (-1 if tr == "DOWN" else 0))
    return None, "unknown", 0


def areas(C, t, d, s, I=None):
    """t ला known trade-बाजूचे areas: zones (role, जिवंत; `self` = K च्या आत जन्मलेला) + trade-योग्य तिरक्या रेघा (value ± tol σ)."""
    role = "seller" if d < 0 else "buyer"
    out = []
    ie = None if I is None else I["end"].bar
    for z in ((getattr(C, "Z", None) and C.Z.snap.get(t)) or []):
        if z["role"] != role or z["status"] == "dead":
            continue
        out.append({"kind": "zone", "id": z["id"], "bot": float(z["bottom"]), "top": float(z["top"]), "stars": int(z.get("stars") or 1),
                    "self": bool(ie is not None and z.get("pivot_bar") is not None and z["pivot_bar"] > ie)})
    sg = _sig(C, t)
    tol = float(s["line_tol_sigma"]) * sg if np.isfinite(sg) else 0.0
    for y in ((C.L5.get(t) or {}).get("lines") or []):
        v = y.get("value_now")
        if y.get("class") == "trade-योग्य" and v is not None and np.isfinite(v):
            out.append({"kind": "line", "id": y.get("id") or y.get("name"), "bot": float(v) - tol, "top": float(v) + tol, "stars": 0,
                        "self": False})
    return out


def _touched(C, t, a, w):
    A = C.A
    return any(A["h"][j] >= a["bot"] and A["l"][j] <= a["top"] for j in range(max(t - w + 1, 0), t + 1))


def _pick(C, t, cands):
    """एकापेक्षा जास्त area ला स्पर्श ⇒ एकच: self नसलेला zone (★ जास्त) > रेघ > self zone; मग close ला जवळचा."""
    c = float(C.A["c"][t])
    rank = lambda a: (0 if (a["kind"] == "zone" and not a["self"]) else (1 if a["kind"] == "line" else 2), -a["stars"],  # noqa: E731
                      min(abs(c - a["bot"]), abs(c - a["top"])))
    return sorted(cands, key=rank)[0] if cands else None


def _shrink(C, t, s):
    A = C.A
    n, p = int(s["shrink_n"]), int(s["shrink_prior"])
    if t - n - p + 1 < 0:
        return False
    r = A["h"] - A["l"]
    last, prior = float(np.mean(r[t - n + 1:t + 1])), float(np.mean(r[t - n - p + 1:t - n + 1]))
    return bool(prior > 0 and last <= float(s["shrink_ratio"]) * prior)


def checklist(C, t, s=None):
    """एका बंद bar ची checklist (फक्त ≤ t माहिती). रिटर्न dict."""
    s = s or RS.load()
    deg, tr, d = trend(C, t)
    out = {"t": t, "c1": d != 0, "deg": deg, "trend": tr, "dir": d, "c2": False, "area": None, "c3": False, "c4": [], "c5": False,
           "c6": False, "pattern": None}
    if d == 0:
        return out
    st = C.trk[1].state(t)
    I = C.trk[1].I_at(t)
    cands = [a for a in areas(C, t, d, s, I) if _touched(C, t, a, int(s["touch_window"]))]
    a = _pick(C, t, cands)
    out["c2"], out["area"] = a is not None, a
    out["c3"] = bool(I is not None and I["dir"] == d and st.get("state") in (IK.ST_K, IK.ST_KSTART))
    rec = C.f1.out.get(t) or {}
    pref = rec.get("pref")
    out["pattern"] = None if not pref else f"{pref.get('family')}/{pref.get('state')}"
    l4, l5, l6 = C.L4.get(t) or {}, C.L5.get(t) or {}, C.L6.get(t) or {}
    m = l4.get("momentum") or rec.get("momentum") or {}
    if _shrink(C, t, s):
        out["c4"].append("shrink")
    if m.get("verdict") == "कमकुवत होतोय":
        out["c4"].append("momentum")
    if l6.get("label") in RSI_END or l6.get("on_K") or l6.get("regular_in_K"):
        out["c4"].append("RSI")
    kb = l5.get("k_base") or {}
    out["c5"] = bool(kb.get("bar") is not None and t - int(s["touch_window"]) < kb["bar"] <= t)
    if a is not None:
        cm = DE.commitment(C, t, d, {"band": (a["bot"], a["top"])})
        out["c6"] = bool(cm and cm["pass"])
        out["cm"] = cm
    out["K_extreme"] = (st.get("K") or {}).get("extreme")
    out["I_end"] = None if I is None else float(I["end"].price)
    return out


def _levels(C, t, ck, s):
    """✅: entry = commitment close; SL = area / K टोक / candle पलीकडे + buffer; target = पुढचा उलट zone (जिवंत) नाहीतर I_end; R:R."""
    d, a, cm = ck["dir"], ck["area"], ck.get("cm") or {}
    sg = _sig(C, t)
    buf = float(s["sl_buffer_sigma"]) * (sg if np.isfinite(sg) else 0.0)
    entry = float((cm.get("candle") or {}).get("c", C.A["c"][t]))
    far = [a["top"] if d < 0 else a["bot"], (cm.get("candle") or {}).get("h" if d < 0 else "l")]
    if ck.get("K_extreme") is not None:
        far.append(ck["K_extreme"])
    far = [x for x in far if x is not None]
    sl = (max(far) + buf) if d < 0 else (min(far) - buf)
    opp = "buyer" if d < 0 else "seller"
    zs = [z for z in ((getattr(C, "Z", None) and C.Z.snap.get(t)) or []) if z["role"] == opp and z["status"] != "dead"]
    tg = [float(z["top"]) for z in zs if z["top"] < entry] if d < 0 else [float(z["bottom"]) for z in zs if z["bottom"] > entry]
    target = (max(tg) if d < 0 else min(tg)) if tg else ck.get("I_end")
    if target is not None and (target - entry) * d <= 0:
        target = None                                                              # entry च्या trade-बाजूला नाही ⇒ target नाही
    risk = (sl - entry) * -d
    rr = None if (target is None or risk <= 0) else round((target - entry) * d / risk, 2)
    return {"entry": round(entry, 2), "sl": round(sl, 2), "target": None if target is None else round(float(target), 2), "rr": rr}


def scan(C, bars, D=None, s=None, cache=None):
    """B1: bars (क्रमाने) वर checklist + चाचण्या ⇒ बाण. रिटर्न यादी {type ✅ / 🟡, bar, known_at, final, …}. causal.
    चाचणी = एकाच दिशेची सलग ①②③ खिडकी (episode_gap पर्यंत खंड चालतो; खिडकीत area बदलला तरी तीच चाचणी). ④ चाचणीभर जमा होतो (≤ t);
    ✅ = ⑥ त्या bar ला + ④ आतापर्यंत. cache = {t: checklist} (एकाच run मध्ये पुन्हा मोजू नये)."""
    s = s or RS.load()
    gap = int(s["episode_gap"])
    marks, ep = [], None

    def close(ep, at, final=True):
        if not ep["done"]:
            marks.append(_mark("🟡", ep["first"], at, final, D, C, s, ep["c4"]))

    for t in bars:
        if cache is not None and t in cache:
            ck = cache[t]
        else:
            ck = checklist(C, t, s)
            if cache is not None:
                cache[t] = ck
        ok = ck["c1"] and ck["c2"] and ck["c3"]
        if ok:
            if ep is not None and ep["dir"] == ck["dir"] and t - ep["last"] <= gap:
                ep["last"] = t
            else:
                if ep is not None:
                    close(ep, t)
                ep = {"dir": ck["dir"], "first": ck, "last": t, "done": False, "c4": []}
            ep["c4"] += [x for x in ck["c4"] if x not in ep["c4"]]
            if not ep["done"] and ep["c4"] and ck["c6"]:
                marks.append(_mark("✅", ck, t, True, D, C, s, ep["c4"]))
                ep["done"] = True
        elif ep is not None and t - ep["last"] > gap:
            close(ep, t)
            ep = None
    if ep is not None:
        close(ep, bars[-1] if len(bars) else None, final=False)                 # चाचणी अजून चालू (chart च्या शेवटी)
    return marks


def _mark(kind, ck, known_at, final, D, C, s, c4=None):
    t = ck["t"]
    a = ck["area"]
    dec = (D or {}).get(t) or {}
    m = {"type": kind, "bar": t, "ts": str(C.ts[t]), "known_at": known_at, "final": bool(final), "dir": ck["dir"], "side": SIDE[ck["dir"]],
         "deg": ck["deg"], "trend": ck["trend"], "area": {k: a[k] for k in ("kind", "id", "bot", "top", "stars", "self")},
         "pattern": ck["pattern"], "c4": list(ck["c4"] if c4 is None else c4), "c5": ck["c5"], "c6": ck["c6"],
         "engine": f"{dec.get('decision', '—')} {dec.get('gate') or ''}".strip(), "engine_why": dec.get("where_wrong")}
    if kind == "✅":
        m.update(_levels(C, t, ck, s))
    return m


def plan(C, t, s=None):
    """B2: शेवटच्या बंद bar (t) पर्यंतच्या माहितीवरून पुढच्या दिवसाची अटींची योजना."""
    s = s or RS.load()
    deg, tr, d = trend(C, t)
    reg = DE.regime(C, t).get("regime")
    st = C.trk[1].state(t)
    I = C.trk[1].I_at(t)
    c = float(C.A["c"][t])
    sg = _sig(C, t)
    buf = float(s["sl_buffer_sigma"]) * (sg if np.isfinite(sg) else 0.0)
    out = {"deg": deg, "trend": tr, "dir": d, "regime": reg, "state": st.get("state"), "close": round(c, 2), "items": [], "invalid": None}
    if d == 0 and tr == "RANGE":
        b = DE.range_band(C, t)
        if b is not None:
            top, bot = float(b[0]), float(b[1])
            mid = (top + bot) / 2
            out["items"] = [{"side": "bear call", "dir": -1, "bot": top - 0.1 * (top - bot), "top": top, "sl": round(top + buf, 2),
                             "target": round(mid, 2), "kind": "range कड"},
                            {"side": "bull put", "dir": 1, "bot": bot, "top": bot + 0.1 * (top - bot), "sl": round(bot - buf, 2),
                             "target": round(mid, 2), "kind": "range कड"}]
            for it in out["items"]:
                e = it["bot"] if it["dir"] < 0 else it["top"]
                it["entry"] = round(e, 2)
                risk = (it["sl"] - e) * -it["dir"]
                it["rr"] = round((it["target"] - e) * it["dir"] / risk, 2) if risk > 0 else None
            out["invalid"] = f"range पट्ट्याबाहेर close ({bot:,.0f} / {top:,.0f})"
        return out
    if d == 0:
        return out
    cand = [a for a in areas(C, t, d, s, I) if (a["bot"] >= c if d < 0 else a["top"] <= c) or a["bot"] <= c <= a["top"]]
    cand.sort(key=lambda a: min(abs(c - a["bot"]), abs(c - a["top"])))
    opp = "buyer" if d < 0 else "seller"
    zs = [z for z in ((getattr(C, "Z", None) and C.Z.snap.get(t)) or []) if z["role"] == opp and z["status"] != "dead"]
    for a in cand[:int(s["plan_areas"])]:
        e = a["bot"] if d < 0 else a["top"]
        sl = (a["top"] + buf) if d < 0 else (a["bot"] - buf)
        tg = [float(z["top"]) for z in zs if z["top"] < e] if d < 0 else [float(z["bottom"]) for z in zs if z["bottom"] > e]
        target = (max(tg) if d < 0 else min(tg)) if tg else (None if I is None else float(I["end"].price))
        if target is not None and (target - e) * d <= 0:
            target = None
        risk = (sl - e) * -d
        rr = None if (target is None or risk <= 0) else round((target - e) * d / risk, 2)
        out["items"].append({**a, "side": SIDE[d], "dir": d, "entry": round(e, 2), "sl": round(sl, 2),
                             "target": None if target is None else round(target, 2), "rr": rr})
    want = "DOWN" if d < 0 else "UP"
    for sd in ((deg,) if deg in (1, 2) else (2, 1)):
        stt = C.st[sd]["states"][t]
        if stt["trend"] == want and stt.get("protected") is not None:
            out["invalid"] = f"D{sd} संरक्षित {'high' if d < 0 else 'low'} {stt['protected']:,.0f} तुटला (close) ⇒ योजना बाद"
            return out
    kind = "H" if d < 0 else "L"                                                   # trend जुळत नाही ⇒ शेवटचा confirmed D2 swing
    ps = [p for p in C.res["pivots"].get(2, []) if p.kind == kind and p.confirm_bar <= t]
    if ps:
        out["invalid"] = f"शेवटचा D2 {'H' if d < 0 else 'L'} {ps[-1].price:,.0f} तुटला (close) ⇒ योजना बाद"
    return out
