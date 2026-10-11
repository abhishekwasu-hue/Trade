"""paper/watch.py — PAPER trades ची updates + journal (Abhi P0 #4–#6). `trade_monitor` च्या प्रत्येक cycle नंतर (exit निर्णय झाल्यावर)
best-effort चालतो; कधीच raise नाही ⇒ exits च्या मार्गात नाही (exit निर्णय `trading_engine.manage_open_trades` चाच).

  • नवा PAPER trade (bot sources) ⇒ journal row (bot, signal_source, Vision मत + कारण, approver, engine shadow मत, R:R, entry charges)
    + Telegram "entry fill" (legs, किंमती, net credit, max loss, SL / target).
  • उघडा trade ⇒ दर `update_every_min` मिनिटांनी P&L; SL / target च्या `near_alert_pct` % जवळ ⇒ एकदा इशारा.
  • बंद झाला ⇒ exit charges (order_log च्या exit fills वरून) + net P&L ⇒ journal + Telegram "exit" (कारण, gross, charges, net).
किंमती फक्त API (order_log fills / Upstox LTP) मधून — image मधून कधीच नाही.
"""
import json
import os
import sqlite3

import pandas as pd

from . import config as PC
from . import journal as PJ

BOT_OF_SOURCE = {"dynamic_sr_instant": "dynamic_sr_instant", "srv2_momentum_reversal": "srv2_momentum_reversal",
                 "dynamic_sr_instant_srv3_shadow": "srv3_instant", "manual_paper": "manual"}   # manual = ✋ /paper (paper/manual.py)
DRYRUN_SUFFIX = "_dryrun_shadow"                                        # Sunday dry-run trades ("_shadow" ⇒ P&L / kill-switch बेरजेत नाहीत)
BOT_OF_SOURCE.update({f"{k}{DRYRUN_SUFFIX}": v for k, v in list(BOT_OF_SOURCE.items())})
SS_KEY = {"srv3_instant": "srv3_signal_source"}                        # SR V3 चा signal_source मूळ 5-Min settings मध्ये वेगळ्या key ने
BOT_LABEL = {"dynamic_sr_instant": "5-Min Instant", "srv2_momentum_reversal": "15M Dynamic SR", "srv3_instant": "SR V3 (5-Min)",
             "manual": "✋ Manual"}


def _db_path():
    from config import DB_PATH
    return DB_PATH


def _now():
    from config import get_ist_now
    t = pd.Timestamp(get_ist_now())
    return t.tz_localize(None) if t.tzinfo else t


def _say(send, text, tag=""):
    try:
        if send is None:
            from notifications import send_telegram_message as send
        send(f"{tag}{text}")
    except Exception as exc:
        print(f"⚠️ paper update पाठवता आला नाही: {exc}")


