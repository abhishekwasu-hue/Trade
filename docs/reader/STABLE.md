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
| 1 | Swings / structure | Question pack sent to Abhi (trade-data `review/method_layer1/`): 12 cases, logic-only swings vs his approved swings. His per-case pick becomes the definition. |
| 2 | Areas + lifecycle | Merged (#332) and reported with charts. Waiting for Abhi's ✅. |
| 3 | Visit, zone study, commitment, LTF | Merged (#331, #333, #334). Abhi's L3-c correction merged (#335): the approach leg crosses gaps; on real volume there is no 12 Oct bear call. Waiting for ✅ after that re-run report. |
| 4 | Lines + confluence | PR #336 (logic lines, candle touch, break = close + swing beyond, confluence labels the area). |
| 5 | RSI | Not started. |
| 6 | Output (charts, dossier, display finder) | Not started. |

The level bots are **not** rebuilt here (Abhi): they are rebuilt in ATP on the ported reader, and stay off in one-bot mode meanwhile.
