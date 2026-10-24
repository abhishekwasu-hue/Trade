Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# Gallery review fixes — A5 (object identity), A6 (band rule), A7 (refined base)

Abhi's gallery review (INBOX 24 Oct, "TRADE_SESSION_GALLERY_REVIEW_FIXES", §A5–A7; DECISIONS 62 / 63). Branch `identity` (local, base
`0e48a7c`). BANKNIFTY only (the NIFTY holdout stays sealed). Charts: trade-data `review/gallery_fixes/A567/` (not in this repo).

## सारांश (Abhi साठी, सोप्या मराठीत)

- **A5 — एका जागेला अनेक नंबर / एक नंबर अनेक जागांना:** area चा नंबर (`id`) हा त्या दिवशीच्या build मधल्या यादीतला क्रमांक होता.
  Engine रोज मागचे 90 दिवस घेऊन नव्याने बनतो — खिडकी पुढे सरकली की जुने area यादीतून गळतात आणि नंबर बदलतो. म्हणून 55,699–55,970 हा
  एकच पट्टा 285 / 281 / 280 / 278 दिसला, आणि 293 / 299 हे नंबर वेगवेगळ्या दिवशी वेगवेगळ्या पट्ट्यांना मिळाले. एकाच build मध्ये
  कधीही दोन area एकाच पट्ट्याचे नव्हते (13 गटांत तपासले). आता प्रत्येक जागेचा कायमचा नंबर: `timeframe : बाजू : base candle`
  (उदा. `1H:L:2026-09-11 09:15`) — खिडकी कुठेही असो, तोच. Visit id, "एका visit ला एका model ची एकच entry" ची किल्ली आणि cluster
  यांनी आता हाच नंबर वापरतात. `max_hits_per_zone` आधीपासूनच पट्ट्यावर (overlap + role) मोजतो, नंबरवर नाही — त्यामुळे duplicate
  नंबरने ती मर्यादा कधीच चुकली नाही; replay मध्ये कोणतेही model एका visit मध्ये दोनदा आले नाही (खाली §4).
- **A6 — union पट्टे?** नाहीत. 298 (54,886–55,193) = 5 Oct 09:15 च्या 1H swing candle चा स्वतःचा वरचा wick (body ची वरची कडा 54,886.20
  ते high 55,192.65); 294 + sweep नाही. 297 (628 pts) = 31 Aug ची 15:15 ची एकच bar: 1m data मध्ये 15:15–15:28 किंमत 57,397.35 वर
  थांबलेली, मग 15:29 ला एकच 58,024.95 print (Daily close पण तोच). त्या candle ला wick नाही ⇒ नियमाने body = पूर्ण bar. नियमाचा
  भंग नाही; data चा प्रश्न — OPEN_QUESTIONS A6-1 मध्ये नोंद, पट्टा बदलला नाही.
- **A7 — refined base:** आधी फक्त D1 structure चे turns आणि फक्त ज्यांचे टोक पट्ट्याच्या आत असे turns वाचले जात होते ⇒ N03, N07, N04
  मधले स्पष्ट 15M turns सुटले, आणि E31 / N07 ला 1-point base (56,551.65–56,552.85) मिळाला. आता: 15M वरचा प्रत्येक confirmed turn
  (D0), ज्याचा wick-to-body पट्ट्यात येतो, त्यातला सर्वात नवा = refined base (पट्ट्याच्या आत कापलेला); आणि area च्या स्वतःच्या base
  candle आधीचा turn कधीच नाही (N08). E31 / N07 आता 56,549.40–56,628.10 (11 Sep 14:00 चा turn), N03 57,859.75–57,994.45 (7 Aug 13:45).
  E01 / E09 / R5-E01 मध्ये base = पूर्ण area हे नियमानेच (तो 15M candle हाच area चा base candle आहे, नवा turn नाही).
- Replay (13 BANKNIFTY गट, आधी / नंतर, प्रत्येक model): §5. Tests: §6.

## 1. Checks of the provisional decisions (CLAUDE.md memory protocol)

| decision | checked against | result |
|---|---|---|
| stable id = timeframe : side : base candle start | DECISIONS 62 ("one place = one id for its life"), Z-1u (one timeframe per band), method "Areas" (one base) | consistent — no reading rule changed, no number |
| refined base reads every 15M turn (D0) | DECISIONS 63 ("newest 15M turn … inside the band, as its wick-to-body"), method "Refined base", RC2 (research default), STABLE layer 1 (swing definition unchanged — the swing engine is only read) | consistent; logged A7-1 |
| a turn counts when its wick to body trades into the band (also a sweep poke) | method "Sweep" (area alive), Z-1u (base kept inside the band) | consistent; logged A7-2 |
| birth turn at / after the area's own base candle | method "from the area's own birth turn on" | consistent |
| 297 / 298 bands unchanged | method "no wick on the area side ⇒ the body"; Z-1u; "never add a rule Abhi didn't state" | no change; A6-1 / A6-2 logged |
| max_hits_per_zone untouched | CLAUDE.md "never add new execution settings" | untouched (already counts by band) |

## 2. A5 — object identity

### 2.1 Today's code (base `0e48a7c`)

- `decision3/levels.py:252` — a new level is `Level(len(self.L), …)`: its `id` is the list index of THIS build.
- `engine3_live.py:428` / the replay harness — every build reads the last `engine3_m15_days` (90) days of 15M bars, so each new session
  drops the oldest levels and every later index moves down (ids are stable within one session, not across sessions).
- `decision3/entry_models.py:423, 752` and `decision3/entry_models5.py:283, 525` — `visit_id = f"{id}@{visit start}"`; this is the
  (bot, symbol, visit_id, model) claim key (`paper/engine_entry.py:559`, `engine_signal.py:621`).
- `decision3/entry_models.py:997, 1009` — the cluster anchor and the same-bar order tie-break on `str(area_id)`.
- `decision3/reading_gallery.py:395` — the gallery looks the case's level up by the integer id in ITS build.
- `engine_signal.py:649` (`zone_entries_today`) / `paper/engine_entry.py:342` (`entry_zone`) — `max_hits_per_zone` counts entries by
  the band (direction + overlapping lo / hi), never by an id.

### 2.2 The named cases (ids over time; charts `A5_identity_<band>.png`)

