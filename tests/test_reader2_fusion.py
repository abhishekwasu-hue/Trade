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
def test_unparsed_count_is_never_a_decisive_correction(mirror):
    """read_counter "3-wave" (no named pattern — also unparsed 5- / 9-wave counts) is weak: |vote| < s_decisive ⇒ silent."""
    for px in ([0, 30, 10, 40, 20, 50], [0, 50, 45, 52, 40, 60, 50, 70, 30, 80]):
        v = RSt.vote_prices(_mir(px, mirror), S)
        if v["family"] == "3-wave":
            assert abs(v["vote"]) < S["s_decisive"] and v["cls"] == "none"
    assert RSt.vote_prices(_mir([0, 30, 10, 40, 20, 50], mirror), S)["family"] == "3-wave"


def test_settings_three_wave_vote_below_decisive():
    assert abs(RS.DEFAULTS["three_wave_vote"]) < RS.DEFAULTS["s_decisive"]


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
    (_sv("none"), _av("NA", None), "uncertain", None),
    (_sv("none"), _av("neutral", 0.0), "uncertain", None),
])
def test_fuse_first_reading(sv, av, label, conf):
    lab, c, why = RF.fuse(sv, av)
    assert (lab, c) == (label, conf) and why


@pytest.mark.parametrize("sv,av", [
    (_sv("correction", "zigzag"), _av("impulsive", 0.5)),          # conflict
    (_sv("impulse"), _av("neutral", 0.1)),                          # one vote silent: never labelled straight away
    (_sv("none"), _av("corrective", -0.5)),
])
def test_fuse_needs_a_reread(sv, av):
    assert RF.fuse(sv, av)[0] is None


def _leg0(ch, sv, av):
    """A degree-0 leg (no lower degree ⇒ no alternative pivots): decide() shows the after-re-read rule directly."""
    lg = Leg(0, 1, 40, 60, 1.0, 2.0, 61, ch.kat[61])
    lg.structure, lg.anatomy = sv, av
    return lg


@pytest.mark.parametrize("sv,av,label,conf", [
    (_sv("impulse"), _av("neutral", 0.1), "uncertain", None),      # structure-only impulse is challenged
    (_sv("impulse"), _av("NA", None), "uncertain", None),
    (_sv("correction", "zigzag"), _av("neutral", -0.1), "correction", "low"),
    (_sv("none"), _av("impulsive", 0.5), "impulse", "low"),        # candles only (lowest degree): low, never trend-capable
    (_sv("correction", "zigzag"), _av("impulsive", 0.5), "uncertain", None),
])
def test_decide_after_reread(sv, av, label, conf):
    df, _ = F.clean_impulse()
    ch = Chart(df)
    lab, c, why = RF.decide(ch, _leg0(ch, sv, av), [])
    assert (lab, c) == (label, conf) and why


def _leg(ch, dirn, i0, i1, label, s_cls="impulse", a_cls="impulsive", conf="high"):
    A = ch.A
    p0 = A["l"][i0] if dirn > 0 else A["h"][i0]
    p1 = A["h"][i1] if dirn > 0 else A["l"][i1]
    lg = Leg(2, dirn, i0, i1, float(p0), float(p1), i1 + 1, ch.kat[i1 + 1])
    lg.structure = {"cls": s_cls, "family": "impulse" if s_cls == "impulse" else "zigzag", "n": 5}
    lg.anatomy = {"cls": a_cls, "score": 0.6 if a_cls == "impulsive" else -0.6}
    lg.label, lg.confidence = label, conf
    return lg


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
@pytest.mark.parametrize("label,s_cls,a_cls,conf,flips", [
    ("impulse", "impulse", "impulsive", "high", True),
    ("impulse", "impulse", "impulsive", "medium", True),     # agreed after re-read
    ("impulse", "impulse", "impulsive", "low", False),       # one vote only never sets / flips the trend
    ("uncertain", "impulse", "impulsive", None, False),      # uncertain never flips the trend
    ("correction", "correction", "corrective", "high", False),
    ("impulse", "correction", "impulsive", "high", False),   # needs impulse structure too
    ("impulse", "impulse", "corrective", "high", False),     # and impulsive anatomy
])
def test_only_a_trend_capable_impulse_moves_the_trend(label, s_cls, a_cls, conf, flips, mirror):
    df, marks = F.deep_sideways(mirror)
    ch = Chart(df)
    d = -1 if mirror else 1
    first = _leg(ch, d, marks[0], marks[5] + 1, "impulse")
    end = len(ch) - 30                                       # the counter-move ends beyond the first leg's start
    second = _leg(ch, -d, marks[5] + 1, end, label, s_cls, a_cls, conf)
    assert (second.p1 - first.p0) * -d > 0, "precondition: the counter-move breaks the prior swing"
    states, events = RT.derive(ch, [first, second])
    flipped = any(e["to"] == ("UP" if -d > 0 else "DOWN") for e in events)
    assert flipped == flips, events
    if not flips:
        assert states[-1]["trend"] in ("uncertain", "UP" if d > 0 else "DOWN")


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
def test_one_vote_impulse_never_sets_the_first_trend_or_moves_the_origin(mirror):
    df, marks = F.overlapping_correction(mirror)
    ch = Chart(df)
    d = -1 if mirror else 1
    weak = _leg(ch, d, marks[0], marks[5] + 1, "impulse", conf="low")
    states, events = RT.derive(ch, [weak])
    assert events == [] and all(s["trend"] is None for s in states)
    strong = _leg(ch, d, marks[0], marks[5] + 1, "impulse")
    later = _leg(ch, d, marks[8], marks[10], "impulse", conf="low")
    states, _ = RT.derive(ch, [strong, later])
    assert states[-1]["origin"] == strong.p0, "a one-vote impulse does not move the protected origin"


