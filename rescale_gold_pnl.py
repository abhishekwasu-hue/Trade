"""rescale_gold_pnl.py
--------------------------------
🎓 GOLD चा भाव प्रति 10 ग्रॅम, पण 1 lot = 1 kg (= 100 × 10g) => P&L ×100 (बघा mcx_contract_specs.py). हा गुणक
#174 पासून नवीन trades साठी लागू आहे (live_trades.pnl_multiplier = 100, lot_size = Upstox lot_size × 100),
पण त्याआधी (किंवा VPS वर तो कोड पोहोचण्याआधी) उघडलेले/बंद झालेले GOLD trades जुन्या, गुणकाशिवायच्या
(÷100 कमी) P&L सह साठवलेले राहिले — म्हणून Performance वर Gross P&L फक्त ₹38 आणि Charges (जे orders वरून ×100
ने मोजले जातात) ₹5,151 असा विसंगत देखावा दिसतो.

हा script त्या जुन्या GOLD (source='mcx_futures') rows — ज्यांचा pnl_multiplier 1/NULL आहे — एकदाच दुरुस्त करतो:
lot_size ×100, realized_pnl/peak_pnl/sl_pnl_level/target_pnl_level/manual_sl_override_pnl ×100, pnl_multiplier=100.
(broker ला जाणारी खरी quantity = lots × lot_size ÷ pnl_multiplier => बदलत नाही.) पुन्हा चालवला तरी सुरक्षित
(pnl_multiplier=100 झालेले rows वगळले जातात).

चालवणे (VPS वर):
    python3 rescale_gold_pnl.py            # फक्त दाखवतो (dry-run), काहीही बदलत नाही
    python3 rescale_gold_pnl.py --apply    # आधी DB चा backup (data/backups/), मग दुरुस्ती
"""
import argparse
import os
import shutil
import sqlite3

from config import DB_PATH, get_ist_now
from mcx_contract_specs import get_price_multiplier

_SELECT = (
    "SELECT trade_id, trade_date, status, mode, lots, lot_size, realized_pnl, peak_pnl FROM live_trades "
    "WHERE source='mcx_futures' AND symbol='GOLD' AND COALESCE(pnl_multiplier, 1) = 1 ORDER BY entry_time"
)


def find_unscaled_gold_trades(conn):
    return conn.execute(_SELECT).fetchall()


def rescale_gold_trades(conn):
    """अद्याप गुणक न लागलेले GOLD rows ×100 ने दुरुस्त करतो; दुरुस्त केलेल्या rows ची संख्या परत देतो."""
    mult = get_price_multiplier("GOLD")
    cur = conn.execute(
        """UPDATE live_trades SET
               lot_size = lot_size * ?,
               realized_pnl = realized_pnl * ?,
               peak_pnl = peak_pnl * ?,
               sl_pnl_level = sl_pnl_level * ?,
               target_pnl_level = target_pnl_level * ?,
               manual_sl_override_pnl = manual_sl_override_pnl * ?,
               pnl_multiplier = ?
           WHERE source='mcx_futures' AND symbol='GOLD' AND COALESCE(pnl_multiplier, 1) = 1""",
        (mult, mult, mult, mult, mult, mult, mult),
    )
    conn.commit()
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="प्रत्यक्ष दुरुस्ती (आधी backup)")
    args = parser.parse_args()

    import database
    database.init_sqlite_db()  # pnl_multiplier column नसेल तर जोडतो
    conn = sqlite3.connect(DB_PATH)
    rows = find_unscaled_gold_trades(conn)
    mult = get_price_multiplier("GOLD")
    if not rows:
        print("✅ दुरुस्त करण्यासारखे कुठलेही जुने GOLD trade नाही.")
        return
    print(f"{len(rows)} जुने GOLD trade(s) सापडले (P&L ×{mult} केल्यावर):")
    for trade_id, trade_date, status, mode, lots, lot_size, realized, peak in rows:
        new_realized = None if realized is None else realized * mult
        print(f"  {trade_id} | {trade_date} | {status} | {mode} | lots={lots} | realized ₹{realized} → ₹{new_realized}")
    open_count = sum(1 for r in rows if r[2] == "OPEN")
    if open_count:
        print(f"⚠️ यातले {open_count} OPEN आहेत — त्यांचेही SL/Target levels सुसंगत रहावेत म्हणून तसेच ×{mult} होतील.")
    if not args.apply:
        print("\n(dry-run — काहीही बदललं नाही. प्रत्यक्ष दुरुस्तीसाठी --apply)")
        return

    backup_dir = os.path.join(os.path.dirname(DB_PATH) or ".", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"before_gold_rescale_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"💾 Backup: {backup_path}")
    changed = rescale_gold_trades(conn)
    print(f"✅ {changed} GOLD trade(s) दुरुस्त झाले.")


if __name__ == "__main__":
    main()
