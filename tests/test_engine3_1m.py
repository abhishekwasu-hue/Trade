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
    assert L.use_1m({"engine3_use_1m": None}) is True and L.use_1m({"engine3_use_1m": ""}) is True   # रिकामं ⇒ default ON
    assert L.use_1m({"engine3_use_1m": " "}) is True and L.use_1m({"engine3_use_1m": "FALSE"}) is False


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
    assert tag({"used": True, "m15_covered": 9, "m15_bars": 9, "note": None}) == " · 1m ✓ (9/9)"      # old row (no m15_complete)
    assert tag({"used": True, "m15_covered": 9, "m15_complete": 7, "m15_bars": 9, "note": None}) == " · 1m ✓ (complete 7/9)"
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


# ------------------------------------------------------------------------------------------------ review #327
def _hist_1m(calls):
    return [c for c in calls if c[0] == "hist" and c[1] == "1minute"]


def test_upstox_1m_history_cached_after_a_weekday_holiday(monkeypatch, tmp_path):
    """Monday holiday: history ends Friday. Expected last day = the 15M history's last session (Friday), not the previous weekday
    (Monday) ⇒ the cache fills on the first cycle; the next cycles fetch only the intraday (not 90 days of 1m every cycle)."""
    import verify_opportunity_data_availability as V
    monkeypatch.setenv("ENGINE3_CACHE_DIR", str(tmp_path))
    today, holiday = dt.date(2026, 10, 13), dt.date(2026, 10, 12)          # Tue; Mon = holiday (no candles)
    calls = _fake_http(monkeypatch, today)
    window = V.fetch_candles_window

    def no_holiday(token, key, interval, frm, to, expired=False):
        r = window(token, key, interval, frm, to)
        return {**r, "candles": [c for c in r["candles"] if not c[0].startswith(str(holiday))]}
    monkeypatch.setattr(V, "fetch_candles_window", no_holiday)
    for _cycle in range(3):                                                # run3 ⇒ new feed per cycle; 15M first (build_inputs), then 1m
        f = L.UpstoxFeed("tok", today)
        f.index("NIFTY", "15minute", 90)
        assert f.last_session == dt.date(2026, 10, 9)                       # Friday
        f.index("NIFTY", "1minute", 90)
    first = len(_hist_1m(calls))
    assert first == 5                                                       # cycle 1 only: 4 chunks + 1 gap-fill (holiday ⇒ empty)
    assert len([p for p in tmp_path.iterdir() if p.name.startswith("hist_")]) == 1
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert sum(c[0] == "intraday" and c[1][0] == "minutes" and c[1][1] == "1" for c in calls) == 3


def test_upstox_1m_cache_refetches_when_15m_gets_a_newer_day(monkeypatch, tmp_path):
    """15M history later shows a newer session than the cached 1m history ⇒ new cache key ⇒ 1m history fetched again."""
    monkeypatch.setenv("ENGINE3_CACHE_DIR", str(tmp_path))
    today = dt.date(2026, 10, 13)
    calls = _fake_http(monkeypatch, today)
    f = L.UpstoxFeed("tok", today)
    f.last_session = dt.date(2026, 10, 9)
    f.index("NIFTY", "1minute", 90)
    n = len(_hist_1m(calls))
    g = L.UpstoxFeed("tok", today)
    g.last_session = dt.date(2026, 10, 12)
    g.index("NIFTY", "1minute", 90)
    assert len(_hist_1m(calls)) == 2 * n and len([p for p in tmp_path.iterdir() if p.name.startswith("hist_")]) == 1


@pytest.fixture
def fake_v22_levels(monkeypatch):
    """V22 stub with levels.snapshot + swings2-like res stream (m1_status per bar) — records df1m per build."""
    from decision3 import engine as E3
    seen = {"df1m": [], "status": "complete", "boom": False}

    class FakeV22:
        def __init__(self, m15, df1m=None, daily_df=None, s=None, res=None, sealed=None, ltf=None, futures=None):
            seen["df1m"].append(df1m)
            if df1m is not None and seen["boom"]:
                raise ValueError("swings2 1m join failed (test)")
            self.m15 = m15
            self.res = {"stream": [{"ts": str(t), "m1_status": seen["status"] if df1m is not None else "absent"}
                                   for t in m15["timestamp"]]}
            self.levels = type("LV", (), {"snapshot": lambda _s, t: [{"role": "resistance", "lo": 1.0, "hi": 2.0,
                                                                      "state": "ACTIVE", "m1": df1m is not None}]})()

        def decide(self, t):
            return {"bar_end": str(self.m15["bar_end"].iloc[t]), "decision": "wait"}
    monkeypatch.setattr(E3, "V22", FakeV22)
    return seen


PRE = pd.Timestamp("2030-03-25 09:00")                                     # pre-open: yesterday's bars only


