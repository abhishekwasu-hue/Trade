"""tests/test_opportunity_engine_data.py -- sessions (NSE 1H/4H bins, bar_end, bar_is_full, session quality), measures (ref_range/ADR), adapters, journal."""
import os

import numpy as np
import pandas as pd
import pytest

import real_nifty_data
from opportunity_engine import adapters, measures, sessions
from opportunity_engine.config import EngineConfig
from opportunity_engine.journal import Journal
from opportunity_engine.structure import StructureTracker
from signals import resample_to_1h


def _fine(days=("2024-03-12",), step=1, start="09:15", end="15:29", extra=None):
    parts = [pd.date_range(f"{d} {start}", f"{d} {end}", freq=f"{step}min") for d in days]
    ts = parts[0].append(parts[1:]) if len(parts) > 1 else parts[0]
    if extra is not None:
        ts = ts.append(extra).sort_values()
    rng = np.random.default_rng(1)
    close = 22000 + np.cumsum(rng.normal(0, 1.0, len(ts)))
    return pd.DataFrame({"timestamp": ts, "open": close - 0.3, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 0})


def _hm(s):
    return [t.strftime("%H:%M") for t in s]


# ---- sessions: NSE bins ----------------------------------------------------------------------------------------------------------
def test_nse_1h_bars_start_at_quarter_past_and_last_bar_is_15_minutes():
    h1 = sessions.resample_nse_1h(_fine())
    assert _hm(h1["bar_start"]) == ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"]
    assert _hm(h1["bar_end"]) == ["10:15", "11:15", "12:15", "13:15", "14:15", "15:15", "15:30"]
    assert h1["bar_is_full"].tolist() == [True] * 6 + [False]
    assert (h1["timestamp"] == h1["bar_start"]).all()


def test_nse_4h_bars_split_at_13_15_and_second_bar_is_short():
    h4 = sessions.resample_nse_4h(_fine())
    assert _hm(h4["bar_start"]) == ["09:15", "13:15"] and _hm(h4["bar_end"]) == ["13:15", "15:30"]
    assert h4["bar_is_full"].tolist() == [True, False]
    assert h4["high"].iloc[0] >= _fine().iloc[:240]["high"].max() - 1e-9


def test_5m_and_15m_bars_are_all_full_and_30m_last_bar_is_not():
    d = _fine()
    assert sessions.resample_nse(d, 5)["bar_is_full"].all() and sessions.resample_nse(d, 15)["bar_is_full"].all()
    m30 = sessions.resample_nse(d, 30)
    assert _hm(m30["bar_start"])[-1] == "15:15" and not m30["bar_is_full"].iloc[-1] and m30["bar_is_full"].iloc[:-1].all()


def test_no_source_bar_ends_after_its_bar_end_and_bins_do_not_cross_days():
    d = _fine(("2024-03-12", "2024-03-13"))
    for minutes in (15, 60, 240):
        out = sessions.resample_nse(d, minutes)
        assert (out["bar_end"].dt.normalize() == out["bar_start"].dt.normalize()).all()
        assert (out["bar_end"] > out["bar_start"]).all() and out["bar_end"].dt.strftime("%H:%M").max() <= "15:30"
        assert out["bar_end"].is_monotonic_increasing


def test_content_matches_old_resampler_but_labels_are_true_starts():
    d30 = sessions.resample_nse(_fine(), 30)[["timestamp", "open", "high", "low", "close", "volume"]]
    d30["oi"] = 0
    old = resample_to_1h(d30)                                       # जुनं: labels :00, सामग्री 09:15-anchored
    new = sessions.resample_nse_1h(_fine())
    np.testing.assert_allclose(old[["open", "high", "low", "close"]].to_numpy(), new[["open", "high", "low", "close"]].to_numpy())
    assert _hm(old["timestamp"])[0] == "09:00" and _hm(new["timestamp"])[0] == "09:15"


def test_upstox_5m_source_gives_same_bins_as_1m_source():
    one = _fine()
    five = sessions.resample_nse(one, 5)[["timestamp", "open", "high", "low", "close", "volume"]]
    a = sessions.resample_nse_1h(one)
    b = sessions.resample_nse_1h(five)
    np.testing.assert_allclose(a[["open", "high", "low", "close"]].to_numpy(), b[["open", "high", "low", "close"]].to_numpy())
    assert a["bar_end"].tolist() == b["bar_end"].tolist() and a["bar_is_full"].tolist() == b["bar_is_full"].tolist()


