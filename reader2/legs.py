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
    reread: dict = None         # re-read मधले पर्यायी votes {"structure" | "anatomy": vote}
    provisional: bool = False   # शेवटच्या confirmed pivot पासून आत्तापर्यंतची अपूर्ण चाल (trend कधीच बदलत नाही)

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
        return f"D{self.degree} {self.dir_name} {'provisional ' if self.provisional else ''}leg bars {self.i0}-{self.i1}"


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


def provisional_leg(pvs, degree, ch):
    """शेवटच्या confirmed pivot पासून आत्तापर्यंतचं टोक (H नंतर सर्वात खालचा low, L नंतर सर्वात उंच high) — अपूर्ण leg, known = शेवटचा
    bar. टोक नाही (pivot नंतर bar नाही) ⇒ None."""
    if not pvs:
        return None
    P = pvs[-1]
    n = len(ch)
    if P.bar >= n - 1:
        return None
    seg = slice(P.bar + 1, n)
    if P.kind == "H":
        j = P.bar + 1 + int(ch.A["l"][seg].argmin())
        p1, d = float(ch.A["l"][j]), -1
    else:
        j = P.bar + 1 + int(ch.A["h"][seg].argmax())
        p1, d = float(ch.A["h"][j]), 1
    if (p1 - P.price) * d <= 0:
        return None
    return Leg(degree, d, P.bar, j, P.price, p1, n - 1, ch.kat[n - 1], provisional=True)


def inner_points(i0, i1, p0, p1, dirn, lower, upto_bar):
    """एक चाल (i0, p0) ⇒ (i1, p1) + आतले खालच्या degree चे pivots (confirm_bar ≤ upto_bar), आलटून पालटून — decision3.daily_legs.classify
    सारखंच: सलग तोच प्रकार ⇒ जास्त टोकाचा; टोकांबाहेरचा pivot नाही; शेवटचा आतला pivot चाल-दिशेचा ⇒ टोकात विलीन. रिटर्न [(bar, price)]."""
    inner = sorted((p for p in lower if i0 < p.bar < i1 and p.confirm_bar <= upto_bar), key=lambda p: p.bar)
    pts, kinds = [(i0, p0)], ["L" if dirn > 0 else "H"]
    for p in inner:
        if (p.price - p0) * dirn < 0 or (p.price - p1) * dirn > 0:
            continue                                                       # चालीच्या टोकांबाहेरचा pivot (दुसऱ्या degree चा टोक) नाही
        if p.kind != kinds[-1]:
            pts.append((p.bar, p.price))
            kinds.append(p.kind)
        elif len(pts) > 1 and (p.price - pts[-1][1]) * (1 if p.kind == "H" else -1) > 0:
            pts[-1] = (p.bar, p.price)
    if len(pts) > 1 and kinds[-1] == ("H" if dirn > 0 else "L"):
        pts = pts[:-1]
    pts.append((i1, p1))
    return pts


def inner_prices(leg, lower, upto_bar):
    return [p for _, p in inner_points(leg.i0, leg.i1, leg.p0, leg.p1, leg.dirn, lower, upto_bar)]
