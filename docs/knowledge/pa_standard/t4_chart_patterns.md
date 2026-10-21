# T4 — Chart patterns from the swings + breakout vs fakeout (PA standard §2H, §2K)

Module: `decision3/patterns_pa.py`. Status: **evidence / state only**. A pattern never blocks or triggers an entry (KB K11.0:
patterns are context, area, evidence; never a breakout entry). E4(b) may later read `retest_levels` (hook only; wiring in T9).
Follows KB K11 and Abhi's decisions K11.0, K11.1, K11.7, K11.19 (KP1–KP5, OPEN_QUESTIONS "KB K11 chart patterns").

## Definitions (the method's words)

- **Swings** = the confirmed swings2 pivots of the timeframe's degree: 1H = the trend degree (`level_degree`, D2), 15M = one degree
  below (D1). Only swings confirmed by bar t (confirm_bar ≤ t). A run of two highs (or lows) keeps the more extreme one.
- **Equal** (C-13, `daily.c13_equal`): the later extreme reaches the earlier swing candle's own area (wick to body) and does not go
  beyond the earlier extreme. **Short of** = a lower high / higher low that does not reach that area. **Beyond** = past the extreme.
  No σ, no MR tolerance.
- **Broken** (method §3, K6.5): a close beyond the boundary **and** a swing formed beyond it (the finest structure degree, as the
  areas use), with no close back inside between them. A close that comes back first is a **fakeout** (failed breakout, K11.16); a
  wick beyond with the close inside is a **sweep** (K11.15).
- **Retest**: after the break, a candle's wick reaches the boundary from the broken side while its body stays on that side (as
  `trendline.touches`).
- **Failed after a break**: the mirror break back inside (a close back inside and a swing formed inside).

## Patterns

| Pattern | Swings show (comparison only) | Boundary |
|---|---|---|
| Double top / bottom (K11.8) | L0, H1, N, H2: H2 equal H1; N short of L0 (the rise came from clearly below the neckline) | neckline = horizontal at N; far side = the tops |
| Triple top / bottom (K11.9) | L0, H1, N1, H2, N2, H3: H2 and H3 equal H1; L0 clearly below the neckline | neckline = the lower trough |
| Head & shoulders / inverse (K11.10) | L0, LS, N1, HD, N2, RS: head beyond the left shoulder, right shoulder short of the head (Dow LH), each shoulder above the opposite trough, L0 clearly below N1 | neckline through N1 and N2; far side = the head |
| Symmetrical / ascending / descending triangle (K11.4, K11.5) | origin + A…D (candidate) or A…E: every leg smaller than the one before; highs falling + lows rising / highs equal + lows rising / highs falling + lows equal. Leg A must not break structure (a leg that does is the impulse into the triangle) | A–C and B–D lines (a flat side = horizontal) |
| Flag / pennant (K11.1, K11.2) | a pole leg that broke structure; then ≥ 2 highs and 2 lows, every leg smaller than the pole, never back to the pole's origin; flag = both sides against the pole or flat; pennant = converging | the envelope of each side |
| Rising / falling wedge (K11.7) | origin + W1…W4 (candidate, two touches a line) or W1…W5: both sides step the same way, each push smaller than the one before, lines converging. Default read = ENDING (KP3) | 1–3 and 2–4 lines |
| Rectangle / range (K11.3) | ≥ 2 highs all equal to the first high and ≥ 2 lows all equal to the first low | horizontal edges at those first swings, each with its C-13 area as the edge band (for §2L) |
| Broadening (K11.13) | every leg larger, highs rising + lows falling. Contrary evidence only (KP4) | envelope lines |

For each family the reader gives the most recent candidate and the most recent named instance. Relevance is by structure: a shape
must end in the current leg of the next higher degree or in the full swing before it (from that degree's 3rd-last confirmed swing on;
fewer such swings ⇒ the whole history). The shape itself may start earlier.

## States