| band | day: id (window start) | stable id (after) |
|---|---|---|
| 55,699.45–55,970.15 | 25 Sep: 285 (29 Jun) · 15 Oct: 281 (17 Jul) · 16 Oct: 280 (20 Jul) · 19 Oct: 278 (21 Jul) | `1H:L:2026-09-11 09:15` (a Daily twin with the same band: 286 / 282 / 281 / 279 = `D:L:2026-09-11`, A5-3) |
| 56,474.40–56,570.45 (288 / 290) | 18 Sep: 290 · 21 Sep: 289 · 23 Sep: 288 | `1H:H:2026-09-17 09:15` |
| 55,055.80–55,135.50 (292 / 293) | 5 Oct: 293 · 6 Oct: 292 | `1H:H:2026-09-30 13:15` |
| 58,078.90–58,251.95 (297 / 293) | 13 Jul: 297 · 17 Jul: 293 | `1H:H:2026-07-10 12:15` |
| id 293 reused (E37 vs E38) | 1 Oct: 293 = 54,555.10–54,583.05 · 5 Oct: 293 = 55,055.80–55,135.50 | `1H:L:2026-10-01 09:15` vs `1H:H:2026-09-30 13:15` |
| id 299 reused (E44 vs E47) | 9 Oct: 299 = 55,143.05–55,201.00 · 13 Oct: 299 = 55,284.15–55,340.70 | `1H:H:2026-10-06 12:15` vs `1H:H:2026-10-07 10:15` |
| 54,886.20–55,192.65 (298 / 296 / 297) | 6 Oct: 298 · 7 Oct: 296 · 9 Oct: 297 | `1H:H:2026-10-05 09:15` |

Inside one build no two levels of one timeframe ever held the same band (checked on the last session of every group). The only
same-band pair is a 1H level and a Daily level whose swing candles share the wick to body (A5-3): Z-1u keeps them as two timeframes —
the 1H is the location, the Daily its confluence label — and identical bands give identical lifecycles.

### 2.3 Can a duplicate bypass `max_hits_per_zone` or one signal per model per place?

1. `max_hits_per_zone` counts by the band (`engine_signal.zone_entries_today`: same direction, overlapping lo / hi), never by an id —
   two ids for one band count together (test `test_duplicate_ids_cannot_bypass_max_hits_per_zone`).
2. Once per model per visit is re-read by the reader in every build from the visit's own bars (`fired_earlier`); a changed id never
   re-opens a model. The claim key used the id — after the fix it uses the stable id, so the same visit keeps one key across sessions
   (`test_visit_ids_carry_the_place_uid_and_match_across_windows`).
3. One signal per model per place (clusters) is read inside one build; the anchor / order tie-break now uses the stable id
   (`test_cluster_anchor_and_order_never_depend_on_the_list_index`).
4. Replay proof (§5.3): before the fix, visits whose id changed between sessions, and models fired twice in one visit — counted on all 13
   groups.

### 2.4 Fix

- `Level.uid` = `place_uid(tf, side, base candle start)` (`decision3/levels.py`), side = H (a swing high / supply base) or L (a swing
  low / demand base); 1H = the hour, Daily / Weekly = the day. The same base candle reborn as a new life (the earlier level dead, or of
  the other role) ⇒ `<uid>~<birth bar start>` (deterministic, window-free). `Levels.by_uid(uid)`; `snapshot` rows carry `uid`.
- Visit ids `<uid>@<visit start>` (15M and 5M paths, areas and broken areas); entries' `area.uid`, armed `area_uid`, cluster
  `anchor_uid` and member `area_uid`; cluster id `C<uid>`.
- The reading gallery finds the case's level by `uid` (never by another build's index).
- `Level.id` stays as it was (a lookup index of one build): no golden, no lifecycle, no band changed.
- Not changed (other owners): line ids still carry bar indices (`line:D2:H+:600-650`) — the same window effect (A5-2).

## 3. A6 — possible union bands (charts `A6_area298_band_rule.png`, `A6_area297_closing_print.png`)

- **Area 298 (54,886.20–55,192.65), L5-E41 (6 Oct).** Birth `a:D2`: the 1H swing high of the 10-05 09:15 hour (15M bars 09:15–10:00).
  The 1H candle: O 54,840.65, H 55,192.65, L 54,719.35, C 54,886.20 ⇒ the swing high's wick to body = body top (the hour's close,
  54,886.20) … high 55,192.65 (`levels._band_swing("H", …)`, `decision3/levels.py:143`). Its lineage lists 292 / 294 / 295 as
  OVERLAPS (evidence only, Z-1u) — their bands were not joined. Not a union; rule-compliant. (294 = 54,877.60–55,091.45, its own base:
  the 10-01 10:15 hour.)
- **Area 297 / R5-E07 (57,397.35–58,024.95, 628 pts), L5-E29 (3 Sep; 296 on 1 Sep, N04 / N05).** Birth `a:D2`: the 1H swing high of the
  31 Aug 15:15 "hour" = ONE 15M bar (the session's last). That bar: O = L 57,397.35, H = C 58,024.95 — no wick on either side ⇒ by the
  rule ("no wick on the area side ⇒ the body") the body = the whole bar. 1m: 15:15–15:28 flat at 57,397.35 (no ticks), then one 15:29
  print at 58,024.95; the Daily candle closes at the same price; next session opens 57,560.30. Not a union; the band follows the rule
  as written; the 628 pts come from a closing print. Logged A6-1 (data question for Abhi); no band rule added.

## 4. A7 — the refined base (charts `A7_<case>_refined_base.png`, before = black dashed, after = blue)

### 4.1 Today's code (base `0e48a7c`)

`decision3/entry_models.py:206–238` (`Reader.refined`): candidates = `Levels._known0` — the levels' STRUCTURE list (the finest structure
degree, D1, `decision3/levels.py:447`) — and only swings whose extreme lies inside the band (`lo <= p.price <= hi`, line 222); band =
the swing candle's wick to body, clipped to the context band.

Two misses: (a) D1 skips the 15M chart's own turns (Abhi's "obvious 15M turns"), (b) a turn whose extreme poked just beyond the band
(0.45 pt above 56,742.60 on 9 Sep 14:00) was not "inside". With D1 the newest turn could also be a split-candle turn (10 Sep 09:30: its
up-move's high sits in the 09:15 bar; the 09:30 bar's own wick is 1.20 pts ⇒ the 1-pt base of E31 / N07).

### 4.2 Fix

The newest 15M turn of the area's side (every turn the swing engine confirms on 15M — D0, `Reader.turns15`) whose wick to body trades
into the band, confirmed by bar u, from the area's own birth turn on — the birth turn now lies at or after the area's own base candle
(`Level.base_ts`; L5-N08: a support flipped to resistance had a July swing high as its "birth turn"). The base = that wick to body,
clipped to the band. Bars ≤ u only; comparison only.

### 4.3 The named cases (refined base at the decision)

