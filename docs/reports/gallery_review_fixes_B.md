Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# Gallery review fixes — B. The visit and the move into the zone (B1 visit end, B2 move start; DECISIONS 64)

Branch `visitmove` (base `0e48a7c`, claude/hopeful-gates-hf186c), local commit only. BANKNIFTY only. Charts (private): trade-data
`review/gallery_fixes/B/` (not committed by me). Scope: the visit lifecycle and the move start (`move_from`) passed to the RSI read.
Not touched: area / line lifecycle (break / sweep), area builder / refined base, RSI push detection (C).

## सारांश (मराठी)
- **आजचा दोष (B1):** visit फक्त **D1 (structure degree)** च्या "दूर बांधलेल्या swing" ने संपत होती. मोठी सरळ घसरण (D04 / D05: ~1,900 pts)
  मध्ये D1 swing तयारच होत नाही ⇒ visit दिवसन्‌दिवस "उघडी" राहायची. आणि price area च्या पलीकडे (far side) टिकली तरी visit संपत नव्हती
  (N07: 07-23 ची visit 09-09 पर्यंत).
- **आजचा दोष (B2):** move start = visit सुरू होण्याआधीचा शेवटचा **D1** swing, आणि तो visit मध्ये कधीच पुढे सरकत नव्हता. त्यामुळे
  D0 वर दिसणारा नवा away swing (D02, D07, D12, E25, E49, E53) दुर्लक्षित; E26 (D1 swing अजून confirm नव्हता) आणि E27 (नंतर confirm)
  एकाच visit साठी वेगळे start वाचत होते.
- **दुरुस्ती (DECISIONS 64 प्रमाणे, setting `visit_end_rule = away_not_reached`):** visit संपते जेव्हा price area सोडून (1) D1 swing दूर
  बांधते (आधीसारखं), किंवा (2) सर्वात बारीक swings (D0) वर: एक swing दूर + पुढचं वळण area पर्यंत परत पोहोचत नाही. पुढचं वळण area मध्ये
  परत आलं ⇒ ती dip visit चाच भाग, visit चालू, आणि move start त्या dip वर पुढे सरकतो. Far side ला पण तसंच: पलीकडे swing + पुढचं वळण
  आत परत नाही ⇒ visit संपली (sweep परत आत आला ⇒ visit चालू). Move start = t पर्यंत माहीत असलेला **शेवटचा** away swing.
- **Named cases:** D03, D04, D05, D13 — visit आता structure ने संपते (D04: 07-22 15:15 ला, 07-23 09:15 ला कळलं; आधी 07-24 नंतरही उघडी).
  D02, D07, D11, D12, E25, E49, E53 — move start पुढे सरकला. E26 = E27 (दोघे 08-25 13:15). N07 आणि D11 — decision bar वर दूर जाणारा swing
  अजून confirm नव्हता ⇒ त्या bar ला visit चालू (structure ने अजून संपली नाही); पुढच्या confirm वर संपते. याबद्दल प्रश्न B-2 खाली.
- **Replay (13 BANKNIFTY groups, 5M trigger):** entries 53 → 56 (एकही काढली नाही; 3 नव्या — जुनी visit आता संपते म्हणून नवी visit:
  09 Jul E4 (b), 03 Aug E1 + E3 area 288; तिन्ही invalidation first). 30 entries चा move start पुढे सरकला; RSI ✓ 5 → 0 (move आता
  शेवटच्या away swing पासून ⇒ D0 वर दोन pushes कमी — push मोजणी C1 चं काम). संपलेल्या visits मधले 251 RSI reads गेले.
  `single_swing` = आधीचं output byte-for-byte (2 groups तपासले).
- **Tests:** नवीन `tests/test_visit_end_move_start.py` (22, दोन्ही mirrors, 15M + 5M readers, full = cut) + जुने सगळे संबंधित pass;
  golden expectations बदलले नाहीत (golden tests pass).
- **जुनं वाचन:** `visit_end_rule = single_swing` (dashboard `engine3_visit_end_rule`) = आजचं वर्तन byte-for-byte (what-if / revert).

