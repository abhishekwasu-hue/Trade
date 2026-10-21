# CLAUDE.md — Abhi's standing rules (read at the start of every task and after every compaction)

First line of every report to Abhi: `Rules re-read: CLAUDE.md, REPORT_STANDARD.md`.

## Trading / reading
- Abhi is a price-action trader, not an intraday trader; trades run about two days. Read the chart as one continuous unit by
  structure. No day / date / session / clock-time framing in reading logic or in result measurement; only operational settings
  (entry hours, schedules) may be time-based.
- No fixed numbers in reading rules: comparison / logic only. Numbers live only in dashboard settings
  (`decision3/settings.py` REGISTER, classified in `tests/test_method_no_numbers.py`).
- The method lives in `docs/knowledge/CHART_READER_METHOD.md` + the Price Action Standard (`docs/knowledge/pa_standard/`).
  Its concept list is CLOSED. A misread is a bug against a named concept, logged in OPEN_QUESTIONS; never a rule from one chart.
  Golden cases are examples, not targets; never tune to pass one day; never edit golden expectations.
- Entry framework: trend side + proven area, then four independent models E1–E4, each at most once per visit. Evidence is listed
  and never blocks. The old v2.2 BOS / K gate (`legacy_k_gate`) is a logged diagnostic and never decides.
- The engine only generates signals. Lots, legs, strikes, SL, target, max trades: the existing dashboard settings. Never add new
  execution settings.
- Never add a trading rule (R:R filter, gate, threshold) that Abhi didn't state.
- FUT (near-month) volume for indices; spot for structure / areas / RSI. RSI divergence is the only indicator.
- The NIFTY holdout stays sealed (Daily bars only as level history, Z-1t). Never read it for results.

## Safety
- PAPER only. LIVE is untouched without Abhi's explicit words. Exits are never blocked.
- AI / Vision never place, block or change orders. Vision mode = `human_confirm` (no ✅ ⇒ the card expires, no entry).
- Never run anything on the VPS. Abhi runs ONE consolidated block (with `--revert`, after market close where possible).
- No secrets in git / logs / chat (never print a token). Private data and charts only in the private trade-data repo
  (`git add --ignore-removal`, never delete there), never in this public repo.
- Trade is never shut down or archived without Abhi's explicit words. No history rewrite on main. Never rotate thresholds.
- No paid API calls without approval.

## Work style
- Specs and code in English; reports to Abhi in plain Marathi.
- Work in parallel agents; never sit idle; log questions with a provisional default (OPEN_QUESTIONS) and continue.
- No frequent "still running / waiting" check-ins: they cost credits. Message Abhi only when something real is ready.
- Self-review every diff before pushing; an independent review before merge; merge only on green CI.
- Keep everything already built; extend, never rewrite approved layers (STABLE register, `docs/reader/STABLE.md`).
- Every reading / replay report follows `docs/reader/REPORT_STANDARD.md` and is validated by `reader_report/standard.py`.
