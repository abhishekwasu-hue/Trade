"""
tests/test_database_overshoot.py
--------------------------------
database.get_sl_tsl_overshoot() — trading_engine.py च्या evaluate_point_spot_exit()/
manage_open_trades() ने आधीच exit_reason_detail मध्ये साठवलेल्या वाचनीय मजकुरातून (regex ने),
प्रत्येक SL/TSL exit threshold च्या किती "पुढे जाऊन" (overshoot) पकडला गेला हे बरोबर काढतो का —
वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("review slipages after trade monitor update", नंतर "yes").
प्रत्यक्ष VPS वरून बघितलेल्या exit_reason_detail मजकुरांवरच (शब्दशः) चाचण्या.
"""
import datetime
import json
import sqlite3
import tempfile

import pytest

import database


@pytest.fixture
def temp_db(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


def seed(tmpdb, trade_id, exit_time, exit_reason, exit_reason_detail, realized_pnl,
          symbol="NIFTY", mode="PAPER", entry_time=None):
    entry_time = entry_time or exit_time
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
           exit_reason_detail, realized_pnl, status, legs_json, mode, trading_style, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, exit_time[:10], symbol, "BULL_PUT_SPREAD", 1, 75, 20.0, 20.0, 500.0, 250.0, 500.0,
         entry_time, exit_time, exit_reason, exit_reason_detail, realized_pnl, "CLOSED", json.dumps([]),
         mode, "INTRADAY", "dynamic_sr_instant"),
    )
    conn.commit()
    conn.close()


