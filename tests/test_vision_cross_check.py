"""V1 (DECISIONS 88) scripts/vision_cross_check.py with a FAKE vision client (no network): no-look-ahead clean frames, cap stop,
table build (reader vs vision vs key, disagreements), cost sum in the usage store, answer-key state words, reader replay ≤ asof."""
import importlib
import json
import os
import types

import numpy as np
import pandas as pd
import pytest

VCX = importlib.import_module("scripts.vision_cross_check")
from vision import config as VC   # noqa: E402
from vision import store as VS    # noqa: E402


def _m15(days=60, start="2026-07-01"):
    rng = np.random.default_rng(1)
    rows, px = [], 55000.0
    for d in pd.bdate_range(start, periods=days):
        for t in pd.date_range(f"{d:%Y-%m-%d} 09:15", f"{d:%Y-%m-%d} 15:15", freq="15min"):
            o = px
            px += rng.normal(0, 20)
            rows.append((t, o, max(o, px) + 5, min(o, px) - 5, px))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def _data(m15):
    return {"m15": m15, "daily": VCX.daily_from_15m(m15)}


@pytest.fixture(scope="module")
def m15():
    return _m15()


def test_frames_have_no_bar_after_the_decision_close(m15):
    dec = pd.Timestamp("2026-08-12 11:00")
    fr, asof = VCX.frames_at(_data(m15), dec)
    assert asof == pd.Timestamp("2026-08-12 11:15")
    for tf in VCX.TFS:
        assert len(fr[tf]) and pd.Timestamp(fr[tf]["bar_end"].max()) <= asof
    assert fr["15M"]["timestamp"].iloc[-1] == dec                                # decision bar = last bar
    assert fr["D"]["timestamp"].iloc[-1] == pd.Timestamp("2026-08-11")           # the decision day (partial) is not a Daily bar
    assert fr["1H"]["bar_end"].iloc[-1] == pd.Timestamp("2026-08-12 11:15")      # 10:15–11:15 closed; 11:15 hour not yet
    assert pd.Timestamp(fr["W"]["bar_end"].iloc[-1]).dayofweek == 4              # whole weeks only
    later = m15[m15["timestamp"] + pd.Timedelta(minutes=15) <= asof]
    fr2, _ = VCX.frames_at(_data(later), dec)                                    # remove every later bar ⇒ identical frames
    for tf in VCX.TFS:
        pd.testing.assert_frame_equal(fr[tf], fr2[tf])


def test_end_of_session_decision_includes_that_daily_bar(m15):
    fr, asof = VCX.frames_at(_data(m15), pd.Timestamp("2026-08-12 15:15"))
    assert asof == pd.Timestamp("2026-08-12 15:30") and fr["D"]["timestamp"].iloc[-1] == pd.Timestamp("2026-08-12")


def test_key_state_words_and_decision_bar(m15):
    ks = VCX.key_state
    assert ks({"verdict": "SWEEP / retest — ALIVE (support)"}) == "false_break"
    assert ks({"verdict": "BROKEN only on 28 Sep (not 24 Sep) ⇒ then FLIPPED resistance"}) == "broken"
    assert ks({"verdict": "SWEEP / retest — flip still ALIVE (not dead)"}) == "false_break"     # lower-case 'dead' is not the state
    assert ks({"verdict": "BROKEN 26 Aug 09:15 (flip to support) → DEAD 31 Aug 10:30"}) == "dead"
    assert ks({"verdict": "SWEEP — Weekly support ALIVE (not broken)"}) == "false_break"
    assert ks({"verdict": "x", "expected_state": "alive"}) == "alive"
    it = {"window": ["2026-08-21", "2026-08-25"], "known_at": "broken known 26 Aug 09:15; dead known 31 Aug 10:30"}
    assert VCX.decision_for(it, m15, "end") == pd.Timestamp("2026-08-25 15:15")
    assert VCX.decision_for(it, m15, "known") == pd.Timestamp("2026-08-31 10:30")


def test_reader_events_replayed_only_up_to_asof(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([{"id": "L06", "tf": "1H", "found": [{"tf": "1H", "events": [
        ["2026-08-26 09:15", "broken", ""], ["2026-08-31 10:30", "dead", ""]]}]}]))
    assert VCX.reader_states(str(p), lambda i: pd.Timestamp("2026-08-28 15:30"))["L06"]["state"] == "broken"
    assert VCX.reader_states(str(p), lambda i: pd.Timestamp("2026-08-31 10:45"))["L06"]["state"] == "dead"


