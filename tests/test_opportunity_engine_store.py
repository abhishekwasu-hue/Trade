"""tests/test_opportunity_engine_store.py -- Supabase store (mocked connection): merge-safe, फक्त स्वतःचे tables, python मूल्ये; refresh pipeline, scripts, adapter."""
import datetime
import re

import numpy as np
import pandas as pd
import pytest

from opportunity_engine import refresh as RF
from opportunity_engine import store as ST
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import Context, TFState
from opportunity_engine.detectors.base import Candidate
from strategies import STRATEGY_REGISTRY
from strategies.base import Direction, MarketSnapshot
from strategies.opportunity_engine import OpportunityEngineStrategy

NOW = pd.Timestamp("2025-01-08 10:30")


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 1

    def execute(self, sql, params=None):
        if self.conn.fail_on and self.conn.fail_on in sql:
            raise RuntimeError("boom")
        self.conn.executed.append((sql, params))

    def fetchall(self):
        return self.conn.rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, rows=None, fail_on=None):
        self.executed, self.rows, self.fail_on = [], rows or [], fail_on
        self.committed = self.rolled_back = self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def factory(conn):
    return lambda: conn


def sql_text(conn):
    return " ".join(s for s, _ in conn.executed)


def level(**kw):
    base = {"level_id": "abc123", "tf": "1h", "kind": "DEMAND", "source": "DISPLACEMENT", "low": np.float64(24000.5), "high": np.float64(24020.5),
            "core_low": np.float64(24005.0), "core_high": np.float64(24015.0), "freshness": "FRESH", "status": "ACTIVE", "role": "SUPPORT", "quality_grade": "A",
            "quality_score": np.float64(0.82), "origin_type": "ORIGIN_BOS", "mtf_count": np.int64(3), "touches": np.int64(0), "formed_at": pd.Timestamp("2025-01-07 11:15"),
            "reject_reason": None}
    base.update(kw)
    return base


# ---- store ---------------------------------------------------------------------------------------------------------------------------------
def test_ensure_tables_creates_only_our_three_tables():
    conn = FakeConn()
    assert ST.ensure_tables(factory(conn)) is True and conn.committed and conn.closed
    text = sql_text(conn)
    assert text.count("CREATE TABLE IF NOT EXISTS") == 3
    for t in (ST.STATE_TABLE, ST.EVENTS_TABLE, ST.ZONES_TABLE):
        assert t in text
    assert not re.search(r"\bmarket_zones\b", text)


def test_save_state_uses_upsert_with_pure_python_values():
    conn = FakeConn()
    snap = {"tf": "1h", "trend_state": "UPTREND", "protected_level": np.float64(24100.0), "last_sh": np.float64(24300.0), "last_sl": None,
            "range_high": None, "range_low": float("nan"), "ref_range": np.float64(35.5), "updated_at": pd.Timestamp("2025-01-08 10:15")}
    assert ST.save_structure_state("NIFTY", [snap], factory(conn)) is True
    sql, params = conn.executed[0]
    assert "ON CONFLICT (symbol, tf) DO UPDATE" in sql and "market_zones" not in sql
    assert params[:3] == ("NIFTY", "1h", "UPTREND")
    assert all(type(p) in (str, float, type(None), datetime.datetime) for p in params), [type(p) for p in params]
    assert params[6] is None and params[7] is None                      # NaN => None
    assert ST.save_structure_state("NIFTY", [], factory(FakeConn())) is False


def test_append_events_filters_types_dedupes_by_key_and_serialises_details():
    events = [
        {"tf": "1h", "time": pd.Timestamp("2025-01-08 10:15"), "type": "CHOCH", "price": np.float64(24100.0), "bar_idx": 5, "state": "UPTREND_WEAK", "from_state": "UPTREND",
         "to_state": "UPTREND_WEAK", "protected_broken": np.float64(24100.0)},
        {"tf": "1h", "time": pd.Timestamp("2025-01-08 10:15"), "type": "SWING", "price": 1.0, "bar_idx": 4, "state": "x"},                  # साठवत नाही
        {"tf": "1h", "time": pd.Timestamp("2025-01-08 10:15"), "type": "CHOCH", "price": 24100.0, "bar_idx": 99, "state": "UPTREND_WEAK"},       # bar_idx वेगळा, तरी तोच key
    ]
    rows = ST.event_rows("NIFTY", events)
    assert len(rows) == 2 and rows[0][0] == rows[1][0] and rows[0][4] == "CHOCH"
    conn = FakeConn()
    assert ST.append_events("NIFTY", events, factory(conn)) == 2
    sql, params = conn.executed[0]
    assert "ON CONFLICT (event_key) DO NOTHING" in sql and "market_zones" not in sql
    assert '"to_state": "UPTREND_WEAK"' in params[6] and isinstance(params[5], float)
    assert ST.append_events("NIFTY", [{"tf": "1h", "time": NOW, "type": "SWING", "price": 1}], factory(FakeConn())) == 0