class TestGetSlTslOvershoot:
    def test_tsl_breakeven_lock_overshoot(self, temp_db):
        seed(temp_db, "T1", "2026-09-23 09:57:53", "TSL_SL",
             "Trailing SL hit (locked to Entry/Breakeven) — Premium gain -1.7 points dropped to/below zero.",
             -5525.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["Basis"] == "TSL Breakeven (Premium pts)"
        assert row["Overshoot (pts)"] == pytest.approx(1.7)
        assert row["Overshoot (%)"] is None
        assert row["Overshoot (Rs)"] is None

    def test_tsl_premium_points_trail_overshoot(self, temp_db):
        seed(temp_db, "T2", "2026-09-23 10:00:00", "TSL_SL",
             "Trailing SL hit (Premium Points trail) — Peak premium gain 12.0 pts, trailing distance 5.0 "
             "pts -> floor 7.0 pts, now at 6.2 pts.",
             300.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        assert df.iloc[0]["Basis"] == "TSL Trail (Premium pts)"
        assert df.iloc[0]["Overshoot (pts)"] == pytest.approx(0.8)

    def test_sl_premium_points_only_overshoot(self, temp_db):
        seed(temp_db, "T3", "2026-09-22 13:54:12", "SL",
             "Stop-Loss hit via Premium points — loss -3.8 points reached/exceeded the -3.0-point threshold "
             "(Spot move still at -0.04%/-0.05%).",
             -12187.5)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["Basis"] == "SL (Premium pts)"
        assert row["Overshoot (pts)"] == pytest.approx(0.8)
        assert row["Overshoot (%)"] is None

    def test_sl_spot_pct_only_overshoot(self, temp_db):
        seed(temp_db, "T4", "2026-09-22 10:40:18", "SL",
             "Stop-Loss hit via Spot move — adverse move -0.08% reached/exceeded the -0.07% threshold "
             "(Premium loss still at -5.3/-10.0 points).",
             -3477.5)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["Basis"] == "SL (Spot %)"
        assert row["Overshoot (%)"] == pytest.approx(0.01, abs=1e-6)
        assert row["Overshoot (pts)"] is None

    def test_sl_both_spot_and_premium_simultaneously(self, temp_db):
        seed(temp_db, "T5", "2026-09-22 10:42:10", "SL",
             "Stop-Loss hit — both adverse Spot move -0.11% (threshold -0.05%) and Premium loss -7.3 "
             "points (threshold -3.0) reached simultaneously.",
             -23887.5)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["Basis"] == "SL (Spot %+Premium pts)"
        assert row["Overshoot (%)"] == pytest.approx(0.06, abs=1e-6)
        assert row["Overshoot (pts)"] == pytest.approx(4.3)

    def test_fixed_rs_based_trailing_sl_overshoot(self, temp_db):
        seed(temp_db, "T6", "2026-09-20 11:00:00", "TRAILING_SL",
             "Trailing SL — total P&L Rs -1,234 hit/crossed the (profit-adjusted) trailing SL level Rs -1,000.",
             -1234.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["Basis"] == "SL/TSL (Fixed Rs)"
        assert row["Overshoot (Rs)"] == pytest.approx(234.0)
        assert row["Overshoot (pts)"] is None

    def test_fixed_rs_based_plain_sl_overshoot(self, temp_db):
        seed(temp_db, "T7", "2026-09-20 11:05:00", "SL",
             "Stop-Loss — total P&L Rs -6,100 hit/crossed the fixed SL level Rs -6,000.",
             -6100.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert len(df) == 1
        assert df.iloc[0]["Basis"] == "SL/TSL (Fixed Rs)"
        assert df.iloc[0]["Overshoot (Rs)"] == pytest.approx(100.0)

    def test_target_exit_never_included(self, temp_db):
        """TARGET exits कधीच overshoot टेबलमध्ये येऊ नयेत (फक्त SL/TSL_SL/TRAILING_SL/PCT_TRAILING_SL)."""
        seed(temp_db, "T8", "2026-09-23 10:28:24", "TARGET",
             "Target hit via Spot move — 0.20% reached/exceeded the 0.2% threshold (Premium gain still at 27.1/30.0 points).",
             17615.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert df.empty

    def test_null_detail_excluded(self, temp_db):
        seed(temp_db, "T9", "2026-09-23 10:00:00", "SL", None, -100.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert df.empty

    def test_unparseable_detail_excluded_not_crashed(self, temp_db):
        """जुन्या (detail-format आधीच्या) किंवा अनपेक्षित मजकुराचे trades गप्प वगळले जावेत, क्रॅश नको."""
        seed(temp_db, "T10", "2026-09-23 10:00:00", "SL", "Some old unrelated free-text reason.", -100.0)
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert df.empty

    def test_mode_filter(self, temp_db):
        seed(temp_db, "L1", "2026-09-23 09:57:53", "TSL_SL",
             "Trailing SL hit (locked to Entry/Breakeven) — Premium gain -1.7 points dropped to/below zero.",
             -5525.0, mode="LIVE")
        seed(temp_db, "P1", "2026-09-23 10:00:00", "TSL_SL",
             "Trailing SL hit (locked to Entry/Breakeven) — Premium gain -0.2 points dropped to/below zero.",
             -130.0, mode="PAPER")
        df_live = database.get_sl_tsl_overshoot("NIFTY", mode_filter="LIVE")
        assert len(df_live) == 1
        assert df_live.iloc[0]["Trade ID"] == "L1"

    def test_date_range_filter(self, temp_db):
        seed(temp_db, "OLD", "2026-09-01 10:00:00", "SL",
             "Stop-Loss hit via Premium points — loss -3.8 points reached/exceeded the -3.0-point threshold "
             "(Spot move still at -0.04%/-0.05%).", -1000.0)
        seed(temp_db, "NEW", "2026-09-23 10:00:00", "SL",
             "Stop-Loss hit via Premium points — loss -3.8 points reached/exceeded the -3.0-point threshold "
             "(Spot move still at -0.04%/-0.05%).", -1000.0)
        df = database.get_sl_tsl_overshoot("NIFTY", start_date=datetime.date(2026, 9, 20), end_date=datetime.date(2026, 9, 30))
        assert len(df) == 1
        assert df.iloc[0]["Trade ID"] == "NEW"

    def test_empty_when_no_trades(self, temp_db):
        df = database.get_sl_tsl_overshoot("NIFTY")
        assert df.empty
        assert list(df.columns) == [
            "Trade ID", "Exit Time", "Exit Reason", "Basis", "Overshoot (pts)", "Overshoot (%)",
            "Overshoot (Rs)", "Realized P&L", "Mode",
        ]

    def test_symbol_isolation(self, temp_db):
        seed(temp_db, "N1", "2026-09-23 09:57:53", "TSL_SL",
             "Trailing SL hit (locked to Entry/Breakeven) — Premium gain -1.7 points dropped to/below zero.",
             -5525.0, symbol="NIFTY")
        seed(temp_db, "B1", "2026-09-23 09:57:53", "TSL_SL",
             "Trailing SL hit (locked to Entry/Breakeven) — Premium gain -2.0 points dropped to/below zero.",
             -6000.0, symbol="BANKNIFTY")
        df = database.get_sl_tsl_overshoot("BANKNIFTY")
        assert len(df) == 1
        assert df.iloc[0]["Trade ID"] == "B1"
