"""Live reading check (owner-orders DECISIONS 38–41; BANKNIFTY E4 (b) bear call at a broken line, Abhi approved it, wrong by the method),
both mirrors, synthetic (CI-safe):

1. DECISIONS 38 — E4 (b) approach side (H2): the retest of a line / area broken DOWN (bear call) needs price to come back UP to it
   from below and be rejected there; a candle coming DOWN from above (the original side, where price was accepted) and closing
   through the object is a breakdown candle — never an E4 (b). `e4b_approach_rule = any` = the earlier reading (what-if).
2. DECISIONS 39 — a line broken back (close + swing on its original side) is dead: covered by `trendline.broken_back_at` (#373,
   tests/test_entry_models_broken_back.py); here only that the approach rule does not change that reading.
3. DECISIONS 40 — range edges are areas: bear call at the upper edge, bull put at the lower edge (trade side, P4), E1–E4 there.
4. DECISIONS 41 — the card / Vision text names a line object as a line with its timeframe ("broken 1H line at X, retest from below"),
   never "supply area X–X (0 pts)"; the header shows the signal's own symbol first, the bot name only as a small label.
"""
import json
from types import SimpleNamespace as NS

import pytest

from decision3 import entry_models as EM
from decision3 import range_edges as RE
from decision3 import trendline as TL
from tests.test_decision3_entry_models import MID, _bare, _mirror_rows

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
UP, DOWN = 1, -1
REJECT = 9
# A rising line of lows (95 + 0.5·bar) broken DOWN (closes below from bar 2, the swing low 93.0 at bar 3 known at bar 4). Price comes
# back UP through it (bar 5 closes above) and is ACCEPTED above (bars 5 … 8 close above, no swing of the line's degree ⇒ not broken
# back); bar 9 opens ABOVE the line and closes below it: a breakdown candle from above (the live case).
FROM_ABOVE = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 95.6, 96.1, 1.0), (96.1, 96.2, 94.0, 94.2, 1.0), (94.2, 94.3, 93.0, 93.2, 1.0),
              (93.2, 94.6, 93.1, 94.5, 1.0), (94.5, 97.8, 94.4, 97.7, 1.0), (97.7, 100.2, 97.6, 99.9, 1.0), (99.9, 101.0, 99.5, 100.8, 1.0),
              (100.8, 101.2, 100.0, 100.5, 1.0), (100.5, 100.7, 98.0, 98.2, 1.0)]
# The proper retest: price comes back UP from below to the line (bar 9 opens below it, its high reaches it, it closes back below).
FROM_BELOW = FROM_ABOVE[:5] + [(94.5, 95.0, 94.0, 94.8, 1.0), (94.8, 95.5, 94.6, 95.3, 1.0), (95.3, 96.0, 95.1, 95.8, 1.0),
                               (95.8, 96.6, 95.6, 96.4, 1.0), (96.4, 99.7, 96.2, 96.5, 1.0)]


def _line_case(mirror, monkeypatch, rows, form="strong_close", swings=(), s=None):
    import decision3.method as M
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s_, tss=None: (form, 1) if t == REJECT else None)
    ln = {"family": "rising line of lows", "kind": "L", "slope_dir": "rising", "degree": 2, "tf": "1H", "p1": [0, 95.0], "p2": [1, 95.5],
          "slope": 0.5, "touches": 2, "touch_groups": [[0], [1]], "value_t": 0.0, "broken": True, "break_bar": 2,
          "break_side": "down", "state": "BROKEN", "id": "D2:L+:0-1"}
    sw = list(swings)
    if mirror:
        rows = _mirror_rows(rows)
        ln = {**ln, "family": "falling line of highs", "kind": "H", "slope_dir": "falling", "p1": [0, 2 * MID - 95.0],
              "p2": [1, 2 * MID - 95.5], "slope": -0.5, "break_side": "up", "id": "D2:H-:0-1"}
        sw = [({"H": "L", "L": "H"}[k], 2 * MID - p, b, c) for k, p, b, c in sw]
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [ln])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    V, _lvl, _d = _bare(rows, sw, mirror=False, s=s, trend_at=lambda u: "UP" if mirror else "DOWN")
    return V, ln, (UP if mirror else DOWN)


