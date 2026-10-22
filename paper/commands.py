"""paper/commands.py — Telegram आज्ञा (Abhi P0 #7): /status · /positions · /pause · /resume · /exit <id>. फक्त approver (vision/telegram_bot च्या
`_authorized` नंतर). /pause, /resume फक्त **नवे PAPER entries** थांबवतात / चालू करतात (paper/pause.py — LIVE / dashboard pause नाही) — exits कधीही चालूच
(trading_engine.manage_open_trades वर pause / kill-switch चा परिणाम नाही).
प्रत्येक dependency injectable (tests); कुठलीही चूक ⇒ "NA (कारण)" — command कधीच crash होत नाही.
/exit (Abhi §10d): उघडी PAPER position लगेच बंद — `trading_engine.close_trade_manually` (✋ manual spot exit / monitor चाच मार्ग). SL / target
Telegram वरून बदलत नाहीत. LIVE (किंवा PAPER नसलेला) trade ⇒ नकार. Pause / kill-switch / इतर काहीही exit अडवत नाही.
"""
import os
import sqlite3

import engine_signal as ES

from . import watch as PW

BOT_KEYS = (("dynamic_sr_instant", "1m_instant", "signal_source"), ("srv2_momentum_reversal", "15m_dynamic_sr", "signal_source"),
            ("srv3_instant", "1m_instant", "srv3_signal_source"), ("classic_sr", "classic_sr_reversal", "signal_source"))


def _try(fn, default="NA"):
    try:
        return fn()
    except Exception as exc:
        return f"{default} ({type(exc).__name__})"


