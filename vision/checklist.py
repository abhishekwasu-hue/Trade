"""vision/checklist.py — V4 checklist output (design §12.2): schema, fixed schema text, parser / validator, "prices must exist in facts"
check, Telegram lines. API call नाही.

🎓 JSON: items 1–7 (Method Pack sections 1–7 च्या क्रमाने) प्रत्येकी pass / fail / NA + एक evidence ओळ; overall verdict agree / partly /
disagree; pack_version. Validator fail-closed: आकार चुकीचा, verdict विसंगत (agree + fail), pack version वेगळा, किंवा evidence मधला
**कोणताही price-सारखा आकडा facts / OHLC मध्ये नाही** (tick tolerance) ⇒ संपूर्ण output नाकारला + log. Vision audit-only: हा निकाल कधीच
order अडवत / बदलत नाही.
"""
import html
import json
import logging
import math
import re

log = logging.getLogger("vision.checklist")

ITEMS = {                                                                  # n ⇒ (key, नाव, प्रश्न) — Method Pack sections 1–7
    1: ("topdown", "Top-down trend",
        "Top-down (section 1): weekly state, daily / parent trend (degree-aware Dow, protected origin intact); the trade is on the trend "
        "side (or an approved exception)."),
    2: ("area", "Area",
        "Area (section 2): price is at a valid, alive band — base / flip / 2-touch band at its 3rd touch / sharp-fall or sharp-rise "
        "point / confluence — not a magnet, not dead beyond the far swing."),
    3: ("trendline", "Trendline / channel",
        "Trendlines / channels (section 3): any line used is valid (2 wick touches, spacing, no close through, slope) and respected; "
        "NA when no line is relevant."),
    4: ("correction", "Correction",
        "Correction (section 4): the move into the area is a correction, not an impulse, and it can be complete here (C / E / Y end; "
        "not an A-end, not inside B / triangle / X)."),
    5: ("zone_study", "Zone study",
        "Zone study (section 5): handover inside the area — counter side weakening, trend side growing, sweep / trap, volume; no "
        "absorption against the trade."),
    6: ("trigger", "Trigger",
        "Trigger (section 6): a closed dominant commitment candle on higher futures volume plus a lower-timeframe CHoCH by close (or the "
        "KP1 line close-through at the area)."),
    7: ("never", "Never-list",
        "Never-list (section 7): no breakout / chase, no counter-trend entry, no minor-swing break alone, no unclosed candle, no price "
        "outside the facts. pass = nothing on the never-list is violated."),
}
STATUSES = ("pass", "fail", "NA")
VERDICTS = ("agree", "partly", "disagree")
ICON = {"pass": "✅", "fail": "❌", "NA": "—"}
TELEGRAM_MAX_LINES = 12
EVIDENCE_MAX = 220
DEFAULT_TICK = 0.05                                                        # NSE index tick

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["pack_version", "items", "verdict"],
    "properties": {
        "pack_version": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["n", "status", "evidence"],
            "properties": {"n": {"type": "integer"}, "status": {"type": "string", "enum": list(STATUSES)},
                           "evidence": {"type": "string"}}}},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
    },
}

SCHEMA_TEXT = ("OUTPUT — the checklist (fixed schema; audit only: your answer never blocks, sizes or changes any order)\n"
               "Audit the proposed trade in the user message against the Method Pack above. Return one JSON object:\n"
               '{"pack_version": "<the 12-hex version from the Method Pack header>", "items": [7 objects '
               '{"n": 1..7, "status": "pass" | "fail" | "NA", "evidence": "<one line>"}], "verdict": "agree" | "partly" | "disagree"}\n'
               "Items, exactly once each, in this order:\n"
               + "\n".join(f"{n}. {q}" for n, (_, _, q) in ITEMS.items()) + "\n"
               "Rules:\n"
               "- status: pass = the proposal satisfies the item; fail = it violates it; NA = the item cannot be judged from the charts and "
               "facts, or does not apply.\n"
               "- evidence: ONE line (≤ 200 characters, English) citing a fact from the FACTS text or a feature visible on a chart. Any "
               "price you write must be copied exactly from the FACTS / OHLC text — never read a price from an image, never round or "
               "invent one. Prefer naming the feature (\"3rd touch of the falling line\") over writing a price.\n"
               "- verdict: agree = no item fails; partly = some items fail or are NA but nothing on the never-list (item 7) fails; "
               "disagree = item 7 fails or the read contradicts the proposal. Never answer agree when any item is fail.\n"
               "- Do not judge stop, target, position size, reward-to-risk or exits — they are not part of this audit.\n"
               "Reply with the JSON object only.")


class ChecklistError(ValueError):
    pass


