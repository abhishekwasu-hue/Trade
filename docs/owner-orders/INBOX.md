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
