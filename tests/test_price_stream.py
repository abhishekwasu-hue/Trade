"""
tests/test_price_stream.py
--------------------------------
🎓 रिअल-टाइम WebSocket price feed (price_stream.py / position_stream_monitor.py / read_cache.py) -- नेटवर्कशिवाय.
"""
import json
from unittest.mock import MagicMock

import pytest

import database
import price_stream
import position_stream_monitor as psm
import read_cache
import upstox_feed_pb2 as pb
from price_stream import FeedClient, PriceStore, build_request, decode_feed_message


def _feed_bytes(**entries):
    """entries: key -> ("ltpc"|"market"|"index"|"greeks", ltp)."""
    resp = pb.FeedResponse()
    resp.type = 1
    for key, (kind, ltp) in entries.items():
        feed = resp.feeds[key]
        if kind == "ltpc":
            feed.ltpc.ltp = ltp
        elif kind == "market":
            feed.fullFeed.marketFF.ltpc.ltp = ltp
        elif kind == "index":
            feed.fullFeed.indexFF.ltpc.ltp = ltp
        elif kind == "greeks":
            feed.firstLevelWithGreeks.ltpc.ltp = ltp
    return resp.SerializeToString()


class TestDecode:
    def test_all_feed_shapes(self):
        data = _feed_bytes(a=("ltpc", 100.5), b=("market", 20.25), c=("index", 22540.0), d=("greeks", 7.5))
        assert decode_feed_message(data) == {"a": 100.5, "b": 20.25, "c": 22540.0, "d": 7.5}

    def test_zero_or_missing_ltp_is_ignored(self):
        assert decode_feed_message(_feed_bytes(a=("ltpc", 0.0))) == {}
        assert decode_feed_message(pb.FeedResponse().SerializeToString()) == {}

    def test_garbage_never_raises(self):
        assert decode_feed_message(b"\xff\xfe\x00garbage") == {}
        assert decode_feed_message(b"") == {}


class TestRequestAndStore:
    def test_request_format_matches_upstox_sdk(self):
        req = json.loads(build_request({"NSE_FO|2", "NSE_FO|1"}, "sub", "ltpc"))
        assert req["method"] == "sub" and req["data"] == {"instrumentKeys": ["NSE_FO|1", "NSE_FO|2"], "mode": "ltpc"}
        assert req["guid"]
        unsub = json.loads(build_request(["x"], "unsub"))
        assert "mode" not in unsub["data"]

    def test_store_snapshot_ages_and_feed_age(self):
        t = {"now": 100.0}
        store = PriceStore(clock=lambda: t["now"])
        assert store.feed_age() is None
        store.update({"a": 1.0, "b": 2.0})
        t["now"] = 102.5
        prices, ages = store.snapshot(["a", "b"])
        assert prices == {"a": 1.0, "b": 2.0} and ages["a"] == pytest.approx(2.5)
        assert store.snapshot(["a", "missing"]) == (None, None)
        assert store.feed_age() == pytest.approx(2.5)
        store.clear()
        assert store.snapshot(["a"]) == (None, None) and store.feed_age() is None


class _FakeWs:
    def __init__(self):
        self.sent = []

    def send(self, payload, opcode=None):
        self.sent.append(json.loads(payload))

    def close(self):
        pass


