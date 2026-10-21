# Numbers in chart reading — inventory (Abhi: "a trader compares, he does not calculate")

Abhi's principle (final): chart reading is **logic, not mathematics**. Reading rules contain no numbers, prices, counts, widths, ratios
or time references. Numbers are allowed only in **operational** dashboard settings (lots, SL, target, exits, schedules).

This file lists every numeric threshold found in the reading path (`decision3`, `rsi2.Divergence`, the levels / flip state machine and
the pieces they call). Each one is in one of three groups:

- **A. Replaced now** with Abhi's comparative / structural definition (this PR).
- **B. Allowed**: operational settings, display limits, data plumbing, or legacy what-if switches that are off by default.
- **C. For Abhi**: a number that cannot be removed without losing the logic, or whose logical replacement Abhi has not defined yet.
  Each row has the reason and a proposed logical form. Nothing is kept silently.

## A. Replaced now (this PR)

| Was | Now (logic) | Where |
|---|---|---|
| `study_min_bars` = 4 (minimum candles before a handover can be read) | No minimum count. The slower read compares an earlier part of the visit with a later part, so it needs at least one candle in each part. The two-candle read covers a fast visit. | `method.zone_study`, `method.handover_episode` |
| `sharp_rej_wick_body` = 1.0 (push wick ≥ 1.0 × body) | Push rejected: the push-side wick is longer than the body, and the candle closes back without closing beyond the zone. | `method.sharp_reversal` |
| Two-candle read needed higher slot-normalised volume | Volume is not part of the two-candle read (Abhi: "a push rejected and immediately swallowed by a dominant opposite candle is a handover in itself"). The commitment does its own volume comparison. | `method.sharp_reversal` |
| `commit_dom_mult` = 1.5 (body ≥ 1.5 × window average) | Dominant: the body is larger than every other candle in the visit. `c0_dominance` False exists only for old synthetic fixtures. | `method.commitment`, `method.sharp_reversal` |
| c0 volume > window average | The commitment's volume is higher than the average of its comparison set: the approach leg's candles and the visit's opposite-side candles, excluding the rejected push and the commitment (Abhi, L3-c). Nothing to compare ⇒ no commitment. | `method.commitment` |
| `trade_band_max_sigma` = 1.5 σ_1H cap + dashboard `engine3_band_max_sigma` | No cap. A zone that looks too wide is a construction problem (two bases joined), and the fix belongs in the construction (Z-1u). The setting is what-if only, default None; the dashboard setting is removed. | `levels.snapshot`, `engine3_live`, dashboard |
| `level_min_width_sigma` = 0.15 σ_1H (minimum zone width; widened thin bands) | 0: a zone is its own base / reaction candle, wick to body, never widened by a number. If the candle has no wick on that side, the zone is its body; with no body either, the whole candle — never a single price (TA4). PF-2 "provisional width" now applies only to the legacy min-width what-if. | `levels._band_swing`, `levels._w` |
| Far swing = nearest swing beyond the band, even a sweep wick | The last real swing of the same structure beyond the zone. A wick that only pokes past the zone and closes back (the swing candle's close) is a sweep, not a swing (Z-1y). | `flip.structural`, `flip.far_swing`, `levels.band_flip_facts` |
| RSI divergence: `div_bars` bar window (3–50 / 3–35 / 3–60) | Consecutive real swings only; no bar counts or gaps. `div_bar_window` True is a legacy what-if. | `rsi2.engine.Divergence._eval` |
| RSI divergence: "equal high / low" within 0.2 MR tolerance counted | Price must make a new extreme (strictly beyond the previous one) while RSI does not go beyond its previous extreme. | `rsi2.engine.Divergence._eval` |
| RSI value = extreme within ±2 bars of the price pivot (`div_rsi_window`) | RSI at the swing: its extreme inside the swing's own span (between the neighbouring opposite swings). | `rsi2.engine.Divergence._eval` |

## B. Allowed (operational, display, data, legacy)

- **Operational / schedule:**
  - `entry_start` / `entry_end` / `evidence_start` / `entry_first_bar` (entry hours).
  - `rr_step`, `sl_buffer_sigma`, `min_rr` (legacy R:R, off).
  - Dashboard lots / SL / target.
  - `approval_band_warn_pts` (Telegram display alert; see C-18).
- **Display only:**
  - `show_distance_sigma`, `chart_*`, `liq_marks_per_side`, `watch_levels_max`, `active_levels_max`.
  - facts/validity `max_lines`, `max_bands_per_side`.
  - rsi2 `div_show`.
- **Data plumbing:**
  - `vol_gap_max_frac` (Abhi RF-2 data-quality rule: share of bars without FUT volume).
  - FUT completeness (3 of 3 5M children).
  - rsi2 `warmup_bars` (RSI needs history to settle).
  - swings2 `warmup_sessions`.
- **Legacy what-if, off by default:**
  - `level_merge`, `zone_visit_rule = touch_window`, `level_flip_rule = acceptance`, `corr_degree_frac`.
  - `daily_swing_method = dc` / `daily_dc_k`, `wave_gates`, `range_state_gate`, `div_bar_window`.
  - `trade_band_max_sigma` (None), `level_min_width_sigma` > 0.
- **Still in the code, not used:** rsi2 `div_rsi_window` (old ±2-bar search; kept only for the read API, marked unused).
- **Indicator definitions:**
  - RSI `period` 14 (Wilder).
  - Cardwell bands in the old rsi2 `RSI` class (`bull_min` …). The decision path does not use these.

## C. For Abhi — numbers still in the reading, with a proposed logical form

| # | Number (default) | What it does | Why it is not removed now | Proposed logic (Abhi to confirm) |
|---|---|---|---|---|
| C-1 | swings2 `k` (θ = k × σ; D1 = 4, D2 = 6) | Defines what counts as a "real swing" at each degree (the "same structure") | Every swing, zone, flip and divergence is built on it. Abhi chose D1 = 4 and D2 = 6 from charts (SWING CHECK). Without a replacement there are no swings. | **Resolved (Abhi, layer 1 ✅):** keep A — the approved swings2 D1 / D2 ARE the swing definition. Significance is judged against the market's own normal movement (σ) at the scale Abhi chose from his own charts: his visual calibration, not a fixed point value. Registered as a calibration setting (`swings2` `k`; decision3 `swing_k`, advanced dashboard). The pure comparative rule is not used (it matched 4 / 12 because it counts one-candle turns as swings). |
| C-2 | swings2 `eq_tol_sigma`, `gap_bar_sigma`, `rhea_*`, `disp_*`, `trend_body`, `trend_clv`, `always_in_*` | Equal highs/lows, gaps, Rhea / Dow lines, displacement, always-in | Part of the swing / structure engine (layer 1). | **Resolved with C-1:** part of the approved swings2 engine; Abhi's approved swing charts are its acceptance. |
| C-3 | `vol_slot_sessions` 20 / `vol_slot_min_sessions` 10 | Volume ÷ the same 15M slot's median over earlier sessions | The opening and closing bars are always heavy, so comparing raw bars across the day is biased. The FUT export starts at the contract's own history, so 12–13 Oct have only 7–8 earlier sessions and normalisation is NA. | Either compare raw volume bars within the same visit (Abhi's "volume bars" view; the opening bar then always looks heavy), or keep the slot baseline as data plumbing. Abhi to choose. |
| C-4 | `accept_closes` 3 | A close beyond the zone sustained 3 times ⇒ BROKEN (else a sweep) | It decides break vs sweep; removing it changes every lifecycle. | "Broken = price closes beyond the zone and does not come back inside on the next candle", or "a close beyond plus a swing formed beyond". Abhi to define. |
| C-5 | `touch_window_bars` 3 (③ "in / next to the zone") | A touch within the last 3 bars counts as at the zone | The visit already defines being in the zone; ③ still uses the bar window. | ③ = a visit is in progress (Z-1v). **Layer 6b:** the facts dossier reads the visit by structure too; the number is read only by the legacy `zone_visit_rule = touch_window` (LEGACY in the CI guard). |
| C-6 | `doji_body_max` 0.1, `commit_body` 0.5, `commit_close_frac` 2/3, `pin_wick_min` 0.5, `star_body_max` 0.3, `tweezer_tol` 0.1, `commit_merge_max` 2 | Candle-shape tests for the commitment form (Q16) | These are the reversal-form vocabulary; Abhi has not given the logical forms. | Doji = body smaller than each wick. Pin = rejection wick longer than body and than the other wick, close on the trade side. Strong close = body larger than both wicks. Star = middle body smaller than both neighbours. Tweezer = the second candle makes no new extreme. |
| C-7 | `candle_avg_n` 5 | "Big" body / range = larger than the average of the last 5 | Evidence only (conviction). | Big = larger than the candles of the same visit / leg. |
| C-8 | `power_shift_min` 2, `power_overlap` 0.5, `power_fallback_bars` 8 | ④ power shift (evidence) | Evidence scoring (C step). | (a) pullback candles smaller than the impulse candles; (b) bodies overlapping each other; at least one of the four items present. |
| C-9 | `pattern_eq_mr` 0.5 | Double / triple top-bottom "equal" extremes | Evidence (a2 pattern). | Equal = the later extreme does not go beyond the earlier one. |
| C-10 | `liquidity_eq_sigma` 0.15, `liquidity_lookback` 8 | Equal-highs/lows liquidity bands, sweep lookback | Level birth (d) and evidence. | Same as C-9; lookback = the current leg. |
| C-11 | `k_reset_sigma` 0.25 | ③ K extreme reset only if the new extreme moves 0.25 σ | Pullback bookkeeping. | Reset when price makes a new extreme beyond the old one (any amount). |
| C-12 | `tl_touch_sigma` 0.15, `tl_min_touches` 2; facts/validity `touch_mr`, `between_close_mr`, `min_spacing`, `max_slope_mr`, `break_buf_mr`, `disp_break_mr`, `disp_outer`, `band_tol_mr`, `band_max_mr`, `magnet_crossings`, `confluence_mr`, `mr_bars` | Trendline / chart-band finder (K5 / K6 / TA rules) | A KB-wide rewrite of K5 / K6 in logic language is needed first (the KB carries these numbers). | Touch = the pivot reaches the line and turns. Real break = a close beyond plus a candle larger than the ones before it, or a second close beyond. Two separate reactions = price left the band between them. |
| C-13 | Daily: `daily_pivot_n` 2, `daily_min_sessions` 10, `weekly_min_bars` 10, `range_eq_sigma_d` 0.25, `maturity_sigma_d` 0.5 | Daily swings, data sufficiency, RANGE "equal" edges, maturity "near target" | Trend layer (①). The minimum-sessions values are data sufficiency (B-like). | **Resolved (Abhi L1-b):** equal = reaches the earlier swing's area and not beyond; maturity "near" = reached the projection's area; `maturity_sigma_d` removed; `range_eq_sigma_d` only legacy / display; `daily_pivot_n` open (L1-c). **Layer 6b:** the Daily display bands / RANGE report use C-13 too (`daily.c13_*`); `range_eq_sigma_d` is read only by the legacy minor fold. |
| C-14 | `prior_level_atr_mult` 8, `prior_level_atr_n` 14 | Which prior Daily / Weekly swings are kept as levels (distance from price) | Q40 selection by distance. | Keep the prior trend-degree swings that the current price range can reach: those inside the last Daily impulse's span. |
| C-15 | `max_attempts` 3 (4th attempt ⇒ no trade) | §5.1 count | Off by default (`wave_gates` False). | Already context only; can be deleted. |
| C-16 | `flip_pullback_vol_ratio` 1.0, `flip_vol_min_coverage` 1.0 | G4 context (b) volume lower/higher | Context only (comparison at 1.0 = "lower"). | Already a comparison; coverage = every bar has volume (data rule). |
| C-17 | `evidence_weights`, `conv_a` / `conv_b` / `conv_weak`, `score_*` | Conviction grade A / B / weak from weighted evidence | Grading is a sum of numbers. | Grade by which pieces of evidence are present (e.g. A = handover + commitment + LTF + a confirming piece), with no weights. Abhi to define. |
| C-18 | `approval_band_warn_pts` 150 (dashboard) | Telegram "merged band — check" when a band is wider than 150 pts | Temporary display alert from before #329 fixed the construction. | Flag only when a band's lineage shows two bases (structural), or remove now that bands are never merged. **Layer 6b:** `approval_band_warn_rule` = `points` (default) / `method` (engine areas never flagged — one base by construction; other sources keep the number, display only). |
| C-20 | `range_overlap_min` 0.5, `range_state_n` 3 | §5.3 range state (context fact) | Context only (`range_state_gate` False). | Range = candles overlapping each other, none making a new extreme. |
| C-21 | `level_degree` 2, `tl_degree` 1, `flip_pullback_inner_degree` 1 | Which swings2 degree a level / trendline / pullback uses | Tied to C-1 (what "the same structure" is). | **Resolved (Abhi):** the zone's structure = the approved D2; the pullback inside it = one degree below (D1). Calibration class in the guard. |
| C-22 | rsi2 `RSI` class `min_price_sigma` 0.25, `min_rsi` 3, `line_skip` 2, `pivot_k` 3, `gaps` | The older layer-6 RSI detector and RSI pivots | Not on the decision path (decision3 uses `Divergence`), but still numeric. | Retire, or align with `Divergence` (consecutive real swings, new extreme, no gaps). |
| C-23 | `_majority` "at least half of the other sub-checks" in `zone_study` | trade side growing / counter side weakening = the required check plus at least half of the others | A count rule inside the zone reading. | "Required check true and no sub-check against it", or Abhi's wording. |
| C-24 | Definitions I coded that are not Abhi's words | Two-candle read: "rejected" = push-side wick longer than the body; "swallowed" = body covers body **and** close beyond candle 1's extreme. Far swing: a swing whose own candle closed back inside the zone is a sweep. RSI at a swing = its extreme inside the swing's span. No opposite-side candle in the visit ⇒ volume not compared, grade cap B (fail-safe). Zone study / dominance windows include visit candles that closed beyond the zone. | Implementations of Abhi's words; each needs his yes / no. | OPEN_QUESTIONS Z-1z-a, Z-1z-d; Abhi to confirm the rest. |
| C-19 | rsi2 `div_degrees` (0, 1, 2) | Which swing degrees are compared | Tied to C-1 (what a "real swing" is). | **Resolved (Abhi L5-a):** the pushes of the move into the zone = one degree below the zone's structure (D1 for a D2 zone); the zone's own degree reported. |

## KB / Method Pack

- K4 zone rules from this round now use logic only:
  - far swing; zone width; visit; failed dominant candle; handover; volume; RSI divergence.
- Golden-case prices and dates moved out of the public KB into the private fixtures (trade-data `fixtures/golden_cases.md`):
  - K4 flip fixtures; K4 13 Oct trend note; K4 golden fixture names; K6 golden fixture; K6 7 Oct example.
- Still numeric in the KB (≈ 230 expressions), mostly the definitions behind C-6 and C-12:
  - base / displacement in MR;
  - trendline touch / slope / spacing;
  - real-break buffer;
  - magnet crossings;
  - hypothetical illustration prices (25,000 examples).
  
  These are rewritten section by section once Abhi confirms the C rows. Changing a definition the KB owns without his answer would be inventing a rule.
- The Method Pack has no golden prices. `--check` passes; the pack is generated from KB sections and follows them.
