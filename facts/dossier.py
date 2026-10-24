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
  • Layer 6b (Abhi's method, CHART_READER_METHOD.md §5): the areas, lines, visits, zone study, commitment, LTF change of character and
    RSI divergence are the DECISION's own reads — `decision3.engine.V22` on the same cut bars (layers 1–5 as merged): areas + K4 state
    (`levels.snapshot`), lines + touch N (`trendline.swing_line` / `touch_groups` / `reaction_touch`), the visit by structure
    (`V22.visit`, never a bar count), the confirmation (`V22._confirm`) and `V22.rsi_divergence` (pushes inside the move, degree,
    zone degree). `cfg["display_finder"] = "validity"` keeps the R1a display finder (facts.validity) for the areas / lines /
    confluence sections only (legacy, for the R1a golden comparison).
  • DECISIONS 37 / 51 (Abhi: "every output reads exactly what the engine read at the decision"): with decision3 `trigger_tf = 5M` (the
    default) the dossier follows the engine's 5M decision — `V22.decide5(j)` at the last 5M candle closed at as_of, on the same V22 —
    instead of re-deriving the visit on the last closed 15M bar: the areas / lines at that decision's 15M bar k(j), the visits by the
    engine's 5M functions (`entry_models5.Reader5.visit5`: a visit may start on a 5M candle inside the 15M bar in progress), the
    required set on the visit's 5M candles (`confirm5` / `c0`), the E4 (b) objects it read (section `e4b_objects`: broken areas / lines
    with their lifecycle, the revisit, the E4 state), the liquidity on the engine's own levels (with the Daily frame), and the engine's
    row itself (section `trigger`: the 5M candle, every armed object with each model's state, the fired entries — the payload's source).
    Reused, never re-read. `trigger_tf = 15M` (what-if) = the earlier dossier, byte for byte (pinned by tests).
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
    "display_finder": "method",      # layer 6b: areas / lines / confluence = the decision's own (decision3 V22); "validity" = the R1a
                                     # display finder (facts.validity: fractal anchors, MR tolerances, session look-back) — legacy only
}
DISPLAY_FINDERS = ("method", "validity")
# keys an owner may return that are a grade / score / vote, never a fact (design §3) — dropped everywhere in the dossier
NOT_FACTS = frozenset({"grade", "score", "scores", "vote", "votes", "conviction", "decision", "confidence", "verdict", "ratio",
                       "strength", "completion", "momentum"})
GRADE_TXT = re.compile(r"\s*·\s*grade\s+\S+")                          # decision3 commitment text carries its grade ⇒ removed
SECTIONS = ("structure", "legs", "areas", "lines", "confluence", "patterns", "candles", "volume", "ltf_choch", "liquidity", "gaps",
            "context", "divergence")
# DECISIONS 37 / 51 (trigger_tf = 5M, the default): the dossier follows the 5M trigger — two more sections, the engine's own 5M decision
# (`trigger`) and the E4 (b) objects it read (`e4b_objects`). trigger_tf = 15M (what-if) = SECTIONS only, byte for byte as before.
SECTIONS_5M = SECTIONS + ("trigger", "e4b_objects")
TRIGGER_TFS = ("5M", "15M")
OWNER_5M = {"candles": "decision3.method.candle_read / reversal_form + the visit's 5M study (entry_models5.Reader5: visit5 / confirm5 / c0 / "
                       "absorbing) at the engine's 5M decision",
            "ltf_choch": "decision3.method.ltf_choch (c1, close-only CHoCH on 5M) via decision3.entry_models5.Reader5.confirm5"}


def sections_of(trigger_tf):
    """The section names of a dossier read with this trigger frame (decision3 setting `trigger_tf`)."""
    return SECTIONS_5M if str(trigger_tf).upper() == "5M" else SECTIONS


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

    def v22(self):
        """The decision engine itself (decision3.engine.V22) on the same cut bars: closed Daily bars when given (as the live engine is
        fed), the 5M spot as the LTF, the FUT 5M bars as volume; the shared swings2 result when the swing scale is the same (else V22
        builds its own with its calibrated scale). Facts only — no decision is read from it here."""
        def build():
            from decision3 import engine as E3
            s3 = self.s3()
            res = self.swings()[0] if (self.cfg["swings2"] is None and E3.swing_scale(s3) is None) else None
            cols = ["timestamp", "bar_end", "open", "high", "low", "close"]
            d = self.f.get("D")
            return E3.V22(self.m15[cols], self.f.get("1m"), None if d is None else d[cols], s=self.cfg["decision3"], res=res,
                          ltf=self.f.get("5M"), futures=self.fut5)
        return self.memo("decision3.engine.V22", build)

    def method(self):
        """The method's reads at as_of (memo): trend side, areas, armed areas (with their line labels), lines, visits in progress."""
        return self.memo("decision3 method reads", lambda: _method_reads(self))

    def trigger_tf(self):
        """decision3 `trigger_tf` (DECISIONS 37): "5M" (default) ⇒ the dossier follows the engine's 5M decision; "15M" ⇒ as before."""
        tf = str(self.s3().get("trigger_tf", "5M")).upper()
        if tf not in TRIGGER_TFS:                                          # a typo never silently picks a frame
            raise ValueError(f"build_dossier: trigger_tf {tf!r} — allowed: {', '.join(TRIGGER_TFS)}")
        return tf

    def decision5(self):
        """DECISIONS 37 / 51: the engine's own decision at the 5M close — `V22.decide5(j)` on the same V22 (j = the last 5M candle closed
        at as_of; k = the last 15M bar closed at that 5M close) and the 5M reader whose memo that decision filled (`entry_models5.Reader5`,
        the same functions, never a second reading). Fails (⇒ NA with the reason) without 5M spot bars."""
        def build():
            from decision3 import entry_models5 as EM5
            V = self.v22()
            F = V.trigger_frame()
            if not F.n:
                raise ValueError("5M spot bars missing — the engine's 5M decision cannot be read (DECISIONS 37: the trigger is read on 5M)")
            j = int(np.searchsorted(F.end, np.datetime64(self.as_of, "ns"), side="right")) - 1
            if j < 0:
                raise ValueError("no 5M candle closed at or before as_of")
            row = V.decide5(j)
            return {"V": V, "F": F, "j": j, "k": int(F.k_of[j]), "row": row, "R": EM5.Reader5(V, j)}
        return self.memo("decision3.engine.V22.decide5", build)


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


