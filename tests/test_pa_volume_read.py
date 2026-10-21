"""PA standard §2I — decision3/volume_read.py (synthetic: comparative FUT volume reads, reuse of method absorption / commitment)."""
from collections import namedtuple

import numpy as np

from decision3 import method as M
from decision3 import settings as S3
from decision3 import volume_read as VR

P = namedtuple("P", "bar kind price confirm_bar")
UP, DOWN = 1, -1


def frame(closes, vols, spread=0.5):
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    return {"open": o, "high": np.maximum(o, c) + spread, "low": np.minimum(o, c) - spread, "close": c,
            "volume_raw": np.array(vols, float)}


def up_then_pullback(pull_vol, imp_vol=200.0, deep=False):
    imp = [100, 102, 104, 106, 108, 110]                                   # bars 0..5: impulse up (swing low at 0, high at 5)
    pb = [109, 108, 107] + ([90] if deep else [106.5])                     # bars 6..9: pullback
    A = frame(imp + pb, [imp_vol] * 6 + [pull_vol] * 4)
    sw = VR.swings([P(0, "L", A["low"][0], 1), P(5, "H", A["high"][5], 7)], 9)
    return A, sw


def test_pullback_on_lower_volume_than_the_impulse():
    A, sw = up_then_pullback(100.0)
    r = VR.pullback_vs_impulse(A, sw, 9)
    assert r["state"] == "lower" and r["impulse"]["dir"] == UP
    assert r["impulse"]["avg_volume"] == 200.0 and r["pullback"]["avg_volume"] == 100.0
    assert "pullback on lower volume than the impulse up" in r["evidence"]
    A2, sw2 = up_then_pullback(300.0)
    assert VR.pullback_vs_impulse(A2, sw2, 9)["state"] == "higher"
    A3, sw3 = up_then_pullback(100.0, deep=True)
    assert VR.pullback_vs_impulse(A3, sw3, 9)["state"] == "beyond"


def test_unconfirmed_swing_is_not_used_and_gaps_never_count_as_zero():
    A, _ = up_then_pullback(100.0)
    sw = VR.swings([P(0, "L", A["low"][0], 1), P(5, "H", A["high"][5], 12)], 9)   # the high is confirmed only at bar 12
    assert VR.pullback_vs_impulse(A, sw, 9)["state"] == "na"
    A, sw = up_then_pullback(100.0)
    A["volume_raw"][7] = np.nan
    r = VR.pullback_vs_impulse(A, sw, 9)
    assert r["state"] == "lower" and r["pullback"]["gaps"] == 1 and r["pullback"]["avg_volume"] == 100.0


def test_no_volume_is_na():
    A, sw = up_then_pullback(100.0)
    A.pop("volume_raw")
    for f in (VR.pullback_vs_impulse, VR.climax, VR.effort_result):
        assert f(A, sw, 9)["state"] == "na"


def test_swings_alternate_keeping_the_more_extreme():
    sw = VR.swings([P(0, "L", 10, 1), P(2, "H", 20, 3), P(4, "H", 25, 5), P(6, "L", 15, 7)], 7)
    assert sw == [(0, "L", 10.0), (4, "H", 25.0), (6, "L", 15.0)]


def selling_climax(after_lower=False):
    closes = [110, 108, 106, 104, 102, 95, 97, 96.5] + ([93] if after_lower else [96])
    vols = [100, 110, 100, 120, 110, 500, 150, 120, 130]
    o = np.array([110, 110, 108, 106, 104, 102, 95.5, 97, 96.5], float)
    c = np.array(closes, float)
    A = {"open": o, "high": np.maximum(o, c) + 0.3, "low": np.minimum(o, c) - 0.3, "close": c, "volume_raw": np.array(vols, float)}
    sw = VR.swings([P(0, "H", A["high"][0], 1)], 8)
    return A, sw


def test_climax_largest_volume_large_candle_at_the_extreme_then_no_progress():
    A, sw = selling_climax()
    r = VR.climax(A, sw, 8)
    assert r["state"] == "found" and r["current"]["bar"] == 5 and r["current"]["dir"] == DOWN
    assert any("selling climax" in e for e in r["evidence"])
    A2, sw2 = selling_climax(after_lower=True)                              # a later candle goes lower ⇒ progress ⇒ no climax
    assert VR.climax(A2, sw2, 8)["state"] == "none"
    r5 = VR.climax(A, sw, 5)                                                # on the climax bar itself: forming (no look-ahead)
    assert r5["state"] == "forming"


