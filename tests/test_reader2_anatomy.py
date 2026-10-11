"""reader2 CR1 — anatomy vote from the candles inside a leg (spec §2b / §7), in median-range units; mirror (UP / DOWN) pairs."""
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


def _legs(R, degree=2):
    return R.legs[degree]


def _trend_leg(R, mirror):
    d = -1 if mirror else 1
    return next(lg for lg in _legs(R) if lg.dirn == d)


def _counter_leg(R, mirror):
    d = 1 if mirror else -1
    return next(lg for lg in _legs(R) if lg.dirn == d)


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
    feats = {e["feature"] for e in lg.anatomy["evidence"]}
    assert set(RS.FEATURES) <= feats, "every anatomy feature is listed in the evidence (NA ones too)"
    assert all(e["text"] for e in lg.anatomy["evidence"])


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_overlapping_correction_reads_corrective(dn, mirror):
    df, _ = F.overlapping_correction(mirror)
    R = RR.read(df)
    lg = _counter_leg(R, mirror)
    assert lg.anatomy["cls"] == "corrective" and lg.anatomy["score"] <= RS.DEFAULTS["a_lo"]
    assert (lg.label, lg.confidence) == ("correction", "high")
    ev = {e["feature"]: e for e in lg.anatomy["evidence"]}
    assert ev["overlap"]["lean"] == "corrective" and ev["wick_both"]["lean"] == "corrective"


def _misplaced(R, mirror):
    """Degree-1 pivots inside the impulse with waves 3 and 4 dropped ⇒ the impulse looks like a 3-wave a-b-c."""
    lg = _trend_leg(R, mirror)
    inner = [p for p in R.pivots[1] if lg.i0 <= p.bar <= lg.i1]
    assert len(inner) == 6, "precondition: 5 waves visible at degree 1"
    keep = [inner[0], inner[1], inner[2], inner[5]]
    rest = [p for p in R.pivots[1] if p.bar > lg.i1]
    return {1: [(p.bar, p.kind, p.confirm_bar) for p in keep + rest]}


@pytest.mark.parametrize("dn,mirror", DIRS)
def test_misplaced_pivots_are_caught_by_the_anatomy_vote(dn, mirror):
    df, _ = F.clean_impulse(mirror)
    pv = _misplaced(RR.read(df), mirror)
    R = RR.read(df, pivots=pv)
    lg = _trend_leg(R, mirror)
    assert lg.structure["family"] == "zigzag", "precondition: the mis-placed pivots read as a correction"
    assert lg.anatomy["cls"] == "impulsive"
    assert lg.label == "impulse", lg.reason
    assert "conflicted with anatomy" in lg.reason and "re-read" in lg.reason
    assert lg.structure["reread"]["family"] == "impulse"


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
    assert lg.anatomy["cls"] != "impulsive"
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
    lg = _counter_leg(RR.read(df), mirror)
    ev = {e["feature"]: e for e in lg.anatomy["evidence"]}
    assert ev["volume"]["value"] < 1.0 and ev["volume"]["lean"] == "corrective"   # lower volume than the impulse it corrects
    for vol in (None, 0.0, np.nan):                                               # no column / index spot volume 0 / missing
        d2 = df.drop(columns="volume") if vol is None else df.assign(volume=vol)
        lg2 = _counter_leg(RR.read(d2), mirror)
        ev2 = {e["feature"]: e for e in lg2.anatomy["evidence"]}
        assert ev2["volume"]["score"] is None and "NA" in ev2["volume"]["text"]
        assert lg2.anatomy["score"] is not None and lg2.label == "correction"


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
    assert any(e["feature"].startswith("lower:") for e in lg.anatomy["evidence"])
    assert lg.anatomy["lower"]["score"] is not None
    assert lg.label == "correction"
