"""vision/engine_audit.py — T-5 (Handover; owner-orders DECISIONS 31, PROVISIONAL): Vision audits an ENGINE signal against the engine's
own reading, with the method's closed concept list — not the old level-bot rulebook.

Why (the 22 Oct NIFTY "15M Dynamic SR" E4 (b) bear call that Vision called "disagree"): for `signal_source = engine` the worker sent
the engine's entry through the level-bot audit (vision/signal_audit.py, `signal_check_v2_2`): the single L line card ("reclaimed /
held R"), PDH / PDL / PDC, ORH / ORL, the gap classes G1–G5 / gap fill, "opening", "event_day", and `role_conflict` from that
session's behaviour. Those code rules (DISAGREE_RULES / GRAY_RULES, `code_verdict`) set a verdict FLOOR, so a session / gap / clock
fact could force "disagree" on a signal that is valid under the engine's concepts. The method forbids that framing for chart reading.

Now, for an engine signal (`tags["engine"] is True`, written only by paper/engine_entry.py) and the Vision setting
`vision_engine_audit = engine` (default; `legacy` = the old audit, a what-if):
  • card — vision/engine_card.py: the engine's chart (visited area faint, refined base strong, the broken object of E4 (b), the trigger
    candle, the invalidation, the next area, the HTF strip); no L line, no session separators, no gap / opening overlays;
  • checklist — the method's concepts only: trend side, area alive / lifecycle state, visit, trigger traded into the refined base,
    invalidation side, model rule, evidence (listed, never decides);
  • floor — only Vision's own checklist (a failed concept ⇒ disagree, an unclear concept ⇒ gray); the old session / gap / opening /
    L-line rules are computed as CONTEXT LINES only (`rule_hits[i]["context_only"]`) and never set the verdict;
  • text — engine facts only: no day / date / session / clock framing, no fixed numbers in the reading rules (tests pin both).
Vision stays advisory (human_confirm: Abhi decides; reduce-only): nothing here places, blocks or changes an order. Level-bot signals
(`signal_source = own`) never reach this module — their audit is byte-identical (tests pin it). No API call happens in tests.
"""
import base64
import json
import time

PROMPT_VERSION = "engine_check_v1"
MODEL_C_VERSION = PROMPT_VERSION + "+c"            # a model C card (DECISIONS 32): + the model C system block
SETTING = "vision_engine_audit"
MODES = ("engine", "legacy")
DEFAULT = "engine"                      # PROVISIONAL (DECISIONS 31): review with the verdict-vs-outcome table (vision/engine_measure.py)
VERDICTS = ("agree", "gray", "disagree")
STATUSES = ("pass", "fail", "unclear")
ITEMS = (                               # (key, card name) — the method's closed concept list (CHART_READER_METHOD §3–§4, §8), in order
    ("trend_side", "Trend side"),
    ("area_state", "Area alive / lifecycle"),
    ("visit", "Visit"),
    ("trigger_in_base", "Trigger in the refined base"),
    ("invalidation_side", "Invalidation side"),
    ("model_rule", "Model rule"),
    ("evidence", "Evidence (listed, never decides)"),
)
KEYS = tuple(k for k, _ in ITEMS)
VERDICT_ITEMS = tuple(k for k in KEYS if k != "evidence")   # evidence is listed and never blocks (CLAUDE.md entry framework)
NOTE_MAX = 160
REASON_MAX = 160
ICON = {"pass": "✓", "fail": "✗", "unclear": "?"}
SEVERITY = {"agree": 0, "gray": 1, "disagree": 2}

