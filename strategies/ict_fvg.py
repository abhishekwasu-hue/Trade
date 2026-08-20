"""
strategies/ict_fvg.py
-----------------------
Strategy 5: ICT / Smart Money — Liquidity Sweep + Fair Value Gap (FVG) Entry

Data source: NIFTY 50 FUTURES (candles) — options chain नाही
Logic:
  1. Swing high/low liquidity sweep ओळखा (wick sweep + close back inside range)
  2. Sweep नंतर BOS/CHoCH confirmation (तुमचं existing market structure engine वापरा)
  3. Sweep नंतर तयार झालेल्या Fair Value Gap (3-candle imbalance) मध्ये price
     retrace झाल्यावर entry
  4. Instrument: FUTURES (किंवा signal वरून ATM option विकत घ्यायचं / विकायचं ठरवा)

Required snapshot.structure_data keys (तुमच्या market structure engine मधून यायला हवं):
  {
    "swept_high": bool, "swept_low": bool,
    "bos_confirmed": bool, "choch_confirmed": bool,
    "bos_direction": "LONG"/"SHORT",
    "fvg_zones": [ {"start": float, "end": float, "direction": "LONG"/"SHORT", "candle_idx": int}, ... ]
  }
Required snapshot.futures_ohlcv: DataFrame with ['open','high','low','close','volume'] latest candle = last row
"""

from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType


class ICTFVGStrategy(StrategyBase):
    strategy_id = "ict_fvg"
    default_weight = 1.2
    max_concurrent_positions = 1

    def __init__(self, config=None):
        super().__init__(config)
        # FVG zone मध्ये price किती % आत शिरली पाहिजे entry trigger साठी
        self.fvg_entry_buffer_pct = self.config.get("fvg_entry_buffer_pct", 0.1)
        self.require_choch = self.config.get("require_choch", False)  # BOS पुरेसं की CHoCH पण हवं
        # 🎓 नवीन गेट: FVG zone किती जुना (bars मध्ये) असेल तर अजूनही वैध मानायचा — खूप जुना (stale) FVG
        # वर आता trading करणं संधी नसून जुना इतिहास असू शकतो
        self.max_fvg_age_bars = self.config.get("max_fvg_age_bars", 20)

    def required_data(self):
        return ["futures_ohlcv", "structure_data"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        struct = snapshot.structure_data
        ohlcv = snapshot.futures_ohlcv

        if struct is None or ohlcv is None or len(ohlcv) == 0:
            return self._no_signal("structure_data / futures_ohlcv missing")

        last_close = ohlcv.iloc[-1]["close"]

        bos_direction = struct.get("bos_direction")
        if bos_direction not in ("LONG", "SHORT"):
            return self._no_signal("bos_direction unavailable")

        # --- GATE 1 (दुरुस्त): Liquidity sweep ची दिशाच bos_direction शी जुळायला हवी — आधी फक्त
        # "कुठलाही sweep झाला का" (swept_high OR swept_low) तपासलं जायचं, त्यामुळे विरुद्ध दिशेचा sweep
        # (उदा. Bearish swept_high) चुकीने LONG entry ला support द्यायचा. आता: LONG साठी swept_low
        # (bullish sweep) हवाच, SHORT साठी swept_high (bearish sweep) हवाच. ---
        if bos_direction == "LONG":
            sweep_aligned = struct.get("swept_low", False)
        else:
            sweep_aligned = struct.get("swept_high", False)
        if not sweep_aligned:
            return self._no_signal(
                f"no liquidity sweep matching direction={bos_direction} "
                f"(dir-specific sweep required — swept_low for LONG, swept_high for SHORT)"
            )

        # --- GATE 2: BOS (आणि optionally CHoCH) confirmation ---
        bos_ok = struct.get("bos_confirmed", False)
        choch_ok = struct.get("choch_confirmed", False)
        if self.require_choch and not choch_ok:
            return self._no_signal("CHoCH not confirmed (required by config)")
        if not bos_ok and not choch_ok:
            return self._no_signal("neither BOS nor CHoCH confirmed after sweep")

        # --- GATE 3: FVG zone मध्ये price आली का, आणि 🎓 तो zone अजूनही ताजा (stale नाही) आहे का ---
        current_idx = len(ohlcv) - 1
        fvg_zones = struct.get("fvg_zones", [])
        matching_zone = None
        for zone in fvg_zones:
            if zone["direction"] != bos_direction:
                continue
            zone_idx = zone.get("candle_idx")
            if zone_idx is not None and (current_idx - zone_idx) > self.max_fvg_age_bars:
                continue  # खूप जुना (stale) FVG — वगळणे
            lo, hi = min(zone["start"], zone["end"]), max(zone["start"], zone["end"])
            buffer = (hi - lo) * self.fvg_entry_buffer_pct
            if (lo - buffer) <= last_close <= (hi + buffer):
                matching_zone = zone
                break

        if matching_zone is None:
            return self._no_signal(f"price not in any (fresh, <={self.max_fvg_age_bars} bars old) matching FVG zone (dir={bos_direction})")

        # --- सगळे gates pass ---
        direction = Direction.LONG if bos_direction == "LONG" else Direction.SHORT
        # confidence: sweep + BOS + CHoCH सगळं मिळालं तर जास्त
        confidence = 0.6 + (0.2 if bos_ok else 0) + (0.2 if choch_ok else 0)

        zone_lo, zone_hi = min(matching_zone["start"], matching_zone["end"]), max(matching_zone["start"], matching_zone["end"])
        sl = zone_lo - (zone_hi - zone_lo) if direction == Direction.LONG else zone_hi + (zone_hi - zone_lo)
        target_rr = self.config.get("target_rr", 2.0)
        risk = abs(last_close - sl)
        target = last_close + risk * target_rr if direction == Direction.LONG else last_close - risk * target_rr

        return SignalResult(
            strategy_id=self.strategy_id,
            direction=direction,
            confidence=round(min(confidence, 1.0), 3),
            instrument_type=InstrumentType.FUTURES,
            entry_price=last_close,
            stop_loss=round(sl, 2),
            target=round(target, 2),
            timestamp=snapshot.timestamp,
            reason=f"Liquidity sweep + BOS({bos_ok})/CHoCH({choch_ok}) + FVG entry @ {matching_zone}",
            meta={"fvg_zone": matching_zone},
        )

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id,
            direction=Direction.NONE,
            confidence=0.0,
            instrument_type=InstrumentType.FUTURES,
            reason=reason,
        )
