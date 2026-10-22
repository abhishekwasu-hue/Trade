"""PAPER trade messages show the exits the bot really uses (Abhi T-6, DECISIONS 30; display only).

The bots store sl_pnl_level from a hard-coded 100% of credit, but trading_engine.manage_open_trades exits them from the dashboard
settings (spot % / premium points SL, TSL ⇒ entry, trail, target, next level, EOD / carry-forward). The entry card, the periodic
"⏱ P&L" line, the near alerts and /positions show those real exits (own unit + ₹ for the position), never the stored SL. Trades the
engine closes on the stored ₹ levels (generic branch, e.g. the Sunday dry-run sources) keep the stored levels."""
import json
import sqlite3

import pandas as pd

from paper import commands as PCMD
from paper import watch as PW

SS2 = {"signal_source": "own", "spread_sl_spot_pct": 0.15, "spread_sl_premium_points": 10, "spread_tsl_spot_pct": 0.3,
       "spread_tsl_premium_points": 25, "spread_target_pct_of_premium": 80, "carry_forward_min_profit_pct": 30,
       "spread_trailing_sl_enabled": False, "spread_trailing_distance_points": 8,
       "naked_sl_spot_pct": 0.05, "naked_sl_premium_points": 10, "naked_tsl_spot_pct": 0.1, "naked_tsl_premium_points": 20,
       "naked_target_spot_pct": 0.4, "naked_target_premium_points": 50, "naked_trailing_sl_enabled": False,
       "naked_trailing_distance_points": 15, "naked_eod_hour": 15, "naked_eod_minute": 0}
CFG = {"update_every_min": 30, "near_alert_pct": 80}
T0 = pd.Timestamp("2026-10-12 10:12")


