"""opportunity_engine/detectors/zone_pullback.py — D6 HTF_ZONE_PULLBACK_REVERSAL (spec §4, मुख्य "pullback संपला" setup). कुठलाही indicator नाही.

🎓 नियम (वापरकर्त्याने मंजूर केलेले डीफॉल्ट):
  • दिशा = primary HTF चा trend (UP ⇒ long, DOWN ⇒ short; RANGE/INIT ⇒ D6 नाही). Bias/gate चा निर्णय `bias.apply_gate` करतो — detector फक्त काय दिसलं ते सांगतो.
  • Zone (long; short आरशात): 1H/4H **FRESH किंवा TESTED_1** demand · flip zone (तुटलेला supply/resistance) ·
    primary HTF च्या शेवटच्या impulse leg (protected low → last swing high) चा **50–62%** retracement (शुद्ध किंमत, indicator नाही).
  • Zone ला स्पर्श: शेवटच्या `d6_touch_bars` (12 × 5M) मध्ये low ≤ zone high, आणि त्या bars चा एकही close zone low खाली नाही (zone टिकला).
  • Trigger (LTF structure shift):
      (अ) **15M bullish CHoCH** — याच 5M bar वर बंद झालेल्या 15M bar वर 15M tracker चा shift event
          (DOWNTREND चा protected high तुटला ⇒ `CHOCH`→DOWNTREND_WEAK, किंवा RECOVERY/REVERSAL_CONFIRMED/RANGE_EXIT_UP ⇒ UPTREND). Trigger bar = तो 15M bar.
      (आ) **5M reversal candle** (BULLISH_ENGULFING/HAMMER/MORNING_STAR) आणि पुढच्या 5M bar चा close त्या candle च्या high वर. Trigger bar = 5M.
  • SL: zone low (आणि स्पर्शाच्या bars चा सर्वात खालचा low — जे खाली असेल) पलीकडे; risk.py त्यावर `0.25 × ref_range` buffer लावतो. Gate HTF protected low तपासतो.
  • Target hints: primary HTF आणि 1H चा शेवटचा swing high (entry च्या वर असेल तर); पुढचा supply zone risk.py (nearest opposing) घेतो.
  • एक zone दिवसातून एकदाच.
"""
import pandas as pd

from signals import detect_candlestick_pattern

from ..context import trend_sign
from .base import Candidate, Detector, KIND_PULLBACK_END

GRADE_Q = {"A": 15.0, "B": 10.0, "C": 5.0}
FRESH_Q = {"FRESH": 10.0, "TESTED_1": 5.0}


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _minutes(ts):
    t = pd.Timestamp(ts)
    return t.hour * 60 + t.minute


def is_shift(event, sign):
    """15M event हा `sign` दिशेचा structure shift आहे का (long: bullish CHoCH / trend पुन्हा UP; short आरशात)."""
    et, to = event.get("type"), event.get("to_state")
    if sign > 0:
        return (et == "CHOCH" and to == "DOWNTREND_WEAK") or (et in ("RECOVERY", "REVERSAL_CONFIRMED", "RANGE_EXIT_UP") and to == "UPTREND")
    return (et == "CHOCH" and to == "UPTREND_WEAK") or (et in ("RECOVERY", "REVERSAL_CONFIRMED", "RANGE_EXIT_DOWN") and to == "DOWNTREND")


def candidate_zones(ctx, sign, cfg):
    """D6 zones (long: किंमतीखालचे/जवळचे support-सारखे; short आरशात). रिटर्न [{low, high, type, tf, key, level}] — level = मूळ level dict (retracement साठी None)."""
    price = ctx.price
    out = []
    for lv in ctx.levels:
        if lv.get("tf") not in cfg.d6_zone_tfs:
            continue
        kind, broken = lv.get("kind"), lv.get("status") == "BROKEN"
        if sign > 0:
            fresh_zone = kind == "DEMAND" and not broken and not lv.get("reject_reason") and lv.get("freshness") in ("FRESH", "TESTED_1")
            flip = kind in ("SUPPLY", "RESISTANCE") and broken
        else:
            fresh_zone = kind == "SUPPLY" and not broken and not lv.get("reject_reason") and lv.get("freshness") in ("FRESH", "TESTED_1")
            flip = kind in ("DEMAND", "SUPPORT") and broken
        if not (fresh_zone or flip):
            continue
        if price is not None and ((lv["low"] > price) if sign > 0 else (lv["high"] < price)):
            continue                                                   # long साठी zone किंमतीच्या वर असेल तर तो pullback zone नाही
        out.append({"low": float(lv["low"]), "high": float(lv["high"]), "type": "FLIP" if flip else kind, "tf": lv["tf"],
                    "key": lv.get("level_id") or f"{lv['tf']}:{kind}:{lv['low']:.2f}", "level": lv})
    st = ctx.get(cfg.primary_htf)
    if st is not None and st.sign == sign and not str(st.state).endswith("_WEAK") and st.protected is not None:
        lo_r, hi_r = cfg.d6_retrace
        if sign > 0 and st.last_sh is not None and st.last_sh > st.protected:
            leg = st.last_sh - st.protected
            out.append({"low": st.last_sh - hi_r * leg, "high": st.last_sh - lo_r * leg, "type": "RETRACE", "tf": cfg.primary_htf,
                        "key": f"RETRACE:{st.protected:.2f}:{st.last_sh:.2f}", "level": None})
        elif sign < 0 and st.last_sl is not None and st.last_sl < st.protected:
            leg = st.protected - st.last_sl
            out.append({"low": st.last_sl + lo_r * leg, "high": st.last_sl + hi_r * leg, "type": "RETRACE", "tf": cfg.primary_htf,
                        "key": f"RETRACE:{st.protected:.2f}:{st.last_sl:.2f}", "level": None})
    if price is not None:
        out.sort(key=lambda z: abs(price - (z["high"] if sign > 0 else z["low"])))
    return out


