"""Vision V1 — veto_then_confirm / auto_veto / human_confirm: निर्णय नियम, reduce-only gate, drift guard, Telegram callback security,
timeout, restart expiry, LIVE वर V1 नाही, shadow tracking."""
import datetime as dt
import json

import pytest

from tests.test_vision_v0 import CTX_OK, GOOD, m1_frame, msg, run
from vision import config as VC
from vision import decide as VD
from vision import gate as VG
from vision import store as VS
from vision import telegram_bot as TB
from vision import worker as VW

KEY = "test-secret-not-real"
ME = 123456789


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "vision.db")
    monkeypatch.setenv("VISION_DB_PATH", p)
    monkeypatch.setenv("VISION_IMAGE_DIR", str(tmp_path / "visual_audit"))
    monkeypatch.setenv("VISION_CALLBACK_SECRET", KEY)
    monkeypatch.setenv("TELEGRAM_APPROVER_IDS", str(ME))
    sent = {"photos": [], "edits": [], "texts": [], "answers": []}
    from vision import tg as TG
    monkeypatch.setattr(TG, "send_photo", lambda png, cap, buttons=None, chat_id=None: (sent["photos"].append((cap, buttons)), 777)[1])
    monkeypatch.setattr(TG, "edit_caption", lambda mid, cap, chat_id=None, has_photo=True: sent["edits"].append((mid, cap)) or True)
    monkeypatch.setattr(TG, "send_text", lambda t, chat_id=None: sent["texts"].append(t) or True)
    monkeypatch.setattr(TG, "answer_callback", lambda cid, t: sent["answers"].append(t) or True)
    monkeypatch.setattr(TG, "_creds", lambda: ("tok-not-real", str(ME)))          # बटणांचा chat = approver (खाजगी chat)
    sent["clock"] = [NOW]                                                          # IST घड्याळ — tests पुढे सरकवतात
    monkeypatch.setattr(VS, "now_ist", lambda: sent["clock"][0])
    return sent


def tick(db, minutes):
    db["clock"][0] = db["clock"][0] + dt.timedelta(minutes=minutes)


S = {**VC.BOT_DEFAULTS, "vision_gray_action": "half", "vision_disagree_action": "skip", "vision_fail_action": "ignore", "timeout_action": "auto_veto"}
NOW = dt.datetime(2026, 10, 6, 10, 42, 20)


def paper(bot, sym):
    return "PAPER"


def set_mode(mode, bot="dynamic_sr_instant"):
    VC.save(bot, {"vision_mode": mode}, "t", trading_mode_fn=paper)


def gate(lots=2, naked=1, spot=25010.0, direction="BULLISH", level=25000.0, ts=NOW):
    return VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", direction, level, "SUPPORT", "5M", ts, spot, lots, naked)


# ------------------------------------------------------------------------------------------------ निर्णय नियम
def test_decide_rules_all_modes():
    d = VD.decide("auto_veto", "agree", S)
    assert (d.status, d.factor) == ("APPROVED", 1.0)
    assert (VD.decide("auto_veto", "gray", S).factor, VD.decide("auto_veto", "disagree", S).status) == (0.5, "REJECTED")
    assert VD.decide("auto_veto", "unavailable", S).status == "APPROVED"                          # fail_action ignore ⇒ algorithm
    assert VD.decide("auto_veto", "unavailable", {**S, "vision_fail_action": "skip"}).status == "REJECTED"
    d = VD.decide("veto_then_confirm", "disagree", S)
    assert d.status == "REJECTED" and not d.ask_human                                             # आपोआप skip, बटण नाही
    d = VD.decide("veto_then_confirm", "agree", S)
    assert (d.status, d.factor, d.timeout_status, d.timeout_factor, d.ask_human) == ("PENDING_HUMAN", 1.0, "APPROVED", 1.0, True)
    d = VD.decide("veto_then_confirm", "gray", S)
    assert (d.factor, d.timeout_factor) == (0.5, 0.5)                                            # gray ⇒ अर्धा, timeout ⇒ auto_veto (अर्धा)
    assert VD.decide("veto_then_confirm", "agree", {**S, "timeout_action": "skip"}).timeout_status == "REJECTED"
    d = VD.decide("veto_then_confirm", "unavailable", S)
    assert d.ask_human and (d.timeout_status, d.timeout_factor) == ("APPROVED", 1.0)              # unavailable ⇒ विचार; timeout ⇒ algorithm
    d = VD.decide("human_confirm", "agree", S)
    assert d.ask_human and d.timeout_status == "REJECTED"                                         # human_confirm: timeout ⇒ skip
    for m in ("auto_veto", "human_confirm", "veto_then_confirm"):
        for v in ("agree", "gray", "disagree", "unavailable"):
            dd = VD.decide(m, v, S)
            assert 0.0 <= dd.factor <= 1.0 and (dd.timeout_factor is None or 0.0 <= dd.timeout_factor <= 1.0)   # reduce-only


