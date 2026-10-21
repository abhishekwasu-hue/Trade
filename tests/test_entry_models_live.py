"""Track H2 — live path for the entry models E1–E4 (decision3 rows carry payload `entries`). Fake engine rows only (no data, no network):
4 models in one visit ⇒ 4 Vision signals / 4 cards / 4 PAPER positions after ✅; same model twice in a visit ⇒ once; model OFF ⇒ skipped;
lots per model; one model's open / stopped position never blocks another; LIVE ⇒ never; dedupe keys (Vision open row / reuse /
cooldown); restart idempotency (persisted); the payload never drops `entries`; rows without `entries` ⇒ today's single-setup path."""
import datetime as dt
import json
import sqlite3

import pytest

import engine3_live as L
import engine_signal as ES
from paper import bot_hooks as PBH
from paper import engine_entry as EE
from tests.test_vision_v1 import ME, NOW, db  # noqa: F401 (fixture)
from vision import card_summary as CS
from vision import config as VC
from vision import decide as VD
from vision import gate as VG
from vision import store as VS
from vision import telegram_bot as TB
from vision import worker as VW

BOT = "srv2_momentum_reversal"
SYM = "NIFTY"
BAR = "2026-10-06 10:30:00"                                                    # NOW (vision clock) = 10:42:20 same day
RUN = "2026-10-06 10:42"
AREA = {"id": "Z15-7", "tf": "15M", "lo": 25080.0, "hi": 25120.0, "state": "ACTIVE"}
VISIT = "Z15-7@2026-10-06 10:00:00"
NAMES = {"E1": "Aggressive", "E2": "Confirmation", "E3": "Structure", "E4": "Sweep-retest (a)"}
ST = {"signal_source": "engine", "trading_mode": "PAPER", "lots": 1, "naked_lots": 0, "naked_enabled": False, "itm_depth_points": 100,
      "hedge_width_points": 150}
CHAIN = [{"underlying_spot_price": 25100.0}]


@pytest.fixture(autouse=True)
def _approval_on(monkeypatch):
    monkeypatch.setitem(VC.BOT_DEFAULTS, "approval_required", True)


@pytest.fixture
def es(tmp_path):
    return str(tmp_path / "es.db")


@pytest.fixture
def opened(monkeypatch):
    got = []

    def fake_open(access_token, symbol, settings, direction, level, lot_size, source, entry_tf, lots, naked_lots, chain=None,
                  open_fn=None, now=None, reason_tag="ENGINE_SIGNAL"):
        got.append({"symbol": symbol, "direction": direction, "level": level, "source": source, "lots": lots, "naked": naked_lots,
                    "tag": reason_tag})
        return [f"Credit Spread ✅ {reason_tag}"], 25100.0
    monkeypatch.setattr(EE, "open_paper", fake_open)
    return got


def entry(m, d=-1, visit=VISIT, area=AREA, label="A", **kw):
    return {"model": m, "name": NAMES[m], "direction": d, "side": "bear_call" if d < 0 else "bull_put", "area": dict(area),
            "visit_id": visit, "trigger_ts": BAR, "entry_ref": 25095.0, "label": label,
            "invalidation": {"price": 25135.0, "rule": "15M close above the area high"},
            "evidence": [{"name": "handover", "mark": "✓"}, {"name": "volume_growing", "mark": "✗"}, {"name": "confluence", "mark": "NA"}],
            **kw}


def put(p, entries, bar=BAR, decision=None, armed=None, extra=None):
    pay = {"engine": "decision3", "entries": entries, "armed": armed or [], **(extra or {})}
    ES.save({"symbol": SYM, "bar_ts": bar, "computed_at": bar, "decision": decision or ("setup" if entries else "wait"), "gate": None,
             "direction": None, "level_lo": None, "level_hi": None, "entry": None, "invalidation": None, "target": None, "grade": None,
             "reason": "x", "payload": json.dumps(pay)}, p)


def put_legacy(p, bar=BAR):
    ES.save({"symbol": SYM, "bar_ts": bar, "computed_at": bar, "decision": "setup", "gate": None, "direction": 1, "level_lo": 25000.0,
             "level_hi": 25020.0, "entry": 25030.0, "invalidation": 24980.0, "target": 25200.0, "grade": "B", "reason": "x",
             "payload": "{}"}, p)


