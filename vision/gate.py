"""vision/gate.py — bots साठी entry gate (V0 + V1). **Reduce-only, कधीच raise नाही.** Exit मार्गात वापर नाही.

    g = entry_gate(bot, symbol, trading_mode, direction, level, role, setup_tf, now, spot, lots, naked_lots, ...)
    g.action: ENTER (g.lots / g.naked_lots ने — ≤ मूळ) · HOLD (आत्ता entry नाही; vision / तुमचा निर्णय बाकी) ·
              SHADOW (नाकारलेला — मूळ lots ने PAPER shadow trade, source "<bot>_vision_shadow")

🎓 प्रवाह (V1 mode, PAPER bot):
  1. पहिल्यांदा signal ⇒ QUEUED row + HOLD (signal_log: SKIPPED_VISION_PENDING — hit / cooldown मोजणीत नाही).
  2. Worker: chart + vision ⇒ `decide` ⇒ APPROVED / REJECTED / PENDING_HUMAN (Telegram बटणं). Timeout ⇒ timeout नियम.
  3. Bot पुढच्या cycle ला `forced_levels` मुळे तो level पुन्हा तपासतो (touch नसला तरी) ⇒ bot चे सगळे gates पुन्हा ⇒ इथे:
     APPROVED ⇒ drift guard ⇒ ठीक: EXECUTED + ENTER (factor) · अपयश: DRIFT_REJECTED + SHADOW
     REJECTED ⇒ SHADOWED + SHADOW.  Half size चे lots 0 झाले ⇒ SHADOW.
  4. `exec_window_min` मध्ये bot पोहोचला नाही (gates बदलले) ⇒ EXPIRED (gate स्वतः किंवा worker).
  5. Worker बंद असला तरी अडकत नाही: QUEUED / RUNNING `approve_window_min` पेक्षा जुने ⇒ "vision unavailable + उत्तर नाही" चा नियम;
     PENDING_HUMAN ची मुदत संपली ⇒ timeout नियम — हे gate स्वतःच (`resolve_due`) लावतो.
  6. नाकारलेला level `shadow_cooldown_min` मध्ये पुन्हा ⇒ नवी विचारणा / shadow नाही (SKIPPED_VISION_COOLDOWN).
  7. दिशा किंवा breakout प्रकार बदलला ⇒ जुनी row EXPIRED (shadow नाही), हा touch नवा signal.
LIVE ⇒ effective_mode off ⇒ नेहमी ENTER (algorithm). काही चूक ⇒ ENTER (algorithm, vision_fail_action = ignore सारखं) + print.
**Forced level** (touch नसताना फक्त vision निर्णयामुळे तपासलेला) ⇒ ENTER फक्त ताज्या APPROVED row वरून; बाकी सगळं (mode बदलला, चूक, row नाही)
⇒ HOLD (SKIPPED_VISION_FORCED_STALE) — touch शिवाय algorithm चा entry कधीच नाही.
"""
import json
from dataclasses import dataclass, field

import pandas as pd

from . import config as VC
from . import decide as VD
from . import hook as VH
from . import store as VS

DB_TIMEOUT = 2


@dataclass
class Gate:
    action: str                         # ENTER | HOLD | SHADOW
    lots: int = 0
    naked_lots: int = 0
    factor: float = 1.0
    status: str = ""                    # signal_log trade_status (HOLD / SHADOW साठी)
    signal_id: str = None
    note: str = ""
    drift: list = field(default_factory=list)


def entry_gate(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot, lots, naked_lots=None, tags=None,
               last_bar=None, origin=None, path=None, forced=False):
    """lots / naked_lots = bot च्या **चालू** legs चे lots (बंद leg ⇒ 0). forced = touch नव्हता, फक्त vision निर्णयामुळे तपासलं."""
    naked_lots = lots if naked_lots is None else naked_lots
    try:
        return _gate(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot, lots, naked_lots, tags, last_bar,
                     origin, path, forced)
    except Exception as exc:                                             # vision ची चूक bot ला थांबवत नाही — algorithm चा निर्णय
        if forced:
            print(f"⚠️ vision gate त्रुटी (forced level ⇒ entry नाही): {type(exc).__name__}: {exc}")
            return _stale(f"gate error: {exc}")
        print(f"⚠️ vision gate त्रुटी ⇒ algorithm चा निर्णय (पूर्ण size): {type(exc).__name__}: {exc}")
        return Gate("ENTER", lots, naked_lots, 1.0, note=f"gate error: {exc}")


def _stale(note):
    return Gate("HOLD", status="SKIPPED_VISION_FORCED_STALE", note=f"forced level, ताजा vision निर्णय नाही ({note}) ⇒ entry नाही")


def _hold(sid, note):
    return Gate("HOLD", status="SKIPPED_VISION_PENDING", signal_id=sid, note=note)


def _row_tags(row):
    try:
        return json.loads(row.get("setup_json") or "{}").get("tags") or {}
    except (ValueError, AttributeError):
        return {}


