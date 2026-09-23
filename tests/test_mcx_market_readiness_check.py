"""
tests/test_mcx_market_readiness_check.py
--------------------------------
mcx_market_readiness_check.py — MCX LIVE करण्याआधी resolver/zones/token च्या तपासण्या बरोबर
काम करतात का, आणि कुठलीही समस्या असो-नसो नेहमी Telegram अलर्ट पाठवला जातो का (रोजचा run न चुकता
झाल्याची खात्री) — याची पडताळणी. सर्व external कॉल्स (resolve_symbol/get_market_zones/
get_total_capital/send_telegram_message) mock केलेले.
"""
import pandas as pd
import pytest

import mcx_market_readiness_check as readiness


class TestCheckResolver:
    def test_returns_result_per_symbol(self, monkeypatch):
        def fake_resolve(token, symbol):
            if symbol == "GOLD":
                return False, "not found"
            return True, {"symbol": symbol, "trading_symbol": f"{symbol} FUT", "lot_size": 100, "tick_size": 1.0, "expiry": "2026-10-30"}

        monkeypatch.setattr(readiness.mcx_resolver, "resolve_symbol", fake_resolve)
        results = readiness.check_resolver("tok", ["CRUDEOIL", "GOLD"])
        assert results["CRUDEOIL"][0] is True
        assert results["GOLD"][0] is False


class TestCheckZones:
    def test_ok_when_active_zones_exist(self, monkeypatch):
        df = pd.DataFrame([
            {"symbol": "CRUDEOIL", "zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": 100, "zone_high": 100, "strength": 2, "formed_date": "2026-09-23", "status": "ACTIVE"},
            {"symbol": "CRUDEOIL", "zone_type": "DYNAMIC_SR_RESISTANCE_60M", "zone_low": 110, "zone_high": 110, "strength": 1, "formed_date": "2026-09-23", "status": "ACTIVE"},
        ])
        monkeypatch.setattr(readiness.cloud_db, "get_market_zones", lambda symbol, status=None: df)
        results = readiness.check_zones(["CRUDEOIL"])
        assert results["CRUDEOIL"]["ok"] is True
        assert results["CRUDEOIL"]["counts"]["30M"] == 1
        assert results["CRUDEOIL"]["counts"]["60M"] == 1
        assert results["CRUDEOIL"]["total"] == 2

    def test_not_ok_when_no_zones(self, monkeypatch):
        monkeypatch.setattr(readiness.cloud_db, "get_market_zones", lambda symbol, status=None: pd.DataFrame())
        results = readiness.check_zones(["GOLD"])
        assert results["GOLD"]["ok"] is False
        assert results["GOLD"]["total"] == 0

    def test_not_ok_when_none_returned(self, monkeypatch):
        """cloud_db.get_market_zones() Supabase जोडणी नसेल तर None रिटर्न करतो — crash न होता 'ok=False' हवं."""
        monkeypatch.setattr(readiness.cloud_db, "get_market_zones", lambda symbol, status=None: None)
        results = readiness.check_zones(["SILVER"])
        assert results["SILVER"]["ok"] is False


class TestCheckToken:
    def test_no_token(self):
        ok, detail = readiness.check_token(None)
        assert ok is False
        assert "token" in detail

    def test_valid_token(self, monkeypatch):
        monkeypatch.setattr(readiness, "get_total_capital", lambda tok: 500000.0)
        ok, detail = readiness.check_token("tok")
        assert ok is True
        assert detail == 500000.0

    def test_invalid_token_zero_capital(self, monkeypatch):
        monkeypatch.setattr(readiness, "get_total_capital", lambda tok: None)
        ok, detail = readiness.check_token("tok")
        assert ok is False

    def test_exception_handled(self, monkeypatch):
        def _boom(tok):
            raise ConnectionError("network down")
        monkeypatch.setattr(readiness, "get_total_capital", _boom)
        ok, detail = readiness.check_token("tok")
        assert ok is False
        assert "चूक" in detail


