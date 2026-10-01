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