def _mk_db(p, source="srv2_momentum_reversal", strategy="BULL_PUT_SPREAD", lots=2, tsl=0, peak=None, timeframe="15M"):
    """Spread: BUY 24900 PE @40 · SELL 25050 PE @110 ⇒ credit 70 × 2 lots × 65 = ₹9,100; stored SL ₹-9,100 (100%), target ₹7,280 (80%).
    Naked: BUY 25000 PE @120 ⇒ premium ₹15,600 (2 lots); stored SL ₹-15,600, target None."""
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE live_trades (trade_id TEXT, trade_date TEXT, symbol TEXT, strategy TEXT, lots INTEGER, lot_size INTEGER,
                 net_credit REAL, max_profit REAL, max_loss REAL, sl_pnl_level REAL, target_pnl_level REAL, entry_time TEXT, exit_time TEXT,
                 exit_reason TEXT, realized_pnl REAL, status TEXT, legs_json TEXT, strikes_summary TEXT, mode TEXT, source TEXT,
                 pnl_multiplier REAL, trade_style TEXT, entry_timeframe TEXT, entry_level_price REAL, entry_spot_price REAL,
                 tsl_activated INTEGER, peak_pnl REAL)""")
    c.execute("""CREATE TABLE order_log (order_id TEXT, trade_id TEXT, symbol TEXT, mode TEXT, instrument_key TEXT, strike REAL,
                 option_type TEXT, transaction_type TEXT, order_type TEXT, quantity INTEGER, price REAL, trigger_price REAL, status TEXT,
                 tag TEXT, placed_at TEXT, fill_price REAL)""")
    if strategy.startswith("NAKED"):
        legs = [{"instrument_key": "K1", "transaction_type": "BUY", "strike": 25000, "option_type": "PE", "ltp": 120.0}]
        nc, sl, tg = -120.0, -15600.0, None
    else:
        legs = [{"instrument_key": "K1", "transaction_type": "BUY", "strike": 24900, "option_type": "PE", "ltp": 40.0},
                {"instrument_key": "K2", "transaction_type": "SELL", "strike": 25050, "option_type": "PE", "ltp": 110.0}]
        nc, sl, tg = 70.0, -9100.0, 7280.0
    c.execute(f"INSERT INTO live_trades VALUES ({','.join('?' * 27)})",
              ("PAPER_S", "2026-10-12", "NIFTY", strategy, lots, 65, nc, nc if nc > 0 else None, 80.0 if nc > 0 else -nc, sl, tg,
               "2026-10-12 10:10:00", None, None, None, "OPEN", json.dumps(legs), "", "PAPER", source, 1.0, "INTRADAY", timeframe,
               24990.0, 25000.0, tsl, peak))
    for lg in legs:
        c.execute("INSERT INTO order_log (trade_id, symbol, mode, instrument_key, transaction_type, quantity, fill_price) VALUES (?,?,?,?,?,?,?)",
                  ("PAPER_S", "NIFTY", "PAPER", lg["instrument_key"], lg["transaction_type"], lots * 65, lg["ltp"]))
    c.commit()
    c.close()


def _set(dbp, **kw):
    c = sqlite3.connect(dbp)
    for k, v in kw.items():
        c.execute(f"UPDATE live_trades SET {k}=? WHERE trade_id='PAPER_S'", (v,))
    c.commit()
    c.close()


def _entry(tmp_path, monkeypatch, ss=SS2, level=25120.0, **kw):
    dbp, jp = str(tmp_path / "h.db"), str(tmp_path / "j.db")
    _mk_db(dbp, **kw)
    sent = []
    monkeypatch.setattr(PW, "vision_link", lambda *a, **k: {})
    ltp = {"K1": 40.0, "K2": 110.0} if not kw.get("strategy", "").startswith("NAKED") else {"K1": 120.0}
    out = PW.run_cycle("tok", now=T0, db_path=dbp, send=sent.append, jpath=jp, cfg=CFG, ltp_fn=lambda tok, keys: ltp,
                       settings_fn=lambda b, s: ss, level_fn=lambda *a, **k: level)
    assert out["entries"] == 1
    return sent, dbp, jp


def _tick(sent, dbp, jp, ltp, minutes=31, ss=SS2):
    PW.run_cycle("tok", now=T0 + pd.Timedelta(minutes=minutes), db_path=dbp, send=sent.append, jpath=jp, cfg=CFG,
                 ltp_fn=lambda tok, keys: ltp, settings_fn=lambda b, s: ss, level_fn=lambda *a, **k: None)
    return sent[-1]


# ------------------------------------------------------------------------------------------------ entry cards
def test_srv2_spread_card_shows_the_real_exits_not_the_stored_sl(tmp_path, monkeypatch):
    card = _entry(tmp_path, monkeypatch)[0][0]
    assert "SL ₹-9,100" not in card and "-9,100" not in card                                # stored 100%-credit SL never shown
    assert "net credit ₹9,100" in card and "R:R (premium SL) 5.6" in card                   # 7,280 / 1,300
    assert "SL: spot 0.15% against or premium −10 pts (spot 24,962.5 · ₹-1,300)" in card     # bull put: SL below the entry spot
    assert "TSL: spot 0.3% in favour or premium +25 pts ⇒ SL to entry (activates at spot 25,075.0 · ₹+3,250)" in card
    assert "then trail" not in card                                                         # trailing off
    assert "target: 80% of credit (₹+7,280)" in card
    assert "next 15M S/R level reached ⇒ exit (now spot 25,120.0)" in card
    assert "carry-forward check 15:10: P&L below 30% of credit (₹2,730) ⇒ exit, else carried forward" in card


def test_spread_card_values_come_from_the_settings(tmp_path, monkeypatch):
    ss = {**SS2, "spread_sl_premium_points": 12, "spread_sl_spot_pct": 0.2, "spread_tsl_premium_points": 30,
          "carry_forward_min_profit_pct": 40, "spread_trailing_sl_enabled": True, "spread_trailing_distance_points": 6}
    card = _entry(tmp_path, monkeypatch, ss=ss, level=None)[0][0]
    assert "premium −12 pts (spot 24,950.0 · ₹-1,560)" in card and "premium +30 pts" in card and "₹+3,900" in card
    assert "then trail 6 pts" in card and "trail ₹780" in card and "40% of credit (₹3,640)" in card
    assert "next 15M S/R level reached ⇒ exit ·" in card                                    # no level found ⇒ the rule only


def test_srv2_naked_card(tmp_path, monkeypatch):
    card = _entry(tmp_path, monkeypatch, strategy="NAKED_PUT")[0][0]
    assert "premium paid ₹15,600" in card and "net credit" not in card and "target ₹0" not in card and "R:R" not in card
    assert "-15,600" not in card                                                            # stored SL never shown
    assert "SL: spot 0.05% against or premium −10 pts (spot 25,012.5 · ₹-1,300)" in card     # naked put: SL above the entry spot
    assert "TSL: spot 0.1% in favour or premium +20 pts ⇒ SL to entry (activates at spot 24,975.0 · ₹+2,600)" in card
    assert "target: spot 0.4% in favour or premium +50 pts (spot 24,900.0 · ₹+6,500)" in card
    assert "EOD exit 15:00 (never carried forward)" in card and "next 15M" not in card


def test_5min_spread_card_uses_its_own_settings_and_eod(tmp_path, monkeypatch):
    import trading_engine as TE
    ss = {**SS2, "spread_target_spot_pct": 0.2, "spread_target_premium_points": 15}
    card = _entry(tmp_path, monkeypatch, ss=ss, source="dynamic_sr_instant", timeframe="5M", level=25040.0)[0][0]
    assert "target: spot 0.2% in favour or premium +15 pts (spot 25,050.0 · ₹+1,950)" in card and "of credit" not in card
    assert "next 5M S/R level reached ⇒ exit (now spot 25,040.0)" in card
    assert f"EOD exit {TE.DYNAMIC_SR_EOD_HOUR}:{TE.DYNAMIC_SR_EOD_MINUTE:02d}" in card and "carry-forward" not in card


def test_dry_run_source_keeps_the_stored_levels_the_engine_uses(tmp_path, monkeypatch):
    """`*_dryrun_shadow` is not in SHADOW_EXIT_PARENT_SOURCE ⇒ the engine's generic branch exits on the stored ₹ levels."""
    card = _entry(tmp_path, monkeypatch, source="srv2_momentum_reversal_dryrun_shadow")[0][0]
    assert "SL ₹-9,100" in card and "target ₹7,280" in card and "SL: spot" not in card