def _overlaps_retrace(z, zones):
    return z["type"] != "RETRACE" and any(r["type"] == "RETRACE" and r["low"] <= z["high"] and z["low"] <= r["high"] for r in zones)


class ZonePullback(Detector):
    """D6: HTF zone मध्ये pullback संपल्याचा LTF structure shift (15M CHoCH किंवा 5M reversal + trigger break) ⇒ trend-दिशेने entry."""
    setup_id = "D6"
    default_kind = KIND_PULLBACK_END

    def __init__(self, cfg, **kw):
        super().__init__(**kw)
        self.cfg = cfg

    def detect(self, ctx, bars_by_tf, bias, now):
        cfg = self.cfg
        mins = _minutes(now)
        if mins < _hm(cfg.d6_window_start) or mins > _hm(cfg.d6_window_end):
            return []
        df5, df15 = bars_by_tf["5m"], bars_by_tf["15m"]
        if len(df5) < 4:
            return []
        sign = trend_sign(ctx.state_name(cfg.primary_htf))
        if sign == 0:
            return []
        long = sign > 0
        row, prev = df5.iloc[-1], df5.iloc[-2]
        # --- trigger ---
        trig_type, trig = None, None
        shift = [e for e in bars_by_tf.get("ev15", ()) if e.get("time") == now and is_shift(e, sign)]
        if shift and len(df15) >= 2 and df15["bar_end"].iloc[-1] == now:
            b, pb = df15.iloc[-1], df15.iloc[-2]
            trig_type = "CHOCH_15M"
            trig = {"open": float(b["open"]), "high": float(b["high"]), "low": float(b["low"]), "close": float(b["close"]),
                    "prev_high": float(pb["high"]), "prev_low": float(pb["low"]), "ref_range": bars_by_tf.get("rr15"), "event": shift[0].get("type")}
        else:
            pat = detect_candlestick_pattern(df5.iloc[-4:-1])
            wanted = cfg.d2_patterns_long if long else cfg.d2_patterns_short
            if pat in wanted and ((row["close"] > prev["high"]) if long else (row["close"] < prev["low"])):
                trig_type = "CANDLE_5M"
                trig = {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]),
                        "prev_high": float(prev["high"]), "prev_low": float(prev["low"]), "ref_range": bars_by_tf.get("rr5"), "pattern": pat}
        if trig_type is None:
            return []
        # --- zone ---
        used = bars_by_tf["state"].setdefault("d6_used", set())
        win = df5.iloc[-cfg.d6_touch_bars:]
        w_low, w_high = float(win["low"].min()), float(win["high"].max())
        w_cmin, w_cmax = float(win["close"].min()), float(win["close"].max())
        entry = float(row["close"])
        zones = candidate_zones(ctx, sign, cfg)
        for z in zones:
            if z["key"] in used:
                continue
            touched = (w_low <= z["high"]) if long else (w_high >= z["low"])
            held = (w_cmin >= z["low"]) if long else (w_cmax <= z["high"])
            beyond = (entry > z["low"]) if long else (entry < z["high"])
            if not (touched and held and beyond):
                continue
            used.add(z["key"])
            sl_ref = min(z["low"], w_low) if long else max(z["high"], w_high)
            hints = []
            for tf in (cfg.primary_htf, "1h"):
                st = ctx.get(tf)
                v = None if st is None else (st.last_sh if long else st.last_sl)
                if v is not None and ((v > entry) if long else (v < entry)):
                    hints.append(float(v))
            lv = z["level"]
            quality = 50.0 + (GRADE_Q.get(lv.get("quality_grade"), 0.0) + FRESH_Q.get(lv.get("freshness"), 0.0) if lv else 5.0) + \
                (10.0 if trig_type == "CHOCH_15M" else 5.0) + (10.0 if _overlaps_retrace(z, zones) else 0.0)
            zone = dict(lv) if lv else {"kind": "RETRACE", "low": z["low"], "high": z["high"], "tf": z["tf"], "quality_grade": "—"}
            if z["type"] == "FLIP":
                zone["flipped"] = True
            return [Candidate(setup_id="D6", direction="LONG" if long else "SHORT", time=now, entry=entry, sl_ref=float(sl_ref), kind=KIND_PULLBACK_END,
                              tf="15m", trigger_tf="15m" if trig_type == "CHOCH_15M" else "5m", setup_quality=min(quality, 100.0), trigger=trig, zone=zone,
                              targets_hint=hints,
                              notes=[f"{z['tf']} {z['type']} zone {z['low']:,.0f}–{z['high']:,.0f} मध्ये pullback, {trig_type}"],
                              meta={"zone_type": z["type"], "zone_tf": z["tf"], "trigger_type": trig_type, "retrace_confluence": _overlaps_retrace(z, zones)})]
        return []
