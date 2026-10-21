# T6 — Hidden RSI divergence (continuation evidence)

Standard §2J (J.2). Owner module: `decision3/rsi_hidden.py`. RSI and the pairs: `rsi2.engine.Divergence`. Tests: `tests/test_pa_rsi_hidden.py`.

## Definition (method words)

- **Hidden bull** — in an **uptrend pullback**, price makes a **higher low** while RSI makes a **lower low**.
- **Hidden bear** (mirror) — in a **downtrend pullback**, price makes a **lower high** while RSI makes a **higher high**.

The pullback held its structure while momentum dipped further. The trend's side is still in control, so this is
**continuation** evidence. It mirrors the regular divergence (layer 5): the regular one says the move into the area is tiring
(reversal of that move), and the hidden one says the pullback held (continuation of the trend).

## Reading frame (the same as the regular divergence, Abhi L5-a)

- Pairs are read between the **consecutive pushes inside the move** into the area. The move begins at the last swing built away from the
  area (`move_from`, the decision's `commit.move_from_bar`).
- In an uptrend pullback the pushes are its **lows**. In a downtrend pullback they are its **highs**.
- The read uses the **highest swings2 degree at which that move shows at least two pushes** (confirmed swings, after `move_from`,
  known by t). A swing from before the move began is never compared.
- RSI at a swing = its extreme inside the swing's own span (rsi2's rule; no bar windows). Wilder RSI(14) is the indicator's definition.
- Frame order: an explicit `move_from` / a decision row (zone move, with its visit start `arm`: the second push must be inside the visit)
  / an area `lvl` (the same `V.visit` that ⑥ reads). With no area, the **K pullback** is used: from the impulse end (`V.pb`, `i_end_bar`).

## States

| state | meaning |
|---|---|
| `forming` | the second push is the running extreme at t (not confirmed yet) |
| `confirmed` | the second push is a confirmed swing (right-side bars or a commitment candle — rsi2) |
| `overtaken` | price later went beyond the second push (below the higher low / above the lower high): the pair no longer stands, and the newer pair is judged on its own |
| NA | the move is not known (no swing built away from the area / no impulse), or rsi2 failed. The reason is stated |
| none | fewer than two pushes at every degree, or no hidden pair at the read degree. Stated in words |

## Evidence wording

`hidden bull divergence (D1, confirmed): price higher low 24,950.00 → 25,010.00 while RSI 41.20 → 38.70 (lower low) — continuation
evidence for the uptrend`. The absence is also stated, for example `no hidden bull divergence between the pushes (lows) inside the move
into the area at D0`.

## What it is NOT

- **Not a gate or a trigger.** It is not part of the conviction label (until Abhi says). Track T9 adds it to the evidence list.
- **Not the regular divergence.** That divergence and its reader (`V22.rsi_divergence`, `V22._rsi`, regular only) are unchanged. rsi2's
  `div_hidden` default stays **off**. This module builds its own rsi2 instance with hidden on (`V._rsi_hidden`). Turning hidden on does
  not change any regular record.
- **Not an equal low / high.** An equal low / high is a double bottom / top. rsi2 marks it hidden when RSI is lower; this module does not
  ("higher low" / "lower high" are strict).
- **Not the classic trend-wide comparison** (this pullback's low against the trend's previous higher low before the impulse). The frame
  stays inside the move, as for the regular divergence. A pair across the impulse is not read (see open question).
- No second indicator, no time / date / session framing, no thresholds. The module adds no new setting.

## API

- `read_hidden_divergence(V, t, d=None, *, move_from=None, arm=None, lvl=None, row=None)`: a plain dict `{concept, side, found
  (True / False / None = NA), divergences [{degree, status, L1, L2, price_rel, rsi_diff, count, …}], overtaken, degree, pushes, frame,
  statements, role}`. When d is None and there is no row, the result is `{bull: …, bear: …}` (each side in its own K-pullback frame).
- `draw_objects(V, t, d=None, read=None, …)`: for each pair, `rsi_hidden_div` (price pane, L1 → L2) and `rsi_hidden_div_rsi` (RSI pane),
  each shaped `{kind, tf, t0, t1, p0, p1, label, state, evidence}`.

## Open question for Abhi

Should hidden divergence also be read in the classic way: the pullback's last low against the trend's previous higher low (across the
impulse)? Today it is read only inside the move, the same frame as the regular divergence.
