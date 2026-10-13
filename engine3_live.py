"""engine3_live.py — decision3 (थर v2.2, method engine: trend → area → pullback → commitment + c1; R:R नाही — Abhi 13 Oct) चा **live** feed (Abhi: one bot, Tuesday PAPER).

प्रत्येक बंद 15M candle नंतर (cron, `scripts/engine_signal_run.py --engine decision3`) एका symbol साठी:
  • 15M spot (Upstox, `engine3_m15_days` दिवस) — फक्त बंद candles; NIFTY ⇒ `data_policy.filter_allowed(..., "annotation")` (holdout row नाही).
  • Daily (Upstox 'day', ~10 वर्षं, आजचा अपूर्ण Daily bar नाही) — Q33: Daily holdout candles फक्त warm-up input (level_reaction.daily_trend
    प्रमाणेच); output मध्ये sealed तारीख नाही (`history.sealed_fn`). Weekly = Daily वरून (V22 स्वतः).
  • 5M spot (LTF: c1 5M CHoCH) ⇒ V22 `ltf=`; नसेल ⇒ fail-closed. Front-month FUT 5M volume (c0 dominant candle + volume) ⇒ V22
    `futures=` (expiry सह; जुना V22 ⇒ m15 joined `volume`; `engine3_fut_days` — volume ÷ त्याच slot चा 20 sessions median). Abhi Z-1c:
    NIFTY / BANKNIFTY चा FUT नसेल ⇒ FutVolumeMissing (data error: entry नाही + दिवसातून एकदा Telegram); volume शिवाय grade-B entry नाही.
  • V22(m15, daily_df=…).decide(शेवटचा बंद bar) ⇒ engine_signal store row (decision2 च्याच columns) ⇒ bots चा adapter (`pending_entry`).
Fail-closed: data नाही / अपूर्ण / exception ⇒ EngineDataError (caller "error" row + दिवसातून एकदा Telegram ओळ). Order / broker call नाही.
Daily fold (सर्वात महाग भाग, ~50 s) दिवसाला एकदा: input hash वर disk cache (`data/engine3_cache/`) — शुद्ध function, निकाल तोच.
1m spot (Abhi Z-1o = (a), setting `engine3_use_1m`, default True): swings2 ला प्रत्येक 15M candle मधला high / low क्रम (replay / rsi2 सारखाच)
⇒ V22 `df1m=` (swings2 ⇒ levels + rsi2 Divergence त्याच pivots वर). आधीचे दिवस historical (दिवसातून एकदा, disk cache), आजचे intraday
(प्रत्येक cycle ला 1 call). फक्त बंद 1m आणि शेवटच्या बंद 15M च्या आतले (look-ahead नाही). 1m नाही ⇒ जुना मार्ग (1m शिवाय) + कारण
(payload `m1`, log ओळ) — data error / block नाही (FUT volume हा आवश्यक input, 1m नाही). False ⇒ जुनं वर्तन.
"""
import datetime as dt
import hashlib
import inspect
import json
import os
import pickle
import urllib.parse

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = {"engine3_m15_days": 90, "engine3_daily_days": 3650, "engine3_ltf_days": 10,
            "engine3_fut_days": 45,                                       # Abhi Z-1: volume ÷ slot median of 20 sessions ⇒ ≥ 21 sessions FUT
            "engine3_use_1m": True}                                       # Abhi Z-1o (a): 1m spot ⇒ swings2 (1m चा window = engine3_m15_days)
FUT_REQUIRED = ("NIFTY", "BANKNIFTY")                                     # Abhi Z-1c: FUT volume नाही = data error (entry नाही + Telegram)
DATA_PROBLEM_FUT = "data problem: FUT volume missing"
SESSION_OPEN, SESSION_CLOSE = (9, 15), (15, 30)
FUT_EXCHANGE = {"SENSEX": "BSE"}                                          # बाकी NSE (NIFTY / BANKNIFTY)


class EngineDataError(RuntimeError):
    """Live data नाही / अपूर्ण ⇒ entry नाही (fail-closed)."""


class FutVolumeMissing(EngineDataError):
    """Abhi Z-1c: NIFTY / BANKNIFTY चा FUT volume नाही ⇒ data error ⇒ entry नाही; caller दिवसातून एकदा (symbol प्रमाणे) Telegram ओळ
    "data problem: FUT volume missing" (engine_signal.alert_data_problem)."""
    data_problem = True


def cache_dir():
    return os.environ.get("ENGINE3_CACHE_DIR") or os.path.join(ROOT, "data", "engine3_cache")


