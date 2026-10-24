"""vision/card_summary.py — the simple approval card (Abhi: "this message is hard to understand; simplify it").

Setting `approval_card_layout` (vision bot settings; decision3/settings.py OUTPUT): "classic" (default) = today's card byte-for-byte;
"summary" = five short lines on top, then today's details unchanged below "── details ──":

  🟡 NIFTY · bear call · Label A — घ्यायचा?                      (❌ … entry नाही (Vision असहमत) · ✅ … · ℹ️ … ; 🧪 TEST tag)
  📍 Supply 22,544–22,622 (1H) · आत्ता 22,489 (≈55 pts खाली)      (+ entry / SL / target only when the signal carries them)
  📋 Reader: ✓ trend ✓ area ✓ handover(fast) ✓ commitment+volume ✓ 5M CHoCH · + RSI div, confluence
  👁 Vision: ✅ सहमत — "<first sentence of Vision's reason, ≤ 90 characters>"
  👉 ✅ घ्या · ✏️ फक्त entry बदला · ❌ नको (कारण)   ⏱ 10 मिनिटं (09:55 पर्यंत)

Every value is read from the signal row / its gate tags / the engine row's reader facts (engine3_live.reader_facts ⇒
paper/engine_entry.engine_gate_tags "reader": the layer 6a evidence list as the engine wrote it). A missing value ⇒ that piece is left
out (never guessed). No rule, no score, no new number: the reader line only spells out what the evidence list says — "required:
present" is the fired model's own conditions (DECISIONS 54, `label_rule = model`; the legacy 6a what-if: handover + commitment with its
volume comparison + LTF CHoCH, decision3/method.evidence_list) and the confirming pieces are the ones it marks present. Display only: no decision, gate, order or button changes here.
"""
import html
import json
import math
import re

import pandas as pd

LAYOUT_KEY = "approval_card_layout"
LAYOUTS = ("classic", "summary")
REASON_MAX = 90                                                          # Vision's reason on the summary: one line (full text in details)
PA_MAX = 240                                                             # display: the card's one PA evidence line (full list in the tags)
CONFIRM_WORDS = {"volume_growing": "volume growing", "rsi_divergence": "RSI div", "confluence": "confluence",
                 "correction_line_closed_through": "line closed through",
                 "counter_channel_broken": "counter channel broken"}   # decision3/method.CONFIRMING + DECISIONS 54's fifth piece
VERDICT = {"agree": ("✅", "सहमत"), "gray": ("🟡", "संदिग्ध"), "disagree": ("❌", "असहमत"), "unavailable": ("⚪", "उपलब्ध नाही")}
NAMES = {"entry": "entry", "sl": "SL", "target": "target"}
TF_NAME = {"D": "Daily", "1D": "Daily", "W": "Weekly", "60M": "1H"}


def layout(value=None):
    """Setting ⇒ "classic" / "summary"; a settings dict ⇒ its LAYOUT_KEY. Empty / unknown ⇒ "classic" (today's card)."""
    if isinstance(value, dict):
        value = value.get(LAYOUT_KEY)
    v = str(value or "").strip().lower()
    return v if v in LAYOUTS else LAYOUTS[0]


def _tags(row):
    t = row.get("tags")
    if isinstance(t, dict):
        return t
    try:
        t = json.loads(row.get("setup_json") or "{}").get("tags")
    except (ValueError, TypeError, AttributeError):
        return {}
    return t if isinstance(t, dict) else {}


def _gate(tags):
    g = tags.get("gate")
    return g if isinstance(g, dict) else {}


def _num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _px(x):
    """22677.0 ⇒ "22,677"; 22677.5 ⇒ "22,677.5" (the value as given, never rounded to a different price)."""
    s = f"{x:,.2f}".rstrip("0").rstrip(".")
    return s


def _pt(x):
    """Area / level / last price in whole points, as today's card prints a band (plain_text.band_range)."""
    return f"{x:,.0f}"


