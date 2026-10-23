# DECISIONS — Abhi's owner decisions (append only; newest last)

Items marked PROVISIONAL are research / lead defaults Abhi has not objected to; Abhi may override them (10, 18).

Check every provisional choice against this list first (CLAUDE.md, memory protocol). Each line: the decision, its source.

1. Abhi is a price-action trader (≈ two-day trades). Reading is by structure, never by day / session / clock. (standing rule)
2. No fixed numbers in reading rules; numbers only in dashboard settings. (standing rule)
3. The method = CHART_READER_METHOD.md + the Price Action Standard; the concept list is CLOSED; a misread is a bug against a named
   concept; golden cases are examples, never targets. (PA standard, 21 Oct)
4. PAPER only; LIVE untouched without Abhi's words; exits never blocked; AI / Vision never place, block or change orders. (standing)
5. The old v2.2 BOS / K gate never decides; it is a logged diagnostic. (PA standard §3, 21 Oct)
6. Entry models E1–E4 are live in PAPER, independent, all four ON, each at most once per visit; NO 6a required set for model
   entries; per-model PAPER statistics decide later which stay. (21 Oct decisions, item 1–2)
7. The engine only generates signals; execution = the existing dashboard settings; no new execution settings. (21 Oct correction)
8. Vision mode = human_confirm: Vision audits and shows its verdict; never skips a card; never enters without Abhi's ✅; no reply ⇒
   the card expires, no entry. (21 Oct decisions, item 3)
9. Never merge areas / bases / timeframes (Z-1u). Overlapping same-role areas count as one place ONLY as a counter (one signal per
   model per place); edges, trigger and invalidation come from the actual area price is visiting, never the union. (21 Oct RC1)
10. PROVISIONAL — Zone refinement (research default, review after replay): the 1H / Daily area is the context; the 15M refined base inside it (TA4,
    wick to body) gives the trigger, the E1 entry and the invalidation; no refined base ⇒ the models wait. (21 Oct RC2)
11. A model never fires when price has already gone beyond the invalidation side (gap / large candle through = the area breaking,
    lifecycle). (21 Oct RC3)
12. An E4b broken line is being revisited only while price is back at it; the revisit ends by structure. (21 Oct RC4)
13. A replay group without near-month FUT volume is "not testable — FUT volume missing"; never spot volume, never fill gaps. (RC5)
14. Clean charts (P8), display only: evidence lines, the current channel, the next lines in the path, respected higher-degree lines;
    the rest behind "Show all lines"; cap = display setting (default 6); refined base / target / invalidation strong, context faint.
    (21 Oct RC6)
