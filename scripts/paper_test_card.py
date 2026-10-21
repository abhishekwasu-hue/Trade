#!/usr/bin/env python3
"""🧪 TEST card (Abhi): one Telegram message through the REAL path — the 15M SRv2 bot's Vision gate ⇒ vision_worker (chart + Vision
verdict + ✅ Approve / ✏️ change the entry only / ❌ Reject with a reason) ⇒ vision_telegram handles the buttons — labelled
"🧪 TEST — not a trade". It NEVER creates a position: this script never calls an order function, the card is tagged `test_only` +
`dry_run` (the ✅ path skips it; summaries skip it), and it checks the real trades DB and journal are unchanged at the end (any change
⇒ ❌ and exit 1). The level is the last closed day's high (a bear call at resistance, as the dry-run replay). Market closed only:
it refuses when the start or the end of the wait falls on a trading day from 08:30 to 15:35 IST (`in_window`; the wait
is capped at 30 minutes).

  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_test_card.py [--symbol NIFTY] [--wait-min 10]
"""
import argparse
import datetime
import os
import sqlite3
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TAG = "🧪 TEST — not a trade · "
BOT = "srv2_momentum_reversal"
FINAL = ("APPROVED", "REJECTED", "EXPIRED", "FAILED")
MAX_WAIT_MIN = 30


def market_window(now=None):
    """True on a trading day from 08:30 to 15:35 IST: the bots' cron (warm-up 08:50, entries 09:31–15:00) plus a margin. Abhi: a TEST
    card only when the market is closed, never in market hours."""
    import config
    return config.is_market_open(now, open_time=datetime.time(8, 30), close_time=datetime.time(15, 35))


def in_window(wait_min, now=None):
    """The card stays answerable for the whole wait ⇒ refuse if its start OR its end falls in the market window (the wait is capped,
    so it can never span the window)."""
    import config
    now = now or config.get_ist_now()
    return market_window(now) or market_window(now + datetime.timedelta(minutes=wait_min))


def count_rows(db, table):
    if not db or not os.path.exists(db):
        return 0
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
            return int(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def snapshot():
    """(real trades rows, real journal rows, journal would-have rows) — read only."""
    import config
    from paper import journal as PJ
    db = config.DB_PATH if os.path.isabs(config.DB_PATH) else os.path.join(ROOT, config.DB_PATH)
    jp = PJ.db_path(None)
    return count_rows(db, "live_trades"), count_rows(jp, "paper_journal")


def run(token, symbol, wait_min, send, gate_fn=None, status_fn=None, levels_fn=None, settings_fn=None, sleep=time.sleep,
        clock=time.time, expire_fn=None):
    """Submit the TEST signal to the bot's real Vision gate, wait for Abhi's button, report. Never an order. Returns the final status."""
    from vision import store as VS
    if gate_fn is None:
        from vision.gate import entry_gate as gate_fn
    status_fn = status_fn or (lambda sid: (VS.get_signal(sid) or {}).get("status"))
    expire_fn = expire_fn or (lambda sid: VS.transition(sid, ("QUEUED", "RUNNING", "PENDING_HUMAN"), "EXPIRED",
                                                        decided_at=VS._iso(VS.now_ist()), decided_by="test_card_timeout"))
    if settings_fn is None:
        import cloud_db
        settings_fn = cloud_db.get_strategy_settings
    if levels_fn is None:
        from scripts import paper_dry_run as DR
        levels_fn = DR.last_day_levels
    st = settings_fn("15m_dynamic_sr", symbol)
    day, lo, hi, close, _ts = levels_fn(token, symbol)
    lots = int(st.get("lots") or 1)
    naked = int(st.get("naked_lots", lots) or 0)
    ts = pd.Timestamp(VS.now_ist())
    tags = {"test_only": True, "dry_run": True}
    g = gate_fn(BOT, symbol, "PAPER", "BEARISH", float(hi), "Resistance", "15M", ts, float(close), lots, naked, tags=tags)
    send(f"{TAG}{symbol}: a TEST card is on its way (Vision verdict + chart + ✅ / ✏️ / ❌). Press any button — no position is ever "
         f"created. Level: the {pd.Timestamp(day):%d %b} high {float(hi):,.0f} (bear call at resistance, replay only).")
    if g.action != "HOLD" or not g.signal_id:
        send(f"{TAG}gate answered {g.action} ({g.note}) — no card (check: Vision approval_required ON, the symbol in the Vision list)")
        return None
    end = clock() + wait_min * 60
    stt = None
    while clock() < end:
        stt = status_fn(g.signal_id)
        if stt in FINAL:
            break
        sleep(5)
    if stt not in FINAL:                                                  # unanswered ⇒ closed now, so its buttons never act later
        expire_fn(g.signal_id)
        stt = "EXPIRED"
    send(f"{TAG}{symbol}: your button ⇒ {stt} — recorded; NO position (TEST).")
    return stt


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--wait-min", type=float, default=10)
    a = ap.parse_args(argv)
    if not 1 <= a.wait_min <= MAX_WAIT_MIN:
        print(f"❌ --wait-min must be 1–{MAX_WAIT_MIN} minutes")
        return 4
    if in_window(a.wait_min):
        print("❌ market hours — the TEST card runs only when the market is closed: start after 15:35 IST, or finish the whole wait "
              "before 08:30 IST, or a holiday (during the session it could share a ✅ with a real card)")
        return 3
    import cloud_db
    from notifications import send_telegram_message as send
    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        print("❌ Upstox token missing — the chart needs data; log in first")
        return 2
    before = snapshot()
    stt = run(token, a.symbol.upper(), a.wait_min, send)
    after = snapshot()
    clean = before == after
    line = f"TEST card: {stt or 'no card / no answer'} · real trades {before[0]} ⇒ {after[0]} · journal {before[1]} ⇒ {after[1]}"
    print(("✅ " if clean else "❌ ") + line + (" · no position created" if clean else " · CHANGED — report this"))
    if not clean:
        send(f"{TAG}❌ the real trades / journal changed during the TEST — check")
    return 0 if clean and stt is not None else 1


if __name__ == "__main__":
    sys.exit(main())
