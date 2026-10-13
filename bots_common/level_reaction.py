"""bots_common/level_reaction.py — level bots: trend आधी, आणि level वर बाजाराची प्रतिक्रिया (confirmation) नंतरच entry.

Abhi (TRADE_SESSION_LEVEL_BOTS_CONFIRMATION): DB मधला level = फक्त उमेदवार AREA (low–high), signal नाही. नवी पद्धत शोधली नाही —
decision3 ची कार्यं जशीच्या तशी वापरली (copy नाही):
  ① trend      = decision3.daily.fold (degree-aware Dow, ABC_FIX) — bar च्या close ला माहीत असलेली Daily अवस्था (आजचा Daily bar नाही)
  ⑥ commitment = decision3.method.commitment / reversal_form (Q16: engulf, pin, outside / strong close …)
  ④ power_shift = पुरावा (corrective approach)
  खरा break    = elliott.breaks.break_from (displacement किंवा पुढचे bars reclaim नाही)
  ⑦ R:R        = entry ची अट नाही (Abhi: R:R / SL / target / lots / exits = dashboard settings). फक्त dashboard setting
                 `gate_rr_gate_enabled` (default False) चालू केल्यास: R:R < min_rr ⇒ DISARMED (target area असेल तरच मोजता येतो).
                 "target area नाही ⇒ DISARMED" = स्वतंत्र dashboard setting `gate_no_target_disarm_enabled` (default False).

State machine प्रत्येक (symbol, area) साठी, फक्त बंद candles वर — दर cycle ला आजच्या session च्या bars वरून पुन्हा replay (DB state
नाही ⇒ restart-safe, causal: bar t चा निर्णय फक्त bars ≤ t वरून):
  IDLE → ARMED (बंद candle area ला overlap, आधीचा close trade-बाजूला, आणि ती बाजू trend ने परवानगी दिलेली)
       → CONFIRMED (commitment candle + LTF CHoCH, approach impulsive नाही, close area च्या आतल्या कडेपलीकडे) = entry
       → DISARMED (खरा break ⇒ area broken, breakout / उलट trade नाही · max_armed_bars मध्ये commitment नाही · impulsive approach;
                   R:R < min_rr फक्त rr_gate_enabled = True; target area नाही फक्त no_target_disarm_enabled = True)
Fail-closed: trend / data / कुठलीही exception ⇒ entry नाही, कारण नोंदीत. हा module order / broker call करत नाही.
"""
import datetime as dt
import json
import os
import time

import numpy as np
import pandas as pd

BULL, BEAR = "BULLISH", "BEARISH"
IDLE, ARMED, CONFIRMED, DISARMED = "IDLE", "ARMED", "CONFIRMED", "DISARMED"

# कारणे (signal log / दैनिक सारांश) — स्थिर शब्द, Abhi च्या यादीप्रमाणे
R_AGAINST = "ignored: against trend"
R_NO_TREND = "no entry: trend unclear"
R_IMPULSIVE = "impulsive approach"
R_NO_COMMIT = "no commitment"
R_BROKEN = "broken"
R_TIMEOUT = "timeout"
R_RR = "R:R < min"
R_NO_TARGET = "no target area"
R_BAD_SL = "invalid SL (not beyond the entry)"     # review: R:R पासून स्वतंत्र guard (structural SL entry च्या चुकीच्या बाजूला ⇒ entry नाही)
R_ERROR = "gate error (fail-closed)"
R_ABSORPTION = "absorption (counter side strengthening inside the area)"
R_LOW_VOL = "commitment on low volume"
R_LTF_MISSING = "LTF data missing"                 # c1: lower-timeframe bars नाहीत ⇒ entry नाही (fail-closed)
R_LTF_AGAINST = "LTF still trending against"       # c1: LTF अजून lower lows (demand) / higher highs (supply)
R_LTF_PENDING = "waiting for LTF CHoCH"            # c1: higher low / sweep झाला, पण शेवटच्या LTF swing पलीकडे close नाही
_LTF_REASON = {"ltf_missing": R_LTF_MISSING, "ltf_against": R_LTF_AGAINST, "ltf_pending": R_LTF_PENDING}

_FORMS = {"engulf": ("bullish engulfing", "bearish engulfing"), "pin": ("hammer / pin", "shooting star / pin"),
          "star": ("morning star", "evening star"), "strong_close": ("strong bullish close", "strong bearish close"),
          "strong_close_2": ("strong bullish close (2 candles)", "strong bearish close (2 candles)"),
          "inside_break": ("inside-bar break up", "inside-bar break down"), "doji_confirm": ("doji + bullish confirm", "doji + bearish confirm"),
          "tweezer": ("tweezer bottom", "tweezer top")}


def form_name(form, side):
    """decision3 reversal_form ⇒ ticket वरचं नाव (दिशेनुसार)."""
    if form is None:
        return ""
    pair = _FORMS.get(form)
    return pair[0 if side == BULL else 1] if pair else str(form)