# ------------------------------------------------------------------------------------------------ instrument
def index_key(symbol):
    """instruments.py (एकच नोंद) ⇒ Upstox index key. माहीत नाही ⇒ EngineDataError (upstox_api चा NIFTY fallback कधीच नाही)."""
    import instruments as INS
    try:
        return INS.get(symbol)["key"]
    except ValueError as exc:
        raise EngineDataError(f"{symbol}: instrument resolve नाही (instruments.py) — {exc}")


def resolve_future(token, symbol, today):
    """Front-month index future (NSE: NIFTY / BANKNIFTY; BSE: SENSEX). रिटर्न info dict; नाही ⇒ EngineDataError."""
    import verify_opportunity_data_availability as V
    exch = FUT_EXCHANGE.get(symbol.upper(), "NSE")
    params = {"query": symbol.upper(), "exchanges": exch, "segments": "FO", "instrument_types": "FUT", "page_number": 1, "records": 30}
    status, body, error = V._get(f"{V.BASE_V2}/instruments/search", token, params=params)
    if status != 200:
        raise EngineDataError(f"{symbol}: FUT resolve HTTP {status} ({str(error)[:80]})")
    rows = [r for r in ((body or {}).get("data") or []) if V._name_before_fut(r.get("trading_symbol")) == symbol.upper()
            and V._expiry_str(r.get("expiry")) >= today.isoformat()]
    if not rows:
        raise EngineDataError(f"{symbol}: {exch} front-month FUT सापडला नाही ⇒ FUT volume नाही")
    rows.sort(key=lambda r: V._expiry_str(r.get("expiry")))
    r = rows[0]
    return {"trading_symbol": r.get("trading_symbol"), "instrument_key": r.get("instrument_key"), "expiry": V._expiry_str(r.get("expiry"))}