def test_scaled_lots_reduce_only():
    assert VD.scaled_lots(4, 0.5) == 2 and VD.scaled_lots(3, 0.5) == 1 and VD.scaled_lots(1, 0.5) == 0
    assert VD.scaled_lots(2, 1.0) == 2 and VD.scaled_lots(2, 7.0) == 2 and VD.scaled_lots(2, 0.0) == 0


def test_drift_guard_rules():
    row = {"spot": 25010.0, "median_range": 20.0, "direction": "BULLISH", "invalidation": None}
    assert VD.drift_guard(row, 25015.0, "BULLISH", 0.5) == []
    assert "drift" in VD.drift_guard(row, 25025.0, "BULLISH", 0.5)[0]                            # 1. 15 > 0.5 × 20
    assert "बाजू" in VD.drift_guard(row, 25012.0, "BEARISH", 0.5)[0]                             # 2. level ओलांडला (दिशा उलटली)
    assert "invalidation" in VD.drift_guard({**row, "invalidation": 25009.0}, 25008.0, "BULLISH", 5)[0]
    assert "origin" in VD.drift_guard(row, 25012.0, "BULLISH", 5, origin=25011.0)[-1]            # 3. pullback origin ओलांडला
    # 4. daily loss / kill switch / max-open: bot चे gates gate पर्यंत पुन्हा चालतात (रचना) — test_bots_use_gate_reduce_only


# ------------------------------------------------------------------------------------------------ gate (bot बाजू)
def test_gate_v0_modes_enter_full_and_live_untouched(db):
    assert gate().action == "ENTER" and gate().lots == 2                                          # notify (default)
    set_mode("veto_then_confirm")
    g = VG.entry_gate("dynamic_sr_instant", "NIFTY", "LIVE", "BULLISH", 25000.0, "SUPPORT", "5M", NOW, 25010.0, 2, 1)
    assert g.action == "ENTER" and g.lots == 2                                                    # LIVE ⇒ vision नाही
    assert not [r for r in VS.list_signals() if r["mode"] == "veto_then_confirm"]


def test_gate_flow_hold_then_approved_then_executed_once(db):
    set_mode("veto_then_confirm")
    g = gate()
    assert g.action == "HOLD" and g.status == "SKIPPED_VISION_PENDING"
    sid = g.signal_id
    assert gate().action == "HOLD" and gate().signal_id == sid                                    # दुसऱ्या मिनिटाला तीच row
    VS.update(sid, status="APPROVED", factor=0.5, decided_at=VS._iso(NOW), median_range=20.0)
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY") == [(25000.0, "5M", "SUPPORT")]
    g = gate(lots=4, naked=2)
    assert (g.action, g.lots, g.naked_lots, g.factor) == ("ENTER", 2, 1, 0.5)
    assert VS.get_signal(sid)["status"] == "EXECUTED" and VG.forced_levels("dynamic_sr_instant", "NIFTY") == []
    assert gate().action == "HOLD"                                                                # executed ⇒ नवा signal (QUEUED)


