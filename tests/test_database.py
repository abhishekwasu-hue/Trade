"""
tests/test_database.py
--------------------------------
Performance टॅबवरच्या नवीन "Entry+Exit कारण" Trade Log आणि rule-based शिफारशींचा आधार असलेल्या
database.py च्या query helpers साठी — खऱ्या तात्पुरत्या SQLite DB वर.
"""
import datetime
import json
import sqlite3
import tempfile

import pandas as pd
import pytest

import database


@pytest.fixture
def temp_db(monkeypatch):
    """प्रत्येक test साठी नवीन, स्वतंत्र तात्पुरता SQLite DB."""
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


def seed_closed_trade(tmpdb, trade_id, realized_pnl, exit_reason, exit_date, symbol="NIFTY",
                       source="dynamic_sr_instant", entry_timeframe="15M", entry_level_price=23900.0,
                       strategy="BULL_PUT_SPREAD", mode="LIVE", exit_reason_detail=None):
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
           exit_reason_detail, realized_pnl, status, legs_json, mode, trading_style, source,
           entry_level_price, entry_timeframe) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, exit_date, symbol, strategy, 1, 75, 1000, 1000, 500, 250, 500,
         f"{exit_date} 10:00:00", f"{exit_date} 14:00:00", exit_reason, exit_reason_detail, realized_pnl,
         "CLOSED", json.dumps([]), mode, "INTRADAY", source, entry_level_price, entry_timeframe),
    )
    conn.commit()
    conn.close()


