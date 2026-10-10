"""legs2/measure2.py — थर 2 v2.1 §1–§4: थर 1 v2 (swings2) च्या pivots वर legs, features, भूमिका R, स्वभाव C / V, label.

Confirmed leg चं माप P_j च्या `known_at` ला एकदाच (गोठलेलं); चालू leg प्रत्येक बंद candle ला (`current`).
- C baseline: त्याच degree चे मागचे ≤ 40 confirmed legs (**स्वतः वगळून**, warm-up / 1–2-bar / gap_leg_theta legs वगळून, `known_at` ≤,
  त्याच segment; holdout नाही), बरोबरीत सरासरी rank. ≥ 40 सामान्य; 10–39 ⇒ `c_warmup`; < 10 ⇒ NA. 1–2 bars ⇒ तटस्थ.
- V = leg RVOL ÷ मागच्या उलट leg RVOL; data नाही / > ½ bars unreliable / कोणत्याही leg ला < 3 reliable bars ⇒ तटस्थ.
- स्वभाव (C × V) D0, D1, D2 ला; label फक्त D1, D2; D3 legs ला फक्त R (थर 2 व्याप्ती).
- gap_in_leg = leg मध्ये ≥ 0.5 σ चा overnight gap (थर 1 चं gap_leg_theta वेगळं); मापं नेहमीच gap वगळून.
"""
import numpy as np
import pandas as pd

from swings2 import candles as SC
from swings2 import engine as SE

from . import features as LF
from . import measure as LM
from . import settings2 as LS
from . import volume as LV

IMP, NEU, COR = LM.IMP, LM.NEU, LM.COR
METRICS = ("er", "overlap", "body", "dirc")


def frame_arrays(res):
    m15 = res["m15"]
    return {"o": m15["open"].to_numpy(float), "h": m15["high"].to_numpy(float), "l": m15["low"].to_numpy(float),
            "c": m15["close"].to_numpy(float), "first": np.asarray(res["first"], bool)}


def _seg(res, p):
    return res["segments"].get(pd.Timestamp(p.ts).normalize())


def build(res, fut5=None, s=None, rr=None):
    """रिटर्न {"legs": {d: [leg]}, "rv", "bad", "vol", "rr", "A", "settings", "res"}."""
    s = LS.load(s, res["settings"])
    m15 = res["m15"]
    A = frame_arrays(res)
    rr = SC.rng_ratio(res) if rr is None else rr
    rv, bad = LV.rvol(m15, fut5, s)
    vol = LV.bar_volume(m15, fut5)
    lg = {"rv": rv, "bad": bad, "vol": vol, "rr": rr, "A": A, "settings": s, "res": res, "legs": {}}
    for d in s["degrees"]:
        ps = res["pivots"][d]
        legs = []
        for j in range(1, len(ps)):
            a, b = ps[j - 1], ps[j]
            if _seg(res, a) != _seg(res, b):
                continue
            prev = ps[j - 2] if j >= 2 and _seg(res, ps[j - 2]) == _seg(res, a) else None
            legs.append(make_leg(lg, d, a, b.bar, b.price, prev, b=b))
        for i, L in enumerate(legs):
            base = [x for x in legs[:i] if x["known_at"] <= L["known_at"]]
            finish(lg, L, base, legs[i - 1] if i and legs[i - 1]["b"] is L["a"] else None)
        lg["legs"][d] = legs
    return lg


