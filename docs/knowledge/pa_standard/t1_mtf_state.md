# T1 — Multi-timeframe market state and market structure (PA standard §1, §2A)

Module: `decision3/mtf_state.py`. Status: **evidence / state only** — it never enters, blocks or grades a trade. Track T9 wires
its output into the evidence list; track T8 draws its objects.

## Definition (the method's words)

- **Market state per timeframe**, one vocabulary for Weekly, Daily, 1H, 15M and 5M:
  **trending up / trending down / range / correction in progress**. When the swings do not give one of these (too little
  data, or no trend structure yet) the state is **unclear** — the reader says so instead of guessing.
- **Weekly** = the overall market state, **Daily** = the trade side, **1H** = the areas and main lines, **15M** = the setup,
  **5M** = the trigger.
- **Agreement**: which timeframes agree with the Daily side, which are in correction, which are against.
- **External structure** = the timeframe's own (higher-degree) swings. **Internal structure** = the next lower degree's swings
  inside the current external leg.
- **HH / HL / LH / LL** label each swing against the previous swing of the same kind (EQH / EQL when the reader's "equal"
  flag is set).
- **BOS** (break of structure, continuation) = a close beyond the last trend-direction swing. **CHoCH** (change of
  character) = a close beyond the swing that protects the trend (the last counter swing before the trend extreme).

## Where each timeframe is read from (existing readers, no new swing detector)

| TF | Swings / state | BOS / CHoCH |
|---|---|---|
| W | `daily.fold_impulse` on Weekly candles (V.weekly), `daily.state_at` | the same close comparison (`dow_events`) on the Weekly swings |
| D | `daily.fold_impulse` (V.daily): trend + phase + counter | `dow_events` on the Daily trend-degree swings |
| 1H | swings2 degree `level_degree` (D2 — the 1H trend degree the areas are born from) + `swings2.structure.fold` | swings2 events (15M close) |
| 15M | swings2 degree `tl_degree` (D1 — the pullback's legs) + `swings2.structure.fold` | swings2 events (15M close) |
| 5M | LTF bars (V.ltf); the LTF swing of `method.ltf_choch` (a high above its left neighbour, not below its right one), alternated | `dow_events` on 5M closes |

Internal degree: 1H → D1 inside the D2 leg · 15M → D0 inside the D1 leg · D → the N − 1 Daily swings inside the Daily leg ·
W → the Daily swings inside the Weekly leg · 5M → none.

## States (comparison only)

- **range** — the reader's own RANGE: the Daily / Weekly RANGE band, or swings2 RANGE (Rhea band, or HH + LL / equal swings).
- **trending up** — UP structure and the impulse leg is running: the newest confirmed swing is the higher low, or price has
  closed above the last high (BOS) since it.
- **correction in progress** — UP structure and either (a) the newest confirmed swing is the high and no close beyond it yet
  (the counter-move is running, the protected low still holds by the swings), or (b) the newest structure event is a CHoCH
  down (the protected low was closed through; the swings have not reversed yet). Daily / Weekly: DState phase `correction`
  (candidate or confirmed same-degree correction), `origin_broken` (origin closed through, no opposite impulse yet) or
  counter `pullback` (lower-degree pullback after the impulse extreme).
- **trending down / correction in a downtrend** — the mirror.
- **unclear** — Daily / Weekly UNKNOWN (data too short) or NEUTRAL (no trend structure); swings: fewer than two confirmed highs
  and lows; 5M: no LTF bars.

## Agreement

Reference = the Daily side (UP / DOWN), or a direction `d` passed by the caller (e.g. a range edge).
`agrees` = trending in that direction · `correction` = same trend, its counter-move running · `against` = the opposite trend
(a counter-move to the side) · `range` / `unclear` listed apart. Daily RANGE / unclear and no `d` ⇒ "no side — states only".

## Evidence wording

- `1H trending down`, `15M correction in progress`, … (one line per timeframe, `evidence(state)`);
- `agreement: Daily side DOWN — agrees: 1H · correction: 15M · against: 5M` (the agreement line);
- the story line per timeframe carries the reason, e.g. `15M: correction in progress (counter-move after the low <price>;
  no close beyond it yet (protected swing intact))`.

## API

```python
from decision3 import mtf_state as MS
st = MS.read_mtf_state(V, t, d=None)   # {t, as_of, tfs: {W, D, 1H, 15M, 5M}, agreement, story, evidence_only}
#   tfs[tf] = {state, trend, side, detail, source, protected, structure: {external: {degree, pivots, events},
#                                                                         internal: {degree, pivots, events, trend, leg_from}}}
MS.evidence(st)                         # short evidence lines
MS.draw_objects(V, t, d=None)           # [{kind: tf_state | swing | bos | choch, tf, t0, t1, p0, p1, label, state, evidence}]
MS.swings(V, t, tf), MS.frame(V, t, tf) # per-TF swings / bars closed at t (shared with legs_compare)
```

`t` is the 15M bar index of the V22 object; everything is read from bars closed at `bar_end[t]` (swings by their confirm bar,
Daily / Weekly states by `known_at`, LTF bars by `bar_end`, 1H candles only when closed). Pivot lists are the structure window:
from the older of the last two highs / lows on (the swings the trend reading uses).

## Numbers and settings

No new setting. The timeframe ↔ degree mapping reuses the existing `level_degree` (D2) and `tl_degree` (D1) settings; the
Daily pivot size reuses `daily_pivot_n`. No date, time or fixed number is used in the reading. The 1H "closed candle" check
compares the last 15M bar's end with the hour's end (or the session end) — a data-completeness check, the same one swings2 uses.

## What it is NOT

- Not a gate and not a grade: it never blocks an entry model or changes the conviction.
- Not a new swing definition: it only reads the existing swings (swings2 D0/D1/D2, the Daily fold, the LTF swing of `ltf_choch`).
- It does not change `daily.py`'s decision logic (DState is read as it is).
- It does not predict: "correction in progress" says the counter-move is running, not where it ends.

## Known gaps (honest)

- The 1H state uses the D2 swings measured on 15M bars and 15M closes for BOS / CHoCH (swings2's own definition), not a
  separate swing reading on 1H candles.
- 5M swings are the simple neighbour swings `ltf_choch` uses — many small swings; the 5M state turns often.
- The Weekly candle of the current (unfinished) week follows `daily.weekly_from_daily` as the engine does.
- BANKNIFTY has no 5M / FUT data in trade-data ⇒ its 5M state is "unclear (LTF data missing)".
