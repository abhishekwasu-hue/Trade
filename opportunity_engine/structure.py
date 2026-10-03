"""opportunity_engine/structure.py — प्रत्येक TF साठी स्वतंत्र trend state machine (incremental, no-lookahead).

🎓 नियम (वापरकर्त्याने मंजूर केलेले, §0.1 / §2.3 / §6):
  • सर्व break फक्त **CLOSE** ने. wick पलीकडे जाऊन आत close = `SWEEP` event, state अबाधित.
  • Pivot `idx + right` bar नंतरच confirmed. swing significance = `k × ref_range`; सलग same-type swings मधला जास्त extreme ठेवतो.
  • UPTREND → protected_low (शेवटचा HL) खाली close ⇒ `UPTREND_WEAK` (event CHOCH).
  • UPTREND_WEAK:
      - `weak_low` = CHoCH bar पासूनचा सर्वात खालचा bar-low (spike असेल तर तिचा body-low).
      - पात्र LH = CHoCH नंतर confirmed swing high, किंमत `last_HH − 0.1×ref_range` पेक्षा खाली (EQH/वरचा LH नाही).
      - पात्र LH confirmed झाल्यानंतर प्रत्येक bar t वर `close_t < min(low[CHoCH..t−1])` ⇒ `DOWNTREND` + `REVERSAL_CONFIRMED`.
        LH च्या pivot-bar i आणि confirmation t=i+R मधला close आधीच खाली गेला असेल तर DOWN **confirmation bar t वर** नोंदवला जातो (`trigger_bar` वेगळं).
      - LH confirm होण्याआधी close < weak_low ⇒ फक्त weak_low खाली सरकतो, state WEAK.
      - close > last_HH ⇒ `UPTREND` (recovery).  N(=4) नवीन swings मध्ये काहीच नाही ⇒ `RANGE`.
  • DOWN बाजू आरशातली प्रतिमा: कोड एकाच `signed` पद्धतीत आहे (s = +1 UP, −1 DOWN; किंमत × s).
  • RANGE: कडेपलीकडे ≥ 0.1×ref_range close + एक confirmed higher-low / lower-high ⇒ UP/DOWN.
  • No-lookahead: bar t वरचा निर्णय फक्त bars[0..t] वर. spike ओळखायला 1–2 पुढचे bars लागतात, म्हणून spike चा body-edge त्या bars बंद झाल्यावरच
    (t ≥ k+2) लागू होतो; तोपर्यंत सामान्य wick (conservative).
कुठलाही indicator नाही. `ref_range` फक्त `k × ref_range` या स्वरूपात.
"""
from dataclasses import dataclass

import numpy as np

from .config import EngineConfig
from .measures import ref_range_from_ranges

INIT, RANGE = "INIT", "RANGE"
UP, UP_PB, UP_WEAK = "UPTREND", "UPTREND_PULLBACK", "UPTREND_WEAK"
DN, DN_PB, DN_WEAK = "DOWNTREND", "DOWNTREND_PULLBACK", "DOWNTREND_WEAK"
STATES = (INIT, RANGE, UP, UP_PB, UP_WEAK, DN, DN_PB, DN_WEAK)
_STATE_OF = {1: (UP, UP_PB, UP_WEAK), -1: (DN, DN_PB, DN_WEAK)}


@dataclass
class Swing:
    kind: str            # "H" / "L"
    idx: int             # swing bar चा index
    time: object         # swing bar चा bar_end
    price: float         # (spike असेल तर body-edge)
    confirmed_idx: int
    confirmed_time: object
    label: str = ""      # HH/LH/EQH (kind H) किंवा HL/LL/EQL (kind L)
    spike: bool = False


class _Neg:
    """−x चा read-only view (यादीची प्रत न करता): s=−1 साठी signed lows. index आणि slice दोन्ही चालतात."""
    __slots__ = ("_a",)

    def __init__(self, a):
        self._a = a

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [-x for x in self._a[i]]
        return -self._a[i]


