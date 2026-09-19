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
    🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Margin Check in Bots, गंभीर यादीतला
    सहावा मुद्दा) — open_multi_leg_trade() आता LIVE trades साठी check_margin_available() कॉल
    करतं (जे adapter नसेल तर fetch_required_margin()/get_available_margin() — खरे Upstox network
    calls — वापरतं). वरच्या fetch_broker_positions सारखीच सुरक्षित डीफॉल्ट (नेहमी "मार्जिन OK")
    — ज्या tests ना अपुऱ्या-मार्जिन वर्तन विशेषतः तपासायचं आहे, ते स्वतःच override करतात.
    """
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda access_token: [])
    monkeypatch.setattr(trading_engine, "check_margin_available", lambda *a, **k: (True, None))
    yield tmpdb


def seed_trade(tmpdb, trade_id, net_credit, sl_level, target_level, strategy="BULL_PUT_SPREAD", source=None, trading_style="SWING", peak_pnl=None, entry_level_price=None, mode="PAPER", tsl_activated=0, legs=None, entry_timeframe=None, account_id=None):
    conn = sqlite3.connect(tmpdb)
    if legs is None:
        legs = [
            {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL"},
            {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY"},
        ]
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json,
           strikes_summary, mode, trading_style, source, peak_pnl, entry_level_price, tsl_activated, entry_timeframe, account_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-08-24", "NIFTY", strategy, 1, 75, net_credit, net_credit, 50,
         sl_level, target_level, "2026-08-24 10:00:00", "OPEN", json.dumps(legs), "test", mode, trading_style, source, peak_pnl, entry_level_price, tsl_activated, entry_timeframe, account_id),
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


class TestSlTargetLevelsPreLiveFixes:
    """🎓 वापरकर्त्याने लाईव्ह ट्रेडिंगआधी मागितलेल्या सखोल review मध्ये सापडलेले, थेट पैशाशी संबंधित
    bugs (तीनही स्वतंत्र review-agents नी दुजोरा दिलेले) — open_multi_leg_trade() मधले
    sl_pnl_level/target_pnl_level फक्त lot_size ने गुणले जायचे, lots ने नाही; आणि Naked Option
    (hedge नसलेला buy, max_profit=None) साठी None*lot_size क्रॅश व्हायचा -- तोही order Upstox कडे
    प्रत्यक्ष गेल्यानंतर, database मध्ये trade साठवण्याआधी."""

    def _capture(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 50.0 for kk in k})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set",
                             lambda t, o, m: (200, {"status": "success", "data": {"order_ids": ["T1", "T2"]}}))
        return captured

    def _stored_levels(self, tmpdb, trade_id):
        conn = sqlite3.connect(tmpdb)
        row = conn.execute(
            "SELECT sl_pnl_level, target_pnl_level, max_profit, max_loss FROM live_trades WHERE trade_id=?",
            (trade_id,),
        ).fetchone()
        conn.close()
        return row

    def test_sl_target_levels_scale_with_lots_not_just_lot_size(self, temp_db, monkeypatch):
        """lots=3 सह घेतलेल्या credit-spread trade चे sl_pnl_level/target_pnl_level, lots=1 च्या
        बरोबर 3 पटच असायला हवेत -- manage_open_trades() मधला current_pnl नेहमी `* lots * lot_size`
        असतो (net_credit_total, ओळ ~741), त्यामुळे तुलना योग्य रकमेशीच व्हायला हवी."""
        self._capture(monkeypatch)
        strategy_result = {
            "strategy": "BULL_PUT_SPREAD",
            "short_leg": {"strike": 24400, "instrument_key": "PE24400", "ltp": 50},
            "long_leg": {"strike": 24300, "instrument_key": "PE24300", "ltp": 25},
            "net_credit": 25, "max_profit": 25, "max_loss": 75,
        }
        ok, result = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", strategy_result, lots=3, lot_size=75,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=80, product_type="D",
            trading_mode="PAPER", trading_style="SWING", sl_pct_of_credit=100,
        )
        assert ok is True
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT sl_pnl_level, target_pnl_level FROM live_trades ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        sl_level, target_level = row
        # net_credit_total (lots=3) = 25 * 3 * 75 = 5625; sl_pct_of_credit=100 -> sl_pnl_level = -5625
        assert sl_level == -5625.0
        # max_profit_total (lots=3) = 25 * 3 * 75 = 5625; target_pct=80% -> 4500
        assert target_level == 4500.0

    def test_naked_option_without_hedge_does_not_crash_on_none_max_profit(self, temp_db, monkeypatch):
        """🎓 Naked Option (hedge नसलेला, डीफॉल्ट settings) साठी strategy.py.select_naked_option_itm()
        max_profit=None (unbounded) रिटर्न करतं -- यामुळे आधी None*lots*lot_size TypeError यायचा,
        प्रत्यक्ष order Upstox कडे गेल्यानंतर, DB insert च्या आधी. आता क्रॅश होता कामा नये, आणि
        target_pnl_level None (unbounded profit साठी % target चा अर्थच नाही) साठवला जायला हवा."""
        self._capture(monkeypatch)
        naked_result = {
            "strategy": "NAKED_CALL", "buy_leg": {"strike": 24000, "instrument_key": "CE24000", "ltp": 150},
            "net_credit": -150.0, "max_profit": None, "max_loss": 150.0,
        }
        ok, result = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", naked_result, lots=2, lot_size=75,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=100, product_type="D",
            trading_mode="PAPER", trading_style="INTRADAY", sl_pct_of_credit=100,
        )
        assert ok is True  # क्रॅश झाला नाही
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT sl_pnl_level, target_pnl_level FROM live_trades ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        sl_level, target_level = row
        assert target_level is None  # unbounded profit -- fixed % target साठवला जाऊ नये
        # 🎓 net_credit ऋण (debit, -150) असल्याने abs() शिवाय sl_pnl_level चुकून धन यायचा (entry
        # नंतर लगेचच खोटा SL trigger व्हायचा). net_credit_total = -150*2*75 = -22500;
        # sl_pct_of_credit=100 -> sl_pnl_level = -(abs(-22500)*1.0) = -22500 (ऋणच, योग्य).
        assert sl_level == -22500.0

    def test_naked_option_sl_level_is_negative_not_positive(self, temp_db, monkeypatch):
        """🎓 विशेषतः sign-fix तपासण्यासाठी -- fix आधी sl_pnl_level धन (+22500) यायचा, ज्यामुळे
        current_pnl <= sl_pnl_level ही तुलना entry नंतर लगेचच (कुठलीही खरी किंमत-हालचाल न होताच)
        खरी ठरायची -- म्हणजे प्रत्येक naked trade उघडल्याक्षणीच चुकीने STOP_LOSS ने बंद व्हायचा."""
        self._capture(monkeypatch)
        naked_result = {
            "strategy": "NAKED_PUT", "buy_leg": {"strike": 24500, "instrument_key": "PE24500", "ltp": 120},
            "net_credit": -120.0, "max_profit": None, "max_loss": 120.0,
        }
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", naked_result, lots=1, lot_size=75,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=100, product_type="D",
            trading_mode="PAPER", trading_style="INTRADAY", sl_pct_of_credit=100,
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT sl_pnl_level FROM live_trades ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] < 0  # कधीच धन नसावा


class TestEntryBasisUsesActualFillPrice:
    """🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — SL पातळी आणि साठवलेला
    net_credit आधी नेहमी strategy_result मधल्या (signal-check वेळी, order पाठवण्याआधी घेतलेल्या)
    chain-LTP वरून ठरायचे — MARKET order च्या प्रत्यक्ष slippage कडे पूर्णपणे दुर्लक्ष करून. पण
    upstox_api.execute_order_leg_set() आधीच खरी fill किंमत (resp["verified_legs"]/["paper_fills"])
    परत देतं — आता तीच वापरली जायला हवी, उपलब्ध असेल तेव्हा."""

    def _strategy_result(self):
        return {
            "strategy": "BULL_PUT_SPREAD",
            "short_leg": {"strike": 24400, "instrument_key": "PE24400", "ltp": 50},
            "long_leg": {"strike": 24300, "instrument_key": "PE24300", "ltp": 25},
            "net_credit": 25, "max_profit": 25, "max_loss": 75,  # chain-snapshot आधारित (जुना)
        }

    def test_live_order_uses_verified_leg_average_price_not_chain_snapshot(self, temp_db, monkeypatch):
        """खरा fill (slippage मुळे) chain-snapshot पेक्षा वेगळा असेल (short leg 48 ऐवजी संभवतः
        जास्त, long leg 27 ऐवजी संभवतः जास्त -- net_credit कमी झालेला, 25 ऐवजी 20), तर साठवलेला
        net_credit आणि sl_pnl_level त्या खऱ्या (कमी झालेल्या) आधारावरच असायला हवेत."""
        def fake_execute(token, orders, mode):
            return 200, {
                "status": "success", "data": {"order_ids": ["T1", "T2"]},
                "verified_legs": [
                    {"instrument_token": "PE24400", "average_price": 48.0},  # short leg, chain-snapshot 50 होता
                    {"instrument_token": "PE24300", "average_price": 28.0},  # long leg, chain-snapshot 25 होता
                ],
            }
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=80, product_type="D",
            trading_mode="LIVE", trading_style="SWING", sl_pct_of_credit=100,
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT net_credit, sl_pnl_level FROM live_trades ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        net_credit, sl_pnl_level = row
        # खरा net_credit = short(48) - long(28) = 20 (chain-snapshot च्या 25 ऐवजी)
        assert net_credit == 20.0
        assert sl_pnl_level == -1500.0  # -(20 * 1 * 75 * 100%)

    def test_paper_order_uses_paper_fills_not_chain_snapshot(self, temp_db, monkeypatch):
        def fake_execute(token, orders, mode):
            return 200, {
                "status": "success", "data": {"order_ids": ["T1", "T2"]},
                "paper_fills": {"PE24400": 49.0, "PE24300": 26.0},
            }
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=80, product_type="D",
            trading_mode="PAPER", trading_style="SWING", sl_pct_of_credit=100,
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT net_credit FROM live_trades ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == 23.0  # short(49) - long(26) = 23, chain-snapshot च्या 25 ऐवजी

    def test_falls_back_to_chain_snapshot_when_no_verified_fill_data(self, temp_db, monkeypatch):
        """Shoonya/Stocko/Fyers सारखे adapter-routed brokers verified_legs/paper_fills कधीच देत
        नाहीत -- अशा वेळी जुनाच chain-snapshot आधार (backward-compatible) वापरला जायलाच हवा."""
        def fake_execute(token, orders, mode):
            return 200, {"status": "success", "data": {"order_ids": ["T1", "T2"]}}  # verified_legs/paper_fills नाहीत
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=None, target_pct_of_max_profit=80, product_type="D",
            trading_mode="LIVE", trading_style="SWING", sl_pct_of_credit=100,
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT net_credit FROM live_trades ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == 25.0  # strategy_result["net_credit"] चाच जुना आधार

    def test_target_and_max_profit_max_loss_also_shift_with_fill_price_not_just_net_credit(self, temp_db, monkeypatch):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug (वरच्याच fill-price दुरुस्तीतली अपूर्ण बाब) —
        net_credit वर तर खरी fill किंमत लागू व्हायची, पण max_profit/max_loss (म्हणजे
        target_pnl_level आणि sl_pct_of_max_loss मार्गाचा sl_pnl_level दोन्हींचा आधार) अजूनही
        strategy_result मधलेच जुने (chain-snapshot-वेळचे) राहायचे. width (max_profit+max_loss)
        किमतीवर अवलंबून नसतो, फक्त net_credit बदलतो — म्हणजे net_credit जेवढा बदलला (delta),
        max_profit त्याच +delta ने आणि max_loss -delta ने सरकवला की परत सुसंगत होतात."""
        def fake_execute(token, orders, mode):
            return 200, {
                "status": "success", "data": {"order_ids": ["T1", "T2"]},
                "verified_legs": [
                    {"instrument_token": "PE24400", "average_price": 48.0},  # short leg, chain-snapshot 50 होता
                    {"instrument_token": "PE24300", "average_price": 28.0},  # long leg, chain-snapshot 25 होता
                ],
            }
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=100, target_pct_of_max_profit=80, product_type="D",
            trading_mode="LIVE", trading_style="SWING",  # sl_pct_of_credit नाही -- max_loss मार्ग वापरण्यासाठी
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute(
            "SELECT net_credit, max_profit, max_loss, sl_pnl_level, target_pnl_level FROM live_trades ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        conn.close()
        net_credit, max_profit, max_loss, sl_pnl_level, target_pnl_level = row
        # खरा net_credit = short(48) - long(28) = 20 (chain-snapshot च्या 25 ऐवजी) -> delta = -5
        assert net_credit == 20.0
        assert max_profit == 20.0  # जुना 25 + delta(-5)
        assert max_loss == 80.0  # जुना 75 - delta(-5)
        assert max_profit + max_loss == 100.0  # width (strategy_result: 25+75=100) कायम अबाधित
        assert sl_pnl_level == -6000.0  # -(80 * 1 * 75 * 100%) -- जुन्या (75-आधारित) ऐवजी नवीन max_loss आधारित
        assert target_pnl_level == 1200.0  # 20 * 1 * 75 * 80% -- जुन्या (25-आधारित, 1500) ऐवजी नवीन max_profit आधारित

    def test_naked_max_profit_none_survives_fill_price_adjustment(self, temp_db, monkeypatch):
        """Naked (hedge नसलेला) trade चा max_profit=None (unbounded) असतो -- fill-price दुरुस्ती
        त्याला None च ठेवायला हवी (crash नाही), max_loss मात्र तरीही योग्य दिशेने सरकायला हवा."""
        naked_result = {
            "strategy": "NAKED_CALL", "buy_leg": {"strike": 24000, "instrument_key": "CE24000", "ltp": 60},
            "net_credit": -60, "max_profit": None, "max_loss": 60,
        }
        def fake_execute(token, orders, mode):
            return 200, {
                "status": "success", "data": {"order_ids": ["T1"]},
                "verified_legs": [{"instrument_token": "CE24000", "average_price": 65.0}],  # आधीपेक्षा जास्त किंमतीत भरलं (slippage)
            }
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)
        trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", naked_result, lots=1, lot_size=75,
            sl_pct_of_max_loss=100, target_pct_of_max_profit=80, product_type="D",
            trading_mode="LIVE", trading_style="SWING",
        )
        conn = sqlite3.connect(temp_db)
        row = conn.execute(
            "SELECT net_credit, max_profit, max_loss, target_pnl_level FROM live_trades ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        conn.close()
        net_credit, max_profit, max_loss, target_pnl_level = row
        assert net_credit == -65.0  # जास्त किंमतीत विकत घेतलं -- net_credit आणखी ऋण
        assert max_profit is None  # unbounded, crash नाही
        assert max_loss == 65.0  # 60 वरून 65 पर्यंत वाढला (जास्त पैसे दिले, जास्त तोटा शक्य)
        assert target_pnl_level is None  # max_profit None असल्याने target_pnl_level सुद्धा None


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

    def test_broker_selected_trade_not_reconciled_via_upstox(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) टेस्ट करताना सापडलेली
        सुरक्षा-मर्यादा — account_id असलेला (निवडलेल्या broker वर उघडलेला) trade Upstox च्या Positions
        शी कधीच ताडून बघितला जाऊ नये (चुकीचा broker तपासला जाईल) — जरी Upstox कडे legs "बंद" दिसल्या तरी."""
        seed_trade(temp_db, "T23", net_credit=30, sl_level=-1125, target_level=1125, mode="LIVE", account_id="ACC_SHOONYA_1")
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": 0},
            {"instrument_token": "PE24300", "quantity": 0},
        ])
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert error == ""
        assert reconciled == []  # account_id असलेला trade वगळलाच जायला हवा

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT status FROM live_trades WHERE trade_id='T23'").fetchone()
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

    def test_empty_positions_response_does_not_close_everything(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याने लाईव्ह ट्रेडिंगआधी मागितलेल्या सखोल review मध्ये सापडवलेली, अत्यंत गंभीर
        bug (तीनही agents पैकी एकाने सापडवलेली) — fetch_broker_positions() 200 status सह रिकामी यादी
        ([], None नाही) रिटर्न करतं तेव्हाही (क्षणिक glitch, किंवा carry-forward झालेली position
        "short-term-positions" API मध्ये त्या दिवशी दिसलीच नाही तरीही) — आधी `positions is None`
        तपासणी हे पकडायचीच नाही, आणि रिकाम्या यादीमुळे प्रत्येक leg "broker कडे नाही" ठरून सर्वच्या
        सर्व OPEN LIVE trades एकाच झटक्यात (चुकीने) CLOSED व्हायच्या -- पुढे SL/Target/EOD काहीच लागू
        न होता, खरी उघडी position कायमची अनियंत्रित राहायची. आता रिकामी/अपूर्ण यादी कुठलाही trade
        बंद करत नाही -- फक्त explicit quantity=0 सापडलेली position तशीच गणली जाते."""
        seed_trade(temp_db, "T24", net_credit=30, sl_level=-1125, target_level=1125, mode="LIVE")
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [])
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert error == ""
        assert reconciled == []  # आधी इथे ["T24"] यायचं -- चुकीने बंद

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT status FROM live_trades WHERE trade_id='T24'").fetchone()
        conn.close()
        assert row == ("OPEN",)

    def test_leg_missing_from_response_entirely_does_not_reconcile(self, temp_db, monkeypatch):
        """response मध्ये leg चा उल्लेखच नसेल (quantity=0 सहही नाही, पूर्णपणे गहाळ) -- ती leg
        "explicitly बंद" म्हणून कधीच गणली जाऊ नये, फक्त response मध्ये स्पष्टपणे quantity=0 दिलेली
        असेल तरच."""
        seed_trade(temp_db, "T25", net_credit=30, sl_level=-1125, target_level=1125, mode="LIVE")
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": 0},
            # PE24300 (दुसरी leg) यादीत पूर्णपणे गहाळ -- quantity=0 सहही नमूद नाही
        ])
        reconciled, error = trading_engine.reconcile_open_trades_with_broker("fake_token", "NIFTY")
        assert reconciled == []

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT status FROM live_trades WHERE trade_id='T25'").fetchone()
        conn.close()
        assert row == ("OPEN",)


