"""vision_led/situation_map.py — KB भाग I (बाजारातल्या परिस्थितींचा नकाशा, Abhi G-MAP1 2026-10-09) चा English सारांश, vision playbooks
साठी (मजकूर फक्त, images नाहीत; ~1k tokens, system prompt मध्ये cached). पूर्ण नकाशा: docs/knowledge/KNOWLEDGE_BASE.md भाग I."""

MAP_TEXT = """SITUATION MAP (KB Part I, approved). Name the situation BEFORE judging the setup.
Principles: P1 degree first: trade only in the PARENT direction (the motive sequence the traded correction belongs to); the grandparent
degree (Daily/Weekly) is evidence only. Exceptions: S4 flip retest, G7 exhaustion gap, G10 range edge. P2 always keep a primary AND an
alternate count, each with invalidation and confirmation; an alternate is not gray. P3 a strong counter-move's meaning comes from the
REACTION after it. P4 measure relative to the impulse being corrected; depth is evidence, displacement weak evidence, overlap/legs
notes only; real break of the impulse ORIGIN (start) => not a pullback. P5 each situation has its own area, and the area must exist
at the decision bar. P6 closed commitment candle only. P9 money/sentiment (FII, VIX, macro) is context, not a rule.
Situations: S1 normal 3-wave overlapping pullback -> trade C-end at area. S2 deep 61.8-80% valid, 80-100% weak (needs area + sweep).
S3 strong counter-move that REAL-breaks the last confirmed 1H LH/HL inside the impulse (origin intact) -> GRAY-1, wait for the reaction:
corrective reaction that does not reclaim the broken area then commitment in the counter-move direction = new trend (trade the reaction
end); impulsive reaction that real-breaks the counter-move start = old trend. S4 real break of the impulse origin (testing) -> only the
flip retest in the break direction; MAGNET (closes chopping around the level) = no setup. S5 shallow 2-6 candle flag in a strong trend
(G8) -> flag edge / broken swing / displacement base; 1 candle is not a flag. S6 sideways triangle/flat -> only E-end/C-end, never
inside B/D/X. S7 expanded flat / spring: sweep beyond A then reclaim -> enter after the reclaim close. S8 trend tiring (smaller
with-trend legs, bigger pullbacks, divergence) -> lower confidence, no fade. S9 range (trade degree RANGE) -> G10 at the edges only
(lower edge bull put, upper edge bear call; with a parent trend only the trend-side edge); never mid-range. S10 gap day: decide by
acceptance/rejection in the first 2-6 bars. S11 inside a B wave -> no trade. S12 first 30 min weak, event/VIX spikes, no pullback yet =
no setup, a 15:15 signal is re-read next day (no automatic entry).
GRAY: Gray-1 = parent direction not settled by structure (S3 reaction open, S4 testing unresolved). Gray-2 = correction end not
decidable at the commitment bar (zigzag/flat needs A, B and a C reaching A's extreme; triangle 5 legs; flag = G8 structure; a 5-wave
counter-move is only A). Never trade gray unless Abhi's daily policy says reduce (Gray-1 also needs his direction). Mid-range is not
gray - there is simply no area. If the situation is unclear, say which two counts compete and what would decide between them.
"""
