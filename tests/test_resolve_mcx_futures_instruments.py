"""
tests/test_resolve_mcx_futures_instruments.py
--------------------------------------------------------------
🎓 वापरकर्त्याने प्रत्यक्ष VPS वर `resolve_mcx_futures_instruments.py` चालवून सापडवलेली गंभीर
bug — "GOLD" शोधताना जुना `startswith()` फिल्टर "GOLDTEN" (पूर्णपणे वेगळा lot_size/tick_size
असलेला, वेगळा contract) सुद्धा जुळवायचा आणि निवडायचा. आता trading_symbol चा " FUT" च्या आधीचा भाग
query symbol शी तंतोतंत जुळायलाच हवा.
"""
from unittest.mock import MagicMock, patch

import resolve_mcx_futures_instruments as rmfi


def _mock_search_response(results):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": results}
    return resp


def _contract(trading_symbol, instrument_key, lot_size, tick_size, expiry):
    return {
        "trading_symbol": trading_symbol, "instrument_key": instrument_key,
        "lot_size": lot_size, "tick_size": tick_size, "expiry": expiry, "freeze_quantity": 100,
    }


class TestResolveSymbolExactMatch:
    def test_does_not_match_variant_contract_with_shared_prefix(self):
        """GOLD शोधताना GOLDTEN (वेगळा contract, फक्त नाव prefix जुळतो) निवडला जाऊ नये — GOLDTEN चा
        expiry GOLD पेक्षा आधी असला तरीही."""
        results = [
            _contract("GOLDTEN FUT 30 SEP 26", "MCX_FO|1", 10, 100.0, "2026-09-30"),
            _contract("GOLD FUT 31 OCT 26", "MCX_FO|2", 100, 1.0, "2026-10-31"),
        ]
        with patch.object(rmfi.requests, "get", return_value=_mock_search_response(results)), \
             patch.object(rmfi, "get_ist_today") as mock_today:
            import datetime
            mock_today.return_value = datetime.date(2026, 9, 1)
            ok, result = rmfi.resolve_symbol("fake_token", "GOLD")
            assert ok is True
            assert result["trading_symbol"] == "GOLD FUT 31 OCT 26"
            assert result["instrument_key"] == "MCX_FO|2"
            assert result["lot_size"] == 100

    def test_does_not_match_mini_variant(self):
        """CRUDEOIL शोधताना CRUDEOILM (Mini, वेगळा lot_size) निवडला जाऊ नये."""
        results = [
            _contract("CRUDEOILM FUT 21 SEP 26", "MCX_FO|1", 10, 10.0, "2026-09-21"),
            _contract("CRUDEOIL FUT 21 SEP 26", "MCX_FO|2", 100, 100.0, "2026-09-21"),
        ]
        with patch.object(rmfi.requests, "get", return_value=_mock_search_response(results)), \
             patch.object(rmfi, "get_ist_today") as mock_today:
            import datetime
            mock_today.return_value = datetime.date(2026, 9, 1)
            ok, result = rmfi.resolve_symbol("fake_token", "CRUDEOIL")
            assert ok is True
            assert result["trading_symbol"] == "CRUDEOIL FUT 21 SEP 26"
            assert result["lot_size"] == 100

    def test_no_exact_match_returns_helpful_hint_with_loose_names(self):
        """plain "GOLD" contract अस्तित्वातच नसेल (फक्त variants), तर स्पष्ट अयशस्वी व्हायला हवं —
        चुकीचा variant शांतपणे निवडला जाऊ नये — आणि error मध्ये जवळची नावं दिसायला हवीत."""
        results = [_contract("GOLDTEN FUT 30 SEP 26", "MCX_FO|1", 10, 100.0, "2026-09-30")]
        with patch.object(rmfi.requests, "get", return_value=_mock_search_response(results)), \
             patch.object(rmfi, "get_ist_today") as mock_today:
            import datetime
            mock_today.return_value = datetime.date(2026, 9, 1)
            ok, result = rmfi.resolve_symbol("fake_token", "GOLD")
            assert ok is False
            assert "GOLDTEN" in result

    def test_picks_nearest_expiry_among_exact_matches_only(self):
        results = [
            _contract("SILVER FUT 30 NOV 26", "MCX_FO|1", 100, 1.0, "2026-11-30"),
            _contract("SILVER FUT 30 SEP 26", "MCX_FO|2", 100, 1.0, "2026-09-30"),
            _contract("SILVERM FUT 15 SEP 26", "MCX_FO|3", 5, 1.0, "2026-09-15"),  # वेगळाच variant, आधीचा expiry
        ]
        with patch.object(rmfi.requests, "get", return_value=_mock_search_response(results)), \
             patch.object(rmfi, "get_ist_today") as mock_today:
            import datetime
            mock_today.return_value = datetime.date(2026, 9, 1)
            ok, result = rmfi.resolve_symbol("fake_token", "SILVER")
            assert ok is True
            assert result["instrument_key"] == "MCX_FO|2"
            assert result["expiry"] == "2026-09-30"

    def test_already_expired_contract_excluded(self):
        results = [_contract("COPPER FUT 30 AUG 26", "MCX_FO|1", 2500, 5.0, "2026-08-30")]
        with patch.object(rmfi.requests, "get", return_value=_mock_search_response(results)), \
             patch.object(rmfi, "get_ist_today") as mock_today:
            import datetime
            mock_today.return_value = datetime.date(2026, 9, 1)
            ok, result = rmfi.resolve_symbol("fake_token", "COPPER")
            assert ok is False

    def test_http_error_returns_false(self):
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"
        with patch.object(rmfi.requests, "get", return_value=resp):
            ok, result = rmfi.resolve_symbol("fake_token", "GOLD")
            assert ok is False
            assert "500" in result