class TestManageOpenTradesBrokerRouting:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) — manage_open_trades()
    ने प्रत्येक trade बंद करताना, त्याच्या साठवलेल्या account_id प्रमाणेच योग्य broker/adapter
    वापरायला हवा — नाहीतर चुकीच्या broker कडे (नेहमी Upstox कडे) बंद-ऑर्डर जाऊ शकतो, आणि प्रत्यक्ष
    position दुसऱ्याच broker वर उघडीच राहील."""

    def test_closes_via_selected_broker_adapter_not_upstox(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T51", net_credit=30, sl_level=-100000, target_level=1000, account_id="ACC_X")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 5.0, "PE24300": 0.0})

        upstox_execute_calls = []
        monkeypatch.setattr(
            trading_engine, "execute_order_leg_set",
            lambda t, o, m: (upstox_execute_calls.append(1), (200, {"status": "success"}))[1],
        )
        mock_adapter = MagicMock()
        mock_adapter.execute_order_leg_set.return_value = (200, {"status": "success"})
        import broker_factory
        monkeypatch.setattr(broker_factory, "get_adapters_for_accounts", lambda ids: ([(mock_adapter, 1.0)], []))

        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TARGET"
        assert mock_adapter.execute_order_leg_set.called
        assert not upstox_execute_calls  # खरा Upstox execute_order_leg_set कधीच कॉल व्हायला नको

    def test_account_id_none_still_uses_raw_upstox(self, temp_db, monkeypatch):
        """जुनंच वर्तन — account_id नसलेला (शुद्ध Upstox) trade अजूनही access_token नेच बंद व्हायला हवा."""
        seed_trade(temp_db, "T52", net_credit=30, sl_level=-100000, target_level=1000, account_id=None)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"PE24400": 5.0, "PE24300": 0.0})
        upstox_execute_calls = []
        monkeypatch.setattr(
            trading_engine, "execute_order_leg_set",
            lambda t, o, m: (upstox_execute_calls.append(1), (200, {"status": "success"}))[1],
        )
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert len(upstox_execute_calls) == 1


class TestAlertLtpFetchFailure:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Token-Expiry/LTP-Fetch Silent Failure,
    गंभीर यादीतला तिसरा मुद्दा) — LTP मिळाली नाही (उदा. token expire) की LIVE trades साठी नेहमी
    Telegram अलर्ट, PAPER-केवळ trades साठी नाही."""

    def test_no_live_trades_sends_no_alert(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        trading_engine._alert_ltp_fetch_failure("NIFTY", "Option-leg", "HTTP 401: ...", has_live_trades=False)
        assert not telegram_calls

    def test_401_error_sends_auth_specific_alert(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        trading_engine._alert_ltp_fetch_failure("NIFTY", "Option-leg", "HTTP 401: Unauthorized", has_live_trades=True)
        assert len(telegram_calls) == 1
        assert "टोकन समस्या" in telegram_calls[0]

    def test_generic_error_sends_generic_alert(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        trading_engine._alert_ltp_fetch_failure("NIFTY", "Underlying Spot", "Exception: connection reset", has_live_trades=True)
        assert len(telegram_calls) == 1
        assert "टोकन समस्या" not in telegram_calls[0]
        assert "LTP मिळाली नाही" in telegram_calls[0]

    def test_none_error_detail_still_alerts(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        trading_engine._alert_ltp_fetch_failure("NIFTY", "Option-leg", None, has_live_trades=True)
        assert len(telegram_calls) == 1


class TestManageOpenTradesLtpFetchFailureAlerting:
    """manage_open_trades() मधलं वायरिंग — LTP fetch अयशस्वी झाल्यास योग्य वेळी, योग्य संदर्भासह अलर्ट."""

    def test_option_leg_fetch_empty_with_live_trade_alerts(self, temp_db, monkeypatch):
        import notifications
        seed_trade(temp_db, "T60", net_credit=30, sl_level=-1125, target_level=1125, mode="LIVE")
        # LIVE trade असल्याने आधी reconcile_open_trades_with_broker() चालतं -- broker कडे अजूनही
        # ही position उघडी दाखवली नाही, तर आपोआप "बाहेरून बंद झाली" समजून बंद केली जाईल, आणि मग
        # LTP fetch पर्यंत पोहोचणारच नाही -- म्हणून इथे legs अजून उघड्याच आहेत हे स्पष्ट सांगणे गरजेचं.
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": -75},
            {"instrument_token": "PE24300", "quantity": 75},
        ])
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {})
        monkeypatch.setattr(trading_engine, "fetch_ltp_map_detailed", lambda t, k: ({}, "HTTP 401: Unauthorized"))
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))

        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert closed == []  # LTP नसल्याने या cycle ला काहीच बंद होणार नाही
        assert len(telegram_calls) == 1
        assert "टोकन समस्या" in telegram_calls[0]

    def test_option_leg_fetch_empty_with_only_paper_trade_no_alert(self, temp_db, monkeypatch):
        import notifications
        seed_trade(temp_db, "T61", net_credit=30, sl_level=-1125, target_level=1125, mode="PAPER")
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {})
        monkeypatch.setattr(trading_engine, "fetch_ltp_map_detailed", lambda t, k: ({}, "HTTP 401: Unauthorized"))
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))

        trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert not telegram_calls

    def test_underlying_spot_fetch_empty_with_live_trade_alerts(self, temp_db, monkeypatch):
        """underlying_spot न मिळाल्याने trade generic (A1/manual) exit-मार्गाकडे पडतो -- तिथे
        चुकून SL/Target लागू नये म्हणून sl_level/target_level जाणीवपूर्वक कधीच न गाठता येणारे,
        आणि EOD-cutoff टाळण्यासाठी वेळ गोठवलेली."""
        import notifications
        seed_trade(temp_db, "T62", net_credit=30, sl_level=-1000000, target_level=1000000, mode="LIVE",
                   source="dynamic_sr_instant", entry_level_price=23900.0, trading_style="INTRADAY")
        monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda t: [
            {"instrument_token": "PE24400", "quantity": -75},
            {"instrument_token": "PE24300", "quantity": 75},
        ])
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)  # UTC 5:00 = IST 10:30 (EOD च्या आधी)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)

        def fake_fetch_ltp_map(token, keys):
            if keys == ["NSE_INDEX|Nifty 50"]:
                return {}  # underlying spot मिळालाच नाही
            return {"PE24400": 5.0, "PE24300": 0.0}  # option legs मात्र ठीक

        monkeypatch.setattr(trading_engine, "fetch_ltp_map", fake_fetch_ltp_map)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map_detailed", lambda t, k: ({}, "HTTP 401: Unauthorized"))
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))

        trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(telegram_calls) == 1
        assert "Underlying Spot" in telegram_calls[0] or "टोकन समस्या" in telegram_calls[0]


