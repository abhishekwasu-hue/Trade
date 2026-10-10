"""paper/journal.py — PAPER trade journal (Abhi P0 #4, #5). VPS local SQLite (`PAPER_JOURNAL_DB`, default data/paper_journal.db).

प्रत्येक trade: bot, signal_source, Vision मत + कारण, approver, engine shadow मत, R:R, entry / exit charges (charges.py, Upstox दर),
gross आणि net P&L. Trade स्वतः `live_trades` (trading_engine) मध्येच; हा journal त्याच्या बाजूला — exits / entries च्या मार्गात नाही.
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_journal (
  trade_id TEXT PRIMARY KEY, bot TEXT, source TEXT, symbol TEXT, signal_source TEXT, direction TEXT, strategy TEXT,
  vision_signal_id TEXT, vision_verdict TEXT, vision_reason TEXT, approver TEXT, engine_opinion TEXT, rr REAL,
  entry_time TEXT, lots INTEGER, lot_size INTEGER, net_credit REAL, max_loss REAL, sl_pnl_level REAL, target_pnl_level REAL,
  legs_json TEXT, entry_charges REAL, exit_time TEXT, exit_reason TEXT, gross_pnl REAL, exit_charges REAL, net_pnl REAL,
  last_update_at TEXT, near_alerts TEXT, dry_run INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS paper_would_have (
  ts TEXT, bot TEXT, symbol TEXT, direction TEXT, level REAL, setup_tf TEXT, status TEXT, reason TEXT, signal_id TEXT,
  orig_lots INTEGER, orig_naked_lots INTEGER, lots INTEGER DEFAULT 0, dry_run INTEGER DEFAULT 0);
"""
WOULD_COLS = ("ts", "bot", "symbol", "direction", "level", "setup_tf", "status", "reason", "signal_id", "orig_lots", "orig_naked_lots",
              "dry_run")
COLS = ("trade_id", "bot", "source", "symbol", "signal_source", "direction", "strategy", "vision_signal_id", "vision_verdict", "vision_reason",
        "approver", "engine_opinion", "rr", "entry_time", "lots", "lot_size", "net_credit", "max_loss", "sl_pnl_level", "target_pnl_level",
        "legs_json", "entry_charges", "exit_time", "exit_reason", "gross_pnl", "exit_charges", "net_pnl", "last_update_at", "near_alerts",
        "dry_run")


def db_path(path=None):
    from . import config as PC
    return path or os.environ.get("PAPER_JOURNAL_DB") or os.path.join(PC.data_dir(), "paper_journal.db")


def connect(path=None, timeout=5):
    p = db_path(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    c = sqlite3.connect(p, timeout=timeout)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def get(trade_id, path=None):
    with connect(path) as c:
        r = c.execute("SELECT * FROM paper_journal WHERE trade_id=?", (trade_id,)).fetchone()
    return dict(r) if r else None


def upsert(row, path=None):
    row = {k: v for k, v in row.items() if k in COLS}
    with connect(path) as c:
        if c.execute("SELECT 1 FROM paper_journal WHERE trade_id=?", (row["trade_id"],)).fetchone():
            sets = [k for k in row if k != "trade_id"]
            if sets:
                c.execute(f"UPDATE paper_journal SET {','.join(f'{k}=?' for k in sets)} WHERE trade_id=?",
                          [row[k] for k in sets] + [row["trade_id"]])
        else:
            c.execute(f"INSERT INTO paper_journal ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))


def rows(day=None, path=None, open_only=False):
    q, a = "SELECT * FROM paper_journal WHERE 1=1", []
    if day:
        q += " AND substr(entry_time,1,10)=?"
        a.append(str(day))
    if open_only:
        q += " AND exit_time IS NULL"
    with connect(path) as c:
        return [dict(r) for r in c.execute(q + " ORDER BY entry_time", a).fetchall()]


# ---------------------------------------------------------------------------------------------------------------- charges
def order_charges(orders, symbol, broker_type="upstox"):
    """order rows [{transaction_type, quantity, fill_price/price}] ⇒ एकूण charges (₹), charges.py चे Upstox दर (STT / exchange / SEBI /
    stamp / GST + brokerage). मोजता न आलेला row ⇒ charges.py चाच ढोबळ fallback (₹25 / order)."""
    import charges as CH
    total = 0.0
    for o in orders or []:
        row = {"quantity": o.get("quantity"), "fill_price": o.get("fill_price"), "price": o.get("price"), "symbol": symbol,
               "transaction_type": o.get("transaction_type")}
        x = CH._accurate_row_charges(row, broker_type)
        total += float(x["charge"]) if x else float(CH.FLAT_CHARGE_PER_ORDER)
    return round(total, 2)


def legs_orders(legs, qty, price_key="ltp", prices=None, exit_=False):
    """legs (live_trades.legs_json) ⇒ order rows. exit_ ⇒ उलटी बाजू. prices = {instrument_key: price} (नसेल ⇒ leg[price_key])."""
    out = []
    for lg in legs or []:
        side = str(lg.get("transaction_type") or "").upper()
        if exit_:
            side = "BUY" if side == "SELL" else "SELL"
        px = (prices or {}).get(lg.get("instrument_key"), lg.get(price_key) if lg.get(price_key) is not None else lg.get("premium"))
        out.append({"transaction_type": side, "quantity": qty, "fill_price": px})
    return out


def load_legs(legs_json):
    try:
        return json.loads(legs_json or "[]")
    except (TypeError, ValueError):
        return []


def would_have(row, path=None):
    """Abhi (Monday PAPER): ✅ शिवाय / नाकारलेला signal ⇒ position नाही, फक्त ही नोंद (lots 0) — "झाला असता तर" तुलनेसाठी."""
    r = {k: row.get(k) for k in WOULD_COLS}
    r["dry_run"] = 1 if r.get("dry_run") else 0
    with connect(path) as c:
        c.execute(f"INSERT INTO paper_would_have ({','.join(WOULD_COLS)}, lots) VALUES ({','.join('?' * len(WOULD_COLS))}, 0)", list(r.values()))


def would_have_rows(path=None):
    with connect(path) as c:
        return [dict(r) for r in c.execute("SELECT * FROM paper_would_have ORDER BY ts").fetchall()]
