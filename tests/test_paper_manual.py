"""✋ Manual trigger (Abhi, Monday PAPER P0): /paper दोन्ही प्रकार, चुकीचे strikes / बाजू, बाजार बंद, token नाही, approver नसलेला user,
kill-switch / pause, Vision ⇒ ✅ ⇒ एकदाच PAPER entry, ❌ / timeout ⇒ entry नाही, spot SL / T exit, caption (Vision: NA), bots पासून वेगळा."""
import datetime as dt

import pytest

import trading_engine
from paper import manual as PM
from paper import watch as PW
from tests.test_vision_v1 import ME, NOW, db, tick  # noqa: F401 (fixture)
from vision import config as VC
from vision import decide as VD
from vision import gate as VG
from vision import store as VS
from vision import telegram_bot as TB
from vision import worker as VW

SPOT = 25010.0
ST = {"lots": 2, "itm_depth_points": 100, "hedge_width_points": 150}


@pytest.fixture(autouse=True)
def _approval_on(monkeypatch):
    monkeypatch.setitem(VC.BOT_DEFAULTS, "approval_required", True)              # production default (conftest tests मध्ये बंद)


def chain(spot=SPOT, expiry="2026-10-13"):
    out = []
    for k in range(24700, 25451, 50):
        out.append({"underlying_spot_price": spot, "strike_price": float(k), "expiry": expiry,
                    "put_options": {"instrument_key": f"PE{k}", "market_data": {"ltp": max(0.0, k - spot) + max(5.0, 100 - 0.3 * abs(k - spot))}, "option_greeks": {}},
                    "call_options": {"instrument_key": f"CE{k}", "market_data": {"ltp": max(0.0, spot - k) + max(5.0, 100 - 0.3 * abs(k - spot))}, "option_greeks": {}}})
    return out


def deps(**kw):
    sent = []
    d = dict(send=sent.append, token_fn=lambda: "tok-not-real", market_fn=lambda: True, chain_fn=lambda t, s: (chain(), "ok", 0),
             paused_fn=lambda: (False, None), kill_fn=lambda: (True, ""), has_open=lambda s, src: False,
             settings_fn=lambda p, s: dict(ST), lot_fn=lambda: (65, "test"), now=NOW)
    d.update(kw)
    return d, sent


# ------------------------------------------------------------------------------------------------ parse / help
def test_parse_both_forms_and_errors():
    p, e = PM.parse("/paper NIFTY bullput SL 24900 T 25400")
    assert e is None and p == {"symbol": "NIFTY", "kind": "bullput", "short": None, "hedge": None, "sl": 24900.0, "target": 25400.0}
    p, e = PM.parse("/paper nifty bearcall 25100/25200 SL 25250")
    assert e is None and (p["short"], p["hedge"], p["sl"], p["target"]) == (25100.0, 25200.0, 25250.0, None)
    for bad in ("/paper NIFTY ironfly SL 1", "/paper NIFTY bullput 24900", "/paper NIFTY bullput SL x", "/paper NIFTY bullput SL 1 Q 2"):
        assert PM.parse(bad)[0] is None


def test_help_has_both_examples(db):
    TB.handle_command("/help", {"id": ME}, {"id": ME})
    h = db["texts"][-1]
    assert "/paper NIFTY bullput SL" in h and "/paper NIFTY bearcall 25100/25200 SL" in h


# ------------------------------------------------------------------------------------------------ validation
def test_profile_form_queues_vision_signal_no_order(db):
    gates = []
    real = VG.entry_gate
    d, sent = deps(gate_fn=lambda *a, **k: gates.append((a, k)) or real(*a, **k))
    ok, msg = PM.handle("/paper NIFTY bullput SL 24900 T 25400", "telegram:1", **d)
    assert ok, msg
    m = PM.rows("QUEUED")[0]
    assert (m["short_strike"], m["hedge_strike"]) == (25100.0, 24950.0)          # SR V3 profile: ATM 25000 + ITM 100, hedge 150
    assert m["profile"] == "srv3_instant" and m["lots"] == 2 and m["lot_size"] == 65 and m["rr"] == pytest.approx(3.55, abs=0.01)
    v = VS.get_signal(m["vision_signal_id"])
    assert v["bot"] == "manual" and v["status"] == "QUEUED" and v["mode"] == "human_confirm"
    assert gates[0][0][0] == "manual" and gates[0][1]["tags"]["manual"]
    assert "R:R 3.55" in sent[-1]