# ------------------------------------------------------------------------------------------------ periodic lines
def test_periodic_line_tsl_off(tmp_path, monkeypatch):
    sent, dbp, jp = _entry(tmp_path, monkeypatch)
    msg = _tick(sent, dbp, jp, {"K1": 38.0, "K2": 112.0})                                  # P&L = −4 pts × 130 = ₹-520
    line = [x for x in msg.split("\n") if x.startswith("⏱ P&L")][0]
    assert line.startswith("⏱ P&L ₹-520 · ") and "-9,100" not in line and "target ₹0" not in line
    assert "SL spot 24,962.5 or premium −10 pts (₹-1,300) पर्यंत ₹780" in line
    assert "TSL not active (at spot 25,075.0 or ₹+3,250)" in line
    assert "target 80% of credit (₹+7,280) पर्यंत ₹7,800" in line


def test_periodic_line_tsl_on_locked_at_entry_then_trailing(tmp_path, monkeypatch):
    sent, dbp, jp = _entry(tmp_path, monkeypatch)
    _set(dbp, tsl_activated=1)
    line = _tick(sent, dbp, jp, {"K1": 30.0, "K2": 70.0})                                 # P&L = +30 pts = ₹3,900
    assert "TSL active ⇒ SL locked at entry (₹0) पर्यंत ₹3,900" in line and "TSL not active" not in line
    _set(dbp, peak_pnl=40.0)                                                                 # peak 40 pts, trail 8 ⇒ floor 32 pts
    line = _tick(sent, dbp, jp, {"K1": 25.0, "K2": 60.0}, minutes=62, ss={**SS2, "spread_trailing_sl_enabled": True})
    assert "TSL active ⇒ SL trailing +32 pts (₹+4,160) पर्यंत ₹390" in line                  # P&L = 35 pts = ₹4,550


def test_near_alerts_use_the_premium_thresholds_not_the_stored_sl(tmp_path, monkeypatch):
    sent, dbp, jp = _entry(tmp_path, monkeypatch)
    msg = _tick(sent, dbp, jp, {"K1": 36.0, "K2": 115.0}, minutes=5)                       # −9 pts = ₹-1,170 ≤ 0.8 × ₹-1,300
    assert "⚠️ SL जवळ: P&L ₹-1,170 (premium SL −10 pts = ₹-1,300; or spot 24,962.5, whichever first)" in msg
    assert "⏱ P&L" not in msg                                                               # not due yet
    msg = _tick(sent, dbp, jp, {"K1": 5.0, "K2": 15.0}, minutes=10)                        # +60 pts = ₹7,800 ≥ 0.8 × ₹7,280
    assert "🎯 target जवळ: P&L ₹7,800 (target 80% of credit ₹+7,280)" in msg


def test_no_sl_near_alert_once_tsl_is_active(tmp_path, monkeypatch):
    sent, dbp, jp = _entry(tmp_path, monkeypatch)
    _set(dbp, tsl_activated=1)
    n = len(sent)
    _tick(sent, dbp, jp, {"K1": 36.0, "K2": 115.0}, minutes=5)
    assert len(sent) == n                                                                   # SL is at entry now: no ₹-1,300 alert