class TestAutoReverseFilledLegs:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Partial-Leg Failure Handling, गंभीर
    यादीतला दुसरा मुद्दा) — Multi-leg ऑर्डर मधला काही भाग भरला, काही अयशस्वी झाला तर उरलेला
    अर्धवट (unhedged) भाग लगेच स्वयंचलितपणे बंद (square-off) करायला हवा, आणि Telegram वर नेहमी
    कळवायला हवं."""

    def _partial_resp(self, legs):
        return {"status": "partial_failure", "verified_legs": legs}

    def test_no_filled_legs_sends_plain_alert_no_reversal_attempted(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        execute_calls = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: execute_calls.append(o) or (200, {"status": "success"}))

        trading_engine._auto_reverse_filled_legs(
            "fake_token", None, {"status": "error", "verified_legs": [
                {"order_id": "O1", "status": "rejected", "instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"},
            ]},
            "LIVE", "D", "NIFTY",
        )
        assert not execute_calls  # कुठलाही reversal-ऑर्डर पाठवायचा प्रश्नच नाही -- काहीच भरलं नाही
        assert len(telegram_calls) == 1
        assert "पूर्णपणे अयशस्वी" in telegram_calls[0]

    def test_partial_fill_reversal_succeeds_sends_success_alert(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        reversal_orders_sent = []

        def fake_execute(token, orders, mode):
            reversal_orders_sent.append(orders)
            return 200, {"status": "success", "data": [{"order_id": "REV1"}]}

        monkeypatch.setattr(trading_engine, "execute_order_leg_set", fake_execute)

        filled_legs = [
            {"order_id": "O1", "status": "complete", "instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"},
        ]
        trading_engine._auto_reverse_filled_legs("fake_token", None, self._partial_resp(filled_legs), "LIVE", "D", "NIFTY")

        assert len(reversal_orders_sent) == 1
        reversal_order = reversal_orders_sent[0][0]
        assert reversal_order["instrument_token"] == "PE24400"
        assert reversal_order["transaction_type"] == "BUY"  # मूळ SELL leg -- उलट दिशा
        assert reversal_order["quantity"] == 75
        assert len(telegram_calls) == 1
        assert "अंशतः अयशस्वी" in telegram_calls[0]
        assert "✅ यशस्वी" in telegram_calls[0]

    def test_partial_fill_reversal_fails_sends_critical_alert(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (500, {"status": "error"}))

        filled_legs = [
            {"order_id": "O1", "status": "complete", "instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"},
        ]
        trading_engine._auto_reverse_filled_legs("fake_token", None, self._partial_resp(filled_legs), "LIVE", "D", "NIFTY")

        assert len(telegram_calls) == 1
        assert "गंभीर" in telegram_calls[0]
        assert "PE24400" in telegram_calls[0]

    def test_uses_adapter_when_given_not_raw_access_token(self, monkeypatch):
        import notifications
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: None)
        upstox_calls = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: upstox_calls.append(1) or (200, {"status": "success"}))
        mock_adapter = MagicMock()
        mock_adapter.execute_order_leg_set.return_value = (200, {"status": "success", "data": [{"order_id": "REV1"}]})

        filled_legs = [
            {"order_id": "O1", "status": "complete", "instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"},
        ]
        trading_engine._auto_reverse_filled_legs("fake_token", mock_adapter, self._partial_resp(filled_legs), "LIVE", "D", "NIFTY")

        assert mock_adapter.execute_order_leg_set.called
        assert not upstox_calls


class TestOpenMultiLegTradePartialFailure:
    """open_multi_leg_trade() ने resp["status"]=="partial_failure" ओळखून auto-reversal ट्रिगर
    करायलाच हवं, आणि कुठलाही trade live_trades मध्ये साठवला जाऊ नये (मूळ position कधीच पूर्ण
    उभी राहिलीच नाही)."""

    def _strategy_result(self):
        return {
            "strategy": "BULL_PUT_SPREAD", "max_loss": 50, "max_profit": 30, "net_credit": 30,
            "legs": [
                {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL", "option_type": "PE", "expiry": "2026-08-28"},
                {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY", "option_type": "PE", "expiry": "2026-08-28"},
            ],
        }

    def test_partial_failure_triggers_reversal_and_returns_false(self, temp_db, monkeypatch):
        import notifications
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: None)
        partial_resp = {
            "status": "partial_failure",
            "verified_legs": [
                {"order_id": "O1", "status": "complete", "instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"},
                {"order_id": "O2", "status": "rejected", "instrument_token": "PE24300", "transaction_type": "BUY", "quantity": 75, "product": "D"},
            ],
        }
        reversal_calls = []

        def execute_side_effect(token, orders, mode, _call=[0]):
            _call[0] += 1
            if _call[0] == 1:
                return 200, partial_resp
            reversal_calls.append(orders)
            return 200, {"status": "success", "data": [{"order_id": "REV1"}]}

        monkeypatch.setattr(trading_engine, "execute_order_leg_set", execute_side_effect)

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
        )
        assert ok is False
        assert len(reversal_calls) == 1

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT COUNT(*) FROM live_trades").fetchone()
        conn.close()
        assert row[0] == 0

    def test_full_failure_zero_filled_legs_does_not_call_reversal_helper(self, temp_db, monkeypatch):
        error_resp = {"status": "error", "verified_legs": [
            {"order_id": "O1", "status": "rejected", "instrument_token": "PE24400", "transaction_type": "SELL", "quantity": 75, "product": "D"},
        ]}
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda token, orders, mode: (200, error_resp))
        reversal_called = []
        monkeypatch.setattr(trading_engine, "_auto_reverse_filled_legs", lambda *a, **k: reversal_called.append(1))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
        )
        assert ok is False
        assert not reversal_called  # "error" (0 legs भरले) -- partial_failure नाही, वेगळा मार्ग


class TestCheckKillSwitch:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit,
    गंभीर यादीतला चौथा मुद्दा) — आजचा एकूण LIVE तोटा/trade-count मर्यादेपलीकडे गेल्यावर नवीन LIVE
    trade अडवलं जायला हवं."""

    def test_disabled_always_ok_regardless_of_pnl(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: {"enabled": False, "max_daily_loss": 100, "max_trades_per_day": 1})
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: (-999999, 999))
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 0)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is True
        assert reason is None

    def test_daily_loss_breached_blocks(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: {"enabled": True, "max_daily_loss": 5000, "max_trades_per_day": 15})
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: (-6000, 2))
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 0)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False
        assert "KILL_SWITCH_DAILY_LOSS" in reason

    def test_max_trades_breached_blocks(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: {"enabled": True, "max_daily_loss": 5000, "max_trades_per_day": 15})
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: (500, 15))
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 0)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False
        assert "KILL_SWITCH_MAX_TRADES" in reason

    def test_within_limits_ok(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: {"enabled": True, "max_daily_loss": 5000, "max_trades_per_day": 15})
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: (-100, 3))
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 0)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is True
        assert reason is None

    def test_unverified_reconciled_trades_blocks_even_within_pnl_limits(self, monkeypatch):
        """🎓 वापरकर्त्याने लाईव्ह ट्रेडिंगआधी मागितलेल्या सखोल review मध्ये सापडवलेली bug —
        reconcile_open_trades_with_broker() externally बंद झालेल्या trade चा realized_pnl कधीच
        साठवत नाही (NULL राहतो), त्यामुळे तो तोटा COALESCE(SUM(...),0) मधून वगळला जातो —
        "आजचा तोटा ₹0" (मर्यादेच्या आतच) दिसत असला, तरी असे unverified trades असतील तर
        नवीन LIVE trading थांबायलाच हवं (fail-safe)."""
        monkeypatch.setattr(cloud_db, "get_kill_switch_settings", lambda: {"enabled": True, "max_daily_loss": 5000, "max_trades_per_day": 15})
        monkeypatch.setattr(trading_engine, "get_todays_live_total_pnl_and_count", lambda: (0, 1))
        monkeypatch.setattr(trading_engine, "get_unverified_reconciled_trades_today_count", lambda: 1)
        ok, reason = trading_engine.check_kill_switch()
        assert ok is False
        assert "KILL_SWITCH_UNVERIFIED_PNL" in reason


