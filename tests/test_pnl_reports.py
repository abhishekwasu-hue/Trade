"""
tests/test_pnl_reports.py
--------------------------------
pnl_reports.generate_pnl_report() — charges.py चं (🎓 "Upstox brokerage calculator वापरून actual
brokerage काढा" नंतर) Upstox-अचूक brokerage+STT+Exchange+SEBI+Stamp+GST breakdown "charges_breakdown"
totals मधून वापरकर्त्यापर्यंत (page_performance.py) योग्यपणे पोचतं का, याची पडताळणी.
"""
import datetime
import json
import sqlite3
import tempfile

import pytest

import database
import pnl_reports


@pytest.fixture
def temp_db(monkeypatch):
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    yield tmpdb


def _seed_closed_trade(tmpdb, trade_id, realized_pnl, exit_date, symbol="NIFTY"):
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, exit_time, exit_reason,
           realized_pnl, status, legs_json, mode, trading_style, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, exit_date, symbol, "BULL_PUT_SPREAD", 1, 75, 1000, 1000, 500, 250, 500,
         f"{exit_date} 10:00:00", f"{exit_date} 14:00:00", "TARGET", realized_pnl, "CLOSED",
         json.dumps([]), "LIVE", "INTRADAY", "dynamic_sr_instant"),
    )
    conn.commit()
    conn.close()


def _seed_order(tmpdb, order_id, trade_id, placed_at, transaction_type, quantity=75, fill_price=100.0, symbol="NIFTY"):
    conn = sqlite3.connect(tmpdb)
    conn.execute(
        """INSERT INTO order_log (order_id, trade_id, symbol, mode, transaction_type, quantity, price,
           status, placed_at, fill_price) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (order_id, trade_id, symbol, "LIVE", transaction_type, quantity, 0.0, "COMPLETE", placed_at, fill_price),
    )
    conn.commit()
    conn.close()


class TestGeneratePnlReportChargesBreakdown:
    def test_breakdown_present_and_matches_total_charges(self, temp_db):
        """symbol="NIFTY" (options segment) + quantity/fill_price/transaction_type सर्व उपलब्ध —
        त्यामुळे आता Upstox-अचूक दर लागतात (जुना सरसकट ₹25/ऑर्डर अंदाज नाही): SELL लेग (O1, qty=75,
        price=100 -> turnover=7500) वर STT+Exchange+SEBI+GST, BUY लेग (O2) वर Stamp Duty+Exchange+
        SEBI+GST — brokerage दोन्हीकडे फ्लॅट ₹20/executed order (options)."""
        _seed_closed_trade(temp_db, "T1", 500.0, "2026-09-10")
        _seed_order(temp_db, "O1", "T1", "2026-09-10 10:00:00", "SELL")
        _seed_order(temp_db, "O2", "T1", "2026-09-10 14:00:00", "BUY")

        report_df, totals = pnl_reports.generate_pnl_report(
            "NIFTY", "Daily", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30),
        )

        assert totals["total_orders"] == 2
        breakdown = totals["charges_breakdown"]
        assert breakdown  # non-empty
        assert set(breakdown.keys()) == {"brokerage", "stt", "exchange_txn", "sebi_fee", "stamp_duty", "gst"}
        turnover = 75 * 100.0  # प्रत्येक लेग
        assert breakdown["brokerage"] == pytest.approx(2 * 20.0)  # दोन्ही लेग — फ्लॅट ₹20/order (options)
        assert breakdown["stt"] == pytest.approx(turnover * 0.001)  # फक्त SELL लेगवर (O1)
        assert breakdown["stamp_duty"] == pytest.approx(turnover * 0.00003, abs=0.01)  # फक्त BUY लेगवर (O2) — summary 2-दशांश-स्थळी round होतो
        assert breakdown["exchange_txn"] == pytest.approx(2 * turnover * 0.00035)  # दोन्ही लेग
        assert breakdown["sebi_fee"] == pytest.approx(2 * turnover * 0.000001, abs=0.01)  # दोन्ही लेग — अतिशय लहान रक्कम, summary round होतो
        assert totals["total_charges"] == pytest.approx(sum(breakdown.values()), abs=0.1)
        # Net P&L = Gross - Charges
        assert totals["net_pnl"] == pytest.approx(totals["gross_pnl"] - totals["total_charges"], abs=0.1)

    def test_empty_range_returns_empty_breakdown(self, temp_db):
        report_df, totals = pnl_reports.generate_pnl_report(
            "NIFTY", "Daily", datetime.date(2026, 9, 1), datetime.date(2026, 9, 30),
        )
        assert totals == pnl_reports._EMPTY_TOTALS
        assert totals["charges_breakdown"] == {}