def _fired(V, d, n):
    return [(t, f) for t in range(4, n) for f in EM.Reader(V).broken(t, d)[1]]


@MIRRORS
def test_a_breakdown_candle_from_the_original_side_is_never_an_e4b(mirror, monkeypatch):
    """Price was accepted on the line's original side and the trigger candle came down from there and closed through the line ⇒ H2,
    no E4 (b). The earlier reading (`e4b_approach_rule = any`) fired it — the live entry."""
    V, ln, d = _line_case(mirror, monkeypatch, FROM_ABOVE)
    assert all(TL.broken_back_at(V, ln, t) is None for t in range(len(FROM_ABOVE)))   # not broken back (no swing of the line's degree)
    assert _fired(V, d, len(FROM_ABOVE)) == []
    armed = [a for a in EM.Reader(V).broken(REJECT, d)[0] if a["area_id"] == "line:" + ln["id"]]
    assert armed and "DECISIONS 38" in armed[0]["models"]["E4"]["waiting"]
    V2, _ln, _d = _line_case(mirror, monkeypatch, FROM_ABOVE, s={"e4b_approach_rule": "any"})
    assert [t for t, _ in _fired(V2, d, len(FROM_ABOVE))] == [REJECT]


@MIRRORS
def test_a_retest_from_the_break_side_still_fires(mirror, monkeypatch):
    V, ln, d = _line_case(mirror, monkeypatch, FROM_BELOW)
    fired = _fired(V, d, len(FROM_BELOW))
    assert [t for t, _ in fired] == [REJECT]
    f = fired[0][1]
    assert f["obj"]["line"]["tf"] == "1H" and f["obj"]["line"]["degree"] == 2 and f["obj"]["line"]["break_side"] == ln["break_side"]


@MIRRORS
def test_a_revisit_that_came_from_the_original_side_is_no_retest(mirror, monkeypatch):
    """A swing that does not reach the line (on its original side) ends the revisit; price then comes back to the line from the
    original side: even a two-candle form whose first candle opened at the line is not a retest from the break side."""
    rows = FROM_ABOVE[:9] + [(99.6, 99.8, 98.0, 98.2, 1.0)]                # bar 9 opens just above the line (99.5) ⇒ from above
    V, ln, d = _line_case(mirror, monkeypatch, rows, form="engulf", swings=[("L", 99.5, 7, 8)])
    assert _fired(V, d, len(rows)) == []
    V2, _ln, _d = _line_case(mirror, monkeypatch, rows, form="engulf", swings=[("L", 99.5, 7, 8)], s={"e4b_approach_rule": "any"})
    assert [t for t, _ in _fired(V2, d, len(rows))] == [REJECT]


def test_unknown_approach_rule_is_refused(monkeypatch):
    V, ln, d = _line_case(False, monkeypatch, FROM_BELOW, s={"e4b_approach_rule": "maybe"})
    with pytest.raises(ValueError):
        _fired(V, d, len(FROM_BELOW))


