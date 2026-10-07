"""vision/signal_audit.py — signal chart चा vision audit (`signal_check`, structured JSON) + verdict चे नियम (code मध्ये) + खर्च.

🎓 G-COST (≤ $5 / महिना):
  • प्रति signal 1 audit; पहिल्याची confidence < `second_audit_below_conf` (0.6) तरच दुसरा.
  • 1 image (2 panels + overlay, ~1000×700 ≈ 900 image tokens), plain image नाही.
  • System prompt स्थिर आणि `cache_control` सह (model चं किमान cacheable prefix पेक्षा लहान असेल तर cache होत नाही — खर्च `usage` मधून मोजतो).
  • Output लहान JSON (reason ≤ 160 chars), `max_tokens` env ने मर्यादित. Model नाव env `VISION_SIGNAL_MODEL` (कोडमध्ये नाही).
Verdict चे नियम (vision चं मत तसंच मानत नाही): `is_breakout_entry = yes` किंवा `reversal_valid = no` ⇒ disagree; कुठलंही `unclear`, किंवा 2 audits
असहमत ⇒ gray; enum अवैध / API अपयश ⇒ unavailable.
"""
import base64
import json
import os
import time

PROMPT_VERSION = "signal_check_v1"
VERDICTS = ("agree", "gray", "disagree")
ENUMS = {
    "level_real": ("yes", "no", "unclear"),
    "trend_context": ("with", "against", "range", "unclear"),
    "reversal_valid": ("yes", "no", "unclear"),
    "is_breakout_entry": ("yes", "no"),
    "false_break_risk": ("low", "medium", "high"),
    "verdict": VERDICTS,
}
SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "string", "enum": list(v)} for k, v in ENUMS.items()},
        "elliott_note": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["level_real", "trend_context", "reversal_valid", "is_breakout_entry", "false_break_risk", "elliott_note", "verdict", "reason",
                 "confidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are an experienced discretionary price-action trader auditing one automated trade signal on an Indian index (NSE NIFTY) chart. "
    "You see one image with two panels: the left panel is the setup timeframe, the right panel is a higher timeframe. Both panels are cut "
    "exactly at the signal moment - there is no future data. The horizontal line marked 'L' is the level the bot traded "
    "(green = support, red = resistance); the arrow marks the signal bar; a dashed yellow line, when present, is the invalidation.\n\n"
    "The trader's rules you must audit against:\n"
    "1. Pullback-only entries. Never a breakout entry: buying after price has broken above resistance, or selling after it has broken below "
    "support, is a breakout entry even if the bot calls it a level touch.\n"
    "2. A valid reversal at the level has four steps: touch (price reaches the level), reclaim (price comes back to the right side of it), "
    "strength (a candle with a real body away from the level, not a doji or long wick against the trade), and close location (the signal bar "
    "closes in the part of its range that favours the trade).\n"
    "3. The level must be real: price has turned or based there before (a clear swing origin or repeated reactions), not a single spike, "
    "noise in the middle of a range, or a level price has already sliced through several times.\n"
    "4. No entry at the end of a first corrective leg (an A-end) against the higher-timeframe trend: when the higher panel shows a strong "
    "trend and the setup panel shows only the first pullback leg ending at the level, a trade against that trend is premature.\n"
    "5. Judge the trend context on the higher panel: is the trade with the trend, against it, or inside a range?\n\n"
    "Answer strictly from what the chart shows. Never read or invent exact prices from the image. When something cannot be judged from the "
    "chart, answer 'unclear' rather than guessing. 'false_break_risk' is your estimate that price will slice through the level against the "
    "trade. 'elliott_note' is one short optional wave-count remark (empty string when none). 'verdict' is agree (the signal follows the "
    "rules), gray (mixed or doubtful) or disagree (it breaks a rule). 'confidence' is 0.0-1.0. Write 'reason' as one short sentence in "
    "simple Marathi (Devanagari), at most 160 characters. Reply with the JSON object only."
)