class G:
    def __init__(self, action, lots=1, naked=0, note="", final=False, sid=None):
        self.action, self.lots, self.naked_lots, self.note, self.final, self.signal_id = action, lots, naked, note, final, sid


def run(p, settings=None, now=RUN, gate_fn=None, has_open=None, has_open_model=None, chain=CHAIN):
    return EE.process(BOT, "tok", SYM, settings or ST, 65, BOT, now=now, has_open=has_open or (lambda s, src: False),
                      gate_fn=gate_fn, chain=chain, path=p, symbols_fn=lambda: [SYM],
                      has_open_model=has_open_model or (lambda s, src, m: False), cutoff=(15, 0))


def recorder(action="ENTER"):
    calls = []

    def fn(*a, **k):
        calls.append({"args": a, "tags": k.get("tags")})
        return G(action)
    return fn, calls


def _pending(sid):
    VS.transition(sid, ("QUEUED",), "PENDING_HUMAN", None, deadline=VS._iso(NOW + dt.timedelta(minutes=10)), factor=1.0,
                  timeout_status="REJECTED", timeout_factor=0.0, median_range=1000.0)


def _approve(sid, when):
    cq = {"id": "c", "from": {"id": ME}, "message": {"chat": {"id": ME}, "message_id": 1}, "data": VD.callback_data(sid, "A")}
    ok, _ = TB.handle_callback(cq, now=when, answer=lambda *a: None, edit=lambda *a: None)
    assert ok


# ------------------------------------------------------------------------------------------------ 1. four models, one visit
def test_four_models_one_visit_four_cards_then_four_positions(db, es, opened, monkeypatch):
    monkeypatch.setenv("ENGINE_SIGNAL_DB", es)                                    # the card's engine line reads this store
    enter_now = []
    monkeypatch.setattr(EE, "enter_now", lambda bot, symbol, send=None: enter_now.append((bot, symbol)))   # ✅ ⇒ the bot's cycle at once
    put(es, [entry(m) for m in ("E1", "E2", "E3", "E4")])
    msg = run(es)                                                                  # the real Vision gate (approval required)
    assert msg.count("Vision / ✅ ची वाट") == 4 and not opened
    rows = [r for r in VS.list_signals() if r["bot"] == BOT]
    assert len(rows) == 4                                                          # same area / level, four separate signals
    assert sorted(VG._row_tags(r)["entry_model"] for r in rows) == ["E1", "E2", "E3", "E4"]
    assert run(es).count("Vision / ✅ ची वाट") == 4 and len(VS.list_signals()) == 4   # next cycle: same rows, no new signal
    d = VD.decide("human_confirm", "agree", {**VC.BOT_DEFAULTS})
    for r in rows:
        _pending(r["signal_id"])
        r = VS.get_signal(r["signal_id"])
        tags = VG._row_tags(r)
        cap = VW.v1_caption(r, {"verdict": "agree", "audits": [{"reason": "Sellers took over."}]}, d, r["deadline"])
        head = cap.split("\n")[0]
        assert head.startswith(f"{tags['entry_model']} — {NAMES[tags['entry_model']]} · {SYM}:")      # classic title line
        assert "invalidation (info): 25,135 — 15M close above the area high" in cap                   # the model invalidation (info)
        assert "evidence: ✓ handover · ✗ volume growing · NA confluence" in cap
        summ = VW.v1_caption(r, {"verdict": "agree"}, d, r["deadline"], layout="summary")
        assert summ.split("\n")[0].startswith(f"🟡 {SYM} · {tags['entry_model']} — {NAMES[tags['entry_model']]} · bear call · Label A")
        assert tags["gate"]["area"] == [25080.0, 25120.0] and tags["entry_visit"] == VISIT
    for r in rows:
        _approve(r["signal_id"], NOW + dt.timedelta(minutes=1))
    assert len(enter_now) == 4                                                     # every ✅ runs the cycle at once (same lock)
    msg = run(es)
    assert len(opened) == 4 and sorted(o["tag"] for o in opened) == ["ENGINE_E1", "ENGINE_E2", "ENGINE_E3", "ENGINE_E4"]
    assert all(o["source"] == BOT and o["lots"] == 1 and o["direction"] == "BEARISH" for o in opened)   # bot's own source ⇒ its exits
    assert all(ES.entry_status(BOT, SYM, VISIT, m, es) == "EXECUTED" for m in ("E1", "E2", "E3", "E4"))
    assert "नवा entry नाही" in run(es) and len(opened) == 4                     # never again in this visit


