"""vision/signal_audit.py — signal chart चा vision audit (`signal_check`, structured JSON) + verdict चे नियम (code मध्ये) + खर्च.

🎓 G-COST (≤ $5 / महिना):
  • प्रति signal 1 audit; पहिल्याची confidence < `second_audit_below_conf` (0.6) तरच दुसरा.
  • 1 image (2 panels + overlay, ~1000×700 ≈ 900 image tokens), plain image नाही.
  • System prompt स्थिर आणि `cache_control` सह (model चं किमान cacheable prefix पेक्षा लहान असेल तर cache होत नाही — खर्च `usage` मधून मोजतो).
  • Output लहान JSON (reason ≤ 160 chars), `max_tokens` env ने मर्यादित. Model नाव env `VISION_SIGNAL_MODEL` (कोडमध्ये नाही).
v2 (`signal_check_v2`, TRADE_VISION_PROMPT_V2): trader's playbook system prompt (~2k tokens, cached), JSON v2, chart v2 overlays + signal text
मध्ये अचूक किंमती. Verdict चे नियम code मध्ये (`DISAGREE_RULES` / `GRAY_RULES`, settings ने on/off) — vision चं मत यांपेक्षा जास्त positive
कधीच नाही; 2 audits असहमत ⇒ gray; enum अवैध / API अपयश ⇒ unavailable. जुने records त्यांच्या `prompt_version` (v1) सह तसेच राहतात.
"""
import base64
import json
import os
import time

PROMPT_VERSION = "signal_check_v2_1"
VERDICTS = ("agree", "gray", "disagree")
YN = ("yes", "no")
ENUMS = {
    "htf_trend": ("up", "down", "range", "unclear"),
    "setup_structure": ("up", "down", "range", "unclear"),
    "trend_context": ("with", "against", "range", "unclear"),
    "level_real": ("yes", "no", "unclear"),
    "level_kind": ("swing_origin", "flip", "range_edge", "reference", "mid_range", "magnet", "unclear"),
    "confluence": ("yes", "no", "unclear"),
    "wave_position": ("w2_end", "w4_end", "b_end", "abc_end", "triangle_e", "a_end", "inside_b_or_triangle", "impulse_running", "unclear"),
    "correction_complete": ("yes", "no", "unclear"),
    "false_break_reclaim": YN,
    "reversal_touch": YN, "reversal_reclaim": YN, "reversal_strength": YN,
    "reversal_close_location": ("good", "middle", "bad"),
    "reversal_valid": ("yes", "no", "unclear"),
    "is_breakout_entry": YN,
    "room_to_next_level": ("enough", "tight", "unclear"),
    "time_risk": ("none", "opening", "last_hour", "gap"),
    "false_break_risk": ("low", "medium", "high"),
    "gap_class_agrees": ("yes", "no", "unclear", "no_gap"),
    "gap_behaviour": ("acceptance", "rejection", "undecided", "no_gap"),
    "gap_setup": ("A", "B", "C", "none", "disallowed"),
    "line_structure": ("up", "down", "range", "unclear"),
    "line_vs_candles": ("consistent", "conflict", "unclear"),
    "verdict": VERDICTS,
}
FIELDS = list(ENUMS)[:-1] + ["elliott_note", "verdict", "reason", "confidence"]
SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "string", "enum": list(v)} for k, v in ENUMS.items()},
        "elliott_note": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": FIELDS,
    "additionalProperties": False,
}

