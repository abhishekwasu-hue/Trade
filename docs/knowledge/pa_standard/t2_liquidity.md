# PA standard §2D — obvious swing extremes and inducement (track T2)

Module: `decision3/liquidity_pa.py`. Evidence only. `decision3/liquidity.py` (pools, equal highs / lows, sweeps / traps) is unchanged
and still owns D.1 / D.4; this module adds D.2 and D.5 beside it.

## D.2 Obvious swing extremes (resting liquidity)

**Definition.** Every confirmed structure swing (D2 on 15M, and the Daily swings) whose own extreme has **not been traded beyond** since
it formed is resting liquidity: buy stops rest above an untaken high (buy-side, BSL), sell stops below an untaken low (sell-side, SSL).
Once a later bar trades beyond it, it is **taken** — by a wick that closed back (`taken_by = "wick"`, the sweep look) or by a close
beyond (`"close"`). A taken extreme no longer rests. Equal highs / lows (method §3 "equal", `liquidity._equal`) are tagged
`src = "equal"`. On each side and timeframe the outermost resting extreme is `outer` (the external liquidity of the visible structure)
and the one closest to price ahead of it `nearest`.

**States.** resting / taken (+ `taken_at`, `taken_by`).

**Evidence wording.** `buy-side liquidity resting above the structure swing high 23,120.90 — nearest`.

**Not.** Not every swing (a taken one is history, not a pool). Not a sweep read — the full sweep / trapped reading stays in
`liquidity.sweeps_and_traps`. No distance limit in the reading (charts may hide far ones).

## D.5 Inducement

**Definition.** A minor extreme just before an area that gets taken first. For every area ahead of price (a supply not below price, a
demand not above it; not BROKEN / DEAD):

1. the approach = the bars after the area's base / last visit, from the extreme of the move away from the area;
2. the inducement = the finest-degree (D1) swing formed on that approach, lying between that extreme and the area — a high below a
   supply, a low above a demand — the one **closest to the area**;
3. it is taken when a later bar trades beyond it; `area_reached` = price reached the area at or after that.

**States.** `none` (no such swing on the approach yet) / `resting` / `taken`; `taken_first` = taken and then the area was reached
("inducement taken first"). `degree` = "minor" (a D1-only swing) or "structure" (the swing is also a D2 swing).

**Evidence wording.** `inducement before the supply 23,016–23,121: minor high 22,980.00 taken by a wick ⇒ then the area was reached
(inducement taken first)`.

**Not.** Not a gate and not a trigger: an untaken inducement does not block a model, a taken one does not arm one. Far areas get a
reading too (their approach may not have developed — then the inducement is far from the area; charts show the nearest area per side).

## API

- `read_liquidity(V, t, d=None)` → `{"obvious": [...], "inducement": [...]}` (each item has `evidence`).
- `obvious_extremes(V, t, include_taken=False)`, `inducement(V, t, area)` (area = a `levels.snapshot` item).
- `draw_objects(V, t, read=None)` → `liquidity_extreme` and `inducement` objects (T8 schema).

No look-ahead: bars ≤ t, swings confirmed by t. No settings added.
