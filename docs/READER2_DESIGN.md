# Chart Reader v2 — design note and legs2 feature audit (CR0)

Abhi: TRADE_SESSION_CHART_READER_V2. Read candles the way a trader does, then re-check the marking. This note covers CR0 (design +
audit); CR1 (anatomy vote + fixtures) and CR2 (fusion + self-check) are implemented in `reader2/`. CR3+ (marking page, gallery
storage, CI scoring, chart layer, decision3 shadow) are **not started**.

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
                              ├─► legs.py      degree D pivots = directional change k_D × MR  ──► legs (dir, degree, bars, known_at)
                              ├─► structure.py inner pivots one degree lower ──► decision3.daily_legs.read_counter ──► structure vote
                              ├─► anatomy.py   candles inside the leg (legs2/features.py) ──► anatomy score [−1, +1] + evidence
                              ├─► fusion.py    agree / one silent / conflict ⇒ re-read ⇒ impulse | correction | uncertain
                              ├─► trend.py     trend state per bar from trend-degree labels (flip rule, protected origin)
                              └─► selfcheck.py invariants 1–7, ≤ 3 passes, relabel log, history (new bars)
reader.read(df, s=None, pivots=None, low=None, higher=None) ──► Reading (legs, labels, confidence, evidence, trend, log)
```

| Module | Public functions |
|---|---|
| `reader2/settings.py` | `DEFAULTS`, `FEATURES`, `REGISTER`, `load(overrides)` |
| `reader2/frame.py` | `Chart(df, s)`, `with_futures_volume(spot, fut)` |
| `reader2/legs.py` | `Leg`, `degree_pivots`, `make_legs`, `inner_prices`, `external_pivots` |
| `reader2/structure.py` | `vote_prices(prices, s)`, `leg_vote(ch, leg, lowers)`, `alternatives(ch, leg)` |
| `reader2/anatomy.py` | `feature_score`, `raw`, `vote(ch, i0, i1, d, prev)`, `leg_vote(ch, leg, prev, low)` |
| `reader2/fusion.py` | `fuse(sv, av)`, `reread(ch, leg, sv, av)`, `label_leg(...)` |
| `reader2/trend.py` | `flip_test(leg, prev)`, `derive(ch, legs)`, `from_events(ch, events)` |
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
- External pivots (Abhi's hand marking, a v1 count) can replace any degree: `read(df, pivots={1: [(bar, "H"|"L"[, confirm_bar])]})`.
- Structure is read from the sub-legs **one degree lower**. When two thresholds catch the same swings (no inner pivots), the next
  lower pivot set is used; the lowest degree has no sub-legs, so its label rests on candles only.
- Anatomy uses the candles inside the leg on its own timeframe; with `low=` (e.g. 1H for a Daily leg) the lower-timeframe candles in
  the same time window are scored too and blended (`lower_weight`), evidence prefixed `lower:`.
- Interpretation (open): "candles are used only for the lowest degree" is read as "the candle vote is the only vote at the lowest
  degree". Every leg still gets a candle anatomy; a higher-degree anatomy is not built from sub-leg labels. See OPEN_QUESTIONS CR-Q1.

## 5. Structure vote (spec §2a)
`structure.vote_prices` wraps `decision3.daily_legs.read_counter` (patterns2 rules: impulse 5-3-5-3-5 incl. extensions, diagonal,
zigzag 5-3-5, flat 3-3-5 incl. expanded / running, triangle, combination; c may exceed a).

| read_counter family | vote | class |
|---|---|---|
| impulse, diagonal | +1 | impulse |
| zigzag, flat, triangle, combination | −1 | correction |
| 3-wave (no named pattern) | `three_wave_vote` (−0.5) | correction (weak) |
| single / lowest degree | 0 | none (silent) |

## 6. Anatomy vote (spec §2b)
Per feature: a linear score between the corrective end (−1) and the impulsive end (+1) from `FEATURES`; "imp"-sided features only add
impulsive evidence (absence is not corrective), "cor"-sided only corrective. Anatomy = weighted mean of available features
(`min_features` else NA; legs ≤ `short_leg_bars` bars ⇒ NA). Classes: ≥ `a_hi` impulsive, ≤ `a_lo` corrective, else neutral.
Every feature (also NA ones, with the reason) is listed in the leg's evidence. **Thresholds are guesses in the register — calibrated
later only on the dev gallery against Abhi's labels, never on trade results. Not tuned now.**

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
| shallow internal pause / sideways | `pause_depth` | new | deepest internal counter-move ÷ leg size | 0.60 → 0.30 (cor only) |
| brief pause / sideways, choppy | `stall` | new | longest run without a new extreme ÷ bars | 0.50 → 0.25 (cor only) |

Volume: the index has no volume, so the caller passes the matching futures volume in a `volume` column
(`frame.with_futures_volume(spot, fut)` sums futures rows per spot bar, near-month contract when `expiry` / `contract` exist). No
column, zeros or NaN ⇒ `volume` and `effort_result` are NA (listed as "NA (no volume)") and the vote uses the other features.

## 7. Fusion (spec §2c)
| Structure | Anatomy | Result |
|---|---|---|
| impulse | impulsive | impulse, **high** |
| correction | corrective | correction, **high** |
| decisive | neutral / NA | structure's label, medium |
| none | decisive | anatomy's label, medium |
| none | neutral / NA | uncertain ("no decisive vote") |
| conflict | conflict | **re-read**: alternative pivots one degree lower (`dc_k[D−1] × reread_k_mult`); a reading that agrees with the anatomy ⇒ that label, low; else **uncertain** with the reason |

## 8. Trend (trend-degree legs)
Trend = direction of the last impulse; protected origin = that impulse's start. A flip needs an impulse counter-move: label impulse +
impulse structure + impulsive anatomy + break of the prior swing (`trend.flip_test`). Corrections (c beyond a included) and uncertain
legs never move the trend. A close beyond the protected origin turns the trend to `uncertain` (re-read, not kept); only a full
impulse (structure + anatomy, plus the break for the opposite side) sets it again. Uncertain ⇒ no entries (reader2 gives no entries).

## 9. Self-check (spec §3)
`selfcheck.run(R, higher=None)`: find violations → fix → repeat, at most `max_passes` (3); leftovers ⇒ the leg becomes uncertain
("unresolved after 3 self-check passes: …"). Every change is logged as `relabelled <target>: X → Y because …` with `known_at` (the
reading time T, so a backtest stores the label as known at T), `at` (the leg / bar it concerns), pass and invariant. An external
marking (v1 labels, a hand-made trend) is loaded with `reader.mark(R, labels, events)` and checked the same way.

| # | Invariant | Check | Fix | Failing case (tests/test_reader2_selfcheck.py) |
|---|---|---|---|---|
| 1 | impulse label with corrective anatomy, or the reverse | label vs decisive anatomy | re-fuse; conflict ⇒ re-read with alternative lower pivots; else uncertain | correction marked impulse; impulse marked correction |
| 2 | flip only on an impulse counter-move | each flip's leg passes `flip_test` | counter-move ⇒ correction (impulsive candles but no structure / break ⇒ uncertain); trend re-derived | sharp 5-wave A without break; overlapping correction marked impulse + flip |
| 3 | correction beyond its a-wave is not a flip | flip resting on a correction leg | trend re-derived (flip removed) | big-c zigzag with a flip where c passes a |
| 4 | protected origin closed beyond ⇒ re-read | trend kept after a close beyond origin | trend re-derived ⇒ uncertain / flip | sideways decline below the origin, stale marking keeps UP |
| 5 | alternation impulse → correction → impulse | two consecutive opposite impulses, second not beyond the first's start | re-read both; still both ⇒ second = correction / uncertain | sharp_a fused labels |
| 6 | higher timeframe consistent (Q48 projection) | lower trend vs higher trend known at the lower reading's time | logged; resolved: trend = higher, pullback state = lower (`R.htf`) | 1H DOWN under Daily UP |
| 7 | new bars re-run the check, never silent | `selfcheck.history(df, start, step)` re-reads at each T | every label / trend change logged with that bar's known_at | origin close turns UP → uncertain; inv-5 relabel on the bar its leg appears |

No look-ahead: pivots are directional-change (known at `confirm_bar`); leg votes use bars ≤ `known_bar` and inner pivots confirmed by
then; the trend at bar i uses only legs known by i. Test: the full-data reading restricted to legs known by T equals the reading of
`df[:T+1]`, and so do the trend states.

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
- Degree thresholds `dc_k` and all anatomy thresholds are register guesses. On the existing correction-fixture library (uniform
  synthetic candles, no anatomy) reader2 mostly reads trend `uncertain`: the flip rule needs impulsive anatomy and the lead-in's lower
  high is not a degree-2 pivot at `dc_k` = 8. This is a calibration item for the dev gallery, not a tuning target now. The library
  tests themselves are unchanged and unaffected (reader2 changes no existing module).
- Sharp, impulsive-looking counter-moves that do not break the prior swing (wave 1 vs wave A, Q49) become `uncertain` under
  invariants 2 / 5 — this raises the uncertain rate; gallery acceptance (≤ 20 %) will tell.

## 12. Tests
`SUPABASE_DB_URL="" python3 -m pytest -q -p no:cacheprovider tests/test_reader2_anatomy.py tests/test_reader2_fusion.py
tests/test_reader2_selfcheck.py tests/test_reader2_boundary.py` — fixtures in `tests/reader2_fixtures.py` (clean impulse,
overlapping correction, impulse with mis-placed pivots, big-c correction, deep sideways decline, sharp A), each with its mirror.