class TestGetClosedTradesDetail:
    def test_returns_entry_and_exit_columns(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-10")
        df = database.get_closed_trades_detail("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["source"] == "dynamic_sr_instant"
        assert row["entry_timeframe"] == "15M"
        assert row["exit_reason"] == "TARGET"
        assert row["Realized P&L"] == 500.0

    def test_date_range_filters_by_exit_date(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-01")
        seed_closed_trade(temp_db, "T2", -200.0, "SL", "2026-09-15")
        df = database.get_closed_trades_detail(
            "NIFTY", start_date=datetime.date(2026, 9, 10), end_date=datetime.date(2026, 9, 20),
        )
        assert len(df) == 1
        assert df.iloc[0]["Trade ID"] == "T2"

    def test_mode_filter(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-10", mode="LIVE")
        seed_closed_trade(temp_db, "T2", 300.0, "TARGET", "2026-09-10", mode="PAPER")
        df = database.get_closed_trades_detail("NIFTY", mode_filter="PAPER")
        assert len(df) == 1
        assert df.iloc[0]["Trade ID"] == "T2"

    def test_includes_exit_reason_detail(self, temp_db):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Performance Report PDF) — SL/Target नेमकं
        Spot% की Premium Points मुळे लागला, हे स्पष्ट करणारा exit_reason_detail column."""
        seed_closed_trade(
            temp_db, "T1", -200.0, "SL", "2026-09-10",
            exit_reason_detail="Stop-Loss hit via Premium points - loss -6.0 points reached/exceeded the -5-point threshold.",
        )
        seed_closed_trade(temp_db, "T2", 300.0, "EOD_SQUAREOFF", "2026-09-10")
        df = database.get_closed_trades_detail("NIFTY").sort_values("Trade ID").reset_index(drop=True)
        assert df.iloc[0]["exit_reason_detail"] == "Stop-Loss hit via Premium points - loss -6.0 points reached/exceeded the -5-point threshold."
        assert pd.isna(df.iloc[1]["exit_reason_detail"])


class TestGetExitReasonBreakdown:
    def test_groups_by_source_and_exit_reason(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-10", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T2", -200.0, "SL", "2026-09-11", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T3", 300.0, "TARGET", "2026-09-12", source="srv2_momentum_reversal")

        df = database.get_exit_reason_breakdown("NIFTY", "source")
        assert len(df) == 3
        instant_sl_row = df[(df["Group"] == "dynamic_sr_instant") & (df["Exit Reason"] == "SL")].iloc[0]
        assert instant_sl_row["Trades"] == 1
        assert instant_sl_row["Total P&L"] == -200.0

    def test_empty_when_no_trades(self, temp_db):
        df = database.get_exit_reason_breakdown("NIFTY", "source")
        assert df.empty


class TestGetTodaysLiveTotalPnlAndCount:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — सर्व symbols/sources मिळून आजचा एकूण LIVE P&L + trade count."""

    def test_sums_across_symbols_and_sources_live_only(self, temp_db):
        import config
        today_str = config.get_ist_today().strftime("%Y-%m-%d")
        seed_closed_trade(temp_db, "T1", -3000.0, "SL", today_str, symbol="NIFTY", source="dynamic_sr_instant", mode="LIVE")
        seed_closed_trade(temp_db, "T2", 500.0, "TARGET", today_str, symbol="BANKNIFTY", source="srv2_momentum_reversal", mode="LIVE")
        seed_closed_trade(temp_db, "T3", -100000.0, "SL", today_str, symbol="NIFTY", source="classic_sr_reversal", mode="PAPER")

        total_pnl, total_trades = database.get_todays_live_total_pnl_and_count()
        assert total_pnl == -2500.0
        assert total_trades == 2

    def test_ignores_other_days(self, temp_db):
        seed_closed_trade(temp_db, "T1", -3000.0, "SL", "2020-01-01", mode="LIVE")
        total_pnl, total_trades = database.get_todays_live_total_pnl_and_count()
        assert total_pnl == 0
        assert total_trades == 0

    def test_counts_open_live_trades_too_not_just_closed(self, temp_db):
        """PNL फक्त CLOSED वरून, पण trade-count मध्ये आजचे सर्व (OPEN सकट) LIVE trades मोजले जातात —
        get_todays_realized_pnl() सारखंच वर्तन (मर्यादा gaming टाळण्यासाठी, फक्त बंद झालेलेच नाही)."""
        import sqlite3
        import json
        import config
        today_str = config.get_ist_today().strftime("%Y-%m-%d")
        conn = sqlite3.connect(temp_db)
        conn.execute(
            """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
               max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json, mode,
               trading_style, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("T_OPEN", today_str, "NIFTY", "BULL_PUT_SPREAD", 1, 75, 1000, 1000, 500, 250, 500,
             f"{today_str} 10:00:00", "OPEN", json.dumps([]), "LIVE", "INTRADAY", "dynamic_sr_instant"),
        )
        conn.commit()
        conn.close()
        total_pnl, total_trades = database.get_todays_live_total_pnl_and_count()
        assert total_pnl == 0
        assert total_trades == 1

    def test_carried_forward_trade_counted_on_exit_day_not_entry_day(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — हे system मुद्दामच
        trades रात्रभर carry-forward करतं (3:10pm "अपुरा नफा" check). सोमवारी उघडलेली, मंगळवारी
        सकाळी मोठ्या तोट्यात बंद झालेली trade — मंगळवारच्याच (जेव्हा खरा तोटा realize झाला) kill-switch
        तपासणीत धरली जायलाच हवी, सोमवारच्या (entry-दिवसाच्या) नाही."""
        import sqlite3
        import json
        import datetime as dt
        conn = sqlite3.connect(temp_db)
        conn.execute(
            """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
               max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
               realized_pnl, status, legs_json, mode, trading_style, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("T_CARRY", "2026-09-15", "NIFTY", "BULL_PUT_SPREAD", 1, 75, 1000, 1000, 500, 250, 500,
             "2026-09-15 15:20:00", "2026-09-16 09:30:00", "SL", -40000.0,
             "CLOSED", json.dumps([]), "LIVE", "INTRADAY", "dynamic_sr_instant"),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 16))
        total_pnl, _ = database.get_todays_live_total_pnl_and_count()
        assert total_pnl == -40000.0  # exit दिवशी (16 तारखेला) धरलं जायलाच हवं

        monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 15))
        total_pnl_entry_day, _ = database.get_todays_live_total_pnl_and_count()
        assert total_pnl_entry_day == 0  # entry दिवशी (15 तारखेला) अजून बंदच झालेली नव्हती


class TestGetUnverifiedReconciledTradesTodayCount:
    """🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — reconcile_open_trades_with_broker()
    (trading_engine.py) externally बंद झालेल्या LIVE position चा realized_pnl कधीच साठवत नाही (ते
    function फक्त वाचतं) — त्यामुळे असे trades kill-switch च्या SUM मधून कायमचे वगळले जायचे."""

    def _seed(self, tmpdb, trade_id, exit_reason, realized_pnl, exit_date, mode="LIVE"):
        conn = sqlite3.connect(tmpdb)
        conn.execute(
            """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
               max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
               realized_pnl, status, legs_json, mode, trading_style, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (trade_id, exit_date, "NIFTY", "BULL_PUT_SPREAD", 1, 75, 1000, 1000, 500, 250, 500,
             f"{exit_date} 10:00:00", f"{exit_date} 11:00:00", exit_reason, realized_pnl,
             "CLOSED", json.dumps([]), mode, "INTRADAY", "dynamic_sr_instant"),
        )
        conn.commit()
        conn.close()

    def test_counts_reconciled_trades_with_null_pnl_today(self, temp_db, monkeypatch):
        import datetime as dt
        monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 16))
        self._seed(temp_db, "T1", "RECONCILED_EXTERNAL_CLOSE", None, "2026-09-16")
        assert database.get_unverified_reconciled_trades_today_count() == 1

    def test_ignores_reconciled_trades_with_known_pnl(self, temp_db, monkeypatch):
        """realized_pnl आधीच कुठल्यातरी मार्गाने भरलेला असेल (उदा. हाताने दुरुस्त केलेला), तर मोजू नये."""
        import datetime as dt
        monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 16))
        self._seed(temp_db, "T1", "RECONCILED_EXTERNAL_CLOSE", -5000.0, "2026-09-16")
        assert database.get_unverified_reconciled_trades_today_count() == 0

    def test_ignores_normal_null_free_closes(self, temp_db, monkeypatch):
        """सामान्य SL/Target/EOD exits ना नेहमीच realized_pnl असतो -- ते इथे कधीच मोजले जाऊ नयेत."""
        import datetime as dt
        monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 16))
        self._seed(temp_db, "T1", "SL", -1000.0, "2026-09-16")
        assert database.get_unverified_reconciled_trades_today_count() == 0

    def test_ignores_other_days(self, temp_db, monkeypatch):
        import datetime as dt
        monkeypatch.setattr(database, "get_ist_today", lambda: dt.date(2026, 9, 16))
        self._seed(temp_db, "T1", "RECONCILED_EXTERNAL_CLOSE", None, "2026-09-15")
        assert database.get_unverified_reconciled_trades_today_count() == 0


