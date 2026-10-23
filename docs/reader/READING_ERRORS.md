# Reading errors log (DECISIONS 49)

One row per reading error found in live PAPER or a gallery review. A row is closed only when the fix PR is merged AND its before /
after charts are in the private trade-data repo AND Abhi gave ✅ on them (DECISIONS 46). Charts never go into this repo.

| # | Found (gallery / live) | Concept (closed list) | Case (symbol, bar) | What was misread | Fix PR | Chart proof (trade-data path) | Abhi ✅ |
|---|---|---|---|---|---|---|---|
| 1 | CRR sample 19 Oct | §1 market state vs concept L range | BANKNIFTY 1H / 15M, 19 Oct close | "correction" while the structural range was in force | #379 | review/fix_proof_gallery (to add) | — |
| 2 | Fix proof gallery §2 | K6.5 broken back (lines) | 10 E4 (b) entries | retest of a line already broken back | #373 | review/fix_proof_gallery/sec2 | — |
| 3 | Fix proof gallery §2 / §3 | K4 reclaim on the break-confirming bar | BANKNIFTY 14 May, areas 265 / 256 | reclaim missed | #373 | review/fix_proof_gallery/sec3 | — |
| 4 | Live 22 Oct + gallery §1 / §2 | E4 (b) approach side (DECISIONS 38) | 7 E4 (b) entries incl. 07 / 09 / 12 Oct | revisit from the original side read as a retest | #377 | review/fix_proof_gallery/sec1, sec2 | — |
| 5 | Fix proof gallery §2 | flip once (DECISIONS 27 / 39) | 9 E4 (b) entries | flipped area broken again still armed | #368 | review/fix_proof_gallery/sec2 | — |
| 6 | Layer 5 gallery §4 | RSI divergence, L5-a "the move into the zone" | BANKNIFTY 11 Sep 10:30 E4 (b), broken Daily area 274 | 5M path read the RSI of an E4 (b) broken-area entry as "move not known" (NA) although the away swing existed | branch `l5` (C-L5-1, not merged) | review/layer5_gallery (L5-X01 before / after) | — |
