"""vision/approval.py — Telegram approval v2 (Abhi §10, Monday PAPER): ✅ Approve · ✏️ Modify · ❌ Reject (+ कारण) · 📝 Correct marking.
फक्त approver (TELEGRAM_APPROVER_IDS — telegram_bot._authorized नंतर). प्रत्येक parsed value आधी परत दाखवतो (echo), मगच लागू.

  ✏️ Modify  = फक्त ENTRY (spot वर limit): "entry 22590". SL / target engine चेच (signal tags["gate"]; ✋ manual ⇒ /paper चे SL / T),
               R:R फक्त माहिती म्हणून मोजतो (R:R इशारा नाही — Abhi: R:R dashboard चा); area बाहेर ⇒ इशारा (block नाही). सुधारित ticket ⇒ पुन्हा ✅ हवं; approval window पुन्हा सुरू.
               ✅ नंतर spot entry ला पोहोचला तरच PAPER entry (vision/gate.py: limit_reached); exec window मध्ये नाही ⇒ EXPIRED + would-have.
               Vision पुन्हा चालत नाही. SL / target / lots / strikes / hedge / expiry / risk — Telegram वरून कधीच नाही (dashboard वरच).
  ❌ Reject  = लगेच REJECTED (जुनं वर्तन: position नाही, would-have) + कारण एक tap: wrong trend / wrong zone / no real commitment /
               too late / against my plan / other (मोकळा मजकूर). signal row: reject_reason + decision_reason (chart = row चा image_path).
  📝 Correct = approve असो वा नसो: engine ने काय चुकीचं वाचलं (zone / trend / correction-impulse / commitment candle / मोकळा मजकूर) ⇒
               `corrections` table (chart path, engine reading, parsed + raw) — **engine ला कधीच लागू नाही**, फक्त daily review queue.
Free-text उत्तरं: approver-निहाय pending state (vision_kv "tg_state:<id>" = प्रकार + signal + मुदत) — मुदत संपली / cancel ⇒ काहीच बदल नाही.
"""
import html
import json
import re
from collections import Counter

import pandas as pd

from . import config as VC
from . import decide as VD
from . import store as VS
from . import tg as TG

STATE_TTL_MIN = 15                                                      # reply ची वाट (मग "पुन्हा बटण दाबा")
CANCEL = ("cancel", "रद्द")
NOT_MINE = ("unauthorized", "no_state")                                 # handle_text ने हा मजकूर घेतला नाही ⇒ पुढचा router (review replies)
FORBIDDEN = ("sl", "stop", "stoploss", "target", "tgt", "t", "lot", "lots", "qty", "strike", "strikes", "hedge", "width", "expiry", "risk",
             "cap", "size")
ENTRY_RE = re.compile(r"^entry\s*[:=]?\s*(\d+(?:\.\d+)?)$", re.I)
NUM = r"(\d+(?:\.\d+)?)"
TREND = {"up": "up", "bull": "up", "bullish": "up", "uptrend": "up", "down": "down", "bear": "down", "bearish": "down",
         "downtrend": "down", "sideways": "sideways", "range": "sideways", "flat": "sideways"}
ONLY_ENTRY = ("❌ Telegram वरून फक्त entry बदलता येतो (उदा. <code>entry 22590</code>). SL / target / lots / strikes / hedge / expiry / "
              "risk caps — dashboard वरच. काहीच बदल नाही.")


# ------------------------------------------------------------------------------------------------ buttons / state
def buttons(sid, modify=True):
    """✅ ❌ पहिले (tests / जुनी क्रमवारी), मग ✏️ (engine SL / target असतील तर) आणि 📝 — tg.keyboard दोन-दोनच्या ओळी करतो."""
    b = [("✅ Approve", VD.callback_data(sid, "A")), ("❌ Reject", VD.callback_data(sid, "R"))]
    if modify:
        b.append(("✏️ Modify", VD.callback_data(sid, "M")))
    return b + [("📝 Correct marking", VD.callback_data(sid, "C"))]


def reason_buttons(sid):
    return [(lbl, VD.callback_data(sid, code)) for code, lbl in VD.REJECT_REASONS.items()]


def _key(uid):
    return f"tg_state:{uid}"


def state_get(uid, path=None):
    try:
        st = json.loads(VS.kv_get(_key(uid), path) or "null")
    except ValueError:
        return None
    return st if isinstance(st, dict) and st.get("kind") and st.get("sid") else None


