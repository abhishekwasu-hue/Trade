"""reader2 CR1 — anatomy vote (spec §2b / §2d / §7): candles read only at the lowest degree, higher-degree legs rolled up from their
sub-legs one degree lower; median-range units; mirror (UP / DOWN) pairs."""
import numpy as np
import pandas as pd
import pytest

from reader2 import anatomy as RA
from reader2 import fusion as RF
from reader2 import reader as RR
from reader2 import settings as RS
from reader2.frame import Chart, with_futures_volume
from tests import reader2_fixtures as F

DIRS = (("up", False), ("down", True))
NAMED_NO_REREAD = ("review rule (CR-Q11): a NAMED corrective structure (here the zigzag read from the mis-placed pivots) is never "
                   "re-read into an impulse, even though 3/3 alternative pivot sets one degree lower read 5 waves and the candles are "
                   "impulsive ⇒ uncertain, not impulse/medium. Kept failing on purpose (fixture and expectation unchanged)")


def _legs(R, degree=2):
    return R.legs[degree]


def _trend_leg(R, mirror):
    d = -1 if mirror else 1
    return next(lg for lg in _legs(R) if lg.dirn == d)


def _counter_leg(R, mirror):
    d = 1 if mirror else -1
    return next(lg for lg in _legs(R) if lg.dirn == d)


def _candle_votes(v):
    """All lowest-degree (candle) votes under a rolled-up vote."""
    if v.get("level") == "candles":
        return [v]
    return [c for x in v.get("subs", []) for c in _candle_votes(x["vote"])]


# --------------------------------------------------------------------------------------------------------------- feature scores
def test_feature_score_maps_linearly_and_respects_sides():
    assert RA.feature_score(0.55, 0.35, 0.55, "both") == pytest.approx(1.0)
    assert RA.feature_score(0.35, 0.35, 0.55, "both") == pytest.approx(-1.0)
    assert RA.feature_score(0.45, 0.35, 0.55, "both") == pytest.approx(0.0)
    assert RA.feature_score(0.20, 0.60, 0.35, "both") == pytest.approx(1.0)        # inverted measure (less overlap ⇒ impulsive)
    assert RA.feature_score(0.0, 0.0, 0.25, "imp") == 0.0                         # absence of displacement is not corrective
    assert RA.feature_score(0.1, 0.5, 0.25, "cor") == 0.0                         # a short stall is not impulsive evidence
    assert RA.feature_score(None, 0.0, 1.0, "both") is None
    assert RA.feature_score(float("nan"), 0.0, 1.0, "both") is None


# --------------------------------------------------------------------------------------------------------------- the four fixtures
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_clean_impulse_reads_impulsive(dn, mirror):
    df, _ = F.clean_impulse(mirror)
    R = RR.read(df)
    lg = _trend_leg(R, mirror)
    assert lg.anatomy["cls"] == "impulsive" and lg.anatomy["score"] >= RS.DEFAULTS["a_hi"]
    assert lg.structure["family"] == "impulse"
    assert (lg.label, lg.confidence) == ("impulse", "high")
    assert lg.anatomy["level"] == "rollup", "a degree-2 leg is read from its sub-legs, not from all its candles"
    ev = {e["feature"]: e for e in lg.anatomy["evidence"]}
    assert ev["sub:motive"]["lean"] == "impulsive" and ev["sub:counter"]["lean"] == "impulsive"   # counter sub-legs corrective
    motive = [x for x in lg.anatomy["subs"] if x["dirn"] == lg.dirn]
    assert len(motive) == 3 and all(x["vote"]["cls"] == "impulsive" for x in motive)
    leaves = _candle_votes(lg.anatomy)
    assert leaves and all(set(RS.FEATURES) <= {e["feature"] for e in v["evidence"]} for v in leaves if v["score"] is not None), \
        "every candle feature is listed in the lowest-degree evidence (NA ones too)"
    assert all(e["text"] for e in lg.anatomy["evidence"])


