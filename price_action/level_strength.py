"""
price_action/level_strength.py
------------------------------
🎓 T2.4–T2.6 — Level/zone ची ताकद (indicator-मुक्त), approach नियम आणि break/sweep घटना. फक्त मोजमाप आणि अहवाल — कुठलाही bot gate नाही
(T4 मध्ये, G2 नंतर, डीफॉल्ट OFF setting मागे जोडायचं).

Zone (कुठल्याही engine चा: sr_dynamic / SR V3 / OE zones): {"low", "high", "kind", "formed_at"(timestamp, ऐच्छिक)}. kind: SUPPORT/DEMAND (खालून आधार)
किंवा RESISTANCE/SUPPLY (वरून अडथळा); इतर (KEY/ROUND/GAP) ⇒ बाजू किंमतीवरून (role).
सर्व मोजमाप **as-of `t`** (bar index): फक्त bars ≤ t वापरले जातात.

T2.4 features:
  • origin_leg   — zone च्या उगमापासून निघालेल्या leg चं लेबल/score (legs.py; फक्त `known_at ≤ t` असलेले legs)
  • departure_mr — उगमानंतरच्या पहिल्या 1–3 candles ची एकूण range ÷ median_range (जोरात निघणं = ताकद)
  • base_bars    — उगमाआधी zone मध्ये सलग किती candles (लहान base = ताजा, जोरदार असंतुलन)
  • touches      — उगमानंतर zone ला किती वेगळ्या visits (चिन्ह/sign data वरून ठरवायचं — T3; इथे फक्त संख्या)
  • recency      — exp(−Δt / τ), Δt = शेवटच्या संपर्कापासून (किंवा उगमापासून) bars
  • round_dist_mr— zone-मध्य ते जवळचा round number (NIFTY 100/500/1000, BANKNIFTY 500/1000) ÷ median_range — फक्त feature
  • tpo_share    — शेवटच्या N सत्रांत (1-min असल्यास 1-min) किती वेळ किंमत zone मध्ये होती (acceptance)
  • role_reversal— zone तुटला आणि नंतर उलट्या बाजूने retest होऊन टिकला का
T2.5 approach नियम: HEALTHY_PULLBACK मजबूत zone मध्ये ⇒ REACTION candidate (मग #241 rejection gate entry ठरवतो);
                    STRONG_IMPULSE zone मध्ये ⇒ BREAK candidate (reversal entry नाही).
T2.6 घटना: SWEEP (wick पलीकडे, close आत) · BREAK (close दूरच्या कडेपलीकडे, n_reclaim bars मध्ये reclaim नाही) · BREAK_CASCADE (BREAK + displacement)
           · FAILED_BREAKOUT (पलीकडे close, n_reclaim मध्ये परत आत). `bar` = break bar; `known_at` = निर्णय ज्या bar ला निश्चित झाला (BREAK/FAILED = bar + n).
"""
import math

import numpy as np
import pandas as pd

from . import legs as LG

ROUND_STEPS = {"NIFTY": (100, 500, 1000), "BANKNIFTY": (500, 1000), "SENSEX": (500, 1000)}
SUPPORT_KINDS = ("SUPPORT", "DEMAND")
RESIST_KINDS = ("RESISTANCE", "SUPPLY")

REACTION_CANDIDATE, BREAK_CANDIDATE = "REACTION_CANDIDATE", "BREAK_CANDIDATE"
SWEEP, BREAK, BREAK_CASCADE, FAILED_BREAKOUT = "SWEEP", "BREAK", "BREAK_CASCADE", "FAILED_BREAKOUT"


def side_of(zone, price):
    """+1 = आधार (support: किंमत वर), −1 = अडथळा (resistance: किंमत खाली), 0 = आत/अनिश्चित. kind दिलेला असेल तर तोच."""
    k = str(zone.get("kind", "")).upper()
    if k in SUPPORT_KINDS:
        return 1
    if k in RESIST_KINDS:
        return -1
    if price > zone["high"]:
        return 1
    if price < zone["low"]:
        return -1
    return 0


