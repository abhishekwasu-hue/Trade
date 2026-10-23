"""DECISIONS 37 — the live loop on 5M closes and the card / Vision on the 5M trigger (docs/reports/trigger_5m_report.md §5 / §6). Fake feeds,
no network, no real model call:

  • build_inputs: in 5M mode the 5M close being decided must be there (spot 5M and its FUT 5M bar), else the cycle fails closed (the
    next minute retries); the 15M what-if is today's check only;
  • decide_live: 15M ⇒ decide(last 15M bar) (today's call); 5M ⇒ decide5(last 5M candle) + the catch-up of every unstored closed 5M
    candle of the session, in order;
  • run3 (5M): stores every caught-up row inside the store window, never a row outside it; `since` = the last stored non-error row;
  • the every-minute guard: exits without a run when the due bar is stored or outside the window; an error row is retried;
  • paper.engine_entry tags `entry_trigger_tf` / `entry_trigger`; Vision waits for the 5M trigger candle (not the 15M bar); the card's
    5M trigger panel, its text line and the 5M prompt block (SYSTEM_PROMPT byte-identical for 15M cards)."""
import json

import pandas as pd
import pytest

import engine3_live as L
import engine_signal as ES
from scripts import engine_signal_run as ESR
from tests.test_one_bot import Feed, v22_setup


# ------------------------------------------------------------------------------------------------ build_inputs on 5M closes
class Feed5(Feed):
    def __init__(self, cut5=None, cutfut=None, **k):
        super().__init__(**k)
        self.cut5, self.cutfut = cut5, cutfut

    def index(self, sym, interval, days):
        out = super().index(sym, interval, days)
        if interval == "5minute" and self.cut5 is not None:
            out = out[out["timestamp"] < pd.Timestamp(self.cut5)]
        return out

    def futures(self, sym, interval, days):
        out = super().futures(sym, interval, days)
        return out[out["timestamp"] < pd.Timestamp(self.cutfut)] if self.cutfut is not None else out


NOW = pd.Timestamp("2030-03-25 10:21")                                    # the 5M close 10:20 is due; the 15M close 10:15 is there


def test_build_inputs_needs_the_5m_close_being_decided_in_5m_mode_only():
    m15, daily, ltf, fut, note = L.build_inputs(Feed5(), "BANKNIFTY", NOW)
    assert ltf["bar_end"].iloc[-1] == pd.Timestamp("2030-03-25 10:20") and fut["bar_end"].iloc[-1] == pd.Timestamp("2030-03-25 10:20")
    with pytest.raises(L.EngineDataError, match="5M spot"):
        L.build_inputs(Feed5(cut5="2030-03-25 10:15"), "BANKNIFTY", NOW)
    with pytest.raises(L.FutBarLate, match="FUT 5M"):
        L.build_inputs(Feed5(cutfut="2030-03-25 10:15"), "BANKNIFTY", NOW)
    s15 = {"engine3_trigger_tf": "15m"}                                    # the 15M what-if: today's checks only
    L.build_inputs(Feed5(cut5="2030-03-25 10:15"), "BANKNIFTY", NOW, s15)
    L.build_inputs(Feed5(cutfut="2030-03-25 10:15"), "BANKNIFTY", NOW, s15)


# ------------------------------------------------------------------------------------------------ decide_live + catch-up
class FakeV5:
    def __init__(self, ends, tf="5M"):
        self.trigger_tf = tf
        self.m15 = pd.DataFrame({"bar_end": ["2030-03-25 10:15:00"]})
        self.F = type("F", (), {"n": len(ends), "end": pd.to_datetime(pd.Series(ends)).to_numpy()})()
        self.asked = []

    def trigger_frame(self):
        return self.F

    def decide5(self, j):
        self.asked.append(j)
        return {"bar_end": str(pd.Timestamp(self.F.end[j])), "decision": "wait"}

    def decide(self, t):
        return {"bar_end": "15M", "decision": "wait"}


