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

import numpy as np
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


DATA_PROBLEMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "data_problems.json")


def data_problems(symbol=None, path=DATA_PROBLEMS):
    """DECISIONS 74: the marked data problems (decision3/data/data_problems.json), each with its evidence; `symbol` filters."""
    import json
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["problems"]
    return [r for r in rows if symbol is None or r["symbol"] in (symbol, "ALL")]


CLOSE_PRINT = "DP-2"                     # data_problems.json: the flat session tail + one last print (DECISIONS 84, rule-detected)
_TF_MIN = {"1m": 1, "1M": 1, "5m": 5, "5M": 5, "15m": 15, "15M": 15, "1H": 60, "60m": 60}


def _naive_ts(x):
    ts = pd.to_datetime(pd.Series(x).reset_index(drop=True))
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return ts


def close_print_runs(df, min_run=None):
    """DECISIONS 84 detector (comparison, no clock): per session, the session-ending run of FLAT bars (open = high = low = close, every
    one the same price) followed by ONE last print — the bar that opens at that flat price and prints elsewhere, or a lone flat bar at another price — and then, if the print
    came before the last bar, flat bars at the printed price up to the session end; or a flat run that reaches the session end itself
    (a frozen tail, no print). A run shorter than `min_run` (settings `dp_flat_run_min_bars`, a data-quality setting) is ordinary data.
    One row per affected session: the flat bars, the flat price, the close before the run, the print and its jump; `bars` = the row
    positions (in `df`) of every affected bar (the run, the print, the flat bars after it)."""
    from . import settings as S3
    k = int(S3.DEFAULTS["dp_flat_run_min_bars"] if min_run is None else min_run)
    cols = ["session", "flat_from", "flat_to", "n_flat", "flat_price", "close_before", "print_ts", "print_high", "print_low",
            "print_close", "jump", "n_after", "bars"]
    if df is None or not len(df):
        return pd.DataFrame(columns=cols)
    ts = _naive_ts(df["timestamp"])
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    flat = (o == h) & (h == l) & (l == c)
    day = ts.dt.normalize().to_numpy()

    def run_back(end, a):                                                 # identical flat bars ending at `end` ⇒ first index
        j = end
        if end < a or not flat[end]:
            return end + 1
        while j - 1 >= a and flat[j - 1] and c[j - 1] == c[end]:
            j -= 1
        return j

    rows = []
    starts = np.r_[0, np.flatnonzero(day[1:] != day[:-1]) + 1]
    for a, e in zip(starts, np.r_[starts[1:], len(df)]):
        last = e - 1
        p0 = run_back(last, a)                                            # trailing flat bars (after a print, or the frozen run)
        hit = None
        for ip in ((p0 - 1, p0) if p0 <= last else (last,)):              # the print: the bar before them, or the first of them
            if ip < a + 1 or ip > last:
                continue
            j = run_back(ip - 1, a)
            if ip - j >= k and (c[ip - 1] == o[ip] or flat[ip]) and (not flat[ip] or c[ip] != c[ip - 1]):
                hit = (j, ip - 1, ip)
                break
        if hit is None and last - p0 + 1 >= k:
            hit = (p0, last, None)                                        # frozen to the session end, no print
        if hit is None:
            continue
        j, t, ip = hit
        bars = list(range(j, last + 1))
        rows.append({"session": pd.Timestamp(day[a]), "flat_from": ts.iloc[j], "flat_to": ts.iloc[t], "n_flat": int(t - j + 1),
                     "flat_price": float(c[t]), "close_before": float(c[j - 1]) if j > a else None,
                     "print_ts": ts.iloc[ip] if ip is not None else None, "print_high": float(h[ip]) if ip is not None else None,
                     "print_low": float(l[ip]) if ip is not None else None, "print_close": float(c[ip]) if ip is not None else None,
                     "jump": float(c[ip] - c[t]) if ip is not None else 0.0, "n_after": int(last - ip) if ip is not None else 0,
                     "bars": bars})
    return pd.DataFrame(rows, columns=cols)


