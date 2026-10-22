"""vision/notify.py — T-1 (Abhi, DECISIONS 29): Vision approval card कधीच पुसत नाही आणि प्रत्येक outcome चा नवा संदेश.

  post(row, kind, line, reply)   card वर (मूळ caption + outcome ओळी, `TG.append_outcome`) एक ओळ जोडतो **आणि** card ला उत्तर म्हणून नवा छोटा
                                 संदेश (`TG.reply`, reply_to_message_id). (signal, kind) एकदाच (vision_kv "tg_out:<sid>:<kind>").
  record_shadow(sid, opened, …)  bot / gate ने shadow चा निकाल नोंदवला (फक्त DB — network नाही; bot च्या entry मार्गात Telegram call नाही);
                                 worker housekeeping तो संदेश पाठवतो. Exit मार्गात यातलं काहीच नाही.
  health_line()                  approval बटणं (TG.can_ask) + listener (telegram_bot ची शेवटची poll) — /status आणि Vision पान.
फक्त दिसणं / संदेश: order ठेवणं / अडवणं / बदलणं इथे कधीच नाही; human_confirm वर्तन तसंच. कुठलीही चूक ⇒ print, raise नाही.
Plain words (Abhi): "shadow" हा शब्द कधीच स्पष्टीकरणाशिवाय नाही — "comparison only, not counted in results".
"""
import html
import json

import pandas as pd

from . import store as VS
from . import tg as TG

EXPLAIN = "comparison only, not counted in results"
SHADOW_NEXT = "A comparison-only shadow trade will be recorded if the setup is still valid on the next check."
NO_SHADOW_APPROVAL = "Approval mode: no shadow trade, only a would-have note is kept (comparison only, not counted in results)."
NOT_TAKEN_SHORT = "Trade NOT taken; a comparison-only shadow trade may follow (not counted in results)."   # card (1024 मर्यादा)
SIZE_EN = {1.0: "full size", 0.5: "half size"}
LISTENER_KEY = "tg_listener_seen"
LISTENER_STALE_SEC = 180                                                # display only: getUpdates long-poll 50 s ⇒ 3 मिनिटं शांत = थांबला


def size_en(f):
    try:
        return SIZE_EN.get(round(float(f), 2), f"×{float(f):g}")
    except (TypeError, ValueError):
        return "?"


def hm(ts):
    try:
        return pd.Timestamp(ts).strftime("%H:%M") if ts else "?"
    except (TypeError, ValueError):
        return "?"


def where(row):
    """"E1 — Aggressive · NIFTY BEARISH L22,761" (साधी ओळख; card आणि reply दोन्हीत)."""
    try:
        from .telegram_bot import _model_prefix
        mp = _model_prefix(row)
    except Exception:                                                    # noqa: BLE001
        mp = ""
    lv = row.get("level")
    try:
        lv = f" L{float(lv):,.0f}" if lv is not None else ""
    except (TypeError, ValueError):
        lv = ""
    return f"{mp}{html.escape(str(row.get('symbol') or ''))} {html.escape(str(row.get('direction') or ''))}{lv}"


def posted(signal_id, kind, path=None):
    """हा outcome संदेश आधीच गेला? (वाचता आलं नाही ⇒ True — शंका असेल तर पुन्हा पाठवत नाही.)"""
    try:
        return bool(VS.kv_get(f"tg_out:{signal_id}:{kind}", path))
    except Exception:                                                    # noqa: BLE001
        return True


