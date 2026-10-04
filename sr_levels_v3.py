"""
sr_levels_v3.py
-----------------
🎓 वापरकर्त्याशी चर्चा करून (नवीन, स्वतंत्र, प्रयोगिक) — Dynamic S/R चं सुधारित रूप. जुना `sr_dynamic.py` / bots /
market_zones **अजिबात बदललेले नाहीत**; इथे फक्त त्याचं pivot-शोधणारं फंक्शन (`find_pivots_indexed`) वाचून वापरलं आहे.
हा मॉड्यूल फक्त levels *मोजतो* (काहीही order करत नाही, DB/network ला हात लावत नाही) — पहिल्या टप्प्यात फक्त चार्टवर
दाखवण्यासाठी (page_sr_levels_v3.py). पडताळणीनंतरच paper, मग live.

सुधारणा (वापरकर्त्याने मान्य केलेल्या):
  A. Recency — ताजे pivots जास्त वजनाचे (exponential decay, half-life दिवसांत).
  B. Reaction strength — pivot नंतर किंमत ATR च्या किती पट उलटली (खरा sell-off / खरेदी कुठून आली).
  C. MTF confluence — 5M/15M/30M/1H मधले जवळचे pivots एका झोनमध्ये; जास्त वेगळे TF = जास्त गुण (मोठा TF जास्त महत्त्वाचा).
     एकच swing अनेक TF मध्ये दिसतो म्हणून touches सर्व TF मिळून बेरीज होत नाहीत (सर्वात जास्त असलेला TF घेतला जातो).
  D. Key levels — मागचा दिवस High/Low/Close (PDH/PDL/PDC) आणि मागचा आठवडा High/Low (PWH/PWL).
  E. Role reversal — resistance तुटून वरती टिकला (आता support) / उलट; retest झाला का ते सुद्धा.
  F. Gaps — न भरलेले (किंवा अर्धवट भरलेले) overnight gaps झोन म्हणून.
  G. एकत्रित Level Score (0-100) + ग्रेड (A/B/C). हा क्रमवारीचा (ranking) गुण आहे, नफ्याची संभाव्यता नव्हे.

इनपुट: {timeframe: DataFrame} — "5minute", "15minute", "30minute", "1hour"; प्रत्येकात timestamp/open/high/low/close
(volume ऐच्छिक). इनपुट DataFrames कधीच बदलले जात नाहीत.
"""
import datetime
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from sr_dynamic import find_pivots_indexed

TF_ORDER = ("5minute", "15minute", "30minute", "1hour")
TF_SHORT = {"5minute": "5M", "15minute": "15M", "30minute": "30M", "1hour": "1H"}

KEY_LEVEL_POINTS = {"PDH": 30.0, "PDL": 30.0, "PDC": 15.0, "PWH": 35.0, "PWL": 35.0}


@dataclass
class SRConfig:
    # TF-नुसार pivot window (दोन्ही बाजूला किती candles) आणि किती दिवसांचे pivots विचारात घ्यायचे
    prd: dict = field(default_factory=lambda: {"5minute": 10, "15minute": 10, "30minute": 10, "1hour": 10})
    lookback_days: dict = field(default_factory=lambda: {"5minute": 3, "15minute": 5, "30minute": 8, "1hour": 10})
    # मोठ्या TF चा pivot जास्त वजनाचा (touches साठी) आणि confluence मध्ये जास्त गुण
    tf_factor: dict = field(default_factory=lambda: {"5minute": 0.6, "15minute": 1.0, "30minute": 1.4, "1hour": 2.0})
    tf_confluence_points: dict = field(default_factory=lambda: {"5minute": 3.0, "15minute": 5.0, "30minute": 7.0, "1hour": 10.0})
    recency_half_life_days: float = 2.5
    atr_period: int = 14
    reaction_atr_full: float = 3.0        # इतक्या ATR ची उलटी चाल = reaction चे पूर्ण गुण
    # झोन बनवण्याची tolerance = tol_atr_mult × (15M) ATR, किंमतीच्या [tol_min_pct, tol_max_pct]% मध्ये बांधलेली
    tol_atr_mult: float = 0.5
    tol_min_pct: float = 0.08
    tol_max_pct: float = 0.40
    # गुणांचे कमाल मूल्य
    w_touch: float = 30.0
    touch_full: float = 3.0
    w_reaction: float = 20.0
    w_confluence_cap: float = 25.0
    w_key_cap: float = 40.0
    w_polarity: float = 5.0
    w_flip: float = 10.0
    w_retest: float = 5.0
    w_gap: float = 10.0
    # 🎓 V3.1: Rejections (level जवळ किंमत नाकारली गेली) — गुण आणि मोजणीचे नियम
    w_reject: float = 10.0
    reject_full: float = 4.0              # (rejections + 0.5×strong) इतके = पूर्ण गुण
    reject_band_frac: float = 0.5         # touch-band = हा अंश × tolerance
    reject_depart_atr: float = 0.5        # swing नंतर किंमत band + इतक्या ATR दूर गेल्यावरच परत येणारे touches मोजायचे
    reject_follow_atr: float = 1.0        # नाकारल्यानंतर इतक्या ATR ची चाल = "strong"
    reject_follow_bars: int = 4
    key_anchor_score: float = 1.5         # PDH/PDL/PWH/PWL ला रेषेचा anchor बनण्याचा प्राधान्य-गुण (ताज्या 1H pivot=2.0, 15M=1.0)
    # Flip (acceptance ratio)
    flip_accept_ratio: float = 0.6
    flip_min_beyond: int = 2
    flip_band_frac: float = 0.5           # flip चा "पलीकडे" = level ± (हा अंश × tolerance)
    # ZONE भूमिका: किंमत झोनच्या इतक्या जवळ (pts) असेल तर "झोनमध्ये"
    zone_touch_pts: float = 5.0
    zone_touch_tol_frac: float = 0.15
    # Gaps
    gap_min_pct: float = 0.20
    gap_max_age_days: int = 10
    # Role reversal
    break_buffer_pct: float = 0.10
    break_confirm_bars: int = 2
    flip_frame: str = "15minute"
    # दाखवण्यासाठी
    grade_a: float = 65.0
    grade_b: float = 45.0
    min_score: float = 25.0
    max_levels: int = 12
    max_distance_pct: float = 3.0
    # सत्र कधी संपतं ("मागचा दिवस" ठरवण्यासाठी) — NSE 15:15 (डीफॉल्ट); MCX साठी "23:30" (बघा mcx_futures_trader.py)
    session_end: str = "15:15"