def test_watched_levels_passes_1m_to_v22_same_as_live(fake_v22_levels):
    f = Feed1m()
    got = L.watched_levels("BANKNIFTY", f, PRE)
    m1 = fake_v22_levels["df1m"][-1]
    assert m1 is not None and len(m1) and f.asked == [L.DEFAULTS["engine3_m15_days"]] and got[0]["m1"] is True
    assert (m1["timestamp"] + pd.Timedelta(minutes=1) <= PRE).all()      # closed 1m only (no look-ahead)


@pytest.mark.parametrize("off", [False, "false"])
def test_watched_levels_setting_off_does_not_fetch_1m(fake_v22_levels, off):
    f = Feed1m()
    got = L.watched_levels("BANKNIFTY", f, PRE, {"engine3_use_1m": off})
    assert fake_v22_levels["df1m"] == [None] and f.asked == [] and got[0]["m1"] is False


def test_watched_levels_v22_error_with_1m_retries_without(fake_v22_levels, capsys):
    fake_v22_levels["boom"] = True
    got = L.watched_levels("BANKNIFTY", Feed1m(), PRE)
    assert [x is None for x in fake_v22_levels["df1m"]] == [False, True] and got[0]["m1"] is False
    assert "V22 1m सह त्रुटी" in capsys.readouterr().out


def test_preopen_and_summary_pass_engine3_settings_to_watched_levels(monkeypatch):
    import inspect as _inspect
    import cloud_db
    from scripts import level_gate_preopen as PO
    from scripts import paper_daily_summary as S
    assert "ES.engine3_settings(sym)" in _inspect.getsource(PO.main)        # pre-open engine_areas ⇒ dashboard engine3_* settings
    seen = []
    monkeypatch.setattr(cloud_db, "get_strategy_settings", lambda k, s: {"signal_source": "engine", "engine3_use_1m": "false", "lots": 1})
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda x: "t")
    monkeypatch.setattr(L, "UpstoxFeed", lambda tok, today=None: object())
    monkeypatch.setattr(L, "watched_levels", lambda sym, feed, now, s=None: seen.append(s) or [])
    S.default_zones("NIFTY")
    assert seen == [{"engine3_use_1m": "false"}]


def test_complete_count_reported_and_mismatch_warned(fake_v22_levels, capsys):
    r = L.compute("BANKNIFTY", Feed1m(), NOW)
    assert r["m1"]["m15_complete"] == r["m1"]["m15_bars"] and r["m1"]["note"] is None
    fake_v22_levels["status"] = "partial"                                  # 1m rows present, highs / lows never match the 15M
    r = L.compute("BANKNIFTY", Feed1m(), NOW)
    assert r["m1"]["used"] and r["m1"]["rows"] > 0 and r["m1"]["m15_complete"] == 0
    assert "complete 0/" in r["m1"]["note"] and "जुळत नाहीत" in capsys.readouterr().out
    from scripts import engine_signal_run as ESR
    assert ESR._m1_tag(L.row_from_v22("BANKNIFTY", r, lambda: "x")).startswith(" · 1m ✓ (complete 0/")


def test_v22_error_with_1m_retries_once_without_1m(fake_v22_levels, capsys):
    fake_v22_levels["boom"] = True
    r = L.compute("BANKNIFTY", Feed1m(), NOW)                              # no raise: 1m must never fail the cycle closed
    assert [x is None for x in fake_v22_levels["df1m"]] == [False, True] and r["decision"] == "wait"
    assert r["m1"]["used"] is False and r["m1"]["fallback"] is True and "ValueError" in r["m1"]["note"]
    assert "V22 1m सह त्रुटी" in capsys.readouterr().out


def test_cache_tmp_name_is_per_process():
    src = open(L.__file__, encoding="utf-8").read()
    assert src.count('f"{p}.{os.getpid()}.tmp"') == 2 and 'p + ".tmp"' not in src


def test_run3_prunes_old_cache_files(monkeypatch, tmp_path, fake_v22):
    import os
    import time
    monkeypatch.setenv("ENGINE3_CACHE_DIR", str(tmp_path))
    old, new = tmp_path / "hist_old.pkl", tmp_path / "fold_new.pkl"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    t = time.time() - (L.DEFAULTS["engine3_cache_keep_days"] + 1) * 86400
    os.utime(old, (t, t))
    monkeypatch.setattr(L, "UpstoxFeed", lambda tok, today=None: Feed1m())
    ES.run3("BANKNIFTY", "tok", now=NOW, dry_run=True)
    assert not old.exists() and new.exists()


def test_dashboard_checkbox_uses_the_same_parser():
    import os
    src = open(os.path.join(os.path.dirname(L.__file__), "page_bot_dynamic_sr_algo.py"), encoding="utf-8").read()
    assert 'bool(settings.get("engine3_use_1m"' not in src and '_L3.use_1m({"engine3_use_1m": settings.get("engine3_use_1m")})' in src
