"""swings2/engine.py — थर 1 engine (v2.1 §1).

D0: 15M spot bars वर DC, θ₀ = k₀ σ (pivots.dc.D0: बरोबरीत नंतरची candle, same-bar ⇒ 1m क्रम किंवा सावध नियम, एका candle मधून दोन
pivots नाहीत, फक्त θ बदलल्याने confirm नाही). 1m फक्त `1m_status = complete` असेल तर; प्रत्येक candle चा status **आणि 1m क्रम-निर्णय**
(`order`: दिशा ⇒ first_ext + after_extreme / first_rev / none) प्रवाहात (`stream`) साठवला जातो; replay त्या निर्णयावरच fold करतो (1m rows
पुन्हा वाचत नाही ⇒ नंतरचा backfill आधीचा pivot बदलत नाही).

D(n+1): extreme फक्त confirmed D(n) pivots मधून, पण θ_(n+1) ओलांडणं **raw bar high / low** वर (extreme च्या नंतरच्या bars, आणि तो
अजून खरंच टोक आहे तोपर्यंत). known_at = max(crossing candle चा close, त्या D(n) pivot चा known_at). ⇒ D(n+1) ⊆ D(n).

Gap (09:15): |open − आदला close| ≥ gap_bar_sigma σ ⇒ `gap_bar_2s`; leg (आधीचा pivot → हा pivot) मध्ये त्या leg च्या दिशेने ≥ θ चा
overnight gap ⇒ pivot ला `gap_leg_theta` (थर 2 ची मापं gap नेहमीच वगळतात; खूण माहितीसाठी).
D0 ने same-bar मुळे candle चा काही भाग वापरला नाही (1m ने त्याच candle चं टोक confirm, किंवा सावध नियम) ⇒ ती candle `split`;
D(n+1) त्या candle वर crossing मोजत नाही (नाहीतर D(n) ला न दिसलेल्या भावावर confirm होईल).
Holdout चा एकही row नाही (guard); holdout ओलांडल्यावर नवा segment (state reset, warm-up पुन्हा).
"""
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from pivots import dc as DC
from pivots import engine as PE
from pivots.dc import BAR, D0

from . import settings as SS

DEGREES = (0, 1, 2, 3, 4)
UNDECIDED, UP, DOWN = "UNDECIDED", "UP", "DOWN"


@dataclass(frozen=True)
class Pivot:
    degree: int
    kind: str
    price: float
    bar: int
    ts: pd.Timestamp
    confirm_bar: int
    known_at: pd.Timestamp
    sigma: float
    theta: float
    rule: str
    eq: bool = False
    warmup: bool = False
    session: int = -1
    gap_leg_theta: bool = False


def m1_status(rows, hi, lo):
    """complete (≥ 15 rows, high / low तंतोतंत जुळतात) / partial / absent."""
    if rows is None or not len(rows):
        return "absent"
    h, l = rows["high"].to_numpy(float), rows["low"].to_numpy(float)
    ok = len(rows) >= 15 and abs(h.max() - hi) <= 1e-9 and abs(l.min() - lo) <= 1e-9
    return "complete" if ok else "partial"


class Upper:
    """D(n+1): candidates = confirmed D(n) pivots; crossing = raw bars."""

    def __init__(self, degree):
        self.degree = degree
        self.reset()

    def reset(self):
        self.mode = UNDECIDED
        self.lower = []                 # आलेले D(n) pivots (क्रमाने)
        self.cand = {}                  # kind ⇒ [pivot, पुढचा तपासायचा bar, अजून टोक?]
        self.base = -1                  # शेवटच्या D(n+1) pivot चा bar
        self.last_cross = -1
        self.out = []

    def _best(self, kind):
        ps = [p for p in self.lower if p.kind == kind and p.bar > self.base]
        if not ps:
            return None
        return (max if kind == "H" else min)(ps, key=lambda p: (p.price, p.bar) if kind == "H" else (p.price, -p.bar))

    def _set(self, kind, p):
        cur = self.cand.get(kind)
        if p is None:
            self.cand.pop(kind, None)
            return
        if cur is None or cur[0] is not p:
            self.cand[kind] = [p, max(p.bar + 1, self.last_cross + 1), True, None]          # [pivot, पुढचा bar, अजून टोक?, rev]

    def add(self, p):
        self.lower.append(p)
        if self.mode in (UNDECIDED, UP) and p.kind == "H":
            c = self.cand.get("H")
            if c is None or p.price >= c[0].price:
                self._set("H", p)
        if self.mode in (UNDECIDED, DOWN) and p.kind == "L":
            c = self.cand.get("L")
            if c is None or p.price <= c[0].price:
                self._set("L", p)

    def _first_cross(self, kind, b, A, theta):
        """candidate चा पहिला crossing bar (≤ b) किंवा None. मध्ये candidate पलीकडे गेलेली candle ⇒ थांब (आता तो टोक नाही)."""
        c = self.cand.get(kind)
        if c is None or not c[2]:
            return None
        p, j0 = c[0], c[1]
        for j in range(max(j0, self.last_cross + 1), b + 1):
            th = theta[j]
            if kind == "H":
                if A["h"][j] > p.price:
                    c[2] = False
                    return None
                if A["split"][j]:
                    c[1] = j + 1
                    continue
                fresh = c[3] is None or A["l"][j] < c[3]                      # उलट हालचाल याच candle ने पुढे नेली (θ-only confirm नाही)
                if fresh and np.isfinite(th) and p.price - A["l"][j] >= th:
                    return j
                c[3] = A["l"][j] if c[3] is None else min(c[3], A["l"][j])
            else:
                if A["l"][j] < p.price:
                    c[2] = False
                    return None
                if A["split"][j]:
                    c[1] = j + 1
                    continue
                fresh = c[3] is None or A["h"][j] > c[3]
                if fresh and np.isfinite(th) and A["h"][j] - p.price >= th:
                    return j
                c[3] = A["h"][j] if c[3] is None else max(c[3], A["h"][j])
            c[1] = j + 1
        return None

    def step(self, b, A, theta, sigma, known_of):
        out = []
        while True:
            kinds = [k for k in ("H", "L") if (self.mode == UNDECIDED or (self.mode == UP and k == "H") or (self.mode == DOWN and k == "L"))]
            hits = [(j, self.cand[k][0].bar, k) for k in kinds if (j := self._first_cross(k, b, A, theta)) is not None]
            if not hits:
                return out
            j, _, k = min(hits)
            p = self.cand[k][0]
            q = Pivot(self.degree, k, p.price, p.bar, p.ts, max(j, p.confirm_bar), max(known_of(j), p.known_at), sigma[j], theta[j],
                      p.rule)
            self.out.append(q)
            out.append(q)
            self.last_cross = j
            self.base = p.bar
            self.mode = DOWN if k == "H" else UP
            opp = "L" if k == "H" else "H"
            self.cand = {}
            self._set(opp, self._best(opp))


