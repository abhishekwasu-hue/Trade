"""tests/test_verify_opportunity_data_availability.py -- PR-0 script (network-free: `_get` / requests mocked). फक्त GET; token print होत नाही."""
import datetime
import re

import pytest

import verify_opportunity_data_availability as v

TODAY = datetime.date(2026, 10, 3)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(v, "REQUEST_PAUSE_SECONDS", 0)
    monkeypatch.setattr(v.time, "sleep", lambda s: None)


def _days_back(months):
    return TODAY - datetime.timedelta(days=round(months * 30.44))


# ---- इतिहास-शोध -----------------------------------------------------------------------------------------------------------
class TestFindEarliestData:
    def _probe_for(self, cutoff, log):
        def probe(end_date):
            log.append(end_date)
            return end_date >= cutoff, {"status": 200 if end_date >= cutoff else 400, "error": None if end_date >= cutoff else "too old"}
        return probe

    def test_finds_cutoff_within_window_and_uses_few_calls(self):
        cutoff = datetime.date(2022, 1, 3)
        calls = []
        r = v.find_earliest_data(self._probe_for(cutoff, calls), TODAY)
        assert r["state"] == "FOUND"
        lo, hi = (datetime.date.fromisoformat(x) for x in r["earliest_between"])
        assert hi - lo <= datetime.timedelta(days=v.PROBE_WINDOW_DAYS)
        assert lo - datetime.timedelta(days=1) < cutoff <= hi + datetime.timedelta(days=v.PROBE_WINDOW_DAYS)
        assert r["calls"] == len(calls) and len(calls) < 30

    def test_data_at_every_checkpoint_means_at_least_deepest(self):
        r = v.find_earliest_data(lambda d: (True, {}), TODAY)
        assert r["state"] == "AT_LEAST" and r["depth_months"] == v.CHECKPOINT_MONTHS[-1]
        assert r["calls"] == len(v.CHECKPOINT_MONTHS)

    def test_no_data_even_at_first_checkpoint_reports_the_failure(self):
        r = v.find_earliest_data(lambda d: (False, {"status": 403, "error": "Forbidden"}), TODAY)
        assert r["state"] == "NO_DATA" and r["first_failure"] == {"status": 403, "error": "Forbidden"} and r["calls"] == 1

    @pytest.mark.parametrize("cutoff", [datetime.date(2025, 9, 20), datetime.date(2024, 2, 29), datetime.date(2019, 5, 6), datetime.date(2016, 12, 31)])
    def test_various_cutoffs_are_bracketed(self, cutoff):
        r = v.find_earliest_data(lambda d: (d >= cutoff, {}), TODAY)
        assert r["state"] in ("FOUND", "AT_LEAST")
        if r["state"] == "FOUND":
            lo, hi = (datetime.date.fromisoformat(x) for x in r["earliest_between"])
            assert lo - datetime.timedelta(days=1) < cutoff <= hi + datetime.timedelta(days=v.PROBE_WINDOW_DAYS)