def seed_open_trade(tmpdb, trade_id, symbol, source, strategy="BULL_PUT_SPREAD"):
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json, mode,
           trading_style, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-09-19", symbol, strategy, 1, 75, 1000, 1000, 500, 250, 500,
         "2026-09-19 10:00:00", "OPEN", json.dumps([]), "LIVE", "INTRADAY", source),
    )
    conn.commit()
    conn.close()


class TestGetOpenTradesByOtherSources:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Cross-Strategy Conflict Check — फक्त अलर्ट, block नाही) —
    एकाच symbol वर, इतर strategies कडून सध्या OPEN असलेले trades शोधणे."""

    def test_finds_open_trades_from_other_sources(self, temp_db):
        seed_open_trade(temp_db, "T1", "NIFTY", "srv2_momentum_reversal", "BEAR_CALL_SPREAD")
        others = database.get_open_trades_by_other_sources("NIFTY", "dynamic_sr_instant")
        assert len(others) == 1
        assert others[0] == {"source": "srv2_momentum_reversal", "strategy": "BEAR_CALL_SPREAD", "trade_id": "T1"}

    def test_excludes_same_source(self, temp_db):
        seed_open_trade(temp_db, "T1", "NIFTY", "dynamic_sr_instant")
        others = database.get_open_trades_by_other_sources("NIFTY", "dynamic_sr_instant")
        assert others == []

    def test_excludes_other_symbols(self, temp_db):
        seed_open_trade(temp_db, "T1", "BANKNIFTY", "srv2_momentum_reversal")
        others = database.get_open_trades_by_other_sources("NIFTY", "dynamic_sr_instant")
        assert others == []

    def test_excludes_closed_trades(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-19", symbol="NIFTY", source="srv2_momentum_reversal")
        others = database.get_open_trades_by_other_sources("NIFTY", "dynamic_sr_instant")
        assert others == []

    def test_empty_when_no_other_trades(self, temp_db):
        assert database.get_open_trades_by_other_sources("NIFTY", "dynamic_sr_instant") == []


class TestRunAutoBackupIfDue:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Crash Recovery / DB Backup, महत्त्वाच्या
    🟠 यादीतला मुद्दा) — आधी हे फक्त shared_context.py (Dashboard उघडं असतानाच) मध्ये होतं, आता
    तिन्ही bots (VPS crontab) कडूनही वापरण्याजोगा एकच, सामायिक मार्ग."""

    def test_not_due_returns_false_without_touching_anything(self, monkeypatch):
        monkeypatch.setattr(database, "auto_backup_due", lambda interval_minutes: False)
        called = []
        monkeypatch.setattr(database, "get_db_backup_bytes", lambda: called.append(1))
        assert database.run_auto_backup_if_due() is False
        assert not called

    def test_due_but_no_bytes_returns_false(self, monkeypatch):
        monkeypatch.setattr(database, "auto_backup_due", lambda interval_minutes: True)
        monkeypatch.setattr(database, "get_db_backup_bytes", lambda: None)
        upload_called = []
        monkeypatch.setattr(database, "upload_to_google_drive", lambda *a, **k: upload_called.append(1))
        assert database.run_auto_backup_if_due() is False
        assert not upload_called

    def test_successful_upload_marks_done_and_returns_true(self, monkeypatch):
        monkeypatch.setattr(database, "auto_backup_due", lambda interval_minutes: True)
        monkeypatch.setattr(database, "get_db_backup_bytes", lambda: b"fake_db_bytes")
        monkeypatch.setattr(database, "upload_to_google_drive", lambda data, name, mime_type: (True, "https://drive/file"))
        marked = []
        monkeypatch.setattr(database, "mark_auto_backup_done", lambda: marked.append(1))
        assert database.run_auto_backup_if_due() is True
        assert marked

    def test_failed_upload_does_not_mark_done_returns_false(self, monkeypatch):
        monkeypatch.setattr(database, "auto_backup_due", lambda interval_minutes: True)
        monkeypatch.setattr(database, "get_db_backup_bytes", lambda: b"fake_db_bytes")
        monkeypatch.setattr(database, "upload_to_google_drive", lambda data, name, mime_type: (False, "Drive not configured"))
        marked = []
        monkeypatch.setattr(database, "mark_auto_backup_done", lambda: marked.append(1))
        assert database.run_auto_backup_if_due() is False
        assert not marked

    def test_exception_anywhere_returns_false_not_raises(self, monkeypatch):
        monkeypatch.setattr(database, "auto_backup_due", lambda interval_minutes: (_ for _ in ()).throw(Exception("boom")))
        assert database.run_auto_backup_if_due() is False

    def test_interval_minutes_passed_through(self, monkeypatch):
        captured = []
        monkeypatch.setattr(database, "auto_backup_due", lambda interval_minutes: captured.append(interval_minutes) or False)
        database.run_auto_backup_if_due(interval_minutes=30)
        assert captured == [30]


