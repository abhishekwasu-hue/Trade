# V22 setups after PR A — trend-first audit (NIFTY 15M, 2015-01 … 2024-03, pre-holdout)

Abhi (TRADE_SESSION_DECISIONS_SENSEX_SETUPS_CD14 §2): the 30 setups are **not accepted yet**. 2020-11-04 (bear call against a
six-month advance) breaks the hard rule "trend first". This report: the diagnosis, the audit of all 30, the root-cause fix, the re-run.
Data: `nifty50_1min.parquet` 2015-01-09 … 2024-03-27 (no holdout row; asserted). No P&L and no post-setup bar is used anywhere.

## 1. 2020-11-04 (bear call, 10:00 and 15:00) — diagnosis

Daily state the engine had (known at the 2020-11-03 close):

| field | value |
|---|---|
| trend / phase / counter | **DOWN** / correction / `candidate` (same-degree correction, not A1) · leg label c |
| protected origin | H **12,151** (2020-02-20 — start of the last same-degree down leg) |
| parent (trend start) | H 12,430 (2020-01-20) |
| impulse end | L 7,512 (2020-03-24) |
| counter-move reading | none on this day — Q49 wave A / alt: none / none |
| caps | none: origin_risk no (high 11,9xx is 1.3 σ_D from 12,151; B1 needs 0.5 σ_D), mature no, Weekly also DOWN |

Why it read DOWN:
1. **Q15**: the trend changes only after a Daily close beyond the protected origin, plus an opposite impulse. The origin was 4,639 points
   above the low. The first close above it came on 2020-11-06. Until then, every day stayed "DOWN", whatever the counter-move did.
2. **The counter-move is never read before that close.** The ABC_FIX / Q49 branch (`counter_kind`) runs only when `pcorr` is set or
   after a close beyond the origin. So from 2020-04-22 to 11-05 the rally was a "correction candidate" and nothing else.
3. When the engine did read it (2020-11-06), `read_counter` called 7,512 → 12,023 a **zigzag** (A 7,512–9,889, B 8,808, C 8,808–12,023).
   The 5-wave reduction (7,512 / 9,889 / 8,808 / 11,794 / 10,791 / 12,023) passes the hard impulse rules, but the sub-waves of waves 1
   and 3 do not verify as motive. That made it "corrective", so the state became an A1 correction with parent 12,430. Q49 (b)
   `unfolded_123` = False. The trend flipped only on 2020-11-09 (close 12,468, above the parent).
4. At the Q22 degree, the rally's internal pullbacks (largest 1,081) are smaller than the down leg's largest internal bounce. So for
   the trend label the whole rally is **one** same-degree leg. The higher highs and higher lows on the Daily swings (N = 2: 8,808 →
   10,328 / 9,545 → … → 12,023 / 10,791 → 11,536) never reached the gate.

The rule that let the bear call through: `engine.step1` (①) looks only at `st.trend`, so DOWN ⇒ bear call. A same-degree correction
`candidate` has no cap and no block. Caps exist only for A1 (B), origin_broken (B), Weekly against (B — Weekly was DOWN as well),
origin_risk and mature (weak). The level-bots gate (`bots_common/level_reaction`) had the same gap.

## 2. Audit rule (declared before any row was computed — `scripts/setups_trend_audit.py`)

