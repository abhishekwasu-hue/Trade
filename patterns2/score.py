"""patterns2/score.py — थर 3 §2.3 (आतली रचना, दोन मापं) आणि §4 (गुण).

ओळख-गुण = फक्त **पूर्ण झालेल्या** waves वरच्या guidelines च्या membership m ∈ [0.2, 1] चा भौमितिक सरासरी × साधेपणाचा गुणक.
पूर्णता-पुरावा (शेवटच्या wave चे guidelines) वेगळा: फक्त अवस्था / अहवालासाठी, क्रमासाठी नाही. न आलेल्या waves चे guidelines मोजत नाही.
प्रत्येक पुरावा एकदाच. रचना "अज्ञात" असेल तेव्हाच थर-2 label ची ओळ (दुहेरी मोजणी नाही).
"""
import numpy as np

from legs2 import measure as LM

from . import rules as R

UNK, THREE, FIVE, DIAG = "अज्ञात", "3", "5", "diagonal"


def trap(x, a, b, c, e, floor=0.2):
    """[b, c] ⇒ 1; a / e बाहेर ⇒ floor; मध्ये रेषीय."""
    if x is None or not np.isfinite(x):
        return None
    if b <= x <= c:
        return 1.0
    if x <= a or x >= e:
        return floor
    if x < b:
        return floor + (1 - floor) * (x - a) / (b - a)
    return floor + (1 - floor) * (e - x) / (e - c)


def classify(prices):
    """एका मापाचा वर्ग: 1 ⇒ अज्ञात; 3 ⇒ 3; 5 + impulse नियम ⇒ 5; 5 + wedge नियम ⇒ diagonal; बाकी ⇒ अज्ञात."""
    n = len(prices) - 1
    if n == 3:
        return THREE
    if n != 5:
        return UNK
    if R.impulse(prices, True):
        return FIVE
    if R.wedge(prices, True, "contracting") or R.wedge(prices, True, "expanding"):
        return DIAG
    return UNK


COMBINE = {(UNK, UNK): UNK, (UNK, THREE): THREE, (UNK, FIVE): FIVE, (UNK, DIAG): DIAG,
           (THREE, UNK): THREE, (THREE, THREE): THREE, (THREE, FIVE): "3 किंवा 5", (THREE, DIAG): "3 किंवा diagonal",
           (FIVE, UNK): FIVE, (FIVE, THREE): "3 किंवा 5", (FIVE, FIVE): FIVE, (FIVE, DIAG): "5 किंवा diagonal",
           (DIAG, UNK): DIAG, (DIAG, THREE): "3 किंवा diagonal", (DIAG, FIVE): "5 किंवा diagonal", (DIAG, DIAG): DIAG}


def combine(m1, m2):
    return COMBINE[(m1, m2)]


def dc_points(h, lo, start, dirn, theta):
    """Wave च्या bars वर DC: सुरुवात wave च्या दिशेने, शेवट wave च्या टोकावर ⇒ बिंदू-संख्या सम (sub-legs विषम)."""
    pts, mode, ext = [start], dirn, start
    for i in range(len(h)):
        if mode > 0:
            if h[i] >= ext:
                ext = h[i]
            elif ext - lo[i] >= theta:
                pts.append(ext)
                mode, ext = -1, lo[i]
        else:
            if lo[i] <= ext:
                ext = lo[i]
            elif h[i] - ext >= theta:
                pts.append(ext)
                mode, ext = 1, h[i]
    if mode == dirn:
        pts.append(ext)
    return pts


def expect_m(struct, want, s):
    """रचनेचा m. want = '5' (5 / diagonal अपेक्षित) किंवा '3'. 'अज्ञात' ⇒ None (label ची ओळ ठरवेल)."""
    if struct == UNK:
        return None
    if want == FIVE:
        return {FIVE: 1.0, DIAG: 1.0, "5 किंवा diagonal": 1.0, "3 किंवा 5": s["one_match_m"], "3 किंवा diagonal": s["one_match_m"],
                THREE: s["strong_penalty"]}[struct]
    return {THREE: 1.0, "3 किंवा 5": s["one_match_m"], "3 किंवा diagonal": s["one_match_m"], FIVE: s["strong_penalty"],
            DIAG: s["strong_penalty"], "5 किंवा diagonal": s["strong_penalty"]}[struct]


