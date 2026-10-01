"""
tests/test_kill_switch_paper_margin.py
--------------------------------------
"Kill switch ne trade band kele nahi" (आजचा PAPER तोटा ₹-45,061, Kill Switch 'OK — LIVE P&L ₹0') —
(१) PAPER P&L (shadow वगळून) मोजला जातो, प्रत्येक mode स्वतंत्र; (२) % चा आधार "trade साठी वापरलेला margin";
(३) "Paper MTM मध्ये shadow trade चा P&L include दिसतो, असे नको" — get_todays_realized_pnl() शॅडो वगळतं.
"""
import json
import sqlite3

import pytest

import cloud_db
import database
import trading_engine
from tests.test_database import seed_closed_trade, temp_db  # noqa: F401  (temp_db fixture)

TODAY = "2026-09-30"


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    import datetime as dt
    monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 30))


def _seed_open(tmpdb, trade_id, mode="PAPER", source="dynamic_sr_instant", entry_margin=None):
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit, max_profit,
           max_loss, entry_time, status, legs_json, mode, trading_style, source, entry_margin_required)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, TODAY, "NIFTY", "BULL_PUT_SPREAD", 1, 75, 10, 1000, 500, f"{TODAY} 11:00:00", "OPEN",
         json.dumps([]), mode, "INTRADAY", source, entry_margin),
    )
    conn.commit()
    conn.close()


class TestRealizedPnlExcludesShadow:
    def test_paper_realized_pnl_excludes_shadow_trades(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "MAIN", -100.0, "SL", TODAY, mode="PAPER")
        seed_closed_trade(temp_db, "SH1", -5000.0, "SL", TODAY, mode="PAPER", source="dynamic_sr_instant_otm_shadow")
        seed_closed_trade(temp_db, "SH2", -700.0, "SL", TODAY, mode="PAPER", source="dynamic_sr_instant_min_hold_shadow")
        pnl, count = database.get_todays_realized_pnl("NIFTY", "PAPER")
        assert pnl == -100.0
        assert count == 1

    def test_live_unaffected(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "L1", 300.0, "TARGET", TODAY, mode="LIVE")
        assert database.get_todays_realized_pnl("NIFTY", "LIVE")[0] == 300.0


class TestPnlForMode:
    def test_modes_are_separate_and_shadow_excluded(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "L1", 300.0, "TARGET", TODAY, mode="LIVE")
        seed_closed_trade(temp_db, "P1", -800.0, "SL", TODAY, mode="PAPER")
        seed_closed_trade(temp_db, "S1", -9000.0, "SL", TODAY, mode="PAPER", source="dynamic_sr_instant_otm_shadow")
        assert database.get_todays_pnl_for_mode("LIVE") == 300.0
        assert database.get_todays_pnl_for_mode("PAPER") == -800.0

    def test_other_days_ignored(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "Y1", -800.0, "SL", "2026-09-29", mode="PAPER")
        assert database.get_todays_pnl_for_mode("PAPER") == 0.0


