"""
price_action/legs.py
--------------------
🎓 T2.1–T2.3 — Leg classifier (indicator-मुक्त; फक्त OHLC). बाजार "legs" मध्ये चालतो: एका confirmed swing पासून पुढच्या confirmed swing पर्यंतची हालचाल.
प्रत्येक leg चे गुण (features) मोजून त्याला लेबल: STRONG_IMPULSE / WEAK_IMPULSE / HEALTHY_PULLBACK / DANGEROUS_PULLBACK / MIXED_PULLBACK / REVERSAL / RANGE.

मोजपट्टी: median_range(N) = शेवटच्या N पूर्ण candles च्या (H−L) चा median (ATR नाही). सर्व आकार "× median_range" मध्ये ⇒ instrument/TF बदलला तरी तेच नियम.

Swings (दोन प्रकार, दोन्हींना pivot_bar आणि confirm_bar):
  • fractal(R): high[j] हा डावीकडच्या R आणि उजवीकडच्या R bars पेक्षा मोठा ⇒ pivot; confirm_bar = j + R (त्याआधी माहीत नसतो).
  • ZigZag (range-normalised): extreme पासून उलट हालचाल ≥ k × median_range ⇒ तो extreme pivot; confirm_bar = ज्या bar ने ही उलट हालचाल पूर्ण केली.
    दोन scales: internal (लहान k) आणि swing (मोठा k). Legs = swing-scale pivots मधल्या हालचाली; internal pivots CHoCH साठी.
No-lookahead: leg (pivot a → pivot b) फक्त b च्या confirm_bar नंतरच "माहीत" — `known_at`. चालू leg (`current_leg`) दर bar ला फक्त मागच्या डेटावरून.

लेबल नियम (T2.3; थ्रेशोल्ड `LegConfig` मध्ये, IS वर calibrate):
  impulse/pullback भूमिका: leg ची लांबी ÷ मागच्या leg ची = depth. depth ≤ 1 ⇒ PULLBACK. depth > 1 आणि मागचा leg pullback ⇒ IMPULSE (trend चालू).
  depth > 1 आणि मागचा leg impulse ⇒ REVERSAL (impulse चा 100%+ retrace = leg च्या सुरुवातीपलीकडे) — पुढे तोच नवा impulse मानला जातो.
  STRONG_IMPULSE: efficiency ≥ e_hi, overlap ≤ o_lo, ≥ 1 displacement किंवा FVG. नाहीतर WEAK_IMPULSE.
  DANGEROUS_PULLBACK: depth > r_warn, किंवा pullback दिशेचा displacement/FVG, किंवा speed ≥ impulse speed, किंवा CHoCH + displacement.
  HEALTHY_PULLBACK: depth ≤ r_ok, speed < impulse speed × s_ratio, spread < 1 (pullback candles impulse पेक्षा अरुंद: avg range ÷ impulse avg range),
                    displacement नाही, रंग मिश्र, protected swing शाबूत.
  MIXED_PULLBACK (माझा निर्णय, WORK_LOG): ना healthy ना dangerous — मधला (उदा. depth r_ok–r_warn, बाकी शांत).
  RANGE: efficiency ≤ e_range, overlap ≥ o_range, रंग आलटून-पालटून (alternation ≥ alt_range) — इतर लेबलवर मात.
Fibonacci गेट नाही — retracement depth फक्त सलग (continuous) feature. EW: फक्त Tier-A नियम-तपासणी (feature, गेट नाही).
"""
import copy
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

STRONG_IMPULSE, WEAK_IMPULSE = "STRONG_IMPULSE", "WEAK_IMPULSE"
HEALTHY_PULLBACK, DANGEROUS_PULLBACK, MIXED_PULLBACK = "HEALTHY_PULLBACK", "DANGEROUS_PULLBACK", "MIXED_PULLBACK"
REVERSAL, RANGE = "REVERSAL", "RANGE"
LABELS = (STRONG_IMPULSE, WEAK_IMPULSE, HEALTHY_PULLBACK, DANGEROUS_PULLBACK, MIXED_PULLBACK, REVERSAL, RANGE)
ROLE_IMPULSE, ROLE_PULLBACK = "IMPULSE", "PULLBACK"

