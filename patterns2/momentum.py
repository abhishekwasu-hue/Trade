"""patterns2/momentum.py — थर 3 v2.1 §7: "momentum कमकुवत होतोय का" (मुख्य output; प्रत्येक बंद candle).

12 लक्षणं; प्रत्येक ✓ (सगळ्या उप-अटी खऱ्या) / ✗ (कोणतीही खोटी) / NA (कोणताही input NA). Pushes = preferred चे counter-दिशेचे waves
(fallback: K चे pivots, "ओळखता येत नाही" तेव्हा). निकाल: non-NA ≥ 6 (नाहीतर "अस्पष्ट (early)"; < 2 pushes ⇒ early); ratio = ✓ ÷ non-NA;
≥ 0.65 ⇒ कमकुवत होतोय, ≤ 0.35 ⇒ नाही, मध्ये अस्पष्ट. Danger ⇒ नाही. Retrace ≥ 0.80 = फक्त नोंद.
थर 4 नंतर item 9 (absorption, zone) `zone_fn` देऊन **हेच function** पुन्हा ⇒ एकच verdict.
"""
import numpy as np

from legs2 import features as LF
from legs2 import measure as LM
from legs2 import measure2 as M2

from . import score as SC

YES, NO, NA = "✓", "✗", "NA"
WEAK, NOT, UNCLEAR, EARLY = "कमकुवत होतोय", "नाही", "अस्पष्ट", "अस्पष्ट (early)"
NAMES = ("SOT", "three-push", "counter candles लहान", "closes / push स्वभाव", "counter displacement नाही", "संथ",
         "नाममात्र नवं टोक", "volume fading", "absorption", "खोली / origin", "3 legs (5 नव्हे)", "CISD")


def _all(conds):
    """None (NA) असेल तर NA; नाहीतर सगळे खरे ⇒ ✓."""
    if any(c is None for c in conds):
        return NA
    return YES if all(conds) else NO


def pushes_of(h, P, kd):
    """Preferred hypothesis चे counter (K) दिशेचे waves ⇒ [(start_bar, end_bar, start_price, end_price)]."""
    if h is not None:
        b = h["bounds"]
        out = []
        for k in range(len(b) - 1):
            a, e = P[b[k]], P[b[k + 1]]
            if (e["price"] - a["price"]) * kd > 0:
                out.append((a["bar"], e["bar"], a["price"], e["price"]))
        return out
    out = []
    for a, e in zip(P, P[1:]):
        if (e["price"] - a["price"]) * kd > 0:
            out.append((a["bar"], e["bar"], a["price"], e["price"]))
    return out


def _nature(lg, d0, p, prev, t):
    """एका push चा C × V स्वभाव (थर 2 च्या मापाने, त्या degree च्या baseline वर; t पर्यंतचे legs)."""
    ref = next((x for x in lg["res"]["pivots"][d0] if x.bar == p[0]), None)
    if ref is None:
        return None
    a = ref
    L = M2.make_leg(lg, d0, a, p[1], p[3], None)
    base = [x for x in lg["legs"][d0] if x["b"].confirm_bar <= t]
    pl = None
    if prev is not None:
        pa = next((x for x in lg["res"]["pivots"][d0] if x.bar == prev[0]), None)
        if pa is not None:
            pl = M2.make_leg(lg, d0, pa, prev[1], prev[3], None)
    M2.finish(lg, L, base, pl)
    if L.get("C_na") or L["short"]:
        return None
    return L["nature"]


