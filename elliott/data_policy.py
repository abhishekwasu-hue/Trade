"""
elliott/data_policy.py
----------------------
🎓 कोणता काळ कशासाठी वापरता येतो — एकाच ठिकाणी, म्हणजे कुठलंही script चुकून sealed holdout उघडत नाही.

  IS            2015-01-01 → 2021-12-31   सगळं calibration (options P&L फक्त weekly options सुरू झाल्यापासून)
  VAL           2022-01-01 → 2024-03-31   IS मध्ये निवडलेल्या ≤ 3 configs; tuning नाही
  HOLDOUT       2024-04-01 → पुढे        sealed — फक्त शेवटी एकदाच, अंतिम एका config साठी
  CONTAMINATED  2026-07-01 → 2026-10-06   golden-file regression (Abhi चे screenshots याच काळाचे; logic इथूनच ठरलं).
                                          फक्त purpose="golden" साठी; अंतिम holdout चाचणीतूनही **वगळायचा** (Abhi, 2026-10-06).
"""
import datetime as dt

import pandas as pd

IS_START = pd.Timestamp("2015-01-01")
IS_END = pd.Timestamp("2021-12-31 23:59:59")
VAL_START = pd.Timestamp("2022-01-01")
VAL_END = pd.Timestamp("2024-03-31 23:59:59")
HOLDOUT_START = pd.Timestamp("2024-04-01")
CONTAMINATED_START = pd.Timestamp("2026-07-01")
CONTAMINATED_END = pd.Timestamp("2026-10-06 23:59:59")
# सीमा नेहमी exclusive (`< पुढचा दिवस`) — sub-second/तास कुठलाही असला तरी period() आणि check_range() एकच उत्तर देतात
_VAL_END_X = pd.Timestamp("2024-04-01")
_IS_END_X = pd.Timestamp("2022-01-01")
_CONT_END_X = pd.Timestamp("2026-10-07")

PURPOSES = ("research", "golden")


class HoldoutError(RuntimeError):
    """Sealed holdout (किंवा चुकीच्या कारणासाठी contaminated काळ) वापरण्याचा प्रयत्न."""


def period(ts):
    """एका वेळेचा काळ: "PRE_IS" / "IS" / "VAL" / "CONTAMINATED" / "HOLDOUT"."""
    t = pd.Timestamp(ts)
    if t < IS_START:
        return "PRE_IS"
    if t < _IS_END_X:
        return "IS"
    if t < _VAL_END_X:
        return "VAL"
    if CONTAMINATED_START <= t < _CONT_END_X:
        return "CONTAMINATED"
    return "HOLDOUT"


def allowed(ts, purpose="research"):
    """research ⇒ फक्त IS/VAL (आणि त्याआधीचा warm-up). golden ⇒ त्याशिवाय CONTAMINATED सुद्धा. HOLDOUT ⇒ कधीच नाही."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} — {PURPOSES} पैकी हवा")
    p = period(ts)
    if p in ("PRE_IS", "IS", "VAL"):
        return True
    return p == "CONTAMINATED" and purpose == "golden"


def check_range(start, end, purpose="research"):
    """[start, end] पूर्ण श्रेणी परवानगीत आहे का; नसेल तर HoldoutError (कुठला भाग का नाकारला ते सांगून)."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if e < s:
        raise ValueError("end < start")
    for lo, hi_x in ((HOLDOUT_START, CONTAMINATED_START), (_CONT_END_X, pd.Timestamp.max)):
        if s < hi_x and e >= lo:
            raise HoldoutError(f"{s.date()}→{e.date()} sealed HOLDOUT ला छेदतो ({lo.date()} नंतर) — परवानगी नाही")
    if s < _CONT_END_X and e >= CONTAMINATED_START and purpose != "golden":
        raise HoldoutError(f"{s.date()}→{e.date()} contaminated golden काळ ({CONTAMINATED_START.date()}→"
                           f"{CONTAMINATED_END.date()}) — फक्त purpose='golden'")
    return True


def filter_allowed(df, purpose="research", col="timestamp"):
    """DataFrame मधून परवानगी नसलेल्या ओळी काढतो (वापरापूर्वी शेवटचा पहारा)."""
    ts = pd.to_datetime(df[col])
    keep = ts < _VAL_END_X
    if purpose == "golden":
        keep |= (ts >= CONTAMINATED_START) & (ts < _CONT_END_X)
    return df[keep.to_numpy()].reset_index(drop=True)


HOLDOUT_FILES = {"nifty50_daily_extension.parquet"}      # 2024-03-28 → 2026-08-20 (#225) — पूर्ण holdout काळ


def load_parquet(path, purpose="research", col="timestamp"):
    """Elliott / research loader: holdout-only files वाचायलाच नकार (HoldoutError), बाकी वाचून filter_allowed (F11)."""
    import os
    if os.path.basename(str(path)) in HOLDOUT_FILES:
        raise HoldoutError(f"{os.path.basename(str(path))} हा sealed holdout काळ आहे — elliott/research मध्ये वाचायचा नाही")
    return filter_allowed(pd.read_parquet(path), purpose, col)


def final_holdout_mask(ts):
    """अंतिम holdout चाचणीसाठी वापरायच्या वेळा: HOLDOUT पण CONTAMINATED नाही (Abhi: contaminated काळ तिथूनही वगळा)."""
    t = pd.to_datetime(pd.Series(ts))
    return ((t >= HOLDOUT_START) & ~((t >= CONTAMINATED_START) & (t < _CONT_END_X))).to_numpy()


def default_download_ranges():
    """VPS वर डाउनलोड करायच्या श्रेणी: IS/VAL (weekly options 2019 पासून, थोडा आधीचा भाग पडताळणीसाठी) + golden काळ."""
    return [(dt.date(2018, 12, 1), dt.date(2024, 3, 31), "research"),
            (CONTAMINATED_START.date(), CONTAMINATED_END.date(), "golden")]