## 1. Today's code (base 0e48a7c)
| what | where | today |
|---|---|---|
| visit (15M) | `decision3/engine.py:274` `V22.visit` → `:336` `_visit_structure` | starts at the first bar trading into the band (≥ born); ends ONLY at a swing of `Levels._known0` built away (`:362` `if i in piv and i > start`) |
| the swing set | `decision3/levels.py:445–458` `_known0` | the finest STRUCTURE degree = swings2 D1 (`structure_degrees` (1, 2); D0 "wiggles" excluded) |
| away swings | `engine.py:311` `_away_swings` | near side only (supply: a D1 low below `lo`); the far side never ends a visit |
| approach / move start | `engine.py:372` `approach_from = last_piv + 1` (fixed at the visit's start); `:471` `cm["move_from_bar"] = approach_from − 1` | the last D1 away swing BEFORE the visit; never moves inside the visit |
| 5M visit | `decision3/entry_models5.py:86` `visit5` (= `V.visit(k(u))`; the bar in progress `:115` `_away_swings(ku)`) | same rule at the closed 15M bar |
| 5M move start → RSI | `entry_models5.py:648` (area), `:660` (broken area, C-L5-1) `mf = approach_from15 − 1` | fixed at the visit start |
| line retest move start (L5-c) | `decision3/entry_models.py:804` `line_move_from` (`:812` `bb <= p.bar < start`) | D1 swings before the revisit only |
| E4 (b) revisit end | `entry_models.py:663` `touch_visit` (`:679`), `entry_models5.py:475` `touch_visit5` | one D1 swing not reaching the object |
| dossier / hidden-RSI frame | `facts/dossier.py:597`; `decision3/rsi_hidden.py:91` | `approach_from − 1` |

Why D04 stayed open: area 293 (57,738–57,964) was touched by the 07-22 09:15 breakdown candle (born on that bar — the area builder's
business, logged B-4). From 07-20 12:45 to 07-24 there is **no D1 pivot at all** (the D1 down-leg from 58,597 never turned by D1's own
measure), so no "D1 swing built away" ever existed; the D0 turns (07-22 12:30 L 56,971 / 15:15 H 57,179 / 07-23 … 07-24) were invisible
to the visit.

## 2. The rule now (DECISIONS 64; `visit_end_rule = away_not_reached`, default)
`decision3/engine.py` `V22._visit_away` (called from `_visit_structure`), the swings = `V22.visit_swings()` (swings2's finest computed
degree, D0 — the turns the 15M chart shows, the same pivots rsi2 counts as pushes) plus the D1 structure swings:
- a visit begins at the first bar trading into the band (as before);
- it ENDS when, after it began, (a) a D1 swing is built away (as before), or (b) a finest swing is built away from the area on the side
  price came from AND the next turn does not reach the area again (supply: its high stays below `lo`; demand mirror) — the visit is over
  at that turn, known at its confirmation; (c) the same on the far side (a swing beyond + the next turn not back inside = held beyond;
  a sweep comes back inside and the visit goes on — CLAUDE.md "Sweep / fakeout");
- a finest dip whose next turn reaches the area again keeps the visit (one visit; E1 does not re-fire), and the move start moves to it;
- `move_from` = the LAST swing built away (near side) known at t — moves forward with each new away swing, also inside the visit;
  `approach_from` (the E2 approach leg, method §3) = after the last away swing before the visit's start;
- broken-area retests (E4 b / C-L5-1): the last swing built away known at t (the break's own swing beyond — BREAK-1 — or a later
  one; both readers); broken lines (L5-c): the last away swing beyond the line after its break known at t (also inside the revisit);
  E4 (b) revisit end: a D1 swing not reaching the object (as before) or two
  consecutive finest swings after the start that both do not reach it (`entry_models.revisit_start`);
- 5M reader: the same at k(u) (`visit5.move_from15`, the bar in progress via `_away_swings`), `touch_visit5` the same; the dossier
  (`facts/dossier.py`) and the hidden-RSI frame (`rsi_hidden.frame_of`) read the engine's `move_from`;
- no numbers: comparisons of swing extremes with the band only; swings confirmed by t only (no look-ahead).

## 3. Named cases (charts: `review/gallery_fixes/B/<id>_before_after.png`, BEFORE top / AFTER bottom: visit start / end lines, the away
swings (blue), the move start ★ at the decision)
Format: visit start / end at the decision ("open" = in progress) / move start.

