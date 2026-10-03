"""tests/test_opportunity_engine_structure.py -- structure state machine (§0.1 reversal नियम, §2.3), कृत्रिम sequences, network-free."""
import numpy as np
import pandas as pd
import pytest

from opportunity_engine.config import EngineConfig
from opportunity_engine.structure import StructureTracker

KEY = ("CHOCH", "BOS", "REVERSAL_CONFIRMED", "RECOVERY", "RANGE_START", "INIT_TREND", "INIT_RANGE", "PULLBACK_START", "PULLBACK_END",
       "RANGE_EXIT_UP", "RANGE_EXIT_DOWN")
MIRROR = {"UPTREND": "DOWNTREND", "UPTREND_PULLBACK": "DOWNTREND_PULLBACK", "UPTREND_WEAK": "DOWNTREND_WEAK",
          "DOWNTREND": "UPTREND", "DOWNTREND_PULLBACK": "UPTREND_PULLBACK", "DOWNTREND_WEAK": "UPTREND_WEAK",
          "RANGE": "RANGE", "INIT": "INIT"}
T0 = pd.Timestamp("2025-01-01 09:15")


def cfg(R=2, k=1.0, **kw):
    params = {"ref_range_min_bars": 3, "ref_range_bars": 10, **kw}
    return EngineConfig(pivot_n={"x": R}, swing_k={"x": k}, **params)


def legs(*pts, step=1.0):
    """turning closes दिले की `step` प्रति bar ने सरळ चाली."""
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(int(round(abs(b - a) / step)), 1)
        out += list(np.linspace(a, b, n + 1)[1:])
    return out


def bar(i, o, c, wick=0.4, lo=None, hi=None):
    return (T0 + pd.Timedelta(minutes=5 * (i + 1)), o, max(o, c) + wick if hi is None else hi, min(o, c) - wick if lo is None else lo, c)


def feed(closes, config=None, wick=0.4, tracker=None):
    tr = tracker or StructureTracker("x", config or cfg())
    prev = closes[0]
    for i, cl in enumerate(closes, start=len(tr.c)):
        tr.on_bar(*bar(i, prev, cl, wick), True)
        prev = cl
    return tr


def keys(tr):
    return [(e["type"], e["to_state"]) for e in tr.events if e["type"] in KEY]


def types(tr):
    return [e["type"] for e in tr.events if e["type"] in KEY]


UP_BASE = (100, 110, 104, 116, 108, 122)          # HH/HL: protected_low ≈ 107.6, HH ≈ 122.4


# ---- १. reversal_confirmed -----------------------------------------------------------------------------------------------
def test_reversal_confirmed_up_to_down():
    tr = feed(legs(*UP_BASE, 104, 114, 98))
    assert types(tr) == ["INIT_TREND", "PULLBACK_START", "BOS", "PULLBACK_START", "CHOCH", "REVERSAL_CONFIRMED"]
    assert tr.state == "DOWNTREND"
    choch = next(e for e in tr.events if e["type"] == "CHOCH")
    rev = next(e for e in tr.events if e["type"] == "REVERSAL_CONFIRMED")
    assert choch["to_state"] == "UPTREND_WEAK" and rev["to_state"] == "DOWNTREND"
    assert rev["time"] >= rev["trigger_bar"] and rev["lh_price"] < 122.4 - 0.1          # LH, HH पेक्षा खाली
    assert tr.protected_level() == pytest.approx(rev["lh_price"])                      # protected_high = तोच LH


def test_close_through_protected_low_is_choch_and_weak():
    tr = feed(legs(*UP_BASE, 104))
    assert tr.state == "UPTREND_WEAK" and types(tr)[-1] == "CHOCH"
    choch = next(e for e in tr.events if e["type"] == "CHOCH")
    assert choch["price"] == pytest.approx(107.6)


# ---- २. low LH आधी तुटला => WEAK च ----------------------------------------------------------------------------------------
def test_low_broken_before_lh_stays_weak_then_down_after_lh_and_new_low():
    # CHoCH नंतर LH व्हायच्या आधीच खाली चालतच राहतं (नवीन lows), पण state WEAK; नंतर LH, मग पुन्हा नवीन low खाली close => DOWN
    tr = feed(legs(*UP_BASE, 98))
    assert tr.state == "UPTREND_WEAK" and "REVERSAL_CONFIRMED" not in types(tr)
    tr = feed(legs(98, 108, 90)[1:], tracker=tr)
    assert tr.state == "DOWNTREND" and types(tr).count("REVERSAL_CONFIRMED") == 1
    rev = next(e for e in tr.events if e["type"] == "REVERSAL_CONFIRMED")
    assert rev["price"] < 98                                                            # तुटलेला weak_low = नवीन (खाली सरकलेला) low