# ------------------------------------------------------------------------------------------------ Upstox feed (VPS)
class UpstoxFeed:
    """फक्त GET. historical (chunks) + आजचा intraday. कोणताही chunk अयशस्वी ⇒ EngineDataError (अपूर्ण history वर निर्णय नाही)."""
    CHUNK = {"1minute": 28, "5minute": 28, "15minute": 28, "day": 3700}

    def __init__(self, token, today=None):
        if not token:
            raise EngineDataError("Upstox token नाही")
        self.token = token
        self.today = today or dt.date.today()

    def _series(self, key, interval, days, contract=None):
        out = self._history(key, interval, days)
        if interval != "day":
            out = out + self._intraday(key, interval)
        return candles_df(out, contract)

    def _history(self, key, interval, days):
        """historical chunks (+ गायब दिवस) — candles list. minute ⇒ काल पर्यंत; day ⇒ आज पर्यंत."""
        import verify_opportunity_data_availability as V
        # minute history: to_date = काल (आजचे bars intraday मधून). to_date = आज दिल्यास Upstox कालचा पूर्ण दिवस वगळतो (13 Oct: 15M/5M
        # 9 Oct ला संपले, 12 Oct गायब; फक्त 12 Oct मागितल्यावर पूर्ण दिवस आला).
        out = []
        to = self.today if interval == "day" else self.today - dt.timedelta(days=1)
        start = self.today - dt.timedelta(days=int(days))
        while to > start:
            frm = max(start, to - dt.timedelta(days=self.CHUNK[interval]))
            r = V.fetch_candles_window(self.token, key, interval, frm, to)
            if r["status"] != 200:
                raise EngineDataError(f"{key} {interval} history HTTP {r['status']} ({str(r['error'])[:80]})")
            out.extend(r["candles"])
            to = frm - dt.timedelta(days=1)
        if interval != "day":
            out.extend(self._fill_recent_days(key, interval, out))
        return out

    def _intraday(self, key, interval):
        import verify_opportunity_data_availability as V
        unit, val = V._V3_UNITS[interval]
        enc = urllib.parse.quote(key, safe="")
        st, body, err = V._get(f"{V.BASE_V3}/intraday/{enc}/{unit}/{val}", self.token)
        if st != 200:
            raise EngineDataError(f"{key} {interval} intraday HTTP {st} ({str(err)[:80]})")
        return list(((body or {}).get("data") or {}).get("candles") or [])

    def _history_cached(self, key, interval, days):
        """आधीचे दिवस बदलत नाहीत ⇒ history दिवसातून एकदा (disk cache: key + interval + days + आजची तारीख). Cache त्रुटी ⇒ साधा fetch."""
        tag = "".join(ch if ch.isalnum() else "_" for ch in f"{key}_{interval}_{int(days)}")
        p = os.path.join(cache_dir(), f"hist_{tag}_{self.today.isoformat()}.pkl")
        try:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    return pickle.load(f)
        except Exception:                                                # noqa: BLE001
            pass
        out = self._history(key, interval, days)
        prev = self.today - dt.timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= dt.timedelta(days=1)
        last = max((pd.Timestamp(str(c[0])[:10]).date() for c in out), default=None)
        if last is None or last < prev:                                  # कालचा दिवस अजून नाही (उशीर / सुट्टी) ⇒ cache नाही, पुढच्या cycle ला पुन्हा
            return out
        try:
            os.makedirs(cache_dir(), exist_ok=True)
            with open(p + ".tmp", "wb") as f:
                pickle.dump(out, f)
            os.replace(p + ".tmp", p)
            for old in os.listdir(cache_dir()):                          # जुन्या दिवसांच्या history files
                if old.startswith(f"hist_{tag}_") and old.endswith(".pkl") and old != os.path.basename(p):
                    os.remove(os.path.join(cache_dir(), old))
        except Exception:                                                # noqa: BLE001
            pass
        return out

    def _fill_recent_days(self, key, interval, rows, lookback=7):
        """History मध्ये शेवटच्या दिवसानंतरचे (आज वगळून) weekday दिवस गायब असतील तर ते एकेक-दिवस मागवून भरतो (सुट्टी ⇒ रिकामं, चालतं)."""
        import verify_opportunity_data_availability as V
        last = max((pd.Timestamp(str(c[0])[:10]).date() for c in rows), default=None)
        if last is None:
            return []
        extra, d = [], max(last + dt.timedelta(days=1), self.today - dt.timedelta(days=lookback))
        while d < self.today:
            if d.weekday() < 5:
                r = V.fetch_candles_window(self.token, key, interval, d, d)
                if r["status"] != 200:
                    raise EngineDataError(f"{key} {interval} {d} history HTTP {r['status']} ({str(r['error'])[:80]})")
                extra.extend(r["candles"])
            d += dt.timedelta(days=1)
        return extra

    def index(self, symbol, interval, days):
        if interval == "1minute":                                        # Z-1o: history दिवसातून एकदा (cache) + आजचा intraday
            key = index_key(symbol)
            return candles_df(self._history_cached(key, interval, days) + self._intraday(key, interval))
        return self._series(index_key(symbol), interval, days)

    def futures(self, symbol, interval, days):
        info = resolve_future(self.token, symbol, self.today)
        f = self._series(info["instrument_key"], interval, days, contract=info["trading_symbol"])
        return f.assign(expiry=pd.Timestamp(info["expiry"])) if len(f) else f     # legs2.volume.near_month साठी


# ------------------------------------------------------------------------------------------------ frames
def candles_df(candles, contract=None):
    from opportunity_engine.volume import candles_to_df
    return candles_to_df(candles, contract=contract)


def _naive(df):
    df = df.copy()
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    df["timestamp"] = ts
    return df.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)


def closed_session_bars(df, minutes, now):
    """फक्त बंद (start + minutes ≤ now) आणि session मधले (09:15 ≤ start, end ≤ 15:30) candles, bar_end सह."""
    if df is None or not len(df):
        return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close", "volume"])
    df = _naive(df)
    end = df["timestamp"] + pd.Timedelta(minutes=minutes)
    tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    eod = end.dt.hour * 60 + end.dt.minute
    keep = (end <= pd.Timestamp(now)) & (tod >= SESSION_OPEN[0] * 60 + SESSION_OPEN[1]) & (eod <= SESSION_CLOSE[0] * 60 + SESSION_CLOSE[1])
    out = df[keep.to_numpy()].assign(bar_end=end[keep.to_numpy()]).reset_index(drop=True)
    if "volume" not in out.columns:
        out["volume"] = 0.0
    return out[["timestamp", "bar_end", "open", "high", "low", "close", "volume"] + (["contract"] if "contract" in out.columns else [])]


def fut_volume_15m(m15, fut5):
    """FUT 5M volume ⇒ 15M bins (09:15 anchored, bar start = 15M timestamp). जुळलं नाही ⇒ 0 (अंदाज नाही)."""
    if fut5 is None or not len(fut5):
        return pd.Series(0.0, index=m15.index)
    f = _naive(fut5)
    b = f["timestamp"].dt.floor("15min")
    vol = f.groupby(b)["volume"].sum()
    return pd.to_datetime(m15["timestamp"]).map(vol).fillna(0.0).astype(float)


