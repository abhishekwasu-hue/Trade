"""
price_action/candles.py
-------------------------
🎓 वापरकर्त्याची "अंतिम, LOGIC-BASED" candle confirmation रचना (pattern-नावांवर आधारित नियम नकोत):
level ला लागून किंमत खरंच **नाकारली गेली** का हे शेवटच्या N = 1, 2, 3 पूर्ण candles च्या **composite** candle वरून
(open = पहिल्याचा, high = max, low = min, close = शेवटच्याचा) मोजतो, आणि 0–100 rejection_score देतो.

Bullish (support) अनिवार्य अटी — Bearish साठी तंतोतंत उलट (आरशातली किंमत, बघा `_mirror`):
  a) touch:   low ≤ support × (1 + touch_pct%)
  b) reclaim: close ≥ support
  c) N ≥ 2 ⇒ शेवटची candle दिशेने बंद (close > open)
  d) strength: k × median_range ≤ range ≤ max_range_mult × median_range (median = window आधीच्या 20 पूर्ण candles)
  + indecision: close_loc 0.40–0.60 ⇒ नाही (पुढची candle दिशेने बंद झाली तर N+1 window म्हणून पुन्हा; N=3 ⇒ N=4 फक्त इथेच)
Score: wick 30 + close_loc 20 + bounce 20 (2 × median_range वर पूर्ण) + sweep 15 + speed (N=1 15, N=2 10, N=3 5, N=4 0).
Label ("≈ Hammer" …) फक्त log/chart साठी — निर्णयात कुठलाही वापर नाही.

सर्व functions ना फक्त **पूर्ण** झालेले candles (जुनं ते नवं) द्यायचे — चालू candle वगळणं caller ची जबाबदारी
(`completed_only` मदत करते). window नेहमी सर्वात शेवटच्या पूर्ण candle ला संपते (ताजेपणा).
"""
import pandas as pd

MAX_N = 3
WEIGHTS = {"wick": 30.0, "close_loc": 20.0, "bounce": 20.0, "sweep": 15.0}
SPEED = {1: 15.0, 2: 10.0, 3: 5.0}
BOUNCE_FULL = 2.0
INDECISION = (0.40, 0.60)
MEDIAN_LOOKBACK = 20
MIN_MEDIAN_CANDLES = 10

# skip कारणे (Signal Log मध्ये "SKIPPED_" + हे), आणि कुठली अपयशी window "सर्वात जवळ" होती ते ठरवण्याचा क्रम
NO_DATA, NO_TOUCH, NO_RECLAIM, LAST_AGAINST = "REJECTION_NO_DATA", "REJECTION_NO_TOUCH", "REJECTION_NO_RECLAIM", "REJECTION_LAST_CANDLE_AGAINST"
WEAK, EXHAUSTION, INDECISIVE, LOW_SCORE = "REJECTION_WEAK_CANDLE", "REJECTION_EXHAUSTION", "REJECTION_INDECISION", "REJECTION_SCORE"
_STAGE = {NO_DATA: -1, NO_TOUCH: 0, NO_RECLAIM: 1, LAST_AGAINST: 2, WEAK: 3, EXHAUSTION: 3, INDECISIVE: 4, LOW_SCORE: 5}


def completed_only(df, tf_minutes, now):
    """`now` पर्यंत पूर्ण झालेले candles (timestamp = candle ची सुरुवात; timestamp + tf ≤ now)."""
    if df is None or len(df) == 0:
        return df
    ts = pd.to_datetime(df["timestamp"])
    now_ts = pd.Timestamp(now)
    if getattr(ts.dt, "tz", None) is not None and now_ts.tzinfo is None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    elif getattr(ts.dt, "tz", None) is None and now_ts.tzinfo is not None:
        now_ts = now_ts.tz_convert("Asia/Kolkata").tz_localize(None)
    return df[(ts + pd.Timedelta(minutes=tf_minutes) <= now_ts).to_numpy()].reset_index(drop=True)


def composite(window):
    """N candles (DataFrame) -> एक composite candle."""
    return {"open": float(window["open"].iloc[0]), "high": float(window["high"].max()), "low": float(window["low"].min()),
            "close": float(window["close"].iloc[-1]), "ts_start": pd.Timestamp(window["timestamp"].iloc[0]),
            "ts_end": pd.Timestamp(window["timestamp"].iloc[-1])}


