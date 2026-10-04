"""opportunity_engine/detectors/gap.py — D1 GAP_GO, D2 GAP_FADE, D3 GAP_RETEST_REVERSAL (spec §4). कुठलाही indicator नाही.

🎓 Detector interface (PR-1c): `detect(ctx, bars_by_tf, bias, now) -> list[Candidate]` — spec चा `journal` पॅरामीटर इथे `Context` (journal चा HTF snapshot + levels) आहे.
`bars_by_tf` = {"5m": आजच्या बंद 5M bars (DataFrame), "15m": आजचे बंद 15M bars, "info": DayInfo, "state": आजच्या (variant-निहाय) detector memory dict, "rr5"/"rr15": ref_range scalars}.
Gap classification (९:१५ open vs PDC) क्रम: SMALL → EXHAUSTION → BREAKAWAY → RUNAWAY → COMMON. Candle patterns: established `signals.detect_candlestick_pattern` (फक्त किंमत; indicator नाही).
"""
from dataclasses import dataclass
from typing import Any, List, Optional

import numpy as np
import pandas as pd

from signals import detect_candlestick_pattern

from ..bias import _opposing, _strong
from ..context import trend_sign
from .base import Candidate, Detector, KIND_BREAKOUT, KIND_REVERSAL

HTF_TFS = ("1h", "4h", "1d")
SMALL, EXHAUSTION, BREAKAWAY, RUNAWAY, COMMON = "SMALL", "EXHAUSTION", "BREAKAWAY", "RUNAWAY", "COMMON"


@dataclass
class DayInfo:
    date: Any
    open: float
    pdc: float
    pdh: float
    pdl: float
    close_3d_ago: Optional[float] = None
    adr: float = float("nan")
    gap_pct: float = 0.0
    gap_dir: int = 0
    gap_type: str = COMMON


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _minutes(ts):
    t = pd.Timestamp(ts)
    return t.hour * 60 + t.minute


def classify_gap(info, ctx, bias, cfg):
    """DayInfo + HTF ctx + bias -> gap प्रकार (spec क्रम). रिटर्न: (प्रकार, तपशील dict). info मध्ये gap_pct/gap_dir भरतो."""
    gap_pct = (info.open - info.pdc) / info.pdc * 100.0 if info.pdc else 0.0
    d = 1 if gap_pct > 0 else -1 if gap_pct < 0 else 0
    info.gap_pct, info.gap_dir = gap_pct, d
    detail = {"gap_pct": round(gap_pct, 3)}
    if abs(gap_pct) < cfg.gap_small_pct or d == 0:
        info.gap_type = SMALL
        return SMALL, detail
    tol = info.open * cfg.gap_exhaustion_zone_pct / 100.0
    for lv in ctx.levels:
        if lv.get("tf") not in HTF_TFS or lv.get("reject_reason") or lv.get("status") == "BROKEN" or not _strong(lv):
            continue
        if _opposing(lv, d) and lv["low"] - tol <= info.open <= lv["high"] + tol:
            detail["exhaustion"] = f"open {lv['tf']} {lv['kind']} zone मध्ये"
            info.gap_type = EXHAUSTION
            return EXHAUSTION, detail
    if info.close_3d_ago is not None and np.isfinite(info.adr) and info.adr > 0 and d * (info.pdc - info.close_3d_ago) >= cfg.gap_exhaustion_adr * info.adr:
        detail["exhaustion"] = "आदल्या 3 दिवसांची एकाच दिशेची over-extension"
        info.gap_type = EXHAUSTION
        return EXHAUSTION, detail
    beyond = info.open > info.pdh if d > 0 else info.open < info.pdl
    if beyond and bias is not None and bias.direction == d:
        lo, hi = (info.pdc, info.open) if d > 0 else (info.open, info.pdc)
        crossed = any(lv.get("tf") in HTF_TFS and lv.get("quality_grade") in ("A", "B") and not lv.get("reject_reason") and lo <= lv["low"] and lv["high"] <= hi
                      for lv in ctx.levels)
        for tf in HTF_TFS:
            st = ctx.get(tf)
            lvl = None if st is None else (st.last_sh if d > 0 else st.last_sl)
            if lvl is not None and lo < lvl <= hi:
                crossed = True
        info.gap_type = BREAKAWAY if crossed else RUNAWAY
        detail["crossed_level"] = crossed
        return info.gap_type, detail
    info.gap_type = COMMON
    return COMMON, detail


