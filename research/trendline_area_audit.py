#!/usr/bin/env python3
"""research/trendline_area_audit.py — READ-ONLY audit: the trendlines and S/R areas that the current chart code would draw at each
session close, checked against KB K6 (lines) and K4 (+ K5 magnet) (areas). No engine / chart code is changed; nothing here feeds a
decision. No broker / Upstox / paid API call. Dates only via CLI. NIFTY holdout rows are dropped (elliott.data_policy) and the
repo's own guards (pivots.engine.guard, mtf.adapter.guard_real) stay in force.

What is audited (the functions that draw, and the engine call that feeds each one):
  lines  trendlines2   mtf.charts.draw_lines / trendlines2.charts._draw  ← trendlines2.layer.run (L5[t]["lines"]); 15M and 1H
         d3_kline      decision3.setup_chart.m15_panel / decision3.charts.m15_png(debug)  ← decision3.trendline.k_line; 15M
         d3_swingline  feeds the "+TL" confluence area (decision3.engine.V22.tl_areas)  ← decision3.trendline.swing_line; 15M
         dash_tl       page_dashboard "Trendline Gate" (text only, not drawn)  ← signals.detect_trendline; 15M and 1H
  areas  d3_level      decision3.charts.h1_png (≤ 6 bands; telegram_view / v22_check)  ← decision3.levels.Levels.snapshot/active; 1H
         d3_tl_area    decision3 "+TL" confluence areas (step ②)  ← decision3.trendline.confluence_areas; 1H
         zones2        mtf.charts.draw_zones / zones2.charts.figure  ← zones2.engine.Zones.snap; 15M and 1H
         srv3          dashboard "SR Levels V3" view / page_sr_levels_v3  ← sr_levels_v3.compute_sr_v3 + select_display_levels; 15M, 1H
         vision_major  vision.chart._overlays (approval chart, single price)  ← vision.context.majors (price_action.major_levels); 15M

K6 line checks (MR = median(H − L) of the last 20 closed bars of the chart TF at t; KB "MR" definition):
  touches ≥ 3 (touch = k=2 fractal pivot extreme within ±0.2 MR; wick anchors count) · touches spaced ≥ 6 and ≥ 8 bars (both reported;
  KB says "6–8") · anchors on wicks (|line − wick extreme| ≤ 0.2 MR at both anchors) · no close beyond the line between the anchors by
  > 0.3 MR · |slope| ≤ 0.5 MR / bar · respected by recent price action: no real break after anchor 2 (K5: close beyond by 0.25 MR + next
  close beyond, or a displacement break bar ≥ 1.2 MR closing in its outer 30%) and ≥ 1 touch in the last 2 sessions (K6.4 a).
K4 area checks (no explicit SR V3 validity rules exist in docs/ — the SR V3 audit, docs/reports/leg_level_validation.md, only measures
bounce vs random): a zone, not a line (width > 0) and width ≤ 1.5 MR · origin = displacement (≥ 2 candles body ≥ 0.6 range and
range ≥ 1.5 MR, or 1 candle ≥ 2.5 MR) away from the area within 3 bars of a visit, with BOS (close beyond the last confirmed opposite
swing), or a flip (close ≥ 0.5 MR through, then a retest from the other side that closes back) · role on the right side of price at t
(support not > 0.25 MR above the close etc.) · not consumed (no acceptance — 2 closes beyond the far edge by 0.25 MR — after the last
origin) · not a magnet (K5: ≥ 4 close-crossings of the area mid in t's session, 15M closes).

  python3 research/trendline_area_audit.py --nifty-1m <csv/parquet ...> --banknifty-1m <...> --banknifty-15m <csv> \
      --banknifty-daily <csv> --out <trade-data/reports/trendline_audit/<date>> [--end YYYY-MM-DD] [--sessions 20] [--no-charts]
"""
import argparse
import dataclasses
import json
import os
import sys
import warnings
from collections import Counter

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import data_policy as DP  # noqa: E402
from pivots import engine as PE  # noqa: E402

# K6 / K4 / K5 numbers (KB, never tuned here)
TOUCH_MR, BETWEEN_MR, SLOPE_MR, SPACING = 0.2, 0.3, 0.5, (6, 8)
BREAK_BUF_MR, DISP_BREAK_MR, OUTER = 0.25, 1.2, 0.30
RECENT_SESSIONS = 2
ZONE_MAX_MR, DISP_BODY, DISP_RANGE_MR, DISP_ONE_MR, FLIP_MR, MAGNET_X = 1.5, 0.6, 1.5, 2.5, 0.5, 4
MR_N = 20
TL_CLASS_EN = {"trade-योग्य": "tradeable", "तुटलेली": "broken", "तीव्र": "steep", "लागू नाही": "n/a", "उमेदवार": "candidate",
               "सपाट": "flat", "मेली": "dead", "stale": "stale"}