class TestFeedClient:
    def _client(self):
        store = PriceStore()
        client = FeedClient(lambda: "tok", store, log=lambda *a: None)
        return client, store

    def test_subscriptions_are_diffed_after_connect(self):
        client, _ = self._client()
        ws = _FakeWs()
        client.set_subscriptions({"a", "b"})            # connect होण्याआधी -- काहीच पाठवत नाही
        client._on_open(ws)
        assert [m["method"] for m in ws.sent] == ["sub"]
        assert set(ws.sent[0]["data"]["instrumentKeys"]) == {"a", "b"}
        client.set_subscriptions({"b", "c"})
        methods = {m["method"]: set(m["data"]["instrumentKeys"]) for m in ws.sent[1:]}
        assert methods == {"sub": {"c"}, "unsub": {"a"}}
        client.set_subscriptions({"b", "c"})            # बदल नाही -- काही नाही
        assert len(ws.sent) == 3

    def test_reconnect_resubscribes_everything(self):
        client, _ = self._client()
        client.set_subscriptions({"a"})
        ws1 = _FakeWs(); client._on_open(ws1)
        client._on_close(ws1)
        assert client.connected is False
        ws2 = _FakeWs(); client._on_open(ws2)
        assert set(ws2.sent[0]["data"]["instrumentKeys"]) == {"a"}

    def test_messages_update_store_and_health(self):
        client, store = self._client()
        ws = _FakeWs(); client._on_open(ws)
        assert client.healthy() is False                   # अजून एकही संदेश नाही
        client._on_message(ws, _feed_bytes(a=("ltpc", 10.0)))
        assert client.healthy() is True and store.snapshot(["a"])[0] == {"a": 10.0}
        client._on_message(ws, b"junk")                    # न समजणारा संदेश -- फक्त जिवंतपणाची खूण
        assert client.healthy() is True
        client._on_close(ws)
        assert client.healthy() is False

    def test_stale_feed_is_unhealthy(self):
        t = {"now": 0.0}
        store = PriceStore(clock=lambda: t["now"])
        client = FeedClient(lambda: "tok", store, log=lambda *a: None)
        client._on_open(_FakeWs())
        store.update({"a": 1.0})
        t["now"] = 6.0
        assert client.healthy(max_feed_age=5.0) is False

    def test_run_loop_reconnects_with_backoff_and_clears_stale_prices(self):
        store = PriceStore()
        sleeps = []
        calls = {"n": 0}

        def connect_fn(url, headers, handlers):
            calls["n"] += 1
            assert headers[0] == "Authorization: Bearer tok"
            handlers["open"](_FakeWs())
            handlers["message"](None, _feed_bytes(a=("ltpc", 5.0)))
            if calls["n"] >= 3:
                client._stop.set()
            handlers["close"](None)

        client = FeedClient(lambda: "tok", store, connect_fn=connect_fn, sleep_fn=sleeps.append, log=lambda *a: None)
        client._run_forever()
        assert calls["n"] == 3
        assert sleeps == [1.0, 2.0]                        # backoff दुप्पट; शेवटच्या वेळी stop मुळे sleep नाही
        assert store.snapshot(["a"]) == (None, None)       # connection तुटल्यावर जुन्या किमती कधीच वापरल्या जात नाहीत


class _Cycle:
    def __init__(self):
        self.calls = []

    def __call__(self, token, product, **kw):
        self.calls.append(kw)
        return "X: SL -> बंद झाला"