def _age_sessions(formed_at, now):
    """gap चं वय (sessions, अंदाजे: सोम–शुक्र दिवस)."""
    try:
        return int(np.busday_count(pd.Timestamp(formed_at).date(), pd.Timestamp(now).date()))
    except (TypeError, ValueError):
        return 0


def _last_row(df5):
    return df5.iloc[-1]


def _trigger(row, prev, rr):
    return {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]),
            "prev_high": None if prev is None else float(prev["high"]), "prev_low": None if prev is None else float(prev["low"]), "ref_range": rr}


class GapGo(Detector):
    """D1: gap BREAKAWAY/RUNAWAY (bias-दिशेचा). Entry: OR (पहिले 15 मि) नंतर OR high/low पलीकडे 5M close (§5 validation पास). SL: OR mid (किंवा opposite)."""
    setup_id = "D1"
    default_kind = KIND_BREAKOUT

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        info, df5, cfg = bars_by_tf["info"], bars_by_tf["5m"], self.cfg
        if info.gap_type not in (BREAKAWAY, RUNAWAY) or len(df5) <= cfg.or_bars:
            return []
        if _minutes(now) > _hm(cfg.d1_window_end):
            return []
        or_df = df5.iloc[:cfg.or_bars]
        or_hi, or_lo = float(or_df["high"].max()), float(or_df["low"].min())
        row, prev = _last_row(df5), df5.iloc[-2]
        long = info.gap_dir > 0
        level = or_hi if long else or_lo
        if (row["close"] <= level) if long else (row["close"] >= level):
            return []
        mid = (or_hi + or_lo) / 2.0
        sl_ref = mid if cfg.d1_sl_mode == "mid" else (or_lo if long else or_hi)
        trig = {**_trigger(row, prev, bars_by_tf.get("rr5")), "level": level, "volume": None}
        quality = 80.0 if info.gap_type == BREAKAWAY else 65.0
        return [Candidate(setup_id="D1", direction="LONG" if long else "SHORT", time=now, entry=float(row["close"]), sl_ref=float(sl_ref), kind=KIND_BREAKOUT,
                          tf="15m", trigger_tf="5m", setup_quality=quality, trigger=trig,
                          notes=[f"Gap {info.gap_type} ({info.gap_pct:+.2f}%), OR {or_lo:,.0f}–{or_hi:,.0f} पलीकडे 5M close"], meta={"gap_type": info.gap_type})]


class GapFade(Detector):
    """D2: gap SMALL/EXHAUSTION/COMMON चा fade. Trigger: OR नंतर 5M reversal candle. SL: दिवसाच्या आत्तापर्यंतच्या extreme पलीकडे. Target: PDC (RR < 1.5 ⇒ वगळा). gap आधी भरला ⇒ रद्द."""
    setup_id = "D2"
    default_kind = KIND_REVERSAL

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        info, df5, cfg = bars_by_tf["info"], bars_by_tf["5m"], self.cfg
        if info.gap_type in (BREAKAWAY, RUNAWAY) or info.gap_dir == 0 or len(df5) <= cfg.or_bars:
            return []
        if _minutes(now) > _hm(cfg.d2_window_end):
            return []
        state = bars_by_tf["state"]
        if state.get("d2_cancelled"):
            return []
        up = info.gap_dir > 0
        # gap आधीच भरला असेल (PDC पर्यंत पोहोचला) तर setup रद्द
        filled = (df5["low"].min() <= info.pdc) if up else (df5["high"].max() >= info.pdc)
        if filled:
            state["d2_cancelled"] = True
            return []
        row, prev = _last_row(df5), df5.iloc[-2]
        patterns = cfg.d2_patterns_short if up else cfg.d2_patterns_long
        pat = detect_candlestick_pattern(df5.iloc[-3:])
        if pat not in patterns:
            return []
        extreme = float(df5["high"].max()) if up else float(df5["low"].min())
        entry = float(row["close"])
        risk = abs(entry - extreme)
        if risk <= 0 or abs(entry - info.pdc) / risk < cfg.d2_min_rr:
            return []                                                   # RR < 1.5 => हा trigger वगळा, पुढचा पाहा
        quality = 55.0 + (15.0 if info.gap_type == EXHAUSTION else 0.0) + (5.0 if "ENGULFING" in pat else 0.0) + min(abs(info.gap_pct) * 10.0, 10.0)
        trig = {**_trigger(row, prev, bars_by_tf.get("rr5"))}
        return [Candidate(setup_id="D2", direction="SHORT" if up else "LONG", time=now, entry=entry, sl_ref=extreme, kind=KIND_REVERSAL, tf="5m", trigger_tf="5m",
                          setup_quality=min(quality, 100.0), trigger=trig, targets_hint=[float(info.pdc)],
                          notes=[f"Gap {info.gap_type} ({info.gap_pct:+.2f}%) fade, {pat}, लक्ष्य PDC {info.pdc:,.0f}"], meta={"gap_type": info.gap_type, "pattern": pat})]


