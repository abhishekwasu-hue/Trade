"""
price_action/major_levels.py
----------------------------
🎓 "Major Level (Trader's Eye)" engine v1 — वापरकर्त्याच्या डोळ्याचे नियम (2026-10-06), report-only (कुठलाही bot gate नाही):
  1) प्रति chart फक्त 2–4 major levels.
  2) chart TF वरचा 2–8 आठवड्यांचा इतिहास; pivots **HTF** (4H-equivalent) bars वरून.
  3) ≥ 2–3 reactions एकाच किंमत-पट्ट्यात; tolerance = k × median HTF range (k grid मधून).
  4) role reversal (त्याच पट्ट्यात swing high आणि swing low दोन्ही) ला सर्वाधिक वजन.
  5) range edges ला वजन; range च्या आतले minor swings (prominence < s × median range) वगळले.
  6) level किंमत = reactions च्या **wick extremes** चा cluster (median किंवा extreme), zone चा midpoint नाही.
  7) तिरकी trendline फक्त ≥ 3 confirmed pivots (tolerance सह), आणि त्यानंतर कुठलाही HTF close रेषेपलीकडे नाही.
No-lookahead: `asof` पर्यंत **संपलेलेच** chart-TF bars (timestamp + TF ≤ asof); HTF bar पूर्ण झाला तरच; pivot त्यानंतरचे r HTF bars पूर्ण
झाल्यावरच confirmed; prominence फक्त `asof` पर्यंतच्या bars वर — म्हणून सर्वात नवे pivots prom_w HTF bars पर्यंत उशिरा दिसू शकतात (पण नंतर
कधीच मागे फिरत नाहीत).
Ranking (review नंतर): role-reversal levels आधी (नियम 4: सर्वाधिक वजन), मग score. 2 पेक्षा कमी levels मिळाले तर range edges (सर्वोच्च pivot
high / सर्वात खालचा pivot low) "weak" म्हणून भरले जातात.
Trendline गणित chart-TF bar-index वर (HTF buckets असमान लांबीचे असतात), anchor = त्या HTF bucket मधला प्रत्यक्ष wick चा chart-TF bar.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MLConfig:
    htf_minutes: int = 240
    pivot_r: int = 2                  # HTF fractal: दोन्ही बाजूंना r bars
    lookback_weeks: int = 4
    k_tol: float = 0.5                # cluster tolerance = k × median HTF range
    min_react: int = 2
    prom_s: float = 1.0               # pivot prominence ≥ s × median HTF range (दोन्ही बाजूंना, ±prom_w bars मध्ये)
    prom_w: int = 6
    price_mode: str = "median"        # "median" | "extreme"
    max_levels: int = 4
    min_levels: int = 2
    rr_weight: float = 2.0            # role reversal
    edge_weight: float = 1.0          # range edge
    tl_min_pivots: int = 3


SESSIONS = {"NSE": ("09:15", "15:30"), "MCX": ("09:00", "23:30")}
MCX_WINTER_CLOSE = "23:55"                                       # नोव्हेंबर–मार्च (US DST संपल्यावर) MCX सत्र 23:55 पर्यंत


def session_close(day, exchange):
    c = SESSIONS[exchange][1]
    if exchange == "MCX" and (pd.Timestamp(day).month >= 11 or pd.Timestamp(day).month <= 3):
        c = MCX_WINTER_CLOSE
    hh, mm = (int(x) for x in c.split(":"))
    return pd.Timestamp(day).normalize() + pd.Timedelta(hours=hh, minutes=mm)


def ltf_minutes_of(d):
    diffs = d["timestamp"].diff().dropna()
    return int(diffs.dt.total_seconds().min() // 60) if len(diffs) else 15


def _prep(df):
    d = df[["timestamp", "open", "high", "low", "close"]].copy()
    ts = pd.to_datetime(d["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["timestamp"] = ts
    return d.dropna().sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)


def htf_bars(df, htf_minutes=240, exchange="NSE", ltf_minutes=None):
    """chart-TF → HTF (सत्राच्या सुरुवातीपासून htf_minutes चे तुकडे). फक्त **पूर्ण** HTF bars: window संपला किंवा त्या दिवसाचं सत्र संपलं."""
    d = _prep(df)
    if d.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "end", "high_ts", "low_ts"])
    start = SESSIONS[exchange][0]
    sh, sm = (int(x) for x in start.split(":"))
    if ltf_minutes is None:
        ltf_minutes = ltf_minutes_of(d)
    day = d["timestamp"].dt.normalize()
    sess0 = day + pd.Timedelta(hours=sh, minutes=sm)
    k = ((d["timestamp"] - sess0).dt.total_seconds() // (htf_minutes * 60)).astype(int)
    d["bucket"] = sess0 + pd.to_timedelta(k * htf_minutes, unit="m")
    g = d.groupby("bucket").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                last_ltf=("timestamp", "max")).reset_index().rename(columns={"bucket": "timestamp"})
    hi_at = d.loc[d.groupby("bucket")["high"].idxmax(), ["bucket", "timestamp"]].set_index("bucket")["timestamp"]
    lo_at = d.loc[d.groupby("bucket")["low"].idxmin(), ["bucket", "timestamp"]].set_index("bucket")["timestamp"]
    g["high_ts"] = g["timestamp"].map(hi_at)                      # प्रत्यक्ष wick कोणत्या chart-TF bar वर (trendline anchors साठी)
    g["low_ts"] = g["timestamp"].map(lo_at)
    sess_close = pd.Series([session_close(t, exchange) for t in g["timestamp"]], index=g.index)
    g["end"] = np.minimum(g["timestamp"] + pd.Timedelta(minutes=htf_minutes), sess_close)
    last_end = d["timestamp"].iloc[-1] + pd.Timedelta(minutes=ltf_minutes)
    complete = (g["end"] <= last_end) | (g["timestamp"].dt.normalize() < d["timestamp"].iloc[-1].normalize())
    return g[complete][["timestamp", "open", "high", "low", "close", "end", "high_ts", "low_ts"]].reset_index(drop=True)


def confirmed_pivots(h, r):
    """HTF fractal pivots: i चा high डाव्या r पेक्षा मोठा आणि उजव्या r पेक्षा ≥; i + r ≤ शेवटचा index (confirmed)."""
    H, L = h["high"].to_numpy(float), h["low"].to_numpy(float)
    out = []
    for i in range(r, len(h) - r):
        if H[i] > H[i - r:i].max() and H[i] >= H[i + 1:i + r + 1].max():
            out.append((i, "H", H[i]))
        if L[i] < L[i - r:i].min() and L[i] <= L[i + 1:i + r + 1].min():
            out.append((i, "L", L[i]))
    return out


def _prominent(h, piv, mr, s, w):
    H, L = h["high"].to_numpy(float), h["low"].to_numpy(float)
    keep = []
    for i, kind, p in piv:
        lo, hi = max(0, i - w), min(len(h), i + w + 1)
        if kind == "H":
            left, right = p - L[lo:i].min() if i > lo else 0.0, p - L[i + 1:hi].min() if hi > i + 1 else 0.0
        else:
            left, right = H[lo:i].max() - p if i > lo else 0.0, H[i + 1:hi].max() - p if hi > i + 1 else 0.0
        if min(left, right) >= s * mr:
            keep.append((i, kind, p))
    return keep


def _clusters(points, tol):
    pts = sorted(points, key=lambda x: x[2])
    out, cur = [], []
    for p in pts:
        if cur and (p[2] - cur[-1][2] > tol or p[2] - cur[0][2] > 2 * tol):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def major_levels(df, asof=None, cfg=MLConfig(), exchange="NSE"):
    """chart-TF candles → (levels, trendlines, info). levels: [{price, score, n_react, role_reversal, edge, kinds, first, last}] (score-क्रमाने,
    2–4). फक्त `asof` पर्यंतचे bars."""
    d = _prep(df)
    ltf = ltf_minutes_of(d)
    if asof is not None:
        d = d[d["timestamp"] + pd.Timedelta(minutes=ltf) <= pd.Timestamp(asof)]     # फक्त संपलेले bars (review: एका bar चा lookahead)
    if d.empty:
        return [], [], {}
    since = (d["timestamp"].iloc[-1] - pd.Timedelta(weeks=cfg.lookback_weeks)).normalize()     # दिवसाच्या सुरुवातीपासून (तुकडा bucket नाही)
    d = d[d["timestamp"] >= since].reset_index(drop=True)
    h = htf_bars(d, cfg.htf_minutes, exchange, ltf_minutes=ltf)
    if len(h) < 2 * cfg.pivot_r + 3:
        return [], [], {"htf_bars": len(h)}
    mr = float((h["high"] - h["low"]).median())
    tol = cfg.k_tol * mr
    piv = _prominent(h, confirmed_pivots(h, cfg.pivot_r), mr, cfg.prom_s, cfg.prom_w)
    info = {"htf_bars": len(h), "median_range": mr, "tol": tol, "pivots": len(piv), "below_min": False}
    if not piv:
        return [], [], info
    top_i = max((p for p in piv if p[1] == "H"), key=lambda x: x[2], default=(None,))[0]
    bot_i = min((p for p in piv if p[1] == "L"), key=lambda x: x[2], default=(None,))[0]

    def _cand(c, weak=False):
        kinds = {p[1] for p in c}
        rr = len(kinds) == 2
        edge = any((p[1] == "H" and p[0] == top_i) or (p[1] == "L" and p[0] == bot_i) for p in c)
        prices = np.array([p[2] for p in c])
        if cfg.price_mode == "extreme" and not rr:
            price = float(prices.max() if "H" in kinds else prices.min())
        else:
            price = float(np.median(prices))
        return {"price": price, "score": len(c) + cfg.rr_weight * rr + cfg.edge_weight * edge, "n_react": len(c), "role_reversal": rr,
                "edge": edge, "weak": weak, "kinds": "".join(sorted(kinds)), "first": h["timestamp"].iloc[min(p[0] for p in c)],
                "last": h["timestamp"].iloc[max(p[0] for p in c)]}

    clusters = _clusters(piv, tol)
    cands = [_cand(c) for c in clusters if len(c) >= cfg.min_react or (len({p[1] for p in c}) == 2 and len(c) >= 2)]
    cands.sort(key=lambda x: (-x["role_reversal"], -x["score"], -x["n_react"]))     # नियम 4: role reversal सर्वाधिक वजन
    sel = []
    for c in cands:
        if all(abs(c["price"] - s_["price"]) > 2 * tol for s_ in sel):
            sel.append(c)
        if len(sel) >= cfg.max_levels:
            break
    if len(sel) < cfg.min_levels:                                    # range edges ने भरणे ("weak" — नियम 3 पूर्ण नाही)
        info["below_min"] = True
        for c in clusters:
            if len(sel) >= cfg.min_levels:
                break
            if any((p[1] == "H" and p[0] == top_i) or (p[1] == "L" and p[0] == bot_i) for p in c):
                cc = _cand(c, weak=True)
                if all(abs(cc["price"] - s_["price"]) > 2 * tol for s_ in sel):
                    sel.append(cc)
    lines = trendlines(h, piv, tol, cfg.tl_min_pivots, ltf=d)
    return sel, lines, info


def trendlines(h, piv, tol, min_pivots=3, ltf=None):
    """उतरती resistance (pivot highs) / चढती support (pivot lows): ≥ min_pivots pivots रेषेवर (± tol), पहिल्या anchor नंतर कुठलाही close रेषेपलीकडे
    (± tol) नाही. गणित chart-TF bar-index वर (ltf दिला तर; नाहीतर HTF index). anchor = प्रत्यक्ष wick चा chart-TF bar. प्रत्येक प्रकारातली
    सर्वाधिक pivots (मग सर्वात अलीकडची) रेषा. रिटर्न: type, slope (प्रति chart-TF bar), a_ts/a_price, anchors, anchor_prices, value_at_last."""
    if ltf is not None and len(ltf):
        ts = pd.to_datetime(ltf["timestamp"]).reset_index(drop=True)
        pos = {t: i for i, t in enumerate(ts)}
        C = ltf["close"].to_numpy(float)
        xof = lambda p: pos.get(h["high_ts" if p[1] == "H" else "low_ts"].iloc[p[0]], None)     # noqa: E731
        tsof = lambda x: ts.iloc[x]                                                               # noqa: E731
    else:
        C = h["close"].to_numpy(float)
        xof = lambda p: p[0]                                                                      # noqa: E731
        tsof = lambda x: h["timestamp"].iloc[x]                                                   # noqa: E731
    n = len(C)
    out = []
    for kind, sign, name in (("H", -1, "desc_resistance"), ("L", +1, "asc_support")):
        pts = sorted([(xof(p), p[2]) for p in piv if p[1] == kind and xof(p) is not None])
        best = None
        for a in range(len(pts)):
            for b in range(a + 1, len(pts)):
                xa, pa = pts[a]
                xb, pb = pts[b]
                if xb == xa:
                    continue
                slope = (pb - pa) / (xb - xa)
                if sign * slope <= 0:                                     # desc: slope < 0; asc: slope > 0
                    continue
                on = [q for q in pts if q[0] >= xa and abs(q[1] - (pa + slope * (q[0] - xa))) <= tol]
                if len(on) < min_pivots:
                    continue
                idx = np.arange(xa, n)
                lv = pa + slope * (idx - xa)
                viol = (C[idx] > lv + tol) if kind == "H" else (C[idx] < lv - tol)
                if viol.any():
                    continue
                key = (len(on), on[-1][0])
                if best is None or key > best[0]:
                    best = (key, {"type": name, "slope": slope, "a_x": xa, "a_ts": tsof(xa), "a_price": pa,
                                  "anchors": [tsof(q[0]) for q in on], "anchor_prices": [q[1] for q in on],
                                  "value_at_last": pa + slope * (n - 1 - xa), "n_pivots": len(on)})
        if best:
            out.append(best[1])
    return out


def match_levels(algo, truth, tol_pct=0.15):
    """precision = algo levels पैकी किती ground truth ±tol_pct% मध्ये; recall = ground truth पैकी किती algo ने पकडले. (p, r, f1, matched pairs)."""
    algo, truth = list(algo), list(truth)
    hit_a = [any(abs(a - t) / t * 100 <= tol_pct for t in truth) for a in algo]
    hit_t = [any(abs(a - t) / t * 100 <= tol_pct for a in algo) for t in truth]
    p = sum(hit_a) / len(algo) if algo else 0.0
    r = sum(hit_t) / len(truth) if truth else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1
