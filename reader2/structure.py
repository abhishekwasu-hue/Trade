"""reader2/structure.py — structure vote (spec §2a): leg च्या आतले एक degree खालचे pivots ⇒ decision3.daily_legs.read_counter
(patterns2 नियम: impulse 5-3-5-3-5, diagonal, zigzag 5-3-5, flat 3-3-5 expanded / running सकट, triangle, combination; c > a चालतो).

Vote: impulse / diagonal ⇒ +1; zigzag / flat / triangle / combination ⇒ −1; नाव नसलेली / न वाचलेली मोजणी ("3-wave", 5 / 9 waves
सकट) ⇒ `three_wave_vote` (निर्णायक नाही); आतले pivots नाहीत (single) किंवा lowest degree ⇒ 0 (रचना दिसत नाही — candles च, spec §2d).
"""
from decision3 import daily_legs as DL

from . import legs as RL

MOTIVE = ("impulse", "diagonal")
NAMED_CORRECTIVE = ("zigzag", "flat", "triangle", "combination")


def vote_prices(prices, s):
    fam = DL.read_counter(prices)["family"] if len(prices) > 2 else "single"
    if fam in MOTIVE:
        v = 1.0
    elif fam in NAMED_CORRECTIVE:
        v = -1.0
    elif fam == "3-wave":
        v = float(s["three_wave_vote"])
    else:
        v = 0.0
    return {"vote": v, "cls": classify(v, s), "family": fam, "n": len(prices) - 1, "prices": [float(x) for x in prices]}


def classify(v, s):
    if abs(v) < float(s["s_decisive"]):
        return "none"
    return "impulse" if v > 0 else "correction"


def leg_vote(ch, leg, lowers, upto_bar=None):
    """lowers = खालच्या degrees चे pivots, जवळच्यापासून ([D−1, D−2, …]); leg च्या आत रचना दिसणारा पहिला संच वापरा (sub-legs = एक
    degree खाली: दोन thresholds एकच swings पकडतात तेव्हा त्याखालचा). रिकामं (lowest degree) ⇒ silent."""
    if not lowers:
        return {"vote": 0.0, "cls": "none", "family": "lowest-degree", "n": 1, "prices": [leg.p0, leg.p1]}
    ub = leg.known_bar if upto_bar is None else upto_bar
    prices = [leg.p0, leg.p1]
    for k, pv in enumerate(lowers):
        prices = RL.inner_prices(leg, pv, ub)
        if len(prices) > 2:
            return dict(vote_prices(prices, ch.s), inner_degree=leg.degree - 1 - k)
    return vote_prices(prices, ch.s)


def sub_degree(leg, lowers, upto_bar=None):
    """leg चे sub-legs ज्या degree वर दिसतात ती (lowers मधला आत रचना असलेला पहिला संच) ⇒ (degree, त्याखालचे संच). नाही ⇒ (D−1, [])."""
    ub = leg.known_bar if upto_bar is None else upto_bar
    for k, pv in enumerate(lowers or []):
        if len(RL.inner_points(leg.i0, leg.i1, leg.p0, leg.p1, leg.dirn, pv, ub)) > 2:
            return leg.degree - 1 - k, list(lowers[k + 1:])
    return leg.degree - 1, list((lowers or [])[1:])


def alt_thresholds(ch, leg, lowers):
    """Re-read (spec §3.1): पर्यायी pivots फक्त एक degree खाली — sub-legs ज्या degree वर दिसतात त्या dc_k चे गुणक (reread_k_mult ≤ 1,
    त्याखालच्या degree च्या वर). रिटर्न ([k], त्याखालचे संच)."""
    if leg.degree <= 0:
        return [], []
    D, rest = sub_degree(leg, lowers)
    base = float(ch.s["dc_k"][max(D, 0)])
    return [base * float(m) for m in ch.s["reread_k_mult"]], rest


def alternatives(ch, leg, lowers=None):
    """पर्यायी pivots ने structure पुन्हा. रिटर्न [(k, vote)]."""
    ks, rest = alt_thresholds(ch, leg, lowers)
    return [(k, leg_vote(ch, leg, [ch.pivots(k)] + rest)) for k in ks]
