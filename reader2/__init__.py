"""reader2 — Chart Reader v2 (research-only, spec TRADE_SESSION_CHART_READER_V2): candles trader सारखे वाचा, मग स्वतःची marking तपासा.

प्रत्येक leg ला दोन स्वतंत्र votes — structure (decision3.daily_legs.read_counter / patterns2) आणि anatomy (legs2 candle features,
MR units) — fusion ⇒ impulse / correction / uncertain, confidence, evidence; नंतर self-check (invariants 1–7, कमाल 3 passes, relabel log).
Gallery gate (§5) पास होऊन Abhi ने मंजुरी देईपर्यंत कोणताही bot / decision3 gate / vision हे वापरत नाही. Design: docs/READER2_DESIGN.md.
"""