# ------------------------------------------------------------------------------------------------ 2. same model twice ⇒ once
def test_same_model_twice_in_a_visit_enters_once(es, opened):
    put(es, [entry("E1")], bar="2026-10-06 10:15:00")
    put(es, [entry("E1")], bar=BAR)                                                # the same (visit, model) again on a later bar
    gate_fn, calls = recorder()
    run(es, gate_fn=gate_fn)
    assert len(calls) == 1 and len(opened) == 1                                    # deduped inside the window
    put(es, [entry("E1")], bar="2026-10-06 10:45:00")
    run(es, now="2026-10-06 10:47", gate_fn=gate_fn)
    assert len(calls) == 1 and len(opened) == 1                                    # consumed ⇒ never re-fires in the visit
    put(es, [entry("E1", visit="Z15-7@2026-10-06 11:00:00")], bar="2026-10-06 11:15:00")
    run(es, now="2026-10-06 11:17", gate_fn=gate_fn)
    assert len(opened) == 2                                                        # a new visit ⇒ a new entry


def test_hold_keeps_the_entry_pending_and_reject_consumes_it(es, opened):
    put(es, [entry("E2")])
    assert "वाट" in run(es, gate_fn=lambda *a, **k: G("HOLD", note="वाट"))
    assert ES.entry_status(BOT, SYM, VISIT, "E2", es) is None                      # ✅ still awaited ⇒ next cycle asks the gate again
    put(es, [], bar="2026-10-06 10:45:00")                                         # a later "wait" bar does not cancel it
    assert "नाकारला" in run(es, now="2026-10-06 10:47", gate_fn=lambda *a, **k: G("HOLD", note="❌", final=True))
    assert ES.entry_status(BOT, SYM, VISIT, "E2", es) == "NOT_ENTERED_HOLD" and not opened


# ------------------------------------------------------------------------------------------------ 3. dashboard: OFF / lots
def test_model_off_is_skipped_without_a_card(es, opened):
    put(es, [entry("E1"), entry("E2"), entry("E3")])
    gate_fn, calls = recorder()
    msg = run(es, settings={**ST, "engine3_model_e2_on": False, "engine3_model_e3_on": "off"}, gate_fn=gate_fn)
    assert [c["tags"]["entry_model"] for c in calls] == ["E1"] and len(opened) == 1
    assert msg.count("model OFF (dashboard) ⇒ skip") == 2
    assert ES.entry_status(BOT, SYM, VISIT, "E2", es) == "SKIPPED_MODEL_OFF"


def test_lots_per_model(es, opened):
    put(es, [entry("E1"), entry("E2"), entry("E3"), entry("E4")])
    gate_fn = lambda *a, **k: G("ENTER", lots=a[9], naked=a[10])                 # noqa: E731 — gate passes the asked lots
    run(es, settings={**ST, "naked_enabled": True, "engine3_model_e1_lots": 2, "engine3_model_e2_lots": "3",
                      "engine3_model_e3_lots": "bad", "engine3_model_e4_lots": 0}, gate_fn=gate_fn)
    got = {o["tag"]: (o["lots"], o["naked"]) for o in opened}
    assert got == {"ENGINE_E1": (2, 2), "ENGINE_E2": (3, 3), "ENGINE_E3": (1, 1)}   # bad ⇒ default 1; 0 lots ⇒ skipped
    assert ES.entry_status(BOT, SYM, VISIT, "E4", es) == "SKIPPED_MODEL_ZERO_LOTS"


def test_model_settings_safe_parsing_and_defaults():
    import cloud_db
    d = cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]
    for m in ("e1", "e2", "e3", "e4"):
        assert d[f"engine3_model_{m}_on"] is True and d[f"engine3_model_{m}_lots"] == 1
    assert EE.model_on({}, "E1") and EE.model_on({"engine3_model_e1_on": ""}, "E1") and not EE.model_on({"engine3_model_e1_on": "false"}, "E1")
    assert not EE.model_on({"engine3_model_e1_on": False}, "E1") and EE.model_on({"engine3_model_e1_on": "yes"}, "E1")
    for v, want in ((None, 1), ("", 1), ("x", 1), (-2, 1), (float("nan"), 1), (True, 1), (2.7, 2), ("4", 4), (0, 0)):
        assert EE.model_lots({"engine3_model_e3_lots": v}, "E3") == want, v