# ------------------------------------------------------------------------------------------------ Daily fold cache
def _fold_key(df, s):
    h = hashlib.sha1()
    h.update(pd.util.hash_pandas_object(df.reset_index(drop=True), index=False).values.tobytes())
    h.update(repr(sorted((k, repr(v)) for k, v in (s or {}).items())).encode())
    return h.hexdigest()[:24]


class fold_cache:
    """`decision3.daily.fold` ला तात्पुरता disk cache (input hash ⇒ तोच निकाल). कोणतीही cache त्रुटी ⇒ साधी गणना."""

    def __init__(self, tag):
        self.tag = tag

    def __enter__(self):
        from decision3 import daily as DD
        self.DD, self.orig = DD, DD.fold
        d = cache_dir()

        def fold(df, s=None, *a, **k):
            if a or k:
                return self.orig(df, s, *a, **k)
            try:
                p = os.path.join(d, f"fold_{self.tag}_{_fold_key(df, s)}.pkl")
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return pickle.load(f)
            except Exception:                                            # noqa: BLE001
                p = None
            res = self.orig(df, s)
            try:
                if p:
                    os.makedirs(d, exist_ok=True)
                    with open(p + ".tmp", "wb") as f:
                        pickle.dump(res, f)
                    os.replace(p + ".tmp", p)
            except Exception:                                            # noqa: BLE001
                pass
            return res
        DD.fold = fold
        return self

    def __exit__(self, *exc):
        self.DD.fold = self.orig
        return False


def prune_cache(keep_days=3, now=None):
    d = cache_dir()
    if not os.path.isdir(d):
        return
    cut = (now or pd.Timestamp.now()).timestamp() - keep_days * 86400
    for f in os.listdir(d):
        try:
            p = os.path.join(d, f)
            if os.path.getmtime(p) < cut:
                os.remove(p)
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------ inputs ⇒ V22
def v22_kwargs():
    """V22 चे optional live kwargs (ltf / futures) आहेत का — confirmation branch merge आधी / नंतर दोन्हीवर चालावं."""
    from decision3 import engine as E3
    return set(inspect.signature(E3.V22.__init__).parameters)


def build_inputs(feed, symbol, now, s=None):
    """(m15, daily, ltf5, fut5|None, volume note|None). 15M / Daily / 5M LTF अपुरा ⇒ EngineDataError (fail-closed); FUT नाही ⇒ volume NA."""
    from bots_common import level_reaction as LR
    from decision3 import history as HI
    from elliott import data_policy as DP
    s = {**DEFAULTS, **(s or {})}
    now = pd.Timestamp(now)
    m15 = closed_session_bars(feed.index(symbol, "15minute", s["engine3_m15_days"]), 15, now)
    if HI.is_nifty(symbol):
        m15 = DP.filter_allowed(m15, "annotation")                      # NIFTY: holdout row कधीच नाही (15M engine input)
    if len(m15) < 200:
        raise EngineDataError(f"{symbol}: 15M candles अपुरे ({len(m15)})")
    want = now.floor("15min")
    if pd.Timestamp(m15["bar_end"].iloc[-1]) < want and SESSION_OPEN <= (want.hour, want.minute) <= SESSION_CLOSE:
        raise EngineDataError(f"{symbol}: शेवटचा बंद 15M ({want:%H:%M}) अजून Upstox कडे नाही (last {m15['bar_end'].iloc[-1]:%H:%M})")
    dd = feed.index(symbol, "day", s["engine3_daily_days"])
    if dd is None or len(dd) < 30:
        raise EngineDataError(f"{symbol}: Daily candles अपुरे ({0 if dd is None else len(dd)})")
    daily = LR.prepare_daily(_naive(dd)[["timestamp", "open", "high", "low", "close"]], now.normalize())
    if len(daily) < 30:
        raise EngineDataError(f"{symbol}: Daily candles अपुरे ({len(daily)})")
    ltf = closed_session_bars(feed.index(symbol, "5minute", s["engine3_ltf_days"]), 5, now)
    if HI.is_nifty(symbol):
        ltf = DP.filter_allowed(ltf, "annotation")
    if not len(ltf) or ltf["timestamp"].iloc[-1].normalize() != m15["timestamp"].iloc[-1].normalize():
        raise EngineDataError(f"{symbol}: 5M spot (LTF) data नाही ⇒ c1 CHoCH तपासता येत नाही")
    fut, note = None, None
    try:                                                                 # c0 / a2 volume (Abhi Z-1: slot-normalised ⇒ ~45 दिवसांचा FUT)
        fut = closed_session_bars(feed.futures(symbol, "5minute", s["engine3_fut_days"]), 5, now)
        today_fut = fut[fut["timestamp"].dt.normalize() == m15["timestamp"].iloc[-1].normalize()] if len(fut) else fut
        if not len(today_fut) or float(today_fut["volume"].sum()) <= 0:
            fut, note = None, f"{symbol}: FUT 5M volume (आज) नाही"
    except Exception as exc:                                             # noqa: BLE001
        fut, note = None, f"{symbol}: FUT volume नाही ({type(exc).__name__}: {str(exc)[:80]})"
    if fut is None:
        if str(symbol).upper() in FUT_REQUIRED:                           # Abhi Z-1c: data error ⇒ entry नाही (+ Telegram, दिवसातून एकदा)
            raise FutVolumeMissing(f"{DATA_PROBLEM_FUT} ({note})")
        note += " ⇒ volume NA ⇒ c0 data problem (volume शिवाय entry नाही)"
    return m15, daily, ltf, fut, note


