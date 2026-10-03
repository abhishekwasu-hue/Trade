"""tests/test_htf_alignment.py -- htf_alignment.py (bar_end, align_asof) आणि resamplers चे `bar_end` column.
🎓 fix/completed-bars-1h: HTF (1H/4H/Daily) bar कमी TF ला फक्त त्याच्या bar_end नंतरच उपलब्ध व्हावा."""
import numpy as np
import pandas as pd
import pytest

import htf_alignment as h
from signals import resample_to_1h, resample_to_4h


def _hm(series):
    return [t.strftime("%H:%M") for t in series]


def _nse_30m(days=("2024-03-12",), last_start="15:15"):
    """NSE सारखे Upstox 30M bars (label = खरी सुरुवात: 09:15, 09:45 … 15:15)."""
    parts = [pd.date_range(f"{d} 09:15", f"{d} {last_start}", freq="30min") for d in days]
    ts = parts[0].append(parts[1:]) if len(parts) > 1 else parts[0]
    close = 100 + np.arange(len(ts), dtype=float)
    return pd.DataFrame({"timestamp": ts, "open": close - .5, "high": close + 1, "low": close - 1, "close": close, "volume": 10, "oi": 0})


def _nse_15m(days=("2024-03-12",)):
    parts = [pd.date_range(f"{d} 09:15", f"{d} 15:15", freq="15min") for d in days]
    ts = parts[0].append(parts[1:]) if len(parts) > 1 else parts[0]
    close = 100 + np.arange(len(ts), dtype=float)
    return pd.DataFrame({"timestamp": ts, "open": close - .5, "high": close + 1, "low": close - 1, "close": close, "volume": 10, "oi": 0})


# ---- compute_bar_end / resamplers ------------------------------------------------------------------------------------------
def test_nse_1h_from_30m_labels_are_hour_but_bars_end_at_quarter_past():
    h1 = resample_to_1h(_nse_30m())
    assert _hm(h1["timestamp"]) == ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    assert _hm(h1["bar_end"]) == ["10:15", "11:15", "12:15", "13:15", "14:15", "15:15", "16:15"]   # शेवटचा conservative (बाजार 15:30 ला बंद)


def test_resample_adds_bar_end_without_changing_existing_values():
    src = _nse_30m()
    out = resample_to_1h(src)
    expected = src.set_index("timestamp").resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "oi": "last"}).dropna(subset=["open"]).reset_index()
    pd.testing.assert_frame_equal(out.drop(columns="bar_end"), expected)
    assert out["bar_end"].notna().all()


def test_mcx_1h_and_4h_bar_end_equal_label_plus_duration_so_mcx_is_unchanged():
    ts = pd.date_range("2024-03-12 09:00", "2024-03-12 23:00", freq="30min")
    d30 = pd.DataFrame({"timestamp": ts, "open": 1.0, "high": 2.0, "low": .5, "close": 1.5, "volume": 1, "oi": 0})
    h1, h4 = resample_to_1h(d30), resample_to_4h(d30)
    assert ((h1["bar_end"] - h1["timestamp"]) == pd.Timedelta(hours=1)).all()
    assert ((h4["bar_end"] - h4["timestamp"]) == pd.Timedelta(hours=4)).all()
    assert _hm(h4["timestamp"]) == ["09:00", "13:00", "17:00", "21:00"]


def test_offline_one_minute_source_gives_clock_hour_bars():
    src = pd.date_range("2024-03-12 09:15", "2024-03-12 15:29", freq="1min")
    labels = pd.date_range("2024-03-12 09:00", "2024-03-12 15:00", freq="1h")
    assert _hm(h.compute_bar_end(labels, src, 60)) == ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]
    assert _hm(h.compute_bar_end(pd.date_range("2024-03-12 09:15", periods=3, freq="15min"), src, 15)) == ["09:30", "09:45", "10:00"]


def test_real_nifty_resampled_frames_carry_bar_end():
    import real_nifty_data as r
    x = r.load_nifty_resampled(60, "2024-03-12", "2024-03-12")
    assert "bar_end" in x.columns and _hm(x["bar_end"])[:2] == ["10:00", "11:00"]
    y = r.load_nifty_resampled(15, "2024-03-12", "2024-03-12")
    assert _hm(y["bar_end"])[:2] == ["09:30", "09:45"]


def test_bar_end_is_correct_for_a_still_forming_last_bar_and_keeps_timezone():
    """चालू (अपूर्ण) 1H bar चा शेवट source मधल्या शेवटच्या bar वरून नाही, grid वरून -- म्हणून 10:15 चा एकच 30M bar आल्यावरही bar_end 11:15."""
    d30 = _nse_30m(last_start="10:15")                       # 10:00-label चा bar अजून फक्त 10:15 पर्यंतच्या एकाच 30M bar चा
    h1 = resample_to_1h(d30)
    assert _hm(h1["bar_end"]) == ["10:15", "11:15"]
    aware = d30.assign(timestamp=d30["timestamp"].dt.tz_localize("Asia/Kolkata"))
    h1_aware = resample_to_1h(aware)
    assert str(h1_aware["bar_end"].dt.tz) == "Asia/Kolkata" and _hm(h1_aware["bar_end"]) == ["10:15", "11:15"]


# ---- bar_end_times (fallbacks) ---------------------------------------------------------------------------------------------
def test_bar_end_times_fallbacks_raw_bars_and_daily():
    raw = _nse_15m()
    assert _hm(h.bar_end_times(raw))[:2] == ["09:30", "09:45"]                     # label + अनुमानित 15 मिनिटं
    daily = pd.DataFrame({"timestamp": pd.to_datetime(["2024-03-11", "2024-03-12"]), "close": [1.0, 2.0]})
    assert [t.strftime("%d %H:%M") for t in h.bar_end_times(daily)] == ["11 15:30", "12 15:30"]
    assert h.is_daily(daily["timestamp"]) and not h.is_daily(raw["timestamp"])
    one_row = raw.iloc[:1]
    assert h.bar_end_times(one_row).iloc[0] == one_row["timestamp"].iloc[0]       # कालावधी अनुमानता न आल्यास जुनं वर्तन (label)


