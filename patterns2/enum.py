"""patterns2/enum.py — थर 3 §2: K मधल्या pivot-क्रमावर (P) hypotheses बनवणं, पक्क्या नियमांनी छाटत.

P = [सुरुवात (I_end)] + K मधले confirmed pivots (वेळेनुसार) + tentative टोक. Wave = P मधल्या दोन pivots मधला भाग, ज्याची सुरुवात आणि
शेवट हीच त्याची टोकं (आत लपलेलं टोक नाही); sub-legs विषम. Pattern एका pivot वर संपू शकतो; त्यानंतर P मध्ये **एकच** उलट leg असू शकतो
(शेवटच्या wave च्या सुरुवातीपलीकडे न गेलेला) ⇒ t = 1. Templates एका निश्चित node budget मध्ये.
"""
from . import rules as R

TEMPLATES = ("zigzag", "flat", "triangle", "double_zigzag", "combination", "wedge", "impulse_k")


def _sub(kind, xs, done, s, tol):
    if len(xs) < 2:
        return True
    if kind == "zz":
        return R.zigzag(xs, done)
    if kind == "flat":
        return R.flat(xs, done, s["flat_b_min_ratio"], s["flat_expanded_min"])[0]
    if kind == "tri_c":
        return R.triangle(xs, done, "contracting", tol)[0]
    if kind == "tri_e":
        return R.triangle(xs, done, "expanding", tol)[0]
    raise ValueError(kind)


def _wxy(w, xl, xk, y):
    """W-X-Y variant: W (zz / flat) 3 waves, X 1 किंवा 3 (zz / flat) waves, Y (zz / flat 3, tri 5)."""
    ylen = 5 if y.startswith("tri") else 3

    def check(x, done, s, tol):
        n = len(x) - 1
        d = 1 if x[1] > x[0] else -1
        if not _sub(w, x[:min(n, 3) + 1], n > 3 or done, s, tol):
            return False, None
        if n > 3 or (n == 3 and done):
            if not R.reached(x[3], x[1], d):                                 # W चा C, W च्या A चं टोक गाठत नाही ⇒ W invalid
                return False, None
        if n > 3:
            if not R.x_not_beyond_w(x[4:min(n, 3 + xl) + 1], x[0], d):
                return False, None
            if xl == 3 and not _sub(xk, x[3:min(n, 6) + 1], n > 6 or done, s, tol):
                return False, None
        st = 3 + xl
        if n > st and not _sub(y, x[st:], done, s, tol):
            return False, None
        return True, {"W": w, "X": f"{xl}" + (f" {xk}" if xl == 3 else ""), "Y": y}
    return 3 + xl + ylen, check


def variants(s):
    """[(family, kind, L, check)]. kind = identity चा भाग (triangle / wedge चा प्रकार); flat चा उप-प्रकार identity मध्ये नाही."""
    out = [("zigzag", "", 3, lambda x, done, s, tol: (R.zigzag(x, done), {})),
           ("flat", "", 3, lambda x, done, s, tol: (lambda r: (r[0], {"sub": r[1]}))(
               R.flat(x, done, s["flat_b_min_ratio"], s["flat_expanded_min"]))),
           ("triangle", "contracting", 5, lambda x, done, s, tol: (lambda r: (r[0], {"barrier": r[1]}))(
               R.triangle(x, done, "contracting", tol))),
           ("triangle", "expanding", 5, lambda x, done, s, tol: (R.triangle(x, done, "expanding")[0], {})),
           ("wedge", "contracting", 5, lambda x, done, s, tol: (R.wedge(x, done, "contracting"), {})),
           ("wedge", "expanding", 5, lambda x, done, s, tol: (R.wedge(x, done, "expanding"), {})),
           ("impulse_k", "", 5, lambda x, done, s, tol: (R.impulse(x, done), {}))]
    for xl, xk in ((1, None), (3, "zz"), (3, "flat")):
        L, chk = _wxy("zz", xl, xk, "zz")
        out.append(("double_zigzag", "", L, chk))
        for w in ("zz", "flat"):
            for y in ("zz", "flat", "tri_c", "tri_e"):
                if w == "zz" and y == "zz":
                    continue                                                   # combination मध्ये एकापेक्षा जास्त zigzag नाही
                L, chk = _wxy(w, xl, xk, y)
                out.append(("combination", "", L, chk))
    return out


def wave_ends(P):
    """ends[i] = j (j − i विषम) ज्यांसाठी P[i] → P[j] हा वैध wave (P[i] आणि P[j] हीच त्या भागाची टोकं)."""
    m = len(P) - 1
    ends = [[] for _ in P]
    for i in range(m):
        up = P[i + 1]["price"] > P[i]["price"]
        ext = None
        for j in range(i + 1, m + 1):
            p = P[j]["price"]
            if (up and p < P[i]["price"]) or (not up and p > P[i]["price"]):
                break                                                          # सुरुवात आता टोक राहिली नाही
            if ext is None or (up and p >= ext) or (not up and p <= ext):
                ext = p
                if (j - i) % 2 == 1:
                    ends[i].append(j)
    return ends


def enumerate_hyps(P, s, sigma=0.0, budget=None):
    """सगळे वैध hypotheses (पूर्ण आणि अपूर्ण). रिटर्न (hyps, budget_hit)."""
    m = len(P) - 1
    if m < 1:
        return [], False
    ends = wave_ends(P)
    tol = float(s["barrier_sigma"]) * float(sigma or 0.0)
    budget = int(budget or s["node_budget"])
    nodes = [0]
    hit = [False]
    out = []
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
            xn = x + [price[j]]
            ok, _ = chk(xn, False, s, tol)
            if ok:
                rec(fam, kind, L, chk, bounds + [j])
            if hit[0]:
                return

    for fam, kind, L, chk in variants(s):
        rec(fam, kind, L, chk, [0])
        if hit[0]:
            break
    return dedupe(out, P), hit[0]


def identity(h, P):
    """(family, प्रकार, सुरुवातीचा pivot, confirmed wave-टोकांचे pivot ids). Pivot id = त्याचा 15M bar (nested degrees मध्ये तोच)."""
    return (h["family"], h["kind"], P[0]["bar"], tuple(P[b]["bar"] for b in h["bounds"][1:] if not P[b].get("tent")))


def dedupe(hyps, P):
    """एकाच family + सीमा + लांबी (L) + X-लांबीचे W-X-Y variants (फक्त W / Y प्रकार वेगळे) ⇒ एकच (पहिला; बाकी `variants` मध्ये).
    वेगळ्या L / X चे readings (उदा. पूर्ण 9-wave वि. 11-wave चा prefix) वेगळे राहतात. क्रम निश्चित."""
    def key(h):
        return (h["family"], h["kind"], tuple(h["bounds"]), h["t"], h["L"], str((h.get("info") or {}).get("X")))
    seen, out = {}, []
    for h in hyps:
        k = key(h)
        if k in seen:
            seen[k].setdefault("variants", [seen[k]["info"]]).append(h["info"])
            continue
        seen[k] = h
        out.append(h)
    return out