def make_leg(lg, d, a, end_bar, end_price, prev, b=None):
    res, s, A = lg["res"], lg["settings"], lg["A"]
    dirn = 1 if end_price > a.price else -1
    sigma = (b.sigma if b is not None else a.sigma) or np.nan
    size = abs(end_price - a.price)
    L = {"degree": d, "a": a, "b": b, "end_bar": end_bar, "end_price": end_price, "prev": prev, "dir": dirn,
         "bars": end_bar - a.bar, "known_at": b.known_at if b is not None else None, "seg": _seg(res, a),
         "warmup": bool(a.warmup or (b is not None and b.warmup)), "size": size,
         "size_sigma": size / sigma if np.isfinite(sigma) and sigma else None,
         "gap_leg_theta": bool(getattr(b, "gap_leg_theta", False)) if b is not None else False, "current": b is None}
    if prev is None:
        L["role"], L["R"] = LM.ROLE_UNK, None
    else:
        R = size / abs(a.price - prev.price) if a.price != prev.price else float("inf")
        L["R"] = R
        L["role"] = LM.ROLE_EQ if (b is not None and b.eq) else (LM.ROLE_DOM if R > 1 else LM.ROLE_RET)
    L["gaps"] = LF.gaps(A, a.bar, end_bar)
    big = [g for g in L["gaps"].values() if np.isfinite(sigma) and abs(g) >= float(s["gap_in_leg_sigma"]) * sigma]
    L["gap_in_leg"] = L["gap"] = bool(big)                                     # "gap" = v1 chart tag चं नाव
    L["gap_sigma"] = round(sum(abs(g) for g in big) / sigma, 2) if big else 0.0
    L["short"] = L["bars"] <= int(s["short_leg_bars"])
    L["f"] = LF.leg_features(A, lg["rr"], lg["vol"], lg["rv"], lg["bad"], a.bar, end_bar, dirn, size, sigma, s)
    L["raw"] = None if L["short"] else {m: L["f"][m] for m in METRICS}
    L["rv_bars"] = (lg["rv"][a.bar + 1:end_bar + 1], lg["bad"][a.bar + 1:end_bar + 1])
    if d >= 1:
        sub = [p for p in res["pivots"][d - 1] if a.bar <= p.bar <= end_bar and _seg(res, p) == L["seg"]
               and (L["known_at"] is None or p.known_at <= L["known_at"])]
        L["structure"] = LM.structure(sub, dirn)
    else:
        L["structure"] = None
    return L


def eligible(x):
    """C baseline मध्ये येणारा leg: warm-up नाही, 1–2-bar नाही, gap_leg_theta नाही."""
    return x["raw"] is not None and not x["warmup"] and not x["gap_leg_theta"]


def c_score(L, base, s):
    """C = ER, (1 − overlap), body, दिशा-candles यांच्या percentile ची सरासरी; base = आधीचे legs (स्वतः नाही)."""
    if L["raw"] is None:
        return {"C": None, "C_na": False, "c_warmup": False, "pct": {}, "n_base": 0, "c_cls": NEU}
    base = [x for x in base if x is not L and eligible(x) and x["seg"] == L["seg"]][-int(s["baseline_legs"]):]
    n = len(base)
    if n < int(s["baseline_min"]):
        return {"C": None, "C_na": True, "c_warmup": False, "pct": {}, "n_base": n, "c_cls": NEU}
    pct = {}
    for m in METRICS:
        x = L["raw"][m]
        vals = [b["raw"][m] for b in base if b["raw"][m] is not None]
        if x is None or not vals:
            continue
        p = LM.pct_rank(x, vals)
        pct[m] = 1.0 - p if m == "overlap" else p
    C = float(np.mean(list(pct.values()))) if pct else None
    return {"C": C, "C_na": C is None, "c_warmup": n < int(s["baseline_legs"]), "pct": pct, "n_base": n,
            "c_cls": LM.classify(C, s["c_hi"], s["c_lo"])}


def v_score(L, prev_leg, s):
    out = {"V": None, "v_cls": NEU, "v_why": None}
    if prev_leg is None:
        out["v_why"] = "मागचा leg नाही"
        return out
    means = []
    for rvb, bdb in (L["rv_bars"], prev_leg["rv_bars"]):
        good = np.isfinite(rvb) & ~bdb
        if not len(rvb) or good.sum() * 2 < len(rvb):
            out["v_why"] = "volume नाही / unreliable"
            return out
        if good.sum() < int(s["v_min_reliable"]):
            out["v_why"] = f"< {int(s['v_min_reliable'])} reliable bars"
            return out
        means.append(float(rvb[good].mean()))
    if means[1] <= 0:
        return out
    out["V"] = means[0] / means[1]
    out["v_cls"] = LM.classify(out["V"], s["v_hi"], s["v_lo"])
    return out