SCHEMA = {
    "type": "object",
    "properties": {
        "checklist": {"type": "object", "additionalProperties": False, "required": list(KEYS),
                      "properties": {k: {"type": "object", "additionalProperties": False, "required": ["status", "note"],
                                         "properties": {"status": {"type": "string", "enum": list(STATUSES)},
                                                        "note": {"type": "string"}}} for k in KEYS}},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["checklist", "verdict", "reason", "confidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """ROLE
You audit one signal of a rule-based chart reader (the engine) on an NSE index chart. The trader is a price-action trader: bull put
spreads at demand, bear call spreads at supply, held across the swing. You check whether the engine's own reading is what the chart
shows. You never trade, never change a level and never change the order: your verdict is advice and the trader decides.

THE CARD
One image: left = the setup timeframe (15M) candles, right = the higher timeframe candles, a futures volume pane under each, and a
strip at the top with the higher-timeframe states. Drawn: the visited area (faint band, "AREA"), the refined base inside it (strong
band, "BASE"), for E4 (b) the broken object being retested (dashed band or line, "BROKEN"), the trigger candle (yellow box, "T"), the
invalidation (dashed yellow line, "INV"), the next area in the trade direction (outlined band, "NEXT"); other areas are faded. Every
price is in the text; never read or invent a price from the image.

THE METHOD (a closed concept list: judge only with these concepts)
- Read the chart as one continuous unit, by structure only. A gap is simply the next candle.
- Trend side: trade only in the direction of the higher-timeframe trend; a correction in progress does not change the trend. Never a
  counter-trend entry, never a breakout entry, never a chase.
- Area and its lifecycle: an area is built from one base (wick to body), never from joined bases. Alive = fresh or tested. Sweep = a
  close beyond the area without a swing formed beyond it, then back inside: the area stays alive and the visit continues. Broken = a
  close beyond the area and a swing formed beyond it. Flipped = price went beyond the far-side swing: the role reverses. Dead = a
  flipped area broken again: never a trade location. An area dies only by structure, never by being touched or entered.
- Visit: begins when price enters the area and ends only by structure (a swing built away from the area, a break, a flip, or a failed
  commitment). Candles that close just outside and come back are the same visit.
- Refined base and trigger: the higher-timeframe area is the context; the refined 15M base inside it gives the trigger location and
  the invalidation. The trigger candle itself must trade into the refined base (its range overlaps the base); touching only the wider
  area is not enough. A close outside the area on the trade side is the confirmation and is allowed; a close beyond on the
  invalidation side is not. E4 (b): the rejection candle trades at the retested broken object and closes on its trade side.
- Invalidation side: price must not be beyond the invalidation now. A candle that gaps or closes through the invalidation side is the
  area breaking, not an entry. A sweep already back inside is not beyond.
- Models, each at most once per visit: E1 aggressive = the visit's first candle at the refined base (it does not come back after a
  sweep); E2 confirmation = a commitment candle after a handover; E3 structure = a lower-timeframe change of character after price
  entered the area; E4 (a) sweep-retest = after a sweep the next push fails inside the sweep extreme (invalidation beyond the sweep
  extreme); E4 (b) = price comes back from the other side to a broken (flipped) area or a broken line and is rejected there
  (invalidation beyond the retest extreme). E2 and E3 never fire while the zone study reads absorption without a handover.
- Evidence (listed, never blocks): a handover (slow form: trend-side candles grow while the other side shrinks; fast form: a rejected
  push taken back by a dominant opposite candle), a commitment candle on higher futures volume than the candles it is compared with,
  a lower-timeframe change of character, volume growing inside the area, RSI divergence, confluence (a line or a higher-timeframe area
  on the area), a correction line closed through at the area. A missing piece is reported; it is never by itself a reason to disagree.
- Comparisons only (larger, smaller, beyond, inside, the same structure); no fixed sizes, ratios or counts.

YOUR TASK
Fill the checklist from the chart and the text. Every item has a status (pass / fail / unclear) and a note of at most one short
English sentence:
  trend_side, area_state, visit, trigger_in_base, invalidation_side, model_rule, evidence (pass = at least one confirming piece is
  visible, fail = none; this item never decides the verdict).
verdict: "agree" = every item except evidence passes; "gray" = an item is unclear or mixed; "disagree" = an item except evidence fails.
reason: one short sentence in simple Marathi (Devanagari) naming the deciding concept. confidence: from zero to one.
Reply with the JSON object only."""


# Model C (DECISIONS 32; OPEN_QUESTIONS: P4 vs DECISIONS 32, provisional — DECISIONS 32 wins for model C only). A SECOND system block, sent
# only with a model C card: SYSTEM_PROMPT (and its cache) stays byte-identical for every other engine signal.
MODEL_C_SYSTEM = """MODEL C (this card only; an owner decision)
This signal is model C: a separate, switchable model for the C leg of a correction against the Daily side. It is the one exception to
"never a counter-trend entry". Its trade side is the correction's own direction: the Daily side is the other way, a 1H change of
character began wave A, wave B is a corrective pullback still in progress (no close beyond the end of A, except the first return to it
when the facts say so), and B has not died (a close beyond the origin O and a swing formed beyond O). Judge trend_side by this rule;
judge every other item as for any signal. It is still a pullback or retest entry, never a breakout entry."""


def is_model_c(sig):
    """A model C card: tags["entry_family"] == "C" (paper/engine_entry.model_c_tags)."""
    return str(_tags(sig).get("entry_family") or "").upper() == "C"


def prompt_version(sig):
    """The audit's prompt version for this card: "engine_check_v1" for every engine signal as before; "engine_check_v1+c" for a model C
    card (its extra system block) — stamped on the audit (validate), the result (audit) and the worker's reuse lookup."""
    return MODEL_C_VERSION if is_model_c(sig) else PROMPT_VERSION


# ------------------------------------------------------------------------------------------------------------------ which signals
def _tags(sig):
    t = (sig or {}).get("tags")
    return t if isinstance(t, dict) else {}


def is_engine(sig):
    """An engine signal = tags["engine"] is True (paper/engine_entry.py — `signal_source = engine`); every other signal (level bots,
    manual, the level bots' own confirmation gate) is not."""
    return _tags(sig).get("engine") is True


def mode_of(sig):
    v = str(((sig or {}).get("ctx_settings") or {}).get(SETTING, DEFAULT) or DEFAULT).lower()
    return v if v in MODES else DEFAULT


def use_engine(sig):
    """The engine audit applies: an engine signal and `vision_engine_audit = engine` (default)."""
    return is_engine(sig) and mode_of(sig) == "engine"


def engine_ctx(ctx):
    """The signal's context was built for the engine audit (vision/chart.render marks it) — the worker's reuse path re-applies the code
    facts on this ctx, so the marker routes it to this module's rules."""
    return isinstance(ctx, dict) and ctx.get("signal_source") == "engine"


# ------------------------------------------------------------------------------------------------------------------ the reading
def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _band(lo, hi):
    a, b = _num(lo), _num(hi)
    return None if a is None or b is None else (min(a, b), max(a, b))


def _inv(x):
    """entry_invalidation: a price, or {price, rule} (engine3_live._invalidation_of) ⇒ (price | None, rule | None)."""
    if isinstance(x, dict):
        return _num(x.get("price")), (None if x.get("rule") is None else str(x["rule"]))
    return _num(x), None


ALIVE = ("FRESH", "TESTED", "ACTIVE", "SWEPT", "ARMED", "VALID", "FLIPPED")


def next_area(d, ref, areas):
    """The next area in the trade direction (Abhi's target area: the next opposite area): the nearest area of the opposite role whose
    near edge lies beyond `ref` on the trade side (bear call ⇒ demand below, bull put ⇒ supply above), not broken / dead. Comparison
    only. ⇒ {role, lo, hi, state, source} | None."""
    want = "support" if d < 0 else "resistance"
    if ref is None:
        return None
    best = None
    for a in areas or []:
        b = _band(a.get("lo"), a.get("hi"))
        st = str(a.get("state") or "").upper()
        if b is None or str(a.get("role") or "").lower() != want or (st and st not in ALIVE):
            continue
        near = b[1] if d < 0 else b[0]
        if (d < 0 and near >= ref) or (d > 0 and near <= ref):
            continue
        if best is None or (d < 0 and near > best["hi"]) or (d > 0 and near < best["lo"]):
            best = {"role": want, "lo": b[0], "hi": b[1], "state": st or None, "source": a.get("source") or "engine"}
    return best


def reading(sig, fallback_areas=None):
    """The engine's own reading of this signal, from the signal tags only (nothing re-read): model, object, trend / HTF strip, the
    visited area, the refined base, the broken object (E4 (b)), the trigger, the invalidation, the next area, cluster, evidence.
    fallback_areas (chart bands at signal time, no look-ahead) give the next area only when the engine row carries no opposite area."""
    t = _tags(sig)
    g = t.get("gate") if isinstance(t.get("gate"), dict) else {}
    d = 1 if str((sig or {}).get("direction", "")).upper().startswith("BULL") else -1
    area = _band(*(list(g.get("area") or []) + [None, None])[:2])
    areas = [a for a in (g.get("areas") or []) if isinstance(a, dict)]
    me = next((a for a in areas if area is not None and _band(a.get("lo"), a.get("hi")) == area), {})
    rb = g.get("refined") if isinstance(g.get("refined"), dict) else {}
    model = str(t.get("entry_model") or "").upper() or None
    name = t.get("entry_name")
    obj = t.get("entry_object") or me.get("object")
    if obj is None and model == "E4" and "(b)" in str(name or ""):
        obj = "broken_line" if str(me.get("tf") or "") == "line" else "broken_area"
    obj = obj or ("area" if area is not None else None)
    ip, rule = _inv(t.get("entry_invalidation"))
    if ip is None:
        ip = _num((sig or {}).get("invalidation"))
    ref = _num(t.get("entry_ref"))
    if ref is None:
        ref = _num((sig or {}).get("spot"))
    nxt = next_area(d, ref, areas)
    if nxt is None and fallback_areas:
        nxt = next_area(d, ref, [{"role": a.get("role"), "lo": a.get("lo"), "hi": a.get("hi"), "source": "chart band finder",
                                  "state": "BROKEN" if a.get("broken") and not a.get("valid") else (a.get("state") or "")}
                                 for a in fallback_areas if isinstance(a, dict)])
    ev = t.get("entry_evidence")
    ev = [[str(x[0]), str(x[1])] for x in ev if isinstance(x, (list, tuple)) and len(x) >= 2] if isinstance(ev, list) else []
    htf = g.get("htf") if isinstance(g.get("htf"), dict) else {}
    cl = g.get("cluster") if isinstance(g.get("cluster"), dict) else None
    mc = None
    if str(t.get("entry_family") or "").upper() == "C":                 # model C (DECISIONS 32): its own facts for trend_side
        c = t.get("entry_model_c") if isinstance(t.get("entry_model_c"), dict) else {}
        mc = {"sub_model": t.get("entry_sub_model"), "story": t.get("entry_story"), "daily": (c.get("daily") or {}).get("trend"),
              "weekly": c.get("weekly"), "O": _num((c.get("O") or {}).get("price")), "HA": _num((c.get("HA") or {}).get("price")),
              "B": _num((c.get("B") or {}).get("price")), "a_nature": (c.get("a_nature") or {}).get("verdict"),
              "b_nature": (c.get("b_nature") or {}).get("verdict"), "window": c.get("window"),
              "invalidated_if": c.get("invalidated_if")}
    return {"direction": d, "side": "bull put" if d > 0 else "bear call", "model": model, "name": name, "label": t.get("entry_label"),
            "grade": g.get("grade"), "object": obj, "trend": g.get("trend"), "htf": htf or None,
            "area": None if area is None else {"lo": area[0], "hi": area[1], "tf": me.get("tf") or g.get("tf"), "state": me.get("state"),
                                               "id": me.get("id"), "role": "support" if d > 0 else "resistance"},
            "refined": _band(rb.get("lo"), rb.get("hi")), "trigger_ts": t.get("entry_trigger_ts"), "entry_ref": ref,
            "invalidation": ip, "invalidation_rule": rule, "next_area": nxt, "evidence": ev,
            "cluster": None if not cl else {"n": cl.get("n"), "members": t.get("entry_cluster")},
            "others": [{"role": a.get("role"), "lo": _num(a.get("lo")), "hi": _num(a.get("hi")), "state": a.get("state")}
                       for a in areas if _band(a.get("lo"), a.get("hi")) not in (area,)], **({"model_c": mc} if mc else {})}


def _p(x):
    return "n/a" if x is None else f"{float(x):,.2f}"


OBJECT_WORDS = {"area": "the visited area", "broken_area": "a broken (flipped) area being retested from the other side",
                "broken_line": "a broken line being retested from the other side"}


def facts_text(sig, rd=None):
    """The engine facts Vision audits against — exact prices from the engine data; no day / date / session / clock words."""
    rd = rd or reading(sig)
    a, nx = rd["area"], rd["next_area"]
    h = rd["htf"] or {}
    lines = [
        f"Signal: {sig.get('symbol')} | {rd['side']} ({'bullish' if rd['direction'] > 0 else 'bearish'}) | setup timeframe 15M",
        "Entry model: " + (f"{rd['model']} {rd['name'] or ''}".strip() if rd["model"] else "the engine's setup (no entry model)")
        + (f" | label {rd['label']}" if rd.get("label") else "") + ".",
        f"Trend side (engine): {rd['trend'] or 'n/a'}"
        + (f" | Weekly {h.get('weekly')}" if h.get("weekly") else "") + (f" | Daily {h.get('daily')}" if h.get("daily") else "")
        + (f" ({h.get('daily_phase')})" if h.get("daily_phase") else "") + ".",
        f"Object: {OBJECT_WORDS.get(rd['object'], rd['object'] or 'n/a')}.",
    ]
    if a:
        kind = "line value" if a["lo"] == a["hi"] else "band"
        lines.append(f"{'Retested object' if str(rd['object'] or '').startswith('broken') else 'Visited area'} ({a['role']} side, "
                     f"{a.get('tf') or 'n/a'}): {kind} {_p(a['lo'])}" + ("" if a["lo"] == a["hi"] else f" - {_p(a['hi'])}")
                     + f" | state {a.get('state') or 'n/a'}.")
    else:
        lines.append("Visited area: not in the signal.")
    rb = rd["refined"]
    lines.append(f"Refined 15M base: {_p(rb[0])} - {_p(rb[1])}." if rb else
                 "Refined 15M base: none in the signal" + (" (E4 (b) is judged at the retested object)." if str(rd['object'] or '')
                                                             .startswith("broken") else "."))
    lines.append("Trigger candle: boxed and marked T on the setup panel (the chart ends at its close)"
                 + (f"; its close (entry reference) {_p(rd['entry_ref'])}." if rd["entry_ref"] is not None else "."))
    lines.append(f"Invalidation: {_p(rd['invalidation'])}" + (f" ({rd['invalidation_rule']})" if rd.get("invalidation_rule") else "")
                 + ".")
    lines.append(f"Next area in the trade direction: {nx['role']} {_p(nx['lo'])} - {_p(nx['hi'])}"
                 + (f" ({nx['source']})" if nx.get("source") and nx["source"] != "engine" else "") + "." if nx else
                 "Next area in the trade direction: none known.")
    mc = rd.get("model_c")
    if mc:                                                               # DECISIONS 32: the C leg's own trend-side rule (advisory audit)
        lines.append(f"Model C ({mc.get('sub_model') or 'C'}, owner decision — a separate switchable model, not the Daily-side rule): "
                     f"the counter-trend C leg of a correction against the Daily side. Daily side {mc.get('daily') or 'n/a'}"
                     + (f", Weekly {mc['weekly']}" if mc.get("weekly") else "") + "; this trade is in the 1H correction's direction.")
        lines.append(f"Model C structure (engine): origin O {_p(mc.get('O'))}; wave A from O made a 1H change of character, its nature "
                     f"{mc.get('a_nature') or 'n/a'}, ended at HA {_p(mc.get('HA'))}; wave B {mc.get('b_nature') or 'n/a'}, extreme so "
                     f"far {_p(mc.get('B'))}; window: {mc.get('window') or 'n/a'}; {mc.get('invalidated_if') or ''}.")
        lines.append("Trend side for this model C signal passes when: the Daily side is opposite to this trade, a 1H change of "
                     "character began wave A, B is a corrective pullback still in progress (or the first return to HA when the window "
                     "says so) and B has not closed beyond O with a swing formed beyond O. Judge trend_side by this rule.")
    if rd.get("cluster") and rd["cluster"].get("n"):
        lines.append("Cluster: overlapping areas of the same role count as one place (one signal per model); the edges, trigger and "
                     "invalidation above come from the visited area only.")
    if rd["evidence"]:
        lines.append("Evidence list (engine; listed, never blocks): " + "; ".join(f"{n} {m}" for n, m in rd["evidence"]) + ".")
    oth = [o for o in rd["others"] if o["lo"] is not None and o["hi"] is not None and str(o.get("state") or "").upper() != "DEAD"
           and not (nx and (o["lo"], o["hi"]) == (nx["lo"], nx["hi"]))]
    if oth:
        lines.append("Other engine areas (faded on the chart): " + "; ".join(
            f"{'supply' if o['role'] == 'resistance' else 'demand'} {_p(o['lo'])} - {_p(o['hi'])} {str(o.get('state') or '').lower()}"
            .strip() for o in sorted(oth, key=lambda z: -z["hi"])) + ".")
    lines.append("Audit this signal against the method and fill the checklist JSON.")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------------ request / parse
def build_request(png, sig, model, max_tokens=None, effort=None, thinking=None, text=None):
    from . import signal_audit as SA
    if not model:
        raise ValueError("VISION_SIGNAL_MODEL env सेट नाही")
    params = {
        "model": model,
        "max_tokens": int(max_tokens or SA.max_output_tokens()),
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
        + ([{"type": "text", "text": MODEL_C_SYSTEM}] if is_model_c(sig) else []),
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode("utf-8")}},
            {"type": "text", "text": text if text is not None else facts_text(sig)}]}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }
    if effort:
        params["output_config"]["effort"] = effort
    if thinking:
        params["thinking"] = {"type": thinking}
    return params


