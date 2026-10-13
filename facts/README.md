# facts/ — the facts layer (design `docs/design/CHART_READER_AGENT.md` §3, build step R1)

One owner per concept; facts + evidence only (prices, bar times, counts) — never a vote, score, grade or trade decision.
No AI calls, no broker, no network.

- `validity.py` (R1a) — the one K6 line check and the one K4 band check used by every chart (`check_line`, `check_band`,
  `confluence`, `select_lines`, `select_bands`, `lookback`).
- `dossier.py` (R1b) — `build_dossier(symbol, bars_by_tf, fut_bars_by_tf=None, as_of=None, cfg=None)`: calls each owner below once
  and returns one JSON-safe dict `{"schema", "symbol", "as_of", "asof_bar", "inputs", "sections"}`.

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
| `areas` | Areas: demand / supply bands, flips, broken (K4, TA3b / TA4) | `decision3.levels.display_bands` (→ `facts.validity.check_band`), lookback per TF (`facts.validity.lookback`), 1H magnet count on 15M | `by_tf.<15M / 1H>.{asof_bar, close, mr, lookback_sessions, bands[]}` — each band: lo, hi, role, touches, touch_count, earlier_side_touches, established, breaks, flipped, broken, price_side, crossings_session, valid, reasons, defined_by | no frame |
| `lines` | Trendlines (K6, TA3) | `trendlines2.two_touch.display_lines` (→ `facts.validity.check_line`) | `by_tf.<15M / 1H>.{asof_bar, mr, lines[]}` — each line: side, anchor1 / anchor2, slope, touches, touch_count, established, valid_from, value_at_t, projected_zone (next 3rd-touch zone + path) | no frame |
| `confluence` | Band + line meeting (K4 + K6.4) | `facts.validity.confluence` over the shown bands × lines (all TF pairs) | `items[]` (band_tf, line_tf, role, offset, line_value, band, distance_mr, zone, line_anchors, band_touches) | no frame at all |
| `patterns` | Chart / correction patterns (K11) | `patterns2.fold2.Fold` D2 and D1 (parent D2) on `legs2.measure2.build` + `legs2.ik2.Tracker` | `D2` / `D1`: phase, state, impulse (dir, origin, end), valid_hypotheses, pref / alt (family, kind, sub, waves, points, state, flags, c_eq_a, lines_geom, range_like), final_flag_risk, position_in_parent | swings2 / legs2 build fails |
| `candles` | K9: reversal form, commitment, zone study (handover / absorption) | `decision3.method.candle_read`, `reversal_form` (both sides, last bar), and per touched valid band `zone_study` + `commitment` | `last_bar` (OHLC + read), `reversal_form_at_last_bar.{up, down}`, `area_studies[]` (band, role, reaction_side, arrival, bars_in_study, zone_study, commitment.present / reason / form / merged / beyond_extreme / body_pct / body_mult / vol_mult), `volume_source` ("FUT volume missing" vs "FUT attach failed: <error>"), `stale_*` | owner fails |
| `volume` | FUT volume, trend side vs counter side (K10) | `opportunity_engine.volume.attach_futures_volume` (FUT 5M ⇒ 09:15-anchored 15M sums) | `coverage`, `last_bar.volume` (+ `reason` when None), `session.{up_bars, down_bars}` (bars / mean / sum) + per-bar list (+ `reason` when None), `lookback.{up_bars, down_bars}`, `incomplete_bars[]` (15M bars with fewer FUT 5M children than 5M slots ⇒ volume NA), `multi_contract_bars[]` | **FUT 5M missing, or no FUT row matches a spot bar** |
| `ltf_choch` | LTF structure / CHoCH (K1 at 5M) | `decision3.method.ltf_frame` + `decision3.method.ltf_choch` per touched valid band | `visits[]` (band, role, reaction_side, context_from, `context_note` when the context falls back to the arrival bar, study_from / study_to, done, code, low / lh / hl, sweep, at, close, line) | 5M spot missing |
| `liquidity` | Liquidity pools / sweeps / traps (K5) | `decision3.liquidity.pools`, `sweeps_and_traps` (adapter: `decision3.levels.Levels` on the swings2 result) | `pools[]` (price, side, src swing / equal / PDH / PDL / PWH / PWL), `sweeps[]`, `traps[]`, `lookback_bars` | swings2 build fails |
| `gaps` | Opening gap (K13) | `vision.gap_context.build` | the owner's dict: pdc / pdh / pdl, open, gap, gap_atr, class G0–G5, location, trend, fill_pct, pdc_acceptance, behaviour, old_gaps … | 1m missing; no complete previous session |
| `context` | PDH / PDL / PDC, week H-L, opening range (K8, K14) | `vision.context.prev_day`, `prev_week`, `opening` | `prev_day`, `prev_week`, `opening`, `minutes_since_open`, `missing` (a reason per missing sub-part prev_day / prev_week / opening; VIX, FII / DII, global cues: no owner function yet) | 1m missing, or all of prev_day / prev_week / opening missing (one missing part ⇒ OK + `missing.<part>`) |
| `divergence` | RSI divergence only (K10) | `rsi2.engine.RSI(...).known` | `rsi15_at_asof`, `rsi_warmup`, `known_count`, `last[]` (type, degree, L1 / L2 pivots, rsi1 / rsi2, gap, known_bar, line_clear, price_clear) | swings2 / legs2 build fails |

Dropped everywhere (not facts): `grade`, `score(s)`, `vote(s)`, `conviction`, `decision`, `confidence`, `verdict`, `ratio`,
`strength`, `completion`, `momentum` (`facts.dossier.NOT_FACTS`), and the "· grade X" tail of the decision3 commitment text.

"Touched valid band" (candles / ltf_choch) = a valid band from the `areas` section whose price range a 15M bar touched within decision3
`touch_window_bars` of `as_of`; arrival = the first bar of that touch group (decision3's own "in / at the area" rule). The reaction side
is the band's role (support ⇒ up, resistance ⇒ down) — a fact about the band, not a trade direction.

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
