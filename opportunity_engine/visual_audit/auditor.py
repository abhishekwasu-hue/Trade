"""opportunity_engine/visual_audit/auditor.py — vision model ने chart वरचे levels तपासणे (spec §17.3) + स्वतंत्र visual वाचन (§17.8). `anthropic` Python SDK.

🎓 नियम:
  • Model चं नाव कोडमध्ये नाही — env `VISUAL_AUDIT_MODEL` (VPS `.env` / GitHub secret). Key: `ANTHROPIC_API_KEY`. `VISUAL_AUDIT_EFFORT` (ऐच्छिक: low|medium|high)
    दिला तरच `output_config.effort` पाठवतो. सध्याच्या models वर temperature स्वीकारला जात नाही (400) — म्हणून determinism साठी "दोनदा audit करून सहमती %"
    (`VISUAL_AUDIT_REPEAT=2`) हा पर्याय; डीफॉल्ट 1.
  • Output फक्त ठराविक JSON (structured outputs `output_config.format = json_schema`) → parse → validate (labels/verdict/किंमत-पट्टे). अपयश ⇒ एकदाच retry ⇒
    तरीही अपयश ⇒ `FAILED` (कारण सकट). `stop_reason == "refusal"` / `max_tokens` ⇒ अपयश म्हणून नोंद.
  • Model ने दिलेली किंमत कधीच थेट level म्हणून वापरली जात नाही: "missing" पट्ट्यासाठी §2.6 चा overlapping body-cluster/origin zone शोधला जातो (`snap_band`);
    सापडला तरच `AUDIT_SUGGESTED`, नाहीतर नाकारला.
  • Few-shot: वापरकर्त्याच्या feedback मधली उदाहरणं (chart + योग्य उत्तर) आधीच्या user/assistant turns म्हणून — model चे weights बदलत नाहीत, फक्त संदर्भ.
    प्रत्येक उदाहरण ≈ 1 image (~1,200 tokens) + ~400 text tokens इतका input खर्च वाढवतो.
"""
import base64
import json
import math
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

VERDICTS = ("VALID", "SPURIOUS", "SHIFT_UP", "SHIFT_DOWN")
ZONE_TYPES = ("SUPPORT", "RESISTANCE", "DEMAND", "SUPPLY")
TREND_STATES = ("UPTREND", "UPTREND_PULLBACK", "UPTREND_WEAK", "DOWNTREND", "DOWNTREND_PULLBACK", "DOWNTREND_WEAK", "RANGE", "UNCLEAR")

SYSTEM_PROMPT = (
    "You are an experienced discretionary price-action trader reviewing an Indian index chart (NSE). You read only what is on the chart: "
    "candles, swings and the labelled horizontal zones. You never use indicators. You judge a zone the way a trader does: did price really "
    "turn or base there (a genuine sell-off/rally origin or repeated reactions), or is it built on a single spike, noise or a level price "
    "has already sliced through? Image prices are approximate, so never invent exact prices; when asked for a band, give a rough band. "
    "Write every 'reason' as one short sentence in simple Marathi (Devanagari). Reply with the JSON object only."
)

OVERLAY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string"}, "verdict": {"type": "string", "enum": list(VERDICTS)}, "reason": {"type": "string"}},
            "required": ["label", "verdict", "reason"], "additionalProperties": False}},
        "missing": {"type": "array", "items": {"type": "object", "properties": {
            "approx_low": {"type": "number"}, "approx_high": {"type": "number"}, "kind": {"type": "string", "enum": list(ZONE_TYPES)},
            "reason": {"type": "string"}}, "required": ["approx_low", "approx_high", "kind", "reason"], "additionalProperties": False}},
        "trend_state": {"type": "string", "enum": list(TREND_STATES)},
        "agrees_with_engine_state": {"type": "boolean"},
    },
    "required": ["verdicts", "missing", "trend_state", "agrees_with_engine_state"],
    "additionalProperties": False,
}

