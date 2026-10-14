"""decision3/history.py — Q33 (Abhi): Daily structure पूर्ण उपलब्ध history वर (degree तिच्यावर अवलंबून), पण NIFTY साठी holdout
तारखांचा कोणताही report / metric / chart / log ओळ नाही (holdout evaluation साठी sealed; आधीच्या candles म्हणून वापर चालतो).

  • load_daily(paths): एक किंवा अधिक Daily files (csv / csv.gz / parquet) ⇒ एक मालिका; एकाच दिवसाचे दोन ⇒ नंतरच्या file चा.
  • sealed_fn(symbol): NIFTY ⇒ ts ⇒ holdout? (elliott.data_policy); इतर symbols ⇒ None.
  • display_start(ts, upto, sealed, sessions): chart कुठून दाखवायचा — शेवटच्या `sessions` पैकी, पण शेवटच्या sealed तारखेनंतरच.
  • level_history_daily / daily_warmup (Abhi Z-1t): replays / tests साठी Daily warm-up (live `engine3_live` Upstox Daily सारखा) — NIFTY
    holdout Daily bars फक्त Daily levels चा इतिहास (Q40 prior levels) म्हणून, आणि फक्त holdout संपल्यानंतरच्या (≥ 2026-07) 15M window
    साठी; प्रत्येक वापराची नोंद ("holdout daily bars used as level history: n bars"). Holdout दिवसासाठी काहीच मोजलं / दाखवलं जात नाही
    (V22 holdout 15M bar ⇒ HoldoutError — `decision3.engine.guard_sealed_bars`).
"""
import logging
import os

import pandas as pd

log = logging.getLogger(__name__)

NIFTY_NAMES = ("NIFTY", "NIFTY50", "NIFTYINDEX", "NIFTY50INDEX", "NSENIFTY", "NSENIFTY50")


def is_nifty(symbol):
    """NIFTY / NIFTY50 / "NIFTY 50" / NIFTY_INDEX / NSE:NIFTY … (sealed holdout नियम); BANKNIFTY / FINNIFTY नाही."""
    s = "".join(ch for ch in str(symbol).upper() if ch.isalnum())
    return s in NIFTY_NAMES


def sealed_fn(symbol):
    if not is_nifty(symbol):
        return None
    from elliott import data_policy as DP
    return lambda ts: DP.period(ts) == "HOLDOUT"


def _read(path):
    return pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)


