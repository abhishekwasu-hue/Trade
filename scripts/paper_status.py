#!/usr/bin/env python3
"""PAPER TRADING status (Abhi): is the 15M SRv2 bot ready to trade PAPER at the open, per symbol? Read-only — changes nothing.

Per symbol it prints exactly one of
    PAPER TRADING: ACTIVE — NIFTY
    PAPER TRADING: NOT ACTIVE — NIFTY: <every reason>
and exits 0 only when every symbol is ACTIVE (1 otherwise) — so a VPS block can stop on it; never a false OK.

What ACTIVE needs (each from the same getters the bot uses):
  • 15M SRv2 settings: symbol_enabled, trading_mode PAPER, signal_source engine, lots > 0 (spread or naked);
  • the symbol in the dashboard's signal_symbols; its PAPER instrument enabled (config.yaml + VPS local override);
  • Vision: approval_required on and the symbol in the srv2 approval list (✅ card goes out);
  • no PAPER pause, no dashboard trading pause;
  • cron: the 15M SRv2 bot, the engine (decision3) and trade_monitor (exits) — uncommented, never --mode LIVE;
  • services: vision_worker (sends the ✅ card) and vision_telegram (handles ✅) active;
  • Telegram / approval settings present (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_APPROVER_IDS, VISION_CALLBACK_SECRET) — names
    only, values are never printed; an Upstox token present (it is refreshed by the morning login).
LIVE is never touched here; a LIVE 15M SRv2 for a symbol is a NOT ACTIVE reason (PAPER only).

  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_status.py [--symbols NIFTY,BANKNIFTY]
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ON_KEY = "15m_dynamic_sr"
SERVICES = ("vision_worker", "vision_telegram")
ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_APPROVER_IDS", "VISION_CALLBACK_SECRET")
CRON = {"15M SRv2 bot": "srv2_momentum_reversal_strategy.py", "engine (decision3)": "scripts/engine_signal_run.py",
        "trade_monitor (exits)": "trade_monitor.py"}


def _sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except Exception:                                                    # noqa: BLE001
        return None


class IO:
    """Every outside read in one place (tests inject a fake)."""

    def settings(self, symbol):
        import cloud_db
        return cloud_db.get_strategy_settings(ON_KEY, symbol)

    def signal_symbols(self):
        import cloud_db
        return [str(x).upper() for x in cloud_db.get_signal_symbols()]

    def paper_instrument(self, symbol):
        from paper import config as PC
        return PC.enabled(symbol)

    def vision(self):
        from bots_common import one_bot as OB
        from vision import config as VC
        return VC.load(OB.VISION_BOT)

    def paper_paused(self):
        from paper import pause as PP
        return PP.get()

    def trading_pause(self):
        import cloud_db
        return cloud_db.get_trading_pause_settings()

    def crontab(self):
        return _sh(["crontab", "-l"])

    def service(self, name):
        return (_sh(["systemctl", "is-active", name]) or "unknown").strip() or "unknown"

    def env(self, name):
        return bool((os.environ.get(name) or "").strip())

    def token(self):
        import cloud_db
        return bool(cloud_db.get_effective_upstox_token(None))


def cron_line(text, script):
    """"on" / "off" (only commented) / "absent" / "LIVE" / "unknown"."""
    from bots_common import one_bot as OB
    if text is None:
        return "unknown"
    lines = text.splitlines()
    act = [x for x in lines if script in x and not x.lstrip().startswith("#")]
    if any(OB.LIVE_RE.search(x) for x in act):
        return "LIVE"
    return "on" if act else ("off" if any(script in x for x in lines) else "absent")


def check(symbols, io=None):
    """{symbol: [reasons]} (empty = ACTIVE) and the shared lines printed above the verdicts."""
    io = io or IO()
    shared, common = [], []

    def guard(name, fn, default=None):
        try:
            return fn()
        except Exception as exc:                                         # noqa: BLE001 — unreadable ⇒ a reason, never a pass
            common.append(f"{name} unreadable ({type(exc).__name__}: {exc})")
            return default
    sig = guard("signal_symbols", io.signal_symbols, [])
    vis = guard("Vision settings", io.vision, {}) or {}
    pp = guard("PAPER pause", io.paper_paused, {"paused": True}) or {}
    tp = guard("trading pause", io.trading_pause, {"paused": True}) or {}
    ctext = guard("crontab", io.crontab)
    shared.append(f"signal_symbols: {' / '.join(sig) or '—'} · Vision approval_required {vis.get('approval_required')} · Vision symbols "
                  f"{' / '.join(str(x).upper() for x in vis.get('symbols') or []) or '—'}")
    if not vis.get("approval_required", False):
        common.append("Vision approval_required OFF")
    if pp.get("paused"):
        common.append(f"PAPER pause ON ({pp.get('reason') or '/resume to clear'})")
    if tp.get("paused"):
        common.append(f"dashboard trading pause ON ({tp.get('reason') or '—'})")
    for name, script in CRON.items():
        st = cron_line(ctext, script)
        shared.append(f"cron {name}: {st}")
        if st != "on":
            common.append(f"cron {name} {st}")
    for s in SERVICES:
        st = guard(f"service {s}", lambda s=s: io.service(s), "unknown")
        shared.append(f"service {s}: {st}")
        if st != "active":
            common.append(f"service {s} {st}")
    for e in ENV:
        ok = guard(e, lambda e=e: io.env(e), False)
        shared.append(f"{e}: {'set' if ok else 'MISSING'}")
        if not ok:
            common.append(f"{e} missing (.env)")
    tok = guard("Upstox token", io.token, False)
    shared.append(f"Upstox token: {'present' if tok else 'MISSING'}")
    if not tok:
        common.append("Upstox token missing — do the morning login")
    out = {}
    vsyms = [str(x).upper() for x in vis.get("symbols") or []]
    for sym in symbols:
        why = list(common)
        st = guard(f"{sym} settings", lambda sym=sym: io.settings(sym), None)
        if st is None:
            why.append("15M SRv2 settings unreadable")
        else:
            mode = str(st.get("trading_mode", "PAPER")).upper()
            if mode != "PAPER":
                why.append(f"15M SRv2 mode {mode} (PAPER only)")
            if not st.get("symbol_enabled", sym == "NIFTY"):
                why.append("15M SRv2 symbol_enabled OFF")
            if str(st.get("signal_source", "own")) != "engine":
                why.append(f"signal_source {st.get('signal_source')} (needs engine)")
            lots = int(st.get("lots") or 0) if st.get("credit_spread_enabled", True) else 0
            naked = int(st.get("naked_lots", st.get("lots")) or 0) if st.get("naked_enabled", True) else 0
            if lots <= 0 and naked <= 0:
                why.append("no lots (spread and naked both 0 / off)")
        if sym not in sig:
            why.append("not in the dashboard's signal_symbols")
        if not guard(f"{sym} PAPER instrument", lambda sym=sym: io.paper_instrument(sym), False):
            why.append("PAPER instrument disabled (config.yaml / data/paper_local.yaml)")
        if sym not in vsyms:
            why.append("not in the Vision approval list (no ✅ card)")
        out[sym] = why
    return out, shared


def main(argv=None, io=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NIFTY,BANKNIFTY")
    a = ap.parse_args(argv)
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    res, shared = check(syms, io)
    for line in shared:
        print("  " + line)
    for sym in syms:
        print(f"PAPER TRADING: ACTIVE — {sym}" if not res[sym] else f"PAPER TRADING: NOT ACTIVE — {sym}: " + "; ".join(res[sym]))
    return 0 if all(not v for v in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
