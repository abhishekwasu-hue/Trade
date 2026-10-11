"""reader2/legs.py — degree नुसार legs (दिशा, degree, bars, known_at) आणि leg च्या आतले एक degree खालचे pivots.

Degree D चे pivots = directional change, threshold `dc_k[D]` × MR (त्याच timeframe चे). Leg = त्याच degree चे लागोपाठचे दोन confirmed
pivots; bars (i0, i1]; known_bar = शेवटच्या pivot चा confirm_bar (leg तेव्हाच माहीत). बाहेरून दिलेले pivots (hand / v1 marking) ⇒
`external_pivots` (confirm_bar दिला नसेल तर pivot चा bar — hindsight marking, ते नोंदवलं जातं).
"""
from dataclasses import dataclass, field

import pandas as pd

from decision3.daily import DPivot


@dataclass
class Leg:
    degree: int
    dirn: int                   # +1 up / −1 down
    i0: int                     # सुरुवातीचा pivot bar
    i1: int                     # शेवटचा pivot bar
    p0: float
    p1: float
    known_bar: int              # शेवटच्या pivot चा confirm_bar
    known_at: pd.Timestamp
    structure: dict = None
    anatomy: dict = None
    label: str = None           # "impulse" / "correction" / "uncertain"
    confidence: str = None      # "high" / "medium" / "low" / None
    reason: str = ""
    history: list = field(default_factory=list)

    @property
    def key(self):
        return (self.degree, self.i0, self.i1)

    @property
    def bars(self):
        return self.i1 - self.i0

    @property
    def dir_name(self):
        return "UP" if self.dirn > 0 else "DOWN"

    def name(self):
        return f"D{self.degree} {self.dir_name} leg bars {self.i0}-{self.i1}"


def external_pivots(ch, pts):
    """[(bar, kind) | (bar, kind, confirm_bar)] ⇒ DPivot (price = त्या bar चा high / low)."""
    out = []
    for p in pts:
        b, kind = int(p[0]), p[1]
        cb = int(p[2]) if len(p) > 2 else b
        price = float(ch.A["h"][b] if kind == "H" else ch.A["l"][b])
        out.append(DPivot(kind, price, b, pd.Timestamp(ch.d["timestamp"].iloc[b]), cb, ch.kat[cb]))
    return out


def degree_pivots(ch, override=None):
    """{degree: pivots}; override = {degree: DPivot यादी} (बाहेरची marking)."""
    out = {D: ch.pivots(k) for D, k in enumerate(ch.s["dc_k"])}
    for D, pv in (override or {}).items():
        out[int(D)] = list(pv)
    return out


def make_legs(pvs, degree, ch):
    out = []
    for a, b in zip(pvs, pvs[1:]):
        if a.kind == b.kind or b.bar <= a.bar:
            continue
        kb = max(a.confirm_bar, b.confirm_bar)
        out.append(Leg(degree, 1 if b.price > a.price else -1, a.bar, b.bar, a.price, b.price, kb, ch.kat[kb]))
    return out


def inner_prices(leg, lower, upto_bar):
    """Leg (टोक ते टोक) + आतले खालच्या degree चे pivots (confirm_bar ≤ upto_bar), आलटून पालटून — decision3.daily_legs.classify
    सारखंच: सलग तोच प्रकार ⇒ जास्त टोकाचा; शेवटचा आतला pivot leg-दिशेचा ⇒ टोकात विलीन. रिटर्न prices यादी."""
    inner = sorted((p for p in lower if leg.i0 < p.bar < leg.i1 and p.confirm_bar <= upto_bar), key=lambda p: p.bar)
    prices, kinds = [leg.p0], ["L" if leg.dirn > 0 else "H"]
    for p in inner:
        if (p.price - leg.p0) * leg.dirn < 0 or (p.price - leg.p1) * leg.dirn > 0:
            continue                                                       # leg च्या टोकांबाहेरचा pivot (दुसऱ्या degree चा टोक) नाही
        if p.kind != kinds[-1]:
            prices.append(p.price)
            kinds.append(p.kind)
        elif len(prices) > 1 and (p.price - prices[-1]) * (1 if p.kind == "H" else -1) > 0:
            prices[-1] = p.price
    if len(prices) > 1 and kinds[-1] == ("H" if leg.dirn > 0 else "L"):
        prices = prices[:-1]
    prices.append(leg.p1)
    return prices