# ---------------------------------------------------------------------------------------------------------------------
# तयारी / मदतनीस
# ---------------------------------------------------------------------------------------------------------------------
def _prep(df):
    """DataFrame ची स्वच्छ प्रत: timestamp naive-IST, कालानुक्रमे, OHLC मध्ये NaN नाही. आवश्यक columns नसतील तर रिकामा."""
    cols = ["timestamp", "open", "high", "low", "close"]
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or any(c not in df.columns for c in cols):
        return pd.DataFrame(columns=cols)
    out = df[cols].copy()
    ts = pd.to_datetime(out["timestamp"], errors="coerce")
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    out["timestamp"] = ts
    for c in cols[1:]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna().sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    return out


def compute_atr(df, period=14):
    """साधा ATR (True Range ची सरासरी, शेवटच्या `period` candles). डेटा अपुरा/रिकामा => 0.0."""
    if df is None or len(df) < 2:
        return 0.0
    high, low, close = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1).dropna()
    if tr.empty:
        return 0.0
    value = tr.tail(int(period)).mean()
    return float(value) if np.isfinite(value) else 0.0


def recency_weight(age_days, half_life_days):
    """(A) ताजेपणा: आज = 1.0, half-life दिवसांनंतर = 0.5, त्यानंतर आणखी निम्मा... (age<0 => 1.0)."""
    if half_life_days <= 0:
        return 1.0
    return float(0.5 ** (max(float(age_days), 0.0) / float(half_life_days)))


def _clamp(value, low, high):
    return max(low, min(high, value))


# ---------------------------------------------------------------------------------------------------------------------
# A + B: pivots (recency + reaction)
# ---------------------------------------------------------------------------------------------------------------------
def extract_pivots(df, tf, cfg, now):
    """एका TF चे (cfg.lookback_days मधले) पुष्टी झालेले pivots. प्रत्येकासोबत recency weight व reaction (0..1).

    pivot ची पुष्टी `prd` candles नंतर होते (jुन्या sr_dynamic प्रमाणेच) — त्यामुळे शेवटच्या `prd` candles मध्ये pivot नसतो,
    आणि पुष्टी झालेला pivot नंतर बदलत नाही (repaint नाही). reaction फक्त pivot नंतरच्या (2×prd) candles मधून मोजतो."""
    prd = int(cfg.prd.get(tf, 10))
    if df is None or len(df) < 2 * prd + 5:
        return []
    highs, lows = df["high"].values, df["low"].values
    atr = compute_atr(df, cfg.atr_period)
    cutoff = now - pd.Timedelta(days=float(cfg.lookback_days.get(tf, 5)))
    out = []
    for idx, value in find_pivots_indexed(df, prd):
        ts = df["timestamp"].iloc[idx]
        if ts < cutoff:
            continue
        is_high = value == highs[idx]
        n_after = min(2 * prd, len(df) - 1 - idx)
        reaction, reaction_raw = 0.0, 0.0
        if n_after > 0 and atr > 0:
            if is_high:
                move = float(value) - float(lows[idx + 1: idx + 1 + n_after].min())
            else:
                move = float(highs[idx + 1: idx + 1 + n_after].max()) - float(value)
            reaction_raw = max(move / atr / cfg.reaction_atr_full, 0.0)       # cap न केलेला — रेषेचा anchor ठरवताना मोठी चाल जास्त निर्णायक
            reaction = _clamp(reaction_raw, 0.0, 1.0)
        age_days = (now - ts).total_seconds() / 86400.0
        out.append({
            "price": float(value), "kind": "H" if is_high else "L", "ts": ts, "tf": tf,
            "weight": recency_weight(age_days, cfg.recency_half_life_days), "reaction": float(reaction),
            "reaction_raw": float(reaction_raw),
        })
    return out


