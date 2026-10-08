"""vision_led/prompt.py — `vision_led_v2` request (v1 + C-V1 structural invalidation) (TRADE_VISION_LED_PROMPT B3–B4).

Input: chart PNG (15M 100 + 1H 70 + line panel + futures volume, असेल तर; CAS राखाडी) · OHLC तक्ते (15M शेवटचे 60, 1H शेवटचे 70; bar start वेळ) · code चे
candidate areas (id, साधन, प्रकार, पट्टा, touches, state) · तटस्थ facts (swings, gap, volume) · playbook (system, cache_control).
Anchoring टाळण्यासाठी code ची बाजू / grade / narrative vision ला **दिली जात नाही** (Abhi 2026-10-08).
Output: ठराविक JSON (schema) — किंमती फक्त OHLC तक्त्यातून (ohlc_ref), image वरून कधीच नाही. Temperature 0.
"""
import base64
import json

import pandas as pd

from .playbook import PLAYBOOK, PROMPT_VERSION

REF = {"type": "object", "additionalProperties": False, "required": ["price", "ohlc_ref"],
       "properties": {"price": {"type": "number"}, "ohlc_ref": {"type": "string"}}}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["trade", "side", "grade", "area_id", "story", "entry", "invalidation", "invalidation_reason", "target", "evidence_for",
                 "evidence_against", "wrong_if"],
    "properties": {
        "trade": {"type": "boolean"},
        "side": {"type": "string", "enum": ["bull_put", "bear_call", "none"]},
        "grade": {"type": "string", "enum": ["A", "B", "C"]},
        "area_id": {"type": "string"},
        "story": {"type": "array", "items": {"type": "string"}},
        "entry": REF, "invalidation": REF, "invalidation_reason": {"type": "string"}, "target": REF,
        "evidence_for": {"type": "array", "items": {"type": "string"}},
        "evidence_against": {"type": "array", "items": {"type": "string"}},
        "wrong_if": {"type": "string"},
    },
}


CAS_NOTE = ("Note: since 2026-08-03 NSE runs a closing auction (CAS) 15:15-15:30; those bars are EXCLUDED from these tables and greyed "
            "on the chart (frozen index + auction print, not traded prices). The official close (PDC in the facts) is the auction price and "
            "can differ from the last 15:00 bar close.")


def ohlc_table(df, n, label):
    d = df.tail(int(n))
    rows = [f"{pd.Timestamp(r.timestamp):%Y-%m-%d %H:%M},{r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f}" for r in d.itertuples()]
    return f"{label} OHLC (bar start time IST, open, high, low, close; last row = last CLOSED bar):\n" + "\n".join(rows)


def areas_text(areas, limit=25):
    out = []
    for z in areas[:limit]:
        extra = []
        if z.get("touches") is not None:
            extra.append(f"touches {z['touches']}" + ("" if z.get("valid", True) else " (not valid)"))
        if z.get("pool"):
            extra.append(f"pool {z['pool']}")
        out.append(f"{z['id']} | tool {z.get('tool')} ({z.get('kind')}) | {z.get('role')} | {z['low']:.2f}-{z['high']:.2f} | state {z.get('state')}"
                   + (" | " + ", ".join(extra) if extra else ""))
    return "Code candidate areas (id | tool | role | band | state):\n" + "\n".join(out)


def user_text(cand, m15, h1, areas, facts, volume_note=None):
    """Anchoring टाळा (Abhi 2026-10-08): code ची बाजू, code grade, code narrative चा निष्कर्ष **दिले जात नाहीत**. फक्त chart, OHLC तक्ते,
    candidate areas (id, साधन, पट्टा, touches) आणि तटस्थ facts (swings, gap, volume आकडे). Trend / impulse / correction / बाजू vision ठरवतो."""
    head = (f"NIFTY. Decision bar: 15M bar starting {cand['bar_start']:%Y-%m-%d %H:%M} (closed at {pd.Timestamp(cand['bar_end']):%H:%M}); "
            f"no data after this close is shown. Median range (MR, 20 closed 15M bars) = {cand['mr']:.2f} points.\n"
            "Decide yourself: trend, impulse, correction type and side (bull_put / bear_call) or no trade.")
    parts = [head, ohlc_table(m15, 60, "15M"), ohlc_table(h1, 70, "1H"), CAS_NOTE, areas_text(areas)]   # 1H 70 ≈ 10 sessions (anchors)
    if facts:
        parts.append("Neutral facts (computed from closed bars only):\n" + "\n".join(facts))
    if volume_note:
        parts.append(volume_note)
    parts.append("Answer with the JSON schema. Prices only from the OHLC tables (copy exactly; ohlc_ref like '2026-10-07 14:15 high'). Invalidation = where the idea is wrong (beyond the active area / trendline), with invalidation_reason.")
    return "\n\n".join(parts)


def build_request(png, text, model, max_tokens=3000, effort=None, thinking=None, temperature=0.0):
    if not model:
        raise ValueError("model env नाही (VISION_SIGNAL_MODEL)")
    content = []
    if png:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode("utf-8")}})
    content.append({"type": "text", "text": text})
    p = {"model": model, "max_tokens": int(max_tokens),
         "system": [{"type": "text", "text": PLAYBOOK, "cache_control": {"type": "ephemeral"}}],
         "messages": [{"role": "user", "content": content}],
         "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}
    if effort:
        p["output_config"]["effort"] = effort
    if thinking:
        p["thinking"] = {"type": thinking}
    elif temperature is not None:
        p["temperature"] = float(temperature)                            # thinking सोबत temperature पाठवत नाही
    return p


def parse(message):
    """(data | None, error | None, usage)."""
    from vision.signal_audit import usage_of
    usage = usage_of(message)
    stop = getattr(message, "stop_reason", None)
    if stop in ("refusal", "max_tokens"):
        return None, f"stop_reason {stop}", usage
    text = next((b.text for b in (getattr(message, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "text उत्तर नाही", usage
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"JSON parse: {exc}", usage
    miss = [k for k in SCHEMA["required"] if k not in data]
    if miss:
        return None, f"JSON field नाही: {miss}", usage
    return data, None, usage


__all__ = ["PROMPT_VERSION", "SCHEMA", "build_request", "parse", "user_text", "ohlc_table", "areas_text"]
