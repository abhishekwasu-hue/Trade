"""Layer 6 output consistency (the layer 6 gallery, awaiting Abhi ✅) — the card / Vision facts say what the engine read:

  O-1 next area: the card's / Vision facts' next area in the trade direction (the target: the next opposite area) is the engine's own
      (engine3_live.next_area_of at the decision's 15M bar ⇒ payload entry `next_area` ⇒ tags gate.next_area), never the chart band
      finder; the engine knows none ahead ⇒ "none known"; an older row (no next_area) keeps today's fallback;
  O-2 label: the Vision facts print the entry's A / B label (method §5, L6-a), never the model's name as "label"; no label ⇒ said so;
  O-3 label on every card layout: the evidence line carries "(label A)" / "(label B)" (the classic card had no label at all);
  O-5 an engine entry model's card has no level-bot "🎯 Confirmation … grade None" line; its details 'Area' line has the area's own TF;
  O-6 a broken line object keeps the state the engine read (BROKEN) on the card / Vision facts.
Display only: no reading rule, no decision, no number added (tests/test_method_no_numbers.py unchanged)."""
import json

import pandas as pd

import engine3_live as L
from paper import engine_entry as EE
from vision import card_summary as CS
from vision import decide as VD
from vision import engine_audit as EA
from vision import worker as VW


class Lev:
    def __init__(self, snap):
        self._snap = snap

    def snapshot(self, t):
        return list(self._snap)


class V:
    def __init__(self, snap):
        self.levels = Lev(snap)


SNAP = [{"id": 1, "tf": "1H", "role": "support", "lo": 55100.0, "hi": 55180.0, "state": "ACTIVE", "trade_location": True},
        {"id": 2, "tf": "1H", "role": "support", "lo": 55400.0, "hi": 55450.0, "state": "BROKEN", "trade_location": True},
        {"id": 3, "tf": "W", "role": "support", "lo": 55300.0, "hi": 55600.0, "state": "ACTIVE", "trade_location": False},
        {"id": 4, "tf": "1H", "role": "resistance", "lo": 55699.45, "hi": 55970.15, "state": "FLIPPED", "trade_location": True},
        {"id": 5, "tf": "D", "role": "support", "lo": 54800.0, "hi": 54900.0, "state": "DEAD", "trade_location": True}]

E5 = {"model": "E1", "name": "Aggressive", "direction": -1, "visit_id": "4@2026-10-15 10:00:00", "trigger_tf": "5M", "object": "area",
      "trigger_ts": "2026-10-15 10:05:00", "entry_ref": 55720.7, "invalidation": {"price": 55762.6, "rule": "price above the refined base"},
      "area": {"id": 4, "tf": "1H", "role": "resistance", "lo": 55699.45, "hi": 55970.15, "state": "FLIPPED", "object": "area"},
      "refined_base": {"lo": 55699.45, "hi": 55762.6, "ts": "2026-09-25 14:00:00"}, "label": None,
      "evidence": [["required set (handover + commitment + volume + LTF CHoCH)", "✗"], ["volume growing inside", "NA"],
                   ["RSI divergence", "✗"], ["confluence", "✓"], ["correction line closed through", "NA"],
                   ["counter channel broken in the trade direction (handover evidence; context)", "✓"]],
      "evidence_list": {"required": "absent", "confirming": {"confluence": "present"}},
      "trigger_bar_end": "2026-10-15 10:10:00", "context_bar_ts": "2026-10-15 09:45:00", "trigger_bar15_ts": "2026-10-15 10:00:00",
      "trigger_ohlc": {"open": 55650.0, "high": 55730.0, "low": 55640.0, "close": 55720.7}, "visit_start5": "2026-10-15 10:00:00",
      "facts": {}}


def stored_row(areas_alive=True, entry=E5):
    r = {"bar_end": "2026-10-15 10:10:00", "ts": "2026-10-15 10:05:00", "decision": "wait", "entries": [dict(entry)], "armed": [],
         "context_bar": 7, "level": {}, "trend_used": "DOWN", "daily_trend": "DOWN"}
    if areas_alive:                                                         # the live path (decide_live) attaches the engine's next area
        L.attach_next_areas(V(SNAP), r)
    return L.row_from_v22("BANKNIFTY", r, lambda: "2026-10-15 10:11:00")


