#!/usr/bin/env python3
"""🧪 TEST PAPER order (Abhi): proves the whole path tonight — one TEST signal ⇒ Telegram card ⇒ Abhi ✅ ⇒ a PAPER order is created and
closed right away — and keeps it OUT of the real journal and P&L.

Separation (checked at the end; any leak ⇒ exit 1):
  • the PAPER trade is written to a separate trades DB (data/historical_data_TEST.db — a fresh file with the same schema; the real
    data/historical_data.db is never opened for writing by this process);
  • its journal rows go to a separate journal (data/paper_journal_TEST.db; PAPER_JOURNAL_DB);
  • every Telegram line starts "🧪 [TEST]"; the trade source carries the "_dryrun_shadow" suffix (excluded from P&L / kill switch even
    if it were seen) and the Vision row is tagged dry_run (kept out of the daily summary).
Only the 15M SRv2 bot, one symbol (default NIFTY), only when the market is closed. PAPER only — LIVE is never touched.

  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_test_order.py [--symbol NIFTY] [--wait-min 10]
"""
import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TAG = "🧪 [TEST] "
BOT = "srv2_momentum_reversal"


def test_paths(data_dir):
    return os.path.join(data_dir, "historical_data_TEST.db"), os.path.join(data_dir, "paper_journal_TEST.db")


def count_rows(db, table):
    if not os.path.exists(db):
        return 0
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
            return int(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def isolate(data_dir):
    """Point this process at the TEST trades DB and TEST journal BEFORE anything imports `config.DB_PATH` (database / trading_engine bind
    it at import). Returns (real trades DB, real journal, test trades DB, test journal)."""
    import config
    real_db = os.path.join(ROOT, config.DB_PATH) if not os.path.isabs(config.DB_PATH) else config.DB_PATH
    from paper import journal as PJ
    real_j = PJ.db_path(None)                                            # read BEFORE PAPER_JOURNAL_DB points elsewhere
    tdb, tj = test_paths(data_dir)
    for p in (tdb, tj):
        if os.path.exists(p):
            os.remove(p)                                                 # a fresh file every run
    config.DB_PATH = tdb
    os.environ["PAPER_JOURNAL_DB"] = tj
    import database
    database.DB_PATH = tdb
    database.init_sqlite_db()                                            # the same schema, empty
    return real_db, real_j, tdb, tj


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--wait-min", type=float, default=10)
    a = ap.parse_args(argv)
    from paper import config as PC
    data_dir = PC.data_dir()
    real_db, real_j, tdb, tj = isolate(data_dir)
    if "trading_engine" in sys.modules and getattr(sys.modules["trading_engine"], "DB_PATH", tdb) != tdb:
        print("❌ trading_engine was imported before the TEST DB was set — stopping (nothing written)")
        return 2
    before = (count_rows(real_db, "live_trades"), count_rows(real_j, "paper_journal"))
    from scripts import paper_dry_run as DR
    DR.TAG = TAG
    import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    lpath = os.path.join(data_dir, "paper_test_order.log")
    lines = []
    if not token:
        DR.log(lines, f"{TAG}❌ Upstox token missing — no TEST (log in first)", lpath)
        return 2
    from config import is_market_open
    if is_market_open():
        DR.log(lines, f"{TAG}❌ the market is open — TEST only when it is closed (never mixed with the real bots)", lpath)
        return 3
    import trading_engine
    assert trading_engine.DB_PATH == tdb, "TEST trades DB not in effect"
    from notifications import send_telegram_message
    send_telegram_message(f"{TAG}start: one TEST signal ({BOT}, {a.symbol}) — press ✅ on its card within {a.wait_min:g} min. "
                          "The PAPER order is opened and closed at once; it never enters the journal or P&L.")
    ok = DR.run_bot(BOT, token, a.symbol, a.wait_min, 0, lines, lpath)
    after = (count_rows(real_db, "live_trades"), count_rows(real_j, "paper_journal"))
    made = count_rows(tdb, "live_trades")
    tj_rows = count_rows(tj, "paper_journal")
    clean = after == before
    DR.log(lines, f"{TAG}result: {'order created and closed' if ok else 'no order (no ✅ / rejected / expired / gate)'} · TEST trades DB rows "
                  f"{made} · TEST journal rows {tj_rows} · real trades DB {before[0]} ⇒ {after[0]} · real journal {before[1]} ⇒ {after[1]}", lpath)
    if not clean:
        DR.log(lines, f"{TAG}❌ the real journal / trades DB changed during the TEST — report this", lpath)
    send_telegram_message(f"{TAG}{'✅ path proven: TEST order opened and closed' if ok else 'no TEST order'} · "
                          f"real journal / P&L untouched: {'yes' if clean else 'NO — check'}")
    return 0 if (ok and clean) else 1


if __name__ == "__main__":
    sys.exit(main())
