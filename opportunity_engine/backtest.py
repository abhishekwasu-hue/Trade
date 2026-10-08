"""opportunity_engine/backtest.py — bar-by-bar backtest (live आणि backtest साठी एकच निर्णय-साखळी: `engine.evaluate`) + analytics + तिन्ही variants ची तुलना (spec §12, plan v2 §8).

🎓 रचना:
  1. `prepare_timeline()` — *एकदाच* सर्व TF चे trackers (1d/4h/1h/15m) incremental चालवून: (अ) 1d/4h/1h चे state snapshots (प्रत्येक HTF bar_end ला), (आ) प्रत्येक दिवसाच्या 09:15 ला (D−1 पर्यंतच्या डेटावरून)
     levels (supply/demand/S-R/KEY/GAP + Level Quality) आणि DayInfo (PDC/PDH/PDL/ADR). HTF bar फक्त `bar_end ≤ t` झाल्यावरच दिसतो (no-lookahead).
  2. `run_variant()` — प्रत्येक 5M closed bar वर: उघड्या position चं exit-management (`risk.on_bar`: SL आधी, T1→BE, trail, time stop, failed-breakout, EOD) → detectors (D1–D3) →
     `engine.evaluate` (gate → risk → validation → score → selector) → TAKEN ⇒ position (entry = trigger bar चा close). Gate ने नाकारलेले candidates `size=0` virtual position म्हणून simulate (counterfactual).
  3. Variants (plan §8): V1 = 4H bias + Daily veto (डीफॉल्ट) · V2 = Daily primary · V3 = 4H bias, veto नाही. Journal/levels एकदाच; gate/selector प्रति variant.
  4. Analytics: breakdowns (setup/bias/Daily state/score/वेळ/वर्ष), IS (2015-01→2021-12) / OOS (2022-01→2024-03), verdict (OOS ≥ 30 trades ∧ expectancy > 0 ⇒ KEEP, नाहीतर REVIEW —
     फक्त अहवाल, setup आपोआप disable नाही), aligned vs counter-trend, variants तुलना.
निकाल जसे आले तसे; चांगले दिसावेत म्हणून ट्यूनिंग नाही. Index डेटात volume नाही ⇒ validation मध्ये volume N/A. R-आधारित (spot points); option P&L नाही.
"""
import bisect
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import cas as CAS
from .bias import resolve_bias
from .config import EngineConfig
from .context import Context, IncrementalTFState, TFState
from .detectors.gap import DayInfo, GapFade, GapGo, GapRetestReversal, classify_gap
from .detectors.range_box import FailedBreakoutTrap
from .detectors.box_triangle import RangeBoxBreakout, TriangleBreakout
from .detectors.chart_pattern import ChartPatternBreakout
from .detectors.trendline import TrendlineBreakRetest, TrendlineThirdTouch
from .detectors.zone_pullback import ZonePullback
from .engine import _rr_of, _validate, evaluate
from .journal import Journal
from .measures import adr as measure_adr
from .measures import ref_range_from_ranges
from .risk import _close_all, on_bar, open_position, plan_trade
from .selector import DayState, day_block_reason
from .visual_audit import consensus as CONS
from .zones import build_levels

HTF = ("1d", "4h", "1h")
VARIANTS = {
    "V1": {"primary_htf": "4h", "daily_veto": True},
    "V2": {"primary_htf": "1d", "daily_veto": False},
    "V3": {"primary_htf": "4h", "daily_veto": False},
}
VARIANT_TEXT = {"V1": "4H bias + Daily veto (डीफॉल्ट)", "V2": "Daily primary (veto लागू नाही)", "V3": "4H bias, veto नाही"}
DETECTORS = {"D1": GapGo, "D2": GapFade, "D3": GapRetestReversal, "D4": TrendlineThirdTouch, "D5": TrendlineBreakRetest, "D6": ZonePullback,
             "D7": RangeBoxBreakout, "D8": TriangleBreakout, "D9": ChartPatternBreakout, "D10": FailedBreakoutTrap}
SHIFT_EVENTS = ("CHOCH", "RECOVERY", "REVERSAL_CONFIRMED", "RANGE_EXIT_UP", "RANGE_EXIT_DOWN")     # 15M structure-shift events (D6 trigger)
IS_END = pd.Timestamp("2021-12-31")
OOS_START = pd.Timestamp("2022-01-01")
PERIODS = ("IS 2015→2021", "OOS 2022→")


@dataclass
class BacktestConfig:
    symbol: str = "NIFTY"
    start: Any = None                       # trading सुरू (warm-up आधीपासूनच; None => सर्व)
    end: Any = None
    detectors: tuple = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10")
    variants: tuple = ("V1", "V2", "V3")
    engine: EngineConfig = field(default_factory=EngineConfig)
    levels_every_day: bool = True
    visual_records: Any = None               # {pd.Timestamp(date): [visual audit records]} — Dual-Eye consensus (engine.consensus_mode off नसेल तेव्हाच वापर)


