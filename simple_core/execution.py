"""simple_core/execution.py — signal + execution settings (dashboard, प्रति bot / profile) ⇒ trade plan. Engine काहीच गृहीत धरत नाही.

Settings (default नाही; निवडलेलं नसेल ⇒ trade नाही + स्पष्ट संदेश):
  sl_mode       structural_invalidation / commitment_extreme / wave1_origin (G1) / subwave_origin (G8) / wave1_extreme (G9) /
                fixed_points / percent / none  (+ sl_buffer, sl_buffer_unit points / mr, sl_value — fixed_points ⇒ points, percent ⇒ %)
  target_mode   next_opposite_area / impulse_end / wave3_projection / wave5_projection / r_multiple / premium_pct / none
                (+ target_value — r_multiple ⇒ R, premium_pct ⇒ %). Wave levels signal च्या ref_levels मधून; count gray ⇒ trade नाही + कारण.
  g9_tier       G9 (wave 5, KB Tier C): "C" ⇒ g9_lots, "skip" ⇒ trade नाही. G9 signal वर निवडलेलं नसेल ⇒ trade नाही.
  rr_filter     true / false (+ min_rr)
  instrument    credit_spread / futures / naked_buy / naked_sell
  strike_mode   offset_points / beyond_sl_points / sigma (options साठी) + strike_value + strike_step; width (credit_spread); lots;
                expiry_rule (मजकूर). sigma ⇒ caller sigma_px (σ points) देतो.
Plan मध्ये settings hash (version) नोंद. premium_pct target spot वर मोजता येत नाही ⇒ spot target नाही (नोंद).
"""
import math

from . import settings as SS

REF_SL = ("structural_invalidation", "commitment_extreme", "wave1_origin", "subwave_origin", "wave1_extreme")
REF_TARGET = ("next_opposite_area", "impulse_end", "wave3_projection", "wave5_projection")
MSG = {"sl_mode": "SL mode निवडलेला नाही", "target_mode": "Target mode निवडलेला नाही", "rr_filter": "R:R filter (on / off) निवडलेला नाही",
       "instrument": "Instrument निवडलेलं नाही", "lots": "Lots / risk निवडलेले नाहीत"}


def _missing(ex, key):
    return ex.get(key) is None or ex.get(key) == ""


def _truthy(v):
    """bool / "true" / "on" / 1 ⇒ True; "false" / "off" / 0 ⇒ False (string "false" चुकून on नाही)."""
    return v is True or str(v).strip().lower() in ("true", "1", "on", "yes")


def _buffer(ex, mr):
    """SL buffer points मध्ये; unit "mr" आणि MR नाही / NaN ⇒ None (शांतपणे 0 नाही)."""
    b = float(ex.get("sl_buffer") or 0.0)
    if ex.get("sl_buffer_unit") == "mr":
        if mr is None or not math.isfinite(float(mr)):
            return None
        return b * float(mr)
    return b