DEFAULTS = {
    "rr_gate_enabled": False,       # ⑦ R:R gate (dashboard `gate_rr_gate_enabled`). Abhi: R:R entry ची अट नाही ⇒ default बंद (skip / disarm / इशारा नाही)
    "min_rr": 3.0,                  # ⑦ R:R किमान — फक्त rr_gate_enabled = True
    "no_target_disarm_enabled": False,   # "no target area" ⇒ DISARMED (dashboard `gate_no_target_disarm_enabled`; Abhi RR3: स्वतंत्र, default बंद)
    "max_armed_bars": 8,            # ARMED नंतर इतक्या बंद candles मध्ये commitment नाही ⇒ timeout
    "mr_n": 20,                     # median range = मागच्या इतक्या बंद candles चा (high − low) median (चालू वगळून)
    "approach_bars": 3,             # approach = ARMED candle सह शेवटच्या इतक्या candles
    "approach_wide_mr": 1.5,        # impulsive candle: range ≥ इतका × median range …
    "approach_close_frac": 0.25,    # … आणि close approach-दिशेच्या टोकाच्या इतक्या भागात
    "approach_min_wide": 2,         # सलग इतक्या अशा candles ⇒ impulsive drive (entry नाही)
    "sl_buffer_mr": 0.25,           # SL = area च्या दूरच्या कडेपलीकडे (आणि ARMED मधल्या टोकापलीकडे) + इतका × median range
    "wait_next_candle": False,      # हो ⇒ commitment नंतरची candle area मध्ये परत close झाली नाही तरच CONFIRMED
    "allow_parent_correction": False,   # A1 (impulse origin तुटला, parent टिकला) चालू असताना नवे entries? default नाही (fail-safe)
    "grade_b_lot_mult": 1.0,        # grade B ⇒ lots × इतके (MVP: बदल नाही; Abhi ठरवतील)
    "trend_retry_min": 15,          # trend अपयशी (fetch त्रुटी / < 30 Daily bars) ⇒ इतकी मिनिटं पुन्हा fetch नाही (negative cache; entry नाहीच)
    "ltf_choch": True,              # c1 (Abhi, REQUIRED): lower-timeframe CHoCH by close; False फक्त what-if / a2-c0 regression
    "ltf_minutes": 0,               # c1 LTF (dashboard): 0 ⇒ Abhi mapping (decision3.method.LTF_OF: 15M ⇒ 5M, 5M ⇒ 1M)
}


def settings(over=None):
    s = dict(DEFAULTS)
    for k, v in (over or {}).items():
        if k in DEFAULTS and v is not None:
            s[k] = type(DEFAULTS[k])(v) if not isinstance(DEFAULTS[k], bool) else bool(v)
    return s


# ------------------------------------------------------------------------------------------------ ① trend gate
def prepare_daily(df, today=None):
    """Upstox / CSV daily candles ⇒ decision3 चा Daily frame. आजचा (अपूर्ण) Daily bar काढला — trend = कालच्या close पर्यंतची माहिती."""
    from decision3 import daily_swings as DS
    d = DS.prepare(df)
    if today is not None:
        d = d[d["timestamp"] < pd.Timestamp(today)].reset_index(drop=True)
    return d


def trend_context(daily_df, today=None, s=None):
    """Daily अवस्था ⇒ कोणत्या बाजूचे entries चालतात. रिटर्न dict: ok, trend, sides (set), band, protected, phase, counter, reason.
    UP ⇒ फक्त bullish (खालचे support / demand) · DOWN ⇒ फक्त bearish · RANGE ⇒ दोन्ही कडा (Q27) · NEUTRAL / UNKNOWN, origin धोक्यात
    (Q47), origin close ने तुटला ⇒ नवे entries नाहीत."""
    s = settings(s)
    from decision3 import daily as DD
    d = prepare_daily(daily_df, today)
    if len(d) < 30:
        return {"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": f"{R_NO_TREND} (Daily data अपुरा: {len(d)} bars)"}
    return context_from_state(DD.fold(d)[-1], s, asof=str(d["timestamp"].iloc[-1].date()))


def mature_cap(ctx):
    """Daily move mature असेल तर engine चा cap — engine च्याच नियमाने (`decision3.engine.mature_intact`, ctx चे phase / counter):
    रचना अखंड ⇒ "B" (पुरावा फक्त, grade एक पायरी खाली: A ⇒ B); अखंड नाही ⇒ "weak" (engine cap). Mature नाही ⇒ None."""
    if not (ctx or {}).get("mature"):
        return None
    from types import SimpleNamespace
    from decision3.engine import mature_intact
    return "B" if mature_intact(SimpleNamespace(phase=ctx.get("phase"), counter=ctx.get("counter"))) else "weak"


def mature_words(ctx):
    """Telegram (pre-open / 15:45) साठी: "evidence only — grade at most B" किंवा "structure not intact — grade at most weak". None ⇒ mature नाही."""
    cap = mature_cap(ctx)
    if cap is None:
        return None
    return "evidence only — grade at most B" if cap == "B" else "structure not intact — grade at most weak"


