# Method map — every reading concept → one owner module (governed by `docs/knowledge/CHART_READER_METHOD.md`)

`CHART_READER_METHOD.md` is Abhi's single, complete specification. It replaces every earlier piece-by-piece answer. This map ties each of its concepts to the **one** module that owns it in the live reading path (decision3 V22 → `engine3_live` → engine signal / level bots). For each concept it gives the current state, what contradicts the method, and the layer PR that rebuilds it.

**Reading path today:**
- `decision3` V22 (`engine`, `levels`, `flip`, `method`, `daily`, `daily_legs`, `trendline`, `liquidity`, `volume_pane`, `setup_chart`, `telegram_view`);
- `swings2` (swings / degrees);
- `legs2.volume` (FUT volume per bar), and `legs2` features / v1 `measure` + `patterns2` (both used inside `decision3.daily_legs`);
- `rsi2.engine.Divergence` (RSI);
- `facts.validity` (the shared line / band check for charts);
- `bots_common.level_reaction` (the level bots share `method.confirm`).

**Not in the reading path** (research or older engines, left in place, not owners of any concept):
- `chart_reader`, `opportunity_engine`, `elliott`, `market_state`, `decision2`;
- `pivots` (v1), `legs2` `ik`, `zones2`, `trendlines2` layer;
- the `rsi2` `RSI` class.

They are listed so nothing claims to own a concept twice. Where a row below names helper modules, the **first** module is the single owner and the rest are internals it calls (or callers that the layer moves onto the owner). Retiring them is a separate clean-up, never mixed into a layer PR.