# Verdict चे नियम (code मध्ये; vision चं मत यांपेक्षा जास्त positive कधीच नाही). id ⇒ (field, disallowed values). Settings
# `v2_disagree_rules` / `v2_gray_rules` मध्ये चालू ids (dashboard वरून on/off).
# "code:" नियम model च्या field वर नाहीत, code च्या तथ्यांवर (ctx) — `rule_hits(..., ctx)`.
DISAGREE_RULES = {
    "breakout": ("is_breakout_entry", ("yes",)),
    "reversal_invalid": ("reversal_valid", ("no",)),
    "weak_level": ("level_kind", ("mid_range", "magnet")),
    "bad_wave": ("wave_position", ("a_end", "inside_b_or_triangle")),
    "bad_close": ("reversal_close_location", ("bad",)),
    "opening": ("time_risk", ("opening",)),
    "gap_disallowed": ("gap_setup", ("disallowed",)),
    "gap_chase": "code",                                                 # G3 / G5 दिवशी gap दिशेने pullback शिवाय entry
    "gap_b_pdc_accept": "code",                                          # setup B: PDC पलीकडे acceptance असताना gap / trend दिशेने entry
    "wrong_approach": "code",                                            # 2a: bear call पण L वर वरून / bull put पण खालून
    "role_conflict": "code",                                             # 2c: bot-role वि. today_role विरोधी
}
GRAY_RULES = {
    "unclear": None,                                                     # कोणतंही "unclear" (htf_trend वगळून)
    "correction_incomplete": ("correction_complete", ("no",)),
    "tight_room": ("room_to_next_level", ("tight",)),
    "middle_close": ("reversal_close_location", ("middle",)),
    "impulse_running": ("wave_position", ("impulse_running",)),
    "gap_undecided_early": "code",                                       # gap वर्तन undecided आणि signal पहिल्या 6 (15m) bars मध्ये
    "line_conflict": ("line_vs_candles", ("conflict",)),
    "event_day": "code",
    "gap_c_alone": None,                                                 # setup C (जुना gap) आणि confluence नाही
}
SEVERITY = {"agree": 0, "gray": 1, "disagree": 2}
# "unclear ⇒ gray" मधून वगळलेले: htf_trend (spec), आणि v2.1 चे माहितीपर fields (line_structure, gap_class_agrees, line_vs_candles — conflict
# वेगळा नियम) — नाहीतर skip दर विनाकारण वाढतो (review S5).
UNCLEAR_EXEMPT = ("htf_trend", "verdict", "line_structure", "gap_class_agrees", "line_vs_candles")