class TestStreamMonitorStep:
    def _monitor(self, modes, open_market=True, healthy=True, **kw):
        store = PriceStore()
        client = MagicMock()
        client.healthy.return_value = healthy
        cycle = _Cycle()
        t = {"now": 0.0}
        mon = psm.StreamMonitor(
            lambda: "tok", client, store, cycle_fn=cycle, modes_fn=lambda: modes, market_open_fn=lambda: open_market,
            keys_fn=lambda syms: {"LEG1"}, spot_key_fn=lambda s: f"SPOT_{s}", clock=lambda: t["now"], log=lambda *a: None, **kw)
        return mon, client, store, cycle, t

    def test_market_closed_and_idle_clear_subscriptions(self):
        mon, client, *_ = self._monitor({"NIFTY": {"PAPER"}}, open_market=False)
        assert mon.step() == "market-closed"
        client.set_subscriptions.assert_called_with([])
        mon, client, *_ = self._monitor({})
        assert mon.step() == "idle"
        client.set_subscriptions.assert_called_with([])

    def test_subscribes_to_legs_and_spot_then_waits_for_prices(self):
        mon, client, store, cycle, _ = self._monitor({"NIFTY": {"PAPER"}})
        assert mon.step() == "waiting-first-ticks"
        assert client.set_subscriptions.call_args.args[0] == {"LEG1", "SPOT_NIFTY"}
        assert cycle.calls == []

    def test_unhealthy_feed_does_nothing(self):
        mon, client, store, cycle, _ = self._monitor({"NIFTY": {"PAPER"}}, healthy=False)
        store.update({"LEG1": 1.0, "SPOT_NIFTY": 2.0})
        assert mon.step() == "feed-unhealthy" and cycle.calls == []

    def test_runs_cycle_with_live_prices_and_rate_limits(self):
        mon, client, store, cycle, t = self._monitor({"NIFTY": {"PAPER"}})
        store.update({"LEG1": 1.0, "SPOT_NIFTY": 2.0})
        assert mon.step() == "cycle"
        assert cycle.calls[0]["live_prices"] == {"LEG1": 1.0, "SPOT_NIFTY": 2.0}
        assert cycle.calls[0]["heartbeat"] is False and "live_price_age" in cycle.calls[0]
        t["now"] = 0.2
        store.update({"LEG1": 1.1})
        assert mon.step() == "skipped"                     # min-cycle-interval (0.5) च्या आत
        t["now"] = 0.6
        assert mon.step() == "cycle"                       # किंमत बदलली + अंतर पुरेसं
        t["now"] = 1.0
        assert mon.step() == "skipped"                     # किंमत बदलली नाही आणि force-interval (2s) अजून नाही
        t["now"] = 3.0
        assert mon.step() == "cycle"                       # वेळेवर आधारित नियमांसाठी सक्तीची तपासणी
        assert len(cycle.calls) == 3

    def test_no_token_skips(self):
        mon, client, store, cycle, _ = self._monitor({"NIFTY": {"PAPER"}})
        mon._token_provider = lambda: None
        store.update({"LEG1": 1.0, "SPOT_NIFTY": 2.0})
        assert mon.step() == "no-token" and cycle.calls == []


class TestHelpers:
    def test_collect_needed_keys(self):
        keys = psm.collect_needed_keys(["NIFTY", "SENSEX"], keys_fn=lambda s: {"L1", "L2"}, spot_key_fn=lambda s: f"S_{s}")
        assert keys == {"L1", "L2", "S_NIFTY", "S_SENSEX"}

    def test_open_trade_instrument_keys_from_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
        database.init_sqlite_db()
        import sqlite3
        conn = sqlite3.connect(database.DB_PATH)
        rows = [
            ("A", "NIFTY", "OPEN", json.dumps([{"instrument_key": "K1"}, {"instrument_key": "K2"}])),
            ("B", "NIFTY", "CLOSED", json.dumps([{"instrument_key": "K3"}])),
            ("C", "SENSEX", "OPEN", json.dumps([{"instrument_key": "K4"}])),
            ("D", "NIFTY", "OPEN", "not-json"),
        ]
        for tid, sym, status, legs in rows:
            conn.execute("INSERT INTO live_trades (trade_id, trade_date, symbol, lots, lot_size, status, legs_json) "
                         "VALUES (?, '2026-10-01', ?, 1, 1, ?, ?)", (tid, sym, status, legs))
        conn.commit(); conn.close()
        assert database.get_open_trade_instrument_keys(["NIFTY"]) == {"K1", "K2"}
        assert database.get_open_trade_instrument_keys(["NIFTY", "SENSEX"]) == {"K1", "K2", "K4"}
        assert database.get_open_trade_instrument_keys([]) == set()


class TestReadCache:
    def test_ttl_cache_hits_then_expires(self):
        t = {"now": 0.0}
        calls = []
        fn = lambda a, b=1: calls.append((a, b)) or len(calls)
        cached = read_cache.ttl_cached(fn, 10, clock=lambda: t["now"])
        assert cached("x") == 1 and cached("x") == 1 and len(calls) == 1
        assert cached("y") == 2
        t["now"] = 11.0
        assert cached("x") == 3

    def test_install_wraps_once_and_only_the_two_readers(self):
        class Fake:
            def get_strategy_settings(self, *a): return 1
            def get_next_level_in_direction(self, *a): return 2
            def other(self): return 3
        fake = Fake()
        mod = type("M", (), {})()
        mod.get_strategy_settings = fake.get_strategy_settings
        mod.get_next_level_in_direction = fake.get_next_level_in_direction
        mod.other = fake.other
        read_cache.install_monitor_read_cache(mod)
        first = mod.get_strategy_settings
        read_cache.install_monitor_read_cache(mod)
        assert mod.get_strategy_settings is first            # दुसऱ्यांदा wrap नाही
        assert hasattr(mod.get_next_level_in_direction, "cache_clear") and not hasattr(mod.other, "cache_clear")