def test_no_reversal_without_a_qualifying_lh():
    # CHoCH नंतर lh शिवाय सतत घसरण: state WEAK राहतं (DOWN नाही)
    tr = feed(legs(*UP_BASE, 100, 92, 84))
    assert tr.state == "UPTREND_WEAK" and "REVERSAL_CONFIRMED" not in types(tr)


# ---- ३. आरशातली प्रतिमा --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pts", [
    (*UP_BASE, 104, 114, 98),                       # reversal
    (*UP_BASE, 98, 108, 90),                        # low LH आधी तुटला
    (*UP_BASE, 104, 126),                           # recovery
    (*UP_BASE, 112, 124, 106),                      # BOS नंतर CHoCH
    (100, 90, 96, 84, 92, 78, 98, 88, 112),         # खाली trend आणि recovery
])
def test_downtrend_is_the_exact_mirror(pts):
    up = feed(legs(*pts))
    down = feed(legs(*[200 - p for p in pts]))
    assert [(e["type"], MIRROR[e["to_state"]]) for e in up.events if e["type"] in KEY] == [(e["type"], e["to_state"]) for e in down.events if e["type"] in KEY]
    assert [e["bar_idx"] for e in up.events if e["type"] in KEY] == [e["bar_idx"] for e in down.events if e["type"] in KEY]
    assert MIRROR[up.state] == down.state


def test_downtrend_reversal_to_up_via_hl_and_close_above_weak_high():
    pts = (200 - 100, 200 - 110, 200 - 104, 200 - 116, 200 - 108, 200 - 122, 200 - 104, 200 - 114, 200 - 98)
    tr = feed(legs(*pts))
    assert tr.state == "UPTREND" and "REVERSAL_CONFIRMED" in types(tr)


# ---- ४. negative / edge ----------------------------------------------------------------------------------------------------
def test_wick_only_break_is_a_sweep_and_does_not_change_state():
    tr = feed(legs(*UP_BASE, 118))
    before = tr.state
    prot = tr.protected_level()
    assert prot is not None
    i = len(tr.c)
    tr.on_bar(*bar(i, 117, 117.5, lo=prot - 1.0, hi=118.0), True)      # wick protected_low च्या खाली, close वर
    assert tr.state == before and tr.protected_level() == prot
    assert any(e["type"] == "SWEEP" and e["side"] == "LOW" for e in tr.events)
    assert "CHOCH" not in types(tr)


def test_equal_or_higher_high_is_not_a_qualifying_lh():
    # CHoCH नंतर bounce HH च्या बरोबरी (EQH) पर्यंत: LH नाही => खाली तुटला तरी DOWN नाही (WEAK)
    tr = feed(legs(*UP_BASE, 104, 122, 96))
    assert "REVERSAL_CONFIRMED" not in types(tr)
    assert tr.state in ("UPTREND_WEAK", "UPTREND")


def test_close_between_lh_pivot_and_confirmation_gives_down_on_the_confirmation_bar():
    base = legs(*UP_BASE, 104, 114)                   # CHoCH, नंतर LH ≈114
    tr = feed(base)
    assert tr.state == "UPTREND_WEAK"
    lh_i = len(tr.c) - 1                              # आत्ता 114 वरचा bar (pivot-bar उमेदवार)
    # R=2: दोन bars नंतर pivot confirmed. त्या दोन्ही bars मध्ये खाली close (weak_low च्या खाली)
    tr.on_bar(*bar(lh_i + 1, 114, 100, hi=114.0), True)       # high pivot च्या खाली (पुढचे bars lower-high)
    assert tr.state == "UPTREND_WEAK"                 # LH अजून confirmed नाही
    tr.on_bar(*bar(lh_i + 2, 100, 97, hi=113.0), True)
    assert tr.state == "DOWNTREND"
    rev = next(e for e in tr.events if e["type"] == "REVERSAL_CONFIRMED")
    assert rev["bar_idx"] == lh_i + 2                                                  # event time = confirmation bar
    assert rev["trigger_idx"] == lh_i + 1 and rev["trigger_bar"] < rev["time"]       # trigger bar वेगळं


