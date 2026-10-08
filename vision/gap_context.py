"""vision/gap_context.py — opening gap चा संदर्भ (v2.1, signal_check_v2_1). **Causal: फक्त signal पर्यंतचे bars.**

🎓 व्याख्या (TRADE_VISION_V2_1_GAP_LINE §6; पुढच्या gap-module PR मध्ये `price_action/gap_context.py` मध्ये हलवायचा — एकच व्याख्या):
  • PDC / PDH / PDL = आधीचा **पूर्ण** session-दिवस (≥ `MIN_SESSION_BARS` 1m bars — muhurat / special sessions वगळले).
  • Open = आजचा पहिला (09:15) 1m bar चा open — तो bar सुरू झाला की बदलत नाही.
  • gap_atr = (Open − PDC) / ATR14 (daily, आधीचे पूर्ण दिवस). |gap_atr| < `gap_g0_atr` ⇒ G0 (noise). Default 0.25 = IS (2015–2021) p50.
  • Location: Open PDH–PDL च्या आत (inside) की पलीकडे (beyond). Trend (HTF context): आधीच्या पूर्ण दिवसांचे closes — PDC > SMA10 आणि SMA10 वाढतोय ⇒ up
    (उलट ⇒ down), नाहीतर range (range ⇒ "trend सोबत" नाही — सावध).
  • वर्ग: G1 trend विरुद्ध + inside · G2 सोबत + inside · G3 सोबत + beyond · G4 विरुद्ध + beyond · G5 सोबत + |gap_atr| ≥ `gap_large_atr` (IS p90 ≈ 0.63)
    + आधीचा 5-session leg ≥ `gap_stretch_atr` × ATR (ताणलेला). Trend range / unclear ⇒ GX-inside / GX-beyond. E = event दिवस — वेगळा flag.
  • Fill % = gap मधला आतापर्यंत भरलेला भाग ÷ gap (PDC touch = 100%).
  • PDC पलीकडे acceptance = PDC च्या पलीकडे buffer (0.25 × median range) सह 15m close, आणि पुढच्या bar ने reclaim नाही (शेवटचा bar ⇒ अजून reclaim नाही).
  • वर्तन (`opening_behaviour`, प्रत्येक बंद 15m bar वर पुन्हा, इतिहासासह): rejection = नवीन extreme न होता open ओलांडून PDC कडे; acceptance =
    open-test-drive (नवीन extreme + PDH / PDL पलीकडे टिकाव); नाहीतर undecided. G0 ⇒ no_gap.
  • जुने unfilled gaps: मागच्या `gap_max_age_sessions` पूर्ण दिवसांचे gaps, नंतरच्या (signal पर्यंतच्या) किंमतीने न भरलेला भाग.
"""
import numpy as np
import pandas as pd

MIN_SESSION_BARS = 200
OPEN_T = pd.Timedelta(hours=9, minutes=15)
DEFAULTS = {"gap_g0_atr": 0.25, "gap_large_atr": 0.63, "gap_stretch_atr": 3.0, "gap_max_age_sessions": 10, "gap_accept_buf_mr": 0.25}


def daily(cut):
    """1m (cut) ⇒ दिवसनिहाय OHLC + bars संख्या."""
    if cut is None or len(cut) == 0:
        return pd.DataFrame(columns=["open", "high", "low", "close", "n"])
    g = cut.groupby(cut["timestamp"].dt.normalize())
    return g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("close", "size"))


def atr14(prior):
    if len(prior) < 6:
        return None
    tr = pd.concat([prior["high"] - prior["low"], (prior["high"] - prior["close"].shift()).abs(),
                    (prior["low"] - prior["close"].shift()).abs()], axis=1).max(axis=1)
    return float(tr.tail(14).mean())


def trend_of(prior):
    c = prior["close"]
    if len(c) < 15:
        return "unclear"
    sma = c.rolling(10).mean()
    if c.iloc[-1] > sma.iloc[-1] and sma.iloc[-1] > sma.iloc[-6]:
        return "up"
    if c.iloc[-1] < sma.iloc[-1] and sma.iloc[-1] < sma.iloc[-6]:
        return "down"
    return "range"


def _m15(today):
    from .chart import resample
    return resample(today, 15)


