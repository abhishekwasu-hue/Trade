# PA standard §2F — confluence levels (track T2)

Module: `decision3/confluence_pa.py`. Evidence only. The existing `levels.confluence_label` (1H band ∩ Daily / Weekly bands) is
unchanged; this module lists the further pieces beside it.

## F.1 HTF horizontal levels from earlier swing extremes

**Definition.** The higher timeframes' earlier swing extremes, exactly as the engine builds them: births a:D / a:D-prior / a:W-prior,
each its own Daily / Weekly band (Abhi Z-1u), plus the Daily swing extremes still resting (§2D). `htf_levels(V, t)` only reads them.
**Not.** Not a re-build of levels and not a location rule (a Daily band is a location only where no 1H zone overlaps it — that stays in
`levels.snapshot`).

## F.2 Imbalances (fair value gaps) left by impulses

**Definition.** Three candles where the third does not trade back to the first: bullish = low of candle 3 above the high of candle 1
with a bullish middle candle (gap = high₁ … low₃); bearish = the mirror. Read on the 15M bars ≤ t and on the 1H candles completed by
t. "Left by an impulse" facts: `middle_largest` (the middle body is larger than both neighbours') and, on 15M, `leg_broke_structure`
(the finest-degree leg holding it closed beyond the last confirmed D2 swing).
**States** (from the later bars only): `open` (no later bar traded into it), `partly` (traded into it but not through it —
`remaining` = the untraded part), `filled` (a later bar traded through it — `filled_at`). The reads list open / partly ones.
**Evidence wording.** `imbalance 15M bearish open 23,846–23,898`.
**Not.** Not an entry (KB: FVG entries rejected) — only a confluence piece where it overlaps an area, and a departure fact (§2C.5).

## F.3 Fibonacci retracement — ONLY as confluence (Abhi's rule, KB K7)

**Definition.** The last impulse that broke structure: the newest D2 BOS, from its origin swing to the extreme confirmed swing after
it (both confirmed pivots). Its retracement levels (`pa_fib_ratios` = 38.2 / 50 / 61.8 / 78.6 %, the declared exception — the ratios
are the tool's definition) are reported **only** where a level lands inside an alive area's band (a trade location of `levels.snapshot`: not BROKEN /
DEAD, not a Weekly context band, not a Daily band under a 1H zone) or inside a resting
liquidity extreme's own swing-candle band (wick-to-body, `levels._band_swing`).
**No Fib at all** when nothing is there ("Fib is never read alone"), when the impulse's end swing is not confirmed yet, when price has
made a new extreme beyond it since, or when price has gone back beyond its origin (retracement beyond 100 %).
**Evidence wording.** `Fib 61.8% 23,410 of the last impulse` inside the area's confluence label.
**Not.** Never alone, never a gate, never a score. No ± band around the level (the area / liquidity band is the band).

## F.4 Confluence = several of these at one place

Per area (alive, not DEAD) one list `pieces` of what sits at the same place — HTF band overlap (from `levels.snapshot`), imbalance
overlapping the band, Fib level landing in it, resting liquidity inside it (not the area's own anchor swing) — and `label` =
"confluence: …". One list, no score, no count gate.

## API

- `read_confluence(V, t, d=None)` → `{"htf_levels", "fvg", "fib", "areas"}`.
- `scan_fvgs(F, i_from, i_to)` (any `pa_frames.Frame`), `fvgs(V, t, include_filled=False)`, `fib_on_areas(V, t, snap=None,
  obvious=None)`, `htf_levels(V, t)`.
- `draw_objects(V, t, read=None)` → `fvg`, `fib_level`, `htf_level` objects (T8 schema).

## Setting added (declared exception)

| key | default | class | why |
|---|---|---|---|
| `pa_fib_ratios` | (0.382, 0.5, 0.618, 0.786) | व्याख्या (definition) | Abhi rule K7: Fib only as a confluence label on an area / liquidity — the ratios are the tool itself; nothing decides on them |

For NUMBERS_INVENTORY (the coordinator integrates): "pa_fib_ratios — Abhi rule K7, confluence label only, declared exception".
No look-ahead: bars ≤ t, swings confirmed by t.
