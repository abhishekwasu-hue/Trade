"""
tests/test_live_chart.py
--------------------------
"Live updates" (चार्टवरची शेवटची candle हलणे, REST LTP दर 3 सेकंदांनी) -- candle कालावधी ओळखणे, tick बनवणे, html फक्त बदलल्यावर पाठवणे,
आणि चार्ट HTML मध्ये live JS फक्त मागितल्यावरच असणे. (खरा browser + Streamlit end-to-end तपासणी वेगळी, हाताने केलेली.)
"""
import types

import numpy as np
import pandas as pd
import pytest

import live_chart
from tradingview_chart import _to_unix_time, build_lightweight_chart_html, build_mini_chart_html


def _df(freq, periods=40, tz=None):
    ts = pd.date_range("2026-10-01 09:15", periods=periods, freq=freq, tz=tz)
    close = 24000 + np.arange(periods, dtype=float)
    return pd.DataFrame({"timestamp": ts, "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1, "oi": 0})


class TestInferTfSeconds:
    @pytest.mark.parametrize("freq,expected", [("1min", 60), ("5min", 300), ("15min", 900), ("30min", 1800), ("1h", 3600)])
    def test_known_timeframes(self, freq, expected):
        assert live_chart.infer_tf_seconds(_df(freq)) == expected

    def test_daily_and_irregular_give_none(self):
        assert live_chart.infer_tf_seconds(_df("1D")) is None
        assert live_chart.infer_tf_seconds(_df("7min")) is None

    def test_too_little_or_bad_data(self):
        assert live_chart.infer_tf_seconds(_df("5min", periods=1)) is None
        assert live_chart.infer_tf_seconds(pd.DataFrame()) is None
        assert live_chart.infer_tf_seconds(None) is None

    def test_overnight_gaps_do_not_confuse_it(self):
        day1 = pd.date_range("2026-10-01 09:15", periods=20, freq="5min")
        day2 = pd.date_range("2026-10-02 09:15", periods=20, freq="5min")
        df = pd.DataFrame({"timestamp": list(day1) + list(day2)})
        assert live_chart.infer_tf_seconds(df) == 300

    def test_follows_real_candles_not_requested_interval(self):
        # MCX '1hour' माग्यावर fetch_mcx_candles 30-मिनिट देतो => 1800 यायला हवं
        assert live_chart.infer_tf_seconds(_df("30min", tz="Asia/Kolkata")) == 1800


class TestTicks:
    def test_closed_market_never_calls_ltp(self):
        calls = []
        ticks = live_chart.fetch_group_ticks("tok", "NSE", ["A", "B"], market_open_fn=lambda: False, ltp_fn=lambda *a: calls.append(a))
        assert calls == [] and {t["status"] for t in ticks.values()} == {"closed"} and all(t["price"] is None for t in ticks.values())

    def test_live_prices_with_one_call_for_all_keys(self):
        calls = []

        def ltp(token, keys):
            calls.append((token, keys))
            return {"A": 24010.5, "B": 52000.0}

        ticks = live_chart.fetch_group_ticks("tok", "NSE", ["A", "B"], market_open_fn=lambda: True, ltp_fn=ltp)
        assert calls == [("tok", ["A", "B"])]
        assert ticks["A"]["status"] == "live" and ticks["A"]["price"] == 24010.5 and ticks["B"]["price"] == 52000.0
        assert ticks["A"]["type"] == "live_tick" and isinstance(ticks["A"]["time"], int) and ":" in ticks["A"]["label"]

    def test_missing_key_or_failure_is_stale_not_fake(self):
        ticks = live_chart.fetch_group_ticks("tok", "NSE", ["A", "B"], market_open_fn=lambda: True, ltp_fn=lambda t, k: {"A": 1.0})
        assert ticks["A"]["status"] == "live" and ticks["B"]["status"] == "stale" and ticks["B"]["price"] is None

        def boom(t, k):
            raise RuntimeError("api down")

        assert live_chart.fetch_group_ticks("tok", "MCX", ["A"], market_open_fn=lambda: True, ltp_fn=boom)["A"]["status"] == "stale"

    def test_market_is_chosen_by_name(self, monkeypatch):
        seen = []
        monkeypatch.setitem(live_chart._MARKET_OPEN_FNS, "MCX", lambda: seen.append("mcx") or False)
        monkeypatch.setitem(live_chart._MARKET_OPEN_FNS, "NSE", lambda: seen.append("nse") or False)
        live_chart.fetch_group_ticks("t", "MCX", ["A"])
        live_chart.fetch_group_ticks("t", "NSE", ["A"])
        assert seen == ["mcx", "nse"]


class TestHtmlIsSentOnlyWhenNeeded:
    @pytest.fixture
    def env(self, monkeypatch):
        fake_st = types.SimpleNamespace(session_state={})
        monkeypatch.setattr(live_chart, "st", fake_st)
        calls = []

        def component(**kw):
            calls.append(kw)
            return fake_st.session_state.get(kw["key"])

        return fake_st, calls, component

    def test_first_call_sends_html_then_only_ticks(self, env):
        st, calls, comp = env
        tick = {"price": 1}
        live_chart.live_chart("<html>A</html>", tick, "k", 400, component_fn=comp)
        live_chart.live_chart("<html>A</html>", tick, "k", 400, component_fn=comp)
        assert calls[0]["html"] == "<html>A</html>" and calls[1]["html"] == ""
        assert calls[0]["html_hash"] == calls[1]["html_hash"] and calls[1]["tick"] == tick

    def test_changed_html_is_sent_again(self, env):
        st, calls, comp = env
        live_chart.live_chart("<html>A</html>", None, "k", 400, component_fn=comp)
        live_chart.live_chart("<html>B</html>", None, "k", 400, component_fn=comp)
        assert calls[1]["html"] == "<html>B</html>" and calls[0]["html_hash"] != calls[1]["html_hash"]

    def test_shell_asking_for_html_triggers_resend(self, env):
        st, calls, comp = env
        live_chart.live_chart("<html>A</html>", None, "k", 400, component_fn=comp)
        st.session_state["_lc_k"] = "need_html:abc"         # शेल remount झाला
        live_chart.live_chart("<html>A</html>", None, "k", 400, component_fn=comp)
        assert calls[1]["html"] == "<html>A</html>"

    def test_charts_are_tracked_independently(self, env):
        st, calls, comp = env
        live_chart.live_chart("<html>A</html>", None, "k1", 400, component_fn=comp)
        live_chart.live_chart("<html>A</html>", None, "k2", 400, component_fn=comp)
        assert calls[0]["html"] and calls[1]["html"]       # दुसऱ्या key साठी अजून पाठवलेलं नव्हतं


class TestChartHtmlLiveHooks:
    def test_main_chart_live_only_when_requested(self):
        df = _df("5min")
        assert "const LIVE_TF = 300;" in build_lightweight_chart_html(df, symbol="X", timeframe_label="5M", live_tf_seconds=300)
        html = build_lightweight_chart_html(df, symbol="X", timeframe_label="5M")
        assert "const LIVE_TF = 0;" in html           # listener आहे, पण LIVE_TF=0 => काहीच करत नाही

    def test_mini_chart_live_hooks(self):
        df = pd.concat([_df("5min").assign(timestamp=lambda d: d.timestamp - pd.Timedelta(days=1)), _df("5min")])
        html = build_mini_chart_html(df, "NIFTY", live_tf_seconds=300)
        assert "const LIVE_TF = 300;" in html and 'id="px"' in html and "const PREV_CLOSE = 240" in html
        assert "const LIVE_TF = 0;" in build_mini_chart_html(df, "NIFTY")


class TestChartTimeAxisUsesIst:
    def test_tz_aware_ist_timestamp_keeps_wall_clock(self):
        ist = pd.Timestamp("2026-10-02 09:15:00", tz="Asia/Kolkata")
        naive = pd.Timestamp("2026-10-02 09:15:00")
        assert _to_unix_time(ist) == _to_unix_time(naive)

    def test_naive_timestamp_unchanged(self):
        assert _to_unix_time(pd.Timestamp("2026-10-02 09:15:00")) == int(pd.Timestamp("2026-10-02 09:15:00").timestamp())

    def test_daily_candle_stays_on_its_own_date(self):
        day = pd.Timestamp("2026-10-02T00:00:00+05:30")
        assert pd.Timestamp(_to_unix_time(day), unit="s").date() == pd.Timestamp("2026-10-02").date()


class TestComponentShell:
    def test_shell_speaks_the_streamlit_protocol(self):
        with open("live_chart_component/index.html", encoding="utf-8") as f:
            shell = f.read()
        for needle in ("streamlit:componentReady", "streamlit:render", "streamlit:setFrameHeight", "streamlit:setComponentValue", "need_html", "srcdoc"):
            assert needle in shell


class TestLinesFnRidesOnTheTick:
    @pytest.fixture
    def env(self, monkeypatch):
        import contextlib

        sent = []
        fake_st = types.SimpleNamespace(
            session_state={}, container=lambda: contextlib.nullcontext(), columns=lambda n: [contextlib.nullcontext() for _ in range(n)],
        )
        monkeypatch.setattr(live_chart, "st", fake_st)
        monkeypatch.setattr(live_chart, "live_chart", lambda html, tick, key, height, component_fn=None: sent.append((key, tick)))
        monkeypatch.setattr(live_chart, "fetch_group_ticks", lambda token, market, keys, **kw: {"K": live_chart.build_tick(24000.5, "live")})
        return fake_st, sent

    def _group(self, st, **chart):
        st.session_state["_live_group_g"] = {"token": "tok", "market": "NSE", "side_by_side": False,
                                             "charts": [{"key": "c", "html": "<html/>", "instrument_key": "K", "height": 400, **chart}]}
        live_chart._render_group("g")

    def test_lines_are_added_to_the_tick_with_the_live_price(self, env):
        st, sent = env
        seen = []
        self._group(st, lines_fn=lambda price: seen.append(price) or [{"title": "SL", "price": 1.0}])
        assert seen == [24000.5] and sent[0][1]["lines"] == [{"title": "SL", "price": 1.0}] and sent[0][1]["price"] == 24000.5

    def test_no_lines_fn_means_no_lines_key(self, env):
        st, sent = env
        self._group(st)
        assert "lines" not in sent[0][1]

    def test_failing_lines_fn_does_not_break_the_chart(self, env):
        st, sent = env

        def boom(price):
            raise RuntimeError("db locked")

        self._group(st, lines_fn=boom)
        assert len(sent) == 1 and "lines" not in sent[0][1]

    def test_lines_still_sent_when_there_is_no_tick(self, env, monkeypatch):
        st, sent = env
        monkeypatch.setattr(live_chart, "fetch_group_ticks", lambda *a, **k: {})
        self._group(st, lines_fn=lambda price: [{"title": "SL", "price": 2.0}])
        assert sent[0][1]["status"] == "stale" and sent[0][1]["lines"] == [{"title": "SL", "price": 2.0}]


class TestChartHtmlLineSync:
    def test_sync_machinery_is_present_and_hooked_to_ticks(self):
        html = build_lightweight_chart_html(_df("5min"), symbol="X", timeframe_label="5M", live_tf_seconds=300,
                                            trade_lines=[{"price": 24000, "title": "SL", "color": "#F23645"}])
        assert "function syncTradeLines" in html and "m.lines" in html and "removePriceLine" in html
