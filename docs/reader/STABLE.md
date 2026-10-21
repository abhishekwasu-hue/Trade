# Chart Reader — STABLE register

Owner decision (Abhi): Trade will be archived only on Abhi's own word; ATP ports every **stable** reader layer with parity tests. This file is the register.

## Rules

- **When a layer becomes stable:** a reader layer is marked stable only after it is merged, reported to Abhi in plain words with charts,
  and **Abhi answers ✅**. Then:
  - tag the commit `reader-layer<N>-stable-v1`;
  - add a row below (layer, tag, date, what it covers, its tests, the KB + Method Pack version);
  - export the parity fixtures to the private trade-data repo under `parity/layer<N>/<tag>/`, never into this public repo
    (`python3 scripts/reader_parity_export.py --layer N=<tag> … --trade-data ../trade-data`, from the clean tagged commit; it refuses
    to overwrite an existing tag's fixtures):
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
| 1 | `reader-layer1-stable-v1` | 2026-10-21 | Swings / structure: the approved swings2 D1 / D2 are the swing definition (Abhi's calibration, L1-a); the Daily structure by C-13 logic (L1-b); Daily pivot size N = 2 provisional (L1-c). Tag: the merge commit of PR "Reader layers 1–4 stable v1" — the tag is created on it right after the PR merges. | `test_swings2`, `test_decision3_daily_swings`, `test_decision3_daily_q15`, `test_decision3_daily_review`, `test_engine3_1m` (swing scale), `test_method_no_numbers` (layer 1), golden `test_decision3_flip` | KB (`docs/knowledge/KNOWLEDGE_BASE.md`) + Method Pack `4e65a0880257` (`build_method_pack.py --check`), both copied into the fixtures' `kb/` | trade-data `parity/layer1/reader-layer1-stable-v1/` |
| 2 | `reader-layer2-stable-v1` | 2026-10-21 | Areas + lifecycle: one base (wick to body), area kinds, break / sweep / flip / dead by structure, liquidity equal by comparison, every valid area ahead armed. Tag: the merge commit of PR "Reader layers 1–4 stable v1" — the tag is created on it right after the PR merges. | `test_decision3`, `test_decision3_flip`, `test_decision3_level_death_side`, `test_decision3_q22_q34`, `test_decision3_zone_answers`, `test_method_no_numbers` (layer 2) | KB (`docs/knowledge/KNOWLEDGE_BASE.md`) + Method Pack `4e65a0880257` (`build_method_pack.py --check`), both copied into the fixtures' `kb/` | trade-data `parity/layer2/reader-layer2-stable-v1/` |
| 3 | `reader-layer3-stable-v1` | 2026-10-21 | Visit, zone study (fast / slow handover, absorption), commitment form + volume (L3-c), LTF CHoCH, raw FUT volume / data problem. Tag: the merge commit of PR "Reader layers 1–4 stable v1" — the tag is created on it right after the PR merges. | `test_decision3_method`, `test_decision3_zone_answers`, `test_decision3_entry_first_bar`, `test_decision3_oct12`, `test_volume_pane`, `test_method_no_numbers` (layer 3), golden `test_decision3_flip` | KB (`docs/knowledge/KNOWLEDGE_BASE.md`) + Method Pack `4e65a0880257` (`build_method_pack.py --check`), both copied into the fixtures' `kb/` | trade-data `parity/layer3/reader-layer3-stable-v1/` |
| 4 | `reader-layer4-stable-v1` | 2026-10-21 | Lines + confluence: a line from two separate reactions, touches counted by reactions (L4-g: `touch_groups`; the touch is the reaction's own turn), correction-line trigger, "confluence: line" label. Tag: the merge commit of PR "Reader layers 1–4 stable v1" — the tag is created on it right after the PR merges. | `test_decision3_trendline`, `test_decision3_method`, `test_decision3_oct12`, `test_method_no_numbers` (layer 4), golden `test_decision3_flip` (12 Oct 09:15 line) | KB (`docs/knowledge/KNOWLEDGE_BASE.md`) + Method Pack `4e65a0880257` (`build_method_pack.py --check`), both copied into the fixtures' `kb/` | trade-data `parity/layer4/reader-layer4-stable-v1/` |

## Where each layer stands (stable = a row in the register above: ✅ + tag + parity fixtures)

| Layer | Spec (CHART_READER_METHOD.md) | State |
|---|---|---|
| 1 | Swings / structure | **Stable v1** (Abhi ✅; L1-a, L1-b merged in #345). L1-c: `daily_pivot_n` N = 2 is Abhi's PROVISIONAL value (recorded; guard class calibration / provisional; he may change it later from the dashboard — the setting comes from the live-switches track). |
| 2 | Areas + lifecycle | **Stable v1** (Abhi ✅, #332). |
| 3 | Visit, zone study, commitment, LTF | **Stable v1** (Abhi ✅, #331, #333, #334, #335, #338). |
| 4 | Lines + confluence | **Stable v1** (Abhi ✅, #336, #339; his L4-g answers merged in #343). |
| 5 | RSI | Merged (#341); Abhi's L5-a final answer merged (#344). **Not stable** until Abhi answers ✅. |
| 6 | Output (charts, dossier, display finder) | 6a (the verdict: required set ⇒ enter; A / B by confirming evidence; no scores) merged (#342) — **not stable** until Abhi answers ✅. 6b (output: charts, dossier, display finder) not merged — in progress on another track. |

The level bots are **not** rebuilt here (Abhi): they are rebuilt in ATP on the ported reader, and stay off in one-bot mode meanwhile.
