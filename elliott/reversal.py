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
PATH, NO_BODY = "path_retrace", "no_body"
_STAGE = {NO_DATA: -1, NO_TOUCH: 0, INV: 1, NO_RECLAIM: 2, LAST_AGAINST: 3, PATH: 3, WEAK: 4, EXHAUSTION: 4, NO_BODY: 4,
          INDECISIVE: 5, LOW_SCORE: 6}


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


def _label(n, o, h, l, c, fo, fc, mo, mc, dirn):
    """Blended classic नाव — **फक्त log/अहवाल**, निर्णयात वापर नाही (addendum §3.8). Mirror केलेल्या (bullish) किमतींवर.
    fo/fc = पहिली candle, mo/mc = दुसरी (N=2) / मधली (N=3)."""
    rng = h - l
    if rng <= 0:
        return "other"
    wick, cl, body = (min(o, c) - l) / rng, (c - l) / rng, abs(c - o) / rng
    bull = dirn > 0
    if n == 1:
        if wick >= 0.5 and cl >= 0.6:
            return "hammer-like" if bull else "shooting-star-like"
        if body >= 0.6 and cl >= 0.8:
            return "marubozu-like"
        return "other"
    lo1, hi1 = min(fo, fc), max(fo, fc)
    if n == 2:
        if fc < fo and mo <= fc + 1e-12 and mc >= fo:
            return "engulfing-like"
        if fc < fo and hi1 > lo1 and lo1 + 0.5 * (hi1 - lo1) <= c <= hi1:
            return "piercing-like" if bull else "dark-cloud-like"
        return "other"
    if fc < fo and abs(mc - mo) <= 0.3 * max(hi1 - lo1, 1e-12) and c >= lo1 + 0.5 * (hi1 - lo1):
        return "star-like"
    return "other"