def use_1m(s=None):
    """Setting `engine3_use_1m` (dashboard, default True — Abhi Z-1o (a)). "false" / "0" / "no" / "off" ⇒ False."""
    v = {**DEFAULTS, **(s or {})}["engine3_use_1m"]
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "0", "no", "off", "")
    return bool(v)


def load_m1(feed, symbol, m15, now, s=None):
    """Abhi Z-1o (a): spot 1m ⇒ (df1m | None, info). फक्त बंद 1m (start + 1 ≤ now), session मधले, m15 च्या पहिल्या bar पासून शेवटच्या
    बंद 15M bar च्या bar_end पर्यंत (त्यानंतरचा 1m कधीच नाही ⇒ look-ahead नाही); NIFTY ⇒ holdout rows नाहीत. 1m नाही / त्रुटी ⇒ None +
    कारण (जुना मार्ग; data error नाही). info = payload `m1`: used, setting, rows, m15_covered / m15_bars, note."""
    from decision3 import history as HI
    from elliott import data_policy as DP
    s = {**DEFAULTS, **(s or {})}
    if not use_1m(s):
        return None, {"used": False, "setting": False, "note": "engine3_use_1m = False ⇒ 1m शिवाय (जुना मार्ग)"}

    def fallback(why):
        note = f"1m नाही ⇒ 1m शिवाय (जुना मार्ग): {why}"
        print(f"⚠️ {str(symbol).upper()} engine3: {note}")
        return None, {"used": False, "setting": True, "fallback": True, "note": note}
    try:
        raw = feed.index(symbol, "1minute", s["engine3_m15_days"])
        m1 = closed_session_bars(raw, 1, now)
        if HI.is_nifty(symbol):
            m1 = DP.filter_allowed(m1, "annotation")
    except Exception as exc:                                             # noqa: BLE001 — 1m हा आवश्यक input नाही
        return fallback(f"{type(exc).__name__}: {str(exc)[:120]}")
    if len(m15):
        first, last_end = pd.Timestamp(m15["timestamp"].iloc[0]), pd.Timestamp(m15["bar_end"].iloc[-1])
        m1 = m1[(m1["timestamp"] >= first) & (m1["bar_end"] <= last_end)]
    if not len(m1):
        return fallback("Upstox कडून 1m candles मिळाले नाहीत (या 15M window मध्ये)")
    m1 = m1[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)
    have = set(m1["timestamp"].dt.floor("15min"))
    keys = pd.to_datetime(m15["timestamp"])
    cov = int(keys.isin(have).sum())
    info = {"used": True, "setting": True, "rows": int(len(m1)), "m15_covered": cov, "m15_bars": int(len(m15)), "note": None}
    if len(m15) and pd.Timestamp(keys.iloc[-1]) not in have:
        info["note"] = "शेवटच्या 15M bar चा 1m नाही (intraday उशीर) ⇒ त्या bar चा क्रम 1m शिवाय"
    elif cov < len(m15):
        info["note"] = f"1m {cov}/{len(m15)} 15M bars (बाकी bars चा क्रम 1m शिवाय)"
    return m1, info