def test_gate_half_of_one_lot_is_shadow_and_rejected_is_shadow_once(db):
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    VS.update(sid, status="APPROVED", factor=0.5, decided_at=VS._iso(NOW), median_range=20.0)
    g = gate(lots=1, naked=1)
    assert g.action == "SHADOW" and g.status == "SKIPPED_VISION_HALF_ZERO" and g.lots == 1      # shadow मूळ lots ने
    assert VS.get_signal(sid)["status"] == "SHADOWED"
    sid2 = gate(level=25300.0).signal_id
    VS.update(sid2, status="REJECTED", factor=0.0, decided_at=VS._iso(NOW))
    g = gate(level=25300.0)
    assert g.action == "SHADOW" and g.status == "SKIPPED_VISION_REJECTED"
    assert VS.get_signal(sid2)["status"] == "SHADOWED"
    n = len(VS.list_signals())
    g = gate(level=25300.0)                                                                       # त्याच level ला पुन्हा touch
    assert g.action == "HOLD" and g.status == "SKIPPED_VISION_COOLDOWN" and len(VS.list_signals()) == n   # नवी विचारणा / shadow नाही
    tick(db, 31)
    g = gate(level=25300.0, ts=db["clock"][0])
    assert g.status == "SKIPPED_VISION_PENDING" and len(VS.list_signals()) == n + 1               # cooldown नंतर नवा signal


def test_cooldown_only_for_same_setup(db):
    """Re-review: bearish नाकारून shadow झाला, मग खरा bullish touch ⇒ cooldown नाही (नवा signal)."""
    set_mode("veto_then_confirm")
    sid = gate(direction="BEARISH").signal_id
    VS.update(sid, status="REJECTED", factor=0.0, decided_at=VS._iso(NOW))
    assert gate(direction="BEARISH").action == "SHADOW"
    assert gate(direction="BEARISH").status == "SKIPPED_VISION_COOLDOWN"
    g = gate(direction="BULLISH")
    assert g.status == "SKIPPED_VISION_PENDING" and g.signal_id != sid


def test_housekeeping_expires_old_day_rows_quietly(db):
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    db["clock"][0] = NOW + dt.timedelta(days=1)
    VW.v1_housekeeping()
    r = VS.get_signal(sid)
    assert r["status"] == "EXPIRED" and r["transition_notified"] == 1 and not db["texts"]


def test_gate_zero_lot_leg_never_enters(db):
    """Review B2: एका चालू leg चे lots 0 ⇒ ENTER नाही (0-lot order / multi-account max(1, …) टाळायला); बंद leg (0) चालतो."""
    set_mode("veto_then_confirm")
    sid = gate(lots=1, naked=2).signal_id
    VS.update(sid, status="APPROVED", factor=0.5, decided_at=VS._iso(NOW), median_range=20.0)
    g = gate(lots=1, naked=2)
    assert g.action == "SHADOW" and g.status == "SKIPPED_VISION_HALF_ZERO"
    sid = gate(lots=2, naked=0, level=25200.0, spot=25205.0).signal_id
    VS.update(sid, status="APPROVED", factor=0.5, decided_at=VS._iso(NOW), median_range=20.0)
    g = gate(lots=2, naked=0, level=25200.0, spot=25205.0)
    assert (g.action, g.lots, g.naked_lots) == ("ENTER", 1, 0)


def fgate(**kw):
    return VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", kw.pop("direction", "BULLISH"), kw.pop("level", 25000.0), "SUPPORT", "5M",
                         NOW, kw.pop("spot", 25010.0), 2, 1, forced=True, **kw)