class TestGetPerformanceSummaryWinRateAndRoi:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Winning Rate — फक्त शुद्ध SL/Target, ROI — मार्जिन-आधारित)
    — प्रत्येक seed_closed_trade() ने max_loss=500, lots=1, lot_size=75 (एकसमान) वापरलं जातं, म्हणजे
    प्रत्येक trade ची मार्जिन नेहमी 500*1*75=37,500 — अचूक अपेक्षित आकडे हाताने काढता येतात."""

    def _seed_mixed_trades(self, tmpdb):
        # sl_target-counted (win_rate साठी मोजले जाणारे): T1 (TARGET, win), T2 (SL, loss)
        seed_closed_trade(tmpdb, "T1", 500.0, "TARGET", "2026-09-01")
        seed_closed_trade(tmpdb, "T2", -200.0, "SL", "2026-09-02")
        # excluded (Trailing SL/EOD) -- win_rate मध्ये कधीच मोजले जात नाहीत, पण win_rate_all_exits/
        # roi_pct/total_pnl मध्ये मात्र मोजले जातात (जुनं वर्तन + ROI संपूर्ण P&L वरच).
        seed_closed_trade(tmpdb, "T3", 100.0, "TRAILING_SL", "2026-09-03")
        seed_closed_trade(tmpdb, "T4", 100.0, "PCT_TRAILING_SL", "2026-09-04")
        seed_closed_trade(tmpdb, "T5", -100.0, "EOD_SQUAREOFF", "2026-09-05")

    def test_win_rate_counts_only_pure_sl_and_target(self, temp_db):
        self._seed_mixed_trades(temp_db)
        summary = database.get_performance_summary("NIFTY")
        assert summary["total_trades"] == 5
        assert summary["sl_target_trade_count"] == 2
        assert summary["win_rate"] == 50.0  # 1 win (T1) / 2 counted (T1,T2) -- T3/T4/T5 वगळलेले

    def test_win_rate_all_exits_kept_as_reference_and_differs_from_new(self, temp_db):
        """जुनं (सर्व closed trades, P&L-चिन्ह आधारित) win rate वेगळं (60%, कारण T3/T4 positive
        trailing trades धरतो) -- नवीन win_rate (50%) पेक्षा वेगळं, दोन्ही स्वतंत्रपणे
        बरोबर calculate होतायत हे सिद्ध करण्यासाठी (चुकून जुनाच फॉर्म्युला वापरला असता तर 60% आलं असतं)."""
        self._seed_mixed_trades(temp_db)
        summary = database.get_performance_summary("NIFTY")
        assert summary["win_rate"] == 50.0
        assert summary["win_rate_all_exits"] == 60.0  # wins: T1,T3,T4 (positive) / एकूण 5

    def test_win_rate_none_when_no_pure_sl_or_target_trades(self, temp_db):
        seed_closed_trade(temp_db, "T1", 100.0, "TRAILING_SL", "2026-09-01")
        seed_closed_trade(temp_db, "T2", -50.0, "EOD_SQUAREOFF", "2026-09-02")
        summary = database.get_performance_summary("NIFTY")
        assert summary["sl_target_trade_count"] == 0
        assert summary["win_rate"] is None
        assert summary["win_rate_all_exits"] is not None  # हे मात्र कधीच None नसतं (total_trades>0 असेल तोवर)

    def test_roi_pct_based_on_total_margin_used(self, temp_db):
        self._seed_mixed_trades(temp_db)
        summary = database.get_performance_summary("NIFTY")
        # margin/trade = 500(max_loss) * 1(lots) * 75(lot_size) = 37,500; 5 trades -> 187,500
        assert summary["margin_used"] == 187500.0
        # total_pnl = 500-200+100+100-100 = 400
        assert summary["total_pnl"] == 400.0
        assert summary["roi_pct"] == round(400.0 / 187500.0 * 100, 2)

    def test_roi_none_when_no_margin_data(self, temp_db):
        """max_loss/lots/lot_size उपलब्ध नसतील (जुनी, अपूर्ण नोंद) -- roi_pct None, crash नाही."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, entry_time, exit_time,
               exit_reason, realized_pnl, status, legs_json, mode, trading_style, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("T1", "2026-09-01", "NIFTY", "BULL_PUT_SPREAD", "2026-09-01 10:00:00", "2026-09-01 14:00:00",
             "TARGET", 500.0, "CLOSED", json.dumps([]), "LIVE", "INTRADAY", "dynamic_sr_instant"),
        )
        conn.commit()
        conn.close()
        summary = database.get_performance_summary("NIFTY")
        assert summary["margin_used"] == 0
        assert summary["roi_pct"] is None