def _mirror(o, h, l, c, level, bullish):
    """bearish ⇒ किंमत उलटी (−x) — मग bullish चेच नियम लागू (high↔low अदलाबदल)."""
    return (o, h, l, c, level) if bullish else (-o, -l, -h, -c, -level)


def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


def _label(n, sweep, bullish):
    if sweep:
        return "≈ Failed Breakdown" if bullish else "≈ Failed Breakout"
    if n == 1:
        return "≈ Hammer" if bullish else "≈ Shooting Star"
    if n == 2:
        return "≈ Bullish Engulfing" if bullish else "≈ Bearish Engulfing"
    return "≈ Morning Star" if bullish else "≈ Evening Star"


def evaluate_window(df, n, level, direction, k=1.2, min_score=60.0, touch_pct=0.10, max_range_mult=2.5,
                    median_lookback=MEDIAN_LOOKBACK):
    """df च्या शेवटच्या `n` पूर्ण candles ची composite window तपासते. रिटर्न dict: ok, reason (None/कारण), n, score, components,
    label, composite, median_range, close_loc."""
    bullish = direction == "BULLISH"
    out = {"ok": False, "reason": NO_DATA, "n": n, "score": 0.0, "components": {}, "label": None, "composite": None,
           "median_range": None, "close_loc": None, "direction": direction, "level": float(level)}
    if df is None or len(df) < n + MIN_MEDIAN_CANDLES:
        return out
    window = df.iloc[len(df) - n:]
    hist = df.iloc[max(0, len(df) - n - median_lookback): len(df) - n]
    med = float((hist["high"] - hist["low"]).median()) if len(hist) >= MIN_MEDIAN_CANDLES else 0.0
    comp = composite(window)
    out.update(composite=comp, median_range=round(med, 6) if med else None)
    if med <= 0:
        return out
    tol = abs(float(level)) * touch_pct / 100.0
    o, h, l, c, lv = _mirror(comp["open"], comp["high"], comp["low"], comp["close"], float(level), bullish)
    rng = h - l
    close_loc = (c - l) / rng if rng > 0 else 0.0
    out["close_loc"] = round(close_loc, 3)
    if not l <= lv + tol:
        out["reason"] = NO_TOUCH
        return out
    if not c >= lv:
        out["reason"] = NO_RECLAIM
        return out
    if n >= 2:
        lo_, lc_ = float(window["open"].iloc[-1]), float(window["close"].iloc[-1])
        if not ((lc_ > lo_) if bullish else (lc_ < lo_)):
            out["reason"] = LAST_AGAINST
            return out
    if rng < k * med:
        out["reason"] = WEAK
        return out
    if rng > max_range_mult * med:
        out["reason"] = EXHAUSTION
        return out
    closes = window["close"].to_numpy(float) * (1 if bullish else -1)
    below = closes < lv
    sweep = bool(below.any() and n >= 2 and any(closes[j] >= lv for j in range(int(below.argmax()) + 1, len(closes))))
    comps = {
        "wick": round(WEIGHTS["wick"] * _clamp01((min(o, c) - l) / rng), 1),
        "close_loc": round(WEIGHTS["close_loc"] * _clamp01(close_loc), 1),
        "bounce": round(WEIGHTS["bounce"] * _clamp01((c - l) / med / BOUNCE_FULL), 1),
        "sweep": WEIGHTS["sweep"] if sweep else 0.0,
        "speed": SPEED.get(n, 0.0),
    }
    score = round(sum(comps.values()), 1)
    out.update(components=comps, score=score, label=_label(n, sweep, bullish), sweep=sweep)
    if INDECISION[0] <= close_loc <= INDECISION[1]:
        out["reason"] = INDECISIVE
        return out
    if score < min_score:
        out["reason"] = LOW_SCORE
        return out
    out.update(ok=True, reason=None)
    return out