| case | area (stable id) | decision | before | after | note |
|---|---|---|---|---|---|
| L5-E31 | D 56,549.40–56,742.60 (`D:L:2026-07-08`) | 17 Sep 09:30 | 56,551.65–56,552.85 (1.2 pts, 10 Sep 09:30) | 56,549.40–56,628.10 (11 Sep 14:00) | the 1-pt base gone |
| L5-N07 | same | 15 Sep 15:15 | 56,551.65–56,552.85 | 56,549.40–56,628.10 (11 Sep 14:00) | the visit's own turn (missed before) |
| L5-N03 | D 57,569.60–58,247.95 (`D:H:2026-08-03`) | 7 Aug 15:15 | 58,054.15–58,076.85 (6 Aug 14:00) | 57,859.75–57,994.45 (7 Aug 13:45) | 7 Aug 10:00 / 13:45 turns read (missed before) |
| L5-N04 | 1H 57,397.35–58,024.95 (`1H:H:2026-08-31 15:15`) | 1 Sep | whole area until 13:15, then 57,728.65–57,766.25 | the same base from 11:45 (the 11:30 turn confirmed on 15M) | at the visit start (09:15) no newer turn exists — the area's own (A6-1) bar |
| L5-N08 | 1H 56,823.20–57,006.45 (`1H:L:2026-09-02 09:15`, a support flipped to resistance) | 16 Sep | 56,884.25–56,996.35 (15 Sep 09:15; none before 15 Sep) | 56,884.25–56,996.35 (15 Sep 09:15; from 8 Sep the 8 Sep 10:15 turn 56,988.20–57,006.45) | no 1-pt base in N08 (its card shows 56,884.25–56,996.35, 112 pts) — the 1-pt base is E31 / N07's. Without the base-candle bound the after-reader took a 24 Jul swing high from before the area existed (fixed, `base_ts`) |
| L5-E01 | 1H 53,600.40–53,930.00 | 13 May 10:15 | = area | = area | the 15M candle is the area's own base candle (gap open at the top, hour body top = its open) — A7-3 |
| L5-E09 | 1H 53,870.45–53,933.55 | 3 Jun 13:45 | = area | = area | same (A7-3) |
| R5-E01 | 1H 53,963.10–54,109.15 | 22 May 14:15 | = area | = area | the 12:45 turn (54,168.65–54,213.05) lies wholly above the band (a sweep), not inside — A7-3 |
| R5-E09 | 1H 56,474.40–56,570.45 | 23 Sep 10:00 | = area (15M wick to body wider than the hour's, clipped) | 56,496.80–56,503.75 (21 Sep 09:30) | the newer 18 / 21 Sep turns read |

## 5. Replay — 13 BANKNIFTY groups, before (`0e48a7c`) / after (`identity`)

Runner: the deployed-engine walk-forward (one live-equivalent V22 build per session; 15M path `walk.py`, 5M trigger `walk5.py`),
reading mode (REPORT_STANDARD 0a: FUT volume missing on most groups — E2 / volume evidence not evaluated there), before = `0e48a7c`,
after = `77f2622`. Outcome rule (unchanged, structure, across sessions): the nearest alive opposite area beyond the entry reference
touched first = "next area first"; a 5M close beyond the entry's invalidation first = "invalidation first"; else open at data end. (The
DECISIONS 67 re-scoring — next area beyond the entry area — belongs to the scoring track and is not applied here.) Changed entries are
keyed by (model, trigger bar, direction, area band); a "removed" / "added" row shows the other run's reader status at that bar. Charts:
trade-data `review/gallery_fixes/A567/replay/` (before | after side by side; `changed.json` lists every row).

What moved the entries: almost all changes come from A7 (a narrower / newer refined base ⇒ a different first touch (E1), a trigger
candle that now does or does not trade into the base (E2 / E3 / E4 a), a base closed through ⇒ E1 passed). A few come from A5's
cluster order: two overlapping areas firing the same model at one bar — the kept signal is now chosen by the stable id instead of the
list index (e.g. 9 Oct 09:30 E1 now on 55,143–55,201 instead of 54,886–55,193; one place, one signal either way).

### 5.1 Per model — 15M trigger (`walk.py`, reading mode)

| model | before: entries | next area first | invalidation first | open | after: entries | next area first | invalidation first | open |
|---|---|---|---|---|---|---|---|---|
| E1 | 26 | 8 | 18 | 0 | 24 | 6 | 18 | 0 |
| E2 | 2 | 2 | 0 | 0 | 3 | 2 | 1 | 0 |
| E3 | 22 | 13 | 9 | 0 | 32 | 17 | 15 | 0 |
| E4b | 10 | 4 | 6 | 0 | 10 | 4 | 6 | 0 |
| **all** | 60 | 27 | 33 | 0 | 69 | 29 | 40 | 0 |

Changed entries (15M): 61 — added E1: 8, added E2: 1, added E3: 18, removed E1: 10, removed E3: 8, same trigger, base / invalidation changed E1: 5, same trigger, base / invalidation changed E2: 2, same trigger, base / invalidation changed E3: 9