def test_forced_level_never_enters_without_fresh_approval(db, monkeypatch):
    """Review B1: forced (touch नाही) ⇒ ENTER फक्त ताज्या APPROVED वरून. Mode बदलला / exec_window गेली / दुसरा दिवस / gate चूक ⇒ HOLD."""
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    VS.update(sid, status="REJECTED", factor=0.0, decided_at=VS._iso(NOW))
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "PAPER") == [(25000.0, "5M", "SUPPORT")]
    set_mode("notify")                                                                            # तुम्ही /vision notify केलं
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "PAPER") == []
    g = fgate()
    assert g.action == "HOLD" and g.status == "SKIPPED_VISION_FORCED_STALE"
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "LIVE") == []
    set_mode("veto_then_confirm")
    tick(db, 6)                                                                                   # exec_window (5) गेली — worker नसला तरी
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "PAPER") == []
    g = fgate()
    assert g.status == "SKIPPED_VISION_FORCED_STALE" and VS.get_signal(sid)["status"] == "EXPIRED"
    assert not [r for r in VS.list_signals() if r["status"] == "QUEUED"]                         # forced ⇒ नवा signal सुद्धा नाही
    sid = gate(level=25100.0, ts=db["clock"][0]).signal_id
    VS.update(sid, status="APPROVED", factor=1.0, decided_at=VS._iso(db["clock"][0]), median_range=20.0)
    monkeypatch.setattr(VC, "load", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db locked")))
    g = fgate(level=25100.0, spot=25105.0)
    assert g.action == "HOLD" and g.status == "SKIPPED_VISION_FORCED_STALE"                      # चूक + forced ⇒ entry नाही
    assert VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25100.0, "SUPPORT", "5M", NOW, 25105.0, 2, 1).action == "ENTER"
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "PAPER") == []                         # कधीच raise नाही


def test_forced_level_from_yesterday_is_ignored(db):
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    VS.update(sid, status="APPROVED", factor=1.0, decided_at=VS._iso(NOW))
    db["clock"][0] = NOW + dt.timedelta(days=1)
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "PAPER") == []


def test_setup_change_closes_old_row_and_starts_new_signal(db):
    """Review S1: bearish नाकारलेला level, नंतर खरा bullish touch ⇒ जुनी row EXPIRED (shadow नाही), नवा signal (HOLD)."""
    set_mode("veto_then_confirm")
    sid = gate(direction="BEARISH").signal_id
    VS.update(sid, status="REJECTED", factor=0.0, decided_at=VS._iso(NOW))
    g = gate(direction="BULLISH")
    assert g.action == "HOLD" and g.status == "SKIPPED_VISION_PENDING" and g.signal_id != sid
    assert VS.get_signal(sid)["status"] == "EXPIRED" and "setup बदलला" in VS.get_signal(sid)["exec_note"]
    sid3 = g.signal_id
    VS.update(sid3, status="APPROVED", factor=1.0, decided_at=VS._iso(NOW), median_range=20.0)
    g = VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000.0, "SUPPORT", "5M", NOW, 25010.0, 2, 1,
                      tags={"breakout_entry": True}, forced=True)
    assert g.status == "SKIPPED_VISION_FORCED_STALE" and VS.get_signal(sid3)["status"] == "EXPIRED"   # reversal ⇒ breakout: नवा setup


def test_gate_applies_timeouts_when_worker_is_down(db):
    """Review S3: worker बंद ⇒ QUEUED कायम HOLD नाही. approve_window नंतर "unavailable + उत्तर नाही" ⇒ veto_then_confirm: algorithm."""
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    assert VS.expire_stale(0) == 0                                                                # V0 चा stale-expiry V1 row ला लागत नाही
    tick(db, 11)
    assert VG.forced_levels("dynamic_sr_instant", "NIFTY", "PAPER") == [(25000.0, "5M", "SUPPORT")]
    g = fgate()
    r = VS.get_signal(sid)
    assert g.action == "ENTER" and (g.lots, g.naked_lots) == (2, 1) and r["status"] == "EXECUTED" and r["decided_by"] == "stale"
    set_mode("human_confirm")
    sid = gate(level=25300.0, ts=db["clock"][0]).signal_id
    VS.update(sid, status="PENDING_HUMAN", factor=1.0, timeout_status="REJECTED", timeout_factor=0.0,
              deadline=VS._iso(db["clock"][0] + dt.timedelta(minutes=10)))
    tick(db, 10)
    g = VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25300.0, "SUPPORT", "5M", db["clock"][0], 25305.0, 2, 1, forced=True)
    assert g.action == "SHADOW" and VS.get_signal(sid)["status"] == "SHADOWED" and VS.get_signal(sid)["decided_by"] == "timeout"


