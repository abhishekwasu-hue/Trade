"""
elliott/data_policy.py
----------------------
🎓 कोणता काळ कशासाठी वापरता येतो — एकाच ठिकाणी, म्हणजे कुठलंही script चुकून sealed holdout उघडत नाही.

  IS            2015-01-01 → 2021-12-31   सगळं calibration (options P&L फक्त weekly options सुरू झाल्यापासून)
  VAL           2022-01-01 → 2024-03-31   IS मध्ये निवडलेल्या ≤ 3 configs; tuning नाही
  HOLDOUT       2024-04-01 → 2026-06-30   sealed — फक्त शेवटी एकदाच, अंतिम एका config साठी (कधीच उघडायचा नाही)
  CONTAMINATED  2026-07-01 → 2026-10-08   golden-file regression (Abhi चे screenshots याच काळाचे; logic इथूनच ठरलं).
                                          फक्त purpose="golden" / "annotation" साठी; अंतिम holdout चाचणीतूनही **वगळायचा** (Abhi, 2026-10-06).
                                          7–8 Oct जोडले (Abhi, 2026-10-08): Chart Reader ची "golden story" — फक्त illustration, tuning नाही.
  ILLUSTRATION  2026-10-09 → पुढे        (Abhi, 2026-10-09) annotation सराव / Abhi ची तपासणी आणि golden illustration साठीचे नवे दिवस
                                          (Jul–Oct 2026 सारखे). फक्त purpose="annotation" (annotation / vision तपासणी, Abhi पाहतो);
                                          golden backtest / IS / VAL / research साठी **कधीच नाही**, आणि अंतिम holdout चाचणीतही नाही.
"""
import datetime as dt

import pandas as pd

IS_START = pd.Timestamp("2015-01-01")
IS_END = pd.Timestamp("2021-12-31 23:59:59")
VAL_START = pd.Timestamp("2022-01-01")
VAL_END = pd.Timestamp("2024-03-31 23:59:59")
HOLDOUT_START = pd.Timestamp("2024-04-01")
CONTAMINATED_START = pd.Timestamp("2026-07-01")
CONTAMINATED_END = pd.Timestamp("2026-10-08 23:59:59")
# सीमा नेहमी exclusive (`< पुढचा दिवस`) — sub-second/तास कुठलाही असला तरी period() आणि check_range() एकच उत्तर देतात
_VAL_END_X = pd.Timestamp("2024-04-01")
_IS_END_X = pd.Timestamp("2022-01-01")
_CONT_END_X = pd.Timestamp("2026-10-09")

PURPOSES = ("research", "golden", "annotation")
ILLUSTRATION_START = _CONT_END_X                          # CONTAMINATED नंतरचा पहिला दिवस ⇒ open-ended
GOLDEN_LIKE = ("golden", "annotation")                    # CONTAMINATED फक्त यांना
ILLUSTRATION_ONLY = ("annotation",)                       # ILLUSTRATION फक्त याला (golden backtest scripts ना नवे दिवस नाहीत)


class HoldoutError(RuntimeError):
    """Sealed holdout (किंवा चुकीच्या कारणासाठी contaminated काळ) वापरण्याचा प्रयत्न."""


def period(ts):
    """एका वेळेचा काळ: "PRE_IS" / "IS" / "VAL" / "HOLDOUT" / "CONTAMINATED" / "ILLUSTRATION"."""
    t = pd.Timestamp(ts)
    if t < IS_START:
        return "PRE_IS"
    if t < _IS_END_X:
        return "IS"
    if t < _VAL_END_X:
        return "VAL"
    if CONTAMINATED_START <= t < _CONT_END_X:
        return "CONTAMINATED"
    if t >= ILLUSTRATION_START:
        return "ILLUSTRATION"
    return "HOLDOUT"