LABEL_TEXT = {
    STRONG_IMPULSE: "जोरदार impulse — कार्यक्षम, कमी overlap, displacement/FVG",
    WEAK_IMPULSE: "कमकुवत impulse — दिशा आहे पण overlap/शेपट्या जास्त, FVG नाही",
    HEALTHY_PULLBACK: "निरोगी pullback — उथळ, हळू, अरुंद candles, रंग मिश्र, protected swing शाबूत",
    DANGEROUS_PULLBACK: "धोकादायक pullback — खोल/जलद/उलट displacement किंवा CHoCH",
    MIXED_PULLBACK: "मधला pullback — ना निरोगी ना धोकादायक",
    REVERSAL: "उलटफेर — मागच्या impulse चा 100%+ retrace",
    RANGE: "range — कार्यक्षमता ≈ 0, overlap जास्त, रंग आलटून-पालटून",
}


@dataclass
class LegConfig:
    n_median: int = 20                 # median_range खिडकी (पूर्ण candles)
    fractal_r: int = 2
    k_internal: float = 1.5            # ZigZag internal scale (× median_range)
    k_swing: float = 3.0               # ZigZag swing scale
    e_hi: float = 0.45                 # STRONG: efficiency (net ÷ Σ range) किमान
    o_lo: float = 0.35                 # STRONG: overlap कमाल
    d_k: float = 1.5                   # displacement: body ≥ d_k × median_range
    d_body: float = 0.6                # displacement: body% ≥ d_body
    fvg_min: float = 0.1               # FVG/imbalance मोजण्यासाठी किमान आकार (× median_range) — सूक्ष्म gaps गोंगाट
    r_ok: float = 0.5                  # HEALTHY: depth कमाल
    r_warn: float = 0.75               # DANGEROUS: depth > r_warn
    s_ratio: float = 0.8               # HEALTHY: speed < impulse speed × s_ratio
    healthy_max_dir: float = 0.8       # HEALTHY: "रंग मिश्र" ⇒ leg-दिशेचे candles ≤ 80%
    e_range: float = 0.15              # RANGE
    o_range: float = 0.55
    alt_range: float = 0.5


# ---------------------------------------------------------------------------------------------------------------------
# मोजपट्टी आणि swings
# ---------------------------------------------------------------------------------------------------------------------
def _arr(df):
    return (df["open"].to_numpy(float), df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float))


