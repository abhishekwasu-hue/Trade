"""
price_action/level_validation.py
--------------------------------
🎓 T3 — Osler पद्धत: levels खरंच "काम करतात" का, हे यादृच्छिक (random) levels शी तुलना करून तपासणं. फक्त मोजमाप/अहवाल.

  • `bounce_outcome` — zone (as-of माहीत) ला पहिला स्पर्श झाल्यावर, पुढच्या `n_bars` मध्ये close दूरच्या कडेपलीकडे जाण्याआधी zone पासून
    `bounce_mr × median_range` इतका close-अंतराने दूर गेला ⇒ BOUNCE; आधी पलीकडे close ⇒ BREAK; दोन्ही नाही ⇒ NONE.
    स्पर्शाचा bar स्वतः bounce मोजत नाही (तो zone कडे येणाराच bar). एकाच bar मध्ये break आणि bounce ⇒ BREAK (सावध).
  • `random_zones` — प्रत्येक खऱ्या zone साठी k यादृच्छिक zones: तीच रुंदी, अंतर त्या engine च्या खऱ्या अंतरांच्या (pooled) वितरणातून, बाजू यादृच्छिक.
  • `option_breach` — short strike (zone ची दूरची कड) 5 सत्रांत तोडली का (कोणत्याही दिवशी low/high ने स्पर्श, आणि 5व्या दिवशी close पलीकडे).
"""
import math

import numpy as np
import pandas as pd

BOUNCE, BREAK, NONE = "BOUNCE", "BREAK", "NONE"


def bounce_outcome(h, l, c, lo, hi, side, a, b, n_bars, mr, bounce_mr=1.0):
    """bars a..b मध्ये पहिला स्पर्श शोधतो; outcome त्यानंतरच्या n_bars मध्ये (b नंतरचेही चालतील — परिणाम मोजायला). side +1 support / −1 resistance.
    रिटर्न dict: touched, touch_bar, outcome, react_mr (touch bar च्या n_bars नंतरचा close − कड, side दिशेने, ÷ mr)."""
    n = len(c)
    b = min(b, n - 1)
    for k in range(max(a, 0), b + 1):
        if (l[k] <= hi) if side > 0 else (h[k] >= lo):
            m = mr[k] if np.isfinite(mr[k]) and mr[k] > 0 else np.nan
            if not np.isfinite(m):
                return {"touched": False, "touch_bar": None, "outcome": NONE, "react_mr": np.nan}
            edge = hi if side > 0 else lo
            out = NONE
            if (c[k] < lo) if side > 0 else (c[k] > hi):
                out = BREAK
            else:
                for j in range(k + 1, min(k + n_bars, n - 1) + 1):
                    if (c[j] < lo) if side > 0 else (c[j] > hi):
                        out = BREAK
                        break
                    if (c[j] - edge) * side >= bounce_mr * m:
                        out = BOUNCE
                        break
            j_end = min(k + n_bars, n - 1)
            return {"touched": True, "touch_bar": k, "outcome": out, "react_mr": float((c[j_end] - edge) * side / m)}
    return {"touched": False, "touch_bar": None, "outcome": NONE, "react_mr": np.nan}


def random_zones(price, width, dist_pool, k, rng):
    """k यादृच्छिक zones: [{"low","high","side"}] — मध्य किंमतीपासून |अंतर| (dist_pool मधून, % मध्ये) वर/खाली (बाजू यादृच्छिक)."""
    out = []
    pool = np.abs(np.asarray(dist_pool, float))
    pool = pool[np.isfinite(pool) & (pool > 0)]
    if not len(pool):
        return out
    for _ in range(k):
        d = float(rng.choice(pool)) * price / 100.0
        s = 1 if rng.random() < 0.5 else -1                  # +1 = support (किंमतीखाली)
        mid = price - s * d
        lo, hi = mid - width / 2, mid + width / 2
        if lo <= price <= hi:
            continue
        out.append({"low": lo, "high": hi, "side": s})
    return out


def rate(outcomes):
    o = [x for x in outcomes if x is not None]
    return (sum(1 for x in o if x == BOUNCE) / len(o)) if o else np.nan


def two_prop_z(k1, n1, k2, n2):
    if min(n1, n2) < 5:
        return np.nan
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se > 0 else np.nan


def option_breach(daily, i, strike, side, hold=5):
    """daily (date-क्रम, open/high/low/close) मध्ये दिवस i च्या open ला short strike (side +1 = put खाली, −1 = call वर). पुढचे `hold` सत्र (i…i+hold−1).
    रिटर्न (touch_breach, close_breach) किंवा None (डेटा अपुरा)."""
    if i + hold - 1 >= len(daily):
        return None
    w = daily.iloc[i:i + hold]
    if side > 0:
        return bool((w["low"] < strike).any()), bool(w["close"].iloc[-1] < strike)
    return bool((w["high"] > strike).any()), bool(w["close"].iloc[-1] > strike)


def logistic_fit(X, y, l2=1.0, iters=300):
    """साधी L2 logistic regression (Newton) — numpy फक्त. X standardised असावं. रिटर्न (coef, intercept)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, p = X.shape
    Xb = np.c_[np.ones(n), X]
    w = np.zeros(p + 1)
    reg = np.eye(p + 1) * l2
    reg[0, 0] = 0.0
    for _ in range(iters):
        z = np.clip(Xb @ w, -30, 30)
        pr = 1 / (1 + np.exp(-z))
        g = Xb.T @ (pr - y) + reg @ w
        H = (Xb * (pr * (1 - pr))[:, None]).T @ Xb + reg
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w[1:], w[0]