@pytest.mark.parametrize("mirror", (False, True), ids=("up", "down"))
def test_live_trend_needs_a_break_of_the_prior_swing_to_flip(mirror):
    df, marks = F.sharp_a(mirror)
    ch = Chart(df)
    d = -1 if mirror else 1
    first = _leg(ch, d, marks[0], marks[5] + 1, "impulse")
    second = _leg(ch, -d, marks[5] + 1, marks[10], "impulse")
    assert (second.p1 - first.p0) * -d < 0, "precondition: no break"
    states, events = RT.derive(ch, [first, second])
    assert not any(e["to"] == ("UP" if -d > 0 else "DOWN") for e in events)
    assert "no break of the prior swing" in states[second.known_bar]["why"]


def test_settings_register_matches_defaults():
    assert set(RS.REGISTER) == set(RS.DEFAULTS)
    assert set(RS.DEFAULTS["weights"]) == set(RS.FEATURES)


def test_reread_alternatives_stay_exactly_one_degree_lower():
    k = RS.DEFAULTS["dc_k"]
    ratio = max(k[i - 1] / k[i] for i in range(1, len(k)))
    assert all(ratio < m <= 1.0 for m in RS.DEFAULTS["reread_k_mult"])


def _alts(monkeypatch, s_fams=(), a_cls=()):
    S2 = {"impulse": "impulse", "diagonal": "impulse", "zigzag": "correction", "flat": "correction", "3-wave": "none"}
    xs = [(1.0, {"cls": S2[f], "family": f, "n": 5, "vote": 0}) for f in s_fams]
    xa = [(1.0, {"cls": c, "score": {"impulsive": 0.5, "corrective": -0.5}.get(c, 0.0)}) for c in a_cls]
    monkeypatch.setattr(RSt, "alternatives", lambda *a, **k: xs)
    monkeypatch.setattr(RF.RA, "alternatives", lambda *a, **k: xa)


def _leg1(ch, sv, av):
    lg = Leg(1, 1, 40, 60, 1.0, 2.0, 61, ch.kat[61])
    lg.structure, lg.anatomy = sv, av
    return lg


@pytest.mark.parametrize("fams,label,conf", [
    (("impulse", "impulse", "zigzag"), "impulse", "medium"),       # 2 / 3 agree ⇒ resolved
    (("impulse", "zigzag", "3-wave"), "impulse", "low"),            # 1 / 3 ⇒ no majority (no cherry-picking)
    (("impulse", "zigzag", "flat"), "uncertain", None),             # majority against
])
def test_reread_decides_by_majority_impulse_side(monkeypatch, fams, label, conf):
    df, _ = F.clean_impulse()
    ch = Chart(df)
    _alts(monkeypatch, s_fams=fams)
    lab, c, _ = RF.decide(ch, _leg1(ch, _sv("none", "3-wave"), _av("impulsive", 0.5)), [])
    assert (lab, c) == (label, conf)


@pytest.mark.parametrize("fams,label,conf", [
    (("zigzag", "flat", "impulse"), "correction", "medium"),       # same rule for the correction side
    (("zigzag", "impulse", "3-wave"), "correction", "low"),
    (("impulse", "diagonal", "zigzag"), "uncertain", None),
])
def test_reread_decides_by_majority_correction_side(monkeypatch, fams, label, conf):
    df, _ = F.clean_impulse()
    ch = Chart(df)
    _alts(monkeypatch, s_fams=fams)
    lab, c, _ = RF.decide(ch, _leg1(ch, _sv("none", "3-wave"), _av("corrective", -0.5)), [])
    assert (lab, c) == (label, conf)


@pytest.mark.parametrize("fam", ("zigzag", "flat", "triangle", "combination"))
def test_named_correction_is_never_reread_into_an_impulse(monkeypatch, fam):
    df, _ = F.clean_impulse()
    ch = Chart(df)
    _alts(monkeypatch, s_fams=("impulse", "impulse", "impulse"), a_cls=("impulsive", "impulsive", "impulsive"))
    lab, c, why = RF.decide(ch, _leg1(ch, _sv("correction", fam), _av("impulsive", 0.6)), [])
    assert lab == RF.UNCERTAIN and c is None
    _alts(monkeypatch, s_fams=("impulse", "impulse", "impulse"), a_cls=("corrective", "corrective", "neutral"))
    lab, c, _ = RF.decide(ch, _leg1(ch, _sv("correction", fam), _av("impulsive", 0.6)), [])
    assert (lab, c) == ("correction", "medium"), "the anatomy re-read can still confirm the named correction"