# ---- session quality ---------------------------------------------------------------------------------------------------------------
def test_muhurat_evening_and_after_hours_bars_are_dropped_and_short_days_flagged():
    evening = pd.date_range("2024-03-12 17:30", "2024-03-12 18:30", freq="1min")
    d = pd.concat([_fine(("2024-03-11",)), _fine(("2024-03-12",), end="12:59", extra=evening)], ignore_index=True).sort_values("timestamp")
    reg = sessions.filter_regular_hours(d)
    assert reg["timestamp"].dt.hour.max() <= 15 and len(reg) == len(d) - len(evening)
    q = sessions.session_quality(reg).set_index("date")
    assert not q.loc[pd.Timestamp("2024-03-11"), "short"] and q.loc[pd.Timestamp("2024-03-12"), "short"]
    daily = sessions.resample_nse_daily(d)
    assert daily["bar_is_full"].tolist() == [True, False]
    h1 = sessions.resample_nse_1h(d)
    last_day = h1[h1["bar_start"].dt.normalize() == pd.Timestamp("2024-03-12")]
    assert not last_day["bar_is_full"].iloc[-1]                     # डेटा 12:59 ला संपल्याने शेवटचा bin अपूर्ण


def test_empty_and_invalid_inputs_do_not_crash():
    assert sessions.resample_nse(pd.DataFrame(), 15).empty and sessions.resample_nse_daily(None).empty
    only_evening = _fine(start="17:30", end="18:30")
    assert sessions.resample_nse(only_evening, 60).empty


def test_build_frames_adds_daily_extension_after_fine_data_ends():
    ext = pd.DataFrame({"timestamp": pd.to_datetime(["2024-03-13", "2024-03-14"]), "open": [1.0, 2.0], "high": [2.0, 3.0], "low": [0.5, 1.5], "close": [1.5, 2.5], "volume": [10, 20]})
    f = sessions.build_frames(_fine(), ext)
    assert set(f) == {"5m", "15m", "1h", "4h", "1d"} and len(f["1d"]) == 3 and f["1d"]["bar_end"].dt.strftime("%H:%M").eq("15:30").all()
    assert f["1d"]["bar_is_full"].all()


# ---- measures ------------------------------------------------------------------------------------------------------------------------
def test_ref_range_is_median_scalar_over_last_n_full_bars_only():
    df = pd.DataFrame({"high": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20.0, 100.0], "low": [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 0.0]})
    df["bar_is_full"] = [True] * 11 + [False]                        # अपूर्ण (मोठ्या) bar वगळला
    v = measures.ref_range(df, n=20, min_bars=10)
    assert isinstance(v, float) and v == pytest.approx(float(np.median(df["high"][:11] - df["low"][:11])))
    assert measures.ref_range(df.iloc[:5], n=20, min_bars=10) != measures.ref_range(df.iloc[:5], n=20, min_bars=10)       # NaN (warm-up)
    assert np.isnan(measures.ref_range(None)) and np.isnan(measures.ref_range(pd.DataFrame(columns=["high", "low"])))
    window = measures.ref_range(df.iloc[:11], n=3, min_bars=3)
    assert window == pytest.approx(float(np.median((df["high"] - df["low"])[8:11])))


def test_ref_range_and_adr_never_return_series():
    df = pd.DataFrame({"high": np.arange(30) + 2.0, "low": np.arange(30) + 0.0})
    assert type(measures.ref_range(df)) is float and type(measures.adr(df)) is float
    assert measures.adr(df.iloc[:3]) != measures.adr(df.iloc[:3])      # NaN: < min_days


def test_adr_skips_short_sessions():
    d = sessions.resample_nse_daily(pd.concat([_fine(("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14", "2024-03-15", "2024-03-18")),
                                               _fine(("2024-03-19",), end="12:59")], ignore_index=True))
    assert not d["bar_is_full"].iloc[-1]
    assert measures.adr(d, n=14, min_days=5) == pytest.approx(float(np.median((d["high"] - d["low"]).iloc[:-1])))


# ---- adapters ------------------------------------------------------------------------------------------------------------------------
def test_adapter_normalises_columns_timezone_order_and_duplicates():
    raw = pd.DataFrame({"Date": pd.to_datetime(["2024-03-12 09:20", "2024-03-12 09:15", "2024-03-12 09:15"]).tz_localize("Asia/Kolkata"),
                        "Open": [2, 1, 1], "High": [3, 2, 2], "Low": [1, 0, 0], "Close": [2.5, 1.5, 1.5]})
    out = adapters.to_engine_frame(raw)
    assert list(out.columns)[:5] == ["timestamp", "open", "high", "low", "close"] and len(out) == 2
    assert out["timestamp"].dt.tz is None and out["timestamp"].is_monotonic_increasing and out["timestamp"].iloc[0].hour == 9
    legacy = adapters.to_legacy_frame(out)
    assert {"Date", "Open", "High", "Low", "Close"} <= set(legacy.columns)
    assert adapters.to_engine_frame(None).empty and adapters.to_engine_frame(pd.DataFrame({"x": [1]})).empty


