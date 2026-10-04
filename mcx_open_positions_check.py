"""
mcx_open_positions_check.py
-----------------------------
🎓 वापरकर्त्याने मागितलेली read-only तपासणी (GOLD Oct expiry आधी) — **कुठलाही order/DB-लेखन/setting बदल नाही**:

  1. सर्व MCX symbols चा सद्य front-month contract (Upstox Search Instruments API), expiry आणि उरलेले ट्रेडिंग दिवस
     (सोम–शुक्र; MCX सुट्ट्यांची यादी repo मध्ये नाही, त्यामुळे त्या वजा केलेल्या नाहीत) — `--warn-days` (डीफॉल्ट 6) च्या आत ⚠️.
  2. स्थानिक DB (live_trades) मधल्या उघड्या MCX positions — PAPER/LIVE, सर्व accounts, मूळ bot आणि SR V3 shadow दोन्ही — प्रत्येकाचा
     contract/expiry आणि expiry-जवळ आहे का.
  3. Upstox broker वरच्या प्रत्यक्ष (LIVE) MCX positions (net qty ≠ 0). इतर brokers (Fyers/Shoonya/Stocko) ला MCX LIVE order जाऊच शकत
     नाही (trading_engine चा MCX LIVE gate फक्त Upstox), म्हणून त्यांची broker-side तपासणी नाही — DB (वर 2) मध्ये त्यांचे account_id दिसतील.

    python3 mcx_open_positions_check.py
    python3 mcx_open_positions_check.py --warn-days 6 --token <UPSTOX_TOKEN>
"""
import argparse
import datetime
import json
import sqlite3
import sys

MCX_SOURCES = ("mcx_futures", "mcx_futures_srv3_shadow")


def trading_days_left(today, expiry):
    """[today, expiry] मधले सोम–शुक्र दिवस (दोन्ही टोकं धरून; आज weekend असेल तर तो मोजला जात नाही). expiry गेलेली ⇒ 0."""
    if expiry is None or expiry < today:
        return 0
    n, d = 0, today
    while d <= expiry:
        if d.weekday() < 5:
            n += 1
        d += datetime.timedelta(days=1)
    return n