def test_save_zones_upserts_prunes_only_own_table_and_never_on_empty():
    conn = FakeConn()
    assert ST.save_zones("NIFTY", [level(), level(level_id="def456", mtf_count=2)], factory(conn)) is True
    upserts = [(s, p) for s, p in conn.executed if s.lstrip().startswith("INSERT")]
    assert len(upserts) == 2 and all("ON CONFLICT (symbol, level_id)" in s for s, _ in upserts)
    for _, params in upserts:
        assert all(type(p) in (str, float, int, type(None), datetime.datetime) for p in params), [type(p) for p in params]
    delete_sql, delete_params = conn.executed[-1]
    assert delete_sql.startswith("DELETE FROM opportunity_zones") and delete_params == ("NIFTY", ["abc123", "def456"])
    assert not re.search(r"\bmarket_zones\b", sql_text(conn))
    empty = FakeConn()
    assert ST.save_zones("NIFTY", [], factory(empty)) is False and empty.executed == []         # रिकामी गणना जुना निकाल पुसत नाही
    assert ST.save_zones("NIFTY", [level(level_id=None)], factory(FakeConn())) is False


def test_failures_never_raise_and_roll_back():
    assert ST.ensure_tables(lambda: None) is False
    conn = FakeConn(fail_on="INSERT")
    assert ST.save_zones("NIFTY", [level()], factory(conn)) is False and conn.rolled_back and conn.closed
    assert ST.load_zones("NIFTY", lambda: None) is None
    bad = FakeConn(fail_on="SELECT")
    assert ST.load_state("NIFTY", factory(bad)) is None


def test_loads_return_dataframes():
    state = FakeConn(rows=[("NIFTY", "1h", "UPTREND", 24100.0, 24300.0, 24050.0, None, None, 35.5, NOW)])
    df = ST.load_state("NIFTY", factory(state))
    assert list(df.columns) == ST.STATE_COLS and df.iloc[0]["trend_state"] == "UPTREND" and "WHERE symbol = %s" in state.executed[0][0]
    ev = ST.load_events("NIFTY", 5, factory(FakeConn(rows=[])))
    assert list(ev.columns)[:4] == ["symbol", "tf", "event_time", "event_type"] and ev.empty


def test_zone_transition_events():
    old = pd.DataFrame([{"level_id": "a", "status": "ACTIVE", "gap_status": None}, {"level_id": "b", "status": "ACTIVE", "gap_status": None},
                        {"level_id": "g", "status": "ACTIVE", "gap_status": "PARTIAL"}])
    new = [level(level_id="a", status="MITIGATED"), level(level_id="b", status="BROKEN"), level(level_id="c"),
           level(level_id="g", kind="GAP", gap_status="FILLED", status="ACTIVE")]
    types = {(e["level_id"], e["type"]) for e in ST.zone_transition_events("NIFTY", old, new, NOW)}
    assert types == {("a", "ZONE_MITIGATED"), ("b", "ZONE_BROKEN"), ("c", "ZONE_FORMED"), ("g", "GAP_FILLED")}
    assert ST.zone_transition_events("NIFTY", None, new, NOW) == [] and ST.zone_transition_events("NIFTY", pd.DataFrame(), new, NOW) == []
    again = ST.zone_transition_events("NIFTY", pd.DataFrame([{"level_id": "a", "status": "MITIGATED", "gap_status": None}]), [level(level_id="a", status="MITIGATED")], NOW)
    assert again == []