INDEPENDENT_SCHEMA = {
    "type": "object",
    "properties": {
        "zones": {"type": "array", "items": {"type": "object", "properties": {
            "approx_low": {"type": "number"}, "approx_high": {"type": "number"}, "kind": {"type": "string", "enum": list(ZONE_TYPES)},
            "reason": {"type": "string"}}, "required": ["approx_low", "approx_high", "kind", "reason"], "additionalProperties": False}},
        "trend_state": {"type": "string", "enum": list(TREND_STATES)},
    },
    "required": ["zones", "trend_state"],
    "additionalProperties": False,
}


@dataclass
class VisualAuditConfig:
    model: Optional[str] = None
    effort: Optional[str] = None
    max_tokens: int = 8000
    repeat: int = 1
    fewshot: int = 0
    retries: int = 1

    @classmethod
    def from_env(cls, **override):
        cfg = cls(model=os.environ.get("VISUAL_AUDIT_MODEL") or None, effort=os.environ.get("VISUAL_AUDIT_EFFORT") or None,
                  max_tokens=int(os.environ.get("VISUAL_AUDIT_MAX_TOKENS", 8000)), repeat=max(1, int(os.environ.get("VISUAL_AUDIT_REPEAT", 1))),
                  fewshot=max(0, int(os.environ.get("VISUAL_AUDIT_FEWSHOT", 0))))
        for k, v in override.items():
            if v is not None:
                setattr(cfg, k, v)
        return cfg


@dataclass
class CallResult:
    status: str = "FAILED"                      # OK | FAILED
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 0


# ---------------------------------------------------------------------------------------------------------------------
# Prompts / requests
# ---------------------------------------------------------------------------------------------------------------------
def b64(png):
    return base64.standard_b64encode(png).decode("utf-8")


def _image_block(png_b64):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}}


def overlay_text(symbol, tf, labels, engine_state):
    return (
        f"Chart: {symbol} {tf.upper()} (last closed bars). Labelled zones (core band darker, outer band lighter; label at the left edge):\n"
        f"{json.dumps(labels, ensure_ascii=False)}\n"
        f"The engine's trend state for this timeframe is: {engine_state or 'UNKNOWN'}.\n"
        "Tasks:\n"
        "1. For EVERY label give a verdict: VALID (a real zone a trader would respect), SPURIOUS (built on one spike / noise / already sliced through), "
        "SHIFT_UP or SHIFT_DOWN (the real turning area is a little higher / lower than drawn), with a one-line reason.\n"
        "2. List important zones that are clearly visible but missing from the list: only a rough price band (approx_low, approx_high), the type and why. "
        "Do not try to read exact prices.\n"
        "3. Give the trend state you see on this chart and whether it agrees with the engine's state."
    )


def independent_text(symbol, tf):
    return (
        f"Chart: {symbol} {tf.upper()} (last closed bars), candles only. As an experienced price-action trader, list the most important "
        "support/resistance and demand/supply zones you see (at most 8), each as a rough price band (approx_low, approx_high) with type and a "
        "one-line reason, and the trend state you see. Rough bands only — do not try to read exact prices."
    )


def build_request(cfg, kind, png, symbol, tf, labels=None, engine_state=None, fewshot=None):
    """Messages API चे params (sync आणि Batches दोन्हीसाठी एकच). kind = "overlay" | "independent"."""
    if not cfg.model:
        raise ValueError("VISUAL_AUDIT_MODEL env सेट नाही — vision model चं नाव द्या")
    text = overlay_text(symbol, tf, labels or [], engine_state) if kind == "overlay" else independent_text(symbol, tf)
    messages = []
    for ex in (fewshot or [])[:cfg.fewshot]:
        messages.append({"role": "user", "content": [_image_block(ex["image_b64"]), {"type": "text", "text": ex["prompt"]}]})
        messages.append({"role": "assistant", "content": json.dumps(ex["answer"], ensure_ascii=False)})
    messages.append({"role": "user", "content": [_image_block(b64(png)), {"type": "text", "text": text}]})
    params = {"model": cfg.model, "max_tokens": int(cfg.max_tokens), "system": SYSTEM_PROMPT, "messages": messages,
              "output_config": {"format": {"type": "json_schema", "schema": OVERLAY_SCHEMA if kind == "overlay" else INDEPENDENT_SCHEMA}}}
    if cfg.effort:
        params["output_config"]["effort"] = cfg.effort
    return params


