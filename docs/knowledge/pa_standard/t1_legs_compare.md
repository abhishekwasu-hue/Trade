# T1 — Impulse vs correction legs, by comparison (PA standard §2B)

Module: `decision3/legs_compare.py`. Status: **evidence only** — no entry, no block, no wave-count prediction.

## Definition (the method's words)

- **Impulse leg**: larger bodies, little overlap, expanding volume — **compared with its neighbouring legs**.
- **Correction leg**: overlapping candles, smaller bodies, lower volume — compared with its neighbouring legs.
- **Correction forms**: zigzag (ABC), flat, triangle, channel — shown as evidence of what the swings show so far; never a
  forecast of the next leg and never a wave count.

## How it reads a leg

A leg = the bars from one swing to the next of the timeframe's external degree (`mtf_state.swings`: W / D / 1H / 15M / 5M), bars
(start swing, end swing], on that timeframe's own candles:

| Measure | What it is |
|---|---|
| body | the average candle body \|close − open\| per bar |
| overlap | the average share of each candle's range that overlaps the previous candle (overlap ÷ the pair's high–low) |
| volume | the average FUT volume per bar (method §3: averages per bar, never sums); NA when any bar of the leg has no volume |

Comparison: on each measure the leg is impulse-like when it is beyond **every** neighbouring leg (larger bodies / less overlap /
higher volume), correction-like when it is short of every neighbour, "between" otherwise. Neighbours = the adjacent legs on
either side known at `t` (the leg after it may still be running — read so far). Verdict = the side most of the measures take
(a strict majority of the measures that could be read); all agree ⇒ "clear"; no majority ⇒ "mixed"; nothing to compare ⇒ NA.
The legs2 percentile settings (c_hi / c_lo / baseline_legs) are **not** used.

## Correction form (comparison only)

From the counter-move's own swings: start = the trend-direction extreme, then the internal swings inside it, then the running
extreme so far.

| Form | Swings show |
|---|---|
| one leg (A) | only the first counter leg so far |
| A–B | two legs; B short of A's start, or B back to A's start |
| zigzag (ABC) | three legs; B stays short of A's start, C goes beyond A's end |
| flat | three legs; B comes back to A's start — reaches the start swing candle's area, wick to body (C-13) — or beyond |
| triangle (contracting) | four or more legs; the highs keep falling and the lows keep rising |
| triangle (expanding) | four or more legs; each swing beyond the previous one on both sides |
| channel | four or more legs stepping in the counter direction on both sides |
| complex | none of the above |

Two forms are given per timeframe: the **running** correction (when the timeframe's state is "correction in progress") and the
**last completed** counter leg.

## Evidence wording

- `15M running down leg: correction (smaller bodies, overlapping candles, lower volume — vs 1 neighbouring leg)`
- `1H last up leg: impulse (larger bodies, little overlap, volume NA (no volume for this timeframe) — vs 2 neighbouring legs)`
- `15M correction so far: zigzag (ABC) (three legs, B short of A's start, C beyond A's end)`

## API

```python
from decision3 import legs_compare as LC
lg = LC.read_legs_compare(V, t, d=None)       # {t, tfs: {tf: {state, degree, internal_degree, legs, correction,
                                               #                 last_correction, volume}}, evidence_only}
LC.leg_facts(F, i0, i1, dirn)                  # measures of one leg on frame F
LC.compare(leg, neighbours)                    # {verdict, clear, measures, why}
LC.correction_form(points, dirn, start_edge)   # {form, why, legs, dir}
LC.evidence(lg); LC.draw_objects(V, t)         # [{kind: leg | correction_form, tf, t0, t1, p0, p1, label, state, evidence}]
```

## Numbers and settings

No new setting and no number in the reading: every decision is "larger / smaller than each neighbour" or "beyond / short of a
swing". A "strict majority of the measures read" is counting, not a tuned threshold.

## What it is NOT

- Not a gate or grade by itself. The Daily reading can use the same comparison through `daily_leg_read = compare`
  (see t1_daily_leg_read.md; default stays `elliott` until Abhi's ✅).
- Not an Elliott count: forms are named from the swings so far; no projection, no ratios (no Fibonacci here).

## Known gaps (honest)

- Daily / Weekly / 5M legs have no volume (spot data; FUT volume exists only on the 15M / 1H path) ⇒ body + overlap only.
- A running leg is compared with its one completed neighbour only.
- Correction forms need the internal swings; when the internal degree shows no swing inside the counter-move the form stays
  "one leg (A)".
