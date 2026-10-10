"""एक setup = एक entry (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §8.3): DUP_SETUP, invalidation तुटल्यावर / नवा correction ⇒ पुन्हा संधी."""
from chart_reader import setups as SU


def res(asof, entry=True, a_ts="2026-03-10 10:00", imp=("2026-03-09 10:00", "2026-03-09 14:00"), inv=105.0, side=-1):
    return {"asof": f"2026-03-10 {asof}", "entry": entry, "side": side, "why_no_entry": [] if entry else ["grade C (30)"],
            "risk": {"invalidation": inv},
            "market_state": {"impulse": {"from_ts": imp[0], "to_ts": imp[1]},
                             "correction": {"labels": [{"label": "A", "to_ts": a_ts}, {"label": "B", "to_ts": "2026-03-10 11:00"}]}}}


def test_first_valid_entry_only_then_dup_setup():
    tr = SU.SetupTracker()
    assert tr.apply(res("12:15"))["entry"]
    r = tr.apply(res("12:30"))
    assert not r["entry"] and any(w.startswith("DUP_SETUP") for w in r["why_no_entry"])
    assert not tr.apply(res("12:45", entry=False))["entry"]                               # नकार तसाच


def test_invalidation_break_frees_the_setup():
    tr = SU.SetupTracker()
    tr.apply(res("12:15"))
    tr.on_bar(high=104.0, low=100.0)
    assert not tr.apply(res("12:30"))["entry"]
    tr.on_bar(high=105.5, low=101.0)                                                       # bear invalidation 105 तुटली
    assert tr.apply(res("13:00"))["entry"]


def test_new_correction_or_impulse_is_a_new_setup():
    tr = SU.SetupTracker()
    tr.apply(res("12:15"))
    assert tr.apply(res("14:00", a_ts="2026-03-10 13:15"))["entry"]                       # नवा A ⇒ नवा correction
    assert tr.apply(res("14:15", imp=("2026-03-10 09:15", "2026-03-10 11:30")))["entry"]
