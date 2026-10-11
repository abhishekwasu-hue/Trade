"""reader2/trend.py — trend-degree legs च्या labels वरून trend अवस्था (bar नुसार, causal: bar i ला फक्त known_bar ≤ i चे legs).

  • फक्त "trend-capable" impulse trend ठरवतो / protected हलवतो / उलटवतो: label impulse, confidence high / medium (दोन्ही votes
    जुळलेले — re-read नंतरही), effective structure impulse, effective anatomy impulsive. एकाच vote वरचा ("low") impulse नाही.
  • Trend = शेवटच्या trend-capable impulse ची दिशा; protected origin = त्याची सुरुवात (त्याच दिशेचा नवा ⇒ origin पुढे).
  • Flip (spec §3.2) = trend-capable counter-move + आधीच्या swing चा break. Correction (c > a सकट, §3.3), uncertain आणि low कधीच नाहीत.
  • Origin च्या पलीकडे close (§3.4) ⇒ trend "uncertain" (re-read). Uncertain कायमचं नाही: पुढचा trend-capable impulse (कोणत्याही
    दिशेचा — origin आधीच तुटला) नेहमीच्या Dow / structure मार्गाने trend पुन्हा ठरवतो. Uncertain ⇒ entries नाहीत.
  • Provisional (अपूर्ण) legs इथे येत नाहीत.
"""
from . import fusion as RF

CAPABLE = ("high", "medium")


def eff_structure(leg):
    """Re-read झालं असेल तर तो structure vote, नाहीतर मूळ."""
    return ((leg.reread or {}).get("structure")) or leg.structure or {}


def eff_anatomy(leg):
    return ((leg.reread or {}).get("anatomy")) or leg.anatomy or {}


def trend_capable(leg):
    """रिटर्न (ok, कारण): दोन्ही votes impulse वर सहमत."""
    why = []
    if leg.label != RF.IMPULSE:
        why.append(f"label is {leg.label}")
    elif leg.confidence not in CAPABLE:
        why.append(f"confidence {leg.confidence} (one vote only)")
    sv = eff_structure(leg)
    if sv.get("cls") != "impulse":
        why.append(f"structure reads {sv.get('family')}, not impulse")
    av = eff_anatomy(leg)
    if av.get("cls") != "impulsive":
        sc = av.get("score")
        why.append("anatomy " + ("NA" if sc is None else f"{av.get('cls')} ({sc:+.2f})") + ", not impulsive")
    if getattr(leg, "provisional", False):
        why.append("provisional leg")
    return (not why), "; ".join(why)


def flip_test(leg, prev, need_break=True):
    """रिटर्न (ok, कारण) — counter-move impulse आहे का (§3.2): trend-capable + prior swing break."""
    ok, why = trend_capable(leg)
    why = [why] if why else []
    if need_break and (prev is None or (leg.p1 - prev.p0) * leg.dirn <= 0):
        why.append("no break of the prior swing" if prev is not None else "no prior swing")
    return (not why), "; ".join(why)


def derive(ch, legs):
    """रिटर्न (states, events). states[i] = {"bar", "known_at", "trend", "dir", "origin", "origin_bar", "why"};
    events = trend बदल [{"bar", "known_at", "from", "to", "leg", "why"}]."""
    legs = sorted((lg for lg in legs if not lg.provisional), key=lambda x: (x.known_bar, x.i1))
    prev_of = {lg.key: p for p, lg in zip([None] + legs[:-1], legs)}
    by_bar = {}
    for lg in legs:
        by_bar.setdefault(lg.known_bar, []).append(lg)
    C = ch.A["c"]
    trend, last_dir, origin, obar, why = None, 0, None, None, ""
    states, events = [], []

    def _set(i, new, lg, reason):
        nonlocal trend
        if new != trend:
            events.append({"bar": i, "known_at": ch.kat[i], "from": trend, "to": new, "leg": lg.key if lg else None, "why": reason})
        trend = new

    for i in range(len(ch)):
        for lg in by_bar.get(i, []):
            if lg.label != RF.IMPULSE:
                continue
            d = "UP" if lg.dirn > 0 else "DOWN"
            opposite = trend in ("UP", "DOWN") and lg.dirn != last_dir
            ok, reason = flip_test(lg, prev_of[lg.key], need_break=opposite)
            if not ok:
                why = f"no {'flip' if opposite else 'trend'} on {lg.name()}: {reason}"
                continue
            if opposite:
                tag = f"flip: impulse counter-move {lg.name()} broke the prior swing"
            elif trend == "uncertain":
                tag = f"trend re-read: impulse {lg.name()}"
            else:
                tag = f"impulse {lg.name()}"
            _set(i, d, lg, tag)
            last_dir, origin, obar, why = lg.dirn, lg.p0, lg.i0, tag
        if trend in ("UP", "DOWN") and origin is not None and (C[i] - origin) * last_dir < 0:
            _set(i, "uncertain", None, f"close beyond protected origin {origin:g}: trend re-read")
            why = "protected origin closed beyond; waiting for an impulse"
        states.append({"bar": i, "known_at": ch.kat[i], "trend": trend, "dir": last_dir, "origin": origin, "origin_bar": obar,
                       "why": why})
    return states, events


def from_events(ch, events):
    """बाहेरची trend marking (उदा. v1): [{"bar", "trend", "origin"?, "leg"?}] ⇒ states (पुढे वाहून नेलेली)."""
    ev = sorted(events, key=lambda e: e["bar"])
    states, k, cur = [], 0, {"trend": None, "origin": None, "leg": None}
    for i in range(len(ch)):
        while k < len(ev) and ev[k]["bar"] <= i:
            cur = {"trend": ev[k]["trend"], "origin": ev[k].get("origin"), "leg": ev[k].get("leg")}
            k += 1
        states.append({"bar": i, "known_at": ch.kat[i], "trend": cur["trend"], "origin": cur["origin"], "leg": cur["leg"],
                       "dir": 1 if cur["trend"] == "UP" else (-1 if cur["trend"] == "DOWN" else 0), "why": "external"})
    out, last = [], None
    for st in states:
        if st["trend"] != last:
            out.append({"bar": st["bar"], "known_at": st["known_at"], "from": last, "to": st["trend"], "leg": st["leg"],
                        "why": "external"})
            last = st["trend"]
    return states, out
