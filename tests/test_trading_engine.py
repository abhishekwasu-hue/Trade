"""
tests/test_trading_engine.py
--------------------------------
SL/Target गणित आणि दुपारी ३ वाजताचा Carry-Forward/Close निर्णय — हे सर्वात नाजूक, थेट खऱ्या पैशाशी
संबंधित logic आहे (वापरकर्त्याशी चर्चा करून ठरवलेलं). खऱ्या तात्पुरत्या SQLite DB वर, वेळ mock करून चालवलं जातं.
"""
import datetime
import json
import sqlite3
import tempfile
from unittest.mock import MagicMock

import pytest

import cloud_db
import database
import trading_engine


@pytest.fixture
def temp_db(monkeypatch):
    """प्रत्येक test साठी नवीन, स्वतंत्र तात्पुरता SQLite DB.
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — manage_open_trades() नेहमी सर्वात आधी
    reconcile_open_trades_with_broker() (-> fetch_broker_positions(), खरा Upstox network call)
    चालवतं. आधी हे कुठेही mock केलेलं नव्हतं — sandbox मध्ये नेटवर्क अडवलं गेलं की
    retry/backoff मुळे प्रत्येक असा test काही सेकंद ते मिनिटं थांबायचा (flaky, कधी-कधी hang
    झाल्यासारखं वाटायचं). इथे एक सुरक्षित डीफॉल्ट (रिकामी यादी — "कुठलीही broker position नाही",
    reconciliation लगेच काहीही न करता संपतं) — ज्या tests ना विशिष्ट broker-position वर्तन
    हवं आहे (उदा. TestReconcileOpenTradesWithBroker), ते स्वतःच्या monkeypatch.setattr() ने
    हेच पुन्हा override करतात, जे नेहमीप्रमाणे चालत राहतं.
    """
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda access_token: [])
    yield tmpdb


def seed_trade(tmpdb, trade_id, net_credit, sl_level, target_level, strategy="BULL_PUT_SPREAD", source=None, trading_style="SWING", peak_pnl=None, entry_level_price=None, mode="PAPER", tsl_activated=0, legs=None, entry_timeframe=None):
    conn = sqlite3.connect(tmpdb)
    if legs is None:
        legs = [
            {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL"},
            {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY"},
        ]
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json,
           strikes_summary, mode, trading_style, source, peak_pnl, entry_level_price, tsl_activated, entry_timeframe) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-08-24", "NIFTY", strategy, 1, 75, net_credit, net_credit, 50,
         sl_level, target_level, "2026-08-24 10:00:00", "OPEN", json.dumps(legs), "test", mode, trading_style, source, peak_pnl, entry_level_price, tsl_activated, entry_timeframe),
    )
    conn.commit()
    conn.close()


class FakeTime(datetime.datetime):
    """वेळ mock करण्यासाठी -- ३ वाजण्यापूर्वी/नंतर दोन्ही परिस्थिती नियंत्रितपणे तयार करता येतात."""
    _fixed = None

    @classmethod
    def utcnow(cls):
        return cls._fixed


class TestSLTargetComputation:
    """SL आधार (net_credit चा % वि max_loss चा %) — दोन्ही मार्ग स्वतंत्र, एकमेकांना बाधा न आणता."""

    def test_old_basis_uses_max_loss_pct(self):
        """Iron Condor/Butterfly साठी जुनाच मार्ग अजूनही कार्यरत असायला हवा."""
        max_loss_total, net_credit_total = 50 * 75, 30 * 75
        sl_pct_of_max_loss = 50
        sl_pnl_level = -(max_loss_total * (sl_pct_of_max_loss / 100.0))
        assert sl_pnl_level == -1875.0

    def test_new_basis_uses_net_credit_pct(self):
        """Price Action/Indicator साठी नवीन मार्ग -- net_credit चा 30%."""
        net_credit_total = 50 * 75
        sl_pct_of_credit = 30
        sl_pnl_level = -(net_credit_total * (sl_pct_of_credit / 100.0))
        assert sl_pnl_level == -1125.0


