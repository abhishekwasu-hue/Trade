"""
elliott/breaks.py — "खरा break" (spec §7, §14 Q1): count invalidation आणि (E3) exits एकाच व्याख्येवर
--------------------------------------------------------------------------------------------------
🎓 आकडे नाहीत, बाजाराचा स्वतःचा noise आणि ताकद:
  MR  = median(high−low) of मागचे median_range_n **बंद** bars (चालू bar वगळून)
  buf = break_buffer_mr × MR
  Candidate: bar t चा close level च्या पलीकडे buf ने (side "below": close < L − buf; "above": close > L + buf)
  Real break confirmed (जे आधी):
    (a) Displacement: bar t स्वतः ताकदीचा (range ≥ strength_min × MR) आणि close break-दिशेच्या टोकाच्या break_close_loc भागात
        ⇒ t वर confirm (break_displacement_confirm).
    (b) Acceptance: पुढचे break_no_reclaim_bars bars सुद्धा level च्या पलीकडेच close (reclaim नाही) ⇒ शेवटच्या bar वर confirm.
        (0 ⇒ एका close वर — तुलनेसाठीच.)
    (c) Failed retest: break नंतर level चा retest उलट logical reversal ने नाकारला ⇒ confirm — logical reversal (E2) लागतो, म्हणून
        `retest_fn` hook (E2 मध्ये जोडतो; तोपर्यंत None).
  अन्यथा (wick, किंवा कमकुवत close मग reclaim) ⇒ false break: candidate रद्द, exit/invalidation नाही.
Causal: confirm index c ठरवायला फक्त bars ≤ c वापरतो ⇒ "t ला तुटलेलं?" = c ≤ t (truncation invariant).
"""
import numpy as np
import pandas as pd


def median_range(frame, n):
    """bar i वर: bars [i−n … i−1] च्या (high−low) चा median (चालू bar वगळून). पहिल्या n bars ला NaN."""
    rng = (frame["high"].astype(float) - frame["low"].astype(float))
    return rng.shift(1).rolling(n, min_periods=n).median().to_numpy(float)


def _beyond(close, level, buf, side):
    return close < level - buf if side == "below" else close > level + buf


def _back_inside(close, level, side):
    return close >= level if side == "below" else close <= level


def first_real_break(frame, start, level, side, s, mr=None, end=None, retest_fn=None):
    """[start, end] मध्ये level च्या पहिल्या **खऱ्या** break चा confirm index (नाहीतर None).
    side: "below" (भाव level च्या खाली तुटणं — bull put/up-count साठी धोका) / "above"."""
    if side not in ("below", "above"):
        raise ValueError("side below/above")
    h, l, c = (frame[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(c)
    end = n - 1 if end is None else min(end, n - 1)
    mr = median_range(frame, s["median_range_n"]) if mr is None else mr
    k = s["break_no_reclaim_bars"]
    t = max(start, 0)
    while t <= end:
        m = mr[t]
        if not np.isfinite(m) or not _beyond(c[t], level, s["break_buffer_mr"] * m, side):
            t += 1
            continue
        rng = h[t] - l[t]
        if s["break_displacement_confirm"] and rng >= s["strength_min"] * m and rng > 0:
            loc = (c[t] - l[t]) / rng if side == "below" else (h[t] - c[t]) / rng     # break-दिशेच्या टोकापासून अंतर
            if loc <= s["break_close_loc"]:
                return t                                                              # (a) displacement
        if k == 0:
            return t
        ok, j = True, t
        for j in range(t + 1, t + k + 1):
            if j > end:
                return None                                                           # अजून ठरलं नाही (भविष्य नाही)
            if _back_inside(c[j], level, side):
                ok = False
                break
            mj, rj = mr[j], h[j] - l[j]
            if (s["break_displacement_confirm"] and np.isfinite(mj) and rj > 0 and rj >= s["strength_min"] * mj
                    and _beyond(c[j], level, s["break_buffer_mr"] * mj, side)
                    and ((c[j] - l[j]) / rj if side == "below" else (h[j] - c[j]) / rj) <= s["break_close_loc"]):
                return j                                                              # window मधली displacement — "जे आधी"
        if ok:
            return t + k                                                              # (b) acceptance
        if retest_fn is not None:
            r = retest_fn(frame, t, level, side, end)
            if r is not None:
                return r                                                              # (c) failed retest (E2)
        t = j + 1 if not ok else t + 1                                                # false break ⇒ reclaim नंतरपासून पुन्हा
    return None


def first_wick_break(frame, start, level, side, end=None):
    """Strict EWP basis: wick level च्या पलीकडे गेली की लगेच (count_inv_basis = wick)."""
    x = frame["low"].to_numpy(float) if side == "below" else frame["high"].to_numpy(float)
    end = len(x) - 1 if end is None else min(end, len(x) - 1)
    for t in range(max(start, 0), end + 1):
        if (x[t] < level) if side == "below" else (x[t] > level):
            return t
    return None


class BreakCache:
    """(level, side, start, basis) → पहिला confirm index, **फक्त t_idx पर्यंत** scan करून (भविष्यातले bars कधीच वाचत नाही).
    सापडलेला confirm index कायमचा (तो फक्त ≤ स्वतःच्या bars वरून ठरतो); "अजून नाही" असेल तर नंतरच्या मोठ्या t साठी पुन्हा scan
    (start पासून — range म्हणजे फक्त चालू wave, लहान)."""

    def __init__(self, frame, s):
        self.frame, self.s = frame, s
        self.mr = median_range(frame, s["median_range_n"])
        self._found = {}           # key → confirm index
        self._clear = {}           # key → इथपर्यंत तपासलं, break नाही

    def broken_by(self, start, level, side, t_idx):
        return self.confirm_index(start, level, side, t_idx) is not None

    def confirm_index(self, start, level, side, t_idx):
        """t_idx पर्यंत confirm झालेल्या खऱ्या break चा index (नसेल ⇒ None)."""
        key = (int(start), round(float(level), 6), side, self.s["count_inv_basis"])
        c = self._found.get(key)
        if c is not None:
            return c if c <= t_idx else None
        if self._clear.get(key, -1) >= t_idx:
            return None
        if self.s["count_inv_basis"] == "wick":
            c = first_wick_break(self.frame, start, level, side, end=t_idx)
        else:
            c = first_real_break(self.frame, start, level, side, self.s, mr=self.mr, end=t_idx)
        if c is None:
            self._clear[key] = t_idx
            return None
        self._found[key] = c
        return c if c <= t_idx else None


def frame_index_at(frame, t):
    """`t` पर्यंत संपलेला शेवटचा bar (bar_end ≤ t) चा index; नसेल तर −1."""
    return int(np.searchsorted(frame["bar_end"].to_numpy(), np.datetime64(pd.Timestamp(t)), side="right")) - 1
