"""pivots/engine.py — थर 1 engine: 15M spot bars (+ ऐच्छिक 1m) ⇒ σ (session-गोठलेला) ⇒ D0…D4 pivots (DC, nested) ⇒ trend / protected
swing / tentative टोक / EQ खूण / मोजमाप. फक्त data-policy ने परवानगी दिलेले rows; sealed holdout चा एकही row σ / DC / मोजमापात
जात नाही (आला तर HoldoutError). Holdout मधून जाणारी सलगता तुटते ⇒ नवा segment (state reset, warm-up पुन्हा).
"""
from dataclasses import replace

import numpy as np
import pandas as pd

from elliott import data_policy as DP

from . import settings as PS
from .dc import BAR, D0, Upper

DEGREES = (0, 1, 2, 3, 4)


def guard(df, col="timestamp"):
    """σ / DC / मोजमाप यांच्या input चा पहारा: holdout row किंवा display_only row ⇒ HoldoutError (शांतपणे वगळत नाही)."""
    if "display_only" in df.columns and df["display_only"].astype(bool).any():
        raise DP.HoldoutError("display_only rows (फक्त chart साठी) σ / DC / मोजमापात नाहीत")
    ts = pd.to_datetime(df[col])
    bad = ts[(ts >= DP.HOLDOUT_START) & (ts < DP.CONTAMINATED_START)]
    if len(bad):
        raise DP.HoldoutError(f"sealed holdout चे {len(bad)} rows engine मध्ये — परवानगी नाही")
    return df


def bars_15m(df1m, asof=None):
    """1m ⇒ बंद 15M spot bars (market_state.core.frame: 09:15 पासून, अपूर्ण नाही, CAS candle नाही)."""
    import market_state.core as MC
    guard(df1m)
    asof = pd.Timestamp(asof) if asof is not None else pd.to_datetime(df1m["timestamp"]).max() + pd.Timedelta(minutes=1)
    return MC.frame(df1m, "15m", asof).reset_index(drop=True)


def session_complete(day, last_bar_end):
    """Session पूर्ण: त्याचा शेवटचा अपेक्षित 15M bar बंद (CAS दिवसांत 15:15 ला संपणारा, नाहीतर 15:30 ला)."""
    from opportunity_engine import cas as CAS
    day = pd.Timestamp(day).normalize()
    cas_day = bool(CAS.cas_mask([day + pd.Timedelta(hours=15, minutes=15)]).iloc[0])
    need = day + (pd.Timedelta(hours=15, minutes=15) if cas_day else pd.Timedelta(hours=15, minutes=30))
    return pd.Timestamp(last_bar_end) >= need


def complete_sessions(m15):
    """{session तारीख: पूर्ण?}"""
    t = pd.to_datetime(m15["timestamp"]).dt.normalize()
    last = m15.assign(_d=t).groupby("_d")["bar_end"].max()
    return {pd.Timestamp(d): session_complete(d, e) for d, e in last.items()}


def sessions_of(m15):
    """प्रत्येक bar चा session (तारीख) आणि segment: दोन लागोपाठच्या sessions मध्ये holdout चा trading दिवस ⇒ नवा segment."""
    day = pd.to_datetime(m15["timestamp"]).dt.normalize()
    days = sorted(day.unique())
    seg, cur = {}, 0
    for i, d in enumerate(days):
        if i and any(DP.period(x) == "HOLDOUT" for x in pd.bdate_range(days[i - 1] + pd.Timedelta(days=1), d - pd.Timedelta(days=1))):
            cur += 1
        seg[pd.Timestamp(d)] = cur
    return day, [pd.Timestamp(d) for d in days], seg


def sigma_by_session(m15, n=20):
    """σ(session) = त्याआधीच्या (त्याच segment मधल्या) n पूर्ण sessions च्या 15M range चा median — 09:15 candle आणि CAS candle वगळून.
    Session सुरू होण्याआधी एकदा ठरतो; session भर तोच. पुरेसे sessions नाहीत ⇒ NaN (त्या session ला DC नाही)."""
    from opportunity_engine import cas as CAS
    ts = pd.to_datetime(m15["timestamp"])
    rng = (m15["high"] - m15["low"]).astype(float).to_numpy()
    ok = ~((ts.dt.hour == 9) & (ts.dt.minute == 15)).to_numpy() & ~CAS.cas_mask(ts).to_numpy()
    day, days, seg = sessions_of(m15)
    dayv = day.to_numpy()
    out = {}
    full = complete_sessions(m15)
    for i, d in enumerate(days):
        prev = [x for x in days[:i] if seg[x] == seg[d] and full[x]][-n:]          # फक्त पूर्ण sessions
        if len(prev) < n:
            out[d] = float("nan")
            continue
        m = np.isin(dayv, np.array(prev, dtype="datetime64[ns]")) & ok
        out[d] = float(np.median(rng[m])) if m.any() else float("nan")
    return out