SYSTEM_PROMPT = """ROLE
You are an experienced discretionary price-action trader auditing one automated trade signal on an NSE index chart (NIFTY).
The trader sells weekly directional credit spreads (bull put / bear call), holds ~2 days, trades 15-minute swings.
You see one image with three panels: top-left = setup timeframe candles, top-right = higher timeframe candles, bottom = a
close-only line chart over a longer lookback. All are cut exactly at the signal moment (no future data). Exact prices of every drawn line are given in the text - never read or invent prices from the image.
Chart legend: thick line "L" = the traded level (green = support, red = resistance); thin blue lines M1/M2 with an up or down
arrow = major levels above / below price (suffix F = role-reversal flip); dotted grey lines = reference levels PDH / PDL / PDC
(previous day high / low / close), PWH / PWL (previous week high / low), OPEN (today's open), ORH / ORL (opening range, the
first 15 minutes, also a faint band); labels joined with "+" are levels that coincide; arrows at the top / bottom edge name
levels outside the visible range; small H / L marks = confirmed swing highs / lows; vertical dotted lines = session starts;
the yellow arrow marks the signal bar; a dashed yellow line, when present, is the invalidation.

1. ENTRY PHILOSOPHY
- Entries only at the END of a pullback (a corrective move) in the direction of the next impulsive move. Never breakouts.
- A breakout entry = buying after price has broken above a resistance / selling after it has broken below a support, or
  entering because price is "running". Treat it as a rule violation even if the bot calls it a level touch.
- A good signal = a real level + a completed correction into it + a logical reversal candle + room to the next opposing level.

2. LEVELS (how the trader draws them)
- Only 2-4 major levels per chart matter. Major = origin of a strong move, a swing where trend changed, a range edge,
  or a role-reversal (flip) level (old resistance now support or vice versa - the strongest kind).
- A level is real if price reacted there 2-3 times with clear rejection (wick + close back), or it is the origin of an
  impulsive leg. Weak/unreal: a single spike, a line in the middle of a range, a level price has crossed back and forth
  many times (a "magnet" - no trade).
- Levels do not weaken with time; they weaken when broken. A level is BROKEN only by a real break (below). PDH/PDL/PDC,
  PWH/PWL, today's open and the opening range are reference levels; confluence of a major level with one of them is stronger.
- Room: the trade needs space to the next opposing level. If the next opposing level is very close (less than about 1
  median range away, see text), the trade is cramped.

3. REAL BREAK vs FALSE BREAK
- Wick beyond a level that closes back inside = FALSE break (a probe; often traps breakout traders - a spring/upthrust).
  A false break INTO the trade's level followed by a reclaim is often the best entry.
- REAL break = close beyond the level by a buffer AND one of: a displacement candle (large body, closes near its extreme),
  the next candle does not reclaim, or a failed retest from the other side. Only a real break invalidates a level.

4. TREND AND STRUCTURE
- Read structure on both panels: higher highs/higher lows = up; lower highs/lower lows = down; overlapping swings = range.
- Higher-timeframe trend is CONTEXT, not a gate: with-trend pullback entries are best; counter-trend entries need a
  completed correction and a strong reversal; in a range, only the range edges are tradable, never the middle.

5. ELLIOTT WAVE (use for position in structure, not prediction)
- Impulsive legs (waves 1, 3, 5, A, C) are fast: large bodies, little overlap, closes near extremes.
  Corrective legs (2, 4, B) are slow and overlapping, with wicks on both sides.
- Tradable: the END of a correction - wave 2 end (into 3), wave 4 end (into 5), B end (into C), end of a full ABC /
  flat / triangle E. Never at the end of the FIRST corrective leg (an A-end): after the first leg against a strong trend
  there is usually a B and a C still to come. Never inside a B wave or inside a triangle. Never on an unclear count.
- Rules: wave 2 never goes beyond the start of wave 1; wave 3 is never the shortest; wave 4 does not overlap wave 1
  (except diagonals); corrections are not 5-wave moves. In an expanded flat, C often sweeps beyond A's end (a false break)
  before reversing - a classic spring.
- If the last leg into the level is still impulsive (big bodies, closes at extremes, accelerating), the correction is
  probably NOT complete yet.

6. REVERSAL CANDLE (logic, not pattern names)
- Judge the reversal as one composite of the last 1-3 candles (first open, highest high, lowest low, last close).
- Four steps: TOUCH (price reaches the level zone), RECLAIM (closes back on the trade's side of the level),
  STRENGTH (a real body/range versus recent candles - not a tiny doji), CLOSE LOCATION (composite closes in the third of
  its range that favours the trade). Close location in the middle (indecision) = wait, not enter.
- Psychology: a long rejection wick at the level shows the opposite side tried and failed; trapped traders' stops fuel
  the reversal. A big candle that closes AWAY from the level in the pullback direction is exhaustion/continuation, not
  a reversal. Harami/inside candles, dojis and spinning tops alone are indecision. A hanging man or inverted hammer alone
  is not a reversal. Shapes like hammer, bullish engulfing, piercing, morning star (and their bearish mirrors) are good
  only when the four steps hold at a real level.
- Bearish reversal signals have weaker statistical evidence than bullish ones - demand clearer steps for bear calls.

7. TIME AND CONTEXT
- The first 15 minutes are noisy (wide bars, gaps) - no entries there. The last hour has thinner follow-through.
- After a gap, the gap edge and the previous close are levels; an entry that requires the gap to fill against the trend
  is weaker.

8. GAPS (overnight opening gaps)
- A gap's type (breakaway, runaway, exhaustion) is mostly known only in hindsight. At the open only context is known:
  size versus ATR, location versus the prior day's range (inside = partial gap, beyond PDH/PDL = full gap), direction
  versus the higher-timeframe trend, and event days. The market's verdict comes in the first 2-6 bars: ACCEPTANCE
  (price holds beyond the level, pullbacks fail) or REJECTION (extension fails, price trades back through the open toward
  the previous close).
- Allowed gap setups (pullback-only):
  A) A gap AGAINST the trend that fails (rejection) -> enter WITH the trend at the end of that failed move, on a valid
     reversal at a real level (PDL/PDH, old gap edge, swing).
  B) A large gap WITH the trend beyond PDH/PDL -> never chase the open; wait for the FIRST pullback to the gap edge
     (old PDH/PDL) or the previous close (full fill) and a valid reversal there. If no pullback comes, no trade.
     Acceptance back beyond the previous close invalidates the idea.
  C) Days later, the edge of an old unfilled gap can act as a pullback level (weak on its own - needs confluence).
- Not allowed: gap-and-go chasing, opening-range breakouts, entering on the break of the first 15-minute candle, any entry
  in the first 15 minutes, fair-value-gap entries.
- Small gaps fill more often than large ones; large, with-trend gaps beyond the prior range fill less often. After a
  large gap expect at most a partial retrace. Gap edges are weak support (price often slices through), so a reversal
  candle is required - never assume the edge holds.
- Event days (policy, budget, major overnight data): be more demanding; gaps on such days are less reliable.
- The gap band on the setup panel is the zone between the previous close and today's open (darker part = filled so far);
  "UG" bands are older unfilled gaps; the faint vertical band is the opening window (09:15-09:30).

9. LINE CHART PANEL
- The bottom panel is a close-only line chart over a longer lookback. Use it to read structure cleanly (swing highs/lows,
  HH/HL vs LH/LL, range) without wick noise, and to see where the signal sits in the bigger swing. Use the candle panels
  for the reversal itself. If the two disagree, say so (gray).
- Level labels may carry today's behaviour: "held S" / "held R" (held as support / resistance today), "broken" with an
  arrow (a real break today). "sH" / "sL" are swing highs / lows; a dotted box marks the 1-3 reversal candles; "INV" is
  the invalidation line.

10. YOUR TASK
Fill the JSON strictly from what the chart and text show. When something cannot be judged, answer "unclear".
verdict: "agree" = follows the rules (real level, completed correction, valid reversal, room, not a breakout);
"gray" = mixed or doubtful; "disagree" = breaks a rule. confidence 0.0-1.0.
elliott_note: one short remark on the wave count, at most 100 characters (empty string when none).
reason: one short sentence in simple Marathi (Devanagari), max 160 characters, naming the deciding factor.
Reply with the JSON object only."""

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
    return int(os.environ.get("VISION_SIGNAL_MAX_TOKENS", 1200))