def validate(raw, version=PROMPT_VERSION):
    """(clean dict, error | None). A missing item / status outside the enum / no verdict ⇒ error (⇒ unavailable)."""
    if not isinstance(raw, dict):
        return None, "JSON object नाही"
    ck = raw.get("checklist")
    if not isinstance(ck, dict):
        return None, "checklist नाही"
    out = {"checklist": {}}
    for k in KEYS:
        it = ck.get(k)
        st = str((it or {}).get("status", "")).strip().lower() if isinstance(it, dict) else ""
        if st not in STATUSES:
            return None, f"{k} अवैध: {it!r}"[:200]
        out["checklist"][k] = {"status": st, "note": str(it.get("note") or "").strip()[:NOTE_MAX]}
    v = str(raw.get("verdict", "")).strip().lower()
    if v not in VERDICTS:
        return None, f"verdict अवैध: {raw.get('verdict')!r}"
    out["verdict"] = v
    try:
        conf = float(raw.get("confidence"))
    except (TypeError, ValueError):
        return None, "confidence अवैध"
    if conf != conf:
        return None, "confidence NaN"
    out["confidence"] = min(1.0, max(0.0, conf))
    out["reason"] = str(raw.get("reason") or "").strip()[:REASON_MAX]
    out["engine_check"] = version
    return out, None


