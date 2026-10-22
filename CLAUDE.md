# CLAUDE.md — Abhi's standing rules (read at the start of every task and after every compaction)

First line of every report to Abhi: `Rules re-read: CLAUDE.md, REPORT_STANDARD.md`.
Abhi's explicit decisions, one line each, newest last: `docs/owner/DECISIONS.md` (append every new one there).

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
- Trigger reading (Abhi 22 Oct, `entry_trigger_rule = traded_inside`): the trigger candle must have traded INSIDE the (refined) area,
  and price must not be beyond the INVALIDATION side. E1 / E2 / E3 / E4 a: the trigger candle ITSELF trades into the 15M refined base
  (its range overlaps the base band), not only the wider context area (Abhi 22 Oct: the base gives entry and invalidation; a candle
  that never touches it brings back the wide invalidation); `entry_area_refine = area` ⇒ the visited area is the base; E4 b keeps
  "at the retested object". A close outside the area on the trade-direction side is the confirmation and is
  allowed (a commitment / rejection candle trades into the area and closes away from it). `inside` (the close inside, #364) and
  `legacy` (da7cbbc) are what-ifs only.
- `max_hits_per_zone` = 4 on the dashboard (Abhi 22 Oct: up to four model entries per visit). It stays a dashboard setting.
- The engine only generates signals. Lots, legs, strikes, SL, target, max trades: the existing dashboard settings. Never add new
  execution settings.
- Never add a trading rule (R:R filter, gate, threshold) that Abhi didn't state.
- A model fires only when its trigger candle traded inside the visited area (E1–E4 a: into its refined base) and price is not beyond
  its invalidation side (no close beyond the far edge / the invalidation; E4 (b): the rejection form at the retested object, closing
  on its trade side). A gap or a large candle that closes through the invalidation side is the area being broken (lifecycle), not
  entered — never an entry; a candle that never traded inside the area (or its refined base) never fires.
- Clusters only count one signal per model per place — edges, trigger and invalidation come from the actual area, never the union
  (Z-1u). No union band in any entry, payload or card; `max_hits_per_zone` counts the visited area.
- Refined base (RC2, RESEARCH DEFAULT, review after the replay — `entry_area_refine = setup_tf`): the 1H / Daily area is the context;
  the refined 15M base inside it (TA4) gives the trigger location (the trigger candle trades into it), the E1 entry and the
  invalidation; no refined base yet ⇒ the models wait.
- A BOS-origin area is the base the impulse left (never the breakout candle); every area band is wick to body, no wick ⇒ the body.
- E4 (b): a broken line / area is being revisited only while price is actually back at it; the revisit ends when price leaves it by
  structure (a new swing that does not reach it).
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
- A replay group is tested only when every spot session in it has near-month FUT volume (`group_data_status`); otherwise it emits one
  line "not testable — FUT volume missing" with the days — no charts, no blocked-trigger cards, never spot volume, never filled gaps.
- Charts are clean (P8): evidence lines + the current channel + the next lines in the path + respected higher-degree lines; everything
  else behind "Show all lines"; cap = the display setting `chart_max_lines`; the legend lists only shown lines. Display only — the
  reader still reads ALL lines. Areas: refined base, target and invalidation strong; context area faint; the rest faded; dead hidden.
- Every provisional decision is first checked against CLAUDE.md and CHART_READER_METHOD.md, and the check is listed in the hand-back.
