"""
strategies/bb_squeeze.py
--------------------------
Strategy 6: Bollinger Band Squeeze + Volume Expansion Breakout

Data source: NIFTY 50 FUTURES candles (options chain नाही)
Logic:
  1. BB width (upper-lower)/middle हा rolling percentile मध्ये low आहे का
     (squeeze = low volatility, range-bound)
  2. Breakout candle: close BB band च्या बाहेर + volume spike (avg च्या X पट)
  3. ATR-based trailing SL (तुमच्या existing ATR trailing logic सोबत consistent)

Required snapshot.futures_ohlcv columns (precomputed upstream, ideally in data layer):
  ['open','high','low','close','volume','bb_upper','bb_lower','bb_middle','bb_width', 'atr']
  bb_width ही rolling series असावी जेणेकरून percentile काढता येईल
"""

from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType


class BBSqueezeStrategy(StrategyBase):
    strategy_id = "bb_squeeze"
    default_weight = 0.8
    max_concurrent_positions = 2

    def __init__(self, config=None):
        super().__init__(config)
        self.squeeze_percentile = self.config.get("squeeze_percentile", 20)   # bottom 20% width = squeeze
        self.volume_spike_multiplier = self.config.get("volume_spike_multiplier", 1.5)
        self.lookback = self.config.get("lookback", 50)
        self.atr_sl_multiplier = self.config.get("atr_sl_multiplier", 1.5)
        self.target_rr = self.config.get("target_rr", 2.0)

    def required_data(self):
        return ["futures_ohlcv"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        ohlcv = snapshot.futures_ohlcv
        if ohlcv is None or len(ohlcv) < self.lookback:
            return self._no_signal("insufficient futures_ohlcv history")

        window = ohlcv.tail(self.lookback)
        last = ohlcv.iloc[-1]
        prev = ohlcv.iloc[-2]

        required_cols = {"close", "bb_upper", "bb_lower", "bb_width", "volume", "atr"}
        if not required_cols.issubset(ohlcv.columns):
            return self._no_signal(f"missing columns: {required_cols - set(ohlcv.columns)}")

        # --- GATE 1: नुकताच squeeze होता का (breakout आधीच्या 1-3 candles मध्ये) ---
        width_percentile_rank = (window["bb_width"] < prev["bb_width"]).mean() * 100
        was_squeezed = width_percentile_rank <= self.squeeze_percentile
        if not was_squeezed:
            return self._no_signal(
                f"no recent squeeze (width percentile={width_percentile_rank:.1f})"
            )

        # --- GATE 2: Breakout — close band च्या बाहेर ---
        breakout_up = last["close"] > last["bb_upper"]
        breakout_down = last["close"] < last["bb_lower"]
        if not (breakout_up or breakout_down):
            return self._no_signal("no band breakout on latest candle")

        # --- GATE 3: Volume spike confirmation ---
        avg_volume = window["volume"].mean()
        volume_ok = last["volume"] >= avg_volume * self.volume_spike_multiplier
        if not volume_ok:
            return self._no_signal(
                f"volume spike missing (last={last['volume']:.0f}, avg={avg_volume:.0f})"
            )

        direction = Direction.LONG if breakout_up else Direction.SHORT
        confidence = 0.5 + min(0.5, (last["volume"] / avg_volume - self.volume_spike_multiplier) * 0.2)

        atr = last["atr"]
        entry = last["close"]
        sl = entry - atr * self.atr_sl_multiplier if direction == Direction.LONG else entry + atr * self.atr_sl_multiplier
        risk = abs(entry - sl)
        target = entry + risk * self.target_rr if direction == Direction.LONG else entry - risk * self.target_rr

        return SignalResult(
            strategy_id=self.strategy_id,
            direction=direction,
            confidence=round(min(confidence, 1.0), 3),
            instrument_type=InstrumentType.FUTURES,
            entry_price=entry,
            stop_loss=round(sl, 2),
            target=round(target, 2),
            timestamp=snapshot.timestamp,
            reason=f"BB squeeze breakout ({'up' if breakout_up else 'down'}) + volume spike x{last['volume']/avg_volume:.2f}",
            meta={"width_percentile": width_percentile_rank, "atr": atr},
        )

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id,
            direction=Direction.NONE,
            confidence=0.0,
            instrument_type=InstrumentType.FUTURES,
            reason=reason,
        )