def state_set(uid, kind, sid, path=None, now=None, ttl=STATE_TTL_MIN):
    now = pd.Timestamp(now or VS.now_ist())
    VS.kv_set(_key(uid), json.dumps({"kind": kind, "sid": sid, "exp": VS._iso(now + pd.Timedelta(minutes=ttl))}), path)


def state_clear(uid, path=None):
    VS.kv_set(_key(uid), "", path)


def _tags(row):
    try:
        return json.loads(row.get("setup_json") or "{}").get("tags") or {}
    except (ValueError, AttributeError, TypeError):
        return {}


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ ✏️ Modify
def base_levels(row):
    """engine चे SL / target / area / entry: signal tags["gate"] (bots_common/level_gate_bot.gate_tags); ✋ manual ⇒ /paper चे SL / T.
    नाहीत ⇒ None (✏️ बटण नाही)."""
    try:
        tags = _tags(row)
        g = tags.get("gate") or {}
        if _f(g.get("sl")) is not None:
            area = [_f(x) for x in (g.get("area") or [])[:2]]
            return {"side": str(g.get("side") or row.get("direction") or "").upper(), "sl": _f(g["sl"]), "target": _f(g.get("target")),
                    "entry": _f(g.get("entry")), "area": area if len(area) == 2 and None not in area else None, "src": "engine",
                    "show_rr": g.get("rr") is not None}                   # gate tags मध्ये rr फक्त dashboard R:R gate चालू असेल तर
        if tags.get("manual") and tags.get("manual_id"):
            from paper import manual as PM
            m = PM.get(tags["manual_id"])
            if m and _f(m.get("sl")) is not None:
                return {"side": str(m.get("direction") or row.get("direction") or "").upper(), "sl": _f(m["sl"]), "target": _f(m.get("target")),
                        "entry": _f(m.get("spot")), "area": None, "src": "manual", "show_rr": True}   # Abhi चे स्वतःचे SL / T ⇒ R:R माहिती
    except Exception as exc:
        print(f"⚠️ approval base_levels: {type(exc).__name__}: {exc}")
    return None


def parse_entry(text):
    """"entry 22590" ⇒ (22590.0, None). इतर काहीही (sl / target / lots …) ⇒ (None, स्पष्ट चूक)."""
    t = " ".join(str(text or "").replace(",", "").split())
    m = ENTRY_RE.match(t)
    if m:
        v = float(m.group(1))
        return (v, None) if v > 0 else (None, "❌ entry 0 पेक्षा मोठा हवा. काहीच बदल नाही.")
    words = re.findall(r"[a-z]+", t.lower())
    if any(w in FORBIDDEN for w in words):
        return None, ONLY_ENTRY
    return None, "❌ समजलं नाही — असं लिहा: <code>entry 22590</code> (spot वर limit). रद्द: cancel. काहीच बदल नाही."


def modify_ticket(row, entry):
    """(ticket, None) किंवा (None, चूक). SL / target बदलत नाहीत; R:R = (target − entry) / (entry − SL) (दिशेनुसार)."""
    b = base_levels(row)
    if b is None:
        return None, "❌ Modify नाही: या signal मध्ये engine चे SL / target नाहीत."
    if b["side"] not in ("BULLISH", "BEARISH"):
        return None, f"❌ Modify नाही: setup ची बाजू कळत नाही ({html.escape(b['side'] or '?')})."
    d = 1 if b["side"] == "BULLISH" else -1
    sl, tg = b["sl"], b["target"]
    if (entry - sl) * d <= 0:
        return None, f"❌ entry {entry:g} हा SL {sl:g} च्या {'वर' if d > 0 else 'खाली'} हवा ({b['side']}). काहीच बदल नाही."
    if tg is not None and (tg - entry) * d <= 0:
        return None, f"❌ entry {entry:g} target {tg:g} च्या पलीकडे — trade उरत नाही. काहीच बदल नाही."
    show_rr = bool(b.get("show_rr", True))                               # engine: फक्त dashboard R:R gate चालू असेल तर (Abhi)
    rr = round((tg - entry) * d / ((entry - sl) * d), 2) if (tg is not None and show_rr) else None
    warn = []
    if b["area"]:
        lo, hi = sorted(b["area"])
        if not lo <= entry <= hi:
            warn.append(f"⚠️ entry area {lo:,.0f}–{hi:,.0f} बाहेर")
    return {"side": b["side"], "entry": entry, "sl": sl, "target": tg, "rr": rr, "area": b["area"], "engine_entry": b["entry"],
            "src": b["src"], "warnings": warn, "show_rr": show_rr}, None


