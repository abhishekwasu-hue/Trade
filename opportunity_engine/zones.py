"""opportunity_engine/zones.py — structure मधून तयार होणारे zones/levels (Supply/Demand, swing S/R clusters, KEY, GAP) आणि त्यांचं Level Quality.

🎓 स्रोत (spec §2.4):
  • DISPLACEMENT zones — impulsive चालीच्या आधीचा base candle (origin). Displacement = सलग ≥2 candles (प्रत्येकाचा body ≥ 0.6 range आणि range ≥ 1.5×ref_range)
    किंवा एकच candle range ≥ 2.5×ref_range. (जुने `market_zones.detect_demand_supply_zones` सरासरी-range वापरतं; इथे फक्त मोजपट्टी `k × ref_range`.)
  • SR clusters — confirmed swing highs/lows, 0.3% च्या आत merge, touches. Core = body edges, outer = wicks. Spike swing ची wick वापरली जात नाही (SWEEP यादीत).
  • KEY — PDH/PDL/PDC, मागच्या आठवड्याचा High/Low, round numbers (NIFTY 100, BANKNIFTY 500).
  • GAP registry — मागच्या 20 sessions चे opening gaps ≥ 0.25%: zone [PDC, Open], status UNFILLED/PARTIAL/FILLED.
Zone माहिती: freshness FRESH|TESTED_1|TESTED_2+, status ACTIVE|MITIGATED|BROKEN (MITIGATED = core मध्ये close; BROKEN = दूरच्या कडेपलीकडे सलग 2 closes = acceptance → flip-candidate),
role सध्याच्या किंमतीच्या सापेक्ष.
`ref_range` फक्त `k × tracker.rr_hist[i]` (मोजपट्टी). जुना कोड (market_zones/V3) बदललेला नाही.
"""
import numpy as np
import pandas as pd

from . import cas as CAS
from .config import EngineConfig
from .level_quality import (ORIGIN_SCORE, REJECT_REASONS, body_core_score, density_percentile, grade, level_id, price_density,
                            reaction_strength, spike_kind)

BREAK_EVENTS = {"BOS", "REVERSAL_CONFIRMED", "RECOVERY", "RANGE_EXIT_UP", "RANGE_EXIT_DOWN"}
ROUND_STEP = {"NIFTY": 100.0, "BANKNIFTY": 500.0, "SENSEX": 500.0}
EVAL_TF = {"15m", "1h", "4h", "1d", "5m"}


def _break_index(tr):
    """{bar_idx: {+1/−1}} — कोणत्या bars वर structure break (BOS/Reversal/Recovery/Range-exit) कोणत्या दिशेने झाला."""
    out = {}
    for e in tr.events:
        if e["type"] in BREAK_EVENTS:
            to = e.get("to_state", e["state"])
            out.setdefault(e["bar_idx"], set()).add(1 if str(to).startswith("UPTREND") else -1)
    return out


def _finite(x):
    return x is not None and np.isfinite(x)


