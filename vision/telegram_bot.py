"""vision/telegram_bot.py — Telegram inbound (V1): Approve / Reject बटणं आणि commands. Long-polling (`getUpdates`), webhook नाही
(VPS वर port उघडायचा नाही). systemd service म्हणून: `python3 -m vision.telegram_bot`.

🎓 Security:
  • `chat.id` **आणि** `from.id` दोन्ही `TELEGRAM_APPROVER_IDS` (env, comma) मध्ये हवेत — नाहीतर दुर्लक्ष (नोंद).
  • Callback data = v1|signal_id|A/R|HMAC(VISION_CALLBACK_SECRET) — बदललेला / खोटा ⇒ नकार.
  • निर्णय conditional (`status = PENDING_HUMAN` असेल तरच) ⇒ दुसऱ्यांदा / replay ⇒ "आधीच ठरलं". Deadline नंतर ⇒ "मुदत संपली".
  • Service सुरू होताना उघडे PENDING_HUMAN ⇒ EXPIRED (restart नंतर जुना approve चालत नाही).
  • Token / secret कधीच print नाहीत. फक्त PAPER bots (LIVE ला vision off). Exits ला यातलं काहीच लागत नाही.
Commands (फक्त approver): /pending · /today · /vision <off|shadow|notify|auto_veto|confirm|veto_then_confirm> <bot>
"""
import argparse
import sys
import time

import pandas as pd

from . import config as VC
from . import decide as VD
from . import store as VS
from . import tg as TG

MODE_ALIAS = {"veto": "auto_veto", "confirm": "human_confirm", "vtc": "veto_then_confirm"}


def expire_on_restart(path=None):
    n = 0
    for r in VS.rows_with_status("PENDING_HUMAN", path):
        if VS.transition(r["signal_id"], "PENDING_HUMAN", "EXPIRED", path, decided_at=VS._iso(VS.now_ist()), decided_by="restart",
                         decision_reason="service restart ⇒ जुना pending निर्णय रद्द"):
            n += 1
            TG.edit_any(r.get("tg_message_id"), f"♻️ Service restart ⇒ हा signal रद्द (stale approve नाही) · {r['symbol']} {r['direction']}")
    return n


def _authorized(upd_from, chat):
    ids = VD.approver_ids()
    return bool(ids) and str((upd_from or {}).get("id")) in ids and str((chat or {}).get("id")) in ids


def handle_callback(cq, path=None, now=None, answer=None, edit=None):
    """रिटर्न (ok, संदेश). answer / edit injectable (tests)."""
    answer = answer or TG.answer_callback
    edit = edit or TG.edit_any
    msg = cq.get("message") or {}
    if not _authorized(cq.get("from"), msg.get("chat")):
        answer(cq.get("id"), "परवानगी नाही")
        return False, "unauthorized"
    parsed = VD.parse_callback(cq.get("data"))
    if parsed is None:
        answer(cq.get("id"), "अवैध बटण")
        return False, "bad_hmac"
    sid, action = parsed
    row = VS.get_signal(sid, path)
    if row is None:
        answer(cq.get("id"), "signal सापडला नाही")
        return False, "missing"
    now = pd.Timestamp(now or VS.now_ist())
    if row["status"] != "PENDING_HUMAN":
        answer(cq.get("id"), f"आधीच ठरलं: {row['status']}")
        return False, "already"
    if row.get("deadline") and pd.Timestamp(row["deadline"]) <= now:
        answer(cq.get("id"), "मुदत संपली")
        return False, "expired"
    who = f"telegram:{(cq.get('from') or {}).get('id')}"
    if action == "A":
        f = float(row.get("factor") or 1.0)
        ok = VS.transition(sid, "PENDING_HUMAN", "APPROVED", path, human_decision="approve", human_ts=VS._iso(now), decided_at=VS._iso(now),
                           decided_by=who, decision_reason=f"तुम्ही approve केलं ({f}×)")
        text = f"✅ Approved {now:%H:%M} — entry ×{f} (drift guard नंतर)"
    else:
        ok = VS.transition(sid, "PENDING_HUMAN", "REJECTED", path, factor=0.0, human_decision="reject", human_ts=VS._iso(now),
                           decided_at=VS._iso(now), decided_by=who, decision_reason="तुम्ही reject केलं")
        text = f"❌ Rejected {now:%H:%M} — skip (shadow trade)"
    if not ok:
        answer(cq.get("id"), "आधीच ठरलं")
        return False, "race"
    answer(cq.get("id"), text)
    edit(row.get("tg_message_id"), f"{text} · {row['symbol']} {row['direction']} L{float(row['level'] or 0):,.0f}")
    return True, text