@dataclass
class DayPack:
    date: Any
    open_t: Any
    df5: pd.DataFrame
    df15: pd.DataFrame
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    be: list
    g5: int                                  # global index (f5) of the day's first bar
    g15: int
    levels: List[dict]
    info: DayInfo
    adr: float
    ev15: list = field(default_factory=list)  # आजचे 15M structure-shift events (time = 15M bar_end; त्या वेळेपासूनच दिसतात)
    pool: list = field(default_factory=list)  # नाकारलेले (LOW_SCORE) zones — visual audit चा "missing" पट्टा snap करण्यासाठी (detectors ना दिसत नाहीत)


@dataclass
class Timeline:
    days: List[DayPack]
    times: Dict[str, list]
    states: Dict[str, list]
    r5: np.ndarray
    full5: np.ndarray
    r15: np.ndarray
    full15: np.ndarray
    cfg: Any = None
    v5: Any = None                               # 5M volume (index डेटात 0 ⇒ N/A; futures volume जोडल्यास खरा)
    journal: Any = None                          # पूर्ण चाललेला journal (visual backfill: swings `confirmed_time` नुसार as-of फिल्टर करून)
    htf: Dict[str, Any] = field(default_factory=dict)   # {"1h"/"4h"/"1d": (closed frame, bar_end ns array)} — D4/D5/D9 साठी as-of इतिहास

    def hist(self, tf, t, n):
        """`t` पर्यंत *बंद* झालेले `tf` चे शेवटचे n bars (bar_end ≤ t) — no-lookahead. tf नसेल तर None."""
        if tf not in self.htf:
            return None
        f, be = self.htf[tf]
        i = int(np.searchsorted(be, np.datetime64(pd.Timestamp(t)), side="right"))
        return f.iloc[max(0, i - n):i]

    def htf_state(self, tf, t):
        i = bisect.bisect_right(self.times[tf], t) - 1
        return self.states[tf][i] if i >= 0 else TFState(tf=tf, state="INIT")

    def context(self, t, day, price):
        return Context(time=t, price=price, states={tf: self.htf_state(tf, t) for tf in HTF}, levels=day.levels, adr=day.adr)

    def volume(self, g, n=20, min_bars=10):
        """5M bar g चा volume आणि त्याआधीच्या n bars चा median (फक्त >0 values; कमी असतील तर None ⇒ validation मध्ये N/A)."""
        if self.v5 is None or g >= len(self.v5):
            return None, None
        v = float(self.v5[g])
        prev = self.v5[max(0, g - n):g]
        prev = prev[prev > 0]
        med = float(np.median(prev)) if len(prev) >= min_bars else None
        return (v if v > 0 else None), med

    def rr(self, which, g):
        r, full = (self.r5, self.full5) if which == 5 else (self.r15, self.full15)
        lo = max(g - 60, 0)
        arr = r[lo:g + 1][full[lo:g + 1]]
        return ref_range_from_ranges(arr, 20, 10)


# ---------------------------------------------------------------------------------------------------------------------
# १. Timeline (एकदाच)
# ---------------------------------------------------------------------------------------------------------------------
def _closed(df):
    return df[df["bar_closed"]].reset_index(drop=True) if "bar_closed" in df.columns else df.reset_index(drop=True)


