"""reader2/fusion.py — structure vote + anatomy vote ⇒ label (spec §2c), confidence, कारण.

  • दोन्ही एकच सांगतात ⇒ तो label, "high".
  • विरोध ⇒ re-read (पर्यायी pivots फक्त एक degree खाली: structure पुन्हा आणि anatomy roll-up पुन्हा): दोन्ही जुळले ⇒ "medium";
    नाहीतर "uncertain" (कारणासह).
  • एक vote गप्प ⇒ आधी re-read (गप्प vote पुन्हा, पर्यायी खालच्या pivots ने). जुळलं ⇒ "medium"; विरोध ⇒ "uncertain"; अजून गप्प ⇒
      – फक्त structure "impulse" ⇒ "uncertain" (candles नी पुष्टी नाही — Abhi ची तक्रार: रचनेवरूनच impulse नाही);
      – फक्त structure "correction" ⇒ correction, "low";
      – फक्त anatomy ⇒ तो label, "low" (lowest degree ला रचना नसते).
  • दोन्ही गप्प ⇒ "uncertain".
"low" किंवा "uncertain" impulse trend ठरवत नाही, उलटवत नाही, protected हलवत नाही (trend.py `trend_capable`).
"""
from . import anatomy as RA
from . import structure as RSt

IMPULSE, CORRECTION, UNCERTAIN = "impulse", "correction", "uncertain"
_A2L = {RA.LEAN_IMP: IMPULSE, RA.LEAN_COR: CORRECTION}
_S2L = {"impulse": IMPULSE, "correction": CORRECTION}


def _a_txt(av):
    return "NA" if av.get("score") is None else f"{av['cls']} ({av['score']:+.2f})"


def _s_txt(sv):
    return f"{sv['family']} ({sv['n']} waves)"


def fuse(sv, av):
    """पहिलं वाचन (re-read शिवाय). रिटर्न (label | None = re-read हवं, confidence, कारण)."""
    s_l, a_l = _S2L.get(sv["cls"]), _A2L.get(av.get("cls"))
    if s_l and a_l and s_l == a_l:
        return s_l, "high", f"structure {_s_txt(sv)} and anatomy {_a_txt(av)} agree"
    if not s_l and not a_l:
        return UNCERTAIN, None, f"no decisive vote: structure {_s_txt(sv)}, anatomy {_a_txt(av)}"
    return None, None, None


def decide(ch, leg, lowers, prev=None, low=None):
    """leg.structure / leg.anatomy (पहिलं वाचन) ⇒ (label, confidence, कारण); re-read केलं तर leg.reread मध्ये पर्यायी votes."""
    sv, av = leg.structure, leg.anatomy
    leg.reread = None
    lab, conf, why = fuse(sv, av)
    if lab is not None:
        return lab, conf, why
    s_l, a_l = _S2L.get(sv["cls"]), _A2L.get(av.get("cls"))
    alt_s = RSt.alternatives(ch, leg, lowers) if (a_l and s_l != a_l) else []        # structure पुन्हा (विरोध / गप्प)
    alt_a = RA.alternatives(ch, leg, lowers, prev, low) if (s_l and s_l != a_l) else []  # anatomy roll-up पुन्हा
    for k, x in alt_s:
        if _S2L.get(x["cls"]) == a_l:
            leg.reread = {"structure": dict(x, reread_k=k)}
            return a_l, "medium", (f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; re-read with alternative pivots one degree lower "
                                   f"(k={k:g}) reads {_s_txt(x)}")
    for k, x in alt_a:
        if _A2L.get(x.get("cls")) == s_l:
            leg.reread = {"anatomy": dict(x, reread_k=k)}
            return s_l, "medium", (f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; anatomy re-read from sub-legs at k={k:g} reads "
                                   f"{_a_txt(x)}")
    tried = [f"structure k={k:g}: {_s_txt(x)}" for k, x in alt_s] + [f"anatomy k={k:g}: {_a_txt(x)}" for k, x in alt_a]
    tail = f" (re-read: {'; '.join(tried)})" if tried else ""
    if s_l and a_l:
        return UNCERTAIN, None, f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; re-read did not resolve{tail}"
    if s_l:
        opp = [x for _, x in alt_a if _A2L.get(x.get("cls")) not in (None, s_l)]
        if opp:
            return UNCERTAIN, None, f"structure {_s_txt(sv)} vs re-read anatomy {_a_txt(opp[0])}{tail}"
        if s_l == IMPULSE:
            return UNCERTAIN, None, f"impulse structure {_s_txt(sv)} not confirmed by the candles: anatomy {_a_txt(av)}{tail}"
        return CORRECTION, "low", f"structure {_s_txt(sv)}; anatomy {_a_txt(av)} silent{tail}"
    opp = [x for _, x in alt_s if _S2L.get(x["cls"]) not in (None, a_l)]
    if opp:
        return UNCERTAIN, None, f"anatomy {_a_txt(av)} vs re-read structure {_s_txt(opp[0])}{tail}"
    return a_l, "low", f"anatomy {_a_txt(av)}; structure {_s_txt(sv)} silent{tail}"


def label_leg(ch, leg, lowers, prev=None, low=None):
    """Leg वर दोन्ही votes + fusion (+ re-read). Leg mutate करतो आणि परत देतो."""
    leg.structure = RSt.leg_vote(ch, leg, lowers)
    leg.anatomy = RA.leg_vote(ch, leg, prev, low, lowers)
    leg.label, leg.confidence, leg.reason = decide(ch, leg, lowers, prev, low)
    return leg
