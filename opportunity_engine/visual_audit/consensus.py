"""opportunity_engine/visual_audit/consensus.py — Dual-Eye Consensus: गणिताचे levels (§2.6) + vision model ची नजर (§17.8). Pure (DB/API नाही).

🎓 वर्ग (प्रत्येक audit केलेल्या zone-level साठी):
  • CONSENSUS — grade A/B **आणि** (model verdict VALID **किंवा** स्वतंत्र visual पट्टा outer band ला छेदतो), आणि model ने SPURIOUS/SHIFT म्हटलेलं नाही.
  • MATH_ONLY — model ने SPURIOUS ठरवलं, किंवा visual कडून पुष्टी नाही (grade C चा VALID सुद्धा — spec नुसार CONSENSUS फक्त A/B).
  • CONFLICT — model ने SHIFT_UP/SHIFT_DOWN सांगितलं: त्या दिशेने (≤ 2 × zone उंची) सर्वात जवळचा §2.6 zone शोधला जातो — सापडला तर तो CONSENSUS उमेदवार
    (मूळ level MATH_ONLY म्हणून वागतो), नाहीतर मूळ MATH_ONLY.
  • VISUAL_ONLY — स्वतंत्र visual पट्टा ज्यात audit केलेला math level नाही: त्या पट्ट्यात §2.6 body-cluster/origin zone सापडला तर grade C level म्हणून, नाहीतर टाकला.
  • वापरकर्त्याचा feedback प्राधान्याने: WRONG ⇒ REJECT (level काढला), CORRECT ⇒ CONSENSUS.
Modes: off (फक्त माहिती; levels बदलत नाहीत) · score (levels वर `consensus` टॅग; scoring मध्ये CONSENSUS +10 / MATH_ONLY −10; VISUAL_ONLY/उमेदवार जोडले) ·
gate (zone-levels पैकी फक्त CONSENSUS; KEY/GAP/ROUND हे अचूक तथ्य — audit होत नाहीत — तसेच राहतात). Visual run नसेल तर gate ⇒ त्या दिवशी score (fallback).
"""
from .auditor import snap_band
from .render import ZONE_KINDS

CONSENSUS, MATH_ONLY, CONFLICT, VISUAL_ONLY, REJECT = "CONSENSUS", "MATH_ONLY", "CONFLICT", "VISUAL_ONLY", "REJECT"


def _outer(z):
    return float(z.get("outer_low", z["low"])), float(z.get("outer_high", z["high"]))


def _intersects(band, z):
    lo, hi = _outer(z)
    return not (float(band["approx_high"]) < lo or float(band["approx_low"]) > hi)


def _shift_target(lv, direction, candidates):
    """SHIFT दिशेने (≤ 2 × outer उंची) मध्य असलेला सर्वात जवळचा zone (lv स्वतः नाही)."""
    lo, hi = _outer(lv)
    mid, h = (lo + hi) / 2.0, max(hi - lo, 1e-9)
    best, best_d = None, None
    for z in candidates:
        if z.get("level_id") == lv.get("level_id") or z.get("kind") not in ZONE_KINDS or z.get("status") == "BROKEN":
            continue
        zl, zh = _outer(z)
        d = ((zl + zh) / 2.0 - mid) * (1 if direction > 0 else -1)
        if 0 < d <= 2.0 * h and (best_d is None or d < best_d):
            best, best_d = z, d
    return best


def match_label(lab, levels, by_id):
    """label -> दिवसाचा level: आधी level_id; नसेल तर (forward testing — live run आणि नंतरच्या backtest ची डेटा-खिडकी वेगळी असल्याने id बदलू शकतो)
    त्याच kind + TF चा, outer band सर्वात जास्त overlap होणारा (≥ 50% लहान पट्ट्याच्या) level."""
    lv = by_id.get(lab.get("level_id"))
    if lv is not None or lab.get("outer_low") is None or lab.get("outer_high") is None:
        return lv
    lo, hi = float(lab["outer_low"]), float(lab["outer_high"])
    best, best_ov = None, 0.0
    for z in levels:
        if z.get("kind") != lab.get("kind") or (lab.get("tf") and z.get("tf") != lab.get("tf")) or not z.get("level_id"):
            continue
        zl, zh = _outer(z)
        ov = min(hi, zh) - max(lo, zl)
        need = 0.5 * max(min(hi - lo, zh - zl), 1e-9)
        if ov >= need and ov > best_ov:
            best, best_ov = z, ov
    return best