def handle_command(text, from_, chat, path=None, send=None, trading_mode_fn=None):
    send = send or TG.send_text
    if not _authorized(from_, chat):
        return False, "unauthorized"
    parts = (text or "").strip().split()
    cmd = parts[0].split("@")[0].lower() if parts else ""
    if cmd == "/pending":
        rows = VS.rows_with_status(("QUEUED", "RUNNING", "PENDING_HUMAN", "APPROVED", "REJECTED"), path)
        lines = [f"{r['signal_ts'][11:16]} {r['bot']} {r['symbol']} {r['direction']} L{float(r['level'] or 0):,.0f} → {r['status']}"
                 + (f" (⏱ {r['deadline'][11:16]})" if r.get("deadline") and r["status"] == "PENDING_HUMAN" else "") for r in rows]
        send("⏳ <b>उघडे signals</b>\n" + ("\n".join(lines) if lines else "काहीच नाही"))
        return True, "pending"
    if cmd == "/today":
        day = VS.now_ist().strftime("%Y-%m-%d")
        rows = VS.list_signals(day, path)
        by = {}
        for r in rows:
            by[r["status"]] = by.get(r["status"], 0) + 1
        u = VS.usage_summary(day, path)
        send(f"📊 <b>आज</b>: signals {len(rows)} · " + ", ".join(f"{k} {v}" for k, v in sorted(by.items()))
             + f"\nVision खर्च ${u['cost_usd']:.3f} ({u['calls']} calls)")
        return True, "today"
    if cmd == "/vision":
        if len(parts) != 3:
            send("वापर: /vision &lt;off|shadow|notify|veto|confirm|vtc&gt; &lt;bot&gt;")
            return False, "usage"
        mode, bot = MODE_ALIAS.get(parts[1].lower(), parts[1].lower()), parts[2]
        try:
            VC.save(bot, {"vision_mode": mode}, f"telegram:{(from_ or {}).get('id')}", path, trading_mode_fn=trading_mode_fn)
        except ValueError as exc:
            send(f"❌ {exc}")
            return False, str(exc)
        send(f"✅ {bot}: vision_mode = {mode}")
        return True, mode
    return False, "unknown"


def poll_once(offset, path=None, timeout=50):
    """एक getUpdates फेरी. रिटर्न पुढचा offset."""
    for u in TG.get_updates(offset, timeout):
        offset = max(offset, int(u.get("update_id", 0)) + 1)
        try:
            if "callback_query" in u:
                handle_callback(u["callback_query"], path)
            elif "message" in u:
                m = u["message"]
                if str(m.get("text", "")).startswith("/"):
                    handle_command(m["text"], m.get("from"), m.get("chat"), path)
        except Exception as exc:                                         # एका update ची चूक service थांबवत नाही
            print(f"⚠️ update {u.get('update_id')}: {type(exc).__name__}: {exc}")
        VS.kv_set("tg_offset", offset, path)
    return offset


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)
    if not VD.secret() or not VD.approver_ids():
        print("❌ VISION_CALLBACK_SECRET आणि TELEGRAM_APPROVER_IDS env हवेत — service सुरू नाही")
        return 1
    from process_lock import ProcessLock, ProcessLockHeld
    try:
        with ProcessLock("vision_telegram"):
            n = expire_on_restart()
            print(f"vision telegram service सुरू — restart मुळे {n} pending रद्द")
            ok, why = TG.can_ask()
            if not ok:                                                   # बटणं पाठवली जाणार नाहीत ⇒ प्रत्येक signal timeout नियमाने — मोठ्याने सांगा
                print(f"⚠️ {why}")
                TG.send_text(f"⚠️ Vision V1: Approve / Reject बटणं बंद — {why}. तोपर्यंत V1 signals timeout नियमाने.")
            offset = int(VS.kv_get("tg_offset") or 0)
            while True:
                offset = poll_once(offset)
                if a.once:
                    break
                time.sleep(0.5)
    except ProcessLockHeld:
        print("⏭️ vision telegram service आधीच चालू आहे")
    return 0


if __name__ == "__main__":
    sys.exit(main())
