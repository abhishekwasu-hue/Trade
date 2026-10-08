"""chart_reader/grade.py — पुरावे (evidence) ⇒ गुण ⇒ A / B / C (code pre-grade). KB भाग D चा तक्ता.

🎓 Abhi चा दृष्टिकोन (KB A2): trading probability वर चालतं; कुठलाच एक घटक निर्णय घेत नाही. प्रत्येक पुराव्याचे + / − गुण आधी ठरवलेले
(settings), आणि प्रत्येकाची एक ओळ (chapter tag सह) log / narrative मध्ये. पक्के नियम (breakout नाही, बंद candle, invalidation,
R:R ≥ 3, risk) इथे नाहीत — ते `rules.py` मध्ये.

तक्ता (KB भाग D; ✚ = Knowledge Base ने जोडलेले, गुण `evidence.py` / `volume.py` कडून, इथे फक्त कमाल-किमान मर्यादा):
  T [K1] −20…+15 · ✚PB [K2] −15…+10 · CW [K10] 0…15 · AQ [K4/K6/K8] 0…20 · CF [K7] 0…10 · ✚LQ [K5] 0…8 · RV [K9] −10…+25 ·
  ✚VL [K10.3] −5…+5 · ✚DV [K10.2] −3…+5 · ✚PT [K11] −10…+5 · GP [K13] ±10 · EW [K3] −15…+10 · RM [A3] 0…5 · ✚TM [K14] −5…0 ·
  ✚VX [K14] −5…+2 · EV [K13] −5…0.   Grade: A ≥ 60 · B 45–59 · C < 45 (Abhi ने मंजूर; बदल फक्त Abhi).
A3 चे व्याख्यात्मक व्हेटो (ev["vetoes"], score च्या बाहेर) ⇒ grade C, गुण कितीही असोत. S6a / S13 (B-end → C) setting
`c_wave_setups_enabled` (default OFF ⇒ C; ON ⇒ counter-trend −20 नाही, Tier B).
Counter-move impulsive (5 waves / displacement) ⇒ PB −10 (पुरावा); structure अशा वेळी entry point देत नाही ⇒ entry नाही.
"""
import numpy as np

KEYS = ("T", "PB", "CW", "AQ", "CF", "LQ", "RV", "VL", "DV", "PT", "GP", "EW", "RM", "TM", "VX", "EV")
KB_KEYS = {"PB": (-15.0, 10.0), "LQ": (0.0, 8.0), "VL": (-5.0, 5.0), "DV": (-3.0, 5.0), "PT": (-10.0, 5.0), "TM": (-5.0, 0.0),
           "VX": (-5.0, 2.0)}
TAGS = {"T": "K1", "PB": "K2", "CW": "K10", "AQ": "K4/K6/K8", "CF": "K7", "LQ": "K5", "RV": "K9", "VL": "K10.3", "DV": "K10.2",
        "PT": "K11", "GP": "K13", "EW": "K3", "RM": "A3", "TM": "K14", "VX": "K14", "EV": "K13"}


def rv_points(s_val, s=None):
    from .settings import DEFAULTS
    s = s or DEFAULTS
    if s_val is None or not np.isfinite(s_val):
        return float(s["rv_min"])
    v = s["rv_scale"] * (float(s_val) - s["rv_zero"])
    return float(round(min(max(v, s["rv_min"]), s["rv_max"]), 2))


def reversal_label(s_val, s=None):
    from .settings import DEFAULTS
    s = s or DEFAULTS
    if s_val is None:
        return "none"
    return "strong" if s_val >= s["rev_label_strong"] else "medium" if s_val >= s["rev_label_medium"] else "weak"


def grade_of(total, s):
    return "A" if total >= s["grade_a_min"] else "B" if total >= s["grade_b_min"] else "C"


def _trend(ev, s):
    side, htf, st = ev["side"], ev.get("htf"), ev.get("trend_strength")
    if htf == "range":
        return (s["w_trend_range_edge"], "trend range — range edge वरून") if ev.get("at_range_edge") else (0.0, "trend range — edge नाही")
    hdir = 1 if htf == "up" else -1 if htf == "down" else 0
    if hdir == 0:
        return 0.0, "HTF trend अस्पष्ट"
    if hdir == side:
        if st == "strong":
            return s["w_trend_strong"], f"HTF {htf} आणि मजबूत — trend दिशेने entry"
        return s["w_trend_weakening"], f"HTF {htf} पण {st or 'अस्पष्ट'} — trend दिशेने entry"
    if ev.get("elliott_setup") in s["c_wave_setups"] and s.get("c_wave_setups_enabled"):
        return 0.0, f"HTF {htf} विरुद्ध, पण Elliott C-wave setup {ev['elliott_setup']} (Tier B) ⇒ counter-trend दंड नाही"
    return s["w_trend_counter"], f"HTF {htf} विरुद्ध (counter-trend, Elliott C-wave setup नाही)"