def finish(lg, L, base, prev_leg):
    s = lg["settings"]
    d = L["degree"]
    L.update(c_score(L, base, s))
    L.update(v_score(L, prev_leg, s))
    if d in s["nature_degrees"]:
        nat, weak = LM.nature(L["c_cls"], L["v_cls"])
        if L["short"]:
            nat, weak = NEU, False
    else:
        nat, weak = None, False
    L["nature"], L["weak"] = nat, weak
    L["label"] = LM.label(L["role"], nat, weak) if (d in s["label_degrees"] and nat is not None) else None
    L["why"] = reasons(L)
    return L


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
    if L.get("gap_in_leg"):
        parts.append(f"gap {L['gap_sigma']:.1f}σ")
    if L.get("gap_leg_theta"):
        parts.append("gap leg (θ)")
    if L.get("weak"):
        parts.append(f"स्वभाव {L['nature']} (कमकुवत)")
    if L.get("short"):
        parts.append("लहान leg")
    return " · ".join(parts)


# ---------------------------------------------------------------------------------------------------------------- asof पर्यंत
def known(lg, d, asof):
    return [L for L in lg["legs"][d] if L["known_at"] <= pd.Timestamp(asof)]


def bar_of(res, asof):
    return int((pd.to_datetime(res["m15"]["bar_end"]) <= pd.Timestamp(asof)).sum()) - 1


def current(lg, d, asof):
    """चालू leg: शेवटचा confirmed pivot → tentative टोक. दुसऱ्या segment मध्ये ⇒ None."""
    res = lg["res"]
    ps = SE.known(res, d, asof)
    tn = SE.tentative(res, d, asof)
    if not ps or tn is None:
        return None
    a = ps[-1]
    m15 = res["m15"]
    hit = np.flatnonzero(pd.to_datetime(m15["timestamp"]).to_numpy() == np.datetime64(pd.Timestamp(tn["ts"])))
    if not len(hit):
        return None
    tb = int(hit[0])
    t = bar_of(res, asof)
    seg_now = res["segments"].get(pd.Timestamp(m15["timestamp"].iloc[t]).normalize())
    if tb <= a.bar or res["segments"].get(pd.Timestamp(tn["ts"]).normalize()) != _seg(res, a) or seg_now != _seg(res, a):
        return None
    prev = ps[-2] if len(ps) >= 2 and _seg(res, ps[-2]) == _seg(res, a) else None
    L = make_leg(lg, d, a, tb, float(tn["price"]), prev)
    L["known_at"] = pd.Timestamp(asof)
    kn = known(lg, d, asof)
    prev_leg = next((x for x in reversed(kn) if x["b"] is a), None)
    finish(lg, L, kn, prev_leg)
    return L


def leg_json(L):
    a, b = L["a"], L.get("b")
    f = L.get("f") or {}
    rnd = (lambda v, k=3: None if v is None else round(float(v), k))                                       # noqa: E731
    return {"degree": L["degree"], "from": {"kind": a.kind, "price": round(a.price, 2), "ts": str(a.ts)},
            "to": ({"kind": b.kind, "price": round(b.price, 2), "ts": str(b.ts)} if b is not None else
                   {"price": round(L["end_price"], 2), "tentative": True}),
            "known_at": str(L["known_at"]), "dir": L["dir"], "bars": L["bars"], "role": L["role"],
            "R": None if L.get("R") is None else (round(L["R"], 3) if np.isfinite(L["R"]) else "inf"),
            "C": rnd(L.get("C")), "C_na": bool(L.get("C_na")), "c_warmup": bool(L.get("c_warmup")), "n_base": L.get("n_base"),
            "pct": {k: round(v, 3) for k, v in (L.get("pct") or {}).items()},
            "V": rnd(L.get("V")), "v_note": L.get("v_why"), "nature": L.get("nature"), "weak": bool(L.get("weak")),
            "label": L.get("label"), "why": L.get("why"), "gap_in_leg": L["gap_in_leg"], "gap_sigma": L["gap_sigma"],
            "gap_leg_theta": L["gap_leg_theta"], "structure": L.get("structure"), "warmup": L["warmup"], "current": bool(L.get("current")),
            "features": {k: (rnd(v, 4) if isinstance(v, float) else v) for k, v in f.items()}}
