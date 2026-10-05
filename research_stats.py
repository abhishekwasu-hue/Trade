"""
research_stats.py
-----------------
🎓 संशोधनासाठी सांख्यिकी साधनं (फक्त अहवाल; कुठलाही bot/order/DB संबंध नाही). T1 (H1–H5) आणि पुढे T3 (level/leg validation) दोन्ही इथूनच वापरतात.

  • `sharpe(r)`                    — प्रति-ट्रेड/प्रति-दिवस mean ÷ std (annualise नाही).
  • `deflated_sharpe(...)`         — Bailey & López de Prado (2014) Deflated Sharpe Ratio: अनेक trials मधून "सर्वोत्तम" निवडल्याचा फायदा वजा करून,
                                    खरा SR > 0 असण्याची संभाव्यता (0–1). skew/kurtosis (non-normal returns) सुधारणा सह.
  • `pbo_cscv(M, S=16)`           — Probability of Backtest Overfitting (Bailey, Borwein, López de Prado, Zhu 2015), CSCV पद्धत:
                                    T×N matrix (rows = काळ, columns = trials) S गटांत; प्रत्येक S/2 संयोगावर IS-सर्वोत्तम trial चा OOS rank;
                                    logit ≤ 0 (OOS मध्ये median पेक्षा खाली) असण्याचं प्रमाण = PBO. PBO > 0.05 ⇒ घटक नाकारा (T3 नियम).
  • `shuffle_pvalue(...)`         — shuffled-returns permutation test: निवड-नियमाचा फायदा योगायोगाने येण्याची p-value.

scipy नाही — फक्त numpy + stdlib `statistics.NormalDist` (requirements बदलत नाहीत).
"""
import itertools
import math
from statistics import NormalDist

import numpy as np

_N = NormalDist()
EULER_GAMMA = 0.5772156649015329


def _clean(r):
    a = np.asarray(r, dtype=float)
    return a[np.isfinite(a)]


def sharpe(r):
    """mean ÷ std (ddof=1). < 2 नमुने किंवा std = 0 ⇒ 0.0."""
    a = _clean(r)
    if len(a) < 2:
        return 0.0
    sd = a.std(ddof=1)
    return float(a.mean() / sd) if sd > 0 else 0.0


def moments(r):
    """(skew, kurtosis — normal = 3). < 3 नमुने ⇒ (0, 3)."""
    a = _clean(r)
    if len(a) < 3:
        return 0.0, 3.0
    m, sd = a.mean(), a.std(ddof=0)
    if sd == 0:
        return 0.0, 3.0
    z = (a - m) / sd
    return float((z ** 3).mean()), float((z ** 4).mean())


def expected_max_sharpe(n_trials, var_sr):
    """N स्वतंत्र trials (खरा SR = 0) मधून अपेक्षित कमाल SR — DSR चा benchmark SR0."""
    if n_trials <= 1 or var_sr <= 0:
        return 0.0
    sd = math.sqrt(var_sr)
    return float(sd * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1.0 / n_trials) + EULER_GAMMA * _N.inv_cdf(1 - 1.0 / (n_trials * math.e))))


def deflated_sharpe(r, trial_sharpes):
    """`r` = निवडलेल्या trial चे returns (प्रति-ट्रेड/दिवस), `trial_sharpes` = सर्व trials चे SR (त्याच एककात). रिटर्न dict:
    sr, sr0 (अपेक्षित कमाल), dsr (P[खरा SR > sr0], 0–1), n, n_trials. DSR ≥ 0.95 ⇒ निवड overfitting पलीकडे टिकते."""
    a = _clean(r)
    srs = _clean(trial_sharpes)
    n, nt = len(a), max(len(srs), 1)
    sr = sharpe(a)
    var_sr = float(srs.var(ddof=1)) if len(srs) > 1 else 0.0
    sr0 = expected_max_sharpe(nt, var_sr)
    skew, kurt = moments(a)
    if n < 3:
        return {"sr": round(sr, 4), "sr0": round(sr0, 4), "dsr": None, "n": n, "n_trials": nt}
    denom = 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr
    if denom <= 0:
        return {"sr": round(sr, 4), "sr0": round(sr0, 4), "dsr": None, "n": n, "n_trials": nt}
    z = (sr - sr0) * math.sqrt(n - 1) / math.sqrt(denom)
    return {"sr": round(sr, 4), "sr0": round(sr0, 4), "dsr": round(float(_N.cdf(z)), 4), "n": n, "n_trials": nt}


def pbo_cscv(M, S=16, metric=None):
    """CSCV PBO. `M` = T×N (rows काळानुसार क्रमाने, columns = trials). `metric(block_matrix) -> N scores` (डीफॉल्ट: column-wise Sharpe).
    रिटर्न dict: pbo, n_splits, logits (list), N, T. N < 2 किंवा T < S ⇒ pbo None."""
    M = np.asarray(M, dtype=float)
    if M.ndim != 2:
        raise ValueError("M 2-D असावा (T × N)")
    T, N = M.shape
    if N < 2 or T < S or S < 2 or S % 2:
        return {"pbo": None, "n_splits": 0, "logits": [], "N": N, "T": T}
    metric = metric or _col_sharpe
    groups = np.array_split(np.arange(T), S)
    logits = []
    for is_ids in itertools.combinations(range(S), S // 2):
        is_set = set(is_ids)
        is_rows = np.concatenate([groups[g] for g in is_ids])
        oos_rows = np.concatenate([groups[g] for g in range(S) if g not in is_set])
        is_score, oos_score = metric(M[is_rows]), metric(M[oos_rows])
        best = int(np.argmax(is_score))
        rank = 1 + int((oos_score < oos_score[best]).sum()) + 0.5 * int((oos_score == oos_score[best]).sum() - 1)   # 1..N (ties सरासरी)
        w = rank / (N + 1.0)
        logits.append(math.log(w / (1 - w)))
    lg = np.array(logits)
    return {"pbo": round(float((lg <= 0).mean()), 4), "n_splits": len(lg), "logits": lg.tolist(), "N": N, "T": T}


def _col_sharpe(B):
    mu = B.mean(axis=0)
    sd = B.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(sd > 0, mu / sd, 0.0)
    return out


def shuffle_pvalue(stat_fn, x, y, n_perm=1000, seed=0):
    """Permutation test: `stat_fn(x, y)` खरा आकडा; `y` (उदा. पुढचे returns) shuffle करून `n_perm` वेळा पुन्हा. रिटर्न (stat, p_value) —
    p = P[shuffled ≥ खरा] (एकतर्फी, +1 सुधारणा). `seed` स्थिर ⇒ पुनरुत्पादनक्षम."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    real = float(stat_fn(x, y))
    hits = sum(1 for _ in range(n_perm) if float(stat_fn(x, rng.permutation(y))) >= real)
    return real, (hits + 1.0) / (n_perm + 1.0)