def prepare_timeline(frames, bcfg=None, progress=None):
    """frames ({tf: engine frame}) -> Timeline. `progress(i, n, date)` ऐच्छिक callback."""
    bcfg = bcfg or BacktestConfig()
    cfg = bcfg.engine
    f5, f15, f1h, f4h, f1d = (_closed(frames[k]) for k in ("5m", "15m", "1h", "4h", "1d"))
    pdc_arr = CAS.pdc_col(f1d).to_numpy(float)                         # PDC = official close (CAS; 2026-08-03 पासून)
    journal = Journal(cfg, tfs=("1d", "4h", "1h", "15m"))
    arr = {}
    for tf, f in (("1d", f1d), ("4h", f4h), ("1h", f1h), ("15m", f15)):
        arr[tf] = {"be": f["bar_end"].tolist(), "o": f["open"].to_numpy(float), "h": f["high"].to_numpy(float), "l": f["low"].to_numpy(float),
                   "c": f["close"].to_numpy(float), "full": f["bar_is_full"].to_numpy(bool)}
    ptr = {tf: 0 for tf in arr}
    inc = {tf: IncrementalTFState(journal.trackers[tf]) for tf in HTF}
    times = {tf: [] for tf in HTF}
    states = {tf: [] for tf in HTF}

    def feed_until(t):
        for tf, a in arr.items():
            p, n = ptr[tf], len(a["be"])
            while p < n and a["be"][p] <= t:
                journal.on_bar_close(tf, a["be"][p], a["o"][p], a["h"][p], a["l"][p], a["c"][p], a["full"][p])
                if tf in inc:
                    times[tf].append(a["be"][p])
                    states[tf].append(inc[tf].state())
                p += 1
            ptr[tf] = p

    day_of_5 = f5["bar_start"].dt.normalize()
    day_of_15 = f15["bar_start"].dt.normalize()
    d1_be = f1d["bar_end"].to_numpy("datetime64[ns]")
    start = None if bcfg.start is None else pd.Timestamp(bcfg.start)
    end = None if bcfg.end is None else pd.Timestamp(bcfg.end)
    first_idx5 = f5.groupby(day_of_5).head(1).index
    day_slices = {d: g for d, g in f5.groupby(day_of_5)}
    day15 = {d: g for d, g in f15.groupby(day_of_15)}
    dates = sorted(day_slices)
    days: List[DayPack] = []
    for n, d in enumerate(dates):
        open_t = d + pd.Timedelta(hours=9, minutes=15)
        feed_until(open_t)
        if (start is not None and d < start) or (end is not None and d > end):
            continue
        g = day_slices[d]
        i_d = int(np.searchsorted(d1_be, np.datetime64(open_t), side="right")) - 1           # शेवटचा बंद Daily bar (D−1)
        if i_d < 3 or len(g) < 6:
            continue
        pdc, pdh, pdl = float(pdc_arr[i_d]), float(f1d["high"].iloc[i_d]), float(f1d["low"].iloc[i_d])            # PDC = official close (CAS)
        daily_adr = measure_adr(f1d.iloc[max(0, i_d - 40):i_d + 1], cfg.adr_days)
        levels, pool = [], []
        if len(journal.trackers["1d"].c) >= 30 and len(journal.trackers["4h"].c) >= 30 and bcfg.levels_every_day:
            g0 = int(g.index[0])
            fine = f5.iloc[max(0, g0 - 1500):g0]
            res = build_levels(journal, {"1d": f1d, "5m": fine}, bcfg.symbol, pdc, cfg, fine=fine, tfs=("15m", "1h", "4h", "1d"))
            levels = res["levels"] + [z for z in res["rejected"] if z.get("status") == "BROKEN"]
            pool = [z for z in res["rejected"] if z.get("status") != "BROKEN" and z.get("kind") in ("DEMAND", "SUPPLY", "SUPPORT", "RESISTANCE")]
        info = DayInfo(date=d, open=float(g["open"].iloc[0]), pdc=pdc, pdh=pdh, pdl=pdl, close_3d_ago=float(pdc_arr[i_d - 3]), adr=daily_adr)
        g15 = day15.get(d, f15.iloc[0:0])
        days.append(DayPack(date=d, open_t=open_t, df5=g.reset_index(drop=True), df15=g15.reset_index(drop=True), o=g["open"].to_numpy(float), h=g["high"].to_numpy(float),
                            l=g["low"].to_numpy(float), c=g["close"].to_numpy(float), be=g["bar_end"].tolist(), g5=int(g.index[0]),
                            g15=int(g15.index[0]) if len(g15) else 0, levels=levels, info=info, adr=daily_adr, pool=pool))
        if progress and n % 50 == 0:
            progress(n, len(dates), d)
    feed_until(pd.Timestamp.max)
    by_day = {}
    for e in journal.trackers["15m"].events:                  # event time = 15M bar_end (तो bar बंद झाल्यावरच) — no-lookahead
        if e["type"] in SHIFT_EVENTS:
            by_day.setdefault(pd.Timestamp(e["time"]).normalize(), []).append(
                {"time": e["time"], "type": e["type"], "to_state": e.get("to_state"), "price": e.get("price")})
    for dp in days:
        dp.ev15 = by_day.get(dp.date, [])
    vol = f5["volume"].fillna(0.0).to_numpy(float) if "volume" in f5.columns else None
    return Timeline(days=days, times=times, states=states, r5=(f5["high"] - f5["low"]).to_numpy(float), full5=f5["bar_is_full"].to_numpy(bool),
                    r15=(f15["high"] - f15["low"]).to_numpy(float), full15=f15["bar_is_full"].to_numpy(bool), cfg=bcfg, v5=vol, journal=journal,
                    htf={tf: (f, f["bar_end"].to_numpy("datetime64[ns]")) for tf, f in (("1h", f1h), ("4h", f4h), ("1d", f1d))})


# ---------------------------------------------------------------------------------------------------------------------
# २. Variant replay
# ---------------------------------------------------------------------------------------------------------------------
class _Open:
    """उघडी (real किंवा virtual) position + तिची नोंद."""

    def __init__(self, pos, cand, decision, k, virtual, meta):
        self.pos, self.cand, self.decision, self.k, self.virtual, self.meta = pos, cand, decision, k, virtual, meta


