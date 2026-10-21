"""PA standard deploy helpers (scripts/pa_standard_settings.py, scripts/pa_standard_status.py; run by Abhi on the VPS, never by a
session): save ⇒ apply ⇒ revert restores exactly (absent keys removed); PAPER only — a LIVE engine-bot combo stops everything before any
write; BANKNIFTY joins the signal symbols only through the PAPER path; the status block is read-only, flags every problem and never
prints the token. Fake dashboard storage only (no network, no DB)."""
import copy
import json
import os
import subprocess

import pytest

from bots_common import one_bot as OB
from scripts import pa_standard_settings as PS
from scripts import pa_standard_status as PST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = "SECRET-TOKEN-VALUE-123"


class FakeIO(PS.IO):
    def __init__(self, store=None, vision=None, symbols=("NIFTY",), symbols_raw=OB.ABSENT):
        self.by = "test"
        self.store = copy.deepcopy(store or {})
        self.vision = dict(vision or {})
        self.symbols = list(symbols)
        self.symbols_raw = symbols_raw
        self.writes = []

    def raw(self, strategy, symbol):
        return dict(self.store.get((strategy, symbol), {}))

    def effective(self, strategy, symbol):
        return {"trading_mode": "PAPER", **self.raw(strategy, symbol)}

    def save(self, strategy, symbol, changes):
        self.writes.append((strategy, symbol, dict(changes)))
        self.store.setdefault((strategy, symbol), {}).update(changes)

    def remove(self, strategy, symbol, keys):
        self.writes.append((strategy, symbol, ("remove", tuple(keys))))
        for k in keys:
            self.store.get((strategy, symbol), {}).pop(k, None)

    def vision_raw(self, bot):
        return dict(self.vision)

    def vision_load(self, bot):
        return {"vision_mode": "off", "approval_required": True, "symbols": ["NIFTY"], **self.vision}

    def vision_save(self, bot, changes):
        self.vision.update(changes)

    def vision_unset(self, bot, keys):
        gone = [k for k in keys if k in self.vision]
        for k in gone:
            self.vision.pop(k)
        return gone

    def signal_symbols(self):
        return list(self.symbols)

    def signal_symbols_raw(self):
        return self.symbols_raw

    def save_signal_symbols(self, symbols):
        self.symbols = list(symbols)
        self.symbols_raw = list(symbols)

    def restore_signal_symbols(self, raw, symbols):
        self.symbols_raw = raw
        self.symbols = ["NIFTY", "BANKNIFTY"] if raw == OB.ABSENT and self.default_both else list(symbols)

    default_both = False

    def apply_signal_symbols(self, before, after):
        self.applied = (list(before), list(after))
        return {"ok": True, "applied": ["15m_dynamic_sr"], "skipped_live": [], "failed": None}

    def paper_cfg(self):
        return {"instruments": {s: {"enabled": True} for s in self.symbols}}

    def crontab(self):
        return "* * * * * python3 scripts/engine_signal_run.py --engine decision3 # one-bot-engine\n" \
               "* * * * * python3 srv2_momentum_reversal_strategy.py\n"


BOT = PS.BOT_KEY


