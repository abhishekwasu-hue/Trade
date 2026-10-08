"""chart_reader/evaluate.py — `evaluate(df1m, profile, asof)` ⇒ {side, grade, active_area, invalidation, targets, rr, story, evidence}.

🎓 प्रवाह = KB भाग B चे 8 टप्पे (Abhi 2026-10-08, Knowledge Base), दर वेळी याच क्रमाने:
  0. फक्त asof पर्यंतचे **बंद** bars (1m ⇒ profile चे TFs; bar_end ≤ asof). MR = 20 बंद bars (measures.py, KB भाग G).
  1. मोठं चित्र: HTF trend (areas TFs) [K1] · Elliott [K3].
  2. trade TF: impulse ⇒ बाजू (फक्त impulse दिशेने) · correction प्रकार · entry point (zigzag / flat C-end, triangle E-end) ·
     pullback की reversal [K2].
  3. Areas: **सगळी 12 साधनं (a–l)** उमेदवार (areas.tools) ⇒ active area (K6.4) + confluence (K7).
  4. Area वरचं वर्तन: candles [K9] · correction कमकुवत [K10] · sweep [K5] · futures volume [K10.3] · RSI divergence [K10.2] · patterns [K11].
  5. Context: gap [K13] · वेळ / expiry / VIX [K14] · event.
  6. पुष्टी: logical reversal (elliott composite, soft) active area वर [K9].
  7. Risk: invalidation / target = impulse चं टोक (expanded flat ⇒ B चं टोक), मग पलीकडचे ठोस HTF areas (मधले लहान areas = obstacles) / R:R ≥ 3 · पक्के नियम (A3).
  8. गोष्ट + grade (KB भाग D) + A3 व्याख्यात्मक व्हेटो.
Entry फक्त: पक्के नियम पास + entry point + reversal "ok" + grade A/B (व्हेटो नाही).
Report-only (G-E1a): order नाही, bot ला जोडलेलं नाही. किंमती फक्त OHLC / code areas — vision कडून कधीच नाही.
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import reversal as RV
from elliott import settings as ES
from price_action import levels_v2 as LV

from . import areas as AR
from . import candles as CC
from . import elliott_ctx as EC
from . import evidence as EVD
from . import grade as G
from . import measures as M
from . import narrative as NR
from . import reversal as CRV
from . import risk as RK
from . import rules as RU
from . import settings as CS
from . import structure as ST
from . import trend as TR
from . import volume as VO
import market_state as MS
from .profiles import PROFILES, TF_MINUTES


def frame(df1m, tf, asof):
    """1m ⇒ NSE 09:15-anchored TF bars (CAS वगळून), फक्त पूर्ण बंद (bar_end ≤ asof) — market_state.frame (F1: एकच व्याख्या)."""
    from market_state import frame as _frame
    return _frame(df1m, tf, asof)


def _gap_evidence(g, side):
    if not g or not g.get("has_gap"):
        return "neutral", "gap नाही / G0"
    gdir = 1 if g.get("direction") == "up" else -1
    beh = g.get("behaviour")
    txt = f"{g.get('class')} gap {g.get('direction')} {g.get('gap_atr')}× ATR · {beh} · fill {g.get('fill_pct')}%"
    if gdir == side:
        return ("opposes", txt + " ⇒ gap trade दिशेचा पण नाकारला") if beh == "rejection" else ("confirms", txt + " ⇒ trade दिशेची पुष्टी")
    if beh == "rejection":
        return "confirms", txt + " ⇒ trade विरुद्ध gap अपयशी (setup A)"
    if beh == "acceptance":
        return "opposes", txt + " ⇒ trade विरुद्ध gap स्वीकारला"
    return "neutral", txt + " ⇒ अजून अनिर्णित"


def _ctx(df_cut, asof, g):
    """tool k / l साठी: PDH/PDL/PDC, आठवड्याचे H/L, आजच्या gap चा न भरलेला भाग, जुने unfilled gaps."""
    ctx = AR.prior_levels(df_cut, asof)
    edges = []
    if g.get("has_gap") and g.get("pdc") is not None and g.get("open") is not None:
        edges.append(tuple(sorted((float(g["pdc"]), float(g["open"])))))
    for og in g.get("old_gaps") or []:
        edges.append((float(og["low"]), float(og["high"])))
    ctx["gap_edges"] = edges
    return ctx


def major_zones(horiz, stc, min_degree=2):
    """Structure च्या "major level acceptance" साठी: degree ≥ 2 चे HTF levels (MAGNET / BROKEN / DEAD नाहीत) जे impulse च्या पट्ट्यात आहेत."""
    imp = stc.get("impulse")
    if not imp:
        return []
    lo, hi = sorted((float(imp["origin"]), float(imp["end"])))
    return [(float(z["low"]), float(z["high"])) for z in horiz
            if int(z.get("degree") or 0) >= min_degree and z.get("state") not in AR.BAD and lo <= (z["low"] + z["high"]) / 2.0 <= hi]


def trend_extreme(trig, stc, side):
    """Target चं टोक: impulse सुरू झाल्यापासून trade दिशेचं सर्वात दूरचं टोक — सहसा impulse end; expanded flat मध्ये B ने ते ओलांडलं
    असेल तर B चं टोक (नाहीतर target entry च्या मागे पडतो)."""
    imp = stc.get("impulse")
    if not imp or not side:
        return None
    seg = trig.iloc[int(imp["start_bar"]):]
    return float(seg["high"].max()) if side > 0 else float(seg["low"].min())


def evaluate(df1m, profile, asof, s=None, daily=None, events=None, risk_ok=True, es=None, run_elliott=True, fut5=None, vix=None,
             expiry_day=None):
    """fut5 = futures 5M (collector; नसेल ⇒ VL 0) · vix = India VIX (timestamp, close; नसेल ⇒ VX 0) · expiry_day = holiday shift साठी."""
    s = s or CS.load()
    es = es or dict(ES.DEFAULTS)
    pr = PROFILES[profile]
    asof = pd.Timestamp(asof)
    trig = frame(df1m, pr["trigger_tf"], asof)
    out = {"profile": profile, "asof": str(asof), "side": 0, "grade": "C", "entry": False, "why_no_entry": [], "story": [],
           "evidence": {}, "points": {}, "lines": []}
    if len(trig) < 40:
        out["why_no_entry"].append("trigger TF डेटा अपुरा")
        return out
    cut = df1m[pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof].reset_index(drop=True)
    mr = M.mr_now(trig)
    j = len(trig) - 1
    bar_end = trig["bar_end"].iloc[j]
    # टप्पा 1–2
    htf_frames = {tf: frame(df1m, tf, asof) for tf in pr["areas_tfs"]}
    horiz = []
    for tf in pr["areas_tfs"]:
        horiz += LV.build(htf_frames[tf], tf=tf)["candidates"]
    # F1: trend / impulse / A-B-C / side एकाच market_state मधून
    ms = MS.read(cut, asof, es=es, run_elliott=run_elliott)
    out["market_state"] = ms
    stc = ST.read(trig, s, es=es, ms=ms)
    majors = major_zones(horiz, stc)
    if majors:                                                           # impulse मधले major HTF levels पलीकडे acceptance ⇒ धोक्याचा पुरावा
        stc = ST.read(trig, s, major_zones=majors, es=es, ms=ms)
    side = int(stc["side"])
    if ms["side"] == "unclear" and side:
        # F4: विरोध ⇒ "unclear" + कारण (candidates / vision साठी). Chart Reader मध्ये gate नाही (KB भाग G: HTF trend = context ⇒ T −20 गुण
        # grade मध्ये) — फक्त नोंद आणि गोष्टीत इशारा. Gate हवा का हा निर्णय Abhi चा (kb_traceability).
        out["side_unclear"] = ms["side_reasons"]
    out.update(side=side, structure=stc, mr=round(mr, 2))
    tr = TR.read(htf_frames, pr["areas_tfs"], ms=ms)
    out["trend"] = tr
    el = EC.read(cut, asof, side, tuple(pr["elliott_degrees"]), es) if (run_elliott and side) else {
        "state": "gray", "clear": False, "line": "Elliott: चालवलं नाही", "setup": None, "tier": None, "zone": None, "hard_inv": None}
    out["elliott"] = el
    # टप्पा 5 (gap आधी — areas साठी PDC / gap edges)
    try:
        from vision import gap_context as GC
        g = GC.build(cut, asof, mr, None, events, daily)
    except Exception as exc:
        g = {"has_gap": False, "error": type(exc).__name__}
    gev, gline = _gap_evidence(g, side) if side else ("neutral", "—")
    g["line"] = gline
    out["gap"] = g
    # टप्पा 3: सगळी साधनं
    cands = AR.tools(trig, horiz, stc, _ctx(cut, asof, g), s, mr)
    out["areas"] = {"candidates": cands, "by_tool": {k: sum(z.get("tool") == k for z in cands) for k in "abcdefghijkl"}}
    act = AR.active(trig, cands, side, s, mr) if side else {"area": None, "quality": 0.0, "confluence": [], "confluence_extra": 0,
                                                            "touched_ids": [], "intersection": False}
    out["active"] = act
    # टप्पा 4 / 6
    lc = trig.iloc[j]
    out["last_candle"] = CC.read(lc["open"], lc["high"], lc["low"], lc["close"], mr)
    rv = {"status": "no_area"}
    if act["area"] is not None:
        z = act["area"]
        b = RV.Bars(trig, BR.median_range(trig, es["median_range_n"]))
        atr = trig["high"].sub(trig["low"]).rolling(14).mean().iloc[-1]
        tol = es["zone_tol_atr"] * float(atr if np.isfinite(atr) else mr)
        inv = el.get("hard_inv") if el.get("state") == "end" else None
        rv = CRV.evaluate(b, j, side, [z["low"], z["high"]], tol, es, s, inv=inv, frame=trig)
    out["reversal"] = rv
    # टप्पा 7
    rk = None
    if act["area"] is not None:
        tg, obst = AR.trade_targets(cands, side, float(lc["close"]), trend_extreme(trig, stc, side))
        rk = RK.compute(side, float(lc["close"]), act["area"], rv.get("comp"), tg, mr, s, extreme=stc.get("correction_extreme"))
        rk["obstacles"] = [{"price": round(p, 2), "id": i} for p, i in obst[:3]]
        if obst:
            rk["line"] += " · मधले areas (target नाहीत): " + ", ".join(f"{i} {p:,.1f}" for p, i in obst[:3])
    out["risk"] = rk
    approach = False
    if act["area"] is not None:
        from pullback_credit_spread.signal import approached_from_trend_side
        approach = approached_from_trend_side(trig, act["area"], "LONG" if side > 0 else "SHORT", 20)
    if not side:
        hard = ["impulse / बाजू नाही"]
    elif act["area"] is None:
        hard = ["active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही)"]
    else:
        hard = RU.check({"side": side, "bar_closed": True, "bar_end": bar_end, "approach_ok": approach,
                         "area_role": act["area"].get("role"), "invalidation": (rk or {}).get("invalidation"),
                         "entry": (rk or {}).get("entry"), "rr": (rk or {}).get("rr"), "gap_chase": False, "risk_ok": risk_ok}, s)
    out["hard_rules"] = hard
    # KB ✚ पुरावे + व्हेटो
    lq = EVD.liquidity(trig, stc, cands, side, s, mr)
    deep = (stc.get("retrace") or 0) > s["retrace_max"] and (act["area"] is not None or lq["pts"] > 0)
    t0 = trig["bar_end"].iloc[stc["impulse"]["end_bar"]] if stc.get("impulse") else None
    rvol = VO.series_for(trig, fut5, TF_MINUTES[pr["trigger_tf"]], int(s["vl_slot_days"])) if fut5 is not None else None
    kb = {"PB": EVD.pullback(stc, s, deep_support=deep), "LQ": lq, "VL": VO.evidence(trig, stc, rvol, side, s, mr),
          "DV": EVD.divergence(trig, stc, side, s, mr, htf=tr["htf"]), "PT": EVD.patterns(trig, stc, side, s, mr),
          "TM": EVD.time_of_day(bar_end, s, expiry_day), "VX": EVD.vix(vix, t0, asof, s)}
    out["kb"] = kb
    vetoes = EVD.vetoes(stc, el, act, cands, g, side, trig, s, mr) if side else []
    # टप्पा 8
    ev = {"side": side, "htf": tr["htf"], "trend_strength": tr["trend_strength"], "at_range_edge": tr["at_range_edge"],
          "elliott": el["state"], "elliott_clear": bool(el.get("clear")), "elliott_setup": el.get("setup"),
          "tier": el.get("tier") if el.get("state") == "end" else None,
          "correction_weakening": stc["correction_weakening"], "area_quality": act["quality"], "confluence_extra": act["confluence_extra"],
          "reversal_s": rv.get("s") if rv.get("status") == "ok" else None, "gap": gev, "rr": (rk or {}).get("rr"),
          "event_day": bool(g.get("event")), "pullback": stc["pullback"], "reversal_reasons": stc["reversal_reasons"],
          "kb": {k: {"pts": v["pts"], "line": v["line"]} for k, v in kb.items()}, "vetoes": vetoes}
    sc = G.score(ev, s)
    out.update(evidence=ev, points=sc["points"], lines=sc["lines"], total=sc["total"], grade=sc["grade"], tier=sc["tier"],
               size_mult=sc["size_mult"], vetoes=sc["vetoes"])
    why = list(hard)
    if not stc["entry_point"]:
        why.append(f"pullback end नाही (correction {stc['correction_type'] or '—'}, {stc['pullback']})")
    if rv.get("status") != "ok":
        why.append(f"reversal: {rv.get('status')}")
    why += sc["vetoes"]
    if sc["grade"] == "C" and not sc["vetoes"]:
        why.append(f"grade C ({sc['total']})")
    out["why_no_entry"] = why
    out["entry"] = not why
    out["active_area"] = act.get("area")
    out["invalidation"] = (rk or {}).get("invalidation")
    out["targets"] = (rk or {}).get("targets")
    out["rr"] = (rk or {}).get("rr")
    out["bar_end"] = str(bar_end)
    out["story"] = NR.build(out)
    return out