def open_trades(db_path=None):
    from config import DB_PATH
    p = db_path or DB_PATH
    if not os.path.exists(p):
        return []
    c = sqlite3.connect(p, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM live_trades WHERE status='OPEN' ORDER BY entry_time").fetchall()]
    finally:
        c.close()


def _paper_pause():
    from . import pause as PP
    return PP.get()


def status_text(token_fn=None, market_fn=None, kill_fn=None, pause_fn=None, settings_fn=None, trades_fn=None, symbol="NIFTY",
                paper_pause_fn=None):
    if token_fn is None:
        import cloud_db
        token_fn = lambda: cloud_db.get_effective_upstox_token(None)  # noqa: E731
    if market_fn is None:
        from config import is_market_open as market_fn
    if kill_fn is None:
        from trading_engine import check_kill_switch as kill_fn
    if pause_fn is None:
        import cloud_db
        pause_fn = cloud_db.get_trading_pause_settings
    if settings_fn is None:
        import cloud_db
        settings_fn = cloud_db.get_strategy_settings
    trades_fn = trades_fn or open_trades
    tok = _try(lambda: "✅ आहे" if token_fn() else "❌ नाही (daily login करा)")
    mkt = _try(lambda: "उघडा" if market_fn() else "बंद")

    def _kill():
        ok, why = kill_fn()
        return "✅ चालू (entries परवानगी)" if ok else f"⛔ लागला — {why}"
    pz = _try(lambda: (lambda p: f"⏸ pause ({p.get('reason') or ''})" if p.get("paused") else "▶️ चालू")(pause_fn()))
    ppz = _try(lambda: (lambda p: f"⏸ pause ({p.get('reason') or ''})" if p.get("paused") else "▶️ चालू")((paper_pause_fn or _paper_pause)()))
    lines = ["📋 <b>/status</b>", f"Upstox token: {tok}", f"बाजार: {mkt}", f"Kill-switch: {_try(_kill)}",
             f"Dashboard pause (PAPER + LIVE): {pz}", f"PAPER pause (/pause /resume): {ppz}"]
    for bot, key, sk in BOT_KEYS:
        lines.append(f"{PW.BOT_LABEL.get(bot, bot)}: signal_source = {_try(lambda: ES.source_of(settings_fn(key, symbol), sk))}")
    lines.append(f"✋ manual_profile (/paper strikes न दिल्यास): {_try(_manual_profile)} · /help")
    lines.append(_try(_vision_health))                                   # T-1: approval बटणं (can_ask) + listener
    lines.append(_try(lambda: ES.opinion(symbol)))
    tr = _try(trades_fn, default=[])
    lines.append(f"उघडे trades: {len(tr) if isinstance(tr, list) else tr}")
    lines.append("Exits (SL / target / वेळ) नेहमी चालू — pause / kill-switch फक्त नवे entries थांबवतात.")
    return "\n".join(lines)


def _vision_health():
    from vision import notify as VN
    return VN.health_line()


def _manual_profile():
    from vision import config as VC
    return VC.load("_global").get("manual_profile")


def _exits_text(t, settings_fn=None):
    """Abhi T-6 (DECISIONS 30): settings-driven bots ⇒ engine चे खरे exits (dashboard settings, TSL स्थिती); stored 100%-credit SL कधीच "SL"
    म्हणून नाही. इतर (manual / generic — stored ₹ levels तेच exits) ⇒ stored levels, नसल्यास "—" (₹0 नाही)."""
    bot = PW.exit_bot(t)
    if bot:
        from vision import config as VC
        key = VC.BOT_STRATEGY_KEY.get(bot, "1m_instant")
        ss = _try(lambda: settings_fn(key, t.get("symbol")), default=None) if settings_fn else PW.bot_settings(bot, t.get("symbol"))
        return PW.exit_status_text(t, bot, ss if isinstance(ss, dict) else None)
    return f"SL {PW._stored(t.get('sl_pnl_level'))} · target {PW._stored(t.get('target_pnl_level'))}"


def positions_text(trades_fn=None, settings_fn=None):
    tr = (trades_fn or open_trades)()
    if not tr:
        return "📂 <b>/positions</b>\nउघडा trade नाही."
    out = ["📂 <b>/positions</b>"]
    for t in tr:
        out.append(f"#{str(t.get('trade_id') or '')[-6:]} · {t.get('mode')} · {t.get('source')} · {t.get('symbol')} {t.get('strategy') or ''} "
                   f"{t.get('strikes_summary') or ''} · entry {str(t.get('entry_time'))[11:16]} · {_try(lambda: _exits_text(t, settings_fn))}")
    out.append("PAPER लगेच बंद: /exit &lt;id&gt; (SL / target Telegram वरून बदलत नाहीत)")
    return "\n".join(out)


def exit_trade(arg, by, trades_fn=None, token_fn=None, close_fn=None):
    """/exit <id> (पूर्ण trade_id किंवा /positions मधला #शेवटचा भाग) ⇒ फक्त PAPER, लगेच बंद. Pause / kill-switch तपासणी मुद्दाम नाही."""
    tid = str(arg or "").strip().lstrip("#")
    if not tid:
        return False, "वापर: /exit &lt;id&gt; (id: /positions मध्ये)"
    tr = (trades_fn or open_trades)()
    hits = [t for t in tr if str(t.get("trade_id")) == tid]
    if not hits and len(tid) >= 4:
        hits = [t for t in tr if str(t.get("trade_id") or "").endswith(tid)]
    if not hits:
        return False, f"❌ /exit: उघडा trade '{tid}' सापडला नाही (/positions)"
    if len(hits) > 1:
        return False, f"❌ /exit: '{tid}' अनेक trades शी जुळतो — पूर्ण id द्या"
    t = hits[0]
    if str(t.get("mode") or "").upper() != "PAPER":
        return False, f"⛔ /exit फक्त PAPER साठी — हा {t.get('mode')} trade; Telegram वरून LIVE ला हात नाही"
    if token_fn is None:
        import cloud_db
        token_fn = lambda: cloud_db.get_effective_upstox_token(None)  # noqa: E731
    if close_fn is None:
        from trading_engine import close_trade_manually as close_fn
    ok, res = close_fn(token_fn(), t["trade_id"], t["symbol"], t.get("product_type") or "D", exit_reason="TELEGRAM_EXIT",
                       exit_reason_detail=f"Telegram /exit ({by})")
    if not ok:
        return False, f"❌ /exit {t['trade_id']}: बंद झाला नाही — {res}"
    return True, f"🔴 /exit: PAPER {t['symbol']} {t.get('strategy') or ''} ({t['trade_id']}) बंद केला — exit संदेश / P&L पुढच्या watcher cycle ला"


def pause(by, set_fn=None):
    """फक्त PAPER-scope pause (paper/pause.py). Dashboard / LIVE चा global pause Telegram वरून बदलत नाही."""
    if set_fn is None:
        from . import pause as PP
        set_fn = PP.set_pause
    set_fn(True, by, f"Telegram /pause ({by})")
    return ("⏸ नवे <b>PAPER</b> entries थांबवले (bots, engine, ✋ /paper). LIVE / dashboard pause ला हात नाही. उघडे trades चे exits "
            "(SL / target / वेळ) चालूच राहतील. पुन्हा: /resume")


def resume(by, set_fn=None):
    """फक्त PAPER pause पुसतो — dashboard वरचा pause (असल्यास) तसाच राहतो."""
    if set_fn is None:
        from . import pause as PP
        set_fn = PP.set_pause
    set_fn(False, by, f"Telegram /resume ({by})")
    return "▶️ नवे PAPER entries पुन्हा चालू (approval मार्ग तसाच: Vision + ✅). Dashboard pause असल्यास तो वेगळा — तो तिथूनच."


def handle(cmd, by, send, arg=None, **deps):
    """रिटर्न (handled, label). cmd = '/status' इ.; arg = command नंतरचा मजकूर (/exit <id>)."""
    if cmd == "/status":
        send(status_text(**{k: v for k, v in deps.items() if k in ("token_fn", "market_fn", "kill_fn", "pause_fn", "settings_fn", "trades_fn", "paper_pause_fn")}))
        return True, "status"
    if cmd == "/positions":
        send(positions_text(deps.get("trades_fn"), deps.get("settings_fn")))
        return True, "positions"
    if cmd == "/pause":
        send(pause(by, deps.get("set_fn")))
        return True, "pause"
    if cmd == "/resume":
        send(resume(by, deps.get("set_fn")))
        return True, "resume"
    if cmd == "/exit":
        ok, msg = exit_trade(arg, by, deps.get("trades_fn"), deps.get("token_fn"), deps.get("close_fn"))
        send(msg)
        return ok, "exit" if ok else msg
    return False, "unknown"
