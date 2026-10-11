# Chart Reader v2 — design note and legs2 feature audit (CR0)

Abhi: TRADE_SESSION_CHART_READER_V2. Read candles the way a trader does, then re-check the marking. This note covers CR0 (design +
audit); CR1 (anatomy vote + fixtures) and CR2 (fusion + self-check) are implemented in `reader2/`. CR3+ (marking page, gallery
storage, CI scoring, chart layer, decision3 shadow) are **not started**. Revised after the independent BANKNIFTY review: candles only at
the lowest degree with a roll-up above, one vote never sets the trend, uncertain is re-entered by a clear impulse, provisional leg.

**Research-only.** No bot, no decision3 gate and no Vision code imports `reader2` until the gallery gate (§5) passes and Abhi approves
(`tests/test_reader2_boundary.py` enforces it). `reader2` itself only *reads* decision3 / legs2 / patterns2; nothing there changes.

## 1. Why
`decision3/daily_legs.read_counter` (ABC_FIX) classifies a move only from the sequence of pivot prices. One wrong pivot changes the
whole reading, and the candles are never consulted. There is no self-verification; Vision is audit-only. Reader v2 gives every leg
two independent votes — the existing structure reading and a new candle **anatomy** vote — fuses them, and then runs a self-check
pass that relabels (with a log) whatever breaks an invariant.

## 2. Package and data flow

```
OHLC(V) of any timeframe ──► frame.Chart  (legs2 candle arrays, median range MR, known_at, volume)
                              │
                              ├─► legs.py      degree D pivots = directional change k_D × MR ──► confirmed legs + one provisional leg per degree
                              ├─► structure.py sub-legs one degree lower ──► decision3.daily_legs.read_counter ──► structure vote
                              ├─► anatomy.py   lowest degree: candles (legs2/features.py); higher: roll-up of the sub-legs' votes
                              ├─► fusion.py    agree ⇒ high; conflict or one vote silent ⇒ re-read one degree lower ⇒ medium / low / uncertain
                              ├─► trend.py     trend state per bar from trend-capable impulses (both votes agree)
                              └─► selfcheck.py invariants 1–7, ≤ 3 passes, relabel log, history (new bars)
reader.read(df, s=None, pivots=None, low=None, higher=None) ──► Reading (legs, current, labels, confidence, evidence, trend, log)
```

| Module | Public functions |
|---|---|
| `reader2/settings.py` | `DEFAULTS`, `FEATURES`, `ROLLUP`, `REGISTER` (same keys as `DEFAULTS`), `load(overrides)`, `is_loaded(s)` |
| `reader2/frame.py` | `Chart(df, s)`, `with_futures_volume(spot, fut)` |
| `reader2/legs.py` | `Leg`, `degree_pivots`, `make_legs`, `provisional_leg`, `inner_points`, `inner_prices`, `external_pivots` |
| `reader2/structure.py` | `vote_prices(prices, s)`, `leg_vote(ch, leg, lowers)`, `alt_thresholds`, `alternatives` |
| `reader2/anatomy.py` | `feature_score`, `raw`, `vote` (candles), `candle_vote` (cached on the Chart), `rollup`, `own_lowers`, `leg_vote(ch, leg, prev, low)`, `alternatives` |
| `reader2/fusion.py` | `fuse(sv, av)` (first reading), `decide(ch, leg, lowers, prev, low)` (with re-read), `label_leg(...)` |
| `reader2/trend.py` | `trend_capable(leg)`, `flip_test(leg, prev)`, `derive(ch, legs)`, `from_events(ch, events)` |
| `reader2/selfcheck.py` | `violations(R)`, `fix`, `run(R, higher)`, `htf_check(R, higher)`, `history(df, start, step)` |
| `reader2/reader.py` | `build`, `read`, `mark(R, labels, events)` (external / v1 marking), `summary(R)` |

## 3. Units
Every measure is in **median-range units of the same timeframe** or is a unit-free ratio of two such measures — never points, never
percentages of price. `MR[i]` = median (H − L) of the last `mr_bars` bars including i (causal). A bar is normalised by `MR[i−1]`
(known before it), a leg by `MR[i0]` (known at its start). DC pivot thresholds are `k × MR`. A test scales and shifts all prices
(×7, +12345) and requires identical scores and labels.

