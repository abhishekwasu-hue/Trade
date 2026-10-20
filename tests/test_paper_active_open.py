"""Abhi (PAPER at the open): ✅ ⇒ the PAPER order at once (one entry, the cron cycle and ✅ share a lock), the spread target from the
dashboard, SL / target hits named on Telegram, the VPS status check (ACTIVE per symbol, never a false OK) and the isolated TEST order."""
import json
import os
import subprocess
import sys

import pytest

from paper import engine_entry as EE
from paper import watch as PW
from scripts import paper_status as PS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_entry_lock_lets_one_cycle_in(tmp_path):
    with EE.entry_lock("srv2_momentum_reversal", "NIFTY", str(tmp_path)) as a:
        with EE.entry_lock("srv2_momentum_reversal", "NIFTY", str(tmp_path)) as b:
            assert a is True and b is False                              # the cron cycle and the ✅ path never enter twice
        with EE.entry_lock("srv2_momentum_reversal", "BANKNIFTY", str(tmp_path)) as c:
            assert c is True                                             # per symbol
    with EE.entry_lock("srv2_momentum_reversal", "NIFTY", str(tmp_path)) as d:
        assert d is True                                                 # released


def test_process_skips_while_another_cycle_holds_the_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_DATA_DIR", str(tmp_path))
    with EE.entry_lock("srv2_momentum_reversal", "NIFTY"):
        m = EE.process("srv2_momentum_reversal", "t", "NIFTY", {"signal_source": "engine", "trading_mode": "PAPER"}, 65, "x")
    assert "another entry cycle" in m


def test_enter_now_runs_the_bots_paper_cycle_and_never_live():
    sent, seen = [], []
    st = {"trading_mode": "PAPER", "signal_source": "engine"}
    m = EE.enter_now("srv2_momentum_reversal", "NIFTY", send=sent.append, settings_fn=lambda k, s: seen.append((k, s)) or st,
                     token_fn=lambda: "tok", cycle_fn=lambda tok: f"entered with {tok}")
    assert m == "entered with tok" and seen == [("15m_dynamic_sr", "NIFTY")] and sent[-1].startswith("⚡ PAPER on ✅")
    live = EE.enter_now("srv2_momentum_reversal", "NIFTY", settings_fn=lambda k, s: {"trading_mode": "LIVE"},
                        cycle_fn=lambda tok: pytest.fail("LIVE must never enter from ✅"))
    assert "LIVE never" in live
    assert EE.enter_now("dynamic_sr_instant", "NIFTY") is None          # not listed ⇒ its own cron cycle
    boom = EE.enter_now("srv2_momentum_reversal", "NIFTY", settings_fn=lambda k, s: st, token_fn=lambda: "t",
                        cycle_fn=lambda tok: (_ for _ in ()).throw(RuntimeError("chain")))
    assert "failed" in boom and "next cycle" in boom                    # never raises


