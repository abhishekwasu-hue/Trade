"""
tests/test_oi_greeks_vix_strategy.py
-----------------------------------------
oi_greeks_vix_strategy.py — OI + Greeks + VIX एकत्रित रणनीती (वापरकर्त्याशी चर्चा करून बांधलेली).
Decision Tree: VIX>20=NoTrade, VIX 16-20=IronCondor, VIX<16+OI स्थिर=Directional Spread,
VIX<16+OI अस्पष्ट=सुरक्षित IronCondor.
"""
import sqlite3
import tempfile

import database
import oi_greeks_vix_strategy as strat
import trading_engine


def _fake_chain(token, symbol):
    strikes = list(range(23600, 25600, 50))
    chain = []
    for k in strikes:
        dist = abs(k - 24500)
        pop_val = min(0.5 + dist * 0.003, 0.97)
        chain.append({
            "strike_price": k, "underlying_spot_price": 24500,
            "put_options": {"instrument_key": f"PE{k}", "market_data": {"ltp": max(150 - (24500 - k) * 0.3, 5)}, "option_greeks": {"pop": pop_val}},
            "call_options": {"instrument_key": f"CE{k}", "market_data": {"ltp": max(150 - (k - 24500) * 0.3, 5)}, "option_greeks": {"pop": pop_val}},
        })
    return chain, "2026-08-28"


def _seed_oi_history(tmpdb, symbol, signal, count=3):
    conn = sqlite3.connect(tmpdb)
    for i, t in enumerate(["10:00", "10:10", "10:20"][:count]):
        conn.execute(
            "INSERT INTO oi_diff_snapshots (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal) VALUES (?,?,?,?,?,?,?,?)",
            (symbol, strat.get_ist_today().strftime("%Y-%m-%d"), t, 100000, 120000, 20000, 0, signal),
        )
    conn.commit()
    conn.close()


class TestDecisionTree:
    def _setup(self, monkeypatch):
        tmpdb = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(database, "DB_PATH", tmpdb)
        database.init_sqlite_db()
        monkeypatch.setattr(strat, "DB_PATH", tmpdb)
        monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
        # 🎓 दुरुस्ती — या decision-tree चाचण्या फक्त VIX/OI तर्कावर लक्ष केंद्रित करतात, बाजार-वेळेवर
        # नाही (ते market_hours चाचण्यांमध्ये स्वतंत्रपणे तपासलेलं आहे) — नाहीतर चाचण्या केव्हा चालवल्या
        # जातात त्या खऱ्या घड्याळाच्या वेळेवर अवलंबून राहून, अस्थिर (flaky) होतील.
        monkeypatch.setattr(strat, "is_market_open", lambda: True)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": {"order_ids": ["T1", "T2"]}}))
        monkeypatch.setattr(strat, "fetch_upstox_option_chain", _fake_chain)
        return tmpdb

    def test_vix_above_20_no_trade(self, monkeypatch):
        self._setup(monkeypatch)
        monkeypatch.setattr(strat, "fetch_india_vix", lambda t: 22.0)
        log = strat.run_cycle("fake_token", "NIFTY", "PAPER")
        assert "NO TRADE" in log[-1]

    def test_vix_below_16_always_uses_iron_condor_regardless_of_oi(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून उलट-पालट केलेली सुधारणा — कमी VIX (शांत बाजार) मध्ये OI काहीही
        असो, नेहमीच Iron Condor (range-bound राहण्याची शक्यता जास्त असते म्हणून)."""
        self._setup(monkeypatch)
        monkeypatch.setattr(strat, "fetch_india_vix", lambda t: 13.0)
        log = strat.run_cycle("fake_token", "NIFTY", "PAPER")  # OI इतिहास नाही, तरीही
        assert "IRON_CONDOR" in log[-1]

    def test_vix_16_to_20_stable_bullish_oi_uses_bull_put(self, monkeypatch):
        tmpdb = self._setup(monkeypatch)
        monkeypatch.setattr(strat, "fetch_india_vix", lambda t: 18.0)
        _seed_oi_history(tmpdb, "NIFTY", "🟢 BULLISH (Strong)")
        log = strat.run_cycle("fake_token", "NIFTY", "PAPER")
        assert "BULL_PUT_SPREAD" in log[-1]

    def test_vix_16_to_20_stable_bearish_oi_uses_bear_call(self, monkeypatch):
        tmpdb = self._setup(monkeypatch)
        monkeypatch.setattr(strat, "fetch_india_vix", lambda t: 18.0)
        _seed_oi_history(tmpdb, "NIFTY", "🔴 BEARISH (Strong)")
        log = strat.run_cycle("fake_token", "NIFTY", "PAPER")
        assert "BEAR_CALL_SPREAD" in log[-1]

    def test_vix_16_to_20_unclear_oi_means_no_trade_not_iron_condor(self, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — VIX 16-20 मध्ये OI अस्पष्ट असल्यास Iron Condor
        सुरक्षित डीफॉल्ट म्हणून वापरायचं नाही, स्पष्टपणे NO TRADE."""
        self._setup(monkeypatch)
        monkeypatch.setattr(strat, "fetch_india_vix", lambda t: 18.0)
        log = strat.run_cycle("fake_token", "NIFTY", "PAPER")  # OI इतिहास नाही
        assert "NO TRADE" in log[-1]
        assert "IRON_CONDOR" not in log[-1]

    def test_kill_switch_blocks_everything(self, monkeypatch, tmp_path):
        self._setup(monkeypatch)
        kill_path = str(tmp_path / "KILL_SWITCH")
        with open(kill_path, "w") as f:
            f.write("STOP")
        monkeypatch.setattr(strat, "KILL_SWITCH_PATH", kill_path)
        log = strat.run_cycle("fake_token", "NIFTY", "PAPER")
        assert "KILL SWITCH" in log[0]
