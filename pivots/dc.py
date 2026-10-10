"""pivots/dc.py — Directional Change (DC) चा नेमका नियम (थर 1 prompt §1.4–§1.5; Guillaume et al. 1997, Glattfelder et al. 2011).

D0: 15M bars वर. Extreme चं update `>=` / `<=` ने (बरोबरीत नंतरची candle). Extreme पासून उलट θ ⇒ ते टोक confirm (pivot), `known_at` =
confirmation candle चा close. एकाच candle मध्ये नवं टोक आणि उलट θ ⇒ 1m क्रम (फक्त त्या candle चे 1m) किंवा सावध नियम (फक्त extend;
पुढच्या candle ने स्वतः θ पूर्ण करायला हवा). एका candle मधून दोन pivots कधीच नाहीत.
D(n+1): D(n) च्या confirmed pivots च्या क्रमावर DC (tentative नाही) ⇒ nesting बांधलेलं: D(n+1) ⊆ D(n).
Confirmed pivot नंतर कधीच बदलत नाही (frozen dataclass).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

UNDECIDED, UP, DOWN = "UNDECIDED", "UP", "DOWN"
BAR = pd.Timedelta(minutes=15)


@dataclass(frozen=True)
class Pivot:
    degree: int
    kind: str                 # "H" | "L"
    price: float
    bar: int                  # टोकाची 15M candle (index)
    ts: pd.Timestamp          # टोकाच्या candle ची सुरुवात
    confirm_bar: int          # confirmation candle (index)
    known_at: pd.Timestamp    # confirmation candle चा close
    sigma: float
    theta: float
    rule: str                 # normal | 1m | conservative-नंतर (normal)
    eq: bool = False          # EQH / EQL (लागोपाठच्या same-type pivot शी ≤ eq_tol × σ)
    warmup: bool = False
    session: int = -1         # known_at चा session क्रमांक (segment मधला)


def _order_1m(rows, bar_high, bar_low, ext_dir):
    """एका 15M candle चे 1m rows ⇒ क्रम. ext_dir = +1 (नवं high, नंतर low हवा) / −1 (नवं low, नंतर high हवा).
    रिटर्न ("first_ext", after_extreme) / ("first_rev", None) / None (ठरवता येत नाही: 1m नाही / अपूर्ण / जुळत नाही / एकाच मिनिटात)."""
    if rows is None or len(rows) == 0:
        return None
    h, lo = rows["high"].to_numpy(float), rows["low"].to_numpy(float)
    eq = (lambda a, b: np.abs(np.asarray(a, float) - b) <= 1e-9)            # noqa: E731 — अचूक जुळणी (rtol नाही)
    if len(rows) < 15 or not eq(h.max(), bar_high) or not eq(lo.min(), bar_low):
        return None
    if ext_dir > 0:
        ie = int(np.flatnonzero(eq(h, bar_high))[0])           # high पहिल्यांदा कधी
        ir = int(np.flatnonzero(eq(lo, bar_low))[0])
        if ie == ir:
            return None                                                 # एकाच मिनिटात दोन्ही
        if ie < ir:
            return "first_ext", float(lo[ie + 1:].min())        # टोकानंतरचा सगळ्यात खालचा भाव (उलट θ तपासायला)
        return "first_rev", None
    ie = int(np.flatnonzero(eq(lo, bar_low))[0])
    ir = int(np.flatnonzero(eq(h, bar_high))[0])
    if ie == ir:
        return None
    if ie < ir:
        return "first_ext", float(h[ie + 1:].max())
    return "first_rev", None


class D0:
    """15M bars वर DC (एकाच segment मध्ये; segment बदलला ⇒ reset). step() प्रत्येक बंद bar साठी, क्रमाने."""

    def __init__(self, degree=0):
        self.degree = degree
        self.order_fn = _order_1m           # 1m क्रम-निर्णय (swings2: stream मध्ये साठवलेला निर्णय replay ला — replay = live)
        self.reset()

    def reset(self):
        self.mode = UNDECIDED
        self.ext = None                 # (price, bar)
        self.mx = None                  # UNDECIDED: (price, bar)
        self.mn = None
        self.out = []
        self.cons = None                # सावध नियम लागलेली candle (index) ⇒ तोच टोक नंतर confirm झाला तर "conservative"
        self.rev = None                 # टोकानंतरचं सगळ्यात उलटं भाव (θ फक्त बदलल्याने confirm होऊ नये — नवी हालचाल हवी)

    def _confirm(self, kind, price, bar, b, ts, known_at, sigma, theta, rule, session, ts_of):
        if rule == "normal" and self.cons is not None and int(bar) == self.cons:
            rule = "conservative"
        self.cons = None
        p = Pivot(self.degree, kind, float(price), int(bar), ts_of(bar), int(b), known_at, float(sigma), float(theta), rule, session=session)
        self.out.append(p)
        return p

    def _hold(self, b):
        """सावध नियम: candle फक्त extend करते; उलट θ पुढच्या candle ने स्वतः पूर्ण करायला हवा."""
        self.cons = b

    def step(self, b, hi, lo, theta, sigma, known_at, session, ts_of, rows_1m=None):
        """एक bar. रिटर्न नवा confirmed pivot किंवा None (एका bar मधून जास्तीत जास्त एक)."""
        if self.mode == UNDECIDED:
            if self.mx is None or hi >= self.mx[0]:
                self.mx = (hi, b)
            if self.mn is None or lo <= self.mn[0]:
                self.mn = (lo, b)
            down = self.mx[0] - lo >= theta
            up = hi - self.mn[0] >= theta
            if down and up:
                if self.mx[1] == b and self.mn[1] < b:                  # नवं high याच candle चं ⇒ L (आधीचं) निश्चित
                    down = False
                elif self.mn[1] == b and self.mx[1] < b:                # नवं low याच candle चं ⇒ H (आधीचं) निश्चित
                    up = False
                else:
                    self._hold(b)                                        # दोन्ही टोकं याच candle मध्ये ⇒ सावध: फक्त extend
                    return None
            if down:
                if self.mx[1] == b:                                     # टोक आणि उलट θ एकाच candle मध्ये
                    o = self.order_fn(rows_1m, hi, lo, +1)
                    if o is None or o[0] == "first_rev" or self.mx[0] - o[1] < theta:
                        self._hold(b)
                        return None
                    p = self._confirm("H", *self.mx, b, None, known_at, sigma, theta, "1m", session, ts_of)
                    self.mode, self.ext, self.rev = DOWN, None, None    # नवं टोक पुढच्या candle पासून (एका candle मधून दोन pivots नाहीत)
                    return p
                p = self._confirm("H", *self.mx, b, None, known_at, sigma, theta, "normal", session, ts_of)
                self.mode, self.ext, self.rev = DOWN, (lo, b), None
                return p
            if up:
                if self.mn[1] == b:
                    o = self.order_fn(rows_1m, hi, lo, -1)
                    if o is None or o[0] == "first_rev" or o[1] - self.mn[0] < theta:
                        self._hold(b)
                        return None
                    p = self._confirm("L", *self.mn, b, None, known_at, sigma, theta, "1m", session, ts_of)
                    self.mode, self.ext, self.rev = UP, None, None
                    return p
                p = self._confirm("L", *self.mn, b, None, known_at, sigma, theta, "normal", session, ts_of)
                self.mode, self.ext, self.rev = UP, (hi, b), None
                return p
            return None
        if self.mode == UP:
            if self.ext is None:
                self.ext = (hi, b)
            prev = self.ext
            if hi >= self.ext[0]:
                self.ext, self.rev = (hi, b), None                     # rev = टोकाच्या candle नंतरच्या candles चं उलटं टोक
                fresh = True
            else:
                fresh = self.rev is None or lo < self.rev              # उलट हालचाल याच candle ने पुढे नेली का
                self.rev = lo if self.rev is None else min(self.rev, lo)
            if self.ext[0] - lo < theta or not fresh:
                return None
            if self.ext[1] != b:
                p = self._confirm("H", *self.ext, b, None, known_at, sigma, theta, "normal", session, ts_of)
                self.mode, self.ext, self.rev = DOWN, (lo, b), None
                return p
            o = self.order_fn(rows_1m, hi, lo, +1)                          # same-bar: नवं high आणि उलट θ
            if o is None:
                self._hold(b)                                            # सावध: फक्त extend
                return None
            if o[0] == "first_ext":
                if self.ext[0] - o[1] < theta:
                    return None
                p = self._confirm("H", *self.ext, b, None, known_at, sigma, theta, "1m", session, ts_of)
                self.mode, self.ext, self.rev = DOWN, None, None    # नवं टोक पुढच्या candle पासून (एका candle मधून दोन pivots नाहीत)
                return p
            if prev[1] != b and prev[0] - lo >= theta:                                   # आधी low (जुन्या टोकापासून θ), मग नवं high ⇒ जुनं टोक H
                p = self._confirm("H", *prev, b, None, known_at, sigma, theta, "1m", session, ts_of)
                self.mode, self.ext, self.rev = DOWN, (lo, b), None
                return p
            return None
        # DOWN (आरसा)
        if self.ext is None:
            self.ext = (lo, b)
        prev = self.ext
        if lo <= self.ext[0]:
            self.ext, self.rev = (lo, b), None
            fresh = True
        else:
            fresh = self.rev is None or hi > self.rev
            self.rev = hi if self.rev is None else max(self.rev, hi)
        if hi - self.ext[0] < theta or not fresh:
            return None
        if self.ext[1] != b:
            p = self._confirm("L", *self.ext, b, None, known_at, sigma, theta, "normal", session, ts_of)
            self.mode, self.ext, self.rev = UP, (hi, b), None
            return p
        o = self.order_fn(rows_1m, hi, lo, -1)
        if o is None:
            self._hold(b)
            return None
        if o[0] == "first_ext":
            if o[1] - self.ext[0] < theta:
                return None
            p = self._confirm("L", *self.ext, b, None, known_at, sigma, theta, "1m", session, ts_of)
            self.mode, self.ext, self.rev = UP, None, None
            return p
        if prev[1] != b and hi - prev[0] >= theta:
            p = self._confirm("L", *prev, b, None, known_at, sigma, theta, "1m", session, ts_of)
            self.mode, self.ext, self.rev = UP, (hi, b), None
            return p
        return None


class Upper:
    """D(n+1): D(n) च्या confirmed pivots च्या क्रमावर DC. Pivot चा भाव / candle D(n) च्या pivot चेच; known_at = max(स्वतःचा θ
    ओलांडल्याचा क्षण = खालच्या pivot चा known_at, टोकाच्या pivot चा known_at)."""

    def __init__(self, degree):
        self.degree = degree
        self.reset()

    def reset(self):
        self.mode = UNDECIDED
        self.ext = None                 # Pivot (खालच्या degree चा)
        self.mx = None
        self.mn = None
        self.out = []
        self.rev = None                 # टोकानंतरचा सगळ्यात उलटा pivot भाव (θ फक्त बदलल्याने confirm नाही)

    def _confirm(self, kind, src, trig, theta, sigma, session):
        p = Pivot(self.degree, kind, src.price, src.bar, src.ts, trig.confirm_bar, max(trig.known_at, src.known_at), float(sigma),
                  float(theta), src.rule, session=session)
        self.out.append(p)
        return p

    def step(self, q, theta, sigma, session):
        """q = खालच्या degree चा नवा confirmed pivot. रिटर्न नवा pivot किंवा None."""
        if self.mode == UNDECIDED:
            if self.mx is None or q.price >= self.mx.price:
                self.mx = q
            if self.mn is None or q.price <= self.mn.price:
                self.mn = q
            down = self.mx.price - q.price >= theta
            up = q.price - self.mn.price >= theta
            if down and (not up or self.mx.known_at <= self.mn.known_at):
                p = self._confirm("H", self.mx, q, theta, sigma, session)
                self.mode, self.ext, self.rev = DOWN, (q if q.price <= self.mn.price else self.mn), None
                return p
            if up:
                p = self._confirm("L", self.mn, q, theta, sigma, session)
                self.mode, self.ext, self.rev = UP, (q if q.price >= self.mx.price else self.mx), None
                return p
            return None
        if self.mode == UP:
            if q.price >= self.ext.price:
                self.ext, self.rev = q, None
                return None
            fresh = self.rev is None or q.price < self.rev
            self.rev = q.price if self.rev is None else min(self.rev, q.price)
            if fresh and self.ext.price - q.price >= theta:
                p = self._confirm("H", self.ext, q, theta, sigma, session)
                self.mode, self.ext, self.rev = DOWN, q, None
                return p
            return None
        if q.price <= self.ext.price:
            self.ext, self.rev = q, None
            return None
        fresh = self.rev is None or q.price > self.rev
        self.rev = q.price if self.rev is None else max(self.rev, q.price)
        if fresh and q.price - self.ext.price >= theta:
            p = self._confirm("L", self.ext, q, theta, sigma, session)
            self.mode, self.ext, self.rev = UP, q, None
            return p
        return None
