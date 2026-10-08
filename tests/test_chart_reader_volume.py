"""Chart Reader — K10.3 futures volume: causal continuous roll, slot-normalised rel_vol, VL पुरावा (−5…+5; data नाही ⇒ 0)."""
import numpy as np
import pandas as pd

from chart_reader import settings as CS
from chart_reader import volume as V

S = dict(CS.DEFAULTS)


def _two_contracts():
    rows = []
    days = pd.date_range("2026-10-19", periods=4, freq="D")
    vols = [(1000, 100), (800, 900), (300, 1500), (900, 1000)]                            # day 2 ला पुढचा जास्त ⇒ day 3 पासून
    for d, (a, b) in zip(days, vols):
        for c, v in (("OCT", a), ("NOV", b)):
            rows.append({"timestamp": d + pd.Timedelta(hours=9, minutes=15), "volume": v, "contract": c})
    return pd.DataFrame(rows)


def test_roll_is_causal_and_sticky():
    out = V.continuous(_two_contracts())
    assert list(out["contract"]) == ["OCT", "OCT", "NOV", "NOV"]                           # day 2 चा निर्णय day 2 संपल्यावर
    assert list(out["roll_day"]) == [False, False, True, False]


def test_roll_without_contract_column_is_identity():
    f = pd.DataFrame({"timestamp": pd.date_range("2026-10-19 09:15", periods=3, freq="5min"), "volume": [1, 2, 3]})
    assert list(V.continuous(f)["volume"]) == [1, 2, 3]


def test_to_tf_sums_on_nse_anchors():
    f = pd.DataFrame({"timestamp": pd.date_range("2026-10-19 09:15", periods=6, freq="5min"), "volume": [1, 2, 3, 4, 5, 6],
                      "roll_day": False})
    out = V.to_tf(f, 15)
    assert list(out["volume"]) == [6, 15] and str(out["timestamp"].iloc[1])[11:16] == "09:30"


def test_rel_vol_uses_only_prior_days_same_slot():
    rows = []
    for k, d in enumerate(pd.date_range("2026-09-01", periods=8, freq="D")):
        for hm, v in (("09:15", 300.0), ("10:00", 100.0)):
            rows.append({"timestamp": pd.Timestamp(f"{d.date()} {hm}"), "volume": 200.0 if (k == 7 and hm == "10:00") else v})
    rv = V.rel_vol(pd.DataFrame(rows), days=20)
    assert rv.iloc[:2 * V.MIN_PRIOR_DAYS].isna().all()                                     # आधीचे 5 दिवस नाहीत ⇒ NaN
    assert rv[pd.Timestamp("2026-09-08 10:00")] == 2.0 and rv[pd.Timestamp("2026-09-08 09:15")] == 1.0


def _trig(closes, opens=None):
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]] if opens is None else np.asarray(opens, float)
    return pd.DataFrame({"timestamp": pd.date_range("2026-10-19 09:15", periods=len(c), freq="15min"), "open": o,
                         "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c})


ST = {"impulse": {"start_bar": 0, "end_bar": 5}, "correction_bars": [5, 7, 8, 10]}


def test_vl_dryup_plus_rev_volume_and_rising_and_no_data():
    trig = _trig([100, 102, 104, 106, 108, 110, 109, 108, 109, 108, 107, 108.5])
    rv = np.r_[[1.5] * 6, [0.6] * 5, 1.3]                                                  # pullback कोरडा, reversal candle ला volume
    r = V.evidence(trig, ST, rv, 1, S, mr=1.0)
    assert r["pts"] == 5 and "dry-up" in r["line"] and "[K10.3]" in r["line"]
    rv2 = np.r_[[0.8] * 6, [1.4] * 6]
    assert V.evidence(trig, ST, rv2, 1, S, mr=1.0)["pts"] <= -3                            # वाढता volume ⇒ −5 (+ reversal bonus)
    assert V.evidence(trig, ST, np.full(12, np.nan), 1, S, mr=1.0)["pts"] == 0
    assert V.evidence(trig, ST, None, 1, S, mr=1.0)["pts"] == 0


def test_series_for_maps_futures_to_trigger_bars():
    days = pd.date_range("2026-09-01", periods=7, freq="D")
    rows = [{"timestamp": d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=5 * i), "volume": 10.0, "contract": "OCT"}
            for d in days for i in range(6)]
    fut = pd.DataFrame(rows)
    trig = pd.DataFrame({"timestamp": [days[-1] + pd.Timedelta(hours=9, minutes=15), days[-1] + pd.Timedelta(hours=9, minutes=30)]})
    out = V.series_for(trig, fut, 15)
    assert list(out) == [1.0, 1.0]
    assert np.isnan(V.series_for(trig, None, 15)).all()


def test_load_merges_front_history_and_all_store(tmp_path):
    """Review: `_all` (नवीन, 5 दिवस) असला तरी front-only file चा जुना इतिहास वापरायचा."""
    old = pd.DataFrame({"timestamp": pd.date_range("2026-09-01 09:15", periods=3, freq="1D"), "volume": [1.0, 2.0, 3.0], "contract": "OCT"})
    new = pd.DataFrame({"timestamp": [pd.Timestamp("2026-09-03 09:15"), pd.Timestamp("2026-09-03 09:15")], "volume": [3.0, 9.0],
                        "contract": ["OCT", "NOV"]})
    old.to_parquet(tmp_path / "oe_futures_5min_NIFTY.parquet", index=False)
    new.to_parquet(tmp_path / "oe_futures_5min_NIFTY_all.parquet", index=False)
    d = V.load("NIFTY", str(tmp_path))
    assert len(d) == 4 and sorted(d["contract"].unique()) == ["NOV", "OCT"]


def test_series_for_tz_aware_trigger_is_normalised():
    days = pd.date_range("2026-09-01", periods=7, freq="D")
    fut = pd.DataFrame([{"timestamp": d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=5 * i), "volume": 10.0, "contract": "OCT"}
                        for d in days for i in range(3)])
    trig = pd.DataFrame({"timestamp": [(days[-1] + pd.Timedelta(hours=9, minutes=15)).tz_localize("Asia/Kolkata")]})
    assert list(V.series_for(trig, fut, 15)) == [1.0]