def _same_setup(row, direction, tags):
    """दिशा आणि breakout प्रकार तेच? (वेगळे ⇒ वेगळा setup — जुना निर्णय लागू नाही.)"""
    return (str(row.get("direction") or "").upper() == str(direction or "").upper()
            and bool(_row_tags(row).get("breakout_entry")) == bool((tags or {}).get("breakout_entry")))


def resolve_due(row, s, now=None, path=None, timeout=DB_TIMEOUT):
    """मुदत संपलेल्या V1 rows ला नियम लावणे (worker असो वा नसो). रिटर्न (ताजी row, बदलला status | None).
      PENDING_HUMAN, deadline गेली ⇒ timeout_status / timeout_factor.
      QUEUED / RUNNING, created_at + approve_window_min गेले (worker बंद / अडकला) ⇒ vision unavailable आणि उत्तर नाही: `decide` चा
      timeout निकाल (veto_then_confirm ⇒ algorithm पूर्ण size; human_confirm ⇒ skip; auto_veto ⇒ vision_fail_action)."""
    now = pd.Timestamp(now or VS.now_ist())
    sid, st = row["signal_id"], row["status"]
    if st == "PENDING_HUMAN" and row.get("deadline") and pd.Timestamp(row["deadline"]) <= now:
        to, f = row.get("timeout_status") or "REJECTED", float(row.get("timeout_factor") or 0.0)
        if VS.transition(sid, "PENDING_HUMAN", to, path, timeout, factor=f, decided_at=VS._iso(now), decided_by="timeout",
                         decision_reason=f"timeout ⇒ {'skip' if to == 'REJECTED' else f'×{f}'}", final_decision="ENTER" if f > 0 else "SKIP"):
            return VS.get_signal(sid, path), to
    elif (st in ("QUEUED", "RUNNING") and row.get("mode") in VC.V1_MODES and row.get("created_at")
          and pd.Timestamp(row["created_at"]) + pd.Timedelta(minutes=int(s["approve_window_min"])) <= now):
        d = VD.decide(row["mode"], "unavailable", s)
        to, f = (d.timeout_status, d.timeout_factor) if d.ask_human else (d.status, d.factor)
        if VS.transition(sid, ("QUEUED", "RUNNING"), to, path, timeout, verdict="unavailable", factor=f, decided_at=VS._iso(now),
                         decided_by="stale", error="worker उशीर / बंद ⇒ vision आणि उत्तर नाही",
                         decision_reason=f"{d.reason} · मुदतीत उत्तर नाही ⇒ {'skip' if f <= 0 else f'×{f}'}",
                         final_decision="ENTER" if f > 0 else "SKIP"):
            return VS.get_signal(sid, path), to
    return VS.get_signal(sid, path) or row, None


def _exec_expired(row, s, now):
    return bool(row.get("decided_at")) and pd.Timestamp(row["decided_at"]) + pd.Timedelta(minutes=int(s["exec_window_min"])) <= now


