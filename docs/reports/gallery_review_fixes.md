Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# Gallery review fixes — report (owner-orders INBOX 24 Oct; DECISIONS 60–69)

## A — lifecycle (A1, A2, A3, A4, A8)

**मराठी सारांश (Abhi साठी).** BREAK-1 (तुमचा नियम, DECISIONS 60 / 69) code मध्ये बसवला: area आणि line दोन्हींसाठी एकच नियम —
पलीकडे close **आणि** पलीकडे pullback swing तयार होऊन टिकला (resistance वर तुटला ⇒ वर pullback low) तरच BROKEN; नाहीतर sweep, object
जिवंत ("reclaimed"). Broken back ⇒ DEAD (area आणि line दोन्ही). Approach side: पलीकडे hold नसलेले closes = sweep ⇒ break बाजूनेच
approach. Stamps = ज्या bar ला अवस्था कळली ती bar. तुमचे proof cases: X01 = sweep ✓ (E4 (b) नाही), 2.3 / 2.4 = 17 Jul poke sweep,
resistance जिवंत ✓. **एक प्रश्न तुमच्याकडे (A-L1):** "pullback swing" कोणत्या degree चा? D1 (मान्य 15M structure) घेतला तर 2.17 (तुमचं
textbook retest) तुटलेलंच वाचलं जात नाही; D0 (प्रत्येक 15M वळण) घेतलं तर 2.17 बरोबर, पण NIFTY 12 Oct golden zone गायब होतो. दोन्हीत
golden बदलतात ⇒ golden न बदलता थांबलो. Replay चे आकडे खाली (D1, default).

### What BREAK-1 says (owner rule) and how it is built
- `decision3/settings.py` `break_hold_rule = hold` (default; registered; `swing_beyond` = the earlier reading, what-if only, reproduces
  code 0e48a7c exactly). `decision3/flip.py` `hold_rule`, `hold_kind`.
