"""CAS (Closing Auction Session) noise: setting, structure मधून वगळणं, official close (PDC) अबाधित, data tests.

Synthetic tests CI मध्ये; खऱ्या data चे tests (6 Oct 2026) trade-data नसेल तर skip.
"""
import os

import numpy as np
import pandas as pd
import pytest

from opportunity_engine import cas as CAS
from opportunity_engine import sessions as S

GOLDEN = os.path.join(os.environ.get("TRADE_DATA", "/home/user/trade-data"), "upstox", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz")


def _day(date, base=100.0, cas_close=None, frozen=True):
    """09:15–15:29 1m bars; 15:15–15:28 गोठलेले (frozen), 15:29 ला cas_close ची उडी."""
    ts = pd.date_range(f"{date} 09:15", f"{date} 15:29", freq="1min")
    n = len(ts)
    c = base + np.sin(np.arange(n) / 20.0) * 5
    o = np.r_[base, c[:-1]]
    h = np.maximum(o, c) + 0.5
    l = np.minimum(o, c) - 0.5
    df = pd.DataFrame({"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": 0.0})
    if frozen:
        k = df["timestamp"].dt.strftime("%H:%M") >= "15:15"
        v = float(df.loc[~k, "close"].iloc[-1])
        df.loc[k, ["open", "high", "low", "close"]] = v
        if cas_close is not None:
            df.loc[df.index[-1], ["high", "close"]] = cas_close
    return df


def test_setting_defaults_from_circular_and_override():
    w = CAS.load_cas_window()
    assert w["effective_from"] == "2026-08-03" and w["start"] == "15:15" and w["end"] == "15:30"
    assert "75479" in w["circular"]
    assert CAS.load_cas_window({"start": "15:20"})["start"] == "15:20"
    assert CAS.load_cas_window(False)["enabled"] is False
    with pytest.raises(ValueError):
        CAS.load_cas_window({"chart": "pink"})


def test_mask_only_after_effective_date_and_inside_window():
    ts = pd.to_datetime(["2026-07-31 15:20", "2026-08-03 15:14", "2026-08-03 15:15", "2026-08-03 15:29", "2026-08-03 15:30"])
    assert CAS.cas_mask(ts).tolist() == [False, False, True, True, False]
    assert not CAS.cas_mask(ts, False).any()


def test_resample_excludes_cas_high_keeps_official_close():
    df = _day("2026-10-06", cas_close=200.0)
    d = S.resample_nse_daily(df)
    assert float(d["high"].iloc[0]) < 120                                # 200 ची उडी high मध्ये नाही
    assert float(d["official_close"].iloc[0]) == 200.0                   # PDC = official close
    assert bool(d["cas"].iloc[0]) and bool(d["bar_closed"].iloc[0])
    m15 = S.resample_nse(df, 15)
    assert m15["timestamp"].dt.strftime("%H:%M").max() == "15:00"        # पूर्ण CAS 15:15 bin structure मधून काढला
    assert m15["high"].max() < 120
    flat = S.resample_nse(df, 15, cas_bars="flat")
    last = flat.iloc[-1]
    assert last["timestamp"].strftime("%H:%M") == "15:15" and bool(last["cas"]) and last["high"] == last["low"]
    assert float(last["official_close"]) == 200.0


def test_pre_cas_era_untouched():
    df = _day("2026-07-30", frozen=False)
    a, b = S.resample_nse(df, 15), S.resample_nse(df, 15, cas=False)
    pd.testing.assert_frame_equal(a, b)
    assert not a["cas"].any()


def test_daily_levels_pdh_clean_pdc_official():
    df = _day("2026-10-06", cas_close=200.0)
    g = CAS.daily_levels(df)
    assert g["high"].iloc[0] < 120 and g["close"].iloc[0] == 200.0 and g["clean_close"].iloc[0] < 120


def test_no_bars_outside_session():
    df = _day("2026-10-06", cas_close=200.0)
    extra = pd.DataFrame({"timestamp": pd.to_datetime(["2026-10-06 09:10", "2026-10-06 15:35", "2026-10-06 16:00"]),
                          "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0.0})
    m15 = S.resample_nse(pd.concat([df, extra]).sort_values("timestamp"), 15)
    hm = m15["timestamp"].dt.strftime("%H:%M")
    assert hm.min() >= "09:15" and (m15["bar_end"].dt.strftime("%H:%M") <= "15:30").all()


def test_outlier_wick_flag():
    df = _day("2026-10-06", cas_close=200.0)
    f = CAS.outlier_wicks(df)
    assert bool(f.iloc[-1]) and f.iloc[:-1].sum() == 0


def test_elliott_frames_exclude_cas():
    from elliott.swings import build_frame
    df = _day("2026-10-06", cas_close=200.0)
    for tf in ("1m", "15m", "1d"):
        assert build_frame(df, tf)["high"].max() < 120, tf


def test_chart_reader_prior_levels_and_daily_frame():
    from chart_reader import areas as AR
    from chart_reader import evaluate as EV
    df = pd.concat([_day("2026-10-06", cas_close=200.0), _day("2026-10-07")], ignore_index=True)
    pl = AR.prior_levels(df, pd.Timestamp("2026-10-07 10:00"))
    assert pl["pdh"] < 120 and pl["pdc"] == 200.0
    d1 = EV.frame(df, "1d", pd.Timestamp("2026-10-07 16:00"))
    assert d1["high"].max() < 120


def test_gap_context_uses_official_pdc():
    from vision import gap_context as GC
    df = pd.concat([_day("2026-10-06", cas_close=200.0), _day("2026-10-07")], ignore_index=True)
    dd = GC.daily(df)
    assert dd["close"].iloc[0] == 200.0 and dd["high"].iloc[0] < 120


# ------------------------------------------------------------------ खरा data (trade-data; नसेल तर skip)
@pytest.fixture(scope="module")
def golden():
    if not os.path.exists(GOLDEN):
        pytest.skip("trade-data golden 1m नाही")
    return pd.read_csv(GOLDEN, parse_dates=["timestamp"])


def test_real_6oct_top_and_official_close(golden):
    d = S.resample_nse_daily(golden).set_index("timestamp")
    r = d.loc[pd.Timestamp("2026-10-06")]
    assert abs(float(r["high"]) - 22731) < 5                             # TradingView ~22,731 (CAS उडी 22,776 नाही)
    assert float(r["official_close"]) == pytest.approx(22776.10)        # PDC = official close
    m15 = S.resample_nse(golden, 15)
    day = m15[m15["timestamp"].dt.normalize() == pd.Timestamp("2026-10-06")]
    assert day["high"].max() < 22740


def test_real_session_hours_and_outliers(golden):
    m15 = S.resample_nse(golden, 15)
    hm = m15["timestamp"].dt.strftime("%H:%M")
    assert hm.min() == "09:15" and hm.max() <= "15:15"
    assert (m15["bar_end"].dt.strftime("%H:%M") <= "15:30").all()
    post = golden[golden["timestamp"] >= "2026-08-03"].reset_index(drop=True)
    flags = CAS.outlier_wicks(post)
    assert bool(flags[post["timestamp"] == pd.Timestamp("2026-10-06 15:29")].iloc[0])     # 22,717.70 → 22,776.10 उडी
    clean = CAS.strip_cas(post)
    assert not CAS.cas_mask(clean["timestamp"]).any()
    cf = CAS.outlier_wicks(clean)
    late = clean["timestamp"].dt.strftime("%H:%M") >= "15:15"
    assert not (cf & late).any()                                         # CAS वगळल्यावर शेवटच्या 15 मिनिटांत outlier नाही


def test_opportunity_engine_pdc_is_official_close():
    """V3 review: OE key levels / gap registry चा PDC = official close (CAS), PDH CAS वगळून."""
    from opportunity_engine import zones as Z
    from opportunity_engine.config import EngineConfig
    df = pd.concat([_day("2026-10-06", cas_close=200.0), _day("2026-10-07", base=150.0)], ignore_index=True)
    daily = S.resample_nse_daily(df)
    kl = {z["source"]: z["low"] for z in Z.key_levels(daily, pd.Timestamp("2026-10-07 10:00"), 150.0)}
    assert kl["PDC"] == 200.0 and kl["PDH"] < 120
    gaps = Z.gap_registry(daily, pd.Timestamp("2026-10-07 16:00"), EngineConfig())
    assert all(200.0 in (g["low"], g["high"]) for g in gaps)
    assert float(CAS.pdc_col(daily).iloc[0]) == 200.0 and float(CAS.pdc_col(daily.drop(columns=["official_close"])).iloc[0]) < 120