# ---------------------------------------------------------------------------------------------------------------------
# Parse / validate
# ---------------------------------------------------------------------------------------------------------------------
def _finite(x):
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _band_ok(z, price_lo=None, price_hi=None):
    if not (_finite(z.get("approx_low")) and _finite(z.get("approx_high"))):
        return False
    lo, hi = float(z["approx_low"]), float(z["approx_high"])
    if lo > hi:
        z["approx_low"], z["approx_high"] = hi, lo                       # उलटा पट्टा दुरुस्त (माहिती तीच)
        lo, hi = hi, lo
    if price_lo is not None and price_hi is not None:
        span = price_hi - price_lo
        if hi < price_lo - span or lo > price_hi + span:                  # chart पासून खूप दूर => अविश्वसनीय
            return False
    return z.get("kind") in ZONE_TYPES


def validate(kind, data, labels=None, price_lo=None, price_hi=None):
    """रिटर्न (स्वच्छ data, error|None). overlay: प्रत्येक दिलेल्या label चा verdict हवा (अज्ञात labels काढले जातात); पट्टे finite आणि chart जवळ."""
    if not isinstance(data, dict):
        return None, "JSON object नाही"
    if data.get("trend_state") not in TREND_STATES:
        return None, "trend_state अवैध"
    if kind == "overlay":
        want = {l["label"] for l in labels or []}
        seen = {}
        for v in data.get("verdicts") or []:
            if isinstance(v, dict) and v.get("label") in want and v.get("verdict") in VERDICTS:
                seen[v["label"]] = {"label": v["label"], "verdict": v["verdict"], "reason": str(v.get("reason", ""))[:300]}
        missing_labels = want - set(seen)
        if missing_labels:
            return None, f"verdict नाही: {sorted(missing_labels)}"
        miss = [m for m in (data.get("missing") or []) if isinstance(m, dict) and _band_ok(m, price_lo, price_hi)]
        return {"verdicts": [seen[l["label"]] for l in labels], "missing": miss, "trend_state": data["trend_state"],
                "agrees_with_engine_state": bool(data.get("agrees_with_engine_state"))}, None
    zones = [z for z in (data.get("zones") or []) if isinstance(z, dict) and _band_ok(z, price_lo, price_hi)]
    return {"zones": zones[:8], "trend_state": data["trend_state"]}, None


