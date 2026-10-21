# T5 — Volume reads (PA standard §2I)

Code: `decision3/volume_read.py` · tests: `tests/test_pa_volume_read.py` · check: `scripts/pa_candles_volume_check.py`

## Definition (the method's words)

Volume is the **near-month FUT** volume for indices (the engine's raw per-bar FUT volume: `legs2.volume.bar_volume`). Every read
is a **comparison** — between legs, or between a candle and its neighbours — using **per-bar averages**, never sums and never a
time-of-day baseline. A bar without FUT volume never counts as zero: it is left out and reported (`gaps`). No FUT volume ⇒ NA.

Legs come from the swings of one swings2 degree (default `tl_degree`, the pullback degree D1) **confirmed by bar t**.

| Read | Reading | States |
|---|---|---|
| Pullback vs impulse | the pullback (the current leg, or the approach leg into an area visit — the engine's structure visit) vs the leg it pulls back from | `lower` / `higher` / `equal` / `beyond` (went past the impulse's start ⇒ no pullback) / `na` |
| Climax | the leg's largest-volume candle is a large candle (range above the leg's earlier candles' average — `method.candle_read` big_range), the leg's extreme is on it, and no later candle goes beyond it (no progress). Read on the completed leg (the climax that ended it) and the current leg | `found` / `forming` (on the last candle, progress unknown) / `none` / `na` |
| Effort vs result | effort = per-bar volume, result = progress per bar; the current leg vs the previous leg in the same direction. Also candle t vs the leg's earlier candles | `effort without result` / `result with ease` / `in harmony`; candle: `effort without result (candle)` |
| Absorption | the existing reader, unchanged: `method.zone_study(..)["absorption"]` over the current visit (`V.visit`), plus the volume wording (the opposite side's per-candle volume in the later part vs the earlier part and vs the trade side) | `absorbing` / `not absorbing` / `na` |
| Commitment volume | the existing definition, unchanged: `method.commitment(..)` (`commit_volume_rule`: approach leg + the visit's opposite-side candles) | `above` / `not_above` / `no_commitment` / `na` |

## Evidence wording

- *"pullback on lower volume than the impulse up (per-bar average 8,120 vs 12,400)"*
- *"selling climax ended the leg down (its largest-volume, large candle made the extreme; nothing went beyond it)"*
- *"leg up: effort without result — more volume per bar than the previous leg up, less progress per bar"*
- *"absorption at the supply: buyers keep coming in small candles and price does not move away; buyers' volume per candle keeps coming (…)"*

## API

`read_volume(V, t, d=None, area=None, degree=None)` → all reads (area ⇒ the pullback is the approach into that visit, plus
absorption and commitment volume there). Single reads: `pullback_vs_impulse(A, swings, t, start=None, start_kind=None)`,
`climax(A, swings, t)`, `effort_result(A, swings, t)`, `absorption(V, t, area)`, `commitment_volume(V, t, area)`;
`swings(pivots, t)`; `draw_objects(read)` → `volume_leg` / `volume_climax` / `effort_result` / `absorption` objects.

No settings were added. No look-ahead: bars ≤ t and swings with confirm_bar ≤ t (tested by truncation).

## What it is NOT

- Not a gate and not a trigger: evidence only. Absorption and the commitment volume keep their existing decision role inside the
  engine; this module only reports them.
- No fixed multiplier ("2× volume") and no percentile: only larger / smaller than the neighbouring leg or candles.
- Not a spot-volume read (spot index volume is NA).