def ticket_text(row, t, deadline, exec_min):
    eng = f" (engine: {t['engine_entry']:g})" if t.get("engine_entry") is not None else ""
    area = f" · area {min(t['area']):,.0f}–{max(t['area']):,.0f}" if t.get("area") else ""
    show_rr = bool(t.get("show_rr", True))                               # engine signal + R:R gate बंद ⇒ R:R कुठेच नाही (Abhi)
    rr = "NA" if t["rr"] is None else f"{t['rr']:g}"
    tgt = "NA" if t["target"] is None else f"{t['target']:g}"
    ref = "engine reference (info): " if t.get("src") == "engine" else ""   # Abhi RR2: trade चे SL / target = dashboard
    lines = [f"✏️ <b>सुधारित ticket</b> · {html.escape(str(row.get('symbol')))} {t['side']} · {html.escape(str(row.get('setup_tf') or ''))}",
             f"Entry (limit, spot) <b>{t['entry']:g}</b>{eng} · {ref}SL {t['sl']:g} · target {tgt}{area}"
             + (f" · R:R <b>{rr}</b>" if show_rr else "")]
    lines += t["warnings"]
    lines += ["फक्त entry बदलली — trade चे SL / target / lots / strikes / hedge / expiry / risk: dashboard चेच." if ref else
              "फक्त entry बदलली — SL / target / lots / strikes / hedge / expiry / risk: engine / dashboard चेच.",
              f"⏱ <b>{pd.Timestamp(deadline):%H:%M} पर्यंत</b> पुन्हा ✅ हवं. ✅ नंतर spot {t['entry']:g} ला पोहोचला तरच PAPER entry; "
              f"{exec_min} मिनिटांत नाही ⇒ position नाही (would-have नोंद)."]
    from bots_common import plain_text as PT                             # Abhi (TELEGRAM_CLEANUP 3): ओळ 1 साधी, ओळ 2 निर्णय
    rr_txt = "" if not show_rr else (" — R:R not available" if t["rr"] is None else f" — reward is {t['rr']:g}× the risk")
    head = (f"{html.escape(str(row.get('symbol')))}: your changed entry {t['entry']:g} ({'engine reference ' if ref else ''}stop {t['sl']:g}, "
            f"target {tgt}){rr_txt}. "
            "Check the new numbers, then approve again.")
    return f"{head}\n<b>{PT.DECISION_APPROVE}</b> by {pd.Timestamp(deadline):%H:%M}\n{PT.SEP}\n" + "\n".join(lines)


def start_modify(row, uid, answer, cq_id, send=None, path=None, now=None):
    send = send or TG.send_text
    b = base_levels(row)
    if b is None:
        answer(cq_id, "Modify नाही: engine SL / target नाहीत")
        return False, "no_levels"
    state_set(uid, "entry", row["signal_id"], path, now)
    area = f" · area {min(b['area']):,.0f}–{max(b['area']):,.0f}" if b["area"] else ""
    eng = f"entry {b['entry']:g} · " if b["entry"] is not None else ""
    tgt = "NA" if b["target"] is None else f"{b['target']:g}"
    send(f"✏️ {html.escape(str(row['symbol']))} {html.escape(str(row.get('direction') or ''))}: नवीन <b>entry</b> लिहा — "
         f"<code>entry 22590</code> (spot वर limit). रद्द: cancel\nEngine: {eng}SL {b['sl']:g} · target {tgt}{area} (हे बदलत नाहीत)"
         + ("\nहे engine reference (info) — trade चे SL / target = dashboard settings." if b.get("src") == "engine" else ""))   # Abhi RR2
    answer(cq_id, "✏️ entry लिहा (उदा. entry 22590)")
    return True, "modify_prompt"


