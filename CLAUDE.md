# CLAUDE.md — Abhi's standing rules (core). Full detail: docs/WORKING_RULES.md (grep the section you need)

## §1 Read at start / after compaction (≤ 15 KB, DECISIONS 70)
- This file + docs/HANDOVER_NOW.md + the current order's row in docs/owner-orders/README.md (short index of docs/owner-orders/).
- INBOX.md / DECISIONS.md are append-only and never read whole: grep by ID or date. OPEN_QUESTIONS holds only open items.
- Every new instruction from Abhi: append VERBATIM to docs/owner-orders/INBOX.md FIRST; status row in README; owner decisions
  appended to DECISIONS.md (no dates). Check provisional choices against DECISIONS (grep) and list them in the report.
- First line of every report: `Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders`. Reports to Abhi in plain Marathi.

## §2 Reading / method (detail: WORKING_RULES "Trading / reading")
- Price-action trader, trades ~2 days; read the chart by structure, no day / clock framing in reading logic or result measurement.
- No fixed numbers in reading rules (numbers only in decision3/settings.py REGISTER, tests/test_method_no_numbers.py).
- Method = docs/knowledge/CHART_READER_METHOD.md + pa_standard; concept list CLOSED; a misread is a bug against a named concept.
  Golden cases are examples: never tune to one day, never edit golden expectations (a golden change ⇒ stop and ask Abhi).
- Entry models E1–E4, each once per visit; evidence listed, never blocks; never add a trading rule Abhi didn't state.
- No look-ahead. Lifecycle = BREAK-1 (DECISIONS 60/69). STABLE layers: bug fixes only, new tag (docs/reader/STABLE.md).
- FUT near-month volume for indices; spot for structure / areas / RSI. NIFTY holdout sealed.

## §3 Safety
- PAPER only; LIVE untouched without Abhi's explicit words. Exits are never blocked. AI / Vision never place, block or change orders;
  Vision mode = human_confirm (no ✅ ⇒ the card expires, no entry).
- Never run anything on the VPS. Abhi runs ONE block (with --revert, after the close where possible).
- No secrets in git / logs / chat. Private data and charts only in the private trade-data repo (`git add --ignore-removal`, never
  delete there; never write into existing replay folders). No paid API calls without approval. No history rewrite on main.

## §4 Proof
- Every reading fix is proven with before / after charts (≤ 20 named charts per fix) and is "done" only after Abhi's ✅ on them
  (DECISIONS 46/57). Galleries go to Abhi as small ZIPs (and key charts as images). No deploy before ✅.

## §5 Work style
- Specs / code in English. Self-review every diff; independent review before merge; merge only on green CI.
- Keep everything built; extend, never rewrite approved layers. Reports follow docs/reader/REPORT_STANDARD.md.

## §6 Token budget (DECISIONS 70, binding)
- Code: grep + line ranges; never cat a whole large file; never re-read a file you just edited.
- Agents: at most 2 at a time; mechanical work (tests, charts, docs / status, copying) on .claude/agents/ sonnet helpers; main
  model for design, review, reader / trading logic and order paths. Each agent writes only to its own folder.
- Tests: locally only the tests touching the change; the full suite runs in CI. Long output to a file; show the failure summary only.
  Re-run a single failing test, never a whole suite for a flake.
- No polling: background runs + completion notice. View ≤ 10 images per PR yourself.
- Reports ≤ 25 lines, 3 parts: changed items by ID / ≤ 3 owner decisions with defaults / deploy line + migration yes-no.
  No narration, no test-count lists, no repeated background.
- At each milestone write docs/HANDOVER_NOW.md (≤ 1 KB: in flight, next step, open PRs) and continue from a fresh session.
