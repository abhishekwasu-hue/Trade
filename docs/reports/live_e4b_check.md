Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders

# Live reading check — BANKNIFTY E4 (b) bear call at a broken line (owner-orders INBOX 23 Oct, items 1–7; DECISIONS 38–41; addition C / D)

## सारांश (मराठी)
- **Live entry:** 22–23 Oct ची BANKNIFTY engine signals trade-data मध्ये नाहीत (शेवटची export 21 Oct; 15M spot 19 Oct पर्यंत). खाली दिलेला
  read-only VPS command (engine_signals.db + vision.db) चालवून output पाठवा. तोपर्यंत 13 BANKNIFTY replay groups वर तपासलं.
- **1 (approach side):** E4 (b) मध्ये approach बाजू तपासलीच जात नव्हती — वरून खाली येणारी, line मधून close करणारी candle (breakdown, H2)
  सुद्धा "rejection" म्हणून चालत होती. आता नियम: break बाजूनेच retest (bear call: खालून वर येऊन नकार). Replay: E4 (b) 17 → 10.
- **2 (line dead):** #373 (`trendline.broken_back_at`) मध्ये हा नियम lines साठी आधीच आहे (close back + त्या बाजूला 1H swing ⇒ line dead,
  E4 (b) नाही). VPS वर शेवटचा confirmed deploy c3e9f0a आहे — त्यात #373 नाही. म्हणजे live entry बहुधा जुन्या code ने झाली. VPS
  command मधली पहिली ओळ commit दाखवेल.
- **3 (range):** range edges entry models ला जोडलेलेच नव्हते (`range_edges.armable` फक्त hook होता; range state फक्त evidence). आता
  Daily / 1H range च्या edges = areas (bear call वरच्या edge ला, bull put खालच्या; trend बाजूच, P4). Replay मध्ये यामुळे एकही नवी
  entry नाही — कारण range reader सर्वात बाहेरची (outer) range वाचतो, आणि 13 groups मध्ये किंमत त्या edge पर्यंत गेली नाही.
- **4 (evidence):** "required set ✗", grade None ही दाखवणी बरोबर आहे — evidence कधीच block करत नाही (DECISIONS 6). E4 (b) च्या FORM मध्ये
  कमी होती ती approach बाजू — ती आता जोडली.
- **5 / 6 (card):** line आता "broken 1H line at X (…, broken down), retest from below" — "supply area X–X (0 pts)" नाही. E4 (b) च्या
  सगळ्या lines 1H degree (D2) च्या आहेत. Card header: आधी signal चं symbol, bot नाव लहान label; engine signal साठी
  "Price-action engine (PAPER)".
- **7:** replay मध्ये item 1 चे 7 entries (5 next area first, 2 invalidation first), item 2 चे 11 (#373 ने आधीच काढलेले: 7 invalidation
  first, 4 next first). E1 / E2 / E3 / E4 (a) बदलले नाहीत.
- Tests: नवीन 18 (दोन्ही mirrors) — सगळे pass; ठरवलेले सगळे test files: 7 जुने failures (main वरही तेच — chart rendering), बाकी pass.

## Where the live entry is (data)
- trade-data has no BANKNIFTY engine signal after 21 Oct: `review/diagnosis_today/2026-10-21/vps*/live/engine_signals.json` ends 21 Oct
  (the v2.2 gate era, all "wait"); `banknifty/vps_spot_history/2026-10-21_2337/BANKNIFTY_15m.csv.gz` ends 19 Oct 15:15, the VPS 5M /
  FUT 5M exports end 21 Oct. The live E4 (b) of 22 / 23 Oct cannot be replayed bar by bar here.
- Read-only VPS command (no write, after market close; paste the output):