# ---------------------------------------------------------------------------------------------------------------------
# स्रोत १: displacement zones
# ---------------------------------------------------------------------------------------------------------------------
def displacement_zones(tr, cfg=None, upto=None, start=0):
    """एका TF चे supply/demand zones (evaluate() आधी — status/freshness नाही). `upto` = शेवटचा वापरायचा bar index (as-of)."""
    cfg = cfg or tr.cfg
    n = len(tr.c) if upto is None else min(len(tr.c), upto + 1)
    o, h, l, c, rr_hist = tr.o, tr.h, tr.l, tr.c, tr.rr_hist
    breaks = _break_index(tr)
    zones, sweeps = [], []

    def qualifies(i, direction, k_mult):
        rr = rr_hist[i]
        if not _finite(rr) or rr <= 0:
            return False
        rng = h[i] - l[i]
        if rng <= 0 or abs(c[i] - o[i]) < cfg.displacement_body_min * rng:
            return False
        if direction != (1 if c[i] > o[i] else -1):
            return False
        return rng >= k_mult * rr

    i = max(int(start), 0)                       # `start`: फक्त अलीकडच्या bars मधले zones हवे असतील तर मागचा इतिहास वगळून (backtest ची गती)
    while i < n:
        direction = 1 if c[i] > o[i] else -1 if c[i] < o[i] else 0
        if direction == 0 or not qualifies(i, direction, cfg.displacement_k):
            i += 1
            continue
        j = i
        while j + 1 < n and qualifies(j + 1, direction, cfg.displacement_k):
            j += 1
        run = j - i + 1
        single = run == 1 and qualifies(i, direction, cfg.displacement_single_k)
        if run < 2 and not single:
            i = j + 1
            continue
        a, formed = i, (i if single else i + 1)
        # origin base: displacement आधीचा शेवटचा विरुद्ध-दिशेचा candle (≤4 bars मागे); नसेल तर लगेचचा आधीचा
        base = None
        for k in range(a - 1, max(a - 5, -1), -1):
            if (direction > 0 and c[k] < o[k]) or (direction < 0 and c[k] > o[k]):
                base = k
                break
        if base is None and a - 1 >= 0:
            base = a - 1
        if base is None:
            i = j + 1
            continue
        body_lo, body_hi = min(o[base], c[base]), max(o[base], c[base])
        outer_lo, outer_hi, spike = l[base], h[base], False
        sk = spike_kind(o[base], h[base], l[base], c[base + 1:base + 1 + int(cfg.spike_return_bars)], rr_hist[base], cfg, o[base], c[base])
        if cfg.spike_body_edge and sk is not None:
            spike = True
            sweeps.append({"tf": tr.tf, "price": float(l[base] if sk == "DOWN" else h[base]), "side": "LOW" if sk == "DOWN" else "HIGH",
                           "time": tr.bar_end[base], "bar_idx": base})
            outer_lo, outer_hi = (body_lo, outer_hi) if sk == "DOWN" else (outer_lo, body_hi)
        confirmed = any(direction in breaks.get(x, ()) for x in range(a, min(formed + 2, n)))
        top = max(h[a:j + 1]) if direction > 0 else None
        bottom = min(l[a:j + 1]) if direction < 0 else None
        departure = ((top - outer_hi) if direction > 0 else (outer_lo - bottom)) / rr_hist[formed]
        zones.append({
            "tf": tr.tf, "kind": "DEMAND" if direction > 0 else "SUPPLY", "source": "DISPLACEMENT",
            "low": float(outer_lo), "high": float(outer_hi), "core_low": float(body_lo), "core_high": float(body_hi),
            "origin_idx": base, "formed_idx": formed, "formed_at": tr.bar_end[formed],
            "origin_type": "ORIGIN_BOS" if confirmed else "ORIGIN_MINOR", "departure_rr": float(max(departure, 0.0)), "spike": spike,
        })
        i = j + 1
    return zones, sweeps


