"""scripts/diagnose_day_export.py — read-only VPS day export. Synthetic SQLite + fake feed + fake V22 only (no real data, no network)."""
import datetime as dt
import gzip
import hashlib
import importlib.util
import inspect
import json
import os
import sqlite3

import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("diagnose_day_export", os.path.join(HERE, "..", "scripts", "diagnose_day_export.py"))
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)

DAY = "2030-03-25"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class FakeFeed:
    """60 sessions of flat 15M / 5M / 1m bars ending on DAY, plus Daily; FUT 5M with volume."""

    def __init__(self, *_a, **_k):
        days = pd.bdate_range(end=DAY, periods=60)
        self.m15 = pd.DataFrame({"timestamp": [d + pd.Timedelta(minutes=555 + 15 * k) for d in days for k in range(25)],
                                 "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 0.0})
        self.today = pd.Timestamp(DAY).date()
        self.calls = []

    def _sub(self, step):
        f = pd.concat([self.m15.assign(timestamp=self.m15["timestamp"] + pd.Timedelta(minutes=step * k)) for k in range(15 // step)])
        return f.sort_values("timestamp").reset_index(drop=True)

    def index(self, sym, interval, days):
        self.calls.append(interval)
        if interval == "day":
            return pd.DataFrame({"timestamp": pd.bdate_range(end=DAY, periods=300), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
                                 "volume": 0.0})
        return {"15minute": self.m15, "5minute": self._sub(5), "1minute": self._sub(1)}[interval]

    def futures(self, sym, interval, days):
        raise AssertionError("the export never calls feed.futures (its FUT search) — the probe did that once")

    def _series(self, key, interval, days, contract=None):
        assert key == "NSE_FO|999" and interval == "5minute"
        return self._sub(5).assign(volume=10.0, contract=contract)


@pytest.fixture
def dbs(tmp_path, monkeypatch):
    """Synthetic engine / vision / paper / live_trades DBs (schemas as on the VPS) via the modules' own env vars."""
    import config
    eng, vis, pj, lt = (str(tmp_path / n) for n in ("engine.db", "vision.db", "paper.db", "hist.db"))
    with sqlite3.connect(eng) as c:
        import engine_signal as ES
        c.executescript(ES.SCHEMA)
        for hm, dec in (("09:30", "wait"), ("09:45", "setup"), ("10:00", "wait")):
            c.execute("INSERT INTO engine_signals (symbol, bar_ts, computed_at, decision, gate, direction, payload) VALUES (?,?,?,?,?,?,?)",
                      ("NIFTY", f"{DAY} {hm}:00", f"{DAY} {hm}:40", dec, "⑥", -1, json.dumps({"engine": "decision3", "decision": dec})))
        c.execute("INSERT INTO engine_signals (symbol, bar_ts, decision) VALUES ('NIFTY', '2030-03-22 15:00:00', 'wait')")   # other day
    with sqlite3.connect(vis) as c:
        from vision import store as VS
        c.executescript(VS.SCHEMA)
        c.execute("INSERT INTO vision_signals (signal_id, bot, symbol, trading_mode, mode, signal_ts, created_at, status, setup_json) "
                  "VALUES ('s1', 'srv2_momentum_reversal', 'NIFTY', 'PAPER', 'veto_then_confirm', ?, ?, 'REJECTED', '{}')",
                  (f"{DAY} 09:46", f"{DAY} 09:46:10"))
        c.execute("INSERT INTO vision_events VALUES (?, 's1', 'telegram', 'Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefgh')",
                  (f"{DAY} 09:46:20",))
        c.execute("INSERT INTO vision_settings VALUES ('srv2_momentum_reversal', '{\"vision_mode\": \"veto_then_confirm\"}', NULL, NULL)")
    with sqlite3.connect(pj) as c:
        from paper import journal as PJ
        c.executescript(PJ.SCHEMA)
    with sqlite3.connect(lt) as c:
        c.execute("CREATE TABLE live_trades (trade_id TEXT, trade_date TEXT, symbol TEXT, mode TEXT, short_order_id TEXT, entry_time TEXT)")
        c.execute("INSERT INTO live_trades VALUES ('p1', ?, 'NIFTY', 'PAPER', 'o1', ?)", (DAY, f"{DAY} 09:50"))
        c.execute("INSERT INTO live_trades VALUES ('l1', ?, 'NIFTY', 'LIVE', 'o2', ?)", (DAY, f"{DAY} 09:50"))
    monkeypatch.setenv("ENGINE_SIGNAL_DB", eng)
    monkeypatch.setenv("VISION_DB_PATH", vis)
    monkeypatch.setenv("PAPER_JOURNAL_DB", pj)
    monkeypatch.setattr(config, "DB_PATH", lt)
    return [eng, vis, pj, lt]


SEARCH = {"code": 401}


@pytest.fixture
def fake_engine(monkeypatch, tmp_path):
    """No network, no real V22: fake Upstox feed + token + a fake V22 with the live constructor signature."""
    import cloud_db
    import engine3_live as L
    from decision3 import engine as E3

    class FakeV22:
        def __init__(self, m15, df1m=None, daily_df=None, s=None, res=None, sealed=None, ltf=None, futures=None):
            self.m15, self.kw = m15.reset_index(drop=True), {"ltf": ltf is not None, "futures": futures is not None, "m1": df1m is not None}

        def decide(self, t):
            return {"bar_end": str(self.m15["bar_end"].iloc[t]), "decision": "setup" if str(self.m15["bar_end"].iloc[t])[11:16] == "09:45"
                    else "wait", "active_levels": [], "checklist": {"①": [True, "x"], "⑥": [False, "waiting"]}, "kw": self.kw}
    monkeypatch.setattr(E3, "V22", FakeV22)
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *_a: "T" * 60)
    monkeypatch.setattr(cloud_db, "get_strategy_settings", lambda st, sym: {"engine3_use_1m": True, "api_token": "zzz", "x": 1})
    monkeypatch.setattr(L, "UpstoxFeed", FakeFeed)
    monkeypatch.setattr(L, "resolve_future", lambda *a: (_ for _ in ()).throw(AssertionError("resolve_future must not be called")))
    import verify_opportunity_data_availability as V
    calls = []

    def get(url, tok, params=None, **k):
        calls.append(url)
        if url.endswith("/instruments/search"):
            if SEARCH["code"] == 401:
                return 401, {"status": "error", "errors": [{"errorCode": "UDAPI1000", "message": "x"}]}, '{"status":"error"}'
            return 200, {"data": [{"trading_symbol": "NIFTY FUT 28 MAR 30", "instrument_key": "NSE_FO|999", "expiry": "2030-03-28"}]}, None
        return 200, {"data": {"candles": [[f"{DAY}T09:15:00+05:30", 1, 2, 0.5, 1.5, 0, 0]]}}, None
    monkeypatch.setattr(V, "_get", get)
    monkeypatch.setattr(V, "fetch_candles_window", lambda *a, **k: {"status": 200, "candles": [[DAY, 1, 2, 0.5, 1.5, 0, 0]], "error": None})
    (tmp_path / "data").mkdir()
    fut = FakeFeed()._sub(5).assign(volume=10.0, oi=0.0, contract="NIFTY FUT 28 MAR 30")
    fut.to_parquet(tmp_path / "data" / "oe_futures_5min_NIFTY.parquet", index=False)
    SEARCH["code"] = 401
    return calls


def run(tmp_path, *extra):
    out = tmp_path / "out"
    rc = D.main(["--symbol", "NIFTY", "--day", DAY, "--now", "10:20", "--out-dir", str(out), "--repo", str(tmp_path), "--no-master",
                 *extra],
                clock=lambda: dt.datetime(2030, 3, 25, 16, 0))
    return rc, out


def test_redaction_never_leaks_secrets(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "secretvalue123")
    D.load_env_secrets()
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
    s = D.redact(f"tok secretvalue123 | Authorization: Bearer {jwt} | token=abc123 | https://api.telegram.org/bot123456:AAH{'x' * 30}/send")
    assert "secretvalue123" not in s and jwt not in s and "abc123" not in s and "xxxxxxxxxx" not in s
    assert D.redact("NIFTY 09:30 wait gate ⑥") == "NIFTY 09:30 wait gate ⑥"
    assert D.secret_name("api_key") and D.secret_name("upstox_token") and not D.secret_name("engine3_use_1m")


def test_effective_now_and_bars():
    late = lambda: dt.datetime(2030, 3, 25, 18, 0)                         # noqa: E731
    assert D.effective_now(DAY, None, late) == dt.datetime(2030, 3, 25, 15, 30)       # after close ⇒ 15:30
    assert D.effective_now(DAY, None, lambda: dt.datetime(2030, 3, 25, 11, 7, 33)) == dt.datetime(2030, 3, 25, 11, 7)   # live ⇒ now
    assert D.effective_now(DAY, "12:00", late) == dt.datetime(2030, 3, 25, 12, 0)
    assert D.effective_now(DAY, None, lambda: dt.datetime(2030, 3, 27, 9, 0)) == dt.datetime(2030, 3, 25, 15, 30)
    with pytest.raises(ValueError):
        D.effective_now(DAY, None, lambda: dt.datetime(2030, 3, 24, 9, 0))
    b = D.replay_bars(DAY, dt.datetime(2030, 3, 25, 11, 7))
    assert [x.strftime("%H:%M") for x in (b[0], b[-1])] == ["09:30", "11:00"] and len(b) == 7
    assert D.replay_bars(DAY, dt.datetime(2030, 3, 25, 15, 30))[-1].strftime("%H:%M") == "15:30"


def test_cut_feed_never_serves_a_bar_closed_after_now():
    f = FakeFeed()
    raw = {("index", "NIFTY", "1minute", 90): f.index("NIFTY", "1minute", 90), ("index", "NIFTY", "day", 10): f.index("NIFTY", "day", 10)}
    now = pd.Timestamp(f"{DAY} 09:46")
    c = D.CutFeed(raw, now)
    m1 = c.index("NIFTY", "1minute", 90)
    assert (m1["timestamp"] + pd.Timedelta(minutes=1) <= now).all() and m1["timestamp"].max() == pd.Timestamp(f"{DAY} 09:45")
    assert c.index("NIFTY", "day", 10)["timestamp"].max() <= now.normalize()
    with pytest.raises(KeyError):                                         # never a network call in the replay
        c.index("NIFTY", "5minute", 10)


def test_capture_keeps_the_v22_signature_so_the_live_kwargs_are_the_same():
    import engine3_live as L
    from decision3 import engine as E3
    before = L.v22_kwargs()
    with D.Capture():
        assert L.v22_kwargs() == before and "ltf" in before
    assert E3.V22.__name__ == "V22" and inspect.isclass(E3.V22)


def test_end_to_end_read_only_export_and_replay(tmp_path, dbs, fake_engine):
    before = {p: sha(p) for p in dbs}
    rc, out = run(tmp_path)
    assert rc == 0
    assert {p: sha(p) for p in dbs} == before                             # nothing written to any bot DB
    eng = json.load(open(out / "live" / "engine_signals.json"))
    assert [r["bar_ts"][11:16] for r in eng["rows"]] == ["09:30", "09:45", "10:00"] and eng["rows"][1]["payload_json"]["decision"] == "setup"
    vis = json.load(open(out / "live" / "vision.json"))
    assert vis["signals"][0]["setup_json"] == "{}" and "eyJ" not in json.dumps(vis)
    lt = json.load(open(out / "live" / "live_trades_paper.json"))
    assert [r["trade_id"] for r in lt["rows"]] == ["p1"] and "short_order_id" not in lt["rows"][0]
    st = json.load(open(out / "meta" / "settings.json"))
    assert "api_token" not in json.dumps(st) and st["vision"]["srv2_momentum_reversal"]["effective"]["vision_mode"] == "veto_then_confirm"
    meta = json.load(open(out / "inputs" / "meta.json"))
    assert meta["errors"] == {} and "T" * 60 not in open(out / "inputs" / "meta.json").read()
    for k in ("m15", "daily", "ltf5", "fut5", "m1", "h1"):
        assert (out / "inputs" / f"engine_NIFTY_{k}.csv.gz").exists()
    m15 = pd.read_csv(out / "inputs" / "engine_NIFTY_m15.csv.gz")
    assert m15["bar_end"].max() == f"{DAY} 10:15:00"                      # --now 10:20 ⇒ nothing later
    cmp_ = json.load(open(out / "replay" / "compare.json"))
    assert [b["bar_ts"][11:16] for b in cmp_["bars"]] == ["09:30", "09:45", "10:00", "10:15"]
    assert all("decision" not in b["diff"] for b in cmp_["bars"][:3]) and cmp_["bars"][1]["diff"]["direction"] == [-1, None]
    assert cmp_["bars"][3]["live"] is None and cmp_["bars"][3]["diff"] is None
    bar = json.load(gzip.open(out / "replay" / "bars" / "NIFTY_0945.json.gz", "rt"))
    assert bar["row"]["decision"] == "setup" and bar["decide"]["kw"] == {"ltf": True, "futures": True, "m1": True}
    assert bar["mode"] == "live_path"
    probe = json.load(open(out / "live" / "upstox_probe.json"))
    assert probe["fut_search"]["status"] == 401 and "UDAPI1000" in json.dumps(probe["fut_search"]["body"])
    assert probe["spot_history_day"]["status"] == 200 and meta["sources"]["fut5"]["source"] == "local collector parquet"
    assert bar["payload_full"]["engine"] == "decision3"
    s = json.load(open(out / "SUMMARY_replay.json"))
    assert {k: s["replay"][k] for k in ("bars", "errors", "decision_mismatches")} == {"bars": 4, "errors": 0, "decision_mismatches": 0}
    assert s["probe"]["fut_search"] == 401 and s["fut_source"] == "local collector parquet"
    rc2, _ = run(tmp_path)                                                # never overwrites a non-empty folder
    assert rc2 == 2


def test_sections_are_independent(tmp_path, dbs, fake_engine, monkeypatch):
    import engine3_live as L
    monkeypatch.setattr(L, "build_inputs", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    os.remove(dbs[1])                                                     # vision db missing
    rc, out = run(tmp_path, "--skip", "code,logs")
    assert rc == 0                                                        # live engine rows exported ⇒ 0
    s = json.load(open(out / "SUMMARY_replay.json"))["sections"]
    assert s["3a_engine_rows"]["ok"] and not s["3b_vision"]["ok"] and s["3d_live_trades"]["ok"] and not s["5_replay"]["ok"]
    assert not os.path.exists(dbs[1])                                     # read-only open never creates a db


def test_pick_out_dir_never_reuses_a_folder(tmp_path):
    p1 = D.pick_out_dir(str(tmp_path), DAY)
    os.makedirs(p1)
    p2 = D.pick_out_dir(str(tmp_path), DAY)
    assert p1.endswith("/vps") and p2.endswith("/vps_run2")


def test_search_ok_uses_the_engine_contract_once(tmp_path, dbs, fake_engine):
    SEARCH["code"] = 200
    rc, out = run(tmp_path, "--bars", "09:45")
    assert rc == 0 and sum(u.endswith("/instruments/search") for u in fake_engine) == 1   # the search is called exactly once
    meta = json.load(open(out / "inputs" / "meta.json"))
    assert meta["sources"]["fut5"]["source"].startswith("upstox_search")
    assert json.load(open(out / "SUMMARY_replay.json"))["replay"]["bars"] == 1


def test_no_fut_anywhere_replays_the_reading_without_fut(tmp_path, dbs, fake_engine):
    os.remove(tmp_path / "data" / "oe_futures_5min_NIFTY.parquet")
    rc, out = run(tmp_path, "--bars", "09:45")
    assert rc == 0
    meta = json.load(open(out / "inputs" / "meta.json"))
    assert meta["sources"]["fut5"]["source"] is None and "FutVolumeMissing" in meta["errors"]["build_inputs"]
    assert (out / "inputs" / "engine_NIFTY_m15.csv.gz").exists() and (out / "inputs" / "engine_NIFTY_ltf5.csv.gz").exists()
    bar = json.load(gzip.open(out / "replay" / "bars" / "NIFTY_0945.json.gz", "rt"))
    assert bar["mode"].startswith("no_fut_reading") and bar["decide"]["kw"]["futures"] is False and bar["decide"]["kw"]["ltf"] is True
    assert "REPLAY WITHOUT FUT" in bar["payload_full"]["volume_note"]
