"""engine3_live.py — decision3 (थर v2.2, method engine: trend → area → pullback → commitment → R:R) चा **live** feed (Abhi: one bot, Tuesday PAPER).

प्रत्येक बंद 15M candle नंतर (cron, `scripts/engine_signal_run.py --engine decision3`) एका symbol साठी:
  • 15M spot (Upstox, `engine3_m15_days` दिवस) — फक्त बंद candles; NIFTY ⇒ `data_policy.filter_allowed(..., "annotation")` (holdout row नाही).
  • Daily (Upstox 'day', ~10 वर्षं, आजचा अपूर्ण Daily bar नाही) — Q33: Daily holdout candles फक्त warm-up input (level_reaction.daily_trend
    प्रमाणेच); output मध्ये sealed तारीख नाही (`history.sealed_fn`). Weekly = Daily वरून (V22 स्वतः).
  • 5M spot (LTF: c1 5M CHoCH) ⇒ V22 `ltf=`; नसेल ⇒ fail-closed. Front-month FUT 5M volume (c0 dominant candle + volume) ⇒ V22
    `futures=` (expiry सह; जुना V22 ⇒ m15 joined `volume`); FUT नसेल ⇒ volume NA (grade कमाल B), fail-closed नाही.
  • V22(m15, daily_df=…).decide(शेवटचा बंद bar) ⇒ engine_signal store row (decision2 च्याच columns) ⇒ bots चा adapter (`pending_entry`).
Fail-closed: data नाही / अपूर्ण / exception ⇒ EngineDataError (caller "error" row + दिवसातून एकदा Telegram ओळ). Order / broker call नाही.
Daily fold (सर्वात महाग भाग, ~50 s) दिवसाला एकदा: input hash वर disk cache (`data/engine3_cache/`) — शुद्ध function, निकाल तोच.
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
DEFAULTS = {"engine3_m15_days": 90, "engine3_daily_days": 3650, "engine3_ltf_days": 10}
SESSION_OPEN, SESSION_CLOSE = (9, 15), (15, 30)
FUT_EXCHANGE = {"SENSEX": "BSE"}                                          # बाकी NSE (NIFTY / BANKNIFTY)


class EngineDataError(RuntimeError):
    """Live data नाही / अपूर्ण ⇒ entry नाही (fail-closed)."""


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
    CHUNK = {"5minute": 28, "15minute": 28, "day": 3700}

    def __init__(self, token, today=None):
        if not token:
            raise EngineDataError("Upstox token नाही")
        self.token = token
        self.today = today or dt.date.today()

    def _series(self, key, interval, days, contract=None):
        import verify_opportunity_data_availability as V
        from opportunity_engine.volume import candles_to_df
        unit, val = V._V3_UNITS[interval]
        enc = urllib.parse.quote(key, safe="")
        out, to = [], self.today
        start = self.today - dt.timedelta(days=int(days))
        while to > start:
            frm = max(start, to - dt.timedelta(days=self.CHUNK[interval]))
            r = V.fetch_candles_window(self.token, key, interval, frm, to)
            if r["status"] != 200:
                raise EngineDataError(f"{key} {interval} history HTTP {r['status']} ({str(r['error'])[:80]})")
            out.extend(r["candles"])
            to = frm - dt.timedelta(days=1)
        if interval != "day":
            st, body, err = V._get(f"{V.BASE_V3}/intraday/{enc}/{unit}/{val}", self.token)
            if st != 200:
                raise EngineDataError(f"{key} {interval} intraday HTTP {st} ({str(err)[:80]})")
            out.extend(((body or {}).get("data") or {}).get("candles") or [])
        return candles_to_df(out, contract=contract)

    def index(self, symbol, interval, days):
        return self._series(index_key(symbol), interval, days)

    def futures(self, symbol, interval, days):
        info = resolve_future(self.token, symbol, self.today)
        f = self._series(info["instrument_key"], interval, days, contract=info["trading_symbol"])
        return f.assign(expiry=pd.Timestamp(info["expiry"])) if len(f) else f     # legs2.volume.near_month साठी


# ------------------------------------------------------------------------------------------------ frames
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
    try:                                                                 # c0 volume: FUT नाही ⇒ volume NA (grade कमाल B) — fail-closed नाही
        fut = closed_session_bars(feed.futures(symbol, "5minute", s["engine3_ltf_days"]), 5, now)
        today_fut = fut[fut["timestamp"].dt.normalize() == m15["timestamp"].iloc[-1].normalize()] if len(fut) else fut
        if not len(today_fut) or float(today_fut["volume"].sum()) <= 0:
            fut, note = None, f"{symbol}: FUT 5M volume (आज) नाही ⇒ volume NA (grade कमाल B)"
    except Exception as exc:                                             # noqa: BLE001
        fut, note = None, f"{symbol}: FUT volume नाही ({type(exc).__name__}: {str(exc)[:80]}) ⇒ volume NA (grade कमाल B)"
    return m15, daily, ltf, fut, note


def evaluate(symbol, m15, daily, ltf=None, fut=None, s3=None):
    """V22 ⇒ शेवटच्या बंद 15M bar चा निर्णय (dict, decide() चा)."""
    import instruments as INS
    prev = INS._current["name"]
    INS.set_current(symbol)                                              # PE.guard चा holdout नियम त्याच instrument चा (NIFTY फक्त)
    try:
        return _evaluate(symbol, m15, daily, ltf, fut, s3)
    finally:
        INS._current["name"] = prev                                      # process-wide instrument पुढच्या caller ला गळू नये


def _evaluate(symbol, m15, daily, ltf, fut, s3):
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
        V = E3.V22(m15, None, daily, **kw)
    return V.decide(len(V.m15) - 1)


def _first_fail(chk):
    for k, v in (chk or {}).items():
        if v and v[0] is False:
            return k, str(v[1])
    return None, None


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
                                                            "mark", "conviction", "commitment_form", "missing", "checklist", "volume_note")},
               "level": {k: lv.get(k) for k in ("id", "role", "lo", "hi", "births", "sweeps", "dist")} if lv else None,
               "risk": rk or None}
    return {"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(r["bar_end"])), "computed_at": str(now_fn()),
            "decision": r.get("decision"), "gate": gate, "direction": d, "level_lo": lv.get("lo"), "level_hi": lv.get("hi"),
            "entry": rk.get("entry"), "invalidation": rk.get("sl"), "target": rk.get("target"), "grade": r.get("conviction"),
            "reason": str(reason)[:300], "payload": json.dumps(payload, ensure_ascii=False, default=str)[:20000]}


def compute(symbol, feed, now, s=None):
    m15, daily, ltf, fut, note = build_inputs(feed, symbol, now, s)
    r = evaluate(symbol, m15, daily, ltf, fut)
    r["volume_note"] = note
    return r