def _trades(db_path, since_day):
    if not os.path.exists(db_path):
        return []
    c = sqlite3.connect(db_path, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        q = (f"SELECT * FROM live_trades WHERE mode='PAPER' AND source IN ({','.join('?' * len(BOT_OF_SOURCE))}) "
             "AND (status='OPEN' OR trade_date>=?)")
        return [dict(r) for r in c.execute(q, list(BOT_OF_SOURCE) + [since_day]).fetchall()]
    finally:
        c.close()


def _orders(db_path, trade_id):
    c = sqlite3.connect(db_path, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM order_log WHERE trade_id=? ORDER BY rowid", (trade_id,)).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def vision_link(bot, symbol, entry_time, vpath=None, window_min=15):
    """त्या trade च्या आधीचा EXECUTED vision row (verdict, कारण, approver). नाही ⇒ {}."""
    try:
        from vision import store as VS
        t1 = pd.Timestamp(entry_time)
        best = None
        for r in VS.rows_with_status(("EXECUTED",), vpath, 5, bot=bot, symbol=str(symbol).upper()):
            ex = pd.Timestamp(r.get("executed_at") or r.get("decided_at") or r["created_at"])
            if t1 - pd.Timedelta(minutes=window_min) <= ex <= t1 + pd.Timedelta(minutes=1) and (best is None or ex > best[0]):
                best = (ex, r)
        if best is None:
            return {}
        r = best[1]
        return {"vision_signal_id": r["signal_id"], "vision_verdict": r.get("verdict"), "vision_reason": r.get("decision_reason"),
                "approver": r.get("decided_by")}
    except Exception as exc:
        print(f"⚠️ vision link: {exc}")
        return {}


def rr_of(t):
    try:
        sl, tg = float(t.get("sl_pnl_level") or 0), float(t.get("target_pnl_level") or 0)
        return round(tg / abs(sl), 2) if sl < 0 < tg else None
    except (TypeError, ValueError):
        return None


def _qty(t):
    return int(t.get("lots") or 0) * int(t.get("lot_size") or 0)


def entry_prices(t, orders):
    legs = PJ.load_legs(t.get("legs_json"))
    n = len(legs)
    ent = {o["instrument_key"]: o.get("fill_price") for o in orders[:n] if o.get("fill_price") is not None}
    return {lg["instrument_key"]: ent.get(lg["instrument_key"], lg.get("ltp")) for lg in legs}


def pnl_now(t, entry_px, ltp):
    """चालू P&L (₹): SELL legs ⇒ (entry − ltp), BUY ⇒ (ltp − entry), × lots × lot_size. LTP नसलेला leg ⇒ None."""
    q = _qty(t) * float(t.get("pnl_multiplier") or 1.0)
    tot = 0.0
    for lg in PJ.load_legs(t.get("legs_json")):
        k = lg["instrument_key"]
        if ltp.get(k) is None or entry_px.get(k) is None:
            return None
        d = float(entry_px[k]) - float(ltp[k])
        tot += d if str(lg.get("transaction_type")).upper() == "SELL" else -d
    return round(tot * q, 2)


def _legs_text(t, entry_px):
    out = []
    for lg in PJ.load_legs(t.get("legs_json")):
        px = entry_px.get(lg["instrument_key"])
        out.append(f"{lg.get('transaction_type')} {lg.get('strike')} {lg.get('option_type') or ''} @ {px if px is not None else 'NA'}")
    return " · ".join(out)


def on_entry(t, orders, send=None, jpath=None, tag="", ss_settings=None, engine_opinion=None):
    bot = BOT_OF_SOURCE[t["source"]]
    link = vision_link(bot, t["symbol"], t["entry_time"])
    if engine_opinion is None:
        try:
            import engine_signal as ES
            engine_opinion = ES.opinion(t["symbol"], t["entry_time"])
        except Exception as exc:
            engine_opinion = f"engine: NA ({exc})"
    src = "own"
    try:
        import engine_signal as ES
        src = ES.source_of(ss_settings or {}, SS_KEY.get(bot, "signal_source"))
    except Exception:
        pass
    rr = rr_of(t)
    if bot == "manual":                                                  # ✋ /paper: signal_source MANUAL, R:R = spot SL / T वरून, profile नोंद
        from . import manual as PM
        src, rr = "MANUAL", PM.rr_for_trade(t["trade_id"], jpath)
        prof = PM.profile_for_trade(t["trade_id"], jpath)
        engine_opinion = f"{engine_opinion} · profile: {prof or '—'}"
    epx = entry_prices(t, orders)
    eo = orders[:len(PJ.load_legs(t.get("legs_json")))] or PJ.legs_orders(PJ.load_legs(t.get("legs_json")), _qty(t), prices=epx)
    ech = PJ.order_charges(eo, t["symbol"])
    lot_size = int(t.get("lot_size") or 0)
    lots = int(t.get("lots") or 0)
    net_credit_total = round(float(t.get("net_credit") or 0) * lots * lot_size, 2)
    max_loss_total = round(abs(float(t.get("max_loss") or 0)) * lots * lot_size, 2)
    row = {"trade_id": t["trade_id"], "bot": bot, "source": t["source"], "symbol": t["symbol"], "signal_source": src,
           "direction": None, "strategy": t.get("strategy"), "engine_opinion": engine_opinion, "rr": rr, "entry_time": t["entry_time"],
           "lots": lots, "lot_size": lot_size, "net_credit": net_credit_total, "max_loss": max_loss_total,
           "sl_pnl_level": t.get("sl_pnl_level"), "target_pnl_level": t.get("target_pnl_level"), "legs_json": t.get("legs_json"),
           "entry_charges": ech, "last_update_at": t["entry_time"], "near_alerts": "[]", "dry_run": 1 if tag else 0, **link}
    PJ.upsert(row, jpath)
    v = link.get("vision_verdict") or "—"
    _say(send, f"🟢 <b>PAPER entry</b> · {BOT_LABEL.get(bot, bot)} · {t['symbol']} {t.get('strategy') or ''}\n"
               f"legs: {_legs_text(t, epx)}\n"
               f"net credit ₹{net_credit_total:,.0f} · max loss ₹{max_loss_total:,.0f} · SL ₹{t.get('sl_pnl_level') or 0:,.0f} · "
               f"target ₹{t.get('target_pnl_level') or 0:,.0f} · R:R {row['rr'] if row['rr'] is not None else 'NA'}\n"
               f"entry charges ₹{ech:,.0f} · Vision: {v} · approver: {link.get('approver') or '—'} · signal_source: {src}\n"
               f"{engine_opinion}", tag)
    return row


def on_exit(t, orders, j, send=None, jpath=None, tag=""):
    legs = PJ.load_legs(t.get("legs_json"))
    xo = orders[len(legs):]
    if not xo:                                                           # exit fills नाहीत ⇒ entry किंमतींच्या उलट बाजू (अंदाज) — legs वरून
        xo = PJ.legs_orders(legs, _qty(t), exit_=True)
    xch = PJ.order_charges(xo, t["symbol"])
    gross = float(t.get("realized_pnl") or 0.0)
    net = round(gross - float(j.get("entry_charges") or 0.0) - xch, 2)
    PJ.upsert({"trade_id": t["trade_id"], "exit_time": t.get("exit_time"), "exit_reason": t.get("exit_reason"), "gross_pnl": gross,
               "exit_charges": xch, "net_pnl": net}, jpath)
    _say(send, f"🔴 <b>PAPER exit</b> · {BOT_LABEL.get(j['bot'], j['bot'])} · {t['symbol']} · कारण: {t.get('exit_reason')}\n"
               f"gross ₹{gross:,.0f} − charges ₹{float(j.get('entry_charges') or 0) + xch:,.0f} ⇒ <b>net ₹{net:,.0f}</b>", tag)
    return net


def on_open(t, orders, j, access_token, now, cfg, send=None, jpath=None, tag="", ltp_fn=None):
    every = int(cfg.get("update_every_min") or 30)
    near = float(cfg.get("near_alert_pct") or 80) / 100.0
    last = pd.Timestamp(j.get("last_update_at") or t["entry_time"])
    alerts = json.loads(j.get("near_alerts") or "[]")
    sl, tg = t.get("sl_pnl_level"), t.get("target_pnl_level")
    due = now - last >= pd.Timedelta(minutes=every)
    if not due and (sl is None or "sl" in alerts) and (tg is None or "target" in alerts):
        return None
    epx = entry_prices(t, orders)
    if ltp_fn is None:
        from upstox_api import fetch_ltp_map as ltp_fn
    ltp = ltp_fn(access_token, list(epx)) if access_token else {}
    p = pnl_now(t, epx, ltp or {})
    if p is None:
        return None
    msgs = []
    if sl is not None and float(sl) < 0 and p <= near * float(sl) and "sl" not in alerts:
        alerts.append("sl")
        msgs.append(f"⚠️ SL जवळ: P&L ₹{p:,.0f} (SL ₹{float(sl):,.0f})")
    if tg is not None and float(tg) > 0 and p >= near * float(tg) and "target" not in alerts:
        alerts.append("target")
        msgs.append(f"🎯 target जवळ: P&L ₹{p:,.0f} (target ₹{float(tg):,.0f})")
    upd = {"trade_id": t["trade_id"], "near_alerts": json.dumps(alerts)}
    if due:
        upd["last_update_at"] = str(now)
        msgs.append(f"⏱ P&L ₹{p:,.0f} · SL ₹{float(sl or 0):,.0f} पर्यंत ₹{p - float(sl or 0):,.0f} · target ₹{float(tg or 0):,.0f} पर्यंत "
                    f"₹{float(tg or 0) - p:,.0f}")
    PJ.upsert(upd, jpath)
    if msgs:
        _say(send, f"📊 {BOT_LABEL.get(j['bot'], j['bot'])} · {t['symbol']} {t.get('strategy') or ''}\n" + "\n".join(msgs), tag)
    return p


def run_cycle(access_token, now=None, db_path=None, send=None, jpath=None, cfg=None, ltp_fn=None, tag="", settings_fn=None, spot_fn=None,
              close_fn=None):
    """एक cycle. रिटर्न {"entries", "exits", "updates"} (मोजणी). कधीच raise नाही."""
    out = {"entries": 0, "exits": 0, "updates": 0}
    try:
        now = pd.Timestamp(now or _now())
        cfg = cfg or PC.load()
        db_path = db_path or _db_path()
        for t in _trades(db_path, (now - pd.Timedelta(days=1)).strftime("%Y-%m-%d")):
            try:
                orders = _orders(db_path, t["trade_id"])
                j = PJ.get(t["trade_id"], jpath)
                if j is None:
                    bot = BOT_OF_SOURCE[t["source"]]
                    ss = None
                    try:
                        if settings_fn is None:
                            import cloud_db
                            from vision import config as VC
                            ss = cloud_db.get_strategy_settings(VC.BOT_STRATEGY_KEY.get(bot, "1m_instant"), t["symbol"])
                        else:
                            ss = settings_fn(bot, t["symbol"])
                    except Exception:
                        ss = None
                    j = on_entry(t, orders, send, jpath, tag, ss)
                    out["entries"] += 1
                if t["status"] == "OPEN" and BOT_OF_SOURCE[t["source"]] == "manual":
                    from . import manual as PM                           # ✋ तुमचा spot SL / T ⇒ बंद (exit संदेश पुढच्या cycle ला on_exit)
                    if PM.spot_exit(t, access_token, spot_fn, close_fn, jpath, send, tag):
                        continue
                if t["status"] == "OPEN":
                    if on_open(t, orders, j, access_token, now, cfg, send, jpath, tag, ltp_fn) is not None:
                        out["updates"] += 1
                elif t["status"] == "CLOSED" and not j.get("exit_time"):
                    on_exit(t, orders, j, send, jpath, tag)
                    out["exits"] += 1
            except Exception as exc:
                print(f"⚠️ paper watch ({t.get('trade_id')}): {type(exc).__name__}: {exc}")
    except Exception as exc:
        print(f"⚠️ paper watch: {type(exc).__name__}: {exc}")
    return out


def run_locked(access_token, **kw):
    """Exit-monitor lock **सुटल्यानंतर** बोलवायचं (network calls मुळे पुढचा exit cycle अडू नये); स्वतःचा lock ("paper_watch") ⇒ दोन monitor
    scripts एकाच वेळी ⇒ दुहेरी संदेश / exit नाहीत. कधीच raise नाही."""
    try:
        from process_lock import ProcessLock, ProcessLockHeld
    except Exception as exc:
        print(f"⚠️ paper watch lock: {exc}")
        return None
    try:
        with ProcessLock("paper_watch"):
            if not _due(kw.get("cfg")):                                  # throttle: TSL loop (5 s) मध्ये प्रत्येक cycle ला network नको
                return None
            return run_cycle(access_token, **kw)
    except ProcessLockHeld:
        return None
    except Exception as exc:
        print(f"⚠️ paper watch: {type(exc).__name__}: {exc}")
        return None


def _due(cfg=None, state_path=None, now=None):
    """शेवटच्या run पासून `watch_min_interval_sec` (config.yaml paper) झाले का; झाले ⇒ timestamp नोंदवून True. वाचता / लिहिता आलं नाही ⇒ True."""
    import time
    cfg = cfg or PC.load()
    p = state_path or os.path.join(PC.data_dir(), "paper_watch_last.json")
    t = time.time() if now is None else now
    try:
        with open(p, encoding="utf-8") as f:
            last = float(json.load(f).get("t") or 0)
    except (OSError, ValueError):
        last = 0.0
    if t - last < float(cfg.get("watch_min_interval_sec") or 0):
        return False
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"t": t}, f)
    except OSError:
        pass
    return True