def sig_of(row, e=E5):
    ce = json.loads(row["payload"])["entries"][0]
    tags = EE.entry_gate_tags(row, ce, "BEARISH")
    return {"symbol": "BANKNIFTY", "direction": "BEARISH", "tags": tags, "spot": e["entry_ref"], "signal_ts": row["bar_ts"]}, ce


# ------------------------------------------------------------------------------------------------ O-1 next area
def test_next_area_of_is_the_nearest_alive_opposite_area_beyond_the_entry():
    nx = L.next_area_of(V(SNAP), 7, E5)                                     # bear call at 55,720.7 ⇒ the demand areas below
    assert (nx["id"], nx["lo"], nx["hi"]) == ("1", 55100.0, 55180.0)      # BROKEN 2, context-only Weekly 3 and DEAD 5 left out
    bp = {**E5, "direction": 1, "entry_ref": 55000.0}
    assert L.next_area_of(V(SNAP), 7, bp)["id"] == "4"                     # bull put ⇒ the supply above
    assert L.next_area_of(V([x for x in SNAP if x["role"] == "resistance"]), 7, E5) is None


def test_the_payload_entry_carries_the_next_area_and_older_rows_do_not():
    pay = json.loads(stored_row()["payload"])
    assert pay["entries"][0]["next_area"] == {"id": "1", "tf": "1H", "role": "support", "lo": 55100.0, "hi": 55180.0, "state": "ACTIVE"}
    assert "next_area" not in json.loads(stored_row(areas_alive=False)["payload"])["entries"][0]
    r = {"entries": [dict(E5)], "context_bar": 7}
    L.attach_next_areas(object(), r)                                       # unreadable ⇒ left out, never raises
    assert "next_area" not in r["entries"][0]


def test_next_area_is_the_engines_own_opposite_area_not_the_chart_band_finder():
    sig, _ce = sig_of(stored_row())
    fb = [{"role": "support", "lo": 55500.0, "hi": 55560.0}]                   # a chart band nearer to price than the engine's area
    nx = EA.reading(sig, fallback_areas=fb)["next_area"]
    assert (nx["lo"], nx["hi"], nx["source"]) == (55100.0, 55180.0, "engine")
    assert "Next area in the trade direction: support 55,100.00 - 55,180.00." in EA.facts_text(sig, EA.reading(sig, fallback_areas=fb))
    old, _ = sig_of(stored_row(areas_alive=False))                            # older row ⇒ today's fallback, unchanged
    assert "next_area" not in old["tags"]["gate"]
    assert EA.reading(old, fallback_areas=fb)["next_area"]["source"] == "chart band finder"


# ------------------------------------------------------------------------------------------------ O-2 / O-3 label
def test_vision_facts_print_the_a_b_label_never_the_model_name():
    sig, _ = sig_of(stored_row())
    txt = EA.facts_text(sig)
    assert "label E1 — Aggressive" not in txt and "| no A / B label (the legacy 6a required set reads absent)" in txt
    ea = {**E5, "label": "A", "evidence_list": {"required": "present", "confirming": {"confluence": "present"}}}
    sa, _ = sig_of(stored_row(entry=ea), ea)
    assert "Entry model: E1 Aggressive | label A (the model's own conditions + at least one confirming piece" in EA.facts_text(sa)
    eb = {**ea, "label": "B"}
    sb, _ = sig_of(stored_row(entry=eb), eb)
    assert "| label B (the model's own conditions only)." in EA.facts_text(sb)
    assert EA.label_words({"model": None}) == ""


def test_the_evidence_line_carries_the_label_on_every_layout():
    ea = {**E5, "label": "A", "evidence_list": {"required": "present", "confirming": {"confluence": "present"}}}
    sa, _ = sig_of(stored_row(entry=ea), ea)
    ln = [x for x in CS.model_lines(sa["tags"]) if " evidence" in x][0]
    assert ln.startswith("📋 E1 — Aggressive evidence (label A): ")
    s0, _ = sig_of(stored_row())
    assert [x for x in CS.model_lines(s0["tags"]) if " evidence" in x][0].startswith("📋 E1 — Aggressive evidence: ✗ required set")