# ---------------------------------------------------------------------------------------------------------------------
# D: key levels (मागचा दिवस / आठवडा)
# ---------------------------------------------------------------------------------------------------------------------
def _daily_from_intraday(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "high", "low", "close"])
    d = df.assign(date=df["timestamp"].dt.date)
    return d.groupby("date").agg(high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index()


def session_reference_date(now, session_end="15:15"):
    """"मागचा दिवस" कोणत्या दिवसाच्या सापेक्ष मोजायचा. सत्र चालू असताना = आजची तारीख. शेवटचा candle सत्राच्या अखेरचा (15:15 किंवा
    नंतर) असेल (बाजार बंद / रात्र / सकाळपूर्वी), तर *पुढच्या* trading दिवसाची तारीख (शनिवार-रविवार वगळून) — म्हणजे बाजार बंद
    झाल्यावर किंवा पुढच्या सकाळी बघितलं तरी PDH/PDL = नुकताच संपलेला दिवस, आणि शुक्रवारनंतर PWH/PWL = नुकताच संपलेला आठवडा."""
    ref = now.date()
    end_h, end_m = (int(x) for x in str(session_end).split(":"))
    if now.time() >= datetime.time(end_h, end_m):
        ref += datetime.timedelta(days=1)
        while ref.weekday() >= 5:
            ref += datetime.timedelta(days=1)
    return ref


def compute_key_levels(daily_df, fallback_df, now_date):
    """PDH/PDL/PDC (now_date आधीचा शेवटचा trading दिवस) आणि PWH/PWL (मागचा संपूर्ण आठवडा, सोम-रवि).
    daily_df नसेल/अपुरा असेल तर fallback_df (intraday) वरून दिवस-निहाय गट. रिटर्न: [{"name","price"}, ...]."""
    daily = _prep(daily_df)
    daily = _daily_from_intraday(daily) if len(daily) else pd.DataFrame(columns=["date", "high", "low", "close"])
    intraday_daily = _daily_from_intraday(fallback_df)
    # दोन्ही असतील तर daily ला प्राधान्य, पण त्यात नसलेले दिवस intraday वरून भरतात
    if len(daily) and len(intraday_daily):
        missing = intraday_daily[~intraday_daily["date"].isin(daily["date"])]
        daily = pd.concat([daily, missing], ignore_index=True)
    elif len(intraday_daily):
        daily = intraday_daily
    if daily.empty:
        return []
    daily = daily.sort_values("date").reset_index(drop=True)
    levels = []
    prev_days = daily[daily["date"] < now_date]
    if not prev_days.empty:
        last = prev_days.iloc[-1]
        levels += [{"name": "PDH", "price": float(last["high"])}, {"name": "PDL", "price": float(last["low"])},
                   {"name": "PDC", "price": float(last["close"])}]
    week_start = now_date - pd.Timedelta(days=now_date.weekday()).to_pytimedelta()
    prev_week_start = week_start - pd.Timedelta(days=7).to_pytimedelta()
    prev_week = daily[(daily["date"] >= prev_week_start) & (daily["date"] < week_start)]
    if not prev_week.empty:
        levels += [{"name": "PWH", "price": float(prev_week["high"].max())}, {"name": "PWL", "price": float(prev_week["low"].min())}]
    return levels


# ---------------------------------------------------------------------------------------------------------------------
# F: gaps
# ---------------------------------------------------------------------------------------------------------------------
def find_unfilled_gaps(df, min_gap_pct=0.20, max_age_days=10, now=None):
    """खरा overnight gap (मागच्या दिवसाचा शेवटचा candle आणि नवीन दिवसाचा पहिला candle यांच्यात overlap नसलेली रिकामी जागा),
    जो अजून पूर्णपणे भरलेला नाही. अर्धवट भरला असेल तर उरलेला भागच झोन. रिटर्न: [{"kind": "UP_GAP"/"DOWN_GAP",
    "low","high","date","fill_pct"}, ...]."""
    if df is None or len(df) < 2:
        return []
    now = now if now is not None else df["timestamp"].iloc[-1]
    work = df.assign(_date=df["timestamp"].dt.date)
    dates = sorted(work["_date"].unique())
    out = []
    for i in range(1, len(dates)):
        prev_rows = work[work["_date"] == dates[i - 1]]
        next_rows = work[work["_date"] == dates[i]]
        if prev_rows.empty or next_rows.empty:
            continue
        if (now - pd.Timestamp(dates[i])).days > max_age_days:
            continue
        prev_last, first = prev_rows.iloc[-1], next_rows.iloc[0]
        if first["low"] > prev_last["high"]:
            kind, g_low, g_high = "UP_GAP", float(prev_last["high"]), float(first["low"])
        elif first["high"] < prev_last["low"]:
            kind, g_low, g_high = "DOWN_GAP", float(first["high"]), float(prev_last["low"])
        else:
            continue
        if (g_high - g_low) < g_low * min_gap_pct / 100.0:
            continue
        since = work[work["timestamp"] >= first["timestamp"]]
        original = g_high - g_low
        if kind == "UP_GAP":
            deepest = float(since["low"].min())
            if deepest <= g_low:
                continue                                  # पूर्ण भरला
            if deepest < g_high:
                g_high = deepest                          # अर्धवट भरला — उरलेला भाग
        else:
            highest = float(since["high"].max())
            if highest >= g_high:
                continue
            if highest > g_low:
                g_low = highest
        out.append({"kind": kind, "low": g_low, "high": g_high, "date": dates[i],
                    "fill_pct": round(100.0 * (1 - (g_high - g_low) / original), 1)})
    return out


# ---------------------------------------------------------------------------------------------------------------------
# E: role reversal
# ---------------------------------------------------------------------------------------------------------------------
def detect_role_reversal(zone_low, zone_high, origin, df, since_ts, buffer_pct=0.10, confirm_bars=2):
    """origin 'R' = झोन आधी resistance होता (वरून रोखलेला), 'S' = support. `since_ts` नंतर `confirm_bars` सलग candle-close
    झोनच्या पलीकडे (buffer% सह) बंद झाले आणि किंमत अजूनही झोनच्या पलीकडच्या बाजूला टिकलेली असेल तर flipped. त्यानंतर किंमत
    झोनमध्ये परत येऊन तिथेच टिकली (retest) तर retested. रिटर्न: {"flipped": bool, "retested": bool}."""
    none = {"flipped": False, "retested": False}
    if origin not in ("R", "S") or df is None or df.empty:
        return none
    after = df[df["timestamp"] > since_ts]
    n = len(after)
    confirm_bars = max(int(confirm_bars), 1)
    if n < confirm_bars:
        return none
    close, high, low = after["close"].values, after["high"].values, after["low"].values
    buf = buffer_pct / 100.0
    beyond = close > zone_high * (1 + buf) if origin == "R" else close < zone_low * (1 - buf)
    confirmed_at = None
    run = 0
    for i in range(n):
        run = run + 1 if beyond[i] else 0
        if run >= confirm_bars:
            confirmed_at = i
            break
    if confirmed_at is None:
        return none
    still_holding = close[-1] >= zone_low if origin == "R" else close[-1] <= zone_high
    if not still_holding:
        return none
    retested = False
    for j in range(confirmed_at + 1, n):
        if origin == "R" and low[j] <= zone_high and close[j] >= zone_low:
            retested = True
            break
        if origin == "S" and high[j] >= zone_low and close[j] <= zone_high:
            retested = True
            break
    return {"flipped": True, "retested": retested}


def detect_flip_acceptance(level, band, origin, df, since_ts, min_ratio=0.6, min_beyond=2):
    """V3.1 — "स्वीकृती गुणोत्तर" (acceptance ratio) वर आधारित role reversal. जुन्या `detect_role_reversal` (सलग N closes) ऐवजी
    गडबडीचा (choppy) breakdown/breakout सुद्धा पकडतो: पहिल्या "पलीकडच्या" close पासून आतापर्यंतच्या closes पैकी ≥ `min_ratio`
    (60%) level च्या पलीकडे (level ± band) बंद झालेले असावेत, किमान `min_beyond` असे closes, आणि शेवटचा close अजूनही
    पलीकडच्या बाजूला (किंवा band मध्ये) टिकलेला. `origin` 'R'/'S' (मूळ भूमिका). रिटर्न: flipped, retested, accept_ratio."""
    none = {"flipped": False, "retested": False, "accept_ratio": 0.0}
    if origin not in ("R", "S") or df is None or df.empty or since_ts is None:
        return none
    after = df[df["timestamp"] > since_ts]
    if after.empty:
        return none
    close, high, low = after["close"].values, after["high"].values, after["low"].values
    beyond = close > level + band if origin == "R" else close < level - band
    if not beyond.any():
        return none
    first = int(np.argmax(beyond))
    seg = beyond[first:]
    ratio = float(seg.mean())
    result = {"flipped": False, "retested": False, "accept_ratio": round(ratio, 2)}
    if int(seg.sum()) < max(int(min_beyond), 1) or ratio < min_ratio:
        return result
    holding = close[-1] > level - band if origin == "R" else close[-1] < level + band
    if not holding:
        return result
    result["flipped"] = True
    for j in range(first + 1, len(close)):
        if origin == "R" and low[j] <= level + band and close[j] >= level - band:
            result["retested"] = True
            break
        if origin == "S" and high[j] >= level - band and close[j] <= level + band:
            result["retested"] = True
            break
    return result


def count_rejections(df, level, band, since_ts, atr, cfg):
    """V3.1 — `since_ts` नंतर किंमत level (± band) ला स्पर्श करून **नाकारली गेली** अशा वेगळ्या घटनांची संख्या.
    Resistance-नाकार: bar चा high ≥ level−band, close ≤ level−band, open ≤ level+band (वरून उघडला नाही).
    Support-नाकार: उलट. सलग qualifying bars = एकच घटना. swing नंतर किंमत आधी band + 0.5 ATR दूर गेली पाहिजे (swing चा स्वतःचा
    लगेचचा उलटा bar नाकार मोजला जात नाही). नाकारल्यानंतर `reject_follow_bars` bars मध्ये ≥ `reject_follow_atr` ATR ची चाल = strong.
    रिटर्न: {"count", "strong"}."""
    out = {"count": 0, "strong": 0}
    if df is None or df.empty or since_ts is None or band <= 0:
        return out
    after = df[df["timestamp"] > since_ts]
    if after.empty:
        return out
    o, h, l, c = (after[k].values for k in ("open", "high", "low", "close"))
    depart = band + cfg.reject_depart_atr * max(atr, 0.0)
    departed, prev_hit, n = False, False, len(after)
    for i in range(n):
        if not departed:
            departed = abs(c[i] - level) >= depart
            prev_hit = False
            continue
        r_rej = h[i] >= level - band and c[i] <= level - band and o[i] <= level + band
        s_rej = l[i] <= level + band and c[i] >= level + band and o[i] >= level - band
        hit = bool(r_rej or s_rej)
        if hit and not prev_hit:
            out["count"] += 1
            window = slice(i + 1, i + 1 + int(cfg.reject_follow_bars))
            if atr > 0 and window.start < n:
                if r_rej and float(l[window].min()) <= level - cfg.reject_follow_atr * atr:
                    out["strong"] += 1
                elif s_rej and float(h[window].max()) >= level + cfg.reject_follow_atr * atr:
                    out["strong"] += 1
        prev_hit = hit
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Clustering + scoring
# ---------------------------------------------------------------------------------------------------------------------
def cluster_items(items, tol):
    """किंमतीनुसार क्रमवार गट; गटाची रुंदी (max-min) 2×tol पेक्षा जास्त वाढू देत नाही (साखळी-जोडणी होऊन सर्व एक झोन होऊ नये)."""
    clusters, current = [], []
    for item in sorted(items, key=lambda it: it["price"]):
        if current and item["price"] - current[0]["price"] > 2.0 * tol:
            clusters.append(current)
            current = []
        current.append(item)
    if current:
        clusters.append(current)
    return clusters


def _pivot_anchor_score(p, cfg):
    """रेषा कुठल्या pivot वर ठेवायची त्याचा निर्णायकपणा = TF-वजन × (0.5 + 0.5×reaction). 🎓 ताजेपणा (recency) इथे जाणीवपूर्वक वापरलेला
    नाही — तो फक्त Score ठरवतो. कारण: level "जिथे जन्मली" तो मूळ swing; नंतरचे pivots त्याचेच retests/टप्पे असतात."""
    raw = _clamp(p.get("reaction_raw", p["reaction"]), 0.0, 3.0)         # 3× पूर्ण-reaction (≈ 9 ATR) पर्यंत चाल जास्त निर्णायक
    return cfg.tf_factor.get(p["tf"], 1.0) * (0.5 + 0.5 * raw)


def _ts_key(ts):
    try:
        return -pd.Timestamp(ts).value if ts is not None else 0
    except (TypeError, ValueError):
        return 0


def _pick_anchor(members, cfg):
    """V3.1 — झोनची रेषा सरासरीवर नाही, सर्वात निर्णायक एका swing/key level च्या **अचूक** किंमतीवर. बरोबरीत मोठा TF, मग **सर्वात जुना**
    (मूळ swing). PDH/PDL/PWH/PWL चा स्वतःचा प्राधान्य-गुण `key_anchor_score`."""
    best, best_key = None, None
    for m in members:
        if m["kind"] in ("H", "L"):
            key = (_pivot_anchor_score(m, cfg), cfg.tf_factor.get(m["tf"], 1.0), _ts_key(m.get("ts")))
        else:
            key = (cfg.key_anchor_score, 99.0, 0)
        if best_key is None or key > best_key:
            best, best_key = m, key
    return best


def _build_zone(members, cfg, tol=None):
    pivots = [m for m in members if m["kind"] in ("H", "L")]
    keys = [m for m in members if m["kind"] == "KEY"]
    key_names = sorted({k["name"] for k in keys})
    prices = [m["price"] for m in members]
    weights = [m["weight"] * cfg.tf_factor.get(m["tf"], 1.0) if m["kind"] in ("H", "L") else 3.0 for m in members]
    mid = float(np.average(prices, weights=weights)) if sum(weights) > 0 else float(np.mean(prices))
    per_tf = {}
    for p in pivots:
        per_tf.setdefault(p["tf"], []).append(p)
    # (C) एकच swing अनेक TF मध्ये दिसतो — म्हणून touches TF-निहाय मोजून सर्वात जास्त TF घेतला, बेरीज नाही
    touches_raw = max((sum(p["weight"] for p in ps) * cfg.tf_factor.get(tf, 1.0) for tf, ps in per_tf.items()), default=0.0)
    best_tf = max(per_tf, key=lambda tf: sum(p["weight"] for p in per_tf[tf]) * cfg.tf_factor.get(tf, 1.0)) if per_tf else None
    n_high = sum(1 for p in pivots if p["kind"] == "H")
    n_low = sum(1 for p in pivots if p["kind"] == "L")
    anchor = _pick_anchor(members, cfg)
    level = float(anchor["price"]) if anchor is not None else mid
    if tol:
        core_prices = [p for p in prices if abs(p - level) <= 0.5 * tol] or [level]
    else:
        core_prices = prices
    if anchor is not None and anchor["kind"] in ("H", "L"):
        origin = "R" if anchor["kind"] == "H" else "S"
    else:
        origin = "R" if n_high > n_low else "S" if n_low > n_high else None
    return {
        "low": float(min(prices)), "high": float(max(prices)), "mid": mid, "level": level,
        "core_low": float(min(core_prices)), "core_high": float(max(core_prices)),
        "anchor": None if anchor is None else {"price": float(anchor["price"]), "tf": anchor.get("tf"), "kind": anchor["kind"],
                                               "ts": anchor.get("ts"), "name": anchor.get("name")},
        "origin": origin, "rejections": 0, "rej_strong": 0, "accept_ratio": 0.0,
        "tfs": [tf for tf in TF_ORDER if tf in per_tf],
        "pivot_count": len(per_tf[best_tf]) if best_tf else 0,
        "n_high": n_high, "n_low": n_low,
        "touches_raw": float(touches_raw),
        "reaction": max((p["reaction"] * (0.5 + 0.5 * p["weight"]) for p in pivots), default=0.0),
        "keys": key_names,
        "gap": None, "flipped": False, "retested": False,
        "polarity": n_high >= 1 and n_low >= 1,
        "last_pivot_ts": max((p["ts"] for p in pivots), default=None),
    }


def _score_zone(zone, cfg):
    comp = {
        "touches": cfg.w_touch * _clamp(zone["touches_raw"] / cfg.touch_full, 0.0, 1.0),
        "reaction": cfg.w_reaction * _clamp(zone["reaction"], 0.0, 1.0),
        "confluence": min(sum(cfg.tf_confluence_points.get(tf, 0.0) for tf in zone["tfs"]), cfg.w_confluence_cap),
        "key_level": min(sum(KEY_LEVEL_POINTS.get(k, 0.0) for k in zone["keys"]), cfg.w_key_cap),
        "polarity": cfg.w_polarity if zone["polarity"] else 0.0,
        "role_reversal": (cfg.w_flip if zone["flipped"] else 0.0) + (cfg.w_retest if zone["flipped"] and zone["retested"] else 0.0),
        "gap": cfg.w_gap if zone["gap"] else 0.0,
        "rejections": cfg.w_reject * _clamp((zone.get("rejections", 0) + 0.5 * zone.get("rej_strong", 0)) / cfg.reject_full, 0.0, 1.0),
    }
    if zone["gap"] and not zone["tfs"] and not zone["keys"]:
        comp["gap"] = 30.0                                  # स्वतंत्र gap झोनचा पाया (इतर कुठलाच आधार नाही)
    score = _clamp(sum(comp.values()), 0.0, 100.0)
    zone["components"] = {k: round(v, 1) for k, v in comp.items()}
    zone["score"] = round(score, 1)
    zone["grade"] = "A" if score >= cfg.grade_a else "B" if score >= cfg.grade_b else "C"


def _tags(zone):
    tags = [TF_SHORT[tf] for tf in zone["tfs"]] + list(zone["keys"])
    if zone["gap"]:
        tags.append("GAP↑" if zone["gap"]["kind"] == "UP_GAP" else "GAP↓")
    if zone["flipped"]:
        tags.append("FLIP✓" if zone["retested"] else "FLIP")
    if zone.get("rejections", 0) >= 2:
        tags.append(f"REJ×{zone['rejections']}")
    if zone["polarity"] and not zone["flipped"]:
        tags.append("दोन्ही-बाजू")
    return tags


# ---------------------------------------------------------------------------------------------------------------------
# मुख्य फंक्शन
# ---------------------------------------------------------------------------------------------------------------------
def compute_sr_v3(frames, daily_df=None, current_price=None, cfg=None):
    """सर्व स्रोत एकत्र करून गुणांकित levels. रिटर्न: {"levels": [...score उतरत्या क्रमाने...], "meta": {...}}.

    प्रत्येक level: level (चार्टवर रेषा), low/high (झोन), role ("SUPPORT"/"RESISTANCE"/"ZONE" — सध्याच्या किंमतीच्या सापेक्ष),
    score, grade, tags, tfs, pivot_count, components (गुणांचे तपशील), distance_pct (किंमतीपासून %, वर = +).
    डेटा अपुरा असेल तर रिकामी यादी (कधीच exception नाही)."""
    cfg = cfg or SRConfig()
    prepared = {tf: _prep(df) for tf, df in (frames or {}).items() if tf in TF_ORDER}
    prepared = {tf: df for tf, df in prepared.items() if not df.empty}
    empty = {"levels": [], "meta": {"frames": sorted(prepared), "reason": "डेटा उपलब्ध नाही"}}
    if not prepared:
        return empty

    now = max(df["timestamp"].iloc[-1] for df in prepared.values())
    finest = next(tf for tf in TF_ORDER if tf in prepared)
    try:
        price = float(current_price)
        valid_price = np.isfinite(price) and price > 0
    except (TypeError, ValueError):
        valid_price = False
    if not valid_price:
        price = float(prepared[finest]["close"].iloc[-1])

    ref_tf = "15minute" if "15minute" in prepared else finest
    atr_ref = compute_atr(prepared[ref_tf], cfg.atr_period)
    tol = _clamp(cfg.tol_atr_mult * atr_ref, price * cfg.tol_min_pct / 100.0, price * cfg.tol_max_pct / 100.0)

    items = []
    for tf, df in prepared.items():
        items += extract_pivots(df, tf, cfg, now)
    key_source = prepared.get("15minute", prepared[finest])
    for key in compute_key_levels(daily_df, key_source, session_reference_date(now, cfg.session_end)):
        items.append({"price": key["price"], "kind": "KEY", "name": key["name"], "tf": None, "weight": 1.0})
    zones = [_build_zone(c, cfg, tol) for c in cluster_items(items, tol)] if items else []

    flip_df = prepared.get(cfg.flip_frame, prepared[finest])
    flip_atr = compute_atr(flip_df, cfg.atr_period)
    band = cfg.flip_band_frac * tol
    for z in zones:
        anchor = z["anchor"]
        since = anchor["ts"] if anchor and anchor.get("ts") is not None else z["last_pivot_ts"]
        if since is None or z["origin"] is None:
            continue
        verdict = detect_flip_acceptance(z["level"], band, z["origin"], flip_df, since, cfg.flip_accept_ratio, cfg.flip_min_beyond)
        z["flipped"], z["retested"], z["accept_ratio"] = verdict["flipped"], verdict["retested"], verdict["accept_ratio"]
        rej = count_rejections(flip_df, z["level"], cfg.reject_band_frac * tol, since, flip_atr, cfg)
        z["rejections"], z["rej_strong"] = rej["count"], rej["strong"]

    gap_source = prepared.get("15minute", prepared[finest])
    for gap in find_unfilled_gaps(gap_source, cfg.gap_min_pct, cfg.gap_max_age_days, now):
        # gap ची किनार (भरताना जिथे किंमत प्रतिक्रिया देते) ज्या झोनच्या tolerance मध्ये आहे फक्त तोच झोन gap शी जोडला जातो —
        # मोठ्या gap च्या आतून जाणाऱ्या कुठल्याही झोनशी नाही
        overlapping = [z for z in zones
                       if any(z["low"] - tol <= edge <= z["high"] + tol for edge in (gap["low"], gap["high"]))]
        if overlapping:
            for z in zones:
                _score_zone(z, cfg)
            target = max(overlapping, key=lambda z: z["score"])
            if target["gap"] is None:
                target["gap"] = gap
            continue
        near_edge = gap["high"] if gap["kind"] == "UP_GAP" else gap["low"]
        in_gap = gap["low"] <= price <= gap["high"]
        zones.append({
            "low": gap["low"], "high": gap["high"], "mid": (gap["low"] + gap["high"]) / 2.0,
            "level": (gap["low"] + gap["high"]) / 2.0 if in_gap else near_edge,
            "tfs": [], "pivot_count": 0, "n_high": 0, "n_low": 0, "touches_raw": 0.0, "reaction": 0.0,
            "keys": [], "gap": gap, "flipped": False, "retested": False, "polarity": False, "last_pivot_ts": None,
            "core_low": gap["low"], "core_high": gap["high"], "anchor": None, "origin": None,
            "rejections": 0, "rej_strong": 0, "accept_ratio": 0.0,
        })

    levels = []
    for z in zones:
        _score_zone(z, cfg)
        zt = min(max(cfg.zone_touch_pts, cfg.zone_touch_tol_frac * tol), tol)       # किंमत झोनच्या ~५ pts आत = "झोनमध्ये"
        z["role"] = "RESISTANCE" if price < z["low"] - zt else "SUPPORT" if price > z["high"] + zt else "ZONE"
        z["distance_pct"] = round((z["level"] - price) / price * 100.0, 2)
        z["tags"] = _tags(z)
        z["gap_kind"] = z["gap"]["kind"] if z["gap"] else None
        z.pop("last_pivot_ts", None)
        levels.append(z)
    levels.sort(key=lambda z: (-z["score"], abs(z["distance_pct"])))
    return {"levels": levels, "meta": {
        "frames": sorted(prepared, key=TF_ORDER.index), "price": price, "now": now, "tol": round(tol, 2),
        "atr_ref": round(atr_ref, 2), "ref_tf": ref_tf, "pivot_count": sum(1 for i in items if i["kind"] in ("H", "L")),
    }}


# ---------------------------------------------------------------------------------------------------------------------
# दाखवण्यासाठी
# ---------------------------------------------------------------------------------------------------------------------
def select_display_levels(levels, price, cfg=None):
    """min_score आणि max_distance_pct मधले, सर्वाधिक गुणाचे max_levels. किंमतीच्या वर/खाली सर्वात जवळची (पात्र) level नेहमी समाविष्ट."""
    cfg = cfg or SRConfig()
    eligible = [z for z in levels if z["score"] >= cfg.min_score and abs(z["distance_pct"]) <= cfg.max_distance_pct]
    chosen = eligible[:max(int(cfg.max_levels), 0)]
    for side in ("RESISTANCE", "SUPPORT"):
        pool = [z for z in eligible if z["role"] == side]
        if pool and not any(z["role"] == side for z in chosen):
            chosen.append(min(pool, key=lambda z: abs(z["distance_pct"])))
    return sorted(chosen, key=lambda z: -z["level"])


_ROLE_COLORS = {
    "SUPPORT": {"A": "#00c853", "B": "#26a69a", "C": "#81c784"},
    "RESISTANCE": {"A": "#ff1744", "B": "#ef5350", "C": "#e57373"},
    "ZONE": {"A": "#ffa726", "B": "#ffb74d", "C": "#ffcc80"},
}


def to_chart_lines(levels, edge_max_distance_pct=1.0):
    """select_display_levels() ची यादी -> tradingview_chart.build_lightweight_chart_html(trade_lines=...) चा फॉरमॅट.
    V3.1: मुख्य रेषा = अचूक swing किंमत. A/B ग्रेडच्या, किंमतीजवळच्या (≤ edge_max_distance_pct%) झोनची दुसरी (outer) किनार
    बारीक ठिपक्यांच्या रेषेत — म्हणजे "किंमत नेमकी रेषेवर आली नाही तरी झोनमध्ये आली" ते दिसतं."""
    lines = []
    for z in levels:
        letter = {"SUPPORT": "S", "RESISTANCE": "R"}.get(z["role"], "Z")
        tags = "+".join(z["tags"][:4])
        lines.append({
            "price": z["level"], "title": f"{letter} {z['grade']}{int(round(z['score']))} {tags}".strip(),
            "color": _ROLE_COLORS[z["role"]][z["grade"]], "dashed": z["grade"] == "C" or bool(z["gap"] and not z["tfs"]),
            # 🎓 वापरकर्त्याची मागणी: resistance लाल, support हिरवी -- ठिपक्यांची रेषा (ग्रेड जाडीतून दिसतो; ZONE नारिंगी तशीच)
            "dotted": z["role"] in ("SUPPORT", "RESISTANCE"),
            "width": {"A": 3, "B": 2, "C": 1}[z["grade"]],
        })
        if z["grade"] in ("A", "B") and abs(z.get("distance_pct", 0.0)) <= edge_max_distance_pct and not (z["gap"] and not z["tfs"]):
            edge = z["high"] if abs(z["high"] - z["level"]) >= abs(z["low"] - z["level"]) else z["low"]
            if abs(edge - z["level"]) >= z["level"] * 0.0002:          # ≥ ~5 pts (NIFTY) — नाहीतर रेषा एकमेकांवर येतात
                lines.append({"price": edge, "title": f"{letter} {z['grade']}{int(round(z['score']))} ↔ झोन किनार", "color": _ROLE_COLORS[z["role"]][z["grade"]],
                              "dashed": True, "width": 1})
    return lines