def _trail_stop(day, k, entry_k, direction):
    """नवीन confirmed 5M swing (2 bars दोन्ही बाजूला) HL/LH — entry नंतर तयार झालेला. रिटर्न stop किंवा None."""
    j = k - 2
    if j <= entry_k or j < 2:
        return None
    if direction == "LONG":
        v = day.l[j]
        return float(v) if v < min(day.l[j - 2], day.l[j - 1], day.l[j + 1], day.l[j + 2]) else None
    v = day.h[j]
    return float(v) if v > max(day.h[j - 2], day.h[j - 1], day.h[j + 1], day.h[j + 2]) else None


def _states_text(ctx):
    return {f"state_{tf}": ctx.state_name(tf) for tf in HTF}


DETAIL_KEYS = ("zone_type", "zone_tf", "trigger_type", "level_type", "pattern")


def _detail(meta):
    """detector चा तपशील (D6 zone/trigger प्रकार, D10 level प्रकार …) — analysis साठी एका column मध्ये."""
    return " | ".join(f"{k}={meta[k]}" for k in DETAIL_KEYS if meta.get(k) is not None)


def _decision_row(variant, day, d, ctx):
    c = d.candidate
    row = {"variant": variant, "date": day.date, "time": c.time, "setup": c.setup_id, "direction": c.direction, "kind": c.kind, "entry": c.entry, "sl_ref": c.sl_ref,
           "status": d.status, "reasons": " | ".join(d.reasons), "bias": d.bias.label, "gate_codes": ",".join(d.gate.codes) if d.gate else "",
           "score": None if d.score is None else d.score.total, "validation": None if d.validation is None else d.validation.score,
           "size_factor": d.size_factor, "gap_type": c.meta.get("gap_type", ""), "setup_detail": _detail(c.meta), "setup_quality": c.setup_quality,
           "commentary": d.commentary}
    row.update(_states_text(ctx))
    if d.score is not None:
        row.update({f"score_{k}": v for k, v in d.score.components.items()})
    return row


def _trade_row(variant, day, o, closed_time):
    p, c, d = o.pos, o.cand, o.decision
    plan = p.plan
    row = {"variant": variant, "date": day.date, "entry_time": c.time, "exit_time": closed_time, "setup": c.setup_id, "direction": c.direction, "kind": c.kind,
           "entry": plan.entry, "sl": plan.sl, "t1": plan.t1, "t2": plan.t2, "risk": plan.risk, "exit_reason": p.exit_reason, "pnl_pts": p.pnl_pts, "r": p.r_multiple,
           "t1_hit": p.t1_done, "bars": p.bars, "mfe_r": p.mfe_r, "level": p.level, "virtual": o.virtual, "gate_rejected": o.virtual, "gate_codes": o.meta.get("gate_codes", ""),
           "size_factor": 0.0 if o.virtual else d.size_factor, "score": o.meta.get("score"), "bias": o.meta.get("bias"), "gap_type": c.meta.get("gap_type", ""), "setup_detail": _detail(c.meta),
           "state_1d": o.meta.get("state_1d"), "state_4h": o.meta.get("state_4h"), "state_1h": o.meta.get("state_1h"), "commentary": o.meta.get("commentary", ""),
           "zone_id": (c.zone or {}).get("level_id"), "zone_consensus": (c.zone or {}).get("consensus")}
    row["r_weighted"] = row["r"] * row["size_factor"]
    return row


def make_detectors(names, ecfg):
    """detector नावं ("D1", "D6" …) -> instances (registry `DETECTORS`)."""
    return [DETECTORS[n](ecfg) for n in names if n in DETECTORS]