def _line(k, v, why):
    return f"{k} {v:+g} [{TAGS[k]}]: {why}"


def score(ev, s):
    """रिटर्न {points{KEY: गुण}, lines[] (KEYS क्रमाने), total, grade, size_mult, tier, vetoes}."""
    pts, why = {}, {}
    pts["T"], why["T"] = _trend(ev, s)
    cw = float(np.clip(ev.get("correction_weakening") or 0.0, 0, 1))
    pts["CW"], why["CW"] = round(s["w_correction_weakening"] * cw, 2), f"correction कमकुवत होण्याचे पुरावे {cw:.2f}"
    aq = float(np.clip(ev.get("area_quality") or 0.0, 0, 1))
    pts["AQ"], why["AQ"] = round(s["w_area_quality"] * aq, 2), f"area गुणवत्ता {aq:.2f}"
    cf = min(int(ev.get("confluence_extra") or 0), int(s["confluence_max_extra"]))
    pts["CF"], why["CF"] = s["w_confluence_each"] * cf, f"confluence अतिरिक्त प्रकार {cf} (मोजपट्टी फक्त ठोस area सोबत)"
    rs = ev.get("reversal_s")
    pts["RV"], why["RV"] = rv_points(rs, s), f"reversal s = {'—' if rs is None else f'{rs:.2f}'} ({reversal_label(rs, s)})"
    g = ev.get("gap") or "neutral"
    pts["GP"] = s["w_gap_confirms"] if g == "confirms" else s["w_gap_opposes"] if g == "opposes" else 0.0
    why["GP"] = f"gap {g}"
    e = ev.get("elliott") or "none"
    pts["EW"] = s["w_elliott_end"] if e == "end" else s["w_elliott_bad"] if e == "a_end_or_in_b" else 0.0
    why["EW"] = f"Elliott {e}" + (f" ({ev['elliott_setup']})" if ev.get("elliott_setup") else "") + (
        " — count gray ⇒ फक्त शक्यता, व्हेटो नाही" if e == "a_end_or_in_b" and not ev.get("elliott_clear") else "")
    rr = ev.get("rr")
    pts["RM"] = s["w_rr_bonus"] if rr is not None and rr >= s["rr_bonus_min"] else 0.0
    why["RM"] = f"spot R:R {'—' if rr is None else f'{rr:.1f}'}"
    pts["EV"] = s["w_event_day"] if ev.get("event_day") else 0.0
    why["EV"] = f"event दिवस {'हो' if ev.get('event_day') else 'नाही'}"
    kb = ev.get("kb") or {}
    for k, (lo, hi) in KB_KEYS.items():
        r = kb.get(k) or {}
        pts[k] = float(np.clip(float(r.get("pts") or 0.0), lo, hi))
        why[k] = (r.get("line") or f"{k} 0: —").split(": ", 1)[-1]
    pts = {k: (int(v) if float(v).is_integer() else v) for k, v in pts.items()}
    lines = [_line(k, pts[k], why[k]) for k in KEYS]
    raw = float(sum(pts[k] for k in KEYS))
    total = float(min(max(raw, 0.0), 100.0))
    grade = grade_of(total, s)
    vetoes = list(ev.get("vetoes") or [])
    if ev.get("elliott_setup") in s["c_wave_setups"] and not s.get("c_wave_setups_enabled"):
        vetoes.append(f"⛔ {ev['elliott_setup']} (B-end → C) setup बंद (setting c_wave_setups_enabled)")
    if vetoes:
        grade = "C"
        lines += [f"{v} ⇒ C" for v in vetoes]
    tier = ev.get("tier") or ("A" if pts["T"] > 0 or ev.get("htf") == "range" else "B")
    size = 0.0 if grade == "C" else float(s["tier_mult"][tier])
    total = int(total) if total.is_integer() else round(total, 2)
    return {"points": pts, "lines": lines, "raw": raw, "total": total, "grade": grade, "tier": tier, "size_mult": size, "vetoes": vetoes}
