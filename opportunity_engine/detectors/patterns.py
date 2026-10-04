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