## 4. Legs and degree (spec §2d)
- Degree D pivots: `decision3.daily.pivots_dc` with threshold `dc_k[D] × MR` (default 2 / 4 / 8). Causal: a pivot is known at its
  `confirm_bar`; a leg is known when both its pivots are (`known_bar`, `known_at`).
- **Provisional leg** (`R.current[D]`): from the last confirmed pivot to the extreme since, known at the last bar, flagged
  `provisional`. It is read and labelled like any leg (so the move in progress — e.g. BANKNIFTY Jun → now — is read), but it is not in
  `R.legs`: it never sets, flips or moves the trend and is not checked by the trend invariants.
- External pivots (Abhi's hand marking, a v1 count) can replace any degree: `read(df, pivots={1: [(bar, "H"|"L"[, confirm_bar])]})`.
- **Sub-legs one degree lower.** A leg's sub-legs are the next lower pivot set that shows structure inside it; when two thresholds catch
  the same swings, the set below is used (`structure.leg_vote` / `anatomy.rollup`; the re-read never goes below `dc_k[0]`).
- **Candles are read only at the lowest degree** (resolves CR-Q1). A leg with no lower pivots inside is its own lowest-degree swing and
  is read from its candles. Every higher leg's anatomy is **rolled up** from its sub-legs, recursively down to candles — never the
  average of all its candles (waves 2 and 4 would dilute it: on realistic candles the flat average of a clean impulse reads ≈ +0.1,
  the roll-up ≈ +0.65; `test_rollup_is_not_diluted_by_waves_2_and_4`).
- With `low=` (e.g. 1H for a Daily chart) the lowest-degree candle votes also score the lower-timeframe candles in the same window and
  blend them (`lower_weight`, evidence prefixed `lower:`).

## 5. Structure vote (spec §2a)
`structure.vote_prices` wraps `decision3.daily_legs.read_counter` (patterns2 rules: impulse 5-3-5-3-5 incl. extensions, diagonal,
zigzag 5-3-5, flat 3-3-5 incl. expanded / running, triangle, combination; c may exceed a).

| read_counter family | vote | class |
|---|---|---|
| impulse, diagonal | +1 | impulse |
| zigzag, flat, triangle, combination | −1 | correction |
| "3-wave" fallback (no named pattern — also unparsed 5- / 9-wave counts) | `three_wave_vote` (−0.25) | **none** (|vote| < `s_decisive`) |
| single / lowest degree | 0 | none (silent) |

## 6. Anatomy vote (spec §2b, §2d)
**Lowest degree — candles.** Per feature a linear score between the corrective end (−1) and the impulsive end (+1) from `FEATURES`.
"imp"-sided features only add impulsive evidence, "cor"-sided only corrective; a one-sided feature at 0 (no evidence) is **not** in the
average. Anatomy = weighted mean of the counted features (`min_features` else NA; legs ≤ `short_leg_bars` bars ⇒ NA). Classes:
≥ `a_hi` impulsive, ≤ `a_lo` corrective, else neutral. Every feature (NA ones with the reason) is in the evidence.

**Higher degrees — roll-up** (`anatomy.rollup` / `_combine`), from the sub-legs' votes. The anatomy always uses the reader's **own**
pivot sets (`own_lowers`): an external marking (hand / v1 pivots) changes only the structure vote, so mis-placed pivots cannot
contaminate the candle vote — the two votes stay independent.

| Roll-up feature | Measure | Reading |
|---|---|---|
| `motive` (weight 2) | size-weighted mean of the sub-legs in the leg direction | impulsive leg ⇒ its pushes read impulsive; corrective leg ⇒ overlapping pushes |
| `counter` | mean of −score of the counter sub-legs | corrective / brief pauses are impulsive evidence; sharp counter-moves are corrective evidence |
| `pause_time` | counter bars ÷ leg bars (0.55 → 0.35) | brief pauses ⇒ impulsive; long ⇒ corrective (sideways) |
| `pause_depth` | total counter travel ÷ total motive travel (0.80 → 0.50) | shallow ⇒ impulsive; choppy / three-push ⇒ corrective |
| `c_like_a` | last push vs the strongest earlier push: candle-score similarity × speed ratio × size ratio (0.85 → 0.60, cor only) | a zigzag's c resembles a ⇒ corrective; an impulse's wave 5 differs from wave 3 ⇒ no evidence |
| `b_brief` | counter sub-leg bars ÷ the preceding push's bars (1.50 → 0.60) | waves 2 / 4 brief ⇒ impulsive; a zigzag's long overlapping b ⇒ corrective |
| `middle_push` | with ≥ 3 pushes: is the strongest push (candle score × size) a middle one? (+1 / −1) | wave 3 the most impulsive push ⇒ impulsive |

**No wave count in the anatomy.** The number of sub-legs is never a feature or a cap (that belongs to the structure vote only), so the two
votes stay independent; a-b-c is told from 1-2-3-4-5 by candle evidence (the rows above).

Gates: (1) pause evidence counts only with ≥ `rollup_pause_min_counters` (2) counter sub-legs — one pause cannot tell an impulse from a
zigzag's b; (2) if `motive` is not impulsive the leg cannot read impulsive (score ≤ motive); (3) a corrective motive sub-leg carrying
≥ `rollup_veto_share` (25 %) of the motive travel vetoes an impulsive reading (score ≤ its score) — the overlapping wave a of a big-c
zigzag keeps it a correction, while a small sluggish first push next to the top does not cancel an impulse. A sharp a-b-c with
impulsive a and c rolls up neutral (c ≈ a, long b) and its zigzag structure labels it a correction (low); an impulse with a
sub-threshold wave 2 or 4 (only 3 sub-legs visible) rolls up impulsive and never reads correction/high (reviewer probes). Each sub-leg is listed in
the evidence with its own vote and level (candles / rollup). **All thresholds are register guesses — calibrated later only on the
dev gallery against Abhi's labels, never on trade results.**

| Spec item | Feature | Source | Measure | corrective → impulsive |
|---|---|---|---|---|
| large bodies | `body` | `features.leg_features` → `body_pct` | mean body ÷ range | 0.35 → 0.55 |
| closes near the leg extreme / closes mid-range | `close_loc` | `leg_features` → `clv_d` | mean CLV in leg direction | 0.50 → 0.68 |
| low overlap / overlapping candles | `overlap` | `leg_features` → `overlap` | mean overlap with previous candle ÷ range | 0.60 → 0.35 |
| displacement candles / FVGs | `displacement` | `leg_features` → `displacement`, `fvg` (rr = range ÷ MR) | (n_disp + n_fvg) ÷ bars | 0 → 0.25 (imp only) |
| range expansion / smaller ranges | `range` | new | mean range ÷ MR[i0] | 0.85 → 1.30 |
| contracting ranges | `contraction` | new | 2nd-half mean range ÷ 1st-half | 0.70 → 1.00 (cor only) |
| high / low efficiency | `er` | `features.er` | close-to-close ER | 0.30 → 0.60 |
| few opposite wicks | `wick_opp` | `features.wick_opp_d` | mean wick at the leg-direction extreme ÷ range | 0.30 → 0.15 |
| wicks on both sides | `wick_both` | new | share of candles with both wicks ≥ `wick_both_min` | 0.50 → 0.20 |
| volume above / below the preceding counter-move | `volume` | new (rule as `legs2.measure2.v_score`) | leg volume per bar ÷ preceding leg's | 0.83 → 1.20 |
| effort without result | `effort_result` | new (MR units) | volume ratio ÷ speed ratio (MR / bar) | 1.50 → 1.00 (cor only) |
| pause inside one swing | `pause_depth`, `stall` | new | deepest counter-move ÷ size; longest run without a new extreme ÷ bars | cor only (a choppy drift also has shallow pauses) |
| shallow, brief internal pause; three-push / sideways | roll-up `pause_time`, `pause_depth` | new | see the roll-up table | two-sided |

Volume: the index has no volume, so the caller passes the matching futures volume in a `volume` column
(`frame.with_futures_volume(spot, fut)` sums futures rows per spot bar, near-month contract when `expiry` / `contract` exist). No
column, zeros or NaN ⇒ `volume` and `effort_result` are NA (listed as "NA (no volume)") and the vote uses the other features.

## 7. Fusion (spec §2c)
Re-read = alternative pivots **exactly one degree lower**: `dc_k[D − 1] × reread_k_mult` with three multipliers 0.9, 0.75, 0.6,
never below the lowest degree (`dc_k[0]`): finer swings are noise counts (13 / 17 / 19 waves).
**Degree-1 legs can never be re-read:** their alternatives would be `dc_k[0]` × 0.9 / 0.75 / 0.6, all below the floor, so the re-read
always **abstains** (no majority). A degree-1 leg is therefore labelled only by its first reading — agree ⇒ high; conflict ⇒
uncertain; one vote silent ⇒ low / uncertain — and never reaches "medium". Only degree-2 (and higher) legs can be resolved by a re-read. Both votes can be re-read: structure from the alternative pivots, anatomy rolled up from them.
A re-read decides only by **majority** (more than half of the alternatives, i.e. 2 of 3), with the same rule for both directions — the
first agreeing alternative is never picked on its own. A **named** corrective structure (zigzag, flat, triangle, combination) is never
re-read into an impulse (only the anatomy re-read can confirm it as a correction).

| Structure | Anatomy | Result |
|---|---|---|
| impulse | impulsive | impulse, **high** |
| correction | corrective | correction, **high** |
| conflict | conflict | re-read: a majority of alternative structures agreeing with the anatomy (not into impulse from a named correction), or a majority of alternative anatomies agreeing with the structure ⇒ that label, **medium**; else **uncertain** with the reason |
| decisive | silent | re-read the anatomy: majority agrees ⇒ **medium**; majority opposite ⇒ uncertain; otherwise structure impulse ⇒ **uncertain** ("impulse structure not confirmed by the candles"); structure correction ⇒ correction, **low** |
| silent | decisive | re-read the structure: majority agrees ⇒ **medium**; majority opposite ⇒ uncertain; otherwise anatomy's label, **low** (the lowest degree has no structure) |
| silent | silent | uncertain ("no decisive vote") |

Only **trend-capable** impulses (label impulse, confidence high or medium, effective structure impulse, effective anatomy impulsive)
can set, flip or move the trend. "Low" and "uncertain" never can; a correction never moves the trend anyway.

## 8. Trend (trend-degree legs)
Trend = direction of the last trend-capable impulse; protected origin = its start (a new one in the same direction moves it). A flip
needs a trend-capable counter-move plus a break of the prior swing (`trend.flip_test`). Corrections (c beyond a included), low and
uncertain legs never move the trend. A close beyond the protected origin turns the trend `uncertain` (re-read, not kept).
**Uncertain is never permanent:** the next trend-capable impulse, in either direction (the origin is already broken, so no prior-swing
break is needed), sets the trend again by the normal Dow / structure path (`test_uncertain_trend_is_re_entered_*`). Uncertain ⇒ no
entries (reader2 gives no entries).

## 9. Self-check (spec §3)
`selfcheck.run(R, higher=None)`: find violations → fix → repeat, at most `max_passes` (3); leftovers ⇒ the leg becomes uncertain
("unresolved after 3 self-check passes: …"). A violation is re-validated before it is fixed (an earlier fix in the same pass may have
removed it). Every change is logged as `relabelled <target>: X → Y because …` with `known_at` (the reading time T, so a backtest stores
the label as known at T), `at` (the leg / bar it concerns), pass and invariant. An external marking (v1 labels, a hand-made trend) is
loaded with `reader.mark(R, labels, events)` and checked the same way.

| # | Invariant | Check | Fix | Failing case (tests/test_reader2_selfcheck.py) |
|---|---|---|---|---|
| 1 | impulse label with corrective anatomy, or the reverse | label vs decisive (effective) anatomy | re-read (fusion `decide`) | correction marked impulse; impulse marked correction |
| 2 | flip only on an impulse counter-move | each flip's leg passes `flip_test` | counter-move ⇒ correction (impulsive candles but no structure / break ⇒ uncertain); trend re-derived | sharp 5-wave A without break; overlapping correction marked impulse + flip |
| 3 | correction beyond its a-wave is not a flip | flip resting on a correction leg | trend re-derived (flip removed) | big-c zigzag with a flip where c passes a |
| 4 | protected origin closed beyond ⇒ re-read | trend kept after a close beyond the origin (origin from the marking, else the trend leg's start, else the last same-direction trend-degree impulse) | trend re-derived ⇒ uncertain / new trend | stale marking keeps UP; marking without origin |
| 5 | alternation impulse → correction → impulse | two consecutive opposite impulses, second not beyond the first's start | re-read both (always); still both ⇒ second = correction / uncertain | sharp_a fused labels |
| 6 | higher timeframe consistent (Q48 projection) | lower trend vs higher trend known at the lower reading's time | logged; resolved: trend = higher, pullback state = lower (`R.htf`) | 1H DOWN under Daily UP |
| 7 | new bars re-run the check, never silent | `selfcheck.history(df, start, step)` re-reads at each T | every label / trend change logged with that bar's known_at | origin close turns UP → uncertain; inv-5 relabel on the bar its leg appears |

No look-ahead: pivots are directional-change (known at `confirm_bar`); leg votes (and their roll-up) use bars ≤ `known_bar` and
pivots confirmed by then; the trend at bar i uses only legs known by i. Test: the full `read()` (with self-check) restricted to legs
known by T equals `read(df[:T+1])`, and so do the trend states (also checked on BANKNIFTY daily every 61 bars, and mirror-symmetric).
`history()` re-reads the whole series at every T — O(n) reads (≈ 0.3–0.5 s per read on 2,400 BANKNIFTY daily bars with the candle-vote
cache, so a full history is ≈ 10–20 min); it is not
incremental, so long histories use `step` or a replay script (heavy-job rule).

## 10. Feature audit — `legs2/features.py`

**Exists (reused as is)**

| Function | What it gives | Used by reader2 |
|---|---|---|
| `body_pct(A, i)` | body ÷ range (H = L ⇒ None) | `body` (via `leg_features`) |
| `clv(A, i)`, `clv_d(A, i, d)` | close location, in leg direction | `close_loc` |
| `wick_opp_d(A, i, d)` | wick at the leg-direction extreme ÷ range | `wick_opp` |
| `overlap(A, i)` | overlap with the previous candle ÷ range (no session-crossing pair) | `overlap` |
| `overlap3(A, i)` | overlap with the union of the previous 3 candles | computed by `leg_features`, not voted (overlap with the previous candle is) |
| `trend_candle(A, i, d, s)` | body ≥ 0.5 and CLV_d ≥ 0.6 in direction | via `leg_features` (`trend_pct`, `max_run`) |
| `displacement(A, rr, i, d, s)` | range ratio ≥ 1.5, body ≥ 0.6, opposite wick ≤ 0.2 | `displacement` (rr = range ÷ MR) |
| `climax_candle(A, rr, i, d, s)` | range ratio ≥ 2, closed in direction | computed by `leg_features` (`n_climax`), not voted yet (CR-Q3) |
| `fvg(A, i, d)` | 3-candle gap inside a session | `displacement` |
| `er(A, i0, i1)` | close-to-close efficiency, overnight term removed | `er` |
| `gaps(A, i0, i1)` | overnight gaps inside a leg | not used |
| `leg_features(...)` | bars, er, body, dirc, overlap, overlap3, clv_d, trend_pct, max_run, n_fvg, n_disp, n_climax, speed, wave_vol, wave_rvol, n_reliable, effort_result | one call per leg |

**Missing for the anatomy vote (added in `reader2/anatomy.py`)**
1. A same-timeframe **median-range unit**: legs2's `rr` comes from `swings2.candles.rng_ratio` (15M slot-normalised, needs sessions);
   reader2 needs any timeframe ⇒ `Chart.mr` / `Chart.rr`.
2. **Range expansion / contraction** in MR units (none in features.py; `chart_reader.candles._leg.spread_mr` exists but not per leg vote).
3. **Wicks on both sides** (only the leg-direction wick exists).
4. **Volume vs the preceding counter-move** on raw futures volume: `leg_features.wave_vol` is absolute; the comparison exists only in
   `legs2.measure2.v_score` on 15M RVOL arrays.
5. **Effort vs result in MR units**: `leg_features.effort_result` = volume ÷ size in **points** (violates the units rule) ⇒ replaced
   by volume ratio ÷ speed ratio.
6. **Internal pause** depth and duration (shallow / brief vs deep / sideways).
7. **Three-push shape**: not built as a separate feature; the structure vote (3-wave / zigzag) and ER / stall cover it for now
   (OPEN_QUESTIONS CR-Q3).
8. A **[−1, +1] score per feature with an evidence list**, NA-safe (features.py returns raw values only).
9. **Daily / any timeframe**: `first` (session start) must be all False above intraday so overlap / ER are not dropped every bar —
   handled in `Chart` (same as `decision3.daily_legs.arrays`).

Definition note: `features.er` returns None for a zero path; `legs2.measure.candle_metrics` returns 0.0. reader2 uses `features.er`
(None ⇒ feature NA).

## 11. Known limits (for CR3–CR4)
- **Correction-fixture library** (`tests/test_reader2_library.py`, 16 shapes × 2 directions; uniform candles):

  | Check | Pass | Strict xfail |
  |---|---|---|
  | no flip against the impulse during the correction | 32 / 32 | — |
  | no correction leg read as a trend-capable impulse | 32 / 32 | — |
  | impulse direction read by the end | 0 / 32 | all: the degree-2 leg runs from the lead-in top through the lower high into the impulse (unparsed 9-wave count); the re-read finds no majority ⇒ no trend-capable impulse ⇒ no trend |

  With uniform candles every push looks impulsive, so correction legs read `correction` (low) or `uncertain`, never impulse. CR-Q2:
  degree calibration on the dev gallery, not tuned here. The library's own decision3 tests are unaffected.
- **Kept-failing tests (strict xfail, fixtures unchanged):** the mis-placed-pivot test (expects impulse / medium) and the three sharp_a
  self-check tests (inv 2 / 5 / 7; the same tests pass live on `sharp_a5`, whose 5 waves are visible at degree 1) — both fixtures give a NAMED zigzag at the default degree-1 pivots, and the review rule forbids
  re-reading a named correction into an impulse even when 3 / 3 alternatives read 5 waves (CR-Q11).
- Sharp, impulsive-looking counter-moves that do not break the prior swing (wave 1 vs wave A, Q49) become `uncertain` (CR-Q4).
- **BANKNIFTY daily** (2016 → now, not sealed): trend share UP 23.6 % / DOWN 5.5 % / uncertain 55.2 % / none 15.7 % (warm-up).
  Only 3 of 37 degree-2 legs are trend-capable impulses. All uncertain bars come from 2 origin-close events (2018-07 → 2021-05 and
  2021-09 → 2024-06); keeping the trend instead would have meant "DOWN" through the 2019–2024 rally, so the origin-close rule is not
  the cause — the missing trend-capable up-impulses are (CR-Q12).

## 12. Tests
`SUPABASE_DB_URL="" python3 -m pytest -q -p no:cacheprovider tests/test_reader2_anatomy.py tests/test_reader2_fusion.py
tests/test_reader2_selfcheck.py tests/test_reader2_library.py tests/test_reader2_boundary.py` — fixtures in `tests/reader2_fixtures.py`:
clean impulse, overlapping correction, impulse with mis-placed pivots, big-c correction, deep sideways decline, sharp A (block candles),
plus realistic noisy candles (bodies ~50–65 %, wicks on both sides; seeds 1–3) and a structure-only 5-wave drawn with ambiguous
candles that must be challenged (uncertain, no trend), sharp a-b-c (impulsive a and c; 3 depths, ideal + noisy) that must stay a
correction, unequal sharp a-b-c (c ≈ 1.3 / 1.6 × a ⇒ never impulse, never a flip; uncertain allowed), sharp_a5 (live inv 2 / 5 / 7
cases), and the reviewer's probes (impulse with a 12-point, 3-bar wave 4 or wave 2 ⇒ never correction/high) — each with its mirror.
