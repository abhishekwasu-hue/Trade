"""T-3 model C on the live PAPER path (DECISIONS 32): the dashboard switches (all default OFF), the per-sub-way skip, the separate
statistics tag / summary slot, the payload (family, sub-model, story, facts), the card's story line, and the Vision engine audit facts
that let `trend_side` be judged by model C's own rule (Vision stays advisory). Fake engine rows only (no data, no network, no API)."""
import json
import re
import sqlite3

import pytest

import engine3_live as L
import engine_signal as ES
from paper import engine_entry as EE
from reader_report import standard as RS
from tests.test_entry_models_live import BAR, BOT, SYM, ST, VISIT, _approval_on, entry, es, opened, put, recorder, run  # noqa: F401
from tests.test_vision_engine_audit import CLOCK, FORBIDDEN, engine_sig
from tests.test_vision_v1 import NOW, db  # noqa: F401 (fixture)
from vision import card_summary as CS
from vision import engine_audit as EA
from vision import store as VS

CTX = {"window": "b_only", "daily": {"trend": "DOWN", "phase": "correction"}, "weekly": "DOWN",
       "O": {"price": 24800.0, "bar": 10, "ts": "x"}, "choch": {"level": 25010.0, "bar": 14}, "HA": {"price": 25210.0, "bar": 20},
       "B": {"price": 25090.0, "bar": 26}, "a_nature": {"verdict": "impulse", "why": "larger bodies"},
       "b_nature": {"verdict": "correction", "why": "smaller bodies"},
       "end_zone": {"first_htf_area": {"tf": "W", "role": "resistance", "lo": 25400.0, "hi": 25450.0}, "protected_origin": 25600.0,
                    "projections": [{"ratio": 1.0, "price": 25500.0}]},
       "invalidated_if": "B closes below O 24,800.00 and a swing forms beyond O"}
STORY = ("Counter C leg — Daily DOWN, 1H correction: A complete (O 24,800.00 → HA 25,210.00), B pullback into the 1H demand area "
         "25,080.00–25,120.00, model C · E2 (C-a) · end zone: W resistance 25,400.00–25,450.00 · invalidated if B closes below O "
         "24,800.00 and a swing forms below O.")
C_VISIT = "C:" + VISIT


def c_entry(m="E2", sub="C-a"):
    return entry(m, d=1, visit=C_VISIT, family="C", sub_model=sub, story=STORY, model_c=CTX)


def test_model_c_switches_default_off_and_each_sub_way_is_its_own_switch():
    assert EE.model_c_on({}) is False and EE.model_c_on({"engine3_model_c_on": True}, "C-a") is False
    on = {"engine3_model_c_on": True, "engine3_model_c_a_on": "true"}
    assert EE.model_c_on(on, "C-a") is True and EE.model_c_on(on, "C-b") is False and EE.model_c_on(on) is True
    assert L.model_c_settings({}) is None and L.model_c_settings({"engine3_model_c_a_on": True}) is None   # model off ⇒ nothing
    got = L.model_c_settings({**on, "engine3_model_c_e_on": 1, "engine3_c_window": "b_and_ha_retest", "engine3_c_projections": "1, 1.618"})
    assert got == {"model_c": "on", "model_c_subs": ["C-a", "C-e"], "c_window": "b_and_ha_retest", "c_projections": (1.0, 1.618)}
    assert L.v22_settings({}) is None                                       # nothing set ⇒ V22 on decision3's defaults (model C off)
    assert L.v22_settings(on)["model_c"] == "on"
    for bad in ({**on, "engine3_c_window": "c_only"}, {**on, "engine3_c_projections": "x"}):
        with pytest.raises(L.SettingError):
            L.v22_settings(bad)


def test_model_c_entry_skipped_while_its_switch_is_off(es, opened):
    put(es, [c_entry()])
    gate_fn, calls = recorder()
    msg = run(es, gate_fn=gate_fn)                                         # dashboard default: model C OFF
    assert calls == [] and opened == [] and "model C / C-a OFF" in msg
    assert ES.entry_status(BOT, SYM, C_VISIT, "E2", es) == "SKIPPED_MODEL_C_OFF"


def test_model_c_sub_way_off_is_skipped_on(es, opened):
    put(es, [c_entry(sub="C-b")])
    gate_fn, calls = recorder()
    run(es, settings={**ST, "engine3_model_c_on": True, "engine3_model_c_a_on": True}, gate_fn=gate_fn)
    assert calls == [] and ES.entry_status(BOT, SYM, C_VISIT, "E2", es) == "SKIPPED_MODEL_C_OFF"


def test_model_c_on_opens_with_its_own_tag_and_card_tags(es, opened):
    put(es, [c_entry(), entry("E2")])                                       # a Daily-side E2 in another visit: its own claim
    gate_fn, calls = recorder()
    run(es, settings={**ST, "engine3_model_c_on": True, "engine3_model_c_a_on": True}, gate_fn=gate_fn,
        has_open=lambda s, src: False)
    tags = [c["tags"] for c in calls]
    assert [t.get("entry_family") for t in tags] == ["C", None]
    c = tags[0]
    assert c["entry_label"] == "C · E2 — Confirmation (C-a)" and c["entry_sub_model"] == "C-a" and c["entry_story"] == STORY
    assert c["entry_model_c"]["HA"]["price"] == 25210.0 and c["entry_visit"] == C_VISIT
    assert "entry_family" not in tags[1] and tags[1]["entry_label"] == "E2 — Confirmation"   # the Daily-side tags stay today's
    assert [o["tag"] for o in opened] == ["ENGINE_C_A_E2", "ENGINE_E2"]
    assert ES.entry_status(BOT, SYM, C_VISIT, "E2", es) == "EXECUTED" and ES.entry_status(BOT, SYM, VISIT, "E2", es) == "EXECUTED"