def test_telegram_approve_enters_engine_rows_at_once_but_not_test_rows():
    from vision import telegram_bot as TB
    calls = []
    fn = lambda bot, sym, send=None: calls.append((bot, sym))           # noqa: E731
    eng = {"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "setup_json": json.dumps({"tags": {"engine": True}})}
    TB._engine_enter_now(eng, enter_fn=fn)
    TB._engine_enter_now({**eng, "setup_json": json.dumps({"tags": {"engine": True, "dry_run": True}})}, enter_fn=fn)
    TB._engine_enter_now({**eng, "setup_json": json.dumps({"tags": {}})}, enter_fn=fn)     # the bot's own signal ⇒ its cycle
    assert calls == [("srv2_momentum_reversal", "NIFTY")]


def test_spread_target_comes_from_the_dashboard():
    chain = [{"underlying_spot_price": 22500.0}]
    got = []

    def open_fn(tok, sym, sp, **k):
        got.append(k)
        return True, {}
    import strategy
    orig = strategy.select_credit_spread_itm, strategy.select_naked_option_itm
    strategy.select_credit_spread_itm = lambda *a, **k: {"strategy": "bear call"}
    strategy.select_naked_option_itm = lambda *a, **k: {"strategy": "naked"}
    try:
        st = {"itm_depth_points": 100, "hedge_width_points": 200, "spread_target_pct_of_premium": 80}
        EE.open_paper("t", "NIFTY", st, "BEARISH", 22600.0, 65, "srv2_momentum_reversal", "ENGINE", 1, 1, chain=chain, open_fn=open_fn)
    finally:
        strategy.select_credit_spread_itm, strategy.select_naked_option_itm = orig
    assert got[0]["target_pct_of_max_profit"] == 80 and got[0]["trading_mode"] == "PAPER"
    assert got[1]["target_pct_of_max_profit"] == 100                     # naked: its own dashboard exits (manage_open_trades)


@pytest.mark.parametrize("reason,head", [("SL", "SL hit"), ("TSL_SL", "SL hit"), ("PCT_TRAILING_SL", "SL hit"), ("TARGET", "target hit"),
                                         ("PREMIUM_TARGET", "target hit"), ("EOD_SQUAREOFF", "PAPER exit"), ("MANUAL_CLOSE", "PAPER exit")])
def test_exit_message_names_sl_and_target_hits(reason, head):
    assert head in PW.exit_head(reason)


class FakeIO:
    def __init__(self, **over):
        self.v = {"settings": {"NIFTY": {"trading_mode": "PAPER", "symbol_enabled": True, "signal_source": "engine", "lots": 1},
                               "BANKNIFTY": {"trading_mode": "PAPER", "symbol_enabled": True, "signal_source": "engine", "lots": 1}},
                  "sig": ["NIFTY", "BANKNIFTY"], "pin": {"NIFTY": True, "BANKNIFTY": True},
                  "vision": {"approval_required": True, "symbols": ["NIFTY", "BANKNIFTY"]}, "pp": {"paused": False}, "tp": {"paused": False},
                  "cron": "* 4-10 * * 1-5 cd /root/Trade && python3 srv2_momentum_reversal_strategy.py\n"
                          "1,16,31,46 3-10 * * 1-5 python3 scripts/engine_signal_run.py\n* 4-10 * * 1-5 python3 trade_monitor.py\n",
                  "svc": "active", "env": True, "token": "valid"}
        self.v.update(over)

    def settings(self, s):
        return self.v["settings"][s]

    def signal_symbols(self):
        return self.v["sig"]

    def paper_instrument(self, s):
        return self.v["pin"][s]

    def vision(self):
        return self.v["vision"]

    def paper_paused(self):
        return self.v["pp"]

    def trading_pause(self):
        return self.v["tp"]

    def crontab(self):
        return self.v["cron"]

    def service(self, n):
        return self.v["svc"]

    def env(self, n):
        return self.v["env"]

    def token(self):
        return self.v["token"]


def test_status_is_active_only_when_everything_is_ready(capsys):
    assert PS.main([], io=FakeIO()) == 0
    out = capsys.readouterr().out
    assert "PAPER TRADING: ACTIVE — NIFTY" in out and "PAPER TRADING: ACTIVE — BANKNIFTY" in out


@pytest.mark.parametrize("over,why", [
    ({"pin": {"NIFTY": True, "BANKNIFTY": False}}, "PAPER instrument disabled"),
    ({"sig": ["NIFTY"]}, "signal_symbols"),
    ({"pp": {"paused": True, "reason": "x"}}, "PAPER pause ON"),
    ({"svc": "inactive"}, "service vision_telegram inactive"),
    ({"cron": "* 4-10 * * 1-5 python3 srv2_momentum_reversal_strategy.py\n"}, "cron trade_monitor (exits) absent"),
    ({"cron": "* 4-10 * * 1-5 python3 srv2_momentum_reversal_strategy.py --mode LIVE\n1 3 * * * scripts/engine_signal_run.py\n"
              "* 4 * * * trade_monitor.py\n"}, "cron 15M SRv2 bot LIVE"),
    ({"token": "missing"}, "Upstox token missing"),
    ({"token": "rejected (HTTP 401)"}, "Upstox token rejected (HTTP 401)"),             # present but expired ⇒ never a false OK
    ({"token": "not verified (HTTP 500)"}, "Upstox token not verified"),
    ({"env": False}, "missing (.env)"),
    ({"vision": {"approval_required": True, "symbols": ["NIFTY"]}}, "Vision approval list"),
])
def test_status_names_why_and_never_a_false_ok(over, why, capsys):
    assert PS.main([], io=FakeIO(**over)) == 1
    out = capsys.readouterr().out
    assert "NOT ACTIVE" in out and why in out


def test_status_live_or_off_bot_is_not_active(capsys):
    io = FakeIO()
    io.v["settings"]["BANKNIFTY"] = {"trading_mode": "LIVE", "symbol_enabled": False, "signal_source": "own", "lots": 0, "naked_lots": 0}
    assert PS.main([], io=io) == 1
    out = capsys.readouterr().out
    assert "PAPER TRADING: ACTIVE — NIFTY" in out
    assert all(x in out for x in ("mode LIVE (PAPER only)", "symbol_enabled OFF", "signal_source own", "no lots"))


def test_status_unreadable_settings_is_a_reason_not_a_pass(capsys):
    class Bad(FakeIO):
        def vision(self):
            raise RuntimeError("db locked")
    assert PS.main(["--symbols", "NIFTY"], io=Bad()) == 1
    assert "Vision settings unreadable" in capsys.readouterr().out


def test_test_card_goes_through_the_real_gate_and_never_orders():
    """The TEST card: the bot's real Vision gate (HOLD ⇒ worker card with the buttons), tagged test_only + dry_run, and no order function
    anywhere in the script; the ✅ path skips test rows."""
    from scripts import paper_test_card as TC
    from types import SimpleNamespace as NS
    import inspect
    calls, sent, st = [], [], iter(["PENDING_HUMAN", "APPROVED"])

    def gate(*a, **k):
        calls.append((a, k))
        return NS(action="HOLD", signal_id="sig1", note="queued")
    out = TC.run("tok", "NIFTY", 1, sent.append, gate_fn=gate, status_fn=lambda sid: next(st), sleep=lambda s: None,
                 levels_fn=lambda tok, sym: ("2026-10-19", 24000.0, 24300.0, 24200.0, None),
                 settings_fn=lambda k, s: {"lots": 1, "naked_lots": 1})
    assert out == "APPROVED" and len(calls) == 1
    a, k = calls[0]
    assert a[0] == "srv2_momentum_reversal" and a[2] == "PAPER" and k["tags"]["test_only"] is True and k["tags"]["dry_run"] is True
    assert all(m.startswith("🧪 TEST — not a trade") for m in sent) and "NO position" in sent[-1]
    src = inspect.getsource(TC)
    assert "open_paper" not in src and "open_multi_leg_trade" not in src and "close_trade" not in src
    from vision import telegram_bot as TB
    row = {"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "setup_json": json.dumps({"tags": {"test_only": True, "dry_run": True,
                                                                                                   "engine": True}})}
    assert TB._engine_enter_now(row, enter_fn=lambda *a, **k: pytest.fail("a TEST card must never enter")) is None


def test_test_card_label_on_the_vision_card():
    from vision import worker as W
    src = open(W.__file__, encoding="utf-8").read()
    assert '"🧪 TEST — not a trade · "' in src and 'tags.get("test_only")' in src


@pytest.mark.parametrize("stored,code,want", [("", None, "missing"), ("abc", 200, "valid"), ("abc", 401, "rejected (HTTP 401)"),
                                              ("abc", 503, "not verified (HTTP 503)")])
def test_token_is_checked_with_upstox_not_just_present(stored, code, want, monkeypatch):
    import cloud_db
    import requests
    from types import SimpleNamespace as NS
    seen = []
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda acc=None: stored)
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: seen.append(url) or NS(status_code=code))
    got = PS.IO().token()
    assert got == want and "abc" not in got                              # the token value is never in the output
    assert seen == ([] if not stored else [PS.PROFILE_URL])
