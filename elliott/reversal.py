"""
elliott/reversal.py — E2: composite "logical reversal" (spec §6 T1–T4, §14 Q2) — entry trigger आणि failed-retest break दोघांसाठी
--------------------------------------------------------------------------------------------------------------------------
🎓 शेवटच्या N = 1…touch_reclaim_window बंद candles चा composite (पहिल्याचा open, max high, min low, शेवटच्याचा close) —
hammer (1), engulfing (2), star (3) यांचं एकच logic: "ढकललं गेलं, आणि दुसऱ्या बाजूने ताबा घेतला".
Bullish (dirn = +1; bearish = mirror: किंमत उलटी करून तेच नियम):
  touch     composite.low ≤ zone_hi                         (zone_hi = सर्वात उथळ level + tol)
  inv       composite.low > inv, आणि window मधला एकही close inv च्या पलीकडे नाही
  touched   शिवलेल्या levels पैकी **सर्वात खोल** (composite.low ≤ L + tol) — §10 उदाहरण: B low 22,396, reclaim close ~22,410
            ⇒ 0.618 level (22,371) हाच "शिवलेला"; सर्वात उथळ level (0.382 = 22,467) वर close मागणं T7 शी विसंगत. (WORK_LOG)
  reclaim   composite.close > touched (reclaim_ref = touched_level) किंवा > सर्वात उथळ level (zone_high)
  last      N ≥ 2 ⇒ शेवटची candle trade दिशेने बंद
  strength  strength_min ≤ range / MR ≤ strength_max   (MR = window आधीच्या median_range_n बंद bars चा median)
  indecision close-location 0.40–0.60 ⇒ नाही; पुढची candle दिशेने बंद झाली तर N+1 (कमाल window+1)
  score     Σ w·x / Σ w (उपलब्ध घटकांवर): wick (min(o,c)−l)/rng, close-loc (c−l)/rng, body |c−o|/rng·[c>o],
            time [bars_to_reclaim ≤ bars_last_subleg], div [RSI divergence]  ≥ rejection_min
फक्त bars ≤ j वापरतो ⇒ causal. price_action/candles.py (MCX) ला हात लावलेला नाही — तिथले weights/score वेगळे (0–100) आहेत.
"""
import numpy as np

INDECISION = (0.40, 0.60)

# कारणे — "सर्वात जवळची" अपयशी window निवडण्याचा क्रम
NO_DATA, NO_TOUCH, INV, NO_RECLAIM, LAST_AGAINST = "no_data", "no_touch", "beyond_inv", "no_reclaim", "last_against"
WEAK, EXHAUSTION, INDECISIVE, LOW_SCORE = "weak", "exhaustion", "indecision", "low_score"
_STAGE = {NO_DATA: -1, NO_TOUCH: 0, INV: 1, NO_RECLAIM: 2, LAST_AGAINST: 3, WEAK: 4, EXHAUSTION: 4, INDECISIVE: 5, LOW_SCORE: 6}