# $ प्रति 1M tokens: (input, output, cache read) — model family नुसार (नाव कोडमध्ये नाही; model नावात हा शब्द असेल तर). Cache write = 1.25 × input
# (5-मिनिट TTL). जुन्या / वेगळ्या किंमतीचा model वापरला तर env VISION_PRICE_IN / _OUT / _CACHE_READ ने अचूक किंमत द्या.
PRICES = {
    "haiku": (1.0, 5.0, 0.10),
    "sonnet": (2.0, 10.0, 0.20),
    "opus": (4.0, 20.0, 0.20),
}
UNKNOWN_PRICE = (5.0, 25.0, 0.50)                                       # अज्ञात model ⇒ जास्त (सावध) अंदाज


def price_for(model):
    env = [os.environ.get(k) for k in ("VISION_PRICE_IN", "VISION_PRICE_OUT", "VISION_PRICE_CACHE_READ")]
    if env[0] and env[1]:
        return float(env[0]), float(env[1]), float(env[2] or float(env[0]) * 0.1)
    for k, v in PRICES.items():
        if model and k in str(model).lower():
            return v
    return UNKNOWN_PRICE


def cost_usd(model, usage):
    pin, pout, pcr = price_for(model)
    return (usage.get("input_tokens", 0) * pin + usage.get("cache_write", 0) * pin * 1.25 + usage.get("cache_read", 0) * pcr
            + usage.get("output_tokens", 0) * pout) / 1e6


def max_output_tokens():
    return int(os.environ.get("VISION_SIGNAL_MAX_TOKENS", 2000))


def estimate_usd(model, image_tokens=900, system_tokens=900, text_tokens=250, output_tokens=None):
    """एका audit चा सावध अंदाज (budget आधी तपासायला): cache न धरता, output = max_tokens (thinking सुद्धा output मध्ये मोजलं जातं)."""
    output_tokens = max_output_tokens() if output_tokens is None else output_tokens
    return cost_usd(model, {"input_tokens": image_tokens + system_tokens + text_tokens, "output_tokens": output_tokens})


def signal_text(sig):
    tags = sig.get("tags") or {}
    lines = [
        f"Signal: {sig.get('symbol')} · bot {sig.get('bot_label') or sig.get('bot')} · direction {sig.get('direction')} "
        f"({'long / bullish' if str(sig.get('direction', '')).upper().startswith('BULL') else 'short / bearish'})",
        f"Level (from the bot's OHLC data, not the image): {sig.get('level')} as {sig.get('role')} on the {sig.get('setup_tf')} level set.",
        f"Signal time: {sig.get('signal_ts')} IST. Spot at signal: {sig.get('spot')}.",
    ]
    if tags:
        lines.append("Bot tags: " + ", ".join(f"{k}={v}" for k, v in sorted(tags.items())))
    lines.append("Audit this signal against the rules and fill the JSON.")
    return "\n".join(lines)


def build_request(png, sig, model, max_tokens=None, effort=None, thinking=None):
    if not model:
        raise ValueError("VISION_SIGNAL_MODEL env सेट नाही")
    params = {
        "model": model,
        "max_tokens": int(max_tokens or max_output_tokens()),
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode("utf-8")}},
            {"type": "text", "text": signal_text(sig)}]}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }
    if effort:
        params["output_config"]["effort"] = effort
    if thinking:
        params["thinking"] = {"type": thinking}
    return params


def validate(raw):
    """(स्वच्छ dict, error|None). Enum अवैध ⇒ error (⇒ unavailable)."""
    if not isinstance(raw, dict):
        return None, "JSON object नाही"
    out = {}
    for k, allowed in ENUMS.items():
        v = str(raw.get(k, "")).strip().lower()
        if v not in allowed:
            return None, f"{k} अवैध: {raw.get(k)!r}"
        out[k] = v
    try:
        conf = float(raw.get("confidence"))
    except (TypeError, ValueError):
        return None, "confidence अवैध"
    if conf != conf:
        return None, "confidence NaN"
    out["confidence"] = min(1.0, max(0.0, conf))
    note = raw.get("elliott_note")
    out["elliott_note"] = (str(note).strip()[:160] or None) if note not in (None, "null") else None
    out["reason"] = str(raw.get("reason") or "").strip()[:160]
    return out, None