```
cd /root/Trade && git log -1 --format='%h %s' && python3 - <<'PY'
# READ-ONLY: the live BANKNIFTY E4 (b) entries of the last sessions (engine store + Vision rows). Nothing is written.
import json, sqlite3
E = sqlite3.connect("file:data/engine_signals.db?mode=ro", uri=True)
for bar_ts, payload in E.execute("SELECT bar_ts, payload FROM engine_signals WHERE symbol='BANKNIFTY' AND bar_ts >= '2026-10-21' "
                                 "AND payload LIKE '%\"E4\"%' ORDER BY bar_ts"):
    p = json.loads(payload or "{}")
    for e in p.get("entries") or []:
        if e.get("model") != "E4":
            continue
        a = e.get("area") or {}
        print("ENTRY", bar_ts, e.get("name"), e.get("object"), a.get("id"), a.get("tf"), a.get("lo"), a.get("hi"),
              "line", json.dumps(a.get("line")), "ref", e.get("entry_ref"), "inv", e.get("invalidation"),
              "visit", e.get("visit_start"), "label", e.get("label"), "ev", json.dumps(e.get("evidence")))
    rs = p.get("range_state") or {}
    print("  RANGE", bar_ts, rs.get("tfs_in_range"), json.dumps({k: (v or {}).get("band") for k, v in (rs.get("by_tf") or {}).items()}))
    for a in p.get("armed") or []:
        print("  ARMED", a.get("object"), a.get("area_id"), a.get("tf"), a.get("lo"), a.get("hi"), a.get("visit_start"),
              json.dumps({m: x.get("status") for m, x in (a.get("models") or {}).items()}), (a.get("disarmed") or "")[:80])
for r in E.execute("SELECT * FROM engine_entry_consumed WHERE symbol='BANKNIFTY' AND bar_ts >= '2026-10-21' ORDER BY bar_ts"):
    print("CONSUMED", r)
V = sqlite3.connect("file:data/vision.db?mode=ro", uri=True)
for r in V.execute("SELECT signal_id, signal_ts, status, verdict, final_decision, setup_json FROM vision_signals WHERE symbol='BANKNIFTY' "
                   "AND signal_ts >= '2026-10-21' AND setup_json LIKE '%\"entry_model\": \"E4\"%' ORDER BY signal_ts"):
    t = (json.loads(r[5] or "{}").get("tags") or {})
    print("VISION", r[:5], t.get("entry_label"), t.get("entry_object"), (t.get("gate") or {}).get("area"), t.get("entry_invalidation"))
PY
```

With that output (the line id, its p1 / slope, break bar, the trigger bar and the commit) the live case is replayed exactly; the BANKNIFTY
15M / 5M / FUT history of 20–23 Oct comes with the next regular VPS export.

## Answers 1–7

**1. Approach side (DECISIONS 38).** Code before this fix (`entry_models.Reader.broken` → `rejection` + `retest_ok`): an E4 (b) fired at
the first bar of the revisit where `method.reversal_form` reads a form, the bar (or the bar before) touches the object and the bar
CLOSES on the trade side of it. Nothing read where price came FROM: a candle that opened above a line broken down (price accepted above)
and closed below it is, by these checks, a "strong close" rejection — that is a breakdown candle (H2). The revisit start
(`touch_visit`: the first bar touching the object after a swing away from it) was also taken from either side. **Fixed:**
`Reader.approach_side` (setting `e4b_approach_rule = break_side`, default by DECISIONS 38; `any` = the earlier reading, what-if):
(a) the close before the revisit's first bar is not beyond the object's original side, and (b) the rejection form's first candle did not
open beyond the original side (one-candle form: the trigger bar; two-candle form: its first candle). Original-side edge: a line = its value
at that bar; a broken support area = its high; a broken resistance area = its low. Both mirrors; both lines and broken areas. Comparison
only, bars ≤ t, no number.

**2. Dead after a second break (DECISIONS 39, T-2 for lines).** Already covered by #373 (`trendline.broken_back_at`, read in
`Reader.broken_objects` for every E4 (b) line object): a broken line that price closes back through on its original side, with a swing of
the line's own degree (1H, D2) formed and confirmed there while the closes hold, is never an E4 (b) object again. That covers the order's
case for lines and for broken channel parallels; areas have it since #368 (`flip_dead_rule = broken_again`). **Why the live entry still
used the line:** the last deploy Abhi confirmed is c3e9f0a (#368–#371, README row 27); #373 (3809ea2) merged after it, so the live engine
most likely ran without the line lifecycle. The VPS command's first line shows the commit. Second possibility, for Abhi's eye: the swings
above the line were only 15M (D1) swings, not 1H — `broken_back_at` reads the line's own degree (as Levels reads an area's reclaim on the
level degree); then the line stays broken by the method's definition, and item 1 (the trigger came from above) is what removes the entry.
No change made to the degree (no new rule).