def prep_bars(df, cfg=None):
    """df -> arrays (o, h, l, c, ts, mr) — अनेक zones साठी पुन्हा पुन्हा वापरायला (मोठ्या backtest मध्ये वेग)."""
    cfg = cfg or LG.LegConfig()
    df = df.reset_index(drop=True)
    return {"o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float), "l": df["low"].to_numpy(float), "c": df["close"].to_numpy(float),
            "ts": pd.to_datetime(df["timestamp"]).to_numpy("datetime64[ns]"), "mr": LG.median_range(df, cfg.n_median), "df": df}


def origin_index(df, zone, ts=None):
    """`formed_at` (timestamp) -> bar index (त्या वेळेपर्यंतचा शेवटचा bar). नसेल तर None."""
    fa = zone.get("formed_at")
    if fa is None or (isinstance(fa, float) and math.isnan(fa)):
        return None
    if ts is None:
        ts = pd.to_datetime(df["timestamp"]).to_numpy("datetime64[ns]")
    i = int(np.searchsorted(ts, np.datetime64(pd.Timestamp(fa).tz_localize(None) if pd.Timestamp(fa).tzinfo else pd.Timestamp(fa)), side="right")) - 1
    return i if i >= 0 else None


def _visits(h, l, lo, hi):
    inside = (l <= hi) & (h >= lo)
    starts = np.flatnonzero(inside & ~np.r_[False, inside[:-1]])
    return starts, inside


def round_distance(mid, symbol="NIFTY"):
    steps = ROUND_STEPS.get(str(symbol).upper(), (100, 500, 1000))
    return min(abs(mid - round(mid / s) * s) for s in steps)


def tpo_share(df_fine, lo, hi, t_end, sessions=5):
    """शेवटच्या `sessions` सत्रांत (t_end पर्यंत) किती bars ची close zone मध्ये — 1-min डेटा असल्यास time-at-price."""
    if df_fine is None or not len(df_fine):
        return None
    ts = pd.to_datetime(df_fine["timestamp"])
    m = ts <= pd.Timestamp(t_end)
    if not m.any():
        return None
    sub = df_fine[m]
    days = ts[m].dt.normalize()
    keep = days >= sorted(days.unique())[-sessions] if days.nunique() >= sessions else days == days
    c = sub["close"].to_numpy(float)[keep.to_numpy()]
    return round(float(((c >= lo) & (c <= hi)).mean()), 4) if len(c) else None


