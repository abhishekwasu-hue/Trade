"""legs2/measure.py — थर 2 §1–§2: प्रत्येक degree चे legs, भूमिका (R), स्वभाव (C candles + V volume), आतली रचना (फक्त नोंद), label.

Leg = एका degree चे लागोपाठचे दोन confirmed pivots P(j−1) → P(j). Leg चे bars = (P(j−1) चा bar, P(j) चा bar]. Confirmed leg चं मोजमाप
P(j) च्या `known_at` ला एकदाच: फक्त त्या क्षणापर्यंतचा data (leg चे bars + मागचे legs), पुढच्या legs शी तुलना कधीच नाही. वेगवेगळ्या
segments (holdout मधून तुटलेली सलगता) मधले दोन pivots ⇒ leg नाही; baseline segment ओलांडत नाही.
"""
import numpy as np
import pandas as pd

from pivots import engine as PE

from . import settings as LS
from . import volume as LV

IMP, NEU, COR = "आवेगी", "तटस्थ", "सुधारात्मक"
ROLE_DOM, ROLE_RET, ROLE_EQ, ROLE_UNK = "प्रबळ", "परतावा", "बरोबरी", "अज्ञात"
METRICS = ("er", "overlap", "body", "dirc")

NATURE = {(IMP, IMP): (IMP, False), (IMP, NEU): (IMP, False), (IMP, COR): (NEU, False),
          (NEU, IMP): (IMP, True), (NEU, NEU): (NEU, False), (NEU, COR): (COR, True),
          (COR, IMP): (NEU, False), (COR, NEU): (COR, False), (COR, COR): (COR, False)}
LABEL = {(ROLE_DOM, IMP): "आवेग", (ROLE_DOM, NEU): "आवेग (कमकुवत)", (ROLE_DOM, COR): "विरोध-1",
         (ROLE_RET, IMP): "विरोध-2", (ROLE_RET, NEU): "सुधार (कमकुवत)", (ROLE_RET, COR): "सुधार",
         (ROLE_EQ, IMP): "बरोबरी-आवेगी", (ROLE_EQ, NEU): "बरोबरी", (ROLE_EQ, COR): "बरोबरी-सुधारात्मक",
         (ROLE_UNK, IMP): "अज्ञात", (ROLE_UNK, NEU): "अज्ञात", (ROLE_UNK, COR): "अज्ञात"}
IMPULSE_LABELS = ("आवेग", "आवेग (कमकुवत)")
CONFLICT_LABELS = ("विरोध-1", "विरोध-2")


def nature(c_cls, v_cls):
    """C × V तक्ता ⇒ (स्वभाव, कमकुवत?)."""
    return NATURE[(c_cls, v_cls)]


def label(role, nat, weak=False):
    """भूमिका × स्वभाव. "कमकुवत" स्वभाव तक्त्यात तटस्थ म्हणून धरायचा (label वर दाखवायचा)."""
    return LABEL[(role, NEU if weak else nat)]


def classify(x, hi, lo):
    if x is None or not np.isfinite(x):
        return NEU
    return IMP if x >= hi else (COR if x <= lo else NEU)


# ---------------------------------------------------------------------------------------------------------------- candle मापं
def frame_arrays(m15):
    ts = pd.to_datetime(m15["timestamp"])
    day = ts.dt.normalize().to_numpy()
    first = np.r_[True, day[1:] != day[:-1]]                    # session चा पहिला bar (overnight gap इथे)
    return {"o": m15["open"].to_numpy(float), "h": m15["high"].to_numpy(float), "l": m15["low"].to_numpy(float),
            "c": m15["close"].to_numpy(float), "first": first}


def candle_metrics(A, i0, i1, dirn):
    """Leg bars (i0, i1] वर ER, overlap, body, दिशेच्या candles; overnight gap वगळून. रिटर्न dict + gaps (bar ⇒ gap)."""
    o, h, l, c, first = A["o"], A["h"], A["l"], A["c"], A["first"]
    idx = np.arange(i0 + 1, i1 + 1)
    step = c[idx] - c[idx - 1]
    gap = np.where(first[idx], o[idx] - c[idx - 1], 0.0)          # 09:15 open − आदला close
    adj = step - gap                                               # overnight पद वजा (दोन्ही net आणि path मधून)
    path = float(np.abs(adj).sum())
    er = abs(float(adj.sum())) / path if path > 0 else 0.0
    er = min(max(er, 0.0), 1.0)
    ovs = []
    for a, b in zip(idx[:-1], idx[1:]):
        if first[b]:                                               # session ओलांडणारी जोडी नाही
            continue
        rng = h[b] - l[b]
        if rng <= 0:
            continue
        ovs.append(max(0.0, min(h[a], h[b]) - max(l[a], l[b])) / rng)
    rng = h[idx] - l[idx]
    ok = rng > 0                                                   # high = low candle वगळायची
    body = float(np.mean(np.abs(c[idx] - o[idx])[ok] / rng[ok])) if ok.any() else None
    dirc = float(np.mean((c[idx] - o[idx]) * dirn > 0)) if len(idx) else None
    return {"er": er, "overlap": float(np.mean(ovs)) if ovs else None, "body": body, "dirc": dirc}, \
        {int(b): float(g) for b, g in zip(idx, gap) if g != 0.0}


