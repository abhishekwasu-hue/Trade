#!/usr/bin/env python3
"""PA standard deploy (Abhi 21 Oct) — the bot settings tonight's PAPER deploy changes, saved before and restored on revert. Run by Abhi on
the VPS through `scripts/deploy_pa_standard_vps.sh` (never by a session). PAPER only: every write is refused for a bot × symbol whose
trading_mode is not PAPER (effective AND stored row — `bots_common.one_bot._combo_mode`); LIVE is never touched. No secret is printed.

What it touches (dashboard storage only — the same keys the dashboard writes):
  • 15M SRv2 (`15m_dynamic_sr`, the bot that receives engine signals) per signal symbol: `engine3_entry_gate` = "" (empty = the method =
    the entry models E1–E4), `engine3_model_e1_on` … `engine3_model_e4_on` = True;
  • `signal_symbols` (the engine run's symbols): BANKNIFTY added when missing (PAPER-only: the 15M SRv2 BANKNIFTY combo must be PAPER),
    then the one-bot signal-symbols part applied (`one_bot.apply_signal_symbols`: 15M SRv2 on / Vision symbols / PAPER instruments);
  • Vision `srv2_momentum_reversal.vision_mode` is saved here; it is SET by the deploy script through `python3 -m vision.config set …`
    and restored here on revert (absent before ⇒ unset).

  python3 scripts/pa_standard_settings.py save   [--file F]   # current values ⇒ F (kept if F exists: the first save wins)
  python3 scripts/pa_standard_settings.py apply  [--file F]   # engine3 keys + signal symbols (exit 3 = stopped, LIVE would be touched)
  python3 scripts/pa_standard_settings.py revert [--file F]   # F ⇒ exactly the values before (absent keys removed); F ⇒ F.reverted
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bots_common import one_bot as OB  # noqa: E402

DEFAULT_FILE = "/root/pa_standard_prev_settings.json"
BOT_KEY = OB.ON_KEY                                                       # 15m_dynamic_sr
VISION_BOT = OB.VISION_BOT                                                # srv2_momentum_reversal
MODEL_KEYS = tuple(f"engine3_model_e{i}_on" for i in range(1, 5))
WANT = {"engine3_entry_gate": "", **{k: True for k in MODEL_KEYS}}      # "" = the method = entry models (engine3_live.METHOD_SWITCHES)
NEED_SYMBOLS = ("NIFTY", "BANKNIFTY")
ABSENT = OB.ABSENT


class IO(OB.IO):
    """one_bot's dashboard storage + the raw Vision row + signal_symbols writes (tests replace these methods)."""

    def vision_raw(self, bot):
        from vision import store as VS
        with VS.connect(None) as c:
            r = c.execute("SELECT json FROM vision_settings WHERE bot=?", (bot,)).fetchone()
        return json.loads(r[0]) if r else {}

    def vision_unset(self, bot, keys):
        from vision import config as VC
        return VC.unset(bot, keys, by=getattr(self, "by", "pa_standard_settings"))

    def save_signal_symbols(self, symbols):
        import cloud_db
        if not cloud_db.save_signal_symbols(symbols):
            raise RuntimeError("signal_symbols save failed")

    def signal_symbols_raw(self):
        import cloud_db
        return (cloud_db.get_strategy_settings_raw(cloud_db.SIGNAL_SYMBOLS_STRATEGY_KEY, cloud_db.SIGNAL_SYMBOLS_SYMBOL_KEY) or {}).get(
            "signal_symbols", ABSENT)

    def restore_signal_symbols(self, raw, symbols):
        """revert: the stored signal_symbols back — absent before ⇒ the key removed (the dashboard default again)."""
        import cloud_db
        if raw == ABSENT:
            self.remove(cloud_db.SIGNAL_SYMBOLS_STRATEGY_KEY, cloud_db.SIGNAL_SYMBOLS_SYMBOL_KEY, ["signal_symbols"])
        else:
            self.save_signal_symbols(symbols)

    def apply_signal_symbols(self, before, after):
        return OB.apply_signal_symbols(before=before, after=after, io=self, by=getattr(self, "by", "pa_standard_settings"))


def snapshot(io):
    """The current stored values of everything the deploy changes ⇒ dict (JSON-able). Stored (raw) values, ABSENT when not stored."""
    syms = OB.signal_symbols(io)
    bots = {}
    for sym in sorted(set(syms) | set(NEED_SYMBOLS)):
        raw = io.raw(BOT_KEY, sym) or {}
        bots[sym] = {"keys": {k: raw.get(k, ABSENT) for k in WANT}, "trading_mode": OB._safe_mode(io.effective(BOT_KEY, sym), raw)}
    vr = io.vision_raw(VISION_BOT)
    return {"kind": "pa_standard_prev", "bot": BOT_KEY, "signal_symbols": syms, "signal_symbols_raw": io.signal_symbols_raw(),
            "bots": bots, "vision": {"bot": VISION_BOT, "vision_mode": vr.get("vision_mode", ABSENT)}}