def estimate_usd(model, image_tokens=1200, system_tokens=2600, text_tokens=700, output_tokens=None):
    """एका audit चा सावध अंदाज (budget आधी तपासायला): cache न धरता, output = max_tokens (thinking सुद्धा output मध्ये मोजलं जातं)."""
    output_tokens = max_output_tokens() if output_tokens is None else output_tokens
    return cost_usd(model, {"input_tokens": image_tokens + system_tokens + text_tokens, "output_tokens": output_tokens})


def _f(x, nd=1):
    return "n/a" if x is None else f"{float(x):,.{nd}f}"


def signal_text(sig):
    """Signal text v2: सगळ्या overlays च्या अचूक किंमती (OHLC वरून), room, वेळ, gap, expiry, bot tags. Image वरून किंमत नाही."""
    tags = sig.get("tags") or {}
    ctx = sig.get("ctx") or {}
    bull = str(sig.get("direction", "")).upper().startswith("BULL")
    ts = sig.get("signal_ts")
    lines = [
        f"Signal: {sig.get('symbol')} | bot {sig.get('bot_label') or sig.get('bot')} | direction {sig.get('direction')} "
        f"({'long / bullish - bull put spread' if bull else 'short / bearish - bear call spread'}) | setup TF {sig.get('setup_tf')} | "
        f"time {ts} IST | spot {_f(sig.get('spot'), 2)}",
        f"Traded level L: {_f(sig.get('level'), 2)} as {sig.get('role')}.",
    ]
    mr = ctx.get("median_range")
    if mr:
        lines.append(f"Median range of the last 20 setup-TF bars: {mr:.1f} points (distances below are in multiples of it; + = above spot).")
    if not ctx:
        lines.append("Context unavailable: reference / major levels, room and time could not be computed. Judge levels only from the "
                     "chart and answer room_to_next_level = unclear.")
    rows = ctx.get("levels") or []
    if rows:
        lines.append("Levels (exact prices from OHLC data, not from the image; coinciding levels joined with +):")
        lines.append("  name | price | position vs spot (x median range) | today_role (how it behaved today, up to the signal)")
        for r in sorted(rows, key=lambda z: -z["price"]):
            d = r.get("dist_mr")
            pos = r.get("position") or ("above" if (d or 0) > 0 else "below")
            tr = r.get("today_role") or r.get("role") or "n/a"
            if r.get("broken_at"):
                tr += f" at {r['broken_at']}"
            if tr.startswith("reclaimed"):
                tr += " (an earlier real break was undone: a completed bar closed back on today's opening side = false break)"
            if r.get("open_bar_breaking") and r.get("held_until"):
                tr += (f" until {r.get('held_until')}; the current OPEN (unfinished) bar is breaking it {r['open_bar_breaking']}")
            lines.append(f"  {r['name']} | {r['price']:,.2f} | {pos} {'n/a' if d is None else f'{d:+.2f}'} x | {tr}")
    ll = ctx.get("l_line")
    if ll:
        brk = ("yes - " + ll["today_role"] + " at " + str(ll["broken_at"])) if ll["broken"] else (
            f"no - it was broken earlier and RECLAIMED at {ll['broken_at']} (back on the opening side: false break)" if ll.get("reclaimed") else "no")
        lines.append(f"Traded level L: price approached L {ll['approach']}; today opened {ll.get('opening_side', '?')} L; earlier today (before the "
                     f"last 3 bars) L was {ll['earlier_role']}; real break today (completed bars only): {brk}; price is now {ll.get('spot_side', '?')} L.")
    room = ctx.get("room") or {}
    if not ctx:
        pass
    if not ctx:
        pass
    elif room.get("next_name"):
        tight = room.get("next_mr") is not None and room["next_mr"] < TIGHT_ROOM_MR
        lines.append(f"Room: next opposing level in the trade direction = {room['next_name']} at {room['next_price']:,.2f}"
                     + (" (broken today = flip, now acts against the trade)" if room.get("next_flip") else f" ({room.get('next_role')})")
                     + f", {_f(room.get('next_mr'), 2)} x median range away" + (f" - ROOM TIGHT ({room['next_name']})." if tight else "."))
    else:
        lines.append("Room: no opposing reference / major level in the trade direction within the data.")
    if ctx and ctx.get("recent_breaks"):
        lines.append("Levels broken IN THE TRADE DIRECTION by the signal bar or the 3 bars before it: "
                     + ", ".join(f"{x['name']} at {x['at']}" for x in ctx["recent_breaks"]) + " (= breakout entry).")
    if room.get("invalidation_mr") is not None:
        lines.append(f"Invalidation: {_f(ctx.get('invalidation', sig.get('invalidation')), 2)} ({ctx.get('invalidation_source', 'bot')}), "
                     f"{room['invalidation_mr']:.2f} x median range away.")
    sb = ctx.get("signal_bar") or {}
    if sb:
        if ctx.get("spot_signal") is not None and abs(float(ctx["spot_signal"]) - float(ctx.get("spot") or 0)) > 1e-9:
            lines.append(f"Spot at signal {ctx['spot_signal']:,.2f}; at evaluation (bar close) {ctx['spot']:,.2f} - levels / room use the latter.")
        lines.append(f"Signal bar ({sb['tf']}m) {sb['start']}-{sb['end']}: " + (
            f"closed (evaluated at {sb['evaluated_at']})." if sb["closed"] else
            f"NOT CLOSED yet ({sb['elapsed']}/{sb['tf']} min elapsed) - the reversal candle is not final."))
    mins = ctx.get("minutes_since_open")
    if mins is not None:
        flag = {"opening": " - FIRST 15 MINUTES", "last_hour": " - LAST HOUR"}.get(ctx.get("time_flag"), "")
        lines.append(f"Time: {mins} minutes since the 09:15 open{flag}.")
    op = ctx.get("opening") or {}
    if op and not op.get("or_complete"):
        lines.append("Opening range is not complete yet (signal inside the first 15 minutes).")
    lines += gap_lines(ctx.get("gap_ctx"))
    if ctx.get("expiry_days") is not None:
        lines.append(f"Weekly expiry in {ctx['expiry_days']} calendar day(s).")
    if tags:
        lines.append("Bot tags: " + ", ".join(f"{k}={v}" for k, v in sorted(tags.items())))
    lines.append("Audit this signal against the playbook and fill the JSON.")
    return "\n".join(lines)


