"""
tests/test_broker_side_sl_integration.py
--------------------------------------------
🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL", "PAPER mode मध्ये आधी
test करूया") — trading_engine.py मधल्या नवीन broker-side SL wiring (_resolve_broker_side_sl_premium_points/
_maybe_place_broker_side_sl/_maybe_cancel_broker_side_sl) आणि open_multi_leg_trade()/
manage_open_trades()/close_trade_manually() मधून प्रत्यक्ष कॉल होतो का याच्या चाचण्या.

वेगळ्या फाईलमध्ये (tests/test_trading_engine.py ऐवजी) ठेवलेलं — त्या फाईलमधले class names खूप
समान (trailing/repeated) आढळल्याने append करताना अस्पष्टता आली, नवीन, स्वतंत्र फाईल जास्त सुरक्षित.
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
    tmpdb = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(database, "DB_PATH", tmpdb)
    database.init_sqlite_db()
    monkeypatch.setattr(trading_engine, "DB_PATH", tmpdb)
    monkeypatch.setattr(trading_engine, "fetch_broker_positions", lambda access_token: [])
    monkeypatch.setattr(trading_engine, "check_margin_available", lambda *a, **k: (True, None))
    monkeypatch.setattr(trading_engine, "_resolve_required_margin", lambda *a, **k: 37500.0)
    yield tmpdb


def seed_trade(tmpdb, trade_id, net_credit, sl_level, target_level, strategy="NAKED_CALL", source=None,
               trading_style="INTRADAY", entry_level_price=None, legs=None):
    conn = sqlite3.connect(tmpdb)
    if legs is None:
        legs = [{"role": "naked_buy", "strike": 24400, "instrument_key": "CE24400", "transaction_type": "BUY"}]
    conn.execute(
        """INSERT INTO live_trades (trade_id, trade_date, symbol, strategy, lots, lot_size, net_credit,
           max_profit, max_loss, sl_pnl_level, target_pnl_level, entry_time, status, legs_json,
           strikes_summary, mode, trading_style, source, entry_level_price) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, "2026-08-24", "NIFTY", strategy, 1, 75, net_credit, net_credit, 50,
         sl_level, target_level, "2026-08-24 10:00:00", "OPEN", json.dumps(legs), "test", "LIVE",
         trading_style, source, entry_level_price),
    )
    conn.commit()
    conn.close()


class FakeTime(datetime.datetime):
    _fixed = None

    @classmethod
    def utcnow(cls):
        return cls._fixed


def _enabled_settings(**overrides):
    def _fn(strategy_name, symbol):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS[strategy_name])
        settings["broker_side_sl_enabled"] = True
        settings.update(overrides)
        return settings
    return _fn


