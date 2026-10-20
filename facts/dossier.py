"""facts/dossier.py — the ONE dossier function of the facts layer (design docs/design/CHART_READER_AGENT.md §3, §13 R1b).

`build_dossier(symbol, bars_by_tf, fut_bars_by_tf=None, as_of=None, cfg=None)` calls exactly one owner module per concept (§3 table;
`facts/README.md` lists the function called and the output keys) and returns a JSON-safe dict of facts with evidence (prices, bar times,
counts). Nothing here is a vote, score, grade or trade decision, and nothing here calls an AI, a broker or the network.

Rules:
  • No look-ahead: every frame is cut to the bars whose CLOSE time is ≤ `as_of` before any owner sees it (15M / 5M / 1m / FUT 5M by
    bar_end or start + bar length; Daily by its 15:30 close; 1H = 09:15-anchored hours from the 15M bars, complete hours only).
  • A section whose owner fails, or whose input is missing, is {"status": "NA", "reason": ...} — never a silent pass. FUT volume
    missing ⇒ the volume section is NA (and the volume-based facts inside the candle study say volume NA).
  • Owners are called as they are (thin adapters only): no owner code is moved or changed here. Known disagreements between owners are
    open questions (README), not decided here.
  • Owner outputs that carry a grade / score / vote (decision3 commitment grade, rsi2 divergence grade, patterns2 hypothesis score,
    reader2 confidence / anatomy score) are dropped; the facts they were computed from are kept.
"""
import math
import re
from dataclasses import asdict, is_dataclass
from types import SimpleNamespace

import numpy as np
import pandas as pd

from decision3 import method as M3
from elliott import data_policy as DP
from facts import validity as FV
from vision import context as VC

SCHEMA = "facts.dossier/1"
OK, NA = "OK", "NA"

DEFAULTS = {
    "pivots_per_degree": 8,          # display cap only (same as vision.context.SWINGS_MAX): last N confirmed pivots per degree
    "area_tfs": ("15M", "1H"),       # design §5: 1H buyer / seller areas, 15M setup
    "divergences_max": 4,            # display cap only: the last N divergences known at as_of
    "validity": None,                # overrides for facts.validity (owners' shared K4 / K6 checks)
    "swings2": None,                 # overrides for swings2 settings
    "decision3": None,               # overrides for decision3 settings (method / liquidity)
    "reader2": None,                 # overrides for reader2 settings
    "legs_reader": None,             # reader2.reader.read, injected by a research / test caller (reader2 is research-only) — None ⇒ legs NA
}
# keys an owner may return that are a grade / score / vote, never a fact (design §3) — dropped everywhere in the dossier
NOT_FACTS = frozenset({"grade", "score", "scores", "vote", "votes", "conviction", "decision", "confidence", "verdict", "ratio",
                       "strength", "completion", "momentum"})
GRADE_TXT = re.compile(r"\s*·\s*grade\s+\S+")                          # decision3 commitment text carries its grade ⇒ removed
SECTIONS = ("structure", "legs", "areas", "lines", "confluence", "patterns", "candles", "volume", "ltf_choch", "liquidity", "gaps",
            "context", "divergence")


# ------------------------------------------------------------------------------------------------ JSON-safe facts
def _j(x):
    """Owner output ⇒ JSON-safe facts (numpy / pandas / dataclass ⇒ plain; NaN / NaT / NA ⇒ None; grade / score / vote keys dropped)."""
    if x is pd.NaT or x is pd.NA:
        return None
    if is_dataclass(x) and not isinstance(x, type):
        x = asdict(x)
    if isinstance(x, dict):
        return {str(k): _j(v) for k, v in x.items() if str(k) not in NOT_FACTS}
    if isinstance(x, (list, tuple, set)):
        return [_j(v) for v in x]
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return None if pd.isna(x) else str(pd.Timestamp(x))
    if isinstance(x, pd.Timedelta):
        return str(x)
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else round(float(x), 4)
    if isinstance(x, np.ndarray):
        return [_j(v) for v in x.tolist()]
    if x is None or isinstance(x, (str, int)):
        return x
    return str(x)


def _na(owner, reason):
    return {"status": NA, "owner": owner, "reason": reason}


def _ok(owner, **facts):
    return {"status": OK, "owner": owner, **_j(facts)}


# ------------------------------------------------------------------------------------------------ inputs (closed bars ≤ as_of only)
def _naive(x):
    """tz-aware ⇒ naive IST through the owner's helper (decision3.method._naive); naive stays as is."""
    return M3._naive(pd.Series(pd.to_datetime(x))).reset_index(drop=True)


def _instrument(symbol):
    """The instrument whose holdout rule applies: the dossier's own symbol (never the process-global current instrument). An unknown /
    anonymised symbol gets the default (NIFTY) rule — the strict one."""
    import instruments as INS
    n = str(symbol or "").upper()
    return n if n in INS.REGISTRY else INS.DEFAULT


