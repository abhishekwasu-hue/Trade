"""patterns2/enum2.py — थर 3 v2.1 §2: hypotheses (v1 enum चीच wave-रचना: P, wave_ends, node budget, एकच उलट leg), पण नियम
v2.1 चे (rules2): फक्त **प्रकार ठरवणारे** नियम छाटतात; मजबूत पुरावा (m 0.2) `info["strong"]` मध्ये, hypothesis valid राहतो."""
from . import enum as EN
from . import rules as R
from . import rules2 as R2

wave_ends, identity, dedupe = EN.wave_ends, EN.identity, EN.dedupe


def _sub(kind, xs, done, s, tol):
    if len(xs) < 2:
        return True, []
    if kind == "zz":
        r = R2.zigzag(xs, done, s)
    elif kind == "flat":
        r = R2.flat(xs, done, s)
    elif kind == "tri_c":
        r = R2.triangle(xs, done, "contracting", tol, s)
    elif kind == "tri_e":
        r = R2.triangle(xs, done, "expanding", 0.0, s)
    else:
        raise ValueError(kind)
    return r[0], r[1]


def _wxy(w, xl, xk, y):
    ylen = 5 if y.startswith("tri") else 3

    def check(x, done, s, tol):
        n = len(x) - 1
        d = 1 if x[1] > x[0] else -1
        strong = []
        ok, st = _sub(w, x[:min(n, 3) + 1], n > 3 or done, s, tol)
        if not ok:
            return False, None
        strong += [f"W: {v}" for v in st]
        if xl == 3 and n > 3:
            ok, st = _sub(xk, x[3:min(n, 6) + 1], n > 6 or done, s, tol)
            if not ok:
                return False, None
            strong += [f"X: {v}" for v in st]
        stt = 3 + xl
        if n > stt:
            ok, st = _sub(y, x[stt:], done, s, tol)
            if not ok:
                return False, None
            strong += [f"Y: {v}" for v in st]
        strong += R2.wxy_strong(x, n, xl, d) if (n > 3 or (n == 3 and done)) else []
        return True, {"W": w, "X": f"{xl}" + (f" {xk}" if xl == 3 else ""), "Y": y, "strong": strong}
    return 3 + xl + ylen, check


def _wrap(fn):
    def check(x, done, s, tol):
        ok, strong, info = fn(x, done, s, tol)
        return ok, {**info, "strong": strong}
    return check


def variants(s):
    out = [("zigzag", "", 3, _wrap(lambda x, done, s, tol: R2.zigzag(x, done, s))),
           ("flat", "", 3, _wrap(lambda x, done, s, tol: R2.flat(x, done, s))),
           ("triangle", "contracting", 5, _wrap(lambda x, done, s, tol: R2.triangle(x, done, "contracting", tol, s))),
           ("triangle", "expanding", 5, _wrap(lambda x, done, s, tol: R2.triangle(x, done, "expanding", 0.0, s))),
           ("wedge", "contracting", 5, _wrap(lambda x, done, s, tol: R2.wedge(x, done, "contracting", s))),
           ("wedge", "expanding", 5, _wrap(lambda x, done, s, tol: R2.wedge(x, done, "expanding", s))),
           ("impulse_k", "", 5, _wrap(lambda x, done, s, tol: R2.impulse_k(x, done, s)))]
    for xl, xk in ((1, None), (3, "zz"), (3, "flat")):
        L, chk = _wxy("zz", xl, xk, "zz")
        out.append(("double_zigzag", "", L, chk))
        for w in ("zz", "flat"):
            for y in ("zz", "flat", "tri_c", "tri_e"):
                if w == "zz" and y == "zz":
                    continue
                L, chk = _wxy(w, xl, xk, y)
                out.append(("combination", "", L, chk))
    return out


def enumerate_hyps(P, s, sigma=0.0, budget=None):
    """v1 enumerate_hyps सारखंच (तीच wave-रचना आणि node budget), variants v2.1 चे. रिटर्न (hyps, budget_hit)."""
    m = len(P) - 1
    if m < 1:
        return [], False
    ends = wave_ends(P)
    tol = float(s["barrier_sigma"]) * float(sigma or 0.0)
    budget = int(budget or s["node_budget"])
    nodes, hit, out = [0], [False], []
    price = [p["price"] for p in P]

    def rec(fam, kind, L, chk, bounds):
        nodes[0] += 1
        if nodes[0] > budget:
            hit[0] = True
            return
        k = len(bounds) - 1
        x = [price[b] for b in bounds]
        if k >= 1 and bounds[-1] == m:
            ok, info = chk(x, False, s, tol)
            if ok:
                out.append({"family": fam, "kind": kind, "L": L, "bounds": list(bounds), "x": x, "t": 0, "done": False, "info": info})
        if k == L and m - bounds[-1] == 1:
            ok, info = chk(x, True, s, tol)
            after_dir = 1 if price[m] > price[bounds[-1]] else -1
            if ok and not R.beyond(price[m], x[-2], after_dir):
                out.append({"family": fam, "kind": kind, "L": L, "bounds": list(bounds), "x": x, "t": 1, "done": True, "info": info})
        if k >= L:
            return
        for j in ends[bounds[-1]]:
            ok, _ = chk(x + [price[j]], False, s, tol)
            if ok:
                rec(fam, kind, L, chk, bounds + [j])
            if hit[0]:
                return

    for fam, kind, L, chk in variants(s):
        rec(fam, kind, L, chk, [0])
        if hit[0]:
            break
    return dedupe(out, P), hit[0]