class Ctx:
    """एका बंद candle (t) चा संदर्भ: P, आतले pivots, bars, थर-2 legs, σ."""

    def __init__(self, P, inner, h, lo, legs, t, sigma, s):
        self.P, self.inner, self.h, self.lo, self.legs, self.t, self.sigma, self.s = P, inner, h, lo, legs, t, sigma, s
        self._st = {}
        self.wave2_evidence = False

    def structure(self, i, j, in_progress=False):
        """P[i] → P[j] wave ची रचना (दोन मापं + एकत्रित). चालू wave: माप 2 फक्त confirmed sub-pivots वर, θ tentative वरून नाही."""
        key = (i, j, in_progress)
        if key in self._st:
            return self._st[key]
        a, b = self.P[i], self.P[j]
        dirn = 1 if b["price"] > a["price"] else -1
        sub = [p for p in self.inner if a["bar"] < p["bar"] < b["bar"]]
        m1 = classify([a["price"]] + [p["price"] for p in sub] + [b["price"]]) if not in_progress else UNK
        if in_progress:
            conf = [p for p in sub if (p["price"] - a["price"]) * dirn > 0]
            end = (max if dirn > 0 else min)(conf, key=lambda p: p["price"]) if conf else None
        else:
            end = b
        if end is None or end["bar"] < a["bar"]:
            m2 = UNK
        else:
            theta = float(self.s["struct_r"]) * abs(end["price"] - a["price"])
            hh, ll = self.h[a["bar"]:end["bar"] + 1].copy(), self.lo[a["bar"]:end["bar"] + 1].copy()
            if len(hh) and theta > 0:
                if dirn > 0:
                    ll[0] = max(ll[0], a["price"])
                    hh[-1] = min(hh[-1], end["price"])
                else:
                    hh[0] = min(hh[0], a["price"])
                    ll[-1] = max(ll[-1], end["price"])
                m2 = classify(dc_points(hh, ll, a["price"], dirn, theta))
            else:
                m2 = UNK
        out = {"m1": m1, "m2": m2, "struct": combine(m1, m2), "sub_legs": len(sub) + 1}
        self._st[key] = out
        return out

    def leg_label(self, i, j):
        """wave ची दोन्ही टोकं त्याच degree च्या एका थर-2 leg च्या टोकांशी तंतोतंत जुळतात आणि known_at ≤ decision bar ⇒ तो leg."""
        a, b = self.P[i], self.P[j]
        for L in self.legs:
            if L["a"].bar == a["bar"] and L["b"].bar == b["bar"] and L["b"].confirm_bar <= self.t:
                return L
        return None


def _wave_m(ctx, i, j, want, label_good=None):
    """रचनेची ओळ; रचना अज्ञात ⇒ थर-2 label ची ओळ (label_good = अपेक्षित स्वभाव) ⇒ एकच ओळ."""
    st = ctx.structure(i, j)
    m = expect_m(st["struct"], want, ctx.s)
    if m is not None:
        return m, f"रचना {st['struct']}"
    if label_good is None:
        return ctx.s["unknown_m"], "रचना अज्ञात"
    L = ctx.leg_label(i, j)
    if L is None or L["nature"] == LM.NEU:
        return ctx.s["unknown_m"], "रचना / label अज्ञात"
    return (1.0 if L["nature"] == label_good else 0.5), f"label {L['label']}"


def _time_m(tb, ta):
    if ta <= 0:
        return None
    return trap(tb / ta, 0.5, 1.0, 1e9, 2e9)


