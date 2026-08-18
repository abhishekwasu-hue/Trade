"""
strategies/oi_pcr.py
---------------------
Strategy 4: Change-in-OI + PCR Breakout

Logic:
  - ATM +/- N strikes चा ΔOI (current OI - previous snapshot OI) बघायचं
  - Call unwinding (Call OI down) + Put buildup (Put OI up)  -> Bullish
  - Put unwinding (Put OI down) + Call buildup (Call OI up)  -> Bearish
  - PCR (Put/Call OI ratio) च्या shift नि दुजोरा (confirmation) द्यायचा
  - Instrument: OPTIONS (credit spread / iron condor selling साठी)

Data source: तुमचं local SQLite OI collector (options_chain snapshot)
Required columns in snapshot.options_chain (per cycle DataFrame):
  ['strike', 'option_type' ('CE'/'PE'), 'oi', 'oi_prev', 'ltp']
"""

from .base import StrategyBase, SignalResult, MarketSnapshot, Direction, InstrumentType


class OIPCRStrategy(StrategyBase):
    strategy_id = "oi_pcr"
    default_weight = 1.0
    max_concurrent_positions = 2

    def __init__(self, config=None):
        super().__init__(config)
        # किती ATM strikes (each side) विचारात घ्यायच्या
        self.atm_range = self.config.get("atm_range", 3)
        # ΔOI change चा minimum threshold (% मध्ये) — noise टाळण्यासाठी
        self.min_oi_change_pct = self.config.get("min_oi_change_pct", 5.0)
        # PCR shift threshold
        self.pcr_shift_threshold = self.config.get("pcr_shift_threshold", 0.05)

    def required_data(self):
        return ["options_chain"]

    def check_gates(self, snapshot: MarketSnapshot) -> SignalResult:
        chain = snapshot.options_chain
        if chain is None or len(chain) == 0:
            return self._no_signal("options_chain data missing")

        ce = chain[chain["option_type"] == "CE"]
        pe = chain[chain["option_type"] == "PE"]

        ce_oi_now, ce_oi_prev = ce["oi"].sum(), ce["oi_prev"].sum()
        pe_oi_now, pe_oi_prev = pe["oi"].sum(), pe["oi_prev"].sum()

        if ce_oi_prev == 0 or pe_oi_prev == 0:
            return self._no_signal("insufficient previous OI baseline")

        ce_change_pct = ((ce_oi_now - ce_oi_prev) / ce_oi_prev) * 100
        pe_change_pct = ((pe_oi_now - pe_oi_prev) / pe_oi_prev) * 100

        pcr_now = pe_oi_now / max(ce_oi_now, 1)
        pcr_prev = pe_oi_prev / max(ce_oi_prev, 1)
        pcr_shift = pcr_now - pcr_prev

        # --- GATE 1: OI change threshold cross झाला का ---
        gate1_ce = abs(ce_change_pct) >= self.min_oi_change_pct
        gate1_pe = abs(pe_change_pct) >= self.min_oi_change_pct
        if not (gate1_ce or gate1_pe):
            return self._no_signal(
                f"OI change below threshold (CE:{ce_change_pct:.1f}% PE:{pe_change_pct:.1f}%)"
            )

        # --- GATE 2: Direction determine करा ---
        bullish = ce_change_pct < 0 and pe_change_pct > 0     # call unwinding + put buildup
        bearish = pe_change_pct < 0 and ce_change_pct > 0     # put unwinding + call buildup

        # --- GATE 3: PCR shift confirmation ---
        pcr_confirms_bull = pcr_shift > self.pcr_shift_threshold
        pcr_confirms_bear = pcr_shift < -self.pcr_shift_threshold

        direction = Direction.NONE
        confidence = 0.0
        reason = ""

        if bullish and pcr_confirms_bull:
            direction = Direction.LONG
            confidence = min(1.0, (abs(ce_change_pct) + abs(pe_change_pct)) / 100)
            reason = f"Call unwinding({ce_change_pct:.1f}%) + Put buildup({pe_change_pct:.1f}%) + PCR shift up({pcr_shift:.3f})"
        elif bearish and pcr_confirms_bear:
            direction = Direction.SHORT
            confidence = min(1.0, (abs(ce_change_pct) + abs(pe_change_pct)) / 100)
            reason = f"Put unwinding({pe_change_pct:.1f}%) + Call buildup({ce_change_pct:.1f}%) + PCR shift down({pcr_shift:.3f})"
        else:
            return self._no_signal(
                f"OI moved but PCR didn't confirm (pcr_shift={pcr_shift:.3f})"
            )

        return SignalResult(
            strategy_id=self.strategy_id,
            direction=direction,
            confidence=round(confidence, 3),
            instrument_type=InstrumentType.OPTIONS,
            timestamp=snapshot.timestamp,
            reason=reason,
            meta={
                "ce_change_pct": ce_change_pct,
                "pe_change_pct": pe_change_pct,
                "pcr_now": pcr_now,
                "pcr_shift": pcr_shift,
            },
        )

    def _no_signal(self, reason: str) -> SignalResult:
        return SignalResult(
            strategy_id=self.strategy_id,
            direction=Direction.NONE,
            confidence=0.0,
            instrument_type=InstrumentType.OPTIONS,
            reason=reason,
        )