def test_save_apply_revert_restores_exactly(tmp_path):
    f = str(tmp_path / "prev.json")
    io = FakeIO({(BOT, "NIFTY"): {"engine3_entry_gate": "legacy_k", "engine3_model_e2_on": False}}, vision={"vision_mode": "notify"})
    before = copy.deepcopy(io.store)
    assert PS.main(["save", "--file", f], io=io, out=lambda *a: None) == 0
    st = json.load(open(f))
    assert st["bots"]["NIFTY"]["keys"]["engine3_entry_gate"] == "legacy_k" and st["bots"]["NIFTY"]["keys"]["engine3_model_e1_on"] == OB.ABSENT
    assert st["vision"]["vision_mode"] == "notify" and st["signal_symbols_raw"] == OB.ABSENT
    assert PS.main(["apply", "--file", f], io=io, out=lambda *a: None) == 0
    for sym in ("NIFTY", "BANKNIFTY"):
        raw = io.raw(BOT, sym)
        assert raw["engine3_entry_gate"] == "" and all(raw[k] is True for k in PS.MODEL_KEYS)
    assert io.symbols == ["NIFTY", "BANKNIFTY"] and io.applied == (["NIFTY"], ["NIFTY", "BANKNIFTY"])
    io.vision["vision_mode"] = "human_confirm"                                      # the deploy script's vision.config set
    io.save(BOT, "NIFTY", {"lots": 3})                                              # an unrelated key changed meanwhile: kept
    assert PS.main(["save", "--file", f], io=io, out=lambda *a: None) == 0 and json.load(open(f)) == st   # first save wins
    assert PS.main(["revert", "--file", f], io=io, out=lambda *a: None) == 0
    assert io.raw(BOT, "NIFTY") == {**before[(BOT, "NIFTY")], "lots": 3}
    assert io.raw(BOT, "BANKNIFTY") == {}                                           # absent before ⇒ removed
    assert io.vision["vision_mode"] == "notify" and io.symbols == ["NIFTY"] and os.path.exists(f + ".reverted")


def test_vision_mode_absent_before_is_unset_on_revert(tmp_path):
    f = str(tmp_path / "prev.json")
    io = FakeIO(symbols=("NIFTY", "BANKNIFTY"))
    PS.main(["save", "--file", f], io=io, out=lambda *a: None)
    io.vision["vision_mode"] = "human_confirm"
    PS.main(["revert", "--file", f], io=io, out=lambda *a: None)
    assert "vision_mode" not in io.vision


def test_a_live_engine_bot_stops_before_any_write(tmp_path):
    f = str(tmp_path / "prev.json")
    io = FakeIO({(BOT, "BANKNIFTY"): {"trading_mode": "LIVE"}})
    lines = []
    assert PS.main(["plan", "--file", f], io=io, out=lines.append) == 3
    assert PS.main(["apply", "--file", f], io=io, out=lines.append) == 3
    assert io.writes == [] and io.symbols == ["NIFTY"]                              # nothing written, BANKNIFTY not added
    assert any("STOP" in x and "BANKNIFTY" in x and "LIVE" in x for x in lines)


def test_revert_never_touches_a_combo_that_became_live(tmp_path):
    f = str(tmp_path / "prev.json")
    io = FakeIO(symbols=("NIFTY", "BANKNIFTY"))
    PS.main(["save", "--file", f], io=io, out=lambda *a: None)
    PS.main(["apply", "--file", f], io=io, out=lambda *a: None)
    io.store[(BOT, "BANKNIFTY")]["trading_mode"] = "LIVE"
    n = len(io.writes)
    lines = []
    assert PS.main(["revert", "--file", f], io=io, out=lines.append) == 4
    assert not [w for w in io.writes[n:] if w[1] == "BANKNIFTY"] and any("LIVE untouched" in x for x in lines)


def _status(io, **kw):
    return PST.collect(io, token_fn=lambda: TOKEN, check_fn=lambda tok: "ok" if tok == TOKEN else "rejected (HTTP 401)",
                       row_fn=lambda s: {"bar_ts": "2026-10-21 10:30:00", "decision": "setup", "entries": ["E2↓"], "has_entries_key": True,
                                         "why": "x"}, **kw)


def _clean_io():
    on = {"symbol_enabled": True, "signal_source": "engine", "engine3_entry_gate": "", **{k: True for k in PS.MODEL_KEYS}}
    return FakeIO({(BOT, "NIFTY"): dict(on), (BOT, "BANKNIFTY"): dict(on)}, symbols=("NIFTY", "BANKNIFTY"),
                  vision={"vision_mode": "human_confirm", "symbols": ["NIFTY", "BANKNIFTY"]})