class TestResolveBrokerSideSlPremiumPoints:
    def test_unsupported_source_returns_none(self):
        assert trading_engine._resolve_broker_side_sl_premium_points("MANUAL", "NIFTY", is_naked=True) is None
        assert trading_engine._resolve_broker_side_sl_premium_points("credit_spread_auto_trader", "NIFTY", is_naked=False) is None

    def test_disabled_by_default_returns_none(self, monkeypatch):
        monkeypatch.setattr(cloud_db, "get_connection", lambda: None)  # Supabase नाही -- शुद्ध डीफॉल्ट
        assert trading_engine._resolve_broker_side_sl_premium_points("dynamic_sr_instant", "NIFTY", is_naked=True) is None
        assert trading_engine._resolve_broker_side_sl_premium_points("classic_sr_reversal", "NIFTY", is_naked=False) is None
        assert trading_engine._resolve_broker_side_sl_premium_points("srv2_momentum_reversal", "NIFTY", is_naked=True) is None

    def test_enabled_returns_naked_vs_spread_premium_points(self, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        naked_points = trading_engine._resolve_broker_side_sl_premium_points("dynamic_sr_instant", "NIFTY", is_naked=True)
        spread_points = trading_engine._resolve_broker_side_sl_premium_points("dynamic_sr_instant", "NIFTY", is_naked=False)
        assert naked_points == cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["naked_sl_premium_points"]
        assert spread_points == cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["spread_sl_premium_points"]
        assert naked_points != spread_points


class TestMaybePlaceBrokerSideSl:
    def test_naked_paper_mode_is_dry_run_no_real_call(self, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        mock_place = MagicMock()
        monkeypatch.setattr(trading_engine, "upstox_place_stop_loss_order", mock_place)
        legs = [{"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", None, "PAPER", "dynamic_sr_instant", "NIFTY", legs,
            {"CE24400": 60.0}, lots=1, lot_size=75, strategy_name="NAKED_CALL", product_type="D",
        )
        assert not mock_place.called
        assert legs[0]["sl_order_id"] == "DRYRUN"
        naked_sl_pts = cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["naked_sl_premium_points"]
        assert legs[0]["sl_trigger_price"] == round(60.0 - naked_sl_pts, 1)

    def test_naked_live_no_adapter_uses_module_level_upstox_call(self, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        monkeypatch.setattr(
            trading_engine, "upstox_place_stop_loss_order",
            lambda token, ik, qty, txn, prod, trig: (200, {"status": "success", "data": {"order_id": "SL-N1"}}),
        )
        legs = [{"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", None, "LIVE", "dynamic_sr_instant", "NIFTY", legs,
            {"CE24400": 60.0}, lots=1, lot_size=75, strategy_name="NAKED_CALL", product_type="D",
        )
        assert legs[0]["sl_order_id"] == "SL-N1"
        naked_sl_pts = cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["naked_sl_premium_points"]
        assert legs[0]["sl_trigger_price"] == round(60.0 - naked_sl_pts, 1)

    def test_naked_live_with_adapter_calls_adapter_with_sell_to_close(self, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        mock_adapter = MagicMock()
        mock_adapter.supports_broker_side_stop_loss.return_value = True
        mock_adapter.place_stop_loss_order.return_value = "SL-A1"
        legs = [{"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", mock_adapter, "LIVE", "dynamic_sr_instant", "NIFTY", legs,
            {"CE24400": 60.0}, lots=2, lot_size=75, strategy_name="NAKED_CALL", product_type="D",
        )
        naked_sl_pts = cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["naked_sl_premium_points"]
        mock_adapter.place_stop_loss_order.assert_called_once_with(
            "CE24400", 150, "SELL", "D", round(60.0 - naked_sl_pts, 1),
        )
        assert legs[0]["sl_order_id"] == "SL-A1"

    def test_adapter_not_supporting_broker_side_sl_is_a_no_op(self, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        mock_adapter = MagicMock()
        mock_adapter.supports_broker_side_stop_loss.return_value = False
        legs = [{"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", mock_adapter, "LIVE", "dynamic_sr_instant", "NIFTY", legs,
            {"CE24400": 60.0}, lots=1, lot_size=75, strategy_name="NAKED_CALL", product_type="D",
        )
        assert not mock_adapter.place_stop_loss_order.called
        assert "sl_order_id" not in legs[0]

    def test_spread_uses_short_sell_leg_with_worst_case_trigger(self, monkeypatch):
        """Credit Spread -- फक्त SHORT (SELL) leg वर SL, hedge leg स्थिर आहे असं worst-case गृहीत
        धरून trigger_price = entry_short + sl_premium_points (BUY-to-close, वर वाढला की SL)."""
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        mock_adapter = MagicMock()
        mock_adapter.supports_broker_side_stop_loss.return_value = True
        mock_adapter.place_stop_loss_order.return_value = "SL-S1"
        legs = [
            {"role": "short_leg", "instrument_key": "PE24400", "transaction_type": "SELL"},
            {"role": "long_hedge", "instrument_key": "PE24300", "transaction_type": "BUY"},
        ]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", mock_adapter, "LIVE", "dynamic_sr_instant", "NIFTY", legs,
            {"PE24400": 30.0, "PE24300": 10.0}, lots=1, lot_size=75,
            strategy_name="BULL_PUT_SPREAD", product_type="D",
        )
        spread_sl_pts = cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["spread_sl_premium_points"]
        mock_adapter.place_stop_loss_order.assert_called_once_with(
            "PE24400", 75, "BUY", "D", round(30.0 + spread_sl_pts, 1),
        )
        assert "sl_order_id" not in legs[1]  # हेज (long) leg ला touch केलं जात नाही
        assert legs[0]["sl_order_id"] == "SL-S1"

    def test_placement_failure_logs_but_leaves_trigger_price_and_no_order_id(self, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        mock_adapter = MagicMock()
        mock_adapter.supports_broker_side_stop_loss.return_value = True
        mock_adapter.place_stop_loss_order.return_value = None  # अयशस्वी
        legs = [{"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", mock_adapter, "LIVE", "dynamic_sr_instant", "NIFTY", legs,
            {"CE24400": 60.0}, lots=1, lot_size=75, strategy_name="NAKED_CALL", product_type="D",
        )
        assert "sl_order_id" not in legs[0]
        assert "sl_trigger_price" in legs[0]  # गणित तरीही साठवलेलं आहे

    def test_unsupported_source_is_a_no_op(self):
        legs = [{"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}]
        trading_engine._maybe_place_broker_side_sl(
            "fake_token", None, "LIVE", "MANUAL", "NIFTY", legs,
            {"CE24400": 60.0}, lots=1, lot_size=75, strategy_name="NAKED_CALL", product_type="D",
        )
        assert legs[0] == {"role": "naked_buy", "instrument_key": "CE24400", "transaction_type": "BUY"}


class TestMaybeCancelBrokerSideSl:
    def test_dryrun_order_id_is_skipped_no_real_call(self, monkeypatch):
        mock_cancel = MagicMock()
        monkeypatch.setattr(trading_engine, "upstox_cancel_order", mock_cancel)
        legs = [{"instrument_key": "CE24400", "sl_order_id": "DRYRUN"}]
        trading_engine._maybe_cancel_broker_side_sl("fake_token", None, legs)
        assert not mock_cancel.called

    def test_no_order_id_is_skipped(self, monkeypatch):
        mock_cancel = MagicMock()
        monkeypatch.setattr(trading_engine, "upstox_cancel_order", mock_cancel)
        legs = [{"instrument_key": "CE24400"}]
        trading_engine._maybe_cancel_broker_side_sl("fake_token", None, legs)
        assert not mock_cancel.called

    def test_real_order_id_no_adapter_calls_module_level_cancel(self, monkeypatch):
        mock_cancel = MagicMock(return_value=(200, {"status": "success"}))
        monkeypatch.setattr(trading_engine, "upstox_cancel_order", mock_cancel)
        legs = [{"instrument_key": "CE24400", "sl_order_id": "SL-N1"}]
        trading_engine._maybe_cancel_broker_side_sl("fake_token", None, legs)
        mock_cancel.assert_called_once_with("fake_token", "SL-N1")

    def test_real_order_id_with_adapter_calls_adapter_cancel(self):
        mock_adapter = MagicMock()
        mock_adapter.cancel_order.return_value = True
        legs = [{"instrument_key": "CE24400", "sl_order_id": "SL-A1"}]
        trading_engine._maybe_cancel_broker_side_sl("fake_token", mock_adapter, legs)
        mock_adapter.cancel_order.assert_called_once_with("SL-A1")

    def test_cancel_exception_does_not_propagate(self):
        mock_adapter = MagicMock()
        mock_adapter.cancel_order.side_effect = Exception("network boom")
        legs = [{"instrument_key": "CE24400", "sl_order_id": "SL-A1"}]
        trading_engine._maybe_cancel_broker_side_sl("fake_token", mock_adapter, legs)  # राईज होता कामा नये

    def test_multiple_legs_only_cancels_ones_with_real_order_id(self, monkeypatch):
        mock_cancel = MagicMock(return_value=(200, {"status": "success"}))
        monkeypatch.setattr(trading_engine, "upstox_cancel_order", mock_cancel)
        legs = [
            {"instrument_key": "PE24400", "sl_order_id": "SL-S1"},
            {"instrument_key": "PE24300"},  # hedge leg -- कधीच SL order नव्हता
        ]
        trading_engine._maybe_cancel_broker_side_sl("fake_token", None, legs)
        mock_cancel.assert_called_once_with("fake_token", "SL-S1")


class TestBrokerSideSlEndToEndIntegration:
    def test_open_multi_leg_trade_paper_mode_dry_runs_and_stores_no_real_order_id(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 60.0 for kk in k})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set",
                             lambda t, o, m: (200, {"status": "success", "data": {"order_ids": ["T1"]}}))
        mock_place = MagicMock()
        monkeypatch.setattr(trading_engine, "upstox_place_stop_loss_order", mock_place)

        strategy_result = {
            "strategy": "NAKED_CALL",
            "buy_leg": {"strike": 24400, "instrument_key": "CE24400", "ltp": 60},
            "net_credit": -60, "max_profit": None, "max_loss": 60,
        }
        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", strategy_result, lots=1, lot_size=75,
            sl_pct_of_max_loss=999, target_pct_of_max_profit=30, product_type="D",
            trading_mode="PAPER", trading_style="INTRADAY", source="dynamic_sr_instant",
        )
        assert ok is True
        assert not mock_place.called  # PAPER -- कधीच खरा order नाही

        conn = sqlite3.connect(temp_db)
        legs_json = conn.execute("SELECT legs_json FROM live_trades WHERE trade_id=?", (resp["trade_id"],)).fetchone()[0]
        conn.close()
        legs = json.loads(legs_json)
        assert legs[0]["sl_order_id"] == "DRYRUN"
        assert "sl_trigger_price" in legs[0]

    def test_open_multi_leg_trade_live_mode_stores_real_order_id(self, temp_db, monkeypatch):
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings())
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {kk: 60.0 for kk in k})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set",
                             lambda t, o, m: (200, {"status": "success", "data": {"order_ids": ["T1"]}}))
        monkeypatch.setattr(
            trading_engine, "upstox_place_stop_loss_order",
            lambda token, ik, qty, txn, prod, trig: (200, {"status": "success", "data": {"order_id": "SL-LIVE1"}}),
        )
        monkeypatch.setattr(trading_engine, "check_kill_switch", lambda: (True, None))
        monkeypatch.setattr(trading_engine, "get_open_trades_by_other_sources", lambda symbol, source: [])

        strategy_result = {
            "strategy": "NAKED_CALL",
            "buy_leg": {"strike": 24400, "instrument_key": "CE24400", "ltp": 60},
            "net_credit": -60, "max_profit": None, "max_loss": 60,
        }
        ok, resp = trading_engine.open_multi_leg_trade(
            "fake_token", "NIFTY", strategy_result, lots=1, lot_size=75,
            sl_pct_of_max_loss=999, target_pct_of_max_profit=30, product_type="D",
            trading_mode="LIVE", trading_style="INTRADAY", source="dynamic_sr_instant",
        )
        assert ok is True
        conn = sqlite3.connect(temp_db)
        legs_json = conn.execute("SELECT legs_json FROM live_trades WHERE trade_id=?", (resp["trade_id"],)).fetchone()[0]
        conn.close()
        legs = json.loads(legs_json)
        assert legs[0]["sl_order_id"] == "SL-LIVE1"

    def test_manage_open_trades_cancels_pending_sl_order_on_close(self, temp_db, monkeypatch):
        """SL आधीच broker कडे ठेवलेला (sl_order_id) trade, TARGET कारणाने बंद होतोय -- pending
        SL order cancel व्हायलाच हवा, नाहीतर तो नंतर चुकून trigger होऊ शकतो."""
        legs_with_sl = [{"role": "naked_buy", "strike": 24400, "instrument_key": "CE24400",
                          "transaction_type": "BUY", "sl_order_id": "SL-OLD1", "sl_trigger_price": 30.0}]
        seed_trade(temp_db, "TCANCEL1", net_credit=-60, sl_level=-4500, target_level=750,
                   strategy="NAKED_CALL", source="dynamic_sr_instant", trading_style="INTRADAY",
                   entry_level_price=23900.0, legs=legs_with_sl)
        monkeypatch.setattr(trading_engine.cloud_db, "get_strategy_settings", _enabled_settings(
            naked_target_spot_pct=0.01, naked_target_premium_points=1,  # लगेच TARGET लागावा म्हणून सैल
        ))

        def _ltp(token, keys):
            if keys == ["NSE_INDEX|Nifty 50"]:
                return {"NSE_INDEX|Nifty 50": 23950.0}  # +0.21% -- target_spot_pct (0.01%) पेक्षा जास्त
            return {"CE24400": 90.0}

        monkeypatch.setattr(trading_engine, "fetch_ltp_map", _ltp)
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        mock_cancel = MagicMock(return_value=(200, {"status": "success"}))
        monkeypatch.setattr(trading_engine, "upstox_cancel_order", mock_cancel)
        FakeTime._fixed = datetime.datetime(2026, 8, 24, 5, 0)
        monkeypatch.setattr(trading_engine.datetime, "datetime", FakeTime)

        closed = trading_engine.manage_open_trades("fake_token", "NIFTY", "D")
        assert len(closed) == 1
        assert closed[0]["reason"] == "TARGET"
        mock_cancel.assert_called_once_with("fake_token", "SL-OLD1")

    def test_close_trade_manually_cancels_pending_sl_order(self, temp_db, monkeypatch):
        legs_with_sl = [{"role": "naked_buy", "strike": 24400, "instrument_key": "CE24400",
                          "transaction_type": "BUY", "sl_order_id": "SL-OLD2", "sl_trigger_price": 30.0}]
        seed_trade(temp_db, "TCANCEL2", net_credit=-60, sl_level=-4500, target_level=100000,
                   strategy="NAKED_CALL", source="dynamic_sr_instant", trading_style="INTRADAY",
                   legs=legs_with_sl)
        monkeypatch.setattr(trading_engine, "fetch_ltp_map", lambda t, k: {"CE24400": 65.0})
        monkeypatch.setattr(trading_engine, "execute_order_leg_set", lambda t, o, m: (200, {"status": "success"}))
        mock_cancel = MagicMock(return_value=(200, {"status": "success"}))
        monkeypatch.setattr(trading_engine, "upstox_cancel_order", mock_cancel)

        ok, pnl = trading_engine.close_trade_manually("fake_token", "TCANCEL2", "NIFTY", "D")
        assert ok is True
        mock_cancel.assert_called_once_with("fake_token", "SL-OLD2")