# ------------------------------------------------------------------------------------------------ 4. stop-out of one model
def test_open_or_stopped_model_never_blocks_another(es, opened):
    put(es, [entry("E1"), entry("E2")])
    gate_fn, calls = recorder()
    msg = run(es, gate_fn=gate_fn, has_open=lambda s, src: True,                     # the bot-wide "one at a time" is not used here
              has_open_model=lambda s, src, m: m == "E1")                          # E1's own position is open
    assert [o["tag"] for o in opened] == ["ENGINE_E2"] and "आधीची E1 position उघडी" in msg
    assert ES.entry_status(BOT, SYM, VISIT, "E1", es) is None                      # not consumed: E1 may still enter in this window
    run(es, gate_fn=gate_fn)                                                       # E1 stopped out (closed) ⇒ E1 free again
    assert sorted(o["tag"] for o in opened) == ["ENGINE_E1", "ENGINE_E2"]
    put(es, [entry("E3")], bar="2026-10-06 10:45:00")                              # E1 / E2 stopped earlier ⇒ E3 of the same visit
    run(es, now="2026-10-06 10:47", gate_fn=gate_fn, has_open_model=lambda s, src, m: m in ("E1", "E2"))
    assert sorted(o["tag"] for o in opened) == ["ENGINE_E1", "ENGINE_E2", "ENGINE_E3"]


def test_one_entry_error_does_not_stop_the_others(es, monkeypatch):
    got = []

    def boom(*a, **k):
        if k.get("reason_tag") == "ENGINE_E1":
            raise RuntimeError("broker down")
        got.append(k.get("reason_tag"))
        return ["ok"], 25100.0
    monkeypatch.setattr(EE, "open_paper", boom)
    put(es, [entry("E1"), entry("E2")])
    msg = run(es, gate_fn=recorder()[0])
    assert got == ["ENGINE_E2"] and "PAPER open त्रुटी" in msg
    assert ES.entry_status(BOT, SYM, VISIT, "E1", es).startswith("OPEN_FAILED")   # claimed ⇒ never a second try in this visit
    run(es, gate_fn=recorder()[0])
    assert got == ["ENGINE_E2"]


# ------------------------------------------------------------------------------------------------ 5. LIVE ⇒ never
def test_live_never(es, opened):
    put(es, [entry("E1")])
    gate_fn, calls = recorder()
    assert "फक्त PAPER" in run(es, settings={**ST, "trading_mode": "LIVE"}, gate_fn=gate_fn)
    assert not calls and not opened and ES.entry_status(BOT, SYM, VISIT, "E1", es) is None
    hit = []
    pre = PBH.pre_cycle(BOT, "tok", SYM, {**ST, "trading_mode": "LIVE"}, 65, engine_fn=lambda *a, **k: hit.append(a))
    assert not hit and not pre.stop                                                # LIVE: the engine path never runs
    sent = []
    m = EE.enter_now(BOT, SYM, send=sent.append, settings_fn=lambda k, s: {**ST, "trading_mode": "LIVE"},
                     cycle_fn=lambda tok: hit.append(tok))
    assert "LIVE never" in m and not hit