def evaluate(symbol, m15, daily, ltf=None, fut=None, s3=None, m1=None):
    """V22 ⇒ शेवटच्या बंद 15M bar चा निर्णय (dict, decide() चा). m1 = spot 1m (Z-1o) ⇒ V22 df1m (swings2 ⇒ levels + rsi2)."""
    import instruments as INS
    prev = INS._current["name"]
    INS.set_current(symbol)                                              # PE.guard चा holdout नियम त्याच instrument चा (NIFTY फक्त)
    try:
        return _evaluate(symbol, m15, daily, ltf, fut, s3, m1)
    finally:
        INS._current["name"] = prev                                      # process-wide instrument पुढच्या caller ला गळू नये


def _evaluate(symbol, m15, daily, ltf, fut, s3, m1=None):
    from decision3 import engine as E3
    from decision3 import history as HI
    m15 = m15.drop(columns=[c for c in ("volume",) if c in m15.columns])   # index volume 0 ≠ खरा volume (NA हवा)
    params = v22_kwargs()
    if fut is not None and "futures" not in params:                      # जुना V22 (futures kwarg नाही) ⇒ joined column
        m15["volume"] = fut_volume_15m(m15, fut).to_numpy()
    kw = {"sealed": HI.sealed_fn(symbol)}
    if s3 is not None:
        kw["s"] = s3
    if "ltf" in params and ltf is not None:
        kw["ltf"] = ltf
    if "futures" in params and fut is not None:
        kw["futures"] = fut
    with fold_cache(symbol.upper()):
        V = E3.V22(m15, m1, daily, **kw)
    return V.decide(len(V.m15) - 1)


def _first_fail(chk):
    for k, v in (chk or {}).items():
        if v and v[0] is False:
            return k, str(v[1])
    return None, None


def _flip_ctx(g):
    """G4 approach context (Abhi Z-1d: context only) ⇒ payload."""
    if not g:
        return None
    return {"a": g.get("a"), "b": g.get("b"), "why": g.get("why"), "b_ratio": (g.get("b_read") or {}).get("ratio"),
            "a_form": (g.get("a_read") or {}).get("form")}


def _zone_sum(z):
    """In-zone study summary ⇒ payload (candles वगळून; RSI divergence सह)."""
    if not z:
        return None
    sm = dict(z.get("summary") or {})
    sm.pop("commit_bar", None)
    return {"from": z.get("from"), "to": z.get("to"), **sm}


def row_from_v22(symbol, r, now_fn):
    """V22 decide dict ⇒ engine_signal store row (decision2 च्याच columns ⇒ adapter / bots बदलत नाहीत)."""
    lv = r.get("level") or {}
    rk = r.get("risk") or {}
    d = None
    if lv.get("role") in ("support", "resistance"):
        d = 1 if lv["role"] == "support" else -1
    gate, why = _first_fail(r.get("checklist"))
    reason = r.get("why") or why or ""
    payload = {"engine": "decision3", **{k: r.get(k) for k in ("ts", "bar_end", "daily_trend", "trend_used", "trend_resolution",
                                                            "weekly_trend", "daily_phase", "mature", "trend_notes", "trend_cap",
                                                            "mark", "conviction", "commitment_form", "missing", "checklist", "volume_note",
                                                            "m1")},
               "level": {k: lv.get(k) for k in ("id", "role", "lo", "hi", "births", "sweeps", "dist", "state", "broken_ts", "far_swing",
                                                "flipped_ts")} if lv else None,
               "risk": rk or None, "flip_context": _flip_ctx(r.get("flip_retest")), "zone_read": _zone_sum(r.get("zone_read")),
               "data_problem": (r.get("commit") or {}).get("data_problem")}
    return {"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(r["bar_end"])), "computed_at": str(now_fn()),
            "decision": r.get("decision"), "gate": gate, "direction": d, "level_lo": lv.get("lo"), "level_hi": lv.get("hi"),
            "entry": rk.get("entry"), "invalidation": rk.get("sl"), "target": rk.get("target"), "grade": r.get("conviction"),
            "reason": str(reason)[:300], "payload": json.dumps(payload, ensure_ascii=False, default=str)[:20000]}


def compute(symbol, feed, now, s=None):
    m15, daily, ltf, fut, note = build_inputs(feed, symbol, now, s)
    m1, m1_info = load_m1(feed, symbol, m15, pd.Timestamp(now), s)
    r = evaluate(symbol, m15, daily, ltf, fut, m1=m1)
    r["volume_note"] = note
    r["m1"] = m1_info                                                    # Z-1o: 1m वापरला का / fallback कारण (row payload)
    return r
