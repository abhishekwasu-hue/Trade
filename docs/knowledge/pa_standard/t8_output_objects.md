# T8 — OUTPUT: one drawn-object list, the per-timeframe story (PA standard §4)

**What it is.** The reader's output is ONE list of drawn objects. The same list is drawn on the Telegram (Vision) approval chart and on
the verification charts (1H, 15M, setup chart), so what Abhi sees on Telegram is exactly what he checks on the review charts. Next to it,
a short story per timeframe (W / D / 1H / 15M / 5M): the market state of that timeframe and the objects read on it.

**What it is NOT.** Not a reading and not a decision. Nothing here makes, blocks or delays an entry; no object is a trade location by
itself. It only gathers what the readers (swings2, levels, trendline, liquidity, rsi2, daily and the PA tracks T1–T7) already found and
words / draws it. Display numbers only (how many sessions a default window shows, colours) — no threshold reads price.

## The object (decision3/draw_objects.py)

`{kind, tf, t0, t1, p0, p1, label, state, style_key, evidence}` + optional `degree`, `base_type`, `lines`, `points`, `id`, `src`.

- Geometry is in **time and price** (never a bar number of one chart) ⇒ the same object lands at the same place on a 15M, a 1H or a Vision
  chart whose bars are cut differently.
- `tf` = the timeframe the object was read on; `state` = the method's state word; `evidence` = the evidence wording that goes with it (T9
  puts these into the evidence list); `style_key` = how it is drawn.

| kind | what (t0, p0) – (t1, p1) mean | states |
|---|---|---|
| swing | the swing (a point), label HH / HL / LH / LL / EQH / EQL, `degree` (D1 internal, D2 the 1H-area structure) | confirmed |
| area | supply / demand: base (birth) → now, low – high; `base_type` RBD / DBR / RBR / DBD (area track); tf 1H / D / W | active, tested, broken, flipped, dead |
| line | first anchor → the line's value at the last bar; `points` = touches | respected, broken, retest |
| channel | the main line + `lines` = the parallel through the opposite extreme | inside, broken, retest |
| level | a horizontal higher-timeframe level (earlier swing extreme, Daily protected swing) | (owner's word) |
| fvg | the gap left by an impulse, low – high | open, partly filled, filled |
| fib | a retracement price — **only when it lands on an area / liquidity** (Abhi); `evidence` must name what it meets, else refused | confluent |
| pattern | `lines` = boundary / neckline, `points` = its swings | forming, broken, retest, failed |
| liquidity | equal highs / lows (horizontal) or a pool along a line (sloped) | resting, taken |
| sweep | t0 = the bar that went beyond, p0 = the pool, p1 = the extreme, t1 = the close back inside | swept, trapped |
| divergence | the two swings of the pair (regular / hidden, bull / bear) | confirmed, forming |
| entry | an entry-model mark E1–E4: p0 = the entry reference, p1 = the invalidation | (owner's word) |

## What `collect(V, t, extras)` gathers today (no look-ahead: bars ≤ t, confirmed swings only)

- swings at D1 and D2 with their HH / HL / LH / LL label (swings2);
- the decision's own areas with the K4 state, tests / sweeps and the confluence label (Levels.snapshot; the trade side labelled with the
  line confluence exactly as engine.step2) — the 1H chart's selection inside the view distance + the decision's next armed area;
- the trade-side line with its touches and the reaction's touch N (trendline.swing_line / reaction_touch);
- equal highs / lows (liquidity.pools, method rule) — resting or taken;
- sweeps / trapped (failed breakout) — liquidity.sweeps_and_traps, one sweep per poke (the outermost pool);
- regular RSI divergence pairs at D1 / D2 not overtaken by a later extreme (rsi2, the engine's own rule);
- the Daily protected swing as a level.
- `extras`: the plain-dict lists from T1–T7 in this shape (channels, patterns, FVG, Fib confluence, inducement, hidden divergence,
  E1–E4 marks …) — validated the same way; a bad one is dropped with its reason, one after bar t is dropped (no look-ahead).

## Drawing (decision3/draw_render.py)

One geometry (`geometry`: primitives in the target chart's bar index and price), two backends: matplotlib (decision3 charts) and plotly
(Vision). A far horizontal object becomes a ▲ / ▼ note at the panel edge instead of squashing the candles. A 1H chart shows the D2
swings only (`min_degree`).

## Setting

`chart_objects` (decision3/settings.py OUTPUT + vision/config.py) — **default `off` = today's charts byte for byte**; `on` = the object
list on the Telegram chart (`sig["objects"]` or the engine gate tags' `objects`, wired by T9) and on `charts.h1_png` / `m15_png` /
`setup_chart.render`. Display only.

## The story per timeframe (`tf_story`)

`W: up` · `D: down, impulse · supply … · Daily protected LH …` · `1H: <state> (D2 swings) · nearest areas above / below` ·
`15M: <state> (D1 swings) · line · latest sweep · latest divergence` · `5M: the LTF CHoCH line inside a visit`. The state word comes from
the swings of that degree (HH + HL = up, LH + LL = down, else range; the last swing against it = pullback / bounce in progress); the
multi-timeframe state track can pass its own words (`states=`) — no second reading. English (chart-safe); display only.

## Open points for Abhi / the coordinator

- The Telegram chart draws the list only when the signal carries it — the engine adapter (paper/engine_entry, T9) must put
  `collect(V, t, r=r)` into the gate tags; until then `on` changes nothing on Telegram.
- The engine arms every area ahead on the trade side; the drawn view keeps the ones inside the view distance + the next one.
- A 15M line drawn on a 1H chart is straight between its two anchors in the 1H bar index (the session's last short hour makes a tiny
  difference to the in-between touches).
