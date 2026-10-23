Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# Entry trigger on 5M for every model — report first (DECISIONS 37; INBOX "entry trigger on 5M for every model"; README row 36)

## सारांश (Abhi साठी, मराठी)
- 5M trigger साठी नवीन Upstox fetch लागत नाही: live feed आधीच दर cycle ला 5M spot आणि FUT 5M आणतो. बदल: engine दर 5M close ला चालेल, आणि
  प्रत्येक model चं trigger 5M candle वर वाचलं जाईल; 15M / 1H / D फक्त बंद झालेले bars.
- FUT 5M volume फक्त 30 Sep पासून आहे ⇒ 13 BANKNIFTY groups पैकी फक्त शेवटचा (07–21 Oct) पूर्ण testable; बाकी reading-only (E2 नाही).
- सगळ्यात मोठा धोका: एखादा 5M cycle चुकला तर तो signal हरवतो ⇒ "catch-up" लागेल. Vision सध्या 15M bar बंद होण्याची वाट पाहतो ⇒ 5M
  trigger साठी तेही बदलायला हवं. Compute 3–27× वाढू शकतो ⇒ deploy आधी लांब visits वर मोजायचं.
- E3 कदाचित कडक होईल: 5M CHoCH candle स्वतः refined base मध्ये trade व्हायला हवी (नियम सैल करणार नाही).
- `trigger_tf = 15M` (what-if) = आजचंच वागणं, byte-identical (test ने pin).
- Build: DECISIONS 38–41 (live E4 (b) fix) चा PR आधी merge, मग हा PR.

## 1. How the engine runs today (code read)
- `decision3/engine.py` V22: 15M swings (`swings2.engine.build`), Daily / Weekly fold, `Levels` (areas, K4 events, `_known0` finest pivots with
  `confirm_bar`); LTF = given 5M (`method.ltf_frame`) or 5M from 1m, else E3 fail-closed; FUT: `legs2.volume.bar_volume` sums near-month FUT 5M
  into 15M bins (`<3/3` children ⇒ NaN + reason). `decide(t)` per closed 15M bar: step 1 Daily side at `bar_end[t]`, step 2 `act`,
  `_models_eval` → `EM.read`; model C only when ON. `visit` / `_visit_structure` (start = first 15M bar trading into the band; end only by a
  `_known0` away swing confirmed by t). `handover_episode`, `vol_view`, `vol_gaps` on 15M arrays; `entry_window` on the bar start.
- `decision3/entry_models.py` Reader: visit → disarm (came from the trade side, K4 broken / dead inside the visit); `w0 = side_since`; once
  per visit = stateless scan `for u in range(w0, t+1)` on 15M bars (u < t ⇒ `fired_earlier`). Trigger checks on the 15M candle: `h2_block`,
  `outside` (traded_inside), `off_base`, `beyond`, `base_broken`. E2 = `M.commitment` + `handover_episode` + `absorbing` + FUT data problem;
  E3 = `M.ltf_choch(V.ltf, …, bar_end[u], lvl)` (5M CHoCH only looked at on the 15M close); E4a = 15M sweep bar + next `_known0` swing failing
  inside the sweep extreme; E4b = K4-broken areas + broken lines (`channel_lines` / parallels, `break_known_at`, `broken_back_at`), revisit =
  `touch_visit`, trigger = `M.reversal_form` on 15M + `retest_ok`. Invalidation structural (E1 base far edge; E2 / E3 farther of visit
  extreme and base far edge; E4a sweep extreme; E4b retest extreme). Clusters key `visit_id = lid@<15M visit start>`.
- Live: cron `1,16,31,46 4-9 * * 1-5` UTC (`scripts/install_engine_schedule.sh`, tag `# one-bot-engine`) → `engine_signal_run.py --engine
  decision3` → `ES.run3` → `engine3_live.compute` (closed 15M 90 d, Daily, 5M spot 10 d, FUT 5M 45 d front-month) → `V22.decide(last)` →
  `row_from_v22` (`bar_ts` = 15M `bar_end`) → SQLite `engine_signals`. `engine_service.timer` (every minute) = exits monitor + paper watch,
  unchanged. Consumer: SRv2 cron → `paper.engine_entry.process` → `ES.pending_entries` (freshness `engine_max_age_min`, idempotency
  `engine_entry_consumed`, `entry_cutoff`, `max_hits_per_zone`) → gate (`"15M"`, `signal_ts = bar_ts`).