class TestPeakMarginUsed:
    def test_empty_is_zero(self, temp_db):  # noqa: F811
        assert database.get_todays_peak_margin_used("PAPER") == 0.0

    def test_overlapping_trades_add_up(self, temp_db):  # noqa: F811
        # दोन्ही 10:00-14:00 -> एकाच वेळी उघडे -> max_loss 500 * 1 lot * 75 = 37,500 प्रत्येकी -> 75,000
        seed_closed_trade(temp_db, "A", -100.0, "SL", TODAY, mode="PAPER")
        seed_closed_trade(temp_db, "B", -100.0, "SL", TODAY, mode="PAPER")
        assert database.get_todays_peak_margin_used("PAPER") == 75000.0

    def test_sequential_trades_reuse_capital(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "A", -100.0, "SL", TODAY, mode="PAPER", exit_time=f"{TODAY} 11:00:00")
        conn = sqlite3.connect(temp_db)
        conn.execute("UPDATE live_trades SET entry_time=? WHERE trade_id='A'", (f"{TODAY} 10:00:00",))
        conn.commit()
        conn.close()
        seed_closed_trade(temp_db, "B", -100.0, "SL", TODAY, mode="PAPER", exit_time=f"{TODAY} 14:00:00")
        conn = sqlite3.connect(temp_db)
        conn.execute("UPDATE live_trades SET entry_time=? WHERE trade_id='B'", (f"{TODAY} 12:00:00",))
        conn.commit()
        conn.close()
        assert database.get_todays_peak_margin_used("PAPER") == 37500.0

    def test_open_trade_is_counted_with_real_margin(self, temp_db):  # noqa: F811
        _seed_open(temp_db, "OPEN1", entry_margin=400000.0)
        assert database.get_todays_peak_margin_used("PAPER") == 400000.0

    def test_shadow_and_other_mode_excluded(self, temp_db):  # noqa: F811
        _seed_open(temp_db, "SH", source="dynamic_sr_instant_otm_shadow", entry_margin=900000.0)
        _seed_open(temp_db, "LV", mode="LIVE", entry_margin=700000.0)
        assert database.get_todays_peak_margin_used("PAPER") == 0.0
        assert database.get_todays_peak_margin_used("LIVE") == 700000.0


class TestCheckKillSwitchPaperAndMargin:
    UPSTOX_CAPITAL = 97_400.0

    def _setup(self, monkeypatch, *, live=(0.0, 0), paper_pnl=0.0, live_margin=0.0, paper_margin=0.0, **settings):
        base = {"enabled": True, "max_daily_loss_pct": 1.5, "max_daily_profit_pct": 3.0, "max_trades_per_day": 8,
                "count_paper_pnl": True, "capital_from_margin_used": True, "min_capital_floor": 0.0}
        base.update(settings)
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: base)
        monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *a, **k: "tok")
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: self.UPSTOX_CAPITAL)
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 0)
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: live)
        monkeypatch.setattr(trading_engine, "get_todays_live_peak_pnl", lambda: 0.0)
        monkeypatch.setattr(trading_engine, "get_todays_pnl_for_mode", lambda mode: paper_pnl if mode == "PAPER" else live[0])
        monkeypatch.setattr(trading_engine, "get_todays_peak_margin_used", lambda mode: paper_margin if mode == "PAPER" else live_margin)

    def test_reported_scenario_paper_loss_over_margin_limit_trips(self, monkeypatch):
        # ₹-45,061 PAPER तोटा, वापरलेला margin ₹23,00,000 -> 1.5% = ₹34,500 -> ट्रिप
        self._setup(monkeypatch, paper_pnl=-45061.0, paper_margin=2_300_000.0)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False
        assert "KILL_SWITCH_DAILY_LOSS_PAPER" in reason
        assert "2,300,000" in reason or "23,00,000" in reason

    def test_paper_loss_under_limit_is_ok(self, monkeypatch):
        self._setup(monkeypatch, paper_pnl=-30000.0, paper_margin=2_300_000.0)  # मर्यादा ₹34,500
        assert trading_engine.check_kill_switch() == (True, None)

    def test_paper_not_counted_when_setting_off(self, monkeypatch):
        self._setup(monkeypatch, paper_pnl=-45061.0, paper_margin=2_300_000.0, count_paper_pnl=False)
        assert trading_engine.check_kill_switch() == (True, None)

    def test_paper_profit_target_trips(self, monkeypatch):
        self._setup(monkeypatch, paper_pnl=80000.0, paper_margin=2_300_000.0)  # 3% = ₹69,000
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False and "PROFIT_TARGET_PAPER" in reason

    def test_floor_raises_a_too_small_margin_base(self, monkeypatch):
        # margin फक्त ₹4,00,000 (मर्यादा ₹6,000) -> तोटा ₹10,000 ट्रिप; floor ₹23,00,000 असेल तर मर्यादा ₹34,500 -> OK
        self._setup(monkeypatch, paper_pnl=-10000.0, paper_margin=400_000.0)
        assert trading_engine.check_kill_switch()[0] is False
        self._setup(monkeypatch, paper_pnl=-10000.0, paper_margin=400_000.0, min_capital_floor=2_300_000.0)
        assert trading_engine.check_kill_switch() == (True, None)

    def test_margin_basis_off_uses_upstox_capital(self, monkeypatch):
        # Upstox भांडवल ₹97,400 -> 1.5% = ₹1,461; PAPER तोटा ₹2,000 -> ट्रिप
        self._setup(monkeypatch, paper_pnl=-2000.0, paper_margin=2_300_000.0, capital_from_margin_used=False)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False and "एकूण capital" in reason

    def test_zero_margin_falls_back_to_upstox_capital(self, monkeypatch):
        # आज अजून margin नाही (0) -> Upstox भांडवलाचा आधार; कुठलाही तोटा नसेल तर OK, अकारण ट्रिप नाही
        self._setup(monkeypatch)
        assert trading_engine.check_kill_switch() == (True, None)

    def test_live_loss_uses_live_margin(self, monkeypatch):
        self._setup(monkeypatch, live=(-20000.0, 1), live_margin=1_000_000.0)  # 1.5% = ₹15,000
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False and "KILL_SWITCH_DAILY_LOSS" in reason and "PAPER" not in reason

    def test_paper_check_skipped_when_no_base_available(self, monkeypatch):
        # LIVE चा margin आहे (आधार मिळाला), PAPER margin 0 आणि Upstox भांडवल अज्ञात -> PAPER साठी 'भांडवल अज्ञात'
        # म्हणून थांबवत नाही (PAPER तपासणी वगळली जाते), पण LIVE साठी तसं असतं तर थांबवलं असतं.
        self._setup(monkeypatch, paper_pnl=-500.0, paper_margin=0.0, live_margin=1_000_000.0)
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: None)
        assert trading_engine.check_kill_switch() == (True, None)

    def test_live_capital_unknown_still_blocks_fail_safe(self, monkeypatch):
        self._setup(monkeypatch)  # LIVE margin 0 -> Upstox भांडवल लागतं
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: None)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False and "KILL_SWITCH_CAPITAL_UNKNOWN" in reason