class GapRetestReversal(Detector):
    """D3: UNFILLED/PARTIAL gap zone चा retest + reversal. Up-gap किंमतीखाली = support (LONG), down-gap वर = resistance (SHORT)."""
    setup_id = "D3"
    default_kind = KIND_REVERSAL

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg, df5, df15, state = self.cfg, bars_by_tf["5m"], bars_by_tf["15m"], bars_by_tf["state"]
        mins = _minutes(now)
        if mins < _hm(cfg.d3_window_start) or mins > _hm(cfg.d3_window_end) or len(df5) < 3 or len(df15) < 1:
            return []
        rr15 = bars_by_tf.get("rr15")
        row, prev, trig_bar = df5.iloc[-1], df5.iloc[-2], df5.iloc[-2]
        out = []
        dead = state.setdefault("d3_dead", set())
        used = state.setdefault("d3_used", set())
        recent15 = df15.iloc[-2:]
        for lv in ctx.levels:
            if lv.get("kind") != "GAP" or lv.get("gap_status") not in ("UNFILLED", "PARTIAL"):
                continue
            lid = lv.get("level_id")
            if lid in dead or lid in used:
                continue
            up = lv.get("source") == "GAP_UP"
            lo, hi = lv["low"], lv["high"]
            far = lo if up else hi
            # invalidation: 15M close लांबच्या किनाऱ्यापलीकडे => gap FILLED (आजसाठी रद्द)
            last15 = df15.iloc[-1]
            if (last15["close"] < far) if up else (last15["close"] > far):
                dead.add(lid)
                continue
            price_ok = row["close"] >= hi * 0.999 if up else row["close"] <= lo * 1.001
            if not price_ok:
                continue
            touched = (recent15["low"].min() <= hi) if up else (recent15["high"].max() >= lo)               # जवळच्या किनाऱ्याला स्पर्श/शिरणं
            held = (recent15["close"].min() >= far) if up else (recent15["close"].max() <= far)              # लांबच्या किनाऱ्यापलीकडे close नाही
            if not (touched and held):
                continue
            pat = detect_candlestick_pattern(df5.iloc[-4:-1])                                                  # trigger bar = मागचा 5M bar
            wanted = cfg.d2_patterns_long if up else cfg.d2_patterns_short
            if pat not in wanted:
                continue
            broke = (row["close"] > trig_bar["high"]) if up else (row["close"] < trig_bar["low"])
            if not broke:
                continue
            used.add(lid)
            age = _age_sessions(lv.get("formed_at"), now)
            quality = 50.0 + max(0.0, 20.0 - age) + (10.0 if lv.get("mtf_count", 1) >= 2 else 0.0)
            st4 = ctx.get("4h")
            if st4 is not None and trend_sign(st4.state) == (1 if up else -1):
                quality += 10.0
            trig = {**_trigger(row, prev, bars_by_tf.get("rr5")), "prev_high": float(trig_bar["high"]), "prev_low": float(trig_bar["low"])}
            buf = cfg.d3_sl_buffer_k * rr15 if rr15 is not None and np.isfinite(rr15) else 0.0           # लांबच्या किनाऱ्यापलीकडे 0.1 × ref_range(15M)
            out.append(Candidate(setup_id="D3", direction="LONG" if up else "SHORT", time=now, entry=float(row["close"]), sl_ref=float(far - buf if up else far + buf), kind=KIND_REVERSAL,
                                 tf="15m", trigger_tf="5m", setup_quality=min(quality, 100.0), trigger=trig, zone=lv,
                                 notes=[f"{'Up' if up else 'Down'}-gap zone {lo:,.0f}–{hi:,.0f} retest + {pat}"], meta={"gap_overlap": True, "rr15": rr15}))
        return out