15. BOS-origin area = the base the impulse left (never the breakout candle); no wick ⇒ the body (Z-1x). (concept C fixes, 21 Oct)
16. Range = from structure (between two edges, price fails to make a new extreme on both sides), comparative; not C-13 equal. (21 Oct)
17. Daily leg reading = compare (Elliott ratios leave the reading). (21 Oct)
18. PROVISIONAL — Hidden RSI divergence = the classic reading (lead's default, not objected to). (21 Oct)
19. Reports follow docs/reader/REPORT_STANDARD.md: every entry charted with all layers; outcomes by structure across sessions;
    per-model table + running total; missed moves + worst losses with charts; Marathi summary on top. (21 Oct)
20. Deploy #364 to PAPER before the open (22 Oct): it halves the risk at the same quality. (22 Oct answers, item 1)
21. max_hits_per_zone = 4 (up to four model entries per visit); it stays a dashboard setting. (22 Oct answers, item 3)
22. Trigger reading: the trigger candle must trade INTO the 15M REFINED BASE itself (not only the wider area) for every model where
    the refined base applies; a close outside the area on the trade-direction side is allowed (the confirmation); a close beyond on
    the invalidation side is not. (22 Oct, decisions on #365)
23. Sweep / fakeout: a close beyond without a swing beyond, then back inside = a sweep (K4), the area stays alive, the visit continues;
    E4a is its model (invalidation beyond the sweep extreme); E2 / E3 may still fire later in the visit (candle touching the refined
    base; invalidation includes the sweep extreme); E1 does not come back after a sweep; close beyond + swing beyond = broken (flip),
    a later return from the other side ⇒ E4b; a single close beyond the refined base ends only E1. (22 Oct consolidated, item 2)
24. #365 deploys only AFTER the market close: merge on green CI + the independent review, then ONE VPS block with --revert. (22 Oct)
25. Memory protocol: CLAUDE.md + docs/owner-orders/ re-read at every start and after compaction; INBOX first; DECISIONS append only.
    (22 Oct consolidated, item 4)
26. Reading galleries are allowed for batches without FUT volume: price-based reading and E1 / E3 / E4 shown; every volume item marked
    "FUT volume missing"; never spot volume; labelled "without volume evidence"; superseded when FUT volume arrives. (22 Oct)
27. An area flips only once. A flipped area broken again (a close beyond it and a swing formed beyond it) is DEAD: no second flip;
    a dead area is never armed, and no E4 (b) retest may use it. (C lifecycle; code `flip_dead_rule = broken_again`)
28. One signal per model per place applies to E4 (b) too: overlapping BROKEN areas (and a BROKEN line lying on them) of the same role
    and break direction, revisited together, give ONE E4 (b) per visit; the signal keeps its own object, retest extreme and
    invalidation (counter only, never a union band — as decision 9).
29. A Vision approval card is never erased: every outcome (✅, ❌, ✏️, no reply, drift, expired, restart-cancel) keeps the original
    caption and appends one outcome line (the outcome line is never cut); buttons go only after a decision; every outcome is also a
    new short message replying to the card. The word "shadow" never appears without its plain explanation (comparison only, not
    counted). Shadow trades (`<bot>_vision_shadow`) are visible on the Vision and Performance pages, kept apart from the real PAPER
    totals and the kill switch. A card without buttons says so and why. (Handover T-1)
30. Trade messages show the exits the bot really uses, from the dashboard settings, each in its own unit and in ₹ for the position
    (SL, TSL activation / state, target, next-level exit, carry-forward check / EOD exit); a stored ₹ level the exit logic does not
    use is never shown as SL / target; a naked leg shows "premium paid", never "target ₹0" / "R:R NA". Display only; exit logic
    unchanged. (Handover T-6)
31. PROVISIONAL — For engine-sourced signals Vision audits against the engine's own reading (engine card and the method's closed
    concept list); the old level-bot session / gap / opening rules are context lines only and never set the verdict floor. Vision
    stays advisory (human_confirm). Level-bot signals (signal_source = own) keep their rules unchanged. Verdict vs Abhi's decision
    vs outcome is measured. (Handover T-5)
32. Model C (counter-trend C leg of a correction against the Daily side) is a separate, switchable entry model with its own
    statistics, default OFF until its replay is shown; Abhi switches it ON. Pullback / retest only (never a breakout entry): A
    needs a 1H CHoCH; B dies only by a close beyond O plus a swing beyond O; entries only while B is in progress (before a close
    beyond HA) unless a what-if window is chosen; end zone and evidence are context, never a gate or an exit; execution stays the
    dashboard settings. Sub-ways C-a … C-f each switchable. (Handover T-3, Appendix A)
33. Older FUT volume: no Upstox Plus (Abhi refuses); forward collection only; a Fyers probe only with Abhi's own account. INTRADAY
    vs two-day holding is Abhi's decision; the current dashboard setting stays. (Handover T-4)
34. PROVISIONAL defaults kept on Abhi's "go ahead" (each can still be changed by Abhi): model C reads A / B at the 1H degree
    (Appendix A C-3) and stays OFF; DECISIONS 32 wins over method P4 for model C only; approval mode keeps only a would-have note
    for rejected / no-reply signals (no shadow trade opened); the model C replay gallery goes to the private trade-data repo.
    (Handover follow-up)
35. The daily Chart Reading Report (Telegram, per dashboard symbol: after the close + a short refresh before the open) is built
    only from the decision3 reader's own facts, in the closed concept words A–L; no new reading rule, score or number; no buy /
    sell / target / stop words; areas as ranges; execution stays the dashboard settings. Vision's part is information only (per
    alive area VALID / SPURIOUS / SHIFT, missing zones, duplicates; an area outside the chart window is "not visible", never
    SPURIOUS); its disagreements are reading checks against a named concept in OPEN_QUESTIONS. The old bare level-count message is
    off by default. Abhi approves one sample (NIFTY + BANKNIFTY) before the deploy. (Chart Reading Report order)