# ---- journal ------------------------------------------------------------------------------------------------------------------------
def _walk_frames(n_days=40, seed=7):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2024-01-01", periods=n_days)
    ts = pd.DatetimeIndex([d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=m) for d in days for m in range(375)])
    close = 22000 + np.cumsum(rng.normal(0, 3.0, len(ts))) + 120 * np.sin(np.arange(len(ts)) / 600.0)
    df = pd.DataFrame({"timestamp": ts, "open": close - 0.5, "high": close + 2.0, "low": close - 2.0, "close": close, "volume": 0})
    return sessions.build_frames(df)


def test_incremental_journal_equals_batch_run_and_is_deterministic():
    frames = _walk_frames()
    batch = Journal().run({"1h": frames["1h"], "15m": frames["15m"]})
    inc = Journal(tfs=("1h", "15m"))
    for tf in ("1h", "15m"):
        for r in frames[tf].itertuples():
            inc.on_bar_close(tf, r.bar_end, r.open, r.high, r.low, r.close, r.bar_is_full)
    for tf in ("1h", "15m"):
        assert [(e["bar_idx"], e["type"], e["price"]) for e in batch.trackers[tf].events] == [(e["bar_idx"], e["type"], e["price"]) for e in inc.trackers[tf].events]


def test_journal_future_bars_do_not_change_earlier_state():
    frames = _walk_frames()
    full = Journal().run({"1h": frames["1h"]})
    cut = len(frames["1h"]) // 2
    part = Journal().run({"1h": frames["1h"].iloc[:cut]})
    a = [(e["bar_idx"], e["type"], e["price"]) for e in full.trackers["1h"].events if e["bar_idx"] < cut]
    assert a == [(e["bar_idx"], e["type"], e["price"]) for e in part.trackers["1h"].events]
    t = frames["1h"]["bar_end"].iloc[cut - 1]
    assert full.state_at("1h", t) == part.state("1h")


def test_state_at_events_and_structure_table():
    frames = _walk_frames()
    j = Journal().run({tf: frames[tf] for tf in ("1d", "4h", "1h")})
    assert j.state_at("1h", pd.Timestamp("2000-01-01")) == "INIT"
    table = j.structure_table(("1h",))
    assert list(table.columns) == ["time", "tf", "event", "from_state", "state", "price", "trigger_bar", "detail"]
    if len(table):
        assert table["time"].is_monotonic_increasing and (table["trigger_bar"] <= table["time"]).all()
    snap = j.snapshot("1h")
    assert snap["trend_state"] == j.state("1h") and snap["updated_at"] == frames["1h"]["bar_end"].iloc[-1]
    assert j.events("1h", types=("CHOCH",)) == [e for e in j.events("1h") if e["type"] == "CHOCH"]


@pytest.mark.skipif(not os.path.exists(real_nifty_data._DATA_PATH), reason="offline NIFTY डेटा नाही")
def test_real_offline_nifty_smoke():
    df = real_nifty_data.load_nifty_1min("2023-09-01", "2024-03-27")
    frames = sessions.build_frames(df)
    assert frames["1d"]["bar_is_full"].iloc[-1] is np.False_ or not frames["1d"]["bar_is_full"].iloc[-1]       # 2024-03-27 (12:59 ला संपलेला) short
    j = Journal().run({tf: frames[tf] for tf in ("1d", "4h", "1h")})
    for tf in ("1d", "4h", "1h"):
        assert j.state(tf) in ("INIT", "RANGE", "UPTREND", "UPTREND_PULLBACK", "UPTREND_WEAK", "DOWNTREND", "DOWNTREND_PULLBACK", "DOWNTREND_WEAK")
        assert j.trackers[tf].rr > 0


@pytest.mark.skipif(not os.path.exists(real_nifty_data._DATA_PATH), reason="offline NIFTY डेटा नाही")
def test_real_data_no_lookahead_4h_and_daily():
    """खऱ्या डेटावर (2015–2024): अर्धा डेटा कापून चालवला तरी त्या भागातले events पूर्ण-डेटा चालवल्यासारखेच."""
    df = real_nifty_data.load_nifty_1min("2018-01-01", "2024-03-27")
    frames = sessions.build_frames(df)
    for tf in ("4h", "1d"):
        full = Journal().run({tf: frames[tf]})
        cut = len(frames[tf]) // 2
        part = Journal().run({tf: frames[tf].iloc[:cut]})
        a = [(e["bar_idx"], e["type"], e["price"]) for e in full.trackers[tf].events if e["bar_idx"] < cut]
        b = [(e["bar_idx"], e["type"], e["price"]) for e in part.trackers[tf].events]
        assert a == b and len(a) > 20, tf