class StructureTracker:
    """एका TF चा incremental structure tracker. `on_bar()` प्रत्येक closed bar ला (bar_end ≤ t) एकदाच बोलवा."""

    def __init__(self, tf, cfg=None):
        self.tf = tf
        self.cfg = cfg or EngineConfig()
        self.R = int(self.cfg.pivot_n.get(tf, 3))
        self.k = float(self.cfg.swing_k.get(tf, 1.5))
        self.o, self.h, self.l, self.c, self.bar_end, self.full = [], [], [], [], [], []
        self.eff_lo, self.eff_hi = [], []        # spike body-edge सह (मंजूर केलेले ones फक्त resolve झाल्यावर)
        self._ranges = []
        self.rr = float("nan")
        self.rr_hist = []                        # प्रत्येक bar वरची ref_range (zones/level_quality मोजपट्टी म्हणून `k × rr_hist[i]`)
        self.swings = []
        self._swept = set()
        self.state = INIT
        self.s = 0                               # trend दिशा (+1/−1) UP/DOWN states साठी
        self.prot = None                         # protected level (signed किंमत)
        self.ext = None                          # trend extreme (signed running max of signed-high)
        self.last_sh = None                      # (signed price, swing idx) — शेवटचा "high" swing (trend दिशेने)
        self.last_sh_broken = False
        self.range_hi = self.range_lo = None
        # WEAK टप्प्याचे चल
        self.choch_idx = None
        self.weak_ext = None
        self.weak_min_settled = None             # signed-low चा settled min (bars choch..t−3)
        self.lh = None                           # पात्र LH (Swing)
        self.weak_swing_count = 0
        self.events = []
        self.changes = []                        # state बदलांचा इतिहास

    # ------------------------------------------------------------------ मदतनीस
    def _signed_bar(self, i, s):
        if s > 0:
            return self.o[i], self.h[i], self.l[i], self.c[i]
        return -self.o[i], -self.l[i], -self.h[i], -self.c[i]

    def _tol(self, mult):
        return mult * self.rr

    def _emit(self, t, etype, price, **details):
        ev = {"tf": self.tf, "bar_idx": t, "time": self.bar_end[t], "type": etype, "price": None if price is None else float(price),
              "state": self.state, **details}
        self.events.append(ev)
        return ev

    def _set_state(self, t, new_state, etype, price, **details):
        old = self.state
        self.state = new_state
        ev = self._emit(t, etype, price, from_state=old, to_state=new_state, **details)
        if old != new_state:
            self.changes.append({"tf": self.tf, "time": self.bar_end[t], "bar_idx": t, "from_state": old, "state": new_state, "event": etype,
                                 "price": None if price is None else float(price), "protected": self.protected_level(),
                                 "trigger_bar": details.get("trigger_bar", self.bar_end[t])})
        return ev

    def protected_level(self):
        if self.prot is None or self.s == 0 or self.state not in _STATE_OF[self.s]:
            return None
        return float(self.prot * self.s)

    # ------------------------------------------------------------------ spike
    def _spike_kind(self, k, upto):
        """bar k spike आहे का? 'UP' (वरची wick), 'DOWN' (खालची) किंवा None. bars k+1..upto (≤ k+spike_return_bars) च्या closes वापरतो — पुढचे bars
        उपलब्ध नसतील तर None. 🎓 spec: wick ≥ 2.5×ref_range, body ≤ 30% range, पुढच्या 1–2 bars मध्ये किंमत wick च्या मुळाशी परत."""
        cfg = self.cfg
        if not np.isfinite(self.rr) or self.rr <= 0:
            return None
        rng = self.h[k] - self.l[k]
        if rng <= 0:
            return None
        body_hi, body_lo = max(self.o[k], self.c[k]), min(self.o[k], self.c[k])
        if (body_hi - body_lo) > cfg.spike_body_max * rng:
            return None
        window = range(k + 1, min(k + int(cfg.spike_return_bars), upto) + 1)
        if (self.l[k] <= body_lo - cfg.spike_wick_k * self.rr) and (body_lo - self.l[k]) >= (self.h[k] - body_hi):
            if any(self.c[j] >= body_lo for j in window):
                return "DOWN"
        if (self.h[k] >= body_hi + cfg.spike_wick_k * self.rr) and (self.h[k] - body_hi) > (body_lo - self.l[k]):
            if any(self.c[j] <= body_hi for j in window):
                return "UP"
        return None

    def _settle_spikes(self, t):
        """bar t−spike_return_bars (आता पूर्ण resolve झालेला) चा effective high/low निश्चित करा."""
        k = t - int(self.cfg.spike_return_bars)
        if k < 0 or not self.cfg.spike_body_edge:
            return
        kind = self._spike_kind(k, t)
        if kind == "DOWN":
            self.eff_lo[k] = min(self.o[k], self.c[k])
        elif kind == "UP":
            self.eff_hi[k] = max(self.o[k], self.c[k])

    # ------------------------------------------------------------------ swings
    def _is_pivot(self, p, kind):
        R = self.R
        if p < R:
            return False
        if kind == "H":
            left, right = self.h[p - R:p], self.h[p + 1:p + R + 1]
            return self.h[p] >= max(left) and self.h[p] > max(right)
        left, right = self.l[p - R:p], self.l[p + 1:p + R + 1]
        return self.l[p] <= min(left) and self.l[p] < min(right)

    def _pivot_price(self, p, kind, t):
        """swing किंमत. spike असेल तर body-edge (spec §2.6, config)."""
        if self.cfg.spike_body_edge:
            sk = self._spike_kind(p, t)
            if kind == "H" and sk == "UP":
                return max(self.o[p], self.c[p]), True
            if kind == "L" and sk == "DOWN":
                return min(self.o[p], self.c[p]), True
        return (self.h[p] if kind == "H" else self.l[p]), False

    def _label(self, kind, price, upto_swings):
        prev = next((sw for sw in reversed(upto_swings) if sw.kind == kind), None)
        if prev is None:
            return ""
        tol = self._tol(self.cfg.eq_tol)
        if abs(price - prev.price) <= tol:
            return "EQH" if kind == "H" else "EQL"
        if kind == "H":
            return "HH" if price > prev.price else "LH"
        return "HL" if price > prev.price else "LL"

    def _add_pivot(self, p, kind, t):
        """नवीन confirmed pivot ला swings यादीत घाला (significance + alternation). रिटर्न: ("added"|"replaced"|"ignored", Swing|None)."""
        price, spike = self._pivot_price(p, kind, t)
        last = self.swings[-1] if self.swings else None
        if last is not None and last.kind == kind:
            better = price > last.price if kind == "H" else price < last.price
            if not better:
                return "ignored", None
            self.swings.pop()
            sw = Swing(kind, p, self.bar_end[p], price, t, self.bar_end[t], "", spike)
            sw.label = self._label(kind, price, self.swings)
            self.swings.append(sw)
            return "replaced", sw
        if last is not None and abs(price - last.price) < self.k * self.rr:
            return "ignored", None
        sw = Swing(kind, p, self.bar_end[p], price, t, self.bar_end[t], "", spike)
        sw.label = self._label(kind, price, self.swings)
        self.swings.append(sw)
        return "added", sw

    # ------------------------------------------------------------------ मुख्य
    def on_bar(self, bar_end, o, h, l, c, full=True):
        """एक closed bar. रिटर्न: या bar वर झालेले events (यादी)."""
        t = len(self.c)
        self.o.append(float(o)); self.h.append(float(h)); self.l.append(float(l)); self.c.append(float(c))
        self.eff_lo.append(float(l)); self.eff_hi.append(float(h))
        self.bar_end.append(bar_end); self.full.append(bool(full))
        if full:
            self._ranges.append(float(h) - float(l))
        self.rr = ref_range_from_ranges(self._ranges, self.cfg.ref_range_bars, self.cfg.ref_range_min_bars)
        self.rr_hist.append(self.rr)
        n_before = len(self.events)
        if not np.isfinite(self.rr) or self.rr <= 0:
            return []
        self._settle_spikes(t)

        new_swings = []
        for kind in ("H", "L"):
            p = t - self.R
            if p >= self.R and self._is_pivot(p, kind):
                status, sw = self._add_pivot(p, kind, t)
                if sw is not None:
                    new_swings.append((status, sw))
                    self._emit(t, "SWING", sw.price, kind=kind, label=sw.label, swing_idx=p, swing_time=sw.time, status=status, spike=sw.spike)

        self._step(t, new_swings)
        self._detect_sweeps(t)
        return self.events[n_before:]

    # ------------------------------------------------------------------ state step
    def _step(self, t, new_swings):
        if self.state == INIT:
            self._try_init(t)
            return
        if self.state == RANGE:
            self._step_range(t, new_swings)
            return
        s = self.s
        # trend extreme: running max of signed-high
        ext_candidate = self._signed_bar(t, s)[1]
        o_s, h_s, l_s, c_s = self._signed_bar(t, s)
        sh_kind, sl_kind = ("H", "L") if s > 0 else ("L", "H")

        base, pb, weak = _STATE_OF[s]
        if self.state in (base, pb):
            prev_ext = self.ext
            self.ext = max(self.ext, ext_candidate)
            for _status, sw in new_swings:
                sp = sw.price * s
                if sw.kind == sh_kind:
                    self.last_sh, self.last_sh_broken = (sp, sw.idx), False
                elif sp > self.prot - self._tol(self.cfg.eq_tol):
                    self.prot = sp                                    # HL (किंवा EQL) = नवीन protected
            if c_s < self.prot:
                self.weak_ext = self.ext
                self.choch_idx = t
                self.lh = None
                self.weak_swing_count = 0
                self.weak_min_settled = None
                self._set_state(t, weak, "CHOCH", self.prot * s, protected_broken=self.prot * s)
                self._weak_bookkeeping(t, s)
                return
            if self.last_sh is not None and not self.last_sh_broken and c_s > self.last_sh[0]:
                self.last_sh_broken = True
                self._set_state(t, base, "BOS", self.last_sh[0] * s, broke_swing_idx=self.last_sh[1])
            elif self.state == pb and c_s > prev_ext:
                self._set_state(t, base, "PULLBACK_END", c_s * s)             # नवीन extreme वर close — pullback संपला
            elif self.state == base and c_s < self.ext - self._tol(self.cfg.pullback_k):
                self._set_state(t, pb, "PULLBACK_START", c_s * s)
            return
        self._step_weak(t, s, new_swings)

    # --- WEAK
    def _weak_lows(self, s):
        """signed effective low (spike body-edge सह). s=−1 साठी −eff_hi (लहान view; मोठ्या यादीची प्रत टाळण्यासाठी _WeakView)."""
        return self.eff_lo if s > 0 else _Neg(self.eff_hi)

    def _weak_bookkeeping(self, t, s):
        """bar t−spike_return_bars (आता settled) चा effective low CHoCH पासूनच्या settled min मध्ये मिसळा (O(1))."""
        k = t - int(self.cfg.spike_return_bars)
        if k >= self.choch_idx:
            v = self._weak_lows(s)[k]
            self.weak_min_settled = v if self.weak_min_settled is None else min(self.weak_min_settled, v)

    def _min_low_before(self, t, s, upto):
        """min(signed low[CHoCH..upto]) — settled भाग + अजून resolve न झालेल्या bars चे raw lows."""
        lows = self._weak_lows(s)
        settle_to = t - int(self.cfg.spike_return_bars)
        start = self.choch_idx
        parts = []
        if self.weak_min_settled is not None and settle_to >= start:
            parts.append(self.weak_min_settled)
        pending_from = max(start, settle_to + 1)
        if upto >= pending_from:
            parts.extend(lows[pending_from:upto + 1])
        return min(parts) if parts else None

    def _step_weak(self, t, s, new_swings):
        cfg = self.cfg
        _o, h_s, l_s, c_s = self._signed_bar(t, s)
        base, pb, weak = _STATE_OF[s]
        sh_kind = "H" if s > 0 else "L"
        self._weak_bookkeeping(t, s)
        # recovery
        if c_s > self.weak_ext:
            self.ext = max(self.weak_ext, h_s)
            floor = self._min_low_before(t, s, t)
            # protected = CHoCH नंतरचा सर्वात खालचा (HL म्हणून) — नवीन HL swings नंतर अद्ययावत होतील
            self.prot = floor if floor is not None else self.prot
            self.last_sh, self.last_sh_broken = (self.weak_ext, -1), True
            self._set_state(t, base, "RECOVERY", c_s * s, recovered_above=self.weak_ext * s)
            return
        for _status, sw in new_swings:
            if sw.idx <= self.choch_idx:
                continue
            self.weak_swing_count += 1
            if sw.kind == sh_kind and sw.price * s < self.weak_ext - self._tol(cfg.lh_tol):
                self.lh = sw
                catch = self._catch_up_down(t, s, sw)
                if catch is not None:
                    self._to_opposite(t, s, trigger_k=catch)
                    return
        # LH confirmed असेल तर ट्रिगर: close_t < min(low[CHoCH..t−1])
        if self.lh is not None and t > self.choch_idx:
            m = self._min_low_before(t, s, t - 1)
            if m is not None and c_s < m:
                self._to_opposite(t, s, trigger_k=t)
                return
        if self.weak_swing_count >= cfg.weak_to_range_swings:
            recent = self.swings[-cfg.init_swings:]
            self.range_hi = max(sw.price for sw in recent)
            self.range_lo = min(sw.price for sw in recent)
            self._set_state(t, RANGE, "RANGE_START", self.c[t], range_high=self.range_hi, range_low=self.range_lo)
            self.s, self.prot, self.ext = 0, None, None

    def _catch_up_down(self, t, s, lh_swing):
        """LH च्या pivot-bar i आणि confirmation t मधला close आधीच min(low[CHoCH..k−1]) खाली गेला असेल तर पहिला असा k (≤ t), नाहीतर None.
        भविष्यातलं काहीही नाही — k ≤ t."""
        lows = self._weak_lows(s)
        for k in range(lh_swing.idx + 1, t + 1):
            floor = min(lows[self.choch_idx:k]) if k > self.choch_idx else None
            if floor is not None and self._signed_bar(k, s)[3] < floor:
                return k
        return None

    def _to_opposite(self, t, s, trigger_k):
        """Reversal confirmed: UP_WEAK → DOWNTREND (किंवा आरशातली). event time = t (confirmation bar); trigger_bar वेगळं नोंदवा."""
        lows = self._weak_lows(s)
        floor = min(lows[self.choch_idx:max(trigger_k, self.choch_idx + 1)])      # तुटलेला weak_low (signed, s च्या space मध्ये)
        ns = -s
        lh_price = self.lh.price
        self.s = ns
        self.prot = lh_price * ns
        # नवीन दिशेचा running extreme (signed' high): CHoCH नंतरचा सर्वात टोकाचा + trigger नंतरचे bars
        self.ext = max([-floor] + [self._signed_bar(i, ns)[1] for i in range(trigger_k, t + 1)])
        old_swing_kind = "L" if s > 0 else "H"                  # नवीन दिशेचा "high-swing" = जुन्या दिशेचा low-swing
        last = next((sw for sw in reversed(self.swings) if sw.kind == old_swing_kind), None)
        if last is None:
            self.last_sh, self.last_sh_broken = None, True
        else:
            self.last_sh = (last.price * ns, last.idx)
            self.last_sh_broken = self._signed_bar(t, ns)[3] > self.last_sh[0]
        self.lh = None
        self.weak_ext = None
        self.choch_idx = None
        self._set_state(t, _STATE_OF[ns][0], "REVERSAL_CONFIRMED", floor * s,
                        trigger_bar=self.bar_end[trigger_k], trigger_idx=trigger_k, lh_price=lh_price)

    # --- INIT / RANGE
    def _try_init(self, t):
        n = self.cfg.init_swings
        if len(self.swings) < n:
            return
        recent = self.swings[-n:]
        highs = [sw for sw in recent if sw.kind == "H"]
        lows = [sw for sw in recent if sw.kind == "L"]
        if len(highs) < 2 or len(lows) < 2:
            return
        tol = self._tol(self.cfg.eq_tol)
        up = highs[-1].price > highs[-2].price + tol and lows[-1].price > lows[-2].price + tol
        down = highs[-1].price < highs[-2].price - tol and lows[-1].price < lows[-2].price - tol
        if up or down:
            s = 1 if up else -1
            self.s = s
            self.prot = (lows[-1].price if s > 0 else highs[-1].price) * s
            hi_kind = "H" if s > 0 else "L"
            tops = [sw for sw in recent if sw.kind == hi_kind]
            self.ext = max(self._signed_bar(i, s)[1] for i in range(tops[-1].idx, t + 1))
            self.last_sh, self.last_sh_broken = (tops[-1].price * s, tops[-1].idx), False
            self._set_state(t, _STATE_OF[s][0], "INIT_TREND", self.c[t])
        else:
            self.range_hi = max(sw.price for sw in recent)
            self.range_lo = min(sw.price for sw in recent)
            self._set_state(t, RANGE, "INIT_RANGE", self.c[t], range_high=self.range_hi, range_low=self.range_lo)

    def _step_range(self, t, new_swings):
        cfg = self.cfg
        for _status, sw in new_swings:
            recent = self.swings[-cfg.init_swings:]
            self.range_hi = max(x.price for x in recent)
            self.range_lo = min(x.price for x in recent)
        tol = self._tol(cfg.range_exit_k)
        close = self.c[t]
        lows = [sw for sw in self.swings if sw.kind == "L"]
        highs = [sw for sw in self.swings if sw.kind == "H"]
        if close > self.range_hi + tol and len(lows) >= 2 and lows[-1].price > lows[-2].price:
            self._enter_trend(t, 1, lows[-1].price, "RANGE_EXIT_UP")
        elif close < self.range_lo - tol and len(highs) >= 2 and highs[-1].price < highs[-2].price:
            self._enter_trend(t, -1, highs[-1].price, "RANGE_EXIT_DOWN")

    def _enter_trend(self, t, s, prot_price, etype):
        self.s = s
        self.prot = prot_price * s
        self.ext = self._signed_bar(t, s)[1]
        hi_kind = "H" if s > 0 else "L"
        last = next((sw for sw in reversed(self.swings) if sw.kind == hi_kind), None)
        self.last_sh = (last.price * s, last.idx) if last else None
        self.last_sh_broken = True
        self._set_state(t, _STATE_OF[s][0], etype, self.c[t])

    # --- SWEEP
    def _detect_sweeps(self, t):
        """wick ने confirmed swing पलीकडे जाऊन आत close = liquidity sweep (state बदलत नाही). प्रत्येक swing + बाजू साठी एकदाच."""
        if len(self.swings) < 2:
            return
        for sw in self.swings[-4:]:
            key = (sw.idx, sw.kind)
            if key in self._swept or t <= sw.confirmed_idx:
                continue
            if sw.kind == "H" and self.h[t] > sw.price and self.c[t] <= sw.price:
                self._swept.add(key)
                self._emit(t, "SWEEP", sw.price, side="HIGH", swing_idx=sw.idx)
            elif sw.kind == "L" and self.l[t] < sw.price and self.c[t] >= sw.price:
                self._swept.add(key)
                self._emit(t, "SWEEP", sw.price, side="LOW", swing_idx=sw.idx)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self):
        sw_h = next((sw for sw in reversed(self.swings) if sw.kind == "H"), None)
        sw_l = next((sw for sw in reversed(self.swings) if sw.kind == "L"), None)
        return {
            "tf": self.tf, "trend_state": self.state, "protected_level": self.protected_level(),
            "last_sh": None if sw_h is None else sw_h.price, "last_sl": None if sw_l is None else sw_l.price,
            "range_high": self.range_hi if self.state == RANGE else None, "range_low": self.range_lo if self.state == RANGE else None,
            "ref_range": None if not np.isfinite(self.rr) else self.rr,
            "updated_at": self.bar_end[-1] if self.bar_end else None, "bars": len(self.c),
        }