@MIRRORS
def test_a_broken_area_retest_from_the_original_side_is_no_e4b(mirror):
    """The same rule for a BROKEN area (support 98–99 broken down ⇒ bear call retest from below): a candle that opened above the
    area's high and closed below it is a breakdown candle."""
    import decision3.method as M
    from decision3 import flip as FL
    rows = [(100.0, 100.5, 99.5, 100.2, 1.0), (100.2, 100.3, 97.0, 97.2, 1.0), (97.2, 97.5, 96.0, 96.2, 1.0), (96.2, 97.0, 96.1, 96.8, 1.0),
            (96.8, 99.8, 96.7, 99.6, 1.0), (99.6, 99.9, 97.2, 97.4, 1.0)]
    lo, hi = 98.0, 99.0
    if mirror:
        rows, (lo, hi) = _mirror_rows(rows), (2 * MID - 99.0, 2 * MID - 98.0)
    snap = {"id": 0, "lo": lo, "hi": hi, "role": "support" if not mirror else "resistance", "tf": "1H", "state": FL.BROKEN,
            "break_dir": UP if mirror else DOWN, "broken_at": 2, "trade_location": True}
    V, _l, _d = _bare(rows, [], band=(98.0, 99.0), mirror=False, snapshot=lambda t: [snap],
                      trend_at=lambda u: "UP" if mirror else "DOWN")
    d = UP if mirror else DOWN
    orig = M.reversal_form
    try:
        M.reversal_form = lambda A, t, dd, s_, tss=None: ("strong_close", 1) if t == 5 else None
        TLc, TLp = TL.channel_lines, TL.channels
        TL.channel_lines, TL.channels = (lambda V, t, degree=None: []), (lambda V, t, degree=None: [])
        fired = [t for t in range(3, len(rows)) for _f in EM.Reader(V).broken(t, d)[1]]
        assert fired == []                                                 # bar 4 closed above the area ⇒ bar 5 came from above
        V.s = {**V.s, "e4b_approach_rule": "any"}
        V.__dict__.pop("_em_memo", None)
        assert [t for t in range(3, len(rows)) for _f in EM.Reader(V).broken(t, d)[1]] == [5]
    finally:
        M.reversal_form = orig
        TL.channel_lines, TL.channels = TLc, TLp


# ------------------------------------------------------------------------------------------------ DECISIONS 40: range edges = areas
def _edge(edge, lo, hi, born=1, same=None, below=False, above=False):
    return {"id": f"range:1H:{edge}:{born}", "tf": "1H", "role": "resistance" if edge == "upper" else "support", "lo": lo, "hi": hi,
            "range_edge": edge, "trade_side": "bear_call" if edge == "upper" else "bull_put", "lifecycle": "tested", "current": True,
            "trade_location": True, "born_bar": born, "same_level": same, "below": below, "above": above, "births": ["range"],
            "state": "TESTED", "sweeps": 0, "fresh": False, "confluence": [], "confluence_label": None, "dist": 0.0}


def test_range_edges_are_armed_on_the_trade_side_only(monkeypatch):
    V, lvl, d = _bare([(100.0, 100.5, 99.5, 100.0, 1.0)] * 4, [])
    up, lo_ = _edge("upper", 104.0, 105.0), _edge("lower", 95.0, 96.0)
    monkeypatch.setattr(RE, "trade_edges", lambda V_, t, tfs=("D", "1H"): [up, lo_])
    R = EM.Reader(V)
    assert [e["id"] for e in R.range_edge_areas(3, "DOWN", [])] == [up["id"]]          # bear call at the upper edge (P4: Daily DOWN)
    assert [e["id"] for e in R.range_edge_areas(3, "UP", [])] == [lo_["id"]]           # bull put at the lower edge
    assert sorted(e["id"] for e in R.range_edge_areas(3, "RANGE", [])) == sorted([up["id"], lo_["id"]])
    assert R.range_edge_areas(3, "DOWN", [])[0]["visit_from"] == 1                     # the visit counts from the range being known
    assert R.range_edge_areas(3, "DOWN", [{"id": 7}]) and R.range_edge_areas(3, "DOWN", [{"id": up["id"]}]) == []
    monkeypatch.setattr(RE, "trade_edges", lambda V_, t, tfs=("D", "1H"): [_edge("upper", 104.0, 105.0, same=7)])
    assert R.range_edge_areas(3, "DOWN", [{"id": 7}]) == []                            # the same band is already that armed area
    monkeypatch.setattr(RE, "trade_edges", lambda V_, t, tfs=("D", "1H"): [_edge("upper", 94.0, 95.0, below=True)])
    assert R.range_edge_areas(3, "DOWN", []) == []                                     # a resistance below price is not ahead
    V.s = {**V.s, "range_edge_areas": "off"}
    monkeypatch.setattr(RE, "trade_edges", lambda V_, t, tfs=("D", "1H"): [up])
    assert EM.Reader(V).range_edge_areas(3, "DOWN", []) == []