def plan(io):
    """⇒ (changes [(symbol, {key: value})], add_symbols [..], stop reason | None). Any engine bot × symbol not PAPER ⇒ stop (LIVE)."""
    syms = OB.signal_symbols(io)
    add = [s for s in NEED_SYMBOLS if s not in syms]
    target = list(dict.fromkeys([*syms, *add]))
    changes, live = [], []
    for sym in target:
        mode = OB._combo_mode(io, BOT_KEY, sym)
        if mode != "PAPER":
            live.append(f"{BOT_KEY} {sym} trading_mode {mode}")
            continue
        raw = io.raw(BOT_KEY, sym) or {}
        kv = {k: v for k, v in WANT.items() if raw.get(k, ABSENT) != v}
        if kv:
            changes.append((sym, kv))
    stop = None
    if live:
        stop = ("❌ STOP: the engine bot is not PAPER for " + "; ".join(live) + " — this deploy changes PAPER settings only; nothing "
                "written (LIVE untouched). Set that combo back to PAPER from the dashboard first, or drop the symbol.")
    return changes, add, stop


def apply(io, out=print):
    """Writes the plan (PAPER combos only; each write re-checks the mode). Returns 0, or 3 when stopped (nothing written)."""
    changes, add, stop = plan(io)
    if stop:
        out(stop)
        return 3
    if add:
        before = OB.signal_symbols(io)
        after = list(dict.fromkeys([*before, *add]))
        io.save_signal_symbols(after)
        res = io.apply_signal_symbols(before, after)
        out(f"signal_symbols {'/'.join(before)} ⇒ {'/'.join(after)} · one-bot parts: applied {res.get('applied')} "
            f"skipped_live {res.get('skipped_live')} failed {res.get('failed')}")
        if not res.get("ok"):
            out("❌ signal symbols part not fully applied — see above (revert: bash scripts/deploy_pa_standard_vps.sh --revert)")
            return 3
    for sym, kv in changes:
        if OB._combo_mode(io, BOT_KEY, sym) != "PAPER":                    # race: re-check right before the write
            out(f"❌ STOP: {BOT_KEY} {sym} is no longer PAPER — not written")
            return 3
        io.save(BOT_KEY, sym, kv)
        out(f"✅ {BOT_KEY} {sym}: " + ", ".join(f"{k}={json.dumps(v)}" for k, v in kv.items()))
    if not changes and not add:
        out("ℹ️ engine settings already as wanted — nothing written")
    return 0


def revert(io, st, out=print):
    """The saved values back, exactly (stored ⇒ written, ABSENT ⇒ key removed); a combo that is not PAPER now ⇒ skipped (LIVE untouched)."""
    warns = 0
    for sym, b in (st.get("bots") or {}).items():
        mode = OB._combo_mode(io, BOT_KEY, sym)
        if mode != "PAPER":
            out(f"⚠️ {BOT_KEY} {sym}: now {mode} ⇒ not reverted (LIVE untouched)")
            warns += 1
            continue
        keys = b.get("keys") or {}
        put = {k: v for k, v in keys.items() if v != ABSENT}
        gone = [k for k, v in keys.items() if v == ABSENT]
        if put:
            io.save(BOT_KEY, sym, put)
        if gone:
            io.remove(BOT_KEY, sym, gone)
        out(f"↩️ {BOT_KEY} {sym}: restored {sorted(put)} · removed {sorted(gone)}")
    raw = st.get("signal_symbols_raw", ABSENT)
    now = OB.signal_symbols(io)
    before = list(st.get("signal_symbols") or now)
    if [s.upper() for s in now] != [s.upper() for s in before]:
        io.restore_signal_symbols(raw, before)
        res = io.apply_signal_symbols(now, before)
        out(f"↩️ signal_symbols {'/'.join(now)} ⇒ {'/'.join(before)} · one-bot parts ok={res.get('ok')}")
    vm = (st.get("vision") or {}).get("vision_mode", ABSENT)
    if vm == ABSENT:
        out(f"↩️ Vision {VISION_BOT}.vision_mode: unset {io.vision_unset(VISION_BOT, ['vision_mode']) or '—'}")
    else:
        io.vision_save(VISION_BOT, {"vision_mode": vm})
        out(f"↩️ Vision {VISION_BOT}.vision_mode = {vm}")
    return 0 if not warns else 4


def main(argv=None, io=None, out=print):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("save", "apply", "revert", "plan"))
    ap.add_argument("--file", default=DEFAULT_FILE)
    a = ap.parse_args(argv)
    io = io or IO(by="deploy_pa_standard")
    if a.cmd == "save":
        if os.path.exists(a.file):
            out(f"ℹ️ {a.file} already exists — kept (the first save is the one revert restores)")
            return 0
        st = snapshot(io)
        os.makedirs(os.path.dirname(a.file) or ".", exist_ok=True)
        with open(a.file, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1, default=str)
        out(f"saved ⇒ {a.file}: signal_symbols {'/'.join(st['signal_symbols'])} · vision_mode {st['vision']['vision_mode']} · "
            + " · ".join(f"{s} {b['trading_mode']}" for s, b in st["bots"].items()))
        return 0
    if a.cmd == "plan":
        changes, add, stop = plan(io)
        out(json.dumps({"changes": changes, "add_symbols": add, "stop": stop}, ensure_ascii=False, default=str))
        return 3 if stop else 0
    if a.cmd == "apply":
        return apply(io, out)
    if not os.path.exists(a.file):
        out(f"❌ {a.file} not found — nothing to restore")
        return 2
    with open(a.file, encoding="utf-8") as f:
        st = json.load(f)
    rc = revert(io, st, out)
    os.replace(a.file, a.file + ".reverted")
    out(f"saved values restored ({a.file} ⇒ {a.file}.reverted)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
