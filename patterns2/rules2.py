"""patterns2/rules2.py — थर 3 v2.1 §3: नियम तीन प्रकारचे.

1. **नकार:** फक्त I_origin चा real break (थर 2 "I रद्द") — इथे नाही; K च नाही तर hypotheses नाहीत.
2. **प्रकार ठरवणारे** (हा प्रकार नाही ⇒ दुसरा प्रकार): zigzag / flat B/A सीमा, triangle contracting / expanding, wedge contracting /
   expanding, impulse-K चे नियम, W-X-Y चा आकार.
3. **मजबूत पुरावा** (m = 0.2, प्रत्येक एकदाच; hypothesis valid राहतो): flat B ≤ 2A; wedge 2 ≯ 1-start, 4 ≯ 2-end; W-X-Y: X ≯ W-start,
   W चा C ≥ W चा A-end, ≤ 1 zigzag; triangle legs "5" (score मध्ये, रचनेवरून).

x = wave-टोकांच्या किंमती [x0 … xn]; done = शेवटचा wave पूर्ण. रिटर्न (type_ok, strong (नावांची यादी), info).
"""
from . import rules as R

beyond, reached = R.beyond, R.reached


def _d(x):
    return 1 if x[1] > x[0] else -1


def _L(x):
    return [abs(x[i + 1] - x[i]) for i in range(len(x) - 1)]


def _complete(n, k, done):
    return n > k or (n == k and done)


def zigzag(x, done=False, s=None):
    """प्रकार: पूर्ण B/A < flat_only (0.90) ⇒ zigzag शक्य (0.618–0.90 दोन्ही). B, A-start पलीकडे ⇒ B/A > 1 ⇒ flat."""
    n = len(x) - 1
    if n >= 2:
        L = _L(x)
        b = L[1] / L[0] if L[0] else float("inf")
        if b >= float(s["zz_max_ba"]):                                         # B फक्त वाढू शकतो ⇒ चालू B सुद्धा
            return False, [], {}
    return True, [], {}


def flat(x, done=False, s=None):
    """प्रकार: पूर्ण B/A ≥ flat_min_ba (0.618). मजबूत: B ≤ 2A. उप-प्रकार C नंतर (identity मध्ये नाही)."""
    n = len(x) - 1
    if n < 2:
        return True, [], {"sub": "प्रलंबित"}
    L = _L(x)
    b = L[1] / L[0] if L[0] else float("inf")
    if _complete(n, 2, done) and b < float(s["flat_min_ba"]):
        return False, [], {}
    strong = ["flat B > 2A"] if b > float(s["flat_b_max"]) else []
    if n < 3:
        return True, strong, {"sub": "प्रलंबित"}
    d = _d(x)
    em = float(s["flat_expanded_min"])
    if b > em and beyond(x[3], x[1], d):
        sub = "expanded"
    elif b > 1.0 and not reached(x[3], x[1], d):
        sub = "running" if done else "प्रलंबित"
    else:
        sub = "regular" if (done or reached(x[3], x[1], d)) else "प्रलंबित"
    return True, strong, {"sub": sub}


def triangle(x, done=False, kind="contracting", barrier_tol=0.0, s=None):
    """प्रकार: contracting = D हा B च्या आत, E हा C च्या आत; expanding = C पलीकडे A, D पलीकडे B, E पलीकडे C. Barrier = B, D ≤ tol."""
    n = len(x) - 1
    if n < 2:
        return True, [], {"barrier": False}
    d = _d(x)
    if kind == "contracting":
        if n >= 4 and beyond(x[4], x[2], -d):
            return False, [], {}
        if n >= 5 and beyond(x[5], x[3], d):
            return False, [], {}
        return True, [], {"barrier": bool(n >= 4 and abs(x[4] - x[2]) <= barrier_tol)}
    if _complete(n, 3, done) and not beyond(x[3], x[1], d):
        return False, [], {}
    if _complete(n, 4, done) and not beyond(x[4], x[2], -d):
        return False, [], {}
    if _complete(n, 5, done) and not beyond(x[5], x[3], d):
        return False, [], {}
    return True, [], {"barrier": False}


def wedge(x, done=False, kind="contracting", s=None):
    """प्रकार: contracting (3 < 1, 4 < 2) / expanding (3 > 1, 4 > 2). मजबूत: 2 ≯ 1-start, 4 ≯ 2-end. "3 > 1-end" आणि "5 > 3-end" =
    guideline / पूर्णता (score). अपूर्ण wedge valid."""
    n = len(x) - 1
    if n < 2:
        return True, [], {}
    d = _d(x)
    L = _L(x)
    strong = []
    if beyond(x[2], x[0], -d):
        strong.append("wedge 2 पलीकडे 1-start")
    con = kind == "contracting"
    if n >= 3 and _complete(n, 3, done):
        if con and L[2] >= L[0]:
            return False, [], {}
        if not con and L[2] <= L[0]:
            return False, [], {}
    elif n >= 3 and con and L[2] >= L[0]:
        return False, [], {}                                                   # चालू 3 आधीच 1 इतका ⇒ contracting नाही (परत येत नाही)
    if n >= 4:
        if beyond(x[4], x[2], -d):
            strong.append("wedge 4 पलीकडे 2-end")
        if _complete(n, 4, done):
            if con and L[3] >= L[1]:
                return False, [], {}
            if not con and L[3] <= L[1]:
                return False, [], {}
        elif con and L[3] >= L[1]:
            return False, [], {}
    return True, strong, {}


def impulse_k(x, done=False, s=None):
    """Impulse-K (correction नाही): 2 ≯ 1-start, 3 > 1-end, 3 सगळ्यात लहान नाही, 4 ∉ 1, 5 > 3-end."""
    return R.impulse(x, done), [], {}


def wxy_strong(x, n, xl, d):
    """W-X-Y मजबूत पुरावा: X ≯ W-start; W चा C ≥ W चा A-end. ("≤ 1 zigzag": zz-X-zz = double zigzag हा वेगळा प्रकार ⇒
    combination मध्ये ती जोडी बनतच नाही.)"""
    out = []
    if n > 3 and not R.x_not_beyond_w(x[4:min(n, 3 + xl) + 1], x[0], d):
        out.append("X पलीकडे W-start")
    if n >= 3 and not reached(x[3], x[1], d):
        out.append("W चा C, W च्या A-end पर्यंत नाही")
    return out