def median_range(df, n=20):
    """bar i वर: bars [i−n+1 … i] (सर्व पूर्ण) च्या (H−L) चा median. सुरुवातीला किमान n//2 bars; त्याआधी NaN."""
    rng = (df["high"].astype(float) - df["low"].astype(float))
    return rng.rolling(n, min_periods=max(n // 2, 1)).median().to_numpy(float)


@dataclass
class Pivot:
    kind: str            # "H" / "L"
    pivot_bar: int
    confirm_bar: int
    price: float
    scale: str = "swing"


def fractal_pivots(df, r=2):
    """Fractal swings: pivot j ला confirm_bar = j + r. सलग समान प्रकार असू शकतात (ZigZag सारखे alternating नाहीत)."""
    _, h, l, _ = _arr(df)
    n, out = len(h), []
    for j in range(r, n - r):
        if h[j] > h[j - r:j].max() and h[j] >= h[j + 1:j + r + 1].max():
            out.append(Pivot("H", j, j + r, float(h[j]), "fractal"))
        if l[j] < l[j - r:j].min() and l[j] <= l[j + 1:j + r + 1].min():
            out.append(Pivot("L", j, j + r, float(l[j]), "fractal"))
    return sorted(out, key=lambda p: (p.confirm_bar, p.pivot_bar))


def zigzag_pivots(df, k=3.0, n_median=20, scale="swing", mr=None):
    """Range-normalised ZigZag. उलट हालचाल (extreme पासून) ≥ k × median_range(त्या bar वर) ⇒ extreme confirmed. Pivots H/L आलटून-पालटून.
    threshold bar i वरचा median_range (फक्त i पर्यंतचे bars) — भविष्यातला डेटा नाही."""
    _, h, l, _ = _arr(df)
    mr = median_range(df, n_median) if mr is None else mr
    n = len(h)
    out: List[Pivot] = []
    if n < 2:
        return out
    trend = 0
    hi_i, lo_i = 0, 0
    for i in range(1, n):
        thr = k * mr[i] if np.isfinite(mr[i]) else np.inf
        if trend >= 0 and h[i] >= h[hi_i]:
            hi_i = i
        if trend <= 0 and l[i] <= l[lo_i]:
            lo_i = i
        if trend >= 0 and hi_i < i and h[hi_i] - l[i] >= thr:
            out.append(Pivot("H", hi_i, i, float(h[hi_i]), scale))
            lo_i = hi_i + 1 + int(np.argmin(l[hi_i + 1:i + 1]))             # pivot नंतरचा सर्वात खालचा bar (i पर्यंतच)
            trend = -1
            continue
        if trend <= 0 and lo_i < i and h[i] - l[lo_i] >= thr:
            out.append(Pivot("L", lo_i, i, float(l[lo_i]), scale))
            hi_i = lo_i + 1 + int(np.argmax(h[lo_i + 1:i + 1]))
            trend = 1
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Leg features (T2.2)
# ---------------------------------------------------------------------------------------------------------------------
@dataclass
class Leg:
    start_bar: int
    end_bar: int
    known_at: int                 # end pivot चा confirm_bar (current leg साठी = आत्ताचा bar)
    direction: int                # +1 वर, −1 खाली
    start_price: float
    end_price: float
    features: dict = field(default_factory=dict)
    role: str = ""
    label: str = ""
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    provisional: bool = False
    disp_mask: Optional[np.ndarray] = field(default=None, repr=False)     # leg-दिशेचे displacement bars (CHoCH साठी)

    def as_dict(self):
        d = asdict(self)
        d.pop("disp_mask", None)
        d.update(d.pop("features"))
        d["reasons"] = " · ".join(self.reasons)
        return d


def _max_run(mask):
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


def leg_features(df, a, b, direction, start_price, end_price, mr_ref, cfg=None):
    """bars a..b (समाविष्ट) वरचे features. `mr_ref` = median_range (leg च्या शेवटी माहीत असलेला). सर्व आकार ÷ mr_ref."""
    cfg = cfg or LegConfig()
    o, h, l, c = (x[a:b + 1] for x in _arr(df))
    s = direction
    m = max(int(b - a + 1), 1)
    mr_ref = float(mr_ref) if mr_ref and np.isfinite(mr_ref) and mr_ref > 0 else float(np.nanmedian(h - l) or 1.0)
    net = abs(end_price - start_price)
    rng = np.maximum(h - l, 1e-12)
    pc = np.concatenate([[c[0]], c[:-1]])                       # leg मधला मागचा close (पहिल्या bar ला स्वतःचा)
    tr = np.maximum(h, pc) - np.minimum(l, pc)                  # overnight gap सह range — efficiency ≤ 1 राहावी (gap ला denominator मध्ये जागा)
    body = np.abs(c - o)
    sum_dc = float(np.abs(np.diff(c)).sum()) if m > 1 else 0.0
    colour = np.sign(c - o)
    with_dir = colour == s
    against = colour == -s
    alt = float((colour[1:] * colour[:-1] < 0).mean()) if m > 1 else 0.0
    ov = []
    for i in range(1, m):
        inter = min(h[i], h[i - 1]) - max(l[i], l[i - 1])
        ov.append(max(inter, 0.0) / rng[i])
    clv = (((c - l) - (h - c)) / rng) * s
    # FVG (3-candle) आणि body gaps — leg दिशेने आणि उलट दिशेने
    fvg_n = fvg_sz = fvg_opp = 0
    for i in range(2, m):
        gap_up, gap_dn = l[i] - h[i - 2], l[i - 2] - h[i]
        g, go = (gap_up, gap_dn) if s > 0 else (gap_dn, gap_up)
        if g >= cfg.fvg_min * mr_ref:
            fvg_n += 1
            fvg_sz += g
        if go >= cfg.fvg_min * mr_ref:
            fvg_opp += 1
    bgap = 0
    for i in range(1, m):
        lo_i, hi_i = min(o[i], c[i]), max(o[i], c[i])
        lo_p, hi_p = min(o[i - 1], c[i - 1]), max(o[i - 1], c[i - 1])
        if (s > 0 and lo_i > hi_p) or (s < 0 and hi_i < lo_p):
            bgap += 1
    disp = (body >= cfg.d_k * mr_ref) & (body / rng >= cfg.d_body)
    disp_with = int((disp & with_dir).sum())
    disp_against = int((disp & against).sum())
    return {
        "bars": m,
        "net_mr": round(net / mr_ref, 3),
        "eff_close": round(abs(c[-1] - c[0]) / sum_dc, 3) if sum_dc > 0 else 0.0,
        "eff_range": round(min(net / float(tr.sum()), 1.0), 3),
        "dir_pct": round(float(with_dir.mean()), 3),
        "max_consec": int(_max_run(with_dir)),
        "alternation": round(alt, 3),
        "body_pct": round(float((body / rng).mean()), 3),
        "clv": round(float(clv.mean()), 3),
        "overlap": round(float(np.mean(ov)), 3) if ov else 0.0,
        "fvg_n": fvg_n, "fvg_mr": round(fvg_sz / mr_ref, 3), "fvg_against": fvg_opp,
        "body_gaps": bgap,
        "disp_n": disp_with, "disp_against": disp_against,
        "speed": round(net / mr_ref / m, 3),
        "spread": round(float(rng.mean()) / mr_ref, 3),
        "mr": round(mr_ref, 4),
    }


# ---------------------------------------------------------------------------------------------------------------------
# Legs + लेबल (T2.3)
# ---------------------------------------------------------------------------------------------------------------------
def _is_range(f, cfg):
    return f["eff_range"] <= cfg.e_range and f["overlap"] >= cfg.o_range and f["alternation"] >= cfg.alt_range


def _impulse_score(f, cfg):
    return round(30 * min(f["eff_range"] / max(cfg.e_hi, 1e-9), 1.0) + 25 * max(0.0, 1 - f["overlap"]) + 25 * min(f["disp_n"] + f["fvg_n"], 2) / 2
                 + 10 * f["body_pct"] + 10 * f["dir_pct"], 1)


def _choch(df, leg, internal, impulse):
    """Pullback leg मध्ये: impulse मधला शेवटचा internal pivot (pullback च्या विरुद्ध बाजूचा protected internal swing) close ने तोडला का, आणि ती
    तोडणारी candle displacement का. फक्त त्या bar पूर्वी confirm झालेले internal pivots."""
    if impulse is None or not internal:
        return False, False
    _, _, _, c = _arr(df)
    s = leg.direction                                   # pullback दिशा (impulse च्या उलट)
    want = "L" if s < 0 else "H"                        # वर-impulse नंतर खाली pullback ⇒ impulse मधला शेवटचा internal LOW
    pool = [p for p in internal if p.kind == want and impulse.start_bar <= p.pivot_bar <= impulse.end_bar and p.confirm_bar <= leg.end_bar]
    broke = disp = False
    if not pool:
        return False, False
    for i in range(leg.start_bar + 1, leg.end_bar + 1):
        cands = [p for p in pool if p.confirm_bar <= i]
        if not cands:
            continue
        lvl = cands[-1].price
        if (c[i] < lvl) if s < 0 else (c[i] > lvl):
            broke = True
            disp = bool(leg.disp_mask is not None and leg.disp_mask[i - leg.start_bar])
            break
    return broke, disp


def classify(legs, df=None, internal=None, cfg=None):
    """legs (काळानुसार) ला role/label/score/reasons लावतो (in-place) आणि परत देतो. प्रत्येक leg साठी फक्त त्याआधीचे legs वापरले जातात."""
    cfg = cfg or LegConfig()
    prev_role, impulse = None, None
    prev = None
    for lg in legs:
        f = lg.features
        depth = (f["net_mr"] / prev.features["net_mr"]) if prev is not None and prev.features.get("net_mr") else None
        f["depth"] = None if depth is None else round(depth, 3)
        if depth is None or (depth > 1.0 and prev_role == ROLE_PULLBACK):
            role = ROLE_IMPULSE
            reversal = False
        elif depth > 1.0:
            role, reversal = ROLE_IMPULSE, True
        else:
            role, reversal = ROLE_PULLBACK, False
        lg.role = role
        reasons = []
        if role == ROLE_IMPULSE:
            lg.score = _impulse_score(f, cfg)
            strong = f["eff_range"] >= cfg.e_hi and f["overlap"] <= cfg.o_lo and (f["disp_n"] + f["fvg_n"]) >= 1
            if reversal:
                lg.label = REVERSAL
                reasons.append(f"मागच्या impulse चा {depth * 100:.0f}% retrace (> 100%)")
            else:
                lg.label = STRONG_IMPULSE if strong else WEAK_IMPULSE
            reasons.append(f"efficiency {f['eff_range']:.2f}, overlap {f['overlap']:.2f}, displacement {f['disp_n']}, FVG {f['fvg_n']}")
            impulse = lg
        else:
            imp_speed = impulse.features["speed"] if impulse is not None else None
            f["speed_ratio"] = round(f["speed"] / imp_speed, 3) if imp_speed else None
            broke, ch_disp = _choch(df, lg, internal, impulse) if df is not None else (False, False)
            f["choch"], f["choch_disp"] = bool(broke), bool(ch_disp)
            danger = []
            if depth > cfg.r_warn:
                danger.append(f"खोल ({depth * 100:.0f}% > {cfg.r_warn * 100:.0f}%)")
            if f["disp_n"] > 0 or f["fvg_n"] > 0:
                danger.append(f"pullback दिशेने displacement {f['disp_n']} / FVG {f['fvg_n']}")
            if imp_speed and f["speed"] >= imp_speed:
                danger.append("impulse पेक्षा जलद")
            if broke and ch_disp:
                danger.append("CHoCH + displacement")
            f["spread_ratio"] = round(f["spread"] / impulse.features["spread"], 3) if impulse is not None and impulse.features.get("spread") else None
            healthy = (depth <= cfg.r_ok and (not imp_speed or f["speed"] < imp_speed * cfg.s_ratio) and (f["spread_ratio"] or 0.0) < 1.0 and f["disp_n"] == 0
                       and f["dir_pct"] <= cfg.healthy_max_dir and depth < 1.0)
            lg.score = round(100 * max(0.0, 1 - depth) * (0.5 + 0.5 * max(0.0, 1 - (f.get("speed_ratio") or 0))), 1)
            if danger:
                lg.label = DANGEROUS_PULLBACK
                reasons += danger
            elif healthy:
                lg.label = HEALTHY_PULLBACK
                reasons.append(f"depth {depth * 100:.0f}%, speed ratio {f.get('speed_ratio')}, spread ratio {f.get('spread_ratio')}")
            else:
                lg.label = MIXED_PULLBACK
                reasons.append(f"depth {depth * 100:.0f}% (r_ok {cfg.r_ok:.2f}–r_warn {cfg.r_warn:.2f}) / इतर अटी अपूर्ण")
        if _is_range(f, cfg) and lg.label != REVERSAL:
            lg.label = RANGE
            reasons = [f"efficiency {f['eff_range']:.2f} ≤ {cfg.e_range}, overlap {f['overlap']:.2f}, alternation {f['alternation']:.2f}"]
        lg.reasons = reasons
        prev_role = role
        prev = lg
    return legs


def _disp_mask(df, a, b, direction, mr_ref, cfg):
    o, h, l, c = (x[a:b + 1] for x in _arr(df))
    rng = np.maximum(h - l, 1e-12)
    body = np.abs(c - o)
    return (body >= cfg.d_k * mr_ref) & (body / rng >= cfg.d_body) & (np.sign(c - o) == direction)


def pivots_for(df, cfg=None):
    """(median_range, swing pivots, internal pivots) — calibration मध्ये एकदाच मोजून पुन्हा वापरायला (हे LegConfig च्या लेबल-थ्रेशोल्डवर अवलंबून नाहीत)."""
    cfg = cfg or LegConfig()
    mr = median_range(df, cfg.n_median)
    return mr, zigzag_pivots(df, cfg.k_swing, cfg.n_median, "swing", mr), zigzag_pivots(df, cfg.k_internal, cfg.n_median, "internal", mr)


def build_legs(df, cfg=None, upto=None, pivots=None):
    """df (पूर्ण candles, जुनं → नवं) -> (legs, swing pivots, internal pivots). `upto` = bar index: फक्त confirm_bar ≤ upto असलेले pivots
    (म्हणजे त्या क्षणी माहीत असलेले legs). leg features फक्त pivot_bar पर्यंतचे bars वापरतात."""
    cfg = cfg or LegConfig()
    df = df.reset_index(drop=True)
    if upto is not None:
        df = df.iloc[:upto + 1]
    mr, swing, internal = pivots if (pivots is not None and upto is None) else pivots_for(df, cfg)
    legs = []
    for p0, p1 in zip(swing, swing[1:]):
        d = 1 if p1.kind == "H" else -1
        ref = mr[p1.pivot_bar]
        f = leg_features(df, p0.pivot_bar, p1.pivot_bar, d, p0.price, p1.price, ref, cfg)
        legs.append(Leg(p0.pivot_bar, p1.pivot_bar, p1.confirm_bar, d, p0.price, p1.price, f, disp_mask=_disp_mask(df, p0.pivot_bar, p1.pivot_bar, d, ref, cfg)))
    classify(legs, df, internal, cfg)
    return legs, swing, internal


def current_leg(df, cfg=None, legs=None, swing=None, internal=None):
    """शेवटच्या confirmed swing pivot पासून शेवटच्या पूर्ण bar पर्यंतचा चालू (provisional) leg — फक्त मागच्या डेटावरून. नसेल तर None."""
    cfg = cfg or LegConfig()
    df = df.reset_index(drop=True)
    if legs is None:
        legs, swing, internal = build_legs(df, cfg)
    if not swing:
        return None
    last = swing[-1]
    t = len(df) - 1
    if t <= last.pivot_bar:
        return None
    d = -1 if last.kind == "H" else 1
    _, h, l, c = _arr(df)
    end = float(c[t])
    mr = median_range(df, cfg.n_median)
    f = leg_features(df, last.pivot_bar, t, d, last.price, end, mr[t], cfg)
    lg = Leg(last.pivot_bar, t, t, d, last.price, end, f, provisional=True, disp_mask=_disp_mask(df, last.pivot_bar, t, d, mr[t], cfg))
    classify(copy.deepcopy(list(legs)) + [lg], df, internal, cfg)   # copy ⇒ caller चे legs बदलत नाहीत; मागचा संदर्भ तोच
    return lg


def legs_frame(df, legs):
    """legs -> DataFrame (वेळा सह) — अहवाल/चार्टसाठी."""
    if not legs:
        return pd.DataFrame()
    ts = pd.to_datetime(df.reset_index(drop=True)["timestamp"]) if "timestamp" in df.columns else None
    rows = []
    for lg in legs:
        r = lg.as_dict()
        if ts is not None:
            r["start_time"], r["end_time"], r["known_time"] = ts.iloc[lg.start_bar], ts.iloc[lg.end_bar], ts.iloc[min(lg.known_at, len(ts) - 1)]
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------------------
# EW Tier-A (फक्त नियम-तपासणी, feature)
# ---------------------------------------------------------------------------------------------------------------------
def ew_tier_a(legs):
    """शेवटचे 5 legs (1-2-3-4-5) Elliott Tier-A नियम पाळतात का: (i) wave 2 wave 1 च्या सुरुवातीपलीकडे जात नाही, (ii) wave 3 सर्वात लहान impulse नाही,
    (iii) wave 4 wave 1 च्या प्रदेशात (overlap) शिरत नाही. 5 legs नसतील किंवा दिशा आलटून-पालटून नसेल ⇒ None. फक्त feature — गेट नाही."""
    if len(legs) < 5:
        return None
    w = legs[-5:]
    d = w[0].direction
    if any(x.direction != (d if i % 2 == 0 else -d) for i, x in enumerate(w)):
        return None
    w1, w2, w3, w4, w5 = (abs(x.end_price - x.start_price) for x in w)
    r1 = (w[1].end_price - w[0].start_price) * d > 0
    r2 = not (w3 < w1 and w3 < w5)
    r3 = (w[3].end_price - w[0].end_price) * d > 0
    return bool(r1 and r2 and r3)


# ---------------------------------------------------------------------------------------------------------------------
# चार्ट (Dashboard): impulse गडद, pullback फिकट, range राखाडी; hover वर features + मराठी कारण
# ---------------------------------------------------------------------------------------------------------------------
_COL = {
    (STRONG_IMPULSE, 1): ("#00695c", 4), (STRONG_IMPULSE, -1): ("#b71c1c", 4),
    (WEAK_IMPULSE, 1): ("#26a69a", 3), (WEAK_IMPULSE, -1): ("#ef5350", 3),
    (REVERSAL, 1): ("#7e57c2", 3), (REVERSAL, -1): ("#7e57c2", 3),
}
_PULL = {HEALTHY_PULLBACK: "rgba(102,187,106,0.55)", MIXED_PULLBACK: "rgba(255,213,79,0.55)", DANGEROUS_PULLBACK: "rgba(255,152,0,0.85)"}
LABEL_MR = {STRONG_IMPULSE: "जोरदार impulse", WEAK_IMPULSE: "कमकुवत impulse", HEALTHY_PULLBACK: "निरोगी pullback", DANGEROUS_PULLBACK: "धोकादायक pullback",
            MIXED_PULLBACK: "मधला pullback", REVERSAL: "उलटफेर", RANGE: "range"}


def leg_info(lg):
    f = lg.features
    arrow = "↑" if lg.direction > 0 else "↓"
    depth = "" if f.get("depth") is None else f" · depth {f['depth'] * 100:.0f}%"
    return (f"{LABEL_MR.get(lg.label, lg.label)} {arrow} ({lg.label}, score {lg.score:.0f}{', चालू' if lg.provisional else ''}) · {f['bars']} bars · "
            f"{f['net_mr']:.1f}×range · eff {f['eff_range']:.2f} · overlap {f['overlap']:.2f} · disp {f['disp_n']} · FVG {f['fvg_n']} · speed {f['speed']:.2f}"
            f"{depth} — {'; '.join(lg.reasons)}")


def chart_legs(df, legs, current=None, max_legs=60):
    """legs -> tradingview_chart `legs` पर्याय: [{start, start_price, end, end_price, color, width, dashed, label, info}] (शेवटचे `max_legs`)."""
    if df is None or not len(df):
        return []
    ts = pd.to_datetime(df.reset_index(drop=True)["timestamp"])
    out = []
    for lg in list(legs)[-max_legs:] + ([current] if current is not None else []):
        if lg.end_bar <= lg.start_bar or lg.end_bar >= len(ts):
            continue
        if lg.label == RANGE:
            color, width = "#9e9e9e", 2
        elif lg.label in _PULL:
            color, width = _PULL[lg.label], 2
        else:
            color, width = _COL.get((lg.label, lg.direction), ("#90a4ae", 2))
        out.append({"start": ts.iloc[lg.start_bar], "start_price": float(lg.start_price), "end": ts.iloc[lg.end_bar], "end_price": float(lg.end_price),
                    "color": color, "width": width, "dashed": bool(lg.provisional), "label": lg.label, "info": leg_info(lg)})
    return out
