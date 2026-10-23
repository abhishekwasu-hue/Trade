# INBOX — Abhi's instructions, verbatim (append FIRST, before acting; newest last)

Older orders (before this file existed) are summarised in README.md and DECISIONS.md; their full text is in the Price Action Standard
(docs/knowledge/pa_standard/), CHART_READER_METHOD.md and REPORT_STANDARD.md.

---
## 22 Oct — answers on #364
Abhi — answers on #364:
1. Deploy #364 to live PAPER now, before today's open: merge on green CI + review, then ONE VPS block (with --revert). It halves the risk (MAE 4,768 → 2,131) at the same quality (64% vs 65% next area first).
2. E2 = 0 is a spec wording bug (mine, in RC3), not the method. A commitment / rejection candle by nature trades INTO the area and closes AWAY from it in the trade direction; that close IS the confirmation. The rule is: the trigger candle must have traded inside the (refined) area, and price must not be beyond the INVALIDATION side. A close outside the area on the trade-direction side is allowed. Apply the same reading to every model where it matters. Fix it in a follow-up PR with tests, re-run 07–21 Oct, show E2 before / after, and deploy after Abhi's ✅ (not before today's open if it isn't ready).
3. max_hits_per_zone = 4 (Abhi: up to four model entries per visit). Set it in the same VPS block as a settings change, printed in the status. It stays a dashboard setting.
Record 2 and 3 in CLAUDE.md / the method doc.

---
## 22 Oct — #365
Yes deploy

---
## 22 Oct — decisions on #365
Abhi — decisions on #365:
1. The trigger candle itself must trade into the 15M REFINED BASE (not only the wider area), for every model where the refined base applies. Reason: the refined base exists so that entry and invalidation come from the narrow base; a candle that never touches it brings back the wide invalidation (MAE 2,826 → 3,952 with your choice; the 07 Oct 09:15 E2, MAE 539, comes back). Record it in CLAUDE.md / the method doc / owner-orders DECISIONS.
2. Apply it in #365, re-run 07–21 Oct (max hits 4), and show the per-model table + the total MAE before / after.
3. Deploy #365 AFTER today's market close: merge on green CI + review, then ONE VPS block with --revert. Not during market hours.

---
## 22 Oct — consolidated decisions
From Abhi — consolidated decisions (record every item in docs/owner-orders/DECISIONS.md and CLAUDE.md as you set them up in point 4).

1. #365 (the E2 rule) — the trigger candle must trade into the 15M REFINED BASE itself, not only the wider area, for every model where the refined base applies. A close outside the area on the trade-direction side is allowed (that close is the confirmation); a close beyond on the invalidation side is not. Reason: the refined base exists so that entry and invalidation come from the narrow base. Your provisional choice ("the base was reached earlier in the visit") brings back the wide invalidation: total MAE 2,826 → 3,952, and the 07 Oct 09:15 E2 (MAE 539) returns. Apply it in #365, re-run 07–21 Oct (max hits 4), show the per-model table and the total MAE before / after.