@pytest.mark.parametrize("seed", (1, 2, 3))
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_rollup_is_not_diluted_by_waves_2_and_4(dn, mirror, seed):
    """Realistic impulse: the average of all its candles (waves 2 / 4 included) reads neutral; the roll-up of its sub-legs reads
    impulsive (spec §2d: candles only at the lowest degree)."""
    df, _ = F.realistic(F.IMPULSE + F.OVERLAP_ABC[:1], mirror, seed=seed)
    R = RR.read(df)
    lg = _trend_leg(R, mirror)
    flat = RA.vote(R.ch, lg.i0, lg.i1, lg.dirn)
    assert flat["cls"] == "neutral"
    assert lg.anatomy["level"] == "rollup" and lg.anatomy["cls"] == "impulsive"
    assert (lg.label, lg.confidence) == ("impulse", "high")


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_overlapping_correction_reads_corrective(dn, mirror):
    df, _ = F.overlapping_correction(mirror)
    R = RR.read(df)
    lg = _counter_leg(R, mirror)
    assert lg.anatomy["cls"] == "corrective" and lg.anatomy["score"] <= RS.DEFAULTS["a_lo"]
    assert (lg.label, lg.confidence) == ("correction", "high")
    ev = {e["feature"]: e for e in lg.anatomy["evidence"]}
    assert ev["sub:motive"]["lean"] == "corrective", "waves a and c are overlapping"
    leaf = _candle_votes(lg.anatomy)[0]
    lev = {e["feature"]: e for e in leaf["evidence"]}
    assert lev["overlap"]["lean"] == "corrective" and lev["wick_both"]["lean"] == "corrective"


def _misplaced(R, mirror):
    """Degree-1 pivots inside the impulse with waves 3 and 4 dropped ⇒ the impulse looks like a 3-wave a-b-c."""
    lg = _trend_leg(R, mirror)
    inner = [p for p in R.pivots[1] if lg.i0 <= p.bar <= lg.i1]
    assert len(inner) == 6, "precondition: 5 waves visible at degree 1"
    keep = [inner[0], inner[1], inner[2], inner[5]]
    rest = [p for p in R.pivots[1] if p.bar > lg.i1]
    return {1: [(p.bar, p.kind, p.confirm_bar) for p in keep + rest]}


@pytest.mark.xfail(strict=True, reason=NAMED_NO_REREAD)
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_misplaced_pivots_are_caught_by_the_anatomy_vote(dn, mirror):
    df, _ = F.clean_impulse(mirror)
    pv = _misplaced(RR.read(df), mirror)
    R = RR.read(df, pivots=pv)
    lg = _trend_leg(R, mirror)
    assert lg.structure["family"] == "zigzag", "precondition: the mis-placed pivots read as a correction"
    assert lg.anatomy["cls"] == "impulsive"
    assert lg.label == "impulse" and lg.confidence == "medium", lg.reason
    assert "alternative pivots one degree lower" in lg.reason
    assert lg.reread["structure"]["family"] == "impulse"


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_misplaced_pivots_without_reread_never_read_correction(dn, mirror):
    df, _ = F.clean_impulse(mirror)
    pv = _misplaced(RR.read(df), mirror)
    R = RR.read(df, s={"reread_k_mult": ()}, pivots=pv)
    lg = _trend_leg(R, mirror)
    assert lg.label == RF.UNCERTAIN
    assert "zigzag" in lg.reason and "impulsive" in lg.reason


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_big_c_correction_stays_a_correction(dn, mirror):
    df, marks = F.big_c_correction(mirror)
    R = RR.read(df)
    lg = _counter_leg(R, mirror)
    a_end, c_end = marks[6], marks[8]
    lo, hi = df["low"].to_numpy(), df["high"].to_numpy()
    if mirror:
        assert hi[c_end] > hi[a_end] + 50, "precondition: c ends well beyond a"
    else:
        assert lo[c_end] < lo[a_end] - 50, "precondition: c ends well beyond a"
    assert lg.structure["family"] in ("zigzag", "flat")
    assert lg.anatomy["cls"] != "impulsive", "wave a is corrective ⇒ the impulsive c cannot make the leg impulsive"
    a_sub = [x for x in lg.anatomy["subs"] if x["dirn"] == lg.dirn][0]
    assert a_sub["vote"]["cls"] == "corrective"
    assert lg.label == "correction"
    want = "DOWN" if mirror else "UP"
    known = next(x for x in _legs(R) if x.label == "impulse").known_bar
    assert {st["trend"] for st in R.states[known:]} == {want}, "c beyond a never flips the trend"


# --------------------------------------------------------------------------------------------------------------- units, NA, volume
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_anatomy_is_scale_free(dn, mirror):
    """All measures are in median-range units: scaling / shifting prices leaves every score unchanged."""
    df, _ = F.overlapping_correction(mirror)
    df2 = df.copy()
    for c in ("open", "high", "low", "close"):
        df2[c] = df[c] * 7.0 + 12345.0
    a, b = RR.read(df), RR.read(df2)
    for x, y in zip(a.all_legs(), b.all_legs()):
        assert x.key == y.key and x.label == y.label
        sa, sb = x.anatomy["score"], y.anatomy["score"]
        assert (sa is None and sb is None) or sa == pytest.approx(sb, abs=1e-9)