| case | area | gallery visit | entry | BEFORE | AFTER |
|---|---|---|---|---|---|
| D02 (B2) | D 260 57,371–57,456 | 06-15 09:15 | — | 06-15 09:15 / open / 06-11 15:00 | 06-15 09:15 / open / **06-15 15:00** |
| D03 (B2) | D 79 57,558–57,628 | 06-15 09:15 | — | 06-15 09:15 / open / 06-11 15:00 | **ended 06-15 14:30** (left 13:45) / — |
| D04 (B1) | 1H 293 57,738–57,964 | 07-22 09:15 | — | 07-22 09:15 / open (07-24 14:00, ~1,000 pts below) / 07-20 12:45 | **ended 07-22 15:15** (left 12:30; known 07-23 09:15) |
| D05 (B1) | 1H 295 same band | 07-22 09:15 | — | 07-22 09:15 / open / 07-20 12:45 | **ended 07-22 15:15** |
| D07 (B2) | 1H 295 57,498–57,716 | 08-20 09:15 | — | 08-20 09:15 / open / 08-19 09:30 | 08-20 09:15 / open / **08-20 15:00** |
| D11 (B1) | 1H 290 57,771–57,886 | 08-26 09:15 | — | 08-26 09:15 / open / 08-25 13:15 | 08-26 09:15 / open / **08-27 12:15**; ends at the 08-28 09:15 swing away (known 10:15; see B-2) |
| D12 (B2) | 1H 289 56,474–56,570 | 09-18 14:30 | — | 09-18 14:30 / open / 09-17 13:30 | 09-18 14:30 / open / **09-21 10:00** |
| D13 (B1) | 1H 288 56,474–56,570 | 09-18 14:30 | — | 09-18 14:30 / open (09-23) / 09-17 13:30 | **ended 09-22 14:15** (left 14:00) |
| N07 (B1) | D 266 56,549–56,743 | 09-11 14:00 | — | 09-11 14:00 / open / 09-11 09:15; the 07-23 visit stayed open 7 weeks while price held ABOVE | 09-11 14:00 / open / **09-11 14:15**; the 07-23 visit ends on the far side (see B-2) |
| E25 (B2) | 1H 293 57,612–57,799 | 08-20 09:30 | 08-24 10:10 E4 | 08-20 09:30 / open / 08-19 09:30 | same visit / **08-20 15:00** (the dip that came back 08-21) |
| E26 (B2) | 1H 292 57,771–57,886 | 08-26 09:15 | 08-26 09:20 E1 | 5M visit 08-26 09:15 / move 08-24 13:00 | **08-25 13:15** (= E27) |
| E27 (B2) | same visit | 08-26 09:15 | 08-26 13:30 E4 | 08-25 13:15 | 08-25 13:15 — E26 and E27 now agree |
| E49 (B2) | 1H 302 55,301–55,419 | 10-13 09:45 | 10-14 13:50 E4 | 10-12 14:30 | **10-14 09:15** |
| E53 (B2) | 1H 280 55,699–55,970 | 10-15 10:00 | 10-16 09:20 E2 | 10-14 13:15 | **10-15 15:00** |

(The RSI verdict of each case after the fix is in the replay tables; the push count itself is C's — not changed here.)

## 4. Replay (13 BANKNIFTY groups 13 Apr – 21 Oct, 5M trigger, default settings; last group live FUT, the others reading mode as the
layer 5 gallery). BEFORE = base 0e48a7c (reproduces the layer 5 census exactly), AFTER = this branch.

| model | run | entries | RSI ✓ | RSI ✗ | RSI NA |
|---|---|---|---|---|---|
| E1 | before | 22 | 2 | 19 | 1 |
| E1 | after | 23 | 0 | 23 | 0 |
| E2 | before | 1 | 0 | 1 | 0 |
| E2 | after | 1 | 0 | 1 | 0 |
| E3 | before | 9 | 0 | 9 | 0 |
| E3 | after | 10 | 0 | 10 | 0 |
| E4 | before | 21 | 3 | 18 | 0 |
| E4 | after | 22 | 0 | 22 | 0 |
| all | before / after | 53 / 56 | 5 / 0 | 47 / 56 | 1 / 0 |