- Card / Vision: `compact_entries` (trigger_ts = 15M start, `entry_ref` = 15M close); `vision/engine_card.py` (15M setup + HTF panels, trigger
  box from `trigger_index`, "setup timeframe 15M"); `engine_audit.apply_facts` sets `trigger_in_base` unclear when the bar is not closed;
  `vision/worker.bar_wait` / `context.signal_bar(setup_tf)` wait for the 15M bar.
- Baseline timing (BANKNIFTY, 15 Oct, live-size): V22 build 9.0 s; cold `decide(last)` 0.41 s (2 armed visits, one 22 × 15M bars).

## 2. What changes per model (`trigger_tf = 5M`) — j / u = 5M bars; k(j) = last 15M bar with bar_end ≤ bar_end5[j]
- **E1** first 5M candle of the visit trading into the refined base known at k(u); closes beyond the base far edge ⇒ no E1 this visit
  (DECISIONS 23); H2 on the 5M candle; invalidation = base far edge.
- **E2** `M.commitment` on 5M arrays (OHLC + raw FUT 5M volume per bar, exact bar-start join, NaN never 0); dominant = body > every other 5M
  candle of the visit; volume > average of approach-leg + visit opposite-side 5M candles; handover / sharp reversal / absorption on the visit's
  5M candles; FUT data problem counted on 5M bars; trades into the base, not beyond the invalidation; invalidation unchanged.
- **E3** same `ltf_choch` with `t_end = end5[u]`; the trigger = the 5M candle whose close makes the CHoCH, must trade into the refined base;
  absorption gate on 5M.
- **E4 (a)** sweep = a 5M candle beyond the far edge / visit extreme closing back inside (K4 sweep events still count); push = the first
  confirmed 5M swing (existing LTF swing definition) failing inside the sweep extreme; invalidation = sweep extreme.
- **E4 (b)** objects known at k(u) (`break_known_at`, `broken_back_at`, DEAD); touch + `reversal_form` on 5M candles; approach side per
  DECISIONS 38; revisit ends by a 15M away swing; a line value at a 5M candle needs a float position (new helper; the 15M path unchanged);
  invalidation = retest extreme.
- **Common**: traded_inside / h2_block / beyond on the 5M trigger candle; came_from_trade_side, K4 disarm, side_since, clusters from the 15M
  state at k (same visit_id ⇒ idempotency and `max_hits_per_zone` unchanged); `entry_window` on the 5M bar start. Payload adds `trigger_tf`,
  5M `trigger_ts` / `trigger_bar_end`, `context_bar_ts`, trigger candle OHLC, CHoCH / sweep facts; `entry_ref` = the 5M close.
- **Code shape** (extend, never rewrite approved layers): setting `trigger_tf` in DEFAULTS + REGISTER ("5M" default, "5M / 15M (what-if)",
  Abhi rule, DECISIONS 37), `engine3_trigger_tf` in METHOD_SWITCHES (`5m` / `15m`); new `decision3/trigger_frame.py` (5M arrays, `k_of` /
  `kids`, FUT 5M NA reasons); `Reader5` overriding only candle-level helpers + the scan with k(u); `V22.decide5(j)`; today's `decide(t)` and
  `Reader` untouched.

