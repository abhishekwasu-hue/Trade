# T1 — Daily leg nature by comparison: `daily_leg_read` (Abhi 21 Oct)

Abhi: numbers left in the reading (decision path / evidence) are replaced with comparative logic — no fixed numbers, no wave-ratio
prediction. Setting `daily_leg_read` = **compare** | **elliott** (register class "Abhi नियम", source "Abhi 21 Oct").
**Default stays `elliott`** (today's behaviour) — the default flips only with Abhi's ✅ at deploy.

## What `compare` replaces

| Where (decision3) | elliott (today, what-if) | compare |
|---|---|---|
| `daily.fold_impulse` `nature_ok` (Q28 trend start, Q36 flip, trend-first structure) | `daily_legs.classify`: 5-wave rules / zigzag / flat (patterns2 ratios) OR legs2 C percentile (c_hi / c_lo / baseline_legs) | leg (1) and leg (3) each vs their neighbouring legs of the same degree (`daily_legs.compare_classify` → `legs_compare.compare`); impulse nature = larger bodies + less overlap (Daily has no volume). Mirror of the elliott semantics: only a **correction** verdict (by comparison) is corrective and blocks; mixed / nothing to compare = unclear, not corrective ⇒ passes (as elliott's "C नाही; रचना corrective नाही") |
| `counter_kind` (A1 counter-move; Q49 wave A / wave 1) | `read_counter` 5-wave count + `unfolded_123` | the counter-move vs the trend leg it corrects (correction / mixed ⇒ not impulse-natured ⇒ no flip, as elliott's corrective / single); impulse-natured + same degree (Q22 pullback comparison, unchanged) ⇒ it breaks the trend only by a close beyond the impulse origin (Q49 (a)); lower degree ⇒ stays A1 |
| `imp_origin` (Q49 (a) complete-impulse origin) | `complete_impulse_start` (5-wave count) | the current leg's origin (no count) |
| `corr_end` (continuation confirm / Rule 4 origin) | `read_counter` motive vs zigzag | the continuation from each candidate vs the correction leg it follows; the most extreme impulse-natured one (mixed = elliott's "single": only the origin itself) |
| `flip.approach_context` (G4, evidence) | `classify(elliott=True)` | the pullback vs the flip impulse it follows (bodies, overlap, FUT volume) |

Flips stay structural: the Dow LH / HL + close rules and the C-13 "equal" are unchanged.

## Display (admin diagnostics)

`daily_swings.build(with_elliott=False, elliott_debug=False)` by default: no Elliott advisory count, no box family / a-b-c marks,
no 5-wave leg check (legs are drawn as trend legs unless Abhi accepted them). `scripts/v22_daily_swings_view.py --debug-elliott`
turns them on for an admin view. The low-level helpers (`structure_objects`, `leg_check`, `_corr`) keep `elliott=True` as their
own default for direct diagnostic calls. Telegram charts are unaffected.

## Not changed

- `daily_legs.classify`, `read_counter`, `c_class` stay as they are (the what-if).
- The swings2 D1 / D2 calibration (Abhi's setting).
- Golden expectations (the golden tests are run under `compare` and any difference is reported, never edited).