- Entries: no entry removed; 53 identical (same bar, model, area). **3 added**, all because an earlier visit now ends by structure and
  the next arrival is a new visit (B1) — each charted, outcome followed forward across sessions:
  | entry | why new | outcome (structure, forward) |
  |---|---|---|
  | 09 Jul 11:50 E4 (b) broken line D2:H-:1262-1425 (par) | the earlier revisit of the line ended (two turns not reaching it) ⇒ a new revisit | invalidation close first (10 Jul 09:15), MFE 150 |
  | 03 Aug 09:45 E1 area 288 57,738–57,964 | the 22 Jul visit (D04 / D05's band) ended 22 Jul 15:15 ⇒ 03 Aug = a new visit | invalidation close first (03 Aug 11:00), MFE 58 |
  | 03 Aug 10:25 E3 area 288 | same new visit | invalidation close first (03 Aug 15:15), MFE 125 |
- RSI evidence: the move start changed on **30** of the 53 common entries (all later = the last away swing; list + charts
  `review/gallery_fixes/B/replay/`). The 5 ✓ became ✗: with the start moved to the last away swing, 4 of them (10 Jun E4, 07 Jul E4 (b),
  21 Aug E1, 09 Oct E1) hold fewer than two pushes inside the move; E49 (14 Oct E4) compares the newer pair, a lower high (55,612 vs
  55,645) ⇒ no regular divergence. 13 May E1 NA → ✗: the move start is now known. The push
  list itself is C1's (pushes under-counted at D0, DECISIONS 65) — these 30 entries are the input for that fix; nothing here decides.
- Visits (armed area visits recorded by the replay hook): 114 → 115 distinct; RSI reads at 15M bars inside armed visits 2,338 → 2,087
  (−251 reads that belonged to visits which had ended by structure — B1 "no RSI read belongs to an ended visit").
- What-if parity: this branch with `visit_end_rule = single_swing` reproduces the BEFORE run byte-for-byte (entries, visits, RSI reads)
  on the groups 22 Sep – 6 Oct and 7 – 21 Oct (live FUT).
- 15M trigger (what-if): covered by the tests (both readers); not replayed here.
- Runners (scratchpad, not committed): `visitB/walkB.py` (= the layer 5 gallery walk + 15M option), `runB.py`, `compare.py`,
  `casemap.py`, `chartB.py`, `chartE.py`.

## 5. Tests
- New `tests/test_visit_end_move_start.py` (24, both mirrors): the rule registered / validated / a live switch; B1 end by "away + the
  next turn not reaching", a dip that comes back keeps the visit, a D1 swing still ends it, the far side (held beyond ends, a sweep
  does not); no model / nothing armed in an ended visit, the next visit re-arms E1; B2 the move start moves forward (15M commit facts,
  hidden-RSI frame, 5M `visit5`, broken-area retest on both readers, broken line); E4 (b) `revisit_start`; no look-ahead full = cut at
  every 15M bar and every 5M close.
- Updated (behaviour pinned under the what-if): `tests/test_rsi_l5bc.py` (line move start: new rule + `single_swing`),
  `tests/test_engine3_live_switches.py` (the new dashboard switch).
- Run green: test_decision3_entry_models, test_decision3_zone_answers, test_rsi_l5bc, test_pa_rsi_hidden, test_method_no_numbers,
  test_trigger_5m (incl. the real-BANKNIFTY full-vs-cut), test_entry_models_* (broken_back, flip_dead, inside_area, live, live_e4b,
  real_bn_oct07, sweep_fakeout), test_facts_dossier(_5m), **test_golden_chart_cases, test_golden_gallery**, test_reader_parity_export,
  test_rsi_divergence, test_engine3_live_switches, test_cloud_db, test_decision2, test_decision3(_flip, _oct12, _entry_first_bar,
  _confirm), test_pa_evidence, test_pa_standard_deploy, test_layer6_output_consistency, test_model_c_live, test_trigger_5m_live —
  no golden expectation edited, none changed.

## 6. Provisional decisions — checked against DECISIONS, CLAUDE.md, the method
- Checked: DECISIONS 64 (the rule itself), 56 / 59 (L5-b forming push untouched; L5-c "before the revisit" → now "the last away swing
  known at t", because 64 says the start moves forward with each new away swing — 64 is the newer, general owner rule; noted B-3), 37
  (5M trigger: structure at the closed 15M bar k(u); the 15M path unchanged except the visit rule itself), 60 / 61 (BREAK-1: the
  far-side end only ends the VISIT; broken / dead stays the lifecycle's), CLAUDE.md "Sweep / fakeout" (a sweep back inside keeps the
  visit), "E4 (b): the revisit ends when price leaves it by structure", "E1 does NOT come back after a sweep" (unchanged: a sweep never
  ends the visit), "no fixed numbers", "never edit golden expectations" (none edited; golden tests pass).
- B-1 … B-4 logged in `docs/reports/v22/OPEN_QUESTIONS.md`.
