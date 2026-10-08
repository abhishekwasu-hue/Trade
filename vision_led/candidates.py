"""vision_led/candidates.py — vision ला दाखवायचे candidates (code, **सैल नियम, high recall**). Abhi 2026-10-08 (TRADE_VISION_LED_PROMPT B2;
C-V1 F1: impulse / correction / side **market_state** मधून — ad-hoc impulse finder काढला).

प्रत्येक बंद 15M bar j वर (फक्त j पर्यंतचे bars — no-lookahead):
  1. market_state.read(asof = bar j चा close): trade-degree impulse (F3) आहे, आणि त्याचा correction origin न तोडता चालू आहे.
  2. correction retrace ≥ pullback_min (38.2%).
  3. किंमत कोणत्याही candidate area जवळ: bar j ची high–low पट्टी आणि area यांचं अंतर ≤ near_mr × MR (12 साधनांपैकी कोणतंही,
     trendline / channel / liquidity सकट; impulse बाजूचा: bull ⇒ area मध्य ≤ close, bear ⇒ ≥ close).
  4. बंद candle वर rejection खूण (impulse दिशेने): wick ≥ 0.4 × range, किंवा CL ≥ 0.6.
  5. 09:30 नंतर (bar start ≥ 09:30).
Side = market_state F4 ("bull_put" / "bear_call" / "unclear" + कारण). Unclear candidate सुद्धा ठेवतो (vision ठरवतो) — पण vision ला
code ची side **दिली जात नाही** (anchoring). एकाच correction चे सलग bars ⇒ एक candidate (पहिला); candidates मध्ये cooldown (bars).
"""
import numpy as np
import pandas as pd

from chart_reader import areas as AR
from chart_reader import measures as M
from price_action import levels_v2 as LV

DEFAULTS = {"pullback_min": 0.382, "near_mr": 0.5, "wick_min": 0.4, "cl_min": 0.6, "start_hm": "09:30", "cooldown_bars": 4}


def impulse_from_state(ms, trig):
    """market_state ⇒ candidates चा impulse dict (trig मधले bar indices timestamp ने). correction नसेल / origin तुटला ⇒ None."""
    imp, corr = ms.get("impulse"), ms.get("correction") or {}
    if not imp or corr.get("status") in (None, "origin_broken", "not_started", "none"):
        return None
    t = trig["timestamp"].to_numpy(dtype="datetime64[ns]")

    def bar(ts):
        return max(int(np.searchsorted(t, np.datetime64(pd.Timestamp(ts), "ns"), side="right")) - 1, 0)
    return {"side": int(imp["dir"]), "s_bar": bar(imp["from_ts"]), "s_px": float(imp["from"]), "e_bar": bar(imp["to_ts"]),
            "e_px": float(imp["to"]), "size_mr": imp["size_mr"], "retrace": float(corr.get("retrace") or 0.0),
            "ext": corr.get("extreme"), "state_side": ms["side"], "side_reasons": list(ms.get("side_reasons") or []),
            "labels": [x["label"] for x in corr.get("labels") or []], "status": corr.get("status")}


def rejection(o, h, l, c, side, cfg):
    rng = h - l
    if rng <= 0:
        return False, 0.0, 0.0
    wick = ((min(o, c) - l) if side > 0 else (h - max(o, c))) / rng
    cl = ((c - l) if side > 0 else (h - c)) / rng
    return bool(wick >= cfg["wick_min"] or cl >= cfg["cl_min"]), round(wick, 3), round(cl, 3)


def near_areas(bar, cands, side, mr, cfg):
    """bar च्या high–low पासून ≤ near_mr × MR मधले trade-बाजूचे areas (सगळी साधनं), जवळचा आधी."""
    lo, hi, c = float(bar["low"]), float(bar["high"]), float(bar["close"])
    out = []
    for z in cands:
        if z.get("state") in ("DEAD",):
            continue
        mid = (z["low"] + z["high"]) / 2.0
        if (mid > c + 1e-9) if side > 0 else (mid < c - 1e-9):
            continue
        dist = max(0.0, z["low"] - hi, lo - z["high"]) / mr
        if dist <= cfg["near_mr"]:
            out.append((round(dist, 3), z))
    return [z for _, z in sorted(out, key=lambda x: x[0])]


def scan(df1m, trig, start, end, s, cfg=None, frame_fn=None, ctx_fn=None, horiz_fn=None, state_fn=None):
    """[start, end] मधल्या प्रत्येक बंद 15M bar वर नियम. रिटर्न candidates [{bar_end, j, side, impulse, areas, wick, cl, state}].
    state_fn(bar_end) ⇒ market_state (default: market_state.read(df1m, bar_end))."""
    cfg = {**DEFAULTS, **(cfg or {})}
    if state_fn is None:
        import market_state as MS

        def state_fn(be):
            return MS.read(df1m, be)
    mra = M.mr_array(trig)
    out, last_j, last_key = [], -10 ** 9, None
    prev_ok_key, prev_ok_j = None, None
    ends = pd.to_datetime(trig["bar_end"])
    for j in range(len(trig)):
        be = ends.iloc[j]
        if be < pd.Timestamp(start) or be > pd.Timestamp(end):
            continue
        if pd.Timestamp(trig["timestamp"].iloc[j]).strftime("%H:%M") < cfg["start_hm"]:
            continue
        mr = mra[j] if np.isfinite(mra[j]) else M.mr_now(trig.iloc[:j])
        if not mr or not np.isfinite(mr):
            continue
        ms = state_fn(be)
        imp = impulse_from_state(ms, trig.iloc[: j + 1])
        if imp is None or imp["retrace"] < cfg["pullback_min"]:
            prev_ok_key = None
            continue
        bar = trig.iloc[j]
        ok, wick, cl = rejection(float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]), imp["side"], cfg)
        if not ok:
            prev_ok_key = None
            continue
        d = trig.iloc[: j + 1].reset_index(drop=True)
        horiz = horiz_fn(be) if horiz_fn else []
        st = {"impulse": {"origin": imp["s_px"], "end": imp["e_px"], "start_bar": imp["s_bar"], "end_bar": imp["e_bar"]}}
        cands = AR.tools(d, horiz, st, (ctx_fn(be) if ctx_fn else {}), s, mr)
        near = near_areas(bar, cands, imp["side"], mr, cfg)
        if not near:
            prev_ok_key = None
            continue
        key = (imp["side"], imp["e_bar"])
        if key == prev_ok_key and prev_ok_j == j - 1:                    # एकाच correction चे सलग bars ⇒ एकच candidate
            prev_ok_j = j
            continue
        prev_ok_key, prev_ok_j = key, j
        if j - last_j <= cfg["cooldown_bars"]:
            continue
        last_j, last_key = j, key
        out.append({"bar_end": be, "bar_start": pd.Timestamp(trig["timestamp"].iloc[j]), "j": j, "side": imp["side"], "impulse": imp,
                    "code_side": ms["side"], "side_reasons": ms["side_reasons"], "state_lines": ms["lines"],
                    "swings": ms.get("swings") or [], "htf_swings": ms.get("trend_swings") or [], "htf_tf": ms["tf"]["trend"],
                    "mr": float(mr), "wick": wick, "cl": cl, "areas": near[:6], "all_areas": cands})
    return out


def htf_levels(df1m, asof, frame_fn, tfs=("1h", "1d")):
    """Areas TFs चे levels_v2 candidates (फक्त asof पर्यंत)."""
    out = []
    for tf in tfs:
        f = frame_fn(df1m, tf, asof)
        if len(f) >= 30:
            out += LV.build(f, tf=tf)["candidates"]
    return out
