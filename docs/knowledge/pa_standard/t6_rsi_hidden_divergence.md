# T6 — Hidden RSI divergence (continuation evidence)

Standard §2J (J.2). Owner module: `decision3/rsi_hidden.py`. RSI and the pairs: `rsi2.engine.Divergence`. Tests: `tests/test_pa_rsi_hidden.py`.

## Definition (method words)

- **Hidden bull** — in an **uptrend pullback**, price makes a **higher low** while RSI makes a **lower low**.
- **Hidden bear** (mirror) — in a **downtrend pullback**, price makes a **lower high** while RSI makes a **higher high**.

The pullback held its structure while momentum dipped further. The trend's side is still in control, so this is
**continuation** evidence. It mirrors the regular divergence (layer 5): the regular one says the move into the area is tiring
(reversal of that move), and the hidden one says the pullback held (continuation of the trend).

## Two labelled readings (both returned; `frame.kind` says which)

### 1. Classic — across the impulse (the reading; lead decision, provisional, logged in OPEN_QUESTIONS)

- The **current pullback's low** is compared with the **trend's previous higher low**, across the impulse. In a downtrend, the
  pullback's high is compared with the previous lower high.
- It is read at the **trend's structure degree** (`level_degree`, D2: the degree whose BOS makes the impulse in `V.pb`), on swings
  confirmed by t.
- The previous higher low is the impulse's **origin** swing. The pullback's low is the most extreme confirmed swing of that degree after
  the impulse end.
- The previous swing must be the extreme up to the pullback (rsi2's consecutive rule). If price went beyond that low before the pullback's
  low, it is not the trend's previous higher low, and nothing is read as hidden. The reason is stated.
- When no impulse is known, it uses the last two same-kind swings of that degree that have an opposite swing between them.
- `frame.kind = "classic_across_impulse"`, with `frame.impulse` (the impulse end). The compared pair is always reported (`pair`), so the
  absence is stated with its numbers.
- Evidence wording: `hidden bull divergence (classic, across the impulse, D2): the pullback's low 24,950.00 is a higher low than the
  trend's previous higher low 24,800.00 (impulse to 25,300.00) while RSI 41.20 → 38.70 (lower low) — continuation evidence for the
  uptrend`.

### 2. Inside the move — a second, labelled read (the regular divergence's own frame, Abhi L5-a)

- Pairs are read between the **consecutive pushes inside the move** into the area. The move begins at the last swing built away from the
  area (`move_from`, the decision's `commit.move_from_bar`).
- In an uptrend pullback the pushes are its **lows**. In a downtrend pullback they are its **highs**.
- The read uses the **highest swings2 degree at which that move shows at least two pushes** (confirmed swings, after `move_from`,
  known by t). A swing from before the move began is never compared.
- Frame order: an explicit `move_from` / a decision row (zone move, with its visit start `arm`: the second push must be inside the visit)
  / an area `lvl` (the same `V.visit` that ⑥ reads). With no area, the **K pullback** is used: from the impulse end (`V.pb`, `i_end_bar`).
- `frame.kind = "zone_move"` or `"pullback_K"`. Its wording starts `hidden bull divergence (inside the move, D0, confirmed): …`.

RSI at a swing = its extreme inside the swing's own span (rsi2's rule; no bar windows; never past the swing's confirm bar). Wilder RSI(14)
is the indicator's definition.

## States

| state | meaning |
|---|---|
| `forming` | inside the move only: the second push is the running extreme at t (not confirmed yet). The classic read uses confirmed swings only |
| `confirmed` | the second push is a confirmed swing (right-side bars or a commitment candle — rsi2) |
| `overtaken` | price later went beyond the second push (below the higher low / above the lower high): the pair no longer stands, and the newer pair is judged on its own |
| NA | the move is not known (no swing built away from the area / no impulse), or rsi2 failed. The reason is stated |
| none | classic: the compared pair is not hidden, or the pullback has no confirmed swing low / high of the trend's degree yet. Inside the move: fewer than two pushes at every degree, or no hidden pair at the read degree. Stated in words |

## Evidence wording

Each statement names its reading. Classic: see above. Inside the move: `hidden bull divergence (inside the move, D1, confirmed): price
higher low 24,950.00 → 25,010.00 while RSI 41.20 → 38.70 (lower low) — continuation evidence for the uptrend`. The absence is also
stated, for example `no hidden bull divergence (classic, D2): the pullback's low … vs the trend's previous higher low …: price higher
low, RSI 38.00 → 41.00` or `no hidden bull divergence between the pushes (lows) inside the move into the area at D0`.

## What it is NOT

- **Not a gate or a trigger.** It is not part of the conviction label (until Abhi says). Track T9 adds it to the evidence list.
- **Not the regular divergence.** That divergence and its reader (`V22.rsi_divergence`, `V22._rsi`, regular only) are unchanged. rsi2's
  `div_hidden` default stays **off**. This module builds its own rsi2 instance with hidden on (`V._rsi_hidden`). Turning hidden on does
  not change any regular record.
- **Not an equal low / high.** An equal low / high is a double bottom / top. rsi2 marks it hidden when RSI is lower; this module does not
  ("higher low" / "lower high" are strict).
- No second indicator, no time / date / session framing, no thresholds. The module adds no new setting.

## API

- `read_hidden_divergence(V, t, d=None, *, move_from=None, arm=None, lvl=None, row=None)`: per side, a plain dict `{concept, side,
  reading, found (= the classic read: True / False / None = NA), classic {frame, divergences, overtaken, pair, degree, statements},
  inside_move {frame, divergences, overtaken, degree, pushes, statements}, statements}`. When d is None and there is no row, the result
  is `{bull: …, bear: …}`.
- `draw_objects(V, t, d=None, read=None, …)`: for each pair of both readings, `rsi_hidden_div` (price pane, L1 → L2) and
  `rsi_hidden_div_rsi` (RSI pane), each shaped `{kind, tf, t0, t1, p0, p1, label, state, evidence}`. The label and the evidence name the
  reading.

## Open question for Abhi

The classic reading (across the impulse) is the lead's provisional decision. Should it stay the reading, with the inside-the-move read as
the second one? And which degree is "the trend's structure degree": D2 (the impulse's BOS degree, used now) or another?