def _areas_validity(c):
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


def _lines_validity(c):
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


def _confluence_validity(c):
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


# ------------------------------------------------------------------------------------------------ layer 6b: the method's own reads
def _ts(c, b):
    return None if b is None else str(c.m15["timestamp"].iloc[int(b)])


def _bar_pt(c, p):
    """[bar, price] ⇒ {bar, ts, price}."""
    return {"bar": int(p[0]), "ts": _ts(c, p[0]), "price": float(p[1])}


def _method_reads(c):
    """The decision engine's own reads at as_of (layers 1–5 as merged), nothing re-implemented here:
      • trend side = V22 step ① (Daily Dow + Weekly parent) — the side the method arms;
      • areas = every alive area of `decision3.levels` with its K4 state (`snapshot`); the armed ones (`step2`: every valid area ahead
        in the trend direction, nearest first) carry the line label "confluence: line (touch N)" exactly as the decision reads them;
      • lines = `trendline.swing_line` for both trade sides (two separate reactions of the structure, touches by reactions), the
        reaction touch (`reaction_touch`, Abhi 4 B / L4-g) and the areas it meets (`confluence_areas` on that side's armed areas);
      • visits = every alive trade-location area (not BROKEN / DEAD) whose visit by structure (`V22.visit`) is in progress at as_of;
        for each: the confirmation as the engine reads it (`V22._confirm`: handover episode, commitment with the approach leg and the
        rejected push excluded, LTF change of character) and `V22.rsi_divergence` (pushes inside the move, degree, zone degree).
    The reaction side of a visit is the area's role (support ⇒ up): a fact about the area, not a trade direction."""
    from decision3 import daily as DD
    from decision3 import flip as FLP
    from decision3 import trendline as TL
    V = c.v22()
    t = c.t
    d5, why5 = None, None
    if c.trigger_tf() == "5M":                                             # DECISIONS 51: read at the 5M decision's own 15M bar k(j)
        try:
            d5 = c.decision5()
            if d5["k"] < 0:
                d5, why5 = None, "no 15M bar closed at the 5M decision yet"
            else:
                t = d5["k"]
        except _Upstream as exc:
            why5 = str(exc)
    ok1, why1, st, ctx = V.step1(t)
    tr = ctx["trend"]
    armed = V.step2(t, tr, ctx.get("band"))[2] if ok1 else []
    lab = {x["id"]: x for x in armed}
    areas = [lab.get(x["id"], x) for x in V.levels.snapshot(t)]
    lines = []
    for d in (TL.DOWN, TL.UP):
        ln = TL.swing_line(V, t, d)
        if ln is None:
            continue
        rt = TL.reaction_touch(V, t, d, ln)
        met = TL.confluence_areas(V, t, d, V.levels.active(t, "DOWN" if d < 0 else "UP"))
        lines.append({"d": d, "line": ln, "reaction_touch": rt, "areas_met": met})
    trend = {"daily": st.trend, "used": tr, "weekly": ctx["weekly"], "resolution": ctx["resolution"],
             "trade_side": list(DD.trade_side(tr)), "why": why1}
    if c.trigger_tf() == "5M":
        visits = _visits5(V, t, d5, areas, armed, tr) if d5 is not None else []
        return {"V": V, "t": t, "trend": trend, "areas": areas, "armed": [x["id"] for x in armed], "lines": lines, "visits": visits,
                "d5": d5, "visits_reason": why5}
    visits = []
    for x in areas:
        if x.get("state") in (FLP.BROKEN, FLP.DEAD) or not x.get("trade_location", True):
            continue
        d = 1 if x["role"] == "support" else -1
        vi = V.visit(t, x, d)
        if vi["start"] is None:
            continue
        k = V.pb.at(t, d) or {}
        _ok, _why, cm = V._confirm(t, d, x, k)
        arm = int(cm.get("arm_bar", vi["start"]))
        rsi = V.rsi_divergence(t, d, arm, x.get("tf", "1H"), cm.get("move_from_bar"))
        k0 = k.get("k_open_bar") if k.get("k_open_bar") is not None else t
        c0 = k.get("i_end_bar") if k.get("i_end_bar") is not None else k0     # the LTF context start, as V22._confirm reads it
        visits.append({"area": x, "d": d, "visit": vi, "arm": arm, "commit": cm, "rsi": rsi, "ltf_from": min(int(c0), arm),
                       "armed": x["id"] in lab})
    trend = {"daily": st.trend, "used": tr, "weekly": ctx["weekly"], "resolution": ctx["resolution"],
             "trade_side": list(DD.trade_side(tr)), "why": why1}
    return {"V": V, "t": t, "trend": trend, "areas": areas, "armed": [x["id"] for x in armed], "lines": lines, "visits": visits}