| Method concept (section) | Owner module | Today | Contradicts the method | Layer |
|---|---|---|---|---|
| P2 one continuous chart | all owners | Several day / session resets exist: swings2 σ is session-frozen; legs2 features always drop the overnight gap; `method._same_window` keeps 2-candle forms within one session (`evidence_start`); slot-normalised volume compares time-of-day slots; the commitment checks clock entry windows. | Every day / session / clock rule inside reading. Entry hours stay only as an **operational** schedule outside reading (`engine_signal.in_window`). | 1, 3 |
| Swing (§3 Structure) | `swings2.engine` | Directional change: θ = k × σ per degree (D1 = 4, D2 = 6). | A numeric θ. Method: a turning point the following structure respects, which price leaves by a leg larger than the pullbacks inside that leg. | **1** |
| Degree | `swings2.engine` (nesting) | Degrees set by k. | The numbers. The nesting itself stays: a higher degree contains lower-degree swings. | 1 |
| Impulse / correction | **`decision3.daily_legs`** (internals: `legs2` features, `patterns2` shapes) | Candle-ratio thresholds (`disp_*`, `trend_body`, `trend_clv`, …). | The ratios. Method: larger directional candles with little overlap versus overlapping smaller candles, plus shape. | 1 |
| Equal (double / triple) | **`swings2`** (one `equal()` helper in layer 1; today's callers with their own tolerances: `levels` liquidity (d), `method.zone_pattern`, `daily` RANGE) | σ / MR tolerances in each caller. | Tolerances. Method: equal = the later extreme does not go beyond the earlier one. | 1, 2, 3 |
| Big / dominant | `method` (`candle_read` `candle_avg_n`; c0 dominance) | c0 already uses "larger than every other candle of the visit". `candle_read` still uses the average of the last 5 candles. | The 5-candle average. | 3 |
| Weekly / Daily trend (§2 a–b) | `decision3.daily` | Degree-aware Dow; maturity / wave gates are already off. | `daily_pivot_n`, `daily_min_sessions`, `range_eq_sigma_d`, `maturity_sigma_d` (numbers). Min-sessions is a data-quality check, which is allowed. | 1 |
| Area — one base, wick to body | `decision3.levels` (`_born`, `_band_swing`) | Done in #329: one timeframe, never merged or widened, no minimum width, never a single price. | — | 2 (keep) |
| Area kinds (demand / supply / flipped / origin of a sharp move) | `decision3.levels` births a / b / c / d | Layer 2: liquidity (d) = equal by comparison (`liquidity_rule = equal`: the later extreme does not go beyond the earlier swing's own area). Prior trend-degree swings without an ATR distance (`prior_level_rule = all`). The origin of a sharp move = BOS base (b). | — (σ / ATR rules kept only as what-if switches) | 2 ✅ |
| Confluence label | `decision3.levels.snapshot` | Done in #329. | — | 2 (keep) |
| Lines (two reactions, 3rd touch, follows the structure's swings) | **`facts.validity`** (the one line check; `decision3.trendline` is its caller) | MR numbers: `touch_mr`, `between_close_mr`, `min_spacing`, `max_slope_mr`, `tl_touch_sigma`, `tl_min_touches`. | The numbers. Method: two separate reactions, price left the line between them, drawn on the structure's own swings. | **4** |
| Visit | `decision3.engine.visit` | One close outside, away from the area, ends the visit. | Method: ends only by structure (a swing built away from the area), a break / flip, or a failed commitment closing outside. A candle that closes just outside and comes back is the same visit. Time never ends a visit. | **3** |
| Sweep / Broken | `decision3.levels._step_far_swing` | Layer 2: `break_rule = structure` — broken = a close beyond **and** a swing (finest degree) formed beyond; back inside before that ⇒ sweep. Reclaim mirrors it (back inside + a swing formed back on the role side). | — (`accept_closes` kept only as the `break_rule = closes` what-if) | **2 ✅** |
| Flipped / far-side swing / Dead | **`decision3.levels`** (state machine; `flip` holds its pure helpers) | Done in #329: structural far swing, sweep wick excluded, Z-1s for new extremes, DEAD with no second flip. | — | 2 (keep) |
| Handover — slow form | `method.zone_study` / `handover_episode` | Halves comparison, no minimum count (#329). `_majority` = the required check + at least half of the others. | `_majority`'s "at least half". Method: trend-side candles grow, opposite-side candles shrink, volume tilts to the trend side. | **3** |
| Handover — fast form | `method.sharp_reversal` | Body covers body **and** close beyond candle 1's extreme. | Method: closes beyond the push candle's **body**. | **3** |
| Opposite side disappearing | `method.zone_study` (Z-1p) | Counted as exhausted. | — | 3 (keep) |
| Absorption | `method.zone_study` | "Counter side strengthening (body ↑, range ↑, volume ↑)". | Method: the opposite side keeps coming in small candles and price does not move away (sideways base) ⇒ no trade, expect a break. | **3** |
| Handover holds / cancelled | `method.handover_episode` | Done (Z-1q) per visit. | — | 3 (keep) |
| Commitment candle form | `method.reversal_form` | Shape ratios: `commit_body`, `commit_close_frac`, `pin_wick_min`, `star_body_max`, `tweezer_tol`, `doji_body_max`. | Ratios. Method: comparisons of body and wicks. | **3** |
| Commitment volume | `method.commitment` | Larger than the opposite-side candles of the visit. No opposite candle ⇒ grade cap B (a review fail-safe, not in the method). Slot-normalised when history exists. | Method: larger than the candles of the **approach leg** and the visit's opposite-side candles, **excluding** the rejected push and the commitment. Raw bars. | **3** |
| LTF change of character | `method.ltf_choch` | Close-based, after arrival; reads 5M swings and the lower-timeframe structure since the pullback began. | Any count / window inside the LTF read (to be listed against the method in layer 3); the rule itself matches. | 3 |
| Correction-line trigger | `decision3.trendline` | Close-through at the area. | Numbers in the line finder. | 4 |
| Volume source / data problem | **`decision3.engine.vol_view`** (data from `legs2.volume.bar_volume`; `method.slot_rel_volume` goes) | Slot-normalised (20 / 10 sessions) with a raw fallback. FUT missing ⇒ data problem. | The slot baseline (time-of-day logic). Method: raw bars. | **3** |
| RSI divergence | `rsi2.engine.Divergence` | Consecutive swings, new extreme, no bar window, RSI at the swing's span (#329). Equal RSI counts. | `div_degrees` follows layer 1 (the method: consecutive real swings of the same degree). | **5** |
| Decision (§4) and labels | **`decision3.engine.decide`** (conviction moves into it from `method`) | Evidence weights (`evidence_weights`, `conv_*`) produce A / B / weak. | Method: no scores. A = the required set + ≥ 1 confirming piece; B = the required set only. | **6** |
| Output (§5) | **`decision3.telegram_view`** (the story + evidence list; `setup_chart`, `engine3_live.row_from_v22`, `bots_common.plain_text` render it) | Partly words, with ratios removed in #329. | A story in the method's order, an evidence list (present / absent), and every price taken from data. | **6** |
| Never: R:R gates, wave gates, breakout entries | `engine` (`rr_step` off, `wave_gates` off) | Off by default. | Delete the legacy gates in layer 6. | 6 |
| Watch (§4): every valid area ahead in the trend direction armed, nearest first (P5) | **`decision3.levels.active`** + `engine` watch-list | Layer 2: no cap — every valid area ahead is armed (RANGE: the nearest support + the nearest resistance); confluence areas uncapped. | — (`watch_levels_max` / `active_levels_max` no longer read by the reading path) | 2 ✅ |
| Mirror (§4) | every owner (each function takes the trade direction) | Mirror tests exist for most reads. | — (layer tests keep a mirror case each) | 1–6 |
| P8 clean charts | **`decision3.setup_chart`** (+ `facts.validity` display selection) | Chart limits per side (display). | Display only — allowed as output settings. | 6 |
| CI check: no numbers / time logic in the reading path | new `tests/test_method_no_numbers.py` | — | Grows with each layer: every reading-path setting must be logic, a data-quality check, or operational. | 1 → 6 |

## How the open questions are resolved (per the method's resolution order; no questions to Abhi)

Every earlier Z- / C- question is answered by the method itself. Each is logged in OPEN_QUESTIONS as "assumed — no answer needed unless Abhi objects":
- **Z-1z-a "swallowed":** taken back by a dominant opposite candle that **closes beyond the push candle's body** (§3 Handover, fast form).
- **Z-1z-d volume when no opposite-side candle:** the commitment is compared with the **approach leg's candles** and the visit's opposite-side candles; the rejected push and the commitment are excluded (§3 Commitment). The grade-cap-B fail-safe goes.
- **C-3 volume baseline:** raw bars; no time-slot baselines (§3 Volume).
- **Z-1v-b / Z-1v-c visit end:** by structure only (§3 Visit).
- **C-4 break vs sweep:** broken = a close beyond **and** a swing formed beyond (§3 Area lifecycle).
- **C-17 conviction weights:** A / B labels as in §5; no weights.
- **C-1 / C-21 swing / degree:** §3 Structure (layer 1).
- **C-5 at the zone:** a visit is in progress (§3 Visit).
- **C-6 / C-9 / C-10 / C-20 shapes / equal / range:** comparisons (§3 Structure, Commitment).
- **C-12 lines:** §3 Lines (layer 4).
- **C-18 approval 150-pt alert:** operational display, kept until layer 6 decides the output.