def plan(sig, ex, mr=None, sigma_px=None, spot_only=False):
    """रिटर्न {ok, reason, side, entry, sl, target, rr, instrument, strike, width, lots, expiry_rule, settings_hash}.
    spot_only (K-10 / review अहवाल): फक्त spot SL / target / R:R — instrument / lots / strike तपासत नाही (order नाही)."""
    ex = dict(ex or {})
    out = {"ok": False, "reason": "", "side": sig.get("side"), "entry": sig.get("trigger_price"), "sl": None, "target": None, "rr": None,
           "instrument": ex.get("instrument"), "strike": None, "width": ex.get("width"), "lots": ex.get("lots"),
           "expiry_rule": ex.get("expiry_rule"), "settings_hash": SS.settings_hash(ex), "settings": ex}
    for key in ("sl_mode", "target_mode", "rr_filter") + (() if spot_only else ("instrument", "lots")):
        if _missing(ex, key):
            out["reason"] = MSG[key]
            return out
    if ex["sl_mode"] not in SS.SL_MODES or ex["target_mode"] not in SS.TARGET_MODES:
        out["reason"] = f"अज्ञात sl_mode / target_mode ({ex['sl_mode']!r} / {ex['target_mode']!r})"
        return out
    side, entry, ref = int(sig["side"]), float(sig["trigger_price"]), sig.get("ref_levels") or {}
    notes = sig.get("ref_notes") or {}
    if sig.get("setup") == "G9" or (sig.get("wave") or {}).get("setup") == "G9":   # flag (G8) label असला तरी wave G9 ⇒ Tier C
        if _missing(ex, "g9_tier"):
            out["reason"] = "G9 (wave 5, Tier C): g9_tier निवडलेला नाही"
            return out
        if ex["g9_tier"] == "skip":
            out["reason"] = "G9: g9_tier = skip ⇒ trade नाही"
            return out
        if _missing(ex, "g9_lots") and not spot_only:
            out["reason"] = "G9 Tier C: g9_lots निवडलेले नाहीत"
            return out
        out.update(lots=ex.get("g9_lots"), tier="C")
    m = ex["sl_mode"]
    if m in REF_SL:
        base = ref.get(m)
        if base is None:
            out["reason"] = f"SL: signal मध्ये {m} नाही" + (f" ({notes[m]})" if notes.get(m) else "")
            return out
        if _missing(ex, "sl_buffer") or _missing(ex, "sl_buffer_unit"):
            out["reason"] = "SL buffer / unit निवडलेले नाहीत"
            return out
        bufpts = _buffer(ex, mr)
        if bufpts is None:
            out["reason"] = "SL buffer MR मध्ये, पण MR उपलब्ध नाही"
            return out
        sl = float(base) - side * bufpts                                   # bear ⇒ वर, bull ⇒ खाली
    elif m in ("fixed_points", "percent"):
        if _missing(ex, "sl_value"):
            out["reason"] = f"SL value ({m}) निवडलेली नाही"
            return out
        d = float(ex["sl_value"]) if m == "fixed_points" else entry * float(ex["sl_value"]) / 100.0
        sl = entry - side * d
    else:
        sl = None
    if sl is not None and (entry - sl) * side <= 0:
        out["reason"] = f"SL {sl:,.1f} entry च्या चुकीच्या बाजूला"
        return out
    out["sl"] = None if sl is None else round(sl, 2)
    t = ex["target_mode"]
    if t in REF_TARGET:
        tg = ref.get(t)
        if tg is None:
            out["reason"] = f"Target: signal मध्ये {t} नाही" + (f" ({notes[t]})" if notes.get(t) else "")
            return out
        tg = float(tg)
    elif t == "r_multiple":
        if _missing(ex, "target_value") or sl is None:
            out["reason"] = "Target r_multiple: target_value / SL हवा"
            return out
        tg = entry + side * float(ex["target_value"]) * abs(entry - sl)
    else:
        tg = None                                                          # premium_pct (option premium वर) / none ⇒ spot target नाही
        if t == "premium_pct" and _missing(ex, "target_value"):
            out["reason"] = "Target premium_pct: target_value निवडलेली नाही"
            return out
    if tg is not None and (tg - entry) * side <= 0:
        out["reason"] = f"Target {tg:,.1f} entry च्या चुकीच्या बाजूला ({t})"
        return out
    out["target"] = None if tg is None else round(tg, 2)
    if sl is not None and tg is not None:
        risk = abs(entry - sl)
        out["rr"] = round(abs(tg - entry) / risk, 2) if risk > 0 else None
    if _truthy(ex["rr_filter"]):
        if _missing(ex, "min_rr"):
            out["reason"] = "R:R filter on, पण min_rr निवडलेला नाही"
            return out
        if out["rr"] is None or out["rr"] < float(ex["min_rr"]):
            out["reason"] = f"R:R {out['rr']} < {ex['min_rr']} (rr_filter)"
            return out
    if not spot_only and ex["instrument"] in ("credit_spread", "naked_sell", "naked_buy"):
        if _missing(ex, "strike_mode") or _missing(ex, "strike_value") or _missing(ex, "strike_step"):
            out["reason"] = "Options: strike mode / value / step निवडलेले नाहीत"
            return out
        if ex["instrument"] == "credit_spread" and _missing(ex, "width"):
            out["reason"] = "Credit spread: width निवडलेली नाही"
            return out
        out["strike"] = strike(sig, ex, sl, step=float(ex["strike_step"]), sigma_px=sigma_px)
        if out["strike"] is None:
            out["reason"] = "strike मोजता आला नाही (sigma ⇒ daily closes हवे / beyond_sl ⇒ SL हवा)"
            return out
    out["ok"] = True
    out["reason"] = "OK"
    return out


def strike(sig, ex, sl, step, sigma_px=None):
    """Short strike (bear call ⇒ वर, bull put ⇒ खाली), step च्या पटीत. offset_points: trigger ± value · beyond_sl_points: SL ± value ·
    sigma: trigger ± value × σ (points; caller देतो — उदा. daily closes वरून; नसेल ⇒ None). step = settings strike_step."""
    side, entry, v = int(sig["side"]), float(sig["trigger_price"]), float(ex["strike_value"])
    m = ex["strike_mode"]
    if m == "offset_points":
        px = entry - side * v
    elif m == "beyond_sl_points":
        if sl is None:
            return None
        px = sl - side * v
    else:
        if sigma_px is None:
            return None
        px = entry - side * v * float(sigma_px)
    return int((math.ceil(px / step) if side < 0 else math.floor(px / step)) * step)


def simulate(p, after, max_sessions=3):
    """Spot वर hindsight (backtest / visual review — settings तुलना): SL / target आधी (एकाच bar मध्ये दोन्ही ⇒ SL), नाहीतर TIME."""
    if not p.get("ok"):
        return {"result": "NO_TRADE", "reason": p.get("reason")}
    import pandas as pd
    side, entry, sl, tg = int(p["side"]), float(p["entry"]), p.get("sl"), p.get("target")
    d = after.copy()
    days = pd.to_datetime(d["timestamp"]).dt.normalize().unique()[:int(max_sessions)]
    d = d[pd.to_datetime(d["timestamp"]).dt.normalize().isin(days)]
    mfe = mae = 0.0
    for r in d.itertuples():
        mfe = max(mfe, (entry - r.low) if side < 0 else (r.high - entry))
        mae = max(mae, (r.high - entry) if side < 0 else (entry - r.low))
        if sl is not None and ((r.high >= sl) if side < 0 else (r.low <= sl)):
            return {"result": "SL", "at": str(r.timestamp), "exit": sl, "mfe": round(mfe, 2), "mae": round(mae, 2)}
        if tg is not None and ((r.low <= tg) if side < 0 else (r.high >= tg)):
            return {"result": "TARGET", "at": str(r.timestamp), "exit": tg, "mfe": round(mfe, 2), "mae": round(mae, 2)}
    last = float(d["close"].iloc[-1]) if len(d) else None
    return {"result": "TIME", "at": None if not len(d) else str(d["timestamp"].iloc[-1]), "exit": last, "mfe": round(mfe, 2),
            "mae": round(mae, 2)}