class TestPaperParityOfRemainingGates:
    """🎓 "Kill switch paper trade la pn asawe adhich sangitle hote" — Profit-Lock, कमाल दैनिक ट्रेड्स, MCX Kill Switch आणि
    Portfolio Open-Risk Cap सुद्धा PAPER (shadow वगळून) साठी, LIVE सारखेच."""

    # ---- DB helpers
    def test_trade_count_for_mode_excludes_shadow_and_other_mode(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "P1", -10.0, "SL", TODAY, mode="PAPER")
        seed_closed_trade(temp_db, "P2", -10.0, "SL", TODAY, mode="PAPER")
        seed_closed_trade(temp_db, "SH", -10.0, "SL", TODAY, mode="PAPER", source="dynamic_sr_instant_otm_shadow")
        seed_closed_trade(temp_db, "L1", -10.0, "SL", TODAY, mode="LIVE")
        assert database.get_todays_trade_count_for_mode("PAPER") == 2
        assert database.get_todays_trade_count_for_mode("LIVE") == 1

    def test_peak_pnl_for_mode(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "P1", 1000.0, "TARGET", TODAY, mode="PAPER", exit_time=f"{TODAY} 10:30:00")
        seed_closed_trade(temp_db, "P2", -600.0, "SL", TODAY, mode="PAPER", exit_time=f"{TODAY} 11:30:00")
        seed_closed_trade(temp_db, "SH", 9000.0, "TARGET", TODAY, mode="PAPER", source="dynamic_sr_instant_otm_shadow",
                          exit_time=f"{TODAY} 12:00:00")
        assert database.get_todays_peak_pnl_for_mode("PAPER") == 1000.0  # शॅडोचे ₹9,000 नाहीत
        assert database.get_todays_peak_pnl_for_mode("LIVE") == 0.0

    def test_live_peak_unchanged(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "L1", 700.0, "TARGET", TODAY, mode="LIVE", exit_time=f"{TODAY} 10:30:00")
        seed_closed_trade(temp_db, "P1", 5000.0, "TARGET", TODAY, mode="PAPER", exit_time=f"{TODAY} 10:40:00")
        assert database.get_todays_live_peak_pnl() == 700.0

    def test_mcx_pnl_and_count_for_mode(self, temp_db):  # noqa: F811
        seed_closed_trade(temp_db, "M1", -500.0, "SL", TODAY, mode="PAPER", source="mcx_futures", symbol="CRUDEOIL")
        seed_closed_trade(temp_db, "M2", -300.0, "SL", TODAY, mode="LIVE", source="mcx_futures", symbol="CRUDEOIL")
        _seed_open(temp_db, "MO", mode="PAPER", source="mcx_futures")
        pnl, open_n = database.get_todays_mcx_pnl_and_count_for_mode("PAPER")
        assert pnl == -500.0 and open_n == 1
        assert database.get_todays_mcx_pnl_and_count_for_mode("LIVE") == (-300.0, 0)

    def test_open_max_loss_total_is_mode_aware(self, temp_db):  # noqa: F811
        _seed_open(temp_db, "PO", mode="PAPER")
        _seed_open(temp_db, "LO", mode="LIVE")
        _seed_open(temp_db, "SHO", mode="PAPER", source="dynamic_sr_instant_otm_shadow")
        syms = ("NIFTY", "BANKNIFTY", "SENSEX")
        # प्रत्येकी max_loss 500 * 1 * 75 = 37,500
        assert database.get_open_live_max_loss_total(symbols=syms) == 37500.0  # LIVE (जुनं वर्तन)
        assert database.get_open_live_max_loss_total(symbols=syms, mode="PAPER") == 37500.0  # शॅडो वगळून

    # ---- global kill switch
    def _ks(self, monkeypatch, **kw):
        base = {"enabled": True, "max_daily_loss_pct": 1.5, "max_daily_profit_pct": 3.0, "max_trades_per_day": 3,
                "count_paper_pnl": True, "capital_from_margin_used": True, "min_capital_floor": 0.0,
                "profit_lock_enabled": True, "profit_lock_pct": 50.0}
        base.update(kw.pop("settings", {}))
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: base)
        monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *a, **k: "tok")
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: 1_000_000.0)
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 0)
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: (0.0, 0))
        monkeypatch.setattr(trading_engine, "get_todays_live_peak_pnl", lambda: 0.0)
        monkeypatch.setattr(trading_engine, "get_todays_peak_margin_used", lambda mode: 0.0)
        monkeypatch.setattr(trading_engine, "get_todays_pnl_for_mode", lambda mode: kw.get("paper_pnl", 0.0) if mode == "PAPER" else 0.0)
        monkeypatch.setattr(trading_engine, "get_todays_peak_pnl_for_mode", lambda mode, mcx_only=False: kw.get("paper_peak", 0.0))
        monkeypatch.setattr(trading_engine, "get_todays_trade_count_for_mode", lambda mode: kw.get("paper_trades", 0))

    def test_paper_profit_lock_trips(self, monkeypatch):
        # PAPER चा peak ₹10,000 झाला होता, आता फक्त ₹3,000 -> 50% floor ₹5,000 खाली -> ट्रिप
        self._ks(monkeypatch, paper_pnl=3000.0, paper_peak=10000.0)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False and "PROFIT_LOCK_PAPER" in reason

    def test_paper_profit_lock_ok_when_above_floor(self, monkeypatch):
        self._ks(monkeypatch, paper_pnl=6000.0, paper_peak=10000.0)
        assert trading_engine.check_kill_switch() == (True, None)

    def test_paper_profit_lock_off_when_disabled(self, monkeypatch):
        self._ks(monkeypatch, paper_pnl=3000.0, paper_peak=10000.0, settings={"profit_lock_enabled": False})
        assert trading_engine.check_kill_switch() == (True, None)

    def test_paper_max_trades_trips(self, monkeypatch):
        self._ks(monkeypatch, paper_trades=3)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False and "MAX_TRADES_PAPER" in reason

    def test_paper_max_trades_not_counted_when_setting_off(self, monkeypatch):
        self._ks(monkeypatch, paper_trades=50, settings={"count_paper_pnl": False})
        assert trading_engine.check_kill_switch() == (True, None)

    # ---- MCX kill switch
    def _mcx(self, monkeypatch, live=(0.0, 0), paper=(0.0, 0), count_paper=True, lock=False, paper_peak=0.0):
        monkeypatch.setattr(cloud_db, "get_mcx_kill_switch_settings", lambda: {
            "enabled": True, "max_daily_loss_pct": 1.0, "max_open_positions": 2,
            "profit_lock_enabled": lock, "profit_lock_pct": 50.0})
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: {"count_paper_pnl": count_paper})
        monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *a, **k: "tok")
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: 1_000_000.0)  # 1% = ₹10,000
        monkeypatch.setattr(trading_engine, "get_todays_mcx_live_pnl_and_count", lambda: live)
        monkeypatch.setattr(trading_engine, "get_todays_mcx_live_peak_pnl", lambda: 0.0)
        monkeypatch.setattr(trading_engine, "get_todays_mcx_pnl_and_count_for_mode", lambda mode: paper)
        monkeypatch.setattr(trading_engine, "get_todays_peak_pnl_for_mode", lambda mode, mcx_only=False: paper_peak)

    def test_mcx_paper_loss_trips(self, monkeypatch):
        self._mcx(monkeypatch, paper=(-12000.0, 0))
        ok, reason = trading_engine.check_mcx_kill_switch()
        assert ok is False and "DAILY_LOSS" in reason and "PAPER" in reason

    def test_mcx_paper_open_positions_trips(self, monkeypatch):
        self._mcx(monkeypatch, paper=(0.0, 2))
        ok, reason = trading_engine.check_mcx_kill_switch()
        assert ok is False and "MAX_OPEN_POSITIONS" in reason and "PAPER" in reason

    def test_mcx_paper_ignored_when_setting_off(self, monkeypatch):
        self._mcx(monkeypatch, paper=(-12000.0, 5), count_paper=False)
        assert trading_engine.check_mcx_kill_switch() == (True, None)

    def test_mcx_paper_profit_lock_trips(self, monkeypatch):
        self._mcx(monkeypatch, paper=(2000.0, 0), lock=True, paper_peak=10000.0)
        ok, reason = trading_engine.check_mcx_kill_switch()
        assert ok is False and "PROFIT_LOCK" in reason and "PAPER" in reason

    def test_mcx_live_message_unchanged(self, monkeypatch):
        self._mcx(monkeypatch, live=(-12000.0, 0))
        ok, reason = trading_engine.check_mcx_kill_switch()
        assert ok is False and "MCX LIVE तोटा" in reason

    # ---- portfolio cap
    def test_portfolio_cap_uses_mode_specific_open_risk(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_portfolio_risk_cap_settings", lambda: {"enabled": True, "max_portfolio_risk_pct_index": 6.0})
        monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *a, **k: "tok")
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: 1_000_000.0)  # cap = ₹60,000
        seen = {}

        def _open(**kw):
            seen.update(kw)
            return 55000.0 if kw.get("mode") == "PAPER" else 0.0

        monkeypatch.setattr(trading_engine, "get_open_live_max_loss_total", _open)
        ok_paper, reason = trading_engine.check_portfolio_risk_cap("NIFTY", "dynamic_sr_instant", 10000, trading_mode="PAPER")
        assert ok_paper is False and "PAPER positions" in reason and seen["mode"] == "PAPER"
        ok_live, _ = trading_engine.check_portfolio_risk_cap("NIFTY", "dynamic_sr_instant", 10000)
        assert ok_live is True  # LIVE exposure 0 (जुनं वर्तन: डीफॉल्ट mode LIVE)


