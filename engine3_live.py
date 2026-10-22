"""engine3_live.py — decision3 (थर v2.2, method engine: trend → area → pullback → commitment + c1; R:R नाही — Abhi 13 Oct) चा **live** feed (Abhi: one bot, Tuesday PAPER).

प्रत्येक बंद 15M candle नंतर (cron, `scripts/engine_signal_run.py --engine decision3`) एका symbol साठी:
  • 15M spot (Upstox, `engine3_m15_days` दिवस) — फक्त बंद candles; NIFTY ⇒ `data_policy.filter_allowed(..., "annotation")` (holdout row नाही).
  • Daily (Upstox 'day', ~10 वर्षं, आजचा अपूर्ण Daily bar नाही) — Q33: Daily holdout candles फक्त warm-up input (level_reaction.daily_trend
    प्रमाणेच); output मध्ये sealed तारीख नाही (`history.sealed_fn`). Weekly = Daily वरून (V22 स्वतः).
  • 5M spot (LTF: c1 5M CHoCH) ⇒ V22 `ltf=`; नसेल ⇒ fail-closed. Front-month FUT 5M volume (c0 dominant candle + volume) ⇒ V22
    `futures=` (expiry सह; जुना V22 ⇒ m15 joined `volume`; `engine3_fut_days` — raw FUT bars, method §3). Abhi Z-1c:
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
import math
import os
import pickle
import urllib.parse

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = {"engine3_m15_days": 90, "engine3_daily_days": 3650, "engine3_ltf_days": 10,
            "engine3_fut_days": 45,                                       # FUT history window (raw bars, method §3; the legacy slot baseline needed ≥ 21 sessions)
            "engine3_use_1m": True,                                       # Abhi Z-1o (a): 1m spot ⇒ swings2 (1m चा window = engine3_m15_days)
            "engine3_cache_keep_days": 3}                                 # data/engine3_cache: इतक्या दिवसांपेक्षा जुन्या files (mtime) run सुरू होताना काढतो
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


class TokenRejected(EngineDataError):
    """Upstox ने token नाकारला (HTTP 401 / 403, उदा. UDAPI100050 "Invalid token used to access API" — दुसऱ्या system साठी नवा token
    काढला की bot चा token रद्द होतो) ⇒ bot आंधळा. EngineDataError च ⇒ आजचे सर्व fail-closed मार्ग तसेच; caller (engine_signal_run)
    वेगळी Telegram ओळ (दर 15M bar). Message मध्ये token कधीच नाही."""
    token_rejected = True


TOKEN_REJECTED_CODES = ("UDAPI100050",)                                   # Upstox: "Invalid token used to access API"


def _upstox_code(body=None, error=None):
    """Upstox errorCode (UDAPI…) body / error text मधून; नाही ⇒ ""."""
    import re
    try:
        text = json.dumps(body, default=str) if body is not None else ""
    except (TypeError, ValueError):
        text = ""
    m = re.search(r"UDAPI\d+", f"{text} {error or ''}")
    return m.group(0) if m else ""


def token_rejected(status, body=None, error=None):
    """एकच detector: Upstox ने token नाकारला का? HTTP 401 / 403 (authenticated endpoint) किंवा body / error मध्ये UDAPI100050 /
    "Invalid token". 200 / network error (status None) ⇒ False (network चूक = token नाकारला नाही)."""
    if status is None or status == 200:
        return False
    if status in (401, 403):
        return True
    text = f"{_upstox_code(body, error)} {error or ''}".lower()
    return any(c.lower() in text for c in TOKEN_REJECTED_CODES) or "invalid token" in text


def raise_if_token_rejected(what, status, body=None, error=None):
    """token_rejected ⇒ TokenRejected (फक्त HTTP status + Upstox code, token नाही). नाहीतर काही नाही (आजचा मार्ग तसाच)."""
    if token_rejected(status, body, error):
        code = _upstox_code(body, error)
        raise TokenRejected(f"{what}: Upstox token rejected (HTTP {status}{' ' + code if code else ''})")


PROFILE_PATH = "/user/profile"                                            # = scripts/paper_status.PROFILE_URL (test तपासतो)
PROFILE_TIMEOUT = (5, 5)                                                  # (connect, read) सेकंद — run सुरुवातीची तपासणी लहानच


def profile_url():
    """GET /v2/user/profile — verify_opportunity_data_availability.BASE_V2 वरून (scripts/ import नाही ⇒ VPS वर ImportError नाही)."""
    import verify_opportunity_data_availability as V
    return f"{V.BASE_V2}{PROFILE_PATH}"


def profile_check(token, get=None):
    """Run सुरुवातीची एकच स्वस्त authenticated तपासणी: GET /v2/user/profile (paper_status सारखाच URL), retry नाही, timeout (5, 5).
    रिटर्न "ok" / "rejected (HTTP 401 UDAPI100050)" / "unknown (…)" (network / इतर status ⇒ unknown = आजचा मार्ग). कधीच raise नाही;
    token कधीच output मध्ये नाही."""
    try:
        if get is None:
            import verify_opportunity_data_availability as V
            get = lambda url, tok: V._get(url, tok, timeout=PROFILE_TIMEOUT, retries=0)  # noqa: E731
        status, body, error = get(profile_url(), token)
    except Exception as exc:                                             # noqa: BLE001
        return f"unknown ({type(exc).__name__})"
    if status == 200:
        return "ok"
    if token_rejected(status, body, error):
        code = _upstox_code(body, error)
        return f"rejected (HTTP {status}{' ' + code if code else ''})"
    return f"unknown (HTTP {status})" if status is not None else "unknown (network)"


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
    raise_if_token_rejected(f"{symbol}: FUT resolve", status, body, error)
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
        self.last_session = None                                         # 15M history मधला शेवटचा (आजच्या आधीचा) session दिवस

    def _series(self, key, interval, days, contract=None):
        out = self._history(key, interval, days)
        if interval == "15minute":                                       # 1m history cache ची "पूर्ण" खूण (सुट्टी ⇒ तोच शेवटचा दिवस)
            self.last_session = _last_date(out, self.today) or self.last_session
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
            raise_if_token_rejected(f"{key} {interval} history", r["status"], None, r["error"])
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
        raise_if_token_rejected(f"{key} {interval} intraday", st, body, err)
        if st != 200:
            raise EngineDataError(f"{key} {interval} intraday HTTP {st} ({str(err)[:80]})")
        return list(((body or {}).get("data") or {}).get("candles") or [])

    def expected_last_session(self):
        """History मध्ये असायलाच हवा तो शेवटचा दिवस: 15M history चा शेवटचा session (सुट्टी असेल तर तो आपोआप आधीचा दिवस); 15M अजून
        मागवला नसेल ⇒ कालचा weekday (जुना नियम)."""
        if self.last_session is not None:
            return self.last_session
        prev = self.today - dt.timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= dt.timedelta(days=1)
        return prev

    def _history_cached(self, key, interval, days):
        """आधीचे दिवस बदलत नाहीत ⇒ history दिवसातून एकदा (disk cache: key + interval + days + आजची तारीख + अपेक्षित शेवटचा session).
        अपेक्षित दिवस = 15M history चा शेवटचा session ⇒ सुट्टीनंतर cache भरतो (आधी कालचा weekday ⇒ सुट्टी दिवशी cache कधीच नाही ⇒ 90 दिवस
        1m प्रत्येक cycle). 15M ला नंतर नवा दिवस आला ⇒ नवी key ⇒ पुन्हा fetch. Cache त्रुटी ⇒ साधा fetch."""
        tag = "".join(ch if ch.isalnum() else "_" for ch in f"{key}_{interval}_{int(days)}")
        want = self.expected_last_session()
        p = os.path.join(cache_dir(), f"hist_{tag}_{self.today.isoformat()}_{want.isoformat()}.pkl")
        try:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    return pickle.load(f)
        except Exception:                                                # noqa: BLE001
            pass
        out = self._history(key, interval, days)
        last = _last_date(out, self.today)
        if last is None or last < want:                                  # अपेक्षित शेवटचा दिवस अजून नाही (उशीर) ⇒ cache नाही, पुढच्या cycle ला पुन्हा
            return out
        try:
            os.makedirs(cache_dir(), exist_ok=True)
            tmp = f"{p}.{os.getpid()}.tmp"                               # process प्रमाणे tmp (दोन runs एकाच वेळी ⇒ एकमेकांची tmp नाही)
            with open(tmp, "wb") as f:
                pickle.dump(out, f)
            os.replace(tmp, p)
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
                raise_if_token_rejected(f"{key} {interval} {d} history", r["status"], None, r["error"])
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


def _last_date(candles, today):
    """Candles list मधला आजच्या आधीचा शेवटचा दिवस (नाही ⇒ None)."""
    return max((d for d in (pd.Timestamp(str(c[0])[:10]).date() for c in candles or []) if d < today), default=None)


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
                    tmp = f"{p}.{os.getpid()}.tmp"
                    with open(tmp, "wb") as f:
                        pickle.dump(res, f)
                    os.replace(tmp, p)
            except Exception:                                            # noqa: BLE001
                pass
            return res
        DD.fold = fold
        return self

    def __exit__(self, *exc):
        self.DD.fold = self.orig
        return False


CACHE_PREFIXES = ("hist_", "fold_")                                        # फक्त हेच (आणि त्यांचे .tmp) prune होतात


def cache_keep_days(v=None):
    """`engine3_cache_keep_days` ⇒ float ≥ 1. रिकामं / चुकीचं / ऋण ⇒ default (3); 0–1 ⇒ 1 (आजच्या cache files कधीच नाही काढत)."""
    dflt = float(DEFAULTS["engine3_cache_keep_days"])
    try:
        k = dflt if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return dflt
    if k != k or k < 0:                                                  # NaN / ऋण ⇒ default
        return dflt
    return max(1.0, k)


def prune_cache(keep_days=None, now=None):
    """data/engine3_cache मधल्या फक्त engine3 cache files (`hist_*` / `fold_*`, .tmp उरलेल्यांसह) — `keep_days` (setting
    `engine3_cache_keep_days`, किमान 1) पेक्षा जुन्या (mtime) — काढतो. इतर files ना हात नाही. एक listdir, स्वस्त. कधीच raise नाही."""
    keep_days = cache_keep_days(keep_days)
    d = cache_dir()
    if not os.path.isdir(d):
        return
    cut = (now or pd.Timestamp.now()).timestamp() - keep_days * 86400
    for f in os.listdir(d):
        if not f.startswith(CACHE_PREFIXES) or not (f.endswith(".pkl") or f.endswith(".tmp")):
            continue
        try:
            p = os.path.join(d, f)
            if os.path.isfile(p) and os.path.getmtime(p) < cut:
                os.remove(p)
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------ inputs ⇒ V22
def v22_kwargs():
    """V22 चे optional live kwargs (ltf / futures) आहेत का — confirmation branch merge आधी / नंतर दोन्हीवर चालावं."""
    from decision3 import engine as E3
    return set(inspect.signature(E3.V22.__init__).parameters)


def build_inputs(feed, symbol, now, s=None, levels_only=False):
    """(m15, daily, ltf5, fut5|None, volume note|None). 15M / Daily / 5M LTF अपुरा ⇒ EngineDataError (fail-closed); FUT नाही ⇒ volume NA.
    levels_only (pre-open areas) ⇒ फक्त 15M + Daily (ltf / fut / note = None; शेवटचा उपलब्ध बंद bar)."""
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
    if not levels_only and pd.Timestamp(m15["bar_end"].iloc[-1]) < want and SESSION_OPEN <= (want.hour, want.minute) <= SESSION_CLOSE:
        raise EngineDataError(f"{symbol}: शेवटचा बंद 15M ({want:%H:%M}) अजून Upstox कडे नाही (last {m15['bar_end'].iloc[-1]:%H:%M})")
    dd = feed.index(symbol, "day", s["engine3_daily_days"])
    if dd is None or len(dd) < 30:
        raise EngineDataError(f"{symbol}: Daily candles अपुरे ({0 if dd is None else len(dd)})")
    daily = LR.prepare_daily(_naive(dd)[["timestamp", "open", "high", "low", "close"]], now.normalize())
    if len(daily) < 30:
        raise EngineDataError(f"{symbol}: Daily candles अपुरे ({len(daily)})")
    if levels_only:
        return m15, daily, None, None, None
    ltf = closed_session_bars(feed.index(symbol, "5minute", s["engine3_ltf_days"]), 5, now)
    if HI.is_nifty(symbol):
        ltf = DP.filter_allowed(ltf, "annotation")
    if not len(ltf) or ltf["timestamp"].iloc[-1].normalize() != m15["timestamp"].iloc[-1].normalize():
        raise EngineDataError(f"{symbol}: 5M spot (LTF) data नाही ⇒ c1 CHoCH तपासता येत नाही")
    fut, note = None, None
    try:                                                                 # c0 / a2 volume (raw FUT bars, method §3; approach leg may reach back)
        fut = closed_session_bars(feed.futures(symbol, "5minute", s["engine3_fut_days"]), 5, now)
        today_fut = fut[fut["timestamp"].dt.normalize() == m15["timestamp"].iloc[-1].normalize()] if len(fut) else fut
        if not len(today_fut) or float(today_fut["volume"].sum()) <= 0:
            fut, note = None, f"{symbol}: FUT 5M volume (आज) नाही"
    except TokenRejected:                                                # token नाकारला ⇒ "FUT volume missing" नाही, खरं कारण
        raise
    except Exception as exc:                                             # noqa: BLE001
        fut, note = None, f"{symbol}: FUT volume नाही ({type(exc).__name__}: {str(exc)[:80]})"
    if fut is None:
        if str(symbol).upper() in FUT_REQUIRED:                           # Abhi Z-1c: data error ⇒ entry नाही (+ Telegram, दिवसातून एकदा)
            raise FutVolumeMissing(f"{DATA_PROBLEM_FUT} ({note})")
        note += " ⇒ volume NA ⇒ c0 data problem (volume शिवाय entry नाही)"
    return m15, daily, ltf, fut, note


def use_1m(s=None):
    """Setting `engine3_use_1m` (dashboard, default True — Abhi Z-1o (a)). "false" / "0" / "no" / "off" ⇒ False; None / "" (रिकामं) ⇒
    default (True)."""
    v = (s or {}).get("engine3_use_1m")
    if v is None or (isinstance(v, str) and not v.strip()):
        v = DEFAULTS["engine3_use_1m"]
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "0", "no", "off")
    return bool(v)


def swing_scale(s=None):
    """Abhi calibration (layer 1 ✅): advanced dashboard `engine3_swing_k_d1` / `engine3_swing_k_d2` ⇒ V22 settings {"swing_k": {1: k, 2: k}}.
    रिकामं / None ⇒ None (swings2 चा approved scale, D1 = 4, D2 = 6). Bad value ⇒ ValueError (engine run fails closed, Telegram)."""
    k = {}
    for d in (1, 2):
        v = (s or {}).get(f"engine3_swing_k_d{d}")
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        k[d] = float(v)
    if not k:
        return None
    from decision3 import engine as E3
    E3.swing_scale({"swing_k": k})                                       # refuse a bad value here (never blamed on the 1m fallback)
    return {"swing_k": k}


class SettingError(ValueError):
    """A bad dashboard `engine3_*` setting (not a data problem): the engine run fails closed and the Telegram line says to fix the
    setting on the dashboard (`setting_error`, read by scripts/engine_signal_run.py)."""
    setting_error = True


DAILY_PIVOT_N_MAX = 5                                                      # registered range 1/2/3 (+ margin): a huge N would leave the
                                                                           # Daily trend unknown and silently stop entries


def daily_pivot_n(s=None):
    """Abhi (L1-c): advanced dashboard `engine3_daily_pivot_n` ⇒ V22 settings {"daily_pivot_n": N} (swing = N bars on both sides, for
    the Daily and the Weekly parent folds; live decision and pre-open levels). रिकामं / None / decision3's default (provisional N = 2) ⇒
    None (today's behaviour). Not a whole number in 1..DAILY_PIVOT_N_MAX ⇒ ValueError (the engine run fails closed: error row +
    Telegram) — before any data fetch."""
    from decision3 import settings as S3
    v = (s or {}).get("engine3_daily_pivot_n")
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        if isinstance(v, bool):
            raise ValueError
        f = float(str(v).strip())
        if not (math.isfinite(f) and f == int(f) and 1 <= f <= DAILY_PIVOT_N_MAX):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(f"engine3_daily_pivot_n = {v!r} — a whole number 1..{DAILY_PIVOT_N_MAX} "
                         f"(empty = {S3.DEFAULTS['daily_pivot_n']}, provisional)") from None
    n = int(f)
    return None if n == S3.DEFAULTS["daily_pivot_n"] else {"daily_pivot_n": n}


# Abhi (live switches): each finished Chart Reader layer can fall back to its legacy what-if from the dashboard (advanced, 15M SRv2 engine
# block) without a deploy. Dashboard key ⇒ (decision3 V22 setting, allowed values — the method first (= decision3's default), then the
# registered legacy what-ifs (decision3/settings.py REGISTER), label). Empty / None / the method ⇒ V22 gets nothing ⇒ today's behaviour
# byte-for-byte.
METHOD_SWITCHES = {
    "engine3_zone_visit_rule": ("zone_visit_rule", ("structure", "close_away", "touch_window"), "layer 3 visit"),
    "engine3_commit_volume_rule": ("commit_volume_rule", ("approach_and_opposite", "opposite"), "layer 3 commitment volume"),
    "engine3_line_rule": ("line_rule", ("logic", "sigma"), "layer 4 lines"),
    "engine3_div_degree_rule": ("div_degree_rule", ("zone", "all"), "layer 5 RSI divergence"),
    "engine3_verdict_rule": ("verdict_rule", ("method", "score"), "layer 6a verdict"),
    # Abhi 21 Oct (PA standard §3): the entry models E1–E4 decide (decision3 default); legacy_k = the old ③ BOS + K pullback gate + the
    # old visit end, exactly as before the models — the no-deploy fallback for the live PAPER engine.
    "engine3_entry_gate": ("entry_gate", ("models", "legacy_k"), "layer 3 entry gate (entry models E1–E4)"),
    # Abhi 21 Oct (PA standard T1, ✅ deploy): the Daily leg's nature by comparison with its neighbouring legs; elliott = the old reading.
    "engine3_daily_leg_read": ("daily_leg_read", ("compare", "elliott"), "layer 1 Daily leg nature"),
    # Lead (provisional): overlapping same-role areas in one visit = one location (one signal per model per cluster); area = per area.
    "engine3_entry_cluster_rule": ("entry_cluster_rule", ("cluster", "area"), "layer 3 entry models: one location per overlapping cluster"),
    # Abhi 21 Oct (PA standard T7): the range from structure (Daily / Weekly fold + 1H / 15M); c13 = two equal highs + two equal lows.
    "engine3_daily_range_rule": ("daily_range_rule", ("structure", "c13"), "layer 1 range (Daily / Weekly / 1H / 15M)"),
    "engine3_range_state_rule": ("range_state_rule", ("structure", "overlap"), "row range state (context)"),
}


def method_switches(s=None):
    """Dashboard `engine3_*` layer switches ⇒ {V22 key: legacy value} — only the ones set away from the method (empty / the method ⇒
    omitted). Unknown value, or a legacy visit rule without the legacy commitment volume (V22: "never a silent half-rule") ⇒ ValueError
    with the reason (the engine run fails closed: error row + Telegram) — before any data fetch or instrument switch."""
    out = {}
    for key, (v22_key, allowed, _label) in METHOD_SWITCHES.items():
        v = (s or {}).get(key)
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        v = str(v).strip().lower()
        if v not in allowed:
            raise ValueError(f"{key} = {v!r} — allowed: {' / '.join(allowed)} (empty = {allowed[0]}, the method)")
        if v != allowed[0]:
            out[v22_key] = v
    if out.get("zone_visit_rule") and out.get("commit_volume_rule") != "opposite":
        raise ValueError(f"engine3_zone_visit_rule = {out['zone_visit_rule']!r} (legacy) knows no approach leg — set "
                         "engine3_commit_volume_rule = 'opposite' with it")
    return out


# Model C (DECISIONS 32, T-3): the dashboard switches, ALL default OFF (the opposite of E1–E4) until Abhi switches it on after the
# replay. engine3_model_c_on = the model (V22 `model_c`) and its live signal switch; engine3_model_c_<a…f>_on = each sub-way (V22
# `model_c_subs`); engine3_c_window / engine3_c_a_nature / engine3_c_projections = the model's own settings (empty = decision3's default).
MODEL_C_KEY = "engine3_model_c_on"


def model_c_sub_key(sub):
    """"C-a" ⇒ "engine3_model_c_a_on"."""
    return f"engine3_model_c_{str(sub).split('-')[-1].lower()}_on"


def _truthy(v, default=False):
    if v is None or (isinstance(v, str) and not v.strip()):
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "0", "no", "off")
    return bool(v)


def model_c_settings(s=None):
    """Dashboard model C keys ⇒ V22 settings; model C off (default) ⇒ None (V22 never reads model C — today's rows). Bad value ⇒
    ValueError (fail closed)."""
    from decision3 import model_c as MDC
    from decision3 import settings as S3
    s = s or {}
    if not _truthy(s.get(MODEL_C_KEY), False):
        return None
    out = {"model_c": "on", "model_c_subs": [x for x in S3.MODEL_C_SUBS if _truthy(s.get(model_c_sub_key(x)), False)]}
    for key, v22 in (("engine3_c_window", "c_window"), ("engine3_c_a_nature", "c_a_nature")):
        v = s.get(key)
        if v is not None and str(v).strip():
            out[v22] = str(v).strip().lower()
    pr = c_projections_of(s.get("engine3_c_projections"))
    if pr is not None:
        out["c_projections"] = pr
    MDC.validate({**S3.DEFAULTS, **out})
    return out


def c_projections_of(v):
    """Dashboard `engine3_c_projections` (display / context only, C-7) ⇒ a tuple of positive ratios or None (decision3's default).
    Empty pieces are skipped ("1, 1.618," ⇒ (1.0, 1.618)); an unreadable value never stops the engine — a warning, then the default."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        parts = [x for x in (v.split(",") if isinstance(v, str) else v) if not (isinstance(x, str) and not x.strip())]
        out = tuple(float(x) for x in parts)
        if not out or not all(math.isfinite(r) and r > 0 for r in out):
            raise ValueError
        return out
    except (TypeError, ValueError):
        print(f"⚠️ engine3_c_projections = {v!r} unreadable (ratios separated by commas, display only) ⇒ the default is used")
        return None


def v22_settings(s=None):
    """Dashboard `engine3_*` ⇒ V22 settings (`s`) for the live decision and the pre-open levels: the swing scale (layer 1), the Daily
    pivot size (L1-c) + the layer switches. Nothing set ⇒ None (V22 on decision3's defaults = the method, today's behaviour). Bad value ⇒
    ValueError (fail closed)."""
    try:
        out = {**(swing_scale(s) or {}), **(daily_pivot_n(s) or {}), **method_switches(s), **(model_c_settings(s) or {})}
    except ValueError as exc:                                            # a setting error, not a data problem (Telegram says so)
        raise SettingError(str(exc)) from exc
    return out or None


# ------------------------------------------------------------------------------------------------ dashboard (advanced) parsing
def switch_label(key, v):
    """Dashboard option label: the method ⇒ "<v> — method (default)"; a legacy value ⇒ "legacy what-if: <v>"."""
    return f"{v} — method (default)" if v == METHOD_SWITCHES[key][1][0] else f"legacy what-if: {v}"


def switch_choice(key, stored):
    """Dashboard: a stored switch ⇒ (value to show, warning | None). Empty ⇒ the method; unknown ⇒ the method + a warning (a bad stored
    value never breaks the page; saving then stores the method)."""
    allowed = METHOD_SWITCHES[key][1]
    v = str(stored if stored is not None else "").strip().lower()
    if not v:
        return allowed[0], None
    if v not in allowed:
        return allowed[0], f"{key}: stored {v!r} unknown ⇒ showing the method ({allowed[0]}); saving stores the method"
    return v, None


def switches_to_save(choices):
    """Dashboard save: {key: chosen value} ⇒ ({key: stored value}, error | None). The method / unknown ⇒ "" (empty = the method). An
    incoherent combo (`method_switches` refuses it, e.g. a legacy visit without the legacy commitment volume) ⇒ visit + commitment volume
    stored as the method, with the reason."""
    out = {}
    for key, (_v22, allowed, _label) in METHOD_SWITCHES.items():
        v = str((choices or {}).get(key) or "").strip().lower()
        out[key] = v if v in allowed[1:] else ""
    try:
        method_switches(out)
    except ValueError as exc:
        out["engine3_zone_visit_rule"] = out["engine3_commit_volume_rule"] = ""
        return out, str(exc)
    return out, None


def pivot_n_choice(stored):
    """Dashboard: stored `engine3_daily_pivot_n` ⇒ (N to show, warning | None). Empty ⇒ decision3's provisional N (2); bad ⇒ that + a
    warning (saving then stores empty)."""
    from decision3 import settings as S3
    try:
        got = daily_pivot_n({"engine3_daily_pivot_n": stored})
    except ValueError as exc:
        return int(S3.DEFAULTS["daily_pivot_n"]), f"{exc} ⇒ showing {S3.DEFAULTS['daily_pivot_n']}; saving stores empty"
    return (got or {}).get("daily_pivot_n", int(S3.DEFAULTS["daily_pivot_n"])), None


def pivot_n_to_save(n):
    """Dashboard save: N ⇒ stored value. decision3's provisional N (2) or a bad value ⇒ "" (empty = 2); otherwise the whole number."""
    try:
        got = daily_pivot_n({"engine3_daily_pivot_n": n})
    except ValueError:
        return ""
    return "" if got is None else int(got["daily_pivot_n"])


def load_m1(feed, symbol, m15, now, s=None):
    """Abhi Z-1o (a): spot 1m ⇒ (df1m | None, info). फक्त बंद 1m (start + 1 ≤ now), session मधले, m15 च्या पहिल्या bar पासून शेवटच्या
    बंद 15M bar च्या bar_end पर्यंत (त्यानंतरचा 1m कधीच नाही ⇒ look-ahead नाही); NIFTY ⇒ holdout rows नाहीत. 1m नाही / त्रुटी ⇒ None +
    कारण (जुना मार्ग; data error नाही). info = payload `m1`: used, setting, rows, m15_covered (1m rows असलेले 15M bars) / m15_bars,
    m15_complete (V22 नंतर: swings2 m1_status "complete" bars — 1m चे high / low 15M शी जुळतात), note."""
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
    except TokenRejected:                                                # token नाकारला ⇒ 1m fallback नाही, fail-closed
        raise
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


def evaluate(symbol, m15, daily, ltf=None, fut=None, s3=None, m1=None, m1_info=None):
    """V22 ⇒ शेवटच्या बंद 15M bar चा निर्णय (dict, decide() चा). m1 = spot 1m (Z-1o) ⇒ V22 df1m (swings2 ⇒ levels + rsi2).
    m1_info (load_m1 चा payload `m1`) ⇒ m15_complete भरतो / V22 1m सह त्रुटी ⇒ fallback नोंद."""
    import instruments as INS
    prev = INS._current["name"]
    INS.set_current(symbol)                                              # PE.guard चा holdout नियम त्याच instrument चा (NIFTY फक्त)
    try:
        return _evaluate(symbol, m15, daily, ltf, fut, s3, m1, m1_info)
    finally:
        INS._current["name"] = prev                                      # process-wide instrument पुढच्या caller ला गळू नये


def m1_complete(symbol, V, info):
    """V22 (swings2) नंतर: किती 15M bars चा 1m "complete" (m1_status — ≥ 15 rows, high / low तंतोतंत जुळतात) ⇒ info["m15_complete"].
    Rows आहेत पण complete 0 ⇒ ⚠️ log + note (1m चे high / low 15M शी जुळत नाहीत ⇒ swings2 1m क्रम कुठेच वापरत नाही)."""
    if info is None:
        return
    res = getattr(V, "res", None)
    stream = res.get("stream") if isinstance(res, dict) else None
    if stream is None:
        return
    n = sum(1 for x in stream if x.get("m1_status") == "complete")
    info["m15_complete"] = int(n)
    if n == 0 and info.get("rows"):
        note = (f"1m rows {info['rows']} पण complete 0/{info.get('m15_bars')} — 1m चे high / low 15M candles शी जुळत नाहीत "
                "(वेगळा source / adjustment?) ⇒ swings2 1m क्रम वापरत नाही (परिणाम 1m शिवाय सारखाच)")
        print(f"⚠️ {str(symbol).upper()} engine3: {note}")
        info["note"] = f"{info['note']}; {note}" if info.get("note") else note


def m1_v22_failed(symbol, info, exc):
    """V22 1m सह त्रुटी ⇒ 1m शिवाय पुन्हा (1m आवश्यक input नाही ⇒ fail-closed नाही); कारण payload `m1` मध्ये + log."""
    note = f"V22 1m सह त्रुटी ⇒ 1m शिवाय (जुना मार्ग): {type(exc).__name__}: {str(exc)[:120]}"
    print(f"⚠️ {str(symbol).upper()} engine3: {note}")
    if info is not None:
        info.update(used=False, fallback=True, note=note)


def _evaluate(symbol, m15, daily, ltf, fut, s3, m1=None, m1_info=None):
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

    def run(df1m):
        with fold_cache(symbol.upper()):
            V = E3.V22(m15, df1m, daily, **kw)
        return V, V.decide(len(V.m15) - 1)
    if m1 is None:
        return run(None)[1]
    try:
        V, r = run(m1)
    except Exception as exc:                                             # noqa: BLE001 — 1m मुळे fail-closed नाही: एकदा 1m शिवाय
        m1_v22_failed(symbol, m1_info, exc)
        return run(None)[1]
    m1_complete(symbol, V, m1_info)
    return r


TRADEABLE_STATES = ("ACTIVE", "TESTED", "FLIPPED")                         # BROKEN / DEAD (किंवा अज्ञात) ⇒ pre-open मध्ये नाही


def tradeable_levels(levels):
    """फक्त trade करता येणारे पट्टे: `state` field असेल (decision3 #325 नंतर) ⇒ ACTIVE / TESTED / FLIPPED ठेवा, BROKEN / DEAD (अज्ञात) वगळा;
    field नसेल (main: snapshot फक्त जिवंत levels देतो) ⇒ सगळे ठेवा. Abhi Z-1u: `trade_location` False (Weekly context; Daily पट्टा 1H zone
    ने झाकलेला) ⇒ वगळा — प्रत्येक timeframe चा स्वतःचा पट्टा, confluence फक्त label (`confluence_label`)."""
    return [x for x in levels or [] if (x.get("state") is None or str(x["state"]).upper() in TRADEABLE_STATES)
            and x.get("trade_location", True)]


def watched_levels(symbol, feed, now, s=None, keep=None):
    """Pre-open (Abhi): engine (V22 ② Levels) चे शेवटच्या बंद 15M bar ला जिवंत levels — [{"role", "lo", "hi", …}] (`Levels.snapshot`).
    पट्टे swing / base candles वरून (TA4, lo < hi). 15M + Daily (+ 1m, live `compute` सारखंच — Z-1o: s = `ES.engine3_settings(sym)`,
    `engine3_use_1m` False ⇒ 1m मागवत नाही) पुरे (levels ला LTF / FUT लागत नाही ⇒ c1 इशारा दाबला). 1m नाही / V22 1m सह त्रुटी ⇒ 1m
    शिवाय (कारण log). Data नाही ⇒ EngineDataError (caller NA + कारण). keep (dict) ⇒ keep["V"] = तोच V22 (pre-open charts तोच data
    वापरतात — पुन्हा fetch / build नाही); None ⇒ जुनंच."""
    import contextlib
    import io
    import warnings
    import instruments as INS
    from decision3 import engine as E3
    from decision3 import history as HI
    s3 = v22_settings(s)                                                 # live compute सारखेच V22 settings (swing scale + layer switches); bad ⇒ raise
    m15, daily, _l, _f, _n = build_inputs(feed, symbol, now, s, levels_only=True)
    m1, info = load_m1(feed, symbol, m15, pd.Timestamp(now), s)           # live compute सारखाच 1m ⇒ pre-open = engine चे पट्टे
    m15 = m15.drop(columns=[c for c in ("volume",) if c in m15.columns])
    prev = INS._current["name"]                                          # before the process-wide instrument changes
    INS.set_current(symbol)

    def build(df1m):
        with fold_cache(symbol.upper()), warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            return E3.V22(m15, df1m, daily, sealed=HI.sealed_fn(symbol), **({"s": s3} if s3 else {}))
    try:
        if m1 is None:
            V = build(None)
        else:
            try:
                V = build(m1)
            except Exception as exc:                                     # noqa: BLE001 — 1m मुळे NA नाही: एकदा 1m शिवाय
                m1_v22_failed(symbol, info, exc)
                V = build(None)
            else:
                m1_complete(symbol, V, info)
    finally:
        INS._current["name"] = prev
    if keep is not None:
        keep["V"] = V
    return tradeable_levels(V.levels.snapshot(len(V.m15) - 1))


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
               "level": {k: lv.get(k) for k in ("id", "tf", "role", "lo", "hi", "births", "sweeps", "dist", "state", "broken_ts", "far_swing",
                                                "flipped_ts", "confluence_label")} if lv else None,   # Abhi Z-1u: confluence = label
               "risk": rk or None, "flip_context": _flip_ctx(r.get("flip_retest")), "zone_read": _zone_sum(r.get("zone_read")),
               "data_problem": (r.get("commit") or {}).get("data_problem"), "volume_measure": r.get("volume_measure"),
               "range_state": r.get("range_state"), "watch_list": r.get("watch_list"), "reader": reader_facts(r)}
    if "entries" in r:                                                   # entry models E1–E4 (decision data — fit_payload never drops them)
        payload["entries"] = compact_entries(r.get("entries"))
        payload["armed"] = compact_armed(r.get("armed"))
        if r.get("legacy_k_gate") is not None:                           # old step ③: a logged diagnostic only (first to go when too long)
            payload["legacy_k_gate"] = r.get("legacy_k_gate")
    if isinstance(r.get("model_c"), dict):                               # model C on (DECISIONS 32): the cycle in one line (display)
        cy = r["model_c"].get("cycle") or {}
        payload["model_c"] = {"phase": cy.get("phase"), "cycle": cy.get("id"), "why": str(cy.get("why") or r["model_c"].get("why")
                                                                                         or "")[:200],
                              "windows": cy.get("windows"), "entries": r["model_c"].get("entries"), "error": r["model_c"].get("error")}
    return {"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(r["bar_end"])), "computed_at": str(now_fn()),
            "decision": r.get("decision"), "gate": gate, "direction": d, "level_lo": lv.get("lo"), "level_hi": lv.get("hi"),
            "entry": rk.get("entry"), "invalidation": rk.get("sl"), "target": rk.get("target"), "grade": r.get("conviction"),
            "reason": str(reason)[:300], "payload": fit_payload(payload)}


def reader_facts(r):
    """Approval card summary (setting `approval_card_layout`, display only): the reading's own facts COPIED from the V22 row — the
    layer 6a evidence list (required set present / absent, confirming pieces present / absent / NA), ① trend and ③ area as the
    checklist read them, the handover's form (sharp_reversal = the fast two-candle form) and the LTF label of the CHoCH. Nothing is
    re-read or scored; a missing fact stays None. Never raises (a display field never blocks a row)."""
    try:
        chk = r.get("checklist") or {}
        cm = r.get("commit") or {}

        def first(k):
            v = chk.get(k)
            return None if not isinstance(v, (list, tuple)) or not v or v[0] is None else bool(v[0])
        return {"evidence_list": r.get("evidence_list"), "trend": first("①"), "area": first("③"),
                "handover_form": (cm.get("handover_state") or {}).get("form"), "ltf": (cm.get("choch") or {}).get("label")}
    except Exception:                                                    # noqa: BLE001 — display only
        return None


ENTRY_KEYS = ("model", "name", "direction", "side", "object", "visit_id", "visit_start", "key", "trigger_ts", "trigger_bar_end",
              "entry_ref", "evidence", "evidence_list", "label")
AREA_KEYS = ("id", "tf", "role", "lo", "hi", "state", "object")
ARMED_MODEL_KEYS = ("status", "at", "waiting", "note")


def _area_of(a):
    return {k: a.get(k) for k in AREA_KEYS if k in a or k in ("id", "tf", "lo", "hi", "state")} if isinstance(a, dict) else None


def _invalidation_of(e):
    """decision3 (H1) gives `invalidation` = the price and `invalidation_rule` = its text (separate keys); a dict {price, rule} is read
    the same way. ⇒ {"price": float | None, "rule": str | None} (card: information only — the trade's SL / target are the dashboard's)."""
    inv = e.get("invalidation")
    if isinstance(inv, dict):
        px, rule = inv.get("price"), inv.get("rule")
    else:
        px, rule = inv, None
    rule = e.get("invalidation_rule") if rule is None else rule
    try:
        px = None if px is None else float(px)
    except (TypeError, ValueError):
        px = None
    return {"price": px if px == px else None, "rule": None if rule is None else str(rule)}


def _cluster_of(c):
    """decision3 `entry_cluster_rule = cluster`: the overlapping cluster an entry stands for ⇒ {id, anchor, visit_id, n, members
    [{area_id, tf, lo, hi, state}]} (ids as text). Abhi 21 Oct (Z-1u): the cluster only COUNTS one signal per model per place — it has
    no band of its own (the entry's zone = its own visited area, `area`). Not a dict ⇒ None."""
    if not isinstance(c, dict):
        return None
    txt = lambda v: None if v is None else (v if isinstance(v, (str, int, float)) and not isinstance(v, bool) else str(v))  # noqa: E731
    num = lambda v: None if v is None else float(v)  # noqa: E731
    try:
        return {"id": txt(c.get("id")), "anchor": txt(c.get("anchor")),
                "visit_id": None if c.get("visit_id") is None else str(c["visit_id"]), "n": int(c.get("n") or 0),
                "members": [{"area_id": txt(m.get("area_id")), "tf": m.get("tf"), "lo": num(m.get("lo")), "hi": num(m.get("hi")),
                             "state": m.get("state")} for m in (c.get("members") or []) if isinstance(m, dict)]}
    except (TypeError, ValueError):
        return None


def compact_entries(entries):
    """decision3 `entries` (fired entry models of this bar) ⇒ the contract fields only (model, name, direction, side, object, area {id,
    tf, role, lo, hi, state, object}, visit_id, visit_start, key, trigger_ts, trigger_bar_end, entry_ref, invalidation {price, rule},
    evidence ([name, mark] pairs), evidence_list (the 6a dict), label); timestamps as text. Not a list ⇒ []. A non-dict item is skipped.
    Nothing is re-read or scored."""
    out = []
    for e in entries if isinstance(entries, (list, tuple)) else []:
        if not isinstance(e, dict):
            continue
        x = {k: e.get(k) for k in ENTRY_KEYS}
        x["area"] = _area_of(e.get("area"))
        x["invalidation"] = _invalidation_of(e)
        if e.get("cluster") is not None:                                 # one location = the overlapping cluster (its member areas)
            x["cluster"] = _cluster_of(e.get("cluster"))
        rb = e.get("refined_base")
        if isinstance(rb, dict) and rb.get("lo") is not None:            # RC2: the refined 15M base inside the area (display + card)
            x["refined_base"] = {"lo": float(rb["lo"]), "hi": float(rb["hi"]), "ts": None if rb.get("ts") is None else str(rb["ts"])}
        if e.get("family") == "C":                                       # model C (DECISIONS 32): family, sub-model, story, context
            x.update(model_c_of(e))
        elif isinstance(e.get("model_c_context"), dict):                 # C-f: a label on a Daily-side entry (statistics only)
            x["model_c_context"] = {"sub_model": e["model_c_context"].get("sub_model"), "cycle": e["model_c_context"].get("cycle")}
        for k in ("trigger_ts", "visit_id", "visit_start", "trigger_bar_end", "key"):
            if x.get(k) is not None:
                x[k] = str(x[k])
        if x["area"] is not None and x["area"].get("id") is not None and not isinstance(x["area"]["id"], (str, int, float)):
            x["area"]["id"] = str(x["area"]["id"])                       # numpy ints ⇒ text, never a JSON error
        out.append(x)
    return out


def model_c_of(e):
    """A model C entry's card / audit facts (decision3/model_c.py label) ⇒ {family, sub_model, story, model_c {window, daily, weekly, O,
    choch, HA, B, a_nature, b_nature, end_zone, invalidated_if}} with plain values (prices, words). Display + audit only; never raises."""
    try:
        c = e.get("model_c") if isinstance(e.get("model_c"), dict) else {}
        pt = lambda p: None if not isinstance(p, dict) else {k: p.get(k) for k in ("price", "level", "ts") if k in p}   # noqa: E731
        nat = lambda n: None if not isinstance(n, dict) else {"verdict": n.get("verdict"), "why": str(n.get("why") or "")[:160]}  # noqa: E731
        ez = c.get("end_zone") if isinstance(c.get("end_zone"), dict) else {}
        return {"family": "C", "sub_model": e.get("sub_model"), "story": None if e.get("story") is None else str(e["story"])[:400],
                "model_c": {"window": c.get("window"), "daily": c.get("daily"), "weekly": c.get("weekly"), "O": pt(c.get("O")),
                            "choch": pt(c.get("choch")), "HA": pt(c.get("HA")), "B": pt(c.get("B")),
                            "a_nature": nat(c.get("a_nature")), "b_nature": nat(c.get("b_nature")),
                            "end_zone": {"first_htf_area": ez.get("first_htf_area"), "protected_origin": ez.get("protected_origin"),
                                         "projections": ez.get("projections")},
                            "invalidated_if": c.get("invalidated_if")}}
    except Exception:                                                    # noqa: BLE001 — display only
        return {"family": "C", "sub_model": e.get("sub_model")}


def compact_armed(armed):
    """decision3 `armed` (per armed area: each model's status — fired / fired_earlier / waiting / passed / off / disarmed …) ⇒ compact:
    scalars and lists of scalars kept, a nested area reduced to {id, tf, lo, hi, state}, the per-model status dict `models` kept as
    {model: {status, at, waiting (≤ 160 chars), note}}, anything else dropped. Not a list ⇒ []."""
    def scalar(v):
        return v is None or isinstance(v, (str, int, float, bool))
    out = []
    for a in armed if isinstance(armed, (list, tuple)) else []:
        if not isinstance(a, dict):
            continue
        x = {}
        for k, v in a.items():
            if k == "area":
                x[k] = _area_of(v)
            elif k == "models" and isinstance(v, dict):
                x[k] = {str(m): {kk: (str(st.get(kk))[:160] if kk in ("waiting", "note") and st.get(kk) is not None else st.get(kk))
                                 for kk in ARMED_MODEL_KEYS if kk in st} for m, st in v.items() if isinstance(st, dict)}
            elif scalar(v):
                x[k] = v
            elif isinstance(v, (list, tuple)) and all(scalar(i) for i in v):
                x[k] = list(v)
            elif hasattr(v, "isoformat"):
                x[k] = str(v)
            elif isinstance(v, (np.integer, np.floating)):
                x[k] = v.item()
        out.append(x)
    return out


PAYLOAD_MAX = 20000
_PAYLOAD_DROP = ("legacy_k_gate", "checklist", "zone_read", "watch_list", "flip_context", "trend_notes", "level", "risk")   # bulky first;
_PAYLOAD_KEEP = ("entries", "armed")                                     # never data_problem / entries / armed (decision data)


def fit_payload(payload, limit=PAYLOAD_MAX):
    """Payload JSON ≤ limit chars WITHOUT a blind cut (a cut string is invalid JSON ⇒ the data_problem flag would be lost): drop the
    bulky context keys one by one (noted in "dropped"); still too long ⇒ only the flags (engine, data_problem, volume_measure) + the
    entry models (`entries`, `armed` — decision data, never dropped; the limit is a size target, not a hard cut)."""
    dump = lambda d: json.dumps(d, ensure_ascii=False, default=str)  # noqa: E731
    out = dump(payload)
    if len(out) <= limit:
        return out
    if "reader" in payload:                                              # display-only reader facts (approval card summary): too
        payload = {k: v for k, v in payload.items() if k != "reader"}     # long ⇒ removed SILENTLY, so the rest is exactly today's
        out = dump(payload)                                              # payload (no longer "dropped" list, no extra key pushed out)
        if len(out) <= limit:
            return out
    p, dropped = dict(payload), []
    for k in _PAYLOAD_DROP:
        if k in p:
            p.pop(k)
            dropped.append(k)
            out = dump({**p, "dropped": dropped})
            if len(out) <= limit:
                return out
    keep = {k: payload.get(k) for k in ("engine", "ts", "bar_end", "data_problem")}
    keep["volume_measure"] = str(payload.get("volume_measure") or "")[:500]
    keep.update({k: payload[k] for k in _PAYLOAD_KEEP if k in payload})  # entry models: decision data, never trimmed away
    return dump({**keep, "dropped": "all context (payload too large)"})


def compute(symbol, feed, now, s=None):
    s3 = v22_settings(s)                                                 # dashboard swing scale + layer switches; bad ⇒ raise before any fetch
    m15, daily, ltf, fut, note = build_inputs(feed, symbol, now, s)
    m1, m1_info = load_m1(feed, symbol, m15, pd.Timestamp(now), s)
    r = evaluate(symbol, m15, daily, ltf, fut, s3=s3, m1=m1, m1_info=m1_info)
    r["volume_note"] = note
    r["m1"] = m1_info                                                    # Z-1o: 1m वापरला का / fallback कारण (row payload)
    return r
