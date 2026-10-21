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
present" is the method's required set (handover + commitment with its volume comparison + LTF CHoCH, decision3/method.evidence_list)
and the confirming pieces are the ones it marks present. Display only: no decision, gate, order or button changes here.
"""
import html
import json
import math
import re

import pandas as pd

LAYOUT_KEY = "approval_card_layout"
LAYOUTS = ("classic", "summary")
REASON_MAX = 90                                                          # Vision's reason on the summary: one line (full text in details)
CONFIRM_WORDS = {"volume_growing": "volume growing", "rsi_divergence": "RSI div", "confluence": "confluence",
                 "correction_line_closed_through": "line closed through"}   # decision3/method.CONFIRMING, in its order
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


def line_where(row, ticket=None):
    """📍 area (or level) + its TF · entry / SL / target when the signal carries them · last price and its distance to the area."""
    tags = _tags(row)
    g = _gate(tags)
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    area = _area(row, g)
    tf = _area_tf(row, g, area)
    tfs = f" ({html.escape(tf)})" if tf else ""
    lvl = _num(row.get("level"))
    if area is not None:
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
    if ev.get("required") == "present":                                  # method §5: the required set, as the engine read it
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


def line_head(row, status, res=None, ticket=None):
    tags = _tags(row)
    g = _gate(tags)
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    trade = "bull put" if bull else "bear call"
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