def apply_entry(uid, sid, text, send=None, path=None, now=None, edit=None, send_buttons=None):
    """"entry X" ⇒ ticket ⇒ row (mod_entry, mod_json, नवी deadline) — status PENDING_HUMAN तसाच (पुन्हा ✅ हवं)."""
    send = send or TG.send_text
    edit = edit or TG.edit_any
    send_buttons = send_buttons or TG.send_photo
    now = pd.Timestamp(now or VS.now_ist())
    entry, err = parse_entry(text)
    if err:
        send(err)                                                        # state तसाच — पुन्हा लिहू शकता
        return False, "bad_input"
    row = VS.get_signal(sid, path)
    if row is None or row["status"] != "PENDING_HUMAN" or (row.get("deadline") and pd.Timestamp(row["deadline"]) <= now):
        state_clear(uid, path)
        send(f"⌛ signal आता {html.escape(str((row or {}).get('status') or 'नाही'))} ⇒ Modify नाही. काहीच बदल नाही.")
        return False, "not_pending"
    t, err = modify_ticket(row, entry)
    if err:
        send(err)
        return False, "bad_input"
    s = VC.load(row["bot"], path)
    dl = now + pd.Timedelta(minutes=int(s["approve_window_min"]))       # Abhi: Modify नंतर approval window पुन्हा सुरू
    if not VS.transition(sid, "PENDING_HUMAN", "PENDING_HUMAN", path, mod_entry=entry, mod_json=json.dumps(t, ensure_ascii=False),
                         deadline=VS._iso(dl)):
        state_clear(uid, path)
        send("⌛ signal चा निर्णय आधीच झाला ⇒ Modify नाही.")
        return False, "race"
    state_clear(uid, path)
    edit(row.get("tg_message_id"), f"✏️ entry बदलली ({entry:g}) — सुधारित ticket खाली; ही बटणं बंद · {row['symbol']} {row['direction']}")
    mid = send_buttons(None, ticket_text(row, t, dl, int(s["exec_window_min"])), buttons(sid, True))
    if mid:
        VS.update(sid, path, tg_message_id=mid)
    return True, "modified"


# ------------------------------------------------------------------------------------------------ ❌ कारण
def prompt_reason(row, send_buttons=None):
    try:
        (send_buttons or TG.send_photo)(None, f"❌ कारण? (एक tap) · {html.escape(str(row['symbol']))} {html.escape(str(row.get('direction') or ''))}",
                                        reason_buttons(row["signal_id"]))
    except Exception as exc:
        print(f"⚠️ reject कारण विचारता आलं नाही: {type(exc).__name__}: {exc}")


def _store_reason(sid, label, path=None):
    VS.update(sid, path, reject_reason=label[:300], decision_reason=f"तुम्ही reject केलं — {label}"[:300])
    VS.event(sid, "reject_reason", label, path)


def set_reason(row, code, uid, answer, cq_id, edit=None, msg_id=None, send=None, path=None, now=None):
    edit = edit or TG.edit_any
    send = send or TG.send_text
    if row.get("human_decision") != "reject":
        answer(cq_id, "हा signal तुम्ही reject केलेला नाही")
        return False, "not_rejected"
    if code == "RO":
        state_set(uid, "reason", row["signal_id"], path, now)
        answer(cq_id, "कारण लिहा")
        send("❌ कारण लिहा (मोकळा मजकूर). रद्द: cancel")
        return True, "reason_prompt"
    label = VD.REJECT_REASONS[code]
    _store_reason(row["signal_id"], label, path)
    answer(cq_id, f"कारण नोंदलं: {label}")
    if msg_id:
        edit(msg_id, f"❌ कारण: <b>{label}</b> ✓ · {row['symbol']} {row.get('direction') or ''}")
    return True, label


# ------------------------------------------------------------------------------------------------ 📝 Correct marking
def parse_correction(text):
    """रिटर्न ({"type", …}, None) किंवा (None, चूक). प्रकार: zone / trend / wave / commitment / free."""
    raw = " ".join(str(text or "").split())
    if not raw:
        return None, "❌ रिकामा मजकूर — काय चुकलं ते लिहा. रद्द: cancel"
    if len(raw) > 500:
        return None, "❌ खूप मोठा मजकूर (500 अक्षरांपर्यंत)."
    low = raw.lower()
    if low.startswith("zone"):
        m = re.match(rf"^zone\s*[:=]?\s*{NUM}\s*(?:-|–|to|/)\s*{NUM}$", low.replace(",", ""))
        if not m or float(m.group(1)) == float(m.group(2)):
            return None, "❌ zone असं लिहा: <code>zone 22570-22640</code> (दोन वेगळे आकडे). नोंद नाही."
        lo, hi = sorted((float(m.group(1)), float(m.group(2))))
        return {"type": "zone", "lo": lo, "hi": hi}, None
    if low.startswith("trend"):
        w = low.split()
        if len(w) != 2 or w[1] not in TREND:
            return None, "❌ trend असं लिहा: <code>trend up</code> / <code>trend down</code> / <code>trend sideways</code>. नोंद नाही."
        return {"type": "trend", "value": TREND[w[1]]}, None
    if low.startswith("commitment"):
        m = re.match(r"^commitment(?:\s+candle)?\s+(\d{1,2}):(\d{2})$", low)
        if not m or not (0 <= int(m.group(1)) < 24 and 0 <= int(m.group(2)) < 60):
            return None, "❌ commitment असं लिहा: <code>commitment candle 10:45</code>. नोंद नाही."
        return {"type": "commitment", "time": f"{int(m.group(1)):02d}:{m.group(2)}"}, None
    pos = re.sub(r"\bnot\s+(?:an?\s+)?(correction|impulse)\b", " ", low)     # "correction, not impulse" ⇒ correction
    kinds = [k for k in ("correction", "impulse") if k in pos]
    if len(kinds) == 1:
        return {"type": "wave", "value": kinds[0]}, None
    return {"type": "free"}, None