# ---- align_asof -------------------------------------------------------------------------------------------------------------
def test_ltf_bar_never_sees_an_htf_bar_before_it_is_complete():
    """09:15 चा 15M bar ला 09:15–10:15 चा 1H bar मिळू नये; 1H bar फक्त 10:15 (त्याच्या bar_end) ला किंवा नंतर बंद होणाऱ्या 15M bar ला."""
    ltf = _nse_15m()
    htf = resample_to_1h(_nse_30m())
    htf["val"] = np.arange(len(htf), dtype=float)               # 09:00→0, 10:00→1, 11:00→2 …
    out = h.align_asof(ltf, htf, ["val"])["val"]
    by_label = dict(zip(_hm(ltf["timestamp"]), out))
    # 09:15, 09:30, 09:45 bars (end ≤ 10:00): कुठलाच 1H bar पूर्ण नाही
    assert all(np.isnan(by_label[k]) for k in ("09:15", "09:30", "09:45"))
    # 10:00 चा 15M bar 10:15 ला बंद होतो = पहिल्या 1H bar चा bar_end ⇒ आता 0 उपलब्ध (बरोबरी समाविष्ट)
    assert by_label["10:00"] == 0 and by_label["10:15"] == 0 and by_label["10:30"] == 0 and by_label["10:45"] == 0
    assert by_label["11:00"] == 1                                # 11:15 ला बंद ⇒ दुसरा 1H bar (10:15–11:15) उपलब्ध


def test_property_matched_htf_bar_never_ends_after_the_ltf_decision_time():
    days = ("2024-03-11", "2024-03-12", "2024-03-13")
    ltf, htf = _nse_15m(days), resample_to_1h(_nse_30m(days))
    htf["idx"] = np.arange(len(htf), dtype=float)
    matched = h.align_asof(ltf, htf, ["idx"])["idx"]
    ltf_end = h.bar_end_times(ltf)
    htf_end = h.bar_end_times(htf).reset_index(drop=True)
    for i, m in enumerate(matched):
        if np.isnan(m):
            assert ltf_end.iloc[i] < htf_end.iloc[0]
        else:
            assert htf_end.iloc[int(m)] <= ltf_end.iloc[i]
            if int(m) + 1 < len(htf_end):
                assert htf_end.iloc[int(m) + 1] > ltf_end.iloc[i]              # आणि त्यानंतरचा bar अजून पूर्ण नाही (म्हणजे सर्वात अलीकडचा पूर्ण bar)


def test_daily_bar_available_only_after_close_and_next_day():
    ltf = _nse_15m(("2024-03-12", "2024-03-13"))
    daily = pd.DataFrame({"timestamp": pd.to_datetime(["2024-03-11", "2024-03-12"]), "val": [10.0, 20.0]})
    out = h.align_asof(ltf, daily, ["val"])["val"].tolist()
    ts = ltf["timestamp"]
    d12 = [v for t, v in zip(ts, out) if t.date().day == 12]
    d13 = [v for t, v in zip(ts, out) if t.date().day == 13]
    assert set(d12[:-1]) == {10.0}          # 12 तारखेच्या दिवशी (शेवटच्या 15:15 bar वगळता) फक्त 11 तारखेचा daily bar पूर्ण
    assert d12[-1] == 20.0                  # 15:15 चा bar 15:30 ला बंद होतो = daily bar चा bar_end
    assert set(d13) == {20.0}


def test_mixed_datetime_precision_and_timezone_do_not_crash():
    """pandas 3: datetime64[us] आणि [ns] मिसळल्यास merge_asof MergeError द्यायचा; tz-aware वि. naive सुद्धा."""
    ltf = _nse_15m()
    htf = resample_to_1h(_nse_30m())
    htf["val"] = np.arange(len(htf), dtype=float)
    base = h.align_asof(ltf, htf, ["val"])["val"]
    htf_us = htf.assign(bar_end=htf["bar_end"].astype("datetime64[us]"), timestamp=htf["timestamp"].astype("datetime64[us]"))
    pd.testing.assert_series_equal(h.align_asof(ltf, htf_us, ["val"])["val"], base)
    ltf_aware = ltf.assign(timestamp=ltf["timestamp"].dt.tz_localize("Asia/Kolkata"))
    htf_aware = htf.assign(bar_end=htf["bar_end"].dt.tz_localize("Asia/Kolkata"), timestamp=htf["timestamp"].dt.tz_localize("Asia/Kolkata"))
    pd.testing.assert_series_equal(h.align_asof(ltf_aware, htf_aware, ["val"])["val"], base)
    pd.testing.assert_series_equal(h.align_asof(ltf, htf_aware, ["val"])["val"], base)       # एक बाजू aware, दुसरी naive


def test_result_keeps_ltf_row_order_and_handles_empty_or_all_nan():
    ltf = _nse_15m()
    htf = resample_to_1h(_nse_30m()).assign(val=1.0)
    out = h.align_asof(ltf.iloc[::-1].reset_index(drop=True), htf, ["val"])          # LTF उलट क्रमात
    assert len(out) == len(ltf)
    fwd = h.align_asof(ltf, htf, ["val"])["val"].tolist()
    rev = out["val"].tolist()[::-1]
    assert [(np.isnan(a), np.isnan(b)) for a, b in zip(fwd, rev)] == [(a, a) for a in (np.isnan(x) for x in fwd)]
