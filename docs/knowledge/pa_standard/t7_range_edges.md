# T7 — Range market: range edges as areas, range state from structure (PA standard §2L)

Code: `decision3/range_edges.py` (new). Wiring: setting `range_state_rule` (`decision3/settings.py`), row key `range_state`
(`decision3/engine.py`). Tests: `tests/test_pa_range_edges.py`. Real-data check: `research/pa_range_edges_check.py`.

## Definition (the method's words)

When a timeframe's state is **range**, the range **edges are the areas**: a **bull put at the lower edge** (support), a **bear call at
the upper edge** (resistance). The entry models (E1–E4) apply at the edges like at any other armed area. A **breakout** of the range is
**context only** — Abhi does not trade breakouts.

* **When is a timeframe in range** (from structure, no numbers): its last two swing highs are *equal* and its last two swing lows are
  *equal*. "Equal" = C-13: the later extreme reaches the earlier swing candle's area (wick to body) and does not go beyond the earlier
  extreme.
  * Daily / Weekly: the existing RANGE state of `decision3/daily.py` (Q27 after a broken origin, or from NEUTRAL) — unchanged, only read.
  * 1H: the level-degree swings (swings2 D2, the 1H areas' own swings) on their 1H candles (as the levels' (a) birth).
  * 15M: the finest structure swings (swings2 D1) on their 15M candles.
  * The range lasts until a **close beyond its band** (the Daily RANGE's own end rule). Then the timeframe is "no range" and the
    breakout is reported as context.
* **An edge** = the swing candles that made it, never a numeric band. The area = the extreme (anchor) swing candle's own area, wick to
  body (`levels._band_swing`, width 0) — the equal-highs / equal-lows construction of the levels ("d": one base ⇒ the earlier, extreme
  swing's band). The other swing candles that reacted there are listed as `members` (inside ⇒ the same zone; overlaps ⇒ lineage) and
  never widen it (Abhi Z-1u / Z-1x). A later equal swing (a third touch: triple top / bottom) joins the members once confirmed.

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
* `armable(V, t, d=None)` — hook for the entry models (T9 wiring): the current edges that are trade locations, nearest first.
* `read_tf(V, t, tf)` (D / W), `read_intraday(V, t, tf)` (1H / 15M), `edges_from_rectangle(V, t, rect)` (hook for a rectangle reader,
  e.g. T4: swings2-shaped pivots, the last two highs / lows must be C-13 equal).
* `range_state(V, t)` — the row's structural range state: `{rule: "structure", in_range, tf (highest of D > 1H > 15M in range),
  tfs_in_range, edges (that tf, compact), by_tf {W, D, 1H, 15M: {state, band, since, edges, breakout}}, note}`. Cached per bar.
* `draw_objects(V, t)` — T8 schema: kind `area` / style `area.range_edge` per edge (state active / tested / broken / flipped / dead), and
  the breakout as kind `pattern` / style `pattern.range_breakout` (context).

## Setting `range_state_rule` (Abhi नियम, Abhi 21 Oct)

* `"overlap"` (default in code = today, until Abhi's ✅ at deploy): the row's `range_state` stays as today — `None` under the method
  verdict, the legacy §5.3 overlap + doji measure (`method.range_state`, `range_overlap_min`, `range_state_n`, `range_broken_by`) only
  under `verdict_rule = score`; `range_state_gate = True` acts only with this rule.
* `"structure"`: the row's `range_state` (key kept) = `range_state(V, t)` above, per bar. Under the legacy score verdict the old overlap
  measure is kept only as the admin diagnostic `range_state_legacy_overlap` (legacy, not on cards) and `range_state_gate` no longer
  acts. Evidence only: the decision / checklist do not change.

## What it is NOT

* Not a numeric band: no tolerance, no width, no distance, no overlap ratio, no candle count, no σ (not swings2's Rhea range).
* Not a trigger or a gate: evidence / areas only; the entry is the entry models' decision (wiring = T9).
* Not a breakout trade: a range breakout is context only.
* It does not change the Daily RANGE reading (`daily.py`) or the levels (`levels.py`); the edges are not added to `Levels`.

## Real data (21 Oct NIFTY, BANKNIFTY) — finding

With the default Daily reading (impulse-degree Dow, C-13 equal), **no Daily or Weekly RANGE episode exists in the whole history** of
either symbol (NIFTY 2016–2026, BANKNIFTY 2016–2026). So on real data the range edges come from the 1H / 15M structural reading only.
Open question for Abhi: is the Daily RANGE (C-13 equal: the later extreme inside the earlier swing candle's own wick-to-body, never
beyond) as strict as he wants, given it has never fired on Daily / Weekly?
