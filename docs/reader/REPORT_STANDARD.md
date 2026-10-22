# REPORT_STANDARD — what every reading / replay report must contain

Purpose: Abhi verifies the reading by eye. A report that does not meet this standard is not sent.
Enforced by `reader_report/standard.py` (`validate_chart`, `validate_outcome_rule`, `validate_report`); tests in
`tests/test_report_standard.py`.

## 0. Data check before any replay (RC5)
`group_data_status(spot_sessions, fut_sessions)`: a group is **testable** only if every spot session in it has near-month FUT volume.
Otherwise the group emits ONE line — `not testable — FUT volume missing` with the missing days — and nothing else: no charts, no
blocked-trigger cards, never spot volume as a substitute, never filled gaps. `validate_report` refuses a report whose `data_status` is
not testable.

## 1. First line
`Rules re-read: CLAUDE.md, REPORT_STANDARD.md`

## 2. Plain Marathi summary on top
Numbers and what the checks found. No opinions, no proposals unless asked.

## 3. Every entry charted (never samples)
Each entry (and each data-blocked trigger, in its own labelled section) has one chart with ALL of these layers. A layer with
nothing at that bar is still evaluated and says so ("no pattern", "no divergence pair"):

| layer key | what |
|---|---|
| `areas_1h_states` | the 1H areas with their states (fresh / tested / broken / flipped / dead) and roles |
| `lines` | the lines through the swings, both sides and both directions |
| `channels` | the channels (two lines + state) |
| `patterns` | chart patterns (named only after confirmation) |
| `liquidity_sweeps` | resting liquidity and sweeps |
| `fut_volume_pane` | near-month FUT volume pane |
| `rsi_pane` | RSI pane |
| `rsi_divergence_pair` | the divergence pair marked (regular / hidden), or "none" |
| `ltf_choch_inset` | the 5M CHoCH inset |
| `htf_state_strip` | the W / D / 1H state strip |
| `story` | the reader's two-line story |

The card text: model (E1–E4), area + state + side, the refined 15M base when the reader used one (RC2), the evidence ✓ / ✗ list,
the invalidation level + rule, the outcome, MFE / MAE.

### 3a. Clean charts (P8) — display only; the reader still reads every line
- SHOW, in this order: (a) evidence lines — the line in confluence with the entry area that price touched in this visit; for E4 (b) the
  broken line being retested; (b) the channel price is in now on the setup timeframe (both boundaries); (c) the next line in price's
  path above and below (met next between the entry and the target / the invalidation); (d) higher-degree lines price respects in the
  current move.
- HIDE behind "Show all lines" (HTML: a toggle revealing a second image with every line + the hidden list; PNG: "hidden: N"): dead
  lines (closed through, not being retested); lines outside the trade's path (beyond the next opposite area or beyond the
  invalidation); a lower-degree line nearly parallel and close to a higher-degree one (keep the higher degree; "close" = within one
  entry-area width over their common span — a comparison, no number); lines that ended before the current leg's start swing.
- Still crowded: the earlier category first, then the higher degree, then more touches. At most `chart_max_lines` lines (DISPLAY
  setting, default 6, `decision3/settings.py` OUTPUT + `vision/config.py`). The legend lists only the shown lines.
- AREAS: the refined base, the target area and the invalidation strong; the context area faint; other areas faded; dead areas hidden.
- Every chart's meta carries `lines_view` {max_lines, shown, evidence, legend, hidden}; `validate_chart` fails when the legend lists
  more than `chart_max_lines` lines, lists a line that is not shown, or an evidence line is not shown. The renderer
  (`decision3/draw_render.geometry(max_lines=…)`) asserts the same cap.

## 4. Outcomes by structure, across sessions
Next opposite area reached first vs a close beyond the invalidation first, followed forward across sessions (also beyond the
batch end, using later data). If the data ends first: "open at data end". No "trigger day", session-end or clock-time horizon.

## 5. Tables
- The per-model table: entries, next area first, invalidation first, open / neither, re-entries.
- A fix / rule change: a before / after table per model and per fixed case, on the same data and outcome rule.
- A running total across batches.
- The data gaps per day (listed, never filled).

## 6. Missed and worst, with charts
- The big moves with no entry before them, and the missing evidence for each.
- The worst losing entries, and what happened inside the area.

## 7. Misreads
Each possible misread is tied to a named concept of the standard (§1 MTF, §2 A–L, §3 models) and logged in OPEN_QUESTIONS as a
bug — never as a one-chart rule.