# ---------------------------------------------------------------------------------------------------------------------
# स्रोत २: swing S/R clusters
# ---------------------------------------------------------------------------------------------------------------------
def sr_clusters(tr, cfg=None, upto=None):
    """confirmed swing highs (RESISTANCE) आणि lows (SUPPORT) चे 0.3% merge clusters. Core = body edges (टॉप/बॉटम), outer = wicks."""
    cfg = cfg or tr.cfg
    swings = [sw for sw in tr.swings if upto is None or sw.confirmed_idx <= upto]
    zones, sweeps = [], []
    for kind, label in (("H", "RESISTANCE"), ("L", "SUPPORT")):
        pts = sorted((sw for sw in swings if sw.kind == kind), key=lambda sw: sw.price)
        groups, cur = [], []
        for sw in pts:
            if cur and (sw.price - cur[0].price) > cur[0].price * cfg.merge_pct / 100.0:
                groups.append(cur)
                cur = []
            cur.append(sw)
        if cur:
            groups.append(cur)
        for g in groups:
            body_edges, wick_edges = [], []
            for sw in g:
                i = sw.idx
                edge = max(tr.o[i], tr.c[i]) if kind == "H" else min(tr.o[i], tr.c[i])
                wick = tr.h[i] if kind == "H" else tr.l[i]
                if sw.spike:
                    sweeps.append({"tf": tr.tf, "price": float(wick), "side": "HIGH" if kind == "H" else "LOW", "time": sw.time, "bar_idx": i})
                    wick = edge
                body_edges.append(edge)
                wick_edges.append(wick)
            if kind == "H":
                core_lo, core_hi, outer_lo, outer_hi = min(body_edges), max(body_edges), min(body_edges), max(wick_edges)
            else:
                core_lo, core_hi, outer_lo, outer_hi = min(body_edges), max(body_edges), min(wick_edges), max(body_edges)
            formed = min(sw.confirmed_idx for sw in g)
            zones.append({
                "tf": tr.tf, "kind": label, "source": "SWING", "low": float(outer_lo), "high": float(outer_hi),
                "core_low": float(core_lo), "core_high": float(core_hi), "origin_idx": min(sw.idx for sw in g), "formed_idx": formed,
                "formed_at": tr.bar_end[formed], "origin_type": "ORIGIN_NONE", "departure_rr": 0.0,
                "spike": any(sw.spike for sw in g), "swing_count": len(g),
            })
    return zones, sweeps


# ---------------------------------------------------------------------------------------------------------------------
# स्रोत ३/४: KEY levels, round numbers, gaps
# ---------------------------------------------------------------------------------------------------------------------
def key_levels(daily, t, price, symbol="NIFTY", round_band_pct=3.0):
    """PDH/PDL/PDC, मागच्या आठवड्याचा High/Low (t पर्यंत बंद झालेल्या daily bars वरून) + round numbers. रिटर्न: zones (low==high) ची यादी."""
    out = []
    if daily is not None and len(daily):
        d = daily[daily["bar_end"] <= pd.Timestamp(t)].copy()
        if len(d):
            d["date"] = d["timestamp"].dt.normalize()
            last = d.iloc[-1]
            pdc = float(CAS.pdc_col(d).iloc[-1])                          # PDC = official close (CAS); PDH/PDL CAS वगळून
            for name, val in (("PDH", last["high"]), ("PDL", last["low"]), ("PDC", pdc)):
                out.append((name, float(val), last["bar_end"]))
            # "आजचा/पुढचा session" = शेवटच्या बंद दिवसानंतरचा weekday; मागचा आठवडा = त्या session च्या आठवड्याआधीचा (शुक्रवार बंद झाल्यावर => नुकताच संपलेला आठवडा)
            ref = last["date"] + pd.Timedelta(days=1)
            while ref.weekday() >= 5:
                ref += pd.Timedelta(days=1)
            week_start = ref - pd.Timedelta(days=int(ref.weekday()))
            prev = d[(d["date"] >= week_start - pd.Timedelta(days=7)) & (d["date"] < week_start)]
            if len(prev):
                out.append(("PWH", float(prev["high"].max()), prev["bar_end"].iloc[-1]))
                out.append(("PWL", float(prev["low"].min()), prev["bar_end"].iloc[-1]))
    step = ROUND_STEP.get(symbol, 100.0)
    if _finite(price) and price > 0:
        lo, hi = price * (1 - round_band_pct / 100.0), price * (1 + round_band_pct / 100.0)
        k = int(np.ceil(lo / step))
        while k * step <= hi:
            out.append((f"R{int(k * step)}", float(k * step), pd.Timestamp(t)))
            k += 1
    zones = []
    for name, val, when in out:
        zones.append({"tf": "1d", "kind": "KEY" if not name.startswith("R") else "ROUND", "source": name, "low": val, "high": val,
                      "core_low": val, "core_high": val, "origin_idx": None, "formed_idx": None, "formed_at": when,
                      "origin_type": "ORIGIN_NONE", "departure_rr": 0.0, "spike": False})
    return zones