def load_daily(paths, prepare=None):
    paths = [paths] if isinstance(paths, str) else list(paths)
    frames = []
    for k, p in enumerate(paths):
        x = _read(p)
        x["timestamp"] = pd.to_datetime(x["timestamp"])
        if getattr(x["timestamp"].dt, "tz", None) is not None:
            x["timestamp"] = x["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        x["timestamp"] = x["timestamp"].dt.normalize()
        x = prepare(x) if prepare else x
        frames.append(x.assign(_src=k))
    d = pd.concat(frames, ignore_index=True)
    d = d.sort_values(["timestamp", "_src"]).drop_duplicates("timestamp", keep="last").drop(columns="_src")
    return d.reset_index(drop=True)


def last_sealed(ts, sealed, upto=None):
    """[0, upto] मधली शेवटची sealed row (नसेल ⇒ -1)."""
    if sealed is None:
        return -1
    ts = list(ts)
    n = len(ts) if upto is None else upto + 1
    for j in range(n - 1, -1, -1):
        if sealed(ts[j]):
            return j
    return -1


def display_start(ts, upto=None, sealed=None, sessions=250):
    """Chart start index: शेवटच्या `sessions` Daily candles (upto पर्यंत), sealed तारखांनंतरच."""
    ts = list(ts)
    n = len(ts) if upto is None else upto + 1
    return max(0, n - int(sessions), last_sealed(ts, sealed, upto) + 1)


# ------------------------------------------------------------------------------------------------ Abhi Z-1t: Daily warm-up for replays / tests
HOLDOUT_LINE = "holdout daily bars used as level history: {n} bars"


def _ohlc_daily(df):
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if getattr(d["timestamp"].dt, "tz", None) is not None:
        d["timestamp"] = d["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["timestamp"] = d["timestamp"].dt.normalize()
    return d[["timestamp", "open", "high", "low", "close"]]


def daily_from_1m(df1m, close_hm="15:29"):
    """1m bars ⇒ Daily candles of complete sessions only (the session's last 1m bar at / after `close_hm`; a cut-off day is dropped,
    never a partial Daily candle)."""
    d = df1m.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    d["_d"] = d["timestamp"].dt.normalize()
    g = d.sort_values("timestamp").groupby("_d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                     close=("close", "last"), last=("timestamp", "max")).reset_index()
    g = g[g["last"].dt.strftime("%H:%M") >= close_hm]
    return g.rename(columns={"_d": "timestamp"})[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)


def level_history_daily(symbol, frames, window_start, log_fn=None):
    """Abhi Z-1t: Daily bars strictly BEFORE the 15M window (`window_start` = its first day) as history for Daily levels (Q40 prior
    levels, Daily trend warm-up) — the same role as live's Upstox Daily (`engine3_live`). frames = DataFrames, older first (a later one
    wins on the same day). NIFTY: holdout-dated rows are allowed ONLY when the whole window is after the holdout end (window_start ≥
    data_policy.CONTAMINATED_START); otherwise HoldoutError. Every use is logged: "holdout daily bars used as level history: n bars".
    Returns (daily DataFrame, n holdout bars used)."""
    from elliott import data_policy as DP
    ws = pd.Timestamp(window_start).normalize()
    fr = [_ohlc_daily(f).assign(_k=k) for k, f in enumerate(frames) if f is not None and len(f)]
    if not fr:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"]), 0
    d = pd.concat(fr, ignore_index=True).sort_values(["timestamp", "_k"]).drop_duplicates("timestamp", keep="last")
    d = d[d["timestamp"] < ws].drop(columns="_k").reset_index(drop=True)
    n = 0
    if is_nifty(symbol):
        hold = d["timestamp"].map(lambda x: DP.period(x) == "HOLDOUT").to_numpy(bool)
        n = int(hold.sum())
        if n and ws < DP.CONTAMINATED_START:
            raise DP.HoldoutError(f"{symbol}: holdout Daily bars as level history only for a 15M window after the holdout end "
                                  f"(window starts {ws.date()}) — refused")
        if n:
            msg = HOLDOUT_LINE.format(n=n)
            (log_fn or log.warning)(msg)
    return d, n


def read_level_history(path, symbol, window_start):
    """Abhi Z-1t: read ONE Daily file as level history — the `level_history_daily` guard (rows before the window; holdout rows only for
    a window after the holdout end). The sealed holdout file (data_policy.HOLDOUT_FILES) is readable here and only here. Not logged
    here: pass the frame on to `level_history_daily`, which logs the holdout use once for the combined history. Returns the frame."""
    from elliott import data_policy as DP
    if os.path.basename(str(path)) in DP.HOLDOUT_FILES and (not is_nifty(symbol) or
                                                             pd.Timestamp(window_start).normalize() < DP.CONTAMINATED_START):
        raise DP.HoldoutError(f"{os.path.basename(str(path))}: holdout file — only as NIFTY level history for a window after the holdout end")
    return level_history_daily(symbol, [_read(path)], window_start, log_fn=lambda _m: None)[0]


def daily_warmup(symbol, m15, history, log_fn=None):
    """Abhi Z-1t: the Daily frame V22 gets in a replay / test (as live): `history` (level_history_daily output, days before the 15M
    window) + the 15M window's own complete days (pivots.charts.daily_from_15m — V22's default). bar_end = 15:30 (decision3.daily_swings
    .prepare). History empty ⇒ only the window's days (V22 default) — and Levels logs "Q40 prior levels skipped"."""
    from decision3 import daily_swings as DS
    from pivots import charts as PC
    m = m15 if "bar_end" in m15.columns else m15.assign(bar_end=pd.to_datetime(m15["timestamp"]) + pd.Timedelta(minutes=15))
    own = PC.daily_from_15m(m, pd.to_datetime(m["bar_end"]).max())[["timestamp", "open", "high", "low", "close"]]
    ws = pd.to_datetime(m["timestamp"]).min().normalize()
    h = history[history["timestamp"] < ws] if history is not None and len(history) else None
    return DS.prepare(pd.concat([x for x in (h, own) if x is not None], ignore_index=True))


def repo_level_history(symbol, window_start, root=None, trade_data=None, log_fn=None):
    """Abhi Z-1t: the default Daily warm-up for a replay / test of `symbol` whose 15M window starts at `window_start` — the files this
    repo / trade-data hold, older first: NIFTY = IS / VAL 1m (`data/nifty50_1min.parquet` ⇒ complete Daily sessions, data_policy
    research rows) + the sealed holdout Daily file (`data/nifty50_daily_extension.parquet`, level history only, window after the
    holdout end — else HoldoutError); BANKNIFTY = <trade-data>/banknifty/BANKNIFTY_daily_*.csv. Missing files are skipped (Levels then
    logs "Q40 prior levels skipped"). Returns (history before the window, n holdout bars used) — logged by `level_history_daily`."""
    from elliott import data_policy as DP
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fr = []
    if is_nifty(symbol):
        p1 = os.path.join(root, "data", "nifty50_1min.parquet")
        if os.path.exists(p1):
            fr.append(daily_from_1m(DP.filter_allowed(pd.read_parquet(p1), "research")))
        pe = os.path.join(root, "data", "nifty50_daily_extension.parquet")
        if os.path.exists(pe):
            fr.append(read_level_history(pe, symbol, window_start))
    elif str(symbol).upper() == "BANKNIFTY" and trade_data:
        import glob
        for p in sorted(glob.glob(os.path.join(trade_data, "banknifty", "BANKNIFTY_daily_*.csv"))):
            fr.append(_read(p))
    return level_history_daily(symbol, fr, window_start, log_fn)
