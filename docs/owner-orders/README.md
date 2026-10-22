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