class TestRealWebSocketRoundTrip:
    """खरा websocket-client + स्थानिक fake Upstox सर्व्हर (websockets lib, फक्त उपलब्ध असेल तर): subscribe विनंती binary JSON
    म्हणून पोहोचते, protobuf ticks store मध्ये येतात, सर्व्हरने connection तोडला तर आपोआप reconnect + पुन्हा subscribe."""

    def test_round_trip_and_reconnect(self):
        websockets = pytest.importorskip("websockets")
        import asyncio
        import threading
        import time

        received, connections = [], []
        loop_holder = {}

        async def handler(ws):
            connections.append(ws)
            async for msg in ws:
                assert isinstance(msg, (bytes, bytearray))        # binary frame
                req = json.loads(msg)
                received.append(req)
                if req["method"] == "sub":
                    prices = {k: ("ltpc", 100.0 + i) for i, k in enumerate(sorted(req["data"]["instrumentKeys"]))}
                    await ws.send(_feed_bytes(**prices))

        def serve():
            async def main():
                async with websockets.serve(handler, "127.0.0.1", 0) as server:
                    loop_holder["port"] = server.sockets[0].getsockname()[1]
                    loop_holder["loop"] = asyncio.get_running_loop()
                    loop_holder["ready"] = True
                    loop_holder["stop"] = asyncio.Event()
                    await loop_holder["stop"].wait()
            asyncio.run(main())

        threading.Thread(target=serve, daemon=True).start()
        for _ in range(100):
            if loop_holder.get("ready"):
                break
            time.sleep(0.05)
        assert loop_holder.get("ready")

        store = PriceStore()
        client = FeedClient(lambda: "tok", store, url=f"ws://127.0.0.1:{loop_holder['port']}",
                            log=lambda *a: None, max_backoff=0.2)
        client.start()
        try:
            def wait(cond, timeout=8.0):
                end = time.time() + timeout
                while time.time() < end:
                    if cond():
                        return True
                    time.sleep(0.05)
                return False

            assert wait(lambda: client.connected)
            client.set_subscriptions({"NSE_FO|1", "NSE_INDEX|Nifty 50"})
            assert wait(lambda: store.snapshot(["NSE_FO|1", "NSE_INDEX|Nifty 50"])[0] is not None)
            assert received[0]["method"] == "sub" and received[0]["data"]["mode"] == "ltpc"
            assert client.healthy()

            # सर्व्हरने connection तोडला -> आपोआप reconnect आणि पुन्हा subscribe
            n_before = len(received)
            asyncio.run_coroutine_threadsafe(connections[0].close(), loop_holder["loop"])   # प्रतीक्षा न करता
            assert wait(lambda: len(connections) >= 2 and client.connected)
            assert wait(lambda: len(received) > n_before)
            assert set(received[-1]["data"]["instrumentKeys"]) == {"NSE_FO|1", "NSE_INDEX|Nifty 50"}
            assert wait(lambda: store.snapshot(["NSE_FO|1", "NSE_INDEX|Nifty 50"])[0] is not None)
        finally:
            client.stop()
            loop_holder["loop"].call_soon_threadsafe(loop_holder["stop"].set)