def evaluate_window(b, j, n, dirn, levels, tol, s, inv=None, min_start=0, extreme_idx=None, bars_last_subleg=None,
                    div_ok=None, reclaim_ref="touched_level", mr_override=None, rmin=None, soft=False):
    """Window = bars [j−n+1, j]. levels = zone levels (किंमत); inv = hard invalidation (किंवा None).
    mr_override = strength संदर्भ (own_correction / time_slot — C1); rmin = rejection_min (profile). दोन्ही None ⇒ सध्याचं वर्तन.
    soft = True (Chart Reader, 2026-10-08): touch / inv / reclaim / indecision पक्के; बाकी (last_against, path, weak, exhaustion,
    no_body, low_score) निर्णय नाही — `flags` मध्ये नोंद आणि score तरीही मोजतो. Default False ⇒ Elliott चं वर्तन तसंच.
    रिटर्न dict: ok, reason, n, score, touched, comp (o,h,l,c — खरी किंमत), close_loc, rng_ratio, parts, label, flags."""
    out = {"ok": False, "reason": NO_DATA, "n": n, "score": 0.0, "touched": None, "comp": None, "close_loc": None, "rng_ratio": None,
           "parts": {}, "label": None, "flags": []}
    flags = out["flags"]
    a = j - n + 1
    if a < max(min_start, 0) or j >= b.n or not levels:
        return out
    m = b.mr[a] if mr_override is None else (mr_override(a) if callable(mr_override) else mr_override)
    if m is None:
        m = b.mr[a]
    if not np.isfinite(m) or m <= 0:
        return out
    o, h, l, c, closes = _window(b, a, j, dirn)
    out["comp"] = (float(b.o[a]), float(b.h[a:j + 1].max()), float(b.l[a:j + 1].min()), float(b.c[j]))
    lv = sorted(dirn * float(x) for x in levels)                     # mirror ⇒ नेहमी "खालचा" touch
    rng = h - l
    out["close_loc"] = (c - l) / rng if rng > 0 else 0.0
    out["rng_ratio"] = rng / m
    fo, fc = (b.o[a], b.c[a]) if dirn > 0 else (-b.o[a], -b.c[a])                # पहिली candle (mirror)
    mo, mc = ((b.o[a + 1], b.c[a + 1]) if dirn > 0 else (-b.o[a + 1], -b.c[a + 1])) if n >= 2 else (fo, fc)   # दुसरी candle
    out["label"] = _label(n, o, h, l, c, fo, fc, mo, mc, dirn)
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
            if not soft:
                out["reason"] = LAST_AGAINST
                return out
            flags.append("last_against")
        if s.get("path_checks"):                                     # शेवटच्या candle ने स्वतः किती परत दिलं (त्याचा high / आधीचा close पासून)
            last_h, prev_c = (b.h[j], b.c[j - 1]) if dirn > 0 else (-b.l[j], -b.c[j - 1])
            if (max(last_h, prev_c) - c) / rng > 0.5:
                if not soft:
                    out["reason"] = PATH
                    return out
                flags.append("path_retrace")
    if rng < s["strength_min"] * m:
        if not soft:
            out["reason"] = WEAK
            return out
        flags.append("weak")
    if rng > s["strength_max"] * m:
        if soft:
            flags.append("climax" if out["close_loc"] < 0.6 else "wide_reclaim")
        elif s.get("strength_cap_mode", "fixed") == "fixed" or out["close_loc"] < 0.6:
            out["reason"] = EXHAUSTION                                   # logic: pullback दिशेने close (climax extension)
            return out
        else:
            guard = s.get("strength_risk_guard_mult", 0.0)
            if guard > 0 and rng > guard * m:
                out["reason"] = EXHAUSTION                               # logic mode मधला पर्यायी risk guard
                return out
    w = s["rejection_weights"]
    body_bull = abs(c - o) / rng * (c > o)
    hi1, lo1 = max(fo, fc), min(fo, fc)
    depth = float(np.clip((c - lo1) / (hi1 - lo1), 0.0, 1.0)) if n >= 2 and hi1 > lo1 and fc < fo else 0.0
    body_v = body_bull
    if s.get("body_term_mode", "bull_body") == "body_or_reclaim" and depth >= 0.5:
        body_v = max(body_bull, depth)
    if s.get("min_body_or_reclaim") and (c - o) / rng < s.get("min_body_frac", MIN_BODY) and depth < 0.5:     # trade दिशेची body (mirror)
        if not soft:
            out["reason"] = NO_BODY
            return out
        flags.append("no_body")
    comps = [("wick", w[0], (min(o, c) - l) / rng), ("close_loc", w[1], (c - l) / rng), ("body", w[2], body_v)]
    if extreme_idx is not None and bars_last_subleg is not None:
        comps.append(("time", w[3], float(j - extreme_idx <= bars_last_subleg)))
    if div_ok is not None:
        comps.append(("div", w[4], float(div_ok)))
    if s.get("w_reclaim_depth", 0.0) > 0:
        rec, stab = float(np.clip((c - touched) / m, 0.0, 1.0)), float(np.clip((touched - l) / m, 0.0, 1.0))
        comps.append(("reclaim_depth", s["w_reclaim_depth"], 0.5 * (rec + stab)))   # level पलीकडे stab + आत close (× median)
    if s.get("w_overlap", 0.0) > 0:
        p0 = max(a - 3, 0)
        if p0 < a:
            ph, pl = (b.h[p0:a].max(), b.l[p0:a].min()) if dirn > 0 else (-b.l[p0:a].min(), -b.h[p0:a].max())
            ov = max(0.0, min(h, ph) - max(l, pl)) / rng
            comps.append(("low_overlap", s["w_overlap"], 1.0 - min(ov, 1.0)))
    tw = sum(x for _, x, _ in comps)
    out["score"] = sum(x * v for _, x, v in comps) / tw if tw > 0 else 0.0
    if n >= 3 and s.get("n3_penalty", 0.0) > 0:
        out["score"] -= s["n3_penalty"]
    out["parts"] = {k: round(float(v), 4) for k, _, v in comps}
    band = s.get("indecision_band", INDECISION)
    if band[0] <= out["close_loc"] <= band[1]:
        out["reason"] = INDECISIVE
        return out
    if not soft and out["score"] < (s["rejection_min"] if rmin is None else rmin):
        out["reason"] = LOW_SCORE
        return out
    out.update(ok=True, reason=None)
    return out


MIN_BODY = 0.10                                                      # min_body_or_reclaim: trade दिशेची body / range


