# Elliott Wave rules and guidelines used by the structure engine

Source: A. J. Frost & R. R. Prechter, *Elliott Wave Principle: Key to Market Behavior* (New Classics Library; 1st ed. 1978,
10th ed. 2005), Chapter 1 ("The Broad Concept" — wave forms and their rules) and Chapter 2 ("Guidelines of Wave Formation"). Wording below is a paraphrase; the
book is the authority. **Rules** are absolute (a count that breaks one is wrong). **Guidelines** describe what is typical and
are never used as decision thresholds in this repo — ratios such as 0.618 / 1.618 appear only in the test fixtures
(`tests/elliott_fixtures.py`) to build typical shapes (Abhi: TRADE_SESSION_CORRECTION_FIXTURES §5).

## Motive waves

**Impulse (5-3-5-3-5)** — rules:
1. Wave 2 never retraces more than 100% of wave 1.
2. Wave 3 is never the shortest of waves 1, 3 and 5.
3. Wave 4 never enters the price territory of wave 1 (no overlap), except in diagonals.

Guidelines: one of waves 1, 3, 5 is usually *extended* (most often 3, in some markets 5); *alternation* between 2 and 4
(sharp vs sideways); wave 4 often ends near the territory of the previous fourth wave of one lesser degree; equality of 1 and 5
when 3 extends; channelling.

**Diagonals** (wedge shaped; wave 4 overlaps wave 1):
- *Leading diagonal* — only in wave 1 or wave A position; subdivides 5-3-5-3-5.
- *Ending diagonal* — only in wave 5 or wave C position; subdivides 3-3-3-3-3.
- Wave 3 still not the shortest; converging (contracting) is typical.

A lone 5-wave counter-move is *not* proof of a new trend: wave A of a zigzag is also five waves (wave A vs wave 1 is resolved only
by what follows). The negative controls are complete impulses of the **same degree** as the prior impulse — each motive wave
itself subdivides into five, wave 4 clear of wave 1 — and those must flip the trend (without a close beyond the prior origin). How
the engine measures "same degree" is open (OPEN_QUESTIONS Q49).

## Corrective waves

Corrections never subdivide into five waves as a whole; the trend of one larger degree resumes after them.

**Zigzag (5-3-5)** — A is 5 waves, B is 3 waves and retraces part of A (B never goes beyond A's start), C is 5 waves and almost
always moves beyond the end of A. Variants: C = A (typical), C extended (≈ 1.618 × A — shape only), C short of A's end (Abhi's
"truncated" fixture; in F&P "truncation" strictly means a fifth wave failing to pass the third). Double / triple zigzag: W-X-Y(-X-Z)
joined by X waves — the engine labels multi-pattern corrections "combination".

**Flat (3-3-5)** — A is 3 waves, B is 3 waves and retraces (nearly) all of A, C is 5 waves.
- *Regular* — B ends near A's start, C ends near A's end.
- *Expanded* — B goes beyond A's start (for a correction of a DOWN impulse: B makes a new low below the impulse end), C ends
  well beyond A's end (typically ≈ 1.618 × A — shape only). The most common flat.
- *Running* — B goes beyond A's start, C fails to reach A's end (rare).

**Triangle (3-3-3-3-3, waves a-b-c-d-e)** — sideways; occurs only in the wave 4, B, X or (last) Y / Z position.
- *Contracting* (incl. ascending / descending), *barrier* (b and d end at about the same level), *expanding* (reverse
  symmetrical; rare).
- A triangle can be the B wave of a zigzag.

**Combinations (double three W-X-Y, triple three W-X-Y-X-Z)** — sideways combinations of simpler corrections (zigzag, flat,
triangle) joined by X waves; at most one triangle and, if present, in the last position.

Guidelines: alternation between 2 and 4; depth (corrections of a fourth wave usually end near the prior fourth wave of lesser
degree); a correction can be longer in time than the impulse it corrects; a very deep correction (> 80%) is still a correction
while the impulse origin holds.

## How the repo uses them (decision3 Daily structure)

| Rule / guideline | Use |
|---|---|
| Corrections are 3-wave (or combinations of 3-wave patterns) | counter-move classified **as a whole**; a 3-wave counter-move never flips the trend, even if C goes beyond A or B makes a new extreme (Abhi ABC_FIX rule 1) |
| Impulse rules 1–3, diagonal overlap exception | a counter-move flips the trend only if it is itself a valid 5-wave impulse / diagonal, or on a close beyond the prior impulse's origin |
| Zigzag / flat / triangle / combination definitions | family labels on the correction boxes (patterns2 adapter) |
| Fibonacci ratios | fixtures only — never decision thresholds |

Every Daily / 1H structure PR runs `tests/test_elliott_correction_library.py` (both directions, negative controls, Abhi's
NIFTY and BANKNIFTY acceptance shapes); a failure blocks merge. Known engine gaps are listed there as strict xfails.