class Fake:
    """Fake Anthropic client: fixed answer, fixed usage; counts calls; never touches the network."""

    def __init__(self, state="alive", tin=20000, tout=1000):
        self.calls, self.state, self.tin, self.tout = 0, state, tin, tout
        self.messages = self

    def create(self, **p):
        assert p["model"] and p["system"][0]["text"].startswith("You are a price-action chart reader")
        assert sum(1 for c in p["messages"][0]["content"] if c["type"] == "image") == 4
        self.calls += 1
        ans = {"htf_trend": {"weekly": "up", "daily": "down"}, "zones_near_price": [{"tf": "D", "kind": "support", "lo": 1.0, "hi": 2.0}],
               "object_state": self.state, "state_reason": "r", "entry": False, "side": "none", "entry_reason": "e"}
        u = types.SimpleNamespace(input_tokens=self.tin, output_tokens=self.tout, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return types.SimpleNamespace(stop_reason="end_turn", usage=u, content=[types.SimpleNamespace(type="text", text=json.dumps(ans))])


@pytest.fixture
def setup(tmp_path, monkeypatch, m15):
    monkeypatch.setenv("VISION_DB_PATH", str(tmp_path / "vision.db"))
    monkeypatch.setattr(VCX.BT, "png", lambda fig: b"PNG")                       # no image engine in the unit test
    monkeypatch.setattr(VCX, "load_symbol", lambda sym, td: _data(m15) if sym == "BANKNIFTY" else None)
    key = {"key_version": "t1", "items": [
        {"id": f"L0{i}", "object": {"tf_band": "1H support", "lo": 54900.0, "hi": 55000.0}, "window": ["2026-08-03", f"2026-08-1{i}"],
         "verdict": "SWEEP / retest — ALIVE", "known_at": ""} for i in range(1, 5)]}
    kp = tmp_path / "key.json"
    kp.write_text(json.dumps(key))
    rp = tmp_path / "replay.json"
    rp.write_text(json.dumps([{"symbol": "BANKNIFTY", "decision_bar": "2026-08-20 11:00", "model": "E4", "side": "bear", "id": "E01"}]))
    return tmp_path, str(kp), str(rp)


def test_run_table_cost_sum_and_disagreements(setup):
    tmp, kp, rp = setup
    out = tmp / "out"
    fake = Fake(state="broken")
    assert VCX.main(["--answer-key", kp, "--replay-json", rp, "--out-dir", str(out), "--model", "claude-opus-5-5", "--cap", "5"],
                    client=fake) == 0
    s = json.load(open(out / "summary.json"))
    assert fake.calls == 5 and s["ok"] == 5 and s["items"] == 5
    from vision.signal_audit import cost_usd
    one = cost_usd("claude-opus-5-5", {"input_tokens": 20000, "output_tokens": 1000})
    assert s["spent_usd"] == pytest.approx(5 * one, abs=1e-4)                     # cost sum = every call
    month = VS.spent_by_task()[VCX.TASK][1]
    assert month == pytest.approx(5 * one)                                        # every call recorded in the usage store
    rows = list(__import__("csv").DictReader(open(out / "table.csv", encoding="utf-8")))
    assert [r["id"] for r in rows] == ["L01", "L02", "L03", "L04", "E01"]
    assert all("vision broken ≠ key false_break" in r["disagree"] for r in rows[:4])
    assert "entry: vision no ≠ reader yes bear" in rows[4]["disagree"] and rows[4]["reader_entry"] == "yes bear (E4)"
    h = open(out / "table.html", encoding="utf-8").read()
    assert "Disagreements (5)" in h and "clean_15M.png" in h
    res = json.load(open(out / "results.json"))
    assert all(len(r["charts"]) == 4 for r in res)


def test_cap_stops_the_run(setup):
    tmp, kp, rp = setup
    fake = Fake()
    from vision.signal_audit import cost_usd
    one = cost_usd("claude-opus-5-5", {"input_tokens": 20000, "output_tokens": 1000})
    out = tmp / "cap"
    VCX.main(["--answer-key", kp, "--replay-json", rp, "--out-dir", str(out), "--model", "claude-opus-5-5",
              "--cap", str(round(one * 2.5, 4))], client=fake)
    s = json.load(open(out / "summary.json"))
    assert s["stopped_by_cap"] and fake.calls == 2                                # 3rd: 2 spent + 1.3 × max cost > 2.5 ⇒ stop
    assert s["spent_usd"] <= round(one * 2.5, 4)
    st = [r["status"] for r in json.load(open(out / "results.json"))]
    assert st[:2] == ["OK", "OK"] and set(st[2:]) == {"NOT_RUN_BUDGET"}


def test_first_call_estimate_over_cap_makes_no_call(setup):
    tmp, kp, _ = setup
    fake = Fake()
    VCX.main(["--answer-key", kp, "--out-dir", str(tmp / "z"), "--model", "claude-opus-5-5", "--cap", "0.001"], client=fake)
    assert fake.calls == 0 and json.load(open(tmp / "z" / "summary.json"))["spent_usd"] == 0


def test_dry_run_makes_no_call_and_estimates(setup):
    tmp, kp, rp = setup
    fake = Fake()
    VCX.main(["--answer-key", kp, "--replay-json", rp, "--out-dir", str(tmp / "d"), "--dry-run", "--model", "claude-opus-5-5"],
             client=fake)
    s = json.load(open(tmp / "d" / "summary.json"))
    assert fake.calls == 0 and s["spent_usd"] == 0 and s["estimate_usd"] > 0 and s["dry_run"]
    assert not os.path.exists(os.environ["VISION_DB_PATH"]) or VCX.TASK not in VS.spent_by_task()


def test_cap_setting_is_a_dashboard_global_and_cli_only_lowers():
    assert VC.GLOBAL_DEFAULTS["vision_check_run_cap_usd"] == 1.0
    assert VC.RANGES["vision_check_run_cap_usd"] == (0.0, 5.0)
    g = dict(VC.GLOBAL_DEFAULTS)
    assert VCX.run_cap(None, g) == 1.0 and VCX.run_cap(0.5, g) == 0.5 and VCX.run_cap(9.0, g) == 1.0
    with pytest.raises(ValueError):
        VC.validate("_global", {"vision_check_run_cap_usd": 50})


def test_unknown_symbol_and_bad_replay_entry(setup, tmp_path):
    rec = VCX.run_item({"kind": "replay", "id": "X", "symbol": "FINNIFTY", "decision_bar": "2026-08-20 11:00"}, None, str(tmp_path),
                       "m", None, {"spent": 0, "cap": 1, "costs": []})
    assert rec["status"] == "NO_DATA"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"symbol": "BANKNIFTY"}]))
    with pytest.raises(ValueError):
        VCX.replay_items(str(p))