# ------------------------------------------------------------------------------------------------ O-4 / O-5 the card
def card(sig, layout="classic"):
    row = {"signal_id": "x", "bot": "srv2_momentum_reversal", "symbol": "BANKNIFTY", "trading_mode": "PAPER", "mode": "human_confirm",
           "signal_ts": pd.Timestamp("2026-10-15 10:10"), "direction": "BEARISH", "level": 55834.8, "role": "Resistance",
           "setup_tf": "15M", "spot": 55720.7, "setup_json": json.dumps({"tags": sig["tags"]}), "tags": sig["tags"],
           "bot_label": "Price-action engine (PAPER)"}
    d = VD.Decision("PENDING_HUMAN", 1.0, "human_confirm", "REJECTED", 0.0, True)
    res = {"verdict": "unavailable", "error": "x" * 60}
    return VW.v1_caption(row, res, d, deadline=pd.Timestamp("2026-10-15 10:20"), layout=layout, window_min=10, approval=True)


def test_no_level_bot_grade_line_and_the_area_tf_is_the_areas_own(monkeypatch):
    monkeypatch.setattr(VW, "engine_line", lambda row: "engine: NA")
    orig = VW._fit
    monkeypatch.setattr(VW, "_fit", lambda lines, limit=1024, keep=2, protect=None: "\n".join(lines))   # every line, uncut
    sig, _ = sig_of(stored_row())
    cap = card(sig)
    monkeypatch.setattr(VW, "_fit", orig)
    det = VW.engine_details({"signal_id": "x", "bot": "srv2_momentum_reversal", "symbol": "BANKNIFTY", "mode": "human_confirm",
                             "signal_ts": pd.Timestamp("2026-10-15 10:10"), "direction": "BEARISH", "level": 55834.8,
                             "role": "Resistance", "setup_tf": "15M", "tags": sig["tags"], "bot_label": "Price-action engine (PAPER)"},
                            {"verdict": "unavailable"})                           # DECISIONS 52: the details = the reply
    for t in (cap, det):
        assert "🎯 Confirmation:" not in t and "grade None" not in t
    assert "(Resistance, 1H) · signal 10:10" in det and "• Area: supply 55,699–55,970 (1H, flipped)" in cap


def test_a_broken_line_object_keeps_its_engine_state_on_the_card_and_in_the_facts():
    ln = {**E5, "model": "E4", "name": "Sweep-retest (b)", "object": "broken_line", "refined_base": None,
          "area": {"id": "line:D2:H+:1-2|par", "tf": "line", "role": "resistance", "lo": 55710.0, "hi": 55710.0, "state": "BROKEN",
                   "object": "broken_line", "line": {"id": "D2:H+:1-2|par", "tf": "1H", "degree": 2, "family": "rising line of lows",
                                                     "break_side": "down"}}}
    r = {"bar_end": "2026-10-15 10:10:00", "ts": "2026-10-15 10:05:00", "decision": "wait", "entries": [ln], "armed": [],
         "level": {"id": "line:D2:H+:1-2|par", "tf": "line", "role": "resistance", "lo": 55710.0, "hi": 55710.0}}
    row = L.row_from_v22("BANKNIFTY", r, lambda: "2026-10-15 10:11:00")
    sig, _ = sig_of(row, ln)
    assert EA.reading(sig)["area"]["state"] == "BROKEN"
    assert "| state BROKEN." in EA.facts_text(sig)


def test_no_opposite_area_in_the_engine_reading_means_none_known_never_a_chart_band():
    r = {"bar_end": "2026-10-15 10:10:00", "ts": "2026-10-15 10:05:00", "decision": "wait", "entries": [dict(E5)], "armed": [],
         "context_bar": 7, "level": {}}
    L.attach_next_areas(V([x for x in SNAP if x["role"] == "resistance"]), r)      # the engine knows no demand area ahead
    sig, _ = sig_of(L.row_from_v22("BANKNIFTY", r, lambda: "2026-10-15 10:11:00"))
    assert "next_area" in sig["tags"]["gate"] and sig["tags"]["gate"]["next_area"] is None
    assert EA.reading(sig, fallback_areas=[{"role": "support", "lo": 55500.0, "hi": 55560.0}])["next_area"] is None
    assert "Next area in the trade direction: none known." in EA.facts_text(sig)