class TestMcxStreamMonitor:
    """🎓 "mcx open trade sathi real time websocket use kra" -- position_stream_monitor.py --market mcx."""

    def test_collect_needed_keys_skips_missing_spot_key(self):
        keys = psm.collect_needed_keys(["GOLD", "SILVER"], keys_fn=lambda s: {"MCX_FO|1", "MCX_FO|2"}, spot_key_fn=lambda s: None)
        assert keys == {"MCX_FO|1", "MCX_FO|2"}

    def _monitor(self, modes, cycle):
        store = PriceStore()
        client = MagicMock()
        client.healthy.return_value = True
        mon = psm.StreamMonitor(
            lambda: "tok", client, store, cycle_fn=cycle, modes_fn=lambda: modes, market_open_fn=lambda: True,
            keys_fn=lambda syms: {"MCX_FO|GOLD1"}, spot_key_fn=lambda s: None, clock=lambda: 0.0,
            log=lambda *a: None, symbols=["CRUDEOIL", "GOLD"])
        return mon, client, store

    def test_only_mcx_symbols_count_and_no_spot_subscription(self):
        cycle = _Cycle()
        mon, client, store = self._monitor({"NIFTY": {"PAPER"}}, cycle)   # NSE symbol -- MCX monitor साठी idle
        assert mon.step() == "idle"
        mon, client, store = self._monitor({"GOLD": {"PAPER"}}, cycle)
        assert mon.step() == "waiting-first-ticks"
        assert client.set_subscriptions.call_args.args[0] == {"MCX_FO|GOLD1"}

    def test_runs_cycle_with_live_prices(self):
        cycle = _Cycle()
        mon, client, store = self._monitor({"GOLD": {"PAPER"}}, cycle)
        store.update({"MCX_FO|GOLD1": 75000.0})
        assert mon.step() == "cycle"
        assert cycle.calls[0]["live_prices"] == {"MCX_FO|GOLD1": 75000.0}

    def test_close_result_is_logged_for_mcx_wording(self):
        logged = []
        store = PriceStore()
        client = MagicMock()
        client.healthy.return_value = True
        mon = psm.StreamMonitor(
            lambda: "tok", client, store, cycle_fn=lambda *a, **k: "GOLD: 🔔 1 position(s) बंद झाल्या",
            modes_fn=lambda: {"GOLD": {"PAPER"}}, market_open_fn=lambda: True, keys_fn=lambda syms: {"K"},
            spot_key_fn=lambda s: None, clock=lambda: 0.0, log=logged.append, symbols=["GOLD"])
        store.update({"K": 1.0})
        mon.step()
        assert logged and "बंद" in logged[0]

    def test_build_market_mcx_wires_live_prices_into_mcx_exit_cycle(self, monkeypatch):
        import mcx_futures_trader as mft
        seen = {}

        def fake_cycle(token, symbols, heartbeat=False, live_prices=None, live_price_age=None):
            seen.update(token=token, symbols=symbols, live_prices=live_prices, age=live_price_age)
            return ["GOLD: 🔔 1 position(s) बंद झाल्या"], True

        monkeypatch.setattr(mft, "run_exit_monitor_cycle", fake_cycle)
        cfg = psm.build_market("mcx")
        assert cfg["script_name"] == "position_stream_monitor_mcx" and cfg["lock_name"] != psm.build_market("nse")["lock_name"]
        assert set(cfg["symbols"]) == set(mft.MCX_FUTURES_SYMBOLS)
        out = cfg["cycle_fn"]("tok", "D", live_prices={"K": 1.0}, live_price_age={"K": 0.2}, heartbeat=False)
        assert seen["live_prices"] == {"K": 1.0} and seen["age"] == {"K": 0.2} and seen["token"] == "tok"
        assert "बंद" in out

    def test_build_market_nse_keeps_old_behaviour(self):
        cfg = psm.build_market("nse")
        assert cfg["cycle_fn"] is None and cfg["market_open_fn"] is None and cfg["script_name"] == "position_stream_monitor"
        assert "NIFTY" in cfg["symbols"] and "GOLD" not in cfg["symbols"]


class TestMcxMarketOpen:
    def test_weekday_session_and_weekend(self):
        import datetime
        from config import is_mcx_market_open
        assert is_mcx_market_open(datetime.datetime(2026, 10, 1, 9, 0))          # गुरुवार सकाळ
        assert is_mcx_market_open(datetime.datetime(2026, 10, 1, 23, 20))        # रात्री अजून सुरू
        assert not is_mcx_market_open(datetime.datetime(2026, 10, 1, 8, 59))
        assert not is_mcx_market_open(datetime.datetime(2026, 10, 3, 12, 0))     # शनिवार