def _gap_desc(g):
    if g.get("atr_missing"):
        return " (ATR unavailable - fewer than 6 prior days)"
    if g["class"] == "G0":
        return " (noise, no gap)"
    tr = (f"{'WITH' if g['with_trend'] else 'AGAINST'} the daily trend ({g['trend']})" if g["trend"] in ("up", "down")
          else f"no clear daily trend ({g['trend']})")
    return f", {g['direction']}, {g['location']} the prior day's range, {tr}"


def gap_lines(g):
    """Signal text: gap संदर्भ (OHLC वरून अचूक आकडे)."""
    if not g:
        return ["Gap context: unavailable."]
    if g.get("error") or g.get("pdc") is None:
        return [f"Gap context: unavailable ({g.get('error') or g.get('reason')}). Event: {g.get('event') or 'none'}."]
    out = [f"Gap today: open {g['open']:,.2f} vs previous close {g['pdc']:,.2f} = {g['gap']:+,.2f} ({g['gap_pct']:+.2f}%), "
           f"{_f(g.get('gap_atr'), 2)} x ATR14 (daily ATR {_f(g.get('atr14'), 1)}) -> class {g['class']}"
           + _gap_desc(g)
           + (f", prior 5-session leg {g['leg_atr']:+.1f} x ATR" if g.get("leg_atr") is not None else "") + "."]
    if g["class"] != "G0":
        out.append(f"Gap fill so far: {g['fill_pct']:.0f}%; previous close touched: {'yes' if g['pdc_touched'] else 'no'}; acceptance beyond the "
                   f"previous close: {'yes at ' + str(g['pdc_acceptance_at']) if g['pdc_acceptance'] else 'no'}. Opening behaviour (first "
                   f"{g['bars_15m_done']} completed 15m bars, re-decided on every closed bar): {g['behaviour']}"
                   + (f" at {g['behaviour_at']}" if g.get("behaviour_at") else "")
                   + (f" (history: {', '.join(g['behaviour_history'])})" if g.get("behaviour_history") else "") + "."
                   + (f" Gap edge: {g['edge']:,.2f}." if g.get("edge") else ""))
    for u in (g.get("old_gaps") or [])[:4]:
        out.append(f"Old unfilled gap ({u['day']}, {u['age']} sessions ago, gap {u['dir']}): remaining {u['low']:,.2f}-{u['high']:,.2f}, "
                   f"{u['filled_pct']:.0f}% filled.")
    out.append(f"Event day: {g.get('event') or 'none'}.")
    return out


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
        canon = {x.lower(): x for x in allowed}                          # gap_setup "A/B/C" — case-insensitive, मूळ रूपात
        if v not in canon:
            return None, f"{k} अवैध: {raw.get(k)!r}"
        out[k] = canon[v]
    try:
        conf = float(raw.get("confidence"))
    except (TypeError, ValueError):
        return None, "confidence अवैध"
    if conf != conf:
        return None, "confidence NaN"
    out["confidence"] = min(1.0, max(0.0, conf))
    note = raw.get("elliott_note")
    out["elliott_note"] = (str(note).strip()[:100] or None) if note not in (None, "null") else None
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


