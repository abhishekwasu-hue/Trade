"""
strategies/mtf_gap_fill.py
------------------------------
Strategy 6: MTF Gap Fill (Unfilled Overnight Gap → Full Fill → Instant Entry)

🎓 वापरकर्त्याशी चर्चा करून बांधलेली रणनीती (mtf_pullback_strategy.py चं established, बग-दुरुस्त
core logic इथेच पुनर्वापर केलं आहे — दोन ठिकाणी वेगळा कोड नाही):
  १. 1H (Higher Timeframe) वर confirmed swings शोधून, त्या trend च्या दिशेशी जुळणारा खरा overnight
     gap (मागच्या दिवसाचा शेवटचा 15M close ते पुढच्या दिवसाचा market open, किमान min_gap_pct%) शोधणे.
  २. तो gap अजून "उघडा" (unfilled) आहे का, आणि 15M वरच्या **सद्य (शेवटच्या) candle** ने तो आत्ताच
     **पूर्णपणे भरला** (मूळ किनाऱ्यापर्यंत पोहोचला) का — हे या cycle मध्ये तपासणे.
  ३. पूर्ण भरला गेला असेल, तरच entry — कुठलीही candle-pattern/RSI पुष्टी लागत नाही (वापरकर्त्याने
     स्पष्ट सांगितल्याप्रमाणे).

Required snapshot.futures_ohlcv: 15M (किंवा मुख्य timeframe) candles.
Required snapshot.extra["mtf_1h_ohlcv"]: 1H OHLCV DataFrame (Date/Open/High/Low/Close स्तंभ) —
sr_bounce strategy च्या "sr_levels_1h" सारखंच, orchestrator/backtest कडून बाहेरून दिलं जातं.
"""
from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType
from mtf_pullback_strategy import pivots, find_overnight_gaps


class MTFGapFillStrategy(StrategyBase):
    strategy_id = "mtf_gap_fill"
    default_weight = 1.0
    max_concurrent_positions = 1

    def __init__(self, config=None):
        super().__init__(config)
        self.min_swing_pct = self.config.get("min_swing_pct", 1.0)
        self.min_gap_pct = self.config.get("min_gap_pct", 0.30)
        self.sl_pct = self.config.get("sl_pct", 0.25)
        self.target_pct = self.config.get("target_pct", 0.70)

    def required_data(self):
        return ["futures_ohlcv"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        m15 = snapshot.futures_ohlcv
        if m15 is None or len(m15) < 2:
            return self._no_signal("अपुरा 15M इतिहास")

        h1 = (snapshot.extra or {}).get("mtf_1h_ohlcv")
        if h1 is None or len(h1) < 10:
            return self._no_signal("1H OHLCV (snapshot.extra['mtf_1h_ohlcv']) उपलब्ध नाही")

        # स्तंभ-नावं Date/Open/High/Low/Close अपेक्षित (mtf_pullback_strategy established convention)
        h1_std = self._standardize(h1)
        m15_std = self._standardize(m15)

        ps = pivots(h1_std, min_swing_pct=self.min_swing_pct)
        if len(ps) < 2:
            return self._no_signal("पुरेसे 1H swings सापडले नाहीत")

        legs = []
        for a, b in zip(ps[:-1], ps[1:]):
            if a["type"] == "SL" and b["type"] == "SH":
                legs.append(("LONG", a, b))
            elif a["type"] == "SH" and b["type"] == "SL":
                legs.append(("SHORT", a, b))
        if not legs:
            return self._no_signal("सद्य 1H trend मध्ये कुठलाही स्पष्ट leg नाही")

        all_gaps = find_overnight_gaps(m15_std, self.min_gap_pct)
        last = m15_std.iloc[-1]

        # 🎓 फक्त सद्य (शेवटच्या) candle नेच gap आत्ता "पूर्ण भरला" का — इथेच तपासणे (live/per-cycle),
        # मागच्या cycles मध्ये आधीच भरला गेलेला gap पुन्हा वापरला जाऊ नये.
        direction, entry_price, matched_leg = None, None, None
        for leg_dir, a, b in legs:
            leg_start = h1_std.iloc[a["idx"]]["Date"]; leg_end = h1_std.iloc[b["idx"]]["Date"]
            wanted_kind = "UP_GAP" if leg_dir == "LONG" else "DOWN_GAP"
            for g in all_gaps:
                if g["kind"] != wanted_kind or not (leg_start <= g["gap_time"] <= leg_end): continue
                if g["gap_time"] >= last["Date"]: continue  # gap स्वतःच सद्य candle च्या आधीच तयार झालेला असावा
                fully_filled = (last.Low <= g["gap_low"]) if leg_dir == "LONG" else (last.High >= g["gap_high"])
                if not fully_filled: continue
                direction = leg_dir
                entry_price = g["gap_low"] if leg_dir == "LONG" else g["gap_high"]
                matched_leg = (a, b)
                break
            if direction:
                break

        if not direction:
            return self._no_signal("सद्य candle ने कुठलाही उघडा gap पूर्ण भरलेला नाही")

        sl_distance = entry_price * (self.sl_pct / 100)
        target_distance = entry_price * (self.target_pct / 100)
        if direction == "LONG":
            sl = entry_price - sl_distance; target = entry_price + target_distance
        else:
            sl = entry_price + sl_distance; target = entry_price - target_distance

        return SignalResult(
            strategy_id=self.strategy_id,
            direction=Direction.LONG if direction == "LONG" else Direction.SHORT,
            confidence=0.65, instrument_type=InstrumentType.FUTURES,
            entry_price=round(float(entry_price), 2), stop_loss=round(float(sl), 2), target=round(float(target), 2),
            timestamp=snapshot.timestamp,
            reason=f"Overnight Gap पूर्ण भरला (Instant, पुष्टीशिवाय) — {direction} trend leg",
            meta={"leg_start": matched_leg[0]["price"], "leg_end": matched_leg[1]["price"]},
        )

    @staticmethod
    def _standardize(df):
        """स्तंभ-नावं Date/Open/High/Low/Close मध्ये आणणे (Dashboard/backtest दोन्ही स्तंभ-रचना स्वीकारण्यासाठी)."""
        rename_map = {}
        for c in df.columns:
            k = c.strip().lower()
            if k in ("date", "timestamp", "datetime", "time"): rename_map[c] = "Date"
            elif k == "open": rename_map[c] = "Open"
            elif k == "high": rename_map[c] = "High"
            elif k == "low": rename_map[c] = "Low"
            elif k == "close": rename_map[c] = "Close"
        return df.rename(columns=rename_map).reset_index(drop=True)

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id, direction=Direction.NONE, confidence=0.0,
            instrument_type=InstrumentType.FUTURES, reason=reason,
        )
