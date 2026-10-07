"""
elliott/pricing.py — E3: Black-Scholes (European index options) — model premium, delta, implied vol
------------------------------------------------------------------------------------------------
🎓 Backtest premium चा क्रम (उत्तर 4): (a) Upstox expired-options candles → (a2) NSE bhavcopy (दिवसाचा close/settle) + त्या
दिवसाच्या bhavcopy IV ने intraday BS → (b) फक्त BS ("model premium" ठळक). इथे BS चं गणित; data जोडणी E4 मध्ये.
वेळ: T = dte_frac / 252 (spec §8 चा trading-day convention — dist_vol सारखाच).
"""
import math

from statistics import NormalDist

_N = NormalDist()


def _d1d2(S, K, T, r, sig):
    v = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / v
    return d1, d1 - v


def price(S, K, T, r, sig, kind):
    """kind "CE"/"PE". T ≤ 0 किंवा sig ≤ 0 ⇒ intrinsic."""
    if T <= 0 or sig <= 0:
        return max(0.0, S - K) if kind == "CE" else max(0.0, K - S)
    d1, d2 = _d1d2(S, K, T, r, sig)
    df = math.exp(-r * T)
    if kind == "CE":
        return S * _N.cdf(d1) - K * df * _N.cdf(d2)
    return K * df * _N.cdf(-d2) - S * _N.cdf(-d1)


def delta(S, K, T, r, sig, kind):
    if T <= 0 or sig <= 0:
        itm = S > K if kind == "CE" else S < K
        return (1.0 if kind == "CE" else -1.0) if itm else 0.0
    d1, _ = _d1d2(S, K, T, r, sig)
    return _N.cdf(d1) if kind == "CE" else _N.cdf(d1) - 1.0


def implied_vol(px, S, K, T, r, kind, lo=1e-4, hi=5.0, tol=1e-6, it=100):
    """Bisection. Arbitrage मर्यादेबाहेर / T ≤ 0 ⇒ None."""
    if T <= 0 or px <= 0:
        return None
    intrinsic = max(0.0, S - K * math.exp(-r * T)) if kind == "CE" else max(0.0, K * math.exp(-r * T) - S)
    if px < intrinsic - 1e-9 or px >= (S if kind == "CE" else K):
        return None
    a, b = lo, hi
    if price(S, K, T, r, b, kind) < px:
        return None
    for _ in range(it):
        m = 0.5 * (a + b)
        if price(S, K, T, r, m, kind) < px:
            a = m
        else:
            b = m
        if b - a < tol:
            break
    return 0.5 * (a + b)


def spread_value(S, short_k, long_k, T, r, sig, kind, sig_long=None):
    """Credit spread बंद करण्याचा खर्च (short − long) — entry ला हाच credit."""
    return price(S, short_k, T, r, sig, kind) - price(S, long_k, T, r, sig if sig_long is None else sig_long, kind)
