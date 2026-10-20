# Chart Reader — STABLE register

Owner decision (Abhi): Trade will be archived only on Abhi's own word; ATP ports every **stable** reader layer with parity tests. This file is the register.

## Rules

- **When a layer becomes stable:** a reader layer is marked stable only after it is merged, reported to Abhi in plain words with charts,
  and **Abhi answers ✅**. Then:
  - tag the commit `reader-layer<N>-stable-v1`;
  - add a row below (layer, tag, date, what it covers, its tests, the KB + Method Pack version);
  - export the parity fixtures to the private trade-data repo under `parity/layer<N>/<tag>/`, never into this public repo:
    - the golden set;
    - a broad sample of real NIFTY / BANKNIFTY bars (trends, ranges, corrections);
    - the mirror cases;
    - with the layer's exact output and a manifest with checksums;
  - publish the matching KB + Method Pack text, so ATP copies the same version.
- **A stable layer is frozen:** bug fixes only. Every fix gets a new tag (`…-v2`, `…-v3`) and its own row, so that ATP re-ports it.
- **No ✅, no tag.** A report, a merge, or a green CI never makes a layer stable.
- **Owner rule:** porting a layer to ATP never removes or weakens it here. Trade keeps running exactly as now until Abhi himself says
  otherwise (see SUNSET.md). No automation, condition or session switches anything off.

## Register

| Layer | Tag | Date | Covers | Tests | KB / Method Pack version | Parity fixtures |
|---|---|---|---|---|---|---|
| — | — | — | (no stable layer yet) | — | — | — |

## Where each layer stands (stable = a row in the register above: ✅ + tag + parity fixtures)

| Layer | Spec (CHART_READER_METHOD.md) | State |
|---|---|---|
| 1 | Swings / structure | **Abhi ✅** (his approved swing charts are the acceptance): the approved swings2 D1 / D2 are the definition — his calibration setting (OPEN_QUESTIONS L1-a). Tag after the calibration PR merges. |
| 2 | Areas + lifecycle | **Abhi ✅** (#332). Tag + parity fixtures next. |
| 3 | Visit, zone study, commitment, LTF | **Abhi ✅** (#331, #333, #334, #335, #338). Tag + parity fixtures next. |
| 4 | Lines + confluence | **Abhi ✅** (#336, #339). His L4-g answers (touches by reactions; the touch is the reaction's own turn) are implemented in #343 and recorded in OPEN_QUESTIONS L4-g there; they land before the tag. |
| 5 | RSI | Merged (#341). Abhi's L5-a answer (the degree one below the zone's structure) is implemented in #344 (OPEN_QUESTIONS L5-a updated there), with one reading question back to him. Not stable. |
| 6 | Output (charts, dossier, display finder) | 6a (the verdict: required set ⇒ enter; A / B by confirming evidence; no scores) in review. Not stable. |

The level bots are **not** rebuilt here (Abhi): they are rebuilt in ATP on the ported reader, and stay off in one-bot mode meanwhile.
