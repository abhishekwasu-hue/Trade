#!/usr/bin/env python3
"""PA standard deploy — READ-ONLY status block (Abhi runs it on the VPS; `scripts/deploy_pa_standard_vps.sh` prints it at the end).
Writes nothing (the engine store is opened read-only; settings through the dashboard getters). Never prints a secret: the Upstox token
check prints only ok / rejected / unknown.

  python3 scripts/pa_standard_status.py [--no-token-check] [--json]
Exit 0 = clean · 3 = a problem (an engine bot × symbol not PAPER, a model OFF, entry gate not models, Vision not human_confirm, a
symbol missing, token rejected).
"""
import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bots_common import one_bot as OB  # noqa: E402

BOT_KEY = OB.ON_KEY
VISION_BOT = OB.VISION_BOT
MODELS = ("E1", "E2", "E3", "E4")
NEED_SYMBOLS = ("NIFTY", "BANKNIFTY")


def last_engine_row(symbol, path=None):
    """The newest engine row of the symbol from the engine store, read-only (sqlite mode=ro) ⇒ {bar_ts, decision, models, why} | None."""
    import engine_signal as ES
    p = ES.db_path(path)
    if not os.path.exists(p):
        return None
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute("SELECT * FROM engine_signals WHERE symbol=? ORDER BY bar_ts DESC LIMIT 1", (str(symbol).upper(),)).fetchone()
    finally:
        c.close()
    if r is None:
        return None
    r = dict(r)
    pay = ES.row_payload(r)
    ents = [f"{str(e.get('model')).upper()}{'↑' if int(e.get('direction') or 0) > 0 else '↓'}" for e in pay.get("entries") or []
            if ES.entry_ok(e)]
    return {"bar_ts": r.get("bar_ts"), "decision": r.get("decision"), "entries": ents, "has_entries_key": "entries" in pay,
            "why": str(r.get("reason") or "")[:140]}


def resolved(settings):
    """Dashboard engine3_* + decision3 defaults ⇒ what the engine actually runs with (entry gate, daily_leg_read, cluster rule, range rule)."""
    import engine3_live as L
    from decision3 import settings as S3
    over = L.method_switches(settings or {})
    eff = {**S3.DEFAULTS, **over}
    return {"entry_gate": eff["entry_gate"], "daily_leg_read": eff["daily_leg_read"], "entry_cluster_rule": eff["entry_cluster_rule"],
            "range_state_rule": eff["range_state_rule"], "daily_range_rule": eff["daily_range_rule"],
            "entry_trigger_rule": eff.get("entry_trigger_rule"), "entry_area_refine": eff.get("entry_area_refine")}


def collect(io=None, token_check=True, token_fn=None, check_fn=None, row_fn=None):
    """Everything the block shows ⇒ dict (read only)."""
    from paper import engine_entry as EE
    io = io or OB.IO()
    st = {"bots": [], "problems": []}
    syms = OB.signal_symbols(io)
    st["signal_symbols"] = syms
    for s in NEED_SYMBOLS:
        if s not in syms:
            st["problems"].append(f"{s} not in signal_symbols (the engine does not run it)")
    for sym in syms:
        try:
            eff, raw = io.effective(BOT_KEY, sym) or {}, io.raw(BOT_KEY, sym) or {}
        except Exception as exc:                                         # noqa: BLE001
            st["bots"].append({"symbol": sym, "error": f"settings unreadable: {type(exc).__name__}"})
            st["problems"].append(f"{BOT_KEY} {sym}: settings unreadable")
            continue
        mode = OB._safe_mode(eff, raw)
        try:
            res = resolved(eff)
        except Exception as exc:                                         # noqa: BLE001 — a bad stored switch fails the engine closed
            res = {"error": str(exc)[:160]}
        row = {"symbol": sym, "trading_mode": mode, "symbol_enabled": bool(eff.get("symbol_enabled")),
               "signal_source": eff.get("signal_source"), "models": {m: EE.model_on(eff, m) for m in MODELS},
               "max_hits_per_zone": EE.max_hits(eff), **res}
        st["bots"].append(row)
        if mode != "PAPER":
            st["problems"].append(f"{BOT_KEY} {sym} trading_mode {mode} (must be PAPER — LIVE is never part of this deploy)")
        if row.get("entry_gate") != "models":
            st["problems"].append(f"{sym}: entry gate {row.get('entry_gate') or row.get('error')} (want models)")
        off = [m for m, on in row["models"].items() if not on]
        if off:
            st["problems"].append(f"{sym}: models OFF {'/'.join(off)}")
        if row.get("signal_source") != "engine" or not row["symbol_enabled"]:
            st["problems"].append(f"{sym}: 15M SRv2 not on the engine (signal_source {row.get('signal_source')}, "
                                  f"symbol_enabled {row['symbol_enabled']})")
    try:
        ob = OB.one_bot_status(io)
        st["live_untouched"] = ob.get("live_untouched") or []
        st["one_bot_line"] = ob.get("line")
    except Exception as exc:                                             # noqa: BLE001
        st["live_untouched"], st["one_bot_line"] = [], f"one-bot status unreadable: {type(exc).__name__}"
    try:
        from vision import config as VC
        vs = io.vision_load(VISION_BOT)
        st["vision"] = {"vision_mode": vs.get("vision_mode"), "approval_required": vs.get("approval_required"),
                        "symbols": vs.get("symbols"), "effective_paper": VC.effective_mode(vs, "PAPER"),
                        "effective_live": VC.effective_mode(vs, "LIVE")}
        if vs.get("vision_mode") != "human_confirm":
            st["problems"].append(f"Vision {VISION_BOT} vision_mode {vs.get('vision_mode')} (want human_confirm)")
        missing = [s for s in syms if s not in [str(x).upper() for x in vs.get("symbols") or []]]
        if missing:
            st["problems"].append(f"Vision symbols missing {'/'.join(missing)}")
    except Exception as exc:                                             # noqa: BLE001
        st["vision"] = {"error": f"{type(exc).__name__}"}
        st["problems"].append("Vision settings unreadable")
    st["token"] = "not checked"
    if token_check:
        try:
            if token_fn is None:
                import cloud_db
                token_fn = lambda: cloud_db.get_effective_upstox_token(None)  # noqa: E731
            tok = token_fn()
            if not tok:
                st["token"] = "missing"
            else:
                import engine_signal as ES
                st["token"] = str((check_fn or ES.token_check)(tok) or "unknown").split("\n")[0][:80]
            del tok
        except Exception as exc:                                         # noqa: BLE001
            st["token"] = f"unknown ({type(exc).__name__})"
        if st["token"] == "missing" or st["token"].startswith("rejected"):
            st["problems"].append(f"Upstox token {st['token']} (log in again)")
    st["last_rows"] = {}
    for sym in sorted(set(syms) | set(NEED_SYMBOLS)):
        try:
            st["last_rows"][sym] = (row_fn or last_engine_row)(sym)
        except Exception as exc:                                         # noqa: BLE001
            st["last_rows"][sym] = {"error": type(exc).__name__}
    st["ok"] = not st["problems"]
    return st


