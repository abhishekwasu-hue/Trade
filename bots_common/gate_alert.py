"""bots_common/gate_alert.py — DECISIONS 47: a gate / engine error never enters (fail-closed) and is never silent: each cause sends ONE
plain-words ⚠️ Telegram alert per day.

    alert(path, symbol, detail, engine_entry_waiting=None, send=None, state_path=None, now=None) -> bool (sent?)

  path   = where the error happened: "level_gate" (the old level-bot confirmation gate inside the 15M SRv2 bot), "engine_entry" (the
           engine's entry step in the bot cycle), "engine_store" (reading the engine store), "vision" (the approval / Vision gate).
  detail = the exact error ("TimeoutError: fetch > 25s", the gate reason …); the cause key = path + the exception name (or the words
           of the reason without numbers) ⇒ the same cause on another symbol / minute is the same alert, a new cause is a new alert.
State: the engine alert file (`engine_signal._alert_path`, key "_gate_error": {cause key: day}); the day is recorded only when the send
succeeded (as `engine_signal.alert_data_problem`), so a failed send is tried again next cycle. Never raises, never blocks or changes an
order / entry / exit — display only. `text()` is a single small function so the Telegram message standard (⚠️ type) can re-skin it.
"""
import datetime as _dt
import json
import os
import re

PATH_WORDS = {
    "level_gate": "the old level-bot check in the 15M SRv2 bot",
    "engine_entry": "the engine entry step",
    "engine_store": "the engine store",
    "vision": "the approval (Vision) step",
}
_EXC = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Timeout|Late|Missing|Rejected|Interrupt|Exit))\b")
_SEEN = set()                                                              # this process: cause keys already handled today (no file read)


def _now(now=None):
    if now is not None:
        return now
    try:
        from zoneinfo import ZoneInfo
        return _dt.datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    except Exception:                                                      # noqa: BLE001
        return _dt.datetime.utcnow() + _dt.timedelta(hours=5, minutes=30)


def clean(detail):
    """The error without the internal prefix ("gate error (fail-closed): ", "[GATE] <band> · ") — one line."""
    d = str(detail or "").replace("\n", " ").strip()
    d = re.sub(r"^\[GATE\]\s*[^·]*·\s*", "", d)
    d = re.sub(r"^gate error \(fail-closed\):\s*", "", d)
    return d[:200]


def cause_key(path, detail):
    """path + the exception name (else the reason's words without numbers / prices) ⇒ one alert per cause per day."""
    d = clean(detail)
    m = _EXC.search(d)
    words = m.group(1) if m else re.sub(r"\s+", " ", re.sub(r"[\d.,:–\-]+", " ", d)).strip()[:60]
    return f"{path}|{words}"


def text(path, symbol, detail, now, engine_entry_waiting=None):
    """The plain-words ⚠️ line (one message). engine_entry_waiting: True / False / None (not known) — whether an engine entry was waiting
    at that moment; for the level-bot check it also says that check never decides engine entries."""
    where = PATH_WORDS.get(path, path)
    lines = [f"⚠️ Alert — error in {where} ({str(symbol).upper()}, first at {now:%H:%M}). No action — information.",
             f"• What failed: {clean(detail)}",
             "• Safe side: no entry was taken from it; exits are not affected."]
    if path == "level_gate":
        lines.append("• Engine entries are decided by the engine models, not by this check"
                     + (" — an engine entry was waiting then and was handled by the engine step." if engine_entry_waiting
                        else "."))
    elif engine_entry_waiting:
        lines.append("• An engine entry was waiting at that moment and was NOT taken because of this error.")
    lines.append("• One alert per cause per day; the cause is being fixed.")
    return "\n".join(lines)


def _sender():
    """The default Telegram sender (tests replace this — never a real message from a test run)."""
    from notifications import send_telegram_message
    return send_telegram_message


def _state_path(state_path=None):
    if state_path:
        return state_path
    import engine_signal as ES
    return ES._alert_path(None)


def alert(path, symbol, detail, engine_entry_waiting=None, send=None, state_path=None, now=None):
    """One ⚠️ Telegram line per (path, cause) per day. Returns True when sent now. Never raises."""
    try:
        now = _now(now)
        day = str(now.date()) if hasattr(now, "date") else str(now)[:10]
        key = cause_key(path, detail)
        if (key, day) in _SEEN:
            return False
        p = _state_path(state_path)
        try:
            st = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        except (OSError, ValueError):
            st = {}
        st = st if isinstance(st, dict) else {}
        seen = st.get("_gate_error") if isinstance(st.get("_gate_error"), dict) else {}
        if seen.get(key) == day:
            _SEEN.add((key, day))
            return False
        line = text(path, symbol, detail, now, engine_entry_waiting)
        try:
            if send is None:
                send = _sender()
            ok = send(line) is not False
        except Exception as exc:                                           # noqa: BLE001
            print(f"{line}  [Telegram send failed: {type(exc).__name__}]")
            ok = False
        if not ok:
            return False
        _SEEN.add((key, day))
        seen = {k: v for k, v in seen.items() if v == day}                 # only today's keys are kept
        seen[key] = day
        st["_gate_error"] = seen
        try:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            json.dump(st, open(p, "w", encoding="utf-8"))
        except OSError:
            pass
        return True
    except Exception as exc:                                               # noqa: BLE001 — an alert never stops anything
        print(f"⚠️ gate_alert: {type(exc).__name__}: {exc}")
        return False


def is_error(r):
    """A level-gate result that is an error (state ERROR, or a reason carrying the fail-closed error prefix, e.g. the Daily trend fetch)."""
    from . import level_reaction as LR
    return bool(r) and (r.get("state") == "ERROR" or str(r.get("reason") or "").startswith(LR.R_ERROR))