def test_decide_live_catch_up_decides_every_unstored_5m_close_of_the_session_in_order():
    ends = ["2030-03-24 15:30", "2030-03-25 09:20", "2030-03-25 09:25", "2030-03-25 09:30", "2030-03-25 09:35"]
    V = FakeV5(ends)
    r = L.decide_live(V)
    assert V.asked == [4] and r["catch_up"] == []                          # no since ⇒ only the last close (as before)
    V = FakeV5(ends)
    r = L.decide_live(V, since=pd.Timestamp("2030-03-25 09:20"))
    assert V.asked == [2, 3, 4] and [x["bar_end"] for x in r["catch_up"]] == ["2030-03-25 09:25:00", "2030-03-25 09:30:00"]
    V = FakeV5(ends)
    L.decide_live(V, since=pd.Timestamp("2030-03-25 00:00"))                # nothing stored today ⇒ the whole session, never yesterday
    assert V.asked == [1, 2, 3, 4]
    assert L.decide_live(FakeV5(ends, tf="15M"))["bar_end"] == "15M"         # 15M what-if ⇒ today's decide(last)


def test_run3_5m_stores_the_caught_up_rows_inside_the_window_and_reads_since_from_the_store(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    seen = []

    def compute(sym, feed, n, st=None, since=None):
        seen.append(since)
        r = v22_setup(sym, "2030-01-07 09:40")
        r["catch_up"] = [dict(v22_setup(sym, "2030-01-07 09:25"), decision="wait"), dict(v22_setup(sym, "2030-01-07 09:30"), decision="wait"),
                         dict(v22_setup(sym, "2030-01-07 09:35"), decision="wait")]
        return r
    monkeypatch.setattr(L, "compute", compute)
    r = ES.run3("NIFTY", "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 09:41"))
    assert seen == [pd.Timestamp("2030-01-07")]                            # nothing stored yet ⇒ the session from its start
    assert r["bar_ts"] == "2030-01-07 09:40:00" and r["caught_up"] == ["2030-01-07 09:30:00", "2030-01-07 09:35:00"]
    assert ES.latest("NIFTY", "2030-01-07 09:41", path=p)["bar_ts"] == "2030-01-07 09:40:00"
    assert not ES.has_bar("NIFTY", "2030-01-07 09:25", p) and ES.has_bar("NIFTY", "2030-01-07 09:30", p)   # 09:25 outside the window
    ES.run3("NIFTY", "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 09:46"))
    assert seen[-1] == pd.Timestamp("2030-01-07 09:40")                    # the next cycle continues from the last stored row
    ES.save_error("NIFTY", "2030-01-07 09:45", "late", path=p)
    assert ES.last_stored("NIFTY", "2030-01-07 09:47", p) == pd.Timestamp("2030-01-07 09:40")   # an error row is decided again


def test_run3_15m_what_if_is_todays_cycle(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    seen = []
    monkeypatch.setattr(L, "compute", lambda s, feed, n, st=None, **k: seen.append(k) or v22_setup(s, "2030-01-07 10:00"))
    r = ES.run3("NIFTY", "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 10:01"), s={"engine3_trigger_tf": "15m"})
    assert seen == [{}] and r["bar_ts"] == "2030-01-07 10:00:00" and "caught_up" not in r


