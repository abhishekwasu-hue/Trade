"""engine3_live.UpstoxFeed: कालचा दिवस history मधून गळू नये (13 Oct 2026 VPS: to_date = आज ⇒ 12 Oct चे 15M / 5M गायब)."""
import datetime as dt

import pandas as pd

import engine3_live as L


def _bars(day, minutes):
    t = pd.Timestamp(f"{day} 09:15")
    out = []
    while t + pd.Timedelta(minutes=minutes) <= pd.Timestamp(f"{day} 15:30"):
        out.append([t.strftime("%Y-%m-%dT%H:%M:%S+05:30"), 100.0, 101.0, 99.0, 100.5, 0, 0])
        t += pd.Timedelta(minutes=minutes)
    return out


def _fake_upstox(monkeypatch, today, drop_prev_when_to_is_today=True, holidays=()):
    import verify_opportunity_data_availability as V
    calls = []

    def window(token, key, interval, frm, to, expired=False):
        calls.append((interval, frm, to))
        mins = {"15minute": 15, "5minute": 5}.get(interval)
        rows, d = [], frm
        last_ok = to
        if drop_prev_when_to_is_today and to >= today:                  # Upstox वर्तन: to = आज ⇒ कालचा दिवस नाही
            last_ok = today - dt.timedelta(days=2)
        while d <= min(to, last_ok):
            if d.weekday() < 5 and d not in holidays and d < today:
                rows += _bars(d, mins) if mins else [[f"{d}T00:00:00+05:30", 100.0, 101.0, 99.0, 100.5, 0, 0]]
            d += dt.timedelta(days=1)
        return {"status": 200, "candles": rows, "error": None}

    monkeypatch.setattr(V, "fetch_candles_window", window)
    monkeypatch.setattr(V, "_get", lambda url, tok: (200, {"data": {"candles": []}}, None))
    return calls


def test_minute_history_includes_previous_trading_day(monkeypatch):
    today = dt.date(2026, 10, 13)                                        # मंगळवार; काल = सोमवार 12 Oct
    calls = _fake_upstox(monkeypatch, today)
    f = L.UpstoxFeed("tok", today)
    for interval in ("15minute", "5minute"):
        df = f.index("NIFTY", interval, 20)
        days = set(pd.to_datetime(df["timestamp"]).dt.tz_localize(None).dt.date)
        assert dt.date(2026, 10, 12) in days and dt.date(2026, 10, 9) in days, interval
    assert all(to < today for iv, frm, to in calls if iv != "day")      # minute history ची to_date कधीच आज नाही


def test_gap_fill_fetches_missing_weekday_and_skips_holiday(monkeypatch):
    today = dt.date(2026, 10, 13)
    calls = _fake_upstox(monkeypatch, today, drop_prev_when_to_is_today=False, holidays={dt.date(2026, 10, 12)})
    df = L.UpstoxFeed("tok", today).index("NIFTY", "15minute", 20)
    days = set(pd.to_datetime(df["timestamp"]).dt.tz_localize(None).dt.date)
    assert dt.date(2026, 10, 12) not in days and dt.date(2026, 10, 9) in days   # सुट्टी ⇒ रिकामं, error नाही
    assert ("15minute", dt.date(2026, 10, 12), dt.date(2026, 10, 12)) in calls


def test_daily_history_still_ends_today(monkeypatch):
    today = dt.date(2026, 10, 13)
    calls = _fake_upstox(monkeypatch, today, drop_prev_when_to_is_today=False)
    L.UpstoxFeed("tok", today).index("NIFTY", "day", 40)
    assert max(to for iv, frm, to in calls if iv == "day") == today
