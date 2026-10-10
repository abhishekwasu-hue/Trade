"""patterns2/score2.py — थर 3 v2.1 §4: गुण. v1 (score.py) ची रचना-मापं (classify, dc_points, Ctx) तशीच; बदल:

- मजबूत पुरावा (rules2) ⇒ प्रत्येकी एक ओळ m = strong_penalty (0.2), एकदाच.
- Flat B/A: 0.90–1.382 ⇒ 1; 0.618–0.90 चढता; > 2 ⇒ मजबूत पुरावा (वेगळी ओळ नाही).
- Wedge: "3 > 1-end" नसेल ⇒ 0.6 (Brooks three push); 1 > 3 > 5 सुसंगती; 4 ∈ 1; [पूर्णता] 5 ने 3 गाठलं (नाही ⇒ 0.6), 1–3 रेघ.
- Triangle: apex — triangle ने apex पर्यंतचा > 85% वेळ घेतला ⇒ 0.6.
- थर 2 स्वभाव-ओळ फक्त रचना अज्ञात असताना; expanded-flat B: label आवेग 0.3, आवेग (कमकुवत) 0.6.
- Volume / वेळ = पूर्णता-पुरावा (ओळख-गुणात नाही): K RVOL slope, K वेळ ≥ I-leg / 3, शेवटचा leg वेळ ≥ पहिला; K > 2 × I-leg ⇒ `range_like`.
"""
import numpy as np

from legs2 import measure as LM

from .score import DIAG, FIVE, THREE, UNK, Ctx, classify, combine, dc_points, expect_m, trap  # noqa: F401


def _wave_m(ctx, i, j, want, nat_good=None):
    st = ctx.structure(i, j)
    m = expect_m(st["struct"], want, ctx.s)
    if m is not None:
        return m, f"रचना {st['struct']}"
    if nat_good is None:
        return ctx.s["unknown_m"], "रचना अज्ञात"
    L = ctx.leg_label(i, j)
    if L is None or L.get("nature") in (None, LM.NEU):
        return ctx.s["unknown_m"], "रचना / स्वभाव अज्ञात"
    return (1.0 if L["nature"] == nat_good else 0.5), f"स्वभाव {L['nature']} ({L['label']})"


def _time_m(tb, ta):
    if ta <= 0:
        return None
    return trap(tb / ta, 0.5, 1.0, 1e9, 2e9)


def _line_y(xa, ya, xb, yb, xc):
    return ya + (yb - ya) * (xc - xa) / (xb - xa)


def lines(h, ctx):
    s, P, b = ctx.s, ctx.P, h["bounds"]
    n = len(b) - 1
    x = h["x"]
    L = [abs(x[k + 1] - x[k]) for k in range(n)]
    T = [P[b[k + 1]]["bar"] - P[b[k]]["bar"] for k in range(n)]
    done = [k < n - 1 or h["done"] for k in range(n)]
    ident, comp = [], []
    fam = h["family"]
    sp = float(s["strong_penalty"])
    sig = float(ctx.sigma or 0.0)
    dK = 1 if x[1] > x[0] else -1
    bx = [P[b[k]]["bar"] for k in range(n + 1)]

    def add(lst, name, m):
        if m is not None:
            lst.append((name, round(float(m), 4)))

    def f2(r):
        return "—" if r is None else f"{r:.2f}"

    def touch(xa, ya, xb, yb, xc, yc, dirn):
        if xb == xa:
            return None
        return 1.0 if (yc - _line_y(xa, ya, xb, yb, xc)) * dirn >= -0.5 * sig else 0.5

    for name in dict.fromkeys((h.get("info") or {}).get("strong") or []):       # मजबूत पुरावा: प्रत्येक एकदाच
        add(ident, f"मजबूत: {name}", sp)

    if fam in ("zigzag", "flat"):
        if done[0]:
            m, why = _wave_m(ctx, b[0], b[1], FIVE if fam == "zigzag" else THREE, LM.IMP if fam == "zigzag" else LM.COR)
            add(ident, f"A: {why}", m)
        if n >= 2 and done[1]:
            r = L[1] / L[0] if L[0] else None
            if fam == "zigzag":
                add(ident, f"B/A {f2(r)}", trap(r, 0.236, 0.382, 0.618, s["zz_max_ba"], sp))
            elif r is not None and r <= float(s["flat_b_max"]):
                add(ident, f"B/A {f2(r)}", trap(r, s["flat_min_ba"], s["flat_b_min_ratio"], 1.382, s["flat_b_max"], sp))
            if fam == "flat" and r is not None and r > float(s["flat_expanded_min"]):
                st = ctx.structure(b[1], b[2])
                if st["struct"] == UNK:                                            # रचना माहीत ⇒ स्वभाव-ओळ नाही
                    lb = ctx.leg_label(b[1], b[2])
                    if lb is not None and lb.get("label") == "आवेग":
                        add(ident, "B चा label आवेग (expanded-B)", s["exp_b_imp_m"])
                    elif lb is not None and lb.get("label") == "आवेग (कमकुवत)":
                        add(ident, "B चा label आवेग (कमकुवत)", s["exp_b_weak_m"])
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
            if fam == "zigzag":
                if bx[2] != bx[0]:
                    slope = (x[2] - x[0]) / (bx[2] - bx[0])
                    add(comp, "C channel ला स्पर्श", touch(bx[1], x[1], bx[1] + 1, x[1] + slope, bx[3], x[3], dK))
            else:
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
        if n >= 4 and h["kind"] == "contracting":
            ap = apex(bx, x)
            if ap is not None and ap > bx[0]:
                frac = (ctx.t - bx[0]) / (ap - bx[0])
                add(ident, f"apex वेळ {frac:.0%}", float(s["apex_m"]) if frac > float(s["apex_frac"]) else 1.0)
        if n == 5 and h["kind"] == "contracting":
            add(comp, "E, A–C रेघेजवळ", touch(bx[1], x[1], bx[3], x[3], bx[5], x[5], dK))
    elif fam == "wedge":
        if n >= 3 and done[2]:
            add(ident, "3 पलीकडे 1-end", 1.0 if (x[3] - x[1]) * dK > 0 else float(s["three_push_m"]))
        if n >= 4 and done[3]:
            add(ident, "4 हा 1 च्या पट्ट्यात", 1.0 if (x[4] - x[1]) * dK <= 0 else 0.5)
        if n == 5 and done[4]:
            con = h["kind"] == "contracting"
            add(ident, "1 > 3 > 5 सुसंगती" if con else "1 < 3 < 5 सुसंगती", 1.0 if ((L[4] < L[2]) if con else (L[4] > L[2])) else 0.5)
        if n == 5:
            add(comp, "5 ने 3 गाठलं", 1.0 if (x[5] - x[3]) * dK >= 0 else float(s["short_final_m"]))
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
    elif fam in ("double_zigzag", "combination"):
        if done[0] and fam == "double_zigzag":
            m, why = _wave_m(ctx, b[0], b[1], FIVE, LM.IMP)
            add(ident, f"W.A: {why}", m)
        info = h["info"] or {}
        xl = int(str(info.get("X", "1")).split()[0])
        wsz = abs(x[3] - x[0]) if n >= 3 else None
        if n >= 3 + xl and done[2 + xl] and wsz:
            r = abs(x[3 + xl] - x[3]) / wsz
            if fam == "double_zigzag":
                add(ident, f"X/W {r:.2f}", trap(r, -1, -1, 0.618, 1.0, sp))
            else:
                add(ident, f"X/W {r:.2f}", trap(r, 0.236, 0.5, 1e9, 2e9, sp))
                tw, tx = bx[3] - bx[0], bx[3 + xl] - bx[3]
                ty = bx[-1] - bx[3 + xl] if n == h["L"] and h["done"] else None
                add(ident, "X चा वेळ ≤ शेजारचे (W, Y)", 1.0 if tx <= tw and (ty is None or tx <= ty) else 0.5)
        if n == h["L"] and wsz:
            ysz = abs(x[-1] - x[3 + xl])
            add(comp, f"Y/W {ysz / wsz:.2f}", trap(ysz / wsz, 0.382, 0.618, 1.618, 2.618, sp))
    vol_time(h, ctx, comp)
    return ident, comp