def pct_rank(x, base):
    """बरोबरीत सरासरी rank: (कमी + ½ बरोबर) ÷ N."""
    b = np.asarray(base, float)
    return float(((b < x).sum() + 0.5 * (b == x).sum()) / len(b))


# ---------------------------------------------------------------------------------------------------------------- आतली रचना (नोंद)
def structure(sub, dirn):
    """एक degree खालचे pivots (टोक ते टोक). 5 sub-legs ⇒ Elliott चे पक्के नियम: '5✓' / '5 overlap' (फक्त wave 4 ने 1 चा प्रदेश) / '5'."""
    n = len(sub) - 1
    if n <= 0:
        return {"n": 0, "note": None}
    if n != 5:
        return {"n": n, "note": str(n)}
    p = [x.price * dirn for x in sub]                              # वरच्या दिशेत बदल (खालच्या leg साठी आरसा)
    w = [p[i + 1] - p[i] for i in range(5)]
    rules = p[2] > p[0] and p[3] > p[1] and abs(w[2]) > min(abs(w[0]), abs(w[4]))
    if rules and p[4] > p[1]:
        return {"n": 5, "note": "5✓"}
    if rules:
        return {"n": 5, "note": "5 overlap"}
    return {"n": 5, "note": "5"}


# ---------------------------------------------------------------------------------------------------------------- legs
def _seg(res, p):
    return res["segments"].get(pd.Timestamp(p.ts).normalize())


def build(res, fut5=None, s=None):
    """सगळ्या degrees चे confirmed legs (known_at क्रमाने). रिटर्न {"legs": {d: [leg]}, "rv", "bad", "A", "settings"}."""
    s = LS.load(s)
    m15 = res["m15"]
    A = frame_arrays(m15)
    rv, bad = LV.rvol(m15, fut5, s)
    out = {}
    for d in s["degrees"]:
        ps = res["pivots"][d]
        legs = []
        for j in range(1, len(ps)):
            a, b = ps[j - 1], ps[j]
            if _seg(res, a) != _seg(res, b):
                continue
            prev = ps[j - 2] if j >= 2 and _seg(res, ps[j - 2]) == _seg(res, a) else None
            legs.append(_leg(res, A, d, a, b, prev, rv, bad, s))
        _baseline(legs, s)
        for i, L in enumerate(legs):
            _volume(L, legs[i - 1] if i and legs[i - 1]["b"] is L["a"] else None, s)
            _label(L, s)
        out[d] = legs
    return {"legs": out, "rv": rv, "bad": bad, "A": A, "settings": s, "res": res}


def _leg(res, A, d, a, b, prev, rv, bad, s):
    dirn = 1 if b.price > a.price else -1
    nb = b.bar - a.bar
    L = {"degree": d, "a": a, "b": b, "prev": prev, "dir": dirn, "bars": nb, "known_at": b.known_at, "seg": _seg(res, b),
         "warmup": bool(a.warmup or b.warmup), "size": abs(b.price - a.price), "size_sigma": abs(b.price - a.price) / b.sigma if b.sigma else None}
    # भूमिका
    if prev is None:
        L["role"], L["R"] = ROLE_UNK, None
    else:
        R = abs(b.price - a.price) / abs(a.price - prev.price) if a.price != prev.price else float("inf")
        L["R"] = R
        L["role"] = ROLE_EQ if b.eq else (ROLE_DOM if R > 1 else ROLE_RET)
    # स्वभाव — candles
    raw, L["gaps"] = candle_metrics(A, a.bar, b.bar, dirn)                 # gap ची नोंद लहान legs ना सुद्धा
    L["short"] = nb <= int(s["short_leg_bars"])
    L["raw"] = None if L["short"] else raw
    _gap_note(L, b.sigma, s)
    # आतली रचना (D0 ला नाही)
    if d >= 1:
        sub = [p for p in res["pivots"][d - 1] if a.bar <= p.bar <= b.bar and _seg(res, p) == L["seg"]]
        st = structure(sub, dirn)
        st["gap"] = any(y.bar - x.bar == 1 and A["first"][y.bar] and abs(A["o"][y.bar] - A["c"][x.bar]) >= 0.5 * abs(y.price - x.price)
                        for x, y in zip(sub, sub[1:]))
        L["structure"] = st
    else:
        L["structure"] = None
    L["rv_bars"] = (rv[a.bar + 1:b.bar + 1], bad[a.bar + 1:b.bar + 1])
    return L