# ------------------------------------------------------------------------------------------------ DECISIONS 51: the engine's 5M reads
ENTRY_FACTS = ("model", "name", "variant", "direction", "side", "object", "area", "visit_id", "visit_start", "visit_start5", "area_visit_id",
               "area_visit_start", "cluster", "refined_base", "key", "trigger_tf", "trigger_ts", "trigger_bar_end", "trigger_ohlc",
               "trigger_volume", "trigger_bar15_ts", "context_bar_ts", "context_bar_end", "entry_ref", "invalidation", "invalidation_rule",
               "facts", "label", "evidence", "evidence_list", "confirming", "channel_evidence", "line_values")


def _entry_facts(e):
    """An engine entry (V22.decide5 row) as the dossier carries it: its own fields, unchanged (nothing re-read)."""
    return {k: e.get(k) for k in ENTRY_FACTS if k in e}


def _visits5(V, t, d5, areas, armed, trend):
    """The visits in progress at the 5M decision, read by the engine's own 5M functions on the same V22 (whose memo the decision filled):
    the visit `Reader5.visit5` (a visit may start on a 5M candle inside the 15M bar in progress), the required set `Reader5.confirm5`,
    the commitment `Reader5.c0`, the absorption gate `Reader5.absorbing`, the refined base `Reader.refined(k)`, the RSI read at the
    entry's 15M context (`V22.rsi_divergence(k, …, arm15, …, move_from)`, as the evidence list reads it), and the engine's armed record
    and entries of that visit. Areas: every alive trade-location area (the reaction side = its role) + the range edges the engine arms
    (DECISIONS 40)."""
    from decision3 import flip as FLP
    R, F, j, row = d5["R"], d5["F"], d5["j"], d5["row"]
    lvls = [x for x in areas if x.get("state") not in (FLP.BROKEN, FLP.DEAD) and x.get("trade_location", True)]
    edges = R.range_edge_areas(t, trend, armed) if hasattr(R, "range_edge_areas") else []
    have = {x.get("id") for x in lvls}
    lvls += [x for x in edges if x.get("id") not in have]
    arm_ids = {x["id"] for x in armed} | {x.get("id") for x in edges}
    out = []
    for x in lvls:
        d = 1 if x["role"] == "support" else -1
        vi = R.visit5(j, x, d)
        if vi["start5"] is None and vi.get("data") is None:
            continue
        vid = f"{R.uid_of(x)}@{vi['vid']}"                                  # A5: the engine's visit id (the place's stable id)
        eng = next((a for a in row.get("armed") or [] if a.get("object") == "area" and a.get("visit_id") == vid), None)
        ents = [_entry_facts(e) for e in row.get("entries") or [] if e.get("area_visit_id") == vid]
        v = {"area": x, "d": d, "visit5": vi, "visit_id": vid, "armed": x.get("id") in arm_ids, "engine": eng, "entries": ents,
             "start5": vi["start5"]}
        if vi["start5"] is not None:
            start = int(vi["start5"])
            appr = R.appr5(vi)
            ok5, cm5 = R.confirm5(x, d, start, appr)
            arm15 = min(int(F.b_of[start]), t)
            mf = (int(vi["approach_from15"]) - 1) if vi.get("approach_from15") is not None else None
            v.update(arm=arm15, commit=cm5, required_ok=bool(ok5), c0=R.c0(j, x, d, start, appr), absorbing=R.absorbing(j, x, d, start),
                     refined=R.refined(t, x, d) if R.refine_on() else None, appr=appr, move_from=mf,
                     rsi=V.rsi_divergence(t, d, arm15, x.get("tf", "1H") if x.get("tf") in ("1H", "D") else "1H", mf))
        out.append(v)
    return out


def _f5(d5, i):
    return None if i is None else d5["F"].T(int(i))


def _area_fact(c, x, armed=()):
    out = {k: v for k, v in x.items() if k not in ("tl", "line_touch")}
    out["born_ts"] = _ts(c, x.get("born_bar"))
    out["armed"] = x["id"] in armed
    if x.get("line_touch"):
        rt = x["line_touch"]
        out["line_touch"] = {**rt, "ts": _ts(c, rt["bar"]), "leg_from_ts": _ts(c, rt["leg_from"])}
    return out