def _gate(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot, lots, naked_lots, tags, last_bar, origin, path,
          forced):
    s = VC.load(bot, path, DB_TIMEOUT)
    mode = VC.effective_mode(s, trading_mode)
    full = Gate("ENTER", lots, naked_lots, 1.0)
    sym = str(symbol).upper()
    listed = sym in [x.upper() for x in s.get("symbols") or []]
    if mode not in VC.V1_MODES or not listed:
        if forced:
            return _stale(f"mode {mode}")
        if mode in VC.V0_MODES and mode != "off" and listed:            # shadow / notify — फक्त नोंद
            VH.submit_signal(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot, tags=tags, last_bar=last_bar,
                             path=path)
        return full
    now = pd.Timestamp(VS.now_ist())
    day = VS._iso(signal_ts)[:10]
    row = VS.find_open_decision(bot, sym, setup_tf, level, day, path=path, timeout=DB_TIMEOUT)
    if row is not None:
        row, _ = resolve_due(row, s, now, path)
        if row["status"] in ("APPROVED", "REJECTED") and _exec_expired(row, s, now):
            VS.transition(row["signal_id"], row["status"], "EXPIRED", path, DB_TIMEOUT,
                          exec_note=f"{row['status']} नंतर {s['exec_window_min']} मिनिटांत bot पोहोचला नाही")
            row = None
        elif row["status"] not in VS.OPEN_V1:
            row = None
    if row is not None and not _same_setup(row, direction, tags):
        VS.transition(row["signal_id"], VS.OPEN_V1, "EXPIRED", path, DB_TIMEOUT, executed_at=VS._iso(now),
                      exec_note=f"setup बदलला ({row.get('direction')} → {direction}) ⇒ रद्द, shadow नाही; नवा signal")
        row = None
    if row is None:
        if forced:
            return _stale("row नाही / कालबाह्य")
        cool = int(s.get("shadow_cooldown_min") or 0)
        if cool > 0:
            prev = VS.recent_closed(bot, sym, setup_tf, level, now - pd.Timedelta(minutes=cool), path=path, timeout=DB_TIMEOUT,
                                    match=lambda r: _same_setup(r, direction, tags))      # वेगळी दिशा / breakout ⇒ नवा setup, cooldown नाही
            if prev is not None:
                return Gate("HOLD", status="SKIPPED_VISION_COOLDOWN", signal_id=prev["signal_id"],
                            note=f"हा level {str(prev['executed_at'])[11:16]} ला नाकारला ({prev['status']}) — {cool} मिनिटं पुन्हा नाही")
        sid = VH._submit(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot, "ENTER", tags, None, path, last_bar)
        return _hold(sid, "vision / तुमच्या निर्णयाची वाट")
    sid = row["signal_id"]
    if row["status"] in ("QUEUED", "RUNNING", "PENDING_HUMAN"):
        return _stale(row["status"]) if forced else _hold(sid, row["status"])
    ts = VS._iso(now)
    if row["status"] == "REJECTED":
        if VS.transition(sid, "REJECTED", "SHADOWED", path, DB_TIMEOUT, executed_at=ts, exec_note="shadow (rejected)"):
            return Gate("SHADOW", lots, naked_lots, 0.0, "SKIPPED_VISION_REJECTED", sid, row.get("decision_reason") or "rejected")
        return _stale("race") if forced else _hold(sid, "race")
    # APPROVED
    drift = VD.drift_guard(row, spot, direction, s["max_drift_mr"], origin)
    if drift:
        if VS.transition(sid, "APPROVED", "DRIFT_REJECTED", path, DB_TIMEOUT, executed_at=ts, drift_result="; ".join(drift)):
            return Gate("SHADOW", lots, naked_lots, 0.0, "SKIPPED_VISION_DRIFT", sid, "; ".join(drift), drift)
        return _stale("race") if forced else _hold(sid, "race")
    f = float(row.get("factor") or 0.0)
    l1, l2 = VD.scaled_lots(lots, f), VD.scaled_lots(naked_lots, f)
    # चालू leg (lots > 0) चे lots 0 झाले ⇒ entry नाही (0-lot order / multi-account चा max(1, …) टाळायला) ⇒ shadow
    if (l1 == 0 and l2 == 0) or (lots > 0 and l1 == 0) or (naked_lots > 0 and l2 == 0):
        if VS.transition(sid, "APPROVED", "SHADOWED", path, DB_TIMEOUT, executed_at=ts, drift_result="ok",
                         exec_note=f"factor {f} ⇒ lots {l1}/{l2} ⇒ shadow"):
            return Gate("SHADOW", lots, naked_lots, f, "SKIPPED_VISION_HALF_ZERO", sid, f"factor {f} ⇒ एका leg चे 0 lots")
        return _stale("race") if forced else _hold(sid, "race")
    if VS.transition(sid, "APPROVED", "EXECUTED", path, DB_TIMEOUT, executed_at=ts, drift_result="ok", exec_note=f"lots {l1}/{l2}"):
        return Gate("ENTER", l1, l2, f, "", sid, f"approved ×{f}")
    return _stale("race") if forced else _hold(sid, "race")


def forced_levels(bot, symbol, trading_mode="PAPER", path=None):
    """Bot ने या cycle ला touch नसला तरी पुन्हा तपासायचे levels [(level, setup_tf, role)] — फक्त V1 mode + symbol यादीत असेल तर, आणि फक्त
    आजचे: APPROVED / REJECTED (exec_window मध्ये), तसेच मुदत संपलेले PENDING_HUMAN / QUEUED / RUNNING (gate त्यांना timeout नियम लावतो).
    कधीच raise नाही."""
    try:
        s = VC.load(bot, path, DB_TIMEOUT)
        sym = str(symbol).upper()
        if VC.effective_mode(s, trading_mode) not in VC.V1_MODES or sym not in [x.upper() for x in s.get("symbols") or []]:
            return []
        now = pd.Timestamp(VS.now_ist())
        day = now.strftime("%Y-%m-%d")
        out = []
        for r in VS.rows_with_status(VS.OPEN_V1, path, DB_TIMEOUT, bot=bot, symbol=sym):
            if r["level"] is None or str(r["signal_ts"])[:10] != day:
                continue
            st = r["status"]
            if st in ("APPROVED", "REJECTED"):
                ok = not _exec_expired(r, s, now)
            elif st == "PENDING_HUMAN":
                ok = bool(r.get("deadline")) and pd.Timestamp(r["deadline"]) <= now
            else:
                ok = bool(r.get("created_at")) and pd.Timestamp(r["created_at"]) + pd.Timedelta(minutes=int(s["approve_window_min"])) <= now
            if ok:
                out.append((float(r["level"]), r["setup_tf"], r["role"]))
        return out
    except Exception as exc:
        print(f"⚠️ vision forced_levels त्रुटी: {exc}")
        return []


def is_forced(forced, level, setup_tf, tol_pct=0.05):
    try:
        return any(tf == setup_tf and abs(lv - float(level)) <= abs(float(level)) * tol_pct / 100.0 for lv, tf, _ in forced or [])
    except Exception:
        return False


def note_execution(signal_id, text, path=None):
    """Bot चा प्रत्यक्ष निकाल (OPENED / FAILED / shadow) — best effort."""
    if not signal_id:
        return
    try:
        VS.update(signal_id, path, exec_note=str(text)[:300])
    except Exception:
        pass