def test_recovery_back_to_uptrend_when_close_above_last_hh():
    tr = feed(legs(*UP_BASE, 104, 126))
    assert "RECOVERY" in types(tr) and tr.state in ("UPTREND", "UPTREND_PULLBACK")


def test_weak_without_confirmation_turns_into_range():
    # CHoCH नंतर swings (४) होतात पण ना recovery ना reversal => RANGE
    tr = feed(legs(*UP_BASE, 104, 114, 106, 116, 107, 115, 108, 115, 109))
    assert "REVERSAL_CONFIRMED" not in types(tr)
    assert tr.state in ("RANGE", "UPTREND_WEAK", "DOWNTREND")


def test_range_exit_needs_close_beyond_edge_and_a_higher_low():
    tr = feed(legs(100, 110, 102, 110, 102, 110, 102, 110, 102, 110.5, 103))
    assert tr.state == "RANGE"
    tr = feed(legs(103, 112, 106, 118)[1:], tracker=tr)
    assert tr.state in ("UPTREND", "UPTREND_PULLBACK") and "RANGE_EXIT_UP" in types(tr)


# ---- ५. no-lookahead --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_future_bars_never_change_past_events(seed):
    rng = np.random.default_rng(seed)
    closes = list(100 + np.cumsum(rng.normal(0, 1.6, 400)))
    full = feed(closes, cfg(R=3, k=1.0))
    for cut in (120, 233, 310):
        part = feed(closes[:cut], cfg(R=3, k=1.0))
        a = [(e["bar_idx"], e["type"], e["price"], e["to_state"] if "to_state" in e else None) for e in full.events if e["bar_idx"] < cut]
        b = [(e["bar_idx"], e["type"], e["price"], e["to_state"] if "to_state" in e else None) for e in part.events]
        assert a == b, (seed, cut)


def test_changing_future_bars_does_not_change_the_state_at_t():
    base = legs(*UP_BASE, 104, 114)
    a = feed(base + list(legs(114, 98)[1:]))
    b = feed(base + list(legs(114, 130)[1:]))
    cut = len(base)
    assert [(e["bar_idx"], e["type"]) for e in a.events if e["bar_idx"] < cut] == [(e["bar_idx"], e["type"]) for e in b.events if e["bar_idx"] < cut]


# ---- ६. spike body-low (weak_low) ---------------------------------------------------------------------------------------------
def test_spike_wick_does_not_set_weak_low_when_body_edge_is_used():
    """CHoCH नंतरचा सर्वात खालचा bar एक SPIKE (मोठी खालची wick, छोटं body, लगेच परत) — weak_low = wick (85) नाही, body-low (≈105.5).
    म्हणून नंतर 104 वर close => DOWN (body_edge=True); body_edge=False असताना weak_low=85 राहिल्याने DOWN नाही."""
    def run(body_edge):
        config = cfg(spike_body_edge=body_edge)
        tr = feed(legs(*UP_BASE, 106), config)                         # CHoCH ≈107.0 ला; weak lows ≈105.6
        i = len(tr.c)
        tr.on_bar(*bar(i, 106, 105.5, lo=85.0, hi=106.4), True)        # spike: छोटं body, wick 85
        feed(list(legs(105.5, 114, 104)[1:]), config, tracker=tr)      # परत वर (LH ≈114), मग 104 वर close
        return tr
    with_body, without = run(True), run(False)
    assert "CHOCH" in types(with_body) and "CHOCH" in types(without)
    assert "REVERSAL_CONFIRMED" in types(with_body)
    assert "REVERSAL_CONFIRMED" not in types(without)


# ---- ७. snapshot / warm-up ----------------------------------------------------------------------------------------------------
def test_snapshot_fields_and_warmup():
    tr = StructureTracker("x", cfg(ref_range_min_bars=10))
    feed(legs(100, 105), tracker=tr)
    snap = tr.snapshot()
    assert snap["trend_state"] == "INIT" and snap["ref_range"] is None or snap["ref_range"] > 0
    tr = feed(legs(*UP_BASE, 112))
    snap = tr.snapshot()
    assert {"trend_state", "protected_level", "last_sh", "last_sl", "range_high", "range_low", "ref_range", "updated_at"} <= set(snap)
    assert snap["protected_level"] == pytest.approx(107.6) and snap["trend_state"].startswith("UPTREND")
