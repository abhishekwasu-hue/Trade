"""Abhi §10 (Monday PAPER): Telegram approval v2 — ✅ · ✏️ Modify (फक्त entry) · ❌ + कारण · 📝 Correct marking · /exit · 15:45 सारांश.
non-approver ignored; parsing (चुकीचा मजकूर ⇒ स्पष्ट उत्तर, बदल नाही); area बाहेर / R:R < 3 ⇒ इशारा पण ✅ हवंच; limit न गाठता ⇒ EXPIRED,
position नाही, would-have; Telegram वरून इतर कुठलाही parameter बदलत नाही; correction नोंद होते पण engine output बदलत नाही; Modify नंतर
approval window पुन्हा; exits कधीच अडत नाहीत."""
import datetime as dt
import json

import pandas as pd
import pytest

from paper import commands as PCMD
from paper import journal as PJ
from paper import pause as PP
from tests.test_vision_v1 import ME, NOW, db, tick  # noqa: F401 (fixture)
from vision import approval as AP
from vision import config as VC
from vision import decide as VD
from vision import gate as VG
from vision import store as VS
from vision import telegram_bot as TB
from vision import worker as VW

BOT = "dynamic_sr_instant"
GATE = {"gate": {"mode": "confirmation", "side": "BULLISH", "area": [22570.0, 22640.0], "form": "engulf", "grade": "A", "entry": 22630.0,
                 "sl": 22540.0, "target": 22990.0, "rr": 4.0, "tf": 5}}
IMG = "/data/visual_audit/x_sent.png"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setitem(VC.BOT_DEFAULTS, "approval_required", True)              # production default (PAPER_DATA_DIR: conftest)


def gate(spot=22630.0, level=22600.0, tags=GATE, forced=False):
    return VG.entry_gate(BOT, "NIFTY", "PAPER", "BULLISH", level, "SUPPORT", "5M", NOW, spot, 2, 1, tags=dict(tags), forced=forced)