36. The Chart Reading Report is ON by default (`chart_reading_report = on`), and so is its Vision part (`chart_reading_vision = on`);
    both can be switched off on the dashboard. Vision stays information only. The Vision budget is $5 per day (`vision_daily_budget_usd`
    = 5.0, a dashboard setting); PROVISIONAL with it: monthly cap 100 (the setting's maximum) and visual-audit sub-cap 2.0 (its maximum)
    so the daily budget is usable; the signals reserve stays. (Chart Reading Report switch-on + Abhi's budget)
37. The entry trigger is read on 5M for every model (`trigger_tf = 5M`; `15M` = the earlier behaviour, what-if, byte-identical). Where
    stays as now: W state, D side, 1H / Daily areas with the K4 lifecycle, the refined 15M base, the visit, once per model per visit,
    max_hits_per_zone. The engine decides at every 5M close using only 15M / 1H / D bars CLOSED at that 5M close (a 15M bar in
    progress is never used). E1 = the first 5M candle trading into the refined base in the visit; E2 = the 5M commitment candle with
    FUT 5M volume (handover on 5M, volume compared on 5M slots); E3 = the 5M CHoCH; E4 (a) = sweep and failed push read on 5M; E4 (b) =
    the 5M rejection candle at the retested object from the correct side. traded_inside applies to the 5M trigger candle. The
    invalidation stays structural (refined base / area / object / sweep extreme), never the 5M candle's own extreme. (Owner rule)
38. E4 (b) approach side: the retest of a line / area broken DOWN (bear call) needs price to come back UP to it from below and be
    rejected there (a close back below); a candle coming down from above, where price was accepted, and closing through the object is
    a breakdown candle (H2) — never an E4 (b). Mirror for bull puts. (Live reading check)
39. Lines flip once too (as DECISIONS 27): a line broken (close + swing beyond), then closed back through with swings formed on the
    original side, is dead — never an E4 (b) object again. (Live reading check)
40. Range (concept L): the range edges are the areas — bear call at the upper edge, bull put at the lower edge; E1–E4 apply there as at
    any area. (Live reading check)
41. Cards and the Vision prompt describe a line object as a line with its timeframe / degree ("broken 1H line at X, retest from
    below"), never as an area band; the card header shows the signal's own symbol first, the bot name only as a small label. (Live
    reading check)
42. The 5M entry trigger stays live in PAPER (DECISIONS 37). Every live 5M signal gets a 15M "would-have" shadow — never a trade,
    recorded only (entry time / price, invalidation, outcome next-area-first vs invalidation-first) — so 5M and 15M are measured on
    the same live bars; reported weekly per model. (Owner decision)
43. A 5M vs 15M result gap is diagnosed entry by entry (paired twins) as reading checks against named concepts — never answered with a
    new rule or a number. (Owner decision)
44. Old PRs superseded by the PA standard are closed, never merged for their own rules (SL is a dashboard setting); their branches are
    never deleted. (Owner decision)
45. STABLE layer 2 approved again: tag reader-layer2-stable-v2 on main; its parity fixtures re-exported to trade-data; the v1 fixtures
    stay as they are. (Owner decision)
46. Every reading fix is proven with before / after charts (Fix proof gallery in the private trade-data repo: 1H + 15M + 5M trigger
    panel, the object with its lifecycle events, approach-side arrow, trigger candle, invalidation, next area, a decision-bar line
    with the later bars faded "after the decision", one "Before / After / because" line) and is "done" only after Abhi's ✅ on the
    gallery — numbers alone never prove a fix. (Standing rule)
47. A gate / engine error never enters (fail-closed), and is never silent: each cause sends ONE plain-words ⚠️ Telegram alert per
    day; the cause is fixed with a test. (Owner decision)
48. Telegram message standard: only seven message types (🌅 prep, 🔔 approaching area, 🎯 decide now, 📈 trade update, 🌙 today +
    tomorrow's prep, 📊 weekly review, ⚠️ alert); the first line states the purpose and the action; short bullets in the fixed concept
    order, no internal codes, no repeats; only 🎯 and ⚠️ ring; one event = one message (updates reply to the trade's card, one pinned
    "Open positions" message edited in place); language MR / EN (default MR), chart text English; "nearness" for 🔔 is a display
    setting, never a reading rule; the old level-bot counts leave Telegram (dashboard only). A snapshot test per type keeps the format.
    (Owner decision)
49. READER-READY FOCUS: until the reader is declared ready, Trade work is only reader correctness — no new features (model C stays
    OFF; the Telegram message standard and other display work wait unless they fix a reading error; urgent error fixes continue).
    Ready = Abhi's ✅ on chart galleries for layer 5 (RSI) and layer 6 (verdict / output) + two consecutive weeks with no new reading
    error in live PAPER + per-model PAPER results shown with charts. Daily loop: after the close a "Today's reading gallery" (every
    entry and every armed-area visit without an entry, 1H + 15M + 5M charts, lifecycle, approach side, trigger, invalidation,
    decision bar with later bars faded, one Marathi reason line) in trade-data; Abhi's consolidated corrections are fixed by the next
    open with tests and before / after charts; a running reading-errors log (concept, case, fix PR, chart proof). (Owner decision)
50. Layer 6 output fixes approved (Abhi ✅ on the gallery): the card / Vision facts take the next area from the engine (O-1), print the
    A / B label (O-2, O-3), drop the old level-bot "grade" line and show the area's own TF (O-5), show a broken line as BROKEN (O-6).
    (Owner decision)
51. Every output reads exactly what the engine read at the decision: the facts dossier follows the 5M trigger (visit, required set,
    E4 (b) objects, the Daily frame for liquidity). (Owner decision)
52. The card caption stays short; the full details (5M trigger, evidence, invalidation) go as a reply under the card — nothing is cut by
    a length limit. The engine card draws the 5M trigger as its own panel beside the 15M panel, never over it. (Owner decision)
53. No "merged band — check" warning for engine areas (approval_band_warn_rule = method; wide areas stay in the comparison-based
    reading check). Missing FUT volume is said as "FUT volume missing — E2 cannot be read", never as a grade cap. (Owner decision)
54. Label: the required set is the fired model's own conditions (every fired entry has it); A = the model's conditions + at least one
    confirming evidence piece (RSI divergence, volume growing inside, confluence, correction line closed through, counter channel
    broken); B = the model's conditions only. The label never blocks. (Owner rule)
55. Label confirming pieces tightened: "counter channel broken" = only the pullback's (correction's) channel at the trend degree (1H);
    "confluence" = only a Daily / Weekly area overlapping the traded area, or an object of a different kind (a line, a liquidity pool)
    at the same place — nearness alone never counts. If A / B still does not separate, the card shows the evidence list + its count
    instead (information only, no threshold); Abhi decides after seeing the split. (Owner rule)
56. RSI divergence (L5-b): the push still forming at the decision bar counts as a push, marked "forming", read only from bars ≤ t, shown
    "confirmed" once its swing confirms. (L5-c): RSI divergence is read at the retest of a broken line / area like at any area — the
    retest is the pullback to the object. (Owner rule)
57. A fix is approved only after Abhi has checked its charts: galleries are sent as ZIPs for review. (Owner decision)
