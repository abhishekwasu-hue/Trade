# owner-orders DECISIONS

Abhi's explicit decisions, one line each, newest last. Only what Abhi decided in his own words (not provisional choices, not agent
defaults). Append a new line for every new decision; never edit or remove an earlier line — a later line that changes one says so.
Details and the code / tests behind each one: `CLAUDE.md`, `docs/knowledge/CHART_READER_METHOD.md`, `docs/reports/v22/OPEN_QUESTIONS.md`.

1. Read the chart as one continuous unit by structure, as a price-action trader whose trades run about two days; no day / date / session / clock-time framing in reading or in result measurement (only operational settings may be time-based).
2. No fixed numbers in reading rules — comparison / logic only; numbers live only in the dashboard settings.
3. The method is `CHART_READER_METHOD.md` + the Price Action Standard; its concept list is closed; a misread is a bug against a named concept, never a rule from one chart; golden cases are examples, never targets, and their expectations are never edited.
4. The engine only generates signals; lots, legs, strikes, SL, target and max trades stay the existing dashboard settings; no new execution settings.
5. Never add a trading rule (R:R filter, gate, threshold) Abhi did not state.
6. FUT (near-month) volume for indices; spot for structure, areas and RSI; RSI divergence is the only indicator.
7. The NIFTY holdout stays sealed (Daily bars only as level history); never read it for results.
8. PAPER only; LIVE is untouched without Abhi's explicit words; exits are never blocked.
9. AI / Vision never place, block or change orders.
10. Nothing runs on the VPS; Abhi runs one consolidated block (with `--revert`, after market close where possible).
11. No secrets in git, logs or chat; private data and charts only in the private trade-data repo, never in the public repo.
12. Trade is never shut down or archived without Abhi's explicit words; no history rewrite on main; never rotate thresholds; no paid API calls without approval.
13. Specs and code in English; reports to Abhi in plain Marathi; no "still running / waiting" check-ins — message only when something real is ready.
14. Keep everything already built; extend, never rewrite approved layers.
15. Every reading / replay report follows `docs/reader/REPORT_STANDARD.md` and is validated by `reader_report/standard.py`.
16. E1–E4 go live in PAPER (entry gate = the four entry models); the old ③ (BOS impulse + K pullback) stays a logged diagnostic only and never decides.
17. No 6a required set for model entries — the models are independent and per-model PAPER stats decide later; E2 / E3 never fire while the zone study reads absorption without a handover (E1 / E4 not forced to "no entry").
18. Vision mode = human_confirm: Vision audits and shows its verdict, never skips a card, never enters without ✅; no reply ⇒ the card expires, no entry.
19. The range comes from structure (not the equal-highs / equal-lows reading).
20. `daily_leg_read` = compare (impulse / correction by comparison with neighbouring legs; Elliott ratios leave the reading, `elliott` stays a what-if).
21. Overlapping areas are never one area (Z-1u): the cluster only counts one signal per model per place; edges, trigger and invalidation come from the actual visited area; no union band in any entry, payload or card.
22. Refined base (RC2, research default, review after the replay): the 1H / Daily area is the context; the refined 15M base inside it gives the trigger location, the E1 entry and the invalidation; no refined base yet ⇒ the models wait.
23. A BOS-origin area is the base the impulse left (never the breakout candle); every area band is wick to body, no wick ⇒ the body.
24. E4 (b): a broken line / area is being revisited only while price is actually back at it; the revisit ends when price leaves it by structure.
25. A replay group is tested only when every spot session in it has near-month FUT volume; otherwise one line "not testable — FUT volume missing" with the days — no charts, never spot volume, never filled gaps.
26. Charts are clean (P8): evidence lines, the current channel, the next lines in the path and respected higher-degree lines; the rest behind "Show all lines"; cap = the display setting `chart_max_lines`; display only — the reader still reads every line.
27. Trigger reading `traded_inside`: the trigger candle must have traded inside the visited area and price must not be beyond the invalidation side; a close outside the area on the trade-direction side is the confirmation and is allowed (`inside` and `legacy` are what-ifs only).
28. `max_hits_per_zone` = 4 on the dashboard (up to four model entries per visit); it stays a dashboard setting.
29. E1 / E2 / E3 / E4 a: the trigger candle ITSELF must trade into the 15M refined base (its range overlaps the base band), not only the wider context area — the refined base exists so entry and invalidation come from the narrow base; close on the trade side outside the area stays allowed, never a close beyond the invalidation side, E1 keeps base_broken; with `entry_area_refine = area` the visited area plays the base's role; E4 b keeps "at the retested object".
