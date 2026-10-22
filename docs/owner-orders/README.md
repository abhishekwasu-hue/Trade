# Owner orders — status

Every order from Abhi and its status. New orders: append to INBOX.md verbatim FIRST, then add a row here, then act.
Decisions taken from orders go to DECISIONS.md (append only).

| # | Order (short) | Status | Where |
|---|---|---|---|
| 1 | Price Action Standard: coverage audit, PA tracks T1–T8, entry models E1–E4 | done (T3 channels per TF, T9 evidence wiring open) | #362 |
| 2 | Standing rules in CLAUDE.md + REPORT_STANDARD enforced by tests | done | #363 |
| 3 | Root-cause fixes RC1–RC6 + concept-C base fixes | done, deployed to PAPER 22 Oct (#365 block, status ✅ clean, reviewed) | #364 |
| 4 | Trigger reading "traded inside, close on the trade side allowed" | merged; deploy after close | #365 |
| 5 | Trigger candle must touch the 15M refined base; sweep tests a–e | done in #367 (merge on green CI) | branch claude/trigger-touches-refined-base |
| 6 | max_hits_per_zone = 4 | in the deploy blocks (#364 / #365) | scripts/pa_standard_settings.py |
| 7 | BANKNIFTY replay in 15-day groups per REPORT_STANDARD (only groups with FUT volume) | 07–21 Oct done; older groups not testable (no FUT before 30 Sep) | trade-data review/replay_banknifty_6m |
| 8 | Memory protocol (CLAUDE.md + owner-orders) | merged (#366) | docs/owner-orders |
| 9 | Older BANKNIFTY FUT volume | not available: VPS collector starts 30 Sep; Upstox expired-instruments = paid (Plus), needs Abhi's approval | — |
| 10 | BANKNIFTY 6-month reading galleries (no FUT before 30 Sep) | done, 12 batches on bf98040 (trade-data review/replay_banknifty_6m/reading/bf98040) | reading-only validator: branch claude/reading-only-reports |
| 11 | Flipped area broken again ⇒ DEAD (no E4b on it) + one E4b per place (duplicate E4b) | code + tests + 07–21 Oct before / after done; Abhi: merge now + VPS block (overrides the after-close timing for this deploy); merge on green CI + independent review | branch claude/trigger-touches-refined-base |
| 12 | Stop: report (docs/reports/owner/STATUS_REPORT.md), commit, merge, no new jobs | done; #367 merges on green CI; VPS block in the report |
| 13 | Remaining-work md file (handoff) + stop (credit limit) | handoff given to Abhi; new session resumed on "ok go ahead" | HANDOFF.md (upload) |
| 14 | Handoff step 1: #367 CI fail (Daily swing confirmed only from a completed day) | done: full suite green (5981 passed) on 7e9e8b7; flip-dead / E4b independent review APPROVE; #367 not merged yet | branch claude/hopeful-gates-hf186c (on #367 head) |
| 15 | T-1: naked-leg PAPER card — premium paid + dashboard exit rules in words, no ₹0 target / R:R NA (display only) | done + tests (tests/test_paper_naked_card.py); "T-1" not found in the repo — provisional: this item itself | paper/watch.py, branch claude/hopeful-gates-hf186c |
| 16 | Handover pack (new account): T-1 … T-6 + Appendix A recorded (INBOX verbatim, DECISIONS 29–33) | done (STEP 0) | docs/owner-orders |
| 17 | T-1 Vision approval UX: never erase a card, notify every outcome, plain words, shadow trades visible, reachability check + report of NIFTY BEARISH L22,761 | fixes + tests done (append_outcome, reply per outcome, shadow section, buttons-unavailable text, health line); report: read-only `scripts/vision_trail_report.py` for Abhi to run after close | vision/*, page_performance.py, page_vision_human_eye.py |
| 18 | T-2 flipped area broken again ⇒ DEAD + one E4b per place | merged (#368, 506b5c6) with the trigger follow-up, the CAS truncation fix and the naked card; deploy after close (VPS block) | main |
| 19 | T-3 model C (counter-trend C leg), Appendix A | step 1 coverage report done (gaps + open questions Q1–Q11 with defaults); step 2 built behind the switch (default OFF, rows byte-identical when OFF — pinned) + tests (tests/test_model_c.py, tests/test_model_c_live.py); P4 vs DECISIONS 32 logged (provisional: DECISIONS 32 wins for model C only); next: step 3 replay on the 07–21 Oct BANKNIFTY group (needs the private trade-data repo) | docs/reports/model_c/COVERAGE.md, decision3/model_c.py, docs/reports/v22/OPEN_QUESTIONS.md |
| 20 | T-4 carry-over: trigger follow-up (merge + deploy after close); reading-only validator (claude/reading-only-reports); older FUT volume (forward only); INTRADAY vs two-day (Abhi) | trigger follow-up merged (#368); rest open | — |
| 21 | T-5 why did Vision disagree (E4b sweep-retest L22,747): report from stored data, then engine-signal audit on the engine reading | root cause confirmed in code; align built (provisional, `vision_engine_audit = engine`) + verdict × result table + tests; report needs VPS data | vision/engine_audit.py, engine_card.py, engine_measure.py |
| 22 | T-6 PAPER trade messages: real active exits from settings (own unit + ₹), naked premium paid | done + tests (display only, exit logic unchanged): entry card (spread + naked), periodic "⏱ P&L" line with TSL state, near alerts on premium-points ₹ thresholds, /positions; tests/test_paper_exit_display.py; needs the PAPER watcher + Telegram bot restarted | paper/watch.py, paper/commands.py |
| 23 | "Merge all" | #368 merged (506b5c6), #367 closed as superseded; T-1 / T-5 / T-6 PR next, merged on green CI + independent review | — |
| 24 | "Merge and continue" | #369 merged (489d526): T-1 / T-5 / T-6; VPS block for #368 + #369 given (after close, --revert); T-4 reading-only validator merged into the next PR; T-3 model C build in progress (switch OFF) | — |
| 25 | T-3 model C step 2 + T-4 reading-only validator | merged (#370, 0d7813e; model C switch OFF; independent review APPROVE after 8 fixes); step 3 replay on trade-data in progress | main |
| 26 | "Merge and continue" (2) | nothing open to merge (#368–#370 merged); continuing: band labels mirror the DEAD rule (display), model C replay on trade-data | branch claude/hopeful-gates-hf186c |
