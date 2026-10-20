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

## Where each layer stands (not stable until the ✅ above)

| Layer | Spec (CHART_READER_METHOD.md) | State |
|---|---|---|
| 1 | Swings / structure | Abhi picked A in all 12 cases. His rule, implemented exactly as stated, matches A in 4 of 12; the 8 differing cases (charts + reasons) are with him (trade-data `review/method_layer1_rule/`). Not stable; no code change until he decides. |
| 2 | Areas + lifecycle | Merged (#332) and reported with charts. Summary for ✅ sent (trade-data `review/layers_2_4_summary/`). Waiting for Abhi's ✅. |
| 3 | Visit, zone study, commitment, LTF | Merged (#331, #333, #334, #335, #338). Commitment volume = above the AVERAGE of the approach leg + the visit's opposite side (Abhi L3-c); real 12 Oct 09:30 = bear call (grade B), 13 Oct no call. Summary for ✅ sent. Waiting for Abhi's ✅. |
| 4 | Lines + confluence | Merged (#336, #339): logic lines, candle touch, break = close + swing beyond, confluence = the line through the area or a reaction out of it turning at the line ("confluence: line"; golden 12 Oct reads so). Two counting questions to Abhi (OPEN_QUESTIONS L4-g). Summary for ✅ sent. Waiting for Abhi's ✅. |
| 5 | RSI | Not started. |
| 6 | Output (charts, dossier, display finder) | Not started. |

The level bots are **not** rebuilt here (Abhi): they are rebuilt in ATP on the ported reader, and stay off in one-bot mode meanwhile.