def parse_json(text):
    """Model text ⇒ dict (code fence / पुढचा-मागचा मजकूर सहन); जमलं नाही ⇒ ValueError."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.lower().startswith("json") else t
    try:
        return json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            raise
        return json.loads(t[a:b + 1])


# ----------------------------------------------------------------------------------------------------------- prices in facts
_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_NOT_PRICE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"                                  # 2026-10-12 [09:15]
    rf"|\b\d{{1,2}}[\s-]+(?:{_MONTHS})[a-z]*(?:[\s-]+\d{{2,4}})?\b"                           # 12 Oct [2026] / 12-Oct
    rf"|\b(?:{_MONTHS})[a-z]*[\s-]+\d{{1,2}}(?:,?\s+\d{{4}})?\b"                               # Oct 12[, 2026]
    r"|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{1,2}\.\d{1,2}\.\d{2,4}\b"                         # 12/10, 12/10/2026, 12.10.2026
    r"|\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?"                                         # 09:15, 9:30am
    r"|\b\d{1,2}\s*[ap]\.?m\b"                                                                # 10am
    r"|\b(?:waves?|items?|sections?|steps?|stages?|legs?|sub-?waves?|degree|n|no\.?|#)\s*\(?\s*[ivx\d]+\s*\)?"   # wave (4), item 3
    r"|\(\s*(?:\d{1,2}|[ivx]{1,4})\s*\)"                                                       # (4) / (iv) wave labels
    r"|\b(?:volume|vol\.?)\s+(?:of\s+)?[\d.,]+",                                              # volume 1.8 / volume 180,000
    re.I)
_NUM = re.compile(r"(?<![\w.,/])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w%×/]|[.,]\d)")
_UNIT_AFTER = re.compile(r"\s*(?:x\b|×|%|percent\b|pc\b|MR\b|ATR\b|bars?\b|candles?\b|min(?:utes?)?\b|hours?\b|sessions?\b|days?\b|"
                         r"weeks?\b|touch(?:es)?\b|legs?\b|waves?\b|pivots?\b|pts?\b|points?\b|σ|lakh\b|lac\b|crore\b|cr\b|k\b|"
                         r"contracts?\b|shares?\b|times\b)", re.I)


def numbers(text):
    """मजकुरातले आकडे ⇒ [(value, decimals, मूळ मजकूर)] — तारखा, वेळा, wave / item / section क्रमांक, ordinals, एककासह आकडे (MR, %,
    percent, lakh, ×, bars …) आणि volume वगळून."""
    t = _NOT_PRICE.sub(" ", str(text or ""))
    out = []
    for m in _NUM.finditer(t):
        if _UNIT_AFTER.match(t, m.end()):
            continue
        raw = m.group(1)
        dec = len(raw.split(".", 1)[1]) if "." in raw else 0
        out.append((float(raw.replace(",", "")), dec, raw))
    return out


def facts_prices(*objs):
    """Facts / OHLC ⇒ sorted unique floats (dict / list / tuple / DataFrame / str सगळ्यांतून; str मधले आकडे सुद्धा)."""
    vals = set()

    def walk(o):
        if o is None or isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            if math.isfinite(float(o)):
                vals.add(round(float(o), 4))
        elif isinstance(o, str):
            for v, _, _ in numbers(o):
                vals.add(round(v, 4))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple, set)):
            for v in o:
                walk(v)
        elif hasattr(o, "columns") and hasattr(o, "__getitem__"):            # DataFrame: OHLC कॉलम
            for c in ("open", "high", "low", "close"):
                if c in o.columns:
                    walk([float(x) for x in o[c].to_numpy() if x == x])
        elif hasattr(o, "item"):
            try:
                walk(o.item())
            except (TypeError, ValueError):
                pass
    for ob in objs:
        walk(ob)
    return sorted(vals)


PRICE_LO, PRICE_HI = 0.5, 1.5                                              # price-range = [0.5 × min anchor, 1.5 × max anchor]


def price_range(anchors):
    """Price anchors (level, spot, invalidation, chart levels, model ला दिसणारे OHLC — facts मधले bar counts / MR / अंतरं नाहीत) ⇒
    (lo, hi). Anchors नाहीत ⇒ (100, inf): fail-closed (≥ 100 चा कोणताही आकडा संशयित)."""
    a = sorted(x for x in (anchors or []) if x and x > 0)
    return (PRICE_LO * a[0], PRICE_HI * a[-1]) if a else (100.0, math.inf)


def unknown_prices(texts, known, tick=DEFAULT_TICK, anchors=None):
    """texts मधले price-सारखे आकडे जे known मध्ये (tick + लिहिलेल्या अचूकतेच्या अर्ध्या एककात) नाहीत ⇒ [मूळ मजकूर].
    Range फक्त anchors वरून (None ⇒ known = anchors, उदा. golden मध्ये model ला दिसणारे OHLC): range मध्ये ⇒ known मध्ये हवा;
    range च्या **वर** (> 1.5 × max: दुसऱ्या instrument ची किंमत?) ⇒ नाकार; range च्या **खाली** (counts, %, wave क्रमांक) ⇒ दुर्लक्ष."""
    import bisect
    known = sorted(known or [])
    lo, hi = price_range(known if anchors is None else anchors)
    bad = []
    for tx in texts:
        for v, dec, raw in numbers(tx):
            if v < lo:
                continue
            if v > hi:
                bad.append(raw)
                continue
            tol = tick + 0.5 * 10 ** (-dec) + 1e-9
            i = bisect.bisect_left(known, v - tol)
            if not (i < len(known) and known[i] <= v + tol):
                bad.append(raw)
    return bad


# ----------------------------------------------------------------------------------------------------------- validator
def _one_line(x):
    return " ".join(str(x).split())


def validate(raw, pack_version=None, known_prices=None, tick=DEFAULT_TICK, anchors=None):
    """Model JSON ⇒ (स्वच्छ dict, None) किंवा (None, English कारण). Fail-closed: कोणतीही चूक ⇒ संपूर्ण output नाकारला (log warning).
    known_prices = facts_prices(...) चा निकाल (model ला दिलेल्या किंमती); anchors = price-range साठी किंमती (None ⇒ known); known_prices
    None ⇒ price check नाही (फक्त tests / आकार तपासणी)."""
    err = _validate(raw, pack_version)
    if isinstance(err, str):
        log.warning("V4 checklist rejected: %s", err)
        return None, err
    out = err
    if known_prices is not None:
        bad = unknown_prices([it["evidence"] for it in out["items"]], known_prices, tick, anchors)
        if bad:
            why = "prices not in facts: " + ", ".join(dict.fromkeys(bad))
            log.warning("V4 checklist rejected: %s", why)
            return None, why
    return out, None


def _validate(raw, pack_version):
    if not isinstance(raw, dict):
        return "not a JSON object"
    extra = set(raw) - {"pack_version", "items", "verdict"}
    if extra:
        return f"unexpected fields {sorted(extra)}"
    pv = raw.get("pack_version")
    if not isinstance(pv, str) or not re.fullmatch(r"[0-9a-f]{12}", pv.strip()):
        return "invalid pack_version"
    if pack_version and pv.strip() != pack_version:
        return f"pack_version {pv.strip()} != {pack_version}"
    if raw.get("verdict") not in VERDICTS:
        return "invalid verdict"
    items = raw.get("items")
    if not isinstance(items, list) or len(items) != len(ITEMS):
        return f"items must be a list of {len(ITEMS)}"
    seen = {}
    for it in items:
        if not isinstance(it, dict) or set(it) != {"n", "status", "evidence"}:
            return "invalid item shape"
        n = it["n"]
        if isinstance(n, bool) or not isinstance(n, int) or n not in ITEMS or n in seen:
            return f"invalid / duplicate item n {n!r}"
        st = {"na": "NA", "pass": "pass", "fail": "fail"}.get(str(it["status"]).strip().lower())
        if st is None:
            return f"item {n}: invalid status {it['status']!r}"
        ev = _one_line(it["evidence"]) if isinstance(it["evidence"], str) else ""
        if not ev:
            return f"item {n}: empty evidence"
        seen[n] = {"n": n, "status": st, "evidence": ev[:EVIDENCE_MAX]}
    out = {"pack_version": pv.strip(), "verdict": raw["verdict"], "items": [seen[n] for n in sorted(seen)]}
    if out["verdict"] == "agree" and any(i["status"] == "fail" for i in out["items"]):
        return "verdict agree with a failed item"
    return out


# ----------------------------------------------------------------------------------------------------------- Telegram
FOOTER = "Audit only — Vision never blocks or changes an order."


def telegram_lines(res, title=None):
    """V4 निकाल ⇒ Telegram ओळी (English, HTML-escaped): failed / NA items आधी, कमाल 12 ओळी, "audit-only" शब्द."""
    head = "👁 Vision V4 checklist (audit only)" + (f" · {html.escape(str(title))}" if title else "")
    lines = [head[:160]]
    data = (res or {}).get("data")
    if not data:
        why = (res or {}).get("error") or (res or {}).get("why") or "not available"
        lines.append(f"Checklist not available: {html.escape(str(why))}"[:200])
    else:
        lines.append(f"Verdict: {data['verdict']} · pack {data['pack_version']}")
        order = {"fail": 0, "NA": 1, "pass": 2}
        for it in sorted(data["items"], key=lambda i: (order[i["status"]], i["n"])):
            lines.append(f"{ICON[it['status']]} {it['n']}. {ITEMS[it['n']][1]}: {html.escape(it['evidence'])}"[:240])
    lines = lines[:TELEGRAM_MAX_LINES - 1] + [FOOTER]
    return lines


def telegram_text(res, title=None):
    return "\n".join(telegram_lines(res, title))