def short_reason(text, limit=REASON_MAX):
    """Vision's reason ⇒ its first sentence on one line, at most `limit` characters (cut at a word, "…"). Empty ⇒ ""."""
    t = " ".join(str(text or "").split())
    if not t:
        return ""
    m = re.match(r"(.+?[.!?।])(?=\s|$)", t)
    s = m.group(1) if m else t
    if len(s) > limit:
        cut = s[:limit - 1]
        sp = cut.rfind(" ")
        s = (cut[:sp] if sp >= limit // 2 else cut).rstrip(" ,;:—-") + "…"
    return s


def _area(row, g):
    a = [_num(x) for x in (g.get("area") or [])[:2]]
    return sorted(a) if len(a) == 2 and None not in a else None


def _area_tf(row, g, area):
    """The area's own timeframe when the engine gave its areas (the traded area's tf, e.g. 1H); else the setup TF."""
    for x in g.get("areas") or []:
        if isinstance(x, dict) and _num(x.get("lo")) is not None and _num(x.get("hi")) is not None and area is not None \
                and abs(float(x["lo"]) - area[0]) < 1e-6 and abs(float(x["hi"]) - area[1]) < 1e-6 and x.get("tf"):
            return TF_NAME.get(str(x["tf"]).upper(), str(x["tf"]))
    tf = str(row.get("setup_tf") or "").strip()
    return TF_NAME.get(tf.upper(), tf)


def _spot(row):
    ctx = row.get("ctx") if isinstance(row.get("ctx"), dict) else {}
    s = _num(ctx.get("spot"))
    return s if s is not None else _num(row.get("spot"))


def object_words(tags, bull):
    """DECISIONS 41 / addition C: the engine object in plain words — "broken 1H line at 55,710 (rising line of lows, broken down),
    retest from below"; "1H range upper edge 55,900–56,010"; "broken 1H area 55,600–55,700, retest from below". None ⇒ an ordinary
    area (the caller's own wording). Never an area band for a line. Not HTML-escaped."""
    try:
        t = tags or {}
        ln = t.get("entry_line") if isinstance(t.get("entry_line"), dict) else None
        frm = "below" if not bull else "above"                           # bear call: a line broken down, retested from below
        if ln is not None or str(t.get("entry_object") or "") == "broken_line":
            ln = ln or {}
            tf = TF_NAME.get(str(ln.get("tf") or "").upper(), ln.get("tf"))
            v = _num(ln.get("value"))
            if v is None:
                a = [_num(x) for x in ((t.get("gate") or {}).get("area") or [])[:1]]
                v = a[0] if a else None
            fam = str(ln.get("family") or "").strip()
            brk = {"down": "broken down", "up": "broken up"}.get(str(ln.get("break_side") or ""), "broken")
            det = ", ".join(x for x in (fam + (" (channel parallel)" if ln.get("parallel") and "parallel" not in fam else ""), brk) if x)
            return (f"broken {tf + ' ' if tf else ''}line" + (f" at {_pt(v)}" if v is not None else "") + (f" ({det})" if det else "")
                    + f", retest from {frm}")
        g = t.get("gate") if isinstance(t.get("gate"), dict) else {}
        a = [_num(x) for x in (g.get("area") or [])[:2]]
        band = f"{_pt(min(a))}–{_pt(max(a))}" if len(a) == 2 and None not in a else ""
        tfa = next((TF_NAME.get(str(x.get("tf")).upper(), x.get("tf")) for x in g.get("areas") or []
                    if isinstance(x, dict) and x.get("tf") and x.get("tf") != "line" and len(a) == 2 and None not in a
                    and _num(x.get("lo")) == min(a) and _num(x.get("hi")) == max(a)), None)
        re_ = t.get("entry_range_edge") if isinstance(t.get("entry_range_edge"), dict) else None
        if re_:
            tf = TF_NAME.get(str(re_.get("tf") or "").upper(), re_.get("tf"))
            return f"{tf + ' ' if tf else ''}range {re_.get('edge')} edge {band}".strip()
        if str(t.get("entry_object") or "") == "broken_area":
            return f"broken {tfa + ' ' if tfa else ''}area {band}, retest from {frm}".replace("  ", " ")
    except Exception:                                                    # noqa: BLE001 — display only
        return None
    return None


def line_where(row, ticket=None):
    """📍 area (or level) + its TF · entry / SL / target when the signal carries them · last price and its distance to the area."""
    tags = _tags(row)
    g = _gate(tags)
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    area = _area(row, g)
    tf = _area_tf(row, g, area)
    tfs = f" ({html.escape(tf)})" if tf else ""
    lvl = _num(row.get("level"))
    ow = object_words(tags, bull) if (tags.get("engine") or g.get("mode") == "engine") else None
    if ow is not None and area is not None:                              # DECISIONS 41: a line is a line, never "Supply X–X"
        out = [f"📍 {html.escape(ow)}"]
        lo, hi = area
    elif area is not None:
        out = [f"📍 {'Demand' if bull else 'Supply'} {_pt(area[0])}–{_pt(area[1])}{tfs}"]
        lo, hi = area
    elif lvl is not None:
        out = [f"📍 {'Support' if bull else 'Resistance'} {_pt(lvl)}{tfs}"]
        lo = hi = lvl
    else:
        out = ["📍 level: NA"]
        lo = hi = None
    src = ticket if ticket is not None else g
    ref = " (ref)" if ticket is None or ticket.get("src") == "engine" else ""     # Abhi RR2: engine SL / target = reference (info)
    lv = [(k, _num(src.get(k))) for k in ("entry", "sl", "target")]
    if any(v is not None for _, v in lv):
        out.append(" · ".join(f"{NAMES[k]} {_px(v)}" for k, v in lv if v is not None)
                   + (ref if any(v is not None for k, v in lv if k != "entry") else ""))
    sp = _spot(row)
    now = "आत्ता" if ticket is None else "signal वेळी"                   # the ✏️ ticket comes minutes later: its spot is the signal's
    if sp is not None and lo is not None:
        if sp < lo:
            out.append(f"{now} {_pt(sp)} (≈{lo - sp:,.0f} pts खाली)")
        elif sp > hi:
            out.append(f"{now} {_pt(sp)} (≈{sp - hi:,.0f} pts वर)")
        else:
            out.append(f"{now} {_pt(sp)} (area मध्ये)" if area is not None else f"{now} {_pt(sp)} (level वर)")
    return " · ".join(out)


def line_reader(row):
    """📋 the reader's pieces from the engine's own evidence list; non-engine signals say so (no reading is invented for them)."""
    tags = _tags(row)
    g = _gate(tags)
    if tags.get("test_only"):
        return "📋 Reader: — (TEST signal, no engine reading)"
    if tags.get("manual"):
        return "📋 Reader: — (your manual signal)"
    if not (tags.get("engine") or g.get("mode") == "engine"):
        return "📋 Reader: — (bot's own signal)"
    rd = g.get("reader") if isinstance(g.get("reader"), dict) else {}
    ev = rd.get("evidence_list") if isinstance(rd.get("evidence_list"), dict) else {}
    mark = {True: "✓", False: "✗"}
    parts = [f"{mark[rd[k]]} {k}" for k in ("trend", "area") if isinstance(rd.get(k), bool)]
    ltf = f"{rd['ltf']} CHoCH" if rd.get("ltf") else "LTF CHoCH"
    if ev.get("label_rule") == "model" and ev.get("required") == "present":   # DECISIONS 54: the required set = the model's own
        parts.append("✓ " + html.escape(str(ev.get("required_set") or "the model's own conditions"), quote=False))   # conditions
    elif ev.get("required") == "present":                                # method §5 legacy 6a: the required set, as the engine read it
        fast = "(fast)" if rd.get("handover_form") == "sharp_reversal" else ""
        parts += [f"✓ handover{fast}", "✓ commitment+volume", f"✓ {html.escape(ltf)}"]
    elif ev.get("required") == "absent":
        parts.append(f"✗ required set (handover / commitment+volume / {html.escape(ltf)})")
    conf = ev.get("confirming") if isinstance(ev.get("confirming"), dict) else {}
    plus = [w for k, w in CONFIRM_WORDS.items() if conf.get(k) == "present"]
    if not parts and not plus:
        return "📋 Reader: NA (the engine's evidence list is not on this signal)"
    return "📋 Reader: " + " ".join(parts) + (" · + " + ", ".join(plus) if plus else "")


def line_vision(res, rejected=False):
    res = res or {}
    v = res.get("verdict") or "unavailable"
    e, mr = VERDICT.get(v, ("⚪", str(v)))
    a = (res.get("audits") or [None])[0]
    r = short_reason(a.get("reason")) if isinstance(a, dict) else ""
    q = f'"{html.escape(r)}"' if r else ""
    if rejected and q:                                                   # Abhi's rejected layout: the verdict is already on line 1
        return f"👁 Vision: {q}"
    return f"👁 Vision: {e} {mr}" + (f" — {q}" if q else "")


def _hm(deadline):
    try:
        return pd.Timestamp(deadline).strftime("%H:%M") if deadline else None
    except (ValueError, TypeError):
        return None


def line_you(status, deadline=None, window_min=None, modify=True, buttons=True, ticket=False):
    """👉 what Abhi does: the buttons the card really carries (✏️ only when there is one) + the deadline; otherwise nothing."""
    if status != "PENDING_HUMAN":
        return "👉 तुमच्याकडून: काही नाही"
    hm = _hm(deadline)
    if not buttons:
        return "👉 बटणं नाहीत ⇒ " + (f"{hm} ला " if hm else "") + "timeout नियम"
    b = ["✅ घ्या"] + (["✏️ entry पुन्हा बदला" if ticket else "✏️ फक्त entry बदला"] if modify else []) + ["❌ नको (कारण)"]
    t = f"⏱ {int(window_min)} मिनिटं" + (f" ({hm} पर्यंत)" if hm else "") if window_min else (f"⏱ {hm} पर्यंत" if hm else "")
    return "👉 " + " · ".join(b) + (f"   {t}" if t else "")


MARK = {True: "✓", False: "✗", None: "NA", "present": "✓", "absent": "✗", "na": "NA", "✓": "✓", "✗": "✗", "NA": "NA", "yes": "✓",
        "no": "✗"}


def trigger_line(tags):
    """DECISIONS 37: the 5M trigger in plain words — "Trigger 5M: E1 candle 10:05–10:10, traded into the refined base ✓, close 55,720.7;
    context = last closed 15M bar 09:45" (E4 (b): "at the retested object"). "" for a 15M-trigger signal (the card as before). Every value
    from the tags; display only; not HTML-escaped."""
    try:
        t = tags or {}
        if str(t.get("entry_trigger_tf") or "").upper() != "5M":
            return ""
        tr = t.get("entry_trigger") if isinstance(t.get("entry_trigger"), dict) else {}
        oh = tr.get("ohlc") if isinstance(tr.get("ohlc"), dict) else {}
        m = str(t.get("entry_model") or "").upper()
        when = ""
        if tr.get("ts") and tr.get("bar_end"):
            when = f" {str(tr['ts'])[11:16]}–{str(tr['bar_end'])[11:16]}"
        g = _gate(t)
        rb = g.get("refined") if isinstance(g.get("refined"), dict) else None
        lo, hi = _num(oh.get("low")), _num(oh.get("high"))
        if str(t.get("entry_object") or "").startswith("broken"):
            where = "at the retested object ✓"
        elif rb and lo is not None and hi is not None and _num(rb.get("lo")) is not None:
            ok = lo <= float(rb["hi"]) and hi >= float(rb["lo"])
            where = "traded into the refined base " + ("✓" if ok else "✗")
        else:
            where = "traded into the area"
        c = _num(oh.get("close")) if oh else _num(t.get("entry_ref"))
        ctx = tr.get("context_bar_ts")
        return (f"Trigger 5M: {m + ' ' if m else ''}candle{when}, {where}" + (f", close {_px(c)}" if c is not None else "")
                + (f"; context = last closed 15M bar {str(ctx)[11:16]}" if ctx else ""))
    except Exception:                                                    # noqa: BLE001 — display only
        return ""


def model_label(tags):
    """Engine entry model of the signal ("E1 — Aggressive"), or "" for every other signal (the card stays today's)."""
    try:
        m = str((tags or {}).get("entry_model") or "").strip().upper()
        if not m:
            return ""
        lab = str(tags.get("entry_label") or "").strip()
        if lab:
            return lab
        name = str(tags.get("entry_name") or "").strip()
        return f"{m} — {name}" if name else m
    except Exception:                                                    # noqa: BLE001 — display only
        return ""


def _mark(v):
    k = v.strip().lower() if isinstance(v, str) else v
    if isinstance(v, str) and v.strip() in MARK:
        return MARK[v.strip()]
    try:
        return MARK.get(k, str(v))
    except TypeError:                                                     # unhashable ⇒ as text
        return str(v)


def evidence_parts(ev):
    """The entry's 6a evidence list as plain "<mark> <name>" pieces, copied as given: a dict (nested dicts flattened), a list of
    {name / label / key, mark / state / value / present} items, (name, mark) pairs or plain strings. Unreadable ⇒ []. Never raises."""
    try:
        parts = []

        def walk(x, pre=""):
            if isinstance(x, dict):
                for k, v in x.items():
                    if isinstance(v, (dict, list, tuple)):
                        walk(v, f"{pre}{k}: " if k not in ("confirming", "items") else pre)
                    else:
                        parts.append(f"{_mark(v)} {pre}{str(k).replace('_', ' ')}")
            elif isinstance(x, (list, tuple)):
                for it in x:
                    if isinstance(it, dict):
                        nm = next((it[k] for k in ("name", "label", "key", "piece") if it.get(k) is not None), None)
                        mk = next((it[k] for k in ("mark", "state", "status", "value", "present") if k in it), None)
                        parts.append(f"{_mark(mk)} {pre}{str(nm).replace('_', ' ')}" if nm is not None else str(it))
                    elif isinstance(it, (list, tuple)) and len(it) == 2:
                        parts.append(f"{_mark(it[1])} {pre}{str(it[0]).replace('_', ' ')}")
                    else:
                        parts.append(str(it))
            elif x not in (None, ""):
                parts.append(str(x))
        walk(ev)
        return [p for p in parts if p.strip()]
    except Exception:                                                    # noqa: BLE001 — display only
        return []


def evidence_text(ev, limit=300):
    """The entry's 6a evidence list as one plain line ("✓ handover · ✗ volume growing · NA confluence") — `evidence_parts` joined.
    Empty / unreadable ⇒ "". Never raises."""
    t = " · ".join(evidence_parts(ev))
    return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"


def model_lines(tags, full=False):
    """Card details for an engine entry model: its invalidation (info — the trade's SL / target are the dashboard's) and its evidence.
    Not an entry-model signal ⇒ [] (today's card). HTML-safe. full (DECISIONS 52: the details reply under the card) ⇒ nothing shortened."""
    lab = model_label(tags)
    if not lab:
        return []
    out = []
    big = 1 << 20
    st = " ".join(str(tags.get("entry_story") or "").split())
    if st:                                                               # model C (DECISIONS 32, C-10): the one-line story
        out.append(f"🌊 {html.escape(st[:big if full else 400])}")
    inv = tags.get("entry_invalidation")
    if isinstance(inv, dict):
        px = _num(inv.get("price"))
        rule = " ".join(str(inv.get("rule") or "").split())
        if px is not None or rule:
            out.append(f"🧷 {html.escape(lab)} invalidation (info): " + (_px(px) if px is not None else "NA")
                       + (f" — {html.escape(rule[:big if full else 160])}" if rule else "") + " · trade SL / target = dashboard")
    elif _num(inv) is not None:
        out.append(f"🧷 {html.escape(lab)} invalidation (info): {_px(_num(inv))} · trade SL / target = dashboard")
    ev = evidence_text(tags.get("entry_evidence"), limit=big if full else 300)
    if ev:                                                               # layer 6 / L6-a: the entry's own A / B label on every layout
        g = _gate(tags)
        gl = f" (label {g['grade']})" if g.get("grade") in ("A", "B") else ""
        el = entry_evidence_list(tags)
        if isinstance(el.get("evidence_count"), int):                    # DECISIONS 58: the count, never a label
            gl = f" ({el['evidence_count']} of {el.get('evidence_of', 5)})"
        out.append(f"📋 {html.escape(lab)} evidence{gl}: {html.escape(ev)}")
    return out


PA_TRACKS = ("T1", "T2", "T3", "T4", "T5", "T6", "T7")                  # decision3/pa_evidence.TRACK_ORDER (the standard's order)


def pa_brief(rows, limit=PA_MAX):
    """T9: the entry's PA evidence (decision3/pa_evidence rows) as one plain line — the first fact of each track in the standard's
    order, its bracketed detail left out (the full list stays in the signal's tags). Empty / unreadable ⇒ "". Never raises."""
    try:
        first = {}
        for r in rows or ():
            if isinstance(r, dict) and r.get("track") in PA_TRACKS and r.get("text") and r["track"] not in first:
                first[r["track"]] = re.sub(r"\s*\([^()]*\)", "", str(r["text"])).strip()
        t = " · ".join(first[k] for k in PA_TRACKS if first.get(k))
        return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"
    except Exception:                                                    # noqa: BLE001 — display only
        return ""


def pa_lines(tags):
    """The card's PA evidence line (listed, never blocks) for an engine entry model; [] when none. HTML-safe. The caption builder puts it
    last before the tail, so it is the first detail dropped when the 1024 caption is full (today's lines never give way to it)."""
    lab = model_label(tags)
    b = pa_brief(tags.get("entry_pa_evidence")) if lab else ""
    return [f"🧩 {html.escape(lab)} PA evidence (listed, never blocks): {html.escape(b)}"] if b else []


# ------------------------------------------------------------------------------------------------ DECISIONS 52 (O-4): engine-entry card
# The engine-entry card's caption is short bullets (the key fields, DECISIONS 48 order); the full details (5M trigger, evidence,
# invalidation, PA evidence, Vision's reading) go as a reply under the card. Every value from the signal's tags, copied, never read here.
def is_engine_entry(tags):
    """An engine entry-model signal (signal_source = engine: tags engine + entry_model) — the cards DECISIONS 52 / 53 change."""
    t = tags if isinstance(tags, dict) else {}
    return bool(t.get("engine") and str(t.get("entry_model") or "").strip())


def _area_row(g, area):
    for x in g.get("areas") or []:
        if isinstance(x, dict) and area is not None and _num(x.get("lo")) is not None and _num(x.get("hi")) is not None \
                and abs(float(x["lo"]) - area[0]) < 1e-6 and abs(float(x["hi"]) - area[1]) < 1e-6:
            return x
    return {}


def bullet_trend(tags):
    """"Trend: DOWN (Daily DOWN, impulse · Weekly UP)" — the trade side the engine used + the HTF strip; "" when the tags carry none."""
    g = _gate(tags)
    h = g.get("htf") if isinstance(g.get("htf"), dict) else {}
    parts = [f"Daily {h['daily']}" + (f", {h['daily_phase']}" if h.get("daily_phase") else "") if h.get("daily") else None,
             f"Weekly {h['weekly']}" if h.get("weekly") else None]
    det = " · ".join(p for p in parts if p)
    if not g.get("trend") and not det:
        return ""
    return f"Trend: {g.get('trend') or 'NA'}" + (f" ({det})" if det else "")


def bullet_area(row, tags):
    """"Area: supply 55,699–55,970 (1H, flipped) · refined base 55,699–55,763" (a line object in its own words, DECISIONS 41)."""
    g = _gate(tags)
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    area = _area(row, g)
    ow = object_words(tags, bull)
    if ow:
        out = f"Object: {ow}"
    elif area is not None:
        ar = _area_row(g, area)
        tf = _area_tf(row, g, area)
        st = str(ar.get("state") or "").strip().lower()
        det = ", ".join(x for x in (tf, st) if x)
        out = f"Area: {'demand' if bull else 'supply'} {_pt(area[0])}–{_pt(area[1])}" + (f" ({det})" if det else "")
    elif _num(row.get("level")) is not None:
        out = f"Level: {'support' if bull else 'resistance'} {_pt(_num(row.get('level')))}"
    else:
        return ""
    rb = g.get("refined") if isinstance(g.get("refined"), dict) else None
    if rb and _num(rb.get("lo")) is not None and _num(rb.get("hi")) is not None:
        out += f" · refined base {_pt(min(float(rb['lo']), float(rb['hi'])))}–{_pt(max(float(rb['lo']), float(rb['hi'])))}"
    return out


def bullet_invalidation(tags):
    """"Invalidation (info): 56,065.5 · trade SL / target = dashboard" (the rule itself is in the details reply)."""
    inv = tags.get("entry_invalidation")
    px = _num(inv.get("price")) if isinstance(inv, dict) else _num(inv)
    return f"Invalidation (info): {_px(px)} · trade SL / target = dashboard" if px is not None else ""


def bullet_next(tags):
    """"Next area: demand 55,284–55,341 (1H)" — the engine's own next opposite area (L6-O1); "none known" when the engine read none;
    "" for an older row without it."""
    g = _gate(tags)
    if "next_area" not in g:
        return ""
    nx = g.get("next_area")
    if not isinstance(nx, dict) or _num(nx.get("lo")) is None or _num(nx.get("hi")) is None:
        return "Next area: none known"
    lo, hi = sorted((float(nx["lo"]), float(nx["hi"])))
    word = "demand" if str(nx.get("role") or "").lower() == "support" else "supply"
    tf = TF_NAME.get(str(nx.get("tf") or "").upper(), str(nx.get("tf") or ""))
    return f"Next area: {word} {_pt(lo)}–{_pt(hi)}" + (f" ({tf})" if tf else "")


def evidence_count_words(el):
    """DECISIONS 58 (no A / B label): the engine evidence list's count as plain words — "evidence: 2 of 5 — confluence, RSI divergence
    · NA: volume growing inside" (information only, no threshold). "" when the list carries no count (legacy / non-engine)."""
    el = el if isinstance(el, dict) else {}
    if not isinstance(el.get("evidence_count"), int):
        return ""
    got, na = list(el.get("evidence_present") or []), list(el.get("evidence_na") or [])
    return (f"evidence: {el['evidence_count']} of {el.get('evidence_of', 5)}" + (f" — {', '.join(got)}" if got else "")
            + (f" · NA: {', '.join(na)}" if na else ""))


def entry_evidence_list(tags):
    """The entry's own engine evidence list as the tags carry it (gate.reader.evidence_list, paper.engine_entry.entry_gate_tags)."""
    rd = _gate(tags).get("reader")
    return rd.get("evidence_list") if isinstance(rd, dict) and isinstance(rd.get("evidence_list"), dict) else {}


def bullet_evidence(tags, limit=200):
    """"Evidence ✓: required set · volume growing inside · confluence" — the entry's own evidence pieces marked present (the bracketed
    detail left out; the full ✓ / ✗ / NA list is in the details reply); "Evidence ✓: none" when none; "" without an evidence list.
    DECISIONS 58: an engine entry whose list carries the count ⇒ "Evidence: 2 of 5 — … · NA: …" (information only)."""
    cw = evidence_count_words(entry_evidence_list(tags))
    if cw:
        cw = "E" + cw[1:]
        return cw if len(cw) <= limit else cw[:limit - 1].rstrip() + "…"
    parts = evidence_parts(tags.get("entry_evidence"))
    if not parts:
        return ""
    names = [re.sub(r"\s*\([^()]*\)", "", p[2:]).strip() for p in parts if p.startswith("✓ ")]
    t = " · ".join(n for n in names if n) or "none"
    return "Evidence ✓: " + (t if len(t) <= limit else t[:limit - 1].rstrip() + "…")


def trigger_details(tags):
    """The 5M trigger in full for the details reply: the trigger line + the candle's OHLC, its FUT 5M volume, the visit's first 5M
    candle and the model's own 5M facts (form, CHoCH level, sweep extreme, failed push). [] for a 15M-trigger signal. Not escaped."""
    tl = trigger_line(tags)
    if not tl:
        return []
    tr = tags.get("entry_trigger") if isinstance(tags.get("entry_trigger"), dict) else {}
    oh = tr.get("ohlc") if isinstance(tr.get("ohlc"), dict) else {}
    out = [tl]
    o = [f"{k[0].upper()} {_px(_num(oh.get(k)))}" for k in ("open", "high", "low", "close") if _num(oh.get(k)) is not None]
    vol = _num(tr.get("volume"))
    if o or vol is not None or tr.get("bar15_ts"):
        out.append("5M candle: " + " ".join(o) + (f" · FUT volume {vol:,.0f}" if vol is not None else " · FUT volume NA")
                   + (f" · inside the 15M bar {str(tr['bar15_ts'])[11:16]}" if tr.get("bar15_ts") else ""))
    if tr.get("visit_start5"):
        out.append(f"Visit's first 5M candle: {str(tr['visit_start5'])[:16]}")
    f = tr.get("facts") if isinstance(tr.get("facts"), dict) else {}
    fx = []
    if f.get("form"):
        fx.append(f"form {str(f['form']).replace('_', ' ')}")
    for k, w in (("choch_level", "5M CHoCH level"), ("sweep_extreme", "sweep extreme"), ("push_price", "failed push")):
        if _num(f.get(k)) is not None:
            fx.append(f"{w} {_px(_num(f.get(k)))}" + (f" ({str(f.get('push_ts'))[11:16]})" if k == "push_price" and f.get("push_ts") else ""))
    if fx:
        out.append("Model's 5M facts: " + " · ".join(fx))
    return out


def pa_full(tags):
    """The entry's PA evidence in full for the details reply (one line per fact, in the standard's order; listed, never blocks). HTML-safe."""
    rows = [r for r in tags.get("entry_pa_evidence") or [] if isinstance(r, dict) and r.get("text")]
    if not rows or not model_label(tags):
        return []
    order = {k: i for i, k in enumerate(PA_TRACKS)}
    rows = sorted(rows, key=lambda r: order.get(r.get("track"), len(order)))
    return ["🧩 PA evidence (listed, never blocks):"] + [
        f"• {html.escape(str(r.get('track') or ''))}{(' ' + html.escape(str(r['tf']))) if r.get('tf') else ''}: {html.escape(str(r['text']))}"
        for r in rows]


def line_head(row, status, res=None, ticket=None):
    tags = _tags(row)
    g = _gate(tags)
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    trade = "bull put" if bull else "bear call"
    ml = model_label(tags)
    if ml:                                                               # engine entry model: "E1 — Aggressive · bear call"
        trade = f"{html.escape(ml)} · {trade}"
    lab = f" · Label {g['grade']}" if (tags.get("engine") or g.get("mode") == "engine") and g.get("grade") in ("A", "B") else ""
    sym = html.escape(str(row.get("symbol") or "?"))
    mr = VERDICT.get((res or {}).get("verdict") or "unavailable", ("⚪", str((res or {}).get("verdict"))))[1]
    if ticket is not None:
        head = f"✏️ {sym} · {trade}{lab} · नवी entry {_px(float(ticket['entry']))} — पुन्हा घ्यायचा?"
    elif status == "PENDING_HUMAN":
        head = f"🟡 {sym} · {trade}{lab} — घ्यायचा?"
    elif status == "APPROVED":
        head = f"✅ {sym} · {trade}{lab} · entry मंजूर (Vision {mr})"
    elif status == "REJECTED":
        head = f"❌ {sym} · {trade}{lab} · entry नाही (Vision {mr})"
    else:                                                                # V0: information only, the bot decided as usual
        head = f"ℹ️ {sym} · {trade}{lab} · फक्त माहिती (Vision {mr}; bot ने नेहमीप्रमाणे ठरवलं)"
    if tags.get("manual"):
        head += " · ✋ manual"
    if tags.get("test_only"):
        head += "   🧪 TEST"
    elif tags.get("dry_run"):
        head += "   🧪 DRY-RUN"
    return head


def lines(row, res, status, deadline=None, window_min=None, modify=True, buttons=True, ticket=None):
    """The five summary lines (HTML-safe). status = PENDING_HUMAN / APPROVED / REJECTED / INFO (V0)."""
    return [line_head(row, status, res, ticket), line_where(row, ticket), line_reader(row),
            line_vision(res, rejected=status == "REJECTED" and ticket is None),
            line_you(status, deadline, window_min, modify, buttons, ticket is not None)]


def top(row, res, status, flag="", deadline=None, window_min=None, modify=True, buttons=True, ticket=None):
    """Summary lines + the merged-band warning (today's line, when it applies) + "── details ──"."""
    from bots_common import plain_text as PT
    s = lines(row, res, status, deadline, window_min, modify, buttons, ticket)
    return "\n".join(s) + "\n" + (f"{html.escape(flag)}\n" if flag else "") + PT.SEP