def usage_of(message):
    u = getattr(message, "usage", None)
    g = (lambda k: int(getattr(u, k, 0) or 0)) if u is not None else (lambda k: 0)
    return {"input_tokens": g("input_tokens"), "output_tokens": g("output_tokens"), "cache_read": g("cache_read_input_tokens"),
            "cache_write": g("cache_creation_input_tokens")}


def parse_message(message):
    """(data, error, usage)."""
    usage = usage_of(message)
    stop = getattr(message, "stop_reason", None)
    if stop == "refusal":
        return None, "refusal", usage
    if stop == "max_tokens":
        return None, "max_tokens संपले", usage
    text = next((b.text for b in (getattr(message, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "text उत्तर नाही", usage
    try:
        raw = json.loads(text)
    except ValueError as exc:
        return None, f"JSON parse: {exc}", usage
    data, err = validate(raw)
    return data, err, usage


def code_verdict(a):
    """एका audit चा verdict — code चे नियम model च्या verdict वर."""
    if not a:
        return "unavailable"
    if a["is_breakout_entry"] == "yes" or a["reversal_valid"] == "no":
        return "disagree"
    if "unclear" in (a["level_real"], a["trend_context"], a["reversal_valid"]):
        return "gray"
    return a["verdict"]


def combine(verdicts):
    """2 audits: एक unavailable ⇒ दुसरा; दोन्ही सारखे ⇒ तोच; असहमत ⇒ gray."""
    vs = [v for v in verdicts if v and v != "unavailable"]
    if not vs:
        return "unavailable"
    return vs[0] if len(set(vs)) == 1 else "gray"


def make_client(timeout_sec=20):
    import anthropic
    return anthropic.Anthropic(timeout=float(timeout_sec), max_retries=1)


def one_call(client, params):
    """(data, error, usage, latency_ms). कधीच raise नाही."""
    t0 = time.monotonic()
    try:
        msg = client.messages.create(**params)
    except Exception as exc:
        return None, f"API: {type(exc).__name__}: {str(exc)[:160]}", {}, int((time.monotonic() - t0) * 1000)
    data, err, usage = parse_message(msg)
    return data, err, usage, int((time.monotonic() - t0) * 1000)


def audit(client, png, sig, model, second_below=0.6, effort=None, thinking=None, on_usage=None, budget_ok=None):
    """1 audit (+ confidence < second_below असेल तर दुसरा, budget_ok() खरं असेल तरच). रिटर्न dict:
    {verdict, audits:[…], verdicts:[…], confidence, cost_usd, usage, latency_ms, error, prompt_version, model}."""
    params = build_request(png, sig, model, effort=effort, thinking=thinking)
    out = {"audits": [], "verdicts": [], "cost_usd": 0.0, "latency_ms": 0, "error": None, "prompt_version": PROMPT_VERSION, "model": model,
           "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0}}
    for n in range(2):
        if n == 1:
            first = out["audits"][0] if out["audits"] else None
            if first is None or first["confidence"] >= second_below or (budget_ok is not None and not budget_ok()):
                break
        data, err, usage, ms = one_call(client, params)
        if not usage and err and err.startswith("API"):
            # timeout / network: request कदाचित billed झाला असेल पण usage मिळाला नाही ⇒ budget साठी सावध अंदाज नोंदवतो
            usage = {"input_tokens": 2050, "output_tokens": max_output_tokens(), "estimated": 1}
        c = cost_usd(model, usage)
        out["cost_usd"] += c
        out["latency_ms"] += ms
        for k in out["usage"]:
            out["usage"][k] += usage.get(k, 0)
        if on_usage is not None and usage:
            on_usage(usage, c)
        if err:
            out["error"] = err
            out["verdicts"].append("unavailable")
            if n == 0:
                break
            continue
        out["audits"].append(data)
        out["verdicts"].append(code_verdict(data))
    out["verdict"] = combine(out["verdicts"])
    confs = [a["confidence"] for a in out["audits"]]
    out["confidence"] = round(sum(confs) / len(confs), 3) if confs else None
    out["cost_usd"] = round(out["cost_usd"], 6)
    return out