def allowed(ts, purpose="research"):
    """research ⇒ फक्त IS/VAL (आणि त्याआधीचा warm-up). golden ⇒ त्याशिवाय CONTAMINATED. annotation ⇒ CONTAMINATED + ILLUSTRATION.
    HOLDOUT ⇒ कधीच नाही."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} — {PURPOSES} पैकी हवा")
    p = period(ts)
    if p in ("PRE_IS", "IS", "VAL"):
        return True
    if p == "CONTAMINATED":
        return purpose in GOLDEN_LIKE
    return p == "ILLUSTRATION" and purpose in ILLUSTRATION_ONLY


def check_range(start, end, purpose="research"):
    """[start, end] पूर्ण श्रेणी परवानगीत आहे का; नसेल तर HoldoutError (कुठला भाग का नाकारला ते सांगून)."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if e < s:
        raise ValueError("end < start")
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} — {PURPOSES} पैकी हवा")
    if s < CONTAMINATED_START and e >= HOLDOUT_START:
        raise HoldoutError(f"{s.date()}→{e.date()} sealed HOLDOUT ला छेदतो ({HOLDOUT_START.date()} → "
                           f"{(CONTAMINATED_START - pd.Timedelta(days=1)).date()}) — परवानगी नाही")
    if e >= CONTAMINATED_START and purpose not in GOLDEN_LIKE:
        raise HoldoutError(f"{s.date()}→{e.date()} contaminated golden काळ ({CONTAMINATED_START.date()}→{CONTAMINATED_END.date()}) — "
                           f"फक्त purpose {GOLDEN_LIKE}")
    if e >= ILLUSTRATION_START and purpose not in ILLUSTRATION_ONLY:
        raise HoldoutError(f"{s.date()}→{e.date()} illustration काळ ({ILLUSTRATION_START.date()} नंतर) — फक्त purpose "
                           f"{ILLUSTRATION_ONLY} (backtest / IS / VAL साठी नाही)")
    return True


def filter_allowed(df, purpose="research", col="timestamp"):
    """DataFrame मधून परवानगी नसलेल्या ओळी काढतो (वापरापूर्वी शेवटचा पहारा)."""
    ts = pd.to_datetime(df[col])
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} — {PURPOSES} पैकी हवा")
    keep = ts < _VAL_END_X
    if purpose in GOLDEN_LIKE:
        keep |= (ts >= CONTAMINATED_START) & (ts < ILLUSTRATION_START)
    if purpose in ILLUSTRATION_ONLY:
        keep |= ts >= ILLUSTRATION_START
    return df[keep.to_numpy()].reset_index(drop=True)


HOLDOUT_FILES = {"nifty50_daily_extension.parquet"}      # 2024-03-28 → 2026-08-20 (#225) — पूर्ण holdout काळ


def load_parquet(path, purpose="research", col="timestamp"):
    """Elliott / research loader: holdout-only files वाचायलाच नकार (HoldoutError), बाकी वाचून filter_allowed (F11)."""
    import os
    if os.path.basename(str(path)) in HOLDOUT_FILES:
        raise HoldoutError(f"{os.path.basename(str(path))} हा sealed holdout काळ आहे — elliott/research मध्ये वाचायचा नाही")
    return filter_allowed(pd.read_parquet(path), purpose, col)


def final_holdout_mask(ts):
    """अंतिम holdout चाचणीसाठी वापरायच्या वेळा: फक्त HOLDOUT (CONTAMINATED / ILLUSTRATION नाही — Abhi)."""
    t = pd.to_datetime(pd.Series(ts))
    return ((t >= HOLDOUT_START) & (t < CONTAMINATED_START)).to_numpy()


def default_download_ranges():
    """VPS वर डाउनलोड करायच्या श्रेणी: IS/VAL (weekly options 2019 पासून, थोडा आधीचा भाग पडताळणीसाठी) + golden काळ."""
    return [(dt.date(2018, 12, 1), dt.date(2024, 3, 31), "research"),
            (CONTAMINATED_START.date(), CONTAMINATED_END.date(), "golden")]
