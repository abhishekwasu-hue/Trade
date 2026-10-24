Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# Gallery review — section F: the Daily trend side (BANKNIFTY)

Source: INBOX 24 Oct "gallery review corrections", section F (F1, F2, F3). BANKNIFTY only. Data: Upstox Daily up to 9 Oct, then
Daily bars built from complete 15M sessions up to 19 Oct (same input as sec6). Engine = branch `claude/hopeful-gates-hf186c` (0e48a7c),
default settings: `daily_trend_mode = impulse`, `daily_leg_read = compare`, `daily_pivot_n = 2` (L1-c, provisional).
Charts (trade-data, not committed): `review/gallery_fixes/F/F1_daily_structure_labels.png`, `F2_29jun_confirmation.png`,
`F3_side_strips.png`.

Checks made before deciding (memory protocol): DECISIONS 1–3 (structure only, no numbers, closed concept list), 17 (Daily leg read =
compare), 60 (BREAK-1, not involved), 68 (galleries must prove changes); STABLE layer 1 (L1-a swings, L1-b C-13, L1-c N = 2; frozen,
bug fixes only); method §2 b) and §3 Structure (Swing, Degree, Equal); OPEN_QUESTIONS D-SIDE-1…3.

## Summary

| Item | Finding | Action |
|---|---|---|
| F1 rule | Apr–Jun reads DOWN by the A1 rule: the impulse origin 54,146 was closed through on 8 Apr, but the counter-move was read corrective by comparison and the parent 61,765 held ⇒ a same-degree correction inside DOWN. From 17 Jun the side is NEUTRAL (trend first), not DOWN. | Reported (exact code lines + swings below). No change. |
| F1 labels | Bug (display). The chart labels compared each swing with the previous swing of the same kind of ANY degree; the reading compares with swings of the same degree. | Fixed: `daily_swings.tag_pivots` (+ the two other Daily label copies). Tests added. Committed. |
| F2 | 58,706 was NOT a confirmed N = 2 pivot on the 29 Jun decision bar: its confirmation bar is 30 Jun. No future data was read (fold cut at 29 Jun = full fold), but the engine took the counter-move's running top as the new protected origin one bar before it became a swing. | Fix written and tested — **held: it changes a golden** (`test_decision3_flip::test_real_29_sep…`). Not committed. Waiting for the lead / Abhi. |
| F3 | N = 3 reads UP all through the 61,765 → 49,955 fall; N = 1 reads NEUTRAL from March. | Logged as fragility. N stays 2 (Abhi L1-c). |

## F1 — why Apr–Jun reads DOWN although plain Dow shows HH / HL

### The rule (code and method)

Method §2 b): "Daily: the trend (degree-aware Dow structure). A correction in progress does not change the trend; the trend stays that
of the impulse before it." §3 Degree: "Every comparison uses swings of the same degree."

Code (`decision3/daily.py`, `fold_impulse`, line numbers at 0e48a7c):