## 3. No look-ahead
At a 5M close T: 15M bars only with bar_end ≤ T (a 15M bar in progress is never read; its 5M children ≤ j only as 5M candles); pivots /
Levels / K4 / refined base by confirm_bar ≤ k; 1m up to the last closed 15M end; Daily `step1(k)`; visit `V.visit(k)` + the 5M candles of the
in-progress 15M bar, end only by 15M structure ≤ k(u); 5M spot / FUT end5 ≤ T; CHoCH `t_end = end5[u]`. Once per visit stays stateless (scan
the visit's 5M candles, each judged with k(u)). Mandatory test: `decide5(j)` on full data = on data cut at T, for random j.

## 4. FUT 5M availability
Code: `opportunity_engine/volume.py` (exact join, NA), `legs2/volume.py` (near month, expiry, rollover). Live: front-month FUT 5M 45 days +
forward collector from 30 Sep; no Upstox Plus (DECISIONS 33). trade-data: FUT 5M complete for 14 sessions 2026-09-30 … 2026-10-21.

| group | status |
|---|---|
| 1–11 (13 Apr … 21 Sep) | not testable — FUT volume missing on every session |
| 12 (22 Sep … 06 Oct) | not testable — FUT missing 22–29 Sep |
| 13 (07 … 21 Oct) | **testable** |

## 5. Live loop
Cron: replace `# one-bot-engine` with an every-minute line in session hours (`* 3-10 * * 1-5` UTC, flock); exits at once when the last closed
5M bar (or 15M in 15M mode) is stored or outside the window; `--revert` restores today's line. Same `build_inputs` (no new endpoint); new check
that the last closed 5M spot + FUT bar exist. Upstox calls 4 / 15 min → 4 / 5 min per symbol. `decide5(last)`; `bar_ts` = 5M bar_end;
`expected_bar_end` / `run3` trigger-tf aware. **Catch-up**: the next good cycle decides every unstored closed 5M bar of the session, in order
(else a missed trigger bar is lost as `fired_earlier`). `paper.engine_entry` unchanged + tag `entry_trigger_tf`.

## 6. Card / Vision
A 5M trigger panel beside the 15M setup + 1H panels: the visit's 5M candles to the trigger, refined base strong, context area faint, "T 5M"
box, invalidation dashed, FUT 5M pane; E3 CHoCH line, E4a sweep extreme + failed push, E4b line value per 5M candle; P8 / `chart_max_lines`.
15M panel `trigger_index` = the 15M bar containing the 5M trigger. Text: "Trigger 5M: <model> candle …, traded into the refined base ✓, close
<x>; context = last closed 15M <ts>". Vision `bar_wait` / `signal_bar` / `apply_facts` on the trigger tf; prompt / checklist "areas 1H / D,
refined base 15M, trigger 5M"; human_confirm, display only.

## 7. Byte-identical 15M what-if
`trigger_tf = 15M` branches to today's code (no 5M frame built; cron guard skips minutes without a new 15M bar). Tests: unit parity, replay
parity (13 groups at 15M vs main's runs, every row JSON equal), switch test.

## 8. Replay plan
`walk5.py` (from the checks_e4 runner): every closed 5M bar, data checks at bar_end5 + 1 min, `trigger_tf` via settings, outcomes on 5M bars for
both variants, 5M inset in the chart pack; outputs only to trade-data. Order: `group_data_status`; group 13 live mode both variants; groups
1–12 reading mode (E1 / E3 / E4, "E2 — FUT volume missing", "without volume evidence"); 15M parity; `validate_report`.
Per-entry table (matched by visit_id + model; unmatched listed): model, side, area, refined base, visit_id, 15M trigger (ts, entry_ref), 5M
trigger (ts, entry_ref), entry earlier by (5M candles), price difference (signed in trade direction), invalidation 15M / 5M + rule, distance to
invalidation 15M / 5M, outcome 15M / 5M (next area first / invalidation first / open), MFE / MAE. Per-model summary: entries, matched,
5M-only, 15M-only, medians (earlier by, price difference, distance), outcomes, re-entries; running total, data gaps, missed moves, worst
losers with charts, E3s dropped by traded_inside on the 5M CHoCH candle.

## 9. Risks
1. Lost signal after a missed cycle ⇒ catch-up + every-minute guard. 2. Vision 15M timing ⇒ must change with the build. 3. Compute (≈3× bars;
`handover_episode` quadratic per call) on a 1 GB droplet ⇒ prefix memo (pinned by 15M parity) + timing on the longest visits. 4. Look-ahead ⇒
full-vs-cut test; the float line helper never reads a future 15M index. 5. E3 stricter (no relaxation without Abhi). 6. More / noisier 5M
triggers, smaller distance to invalidation ⇒ replay; never tune. 7. Thin evidence: one testable group. 8. 5M history window
(`engine3_ltf_days` = 10). 9. Conflict with the DECISIONS 38–41 PR ⇒ build after it. 10. FUT rollover gaps ⇒ existing data problem.
11. 15M-cadence assumptions (`expected_bar_end`, token alerts, `models_summary`). 12. Out of scope, logged: `zone_entries_today` counts
`max_hits_per_zone` by day, CLAUDE.md says per visited area.

## 10. Build order (one PR, after the DECISIONS 38–41 PR)
1 `trigger_tf` setting + switch + parity tests first. 2 `trigger_frame.py` + tests (FUT join, NaN never 0, rollover, no look-ahead).
3 `Reader5` per model (E1 → E2 → E3 → E4a → E4b) + tests (traded_inside / H2 / beyond on 5M, sweep back inside, once per visit across 5M steps,
visit inside the in-progress 15M bar, cluster count). 4 `decide5` + payload + model C wiring + full-vs-cut test. 5 performance memo + timing.
6 live (engine3_live, engine_signal, catch-up, schedule script + `--revert`, engine_entry tag) with fake feeds / crontab tests. 7 card /
Vision (5M panel, text, prompt, bar_wait / apply_facts on the trigger tf) + `validate_chart` tests. 8 docs (method §2 d / e and §3 line citing
DECISIONS 37, REGISTER, OPEN_QUESTIONS, STABLE note). 9 replay + report per REPORT_STANDARD. 10 self-review, independent review, green CI,
merge; one VPS block after the close with `--revert`, PAPER only.

## 11. Open questions — provisional defaults (checked against DECISIONS 1–41, CLAUDE.md, method §2 / §3)
- Q1 a visit may start on a 5M candle inside an in-progress 15M bar; visit_id = area@(the 15M bar containing it); end only by 15M structure.
- Q2 the 5M visit begins at the first 5M child trading into the area.
- Q3 E1 = the first 5M touch of the base; that candle closing beyond the base far edge ⇒ no E1 this visit.
- Q4 E2 "5M slots" = the 5M bars themselves; dominant over every other 5M candle of the visit; volume above approach + opposite-side average;
  slot baseline stays a what-if.
- Q5 handover / absorption on the visit's 5M candles (gating E2 / E3 only); method §2 d gets a line citing DECISIONS 37.
- Q6 E3 trigger = the 5M CHoCH close candle, must trade into the base; not relaxed.
- Q7 E4a push = the existing LTF 5M swing definition, confirmed; K4 sweep events still count.
- Q8 E4b objects as known at k(u); line value at the 5M candle's float position; revisit ends by a 15M away swing; approach side DECISIONS 38.
- Q9 required set read on 5M at the trigger; confirming pieces / zone read at 15M / 1H (k); evidence never blocks.
- Q10 model C follows `trigger_tf`; stays OFF.
- Q11 every-minute cron with a guard; entry-hours / store-window settings unchanged (note: with `engine_first_bar_end` 09:30 the 09:20 / 09:25
  5M closes are read but not stored).
- Q12 catch-up of unstored 5M closes; freshness stays `engine_max_age_min`.
- Q13 replay outcomes on 5M closes for both variants.
- Q14 entry time difference counted in 5M candles (timestamps only as identifiers).
- Q15 groups without FUT: one line each + reading-only E1 / E3 / E4 comparison "without volume evidence"; no regrouping.
- Q16 5M history window stays 10 days; a visit older than that ⇒ that area's 5M models wait with a data reason.
- Q17 the DECISIONS 38–41 fix merges first; the 5M PR builds on it.
- Q18 card keeps the 15M and 1H panels and adds the 5M trigger panel; display only.
