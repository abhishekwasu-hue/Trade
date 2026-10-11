"""vision2/veto.py — थर 7 §8: vision = **फक्त veto, कधीच promote नाही**. इथे कोणताही API call नाही (paid call फक्त Abhi च्या मंजुरीने,
model + `run_vision_budget` Abhi ठरवतो). हा module: कधी विचारायचं, काय पाठवायचं (payload), आणि उत्तर `decision` वर कसं लावायचं.

नियम: gate items (4, 5, 6, 9, 10, 12) वर vision ✘ ⇒ setup → no_trade(vision:<item>); vision ✔ / ✏️ कधीच wait / no_trade ⇒ setup नाही;
evidence items (1, 7, 8, 11) ⇒ फक्त grade; ✏️ मधली कोणतीही किंमत dropped; vision fail ⇒ `vision_fail_action`. Vision कधीच order / exit
block / किंमत नाही.
"""
import copy
import re

GATE_ITEMS = (4, 5, 6, 9, 10, 12)
EVIDENCE_ITEMS = (1, 7, 8, 11)
CONTEXT_ITEMS = (2, 3)
CHECKLIST = {1: "Weekly + Daily स्थिती, मोठे areas", 2: "1H trend, protected swing, impulse", 3: "Impulse खरा",
             4: "Pullback = correction, reversal नाही", 5: "Pattern (labels)", 6: "Pattern पूर्ण / position",
             7: "Area (zone / रेघ / confluence; Fib फक्त area सोबत)", 8: "खोली", 9: "Price failure बंद candle वर",
             10: "Risk (invalidation, target, R:R ≥ 3)", 11: "संदर्भ (gap, वेळ, expiry, event, VIX)", 12: "पक्के नियम"}
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def should_call(dec, manual=False):
    """setup, किंवा grade ≥ B चा wait, किंवा Abhi चा manual "मला trade दिसतोय"."""
    if manual:
        return True
    return dec.get("decision") == "setup" or (dec.get("decision") == "wait" and dec.get("grade") in ("A", "B"))


MODEL_TASK = "veto"            # model नाव फक्त VPS env मध्ये: VISION_VETO_MODEL (vision.config.env_model); Abhi default = Sonnet वर्ग


def run_budget(g):
    """run_vision_budget (Abhi उत्तर 15 default): नवी रक्कम नाही — सध्याच्या vision_daily_budget_usd मधली visual_audit_daily_cap उप-मर्यादा;
    महिना vision_monthly_budget_usd (default $60) तसाच. g = vision.config global settings."""
    if g is None:
        return None
    return min(float(g["visual_audit_daily_cap"]), float(g["vision_daily_budget_usd"]))


def budget_ok(spent, cap):
    """run_vision_budget (replay साठी वेगळा; live vision_* reserve ला हात नाही)."""
    return cap is not None and spent < cap


def payload(dec, chart_paths, macro=None):
    """Vision ला काय: थर 1–6 charts (paths) + decision JSON + macro row + 12-मुद्दे checklist. किंमती image वरून नाहीत."""
    return {"charts": list(chart_paths), "decision": dec, "macro": macro,
            "checklist": [{"item": k, "text": v, "kind": "gate" if k in GATE_ITEMS else ("evidence" if k in EVIDENCE_ITEMS else "context")}
                          for k, v in CHECKLIST.items()],
            "answer_format": {"items": "{n: '✔' | '✘' | '✏️'}", "overall": "agree / disagree / unclear", "why": "मजकूर",
                              "rule_ids": "v2_disagree_rules / v2_gray_rules"},
            "rules": "labels फक्त; किंमत लिहू नका; order / exit बद्दल काही नाही"}


def sanitize(v):
    """✏️ / why मधल्या किंमती (अंक) काढा."""
    out = copy.deepcopy(v or {})
    for k in ("why", "notes"):
        if isinstance(out.get(k), str):
            out[k] = NUM.sub("…", out[k])
    edits = out.get("edits") or {}
    out["edits"] = {k: NUM.sub("…", str(x)) for k, x in edits.items()}
    return out


def apply(dec, v, s):
    """vision उत्तर `decision` वर लावा (veto-only). v = None ⇒ vision fail."""
    out = copy.deepcopy(dec)
    out["vision"] = None
    if v is None:
        out["vision"] = {"status": "fail", "action": s["vision_fail_action"]}
        if s["vision_fail_action"] == "wait" and out.get("decision") == "setup":
            out["decision"], out["gate"] = "wait", "vision:fail"
        return out
    v = sanitize(v)
    items = {int(k): x for k, x in (v.get("items") or {}).items()}
    out["vision"] = {"status": "ok", "items": items, "overall": v.get("overall"), "why": v.get("why"), "rule_ids": v.get("rule_ids")}
    if out.get("decision") == "setup":
        bad = [k for k in GATE_ITEMS if items.get(k) == "✘"]
        if bad:
            out["decision"], out["gate"] = "no_trade", f"vision:{bad[0]}"
    pen = sum(1 for k in EVIDENCE_ITEMS if items.get(k) == "✘") * float(s["vision_evidence_penalty"])
    if pen and out.get("grade_score") is not None:
        out["grade_score"] = round(out["grade_score"] - pen, 3)
        g = out["grade_score"]
        out["grade"] = "A" if g >= float(s["grade_a"]) else ("B" if g >= float(s["grade_b"]) else "C")
    return out