def strength_features(zone, df, t, symbol="NIFTY", legs=None, df_fine=None, tau_bars=200.0, cfg=None, mr=None, bars=None):
    """zone + bars (df, जुनं → नवं) + as-of bar index `t` -> features dict. फक्त bars ≤ t. `bars` = prep_bars(df) (ऐच्छिक, वेगासाठी)."""
    cfg = cfg or LG.LegConfig()
    bars = bars or prep_bars(df, cfg)
    df = bars["df"]
    t = min(int(t), len(df) - 1)
    o, h, l, c = bars["o"], bars["h"], bars["l"], bars["c"]
    mr = bars["mr"] if mr is None else mr
    mr_t = mr[t] if np.isfinite(mr[t]) and mr[t] > 0 else float(np.nanmedian(h[:t + 1] - l[:t + 1]))
    lo, hi = float(zone["low"]), float(zone["high"])
    mid = (lo + hi) / 2
    side = side_of(zone, c[t])
    oi = origin_index(df, zone, bars["ts"])
    if oi is not None and oi > t:
        oi = None                                                    # भविष्यात बनलेला zone — as-of t माहीत नाही
    f = {"width_mr": round((hi - lo) / mr_t, 3), "dist_mr": round((c[t] - mid) / mr_t, 3), "side": side, "origin_known": oi is not None}
    # departure आणि base
    if oi is not None:
        a, b = oi + 1, min(oi + 3, t)
        f["departure_mr"] = round(float((h[a:b + 1].max() - l[a:b + 1].min()) / mr_t), 3) if b >= a else None
        base = 0
        j = oi
        while j >= 0 and l[j] <= hi and h[j] >= lo:
            base += 1
            j -= 1
        f["base_bars"] = base
    else:
        f["departure_mr"], f["base_bars"] = None, None
    # touches आणि recency (उगमानंतर; उगम माहीत नसेल तर शेवटचे 400 bars)
    start = (oi + 1) if oi is not None else max(t - 400, 0)
    while start <= t and l[start] <= hi and h[start] >= lo:          # उगमानंतर zone सोडेपर्यंतचे bars = departure, touch नाही
        start += 1
    starts, _ = _visits(h[start:t + 1], l[start:t + 1], lo, hi)
    f["touches"] = int(len(starts))
    last = (start + int(starts[-1])) if len(starts) else (oi if oi is not None else start)
    f["bars_since"] = int(t - last)
    f["recency"] = round(math.exp(-(t - last) / tau_bars), 4)
    f["round_dist_mr"] = round(round_distance(mid, symbol) / mr_t, 3)
    f["tpo_share"] = tpo_share(df_fine, lo, hi, df["timestamp"].iloc[t]) if df_fine is not None else None
    # role reversal: दूरच्या कडेपलीकडे close (तुटला) आणि नंतर उलट्या बाजूने visit होऊन त्या बाजूला close
    rr = False
    seg_c = c[start:t + 1]
    if side != 0 and len(seg_c):
        broke = np.flatnonzero(seg_c < lo) if side > 0 else np.flatnonzero(seg_c > hi)
        if len(broke):
            k0 = int(broke[0])
            after_h, after_l, after_c = h[start + k0 + 1:t + 1], l[start + k0 + 1:t + 1], c[start + k0 + 1:t + 1]
            if side > 0:                                             # support तुटला ⇒ आता resistance म्हणून वरून नाकारतो का
                rr = bool(((after_h >= lo) & (after_c < lo)).any())
            else:
                rr = bool(((after_l <= hi) & (after_c > hi)).any())
    f["role_reversal"] = rr
    # origin leg (legs.py) — zone उगमापासून सुरू होणारा आणि t पर्यंत माहीत असलेला leg
    f["origin_label"], f["origin_score"] = None, None
    if legs is not None and oi is not None:
        cands = [lg for lg in legs if lg.known_at <= t and abs(lg.start_bar - oi) <= 3]
        if cands:
            lg = min(cands, key=lambda x: abs(x.start_bar - oi))
            f["origin_label"], f["origin_score"] = lg.label, lg.score
    return f


DEFAULT_WEIGHTS = {"departure_mr": 0.25, "origin_strong": 0.25, "base_short": 0.15, "recency": 0.15, "tpo_low": 0.10, "role_reversal": 0.10, "touches": 0.0}