1. `daily.py:752-753` — when the Daily close goes beyond the protected impulse origin, the whole counter-move (from the impulse end to
   today's extreme) is read once: `counter_kind(i)` (`daily.py:355-386`). With `daily_leg_read = compare` it calls
   `daily_legs.compare_classify` (`daily.py:369`, `daily_legs.py:405`): the counter-move against the trend leg it corrects — bodies,
   overlap (Daily has no volume). Impulse-natured ⇒ it may break the trend; otherwise ⇒ corrective.
2. `daily.py:760, 779-784` (A1, ABC_FIX rule 1) — corrective counter-move AND the close still on the trend side of the parent (the start
   of the trend's impulse, `tstart_org`) ⇒ `porg, pcorr, phase = par, True, "correction"`: a same-degree correction; trend unchanged;
   protected = the parent (`daily.py:897`).
3. `daily.py:693-720` (Q45 / ABC_FIX rule 3) — the A1 correction ends when, after the counter-move's top, a close goes beyond the
   counter-move's last HL, or the top lies inside the sharp-fall zone (ABC_FIX rule 2, `sharp_zone`) and a close goes below that zone ⇒
   a new DOWN impulse, protected = the correction's top.
4. `daily.py:859-861` + `rev_structure` (`daily.py:617-629`) and `engine.py:510-518` (step ①, trend first) — inside the correction, an
   HL after the impulse end + a close beyond the highest H between them + an impulse-natured new leg (Q36) = Daily structure against
   the trend ⇒ step ① returns NEUTRAL: no bear call and no bull put. The trend flips only by a close beyond the parent.

### The swings used, bar by bar

| Daily close | Swings / levels the rule used | Reading after this close | Side for the next session |
|---|---|---|---|
| 23 Mar | origin 55,554 (H 18 Mar) after the Feb top 61,765; LL 51,324 | DOWN impulse (flip (a)); parent 61,765 | DOWN |
| 30 Mar | correction top 54,146 (H 25 Mar, confirmed 30 Mar); close 50,275 < 51,324 | new impulse, protected 54,146 | DOWN |
| 2 Apr | impulse end L 49,955 (confirmed 7 Apr) | impulse | DOWN |
| 8 Apr | close 55,704 > 54,146. Counter-move 49,955 → 55,778 vs the leg 54,146 → 49,955: "smaller bodies, overlapping candles" ⇒ corrective. Close < parent 61,765 | A1 correction, protected = parent 61,765 | DOWN |
| 21 Apr – 16 Jun | counter-move re-read at each new extreme (57,456 on 21 Apr; same verdict: corrective). Q45 level = last HL of the counter-move: none before 57,456 ⇒ 49,955; never closed below | correction (DOWN) | DOWN |
| 17 Jun | HL 52,783 (18 May — the lowest low after 49,955, never broken), highest H between = 57,456 (21 Apr); close 57,585 > 57,456; new leg not corrective | correction + `rev` = structure UP | **NEUTRAL** (trend first) |
| 18 – 26 Jun | same `rev`; counter-move tops 58,021 (18 Jun), 58,706 (25 Jun) — still corrective vs 54,146 → 49,955; no close above 61,765 | correction + rev | NEUTRAL |
| 29 Jun | top 58,706 lies inside the sharp-fall supply 58,394 – 59,840 (the first swing low the Feb–Mar run broke, 4 Mar); close 57,727 < 58,394 (ABC_FIX 3). Q45 level = last HL 57,075 — not closed below | new DOWN impulse, protected 58,706 (see F2) | DOWN |
| 30 Jun – 19 Oct | lows 57,457 … 53,786; every high stays at or below 58,706; no close above it | DOWN impulse / pullbacks | DOWN |

So the Apr–Jun DOWN is the A1 correction rule (an ABC up-move inside a DOWN trend: A = 49,955 → 57,456, B = 57,456 → 52,783, C =
52,783 → 58,706), and from 17 Jun to 29 Jun the side was already NEUTRAL by trend first. A flip to UP needed a close above 61,765.

### The inconsistent labels — cause and fix

Cause: every Daily chart label (`daily_swings.tag_pivots`, `charts.daily_png`, `preopen_chart.daily_png`, and the sec6 gallery script
that copied it) compared a swing with the **previous swing of the same kind, whatever its degree**. The reading compares with the swing
of the same degree:

- "LL 52,783": compared with the inner low 54,222 (5 May, inside the B leg 57,456 → 52,783). The reading's "HL 52,783" compares it
  with the impulse end 49,955 — the same-degree low. 52,783 is a higher low.
- "HH 58,597" (17 Jul): compared with the inner high 58,252 (10 Jul). The reference high after the LL 56,549 is 58,706; 58,597 does not
  go beyond it.

Corrected rule (`decision3/daily_swings.py::tag_pivots`, display only, the reading is unchanged): a swing is compared with the
structure's reference swing of the same kind. A high beyond the reference high = HH: it becomes the reference, and the reference low
becomes the lowest low between the old reference high and it (the low that break started from). A low beyond the reference low = LL
(mirror). A swing that stays inside is an inner swing (LH / HL) and never moves the references. With opens / closes, a swing that
reaches the reference swing candle's own area without going beyond = EQH / EQL (C-13, `daily.c13_equal`, L1-b). It is the same Dow
comparison the reading uses (protected = the swing a break started from), no number.

Labels that change on BANKNIFTY Jan – Oct 2026 (all other labels unchanged):

| Swing | Old | New | Reference |
|---|---|---|---|
| H 61,679 (19 Feb) | HH | EQH | 61,765: inside its candle's area, not beyond |
| L 52,783 (18 May) | LL | **HL** | 49,955 |
| H 58,581 (7 Jul) | LH | EQH | 58,706: inside its candle's area (58,494 – 58,706) |
| H 58,597 (17 Jul) | HH | **EQH** | 58,706: inside its area, not beyond |

The 29 Jun reading text also says "close beyond the counter-move's last HL 58,393.55"; 58,393.55 is the sharp-fall zone's lower edge,
not an HL (D-SIDE-3). That wording is corrected inside the held F2 fix (same code branch), so it waits with it.

## F2 — the 29 Jun panel: no look-ahead?

- 58,706 = the high of 25 Jun (Daily bar 2843). An N = 2 pivot is confirmed at the close of the second bar to its right
  (`daily.py:95-105`): right bar 1 = 29 Jun (high 58,318), right bar 2 = 30 Jun (high 58,012) ⇒ **confirmed at the 30 Jun close**.
- The decision bar is 29 Jun: only one of the two right-hand bars existed. **58,706 was not a confirmed pivot at the decision.**
- Data look-ahead: none. The fold cut at the 29 Jun close gives exactly the full fold's 29 Jun state (same trend, phase, protected).
  The engine read the counter-move's running top (`daily.py:695`: the highest high since the impulse end) and made it the protected
  origin (`daily.py:706`, `top = piv("H", tb)`) — the only branch of the Daily reading that takes a turn as a swing before its
  confirmation (every other branch uses `confirm_bar ≤ i`). It also stamps that protected with `confirm_bar` = 25 Jun.
- It is a bug against §3 Swing (a turning point the following structure respects; the swings of the reading are the confirmed ones).
- Fix (written, tested, **not committed**; patch at scratchpad `dailyF/F2_confirmed_top.patch`): the correction's top becomes the new
  protected origin only when it is a confirmed Daily swing at that bar; the why names the right level (D-SIDE-3).
- Effect on the BANKNIFTY six-month side strip (F3 chart row 2): only the 29 Jun close changes, DOWN → NEUTRAL (the 30 Jun session; the
  DOWN start moves to the 30 Jun close, protected still 58,706). Over all BANKNIFTY history 35 Daily closes change side (single-bar
  delays in 2019, 2021, 2022, 2024; a longer stretch Jan – May 2023, because a one-day dip of Nov 2022 had been taken as the protected
  origin).
- **STOP — golden changed.** With the fix, `tests/test_decision3_flip.py::test_real_29_sep_new_low_flip_on_the_swing_confirmation_with_the_daily_warmup`
  fails: the NIFTY 22,725 – 22,810 prior-Daily level (`a:D-prior`, built with the Daily warm-up) is no longer born. The same test passes
  without the fix (68 / 68). Golden expectations are not edited. I did not investigate the NIFTY Daily states further (that Daily
  history includes the sealed holdout as level history). Decision needed from Abhi / the lead.

## F3 — N sensitivity (fragility)

Same data, display only (F3 chart):
- N = 3: the Feb – Apr fall 61,765 → 49,955 is read as a same-degree correction of the 2025 uptrend (parent 47,703 held) ⇒ **UP** (bull
  put) all through the fall and the whole replay window.
- N = 1: trend first NEUTRAL from March on (no trade side).
- N = 2: DOWN with a NEUTRAL stretch 17 – 29 Jun.

The six-month side depends strongly on the pivot size. This is a fragility of the reading, logged (D-SIDE-2 / F3). N stays 2 (Abhi
L1-c, his provisional setting; changed only by him on the dashboard).

## Tests

- New: `tests/test_decision3_daily_swings.py::test_structure_tags_compare_with_the_same_degree_reference_not_an_inner_swing` and
  `::test_structure_tags_equal_by_c13_area_only_with_opens_and_closes` (both mirrors, the two review cases in synthetic form).
- Layer-1 / display suites green with the label fix: `test_decision3_daily_swings`, `test_decision3_daily_review`,
  `test_decision3_vision_audit`, `test_decision3_chart_declutter`; the 21 suites that touch the Daily reading / labels / charts
  (daily_q15, daily_review, daily_swings, abc_fix, q49, q22_q34, trend_first, pa_daily_leg_read, method_no_numbers,
  reader_no_new_thresholds, preopen_charts, volume_pane, layer6_output_consistency, chart_reading_report, telegram, …): 515 passed,
  9 xfailed. Golden `test_decision3_flip`: 68 / 68 on the base (the label fix does not touch the reading). The full suite did not
  finish inside 50 minutes on the shared machine — CI runs it.
- F2 fix (held): layer-1 suites green except the golden above.
