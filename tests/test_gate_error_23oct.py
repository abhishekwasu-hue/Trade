"""gate_error_23oct (DECISIONS 47): the SRv2 "error 14" and BANKNIFTY "no entry because a gate error".

Root cause reproduced: before today's first 15M candle closes (SRv2 cycles 09:15–09:29) the old level-bot confirmation gate returned
state ERROR ("आजचा पहिला बंद candle अजून नाही") for EVERY candidate area ⇒ signal_log SKIPPED_GATE_ERROR on each area each morning ⇒ the
15:45 visibility count "error N" and the per-symbol line "no entry because a gate error". Fix: that is a wait (IDLE, own status), never an
error; still no entry (fail-closed). Real errors stay SKIPPED_GATE_ERROR. Every gate / engine error ⇒ ONE plain-words ⚠️ per cause per day.
The level gate never decides an engine entry (signal_source = engine: the engine step runs in pre_cycle, before the gate)."""
import json

import pandas as pd
import pytest

from bots_common import gate_alert as GA
from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from bots_common import level_visibility as LV
from tests import test_level_bots_classic_srv2 as T

UP = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP"}


def _bars_yesterday_plus_forming(day="2026-10-23"):
    d = pd.Timestamp(day)
    ts = [d - pd.Timedelta(days=1) + pd.Timedelta(hours=9, minutes=15 + 15 * i) for i in range(25)] + [d + pd.Timedelta(hours=9, minutes=15)]
    return pd.DataFrame({"timestamp": ts, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0})


@pytest.fixture
def up(monkeypatch):
    monkeypatch.setattr(LR, "daily_trend", lambda *a, **k: UP)


# ------------------------------------------------------------------------------------------------ root cause (level gate)
@pytest.mark.parametrize("hm", ["09:16", "09:20", "09:29"])
def test_before_first_closed_15m_bar_is_a_wait_not_an_error(up, hm):
    g = LGB.cycle_gate("srv2", "BANKNIFTY", "tok", {"trading_mode": "PAPER"}, [(99, 101), (150, 151)], pd.Timestamp(f"2026-10-23 {hm}"),
                       fetch_bars=lambda *a: _bars_yesterday_plus_forming(), fetch_volume=lambda *a: None)
    assert not g.err
    for a in [(99, 101), (150, 151)]:
        r = g.result(*a)
        assert r["entry"] is False and r["state"] == LR.IDLE                 # fail-closed: still no entry
        assert not GA.is_error(r)
        f = LGB.skip_fields(r)
        assert f["trade_status"] == LGB.FIRST_BAR_STATUS != "SKIPPED_GATE_ERROR"
        assert LV.category({"trade_status": f["trade_status"]}) == "first_bar"


def test_first_closed_bar_reads_normally(up):
    df = _bars_yesterday_plus_forming()
    g = LGB.cycle_gate("srv2", "BANKNIFTY", "tok", {"trading_mode": "PAPER"}, [(99, 101)], pd.Timestamp("2026-10-23 09:31"),
                       fetch_bars=lambda *a: df, fetch_volume=lambda *a: None)
    assert not g.err and not g.wait and LGB.status_of(g.result(99, 101)) != LGB.FIRST_BAR_STATUS


def test_morning_rows_no_longer_count_as_error_14():
    """14 areas, each: the 09:16 first-bar row then "price not at area" ⇒ before the fix 14 × error; now 0 ignored."""
    rows = []
    for i in range(14):
        base = {"symbol": "BANKNIFTY", "level_type": "RESISTANCE", "level_price": 50000.0 + 50 * i, "hit_type": "NO_HIT"}
        rows.append({**base, "signal_time": "2026-10-23 09:16", "trade_status": LGB.FIRST_BAR_STATUS})
        rows.append({**base, "signal_time": "2026-10-23 09:31", "trade_status": "SKIPPED_GATE_NOT_AT_AREA"})
    s = LV.summarize(rows)
    assert s["ignored"].get("error", 0) == 0 and s["armed"] == 0
    old = [dict(r, trade_status="SKIPPED_GATE_ERROR") if r["trade_status"] == LGB.FIRST_BAR_STATUS else r for r in rows]
    assert LV.summarize(old)["ignored"]["error"] == 14                      # the bug as it was (the old rows of today)
    tbl = LV.area_table(rows[:1], "15m_dynamic_sr", include_idle=False)
    assert tbl == []                                                        # a wait is shown like idle (hidden with idle)