class TestBuildReport:
    def test_no_problem_when_all_ok(self):
        resolver_results = {"CRUDEOIL": (True, {"trading_symbol": "CRUDEOIL FUT", "lot_size": 100, "tick_size": 1.0, "expiry": "2026-10-30"})}
        zone_results = {"CRUDEOIL": {"ok": True, "counts": {"30M": 2, "60M": 1}, "total": 3}}
        token_result = (True, 500000.0)
        report, any_problem = readiness.build_report(resolver_results, zone_results, token_result)
        assert any_problem is False
        assert "✅" in report
        assert "CRUDEOIL" in report

    def test_problem_when_resolver_fails(self):
        resolver_results = {"GOLD": (False, "not found")}
        zone_results = {"GOLD": {"ok": True, "counts": {"30M": 1, "60M": 1}, "total": 2}}
        token_result = (True, 500000.0)
        _, any_problem = readiness.build_report(resolver_results, zone_results, token_result)
        assert any_problem is True

    def test_problem_when_zones_missing(self):
        resolver_results = {"SILVER": (True, {"trading_symbol": "SILVER FUT", "lot_size": 30, "tick_size": 1.0, "expiry": "2026-10-30"})}
        zone_results = {"SILVER": {"ok": False, "counts": {"30M": 0, "60M": 0}, "total": 0}}
        token_result = (True, 500000.0)
        _, any_problem = readiness.build_report(resolver_results, zone_results, token_result)
        assert any_problem is True

    def test_problem_when_token_invalid(self):
        resolver_results = {}
        zone_results = {}
        token_result = (False, "token expired")
        _, any_problem = readiness.build_report(resolver_results, zone_results, token_result)
        assert any_problem is True


class TestRunReadinessCheck:
    def _mock_all_ok(self, monkeypatch):
        monkeypatch.setattr(readiness, "get_total_capital", lambda tok: 500000.0)
        monkeypatch.setattr(readiness.mcx_resolver, "resolve_symbol", lambda tok, sym: (True, {"trading_symbol": f"{sym} FUT", "lot_size": 100, "tick_size": 1.0, "expiry": "2026-10-30"}))
        df = pd.DataFrame([{"symbol": "X", "zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": 1, "zone_high": 1, "strength": 1, "formed_date": "2026-09-23", "status": "ACTIVE"}])
        monkeypatch.setattr(readiness.cloud_db, "get_market_zones", lambda symbol, status=None: df)

    def test_always_sends_telegram_even_when_ok(self, monkeypatch):
        self._mock_all_ok(monkeypatch)
        telegram_calls = []
        monkeypatch.setattr(readiness, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        printed = []
        any_problem = readiness.run_readiness_check("tok", ["CRUDEOIL"], print_fn=printed.append)
        assert any_problem is False
        assert len(telegram_calls) == 1
        assert "🟢" in telegram_calls[0]

    def test_sends_telegram_with_problem_marker_when_issue_found(self, monkeypatch):
        monkeypatch.setattr(readiness, "get_total_capital", lambda tok: None)  # token अवैध
        monkeypatch.setattr(readiness.cloud_db, "get_market_zones", lambda symbol, status=None: pd.DataFrame())
        telegram_calls = []
        monkeypatch.setattr(readiness, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        any_problem = readiness.run_readiness_check("tok", ["CRUDEOIL"], print_fn=lambda x: None)
        assert any_problem is True
        assert "🔴" in telegram_calls[0]

    def test_no_alert_when_send_alert_false(self, monkeypatch):
        self._mock_all_ok(monkeypatch)
        telegram_calls = []
        monkeypatch.setattr(readiness, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        readiness.run_readiness_check("tok", ["CRUDEOIL"], print_fn=lambda x: None, send_alert=False)
        assert telegram_calls == []

    def test_telegram_failure_does_not_crash(self, monkeypatch):
        self._mock_all_ok(monkeypatch)

        def _boom(msg):
            raise ConnectionError("telegram down")
        monkeypatch.setattr(readiness, "send_telegram_message", _boom)
        printed = []
        any_problem = readiness.run_readiness_check("tok", ["CRUDEOIL"], print_fn=printed.append)
        assert any_problem is False  # टेलिग्राम अपयशी झाला तरी प्रत्यक्ष readiness-निकालावर परिणाम नाही
        assert any("Telegram" in p for p in printed)

    def test_resolver_skipped_when_token_invalid(self, monkeypatch):
        """token अवैध असेल तर resolve_symbol() ला कधीच call करू नये (उगाच API hits वाया घालवू नयेत)."""
        monkeypatch.setattr(readiness, "get_total_capital", lambda tok: None)
        monkeypatch.setattr(readiness.cloud_db, "get_market_zones", lambda symbol, status=None: pd.DataFrame())

        def _boom(tok, sym):
            raise AssertionError("token अवैध असताना resolve_symbol() call व्हायला नको होतं")
        monkeypatch.setattr(readiness.mcx_resolver, "resolve_symbol", _boom)
        monkeypatch.setattr(readiness, "send_telegram_message", lambda msg: None)
        readiness.run_readiness_check("tok", ["CRUDEOIL"], print_fn=lambda x: None)