TIGHT_ROOM_MR = 1.0                                                     # spec: पुढचा विरोधी level < ~1 median range ⇒ cramped


def apply_facts(a, ctx, direction=None):
    """Code ला आधीच माहीत असलेली तथ्यं (OHLC वरून) model च्या उत्तरावर लादणे — नियम model ने ती पुन्हा लिहिण्यावर अवलंबून नकोत.
    फक्त कडक दिशेने: पहिली 15 मिनिटं ⇒ time_risk = opening; room < 1 × median range ⇒ tight; संदर्भ नाही ⇒ room unclear. रिटर्न (a, बदल)."""
    if not a:
        return a, []
    a, ch = dict(a), []
    if not ctx:
        if a.get("room_to_next_level") != "unclear":
            a["room_to_next_level"] = "unclear"
            ch.append("room=unclear (context नाही)")
        return a, ch
    sb = ctx.get("signal_bar") or {}
    if sb and not sb.get("closed") and a.get("reversal_valid") == "yes":   # तुमचा नियम 1c: signal bar बंद नाही ⇒ reversal unclear ⇒ gray
        a["reversal_valid"] = "unclear"
        ch.append(f"reversal_valid=unclear (signal bar {sb['start']} बंद नाही, {sb['elapsed']}/{sb['tf']} min)")
    if ctx.get("time_flag") == "opening" and a.get("time_risk") != "opening":
        a["time_risk"] = "opening"
        ch.append("time_risk=opening")
    why = None
    rb = ctx.get("recent_breaks") or []
    if direction and rb:                                                 # तुमचा नियम 2b: signal bar / मागचे 3 bars नी trade दिशेने level तोडला
        why = "recent real break in trade direction: " + ", ".join(f"{x['name']} {x['at']}" for x in rb)
    if why and a.get("is_breakout_entry") != "yes":
        a["is_breakout_entry"] = "yes"
        ch.append(f"is_breakout_entry=yes ({why})")
    nm = (ctx.get("room") or {}).get("next_mr")
    if nm is not None and nm < TIGHT_ROOM_MR and a.get("room_to_next_level") == "enough":
        a["room_to_next_level"] = "tight"
        ch.append(f"room=tight ({nm:.2f}x)")
    return a, ch


