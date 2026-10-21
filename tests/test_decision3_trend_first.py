"""Trend first (Abhi: TRADE_SESSION_DECISIONS_SENSEX_SETUPS_CD14 §2; audit docs/reports/setups_prA_v1_audit.md) — the Daily trend gate
never allows a trade against the Daily structure. Defect: a same-degree counter-move climbed for months in higher highs + higher lows
below the far protected origin; the label stayed DOWN (Q15: no close beyond the origin) and V22 allowed a bear call.

Fix (root cause, no thresholds): the engine's own flip shape (Q29 (अ): HL after the impulse end + Daily close beyond the swing high
before it, with an impulse-nature leg — Q36) is now also read BEFORE the origin is closed beyond, while the counter-move is a
same-degree correction (`DState.rev`). It blocks the trend side (no bear call / no bull put); trend, phase and protected do not change.
Every case in both directions."""
import numpy as np
import pytest

from bots_common import level_reaction as LR
from decision3 import daily as DD
from decision3 import daily_swings as DS
from tests import elliott_fixtures as F
from tests.test_decision3_daily_q15 import _V_with

MIRRORS = [pytest.param(False, id="down"), pytest.param(True, id="up")]


def _px(v, mirror, wick=0.0):
    return (F.MIRROR - v - wick) if mirror else (v + wick)


def _eb(d, mirror):
    ext = d["high"].to_numpy() if mirror else d["low"].to_numpy()
    return int(np.argmin(np.abs(ext - _px(F.E, mirror, -F.WICK))))


def _step1(st, i):
    V = _V_with(st[:i + 1], [DD.DState(0, st[0].day, st[0].known_at, "UNKNOWN")])
    return V.step1(0)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_staircase_counter_move_below_origin_blocks_the_trend_side(mirror):
    """The misread, reproduced: trend label DOWN, protected origin never closed beyond, phase = same-degree correction candidate —
    before the fix ① said "Daily DOWN ⇒ bear call". After: the structure since the impulse end is UP ⇒ trade नाही."""
    d, info = F.staircase_below_origin(mirror)
    st = DD.fold(d)
    old, opp = ("UP", "DOWN") if mirror else ("DOWN", "UP")
    eb = _eb(d, mirror)
    C = d["close"].to_numpy()
    org = _px(info["origin4"], mirror, F.WICK)
    assert all(x.trend == old for x in st[eb:])                            # Q15: label unchanged
    assert not ((C[eb:] < org) if mirror else (C[eb:] > org)).any()        # origin never closed beyond
    last = st[-1]
    assert last.phase == "correction" and last.counter == "candidate" and abs(last.protected.price - org) < 1e-9
    assert last.rev is not None
    h, lm = last.rev
    assert h.kind == ("H" if mirror else "L") and lm.kind == ("L" if mirror else "H")
    assert ((h.price < _px(F.E, mirror, -F.WICK)) if mirror else (h.price > _px(F.E, mirror, -F.WICK)))   # HL above the low
    assert ((C[-1] < lm.price) if mirror else (C[-1] > lm.price))                                          # close beyond the high
    ok, why, _, ctx = _step1(st, len(st) - 1)
    assert not ok and ctx["trend"] == "NEUTRAL" and DD.trade_side(ctx["trend"]) == ()
    assert "trend first" in why and f"रचना {opp}" in why
    assert any(("bull put" if mirror else "bear call") in x for x in ctx["notes"])


@pytest.mark.parametrize("mirror", MIRRORS)
def test_close_back_under_the_swing_with_the_hl_intact_keeps_the_gate_on(mirror):
    """PR #305 review 🔴: the structure turned (HL + a close beyond the swing before it); today's close dips back under that swing but
    the HL is intact ⇒ still blocked (any close since the HL counts, bars <= today only). Level bots: no side either."""
    d, _ = F.staircase_dip_back(mirror)
    st = DD.fold(d)
    old = "UP" if mirror else "DOWN"
    C, Lw, Hw = (d[k].to_numpy() for k in ("close", "low", "high"))
    last = st[-1]
    assert last.trend == old and last.phase == "correction" and last.rev is not None
    h, lm = last.rev
    assert ((C[-1] > lm.price) if mirror else (C[-1] < lm.price))          # today's close back under the swing
    assert ((Hw[h.bar:].max() <= h.price) if mirror else (Lw[h.bar:].min() >= h.price))   # HL (LH) intact
    seg = C[h.bar + 1:]
    assert ((seg < lm.price) if mirror else (seg > lm.price)).any()        # a close beyond it happened after the HL
    ok, why, _, ctx = _step1(st, len(st) - 1)
    assert not ok and ctx["trend"] == "NEUTRAL" and "trend first" in why
    c = LR.context_from_state(last)
    assert not c["ok"] and c["sides"] == set()


