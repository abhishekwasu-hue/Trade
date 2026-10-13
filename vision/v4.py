"""vision/v4.py — Vision V4 prompt (design §12.2–§12.4): system prefix = Method Pack + स्थिर checklist schema मजकूर, शेवटी स्पष्ट
prompt-caching breakpoint (`cache_control` शेवटच्या system block वर); chart images + त्या क्षणाचे facts त्यानंतर (user message).

🎓 Audit-only: निकाल फक्त नोंद / Telegram — कधीच order अडवत, size बदलत किंवा निर्णय बदलत नाही (V1 gate ला V2 चाच verdict जातो).
Model नाव env मधून (`VISION_SIGNAL_MODEL`, कोडमध्ये नाही); किंमती / खर्च `vision.signal_audit` (cost_usd, usage_of) चेच; budget
`vision.config` चं ($2 / दिवस) — इथे बदल नाही. Global setting `vision_v4_audit` = "off" (default) ⇒ worker हा मार्ग बोलावत नाही.
"""
import base64
import time

from . import checklist as CK
from . import method_pack as MP

PROMPT_VERSION = "v4_checklist"
TASK = "signal_v4"
IMAGE_TOKENS = 1600                                                        # design §8: एक chart image ≈ 1,600 input tokens
MAX_TOKENS = 3000                                                          # checklist JSON + thinking (सावध; env ने बदलता येतो)
FACTS_HEAD = ("FACTS (exact numbers from data — the only source of prices; closed candles only, nothing after the decision bar "
              "exists):\n")
TASK_TEXT = ("Audit this proposal with the Method Pack and return the checklist JSON (items 1–7, verdict, pack_version). "
             "Audit only — your answer never blocks or changes the order.")


def max_tokens():
    import os
    return int(os.environ.get("VISION_V4_MAX_TOKENS", MAX_TOKENS))


def system_blocks(pack_text, ttl=None):
    """[Method Pack, schema मजकूर (cache_control)] — prefix स्थिर: pack version बदलला तरच बदलतो. ttl None ⇒ default (5 मिनिटं)."""
    cc = {"type": "ephemeral"}
    if ttl:
        cc["ttl"] = ttl
    return [{"type": "text", "text": pack_text.rstrip() + "\n"},
            {"type": "text", "text": CK.SCHEMA_TEXT, "cache_control": cc}]


def user_content(images, facts):
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.standard_b64encode(p).decode("utf-8")}} for p in images if p]
    content.append({"type": "text", "text": FACTS_HEAD + str(facts).strip() + "\n\n" + TASK_TEXT})
    return content


def build_request(images, facts, model, pack=None, max_tokens_=None, effort=None, thinking=None, ttl=None):
    """images = PNG bytes ची यादी (W / D / 1H / 15M किंवा signal chart), facts = मजकूर. pack = (text, version) — None ⇒ commit केलेला
    method_pack.md (header hash तपासून)."""
    if not model:
        raise ValueError("VISION_SIGNAL_MODEL env सेट नाही")
    text, _ = pack or MP.load()
    params = {"model": model, "max_tokens": int(max_tokens_ or max_tokens()),
              "system": system_blocks(text, ttl),
              "messages": [{"role": "user", "content": user_content(images, facts)}],
              "output_config": {"format": {"type": "json_schema", "schema": CK.SCHEMA}}}
    if effort:
        params["output_config"]["effort"] = effort
    if thinking:
        params["thinking"] = {"type": thinking}
    return params


def estimate(n_images, facts, pack_text, model, max_tokens_=None):
    """Dry-run अंदाज (chars / 4, image ≈ 1,600): tokens + $ (pack cached / uncached / पहिला cache write). खर्च signal_audit.cost_usd ने."""
    from .signal_audit import cost_usd
    sys_tok = MP.tokens_estimate(pack_text) + MP.tokens_estimate(CK.SCHEMA_TEXT)
    fresh = n_images * IMAGE_TOKENS + MP.tokens_estimate(FACTS_HEAD + str(facts) + TASK_TEXT)
    out = int(max_tokens_ or max_tokens())
    return {"system_tokens": sys_tok, "fresh_input_tokens": fresh, "max_output_tokens": out,
            "usd_uncached": round(cost_usd(model, {"input_tokens": sys_tok + fresh, "output_tokens": out}), 5),
            "usd_cache_write": round(cost_usd(model, {"input_tokens": fresh, "cache_write": sys_tok, "output_tokens": out}), 5),
            "usd_cached": round(cost_usd(model, {"input_tokens": fresh, "cache_read": sys_tok, "output_tokens": out}), 5)}


def read_message(msg, pack_version, known_prices, tick=CK.DEFAULT_TICK):
    """API message ⇒ (data, error). Refusal / max_tokens / JSON / schema / price check ⇒ error (fail-closed)."""
    stop = getattr(msg, "stop_reason", None)
    if stop in ("refusal", "max_tokens"):
        return None, f"stop_reason {stop}"
    text = next((b.text for b in (getattr(msg, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "no text answer"
    try:
        raw = CK.parse_json(text)
    except ValueError:
        return None, "parse error"
    return CK.validate(raw, pack_version=pack_version, known_prices=known_prices, tick=tick)


def audit(client, images, facts, model, known_prices, pack=None, on_usage=None, effort=None, thinking=None, ttl=None):
    """एक V4 call (repair / दुसरा call नाही — खर्च मर्यादित). रिटर्न dict: status done / rejected / failed, data, error, usage, cost_usd,
    latency_ms, pack_version, prompt_version, model. कधीच raise नाही (request बांधताना चूक वगळता)."""
    from . import signal_audit as SA
    text, ver = pack or MP.load()
    params = build_request(images, facts, model, pack=(text, ver), effort=effort, thinking=thinking, ttl=ttl)
    out = {"status": "failed", "data": None, "error": None, "usage": {}, "cost_usd": 0.0, "latency_ms": 0, "pack_version": ver,
           "prompt_version": PROMPT_VERSION, "model": model}
    t0 = time.monotonic()
    try:
        msg = client.messages.create(**params)
    except Exception as exc:                                               # noqa: BLE001 — billed असू शकतो ⇒ सावध अंदाज नोंद
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        out["error"] = f"API: {type(exc).__name__}"
        est = estimate(len([p for p in images if p]), facts, text, model)
        usage = {"input_tokens": est["system_tokens"] + est["fresh_input_tokens"], "output_tokens": est["max_output_tokens"],
                 "estimated": 1}
        out.update(usage=usage, cost_usd=round(SA.cost_usd(model, usage), 6), cost_estimated=True)
        _usage_cb(on_usage, usage, out)
        return out
    out["latency_ms"] = int((time.monotonic() - t0) * 1000)
    usage = SA.usage_of(msg)
    out.update(usage=usage, cost_usd=round(SA.cost_usd(model, usage), 6))
    _usage_cb(on_usage, usage, out)
    data, err = read_message(msg, ver, known_prices)
    if err:
        out.update(status="rejected", error=err)
        return out
    out.update(status="done", data=data)
    return out


def _usage_cb(on_usage, usage, out):
    if on_usage is None:
        return
    try:
        on_usage(usage, out["cost_usd"])
    except Exception as exc:                                               # noqa: BLE001 — cost log अपयश ⇒ निकाल टाकत नाही
        out["cost_log_error"] = type(exc).__name__