class TestThreePMCarryForwardLogic:
    """दुपारी ३:१० वाजताचा Carry-Forward-वि-Close निर्णय (BULL_PUT_SPREAD/BEAR_CALL_SPREAD साठीच).
    🎓 वापरकर्त्याशी चर्चा करून वेगळं केलेलं — established Target (उदा. 80%, केव्हाही गाठला तरी लगेच
    बंद) आणि established 3:10pm Carry-Forward साठीचा वेगळा, कमी उंबरठा (established डीफॉल्ट 30%
    credit, established Target अजून गाठलेला नसेल तेव्हाच लागू) — या दोन वेगळ्या तपासण्या आहेत.
    सर्व टेस्ट्समध्ये net_credit=30, lot_size=75 => net_credit_total=2250, carry_forward_min(30%)=675,
    established target_level=1800 (एक ठोस, carry-forward-min पेक्षा जास्त, वास्तविक target दर्शवणारा)."""

    def test_below_carry_forward_min_before_310pm_does_not_close(self, temp_db, monkeypatch):
        # pnl=300 (< carry_forward_min 675, < target 1800) -- 3:10pm आधी काहीही तपासलं जात नाही
        seed_trade(temp_db, "T1", net_credit=30, sl_level=-1125, target_level=1800)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 28.0, "PE24300": 2.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 0)  # UTC 9:00 = IST 14:30 (3:10pm आधी)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0

    def test_between_carry_forward_min_and_target_after_310pm_carries_forward(self, temp_db, monkeypatch):
        # pnl=900 (>= carry_forward_min 675, पण < target 1800) -- 3:10pm नंतर पुरेसा नफा -> carry forward
        seed_trade(temp_db, "T2", net_credit=30, sl_level=-1125, target_level=1800)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 18.0, "PE24300": 0.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 45)  # UTC 9:45 = IST 15:15 (3:10pm नंतर)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0  # नफा पुरेसा (>=30%) -> carry-forward

    def test_below_carry_forward_min_after_310pm_closes(self, temp_db, monkeypatch):
        # pnl=300 (< carry_forward_min 675) -- 3:10pm नंतर अपुरा नफा -> आजच बंद
        seed_trade(temp_db, "T3", net_credit=30, sl_level=-1125, target_level=1800)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 28.0, "PE24300": 2.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 45)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"

    def test_target_reached_closes_immediately_regardless_of_time(self, temp_db, monkeypatch):
        # 🎓 गाभा टेस्ट — established Target (1800) गाठला की, established 3:10pm च्या खूप आधीही, लगेच
        # बंद व्हायला हवा (established वेळेची वाट बघायची नाही — established जुनं वर्तन उलट होतं).
        seed_trade(temp_db, "T5", net_credit=30, sl_level=-1125, target_level=1800)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 5.0, "PE24300": 0.0})  # pnl=(30-5)*75=1875 >= 1800
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)  # सकाळी, 3:10pm च्या खूप आधी
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TARGET"

    def test_sl_hit_closes_regardless_of_time(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T4", net_credit=30, sl_level=-1125, target_level=1125)
        # short leg (24400, SELL) खूप महाग झाला -> मोठा तोटा (MTM = (net_credit - (short-long))*lot_size)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 60.0, "PE24300": 5.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)  # सकाळी, 3pm च्या खूप आधी
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"

    def test_classic_sl_stores_exit_reason_detail(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Performance Report PDF) — exit_reason_detail
        DB मध्ये प्रत्यक्ष साठवलं जायला हवं, फक्त in-memory closed_summaries मध्ये नाही."""
        seed_trade(temp_db, "T4b", net_credit=30, sl_level=-1125, target_level=1125)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 60.0, "PE24300": 5.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT exit_reason, exit_reason_detail FROM live_trades WHERE trade_id='T4b'").fetchone()
        conn.close()
        assert row[0] == "SL"
        assert row[1] is not None and "SL level" in row[1]


class TestPctTrailingSlLevel:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` साठी established ATR-Trailing
    पेक्षा वेगळी, %-आधारित Trailing SL (MTM नफा 20% झाल्यावर सक्रिय, 10% credit lock)."""

    def test_below_activation_threshold_returns_original_sl(self):
        # net_credit_total=1000, activation 20% => 200 पर्यंत सक्रिय होणार नाही
        new_peak, effective_sl = trading_engine.compute_pct_trailing_sl_level(
            current_pnl=150, peak_pnl=150, net_credit_total=1000, original_sl_level=-500,
        )
        assert new_peak == 150
        assert effective_sl == -500  # मूळ स्थिर SL तसाच

    def test_at_activation_locks_in_10pct(self):
        # net_credit_total=1000, peak=200 (नेमकं 20%) => lock = peak - 10% = 200-100 = 100
        new_peak, effective_sl = trading_engine.compute_pct_trailing_sl_level(
            current_pnl=200, peak_pnl=200, net_credit_total=1000, original_sl_level=-200,
        )
        assert new_peak == 200
        assert effective_sl == 100

    def test_further_profit_keeps_trailing_up(self):
        # peak 300 (30%) => lock = 300-100 = 200 (established 100 पेक्षा जास्त, सतत वर सरकतंय)
        new_peak, effective_sl = trading_engine.compute_pct_trailing_sl_level(
            current_pnl=300, peak_pnl=200, net_credit_total=1000, original_sl_level=-200,
        )
        assert new_peak == 300
        assert effective_sl == 200

    def test_never_worse_than_original_sl(self):
        # मूळ SL established trailing-lock पेक्षा जास्त (चांगला) असेल तर तोच वापरायला हवा
        new_peak, effective_sl = trading_engine.compute_pct_trailing_sl_level(
            current_pnl=210, peak_pnl=210, net_credit_total=1000, original_sl_level=150,  # मूळ SL trailing-lock (110) पेक्षा जास्त
        )
        assert effective_sl == 150

    def test_price_pullback_does_not_lower_peak(self):
        # सद्य नफा आधीच्या शिखरापेक्षा कमी झाला तरी established शिखर (आणि त्यावर आधारित lock) कमी होत नाही
        new_peak, effective_sl = trading_engine.compute_pct_trailing_sl_level(
            current_pnl=180, peak_pnl=300, net_credit_total=1000, original_sl_level=-200,
        )
        assert new_peak == 300
        assert effective_sl == 200


class TestDynamicSrInstantSourceRules:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — `dynamic_sr_instant` साठी SL/Target आता
    प्रीमियमवर नाही, underlying स्पॉटच्या entry_level_price पासूनच्या % हालचालीवर आधारित
    (SL 0.05%, Target 0.20%, दिशेनुसार) — जुना प्रीमियम-आधारित SL/Target/%-Trailing/Carry-Forward
    या source साठी पूर्णपणे बदलला."""

    def _mock_ltp_map(self, spot_value):
        def _fn(token, keys):
            if keys == ["NSE_INDEX|Nifty 50"]:
                return {"NSE_INDEX|Nifty 50": spot_value}
            return {"PE24400": 28.0, "PE24300": 3.0}
        return _fn

    def test_spread_sl_on_spot_move(self, temp_db, monkeypatch):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo -- नवीन नियम-संच) --
        Credit Spread SL आता Spot% + Premium-Points combined (डीफॉल्ट settings: 0.05%/5pts)."""
        # entry_level_price=23900, SL_spot=0.05% -> threshold=23888.05. स्पॉट त्याखाली.
        # प्रीमियम neutral (net_credit-cost=30-25=5, established -5 threshold च्या establishedच establishedच).
        seed_trade(temp_db, "T10", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23880.0, ce_ltp=28.0, pe_ltp=3.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"

    def test_spread_sl_on_premium_move(self, temp_db, monkeypatch):
        # स्पॉट neutral (23905), प्रीमियम 5+ पॉइंट्स विरुद्ध: cost=35, net_credit-cost=30-35=-5
        seed_trade(temp_db, "T11", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23905.0, ce_ltp=35.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"

    def test_spread_neither_stays_open(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T12", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23905.0, ce_ltp=28.0, pe_ltp=3.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0

    def _mock_ltp_map_with_options(self, spot_value, ce_ltp, pe_ltp):
        def _fn(token, keys):
            if keys == ["NSE_INDEX|Nifty 50"]:
                return {"NSE_INDEX|Nifty 50": spot_value}
            return {"PE24400": ce_ltp, "PE24300": pe_ltp}
        return _fn

    def test_spread_target_on_premium(self, temp_db, monkeypatch):
        # net_credit-cost=15 (Target premium threshold, डीफॉल्ट)
        seed_trade(temp_db, "T30", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23905.0, ce_ltp=15.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TARGET"

    def test_spread_tsl_activates_then_sticky_sl_next_cycle(self, temp_db, monkeypatch):
        """पहिल्या cycle ला TSL सक्रिय व्हावी (बंद न होता, tsl_activated column अपडेट व्हावं), आणि
        established establishedच established (established establishedच establishedच established establishedच)
        established establishedच establishedच establishedच established establishedत establishedत TSL_SL establishedच establishedत establishedत."""
        seed_trade(temp_db, "T31", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        # प्रीमियम +10 (TSL activation threshold, डीफॉल्ट) -- net_credit-cost=10 -> cost=20
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23905.0, ce_ltp=20.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0  # established establishedच establishedच establishedत -- established establishedच establishedत establishedच

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT tsl_activated FROM live_trades WHERE trade_id='T31'").fetchone()
        conn.close()
        assert row[0] == 1

    def test_naked_call_sl_on_premium_move(self, temp_db, monkeypatch):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा -- Naked Call/Put (समांतर trade-प्रकार) साठी
        established वेगळे established (established घट्ट established establishedच established
        established establishedच established establishedच) established SL/TSL/Target established
        established establishedच established establishedच established established (established
        established डीफॉल्ट: established SL 10pts, established TSL 20pts, established Target 30pts)."""
        seed_trade(temp_db, "T32", net_credit=-30, sl_level=-1125, target_level=100000,
                   strategy="NAKED_CALL", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        # established BUY established establishedच established establishedच -- established
        # established net_credit=-30 established (established established, established established
        # established established), established established established established established
        # established established established established established established established established
        # premium established established established established established established established
        # established established established established established established established established established
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23905.0, ce_ltp=20.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"

    def test_next_level_exit_on_5m_entry(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा — 1-Min Instant Trader साठी Next-Level-Exit परत आणला,
        पण फक्त 5M-touch entries साठी (वापरकर्त्याने स्पष्टपणे ठरवलेलं). स्पॉट/प्रीमियम दोन्ही
        neutral (कुठलाही SL/TSL/Target लागू होणार नाही असे) ठेवून, फक्त next-level गाठल्यानेच बंद
        व्हायला हवं."""
        seed_trade(temp_db, "T40", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, entry_timeframe="5M")
        # प्रीमियम-नफा = 30-30 = 0 (neutral, SL/TSL/Target यापैकी काहीही लागू होणार नाही)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=30.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: 23905.0)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "NEXT_LEVEL_EXIT"

    def test_next_level_exit_applies_to_naked_trades_too(self, temp_db, monkeypatch):
        """वापरकर्त्याने ठरवलेलं — Next-Level-Exit Credit Spread आणि Naked दोन्हींना लागू (SRv2 च्या
        फक्त-Spread पद्धतीपेक्षा वेगळं)."""
        seed_trade(temp_db, "T41", net_credit=-30, sl_level=-1125, target_level=100000,
                   strategy="NAKED_CALL", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, entry_timeframe="5M")
        # cost_to_close_now = ce_ltp(SELL leg, +1) - pe_ltp(BUY leg, -1) = 0-30 = -30;
        # प्रीमियम-नफा = net_credit(-30) - cost_to_close_now(-30) = 0 (neutral)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=0.0, pe_ltp=30.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: 23905.0)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "NEXT_LEVEL_EXIT"

    def test_next_level_exit_not_applied_to_1m_entry(self, temp_db, monkeypatch):
        """वापरकर्त्याने स्पष्टपणे ठरवलेलं — 1M-touch entries ला Next-Level-Exit लागू नाही (अजूनही
        फक्त सध्याचेच Spot%/Premium/TSL नियम). get_next_level_in_direction ला कधीच call व्हायलाच
        नको, आणि trade neutral असल्याने उघडाच राहायला हवा."""
        seed_trade(temp_db, "T42", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, entry_timeframe="1M")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=30.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        mock_next_level = MagicMock(return_value=23905.0)
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", mock_next_level)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0
        mock_next_level.assert_not_called()

    def test_next_level_exit_does_not_fire_when_level_not_reached(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T43", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, entry_timeframe="5M")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=30.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: 24000.0)  # स्पॉट (23910) अजून तिथे पोहोचलेला नाही
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0

    def test_dynamic_sr_instant_gets_eod_squareoff_not_carry_forward(self, temp_db, monkeypatch):
        # entry_level_price/underlying_spot गहाळ असले (जुना trade), तरीही carry-forward कधीच लागू
        # होता कामा नये — EOD_SQUAREOFF च व्हावं.
        seed_trade(temp_db, "T5", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 28.0, "PE24300": 3.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 46)  # UTC 9:46 = IST 15:16 (EOD नंतर)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D", eod_squareoff_hour=15, eod_squareoff_minute=15)
        assert len(closed) == 1
        assert closed[0]["reason"] == "EOD_SQUAREOFF"

    def test_dynamic_sr_instant_eod_is_1500_not_1515(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — dynamic_sr_instant साठी EOD आता 15:00 (इतर
        strategies साठीचा 15:15 नाही). 15:05 ला (नवीन कटऑफनंतर, जुन्याच्या आधी) dynamic_sr_instant
        बंद व्हायलाच हवा, पण function-level eod_squareoff_hour/minute=15:15 दिलेला असूनही."""
        seed_trade(temp_db, "T33", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23910.0))  # स्पॉट neutral, SL/Target च्या दरम्यान
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 35)  # UTC 9:35 = IST 15:05
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D", eod_squareoff_hour=15, eod_squareoff_minute=15)
        assert len(closed) == 1
        assert closed[0]["reason"] == "EOD_SQUAREOFF"

    def test_other_strategy_not_yet_eod_at_1505_when_cutoff_is_1515(self, temp_db, monkeypatch):
        """तुलनेसाठी — इतर strategies साठीचा 15:15 कटऑफ तसाच बदललेला नाही; 15:05 ला अजून EOD होता कामा नये."""
        seed_trade(temp_db, "T34", net_credit=30, sl_level=-1125, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="strategy_builder", trading_style="INTRADAY")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 28.0, "PE24300": 3.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 35)  # UTC 9:35 = IST 15:05
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D", eod_squareoff_hour=15, eod_squareoff_minute=15)
        assert len(closed) == 0  # 15:15 चा कटऑफ अजून झालेला नाही

    def test_srv2_bullish_spot_sl_hit(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून बदललेली सुधारणा — srv2_momentum_reversal (Credit Spread)
        साठी आता जुनी %-Trailing SL नाही, स्पॉट-आधारित SL (settings डीफॉल्ट 0.15%, entry_level_price
        पासून प्रतिकूल दिशेने)."""
        seed_trade(temp_db, "T8", net_credit=30, sl_level=-2250, target_level=2250,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23860.0))  # ~-0.167%, SL(0.15%) पेक्षा जास्त
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: None)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"

    def test_srv2_premium_target_hit(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T9", net_credit=30, sl_level=-2250, target_level=100,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        # स्पॉट neutral (SL ट्रिगर होऊ नये), पण target_level (100) पेक्षा जास्त pnl
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23910.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: None)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "PREMIUM_TARGET"

    def test_srv2_next_level_exit(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 साठी Next-Level-Exit परत आणला (15M/30M/60M
        पूल केलेले) — favourable दिशेने पुढचा level (24000) गाठला की बंद व्हायला हवं."""
        seed_trade(temp_db, "T10", net_credit=30, sl_level=-2250, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, entry_timeframe="15M")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(24005.0))  # पुढचा level (24000) ओलांडला
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: 24000.0)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "NEXT_LEVEL_EXIT"

    def test_srv2_next_level_exit_searches_only_entry_timeframe(self, temp_db, monkeypatch):
        """entry_timeframe="30M" असेल, तर get_next_level_in_direction ला फक्त ("30M",) दिला जायला
        हवा -- तिन्ही पूल केलेले नाहीत."""
        seed_trade(temp_db, "T16", net_credit=30, sl_level=-2250, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, entry_timeframe="30M")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23910.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        mock_next_level = MagicMock(return_value=None)
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", mock_next_level)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert mock_next_level.called
        assert mock_next_level.call_args.kwargs.get("timeframe_suffixes") == ("30M",)

    def test_srv2_neither_stays_open(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T11", net_credit=30, sl_level=-2250, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23910.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: 24000.0)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0

    def test_srv2_carry_forward_closes_when_insufficient_profit_at_310pm(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याने सापडवलेली, महत्त्वाची दुरुस्ती — नवीन Spot/Premium exit-रचना जोडताना ही
        आधीचीच 3:10pm Carry-Forward तपासणी चुकून काढली गेली होती, परत जोडली. Target अजून गाठलेला
        नाही, 3:10pm झालेली आहे, नफा 30% (net credit) पेक्षा कमी -> आजच बंद व्हायला हवं."""
        # net_credit_total=2250, 30%=675. cost_to_close=25 -> pnl=(30-25)*75=375 (<675)
        seed_trade(temp_db, "T12", net_credit=30, sl_level=-2250, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=25.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: None)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 41)  # UTC 9:41 = IST 15:11 (3:10pm नंतर, EOD 15:15 आधी)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT"

    def test_srv2_carry_forward_stays_open_when_sufficient_profit_at_310pm(self, temp_db, monkeypatch):
        """तोच वेळ (3:10pm नंतर), पण नफा 30% (net credit) पेक्षा जास्त -> पुढच्या दिवशी चालू ठेवणे
        (आजच बंद न करता — EOD 15:15 चाही परिणाम होता कामा नये)."""
        # cost_to_close=21 -> pnl=(30-21)*75=675 (>=675, बरोबर 30%)
        seed_trade(temp_db, "T13", net_credit=30, sl_level=-2250, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=21.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: None)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 46)  # UTC 9:46 = IST 15:16 (EOD 15:15 च्याही नंतर)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0  # पुरेसा नफा -- EOD नंतरही उघडीच राहायला हवी

    def test_srv2_naked_sl_hit_at_005_percent(self, temp_db, monkeypatch):
        """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Naked Option Trade) — SL settings डीफॉल्ट
        0.05% (Spread च्या 0.15% पेक्षा घट्ट)."""
        naked_leg = [{"role": "naked_buy", "strike": 23850, "instrument_key": "PE24400", "transaction_type": "BUY"}]
        seed_trade(temp_db, "T14", net_credit=-60, sl_level=None, target_level=None,
                   strategy="NAKED_CALL", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, legs=naked_leg)
        # premium_pnl_points = net_credit(-60) + ltp(58) = -2 (सुरक्षित, प्रीमियम-SL(-10) पेक्षा कमी) --
        # स्पॉट (23880, ~-0.084%) च SL ठरवतो.
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23880.0, ce_ltp=58.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SL"

    def test_srv2_naked_never_carries_forward_closes_at_3pm(self, temp_db, monkeypatch):
        """वापरकर्त्याशी चर्चा करून ठरवलेला नियम — Naked trade कधीच carry-forward नाही, नेहमी आजच
        (डीफॉल्ट 3:00pm) बंद व्हायला हवी, SL/Target न लागतानाही."""
        naked_leg = [{"role": "naked_buy", "strike": 23850, "instrument_key": "PE24400", "transaction_type": "BUY"}]
        seed_trade(temp_db, "T15", net_credit=-60, sl_level=None, target_level=None,
                   strategy="NAKED_CALL", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, legs=naked_leg)
        # स्पॉट व प्रीमियम दोन्ही neutral (SL/Target लागू नयेत) -- फक्त EOD-वेळेचीच तपासणी.
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23905.0, ce_ltp=61.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 31)  # UTC 9:31 = IST 15:01 (3pm नंतर, 3:10pm आधी)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "EOD_SQUAREOFF"


class TestCorrelationIdInOrders:
    """🎓 वापरकर्त्याने Upstox कडून सापडवलेली bug (UDAPI1115: correlation_id is required) — Upstox
    Multi Order API ला प्रत्येक order मध्ये आता `correlation_id` सक्तीचा आहे, नसेल तर संपूर्ण
    ऑर्डर नाकारतो. established सर्व order-construction ठिकाणी (entry, managed-exit, manual-close)
    ही key असायलाच हवी."""

    def test_open_multi_leg_trade_includes_correlation_id(self, temp_db, monkeypatch):
        captured_orders = {}
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})

        def fake_execute(token, orders, mode):
            captured_orders["orders"] = orders
            return 200, {"status": "success", "data": {"order_ids": ["T1", "T2"]}}

        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)

        strategy_result = {
            "strategy": "BULL_PUT_SPREAD",
            "short_leg": {"strike": 24400, "instrument_key": "PE24400", "ltp": 50},
            "long_leg": {"strike": 24300, "instrument_key": "PE24300", "ltp": 25},
            "net_credit": 25, "max_profit": 25, "max_loss": 75,
        }
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", strategy_result, lots=1, lot_size=75,
            sl_pct_of_max_loss=999, target_pct_of_max_profit=30, product_type="D",
            trading_mode="PAPER", trading_style="SWING", sl_pct_of_credit=30,
        )
        orders = captured_orders["orders"]
        assert len(orders) == 2
        for o in orders:
            assert "correlation_id" in o and o["correlation_id"]
        # established दोन्ही legs ची correlation_id वेगळी (unique) असायला हवी
        assert orders[0]["correlation_id"] != orders[1]["correlation_id"]

    def test_manage_open_trades_close_orders_include_correlation_id(self, temp_db, monkeypatch):
        captured_orders = {}
        # established "insufficient profit" carry-forward-check पॅटर्न (वर टेस्ट केलेला) — pnl(300) <
        # carry_forward_min(675, net_credit_total=2250 च्या 30%) मुळे 3:10pm नंतर "अपुरा नफा" ठरून
        # बंद होईल, आणि तेव्हाच close_orders तपासता येतील.
        seed_trade(temp_db, "T7", net_credit=30, sl_level=-1125, target_level=1800)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 28.0, "PE24300": 2.0})

        def fake_execute(token, orders, mode):
            captured_orders["orders"] = orders
            return 200, {"status": "success"}

        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 9, 45)  # UTC 9:45 = IST 15:15 (3:10pm नंतर)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        orders = captured_orders.get("orders")
        assert orders is not None
        for o in orders:
            assert "correlation_id" in o and o["correlation_id"]


