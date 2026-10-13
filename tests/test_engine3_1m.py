"""Abhi Z-1o = (a): live decision3 engine gets spot 1m ⇒ V22 df1m (swings2 intrabar order, as replay / rsi2). No network.

  • df1m reaches V22; only closed 1m inside closed 15M bars (nothing after the decided bar ⇒ no look-ahead).
  • 1m missing / error ⇒ old path (no 1m) + reason in the row, never a data-error block.
  • `engine3_use_1m` (dashboard, default True) toggles it; False ⇒ 1m is not even fetched.
  • UpstoxFeed 1m: history once per day (disk cache), intraday every cycle.
"""
import datetime as dt
import json

import pandas as pd
import pytest

import engine3_live as L
import engine_signal as ES
from tests.test_one_bot import Feed


class Feed1m(Feed):
    """test_one_bot.Feed + spot 1m (15 rows per 15M bar) and deliberately later rows (after `now`) ⇒ look-ahead check."""

    def __init__(self, m1=True, boom=False, **k):
        super().__init__(**k)
        self.m1, self.boom, self.asked = m1, boom, []

    def one(self):
        f = pd.concat([self.m15.assign(timestamp=self.m15["timestamp"] + pd.Timedelta(minutes=k)) for k in range(15)])
        return f.sort_values("timestamp").reset_index(drop=True)

    def index(self, sym, interval, days):
        if interval == "1minute":
            self.asked.append(days)
            if self.boom:
                raise L.EngineDataError(f"{sym} 1minute intraday HTTP 500 (test)")
            return self.one() if self.m1 else self.one().iloc[:0]
        return super().index(sym, interval, days)


@pytest.fixture
def fake_v22(monkeypatch):
    from decision3 import engine as E3
    seen = {}

    class FakeV22:
        def __init__(self, m15, df1m=None, daily_df=None, s=None, res=None, sealed=None, ltf=None, futures=None):
            seen.update(m15=m15, df1m=df1m, ltf=ltf, futures=futures)
            self.m15 = m15

        def decide(self, t):
            return {"bar_end": str(self.m15["bar_end"].iloc[t]), "decision": "wait"}
    monkeypatch.setattr(E3, "V22", FakeV22)
    return seen


NOW = pd.Timestamp("2030-03-25 10:07")                                    # 10:00 15M bar not closed; its 1m 10:00–10:06 are


def test_df1m_reaches_v22_and_never_after_the_decided_bar(fake_v22):
    f = Feed1m()
    r = L.compute("BANKNIFTY", f, NOW)
    m1, m15 = fake_v22["df1m"], fake_v22["m15"]
    assert m1 is not None and len(m1) and f.asked == [L.DEFAULTS["engine3_m15_days"]]   # 1m window = the 15M window
    last_end = pd.Timestamp(m15["bar_end"].iloc[-1])
    assert last_end == pd.Timestamp("2030-03-25 10:00")
    assert (m1["timestamp"] + pd.Timedelta(minutes=1) <= last_end).all()  # feed has later rows (10:00 … 15:29): none used
    assert m1["timestamp"].max() == pd.Timestamp("2030-03-25 09:59")
    assert m1["timestamp"].min() >= pd.Timestamp(m15["timestamp"].iloc[0])
    assert list(m1.columns) == ["timestamp", "open", "high", "low", "close"]
    assert r["m1"]["used"] and r["m1"]["m15_covered"] == r["m1"]["m15_bars"] == len(m15) and r["m1"]["note"] is None
    row = L.row_from_v22("BANKNIFTY", r, lambda: "x")
    assert json.loads(row["payload"])["m1"]["used"] is True


@pytest.mark.parametrize("feed,why", [(Feed1m(boom=True), "HTTP 500"), (Feed1m(m1=False), "1m candles मिळाले नाहीत"),
                                      (Feed(), "KeyError")])
def test_missing_1m_falls_back_to_no_1m_with_reason_not_a_data_error(fake_v22, feed, why, capsys):
    r = L.compute("BANKNIFTY", feed, NOW)                                 # no raise: 1m is not a required input
    assert fake_v22["df1m"] is None and fake_v22["futures"] is not None and r["decision"] == "wait"
    assert r["m1"]["used"] is False and r["m1"]["setting"] is True and r["m1"]["fallback"] and why in r["m1"]["note"]
    assert "1m शिवाय" in capsys.readouterr().out                           # logged
    row = L.row_from_v22("BANKNIFTY", r, lambda: "x")
    assert row["decision"] == "wait" and json.loads(row["payload"])["m1"]["fallback"] is True


def test_partial_1m_is_used_and_reported():
    f = Feed1m()
    m15 = L.closed_session_bars(f.m15, 15, NOW)
    full = f.one()
    late = full[full["timestamp"] >= pd.Timestamp("2030-03-25 09:45")]   # intraday lag: last closed 15M bar has no 1m yet
    f.one = lambda: full.drop(late.index)
    m1, info = L.load_m1(f, "BANKNIFTY", m15, NOW)
    assert m1 is not None and info["used"] and "शेवटच्या 15M bar चा 1m नाही" in info["note"]


@pytest.mark.parametrize("off", [False, "false", "0", "off"])
def test_setting_off_is_the_old_behaviour_and_does_not_fetch_1m(fake_v22, off):
    f = Feed1m()
    r = L.compute("BANKNIFTY", f, NOW, {"engine3_use_1m": off})
    assert fake_v22["df1m"] is None and f.asked == [] and r["m1"] == {"used": False, "setting": False, "note": r["m1"]["note"]}
    assert L.use_1m(None) is True and L.use_1m({"engine3_use_1m": "True"}) is True