2. Sweep / fakeout behaviour — confirmed as you described:
 a. A close beyond the area WITHOUT a swing formed beyond, then price back inside = a fakeout / sweep (K4). The area stays alive and the visit continues.
 b. E4a is the model for it: the next push fails inside the sweep extreme → entry, with the invalidation beyond the sweep extreme.
 c. E2 / E3 may still come later in the same visit (the candle must touch the refined base); their invalidation includes the sweep extreme.
 d. E1 does NOT come back after a sweep (E1 = the first touch, once per visit; the post-sweep entry is E4a's job).
 e. A close beyond + a swing formed beyond = the area is really broken (flip). A later return from the other side is the retest of the flipped area → E4b.
 Add a test that "base_broken" after a single close beyond the refined base ONLY ends E1: it must not mark the area broken (that needs a close beyond + a swing beyond) and must not block E2 / E3 / E4 in the same visit. Add tests for a–e on fixtures.

3. Deploy #365 only AFTER today's market close: merge on green CI + the independent review, then ONE VPS block with --revert, printing the status. Never during market hours. Tell Abhi first whether this morning's #364 deploy status looked correct (he will paste it).

4. Memory protocol (as ATP did in its PR #331), a docs-only PR:
 - add to CLAUDE.md: re-read CLAUDE.md + docs/owner-orders/ at the start of every task and after every compaction, and begin each report with "Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders";
 - create docs/owner-orders/ with README.md (every order + its status), INBOX.md (every new instruction from Abhi, verbatim, appended FIRST, before acting) and DECISIONS.md (owner decisions, append only);
 - back-fill them from the method doc, the Price Action Standard, REPORT_STANDARD and these decisions: entry models E1–E4, human_confirm, max_hits_per_zone 4, the E2 rule above, never merge areas (Z-1u), clean charts, zone refinement, the sweep behaviour above;
 - any provisional decision of yours is first checked against DECISIONS.md and listed in the report.
Trade's private method stays in the repo as it is now; nothing goes into the public ATP repo.

---
## 22 Oct — BANKNIFTY 6-month galleries
Abhi — the BANKNIFTY 6-month galleries (15-day batches) are still missing. Two tracks, in parallel:
1. FUT volume for the months before 30 Sep: report NOW what you found per source: (a) the VPS collector history, (b) trade-data, (c) Upstox's expired-instruments historical data (docs + whether Abhi's plan includes it). If (a) has it, give Abhi ONE read-only export block to run after today's close (the VPS is small; never during market hours). If no source exists, say so plainly.
2. Meanwhile, a READING GALLERY for every 15-day batch of the 6 months, so Abhi can verify the chart reading now. Everything price-based is shown, per REPORT_STANDARD:
 - the areas (refined bases), lines, channels, patterns, swings, the trend per timeframe, RSI divergence, the setups;
 - the E1 / E3 / E4 entries with their outcomes.
 Every volume-dependent item (commitment volume, E2, volume evidence) is marked "FUT volume missing", never filled with spot volume.
 Same code as deployed (record the commit); one HTML gallery per batch, newest first; a running per-model table marked "without volume evidence".
 When the FUT volume arrives, re-run those batches in full and mark the old gallery superseded.
Send each batch as it is ready (one message per batch, no "still waiting" messages). इट्स अर्जंट

---
## 22 Oct — latest replay group review: flipped-area death + duplicate E4b
Abhi — review of the latest replay group (all parts). By model: E3 strongest, E2 clean, E4b mostly good, E1 weakest (expected for aggressive entries; the PAPER statistics decide later, no change). The big moves missed against the Daily side are correct by the method.
One reading check (concept C, the area lifecycle), report first, then fix if the code departs from the method:
- The worst-loss E4b in the group's "worst losses" page was a retest of a FLIPPED area (a broken support acting as resistance). Before that retest, price had closed back above that flipped area AND formed a swing high beyond it, i.e. the flipped area was broken a second time in the opposite direction.
- Method: an area flips only once; broken again after its flip ⇒ DEAD (no second flip). A dead area is never armed, and no E4 (b) retest may use it.
- Check how the code treats "broken again after flip" (level_flip_rule / the death rule), list every replayed entry that used such an area, fix it with a test (flip → broken back with a close beyond + a swing beyond ⇒ dead ⇒ no E4b), re-run, and show the before / after per model.
Do this together with the duplicate-E4b fix (one signal per model per place), in the same PR, before the post-close deploy. Record both in owner-orders DECISIONS as principles, without dates.

---
## 22 Oct (market hours) — merge now
आताच merge kra aani vps block dya

---
## 22 Oct — stop here
कोणताही नवीन जॉब सुरू करू नका जे आतापर्यंत काम झालेला आहे त्याचा रिपोर्ट मला द्या एक एमडी फाईल तयार करा आणि जे झालं आहे ते कमेंट आणि मर्ज करा आणि काम इथेच थांबवा

---
## 22 Oct — md file of the remaining work (recorded late, from the handoff)
आणि अजून कोणते काम शिल्लक आहे त्याची पण एमडी फाईल द्या

---
## 22 Oct — credit limit (recorded late, from the handoff)
क्रेडिट लिमिट संपली असल्यामुळे तुम्ही कोणतही काम करू नका फक्त जे काही करायचं आहे ते मला सांगा मी दुसऱ्याकडून मधून करतो

---
## 22 Oct — md file (recorded late, from the handoff)
Md file de

---
## 22 Oct — new session: read only
repo read kra, kontihi file delete kinwa change karu nka

---
## 22 Oct — new session: go ahead (with the handoff: fix the #367 CI fail, review, merge, VPS block, owner-orders)
ok go ahead

---
## 22 Oct — naked-leg PAPER card (add to T-1)
Add to T-1: the PAPER entry card shows "target ₹0 · R:R NA" and "net credit ₹-…" for a NAKED leg (paper/watch.py) because naked exits run on the dashboard's spot % / premium-points / TSL / EOD settings, not a ₹ level. Show for naked legs: "premium paid ₹…", the active exit rules in words with their dashboard values (SL, TSL, target as spot % / points, EOD exit), and no ₹0 target / R:R NA. Display only; no exit logic change; tests.

---
## Handover pack, new account
Abhi (message with the pack):
Merge and Abhi — handover from my other account. The attached TRADE_HANDOVER_PACK.md is the complete and only order set (T-1 … T-6 + Appendix A, the C-wave plan); it replaces all earlier chat messages on these topics. Read it fully and do its STEP 0 first: re-read CLAUDE.md, REPORT_STANDARD.md and owner-orders; record T-1 … T-6 verbatim in INBOX with README rows and DECISIONS principles (no dates in principles); report the repo / VPS state. Then follow "Order of PRs" without stopping: reports first where the pack says so, self-review every diff, tests for everything, PAPER only, one consolidated VPS block per PR for me (after market close, --revert, say if a restart / migration is needed). Log questions in OPEN_QUESTIONS with a provisional default and keep going. Reports to me in Marathi.

The pack (verbatim, T-1 … T-6, Order of PRs, Appendix A):

## T-1: Vision approval UX bug (the 15M Dynamic SR bot; applies to every V1 bot). Priority 1.

### What Abhi saw
A NIFTY BEARISH signal of the "15M Dynamic SR" bot (srv2_momentum_reversal). He never saw an approve / reject question.
He only saw the chart with the line "⏱ उत्तर आलं नाही ⇒ skip (shadow) · NIFTY BEARISH L22,761". He does not know what
"skip (shadow)" means and cannot find any shadow trade.

### Root cause (read from the code; confirm it)
- `vision/worker.py` `v1_notify` sends the card: the photo, the caption with the deadline, and the ✅ / ❌ / ✏️ / 📝
  buttons when `TG.can_ask()` is OK.
- On the deadline, `v1_housekeeping` calls `TG.edit_any(tg_message_id, "⏱ उत्तर आलं नाही ⇒ skip (shadow) · …")`. The
  editMessageCaption REPLACES the whole caption, and since no reply_markup is sent, it also removes the buttons.
  - The question, the reasons and the deadline are erased.
  - Telegram sends NO notification for an edit.
  - So Abhi sees only a chart plus one line.
- The same erase pattern exists in `vision/approval.py` (lines ~218, ~265, the button results) and
  `vision/telegram_bot.py` (~40, the service-restart cancel).
- If `TG.can_ask()` failed, the card went WITHOUT buttons (the reason is in `why`), and the signal could only time out.
- A timeout gives status REJECTED. The shadow trade is NOT opened at that moment. On the bot's next cycle (the forced
  level), `vision/gate.py` turns REJECTED into SHADOWED, and the bot opens a PAPER shadow with source
  `srv2_momentum_reversal_vision_shadow`, but only if:
  - the bot's gates still pass within `exec_window_min`;
  - no earlier shadow of that source is still open;
  - strike selection works.
  Otherwise the row goes EXPIRED and no shadow is opened.