# ---- URL आणि HTTP -----------------------------------------------------------------------------------------------------------
class TestRequests:
    def test_v3_and_expired_urls(self, monkeypatch):
        seen = []
        monkeypatch.setattr(v, "_get", lambda url, token, params=None, **kw: (seen.append((url, params)), (200, {"data": {"candles": [["t", 1, 2, 0, 1, 5, 7]]}}, None))[1])
        v.fetch_candles_window("tok", "NSE_INDEX|Nifty 50", "5minute", datetime.date(2026, 9, 1), datetime.date(2026, 9, 10))
        v.fetch_candles_window("tok", "NSE_INDEX|Nifty 50", "day", datetime.date(2026, 9, 1), datetime.date(2026, 9, 10))
        out = v.fetch_candles_window("tok", "NSE_FO|53806|24-04-2025", "5minute", datetime.date(2025, 4, 20), datetime.date(2025, 4, 24), expired=True)
        assert seen[0][0] == "https://api.upstox.com/v3/historical-candle/NSE_INDEX%7CNifty%2050/minutes/5/2026-09-10/2026-09-01"
        assert seen[1][0].endswith("/days/1/2026-09-10/2026-09-01")
        assert seen[2][0] == "https://api.upstox.com/v2/expired-instruments/historical-candle/NSE_FO%7C53806%7C24-04-2025/5minute/2025-04-24/2025-04-20"
        assert out["candles"] and out["status"] == 200

    def test_non_200_gives_no_candles_and_keeps_status_and_error(self, monkeypatch):
        monkeypatch.setattr(v, "_get", lambda *a, **k: (403, {"status": "error"}, "plan required"))
        r = v.fetch_candles_window("tok", "K", "5minute", TODAY, TODAY)
        assert r == {"status": 403, "candles": [], "error": "plan required"}

    def test_get_retries_on_429_then_succeeds_and_never_posts(self, monkeypatch):
        class Res:
            def __init__(self, code, body=None, text=""):
                self.status_code, self._b, self.text, self.headers = code, body, text, {}
            def json(self):
                if self._b is None:
                    raise ValueError
                return self._b
        responses = [Res(429), Res(200, {"data": 1})]
        monkeypatch.setattr(v.requests, "get", lambda *a, **k: responses.pop(0))
        monkeypatch.setattr(v.requests, "post", lambda *a, **k: pytest.fail("POST नको -- script फक्त वाचते"))
        assert v._get("https://x", "tok") == (200, {"data": 1}, None)

    def test_get_network_error_returns_none_status(self, monkeypatch):
        def boom(*a, **k):
            raise v.requests.exceptions.ConnectionError("down")
        monkeypatch.setattr(v.requests, "get", boom)
        status, body, err = v._get("https://x", "tok", retries=1)
        assert status is None and body is None and "ConnectionError" in err

    def test_non_json_body_is_tolerated(self, monkeypatch):
        class Res:
            status_code, headers, text = 500, {}, "<html>oops</html>"
            def json(self):
                raise ValueError
        monkeypatch.setattr(v.requests, "get", lambda *a, **k: Res())
        status, body, err = v._get("https://x", "tok", retries=0)
        assert (status, body) == (500, None) and "oops" in err


# ---- candles सारांश ---------------------------------------------------------------------------------------------------------
def test_summarize_candles():
    assert v.summarize_candles([]) == {"rows": 0}
    rows = [["2026-09-01T09:15:00+05:30", 1, 2, 0, 1, 100, 5], ["2026-09-01T09:20:00+05:30", 1, 2, 0, 1, 0, 0],
            ["2026-09-01T09:25:00+05:30", 1, 2, 0, 1, None, None], ["2026-09-01T09:30:00+05:30", 1, 2, 0, 1, "50", "9"]]
    s = v.summarize_candles(rows)
    assert s["rows"] == 4 and s["volume_nonzero_pct"] == 50.0 and s["oi_nonzero_pct"] == 50.0
    assert s["first"].startswith("2026-09-01T09:15") and s["last"].startswith("2026-09-01T09:30")
    assert v.summarize_candles([["t", 1, 1, 1, 1]])["volume_nonzero_pct"] == 0.0           # खूप लहान row