def test_engine3_settings_from_dashboard_and_run_script_passes_them(monkeypatch):
    got = ES.engine3_settings("nifty", lambda strat, sym: {"engine3_use_1m": False, "lots": 2, "signal_source": "engine"})
    assert got == {"engine3_use_1m": False}

    def boom(*_a):
        raise RuntimeError("db down")
    assert ES.engine3_settings("NIFTY", boom) == {}                      # ⇒ engine3_live.DEFAULTS (1m on)
    import cloud_db
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS[ES.ENGINE3_SETTINGS_KEY]["engine3_use_1m"] is True
    from scripts import engine_signal_run as ESR
    seen = []
    monkeypatch.setattr(ES, "engine3_settings", lambda sym: {"engine3_use_1m": sym != "NIFTY"})

    def run3(sym, tok, now=None, dry_run=False, s=None, **k):
        seen.append((sym, s))
        return {"bar_ts": "2030-01-07 10:00:00", "decision": "wait", "skipped": "x"}
    monkeypatch.setattr(ES, "run3", run3)
    ESR.main(["--symbols", "NIFTY,BANKNIFTY", "--dry-run", "--force"], token_fn=lambda: "tok", market_fn=lambda: True,
             now=pd.Timestamp("2030-01-07 10:16"))
    assert seen == [("NIFTY", {"engine3_use_1m": False}), ("BANKNIFTY", {"engine3_use_1m": True})]


def test_m1_tag_in_run_log():
    from scripts import engine_signal_run as ESR
    tag = lambda m: ESR._m1_tag({"payload": json.dumps({"m1": m})})     # noqa: E731
    assert tag({"used": True, "m15_covered": 9, "m15_bars": 9, "note": None}) == " · 1m ✓ (9/9)"
    assert tag({"used": False, "setting": False}) == " · 1m off"
    assert "fallback" in tag({"used": False, "setting": True, "note": "x"}) and ESR._m1_tag({"payload": "{}"}) == ""


# ------------------------------------------------------------------------------------------------ UpstoxFeed 1m (fake HTTP)
def _fake_http(monkeypatch, today):
    import verify_opportunity_data_availability as V
    calls = []

    def window(token, key, interval, frm, to, expired=False):
        calls.append(("hist", interval, frm, to))
        rows, d = [], frm
        while d <= to:
            if d.weekday() < 5 and d < today:
                rows.append([f"{d}T09:15:00+05:30", 100.0, 101.0, 99.0, 100.5, 0, 0])
            d += dt.timedelta(days=1)
        return {"status": 200, "candles": rows, "error": None}

    def get(url, tok):
        calls.append(("intraday", url.rsplit("/", 2)[-2:]))
        return 200, {"data": {"candles": [[f"{today}T09:15:00+05:30", 1.0, 2.0, 0.5, 1.5, 0, 0]]}}, None
    monkeypatch.setattr(V, "fetch_candles_window", window)
    monkeypatch.setattr(V, "_get", get)
    return calls


def test_upstox_1m_history_once_per_day_intraday_every_cycle(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGINE3_CACHE_DIR", str(tmp_path))
    today = dt.date(2026, 10, 13)
    calls = _fake_http(monkeypatch, today)
    f = L.UpstoxFeed("tok", today)
    a = f.index("NIFTY", "1minute", 90)
    hist1 = [c for c in calls if c[0] == "hist"]
    assert len(hist1) == 4 and all(c[1] == "1minute" and c[3] < today and (c[3] - c[2]).days <= 28 for c in hist1)
    assert sum(c[0] == "intraday" for c in calls) == 1
    b = L.UpstoxFeed("tok", today).index("NIFTY", "1minute", 90)        # next cycle, same day
    assert len([c for c in calls if c[0] == "hist"]) == 4 and sum(c[0] == "intraday" for c in calls) == 2
    assert a.equals(b) and pd.Timestamp(f"{today} 09:15") in set(a["timestamp"])
    L.UpstoxFeed("tok", today + dt.timedelta(days=1)).index("NIFTY", "1minute", 90)   # new day ⇒ history again, old file removed
    assert len([c for c in calls if c[0] == "hist"]) >= 8                 # (+ the fake's gap-fill day)
    assert len([p for p in tmp_path.iterdir() if p.name.startswith("hist_")]) == 1


def test_upstox_15m_path_unchanged_no_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGINE3_CACHE_DIR", str(tmp_path))
    today = dt.date(2026, 10, 13)
    calls = _fake_http(monkeypatch, today)
    L.UpstoxFeed("tok", today).index("NIFTY", "15minute", 90)
    L.UpstoxFeed("tok", today).index("NIFTY", "15minute", 90)
    assert len([c for c in calls if c[0] == "hist"]) == 8 and not list(tmp_path.iterdir())


def test_upstox_1m_history_not_cached_while_previous_day_missing(monkeypatch, tmp_path):
    """Upstox historical without yesterday yet (early / holiday) ⇒ no cache ⇒ next cycle fetches history again (self-heals)."""
    monkeypatch.setenv("ENGINE3_CACHE_DIR", str(tmp_path))
    today = dt.date(2026, 10, 13)
    calls = _fake_http(monkeypatch, dt.date(2026, 10, 12))               # fake has nothing on / after 12 Oct (= yesterday)
    L.UpstoxFeed("tok", today).index("NIFTY", "1minute", 90)
    n = len([c for c in calls if c[0] == "hist"])
    L.UpstoxFeed("tok", today).index("NIFTY", "1minute", 90)
    assert len([c for c in calls if c[0] == "hist"]) == 2 * n and not list(tmp_path.iterdir())
