"""PAPER entry card for a NAKED leg (Abhi T-1, display only): no "target ₹0 · R:R NA" / "net credit ₹-…"; instead "premium paid ₹…"
and the active exit rules in words with their dashboard values. Exit logic is untouched (trading_engine is not changed)."""
import json
import sqlite3

import pandas as pd

from paper import journal as PJ
from paper import watch as PW

SS = {"signal_source": "own", "naked_sl_spot_pct": 0.4, "naked_sl_premium_points": 30, "naked_tsl_spot_pct": 0.3,
      "naked_tsl_premium_points": 20, "naked_target_spot_pct": 0.8, "naked_target_premium_points": 60, "naked_trailing_sl_enabled": True,
      "naked_trailing_distance_points": 15, "naked_eod_hour": 15, "naked_eod_minute": 5}


def _db(p, strategy="NAKED_CALL", source="dynamic_sr_instant", net_credit=-120.0, sl=-1950.0, tg=0.0):
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE live_trades (trade_id TEXT, trade_date TEXT, symbol TEXT, strategy TEXT, lots INTEGER, lot_size INTEGER,
                 net_credit REAL, max_profit REAL, max_loss REAL, sl_pnl_level REAL, target_pnl_level REAL, entry_time TEXT, exit_time TEXT,
                 exit_reason TEXT, realized_pnl REAL, status TEXT, legs_json TEXT, strikes_summary TEXT, mode TEXT, source TEXT,
                 pnl_multiplier REAL, trade_style TEXT, entry_timeframe TEXT)""")
    c.execute("""CREATE TABLE order_log (order_id TEXT, trade_id TEXT, symbol TEXT, mode TEXT, instrument_key TEXT, strike REAL,
                 option_type TEXT, transaction_type TEXT, order_type TEXT, quantity INTEGER, price REAL, trigger_price REAL, status TEXT,
                 tag TEXT, placed_at TEXT, fill_price REAL)""")
    legs = [{"role": "naked_buy", "instrument_key": "K1", "transaction_type": "BUY", "strike": 25000, "option_type": "CE", "ltp": 120.0}]
    c.execute("INSERT INTO live_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("PAPER_N", "2026-10-12", "NIFTY", strategy, 1, 65, net_credit, None, -net_credit, sl, tg, "2026-10-12 10:10:00", None, None,
               None, "OPEN", json.dumps(legs), "", "PAPER", source, 1.0, "INTRADAY", "1M"))
    c.execute("INSERT INTO order_log (trade_id, symbol, mode, instrument_key, transaction_type, quantity, fill_price) VALUES (?,?,?,?,?,?,?)",
              ("PAPER_N", "NIFTY", "PAPER", "K1", "BUY", 65, 120.0))
    c.commit()
    c.close()


def _run(tmp_path, monkeypatch, ss=SS, **kw):
    dbp, jp = str(tmp_path / "h.db"), str(tmp_path / "j.db")
    _db(dbp, **kw)
    sent = []
    monkeypatch.setattr(PW, "vision_link", lambda *a, **k: {})
    t0 = pd.Timestamp("2026-10-12 10:12")
    cfg = {"update_every_min": 30, "near_alert_pct": 80}
    out = PW.run_cycle("tok", now=t0, db_path=dbp, send=sent.append, jpath=jp, cfg=cfg, ltp_fn=lambda tok, keys: {"K1": 120.0},
                       settings_fn=lambda b, s: ss)
    assert out["entries"] == 1
    return sent, dbp, jp, cfg, t0


def test_naked_entry_card_shows_premium_paid_and_dashboard_exit_rules(tmp_path, monkeypatch):
    import trading_engine as TE
    sent, *_ = _run(tmp_path, monkeypatch)
    card = sent[0]
    assert "premium paid ₹7,800" in card                                        # 120 × 1 lot × 65
    assert "target ₹0" not in card and "R:R NA" not in card and "net credit" not in card
    assert "SL: spot 0.4% against or premium −30 pts" in card
    assert "TSL: spot 0.3% in favour or premium +20 pts ⇒ SL to entry, then trail 15 pts" in card
    assert "target: spot 0.8% in favour or premium +60 pts" in card
    assert f"EOD exit {TE.DYNAMIC_SR_EOD_HOUR}:{TE.DYNAMIC_SR_EOD_MINUTE:02d}" in card
    assert "next 5M level" not in card                                          # 1M entry


def test_naked_srv2_uses_its_own_eod_setting_and_no_trail_when_off(tmp_path, monkeypatch):
    sent, *_ = _run(tmp_path, monkeypatch, ss={**SS, "naked_trailing_sl_enabled": False}, source="srv2_momentum_reversal",
                    strategy="NAKED_PUT")
    assert "EOD exit 15:05" in sent[0] and "then trail" not in sent[0] and "premium paid" in sent[0]


def test_naked_settings_missing_never_breaks_the_card(tmp_path, monkeypatch):
    sent, *_ = _run(tmp_path, monkeypatch, ss={"signal_source": "own"})
    assert "premium paid ₹7,800" in sent[0] and "exits: dashboard settings (NA:" in sent[0] and "target ₹0" not in sent[0]


def test_naked_periodic_update_has_no_zero_target(tmp_path, monkeypatch):
    sent, dbp, jp, cfg, t0 = _run(tmp_path, monkeypatch)
    PW.run_cycle("tok", now=t0 + pd.Timedelta(minutes=31), db_path=dbp, send=sent.append, jpath=jp, cfg=cfg,
                 ltp_fn=lambda tok, keys: {"K1": 130.0})
    upd = [x for x in sent if "⏱ P&L" in x]
    assert upd and "target ₹0" not in upd[-1] and "exits: dashboard" in upd[-1]


def test_spread_card_unchanged(tmp_path, monkeypatch):
    sent, _, jp, *_ = _run(tmp_path, monkeypatch, strategy="Bull Put", net_credit=70.0, sl=-4550.0, tg=4550.0)
    assert "net credit ₹4,550" in sent[0] and "target ₹4,550" in sent[0] and "R:R 1.0" in sent[0] and "premium paid" not in sent[0]
    assert PJ.get("PAPER_N", jp)["rr"] == 1.0


def test_exit_logic_not_touched():
    src = open(PW.__file__, encoding="utf-8").read()
    assert "UPDATE live_trades" not in src and "evaluate_point_spot_exit" not in src