class TestOpenMultiLegTradeKillSwitch:
    def _strategy_result(self):
        return {
            "strategy": "BULL_PUT_SPREAD", "max_loss": 50, "max_profit": 30, "net_credit": 30,
            "legs": [
                {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL", "option_type": "PE", "expiry": "2026-08-28"},
                {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY", "option_type": "PE", "expiry": "2026-08-28"},
            ],
        }

    def test_live_blocked_by_kill_switch_skips_order_and_alerts(self, temp_db, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (False, "KILL_SWITCH_DAILY_LOSS — test"))
        execute_calls = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: execute_calls.append(1) or (200, {"status": "success"}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
        )
        assert ok is False
        assert resp["status"] == "error"
        assert "KILL_SWITCH_DAILY_LOSS" in resp["reason"]
        assert not execute_calls  # ऑर्डरच पाठवला गेला नाही
        assert len(telegram_calls) == 1
        assert "Kill Switch" in telegram_calls[0]

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT COUNT(*) FROM live_trades").fetchone()
        conn.close()
        assert row[0] == 0

    def test_paper_mode_never_checks_kill_switch(self, temp_db, monkeypatch):
        def _boom():
            raise AssertionError("PAPER mode ने कधीच kill switch तपासायला नको")
        monkeypatch.setattr(trading_engine, "check_kill_switch", _boom)
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["PAPER-1"]}]}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="PAPER",
        )
        assert ok is True

    def test_live_mode_kill_switch_ok_proceeds_normally(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["LIVE-1"]}]}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
        )
        assert ok is True