def post(row, kind, line, reply=None, path=None, append=None, send_reply=None, edit=True, once=True):
    """Card वर outcome ओळ जोडतो (आधीच्या outcome ओळी टिकवून) + card ला उत्तर म्हणून नवा संदेश. रिटर्न True ⇒ पाठवलं.
    मूळ caption नोंदलेला नाही (T-1 आधी पाठवलेला card) ⇒ card ला हात नाही (पुसत नाही), फक्त नवा संदेश.
    append / send_reply injectable (tests). कधीच raise नाही."""
    try:
        sid = (row or {}).get("signal_id")
        key = f"tg_out:{sid}:{kind}"
        if once and sid and VS.kv_get(key, path):
            return False
        fresh = (VS.get_signal(sid, path) if sid else None) or row or {}
        mid = fresh.get("tg_message_id")
        prev = str(fresh.get("tg_outcome") or "").strip()
        block = f"{prev}\n{line}" if prev else str(line)
        if sid:                                                          # आधी नोंद ⇒ दुसरा process / पुढचा loop पुन्हा पाठवत नाही
            VS.kv_set(key, VS._iso(VS.now_ist()), path)
            VS.update(sid, path, tg_outcome=block[:3000])
        if edit and mid and fresh.get("tg_caption"):
            (append or TG.append_outcome)(mid, fresh.get("tg_caption"), block)
        (send_reply or TG.reply)(mid, reply or line)
        if sid:
            VS.event(sid, "tg_outcome", f"{kind}: {line}", path)
        return True
    except Exception as exc:                                             # noqa: BLE001 — display only
        print(f"⚠️ vision outcome संदेश ({kind}): {type(exc).__name__}: {exc}")
        return False


# ------------------------------------------------------------------------------------------------ outcome texts (plain English)
def approved_line(now, factor, limit=None):
    if limit is not None:
        return (f"✅ Approved {hm(now)} — limit entry {float(limit):g}: {size_en(factor)} only when spot reaches it "
                "(within the entry window; otherwise no position)")
    return f"✅ Approved {hm(now)} — entry {size_en(factor)} (after the drift guard)"


def _next(approval):
    return NO_SHADOW_APPROVAL if approval else SHADOW_NEXT


def rejected_line(now, approval=True):
    return f"❌ Rejected by you {hm(now)} ⇒ trade NOT taken. {_next(approval)}"


def no_reply_line(deadline, taken_factor=None, approval=True):
    """taken_factor None / 0 ⇒ skipped (human_confirm, approval mode); > 0 ⇒ the no-reply rule enters (approval off only)."""
    if taken_factor:
        return f"⏱ No reply by {hm(deadline)} ⇒ the no-reply rule: entry {size_en(taken_factor)} (after the drift guard)."
    return f"⏱ No reply by {hm(deadline)} ⇒ trade NOT taken. {_next(approval)}"


def drift_line(drift, approval=True):
    return (f"❌ Not entered: price moved too far after the approval (drift guard: {html.escape(str(drift or '?'))[:160]}) ⇒ "
            f"trade NOT taken. {_next(approval)}")


def no_shadow_line(reason):
    return f"No shadow: the setup was no longer valid ({html.escape(str(reason or '?'))[:160]})"


def shadow_opened_line():
    return f"📒 Shadow trade opened ({EXPLAIN})"


def shadow_closed_line(pnl, exit_reason=None):
    p = f"₹{float(pnl):,.0f}" if pnl is not None else "NA"
    return f"📒 Shadow trade closed ({EXPLAIN}): P&L {p}" + (f" · {html.escape(str(exit_reason))}" if exit_reason else "")


def restart_line():
    return "♻️ Service restart ⇒ this signal is cancelled (no stale approval) ⇒ trade NOT taken."


def expired_line(row, prev=None):
    """EXPIRED: कुठून आला (शेवटचा transition) त्यानुसार साधे शब्द."""
    note = html.escape(str(row.get("exec_note") or row.get("error") or "expired"))[:160]
    src = str(prev or "").split("→")[0]
    if src == "REJECTED":                                                # नाकारलेला, पण bot exec window मध्ये पोहोचला नाही
        return no_shadow_line(note)
    if src == "APPROVED":
        return f"⌛ Expired: approved, but the bot did not reach the entry in time ({note}) ⇒ trade NOT taken; no shadow trade."
    return f"⌛ Cancelled ({note}) ⇒ trade NOT taken; no shadow trade."