# ------------------------------------------------------------------------------------------------ 6. dedupe keys (Vision)
def test_vision_keys_carry_the_model(db):
    t1 = EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, entry("E1"), "BEARISH")
    t2 = EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, entry("E2"), "BEARISH")
    j = lambda t: json.dumps({"tags": t})                                          # noqa: E731
    assert VS._reuse_tags(j(t1)) != VS._reuse_tags(j(t2))                          # different model ⇒ different reuse key
    assert VS._reuse_tags(j({})) == (False, False, None)                           # every other signal: today's key + None
    r1 = {"direction": "BEARISH", "setup_json": j(t1)}
    assert VG._same_setup(r1, "BEARISH", t1) and not VG._same_setup(r1, "BEARISH", t2)
    t1b = {**t1, "entry_visit": "Z15-7@later"}
    assert not VG._same_setup(r1, "BEARISH", t1b) and VG._same_setup(r1, "BEARISH", t1b, visit=False)   # new visit; cooldown = model
    assert VG._same_setup({"direction": "BULLISH", "setup_json": "{}"}, "BULLISH", {})          # legacy unchanged
    # reuse of a finished Vision verdict: only the same model
    base = {"bot": BOT, "symbol": SYM, "trading_mode": "PAPER", "mode": "human_confirm", "signal_ts": NOW, "direction": "BEARISH",
            "level": 25100.0, "role": "Resistance", "setup_tf": "15M", "spot": 25100.0}
    sid = VS.insert_signal({**base, "setup": {"tags": t1}})
    VS.finish(sid, "DONE", verdict="agree", prompt_version="p")
    assert VS.find_reusable({**base, "setup_json": j(t2)}, 15) is None
    assert VS.find_reusable({**base, "setup_json": j(t1)}, 15)["signal_id"] == sid


def test_rejected_model_cooldown_is_per_model(db, es, monkeypatch, tmp_path):
    monkeypatch.setitem(VC.BOT_DEFAULTS, "shadow_cooldown_min", 30)
    monkeypatch.setenv("PAPER_JOURNAL_DB", str(tmp_path / "pj.db"))              # the would-have note of the rejected E1
    tags = lambda m: EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, entry(m), "BEARISH")   # noqa: E731
    g1 = VG.entry_gate(BOT, SYM, "PAPER", "BEARISH", 25100.0, "Resistance", "15M", NOW, 25100.0, 1, 0, tags=tags("E1"))
    VS.transition(g1.signal_id, "QUEUED", "REJECTED", None, decided_at=VS._iso(NOW), decided_by=f"telegram:{ME}", factor=0.0)
    assert VG.entry_gate(BOT, SYM, "PAPER", "BEARISH", 25100.0, "Resistance", "15M", NOW, 25100.0, 1, 0, tags=tags("E1")).final
    g2 = VG.entry_gate(BOT, SYM, "PAPER", "BEARISH", 25100.0, "Resistance", "15M", NOW, 25100.0, 1, 0, tags=tags("E2"))
    assert g2.status == "SKIPPED_VISION_PENDING" and g2.signal_id != g1.signal_id   # E1 rejected ⇒ E2 still asks (own signal)
    g1b = VG.entry_gate(BOT, SYM, "PAPER", "BEARISH", 25100.0, "Resistance", "15M", NOW, 25100.0, 1, 0, tags=tags("E1"))
    assert g1b.status == "SKIPPED_VISION_COOLDOWN"                                 # E1 again ⇒ today's cooldown for that model


# ------------------------------------------------------------------------------------------------ 7. restart idempotency
def test_restart_idempotency_is_persisted(es, opened, tmp_path):
    put(es, [entry("E1"), entry("E2")])
    run(es, gate_fn=recorder()[0])
    assert len(opened) == 2
    c = sqlite3.connect(es)                                                        # a fresh process sees the same store
    got = sorted(tuple(r) for r in c.execute("SELECT bot, symbol, visit_id, model, status FROM engine_entry_consumed"))
    c.close()
    assert got == [(BOT, SYM, VISIT, "E1", "EXECUTED"), (BOT, SYM, VISIT, "E2", "EXECUTED")]
    gate_fn, calls = recorder()                                                   # "restart": nothing in memory, only the store
    msg = EE.process(BOT, "tok", SYM, ST, 65, BOT, now=RUN, has_open=lambda s, src: False, gate_fn=gate_fn, chain=CHAIN, path=es,
                     symbols_fn=lambda: [SYM], has_open_model=lambda s, src, m: False, cutoff=(15, 0))
    assert not calls and len(opened) == 2 and "नवा entry नाही" in msg
    assert not ES.claim_entry(BOT, SYM, VISIT, "E1", "ENTERING", BAR, es)            # the key is taken (INSERT OR IGNORE)
    assert ES.claim_entry(BOT, SYM, VISIT, "E3", "ENTERING", BAR, es) and ES.entry_status(BOT, SYM, VISIT, "E3", es) == "ENTERING"
    put(es, [entry("E3")], bar="2026-10-06 10:45:00")                              # claimed (crash before EXECUTED) ⇒ never re-entered
    EE.process(BOT, "tok", SYM, ST, 65, BOT, now="2026-10-06 10:47", has_open=lambda s, src: False, gate_fn=gate_fn, chain=CHAIN,
               path=es, symbols_fn=lambda: [SYM], has_open_model=lambda s, src, m: False, cutoff=(15, 0))
    assert not calls and len(opened) == 2


