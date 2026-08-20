"""
strategies/vwap.py
---------------------
Strategy 2: VWAP Trend + Retracement (Standard/Regular VWAP रणनीती)

जुनं mean-reversion / 5-candle-persistence logic पूर्णपणे काढून, याऐवजी standard, व्यावसायिक
"VWAP-आधारित trend + pullback entry" रणनीती:

  १. दिशा (Trend): snapshot.extra["trend_direction_1h"] मध्ये दिलेली असल्यास तीच वापरली जाते (1H
     Supertrend वरून — आपल्याच मुख्य A1 Engine शी सुसंगत); नसेल तर जुनी पद्धत (close vs VWAP) कडे मागे
     जाते (उदा. demo_test.py सारख्या स्वतंत्र/synthetic टेस्टिंगसाठी)
  २. Extension पुष्टीकरण: गेल्या काही bars मध्ये किंमत VWAP पासून खरंच लांब गेली होती का (खरा trend
     आहे याची खात्री — नुसता chop/noise नाही)
  ३. Retracement: किंमत आता परत VWAP जवळ आलीये (pullback) — हीच entry संधी
  ४. 🎓 Candlestick Confirmation (नवीन, कडक गेट — डीफॉल्ट चालू): retracement candle स्वतःच reversal
     candlestick pattern (Hammer/Bullish Engulfing/Morning Star, किंवा उलट) दाखवते का — फक्त VWAP जवळ
     येणं पुरेसं नाही, प्रत्यक्ष उलटफेराचा candlestick संकेतही हवा
  ५. 🎓 RSI Filter (नवीन, कडक गेट — डीफॉल्ट चालू): LONG साठी RSI आधीच खूप overbought नसावा (जास्तीत
     जास्त rsi_long_max), SHORT साठी आधीच खूप oversold नसावा — आधीच "थकलेल्या" हालचालीत entry टाळणे
  ६. Entry: trend च्याच दिशेने (उदा. Uptrend मध्ये VWAP जवळ आल्यावर LONG — "buy the dip at VWAP support")
  ७. SL: reversal candlestick (Gate 4 मध्ये सापडलेली) च्या low/high वरून (+ छोटा buffer) — बाजाराच्या
     प्रत्यक्ष संरचनेवर आधारित; candlestick gate बंद असेल आणि candle सापडली नसेल तरच VWAP-आधारित SL कडे
     मागे जाते. Target: किमान Risk:Reward सह

Required snapshot.futures_ohlcv columns:
  ['close','high','low','vwap']  (RSI आतल्या आत calculate_rsi ने आपोआप काढला जातो)
"""

from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType
from signals import detect_candlestick_pattern, calculate_rsi, find_reversal_candle_recent


