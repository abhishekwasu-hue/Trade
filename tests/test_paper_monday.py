"""Monday PAPER (Abhi P0): approval शिवाय entry नाही, exit कधीच अडत नाही, Vision order देत नाही / image मधून किंमत नाही, LIVE मार्गाला
हात नाही, signal_source (own / engine / both), token नाही ⇒ स्पष्ट error, lot size (master / fallback), journal + charges, commands."""
import datetime as dt
import json
import os
import re
import sqlite3

import pandas as pd
import pytest

import engine_signal as ES
from paper import bot_hooks as PBH
from paper import commands as PCMD
from paper import config as PC
from paper import engine_entry as EE
from paper import journal as PJ
from paper import lots as PL
from paper import watch as PW
from tests.test_vision_v1 import NOW, db, paper, tick  # noqa: F401 (fixture)
from vision import config as VC
from vision import gate as VG
from vision import store as VS
from vision import telegram_bot as TB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = 123456789


@pytest.fixture(autouse=True)
def _approval_on(monkeypatch):
    monkeypatch.setitem(VC.BOT_DEFAULTS, "approval_required", True)              # production default (conftest tests मध्ये बंद ठेवतो)


def _src(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


# ------------------------------------------------------------------------------------------------ 1. approval शिवाय PAPER entry नाही
def test_paper_mode_forced_to_human_confirm_and_live_untouched():
    s = {**VC.BOT_DEFAULTS, "vision_mode": "notify"}
    assert VC.effective_mode(s, "PAPER") == "human_confirm"                      # V0 mode ⇒ approval मार्ग
    assert VC.effective_mode(s, "LIVE") == "off" and VC.effective_mode(s, "LIVE_PAPER") == "off"   # LIVE मार्ग जुनाच
    assert not VC.approval_required(s, "LIVE")
    assert VC.effective_mode({**s, "approval_required": False}, "PAPER") == "notify"


def gate(ts=None, level=25000.0, direction="BULLISH"):
    return VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", direction, level, "SUPPORT", "5M", ts or NOW, 25010.0, 2, 1)


def test_no_entry_without_approval_then_enter_after_approve(db):
    g = gate()
    assert g.action == "HOLD"                                                    # पहिला signal ⇒ vision / ✅ ची वाट
    row = VS.get_signal(g.signal_id)
    assert row["mode"] == "human_confirm"
    VS.transition(g.signal_id, ("QUEUED",), "PENDING_HUMAN", None, deadline=str(NOW + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0)
    assert gate().action == "HOLD"                                               # ✅ अजून नाही ⇒ entry नाही
    cq = {"id": "c1", "from": {"id": ME}, "message": {"chat": {"id": ME}, "message_id": 777},
          "data": __import__("vision.decide", fromlist=["x"]).callback_data(g.signal_id, "A")}
    ok, _ = TB.handle_callback(cq, now=NOW)
    assert ok
    ok2, why2 = TB.handle_callback(cq, now=NOW)                                  # double-click ⇒ एकच निर्णय
    assert not ok2 and why2 == "already"
    g2 = gate()
    assert g2.action == "ENTER" and g2.lots == 2
    assert gate().action == "HOLD"                                               # तोच signal पुन्हा ENTER नाही (एकच order)


def test_timeout_means_no_entry(db):
    g = gate()
    VS.transition(g.signal_id, ("QUEUED",), "PENDING_HUMAN", None, deadline=str(NOW + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0)
    tick(db, 11)
    g2 = VG.entry_gate("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000.0, "SUPPORT", "5M", NOW, 25010.0, 2, 1, forced=True)
    assert g2.action != "ENTER"


def test_reject_never_enters(db):
    g = gate()
    VS.transition(g.signal_id, ("QUEUED",), "PENDING_HUMAN", None, deadline=str(NOW + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0)
    cq = {"id": "c2", "from": {"id": ME}, "message": {"chat": {"id": ME}, "message_id": 777},
          "data": __import__("vision.decide", fromlist=["x"]).callback_data(g.signal_id, "R")}
    assert TB.handle_callback(cq, now=NOW)[0]
    assert gate().action in ("SHADOW", "HOLD")                                   # ❌ ⇒ खरा entry नाही


def test_gate_error_in_paper_holds(monkeypatch, db):
    monkeypatch.setattr(VG, "_gate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert gate().action == "HOLD"                                               # approval_required ⇒ चूक ⇒ entry नाही


def test_unlisted_symbol_holds_in_paper(db):
    g = VG.entry_gate("dynamic_sr_instant", "BANKNIFTY", "PAPER", "BULLISH", 50000.0, "SUPPORT", "5M", NOW, 50010.0, 1, 1)
    assert g.action == "HOLD" and g.status == "SKIPPED_NOT_ENABLED"


def test_bots_hold_when_gate_unavailable_in_paper():
    for f in ("dynamic_sr_instant_trader.py", "srv2_momentum_reversal_strategy.py"):
        s = _src(f)
        assert 'if _vg is None and str(settings.get("trading_mode", "PAPER")).upper() == "PAPER":' in s
        assert "SKIPPED_VISION_ERROR" in s and "_PBH.own_signal_ok" in s and "_PBH.pre_cycle" in s
    s3 = _src("srv3_instant_shadow.py")
    assert "_gate(symbol, direction, level" in s3 and 'g is None or g.action != "ENTER"' in s3


# ------------------------------------------------------------------------------------------------ 2. exit कधीही अडत नाही
def test_paper_watch_lock_and_never_raises(monkeypatch, tmp_path):
    """Exits नंतरचा क्रम / stream loop: tests/test_paper_approval_e2e.py (behaviour). इथे: स्वतःचा lock आणि कधीच raise नाही."""
    calls = []
    monkeypatch.setattr(PW, "run_cycle", lambda tok, **k: calls.append(tok) or {"entries": 0})
    from process_lock import ProcessLock
    with ProcessLock("paper_watch"):                                             # दुसरा monitor watcher चालवत असेल ⇒ वगळतो
        assert PW.run_locked("tok") is None and not calls
    assert PW.run_locked("tok") == {"entries": 0} and calls == ["tok"]
    monkeypatch.undo()
    monkeypatch.setattr(PW, "_trades", lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    assert PW.run_cycle("tok", now=pd.Timestamp("2026-10-12 10:00"), db_path=str(tmp_path / "x.db")) == {"entries": 0, "exits": 0, "updates": 0}


def test_pause_is_paper_scoped_and_only_blocks_entries(monkeypatch):
    import cloud_db
    from paper import pause as PP
    monkeypatch.setattr(cloud_db, "set_trading_pause", lambda *a, **k: pytest.fail("Telegram ने LIVE / dashboard pause बदलू नये"))
    assert "PAPER" in PCMD.pause("telegram:1") and PP.paused()
    s = {"signal_source": "own", "trading_mode": "PAPER"}
    assert PBH.own_signal_ok("NIFTY", "BULLISH", s)[0] is False                  # नवे PAPER entries नाहीत
    assert PBH.own_signal_ok("NIFTY", "BULLISH", {**s, "trading_mode": "LIVE"})[0] is True   # LIVE ला हात नाही
    PCMD.resume("telegram:1")
    assert not PP.paused() and PBH.own_signal_ok("NIFTY", "BULLISH", s)[0] is True

def test_vision_cannot_place_orders():
    for d in ("vision", "vision2"):
        for f in os.listdir(os.path.join(ROOT, d)):
            if f.endswith(".py"):
                s = _src(os.path.join(d, f))
                for bad in ("open_multi_leg_trade", "place_order", "execute_trade_on_all_accounts", "broker_factory", "fetch_upstox_option_chain"):
                    assert bad not in s, f"{d}/{f}: {bad}"
    assert set(VG.Gate.__dataclass_fields__) == {"action", "lots", "naked_lots", "factor", "status", "signal_id", "note", "drift", "final"}


def test_no_price_from_image():
    for f in ("paper/engine_entry.py", "paper/watch.py", "paper/journal.py", "paper/bot_hooks.py", "engine_signal.py"):
        s = _src(f)
        for bad in ("vision_json", "image_path", "png", "audits"):
            assert bad not in s, f"{f}: {bad}"
    assert "raw_chain[0].get(\"underlying_spot_price\")" in _src("paper/engine_entry.py")         # किंमत फक्त API chain मधून


def test_live_path_untouched():
    pre = PBH.pre_cycle("dynamic_sr_instant", None, "NIFTY", {"trading_mode": "LIVE"}, None, cfg={"instruments": {"NIFTY": {"enabled": True,
                        "lot_size_fallback": 65}}})
    assert not pre.stop and pre.lot_size == 65                                   # token / enabled / engine — LIVE ला लागू नाही
    assert PBH.own_signal_ok("NIFTY", "BULLISH", {"trading_mode": "LIVE", "signal_source": "engine"})[0]
    assert "signal_source = engine फक्त PAPER" in EE.process("x", "t", "NIFTY", {"signal_source": "engine", "trading_mode": "LIVE"}, 65, "x")


# ------------------------------------------------------------------------------------------------ 4. signal_source
@pytest.fixture
def es(tmp_path):
    p = str(tmp_path / "es.db")
    return p


def _put(p, decision="setup", d=1, bar="2026-10-12 10:00:00"):
    ES.save({"symbol": "NIFTY", "bar_ts": bar, "computed_at": bar, "decision": decision, "gate": None if decision == "setup" else "G-A",
             "direction": d, "level_lo": 25000.0, "level_hi": 25020.0, "entry": 25030.0, "invalidation": 24980.0, "target": 25200.0,
             "grade": "B", "reason": "x", "payload": "{}"}, p)


def test_signal_source_three_modes(es):
    now = "2026-10-12 10:05"
    assert ES.own_allowed("NIFTY", "BULLISH", {"signal_source": "own"}, now, es)[0]
    assert not ES.own_allowed("NIFTY", "BULLISH", {"signal_source": "engine"}, now, es)[0]
    assert not ES.own_allowed("NIFTY", "BULLISH", {"signal_source": "both"}, now, es)[0]           # engine setup नाही
    _put(es)
    assert ES.own_allowed("NIFTY", "BULLISH", {"signal_source": "both"}, now, es)[0]               # दिशा जुळली
    assert not ES.own_allowed("NIFTY", "BEARISH", {"signal_source": "both"}, now, es)[0]
    assert not ES.own_allowed("NIFTY", "BULLISH", {"signal_source": "both"}, "2026-10-12 11:30", es)[0]   # जुना (stale) setup नाही
    assert "setup ↑" in ES.opinion("NIFTY", now, es)
    assert ES.source_of({"signal_source": "weird"}) == "own"


def test_engine_mode_goes_through_gate_and_enters_once(es, monkeypatch):
    _put(es)
    opened = []
    G = type("G", (), {})
    hold = G()
    hold.action, hold.note = "HOLD", "वाट"
    enter = G()
    enter.action, enter.lots, enter.naked_lots, enter.signal_id, enter.note = "ENTER", 1, 0, None, "ok"
    st = {"signal_source": "engine", "trading_mode": "PAPER", "lots": 1, "naked_lots": 0, "naked_enabled": False, "itm_depth_points": 100,
          "hedge_width_points": 150}
    chain = [{"underlying_spot_price": 25010.0}]
    monkeypatch.setattr(EE, "open_paper", lambda *a, **k: (opened.append(a) or ["Credit Spread ✅"], 25010.0))
    now = "2026-10-12 10:05"
    m = EE.process("dynamic_sr_instant", "t", "NIFTY", st, 65, "dynamic_sr_instant", now=now, has_open=lambda s, src: False,
                   gate_fn=lambda *a, **k: hold, chain=chain, path=es)
    assert "वाट" in m and not opened                                             # approval शिवाय entry नाही
    m = EE.process("dynamic_sr_instant", "t", "NIFTY", st, 65, "dynamic_sr_instant", now=now, has_open=lambda s, src: False,
                   gate_fn=lambda *a, **k: enter, chain=chain, path=es)
    assert len(opened) == 1
    m = EE.process("dynamic_sr_instant", "t", "NIFTY", st, 65, "dynamic_sr_instant", now=now, has_open=lambda s, src: False,
                   gate_fn=lambda *a, **k: enter, chain=chain, path=es)
    assert len(opened) == 1 and "नवा setup नाही" in m                            # तोच signal पुन्हा नाही


def test_pre_cycle_engine_mode_routes_to_engine():
    calls = []
    pre = PBH.pre_cycle("dynamic_sr_instant", "tok", "NIFTY", {"signal_source": "engine", "trading_mode": "PAPER"}, 65,
                        cfg={"instruments": {"NIFTY": {"enabled": True}}}, engine_fn=lambda *a, **k: calls.append(a) or "engine msg")
    assert not pre.stop and pre.msg == "engine msg" and calls                    # engine मार्ग चालला, bot चा cycle (levels refresh) चालू
    assert PBH.own_signal_ok("NIFTY", "BULLISH", {"signal_source": "engine", "trading_mode": "PAPER"})[0] is False   # bot चे स्वतःचे entries नाहीत


# ------------------------------------------------------------------------------------------------ 5. token / instruments / lot size
def test_token_missing_is_explicit_and_alerts_once(tmp_path):
    sent = []
    cfg = {"instruments": {"NIFTY": {"enabled": True}}}
    st = str(tmp_path / "tok.json")
    pre = PBH.pre_cycle("dynamic_sr_instant", None, "NIFTY", {"trading_mode": "PAPER"}, None, cfg=cfg, send=sent.append)
    assert pre.stop and "token नाही" in pre.msg
    PBH.token_error("NIFTY", "b", send=sent.append, state_path=st)
    PBH.token_error("NIFTY", "b", send=sent.append, state_path=st)
    assert len([x for x in sent if "token नाही" in x]) >= 1
    n = len(sent)
    PBH.token_error("NIFTY", "b", send=sent.append, state_path=st)
    assert len(sent) == n                                                        # दिवसातून एकदाच


def test_instrument_disabled_blocks_paper():
    cfg = {"instruments": {"NIFTY": {"enabled": True}, "BANKNIFTY": {"enabled": False}}}
    assert PBH.pre_cycle("dynamic_sr_instant", "tok", "BANKNIFTY", {"trading_mode": "PAPER"}, 30, cfg=cfg).stop
    c = PC.load()
    assert PC.enabled("NIFTY", c) and not PC.enabled("BANKNIFTY", c) and not PC.enabled("SENSEX", c)


def test_lot_size_from_master_with_mismatch_warning(tmp_path):
    sent = []
    cfg = {"instruments": {"NIFTY": {"enabled": True, "lot_size_fallback": 65}}}
    lot, src = PL.lot_size("tok", "NIFTY", today=dt.date(2026, 10, 12), resolve=lambda t, s, d: ({"lot_size": 75}, None), send=sent.append,
                           cache_path=str(tmp_path / "c.json"), cfg=cfg)
    assert (lot, src) == (75, "upstox") and any("≠" in x for x in sent)
    lot2, src2 = PL.lot_size("tok", "NIFTY", today=dt.date(2026, 10, 13), resolve=lambda t, s, d: (None, "err"), send=sent.append,
                             cache_path=str(tmp_path / "c.json"), cfg=cfg)
    assert (lot2, src2) == (65, "config fallback")
    assert "lot_size=65" not in _src("dynamic_sr_instant_trader.py") and "lot_size=65" not in _src("srv2_momentum_reversal_strategy.py")


# ------------------------------------------------------------------------------------------------ 6. journal + charges + updates
def _mk_db(p):
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE live_trades (trade_id TEXT, trade_date TEXT, symbol TEXT, strategy TEXT, lots INTEGER, lot_size INTEGER,
                 net_credit REAL, max_profit REAL, max_loss REAL, sl_pnl_level REAL, target_pnl_level REAL, entry_time TEXT, exit_time TEXT,
                 exit_reason TEXT, realized_pnl REAL, status TEXT, legs_json TEXT, strikes_summary TEXT, mode TEXT, source TEXT,
                 pnl_multiplier REAL)""")
    c.execute("""CREATE TABLE order_log (order_id TEXT, trade_id TEXT, symbol TEXT, mode TEXT, instrument_key TEXT, strike REAL,
                 option_type TEXT, transaction_type TEXT, order_type TEXT, quantity INTEGER, price REAL, trigger_price REAL, status TEXT,
                 tag TEXT, placed_at TEXT, fill_price REAL)""")
    legs = [{"instrument_key": "K1", "transaction_type": "BUY", "strike": 24900, "option_type": "PE", "ltp": 40.0},
            {"instrument_key": "K2", "transaction_type": "SELL", "strike": 25050, "option_type": "PE", "ltp": 110.0}]
    c.execute("INSERT INTO live_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("PAPER_1", "2026-10-12", "NIFTY", "Bull Put", 1, 65, 70.0, 70.0, -80.0, -4550.0, 4550.0, "2026-10-12 10:10:00", None, None, None,
               "OPEN", json.dumps(legs), "", "PAPER", "dynamic_sr_instant", 1.0))
    for k, side, px in (("K1", "BUY", 40.0), ("K2", "SELL", 110.0)):
        c.execute("INSERT INTO order_log (trade_id, symbol, mode, instrument_key, transaction_type, quantity, fill_price) VALUES (?,?,?,?,?,?,?)",
                  ("PAPER_1", "NIFTY", "PAPER", k, side, 65, px))
    c.commit()
    c.close()


def test_journal_entry_updates_exit_with_charges(tmp_path, monkeypatch):
    dbp, jp = str(tmp_path / "h.db"), str(tmp_path / "j.db")
    _mk_db(dbp)
    sent = []
    monkeypatch.setattr(PW, "vision_link", lambda *a, **k: {"vision_signal_id": "s1", "vision_verdict": "agree", "vision_reason": "ok",
                                                         "approver": f"telegram:{ME}"})
    cfg = {"update_every_min": 30, "near_alert_pct": 80}
    t0 = pd.Timestamp("2026-10-12 10:12")
    out = PW.run_cycle("tok", now=t0, db_path=dbp, send=sent.append, jpath=jp, cfg=cfg, ltp_fn=lambda tok, keys: {"K1": 40.0, "K2": 110.0},
                       settings_fn=lambda b, s: {"signal_source": "own"})
    assert out["entries"] == 1
    j = PJ.get("PAPER_1", jp)
    assert j["bot"] == "dynamic_sr_instant" and j["vision_verdict"] == "agree" and j["approver"] == f"telegram:{ME}" and j["rr"] == 1.0
    assert j["entry_charges"] > 0 and j["signal_source"] == "own" and j["engine_opinion"].startswith("engine")
    assert "PAPER entry" in sent[0] and "net credit" in sent[0]
    # 30 मिनिटांनी P&L + SL जवळ इशारा (एकदाच)
    near = {"K1": 10.0, "K2": 160.0}                                             # P&L = (110−160 + 10−40) × 65 = −5200 ≤ 0.8 × SL
    PW.run_cycle("tok", now=t0 + pd.Timedelta(minutes=31), db_path=dbp, send=sent.append, jpath=jp, cfg=cfg, ltp_fn=lambda tok, keys: near)
    assert any("SL जवळ" in x for x in sent) and any("⏱ P&L" in x for x in sent)
    n = len(sent)
    PW.run_cycle("tok", now=t0 + pd.Timedelta(minutes=33), db_path=dbp, send=sent.append, jpath=jp, cfg=cfg, ltp_fn=lambda tok, keys: near)
    assert len(sent) == n                                                        # इशारा पुन्हा नाही
    # exit
    c = sqlite3.connect(dbp)
    c.execute("UPDATE live_trades SET status='CLOSED', exit_time='2026-10-12 11:00:00', exit_reason='SL', realized_pnl=-4550 WHERE trade_id='PAPER_1'")
    for k, side, px in (("K1", "SELL", 15.0), ("K2", "BUY", 155.0)):
        c.execute("INSERT INTO order_log (trade_id, symbol, mode, instrument_key, transaction_type, quantity, fill_price) VALUES (?,?,?,?,?,?,?)",
                  ("PAPER_1", "NIFTY", "PAPER", k, side, 65, px))
    c.commit()
    c.close()
    out = PW.run_cycle("tok", now=t0 + pd.Timedelta(minutes=50), db_path=dbp, send=sent.append, jpath=jp, cfg=cfg, ltp_fn=lambda tok, keys: near)
    assert out["exits"] == 1
    j = PJ.get("PAPER_1", jp)
    assert j["exit_charges"] > 0 and j["net_pnl"] == pytest.approx(-4550 - j["entry_charges"] - j["exit_charges"], abs=0.02)
    assert "PAPER exit" in sent[-1] and "net" in sent[-1]
    assert PW.run_cycle("tok", now=t0 + pd.Timedelta(minutes=51), db_path=dbp, send=sent.append, jpath=jp, cfg=cfg)["exits"] == 0


def test_order_charges_match_charges_module():
    import charges as CH
    o = [{"transaction_type": "SELL", "quantity": 65, "fill_price": 110.0}, {"transaction_type": "BUY", "quantity": 65, "fill_price": 40.0}]
    exp = sum(CH._accurate_row_charges({"quantity": x["quantity"], "fill_price": x["fill_price"], "symbol": "NIFTY",
                                        "transaction_type": x["transaction_type"]}, "upstox")["charge"] for x in o)
    assert PJ.order_charges(o, "NIFTY") == round(exp, 2)


# ------------------------------------------------------------------------------------------------ 7. commands
def test_status_and_positions_text():
    txt = PCMD.status_text(token_fn=lambda: None, market_fn=lambda: False, kill_fn=lambda: (True, None), pause_fn=lambda: {"paused": True,
                           "reason": "r"}, settings_fn=lambda k, s: {"signal_source": "both", "srv3_signal_source": "own"}, trades_fn=lambda: [])
    assert "token: ❌" in txt and "बाजार: बंद" in txt and "pause" in txt and "signal_source = both" in txt and "signal_source = own" in txt
    assert "उघडे trades: 0" in txt and "Exits" in txt
    assert "उघडा trade नाही" in PCMD.positions_text(lambda: [])


def test_commands_require_approver(db):
    sent = []
    ok, why = TB.handle_command("/pause", {"id": 999}, {"id": 999}, send=sent.append)
    assert not ok and why == "unauthorized" and not sent


def test_sources_have_no_dates_or_live_orders():
    for f in ("engine_signal.py", "paper/bot_hooks.py", "paper/engine_entry.py", "paper/watch.py", "paper/journal.py", "paper/commands.py",
              "paper/lots.py", "paper/config.py", "scripts/engine_signal_run.py"):
        s = _src(f)
        assert not re.search(r"20\d\d-\d\d-\d\d", s), f
        assert 'trading_mode="LIVE"' not in s and "place_order" not in s
