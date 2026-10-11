"""reader2 CR2 — self-check pass (spec §3): every invariant 1–7 has a failing case that the pass fixes or marks uncertain; at most
3 passes; every relabel logged "relabelled X → Y because …" with known_at; no look-ahead. Mirror (UP / DOWN) pairs throughout."""
import pytest

from reader2 import fusion as RF
from reader2 import reader as RR
from reader2 import selfcheck as SC
from reader2 import trend as RT
from tests import reader2_fixtures as F

DIRS = (("up", False), ("down", True))
FIXTURES = ("clean_impulse", "overlapping_correction", "big_c_correction", "deep_sideways", "sharp_a")


def _d(mirror):
    return -1 if mirror else 1


def _name(d):
    return "UP" if d > 0 else "DOWN"


def _leg(R, d, degree=2, k=0):
    return [lg for lg in R.legs[degree] if lg.dirn == d][k]


def _invs(R):
    return {v["inv"] for v in SC.violations(R)}


def _check_log(R):
    assert R.log, "a relabel is never silent"
    for e in R.log:
        assert e["text"].startswith("relabelled ") and " → " in e["text"] and " because " in e["text"]
        assert e["known_at"] == R.known_at and e["at"] is not None


@pytest.mark.parametrize("name", FIXTURES)
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_own_reading_passes_its_check(name, dn, mirror):
    df, _ = getattr(F, name)(mirror)
    R = RR.read(df)
    assert SC.violations(R) == []
    assert 0 <= R.passes <= 3


# ---------------------------------------------------------------------------------------------------------------- invariant 1
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv1_impulse_label_with_corrective_anatomy_is_reread(dn, mirror):
    df, _ = F.overlapping_correction(mirror)
    R = RR.build(df)
    lg = _leg(R, -_d(mirror))
    RR.mark(R, labels={lg.key: "impulse"})
    assert "1" in _invs(R)
    SC.run(R)
    assert lg.label == "correction"
    assert any(e["invariant"] == "1" and e["from"] == "impulse" and e["to"] == "correction" for e in R.log)
    _check_log(R)


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv1_correction_label_with_impulsive_anatomy_is_reread(dn, mirror):
    df, _ = F.clean_impulse(mirror)
    R = RR.build(df)
    lg = _leg(R, _d(mirror))
    RR.mark(R, labels={lg.key: "correction"})
    assert "1" in _invs(R)
    SC.run(R)
    assert lg.label == "impulse" and R.trend_now()["trend"] == _name(_d(mirror))
    _check_log(R)


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_unresolved_after_max_passes_is_uncertain(dn, mirror):
    df, _ = F.overlapping_correction(mirror)
    R = RR.build(df, s={"max_passes": 0})
    lg = _leg(R, -_d(mirror))
    RR.mark(R, labels={lg.key: "impulse"})
    SC.run(R)
    assert lg.label == RF.UNCERTAIN and "unresolved after 0 self-check passes" in lg.reason


# ---------------------------------------------------------------------------------------------------------------- invariant 2
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv2_flip_without_a_break_of_the_prior_swing_is_undone(dn, mirror):
    df, _ = F.sharp_a(mirror)
    R = RR.build(df)
    d = _d(mirror)
    up, cm = _leg(R, d), _leg(R, -d)
    assert RT.eff_structure(cm)["cls"] == "impulse" and cm.anatomy["cls"] == "impulsive", "precondition: impulse-looking counter-move"
    RR.mark(R, labels={cm.key: "impulse"}, events=[{"bar": up.known_bar, "trend": _name(d), "origin": up.p0},
                                                    {"bar": cm.known_bar, "trend": _name(-d), "leg": cm.key}])
    assert "2" in _invs(R)
    SC.run(R)
    assert cm.label == RF.UNCERTAIN and "break" in cm.reason
    assert {st["trend"] for st in R.states[up.known_bar:]} == {_name(d)}
    e = next(e for e in R.log if "2" in e["invariant"].split("/") and e["target"].startswith("trend"))
    assert e["from"] == _name(-d) and e["to"] == _name(d) and "prior swing" in e["because"]
    _check_log(R)


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv2_flip_on_a_corrective_counter_move_is_undone(dn, mirror):
    df, _ = F.overlapping_correction(mirror)
    R = RR.build(df)
    d = _d(mirror)
    up, cm = _leg(R, d), _leg(R, -d)
    RR.mark(R, labels={cm.key: "impulse"}, events=[{"bar": up.known_bar, "trend": _name(d)},
                                                    {"bar": cm.known_bar, "trend": _name(-d), "leg": cm.key}])
    assert {"1", "2"} <= _invs(R)
    SC.run(R)
    assert cm.label == "correction"
    assert R.trend_now()["trend"] == _name(d) and not any(e["to"] == _name(-d) for e in R.events)
    _check_log(R)


# ---------------------------------------------------------------------------------------------------------------- invariant 3
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv3_correction_beyond_its_a_wave_is_not_a_flip(dn, mirror):
    df, marks = F.big_c_correction(mirror)
    R = RR.build(df)
    d = _d(mirror)
    up, cm = _leg(R, d), _leg(R, -d)
    assert cm.label == "correction"
    a_end = marks[6]
    a_px = df["low"].iloc[a_end] if d > 0 else df["high"].iloc[a_end]
    cross = next(i for i in range(max(a_end, up.known_bar) + 1, len(df)) if (df["close"].iloc[i] - a_px) * d < 0)   # c beyond a
    RR.mark(R, events=[{"bar": up.known_bar, "trend": _name(d)}, {"bar": cross, "trend": _name(-d)}])
    assert "3" in _invs(R)
    SC.run(R)
    assert cm.label == "correction"
    assert {st["trend"] for st in R.states[up.known_bar:]} == {_name(d)}
    e = next(e for e in R.log if "3" in e["invariant"])
    assert "not a flip" in e["because"] and e["from"] == _name(-d) and e["to"] == _name(d)
    _check_log(R)