def _date(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def contract_rows(token, symbols, today, warn_days, resolve):
    rows = []
    for sym in symbols:
        try:
            ok, r = resolve(token, sym)
        except Exception as exc:                                 # एका symbol ची अडचण बाकीच्यांना थांबवू नये
            ok, r = False, str(exc)
        if not ok:
            rows.append({"symbol": sym, "contract": None, "expiry": None, "trading_days_left": None, "warn": True, "note": str(r)})
            continue
        exp = _date(r.get("front_expiry") or r.get("expiry"))
        name = r.get("front_trading_symbol") or r.get("trading_symbol")
        tdl = trading_days_left(today, exp)
        rows.append({"symbol": sym, "contract": name, "expiry": exp, "trading_days_left": tdl, "warn": tdl <= warn_days,
                     "note": f"पुढचे: {', '.join(str(e) for e in (r.get('all_upcoming_expiries') or [])[1:3])}"})
    return rows


def db_open_positions(db_path, symbols, today, warn_days):
    """live_trades मधल्या OPEN MCX trades (read-only connection)."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return None, f"DB उघडता आला नाही: {exc}"
    try:
        placeholders = ",".join("?" * len(symbols))
        cur = conn.execute(
            f"""SELECT trade_id, symbol, COALESCE(mode,'LIVE'), COALESCE(account_id,''), COALESCE(source,''), legs_json, entry_time, strategy, lots
                FROM live_trades WHERE status='OPEN' AND (source IN ({",".join("?" * len(MCX_SOURCES))}) OR symbol IN ({placeholders}))""",
            (*MCX_SOURCES, *symbols))
        out = []
        for trade_id, sym, mode, acc, src, legs_json, entry_time, strategy, lots in cur.fetchall():
            try:
                legs = json.loads(legs_json or "[]")
            except ValueError:
                legs = []
            leg = legs[0] if legs else {}
            exp = _date(leg.get("expiry"))
            tdl = trading_days_left(today, exp) if exp else None
            out.append({"trade_id": trade_id, "symbol": sym, "mode": mode, "account_id": acc or "Upstox (डीफॉल्ट)", "source": src,
                        "instrument_key": leg.get("instrument_key"), "expiry": exp, "trading_days_left": tdl,
                        "warn": tdl is not None and tdl <= warn_days, "entry_time": entry_time, "strategy": strategy, "lots": lots})
        return out, None
    except sqlite3.Error as exc:
        return None, f"DB query अयशस्वी: {exc}"
    finally:
        conn.close()


def broker_mcx_positions(positions):
    """Upstox short-term positions -> net qty ≠ 0 असलेल्या MCX positions."""
    if positions is None:
        return None
    out = []
    for p in positions:
        exch = str(p.get("exchange") or p.get("segment") or "").upper()
        key = str(p.get("instrument_token") or p.get("instrument_key") or "")
        if "MCX" not in exch and not key.upper().startswith("MCX"):
            continue
        qty = p.get("quantity", p.get("net_quantity", 0)) or 0
        if float(qty) == 0:
            continue
        out.append({"trading_symbol": p.get("trading_symbol") or p.get("tradingsymbol"), "instrument_key": key, "quantity": qty,
                    "product": p.get("product"), "pnl": p.get("pnl")})
    return out


def main(argv=None, resolve=None, positions_fn=None, token_fn=None, db_path=None, today=None):
    p = argparse.ArgumentParser()
    p.add_argument("--token", default=None)
    p.add_argument("--warn-days", type=int, default=6)
    args = p.parse_args(argv)
    if resolve is None or positions_fn is None or token_fn is None or db_path is None or today is None:
        import cloud_db
        import resolve_mcx_futures_instruments as res
        from config import DB_PATH, get_ist_today
        from upstox_api import fetch_broker_positions
        resolve = resolve or res.resolve_symbol
        positions_fn = positions_fn or fetch_broker_positions
        token_fn = token_fn or cloud_db.get_effective_upstox_token
        db_path = db_path or DB_PATH
        today = today or get_ist_today()
        symbols = res.MCX_FUTURES_SYMBOLS
    else:
        symbols = ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER"]
    token = token_fn(args.token)
    alerts = 0

    print(f"=== 1. MCX contracts (आज {today}; ट्रेडिंग दिवस = सोम–शुक्र, MCX सुट्ट्या वजा नाहीत) ===")
    if not token:
        print("❌ Upstox token नाही — contracts/broker positions तपासता आले नाहीत (फक्त DB तपासणी खाली).")
    else:
        for r in contract_rows(token, symbols, today, args.warn_days, resolve):
            flag = "⚠️" if r["warn"] else "✅"
            alerts += int(r["warn"])
            print(f"{flag} {r['symbol']:<11} {r['contract'] or '—':<24} expiry {r['expiry'] or '—'}  उरलेले ट्रेडिंग दिवस: "
                  f"{r['trading_days_left'] if r['trading_days_left'] is not None else '—'}  ({r['note']})")

    print("\n=== 2. स्थानिक DB — उघड्या MCX positions (PAPER/LIVE, सर्व accounts, मूळ + SR V3 shadow) ===")
    rows, err = db_open_positions(db_path, symbols, today, args.warn_days)
    if err:
        print(f"❌ {err}")
        alerts += 1
    elif not rows:
        print("✅ कुठलीही उघडी MCX position नाही.")
    else:
        for r in rows:
            flag = "⚠️ expiry-जवळ" if r["warn"] else "•"
            alerts += 1
            print(f"{flag} {r['trade_id']} {r['symbol']} {r['mode']} account={r['account_id']} source={r['source']} {r['strategy']} "
                  f"lots={r['lots']} instrument={r['instrument_key']} expiry={r['expiry']} (ट्रेडिंग दिवस {r['trading_days_left']}) "
                  f"entry={r['entry_time']}")

    print("\n=== 3. Upstox broker — प्रत्यक्ष (LIVE) MCX positions ===")
    if token:
        live = broker_mcx_positions(positions_fn(token))
        if live is None:
            print("❌ Upstox positions मिळाले नाहीत (token/Static IP proxy तपासा).")
            alerts += 1
        elif not live:
            print("✅ Upstox वर कुठलीही उघडी MCX position नाही.")
        else:
            for r in live:
                alerts += 1
                print(f"⚠️ {r['trading_symbol']} qty={r['quantity']} product={r['product']} P&L={r['pnl']} ({r['instrument_key']})")
    print("\n(इतर brokers वर MCX LIVE order जाऊच शकत नाही — trading_engine चा MCX LIVE gate फक्त Upstox.)")
    print(f"\nसारांश: {'⚠️ लक्ष देण्याजोगे ' + str(alerts) + ' मुद्दे' if alerts else '✅ सर्व ठीक'} — हा script काहीही बदलत नाही.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