def gap_registry(daily, t, cfg):
    """मागच्या `gap_sessions` sessions चे opening gaps ≥ gap_min_pct. zone [PDC, Open]; status UNFILLED/PARTIAL/FILLED (t पर्यंत बंद झालेल्या दिवसांवरून)."""
    if daily is None or len(daily) < 2:
        return []
    d = daily[daily["bar_end"] <= pd.Timestamp(t)].reset_index(drop=True)
    if len(d) < 2:
        return []
    out = []
    start = max(1, len(d) - int(cfg.gap_sessions))
    closes = CAS.pdc_col(d).to_numpy(float)                              # official close (CAS)
    for i in range(start, len(d)):
        pdc, op = float(closes[i - 1]), float(d["open"].iloc[i])
        if pdc <= 0 or abs(op - pdc) / pdc * 100.0 < cfg.gap_min_pct:
            continue
        up = op > pdc
        after = d.iloc[i:]
        if up:
            filled = float(after["low"].min()) <= pdc
            partial = float(after["low"].min()) < op
        else:
            filled = float(after["high"].max()) >= pdc
            partial = float(after["high"].max()) > op
        out.append({
            "tf": "1d", "kind": "GAP", "source": "GAP_UP" if up else "GAP_DOWN", "low": min(pdc, op), "high": max(pdc, op),
            "core_low": min(pdc, op), "core_high": max(pdc, op), "origin_idx": i, "formed_idx": i, "formed_at": d["bar_start"].iloc[i],
            "origin_type": "ORIGIN_MINOR", "departure_rr": 0.0, "spike": False,
            "gap_status": "FILLED" if filled else "PARTIAL" if partial else "UNFILLED",
        })
    return out


# ---------------------------------------------------------------------------------------------------------------------
# मूल्यांकन: touches, reaction, freshness, status
# ---------------------------------------------------------------------------------------------------------------------
def evaluate(zone, tr, upto=None, band_rr=0.0, cfg=None):
    """zone चे touches (वेगळ्या visits), reaction excursions, freshness, status — zone बनल्यानंतरच्या bars वर (as-of `upto`). zone मध्ये भर घालतो आणि परत करतो."""
    cfg = cfg or tr.cfg
    n = len(tr.c) if upto is None else min(len(tr.c), upto + 1)
    zone.setdefault("excursions_rr", [])
    start = (zone["formed_idx"] + 1) if zone.get("formed_idx") is not None else max(n - 400, 0)
    zone.update({"touches": 0, "excursions_rr": [], "visit_ages": [], "mitigated": False, "broken": False, "broken_idx": None})
    if start >= n:
        return _finalize_status(zone)
    h = np.asarray(tr.h[start:n]); l = np.asarray(tr.l[start:n]); c = np.asarray(tr.c[start:n])
    rr = np.asarray(tr.rr_hist[start:n], dtype="float64")
    pad = np.where(np.isfinite(rr), band_rr * rr, 0.0)
    overlap = (l <= zone["high"] + pad) & (h >= zone["low"] - pad)
    supply_side = zone["kind"] in ("SUPPLY", "RESISTANCE")
    far_break = c > zone["high"] if supply_side else c < zone["low"]
    if zone["kind"] in ("KEY", "ROUND", "GAP"):
        supply_side = None
    # तुटणं (acceptance): दूरच्या कडेपलीकडे सलग 2 closes (फक्त supply/demand/support/resistance साठी)
    end = len(c)
    if supply_side is not None:
        both = far_break[:-1] & far_break[1:]
        if both.any():
            zone["broken_idx"] = start + int(np.argmax(both)) + 1
            zone["broken"] = True
            end = zone["broken_idx"] - start
    # visits
    visits = []
    prev = False
    for j in range(end):
        if overlap[j] and not prev:
            visits.append(j)
        prev = bool(overlap[j])
    zone["touches"] = len(visits)
    nb = int(cfg.reaction_bars)
    for j in visits:
        w = slice(j, min(j + nb + 1, len(c)))
        rr_j = rr[j] if np.isfinite(rr[j]) and rr[j] > 0 else np.nan
        if not np.isfinite(rr_j):
            continue
        if supply_side is True:
            exc = (zone["low"] - float(l[w].min())) / rr_j
        elif supply_side is False:
            exc = (float(h[w].max()) - zone["high"]) / rr_j
        else:
            exc = max((float(h[w].max()) - zone["high"]), (zone["low"] - float(l[w].min()))) / rr_j
        zone["excursions_rr"].append(max(float(exc), 0.0))
        zone["visit_ages"].append(float(n - 1 - (start + j)))
    inside_core = (c[:end] >= zone["core_low"]) & (c[:end] <= zone["core_high"])
    zone["mitigated"] = bool(inside_core.any()) if zone["kind"] in ("SUPPLY", "DEMAND") else False
    return _finalize_status(zone)