# ---------------------------------------------------------------------------------------------------------------- invariant 4
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv4_close_beyond_the_protected_origin_rereads_the_trend(dn, mirror):
    df, _ = F.deep_sideways(mirror)
    R = RR.build(df)
    d = _d(mirror)
    up = _leg(R, d)
    brk = next(i for i in range(up.i1, len(df)) if (df["close"].iloc[i] - up.p0) * d < 0)
    assert R.states[brk]["trend"] == "uncertain" and R.states[brk - 1]["trend"] == _name(d), "own reading: re-read, not kept"
    RR.mark(R, events=[{"bar": up.known_bar, "trend": _name(d), "origin": up.p0}])        # stale marking keeps the trend
    assert "4" in _invs(R)
    SC.run(R)
    assert R.states[brk]["trend"] == "uncertain" and R.trend_now()["trend"] == "uncertain"
    assert any(e["invariant"] == "4" and e["to"] == "uncertain" for e in R.log)
    _check_log(R)


# ---------------------------------------------------------------------------------------------------------------- invariant 5
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv5_two_opposite_impulses_are_reread(dn, mirror):
    df, _ = F.sharp_a(mirror)
    R = RR.build(df)
    d = _d(mirror)
    up, cm = _leg(R, d), _leg(R, -d)
    assert up.label == cm.label == "impulse" and _invs(R) == {"5"}, "precondition: the fused labels alone violate 5"
    SC.run(R)
    assert up.label == "impulse" and cm.label == RF.UNCERTAIN
    assert not any(e["to"] == _name(-d) for e in R.events), "uncertain never flips the trend"
    assert any(e["invariant"] == "5" and e["target"] == cm.name() for e in R.log)
    _check_log(R)


# ---------------------------------------------------------------------------------------------------------------- invariant 6
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv6_higher_timeframe_wins_for_trend_lower_gives_the_pullback(dn, mirror):
    dfh, _ = F.clean_impulse(mirror)
    H = RR.read(dfh)
    d = _d(mirror)
    assert H.trend_now()["trend"] == _name(d)
    dfl, _ = F.clean_impulse(not mirror)                                       # lower TF trending the other way
    L = RR.read(F.hourly(dfl, start=dfh["timestamp"].iloc[-1]), higher=H)
    assert L.trend_now()["trend"] == _name(-d)
    assert L.htf == {"trend": _name(d), "lower_trend": _name(-d), "higher_trend": _name(d), "pullback": True, "contradiction": True}
    e = next(e for e in L.log if e["invariant"] == "6")
    assert "higher degree" in e["because"] and e["to"] == f"pullback within higher {_name(d)}"
    _check_log(L)
    same = RR.read(F.hourly(dfh, start=dfh["timestamp"].iloc[-1]), higher=H)
    assert same.htf["contradiction"] is False and not [e for e in same.log if e["invariant"] == "6"]


# ---------------------------------------------------------------------------------------------------------------- invariant 7
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv7_label_known_at_T_uses_bars_up_to_T(dn, mirror):
    """Fused labels and the trend state at T are the same whether or not later bars exist."""
    df, _ = F.overlapping_correction(mirror)
    full = RR.build(df)
    for T in (140, 170, 200, 240, 280):
        cut = RR.build(df.iloc[:T + 1])
        known = {lg.key: lg.label for lg in full.all_legs() if lg.known_bar <= T}
        mine = {lg.key: lg.label for lg in cut.all_legs()}
        assert known == mine, T
        assert [s["trend"] for s in full.states[:T + 1]] == [s["trend"] for s in cut.states], T


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv7_new_bars_rerun_the_check_and_log_every_change(dn, mirror):
    df, _ = F.deep_sideways(mirror)
    h = SC.history(df, start=150, step=1)
    Ts = sorted(h["trend"])
    changes = [(T, h["trend"][P], h["trend"][T]) for P, T in zip(Ts, Ts[1:]) if h["trend"][P] != h["trend"][T]]
    assert (None, _name(_d(mirror))) in [(a, b) for _, a, b in changes]
    assert (_name(_d(mirror)), "uncertain") in [(a, b) for _, a, b in changes], "close beyond origin re-reads the trend"
    logged = [(e["bar"], e["from"], e["to"]) for e in h["log"] if e["target"] == "trend"]
    assert logged == changes, "no silent label change"
    from reader2.frame import Chart
    kat = Chart(df).kat
    for e in h["log"]:
        assert e["known_at"] == kat[e["bar"]] and e["text"].startswith("relabelled ")


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_inv7_selfcheck_relabel_on_a_new_bar_carries_that_bars_known_at(dn, mirror):
    df, _ = F.sharp_a(mirror)
    R0 = RR.build(df)
    cm = _leg(R0, -_d(mirror))
    T = cm.known_bar
    before, at = RR.read(df.iloc[:T]), RR.read(df.iloc[:T + 1])
    assert before.find(*cm.key) is None
    lg = at.find(*cm.key)
    assert lg.label == RF.UNCERTAIN
    e = next(e for e in at.log if e["target"] == lg.name())
    assert e["known_at"] == at.ch.kat[T] and e["from"] == "impulse" and e["to"] == RF.UNCERTAIN
    assert lg.history and lg.history[-1]["known_at"] == at.ch.kat[T]
