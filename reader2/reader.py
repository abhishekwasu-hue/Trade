"""reader2/reader.py — एका frame चं संपूर्ण वाचन: legs (degree नुसार) ⇒ structure + anatomy votes ⇒ fusion ⇒ trend ⇒ self-check.

`read(df)` फक्त दिलेले bars वापरतो (look-ahead नाही: T पर्यंतचं वाचन = `read(df[:T+1])`). Research-only: decision3 / bots / vision
reader2 import करत नाहीत (spec §1; test_reader2_boundary).
"""
from dataclasses import dataclass, field

from . import fusion as RF
from . import legs as RL
from . import selfcheck as SC
from . import trend as RT
from .frame import Chart


@dataclass
class Reading:
    ch: Chart
    pivots: dict                       # degree ⇒ DPivot यादी
    legs: dict                         # degree ⇒ Leg यादी
    states: list = None                # trend अवस्था (bar नुसार)
    events: list = None                # trend बदल
    trend_source: str = "reader2"      # "reader2" / "external"
    log: list = field(default_factory=list)
    passes: int = 0
    htf: dict = None
    low: Chart = None                  # खालच्या TF चा Chart (anatomy, §2d)
    current: dict = field(default_factory=dict)   # degree ⇒ provisional leg (शेवटच्या confirmed pivot पासून आत्तापर्यंत)

    @property
    def trend_degree(self):
        return int(self.ch.s["trend_degree"])

    @property
    def known_at(self):
        return self.ch.kat[-1] if len(self.ch) else None

    def lower(self, degree):
        """खालच्या degrees चे pivots, जवळच्यापासून (lowest degree ⇒ [])."""
        return [self.pivots[D] for D in range(degree - 1, -1, -1) if D in self.pivots]

    def all_legs(self):
        return [lg for D in sorted(self.legs) for lg in self.legs[D]]

    def find(self, degree, i0, i1):
        return next((lg for lg in self.legs.get(degree, []) if lg.i0 == i0 and lg.i1 == i1), None)

    def prev_of(self, leg):
        same = self.legs.get(leg.degree, [])
        if leg.provisional:
            return same[-1] if same else None
        k = same.index(leg)
        return same[k - 1] if k > 0 else None

    def trend_now(self):
        return self.states[-1] if self.states else None


def label_all(R):
    for D in sorted(R.legs):
        for lg in R.legs[D]:
            RF.label_leg(R.ch, lg, R.lower(D), R.prev_of(lg), R.low)
    for D, lg in R.current.items():                     # अपूर्ण चाल पण वाचा (फक्त नोंद; trend / invariants मध्ये नाही)
        RF.label_leg(R.ch, lg, R.lower(D), R.prev_of(lg), R.low)


def rederive(R):
    R.states, R.events = RT.derive(R.ch, R.legs.get(R.trend_degree, []))
    R.trend_source = "reader2"


def build(df, s=None, pivots=None, low=None):
    """Labels + trend, self-check शिवाय. pivots = {degree: [(bar, kind[, confirm_bar])] किंवा DPivot} (बाहेरची marking)."""
    ch = Chart(df, s)
    lowc = Chart(low, ch.s) if low is not None else None
    ov = {}
    for D, pv in (pivots or {}).items():
        ov[D] = [p for p in pv] if pv and hasattr(pv[0], "confirm_bar") else RL.external_pivots(ch, pv)
    pvs = RL.degree_pivots(ch, ov)
    legs = {D: RL.make_legs(pvs[D], D, ch) for D in sorted(pvs)}
    cur = {D: RL.provisional_leg(pvs[D], D, ch) for D in sorted(pvs)}
    R = Reading(ch, pvs, legs, low=lowc, current={D: lg for D, lg in cur.items() if lg is not None})
    label_all(R)
    rederive(R)
    return R


def read(df, s=None, pivots=None, low=None, higher=None):
    """संपूर्ण वाचन + self-check (spec §3). higher = वरच्या TF चं Reading (invariant 6)."""
    R = build(df, s, pivots, low)
    SC.run(R, higher)
    return R


def mark(R, labels=None, events=None):
    """बाहेरची marking (v1 / hand) R वर: labels {(degree, i0, i1): label}; events = trend [{"bar", "trend", "origin"?, "leg"?}].
    Events नसतील तर trend नव्या labels वरून. नंतर `selfcheck.run(R)` ती marking तपासतो."""
    for key, lab in (labels or {}).items():
        lg = R.find(*key)
        if lg is None:
            raise KeyError(f"no leg {key}")
        lg.label, lg.confidence, lg.reason = lab, None, "external marking"
    if events is not None:
        R.states, R.events = RT.from_events(R.ch, events)
        R.trend_source = "external"
    elif labels:
        rederive(R)
    return R


def summary(R):
    """छोटी English नोंद (debug / tests)."""
    t = R.trend_now()
    out = {"trend": t["trend"] if t else None, "origin": t["origin"] if t else None, "passes": R.passes,
           "legs": [{"degree": lg.degree, "dir": lg.dir_name, "i0": lg.i0, "i1": lg.i1, "label": lg.label, "confidence": lg.confidence,
                     "anatomy": RT.eff_anatomy(lg).get("score"), "structure": RT.eff_structure(lg).get("family"),
                     "provisional": lg.provisional, "reason": lg.reason, "known_at": lg.known_at}
                    for lg in R.all_legs() + list(R.current.values())],
           "selfcheck": [e["text"] for e in R.log]}
    return out
