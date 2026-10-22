"""reader_report/standard.py — enforce docs/reader/REPORT_STANDARD.md. Every reading / replay report generator calls these before
it writes a report; a missing chart layer, a day-based outcome horizon or a missing section raises ReportStandardError. A replay first
calls group_data_status (RC5): a group without near-month FUT volume on every spot session is "not testable" and emits one line only.
Every chart carries its clean-chart line selection (P8, `lines_view`): legend ≤ chart_max_lines, only shown lines, evidence shown.

A chart's meta = {"entry_key": str, "layers": {layer_key: {"evaluated": bool, "count": int, "note": str}}}. A layer with nothing at
that bar is still evaluated (count 0, note e.g. "no pattern").
"""

RULES_LINE = "Rules re-read: CLAUDE.md, REPORT_STANDARD.md"

REQUIRED_LAYERS = ("areas_1h_states", "lines", "channels", "patterns", "liquidity_sweeps", "fut_volume_pane", "rsi_pane",
                   "rsi_divergence_pair", "ltf_choch_inset", "htf_state_strip", "story")

REQUIRED_CARD_FIELDS = ("entry_key", "model", "area", "state", "side", "evidence", "invalidation", "story", "outcome", "mfe", "mae")

OUTCOMES = ("next_area_first", "invalidation_first", "open_at_data_end")

import re

# whole words that mark a calendar / session / clock horizon (forbidden: the outcome is measured by structure across sessions)
_DAY_RE = re.compile(r"\b(days?|sessions?|eod|clock|o'clock|dates?|intraday|expiry|hours?|hrs?|weeks?|months?|tomorrow|overnight|"
                     r"today|market close|next open)\b")   # timeframe labels (15M, 1H) are bar sizes, not horizons


class ReportStandardError(ValueError):
    pass


def chart_max_lines_default():
    from decision3 import settings as S3
    return int(S3.OUTPUT["chart_max_lines"][0])


def validate_lines_view(meta, chart_max_lines=None):
    """P8 clean charts (REPORT_STANDARD §3a): meta["lines_view"] = {"max_lines", "shown": [line keys], "evidence": [line keys],
    "legend": [line keys in the legend], "hidden": n}. The legend lists only the shown lines and never more than `chart_max_lines` (the display
    setting; the value the chart was drawn with, never above the setting passed here); every evidence line is among the shown lines."""
    key = (meta or {}).get("entry_key")
    lv = (meta or {}).get("lines_view")
    if not isinstance(lv, dict):
        raise ReportStandardError(f"chart {key!r}: no lines_view (P8 clean-chart selection missing)")
    limit = int(chart_max_lines if chart_max_lines is not None else chart_max_lines_default())
    used = int(lv.get("max_lines") if lv.get("max_lines") is not None else limit)
    if used > limit:
        raise ReportStandardError(f"chart {key!r}: drawn with max_lines {used} > chart_max_lines {limit}")
    legend, shown = list(lv.get("legend") or []), list(lv.get("shown") or [])
    if len(legend) > used or len(shown) > used:
        raise ReportStandardError(f"chart {key!r}: the legend lists {max(len(legend), len(shown))} lines > chart_max_lines {used}")
    extra = [x for x in legend if x not in shown]
    if extra:
        raise ReportStandardError(f"chart {key!r}: the legend must list only the shown lines (not shown: {', '.join(map(str, extra))})")
    miss = [e for e in lv.get("evidence") or [] if e not in shown]
    if miss:
        raise ReportStandardError(f"chart {key!r}: evidence line(s) {', '.join(map(str, miss))} not shown")
    return True


def validate_chart(meta, chart_max_lines=None):
    """Every required layer present and evaluated; the story has exactly two lines; the clean-chart line selection (legend ≤
    chart_max_lines, only shown lines in the legend, evidence lines shown)."""
    meta = meta or {}
    layers = meta.get("layers") or {}
    missing = [k for k in REQUIRED_LAYERS if not (layers.get(k) or {}).get("evaluated")]
    if missing:
        raise ReportStandardError(f"chart {meta.get('entry_key')!r}: missing layer(s) {', '.join(missing)}")
    story = (layers["story"].get("note") or "").strip().splitlines()
    if len(story) != 2:
        raise ReportStandardError(f"chart {meta.get('entry_key')!r}: the story must be two lines (has {len(story)})")
    validate_lines_view(meta, chart_max_lines)
    return True


NOT_TESTABLE = "not testable — FUT volume missing"


def group_data_status(spot_sessions, fut_sessions):
    """RC5 — the pre-replay data check (REPORT_STANDARD §0): a group is "testable" only if EVERY spot session in it has near-month FUT
    volume. spot_sessions = the group's spot sessions (dates / "YYYY-MM-DD"); fut_sessions = the sessions with near-month FUT volume.
    ⇒ {"status": "testable" | NOT_TESTABLE, "missing": [days], "line": the one line a not-testable group emits}. Never substitutes
    spot volume, never fills a gap."""
    day = lambda x: str(x)[:10]  # noqa: E731
    spot = sorted({day(x) for x in spot_sessions or ()})
    fut = {day(x) for x in fut_sessions or ()}
    missing = [x for x in spot if x not in fut]
    if not spot:
        return {"status": NOT_TESTABLE, "missing": [], "line": f"{NOT_TESTABLE}: no spot session in the group"}
    if missing:
        return {"status": NOT_TESTABLE, "missing": missing,
                "line": f"{NOT_TESTABLE} on {len(missing)} of {len(spot)} sessions: {', '.join(missing)}"}
    return {"status": "testable", "missing": [], "line": f"testable: near-month FUT volume on all {len(spot)} sessions"}


def validate_outcome_rule(rule):
    """{"horizon": "structure", "target": ..., "stop": ...}: structural horizon, never a day / session / clock one."""
    h = str((rule or {}).get("horizon", "")).strip().lower()
    if h != "structure":
        raise ReportStandardError(f"outcome horizon must be 'structure' (got {h!r})")
    for k, v in (rule or {}).items():
        if k == "horizon":
            continue
        text = f"{k} {v}".lower()
        if _DAY_RE.search(text):
            raise ReportStandardError(f"outcome rule {k!r} is day / session / clock based: {v!r}")
    return True


def validate_card(card):
    miss = [f for f in REQUIRED_CARD_FIELDS if card.get(f) in (None, "")]
    if miss:
        raise ReportStandardError(f"card {card.get('entry_key')!r}: missing {', '.join(miss)}")
    if card["outcome"] not in OUTCOMES:
        raise ReportStandardError(f"card {card.get('entry_key')!r}: outcome {card['outcome']!r} not in {OUTCOMES}")
    return True


def validate_report(rep, chart_max_lines=None):
    """rep = {"first_line", "summary_mr", "outcome_rule", "entries": [card], "charts": {entry_key: meta}, "per_model": [...],
    "running_total": [...], "missed_big_moves": [{"chart": ...}], "worst_losses": [{"chart": ...}], "gaps": [...]}."""
    ds = rep.get("data_status")
    if ds is not None and ds.get("status") != "testable":
        raise ReportStandardError(f"group not testable ({ds.get('line')}): emit only that one line, no report")
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
        validate_chart(charts[card["entry_key"]], chart_max_lines)
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