def _rows_1m(df1m):
    if df1m is None or not len(df1m):
        return {}
    t = pd.to_datetime(df1m["timestamp"])
    key = t.dt.floor("15min")
    return {k: g for k, g in df1m.assign(_k=key).groupby("_k")}


def build(m15, df1m=None, s=None):
    """सगळ्या bars वर engine. रिटर्न dict: pivots {degree: [Pivot]}, sigma {session: σ}, sessions, segments, warmup_start, m15."""
    s = PS.load(s)
    guard(m15)
    m15 = m15.reset_index(drop=True)
    sig = sigma_by_session(m15, int(s["sigma_sessions"]))
    day, days, seg = sessions_of(m15)
    rows = _rows_1m(guard(df1m) if df1m is not None else None)
    ts = pd.to_datetime(m15["timestamp"])
    ts_of = (lambda i: pd.Timestamp(ts.iloc[i]))                                      # noqa: E731
    hi, lo = m15["high"].to_numpy(float), m15["low"].to_numpy(float)
    k = {d: float(s["k"][d]) for d in DEGREES}
    wu = {d: int(s["warmup_sessions"][d]) for d in DEGREES}
    d0, ups = D0(0), {d: Upper(d) for d in DEGREES[1:]}
    piv = {d: [] for d in DEGREES}
    started = {}                                                                     # segment ⇒ σ असलेला पहिला session क्रमांक
    sess_idx = {d: i for i, d in enumerate(days)}
    cur_seg = None
    last_same = {d: {"H": None, "L": None} for d in DEGREES}

    def finish(p, d, sigma):
        """warm-up, EQ खूण, session — pivot frozen होण्याआधी एकदाच."""
        si = sess_idx[pd.Timestamp(p.known_at - BAR).normalize()] - started[cur_seg]
        q = last_same[d][p.kind]
        eq = q is not None and abs(p.price - q.price) <= float(s["eq_tol_sigma"]) * sigma
        p = replace(p, warmup=si < wu[d], eq=bool(eq), session=si)
        last_same[d][p.kind] = p
        piv[d].append(p)
        return p

    for b in range(len(m15)):
        dd = pd.Timestamp(day.iloc[b])
        sigma = sig.get(dd, float("nan"))
        if seg[dd] != cur_seg:                                                         # holdout ओलांडली ⇒ reset
            cur_seg = seg[dd]
            d0.reset()
            for u in ups.values():
                u.reset()
            last_same = {d: {"H": None, "L": None} for d in DEGREES}
        if not np.isfinite(sigma):
            continue
        started.setdefault(cur_seg, sess_idx[dd])
        known = ts_of(b) + BAR
        r1 = rows.get(ts_of(b))
        if r1 is not None and "received_at" in r1.columns:                             # फक्त candle च्या close ला उपलब्ध असलेला 1m
            r1 = r1[pd.to_datetime(r1["received_at"]) <= known]                         # (नंतरचा backfill आधीचा pivot बदलत नाही)
        p = d0.step(b, hi[b], lo[b], k[0] * sigma, sigma, known, None, ts_of, r1)
        if p is None:
            continue
        q = finish(p, 0, sigma)
        for d in DEGREES[1:]:                                                          # D(n) चा नवा pivot ⇒ D(n+1) ला
            r = ups[d].step(q, k[d] * sigma, sigma, None)
            if r is None:
                break
            q = finish(r, d, sigma)
    return {"pivots": piv, "sigma": sig, "sessions": days, "segments": seg, "started": started, "m15": m15, "settings": s,
            "state": {"D0": (d0.mode, d0.ext), **{f"D{d}": (u.mode, None if u.ext is None else (u.ext.price, u.ext.bar)) for d, u in ups.items()}}}


# ---------------------------------------------------------------------------------------------------------------- वाचन (asof पर्यंत)
def known(res, d, asof):
    return [p for p in res["pivots"][d] if p.known_at <= pd.Timestamp(asof)]


def tentative(res, d, asof):
    """शेवटच्या confirmed pivot नंतरचं चालू टोक (pivot नाही; trend मध्ये नाही). bars फक्त asof पर्यंत बंद झालेले."""
    ps = known(res, d, asof)
    if not ps:
        return None
    m = res["m15"]
    end = pd.to_datetime(m["timestamp"]) + BAR <= pd.Timestamp(asof)
    last = ps[-1]
    seg = m.iloc[last.bar + 1:][end.iloc[last.bar + 1:].to_numpy()]
    if not len(seg):
        return None
    if last.kind == "H":
        i = int(seg["low"].to_numpy(float).argmin())
        return {"kind": "L", "price": float(seg["low"].iloc[i]), "ts": str(seg["timestamp"].iloc[i])}
    i = int(seg["high"].to_numpy(float).argmax())
    return {"kind": "H", "price": float(seg["high"].iloc[i]), "ts": str(seg["timestamp"].iloc[i])}


