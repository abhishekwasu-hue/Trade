"""opportunity_engine/measures.py — *मोजपट्टी* (किंमतीचा आकार मोजण्याचं साधन), indicator नाही.

🎓 `ref_range` = त्याच TF च्या शेवटच्या N closed **पूर्ण** bars चा `median(high − low)`.
  - smoothing नाही, true-range नाही, gap नाही, किंमतीच्या सरासरीवर आधारित काहीही नाही — फक्त `median`.
  - फक्त "अंतर / आकार" मोजण्यासाठी: `k × ref_range(...)` (tolerance, swing significance, displacement तुलना).
    कुठलाही entry/exit signal, crossover किंवा trend/direction निर्णय याच्यावरून नाही.
  - नेहमी scalar `float` (किंवा NaN) परत देतो — कधीच Series नाही. आवश्यक पूर्ण bars (`min_bars`) नसतील तर NaN.
`adr` = शेवटच्या N पूर्ण sessions चा median(high − low) (दैनिक range). तेही scalar.
guard tests (tests/test_opportunity_engine_guards.py): या फाइलमध्ये rolling/ewm/expanding/cumsum/diff/shift/mean वापर नाही; कुठल्याही
call-site वर `ref_range(...)`/`adr(...)` चा वापर फक्त गुणाकार/भागाकारात.
"""
import numpy as np


def _clean(values):
    arr = np.asarray(values, dtype="float64")
    return arr[np.isfinite(arr)]


def ref_range_from_ranges(ranges, n=20, min_bars=10):
    """`ranges` = (high − low) च्या पूर्ण bars ची (जुन्यापासून नवीनकडे) यादी. शेवटचे n चा median; < min_bars असतील तर NaN."""
    n = int(n)
    arr = _clean(ranges[-(4 * n):])          # लांब इतिहासाची प्रत टाळण्यासाठी आधी शेपूट; NaN वगळून शेवटचे n
    if len(arr) < int(min_bars):
        return float("nan")
    return float(np.median(arr[-n:]))


def ref_range(df, n=20, min_bars=10):
    """df (closed bars; high, low आणि ऐच्छिक `bar_is_full`) -> scalar ref_range. अपूर्ण bars (bar_is_full == False) वगळले जातात."""
    if df is None or len(df) == 0:
        return float("nan")
    d = df
    if "bar_is_full" in d.columns:
        d = d[d["bar_is_full"].astype(bool)]
    if len(d) == 0:
        return float("nan")
    return ref_range_from_ranges((d["high"] - d["low"]).values, n, min_bars)


def adr(daily_df, n=14, min_days=5):
    """शेवटच्या n पूर्ण sessions चा median(high − low) — scalar. `bar_is_full` असेल तर लहान/अपूर्ण sessions वगळले जातात."""
    if daily_df is None or len(daily_df) == 0:
        return float("nan")
    d = daily_df
    if "bar_is_full" in d.columns:
        d = d[d["bar_is_full"].astype(bool)]
    return ref_range_from_ranges((d["high"] - d["low"]).values, n, min_days)