def test_effort_without_result_vs_the_previous_leg_same_direction():
    up1 = [100, 102, 104, 106, 108, 110]                                    # leg up: 10 points, volume 100
    dn = [108, 106, 105]                                                    # leg down
    up2 = [106, 107, 107.5, 108]                                            # leg up again: 3 points, volume 300
    c = up1 + dn + up2
    A = frame(c, [100] * 6 + [100] * 3 + [300] * 4, spread=0.1)
    sw = VR.swings([P(0, "L", A["low"][0], 1), P(5, "H", A["high"][5], 6), P(8, "L", A["low"][8], 9)], 12)
    r = VR.effort_result(A, sw, 12)
    assert r["state"] == "effort without result"
    assert r["leg"]["effort"] == "more" and r["leg"]["result"] == "less"
    A2 = frame(c[:9] + [108, 111, 114, 117], [100] * 9 + [50] * 4, spread=0.1)   # less volume, more progress ⇒ ease
    assert VR.effort_result(A2, sw, 12)["state"] == "result with ease"


class FakeV:
    """Just what volume_read's area reads call: visit, vol_view, s, levels.A, _ts."""
    def __init__(self, A, start, approach_from=None):
        A["volume"] = A["volume_raw"]                                      # the engine's A carries both (raw default)
        self.levels = type("L", (), {"A": A})()
        self.s = dict(S3.DEFAULTS)
        self._ts = np.array([np.datetime64("2026-01-05T09:15") + np.timedelta64(15 * i, "m") for i in range(len(A["close"]))])
        self._start, self._appr = start, approach_from

    def visit(self, t, lvl, d, k0=0):
        return {"start": self._start, "approach_from": self._appr, "why": None}

    def vol_view(self, a, t):
        return self.levels.A, "raw"


def test_absorption_reuses_zone_study_and_adds_volume_wording():
    o = np.array([101, 100, 100.6, 100.0, 100.5, 100.1, 100.4, 100.0], float)
    c = np.array([100, 100.6, 100.0, 100.5, 100.1, 100.4, 100.0, 100.3], float)
    A = {"open": o, "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c,
         "volume_raw": np.array([100, 100, 120, 100, 150, 100, 180, 100], float)}
    V = FakeV(A, start=0)
    area = {"role": "resistance", "lo": 99.5, "hi": 101.5}
    r = VR.absorption(V, 7, area)
    zs = M.zone_study(A, 0, 7, DOWN, V.s)
    assert zs["absorption"] and r["state"] == "absorbing"
    assert r["volume"]["opposite_later"] is not None
    assert "absorption at the supply" in r["evidence"] and r["volume"]["opposite_keeps_coming"]


def test_commitment_volume_reuses_method_commitment():
    o = np.array([105, 104, 103, 102, 101, 100.5, 100.2, 100.8], float)
    c = np.array([104, 103, 102, 101, 100.5, 100.2, 100.8, 104.0], float)
    A = {"open": o, "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c,
         "volume_raw": np.array([100, 100, 100, 100, 100, 100, 100, 400], float)}
    V = FakeV(A, start=4, approach_from=1)
    area = {"role": "support", "lo": 99.5, "hi": 100.6}
    r = VR.commitment_volume(V, 7, area)
    ok, why, cm = M.commitment(A, 7, UP, area, V.s, V._ts, win=4, approach=range(1, 4))
    assert r["vol_mult"] == cm.get("vol_mult") and r["form"] == cm.get("form")
    assert r["state"] == "above" and ok
    A["volume_raw"][7] = 50.0                                              # same array as A["volume"]
    assert VR.commitment_volume(V, 7, area)["state"] == "not_above"


def test_v22_volume_reads_truncation_safe():
    from tests.test_decision3_method import _abc_m15
    from tests.test_pa_candle_forms import _v22
    m15 = _abc_m15()
    V = _v22(m15)
    states = set()
    for t in range(0, len(m15), 7):
        r = VR.read_volume(V, t)
        states.add(r["pullback_vs_impulse"]["state"])
        assert all(o["kind"].startswith(("volume_", "effort", "absorption")) for o in VR.draw_objects(r))
    assert states - {"na"}                                                 # not vacuous
    for t in (200, 420, 640):
        Vt = _v22(m15.iloc[:t + 1].reset_index(drop=True))
        a, b = VR.public(VR.read_volume(V, t)), VR.public(VR.read_volume(Vt, t))
        assert a == b
        for ar in [x for x in V.levels.snapshot(t) if x["tf"] == "1H"][:3]:
            assert VR.public(VR.read_volume(V, t, area=ar)) == VR.public(VR.read_volume(Vt, t, area=ar))