def parse_message(message, version=PROMPT_VERSION):
    from . import signal_audit as SA
    usage = SA.usage_of(message)
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
    data, err = validate(raw, version)
    return data, err, usage


def one_call(client, params, version=PROMPT_VERSION):
    """(data, error, usage, latency_ms). Never raises."""
    t0 = time.monotonic()
    try:
        msg = client.messages.create(**params)
    except Exception as exc:                                             # noqa: BLE001
        return None, f"API: {type(exc).__name__}: {str(exc)[:160]}", {}, int((time.monotonic() - t0) * 1000)
    data, err, usage = parse_message(msg, version)
    return data, err, usage, int((time.monotonic() - t0) * 1000)


# ------------------------------------------------------------------------------------------------------------------ verdict rules
def apply_facts(a, ctx=None):
    """Code facts the engine audit imposes (strict direction only): the trigger candle not closed yet ⇒ trigger_in_base unclear. No
    session / gap / opening / L-line fact touches the engine checklist. ⇒ (a, changes)."""
    if not a or not isinstance(a.get("checklist"), dict):
        return a, []
    a = {**a, "checklist": {k: dict(v) for k, v in a["checklist"].items()}}
    ch = []
    sb = (ctx or {}).get("signal_bar") or {}
    it = a["checklist"].get("trigger_in_base") or {}
    if sb and sb.get("closed") is False and it.get("status") == "pass":
        it["status"] = "unclear"
        ch.append("trigger_in_base=unclear (the trigger candle is not closed yet)")
    return a, ch