def _gap_note(L, sigma, s):
    big = [g for g in L["gaps"].values() if sigma and abs(g) >= float(s["gap_sigma"]) * sigma]
    L["gap"] = bool(big)
    L["gap_sigma"] = round(sum(abs(g) for g in big) / sigma, 2) if big else 0.0


def _baseline(legs, s):
    """त्याच degree चे मागचे `baseline_legs` confirmed legs (known_at ≤ या leg चा, warm-up नाही, त्याच segment मध्ये) ⇒ percentile ⇒ C."""
    n_keep, n_min = int(s["baseline_legs"]), int(s["baseline_min"])
    for i, L in enumerate(legs):
        if L["raw"] is None:
            L.update(C=None, C_na=False, c_warmup=False, pct={}, n_base=0, c_cls=NEU)
            continue
        base = [x for x in legs[:i] if x["raw"] is not None and not x["warmup"] and x["seg"] == L["seg"]
                and x["known_at"] <= L["known_at"]][-n_keep:]
        L["n_base"] = len(base)
        if len(base) < n_min:
            L.update(C=None, C_na=True, c_warmup=False, pct={}, c_cls=NEU)
            continue
        pct = {}
        for m in METRICS:
            x = L["raw"][m]
            vals = [b["raw"][m] for b in base if b["raw"][m] is not None]
            if x is None or not vals:
                continue
            p = pct_rank(x, vals)
            pct[m] = 1.0 - p if m == "overlap" else p
        C = float(np.mean(list(pct.values()))) if pct else None
        L.update(C=C, C_na=C is None, c_warmup=len(base) < n_keep, pct=pct, c_cls=classify(C, s["c_hi"], s["c_lo"]))


def _volume(L, prev_leg, s):
    """V = leg चा सरासरी RVOL ÷ मागच्या उलट leg चा. Volume नाही / अर्ध्यापेक्षा जास्त bars unreliable किंवा volume-विना ⇒ तटस्थ."""
    L["V"], L["v_cls"], L["v_why"] = None, NEU, None
    if prev_leg is None:
        L["v_why"] = "मागचा leg नाही"
        return
    means = []
    for rvb, bdb in (L["rv_bars"], prev_leg["rv_bars"]):
        good = np.isfinite(rvb) & ~bdb
        if not len(rvb) or good.sum() * 2 < len(rvb):
            L["v_why"] = "volume नाही / rollover"
            return
        means.append(float(rvb[good].mean()))
    if means[1] <= 0:
        return
    L["V"] = means[0] / means[1]
    L["v_cls"] = classify(L["V"], s["v_hi"], s["v_lo"])


def _label(L, s):
    nat, weak = nature(L["c_cls"], L["v_cls"])
    if L.get("short"):
        nat, weak = NEU, False
    L["nature"], L["weak"] = nat, weak
    L["label"] = label(L["role"], nat, weak)
    L["why"] = reasons(L)


def reasons(L):
    parts = []
    if L.get("R") is not None:
        parts.append(f"R {L['R']:.2f}" if np.isfinite(L["R"]) else "R ∞")
    parts.append(f"C {L['C']:.2f}" if L.get("C") is not None else ("C NA" if L.get("C_na") else "C —"))
    if L.get("V") is not None:
        parts.append(f"V {L['V']:.2f}")
    st = L.get("structure")
    if st and st.get("note"):
        parts.append(f"रचना {st['note']}")
    if L.get("gap"):
        parts.append(f"gap {L['gap_sigma']:.1f}σ")
    if L.get("weak"):
        parts.append(f"स्वभाव {L['nature']} (कमकुवत)")
    if L.get("short"):
        parts.append("लहान leg")
    return " · ".join(parts)


# ---------------------------------------------------------------------------------------------------------------- asof पर्यंत
def known(lg, d, asof):
    return [L for L in lg["legs"][d] if L["known_at"] <= pd.Timestamp(asof)]


