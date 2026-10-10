#!/usr/bin/env python3
"""🧪 Sunday dry-run (Abhi, Monday PAPER): मागच्या बंद दिवसाच्या data वर तिन्ही bots चा एकेक signal replay — खरा मार्ग वापरून:
signal ⇒ Vision gate (vision_signals QUEUED) ⇒ vision worker (chart + Vision + Telegram ✅ / ❌, "[DRY-RUN]") ⇒ तुमचं बटण ⇒ PAPER entry
(Upstox option chain LTP, bot च्या settings, lot size master) ⇒ updates (entry / P&L / जवळ इशारा) ⇒ exit ⇒ journal (dry_run = 1).

  • Signal level = मागच्या बंद दिवसाची किंमत (5-Min ⇒ दिवसाचा low = Support / bull put · 15M ⇒ high = Resistance / bear call ·
    SR V3 ⇒ close = Support) — replay साठी; खरे bot gates (RSI / PCR / touch) इथे नाहीत.
  • Trade source "<bot source>_dryrun_shadow" ⇒ P&L / kill-switch बेरजेत नाही; खरा पैसा नाही; LIVE ला हात नाही.
  • बाजार चालू असताना चालत नाही (खरे bots याच vision keys वापरतात ⇒ मिसळू नये).
  • Vision call = खरा (bot चा vision खर्च नियम / budget लागू) — Abhi ने dry-run साठी मागितला.
  • vision_worker.service आणि vision_telegram.service चालू हवेत (ते बटण हाताळतात). प्रत्येक signal ला उत्तराची वाट: --wait-min.
  • ✋ manual: `/paper <SYM> bullput SL <spot − 100> T <spot + 300>` (option chain च्या spot वरून) — खरा `paper.manual.handle` मार्ग
    (dry-run ⇒ बाजार-वेळ तपासणी वगळली; source "manual_paper_dryrun_shadow").

  python3 scripts/paper_dry_run.py [--bots dynamic_sr_instant,srv2_momentum_reversal,srv3_instant,manual] [--wait-min 12] [--hold-min 1]
"""
import argparse
import datetime as dt
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TAG = "🧪 [DRY-RUN] "
SOURCE = {"dynamic_sr_instant": "dynamic_sr_instant", "srv2_momentum_reversal": "srv2_momentum_reversal",
          "srv3_instant": "dynamic_sr_instant_srv3_shadow"}
SETTINGS_KEY = {"dynamic_sr_instant": "1m_instant", "srv2_momentum_reversal": "15m_dynamic_sr", "srv3_instant": "1m_instant"}
TF = {"dynamic_sr_instant": "5M", "srv2_momentum_reversal": "15M", "srv3_instant": "5M"}


def _ist_now():
    from config import get_ist_now
    t = pd.Timestamp(get_ist_now())
    return t.tz_localize(None) if t.tzinfo else t