def _line_fact(c, L):
    ln, rt, d = L["line"], L["reaction_touch"], L["d"]
    out = {"side": "falling line of swing highs (bear call side)" if d < 0 else "rising line of swing lows (bull put side)",
           "p1": _bar_pt(c, ln["p1"]), "p2": _bar_pt(c, ln["p2"]), "slope_per_bar": ln["slope"], "touches": ln["touches"],
           "touch_points": [[_ts(c, b) for b in g] for g in ln["touch_groups"]] if ln.get("touch_groups") else None,
           "value_at_asof": ln["value_t"],
           "reaction_touch": None if rt is None else {**rt, "ts": _ts(c, rt["bar"]), "leg_from_ts": _ts(c, rt["leg_from"])},
           "areas_met": [{k: a.get(k) for k in ("id", "tf", "role", "lo", "hi", "state", "confluence_label")} for a in L["areas_met"]]}
    return out


def _areas_method(c):
    owner = "decision3.levels (the decision's areas + K4 state) via decision3.engine.V22 — method layer 2"
    m = c.method()
    t = m["t"]
    return _ok(owner, asof_bar=_ts(c, t), close=float(c.m15["close"].iloc[t]), trend=m["trend"], armed=m["armed"],
               areas=[_area_fact(c, x, m["armed"]) for x in sorted(m["areas"], key=lambda x: x["dist"])],
               note="one base per area, wick to body, never merged or widened; state = K4 (ACTIVE / TESTED / BROKEN / FLIPPED / DEAD); "
                    "armed = the decision's watch list on the trend side, nearest first (method §4)")


def _lines_method(c):
    owner = "decision3.trendline.swing_line / touch_groups / reaction_touch via decision3.engine.V22 — method layer 4"
    m = c.method()
    return _ok(owner, lines=[_line_fact(c, L) for L in m["lines"]], rule=m["V"].s.get("line_rule", "logic"),
               note="a line = two separate reactions of the structure (D2), no close through it between them; touches counted by "
                    "reactions (the touch number is information; from the third touch on a trade location while unbroken)")


def _confluence_method(c):
    owner = "decision3.levels.snapshot (Daily / Weekly label) + decision3.trendline.confluence_areas (line label) via V22 — layer 4"
    m = c.method()
    items = [{k: x.get(k) for k in ("id", "tf", "role", "lo", "hi", "state", "confluence_label")} for x in m["areas"]
             if x.get("confluence_label")]
    return _ok(owner, items=items, note="confluence labels the area itself (same band, never a new or narrowed band)")


def areas(c):
    return _areas_validity(c) if c.cfg["display_finder"] == "validity" else _areas_method(c)


def lines(c):
    return _lines_validity(c) if c.cfg["display_finder"] == "validity" else _lines_method(c)


def confluence(c):
    return _confluence_validity(c) if c.cfg["display_finder"] == "validity" else _confluence_method(c)


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


COMMIT_OUT = ("choch", "handover_state", "handover", "handover_present", "absorption", "confirm_lines", "confirm_wait", "commit_present",
              "commit_why", "study_from", "arm_bar", "visit_start", "visit_start_bar", "visit_prev_end", "choch_vs_arm", "ltf_line",
              "approach_from", "move_from_bar", "visit_end")


def _side(d):
    return "up" if d > 0 else "down"


def _study(c, v):
    """One visit in progress (method §3 Visit by structure) as facts: the area, the arrival, the approach leg, the zone study of the
    visit's own candles, the handover episode, absorption and the commitment with its volume comparison — the engine's own read."""
    from decision3 import method as M
    V, t, x, d, a, cm = c.method()["V"], c.t, v["area"], v["d"], v["arm"], v["commit"]
    Av = V.vol_view(a, t)[0]
    hs = cm.get("handover_state") or {}
    commit = {k: val for k, val in cm.items() if k not in COMMIT_OUT}
    return {"band_tf": x.get("tf"), "band": [x["lo"], x["hi"]], "area_id": x["id"], "role": x["role"], "state": x.get("state"),
            "reaction_side": _side(d), "armed": v["armed"], "confluence_label": x.get("confluence_label"),
            "arrival": {"bar": a, "ts": _ts(c, a)}, "approach_from": cm.get("approach_from"), "visit_prev_end": cm.get("visit_prev_end"),
            "bars_in_study": t - a + 1, "zone_study": M.zone_study(Av, a, t, d, V.s),
            "handover": {"present": cm.get("handover_present"), "form": hs.get("form"), "seen_ts": hs.get("seen_ts"),
                         "cancelled": hs.get("cancelled"), "cancelled_ts": hs.get("cancelled_ts")},
            "absorption": cm.get("absorption"),
            "commitment": {"present": bool(cm.get("commit_present")), "reason": GRADE_TXT.sub("", str(cm.get("commit_why") or "")),
                           "read": M.candle_read(Av, t, V.s, a), **commit}}


