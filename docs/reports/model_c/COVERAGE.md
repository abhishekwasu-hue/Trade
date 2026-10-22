# Model C (counter-trend C leg): coverage report (T-3, step 1)

Order: handover pack T-3 and Appendix A (INBOX; DECISIONS item 32). This is step 1 of the order of work: what the code already gives
and the exact gaps. No engine code changes in this step. Base: `claude/hopeful-gates-hf186c` @ f25f04d.

Read first: CLAUDE.md, docs/owner-orders/ (README, INBOX, DECISIONS), docs/reader/REPORT_STANDARD.md,
docs/knowledge/CHART_READER_METHOD.md, docs/knowledge/pa_standard/.

Words used below: "Daily DOWN" means the Daily reader's `DState.trend == "DOWN"`. Everything mirrors for Daily UP. d = +1 is the minor
(UP) direction, a bull put. O is the 1H swing low where the counter-move starts. A runs from O to HA, a 1H swing high, and B is the
pullback from HA.

## 0. Summary

- **Already there.** Every piece model C needs is already a concept in the method, so model C adds no new concept. The pieces are the
  Daily DState, the 1H swings and their BOS / CHoCH events, the leg-nature comparison, the K4 close-and-swing-beyond break, the 1H
  areas with their states, the refined base, E1–E4 (including E4 (a) and E4 (b)), the channel lines with the K6.5 break, the entry
  pipeline and the per-model dashboard switch.
- **What is missing** is one thin **model-C reader** with five jobs:
  1. read the C cycle (O / A / HA / B) at bar t;
  2. choose the C areas and C objects;
  3. run the existing `entry_models.Reader` in direction +1 while the Daily side is DOWN;
  4. label the entries "C · Ex" with their sub-model;
  5. carry the context for the card and the separate statistics.
  It also needs the settings and switches, a Vision audit that knows about model C, and the card text.
- **The main code obstacle.** `entry_models.Reader` decides "the trade side since when" through `V22.step1`, which is the Daily side.
  For a support area while the Daily is DOWN this returns 0, so the models never arm. Model C needs an injected side function. This
  is the one change inside `entry_models.py`. When the switch is OFF it is never used.
- **Conflict to record.** Method P4 ("never a counter-trend entry") and the Vision engine audit's `trend_side` item contradict model C.
  DECISIONS item 32 is Abhi's own later order, so it wins. At build time the method doc §8 and the audit prompt must name model C.

## 1. Item by item: what exists, where, and the gap

### C-0 Switch
- **Exists**
  - Engine side: `decision3/settings.py` DEFAULTS / REGISTER `entry_models_on` (replays / what-if subset of E1–E4).
  - Live signal switch per model: `paper/engine_entry.py:model_on` reads the dashboard `engine3_model_eN_on`, default ON.
  - Dashboard ⇒ V22 mapping: `engine3_live.py:METHOD_SWITCHES` / `method_switches`.
  - Statistics per model: `paper/engine_entry.py:model_tag` ("ENGINE_E2" on `live_trades.entry_reason_tag`) and `models_summary`
    / `models_summary_text`.
- **Gap**
  - Engine setting `model_c` = `off` (default) / `on`. When it is off, `V22.decide` never calls the model-C reader, so rows stay
    byte-identical to today.
  - Dashboard `engine3_model_c_on`, default **False**, the opposite of `MODEL_DEFAULT_ON` for E1–E4. It sets V22 `model_c` and is
    also the live signal switch.
  - Sub-switches `engine3_model_c_a_on` … `engine3_model_c_f_on`, default False. Engine counterpart: `model_c_subs`, a subset of
    a…f used for replays / what-ifs, like `entry_models_on`.
  - Separate statistics: tag the position "ENGINE_C_E2" (and so on). `models_summary` must key on the family as well as the model.
  - All of these are dashboard settings in REGISTER. None of them is a number.

### C-1 Context (Daily DOWN; Weekly; DState)
- **Exists**
  - `decision3/daily.py:DState` (phase, counter, corr_label, wave_a, protected, parent, imp_end, rev), read with `daily.state_at`.
  - `daily.describe` gives the one-line story.
  - Weekly: `engine.V22.step1` (`wk = DD.state_at(self.weekly, …)`) and `mtf_state._tf_state(V, t, "W")`.
  - The decision row already carries daily_trend, daily_phase, corr_label, weekly_trend and wave_context (`V22.decide`).