def run_variant(tl, variant, bcfg=None, progress=None, detector_factory=None):
    """एक variant चं पूर्ण replay. रिटर्न dict: trades, virtual (gate-rejected counterfactual), decisions (DataFrames)."""
    bcfg = bcfg or tl.cfg or BacktestConfig()
    ecfg = replace(bcfg.engine, **VARIANTS[variant])
    if detector_factory is not None:                       # चाचणी/विस्तारासाठी: factory(ecfg) -> [Detector...]
        dets = list(detector_factory(ecfg))
    else:
        dets = make_detectors(bcfg.detectors, ecfg)
    trades, virtual_rows, decisions, cons_rows = [], [], [], []
    vis = bcfg.visual_records if ecfg.consensus_mode != "off" else None
    for di, day in enumerate(tl.days):
        if vis is not None:                                  # Dual-Eye consensus: दिवस D चे records फक्त D−1 पर्यंतच्या chart वरून
            lv, cinfo = CONS.apply(day.levels, day.pool, vis.get(pd.Timestamp(day.date).normalize(), []), ecfg.consensus_mode)
            cons_rows.append({"date": day.date, "mode_used": cinfo.get("mode_used", ecfg.consensus_mode), "fallback": cinfo["fallback"],
                              "levels_before": len(day.levels), "levels_after": len(lv), **{f"n_{k}": v for k, v in cinfo.get("counts", {}).items()}})
            day = replace(day, levels=lv)
        info = replace(day.info)
        ctx0 = tl.context(day.open_t, day, info.open)
        bias0 = resolve_bias(ctx0, ecfg)
        classify_gap(info, ctx0, bias0, ecfg)
        dstate, detmem = DayState(), {}
        real: Optional[_Open] = None
        virt: List[_Open] = []
        virt_seen = set()                                    # counterfactual: दिवसात (setup, दिशा) ची फक्त पहिली gate-rejected signal (एकसारख्या सलग bars च्या signals ने आकडे फुगू नयेत)
        n = len(day.be)
        for k in range(n):
            t = day.be[k]
            bar = {"open": day.o[k], "high": day.h[k], "low": day.l[k], "close": day.c[k]}
            last_bar = k == n - 1
            # --- उघड्या positions चं management ---
            if real is not None:
                p = real.pos
                trail = _trail_stop(day, k, real.k, real.cand.direction) if p.t1_done else None
                on_bar(p, bar, ecfg, time=t, trail_stop=trail)
                if not p.closed:
                    ps = tl.htf_state(ecfg.primary_htf, t).state
                    weak = (ps == "UPTREND_WEAK" and real.cand.direction == "LONG") or (ps == "DOWNTREND_WEAK" and real.cand.direction == "SHORT")
                    if weak:
                        dstate.htf_weak = True
                        if ecfg.weak_exit == "exit":
                                    _close_all(p, bar["close"], "HTF_WEAK", t)
                        elif (p.sl < p.plan.entry) if real.cand.direction == "LONG" else (p.sl > p.plan.entry):
                            p.sl = p.plan.entry
                if not p.closed and last_bar:
                    _close_all(p, bar["close"], "EOD_DATA", t)
                if p.closed:
                    trades.append(_trade_row(variant, day, real, t))
                    dstate.open_positions = 0
                    if p.exit_reason == "SL":
                        dstate.sl_today += 1
                        dstate.last_sl_time = t
                    real = None
            for vo in list(virt):
                on_bar(vo.pos, bar, ecfg, time=t)
                if not vo.pos.closed and last_bar:
                    _close_all(vo.pos, bar["close"], "EOD_DATA", t)
                if vo.pos.closed:
                    virtual_rows.append(_trade_row(variant, day, vo, t))
                    virt.remove(vo)
            # --- detection ---
            if k < ecfg.or_bars or not dets:
                continue
            price = day.c[k]
            ctx = tl.context(t, day, price)
            vol, vol_med = tl.volume(day.g5 + k)
            bars = {"5m": day.df5.iloc[:k + 1], "15m": day.df15[day.df15["bar_end"] <= t], "info": info, "state": detmem,
                    "rr5": tl.rr(5, day.g5 + k), "rr15": None, "ev15": [e for e in day.ev15 if e["time"] <= t], "vol5": vol, "vol_med5": vol_med,
                    "hist": (lambda tf, n, _t=t: tl.hist(tf, _t, n))}
            if len(bars["15m"]):
                bars["rr15"] = tl.rr(15, day.g15 + len(bars["15m"]) - 1)
            cands = []
            bias_now = resolve_bias(ctx, ecfg)
            for det in dets:
                cands += det.detect(ctx, bars, bias_now, t)
            if not cands:
                continue
            res = evaluate(cands, ctx, ecfg, now=t, day=dstate, symbol=bcfg.symbol)
            for d in res.decisions:
                decisions.append(_decision_row(variant, day, d, ctx))
                meta = {"gate_codes": ",".join(d.gate.codes) if d.gate else "", "score": None if d.score is None else d.score.total, "bias": d.bias.label,
                        "commentary": d.commentary, **{k2: v for k2, v in _states_text(ctx).items()}}
                meta = {**meta, "state_1d": ctx.state_name("1d"), "state_4h": ctx.state_name("4h"), "state_1h": ctx.state_name("1h")}
                if d.status == "TAKEN" and real is None:
                    real = _Open(open_position(d.plan, d.candidate.kind, d.candidate.trigger.get("level"), d.candidate.setup_id), d.candidate, d, k, False, meta)
                    dstate.trades_today += 1
                    dstate.open_positions = 1
                elif d.status == "REJECTED_GATE" and (d.candidate.setup_id, d.candidate.direction) not in virt_seen:
                    plan = plan_trade(d.candidate, ctx, ecfg, _rr_of(d.candidate), adr=ctx.adr, symbol=bcfg.symbol)
                    if plan.ok:
                        val = _validate(d.candidate, plan.rr_to_opposing, ecfg)
                        if val.passed:
                            virt_seen.add((d.candidate.setup_id, d.candidate.direction))
                            virt.append(_Open(open_position(plan, d.candidate.kind, d.candidate.trigger.get("level"), d.candidate.setup_id), d.candidate, d, k, True, meta))
        if progress and di % 100 == 0:
            progress(di, len(tl.days), day.date)
    out = {"trades": pd.DataFrame(trades), "virtual": pd.DataFrame(virtual_rows), "decisions": pd.DataFrame(decisions)}
    if vis is not None:
        out["consensus"] = pd.DataFrame(cons_rows)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# ३. Analytics