def parse_message(message, kind, labels=None, price_lo=None, price_hi=None):
    """SDK Message (किंवा तसाच object) -> (data, error, input_tokens, output_tokens)."""
    usage = getattr(message, "usage", None)
    tin, tout = int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)
    stop = getattr(message, "stop_reason", None)
    if stop == "refusal":
        return None, "model ने नकार दिला (refusal)", tin, tout
    if stop == "max_tokens":
        return None, "max_tokens संपले — उत्तर अपूर्ण", tin, tout
    text = next((b.text for b in (getattr(message, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "text उत्तर नाही", tin, tout
    try:
        raw = json.loads(text)
    except ValueError as exc:
        return None, f"JSON parse अयशस्वी: {exc}", tin, tout
    data, err = validate(kind, raw, labels, price_lo, price_hi)
    return data, err, tin, tout


def call(client, params, kind, labels=None, price_lo=None, price_hi=None, retries=1):
    """एक sync call (+ अयशस्वी झाल्यास `retries` वेळा पुन्हा). API चुका (network/429/5xx) SDK स्वतः retry करतो; इथे फक्त अवैध/अपूर्ण उत्तर पुन्हा."""
    res = CallResult()
    for _ in range(1 + max(0, int(retries))):
        res.attempts += 1
        try:
            msg = client.messages.create(**params)
        except Exception as exc:                                        # SDK च्या स्वतःच्या retries नंतरही अपयश
            res.error = f"API चूक: {type(exc).__name__}: {str(exc)[:200]}"
            continue
        data, err, tin, tout = parse_message(msg, kind, labels, price_lo, price_hi)
        res.input_tokens += tin
        res.output_tokens += tout
        if err is None:
            res.status, res.data, res.error = "OK", data, None
            return res
        res.error = err
    return res


# ---------------------------------------------------------------------------------------------------------------------
# Snap (model ची किंमत कधीच थेट नाही)
# ---------------------------------------------------------------------------------------------------------------------
SNAP_KINDS = ("SUPPORT", "RESISTANCE", "DEMAND", "SUPPLY")


def snap_band(low, high, pool, kinds=SNAP_KINDS, exclude_ids=()):
    """[low, high] पट्ट्याला छेदणारा §2.6 body-cluster (SUPPORT/RESISTANCE) किंवा origin zone (DEMAND/SUPPLY) — पट्ट्याच्या मध्याच्या सर्वात जवळचा. नसेल तर None."""
    mid = (float(low) + float(high)) / 2.0
    best, best_d = None, None
    for z in pool or []:
        if z.get("kind") not in kinds or z.get("level_id") in exclude_ids:
            continue
        zl, zh = float(z.get("outer_low", z["low"])), float(z.get("outer_high", z["high"]))
        if zh < low or zl > high:
            continue
        d = abs((zl + zh) / 2.0 - mid)
        if best_d is None or d < best_d:
            best, best_d = z, d
    return best


def agreement(a, b):
    """दोन overlay उत्तरांतील verdict सहमती % (repeat=2 साठी)."""
    if not a or not b:
        return None
    va = {v["label"]: v["verdict"] for v in a.get("verdicts", [])}
    vb = {v["label"]: v["verdict"] for v in b.get("verdicts", [])}
    common = set(va) & set(vb)
    return round(100.0 * sum(va[k] == vb[k] for k in common) / len(common), 1) if common else None


# ---------------------------------------------------------------------------------------------------------------------
# एका chart चा पूर्ण audit (overlay + स्वतंत्र)
# ---------------------------------------------------------------------------------------------------------------------
def new_run_id():
    return uuid.uuid4().hex[:12]


def audit_chart(client, cfg, symbol, tf, audit_date, png_overlay, png_plain, labels, pool, engine_state=None, price_lo=None, price_hi=None, fewshot=None):
    """रिटर्न record dict (JSON-योग्य): run_id, date, symbol, tf, model, labels, overlay/independent {status, data, error}, suggestions (snapped), usage, agreement."""
    rec = {"run_id": new_run_id(), "audit_date": str(audit_date), "symbol": symbol, "tf": tf, "model": cfg.model, "engine_state": engine_state,
           "labels": labels, "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 0}}

    def add(r):
        rec["usage"]["input_tokens"] += r.input_tokens
        rec["usage"]["output_tokens"] += r.output_tokens
        rec["usage"]["calls"] += r.attempts

    ov = CallResult(error="chart image नाही")
    if png_overlay is not None and labels:
        params = build_request(cfg, "overlay", png_overlay, symbol, tf, labels, engine_state, fewshot)
        ov = call(client, params, "overlay", labels, price_lo, price_hi, cfg.retries)
        add(ov)
        if cfg.repeat >= 2 and ov.status == "OK":
            ov2 = call(client, params, "overlay", labels, price_lo, price_hi, 0)
            add(ov2)
            rec["agreement_pct"] = agreement(ov.data, ov2.data) if ov2.status == "OK" else None
    elif not labels:
        ov = CallResult(status="SKIPPED", error="या chart वर audit करण्याजोगे levels नाहीत")
    rec["overlay"] = {"status": ov.status, "data": ov.data, "error": ov.error}
    ind = CallResult(error="chart image नाही")
    if png_plain is not None:
        ind = call(client, build_request(cfg, "independent", png_plain, symbol, tf), "independent", None, price_lo, price_hi, cfg.retries)
        add(ind)
    rec["independent"] = {"status": ind.status, "data": ind.data, "error": ind.error}
    sugg = []
    for m in (ov.data or {}).get("missing", []):
        z = snap_band(m["approx_low"], m["approx_high"], pool, exclude_ids={l["level_id"] for l in labels})
        sugg.append({**m, "snapped_level_id": None if z is None else z.get("level_id")})
    rec["suggestions"] = sugg
    return rec


def make_client():
    """anthropic client (credentials SDK स्वतः env/profile मधून शोधतो). SDK नसेल तर ImportError."""
    import anthropic
    return anthropic.Anthropic()