def _as_c(z, tag):
    out = dict(z)
    out.update({"quality_grade": "C", "reject_reason": None, "consensus": tag, "visual_source": True})
    return out


def classify(levels, pool, records, feedback=None):
    """levels = दिवसाचे levels (KEY/GAP/flips सकट), pool = नाकारलेले (LOW_SCORE) zones (snap साठी), records = त्या तारखेचे audit records (प्रत्येक TF एक),
    feedback = {level_id: CORRECT|WRONG|SHIFT}. रिटर्न dict: classes {level_id: {class, verdict, reason, tf}}, added [level dicts], visual_rows [..]."""
    feedback = feedback or {}
    by_id = {z["level_id"]: z for z in levels if z.get("level_id")}
    everything = list(levels) + list(pool or [])
    classes, added, visual_rows = {}, [], []
    added_ids = set()
    for rec in records or []:
        ov = rec.get("overlay") or {}
        ind = rec.get("independent") or {}
        verdicts = {v["label"]: v for v in ((ov.get("data") or {}).get("verdicts") or [])} if ov.get("status") == "OK" else {}
        zones = (ind.get("data") or {}).get("zones") or [] if ind.get("status") == "OK" else []
        if not verdicts and not zones:
            continue                                                       # या chart चं वाचन अयशस्वी — माहिती नाही
        labelled = []
        for lab in rec.get("labels") or []:
            lv = match_label(lab, levels, by_id)
            if lv is None:
                continue
            labelled.append(lv)
            v = verdicts.get(lab["label"], {})
            verdict = v.get("verdict")
            inter = any(_intersects(z, lv) for z in zones)
            if verdict in ("SHIFT_UP", "SHIFT_DOWN"):
                cls = CONFLICT
                tgt = _shift_target(lv, 1 if verdict == "SHIFT_UP" else -1, everything)
                if tgt is not None and tgt["level_id"] not in added_ids:
                    if tgt["level_id"] in by_id:
                        classes.setdefault(tgt["level_id"], {"class": CONSENSUS, "verdict": None, "reason": f"{lab['label']} चा SHIFT", "tf": rec.get("tf")})
                    else:
                        added.append(_as_c(tgt, CONSENSUS))
                        added_ids.add(tgt["level_id"])
            elif verdict == "SPURIOUS":
                cls = MATH_ONLY
            elif lv.get("quality_grade") in ("A", "B") and (verdict == "VALID" or inter):
                cls = CONSENSUS
            else:
                cls = MATH_ONLY
            classes[lv["level_id"]] = {"class": cls, "verdict": verdict, "reason": v.get("reason"), "tf": rec.get("tf")}
        for z in zones:
            hit = next((lv for lv in labelled if _intersects(z, lv)), None)
            if hit is not None:
                visual_rows.append({**z, "tf": rec.get("tf"), "matched_level_id": hit["level_id"], "consensus_class": classes.get(hit["level_id"], {}).get("class")})
                continue
            snapped = snap_band(z["approx_low"], z["approx_high"], everything, exclude_ids={lv["level_id"] for lv in labelled})
            if snapped is not None and snapped.get("status") != "BROKEN":
                if snapped["level_id"] in by_id and snapped["level_id"] not in classes:
                    classes[snapped["level_id"]] = {"class": VISUAL_ONLY, "verdict": None, "reason": z.get("reason"), "tf": rec.get("tf")}
                elif snapped["level_id"] not in by_id and snapped["level_id"] not in added_ids:
                    added.append(_as_c(snapped, VISUAL_ONLY))
                    added_ids.add(snapped["level_id"])
                visual_rows.append({**z, "tf": rec.get("tf"), "matched_level_id": snapped["level_id"], "consensus_class": VISUAL_ONLY})
            else:
                visual_rows.append({**z, "tf": rec.get("tf"), "matched_level_id": None, "consensus_class": None})
    for lid, fb in feedback.items():                                       # वापरकर्त्याचा निर्णय सर्वात वर
        if fb == "WRONG":
            classes[lid] = {**classes.get(lid, {}), "class": REJECT, "user": fb}
        elif fb == "CORRECT":
            classes[lid] = {**classes.get(lid, {}), "class": CONSENSUS, "user": fb}
    return {"classes": classes, "added": added, "visual_rows": visual_rows}