def context_from_state(st, s=None, asof=None):
    """एक decision3 DState ⇒ trend context (replay साठी: एकदा fold, मग DD.state_at(states, ts) ⇒ इथे)."""
    s = settings(s)
    ctx = {"ok": False, "trend": st.trend, "sides": set(), "band": st.band, "phase": st.phase, "counter": st.counter,
           "protected": None if st.protected is None else round(float(st.protected.price), 2), "asof": asof,
           "origin_risk": bool(st.origin_risk), "mature": bool(st.mature),
           "targets": [round(float(x), 2) for x in (getattr(st, "targets", None) or ())],   # फक्त माहिती (15:45 सारांश) — निर्णयात नाही
           "structure_against": getattr(st, "rev", None) is not None}
    if st.trend in ("UP", "DOWN"):
        if st.phase == "origin_broken":
            ctx["reason"] = f"{R_NO_TREND} (Daily {st.trend}: protected origin close ने तुटला)"
        elif st.origin_risk:
            ctx["reason"] = f"{R_NO_TREND} (Daily {st.trend}: origin धोक्यात — Q47)"
        elif getattr(st, "rev", None) is not None:                         # trend first (setups audit): रचना trend विरुद्ध
            ctx["reason"] = (f"{R_NO_TREND} (Daily {st.trend}: impulse टोकानंतरची रचना उलट — "
                             f"{'HL' if st.rev[0].kind == 'L' else 'LH'} {st.rev[0].price:,.0f} + close {st.rev[1].price:,.0f} पलीकडे)")
        elif st.counter == "correction" and not s["allow_parent_correction"]:
            ctx["reason"] = f"{R_NO_TREND} (Daily {st.trend}: impulse origin तुटला, parent correction चालू)"
        else:
            ctx.update(ok=True, sides={BULL} if st.trend == "UP" else {BEAR}, reason=f"Daily {st.trend}")
    elif st.trend == "RANGE" and st.band:
        ctx.update(ok=True, sides={BULL, BEAR}, reason=f"Daily RANGE {st.band[0]:,.0f}–{st.band[1]:,.0f} (दोन्ही कडा)")
    else:
        ctx["reason"] = f"{R_NO_TREND} (Daily {st.trend})"
    return ctx


def side_allowed(ctx, side, area):
    """trend ने ही बाजू या area वर चालते का? RANGE ⇒ bullish खालच्या अर्ध्यात, bearish वरच्या अर्ध्यात (Q38)."""
    if not ctx or not ctx.get("ok") or side not in ctx.get("sides", ()):
        return False
    if ctx.get("trend") == "RANGE" and ctx.get("band"):
        mid = (ctx["band"][0] + ctx["band"][1]) / 2.0
        am = (area[0] + area[1]) / 2.0
        return am <= mid if side == BULL else am >= mid
    return True


def _cache_path(symbol, day, cache_dir=None):
    base = cache_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "level_gate")
    return os.path.join(base, f"trend_{symbol}_{day}.json")


def call_with_timeout(fn, args=(), timeout=20.0):
    """fn(*args) daemon thread मध्ये; timeout ⇒ TimeoutError (1-मिनिटाचा cron cycle network मुळे अडकू नये). Exception तसाच पुढे."""
    import threading
    box = {}

    def run():
        try:
            box["v"] = fn(*args)
        except Exception as exc:                                           # noqa: BLE001
            box["e"] = exc
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        raise TimeoutError(f"{getattr(fn, '__name__', 'call')} > {timeout:g}s")
    if "e" in box:
        raise box["e"]
    return box.get("v")


TREND_CTX_VERSION = "trend-first-2"                                        # Daily gate (decision3 fold / context_from_state) बदलला की
                                                                           # वाढवा ⇒ आजचा जुन्या code चा cache (ok True) वापरला जात नाही