def evaluate(ctx, zone_fn=None):
    """ctx: dict — A, rr, lg, s (थर 3 settings), d (degree), t, I (ik2 state dict), K, flags, h (preferred किंवा None), P,
    pref_family, k_struct (K च्या counter चालीची रचना), sigma. रिटर्न {"items": [...], "verdict", "ratio", "danger", "notes"}."""
    A, rr, lg_, s, t = ctx["A"], ctx["rr"], ctx["lg"], ctx["s"], ctx["t"]
    st = ctx["state"]
    I, K, fl = st["I"], st.get("K") or {}, st.get("flags") or {}
    idir = I["dir"]
    kd = -idir
    P, h = ctx["P"], ctx.get("h")
    sig = ctx["sigma"]
    pu = pushes_of(h, P, kd)
    k0 = P[0]["bar"]
    kbars = list(range(k0 + 1, t + 1))
    il = ctx["i_leg"]                                                       # (start_bar, end_bar, start_price, end_price)
    items = []

    # 1 SOT
    if len(pu) < 3:
        items.append(NA)
    else:
        g = [abs(p[3] - p[2]) for p in pu[-3:]]
        items.append(_all([g[0] > g[1] > g[2], g[2] <= float(s["m_sot_ratio"]) * g[0]]))
    # 2 three-push geometry + convergence
    if len(pu) < 3:
        items.append(NA)
    else:
        q = pu[-3:]
        sl = [abs(p[3] - p[2]) / max(p[1] - p[0], 1) for p in q]
        bd = [np.nanmean([LF.body_pct(A, i) if LF.body_pct(A, i) is not None else np.nan for i in range(p[0] + 1, p[1] + 1)])
              for p in (q[0], q[2])]
        w = LF.wick_opp_d(A, q[2][1], kd)
        conv = converge(pu, P, h, kd)
        items.append(_all([sl[0] >= sl[1] >= sl[2], bool(bd[1] < bd[0]) if np.isfinite(bd).all() else None,
                           None if w is None else w >= float(s["m_wick"]), conv]))
    # 3 counter candles लहान
    cc = [i for i in kbars if (A["c"][i] - A["o"][i]) * kd > 0 and np.isfinite(rr[i])]
    if len(kbars) < int(s["m_min_k_candles"]) or len(cc) < 3:
        items.append(NA)
    else:
        last, first = np.median([rr[i] for i in cc[-3:]]), np.median([rr[i] for i in cc[:3]])
        kmed = np.median([rr[i] for i in kbars if np.isfinite(rr[i])])
        imed_l = [rr[i] for i in range(il[0] + 1, il[1] + 1) if np.isfinite(rr[i])]
        items.append(_all([last < float(s["m_small_ratio"]) * first, (kmed < np.median(imed_l)) if imed_l else None]))
    # 4 closes टोकापासून दूर + शेवटच्या push चा स्वभाव
    if not pu or not kbars:
        items.append(NA)
    else:
        cl = [LF.clv_d(A, i, kd) for i in kbars[-3:]]
        tc = np.mean([LF.trend_candle(A, i, kd, lg_["settings"]) for i in kbars[-5:]])
        nat = _nature(lg_, ctx["d0"], pu[-1], pu[-2] if len(pu) >= 2 else None, t)
        items.append(_all([None if any(x is None for x in cl) else np.mean(cl) <= float(s["m_clv"]),
                           tc <= float(s["m_trend_pct"]), None if nat is None else nat in (LM.COR, LM.NEU)]))
    # 5 counter displacement नाही; counter FVG नाही / भरला
    nd = sum(LF.displacement(A, rr, i, kd, lg_["settings"]) for i in kbars[-5:])
    items.append(_all([nd == 0, not unfilled_fvg(A, kbars, kd, t)]))
    # 6 संथ
    ksize = abs(K.get("extreme", P[-1]["price"]) - P[0]["price"]) if K else abs(P[-1]["price"] - P[0]["price"])
    kb = max(t - k0, 1)
    isz, ib = abs(il[3] - il[2]), max(il[1] - il[0], 1)
    items.append(_all([ksize / kb <= float(s["m_speed"]) * isz / ib, kb >= float(s["m_bars"]) * ib]))
    # 7 नाममात्र नवं टोक
    if len(pu) < 2:
        items.append(NA)
    else:
        new = (pu[-1][3] - pu[-2][3]) * kd
        j = pu[-1][1]
        cv = LF.clv_d(A, j, kd)
        items.append(_all([new < float(s["m_new_ext_sigma"]) * sig, None if cv is None else cv < 0.5]))
    # 8 volume fading
    rv, bad = lg_["rv"], lg_["bad"]

    def prv(p):
        xs = [rv[i] for i in range(p[0] + 1, p[1] + 1) if np.isfinite(rv[i]) and not bad[i]]
        return float(np.mean(xs)) if xs else None
    if len(pu) < 2:
        items.append(NA)
    else:
        r = [prv(p) for p in pu[-3:]]
        if any(x is None for x in r):
            items.append(NA)
        else:
            dec = all(r[i + 1] < r[i] for i in range(len(r) - 1))
            items.append(_all([dec, bool(fl.get("pullback_quiet"))]))
    # 9 absorption (फक्त zone; थर 4 आधी NA)
    if zone_fn is None:
        items.append(NA)
    else:
        vol = lg_["vol"]
        kv = np.nansum([vol[i] for i in kbars if np.isfinite(vol[i]) and not bad[i]])
        iv = np.nansum([vol[i] for i in range(il[0] + 1, il[1] + 1) if np.isfinite(vol[i]) and not bad[i]])
        if not kv or not iv or not ksize or not isz:
            items.append(NA)
        else:
            z = zone_fn(K.get("extreme", P[-1]["price"]), t)
            items.append(_all([(kv / ksize) >= float(s["m_absorb"]) * (iv / isz), None if z is None else bool(z)]))
    # 10 खोली / origin
    dm = K.get("depth_main")
    items.append(_all([None if dm is None else float(s["m_depth_lo"]) <= dm <= float(s["m_depth_hi"]), not fl.get("choch_strict")]))
    # 11 3 legs (impulsive 5 नव्हे)
    fam = ctx.get("pref_family")
    if fam in ("wedge", "triangle"):
        items.append(YES)
    else:
        items.append(_all([fam != "impulse_k", ctx.get("k_struct") != SC.FIVE]))
    # 12 CISD
    items.append(YES if fl.get("cisd") is not None else NO)

    # danger
    danger = []
    if fl.get("pullback_heavy") and any(L.get("label") == "आवेग" and L["dir"] == kd for L in ctx.get("k_legs", [])):
        danger.append("K leg आवेग + pullback_heavy")
    if fl.get("choch_disp"):
        danger.append("CHoCH strict + displacement")
    if ctx.get("k_struct") == SC.FIVE and fam not in ("wedge", "triangle"):
        danger.append("impulsive 5-leg counter")
    if I.get("climax") and len(ctx.get("k_legs", [])) <= 1:
        danger.append("I टोकावर climax आणि K चा पहिलाच leg")
    if fam == "impulse_k":
        danger.append("impulse-K preferred")
    non_na = [x for x in items if x != NA]
    ratio = (sum(x == YES for x in non_na) / len(non_na)) if non_na else None
    if danger:
        verdict = NOT
    elif len(pu) < 2 or len(non_na) < int(s["m_min_non_na"]):
        verdict = EARLY
    elif ratio >= float(s["m_hi"]):
        verdict = WEAK
    elif ratio <= float(s["m_lo"]):
        verdict = NOT
    else:
        verdict = UNCLEAR
    notes = []
    sec = K.get("depth_secondary")
    if dm is not None and dm >= float(s["retrace_note"]):
        notes.append(f"retrace {dm:.2f} ≥ {s['retrace_note']} (sweep-flavour नोंद; danger नाही)")
    return {"items": items, "names": list(NAMES), "verdict": verdict, "ratio": None if ratio is None else round(ratio, 3),
            "non_na": len(non_na), "pushes": len(pu), "danger": danger, "notes": notes, "depth_secondary": sec,
            "item9_zone": zone_fn is not None}