def strength_score(f, weights=None):
    """features -> 0–100. `touches` चं वजन डीफॉल्ट 0 — चिन्ह (sign) T3 मध्ये IS डेटावरून ठरवायचं (गृहीत धरत नाही)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    dep = min((f.get("departure_mr") or 0.0) / 3.0, 1.0)
    origin = 1.0 if f.get("origin_label") == LG.STRONG_IMPULSE else 0.5 if f.get("origin_label") in (LG.WEAK_IMPULSE, LG.REVERSAL) else 0.0
    base = 0.0 if f.get("base_bars") is None else 1.0 / (1.0 + max(f["base_bars"] - 1, 0) / 3.0)
    tpo = f.get("tpo_share")
    tpo_low = 0.5 if tpo is None else max(0.0, 1.0 - tpo * 5.0)          # कमी वेळ = असंतुलन (acceptance नाही)
    touches = min(f.get("touches", 0), 5) / 5.0
    s = (w["departure_mr"] * dep + w["origin_strong"] * origin + w["base_short"] * base + w["recency"] * f.get("recency", 0.0)
         + w["tpo_low"] * tpo_low + w["role_reversal"] * (1.0 if f.get("role_reversal") else 0.0) + w["touches"] * touches)
    tot = sum(abs(v) for v in w.values()) or 1.0
    return round(100.0 * max(s, 0.0) / tot, 1)


# ---------------------------------------------------------------------------------------------------------------------
# T2.5 approach नियम
# ---------------------------------------------------------------------------------------------------------------------
def approach(current_leg, zone, strength, min_strength=50.0):
    """चालू leg zone कडे येत असताना: HEALTHY_PULLBACK + मजबूत zone ⇒ REACTION_CANDIDATE; STRONG_IMPULSE ⇒ BREAK_CANDIDATE; नाहीतर None.
    leg zone कडे येत आहे का: support कडे खाली (dir −1), resistance कडे वर (dir +1)."""
    if current_leg is None or zone is None:
        return None, "leg/zone नाही"
    side = side_of(zone, current_leg.end_price)
    toward = (side > 0 and current_leg.direction < 0) or (side < 0 and current_leg.direction > 0)
    if not toward:
        return None, "leg zone कडे येत नाही"
    if current_leg.label == LG.STRONG_IMPULSE:
        return BREAK_CANDIDATE, "जोरदार impulse zone मध्ये ⇒ तुटण्याची शक्यता; reversal entry नाही"
    if current_leg.label == LG.HEALTHY_PULLBACK and strength >= min_strength:
        return REACTION_CANDIDATE, f"निरोगी pullback मजबूत zone (ताकद {strength:.0f}) मध्ये ⇒ reaction candidate (rejection gate पुढे ठरवेल)"
    return None, f"{current_leg.label} / ताकद {strength:.0f} — नियम लागू नाही"


# ---------------------------------------------------------------------------------------------------------------------
# T2.6 घटना
# ---------------------------------------------------------------------------------------------------------------------
def zone_events(zone, df, start, end, n_reclaim=2, cfg=None, mr=None):
    """bars [start, end] मधल्या घटना. support साठी "पलीकडे" = low च्या खाली; resistance साठी high च्या वर.
    रिटर्न [{type, bar, known_at, time, price}] — BREAK/FAILED चा निर्णय break bar + n_reclaim ला (त्या bars उपलब्ध असतील तरच)."""
    cfg = cfg or LG.LegConfig()
    df = df.reset_index(drop=True)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    mr = LG.median_range(df, cfg.n_median) if mr is None else mr
    ts = pd.to_datetime(df["timestamp"])
    lo, hi = float(zone["low"]), float(zone["high"])
    side = side_of(zone, c[max(start - 1, 0)])
    if side == 0:
        return []
    end = min(int(end), len(df) - 1)
    out = []
    i = max(int(start), 0)
    while i <= end:
        beyond_wick = (l[i] < lo) if side > 0 else (h[i] > hi)
        beyond_close = (c[i] < lo) if side > 0 else (c[i] > hi)
        if beyond_close:
            j_end = i + n_reclaim
            if j_end > end:
                break                                                   # निर्णयासाठी पुरेसे bars अजून नाहीत (no-lookahead)
            reclaimed = any(((c[j] >= lo) if side > 0 else (c[j] <= hi)) for j in range(i + 1, j_end + 1))
            if reclaimed:
                typ = FAILED_BREAKOUT
            else:
                body = abs(c[i] - o[i])
                rng = max(h[i] - l[i], 1e-12)
                disp = np.isfinite(mr[i]) and body >= cfg.d_k * mr[i] and body / rng >= cfg.d_body
                typ = BREAK_CASCADE if disp else BREAK
            out.append({"type": typ, "bar": i, "known_at": j_end, "time": ts.iloc[i], "price": float(c[i])})
            if typ in (BREAK, BREAK_CASCADE):
                break                                                   # zone तुटला — पुढच्या घटना नव्या role मध्ये
            i = j_end + 1
            continue
        if beyond_wick:
            out.append({"type": SWEEP, "bar": i, "known_at": i, "time": ts.iloc[i], "price": float(l[i] if side > 0 else h[i])})
        i += 1
    return out