def _study5(c, m, v):
    """One visit in progress at the 5M decision (DECISIONS 37 / 51) as the engine read it: the 5M visit start (and the 15M bin that holds
    it = the visit id), the approach leg on 5M, the refined base, the handover episode / commitment / LTF CHoCH (the required set read on
    the visit's 5M candles), the absorption gate, each model's state and the entries the engine fired there — the engine's own values."""
    from decision3 import method as M
    d5 = m["d5"]
    V, F, j, k = d5["V"], d5["F"], d5["j"], d5["k"]
    x, d, vi = v["area"], v["d"], v["visit5"]
    eng = v.get("engine") or {}
    out = {"band_tf": x.get("tf"), "band": [x["lo"], x["hi"]], "area_id": x["id"], "role": x["role"], "state": x.get("state"),
           "reaction_side": _side(d), "armed": v["armed"], "confluence_label": x.get("confluence_label"), "trigger_tf": "5M",
           "range_edge": x.get("range_edge"), "visit_id": v["visit_id"],
           "arrival": {"tf": "5M", "bar5": vi["start5"], "ts5": _f5(d5, vi["start5"]), "ts": vi["vid"],
                       "bin15_in_progress": None if vi.get("s15") is None else bool(int(vi["s15"]) > k)},
           "approach_from": _ts(c, vi["approach_from15"]) if vi.get("approach_from15") is not None and int(vi["approach_from15"]) < len(c.m15)
           else None,
           "models": eng.get("models"), "disarmed": eng.get("disarmed"), "side_since": eng.get("side_since"),
           "visit_extreme": eng.get("visit_extreme"), "entries": v["entries"]}
    if vi["start5"] is None:
        out["data"] = vi.get("data")
        return out
    start, cm = int(vi["start5"]), v["commit"]
    hs = cm.get("handover_state") or {}
    ok0, why0, cm0 = v["c0"]
    ap = v.get("appr")
    a_ab = int(hs.get("window_start", start))
    commit = {kk: val for kk, val in cm0.items() if kk not in COMMIT_OUT}
    out.update(
        approach_5m=None if not ap else {"from": _f5(d5, ap[0]), "to": _f5(d5, ap[-1]), "candles": len(ap)},
        bars_in_study=j - start + 1, refined_base=v.get("refined"),
        zone_study=M.zone_study(F.A, a_ab, j - 1, d, V.s) if j - 1 >= a_ab else None,
        handover={"present": hs.get("present"), "form": hs.get("form"), "seen_ts": _f5(d5, hs.get("seen_at")),
                  "cancelled": hs.get("cancelled"), "cancelled_ts": _f5(d5, hs.get("cancelled_at")), "tf": "5M"},
        absorption=v.get("absorbing"),
        commitment={"present": bool(ok0), "reason": GRADE_TXT.sub("", str(why0 or "")), "read": M.candle_read(F.A, j, V.s, start),
                    "tf": "5M", **commit},
        required_set={"read": "present" if v["required_ok"] else "absent", "handover": hs.get("present"),
                      "commitment": bool(ok0), "ltf_choch": (cm.get("choch") or {}).get("done"), "wait": cm.get("confirm_wait"),
                      "tf": "5M", "by_model": {e["model"]: (e.get("evidence_list") or {}).get("required") for e in v["entries"]},
                      "note": "read = the shared confirmation on the visit's 5M candles (Reader5.confirm5: handover + commitment + volume "
                              "+ 5M CHoCH); by_model = each fired entry's required set exactly as the engine wrote it in its evidence list"})
    return out


def candles(c):
    owner = "decision3.method.candle_read / reversal_form + the visit's zone study / commitment via decision3.engine.V22"
    from decision3 import method as M
    s3 = c.s3()
    A, vsrc = _arrays(c)
    tss = c.m15["timestamp"].to_numpy()
    t = c.t
    last = {"ts": str(c.m15["timestamp"].iloc[t]), "open": A["open"][t], "high": A["high"][t], "low": A["low"][t], "close": A["close"][t],
            "read": M.candle_read(A, t, s3)}                                # no visit context ⇒ "big" is None (see each study's own read)
    forms = {}
    for d, name in ((1, "up"), (-1, "down")):
        f = M.reversal_form(A, t, d, s3, tss)
        forms[name] = None if f is None else {"form": f[0], "candles": f[1]}
    try:
        m = c.method()
        if c.trigger_tf() == "5M":                                         # DECISIONS 51: the visit / required set the 5M decision read
            studies, why = [_study5(c, m, v) for v in m["visits"]], m.get("visits_reason")
            studies = None if why and not studies else studies
        else:
            studies, why = [_study(c, v) for v in m["visits"]], None
    except _Upstream as exc:                                               # the engine failed ⇒ no study, the reason kept (never silent)
        studies, why = None, str(exc)
    extra = {} if why is None else {"area_studies_reason": why}
    if c.trigger_tf() == "5M":
        owner = OWNER_5M["candles"]
    return _ok(owner, last_bar=last, reversal_form_at_last_bar=forms, area_studies=studies, volume_source=vsrc, **extra,
               **c.stale_facts(),
               note="area_studies = every alive area whose visit (by structure, method §3) is in progress at as_of — the engine's own "
                    "visit, approach leg, handover episode and commitment (FUT volume as the engine joins it); last_bar reads have no "
                    "visit context")


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
    owner = "decision3.method.ltf_choch (c1, close-only CHoCH on 5M) via decision3.engine.V22._confirm"
    if c.f.get("5M") is None:
        return _na(owner, "5M spot bars missing")
    m = c.method()
    if c.trigger_tf() == "5M":                                             # DECISIONS 51: the CHoCH the 5M decision read
        d5 = m.get("d5")
        out = []
        for v in m["visits"]:
            if v.get("start5") is None:
                continue
            x, ch = v["area"], v["commit"].get("choch")
            body = dict(ch) if ch else {"done": None, "line": "not read: the visit's study stopped earlier (absorption)"}
            out.append({"band_tf": x.get("tf"), "band": [x["lo"], x["hi"]], "area_id": x["id"], "role": x["role"],
                        "reaction_side": _side(v["d"]), "visit_id": v["visit_id"], "trigger_tf": "5M",
                        "context_from": _f5(d5, v["start5"]), "study_from": _f5(d5, v["start5"]), "study_to": d5["F"].E(d5["j"]), **body})
        extra = {} if not m.get("visits_reason") else {"visits_reason": m["visits_reason"]}
        return _ok(OWNER_5M["ltf_choch"], visits=out, **extra, note="read at every visit in progress at the 5M decision (DECISIONS 37 / 51): the visit's "
                                                    "first 5M candle … the 5M decision close, as the engine's required set reads it")
    t_end = str(c.m15["bar_end"].iloc[c.t])
    out = []
    for v in m["visits"]:
        x, ch = v["area"], v["commit"].get("choch")
        body = dict(ch) if ch else {"done": None, "line": "not read: the visit's study stopped earlier (absorption)"}
        out.append({"band_tf": x.get("tf"), "band": [x["lo"], x["hi"]], "area_id": x["id"], "role": x["role"],
                    "reaction_side": _side(v["d"]), "context_from": _ts(c, v["ltf_from"]), "study_from": _ts(c, v["arm"]),
                    "study_to": t_end, **body})
    return _ok(owner, visits=out, note="read at every visit in progress (method §3, by structure); context from the pullback's impulse "
                                       "end as the engine reads it (else the arrival)")