- `page_performance.py` has labels for the other shadow sources but not for `*_vision_shadow`. So even an opened shadow
  is hard to find.

### Fix (one PR, tests for each)
1. **Never erase a card.**
   - Every outcome edit (timeout, ✅, ❌, ✏️, drift, expired, restart-cancel) keeps the original caption and appends one
     outcome line.
   - Shorten the old part if Telegram's caption limit needs it; the outcome line is never cut.
   - Remove the buttons only after a decision.
   - Put this in one helper, `TG.append_outcome(message_id, original_caption, line)`. Store the original caption on the
     signal row when the card is sent.
2. **Notify every outcome.** Besides the edit, send a NEW short text message, replying to the card (reply_to_message_id)
   so it is linked, for:
   - approved / rejected / no reply / expired / drift-rejected / shadow opened / shadow closed.
3. **Plain words (English UI text is fine; keep it short).** Examples:
   - The card: "Decide by HH:MM. ✅ take · ❌ skip. No reply ⇒ skipped." That is the operational deadline, allowed.
   - The timeout line: "No reply by HH:MM ⇒ trade NOT taken. A comparison-only shadow trade will be recorded if the setup
     is still valid on the next check."
   - Then, depending on what happens next:
     - "Shadow trade opened (comparison only, not counted in results)";
     - or "No shadow: the setup was no longer valid (<reason>)".
   - Never the bare word "shadow" without that explanation.
4. **Make shadow trades visible.** On the Vision page and the Performance page, add a "Shadow trades (rejected / no
   reply)" section for every `<bot>_vision_shadow` source. It shows:
   - the label (e.g. "15M Dynamic SR: shadow");
   - the linked signal / card time, open / closed, entry, exit and P&L;
   - the reason it was rejected (Abhi ❌ / no reply / drift).
   It is kept apart from the real PAPER statistics (the kill switch and P&L totals are unchanged). Add a small summary:
   "Rejected / no-reply signals: N · shadow trades opened M · their P&L".