# ------------------------------------------------------------------------------------------------ data
def _read(p):
    d = pd.read_parquet(p) if str(p).endswith(".parquet") else pd.read_csv(p)
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    if getattr(d["timestamp"].dt, "tz", None) is not None:
        d["timestamp"] = d["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return d


def no_holdout(df, col="timestamp"):
    d = DP.filter_allowed(df, purpose="annotation", col=col)
    assert not any(DP.period(x) == "HOLDOUT" for x in pd.to_datetime(d[col]).dt.normalize().unique())
    return d.reset_index(drop=True)


def load_1m(paths):
    d = pd.concat([_read(p)[["timestamp", "open", "high", "low", "close"]] for p in paths])
    d = d.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    return no_holdout(d)


def load_m15(m1_paths, older_15m=None):
    """15M = repo resampler (pivots.engine.bars_15m) on 1m; days before the 1m data from an older 15M file (CAS 15:15 bar dropped the
    same way bars_15m drops it)."""
    m15 = PE.bars_15m(load_1m(m1_paths))
    if older_15m:
        from opportunity_engine import cas as CAS
        o = no_holdout(_read(older_15m))
        o = o[o["timestamp"] < pd.to_datetime(m15["timestamp"]).min().normalize()]
        o = o[~CAS.cas_mask(o["timestamp"]).to_numpy()]
        o = o.assign(bar_end=o["timestamp"] + pd.Timedelta(minutes=15))[["timestamp", "bar_end", "open", "high", "low", "close"]]
        m15 = pd.concat([o, m15[["timestamp", "bar_end", "open", "high", "low", "close"]]], ignore_index=True)
    m15 = m15.sort_values("timestamp").reset_index(drop=True)
    PE.guard(m15)
    return m15


def load_daily(path, m15):
    from decision3 import history as HI
    from pivots import charts as PC
    d = HI.load_daily(path)[["timestamp", "open", "high", "low", "close"]] if path else pd.DataFrame(columns=["timestamp"])
    x = PC.daily_from_15m(m15, pd.to_datetime(m15["bar_end"]).max())[["timestamp", "open", "high", "low", "close"]]
    d = pd.concat([d[pd.to_datetime(d["timestamp"]) < x["timestamp"].min()] if len(d) else d, x], ignore_index=True)
    d = no_holdout(d)
    d["bar_end"] = pd.to_datetime(d["timestamp"]) + pd.Timedelta(hours=15, minutes=30)
    return d.reset_index(drop=True)


def h1_of(m15):
    """1H = the live engine's own 15M ⇒ 1H resampler (decision3.levels.h1_frame, 09:15-anchored)."""
    from decision3.levels import h1_frame
    h1, _ = h1_frame(m15)
    be = m15.assign(_k=h1_frame(m15)[1]).groupby("_k")["bar_end"].max().to_numpy()
    h1["bar_end"] = pd.to_datetime(be)
    return h1


def m30_of(m15):
    t = pd.to_datetime(m15["timestamp"])
    day = t.dt.normalize()
    k = (t - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(minutes=30)
    key = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(minutes=30)
    g = m15.assign(_k=key).groupby("_k", sort=True).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                                       close=("close", "last")).reset_index().rename(columns={"_k": "timestamp"})
    return g.assign(volume=0, oi=0)


# ------------------------------------------------------------------------------------------------ frame helpers
class Frame:
    def __init__(self, df, tf):
        self.df = df.reset_index(drop=True)
        self.tf = tf
        self.ts = pd.to_datetime(self.df["timestamp"]).reset_index(drop=True)
        self.day = self.ts.dt.normalize()
        self.O, self.H, self.L, self.C = (self.df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.R = self.H - self.L
        self.idx = {str(x): i for i, x in enumerate(self.ts)}
        days = sorted(self.day.unique())
        self.close_bar = {pd.Timestamp(d): int(np.flatnonzero((self.day == d).to_numpy())[-1]) for d in days}
        self.days = [pd.Timestamp(d) for d in days]

    def mr(self, t):
        return float(np.median(self.R[max(0, t - MR_N + 1):t + 1]))

    def pivots(self, t, kind, k=2):
        """k-fractal pivots confirmed by t (i + k ≤ t)."""
        out = []
        y = self.H if kind == "H" else self.L
        for i in range(k, t - k + 1):
            w = y[i - k:i + k + 1]
            if (kind == "H" and y[i] == w.max()) or (kind == "L" and y[i] == w.min()):
                out.append(i)
        return out


def bar_of(F, ts, alt=None):
    s = str(pd.Timestamp(ts))
    if s in F.idx:
        return F.idx[s]
    if alt is not None and s in alt:
        return alt[s]
    return None


# ------------------------------------------------------------------------------------------------ K6 line check
def greedy_spaced(bars, gap):
    n, last = 0, None
    for b in sorted(bars):
        if last is None or b - last >= gap:
            n, last = n + 1, b
    return n


def check_line(F, t, ln):
    """ln: {b1, y1, b2, y2, side ('res'|'sup')}. Returns metrics + reasons (valid at spacing 6 and 8)."""
    b1, y1, b2, y2, side = ln["b1"], ln["y1"], ln["b2"], ln["y2"], ln["side"]
    mr = F.mr(t)
    m = (y2 - y1) / (b2 - b1) if b2 != b1 else 0.0

    def v(i):
        return y1 + m * (i - b1)
    s = 1 if side == "res" else -1                                          # +1 ⇒ beyond = above
    wick = F.H if side == "res" else F.L
    kind = "H" if side == "res" else "L"
    reasons = []
    anc_dev = max(abs(y1 - wick[b1]), abs(y2 - wick[b2])) / mr
    anchors_ok = anc_dev <= TOUCH_MR
    if not anchors_ok:
        reasons.append("anchor_not_on_wick")
    touch = {i for i in F.pivots(t, kind) if b1 <= i <= t and abs(wick[i] - v(i)) <= TOUCH_MR * mr}
    if anchors_ok:
        touch |= {b1, b2}
    touch = sorted(touch)
    sp6, sp8 = greedy_spaced(touch, SPACING[0]), greedy_spaced(touch, SPACING[1])
    if len(touch) < 3:
        reasons.append("touches_lt3")
    between = [s * (F.C[i] - v(i)) / mr for i in range(b1 + 1, b2)]
    mx_between = max(between) if between else 0.0
    if mx_between > BETWEEN_MR:
        reasons.append("close_through_between_anchors")
    slope_mr = abs(m) / mr
    if slope_mr > SLOPE_MR:
        reasons.append("too_steep")
    brk = None
    for i in range(b2 + 1, t + 1):
        if s * (F.C[i] - v(i)) > BREAK_BUF_MR * mr:
            acc = i + 1 <= t and s * (F.C[i + 1] - v(i + 1)) > BREAK_BUF_MR * mr
            rng = F.R[i]
            pos = (F.C[i] - F.L[i]) / rng if rng > 0 else 0.5
            disp = rng >= DISP_BREAK_MR * mr and (pos >= 1 - OUTER if s > 0 else pos <= OUTER)
            if acc or disp:
                brk = i
                break
    if brk is not None:
        reasons.append("broken")
    recent_days = set(F.days[max(0, F.days.index(F.day[t]) - RECENT_SESSIONS + 1):F.days.index(F.day[t]) + 1])
    recent_touch = any(F.day[i] in recent_days for i in touch)
    if not recent_touch:
        reasons.append("no_touch_last2_sessions")
    sp_r6 = [] if len(touch) < 3 or sp6 >= 3 else ["spacing_lt6"]
    sp_r8 = [] if len(touch) < 3 or sp8 >= 3 else ["spacing_lt8"]
    return {"mr": round(mr, 2), "touches": len(touch), "spaced6": sp6, "spaced8": sp8, "slope_mr_per_bar": round(slope_mr, 3),
            "anchor_dev_mr": round(anc_dev, 3), "max_close_beyond_between_mr": round(mx_between, 3),
            "break_ts": str(F.ts[brk]) if brk is not None else "", "recent_touch": recent_touch, "value_t": round(v(t), 2),
            "valid6": not (reasons + sp_r6), "valid8": not (reasons + sp_r8),
            "reasons6": "|".join(reasons + sp_r6), "reasons8": "|".join(reasons + sp_r8)}


# ------------------------------------------------------------------------------------------------ K4 area check
def _disp_away(F, j, s, mr):
    """displacement starting at j going s (+1 up / −1 down): ≥ 2 consecutive strong candles, or one ≥ 2.5 MR. Returns end bar or None."""
    def strong(i):
        r = F.R[i]
        return r > 0 and s * (F.C[i] - F.O[i]) >= DISP_BODY * r and r >= DISP_RANGE_MR * mr
    if j + 1 < len(F.C) and strong(j) and strong(j + 1):
        return j + 1
    if F.R[j] >= DISP_ONE_MR * mr and s * (F.C[j] - F.O[j]) > 0:
        return j
    return None


def check_area(F, F15, t, ar):
    """ar: {lo, hi, role ('support'|'resistance'|'zone')}."""
    lo, hi, role = float(ar["lo"]), float(ar["hi"]), ar["role"]
    mr = F.mr(t)
    reasons = []
    w = hi - lo
    if w <= 0:
        reasons.append("line_not_zone")
    elif w > ZONE_MAX_MR * mr:
        reasons.append("too_wide")
    c = F.C[t]
    if role == "zone":
        role = "support" if c >= (lo + hi) / 2 else "resistance"
    s = 1 if role == "support" else -1                                      # departure direction
    piv_opp = F.pivots(t, "H" if s > 0 else "L")
    origin, how = None, ""
    for j in range(0, t + 1):
        if not (F.L[j] <= hi and F.H[j] >= lo):
            continue
        mrj = F.mr(j)
        for k in range(j, min(j + 3, t) + 1):
            e = _disp_away(F, k, s, mrj)
            if e is None or e > t:
                continue
            prior = [p for p in piv_opp if p + 2 <= j]
            if not prior:
                continue
            lvl = (F.H if s > 0 else F.L)[prior[-1]]
            if any(s * (F.C[i] - lvl) > 0 for i in range(k, min(e + 3, t) + 1)):
                origin, how = e, "displacement_bos"
                break
    for a in range(1, t + 1):                                               # flip: through by ≥ 0.5 MR, then retest + close back
        if s * (F.C[a] - (hi if s > 0 else lo)) >= FLIP_MR * F.mr(a) and s * (F.C[a - 1] - (hi if s > 0 else lo)) < 0:
            for r in range(a + 1, t + 1):
                touched = F.L[r] <= hi if s > 0 else F.H[r] >= lo
                if touched and s * (F.C[r] - (hi if s > 0 else lo)) > 0:
                    if origin is None or r > origin:
                        origin, how = r, "flip"
                    break
    if origin is None:
        reasons.append("no_displacement_bos_or_flip")
    near = lo if s > 0 else hi                                              # role side at t
    if s * (c - near) < -BREAK_BUF_MR * mr:
        reasons.append("wrong_side_of_price")
    consumed = False
    if origin is not None:
        for i in range(origin + 1, t):
            if s * (near - F.C[i]) > BREAK_BUF_MR * mr and s * (near - F.C[i + 1]) > BREAK_BUF_MR * mr:
                consumed = True
                break
    if consumed and "wrong_side_of_price" not in reasons:
        reasons.append("consumed_by_acceptance")
    t15 = F15.close_bar[F.day[t]] if F.tf != "15M" else t
    sess = np.flatnonzero((F15.day == F15.day[t15]).to_numpy())
    sess = sess[sess <= t15]
    mid = (lo + hi) / 2
    sg = np.sign(F15.C[sess] - mid)
    cross = int(np.sum(sg[1:] * sg[:-1] < 0)) if len(sg) > 1 else 0
    if cross >= MAGNET_X:
        reasons.append("magnet")
    return {"mr": round(mr, 2), "width_mr": round(w / mr, 3), "origin": how, "origin_ts": str(F.ts[origin]) if origin is not None else "",
            "consumed": consumed, "crossings_session": cross, "valid": not reasons, "reasons": "|".join(reasons)}


# ------------------------------------------------------------------------------------------------ engines
def mtf_items(df, tf, sym, bars):
    """trendlines2 lines + zones2 zones as the mtf charts draw them (draw_lines / draw_zones)."""
    from mtf import adapter as MA
    C = MA.build(df[["timestamp", "open", "high", "low", "close"]], tf, sym, bars=bars)
    syn = MA.pseudo15(MA.guard_real(df[["timestamp", "open", "high", "low", "close"]], sym, tf), tf)[0]
    alt = {str(pd.Timestamp(x)): i for i, x in enumerate(syn["timestamp"])}
    out = {}
    for t in bars:
        lines, areas = [], []
        for x in ((C.L5.get(t) or {}).get("lines") or []):
            cls = x.get("class") or ""
            if cls == "तुटलेली" and (x.get("name") or "").startswith("fan"):
                continue                                                    # draw_lines skips broken fans
            lines.append({"engine": "trendlines2", "name": x.get("name") or "line", "class": TL_CLASS_EN.get(cls, "other"),
                          "provisional": bool(x.get("provisional")), "engine_touches": (x.get("touches") or {}).get("held"),
                          "a1": x["a1"], "a2": x["a2"], "side": "res" if x["kind"] == "H" else "sup", "_alt": alt})
        for z in (C.Z.snap.get(t) or []):
            if z["status"] == "dead":
                continue
            areas.append({"engine": "zones2", "name": z["id"], "lo": z["bottom"], "hi": z["top"],
                          "role": "resistance" if z["role"] == "seller" else "support", "class": z["status"],
                          "engine_touches": z.get("visits")})
        out[t] = (lines, areas)
    return out


def d3_items(m15, daily, sym, F15):
    from decision3 import daily as DD
    from decision3 import engine as E3
    from decision3 import history as HI
    from decision3 import trendline as TL
    from decision3 import charts as CH
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        V = E3.V22(m15[["timestamp", "bar_end", "open", "high", "low", "close"]], None, daily, sealed=HI.sealed_fn(sym))
    vts = pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)
    lv = V.levels
    out = {}
    for d in F15.days:
        sel = np.flatnonzero((vts.dt.normalize() == d).to_numpy())
        if not len(sel):
            continue
        t = int(sel[-1])
        st = DD.state_at(V.daily, V.bar_end[t])
        trend = st.trend
        band = st.band if trend == "RANGE" else None
        lines, areas = [], []
        dirs = {"UP": [1], "DOWN": [-1], "RANGE": [1, -1]}.get(trend, [])
        for dd in dirs:
            k = V.pb.at(t, dd)
            kl = TL.k_line(V, t, dd, k) if k else None
            if kl:
                lines.append({"engine": "d3_kline", "name": f"K line d{dd:+d}", "class": "broken" if kl["broken"] else "intact",
                              "engine_touches": kl["touches"], "b1": kl["p1"][0], "y1": kl["p1"][1], "b2": kl["p2"][0], "y2": kl["p2"][1],
                              "side": "sup" if dd < 0 else "res", "_vts": vts})
            sl = TL.swing_line(V, t, dd)
            if sl:
                lines.append({"engine": "d3_swingline", "name": f"swing line d{dd:+d}", "class": "", "engine_touches": sl["touches"],
                              "b1": sl["p1"][0], "y1": sl["p1"][1], "b2": sl["p2"][0], "y2": sl["p2"][1],
                              "side": "res" if dd < 0 else "sup", "_vts": vts})
        sg = lv.sig1h[t]
        lim = float(lv.s["show_distance_sigma"]) * (sg if np.isfinite(sg) else np.inf)
        act = {x["id"] for x in lv.active(t, trend, band)}
        shown = [x for x in lv.snapshot(t) if x["dist"] <= lim or x["id"] in act]
        shown = sorted(shown, key=lambda x: (x["id"] not in act, x["dist"]))[:CH.MAX_LEVEL_BANDS]   # = charts.h1_png (default)
        for x in shown:
            areas.append({"engine": "d3_level", "name": str(x["id"]), "lo": x["lo"], "hi": x["hi"], "role": x["role"],
                          "class": ("active " if x["id"] in act else "") + ("tested" if x.get("tests") else "fresh"),
                          "engine_touches": x.get("tests")})
        if trend in ("UP", "DOWN"):
            for x in V.tl_areas(t, trend):
                areas.append({"engine": "d3_tl_area", "name": str(x["id"]), "lo": x["lo"], "hi": x["hi"], "role": x["role"],
                              "class": "confluence", "engine_touches": (x.get("tl") or {}).get("touches")})
        out[pd.Timestamp(d)] = {"t15": int(F15.idx.get(str(vts[t]), -1)), "trend": trend, "lines": lines, "areas": areas}
    return out


def dash_lines(F, t, days_back):
    """signals.detect_trendline on the dashboard's fetch window (15minute 20 calendar days; 1hour from 30minute 60 days)."""
    from signals import detect_trendline, find_swings
    t0 = int(np.flatnonzero((F.ts >= F.ts[t].normalize() - pd.Timedelta(days=days_back)).to_numpy())[0])
    df = F.df.iloc[t0:t + 1].reset_index(drop=True)
    out = []
    sh, sl = find_swings(df, 3)
    for typ, idx, side in (("low", sl, "sup"), ("high", sh, "res")):
        r = detect_trendline(df, swing_type=typ)
        if not r or not r.get("valid"):
            continue
        rec = idx[-4:]
        xs = np.array(rec, float)
        ys = np.array([df["low" if typ == "low" else "high"].iloc[i] for i in rec], float)
        m, b = np.polyfit(xs, ys, 1)
        out.append({"engine": "dash_tl", "name": r["type"].lower(), "class": r["status"].lower(), "engine_touches": len(rec),
                    "b1": t0 + rec[0], "y1": float(m * rec[0] + b), "b2": t0 + rec[-1], "y2": float(m * rec[-1] + b), "side": side})
    return out


def srv3_areas(m15, daily, t15, chart_tf):
    """dashboard V3 view (sr_v3_chart.v3_chart_lines) on the same windows (FETCH_DAYS), as-of the session close."""
    import sr_levels_v3 as V3
    import sr_v3_chart as V3C
    from signals import resample_to_1h, resample_to_4h
    end = pd.Timestamp(m15["timestamp"].iloc[t15])
    upto = m15.iloc[:t15 + 1]
    ts = pd.to_datetime(upto["timestamp"])

    def last_days(df, n):
        return df[pd.to_datetime(df["timestamp"]) >= end.normalize() - pd.Timedelta(days=n)].reset_index(drop=True)
    m15v = upto.assign(volume=0, oi=0)[["timestamp", "open", "high", "low", "close", "volume", "oi"]]
    want = V3C.CHART_TF_SETS[chart_tf]
    frames = {}
    if "15minute" in want:
        frames["15minute"] = last_days(m15v, V3C.FETCH_DAYS["15minute"])
    m30 = m30_of(upto.assign(timestamp=ts))
    days30 = 70 if "4hour" in want else V3C.FETCH_DAYS["30minute"]
    d30 = last_days(m30, days30)
    if "30minute" in want:
        frames["30minute"] = d30
    if "1hour" in want:
        frames["1hour"] = resample_to_1h(d30)
    if "4hour" in want:
        frames["4hour"] = resample_to_4h(d30)
    dly = daily[pd.to_datetime(daily["timestamp"]) <= end.normalize()].assign(volume=0, oi=0)
    dly = last_days(dly[["timestamp", "open", "high", "low", "close", "volume", "oi"]], 400 if "day" in want else V3C.FETCH_DAYS["day"])
    if "day" in want:
        frames["day"] = dly
    cfg = V3.SRConfig()
    if chart_tf in V3C.DISPLAY_MAX_DISTANCE_PCT:
        cfg = dataclasses.replace(cfg, max_distance_pct=max(cfg.max_distance_pct, V3C.DISPLAY_MAX_DISTANCE_PCT[chart_tf]))
    price = float(upto["close"].iloc[-1])
    res = V3.compute_sr_v3(frames, daily_df=dly, current_price=price, cfg=cfg)
    shown = V3.select_display_levels(res["levels"], price, cfg)
    return [{"engine": "srv3", "name": f"{z['grade']}{int(round(z['score']))} {'+'.join(z['tags'][:3])}", "lo": z["low"], "hi": z["high"],
             "role": z["role"].lower(), "class": z["grade"], "engine_touches": z.get("pivot_count")} for z in shown]


def vision_majors(m15, t15):
    """vision.context.majors: price_action.major_levels on 15M as-of the bar end, 2 nearest per side — drawn as single-price lines."""
    from price_action.major_levels import major_levels
    asof = pd.Timestamp(m15["bar_end"].iloc[t15])
    spot = float(m15["close"].iloc[t15])
    try:
        lv, _, _ = major_levels(m15.iloc[:t15 + 1][["timestamp", "open", "high", "low", "close"]], asof=asof)
    except Exception:
        return []
    up = sorted([x for x in lv if x["price"] > spot], key=lambda x: x["price"])[:2]
    dn = sorted([x for x in lv if x["price"] <= spot], key=lambda x: -x["price"])[:2]
    return [{"engine": "vision_major", "name": f"M{k + 1}{'up' if u else 'dn'}", "lo": float(x["price"]), "hi": float(x["price"]),
             "role": "resistance" if u else "support", "class": "flip" if x.get("role_reversal") else "",
             "engine_touches": x.get("n_react")} for u, grp in ((True, up), (False, dn)) for k, x in enumerate(grp)]


# ------------------------------------------------------------------------------------------------ charts (English only)
ENG_COL = {"trendlines2": "#2a78d6", "d3_kline": "#eb6834", "d3_swingline": "#1baf7a", "dash_tl": "#6250d6",
           "d3_level": "#eb6834", "d3_tl_area": "#e87ba4", "zones2": "#2a78d6", "srv3": "#1baf7a", "vision_major": "#6250d6"}
SHORT = {"touches_lt3": "T<3", "spacing_lt6": "gap<6", "spacing_lt8": "gap<8", "anchor_not_on_wick": "anchor-off-wick",
         "close_through_between_anchors": "close-through", "too_steep": "steep", "broken": "broken", "no_touch_last2_sessions": "stale",
         "line_not_zone": "line-not-zone", "too_wide": "wide", "no_displacement_bos_or_flip": "no-origin", "wrong_side_of_price": "wrong-side",
         "consumed_by_acceptance": "consumed", "magnet": "magnet"}


def render(path, F, t, sym, tf, lines, areas, nbars):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    i0 = max(0, t - nbars + 1)
    x = np.arange(i0, t + 1)
    fig, axs = plt.subplots(1, 2, figsize=(18, 7.5), sharey=True)
    lo_y, hi_y = F.L[i0:t + 1].min(), F.H[i0:t + 1].max()
    pad = 0.08 * (hi_y - lo_y)
    for ax in axs:
        for i in x:
            up = F.C[i] >= F.O[i]
            col = "#7a9a84" if up else "#b07a7a"
            ax.vlines(i, F.L[i], F.H[i], color=col, lw=0.7)
            ax.add_patch(plt.Rectangle((i - 0.3, min(F.O[i], F.C[i])), 0.6, max(abs(F.C[i] - F.O[i]), 1e-6), color=col, lw=0))
        for k in range(i0 + 1, t + 1):
            if F.day[k] != F.day[k - 1]:
                ax.axvline(k - 0.5, color="#bbbbbb", lw=0.6, ls=":")
        ax.set_xlim(i0 - 1, t + nbars * 0.45)
        ax.grid(alpha=0.15)
        ticks = [k for k in range(i0 + 1, t + 1) if F.day[k] != F.day[k - 1]]
        ticks = ([i0] if not ticks or ticks[0] - i0 >= 6 else []) + ticks
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{F.ts[k]:%d %b}" for k in ticks], fontsize=7)
    labs = []
    for ln in lines:
        b1 = ln["b1"]
        xs = np.array([max(b1, i0), t])
        ys = ln["y1"] + (ln["y2"] - ln["y1"]) / (ln["b2"] - b1) * (xs - b1)
        ok = ln["valid6"]
        axs[0].plot(xs, ys, color=ENG_COL[ln["engine"]], lw=2 if ok else 1.2, ls="-" if ok else "--")
        if b1 >= i0:
            axs[0].plot([b1, ln["b2"]] if ln["b2"] >= i0 else [b1], [ln["y1"], ln["y2"]] if ln["b2"] >= i0 else [ln["y1"]], "o",
                        color=ENG_COL[ln["engine"]], ms=4)
        why = "VALID" if ok else ",".join(SHORT.get(r, r) for r in ln["reasons6"].split("|") if r)
        labs.append((0, ys[-1], f"{ln['engine']} {ln['side']} T={ln['touches']}: {why}", ENG_COL[ln["engine"]]))
    for ar in areas:
        ok = ar["valid"]
        if ar["hi"] - ar["lo"] <= 0:
            axs[1].hlines(ar["lo"], i0, t, color=ENG_COL[ar["engine"]], lw=1.4, ls="-" if ok else "--")
        else:
            axs[1].fill_between([i0, t], ar["lo"], ar["hi"], color=ENG_COL[ar["engine"]], alpha=0.22 if ok else 0.10,
                                hatch=None if ok else "//", edgecolor=ENG_COL[ar["engine"]], lw=0.4)
        why = "VALID" if ok else ",".join(SHORT.get(r, r) for r in ar["reasons"].split("|") if r)
        labs.append((1, (ar["lo"] + ar["hi"]) / 2, f"{ar['engine']} {ar['role'][:3]} {ar['lo']:,.0f}-{ar['hi']:,.0f}: {why}",
                     ENG_COL[ar["engine"]]))
    allv = [lo_y, hi_y] + [y for p, y, _, _ in labs if lo_y - 3 * pad <= y <= hi_y + 3 * pad]
    ylo, yhi = min(allv) - pad, max(allv) + pad
    for p in (0, 1):
        items = sorted([z for z in labs if z[0] == p], key=lambda z: z[1])
        gap = (yhi - ylo) / 40
        last = -np.inf
        for _, y, txt, col in items:
            yy = max(y, last + gap)
            yy = min(max(yy, ylo), yhi)
            last = yy
            off = "" if ylo <= y <= yhi else (" (above)" if y > yhi else " (below)")
            axs[p].text(t + 1, yy, txt + off, fontsize=6.5, color="#222222", va="center",
                        bbox=dict(facecolor="white", edgecolor=col, lw=0.6, alpha=0.85, pad=1))
    axs[0].set_ylim(ylo, yhi)
    nv6 = sum(1 for z in lines if z["valid6"])
    nva = sum(1 for z in areas if z["valid"])
    axs[0].set_title(f"Lines drawn: {len(lines)} (K6-valid at 6-bar spacing: {nv6}) - solid = valid, dashed = invalid", fontsize=9, loc="left")
    axs[1].set_title(f"Areas drawn: {len(areas)} (K4-valid: {nva}) - filled = valid, hatched = invalid", fontsize=9, loc="left")
    leg = [Line2D([0], [0], color=ENG_COL[e], lw=2, label=e) for e in ("trendlines2", "d3_kline", "d3_swingline", "dash_tl")]
    axs[0].legend(handles=leg, fontsize=7, loc="upper left")
    leg = [Patch(color=ENG_COL[e], alpha=0.4, label=e) for e in ("d3_level", "d3_tl_area", "zones2", "srv3", "vision_major")]
    axs[1].legend(handles=leg, fontsize=7, loc="upper left")
    fig.suptitle(f"{sym} {tf} - session close {F.ts[t]:%Y-%m-%d %H:%M} (bar start) - audit vs KB K6 / K4, read-only", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=95)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ main
def run_symbol(sym, m15, daily, n_sessions, end, out_dir, charts):
    F15 = Frame(m15, "15M")
    h1 = h1_of(m15)
    F1 = Frame(h1, "1H")
    days = [d for d in F15.days if end is None or d <= end][-n_sessions:]
    b15 = [F15.close_bar[d] for d in days]
    b1h = [F1.close_bar[d] for d in days]
    print(f"{sym}: 15M {len(m15)} bars, sessions {days[0].date()} .. {days[-1].date()}", flush=True)
    mt15 = mtf_items(m15, "15M", sym, b15)
    mt1h = mtf_items(h1, "1H", sym, b1h)
    d3 = d3_items(m15, daily, sym, F15)
    rows = []
    for d, t15, t1 in zip(days, b15, b1h):
        for tf, F, t, (lns, ars) in (("15M", F15, t15, mt15[t15]), ("1H", F1, t1, mt1h[t1])):
            lines, areas = [], []
            for x in lns:
                b1 = bar_of(F, x["a1"]["ts"], x["_alt"])
                b2 = bar_of(F, x["a2"]["ts"], x["_alt"])
                if b1 is None or b2 is None or b1 == b2:
                    continue
                lines.append({**{k: v for k, v in x.items() if k not in ("a1", "a2", "_alt")}, "b1": b1, "y1": float(x["a1"]["price"]),
                              "b2": b2, "y2": float(x["a2"]["price"])})
            areas += ars
            dd = d3.get(pd.Timestamp(d)) or {}
            if tf == "15M":
                for x in dd.get("lines") or []:
                    vts = x["_vts"]
                    b1, b2 = F15.idx.get(str(vts[x["b1"]])), F15.idx.get(str(vts[x["b2"]]))
                    if b1 is None or b2 is None:
                        continue
                    lines.append({**{k: v for k, v in x.items() if k != "_vts"}, "b1": b1, "b2": b2})
                areas += vision_majors(m15, t)
                lines += dash_lines(F, t, 20)
                areas += srv3_areas(m15, daily, t15, "15minute")
            else:
                areas += dd.get("areas") or []
                lines += dash_lines(F, t, 60)
                areas += srv3_areas(m15, daily, t15, "1hour")
            for ln in lines:
                ln.update(check_line(F, t, ln))
                rows.append({"symbol": sym, "tf": tf, "session": str(d.date()), "asof_bar": str(F.ts[t]), "kind": "line",
                             "engine": ln["engine"], "name": ln["name"], "engine_class": ln.get("class", ""),
                             "engine_touches": ln.get("engine_touches"), "side_or_role": ln["side"],
                             "a1_ts": str(F.ts[ln["b1"]]), "a1": round(ln["y1"], 2), "a2_ts": str(F.ts[ln["b2"]]), "a2": round(ln["y2"], 2),
                             **{k: ln[k] for k in ("mr", "touches", "spaced6", "spaced8", "slope_mr_per_bar", "anchor_dev_mr",
                                                   "max_close_beyond_between_mr", "break_ts", "recent_touch", "value_t")},
                             "valid": ln["valid6"], "valid8": ln["valid8"], "reasons": ln["reasons6"], "reasons8": ln["reasons8"]})
            for ar in areas:
                ar.update(check_area(F, F15, t, ar))
                rows.append({"symbol": sym, "tf": tf, "session": str(d.date()), "asof_bar": str(F.ts[t]), "kind": "area",
                             "engine": ar["engine"], "name": ar["name"], "engine_class": ar.get("class", ""),
                             "engine_touches": ar.get("engine_touches"), "side_or_role": ar["role"],
                             "lo": round(float(ar["lo"]), 2), "hi": round(float(ar["hi"]), 2),
                             **{k: ar[k] for k in ("mr", "width_mr", "origin", "origin_ts", "consumed", "crossings_session")},
                             "valid": ar["valid"], "valid8": ar["valid"], "reasons": ar["reasons"], "reasons8": ar["reasons"]})
            if charts:
                cdir = os.path.join(out_dir, "charts", sym, tf)
                os.makedirs(cdir, exist_ok=True)
                render(os.path.join(cdir, f"{sym}_{tf}_{d:%Y%m%d}.png"), F, t, sym, tf, lines, areas, 100 if tf == "15M" else 84)
    return rows


def summary(df):
    out = {}
    for (sym, tf, kind), g in df.groupby(["symbol", "tf", "kind"]):
        e = {}
        for eng, h in g.groupby("engine"):
            rs = Counter(r for x in h["reasons"] if isinstance(x, str) for r in x.split("|") if r)
            rs8 = Counter(r for x in h["reasons8"] if isinstance(x, str) for r in x.split("|") if r)
            e[eng] = {"drawn": int(len(h)), "valid": int(h["valid"].sum()), "valid8": int(h["valid8"].sum()),
                      "sessions_with_item": int(h["session"].nunique()), "reasons": dict(rs), "reasons8": dict(rs8)}
        out[f"{sym}|{tf}|{kind}"] = e
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--nifty-1m", nargs="+", required=True)
    ap.add_argument("--banknifty-1m", nargs="+", required=True)
    ap.add_argument("--banknifty-15m", help="older BANKNIFTY 15M (days before the 1m data)")
    ap.add_argument("--banknifty-daily", help="BANKNIFTY daily history (Q33 warm-up, like engine3_live; not sealed)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--end", help="last session (YYYY-MM-DD); default = last in data")
    ap.add_argument("--sessions", type=int, default=20)
    ap.add_argument("--no-charts", action="store_true")
    a = ap.parse_args(argv)
    end = pd.Timestamp(a.end) if a.end else None
    os.makedirs(a.out, exist_ok=True)
    rows = []
    m15 = load_m15(a.nifty_1m)
    rows += run_symbol("NIFTY", m15, load_daily(None, m15), a.sessions, end, a.out, not a.no_charts)   # NIFTY daily: 15M-derived only (holdout sealed)
    m15 = load_m15(a.banknifty_1m, a.banknifty_15m)
    rows += run_symbol("BANKNIFTY", m15, load_daily(a.banknifty_daily, m15), a.sessions, end, a.out, not a.no_charts)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.out, "trendline_area_audit.csv"), index=False)
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary(df), f, indent=1, default=str)
    print(json.dumps(summary(df), indent=1, default=str))


if __name__ == "__main__":
    main()