class TestCheckMarginAvailable:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Margin Check in Bots, गंभीर यादीतला
    सहावा मुद्दा) — page_dashboard.py च्या Strategy Builder मध्ये आधीपासूनच असलेला Pre-Trade Margin
    Check आता trading_engine.open_multi_leg_trade() (सर्व 3 bots चं LIVE choke-point) मध्येही."""

    def _strategy_result(self):
        return {"strategy": "BULL_PUT_SPREAD", "max_loss": 50, "max_profit": 30, "net_credit": 30}

    def test_adapter_path_uses_adapter_methods(self, monkeypatch):
        mock_adapter = MagicMock()
        mock_adapter.get_required_margin.return_value = 5000.0
        mock_adapter.get_funds.return_value = 10000.0
        ok, reason = trading_engine.check_margin_available("fake_token", mock_adapter, [{"o": 1}], self._strategy_result(), 1, 75)
        assert ok is True
        assert reason is None
        mock_adapter.get_required_margin.assert_called_once_with([{"o": 1}])
        mock_adapter.get_funds.assert_called_once()

    def test_raw_path_uses_upstox_functions(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "fetch_required_margin", lambda t, o: 5000.0)
        monkeypatch.setattr(trading_engine, "get_available_margin", lambda t: 10000.0)
        ok, reason = trading_engine.check_margin_available("fake_token", None, [{"o": 1}], self._strategy_result(), 1, 75)
        assert ok is True
        assert reason is None

    def test_required_margin_none_falls_back_to_max_loss(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "fetch_required_margin", lambda t, o: None)
        monkeypatch.setattr(trading_engine, "get_available_margin", lambda t: 3000.0)
        # max_loss=50 * lots=2 * lot_size=75 = 7500 -- उपलब्ध 3000 पेक्षा जास्त -- block व्हायलाच हवं
        ok, reason = trading_engine.check_margin_available("fake_token", None, [{"o": 1}], self._strategy_result(), 2, 75)
        assert ok is False
        assert "MARGIN_INSUFFICIENT" in reason

    def test_available_margin_none_does_not_block(self, monkeypatch):
        """उपलब्ध मार्जिन तपासताच आली नाही (Fyers सारखा broker) -- Dashboard प्रमाणेच सावधपणे
        पुढे जाऊ देतो, block करत नाही."""
        monkeypatch.setattr(trading_engine, "fetch_required_margin", lambda t, o: 999999.0)
        monkeypatch.setattr(trading_engine, "get_available_margin", lambda t: None)
        ok, reason = trading_engine.check_margin_available("fake_token", None, [{"o": 1}], self._strategy_result(), 1, 75)
        assert ok is True
        assert reason is None

    def test_insufficient_margin_blocks(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "fetch_required_margin", lambda t, o: 8000.0)
        monkeypatch.setattr(trading_engine, "get_available_margin", lambda t: 5000.0)
        ok, reason = trading_engine.check_margin_available("fake_token", None, [{"o": 1}], self._strategy_result(), 1, 75)
        assert ok is False
        assert "MARGIN_INSUFFICIENT" in reason
        assert "8,000" in reason
        assert "5,000" in reason

    def test_sufficient_margin_ok(self, monkeypatch):
        monkeypatch.setattr(trading_engine, "fetch_required_margin", lambda t, o: 5000.0)
        monkeypatch.setattr(trading_engine, "get_available_margin", lambda t: 8000.0)
        ok, reason = trading_engine.check_margin_available("fake_token", None, [{"o": 1}], self._strategy_result(), 1, 75)
        assert ok is True
        assert reason is None


class TestOpenMultiLegTradeMarginCheck:
    def _strategy_result(self):
        return {
            "strategy": "BULL_PUT_SPREAD", "max_loss": 50, "max_profit": 30, "net_credit": 30,
            "legs": [
                {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL", "option_type": "PE", "expiry": "2026-08-28"},
                {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY", "option_type": "PE", "expiry": "2026-08-28"},
            ],
        }

    def test_live_blocked_by_insufficient_margin_skips_order_and_alerts(self, temp_db, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "check_margin_available", lambda *a, **k: (False, "MARGIN_INSUFFICIENT — test"))
        execute_calls = []
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: execute_calls.append(1) or (200, {"status": "success"}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
        )
        assert ok is False
        assert resp["status"] == "error"
        assert "MARGIN_INSUFFICIENT" in resp["reason"]
        assert not execute_calls
        assert len(telegram_calls) == 1
        assert "मार्जिन" in telegram_calls[0]

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT COUNT(*) FROM live_trades").fetchone()
        conn.close()
        assert row[0] == 0

    def test_paper_mode_never_checks_margin(self, temp_db, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("PAPER mode ने कधीच margin तपासायला नको")
        monkeypatch.setattr(trading_engine, "check_margin_available", _boom)
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["PAPER-1"]}]}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="PAPER",
        )
        assert ok is True

    def test_live_mode_margin_ok_proceeds_normally(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "check_margin_available", lambda *a, **k: (True, None))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["LIVE-1"]}]}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
        )
        assert ok is True


class TestAlertCrossStrategyConflict:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (Cross-Strategy Conflict Check — फक्त अलर्ट, block नाही,
    वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय)."""

    def test_sends_alert_naming_other_strategies(self, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))

        trading_engine._alert_cross_strategy_conflict(
            "NIFTY", "dynamic_sr_instant", {"strategy": "BULL_PUT_SPREAD"},
            [{"source": "srv2_momentum_reversal", "strategy": "BEAR_CALL_SPREAD", "trade_id": "T1"}],
        )
        assert len(telegram_calls) == 1
        assert "NIFTY" in telegram_calls[0]
        assert "dynamic_sr_instant" in telegram_calls[0]
        assert "srv2_momentum_reversal" in telegram_calls[0]
        assert "BEAR_CALL_SPREAD" in telegram_calls[0]