def classify(gap_atr, location, with_trend, leg_atr, s, trend="up"):
    """with_trend: True (सोबत) / False (विरुद्ध). Trend range / unclear ⇒ GX-inside / GX-beyond (G1 / G3 / G4 नाही — तुमचा निर्णय)."""
    if gap_atr is None or abs(gap_atr) < s["gap_g0_atr"]:
        return "G0"
    if trend not in ("up", "down"):
        return "GX-inside" if location == "inside" else "GX-beyond"
    if with_trend and abs(gap_atr) >= s["gap_large_atr"] and leg_atr is not None and leg_atr >= s["gap_stretch_atr"]:
        return "G5"
    if with_trend:
        return "G2" if location == "inside" else "G3"
    return "G1" if location == "inside" else "G4"


def opening_behaviour(done, o, pdc, edge_hi, edge_lo, up, location, buf):
    """प्रत्येक बंद 15m bar वर पुन्हा ठरवलेला निकाल (पहिल्या घटनेवर lock नाही) + इतिहास. Gap up साठी (down = आरसा):
      test        = bar ने open ला (buffer मध्ये) touch केलं
      rejection   = gap दिशेने नवीन extreme (पहिल्या bar च्या high पलीकडे) न होता close open च्या खाली PDC कडे buffer पेक्षा जास्त
      acceptance  = open-test-drive: open ची चाचणी (किंवा पहिल्या bar पासून टिकाव), मग gap दिशेने नवीन extreme, आणि close PDH च्या पलीकडे
                    (beyond gap) / open च्या वर buffer सह (inside gap)
      acceptance नंतर close परत open खाली buffer पेक्षा जास्त ⇒ undecided ("failed drive"). रिटर्न (state, at, history)."""
    if done is None or len(done) == 0:
        return "undecided", None, []
    sgn = 1 if up else -1
    first_ext = float(done["high"].iloc[0] if up else done["low"].iloc[0])
    hold_level = (edge_hi if up else edge_lo) if location == "beyond" else o + sgn * buf
    state, at, hist, tested, new_ext = "undecided", None, [], False, False
    for _, b in done.iterrows():
        hm = str(b["start"])[11:16]
        hi, lo, c = float(b["high"]), float(b["low"]), float(b["close"])
        if (lo <= o + buf) if up else (hi >= o - buf):
            if not tested:
                hist.append(f"{hm} test")
            tested = True
        if (hi > first_ext) if up else (lo < first_ext):
            new_ext = True
        back = (c < o - buf) if up else (c > o + buf)
        if back and not new_ext:
            if state != "rejection":
                hist.append(f"{hm} rejection")
            state, at = "rejection", hm
        elif back and state == "acceptance":
            hist.append(f"{hm} failed drive (back through open)")
            state, at = "undecided", hm
        elif new_ext and ((c > hold_level) if up else (c < hold_level)):
            if state != "acceptance":
                hist.append(f"{hm} acceptance" + (" (open-test-drive)" if tested else ""))
            state, at = "acceptance", hm
    return state, at, hist


def old_gaps(cut, prior, sig_day, mr, s):
    """मागचे unfilled gaps: [{day, low, high, age, filled_pct}] — उरलेला भाग (signal पर्यंतच्या किंमतीने)."""
    out = []
    days = list(prior.index)
    for k in range(max(1, len(days) - int(s["gap_max_age_sessions"])), len(days)):
        d, prev = days[k], prior.iloc[k - 1]
        o = float(prior["open"].iloc[k])
        pc = float(prev["close"])
        if abs(o - pc) < 0.1 * (mr or 1.0):
            continue
        after = cut[cut["timestamp"].dt.normalize() >= d]
        if o > pc:                                                       # gap up: [pc, o]; खाली आलेली किंमत भरते
            lo_seen = float(after["low"].min())
            hi_rem = min(o, lo_seen)
            if hi_rem <= pc:
                continue
            out.append({"day": str(d.date()), "low": pc, "high": hi_rem, "dir": "up", "age": len(days) - k,
                        "filled_pct": round(100 * (o - hi_rem) / (o - pc), 0)})
        else:                                                            # gap down: [o, pc]; वर गेलेली किंमत भरते
            hi_seen = float(after["high"].max())
            lo_rem = max(o, hi_seen)
            if lo_rem >= pc:
                continue
            out.append({"day": str(d.date()), "low": lo_rem, "high": pc, "dir": "down", "age": len(days) - k,
                        "filled_pct": round(100 * (lo_rem - o) / (pc - o), 0)})
    return out


