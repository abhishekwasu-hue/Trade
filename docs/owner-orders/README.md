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
| 17 | T-1 Vision approval UX: never erase a card, notify every outcome, plain words, shadow trades visible, reachability check + report of NIFTY BEARISH L22,761 | report needs VPS data (read-only block for Abhi); fixes next PR | — |
| 18 | T-2 flipped area broken again ⇒ DEAD + one E4b per place | done in #367 (code + tests + 07–21 Oct before / after); with the CAS truncation fix, merging with the trigger follow-up | branch claude/hopeful-gates-hf186c |
| 19 | T-3 model C (counter-trend C leg), Appendix A | open: coverage report → build behind switch (OFF) → replay | — |
| 20 | T-4 carry-over: trigger follow-up (merge + deploy after close); reading-only validator (claude/reading-only-reports); older FUT volume (forward only); INTRADAY vs two-day (Abhi) | trigger follow-up merging with T-2; rest open | — |
| 21 | T-5 why did Vision disagree (E4b sweep-retest L22,747): report from stored data, then engine-signal audit on the engine reading | report needs VPS data; align in the T-1 PR | — |
| 22 | T-6 PAPER trade messages: real active exits from settings (own unit + ₹), naked premium paid | done + tests (display only, exit logic unchanged): entry card (spread + naked), periodic "⏱ P&L" line with TSL state, near alerts on premium-points ₹ thresholds, /positions; tests/test_paper_exit_display.py; needs the PAPER watcher + Telegram bot restarted | paper/watch.py, paper/commands.py |
