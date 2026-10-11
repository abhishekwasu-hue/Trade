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
    targets: tuple = ()        # maturity targets (equality / मोठा आधीचा swing)


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


def fold_impulse(d, s=None):
    """Q15 (Abhi, FINAL): degree-aware Dow — trend = शेवटच्या **impulse** leg ची दिशा; protected = त्या impulse चा **origin**.

    • सुरुवात: LH (H2 < H1 − tol) confirmed आणि Daily **close** त्या दोन H मधल्या L खाली (LL) ⇒ DOWN. रचना = (1) H1 → L, (2) L → H2
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
    • Maturity (पुरावा, gate नाही): wave (5) किंवा पुढे (impulse) आणि किंमत target च्या `maturity_sigma_d` × σ_D आत / पलीकडे.
      Targets: (5) = (4) टोक − (1) ची लांबी (DOWN), आणि (1) सुरू होण्याआधीचा उलट swing (उदा. (A) low).
    RANGE: trend नसताना दोन H / दोन L जवळपास समान (tol). UNKNOWN फक्त ≤ daily_min_sessions candles."""
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
    eq = float(s["range_eq_sigma_d"])
    msig = float(s["maturity_sigma_d"])
    cfrac = float(s["corr_degree_frac"])
    rule = s["corr_degree_rule"]
    if rule not in ("internal_pullback", "ratio"):
        raise ValueError(f"corr_degree_rule {rule!r} — internal_pullback / ratio पैकी")
    gate, range_after = bool(s["daily_start_nature_gate"]), bool(s["range_after_trend"])
    A2, mcache = DL.arrays(d), {}

    def piv(kind, bar):
        price = float(H[bar] if kind == "H" else L[bar])
        return DPivot(kind, price, int(bar), pd.Timestamp(d["timestamp"].iloc[bar]), int(bar), kat[bar])

    def extreme(dirn, a, b):                                               # [a, b] मधलं impulse-दिशेचं टोक
        return a + int(np.argmin(L[a:b + 1]) if dirn < 0 else np.argmax(H[a:b + 1]))

    seq, out = [], []
    trend, dirn, band, brk = "NEUTRAL", 0, None, -1
    origin = imp_end = w1_start = None
    phase, k_imp, w1_len, ref_corr, broken_at, leg_start = None, 0, None, None, None, None
    prev_int = 0.0                                                         # Q22: मागच्या impulse leg चा सर्वात मोठा आतला pullback

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

    def pre_swing(dirn, w1s):
        """(1) सुरू होण्याआधीचा मोठा उलट swing: DOWN ⇒ w1_start (H) आधीचा, त्याहून उंच शेवटचा confirmed H नंतरचं सर्वात खालचं low
        (त्या leg चं टोक = (A) low); असा H नसेल ⇒ सर्वात टोकाचा confirmed उलट pivot (raw data-सुरुवात नाही). UP आरसा."""
        if w1s is None or w1s.bar < 1:
            return None
        hk = "H" if dirn < 0 else "L"
        above = [p for p in seq if p.kind == hk and p.bar < w1s.bar and (p.price - w1s.price) * -dirn > 0]
        if not above:                                                      # data-सुरुवातीचा raw टोक नाही (review 🟡5): फक्त confirmed उलट pivot
            opp = [p for p in seq if p.kind != hk and p.bar < w1s.bar]
            return min(p.price for p in opp) if opp and dirn < 0 else (max(p.price for p in opp) if opp else None)
        a = above[-1].bar
        seg = L[a:w1s.bar] if dirn < 0 else H[a:w1s.bar]
        return float(seg.min() if dirn < 0 else seg.max()) if len(seg) else None

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
        nonlocal trend, dirn, band, origin, imp_end, w1_start, phase, k_imp, w1_len, ref_corr, broken_at, leg_start, prev_int
        trend, dirn, band = ("UP" if nd > 0 else "DOWN"), nd, None
        origin, w1_start, w1_len, ref_corr, k_imp, phase, broken_at = org, w1s, w1l, max(ref, 1e-9), 2, "impulse", None
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

    def flip(i):
        """origin_broken नंतर उलट impulse? (break च्या दिवशीही तपासतो.) Q36 (Abhi): उलट रचनेत नव्या दिशेचा impulse-स्वभावाचा पाय हवा
        (Q28 नियम flip ला सुद्धा; Q29: त्याच दिवशी flip फक्त तेव्हाच) — फक्त corrective पायांची उलट रचना ⇒ flip नाही, origin_broken
        (Q23 कमाल B). रिटर्न why ("" ⇒ काही नाही; flip नाही पण नकार ⇒ कारण)."""
        why, nd, ek = "", -dirn, ("L" if dirn < 0 else "H")
        tag = "flip नाही — origin तुटला, उलट impulse नाही (Q36; कमाल B)"
        blocked = ""
        # (अ) मोठी degree: जुन्या impulse टोकापासूनच उलट रचना (LH + मधल्या L खाली close / HL आरसा) आधीच झाली असेल ⇒ लगेच flip;
        #     origin = त्या टोकानंतरचा सर्वात उंच LH (UP ⇒ सर्वात खालचा HL) — minor post-break swing नाही (degree-स्वतंत्र).
        okind = "H" if nd < 0 else "L"
        cands = [p for p in seq if p.kind == okind and p.bar > imp_end.bar and p.confirm_bar <= i
                 and (p.price - imp_end.price) * nd > 0]
        flipped = False
        for h in sorted(cands, key=lambda p: p.price * nd):           # सर्वात उंच LH (DOWN) / सर्वात खालचा HL (UP) आधी
            later = H[h.bar:i + 1].max() if nd < 0 else L[h.bar:i + 1].min()
            if (later - h.price) * nd < 0:
                continue                                                   # नंतर किंमत त्या LH / HL पलीकडे गेली ⇒ origin नाही (review 🟡2)
            mids = [p for p in seq if p.kind == ("L" if nd < 0 else "H") and imp_end.bar < p.bar < h.bar]
            if not mids:
                continue
            lm = min(mids, key=lambda p: p.price * -nd)               # (1) चं टोक
            if (C[i] - lm.price) * nd > 0:
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
        why = ""
        for p in by_conf.get(i, []):
            _add(seq, p)
        low.extend(low_by.get(i, []))
        tol = eq * sig[i] if np.isfinite(sig[i]) else 0.0
        ek = "L" if dirn < 0 else "H"
        if dirn != 0 and phase == "origin_broken":
            why = flip(i) or why
        if dirn != 0 and phase in ("impulse", "correction", "origin_broken"):
            ek = "L" if dirn < 0 else "H"
            corr = corrections(i)
            done = [p for p in corr if beyond_after(p, i)]
            if done:                                                       # correction नंतर close त्या आधीच्या टोकापलीकडे ⇒ नवा impulse
                top = max(done, key=lambda p: p.price * -dirn)             # पूर्ण correction चं टोक ((4) high; आतले b-swings नाहीत)
                ref_corr = abs(top.price - pre_ext(top))
                prev_int = int_pull(dirn, leg_start, extreme(dirn, leg_start, top.bar), i)   # संपलेल्या impulse leg चा आतला pullback
                origin, phase, k_imp, leg_start = top, "impulse", k_imp + 1, top.bar
                why = f"नवा impulse (L{2 * k_imp - 1}) ⇒ protected पुढे = correction टोक {origin.price:,.2f}"
                corr = corrections(i)
            imp_end = piv(ek, extreme(dirn, leg_start, i))                 # leg चं टोक (wick सह; origin_broken मध्येही — 🟡3 / 🟡4)
            if phase != "origin_broken":
                phase = "correction" if corr else "impulse"
                if (C[i] - origin.price) * dirn < 0:
                    phase, broken_at = "origin_broken", i
                    why = f"protected origin {origin.price:,.2f} Daily close ने तुटला — उलट impulse ची वाट (trend संपलेला नाही)"
                    w = flip(i)                                            # त्याच दिवशी उलट रचना (impulse पायासह) पूर्ण ⇒ लगेच flip
                    why = w if phase == "impulse" else (why + (f" · {w}" if w else ""))
        if range_after and dirn != 0 and phase == "origin_broken":           # Q27: origin तुटला + उलट impulse नाही + दोन समान H / L
            hs = [p for p in seq if p.kind == "H" and p.bar > imp_end.bar and p.confirm_bar <= i]
            ls = [p for p in seq if p.kind == "L" and p.bar > imp_end.bar and p.confirm_bar <= i]
            if len(hs) >= 2 and len(ls) >= 2 and abs(hs[-1].price - hs[-2].price) <= tol and abs(ls[-1].price - ls[-2].price) <= tol:
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
                if mid and h2.bar > brk and h2.price < h1.price - tol and C[i] < mid[-1].price:
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
                if mid and l2.bar > brk and l2.price > l1.price + tol and C[i] > mid[-1].price:
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
                if h1 and l1 and h2.bar > brk and l2.bar > brk and abs(h2.price - h1.price) <= tol and abs(l2.price - l1.price) <= tol:
                    trend, band, why = "RANGE", (min(l1.price, l2.price), max(h1.price, h2.price)), "दोन H आणि दोन L जवळपास समान"
            elif trend == "RANGE" and band and (C[i] > band[1] or C[i] < band[0]):
                trend, why, brk, band = "NEUTRAL", "close range पट्ट्याबाहेर", i, None
        # wave / correction पाय / maturity
        wave = corr_label = None
        mature, targets = False, ()
        if dirn != 0 and phase:
            wave = f"L{2 * k_imp - 1}" if phase == "impulse" else f"L{2 * k_imp}"   # Q34: mechanical leg index (debug); Elliott लेबल फक्त advisory
            if phase in ("correction", "origin_broken"):
                prev_px, prev_k, n_after = imp_end.price, imp_end.kind, 0   # फक्त same-degree, H / L आलटून पालटून पाय
                lref = cfrac * ref_corr if rule == "ratio" else max(int_pull(dirn, leg_start, imp_end.bar, i), prev_int)
                for p in seq:
                    if p.bar > imp_end.bar and p.confirm_bar <= i and p.kind != prev_k and (
                            abs(p.price - prev_px) >= lref if rule == "ratio" else (lref > 0 and abs(p.price - prev_px) > lref)):
                        prev_px, prev_k, n_after = p.price, p.kind, n_after + 1
                corr_label = "abcde"[min(n_after, 4)]                      # 1 swing ⇒ a पूर्ण, b चालू
            if k_imp >= 3 and phase == "impulse":
                tg = [origin.price + dirn * w1_len] if w1_len else []      # (5) = (4) टोक ± (1) ची लांबी
                pre = pre_swing(dirn, w1_start)
                if pre is not None:
                    tg.append(pre)                                         # (1) ज्या leg च्या शेवटी सुरू झाली त्या leg चं उलट टोक ((A) low)
                near = msig * (sig[i] if np.isfinite(sig[i]) else 0.0)
                ext = L[i] if dirn < 0 else H[i]
                mature = any((ext - x) * dirn >= -near for x in tg)
                targets = tuple(round(float(x), 2) for x in tg)
        shown = trend if i + 1 > int(s["daily_min_sessions"]) else "UNKNOWN"
        tr = shown in ("UP", "DOWN")
        out.append(DState(i, pd.Timestamp(d["timestamp"].iloc[i]), kat[i], shown,
                          origin if trend in ("UP", "DOWN") else None, band if trend == "RANGE" else None,
                          why if shown != "UNKNOWN" else "Daily data अपुरा", list(seq),
                          phase if tr else None, wave if tr else None, corr_label if tr else None, imp_end if tr else None,
                          bool(mature and tr), targets if tr else ()))
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
        txt = "impulse"
    elif st.phase == "correction":
        txt = f"correction चालू (पाय {st.corr_label})"
    else:
        txt = f"origin close ने तुटला — उलट impulse ची वाट (correction पाय {st.corr_label or '—'}; कमाल B)"
    if st.protected is not None:
        txt += f" · protected origin {st.protected.price:,.0f}"
    if st.mature:
        txt += " · ⚠ impulse mature (target " + " / ".join(f"{x:,.0f}" for x in st.targets) + ")"
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