# ------------------------------------------------------------------------------------------------ K5 liquidity — decision3.liquidity
def _liquidity5(c):
    """DECISIONS 51 (O-12): liquidity on the engine's own levels — the V22 the 5M decision read (its Levels carry the Daily frame: Daily
    swings, Q40 prior levels), at that decision's 15M bar k; the current leg's window as before, and at every visit in progress the
    window the evidence list reads (`sweeps_and_traps(V, k, start = the visit's 15M arrival)`)."""
    owner = "decision3.liquidity.pools / sweeps_and_traps on the engine's V22 levels (with the Daily frame) at the 5M decision"
    from decision3 import liquidity as LQ
    m = c.method()
    V, t = m["V"], m["t"]
    s3 = V.s
    pools = LQ.pools(V, t)
    ts = pd.Series(pd.to_datetime(V.m15["timestamp"])).reset_index(drop=True)
    if s3.get("liquidity_rule", "equal") == "equal":
        sw_bars = [p.bar for p in getattr(V.levels, "_known0", []) if p.confirm_bar <= t and p.bar < t]
        start = max(sw_bars) if sw_bars else 0
        sw, tr = LQ.sweeps_and_traps(V, t, start=start)
        win = {"window_from": str(ts.iloc[max(1, start)])}
    else:
        sw, tr = LQ.sweeps_and_traps(V, t, int(s3["liquidity_lookback"]))
        win = {"lookback_bars": int(s3["liquidity_lookback"])}
    for x in sw + tr:
        x["ts"] = str(ts.iloc[x["bar"]])
    at = []
    for v in m["visits"]:
        if v.get("arm") is None:
            continue
        vs, vt = LQ.sweeps_and_traps(V, t, start=int(v["arm"]))
        for x in vs + vt:
            x["ts"] = str(ts.iloc[x["bar"]])
        at.append({"visit_id": v["visit_id"], "area_id": v["area"]["id"], "window_from": str(ts.iloc[int(v["arm"])]), "sweeps": vs,
                   "traps": vt})
    frame = {"daily_bars": int(len(V.daily_df)), "prior_levels": getattr(V.levels, "prior_note", None) or "read (Daily bars before the 15M window)"}
    return _ok(owner, pools=pools, sweeps=sw, traps=tr, **win, at_visits=at, daily_frame=frame, asof_bar=str(ts.iloc[t]))


def liquidity(c):
    if c.trigger_tf() == "5M":
        return _liquidity5(c)
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
DIV_KEEP = ("degree", "side", "type", "status", "bars", "price_rel", "count", "known_bar")


def _div_brief(c, x):
    out = {k: x.get(k) for k in DIV_KEEP}
    for p in ("L1", "L2"):
        out[p] = {k: x[p].get(k) for k in ("time", "price", "rsi")}
    out["known_ts"] = _ts(c, x.get("known_bar"))
    return out