# ---------------------------------------------------------------------------------------------------------------------
def summarize(trades, col="r_weighted"):
    """trades DataFrame -> metrics dict. `col`: r (साइज-विना) किंवा r_weighted (साइज सह). रिकामं => शून्य/None."""
    empty = {"trades": 0, "win_pct": None, "expectancy_r": None, "avg_win_r": None, "avg_loss_r": None, "profit_factor": None, "total_r": 0.0, "max_dd_r": 0.0}
    if trades is None or len(trades) == 0:
        return empty
    t = trades.sort_values("exit_time") if "exit_time" in trades.columns else trades
    r = t[col].astype(float)
    wins, losses = r[r > 0], r[r < 0]
    eq = r.cumsum()
    dd = (eq.cummax() - eq).max()
    return {"trades": int(len(t)), "win_pct": round(float((r > 0).mean() * 100), 1), "expectancy_r": round(float(r.mean()), 3),
            "avg_win_r": None if wins.empty else round(float(wins.mean()), 3), "avg_loss_r": None if losses.empty else round(float(losses.mean()), 3),
            "profit_factor": None if losses.empty else round(float(wins.sum() / abs(losses.sum())), 2), "total_r": round(float(r.sum()), 2), "max_dd_r": round(float(dd), 2)}


def split_is_oos(trades):
    d = pd.to_datetime(trades["date"]) if len(trades) else pd.Series([], dtype="datetime64[ns]")
    return trades[d <= IS_END], trades[d >= OOS_START]


def breakdown(trades, by, col="r_weighted"):
    """by: column नाव / "year" / "tod" (वेळ-बकेट) / "score_bucket". रिटर्न DataFrame (प्रत्येक गटाचे metrics)."""
    if trades is None or len(trades) == 0:
        return pd.DataFrame()
    t = trades.copy()
    bys = [by] if isinstance(by, str) else list(by)                 # एक किंवा अनेक (उदा. ["setup", "tod"])
    if "year" in bys:
        t["year"] = pd.to_datetime(t["date"]).dt.year
    if "tod" in bys:
        t["tod"] = pd.to_datetime(t["entry_time"]).dt.strftime("%H:") + np.where(pd.to_datetime(t["entry_time"]).dt.minute < 30, "00", "30")
    if "score_bucket" in bys:
        t["score_bucket"] = pd.cut(t["score"].astype(float), [0, 60, 75, 101], labels=["<60", "60-74", "75+"], right=False).astype(str)
    rows = []
    for key, g in t.groupby(bys if len(bys) > 1 else bys[0], dropna=False):
        keys = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(bys, keys)), **summarize(g, col)})
    return pd.DataFrame(rows)


def breakdown_split(trades, by, col="r_weighted"):
    """`breakdown` पण IS आणि OOS वेगळे (पहिला column `period`) — एकत्रित (IS+OOS) तक्त्यावरून tuning म्हणजे OOS leakage, म्हणून breakdowns नेहमी वेगळे."""
    if trades is None or len(trades) == 0:
        return pd.DataFrame()
    parts = []
    for label, part in zip(PERIODS, split_is_oos(trades)):
        b = breakdown(part, by, col)
        if len(b):
            parts.append(b.assign(period=label)[["period"] + list(b.columns)])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def verdicts(trades, min_oos=30):
    """setup-निहाय: OOS मध्ये ≥ 30 trades ∧ expectancy > 0 ⇒ KEEP, नाहीतर REVIEW (फक्त अहवाल)."""
    rows = []
    if trades is None or len(trades) == 0:
        return pd.DataFrame(columns=["setup", "is_trades", "is_expectancy_r", "oos_trades", "oos_expectancy_r", "verdict"])
    for setup, g in trades.groupby("setup"):
        is_t, oos_t = split_is_oos(g)
        si, so = summarize(is_t), summarize(oos_t)
        ok = so["trades"] >= min_oos and (so["expectancy_r"] or 0) > 0
        rows.append({"setup": setup, "is_trades": si["trades"], "is_expectancy_r": si["expectancy_r"], "oos_trades": so["trades"], "oos_expectancy_r": so["expectancy_r"],
                     "verdict": "KEEP" if ok else "REVIEW"})
    return pd.DataFrame(rows)