@MIRRORS
def test_e1_fires_at_a_range_edge_like_at_any_area(mirror, monkeypatch):
    """The upper edge 100–102 of a 1H range (bear call; mirror: the lower edge, bull put) — price comes up into it from below: E1 at
    the first bar trading into it (refined base off, as the model-mechanics tests), invalidation beyond the edge's far side."""
    rows = [(97.0, 97.5, 96.5, 97.2, 1.0), (97.2, 98.5, 97.0, 98.4, 1.0), (98.4, 99.5, 98.2, 99.3, 1.0), (99.3, 100.8, 99.1, 99.6, 1.0)]
    V, _lvl, d = _bare(rows, [], mirror=mirror)
    e = _edge("lower" if mirror else "upper", *((2 * MID - 102.0, 2 * MID - 100.0) if mirror else (100.0, 102.0)), born=0)
    monkeypatch.setattr(RE, "trade_edges", lambda V_, t, tfs=("D", "1H"): [e])
    R = EM.Reader(V)
    act = R.range_edge_areas(3, "UP" if mirror else "DOWN", [])
    a, fired = R.area(3, act[0], d)
    assert a["area_id"] == e["id"] and [f["model"] for f in fired] == ["E1"]
    assert fired[0]["invalidation"] == pytest.approx(2 * MID - 102.0 if mirror else 102.0)


def test_trade_edges_reads_the_row_range_state_cache(monkeypatch):
    e = _edge("upper", 104.0, 105.0)
    dead = {**_edge("upper", 110.0, 111.0), "trade_location": False}
    V = NS(levels=object())
    V.__dict__["_range_state_cache"] = {5: {"in_range": True}}
    V.__dict__["_range_edges_full"] = {5: {"1H": [e, dead], "15M": [_edge("upper", 101.0, 102.0)], "D": []}}
    assert [x["id"] for x in RE.trade_edges(V, 5)] == [e["id"]]                        # 15M edges are not areas (setup TF)


# ------------------------------------------------------------------------------------------------ DECISIONS 41: card text for a line
LINE_TAGS = {"engine": True, "entry_model": "E4", "entry_name": "Sweep-retest (b)", "entry_label": "E4 — Sweep-retest (b)",
             "entry_object": "broken_line",
             "entry_line": {"tf": "1H", "degree": 2, "family": "rising line of lows", "break_side": "down", "value": 55710.4},
             "gate": {"mode": "engine", "area": [55710.4, 55710.4],
                      "areas": [{"id": "line:D2:L+:1-9", "role": "resistance", "lo": 55710.4, "hi": 55710.4, "tf": "line",
                                 "state": "BROKEN"}]}}


def _row(tags, symbol="BANKNIFTY", direction="BEARISH"):
    return {"signal_id": "s1", "bot": "srv2_momentum_reversal", "bot_label": "NIFTY 15M Dynamic SR", "symbol": symbol,
            "direction": direction, "setup_tf": "15M", "level": 55710.4, "signal_ts": "2030-01-07 10:15:00", "mode": "PAPER",
            "role": "resistance", "setup_json": json.dumps({"tags": tags}), "tags": tags}


def test_the_card_names_a_line_object_as_a_line_with_its_timeframe():
    from vision import card_summary as CS
    from vision import worker as W
    head = W.plain_head(_row(LINE_TAGS))
    assert head.startswith("BANKNIFTY · E4 — Sweep-retest (b)")                         # the signal's own symbol first
    assert "broken 1H line" in head and "55,710" in head and "retest from below" in head
    assert "supply area" not in head and "0 pts" not in head
    where = CS.line_where(_row(LINE_TAGS))
    assert "broken 1H line" in where and "Supply" not in where and "retest from below" in where
    bull = json.loads(json.dumps(LINE_TAGS))
    bull["entry_line"].update(break_side="up", family="falling line of highs")
    assert "retest from above" in W.plain_head(_row(bull, direction="BULLISH"))