def test_cutoff_and_direction_off_consume_per_model(es, opened):
    put(es, [entry("E1"), entry("E2", d=1)])
    gate_fn, calls = recorder()
    run(es, settings={**ST, "bullish_entry_enabled": False}, gate_fn=gate_fn)
    assert ES.entry_status(BOT, SYM, VISIT, "E2", es) == "SKIPPED_DIRECTION_OFF" and [o["tag"] for o in opened] == ["ENGINE_E1"]
    put(es, [entry("E3")], bar="2026-10-06 14:45:00")
    EE.process(BOT, "tok", SYM, ST, 65, BOT, now="2026-10-06 15:05", has_open=lambda s, src: False, gate_fn=gate_fn, chain=CHAIN, path=es,
               symbols_fn=lambda: [SYM], has_open_model=lambda s, src, m: False, cutoff=(15, 0))
    assert ES.entry_status(BOT, SYM, VISIT, "E3", es) == "SKIPPED_CUTOFF" and len(opened) == 1


# ------------------------------------------------------------------------------------------------ 8. payload never drops `entries`
def _v22(entries, armed=None, big=0):
    return {"bar_end": BAR, "ts": BAR, "decision": "setup" if entries else "wait", "level": None, "risk": None,
            "checklist": {"①": (True, "x" * big)}, "watch_list": [{"lo": 1.0, "hi": 2.0, "note": "y" * big}],
            "zone_read": {"summary": {"z": "z" * big}}, "entries": entries, "armed": armed or [], "legacy_k_gate": {"k": "q" * big}}


def test_payload_carries_entries_and_never_drops_them():
    ents = [entry(m) for m in ("E1", "E2", "E3", "E4")]
    armed = [{"area": {**AREA, "extra": "x"}, "visit_id": VISIT, "armed": ["E2", "E3"], "fired": ["E1"], "blob": {"a": 1}}]
    row = L.row_from_v22(SYM, _v22(ents, armed), lambda: RUN)
    pay = json.loads(row["payload"])
    assert [e["model"] for e in pay["entries"]] == ["E1", "E2", "E3", "E4"] and pay["entries"][0]["area"] == AREA
    assert pay["entries"][0]["invalidation"] == {"price": 25135.0, "rule": "15M close above the area high"}
    assert pay["armed"] == [{"area": AREA, "visit_id": VISIT, "armed": ["E2", "E3"], "fired": ["E1"]}]   # compact
    assert row["decision"] == "setup"
    for big in (6000, 30000):                                                      # display keys trimmed first; entries stay
        pay = json.loads(L.row_from_v22(SYM, _v22(ents, armed, big), lambda: RUN)["payload"])
        assert [e["model"] for e in pay["entries"]] == ["E1", "E2", "E3", "E4"] and pay["armed"][0]["fired"] == ["E1"]
        assert "dropped" in pay and "legacy_k_gate" not in pay
    tiny = json.loads(L.fit_payload({"engine": "decision3", "checklist": "c" * 500, "entries": ents, "armed": armed}, limit=100))
    assert tiny["dropped"] == "all context (payload too large)" and [e["model"] for e in tiny["entries"]] == ["E1", "E2", "E3", "E4"]
    old = L.row_from_v22(SYM, {k: v for k, v in _v22([]).items() if k not in ("entries", "armed", "legacy_k_gate")}, lambda: RUN)
    assert "entries" not in json.loads(old["payload"])                             # an older engine ⇒ no key ⇒ legacy path


def test_pending_entries_reads_the_stored_row(es):
    row = L.row_from_v22(SYM, _v22([entry("E1"), {"model": "E9"}, entry("E2", visit="")]), lambda: RUN)
    ES.save(row, es)
    got = ES.pending_entries(BOT, SYM, ST, RUN, es)
    assert [(e["model"], e["visit_id"]) for _r, e in got] == [("E1", VISIT)]    # bad items ignored, never guessed
    assert "E1 ↓ bear call" in ES.opinion(SYM, RUN, es)
    assert ES.own_allowed(SYM, "BEARISH", {"signal_source": "both"}, RUN, es)[0]
    assert not ES.own_allowed(SYM, "BULLISH", {"signal_source": "both"}, RUN, es)[0]


