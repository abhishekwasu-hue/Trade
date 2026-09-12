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

import pytest

import database
import trading_engine


@pytest.fixture
def temp_db(monkeypatch):
    """प्रत्येक test साठी नवीन, स्वतंत्र तात्पुरता SQLite DB."""
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    yield tmpdb


def seed_trade(tmpdb, trade_id, net_credit, sl_level, target_level, strategy="BULL_PUT_SPREAD", source=None, trading_style="SWING", peak_pnl=None, entry_level_price=None, mode="PAPER"):
    conn = sqlite3.connect(tmpdb)
    legs = [
        {"role": "short_leg", "strike": 24400, "instrument_key": "PE24400", "transaction_type": "SELL"},
        {"role": "long_hedge", "strike": 24300, "instrument_key": "PE24300", "transaction_type": "BUY"},
    ]
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json,
           strikes_summary, mode, trading_style, source, peak_pnl, entry_level_price) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-08-24", "NIFTY", strategy, 1, 75, net_credit, net_credit, 50,
         sl_level, target_level, "2026-08-24 10:00:00", "OPEN", json.dumps(legs), "test", mode, trading_style, source, peak_pnl, entry_level_price),
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

    def test_bullish_spot_target_hit(self, temp_db, monkeypatch):
        # entry_level_price=23900 (Support, Bull Put Spread) -- Target = 23900*1.0020=23947.8
        seed_trade(temp_db, "T10", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23950.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)  # सकाळी, EOD च्या खूप आधी
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SPOT_TARGET"

    def test_bullish_spot_sl_hit(self, temp_db, monkeypatch):
        # SL = 23900*0.9995=23888.05 -- स्पॉट त्याखाली गेला
        seed_trade(temp_db, "T11", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23880.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SPOT_SL"

    def test_bullish_neither_target_nor_sl_stays_open(self, temp_db, monkeypatch):
        seed_trade(temp_db, "T12", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23910.0))  # SL आणि Target च्या दरम्यान
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

    def test_premium_sl_hit_when_spot_neutral(self, temp_db, monkeypatch):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Next-Level-Exit काढून, निव्वळ प्रीमियम-आधारित
        SL(10%)/Target(25%, Trailing सह) जोडलेला — स्पॉट neutral (SL/Target च्या दरम्यान) असतानाही,
        फक्त प्रीमियम-हालचालीनेच बंद व्हायला हवं."""
        # net_credit=30, lot_size=75 -> net_credit_total=2250. -10% म्हणजे
        # established -225. established (net_credit - cost_to_close_now)*75 = -225 -> cost_to_close_now = 33.
        seed_trade(temp_db, "T30", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=33.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "PREMIUM_SL"

    def test_premium_target_hit_when_spot_neutral(self, temp_db, monkeypatch):
        # net_credit_total=2250, +25% = 562.5. cost_to_close_now = 30 - 562.5/75 = 22.5
        seed_trade(temp_db, "T31", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=22.5, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "PREMIUM_TARGET"

    def test_premium_trailing_sl_active_and_triggers(self, temp_db, monkeypatch):
        """आधीचा साठवलेला peak_pnl (net_credit_total 2250 च्या 10% पेक्षा जास्त, आधीच सक्रिय झालेला)
        -- lock = peak - 5%(112.5). किंमत परत आली, सद्य pnl त्या lock पेक्षा कमी -> बंद व्हायला हवं."""
        seed_trade(temp_db, "T32", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BULL_PUT_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, peak_pnl=300)  # 300/2250=13.3%, आधीच 10% ओलांडलेला
        # peak(300) - lock(112.5) = 187.5 -> सद्य pnl त्यापेक्षा कमी हवा
        # cost_to_close_now = 30 - 150/75 = 28
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map_with_options(23910.0, ce_ltp=28.0, pe_ltp=0.0))
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "PREMIUM_TRAILING_SL"

    def test_bearish_spot_target_and_sl(self, temp_db, monkeypatch):
        # entry_level_price=24000 (Resistance, Bear Call Spread) -- Target = 24000*0.9980=23952 (खाली)
        seed_trade(temp_db, "T13", net_credit=30, sl_level=-1125, target_level=1125,
                   strategy="BEAR_CALL_SPREAD", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=24000.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23940.0))  # Target-पातळी 23952 च्या खाली
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SPOT_TARGET"

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
        """🎓 वापरकर्त्याशी चर्चा करून बदललेली सुधारणा — srv2_momentum_reversal साठी आता जुनी
        %-Trailing SL नाही, स्पॉट-आधारित SL (0.10%, entry_level_price पासून प्रतिकूल दिशेने)."""
        seed_trade(temp_db, "T8", net_credit=30, sl_level=-2250, target_level=2250,
                   strategy="BULL_PUT_SPREAD", source="srv2_momentum_reversal", trading_style="INTRADAY",
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(23875.0))  # -0.105%, SL पेक्षा जास्त
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: None)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "SPOT_SL"

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
                   entry_level_price=23900.0)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", self._mock_ltp_map(24005.0))  # पुढचा level (24000) ओलांडला
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        monkeypatch.setattr(trading_engine.cloud_db, "get_next_level_in_direction", lambda *a, **k: 24000.0)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)
        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "NEXT_LEVEL_EXIT"

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