# Code-only pre-verdict: vision "सगळं ठीक / agree" म्हणाला असता तरी code चे नियम काय म्हणतात (vision शिवाय, खर्च 0)
NEUTRAL = {"htf_trend": "up", "setup_structure": "range", "trend_context": "with", "level_real": "yes", "level_kind": "swing_origin",
           "confluence": "yes", "wave_position": "abc_end", "correction_complete": "yes", "false_break_reclaim": "no", "reversal_touch": "yes",
           "reversal_reclaim": "yes", "reversal_strength": "yes", "reversal_close_location": "good", "reversal_valid": "yes",
           "is_breakout_entry": "no", "room_to_next_level": "enough", "time_risk": "none", "false_break_risk": "low",
           "gap_class_agrees": "yes", "gap_behaviour": "no_gap", "gap_setup": "none", "line_structure": "up", "line_vs_candles": "consistent",
           "elliott_note": "", "verdict": "agree", "reason": "", "confidence": 1.0}


def pre_verdict(ctx, direction, disagree_rules=None, gray_rules=None):
    """(verdict, {"disagree": […], "gray": […]}, code तथ्यं) — फक्त OHLC वरून (vision शिवाय)."""
    a, facts = apply_facts(dict(NEUTRAL), ctx, direction)
    d, g = rule_hits(a, disagree_rules, gray_rules, ctx, direction)
    return code_verdict(a, disagree_rules, gray_rules, ctx, direction), {"disagree": d, "gray": g}, facts


def rule_hits(a, disagree_rules=None, gray_rules=None, ctx=None, direction=None):
    """(disagree ids, gray ids) जे या audit ला लागतात. None ⇒ सगळे नियम चालू."""
    dr = DISAGREE_RULES if disagree_rules is None else {k: v for k, v in DISAGREE_RULES.items() if k in disagree_rules}
    gr = GRAY_RULES if gray_rules is None else {k: v for k, v in GRAY_RULES.items() if k in gray_rules}
    code = code_facts(ctx, direction)
    d = [k for k, spec in dr.items() if (code.get(k) if spec == "code" else a.get(spec[0]) in spec[1])]
    g = []
    for k, spec in gr.items():
        if k == "unclear":
            if any(a.get(f) == "unclear" for f in ENUMS if f not in UNCLEAR_EXEMPT):
                g.append(k)
        elif k == "gap_c_alone":
            if a.get("gap_setup") == "C" and a.get("confluence") != "yes":
                g.append(k)
        elif spec == "code":
            if code.get(k) or (k == "gap_undecided_early" and a.get("gap_behaviour") == "undecided"
                               and int(((ctx or {}).get("gap_ctx") or {}).get("bars_15m_done") or 0) < 6):
                g.append(k)
        elif a.get(spec[0]) in spec[1]:
            g.append(k)
    return d, g