def test_real_data_errors_stay_errors_fail_closed(up):
    g = LGB.cycle_gate("srv2", "NIFTY", "tok", {"trading_mode": "PAPER"}, [(99, 101)], pd.Timestamp("2026-10-23 10:01"),
                       fetch_bars=lambda *a: None)
    r = g.result(99, 101)
    assert r["state"] == "ERROR" and r["entry"] is False and LGB.status_of(r) == "SKIPPED_GATE_ERROR" and GA.is_error(r)

    def boom(*a):
        raise ConnectionError("Upstox 429")
    r = LGB.cycle_gate("srv2", "NIFTY", "tok", {"trading_mode": "PAPER"}, [(99, 101)], pd.Timestamp("2026-10-23 10:01"),
                       fetch_bars=boom).result(99, 101)
    assert r["entry"] is False and "ConnectionError: Upstox 429" in r["reason"] and LGB.status_of(r) == "SKIPPED_GATE_ERROR"


def test_trend_fetch_error_is_flagged_as_error(tmp_path):
    def boom(*a):
        raise TimeoutError("fetch_candles > 25s")
    ctx = LR.daily_trend("BANKNIFTY", "tok", today="2026-10-23", fetch=boom, cache_dir=str(tmp_path))
    assert ctx["ok"] is False and ctx["reason"].startswith(LR.R_ERROR)
    assert GA.is_error({"state": LR.DISARMED, "reason": ctx["reason"]})


# ------------------------------------------------------------------------------------------------ SRv2 cycle
def test_srv2_cycle_before_first_bar_logs_no_gate_error_and_no_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(GA, "alert", lambda *a, **k: sent.append(a) or True)
    h = T.Harness(monkeypatch, "srv2", T.CONFIRMED_ROWS)
    bars = T._bars(T.CONFIRMED_ROWS, 15)
    only_yday = bars[bars["timestamp"] < pd.Timestamp("2026-09-11")]
    forming = pd.DataFrame([{"timestamp": pd.Timestamp("2026-09-11 09:15"), "open": 1000.0, "high": 1001.0, "low": 999.0, "close": 1000.0}])
    raw = pd.concat([only_yday, forming], ignore_index=True)
    monkeypatch.setattr(LGB, "cycle_gate", lambda bot, sym, tok, st, areas, now, **k: _real_cycle_gate(bot, sym, tok, st, areas, now, raw))
    h.now = pd.Timestamp("2026-09-11 09:20").to_pydatetime()
    h.run()
    sts = h.statuses()
    assert sts and "SKIPPED_GATE_ERROR" not in sts and LGB.FIRST_BAR_STATUS in sts
    assert not h.trade.calls and not h.entry_gate.calls and not sent


_ORIG_CYCLE_GATE = LGB.cycle_gate


def _real_cycle_gate(bot, sym, tok, st, areas, now, raw):
    return _ORIG_CYCLE_GATE(bot, sym, tok, st, areas, now, fetch_bars=lambda *a: raw.copy(), fetch_volume=lambda *a: None)


def test_srv2_gate_error_fails_closed_and_alerts_once_per_cause(monkeypatch, tmp_path):
    lines = []
    real_alert = GA.alert
    monkeypatch.setattr(GA, "alert", lambda *a, **k: real_alert(*a, send=lambda x: lines.append(x) or True,
                                                                 state_path=str(tmp_path / "alerts.json"),
                                                                 now=pd.Timestamp("2026-10-23 11:05"), **k))
    h = T.Harness(monkeypatch, "srv2", T.CONFIRMED_ROWS, gate_exc=RuntimeError("boom"))
    h.run()
    h.run()                                                                 # next minute: same cause ⇒ no second alert
    assert "SKIPPED_GATE_ERROR" in h.statuses() and not h.trade.calls and not h.entry_gate.calls
    assert len(lines) == 1
    assert lines[0].startswith("⚠️ Alert") and "NIFTY" in lines[0] and "RuntimeError: boom" in lines[0]
    assert "No action — information" in lines[0] and "no entry was taken" in lines[0] and "SKIPPED_" not in lines[0]