# ---- refresh pipeline ----------------------------------------------------------------------------------------------------------------------------
def fine_5m(days=60, seed=5):
    rng = np.random.default_rng(seed)
    ds = pd.bdate_range("2024-10-01", periods=days)
    ts = pd.DatetimeIndex([d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=5 * k) for d in ds for k in range(75)])
    close = 24000 + np.cumsum(rng.normal(0, 4.0, len(ts))) + 250 * np.sin(np.arange(len(ts)) / 700.0)
    df = pd.DataFrame({"timestamp": ts, "open": close - 0.5, "high": close + 3.0, "low": close - 3.0, "close": close, "volume": 1000})
    daily = df.assign(d=df["timestamp"].dt.normalize()).groupby("d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                                                        volume=("volume", "sum")).reset_index().rename(columns={"d": "timestamp"})
    return df, daily


class FakeStore:
    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def ensure_tables(self, cf=None):
        self.calls.append("ensure")
        return self.ok

    def load_zones(self, symbol, cf=None):
        self.calls.append("load_zones")
        return pd.DataFrame()

    def save_structure_state(self, symbol, states, cf=None):
        self.calls.append(("state", [s["tf"] for s in states]))
        return True

    def save_zones(self, symbol, zones, cf=None):
        self.calls.append(("zones", len(zones)))
        return True

    def append_events(self, symbol, events, cf=None):
        self.calls.append(("events", len(events)))
        return len(events)


def fake_fetch(df5, daily, failed=False):
    def fetch(token, symbol, interval, lookback_days):
        d = (df5 if interval == "5minute" else daily).copy()
        if failed:
            d.attrs["failed_chunks"] = 2
        return d
    return fetch


NOW_LIVE = pd.Timestamp("2024-12-31 16:00")


def test_compute_snapshot_and_brief_text():
    df5, daily = fine_5m()
    snap = RF.compute_snapshot(df5, daily, "NIFTY", now=NOW_LIVE)
    assert snap.bias.label and snap.context.price == pytest.approx(snap.price) and "5m" in snap.frames and snap.levels
    text = RF.brief_text(snap)
    assert "NIFTY" in text and "Bias:" in text and "कुठलाही trade होत नाही" in text and "Daily" in text
    with pytest.raises(ValueError):
        RF.compute_snapshot(pd.DataFrame(columns=df5.columns), daily, "NIFTY", now=NOW_LIVE)


def test_refresh_symbol_stores_state_zones_events_and_sends_brief_only_when_asked():
    df5, daily = fine_5m()
    store, sent = FakeStore(), []
    ok, msg = RF.refresh_symbol("NIFTY", "tok", fake_fetch(df5, daily), store_mod=store, now=NOW_LIVE, notify=sent.append, send_brief=True)
    assert ok and "bias" in msg
    kinds = [c if isinstance(c, str) else c[0] for c in store.calls]
    assert kinds == ["ensure", "load_zones", "state", "zones", "events"] and len(sent) == 1
    states_call = next(c for c in store.calls if isinstance(c, tuple) and c[0] == "state")
    assert set(states_call[1]) <= {"1d", "4h", "1h", "15m"}
    store2, sent2 = FakeStore(), []
    RF.refresh_symbol("NIFTY", "tok", fake_fetch(df5, daily), store_mod=store2, now=NOW_LIVE, notify=sent2.append, send_brief=False)
    assert sent2 == []


def test_refresh_skips_on_failed_chunks_empty_data_dry_run_and_store_failure():
    df5, daily = fine_5m()
    store = FakeStore()
    ok, msg = RF.refresh_symbol("NIFTY", "tok", fake_fetch(df5, daily, failed=True), store_mod=store, now=NOW_LIVE)
    assert not ok and "chunks" in msg and store.calls == []
    ok, msg = RF.refresh_symbol("NIFTY", "tok", fake_fetch(df5.iloc[:0], daily), store_mod=store, now=NOW_LIVE)
    assert not ok and store.calls == []
    ok, msg = RF.refresh_symbol("NIFTY", "tok", fake_fetch(df5, daily), store_mod=store, now=NOW_LIVE, dry_run=True)
    assert ok and "dry-run" in msg and store.calls == []
    bad = FakeStore(ok=False)
    ok, msg = RF.refresh_symbol("NIFTY", "tok", fake_fetch(df5, daily), store_mod=bad, now=NOW_LIVE)
    assert not ok and "Supabase" in msg
    ok, msg = RF.refresh_symbol("NIFTY", "tok", lambda *a, **k: pd.DataFrame({"x": [1]}), store_mod=store, now=NOW_LIVE)
    assert not ok and ("गणना अयशस्वी" in msg or "डेटा" in msg)


# ---- scripts --------------------------------------------------------------------------------------------------------------------------------------
def test_eod_script_main_stores_via_injected_store_and_reports_token_errors(monkeypatch, capsys):
    import cloud_db
    import refresh_market_structure as script
    df5, daily = fine_5m()
    monkeypatch.setattr(cloud_db, "init_cloud_table", lambda: True)
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda t: t or "tok")
    monkeypatch.setattr(script, "send_telegram_message", lambda m: True)
    import opportunity_engine.report as RP
    monkeypatch.setattr(RP, "_ist_now", lambda: NOW_LIVE)
    store = FakeStore()
    assert script.main(["--symbols", "NIFTY"], fetch_fn=fake_fetch(df5, daily), store_mod=store) == 0
    assert "✅" in capsys.readouterr().out and store.calls
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda t: None)
    assert script.main(["--symbols", "NIFTY"], fetch_fn=fake_fetch(df5, daily), store_mod=FakeStore()) == 1
    assert "token" in capsys.readouterr().out