def test_worker_does_not_overwrite_decision_taken_meanwhile(db, monkeypatch):
    """Review S4: worker चालू असताना bot / service ने row ठरवली ⇒ worker चा finish / बटणं नाहीत."""
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    row = VS.claim_queued()[0]
    VS.transition(sid, "RUNNING", "APPROVED", factor=1.0, decided_by="stale")
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (m1_frame(), None))
    VW.process_row(row)
    assert VS.get_signal(sid)["status"] == "APPROVED" and VS.get_signal(sid)["decided_by"] == "stale" and db["photos"] == []


def test_worker_notify_error_keeps_decision(db, monkeypatch):
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    row = VS.claim_queued()[0]
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (m1_frame(), None))
    monkeypatch.setattr(VW, "v1_notify", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("telegram down")))
    VW.process_row(row)
    r = VS.get_signal(sid)
    assert r["status"] == "PENDING_HUMAN" and r["deadline"]                                       # FAILED नाही, निर्णय टिकला


def test_drift_guard_reads_invalidation_from_setup_and_falls_back_for_median_range():
    """Review S5."""
    row = {"spot": 25010.0, "median_range": 100.0, "direction": "BULLISH", "setup_json": json.dumps({"invalidation": 24990.0})}
    assert [x for x in VD.drift_guard(row, 24985.0, "BULLISH", 0.5) if "invalidation" in x] == ["invalidation 24,990.0 ओलांडली"]
    row["median_range"] = None
    assert VD.drift_guard(row, 25030.0, "BULLISH", 0.5)                                            # fallback 0.1% ⇒ 25 × 0.5 = 12.5 < 20
    assert VD.drift_guard(row, 25015.0, "BULLISH", 0.5) == []


def test_migration_tolerates_concurrent_alter(tmp_path):
    """Review S6: दुसऱ्या process ने आधीच column जोडला (आपल्या PRAGMA नंतर) ⇒ duplicate column चूक गिळली."""
    import sqlite3
    p = str(tmp_path / "v.db")
    with VS.connect(p) as c:
        c.execute("SELECT 1")
    VS._MIGRATED.discard(p)

    class Stale:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, q, *a):
            return iter([]) if q.startswith("PRAGMA") else self.conn.execute(q, *a)
    conn = sqlite3.connect(p)
    VS._migrate(Stale(conn), p)                                                                   # सगळे columns आधीच आहेत ⇒ raise नाही
    conn.close()


def test_no_buttons_when_button_chat_is_not_an_approver(db, monkeypatch):
    """Review S7: बटणं group chat मध्ये जातात पण फक्त user id whitelist ⇒ बटणं नाहीत, caption मध्ये कारण."""
    from vision import tg as TG
    monkeypatch.setattr(TG, "_creds", lambda: ("tok-not-real", "-100555"))
    ok, why = TG.can_ask()
    assert not ok and "chat id" in why
    set_mode("veto_then_confirm")
    gate()
    row = VS.claim_queued()[0]
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (m1_frame(), None))
    VW.process_row(row)
    cap, buttons = db["photos"][-1]
    assert buttons is None and "chat id" in cap


def test_gate_drift_rejects_to_shadow(db):
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    VS.update(sid, status="APPROVED", factor=1.0, decided_at=VS._iso(NOW), median_range=20.0)
    g = gate(spot=25100.0)
    assert g.action == "SHADOW" and g.status == "SKIPPED_VISION_DRIFT" and g.drift
    r = VS.get_signal(sid)
    assert r["status"] == "DRIFT_REJECTED" and "drift" in r["drift_result"]


