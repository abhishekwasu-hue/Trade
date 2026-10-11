"""reader2/structure.py — structure vote (spec §2a): leg च्या आतले एक degree खालचे pivots ⇒ decision3.daily_legs.read_counter
(patterns2 नियम: impulse 5-3-5-3-5, diagonal, zigzag 5-3-5, flat 3-3-5 expanded / running सकट, triangle, combination; c > a चालतो).

Vote: impulse / diagonal ⇒ +1; zigzag / flat / triangle / combination ⇒ −1; नाव नसलेली 3-wave ⇒ `three_wave_vote`; आतले pivots नाहीत
(single) किंवा lowest degree ⇒ 0 (रचना दिसत नाही — candles च, spec §2d).
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


def alternatives(ch, leg):
    """Re-read (spec §3.1): पर्यायी pivots एक degree खाली — threshold dc_k[D−1] × reread_k_mult. रिटर्न [(k, vote)]."""
    if leg.degree <= 0:
        return []
    base = float(ch.s["dc_k"][leg.degree - 1])
    out = []
    for m in ch.s["reread_k_mult"]:
        k = base * float(m)
        out.append((k, leg_vote(ch, leg, [ch.pivots(k)])))
    return out
