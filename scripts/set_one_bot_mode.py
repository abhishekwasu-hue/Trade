#!/usr/bin/env python3
"""🎯 One bot mode (Abhi): फक्त 15M SRv2 (`15m_dynamic_sr`) ON — dashboard setting `signal_symbols` चे symbols (default NIFTY / BANKNIFTY;
बाकी index उदा. SENSEX वर 15M SRv2 सुद्धा OFF), PAPER, signal_source = engine (decision3).
बाकी entry-capable bots OFF (bot जे field तपासतो तेच — `symbol_enabled` / `srv3_shadow_enabled`); काहीही delete नाही; Abhi चे strikes / ITM
depth / hedge / lots / SL / TSL / target / exits तसेच; LIVE combo ला हात नाही (इशारा). Dashboard चीच storage (Supabase strategy_settings,
Vision settings, PAPER instruments local override) ⇒ dashboard तेच दाखवतो. यादी / नियम: `bots_common/one_bot.py`.

  python3 scripts/set_one_bot_mode.py --dry-run      # before / after table, काहीच लिहीत नाही
  python3 scripts/set_one_bot_mode.py                # लिहितो; before-state ⇒ data/one_bot_before.json (आधीच असेल तर ओव्हरराइट नाही)
  python3 scripts/set_one_bot_mode.py --revert       # before-state ⇒ तंतोतंत आधीचं
  python3 scripts/set_one_bot_mode.py --status       # one_bot_status() (pre-open ओळ)
Auto traders (oi_signal / credit_spread / oi_greeks — settings flag नाही) ⇒ `scripts/install_engine_schedule.sh` (cron).
Dashboard वर `signal_symbols` सेव्ह ⇒ याच plan चा signal-symbols भाग आपोआप लागतो (`one_bot.apply_signal_symbols`, Abhi 9a) — ही script
पहिल्या deploy / revert / status साठी, किंवा dashboard ने "पूर्ण लागला नाही" सांगितलं तर.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bots_common import one_bot as OB  # noqa: E402

DEFAULT_STATE = os.path.join(ROOT, "data", "one_bot_before.json")


def _print_status(st):
    print(f"\nAfter (dashboard getters) · signal_symbols: {' / '.join(st.get('signal_symbols') or [])}")
    for r in st["bots"]:
        note = "  (not a signal symbol — data only)" if r.get("signal_symbol") is False and r["strategy"] == OB.ON_KEY else ""
        print(f"  {r['bot']:<20} {r['symbol']:<11} {'ON ' if r.get('on') else 'off'}  mode {r.get('trading_mode')}  "
              f"signal_source {r.get('signal_source')}  entry_mode {r.get('entry_mode')}{note}")
    print(f"  Vision {OB.VISION_BOT}: {st['vision']}")
    print(f"  auto traders cron: {st['auto_traders']} · engine cron: {st['engine_cron']} · 15M SRv2 cron: {st['srv2_cron']}")
    print(f"\n{st['line']}")


def main(argv=None, io=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--state", default=DEFAULT_STATE, help="before-state JSON")
    a = ap.parse_args(argv)
    io = io or OB.IO()
    if a.status:
        st = OB.one_bot_status(io)
        _print_status(st)
        return 0 if st["ok"] else 3
    if a.revert:
        if not os.path.exists(a.state):
            print(f"❌ before-state नाही: {a.state} — revert करता येत नाही")
            return 2
        st = json.load(open(a.state, encoding="utf-8"))
        if a.dry_run:
            print(json.dumps(st, ensure_ascii=False, indent=1))
            return 0
        for w in OB.revert(io, st):
            print(w)
        os.replace(a.state, a.state + ".reverted")
        print(f"✅ revert झाला (before-state ⇒ {a.state}.reverted)")
        _print_status(OB.one_bot_status(io))
        return 0
    changes, warns = OB.plan(io)
    print("Before / after (one bot mode):")
    print(OB.table(changes))
    for w in warns:
        print(w)
    if a.dry_run:
        print("\n(dry-run: काहीच लिहिलं नाही)")
        return 0
    if os.path.exists(a.state):
        print(f"ℹ️ before-state आधीच आहे ({a.state}) — तसाच ठेवला (पहिल्या run चा; revert त्यावरूनच)")
    else:
        os.makedirs(os.path.dirname(a.state) or ".", exist_ok=True)
        json.dump(OB.before_state(io, changes), open(a.state, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        print(f"before-state ⇒ {a.state}")
    n = OB.apply(io, changes)
    print(f"✅ {n} bot × symbol settings लिहिले (+ Vision + PAPER instruments)")
    st = OB.one_bot_status(io)
    _print_status(st)
    return 0 if st["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