def converge(pu, P, h, kd):
    """K च्या रेघा converge: counter push-टोकांची रेघ (शेवटचे दोन) आणि pullback-टोकांची रेघ (शेवटचे दोन) — त्यांच्यातलं अंतर
    पुढे घटतं. < 2 + 2 टोकं ⇒ None."""
    if len(pu) < 2:
        return None
    ends = [(p[1], p[3]) for p in pu[-2:]]
    starts = [(p[0], p[2]) for p in pu[-2:]]
    if ends[0][0] == ends[1][0] or starts[0][0] == starts[1][0]:
        return None
    s1 = (ends[1][1] - ends[0][1]) / (ends[1][0] - ends[0][0])
    s2 = (starts[1][1] - starts[0][1]) / (starts[1][0] - starts[0][0])
    return bool((s1 - s2) * kd < 0)


def unfilled_fvg(A, kbars, kd, t):
    """K मधला counter-दिशेचा FVG जो t पर्यंत भरला नाही."""
    for i in kbars:
        if LF.fvg(A, i, kd):
            edge = A["h"][i - 2] if kd > 0 else A["l"][i - 2]
            later = range(i + 1, t + 1)
            filled = any((A["l"][j] <= edge) if kd > 0 else (A["h"][j] >= edge) for j in later)
            if not filled:
                return True
    return False


class Hysteresis:
    """Verdict बदल: नवा verdict लागोपाठ `bars` candles ⇒ बदल (danger ⇒ लगेच)."""

    def __init__(self, bars=2):
        self.bars, self.cur, self.cand, self.n = int(bars), None, None, 0

    def step(self, v, danger=False):
        if self.cur is None or danger:
            self.cur, self.cand, self.n = v, None, 0
            return self.cur
        if v == self.cur:
            self.cand, self.n = None, 0
            return self.cur
        self.n = self.n + 1 if v == self.cand else 1
        self.cand = v
        if self.n >= self.bars:
            self.cur, self.cand, self.n = v, None, 0
        return self.cur