def close_print_mask(df, tf=None, finer=None, min_run=None):
    """bool array over `df`: the bars a close-print run (close_print_runs) touches — detected on `df` itself, and, when `finer` (a finer
    TF of the same instrument, e.g. 1m / 5M under a 15M frame) is given, every `df` bar whose span holds a flagged finer bar (the 15M
    bar that contains the flat run + the print). `tf` (15M / 5M / 1H …) gives the span; without it the bar_end column, else none."""
    n = 0 if df is None else len(df)
    m = np.zeros(n, dtype=bool)
    if not n:
        return m
    for bars in close_print_runs(df, min_run)["bars"]:
        m[bars] = True
    if finer is not None and len(finer):
        fr = close_print_runs(finer, min_run)
        if len(fr):
            fts = _naive_ts(finer["timestamp"]).to_numpy()
            hit = np.sort(fts[np.concatenate([np.asarray(b, int) for b in fr["bars"]])])
            ts = _naive_ts(df["timestamp"])
            if tf in _TF_MIN:
                end = ts + pd.Timedelta(minutes=_TF_MIN[tf])
            elif "bar_end" in df.columns:
                end = _naive_ts(df["bar_end"])
            else:
                end = ts
            lo = np.searchsorted(hit, ts.to_numpy(), side="left")
            hi = np.searchsorted(hit, end.to_numpy(), side="left")
            m |= hi > lo
    return m


def dp_mask(df):
    """bool array: the bars marked as a data problem (`data_problem` column non-empty); no column ⇒ none (DECISIONS 84 guard input)."""
    if df is None or "data_problem" not in getattr(df, "columns", ()):
        return np.zeros(0 if df is None else len(df), dtype=bool)
    return df["data_problem"].fillna("").astype(str).ne("").to_numpy()


def mark_data_problems(df, symbol, tf, path=DATA_PROBLEMS, finer=None, detect=True):
    """DECISIONS 74 / 84: a copy of `df` with a `data_problem` column (the problem id, "" elsewhere): the listed `tf` bars of `symbol`
    (data_problems.json) and — `detect` — every close-print bar the rule detector finds (CLOSE_PRINT; `finer` = a finer TF of the same
    instrument so a coarse bar that holds the run is marked too). A listed id wins over the detector's on the same bar.
    Never changes a price and never drops a bar (bad data is marked, not patched or hidden)."""
    out = df.copy()
    ts = _naive_ts(out["timestamp"]).to_numpy()
    out["data_problem"] = ""
    if detect and len(out):
        out.loc[close_print_mask(out, tf, finer), "data_problem"] = CLOSE_PRINT
    rows = data_problems(symbol, path) if symbol else [r for r in data_problems(None, path) if r["symbol"] == "ALL"]
    for r in rows:                                                        # no symbol ⇒ only the rule-detected (ALL) problems
        b = (r.get("bars") or {}).get(tf)
        if b is not None:
            out.loc[ts == np.datetime64(pd.Timestamp(b)), "data_problem"] = r["id"]
    return out


def ensure_marked(m15, finer=(), symbol=None):
    """DECISIONS 84 / 87 (DP-2: the flags apply in replays as in live — the same V22 path for both): `m15` with the `data_problem`
    column — the marks it already carries (live marks the 15M from the 5M at the source, engine3_live.mark_close_prints) kept, plus
    every 15M bar the rule detector finds from each `finer` frame of the same instrument (the 5M LTF, the 1m spot: the 15M bar that
    holds the flat run + the print). Never changes a price, never drops a bar; unflagged data reads identical."""
    if m15 is None or not len(m15):
        return m15
    fr = [f for f in (finer if isinstance(finer, (list, tuple)) else [finer]) if f is not None and len(f)]
    had = "data_problem" in m15.columns
    out = m15 if had else mark_data_problems(m15, symbol, "15M", finer=fr[0] if fr else None)
    rest = fr if had else fr[1:]
    if rest:
        out = out.copy()
        free = out["data_problem"].fillna("").astype(str).eq("").to_numpy()
        for f in rest:
            hit = close_print_mask(out, "15M", f) & free
            out.loc[hit, "data_problem"] = CLOSE_PRINT
            free = free & ~hit
    return out


AUCTION_EXTENDED = "DP-3"                # data_problems.json: a Daily bar whose closing-auction print lies beyond the traded range


