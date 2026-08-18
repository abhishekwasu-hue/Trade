"""
strategies/vwap.py
---------------------
Strategy 2: VWAP Mean-Reversion / Trend-Continuation

Data source: NIFTY 50 FUTURES candles
Two modes (config मध्ये निवडा — mode: "reversion" / "trend" / "both"):
  - reversion: price VWAP पासून N std-dev लांब गेल्यास, VWAP कडे परत येण्याची अपेक्षा (fade)
  - trend: price VWAP च्या सातत्याने वर/खाली राहिल्यास (sustained), trend-following entry

Required snapshot.futures_ohlcv columns:
  ['close','volume','vwap','vwap_std']   # vwap_std = rolling std-dev of (close - vwap)
"""

from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType


class VWAPStrategy(StrategyBase):
    strategy_id = "vwap"
    default_weight = 1.0
    max_concurrent_positions = 2

    def __init__(self, config=None):
        super().__init__(config)
        self.mode = self.config.get("mode", "both")            # reversion / trend / both
        self.reversion_std_threshold = self.config.get("reversion_std_threshold", 2.0)
        self.trend_sustain_candles = self.config.get("trend_sustain_candles", 5)
        self.target_rr = self.config.get("target_rr", 1.5)
        self.sl_std_multiplier = self.config.get("sl_std_multiplier", 1.0)

    def required_data(self):
        return ["futures_ohlcv"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        ohlcv = snapshot.futures_ohlcv
        if ohlcv is None or len(ohlcv) < self.trend_sustain_candles + 1:
            return self._no_signal("insufficient futures_ohlcv history")

        required_cols = {"close", "vwap", "vwap_std"}
        if not required_cols.issubset(ohlcv.columns):
            return self._no_signal(f"missing columns: {required_cols - set(ohlcv.columns)}")

        last = ohlcv.iloc[-1]
        deviation = last["close"] - last["vwap"]
        std = max(last["vwap_std"], 1e-6)
        z_score = deviation / std

        signal = None

        # --- Reversion mode ---
        if self.mode in ("reversion", "both") and abs(z_score) >= self.reversion_std_threshold:
            direction = Direction.SHORT if z_score > 0 else Direction.LONG  # fade the extreme
            confidence = min(1.0, abs(z_score) / (self.reversion_std_threshold * 2))
            sl = last["close"] + std * self.sl_std_multiplier if direction == Direction.SHORT else last["close"] - std * self.sl_std_multiplier
            risk = abs(last["close"] - sl)
            target = last["vwap"]  # reversion target = VWAP itself
            signal = SignalResult(
                strategy_id=self.strategy_id,
                direction=direction,
                confidence=round(confidence, 3),
                instrument_type=InstrumentType.FUTURES,
                entry_price=last["close"],
                stop_loss=round(sl, 2),
                target=round(target, 2),
                timestamp=snapshot.timestamp,
                reason=f"VWAP mean-reversion, z-score={z_score:.2f}",
                meta={"mode": "reversion", "z_score": z_score},
            )

        # --- Trend mode: last N candles सातत्याने एकाच बाजूला ---
        if signal is None and self.mode in ("trend", "both"):
            recent = ohlcv.tail(self.trend_sustain_candles)
            all_above = (recent["close"] > recent["vwap"]).all()
            all_below = (recent["close"] < recent["vwap"]).all()
            if all_above or all_below:
                direction = Direction.LONG if all_above else Direction.SHORT
                confidence = 0.6  # trend confirmation आहे, पण extreme नाही म्हणून moderate
                sl = last["vwap"] - std * self.sl_std_multiplier if direction == Direction.LONG else last["vwap"] + std * self.sl_std_multiplier
                risk = abs(last["close"] - sl)
                target = last["close"] + risk * self.target_rr if direction == Direction.LONG else last["close"] - risk * self.target_rr
                signal = SignalResult(
                    strategy_id=self.strategy_id,
                    direction=direction,
                    confidence=confidence,
                    instrument_type=InstrumentType.FUTURES,
                    entry_price=last["close"],
                    stop_loss=round(sl, 2),
                    target=round(target, 2),
                    timestamp=snapshot.timestamp,
                    reason=f"VWAP trend-continuation, sustained {self.trend_sustain_candles} candles {'above' if all_above else 'below'} VWAP",
                    meta={"mode": "trend"},
                )

        if signal is None:
            return self._no_signal(f"no VWAP condition met (z_score={z_score:.2f})")
        return signal

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id,
            direction=Direction.NONE,
            confidence=0.0,
            instrument_type=InstrumentType.FUTURES,
            reason=reason,
        )