def test_the_card_header_shows_the_symbol_first_and_the_bot_as_a_small_label():
    from vision import worker as W
    body = W._body(_row(LINE_TAGS), {"verdict": "agree"}, "PAPER")
    first = body.split("\n")[0]
    assert first.index("BANKNIFTY") < first.index("Price-action engine (PAPER)") and "<i>Price-action engine (PAPER)</i>" in first
    assert "15M Dynamic SR" not in body and "Broken 1H line at 55,710" in body
    lv = {"gate": {"area": [22500.0, 22560.0]}}                           # a level-bot signal: today's header and text, untouched
    b2 = W._body(_row(lv, symbol="NIFTY"), {"verdict": "agree"}, "PAPER")
    assert b2.split("\n")[0] == "👁 <b>Vision V0 — फक्त माहिती</b> · NIFTY 15M Dynamic SR" and "Area 22,500–22,560" in b2
    assert W.plain_head(_row(lv, symbol="NIFTY")).startswith("NIFTY: a bear call (bearish) trade at supply area 22,500–22,560 (60 pts)")


def test_engine_label_by_signal_source(monkeypatch):
    """Addition D: signal_source = engine ⇒ "Price-action engine (PAPER)"; the old bot name only for own (trade messages, /status, the
    Vision row's label)."""
    import engine_signal as ES
    from paper import watch as PW
    assert PW.bot_label("srv2_momentum_reversal", "engine") == ES.ENGINE_LABEL == "Price-action engine (PAPER)"
    assert PW.bot_label("srv2_momentum_reversal", "own") == "15M Dynamic SR" and PW.bot_label("srv2_momentum_reversal") == "15M Dynamic SR"
    from vision import hook as VH
    seen = []
    monkeypatch.setattr(VH.VC, "load", lambda bot, path=None, timeout=None: {"symbols": ["BANKNIFTY", "NIFTY"]})
    monkeypatch.setattr(VH.VC, "effective_mode", lambda s, tm: "notify")
    monkeypatch.setattr(VH.VS, "insert_signal", lambda row, path=None, timeout=None: seen.append(row) or "id")
    for tags in ({"engine": True}, {}):
        VH._submit("srv2_momentum_reversal", "BANKNIFTY", "PAPER", "BEARISH", 1.0, "resistance", "15M", "2030-01-07 10:15", tags=tags)
    assert seen[0]["setup"]["bot_label"] == ES.ENGINE_LABEL and seen[0]["setup"]["bot_own_label"] == "NIFTY 15M Dynamic SR"
    assert seen[1]["setup"] == {"tags": {}, "invalidation": None, "bot_label": "NIFTY 15M Dynamic SR", "last_bar": None}


def test_engine_card_labels_the_line_and_puts_the_symbol_first():
    from vision import engine_audit as EA
    from vision import engine_card as EC
    rd = EA.reading({**_row(LINE_TAGS), "spot": 55700.0})
    assert EC.object_label(rd) == "BROKEN 1H LINE (retest from below)"
    rd2 = {**rd, "line": None, "object": "area", "range_edge": {"edge": "upper", "tf": "1H"}, "area": {**rd["area"], "state": "TESTED"}}
    assert EC.object_label(rd2) == "1H RANGE UPPER EDGE tested"


def test_the_vision_facts_describe_the_line_with_its_timeframe():
    from vision import engine_audit as EA
    sig = {**_row(LINE_TAGS), "spot": 55700.0}
    txt = EA.facts_text(sig)
    assert "broken 1H line" in txt and "retest from below" in txt and "band" not in txt.split("Retested object")[1].split("\n")[0]