def render(st):
    out = ["==== PA standard status (read-only) ===="]
    out.append(f"signal symbols (engine run): {' / '.join(st.get('signal_symbols') or [])}")
    for b in st.get("bots") or []:
        if b.get("error"):
            out.append(f"  15M SRv2 {b['symbol']}: {b['error']}")
            continue
        ms = " ".join(f"{m}{'✓' if on else '✗'}" for m, on in b["models"].items())
        out.append(f"  15M SRv2 {b['symbol']:<10} mode {b['trading_mode']} · on {b['symbol_enabled']} · source {b.get('signal_source')} · "
                   f"entry gate {b.get('entry_gate')} · models {ms} · max_hits_per_zone {b['max_hits_per_zone']}")
        out.append(f"      daily_leg_read {b.get('daily_leg_read')} · range rule {b.get('daily_range_rule')} (row state "
                   f"{b.get('range_state_rule')}) · "
                   f"entry clusters {b.get('entry_cluster_rule')} · trigger {b.get('entry_trigger_rule')} · "
                   f"area refine {b.get('entry_area_refine')}")
    v = st.get("vision") or {}
    out.append(f"Vision {VISION_BOT}: vision_mode {v.get('vision_mode')} (effective PAPER {v.get('effective_paper')}, LIVE "
               f"{v.get('effective_live')}) · approval_required {v.get('approval_required')} · symbols {v.get('symbols')}")
    live = st.get("live_untouched") or []
    out.append("LIVE: " + ("none of the engine bots is LIVE · other LIVE combos (untouched): " + ", ".join(live) if live else
                           "none of the engine bots is LIVE · no other LIVE combo seen"))
    out.append(f"one-bot: {st.get('one_bot_line')}")
    out.append(f"Upstox token check: {st.get('token')}")
    for sym, r in (st.get("last_rows") or {}).items():
        if not r:
            out.append(f"last engine row {sym}: none")
        elif r.get("error"):
            out.append(f"last engine row {sym}: unreadable ({r['error']})")
        else:
            out.append(f"last engine row {sym}: {r['bar_ts']} {r['decision']}" + (f" · entries {' '.join(r['entries'])}" if r["entries"]
                                                                                 else "") + ("" if r["has_entries_key"] else
                                                                                             " · (older row: no entry-models payload)"))
    out.append("✅ clean" if st.get("ok") else "❌ " + "; ".join(st.get("problems") or []))
    return "\n".join(out)


def main(argv=None, io=None, out=print, **kw):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-token-check", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    st = collect(io, token_check=not a.no_token_check, **kw)
    out(json.dumps(st, ensure_ascii=False, default=str, indent=1) if a.json else render(st))
    return 0 if st["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