def test_own_strikes_form(db):
    d, sent = deps()
    ok, msg = PM.handle("/paper NIFTY bearcall 25100/25200 SL 25150 T 24700", "telegram:1", **d)
    assert ok, msg
    m = PM.rows("QUEUED")[0]
    assert (m["short_strike"], m["hedge_strike"], m["strikes_from"]) == (25100.0, 25200.0, "तुमचे strikes")
    assert m["direction"] == "BEARISH"


@pytest.mark.parametrize("cmd,needle", [
    ("/paper NIFTY bullput 24800/24900 SL 24700", "short (24800) > hedge (24900)"),        # चुकीची बाजू
    ("/paper NIFTY bullput 25100/24950 SL 25050", "SL (25050) spot"),                     # SL spot च्या वर
    ("/paper NIFTY bullput 25100/24950 SL 24900 T 24950", "T (24950) spot"),              # T चुकीच्या बाजूला
    ("/paper NIFTY bearcall 25125/25200 SL 25150", "chain मध्ये नाही"),                    # strike chain मध्ये नाही
    ("/paper NIFTY bearcall 25100/25200 SL 24900", "SL (24900) spot"),
    ("/paper BANKNIFTY bullput SL 50000", "enabled: false"),                              # Monday NIFTY only
])
def test_wrong_strikes_or_side_rejected(db, cmd, needle):
    d, sent = deps(gate_fn=lambda *a, **k: pytest.fail("gate नको"))
    ok, msg = PM.handle(cmd, "telegram:1", **d)
    assert not ok and needle in msg, msg
    assert not PM.rows("QUEUED")


def test_market_closed_token_missing_pause_kill(db):
    no_gate = lambda *a, **k: pytest.fail("gate नको")  # noqa: E731
    for kw, needle in ((dict(market_fn=lambda: False), "बाजार बंद"), (dict(token_fn=lambda: None), "Upstox token नाही"),
                       (dict(kill_fn=lambda: (False, "KILL_SWITCH daily loss")), "Kill-switch"),
                       (dict(paused_fn=lambda: (True, "Abhi")), "pause"), (dict(has_open=lambda s, src: True), "आधीच उघडी")):
        d, _ = deps(gate_fn=no_gate, **kw)
        ok, msg = PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
        assert not ok and needle in msg, (kw, msg)


def test_rr_below_3_warns_but_allowed(db):
    d, sent = deps()
    ok, msg = PM.handle("/paper NIFTY bullput SL 24900 T 25100", "telegram:1", **d)
    assert ok and "R:R 0.82" in msg and "&lt; 3" in msg


def test_approval_off_means_no_manual_entry(db):
    VC.save("manual", {"approval_required": False}, "t")
    d, _ = deps()
    ok, msg = PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
    assert not ok and "approval मार्ग उपलब्ध नाही" in msg


def test_non_approver_cannot_trigger(db, monkeypatch):
    monkeypatch.setattr(PM, "handle", lambda *a, **k: pytest.fail("approver नसलेल्याची आज्ञा चालू नये"))
    assert TB.handle_command("/paper NIFTY bullput SL 24900", {"id": 42}, {"id": 42}) == (False, "unauthorized")


def test_one_pending_manual_at_a_time(db):
    d, _ = deps()
    assert PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)[0]
    ok, msg = PM.handle("/paper NIFTY bullput SL 24850", "telegram:1", **d)
    assert not ok and "वाटेत" in msg


