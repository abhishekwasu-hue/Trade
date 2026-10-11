"""Elliott correction fixture library + acceptance set (Abhi: TRADE_SESSION_CORRECTION_FIXTURES / BANKNIFTY_ABC_FIX).

Every Daily structure rule must pass this library (both directions) before merge. Known engine failures are listed in KNOWN_FAIL
(strict xfail — when the engine is fixed the test XPASSes and fails, so the entry must be removed). Shapes / rules: docs/research/
elliott_rules.md (Frost & Prechter). Ratios in fixtures are typical shapes only, never engine thresholds.
"""
import numpy as np
import pytest

from tests import elliott_fixtures as F
from decision3 import daily as DD
from decision3 import daily_swings as DS

DIRS = (("down", False), ("up", True))

# (fixture, check, direction) ⇒ reason. Library first (Abhi's order): the library PR lists the engine's failures here; the engine fix
# empties it. Strict — a fixed case XPASSes and fails until its entry is removed.
KNOWN_FAIL = {}
_WHY = {"trend": "engine flips / leaves the trend during the correction (b new extreme, c beyond a, 5-wave a) — ABC_FIX rule 1",
        "origin": "protected never moves to the correction end (triangle e, truncated / running c, provisional completion)",
        "family": "correction not boxed with its family (no box, b-new-extreme box, or family misread)",
        "control": "impulse with an ending-diagonal wave 5 is not read as a 5-wave counter impulse (no flip)"}
_FAILING = {
    "trend": {
        "double_three": ('down', 'up'),
        "double_zigzag": ('down', 'up'),
        "flat_expanded": ('down', 'up'),
        "flat_running": ('down', 'up'),
        "long_in_time": ('down', 'up'),
        "triangle_expanding": ('down', 'up'),
        "very_deep_holds_origin": ('down', 'up'),
        "zigzag_b_triangle": ('down', 'up'),
        "zigzag_c_eq_a": ('down', 'up'),
        "zigzag_c_extended": ('down', 'up'),
    },
    "origin": {
        "double_three": ('down', 'up'),
        "double_zigzag": ('down', 'up'),
        "flat_expanded": ('down', 'up'),
        "flat_running": ('down', 'up'),
        "long_in_time": ('down', 'up'),
        "triangle_expanding": ('down', 'up'),
        "very_deep_holds_origin": ('down', 'up'),
        "zigzag_b_triangle": ('down', 'up'),
        "zigzag_c_eq_a": ('down', 'up'),
        "zigzag_c_extended": ('down', 'up'),
    },
    "family": {
        "b_looks_impulsive": ('down', 'up'),
        "double_three": ('down', 'up'),
        "double_zigzag": ('down', 'up'),
        "flat_expanded": ('down', 'up'),
        "flat_running": ('down', 'up'),
        "long_in_time": ('down', 'up'),
        "triangle_barrier": ('down', 'up'),
        "triangle_contracting": ('down', 'up'),
        "triangle_expanding": ('down', 'up'),
        "triple_three": ('down', 'up'),
        "very_deep_holds_origin": ('down', 'up'),
        "zigzag_b_triangle": ('down', 'up'),
        "zigzag_c_eq_a": ('down', 'up'),
        "zigzag_c_extended": ('down', 'up'),
        "zigzag_c_truncated": ('down', 'up'),
    },
    "control": {
        "ending_diagonal": ('down', 'up'),
    },
}
for _ck, _by in _FAILING.items():
    for _nm, _dns in _by.items():
        for _dn in _dns:
            KNOWN_FAIL[(_nm, _ck, _dn)] = _WHY[_ck]


def _mark(name, check, dn):
    why = KNOWN_FAIL.get((name, check, dn))
    return [pytest.mark.xfail(strict=True, reason=why)] if why else []


def _params(check):
    return [pytest.param(nm, mir, id=f"{nm}-{dn}", marks=_mark(nm, check, dn)) for nm in F.CORRECTIONS for dn, mir in DIRS]


def _bars(d, info, mirror):
    """impulse-end bar and correction-end bar (its last waypoint: triangle e, truncated / running c) of a correction fixture."""
    L, H = d["low"].to_numpy(), d["high"].to_numpy()
    ev = (F.MIRROR - F.E + F.WICK) if mirror else (F.E - F.WICK)
    eb = int(np.argmin(np.abs((H if mirror else L) - ev)))
    tv = (F.MIRROR - info["end"] - F.WICK) if mirror else (info["end"] + F.WICK)
    tb = eb + int(np.argmin(np.abs((L[eb:] if mirror else H[eb:]) - tv)))
    return eb, tb


@pytest.mark.parametrize("name,mirror", _params("trend"))
def test_trend_stays_with_prior_impulse_through_the_correction(name, mirror):
    d, info = F.correction_fixture(name, mirror)
    st = DD.fold(d)
    eb, _ = _bars(d, info, mirror)
    want = "UP" if mirror else "DOWN"
    assert st[eb].trend == want, "precondition: trend at the impulse end"
    bad = [i - eb for i in range(eb, len(st)) if st[i].trend != want]
    assert not bad, f"{name}: trend left {want} {len(bad)} bars, first {bad[0]} bars after the impulse end"


@pytest.mark.parametrize("name,mirror", _params("origin"))
def test_origin_moves_to_the_correction_end_after_continuation(name, mirror):
    """Q45 / ABC_FIX rule 4: once the continuation confirms, protected = the correction's END (not its extreme, not a swing inside
    it); the trend-direction move is running (not origin_broken)."""
    d, info = F.correction_fixture(name, mirror)
    st = DD.fold(d)
    _, tb = _bars(d, info, mirror)
    px = float(d["low"].iloc[tb] if mirror else d["high"].iloc[tb])
    hit = [j for j in range(tb, len(st)) if st[j].protected is not None and st[j].protected.bar == tb]
    assert hit, f"{name}: protected never moved to the correction end {px:,.1f}"
    assert st[hit[0]].protected.price == px and st[hit[0]].phase != "origin_broken"