def test_statistics_keep_model_c_apart(db, tmp_path):
    for e in (c_entry(), c_entry("E4", "C-e"), entry("E2")):
        t = EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, e, "BULLISH" if e["direction"] > 0 else "BEARISH")
        VS.insert_signal({"bot": BOT, "symbol": SYM, "trading_mode": "PAPER", "mode": "human_confirm", "signal_ts": NOW,
                          "direction": "BULLISH", "level": 25100.0, "role": "Support", "setup_tf": "15M", "setup": {"tags": t}})
    p = str(tmp_path / "trades.db")
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE live_trades (trade_id TEXT, mode TEXT, entry_time TEXT, entry_reason_tag TEXT, status TEXT, exit_reason TEXT)")
    c.executemany("INSERT INTO live_trades VALUES (?,?,?,?,?,?)", [
        ("a", "PAPER", "2026-10-06 10:45:00", "ENGINE_C_A_E2", "OPEN", None),
        ("b", "PAPER", "2026-10-06 11:00:00", "ENGINE_E2", "CLOSED", "SPREAD_TARGET")])
    c.commit()
    c.close()
    d = EE.models_summary("2026-10-06", p)
    assert d["C-a · E2"] == {"cards": 1, "positions": 1, "open": 1, "stopped": 0, "target": 0, "other": 0}
    assert d["C-e · E4"]["cards"] == 1 and d["E2"] == {"cards": 1, "positions": 1, "open": 0, "stopped": 0, "target": 1, "other": 0}
    txt = EE.models_summary_text("2026-10-06", p)
    assert "C · E2 — Confirmation (C-a) 1 card, 1 position" in txt and "E2 — Confirmation 1 card" in txt
    assert EE.model_tag("E2") == "ENGINE_E2" and EE.tag_slot("ENGINE_E2") == "E2" and EE.tag_slot("ENGINE_SIGNAL") is None
    assert EE.tag_slot(EE.model_tag("E4", "C", "C-d")) == "C-d · E4"


def test_payload_carries_the_model_c_fields_and_daily_entries_stay_todays():
    daily = {**entry("E1"), "model_c_context": {"sub_model": "C-f", "cycle": "14:10", "end_zone": {}}}
    out = L.compact_entries([c_entry(), entry("E2"), daily])
    assert out[0]["family"] == "C" and out[0]["sub_model"] == "C-a" and out[0]["story"] == STORY
    assert out[0]["model_c"]["O"] == {"price": 24800.0, "ts": "x"} and out[0]["model_c"]["window"] == "b_only"
    assert out[1] == L.compact_entries([entry("E2")])[0] and "family" not in out[1] and "model_c" not in out[1]
    assert out[2]["model_c_context"] == {"sub_model": "C-f", "cycle": "14:10"} and "family" not in out[2]
    json.dumps(out)


def test_card_shows_the_story_line_and_the_c_label():
    t = EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, c_entry(), "BULLISH")
    lines = CS.model_lines(t)
    assert lines[0].startswith("🌊 Counter C leg — Daily DOWN") and CS.model_label(t) == "C · E2 — Confirmation (C-a)"
    plain = EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, entry("E2"), "BEARISH")
    assert not any(x.startswith("🌊") for x in CS.model_lines(plain))


def _c_sig():
    s = engine_sig()
    s["direction"] = "BULLISH"
    s["tags"] = {**s["tags"], "entry_model": "E2", "entry_name": "Confirmation", "entry_object": "area", "entry_family": "C",
                 "entry_sub_model": "C-a", "entry_story": STORY, "entry_model_c": CTX,
                 "entry_label": "C · E2 — Confirmation (C-a)"}
    return s


def test_vision_audit_gets_the_model_c_facts_and_stays_advisory():
    """DECISIONS 32 vs method P4 (OPEN_QUESTIONS, provisional: DECISIONS 32 wins for model C only): the audit facts name model C and
    its trend-side rule, so `trend_side` is not failed for being counter-trend; the prompt names the exception; a Daily-side signal's
    facts carry no model C line. No time framing and no numbers in the rules."""
    rd = EA.reading(_c_sig())
    assert rd["model_c"]["sub_model"] == "C-a" and rd["model_c"]["HA"] == 25210.0 and rd["model_c"]["daily"] == "DOWN"
    txt = EA.facts_text(_c_sig())
    assert "Model C (C-a, owner decision" in txt and "Trend side for this model C signal passes when" in txt
    assert "origin O 24,800.00" in txt and "HA 25,210.00" in txt
    assert "Model C" not in EA.facts_text(engine_sig()) and EA.reading(engine_sig())["model_c"] is None
    assert "model C" in EA.SYSTEM_PROMPT and "never a breakout entry" in EA.SYSTEM_PROMPT
    for text in (EA.SYSTEM_PROMPT, txt):
        assert not RS._DAY_RE.search(text.lower()), RS._DAY_RE.search(text.lower())
        assert not FORBIDDEN.search(text) and not CLOCK.search(text)
    rules = re.sub(r"\bE[1-4]\b|\b(15M|1H|5M)\b", "", EA.SYSTEM_PROMPT)
    assert not re.search(r"\d", rules)
    assert EA.KEYS[0] == "trend_side" and EA.VERDICTS == ("agree", "gray", "disagree")   # the checklist / verdict shape unchanged
