# REPORT_STANDARD — what every reading / replay report must contain

Purpose: Abhi verifies the reading by eye. A report that does not meet this standard is not sent.
Enforced by `reader_report/standard.py` (`validate_chart`, `validate_outcome_rule`, `validate_report`); tests in
`tests/test_report_standard.py`.

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

The card text: model (E1–E4), area + state + side, the evidence ✓ / ✗ list, the invalidation level + rule, the outcome, MFE / MAE.

## 4. Outcomes by structure, across sessions
Next opposite area reached first vs a close beyond the invalidation first, followed forward across sessions (also beyond the
batch end, using later data). If the data ends first: "open at data end". No "trigger day", session-end or clock-time horizon.

## 5. Tables
- The per-model table: entries, next area first, invalidation first, open / neither, re-entries.
- A running total across batches.
- The data gaps per day (listed, never filled).

## 6. Missed and worst, with charts
- The big moves with no entry before them, and the missing evidence for each.
- The worst losing entries, and what happened inside the area.

## 7. Misreads
Each possible misread is tied to a named concept of the standard (§1 MTF, §2 A–L, §3 models) and logged in OPEN_QUESTIONS as a
bug — never as a one-chart rule.
