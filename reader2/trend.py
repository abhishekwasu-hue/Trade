"""reader2/trend.py — trend-degree legs च्या labels वरून trend अवस्था (bar नुसार, causal: bar i ला फक्त known_bar ≤ i चे legs).

  • Trend = शेवटच्या impulse leg ची दिशा; protected origin = त्या impulse ची सुरुवात (त्याच दिशेचा नवा impulse ⇒ origin पुढे).
  • Flip (spec §3.2) फक्त impulse counter-move ने: label impulse + impulse structure + impulsive anatomy + आधीच्या swing चा break
    (counter-move चं टोक आधीच्या leg च्या सुरुवातीपलीकडे). नाहीतर trend तसाच. Correction (c > a सकट, §3.3) आणि uncertain कधीच flip नाहीत.
  • Origin च्या पलीकडे close (§3.4) ⇒ trend "uncertain" (re-read): पुढचा पूर्ण impulse (structure + anatomy; उलट दिशेला prior
    swing break सुद्धा) trend ठरवतो. Uncertain ⇒ entries नाहीत.
"""
from . import fusion as RF


def eff_structure(leg):
    """Re-read झालं असेल तर तो structure vote, नाहीतर मूळ."""
    sv = leg.structure or {}
    return sv.get("reread") or sv


def flip_test(leg, prev, need_break=True):
    """रिटर्न (ok, कारण) — counter-move impulse आहे का (§3.2): label impulse + impulse structure + impulsive anatomy (+ prior swing
    break). need_break=False ⇒ origin तुटल्यावर ("uncertain") जुन्याच दिशेने trend पुन्हा ठरवताना (break ची गरज नाही)."""
    why = []
    if leg.label != RF.IMPULSE:
        why.append(f"label is {leg.label}")
    sv = eff_structure(leg)
    if sv.get("cls") != "impulse":
        why.append(f"structure reads {sv.get('family')}, not impulse")
    av = leg.anatomy or {}
    if av.get("cls") != "impulsive":
        sc = av.get("score")
        why.append("anatomy " + ("NA" if sc is None else f"{av.get('cls')} ({sc:+.2f})") + ", not impulsive")
    if need_break and (prev is None or (leg.p1 - prev.p0) * leg.dirn <= 0):
        why.append("no break of the prior swing" if prev is not None else "no prior swing")
    return (not why), "; ".join(why)


def derive(ch, legs):
    """रिटर्न (states, events). states[i] = {"bar", "known_at", "trend", "dir", "origin", "origin_bar", "why"};
    events = trend बदल [{"bar", "known_at", "from", "to", "leg", "why"}]."""
    legs = sorted(legs, key=lambda x: (x.known_bar, x.i1))
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
            if trend is None or (trend != "uncertain" and lg.dirn == last_dir):
                _set(i, d, lg, f"impulse {lg.name()}")
                last_dir, origin, obar, why = lg.dirn, lg.p0, lg.i0, f"impulse {lg.name()}"
                continue
            ok, reason = flip_test(lg, prev_of[lg.key], need_break=lg.dirn != last_dir)
            if ok:
                tag = "flip: impulse counter-move" if lg.dirn != last_dir else "trend re-read: impulse"
                _set(i, d, lg, f"{tag} {lg.name()}" + (" broke the prior swing" if lg.dirn != last_dir else ""))
                last_dir, origin, obar, why = lg.dirn, lg.p0, lg.i0, f"{tag} {lg.name()}"
            else:
                why = f"no {'flip' if lg.dirn != last_dir else 're-read'} on {lg.name()}: {reason}"
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