- **BROKEN** = a close beyond AND a swing of the hold side (`hold_kind`: up ⇒ a pullback LOW above the object; down ⇒ a pullback HIGH
  below it) formed during the excursion and CONFIRMED while every close is still beyond — the confirming bar too (a break-known bar
  that already closed back = no hold: the #373 lesson applied to the break itself and to lines).
- **SWEEP** = beyond and back without that (the push's own extreme beyond — the earlier "swing beyond" — is never a hold). The object
  stays alive ("reclaimed" wording). Reaching the far-side swing on a push that never held is no flip; the flip comes with the hold.
- **BROKEN BACK ⇒ DEAD** = the same test opposite (a close back on the original side + a hold swing there, confirmed while still
  back). Areas and lines alike — the earlier area "reclaim" (back to the old role) is gone (what-if only).
- **Approach side (A3, DECISIONS 61)**: `entry_models.Reader.accepted_on_original_side` — the revisit / the rejection candle's open
  counts as "from the original side, accepted" only when the run of closes there held a hold swing (confirmed by that bar); marginal
  closes without it are a sweep ⇒ still the approach from the break side. 15M and 5M paths (5M: the 15M structure at the 5M close).
- **Stamps (A8, DECISIONS 63)**: every engine event is appended at the bar it became known (unchanged); lines now stamp "broken" at
  `break_known_at` (not the first close) and "dead (broken back)" at its KNOWN bar (`broken_back_at(known=True)`, not the attempt's
  first close); area charts show the base candle and the state; wording "reclaimed" = alive, "dead" = dead
  (`decision3/reading_gallery.py`).
- Hold swing degree (provisional, A-L1): the structure's finest degree (Abhi's approved D1, `Levels._known0`) for areas AND lines.

### A1 — break definition (areas and lines disagreed)
| | today (0e48a7c) | BREAK-1 |
|---|---|---|
| area break | `levels.py:604` `_swing_beyond(L, start, up, t)` — ANY swing beyond (the push's own high above a resistance counted) ⇒ BROKEN | the hold side's swing only, confirmed while still beyond (`levels.py` `_step_far_swing`, `kind=hold_kind`) |
| area flip | `levels.py:558` far-side swing reached during the excursion ⇒ FLIPPED even without any hold | flip only with the hold (reached is remembered until the hold) |
| area broken back | `levels.py:581–598` reclaim ⇒ the previous state, role kept, "RECLAIMED (broken back)" | DEAD (`dead_rule = broken_back`) |
| line break | `trendline.py:327 _broken_at` / `:40 broken_by` — a swing of the line's OWN kind beyond (the push extreme), line degree | the hold side's swing (finest structure), closes beyond through its confirmation |
| line broken back | `trendline.py:594 broken_back_on` — back_kind = the push extreme; the confirming bar may already be through again (`:612–621`) | hold side, the confirming bar must still be back |

Cases: **2.10** (area 265, "RECLAIMED" 14 May 09:45) — under BREAK-1 never broken: 09:15 (1 close below) and 11:15 (3 closes below,
past the far swing 53,194) are sweeps ⇒ alive support, no E4 (b) object (the entry stays removed, for the right reason). **2.11–2.20**
(lines "dead") — under BREAK-1 (D1) none of these lines is broken at the decision (see per-case table), so none is an E4 (b) object;
"broken back" before "break known" can no longer happen (both are stamped at their known bars and broken back needs a break first).
Charts: `gallery_fixes/A/case_2.10.png`, `case_2.11.png`, `case_2.16.png`, `case_2.17.png`.

### A2 — #373 never reached lines (sec1 07 / 09 / 12 Oct = 2.25 / 2.26 / 2.27)
Today the break was "known" at the bar that itself closed back over the line (9 Oct 09:15) and `broken_back_at` = none (the back
swing had to be the push extreme and the attempt began only after the break's run). Under BREAK-1 no hold swing formed below these
lines while the closes stayed below (on D1 and on D0) ⇒ the lines are NOT broken at all ⇒ no E4 (b) object — the three entries stay
removed, now by the lifecycle, no longer by the approach-side rule. Charts: `case_2.25.png`, `case_2.26.png`, `case_2.27.png`.

### A3 — approach side allows a sweep (2.23 / 2.24)
Today `entry_models.py:403 / :407` blocked on ANY close (or open) on the original side. Now blocked only when price held there.
2.23 / 2.24: under BREAK-1 (D1) their lines are not broken at the decision ⇒ no E4 (b) object either way; on D0 both are broken
(1 Sep 13:30 / 22 Sep 10:30) and the approach rule would then read the marginal closes as a sweep. Charts: `case_2.23.png`, `case_2.24.png`.

### A4 — re-evaluation of the named cases
| case | object | today | BREAK-1 (D1, default) | D0 (A-L1 alternative) |
|---|---|---|---|---|
| L5-X01 11 Sep | Daily support 274 | BROKEN 10:00, FLIPPED 11:00, E4 (b) 10:15 | sweep (10:30, 11:00), alive — **no E4 (b)** ✓ proof case | sweep ✓ |
| 2.3 / 2.4 20 Jul | 1H 292 / Daily 294 resistance | flipped 17 Jul 15:15, dead 20 Jul 13:45 | 17 Jul poke = sweep (ends 20 Jul 09:15), resistance alive ✓ | sweep ✓ |
| 2.17 20 Jul 14:15 | line D2:L+:1347-1442 | broken 16 Jul (known 17 Jul 10:00), broken back 17 Jul (known 20 Jul 09:15) | not broken (16 Jul dip and the 20 Jul gap-down have no D1 pullback high below) ⇒ no E4 (b) ✗ vs Abhi's "textbook retest" | broken 20 Jul 09:15 (held: 10:30 pullback high 57,838 below) ⇒ the 14:15 retest is an E4 (b) object ✓ |
| 2.1 / 2.7 / 2.9 | 291 / 290 / 297 | flipped then dead (stamped on rally bars) | sweeps, alive (2.1: 50 closes above 24–29 Jun with no D1 low above) | 2.1 / 2.9 sweeps; 2.7 broken 7 Oct 11:00 |
| sec3 1H 265 / W 256 | 14 May | reclaim 09:45, flip 10:45, dead 11:30 | sweeps only, alive | sweeps only |
| N01 | Daily 81 | "sweeps ×12" Apr–May | the same: no swings exist before 13 May in the build (swings2 warm-up from the 13 Apr data start) — A-L5 | same |
| N03 | Daily 288 | no event | no event (price inside the wide band) | no event |
Charts for every row: `gallery_fixes/A/case_<id>.png` (two panels: before / after on the same bars, decision bar marked, later bars faded).

### A8 — stamps at the bar KNOWN
Today the line "broken" stamp is the first close beyond (`reading_gallery.py:379`) and "broken back" the attempt's first close
(`:386`, from `broken_back_at`) — so it appeared before "break known" on every line case; areas were stamped at their engine bar,
which for the earlier reading was the late D1 confirmation of the push extreme (2.1 DEAD 01 Jul 11:15 on the rally bar). Now: line
"broken" at `break_known_at`, "dead (broken back)" at the known bar, the base candle and the state on every area chart; no stamp is
ever before the bar it became known (tests: cut = full).

### Golden tests (STOP — not edited)
On the default (D1) two golden tests in `tests/test_decision3_flip.py` fail: `test_real_29_sep_new_low_flip_on_the_swing_confirmation_
with_the_daily_warmup` (NIFTY 29 Sep: the Daily supply broke to new lows and came back with no pullback high below ⇒ a sweep, never
flipped) and `test_oct12_synthetic_fixture_supply_flips_when_the_first_swing_after_the_break_is_confirmed` (the synthetic replica, same
shape). On D0 seven more fail (the NIFTY 12 / 13 Oct golden zone 22,544–22,622 no longer exists at 12 Oct). Both are owner questions
(A-L1, A-L2 in OPEN_QUESTIONS); nothing golden was edited.

### Replay (13 BANKNIFTY groups, reading mode, 5M trigger = the live default; before = 0e48a7c, after = branch `lifecycle`)
Per model (outcome by structure, REPORT_STANDARD §4; an.py rule). Before = code 0e48a7c; after = BREAK-1 with the hold swing on D1
(the default here). Entries keyed by trigger bar + model + entry ref (area ids differ between readings — A5).

| model | before | after | removed | added | kept | before next / inval / open | after next / inval / open |
|---|---|---|---|---|---|---|---|
| E1 | 25 | 33 | 5 | 13 | 20 | 8 / 17 / 0 | 9 / 24 / 0 |
| E2 | 2 | 2 | 0 | 0 | 2 | 2 / 0 / 0 | 1 / 0 / 1 |
| E3 | 19 | 44 | 1 | 26 | 18 | 12 / 7 / 0 | 25 / 18 / 1 |
| E4 (a) | 0 | 1 | 0 | 1 | 0 | — | 0 / 0 / 1 |
| E4 (b) | 10 | 2 | 9 | 1 | 1 | 5 / 5 / 0 | 2 / 0 / 0 |
| all | 56 | 82 | 15 | 41 | 41 | 27 / 29 / 0 | 37 / 42 / 3 |

BREAK-1 changes **56 replay entries** (15 removed, 41 added; 7 kept entries change their scored outcome because the next area changed).
Which rule (A1 decides all of them; A3 / A8 change no entry on their own here):
- E4 (b) removed 9: the object is no longer broken under the hold rule — 7 lines (5 Jun ×2, 9 Jul, 10 Jul, 30 Sep, 1 Oct, 5 Oct; none
  held a D1 pullback on the far side) and 2 areas (11 Sep Daily 274 = L5-X01, the owner's proof case; 25 Sep area 285).
- E4 (b) added 1: 17 Sep 09:30 area 265 — broken WITH a hold, retested from the break side (the same bar was an E1 before).
- E1 / E3 / E4 (a) added 40, removed 6: areas the earlier reading called BROKEN / FLIPPED / DEAD after a push that never held now stay
  alive with their role (e.g. 2.3 / 2.4 area 292 — E1 20 Jul 14:00; 2.1 area 290 — E1 / E3 1 Jul 12:15; 2.7 / 2.9 — E3 7 Oct 12:15,
  8 Oct 09:15, 13 Oct 11:30), so their visits are no longer disarmed "broke inside this visit" and they stay trade locations. 6
  earlier E1 / E3 entries are not taken (17 Sep 09:30 became the E4 (b) above; 3 Jun, 1 Sep, 3 Sep, 11 Sep, 7 Oct 12:30 — the visit /
  area now reads differently; to be charted with the A-L1 answer).
The full list (group, trigger, model, area, entry, invalidation, result, MFE / MAE): trade-data
`review/gallery_fixes/A/replay_before_after.txt` (+ the two scored JSONs). Before / after charts of every changed entry are NOT drawn
yet: the changed set depends on A-L1 (on D0 it differs again), so they follow the owner's answer; the 18 named-case charts are drawn.

### Tests (full suite on branch `lifecycle`, D1 default)
New: `tests/test_break_hold.py` (27 tests, both mirrors: break needs a hold, the push extreme is a sweep (X01), a hold known on a bar
already back is no break, no flip without the hold, broken back ⇒ dead, a retest that does not hold stays broken, flip once ⇒ dead,
cut = full no look-ahead, lines break / broken back stamped at the known bar, the approach side allows a sweep, E4 (b) fires only at a
held break, the hold degree). Tests written for the earlier reading run on the what-if (`earlier_break_reading` fixture) and pass.
Still failing (left for the lead / Abhi, nothing golden edited) — 30:
- golden (`tests/test_decision3_flip.py`): 29 Sep NIFTY, the oct12 synthetic replica (A-L2);
- built on the oct12 synthetic replica / real BN 7 Oct (the supply only exists as BROKEN / FLIPPED under the earlier reading):
  `test_entry_models_inside_area` (2), `test_entry_models_live` (2), `test_entry_models_real_bn_oct07` (1), `test_facts_dossier` (3),
  `test_facts_dossier_5m` (10), `test_pa_evidence` (4);
- byte-identical pins of the earlier code: `test_trigger_5m::…byte_identical…[abc]`, `test_model_c::…byte_identical…` (3);
- `test_pa_range_edges` (2): range-edge areas replay the K4 machine (`range_edges.py`), synthetic breaks by the push extreme.
These change only by the owner rule (or need re-pinning to the what-if) — a decision for the lead after A-L1 / A-L2.