def test_short_leg_is_na():
    df, _ = F.clean_impulse()
    ch = Chart(df)
    v = RA.vote(ch, 100, 102, 1)
    assert v["score"] is None and v["cls"] == "NA" and "too short" in v["evidence"][0]["text"]


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_volume_is_used_when_present_and_na_safe_otherwise(dn, mirror):
    df, _ = F.overlapping_correction(mirror, volume=True)
    R = RR.read(df)
    lg = next(x for x in R.legs[0] if x.i0 == _counter_leg(R, mirror).i0)          # wave a: a lowest-degree leg (candles)
    ev = {e["feature"]: e for e in lg.anatomy["evidence"]}
    assert lg.anatomy["level"] == "candles"
    assert ev["volume"]["value"] < 1.0 and ev["volume"]["lean"] == "corrective"   # lower volume than the impulse it corrects
    for vol in (None, 0.0, np.nan):                                               # no column / index spot volume 0 / missing
        d2 = df.drop(columns="volume") if vol is None else df.assign(volume=vol)
        R2 = RR.read(d2)
        lg2 = next(x for x in R2.legs[0] if x.key == lg.key)
        ev2 = {e["feature"]: e for e in lg2.anatomy["evidence"]}
        assert ev2["volume"]["score"] is None and "NA" in ev2["volume"]["text"]
        assert lg2.anatomy["score"] is not None and _counter_leg(R2, mirror).label == "correction"


def test_one_sided_features_without_evidence_do_not_dilute():
    df, _ = F.overlapping_correction()
    v = RA.vote(Chart(df), 124, 163, -1)
    for e in v["evidence"]:
        side = RS.FEATURES[e["feature"]][2]
        if side != "both" and e["score"] == 0.0:
            assert e["counted"] is False