def daily_prior(daily_df, sig_day):
    """Upstox / parquet daily candles ⇒ signal दिवसाआधीचे पूर्ण दिवस (आजचा अपूर्ण daily candle कधीच नाही)."""
    if daily_df is None or len(daily_df) == 0:
        return None
    d = daily_df[["timestamp", "open", "high", "low", "close"]].copy()
    ts = pd.to_datetime(d["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d.index = ts.dt.normalize()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d[d.index < sig_day][["open", "high", "low", "close"]]


def build(cut, signal_ts, mr, settings=None, events=None, daily_df=None):
    """Gap संदर्भ (dict, JSON-safe). cut = signal पर्यंत पूर्ण 1m bars (+ bot चा चालू bar). daily_df (ऐच्छिक) = daily candles — ATR14 / trend /
    leg साठी (1m चे ~3 आठवडे trend ला अपुरे — review B1); नसतील तर 1m वरून."""
    s = {**DEFAULTS, **(settings or {})}
    t = pd.Timestamp(signal_ts)
    sig_day = t.normalize()
    dd = daily(cut)
    prior = dd[(dd.index < sig_day) & (dd["n"] >= MIN_SESSION_BARS)]
    today = cut[cut["timestamp"].dt.normalize() == sig_day]
    ev = (events or {}).get(str(sig_day.date()))
    base = {"event": ev, "has_gap": False, "class": "G0", "behaviour": "no_gap"}
    if prior.empty or today.empty:
        return {**base, "reason": "आधीचा पूर्ण दिवस / आजचे bars नाहीत"}
    p = prior.iloc[-1]
    pdc, pdh, pdl = float(p["close"]), float(p["high"]), float(p["low"])
    o = float(today["open"].iloc[0])
    dp = daily_prior(daily_df, sig_day)
    long_ = dp if dp is not None and len(dp) >= 15 else prior            # ATR / trend / leg: daily candles (असतील तर)
    atr = atr14(long_)
    gap = o - pdc
    gap_atr = gap / atr if atr else None
    up = gap > 0
    location = "inside" if pdl <= o <= pdh else "beyond"
    tr = trend_of(long_)
    with_trend = (up and tr == "up") or ((not up) and tr == "down")
    leg = None
    if atr and len(long_) >= 6:
        leg = (pdc - float(long_["close"].iloc[-6])) / atr * (1 if up else -1)
    cls = classify(gap_atr, location, with_trend, leg, s, tr)
    buf = s["gap_accept_buf_mr"] * (mr or 0.0)
    out = {**base, "trend_source": "daily" if long_ is not prior else "1m", "pdc": pdc, "pdh": pdh, "pdl": pdl, "open": o, "gap": round(gap, 2), "gap_pct": round(gap / pdc * 100, 3),
           "atr14": round(atr, 2) if atr else None, "gap_atr": round(gap_atr, 3) if gap_atr is not None else None,
           "direction": "up" if up else "down", "location": location, "trend": tr, "with_trend": bool(with_trend),
           "leg_atr": round(leg, 2) if leg is not None else None, "class": cls, "has_gap": cls != "G0",
           "edge": (pdh if up else pdl) if location == "beyond" else None, "old_gaps": old_gaps(cut, prior, sig_day, mr, s)}
    # fill
    if up:
        extreme = float(today["low"].min())
        filled = 0.0 if gap == 0 else (o - max(extreme, pdc)) / gap
        touched = extreme <= pdc
    else:
        extreme = float(today["high"].max())
        filled = 0.0 if gap == 0 else (min(extreme, pdc) - o) / (-gap)
        touched = extreme >= pdc
    out["fill_pct"] = round(100 * float(np.clip(filled, 0, 1)), 1)
    out["pdc_touched"] = bool(touched)
    m15 = _m15(today)
    done = m15[m15["end"] <= t] if len(m15) else m15                     # पूर्ण 15m bars फक्त (वर्तनासाठी)
    out["bars_15m_done"] = int(len(done))
    acc = None
    closes = m15["close"].to_numpy(float) if len(m15) else np.array([])
    for i in range(len(done)):                                           # acceptance फक्त पूर्ण bars वर; पुढचा (अपूर्ण असला तरी) reclaim तपासतो
        c = closes[i]
        beyond = (c < pdc - buf) if up else (c > pdc + buf)
        if beyond and (i == len(closes) - 1 or ((closes[i + 1] < pdc) if up else (closes[i + 1] > pdc))):
            acc = str(m15["start"].iloc[i])[11:16]
            break
    out["pdc_acceptance"] = acc is not None
    out["pdc_acceptance_at"] = acc
    if atr is None:
        out["atr_missing"] = True
    if cls == "G0":
        out["behaviour"], out["behaviour_at"], out["behaviour_history"] = "no_gap", None, []
    else:
        beh, at, hist = opening_behaviour(done, o, pdc, pdh, pdl, up, location, buf)
        out["behaviour"], out["behaviour_at"], out["behaviour_history"] = beh, at, hist
    return out