def evaluate_rejection(df, level, direction, k=1.2, min_score=60.0, touch_pct=0.10, max_range_mult=2.5, median_lookback=MEDIAN_LOOKBACK):
    """N = 1..3 (आणि indecision follow-through साठी N=4) — पास झालेल्यांपैकी सर्वाधिक score; एकही पास नाही तर "सर्वात जवळची"
    अपयशी window (कारणासह). df = फक्त पूर्ण candles (जुनं ते नवं)."""
    kw = dict(k=k, min_score=min_score, touch_pct=touch_pct, max_range_mult=max_range_mult, median_lookback=median_lookback)
    results = [evaluate_window(df, n, level, direction, **kw) for n in range(1, MAX_N + 1)]
    if df is not None and len(df) >= MAX_N + 2:
        prev = evaluate_window(df.iloc[:-1], MAX_N, level, direction, **kw)
        last_o, last_c = float(df["open"].iloc[-1]), float(df["close"].iloc[-1])
        if prev["reason"] == INDECISIVE and ((last_c > last_o) if direction == "BULLISH" else (last_c < last_o)):
            results.append(evaluate_window(df, MAX_N + 1, level, direction, **kw))
    passed = [r for r in results if r["ok"]]
    if passed:
        return max(passed, key=lambda r: (r["score"], -r["n"]))
    return max(results, key=lambda r: (_STAGE.get(r["reason"], -1), r["score"], -r["n"]))


def structure_sl(result, buffer_pct=0.05):
    """SL = composite low − buffer (bullish) / high + buffer (bearish) — आणि कधीही level च्या चुकीच्या बाजूला नाही
    (bullish SL ≤ level × (1 − buffer); bearish SL ≥ level × (1 + buffer))."""
    comp, lv, b = result["composite"], float(result["level"]), buffer_pct / 100.0
    if result["direction"] == "BULLISH":
        return round(min(comp["low"], lv) * (1 - b), 4)
    return round(max(comp["high"], lv) * (1 + b), 4)


def chase_ok(entry, level, sl, direction, max_frac=0.5):
    """entry चं level पासूनचं (अनुकूल दिशेतलं) अंतर ≤ max_frac × (entry पासून SL अंतर)."""
    entry, level, sl = float(entry), float(level), float(sl)
    if direction == "BULLISH":
        return (entry - level) <= max_frac * (entry - sl)
    return (level - entry) <= max_frac * (sl - entry)


def sl_distance(entry, sl, direction):
    return float(entry) - float(sl) if direction == "BULLISH" else float(sl) - float(entry)


def pullback_price(result):
    """भाग 2: composite candle च्या range चा 50%."""
    comp = result["composite"]
    return round((comp["high"] + comp["low"]) / 2.0, 4)


def describe(result):
    """Signal Log साठी: N, घटक-गुण, score, label."""
    comps = result.get("components") or {}
    parts = " ".join(f"{k}={v:g}" for k, v in comps.items())
    return f"N={result['n']} score={result['score']:g} {result.get('label') or ''} [{parts}]".strip()


def scan_markers(df, levels, k=1.2, min_score=60.0, touch_pct=0.10, max_range_mult=2.5, max_distance_pct=3.0):
    """चार्टसाठी: प्रत्येक पूर्ण candle वर संपणाऱ्या windows पैकी, जवळच्या (`max_distance_pct`) levels वर पास झालेले rejections.
    दिशा = त्या वेळच्या close वरून (close ≥ level ⇒ support/bullish). रिटर्न [(index, {"bullish", "text"})] — एका candle वर एकच (सर्वोत्तम)."""
    markers = []
    if df is None or len(df) < MAX_N + MIN_MEDIAN_CANDLES:
        return markers
    levels = [float(x) for x in levels or []]
    last_end = None
    for i in range(MAX_N + MIN_MEDIAN_CANDLES - 1, len(df)):
        sub = df.iloc[: i + 1]
        close = float(sub["close"].iloc[-1])
        best = None
        for lv in levels:
            if abs(close - lv) / lv * 100 > max_distance_pct:
                continue
            r = evaluate_rejection(sub, lv, "BULLISH" if close >= lv else "BEARISH", k, min_score, touch_pct, max_range_mult)
            if r["ok"] and (best is None or r["score"] > best["score"]):
                best = r
        if best is not None and (last_end is None or best["composite"]["ts_start"] > last_end):   # एकच rejection पुन्हा-पुन्हा नाही
            last_end = best["composite"]["ts_end"]
            markers.append((i, {"bullish": best["direction"] == "BULLISH", "text": f"{best['label'].replace('≈ ', '≈')} {best['score']:.0f}"}))
    return markers