@pytest.mark.usefixtures("elliott_leg_read")   # Abhi 21 Oct: Elliott what-if path (daily_leg_read = compare default)
@pytest.mark.parametrize("mirror", MIRRORS)
def test_new_extreme_undoes_the_counter_structure_and_the_trend_side_returns(mirror):
    """Same staircase, then the DOWN continuation to a new low: once price closes beyond the impulse end the counter structure is gone
    and bear calls are allowed again — trend DOWN throughout (no flip, no special case)."""
    d, _ = F.staircase_below_origin(mirror, breakdown=True)
    st = DD.fold(d)
    old = "UP" if mirror else "DOWN"
    eb = _eb(d, mirror)
    assert all(x.trend == old for x in st[eb:])
    assert any(x.rev is not None for x in st[eb:])
    C = d["close"].to_numpy()
    low = _px(F.E, mirror, -F.WICK)
    top = int(np.argmax(d["high"].to_numpy()[eb:]) if not mirror else np.argmin(d["low"].to_numpy()[eb:])) + eb
    nb = next(i for i in range(top, len(d)) if ((C[i] > low) if mirror else (C[i] < low)))
    assert all(x.rev is None for x in st[nb:])
    ok, _, _, ctx = _step1(st, len(st) - 1)
    assert ok and ctx["trend"] == old


@pytest.mark.usefixtures("elliott_leg_read")   # Abhi 21 Oct: Elliott what-if path (daily_leg_read = compare default)
@pytest.mark.parametrize("mirror", MIRRORS)
def test_truncated_zigzag_c_top_keeps_the_trend_side(mirror):
    """Negative control: a zigzag whose c stays below a (no higher high) never turns the structure — the c-top bear call stays."""
    d, info = F.correction_fixture("zigzag_c_truncated", mirror)
    st = DD.fold(d)
    old = "UP" if mirror else "DOWN"
    eb = _eb(d, mirror)
    ext = d["low"].to_numpy() if mirror else d["high"].to_numpy()
    c_end = _px(info["end"], mirror, F.WICK)
    cb = eb + int(np.argmin(np.abs(ext[eb:] - c_end)))
    assert st[cb].trend == old and st[cb].phase == "correction" and st[cb].rev is None
    ok, _, _, ctx = _step1(st, cb)
    assert ok and ctx["trend"] == old


def _fixtures(mirror):
    yield F.staircase_below_origin(mirror)[0]
    yield F.staircase_below_origin(mirror, breakdown=True)[0]
    yield F.staircase_dip_back(mirror)[0]
    for name in ("zigzag_c_truncated", "zigzag_c_extended", "flat_regular", "triangle_contracting", "very_deep_holds_origin"):
        yield F.correction_fixture(name, mirror)[0]
    yield F.acceptance_banknifty(mirror)[0]


@pytest.mark.parametrize("mirror", MIRRORS)
def test_structure_against_only_in_same_degree_counter_moves_and_never_changes_the_trend(mirror):
    """`rev` is read only while the counter-move is a same-degree correction (phase correction / origin_broken — a lower-degree pullback
    inside the impulse is not the trend-degree structure), only with a trend, and is causal (same value from the prefix)."""
    for d in _fixtures(mirror):
        st = DD.fold(d)
        assert all(x.rev is None or (x.trend in ("UP", "DOWN") and x.phase in ("correction", "origin_broken")) for x in st)
        on = [i for i, x in enumerate(st) if x.rev is not None]
        for i in on[:1] + on[-1:]:
            pre = DD.fold(d.iloc[:i + 1])[-1]
            assert pre.rev is not None and pre.rev[0].price == st[i].rev[0].price and pre.rev[1].price == st[i].rev[1].price
            assert i == 0 or DD.fold(d.iloc[:i])[-1].trend == st[i - 1].trend


@pytest.mark.parametrize("mirror", MIRRORS)
def test_level_bots_and_daily_caption_use_the_same_gate(mirror):
    d, _ = F.staircase_below_origin(mirror)
    st = DD.fold(d)
    c = LR.context_from_state(st[-1])
    assert not c["ok"] and c["sides"] == set() and c["structure_against"]
    v = DS.build(d, window=len(d), with_elliott=False)
    line = DS.trend_line(v["q15"])
    assert f"structure turned {'DOWN' if mirror else 'UP'}" in line and ("no bull put" if mirror else "no bear call") in line
    assert "trend-बाजूचे entries नाहीत" in DD.describe(st[-1])