5. **Approval reachability check.**
   - When `TG.can_ask()` is false, the card says so in plain words ("Buttons unavailable: <reason>; this signal will be
     skipped") and sends one alert a day.
   - Add the listener / `can_ask` state to the bot health line.
6. **Report first (in the PR description and to Abhi in Marathi), for this NIFTY BEARISH L22,761 signal:** the full
   trail.
   - signal_id;
   - the card send time and message id;
   - whether the buttons were attached (the `can_ask` result and reason);
   - the deadline;
   - the timeout;
   - then SHADOWED or EXPIRED and why;
   - whether a shadow trade was opened, and its P&L if closed.
   Do the same for any other V1 signal from today that timed out.
7. Tests:
   - append-not-replace for every edit path;
   - a new message per outcome;
   - the caption limit (the outcome line kept);
   - the shadow section lists `*_vision_shadow` trades and excludes them from the real totals;
   - the no-buttons card text.
   Existing vision tests stay green, and `tests/test_vision_v1.py` is updated, not deleted.
- Deploy: after market close, one block, a service restart of the vision worker / telegram listener, `--revert`. No
  migration unless the stored original caption needs a column; say so if it does.

---

## T-2: Area lifecycle "dead after a second break" + the duplicate E4b fix (one PR, before the next deploy)
Principle (concept C, the area lifecycle):
- An area flips only once. A FLIPPED area that is broken again in the opposite direction (a close beyond + a swing
  beyond) is DEAD:
  - no second flip;
  - never armed;
  - never used by an E4 (b) retest.
- Observed: the worst-loss E4b of the latest BANKNIFTY replay group retested a flipped area (a broken support acting as
  resistance), after price had already closed back above it AND formed a swing high beyond it.
- Work:
  1. Check how the code treats "broken again after flip" (level_flip_rule / the death rule).
  2. List every replayed entry that used such an area.
  3. Fix it, with tests:
     - flip → broken back (close + swing beyond) ⇒ dead ⇒ no E4b;
     - flip → a sweep back (close without a swing) ⇒ still flipped.
  4. Re-run, and show before / after per model.

Duplicate E4b principle:
- One signal per model per place. Two overlapping broken areas / lines at the same place on the same bar give ONE E4b,
  not two (Z-1u: count once, never merge the bands).
- `max_hits_per_zone` counts the visited place.
- Tests:
  - two overlapping broken areas on the same bar ⇒ one E4b;
  - two separate places ⇒ two.

Same PR as the open trigger follow-up (`claude/trigger-touches-refined-base`, README row 5) if that is still open;
otherwise right after it.

## T-3: Counter-trend C leg, "model C" (full order in Appendix A)
- A new, switchable entry model for the C wave of a correction against the Daily side (Daily DOWN ⇒ bull put on the 1H
  correction's C leg; mirror for UP). The sub-ways C-a … C-f are retest / pullback only.
- The default is OFF until the replay is shown; then Abhi switches it ON in PAPER.
- Golden check: in the latest BANKNIFTY replay group, the biggest up move against the Daily side is a clean zigzag:
  - A broke the 1H structure;
  - B held above A's start and ended inside a TESTED 1H demand area, on lower FUT volume;
  - C ended at a Weekly resistance.
  The replay must show model C entries there (C-a, C-b, C-e), and NO model C entry on the earlier up move whose start
  was later broken (C-4). Explain any difference from this reading.
- Note: the existing engine already took the bear call at A's end, and it caught the B leg. Model C complements it, it
  does not replace it.

## T-4: Carry-over items (status in README; continue them)
- **The trigger follow-up** (the trigger candle must touch the 15M refined base; sweep tests a–e): finish, merge, and
  deploy after close.
- **Reading-only validator / galleries** for the older BANKNIFTY batches (no FUT volume before the collector start):
  finish `claude/reading-only-reports`.
- **Older FUT volume.** Abhi refuses Upstox Plus. Use forward collection. A Fyers `fno_historical_data` probe is possible
  only with Abhi's Fyers account; log it in OPEN_QUESTIONS, don't block on it.
- **INTRADAY vs two-day holding** (the carry-forward setting / trading style) is Abhi's decision. Keep the current
  dashboard setting; list the choice in OPEN_QUESTIONS with the replay numbers for both, if available.

## T-6: PAPER trade messages show wrong SL / target (display only; part of the T-1 PR)
What Abhi saw on a 15M Dynamic SR PAPER entry:
- a spread card "SL ₹-208,488" (= 100% of credit);
- a naked card "net credit ₹-170,918 · SL ₹-170,918 · target ₹0 · R:R NA";
- the periodic lines "target ₹0 पर्यंत ₹-17,648".

Root cause (confirm):
- `srv2_momentum_reversal_strategy.py` opens both legs with a hard-coded `sl_pct_of_credit = 100` (naked also
  `target_pct_of_max_profit = 100`). That stores sl_pnl_level / target_pnl_level.
- The exits this bot actually uses are in `trading_engine.py`, the srv2 branch, from the `15m_dynamic_sr` dashboard
  settings:
  - **Spread:** SL = spot % OR premium points, whichever first; TSL activation by spot % / points, then locked at entry;
    trailing if enabled; target = `spread_target_pct_of_premium` of credit; next-S/R-level exit; the carry-forward check.
  - **Naked:** SL / TSL / target as spot % / premium points; EOD exit; never carried forward.
- `paper/watch.py` (the entry card and the "⏱ P&L … SL … target …" / "🎯 target जवळ" lines) and `paper/commands.py` print the
  stored ₹ levels with `or 0`.

Fix (display only, no exit-logic change):
- Never show the stored sl_pnl_level as "SL" for these bots.
- On the entry card and every periodic P&L line, show the REAL active exits from the dashboard settings. Give each in its
  own unit AND converted to ₹ for this position (lots × lot size):
  - SL (spot % / points, whichever first);
  - the TSL activation level and whether TSL is active (then "SL locked at entry");
  - the target (spread: % of credit in ₹; naked: spot % / points in ₹);
  - the next-level exit;
  - the carry-forward check / EOD exit.
- Naked legs: "premium paid ₹…" instead of "net credit ₹-…"; no "target ₹0", no "R:R NA".
- Tests:
  - the spread card;
  - the naked card;
  - the periodic lines with TSL off / on;
  - the values read from the settings, not hard-coded.

## T-5: Why did Vision DISAGREE? (report first, then align; part of the T-1 PR)
The case: the NIFTY "15M Dynamic SR" PAPER entry, signal_source = engine, model E4 (b) sweep-retest, bear call, level
L22,747. Vision said "disagree" and Abhi approved with ✅.

1. **Report this signal from the stored data**, verbatim, and in Marathi for Abhi.
   - From vision_signals / vision_events:
     - Vision's own verdict;
     - `code_verdict` and `rule_hits` (which disagree / gray rule ids fired);
     - the checklist items with status and evidence;
     - the `gap_ctx` and `l_line` context;
     - prompt_version / model;
     - the exact chart image Vision received.
   - Say clearly:
     - whether the "disagree" came from Vision's own reading or from a code rule floor;
     - which rule fired;
     - what the engine's reading was at that bar (trend, area id / band, broken object, refined base, trigger,
       invalidation).
2. **Check the root cause against CLAUDE.md** (likely, confirm it). For engine-sourced signals, Vision still audits with
   the OLD level-bot rulebook:
   - the single L line, PDH / PDL / PDC, ORH / ORL;
   - the gap classes G1–G5 / gap fill;
   - "opening", "event_day";
   - `role_conflict` from today's behaviour.
   The card is also the old Dynamic SR card (the L line "reclaimed / held R"), not the engine's area band, model and
   invalidation. Those rules frame the reading by day / session / clock, which the method forbids for chart reading. They
   can force "disagree" on a signal that is valid under the engine's concepts.
3. **Align (provisional default; record it in OPEN_QUESTIONS and in the Marathi report):** for signal_source = engine,
   Vision audits against the ENGINE's own reading, using the method's closed concept list:
   - **Card:** the engine's chart (area band, refined base, broken object for E4 (b), trigger candle, invalidation,
     next area, HTF strip) instead of the L-line card.
   - **Checklist:** the method's concepts only (trend side, area alive / lifecycle state, visit, trigger traded into
     the refined base, invalidation side, model rules, evidence).
   - **Old rules:** the session / gap / opening rules are shown as context lines only and never set the verdict floor.
   - **Unchanged:** Vision stays advisory (human_confirm: Abhi decides; reduce-only). The old level-bot signals
     (signal_source = own) keep their current rules unchanged.