# ------------------------------------------------------------------------------------------------ 9. old rows ⇒ today's behaviour
def test_rows_without_entries_keep_the_legacy_path(es, opened):
    put_legacy(es)
    gate_fn, calls = recorder()
    assert ES.pending_entries(BOT, SYM, ST, RUN, es) is None
    msg = run(es, gate_fn=gate_fn, has_open=lambda s, src: True)
    assert "आधीची position उघडी (एका वेळी एकच)" in msg and not calls             # today's one-at-a-time check
    run(es, gate_fn=gate_fn)
    assert len(calls) == 1 and "entry_model" not in calls[0]["tags"] and opened[0]["tag"] == "ENGINE_SIGNAL"
    assert "नवा setup नाही" in run(es, gate_fn=gate_fn)


def test_store_error_fails_closed(es, monkeypatch):
    monkeypatch.setattr(ES, "connect", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    assert ES.pending_entries(BOT, SYM, ST, RUN, es) == []                         # never the legacy path on an error
    assert not ES.claim_entry(BOT, SYM, VISIT, "E1", "ENTERING", BAR, es)


# ------------------------------------------------------------------------------------------------ 10. summaries / labels
def test_day_summary_per_model(db, tmp_path):
    t = lambda m: EE.entry_gate_tags({"bar_ts": BAR, "payload": "{}"}, entry(m), "BEARISH")   # noqa: E731
    for m in ("E1", "E1", "E2"):
        VS.insert_signal({"bot": BOT, "symbol": SYM, "trading_mode": "PAPER", "mode": "human_confirm", "signal_ts": NOW,
                          "direction": "BEARISH", "level": 25100.0, "role": "Resistance", "setup_tf": "15M", "setup": {"tags": t(m)}})
    p = str(tmp_path / "trades.db")
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE live_trades (trade_id TEXT, mode TEXT, entry_time TEXT, entry_reason_tag TEXT, status TEXT, exit_reason TEXT)")
    c.executemany("INSERT INTO live_trades VALUES (?,?,?,?,?,?)", [
        ("a", "PAPER", "2026-10-06 10:45:00", "ENGINE_E1", "CLOSED", "TSL_SL"),
        ("b", "PAPER", "2026-10-06 11:00:00", "ENGINE_E1", "OPEN", None),
        ("c", "PAPER", "2026-10-06 11:00:00", "ENGINE_E2", "CLOSED", "SPREAD_TARGET"),
        ("d", "PAPER", "2026-10-06 11:00:00", "ENGINE_SIGNAL", "OPEN", None),
        ("e", "LIVE", "2026-10-06 11:00:00", "ENGINE_E3", "OPEN", None)])
    c.commit()
    c.close()
    d = EE.models_summary("2026-10-06", p)
    assert d == {"E1": {"cards": 2, "positions": 2, "open": 1, "stopped": 1, "target": 0, "other": 0},
                 "E2": {"cards": 1, "positions": 1, "open": 0, "stopped": 0, "target": 1, "other": 0}}
    txt = EE.models_summary_text("2026-10-06", p)
    assert txt.startswith("<b>Entry models today</b>: E1 — Aggressive 2 cards, 2 positions (open 1, stopped 1, target 0)")
    assert EE.models_summary_text("2026-10-07", p) == ""                           # no activity ⇒ today's summary unchanged


def test_cards_without_a_model_stay_todays():
    row = {"symbol": SYM, "direction": "BULLISH", "level": 25000.0, "setup_tf": "15M", "setup_json": json.dumps({"tags": {"engine": True}})}
    assert VW.plain_head(row).startswith(f"{SYM}: a bull put")
    assert CS.line_head(row, "PENDING_HUMAN") == f"🟡 {SYM} · bull put — घ्यायचा?"
    assert CS.model_lines({"engine": True}) == []
    assert CS.evidence_text({"required": "present", "confirming": {"rsi_divergence": "absent", "confluence": None}}) == \
        "✓ required · ✗ rsi divergence · NA confluence"