def code_facts(ctx, direction=None):
    """Gap नियमांची code-तथ्यं (OHLC वरून, model वर अवलंबून नाहीत)."""
    g = (ctx or {}).get("gap_ctx") or {}
    out = {"event_day": bool(g.get("event"))}
    ll = (ctx or {}).get("l_line") or {}
    if direction and ll:
        bull_ = str(direction).upper().startswith("BULL")
        # 2a: bear call ⇒ किंमत L कडे खालून; bull put ⇒ वरून. उलट ⇒ disagree
        out["wrong_approach"] = ll.get("approach") == ("from below" if bull_ else "from above")
        # 2c: L चा bot-role आणि आजचं वागणं विरोधी (resistance म्हणून trade पण held_as_support, आणि उलट)
        br, tr_ = ll.get("bot_role"), ll.get("today_role")
        out["role_conflict"] = (br == "RESISTANCE" and tr_ == "held_as_support") or (br == "SUPPORT" and tr_ == "held_as_resistance")
    if not g.get("has_gap"):
        return out
    bull = str(direction or "").upper().startswith("BULL")
    with_gap = (g.get("direction") == "up") == bull
    mr = (ctx or {}).get("median_range") or 0.0
    lvl = (ctx or {}).get("level")
    near = lvl is not None and any(x is not None and abs(float(lvl) - float(x)) <= 0.5 * mr for x in (g.get("pdc"), g.get("edge")))
    out["gap_chase"] = g.get("class") in ("G3", "G5") and with_gap and float(g.get("fill_pct") or 0) < 25 and not near
    out["gap_b_pdc_accept"] = g.get("class") in ("G3", "G5") and with_gap and bool(g.get("pdc_acceptance"))
    out["gap_undecided_early"] = g.get("behaviour") == "undecided" and int(g.get("bars_15m_done") or 0) < 6
    return out


def code_verdict(a, disagree_rules=None, gray_rules=None, ctx=None, direction=None):
    """एका audit चा verdict: नियमांनी ठरलेली पातळी किंवा vision चा स्वतःचा verdict — जो जास्त कडक तो (नियमांपेक्षा positive कधीच नाही)."""
    if not a:
        return "unavailable"
    d, g = rule_hits(a, disagree_rules, gray_rules, ctx, direction)
    floor = "disagree" if d else ("gray" if g else "agree")
    own = a.get("verdict") if a.get("verdict") in SEVERITY else "gray"
    return max(floor, own, key=SEVERITY.get)


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


def audit(client, png, sig, model, second_below=0.6, effort=None, thinking=None, on_usage=None, budget_ok=None, disagree_rules=None,
          gray_rules=None):
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
        data, facts = apply_facts(data, sig.get("ctx"), sig.get("direction"))
        if facts:
            data["code_overrides"] = facts
        out["audits"].append(data)
        cx, dr = sig.get("ctx"), sig.get("direction")
        out["verdicts"].append(code_verdict(data, disagree_rules, gray_rules, cx, dr))
        out.setdefault("rule_hits", []).append(dict(zip(("disagree", "gray"), rule_hits(data, disagree_rules, gray_rules, cx, dr))))
    out["verdict"] = combine(out["verdicts"])
    if len(out["verdicts"]) == 2 and out["verdicts"][1] == "unavailable" and out["verdict"] == "agree":
        out["verdict"] = "gray"                                          # कमी confidence चा agree, दुसरा audit अयशस्वी ⇒ entry नाही
    confs = [a["confidence"] for a in out["audits"]]
    out["confidence"] = round(sum(confs) / len(confs), 3) if confs else None
    out["cost_usd"] = round(out["cost_usd"], 6)
    return out