def describe(p):
    if p["type"] == "zone":
        return f"zone {p['lo']:g}–{p['hi']:g}"
    if p["type"] == "trend":
        return f"trend {p['value']}"
    if p["type"] == "wave":
        return f"wave: {p['value']}"
    if p["type"] == "commitment":
        return f"commitment candle {p['time']}"
    return "मोकळा मजकूर"


def start_correction(row, uid, answer, cq_id, send=None, path=None, now=None):
    send = send or TG.send_text
    state_set(uid, "correction", row["signal_id"], path, now)
    send(f"📝 {html.escape(str(row['symbol']))} {html.escape(str(row.get('setup_tf') or ''))}: engine ने काय चुकीचं वाचलं? उदा. "
         "<code>zone 22570-22640</code> · <code>trend down</code> · <code>this is a correction, not impulse</code> · "
         "<code>commitment candle 10:45</code> · किंवा मोकळा मजकूर. (फक्त daily review — engine ला लागू नाही.) रद्द: cancel")
    if answer:
        answer(cq_id, "📝 लिहा")
    return True, "correction_prompt"


def apply_correction(uid, sid, text, by, send=None, path=None, now=None):
    send = send or TG.send_text
    p, err = parse_correction(text)
    if err:
        send(err)
        return False, "bad_input"
    row = VS.get_signal(sid, path)
    if row is None:
        state_clear(uid, path)
        send("❌ signal सापडला नाही — नोंद नाही.")
        return False, "missing"
    cid = VS.add_correction({"ts": now, "signal_id": sid, "bot": row.get("bot"), "symbol": row.get("symbol"), "tf": row.get("setup_tf"),
                             "image_path": row.get("image_path"), "engine_reading": row.get("setup_json"), "ctype": p["type"], "parsed": p,
                             "raw_text": " ".join(str(text).split()), "by_": by}, path)
    state_clear(uid, path)
    send(f"📝 नोंदलं ({html.escape(describe(p))}) · {html.escape(str(row['symbol']))} {html.escape(str(row.get('setup_tf') or ''))} · "
         f"signal {sid} · #{cid} — engine ला लागू नाही, daily review queue मध्ये.")
    return True, cid


def start_correction_cmd(text, uid, send=None, path=None, now=None):
    """/correct [signal_id] — ✅ / ❌ नंतर (बटणं गेल्यावर) सुद्धा 📝. id नाही ⇒ आजचा शेवटचा signal."""
    send = send or TG.send_text
    parts = (text or "").split()
    row = None
    if len(parts) > 1:
        row = VS.get_signal(parts[1], path)
    else:
        day = pd.Timestamp(now or VS.now_ist()).strftime("%Y-%m-%d")
        rows = sorted(VS.list_signals(day, path), key=lambda r: r.get("created_at") or "")
        row = rows[-1] if rows else None
    if row is None:
        send("❌ /correct: signal सापडला नाही (वापर: /correct [signal_id])")
        return False, "missing"
    return start_correction(row, uid, None, None, send, path, now)