def divergence(c):
    owner = "rsi2.engine.Divergence via decision3.engine.V22.rsi_divergence (method layer 5: pushes inside the move into the zone)"
    m = c.method()
    V, t = m["V"], m["t"]
    if getattr(V, "_rsi", None) is None:
        V.rsi_divergence(t, -1, t)                                          # the engine's own lazy owner (same object the decision reads)
    if isinstance(V._rsi, str):
        return _na(owner, "rsi2 Divergence failed — " + V._rsi)
    r = V._rsi.read(t)
    hist = [x for x in V._rsi.history(t) if x["type"] == "regular"]
    at = [{"band_tf": v["area"].get("tf"), "band": [v["area"]["lo"], v["area"]["hi"]], "area_id": v["area"]["id"],
           "reaction_side": _side(v["d"]), "zone_side": "bear" if v["d"] < 0 else "bull",
           **({"visit_id": v["visit_id"], "arm_ts": _ts(c, v["arm"])} if "visit_id" in v else {}), **v["rsi"]}
          for v in m["visits"] if "visit_id" not in v or v.get("rsi") is not None]
    return _ok(owner, rsi15_at_asof=r["rsi"], rsi_warmup=r["rsi_warmup"], known_count=len(hist),
               last=[_div_brief(c, x) for x in hist[-int(c.cfg["divergences_max"]):]],
               latest=[y["statement"] for y in r["latest"]], at_visits=at,
               note="method §3: consecutive swings of one degree, a new price extreme vs an RSI that does not exceed its previous extreme "
                    "(equal counts); at a visit only the pushes inside the move into the zone (the highest degree with two pushes), the "
                    "zone's own degree reported too — evidence, never a trigger")


# ------------------------------------------------------------------------------------------------ DECISIONS 51: the 5M decision itself
def trigger(c):
    """The engine's own decision at the 5M close (V22.decide5): the 5M candle, its 15M context bar, the trend side, every armed object with
    each model's state and every entry it fired — the engine's fields unchanged (what the stored payload is built from)."""
    owner = "decision3.engine.V22.decide5 (DECISIONS 37: the entry trigger on 5M) — the engine's own row"
    d5 = c.decision5()
    F, j, row = d5["F"], d5["j"], d5["row"]
    ohlc = {kk: float(F.A[kk][j]) for kk in ("open", "high", "low", "close")}
    return _ok(owner, trigger_tf="5M", candle={"bar5": j, "ts": F.T(j), "bar_end": F.E(j), **ohlc},
               context_bar={"bar": d5["k"], "ts": row.get("context_ts"), "bar_end": row.get("context_bar_end")},
               trend_used=row.get("trend_used"), watch_list=[x.get("id") for x in row.get("watch_list") or []],
               entries=[_entry_facts(e) for e in row.get("entries") or []], armed=row.get("armed") or [], why=row.get("why"),
               note="the engine's row at this 5M close: armed = every object the entry models read (areas, range edges, E4 (b) objects) "
                    "with each model's state; entries = the fired entries as the engine wrote them (the stored payload's source)")


def _events(c, L, k):
    out = [{"bar": int(L.born_bar), "ts": _ts(c, L.born_bar), "event": "born", "detail": "/".join(L.births)}]
    for b, kind, det in L.events:
        if int(b) <= k:
            out.append({"bar": int(b), "ts": _ts(c, b), "event": kind, "detail": str(det)})
    if L.dead_bar is not None and int(L.dead_bar) <= k and not any(x["event"] == "dead" for x in out):
        out.append({"bar": int(L.dead_bar), "ts": _ts(c, L.dead_bar), "event": "dead", "detail": "dead"})
    return out


def e4b_objects(c):
    """DECISIONS 51 (O-9): the E4 (b) objects the engine read at the 5M decision — every trade-direction BROKEN area / line known at k
    (`Reader.broken_objects`), its lifecycle known at k, the revisit the engine reads (`Reader5.touch_visit5`: price back AT it; ends
    by a 15M swing away), the E4 state, the required set on the revisit's 5M candles (`Reader5.confirm5`, as the entry reads it) and the
    E4 (b) entry when one fired."""
    owner = "decision3.entry_models.Reader.broken_objects + entry_models5.Reader5 (touch_visit5 / broken5 / confirm5) at the 5M decision"
    from decision3 import trendline as TL
    m = c.method()
    d5 = m.get("d5")
    if d5 is None:
        return _na(owner, m.get("visits_reason") or "the engine's 5M decision could not be read")
    V, F, R, j, k, row = d5["V"], d5["F"], d5["R"], d5["j"], d5["k"], d5["row"]
    tr = m["trend"]["used"]
    if tr not in ("UP", "DOWN"):
        return _ok(owner, objects=[], reason=f"the engine reads E4 (b) objects only with a trend side (UP / DOWN); trend side: {tr}")
    if "E4" not in R.on:
        return _ok(owner, objects=[], reason="E4 is off (entry_models_on)")
    d = M3._dir(tr)
    objs = []
    for kind, obj, _t, _a, _sw, born in R.broken_objects(k, d):
        oid = obj["id"] if kind == "area" else f"line:{obj['id']}"
        eng = next((a for a in row.get("armed") or [] if a.get("object") == "broken_" + kind and str(a.get("area_id")) == str(oid)), None)
        x = {"object": "broken_" + kind, "id": oid, "direction": int(d), "known_from": _ts(c, born) if int(born) < len(c.m15) else
             "the next 15M bar", "known_at_k": bool(int(born) <= k)}
        if kind == "area":
            x.update({kk: obj.get(kk) for kk in ("tf", "role", "lo", "hi", "state", "break_dir", "confluence_label")},
                     broken_at=_ts(c, obj.get("broken_at")), lifecycle=_events(c, V.levels.L[obj["id"]], k))
        else:
            kb = TL.break_known_at(V, obj)
            x.update(tf=obj.get("tf"), family=obj.get("family"), degree=obj.get("degree"), kind=obj.get("kind"),
                     role="support" if d < 0 else "resistance", break_side=obj.get("break_side"), touches=obj.get("touches"),
                     p1=_bar_pt(c, obj["p1"]), p2=_bar_pt(c, obj["p2"]) if obj.get("p2") is not None else None, slope_per_bar=obj.get("slope"),
                     broken_at=_ts(c, obj.get("break_bar")), break_known_at=_ts(c, kb), parallel_of=obj.get("parallel_of"),
                     value_at_decision=round(F.line_value(obj, j), 2),
                     lifecycle=[{"ts": _ts(c, obj["p2"][0]) if obj.get("p2") is not None else None, "event": "line drawn (2nd touch)"},
                                {"ts": _ts(c, obj.get("break_bar")), "event": "broken", "detail": obj.get("break_side")}])
        if eng is None:
            x["revisit"] = None
            x["revisit_why"] = "no revisit in progress at the 5M decision (price is not back at it, or it left by structure)"
        else:
            x["revisit"] = {kk: eng.get(kk) for kk in ("visit_id", "visit_start", "visit_start5", "lo", "hi", "models", "disarmed",
                                                         "side_since")}
            st5 = int(eng["visit_start_bar"])
            if kind == "area":
                lvl = {**obj, "visit_from": min(int(F.b_of[st5]), k)}
            else:
                v = round(F.line_value(obj, j), 2)
                lvl = {"id": oid, "lo": v, "hi": v, "tf": "line", "role": eng.get("role"), "births": ["tl"], "sweeps": 0, "fresh": None,
                       "confluence_line": True, "confluence": []}
            if not eng.get("disarmed"):
                ok5, cm5 = R.confirm5(lvl, d, st5, None)
                hs = cm5.get("handover_state") or {}
                x["required_set"] = {"read": "present" if ok5 else "absent", "handover": hs.get("present"),
                                     "ltf_choch": (cm5.get("choch") or {}).get("done"), "wait": cm5.get("confirm_wait"), "tf": "5M"}
        x["entries"] = [_entry_facts(e) for e in row.get("entries") or [] if e.get("object") == "broken_" + kind
                        and str((e.get("area") or {}).get("id")) == str(oid)]
        objs.append(x)
    return _ok(owner, direction=int(d), objects=objs,
               note="E4 (b): a broken area / line of the trade direction; a revisit only while price is back AT it (ends by a 15M swing "
                    "away); approach side and the 5M rejection candle as the engine reads them (DECISIONS 37, 38)")