@pytest.mark.parametrize("name,mirror", _params("family"))
def test_correction_is_boxed_with_its_family(name, mirror):
    d, info = F.correction_fixture(name, mirror)
    st = DD.fold(d)
    _, tb = _bars(d, info, mirror)
    shapes = [c["shape"] for c in DS.structure_objects(d, st)["corrections"] if c["end_bar"] == tb]
    assert shapes, "correction not boxed"
    assert shapes[0] == info["family"], f"{name}: labelled {shapes[0]!r}, expected {info['family']!r}"


@pytest.mark.parametrize("name,mirror", [pytest.param(nm, mir, id=f"{nm}-{dn}", marks=_mark(nm, "control", dn))
                                         for nm in F.IMPULSES for dn, mir in DIRS])
def test_negative_control_counter_impulse_flips_the_trend(name, mirror):
    """A real 5-wave impulse against the trend (incl. extended 3rd / 5th, leading / ending diagonal) MUST flip it."""
    d, info = F.impulse_control(name, mirror)
    st = DD.fold(d)
    want = "DOWN" if mirror else "UP"
    assert st[-1].trend == want, f"{name}: still {st[-1].trend} after a 5-wave counter impulse"
    if not info["beyond_origin"]:                                          # flip from the 5-wave rule, never a close beyond the origin
        org = (F.MIRROR - F.E - F.I) if mirror else (F.E + F.I)
        ext = d["high"].to_numpy() if mirror else d["low"].to_numpy()
        eb = int(np.argmin(np.abs(ext - ((F.MIRROR - F.E + F.WICK) if mirror else (F.E - F.WICK)))))   # impulse end
        C = d["close"].to_numpy()[eb:]
        assert not ((C < org) if mirror else (C > org)).any()


def test_acceptance_nifty_wave4_correction_then_wave5():
    """Abhi's NIFTY count: (4) rally breaks the minor origin, not the C start ⇒ DOWN throughout; (5) origin = (4) top."""
    d, info = F.acceptance_nifty()
    st = DD.fold(d)
    start = next(i for i, x in enumerate(st) if x.trend == "DOWN")
    low3 = 60 + int(np.argmin(d["low"].to_numpy()[60:110]))                # (3) low before the (4) rally
    assert start < low3, "DOWN before the (4) rally"
    assert all(x.trend == "DOWN" for x in st[start:])
    assert st[-1].protected.price == info["top4"] + F.WICK


_BN = "ABC_FIX: 3-wave counter-move (c beyond a) flips the trend; sharp-fall band / a-b-c box not implemented"


@pytest.mark.parametrize("mirror", [pytest.param(False, id="down", marks=pytest.mark.xfail(strict=True, reason=_BN)),
                                    pytest.param(True, id="up", marks=pytest.mark.xfail(strict=True, reason=_BN))])
def test_acceptance_banknifty_abc_ends_at_sharp_fall_supply(mirror):
    """Abhi's BANKNIFTY count: sharp fall → a-b-c (c beyond a) ending inside the sharp-fall zone → new decline. Engine stays DOWN
    through the a-b-c; origin = c top after the decline confirms; the a-b-c is boxed as a zigzag; sharp-fall band drawn."""
    d, info = F.acceptance_banknifty(mirror)
    st = DD.fold(d)
    want = "UP" if mirror else "DOWN"
    L, H = d["low"].to_numpy(), d["high"].to_numpy()
    low_v = (F.MIRROR - 1080.0 + F.WICK) if mirror else (1080.0 - F.WICK)
    lb = int(np.argmin(np.abs((H if mirror else L) - low_v)))                # sharp-fall impulse end
    assert st[lb].trend == want and all(x.trend == want for x in st[lb:])
    c_v = (F.MIRROR - info["c"] - F.WICK) if mirror else (info["c"] + F.WICK)
    cb = int(np.argmin(np.abs((L if mirror else H) - c_v)))
    assert st[-1].protected.bar == cb
    v = DS.build(d, window=len(d), with_elliott=False)
    assert any(c["end_bar"] == cb and c["shape"] == "zigzag" for c in v["q15"]["objects"]["corrections"])
    assert any("sharp-fall" in b["label"] or "sharp-rise" in b["label"] for b in v["q15"]["levels"])


def test_library_covers_every_requested_shape():
    """Abhi's list: zigzags (c = a, extended, truncated, double), flats (regular, expanded, running), triangles (contracting,
    expanding, barrier, as b of a zigzag), combinations (double / triple three), edge cases; negative controls."""
    need = {"zigzag_c_eq_a", "zigzag_c_extended", "zigzag_c_truncated", "double_zigzag", "flat_regular", "flat_expanded",
            "flat_running", "triangle_contracting", "triangle_expanding", "triangle_barrier", "zigzag_b_triangle", "double_three",
            "triple_three", "b_looks_impulsive", "long_in_time", "very_deep_holds_origin"}
    assert need <= set(F.CORRECTIONS)
    assert {"impulse_extended_third", "impulse_extended_fifth", "leading_diagonal", "ending_diagonal"} <= set(F.IMPULSES)
    d, _ = F.correction_fixture("flat_expanded")
    assert d["low"].min() < F.E - F.WICK                                   # expanded flat: b makes a new low below the impulse end
