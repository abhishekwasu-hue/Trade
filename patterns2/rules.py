"""patterns2/rules.py — पक्के नियम (Tier A + आजचे code gates), शुद्ध फंक्शन्स: फक्त wave-टोकांच्या किंमती.

`elliott/patterns.build` मधले नियम settings / ATR / real-break callback / CountNode शी गुंतलेले आहेत (शुद्ध नाहीत) ⇒ इथे त्याच व्याख्या
पुन्हा लिहिल्या (थर 3 prompt §10.2); tests मध्ये दोघांची तुलना (एकच उत्तर). फरक (Abhi च्या §3.7 यादीत): flat B/A > 2.0 इथे gate नाही
(m 0.2), triangle मध्ये "C, A च्या आत" अट नाही, wedge चा truncation gate.

x = [x0, x1, …, xn] = wave-टोकांच्या किंमती (n waves हजर). done = शेवटचा (n-वा) wave पूर्ण झाला का. शेवटचा wave चालू असेल तर फक्त
न बदलणारे (irrevocable) नियम तपासले जातात — बाकीचे तो wave पूर्ण झाल्यावर. d = पहिल्या wave ची दिशा.
"""


def beyond(a, b, dirn):
    """a हा b च्या पलीकडे, dirn दिशेने (बरोबरी = पलीकडे नाही)."""
    return (a - b) * dirn > 0


def _d(x):
    return 1 if x[1] > x[0] else -1


def _L(x):
    return [abs(x[i + 1] - x[i]) for i in range(len(x) - 1)]


def _complete(n, k, done):
    """wave k (1-based) पूर्ण: त्यानंतर wave आहे, किंवा तो शेवटचा आणि done."""
    return n > k or (n == k and done)


def zigzag(x, done=False):
    """R6: B हा A च्या सुरुवातीपलीकडे नाही. C ने A गाठलं नाही ⇒ invalid नाही (अवस्था)."""
    n = len(x) - 1
    if n < 2:
        return True
    d = _d(x)
    return not beyond(x[2], x[0], -d)


def flat(x, done=False, b_min=0.90, exp_min=1.05):
    """R7: पूर्ण B ≥ b_min × A. रिटर्न (valid, उप-प्रकार). उप-प्रकार C हजर झाल्यावर (तोपर्यंत "प्रलंबित")."""
    n = len(x) - 1
    if n < 2:
        return True, "प्रलंबित"
    L = _L(x)
    b = L[1] / L[0] if L[0] else float("inf")
    if _complete(n, 2, done) and b < b_min:
        return False, None
    if n < 3:
        return True, "प्रलंबित"
    d = _d(x)
    if reached(x[3], x[1], d):                                     # C हजर (A चं टोक गाठलं / पलीकडे)
        return True, ("expanded" if b > exp_min and beyond(x[3], x[1], d) else "regular")
    if not done:
        return True, "प्रलंबित"                                    # C चालू, A गाठलं नाही ⇒ उप-प्रकार अजून ठरत नाही
    return True, ("running" if b > 1.0 else "regular")


def triangle(x, done=False, kind="contracting", barrier_tol=0.0):
    """Contracting: D हा B च्या आत, E हा C च्या आत (R8; "C, A च्या आत" अट नाही). Expanding: C, A पलीकडे; D, B पलीकडे; E, C पलीकडे.
    रिटर्न (valid, barrier?)."""
    n = len(x) - 1
    if n < 2:
        return True, False
    d = _d(x)
    if kind == "contracting":
        if n >= 4 and beyond(x[4], x[2], -d):
            return False, False
        if n >= 5 and beyond(x[5], x[3], d):
            return False, False
        return True, bool(n >= 4 and abs(x[4] - x[2]) <= barrier_tol)
    if _complete(n, 3, done) and not beyond(x[3], x[1], d):
        return False, False
    if _complete(n, 4, done) and not beyond(x[4], x[2], -d):
        return False, False
    if _complete(n, 5, done) and not beyond(x[5], x[3], d):
        return False, False
    return True, False


def wedge(x, done=False, kind="contracting"):
    """2 ≯ 1 ची सुरुवात; 3 पलीकडे 1 चं टोक; 4 ≯ 2 चं टोक; contracting 3<1, 4<2, 5<3 / expanding 3>1, 4>2, 5>3; 5 पलीकडे 3 चं टोक
    (truncation नाही — §3.7 यादीत)."""
    n = len(x) - 1
    if n < 2:
        return True
    d = _d(x)
    L = _L(x)
    if beyond(x[2], x[0], -d):
        return False
    if _complete(n, 3, done) and not beyond(x[3], x[1], d):
        return False
    con = kind == "contracting"
    if n >= 3:
        if con and L[2] >= L[0]:
            return False
        if not con and _complete(n, 3, done) and L[2] <= L[0]:
            return False
    if n >= 4:
        if beyond(x[4], x[2], -d):
            return False
        if con and L[3] >= L[1]:
            return False
        if not con and _complete(n, 4, done) and L[3] <= L[1]:
            return False
    if n >= 5:
        if con and L[4] >= L[2]:
            return False
        if not con and _complete(n, 5, done) and L[4] <= L[2]:
            return False
        if _complete(n, 5, done) and not beyond(x[5], x[3], d):
            return False
    return True


def impulse(x, done=False):
    """Tier A: 2 ≯ 1 ची सुरुवात; 3 पलीकडे 1 चं टोक; 3 सगळ्यात लहान नाही; 4 हा 1 च्या पट्ट्यात नाही; 5 पलीकडे 3 चं टोक."""
    n = len(x) - 1
    if n < 2:
        return True
    d = _d(x)
    L = _L(x)
    if beyond(x[2], x[0], -d):
        return False
    if _complete(n, 3, done) and not beyond(x[3], x[1], d):
        return False
    if n >= 4 and not beyond(x[4], x[1], d):
        return False
    if n >= 5:
        if L[2] < L[0] and L[4] > L[2]:
            return False
        if _complete(n, 5, done) and not beyond(x[5], x[3], d):
            return False
    return True


def x_not_beyond_w(xs_x, w_start, d):
    """W-X-Y: X चा कोणताही बिंदू W च्या सुरुवातीपलीकडे (X च्या दिशेने) नाही (आजचा wxy नियम)."""
    return not any(beyond(v, w_start, -d) for v in xs_x)


def reached(c_end, a_end, d):
    """C ने A चं टोक गाठलं (बरोबरी सुद्धा)."""
    return (c_end - a_end) * d >= 0
