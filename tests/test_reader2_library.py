"""reader2 on the existing Elliott correction-fixture library (tests/elliott_fixtures.py, both directions) — honest pass / fail.

The library's candles are uniform (no anatomy design), so this measures reader2's degree / structure reading, not its candle reading.
Checks per fixture: (1) the trend never flips against the prior impulse during the correction; (2) no trend-degree leg inside the
correction is a trend-capable impulse; (3) the impulse direction is read by the end of the fixture. Known failures are strict xfail
(a fix XPASSes and fails until the entry is removed) — see OPEN_QUESTIONS CR-Q2. Nothing here is tuned.
"""
import numpy as np
import pytest

from reader2 import reader as RR
from reader2 import trend as RT
from tests import elliott_fixtures as EF

DIRS = (("down", False), ("up", True))
_DEG = ("CR-Q2: at dc_k = 8 MR the degree-2 pivots do not separate this correction's first leg from the impulse (flat A / triangle "
        "swings < 8 MR), so the trend-degree impulse is never confirmed — degree calibration on the dev gallery, not tuned here")
_FLAT_C = ("CR-Q2: same degree cause — flat A + B merge into the prior degree-2 leg, so the C wave (a real 5-wave motive with "
           "impulsive candles) is read alone as a trend-capable impulse; needs the degree calibration, not a rule change")
KNOWN_FAIL = {(nm, "trend", dn): _DEG for nm in ("flat_expanded", "flat_running", "triangle_contracting", "triangle_barrier")
              for dn in ("down", "up")}
KNOWN_FAIL.update({("flat_expanded", "impulse", dn): _FLAT_C for dn in ("down", "up")})


def _params(check):
    out = []
    for nm in EF.CORRECTIONS:
        for dn, mir in DIRS:
            why = KNOWN_FAIL.get((nm, check, dn))
            out.append(pytest.param(nm, mir, id=f"{nm}-{dn}", marks=[pytest.mark.xfail(strict=True, reason=why)] if why else []))
    return out


_CACHE = {}


def _read(name, mirror):
    if (name, mirror) not in _CACHE:
        d, info = EF.correction_fixture(name, mirror)
        L, H = d["low"].to_numpy(), d["high"].to_numpy()
        ev = (EF.MIRROR - EF.E + EF.WICK) if mirror else (EF.E - EF.WICK)
        eb = int(np.argmin(np.abs((H if mirror else L) - ev)))
        tv = (EF.MIRROR - info["end"] - EF.WICK) if mirror else (info["end"] + EF.WICK)
        tb = eb + int(np.argmin(np.abs((L[eb:] if mirror else H[eb:]) - tv)))
        _CACHE[(name, mirror)] = (RR.read(d), eb, tb)
    return _CACHE[(name, mirror)]


@pytest.mark.parametrize("name,mirror", _params("flip"))
def test_library_no_flip_during_the_correction(name, mirror):
    R, eb, tb = _read(name, mirror)
    opp = "DOWN" if mirror else "UP"
    assert opp not in [s["trend"] for s in R.states[eb:tb + 1]]


@pytest.mark.parametrize("name,mirror", _params("impulse"))
def test_library_correction_is_never_a_trend_capable_impulse(name, mirror):
    R, eb, tb = _read(name, mirror)
    cdir = -1 if mirror else 1
    legs = [lg for lg in R.legs[R.trend_degree] if lg.dirn == cdir and lg.i0 >= eb - 3 and lg.i1 <= tb + 3]
    assert not [lg.name() for lg in legs if RT.trend_capable(lg)[0]]


@pytest.mark.parametrize("name,mirror", _params("trend"))
def test_library_impulse_direction_is_read(name, mirror):
    R, _, _ = _read(name, mirror)
    assert R.trend_now()["trend"] == ("UP" if mirror else "DOWN")