**3. Range edges (DECISIONS 40, concept L).** Before: the range was READ (`range_edges.range_state`, every row, evidence only) but its
edges were NEVER armed: `range_edges.armable` was a hook "wiring = T9 — entry_models.py untouched"; the models armed only `Levels.active`
areas (+ the Daily RANGE (Q27) edge-side areas when the Daily trend is RANGE). So an upper edge that price rejected several times was a
trade location only if Levels had built a 1H / Daily area there. **Fixed:** `range_edges.trade_edges` (the current Daily / 1H range from
structure, each edge = its swing candle wick to body, fresh / tested, not broken / flipped / dead — the levels' own K4 machine; the same
cache as the row's range_state) ⇒ `Reader.range_edge_areas` adds them to the armed list: bear call at the upper edge, bull put at the lower
edge, trade side only (P4: Daily DOWN ⇒ upper edge, UP ⇒ lower, RANGE ⇒ both), ahead of price like `Levels.active`; an edge with the same
band as an armed area is that area; the visit counts from the bar the range is known. E1–E4 (a) read them as any area (refined base,
traded_inside, invalidation from the edge). Setting `range_edge_areas = on` (off = what-if). Replay: **no new entry** in the 13 groups —
the range reader keeps the OUTER range (the oldest unbroken pair, T7 definition approved 21 Oct): in 07–21 Oct the 1H range is
53,785.70–56,623.80 on all 225 bars and the 15M one 53,785.70–55,762.60, price never visited a current D / 1H edge. Two questions logged
(OPEN_QUESTIONS): 15M range edges are not armed (15M = the setup TF: refined base / trigger), and an inner range inside the outer one is not
read — Abhi's live range (the broken line ↔ an upper edge rejected several times) may be such an inner range.

**4. Evidence ✗ / grade None vs the E4 (b) definition.** The method's E4 (b) = the rejection form at the retested object (method §8:
"E4 (b): the rejection form trades at the retested object and closes on its trade side"); evidence is listed and never blocks (CLAUDE.md;
DECISIONS 6: no 6a required set for the models). The card's "required set ✗" (no handover / commitment / LTF CHoCH) and label None
(6a: A and B both need the required set) are therefore the correct listing, not a bug. What WAS missing from the form itself is the
approach side (item 1): a retest is a rejection coming from the break side; the code accepted a close through from the original side.
Nothing else in the form is missing (touch at the object, trade-side close, not beyond the retest extreme — all read).

**5. Card text (DECISIONS 41).** Was: the line object went into the gate area as `[v, v]` ⇒ "supply area 55,710–55,710 (0 pts)". Now
(`paper/engine_entry.object_tags` ⇒ tag `entry_line` {tf, degree, family, break_side, value}; `vision/card_summary.object_words`): classic
title "BANKNIFTY · E4 — Sweep-retest (b): a bear call (bearish) trade at the broken 1H line at 55,710 (rising line of lows, broken down),
retest from below (15M chart). Look at the line …"; summary 📍 the same words; details line "Broken 1H line at …"; engine chart label
"BROKEN 1H LINE (retest from below)"; Vision facts "Retested object: broken 1H line (…, broken down) at X at the trigger; retest from below —
price must come back to the line from the break side and be rejected there". Broken areas say "broken 1H area X–Y, retest from below"; a
range edge "1H range upper edge X–Y".