- **Gap**
  - Context only: store `{daily: trend / phase / counter / corr_label / wave_a / protected, weekly: trend}` on each C entry.
  - "Daily same-degree correction in leg b" = `corr_label == "b"` with `counter in ("candidate", "correction")`, as a context line
    only.
  - Model C reads `DState.trend` itself, not step1's `ctx["trend"]`. step1 turns the trend to NEUTRAL when `st.rev` is set, and uses a
    Weekly fallback when the Daily is NEUTRAL (open question Q1).

### C-2 Origin O / C-3 Wave A (1H CHoCH, nature, HA)
- **1H swings exist:** `mtf_state.swings(V, t, "1H")`, the swings2 degree `level_degree` (D2) in the 1H index, confirmed by t.
  `mtf_state._swings2_known` and `_sp_swings2` give the same swings in the 15M index.
- **CHoCH exists:**
  - `mtf_state.dow_events` and `_swings2_events(V, d2)` give the events per data segment.
  - `mtf_state._events(V, t, "1H")` gives them known at t, with `bar15`.
  - A 1H DOWN structure ⇒ `{"type": "CHoCH", "dir": +1, "level": the protected lower high, "bar": the 15M close bar, "pivot_bar"}`.
    That is exactly "a close beyond the last 1H lower high".
  - `levels.Levels._bos` sees the same close: a close above the last confirmed D2 high, with origin = the last D2 low = O. It births
    a BOS-origin demand ("b") at the base A left (`Levels._base`, `bos_band`), and `method.Pullbacks` opens an UP impulse
    (origin = O, i_end = A's running high).
- **Leg nature exists:**
  - `decision3/legs_compare.py:leg_facts(F, i0, i1, dirn)` works on any bar range (body, overlap and FUT volume per bar; volume is NA
    when a bar has none).
  - `legs_compare.compare(leg, neighbours)` gives impulse / correction / mixed by comparison only.
  - The 1H frame is `mtf_state.frame(V, t, "1H")`.
  - (`daily_legs.compare_classify` is the Daily-degree equivalent, not needed here.)
- **Gap** (reading, no look-ahead: everything below at 15M bar t uses only swings with confirm_bar ≤ t and closes ≤ t):
  - **A start:** the newest 1H CHoCH up event (`dir = +1`) known at t, while Daily DOWN.
  - **O** = the lowest low between that CHoCH's protected high (`pivot_bar`) and the CHoCH bar. This is the DOWN structure's
    extreme swing (`ext` in `dow_events`, already confirmed when the CHoCH fires). If a lower low that is not yet confirmed lies after
    it, the lowest one is O (Q3).
  - **HA** = the first D2 swing high formed after the CHoCH bar, read only from its confirm bar on. Before that, A is running and
    there is no B and no entry.
  - **A nature:** `leg_facts(F1H, O.bar, HA.bar, +1)` compared with its neighbours: the Daily-side leg before O (from the protected
    high to O) and B so far. It is re-read every bar with the bars known by then, as `legs_compare` reads every running leg.
    `c_a_nature = impulse` (default) needs the verdict "impulse"; `any` is a what-if.
  - A 1H RANGE (C-13 equal swings) gives no CHoCH event, so it gives no model C.

### C-4 Wave B (corrective; death only by close + swing beyond O)
- **Exists**
  - The B leg nature: `legs_compare.leg_facts` / `compare` (B against A).
  - The K4 structural break: `levels.Levels._step_far_swing` with `_structural_break` and `_swing_beyond`, which is a close beyond
    and a swing of the finest structure (`Levels._known0`) formed beyond.
  - The same definition as a pure function on a line: `trendline._broken_at(C, pivs, kind, line, side, start, end)`, which is a close
    beyond plus a swing beyond with no close back in between (K6.5). Its "known at" is `trendline.break_known_at`.
  - A sweep that does not kill: `flip.structural` (a wick or a candle that closes back is not a structural swing).
- **Gap**
  - B in progress: from HA's confirm bar while no 15M close > HA.
  - B must read "correction" (`compare` of B so far against A); "mixed" or "NA" ⇒ the models wait.
  - **B death** reuses K4 / K6.5 unchanged: `trendline._broken_at(C, known0 confirmed ≤ t, "L", line = O constant, side = −1,
    HA.bar + 1, t)` is not None and the swing is known by t. Then the cycle is DEAD: no more model C entries, and the Daily-side
    trading goes on as now. One candle beyond O with no swing ⇒ still alive. The swing degree is the finest structure, as K4 (Q4).

### C-5 Entry = existing models, direction UP, at a 1H demand area built during A
- **Area builder + K4 exist:**
  - `levels.Levels` builds both roles whatever the Daily trend (`_births_at`: "a:D2" swings, Daily "a:D", liquidity "d"; `_run`:
    BOS "b"; flips "c").
  - States come from `Level.state_at` (ACTIVE / TESTED / BROKEN / FLIPPED / DEAD) and `Levels.snapshot`.
  - `Levels.active(t, "UP")` gives the supports below price, not BROKEN / DEAD, `trade_location` only (Z-1u).
- **Refined base exists:** `entry_models.Reader.refined` (RC2, the 15M turn inside the band), `rb_ok`, `off_base` (traded_inside).
- **E1–E4 exist:** `entry_models.Reader.area(t, lvl, d)` with e1 / e23 / e4 (E4 (a) via `Reader.sweep`).
  - Absorption without a handover blocks E2 / E3: `Reader.absorbing`.
  - Once per model per visit: the first-bar loop in `area`, plus `engine_signal.claim_entry` live.
  - The H2 breakout guards: `h2_block`, `came_from_trade_side`.
  - Visits: `V22.visit` / `_visit_structure`.
  - Confirmation: `V22._confirm`.
  - Data problem: `Reader.data_problem` / `V22.vol_gaps`.
  - Entry hours: `V22.entry_window`.
  - Every one of these is direction-generic (d = ±1).
- **Entry pipeline exists:**
  - `entry_models.read(V, t, trend, act)` ⇒ `clusters` (one signal per model per place).
  - Then `V22._models_eval` ⇒ `row["entries"]`.
  - Live: `engine_signal.pending_entries` ⇒ `paper/engine_entry._one_entry` (switch, cutoff, direction switch, one position at a
    time, `max_hits_per_zone`, Vision gate, PAPER open).
- **Gap 1, the side**
  - `Reader.trend_dir` / `side_since` call `V22.step1`. For d = +1 while Daily DOWN, `M._dir("DOWN", "support")` is 0, so w0 = t on
    every bar. E1 could never fire, and the "once per visit" scan would only look at bar t.
  - Smallest change: `Reader(V, side_fn=None)`. With `side_fn` set (model C), `trend_dir(u, role)` returns `side_fn(u)`: +1 while
    the C window is open at u, else 0. `read(V, t, trend, act, side_fn=None, …)` passes it through. Default None ⇒ today's code path.
- **Gap 2, the C areas**
  - Take `Levels.active(t, "UP")`, keep `tf == "1H"` and `state in (ACTIVE, TESTED)` (the order says fresh or tested, never broken,
    flipped or dead), and keep those whose base lies in A: O's own swing area, the CHoCH BOS-origin "b" area, and D2 / liquidity
    areas formed between O and HA.
  - `Level` keeps no base bar today. Add an additive `base_bar` field, set in `_births_at` (the pivot's bar) and `_run` (the `_base`
    1H candle). Until then, born_bar between O's confirm bar and HA's confirm bar, with the anchor between O and HA, is the
    stand-in (Q5).
- **Gap 3, the window gate:** `c_window` is checked inside `side_fn` (C-6).
- "Pullback only, never on a break of HA" is already covered: `h2_block` and `came_from_trade_side`, plus the window closing at the
  first close beyond HA.

### C-6 Window
- **Exists:** nothing model-specific.
- **Gap:** `side_fn(u)` returns +1 only while the cycle is alive (A complete, HA confirmed, B corrective, not dead) and:
  - `b_only` (default): no 15M close > HA from HA.bar + 1 up to u.
  - `b_and_ha_retest` (forced when C-e is ON): also from the first close beyond HA until the first return to HA ends (C-e).
  - `c_pullbacks` (what-if): C's own pullbacks after HA. The areas are those built during C, by the same rule as C-5.
  - Dashboard setting `c_window` (no number).

### C-7 End zone (context only)
- **Exists**
  - Daily / Weekly supply bands: `Levels.snapshot(t)` rows with `tf in ("D", "W")`, `role == "resistance"`, above HA ("a:D", "a:D-prior",
    "a:W-prior"; Weekly is context only by Z-1u).
  - The Daily protected origin: `DState.protected` (Daily DOWN ⇒ the protected lower high). If C closes beyond it and the Daily
    flips, `step1` turns UP and the normal engine takes over.
- **Gap**
  - Build the context dict: the first D / W resistance above HA, the protected origin, and the projection band
    `B_end + r × (HA − O)` for each r in `c_projections`.
  - Display only. It is drawn as a faint context band and never read by an entry, a gate or an exit.
  - Setting `c_projections` (a tuple of ratios) is a dashboard setting classified OPERATIONAL in
    `tests/test_method_no_numbers.py`, with a test that no entry path reads it (Q7).

### C-8 Evidence
- **Exists**
  - Hidden divergence: `decision3/rsi_hidden.py:read_hidden_divergence(V, t, d=+1)` (`_classic`: the pullback's low against the
    trend's previous higher low across the impulse, at `level_degree`). Its impulse is `V.pb.at(t, +1)`, which during B normally has
    origin = O and i_end = HA, so the pair is O against the B low.
  - Regular divergence at the C high: `V22.rsi_divergence` (inside the move into the supply), already in E1–E4's evidence list.
- **Gap**
  - `Pullbacks` cancels the up K on ONE close below O. B is still alive then (no swing), but `_classic` falls back to "the last two
    swing lows with an opposite swing between". That is normally still O and the B low. Step 2 checks this in a test. If they differ,
    add `read_hidden_divergence(…, pair=(O_bar, B_bar))`, an explicit frame.
  - Evidence only.

### C-9 Execution and safety (unchanged)
- **Exists**
  - `_one_entry` covers the PAPER-only check (`trading_mode` PAPER), `bullish_entry_enabled`, one open position (`has_open(symbol,
    source)`), `max_hits_per_zone` (`zone_full`, counted on the visited area), the Vision `human_confirm` gate (`vision.gate.entry_gate`)
    and the spread / naked settings (`open_paper`).
  - Direction +1 ⇒ BULLISH ⇒ a bull put, whatever the Daily trend.
- **Gap**
  - No new execution code.
  - **Vision audit:** `vision/engine_audit.py` ITEMS `trend_side` and its prompt ("never a counter-trend entry") would mark every
    model C card "disagree". Under DECISIONS 31 (audit against the engine's own reading), the engine card and facts must say "model C:
    Daily DOWN, 1H correction, B in progress" so that `trend_side` is judged against model C's rule. Vision stays advisory.

### C-10 Telegram text
- **Exists**
  - The card's model label: `engine_signal.model_label` ⇒ `paper/engine_entry.entry_gate_tags` (`entry_label`, `entry_invalidation`,
    `entry_evidence`, `entry_object`) ⇒ `vision/card_summary.model_label`.
  - `decision3/telegram_view.caption` is the review-run caption (Marathi). It is not the live card.
- **Gap**
  - Each C entry carries `family: "C"`, `sub_model: "C-a" … "C-e"`, `name: "C · E2 — Confirmation"`, `visit_id: "C:<area>@<start>"`
    (keeps the per-visit claim separate from the Daily side) and `model_c` context: the Daily / Weekly state, O / HA / B, the area
    lo–hi, the end zone, and "invalidated if B closes below O and a swing forms below O".
  - The payload `model` stays "E1"…"E4", so `engine_signal.entry_ok` is unchanged.
  - Add one text line built from it, for example: "Counter C leg — Daily DOWN, 1H correction: A complete, B pullback into the 1H demand
    area lo–hi, model E2." It goes in `entry_gate_tags` (tag `entry_story`) and is shown by `card_summary`.
  - Use `clusters(prefix="MC")` so C cluster ids do not clash with the existing "C…" ids.

### C-11 sub-models
- **C-a: B-end at an A demand area.** This is C-5 itself (E1–E4 at the C areas). No other code.
- **C-b: B channel break, then the retest.**
  - **Exists:** `trendline.channel_lines` (falling line of highs, K6.5 `broken`, `break_side "up"`) and `channels` (the parallel).
    `Reader.broken_objects` / `broken` already treat a broken-up line as an E4 (b) object for d = +1 (`touch_visit`, `rejection`,
    `retest_ok`, the RC4 revisit).
  - **Gap:**
    - `read()` only calls `broken` for the trend direction. Model C calls it with d = +1 and the C `side_fn`, and keeps only lines
      whose two anchors (or the base line of a parallel) lie inside B (HA.bar ≤ p1, p2 ≤ t).
    - `broken_objects` reads only the `level_degree` (1H) lines. A short B whose channel exists only on D1 (15M) is not an object
      (Q8).
- **C-c: expanded flat, B sweeps O.**
  - **Exists:** E4 (a) `Reader.sweep` at O's own area. O's swing area is the "a:D2" support whose far edge is O. The K4 "sweep" event
    of that area marks a close beyond with no swing beyond. A close plus a swing beyond O makes that area BROKEN, which is also B's
    death, so the two rules agree.
  - **Gap:** O's area must be in the C-area set (C-5). An E4 (a) whose sweep extreme lies below O is labelled C-c; any other E4 (a)
    at a C area is C-a.
- **C-d: B triangle edge, then the retest.**
  - **Exists:** `decision3/patterns_pa.py:read_patterns` / `retest_levels(V, t, d, tf)` (named, accepted boundaries;
    `_pullback_over`).
  - **Gap:**
    - `entry_models.PATTERN_HOOK` is still None in production; only tests set it. `retest_levels` rows (src, p0, p1, slope, role,
      break_dir, accepted_bar) do not have the hook's line shape (kind, p1 [bar, price], slope, broken, break_bar, break_side, id,
      degree).
    - Smallest change: a small adapter `patterns_pa.hook_lines(V, t, d)`, wired only by model C. The general T9 wiring of the hook for
      the Daily side stays a separate item.
    - Keep only patterns whose swings lie inside B.
- **C-e: HA flip retest.**
  - **Exists:** HA's own 1H supply ("a:D2" born at HA). When C closes above it with a swing above (K4), it is BROKEN with
    break_dir +1, an E4 (b) object (`broken_objects`). Once the far-side swing is reached it is FLIPPED (support) and enters
    `Levels.active(t, "UP")` as an ordinary area for E1–E4. Broken again ⇒ DEAD (T-2, `flip_dead_rule = broken_again`).
  - **Gap:**
    - The window becomes `b_and_ha_retest`.
    - Keep only the area(s) at HA, meaning the area born at HA's swing plus a BROKEN line lying on it, as one place (DECISIONS 28).
    - Only the first return: the first revisit after the break. A later revisit is not model C.
- **C-f: end of C, back to the Daily side.**
  - **Exists, no new code:**
    - `channel_lines` / `channels` draw C's rising channel on the 1H.
    - Its line of lows broken down (K6.5) is an E4 (b) object for d = −1 in today's `Reader.broken` (`break_side "down"`).
    - `Reader.channel_evidence` lists "rising channel broken down" as handover evidence for a bear call.
    - E1–E4 at the Daily / 1H supply are today's engine.
    - The 15M (D1) lines are evidence only (`channel_evidence` reads both degrees), not E4 (b) objects (Q8).
  - **Gap:** only the label. A Daily-side entry inside the C-7 end zone of a C cycle gets `sub_model: "C-f"` in its context, for
    statistics. Its switch never removes a normal entry (Q6).
- **Re-arm.** One cycle at a time: the newest 1H CHoCH up while Daily DOWN starts a new A. `dow_events` fires a new CHoCH up only after
  the 1H structure has turned DOWN again, which covers the X leg acting like B. A Daily flip to UP ends model C, because the normal
  engine trades UP.
- **Evidence** (B volume lower than A, the C start on rising volume, hidden divergence at the B low, regular divergence at the C end)
  comes from `legs_compare.leg_facts` volume per bar, `decision3/volume_read.py` (leg against leg) and `rsi_hidden` / `V22.rsi_divergence`.
  It is context lines only.

## 2. Smallest reuse-first design (for step 2)

1. **`decision3/model_c.py`** (new, about one screen; evidence and state only):
   - `cycle(V, t)` ⇒ `{alive, dead_at, O, CHoCH, HA, a_nature, b_nature, window_open, ha_broken_at}`. It is built from
     `mtf_state._events / _swings2_known`, `legs_compare.leg_facts / compare`, `trendline._broken_at` (B death) and the 15M closes.
     Memoised per V like `_em_memo`, with bars ≤ t only.
   - `side_fn(V)` ⇒ `u ↦ +1 / 0` (mirror −1 / 0).
   - `areas(V, t, cyc)` ⇒ the C-5 set.
   - `objects(V, t, cyc, sub)` ⇒ the C-b / C-d / C-e filters on `Reader.broken_objects`.
   - `end_zone(V, t, cyc)` ⇒ C-7.
   - `label(entry, cyc)` ⇒ sub-model, name, visit_id prefix, context.
2. **`entry_models.py`:** add `Reader(V, side_fn=None)` and `read(…, side_fn=None, objects=None)`, plus `broken(t, d, keep=None)`.
   The defaults keep today's path.
3. **`engine.py` `V22.decide`:** after today's evaluation, `if s["model_c"] == "on": row["model_c"] = …; row["entries"] += C entries`.
   This also runs when step1 / step2 fail for the Daily side (Daily DOWN but no Daily-side area). The `legacy_k` row stays untouched.
4. **`settings.py` DEFAULTS + REGISTER** (all dashboard settings, none a number except `c_projections`, which is display only):
   - `model_c` (off / on)
   - `model_c_subs` (subset of a…f)
   - `c_a_nature` (impulse / any)
   - `c_window` (b_only / b_and_ha_retest / c_pullbacks)
   - `c_projections` (tuple of ratios, OPERATIONAL)

   Dashboard keys are `engine3_model_c_on` and `engine3_model_c_a_on` … `_f_on` (default False), mapped in `engine3_live`.
5. **Live:**
   - `paper/engine_entry`: `model_on` reads the C switches when `family == "C"`; `model_tag` ⇒ "ENGINE_C_E2"; `models_summary`
     separates the C rows.
   - `vision/engine_audit` + `engine_card`: model C facts.
   - `vision/card_summary`: the story line.
6. **Tests (step 2, per the order):** no look-ahead (truncation); A needs a CHoCH; B beyond O plus a swing ⇒ dead; one candle beyond O ⇒
   alive; no C entry after a close beyond HA; no entry on the break of HA; the UP mirror; switch OFF ⇒ entries byte-identical
   (a golden diff of `row` on the existing fixtures). Also C-c / C-e labelling, the first return only, and a test that `c_projections`
   is never read on an entry path.

## 3. Golden check (T-3) on the latest BANKNIFTY replay group

- **The group.** The latest BANKNIFTY replay group is **07–21 Oct** (owner-orders README row 7). Its gallery is in the private
  trade-data repo: `review/replay_banknifty_6m/35b2b17/groups/2026-10-07_2026-10-21/`. Older groups are "not testable — FUT volume
  missing" (no near-month FUT before 30 Sep; DECISIONS 13 / 33).
- **Data the replay needs** for the group's sessions:
  - BANKNIFTY spot 15M (+ 1m for swings2, `engine3_use_1m`), 5M LTF, and Daily (Weekly is folded from the Daily);
  - near-month FUT 5M volume on **every** spot session of the group. `reader_report.standard.group_data_status` must return
    "testable", otherwise the group emits one line and nothing else (REPORT_STANDARD §0);
  - spot history before the group, as level and swing history only (15M window `engine3_m15_days`).

  If O or A lies before 30 Sep, A's volume measure is NA. `legs_compare.compare` then reads the body and overlap only and says
  "volume NA". The volume is never filled and spot volume is never used.
- **Where the data is.** It is **not in this repo**. `data/` holds only the NIFTY 1m and Daily parquet; the NIFTY holdout stays sealed
  and is not used. The BANKNIFTY bars, FUT volume and gallery are only in the private trade-data repo, which this session cannot
  access. So the golden check cannot run here. The one-day runner in this repo is `scripts/replay_day.py`, and the group runner and
  its outputs live with the gallery.
- **How to verify** (step 3):
  - Run the group with `model_c = on`, every sub-switch on, and `c_window = b_and_ha_retest` (C-e needs it), plus once with `b_only`.
  - Check that the biggest up move against the Daily side reads as:
    - A = CHoCH up with an impulse nature;
    - B corrective, ending in a TESTED 1H demand area, B's volume per bar lower than A's;
    - C ending at the Weekly resistance (C-7 context);
    - C-a, C-b and C-e entries there.
  - Check that the earlier up move whose start was later broken shows the B death (close plus swing below O).
  - Each entry needs next-area-first against invalidation-first and the worst adverse move, on the replay card format, with charts.
- **Known possible difference, to explain rather than tune.**
  - Model C has no look-ahead, so on the earlier up move an entry taken **before** B died is valid when it was taken.
  - The golden "no model C entry" then holds only if that move's A did not read impulse, its B never reached a C area before dying,
    or the death came first.
  - If the replay shows such an entry, it is reported as a difference with its chart, never fixed by a new rule. Golden cases are
    examples, not targets.

## 4. Open questions (each with a provisional default, checked against DECISIONS / CLAUDE.md / the method)

| # | Question | Provisional default | Checked against |
|---|---|---|---|
| Q1 | Model C when step1 has set the trend to NEUTRAL (`st.rev`, "trend first") or uses the Weekly fallback | Needs `DState.trend == DOWN` (C-1: "read by the Daily reader exactly as now"). `rev` is a context line. The Weekly fallback gives no model C. | DEC 32; C-1; CLAUDE "never add a rule" (no new gate: uses the Daily state as it is) |
| Q2 | Method P4 "never a counter-trend entry" and the Vision `trend_side` item | DECISIONS 32 (a later owner order) wins for model C only. At build time, add a method §8 line "Model C (DEC 32)" and model-C facts in the engine audit. P4 stands for E1–E4. | DEC 3, 31, 32; method concept list closed (no new concept) |
| Q3 | O when a lower low is not yet confirmed at the CHoCH | O = the lowest low between the protected high and the CHoCH bar (a known price, bars ≤ t) | method §3 swing; no look-ahead |
| Q4 | Swing degree for "a swing beyond O" (B death) | The finest structure (`Levels._known0`), exactly as the K4 break | DEC 23, 27; C-4 "like the K4 death rule" |
| Q5 | "Built during A": which areas | 1H only, ACTIVE / TESTED, base between O and HA inclusive (O's own area and the CHoCH BOS-origin area included; prior / Daily / Weekly bands excluded) | C-5 words; Z-1u (DEC 9); DEC 15 (BOS-origin base) |
| Q6 | The flipped old lower-high supply (now support) inside A, and the C-f switch | Not C-a (the order says fresh / tested only); it is listed in the replay as "not taken: flipped". The C-f switch only labels / counts Daily-side entries and never removes one. | C-5; DEC 6, 7 |
| Q7 | `c_projections` values (Abhi gave no ratio) | `(1.0,)` (C = A, the only relation the research names without a number). Display only, OPERATIONAL, never read by an entry. Abhi adds ratios on the dashboard. | CLAUDE "no fixed numbers in reading rules"; C-7; DEC 2 |
| Q8 | B's / C's channel only on D1 (15M) | Not an E4 (b) object (today E4 (b) reads the 1H lines); listed as evidence. Changing it would also change the Daily side and is Abhi's call. | DEC 12; existing `broken_objects` |
| Q9 | B "must read corrective" while B is only a few bars old (`compare` mixed) | "mixed" / "NA" ⇒ the models wait (not a block of a fired entry; re-read every bar) | C-4; legs_compare "read so far" |
| Q10 | Sub-model when one entry fits two (an E4 (a) sweep below O at O's area) | C-c wins over C-a; one entry, one label, each counted once | DEC 9 (one signal per model per place) |
| Q11 | `max_hits_per_zone` across model C and the Daily side at the same band | Counted together on the visited area (the existing `zone_full`); no new execution setting | DEC 7, 21 |

## 5. Checks made (provisional decisions in this report)
- **DECISIONS** 2 (numbers only in settings), 6 (E1–E4 independent, once per visit), 7 (no new execution settings), 9 (Z-1u),
  10 (refined base), 11 (never beyond invalidation), 12 (E4 (b) revisit), 13 (FUT rule), 15 (BOS-origin base), 21 (max_hits = 4),
  22 (traded_inside), 23 (sweep), 27 (flip once), 28 (one E4 (b) per place), 31 (Vision audits the engine reading), 32 (model C),
  33 (no older FUT).
- **CLAUDE.md:** PAPER only, signals only, Vision `human_confirm`, no day / clock framing (the C window is by structure), NIFTY holdout
  sealed, private data only in trade-data.
- **Method:** §3 (swing, broken / sweep, visit), §4, §8 (entry models, refined base, trigger) and P4 (see Q2).
