"""reader2/fusion.py — structure vote + anatomy vote ⇒ label (spec §2c).

  • दोन्ही एकच सांगतात ⇒ तो label, confidence "high".
  • एक निर्णायक, दुसरा गप्प (structure "none" / anatomy neutral / NA) ⇒ निर्णायकाचा label, "medium".
  • दोन्ही गप्प ⇒ "uncertain" (कारणासह).
  • विरोध ⇒ re-read (पर्यायी pivots एक degree खाली, spec §3.1): एखादं पर्यायी वाचन anatomy शी जुळलं ⇒ तो label, "low"; नाहीतर
    "uncertain" (कारणासह). Uncertain leg trend उलटत नाही आणि entry देत नाही (trend.py).
"""
from . import anatomy as RA
from . import structure as RSt

IMPULSE, CORRECTION, UNCERTAIN = "impulse", "correction", "uncertain"
_A2L = {RA.LEAN_IMP: IMPULSE, RA.LEAN_COR: CORRECTION}


def _a_txt(av):
    return "NA" if av["score"] is None else f"{av['cls']} ({av['score']:+.2f})"


def _s_txt(sv):
    return f"{sv['family']} ({sv['n']} waves)"


def fuse(sv, av):
    """रिटर्न (label, confidence, reason) — re-read शिवाय."""
    s_l = {"impulse": IMPULSE, "correction": CORRECTION}.get(sv["cls"])
    a_l = _A2L.get(av["cls"])
    if s_l and a_l and s_l == a_l:
        return s_l, "high", f"structure {_s_txt(sv)} and anatomy {_a_txt(av)} agree"
    if s_l and a_l:
        return None, None, f"structure reads {_s_txt(sv)} but anatomy reads {_a_txt(av)}"
    if s_l or a_l:
        lab = s_l or a_l
        src = f"structure {_s_txt(sv)}" if s_l else f"anatomy {_a_txt(av)}"
        other = f"anatomy {_a_txt(av)}" if s_l else f"structure {_s_txt(sv)}"
        return lab, "medium", f"{src}; {other} is silent"
    return UNCERTAIN, None, f"no decisive vote: structure {_s_txt(sv)}, anatomy {_a_txt(av)}"


def reread(ch, leg, sv, av):
    """विरोध ⇒ पर्यायी खालचे pivots. रिटर्न (label, confidence, reason, structure vote वापरलेला)."""
    a_l = _A2L.get(av["cls"])
    tried = []
    for k, alt in RSt.alternatives(ch, leg):
        tried.append(f"k={k:g}: {_s_txt(alt)}")
        if {"impulse": IMPULSE, "correction": CORRECTION}.get(alt["cls"]) == a_l:
            return a_l, "low", (f"structure {_s_txt(sv)} conflicted with anatomy {_a_txt(av)}; re-read with alternative pivots "
                                f"(k={k:g}) reads {_s_txt(alt)}"), dict(alt, reread_k=k)
    why = f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; re-read did not resolve" + (f" ({'; '.join(tried)})" if tried else "")
    return UNCERTAIN, None, why, sv


def label_leg(ch, leg, lower, prev=None, low=None):
    """Leg वर दोन्ही votes + fusion (+ विरोध ⇒ re-read). Leg mutate करतो आणि परत देतो."""
    sv = RSt.leg_vote(ch, leg, lower)
    av = RA.leg_vote(ch, leg, prev, low)
    leg.structure, leg.anatomy = sv, av
    lab, conf, why = fuse(sv, av)
    if lab is None:
        lab, conf, why, sv2 = reread(ch, leg, sv, av)
        leg.structure = dict(sv, reread=sv2) if sv2 is not sv else sv
    leg.label, leg.confidence, leg.reason = lab, conf, why
    return leg