# ------------------------------------------------------------------------------------------------ engine path: never blocked by the level gate
def test_engine_step_runs_before_and_independent_of_level_gate_error(monkeypatch):
    calls = []
    from paper import engine_entry as EE
    monkeypatch.setattr(EE, "process", lambda *a, **k: calls.append(("engine", a[2])) or "NIFTY: engine E2 ⇒ OPENED")
    h = T.Harness(monkeypatch, "srv2", T.CONFIRMED_ROWS, gate_exc=RuntimeError("boom"), settings={"signal_source": "engine"})
    orig = h.cycle_gate.ret
    h.cycle_gate.ret = lambda *a, **k: calls.append(("gate", a[1])) or orig(*a, **k)
    h.run()
    assert calls[0] == ("engine", "NIFTY") and ("gate", "NIFTY") in calls  # engine first; the gate error after it
    assert not h.trade.calls                                                # the bot's own entry: never (engine mode, and gate error)


def test_engine_exception_in_pre_cycle_alerts_and_does_not_enter(monkeypatch, tmp_path):
    from paper import bot_hooks as PBH
    got = []
    monkeypatch.setattr(GA, "alert", lambda *a, **k: got.append((a, k)) or True)

    def eng(*a, **k):
        raise KeyError("trigger")
    pre = PBH.pre_cycle("srv2_momentum_reversal", "tok", "NIFTY", {"trading_mode": "PAPER", "signal_source": "engine"}, 75, engine_fn=eng)
    assert pre.stop is False and "engine त्रुटी ⇒ entry नाही" in pre.msg
    assert got and got[0][0][0] == "engine_entry" and "KeyError" in got[0][0][2]


def test_engine_entry_gate_exception_alerts_and_does_not_enter(monkeypatch):
    from paper import engine_entry as EE
    got = []
    monkeypatch.setattr(GA, "alert", lambda *a, **k: got.append(a) or True)

    def gate(*a, **k):
        raise ValueError("bad tags")
    r = {"bar_ts": "2026-10-23 10:05:00", "direction": -1}
    e = {"model": "E2", "visit_id": "v1", "direction": -1, "lo": 100.0, "hi": 101.0}
    opened = []
    monkeypatch.setattr(EE, "zone_full", lambda *a, **k: (None, ""))
    monkeypatch.setattr(EE, "entry_gate_tags", lambda *a, **k: {})
    out = EE._one_entry("srv2_momentum_reversal", "tok", "BANKNIFTY", {"lots": 1, "trading_mode": "PAPER"}, 30, "srv2", pd.Timestamp(
        "2026-10-23 10:06"), r, e, lambda *a: False, gate, lambda *a, **k: opened.append(a), {"chain": [{"underlying_spot_price": 100.5}]},
        None, (15, 0), None)
    assert "gate त्रुटी ⇒ entry नाही" in out and not opened
    assert got and got[0][0] == "vision" and got[0][1] == "BANKNIFTY" and "ValueError: bad tags" in got[0][2]


# ------------------------------------------------------------------------------------------------ the alert itself
def _al(tmp_path, detail, now="2026-10-23 10:00", path="level_gate", sym="BANKNIFTY", send=None):
    lines = [] if send is None else None
    s = send or (lambda x: lines.append(x) or True)
    ok = GA.alert(path, sym, detail, send=s, state_path=str(tmp_path / "a.json"), now=pd.Timestamp(now))
    return ok, lines


def test_alert_once_per_cause_per_day(tmp_path):
    assert _al(tmp_path, "gate error (fail-closed): TimeoutError: fetch > 25s")[0] is True
    GA._SEEN.clear()                                                        # a new process (next cron minute) reads the state file
    assert _al(tmp_path, "gate error (fail-closed): TimeoutError: fetch > 30s", "2026-10-23 10:01", sym="NIFTY")[0] is False
    assert _al(tmp_path, "gate error (fail-closed): 15m candles मिळाले नाहीत")[0] is True     # another cause
    assert _al(tmp_path, "TimeoutError: x", path="engine_entry")[0] is True                 # another path = another cause
    assert _al(tmp_path, "gate error (fail-closed): TimeoutError: fetch > 25s", "2026-10-24 09:40")[0] is True   # next day
    st = json.load(open(tmp_path / "a.json", encoding="utf-8"))
    assert set(st["_gate_error"].values()) == {"2026-10-24"}                # only today's keys kept


