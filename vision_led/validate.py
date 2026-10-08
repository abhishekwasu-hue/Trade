"""vision_led/validate.py — vision च्या उत्तरावर code ची तपासणी (TRADE_VISION_LED_PROMPT B5) + hindsight (B7).

  1. प्रत्येक ohlc_ref ("YYYY-MM-DD HH:MM open|high|low|close") ची किंमत OHLC तक्त्यात खरंच आहे (± ref_tol_mr × MR). नसेल ⇒ reject.
     Entry ref = decision bar चा close (पुढचा / मागचा bar नाही).
  2. बाजू सुसंगत (bull: invalidation < entry < target) · invalidation = ref + buffer (inv_buffer_mr × MR, पलीकडे) · spot R:R ≥ min_rr.
  3. पाच पक्के नियम (chart_reader/rules.py) आणि A3 व्हेटो (chart_reader/evidence.py) — vision ने निवडलेल्या area वर.
  4. Strike (फक्त माहिती): max(|spot − inv| + 0.5 MR, k × spot × σ20 × √(DTE + 1)), 50 च्या पटीत पलीकडे.
  5. दोन SL व्याख्या (C-V1 §4): reversal-candle SL आणि structural SL (active area / trendline पलीकडे) — दोन्हींचा R:R (अहवाल / chart).
     Vision चा SL structural पेक्षा जवळ आणि invalidation_reason रिकामा ⇒ warning (reject नाही).
Hindsight: entry नंतरच्या पुढच्या 2 trading दिवसांत target की SL आधी (एकाच bar मध्ये दोन्ही ⇒ SL, सावध).
"""
import math
import re

import numpy as np
import pandas as pd

REF_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+(open|high|low|close)\s*$", re.I)
DEFAULTS = {"ref_tol_mr": 0.1, "inv_buffer_mr": 0.25, "min_rr": 3.0, "strike_k": 1.0, "strike_step": 50, "expiry_weekday": 1}


def ref_value(ref, tables):
    """ohlc_ref ⇒ (मूल्य, bar ts, field) किंवा (None, None, कारण). tables = [15M df, 1H df] (timestamp = bar start)."""
    m = REF_RE.match(str(ref or ""))
    if not m:
        return None, None, f"ohlc_ref अवैध: {ref!r}"
    ts, field = pd.Timestamp(m.group(1)), m.group(2).lower()
    vals = ref_values(ts, field, tables)
    if vals:
        return vals[0], ts, field
    return None, None, f"ohlc_ref चा bar तक्त्यात नाही: {ref}"


def ref_values(ts, field, tables):
    """त्याच वेळेचे सगळे तक्ते (15M आणि 1H दोन्हीत 14:15 असू शकतो) ⇒ मूल्यांची यादी (तक्त्यांच्या क्रमाने)."""
    out = []
    for t in tables:
        hit = t[pd.to_datetime(t["timestamp"]) == ts]
        if len(hit):
            out.append(float(hit[field].iloc[0]))
    return out


def check_refs(v, tables, decision_start, mr, cfg):
    errs = []
    vals = {}
    for key in ("entry", "invalidation", "target"):
        r = v.get(key) or {}
        val, ts, fld = ref_value(r.get("ohlc_ref"), tables)
        if val is None:
            errs.append(f"{key}: {fld}")
            continue
        try:
            px = float(r.get("price"))
        except (TypeError, ValueError):
            errs.append(f"{key}: price अवैध")
            continue
        cands = ref_values(ts, fld, tables)                              # 15M / 1H दोन्हीत तीच वेळ ⇒ price शी जुळणारा (V3 review)
        val = min(cands, key=lambda x: abs(px - x)) if cands else val
        if abs(px - val) > cfg["ref_tol_mr"] * mr:
            errs.append(f"{key}: price {px:,.2f} ≠ OHLC {r.get('ohlc_ref')} = {val:,.2f} (> {cfg['ref_tol_mr']} MR)")
            continue
        vals[key] = (val, ts, fld)
    if "entry" in vals and (vals["entry"][1] != pd.Timestamp(decision_start) or vals["entry"][2] != "close"):
        errs.append(f"entry: decision bar ({pd.Timestamp(decision_start):%Y-%m-%d %H:%M}) चा close हवा, मिळालं {v['entry'].get('ohlc_ref')}")
    return vals, errs


def strike_info(side, spot, inv, mr, daily_close, asof, cfg):
    """σ-आधारित short strike (माहिती). daily_close = आधीच्या पूर्ण दिवसांचे closes."""
    r = np.diff(np.log(np.asarray(daily_close, float)[-21:]))
    sig = float(np.std(r, ddof=1)) if len(r) >= 5 else float("nan")
    d = pd.Timestamp(asof).normalize()
    dte = (cfg["expiry_weekday"] - d.weekday()) % 7 or 7                 # expiry दिवशी ⇒ पुढचा weekly (KB K14)
    dist = abs(spot - inv) + 0.5 * mr
    if np.isfinite(sig):
        dist = max(dist, cfg["strike_k"] * spot * sig * math.sqrt(dte + 1))
    step = cfg["strike_step"]
    k = (math.floor((spot - dist) / step) * step) if side > 0 else (math.ceil((spot + dist) / step) * step)
    return {"strike": int(k), "sigma_daily": None if not np.isfinite(sig) else round(sig, 5), "dte": int(dte), "distance": round(dist, 1)}