4. **Measure.** For every closed engine trade, record Vision verdict vs Abhi's decision vs the outcome (next area first /
   invalidation first, P&L). Add a small table on the Vision page: "Vision agreed / disagreed / gray × result". This
   trade is the first row once it closes.
5. **Tests:**
   - an engine signal is audited with the engine card and checklist;
   - session / gap rules never floor the verdict for engine signals;
   - the old level-bot path is byte-identical;
   - the verdict-vs-outcome table.

## Order of PRs
1. The docs PR (STEP 0).
2. T-1 Vision UX + T-5 Vision disagree check + T-6 trade-message display: the reports first, then the fixes.
3. T-2 together with the T-4 trigger follow-up.
4. T-3 model C: the coverage report, the build behind its switch, the replay.
5. T-4 rest.

For each PR:
- self-review the diff;
- run the tests;
- give one consolidated VPS block for Abhi (after close, `--revert`, a status check at the end), saying whether a
  restart / migration is needed;
- write a Marathi summary for Abhi.

---

# Appendix A: TRADE_SESSION_C_WAVE_PLAN.md (verbatim)

Owner: Abhi. Record this order in the repo's owner-orders (INBOX verbatim + DECISIONS as a principle) before coding.
Rules unchanged: PAPER only; the engine only generates signals; execution (lots, strikes, hedge, exits) stays the
dashboard settings; no day / date / clock framing and no fixed numbers in reading rules (numbers live only in settings);
never merge areas (Z-1u); no breakout entries (H2).

## Why
Abhi's wave reading: the C wave of a correction is tradeable. The Daily trend can be DOWN while the minor (1H) trend is
in an up correction; its C leg may be traded in the minor direction. The replays showed big moves against the Daily side
that the engine correctly skipped under the current rules. This order adds them as a separate, switchable model.

## Research basis (web sources; context, not new rules)
- A zigzag is 5-3-5: A and C are impulsive, B is corrective (three waves).
- B never retraces all of A. If it goes beyond A's start, the count is wrong, and the larger trend is continuing.
- C usually goes beyond the end of A. Its length is often related to A (equal, or a ratio). These ratios estimate where
  C may END; they are not entry rules.
- Practitioners agree on two points. The entry is at the END of B, confirmed by structure on a lower timeframe, never
  during B on hope. Late entries inside C are the riskiest, because C is the last leg before the larger trend resumes.
- Honest caveat: an A–B can also be waves 1–2 of a new trend. The entry direction is the same; only the end zone
  differs.

## The model (mirror everything for a Daily UP trend)

**C-0 Switch.**
- A new entry model "C" (counter-trend C leg) with its own on/off on the dashboard, like E1–E4.
- Default OFF until the replay report (C-9) is shown. Abhi then switches it ON in PAPER.
- Its statistics are kept separately.

**C-1 Context.**
- Daily trend DOWN, read by the Daily reader exactly as now; nothing in the Daily reader changes.
- The Weekly state and the Daily DState (phase, counter, corr_label) are recorded as context.
- A Daily same-degree correction in leg "b" means the same idea at a higher degree: context only.

**C-2 Origin O.**
- O is the 1H swing low where the counter-move starts: the extreme of the Daily-side leg.

**C-3 Wave A.**
- An up leg from O that makes a 1H CHoCH up: a close beyond the last 1H lower high.
- Its nature is read by the existing leg reader (legs_compare), with the setting `c_a_nature`:
  - `impulse` (default; research: a zigzag A is a five, and the clean tradeable C follows it);
  - `any` (what-if).
- A ends at its confirmed swing high HA.

**C-4 Wave B.** B is the pullback from HA.
- It must read corrective (the leg reader).
- B dies if it closes beyond O AND forms a swing beyond O (structure, like the K4 death rule). Then the correction idea is
  dead and Daily-side trading continues as now.
- One candle beyond O without a swing does not kill it.

**C-5 Entry = the existing models, direction UP.**
- At a 1H demand area built during A (the existing area builder and the K4 lifecycle; fresh or tested only, never broken
  or dead), with the 15M refined base and the 5M trigger, E1–E4 fire unchanged:
  - `traded_inside`;
  - once per model per visit;
  - absorption without handover blocks E2 / E3 as now.
- The signal is labelled model C plus the firing sub-model (for example "C · E2").
- Pullback only: never an entry on a break of HA.

