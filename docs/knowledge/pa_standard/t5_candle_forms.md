# T5 — Candle forms at a location (PA standard §2G)

Code: `decision3/candle_forms.py` · tests: `tests/test_pa_candle_forms.py` · check: `scripts/pa_candles_volume_check.py`

## Definition (the method's words)

A candle form is read **relative to its neighbouring candles** and counts **only at a location** — an area (1H zone), a level
(Daily band) or a line (the swing line of each side). A form away from every location is not evidence. Forms are read in **both
directions** (bullish = buyers won the form, bearish = sellers won) and at **any** location, not only as the commitment in the
trade direction.

Every form is the method's existing comparative reader in `decision3/method.py`, called read-only — no new rule, no ratio:

| Form | Reader (unchanged) | Reading |
|---|---|---|
| Rejection (long wick) | `_one_candle_form` → `pin` | the wick on one side is longer than the rest of the candle |
| Momentum | `_one_candle_form` → `strong_close` + `candle_read(..)["big_body"]` | the body is larger than both wicks together (closes near its extreme) **and** larger than the average body of the current leg's earlier candles |
| Engulfing | `_reversal_form_compare` → `engulf` | the body covers the previous opposite-colour body |
| Morning / evening star | `_reversal_form_compare` → `star` | a strong first candle, a small middle one, the third back beyond the first's close |
| Tweezer bottom / top | `_reversal_form_compare` → `tweezer` | reaches the earlier candle's extreme wick, not beyond it, and turns |
| Inside bar broken | `_reversal_form_compare` → `inside_break` | an inside / harami candle, then a close beyond it |
| Doji then confirmation | `_reversal_form_compare` → `doji_confirm` | a doji, then a close beyond it |
| Inside bar (state) | the commitment's "wait: inside" definition | high and low inside the previous candle's |
| Indecision / doji (state) | `is_doji` | the body smaller than each wick |

The comparative definitions are always used here (`candle_rule = compare`, `session_windows = False`), whatever the engine's
what-if switches say.

## States and evidence wording

Each form at a location gets a relation per location:

- **with** — a bullish form at support (demand, rising support line), or a bearish form at resistance (supply, falling resistance line);
- **against** — the opposite (e.g. *"bearish engulfing at a location — against: demand 22,718–22,776 (1H)"*);
- **neutral** — doji / inside bar: *"indecision (doji) at a location — indecision: Daily supply level …"*.

With a trade direction `d`, the line also says `(for the trade)` / `(against the trade)`.
Off-location forms are only counted (`off_location`), never evidence.

Timeframes: 15M (the engine's bars) and 1H (completed 1H candles from `levels.h1_frame`; the hour holding bar t is read only once it
has ended, so the short last hour of a session is read at the next bar).

## API

- `forms_on(A, j, s=None, ctx=None)` — every form ending at candle j, both directions, no location.
- `forms_at(A, j, locations, s=None, ctx=None, d=None, span=None)` — the raw-frame core: forms at the given locations.
- `read_candle_forms(V, t, d=None, tf="15M", locations_=None)` — on a V22 state (locations from `locations(V, t)`).
- `locations(V, t, weekly=False)` — areas / Daily levels from `Levels.snapshot(t)` + both `trendline.swing_line` lines.
- `draw_objects(read)` — `{kind: "candle_form", tf, t0, t1, p0, p1, label, state, evidence}` for the chart track.

No settings were added. No look-ahead: bars ≤ t; swings, lines and areas known at t (tested by truncation).

## What it is NOT

- Not a gate and not a trigger: evidence only (the entry models decide; wiring into the evidence list is T9).
- Not a new candle rule: it calls the method's readers; it does not change them or the commitment.
- Not a candle read away from a location.
- Weekly bands are left out by default (Abhi Z-1u: context only; one wide Weekly band would make every candle "at a location").
- When one bar fits two multi-candle forms in the same direction, the method's own order (engulf, star, inside break, doji
  confirm, tweezer) names it — the same order the commitment uses. One-candle forms (rejection, momentum) and the two states are
  read independently.