def test_gate_error_falls_back_to_algorithm(db, monkeypatch):
    set_mode("veto_then_confirm")
    monkeypatch.setattr(VS, "find_open_decision", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db locked")))
    g = gate(lots=3, naked=2)
    assert (g.action, g.lots, g.naked_lots) == ("ENTER", 3, 2)


# ------------------------------------------------------------------------------------------------ worker
def _queue_v1(mode, level=25000.0):
    set_mode(mode)
    return gate(level=level).signal_id


def test_worker_veto_then_confirm_disagree_auto_skip_no_buttons(db, monkeypatch):
    sid = _queue_v1("veto_then_confirm")
    run(None, [msg({**GOOD, "reversal_valid": "no"})], monkeypatch)
    r = VS.get_signal(sid)
    assert r["status"] == "REJECTED" and r["decided_by"] == "vision"
    cap, buttons = db["photos"][-1]
    assert buttons is None and "skip" in cap


def test_worker_veto_then_confirm_agree_asks_with_hmac_buttons(db, monkeypatch):
    sid = _queue_v1("veto_then_confirm")
    run(None, [msg(GOOD)], monkeypatch)
    r = VS.get_signal(sid)
    assert r["status"] == "PENDING_HUMAN" and r["deadline"] and r["tg_message_id"] == 777 and r["factor"] == 1.0
    cap, buttons = db["photos"][-1]
    assert [b[0] for b in buttons] == ["✅ Approve", "❌ Reject"] and "पर्यंत" in cap
    assert VD.parse_callback(buttons[0][1]) == (sid, "A") and VD.parse_callback(buttons[1][1]) == (sid, "R")


def test_worker_auto_veto_gray_half_no_human(db, monkeypatch):
    sid = _queue_v1("auto_veto")
    run(None, [msg({**GOOD, "level_real": "unclear"})], monkeypatch)
    r = VS.get_signal(sid)
    assert (r["status"], r["factor"], r["verdict"]) == ("APPROVED", 0.5, "gray") and db["photos"][-1][1] is None


def test_worker_no_secret_means_no_buttons_and_timeout_rule(db, monkeypatch):
    sid = _queue_v1("veto_then_confirm")
    monkeypatch.delenv("VISION_CALLBACK_SECRET")
    run(None, [msg(GOOD)], monkeypatch)
    cap, buttons = db["photos"][-1]
    assert buttons is None and "बटणं नाहीत" in cap and VS.get_signal(sid)["status"] == "PENDING_HUMAN"


# ------------------------------------------------------------------------------------------------ Telegram callback security
def _pending(monkeypatch, db):
    sid = _queue_v1("veto_then_confirm")
    run(None, [msg(GOOD)], monkeypatch)
    return sid, db["photos"][-1][1]


def _cq(data, uid=ME, chat=ME):
    return {"id": "cb1", "data": data, "from": {"id": uid}, "message": {"chat": {"id": chat}}}


def test_callback_security_other_user_bad_hmac_replay_and_double_approve(db, monkeypatch):
    sid, buttons = _pending(monkeypatch, db)
    now = dt.datetime(2026, 10, 6, 10, 44)
    assert TB.handle_callback(_cq(buttons[0][1], uid=999), now=now) == (False, "unauthorized")       # दुसरा from.id
    assert TB.handle_callback(_cq(buttons[0][1], chat=-100), now=now) == (False, "unauthorized")     # दुसरा chat
    forged = f"v1|{sid}|A|{'0' * 16}"
    assert TB.handle_callback(_cq(forged), now=now) == (False, "bad_hmac")
    assert TB.handle_callback(_cq(VD.callback_data(sid, "A", key="wrong")), now=now) == (False, "bad_hmac")
    ok, _ = TB.handle_callback(_cq(buttons[0][1]), now=now)
    assert ok and VS.get_signal(sid)["status"] == "APPROVED" and VS.get_signal(sid)["human_decision"] == "approve"
    assert TB.handle_callback(_cq(buttons[0][1]), now=now) == (False, "already")                    # replay / दोनदा approve
    assert TB.handle_callback(_cq(buttons[1][1]), now=now) == (False, "already")                    # नंतर reject सुद्धा नाही
    assert len([e for e in VS.list_signals() if e["status"] == "APPROVED"]) == 1


def test_callback_expired_and_reject(db, monkeypatch):
    sid, buttons = _pending(monkeypatch, db)
    late = dt.datetime(2026, 10, 6, 11, 30)
    assert TB.handle_callback(_cq(buttons[0][1]), now=late) == (False, "expired")
    sid2 = _queue_v1("veto_then_confirm", level=25300.0)
    run(None, [msg(GOOD)], monkeypatch)
    b2 = db["photos"][-1][1]
    ok, _ = TB.handle_callback(_cq(b2[1][1]), now=dt.datetime(2026, 10, 6, 10, 44))
    assert ok and VS.get_signal(sid2)["status"] == "REJECTED" and VS.get_signal(sid2)["factor"] == 0.0


def test_timeout_applies_mode_rule_and_restart_expires_pending(db, monkeypatch):
    sid, _ = _pending(monkeypatch, db)
    VW.v1_housekeeping(now=dt.datetime(2026, 10, 6, 11, 30))
    r = VS.get_signal(sid)
    assert (r["status"], r["factor"], r["decided_by"]) == ("APPROVED", 1.0, "timeout")             # veto_then_confirm agree ⇒ auto_veto पूर्ण
    assert any("उत्तर आलं नाही" in e[1] for e in db["edits"])
    sid2 = _queue_v1("human_confirm", level=25300.0)
    run(None, [msg(GOOD)], monkeypatch)
    VW.v1_housekeeping(now=dt.datetime(2026, 10, 6, 11, 30))
    assert VS.get_signal(sid2)["status"] == "REJECTED"                                            # human_confirm timeout ⇒ skip
    sid3 = _queue_v1("veto_then_confirm", level=25500.0)
    run(None, [msg(GOOD)], monkeypatch)
    assert TB.expire_on_restart() == 1 and VS.get_signal(sid3)["status"] == "EXPIRED"            # restart ⇒ stale approve नाही


def test_unused_decisions_expire_after_exec_window(db, monkeypatch):
    sid = _queue_v1("auto_veto")
    run(None, [msg(GOOD)], monkeypatch)
    assert VS.get_signal(sid)["status"] == "APPROVED"
    VW.v1_housekeeping(now=dt.datetime(2026, 10, 6, 11, 30))
    r = VS.get_signal(sid)
    assert r["status"] == "EXPIRED" and "पोहोचला नाही" in r["exec_note"]
    VW.v1_housekeeping(now=dt.datetime(2026, 10, 6, 11, 31))
    assert len([t for t in db["texts"] if "⌛" in t]) == 1                                       # माहिती एकदाच


def test_commands_only_for_approver_and_live_guard(db, monkeypatch):
    out = []
    assert TB.handle_command("/today", {"id": 1}, {"id": 1}, send=out.append) == (False, "unauthorized")
    assert TB.handle_command("/pending", {"id": ME}, {"id": ME}, send=out.append)[0]
    ok, _ = TB.handle_command("/vision vtc dynamic_sr_instant", {"id": ME}, {"id": ME}, send=out.append, trading_mode_fn=paper)
    assert ok and VC.load("dynamic_sr_instant")["vision_mode"] == "veto_then_confirm"
    ok, why = TB.handle_command("/vision confirm srv2_momentum_reversal", {"id": ME}, {"id": ME}, send=out.append,
                                trading_mode_fn=lambda b, s: "LIVE")
    assert not ok and "PAPER" in why and VC.load("srv2_momentum_reversal")["vision_mode"] == "notify"
    assert VC.history()[-1]["by"] == f"telegram:{ME}"


def test_outcome_uses_shadow_source_for_rejected(db, monkeypatch, tmp_path):
    import sqlite3
    from vision import outcome as VO
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    VS.update(sid, status="REJECTED", factor=0.0, decided_at=VS._iso(NOW))
    gate()                                                                                        # SHADOWED (executed_at = आता)
    VS.update(sid, executed_at="2026-10-06T10:45:00")
    tdb = str(tmp_path / "t.db")
    c = sqlite3.connect(tdb)
    c.execute("CREATE TABLE live_trades (trade_id TEXT, symbol TEXT, entry_time TEXT, mode TEXT, source TEXT, status TEXT)")
    c.execute("INSERT INTO live_trades VALUES ('S1','NIFTY','2026-10-06 10:45:30','PAPER','dynamic_sr_instant_vision_shadow','OPEN')")
    c.execute("INSERT INTO live_trades VALUES ('R1','NIFTY','2026-10-06 10:45:30','PAPER','dynamic_sr_instant','OPEN')")
    c.commit()
    c.close()
    assert VO.find_trade(VS.get_signal(sid), tdb)["trade_id"] == "S1"


def test_v1_event_log_records_transitions(db):
    set_mode("veto_then_confirm")
    sid = gate().signal_id
    VS.update(sid, status="APPROVED", factor=1.0, decided_at=VS._iso(NOW), median_range=20.0)
    gate()
    with VS.connect() as c:
        ev = [r["event"] for r in c.execute("SELECT event FROM vision_events WHERE signal_id=?", (sid,))]
    assert "APPROVED→EXECUTED" in ev
    assert json.loads(VS.get_signal(sid)["setup_json"])["bot_label"]


def test_dashboard_hides_v1_modes_for_live_bots():
    import page_vision_human_eye as P
    assert set(P.mode_options("dynamic_sr_instant", "LIVE")) == {"off", "shadow", "notify"}
    assert set(P.mode_options("dynamic_sr_instant", "UNKNOWN")) == {"off", "shadow", "notify"}
    assert "veto_then_confirm" in P.mode_options("dynamic_sr_instant", "PAPER")


def _dryrun_mod():
    import importlib.util
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("vdry", os.path.join(root, "scripts", "vision_dryrun.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("press,drift,want", [("A", False, "EXECUTED"), ("R", False, "SHADOWED"), ("A", True, "DRIFT_REJECTED"),
                                              (None, False, "EXECUTED")])
def test_dryrun_end_to_end_no_order(db, monkeypatch, press, drift, want):
    """Dry-run: TEST signal ⇒ बटणं ⇒ approve / reject / timeout ⇒ drift guard ⇒ निकाल. Order कधीच नाही (trading_engine import नाही)."""
    from vision import chart as CH
    from vision import tg as TG
    mod = _dryrun_mod()
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (m1_frame(), None))
    monkeypatch.setattr(CH, "render", lambda df, s, daily=None: (b"\x89PNGfake", {"error": None, "median_range": 10.0, "ctx": CTX_OK}))

    def updates(offset, timeout=50):
        if press is None:
            pend = VS.rows_with_status("PENDING_HUMAN")
            if pend:
                VS.update(pend[0]["signal_id"], deadline="2000-01-01T00:00:00")          # timeout लगेच
            return []
        pend = VS.rows_with_status("PENDING_HUMAN")
        if not pend:
            return []
        return [{"update_id": offset + 1, "callback_query": _cq(VD.callback_data(pend[0]["signal_id"], press))}]
    monkeypatch.setattr(TG, "get_updates", updates)
    args = ["--no-vision", "--window", "1"] + (["--drift"] if drift else [])
    assert mod.main(args) == 0
    r = [x for x in VS.list_signals() if x["bot"] == "vision_dryrun"][0]
    assert r["status"] == want and "order नाही" in (r["exec_note"] or "")
    assert any("DRY-RUN" in t for t in db["texts"]) and db["photos"][0][1]                       # बटणांसह chart, निकाल संदेश
    src = open(mod.__file__, encoding="utf-8").read()
    assert "trading_engine" not in src and "open_multi_leg_trade" not in src


def test_store_v1_modes_match_config():
    assert VS.V1_MODES == VC.V1_MODES                                     # store ला config import करता येत नाही (cycle) ⇒ प्रत