def lines(h, ctx):
    """रिटर्न (ओळख-ओळी [(नाव, m)], पूर्णता-ओळी [(नाव, m)])."""
    s, P, b = ctx.s, ctx.P, h["bounds"]
    n = len(b) - 1
    x = h["x"]
    L = [abs(x[k + 1] - x[k]) for k in range(n)]
    T = [P[b[k + 1]]["bar"] - P[b[k]]["bar"] for k in range(n)]
    done = [k < n - 1 or h["done"] for k in range(n)]                      # wave k (0-based) पूर्ण?
    ident, comp = [], []
    fam = h["family"]
    sp = s["strong_penalty"]

    def add(lst, name, m):
        if m is not None:
            lst.append((name, round(float(m), 4)))

    def f2(r):
        return "—" if r is None else f"{r:.2f}"

    sig = float(ctx.sigma or 0.0)

    def touch(xa, ya, xb, yb, xc, yc, dirn):
        """(xc, yc) हा (xa, ya)–(xb, yb) रेघेला स्पर्श / पलीकडे (dirn दिशेने) ⇒ 1; 0.5σ आत ⇒ 1; नाहीतर 0.5."""
        if xb == xa:
            return None
        yl = ya + (yb - ya) * (xc - xa) / (xb - xa)
        return 1.0 if (yc - yl) * dirn >= -0.5 * sig else 0.5

    if fam in ("zigzag", "flat"):
        if done[0]:
            m, why = _wave_m(ctx, b[0], b[1], FIVE if fam == "zigzag" else THREE, LM.IMP if fam == "zigzag" else LM.COR)
            add(ident, f"A: {why}", m)
        if n >= 2 and done[1]:
            r = L[1] / L[0] if L[0] else None
            if fam == "zigzag":
                add(ident, f"B/A {f2(r)}", trap(r, 0.236, 0.382, 0.618, 0.786, sp))
            elif r is not None:
                add(ident, f"B/A {f2(r)}", trap(r, 0.80, 0.90, 1.382, s["flat_b_max"], sp) if r <= s["flat_b_max"] else sp)
                lb = ctx.leg_label(b[1], b[2])
                if lb is not None and lb["label"] == "आवेग":
                    add(ident, "B चा label आवेग (expanded-B)", 0.3)
            add(ident, "B चा वेळ ≥ A", _time_m(T[1], T[0]))
        if n >= 3:
            r = L[2] / L[0] if L[0] else None
            sub = (h.get("info") or {}).get("sub")
            tg = (0.618, 1.0, 1.618) if fam == "zigzag" else {"expanded": (1.618,), "regular": (1.0,)}.get(sub, (1.0, 1.618))
            near = min(abs(r - g) / g for g in tg) if r else None
            add(comp, f"C/A {f2(r)}", 1.0 if near is not None and near <= s["fib_tol"] else trap(near, -1, -1, s["fib_tol"], 0.5, sp))
            add(comp, "C चा वेळ > A", 1.0 if T[2] > T[0] else 0.5)
            stc = ctx.structure(b[2], b[3], in_progress=not h["done"])
            add(comp, f"C रचना {stc['struct']}", expect_m(stc["struct"], FIVE, s))
            dK = 1 if x[1] > x[0] else -1
            bx = [P[b[k]]["bar"] for k in range(4)]
            if fam == "zigzag":                                                # channel: A सुरुवात–B टोक, समांतर A च्या टोकातून
                if bx[2] != bx[0]:
                    slope = (x[2] - x[0]) / (bx[2] - bx[0])
                    add(comp, "C channel ला स्पर्श", touch(bx[1], x[1], bx[1] + 1, x[1] + slope, bx[3], x[3], dK))
            else:                                                              # flat: C, A–B पट्ट्याजवळ / पलीकडे
                add(comp, "C A-टोकाजवळ / पलीकडे", 1.0 if (x[3] - x[1]) * dK >= -0.5 * sig else 0.5)
    elif fam == "triangle":
        for k in range(n):
            if done[k]:
                m = expect_m(ctx.structure(b[k], b[k + 1])["struct"], THREE, s)
                add(ident, f"{'ABCDE'[k]} रचना", m if m is not None else s["unknown_m"])
        for k in range(1, n):
            if done[k]:
                ok = L[k] < L[k - 1] if h["kind"] == "contracting" else L[k] > L[k - 1]
                add(ident, f"{'ABCDE'[k]} {'लहान' if h['kind'] == 'contracting' else 'मोठा'}", 1.0 if ok else 0.5)
        if h["kind"] == "expanding":
            add(ident, "expanding उप-प्रकार", 0.5)
        if ctx.wave2_evidence:
            add(ident, "K हा wave 2 असण्याचा पुरावा", sp)
        if n == 5 and h["kind"] == "contracting":                              # पूर्णता: E, A–C रेघेला स्पर्श
            bx = [P[b[k]]["bar"] for k in range(6)]
            dK = 1 if x[1] > x[0] else -1
            add(comp, "E, A–C रेघेजवळ", touch(bx[1], x[1], bx[3], x[3], bx[5], x[5], dK))
    elif fam == "wedge":
        if n >= 4 and done[3]:
            add(ident, "4 हा 1 च्या पट्ट्यात", 1.0 if (x[4] - x[1]) * (1 if x[1] > x[0] else -1) <= 0 else 0.5)
        # "legs च्या लांबीची सुसंगती" (1 > 3 > 5 / उलट) हा wedge चा gate आधीच (rules.wedge) ⇒ इथे दुसऱ्यांदा मोजत नाही
        if n == 5:                                                             # पूर्णता: 5, 1–3 रेघेला स्पर्श / throw-over
            bx = [P[b[k]]["bar"] for k in range(6)]
            dK = 1 if x[1] > x[0] else -1
            add(comp, "5, 1–3 रेघेला स्पर्श / throw-over", touch(bx[1], x[1], bx[3], x[3], bx[5], x[5], dK))
    elif fam == "impulse_k":
        if done[0]:
            m, why = _wave_m(ctx, b[0], b[1], FIVE)
            add(ident, f"1: {why}", m)
        if n >= 2 and done[1]:
            add(ident, "2 चा वेळ ≥ 1", _time_m(T[1], T[0]))
        if n >= 3 and done[2]:
            add(ident, "3 लांब", 1.0 if L[2] >= max([L[0]] + ([L[4]] if n == 5 and done[4] else [])) else 0.5)
        if n >= 4 and done[3] and L[2]:
            add(ident, f"4/3 {L[3] / L[2]:.2f}", trap(L[3] / L[2], 0.146, 0.236, 0.382, 0.618, sp))
        if n == 5 and done[4]:
            ext = [k for k in (0, 2, 4) if L[k] >= 1.618 * max(L[j] for j in (0, 2, 4) if j != k)]
            add(ident, "एकच extended wave", 1.0 if len(ext) == 1 else 0.5)
    elif fam in ("double_zigzag", "combination"):
        if done[0]:
            m, why = _wave_m(ctx, b[0], b[1], FIVE, LM.IMP) if fam == "double_zigzag" else (None, "")
            add(ident, f"W.A: {why}", m)
        info = h["info"] or {}
        xl = int(str(info.get("X", "1")).split()[0])
        wsz = abs(x[3] - x[0]) if n >= 3 else None
        if n >= 3 + xl and done[2 + xl] and wsz:
            xsz = abs(x[3 + xl] - x[3])
            r = xsz / wsz
            if fam == "double_zigzag":
                add(ident, f"X/W {r:.2f}", trap(r, -1, -1, 0.618, 1.0, sp))
            else:
                add(ident, f"X/W {r:.2f}", trap(r, 0.236, 0.5, 1e9, 2e9, sp))
                tw, tx = P[b[3]]["bar"] - P[b[0]]["bar"], P[b[3 + xl]]["bar"] - P[b[3]]["bar"]
                ty = P[b[-1]]["bar"] - P[b[3 + xl]]["bar"] if n == h["L"] and h["done"] else None
                add(ident, "X चा वेळ ≤ शेजारचे (W, Y)", 1.0 if tx <= tw and (ty is None or tx <= ty) else 0.5)
        if n == h["L"] and wsz:
            ysz = abs(x[-1] - x[3 + xl])
            add(comp, f"Y/W {ysz / wsz:.2f}", trap(ysz / wsz, 0.382, 0.618, 1.618, 2.618, sp))
    return ident, comp


def score(h, ctx):
    """ओळख-गुण = भौमितिक सरासरी(m) × साधेपणा. रिकामा संच ⇒ empty_m."""
    ident, comp = lines(h, ctx)
    ms = [m for _, m in ident]
    g = float(np.exp(np.mean(np.log(ms)))) if ms else float(ctx.s["empty_m"])
    simp = ctx.s["simplicity"]
    mult = simp["wxy"] if h["family"] in ("double_zigzag", "combination") else simp.get(str(h["L"]), 1.0)
    h["lines"], h["completion"] = ident, comp
    h["score"] = round(g * float(mult), 6)
    return h["score"]