def test_status_block_clean_and_never_prints_the_token():
    st = _status(_clean_io())
    txt = PST.render(st)
    assert st["ok"], st["problems"]
    assert TOKEN not in txt and TOKEN not in json.dumps(st, default=str) and "Upstox token check: ok" in txt
    assert "entry gate models" in txt and "E1✓ E2✓ E3✓ E4✓" in txt and "vision_mode human_confirm" in txt
    assert "daily_leg_read compare" in txt and "entry clusters cluster" in txt and "max_hits_per_zone 2" in txt
    assert "mode PAPER" in txt and "LIVE: none of the engine bots is LIVE" in txt
    assert "last engine row BANKNIFTY: 2026-10-21 10:30:00 setup · entries E2↓" in txt


@pytest.mark.parametrize("change,word", [
    (lambda io: io.store[(BOT, "BANKNIFTY")].update(trading_mode="LIVE"), "LIVE is never part"),
    (lambda io: io.store[(BOT, "NIFTY")].update(engine3_model_e3_on=False), "models OFF E3"),
    (lambda io: io.store[(BOT, "NIFTY")].update(engine3_entry_gate="legacy_k"), "entry gate legacy_k"),
    (lambda io: io.vision.update(vision_mode="notify"), "want human_confirm"),
    (lambda io: setattr(io, "symbols", ["NIFTY"]), "BANKNIFTY not in signal_symbols"),
])
def test_status_flags_each_problem(change, word):
    io = _clean_io()
    change(io)
    st = _status(io)
    assert not st["ok"] and any(word in p for p in st["problems"]), st["problems"]


def test_status_token_rejected_is_a_problem_and_read_only():
    io = _clean_io()
    st = PST.collect(io, token_fn=lambda: TOKEN, check_fn=lambda tok: "rejected (HTTP 401 UDAPI100050)", row_fn=lambda s: None)
    assert not st["ok"] and any("rejected" in p for p in st["problems"]) and io.writes == []
    assert "last engine row NIFTY: none" in PST.render(st)


def test_last_engine_row_reads_the_store_read_only(tmp_path):
    import engine_signal as ES
    p = str(tmp_path / "es.db")
    ES.save({"symbol": "BANKNIFTY", "bar_ts": "2026-10-21 10:30:00", "computed_at": "x", "decision": "setup", "gate": None,
             "direction": None, "level_lo": None, "level_hi": None, "entry": None, "invalidation": None, "target": None, "grade": None,
             "reason": "r", "payload": json.dumps({"entries": [{"model": "E1", "direction": 1, "visit_id": "v"}]})}, p)
    r = PST.last_engine_row("BANKNIFTY", p)
    assert r["bar_ts"] == "2026-10-21 10:30:00" and r["entries"] == ["E1↑"] and r["has_entries_key"]
    assert PST.last_engine_row("NIFTY", p) is None and PST.last_engine_row("NIFTY", str(tmp_path / "none.db")) is None


def test_deploy_script_shape():
    src = open(os.path.join(ROOT, "scripts", "deploy_pa_standard_vps.sh"), encoding="utf-8").read()
    assert src.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in src
    assert subprocess.run(["bash", "-n", os.path.join(ROOT, "scripts", "deploy_pa_standard_vps.sh")]).returncode == 0
    for need in ("/root/pa_standard_prev_settings.json", "bash scripts/deploy_one_bot.sh", "bash scripts/deploy_one_bot.sh --revert",
                 "vision.config set srv2_momentum_reversal vision_mode human_confirm --by abhi", "pa_standard_settings.py apply",
                 "pa_standard_settings.py revert", "scripts/pa_standard_status.py"):
        assert need in src, need
    assert src.index("pa_standard_settings.py\" save") < src.index("bash scripts/deploy_one_bot.sh\n")   # saved before anything changes
    assert "echo $UPSTOX" not in src and "cat .env" not in src and "cat ./.env" not in src