def test_settings_missing_never_breaks_the_periodic_line(tmp_path, monkeypatch):
    sent, dbp, jp = _entry(tmp_path, monkeypatch)

    def boom(b, s):
        raise RuntimeError("supabase down")
    PW.run_cycle("tok", now=T0 + pd.Timedelta(minutes=31), db_path=dbp, send=sent.append, jpath=jp, cfg=CFG,
                 ltp_fn=lambda tok, keys: {"K1": 40.0, "K2": 110.0}, settings_fn=boom)
    assert "⏱ P&L ₹0 · exits: dashboard settings unavailable" in sent[-1] and "-9,100" not in sent[-1]


# ------------------------------------------------------------------------------------------------ /positions
def test_positions_shows_real_exits_for_bots_and_stored_for_the_rest():
    bot = {"trade_id": "PAPER_1_ab12cd", "mode": "PAPER", "symbol": "NIFTY", "strategy": "BULL_PUT_SPREAD", "source": "srv2_momentum_reversal",
           "lots": 2, "lot_size": 65, "net_credit": 70.0, "sl_pnl_level": -9100.0, "target_pnl_level": 7280.0, "entry_spot_price": 25000.0,
           "entry_time": "2026-10-12 10:10:00", "tsl_activated": 1}
    shadow = {**bot, "trade_id": "PAPER_2_ef34gh", "source": "srv2_momentum_reversal_vision_shadow", "tsl_activated": 0}
    other = {"trade_id": "X_3_zz99yy", "mode": "PAPER", "symbol": "NIFTY", "strategy": "NAKED_CALL", "source": "manual_paper",
             "sl_pnl_level": -5000.0, "target_pnl_level": None, "entry_time": "2026-10-12 10:10:00"}
    keys = []

    def sfn(key, sym):
        keys.append(key)
        return SS2
    txt = PCMD.positions_text(lambda: [bot, shadow, other], settings_fn=sfn)
    rows = txt.split("\n")
    assert "TSL active ⇒ SL locked at entry (₹0)" in rows[1] and "target 80% of credit (₹+7,280)" in rows[1] and "-9,100" not in rows[1]
    assert "SL spot 24,962.5 or premium −10 pts (₹-1,300)" in rows[2]                         # vision shadow ⇒ parent's exits
    assert "SL ₹-5,000 · target —" in rows[3] and "target ₹0" not in txt                       # stored levels, never "₹0"
    assert keys == ["15m_dynamic_sr", "15m_dynamic_sr"]


def test_manual_sl_override_and_missing_level_follow_the_engine():
    """Engine: a manual SL override (₹) beats every branch (plus the stored target); no entry_level_price ⇒ generic stored levels."""
    t = {"source": "srv2_momentum_reversal", "strategy": "BULL_PUT_SPREAD", "lots": 2, "lot_size": 65, "net_credit": 70.0,
         "sl_pnl_level": -9100.0, "target_pnl_level": 7280.0, "entry_spot_price": 25000.0, "entry_level_price": 24990.0,
         "manual_sl_override_pnl": -2000.0}
    assert PW.exit_status_text(t, "srv2_momentum_reversal", SS2, -500.0) == "manual SL override ₹-2,000 पर्यंत ₹1,500 · target ₹+7,280 पर्यंत ₹7,780"
    assert PW.near_levels(t, "srv2_momentum_reversal", SS2)[0] == -2000.0
    assert PW.exit_bot({**t, "entry_level_price": None}) is None                              # generic branch ⇒ stored levels
    assert PW.exit_bot({k: v for k, v in t.items() if k != "entry_level_price"}) == "srv2_momentum_reversal"


# ------------------------------------------------------------------------------------------------ the display mirrors the engine
def test_display_mirrors_the_engine_branches():
    import inspect

    import trading_engine as TE
    src = inspect.getsource(TE.manage_open_trades)
    h, m = PW.SRV2_CARRY_CHECK
    assert f"(ist_now.hour, ist_now.minute) >= ({h}, {m})" in src                            # carry-forward check time
    assert 'current_pnl >= target_level' in src and 'exit_reason = "PREMIUM_TARGET"' in src  # srv2 spread target = stored level
    assert 'direction_bullish = strategy_name in ("BULL_PUT_SPREAD", "NAKED_CALL")' in src
    assert 'cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)' in src
    assert set(PW.ENGINE_SETTINGS_BOT) == {"dynamic_sr_instant", "classic_sr_reversal", "srv2_momentum_reversal"}
    assert all(f'exit_source == "{s}"' in src for s in PW.ENGINE_SETTINGS_BOT)
    wsrc = open(PW.__file__, encoding="utf-8").read() + open(PCMD.__file__, encoding="utf-8").read()
    assert "UPDATE live_trades" not in wsrc and "evaluate_point_spot_exit" not in wsrc     # display only