def rule_hits(a, ctx=None):
    """(disagree ids, gray ids) from Vision's own checklist: a failed method concept ⇒ disagree, an unclear one ⇒ gray. Evidence is
    listed and never counts. Nothing from the old level-bot rulebook."""
    ck = (a or {}).get("checklist") or {}
    d = [k for k in VERDICT_ITEMS if (ck.get(k) or {}).get("status") == "fail"]
    g = [k for k in VERDICT_ITEMS if (ck.get(k) or {}).get("status") == "unclear"]
    return d, g


def code_verdict(a, ctx=None):
    """The audit's verdict: the stricter of Vision's own verdict and its own checklist (never more positive than the checklist)."""
    if not a:
        return "unavailable"
    d, g = rule_hits(a, ctx)
    floor = "disagree" if d else ("gray" if g else "agree")
    own = a.get("verdict") if a.get("verdict") in SEVERITY else "gray"
    return max(floor, own, key=SEVERITY.get)


def legacy_context(ctx, direction, disagree_rules=None, gray_rules=None):
    """CONTEXT LINES only: the old level-bot rules (session / gap / opening / L line) on this signal's context, as the old audit would
    have floored it with a neutral reading — {"disagree": [...], "gray": [...], "facts": [...]}. Never sets the engine verdict."""
    from . import signal_audit as SA
    if not isinstance(ctx, dict):
        return {"disagree": [], "gray": [], "facts": []}
    plain = {k: v for k, v in ctx.items() if k not in ("signal_source", "engine")}
    if not plain:
        return {"disagree": [], "gray": [], "facts": []}
    try:
        _, hits, facts = SA.pre_verdict(plain, direction, disagree_rules, gray_rules)
    except Exception as exc:                                             # noqa: BLE001 — context only, never the verdict
        return {"disagree": [], "gray": [], "facts": [], "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return {"disagree": list(hits.get("disagree") or []), "gray": [x for x in hits.get("gray") or [] if x != "unclear"], "facts": facts}


def audit(client, png, sig, model, second_below=0.6, effort=None, thinking=None, on_usage=None, budget_ok=None, disagree_rules=None,
          gray_rules=None):
    """The engine audit — the same shape as signal_audit.audit ({verdict, audits, verdicts, confidence, cost_usd, usage, latency_ms,
    error, prompt_version, model, rule_hits}) so the worker / gate / store paths stay as they are. rule_hits[i] = {"disagree": [concept
    ids failed], "gray": [concept ids unclear], "context_only": the old rules' hits (context lines, never the verdict)}."""
    from . import signal_audit as SA
    ctx = sig.get("ctx")
    rd = (ctx or {}).get("engine") if isinstance(ctx, dict) and isinstance(ctx.get("engine"), dict) else reading(sig)
    params = build_request(png, sig, model, effort=effort, thinking=thinking, text=facts_text(sig, rd))
    pv = prompt_version(sig)
    legacy = legacy_context(ctx, sig.get("direction"), disagree_rules, gray_rules)
    out = {"audits": [], "verdicts": [], "cost_usd": 0.0, "latency_ms": 0, "error": None, "prompt_version": pv, "model": model,
           "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0}, "rule_hits": []}
    for n in range(2):
        if n == 1:
            first = out["audits"][0] if out["audits"] else None
            if first is None or first["confidence"] >= second_below or (budget_ok is not None and not budget_ok()):
                break
        data, err, usage, ms = one_call(client, params, pv)
        if not usage and err and err.startswith("API"):
            usage = {"input_tokens": 2050, "output_tokens": SA.max_output_tokens(), "estimated": 1}   # as signal_audit.audit (budget)
        c = SA.cost_usd(model, usage)
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
        data, facts = apply_facts(data, ctx)
        if facts:
            data["code_overrides"] = facts
        out["audits"].append(data)
        out["verdicts"].append(code_verdict(data, ctx))
        d, g = rule_hits(data, ctx)
        out["rule_hits"].append({"disagree": d, "gray": g, "context_only": legacy})
    out["verdict"] = SA.combine(out["verdicts"])
    if len(out["verdicts"]) == 2 and out["verdicts"][1] == "unavailable" and out["verdict"] == "agree":
        out["verdict"] = "gray"                                          # as signal_audit.audit
    confs = [x["confidence"] for x in out["audits"]]
    out["confidence"] = round(sum(confs) / len(confs), 3) if confs else None
    out["cost_usd"] = round(out["cost_usd"], 6)
    if not out["rule_hits"]:
        out["rule_hits"] = [{"disagree": [], "gray": [], "context_only": legacy}]
    return out


# ------------------------------------------------------------------------------------------------------------------ card text
def caption_lines(a, hits=None):
    """Telegram details for an engine audit: one line per method concept (✓ / ✗ / ?) + the old rules as context lines (never the
    verdict). HTML-escaped."""
    import html
    out = []
    names = dict(ITEMS)
    for k in KEYS:
        it = ((a or {}).get("checklist") or {}).get(k) or {}
        out.append(f"{ICON.get(it.get('status'), '?')} {names[k]}" + (f" — {html.escape(it['note'])}" if it.get("note") else ""))
    if (a or {}).get("code_overrides"):
        out.append("Code तथ्यं: " + html.escape("; ".join(a["code_overrides"])))
    if hits and (hits.get("disagree") or hits.get("gray")):
        out.append("नियम: " + ", ".join([f"❌ {x}" for x in hits.get("disagree") or []] + [f"🟡 {x}" for x in hits.get("gray") or []]))
    ctxo = (hits or {}).get("context_only") or {}
    old = list(ctxo.get("disagree") or []) + list(ctxo.get("gray") or [])
    if old:
        out.append("Context only (old level-bot rules, not in the verdict): " + html.escape(", ".join(old)))
    return out