def sl_definitions(side, entry, target, trig, area, mr, cfg, extreme_bars=12):
    """दोन SL व्याख्या (Abhi 2026-10-08 §4) — दोन्हींचा R:R अहवालात / chart वर:
      candle      reversal candle चं टोक: decision bar आणि आधीचा bar यांचं trade-विरुद्ध टोक + buffer (SIM 7 Oct: 22,648.8 ⇒ ~22,652)
      structural  idea जिथे चुकीची ठरते: active area (trendline / zone) च्या पलीकडे + buffer; area ला शिवणाऱ्या ताज्या टोकाने area
                  ओलांडला असेल तर ते टोक (7 Oct: trendline / 22,700–22,730 ⇒ ~22,735–22,740)
    trig = decision bar पर्यंतचे 15M bars. रिटर्न {"candle": {inv, ref, rr}, "structural": {inv, ref, rr} | None}."""
    buf = cfg["inv_buffer_mr"] * mr
    h, lo = trig["high"].to_numpy(float), trig["low"].to_numpy(float)
    out = {}
    cref = float(h[-2:].max()) if side < 0 else float(lo[-2:].min())
    out["candle"] = {"ref": round(cref, 2), "inv": round(cref + buf if side < 0 else cref - buf, 2)}
    out["structural"] = None
    if area is not None:
        edge = float(area["high"] if side < 0 else area["low"])
        rh, rl = h[-int(extreme_bars):], lo[-int(extreme_bars):]
        if side < 0 and rh.max() >= area["low"]:
            edge = max(edge, float(rh.max()))
        elif side > 0 and rl.min() <= area["high"]:
            edge = min(edge, float(rl.min()))
        out["structural"] = {"ref": round(edge, 2), "inv": round(edge + buf if side < 0 else edge - buf, 2)}
    for k, d in out.items():
        if d is not None and target is not None:
            risk = abs(entry - d["inv"])
            d["rr"] = round(abs(target - entry) / risk, 2) if risk > 0 and (d["inv"] - entry) * side < 0 else None
    return out


def validate(v, cand, tables, decision_start, ev, trig, s, daily_close=None, cfg=None):
    """रिटर्न {status: OK / REJECTED / NO_TRADE, reasons[], side, entry, inv, target, rr, area, strike}."""
    from chart_reader import evidence as EVD
    from chart_reader import rules as RU
    cfg = {**DEFAULTS, **(cfg or {})}
    mr = float(cand["mr"])
    out = {"status": "REJECTED", "reasons": [], "warnings": [], "side": 0, "entry": None, "inv": None, "inv_ref": None, "target": None,
           "rr": None, "area": None, "strike": None, "grade": v.get("grade"), "sl_defs": None}
    if not v.get("trade") or v.get("side") == "none":
        out["status"] = "NO_TRADE"
        return out
    side = 1 if v.get("side") == "bull_put" else -1
    out["side"] = side
    vals, errs = check_refs(v, tables, decision_start, mr, cfg)
    if errs:
        out["reasons"] = errs
        return out
    entry, inv_ref, tgt = vals["entry"][0], vals["invalidation"][0], vals["target"][0]
    inv = inv_ref + side * -1 * cfg["inv_buffer_mr"] * mr                # bull: low − buffer · bear: high + buffer
    out.update(entry=entry, inv=inv, inv_ref=inv_ref, target=tgt)
    if not ((inv < entry < tgt) if side > 0 else (tgt < entry < inv)):
        out["reasons"].append("बाजू विसंगत (bull: invalidation < entry < target; bear उलट)")
        return out
    rr = abs(tgt - entry) / abs(entry - inv)
    out["rr"] = round(rr, 2)
    area = next((z for z in cand["all_areas"] if z["id"] == v.get("area_id")), None)
    out["area"] = area
    if area is None:
        out["reasons"].append(f"area_id अज्ञात: {v.get('area_id')!r}")
    from pullback_credit_spread.signal import approached_from_trend_side
    approach = area is not None and approached_from_trend_side(trig, area, "LONG" if side > 0 else "SHORT", 20)
    hard = RU.check({"side": side, "bar_closed": True, "bar_end": cand["bar_end"], "approach_ok": approach,
                     "area_role": (area or {}).get("role"), "invalidation": inv, "entry": entry, "rr": rr, "gap_chase": False,
                     "risk_ok": True}, {**s, "min_rr": cfg["min_rr"]})
    out["reasons"] += hard
    out["sl_defs"] = sl_definitions(side, entry, tgt, trig, area, mr, cfg)
    st = out["sl_defs"].get("structural")
    if st is not None and (inv - st["inv"]) * side > 0.1 * mr and not str(v.get("invalidation_reason") or "").strip():
        out["warnings"].append(f"tight SL {inv:,.1f} (structural {st['inv']:,.1f}) — structural कारण दिलं नाही")
    if ev is not None and ev.get("structure"):
        out["reasons"] += EVD.vetoes(ev["structure"], ev.get("elliott") or {}, {"area": area}, (ev.get("areas") or {}).get("candidates") or [],
                                     ev.get("gap") or {}, side, trig, s, mr)
    if daily_close is not None and len(daily_close):
        out["strike"] = strike_info(side, entry, inv, mr, daily_close, cand["bar_end"], cfg)
    out["status"] = "OK" if not out["reasons"] else "REJECTED"
    return out


def hindsight(future15, side, entry, inv, target):
    """entry नंतरचे bars (फक्त अहवालासाठी — निर्णयात कधीच नाही). रिटर्न {result: TARGET / SL / OPEN, at, last_close}."""
    for r in future15.itertuples():
        hit_sl = (r.low <= inv) if side > 0 else (r.high >= inv)
        hit_tg = (r.high >= target) if side > 0 else (r.low <= target)
        if hit_sl:
            return {"result": "SL", "at": str(r.timestamp), "both_same_bar": bool(hit_tg)}
        if hit_tg:
            return {"result": "TARGET", "at": str(r.timestamp)}
    return {"result": "OPEN", "at": None, "last_close": None if not len(future15) else float(future15["close"].iloc[-1])}
