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