| # | group | trigger | model | area | change | before | after | chart |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-10_2026-05-24 | 2026-05-13 10:45 | E3 | 53,600.40–53,930.00 | same trigger, base / invalidation changed | base 53600.4–53930.0, inval | base 53764.9–53800.45, inval | `replay/15M_2026-05-13_1045_E3_0.png` |
| 2 | 2026-05-10_2026-05-24 | 2026-05-14 09:15 | E1 | 53,600.40–53,930.00 | removed | entry, base 53600.4–53930.0, next | E1: passed — the refined 15M base 53,764.90–53,800.45 (2026-05-13 10:30) was closed through in this visit at 2 | `replay/15M_2026-05-14_0915_E1_1.png` |
| 3 | 2026-05-10_2026-05-24 | 2026-05-14 09:30 | E3 | 53,600.40–53,930.00 | same trigger, base / invalidation changed | base 53600.4–53930.0, next | base 53924.4–53930.0, next | `replay/15M_2026-05-14_0930_E3_2.png` |
| 4 | 2026-05-10_2026-05-24 | 2026-05-14 11:15 | E1 | 53,600.40–53,930.00 | removed | entry, base 53600.4–53930.0, inval | E1: passed — waiting for price to reach the refined 15M base 53,924.40–53,930.00 (2026-05-14 09:15) | `replay/15M_2026-05-14_1115_E1_3.png` |
| 5 | 2026-05-10_2026-05-24 | 2026-05-15 09:45 | E3 | 54,221.65–54,547.05 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 54302.9–54393.75, next | `replay/15M_2026-05-15_0945_E3_4.png` |
| 6 | 2026-05-10_2026-05-24 | 2026-05-15 13:15 | E3 | 54,221.65–54,547.05 | removed | entry, base 54302.9–54393.75, next | E3: fired_earlier — 2026-05-15 09:45:00 | `replay/15M_2026-05-15_1315_E3_5.png` |
| 7 | 2026-05-10_2026-05-24 | 2026-05-18 12:15 | E3 | 53,194.25–53,510.20 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 53194.25–53290.8, inval | `replay/15M_2026-05-18_1215_E3_6.png` |
| 8 | 2026-05-10_2026-05-24 | 2026-05-20 12:00 | E3 | 53,194.25–53,510.20 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 53194.25–53290.8, inval | `replay/15M_2026-05-20_1200_E3_7.png` |
| 9 | 2026-05-10_2026-05-24 | 2026-05-21 09:15 | E1 | 54,025.00–54,103.90 | same trigger, base / invalidation changed | base 54092.9–54103.9, next | base 54025.0–54103.9, next | `replay/15M_2026-05-21_0915_E1_8.png` |
| 10 | 2026-05-10_2026-05-24 | 2026-05-21 09:15 | E3 | 54,025.00–54,103.90 | same trigger, base / invalidation changed | base 54092.9–54103.9, next | base 54025.0–54103.9, next | `replay/15M_2026-05-21_0915_E3_9.png` |
| 11 | 2026-05-10_2026-05-24 | 2026-05-22 11:15 | E3 | 54,025.00–54,103.90 | added | E3: waiting — the candle did not trade into the refined 15M base 54,092.90–54,103.90 (only the wider context a | entry, base 54025.0–54103.9, inval | `replay/15M_2026-05-22_1115_E3_10.png` |
| 12 | 2026-05-10_2026-05-24 | 2026-05-22 14:30 | E3 | 53,963.10–54,109.15 | removed | entry, base 53963.1–54109.15, inval | E3: cluster_consumed — E3 already fired in this cluster's visit on area 266 at 2026-05-22 11:15:00 — one place | `replay/15M_2026-05-22_1430_E3_11.png` |
| 13 | 2026-05-25_2026-06-08 | 2026-05-26 09:45 | E3 | 55,326.05–55,554.15 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 55459.0–55536.8, next | `replay/15M_2026-05-26_0945_E3_12.png` |
| 14 | 2026-06-09_2026-06-23 | 2026-06-10 10:45 | E1 | 55,396.45–55,536.80 | same trigger, base / invalidation changed | base 55459.0–55536.8, inval | base 55465.8–55509.8, inval | `replay/15M_2026-06-10_1045_E1_13.png` |
| 15 | 2026-06-09_2026-06-23 | 2026-06-10 12:30 | E3 | 55,396.45–55,536.80 | removed | entry, base 55459.0–55536.8, inval | E3: waiting — the candle did not trade into the refined 15M base 55,465.80–55,509.80 (only the wider context a | `replay/15M_2026-06-10_1230_E3_14.png` |
| 16 | 2026-06-09_2026-06-23 | 2026-06-11 12:00 | E1 | 55,396.45–55,536.80 | removed | entry, base 55459.0–55536.8, inval | E1: passed — waiting for price to reach the refined 15M base 55,506.55–55,536.80 (2026-06-10 13:00) | `replay/15M_2026-06-11_1200_E1_15.png` |
| 17 | 2026-06-09_2026-06-23 | 2026-06-16 09:15 | E3 | 57,371.45–57,456.30 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57371.45–57399.2, inval | `replay/15M_2026-06-16_0915_E3_16.png` |
| 18 | 2026-06-09_2026-06-23 | 2026-06-17 10:45 | E1 | 57,558.20–57,628.40 | added | E1: passed — no refined base yet: no 15M turn of the area's side inside its band (RC2) — E1 waits | entry, base 57558.2–57590.6, inval | `replay/15M_2026-06-17_1045_E1_17.png` |
| 19 | 2026-06-09_2026-06-23 | 2026-06-17 12:00 | E3 | 57,558.20–57,628.40 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57558.2–57590.6, inval | `replay/15M_2026-06-17_1200_E3_18.png` |
| 20 | 2026-07-09_2026-07-23 | 2026-07-13 14:00 | E3 | 58,078.90–58,251.95 | same trigger, base / invalidation changed | base 58078.9–58251.95, next | base 58078.9–58103.4, inval | `replay/15M_2026-07-13_1400_E3_19.png` |
| 21 | 2026-07-09_2026-07-23 | 2026-07-15 11:30 | E3 | 58,078.90–58,251.95 | added | E3: waiting — price has not reached the refined 15M base 58,165.60–58,219.90 in this visit yet | entry, base 58078.9–58148.8, next | `replay/15M_2026-07-15_1130_E3_20.png` |
| 22 | 2026-07-09_2026-07-23 | 2026-07-17 10:15 | E1 | 58,078.90–58,251.95 | removed | entry, base 58078.9–58148.8, inval | E1: passed — the refined 15M base 58,084.70–58,118.60 (2026-07-15 12:15) was closed through in this visit at 2 | `replay/15M_2026-07-17_1015_E1_21.png` |
| 23 | 2026-07-09_2026-07-23 | 2026-07-17 10:30 | E3 | 58,078.90–58,251.95 | same trigger, base / invalidation changed | base 58078.9–58148.8, inval | base 58084.7–58118.6, inval | `replay/15M_2026-07-17_1030_E3_22.png` |
| 24 | 2026-07-09_2026-07-23 | 2026-07-22 09:15 | E1 | 57,738.25–57,963.55 | same trigger, base / invalidation changed | base 57738.25–57804.5, next | base 57794.45–57837.95, next | `replay/15M_2026-07-22_0915_E1_23.png` |
| 25 | 2026-07-09_2026-07-23 | 2026-07-22 09:15 | E3 | 57,738.25–57,963.55 | same trigger, base / invalidation changed | base 57738.25–57804.5, next | base 57794.45–57837.95, next | `replay/15M_2026-07-22_0915_E3_24.png` |
| 26 | 2026-07-24_2026-08-07 | 2026-08-06 09:15 | E1 | 57,569.60–58,247.95 | added | E1: passed — waiting for price to reach the refined 15M base 57,895.60–57,931.85 (2026-08-05 09:45) | entry, base 57846.9–57875.65, inval | `replay/15M_2026-08-06_0915_E1_25.png` |
| 27 | 2026-07-24_2026-08-07 | 2026-08-06 10:45 | E1 | 57,569.60–58,247.95 | removed | entry, base 57895.6–57931.85, inval | E1: fired_earlier — 2026-08-06 09:15:00 | `replay/15M_2026-08-06_1045_E1_26.png` |
| 28 | 2026-07-24_2026-08-07 | 2026-08-06 11:30 | E3 | 57,569.60–58,247.95 | same trigger, base / invalidation changed | base 57895.6–57931.85, inval | base 57846.9–57875.65, inval | `replay/15M_2026-08-06_1130_E3_27.png` |
| 29 | 2026-08-08_2026-08-22 | 2026-08-17 13:00 | E1 | 57,611.70–57,799.15 | added | E1: passed — no refined base yet: no 15M turn of the area's side inside its band (RC2) — E1 waits | entry, base 57633.5–57681.45, inval | `replay/15M_2026-08-17_1300_E1_28.png` |
| 30 | 2026-08-08_2026-08-22 | 2026-08-17 13:45 | E3 | 57,611.70–57,799.15 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57633.5–57681.45, inval | `replay/15M_2026-08-17_1345_E3_29.png` |
| 31 | 2026-08-08_2026-08-22 | 2026-08-21 09:30 | E1 | 57,611.70–57,799.15 | removed | entry, base 57711.95–57757.25, inval | E1: passed — the refined 15M base 57,686.25–57,702.95 (2026-08-20 11:00) was closed through in this visit at 2 | `replay/15M_2026-08-21_0930_E1_30.png` |
| 32 | 2026-08-08_2026-08-22 | 2026-08-21 09:45 | E1 | 57,771.35–57,885.85 | added | E1: cluster_consumed — E1 already fired in this cluster's visit on area 293 at 2026-08-21 09:30:00 — one place | entry, base 57771.35–57885.85, inval | `replay/15M_2026-08-21_0945_E1_31.png` |
| 33 | 2026-08-23_2026-09-06 | 2026-09-02 10:15 | E1 | 57,158.10–57,214.80 | added | E1: passed — no refined base yet: no 15M turn of the area's side inside its band (RC2) — E1 waits | entry, base 57185.45–57214.8, inval | `replay/15M_2026-09-02_1015_E1_32.png` |
| 34 | 2026-08-23_2026-09-06 | 2026-09-03 09:30 | E1 | 57,397.35–58,024.95 | removed | entry, base 57728.65–57766.25, next | E1: passed — the refined 15M base 57,397.35–57,409.60 (2026-09-01 15:15) was closed through in this visit at 2 | `replay/15M_2026-09-03_0930_E1_33.png` |
| 35 | 2026-08-23_2026-09-06 | 2026-09-03 10:15 | E3 | 57,397.35–58,024.95 | removed | entry, base 57728.65–57766.25, next | E3: waiting — price has not reached the refined 15M base 57,397.35–57,409.60 in this visit yet | `replay/15M_2026-09-03_1015_E3_34.png` |
| 36 | 2026-08-23_2026-09-06 | 2026-09-03 13:30 | E3 | 57,397.35–58,024.95 | added | E3: fired_earlier — 2026-09-03 10:15:00 | entry, base 57604.2–57642.8, next | `replay/15M_2026-09-03_1330_E3_35.png` |
| 37 | 2026-08-23_2026-09-06 | 2026-09-04 12:00 | E3 | 57,397.35–58,024.95 | added | E3: waiting — price has not reached the refined 15M base 57,715.85–57,753.60 in this visit yet | entry, base 57492.65–57545.5, next | `replay/15M_2026-09-04_1200_E3_36.png` |
| 38 | 2026-09-07_2026-09-21 | 2026-09-15 09:15 | E1 | 56,823.20–57,006.45 | added | E1: passed — no refined base yet: no 15M turn of the area's side inside its band (RC2) — E1 waits | entry, base 56884.25–56996.35, next | `replay/15M_2026-09-15_0915_E1_37.png` |
| 39 | 2026-09-07_2026-09-21 | 2026-09-15 09:15 | E3 | 56,823.20–57,006.45 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 56884.25–56996.35, next | `replay/15M_2026-09-15_0915_E3_38.png` |
| 40 | 2026-09-07_2026-09-21 | 2026-09-17 09:30 | E1 | 56,549.40–56,742.60 | same trigger, base / invalidation changed | base 56551.65–56552.85, inval | base 56549.4–56628.1, inval | `replay/15M_2026-09-17_0930_E1_39.png` |
| 41 | 2026-09-22_2026-10-06 | 2026-09-23 10:00 | E1 | 56,474.40–56,570.45 | same trigger, base / invalidation changed | base 56474.4–56570.45, inval | base 56496.8–56503.75, inval | `replay/15M_2026-09-23_1000_E1_40.png` |
| 42 | 2026-09-22_2026-10-06 | 2026-10-05 13:45 | E1 | 54,877.60–55,091.45 | added | E1: passed — waiting for price to reach the refined 15M base 54,993.40–55,091.45 (2026-10-01 10:30) | entry, base 54877.6–54893.15, inval | `replay/15M_2026-10-05_1345_E1_41.png` |
| 43 | 2026-09-22_2026-10-06 | 2026-10-05 14:00 | E3 | 54,877.60–55,091.45 | added | E3: waiting — price has not reached the refined 15M base 54,993.40–55,091.45 in this visit yet | entry, base 54877.6–54885.35, inval | `replay/15M_2026-10-05_1400_E3_42.png` |
| 44 | 2026-09-22_2026-10-06 | 2026-10-06 09:15 | E1 | 54,877.60–55,091.45 | removed | entry, base 54993.4–55091.45, inval | E1: fired_earlier — 2026-10-05 13:45:00 | `replay/15M_2026-10-06_0915_E1_43.png` |
| 45 | 2026-09-22_2026-10-06 | 2026-10-06 10:30 | E3 | 55,055.80–55,135.50 | removed | entry, base 55055.8–55091.45, inval | E3: cluster_consumed — E3 already fired in this cluster's visit on area 294 at 2026-10-05 14:00:00 — one place | `replay/15M_2026-10-06_1030_E3_44.png` |
| 46 | 2026-09-22_2026-10-06 | 2026-10-06 12:30 | E1 | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, next | E1: passed — the refined 15M base 55,035.20–55,074.45 (2026-10-06 09:30) was closed through in this visit at 2 | `replay/15M_2026-10-06_1230_E1_45.png` |
| 47 | 2026-10-07_2026-10-21 | 2026-10-07 12:30 | E3 | 54,886.20–55,192.65 | same trigger, base / invalidation changed | base 55111.65–55192.65, next | base 54993.75–55128.4, next | `replay/15M_2026-10-07_1230_E3_46.png` |
| 48 | 2026-10-07_2026-10-21 | 2026-10-08 09:15 | E3 | 54,886.20–55,192.65 | added | E3: waiting — the candle did not trade into the refined 15M base 55,111.65–55,192.65 (only the wider context a | entry, base 54993.75–55128.4, next | `replay/15M_2026-10-08_0915_E3_47.png` |
| 49 | 2026-10-07_2026-10-21 | 2026-10-09 09:30 | E1 | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, inval | E1: passed — the refined 15M base 54,886.20–54,907.15 (2026-10-08 11:45) was closed through in this visit at 2 | `replay/15M_2026-10-09_0930_E1_48.png` |
| 50 | 2026-10-07_2026-10-21 | 2026-10-09 09:30 | E1 | 55,143.05–55,201.00 | added | E1: cluster_consumed — E1 fired on overlapping area 297 at this bar — one place, one signal per model | entry, base 55175.0–55201.0, inval | `replay/15M_2026-10-09_0930_E1_49.png` |
| 51 | 2026-10-07_2026-10-21 | 2026-10-09 11:00 | E3 | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, inval | E3: waiting — the candle did not trade into the refined 15M base 54,886.20–54,907.15 (only the wider context a | `replay/15M_2026-10-09_1100_E3_50.png` |
| 52 | 2026-10-07_2026-10-21 | 2026-10-09 11:00 | E3 | 55,143.05–55,201.00 | added | E3: cluster_consumed — E3 fired on overlapping area 297 at this bar — one place, one signal per model | entry, base 55175.0–55201.0, inval | `replay/15M_2026-10-09_1100_E3_51.png` |
| 53 | 2026-10-07_2026-10-21 | 2026-10-12 09:15 | E2 | 55,408.35–55,650.35 | added | E2: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 55408.35–55419.3, inval | `replay/15M_2026-10-12_0915_E2_52.png` |
| 54 | 2026-10-07_2026-10-21 | 2026-10-12 09:15 | E3 | 55,408.35–55,650.35 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 55408.35–55419.3, inval | `replay/15M_2026-10-12_0915_E3_53.png` |
| 55 | 2026-10-07_2026-10-21 | 2026-10-14 11:30 | E3 | 55,301.25–55,419.30 | same trigger, base / invalidation changed | base 55353.55–55419.3, next | base 55326.75–55365.75, next | `replay/15M_2026-10-14_1130_E3_54.png` |
| 56 | 2026-10-07_2026-10-21 | 2026-10-15 14:15 | E3 | 55,699.45–55,970.15 | removed | entry, base 55699.45–55762.6, next | E3: waiting — the candle did not trade into the refined 15M base 55,870.65–55,888.30 (only the wider context a | `replay/15M_2026-10-15_1415_E3_55.png` |
| 57 | 2026-10-07_2026-10-21 | 2026-10-16 09:15 | E2 | 55,699.45–55,970.15 | same trigger, base / invalidation changed | base 55699.45–55762.6, next | base 55927.15–55970.15, next | `replay/15M_2026-10-16_0915_E2_56.png` |
| 58 | 2026-10-07_2026-10-21 | 2026-10-16 09:15 | E3 | 55,699.45–55,970.15 | added | E3: fired_earlier — 2026-10-15 14:15:00 | entry, base 55927.15–55970.15, next | `replay/15M_2026-10-16_0915_E3_57.png` |
| 59 | 2026-10-07_2026-10-21 | 2026-10-16 14:30 | E3 | 55,699.45–55,970.15 | removed | entry, base 55699.45–55762.6, next | E3: waiting — the candle did not trade into the refined 15M base 55,863.80–55,926.50 (only the wider context a | `replay/15M_2026-10-16_1430_E3_58.png` |
| 60 | 2026-10-07_2026-10-21 | 2026-10-19 09:15 | E2 | 55,699.45–55,970.15 | same trigger, base / invalidation changed | base 55699.45–55762.6, next | base 55827.45–55883.7, next | `replay/15M_2026-10-19_0915_E2_59.png` |
| 61 | 2026-10-07_2026-10-21 | 2026-10-19 09:15 | E3 | 55,699.45–55,970.15 | added | E3: fired_earlier — 2026-10-16 14:30:00 | entry, base 55827.45–55883.7, next | `replay/15M_2026-10-19_0915_E3_60.png` |

### 5.2 Per model — 5M trigger (`walk5.py`, reading mode)

| model | before: entries | next area first | invalidation first | open | after: entries | next area first | invalidation first | open |
|---|---|---|---|---|---|---|---|---|
| E1 | 22 | 3 | 19 | 0 | 24 | 3 | 21 | 0 |
| E3 | 9 | 2 | 7 | 0 | 9 | 3 | 6 | 0 |
| E4a | 11 | 6 | 5 | 0 | 15 | 7 | 8 | 0 |
| E4b | 10 | 3 | 7 | 0 | 10 | 3 | 7 | 0 |
| **all** | 52 | 14 | 38 | 0 | 58 | 16 | 42 | 0 |

Changed entries (5M): 46 — added E1: 9, added E3: 4, added E4a: 10, removed E1: 7, removed E3: 4, removed E4a: 6, same trigger, base / invalidation changed E1: 4, same trigger, base / invalidation changed E3: 1, same trigger, base / invalidation changed E4a: 1

| # | group | trigger | model | area | change | before | after | chart |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-10_2026-05-24 | 2026-05-13 10:55 | E3 | 53,600.40–53,930.00 | removed | entry, base 53600.4–53930.0, inval | E3: waiting — 5M: lower high 53,789.5, no close below HL 53,665.4 yet (wick only) | `replay/5M_2026-05-13_1055_E3_0.png` |
| 2 | 2026-05-10_2026-05-24 | 2026-05-13 13:35 | E4a | 53,600.40–53,930.00 | removed | entry, base 53600.4–53930.0, next | E4: waiting — the 5M candle did not trade into the refined 15M base 53,764.90–53,800.45 (only the wider contex | `replay/5M_2026-05-13_1335_E4a_1.png` |
| 3 | 2026-05-10_2026-05-24 | 2026-05-13 13:55 | E4a | 53,600.40–53,930.00 | added | E4: fired_earlier — 2026-05-13 13:35:00 | entry, base 53764.9–53800.45, next | `replay/5M_2026-05-13_1355_E4a_2.png` |
| 4 | 2026-05-10_2026-05-24 | 2026-05-14 10:15 | E4a | 53,600.40–53,930.00 | removed | entry, base 53600.4–53930.0, next | E4: waiting — the candle did not trade inside the area — price has left the area on the trade side (the trigge | `replay/5M_2026-05-14_1015_E4a_3.png` |
| 5 | 2026-05-10_2026-05-24 | 2026-05-20 11:00 | E4a | 53,194.25–53,510.20 | added | E4: waiting — the candle did not trade inside the area — price has left the area on the trade side (the trigge | entry, base 53194.25–53290.8, inval | `replay/5M_2026-05-20_1100_E4a_4.png` |
| 6 | 2026-05-10_2026-05-24 | 2026-05-20 12:05 | E3 | 53,194.25–53,510.20 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 53194.25–53290.8, inval | `replay/5M_2026-05-20_1205_E3_5.png` |
| 7 | 2026-06-09_2026-06-23 | 2026-06-10 10:55 | E1 | 55,396.45–55,536.80 | same trigger, base / invalidation changed | base 55459.0–55536.8, inval | base 55465.8–55509.8, inval | `replay/5M_2026-06-10_1055_E1_6.png` |
| 8 | 2026-06-09_2026-06-23 | 2026-06-10 12:30 | E3 | 55,396.45–55,536.80 | removed | entry, base 55459.0–55536.8, inval | E3: waiting — 5M: sweep of high 55,534.65 closed back inside, lower high 55,469.65, no close below HL 55,419.2 | `replay/5M_2026-06-10_1230_E3_7.png` |
| 9 | 2026-06-09_2026-06-23 | 2026-06-10 13:35 | E4a | 55,396.45–55,536.80 | same trigger, base / invalidation changed | base 55459.0–55536.8, next | base 55480.9–55534.65, next | `replay/5M_2026-06-10_1335_E4a_8.png` |
| 10 | 2026-06-09_2026-06-23 | 2026-06-11 12:05 | E1 | 55,396.45–55,536.80 | removed | entry, base 55459.0–55536.8, inval | E1: passed — waiting for a 5M candle to reach the refined 15M base 55,506.55–55,536.80 (2026-06-10 13:00) | `replay/5M_2026-06-11_1205_E1_9.png` |
| 11 | 2026-06-09_2026-06-23 | 2026-06-16 09:15 | E4a | 57,371.45–57,456.30 | added | E4: area not armed at this bar | entry, base 57371.45–57399.2, inval | `replay/5M_2026-06-16_0915_E4a_10.png` |
| 12 | 2026-06-09_2026-06-23 | 2026-06-17 10:50 | E1 | 57,558.20–57,628.40 | added | E1: area not armed at this bar | entry, base 57558.2–57590.6, inval | `replay/5M_2026-06-17_1050_E1_11.png` |
| 13 | 2026-06-09_2026-06-23 | 2026-06-17 11:50 | E4a | 57,558.20–57,628.40 | added | E4: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57558.2–57590.6, inval | `replay/5M_2026-06-17_1150_E4a_12.png` |
| 14 | 2026-06-09_2026-06-23 | 2026-06-17 11:55 | E3 | 57,558.20–57,628.40 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57558.2–57590.6, inval | `replay/5M_2026-06-17_1155_E3_13.png` |
| 15 | 2026-07-09_2026-07-23 | 2026-07-17 10:15 | E1 | 58,078.90–58,251.95 | same trigger, base / invalidation changed | base 58078.9–58148.8, inval | base 58084.7–58118.6, inval | `replay/5M_2026-07-17_1015_E1_14.png` |
| 16 | 2026-07-09_2026-07-23 | 2026-07-17 10:40 | E3 | 58,078.90–58,251.95 | same trigger, base / invalidation changed | base 58078.9–58148.8, inval | base 58084.7–58118.6, inval | `replay/5M_2026-07-17_1040_E3_15.png` |
| 17 | 2026-07-24_2026-08-07 | 2026-08-06 09:25 | E1 | 57,569.60–58,247.95 | added | E1: passed — waiting for a 5M candle to reach the refined 15M base 57,895.60–57,931.85 (2026-08-05 09:45) | entry, base 57846.9–57875.65, inval | `replay/5M_2026-08-06_0925_E1_16.png` |
| 18 | 2026-07-24_2026-08-07 | 2026-08-06 10:55 | E1 | 57,569.60–58,247.95 | removed | entry, base 57895.6–57931.85, inval | E1: fired_earlier — 2026-08-06 09:25:00 | `replay/5M_2026-08-06_1055_E1_17.png` |
| 19 | 2026-08-08_2026-08-22 | 2026-08-17 13:00 | E1 | 57,611.70–57,799.15 | added | E1: area not armed at this bar | entry, base 57633.5–57681.45, inval | `replay/5M_2026-08-17_1300_E1_18.png` |
| 20 | 2026-08-08_2026-08-22 | 2026-08-21 09:40 | E1 | 57,611.70–57,799.15 | removed | entry, base 57711.95–57757.25, inval | E1: passed — E1 fires only on the visit's first 5M candle at the refined 15M base 57,686.25–57,702.95 (2026-08 | `replay/5M_2026-08-21_0940_E1_19.png` |
| 21 | 2026-08-08_2026-08-22 | 2026-08-21 09:50 | E1 | 57,771.35–57,885.85 | added | E1: area not armed at this bar | entry, base 57771.35–57885.85, inval | `replay/5M_2026-08-21_0950_E1_20.png` |
| 22 | 2026-08-08_2026-08-22 | 2026-08-21 10:35 | E4a | 57,497.80–57,716.05 | added | E4: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57708.6–57716.05, inval | `replay/5M_2026-08-21_1035_E4a_21.png` |
| 23 | 2026-08-23_2026-09-06 | 2026-08-24 10:05 | E4a | 57,611.70–57,799.15 | removed | entry, base 57711.95–57757.25, inval | E4: waiting — 5M sweep seen; waiting for the next 5M push to fail inside the sweep extreme (a confirmed 5M swi | `replay/5M_2026-08-24_1005_E4a_22.png` |
| 24 | 2026-08-23_2026-09-06 | 2026-09-02 10:20 | E1 | 57,158.10–57,214.80 | added | E1: area not armed at this bar | entry, base 57185.45–57214.8, inval | `replay/5M_2026-09-02_1020_E1_23.png` |
| 25 | 2026-08-23_2026-09-06 | 2026-09-02 10:40 | E4a | 57,158.10–57,214.80 | added | E4: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 57185.45–57214.8, inval | `replay/5M_2026-09-02_1040_E4a_24.png` |
| 26 | 2026-08-23_2026-09-06 | 2026-09-03 09:40 | E1 | 57,397.35–58,024.95 | removed | entry, base 57728.65–57766.25, next | E1: passed — the refined 15M base 57,397.35–57,409.60 (2026-09-01 15:15) was closed through in this visit at t | `replay/5M_2026-09-03_0940_E1_25.png` |
| 27 | 2026-09-07_2026-09-21 | 2026-09-15 09:15 | E1 | 56,823.20–57,006.45 | added | E1: area not armed at this bar | entry, base 56988.2–57006.45, next | `replay/5M_2026-09-15_0915_E1_26.png` |
| 28 | 2026-09-07_2026-09-21 | 2026-09-17 09:35 | E1 | 56,549.40–56,742.60 | same trigger, base / invalidation changed | base 56551.65–56552.85, inval | base 56549.4–56628.1, inval | `replay/5M_2026-09-17_0935_E1_27.png` |
| 29 | 2026-09-22_2026-10-06 | 2026-09-23 10:00 | E1 | 56,474.40–56,570.45 | same trigger, base / invalidation changed | base 56474.4–56570.45, inval | base 56496.8–56503.75, inval | `replay/5M_2026-09-23_1000_E1_28.png` |
| 30 | 2026-09-22_2026-10-06 | 2026-09-23 14:55 | E4a | 56,474.40–56,570.45 | added | E4: fired_earlier — 2026-09-23 11:50:00 | entry, base 56496.8–56503.75, next | `replay/5M_2026-09-23_1455_E4a_29.png` |
| 31 | 2026-09-22_2026-10-06 | 2026-10-05 13:45 | E1 | 54,854.25–55,025.60 | added | E1: area not armed at this bar | entry, base 54856.3–54893.15, inval | `replay/5M_2026-10-05_1345_E1_30.png` |
| 32 | 2026-09-22_2026-10-06 | 2026-10-05 14:00 | E3 | 54,854.25–55,025.60 | added | E3: waiting — no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait | entry, base 54856.3–54893.15, inval | `replay/5M_2026-10-05_1400_E3_31.png` |
| 33 | 2026-09-22_2026-10-06 | 2026-10-06 09:15 | E1 | 54,877.60–55,091.45 | removed | entry, base 54993.4–55091.45, inval | E1: area not armed at this bar | `replay/5M_2026-10-06_0915_E1_32.png` |
| 34 | 2026-09-22_2026-10-06 | 2026-10-06 09:55 | E3 | 55,055.80–55,135.50 | removed | entry, base 55055.8–55091.45, inval | E3: waiting — price has not reached the refined 15M base 55,111.65–55,135.50 in this visit yet (5M) | `replay/5M_2026-10-06_0955_E3_33.png` |
| 35 | 2026-09-22_2026-10-06 | 2026-10-06 13:20 | E4a | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, next | E4: waiting — the 5M candle did not trade into the refined 15M base 55,035.20–55,074.45 (only the wider contex | `replay/5M_2026-10-06_1320_E4a_34.png` |
| 36 | 2026-09-22_2026-10-06 | 2026-10-06 13:40 | E4a | 54,886.20–55,192.65 | added | E4: fired_earlier — 2026-10-06 13:20:00 | entry, base 55035.2–55074.45, next | `replay/5M_2026-10-06_1340_E4a_35.png` |
| 37 | 2026-10-07_2026-10-21 | 2026-10-07 10:15 | E1 | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, inval | E1: passed — waiting for a 5M candle to reach the refined 15M base 54,993.75–55,128.40 (2026-10-06 15:15) | `replay/5M_2026-10-07_1015_E1_36.png` |
| 38 | 2026-10-07_2026-10-21 | 2026-10-07 10:15 | E1 | 55,143.05–55,201.00 | added | E1: area not armed at this bar | entry, base 55175.0–55201.0, inval | `replay/5M_2026-10-07_1015_E1_37.png` |
| 39 | 2026-10-07_2026-10-21 | 2026-10-08 09:15 | E3 | 54,886.20–55,192.65 | added | E3: area not armed at this bar | entry, base 54993.75–55128.4, next | `replay/5M_2026-10-08_0915_E3_38.png` |
| 40 | 2026-10-07_2026-10-21 | 2026-10-08 10:15 | E4a | 54,886.20–55,192.65 | added | E4: waiting — the 5M candle did not trade into the refined 15M base 55,111.65–55,192.65 (only the wider contex | entry, base 54993.75–55128.4, next | `replay/5M_2026-10-08_1015_E4a_39.png` |
| 41 | 2026-10-07_2026-10-21 | 2026-10-09 09:30 | E1 | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, inval | E1: passed — the refined 15M base 54,886.20–54,907.15 (2026-10-08 11:45) was closed through in this visit at t | `replay/5M_2026-10-09_0930_E1_40.png` |
| 42 | 2026-10-07_2026-10-21 | 2026-10-09 09:40 | E1 | 55,143.05–55,201.00 | added | E1: passed — waiting for a 5M candle to reach the refined 15M base 55,175.00–55,201.00 (2026-10-06 12:45) | entry, base 55175.0–55201.0, inval | `replay/5M_2026-10-09_0940_E1_41.png` |
| 43 | 2026-10-07_2026-10-21 | 2026-10-09 11:05 | E3 | 54,886.20–55,192.65 | removed | entry, base 55111.65–55192.65, inval | E3: waiting — the 5M candle did not trade into the refined 15M base 54,886.20–54,907.15 (only the wider contex | `replay/5M_2026-10-09_1105_E3_42.png` |
| 44 | 2026-10-07_2026-10-21 | 2026-10-14 13:45 | E4a | 55,301.25–55,419.30 | removed | entry, base 55353.55–55419.3, inval | E4: fired_earlier — 2026-10-14 13:05:00 | `replay/5M_2026-10-14_1345_E4a_43.png` |
| 45 | 2026-10-07_2026-10-21 | 2026-10-15 14:45 | E4a | 55,699.45–55,970.15 | removed | entry, base 55699.45–55762.6, next | E4: waiting — the 5M candle did not trade into the refined 15M base 55,870.65–55,888.30 (only the wider contex | `replay/5M_2026-10-15_1445_E4a_44.png` |
| 46 | 2026-10-07_2026-10-21 | 2026-10-16 09:15 | E4a | 55,699.45–55,970.15 | added | E4: area not armed at this bar | entry, base 55870.65–55888.3, next | `replay/5M_2026-10-16_0915_E4a_45.png` |

### 5.3 A5 on the replay rows — visits under several ids, models fired twice in one visit

| run | visits with an entry | visits seen under more than one visit id | a model fired twice in one visit |
|---|---|---|---|
| before_15M | 42 | 2 (280@2026-10-15 10:00:00 / 281@2026-10-15 10:00:00; 278@2026-10-16 10:00:00 / 280@2026-10-16 10:00:00) | 0 |
| before_5M | 39 | 0 | 0 |
| after_15M | 51 | 0 | 0 |
| after_5M | 43 | 0 | 0 |


## 6. Tests

- New: `tests/test_area_identity_refined_base.py` (both mirrors): the same place keeps its uid when the data window moves (and the list
  index moved); a reused index never names two places; visit ids carry the uid and match across windows; the cluster anchor / order
  never depend on the list index; duplicate ids cannot bypass `max_hits_per_zone`; the refined base is the newest 15M turn inside the
  band as its wick to body (no look-ahead: not before its confirmation), reads every 15M turn (not only D1), counts a sweep-poke turn
  clipped to the band, ignores a turn wholly beyond the band, never takes a turn from before the area's birth turn / base candle; the
  298 band = its own candle's wick to body.
- Re-pinned (content changed by design, no golden touched): `tests/test_trigger_5m.py` PIN15 / PIN15_C (rows carry `uid`, refined base),
  `tests/test_model_c.py` PIN (same), `tests/fixtures/dossier_15m_pin.json.gz` (only the added `uid` key differs — checked: equal with
  `uid` removed).
- Wiring: `facts/dossier.py` builds the engine's visit id with the uid; `decision3/range_edges.py` edge rows carry `uid` (snapshot key
  compatibility).
- Golden `tests/test_decision3_flip.py` and `tests/test_method_no_numbers.py` pass unchanged. Locally only the tests touching the change
  were run (CLAUDE.md §6); the full suite runs in CI.
- Note: a first version of `compare.py` imported the old 15M-vs-5M analysis module, whose import re-ran it and overwrote
  trade-data `review/replay_banknifty_6m/trigger5m/c2be8aa/all_rows.json` + `summary.json` (restored by the coordinator). The runner now
  uses a read-only copy of the outcome helpers and writes only to its scratch folder and `review/gallery_fixes/A567/`.

## 7. Logged

- OPEN_QUESTIONS (`docs/reports/v22/OPEN_QUESTIONS.md`, section "Gallery review A5–A7"): A5-1 … A5-3, A6-1, A6-2, A7-1 … A7-4.
- READING_ERRORS (`docs/reader/READING_ERRORS.md`): rows A5, A6, A7.