def current(lg, d, asof):
    """चालू leg: शेवटचा confirmed pivot → tentative टोक (प्रत्येक बंद candle ला पुन्हा). Baseline = asof पर्यंतचे legs.
    Tentative टोक दुसऱ्या segment मध्ये (holdout ओलांडून) ⇒ चालू leg नाही (segment ची सलगता तुटते)."""
    res, s, A = lg["res"], lg["settings"], lg["A"]
    ps = PE.known(res, d, asof)
    tn = PE.tentative(res, d, asof)
    if not ps or tn is None:
        return None
    a = ps[-1]
    m15 = res["m15"]
    tb = int(np.flatnonzero(pd.to_datetime(m15["timestamp"]).to_numpy() == np.datetime64(pd.Timestamp(tn["ts"])))[0])
    seg_now = res["segments"].get(pd.Timestamp(m15["timestamp"].iloc[int((pd.to_datetime(m15["bar_end"]) <= pd.Timestamp(asof)).sum()) - 1])
                                  .normalize())
    if tb <= a.bar or res["segments"].get(pd.Timestamp(tn["ts"]).normalize()) != _seg(res, a) or seg_now != _seg(res, a):
        return None
    dirn = 1 if tn["price"] > a.price else -1
    prev = ps[-2] if len(ps) >= 2 and _seg(res, ps[-2]) == _seg(res, a) else None
    L = {"degree": d, "a": a, "b": None, "end_bar": tb, "end_price": tn["price"], "dir": dirn, "bars": tb - a.bar, "current": True,
         "known_at": pd.Timestamp(asof), "seg": _seg(res, a), "warmup": a.warmup, "size": abs(tn["price"] - a.price),
         "structure": None}
    if prev is None:
        L["role"], L["R"] = ROLE_UNK, None
    else:
        L["R"] = abs(tn["price"] - a.price) / abs(a.price - prev.price) if a.price != prev.price else float("inf")
        L["role"] = ROLE_DOM if L["R"] > 1 else ROLE_RET
    raw, L["gaps"] = candle_metrics(A, a.bar, tb, dirn)
    _gap_note(L, a.sigma, s)
    L["short"] = L["bars"] <= int(s["short_leg_bars"])
    L["raw"] = None if L["short"] else raw
    if L["short"]:
        L.update(C=None, C_na=False, c_warmup=False, c_cls=NEU)
    else:
        base = [x for x in known(lg, d, asof) if x["raw"] is not None and not x["warmup"] and x["seg"] == L["seg"]][-int(s["baseline_legs"]):]
        if len(base) < int(s["baseline_min"]):
            L.update(C=None, C_na=True, c_warmup=False, c_cls=NEU)
        else:
            pct = {}
            for m in METRICS:
                vals = [b["raw"][m] for b in base if b["raw"][m] is not None]
                if L["raw"][m] is not None and vals:
                    p = pct_rank(L["raw"][m], vals)
                    pct[m] = 1.0 - p if m == "overlap" else p
            C = float(np.mean(list(pct.values()))) if pct else None
            L.update(C=C, C_na=C is None, c_warmup=len(base) < int(s["baseline_legs"]), pct=pct, c_cls=classify(C, s["c_hi"], s["c_lo"]))
    L["rv_bars"] = (lg["rv"][a.bar + 1:tb + 1], lg["bad"][a.bar + 1:tb + 1])
    prev_leg = next((x for x in reversed(known(lg, d, asof)) if x["b"] is a), None)
    _volume(L, prev_leg, s)
    _label(L, s)
    return L


def leg_json(L):
    a, b = L["a"], L.get("b")
    return {"degree": L["degree"], "from": {"kind": a.kind, "price": round(a.price, 2), "ts": str(a.ts)},
            "to": ({"kind": b.kind, "price": round(b.price, 2), "ts": str(b.ts)} if b is not None else
                   {"price": round(L["end_price"], 2), "tentative": True}),
            "known_at": str(L["known_at"]), "dir": L["dir"], "bars": L["bars"], "role": L["role"],
            "R": None if L.get("R") is None else (round(L["R"], 3) if np.isfinite(L["R"]) else "inf"),
            "C": None if L.get("C") is None else round(L["C"], 3), "C_na": bool(L.get("C_na")), "c_warmup": bool(L.get("c_warmup")),
            "pct": {k: round(v, 3) for k, v in (L.get("pct") or {}).items()},
            "raw": None if L.get("raw") is None else {k: (None if v is None else round(v, 4)) for k, v in L["raw"].items()},
            "V": None if L.get("V") is None else round(L["V"], 3), "v_note": L.get("v_why"), "nature": L["nature"], "weak": L["weak"],
            "label": L["label"], "why": L["why"], "gap": L["gap"], "gap_sigma": L["gap_sigma"], "structure": L.get("structure"),
            "warmup": L["warmup"], "current": bool(L.get("current"))}