**C-6 Window.**
- Model C entries are allowed only while B is in progress, i.e. before any close beyond HA.
- After a close beyond HA, C is underway and no new model C entries are taken.
- Setting `c_window`: `b_only` (default) / `c_pullbacks` (what-if only, for C's own internal pullbacks).

**C-7 End zone (context on the signal and the chart; never a gate, never an exit).** It shows:
- the first Daily / Weekly supply area above HA;
- the Daily protected origin: if C closes beyond it and the Daily flips, the normal engine takes over;
- the C-vs-A projections from the setting `c_projections` (ratios live only in settings; drawn as a context band).

**C-8 Evidence (context only, no gate; Abhi B1).**
- RSI hidden divergence at the B low (the existing rsi_hidden module).
- RSI regular divergence at the C high: it supports the return of the Daily-side entries at the supply area where C
  ends. The existing E1–E4 handle that entry; nothing new.

**C-9 Execution and safety (unchanged).**
- The dashboard spread settings apply (a bull put while the Daily is DOWN).
- One open position bot-wide.
- The Vision human_confirm gate (✅ / ✏️ / ❌).
- No new lot, exit or R:R rule.

**C-10 Telegram text.**
- Example: "Counter C leg — Daily DOWN, 1H correction: A complete, B pullback into the 1H demand area lo–hi, model E2."
- It also gives the end-zone context and what invalidates it (B beyond O with a swing).

## C-11 More ways to trade the same correction (all pullback / retest; never a breakout entry, H2)
The code already has what these need:
- trendline.channel_lines / channels (both lines plus the parallel; break = close beyond + swing beyond, K6.5);
- E4 (a) sweep and E4 (b) broken-line retest;
- PATTERN_HOOK.
Each way below is a sub-model of model C with its own on/off and its own statistics. Default OFF until the replay shows
it.

| # | Name | Where | Entry (existing machinery) | Direction |
|---|---|---|---|---|
| C-a | B-end at an A demand area | end of B | E1–E4 at the 1H demand area (C-5) | minor (UP) |
| C-b | B channel break → retest | B usually forms a falling channel / flag | B's line of highs (or its channel parallel) BROKEN by K6.5, then the retest of that broken line with a rejection = E4 (b) | minor (UP) |
| C-c | Expanded flat: B sweeps O | B goes beyond O (a wick, or a close without a swing beyond) and comes back | E4 (a) sweep and failed push at O. C-4 is unchanged: only close + swing beyond O kills the idea | minor (UP) |
| C-d | B triangle edge → retest | B contracts into a triangle (the patterns track) | the broken triangle edge (PATTERN_HOOK) retested = E4 (b) | minor (UP) |
| C-e | HA flip retest | after HA is BROKEN by K6.5 (C underway), price returns to HA (former resistance as support) | E4 (b) on the flipped HA area / line; only the first return to HA (a second break of the flipped area ⇒ dead, concept C) | minor (UP) |
| C-f | End of C → back to the Daily side | C ends at the Daily / Weekly supply area (C-7), often as a rising channel or wedge (ending diagonal) | C's line of lows (or its channel parallel) BROKEN by K6.5, then the retest = E4 (b), plus E1–E4 at the supply area. Normal engine; the broken C channel is the handover evidence | Daily side (DOWN) |

Notes:
- C-e changes the window. With C-e ON, `c_window` = `b_and_ha_retest`: the B pullback plus the first retest of HA.
- C-f is not new code. It must work in the coverage report: the 1H channel of the C leg is drawn, its break is read as
  handover evidence, and its broken line is an E4 (b) level.
- Re-arm: after a complete A–B–C, a new 1H CHoCH up from a new low starts a new A. This covers a double correction:
  the X leg acts like a B.
- Evidence (context only, never a gate; Abhi's own reading):
  - B legs on lower FUT volume than A;
  - the C start on rising FUT volume;
  - RSI hidden divergence at the B low;
  - RSI regular divergence at the C end.
- Never: an entry on the breakout candle of a channel, a triangle or HA. Only the retest / pullback after the break.

The replay (order of work step 3) reports every sub-model separately: count, next-area-first vs invalidation-first, and
the worst adverse move.

## Order of work (one PR)
1. **Coverage report first.** What exists today:
   - DState corr_label / wave_a / counter;
   - the 1H swing state in mtf_state;
   - legs_compare;
   - rsi_hidden;
   - the area builder for A's bases.
   Then the exact gaps. Reuse; do not rewrite.
2. **Build behind the switch, with tests.**
   - No look-ahead.
   - A needs a CHoCH.
   - B beyond O plus a swing ⇒ dead.
   - One candle beyond O ⇒ alive.
   - No model C entry after a close beyond HA.
   - No entry on a break of HA.
   - The UP mirror.
   - The switch OFF ⇒ entries are byte-identical to today.
3. **Replay on the existing BANKNIFTY replay group.** For every model C entry, show next-area-first vs invalidation-first
   and the worst adverse move, plus the big moves against the Daily side (taken or not, and why). Use the same card format
   as the replay batches, with charts.
4. Abhi reviews, then switches it ON in PAPER. Deploy only after market close, in one VPS block with --revert.

---
## 22 Oct — merge all
Merge all

---
## 22 Oct — merge and continue
Merge and continue

---
## 22 Oct — merge and continue (2)
Merge and continue

---
## 22 Oct — VPS block
Vps block dya

---
## 22 Oct — after the deploy status (reply to the four open decisions)
Ok go ahead

---
## Chart Reading Report order
Abhi (message with the order):
Abhi — a separate new order attached: TRADE_SESSION_CHART_READING_REPORT.md (the daily Chart Reading Report on Telegram, replacing the bare Visual-audit level-count message). Record it in owner-orders first (INBOX verbatim, a README row, a DECISIONS principle). Do its "Report first" part, then build it in its own PR after the handover's T-1 / T-5 / T-6 Vision work. Send me one sample report for NIFTY and BANKNIFTY (charts + text) for approval before the deploy. Reports to me in Marathi.

The order (verbatim):

# Trade session — order: the daily Chart Reading Report on Telegram

From Abhi. English spec; reports to Abhi in Marathi. A separate order (not part of the handover pack).
First: re-read CLAUDE.md, REPORT_STANDARD.md and owner-orders; append this order VERBATIM to docs/owner-orders/INBOX.md; add a README row and a DECISIONS principle (no dates). One PR (`claude/chart-reading-report`); self-review; tests; PAPER unaffected; one VPS block for Abhi after market close with --revert (say if a restart is needed). Standing rules of CLAUDE.md apply.

### What Abhi saw
The daily Visual-audit message ("NIFTY 1D: 6 levels → 3 VALID, 3 SPURIOUS …, 2 missing भाग …, CONSENSUS: 2"):
- It shows only level counts. A trader cannot learn the market state from it, and it does not look professional.
- It also audits the OLD Opportunity Engine §2.6 levels, which no live bot trades (`consensus_mode = off`).
- Abhi reads the chart with many concepts and decides trades with all of them. The report must show the same reading.

### Report first
1. Which bots / paths read the Opportunity Engine levels or the consensus today. Confirm that decision3 does not.
2. Why `visual_audit_symbols` now includes BANKNIFTY. Abhi's setting was NIFTY only, for cost.

### The new report
- **One report per symbol** (the dashboard symbols list):
  - after the market close (the reading for the next session);
  - a short refresh before the open (what changed overnight / at the open).
- **Built from the decision3 READER's own facts.** Reuse what exists:
  - `mtf_state` (W / D / 1H / 15M state + story);
  - the areas with their K4 lifecycle;
  - liquidity / liquidity_pa;
  - trendline channel_lines / channels;
  - patterns_pa;
  - volume_read;
  - rsi / rsi_hidden;
  - daily wave_context (corr_label, wave);
  - confluence_pa;
  - entry_models state;
  - `bots_common/preopen_crux` + `decision3/preopen_chart` (the existing pre-open crux and charts are the starting point;
    extend them, do not rebuild).
- **No new reading rule, score or number.** Every value comes from the reader. Words come only from the closed concept
  list A–L of the Price Action Standard.

### Message 1: the charts
An album of 3 annotated PNGs, with chart text in English:
- **Weekly + Daily:** trend, protected level, the correction legs (a / b / c), the Daily / Weekly areas.
- **1H:**
  - the alive areas with their ids and states;
  - the broken / flipped ones dashed;
  - liquidity pools;
  - channel lines with touch counts;
  - pattern boundaries;
  - the last BOS / CHoCH.
- **15M:**
  - the refined bases;
  - the current visit;
  - the "entry only if" sequence at the nearest trade-side area;
  - the invalidation line;
  - the next area.
- Each chart has an FUT volume pane, and RSI with the divergences marked.

### Message 2: the reading
- Plain words, in Marathi by default (a dashboard language setting, MR / EN).
- Short lines; one section per concept; a section with nothing to say is omitted.
- It must fit one Telegram message (≤ 4096 characters). The "full" detail goes to a dashboard page linked at the end.
- Layout (the values below are a FORMAT EXAMPLE only, not a reading):

```
📘 NIFTY — chart reading (for the next session)
━━━━━━━━━━━━━━━━
🧭 Big picture
• Weekly: correction inside an up-trend
• Daily: DOWN · protected high 23,180 · correction leg b
• 1H: range 22,600–22,950 · 15M: counter-move

🏗 Structure (A, B)
• Last 1H event: CHoCH ↓ (close below 22,790); no BOS since
• Legs: the down-leg impulsive (larger bodies, rising FUT volume); the up-leg corrective (overlapping, lower volume)

🧱 Areas (C) — what the engine watches
• 🔴 1H supply 22,760–22,820 · FLIPPED (was support) · retested once
• 🟢 1H demand 22,560–22,610 · FRESH
• Daily supply 23,050–23,200 · TESTED
• Reading check: no wide / duplicate area

💧 Liquidity (D)
• Above: equal highs ≈ 22,950 (resting) · Below: swept 22,600 and closed back inside

📐 Lines · patterns (E, H) · confluence (F)
• 1H falling channel, lower line touched 3×
• Confluence: the supply 22,760–22,820 lies on the channel's upper line

📊 Volume (I) · RSI (J)
• The pullback came on lower FUT volume
• 1H: regular bullish divergence at 22,600 (evidence only)

🔀 Breakout / range (K, L)
• No accepted breakout · Range edges 22,600 / 22,950

🌊 Wave context
• Daily correction: A done, B in progress → a C leg is possible (model C: OFF)

🎯 What the engine waits for (a plan, not a signal)
• Bear-call side: visit 22,760–22,820 → handover → commitment with FUT volume → 5-min CHoCH ⇒ E1–E4
• Idea cancelled if: a close above 22,820 + a swing above (the area BROKEN)
• Bull-put side: only via model C (OFF)
• Execution = your dashboard settings

👁 Vision second opinion (info only)
• Areas: 4 of 5 agree · 1 shift suggested (22,760 → 22,790)
• A zone it sees that the engine does not: 22,860–22,890
• Trend / structure reading: agrees
• Full report → <dashboard link>
```

### Vision's part
The existing Dual-Eye audit is pointed at the decision3 reader's ALIVE areas per timeframe (bands as drawn, lifecycle
state, area id). It is information only, never a gate. Per area it gives:
- VALID / SPURIOUS / SHIFT;
- the missing zones;
- duplicates inside another area (a concept C / Z-1u reading check).
Rules:
- An area drawn outside the visible chart window is "not visible on this chart", never SPURIOUS.
- Vision also gives one line each for trend / structure agreement.
- Its disagreements go to OPEN_QUESTIONS as reading checks against a named concept. Never a rule from one chart.

### Rules
- No buy / sell / target / stop words in the reading. Areas as ranges.
- Execution stays the dashboard settings.
- No day / date / session framing in the READING. "For the next session" is only the operational send time.
- The Vision budget caps stay. The symbols, the language, the on / off switch and the short / full detail level are
  dashboard settings.
- The old bare level-count message: off by default (a setting); its data is kept on the dashboard page.
- Charts and private reading data go to the private trade-data repo only, never this public repo.

### Tests
- Every section maps to its reader fact (a fixture per concept).
- An empty concept is omitted.
- The message length ≤ 4096 characters with the overflow to the link.
- The "not visible" rule.
- The language setting.
- No look-ahead (the report at the close uses bars ≤ that close).
- Golden-format snapshot tests in English and Marathi.

### Show Abhi
Before the deploy, send ONE sample report for NIFTY and BANKNIFTY (charts + text) from the latest close, for his
approval of the look.

---
## 22 Oct — no questions, continue non-stop
ओके आता प्रश्न विचारू नका पुढील रिमिक्स काम करा नॉनस्टॉप

---
## 22 Oct — merge and continue (3)
Merge and continue

---
## 23 Oct — merge and continue (4)
Merge and continue

---
## 23 Oct — VPS block
Vps block

---
## 23 Oct — do remaining job
Do remaining job

---
## 23 Oct — Chart reading default ON
Chart reading tumhich on kra default

---
## 23 Oct — Chart reading Vision ON
Vision pn on kra

---
## 23 Oct — Vision budget
Per day 5 dollar budget

---
## 23 Oct — entry trigger on 5M for every model
Abhi — new owner rule: the entry trigger is on 5M for every model. Record it in owner-orders first (INBOX verbatim, a DECISIONS principle without dates, a README row). Report first, then build in one PR with tests and a replay before / after per model.
- Where stays as now: W state, D side, 1H / Daily areas with the K4 lifecycle, the refined 15M base (RC2), the visit, once per model per visit, max_hits_per_zone.
- When moves to 5M: the engine decides at every 5M close, using only CLOSED 15M / 1H / D bars as known at that 5M close (no look-ahead; a 15M bar in progress is never used).
  - E1 = the first 5M candle that trades into the refined base in the visit.
  - E2 = the 5M commitment candle with FUT 5M volume (the handover read on 5M; volume compared on 5M slots).
  - E3 = the 5M CHoCH (as now).
  - E4 (a) = the sweep and the failed push read on 5M.
  - E4 (b) = the 5M rejection candle at the retested object, from the correct side.
- traded_inside applies to the 5M trigger candle (it must trade into the refined base; a close outside on the trade side is allowed, never beyond the invalidation side).
- The invalidation stays structural (refined base / area / object / sweep extreme), never the 5M candle's own extreme.
- A dashboard setting trigger_tf = 5M (default, my rule) / 15M (what-if = today's behaviour, byte-identical).
- The live loop runs on 5M closes; the Telegram / Vision card shows the 5M trigger panel.
- The replay shows 15M vs 5M per model: entry time and price difference, distance to invalidation, next-area-first vs invalidation-first.
Self-review, PAPER only, one VPS block for me after market close with --revert. Report to me in Marathi.

---
## 23 Oct — reading check from a live PAPER entry (BANKNIFTY E4 (b) sweep-retest bear call)
Abhi — reading check from a live PAPER entry: BANKNIFTY, E4 (b) sweep-retest, a bear call at a broken horizontal line (I approved it; the entry was wrong by the method). Record it in owner-orders first (INBOX verbatim, DECISIONS principles without dates, a README row). Report first, then fix in one PR together with the handover's T-2, with tests and a replay before / after per model.
1. Approach side (E4 b): a bear-call retest of a line broken DOWN requires price to come back UP to it from below and be rejected there (a close back below). Here price came DOWN from above, where it had been accepted for a long time, and the trigger candle closed through the line: that is a breakdown candle (H2, no breakout entries), never an E4 (b). Mirror for bull puts.
2. Dead after a second break (the T-2 principle applies to LINES too): the line was broken down (a close + a swing below), then price closed back above it and formed swings above ⇒ the line is dead ⇒ no E4 (b) on it.
3. Range state (concept L): after that, price ranged between that line and an upper edge it rejected several times; the engine's own invalidation sat exactly at that upper edge, so the entry was at the wrong end of the range. Explain why no model fired at the upper edge (were the range edges built as areas? was the range state read?) and fix it per the method: range edges are the areas — bear call at the upper edge, bull put at the lower edge; E1–E4 apply there.
4. Evidence: the entry had "required set ✗" (no handover, no commitment, no LTF CHoCH) and grade None. Report how E4 (b) is allowed to fire with none of them and whether that matches the method's E4 (b) definition (the rejection form at the retested object).
5. Card text: a line object is described as a line ("broken 1H line at X, retest from below"), never as "supply area X–X (0 pts)". Fix the Telegram card and the Vision prompt.
6. Report which timeframe / degree the line came from (1H or 15M) and show it on the card. The card header shows the signal's own symbol first; the bot name ("NIFTY 15M Dynamic SR") only as a small label.
7. List every live and replayed entry matching 1 or 2, with its result.
Self-review, PAPER only, one VPS block for me after market close with --revert. Report to me in Marathi.