**6. The line's TF / degree.** E4 (b) line objects are `trendline.channel_lines(V, t)` + `channels(V, t)` parallels at the default degree
= `level_degree` (D2, the 1H swings of the 1H areas) — every replayed E4 (b) line id is `D2:…` (1H). 15M (D1) lines are evidence only; D / W
lines (T3) are display only. The card now shows it ("1H line"). Header: the signal's own symbol first (`👁 <b>BANKNIFTY</b> · Vision V1 —
PAPER · <i>Price-action engine (PAPER)</i>`), the bot name only as a small label; the level bots' header is unchanged.

**7. Matching entries (replay, 13 BANKNIFTY groups 13 Apr – 21 Oct; outcome by structure: the next opposite area first vs a close beyond
the invalidation first; 12 groups reading-only (no near-month FUT, REPORT_STANDARD 0a), 07–21 Oct testable).**

Item 1 (came from the original side / breakdown candle) — removed by this fix:

| trigger | object (1H line) | entry ref | invalidation | why (engine text) | result | MFE / MAE |
|---|---|---|---|---|---|---|
| 15 May 14:15 | D2:H+:500-514 parallel | 53,972.65 | 54,325.45 | revisit came from above | next area first | 70.3 / 13.6 |
| 02 Jul 14:00 | D2:H+:1148-1262 parallel | 57,910.30 | 58,066.40 | revisit came from above | invalidation first | 25.7 / 187.5 |
| 03 Sep 10:30 | D2:L+:1505-1527 | 57,595.90 | 57,753.60 | trigger opened above, closed through | next area first | 477.9 / 81.2 |
| 23 Sep 11:45 | D2:L+:1424-1467 | 56,529.00 | 56,611.60 | revisit came from above | next area first | 907.6 / 94.1 |
| 07 Oct 11:45 | D2:L+:1494-1511 | 55,221.80 | 55,340.70 | revisit came from above | next area first | 113.0 / 87.9 |
| 09 Oct 11:45 | D2:H+:1489-1507 parallel | 55,044.40 | 55,247.00 | trigger opened above, closed through | invalidation first | 0.0 / 263.4 |
| 12 Oct 09:30 | D2:L+:1436-1476 | 55,028.55 | 55,419.30 | revisit came from above | next area first | 66.7 / 109.1 |

Item 2 (broken back before the retest) — removed earlier by #373 (results from the pre-#373 replay, same harness): 20 May 13:15
(D2:L-:501-531, invalidation first, MAE 434), 30 Jun 14:00 (invalidation first, 243), 08 Jul 09:15 (next first), 13 Jul 09:15
(invalidation first, MAE 919), 13 Jul 10:30 (invalidation first), 20 Jul 09:15 (next first), 20 Jul 14:15 (next first), 02 Sep 11:15
(invalidation first, MAE 669), 07 Sep 09:15 (next first), 24 Sep 13:45 (invalidation first) — plus 14 May 10:30 (area 265, the K4 reclaim
fix, invalidation first, MAE 684). 7 invalidation first, 4 next first.
Live entries matching 1 or 2: only the reported BANKNIFTY E4 (b) is known; the VPS command lists all of them.
P7: the removed item-1 entries were not valid reads (5 of 7 reached the next area — a breakdown candle can win; the method still does
not take it). Never tuned.

## Before / after (same data, same outcome rule; per model, entries (next first / invalidation first), worst MAE)

| model | before (branch head 32af692) | after: approach side only (`range_edge_areas = off`) | after: both (defaults) |
|---|---|---|---|
| E1 | 25 (8 / 17) | 25 (8 / 17) | 25 (8 / 17) |
| E2 | 2 (2 / 0) | 2 (2 / 0) | 2 (2 / 0) |
| E3 | 19 (12 / 7) | 19 (12 / 7) | 19 (12 / 7) |
| E4 a | 0 | 0 | 0 |
| E4 b | 17 (10 / 7), MAE 590.8 | 10 (5 / 5), MAE 590.8 | 10 (5 / 5), MAE 590.8 |
| all | 63 (32 / 31) | 56 (27 / 29) | 56 (27 / 29) |

E1 / E2 / E3 entries are identical entry by entry (trigger, entry ref, invalidation, area). Changed groups (E4 b): 10–24 May 1 → 0,
24 Jun – 8 Jul 1 → 0, 23 Aug – 6 Sep 1 → 0, 22 Sep – 6 Oct 5 → 4, 07–21 Oct (testable) 3 → 0. The what-if
(`e4b_approach_rule = any`, `range_edge_areas = off`) reproduces the before column on the checked groups (22 Sep – 21 Oct).

## Addition C / D (engine card and name)
- C — what the Telegram card sends for `signal_source = engine`: `vision/worker.process_row` renders with `vision/chart.render`, which
  routes every engine signal (`engine_audit.use_engine`, `vision_engine_audit = engine` default) to the engine card (`engine_figure` /
  `engine_card.build_figure`: HTF strip, the area or line with its state and TF, the refined 15M base, the trigger candle, INV, NEXT, the
  FUT volume pane; no L line / PDH / ORH / opening / gap overlays) and audits it with the engine checklist (T-5, #369). That photo is what
  `v1_notify` sends. What still showed the old reading was the TEXT: "supply area X–X (0 pts)" for a line, the model before the symbol, and
  the bot name "NIFTY 15M Dynamic SR" in the header — fixed (items 5 / 6). The trigger: `engine_card.trigger_panel` is the plug point for
  the 5M trigger build (a trigger-TF frame ⇒ an inset with the trigger candle); today the engine's trigger TF is 15M, boxed on the setup
  panel. Vision prompt `engine_check_v2` (approach side, lines flip once, range edges, a line is a line).
- T-6: engine trades use the same exit path (`paper/watch.exit_bot` by the trade's source) — `tests/test_paper*.py` pass unchanged.
- D — label: `engine_signal.ENGINE_LABEL = "Price-action engine (PAPER)"`; used for engine signals on the Vision row (`vision/hook`,
  `bot_label`; the bot's own label kept as `bot_own_label`), the card header, the engine chart title, the PAPER entry / exit / P&L messages
  (`paper/watch.bot_label` by the journal's signal_source), `/status` and the dashboard page (an info line when signal_source = engine).
  `own` keeps the old name; the level bots' cards and messages are byte-identical (pinned).

## Checks against DECISIONS / CLAUDE.md / method (provisional choices)
- Approach rule = DECISIONS 38 verbatim, read as H2 (P4 "never a breakout entry") — the same open / close comparisons as `h2_block`.
- Lines dead = DECISIONS 27 / 39, #373 unchanged.
- Range edges armed on the trade side only: P4 + DECISIONS 40 + method §8 T7; D / 1H only (areas are 1H / Daily context, CLAUDE.md
  refined base); outer range kept (T7, Abhi 21 Oct). Logged as provisional.
- No number added (two word settings, `tests/test_method_no_numbers.py` passes); no look-ahead (bars ≤ t); evidence still never blocks;
  no execution setting; PAPER only.
- Approach side after a single overshoot close from below (review M1): the rejection candle opening above still counts as "from
  above" — PROVISIONAL (OPEN_QUESTIONS); affects 03 Sep and 09 Oct of the 7 removed entries.