Daily sessions strictly before the setup day, last 126 (~6 months). Fractal swings, N = 5 each side, confirmed inside the window,
alternating (same kind twice ⇒ the more extreme one). The last two swing highs and the last two swing lows give HH + HL ⇒ **UP**,
LH + LL ⇒ **DOWN**, anything else ⇒ RANGE. Flags (row = ambiguous, Abhi to confirm): `few` swings; `mixed` (RANGE); `broken`
(the last close is already beyond the latest opposite swing); `equal` (two highs or two lows within 0.25 × median 10-day range = the
engine's RANGE tol). Verdict: bull put needs UP, bear call needs DOWN; against ⇒ **FAIL**; RANGE ⇒ ambiguous.
**This is the rule's reading, not Abhi's. Abhi confirms it.**

## 3. Audit — the 30 setups (before fix)

| # | setup (15M) | side | Daily as read by the engine | 6-month rule (H1→H2 / L1→L2) | verdict | reason |
|---|---|---|---|---|---|---|
| 1 | 2015-03-10 10:30 | bull put | UP impulse (pullback) · prot 8,670 | RANGE (LH 8,997→8,913, HL 8,472→8,670) | ambiguous | mixed |
| 2 | 2015-08-10 10:45 | bear call | DOWN impulse (pullback) · prot 8,655 | UP `equal` (HH 8,561→8,655, lows 8,316→8,322) | FAIL* | the "HL" is +6 pts (equal lows); engine DOWN from a larger-degree LH |
| 3 | 2017-03-27 12:45 | bull put | UP impulse · prot 8,328 | UP | pass | |
| 4–5 | 2017-11-08 10:15, 13:30 | bull put | UP impulse · prot 9,688 | UP `equal` (lows 9,686→9,688) | pass | |
| 6–9 | 2018-03-05 12:00, 13:15, 13:30, 13:45 | bull put | UP correction candidate (e) · prot 10,076 | RANGE (HH 10,552→11,171, LL 10,405→10,282) | ambiguous | mixed |
| 10–11 | 2018-05-16 10:15, 15:00 | bull put | UP impulse · prot 9,952 | RANGE (HH 10,479→10,784, LL 10,142→9,952) | ambiguous | mixed |
| 12–13 | 2018-06-19 11:45, 13:15 | bull put | UP impulse (pullback) · prot 9,952 | UP | pass | |
| 14 | 2019-09-03 10:45 | bull put | UP impulse (new leg after the A1 correction closed 2019-08-26) · prot 10,638 | DOWN (LH 11,707→11,181, LL 10,783→10,638) | **FAIL** | Q45 ended the Jun–Aug A1 correction on a close above its last N = 2 LH (10,740); the N = 5 LH 11,181 is intact |
| 15 | 2019-09-25 10:45 | bull put | UP impulse (pullback) · prot 10,638 | RANGE (LH 11,181→11,142, HL 10,638→10,747) | ambiguous | mixed |
| 16–17 | 2020-11-04 10:00, 15:00 | bear call | DOWN correction candidate (c) · prot 12,151 | UP (HH 11,618→12,023, HL 10,791→11,662) | **FAIL** | the defect (§1) |
| 18–19 | 2020-11-20 11:15, 11:30 | bull put | UP impulse · prot 11,536 | UP | pass | |
| 20 | 2021-11-11 11:30 | bull put | UP correction candidate (e) · prot 17,453 | UP | pass | |
| 21 | 2022-01-20 14:45 | bull put | UP impulse (pullback) · prot 16,410 | DOWN `broken` (close 17,941 > LH 17,639) | FAIL* | the rule's DOWN was already broken by close |
| 22 | 2022-02-07 12:30 | bull put | UP correction candidate (b) · prot 16,410 | UP | pass | |
| 23 | 2022-03-14 13:30 | bull put | UP A1 correction (e) · parent 7,512 (Mar-2020 low) · cap B | DOWN `equal` (LH 18,351→17,794, lows 16,838→16,810) | FAIL* | equal lows; close 16,620 below both |
| 24–27 | 2022-03-28 09:45, 10:45, 12:00, 12:15 | bull put | UP impulse (new leg after A1 closed) · prot 15,672 | DOWN (LH 18,351→17,794, LL 16,838→15,672) | **FAIL** | same as #14: Q45 completion on the last N = 2 LH; the N = 5 LH 17,794 is intact |
| 28 | 2022-04-25 10:00 | bull put | UP impulse (pullback) · prot 15,672 | RANGE (HH 17,794→18,095, LL 16,838→15,672) | ambiguous | mixed |
| 29 | 2022-09-16 14:30 | bull put | UP origin_broken (e) · prot 17,453 · cap B | RANGE (LH 17,989→17,777, HL 15,859→17,168) | ambiguous | mixed |
| 30 | 2022-11-15 11:15 | bull put | UP origin_broken (e) · prot 17,453 · cap B | DOWN `broken` (close 18,320 > LH 17,428) | FAIL* | the rule's DOWN was already broken by close |

Before fix: **9 pass · 10 ambiguous (RANGE) · 11 FAIL**. Of the 11, 7 are clean (2019-09-03; 2020-11-04 ×2; 2022-03-28 ×4) and 4 carry a
rule flag (`*` — equal / broken; Abhi to confirm).

## 4. Fix (root cause, no thresholds, no dates)

`decision3/daily.py`: the engine already has a structural reading of "the Daily has turned": the flip test Q29 (अ). After the
impulse end it needs an opposite HL (LH in an UP trend) that is not violated afterwards, a Daily close beyond the swing high
(low) before it, and a leg with impulse nature (Q36 / Q28 gate). Until now this test ran only after the origin was closed beyond. It now
also runs while the counter-move is a **same-degree** correction (phase `correction` — candidate or A1 — or `origin_broken`). The
result is `DState.rev = (HL, high)`. A lower-degree pullback inside the impulse is not trend-degree structure, so it is not read there.
Trend, phase, protected and parent are unchanged (Q15 intact; verified: 0 state changes, §6).
Review fix (PR #305): for this structure reading, **any** Daily close beyond the swing high after the HL formed counts (bars ≤ today,
no lookahead). Earlier it had to be today's close. So the structure persists when today's close dips back under the swing while the
HL is intact (Dow: until the HL breaks). Before this fix, NIFTY 2020-05-18/19 inside the defect rally reopened the bear side. The
reading clears only when a wick goes through the HL or the impulse makes a new extreme (imp_end moves). The structure is anchored
at the trend-direction extreme reached after imp_end, so a provisional restore that moves imp_end back to an earlier leg no longer
drops it (2021-11-24). The flip itself keeps its same-day close test and the imp_end anchor. Fixture: `staircase_dip_back`.
On the previous commit it gives rev = None; now it stays blocked.
Level bots: the daily trend cache now carries `engine` = `TREND_CTX_VERSION`, so a cache written today by older code is recomputed
and not reused after deploy.

`decision3/engine.py` ①: `st.rev` set ⇒ **trade नाही**. The trend side is blocked: "trend first — Daily structure UP" for a bear
call, and DOWN for a bull put. The other side is blocked too, because the trend has not flipped. This is a gate (H1), not a cap.
The same gate is applied in `bots_common/level_reaction.context_from_state` (level bots), in the Daily caption (`daily_swings.trend_line`)
and in `DD.describe`. Fixture: `tests/elliott_fixtures.staircase_below_origin` (a staircase of higher highs and higher lows below the
protected origin, plus a version that breaks down to a new low). Tests: `tests/test_decision3_trend_first.py` (12 cases, down + up).
On origin/main the fixture gives "Daily DOWN ⇒ bear call" (UP ⇒ bull put); after the fix it gives "trade नाही".

## 5. After fix — one V22 re-run (branch `claude/setups-audit`, same data and range, holdout asserted absent)

56,765 bars: setup 30 ⇒ **28**, no_trade 922 ⇒ 16,682 (the "structure against trend" gate blocks 15,770 bars on 654 sessions),
wait 55,813 ⇒ 40,055, mature bars 20,170 (unchanged). This is the re-run after the PR #305 review fix. The first fix gave the same
28 setups with 12,720 blocked bars on 546 sessions. **Removed: 2020-11-04 10:00 and 15:00. Added: none.** The other 28 rows
are unchanged (same conviction, cap and phase). Note: origin/main moved between the 30-setup run and this one (Q49 merged), and it
changed none of these rows.

Re-audit with the same rule (§2): **9 pass · 10 ambiguous · 9 FAIL**. The rows are the same as in §3 without #16–17. Remaining FAILs:

| rows | why it is not fixed here |
|---|---|
| 2019-09-03; 2022-03-28 ×4 (clean) | Degree of "structure". The engine reads Daily swings at N = 2 (spec ①). By Q45 the A1 correction ends on a close beyond the counter-move's **last** N = 2 swing, which starts a new UP leg. The audit rule uses N = 5 swings over 6 months and still sees LH + LL. Both readings follow rules that already exist; choosing one is Abhi's decision (TF3 / TF4). |
| 2015-08-10, 2022-01-20, 2022-03-14, 2022-11-15 (`*`) | The rule itself is ambiguous: equal lows (6 and 28 points) or a DOWN reading already broken by the close. Abhi confirms each row (TF5). |

So 7 ⇒ 28 is **not yet acceptable** under Abhi's condition ("only if every remaining setup passes"). 9 rows wait for TF3–TF5,
and option T2 below would remove exactly these 9. Under the a–f columns (§8) no row passes yet; those fixes are on other branches.
Review charts for the 28 were rendered locally but **not committed** to trade-data, because they have no volume pane yet (Abhi:
"VOLUME ON EVERY CHART", `claude/chart-volume`). Regenerate them after a2 / c0 / c1 are in decision3.

## 6. Daily before / after (`decision3.daily.fold`, origin/main vs this branch)

| symbol | days | trend / phase / counter / protected / parent / wave A / leg / mature / target / origin-risk changes | trend-change days | new "structure against trend" days |
|---|---|---|---|---|
| NIFTY (2015-01-09 … 2024-03-27) | 2,282 | **0** | **0** | 633 (UP trend 378, DOWN trend 255; all in phase correction) — 510 before the review fix |
| BANKNIFTY (2016-10-10 … 2026-10-09) | 2,479 | **0** | **0** | 716 (UP 500, DOWN 216; 1 in origin_broken) — 535 before; last day: DOWN impulse, no flag |

NIFTY spans include 2020-04-22 … 2020-11-06 (the defect), 2016-05 … 10 (a DOWN label through the 2016 advance) and
2018-10 … 2019-03 (an UP label through the late-2018 fall). BANKNIFTY: 2026-06-17 … 25 (the a-b-c advance, c above a).

Tests: `pytest -q tests/test_decision3*.py tests/test_elliott_correction_library.py tests/test_level*.py` ⇒ **570 passed, 9 xfailed** (after the PR #305 review fix).
These are the same 9 xfails as on main. No golden or correction-library expectation was edited. The new
`tests/test_decision3_trend_first.py` (12 tests) and the level cache-version test are included.

## 7. Open questions (OPEN_QUESTIONS TF1–TF7)

- **TF1** The gate reads the counter structure on the Daily swings (N = 2), the same swings the flip test uses. With the Q22-filtered
  swings (trend degree) the 2020 rally is a single leg, so the defect would remain (verified: rev days 62, and 2020 was not caught).
- **TF2** A zigzag whose c closes above a (with b as a HL) is a Dow UP structure, so the c-top bear call is blocked until a wick
  breaks the b low (the HL) or a new low prints. After the review fix, a close back below the a top no longer lifts the block. The default follows Abhi's wording ("never a bear call while the structure is
  UP"). Among the 30 setups this affects only 2020-11-04. The alternative is to block only when the counter-move reads as an
  impulse, but `read_counter` called 2020 a zigzag, so the defect would stay.
- **TF3** Is the §2 rule (N = 5, 126 sessions) Abhi's "6-month structure"?
- **TF4** For 2019-09-03 and 2022-03-28 ×4, two options. T1: keep the engine degree (N = 2 + Q45), so these rows are accepted.
  T2: the gate also reads the §2 rule (opposite reading ⇒ no trade). T2 leaves 19 setups (9 pass + 10 ambiguous), but it adds a
  new swing degree (N = 5) that the engine does not use today.
- **TF5** The rule-ambiguous rows (equal / broken): Abhi decides each one.
- **TF6** Level bots use the same gate (`structure_against` ⇒ no new entries). The default is yes, as fail-safe.
- **TF7** The definitions behind the diagnostic columns in §8: swing sizes and lookbacks, "edge touch", and the provisional trail.
## 8. Audit columns a–f (Abhi §2 a–f, reviews of #23 and #24) — all 30, diagnostic only

`scripts/setups_audit_columns.py <rows.pkl> <1m parquet>` reads the finished V22 run and recomputes evidence with the existing
decision3 functions (`method.zone_study`, `method.commitment(win=…)`). It changes no engine decision. It uses only bars up to the
setup bar. Definitions are in the script docstring. In short:
- (a) Nearest unbroken opposite swing between entry and target: 15M (N 3, 5 sessions), 1H (N 2, 20 sessions), Daily (N 2, 126
  sessions), plus Daily swing lows broken by a close since (flipped supply; mirror for bear). R:R is recomputed to it; < 3 ⇒ ✘.
- (b) ✘ when the K touched only the edge of the area (≤ 2 candles, extreme in the near half), or when the area was broken inside
  the current pullback window (immediate retest, no impulse away first), or when the far side was never reclaimed.
- (c) Crossings = 15M closes switching side of the band in 5 days; chop setting `chop_max_crossings` 6 (sr_levels_v3) ⇒ grade C.
- (d) Provisional = the engine's `prov` stack is open, i.e. a correction completion or new leg not yet confirmed by "continuation
  confirm". It is traced from the Daily `why` events, so it is approximate. A provisional origin with conviction A ⇒ ✘.
- (e) ✘ unless a2 = handover **and** c0 body is dominant (≥ `commit_dom_mult` 1.5 × window average).
- (f) ✘ unless a 5M close went beyond the last 5M swing before the pullback extreme (CHoCH).

**Volume: NA for every row.** The NIFTY spot 1m has volume 0. The futures intraday volume in trade-data starts 2026-09; the
2015–2024 data has only daily bhavcopy (LB23). So c0 volume and the a2 volume sub-tests cannot run, and the grade cap is B.

**Fix in progress on other branches (not in this one):** `claude/v22-confirmation` covers a2 / c0 / c1 (LTF CHoCH) in decision3
`commitment` and the level bots. `claude/v22-areas-quality` covers (a) the HTF opposite-area target / R:R, (b) the breakout-retest vs
pullback rule, (c) the chop rule in V22, and (d) the Q45 provisional-origin cap B. `claude/chart-volume` covers the volume panes on
charts. The Q44 target is to be removed from the 15M setup chart (caption only).

| # | setup | (a) nearest opposite area between entry and target · R:R (engine) | (b) arrival | (c) crossings 5d (tests/sweeps) | (d) Daily · provisional · conv | (e) a2 · c0 body× · volume | (f) 5M at setup |
|---|---|---|---|---|---|---|---|
| 1 | 2015-03-10 10:30 BP | 15M swing high 8,794 (09-Mar 14:30) · R:R 1.23 (4.16) ✘ | breakout→retest (165 bars after break), 17 touch, depth 1.02 | 0 (8/4) | UP impulse/pullback · confirmed · B | absorption · 2.34× ok · vol NA ✘ | CHoCH by close at 10-Mar 10:30 (8,758 beyond 8,755) |
| 2 | 2015-08-10 10:45 BC | 15M swing low 8,565 (07-Aug 11:15) · R:R 0.8 (4.17) ✘ | pullback, 2 touch, depth 0.04, edge only ✘ | 0 (8/2) | DOWN impulse/pullback · provisional · A ✘ (> B) | too few bars · 1.74× ok · vol NA ✘ | against (last 5M HL 8,605 at 10-Aug 10:00, no close beyond) ✘ |
| 3 | 2017-03-27 12:45 BP | none · R:R 3.37 | breakout→retest (239 bars after break), 6 touch, depth 1.0 | 0 (1/0) | UP impulse/pullback · confirmed · B | no handover · 1.51× ok · vol NA ✘ | CHoCH by close at 23-Mar 09:40 (9,066 beyond 9,064) |
| 4 | 2017-11-08 10:15 BP | 15M swing high 10,384 (08-Nov 09:15) · R:R 0.72 (3.14) ✘ | breakout→retest (179 bars after break), 1 touch, depth 0.08, edge only ✘ | 0 (9/2) | UP impulse/pullback · provisional · A ✘ (> B) | too few bars · 3.87× ok · vol NA ✘ | against (last 5M LH 10,378 at 08-Nov 09:40, no close beyond) ✘ |
| 5 | 2017-11-08 13:30 BP | 15M swing high 10,370 (08-Nov 11:45) · R:R 0.93 (4.86) ✘ | breakout→retest (192 bars after break), 4 touch, depth 0.54 | 0 (10/2) | UP impulse/pullback · provisional · A ✘ (> B) | no handover · 1.24× not dominant · vol NA ✘ | against (last 5M LH 10,353 at 08-Nov 12:30, no close beyond) ✘ |
| 6 | 2018-03-05 12:00 BP | 15M swing high 10,514 (01-Mar 13:30) · R:R 2.83 (3.46) ✘ | pullback, 12 touch, depth 0.59 | 0 (2/0) | UP correction/candidate · provisional · B | no handover · 1.22× not dominant · vol NA ✘ | against (last 5M LH 10,358 at 05-Mar 11:25, no close beyond) ✘ |
| 7 | 2018-03-05 13:15 BP | 15M swing high 10,514 (01-Mar 13:30) · R:R 4.96 (5.95) | pullback, 17 touch, depth 0.75 | 0 (2/0) | UP correction/candidate · provisional · B | no handover · 1.02× not dominant · vol NA ✘ | against (last 5M LH 10,355 at 05-Mar 12:15, no close beyond) ✘ |
| 8 | 2018-03-05 13:30 BP | 15M swing high 10,514 (01-Mar 13:30) · R:R 3.65 (4.42) | pullback, 18 touch, depth 0.75 | 0 (2/0) | UP correction/candidate · provisional · B | no handover · 0.98× not dominant · vol NA ✘ | against (last 5M LH 10,355 at 05-Mar 12:15, no close beyond) ✘ |
| 9 | 2018-03-05 13:45 BP | 15M swing high 10,514 (01-Mar 13:30) · R:R 2.49 (3.06) ✘ | pullback, 19 touch, depth 0.75 | 0 (2/0) | UP correction/candidate · provisional · B | no handover · 1.6× ok · vol NA ✘ | CHoCH by close at 05-Mar 13:45 (10,356 beyond 10,355) |
| 10 | 2018-05-16 10:15 BP | 15M swing high 10,822 (15-May 15:00) · R:R 2.66 (5.65) ✘ | pullback, 3 touch, depth 2.12 | 0 (1/2) | UP impulse/- · provisional · B | too few bars · 5.51× ok · vol NA ✘ | against (last 5M LH 10,822 at 15-May 15:00, no close beyond) ✘ |
| 11 | 2018-05-16 15:00 BP | 15M swing high 10,790 (16-May 13:15) · R:R 0.85 (3.52) ✘ | breakout→retest (15 bars after break, immediate), 13 touch, depth 2.43 ✘ | 2 (5/2) | UP impulse/- · provisional · B | no handover · 1.63× ok · vol NA ✘ | against (last 5M LH 10,822 at 15-May 15:00, no close beyond) ✘ |
| 12 | 2018-06-19 11:45 BP | none · R:R 4.97 | breakout→retest (168 bars after break), 2 touch, depth 0.88 | 0 (1/0) | UP impulse/pullback · provisional · B | too few bars · 1.27× not dominant · vol NA ✘ | against (last 5M LH 10,747 at 19-Jun 10:50, no close beyond) ✘ |
| 13 | 2018-06-19 13:15 BP | none · R:R 3.88 | pullback, 3 touch, depth 0.95 | 0 (1/0) | UP impulse/pullback · provisional · B | too few bars · 1.86× ok · vol NA ✘ | against (last 5M LH 10,735 at 19-Jun 12:20, no close beyond) ✘ |
| 14 | 2019-09-03 10:45 BP | none · R:R 4.53 | breakout→retest (121 bars after break), 10 touch, depth 1.0 | 0 (2/0) | UP impulse/pullback · provisional · B | absorption · 0.27× not dominant · vol NA ✘ | CHoCH by close at 30-Aug 13:45 (10,963 beyond 10,954) |
| 15 | 2019-09-25 10:45 BP | Daily broken low ⇒ supply 11,615 (23-May-19) · R:R 4.36 (5.28) | pullback, 7 touch, depth 1.22 | 1 (1/1) | UP impulse/pullback · provisional · A ✘ (> B) | no handover · 0.48× not dominant · vol NA ✘ | against (last 5M LH 11,520 at 25-Sep 09:55, no close beyond) ✘ |
| 16 | 2020-11-04 10:00 BC | Daily broken high ⇒ demand 11,794 (31-Aug-20) · R:R 1.04 (3.33) ✘ | breakout→retest (0 bars after break, immediate), 3 touch, depth 2.45 ✘ | 1 (1/1) | DOWN correction/candidate · provisional · B | too few bars · 1.86× ok · vol NA ✘ | against (last 5M HL 11,783 at 04-Nov 09:15, no close beyond) ✘ |
| 17 | 2020-11-04 15:00 BC | Daily broken high ⇒ demand 11,794 (31-Aug-20) · R:R 4.73 (10.71) | pullback, 2 touch, depth 0.98 | 0 (1/0) | DOWN correction/candidate · provisional · B | too few bars · 0.36× not dominant · vol NA ✘ | against (last 5M HL 11,757 at 04-Nov 13:15, no close beyond) ✘ |
| 18 | 2020-11-20 11:15 BP | 15M swing high 12,844 (20-Nov 10:15) · R:R 3.05 (6.64) | breakout→retest (83 bars after break), 7 touch, depth 1.24 | 0 (4/1) | UP impulse/- · provisional · B | no handover · 0.17× not dominant · vol NA ✘ | against (last 5M LH 12,844 at 20-Nov 10:20, no close beyond) ✘ |
| 19 | 2020-11-20 11:30 BP | 15M swing high 12,844 (20-Nov 10:15) · R:R 2.7 (5.97) ✘ | breakout→retest (84 bars after break), 8 touch, depth 1.24 | 0 (4/1) | UP impulse/- · provisional · B | no handover · 0.1× not dominant · vol NA ✘ | against (last 5M LH 12,844 at 20-Nov 10:20, no close beyond) ✘ |
| 20 | 2021-11-11 11:30 BP | 15M swing high 18,061 (10-Nov 14:00) · R:R 5.03 (5.62) | far side, no reclaim, 9 touch, depth 1.48 ✘ | 2 (13/12) | UP correction/candidate · provisional · B | absorption · 1.04× not dominant · vol NA ✘ | against (last 5M LH 17,950 at 11-Nov 09:50, no close beyond) ✘ |
| 21 | 2022-01-20 14:45 BP | 15M swing high 17,835 (20-Jan 12:30) · R:R 1.61 (7.62) ✘ | pullback, 3 touch, depth 1.32 | 0 (2/1) | UP impulse/pullback · provisional · A ✘ (> B) | absorption · 2.59× ok · vol NA ✘ | CHoCH by close at 20-Jan 14:55 (17,716 beyond 17,708) |
| 22 | 2022-02-07 12:30 BP | 15M swing high 17,571 (04-Feb 13:45) · R:R 2.73 (5.1) ✘ | pullback, 2 touch, depth 0.37, edge only ✘ | 0 (1/0) | UP correction/candidate · provisional · B | too few bars · 1.25× not dominant · vol NA ✘ | against (last 5M LH 17,334 at 07-Feb 11:55, no close beyond) ✘ |
| 23 | 2022-03-14 13:30 BP | Daily broken low ⇒ supply 16,810 (14-Feb-22) · R:R 0.18 (3.94) ✘ | breakout→retest (4 bars after break, immediate), 1 touch, depth 0.01, edge only ✘ | 1 (6/8) | UP correction/correction · provisional · B | too few bars · 1.67× ok · vol NA ✘ | no 5M swing before the pullback extreme ✘ |
| 24 | 2022-03-28 09:45 BP | 15M swing high 17,198 (25-Mar 15:15) · R:R 1.49 (4.04) ✘ | pullback, 1 touch, depth 0.04, edge only ✘ | 0 (1/0) | UP impulse/pullback · provisional · B | too few bars · 1.0× not dominant · vol NA ✘ | against (last 5M LH 17,198 at 25-Mar 15:25, no close beyond) ✘ |
| 25 | 2022-03-28 10:45 BP | 15M swing high 17,198 (25-Mar 15:15) · R:R 3.3 (7.67) | pullback, 4 touch, depth 1.07 | 0 (2/1) | UP impulse/pullback · provisional · A ✘ (> B) | no handover · 1.21× not dominant · vol NA ✘ | against (last 5M LH 17,046 at 28-Mar 10:30, no close beyond) ✘ |
| 26 | 2022-03-28 12:00 BP | 15M swing high 17,066 (28-Mar 11:15) · R:R 0.27 (6.25) ✘ | pullback, 9 touch, depth 1.07 | 0 (2/2) | UP impulse/pullback · provisional · A ✘ (> B) | no handover · 1.74× ok · vol NA ✘ | CHoCH by close at 28-Mar 11:20 (17,055 beyond 17,046) |
| 27 | 2022-03-28 12:15 BP | 15M swing high 17,198 (25-Mar 15:15) · R:R 1.43 (3.9) ✘ | pullback, 9 touch, depth 1.07 | 0 (2/2) | UP impulse/pullback · provisional · A ✘ (> B) | handover · 3.57× ok · vol NA | CHoCH by close at 28-Mar 11:20 (17,055 beyond 17,046) |
| 28 | 2022-04-25 10:00 BP | Daily broken low ⇒ supply 17,217 (23-Nov-21) · R:R 1.69 (3.28) ✘ | breakout→retest (78 bars after break), 4 touch, depth 1.7 | 0 (1/4) | UP impulse/pullback · provisional · B | handover · 4.11× ok · vol NA | against (last 5M LH 17,200 at 22-Apr 15:05, no close beyond) ✘ |
| 29 | 2022-09-16 14:30 BP | 15M swing high 17,962 (15-Sep 14:30) · R:R 3.67 (3.77) | breakout→retest (1 bars after break, immediate), 2 touch, depth 4.78 ✘ | 2 (1/1) | UP origin_broken/- · confirmed · B | too few bars · 1.25× not dominant · vol NA ✘ | against (last 5M LH 17,612 at 16-Sep 13:25, no close beyond) ✘ |
| 30 | 2022-11-15 11:15 BP | 15M swing high 18,375 (14-Nov 14:00) · R:R 2.86 (3.74) ✘ | breakout→retest (34 bars after break), 31 touch, depth 0.93 | 1 (9/8) | UP origin_broken/- · confirmed · B | absorption · 1.07× not dominant · vol NA ✘ | against (last 5M LH 18,308 at 15-Nov 10:55, no close beyond) ✘ |

✘ counts (30 rows): (a) 18 · (b) 9 · (c) 0 · (d) 8 · (e) 28 · (f) 23. **No row passes all of a–f.** Rows #16–17 were
already removed by the trend-first fix.
- **#23** (2022-03-14 13:30): (a) ✘, because the Daily broken low 16,810 is supply 18 points above the entry (R:R 0.18). (b) ✘: a
  breakout followed by an immediate retest (break 4 bars before, 1 edge touch, depth 0.01). This matches Abhi's reading. Crossings
  in 5 days: 1 (level tests 6 / sweeps 8, not fresh), so the chop rule does not fire.
- **#24** (2022-03-28 09:45): c0 is not dominant (1.0×), the 5M is still against (LH 17,198 not closed above), and (a) ✘ against the
  15M LH 17,198 (R:R 1.49). So there is no setup at 09:45, as Abhi expected. The same area later: 12:00 has a 5M CHoCH (11:20) and a
  dominant engulf (1.74×) but no handover, and (a) ✘ (R:R 0.27 to 17,066). 12:15 passes a2 + c0 (3.57×) + CHoCH but fails (a)
  (R:R 1.43 to 17,198) and (d) (conviction A on a provisional origin).

## 9. Re-run on the merged main (13 Oct, 1396ac8 — after #305 trend-first, #308 a2/c0/c1, #309 touch / death side, #306 volume pane, 12-Oct blockers)

Same data, same range, holdout asserted absent (`scripts/v22_setup_charts.py run`, 56,765 bars, 459 s). No setting was changed for this
run. Charts (Daily + 15M + 5M, volume pane under each; intraday volume NA, Daily = bhavcopy near-month FUT from 2018-12) and the
machine-readable audit are in trade-data `review/v22/setups_prA_v2/` (commit ebe254e; manifest tag `debug` — not for Telegram until Abhi has audited).

| run | setup | wait | no_trade |
|---|---|---|---|
| §3 before PR A fixes (prA_v1) | 30 | 55,813 | 922 |
| §5 trend-first only (#305) | 28 | 40,055 | 16,682 |
| a2/c0/c1 only (`v22_confirmation_c1.md`, on the pre-#305 base) | 8 | 55,873 | 884 |
| **merged main (this run)** | **14** | 39,024 | 17,727 |

**The 14 setups.** 4 are from the confirmation run's 8 (2017-11-08 13:30, 2022-03-14 13:30, 2022-03-28 12:00 and 12:15) — all of them
were in the original 30. **10 are new bear calls, none in the original 30**, all grade B (volume NA): 2015-08-03 13:00, 2015-11-20 12:15 /
13:30, 2016-02-18 11:15, 2016-04-12 13:15 / 13:30, 2017-01-24 11:30 / 12:45, 2020-04-08 11:30, 2020-04-09 10:45. Why they appear now
(engine fields + one what-if, `level_death_side = "role0"`, decide() on these bars only — `role0_whatif.json`): 7 of the 10 carry
`mature_step_down` — the Daily impulse was mature, which until the 12-Oct blockers change capped the bar at "weak" (wait, whatever
③–⑦ said) and now only steps the grade down (D12-1: maturity is evidence). 2015-08-03 is a death-side row: with `role0` the area
8,551–8,561 (born a:D2+c) is dead and the bar waits ("no touch"); with `role` (TL1, Abhi approved) it lives. 2020-04-08 / 09 are **not**
death-side rows (with `role0` they are still setups) and not maturity rows; which of the other merged changes (#309 touched-level
ranking, 12-Oct blockers evidence window / areas, #305) opened them was not isolated here.

**The 4 confirmation-run setups that are gone:** 2018-03-05 13:45, 2018-05-16 10:15 and 2018-06-19 13:15 now end at ⑦ **R:R < 3**
(2.71 / 1.34 / 1.28) — a2 / c0 / c1 still pass, but the area is a different, wider merged band (10,295–10,424 born a:D2+b+a:D+c with
13 sweeps, vs 10,303–10,388 under `role0`), so the SL sits further away. The what-if confirms it: with `level_death_side = "role0"`
all three are setups again. So TL1 (approved) and the merge rule (TL2) together cost these three; they are the concrete rows for TL2.
2022-01-20 14:45 ends at ③ ("no trend-direction impulse / origin broken" — K not open) under both death rules — not isolated here.
#24 (2022-03-28 09:45) still waits — "commitment not dominant (1.0×)" — as Abhi expected (`lost_rows_decide.json`).

**Trend audit (§2 rule, unchanged):** 6 pass · 2 ambiguous · 6 FAIL. New FAIL rows: 2015-08-03 (engine DOWN impulse; rule UP — HH
8,561 → 8,655, HL 7,941 → 8,316) and 2015-11-20 ×2 (engine DOWN correction candidate; rule UP — HH 8,055 → 8,335, HL 7,540 → 7,691).
Both are bear calls inside a Daily advance that the trend-first gate (`rev`) did not catch — the same degree question as TF1 / TF4 (the
rule's N = 5 swings vs the engine's N = 2 + Q45). 2017-01-24 ×2 pass with the `broken` flag (rule DOWN already broken by the close).
2022-03-14 and 2022-03-28 ×3 FAIL as in §5. 2020-04-08 / 09 pass (rule DOWN) — but they are bear calls in the 2nd / 3rd week of the
2020-03-24 rebound; Abhi reads them (TF8).

**Audit columns a–f (same script, same definitions as §8):**

| # | setup | area | (a) nearest opposite area between entry and target · R:R (engine) | (b) arrival | (c) crossings 5d (tests/sweeps) | (d) Daily · provisional · conv | (e) a2 · c0 body× · volume | (f) 5M at setup |
|---|---|---|---|---|---|---|---|---|
| 1 | 2015-08-03 13:00 BC | 8,551–8,561 | 15M swing low 8,511 (03-Aug 09:15) · R:R 0.99 (6.01) ✘ | breakout→retest (0 bars after break, immediate), 15 touch, depth 1.25 ✘ | 1 (6/6) | DOWN impulse/pullback · provisional · B | no handover · 3.6× ok · vol NA ✘ | CHoCH by close at 03-Aug 13:00 (8,549 beyond 8,555) |
| 2 | 2015-11-20 12:15 BC | 7,897–7,938 | 15M swing low 7,818 (20-Nov 09:45) · R:R 1.37 (3.14) ✘ | pullback, 6 touch, depth 0.24 | 0 (18/7) | DOWN correction/candidate · provisional · B | handover · 3.19× ok · vol NA ✘ | CHoCH by close at 20-Nov 12:20 (7,889 beyond 7,893) |
| 3 | 2015-11-20 13:30 BC | 7,897–7,938 | 15M swing low 7,880 (20-Nov 12:30) · R:R 0.17 (3.19) ✘ | pullback, 10 touch, depth 0.24 | 0 (19/7) | DOWN correction/candidate · provisional · B | handover · 1.75× ok · vol NA ✘ | CHoCH by close at 20-Nov 12:20 (7,889 beyond 7,893) |
| 4 | 2016-02-18 11:15 BC | 7,194–7,199 | 15M swing low 6,994 (17-Feb 13:15) · R:R 3.37 (3.71) | breakout→retest (0 bars after break, immediate), 9 touch, depth 4.43 ✘ | 3 (2/3) | DOWN impulse/pullback · provisional · B | absorption · 2.5× ok · vol NA ✘ | CHoCH by close at 18-Feb 11:25 (7,168 beyond 7,180) |
| 5 | 2016-04-12 13:15 BC | 7,667–7,726 | 15M swing low 7,679 (12-Apr 10:15) · R:R 0.5 (4.95) ✘ | breakout→retest (133 bars after break), 19 touch, depth 0.84 | 0 (34/9) | DOWN correction/candidate · provisional · B | no handover · 2.16× ok · vol NA ✘ | CHoCH by close at 12-Apr 13:25 (7,696 beyond 7,701) |
| 6 | 2016-04-12 13:30 BC | 7,667–7,726 | 15M swing low 7,679 (12-Apr 10:15) · R:R 0.07 (3.26) ✘ | breakout→retest (134 bars after break), 20 touch, depth 0.84 | 0 (34/9) | DOWN correction/candidate · provisional · B | handover · 4.19× ok · vol NA ✘ | CHoCH by close at 12-Apr 13:25 (7,696 beyond 7,701) |
| 7 | 2017-01-24 11:30 BC | 8,414–8,460 | 15M swing low 8,351 (23-Jan 13:30) · R:R 2.65 (3.32) ✘ | pullback, 10 touch, depth 0.61 | 0 (2/1) | DOWN impulse/pullback · provisional · B | no handover · 1.99× ok · vol NA ✘ | CHoCH by close at 24-Jan 11:30 (8,434 beyond 8,434) |
| 8 | 2017-01-24 12:45 BC | 8,414–8,460 | 15M swing low 8,429 (24-Jan 11:30) · R:R 0.17 (3.62) ✘ | pullback, 15 touch, depth 0.67 | 0 (2/1) | DOWN impulse/pullback · provisional · B | no handover · 1.68× ok · vol NA ✘ | CHoCH by close at 24-Jan 12:50 (8,431 beyond 8,433) |
| 9 | 2017-11-08 13:30 BP | 10,321–10,333 | 15M swing high 10,370 (08-Nov 11:45) · R:R 0.93 (4.86) ✘ | breakout→retest (192 bars after break), 4 touch, depth 0.54 | 0 (10/2) | UP impulse/pullback · provisional · B | no handover · 1.24× not dominant · vol NA ✘ | still against (last 5M LH 10,353 at 08-Nov 12:30, no close beyond) ✘ |
| 10 | 2020-04-08 11:30 BC | 8,949–9,038 | 15M swing low 8,658 (08-Apr 09:15) · R:R 0.9 (4.04) ✘ | breakout→retest (0 bars after break, immediate), 8 touch, depth 2.03 ✘ | 1 (1/2) | DOWN impulse/pullback · provisional · B | no handover · 3.28× ok · vol NA ✘ | CHoCH by close at 08-Apr 11:40 (8,889 beyond 8,900) |
| 11 | 2020-04-09 10:45 BC | 8,949–9,038 | 15M swing low 8,700 (08-Apr 14:00) · R:R 1.1 (3.89) ✘ | breakout→retest (22 bars after break, immediate), 15 touch, depth 2.03 ✘ | 2 (2/2) | DOWN impulse/pullback · provisional · B | no handover · 1.8× ok · vol NA ✘ | CHoCH by close at 08-Apr 11:40 (8,889 beyond 8,900) |
| 12 | 2022-03-14 13:30 BP | 16,701–16,757 | Daily broken low ⇒ supply 16,810 (14-Feb-22) · R:R 0.18 (3.94) ✘ | breakout→retest (4 bars after break, immediate), 1 touch, depth 0.01, edge only ✘ | 1 (6/8) | UP correction/correction · provisional · B | too few bars · 1.67× ok · vol NA ✘ | no 5M swing before the pullback extreme ✘ |
| 13 | 2022-03-28 12:00 BP | 17,006–17,039 | 15M swing high 17,066 (28-Mar 11:15) · R:R 0.27 (6.25) ✘ | pullback, 9 touch, depth 1.07 | 0 (2/2) | UP impulse/pullback · provisional · B | no handover · 1.74× ok · vol NA ✘ | CHoCH by close at 28-Mar 11:20 (17,055 beyond 17,046) |
| 14 | 2022-03-28 12:15 BP | 17,006–17,039 | 15M swing high 17,198 (25-Mar 15:15) · R:R 1.43 (3.9) ✘ | pullback, 9 touch, depth 1.07 | 0 (2/2) | UP impulse/pullback · provisional · B | handover · 3.57× ok · vol NA ✘ | CHoCH by close at 28-Mar 11:20 (17,055 beyond 17,046) |

✘ counts (14 rows): (a) 13 · (b) 5 · (c) 0 · (d) 0 · (e) 14 · (f) 2. **No row passes all of a–f.** (a) fails on 13 of 14 — the nearest
15M opposite swing between entry and target gives R:R < 3 everywhere except 2016-02-18 (3.37); (e) fails everywhere because volume is NA
in 2015–2024 (LB23) — with volume ignored, (e) would pass on 4 rows (handover + dominant: 2015-11-20 ×2, 2016-04-12 13:30, 2022-03-28
12:15). (d) is 0 now because every setup is grade B (volume NA cap), so "conviction A on a provisional origin" cannot occur.
**Definition note (TF7):** for #9 (2017-11-08 13:30) the audit's (e) says "1.24× not dominant" and (f) "still against", while the
engine's ⑥ passed (engulf 2.42×, 5M CHoCH via sweep-and-reclaim at 13:40). The column script uses its own arrival bar and a plain N = 2
5M swing (LB25 / LB26 differ: sweep of the study-window low, last 1-bar LH); it is diagnostic and was not changed here.

Not done here: no threshold, merge rule or gate was touched. The rows go to Abhi (TF8); the TL2 merge-width question now has 3 concrete
2018 rows.