OWNERS = {"structure": structure, "legs": legs, "areas": areas, "lines": lines, "confluence": confluence, "patterns": patterns,
          "candles": candles, "volume": volume, "ltf_choch": ltf_choch, "liquidity": liquidity, "gaps": gaps, "context": context,
          "divergence": divergence, "trigger": trigger, "e4b_objects": e4b_objects}
OWNER_NAMES = {"structure": "swings2 (+ pivots)", "legs": "reader2", "areas": "decision3.levels", "lines": "decision3.trendline",
               "confluence": "decision3.levels + decision3.trendline", "patterns": "patterns2", "candles": "decision3.method",
               "volume": "opportunity_engine.volume", "ltf_choch": "decision3.method.ltf_choch", "liquidity": "decision3.liquidity",
               "gaps": "vision.gap_context", "context": "vision.context", "divergence": "rsi2.engine.Divergence",
               "trigger": "decision3.engine.V22.decide5", "e4b_objects": "decision3.entry_models5 (E4 b objects)"}


# ------------------------------------------------------------------------------------------------ the dossier
def build_dossier(symbol, bars_by_tf, fut_bars_by_tf=None, as_of=None, cfg=None):
    """Facts dossier at `as_of` (default: close of the last 15M bar).

    bars_by_tf: spot bars {"15M": required, "5M": LTF CHoCH, "1m": context / gaps, "1H": optional (else complete hours from 15M),
    "D": optional daily (gap ATR / trend)}; each a DataFrame with timestamp (bar start, IST) + open / high / low / close [+ bar_end].
    fut_bars_by_tf: {"5M": near-month FUT 5M bars with timestamp + volume [+ expiry / contract]} — FUT volume (K10).
    Returns {"schema", "symbol", "as_of", "inputs", "sections": {name: {"status": OK | NA, "owner", ...facts | "reason"}}}.
    Every input frame (spot all TFs + FUT) is checked against the sealed holdout for `symbol` first (HoldoutError, never NA)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    if cfg["display_finder"] not in DISPLAY_FINDERS:                       # a typo never silently picks a finder
        raise ValueError(f"build_dossier: display_finder {cfg['display_finder']!r} — allowed: {', '.join(DISPLAY_FINDERS)}")
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
    sections = {name: _run(OWNER_NAMES[name], lambda fn=OWNERS[name]: fn(c)) for name in sections_of(c.trigger_tf())}
    return {"schema": SCHEMA, "symbol": symbol, "as_of": str(as_of),
            "asof_bar": {"tf": "15M", "ts": str(m15["timestamp"].iloc[-1]), "close": round(float(m15["close"].iloc[-1]), 2),
                         **c.stale_facts()},
            "inputs": {**{tf: _frame_info(frames[tf]) for tf in ("15M", "1H", "5M", "1m", "D")}, "FUT_5M": _frame_info(fut5)},
            "sections": sections}
