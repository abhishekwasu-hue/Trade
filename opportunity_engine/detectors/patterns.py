"""opportunity_engine/detectors/patterns.py — price-only geometry: range box आणि triangle शोधणे (spec §4 D7/D8). कुठलाही indicator नाही.

🎓 No-lookahead: दोन्ही functions फक्त दिलेले bars (breakout bar च्या *आधीचे*) पाहतात. Linear fit (np.polyfit) ही swing points वरची रेषा (geometry) —
moving average/indicator नाही. सर्व आकारमान `k × ADR` किंवा `k × ref_range` (मोजपट्टी) स्वरूपात.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from signals import find_swings


@dataclass
class Box:
    top: float
    bottom: float
    start: int                  # window मधला पहिला bar index (दिलेल्या df मध्ये)
    end: int                    # शेवटचा bar index (breakout bar च्या आधीचा)
    touches_top: int
    touches_bottom: int
    kind: str = "BOX"           # BOX | OR

    @property
    def height(self):
        return self.top - self.bottom

    @property
    def mid(self):
        return (self.top + self.bottom) / 2.0

    @property
    def bars(self):
        return self.end - self.start + 1


def _visits(mask):
    """सलग True चे गट = वेगळे visits (touches)."""
    m = np.asarray(mask, dtype=bool)
    if not len(m):
        return 0
    return int(m[0]) + int(np.sum(m[1:] & ~m[:-1]))


def find_box(high, low, adr, min_bars=12, max_bars=36, max_adr=0.35, touch_frac=0.15, min_touches=2):
    """शेवटच्या bars मध्ये (high/low arrays — breakout bar वगळून) सर्वात लांब पात्र box. नसेल तर None.
    पात्र: उंची ≤ max_adr × ADR, वरच्या कडेला ≥ min_touches वेगळे touches आणि खालच्याला सुद्धा (touch = कडेपासून उंचीच्या touch_frac आत)."""
    n = len(high)
    if n < min_bars or adr is None or not np.isfinite(adr) or adr <= 0:
        return None
    hi, lo = np.asarray(high, float), np.asarray(low, float)
    for w in range(min(max_bars, n), min_bars - 1, -1):
        seg_h, seg_l = hi[n - w:], lo[n - w:]
        top, bottom = float(seg_h.max()), float(seg_l.min())
        h = top - bottom
        if h <= 0 or h > max_adr * adr:
            continue
        tt = _visits(seg_h >= top - touch_frac * h)
        tb = _visits(seg_l <= bottom + touch_frac * h)
        if tt >= min_touches and tb >= min_touches:
            return Box(top=top, bottom=bottom, start=n - w, end=n - 1, touches_top=tt, touches_bottom=tb)
    return None


@dataclass
class Triangle:
    kind: str                   # ASCENDING | DESCENDING | SYMMETRICAL
    m_hi: float
    b_hi: float
    m_lo: float
    b_lo: float
    x0: int                     # पहिल्या swing चा index
    width0: float               # x0 वरची रुंदी (सर्वात रुंद — measured move)
    apex: float                 # रेषा जिथे मिळतात तो x (inf असू शकतो)
    n_hi: int
    n_lo: int
    last_hi: float              # शेवटचा आतला swing high (short SL)
    last_lo: float              # शेवटचा आतला swing low (long SL)

    def upper(self, x):
        return self.m_hi * x + self.b_hi

    def lower(self, x):
        return self.m_lo * x + self.b_lo


def find_triangle(df, rr, max_bars=40, order=2, flat_k=0.05, min_conv=0.40, max_apex_frac=0.75):
    """df = breakout bar आधीचे bars (high/low). शेवटच्या `max_bars` मध्ये ≥ 2 swing highs आणि ≥ 2 swing lows; highs/lows वर स्वतंत्र रेषा.
    Ascending (highs सपाट, lows वाढते) · Descending (highs घटते, lows सपाट) · Symmetrical (highs घटते, lows वाढते). रुंदी ≥ min_conv कमी, आणि
    पुढचा bar (x = len(df)) apex च्या मार्गाच्या max_apex_frac आधी. नसेल तर None."""
    if rr is None or not np.isfinite(rr) or rr <= 0:
        return None
    seg = df.iloc[-max_bars:]
    n = len(seg)
    if n < 2 * order + 4:
        return None
    sh, sl = find_swings(seg, order=order)
    sh = [i for i in sh if i <= n - 1 - order][-4:]
    sl = [i for i in sl if i <= n - 1 - order][-4:]
    if len(sh) < 2 or len(sl) < 2:
        return None
    hi, lo = seg["high"].to_numpy(float), seg["low"].to_numpy(float)
    m_hi, b_hi = np.polyfit(np.array(sh, float), hi[sh], 1)
    m_lo, b_lo = np.polyfit(np.array(sl, float), lo[sl], 1)
    flat = flat_k * rr
    if abs(m_hi) <= flat and m_lo > flat:
        kind = "ASCENDING"
    elif m_hi < -flat and abs(m_lo) <= flat:
        kind = "DESCENDING"
    elif m_hi < -flat and m_lo > flat:
        kind = "SYMMETRICAL"
    else:
        return None
    x0 = float(min(sh[0], sl[0]))
    xn = float(n)                                               # breakout bar (पुढचा) चा x
    width0 = (m_hi * x0 + b_hi) - (m_lo * x0 + b_lo)
    width_n = (m_hi * (xn - 1) + b_hi) - (m_lo * (xn - 1) + b_lo)
    if width0 <= 0 or width_n <= 0 or width_n > (1.0 - min_conv) * width0:
        return None
    apex = (b_lo - b_hi) / (m_hi - m_lo) if m_hi != m_lo else float("inf")
    if not np.isfinite(apex) or apex <= x0 or xn > x0 + max_apex_frac * (apex - x0):
        return None
    return Triangle(kind=kind, m_hi=float(m_hi), b_hi=float(b_hi), m_lo=float(m_lo), b_lo=float(b_lo), x0=int(x0), width0=float(width0), apex=float(apex),
                    n_hi=len(sh), n_lo=len(sl), last_hi=float(hi[sh[-1]]), last_lo=float(lo[sl[-1]]))


def or_box(df, or_bars, adr, max_adr=0.35) -> Optional[Box]:
    """Opening Range = box चा विशेष प्रकार (touch-अट नाही)."""
    if len(df) < or_bars or adr is None or not np.isfinite(adr) or adr <= 0:
        return None
    seg = df.iloc[:or_bars]
    top, bottom = float(seg["high"].max()), float(seg["low"].min())
    if top - bottom <= 0 or top - bottom > max_adr * adr:
        return None
    return Box(top=top, bottom=bottom, start=0, end=or_bars - 1, touches_top=1, touches_bottom=1, kind="OR")


# ---------------------------------------------------------------------------------------------------------------------
# PR-4: trendline (D4/D5), flag आणि double top/bottom (D9)
# ---------------------------------------------------------------------------------------------------------------------
@dataclass
class Trendline:
    side: str                   # "support" (swing lows वर; line खाली close ⇒ तुटली) | "resistance" (swing highs वर)
    m: float                    # slope (प्रति bar)
    b: float                    # x = 0 वरचं मूल्य (दिलेल्या df च्या index मध्ये)
    a: int                      # पहिला anchor swing
    b_idx: int                  # दुसरा anchor swing
    touches: int                # anchors सकट line ला स्पर्श करणारे swings
    after_b: int                # B नंतरचे touches (D4: 0 ⇒ आत्ताचा तिसरा touch)
    between_ext: float          # A–B मधला विरुद्ध टोक (support: सर्वोच्च high) — target hint

    def at(self, x):
        return self.m * x + self.b


def find_trendline(df, rr, side, slope_sign, order=3, min_gap=5, max_slope_k=0.5, tol=None, min_touches=2):
    """df = बंद bars (high/low/close). `side` support|resistance, `slope_sign` +1 (वाढती) / −1 (घटती).
    नियम: A < B confirmed swings, B − A ≥ min_gap, 0 < slope·sign ≤ max_slope_k × rr, A पासून शेवटपर्यंत एकही close line पलीकडे नाही,
    touches ≥ min_touches. सर्वात नवीन B, आणि त्यासाठी सर्वात जुना (लांब line) वैध A. नसेल तर None."""
    if rr is None or not np.isfinite(rr) or rr <= 0 or len(df) < 2 * order + min_gap + 2:
        return None
    n = len(df)
    hi, lo, cl = df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float)
    sh, sl = find_swings(df, order=order)
    idx = [i for i in (sl if side == "support" else sh) if i <= n - 1 - order]
    y = lo if side == "support" else hi
    tol = 0.25 * rr if tol is None else tol
    for bi in range(len(idx) - 1, 0, -1):
        B = idx[bi]
        for A in idx[:bi]:
            if B - A < min_gap:
                break
            m = (y[B] - y[A]) / (B - A)
            if not (0 < m * slope_sign <= max_slope_k * rr):
                continue
            b0 = y[A] - m * A
            xs = np.arange(A, n)
            line = m * xs + b0
            broken = (cl[A:] < line - 1e-9).any() if side == "support" else (cl[A:] > line + 1e-9).any()
            if broken:
                continue
            pts = [i for i in idx if i >= A and abs(y[i] - (m * i + b0)) <= tol]
            if len(pts) < min_touches:
                continue
            ext = float(hi[A:B + 1].max()) if side == "support" else float(lo[A:B + 1].min())
            return Trendline(side=side, m=float(m), b=float(b0), a=int(A), b_idx=int(B), touches=len(pts), after_b=sum(1 for i in pts if i > B),
                             between_ext=ext)
    return None


@dataclass
class Flag:
    sign: int                   # +1 bull flag, −1 bear flag
    pole_start: int
    pole_end: int               # pole चे टोक (flag सुरू होण्याआधीचा bar)
    pole_len: float
    m: float                    # flag च्या वरच्या (bull) / खालच्या (bear) कडेची रेषा — breakout रेषा
    b: float
    flag_ext: float             # flag चा विरुद्ध टोक (bull: flag low) — SL
    bars: int

    def at(self, x):
        return self.m * x + self.b


def find_flag(df, rr, sign, pole_max=8, pole_k=2.0, min_bars=5, max_bars=20, max_retrace=0.5):
    """शेवटचे bars = flag (min_bars..max_bars), त्याआधी ≤ pole_max bars चा pole: हालचाल ≥ pole_k × rr × √bars (sign दिशेने).
    Flag: pole विरुद्ध (किंवा सपाट) channel — flag highs वरची रेषा slope ≤ 0 (bull), retracement ≤ max_retrace × pole, आणि flag मध्ये pole चं टोक
    ओलांडलं नाही. Breakout रेषा = flag highs (bull) / lows (bear) वरची fit. नसेल तर None."""
    if rr is None or not np.isfinite(rr) or rr <= 0:
        return None
    n = len(df)
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    for fb in range(min_bars, max_bars + 1):
        pe = n - fb - 1                                          # pole चं टोक
        if pe < 1:
            break
        top = hi[pe] if sign > 0 else lo[pe]
        f_hi, f_lo = hi[pe + 1:], lo[pe + 1:]
        if (f_hi.max() > top) if sign > 0 else (f_lo.min() < top):
            continue                                             # flag मध्ये pole चं टोक ओलांडलं ⇒ flag नाही
        for pb in range(1, pole_max + 1):
            ps = pe - pb
            if ps < 0:
                break
            start = lo[ps:pe + 1].min() if sign > 0 else hi[ps:pe + 1].max()
            pole = (top - start) * sign
            if pole < pole_k * rr * np.sqrt(pb + 1):
                continue
            retr = (top - f_lo.min()) / pole if sign > 0 else (f_hi.max() - top) / pole
            if retr > max_retrace:
                continue
            xs = np.arange(pe + 1, n, dtype=float)
            m, b0 = np.polyfit(xs, f_hi if sign > 0 else f_lo, 1)
            if m * sign > 0.05 * rr:
                continue                                         # channel pole च्याच दिशेने चढतोय ⇒ flag नाही
            return Flag(sign=sign, pole_start=int(ps), pole_end=int(pe), pole_len=float(pole), m=float(m), b=float(b0),
                        flag_ext=float(f_lo.min() if sign > 0 else f_hi.max()), bars=int(fb))
    return None


@dataclass
class Double:
    sign: int                   # +1 double bottom, −1 double top
    first: int
    second: int
    level: float                # दोन lows/highs पैकी टोकाचा (SL त्याच्या पलीकडे)
    neckline: float             # मधला peak (bottom) / trough (top)

    @property
    def height(self):
        return abs(self.neckline - self.level)


def find_double(df, rr, sign, tol_pct=0.003, min_gap=10, peak_k=1.5, order=3):
    """शेवटचे दोन confirmed swing lows (bottom) / highs (top): 0.3% आत, ≥ min_gap bars अंतर, मधला peak ≥ peak_k × rr; दुसऱ्या swing नंतर
    neckline पलीकडे close झालेला नाही (pattern अजून उघडा) आणि level तुटलेला नाही. नसेल तर None."""
    if rr is None or not np.isfinite(rr) or rr <= 0:
        return None
    n = len(df)
    hi, lo, cl = df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float)
    sh, sl = find_swings(df, order=order)
    idx = [i for i in (sl if sign > 0 else sh) if i <= n - 1 - order]
    if len(idx) < 2:
        return None
    y = lo if sign > 0 else hi
    s2 = idx[-1]
    for s1 in reversed(idx[:-1]):
        if s2 - s1 < min_gap:
            continue
        if abs(y[s1] - y[s2]) > tol_pct * max(abs(y[s1]), 1e-9):
            continue
        level = min(y[s1], y[s2]) if sign > 0 else max(y[s1], y[s2])
        neck = float(hi[s1:s2 + 1].max()) if sign > 0 else float(lo[s1:s2 + 1].min())
        if abs(neck - level) < peak_k * rr:
            continue
        after_c = cl[s2 + 1:]
        if len(after_c) and ((after_c > neck).any() if sign > 0 else (after_c < neck).any()):
            return None                                          # neckline आधीच तुटली (जुनी गोष्ट)
        between = y[s1 + 1:s2]
        if len(between) and ((between < level).any() if sign > 0 else (between > level).any()):
            continue
        after = (lo[s2 + 1:] < level).any() if sign > 0 else (hi[s2 + 1:] > level).any()
        if after:
            return None
        return Double(sign=sign, first=int(s1), second=int(s2), level=float(level), neckline=neck)
    return None
