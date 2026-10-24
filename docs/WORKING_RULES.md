# WORKING_RULES.md — the full standing rules (moved from CLAUDE.md on Abhi's token-budget order, DECISIONS 70)

CLAUDE.md keeps the short core; this file keeps every detail. Read the section you need (grep), not the whole file.

# CLAUDE.md — Abhi's standing rules (read at the start of every task and after every compaction)

## Memory protocol (Abhi)
- At the start of every task and after every compaction: re-read this file, `docs/owner-orders/` (README, INBOX, DECISIONS) and
  `docs/reader/REPORT_STANDARD.md` before acting.
- Every new instruction from Abhi is appended VERBATIM to `docs/owner-orders/INBOX.md` FIRST, before acting on it; its status goes
  into `docs/owner-orders/README.md`; each owner decision is appended to `docs/owner-orders/DECISIONS.md` (append only).
- Any provisional decision of yours is first checked against `docs/owner-orders/DECISIONS.md` (and this file and the method doc);
  list those checks in the report.
- First line of every report to Abhi: `Rules re-read: CLAUDE.md, REPORT_STANDARD.md, owner-orders`.
- Trade's private method stays in this repo; nothing of it goes into the public ATP repo.

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
- Trigger reading (Abhi 22 Oct, `entry_trigger_rule = traded_inside`; code: the follow-up PR after #365, not yet on main): the trigger candle must trade INTO the 15M REFINED BASE itself
  (not only the wider area) for every model where the refined base applies (E1, E2, E3, E4a; E4b: at the retested object). A close
  outside the area on the trade-direction side is allowed (that close is the confirmation); a close beyond on the invalidation side is
  not. The refined base exists so that entry and invalidation come from the narrow base. `inside` (#364) and `legacy` (da7cbbc) are
  what-ifs only.
- Sweep / fakeout (Abhi 22 Oct): a close beyond the area WITHOUT a swing formed beyond, then back inside = a sweep (K4): the area stays
  alive and the visit continues. E4a is its model (the next push fails inside the sweep extreme; invalidation beyond the sweep
  extreme). E2 / E3 may still fire later in the visit (candle touching the refined base; invalidation includes the sweep extreme).
  E1 does NOT come back after a sweep (first touch, once per visit). A close beyond + a swing beyond = broken (flip); a later return
  from the other side = the retest of the flipped area ⇒ E4b. A single close beyond the refined base ends only E1 and is not by
  itself a break of the area; E2 / E3 / E4 are judged against their own invalidation at their trigger (current state).
- `max_hits_per_zone` = 4 on the dashboard (Abhi 22 Oct: up to four model entries per visit). It stays a dashboard setting.
- The engine only generates signals. Lots, legs, strikes, SL, target, max trades: the existing dashboard settings. Never add new
  execution settings.
- Never add a trading rule (R:R filter, gate, threshold) that Abhi didn't state.
- A model fires only when its trigger candle traded inside the visited area (and touches the refined base, see Trigger reading) and
  price is not beyond its invalidation side NOW (no close beyond the far edge / the invalidation at the trigger; a sweep already back
  inside is not "beyond" — see Sweep / fakeout; E4 (b): the rejection form at the retested object, closing on its trade side). A gap or a
  large candle that closes through the invalidation side is the area being broken (lifecycle), not entered — never an entry; a candle
  that never traded inside the area never fires.
- Clusters only count one signal per model per place — edges, trigger and invalidation come from the actual area, never the union
  (Z-1u). No union band in any entry, payload or card; `max_hits_per_zone` counts the visited area. The same count applies to E4 (b):
  overlapping broken areas (and a broken line lying on them) of one role and break direction = one place, one E4 (b) per visit.
- An area flips only once: a flipped area broken again (close beyond + swing beyond) is DEAD — never armed, never an E4 (b) object
  (`flip_dead_rule = broken_again`; `far_swing` = the earlier reading, what-if only).
- Refined base (RC2, RESEARCH DEFAULT, review after the replay — `entry_area_refine = setup_tf`): the 1H / Daily area is the context;
  the refined 15M base inside it (TA4) gives the trigger (the trigger candle must trade into it, see Trigger reading), the E1 entry
  and the invalidation; no refined base yet ⇒ the models wait.
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
- Provisional decisions: see Memory protocol (checked against DECISIONS, this file and the method doc; listed in the report).
