# facts/ — the facts layer (design `docs/design/CHART_READER_AGENT.md` §3, build step R1)

One owner per concept; facts + evidence only (prices, bar times, counts) — never a vote, score, grade or trade decision.
No AI calls, no broker, no network.

- `validity.py` (R1a) — the one K6 line check and the one K4 band check used by every chart (`check_line`, `check_band`,
  `confluence`, `select_lines`, `select_bands`, `lookback`).
- `dossier.py` (R1b) — `build_dossier(symbol, bars_by_tf, fut_bars_by_tf=None, as_of=None, cfg=None)`: calls each owner below once
  and returns one JSON-safe dict `{"schema", "symbol", "as_of", "asof_bar", "inputs", "sections"}`.

## Layer 6b — the facts read the SAME method as the decision

Abhi's method (`docs/knowledge/CHART_READER_METHOD.md` §5): the areas, lines, visits, zone study, commitment, LTF change of character
and RSI divergence in the dossier are the decision engine's own reads — `decision3.engine.V22` on the same cut bars (closed Daily bars
when given, the 5M spot as the LTF, the FUT 5M bars as volume, the shared swings2 result when the swing scale is the same):

- areas = `decision3.levels` (one base per area, wick to body, K4 state; the armed ones = the decision's watch list, with the line label);
- lines = `decision3.trendline.swing_line` (two separate reactions; touches by reactions, `touch_groups`) + `reaction_touch` (touch N);
- the visit = `V22.visit` by structure (`zone_visit_rule = structure`) — never `touch_window_bars`;
- the confirmation = `V22._confirm` (handover episode, commitment vs the approach leg + the visit's opposite side with the rejected push
  excluded — L3-c3 closed, LTF CHoCH);
- RSI = `V22.rsi_divergence` (pushes inside the move into the zone, the highest degree with two pushes, the zone's own degree) and the
  layer-5 `rsi2.engine.Divergence` read / history — the old `rsi2.engine.RSI` class (Cardwell zones, gaps) is not read.

`cfg["display_finder"] = "validity"` keeps the R1a display finder (`facts.validity` via `decision3.levels.display_bands` /
`trendlines2.two_touch.display_lines`) for the `areas` / `lines` / `confluence` sections only — the legacy what-if the R1a golden test
pins. The dossier is not wired into the live Vision card yet.

## Inputs and the no-look-ahead rule

`bars_by_tf` = spot bars `{"15M": required, "5M": LTF CHoCH, "1m": context / gaps, "1H": optional (default: complete NSE hours
09:15 … 15:15–15:30 from the 15M bars via `opportunity_engine.sessions.resample_nse`, `bar_closed` only), "D": optional daily (gap ATR /
trend)}`; `fut_bars_by_tf = {"5M": FUT 5M bars with volume [+ contract / expiry]}`.

**Holdout guard first:** before any section runs, every input frame (spot all TFs and FUT) goes through `pivots.engine.guard` with
`instrument = symbol` (unknown / anonymised symbol ⇒ the strict NIFTY rule) — never the process-global current instrument. Holdout rows
anywhere ⇒ `HoldoutError` (raised, never NA). FUT rows are de-duplicated only on timestamp + contract / expiry (no such column ⇒ no
dedupe); sorts are stable.

Every frame is cut to the bars whose **close** time is ≤ `as_of` before any owner sees it (`as_of` default = close of the last 15M bar).
A running bar is never read. When `as_of` is more than one 15M bar after the last closed 15M bar, `asof_bar`, `structure` and `candles`
carry `stale_by_minutes` + `stale_reason` (the facts describe that older bar). `tests/test_facts_dossier.py` proves that cutting or changing the future bars does not change the dossier.

## Sections: concept → owner function actually called → output keys

Each section is `{"status": "OK" | "NA", "owner": ..., ...}`. NA always carries `"reason"` (owner failed, input missing); a failure
of the shared swings2 / legs2 build marks every section that needs it NA with that reason. The sealed-holdout guard is never turned
into NA (it raises).

| Section | Concept (KB) | Owner function(s) called | Output keys (besides status / owner) | NA when |
|---|---|---|---|---|
| `structure` | Swings / structure, degree-aware: trend, protected swing, BOS / CHoCH (K1) | `swings2.engine.build` (pivots DC engine) → `swings2.structure.all_structure`; per degree `swings2.engine.known` / `labels` / `pivot_json`, `swings2.structure.trend_of` | `degrees.D0…D4.{pivots, confirmed_pivots, warmup_done, pivot_trend}`; D1 / D2 also `state` (trend, range, lastH / lastL, strict, protected, weak, reversal stage) and `events` (BOS, CHoCH, sweep, range_start / range_break, LH, reversal, always_in_flip, failed_gap_break) since the 15M lookback start; `events_from` | engine fails; no confirmed pivot at any degree (σ needs 20 complete sessions) |
| `legs` | Legs: impulse vs correction (K2, K3) | `reader2.reader.read` on 15M (low = 5M) and on 1H (low = 15M) — **injected** as `cfg["legs_reader"]` (reader2 is research-only; facts never imports it) | `by_tf.<tf>.legs[]` (degree, dir, start / end bar-ts-price, bars, label impulse / correction / uncertain, structure_family, reason, provisional, known_at), `selfcheck_passes`, `selfcheck_log`, `reader2_trend` (evidence only) | no reader injected (default; reason names the reader2 gate); no frame |
| `areas` | Areas: demand / supply, flipped, origin of a sharp move (method §3 Areas, layer 2) | `decision3.engine.V22` → `levels.snapshot` (all alive areas + K4 state) and `step1` / `step2` (trend side, armed areas with the line label) | `asof_bar`, `close`, `trend.{daily, used, weekly, resolution, trade_side, why}`, `armed[]` (area ids, nearest first), `areas[]` — each: id, tf, role, lo, hi, births, state (+ broken / far swing / flipped facts), tests, sweeps, flips, fresh, dist, confluence (+ `confluence_label`, "line (touch N)" when armed), trade_location, lineage, width, born_ts, armed, line_touch | the engine fails (reason) |
| `lines` | Lines (method §3 Lines, layer 4) | `decision3.trendline.swing_line` (both trade sides) + `reaction_touch` + `confluence_areas` | `lines[]` — side, p1 / p2 (bar, ts, price), slope_per_bar, touches (by reactions), touch_points (ts per reaction), value_at_asof, reaction_touch (bar, ts, price, touch_no, trade_location), areas_met; `rule` | the engine fails |
| `confluence` | A line or a Daily / Weekly area meeting the area (labels the area itself) | `levels.snapshot` (HTF label) + `trendline.confluence_areas` (line label) | `items[]` (id, tf, role, lo, hi, state, confluence_label) | the engine fails |
| `patterns` | Chart / correction patterns (K11) | `patterns2.fold2.Fold` D2 and D1 (parent D2) on `legs2.measure2.build` + `legs2.ik2.Tracker` | `D2` / `D1`: phase, state, impulse (dir, origin, end), valid_hypotheses, pref / alt (family, kind, sub, waves, points, state, flags, c_eq_a, lines_geom, range_like), final_flag_risk, position_in_parent | swings2 / legs2 build fails |
| `candles` | Reversal form at the last bar; the zone study / commitment at every visit in progress (method §3, layer 3) | `decision3.method.candle_read`, `reversal_form` (both sides, last bar); per visit: `V22.visit` (structure) + `V22._confirm` + `method.zone_study` | `last_bar` (OHLC + read), `reversal_form_at_last_bar.{up, down}`, `area_studies[]` (band_tf, band, area_id, role, state, reaction_side, armed, confluence_label, arrival, approach_from, visit_prev_end, bars_in_study, zone_study, handover.{present, form, seen_ts, cancelled}, absorption, commitment.{present, reason, read, form, …, volume_measure, vol_gaps, data_problem}) — `area_studies` None + `area_studies_reason` when the engine fails; `volume_source`, `stale_*` | owner fails |
| `volume` | FUT volume, trend side vs counter side (K10) | `opportunity_engine.volume.attach_futures_volume` (FUT 5M ⇒ 09:15-anchored 15M sums) | `coverage`, `last_bar.volume` (+ `reason` when None), `session.{up_bars, down_bars}` (bars / mean / sum) + per-bar list (+ `reason` when None), `lookback.{up_bars, down_bars}`, `incomplete_bars[]` (15M bars with fewer FUT 5M children than 5M slots ⇒ volume NA), `multi_contract_bars[]` | **FUT 5M missing, or no FUT row matches a spot bar** |
| `ltf_choch` | LTF change of character (method §3, c1 at 5M) | `decision3.method.ltf_choch` as read by `V22._confirm` at every visit in progress | `visits[]` (band_tf, band, area_id, role, reaction_side, context_from — the pullback's impulse end as the engine reads it, else the arrival — study_from / study_to, done, code, low / lh / hl, sweep, at, close, line) | 5M spot missing; the engine fails |
| `liquidity` | Liquidity pools / sweeps / traps (K5) | `decision3.liquidity.pools`, `sweeps_and_traps` (adapter: `decision3.levels.Levels` on the swings2 result) | `pools[]` (price, side, src swing / equal / PDH / PDL / PWH / PWL), `sweeps[]`, `traps[]`, `lookback_bars` | swings2 build fails |
| `gaps` | Opening gap (K13) | `vision.gap_context.build` | the owner's dict: pdc / pdh / pdl, open, gap, gap_atr, class G0–G5, location, trend, fill_pct, pdc_acceptance, behaviour, old_gaps … | 1m missing; no complete previous session |
| `context` | PDH / PDL / PDC, week H-L, opening range (K8, K14) | `vision.context.prev_day`, `prev_week`, `opening` | `prev_day`, `prev_week`, `opening`, `minutes_since_open`, `missing` (a reason per missing sub-part prev_day / prev_week / opening; VIX, FII / DII, global cues: no owner function yet) | 1m missing, or all of prev_day / prev_week / opening missing (one missing part ⇒ OK + `missing.<part>`) |
| `divergence` | RSI divergence (method §3, layer 5) | `rsi2.engine.Divergence` (the engine's own object) via `V22.rsi_divergence` | `rsi15_at_asof`, `rsi_warmup`, `known_count`, `last[]` (degree, side, type, status, bars, price_rel, L1 / L2 time-price-rsi, known_ts), `latest[]` (statements per degree and side), `at_visits[]` (per visit: found, degree, pushes, zone_degree, divergences, statements / na) | the engine fails; rsi2 fails |

Dropped everywhere (not facts): `grade`, `score(s)`, `vote(s)`, `conviction`, `decision`, `confidence`, `verdict`, `ratio`,
`strength`, `completion`, `momentum` (`facts.dossier.NOT_FACTS`), and the "· grade X" tail of the decision3 commitment text.

"Visit in progress" (candles / ltf_choch / divergence) = an alive trade-location area of the engine (not BROKEN / DEAD, not a
context-only Weekly band) whose visit by structure (`V22.visit`, method §3: begins when price enters, ends only by a swing built away,
a break / flip or a failed commitment closing outside — never by time or a bar count) is in progress at `as_of`; arrival = the visit's
start. The reaction side is the area's role (support ⇒ up, resistance ⇒ down) — a fact about the area, not a trade direction.

### The dossier follows the 5M trigger (DECISIONS 37 / 51; L6-O7 / O8 / O9 / O12)

With decision3 `trigger_tf = 5M` (the default) the dossier reads exactly what the engine read at the 5M decision, on the same V22 —
reused, never re-derived on the last closed 15M bar. `trigger_tf = 15M` (what-if) = the table above, byte for byte (pinned:
`tests/fixtures/dossier_15m_pin.json.gz`).

| Section (5M) | What the engine read (function called) | Output keys |
|---|---|---|
| `trigger` (new) | `V22.decide5(j)` — j = the last 5M candle closed at `as_of`, k = the last 15M bar closed at that 5M close | `candle` (bar5, ts, bar_end, OHLC), `context_bar`, `trend_used`, `watch_list`, `armed[]` (every object the models read: areas, range edges, E4 (b) objects, each model's state), `entries[]` (the fired entries as the engine wrote them — the stored payload's source), `why` |
| `areas` / `lines` / `confluence` | as above, at the decision's 15M bar k | as above |
| `candles.area_studies` | per visit in progress at the 5M decision: `entry_models5.Reader5.visit5` (a visit may start on a 5M candle inside the 15M bar in progress), `confirm5` (required set on the visit's 5M candles), `c0` (commitment), `absorbing`, `refined(k)`, the engine's armed record | `visit_id`, `arrival.{tf, bar5, ts5, ts (15M bin = the visit id), bin15_in_progress}`, `approach_5m`, `refined_base`, `zone_study` (5M, the confirmation's a2 window), `handover`, `absorption`, `commitment`, `required_set.{read, handover, commitment, ltf_choch, wait}`, `models`, `disarmed`, `entries[]` |
| `ltf_choch.visits` | the 5M CHoCH inside `confirm5` | `visit_id`, `study_from` (the visit's first 5M candle) / `study_to` (the 5M close), CHoCH facts |
| `divergence.at_visits` | `V22.rsi_divergence(k, d, arm15, tf, move_from)` as the evidence list reads it | + `visit_id`, `arm_ts` |
| `e4b_objects` (new) | `Reader.broken_objects(k, d)` + `Reader5.broken5` (revisit `touch_visit5`, E4 state) + `confirm5` | `objects[]` — broken area (band, broken_at, lifecycle) / broken line (p1, p2, slope, broken_at, break_known_at, value at the 5M decision, lifecycle), `revisit` (visit id, 5M start, models) or `revisit_why`, `required_set`, `entries[]` |
| `liquidity` | `liquidity.pools` / `sweeps_and_traps` on the engine's own V22 levels (built WITH the Daily frame), at k; per visit the evidence window (start = the visit's 15M arrival) | `pools`, `sweeps`, `traps`, `window_from`, `at_visits[]`, `daily_frame.{daily_bars, prior_levels}` |

No 5M spot bars (and no 1m to build them) ⇒ `trigger` / `e4b_objects` NA and `area_studies` None with the reason — never a 15M re-read.

## Open questions (R1b; for Abhi — not decided here)

- **Legs owner vs reader2 gate:** design §3 names `reader2` the legs owner, but reader2 is research-only until its gallery gate passes
  and Abhi approves (`docs/READER2_DESIGN.md`, `tests/test_reader2_boundary.py` forbids any production import). The dossier therefore
  never imports reader2: `legs` is NA by default and a research / test caller injects `reader2.reader.read` as `cfg["legs_reader"]`.

- **Trend has more than one computation in the dossier inputs:** `structure` (swings2 D1 / D2 fold, the owner) vs `legs.reader2_trend`
  (reader2's leg-trend) vs `gaps.trend` (vision.gap_context SMA-10 trend on daily closes); decision3's own Daily Dow is not in the dossier.
  On the R1a real-data fixture at the 9 Oct close: swings2 D1 DOWN, D2 RANGE, D3 DOWN; reader2 15M "uncertain".
- **PDH / PDL / PWH / PWL twice:** `context` (vision.context, from 1m, ISO weeks) and `liquidity.pools` (decision3.liquidity, from 15M,
  W-FRI weeks). They matched on the synthetic fixture; §3 says context owns them.
- **FUT contract roll (decided, Abhi):** the dossier keeps only the near-month contract (`opportunity_engine.volume.near_month_rows`,
  expiry ≥ the day, nearest), on roll days too; volumes of two contracts are never summed. No contract / expiry columns ⇒ rows used as one series.
- **No owner yet:** VIX, FII / DII, global cues (context `missing`); K11 patterns beyond patterns2's correction family (box / flag /
  double top inside an area come only from `decision3.method.zone_pattern` inside `candles.area_studies`).
- **swings2 warm-up:** D2 (decision3's level degree) needs 20 sessions for σ plus 10 warm-up sessions; on shorter history `structure` is
  NA or D2 "unknown" while decision3's Daily Dow (from daily bars) already has a trend.
- Some owner labels are Marathi (e.g. patterns2 `phase`, `sub`); translated only when the owner is merged.
- **Owner chain into a frozen package:** `swings2.engine.sigma_1h`, `swings2.structure._h1` and `rsi2.engine` import `pivots.charts`, which
  imports `backtest_review.charts` ⇒ `vision_led.charts` (plotting helpers). facts' own code imports no chart module (the 1H builder uses
  `opportunity_engine.sessions`), and a test pins that no other frozen module is loaded; removing this chain needs an owner change
  (merge step), not R1b.