def labels(ps):
    """प्रत्येक confirmed pivot ला HH / LH / EQH (H) किंवा HL / LL / EQL (L) — त्याच degree च्या मागच्या same-type pivot शी."""
    out, last = {}, {"H": None, "L": None}
    for p in ps:
        q = last[p.kind]
        if p.eq:
            out[id(p)] = "EQH" if p.kind == "H" else "EQL"
        elif q is None:
            out[id(p)] = p.kind
        elif p.kind == "H":
            out[id(p)] = "HH" if p.price > q.price else "LH"
        else:
            out[id(p)] = "HL" if p.price > q.price else "LL"
        last[p.kind] = p
    return out


def trend(ps):
    """फक्त confirmed pivots: शेवटचे दोन H आणि दोन L. HH + HL = वर; LH + LL = खाली; बाकी (EQ सह) = range.
    Protected swing = चालू trend चा शेवटचा उलट pivot (range ⇒ नाही)."""
    hs = [p for p in ps if p.kind == "H"][-2:]
    ls = [p for p in ps if p.kind == "L"][-2:]
    out = {"dir": 0, "name": "range", "protected": None, "last": [(p.kind, p.price, str(p.ts)) for p in ps[-2:]]}
    if len(hs) < 2 or len(ls) < 2 or hs[1].eq or ls[1].eq:
        return out
    if hs[1].price > hs[0].price and ls[1].price > ls[0].price:
        out.update(dir=1, name="वर", protected={"kind": "L", "price": ls[1].price, "ts": str(ls[1].ts)})
    elif hs[1].price < hs[0].price and ls[1].price < ls[0].price:
        out.update(dir=-1, name="खाली", protected={"kind": "H", "price": hs[1].price, "ts": str(hs[1].ts)})
    return out


def snapshot(res, asof):
    """asof ला प्रत्येक degree: confirmed pivots (JSON), trend, protected, tentative, warm-up स्थिती."""
    out = {}
    for d in DEGREES:
        ps = known(res, d, asof)
        lab = labels(ps)
        out[f"D{d}"] = {"pivots": [pivot_json(p, lab[id(p)]) for p in ps], "trend": trend(ps), "tentative": tentative(res, d, asof),
                        "warmup_done": any(not p.warmup for p in ps)}
    return out


def pivot_json(p, label=None):
    return {"degree": p.degree, "kind": p.kind, "label": label, "price": round(p.price, 2), "ts": str(p.ts), "bar": p.bar,
            "confirm_bar": p.confirm_bar, "known_at": str(p.known_at), "sigma": round(p.sigma, 3), "theta": round(p.theta, 3),
            "rule": p.rule, "eq": p.eq, "warmup": p.warmup}


# ---------------------------------------------------------------------------------------------------------------- मोजमाप (वर्णन)
def measures(res, start, end):
    """[start, end] मध्ये known_at असलेल्या pivots चं वर्णन (backtest नाही): संख्या, leg लांबी (bars, σ), confirmation lag (bars:
    median / p75 / p90), 09:15 वरचे pivots %, नियम (normal / 1m), warm-up."""
    m = res["m15"]
    t = pd.to_datetime(m["timestamp"])
    rows = []
    for d in DEGREES:
        allp = res["pivots"][d]
        ps = [p for p in allp if pd.Timestamp(start) <= p.known_at <= pd.Timestamp(end)]
        segof = (lambda p: res["segments"].get(pd.Timestamp(p.ts).normalize()))  # noqa: E731
        legs_b, legs_s = [], []
        for a, b in zip(allp, allp[1:]):                                       # leg: एकाच segment मध्ये, warm-up नाही
            if b in ps and not a.warmup and not b.warmup and segof(a) == segof(b):
                legs_b.append(b.bar - a.bar)
                legs_s.append(abs(b.price - a.price) / b.sigma if b.sigma else np.nan)
        lag = [p.confirm_bar - p.bar for p in ps if not p.warmup]
        q = (lambda x, r: round(float(np.percentile(x, r)), 1) if len(x) else None)  # noqa: E731
        rows.append({"degree": f"D{d}", "n": len(ps), "leg_bars_median": q(legs_b, 50), "leg_sigma_median": q(legs_s, 50),
                     "lag_median": q(lag, 50), "lag_p75": q(lag, 75), "lag_p90": q(lag, 90),
                     "at_0915_pct": round(100.0 * sum(1 for p in ps if t.iloc[p.bar].strftime("%H:%M") == "09:15") / len(ps), 1) if ps else None,
                     "rule_1m": sum(1 for p in ps if p.rule == "1m"), "rule_conservative": sum(1 for p in ps if p.rule == "conservative"),
                     "warmup": sum(1 for p in ps if p.warmup), "warmup_done": any(not p.warmup for p in allp)})
    return rows