def test_with_futures_volume_maps_near_month_rows_to_spot_bars():
    from mtf.adapter import SYN_EPOCH                                               # synthetic sessions, no real dates
    day = SYN_EPOCH + pd.Timedelta(hours=9, minutes=15)
    h = pd.Timedelta(hours=1)
    spot = pd.DataFrame({"timestamp": [day, day + h, day + 2 * h], "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    near, far = SYN_EPOCH + pd.Timedelta(days=20), SYN_EPOCH + pd.Timedelta(days=50)
    fut = pd.DataFrame({"timestamp": [day, day + pd.Timedelta(minutes=5), day + h, day],
                        "volume": [10.0, 5.0, 7.0, 999.0], "expiry": [near, near, near, far]})
    out = with_futures_volume(spot, fut)
    assert out["volume"].iloc[0] == 15.0 and out["volume"].iloc[1] == 7.0        # far-month row ignored
    assert np.isnan(out["volume"].iloc[2])                                        # no futures row ⇒ NA
    assert with_futures_volume(spot, None)["volume"].isna().all()


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_lower_timeframe_candles_join_the_daily_anatomy(dn, mirror):
    df, _ = F.overlapping_correction(mirror)
    low = F.split_hourly(df)
    R = RR.read(df, low=low)
    lg = _counter_leg(R, mirror)
    leaves = _candle_votes(lg.anatomy)
    assert any(any(e["feature"].startswith("lower:") for e in v["evidence"]) and v["lower"]["score"] is not None for v in leaves)
    assert lg.label == "correction"


# --------------------------------------------------------------------------------------------------------------- realistic candles
@pytest.mark.parametrize("seed", (1, 2, 3))
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_realistic_impulse_and_correction(dn, mirror, seed):
    """Noisy candles (bodies ~50–65 %, wicks on both sides): the roll-up still reads the impulse and the overlapping correction."""
    df, _ = F.realistic(F.IMPULSE + F.OVERLAP_ABC + F.CONT, mirror, seed=seed)
    R = RR.read(df)
    up, cm = _trend_leg(R, mirror), _counter_leg(R, mirror)
    assert (up.label, up.confidence) == ("impulse", "high"), up.reason
    assert cm.label == "correction" and cm.anatomy["cls"] == "corrective", cm.reason
    assert R.trend_now()["trend"] == ("DOWN" if mirror else "UP")


@pytest.mark.parametrize("seed", (1, 2, 3))
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_structure_only_impulse_is_challenged(dn, mirror, seed):
    """A clean 5-wave count drawn with ambiguous candles: structure says impulse, the candles do not ⇒ uncertain, no trend."""
    df, _ = F.realistic(F.neutral_shape(F.IMPULSE) + F.OVERLAP_ABC, mirror, seed=seed)
    R = RR.read(df)
    lg = _trend_leg(R, mirror)
    assert lg.structure["family"] == "impulse" and lg.anatomy["cls"] != "impulsive"
    assert lg.label == RF.UNCERTAIN
    assert all(st["trend"] is None for st in R.states), "a structure-only impulse never sets the trend"


# --------------------------------------------------------------------------------------------------------------- sharp a-b-c
@pytest.mark.parametrize("depth", (0.65, 0.72, 0.8))
@pytest.mark.parametrize("seed", (None, 1, 2, 3))
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_sharp_abc_with_impulsive_a_and_c_stays_a_correction(dn, mirror, seed, depth):
    """Abhi's "sharp fall ⇒ a-b-c": a and c are impulsive candles, b a bounce. The candles alone (c resembles a; b long against
    a) keep the roll-up from reading impulsive — no wave count in the anatomy — so the zigzag structure labels it a correction
    (not uncertain, not impulse); the trend stays with the prior impulse."""
    shape = F.IMPULSE + F.sharp_abc(depth * F.IMP_SIZE) + F.CONT
    df, _ = F.frame(shape, mirror) if seed is None else F.realistic(shape, mirror, seed=seed)
    R = RR.read(df)
    cm = _counter_leg(R, mirror)
    subs = cm.anatomy["subs"]
    assert len(subs) == 3, "precondition: a-b-c visible one degree lower"
    if seed is None:
        assert all(x["vote"]["cls"] == "impulsive" for x in subs if x["dirn"] == cm.dirn), "precondition: a and c impulsive"
    assert cm.anatomy["cls"] != "impulsive", cm.reason
    ev = {e["feature"]: e for e in cm.anatomy["evidence"]}
    assert ev["sub:c_like_a"]["lean"] == "corrective" or ev["sub:b_brief"]["lean"] == "corrective"
    assert cm.label == "correction", cm.reason
    assert {s["trend"] for s in R.states[_trend_leg(R, mirror).known_bar:]} == {"DOWN" if mirror else "UP"}


@pytest.mark.parametrize("c_mult", (1.3, 1.6))
@pytest.mark.parametrize("seed", (None, 1, 2))
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_sharp_abc_with_a_longer_c_is_never_an_impulse(dn, mirror, seed, c_mult):
    """Unequal sharp a-b-c (c ≈ 1.3–1.6 × a): never labelled impulse and never flips the trend; correction or uncertain allowed."""
    shape = F.IMPULSE + F.sharp_abc(0.72 * F.IMP_SIZE, c_mult=c_mult) + F.CONT
    df, _ = F.frame(shape, mirror) if seed is None else F.realistic(shape, mirror, seed=seed)
    R = RR.read(df)
    cm = _counter_leg(R, mirror)
    assert cm.label in ("correction", RF.UNCERTAIN), cm.reason
    against = "UP" if mirror else "DOWN"
    assert against not in [s["trend"] for s in R.states]
    assert not any(e["to"] == against for e in R.events)


# --------------------------------------------------------------------------------------------------------------- reviewer probes
SMALL_W4 = [("imp", 150, 14), ("cor", -70, 20), ("imp", 300, 24), ("cor", -12, 3), ("imp", 160, 14)]
SMALL_W2 = [("imp", 150, 14), ("cor", -12, 3), ("imp", 300, 24), ("cor", -80, 22), ("imp", 160, 14)]


@pytest.mark.parametrize("shape", (SMALL_W4, SMALL_W2), ids=("small-wave-4", "small-wave-2"))
@pytest.mark.parametrize("seed", (None, 1, 2))
@pytest.mark.parametrize("dn,mirror", DIRS)
def test_impulse_with_a_sub_threshold_wave_never_reads_correction_high(dn, mirror, seed, shape):
    """Reviewer probe: a 12-point, 3-bar wave 4 (or 2) is below the degree-1 threshold, so only 3 sub-legs are visible. The anatomy
    has no wave count, so the impulse must not come out as a high-confidence correction."""
    full = shape + F.OVERLAP_ABC[:1]
    df, _ = F.frame(full, mirror) if seed is None else F.realistic(full, mirror, seed=seed)
    R = RR.read(df)
    lg = _trend_leg(R, mirror)
    assert not (lg.label == "correction" and lg.confidence == "high"), lg.reason
    assert lg.anatomy["cls"] != "corrective", lg.reason
