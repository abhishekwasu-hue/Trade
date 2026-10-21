# PA standard §2C — area base types and departure strength (track T2)

Module: `decision3/area_types.py` (shared frames: `decision3/pa_frames.py`). Evidence only. It reads `levels.Levels` and its
`snapshot`; it never changes them and never decides an entry.

## C.1 Base types — RBD / DBR (reversal), RBR / DBD (continuation)

**Definition (method words).** Every area is built from its own base candle(s) (Abhi Z-1u / TA4). The base type says how price came
INTO that base and how it LEFT it:

- **The base** = the area's own candle(s) on its own timeframe — birth (a) the swing candle, (b) the BOS-origin base 1H candle, (d) the
  two equal swings, Daily / Weekly bands their Daily / Weekly swing candle — extended to every adjoining bar that still trades inside
  the band.
- **Leg in** = where the bar just before the base lies: wholly above the band ⇒ price **dropped** into it (D); wholly below ⇒ it
  **rallied** into it (R).
- **Leg out** = where the first bar after the base lies: wholly above ⇒ **rally** out (R); wholly below ⇒ **drop** out (D).
- RBD (rally-base-drop) and DBR (drop-base-rally) are **reversal** bases; RBR (rally-base-rally) and DBD (drop-base-drop) are
  **continuation** bases.
- **Role reversal (KB K4, FLIPPED areas)** — also `flip_base`: the leg in is the break leg (broken by a rally ⇒ R), the base is the
  latest retest after the flip, the leg out is how price left that retest. Old supply broken up, retested, rallied away ⇒ RBR.

**States.** `type` = RBD / DBR / RBR / DBD; `family` = reversal / continuation; `type_partial` = e.g. "RB?" while price is still inside
the base (no leg out yet) or when the data has no bar before the base; `consistent_with_role` = a supply left downward / a demand left
upward.

**Not.** Not a filter: a continuation base is not "worse" and a reversal base is not "better" here. Not a new area: the areas are
the engine's own (`levels.Levels`). Swing-born areas are, by construction, mostly reversal bases (a swing is an extreme); continuation
bases appear where price paused inside a leg and then went on.

## C.5 Departure strength — how strongly price left the base, and whether that move broke structure

**Definition.** The departure leg runs from the base to the first finest-degree swing beyond it (still running ⇒ to the running
extreme, `complete` = False), stopping where price came back into the band. It is compared with its **neighbouring legs**, measure by
measure, by comparison only:

| measure | stronger side |
|---|---|
| pace = the leg's own high − low per bar | larger |
| mean body | larger |
| body overlap = share of bars whose body overlaps the previous body | smaller (one-sided) |
| FUT volume per bar (when every bar has it) | larger |

- `vs_approach` — against the approach leg (the leg in, from the last finest swing beyond the band on that side). `strength` =
  "strong" when the departure wins more measures than it loses, "weak" when it loses more than it wins, "even" otherwise;
  `unanimous` = one leg won every measure present. A missing measure (e.g. no FUT volume) is absent, never guessed.
- `vs_next` — the same against the next leg (from the departure's end to the next opposite swing), reported beside it.
- **Broke structure** (`bos`) = a close beyond the last confirmed structure swing (D2 on 15M; the Daily / Weekly swing on a Daily /
  Weekly band) that already existed before the departure, before price came back into the base. `internal_bos` = the same with the
  finest swings (D1).
- `fvg` = the imbalances (§2F.2) the departure left.

**Evidence wording** (one line per area), e.g.:
`demand · base DBR (reversal: drop-base-rally) · left strongly (stronger than the approach) · broke structure (close beyond swing
22,651.10) · left 5 imbalance(s)`; a flipped area: `demand (born as supply, flipped) · base RBD … · after the flip: RBR (continuation)`.

**Not.** No score, no threshold, no gate: "strong" never arms or blocks a model (E1–E4 stay the decision, track T0). No fixed numbers —
every measure is a comparison between neighbouring legs. When track T1's `legs_compare` lands, T9 may swap the measure set; the
output keys stay.

## API

- `read_area_types(V, t, d=None)` → one dict per area alive at t: `id, tf, role, role0, lo, hi, state, births, trade_location,
  trade_side, base{…}, departure{…}, flip_base{…}|None, evidence`. `d` (±1) only marks `trade_side`.
- `read_base(F, lo, hi, s0, s1)` → `(base, departure)` on any `pa_frames.Frame` (used for synthetic tests and for other timeframes).
- `draw_objects(V, t, items=None)` → `[{kind: "area_base", tf, t0, t1, p0, p1, label, state, evidence}]` (T8 schema).

No look-ahead: bars ≤ t, swings confirmed by t (tests rebuild on truncated data and compare). No settings added.