| State | Meaning |
|---|---|
| forming | candidate: the shape is there, its confirmation is not (K11.0: listed, never evidence) |
| complete | named: reversal = a close beyond the neckline; triangle / broadening = 5 legs; wedge = 5th push + a close beyond the 2–4 line; flag / pennant = the flag's counter-pole end confirmed; rectangle = two reactions on each edge |
| broken | the boundary is broken (close beyond + swing beyond) = acceptance |
| retested | broken, then retested from the broken side |
| failed | reversal: neckline fakeout (name cancelled, K11.8) or acceptance beyond the tops / head before the neckline broke (continuation); any: broken then reclaimed; a biased continuation shape broken against its bias; a converging shape whose apex passed with no close beyond either line (expired) |

`named` is separate from `state`: a candidate whose line broke shows `state = broken` but stays unnamed (KP4: an incomplete wedge is
read through the KP1 trigger form by the entry models, not named here). Converging lines are boundaries only up to their apex.

Each boundary also carries its own §2K state: inside · sweep · beyond (closed beyond, not accepted yet) · accepted · retested ·
fakeout · failed, with the bars of each event.

## Roles (K11.0) — only when the trade side d is given

- reversal against the trade side (double top for a bull put) = **[E]** warning; on the trade side = **[A]** (handover evidence);
- flag / pennant / wedge / asc-desc triangle in the trade direction = **[P]** (pullback shape); against = **[E]**;
- symmetrical triangle = [P]; rectangle = [A] (its edges are the areas, §2L); broadening = [E] (contrary only).

## Evidence wording (named patterns only)

- `1H double top: broken boundary retested · neckline 24,850.00 — against the trade side [E]`
- `15M bull flag: complete · upper (sloped) — pullback shape [P]`
- `1H rectangle / range: complete · upper edge 25,120.00 — on the trade side [A]`

Candidates are listed separately (`candidates`), never as evidence.

## E4(b) hook

`retest_levels(V, t, d, tf)` = every pattern boundary accepted at t (only the decisive break, only while it is still a boundary):
`{src: "pattern", pattern, tf, boundary, p0, p1, slope, value_t, role (support after an up-break / resistance after a down-break),
break_dir, accepted_bar, swing_beyond, retests, state}`. `entry_models.py` is not touched.

## API

```python
from decision3 import patterns_pa as PP
r = PP.read_patterns(V, t, d=None, tf="1H")   # {tf, degree, patterns, evidence, candidates, retest_levels}
PP.retest_levels(V, t, d=None, tf="1H")
PP.draw_objects(V, t, d=None, tf="1H")         # [{kind: pattern | pattern_boundary, tf, t0, t1, p0, p1, label, state, evidence}]
PP.breakout_state(A, swings, line, side, start, t)   # §2K for any line (callable bar → price)
PP.level_breakout(A, swings, lo, hi, side, start, t)   # §2K for a band (area, range edge)
PP.find_patterns(A, swings, fine, t, tf, d, ts)       # the core on raw arrays
```

## Numbers

None in the reading and no new setting. The degrees come from the existing `level_degree` (1H = D2, 15M = one below). The KB's
research numbers (≤ 0.5 MR equal tops, ≥ 8 bars apart, flag depth 23.6–50%, 2–11 bars, apex 85%) are **not** used: "equal" is C-13,
sizes are compared with the neighbouring legs, the pole depth is reported as a fact (`depth_of_pole`) only.

## What it is NOT

- Not an entry, not a gate, not a score (KP5: no PT points for these patterns).
- Not a breakout signal: a close beyond a neckline / edge is context only (Abhi does not trade breakouts); the trade location after a
  break is the retest, read by E4(b).
- Not a channel reader (§2E belongs to the lines / channels track); a channel here is only the flag after a pole.
- Not an Elliott count: triangle / wedge legs are counted for the K11 naming rule only.

## Known gaps

- Rounding, V-reversal and island patterns (K11.11, K11.12, K11.14) are not read (not in §2H's list).
- A flat B near the impulse end is not separated from a double top (K11.8 "flat चा B"); the C-13 shape test only.
- The triangle "not as wave 2" rule (R5) is not checked; volume (K10.3) is not read here (T5 owns volume).
- Shapes are read from one degree; a shape that stops progressing without a break is kept until a newer one replaces it.