def build(m15, df1m=None, s=None, m1_status_map=None):
    """सगळ्या bars वर engine. m1_status_map (ts ⇒ status) दिल्यास तोच वापर (replay = live). (status complete असेल तर 1m rows
    पुन्हा वाचल्या जातात; नंतरचा backfill त्या candle चा high / low क्रम बदलेल अशी दुरुस्ती असेल तर ती नोंद वेगळी हवी — register.)"""
    s = SS.load(s)
    PE.guard(m15)
    if not len(m15):
        raise ValueError("15M bars नाहीत")
    m15 = m15.reset_index(drop=True)
    sig = PE.sigma_by_session(m15, int(s["sigma_sessions"]))
    day, days, seg = PE.sessions_of(m15)
    rows = PE._rows_1m(PE.guard(df1m) if df1m is not None else None)
    ts = pd.to_datetime(m15["timestamp"])
    end = ts + BAR
    A = {"o": m15["open"].to_numpy(float), "h": m15["high"].to_numpy(float), "l": m15["low"].to_numpy(float),
         "c": m15["close"].to_numpy(float)}
    n = len(m15)
    A["split"] = np.zeros(n, dtype=bool)
    first = np.r_[True, day.to_numpy()[1:] != day.to_numpy()[:-1]]
    sigma = np.array([sig.get(pd.Timestamp(d), np.nan) for d in day], float)
    k = {d: float(s["k"][d]) for d in DEGREES}
    theta = {d: k[d] * sigma for d in DEGREES}
    gap = np.where(first, A["o"] - np.r_[np.nan, A["c"][:-1]], 0.0)
    same_seg = np.r_[False, [seg[pd.Timestamp(day.iloc[i])] == seg[pd.Timestamp(day.iloc[i - 1])] for i in range(1, n)]]
    gap = np.where(first & same_seg, gap, 0.0)
    gap_bars = [int(i) for i in np.flatnonzero(np.abs(np.nan_to_num(gap)) >= float(s["gap_bar_sigma"]) * np.nan_to_num(sigma, nan=np.inf))]
    wu = {d: int(s["warmup_sessions"][d]) for d in DEGREES}
    d0, ups = D0(0), {d: Upper(d) for d in DEGREES[1:]}
    piv = {d: [] for d in DEGREES}
    sess_idx = {d: i for i, d in enumerate(days)}
    started, cur_seg = {}, None
    last_same = {d: {"H": None, "L": None} for d in DEGREES}
    stream = []
    known_of = (lambda j: pd.Timestamp(end.iloc[j]))                                 # noqa: E731
    ts_of = (lambda i: pd.Timestamp(ts.iloc[i]))                                     # noqa: E731

    def gap_leg(prev, p, d):
        """leg prev → p मध्ये, leg च्या दिशेने, त्या bar च्या θ_d इतका / जास्त overnight gap."""
        if prev is None:
            return False
        dirn = 1 if p.price > prev.price else -1
        js = [j for j in range(prev.bar + 1, p.bar + 1) if first[j]]
        return any(np.isfinite(theta[d][j]) and gap[j] * dirn >= theta[d][j] for j in js)

    def finish(p, d):
        kd = pd.Timestamp(p.known_at - BAR).normalize()
        si = sess_idx[kd] - started[cur_seg]
        q = last_same[d][p.kind]
        sk = sig.get(kd, p.sigma)                                                    # σ नंतरच्या pivot च्या known_at चा
        eq = q is not None and abs(p.price - q.price) <= float(s["eq_tol_sigma"]) * sk
        prev = piv[d][-1] if piv[d] and seg[pd.Timestamp(piv[d][-1].ts).normalize()] == cur_seg else None
        base = asdict(p) if isinstance(p, Pivot) else {"degree": d, "kind": p.kind, "price": p.price, "bar": p.bar, "ts": p.ts,
                                                       "confirm_bar": p.confirm_bar, "known_at": p.known_at, "sigma": p.sigma,
                                                       "theta": p.theta, "rule": p.rule}
        p = Pivot(**{**base, "warmup": si < wu[d], "eq": bool(eq), "session": si, "gap_leg_theta": gap_leg(prev, p, d)})
        last_same[d][p.kind] = p
        piv[d].append(p)
        return p

    for b in range(n):
        dd = pd.Timestamp(day.iloc[b])
        if seg[dd] != cur_seg:
            cur_seg = seg[dd]
            d0.reset()
            for u in ups.values():
                u.reset()
            last_same = {d: {"H": None, "L": None} for d in DEGREES}
        r1 = rows.get(ts_of(b))
        if r1 is not None and "received_at" in r1.columns:
            r1 = r1[pd.to_datetime(r1["received_at"]) <= known_of(b)]
        entry = (m1_status_map or {}).get(str(ts_of(b)))
        saved = entry.get("order") if isinstance(entry, dict) else None
        st = (entry.get("m1_status") if isinstance(entry, dict) else entry) or m1_status(r1, A["h"][b], A["l"][b])
        rec = {}
        if saved is not None:                                                        # replay: साठवलेला 1m निर्णयच (rows नाहीत)
            d0.order_fn = (lambda rows, hi, lo, dr, sv=saved: (lambda x: None if x is None else tuple(x))(sv.get(str(dr))))
        else:
            d0.order_fn = (lambda rows, hi, lo, dr, rc=rec: rc.setdefault(str(dr), DC._order_1m(rows, hi, lo, dr)))
        stream.append({"ts": str(ts_of(b)), "m1_status": st, "order": rec if saved is None else saved})
        if not np.isfinite(sigma[b]):
            continue
        started.setdefault(cur_seg, sess_idx[dd])
        p = d0.step(b, A["h"][b], A["l"][b], theta[0][b], sigma[b], known_of(b), None, ts_of, r1 if st == "complete" else None)
        A["split"][b] = bool((p is not None and p.bar == b) or d0.cons == b          # same-bar: candle चा भाग D0 ला दिसला नाही
                             or (p is not None and p.rule == "1m" and p.bar != b))       # first_rev: आधीचं टोक confirm, या candle चं टोक नाही
        new = [finish(p, 0)] if p is not None else []
        for d in DEGREES[1:]:
            nxt = []
            for q in new:
                ups[d].add(q)
            for q in ups[d].step(b, A, theta[d], sigma, known_of):
                nxt.append(finish(q, d))
            new = nxt
    sig1h = sigma_1h(m15, days, seg, int(s["sigma_sessions"]))
    return {"pivots": piv, "sigma": sig, "sigma_1h": sig1h, "sessions": days, "segments": seg, "started": started, "m15": m15,
            "settings": s, "stream": stream, "gap_bar_2s": gap_bars, "gap": gap, "first": first, "A": A, "theta": theta}