def pending(level=22600.0, tags=GATE):
    """bot signal ⇒ QUEUED ⇒ (worker सारखं) PENDING_HUMAN, deadline +10 मि., chart path."""
    g = gate(level=level, tags=tags)
    assert g.action == "HOLD" and g.signal_id
    VS.transition(g.signal_id, ("QUEUED",), "PENDING_HUMAN", None, deadline=VS._iso(VS.now_ist() + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0, median_range=40.0, tg_message_id=777, image_path=IMG)
    return g.signal_id


def cq(sid, action, uid=ME, chat=ME, mid=777):
    return {"id": "cb", "data": VD.callback_data(sid, action), "from": {"id": uid}, "message": {"chat": {"id": chat}, "message_id": mid}}


def press(db, sid, action, **kw):
    return TB.handle_callback(cq(sid, action, **kw), now=db["clock"][0])


def say(db, text, uid=ME, chat=ME):
    return AP.handle_text({"text": text, "from": {"id": uid}, "chat": {"id": chat}}, TB._authorized)


def frozen(sid):
    r = VS.get_signal(sid)
    return {k: r[k] for k in ("status", "level", "direction", "setup_json", "factor", "mod_entry", "mod_json", "spot", "role", "setup_tf")}


# ------------------------------------------------------------------------------------------------ buttons / parsing
def test_four_buttons_and_new_actions_hmac_protected(db):
    sid = pending()
    b = AP.buttons(sid, AP.base_levels(VS.get_signal(sid)) is not None)
    assert [x[0] for x in b] == ["✅ Approve", "❌ Reject", "✏️ Modify", "📝 Correct marking"]
    assert [VD.parse_callback(x[1])[1] for x in b] == ["A", "R", "M", "C"]
    assert VD.parse_callback(f"v1|{sid}|S|{VD.sign(sid, 'S')}") is None                  # अज्ञात action (उदा. SL) ⇒ नकार
    assert VD.parse_callback(f"v1|{sid}|M|{'0' * 16}") is None                            # खोटा HMAC
    assert json.loads(__import__("vision.tg", fromlist=["x"]).keyboard(b))["inline_keyboard"][1][0]["text"] == "✏️ Modify"
    assert AP.base_levels({"setup_json": json.dumps({"tags": {}})}) is None                # engine SL / T नाहीत ⇒ ✏️ बटण नाही


def test_parse_entry_and_correction_inputs():
    assert AP.parse_entry("entry 22590") == (22590.0, None)
    assert AP.parse_entry("Entry: 22,590.5") == (22590.5, None)
    for bad in ("entry", "entry abc", "22590", "entry -5", "entry 0", ""):
        v, err = AP.parse_entry(bad)
        assert v is None and err.startswith("❌")
    for other in ("sl 22500", "target 23000", "T 23000", "lots 5", "strike 22500", "hedge 200", "expiry next", "risk 5000",
                  "entry 22590 sl 22500", "entry 22590 target 23000"):
        v, err = AP.parse_entry(other)
        assert v is None and err == AP.ONLY_ENTRY
    assert AP.parse_correction("zone 22570-22640")[0] == {"type": "zone", "lo": 22570.0, "hi": 22640.0}
    assert AP.parse_correction("zone 22640 to 22570")[0] == {"type": "zone", "lo": 22570.0, "hi": 22640.0}
    assert AP.parse_correction("trend down")[0] == {"type": "trend", "value": "down"}
    assert AP.parse_correction("this is a correction, not impulse")[0] == {"type": "wave", "value": "correction"}
    assert AP.parse_correction("impulse, not a correction")[0] == {"type": "wave", "value": "impulse"}
    assert AP.parse_correction("commitment candle 10:45")[0] == {"type": "commitment", "time": "10:45"}
    assert AP.parse_correction("level खूप जुना होता")[0] == {"type": "free"}
    for bad in ("zone 22640", "zone abc-def", "zone 22600-22600", "trend maybe", "commitment candle 25:10", "commitment soon", "  "):
        p, err = AP.parse_correction(bad)
        assert p is None and err.startswith("❌")


# ------------------------------------------------------------------------------------------------ non-approver
def test_non_approver_ignored_everywhere(db):
    sid = pending()
    before = frozen(sid)
    for a in ("A", "R", "M", "C", "RT"):
        assert press(db, sid, a, uid=999) == (False, "unauthorized")
        assert press(db, sid, a, chat=-100) == (False, "unauthorized")
    assert AP.state_get("999") is None
    assert press(db, sid, "M")[0]                                                         # approver चा state आहे …
    assert say(db, "entry 22590", uid=999) == (False, "unauthorized")                    # … पण दुसऱ्याचा मजकूर ⇒ दुर्लक्ष
    assert TB.handle_command("/exit 123456", {"id": 999}, {"id": 999}, send=db["texts"].append) == (False, "unauthorized")
    assert TB.handle_command("/correct", {"id": 999}, {"id": 999}, send=db["texts"].append) == (False, "unauthorized")
    assert frozen(sid) == before and VS.corrections() == []


# ------------------------------------------------------------------------------------------------ ✏️ Modify
def test_modify_bad_input_clear_error_no_change_then_ticket(db):
    sid = pending()
    before = frozen(sid)
    ok, why = press(db, sid, "M")
    assert ok and why == "modify_prompt" and "entry 22590" in db["texts"][-1] and "SL 22540" in db["texts"][-1]
    assert VS.get_signal(sid)["status"] == "PENDING_HUMAN"                                # ✏️ दाबल्याने निर्णय नाही
    for bad in ("entry abc", "sl 22500", "entry 22530", "entry 23000", "lots 3"):        # 22530 < SL · 23000 > target
        ok, why = say(db, bad)
        assert (ok, why) == (False, "bad_input") and db["texts"][-1].startswith("❌")
        assert frozen(sid) == before                                                       # काहीच बदल नाही
    n = len(db["photos"])
    ok, why = say(db, "entry 22590")
    assert (ok, why) == (True, "modified")
    r = VS.get_signal(sid)
    t = json.loads(r["mod_json"])
    assert r["status"] == "PENDING_HUMAN" and r["mod_entry"] == 22590.0                   # पुन्हा ✅ हवं
    assert (t["sl"], t["target"], t["rr"], t["warnings"]) == (22540.0, 22990.0, 8.0, [])  # SL / target engine चेच; R:R = 400 / 50
    assert json.loads(r["setup_json"]) == json.loads(before["setup_json"]) and r["level"] == before["level"]
    cap, btn = db["photos"][-1]
    assert len(db["photos"]) == n + 1 and "सुधारित ticket" in cap and "22590" in cap and "R:R <b>8</b>" in cap   # echo आधी
    assert VD.parse_callback(btn[0][1]) == (sid, "A") and r["tg_message_id"] == 777
    assert any("ही बटणं बंद" in e[1] for e in db["edits"])                              # जुन्या chart वरची बटणं काढली
    assert AP.state_get(str(ME)) is None
    assert gate(spot=22580.0).action == "HOLD"                                             # ✅ नाही ⇒ entry नाही


def test_modify_outside_area_or_low_rr_warns_but_still_needs_approve(db):
    sid = pending()
    press(db, sid, "M")
    assert say(db, "entry 22660")[0]                                                      # area 22570–22640 बाहेर, R:R 330/120 = 2.75
    cap = db["photos"][-1][0]
    assert "area 22,570–22,640 बाहेर" in cap and "R:R 2.75 &lt; 3" in cap
    r = VS.get_signal(sid)
    assert r["status"] == "PENDING_HUMAN" and r["mod_entry"] == 22660.0
    assert gate(spot=22650.0).action == "HOLD"                                             # इशारा ⇒ आपोआप entry नाही
    assert press(db, sid, "A")[0]
    g = gate(spot=22655.0)
    assert g.action == "ENTER" and g.lots == 2                                             # ✅ नंतरच, spot ≤ 22660


def test_approval_window_resets_after_modify(db):
    sid = pending()                                                                        # deadline 10:52:20
    tick(db, 8)
    press(db, sid, "M")
    assert say(db, "entry 22590")[0]
    assert pd.Timestamp(VS.get_signal(sid)["deadline"]) == pd.Timestamp(NOW) + pd.Timedelta(minutes=18)
    tick(db, 5)                                                                            # मूळ deadline गेली
    assert VW.v1_housekeeping(now=db["clock"][0]) == [] and VS.get_signal(sid)["status"] == "PENDING_HUMAN"
    ok, text = press(db, sid, "A")
    assert ok and "limit entry 22590" in text and VS.get_signal(sid)["status"] == "APPROVED"


def test_limit_entry_waits_for_spot_then_enters_once(db):
    sid = pending()
    press(db, sid, "M")
    say(db, "entry 22590")
    press(db, sid, "A")
    g = gate(spot=22630.0)
    assert (g.action, g.status, g.final) == ("HOLD", "SKIPPED_VISION_LIMIT_WAIT", False)
    assert VS.get_signal(sid)["status"] == "APPROVED"
    assert VG.forced_levels(BOT, "NIFTY") == [(22600.0, "5M", "SUPPORT")]                 # bot पुढच्या cycle ला पुन्हा तपासतो
    g = gate(spot=22588.0, forced=True)
    assert g.action == "ENTER" and VS.get_signal(sid)["status"] == "EXECUTED"
    assert gate(spot=22588.0).action == "HOLD"                                             # एकदाच


def test_limit_not_reached_in_window_expires_no_position_would_have(db):
    sid = pending()
    press(db, sid, "M")
    say(db, "entry 22590")
    press(db, sid, "A")
    assert gate(spot=22620.0).action == "HOLD"
    tick(db, 6)                                                                            # exec_window_min 5
    g = gate(spot=22620.0)
    r = VS.get_signal(sid)
    assert g.action != "ENTER" and r["status"] == "EXPIRED" and "गाठला नाही" in r["exec_note"]
    wh = [w for w in PJ.would_have_rows() if w["signal_id"] == sid]
    assert len(wh) == 1 and wh[0]["status"] == "EXPIRED_LIMIT" and wh[0]["lots"] == 0
    # worker housekeeping मार्ग (bot पोहोचलाच नाही)
    sid2 = pending(level=22750.0, tags={"gate": {**GATE["gate"], "area": [22680.0, 22720.0], "sl": 22650.0, "target": 23100.0}})
    press(db, sid2, "M")
    say(db, "entry 22690")
    press(db, sid2, "A")
    tick(db, 6)
    assert (sid2, "EXPIRED") in VW.v1_housekeeping(now=db["clock"][0])
    assert [w["status"] for w in PJ.would_have_rows() if w["signal_id"] == sid2] == ["EXPIRED_LIMIT"]
    assert VS.get_signal(sid2)["status"] == "EXPIRED"


def test_no_other_parameter_can_be_changed_from_telegram(db):
    sid = pending()
    s0 = VC.load(BOT)
    before = frozen(sid)
    press(db, sid, "M")
    for text in ("sl 22500", "target 23500", "lots 4", "strike 22500", "hedge 300", "expiry monthly", "risk 9000", "entry 22590 lots 4"):
        assert say(db, text) == (False, "bad_input")
        assert db["texts"][-1] == AP.ONLY_ENTRY
    assert frozen(sid) == before and VC.load(BOT) == s0
    say(db, "entry 22600")
    t = json.loads(VS.get_signal(sid)["mod_json"])
    assert (t["sl"], t["target"]) == (GATE["gate"]["sl"], GATE["gate"]["target"])          # entry शिवाय काहीच नाही
    assert VC.load(BOT) == s0
    for cmd in ("/sl 22500", "/target 23000", "/lots 4"):                                  # अशा commands नाहीत
        assert TB.handle_command(cmd, {"id": ME}, {"id": ME}, send=db["texts"].append) == (False, "unknown")


def test_modify_not_after_decision_and_state_expiry(db):
    sid = pending()
    press(db, sid, "M")
    tick(db, AP.STATE_TTL_MIN + 1)
    assert say(db, "entry 22590") == (True, "state_expired") and VS.get_signal(sid)["mod_entry"] is None
    sid2 = pending(level=22700.0)
    press(db, sid2, "M")
    press(db, sid2, "R")                                                                   # मधेच ❌
    assert say(db, "entry 22590") == (False, "not_pending") and VS.get_signal(sid2)["mod_entry"] is None
    assert press(db, sid2, "M") == (False, "already")
    press(db, sid2, "C")
    assert say(db, "cancel") == (True, "cancelled") and VS.corrections() == []


# ------------------------------------------------------------------------------------------------ ❌ कारण
def test_reject_then_one_tap_reason_and_other_free_text(db):
    sid = pending()
    ok, _ = press(db, sid, "R")
    r = VS.get_signal(sid)
    assert ok and r["status"] == "REJECTED" and r["factor"] == 0.0                        # निर्णय लगेच (जुनं वर्तन)
    cap, btn = db["photos"][-1]
    assert "कारण" in cap and [b[0] for b in btn] == list(VD.REJECT_REASONS.values())
    assert press(db, sid, "RZ", mid=888) == (True, "wrong zone")
    r = VS.get_signal(sid)
    assert r["reject_reason"] == "wrong zone" and "wrong zone" in r["decision_reason"] and r["image_path"] == IMG
    assert any(e[0] == 888 and "wrong zone" in e[1] for e in db["edits"])
    g = gate()
    assert g.action == "HOLD" and g.final                                                  # position नाही, would-have
    assert [w["signal_id"] for w in PJ.would_have_rows()] == [sid]
    sid2 = pending(level=22700.0)
    press(db, sid2, "R")
    assert press(db, sid2, "RO") == (True, "reason_prompt")
    assert say(db, "news event day") == (True, "reason")
    assert VS.get_signal(sid2)["reject_reason"] == "other: news event day"
    sid3 = pending(level=22800.0)
    assert press(db, sid3, "RT") == (False, "not_rejected") and VS.get_signal(sid3)["status"] == "PENDING_HUMAN"


# ------------------------------------------------------------------------------------------------ 📝 Correct marking
def test_correction_stored_and_never_changes_engine_output(db):
    sid = pending()
    before = frozen(sid)
    s0 = VC.load(BOT)
    ok, why = press(db, sid, "C")
    assert ok and why == "correction_prompt" and VS.get_signal(sid)["status"] == "PENDING_HUMAN"
    assert say(db, "zone 22640") == (False, "bad_input") and VS.corrections() == []        # चुकीचा ⇒ नोंद नाही
    ok, cid = say(db, "zone 22570-22640")
    assert ok
    rows = VS.corrections(NOW.strftime("%Y-%m-%d"), unreviewed=True)
    assert len(rows) == 1
    c = rows[0]
    assert (c["id"], c["signal_id"], c["symbol"], c["tf"], c["image_path"], c["ctype"]) == (cid, sid, "NIFTY", "5M", IMG, "zone")
    assert c["engine_reading"] == before["setup_json"] and json.loads(c["parsed_json"]) == {"type": "zone", "lo": 22570.0, "hi": 22640.0}
    assert c["raw_text"] == "zone 22570-22640" and c["by_"] == f"telegram:{ME}" and c["ts"].startswith("2026-10-06")
    assert "📝 नोंदलं (zone 22570–22640)" in db["texts"][-1]
    assert frozen(sid) == before and VC.load(BOT) == s0                                    # signal / settings ला हात नाही
    # ✅ नंतरही 📝 (/correct) — आणि gate चा निर्णय correction नसलेल्या जुळ्या signal सारखाच
    press(db, sid, "A")
    TB.handle_command(f"/correct {sid}", {"id": ME}, {"id": ME}, send=db["texts"].append)
    assert say(db, "trend down")[0] and len(VS.corrections()) == 2
    twin = pending(level=22900.0, tags={"gate": {**GATE["gate"]}})
    press(db, twin, "A")
    g1, g2 = gate(spot=22630.0), gate(spot=22630.0, level=22900.0)
    assert (g1.action, g1.lots, g1.naked_lots, g1.factor) == (g2.action, g2.lots, g2.naked_lots, g2.factor) == ("ENTER", 2, 1, 1.0)
    assert VS.mark_correction_reviewed(cid) and len(VS.corrections(unreviewed=True)) == 1


def test_engine_evaluate_unchanged_by_corrections(db):
    LR = pytest.importorskip("bots_common.level_reaction")
    ts = [pd.Timestamp("2001-01-01 09:15") + pd.Timedelta(minutes=5 * i) for i in range(9)]
    bars = pd.DataFrame([(1030, 1031, 1024, 1025), (1025, 1027, 1018, 1019), (1019, 1021, 1012, 1013), (1013, 1015, 1006, 1007),
                         (1007, 1009, 1001, 1002), (1002, 1003, 995, 999), (999, 1000, 987, 997), (996, 1009, 995, 1008),
                         (1008, 1012, 1004, 1010)], columns=["open", "high", "low", "close"])
    bars.insert(0, "timestamp", ts)
    ctx = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP"}

    def run():
        return LR.safe_evaluate(bars.copy(), (990.0, 1000.0), ctx, [(1090.0, 1100.0)], 0)
    r0 = run()
    sid = pending()
    press(db, sid, "C")
    say(db, "zone 985-1001")
    press(db, sid, "C")
    say(db, "this is a correction, not impulse")
    assert len(VS.corrections()) == 2
    assert repr(run()) == repr(r0)                                                         # live self-tuning नाही


# ------------------------------------------------------------------------------------------------ /exit
def _trade(mode="PAPER", tid="PAPER_1760000000_ab12cd"):
    return {"trade_id": tid, "mode": mode, "symbol": "NIFTY", "strategy": "BULL_PUT_SPREAD", "source": "dynamic_sr_instant", "status": "OPEN"}


def test_exit_paper_only_and_never_blocked_by_pause(db, monkeypatch):
    closed = []

    def close(tok, tid, sym, pt, exit_reason=None, exit_reason_detail=None):
        closed.append((tid, exit_reason, pt))
        return True, "ok"
    PP.set_pause(True, "t", "test pause")                                                  # PAPER pause चालू
    import cloud_db
    monkeypatch.setattr(cloud_db, "get_trading_pause_settings", lambda: {"paused": True, "reason": "dashboard"}, raising=False)
    import trading_engine
    monkeypatch.setattr(trading_engine, "check_kill_switch", lambda *a, **k: (False, "kill"), raising=False)
    sent = []
    deps = dict(trades_fn=lambda: [_trade(), _trade("LIVE", "NIFTY_1760000000_ffee99")], token_fn=lambda: "tok-not-real", close_fn=close)
    assert PCMD.handle("/exit", "telegram:1", sent.append, arg="ab12cd", **deps) == (True, "exit")
    assert closed == [("PAPER_1760000000_ab12cd", "TELEGRAM_EXIT", "D")] and "बंद केला" in sent[-1]
    ok, why = PCMD.handle("/exit", "telegram:1", sent.append, arg="NIFTY_1760000000_ffee99", **deps)
    assert not ok and "फक्त PAPER" in sent[-1] and len(closed) == 1                       # LIVE ला हात नाही
    assert not PCMD.handle("/exit", "telegram:1", sent.append, arg="zzzzzz", **deps)[0] and "सापडला नाही" in sent[-1]
    assert not PCMD.handle("/exit", "telegram:1", sent.append, arg="", **deps)[0] and "वापर" in sent[-1]
    assert "/exit" in PCMD.positions_text(lambda: [_trade()]) and "#ab12cd" in PCMD.positions_text(lambda: [_trade()])


# ------------------------------------------------------------------------------------------------ 15:45 सारांश
def test_daily_summary_counts(db, capsys):
    a = pending()
    press(db, a, "M")
    say(db, "entry 22590")
    press(db, a, "A")
    b = pending(level=22700.0)
    press(db, b, "R")
    press(db, b, "RT")
    c = pending(level=22800.0)
    press(db, c, "R")
    press(db, c, "C")
    say(db, "trend down")
    PJ.would_have({"ts": "2026-10-06T10:50:00", "bot": BOT, "symbol": "NIFTY", "signal_id": c, "status": "X"})
    PJ.upsert({"trade_id": "T1", "bot": BOT, "entry_time": "2026-10-06 10:50:00", "exit_time": "2026-10-06 11:30:00", "net_pnl": 1234.5})
    PJ.upsert({"trade_id": "T2", "bot": BOT, "entry_time": "2026-10-06 11:00:00"})
    d = AP.daily_summary("2026-10-06")
    assert (d["approvals"], d["modifications"], d["modified_approved"], d["corrections"]) == (1, 1, 1, 1)
    assert d["rejections"] == {"wrong trend": 1, "कारण नाही": 1}
    assert (d["trades_closed"], d["trades_open"], d["pnl"], d["would_have"]) == (1, 1, 1234.5, 1)
    from scripts import paper_daily_summary as S
    sent = []
    assert S.main(["--day", "2026-10-06"], send=sent.append) == 0
    assert "approvals 1" in sent[0] and "wrong trend 1" in sent[0] and "₹1,234" in sent[0] and "would-have नोंदी 1" in sent[0]


def test_poll_routes_state_text_before_review_replies(db, monkeypatch):
    sid = pending()
    press(db, sid, "M")
    import backtest_review.telegram as RT
    seen = []
    monkeypatch.setattr(RT, "handle_reply", lambda m, auth, send=None: seen.append(m["text"]) or (True, "saved"))
    upd = [{"update_id": 1, "message": {"text": "entry 22590", "from": {"id": ME}, "chat": {"id": ME}, "reply_to_message": {"message_id": 5}}},
           {"update_id": 2, "message": {"text": "✔", "from": {"id": ME}, "chat": {"id": ME}, "reply_to_message": {"message_id": 6}}}]
    monkeypatch.setattr(TB.TG, "get_updates", lambda off, timeout: upd)
    monkeypatch.setattr(TB, "_manual_sweep", lambda *a, **k: [])
    assert TB.poll_once(0, timeout=0) == 3
    assert VS.get_signal(sid)["mod_entry"] == 22590.0 and seen == ["✔"]                   # state नंतर साधा reply ⇒ review (जुना मार्ग)


def test_manual_signal_modify_uses_paper_sl_t_and_waits_for_limit(db, monkeypatch):
    """✋ /paper: engine gate tags नाहीत ⇒ तुमचे SL / T; ✅ नंतर spot limit ला येईपर्यंत order नाही."""
    import trading_engine
    from paper import manual as PM
    from tests.test_paper_manual import chain, deps
    spot = [25010.0]
    opened = []
    monkeypatch.setattr(PM, "default_chain", lambda t, s: (chain(spot[0]), "ok", 0))
    monkeypatch.setattr(PM, "_token", lambda: "tok-not-real")
    monkeypatch.setattr(PM, "_market_open", lambda: True)
    monkeypatch.setattr(trading_engine, "open_multi_leg_trade", lambda *a, **k: opened.append((a, k)) or (True, {"trade_id": "T1"}))
    d, _ = deps()
    assert PM.handle("/paper NIFTY bullput 25100/24950 SL 24900 T 25400", "telegram:1", **d)[0]
    m = PM.rows("QUEUED")[0]
    sid = m["vision_signal_id"]
    VS.transition(sid, ("QUEUED",), "PENDING_HUMAN", None, deadline=VS._iso(NOW + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0, median_range=40.0)
    assert press(db, sid, "M")[0] and say(db, "entry 24990")[0]
    t = json.loads(VS.get_signal(sid)["mod_json"])
    assert (t["sl"], t["target"], t["rr"], t["src"]) == (24900.0, 25400.0, 4.56, "manual")
    assert press(db, sid, "A")[0]                                                          # ✅ ⇒ sweep, पण spot 25010 > 24990
    assert not opened and VS.get_signal(sid)["status"] == "APPROVED" and PM.get(m["id"])["status"] == "QUEUED"
    spot[0] = 24985.0
    PM.execute_ready()
    assert len(opened) == 1 and VS.get_signal(sid)["status"] == "EXECUTED" and PM.get(m["id"])["status"] == "EXECUTED"