def _finalize_status(zone):
    t = zone.get("touches", 0)
    zone["freshness"] = "FRESH" if t == 0 else "TESTED_1" if t == 1 else "TESTED_2+"
    zone["status"] = "BROKEN" if zone.get("broken") else "MITIGATED" if zone.get("mitigated") else "ACTIVE"
    return zone


def role_of(zone, price):
    """role सध्याच्या किंमतीच्या सापेक्ष (SRv2 चा धडा): किंमत वर => SUPPORT, खाली => RESISTANCE, आत => ZONE."""
    if not _finite(price):
        return "ZONE"
    return "RESISTANCE" if price < zone["low"] else "SUPPORT" if price > zone["high"] else "ZONE"


# ---------------------------------------------------------------------------------------------------------------------
# एकत्रित
# ---------------------------------------------------------------------------------------------------------------------
def _mid(z):
    return (z["core_low"] + z["core_high"]) / 2.0


def _mtf_counts(zones, cfg):
    """प्रत्येक zone जवळ (confluence_pct च्या आत किंवा overlap) किती वेगळे TF चे levels आहेत (स्वतः सकट)."""
    out = []
    for z in zones:
        tol = _mid(z) * cfg.confluence_pct / 100.0
        tfs = {z["tf"]}
        for o in zones:
            if o is z or o["tf"] in tfs or o["kind"] == "ROUND":          # round number स्वतःहून TF-confluence देत नाही (psychological, structural नाही)
                continue
            if abs(_mid(o) - _mid(z)) <= tol:                      # core-मध्य एकमेकांच्या confluence_pct (0.15%) च्या आत (रुंद gap/outer ने फुगवलेलं नाही)
                tfs.add(o["tf"])
        out.append(len(tfs))
    return out