class TestGetPerformanceByGroupWinRateAndRoi:
    def test_group_win_rate_and_roi_computed_per_group(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-01", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T2", -200.0, "SL", "2026-09-02", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T3", 100.0, "TRAILING_SL", "2026-09-03", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T4", 300.0, "TARGET", "2026-09-04", source="srv2_momentum_reversal")

        df = database.get_performance_by_group("NIFTY", "source")
        assert set(df["Group"]) == {"dynamic_sr_instant", "srv2_momentum_reversal"}

        dsr_row = df[df["Group"] == "dynamic_sr_instant"].iloc[0]
        assert dsr_row["SL/Target Trades"] == 2  # T1,T2 (T3 trailing वगळलेला)
        assert dsr_row["Win Rate %"] == 50.0
        assert dsr_row["Win Rate % (All Exits)"] == round(2 / 3 * 100, 1)  # T1,T3 positive / 3 एकूण

        srv2_row = df[df["Group"] == "srv2_momentum_reversal"].iloc[0]
        assert srv2_row["Win Rate %"] == 100.0  # फक्त T4 (TARGET, win)
        assert srv2_row["ROI %"] == round(300.0 / 37500.0 * 100, 2)

    def test_group_win_rate_none_for_group_with_no_sl_target_trades(self, temp_db):
        """एका group चा Win Rate % None असेल आणि दुसऱ्या group चा numeric value असेल, तर
        pandas None ला आपोआप float NaN मध्ये रूपांतरित करतो (एकाच स्तंभात None + numeric
        mixed असेल तरच — एकट्या row मध्ये हे घडत नाही, म्हणून इथे मुद्दाम 2 वेगळे groups
        seed केले आहेत). caller (page_performance.py) ने pd.isna()/pd.notna() वापरायलाच हवं,
        plain "is None" नाही."""
        seed_closed_trade(temp_db, "T1", 100.0, "TRAILING_SL", "2026-09-01", source="dynamic_sr_instant")
        seed_closed_trade(temp_db, "T2", 500.0, "TARGET", "2026-09-02", source="srv2_momentum_reversal")
        df = database.get_performance_by_group("NIFTY", "source")

        dsr_row = df[df["Group"] == "dynamic_sr_instant"].iloc[0]
        assert dsr_row["SL/Target Trades"] == 0
        assert pd.isna(dsr_row["Win Rate %"])  # Python मध्ये None होता, pandas coercion मुळे आता NaN

        srv2_row = df[df["Group"] == "srv2_momentum_reversal"].iloc[0]
        assert srv2_row["Win Rate %"] == 100.0  # हा group मात्र नेहमीप्रमाणेच numeric