def auction_extended_bars(intraday):
    """DECISIONS 87: bool array over `intraday` (marked: `data_problem`) — the data-problem bars whose close (the closing-auction print)
    lies beyond the session's TRADED range (its unmarked bars + the flat value before the print). Such a close is not traded price
    action: it never counts as a close beyond / back inside an object (a print inside the traded range is the session's real close and
    counts). Comparison only."""
    n = 0 if intraday is None else len(intraday)
    m = np.zeros(n, dtype=bool)
    dp = dp_mask(intraday)
    if not n or len(dp) != n or not dp.any():
        return m
    day = _naive_ts(intraday["timestamp"]).dt.normalize().to_numpy()
    o, h, l, c = (intraday[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    th, tl = np.where(dp, o, h), np.where(dp, o, l)
    for i in np.flatnonzero(dp):
        same = day == day[i]
        m[i] = c[i] > th[same].max() or c[i] < tl[same].min()
    return m


def mark_auction_extended(daily, intraday):
    """DECISIONS 87 (owner rule, DP-1 of 24 Oct): a Daily bar whose official close (the closing-auction print) lies beyond the session's
    TRADED high / low keeps that close as its Daily close and is flagged "auction-extended" (`auction_extended` True, `data_problem`
    AUCTION_EXTENDED); its high (print above) / low (print below) becomes the traded extreme, so the auction-only extension never
    defines a Daily swing extreme or a zone edge (wick to body clamps to the swing price). The official values stay in `print_high` /
    `print_low`. Traded range = the session's intraday bars (`intraday`, marked: `data_problem`) that are not data-problem bars, plus
    the open of a marked bar (the flat value before the print). A session without intraday bars is read as given (no evidence ⇒ no
    flag). Comparison only; nothing else changes."""
    out = daily.copy().reset_index(drop=True)
    out["print_high"], out["print_low"] = out["high"].astype(float), out["low"].astype(float)
    out["auction_extended"] = False
    if "data_problem" not in out.columns:
        out["data_problem"] = ""
    if intraday is None or not len(intraday) or not len(out):
        return out
    x = pd.DataFrame({"day": _naive_ts(intraday["timestamp"]).dt.normalize().to_numpy(),
                      "high": intraday["high"].to_numpy(float), "low": intraday["low"].to_numpy(float),
                      "open": intraday["open"].to_numpy(float)})
    dp = dp_mask(intraday)
    dp = dp if len(dp) == len(x) else np.zeros(len(x), dtype=bool)
    x["th"] = np.where(dp, x["open"], x["high"])
    x["tl"] = np.where(dp, x["open"], x["low"])
    g = x.groupby("day").agg(th=("th", "max"), tl=("tl", "min"), n_dp=("th", lambda s: int(dp[s.index].sum())))
    days = _naive_ts(out["timestamp"]).dt.normalize()
    th = days.map(g["th"]).to_numpy(float)
    tl = days.map(g["tl"]).to_numpy(float)
    nd = days.map(g["n_dp"]).fillna(0).to_numpy(float)
    c = out["close"].to_numpy(float)
    up = np.isfinite(th) & (nd > 0) & (c > th)
    dn = np.isfinite(tl) & (nd > 0) & (c < tl)
    out.loc[up, "high"] = th[up]
    out.loc[dn, "low"] = tl[dn]
    ext = up | dn
    out.loc[ext, "auction_extended"] = True
    out.loc[ext & out["data_problem"].fillna("").astype(str).eq(""), "data_problem"] = AUCTION_EXTENDED
    return out


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
    if "timestamp" not in d.columns and "date" in d.columns:               # research Daily files (date, open, high, low, close)
        d = d.rename(columns={"date": "timestamp"})
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if getattr(d["timestamp"].dt, "tz", None) is not None:
        d["timestamp"] = d["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    d["timestamp"] = d["timestamp"].dt.normalize()
    return d[["timestamp", "open", "high", "low", "close"]]


def daily_from_1m(df1m, bar_minutes=1):
    """1m bars ⇒ Daily candles of complete sessions only — the shared session definition `pivots.engine.session_complete` (the session's
    last bar closes at the session end; CAS days included); a cut-off day is dropped, never a partial Daily candle."""
    from pivots import engine as PE
    d = df1m.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    d["_d"] = d["timestamp"].dt.normalize()
    g = d.sort_values("timestamp").groupby("_d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                     close=("close", "last"), last=("timestamp", "max")).reset_index()
    ok = [PE.session_complete(x, e + pd.Timedelta(minutes=int(bar_minutes))) for x, e in zip(g["_d"], g["last"])]
    return g[ok].rename(columns={"_d": "timestamp"})[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)


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
    holdout end — else HoldoutError); BANKNIFTY = <trade-data>/banknifty/BANKNIFTY_daily_*.csv + BANKNIFTY_D.csv.gz.
    Missing files are skipped (Levels then
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
        for p in sorted(glob.glob(os.path.join(trade_data, "banknifty", "BANKNIFTY_daily_*.csv"))) + \
                sorted(glob.glob(os.path.join(trade_data, "banknifty", "BANKNIFTY_D.csv*"))):       # older first; Upstox Daily wins
            fr.append(_read(p))
    return level_history_daily(symbol, fr, window_start, log_fn)
