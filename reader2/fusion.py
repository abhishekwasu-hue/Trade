"""reader2/fusion.py — structure vote + anatomy vote ⇒ label (spec §2c), confidence, कारण.

  • दोन्ही एकच सांगतात ⇒ तो label, "high".
  • विरोध किंवा एक vote गप्प ⇒ re-read: पर्यायी pivots फक्त एक degree खाली (`reread_k_mult`, दोन पर्याय). निर्णय **बहुमताने**
    (पर्यायांपैकी अर्ध्यापेक्षा जास्त), दोन्ही दिशांना एकच नियम — पहिला जुळणारा पर्याय निवडत नाही (cherry-picking नाही):
      – structure पुन्हा (anatomy च्या बाजूचं बहुमत) किंवा anatomy roll-up पुन्हा (structure च्या बाजूचं बहुमत) ⇒ तो label, "medium";
      – विरुद्ध बहुमत ⇒ "uncertain"; बहुमत नाही ⇒ विरोध असेल तर "uncertain", एक vote गप्प असेल तर:
          · फक्त structure "impulse" ⇒ "uncertain" (candles नी पुष्टी नाही); फक्त structure "correction" ⇒ correction, "low";
          · फक्त anatomy ⇒ तो label, "low" (lowest degree ला रचना नसते).
  • नाव असलेली corrective रचना (zigzag / flat / triangle / combination) re-read ने कधीच impulse होत नाही.
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


def _majority(votes, label, to_label):
    """पर्यायांपैकी अर्ध्यापेक्षा जास्त `label` सांगतात का."""
    return bool(votes) and sum(1 for x in votes if to_label(x) == label) * 2 > len(votes)


def decide(ch, leg, lowers, prev=None, low=None):
    """leg.structure / leg.anatomy (पहिलं वाचन) ⇒ (label, confidence, कारण); re-read केलं तर leg.reread मध्ये पर्यायी votes."""
    sv, av = leg.structure, leg.anatomy
    leg.reread = None
    lab, conf, why = fuse(sv, av)
    if lab is not None:
        return lab, conf, why
    s_l, a_l = _S2L.get(sv["cls"]), _A2L.get(av.get("cls"))
    named_cor = sv.get("family") in RSt.NAMED_CORRECTIVE
    alt_s = RSt.alternatives(ch, leg, lowers) if (a_l and s_l != a_l) else []          # structure पुन्हा (विरोध / गप्प)
    alt_a = RA.alternatives(ch, leg, prev, low) if (s_l and s_l != a_l) else []         # anatomy roll-up पुन्हा
    xs, xa = [x for _, x in alt_s], [x for _, x in alt_a]
    s_of = lambda x: _S2L.get(x["cls"])                                                  # noqa: E731
    a_of = lambda x: _A2L.get(x.get("cls"))                                              # noqa: E731
    tried = [f"structure k={k:g}: {_s_txt(x)}" for k, x in alt_s] + [f"anatomy k={k:g}: {_a_txt(x)}" for k, x in alt_a]
    tail = f" (re-read: {'; '.join(tried)})" if tried else ""
    s_ok = _majority(xs, a_l, s_of) and not (named_cor and a_l == IMPULSE)               # नाव असलेली correction impulse होत नाही
    a_ok = _majority(xa, s_l, a_of)
    if s_ok and not a_ok:
        x = next(x for x in xs if s_of(x) == a_l)
        leg.reread = {"structure": x}
        return a_l, "medium", (f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; a majority of the alternative pivots one degree "
                               f"lower reads {_s_txt(x)}{tail}")
    if a_ok and not s_ok:
        x = next(x for x in xa if a_of(x) == s_l)
        leg.reread = {"anatomy": x}
        return s_l, "medium", (f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; a majority of the anatomy re-reads from the "
                               f"alternative sub-legs reads {_a_txt(x)}{tail}")
    if s_l and a_l:
        return UNCERTAIN, None, f"structure {_s_txt(sv)} vs anatomy {_a_txt(av)}; re-read has no majority to resolve it{tail}"
    if s_l:
        if _majority(xa, IMPULSE if s_l == CORRECTION else CORRECTION, a_of):
            return UNCERTAIN, None, f"structure {_s_txt(sv)} vs a majority of re-read anatomy against it{tail}"
        if s_l == IMPULSE:
            return UNCERTAIN, None, f"impulse structure {_s_txt(sv)} not confirmed by the candles: anatomy {_a_txt(av)}{tail}"
        return CORRECTION, "low", f"structure {_s_txt(sv)}; anatomy {_a_txt(av)} silent{tail}"
    if _majority(xs, IMPULSE if a_l == CORRECTION else CORRECTION, s_of):
        return UNCERTAIN, None, f"anatomy {_a_txt(av)} vs a majority of re-read structure against it{tail}"
    return a_l, "low", f"anatomy {_a_txt(av)}; structure {_s_txt(sv)} silent{tail}"


def label_leg(ch, leg, lowers, prev=None, low=None):
    """Leg वर दोन्ही votes + fusion (+ re-read). Leg mutate करतो आणि परत देतो."""
    leg.structure = RSt.leg_vote(ch, leg, lowers)
    leg.anatomy = RA.leg_vote(ch, leg, prev, low)                  # reader चे स्वतःचे sub-legs (बाहेरच्या pivots पासून स्वतंत्र)
    leg.label, leg.confidence, leg.reason = decide(ch, leg, lowers, prev, low)
    return leg
