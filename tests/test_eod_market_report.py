"""
tests/test_eod_market_report.py
------------------------------------
eod_market_report.py — दररोज दुपारी ४ वाजताचा, तिन्ही symbols साठी EOD Market Report (PDF+Telegram).
"""
import os
import tempfile

import numpy as np
import pandas as pd

import database
import eod_market_report as eod
import market_report


def _fake_chain(token, symbol):
    strikes = list(range(24200, 24800, 50))
    chain = []
    for k in strikes:
        chain.append({
            "strike_price": k, "underlying_spot_price": 24500,
            "call_options": {"instrument_key": f"CE{k}", "market_data": {"ltp": 50.0, "oi": 10000}},
            "put_options": {"instrument_key": f"PE{k}", "market_data": {"ltp": 45.0, "oi": 12000}},
        })
    return chain, "OK"


def _fake_candles(token, symbol, spot, interval="15minute"):
    np.random.seed(3)
    n = 80
    walk = 24000 + np.cumsum(np.random.randn(n) * 15)
    freq = "15min" if interval == "15minute" else ("30min" if interval == "30minute" else "1D")
    dates = pd.date_range("2026-08-27 09:15", periods=n, freq=freq)
    return pd.DataFrame({"timestamp": dates, "open": walk, "close": walk + 2, "high": walk + 8, "low": walk - 8, "volume": 1000})


class TestRunReport:
    def _setup(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        monkeypatch.setattr(market_report, "DB_PATH", tmpdb)
        monkeypatch.setattr(eod, "fetch_upstox_option_chain", _fake_chain)
        monkeypatch.setattr(eod, "fetch_candles", _fake_candles)
        monkeypatch.setattr(eod, "fetch_india_vix", lambda t: 15.5)
        monkeypatch.setattr(eod, "send_telegram_message", lambda msg: False)
        reports_dir = tempfile.mkdtemp()
        monkeypatch.setattr(eod, "REPORTS_DIR", reports_dir)
        return reports_dir

    def test_full_report_generates_pdf_and_sends_telegram(self, monkeypatch):
        sent = []
        monkeypatch.setattr(eod, "fetch_upstox_option_chain", _fake_chain)
        reports_dir = self._setup(monkeypatch)
        monkeypatch.setattr(eod, "send_telegram_message", lambda msg: sent.append(msg) or False)

        result = eod.run_report("fake_token", "PAPER")
        assert "✅" in result
        assert len(sent) == 1
        assert "NIFTY" in sent[0] and "SENSEX" in sent[0]

        pdf_files = [f for f in os.listdir(reports_dir) if f.endswith(".pdf")]
        assert len(pdf_files) == 1

    def test_non_trading_day_skips_report(self, monkeypatch):
        import datetime
        import config
        self._setup(monkeypatch)
        monkeypatch.setattr(config, "get_ist_now", lambda: datetime.datetime(2026, 8, 29, 16, 0))  # शनिवार
        monkeypatch.setattr(eod, "is_trading_day", lambda: config.is_trading_day(config.get_ist_now()))

        result = eod.run_report("fake_token", "PAPER")
        assert "व्यापार-दिवस नाही" in result

    def test_symbol_level_data_error_does_not_crash_whole_report(self, monkeypatch):
        """एका symbol साठी डेटा मिळवताना चूक झाली तरी, बाकीचे symbols आणि संपूर्ण PDF तयार व्हायलाच हवा."""
        reports_dir = self._setup(monkeypatch)

        def flaky_chain(token, symbol):
            if symbol == "BANKNIFTY":
                raise RuntimeError("मुद्दाम घडवलेली टेस्ट-चूक")
            return _fake_chain(token, symbol)
        monkeypatch.setattr(eod, "fetch_upstox_option_chain", flaky_chain)

        result = eod.run_report("fake_token", "PAPER")
        assert "✅" in result
        pdf_files = [f for f in os.listdir(reports_dir) if f.endswith(".pdf")]
        assert len(pdf_files) == 1