# ------------------------------------------------------------------------------------------------ approval ⇒ entry
def _pending(sid):
    VS.transition(sid, ("QUEUED",), "PENDING_HUMAN", None, deadline=str(NOW + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0)


@pytest.fixture
def exec_env(monkeypatch):
    opened = []
    monkeypatch.setattr(PM, "default_chain", lambda t, s: (chain(), "ok", 0))
    monkeypatch.setattr(PM, "_token", lambda: "tok-not-real")
    monkeypatch.setattr(PM, "_market_open", lambda: True)
    monkeypatch.setattr(trading_engine, "open_multi_leg_trade",
                        lambda *a, **k: opened.append((a, k)) or (True, {"trade_id": f"T{len(opened)}"}))
    return opened


def test_approve_enters_once_via_callback_and_sweep(db, exec_env):
    d, _ = deps()
    assert PM.handle("/paper NIFTY bullput SL 24900 T 25400", "telegram:1", **d)[0]
    m = PM.rows("QUEUED")[0]
    sid = m["vision_signal_id"]
    assert PM.execute_ready() and not exec_env                                  # ✅ नाही ⇒ entry नाही
    _pending(sid)
    assert not exec_env
    cq = {"id": "c1", "from": {"id": ME}, "message": {"chat": {"id": ME}, "message_id": 777}, "data": VD.callback_data(sid, "A")}
    ok, _ = TB.handle_callback(cq, now=NOW)
    assert ok and len(exec_env) == 1
    a, k = exec_env[0]
    assert k["trading_mode"] == "PAPER" and k["source"] == "manual_paper" and k["lots"] == 2 and k["lot_size"] == 65
    assert (a[2]["short_leg"]["strike"], a[2]["long_leg"]["strike"]) == (25100.0, 24950.0)
    assert PM.get(m["id"])["status"] == "EXECUTED" and PM.get(m["id"])["trade_id"] == "T1"
    TB.handle_callback(cq, now=NOW)                                              # double-click
    PM.execute_ready()                                                           # sweep
    assert len(exec_env) == 1                                                    # एकच order
    assert VS.get_signal(sid)["status"] == "EXECUTED"


def test_reject_and_timeout_never_enter(db, exec_env):
    d, _ = deps()
    PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
    m = PM.rows("QUEUED")[0]
    _pending(m["vision_signal_id"])
    cq = {"id": "c1", "from": {"id": ME}, "message": {"chat": {"id": ME}, "message_id": 777},
          "data": VD.callback_data(m["vision_signal_id"], "R")}
    assert TB.handle_callback(cq, now=NOW)[0]
    assert not exec_env and PM.get(m["id"])["status"] == "REJECTED"
    d, _ = deps(chain_fn=lambda t, s: (chain(), "ok", 0))
    assert PM.handle("/paper NIFTY bullput SL 24800", "telegram:1", **d)[0]
    m2 = PM.rows("QUEUED")[0]
    _pending(m2["vision_signal_id"])
    tick(db, 11)
    PM.execute_ready()
    assert not exec_env and PM.get(m2["id"])["status"] in ("REJECTED", "EXPIRED")


def test_kill_switch_at_execution_blocks(db, monkeypatch, exec_env):
    monkeypatch.setattr(trading_engine, "open_multi_leg_trade", lambda *a, **k: (False, {"status": "error", "reason": "KILL_SWITCH"}))
    d, _ = deps()
    PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
    m = PM.rows("QUEUED")[0]
    _pending(m["vision_signal_id"])
    VS.transition(m["vision_signal_id"], "PENDING_HUMAN", "APPROVED", None, decided_at=str(NOW), decided_by="telegram:1")
    sent = []
    PM.execute_ready(send=sent.append)
    assert PM.get(m["id"])["status"] == "FAILED" and "KILL_SWITCH" in sent[-1]


def test_manual_signal_not_in_bot_forced_levels(db):
    d, _ = deps()
    PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
    _pending(PM.rows("QUEUED")[0]["vision_signal_id"])
    tick(db, 11)
    for bot in ("dynamic_sr_instant", "srv3_instant", "srv2_momentum_reversal"):
        assert VG.forced_levels(bot, "NIFTY") == []                             # bots manual signal वर entry घेत नाहीत


# ------------------------------------------------------------------------------------------------ caption / exit / journal
def test_caption_shows_manual_and_vision_na(db):
    d, _ = deps()
    PM.handle("/paper NIFTY bullput SL 24900 T 25100", "telegram:1", **d)
    row = VS.get_signal(PM.rows("QUEUED")[0]["vision_signal_id"])
    dec = VD.decide("human_confirm", "unavailable", VC.load("manual"))
    cap = VW.v1_caption(row, {"verdict": "unavailable", "error": "ANTHROPIC_API_KEY नाही"}, dec, str(NOW), buttons=True)
    assert "✋ MANUAL" in cap and "Vision: NA" in cap and "R:R 0.82" in cap
    assert dec.ask_human                                                         # Vision NA तरी ✅ / ❌ बटणं


def test_spot_sl_and_target_exit():
    PM._put({"id": "m1", "created_at": str(NOW), "symbol": "NIFTY", "kind": "bullput", "sl": 24900.0, "target": 25400.0, "spot": SPOT,
             "status": "EXECUTED", "trade_id": "T9", "rr": 3.55, "profile": "srv3_instant"})
    closed = []
    close = lambda tok, tid, sym, pt, exit_reason, exit_reason_detail: closed.append(exit_reason) or (True, {})  # noqa: E731
    t = {"trade_id": "T9", "symbol": "NIFTY"}
    assert PM.spot_exit(t, "tok", spot_fn=lambda a, s: 25000.0, close_fn=close) is None
    assert PM.spot_exit(t, "tok", spot_fn=lambda a, s: 24899.0, close_fn=close) == "MANUAL_SPOT_SL"
    assert PM.spot_exit(t, "tok", spot_fn=lambda a, s: 25401.0, close_fn=close) == "MANUAL_SPOT_TARGET"
    assert closed == ["MANUAL_SPOT_SL", "MANUAL_SPOT_TARGET"]
    assert PM.spot_exit(t, "tok", spot_fn=lambda a, s: (_ for _ in ()).throw(RuntimeError("x")), close_fn=close) is None   # कधीच raise नाही
    assert PW.BOT_OF_SOURCE["manual_paper"] == "manual" and PW.BOT_OF_SOURCE["manual_paper_dryrun_shadow"] == "manual"


def test_manual_is_paper_only():
    assert VC.bot_trading_mode("manual") == "PAPER"
    assert "manual" in VC.BOTS and VC.load("_global")["manual_profile"] == "srv3_instant"
    with pytest.raises(ValueError):
        VC.save("_global", {"manual_profile": "mcx_futures"}, "t")
    src = open(PM.__file__, encoding="utf-8").read()
    assert 'trading_mode="LIVE"' not in src and "LIVE_PAPER" not in src


def test_dry_run_replays_manual_trigger(db, exec_env, monkeypatch, tmp_path):
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("paper_dry_run", os.path.join(os.path.dirname(PM.__file__), "..", "scripts", "paper_dry_run.py"))
    DR = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(DR)
    monkeypatch.setattr(PM, "_paused", lambda: (False, None))
    monkeypatch.setattr(PM, "_kill", lambda: (True, ""))
    monkeypatch.setattr(PM, "_has_open", lambda s, src: False)
    monkeypatch.setattr(PM, "_settings", lambda p, s: dict(ST))
    monkeypatch.setattr(PM.PL, "lot_size", lambda *a, **k: (65, "test"))
    monkeypatch.setattr(PW, "run_cycle", lambda *a, **k: {"entries": 0, "exits": 0, "updates": 0})
    sent, closed, lines = [], [], []

    def approve(_):                                                              # "Abhi" ✅ दाबतो (worker + बटणाऐवजी थेट)
        for m in PM.rows("QUEUED"):
            v = VS.get_signal(m["vision_signal_id"])
            if v["status"] == "QUEUED":
                _pending(v["signal_id"])
                VS.transition(v["signal_id"], "PENDING_HUMAN", "APPROVED", None, decided_at=str(NOW), decided_by="telegram:1")
    ok = DR.run_manual("tok-not-real", "NIFTY", 0.05, 0, lines, str(tmp_path / "log.txt"), send=sent.append,
                       close_fn=lambda *a, **k: closed.append(k["exit_reason"]) or (True, {}), sleep=approve,
                       chain_fn=lambda t, s: (chain(), "ok", 0))
    assert ok and closed == ["DRY_RUN_EXIT"] and len(exec_env) == 1
    assert exec_env[0][1]["source"] == "manual_paper_dryrun_shadow" and exec_env[0][1]["trading_mode"] == "PAPER"
    assert any("[DRY-RUN]" in x for x in sent)
    assert VS.get_signal(PM.rows("EXECUTED")[0]["vision_signal_id"])["setup_json"].count("dry_run")


# ------------------------------------------------------------------------------------------------ review fixes
def test_spot_exit_default_spot_fn_uses_real_upstox_names(monkeypatch):
    import upstox_api
    PM._put({"id": "m2", "created_at": str(NOW), "symbol": "NIFTY", "kind": "bearcall", "sl": 25200.0, "target": None, "spot": SPOT,
             "status": "EXECUTED", "trade_id": "T7"})
    keys = []
    monkeypatch.setattr(upstox_api, "fetch_ltp_map", lambda tok, ks: keys.extend(ks) or {ks[0]: 25250.0})
    closed = []
    out = PM.spot_exit({"trade_id": "T7", "symbol": "NIFTY"}, "tok",
                       close_fn=lambda *a, **k: closed.append(k["exit_reason"]) or (True, {}))
    assert out == "MANUAL_SPOT_SL" and keys == [upstox_api.get_instrument_key("NIFTY")]


def test_spot_exit_falls_back_to_trade_row_when_link_lost():
    closed = []
    t = {"trade_id": "T-lost", "symbol": "NIFTY", "strategy": "BULL_PUT_SPREAD", "entry_level_price": 24900.0}
    assert PM.spot_exit(t, "tok", spot_fn=lambda a, s: 24890.0,
                        close_fn=lambda *a, **k: closed.append(k["exit_reason"]) or (True, {})) == "MANUAL_SPOT_SL"


def test_no_entry_after_cutoff(db):
    d, _ = deps(now=NOW.replace(hour=14, minute=50), gate_fn=lambda *a, **k: pytest.fail("gate नको"))
    ok, msg = PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
    assert not ok and "14:45" in msg


@pytest.mark.parametrize("who", ["timeout", "vision", "stale"])
def test_only_human_telegram_approval_enters(db, who):
    VC.save("dynamic_sr_instant", {"vision_mode": "veto_then_confirm"}, "t", trading_mode_fn=lambda b, s: "PAPER")
    g = VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000.0, "SUPPORT", "5M", NOW, 25010.0, 2, 1)
    VS.transition(g.signal_id, ("QUEUED",), "APPROVED", None, decided_at=str(NOW), decided_by=who, factor=1.0)
    g2 = VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000.0, "SUPPORT", "5M", NOW, 25010.0, 2, 1, forced=True)
    assert g2.action != "ENTER" and g2.status == "SKIPPED_NO_HUMAN_APPROVAL"