class TestGetPerformanceByTwoGroups:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("strategy आणि timeframe दोन्ही एकत्र दाखवणारं वेगळं टेबल")."""

    def test_groups_by_both_columns_combined(self, temp_db):
        seed_closed_trade(temp_db, "T1", 500.0, "TARGET", "2026-09-01", source="dynamic_sr_instant", entry_timeframe="1M")
        seed_closed_trade(temp_db, "T2", 300.0, "TARGET", "2026-09-02", source="dynamic_sr_instant", entry_timeframe="5M")
        seed_closed_trade(temp_db, "T3", -100.0, "SL", "2026-09-03", source="dynamic_sr_instant", entry_timeframe="1M")

        df = database.get_performance_by_two_groups("NIFTY", "source", "entry_timeframe")
        assert len(df) == 2  # (dynamic_sr_instant,1M) आणि (dynamic_sr_instant,5M) -- वेगळ्या ओळी

        combo_1m = df[(df["Strategy"] == "dynamic_sr_instant") & (df["Timeframe"] == "1M")].iloc[0]
        assert combo_1m["Trades"] == 2  # T1,T3
        assert combo_1m["Total P&L"] == 400.0  # 500-100
        assert combo_1m["Win Rate %"] == 50.0  # T1 win / (T1,T3) दोन्ही SL/Target-counted

        combo_5m = df[(df["Strategy"] == "dynamic_sr_instant") & (df["Timeframe"] == "5M")].iloc[0]
        assert combo_5m["Trades"] == 1
        assert combo_5m["Win Rate %"] == 100.0

    def test_empty_when_no_trades(self, temp_db):
        assert database.get_performance_by_two_groups("NIFTY", "source", "entry_timeframe").empty