def evaluate(b, j, dirn, levels, tol, s, **kw):
    """N = 1…touch_reclaim_window (+ indecision follow-through) — पास झालेल्यांपैकी सर्वोच्च score (समान ⇒ लहान N);
    नाहीतर "सर्वात जवळची" अपयशी window. Window नेहमी bar j वर संपते.
    Follow-through: legacy — N=3 (j−1) अनिर्णयी + bar j दिशेने बंद ⇒ N=4; addendum — `_followthrough` (अनिर्णयी composite नंतर
    close पलीकडे ⇒ trigger; T7 trigger मध्ये; signal high stop-entry नाही)."""
    nmax = s["touch_reclaim_window"]
    res = [evaluate_window(b, j, n, dirn, levels, tol, s, **kw) for n in range(1, nmax + 1)]
    if j >= 1 and j < b.n:
        if s.get("followthrough_mode", "legacy") == "legacy":
            prev = evaluate_window(b, j - 1, nmax, dirn, levels, tol, s, **kw)
            if prev["reason"] == INDECISIVE and dirn * (b.c[j] - b.o[j]) > 0:
                res.append(evaluate_window(b, j, nmax + 1, dirn, levels, tol, s, **kw))
        else:
            res += _followthrough(b, j, dirn, levels, tol, s, nmax, kw)
    ok = [r for r in res if r["ok"]]
    if ok:
        return max(ok, key=lambda r: (r["score"], -r["n"]))
    return max(res, key=lambda r: (_STAGE.get(r["reason"], -1), r["score"], -r["n"]))


def _followthrough(b, j, dirn, levels, tol, s, nmax, kw):
    """Addendum §3.7: bar j−k (k ≤ followthrough_max_bars) वर संपलेली composite अनिर्णयी (CL 0.40–0.60; touch/reclaim/strength पास);
    मधल्या candles नी trigger दिलं नाही / hard_inv पलीकडे close नाही; bar j चा close त्या composite च्या close पलीकडे trade दिशेने
    ⇒ trigger. Score = अनिर्णयी composite चा; composite (soft stop साठी) = j पर्यंत. T7 trigger() मध्ये; stop-entry नाही."""
    out = []
    rmin = kw.get("rmin")
    kw = {k: v for k, v in kw.items() if k != "rmin"}
    inv = kw.get("inv")
    for k in range(1, s.get("followthrough_max_bars", 1) + 1):
        e = j - k
        if e < 0:
            break
        if inv is not None and any(dirn * b.c[x] <= dirn * float(inv) for x in range(e + 1, j + 1)):
            break
        if dirn * (b.c[j] - b.c[e]) <= 0:
            continue
        if any(evaluate_window(b, x, n, dirn, levels, tol, s, rmin=rmin, **kw)["ok"] for x in range(e + 1, j) for n in range(1, nmax + 1)):
            break                                                    # मधेच trigger झाला असता ⇒ तो signal, follow-through नाही
        for n in range(1, nmax + 1):
            prev = evaluate_window(b, e, n, dirn, levels, tol, s, rmin=rmin, **kw)
            if prev["reason"] != INDECISIVE:                         # touch/reclaim/strength आधीच पास; CL 0.40–0.60
                continue
            if s.get("followthrough_score_gate"):                    # F10 पर्याय: merged window चा score अट (सवलतीसह)
                mw = evaluate_window(b, j, n + k, dirn, levels, tol, s, rmin=rmin, **kw)
                if not mw["parts"] or mw["score"] < (s["rejection_min"] if rmin is None else rmin) - s["followthrough_score_relax"]:
                    continue                                         # merged window आधीच नापास ⇒ अट पूर्ण नाही
            a = e - n + 1
            r = dict(prev, ok=True, reason=None, n=n + k, followthrough=True,
                     comp=(float(b.o[a]), float(b.h[a:j + 1].max()), float(b.l[a:j + 1].min()), float(b.c[j])))
            out.append(r)
    return out


def retest_fn(frame, s, mr):
    """breaks.first_real_break साठी (c) failed-retest hook. Break candidate t (side "below") नंतर reclaim झाला; मग window
    (t+1 … t+1+touch_reclaim_window) मध्ये level L ला **उलट बाजूने** (खालून) logical reversal ने नाकारलं ⇒ त्या bar वर confirm.
    Window चे सगळे candles t नंतरचे (breaking candle composite मध्ये नाही); composite level च्या **तुटलेल्या बाजूने** सुरू
    (पहिला open L पलीकडे) आणि नकाराचा close L ∓ buffer पलीकडे — म्हणजे भाव खरंच खालून L ला लागून परत फेकला गेला.
    Time/div घटक नाहीत (score उरलेल्या weights वर)."""
    from .settings import core_candle
    s = core_candle(s)                                               # C1 candle प्रयोग real-break बदलत नाहीत
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
