# T7 — Range market: range edges as areas, range state from structure (PA standard §2L)

Code: `decision3/range_edges.py` (new). Wiring: setting `range_state_rule` (`decision3/settings.py`), row key `range_state`
(`decision3/engine.py`). Tests: `tests/test_pa_range_edges.py`. Real-data check: `research/pa_range_edges_check.py`.

## Definition (the method's words)

When a timeframe's state is **range**, the range **edges are the areas**: a **bull put at the lower edge** (support), a **bear call at
the upper edge** (resistance). The entry models (E1–E4) apply at the edges like at any other armed area. A **breakout** of the range is
**context only** — Abhi does not trade breakouts.

* **When is a timeframe in range** (Abhi 21 Oct, from structure, comparative, no numbers — setting `daily_range_rule = structure`,
  the default): after a swing high **H** and a swing low **L** (an adjacent pair of that timeframe's swings — the two edges), the
  market is in range while the following confirmed swings **fail to make a new extreme on both sides**: at least one later swing high
  that does not break H and at least one later swing low that does not break L. Failure = no close beyond the edge in that swing's own
  leg; a wick beyond and the closes back inside = a **sweep**, still inside. The range in force = the oldest such pair not broken (the
  outer range). It **ends** when a swing forms beyond an edge with a close beyond the edge in its leg (the method's broken) ⇒ breakout,
  context only. No equality, no counts, no ratios (`daily.range_walk` / `range_pairs` / `range_at`).
  * Daily / Weekly: `daily.fold` uses this rule exactly where it used C-13 equal to declare RANGE (Q27 after a broken origin — edges from
    the impulse extreme on; from NEUTRAL — edges after the last break); the RANGE then ends at the break above (instead of the first close
    outside the band). `DState.range_pair` = the two edge swings.
  * 1H: the level-degree swings (swings2 D2) on their 1H candles; closes = the 1H closes (a 15M close beyond that is back inside by the
    hour's close is a sweep). 15M: the finest structure swings (D1) on 15M candles and closes.
  * `daily_range_rule = c13` = the earlier reading (two C-13 equal highs + two equal lows; ends at a close outside the band) — what-if.
* **An edge** = the edge swing's own candle, wick to body (`levels._band_swing`, width 0) — never a numeric band. Later swings of that
  side that reached the area (or swept beyond it) are listed as `members` (evidence) and never move or widen it (Abhi Z-1u / Z-1x).
  (c13 what-if: the extreme of the two equal swings anchors, as the levels' "d".)

## States (lifecycle of each edge)

The levels' own K4 machine (`Levels._step_far_swing` + the test count), replayed on the 15M bars from the bar the range is known:

| word | meaning |
|---|---|
| fresh | no visit since the range was read |
| tested ×n | price came into the edge area n times |
| broken | a close beyond the edge AND a swing formed beyond it; the far-side swing not reached — not a trade location |
| flipped | the far-side swing reached ⇒ role reversed — no longer this range's edge (no range trade side) |
| dead | a flipped edge broken again past its far-side swing |

A wick / closes beyond and back before any swing forms beyond = a sweep (★), not a break.

Trade location (`trade_location`): current range, fresh / tested, not Weekly (context only), and no alive 1H zone overlapping a
Daily edge (Abhi Z-1u: then the 1H band is the location — named in `inside_1h`).

## Evidence wording

* "Daily RANGE a–b: edges are the areas — bull put at the lower edge, bear call at the upper edge"
* "range upper edge = 2 equal swing highs (x, y) — area = swing candle lo–hi (wick to body)"; "tested ×2, ★1"; "bear call at the upper edge"
* "last Daily range ended: Daily close c above the range — Abhi does not trade breakouts — a range breakout is context only"

## API

* `read_range_edges(V, t, d=None, tfs=("D", "W"))` ⇒ `{by_tf, edges, evidence}`; `d` = +1 lower edges (bull put), −1 upper (bear call).
  Each edge has every key of a `Levels.snapshot` entry (id `range:<tf>:<edge>:<anchor bar>`, births `["range"]` (+ `"c"` once flipped),
  role, lo, hi, tests, sweeps, fresh, dist, state, far_swing, trade_location, …) plus `range_edge`, `trade_side`, `lifecycle`, `members`,
  `range`, `current`, `same_level` (the existing level with the same band, lineage), `inside_1h`, `evidence`.
* `armable(V, t, d=None)` — the current edges that are trade locations, nearest first. `trade_edges(V, t, tfs=("D", "1H"))` — the entry models' edges (DECISIONS 40, wired: `entry_models.Reader.range_edge_areas`, setting `range_edge_areas`, trade side only).
* `read_tf(V, t, tf)` (D / W), `read_intraday(V, t, tf)` (1H / 15M), `edges_from_rectangle(V, t, rect)` (hook for a rectangle reader,
  e.g. T4: swings2-shaped pivots, the last two highs / lows must be C-13 equal).
* `range_state(V, t)` — the row's structural range state: `{rule: "structure", in_range, tf (highest of D > 1H > 15M in range),
  tfs_in_range, edges (that tf, compact), by_tf {W, D, 1H, 15M: {state, band, since, edges, breakout}}, note}`. Cached per bar.
* `draw_objects(V, t)` — T8 schema: kind `area` / style `area.range_edge` per edge (state active / tested / broken / flipped / dead), and
  the breakout as kind `pattern` / style `pattern.range_breakout` (context).

## Settings (Abhi नियम, Abhi 21 Oct — both decided, default "structure")

* `daily_range_rule` = `"structure"` (default) / `"c13"` (what-if): the range definition above, for the Daily / Weekly fold and the
  1H / 15M reading.
* `range_state_rule` = `"structure"` (default): the row's `range_state` (key kept) = `range_state(V, t)` above, per bar.
  `"overlap"` = the legacy §5.3 overlap + doji measure (`method.range_state`, `range_overlap_min`, `range_state_n`, `range_broken_by`),
  only under `verdict_rule = score`, `None` under the method verdict; `range_state_gate = True` acts only with it (admin / what-if). Under the legacy score verdict the old overlap
  measure is kept only as the admin diagnostic `range_state_legacy_overlap` (legacy, not on cards) and `range_state_gate` no longer
  acts. Evidence only: the decision / checklist do not change.

## What it is NOT

* Not a numeric band: no tolerance, no width, no distance, no overlap ratio, no candle count, no σ (not swings2's Rhea range), no
  "equal" requirement.
* Not a trigger or a gate: evidence / areas only; the entry is the entry models' decision (wiring = T9).
* Not a breakout trade: a range breakout is context only.
* It does not change the Daily trend reading (UP / DOWN starts, protected, flips) — only where RANGE was declared by C-13 equal; the
  levels (`levels.py`) are unchanged and the edges are not added to `Levels`.

## Real data

### Under the earlier C-13 definition (why it was replaced)

* No Daily or Weekly RANGE episode in the whole history of NIFTY or BANKNIFTY (2016–2026); 1H / 15M almost never (BANKNIFTY 13 Jul – 9
  Oct: one 1H rectangle, already broken when known). Abhi (21 Oct): "a range never appearing in 10 years means the 'equal' definition is
  wrong for a range" ⇒ the structural definition above.

### Under the structural definition

Daily / Weekly, whole history (NIFTY 24 Oct 2016 – 19 Oct 2026 without the holdout days; BANKNIFTY 10 Oct 2016 – 9 Oct 2026;
`daily_leg_read = compare`):

| | NIFTY D | NIFTY W | BANKNIFTY D | BANKNIFTY W |
|---|---|---|---|---|
| RANGE episodes, structure | 1 (16 days) | 0 | 3 (43 days) | 0 |
| RANGE episodes, c13 | 0 | 0 | 0 | 0 |
| days whose trend state differs (structure vs c13) | 16 | 0 | 197 | 0 |

* NIFTY: 29 Jan – 19 Feb 2024, RANGE 21,285.55–22,124.15 (edges 16 / 18 Jan 2024); c13 read UP (origin broken) on those days.
* BANKNIFTY: 5–27 Dec 2016 (18,143.70–20,309.65), 9–22 Mar 2021 (34,658.70–37,232.20), 23 Oct – 14 Nov 2024 (50,369.40–54,467.35,
  ended by a close below the lower edge + a swing below).
* Longest periods where the Daily trend state differs (BANKNIFTY): 21 May – 16 Sep 2021 (82 days, c13 DOWN ⇒ structure UP), 4 Dec 2024
  – 8 Jan 2025 (25, DOWN ⇒ UP), 5–27 Dec 2016 (17, DOWN ⇒ RANGE), 6–31 Jan 2017 (17, DOWN ⇒ UP), 23 Oct – 14 Nov 2024 (17, DOWN ⇒
  RANGE), 23 Mar – 9 Apr 2021 (12, DOWN ⇒ NEUTRAL). A RANGE episode ends the old trend's origin_broken phase, so the trend that
  follows can differ for weeks. No differing day in 2025–2026 on either symbol.
* Daily RANGE stays rare because the fold declares it only where it did before: with no trend (NEUTRAL) or after a broken origin (Q27).

1H / 15M (bars where each measure says "range"; structure = any of D / 1H / 15M in range):

| sample | bars | structure | 1H | 15M | overlap + doji | differ |
|---|---|---|---|---|---|---|
| NIFTY 21 Oct | 22 | 14 | 14 | 0 | 5 | 15 |
| NIFTY 1–21 Oct | 322 | 185 | 146 | 121 | 96 | 163 |
| BANKNIFTY 1–9 Oct | 150 | 149 | 145 | 149 | 58 | 93 |
| BANKNIFTY 22–29 Sep | 150 | 134 | 134 | 78 | 51 | 95 |

* NIFTY 21 Oct 14:30: 1H RANGE 22,558.95–23,175.25 (lower edge = the 14 Oct swing low, upper = the 19 Oct swing high), both edges
  fresh; the 15M range 22,913.80–23,175.25 ended earlier that day (a close below the lower edge + a swing below — context).
* The range in force is the OUTER one (the oldest unbroken pair); inside it narrower pairs are the same range.

Charts: trade-data `review/pa_standard/t7/structure/` — `daily/` (the four Daily episodes), `nifty_21oct/`, `nifty_oct/`,
`banknifty_oct/`, `banknifty_sep/` (15M + 1H per sample bar; markers under the 15M candles: structure range / overlap + doji),
`daily_weekly_compare.json`.