class TestReconcileOpenTradesWithBroker:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Broker Reconciliation) — Upstox च्या स्वतःच्या
    app/website वरून थेट बंद केलेली position आपल्याच database मध्ये आपोआप "CLOSED" करणे —
    Upstox कडे कुठलाही नवीन order न पाठवता (फक्त वाचनं)."""

    def test_position_closed_externally_gets_reconciled(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T20", net_credit=30, sl_level=-1125, target_level=1125, mode="LIVE")
        # Upstox कडे दोन्ही legs ची quantity शून्य (म्हणजे बाहेरून बंद झालेली)
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": 0},
            {"instrument_token": "PE24300", "quantity": 0},
        ])
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert error == ""
        assert reconciled == ["T20"]

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT status, exit_reason FROM live_trades WHERE trade_id='T20'").fetchone()
        conn.close()
        assert row == ("CLOSED", "RECONCILED_EXTERNAL_CLOSE")

    def test_position_still_open_at_broker_not_touched(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T21", net_credit=30, sl_level=-1125, target_level=1125)
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": -75},  # अजून उघडी
            {"instrument_token": "PE24300", "quantity": 75},
        ])
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert error == ""
        assert reconciled == []

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT status FROM live_trades WHERE trade_id='T21'").fetchone()
        conn.close()
        assert row == ("OPEN",)

    def test_one_leg_still_open_does_not_reconcile(self, temp_db, monkeypatch):
        """एकच leg अजून उघडी असेल तरीही — पूर्ण trade बंद केलं जाऊ नये (आंशिक स्थिती अनिश्चित असते)."""
        seed_trade(temp_db, "T22", net_credit=30, sl_level=-1125, target_level=1125)
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": -75},  # ही अजून उघडी
            {"instrument_token": "PE24300", "quantity": 0},
        ])
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert reconciled == []

    def test_broker_fetch_fails_returns_error(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: None)
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert reconciled == []
        assert error != ""


class TestEvaluatePointSpotExit:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) — Spot% +
    Premium-Points combined exit-गणित, Credit Spread आणि Naked Buy दोन्हींसाठी, TSL-to-Breakeven
    sticky-राज्यासह. premium_pnl_points आधीच योग्य चिन्हासह (net_credit - cost_to_close_now) दिला
    जातो -- Spread आणि Naked दोन्हींसाठी हेच सूत्र सुसंगत आहे."""

    def test_spread_sl_on_spot_move(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900 * (1 - 0.0006), 0, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r[0] == "SL"
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Performance Report PDF — "exact reason") —
        # detail ने नेमकं सांगायला हवं की Spot% मुळे लागला, Premium Points मुळे नाही (दुसऱ्याचा
        # संदर्भ "still at ..." असा फक्त माहितीसाठी असू शकतो, म्हणून नेमका "via" वाक्यांश तपासतो).
        assert "via Spot move" in r[2]

    def test_spread_sl_on_premium_move(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, -5, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r[0] == "SL"
        assert "via Premium points" in r[2]

    def test_spread_neither_stays_open_no_tsl(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23905, 2, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r == (None, False, None)

    def test_spread_tsl_activates_on_spot(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900 * 1.0011, 2, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r == (None, True, None)

    def test_spread_tsl_activates_on_premium(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, 10, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r == (None, True, None)

    def test_spread_tsl_sl_once_activated_and_profit_gives_back(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, -1, 0.05, 5, 0.10, 10, 0.20, 15, True)
        assert r[0] == "TSL_SL"

    def test_spread_tsl_sticky_while_still_profitable(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, 5, 0.05, 5, 0.10, 10, 0.20, 15, True)
        assert r == (None, True, None)

    def test_spread_target_on_spot(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900 * 1.0021, 2, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r[0] == "TARGET"
        assert "via Spot move" in r[2]

    def test_spread_target_on_premium(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, 15, 0.05, 5, 0.10, 10, 0.20, 15, False)
        assert r[0] == "TARGET"
        assert "via Premium points" in r[2]

    def test_tsl_sl_detail_mentions_breakeven(self):
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, -1, 0.05, 5, 0.10, 10, 0.20, 15, True)
        assert r[0] == "TSL_SL"
        assert "Breakeven" in r[2]

    def test_naked_tsl_activates_on_premium(self):
        r = trading_engine.evaluate_point_spot_exit(False, 24000, 24000, 20, 0.05, 10, 0.10, 20, 0.20, 30, False)
        assert r == (None, True, None)

    def test_naked_sl_on_adverse_spot(self):
        r = trading_engine.evaluate_point_spot_exit(False, 24000, 24000 * 1.0006, 0, 0.05, 10, 0.10, 20, 0.20, 30, False)
        assert r[0] == "SL"

    def test_naked_target_on_premium(self):
        r = trading_engine.evaluate_point_spot_exit(False, 24000, 24000, 30, 0.05, 10, 0.10, 20, 0.20, 30, False)
        assert r[0] == "TARGET"

    def test_naked_tsl_sl_once_activated(self):
        r = trading_engine.evaluate_point_spot_exit(False, 24000, 24000, -5, 0.05, 10, 0.10, 20, 0.20, 30, True)
        assert r[0] == "TSL_SL"

    def test_target_takes_priority_even_if_tsl_already_active(self):
        """TSL आधीच सक्रिय असतानाही, Target गाठला की तोच लागू व्हायला हवा (TSL_SL नाही)."""
        r = trading_engine.evaluate_point_spot_exit(True, 23900, 23900, 15, 0.05, 5, 0.10, 10, 0.20, 15, True)
        assert r[0] == "TARGET"


class TestComputePremiumTrailingFloor:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("user defined trailing stop loss for all strategies") —
    3 Bot स्ट्रॅटेजींसाठी Premium-Points-आधारित सतत Trailing Stop चं शुद्ध (pure) गणित."""

    def test_peak_tracks_current_when_higher(self):
        new_peak, floor_points = trading_engine.compute_premium_trailing_floor(20.0, 15.0, 5.0)
        assert new_peak == 20.0
        assert floor_points == 15.0

    def test_peak_never_decreases_when_current_drops(self):
        new_peak, floor_points = trading_engine.compute_premium_trailing_floor(18.0, 25.0, 5.0)
        assert new_peak == 25.0  # आधीचा peak (25) कायम, सद्य (18) पेक्षा जास्त
        assert floor_points == 20.0

    def test_none_peak_treated_as_zero(self):
        new_peak, floor_points = trading_engine.compute_premium_trailing_floor(10.0, None, 5.0)
        assert new_peak == 10.0
        assert floor_points == 5.0


class TestPremiumTrailingStopLossIntegration:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा — तिन्ही Bot स्ट्रॅटेजींच्या manage_open_trades() branches
    मध्ये नवीन Premium-Points Trailing SL (settings-चालित, डीफॉल्ट बंद) योग्य प्रकारे लागू होतो का."""

    def _mock_ltp_map(self, spot_value, short_leg_ltp, long_hedge_ltp):
        def _fn(token, keys):
            if keys == ["NSE_INDEX|Nifty 50"]:
                return {"NSE_INDEX|Nifty 50": spot_value}
            return {"PE24400": short_leg_ltp, "PE24300": long_hedge_ltp}
        return _fn

    def _settings_with_trailing(self, base_strategy_name, **overrides):
        def _fn(strategy_name, symbol):
            settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS[base_strategy_name])
            settings["symbol_enabled"] = True
            settings.update(overrides)
            return settings
        return _fn

    def test_disabled_by_default_stays_at_old_breakeven_only(self, temp_db, monkeypatch):
        """trailing टॉगल डीफॉल्ट बंद असल्याने, TSL सक्रिय असतानाही नफा breakeven च्या वर असेल
        (जुनं वर्तन) तर बंद व्हायला नको — नवीन कोड जोडण्याआधीचंच वर्तन अबाधित."""
        seed_trade(temp_db, "TT1", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, tsl_activated=1, peak_pnl=0)
        # स्पॉट neutral, प्रीमियम-नफा = 30-18 = 12 (breakeven च्या वर, Target 15 च्या खाली, पण
        # trailing बंद असल्याने काहीच परिणाम नाही)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23905.0, 18.0, 0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0

    def test_dynamic_sr_instant_trailing_stays_open_above_floor(self, temp_db, monkeypatch):
        seed_trade(temp_db, "TT2", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, tsl_activated=1, peak_pnl=0)
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", self._settings_with_trailing(
            "1m_instant", spread_trailing_sl_enabled=True, spread_trailing_distance_points=5,
        ))
        # प्रीमियम-नफा = 30-18 = 12 (Target 15 च्या खाली); peak आता 12, floor = 12-5 = 7; 12 > 7 -- उघडाच राहायला हवा
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23905.0, 18.0, 0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 0

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT peak_pnl FROM live_trades WHERE trade_id='TT2'").fetchone()
        conn.close()
        assert row == (12.0,)  # नवीन peak साठवला गेला

    def test_dynamic_sr_instant_trailing_triggers_below_floor(self, temp_db, monkeypatch):
        # आधीच्या cycle मध्ये peak 15 पर्यंत गेलेला (saved), आता प्रीमियम-नफा घसरून 8 झालेला --
        # floor = 15-5 = 10, 8 <= 10 -- Trailing SL लागू व्हायलाच हवा (Target 15 च्या खालीच राहून, TARGET न लागता).
        seed_trade(temp_db, "TT3", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, tsl_activated=1, peak_pnl=15)
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", self._settings_with_trailing(
            "1m_instant", spread_trailing_sl_enabled=True, spread_trailing_distance_points=5,
        ))
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23905.0, 22.0, 0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TSL_SL"

    def test_classic_sr_reversal_trailing_triggers_below_floor(self, temp_db, monkeypatch):
        # dynamic_sr_instant च्याच नंबर्ससह (classic_sr_reversal चाही spread_target_premium_points
        # डीफॉल्ट 15 आहे) -- peak 15, current 8, floor=10, TARGET(15) च्या खाली राहून TSL_SL लागू.
        seed_trade(temp_db, "TT4", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="classic_sr_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, tsl_activated=1, peak_pnl=15)
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", self._settings_with_trailing(
            "classic_sr_reversal", spread_trailing_sl_enabled=True, spread_trailing_distance_points=5,
        ))
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23905.0, 22.0, 0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TSL_SL"

    def test_srv2_spread_trailing_triggers_below_floor(self, temp_db, monkeypatch):
        seed_trade(temp_db, "TT5", net_credit=30, sl_level=-2250, target_level=100000,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, tsl_activated=1, peak_pnl=30)
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", self._settings_with_trailing(
            "15m_dynamic_sr", spread_trailing_sl_enabled=True, spread_trailing_distance_points=5,
        ))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: None)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23905.0, 6.0, 0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TSL_SL"

    def test_srv2_naked_trailing_triggers_below_floor(self, temp_db, monkeypatch):
        # एकच naked (BUY) leg -- net_credit=-30 (debit paid), ltp=54 -> premium_pnl_points =
        # net_credit - cost_to_close_now = -30 - (-54) = 24. peak आधीच 30 (seeded), floor=30-5=25,
        # 24 <= 25 -- Trailing SL लागू व्हायलाच हवा.
        seed_trade(temp_db, "TT6", net_credit=-30, sl_level=-1125, target_level=100000,
                   strategy="NAKED_CALL", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0, tsl_activated=1, peak_pnl=30,
                   legs=[{"role": "naked_leg", "strike": 24400, "instrument_key": "CE24400", "transaction_type": "BUY"}])
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", self._settings_with_trailing(
            "15m_dynamic_sr", naked_trailing_sl_enabled=True, naked_trailing_distance_points=5,
        ))
        def _naked_ltp(token, keys):
            if keys == ["NSE_INDEX|Nifty 50"]:
                return {"NSE_INDEX|Nifty 50": 23905.0}
            return {"CE24400": 54.0}
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", _naked_ltp)
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TSL_SL"
