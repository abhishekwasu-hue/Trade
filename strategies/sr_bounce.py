"""
strategies/sr_bounce.py
--------------------------
Strategy 5: High-Probability S/R Bounce

चर्चा करून ठरवलेली रणनीती — फक्त Bounce (mean-reversion), Breakout नाही:
  १. S/R Levels: 1H (Higher Timeframe) वर शोधलेले — जास्त विश्वासार्ह, कमी नॉइझ. फक्त high-probability
     (`touches >= min_touches`, आधीच्या Dashboard सुधारणेतलाच touch-count) levels वापरले जातात.
  २. Entry: 15M (सद्य/मुख्य Timeframe) वर — किंमत त्या level च्या tolerance% च्या आत आली (Retest), आणि
     त्याच bar वर (किंवा मागच्या काही bars मध्ये) reversal candlestick pattern.
  ३. दिशा: मजबूत Support जवळ → LONG (bounce अपेक्षा); मजबूत Resistance जवळ → SHORT (bounce अपेक्षा).
  ४. SL: level च्या थोडं पलीकडे (तुटला तर थीसिस चुकीची). Target: विरुद्ध दिशेचा पुढचा S/R level
     (उपलब्ध असल्यास), नाहीतर किमान Risk:Reward.

Required snapshot.futures_ohlcv: 15M (किंवा मुख्य timeframe) candles.
Required snapshot.extra["sr_levels_1h"]: {"support": [{"level":x,"touches":n},...], "resistance": [...]}
(1H वरून, no-lookahead पद्धतीने बाहेरून दिलेलं — याच फाईलमध्ये संगणन होत नाही, कारण त्यासाठी 1H डेटा
वेगळा लागतो, जो orchestrator/backtest कडून दिला जातो, VWAP strategy च्या trend_direction_1h सारखंच).
"""
from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType
from signals import detect_candlestick_pattern, find_reversal_candle_recent


class SRBounceStrategy(StrategyBase):
    strategy_id = "sr_bounce"
    default_weight = 1.0
    max_concurrent_positions = 2

    def __init__(self, config=None):
        super().__init__(config)
        self.min_touches = self.config.get("min_touches", 3)          # high-probability साठी किमान touches
        self.retest_tolerance_pct = self.config.get("retest_tolerance_pct", 0.15)
        self.pattern_lookback = self.config.get("pattern_lookback", 3)
        # 🎓 SL आता entry (index) किमतीच्या सरळ ठराविक % वर — आधीची level+buffer+floor पद्धत काढली,
        # ही जास्त सोपी आणि सुसंगत आहे (उदा. NIFTY ~24000 वर 0.25% म्हणजे ~60 पॉइंट्स)
        self.sl_pct = self.config.get("sl_pct", 0.25)
        self.target_rr = self.config.get("target_rr", 2.0)             # पुढचा S/R level नसेल तर किमान RR

    def required_data(self):
        return ["futures_ohlcv"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        ohlcv = snapshot.futures_ohlcv
        if ohlcv is None or len(ohlcv) < self.pattern_lookback + 1:
            return self._no_signal("insufficient futures_ohlcv history")

        sr_1h = (snapshot.extra or {}).get("sr_levels_1h")
        if not sr_1h or not (sr_1h.get("support") or sr_1h.get("resistance")):
            return self._no_signal("1H वर कुठलाही high-probability S/R level उपलब्ध नाही")

        support_levels = sorted([s for s in sr_1h.get("support", []) if s["touches"] >= self.min_touches], key=lambda x: -x["touches"])
        resistance_levels = sorted([r for r in sr_1h.get("resistance", []) if r["touches"] >= self.min_touches], key=lambda x: -x["touches"])
        if not support_levels and not resistance_levels:
            return self._no_signal(f"min_touches={self.min_touches} पेक्षा जास्त touches असलेला कुठलाही level नाही")

        last = ohlcv.iloc[-1]

        # --- GATE 1+2: Retest + Candlestick Confirmation — Support (LONG) आधी तपासणे ---
        for s in support_levels:
            level = s["level"]
            tolerance = level * (self.retest_tolerance_pct / 100)
            if last["low"] <= level + tolerance:
                pattern = self._confirm_pattern(ohlcv, "BULLISH")
                if pattern:
                    return self._build_signal(Direction.LONG, last["close"], level, s["touches"], pattern, resistance_levels, snapshot.timestamp)
                return self._no_signal(f"Support({s['touches']}x, {level:.2f}) जवळ आलं, पण candlestick confirmation नाही")

        # --- Resistance (SHORT) ---
        for r in resistance_levels:
            level = r["level"]
            tolerance = level * (self.retest_tolerance_pct / 100)
            if last["high"] >= level - tolerance:
                pattern = self._confirm_pattern(ohlcv, "BEARISH")
                if pattern:
                    return self._build_signal(Direction.SHORT, last["close"], level, r["touches"], pattern, support_levels, snapshot.timestamp)
                return self._no_signal(f"Resistance({r['touches']}x, {level:.2f}) जवळ आलं, पण candlestick confirmation नाही")

        return self._no_signal("कुठल्याही high-probability S/R level जवळ सद्य किंमत नाही")

    def _confirm_pattern(self, ohlcv, direction_str):
        pattern = detect_candlestick_pattern(ohlcv)
        bullish, bearish = ("HAMMER", "BULLISH_ENGULFING", "MORNING_STAR"), ("SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR")
        valid = bullish if direction_str == "BULLISH" else bearish
        if pattern in valid:
            return pattern
        recent = find_reversal_candle_recent(ohlcv, direction_str, lookback=self.pattern_lookback)
        return recent["pattern"] if recent else None

    def _build_signal(self, direction, entry, level, touches, pattern, opposite_levels, timestamp):
        # SL — entry (index) किमतीच्या सरळ sl_pct% वर (S/R level वर आधारित buffer/floor ऐवजी)
        sl_distance = entry * (self.sl_pct / 100)
        sl = entry - sl_distance if direction == Direction.LONG else entry + sl_distance
        risk = abs(entry - sl)

        # Target: विरुद्ध दिशेचा जवळचा S/R level (असल्यास), नाहीतर किमान RR
        target = None
        if opposite_levels:
            if direction == Direction.LONG:
                candidates = [l["level"] for l in opposite_levels if l["level"] > entry]
                target = min(candidates) if candidates else None
            else:
                candidates = [l["level"] for l in opposite_levels if l["level"] < entry]
                target = max(candidates) if candidates else None
        if target is None or abs(target - entry) < risk * self.target_rr:
            target = entry + risk * self.target_rr if direction == Direction.LONG else entry - risk * self.target_rr

        confidence = min(1.0, 0.5 + touches * 0.1)  # जितके जास्त touches, तितका जास्त आत्मविश्वास
        return SignalResult(
            strategy_id=self.strategy_id, direction=direction, confidence=round(confidence, 3),
            instrument_type=InstrumentType.FUTURES,
            entry_price=round(entry, 2), stop_loss=round(sl, 2), target=round(target, 2),
            timestamp=timestamp,
            reason=f"1H {'Support' if direction==Direction.LONG else 'Resistance'} Bounce ({touches}x touches) @ {level:.2f}, confirmed by {pattern}",
            meta={"level": level, "touches": touches, "pattern": pattern},
        )

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id, direction=Direction.NONE, confidence=0.0,
            instrument_type=InstrumentType.FUTURES, reason=reason,
        )