def build_levels(journal, frames, symbol="NIFTY", price=None, cfg=None, lookback=None, tfs=("15m", "1h", "4h", "1d"), fine=None):
    """सर्व स्रोत -> गुणांकित levels. रिटर्न: {"levels": [...], "sweeps": [...], "rejected": [...]} — `rejected` मध्ये "का नाकारला" सकट.
    `lookback` = {tf: शेवटचे किती bars मधले zones} (डीफॉल्ट: 15m 1500, 1h 1500, 4h 1000, 1d 600)."""
    cfg = cfg or journal.cfg
    lookback = lookback or {"15m": 1500, "1h": 1500, "4h": 1000, "1d": 600}
    zones, sweeps = [], []
    t_now = None
    for tf in tfs:
        tr = journal.trackers.get(tf)
        if tr is None or not tr.c:
            continue
        t_now = tr.bar_end[-1] if t_now is None else max(t_now, tr.bar_end[-1])
        floor_idx = max(len(tr.c) - int(lookback.get(tf, 1000)), 0)
        for builder in (displacement_zones, sr_clusters):
            zs, sw = builder(tr, cfg, start=max(floor_idx - 8, 0)) if builder is displacement_zones else builder(tr, cfg)
            for z in zs:
                if z["formed_idx"] < floor_idx:
                    continue
                zones.append(evaluate(z, tr, None, band_rr=0.1 if z["source"] == "SWING" else 0.0, cfg=cfg))
            sweeps += sw
    daily = frames.get("1d")
    ref_tr = journal.trackers.get("15m") or journal.trackers.get("1h")
    if t_now is not None and ref_tr is not None:
        tr = journal.trackers.get("15m", ref_tr)
        be = pd.DatetimeIndex(tr.bar_end)
        for z in key_levels(daily, t_now, price, symbol) + gap_registry(daily, t_now, cfg):
            # KEY/GAP: touches/reaction त्या level बनल्यानंतरच्या bars वरून (ROUND: शेवटचे ~400 bars)
            if z["kind"] in ("KEY", "GAP") and z.get("formed_at") is not None:
                z["formed_idx"] = max(int(be.searchsorted(pd.Timestamp(z["formed_at"]), side="right")) - 1, 0)
            else:
                z["formed_idx"] = None
            z["eval_tf"] = tr.tf                                   # index इथल्या tracker (15m) चा; tf='1d' फक्त MTF/लेबलसाठी
            zones.append(evaluate(z, tr, None, band_rr=0.5 if z["kind"] != "GAP" else 0.0, cfg=cfg))
    edges, share = price_density(fine if fine is not None else frames.get("5m"), cfg.density_sessions, cfg.density_bin_pct)
    mtf = _mtf_counts(zones, cfg)
    levels, rejected = [], []
    for z, m in zip(zones, mtf):
        tr = journal.trackers.get(z.get("eval_tf", z["tf"])) or ref_tr
        rr = tr.rr_hist[z["formed_idx"]] if z.get("formed_idx") is not None and tr.rr_hist else tr.rr
        if not _finite(rr):
            rr = tr.rr
        comps = {
            "clean": 0.0 if z.get("spike") else 1.0,
            "body_core": body_core_score(z["core_high"] - z["core_low"], z["high"] - z["low"], rr) if z["kind"] not in ("KEY", "ROUND") else (0.7 if z["kind"] == "KEY" else 0.5),
            "origin": 0.0 if z["kind"] == "ROUND" else ORIGIN_SCORE.get(z["origin_type"], 0.2),
            "reaction": reaction_strength(z.get("excursions_rr", []), z.get("visit_ages", []), z.get("departure_rr", 0.0)),
            "density": density_percentile(edges, share, _mid(z)),
            "mtf": float(np.clip((m - 1) / 2.0, 0.0, 1.0)),
        }
        score, letter = grade(comps, cfg)
        reason = None
        if z["kind"] == "GAP" and z.get("gap_status") == "FILLED":
            reason = "FILLED"
        elif z.get("broken") and z["kind"] != "GAP":
            reason = "BROKEN"
        elif letter == "REJECT":
            reason = "LOW_SCORE"
        z.update({
            "symbol": symbol, "quality_components": {k: round(v, 3) for k, v in comps.items()}, "quality_score": score, "quality_grade": "REJECT" if reason else letter,
            "mtf_count": m, "minor": m <= 1, "role": role_of(z, price), "reject_reason": REJECT_REASONS.get(reason) if reason else None,
            "outer_low": z["low"], "outer_high": z["high"],
            "level_id": level_id(symbol, z["tf"], z["kind"] + ":" + str(z.get("source", "")), _mid(z), z["formed_at"]),
        })
        (rejected if reason else levels).append(z)
    levels.sort(key=lambda z: (-z["quality_score"], z["tf"]))
    return {"levels": levels, "sweeps": sweeps, "rejected": rejected}