def test_alert_failed_send_is_retried_and_never_raises(tmp_path):
    def bad(x):
        raise RuntimeError("telegram down")
    assert _al(tmp_path, "KeyError: x", send=bad)[0] is False
    calls = []
    assert _al(tmp_path, "KeyError: x", send=lambda x: calls.append(x) or True)[0] is False
    assert calls == []                                                      # review 3: a failed send is not retried in this run
    GA._FAILED.clear()                                                      # next process (next cron minute) tries again
    assert _al(tmp_path, "KeyError: x", send=lambda x: False)[0] is False
    GA._FAILED.clear()
    assert not (tmp_path / "a.json").exists()                               # nothing recorded on failure
    assert _al(tmp_path, "KeyError: x")[0] is True                          # recorded only after a real send
    assert GA.alert("level_gate", None, None, send=lambda x: True, state_path=str(tmp_path / "dir_missing" / "a.json"),
                    now=pd.Timestamp("2026-10-23 10:00")) is True


def test_alert_text_is_plain_words():
    t = GA.text("level_gate", "banknifty", "[GATE] 50,000–50,050 · gate error (fail-closed): ConnectionError: Upstox 429",
                pd.Timestamp("2026-10-23 11:05"))
    first = t.split("\n")[0]
    assert first.startswith("⚠️ Alert") and "BANKNIFTY" in first and "11:05" in first and "No action — information" in first
    assert "ConnectionError: Upstox 429" in t and "[GATE]" not in t and "fail-closed" not in t and "SKIPPED" not in t
    assert "Engine entries are decided by the engine models" in t and len(t.split("\n")) <= 12
    t2 = GA.text("engine_entry", "NIFTY", "KeyError: 'x'", pd.Timestamp("2026-10-23 11:05"), engine_entry_waiting=True)
    assert "NOT taken" in t2


def test_existing_engine_alert_state_is_kept(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"NIFTY": {"failing": True}, "_data_problem": {"NIFTY": "2026-10-23"}}), encoding="utf-8")
    GA.alert("vision", "NIFTY", "OSError: db locked", send=lambda x: True, state_path=str(p), now=pd.Timestamp("2026-10-23 10:00"))
    st = json.loads(p.read_text(encoding="utf-8"))
    assert st["NIFTY"] == {"failing": True} and st["_data_problem"] == {"NIFTY": "2026-10-23"} and st["_gate_error"]


# ------------------------------------------------------------------------------------------------ the day summary wording (engine mode)
def test_day_summary_engine_mode_does_not_say_no_entry_because_gate_error():
    from scripts import paper_daily_summary as S
    ctx = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "reason": "Daily DOWN"}
    gate = {"armed": 2, "confirmed": 0, "ignored": {"error": 2}, "entry_statuses": {}}
    empty = {"armed": 0, "confirmed": 0, "ignored": {}, "entry_statuses": {}}
    own = S.symbol_line("BANKNIFTY", ctx, gate, None, None)
    eng = S.symbol_line("BANKNIFTY", ctx, empty, None, None, engine_gate=gate)
    assert "no entry because a gate error" in own
    assert "no entry because" not in eng and "never reached" not in eng and "old level-bot check" in eng and "engine models" in eng