class VWAPStrategy(StrategyBase):
    strategy_id = "vwap"
    default_weight = 1.0
    max_concurrent_positions = 2

    def __init__(self, config=None):
        super().__init__(config)
        # सद्य bar VWAP च्या किती % च्या आत असेल तर 'retracement झाली' मानायचं
        self.retracement_tolerance_pct = self.config.get("retracement_tolerance_pct", 0.1)
        # गेल्या किती bars मध्ये extension तपासायची
        self.extension_lookback = self.config.get("extension_lookback", 10)
        # त्या lookback मध्ये किमान किती % extension (VWAP पासून लांब जाणं) खरा trend मानण्यासाठी हवी
        self.min_extension_pct = self.config.get("min_extension_pct", 0.15)
        # SL साठी VWAP पासून किती % पलीकडे buffer
        self.sl_buffer_pct = self.config.get("sl_buffer_pct", 0.05)
        self.target_rr = self.config.get("target_rr", 1.5)
        # 🎓 नवीन कडक गेट्स — जास्त निवडक, कमी पण जास्त-विश्वासार्ह सिग्नल्ससाठी (डीफॉल्ट दोन्ही चालू)
        self.require_candlestick_confirmation = self.config.get("require_candlestick_confirmation", True)
        # candlestick pattern फक्त retracement bar वरच नाही, तर त्याआधीच्या इतक्या bars मध्येही शोधायचा
        # (Price Action strategy सारखंच — अगदी exact retracement bar वरच पॅटर्न असणं खूपच दुर्मिळ योगायोग
        # ठरतो, त्यामुळे किंचित मागचेही bars तपासले तर जास्त वाजवी संख्येने, तरीही निवडक सिग्नल्स मिळतात)
        self.pattern_lookback = self.config.get("pattern_lookback", 3)
        self.require_rsi_filter = self.config.get("require_rsi_filter", True)
        self.rsi_long_max = self.config.get("rsi_long_max", 65)
        self.rsi_short_min = self.config.get("rsi_short_min", 35)

    def required_data(self):
        return ["futures_ohlcv"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        ohlcv = snapshot.futures_ohlcv
        if ohlcv is None or len(ohlcv) < self.extension_lookback + 1:
            return self._no_signal("insufficient futures_ohlcv history")

        required_cols = {"close", "high", "low", "vwap"}
        if not required_cols.issubset(ohlcv.columns):
            return self._no_signal(f"missing columns: {required_cols - set(ohlcv.columns)}")

        last = ohlcv.iloc[-1]
        vwap = last["vwap"]
        if vwap != vwap or vwap == 0:  # NaN check शिवाय pandas import न करता
            return self._no_signal("VWAP unavailable for latest candle")

        # --- GATE 1: दिशा — 1H Supertrend वरून (snapshot.extra["trend_direction_1h"] मध्ये दिलेली असल्यास,
        # आपल्याच मुख्य A1 Engine शी सुसंगत राहण्यासाठी) — नसेल तर जुनी पद्धत (close vs vwap) कडे मागे जाणे. ---
        given_direction = (snapshot.extra or {}).get("trend_direction_1h")
        if given_direction in ("LONG", "SHORT"):
            direction = Direction.LONG if given_direction == "LONG" else Direction.SHORT
        else:
            direction = Direction.LONG if last["close"] > vwap else Direction.SHORT

        # --- GATE 2: Extension पुष्टीकरण — खरा trend होता का (नुसता VWAP जवळचा chop नाही) ---
        recent = ohlcv.iloc[-self.extension_lookback:]
        if direction == Direction.LONG:
            max_extension_pct = (recent["high"] - recent["vwap"]).max() / vwap * 100
        else:
            max_extension_pct = (recent["vwap"] - recent["low"]).max() / vwap * 100
        had_extension = max_extension_pct >= self.min_extension_pct
        if not had_extension:
            return self._no_signal(
                f"no real trend/extension from VWAP in last {self.extension_lookback} bars "
                f"(max_extension={max_extension_pct:.3f}%, need >= {self.min_extension_pct}%)"
            )

        # --- GATE 3: Retracement — सद्य bar VWAP जवळ आलाय का ---
        tolerance = vwap * (self.retracement_tolerance_pct / 100)
        if direction == Direction.LONG:
            near_vwap = last["low"] <= vwap + tolerance
        else:
            near_vwap = last["high"] >= vwap - tolerance
        if not near_vwap:
            return self._no_signal(f"price has not retraced back to VWAP yet (direction={direction.value})")

        # --- 🎓 GATE 4: Candlestick Confirmation (नवीन, सैल केलेलं) — retracement candle स्वतः, किंवा
        # त्याआधीच्या pattern_lookback bars पैकी कुठलाही, reversal pattern दाखवतो का. जी candle पॅटर्न
        # दाखवते, तिचाच low/high पुढे SL काढण्यासाठी वापरला जातो (VWAP ऐवजी — जास्त अचूक, बाजाराच्या
        # प्रत्यक्ष संरचनेवर आधारित SL). ---
        pattern = detect_candlestick_pattern(ohlcv)
        bullish_patterns = ("HAMMER", "BULLISH_ENGULFING", "MORNING_STAR")
        bearish_patterns = ("SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR")
        pattern_ok = (pattern in bullish_patterns) if direction == Direction.LONG else (pattern in bearish_patterns)
        reversal_candle_low = float(last["low"]) if pattern_ok else None
        reversal_candle_high = float(last["high"]) if pattern_ok else None
        if self.require_candlestick_confirmation and not pattern_ok:
            direction_str = "BULLISH" if direction == Direction.LONG else "BEARISH"
            recent = find_reversal_candle_recent(ohlcv, direction_str, lookback=self.pattern_lookback)
            if recent:
                pattern = recent["pattern"]
                pattern_ok = True
                reversal_candle_low = recent["low"]
                reversal_candle_high = recent["high"]
        if self.require_candlestick_confirmation and not pattern_ok:
            return self._no_signal(
                f"no reversal candlestick pattern at/near VWAP retracement (direction={direction.value}, "
                f"checked current + last {self.pattern_lookback} bars)"
            )

        # --- 🎓 GATE 5: RSI Filter (नवीन, कडक) — आधीच खूप overbought/oversold नसावं (थकलेली हालचाल टाळणे) ---
        rsi_value = None
        if self.require_rsi_filter:
            rsi_series = calculate_rsi(ohlcv, period=14)
            if rsi_series is not None and len(rsi_series) > 0 and rsi_series.iloc[-1] == rsi_series.iloc[-1]:  # NaN check
                rsi_value = float(rsi_series.iloc[-1])
                rsi_ok = (rsi_value <= self.rsi_long_max) if direction == Direction.LONG else (rsi_value >= self.rsi_short_min)
                if not rsi_ok:
                    return self._no_signal(
                        f"RSI already extended for a fresh {direction.value} entry (RSI={rsi_value:.1f})"
                    )

        # --- सर्व गेट्स पास — Entry/SL/Target काढणे ---
        # SL: reversal candle सापडली असेल तर तिचाच low/high (+ थोडा buffer) — बाजाराच्या प्रत्यक्ष
        # संरचनेवर (candle नुसार) आधारित, VWAP-आधारित buffer पेक्षा जास्त अचूक. candlestick gate बंद
        # असेल (require_candlestick_confirmation=False) आणि कुठलीही candle सापडली नसेल तरच जुनी
        # VWAP-आधारित पद्धत वापरली जाते (मागचं सुसंगत वर्तन राखण्यासाठी).
        entry = last["close"]
        sl_buffer_frac = self.sl_buffer_pct / 100
        if direction == Direction.LONG and reversal_candle_low is not None:
            sl = reversal_candle_low * (1 - sl_buffer_frac)
        elif direction == Direction.SHORT and reversal_candle_high is not None:
            sl = reversal_candle_high * (1 + sl_buffer_frac)
        else:
            sl_buffer = vwap * sl_buffer_frac
            sl = vwap - sl_buffer if direction == Direction.LONG else vwap + sl_buffer
        risk = abs(entry - sl)
        target = entry + risk * self.target_rr if direction == Direction.LONG else entry - risk * self.target_rr

        # Confidence: extension जितकी जास्त (खरा, ठाम trend), तितका आत्मविश्वास जास्त
        confidence = min(1.0, 0.5 + (max_extension_pct / self.min_extension_pct) * 0.1)

        return SignalResult(
            strategy_id=self.strategy_id,
            direction=direction,
            confidence=round(confidence, 3),
            instrument_type=InstrumentType.FUTURES,
            entry_price=round(entry, 2),
            stop_loss=round(sl, 2),
            target=round(target, 2),
            timestamp=snapshot.timestamp,
            reason=(
                f"VWAP trend+retracement ({direction.value}): extended {max_extension_pct:.2f}% from VWAP, "
                f"retraced near VWAP={vwap:.2f}, confirmed by {pattern or 'no-pattern-required'} "
                f"(SL from candle{'' if (reversal_candle_low is not None or reversal_candle_high is not None) else ' [fallback: VWAP]'})"
                + (f", RSI={rsi_value:.1f}" if rsi_value is not None else "")
            ),
            meta={
                "vwap": vwap, "max_extension_pct": max_extension_pct, "pattern": pattern, "rsi": rsi_value,
                "sl_source": "candle" if (reversal_candle_low is not None or reversal_candle_high is not None) else "vwap",
            },
        )

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id,
            direction=Direction.NONE,
            confidence=0.0,
            instrument_type=InstrumentType.FUTURES,
            reason=reason,
        )
