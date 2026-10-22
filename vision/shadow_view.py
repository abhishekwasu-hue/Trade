"""vision/shadow_view.py — T-1 (Abhi, DECISIONS 29): "Shadow trades (rejected / no reply)" — Vision पान आणि Performance पान दोन्हीकडे.

प्रत्येक `<bot>_vision_shadow` PAPER trade: label ("15M Dynamic SR: shadow"), जोडलेला signal / card वेळ, open / closed, entry, exit, P&L आणि
का नाकारला (Abhi ❌ / no reply / drift / Vision auto-reject). सारांश: "Rejected / no-reply signals: N · shadow trades opened M · their P&L".
हे trades **खऱ्या PAPER आकडेवारीत नाहीत**: database._shadow_exclusion_clause ("…_shadow" ने संपणारा source) मुळे P&L totals, kill switch,
daily max trades — कुठेच मोजले जात नाहीत. हे पान / module फक्त वाचतं (live_trades read-only), काहीही लिहित / order पाठवत नाही.
"""
import os
import sqlite3

import pandas as pd

from . import config as VC
from . import store as VS

SUFFIX = "_vision_shadow"
EXPLAIN = "comparison only, not counted in results"
TITLE = "Shadow trades (rejected / no reply)"
CAPTION = ("A shadow trade is a PAPER trade the bot records for a signal you rejected or did not answer — comparison only, not "
           "counted in results: the P&L totals, the kill switch and the trade limits above never include it.")
LINK_WINDOW_MIN = 10                                                    # vision/outcome.find_trade सारखंच: executed_at नंतर 10 मिनिटांत entry


def bot_of(source):
    s = str(source or "")
    return s[:-len(SUFFIX)] if s.endswith(SUFFIX) else None


def label(bot):
    try:
        from paper.watch import BOT_LABEL
        name = BOT_LABEL.get(bot)
    except Exception:                                                    # noqa: BLE001
        name = None
    name = name or VC.BOTS.get(bot, (bot,))[0]
    return f"{name}: shadow"


def reason_of(r):
    """का नाकारला: Abhi ❌ (+ कारण) / no reply / drift / service restart / Vision auto-reject — नाकारलेला नसेल ⇒ None."""
    if r.get("status") == "EXECUTED":
        return None
    if r.get("status") == "DRIFT_REJECTED":
        return "drift (price moved after the approval)"
    if r.get("human_decision") == "reject":
        return "Abhi ❌" + (f" ({r['reject_reason']})" if r.get("reject_reason") else "")
    by = str(r.get("decided_by") or "")
    if by in ("timeout", "stale"):
        return "no reply"
    if by == "restart":
        return "service restart"
    if by == "vision" and float(r.get("factor") or 0) <= 0:
        return "Vision auto-reject"
    if r.get("status") == "SHADOWED":                                    # उदा. approval mode: ✅ नव्हतं (vision APPROVED)
        return "no ✅ approval"
    return None


def shadow_trades(trades_db=None, start=None, end=None):
    """live_trades मधले `*_vision_shadow` PAPER trades (read-only). DB नाही ⇒ []."""
    if trades_db is None:
        import database
        trades_db = database.DB_PATH
    if not trades_db or not os.path.exists(trades_db):
        return []
    q = ("SELECT * FROM live_trades WHERE COALESCE(source,'') LIKE ? ESCAPE '\\' AND COALESCE(mode,'PAPER')='PAPER'")
    a = ["%\\_vision\\_shadow"]
    if start:
        q += " AND substr(entry_time,1,10) >= ?"
        a.append(str(start))
    if end:
        q += " AND substr(entry_time,1,10) <= ?"
        a.append(str(end))
    c = sqlite3.connect(f"file:{trades_db}?mode=ro", uri=True, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(q + " ORDER BY entry_time", a)]
    finally:
        c.close()


def _link(tr, sigs):
    """Trade ⇒ त्याचा signal: vision_signals.trade_id आधी; नाहीतर त्याच bot / symbol चा SHADOWED / DRIFT_REJECTED, executed_at ≤ entry ≤ +10 मि."""
    bot = bot_of(tr.get("source"))
    for s in sigs:
        if s.get("trade_id") and s["trade_id"] == tr.get("trade_id"):
            return s
    try:
        e = pd.Timestamp(tr.get("entry_time"))
    except (TypeError, ValueError):
        return None
    best = None
    for s in sigs:
        if s.get("bot") != bot or s.get("symbol") != tr.get("symbol") or s.get("status") not in ("SHADOWED", "DRIFT_REJECTED"):
            continue
        try:
            x = pd.Timestamp(s.get("executed_at") or s.get("signal_ts"))
        except (TypeError, ValueError):
            continue
        if x <= e <= x + pd.Timedelta(minutes=LINK_WINDOW_MIN) and (best is None or x > best[0]):
            best = (x, s)
    return best[1] if best else None


def build(trades_db=None, vpath=None, start=None, end=None):
    """(rows, summary) — rows: प्रत्येक shadow trade ची एक ओळ; summary: {rejected, opened, closed, open, pnl, line}."""
    sigs = [r for r in VS.list_signals(None, vpath) if r.get("mode") in VC.V1_MODES
            and (not start or str(r.get("signal_ts"))[:10] >= str(start)) and (not end or str(r.get("signal_ts"))[:10] <= str(end))]
    rows = []
    for tr in shadow_trades(trades_db, start, end):
        s = _link(tr, sigs) or {}
        closed = str(tr.get("status") or "").upper() == "CLOSED"
        rows.append({"label": label(bot_of(tr.get("source"))), "signal_id": s.get("signal_id"),
                     "card time": str(s.get("signal_ts") or "")[:16].replace("T", " ") or None,
                     "signal": f"{s.get('symbol')} {s.get('direction')}" if s else None,
                     "state": "closed" if closed else "open", "entry time": str(tr.get("entry_time") or "")[:16],
                     "entry spot": tr.get("entry_spot_price"), "net credit": tr.get("net_credit"),
                     "exit time": str(tr.get("exit_time") or "")[:16] or None, "exit": tr.get("exit_reason"),
                     "P&L": tr.get("realized_pnl") if closed else None, "why rejected": reason_of(s) if s else None,
                     "source": tr.get("source"), "trade_id": tr.get("trade_id")})
    rejected = sum(1 for r in sigs if reason_of(r))
    closed = [r for r in rows if r["state"] == "closed" and r["P&L"] is not None]
    pnl = round(sum(float(r["P&L"]) for r in closed), 2)
    n_open = sum(1 for r in rows if r["state"] == "open")
    line = (f"Rejected / no-reply signals: {rejected} · shadow trades opened {len(rows)} · their P&L ₹{pnl:,.0f}"
            + (f" ({n_open} still open)" if n_open else "") + f" — {EXPLAIN}")
    return rows, {"rejected": rejected, "opened": len(rows), "closed": len(closed), "open": n_open, "pnl": pnl, "line": line}


def render(st, start=None, end=None, trades_db=None, vpath=None, header=None):
    """Streamlit section (दोन्ही पानं). कुठलीही चूक ⇒ caption; पान कधीच मोडत नाही."""
    try:
        (header or st.subheader)(f"📒 {TITLE}")
        st.caption(CAPTION)
        rows, summ = build(trades_db, vpath, start, end)
        st.markdown(f"**{summ['line']}**")
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No shadow trades in this period.")
    except Exception as exc:                                             # noqa: BLE001 — display only
        st.caption(f"Shadow trades वाचता आले नाहीत: {type(exc).__name__}: {exc}")
