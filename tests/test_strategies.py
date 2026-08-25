"""
tests/test_strategies.py
----------------------------
strategies/ package — ५ orchestrator strategies (oi_pcr, ict_fvg, bb_squeeze, vwap, sr_bounce).
प्रत्येकाची मूलभूत sanity (कधीच crash न होणे + अपेक्षित परिस्थितीत सिग्नल देणे) तपासली जाते.
"""
import datetime

import pandas as pd
import pytz

from strategies import STRATEGY_REGISTRY, Direction
from strategies.base import MarketSnapshot
from strategies.sr_bounce import SRBounceStrategy

IST = pytz.timezone("Asia/Kolkata")


def test_all_five_strategies_registered():
    assert set(STRATEGY_REGISTRY.keys()) == {"oi_pcr", "ict_fvg", "bb_squeeze", "vwap", "sr_bounce"}


def test_all_strategies_handle_empty_snapshot_gracefully(trending_up_df):
    """कुठलाही strategy अपुऱ्या/रिकाम्या डेटावर crash न होता, फक्त NONE सिग्नल द्यायला हवा."""
    empty_snap = MarketSnapshot(timestamp=datetime.datetime.now(IST), futures_ohlcv=pd.DataFrame())
    for strategy_id, cls in STRATEGY_REGISTRY.items():
        strat = cls()
        result = strat.check_gates(empty_snap)
        assert result.direction == Direction.NONE, f"{strategy_id} रिकाम्या डेटावर सिग्नल देतोय (crash नाही, पण चुकीचं)"


class TestSRBounceStrategy:
    """sr_bounce — 1H high-probability S/R level जवळ bounce + candlestick confirmation."""

    def test_long_signal_on_support_bounce_with_hammer(self):
        strat = SRBounceStrategy(config={"min_touches": 3, "retest_tolerance_pct": 0.15, "sl_pct": 0.25, "target_rr": 2.0})
        rows = []
        for i in range(10):
            p = 24050 + i * 2
            rows.append({"open": p + 1, "close": p, "high": p + 5, "low": p - 5})
        rows.append({"open": 24003, "close": 24004, "high": 24004.5, "low": 23988})  # Hammer, support(24000) जवळ
        df_test = pd.DataFrame(rows)
        sr_1h = {"support": [{"level": 24000, "touches": 4}], "resistance": []}
        snap = MarketSnapshot(timestamp=datetime.datetime.now(IST), futures_ohlcv=df_test, extra={"sr_levels_1h": sr_1h})
        result = strat.check_gates(snap)
        assert result.direction == Direction.LONG
        assert result.stop_loss < result.entry_price

    def test_sl_is_exactly_fixed_percent_of_entry(self):
        strat = SRBounceStrategy(config={"min_touches": 3, "sl_pct": 0.25})
        rows = []
        for i in range(10):
            p = 24050 + i * 2
            rows.append({"open": p + 1, "close": p, "high": p + 5, "low": p - 5})
        rows.append({"open": 24003, "close": 24004, "high": 24004.5, "low": 23988})
        df_test = pd.DataFrame(rows)
        sr_1h = {"support": [{"level": 24000, "touches": 4}], "resistance": []}
        snap = MarketSnapshot(timestamp=datetime.datetime.now(IST), futures_ohlcv=df_test, extra={"sr_levels_1h": sr_1h})
        result = strat.check_gates(snap)
        expected_distance = result.entry_price * 0.0025
        assert abs(abs(result.entry_price - result.stop_loss) - expected_distance) < 0.1

    def test_no_signal_without_1h_sr_data(self, trending_up_df):
        strat = SRBounceStrategy()
        snap = MarketSnapshot(timestamp=datetime.datetime.now(IST), futures_ohlcv=trending_up_df)
        result = strat.check_gates(snap)
        assert result.direction == Direction.NONE