def sigma_1h(m15, days, seg, n):
    """σ_1H(session) = आधीच्या n पूर्ण sessions च्या बंद 1H candles च्या range चा median — पहिली (09:15) आणि शेवटची लहान
    (15:15–15:30) candle वगळून (MASTER §3)."""
    from pivots import charts as PC
    h1 = PC.agg_1h(m15)
    t = pd.to_datetime(h1["timestamp"])
    rng = (h1["high"] - h1["low"]).to_numpy(float)
    hm = t.dt.strftime("%H:%M")
    ok = ~hm.isin(["09:15", "15:15"]).to_numpy()
    d = t.dt.normalize().to_numpy()
    full = PE.complete_sessions(m15)
    out = {}
    for i, dd in enumerate(days):
        prev = [x for x in days[:i] if seg[x] == seg[dd] and full[x]][-n:]
        if len(prev) < n:
            out[dd] = float("nan")
            continue
        m = np.isin(d, np.array(prev, dtype="datetime64[ns]")) & ok
        out[dd] = float(np.median(rng[m])) if m.any() else float("nan")
    return out


# ---------------------------------------------------------------------------------------------------------------- वाचन
def known(res, d, asof):
    return [p for p in res["pivots"][d] if p.known_at <= pd.Timestamp(asof)]


def tentative(res, d, asof):
    return PE.tentative(res, d, asof)


def labels(ps):
    return PE.labels(ps)


def pivot_json(p, label=None):
    j = PE.pivot_json(p, label)
    j["gap_leg_theta"] = p.gap_leg_theta
    return j