def test_intraday_script_respects_market_hours(monkeypatch, capsys):
    import refresh_market_structure_intraday as intra
    tz = intra.IST
    assert intra.market_is_open(tz.localize(datetime.datetime(2025, 1, 8, 10, 31)))
    assert not intra.market_is_open(tz.localize(datetime.datetime(2025, 1, 8, 9, 15)))
    assert not intra.market_is_open(tz.localize(datetime.datetime(2025, 1, 11, 11, 0)))            # शनिवार
    assert not intra.market_is_open(tz.localize(datetime.datetime(2025, 1, 8, 15, 40)))
    assert intra.main([], now=tz.localize(datetime.datetime(2025, 1, 11, 11, 0))) == 0
    assert "बाजार बंद" in capsys.readouterr().out


# ---- adapter ---------------------------------------------------------------------------------------------------------------------------------------
def ctx_of(states, price=24316.0):
    tfs = {tf: TFState(tf=tf, state=st, updated_at=NOW) for tf, st in states.items()}
    return Context(time=NOW, price=price, states=tfs, levels=[], adr=200.0)


GOOD = {"open": 24300.0, "high": 24318.0, "low": 24298.0, "close": 24316.0, "volume": 1700.0, "volume_median": 1000.0, "level": 24310.0, "ref_range": 10.0}
UP_ALL = {"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND"}


def test_registry_and_config_register_the_strategy_but_disabled():
    import yaml
    assert STRATEGY_REGISTRY["opportunity_engine"] is OpportunityEngineStrategy
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))["strategies"]["opportunity_engine"]
    assert cfg["enabled"] is False and cfg["primary_htf"] == "4h" and cfg["daily_veto"] is True
    from loader import build_orchestrator
    assert "opportunity_engine" not in [s.strategy_id for s in build_orchestrator("config.yaml").strategies]


def snapshot(payload):
    return MarketSnapshot(timestamp=NOW, extra={"oe_journal": payload} if payload is not None else {})


def test_adapter_returns_none_with_marathi_reason_on_missing_or_invalid_data():
    s = OpportunityEngineStrategy({"enabled": True})
    for payload in (None, "junk", {"context": "nope"}):
        r = s.check_gates(snapshot(payload))
        assert r.direction == Direction.NONE and "Opportunity Engine" in r.reason
    r = s.check_gates(snapshot(ctx_of({"1h": "UPTREND"})))
    assert r.direction == Direction.NONE and "तयार नाही" in r.reason
    r2 = s.check_gates(snapshot(ctx_of(UP_ALL)))
    assert r2.direction == Direction.NONE and "candidates नाहीत" in r2.reason and r2.meta["bias"] == "LONG_ONLY"
    assert s.required_data() == ["extra.oe_journal"]


def test_adapter_emits_a_signal_for_a_passing_candidate_and_respects_config_overrides():
    s = OpportunityEngineStrategy({"enabled": True})
    cand = Candidate(setup_id="D7", direction="LONG", time=NOW, entry=24316.0, sl_ref=24296.0, kind="BREAKOUT", setup_quality=100.0, trigger=dict(GOOD),
                     zone={"kind": "DEMAND", "tf": "1h", "low": 24280.0, "high": 24300.0, "freshness": "FRESH", "quality_grade": "A", "mtf_count": 3})
    r = s.check_gates(snapshot({"context": ctx_of(UP_ALL), "candidates": [cand]}))
    assert r.direction == Direction.LONG and r.confidence > 0.6 and r.entry_price == 24316.0 and r.stop_loss < r.entry_price < r.target
    assert r.meta["setup_id"] == "D7" and "Score" in r.reason and r.is_actionable()
    strict = OpportunityEngineStrategy({"enabled": True, "score_full": 99.0, "score_half": 98.0})
    r2 = strict.check_gates(snapshot({"context": ctx_of(UP_ALL), "candidates": [cand]}))
    assert r2.direction == Direction.NONE and r2.meta["decisions"][0]["status"] == "REJECTED_SCORE"
    short = Candidate(setup_id="D7", direction="SHORT", time=NOW, entry=24300.0, sl_ref=24320.0, kind="BREAKOUT", trigger={**GOOD, "level": 24310.0})
    r3 = s.check_gates(snapshot({"context": ctx_of(UP_ALL), "candidates": [short]}))
    assert r3.direction == Direction.NONE and r3.meta["decisions"][0]["status"] == "REJECTED_GATE"


def test_orchestrator_runs_the_strategy_without_crashing_when_enabled():
    from orchestrator import SignalOrchestrator
    orch = SignalOrchestrator([OpportunityEngineStrategy({"enabled": True})])
    assert orch.run_cycle(snapshot(ctx_of(UP_ALL))) == []                          # candidates नाहीत => कुठलाच signal नाही