class TestOpenMultiLegTradeCrossStrategyConflict:
    def _strategy_result(self):
        return {
            "strategy": "BULL_PUT_SPREAD", "max_loss": 50, "max_profit": 30, "net_credit": 30,
            "legs": [
                {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL", "option_type": "PE", "expiry": "2026-08-28"},
                {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY", "option_type": "PE", "expiry": "2026-08-28"},
            ],
        }

    def test_live_with_other_source_open_alerts_but_does_not_block(self, temp_db, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "check_margin_available", lambda *a, **k: (True, None))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["LIVE-1"]}]}))
        seed_trade(temp_db, "T_OTHER", 1000, -500, 500, source="srv2_momentum_reversal")

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
            source="dynamic_sr_instant",
        )
        assert ok is True  # अलर्ट पाठवला, पण trade ब्लॉक झाला नाही
        assert len(telegram_calls) == 1
        assert "Cross-Strategy Overlap" in telegram_calls[0]

    def test_live_with_no_other_source_open_no_alert(self, temp_db, monkeypatch):
        import notifications
        telegram_calls = []
        monkeypatch.setattr(notifications, "send_telegram_message", lambda msg: telegram_calls.append(msg))
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "check_margin_available", lambda *a, **k: (True, None))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["LIVE-1"]}]}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="LIVE",
            source="dynamic_sr_instant",
        )
        assert ok is True
        assert not telegram_calls

    def test_paper_mode_never_checks_cross_strategy_conflict(self, temp_db, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("PAPER mode ने कधीच cross-strategy conflict तपासायला नको")
        monkeypatch.setattr(trading_engine, "get_open_trades_by_other_sources", _boom)
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success", "data": [{"order_ids": ["PAPER-1"]}]}))

        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", self._strategy_result(), lots=1, lot_size=75,
            sl_pct_of_max_loss=50, target_pct_of_max_profit=100, product_type="D", trading_mode="PAPER",
        )
        assert ok is True


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