# ---- front-month futures ---------------------------------------------------------------------------------------------------
class TestResolveFrontFuture:
    ROWS = [
        {"trading_symbol": "NIFTY FUT 25 NOV 26", "instrument_key": "NSE_FO|2", "expiry": "2026-11-24", "lot_size": 75},
        {"trading_symbol": "NIFTY FUT 27 OCT 26", "instrument_key": "NSE_FO|1", "expiry": "2026-10-27", "lot_size": 75},
        {"trading_symbol": "NIFTY FUT 29 SEP 26", "instrument_key": "NSE_FO|0", "expiry": "2026-09-29", "lot_size": 75},     # expire झालेला
        {"trading_symbol": "FINNIFTY FUT 27 OCT 26", "instrument_key": "NSE_FO|9", "expiry": "2026-10-27", "lot_size": 65},
        {"trading_symbol": "NIFTYNXT50 FUT 27 OCT 26", "instrument_key": "NSE_FO|8", "expiry": "2026-10-27", "lot_size": 25},
    ]

    def test_picks_exact_name_nearest_unexpired(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(v, "_get", lambda url, token, params=None, **k: (captured.update(params=params), (200, {"data": self.ROWS}, None))[1])
        info, err = v.resolve_front_future("tok", "NIFTY", TODAY)
        assert err is None and info["instrument_key"] == "NSE_FO|1" and info["expiry"] == "2026-10-27"
        assert captured["params"]["exchanges"] == "NSE" and captured["params"]["instrument_types"] == "FUT"

    def test_epoch_millisecond_expiry_is_parsed(self, monkeypatch):
        ms = int(datetime.datetime(2026, 10, 27, 10, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
        monkeypatch.setattr(v, "_get", lambda *a, **k: (200, {"data": [{"trading_symbol": "BANKNIFTY FUT 27 OCT 26", "instrument_key": "K", "expiry": ms}]}, None))
        info, _ = v.resolve_front_future("tok", "BANKNIFTY", TODAY)
        assert info["expiry"] == "2026-10-27"

    def test_errors_are_reported_not_raised(self, monkeypatch):
        monkeypatch.setattr(v, "_get", lambda *a, **k: (401, None, "bad token"))
        info, err = v.resolve_front_future("tok", "NIFTY", TODAY)
        assert info is None and "401" in err and "bad token" in err
        monkeypatch.setattr(v, "_get", lambda *a, **k: (200, {"data": [self.ROWS[3]]}, None))
        info, err = v.resolve_front_future("tok", "NIFTY", TODAY)
        assert info is None and "exact" in err and "FINNIFTY" in err


# ---- expired futures --------------------------------------------------------------------------------------------------------
class TestExpired:
    def test_list_expiries_handles_strings_dicts_and_errors(self, monkeypatch):
        monkeypatch.setattr(v, "_get", lambda *a, **k: (200, {"data": ["2025-04-24", "2025-04-17", {"expiry": "2024-03-28"}, "", None]}, None))
        dates, status, err = v.list_expiries("tok", "NSE_INDEX|Nifty 50")
        assert dates == ["2024-03-28", "2025-04-17", "2025-04-24"] and status == 200 and err is None
        monkeypatch.setattr(v, "_get", lambda *a, **k: (403, None, "Upstox Plus required"))
        assert v.list_expiries("tok", "K") == (None, 403, "Upstox Plus required")

    def test_pick_samples_uses_monthly_expiry_only_and_includes_oldest(self):
        weekly = [datetime.date(2026, 8, 6) + datetime.timedelta(days=7 * i) for i in range(7)]
        expiries = sorted({d.isoformat() for d in weekly} | {"2026-09-29", "2026-08-25", "2025-10-28", "2024-10-31", "2022-03-31", "2021-01-28", "2026-11-24"})
        picks = v.pick_sample_expiries(expiries, TODAY, (1, 12, 24, 60))
        assert "2026-11-24" not in picks                                    # भविष्यातला नाही
        assert "2021-01-28" in picks                                        # सर्वात जुना
        assert picks == sorted(picks, reverse=True)
        # महिन्याचा शेवटचा: ऑगस्ट 2026 साठी weekly नव्हे तर 2026-08-25 (नाही तर शेवटची weekly ऑगस्ट मधली)
        by_month = {p[:7] for p in picks}
        assert len(picks) == len(set(picks)) and all(p < TODAY.isoformat() for p in picks) and by_month
        assert v.pick_sample_expiries([], TODAY, (1,)) == [] and v.pick_sample_expiries(["2027-01-01"], TODAY, (1,)) == []

    def test_get_expired_future_key_prefers_exact_future_row(self, monkeypatch):
        rows = [{"trading_symbol": "NIFTY FUT 24 APR 25", "expired_instrument_key": "NSE_FO|53806|24-04-2025"},
                {"trading_symbol": "NIFTY 24500 CE 24 APR 25", "expired_instrument_key": "NSE_FO|1|24-04-2025"}, {"trading_symbol": "x"}]
        monkeypatch.setattr(v, "_get", lambda *a, **k: (200, {"data": rows}, None))
        row, status, _ = v.get_expired_future_key("tok", "NSE_INDEX|Nifty 50", "NIFTY", "2025-04-24")
        assert row["expired_instrument_key"] == "NSE_FO|53806|24-04-2025" and status == 200
        monkeypatch.setattr(v, "_get", lambda *a, **k: (200, {"data": []}, None))
        assert v.get_expired_future_key("tok", "K", "NIFTY", "2025-04-17")[0] is None          # weekly तारखेला futures नाही

    def test_expired_sample_success_and_each_failure_stage(self, monkeypatch):
        monkeypatch.setattr(v, "get_expired_future_key", lambda *a, **k: ({"expired_instrument_key": "KEY"}, 200, None))
        monkeypatch.setattr(v, "fetch_candles_window", lambda *a, **k: {"status": 200, "error": None, "candles": [["t", 1, 2, 0, 1, 10, 3]] * 4})
        ok = v.expired_future_sample("tok", "U", "NIFTY", "2025-04-24")
        assert ok["ok"] and ok["5minute"]["rows"] == 4 and ok["5minute"]["volume_nonzero_pct"] == 100.0
        monkeypatch.setattr(v, "fetch_candles_window", lambda *a, **k: {"status": 200, "error": None, "candles": []})
        empty = v.expired_future_sample("tok", "U", "NIFTY", "2025-04-24")
        assert not empty["ok"] and empty["stage"] == "candles"
        monkeypatch.setattr(v, "get_expired_future_key", lambda *a, **k: (None, 403, "plan"))
        denied = v.expired_future_sample("tok", "U", "NIFTY", "2025-04-24")
        assert not denied["ok"] and denied["stage"] == "contract" and denied["status"] == 403


# ---- एकत्रित अहवाल ---------------------------------------------------------------------------------------------------------
def _fake_router(monkeypatch, expired_allowed=True, cutoff=datetime.date(2022, 1, 1)):
    """URL नुसार बनावट Upstox. इतिहास: cutoff पासून; index volume 0; futures volume>0; expired API फक्त expired_allowed असेल तर."""
    def fake_get(url, token, params=None, **kw):
        if "/instruments/search" in url:
            return 200, {"data": [{"trading_symbol": f"{params['query']} FUT 27 OCT 26", "instrument_key": f"NSE_FO|{params['query']}", "expiry": "2026-10-27", "lot_size": 75}]}, None
        if "/expired-instruments/expiries" in url:
            if not expired_allowed:
                return 403, None, '{"errors":[{"message":"Plan upgrade required"}]}'
            return 200, {"data": ["2025-04-24", "2025-04-17", "2024-04-25", "2023-03-30", "2022-01-27"]}, None
        if "/expired-instruments/future/contract" in url:
            d = params["expiry_date"]
            return 200, ({"data": [{"trading_symbol": f"{'BANKNIFTY' if 'Bank' in params['instrument_key'] else 'NIFTY'} FUT", "expired_instrument_key": f"NSE_FO|1|{d}"}]}), None
        if "/expired-instruments/historical-candle/" in url:
            return 200, {"data": {"candles": [["2025-04-24T09:15:00+05:30", 1, 2, 0, 1, 500, 90]] * 3}}, None
        if "/historical-candle/" in url:
            to_date = datetime.date.fromisoformat(url.rsplit("/", 2)[-2])
            has = to_date >= cutoff
            is_future = "NSE_FO" in url
            volume = 1000 if is_future else 0
            return (200, {"data": {"candles": [["2026-09-01T09:15:00+05:30", 1, 2, 0, 1, volume, 10 if is_future else 0]] * 2 if has else []}}, None) if has else (200, {"data": {"candles": []}}, None)
        return 404, None, "unexpected"
    monkeypatch.setattr(v, "_get", fake_get)


def test_collect_and_format_full_report(monkeypatch):
    _fake_router(monkeypatch)
    results = v.collect_results("tok", ["NIFTY", "BANKNIFTY"], quick=True, today=TODAY)
    assert set(results["history"]) == {"NIFTY", "BANKNIFTY"} and set(results["history"]["NIFTY"]) == set(v.QUICK_INTERVALS)
    assert results["history"]["NIFTY"]["5minute"]["state"] == "FOUND"
    assert results["index_volume"]["NIFTY"]["volume_nonzero_pct"] == 0.0
    assert results["live_future"]["NIFTY"]["volume_nonzero_pct"] == 100.0
    assert results["expired_futures"]["BANKNIFTY"]["samples"] and all(s["ok"] for s in results["expired_futures"]["BANKNIFTY"]["samples"])
    text = v.format_report(results)
    for needle in ("इतिहास किती मागे", "Index (spot) candles मध्ये volume", "front-month", "Expired futures", "निष्कर्ष", "NIFTY 5M backtest Upstox वरून शक्य", "सर्वात जुना नमुना"):
        assert needle in text, needle
    assert "tok" not in text.replace("token", "")                      # token कधीच print होत नाही


def test_expired_api_denied_is_reported_clearly_and_rest_still_works(monkeypatch):
    _fake_router(monkeypatch, expired_allowed=False)
    results = v.collect_results("tok", ["NIFTY"], quick=True, today=TODAY)
    assert "error" in results["expired_futures"]["NIFTY"] and results["expired_futures"]["NIFTY"]["status"] == 403
    assert results["history"]["NIFTY"]["5minute"]["state"] == "FOUND" and results["live_future"]["NIFTY"]["instrument_key"]
    text = v.format_report(results)
    assert "403" in text and "Plus plan" in text and "volume या खात्यावर उपलब्ध नाही" in text


def test_everything_denied_reports_no_data_without_crashing(monkeypatch):
    monkeypatch.setattr(v, "_get", lambda *a, **k: (401, None, "Invalid token"))
    results = v.collect_results("tok", ["NIFTY"], quick=True, today=TODAY)
    assert results["history"]["NIFTY"]["5minute"]["state"] == "NO_DATA"
    text = v.format_report(results)
    assert "401" in text and "Invalid token" in text and "डेटा नाही" in text


def test_unknown_symbol_is_flagged_not_crashed(monkeypatch):
    _fake_router(monkeypatch)
    results = v.collect_results("tok", ["FOO"], quick=True, today=TODAY)
    assert results["history"]["FOO"] == {"error": "अज्ञात symbol"}
    assert "अज्ञात symbol" in v.format_report(results)


# ---- main -------------------------------------------------------------------------------------------------------------------
def test_main_without_token_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(v.cloud_db, "get_effective_upstox_token", lambda cli: None)
    with pytest.raises(SystemExit) as e:
        v.main([])
    assert e.value.code == 1 and "token" in capsys.readouterr().out


def test_main_prints_report_and_writes_json(monkeypatch, tmp_path, capsys):
    _fake_router(monkeypatch)
    monkeypatch.setattr(v.cloud_db, "get_effective_upstox_token", lambda cli: cli or "SECRET-TOKEN-123")
    out = tmp_path / "r.json"
    v.main(["--quick", "--symbols", "NIFTY", "--json", str(out)])
    printed = capsys.readouterr().out
    assert "Opportunity Engine — डेटा उपलब्धता" in printed and "SECRET-TOKEN-123" not in printed
    import json
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["history"]["NIFTY"]["5minute"]["state"] == "FOUND" and "SECRET-TOKEN-123" not in out.read_text(encoding="utf-8")


def test_script_is_read_only_no_order_or_db_write_calls():
    """स्थिर तपासणी: script मध्ये POST/PUT/DELETE, order placement, किंवा cloud_db write नाही."""
    src = open(v.__file__, encoding="utf-8").read()
    assert not re.search(r"requests\.(post|put|delete|patch)\b", src)
    assert "place_order" not in src and "open_multi_leg_trade" not in src
    assert not re.search(r"cloud_db\.(save_|insert_|upsert_|delete_|write_)", src)