# ------------------------------------------------------------------------------------------------ the every-minute guard
def test_guard_runs_only_when_the_due_bar_is_not_stored_and_inside_the_window(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    monkeypatch.setenv("ENGINE_SIGNAL_DB", p)
    fivem = lambda strat, sym: {"engine3_trigger_tf": ""}                 # noqa: E731
    assert ES.due_bar_end("2030-01-07 10:21", "5M") == pd.Timestamp("2030-01-07 10:20")
    assert ES.due_bar_end("2030-01-07 10:20:30", "5M") == pd.Timestamp("2030-01-07 10:15")   # a minute after the close, never at it
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 10:21", settings_fn=fivem) == ["NIFTY"]
    ES.save(L.row_from_v22("NIFTY", v22_setup("NIFTY", "2030-01-07 10:20"), lambda: "x"), p)
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 10:22", settings_fn=fivem) == []
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 09:26", settings_fn=fivem) == []          # 09:25 is outside the store window
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 15:06", settings_fn=fivem) == []          # after 15:00
    ES.save_error("NIFTY", "2030-01-07 10:25", "late", path=p)
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 10:26", settings_fn=fivem) == ["NIFTY"]   # an error row is retried
    m15 = lambda strat, sym: {"engine3_trigger_tf": "15m"}                # noqa: E731
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 10:31", settings_fn=m15) == ["NIFTY"]     # 15M bar 10:30 due
    ES.save(L.row_from_v22("NIFTY", v22_setup("NIFTY", "2030-01-07 10:30"), lambda: "x"), p)
    assert ESR.due_symbols(["NIFTY"], "2030-01-07 10:36", settings_fn=m15) == []            # 15M mode: no new 15M bar yet
    runs = []
    rc = ESR.main(["--symbols", "NIFTY", "--guard"], token_fn=lambda: "tok", run_fn=lambda s, t: runs.append(s), market_fn=lambda: True,
                  now=pd.Timestamp("2030-01-07 10:36"), symbols_fn=lambda: ["NIFTY"], settings_fn=m15, check_fn=lambda t: "ok")
    assert rc == 0 and runs == []


# ------------------------------------------------------------------------------------------------ PAPER tags, Vision timing, the card
E5 = {"model": "E1", "name": "Aggressive", "direction": -1, "visit_id": "281@2026-10-15 10:00:00", "trigger_tf": "5M",
      "trigger_ts": "2026-10-15 10:05:00", "entry_ref": 55720.7, "invalidation": {"price": 55762.6, "rule": "r"},
      "area": {"id": 281, "tf": "1H", "lo": 55699.45, "hi": 55970.15, "state": "FLIPPED"},
      "refined_base": {"lo": 55699.45, "hi": 55762.6, "ts": "2026-09-25 14:00:00"},
      "trigger": {"tf": "5M", "ts": "2026-10-15 10:05:00", "bar_end": "2026-10-15 10:10:00", "context_bar_ts": "2026-10-15 09:45:00",
                  "ohlc": {"open": 55650.0, "high": 55730.0, "low": 55640.0, "close": 55720.7}, "bar15_ts": "2026-10-15 10:00:00",
                  "visit_start5": "2026-10-15 10:00:00", "facts": {}}}


def test_engine_entry_tags_the_5m_trigger_and_a_15m_entry_is_unchanged():
    from paper import engine_entry as EE
    r = {"bar_ts": "2026-10-15 10:10:00", "level_lo": 55699.45, "level_hi": 55970.15, "grade": None, "payload": "{}"}
    t = EE.entry_gate_tags(r, E5, "BEARISH")
    assert t["entry_trigger_tf"] == "5M" and t["entry_trigger"]["ohlc"]["close"] == 55720.7
    e15 = {k: v for k, v in E5.items() if k not in ("trigger_tf", "trigger")}
    assert "entry_trigger_tf" not in EE.entry_gate_tags(r, e15, "BEARISH")


def test_vision_waits_for_the_5m_trigger_candle_not_the_15m_bar():
    from vision import context as CX
    from vision import worker as VW
    from paper import engine_entry as EE
    r = {"bar_ts": "2026-10-15 10:10:00", "level_lo": 55699.45, "level_hi": 55970.15, "grade": None, "payload": "{}"}
    tags = EE.entry_gate_tags(r, E5, "BEARISH")
    row = {"setup_tf": "15M", "signal_ts": "2026-10-15 10:10:00", "setup_json": json.dumps({"tags": tags})}
    wait, sb = VW.bar_wait(row, {"vision_wait_for_bar_close": True}, now=pd.Timestamp("2026-10-15 10:10:30"))
    assert sb["tf"] == 5 and sb["closed"] and not wait                     # the 5M trigger candle 10:05–10:10 is closed
    row15 = {"setup_tf": "15M", "signal_ts": "2026-10-15 10:10:00", "setup_json": json.dumps({"tags": {k: v for k, v in tags.items()
                                                                                                    if not k.startswith("entry_trigger")}})}
    _w, sb15 = VW.bar_wait(row15, {"vision_wait_for_bar_close": True}, now=pd.Timestamp("2026-10-15 10:10:30"))
    assert sb15["tf"] == 15 and not sb15["closed"]                         # a 15M signal: today's wait for the 15M bar
    assert CX.bar_end_of(row) == pd.Timestamp("2026-10-15 10:10") and CX.bar_end_of(row15) == pd.Timestamp("2026-10-15 10:15")


def test_card_text_prompt_and_trigger_panel_on_a_5m_entry(monkeypatch):
    from paper import engine_entry as EE
    from tests.test_vision_engine_audit import TS, engine_sig
    from tests.test_vision_v2 import bars
    from vision import card_summary as CS
    from vision import chart as CH
    from vision import engine_audit as EA
    df = bars()
    s = engine_sig(df)
    last = float(df[df.timestamp < TS].close.iloc[-1])
    trig = {"tf": "5M", "ts": str(TS - pd.Timedelta(minutes=5)), "bar_end": str(TS), "context_bar_ts": str(TS - pd.Timedelta(minutes=30)),
            "ohlc": {"open": last, "high": last + 4, "low": last - 3, "close": last}, "bar15_ts": str(TS - pd.Timedelta(minutes=15)),
            "visit_start5": str(TS - pd.Timedelta(minutes=40)), "facts": {"choch_level": last - 1}}
    s5 = {**s, "tags": {**s["tags"], **EE.trigger_tags({"trigger_tf": "5M", "trigger": trig}), "entry_trigger_ts": trig["ts"],
                        "entry_object": "area", "entry_model": "E3"}}
    line = CS.trigger_line(s5["tags"])
    assert line.startswith("Trigger 5M: E3 candle") and "traded into the refined base ✓" in line and "context = last closed 15M bar" in line
    assert CS.trigger_line(s["tags"]) == ""
    assert EA.prompt_version(s5) == EA.PROMPT_VERSION + "+5m" and EA.prompt_version(s) == EA.PROMPT_VERSION
    rd = EA.reading(s5)
    assert rd["trigger_tf"] == "5M"
    txt = EA.facts_text(s5, rd)
    assert "trigger 5M" in txt and "Trigger candle (5M)" in txt and "context = the last closed 15M bar" in txt
    assert "Trigger candle (5M)" not in EA.facts_text(s)
    req = EA.build_request(b"png", s5, "m")
    assert req["system"][0]["text"] == EA.SYSTEM_PROMPT and req["system"][-1]["text"] == EA.TRIGGER_5M_SYSTEM
    assert [x["text"] for x in EA.build_request(b"png", s, "m")["system"]] == [EA.SYSTEM_PROMPT]
    setup, higher, tfs, cut = CH.panels(df, TS, "15M", return_cut=True)
    meta = {}
    fig = CH.engine_figure(cut, setup, higher, tfs, s5, {}, None, meta)
    texts = [a.text for a in fig.layout.annotations]
    assert any(t.startswith("trigger 5M · T") for t in texts) and "CHoCH 5M" in texts and meta["trigger_panel"]["tf"] == "5M"
    fig15 = CH.engine_figure(cut, setup, higher, tfs, s, {}, None, {})
    assert not any(str(t).startswith("trigger 5M") for t in [a.text for a in fig15.layout.annotations])
