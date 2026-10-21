"""decision3/daily.py — ① Daily trend (Dow), थर v2.2.

Input: Daily candles (timestamp = session तारीख, `bar_end` = त्या दिवसाचा close वेळ = known_at). NIFTY: 1m ⇒ 15M ⇒ Daily (फक्त पूर्ण
sessions, `pivots.charts.daily_from_15m`); BANKNIFTY: fetched D (bar_end = तारीख + session close).

Daily swings — `daily_swing_method`:
  • pivot (default): high[i] > डावीकडचे N highs आणि ≥ उजवीकडचे N highs (low आरसा). Confirm = i+N दिवसाचा close (known_at).
  • dc: directional change, θ_D = k_D × σ_D (σ_D = शेवटच्या `daily_sigma_sessions` Daily ranges चा median; warm-up फक्त σ साठी).
  Confirm-क्रमाने H / L आलटून पालटून; सलग तोच प्रकार ⇒ जास्त टोकाचा ठेवा (replace, त्याच confirm वेळी).

Dow (प्रत्येक बंद Daily candle नंतर; आधी त्या दिवशी confirm झालेले pivots, मग close तपासणी):
  • UP = नवा HL + HH (शेवटच्या दोन L मध्ये L2 > L1 + tol, शेवटच्या दोन H मध्ये H2 > H1 + tol; L2 आणि H2 दोन्ही शेवटच्या break नंतरचे).
    DOWN आरसा. protected = तो HL (UP) / LH (DOWN); trend मध्ये नवा HL (L > मागचा L) ⇒ protected पुढे.
  • Trend संपतो (NEUTRAL) जेव्हा protected Daily close ने तुटतो (wick नाही).
  • RANGE = NEUTRAL + दोन H जवळपास समान (|H2 − H1| ≤ tol) आणि दोन L जवळपास समान; पट्टा [min L, max H]; close पट्ट्याबाहेर ⇒ NEUTRAL.
  • tol = range_eq_sigma_d × σ_D. UNKNOWN फक्त data अपुरा (≤ daily_min_sessions Daily candles).
Pullback मध्ये trend बदलत नाही: trend फक्त protected च्या close-break ने संपतो (v2.1 चं net/H regime नाही).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import daily_legs as DL
from . import settings as S3


@dataclass(frozen=True)
class DPivot:
    kind: str           # "H" / "L"
    price: float
    bar: int            # Daily candle index
    day: pd.Timestamp
    confirm_bar: int
    known_at: pd.Timestamp


@dataclass
class DState:
    bar: int
    day: pd.Timestamp
    known_at: pd.Timestamp
    trend: str
    protected: DPivot = None
    band: tuple = None
    why: str = ""
    pivots: list = field(default_factory=list)
    # Q15 degree-aware (impulse mode): टप्पा / wave / impulse टोक / maturity
    phase: str = None          # "impulse" / "correction" / "origin_broken" (protected close ने तुटला, उलट impulse ची वाट)
    wave: str = None           # "(1)", "(2)", "(3)", ... — दिसणाऱ्या data मधली impulse-leg मोजणी
    corr_label: str = None     # correction चा चालू पाय "a" / "b" / "c" / "d" / "e"
    imp_end: DPivot = None     # शेवटच्या impulse चं टोक (DOWN ⇒ low)
    mature: bool = False       # पाचवी wave target जवळ (पुरावा, gate नाही)
    targets: tuple = ()        # Q44 structural target: parent origin नंतरच्या पहिल्या impulse leg चं टोक (फक्त A1 correction नंतर)
    # Abhi daily review A1–A3: मोठ्या degree चा origin (trend ज्या origin पासून सुरू झाला), चालू counter-move ची degree, origin धोक्यात
    parent: DPivot = None      # A1: मोठ्या degree चा origin — correction (counter="correction") मध्ये तो टिकलेला parent, नाहीतर trend
                               # ज्या origin पासून सुरू झाला तो (counter-move ने trend उलटायला याच्या पलीकडे Daily close लागतो)
    counter: str = None        # "pullback" (lower degree) / "candidate" (same-degree correction, अजून पूर्ण नाही) / "correction"
                               # (impulse origin तुटला, parent टिकला ⇒ same-degree correction नक्की) / None
    leg_start: int = None      # चालू impulse leg चा origin bar (chart: legs / corrections objects)
    corr_bars: tuple = ()      # चालू leg मधले same-degree correction swings (bars, confirmed)
    origin_risk: bool = False  # B1: correction किंमत protected origin च्या area पर्यंत पोहोचली (C-13; पुरावा, gate नाही)
    sharp: tuple = None        # ABC_FIX rule 2: (lo, hi, bar) sharp-fall (DOWN) / sharp-rise (UP) zone
    evidence: tuple = ()       # ABC_FIX rule 3: continuation पुरावा (उदा. correction sharp zone मध्ये संपली)
    corr_zone: tuple = None    # ABC_FIX rule 2 / 5: चालू leg ज्या correction नंतर सुरू झाला ती sharp zone मध्ये संपली ⇒ (lo, hi, bar)
    leg_from: int = None       # चालू impulse leg ज्या correction नंतर सुरू झाला त्या counter-move ची सुरुवात (bar) — box / family साठी
    target_passed: bool = False  # Q44: रचनेतला target होता पण protected आधीच त्याच्या पलीकडे ⇒ दाखवत नाही ("target passed", "none" नाही)
    wave_a: DPivot = None      # Q49: A1 correction चा 5-wave पहिला पाय — default wave A (chart label "A"); त्याचं टोक
    alt: str = None            # Q49: wave_a चा पर्यायी count ("1") — फक्त debug (Telegram वर wave क्रमांक नाही, Q46)
    rev: tuple = None          # trend first (setups audit): (HL, मधला H) DOWN trend मध्ये (UP ⇒ (LH, मधला L)) — impulse टोकानंतर उलट
                               # रचना + impulse-स्वभावाचा पाय (flip चा (अ) नियम, Q29 / Q36) पूर्ण, फक्त origin पलीकडचा close बाकी ⇒ Daily
                               # रचना trend विरुद्ध; trend-बाजूचे नवे entries नाहीत (trend / protected तसेच — Q15)


def _arr(d):
    return {k: d[k].to_numpy(float) for k in ("open", "high", "low", "close")}


def known_at_of(d):
    if "bar_end" in d.columns:
        return [pd.Timestamp(x) for x in d["bar_end"]]
    return [pd.Timestamp(x).normalize() + pd.Timedelta(hours=15, minutes=30) for x in d["timestamp"]]


def sigma_d(d, n):
    """σ_D[i] = Daily range चा median, शेवटच्या n candles (i सकट) — कमी असतील तर NaN (warm-up)."""
    rng = (d["high"] - d["low"]).to_numpy(float)
    out = np.full(len(d), np.nan)
    for i in range(len(d)):
        if i + 1 >= n:
            out[i] = float(np.median(rng[i + 1 - n:i + 1]))
    return out


def pivots_pivot(d, n, kat):
    """(confirm_bar क्रमाने) raw pivots — tie: डावीकडे strict, उजवीकडे ≥ (नंतरचं बरोबरीचं टोक pivot मारत नाही)."""
    A = _arr(d)
    H, L = A["high"], A["low"]
    out = []
    for i in range(n, len(d) - n):
        if H[i] > H[i - n:i].max() and H[i] >= H[i + 1:i + n + 1].max():
            out.append(DPivot("H", float(H[i]), i, pd.Timestamp(d["timestamp"].iloc[i]), i + n, kat[i + n]))
        if L[i] < L[i - n:i].min() and L[i] <= L[i + 1:i + n + 1].min():
            out.append(DPivot("L", float(L[i]), i, pd.Timestamp(d["timestamp"].iloc[i]), i + n, kat[i + n]))
    return sorted(out, key=lambda p: (p.confirm_bar, p.bar))


def pivots_dc(d, k, sig, kat):
    """Directional change: टोकापासून θ_D = k × σ_D उलट चाल (raw high / low) ⇒ टोक confirm (त्या दिवसाच्या close ला)."""
    A = _arr(d)
    H, L = A["high"], A["low"]
    out, mode = [], 0
    hi_i = lo_i = None
    for i in range(len(d)):
        if not np.isfinite(sig[i]):
            continue
        th = k * sig[i]
        if hi_i is None:
            hi_i = lo_i = i
            continue
        if mode >= 0 and H[i] > H[hi_i]:
            hi_i = i
        if mode <= 0 and L[i] < L[lo_i]:
            lo_i = i
        if mode >= 0 and hi_i < i and H[hi_i] - L[i] >= th:
            out.append(DPivot("H", float(H[hi_i]), hi_i, pd.Timestamp(d["timestamp"].iloc[hi_i]), i, kat[i]))
            mode, lo_i = -1, i
        elif mode <= 0 and lo_i < i and H[i] - L[lo_i] >= th:
            out.append(DPivot("L", float(L[lo_i]), lo_i, pd.Timestamp(d["timestamp"].iloc[lo_i]), i, kat[i]))
            mode, hi_i = 1, i
    return out


def _add(seq, p):
    """आलटून पालटून: सलग तोच प्रकार ⇒ जास्त टोकाचा ठेवा."""
    if seq and seq[-1].kind == p.kind:
        better = p.price > seq[-1].price if p.kind == "H" else p.price < seq[-1].price
        if better:
            seq[-1] = p
        return
    seq.append(p)


def _last2(seq, kind):
    xs = [p for p in seq if p.kind == kind]
    return (xs[-2], xs[-1]) if len(xs) >= 2 else (None, xs[-1] if xs else None)


def fold(d, s=None):
    """प्रत्येक Daily candle नंतरची DState यादी (index = Daily candle). `daily_trend_mode`: impulse (Q15, default) / minor (जुना —
    फक्त what-if)."""
    s = S3.load(s)
    if s["daily_trend_mode"] == "impulse":
        return fold_impulse(d, s)
    if s["daily_trend_mode"] != "minor":
        raise ValueError(f"daily_trend_mode {s['daily_trend_mode']!r} — impulse / minor पैकी")
    return fold_minor(d, s)


def _raw_pivots(d, s, kat, sig):
    if s["daily_swing_method"] == "dc":
        return pivots_dc(d, float(s["daily_dc_k"]), sig, kat)
    if s["daily_swing_method"] != "pivot":
        raise ValueError(f"daily_swing_method {s['daily_swing_method']!r} — pivot / dc पैकी")
    return pivots_pivot(d, int(s["daily_pivot_n"]), kat)


def complete_impulse_start(cands, seq, low, end, w_lo, w_hi, upto):
    """Q49 (a) विस्तार: cands (क्रमाने) मधला पहिला P ज्यापासून end पर्यंतची चाल पूर्ण 5-wave impulse वाचते (read_counter; आधी
    trend-degree seq, मग एक degree खालचे low — फक्त confirm_bar ≤ upto) आणि जिचा wave 5 bar [w_lo, w_hi] मध्ये सुरू होतो (चालू leg
    आधीच्या correction मधून — bar ने, किंमतीने नाही: Rule 4 चा origin correction चा शेवट / खालच्या degree चा pivot असला तरी).
    नसेल ⇒ None."""
    for q in cands:
        for src in (seq, low):
            pr, br = DL.leg_points(src, q.bar, q.price, end.bar, end.price, upto)
            if DL.read_counter(pr)["family"] != "impulse":
                continue
            segs = DL._motive_segs(pr)
            if segs is not None and w_lo <= br[len(pr) - len(segs[4])] <= w_hi:
                return q
    return None


def fold_impulse(d, s=None):
    """Q15 (Abhi, FINAL): degree-aware Dow — trend = शेवटच्या **impulse** leg ची दिशा; protected = त्या impulse चा **origin**.

    • सुरुवात: LH (H2 हा H1 च्या area पर्यंत पोहोचत नाही — C-13) confirmed आणि Daily **close** त्या दोन H मधल्या L खाली (LL) ⇒ DOWN. रचना = (1) H1 → L, (2) L → H2
      (LH), आता (3). Origin = H2; (1) ची लांबी = H1 − L; correction-degree संदर्भ = (2) चा आकार (H2 − L). UP आरसा.
    • Impulse टोक = origin नंतरचं सर्वात टोकाचं low (correction सुरू होईपर्यंत रोज पुढे).
    • Correction (त्याच degree ची) = impulse टोकानंतरचा confirmed उलट swing ज्याचा आकार ≥ `corr_degree_frac` × मागच्या same-degree
      correction चा आकार. त्यापेक्षा लहान उलट swings = impulse च्या आतले (minor) ⇒ दुर्लक्ष (minor LH close ने तुटला तरी काही नाही).
    • नवा impulse = correction नंतर Daily **close** impulse टोकापलीकडे ⇒ protected पुढे = correction चं टोक (wave + 2); संदर्भ = ही
      correction. Correction शिवाय ⇒ तोच impulse वाढतो.
    • Origin Daily close ने तुटला ⇒ phase "origin_broken" (trend तसाच; conviction cap नाही — Q23). Trend बदलतो फक्त उलट impulse ने:
      (अ) जुन्या impulse टोकापासून उलट रचना (LH + मधल्या L खाली close) आधीच झाली ⇒ लगेच flip, origin = सर्वात उंच LH (degree
      डेटा-सुरुवातीवर अवलंबून नाही); (आ) नाहीतर break नंतरचा HL / LH + break-नंतरच्या टोकापलीकडे close. त्याआधी impulse टोकापलीकडे
      close ⇒ जुना trend नव्या impulse ने चालू.
    • Q49 (Abhi): counter-move चा 5-wave पहिला पाय default wave A (parent टिकला ⇒ A1 correction, `wave_a`, alt "1" फक्त debug);
      wave 1 (flip शक्य) फक्त (a) तो correct करत असलेल्या impulse च्या origin पलीकडे close (`imp_origin`: चालू impulse leg चा
      origin, किंवा तो leg ज्या पूर्ण 5-wave चा wave 5 आहे त्याची सुरुवात — ABC_FIX rule 1) किंवा (b) counter-move स्वतःची same-degree 5-wave रचना
      (`daily_legs.unfolded_123`: "1" 5, "2" 3, "3" "1" पलीकडे स्वतः 5). Ratios / खोली नाहीत.
    • Maturity (पुरावा, gate नाही): wave (5) किंवा पुढे (impulse) आणि किंमत target च्या area मध्ये / पलीकडे (C-13: swing candle, wick ते body).
      Targets: (5) = (4) टोक − (1) ची लांबी (DOWN), आणि (1) सुरू होण्याआधीचा उलट swing (उदा. (A) low).
    RANGE: trend नसताना दोन H / दोन L "समान" (C-13: नंतरचा टोक आधीच्या पलीकडे नाही). UNKNOWN फक्त ≤ daily_min_sessions candles."""
    s = S3.load(s)
    d = d.reset_index(drop=True)
    kat = known_at_of(d)
    sig = sigma_d(d, int(s["daily_sigma_sessions"]))
    raw = _raw_pivots(d, s, kat, sig)
    A = _arr(d)
    H, L, C = A["high"], A["low"], A["close"]
    by_conf = {}
    for p in raw:
        by_conf.setdefault(p.confirm_bar, []).append(p)
    # एक degree खालचे pivots (N − 1; Q22 आतले pullbacks, Q32 आतली रचना) — confirm क्रमाने; N = 1 / dc ⇒ हेच pivots
    nlow = int(s["daily_pivot_n"]) - 1
    low_all = pivots_pivot(d, nlow, kat) if (s["daily_swing_method"] == "pivot" and nlow >= 1) else list(raw)
    low = []                                                               # bar i पर्यंत confirmed (loop मध्ये वाढतो)
    low_by = {}
    for p in low_all:
        low_by.setdefault(p.confirm_bar, []).append(p)
    # Abhi (L1-b ⇒ C-13): no σ tolerances in the Daily reading — "equal" = the later extreme does not go beyond the earlier one;
    # maturity is context only and "near" = price reached the projection's area (its swing candle, wick to body)
    O_ = d["open"].to_numpy(float)

    def body_edge(bar, dn):                                                # the far edge of a swing candle's body: a low's area runs
        return float(min(O_[bar], C[bar]) if dn < 0 else max(O_[bar], C[bar]))   # from its wick up to its body (a high's: mirror)

    def equal(later, earlier):                                             # method "equal": the later extreme reaches the earlier swing
        dn = -1 if earlier.kind == "L" else 1                              # candle's area (wick to body) and does not go beyond it
        return (later.price - earlier.price) * dn <= 0 and (later.price - body_edge(earlier.bar, dn)) * dn >= 0

    def short_of(later, earlier):                                          # a lower high / higher low: stays short of the earlier area
        dn = -1 if earlier.kind == "L" else 1
        return (later.price - body_edge(earlier.bar, dn)) * dn < 0
    cfrac = float(s["corr_degree_frac"])
    rule = s["corr_degree_rule"]
    if rule not in ("internal_pullback", "ratio"):
        raise ValueError(f"corr_degree_rule {rule!r} — internal_pullback / ratio पैकी")
    gate, range_after = bool(s["daily_start_nature_gate"]), bool(s["range_after_trend"])
    pgate = bool(s["daily_parent_gate"])
    A2, mcache = DL.arrays(d), {}

    def piv(kind, bar):
        price = float(H[bar] if kind == "H" else L[bar])
        return DPivot(kind, price, int(bar), pd.Timestamp(d["timestamp"].iloc[bar]), int(bar), kat[bar])

    def extreme(dirn, a, b):                                               # [a, b] मधलं impulse-दिशेचं टोक
        return a + int(np.argmin(L[a:b + 1]) if dirn < 0 else np.argmax(H[a:b + 1]))

    seq, out = [], []
    trend, dirn, band, brk = "NEUTRAL", 0, None, -1
    origin = imp_end = w1_start = None
    phase, k_imp, ref_corr, broken_at, leg_start = None, 0, None, None, None
    prev_int = 0.0                                                         # Q22: मागच्या impulse leg चा सर्वात मोठा आतला pullback
    porg, pcorr, tstart_org = None, False, None                            # A1 / ABC_FIX: parent = trend च्या impulse ची सुरुवात
    t_first, t_first_par = None, None                                      # Q44: parent origin नंतरच्या पहिल्या impulse leg चं टोक (target) + तो parent
    cm_cache, sharp, evid = {}, None, ()                                   # counter-move वर्गीकरण cache; sharp-fall / rise zone; पुरावा
    cm0 = None                                                             # चालू counter-move (correction) ची सुरुवात = impulse टोक
    czone = None                                                           # शेवटची correction sharp zone मध्ये संपली ⇒ ती zone
    leg_cm = None                                                          # चालू leg ज्या counter-move नंतर सुरू झाला त्याची सुरुवात (bar)
    wave_a = None                                                          # Q49: A1 correction चा 5-wave पहिला पाय (wave A) — त्याचं टोक

    def counter_kind(i):
        """ABC_FIX rule 1: impulse टोकापासून आजच्या टोकापर्यंतची **संपूर्ण** counter-move एकच वाचली (Q32 adapter, एक degree खालचे
        pivots): "impulse" (5-wave नियम / diagonal) / "corrective" (3-wave, triangle, combination) / "single". c ने a ओलांडला किंवा
        b ने नवा टोक केला तरी 3-wave ⇒ correction."""
        st0 = cm0 or imp_end                                               # expanded flat चा b नवा टोक ⇒ सुरुवात तीच (E)
        seg = H[st0.bar:i + 1] if dirn < 0 else L[st0.bar:i + 1]
        tb = st0.bar + int(np.argmax(seg) if dirn < 0 else np.argmin(seg))
        if tb <= st0.bar:
            return "single", tb
        key = (st0.bar, tb, len(low), leg_start, round(prev_int, 9))      # degree तपासणी leg_start / prev_int वर अवलंबून
        if key not in cm_cache:
            tpx = float(H[tb] if dirn < 0 else L[tb])
            k = DL.classify(A2, seq, st0.bar, st0.price, tb, tpx, i, cache=mcache, inner_seq=low, elliott=True)["structure"]
            if k == "impulse":                                             # degree (Q22 माप): counter impulse चा wave 2 / 4 आधीच्या
                own = int_pull(-dirn, st0.bar, tb, i)                      # trend-degree impulse च्या सर्वात मोठ्या आतल्या pullback इतका
                ref = max(int_pull(dirn, leg_start, st0.bar, i), prev_int)  # हवा — Q22 degree_ref (चालू / मागच्या leg चा आतला
                                                                           # pullback); लहान ⇒ एक degree खाली
                if own < ref:                                              # खालचा 5-wave (zigzag चा a) ⇒ trend उलटत नाही
                    k = "wave_a"
                elif not DL.unfolded_123(DL.leg_prices(seq, st0.bar, st0.price, tb, tpx, i, inner_seq=low)):
                    k = "wave_1a"                                          # Q49 (Abhi): same-degree 5-wave पहिला पाय default wave A —
                                                                           # wave 1 फक्त (a) impulse origin पलीकडे close किंवा (b)
                                                                           # "1"(5) + "2"(3) + "3" पलीकडे स्वतः 5 waves
            cm_cache[key] = k
        return cm_cache[key], tb

    imp_cache = {}
    q49_org = s["q49_impulse_origin"]
    if q49_org not in ("complete_impulse", "leg"):
        raise ValueError(f"q49_impulse_origin {q49_org!r} — complete_impulse / leg पैकी")

    def imp_origin(i):
        """Q49 (a) (Abhi, ABC_FIX सुसंगत): counter-move ज्या impulse ला correct करते त्याचा origin = चालू impulse leg चा origin.
        विस्तार ("complete_impulse", Abhi मंजुरी बाकी): चालू leg हा एखाद्या **पूर्ण** 5-wave impulse चा wave 5 असेल ⇒ counter-move तो
        संपूर्ण impulse correct करते ⇒ त्याची सुरुवात P. वाचन: P ⇒ imp_end (trend-degree, नाहीतर एक degree खालचे confirmed pivots)
        read_counter impulse आणि त्याचा wave 5 चालू leg आधीच्या correction मधून सुरू (bar: leg_cm … origin — Rule 4 चा origin
        correction चा शेवट असला तरी). P उमेदवार = origin आधीचे (trend सुरुवातीपर्यंत) उलट-प्रकारचे pivots जे नंतरच्या किंमतीने
        ओलांडलेले नाहीत (impulse ची सुरुवात त्याचा टोक असतो) — जवळचा आधी. नसेल ⇒ origin."""
        if q49_org == "leg":
            return origin
        ok = "H" if dirn < 0 else "L"
        lo_bar = tstart_org.bar if tstart_org is not None else origin.bar
        pool = [p for p in seq if p.kind == ok and lo_bar <= p.bar < origin.bar and p.confirm_bar <= i]
        if tstart_org is not None and tstart_org.bar < origin.bar and all(p.bar != tstart_org.bar for p in pool):
            pool.append(tstart_org)
        w_lo = leg_cm if (leg_cm is not None and leg_cm <= origin.bar) else origin.bar
        cands = []
        for q in sorted(pool, key=lambda p: -p.bar):                       # जवळचा आधी; नंतर ओलांडलेला टोक impulse सुरुवात नाही
            seg = H[q.bar + 1:imp_end.bar + 1] if dirn < 0 else L[q.bar + 1:imp_end.bar + 1]
            if len(seg) and ((seg.max() > q.price) if dirn < 0 else (seg.min() < q.price)):
                continue
            cands.append(q)
        tail = (len(seq), seq[-1].bar if seq else -1, seq[-1].price if seq else None, len(low))
        for q in cands:
            key = (q.bar, imp_end.bar, origin.bar, w_lo) + tail
            if key not in imp_cache:
                imp_cache[key] = complete_impulse_start([q], seq, low, imp_end, w_lo, origin.bar, i) is not None
            if imp_cache[key]:
                return q
        return origin

    prov = []                                                              # तात्पुरत्या completions (continuation confirm होईपर्यंत)
    PROV_KEYS = ("origin", "k_imp", "leg_start", "pcorr", "porg", "tstart_org", "prev_int", "ref_corr", "cm0", "imp_end", "sharp",
                 "leg_cm", "evid", "czone", "t_first", "t_first_par", "wave_a")   # Q44 target सुद्धा (सुरक्षा; A1 रिकाम्या stack वरच सुरू होतो)

    def corr_end(i):
        """continuation confirm झालं का आणि correction कुठे संपली: तात्पुरत्या origin पासून आजच्या टोकापर्यंतचे उलट (एक degree खालचे)
        pivots — ज्या pivot पासून आजपर्यंतची चाल motive (5-wave / सरळ) वाचते त्यातला सर्वात टोकाचा = correction चा शेवट. नसेल ⇒ None
        (continuation अजून confirm नाही)."""
        okind = "H" if dirn < 0 else "L"
        b0 = prov[0]["cm0"].bar if prov else origin.bar                    # counter-move च्या सुरुवातीपासून (running flat चा c टोकानंतर नाही)
        cands = [origin] + [q for q in low if q.kind == okind and b0 < q.bar < imp_end.bar and q.confirm_bar <= i and q.bar != origin.bar]
        best, wait = None, None
        for q in cands:
            if best is not None and (q.price - best.price) * -dirn <= 0:
                continue
            r = DL.classify(A2, seq, q.bar, q.price, imp_end.bar, imp_end.price, i, cache=mcache, inner_seq=low, elliott=True)
            k = r["structure"]
            if k == "impulse" or (k == "single" and q is origin):          # आतल्या swing पासूनचा एकच पाय (expanded flat च्या b चा c) नाही
                best = q
            elif r.get("form") == "zigzag" and (wait is None or (q.price - wait.price) * -dirn > 0):
                wait = q                                                   # 5-3-5 = impulse चे 1-2-3 सुद्धा ⇒ अजून ठरत नाही
        if best is not None and wait is not None and (wait.price - best.price) * -dirn > 0:
            return None                                                    # वरचा swing अजून continuation ची सुरुवात असू शकतो
        return best

    def push_prov():
        """correction संपली (done / A1) — पण a-b-c चा a / b की खरा शेवट हे continuation नंतरच कळतं (ABC_FIX 1, Q45). आधीची अवस्था
        जपून ठेवा: नवा origin continuation confirm होण्याआधी close ने तुटला ⇒ तीच correction चालू (trend उलटत नाही). Stack confirm
        (corr_end) किंवा अपयशी restore वरच रिकामा होतो; restore फक्त snapshot चा origin / parent आज close ने टिकला असेल तर (Q54)."""
        snap = {k: v for k, v in zip(PROV_KEYS, (origin, k_imp, leg_start, pcorr, porg, tstart_org, prev_int, ref_corr,
                                                    cm0 or imp_end, imp_end, sharp, leg_cm, evid, czone, t_first, t_first_par, wave_a))}
        prov.append(snap)


    def sharp_zone(dn, a, b, i):
        """ABC_FIX rule 2 (Abhi Q55 = B): "sharp-fall point" = wide-range दिशेच्या धावेने तोडलेला **पहिला** swing low (एक degree खालचा)
        (DOWN; UP आरसा: swing high) — जिथे घसरण वेगावली; तुटलेली demand ⇒ supply. धाव = सलग किमान दोन wide-range, impulse-दिशेच्या
        candles (range > impulse च्या स्वतःच्या आधीच्या bars ची सरासरी; candle चा रंग impulse दिशेचा). Swing impulse origin (a)
        च्या आधीचाही चालतो (BANKNIFTY: Feb top आधीचा late-Jan low) — अट एकच: त्याचा पहिला close-break a नंतर, धावेतल्या candle ने
        झाला असेल तरच तो उमेदवार; सर्वात आधी तुटलेला निवडला (एकाच candle ने दोन ⇒ आधी ओलांडलेला, म्हणजे
        DOWN ⇒ उंच). Zone = swing candle चं टोक + base candles (swing आणि शेजारचे candles) चे bodies, ± इतर पट्ट्यांसारखा half
        (C-13: half = 0 — the area itself, never widened). फक्त confirmed (≤ i) pivots आणि ≤ i bars. नसेल ⇒ None."""
        if b - a < 2:
            return None
        O = d["open"].to_numpy(float)
        R_ = H - L
        wide = {}

        def wd(k):                                                         # wide-range, impulse-दिशेचा candle?
            if k not in wide:
                ok_ = a + 1 <= k - 1 and k <= i
                wide[k] = bool(ok_ and R_[k] > R_[a + 1:k].mean() and (C[k] - O[k]) * dn > 0)
            return wide[k]

        def in_run(k):
            return wd(k) and (wd(k - 1) or (k + 1 <= i and wd(k + 1)))

        kind = "L" if dn < 0 else "H"
        best = None
        for p in low:                                                      # एक degree खालचे confirmed swings (धावेच्या आतले lows सुद्धा)
            if p.kind != kind or p.confirm_bar > i or p.bar >= b:
                continue
            brk = (C[p.bar + 1:i + 1] - p.price) * dn > 0                  # p नंतर पहिला close-break
            if not brk.any():
                continue
            t = p.bar + 1 + int(np.argmax(brk))
            if t <= a or not in_run(t):
                continue
            key = (t, p.price * dn)                                        # आधी तुटलेला; एकाच candle वर ⇒ आधी ओलांडलेला
            if best is None or key < best[0]:
                best = (key, p)
        if best is None:
            return None
        q = best[1]
        half = 0.0                                                         # Abhi (C-13): the area itself, never widened by a σ band
        k0, k1 = max(q.bar - 1, 0), min(q.bar + 1, len(d) - 1)
        if dn < 0:                                                         # supply: swing low पासून base bodies च्या वरपर्यंत
            lo, hi = float(L[q.bar]), float(max(max(O[k], C[k]) for k in range(k0, k1 + 1)))
        else:                                                              # demand: base bodies च्या खालपासून swing high पर्यंत
            lo, hi = float(min(min(O[k], C[k]) for k in range(k0, k1 + 1))), float(H[q.bar])
        return (lo - half, hi + half, int(q.bar))

    def int_pull(dn, a, b, i):
        """Q22: (a, b) मधल्या impulse (दिशा dn) चा सर्वात मोठा आतला pullback (किंमत) — एक degree खालचे confirmed (≤ i) उलट pivots,
        प्रत्येक त्याच्या आधीच्या (a पासून) impulse-टोकापासून मोजलेला. नसेल ⇒ 0."""
        ok, out = ("H" if dn < 0 else "L"), 0.0
        for q in low:
            if q.kind == ok and a < q.bar < b and q.confirm_bar <= i:
                j = extreme(dn, a, q.bar)
                out = max(out, (q.price - float(L[j] if dn < 0 else H[j])) * -dn)
        return out

    def degree_ref(p_bar, i):
        """Q22 संदर्भ: चालू impulse leg (leg_start ⇒ p आधीचं टोक) चा सर्वात मोठा आतला pullback, किंवा मागच्या impulse leg चा (त्याच
        degree चे आतले पाय खालच्या degree चे) — जो मोठा. दोन्ही 0 (सरळ legs) ⇒ 0 ⇒ हा pullback आतलाच धरतो आणि पुढच्यांचा संदर्भ बनतो."""
        return max(int_pull(dirn, leg_start, extreme(dirn, leg_start, p_bar), i), prev_int)

    def pre_ext(p):
        """correction swing p आधीचं (leg_start पासून) impulse-दिशेचं टोक (किंमत)."""
        j = extreme(dirn, leg_start, p.bar)
        return float(L[j] if dirn < 0 else H[j])

    def corrections(i):
        """चालू impulse leg (leg_start पासून) मधले same-degree उलट swings (confirmed ≤ i): आकार = p − p-आधीचं टोक ≥ cfrac × संदर्भ.
        p-आधीच्या टोकाशी मोजतो ⇒ pivot उशिरा (N bars) confirm झाला आणि त्याआधीच नवा LL आला तरी correction हरवत नाही (review 🔴1)."""
        ok = "H" if dirn < 0 else "L"
        cand = [p for p in seq if p.kind == ok and p.bar > leg_start and p.confirm_bar <= i]
        if rule == "ratio":
            return [p for p in cand if (p.price - pre_ext(p)) * -dirn >= cfrac * ref_corr]
        out = []
        for p in cand:                                                     # Q22: रचनात्मक, प्रमाण नाही
            ref = degree_ref(p.bar, i)
            if ref > 0 and (p.price - pre_ext(p)) * -dirn > ref:            # आतला संदर्भच नाही ⇒ पहिला pullback आतलाच (Q35 default)
                out.append(p)
        return out

    def beyond_after(p, i):
        """p नंतर (≤ i) कोणत्या Daily close ने p-आधीचं टोक impulse-दिशेने ओलांडलं?"""
        seg = C[p.bar + 1:i + 1]
        return bool(len(seg)) and bool(((seg - pre_ext(p)) * dirn > 0).any())

    def start(nd, org, w1s, w1l, ref, i, why_, w1e_bar=None):
        nonlocal trend, dirn, band, origin, imp_end, w1_start, phase, k_imp, ref_corr, broken_at, leg_start, prev_int, porg, pcorr, \
            tstart_org, sharp, evid, cm0, prov, leg_cm, czone, t_first, t_first_par, wave_a
        trend, dirn, band = ("UP" if nd > 0 else "DOWN"), nd, None
        porg, pcorr, sharp, evid, cm0, prov, leg_cm, czone, t_first, t_first_par = None, False, None, (), None, [], None, None, None, None
        wave_a = None
        tstart_org = w1s if w1s is not None else org                       # ABC_FIX: parent = trend च्या impulse ची सुरुवात (टोक)
        origin, w1_start, ref_corr, k_imp, phase, broken_at = org, w1s, max(ref, 1e-9), 2, "impulse", None   # w1l: (1) ची लांबी
                                                                           # (Q44 नंतर target ला वापर नाही; signature तसाच)
        leg_start = org.bar
        prev_int = int_pull(nd, w1s.bar, w1e_bar, i) if (w1s is not None and w1e_bar is not None) else 0.0   # (1) चा आतला pullback
        imp_end = piv("H" if nd > 0 else "L", extreme(nd, org.bar, i))
        return why_

    def nature_ok(nd, w1s, w1e, org, i, tag="trend नाही (Q28)"):
        """Q28: trend सुरुवात फक्त impulse-स्वभावाच्या पायाने — (1) = w1s ⇒ w1e किंवा (3) = org ⇒ आजचं टोक impulse (Q32 adapter:
        5-wave impulse रचना किंवा legs2 C = IMP). C चा baseline नसेल (warm-up) तर फक्त रचना: corrective (3-wave) ⇒ नाही.
        रिटर्न (ok, why-जोड)."""
        if not gate:
            return True, ""
        e = extreme(nd, org.bar, i)
        c1 = DL.classify(A2, seq, w1s.bar, w1s.price, w1e.bar, w1e.price, i, cache=mcache, inner_seq=low)
        c3 = DL.classify(A2, seq, org.bar, org.price, e, float(H[e] if nd > 0 else L[e]), i, cache=mcache, inner_seq=low)
        kinds = (c1["kind"], c3["kind"])
        if "impulse" in kinds:
            return True, f" ((1) {DL.tag(c1)}, (3) {DL.tag(c3)})"
        if c1["C"] is None and c3["C"] is None and "corrective" not in kinds:   # C माहीत नाही (warm-up / ≤ 2-bar पाय) ⇒ फक्त रचना
            return True, " (C नाही; रचना corrective नाही)"
        return False, (f"{'UP' if nd > 0 else 'DOWN'} रचना पण impulse-स्वभावाचा पाय नाही ((1) {DL.tag(c1)}, (3) {DL.tag(c3)}) "
                       f"⇒ {tag}")

    def rev_shapes(i, held=False):
        """Q29 (अ) उलट रचना: जुन्या impulse टोकानंतरचा उलट-दिशेचा HL (DOWN trend मध्ये; UP ⇒ LH) जो नंतर (wick ने) ओलांडला नाही,
        आणि आज Daily close त्याआधीच्या (टोकानंतरच्या) सर्वात टोकाच्या मधल्या swing पलीकडे — (h, lm) जोड्या, सर्वात खालचा HL (UP ⇒
        सर्वात उंच LH) आधी. फक्त आकार; impulse-स्वभाव (Q36) वेगळा तपासतात. held = True (trend-first रचना, PR #305 review): HL नंतरचा
        कोणताही close (≤ आज) पलीकडे पुरे — close परत मधल्या swing आत आला तरी HL अखंड असेपर्यंत रचना टिकते (Dow: HL तुटेपर्यंत);
        clear फक्त HL wick ने तुटणं किंवा नवा impulse टोक (imp_end पुढे)."""
        nd = -dirn
        okind = "H" if nd < 0 else "L"
        e0 = rev_anchor(i) if held else imp_end
        cands = [p for p in seq if p.kind == okind and p.bar > e0.bar and p.confirm_bar <= i
                 and (p.price - e0.price) * nd > 0]
        for h in sorted(cands, key=lambda p: p.price * nd):           # सर्वात उंच LH (DOWN) / सर्वात खालचा HL (UP) आधी
            later = H[h.bar:i + 1].max() if nd < 0 else L[h.bar:i + 1].min()
            if (later - h.price) * nd < 0:
                continue                                                   # नंतर किंमत त्या LH / HL पलीकडे गेली ⇒ origin नाही (review 🟡2)
            mids = [p for p in seq if p.kind == ("L" if nd < 0 else "H") and e0.bar < p.bar < h.bar]
            if not mids:
                continue
            lm = min(mids, key=lambda p: p.price * -nd)               # (1) चं टोक
            if held:                                                       # रचना (gate): HL नंतर कधीही (≤ आज) close पलीकडे
                ok_c = bool((((C[h.bar + 1:i + 1] - lm.price) * nd) > 0).any())
            else:                                                          # flip: आजचाच close (Q29 त्याच दिवशी)
                ok_c = (C[i] - lm.price) * nd > 0
            if ok_c:
                yield h, lm

    def rev_structure(i):
        """Trend first (Abhi, setups audit — docs/reports/setups_prA_v1_audit.md): flip चा (अ) नियम — उलट रचना + नव्या दिशेचा impulse-स्वभावाचा पाय (Q36) — origin
        close-break शिवाय आधीच पूर्ण झाला का? झाला ⇒ (h, lm): Daily रचना trend विरुद्ध (flip ला फक्त origin पलीकडचा close बाकी).
        Trend / phase / protected बदलत नाहीत (Q15); फक्त ① gate trend-बाजू अडवतो. नाही ⇒ None."""
        if dirn == 0 or imp_end is None or imp_end.bar >= i:
            return None
        e0 = rev_anchor(i)
        if e0.bar >= i:
            return None
        for h, lm in rev_shapes(i, held=True):                             # Daily swings (seq, spec ① Dow) — flip सारखेच; Q22 ने
            if nature_ok(-dirn, e0, lm, h, i)[0]:                          # गाळलेले swings नाहीत (अहवाल: NIFTY 2020 rally Q22 degree ला
                return h, lm                                               # एकच पाय ⇒ तसं गाळलं तर defect राहतो)
        return None

    def rev_anchor(i):
        """counter-move ची सुरुवात = impulse टोकानंतरचं (imp_end पासून आजपर्यंत) trend-दिशेचं सर्वात टोकाचं बिंदू (≤ i). सहसा imp_end
        स्वतः; provisional restore (ABC_FIX 1) ने imp_end आधीच्या leg वर परत गेला तरी रचना त्याच टोकापासून (PR #305 review)."""
        return piv("H" if dirn > 0 else "L", extreme(dirn, imp_end.bar, i))

    def flip(i):
        """origin_broken नंतर उलट impulse? (break च्या दिवशीही तपासतो.) Q36 (Abhi): उलट रचनेत नव्या दिशेचा impulse-स्वभावाचा पाय हवा
        (Q28 नियम flip ला सुद्धा; Q29: त्याच दिवशी flip फक्त तेव्हाच) — फक्त corrective पायांची उलट रचना ⇒ flip नाही, origin_broken
        (Q23 कमाल B). रिटर्न why ("" ⇒ काही नाही; flip नाही पण नकार ⇒ कारण)."""
        why, nd, ek = "", -dirn, ("L" if dirn < 0 else "H")
        tag = "flip नाही — origin तुटला, उलट impulse नाही (Q36; कमाल B)"
        blocked = ""
        # (अ) मोठी degree: जुन्या impulse टोकापासूनच उलट रचना (LH + मधल्या L खाली close / HL आरसा) आधीच झाली असेल ⇒ लगेच flip;
        #     origin = त्या टोकानंतरचा सर्वात उंच LH (UP ⇒ सर्वात खालचा HL) — minor post-break swing नाही (degree-स्वतंत्र).
        flipped = False
        for h, lm in rev_shapes(i):
            ok_n, why_n = nature_ok(nd, imp_end, lm, h, i, tag)
            if not ok_n:
                blocked = blocked or why_n
                continue
            why = start(nd, h, imp_end, abs(imp_end.price - lm.price), abs(h.price - lm.price), i,
                        f"origin तुटला + उलट रचना ⇒ {'UP' if nd > 0 else 'DOWN'} (origin {h.price:,.2f})", lm.bar)
            flipped = True
            break
        post = [] if flipped else [p for p in seq if p.kind == ek and p.bar > broken_at and p.confirm_bar <= i
                                   and (p.price - imp_end.price) * -dirn > 0]   # (आ) break नंतरचा खरा HL / LH (जुन्या टोकाच्या आत; 🟡3)
        if post:
            hl = post[-1]
            ext_bar = broken_at + int(np.argmax(H[broken_at:hl.bar + 1]) if dirn < 0 else np.argmin(L[broken_at:hl.bar + 1]))
            ext = float(H[ext_bar] if dirn < 0 else L[ext_bar])
            if (C[i] - ext) * -dirn > 0:
                nd = -dirn                                             # (1) = जुन्या impulse टोकापासून break नंतरच्या टोकापर्यंत
                ok_n, why_n = nature_ok(nd, imp_end, piv("H" if dirn < 0 else "L", ext_bar), hl, i, tag)
                if ok_n:
                    why = start(nd, hl, imp_end, abs(ext - imp_end.price), abs(ext - hl.price), i,
                                f"origin तुटल्यानंतर उलट impulse ⇒ {'UP' if nd > 0 else 'DOWN'} (origin {hl.price:,.2f})", ext_bar)
                else:
                    blocked = blocked or why_n
        return why or blocked

    for i in range(len(d)):
        why, corr = "", []
        for p in by_conf.get(i, []):
            _add(seq, p)
        low.extend(low_by.get(i, []))
        ek = "L" if dirn < 0 else "H"
        if dirn != 0 and phase == "origin_broken":
            why = flip(i) or why
        if dirn != 0 and phase in ("impulse", "correction", "origin_broken"):
            ek = "L" if dirn < 0 else "H"
            corr = corrections(i)
            done = [] if pcorr else [p for p in corr if beyond_after(p, i) and (C[i] - p.price) * dirn > 0]   # A1 ⇒ खालचा नियम;
                                                                           # आज close ने तुटलेला टोक origin होऊ शकत नाही
            if done:                                                       # correction नंतर close त्या आधीच्या टोकापलीकडे ⇒ नवा impulse
                top = max(done, key=lambda p: p.price * -dirn)             # पूर्ण correction चं टोक ((4) high; आतले b-swings नाहीत)
                push_prov()
                ref_corr = abs(top.price - pre_ext(top))
                prev_int = int_pull(dirn, leg_start, extreme(dirn, leg_start, top.bar), i)   # संपलेल्या impulse leg चा आतला pullback
                leg_cm, czone = (cm0 or imp_end).bar, None
                origin, phase, k_imp, leg_start, pcorr, cm0 = top, "impulse", k_imp + 1, top.bar, False, None
                why = f"नवा impulse (L{2 * k_imp - 1}) ⇒ protected पुढे = correction टोक {origin.price:,.2f}"
                corr = corrections(i)
            if pcorr and imp_end.bar < i:                                  # A1 correction कधी संपली? (Dow: counter-move चा शेवटचा HL close ने तुटला)
                seg = H[imp_end.bar + 1:i + 1] if dirn < 0 else L[imp_end.bar + 1:i + 1]
                tb = imp_end.bar + 1 + int(np.argmax(seg) if dirn < 0 else np.argmin(seg))
                hl = [p for p in seq if p.kind == ek and imp_end.bar < p.bar < tb and p.confirm_bar <= i]
                lvl = hl[-1].price if hl else imp_end.price
                fire = tb < i and (C[i] - lvl) * dirn > 0                  # Q45: फक्त counter-move च्या शेवटच्या HL पलीकडे close (टोकानंतरचा
                                                                           # LH + मधला L नियम complex correction च्या आतल्या minor रचनेवर
                                                                           # लवकर फुटतो — NIFTY (4) — म्हणून नाही)
                tpx = float(H[tb] if dirn < 0 else L[tb])
                at_sharp = sharp is not None and sharp[0] <= tpx <= sharp[1]
                if not fire and at_sharp and tb < i and (C[i] - (sharp[0] if dirn < 0 else sharp[1])) * dirn > 0:
                    fire, lvl = True, (sharp[0] if dirn < 0 else sharp[1])  # ABC_FIX rule 3: sharp zone मध्ये संपली + trend दिशेने close
                if fire:                     # trend-दिशेचं पुढे जाणं ⇒ nature gate नाही (Q28 / Q36 फक्त सुरुवात / flip)
                    top = piv("H" if dirn < 0 else "L", tb)
                    push_prov()
                    ref_corr = max(abs(top.price - imp_end.price), 1e-9)
                    t0 = tstart_org.bar if tstart_org is not None else leg_start   # trend-degree correction ⇒ नव्या impulse चा degree
                    prev_int = int_pull(dirn, t0, imp_end.bar, i)          # संदर्भ = आधीच्या trend-degree impulse चा सर्वात मोठा आतला pullback
                    leg_cm = (cm0 or imp_end).bar
                    origin, phase, k_imp, leg_start, pcorr, cm0, wave_a = top, "impulse", k_imp + 1, tb, False, None, None
                    czone = sharp if at_sharp else None
                    if at_sharp:
                        evid = evid + (f"correction ended at sharp-{'fall supply' if dirn < 0 else 'rise demand'} "
                                       f"{sharp[0]:,.0f}-{sharp[1]:,.0f}",)
                    tstart_org, sharp = top, None                          # नवा trend-degree impulse इथून (parent / degree / sharp zone)
                    why = (f"correction (A1) संपली — close counter-move च्या शेवटच्या {'HL' if dirn < 0 else 'LH'} {lvl:,.2f} "
                           f"पलीकडे ⇒ नवा impulse (L{2 * k_imp - 1}), protected = correction टोक {top.price:,.2f}")
                    corr = corrections(i)
            imp_end = piv(ek, extreme(dirn, leg_start, i))                 # leg चं टोक (wick सह; origin_broken मध्येही — 🟡3 / 🟡4)
            if phase == "impulse" and not pcorr and tstart_org is not None and imp_end.bar == i:   # नवा टोक ⇒ sharp zone पुन्हा
                sharp = sharp_zone(dirn, tstart_org.bar, imp_end.bar, i) or sharp
            if prov and imp_end.bar == i and (imp_end.price - prov[0]["cm0"].price) * dirn > 0:
                end = corr_end(i)                                          # correction सुरुवातीच्या पलीकडे motive continuation ⇒ confirm
                if end is not None:
                    leg_cm = prov[0]["cm0"].bar                            # पूर्ण correction ची सुरुवात (आतल्या तात्पुरत्या completions सह)
                    prov.clear()
                    if end.bar != origin.bar:                              # Rule 4: origin = correction चा शेवट (triangle e, truncated /
                        why = (f"continuation confirm ⇒ origin = correction चा शेवट {end.price:,.2f} "   # running चा c), टोक नाही
                               f"(टोक {origin.price:,.2f} नाही)")
                        if tstart_org is not None and tstart_org.bar == origin.bar:
                            tstart_org = end                               # नवा trend-degree impulse सुद्धा शेवटापासून
                        origin, leg_start = end, end.bar
            while prov and phase != "origin_broken" and (C[i] - origin.price) * dirn < 0:
                snap = prov.pop()                                          # तात्पुरता origin तुटला ⇒ ती completion नव्हती (a / b चा पाय)
                keep = snap["porg"] if snap["pcorr"] else snap["origin"]   # परत जायचं तर ती अवस्था आज टिकलेली हवी (A1 ⇒ parent)
                if keep is None or (C[i] - keep.price) * dirn < 0:
                    prov.clear()                                           # तीही तुटली ⇒ जुन्या अवस्था नाहीत; सामान्य origin_broken
                    break
                origin, k_imp, leg_start, pcorr, porg, tstart_org, prev_int, ref_corr, cm0, imp_end, sharp, leg_cm, evid, czone, \
                    t_first, t_first_par, wave_a = (snap[k] for k in PROV_KEYS)
                why = (f"origin {origin.price:,.2f} वर परत — आधीची correction completion continuation आधीच तुटली ⇒ correction चालू "
                       f"(ABC_FIX 1)")
                corr = corrections(i)
            if phase != "origin_broken":
                phase = "correction" if (corr or pcorr) else "impulse"
                if phase == "correction" and cm0 is None:
                    cm0 = imp_end                                          # correction इथून (b चा नवा टोक आला तरी सुरुवात तीच)
                elif phase == "impulse" and imp_end.bar == i:
                    cm0 = None
                if pgate and (pcorr or (C[i] - origin.price) * dirn < 0):  # ABC_FIX rule 1: counter-move संपूर्ण वाचा
                    cmk, _tb = counter_kind(i)
                    par = tstart_org if (tstart_org is not None and (tstart_org.price - origin.price) * dirn < 0) else None
                    ao = imp_origin(i) if cmk == "wave_1a" else origin
                    if cmk == "impulse" or (cmk == "wave_1a" and (C[i] - ao.price) * dirn < 0):   # Q49 (b) / (a) ⇒ wave 1
                        if cmk == "wave_1a" and ao is not origin:          # (a) पूर्ण impulse च्या सुरुवातीपलीकडे ⇒ तोच तुटलेला origin
                            origin = ao                                    # (pcorr शाखेसारखंच: protected = तुटलेला origin)
                        pcorr, wave_a = False, None                        # — खरा break (flip शक्य)
                    elif par is not None and (C[i] - par.price) * dirn >= 0:
                        if cmk in ("wave_a", "wave_1a"):                   # Q49: 5-wave पहिला पाय ⇒ default wave A (पर्याय "1" फक्त debug)
                            new_a = piv("H" if dirn < 0 else "L", _tb)
                            if wave_a is not None and wave_a.bar == new_a.bar:
                                pass
                            elif cmk == "wave_1a":                         # same degree: (a) impulse origin टिकला (नाहीतर वर flip)
                                why = (f"counter-move 5-wave, पण wave 1 ची अट नाही ((b) same-degree 5-wave रचना नाही; (a) तो "
                                       f"correct करत असलेल्या impulse चा origin {ao.price:,.2f} close ने टिकला) ⇒ wave A "
                                       f"{new_a.price:,.2f} (alt: 1), correction — trend उलटत नाही (Q49)")
                            else:                                          # Q22 खालचा degree: impulse origin तुटला असू शकतो
                                why = (f"counter-move 5-wave पण खालच्या degree चा (Q22) ⇒ wave A {new_a.price:,.2f} (alt: 1); "
                                       f"wave 1 फक्त parent {par.price:,.2f} पलीकडे close ने — correction, trend उलटत नाही (Q49)")
                            wave_a = new_a
                        elif not pcorr:
                            why = (f"impulse origin {origin.price:,.2f} Daily close ने तुटला, पण counter-move {cmk} (3-wave / impulse नाही) आणि "
                                   f"impulse ची सुरुवात {par.price:,.2f} टिकली ⇒ correction, trend उलटत नाही (ABC_FIX 1)")
                        porg, pcorr, phase = par, True, "correction"
                        if t_first is None or t_first_par is None or t_first_par.bar != par.bar:
                            # Q44: A1 correction (impulse origin तुटला, parent टिकला) ⇒ parent origin नंतरचा पहिला impulse leg इथे संपला.
                            # नवा parent (दुसरी A1 correction) ⇒ target नव्या parent नंतरच्या पहिल्या leg चा (जुना टोक नाही — review 🔴2)
                            t_first, t_first_par = cm0 or imp_end, par
                    elif pcorr:                                            # Q49 (a): parent origin सुद्धा close ने तुटला ⇒ wave A नाही
                        origin, pcorr, wave_a = par or porg, False, None         # impulse ची सुरुवात सुद्धा close ने तुटली ⇒ खरा origin_broken
                if not pcorr and (C[i] - origin.price) * dirn < 0:
                    phase, broken_at = "origin_broken", i
                    why = f"protected origin {origin.price:,.2f} Daily close ने तुटला — उलट impulse ची वाट (trend संपलेला नाही)"
                    w = flip(i)                                            # त्याच दिवशी उलट रचना (impulse पायासह) पूर्ण ⇒ लगेच flip
                    why = w if phase == "impulse" else (why + (f" · {w}" if w else ""))
        if range_after and dirn != 0 and phase == "origin_broken":           # Q27: origin तुटला + उलट impulse नाही + दोन समान H / L
            hs = [p for p in seq if p.kind == "H" and p.bar > imp_end.bar and p.confirm_bar <= i]
            ls = [p for p in seq if p.kind == "L" and p.bar > imp_end.bar and p.confirm_bar <= i]
            if len(hs) >= 2 and len(ls) >= 2 and equal(hs[-1], hs[-2]) and equal(ls[-1], ls[-2]):   # C-13 equal edges
                bd = (min(ls[-1].price, ls[-2].price), max(hs[-1].price, hs[-2].price))
                if bd[0] <= C[i] <= bd[1]:                                 # close पट्ट्यात असेल तेव्हाच (नाहीतर लगेच तुटलेली range)
                    trend, dirn, phase, brk, band = "RANGE", 0, None, broken_at, bd
                    why = "origin तुटला + दोन H आणि दोन L जवळपास समान ⇒ RANGE (कडांवर; Q27)"
        if trend in ("NEUTRAL", "RANGE"):
            Hs = [p for p in seq if p.kind == "H" and p.confirm_bar <= i]
            Ls = [p for p in seq if p.kind == "L" and p.confirm_bar <= i]
            if len(Hs) >= 2:                                               # DOWN: LH + close खाली मधल्या L
                h1, h2 = Hs[-2], Hs[-1]
                mid = [p for p in Ls if h1.bar < p.bar < h2.bar]
                if mid and h2.bar > brk and short_of(h2, h1) and C[i] < mid[-1].price:
                    lm = mid[-1]
                    ok_n, why_n = nature_ok(-1, h1, lm, h2, i)
                    if ok_n:
                        why = start(-1, h2, h1, h1.price - lm.price, h2.price - lm.price, i,
                                    "LH + close मागच्या low खाली ⇒ DOWN impulse" + why_n, lm.bar)
                    else:
                        why = why_n
            if trend in ("NEUTRAL", "RANGE") and len(Ls) >= 2:             # UP आरसा
                l1, l2 = Ls[-2], Ls[-1]
                mid = [p for p in Hs if l1.bar < p.bar < l2.bar]
                if mid and l2.bar > brk and short_of(l2, l1) and C[i] > mid[-1].price:
                    hm = mid[-1]
                    ok_n, why_n = nature_ok(1, l1, hm, l2, i)
                    if ok_n:
                        why = start(1, l2, l1, hm.price - l1.price, hm.price - l2.price, i,
                                    "HL + close मागच्या high वर ⇒ UP impulse" + why_n, hm.bar)
                    else:
                        why = why_n
            if trend == "NEUTRAL":
                h1, h2 = _last2(seq, "H")
                l1, l2 = _last2(seq, "L")
                if h1 and l1 and h2.bar > brk and l2.bar > brk and equal(h2, h1) and equal(l2, l1):   # C-13 equal edges
                    trend, band, why = "RANGE", (min(l1.price, l2.price), max(h1.price, h2.price)), "दोन H आणि दोन L जवळपास समान"
            elif trend == "RANGE" and band and (C[i] > band[1] or C[i] < band[0]):
                trend, why, brk, band = "NEUTRAL", "close range पट्ट्याबाहेर", i, None
        # wave / correction पाय / maturity
        wave = corr_label = counter = rev = None
        mature, targets, risk, cbars, passed = False, (), False, (), False
        if dirn != 0 and phase:
            if phase in ("correction", "origin_broken"):                   # trend first: same-degree (Q22) counter-move ची रचना trend
                rev = rev_structure(i)                                     # विरुद्ध? (gate; trend बदल नाही). lower-degree pullback ची
                                                                           # रचना trend-degree नाही ⇒ तपासत नाही
            wave = f"L{2 * k_imp - 1}" if phase == "impulse" else f"L{2 * k_imp}"   # Q34: mechanical leg index (debug); Elliott लेबल फक्त advisory
            if phase in ("correction", "origin_broken"):
                prev_px, prev_k, n_after = imp_end.price, imp_end.kind, 0   # फक्त same-degree, H / L आलटून पालटून पाय
                lref = cfrac * ref_corr if rule == "ratio" else max(int_pull(dirn, leg_start, imp_end.bar, i), prev_int)
                for p in seq:
                    if p.bar > imp_end.bar and p.confirm_bar <= i and p.kind != prev_k and (
                            abs(p.price - prev_px) >= lref if rule == "ratio" else (lref > 0 and abs(p.price - prev_px) > lref)):
                        prev_px, prev_k, n_after = p.price, p.kind, n_after + 1
                corr_label = "abcde"[min(n_after, 4)]                      # 1 swing ⇒ a पूर्ण, b चालू
            t_live = t_first is not None and phase in ("impulse", "correction") and (pcorr or imp_end.bar > t_first.bar)
            passed = t_live and ((porg if pcorr else origin).price - t_first.price) * dirn >= 0
            if t_live and not passed:
                # Q44 (Abhi): target = parent origin नंतरच्या पहिल्या impulse leg चं टोक (BANKNIFTY: Feb top नंतरचा March low). Numeric
                # fallback / projection नाही; अशी रचना नसेल ⇒ target नाही ("target: none (structure incomplete)"). A1 correction चालू
                # असताना target दिसतो (पुढचा leg तिथे जाईल), पण mature फक्त नवा leg चालू असताना (A3): चालू leg चं टोक target च्या near आत /
                # पलीकडे. Protected आधीच target च्या पलीकडे (नवा impulse target ओलांडून पुढे गेला) ⇒ तो जुना, दाखवत नाही
                # (passed ⇒ caption "target passed", रचना नसल्याचा "none" नाही).
                tg = [t_first.price]                                       # C-13: mature = the leg's extreme reached the target's area
                mature = (not pcorr) and (imp_end.price - body_edge(t_first.bar, dirn)) * dirn >= 0
                targets = tuple(round(float(x), 2) for x in tg)
            cbars = tuple(int(p.bar) for p in corr) if phase in ("impulse", "correction") else ()
            if pcorr:
                counter = "correction"
            elif phase == "correction":
                counter = "candidate"
            elif phase == "impulse" and imp_end.bar < i:
                counter = "pullback"                                       # टोकानंतर उलट हालचाल, same-degree correction नाही
            if phase in ("correction", "origin_broken") or counter == "pullback":
                prot_px = porg.price if pcorr else origin.price           # B1: correction किंमत protected origin जवळ ⇒ origin धोक्यात
                ext_c = H[i] if dirn < 0 else L[i]
                prot_bar = porg.bar if pcorr else origin.bar               # C-13: price reached the protected origin's area
                risk = (ext_c - body_edge(prot_bar, -dirn)) * dirn <= 0 and phase != "origin_broken"
        shown = trend if i + 1 > int(s["daily_min_sessions"]) else "UNKNOWN"
        tr = shown in ("UP", "DOWN")
        prot = (porg if pcorr else origin) if trend in ("UP", "DOWN") else None   # A1: parent टिकलेल्या correction मध्ये protected = parent
        out.append(DState(i, pd.Timestamp(d["timestamp"].iloc[i]), kat[i], shown,
                          prot, band if trend == "RANGE" else None,
                          why if shown != "UNKNOWN" else "Daily data अपुरा", list(seq),
                          phase if tr else None, wave if tr else None, corr_label if tr else None, imp_end if tr else None,
                          bool(mature and tr), targets if tr else (),
                          (porg if pcorr else tstart_org) if tr else None, counter if tr else None, leg_start if tr else None, cbars if tr else (),
                          bool(risk and tr), sharp if tr else None, evid if tr else (), czone if tr else None,
                          leg_cm if tr else None, bool(passed and tr),
                          wave_a if (tr and pcorr) else None, "1" if (tr and pcorr and wave_a) else None,
                          rev=rev if tr else None))
    return out


def fold_minor(d, s=None):
    """जुना (v2.2 run1–run2) Dow: protected = सर्वात अलीकडचा minor HL / LH. Q15 नंतर फक्त what-if अहवालासाठी."""
    s = S3.load(s)
    d = d.reset_index(drop=True)
    kat = known_at_of(d)
    sig = sigma_d(d, int(s["daily_sigma_sessions"]))
    if s["daily_swing_method"] == "dc":
        raw = pivots_dc(d, float(s["daily_dc_k"]), sig, kat)
    else:
        raw = pivots_pivot(d, int(s["daily_pivot_n"]), kat)
    C = d["close"].to_numpy(float)
    by_conf = {}
    for p in raw:
        by_conf.setdefault(p.confirm_bar, []).append(p)
    seq, out = [], []
    trend, prot, band, brk = "NEUTRAL", None, None, -1
    eq = float(s["range_eq_sigma_d"])
    for i in range(len(d)):
        why = ""
        for p in by_conf.get(i, []):
            before = seq[-1] if seq else None
            _add(seq, p)
            if not seq or seq[-1] is not p:
                continue                                                 # कमी टोकाचा सलग pivot टाकला ⇒ protected ला हात नाही
            if before is not None and before.kind == p.kind and before is prot:
                prot, why = p, "protected swing अधिक टोकाच्या सलग pivot ने बदलला"
                continue                                                 # (सलग L / H: खरा HL / LH हा नवा)
            if trend == "UP" and p.kind == "L":
                prev = [q for q in seq[:-1] if q.kind == "L"]
                if prev and p.price > prev[-1].price and (prot is None or p.price > prot.price):
                    prot, why = p, "नवा HL ⇒ protected पुढे"
            if trend == "DOWN" and p.kind == "H":
                prev = [q for q in seq[:-1] if q.kind == "H"]
                if prev and p.price < prev[-1].price and (prot is None or p.price < prot.price):
                    prot, why = p, "नवा LH ⇒ protected पुढे"
        tol = eq * sig[i] if np.isfinite(sig[i]) else 0.0
        h1, h2 = _last2(seq, "H")
        l1, l2 = _last2(seq, "L")
        if trend in ("NEUTRAL", "RANGE") and h1 and l1:
            new = h2.bar > brk and l2.bar > brk
            if new and h2.price > h1.price + tol and l2.price > l1.price + tol:
                trend, prot, band, why = "UP", l2, None, "नवा HL + HH"
            elif new and h2.price < h1.price - tol and l2.price < l1.price - tol:
                trend, prot, band, why = "DOWN", h2, None, "नवा LH + LL"
            elif trend == "NEUTRAL" and abs(h2.price - h1.price) <= tol and abs(l2.price - l1.price) <= tol and new:
                trend, band, why = "RANGE", (min(l1.price, l2.price), max(h1.price, h2.price)), "दोन H आणि दोन L जवळपास समान"
        if trend == "UP" and prot is not None and C[i] < prot.price:
            trend, why, brk, prot = "NEUTRAL", f"protected HL {prot.price:,.2f} Daily close ने तुटला", i, prot
        elif trend == "DOWN" and prot is not None and C[i] > prot.price:
            trend, why, brk, prot = "NEUTRAL", f"protected LH {prot.price:,.2f} Daily close ने तुटला", i, prot
        elif trend == "RANGE" and band and (C[i] > band[1] or C[i] < band[0]):
            trend, why, brk, band = "NEUTRAL", "close range पट्ट्याबाहेर", i, None
        shown = trend if i + 1 > int(s["daily_min_sessions"]) else "UNKNOWN"
        out.append(DState(i, pd.Timestamp(d["timestamp"].iloc[i]), kat[i], shown,
                          prot if trend in ("UP", "DOWN", "NEUTRAL") else None, band if trend == "RANGE" else None,
                          why if shown != "UNKNOWN" else "Daily data अपुरा", list(seq)))
    return out


def weekly_from_daily(d):
    """Daily ⇒ Weekly (W-FRI). known_at = आठवड्याच्या शेवटच्या Daily candle चा known_at (अपूर्ण आठवडा ⇒ शेवटचा उपलब्ध दिवस)."""
    d = d.reset_index(drop=True)
    kat = known_at_of(d)
    wk = pd.to_datetime(d["timestamp"]).dt.to_period("W-FRI")
    g = d.assign(_w=wk, _k=kat).groupby("_w", sort=True)
    w = g.agg(timestamp=("timestamp", "first"), open=("open", "first"), high=("high", "max"), low=("low", "min"),
              close=("close", "last"), bar_end=("_k", "last")).reset_index(drop=True)
    return w


def describe(st):
    """① वाचन (मराठी, caption साठी): टप्पा / correction पाय / maturity. Q34: mechanical leg क्रमांक (L5 …) फक्त debug (JSON) —
    Elliott लेबल (1)…(5) / (A)(B)(C) फक्त advisory elliott count मधून."""
    if st.phase is None:
        return ""
    if st.phase == "impulse":
        txt = "impulse" + (" · lower-degree pullback चालू" if st.counter == "pullback" else "")
    elif st.phase == "correction" and st.counter == "correction":
        txt = f"same-degree correction चालू (impulse origin तुटला, parent {st.parent.price:,.0f} टिकला — A1; पाय {st.corr_label})"
    elif st.phase == "correction":
        txt = f"same-degree correction candidate चालू (पाय {st.corr_label})"
    else:
        txt = f"origin close ने तुटला — उलट impulse ची वाट (correction पाय {st.corr_label or '—'}; कमाल B)"
    if st.protected is not None:
        txt += f" · protected origin {st.protected.price:,.0f}"
    if st.mature:
        txt += " · ⚠ impulse mature (target " + " / ".join(f"{x:,.0f}" for x in st.targets) + ") — मोठा reversal शक्य"
    if st.origin_risk:
        txt += " · ⚠ origin धोक्यात (correction origin जवळ)"
    if getattr(st, "rev", None) is not None:
        h, lm = st.rev
        txt += (f" · ⚠ impulse टोकानंतर रचना trend विरुद्ध ({'HL' if h.kind == 'L' else 'LH'} {h.price:,.0f} + close "
                f"{lm.price:,.0f} पलीकडे) — trend-बाजूचे entries नाहीत")
    return txt


def state_at(states, ts):
    """ts ला माहीत असलेली (known_at ≤ ts) शेवटची Daily state; नसेल ⇒ UNKNOWN."""
    import bisect
    ts = pd.Timestamp(ts)
    hit = _KAT_CACHE.get(id(states))
    if hit is None or hit[0] is not states or len(hit[1]) != len(states):   # list चा reference ठेवतो ⇒ id reuse नाही
        if len(_KAT_CACHE) > 16:
            _KAT_CACHE.clear()
        hit = _KAT_CACHE[id(states)] = (states, [x.known_at for x in states])   # known_at क्रमाने ⇒ bisect
    kats = hit[1]
    j = bisect.bisect_right(kats, ts) - 1
    return states[j] if j >= 0 else DState(-1, None, None, "UNKNOWN", why="Daily candle अजून नाही")


_KAT_CACHE = {}


def trade_side(trend):
    """trend ⇒ trade (spec ①): UP ⇒ bull put; DOWN ⇒ bear call; RANGE ⇒ कडेनुसार दोन्ही; NEUTRAL / UNKNOWN ⇒ नाही."""
    return {"UP": ("bull_put",), "DOWN": ("bear_call",), "RANGE": ("bull_put", "bear_call")}.get(trend, ())