# ------------------------------------------------------------------------------------------------ free-text router
def handle_text(m, authorized, path=None, send=None, now=None, edit=None, send_buttons=None):
    """approver चा साधा मजकूर (command नाही): pending state असेल तरच हाताळतो. रिटर्न (handled, label); handled False ⇒ पुढचा router
    (review replies) पाहील."""
    if not authorized(m.get("from"), m.get("chat")):
        return False, "unauthorized"
    uid = str((m.get("from") or {}).get("id"))
    st = state_get(uid, path)
    if st is None:
        return False, "no_state"
    send = send or TG.send_text
    now = pd.Timestamp(now or VS.now_ist())
    text = str(m.get("text") or "").strip()
    if pd.Timestamp(st["exp"]) <= now:
        state_clear(uid, path)
        send("⌛ उत्तराची मुदत संपली — पुन्हा बटण दाबा. काहीच बदल नाही.")
        return True, "state_expired"
    if text.lower() in CANCEL:
        state_clear(uid, path)
        send("रद्द — काहीच बदल नाही.")
        return True, "cancelled"
    if st["kind"] == "entry":
        return apply_entry(uid, st["sid"], text, send, path, now, edit, send_buttons)
    if st["kind"] == "correction":
        return apply_correction(uid, st["sid"], text, f"telegram:{uid}", send, path, now)
    if st["kind"] == "reason":
        if not text:
            send("❌ रिकामा मजकूर — कारण लिहा. रद्द: cancel")
            return False, "bad_input"
        label = f"other: {' '.join(text.split())}"
        _store_reason(st["sid"], label, path)
        state_clear(uid, path)
        send(f"❌ कारण नोंदलं: {html.escape(label[:200])}")
        return True, "reason"
    state_clear(uid, path)
    return False, "unknown_state"


# ------------------------------------------------------------------------------------------------ 15:45 daily summary (Abhi §10e)
def daily_summary(day=None, vpath=None, jpath=None):
    """{approvals, modifications, rejections: {कारण: n}, timeouts, corrections, pnl, trades_closed, trades_open, would_have} — dry-run वगळून."""
    from paper import journal as PJ
    day = str(day or VS.now_ist().strftime("%Y-%m-%d"))
    sig = [r for r in VS.list_signals(day, vpath) if not _tags(r).get("dry_run")]
    rej = Counter((r.get("reject_reason") or "कारण नाही") for r in sig if r.get("human_decision") == "reject")
    tr = [t for t in PJ.rows(day, jpath) if not t.get("dry_run")]
    closed = [t for t in tr if t.get("exit_time")]
    wh = [w for w in PJ.would_have_rows(jpath) if str(w.get("ts") or "")[:10] == day and not w.get("dry_run")]
    return {"day": day, "approvals": sum(1 for r in sig if r.get("human_decision") == "approve"),
            "modifications": sum(1 for r in sig if r.get("mod_entry") is not None),
            "modified_approved": sum(1 for r in sig if r.get("mod_entry") is not None and r.get("human_decision") == "approve"),
            "limit_expired": sum(1 for r in sig if r.get("mod_entry") is not None and r["status"] == "EXPIRED"),
            "rejections": dict(rej), "timeouts": sum(1 for r in sig if r.get("decided_by") in ("timeout", "stale")),
            "corrections": len(VS.corrections(day, path=vpath)), "pnl": round(sum(float(t.get("net_pnl") or 0) for t in closed), 2),
            "trades_closed": len(closed), "trades_open": len(tr) - len(closed), "would_have": len(wh)}


def daily_summary_text(day=None, vpath=None, jpath=None):
    """15:45 सारांशाचा "तुमचे निर्णय + P&L" भाग — साधे English शब्द (Abhi, TELEGRAM_CLEANUP 4). आकडे daily_summary चेच."""
    d = daily_summary(day, vpath, jpath)
    nrej = sum(d["rejections"].values())
    rej = ", ".join(f"{html.escape('no reason given' if k == 'कारण नाही' else k)} {v}"
                    for k, v in sorted(d["rejections"].items(), key=lambda x: -x[1]))
    appr = f"approved {d['approvals']}"
    if d["modified_approved"] or d["limit_expired"]:
        appr += (f" ({d['modified_approved']} with a changed entry"
                 + (f"; {d['limit_expired']} never reached the changed entry" if d["limit_expired"] else "") + ")")
    return "\n".join([
        f"<b>Your decisions today</b>: {appr}, rejected {nrej}" + (f" ({rej})" if rej else "")
        + f", changed entry {d['modifications']}, no answer {d['timeouts']}.",
        f"<b>Trades</b>: closed {d['trades_closed']}, still open {d['trades_open']}, net P&L <b>₹{d['pnl']:,.0f}</b>. "
        f"Skipped trades tracked for comparison: {d['would_have']}.",
        f"Chart corrections you sent: {d['corrections']} (kept for review; not applied to the engine)."])