class TestPaperEntryIsActuallyBlocked:
    """प्रत्यक्ष entry मार्ग (open_multi_leg_trade) — असली DB मधला PAPER तोटा/margin वापरून; नवीन PAPER trade अडतो आणि
    कुठलीही order (PAPER सिम्युलेशनसुद्धा) पाठवली जात नाही."""

    STRATEGY = {"strategy": "BULL_PUT_SPREAD", "net_credit": 30.0, "max_loss": 70.0, "max_profit": 30.0,
                "short_leg": {"strike": 23900, "instrument_key": "PE1", "ltp": 120.0, "option_type": "PE", "expiry": "2026-10-06"},
                "long_leg": {"strike": 23750, "instrument_key": "PE2", "ltp": 90.0, "option_type": "PE", "expiry": "2026-10-06"}}

    def _env(self, monkeypatch, temp_db, **ks):  # noqa: F811
        settings = {"enabled": True, "max_daily_loss_pct": 1.5, "max_daily_profit_pct": 3.0, "max_trades_per_day": 50,
                    "count_paper_pnl": True, "capital_from_margin_used": True, "min_capital_floor": 0.0,
                    "profit_lock_enabled": False, "profit_lock_pct": 50.0}
        settings.update(ks)
        # trading_engine स्वतःचा `DB_PATH` (config वरून) वापरतो — temp DB कडे वळवला नाही तर test खऱ्या DB मध्ये OPEN
        # trade टाकून बाकी tests बिघडवतो (हेच आधी झालं होतं).
        monkeypatch.setattr(trading_engine, "DB_PATH", temp_db)
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: settings)
        monkeypatch.setattr(cloud_db, "get_trading_pause_settings", lambda: {"paused": False})
        monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *a, **k: "tok")
        monkeypatch.setattr(trading_engine, "get_total_capital", lambda t: 97400.0)
        monkeypatch.setattr(trading_engine, "check_vix_spike_halt", lambda *a, **k: (True, None))
        monkeypatch.setattr(trading_engine, "check_portfolio_risk_cap", lambda *a, **k: (True, None))
        monkeypatch.setattr(trading_engine, "_resolve_required_margin", lambda *a, **k: None)  # खरा Upstox कॉल नको
        calls = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda *a, **k: calls.append(a) or (200, {"status": "success"}))
        return calls

    def test_paper_entry_blocked_when_paper_loss_exceeds_margin_based_limit(self, monkeypatch, temp_db):  # noqa: F811
        calls = self._env(monkeypatch, temp_db)
        # आजचे बंद PAPER trades: एकूण ₹-45,000; margin (entry_margin_required) ₹23,00,000 -> 1.5% = ₹34,500
        for i in range(3):
            seed_closed_trade(temp_db, f"P{i}", -15000.0, "SL", TODAY, mode="PAPER")
        conn = sqlite3.connect(temp_db)
        conn.execute("UPDATE live_trades SET entry_margin_required=2300000.0 WHERE trade_id='P0'")
        conn.commit()
        conn.close()
        ok, resp = trading_engine.open_multi_leg_trade(
            "tok", "NIFTY", dict(self.STRATEGY), 1, 75, 100.0, 80.0, "I", trading_mode="PAPER", source="dynamic_sr_instant")
        assert ok is False
        assert "KILL_SWITCH_DAILY_LOSS_PAPER" in resp["reason"]
        assert calls == []  # कुठलीही order गेली नाही

    def test_shadow_loss_alone_does_not_block_paper_entry(self, monkeypatch, temp_db):  # noqa: F811
        calls = self._env(monkeypatch, temp_db)
        for i in range(3):
            seed_closed_trade(temp_db, f"S{i}", -50000.0, "SL", TODAY, mode="PAPER", source="dynamic_sr_instant_otm_shadow")
        trading_engine.open_multi_leg_trade(
            "tok", "NIFTY", dict(self.STRATEGY), 1, 75, 100.0, 80.0, "I", trading_mode="PAPER", source="dynamic_sr_instant")
        assert len(calls) == 1  # शॅडो तोट्यामुळे Kill Switch लागला नाही -> PAPER order (सिम्युलेशन) गेली