def test_auto_veto_still_asks_human_in_paper():
    s = {**VC.BOT_DEFAULTS, "vision_mode": "auto_veto"}
    assert VC.effective_mode(s, "PAPER") == "human_confirm"
    assert VC.effective_mode({**s, "vision_mode": "veto_then_confirm"}, "PAPER") == "veto_then_confirm"
    assert VC.effective_mode(s, "LIVE") == "off"


def test_live_lot_size_unchanged():
    from paper import bot_hooks as PBH
    for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):
        assert PBH.pre_cycle("dynamic_sr_instant", "tok", sym, {"trading_mode": "LIVE"}).lot_size == 65      # आधीचा default
    assert PBH.pre_cycle("dynamic_sr_instant", "tok", "NIFTY", {"trading_mode": "LIVE"}, lot_size=75).lot_size == 75


def test_submit_with_final_hold_fails_cleanly(db):
    import vision.gate as VG2
    d, _ = deps(gate_fn=lambda *a, **k: VG2.Gate("HOLD", 0, 0, 0.0, "SKIPPED_VISION_REJECTED", "sid1", "आधीच नाकारलं", final=True))
    ok, msg = PM.handle("/paper NIFTY bullput SL 24900", "telegram:1", **d)
    assert not ok and "approval मार्ग उपलब्ध नाही" in msg and not PM.rows("QUEUED")