def guard_inputs(symbol, bars_by_tf, fut_bars_by_tf):
    """Sealed-holdout guard on EVERY input frame (spot all TFs + FUT), before any owner runs, with instrument = the dossier's symbol
    (pivots.engine.guard: holdout rows or display_only rows ⇒ HoldoutError). Whole frames are checked, not only the bars ≤ as_of."""
    from pivots import engine as PE
    inst = _instrument(symbol)
    for kind, frames in (("spot", bars_by_tf), ("FUT", fut_bars_by_tf)):
        for tf, df in (frames or {}).items():
            if df is None or not len(df):
                continue
            g = pd.DataFrame({"timestamp": _naive(df["timestamp"])})
            if "display_only" in df.columns:
                g["display_only"] = df["display_only"].to_numpy()
            try:
                PE.guard(g, instrument=inst)
            except DP.HoldoutError as exc:
                raise DP.HoldoutError(f"build_dossier({symbol}): {kind} {tf} — {exc}") from exc


def _bar_end(df, minutes):
    if "bar_end" in df.columns:
        return _naive(df["bar_end"])
    return _naive(df["timestamp"]) + pd.Timedelta(minutes=minutes)


def _closed(df, minutes, as_of, keys=("timestamp",)):
    """Rows whose close time ≤ as_of, stable-sorted, timestamp tz-naive IST, bar_end added (None / empty ⇒ None). Duplicates are dropped
    on `keys` only (FUT: timestamp + contract / expiry; no contract column ⇒ no dedupe — rows of two contracts are never collapsed)."""
    if df is None or not len(df):
        return None
    d = df.copy().reset_index(drop=True)
    d["timestamp"] = _naive(d["timestamp"])
    d["bar_end"] = _bar_end(d, minutes)
    d = d.sort_values("timestamp", kind="stable")
    if keys:
        d = d.drop_duplicates(list(keys), keep="last")
    if as_of is not None:
        d = d[d["bar_end"] <= as_of]
    d = d.reset_index(drop=True)
    return d if len(d) else None


def _fut_keys(df):
    if df is None:
        return ()
    extra = [c for c in ("contract", "expiry") if c in df.columns]
    return ("timestamp", *extra) if extra else ()


def _closed_daily(df, as_of):
    """Daily bars closed by as_of (the session close, vision.context.SESSION_CLOSE, of their day)."""
    if df is None or not len(df):
        return None
    d = df.copy().reset_index(drop=True)
    d["timestamp"] = _naive(d["timestamp"]).dt.normalize()
    d["bar_end"] = d["timestamp"] + VC.SESSION_CLOSE
    d = d.sort_values("timestamp", kind="stable").drop_duplicates("timestamp", keep="last")
    if as_of is not None:
        d = d[d["bar_end"] <= as_of]
    d = d.reset_index(drop=True)
    return d if len(d) else None