def aligned_vs_counter(trades, virtual):
    """aligned (घेतलेले) vs gate ने नाकारलेले counter-trend (HTF_MISALIGNED) vs इतर gate-rejects — size=0 virtual simulation. R साइज-विना (तुलनेसाठी)."""
    rows = [{"गट": "aligned (घेतलेले)", **summarize(trades, "r")}]
    if virtual is not None and len(virtual):
        mis = virtual[virtual["gate_codes"].str.contains("HTF_MISALIGNED", na=False)]
        oth = virtual[~virtual["gate_codes"].str.contains("HTF_MISALIGNED", na=False)]
        rows.append({"गट": "counter-trend (HTF_MISALIGNED, नाकारलेले)", **summarize(mis, "r")})
        rows.append({"गट": "इतर gate-rejected (veto/room/protected…)", **summarize(oth, "r")})
    return pd.DataFrame(rows)


def aligned_vs_counter_split(trades, virtual):
    """aligned_vs_counter, IS आणि OOS वेगळे."""
    parts = []
    for label, (t, v) in zip(PERIODS, zip(*(split_is_oos(x) if x is not None and len(x) else (x, x) for x in (trades, virtual)))):
        parts.append(aligned_vs_counter(t, v).assign(period=label))
    out = pd.concat(parts, ignore_index=True)
    return out[["period"] + [c for c in out.columns if c != "period"]]


def compare_variants(results):
    """प्रत्येक variant: metrics + (त्याने नाकारलेले पण दुसऱ्याने घेतलेले) trades चा expectancy. results = {variant: run_variant dict}."""
    rows = []
    keys = {v: set(zip(r["trades"]["date"], r["trades"]["entry_time"], r["trades"]["setup"], r["trades"]["direction"])) if len(r["trades"]) else set() for v, r in results.items()}
    for v, r in results.items():
        tr = r["trades"]
        m = summarize(tr)
        m_is, m_oos = summarize(split_is_oos(tr)[0]), summarize(split_is_oos(tr)[1])
        others = {}
        for w, rw in results.items():
            if w == v or not len(rw["trades"]):
                continue
            k = list(zip(rw["trades"]["date"], rw["trades"]["entry_time"], rw["trades"]["setup"], rw["trades"]["direction"]))
            only = rw["trades"][[kk not in keys[v] for kk in k]]
            others[w] = summarize(only)
        rows.append({"variant": v, "वर्णन": VARIANT_TEXT.get(v, ""), **m, "IS_trades": m_is["trades"], "IS_expectancy_r": m_is["expectancy_r"],
                     "OOS_trades": m_oos["trades"], "OOS_expectancy_r": m_oos["expectancy_r"],
                     "इतर variants ने घेतलेले (हिने नाही) trades": sum(o["trades"] for o in others.values()),
                     "त्यांचा expectancy_r": None if not others or sum(o["trades"] for o in others.values()) == 0 else
                     round(sum((o["expectancy_r"] or 0) * o["trades"] for o in others.values()) / sum(o["trades"] for o in others.values()), 3)})
    return pd.DataFrame(rows)


def _period_rows(trades, extra=None, col="r"):
    rows = []
    for label, part in zip(PERIODS, split_is_oos(trades) if trades is not None and len(trades) else (trades, trades)):
        m = summarize(part, col)
        mw = summarize(part, "r_weighted")
        rows.append({**(extra or {}), "period": label, "trades": m["trades"], "win_pct": m["win_pct"], "avg_win_r": m["avg_win_r"], "avg_loss_r": m["avg_loss_r"],
                     "expectancy_r": m["expectancy_r"], "expectancy_r_साइज_सह": mw["expectancy_r"], "total_r": m["total_r"]})
    return rows


def variants_is_oos(results):
    """§3.4 तक्ता: प्रत्येक variant — IS आणि OOS वेगळे (trades, win %, avg win/loss R, expectancy साइज-विना आणि साइज-सह)."""
    rows = []
    for v, r in results.items():
        rows += _period_rows(r["trades"], {"variant": v, "वर्णन": VARIANT_TEXT.get(v, "")})
    return pd.DataFrame(rows)


def variants_yearwise(results, col="r"):
    """वर्षनिहाय expectancy (trades) — प्रत्येक variant एक column; period column सह (IS/OOS)."""
    years = {}
    for v, r in results.items():
        tr = r["trades"]
        if tr is None or not len(tr):
            continue
        for y, g in tr.groupby(pd.to_datetime(tr["date"]).dt.year):
            years.setdefault(int(y), {})[v] = f"{g[col].mean():+.3f} ({len(g)})"
    rows = [{"वर्ष": y, "period": PERIODS[0] if y <= IS_END.year else PERIODS[1], **{v: years[y].get(v, "—") for v in results}} for y in sorted(years)]
    return pd.DataFrame(rows)