def daily_trend(symbol, access_token=None, today=None, fetch=None, cache_dir=None, lookback_days=3650, s=None, timeout=25.0):
    """आजच्या दिवसासाठी trend context (दिवसातून एकदा गणना, file cache). fetch(access_token, symbol) ⇒ daily DataFrame (default Upstox
    'day' candles, ~10 वर्षं — पूर्ण history सारखीच अवस्था देतात). अपयश ⇒ ok False (fail-closed). Cache फक्त पूर्ण fetch चा (≥ 30 bars,
    failed_chunks 0) — एखादा अपयशी / अपूर्ण fetch दिवसभर "trend नाही" ठेवत नाही; `trend_retry_min` नंतर पुन्हा प्रयत्न. Cache key मध्ये
    allow_parent_correction (settings बदलले ⇒ नवी गणना).
    अपयश (ok False — fetch त्रुटी / रिकामे / < 30 bars) ⇒ "_fail" negative cache `trend_retry_min` मिनिटं: त्या काळात तोच ok False निकाल
    (fail-closed, entry नाही) — दर 1-मिनिट cycle ला 25 s चा fetch नाही (MCX exits उशिरा होऊ नयेत)."""
    s = settings(s)
    today = pd.Timestamp(today or dt.date.today()).normalize()
    key = today.date().isoformat() + ("_a1" if s["allow_parent_correction"] else "")
    p = _cache_path(symbol, key, cache_dir)
    pf = _cache_path(symbol, key + "_fail", cache_dir)
    try:
        if os.path.exists(p):
            c = json.load(open(p, encoding="utf-8"))
            if c.get("engine") == TREND_CTX_VERSION:                       # जुन्या code चा (deploy आधीचा) cache ⇒ नवी गणना
                c["sides"] = set(c.get("sides") or ())
                c["band"] = tuple(c["band"]) if c.get("band") else None
                return c
    except (OSError, ValueError):
        pass
    try:
        if os.path.exists(pf):
            f = json.load(open(pf, encoding="utf-8"))
            if _clock() - float(f.get("at", 0)) < float(s["trend_retry_min"]) * 60 and not (f.get("ctx") or {}).get("ok"):
                return {**f["ctx"], "ok": False, "sides": set()}
    except (OSError, ValueError, TypeError):
        pass
    ctx, complete = _fetch_trend(symbol, access_token, today, fetch, lookback_days, s, timeout)
    try:
        if complete:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            json.dump({**ctx, "sides": sorted(ctx["sides"]), "engine": TREND_CTX_VERSION}, open(p, "w", encoding="utf-8"),
                      ensure_ascii=False)
        elif not ctx.get("ok"):
            os.makedirs(os.path.dirname(pf), exist_ok=True)
            json.dump({"at": _clock(), "ctx": {**ctx, "sides": []}}, open(pf, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError:
        pass
    return ctx


_clock = time.time                                                         # tests बदलतात (negative cache ची मुदत)


def _fetch_trend(symbol, access_token, today, fetch, lookback_days, s, timeout):
    """(ctx, complete) — complete = पूर्ण fetch (≥ 30 bars, failed_chunks 0) ⇒ दिवसाचा cache."""
    try:
        if fetch is None:
            from upstox_api import fetch_candles

            def fetch(tok, sym):
                return fetch_candles(tok, sym, current_spot=0, interval="day", lookback_days=lookback_days)
        df = call_with_timeout(fetch, (access_token, symbol), timeout)
        if df is None or len(df) == 0:
            return {"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": f"{R_NO_TREND} (Daily candles मिळाले नाहीत)"}, False
        ctx = trend_context(df, today, s)
    except Exception as exc:                                               # noqa: BLE001 — fail-closed, कारण नोंदीत
        return ({"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": f"{R_ERROR}: trend — {type(exc).__name__}: {str(exc)[:80]}"},
                False)
    return ctx, len(df) >= 30 and not int(getattr(df, "attrs", {}).get("failed_chunks", 0) or 0)


# ------------------------------------------------------------------------------------------------ bars
def closed_bars(df, minutes, now):
    """फक्त पूर्ण झालेले candles (timestamp = candle सुरुवात; सुरुवात + minutes ≤ now)."""
    if df is None or len(df) == 0:
        return df
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    now = pd.Timestamp(now)
    if now.tzinfo is not None:
        now = now.tz_convert("Asia/Kolkata").tz_localize(None)
    out = df.assign(timestamp=ts)
    return out[ts + pd.Timedelta(minutes=int(minutes)) <= now].sort_values("timestamp").reset_index(drop=True)


def _arrays(bars):
    A = {k: bars[k].to_numpy(float) for k in ("open", "high", "low", "close")}
    A["volume"] = bars["volume"].to_numpy(float) if "volume" in bars.columns else None
    return A


def median_ranges(A, n):
    r = pd.Series(A["high"] - A["low"])
    return r.shift(1).rolling(int(n), min_periods=max(3, int(n) // 2)).median().to_numpy(float)


def _impulsive_approach(A, t, side, mr, s):
    """(a) approach: area मध्ये सलग wide-range candles (≥ approach_wide_mr × median range) approach-दिशेच्या टोकाजवळ close ⇒ impulsive."""
    run, best = 0, 0
    for i in range(max(0, t - int(s["approach_bars"]) + 1), t + 1):
        m = mr[i]
        rng = A["high"][i] - A["low"][i]
        if not np.isfinite(m) or m <= 0 or rng <= 0:
            run = 0
            continue
        # approach दिशा = trade च्या उलट: bullish (support) ⇒ खाली येणं ⇒ close low जवळ
        loc = (A["close"][i] - A["low"][i]) / rng if side == BULL else (A["high"][i] - A["close"][i]) / rng
        down = (A["close"][i] - A["open"][i]) * (1 if side == BEAR else -1) > 0
        if rng >= float(s["approach_wide_mr"]) * m and loc <= float(s["approach_close_frac"]) and down:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best >= int(s["approach_min_wide"])


def _target(side, entry, area, others):
    """target = पुढचा उलट area (bullish ⇒ entry वरचा सर्वात जवळचा area चा low; bearish ⇒ खालचा सर्वात जवळचा area चा high)."""
    best = None
    for lo, hi in others or ():
        if hi >= area[0] and lo <= area[1]:
            continue                                                       # तोच / overlapping area
        x = lo if side == BULL else hi
        if (x - entry) * (1 if side == BULL else -1) <= 0:
            continue
        if best is None or abs(x - entry) < abs(best - entry):
            best = x
    return best


# ------------------------------------------------------------------------------------------------ state machine
def tf_minutes_of(bars):
    """bars च्या timestamps मधला सर्वात लहान धन फरक (मिनिटं) — setup TF माहीत नसेल तर. एकच bar ⇒ None."""
    ts = pd.to_datetime(bars["timestamp"]).sort_values().diff().dropna()
    ts = ts[ts > pd.Timedelta(0)]
    return int(ts.min() / pd.Timedelta(minutes=1)) if len(ts) else None


def ltf_minutes_for(tf, s=None):
    """c1 mapping (Abhi): setting `ltf_minutes` (> 0) नाहीतर decision3.method.LTF_OF (15 ⇒ 5, 5 ⇒ 1). माहीत नाही ⇒ None."""
    from decision3 import method as M
    s = settings(s)
    return int(s["ltf_minutes"]) if int(s["ltf_minutes"]) > 0 else M.LTF_OF.get(int(tf)) if tf else None


def evaluate(bars, area, ctx, others=(), session_start=0, s=None, s3=None, es=None, ltf=None, tf_minutes=None):
    """एका area साठी आजच्या session चे बंद bars replay. bars = DataFrame (timestamp, open, high, low, close[, volume]) — मागच्या
    दिवसांचे bars फक्त median range साठी; session_start = आजचा पहिला bar index. area = (lo, hi). ctx = trend_context. others =
    इतर areas [(lo, hi)] (target). ltf = lower-timeframe बंद bars (DataFrame, timestamp = सुरुवात, किंवा तो देणारं callable — commitment
    candle असेल तेव्हाच बोलावतो) — c1 CHoCH; None ⇒ "LTF data
    missing" (entry नाही). tf_minutes = setup TF (नसेल ⇒ bars वरून). a2 + c0 + c1 = decision3.method.confirm (एकच shared function).
    रिटर्न dict: state, entry (शेवटच्या bar वर CONFIRMED?), side, reason, events [(i, state, reason)],
    + CONFIRMED असेल तर entry_price / sl / target / rr / form / grade / evidence."""
    s = settings(s)
    from decision3 import method as M
    from decision3 import settings as S3
    from elliott import breaks as BR
    from elliott import settings as ES
    s3 = {**(s3 or S3.DEFAULTS), "ltf_choch": bool(s["ltf_choch"])}
    es = es or ES.DEFAULTS
    lo, hi = float(min(area)), float(max(area))
    n = len(bars)
    out = {"state": IDLE, "entry": False, "side": None, "reason": "", "events": [], "area": (lo, hi), "bars_armed": 0,
           "max_armed_bars": int(s["max_armed_bars"])}
    if n == 0 or session_start >= n:
        out["reason"] = "आजचे बंद candles नाहीत"
        return out
    A = _arrays(bars)
    mr = median_ranges(A, s["mr_n"])
    frame = bars.reset_index(drop=True)
    tfm = int(tf_minutes or tf_minutes_of(frame) or 5)
    ltm = ltf_minutes_for(tfm, s)
    lcache = {}

    def get_ltf():                                                         # lazy: commitment candle असेल तेव्हाच LTF (fetch) लागतो
        if "L" not in lcache:
            raw = ltf() if callable(ltf) else ltf
            lcache["L"] = M.ltf_frame(raw, ltm or 1, f"{ltm}M" if ltm else "LTF") if raw is not None else None
            if lcache["L"] is None and s["ltf_choch"]:
                M.warn_ltf_missing("level_reaction.evaluate")
        return lcache["L"]
    TS = pd.to_datetime(frame["timestamp"])
    t_ses = TS.iloc[int(session_start)]
    state, side, arm, broken, reason = IDLE, None, None, False, ""
    broken_side = None                                                     # आज ज्या भूमिकेत area खरा तुटला (review 🟡8: उलट भूमिकेत retest चालतो)
    commit_at, info = None, {}
    swept = False
    lvl = {"lo": lo, "hi": hi}

    def ev(i, st_, why):
        out["events"].append((int(i), st_, why))

    for t in range(int(session_start), n):
        o, h, l, c = A["open"][t], A["high"][t], A["low"][t], A["close"][t]
        overlap = l <= hi and h >= lo
        if state != IDLE and side is not None and side != broken_side:     # area वर आलेल्या प्रत्येक भेटीत: far edge चा खरा break?
            d = M.UP if side == BULL else M.DOWN
            far_side = "below" if side == BULL else "above"
            far = lo if side == BULL else hi
            if (c - far) * d < 0:                                          # far edge पलीकडे close
                r = BR.break_from(frame, t, far, far_side, es, mr=None)
                swept = True                                               # far edge पलीकडे गेलं (break नसेल तर sweep पुरावा)
                if r is not None and r != -1:
                    state, reason, broken, broken_side = DISARMED, R_BROKEN, True, side   # तीच बाजू आज पुन्हा नाही; उलट भूमिका (flip) चालते
                    ev(r, DISARMED, R_BROKEN)
                    out["broken_at"] = int(r)
                    continue
                if r == -1:
                    out["break_pending"] = True                            # अजून ठरलं नाही (पुढचे bars नाहीत)
                continue                                                   # false break (पुढे reclaim) ⇒ पुढच्या bars वर commitment
        if state in (CONFIRMED, DISARMED):
            if not overlap:
                state, side, arm, swept, commit_at = IDLE, None, None, False, None   # area सोडली ⇒ पुढचा स्पर्श नवा
            continue
        if state == IDLE:
            if not overlap:
                continue
            pc = A["close"][t - 1] if t > 0 else o
            if pc > hi:
                sd = BULL                                                  # वरून आलं ⇒ support / demand
            elif pc < lo:
                sd = BEAR                                                  # खालून आलं ⇒ resistance / supply
            else:
                continue                                                   # आधीपासून area मध्ये ⇒ arrival नाही
            if sd == broken_side:
                continue                                                   # आज याच भूमिकेत तुटलेला area ⇒ पुन्हा नाही (उलट भूमिका चालते)
            if not side_allowed(ctx, sd, (lo, hi)):
                reason = R_AGAINST if (ctx or {}).get("ok") else (ctx or {}).get("reason", R_NO_TREND)
                ev(t, DISARMED, reason)
                state, side, arm = DISARMED, sd, t
            else:
                state, side, arm, swept = ARMED, sd, t, False
                for k_ in ("absorbing", "low_vol_logged", "impulsive", "ltf_wait", "ltf_logged"):
                    info.pop(k_, None)                                     # नवी भेट ⇒ मागचे झेंडे नाहीत
                ev(t, ARMED, "price arrived")
                if _impulsive_approach(A, t, sd, mr, s):
                    info["impulsive"] = True
            d = M.UP if side == BULL else M.DOWN
            far = lo if side == BULL else hi
            if (c - far) * d < 0 or (o - far) * d < 0:                     # arrival candle नेच far edge पलीकडे (gap / close)
                r = BR.break_from(frame, t, far, "below" if side == BULL else "above", es, mr=None)
                swept = True
                if r is not None and r != -1:
                    state, reason, broken, broken_side = DISARMED, R_BROKEN, True, side
                    ev(r, DISARMED, R_BROKEN)
                    out["broken_at"] = int(r)
                    continue
                if r == -1:
                    out["break_pending"] = True
                continue
        if state != ARMED:
            continue
        d = M.UP if side == BULL else M.DOWN
        far = lo if side == BULL else hi
        if (l < far and side == BULL) or (h > far and side == BEAR):
            swept = True
        if info.get("impulsive"):
            state, reason = DISARMED, R_IMPULSIVE
            ev(t, DISARMED, R_IMPULSIVE)
            info.pop("impulsive", None)
            continue
        if commit_at is not None:                                          # wait_next_candle: commitment नंतरची candle
            if (c - (hi if side == BULL else lo)) * d > 0:
                state = CONFIRMED
                ev(t, CONFIRMED, "commitment + next candle held")
                out.update(info.get("plan", {}))
                if t == n - 1:
                    out["entry"] = True
            else:
                state, reason, commit_at = DISARMED, R_NO_COMMIT + " (next candle back inside)", None
                ev(t, DISARMED, reason)
            continue
        cf = M.confirm(A, arm, t, d, lvl, s3, None, mr=mr[t], ltf=get_ltf,  # a2 + c0 + c1 — decision3 चं एकच shared function
                       ltf_times=(t_ses, TS.iloc[arm], TS.iloc[t] + pd.Timedelta(minutes=tfm)))
        if cf["absorption"]:                                               # a2: area मध्ये उलट-बाजू मजबूत होत (absorption) ⇒ ती टिकेपर्यंत entry नाही
            if not info.get("absorbing"):
                ev(t, ARMED, R_ABSORPTION)
            info["absorbing"] = True
            if t - arm + 1 >= int(s["max_armed_bars"]):
                state, reason = DISARMED, R_TIMEOUT
                ev(t, DISARMED, R_TIMEOUT)
            continue
        if cf["study_ran"]:
            info["absorbing"] = False
        ok, cm = cf["c0"], cf["commit"]
        if not ok and cm.get("wait") == "low_volume" and not info.get("low_vol_logged"):
            ev(t, ARMED, R_LOW_VOL)                                        # c0: dominant पण volume कमी ⇒ याच candle वर नाही, timeout पर्यंत वाट
            info["low_vol_logged"] = True
        inner_ok = (c - (hi if side == BULL else lo)) * d > 0              # area च्या आतल्या कडेपलीकडे close
        info["ltf_wait"] = None
        if ok and inner_ok and not cf["ok"]:                               # c1: commitment आहे पण LTF CHoCH नाही ⇒ वाट (कारण नोंदीत, timeout पर्यंत)
            why_l = _LTF_REASON.get(cf["wait"], R_LTF_PENDING)
            info["ltf_wait"] = why_l
            if info.get("ltf_logged") != why_l:
                ev(t, ARMED, why_l)
                info["ltf_logged"] = why_l
            info["ltf_line"] = (cf["choch"] or {}).get("line")
        if ok and inner_ok and cf["ok"]:
            m = mr[t] if np.isfinite(mr[t]) else 0.0
            seg_l, seg_h = A["low"][arm:t + 1].min(), A["high"][arm:t + 1].max()
            sl = (min(lo, seg_l) - float(s["sl_buffer_mr"]) * m) if side == BULL else (max(hi, seg_h) + float(s["sl_buffer_mr"]) * m)
            tgt = _target(side, c, (lo, hi), others)
            rk = (c - sl) * d
            rr_on = bool(s["rr_gate_enabled"])                             # ⑦ dashboard setting; बंद (default) ⇒ R:R मोजत / दाखवत नाही
            rr = None if (not rr_on or tgt is None or rk <= 0) else (tgt - c) * d / rk
            zs = cf["study"]                                               # a2: window ARMED ⇒ commitment candle
            evid = {"sweep": bool(swept), "corrective_approach": bool(M.power_shift(A, t, d, None, s3, lvl)[0]),
                    "handover": zs.get("handover"), "pattern": zs.get("pattern"), "rsi_divergence": None,
                    "commit_grade_A": cm.get("grade") == "A", "volume_na": bool(cm.get("vol_na"))}
            n_ev = sum(1 for k in ("sweep", "corrective_approach", "pattern", "rsi_divergence") if evid[k])
            grade = "A" if (evid["handover"] or n_ev >= 2) else "B"       # handover (दोन्ही बाजू) = मजबूत पुरावा ⇒ A
            if cm.get("vol_na"):
                grade = "B"                                                # c0: volume NA ⇒ grade कमाल B
            kind = "demand" if side == BULL else "supply"
            vtxt = f"volume {cm['vol_mult']:.1f}× window avg" if cm.get("vol_mult") is not None else "volume: NA"
            btxt = f"body {cm['body_mult']:.1f}× window avg" if cm.get("body_mult") is not None else ""
            plan = {"entry_price": round(float(c), 2), "sl": round(float(sl), 2), "target": None if tgt is None else round(float(tgt), 2),
                    "rr": None if rr is None else round(float(rr), 2), "form": cm.get("form"), "commit_grade": cm.get("grade"),
                    "grade": grade, "evidence": evid, "confirm_bar": int(t),
                    "confirm_ts": str(pd.Timestamp(bars["timestamp"].iloc[t])),
                    "arm_bar": int(arm), "arm_ts": str(pd.Timestamp(bars["timestamp"].iloc[arm])),   # chart: study window (volume pane)
                    **_volume_out(frame, A, arm, t, (lo, hi), d, cm),          # chart / caption: engine चेच volume आकडे (output only)
                    "study": f"inside {kind}: " + (zs.get("line") or "no clear handover read"),
                    "commit_line": "commitment: " + " · ".join(x for x in (form_name(cm.get("form"), side), btxt, vtxt) if x)}
            if cf["choch"] and cf["choch"].get("done"):
                plan["ltf_line"] = cf["choch"]["line"]                     # c1 ticket: "5M CHoCH: higher low …, close above LH … at 10:20"
            if rk <= 0:                                                    # R:R-निरपेक्ष guard (आधी R:R None ⇒ disarm मधून अप्रत्यक्ष होता)
                state, reason = DISARMED, R_BAD_SL
                ev(t, DISARMED, R_BAD_SL)
                out.update(plan)
                continue
            if tgt is None and s["no_target_disarm_enabled"]:              # स्वतंत्र dashboard setting (default बंद; Abhi RR3)
                state, reason = DISARMED, R_NO_TARGET
                ev(t, DISARMED, R_NO_TARGET)
                out.update(plan)
                continue
            if rr_on and rr is not None and rr < float(s["min_rr"]):      # target नाही ⇒ R:R मोजता येत नाही ⇒ इथे skip नाही (वरची setting)
                state, reason = DISARMED, f"{R_RR} ({rr:.2f} < {float(s['min_rr']):g})"
                ev(t, DISARMED, reason)
                out.update(plan)
                continue
            if s["wait_next_candle"]:
                commit_at, info["plan"] = t, plan
                ev(t, ARMED, f"commitment {cm.get('form')} — next candle ची वाट")
                continue
            state = CONFIRMED
            ev(t, CONFIRMED, f"commitment {cm.get('form')} · grade {plan['grade']}")
            out.update(plan)
            if t == n - 1:
                out["entry"] = True
            continue
        if t - arm + 1 >= int(s["max_armed_bars"]):
            state, reason = DISARMED, R_TIMEOUT
            ev(t, DISARMED, R_TIMEOUT)
            continue
    out["state"], out["side"] = state, side
    out["bars_armed"] = 0 if arm is None or state != ARMED else int(n - arm)
    if state == ARMED:
        out["reason"] = R_NO_COMMIT + (" (break pending)" if out.get("break_pending") else "")
    elif state == DISARMED:
        out["reason"] = reason
    elif state == CONFIRMED:
        out["reason"] = "confirmed" if out["entry"] else "confirmed earlier (area not left yet)"
    else:
        out["reason"] = R_BROKEN if broken else "price not at area"            # आज तुटलेला area (flip retest अजून नाही) ⇒ कारण "broken"
    out["broken"] = bool(broken)
    out["absorbing"] = state == ARMED and bool(info.get("absorbing"))     # L5: ARMED मधलं कारण (signal log / दैनिक सारांश)
    out["low_volume"] = state == ARMED and bool(info.get("low_vol_logged"))
    out["ltf_wait"] = info.get("ltf_wait") if state == ARMED else None   # c1: ARMED मधलं LTF कारण (signal log / dashboard)
    if out["ltf_wait"]:
        out["ltf_line"] = info.get("ltf_line")
    return out


VOLUME_BARS_OUT = 80                                                       # chart साठी bar volumes (setup panel ≈ 60 bars)


def _volume_out(frame, A, arm, t, area, d, cm):
    """Output only (निर्णयात नाही): c0 चा vol_mult / vol_na, त्याच window ची trend-side / counter-side सरासरी (× window avg) आणि
    t पर्यंतचे शेवटचे bars चे volume — Vision chart / caption तेच आकडे दाखवतात (पुन्हा futures fetch नाही, दोन वेगळे आकडे नाहीत)."""
    from decision3 import volume_pane as VP
    v = A.get("volume")
    out = {"vol_mult": cm.get("vol_mult"), "vol_na": bool(cm.get("vol_na")) if cm.get("vol_na") is not None else v is None,
           "vol_trend_mult": None, "vol_counter_mult": None, "bar_volumes": []}
    if v is None:
        return out
    st = VP.study(frame.iloc[:t + 1], vol=v[:t + 1], area=area, d=d, commit=int(t), arm=int(arm))
    out["vol_trend_mult"], out["vol_counter_mult"] = st["trend_mult"], st["counter_mult"]
    k0 = max(0, int(t) + 1 - VOLUME_BARS_OUT)
    ts = pd.to_datetime(frame["timestamp"]).iloc[k0:t + 1]
    out["bar_volumes"] = [[str(pd.Timestamp(x)), (float(y) if np.isfinite(y) and y > 0 else None)] for x, y in zip(ts, v[k0:t + 1])]
    return out


def safe_evaluate(*a, **k):
    """Fail-closed wrapper: exception ⇒ entry नाही, कारण नोंदीत."""
    try:
        return evaluate(*a, **k)
    except Exception as exc:                                               # noqa: BLE001
        return {"state": "ERROR", "entry": False, "side": None, "reason": f"{R_ERROR}: {type(exc).__name__}: {str(exc)[:80]}",
                "events": []}


def session_start_index(bars, day=None):
    """bars मधला `day` (default: शेवटच्या bar चा दिवस) चा पहिला index."""
    if bars is None or len(bars) == 0:
        return 0
    ts = pd.to_datetime(bars["timestamp"])
    day = pd.Timestamp(day).normalize() if day is not None else ts.iloc[-1].normalize()
    idx = np.nonzero((ts.dt.normalize() == day).to_numpy())[0]
    return int(idx[0]) if len(idx) else len(bars)


def describe(r, area=None):
    """Dashboard / log साठी एक ओळ: "Watching supply 22,570–22,640 · price arrived · waiting for a bearish commitment · 3/8 bars"."""
    lo, hi = r.get("area") or area or (None, None)
    kind = "demand" if r.get("side") == BULL else ("supply" if r.get("side") == BEAR else "area")
    rng = f"{lo:,.0f}–{hi:,.0f}" if lo is not None else ""
    st = r.get("state")
    if st == ARMED:
        word = "bullish" if r.get("side") == BULL else "bearish"
        why = " · absorption" if r.get("absorbing") else (" · commitment on low volume" if r.get("low_volume") else
                                                          (f" · {r['ltf_wait']}" if r.get("ltf_wait") else ""))
        return (f"Watching {kind} {rng} · price arrived · waiting for a {word} commitment · "
                f"{r.get('bars_armed', 0)}/{r.get('max_armed_bars')} bars{why}")
    if st == CONFIRMED:
        return (f"CONFIRMED {kind} {rng} · {r.get('form')} · grade {r.get('grade')} · entry {r.get('entry_price')} · "   # Abhi RR2: trade चे
                f"engine reference (info): SL {r.get('sl')} · target {r.get('target')}"                        # SL / target = dashboard
                + (f" · R:R {r.get('rr')}" if r.get("rr") is not None else ""))   # R:R फक्त rr gate चालू
    if st == DISARMED:
        return f"{kind} {rng} · disarmed: {r.get('reason')}"
    if st == "ERROR":
        return f"{rng} · {r.get('reason')}"
    return f"{kind} {rng} · {r.get('reason')}"


def lot_multiplier(r, s=None):
    s = settings(s)
    return 1.0 if r.get("grade") == "A" else float(s["grade_b_lot_mult"])
