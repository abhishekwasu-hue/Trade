"""reader_report/standard.py — enforce docs/reader/REPORT_STANDARD.md. Every reading / replay report generator calls these before
it writes a report; a missing chart layer, a day-based outcome horizon or a missing section raises ReportStandardError.

A chart's meta = {"entry_key": str, "layers": {layer_key: {"evaluated": bool, "count": int, "note": str}}}. A layer with nothing at
that bar is still evaluated (count 0, note e.g. "no pattern").
"""

RULES_LINE = "Rules re-read: CLAUDE.md, REPORT_STANDARD.md"

REQUIRED_LAYERS = ("areas_1h_states", "lines", "channels", "patterns", "liquidity_sweeps", "fut_volume_pane", "rsi_pane",
                   "rsi_divergence_pair", "ltf_choch_inset", "htf_state_strip", "story")

REQUIRED_CARD_FIELDS = ("model", "area", "state", "side", "evidence", "invalidation", "story", "outcome", "mfe", "mae")

OUTCOMES = ("next_area_first", "invalidation_first", "open_at_data_end")

# words that mark a calendar / session / clock horizon (forbidden: the outcome is measured by structure across sessions)
_DAY_WORDS = ("day", "session", "eod", "clock", "date", "intraday", "expiry", "o'clock")


class ReportStandardError(ValueError):
    pass


def validate_chart(meta):
    """Every required layer present and evaluated; the story has exactly two lines."""
    layers = (meta or {}).get("layers") or {}
    missing = [k for k in REQUIRED_LAYERS if not (layers.get(k) or {}).get("evaluated")]
    if missing:
        raise ReportStandardError(f"chart {meta.get('entry_key')!r}: missing layer(s) {', '.join(missing)}")
    story = (layers["story"].get("note") or "").strip().splitlines()
    if len(story) != 2:
        raise ReportStandardError(f"chart {meta.get('entry_key')!r}: the story must be two lines (has {len(story)})")
    return True


def validate_outcome_rule(rule):
    """{"horizon": "structure", "target": ..., "stop": ...}: structural horizon, never a day / session / clock one."""
    h = str((rule or {}).get("horizon", "")).lower()
    if h != "structure":
        raise ReportStandardError(f"outcome horizon must be 'structure' (got {h!r})")
    for k, v in (rule or {}).items():
        if k == "horizon":
            continue
        text = f"{k} {v}".lower()
        if any(w in text for w in _DAY_WORDS):
            raise ReportStandardError(f"outcome rule {k!r} is day / session / clock based: {v!r}")
    return True


def validate_card(card):
    miss = [f for f in REQUIRED_CARD_FIELDS if card.get(f) in (None, "")]
    if miss:
        raise ReportStandardError(f"card {card.get('entry_key')!r}: missing {', '.join(miss)}")
    if card["outcome"] not in OUTCOMES:
        raise ReportStandardError(f"card {card.get('entry_key')!r}: outcome {card['outcome']!r} not in {OUTCOMES}")
    return True


def validate_report(rep):
    """rep = {"first_line", "summary_mr", "outcome_rule", "entries": [card], "charts": {entry_key: meta}, "per_model": [...],
    "running_total": [...], "missed_big_moves": [{"chart": ...}], "worst_losses": [{"chart": ...}], "gaps": [...]}."""
    if (rep.get("first_line") or "").strip() != RULES_LINE:
        raise ReportStandardError(f"first line must be {RULES_LINE!r}")
    if not (rep.get("summary_mr") or "").strip():
        raise ReportStandardError("plain Marathi summary on top is missing")
    validate_outcome_rule(rep.get("outcome_rule"))
    charts = rep.get("charts") or {}
    for card in rep.get("entries") or []:
        validate_card(card)
        if card["entry_key"] not in charts:
            raise ReportStandardError(f"entry {card['entry_key']!r} has no chart (every entry is charted, never samples)")
        validate_chart(charts[card["entry_key"]])
    for key in ("per_model", "running_total"):
        if not rep.get(key):
            raise ReportStandardError(f"{key} table missing")
    for key in ("missed_big_moves", "worst_losses"):
        items = rep.get(key)
        if items is None:
            raise ReportStandardError(f"{key} section missing")
        if any(not it.get("chart") for it in items):
            raise ReportStandardError(f"{key}: every item needs a chart")
    if rep.get("gaps") is None:
        raise ReportStandardError("data gaps table missing (empty list if none)")
    return True