def wait_pullback_table(result):
    """bias `*_WAIT_PULLBACK_END` असताना: setup-निहाय (IS/OOS वेगळे) candidates किती, कोणत्या टप्प्यावर थांबले, घेतलेल्यांचा निकाल,
    आणि gate ने नाकारलेल्यांचा virtual (size=0) निकाल. + `HTF_WAIT_PULLBACK` ने नाकारलेले breakouts (virtual). R साइज-विना."""
    dec, tr, vt = result["decisions"], result["trades"], result["virtual"]
    is_wait = lambda df: df["bias"].astype(str).str.endswith("WAIT_PULLBACK_END") if len(df) and "bias" in df.columns else pd.Series([], dtype=bool)   # noqa: E731
    rows = []
    if dec is None or not len(dec):
        return pd.DataFrame()
    d = dec[is_wait(dec)]
    t = tr[is_wait(tr)] if tr is not None and len(tr) else pd.DataFrame(columns=["date", "setup", "r"])
    v = vt[is_wait(vt)] if vt is not None and len(vt) else pd.DataFrame(columns=["date", "setup", "r", "gate_codes"])
    for label, (dp, tp, vp) in zip(PERIODS, zip(split_is_oos(d), split_is_oos(t) if len(t) else (t, t), split_is_oos(v) if len(v) else (v, v))):
        for setup in sorted(set(dp["setup"]) | set(tp.get("setup", []))):
            ds, ts, vs = dp[dp["setup"] == setup], tp[tp["setup"] == setup] if len(tp) else tp, vp[vp["setup"] == setup] if len(vp) else vp
            st = ds["status"].value_counts()
            mt, mv = summarize(ts, "r"), summarize(vs, "r")
            rows.append({"period": label, "setup": setup, "candidates": len(ds), "दिवस": ds["date"].nunique(),
                         "gate_reject": int(st.get("REJECTED_GATE", 0)), "risk_reject": int(st.get("REJECTED_RISK", 0)), "validation_reject": int(st.get("REJECTED_VALIDATION", 0)),
                         "score_reject": int(st.get("REJECTED_SCORE", 0)), "selector_reject": int(st.get("DROPPED", 0)), "taken": int(st.get("TAKEN", 0)),
                         "घेतलेले_trades": mt["trades"], "घेतलेले_win_pct": mt["win_pct"], "घेतलेले_expectancy_r": mt["expectancy_r"], "घेतलेले_total_r": mt["total_r"],
                         "नाकारलेले_virtual_trades": mv["trades"], "नाकारलेले_virtual_expectancy_r": mv["expectancy_r"]})
    return pd.DataFrame(rows)


def wait_pullback_breakouts(result):
    """`HTF_WAIT_PULLBACK` ने नाकारलेले breakouts (pullback-end ची वाट असताना) — virtual निकाल, IS/OOS वेगळे."""
    vt = result["virtual"]
    if vt is None or not len(vt):
        return pd.DataFrame()
    w = vt[vt["gate_codes"].astype(str).str.contains("HTF_WAIT_PULLBACK", na=False)]
    rows = []
    for setup in sorted(set(w["setup"])) or ["—"]:
        rows += _period_rows(w[w["setup"] == setup] if len(w) else w, {"setup": setup})
    return pd.DataFrame(rows)


@dataclass
class BacktestResult:
    results: Dict[str, dict]
    comparison: pd.DataFrame
    timeline: Any = None

    def tables(self, variant):
        r = self.results[variant]
        tr = r["trades"]
        out = {"summary": pd.DataFrame([{"scope": "सर्व", **summarize(tr)}, {"scope": "IS 2015→2021", **summarize(split_is_oos(tr)[0])},
                                        {"scope": "OOS 2022→", **summarize(split_is_oos(tr)[1])}]),
               "verdicts": verdicts(tr), "aligned_vs_counter": aligned_vs_counter_split(tr, r["virtual"])}
        for by in ("setup", "bias", "state_1d", "score_bucket", "tod", "year", "gap_type", "exit_reason"):
            out[f"by_{by}"] = breakdown_split(tr, by)                     # IS आणि OOS वेगळे
        out["by_setup_tod"] = breakdown_split(tr, ["setup", "tod"], col="r")        # setup × 30-मिनिट वेळ (R साइज-विना)
        out["wait_pullback"] = wait_pullback_table(r)
        out["wait_pullback_breakouts"] = wait_pullback_breakouts(r)
        return out

    def variant_tables(self):
        """§3.4 तुलना: variants IS/OOS वेगळे + वर्षनिहाय expectancy."""
        return {"variants_is_oos": variants_is_oos(self.results), "variants_yearwise": variants_yearwise(self.results)}


def run_backtest(frames, bcfg=None, progress=None, timeline=None):
    """frames -> BacktestResult (तिन्ही variants). `timeline` दिलं तर prepare वगळून पुन्हा वापरतो."""
    bcfg = bcfg or BacktestConfig()
    tl = timeline or prepare_timeline(frames, bcfg, progress)
    results = {v: run_variant(tl, v, bcfg, progress) for v in bcfg.variants}
    return BacktestResult(results=results, comparison=compare_variants(results), timeline=tl)