def log(lines, text, path):
    print(text, flush=True)
    lines.append(text)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def last_day_levels(token, symbol, fetch=None):
    """मागचा पूर्ण दिवस: (day, low, high, close, signal_ts)."""
    if fetch is None:
        from upstox_api import fetch_candles as fetch
    m1 = fetch(token, symbol, 0, interval="1minute", lookback_days=7)
    m1 = m1.copy()
    m1["timestamp"] = pd.to_datetime(m1["timestamp"])
    if getattr(m1["timestamp"].dt, "tz", None) is not None:
        m1["timestamp"] = m1["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    day = m1["timestamp"].dt.normalize().max()
    d = m1[m1["timestamp"].dt.normalize() == day]
    ts = d["timestamp"].iloc[len(d) * 3 // 4]                                   # दिवसाच्या ~¾ वेळचा signal (chart मध्ये पुरेसा संदर्भ)
    return day, float(d["low"].min()), float(d["high"].max()), float(d["close"].iloc[-1]), ts


def signal_for(bot, lo, hi, close):
    if bot == "srv2_momentum_reversal":
        return "BEARISH", hi, "Resistance"
    if bot == "srv3_instant":
        return "BULLISH", close, "Support"
    return "BULLISH", lo, "Support"


def run_bot(bot, token, symbol, wait_min, hold_min, lines, lpath, gate_fn=None, status_fn=None, open_fn=None, close_fn=None, sleep=time.sleep):
    import cloud_db
    from paper import engine_entry as EE
    from paper import journal as PJ
    from paper import lots as PL
    from paper import watch as PW
    from vision import store as VS
    if gate_fn is None:
        from vision.gate import entry_gate as gate_fn
    status_fn = status_fn or (lambda sid: (VS.get_signal(sid) or {}).get("status"))
    st = cloud_db.get_strategy_settings(SETTINGS_KEY[bot], symbol)
    day, lo, hi, close, _ts = last_day_levels(token, symbol)
    direction, level, role = signal_for(bot, lo, hi, close)
    ts = pd.Timestamp(VS.now_ist())                                              # signal वेळ = आत्ता (worker आदल्या दिवसाचे signals expire करतो);
    log(lines, f"{TAG}{bot}: signal {direction} {role} {level:,.2f} — मागच्या दिवसाची ({day:%d %b}) किंमत, chart त्या दिवसापर्यंतचा", lpath)
    lots = int(st["lots"]) if st.get("credit_spread_enabled", True) else 0
    naked = int(st.get("naked_lots", st["lots"])) if st.get("naked_enabled", True) else 0
    args = (bot, symbol, "PAPER", direction, level, role, TF[bot], ts, close, lots, naked)
    g = gate_fn(*args, tags={"dry_run": True})
    log(lines, f"{TAG}gate #1: {g.action} — {g.note}", lpath)
    if g.action != "HOLD" or not g.signal_id:
        log(lines, f"{TAG}अपेक्षित HOLD (approval शिवाय entry नाही) मिळाला नाही ⇒ थांबलो", lpath)
        return None
    t_end = time.time() + wait_min * 60
    stt = None
    while time.time() < t_end:
        stt = status_fn(g.signal_id)
        if stt in ("APPROVED", "REJECTED", "EXPIRED", "FAILED"):
            break
        sleep(5)
    log(lines, f"{TAG}Vision / तुमचा निर्णय: {stt}", lpath)
    g2 = gate_fn(*args, tags={"dry_run": True}, forced=True)
    log(lines, f"{TAG}gate #2: {g2.action} — {g2.note}", lpath)
    if g2.action != "ENTER":
        log(lines, f"{TAG}entry नाही (approval नाही / नाकारलं / मुदत संपली) — बरोबर वर्तन", lpath)
        return None
    from paper import pause as PP
    if PP.paused():
        log(lines, f"{TAG}PAPER pause ⇒ entry नाही (/resume)", lpath)
        return None
    lot_size, src = PL.lot_size(token, symbol)
    log(lines, f"{TAG}lot size {lot_size} ({src})", lpath)
    msgs, spot = EE.open_paper(token, symbol, st, direction, level, lot_size, SOURCE[bot] + PW.DRYRUN_SUFFIX, "DRYRUN", min(lots, g2.lots),
                               min(naked, g2.naked_lots), open_fn=open_fn)
    log(lines, f"{TAG}PAPER entry: " + "; ".join(msgs), lpath)
    now = _ist_now()
    out = PW.run_cycle(token, now=now, tag=TAG)                                  # entry संदेश + journal
    log(lines, f"{TAG}watch (entry): {out}", lpath)
    out = PW.run_cycle(token, now=now + pd.Timedelta(minutes=int(PW.PC.load().get("update_every_min") or 30) + 1), tag=TAG)   # P&L update
    log(lines, f"{TAG}watch (P&L update): {out}", lpath)
    sleep(hold_min * 60)
    if close_fn is None:
        from trading_engine import close_trade_manually as close_fn
    for t in PJ.rows(open_only=True):
        if t["source"] == SOURCE[bot] + PW.DRYRUN_SUFFIX:
            ok, res = close_fn(token, t["trade_id"], symbol, "D", exit_reason="DRY_RUN_EXIT", exit_reason_detail="Sunday dry-run")
            log(lines, f"{TAG}exit {t['trade_id']}: {ok} {res}", lpath)
    out = PW.run_cycle(token, now=_ist_now(), tag=TAG)                  # exit संदेश + journal (net P&L)
    log(lines, f"{TAG}watch (exit): {out}", lpath)
    return True


def run_manual(token, symbol, wait_min, hold_min, lines, lpath, send=None, close_fn=None, sleep=time.sleep, chain_fn=None):
    """✋ /paper replay: handle ⇒ Vision ⇒ तुमचं ✅ ⇒ execute_ready ⇒ PAPER entry ⇒ updates ⇒ exit ⇒ journal."""
    from paper import journal as PJ
    from paper import manual as PM
    from paper import watch as PW
    if send is None:
        from notifications import send_telegram_message as send
    chain, why, ei = (chain_fn or PM.default_chain)(token, symbol)
    if not chain:
        log(lines, f"{TAG}manual: option chain नाही ({why})", lpath)
        return None
    spot = float(chain[0]["underlying_spot_price"])
    cmd = f"/paper {symbol} bullput SL {round(spot - 100)} T {round(spot + 300)}"
    log(lines, f"{TAG}manual: {cmd} (spot {spot:,.1f})", lpath)
    ok, msg = PM.handle(cmd, "dry-run", send=lambda t: send(TAG + t), dry_run=True, token_fn=lambda: token,
                        chain_fn=lambda t, s: (chain, why, ei))
    log(lines, f"{TAG}manual handle: {ok} — {msg}", lpath)
    if not ok:
        return None
    mid = PM.rows("QUEUED", symbol=symbol)[-1]["id"]
    t_end = time.time() + wait_min * 60
    while time.time() < t_end:
        PM.execute_ready(token=token, send=lambda t: send(TAG + t))       # idempotent (Telegram service सुद्धा हेच करते)
        if PM.get(mid)["status"] != "QUEUED":
            break
        sleep(5)
    m = PM.get(mid)
    log(lines, f"{TAG}manual निकाल: {m['status']} {m.get('trade_id') or ''} {m.get('note') or ''}", lpath)
    if m["status"] != "EXECUTED":
        log(lines, f"{TAG}manual: entry नाही (✅ नाही / नाकारलं / मुदत) — बरोबर वर्तन", lpath)
        return None
    now = _ist_now()
    log(lines, f"{TAG}watch (entry): {PW.run_cycle(token, now=now, tag=TAG)}", lpath)
    log(lines, f"{TAG}watch (P&L update): {PW.run_cycle(token, now=now + pd.Timedelta(minutes=int(PW.PC.load().get('update_every_min') or 30) + 1), tag=TAG)}",
        lpath)
    sleep(hold_min * 60)
    if close_fn is None:
        from trading_engine import close_trade_manually as close_fn
    ok, res = close_fn(token, m["trade_id"], symbol, "D", exit_reason="DRY_RUN_EXIT", exit_reason_detail="Sunday dry-run (manual)")
    log(lines, f"{TAG}manual exit {m['trade_id']}: {ok} {res}", lpath)
    log(lines, f"{TAG}watch (exit): {PW.run_cycle(token, now=_ist_now(), tag=TAG)}", lpath)
    j = PJ.get(m["trade_id"])
    log(lines, f"{TAG}manual journal: signal_source {j and j.get('signal_source')} · R:R {j and j.get('rr')} · net ₹{(j or {}).get('net_pnl')}", lpath)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bots", default="dynamic_sr_instant,srv2_momentum_reversal,srv3_instant,manual")
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--wait-min", type=float, default=12)
    ap.add_argument("--hold-min", type=float, default=1)
    a = ap.parse_args(argv)
    import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    lpath = os.path.join(ROOT, "data", f"paper_dry_run_{dt.date.today():%Y%m%d}.log")
    os.makedirs(os.path.dirname(lpath), exist_ok=True)
    lines = []
    if not token:
        log(lines, "❌ Upstox token नाही — dry-run नाही (आधी daily login)", lpath)
        return 2
    from config import is_market_open
    if is_market_open():                                                 # बाजार चालू ⇒ खरे bots याच vision keys वर ⇒ dry-run नाही (Sunday / बाजार बंद असतानाच)
        log(lines, "❌ बाजार चालू आहे — dry-run फक्त बाजार बंद असताना (खऱ्या bots च्या signals मध्ये मिसळू नये)", lpath)
        return 3
    from notifications import send_telegram_message
    send_telegram_message(f"{TAG}सुरू: {a.bots} · प्रत्येक signal ला ✅ / ❌ दाबा ({a.wait_min:g} मिनिटं)")
    for bot in [x.strip() for x in a.bots.split(",") if x.strip()]:
        try:
            if bot == "manual":
                run_manual(token, a.symbol, a.wait_min, a.hold_min, lines, lpath)
            else:
                run_bot(bot, token, a.symbol, a.wait_min, a.hold_min, lines, lpath)
        except Exception as exc:
            log(lines, f"{TAG}{bot}: त्रुटी {type(exc).__name__}: {exc}", lpath)
    from paper import journal as PJ
    js = [j for j in PJ.rows() if j.get("dry_run")]
    log(lines, f"{TAG}journal dry-run rows: {len(js)} · " + "; ".join(f"{j['bot']} net ₹{(j.get('net_pnl') or 0):,.0f}" for j in js[-3:]), lpath)
    send_telegram_message(f"{TAG}पूर्ण. log: {lpath}")
    print(f"log: {lpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
