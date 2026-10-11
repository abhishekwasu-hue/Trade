"""reader2 CR2 — structure vote (read_counter / patterns2 wrapper) and fusion of the two votes (spec §2a / §2c)."""
import pytest

from decision3 import daily_legs as DL
from reader2 import fusion as RF
from reader2 import settings as RS
from reader2 import structure as RSt
from reader2 import trend as RT
from reader2.frame import Chart
from reader2.legs import Leg
from tests import reader2_fixtures as F

S = RS.load()


def _mir(px, mirror):
    return [1000.0 - p for p in px] if mirror else list(px)


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
@pytest.mark.parametrize("px,family,cls", [
    ([0, 30, 18, 75, 60, 100], "impulse", "impulse"),
    ([100, 60, 80, 30], "zigzag", "correction"),
    ([100, 60, 98, 50], "flat", "correction"),
    ([0, 10], "single", "none"),
])
def test_structure_vote_wraps_read_counter(px, family, cls, mirror):
    p = _mir(px, mirror)
    v = RSt.vote_prices(p, S)
    assert v["family"] == family == (DL.read_counter(p)["family"] if len(p) > 2 else "single")
    assert v["cls"] == cls


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
def test_unnamed_three_wave_is_a_weak_correction(mirror):
    v = RSt.vote_prices(_mir([0, 30, 10, 40, 20, 50], mirror), S)          # overlapping 5 swings: no impulse, no named pattern
    assert v["family"] == "3-wave"
    assert v["vote"] == S["three_wave_vote"] and v["cls"] == "correction"


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
def test_diagonal_counts_as_motive(mirror):
    assert RSt.vote_prices(_mir([0, 30, 18, 75, 25, 100], mirror), S)["cls"] == "impulse"


def _sv(cls, fam="x"):
    return {"cls": cls, "family": fam, "n": 5 if cls == "impulse" else 3, "vote": {"impulse": 1, "correction": -1}.get(cls, 0)}


def _av(cls, score):
    return {"cls": cls, "score": score}


@pytest.mark.parametrize("sv,av,label,conf", [
    (_sv("impulse"), _av("impulsive", 0.6), "impulse", "high"),
    (_sv("correction"), _av("corrective", -0.6), "correction", "high"),
    (_sv("impulse"), _av("neutral", 0.1), "impulse", "medium"),
    (_sv("none"), _av("corrective", -0.5), "correction", "medium"),
    (_sv("none"), _av("NA", None), "uncertain", None),
    (_sv("none"), _av("neutral", 0.0), "uncertain", None),
])
def test_fuse_table(sv, av, label, conf):
    lab, c, why = RF.fuse(sv, av)
    assert (lab, c) == (label, conf) and why


def test_fuse_conflict_needs_reread():
    lab, conf, why = RF.fuse(_sv("correction", "zigzag"), _av("impulsive", 0.5))
    assert lab is None and "zigzag" in why and "impulsive" in why


def _leg(ch, dirn, i0, i1, label, s_cls="impulse", a_cls="impulsive"):
    A = ch.A
    p0 = A["l"][i0] if dirn > 0 else A["h"][i0]
    p1 = A["h"][i1] if dirn > 0 else A["l"][i1]
    lg = Leg(2, dirn, i0, i1, float(p0), float(p1), i1 + 1, ch.kat[i1 + 1])
    lg.structure = {"cls": s_cls, "family": "impulse" if s_cls == "impulse" else "zigzag", "n": 5}
    lg.anatomy = {"cls": a_cls, "score": 0.6 if a_cls == "impulsive" else -0.6}
    lg.label = label
    return lg


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
@pytest.mark.parametrize("label,s_cls,a_cls,flips", [
    ("impulse", "impulse", "impulsive", True),
    ("uncertain", "impulse", "impulsive", False),          # uncertain never flips the trend
    ("correction", "correction", "corrective", False),
    ("impulse", "correction", "impulsive", False),          # needs impulse structure too
    ("impulse", "impulse", "corrective", False),            # and impulsive anatomy
])
def test_only_an_impulse_counter_move_flips(label, s_cls, a_cls, flips, mirror):
    df, marks = F.deep_sideways(mirror)
    ch = Chart(df)
    d = -1 if mirror else 1
    first = _leg(ch, d, marks[0], marks[5] + 1, "impulse")
    end = len(ch) - 30                                       # the counter-move ends beyond the first leg's start
    second = _leg(ch, -d, marks[5] + 1, end, label, s_cls, a_cls)
    assert (second.p1 - first.p0) * -d > 0, "precondition: the counter-move breaks the prior swing"
    states, events = RT.derive(ch, [first, second])
    flipped = any(e["to"] == ("UP" if -d > 0 else "DOWN") for e in events)
    assert flipped == flips, events
    if not flips:
        assert states[-1]["trend"] in ("uncertain", "UP" if d > 0 else "DOWN")