def apex(bx, x):
    """A–C (bx1, bx3) आणि B–D (bx2, bx4) रेघांचा छेद (bar). समांतर / उलट ⇒ None."""
    if bx[3] == bx[1] or bx[4] == bx[2]:
        return None
    s1 = (x[3] - x[1]) / (bx[3] - bx[1])
    s2 = (x[4] - x[2]) / (bx[4] - bx[2])
    if s1 == s2:
        return None
    t = (x[2] - s2 * bx[2] - x[1] + s1 * bx[1]) / (s1 - s2)
    return t if t > bx[4] else None


def vol_time(h, ctx, comp):
    """पूर्णता-पुरावा (ओळख-गुणात नाही): K वर RVOL slope; K वेळ vs I-leg; शेवटचा leg वेळ vs पहिला. range_like खूण info मध्ये."""
    ex = getattr(ctx, "extra", None) or {}
    P, b = ctx.P, h["bounds"]
    k0, k1 = P[0]["bar"], ctx.t
    rv, bad = ex.get("rv"), ex.get("bad")
    if rv is not None and k1 - k0 >= 3:
        xs = [(j, rv[j]) for j in range(k0 + 1, k1 + 1) if np.isfinite(rv[j]) and not bad[j]]
        if len(xs) >= 3:
            sl = float(np.polyfit([a for a, _ in xs], [v for _, v in xs], 1)[0])
            comp.append(("K RVOL slope " + ("घटता" if sl < 0 else "वाढता / सपाट"), 1.0 if sl < 0 else float(ctx.s["vol_flat_m"])))
    il = ex.get("i_leg_bars")
    T = [P[b[k + 1]]["bar"] - P[b[k]]["bar"] for k in range(len(b) - 1)]
    if il:
        kt = k1 - k0
        ok = kt >= il / 3.0 and (len(T) < 2 or T[-1] >= T[0])
        comp.append(("K वेळ ≥ I-leg/3, शेवटचा leg ≥ पहिला", 1.0 if ok else 0.5))
        h["range_like"] = bool(kt > float(ctx.s["range_like_x"]) * il)


def score(h, ctx):
    ident, comp = lines(h, ctx)
    ms = [m for _, m in ident]
    g = float(np.exp(np.mean(np.log(ms)))) if ms else float(ctx.s["empty_m"])
    simp = ctx.s["simplicity"]
    mult = simp["wxy"] if h["family"] in ("double_zigzag", "combination") else simp.get(str(h["L"]), 1.0)
    h["lines"], h["completion"] = ident, comp
    h["score"] = round(g * float(mult), 6)
    return h["score"]