def apply(levels, pool, records, mode="off", feedback=None):
    """mode नुसार दिवसाचे levels. रिटर्न (levels, info) — info: classes, counts, fallback (gate पण visual run नाही ⇒ score)."""
    info = {"mode": mode, "fallback": False, "counts": {}}
    if mode == "off":
        return levels, info
    have = any(((r.get("overlay") or {}).get("status") == "OK") or ((r.get("independent") or {}).get("status") == "OK") for r in records or [])
    if not have and not feedback:
        if mode == "gate":
            info["fallback"] = True
            mode = "score"
        info["mode_used"] = mode
        return levels, info                                                 # माहिती नाही ⇒ levels तसेच (score मध्ये टॅग नाही ⇒ बदल नाही)
    res = classify(levels, pool, records, feedback)
    classes = res["classes"]
    out = []
    for lv in levels:
        c = classes.get(lv.get("level_id"), {}).get("class")
        if c == REJECT:
            continue
        tag = CONSENSUS if c == CONSENSUS else MATH_ONLY if c in (MATH_ONLY, CONFLICT) else VISUAL_ONLY if c == VISUAL_ONLY else None
        if mode == "gate" and lv.get("kind") in ZONE_KINDS and tag != CONSENSUS:
            continue
        out.append({**lv, "consensus": tag} if tag else lv)
    for z in res["added"]:
        if mode == "gate" and z["consensus"] != CONSENSUS:
            continue
        out.append(z)
    counts = {}
    for v in classes.values():
        counts[v["class"]] = counts.get(v["class"], 0) + 1
    counts["ADDED"] = len(res["added"])
    info.update({"classes": classes, "counts": counts, "mode_used": mode, "visual_rows": res["visual_rows"]})
    return out, info


def summary_text(symbol, rec, classes):
    """Telegram साठी एक ओळ: "NIFTY 1H: 7 levels → 5 VALID, 1 SPURIOUS (L3: spike), 1 SHIFT. 1 missing भाग 24,610–24,650." """
    ov = rec.get("overlay") or {}
    tf = str(rec.get("tf", "")).upper()
    if ov.get("status") != "OK":
        return f"{symbol} {tf}: audit {ov.get('status', 'FAILED')} ({ov.get('error') or '—'})"
    vs = ov["data"]["verdicts"]
    n = {k: sum(v["verdict"] == k for v in vs) for k in ("VALID", "SPURIOUS", "SHIFT_UP", "SHIFT_DOWN")}
    spur = [f"{v['label']}: {v['reason']}" for v in vs if v["verdict"] == "SPURIOUS"][:2]
    parts = [f"{symbol} {tf}: {len(vs)} levels → {n['VALID']} VALID, {n['SPURIOUS']} SPURIOUS" + (f" ({'; '.join(spur)})" if spur else "") +
             f", {n['SHIFT_UP'] + n['SHIFT_DOWN']} SHIFT."]
    miss = ov["data"].get("missing") or []
    if miss:
        parts.append(f"{len(miss)} missing भाग " + ", ".join(f"{m['approx_low']:,.0f}–{m['approx_high']:,.0f}" for m in miss[:3]) + ".")
    cons = sum(1 for c in classes.values() if c.get("class") == CONSENSUS and c.get("tf") == rec.get("tf"))
    parts.append(f"CONSENSUS: {cons}.")
    return " ".join(parts)