class Bars:
    """एका TF frame चे numpy arrays (एकदाच) + median range."""

    def __init__(self, frame, mr):
        self.frame = frame
        self.o, self.h, self.l, self.c = (frame[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.mr = mr
        self.n = len(self.c)


def _window(b, a, j, dirn):
    """bars a..j चा composite, dirn नुसार mirror केलेला (bearish ⇒ −किंमत, high↔low)."""
    if dirn > 0:
        return b.o[a], b.h[a:j + 1].max(), b.l[a:j + 1].min(), b.c[j], b.c[a:j + 1]
    return -b.o[a], -b.l[a:j + 1].min(), -b.h[a:j + 1].max(), -b.c[j], -b.c[a:j + 1]


def evaluate_window(b, j, n, dirn, levels, tol, s, inv=None, min_start=0, extreme_idx=None, bars_last_subleg=None,
                    div_ok=None, reclaim_ref="touched_level"):
    """Window = bars [j−n+1, j]. levels = zone levels (किंमत); inv = hard invalidation (किंवा None).
    रिटर्न dict: ok, reason, n, score, touched, comp (o,h,l,c — खरी किंमत), close_loc, rng_ratio."""
    out = {"ok": False, "reason": NO_DATA, "n": n, "score": 0.0, "touched": None, "comp": None, "close_loc": None, "rng_ratio": None}
    a = j - n + 1
    if a < max(min_start, 0) or j >= b.n or not levels:
        return out
    m = b.mr[a]
    if not np.isfinite(m) or m <= 0:
        return out
    o, h, l, c, closes = _window(b, a, j, dirn)
    out["comp"] = (float(b.o[a]), float(b.h[a:j + 1].max()), float(b.l[a:j + 1].min()), float(b.c[j]))
    lv = sorted(dirn * float(x) for x in levels)                     # mirror ⇒ नेहमी "खालचा" touch
    rng = h - l
    out["close_loc"] = (c - l) / rng if rng > 0 else 0.0
    out["rng_ratio"] = rng / m
    if not l <= lv[-1] + tol:
        out["reason"] = NO_TOUCH
        return out
    if inv is not None:
        iv = dirn * float(inv)
        if not l > iv or (closes <= iv).any():
            out["reason"] = INV
            return out
    touched = next(x for x in lv if l <= x + tol)                    # सर्वात खोल शिवलेला level
    out["touched"] = dirn * touched
    ref = touched if reclaim_ref == "touched_level" else lv[-1]
    if not c > ref:
        out["reason"] = NO_RECLAIM
        return out
    if n >= 2:
        last_o, last_c = (b.o[j], b.c[j]) if dirn > 0 else (-b.o[j], -b.c[j])
        if not last_c > last_o:
            out["reason"] = LAST_AGAINST
            return out
    if rng < s["strength_min"] * m:
        out["reason"] = WEAK
        return out
    if rng > s["strength_max"] * m:
        out["reason"] = EXHAUSTION
        return out
    w = s["rejection_weights"]
    comps = [(w[0], (min(o, c) - l) / rng), (w[1], (c - l) / rng), (w[2], abs(c - o) / rng * (c > o))]
    if extreme_idx is not None and bars_last_subleg is not None:
        comps.append((w[3], float(j - extreme_idx <= bars_last_subleg)))
    if div_ok is not None:
        comps.append((w[4], float(div_ok)))
    tw = sum(x for x, _ in comps)
    out["score"] = sum(x * v for x, v in comps) / tw if tw > 0 else 0.0
    if INDECISION[0] <= out["close_loc"] <= INDECISION[1]:
        out["reason"] = INDECISIVE
        return out
    if out["score"] < s["rejection_min"]:
        out["reason"] = LOW_SCORE
        return out
    out.update(ok=True, reason=None)
    return out


def evaluate(b, j, dirn, levels, tol, s, **kw):
    """N = 1…touch_reclaim_window (+ indecision follow-through) — पास झालेल्यांपैकी सर्वोच्च score (समान ⇒ लहान N);
    नाहीतर "सर्वात जवळची" अपयशी window. Window नेहमी bar j वर संपते."""
    nmax = s["touch_reclaim_window"]
    res = [evaluate_window(b, j, n, dirn, levels, tol, s, **kw) for n in range(1, nmax + 1)]
    prev = evaluate_window(b, j - 1, nmax, dirn, levels, tol, s, **kw) if j >= 1 else None
    if prev is not None and prev["reason"] == INDECISIVE and j < b.n and dirn * (b.c[j] - b.o[j]) > 0:
        res.append(evaluate_window(b, j, nmax + 1, dirn, levels, tol, s, **kw))
    ok = [r for r in res if r["ok"]]
    if ok:
        return max(ok, key=lambda r: (r["score"], -r["n"]))
    return max(res, key=lambda r: (_STAGE.get(r["reason"], -1), r["score"], -r["n"]))


def retest_fn(frame, s, mr):
    """breaks.first_real_break साठी (c) failed-retest hook. Break candidate t (side "below") नंतर reclaim झाला; मग window
    (t+1 … t+1+touch_reclaim_window) मध्ये level L ला **उलट बाजूने** (खालून) logical reversal ने नाकारलं ⇒ त्या bar वर confirm.
    Window चे सगळे candles t नंतरचे (breaking candle composite मध्ये नाही); composite level च्या **तुटलेल्या बाजूने** सुरू
    (पहिला open L पलीकडे) आणि नकाराचा close L ∓ buffer पलीकडे — म्हणजे भाव खरंच खालून L ला लागून परत फेकला गेला.
    Time/div घटक नाहीत (score उरलेल्या weights वर)."""
    b = Bars(frame, mr)

    def fn(_frame, t, level, side, end):
        dirn = -1 if side == "below" else 1                          # below-break ⇒ retest खालून ⇒ bearish rejection
        tol = s["break_buffer_mr"] * (mr[t] if np.isfinite(mr[t]) else 0.0)
        last = min(end, t + 1 + s["touch_reclaim_window"])
        for j in range(t + 1, last + 1):
            beyond = b.c[j] < level - tol if side == "below" else b.c[j] > level + tol   # नकाराचा close buffer पलीकडे
            if not beyond:
                continue
            for n in range(1, min(s["touch_reclaim_window"], j - t) + 1):
                a = j - n + 1
                started = b.o[a] < level if side == "below" else b.o[a] > level         # composite तुटलेल्या बाजूने सुरू
                if started and evaluate_window(b, j, n, dirn, [level], tol, s, min_start=t + 1)["ok"]:
                    return j
        return None
    return fn