def test_day_summary_comparison_wording_is_per_bot_signal_source():
    """review 5: each level bot by its OWN signal_source — SRv2 (plain SUPPORT / RESISTANCE) engine, Classic (15M DYNAMIC_SR) own."""
    from scripts import paper_daily_summary as S
    rows = [{"symbol": "BANKNIFTY", "level_type": "RESISTANCE", "level_price": 57000.0, "signal_time": "2026-10-23 10:00",
             "trade_status": "SKIPPED_GATE_ERROR", "hit_type": "NO_HIT"},
            {"symbol": "BANKNIFTY", "level_type": "DYNAMIC_SR_RESISTANCE_15M", "level_price": 57100.0, "signal_time": "2026-10-23 10:00",
             "trade_status": "SKIPPED_GATE_BROKEN", "hit_type": "NO_HIT"},
            {"symbol": "BANKNIFTY", "level_type": "DYNAMIC_SR_RESISTANCE_5M", "level_price": 57200.0, "signal_time": "2026-10-23 10:00",
             "trade_status": "SKIPPED_GATE_BROKEN", "hit_type": "NO_HIT"}]
    own, eng = S.split_engine_rows(rows, {"15m_dynamic_sr", "1m_instant"}, "BANKNIFTY")
    assert [r["level_price"] for r in eng] == [57000.0]                    # SRv2 only
    assert [r["level_price"] for r in own] == [57100.0, 57200.0]           # Classic own; 5M rows shared by Instant (engine) + Classic (own)
    rows = [dict(r, signal_time="2026-10-23 09:45", trade_status="SKIPPED_GATE_WAITING_COMMITMENT") for r in rows] + rows   # armed first
    ctx = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "reason": "Daily DOWN"}
    txt = S.symbols_section("2026-10-23", symbols=("BANKNIFTY",), ctx_fn=lambda s, d: ctx, rows_fn=lambda s, d: (rows, None),
                            zones_fn=lambda s: None, range_fn=lambda s, d: None, engine_fn=lambda s: {"15m_dynamic_sr"})
    assert "no entry because price broke through the area" in txt          # Classic (own): today's wording
    assert "old level-bot check (comparison only" in txt and "it ignored them because a gate error" in txt   # SRv2 (engine)
    assert "no entry because a gate error" not in txt
    txt_own = S.symbols_section("2026-10-23", symbols=("BANKNIFTY",), ctx_fn=lambda s, d: ctx, rows_fn=lambda s, d: (rows, None),
                                zones_fn=lambda s: None, range_fn=lambda s, d: None, engine_fn=lambda s: set())
    assert "old level-bot check" not in txt_own


def test_no_bar_from_today_mid_day_is_an_error(up):
    """review 1: Upstox returns no bar from today at 11:00 (data missing) ⇒ SKIPPED_GATE_ERROR (alerted), never a silent wait."""
    df = _bars_yesterday_plus_forming().iloc[:-1]                          # yesterday only
    for hm in ("09:20", "11:00"):
        g = LGB.cycle_gate("srv2", "BANKNIFTY", "tok", {"trading_mode": "PAPER"}, [(99, 101)], pd.Timestamp(f"2026-10-23 {hm}"),
                           fetch_bars=lambda *a: df, fetch_volume=lambda *a: None)
        r = g.result(99, 101)
        assert r["entry"] is False and r["state"] == "ERROR" and LGB.status_of(r) == "SKIPPED_GATE_ERROR" and GA.is_error(r)
    tz = _bars_yesterday_plus_forming()
    tz["timestamp"] = tz["timestamp"].dt.tz_localize("Asia/Kolkata")       # Upstox tz-aware timestamps: still the forming-bar wait
    g = LGB.cycle_gate("srv2", "BANKNIFTY", "tok", {"trading_mode": "PAPER"}, [(99, 101)], pd.Timestamp("2026-10-23 09:20"),
                       fetch_bars=lambda *a: tz, fetch_volume=lambda *a: None)
    assert LGB.status_of(g.result(99, 101)) == LGB.FIRST_BAR_STATUS


def test_alert_write_merges_a_concurrent_writer(tmp_path):
    """review 4: the shared alert file is re-read just before the write (ES.alert_error may write between) and replaced atomically."""
    p = tmp_path / "a.json"

    def send(line):                                                        # another process writes the file while we send
        p.write_text(json.dumps({"NIFTY": {"failing": True, "since": "x"}}), encoding="utf-8")
        return True
    assert GA.alert("vision", "NIFTY", "OSError: x", send=send, state_path=str(p), now=pd.Timestamp("2026-10-23 10:00"))
    st = json.loads(p.read_text(encoding="utf-8"))
    assert st["NIFTY"] == {"failing": True, "since": "x"} and list(st["_gate_error"].values()) == ["2026-10-23"]
    assert [x.name for x in tmp_path.iterdir()] == ["a.json"]              # no temp file left