# ------------------------------------------------------------------------------------------------ shadow result (bot / gate ⇒ DB only)
def record_shadow(signal_id, opened, note="", path=None, approval_mode=False):
    """Bot ने shadow उघडला का (opened True / False) + कारण — फक्त vision_kv (network नाही, कधीच raise नाही). Housekeeping संदेश पाठवतो."""
    if not signal_id:
        return
    try:
        VS.kv_set(f"shadow_result:{signal_id}", json.dumps({"opened": bool(opened), "note": str(note or "")[:300],
                                                               "approval_mode": bool(approval_mode)}, ensure_ascii=False),
                  path)
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ shadow result नोंद: {type(exc).__name__}: {exc}")


def shadow_result(signal_id, path=None):
    try:
        v = json.loads(VS.kv_get(f"shadow_result:{signal_id}", path) or "null")
        return v if isinstance(v, dict) else None
    except (ValueError, TypeError):
        return None


def shadow_result_text(res):
    """record_shadow चा निकाल ⇒ card ओळ (साधे शब्द)."""
    if res.get("opened"):
        return shadow_opened_line()
    note = str(res.get("note") or "")
    if res.get("approval_mode"):
        return f"No shadow trade: approval mode keeps only a would-have note (lots 0; {EXPLAIN})"
    if "उघडा" in note:                                                   # bot: "आधीचा shadow अजून उघडा ⇒ नवा नाही"
        return f"No shadow: an earlier comparison-only shadow trade of this bot is still open ({EXPLAIN})"
    return no_shadow_line(note.replace("shadow:", "").strip() or "not opened")


# ------------------------------------------------------------------------------------------------ approval reachability
def can_ask_alert(why, path=None, send=None, now=None):
    """Buttons unavailable ⇒ दिवसातून एकच इशारा. रिटर्न True ⇒ आज पाठवला."""
    try:
        day = pd.Timestamp(now or VS.now_ist()).strftime("%Y-%m-%d")
        k = f"tg_can_ask_alert:{day}"
        if VS.kv_get(k, path):
            return False
        VS.kv_set(k, str(why)[:200], path)
        (send or TG.send_text)(f"⚠️ <b>Vision approval buttons unavailable</b>: {html.escape(str(why))}. "
                               "Every V1 signal is skipped (no entry) until this is fixed.")
        return True
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ can_ask इशारा: {type(exc).__name__}: {exc}")
        return False


def listener_seen(path=None, now=None):
    try:
        VS.kv_set(LISTENER_KEY, VS._iso(pd.Timestamp(now or VS.now_ist()).to_pydatetime()), path)
    except Exception:                                                    # noqa: BLE001
        pass


def health_line(path=None, now=None, can_ask=None):
    """"Vision approval: buttons ✅ OK · listener ✅ seen 10:41:05" — कधीच raise नाही (NA)."""
    try:
        ok, why = (can_ask or TG.can_ask)()
    except Exception as exc:                                             # noqa: BLE001
        ok, why = False, type(exc).__name__
    try:
        seen = VS.kv_get(LISTENER_KEY, path)
        now = pd.Timestamp(now or VS.now_ist())
        if not seen:
            lis = "listener ❌ never seen"
        else:
            age = (now - pd.Timestamp(seen)).total_seconds()
            lis = (f"listener ✅ seen {pd.Timestamp(seen):%H:%M:%S}" if age <= LISTENER_STALE_SEC
                   else f"listener ❌ silent since {pd.Timestamp(seen):%d %b %H:%M}")
    except Exception as exc:                                             # noqa: BLE001
        lis = f"listener NA ({type(exc).__name__})"
    btn = "buttons ✅ OK" if ok else f"buttons ❌ unavailable ({html.escape(str(why))})"
    return f"Vision approval: {btn} · {lis}"