def _hours_from_15m(m15):
    """Complete NSE hours (09:15-anchored, the 15:15–15:30 hour included) from closed 15M bars via the session owner
    opportunity_engine.sessions.resample_nse (data path, no chart module; CAS off ⇒ the same OHLC as the 15M input); only bars whose
    source covers the whole hour (`bar_closed`) — a running hour is never a bar."""
    from opportunity_engine import sessions as OS
    h1 = OS.resample_nse(m15[["timestamp", "open", "high", "low", "close"]], 60, cas=False)
    h1 = h1[h1["bar_closed"].astype(bool)]
    return h1[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def _frame_info(df):
    if df is None:
        return "missing"
    return {"bars": int(len(df)), "from": str(df["timestamp"].iloc[0]), "to": str(df["timestamp"].iloc[-1]),
            "last_close_at": str(df["bar_end"].iloc[-1])}


# ------------------------------------------------------------------------------------------------ shared owner state (built once)
class _Ctx:
    """Lazy, shared owner state for one dossier: the swings2 engine result is the input of structure, liquidity, patterns2 and rsi2 —
    built once from the cut 15M bars. A failure is remembered and turned into NA by every section that needs it."""

    def __init__(self, symbol, frames, fut5, as_of, cfg):
        self.symbol, self.f, self.fut5, self.as_of, self.cfg = symbol, frames, fut5, as_of, cfg
        self.m15 = frames["15M"]
        self.t = len(self.m15) - 1
        self._memo = {}
        gap = (as_of - pd.Timestamp(self.m15["bar_end"].iloc[-1])) / pd.Timedelta(minutes=1)
        bar = (pd.Timestamp(self.m15["bar_end"].iloc[-1]) - pd.Timestamp(self.m15["timestamp"].iloc[-1])) / pd.Timedelta(minutes=1)
        self.stale = None if gap <= bar else {
            "stale_by_minutes": int(gap),
            "stale_reason": f"the last closed 15M bar closed {int(gap)} min before as_of (> one bar): these facts describe that bar, "
                            f"not as_of (feed stale, market closed or pre-open)"}

    def stale_facts(self):
        return dict(self.stale or {})

    def memo(self, key, fn):
        if key not in self._memo:
            try:
                self._memo[key] = (True, fn())
            except Exception as exc:                                       # noqa: BLE001 — becomes NA with the reason
                _reraise_policy(exc)
                self._memo[key] = (False, f"{type(exc).__name__}: {str(exc)[:160]}")
        ok, val = self._memo[key]
        if not ok:
            raise _Upstream(f"{key} failed — {val}")
        return val

    # swings2 engine + structure (D1, D2)
    def swings(self):
        def build():
            from swings2 import engine as SE
            from swings2 import structure as ST
            res = SE.build(self.m15[["timestamp", "bar_end", "open", "high", "low", "close"]], self.f.get("1m"),
                           s=self.cfg["swings2"])
            struct, rr = ST.all_structure(res)
            return res, struct, rr
        return self.memo("swings2.engine.build", build)

    def legs2(self):
        def build():
            from legs2 import ik2 as LI
            from legs2 import measure2 as M2
            res, struct, rr = self.swings()
            lg = M2.build(res, self.fut5, rr=rr)
            trk = {d: LI.Tracker(lg, struct, d) for d in lg["settings"]["ik_degrees"]}
            return lg, trk
        return self.memo("legs2.measure2.build", build)

    def s3(self):
        from decision3 import settings as S3
        return S3.load(self.cfg["decision3"])

    def fut15(self):
        """FUT volume on the 15M spot bars through the volume owner (opportunity_engine.volume.attach_futures_volume); None if missing."""
        return self.memo("opportunity_engine.volume.attach_futures_volume", lambda: _attach_volume(self))

    def bands_and_lines(self):
        return self.memo("areas+lines", lambda: _areas_lines(self))


class _Upstream(Exception):
    pass


def _reraise_policy(exc):
    """The sealed holdout guard is never turned into NA: a dossier over holdout rows must fail loudly."""
    if isinstance(exc, DP.HoldoutError):
        raise exc


def _run(owner, fn):
    try:
        return fn()
    except _Upstream as exc:
        return _na(owner, str(exc))
    except Exception as exc:                                               # noqa: BLE001 — owner failure ⇒ NA, never a silent pass
        _reraise_policy(exc)
        return _na(owner, f"owner failed: {type(exc).__name__}: {str(exc)[:200]}")


# ------------------------------------------------------------------------------------------------ K1 structure — swings2 (+ pivots)
def structure(c):
    owner = "swings2.engine.build + swings2.structure.all_structure (pivots DC engine)"
    from swings2 import engine as SE
    from swings2 import structure as ST
    res, struct, _ = c.swings()
    n_piv = int(c.cfg["pivots_per_degree"])
    start = FV.session_start(FV.bars_of(c.m15), c.t, FV.lookback("15M")["lookback_sessions"])
    degrees = {}
    for d in SE.DEGREES:
        ps = SE.known(res, d, c.as_of)
        lab = SE.labels(ps)
        live = [p for p in ps if not p.warmup]
        x = {"pivots": [SE.pivot_json(p, lab[id(p)]) for p in ps][-n_piv:], "confirmed_pivots": len(ps),
             "warmup_done": bool(live), "pivot_trend": ST.trend_of(live)}
        if d in struct:
            st = struct[d]["states"][c.t]
            x["state"] = st
            x["events"] = [e for e in struct[d]["events"] if e["bar"] >= start]
        degrees[f"D{d}"] = x
    if not any(x["confirmed_pivots"] for x in degrees.values()):
        sig = res["settings"]["sigma_sessions"]
        return _na(owner, f"no confirmed swings2 pivot at as_of (σ needs {sig} complete sessions; warm-up per degree)")
    return _ok(owner, degrees=degrees, events_from=str(c.m15["timestamp"].iloc[start]), **c.stale_facts(),
               note="state / events per 15M close (swings2 structure degrees D1, D2); pivot_trend = swings2.structure.trend_of "
                    "on confirmed non-warm-up pivots of that degree")


# ------------------------------------------------------------------------------------------------ K2 / K3 legs — reader2
def _legs_of(R, tf):
    out = []
    for lg in R.all_legs() + list(R.current.values()):
        sv = ((lg.reread or {}).get("structure")) or lg.structure or {}        # = reader2.trend.eff_structure (re-read vote, else the first)
        out.append({"tf": tf, "degree": lg.degree, "dir": lg.dir_name, "start": {"bar": lg.i0, "ts": str(R.ch.d["timestamp"].iloc[lg.i0]),
                                                                                  "price": lg.p0},
                    "end": {"bar": lg.i1, "ts": str(R.ch.d["timestamp"].iloc[lg.i1]), "price": lg.p1}, "bars": lg.bars,
                    "label": lg.label, "structure_family": sv.get("family"), "reason": lg.reason, "provisional": lg.provisional,
                    "known_at": str(lg.known_at)})
    return out


LEGS_GATE = ("reader2 is research-only until its gallery gate passes and Abhi approves (docs/READER2_DESIGN.md, "
             "tests/test_reader2_boundary.py) — no production module may import it; pass cfg['legs_reader'] = reader2.reader.read "
             "from a research / test caller")


def legs(c):
    """K2 / K3 legs from the owner reader2 (`reader2.reader.read`). reader2 is research-only (its boundary test forbids any production
    import), so the facts package never imports it: the caller injects the reader as cfg["legs_reader"] (default None ⇒ NA with the
    reason). Open question R1b-6: design §3 names reader2 the owner; the reader2 gate says research-only."""
    owner = "reader2.reader.read (structure + anatomy fusion, self-check)"
    read = c.cfg.get("legs_reader")
    if read is None:
        return _na(owner, LEGS_GATE)
    out, na = {}, {}
    for tf in c.cfg["area_tfs"]:
        df = c.f.get(tf)
        if df is None:
            na[tf] = f"{tf} bars missing"
            continue
        low = c.f.get("5M") if tf == "15M" else (c.m15 if tf == "1H" else None)
        R = read(df[["timestamp", "bar_end", "open", "high", "low", "close"]], c.cfg["reader2"],
                 low=None if low is None else low[["timestamp", "bar_end", "open", "high", "low", "close"]])
        t_now = R.trend_now() or {}
        out[tf] = {"legs": _legs_of(R, tf), "selfcheck_passes": R.passes,
                   "reader2_trend": {"trend": t_now.get("trend"), "origin": t_now.get("origin")},
                   "selfcheck_log": [e.get("text") for e in R.log]}
    if not out:
        return _na(owner, "; ".join(f"{k}: {v}" for k, v in na.items()))
    return _ok(owner, by_tf=out, missing=na,
               note="reader2_trend is reader2's own leg-trend (evidence); the structure section (swings2) owns trend")


# ------------------------------------------------------------------------------------------------ K4 areas + K6 lines — facts.validity
def _areas_lines(c):
    from decision3 import levels as LV
    from trendlines2 import two_touch as TT
    out = {}
    for tf in c.cfg["area_tfs"]:
        df = c.f.get(tf)
        if df is None or len(df) < 2:
            out[tf] = None
            continue
        s = FV.lookback(tf, c.cfg["validity"])
        t = len(df) - 1
        magnet = c.m15 if tf != "15M" else None
        bands = LV.display_bands(df, t, s, magnet_df=magnet)
        lines = TT.display_lines(df, t, s)
        out[tf] = {"bands": bands, "lines": lines, "mr": FV.mr_at(FV.bars_of(df), t, s), "settings": s,
                   "close": float(df["close"].iloc[t]), "asof_bar": str(df["timestamp"].iloc[t])}
    return out


def areas(c):
    owner = "decision3.levels.display_bands (facts.validity.check_band, TA3b / TA4)"
    al = c.bands_and_lines()
    by, na = {}, {}
    for tf, x in al.items():
        if x is None:
            na[tf] = f"{tf} bars missing"
            continue
        by[tf] = {"asof_bar": x["asof_bar"], "close": x["close"], "mr": x["mr"],
                  "lookback_sessions": x["settings"]["lookback_sessions"], "bands": x["bands"]}
    if not by:
        return _na(owner, "; ".join(f"{k}: {v}" for k, v in na.items()))
    return _ok(owner, by_tf=by, missing=na)


def lines(c):
    owner = "trendlines2.two_touch.display_lines (facts.validity.check_line, TA3)"
    al = c.bands_and_lines()
    by, na = {}, {}
    for tf, x in al.items():
        if x is None:
            na[tf] = f"{tf} bars missing"
            continue
        by[tf] = {"asof_bar": x["asof_bar"], "mr": x["mr"], "lines": x["lines"]}
    if not by:
        return _na(owner, "; ".join(f"{k}: {v}" for k, v in na.items()))
    return _ok(owner, by_tf=by, missing=na)


def confluence(c):
    owner = "facts.validity.confluence (K4 + K6.4)"
    al = c.bands_and_lines()
    out = []
    for ltf, lx in al.items():
        if lx is None:
            continue
        for btf, bx in al.items():
            if bx is None:
                continue
            for b in bx["bands"]:
                for ln in lx["lines"]:
                    x = FV.confluence(b, ln, lx["settings"])
                    if x:
                        out.append({"band_tf": btf, "line_tf": ltf, **x})
    if not any(al.values()):
        return _na(owner, "no frame for areas / lines")
    return _ok(owner, items=out)


# ------------------------------------------------------------------------------------------------ K11 patterns — patterns2
def _pattern_rec(rec, ts):
    from patterns2 import fold2 as F2
    if rec is None:
        return None
    out = {"bar": rec["bar"], "ts": rec["ts"], "phase": rec.get("phase"), "state": rec.get("agg"), "impulse": rec.get("I"),
           "valid_hypotheses": rec.get("n_valid"), "notes": rec.get("notes")}
    for k in ("pref", "alt"):
        h = rec.get(k)
        if h is None:
            out[k] = None
            continue
        j = F2.hyp_json(h, ts)
        out[k] = {x: j.get(x) for x in ("family", "kind", "sub", "barrier", "waves", "of", "points", "after_leg", "state", "flags",
                                         "c_eq_a", "lines_geom", "range_like")}
    out["c_eq_a"] = rec.get("c_eq_a")
    out["final_flag_risk"] = rec.get("final_flag_risk")
    out["position_in_parent"] = rec.get("position")
    return out


def patterns(c):
    owner = "patterns2.fold2.Fold (D2, D1) on legs2.ik2 I / K"
    from patterns2 import fold2 as F2
    lg, trk = c.legs2()
    if 2 not in trk or 1 not in trk:
        return _na(owner, "legs2 tracker degrees 1 / 2 missing")
    f2 = F2.Fold(lg, trk[2])
    f2.run()
    f1 = F2.Fold(lg, trk[1], parent=f2)
    f1.run()
    ts = f1.ts
    return _ok(owner, D2=_pattern_rec(f2.out.get(c.t), ts), D1=_pattern_rec(f1.out.get(c.t), ts),
               note="pattern facts at as_of (family, wave points, state); hypothesis scores are not facts and are dropped")


# ------------------------------------------------------------------------------------------------ K9 candles — decision3.method
def _arrays(c):
    """OHLC arrays for the decision3.method owners + FUT volume from the volume owner. Returns (A, volume_source text): the text tells
    "FUT volume missing" (no FUT input) apart from "FUT attach failed: <error>" (the volume owner raised)."""
    A = {k: c.m15[k].to_numpy(float) for k in ("open", "high", "low", "close")}
    if c.fut5 is None:
        return A, "NA (FUT volume missing: no FUT 5M bars at or before as_of)"
    try:
        v = c.fut15()
    except _Upstream as exc:
        return A, f"NA (FUT attach failed: {exc})"
    if v is None or not np.isfinite(v).any():
        return A, "NA (FUT volume missing: no FUT rows match the 15M spot bars)"
    A["volume"] = v
    return A, "FUT 15M (volume owner); bars with incomplete FUT 5M children are NA"


def _visits(c, s3):
    """Valid bands (areas section) whose band the 15M bars touch now: the last touch is within decision3 `touch_window_bars` of as_of.
    arrival = first bar of that touch group (touches ≤ touch_window_bars apart — decision3 engine's own "in / at the area" rule).
    Reaction side = the band's role (support ⇒ +1, resistance ⇒ −1): a fact about the band, not a trade direction."""
    al = c.bands_and_lines()
    H, L = c.m15["high"].to_numpy(float), c.m15["low"].to_numpy(float)
    w = int(s3["touch_window_bars"])
    B = FV.bars_of(c.m15)
    out = []
    for tf, x in al.items():
        if x is None:
            continue
        start = FV.session_start(B, c.t, int(x["settings"]["lookback_sessions"]))
        for b in x["bands"]:
            if not b.get("valid"):
                continue
            hits = [i for i in range(start, c.t + 1) if L[i] <= b["hi"] and H[i] >= b["lo"]]
            if not hits or c.t - hits[-1] > w:
                continue
            arm = hits[-1]
            for i in reversed(hits[:-1]):
                if arm - i > w:
                    break
                arm = i
            out.append({"tf": tf, "band": b, "arrival_bar": arm, "d": 1 if b["role"] == FV.SUP else -1})
    return out


def _structure_swings(c, t):
    """The finest structure degree's swings (swings2, Abhi's approved D1 / D2) confirmed by bar t — the decision engine's own source.
    Returns (swings, error); an error ⇒ no approach leg (never invented), and the reason is kept."""
    from swings2 import settings as S2
    try:
        res, _, _ = c.swings()
    except Exception as exc:                                               # noqa: BLE001
        return [], str(exc)
    low = min((res.get("settings") or S2.DEFAULTS).get("structure_degrees", S2.DEFAULTS["structure_degrees"]))
    deg = next((d for d in sorted(res["pivots"]) if d >= low and res["pivots"].get(d)), None)
    return [p for p in (res["pivots"].get(deg, []) if deg is not None else []) if p.confirm_bar <= t], None


def candles(c):
    owner = "decision3.method.candle_read / reversal_form / zone_study / commitment"
    from decision3 import method as M
    s3 = c.s3()
    A, vsrc = _arrays(c)
    tss = c.m15["timestamp"].to_numpy()
    t = c.t
    mr = FV.mr_at(FV.bars_of(c.m15), t)
    last = {"ts": str(c.m15["timestamp"].iloc[t]), "open": A["open"][t], "high": A["high"][t], "low": A["low"][t], "close": A["close"][t],
            "read": M.candle_read(A, t, s3)}                                # no visit context ⇒ "big" is None (see each study's own read)
    forms = {}
    for d, name in ((1, "up"), (-1, "down")):
        f = M.reversal_form(A, t, d, s3, tss)
        forms[name] = None if f is None else {"form": f[0], "candles": f[1]}
    studies = []
    known, known_err = _structure_swings(c, t)
    for v in _visits(c, s3):
        b, d, a = v["band"], v["d"], v["arrival_bar"]
        lvl = {"lo": b["lo"], "hi": b["hi"]}
        zs = M.zone_study(A, a, t, d, s3, mr)
        away = [p.bar for p in known if p.bar < a and ((p.kind == "L" and p.price < b["lo"]) if d < 0 else (p.kind == "H" and p.price > b["hi"]))]
        appr = range(max(away) + 1, a) if away else None                  # method §3 / Abhi (P2): the leg from the last swing built away
        present, why, cm = M.commitment(A, t, d, lvl, s3, tss, win=a, approach=appr)   # from the area, across gaps and sessions
        cm["approach_from"] = None if appr is None else str(c.m15["timestamp"].iloc[appr.start]) if appr.start < a else None
        if known_err:
            cm["approach_error"] = f"swings2 unavailable ({known_err})"
        cm["read"] = M.candle_read(A, t, s3, a)                            # "big" = vs this visit's own candles (method §3)
        studies.append({"band_tf": v["tf"], "band": [b["lo"], b["hi"]], "role": b["role"], "reaction_side": "up" if d > 0 else "down",
                        "arrival": {"bar": a, "ts": str(c.m15["timestamp"].iloc[a])}, "bars_in_study": t - a + 1,
                        "zone_study": zs, "commitment": {"present": bool(present), "reason": GRADE_TXT.sub("", why), **cm}})
    return _ok(owner, last_bar=last, reversal_form_at_last_bar=forms, area_studies=studies, volume_source=vsrc, **c.stale_facts(),
               note="area_studies only for valid bands touched within decision3 touch_window_bars of as_of")


# ------------------------------------------------------------------------------------------------ K10 volume — opportunity_engine.volume
def _attach_volume(c):
    from opportunity_engine import volume as OV
    if c.fut5 is None:
        return None
    f15 = c.m15.assign(bar_start=c.m15["timestamp"])
    s5 = c.f.get("5M")
    f5 = s5.assign(bar_start=s5["timestamp"]) if s5 is not None else \
        pd.DataFrame({"bar_start": pd.to_datetime(c.fut5["timestamp"]).drop_duplicates().sort_values().reset_index(drop=True)})
    fut = OV.near_month_rows(c.fut5)                                         # Abhi (R1b-3): roll दिवशी सुद्धा फक्त near-month
    frames, cov = OV.attach_futures_volume({"5m": f5, "15m": f15}, fut)
    v = np.array(frames["15m"]["volume"].to_numpy(float), dtype=float)
    v[~(v > 0)] = np.nan                                                    # owner: 0 = no FUT row ⇒ NA, never a guess
    # completeness (adapter facts, not a rule): a 15M bar whose FUT 5M children (distinct 5M starts inside it) are fewer than the 5M
    # slots of the bar is under-counted by the sum ⇒ NA for that bar; bars where more than one contract was summed are listed.
    ft = pd.to_datetime(fut["timestamp"]).to_numpy()
    st, en = c.m15["timestamp"].to_numpy(), c.m15["bar_end"].to_numpy()
    pos = np.searchsorted(st, ft, side="right") - 1
    ok = (pos >= 0) & (ft < en[np.clip(pos, 0, len(st) - 1)])
    slot = pd.Timedelta(minutes=M3.LTF_OF.get(15, 5))
    kids = pd.Series(ft[ok]).groupby(pos[ok]).nunique()
    ccol = next((k for k in ("contract", "expiry") if k in fut.columns), None)
    multi = pd.Series(fut[ccol].to_numpy()[ok]).groupby(pos[ok]).nunique() if ccol else pd.Series(dtype=int)
    incomplete = []
    for i in range(len(st)):
        need = int((pd.Timestamp(en[i]) - pd.Timestamp(st[i])) / slot)
        got = int(kids.get(i, 0))
        if 0 < got < need:
            incomplete.append({"ts": str(pd.Timestamp(st[i])), "fut_5m_children": got, "expected": need})
            v[i] = np.nan
    c._cov = cov
    c._incomplete = incomplete
    c._multi = [str(pd.Timestamp(st[i])) for i, n in multi.items() if n > 1]
    return v


def volume(c):
    owner = "opportunity_engine.volume.attach_futures_volume (near-month FUT 5M ⇒ 09:15-anchored 15M sums)"
    if c.fut5 is None:
        return _na(owner, "FUT volume missing (no FUT 5M bars at or before as_of)")
    v = c.fut15()
    if v is None or not np.isfinite(v).any():
        return _na(owner, "FUT volume missing (no FUT rows match the 15M spot bars)")
    m = c.m15
    t = c.t
    up = (m["close"] > m["open"]).to_numpy()
    dn = (m["close"] < m["open"]).to_numpy()
    day = m["timestamp"].dt.normalize()
    sess = (day == day.iloc[t]).to_numpy()
    start = FV.session_start(FV.bars_of(m), t, FV.lookback("15M")["lookback_sessions"])
    win = np.arange(len(m)) >= start

    def side(mask):
        x = v[mask]
        x = x[np.isfinite(x)]
        return {"bars": int(len(x)), "mean": float(np.mean(x)) if len(x) else None, "sum": float(np.sum(x)) if len(x) else None}
    inc = {x["ts"]: x for x in getattr(c, "_incomplete", [])}

    def why(i):
        k = str(m["timestamp"].iloc[i])
        if k in inc:
            return f"incomplete FUT 5M children ({inc[k]['fut_5m_children']} of {inc[k]['expected']}) — sum would under-count"
        return "no FUT row for this bar"
    bars = [{"ts": str(m["timestamp"].iloc[i]), "side": "up" if up[i] else ("down" if dn[i] else "flat"), "volume": v[i],
             **({} if np.isfinite(v[i]) else {"reason": why(i)})} for i in np.flatnonzero(sess)]
    last = {"ts": str(m["timestamp"].iloc[t]), "volume": v[t], **({} if np.isfinite(v[t]) else {"reason": why(t)})}
    return _ok(owner, coverage=getattr(c, "_cov", None), last_bar=last, incomplete_bars=getattr(c, "_incomplete", []),
               multi_contract_bars=getattr(c, "_multi", []),
               session={"up_bars": side(sess & up), "down_bars": side(sess & dn), "bars": bars},
               lookback={"from": str(m["timestamp"].iloc[start]), "up_bars": side(win & up), "down_bars": side(win & dn)},
               note="up / down = candle colour on spot 15M; which side is the trend side is the reader's call (structure section)")


# ------------------------------------------------------------------------------------------------ K1 at LTF — decision3.method.ltf_choch
def ltf_choch(c):
    owner = "decision3.method.ltf_choch (c1, close-only CHoCH on 5M)"
    from decision3 import method as M
    from swings2 import engine as SE
    if c.f.get("5M") is None:
        return _na(owner, "5M spot bars missing")
    L = M.ltf_frame(c.f["5M"], 5, "5M")
    s3 = c.s3()
    vis = _visits(c, s3)
    d1_err = None
    try:
        res, _, _ = c.swings()
        d1 = SE.known(res, 1, c.as_of)
    except _Upstream as exc:
        d1, d1_err = [], str(exc)
    out = []
    t_end = c.m15["bar_end"].iloc[c.t]
    for v in vis:
        b, d, a = v["band"], v["d"], v["arrival_bar"]
        t_start = c.m15["timestamp"].iloc[a]
        kind = "H" if d > 0 else "L"                                       # the swing the move into the band came from (pullback start)
        prev = [p for p in d1 if p.kind == kind and p.bar < a]
        t_ctx = pd.Timestamp(prev[-1].ts) if prev else t_start
        x = M.ltf_choch(L, d, t_ctx, t_start, t_end, {"lo": b["lo"], "hi": b["hi"]})
        note = {} if prev else {"context_note": "context falls back to the arrival bar: " + (
            f"swings2 unavailable ({d1_err})" if d1_err else "no confirmed swings2 D1 swing before the arrival")}
        out.append({"band_tf": v["tf"], "band": [b["lo"], b["hi"]], "role": b["role"], "reaction_side": "up" if d > 0 else "down",
                    "context_from": str(t_ctx), "study_from": str(t_start), "study_to": str(t_end), **note, **x})
    return _ok(owner, visits=out, note="studied only at valid bands touched within decision3 touch_window_bars of as_of; context starts "
                                       "at the last confirmed swings2 D1 swing before the arrival (else at the arrival)")


# ------------------------------------------------------------------------------------------------ K5 liquidity — decision3.liquidity
def liquidity(c):
    owner = "decision3.liquidity.pools / sweeps_and_traps"
    from decision3 import levels as LV
    from decision3 import liquidity as LQ
    res, _, _ = c.swings()
    s3 = c.s3()
    V = SimpleNamespace(levels=LV.Levels(res, s=s3), s=s3)                 # thin adapter: the owner reads V.levels (A, ts, pivots, σ_1H) + V.s
    t = c.t
    pools = LQ.pools(V, t)
    ts = c.m15["timestamp"]
    if s3.get("liquidity_rule", "equal") == "equal":                      # method §3: the current leg — from the last confirmed swing of the
        sw_bars = [p.bar for p in getattr(V.levels, "_known0", []) if p.confirm_bar <= t and p.bar < t]   # structure (as V22 reads the
        start = max(sw_bars) if sw_bars else 0                             # pullback's own window), never a fixed look-back
        sw, tr = LQ.sweeps_and_traps(V, t, start=start)
        win = {"window_from": str(ts.iloc[max(1, start)])}
    else:
        sw, tr = LQ.sweeps_and_traps(V, t, int(s3["liquidity_lookback"]))
        win = {"lookback_bars": int(s3["liquidity_lookback"])}
    for x in sw + tr:
        x["ts"] = str(ts.iloc[x["bar"]])
    return _ok(owner, pools=pools, sweeps=sw, traps=tr, **win)


# ------------------------------------------------------------------------------------------------ K13 gaps — vision.gap_context
def gaps(c):
    owner = "vision.gap_context.build"
    from vision import gap_context as GC
    cut = c.f.get("1m")
    if cut is None:
        return _na(owner, "1m spot bars missing (the gap owner reads complete 1m sessions)")
    mr = FV.mr_at(FV.bars_of(c.m15), c.t)
    g = GC.build(cut[["timestamp", "open", "high", "low", "close"]], c.as_of, mr, None, None, c.f.get("D"))
    if g.get("reason"):
        return _na(owner, f"gap owner: {g['reason']}")
    return _ok(owner, **g)


# ------------------------------------------------------------------------------------------------ K8 / K14 context — vision.context
def context(c):
    owner = "vision.context.prev_day / prev_week / opening"
    cut = c.f.get("1m")
    if cut is None:
        return _na(owner, "1m spot bars missing (the context owner reads complete 1m sessions)")
    cut = cut[["timestamp", "open", "high", "low", "close"]]
    day = c.as_of.normalize()
    pdx, pw, op = VC.prev_day(cut, day), VC.prev_week(cut, day), VC.opening(cut, day, c.as_of)
    mins = int((c.as_of - (day + VC.OPEN_T)).total_seconds() // 60)
    na = {"vix": "no owner function yet (design §3: VIX lives in chart_reader/evidence)",
          "fii_dii": "no owner function yet (design §3: to move in from vision_led)",
          "global_cues": "no owner function yet (design §3: to move in from vision_led)"}
    if pdx is None:
        na["prev_day"] = "no complete previous session in the 1m data (owner's minimum 1m bars per session)"
    if pw is None:
        na["prev_week"] = "no complete previous week in the 1m data"
    if op is None:
        na["opening"] = "no 1m bar of the as_of session at or before as_of"
    if pdx is None and pw is None and op is None:
        return _na(owner, "no complete previous session / week and no bar today in the 1m data")
    return _ok(owner, prev_day=pdx, prev_week=pw, opening=op, minutes_since_open=mins, missing=na,
               note="context only, never a trigger (design §3)")


# ------------------------------------------------------------------------------------------------ K10 RSI divergence — rsi2
def divergence(c):
    owner = "rsi2.engine.RSI.known (pivot-based divergence on swings2 pivots)"
    from rsi2 import engine as RE
    lg, _ = c.legs2()
    _, struct, _ = c.swings()
    R = RE.RSI(lg, struct)
    t = c.t
    known = R.known(t)
    r15 = R.r15[t]
    return _ok(owner, rsi15_at_asof=None if not np.isfinite(r15) else float(r15), rsi_warmup=bool(R.warm[t]),
               known_count=len(known), last=known[-int(c.cfg["divergences_max"]):],
               note="divergence facts only (pivots, RSI values, known bar); the owner's grade / strength are dropped")


OWNERS = {"structure": structure, "legs": legs, "areas": areas, "lines": lines, "confluence": confluence, "patterns": patterns,
          "candles": candles, "volume": volume, "ltf_choch": ltf_choch, "liquidity": liquidity, "gaps": gaps, "context": context,
          "divergence": divergence}
OWNER_NAMES = {"structure": "swings2 (+ pivots)", "legs": "reader2", "areas": "decision3.levels", "lines": "trendlines2.two_touch",
               "confluence": "facts.validity", "patterns": "patterns2", "candles": "decision3.method", "volume": "opportunity_engine.volume",
               "ltf_choch": "decision3.method.ltf_choch", "liquidity": "decision3.liquidity", "gaps": "vision.gap_context",
               "context": "vision.context", "divergence": "rsi2"}


# ------------------------------------------------------------------------------------------------ the dossier
def build_dossier(symbol, bars_by_tf, fut_bars_by_tf=None, as_of=None, cfg=None):
    """Facts dossier at `as_of` (default: close of the last 15M bar).

    bars_by_tf: spot bars {"15M": required, "5M": LTF CHoCH, "1m": context / gaps, "1H": optional (else complete hours from 15M),
    "D": optional daily (gap ATR / trend)}; each a DataFrame with timestamp (bar start, IST) + open / high / low / close [+ bar_end].
    fut_bars_by_tf: {"5M": near-month FUT 5M bars with timestamp + volume [+ expiry / contract]} — FUT volume (K10).
    Returns {"schema", "symbol", "as_of", "inputs", "sections": {name: {"status": OK | NA, "owner", ...facts | "reason"}}}.
    Every input frame (spot all TFs + FUT) is checked against the sealed holdout for `symbol` first (HoldoutError, never NA)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    bars_by_tf = bars_by_tf or {}
    fut_bars_by_tf = fut_bars_by_tf or {}
    guard_inputs(symbol, bars_by_tf, fut_bars_by_tf)
    as_of = None if as_of is None else pd.Timestamp(_naive([as_of]).iloc[0])
    m15 = _closed(bars_by_tf.get("15M"), 15, as_of)
    if m15 is None:
        raise ValueError("build_dossier: 15M spot bars (closed at or before as_of) are required")
    if as_of is None:
        as_of = pd.Timestamp(m15["bar_end"].iloc[-1])
    frames = {"15M": m15, "5M": _closed(bars_by_tf.get("5M"), 5, as_of), "1m": _closed(bars_by_tf.get("1m"), 1, as_of),
              "D": _closed_daily(bars_by_tf.get("D"), as_of)}
    frames["1H"] = _closed(bars_by_tf.get("1H"), 60, as_of) if bars_by_tf.get("1H") is not None else _hours_from_15m(m15)
    if frames["1H"] is not None and not len(frames["1H"]):
        frames["1H"] = None
    fut5 = _closed(fut_bars_by_tf.get("5M"), 5, as_of, keys=_fut_keys(fut_bars_by_tf.get("5M")))
    c = _Ctx(symbol, frames, fut5, as_of, cfg)
    sections = {name: _run(OWNER_NAMES[name], lambda fn=fn: fn(c)) for name, fn in OWNERS.items()}
    return {"schema": SCHEMA, "symbol": symbol, "as_of": str(as_of),
            "asof_bar": {"tf": "15M", "ts": str(m15["timestamp"].iloc[-1]), "close": round(float(m15["close"].iloc[-1]), 2),
                         **c.stale_facts()},
            "inputs": {**{tf: _frame_info(frames[tf]) for tf in ("15M", "1H", "5M", "1m", "D")}, "FUT_5M": _frame_info(fut5)},
            "sections": sections}
