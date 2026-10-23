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
| 6 | Layer 6 gallery (L6-O1) | C areas — target = next opposite area (output) | BANKNIFTY, 53 / 53 entries 13 Apr – 21 Oct | engine card / Vision facts next area from the chart band finder, not the engine's areas | l6 50f3a9d (local, awaiting ✅) | review/layer6_gallery | — |
| 7 | Layer 6 gallery (L6-O2, O3) | L6-a label rule (output) | 53 / 53 (Vision facts), 1 / 1 labelled (classic card) | Vision facts "label" = the model name; classic card without the A / B label | l6 50f3a9d (local, awaiting ✅) | review/layer6_gallery | — |
| 8 | Layer 6 gallery (L6-O5; O4 logged) | §1 MTF area TF; L6-a (card detail lines) | 53 / 53 cards | "grade None" level-bot line; details Area line with the setup TF (the 5M trigger text line is cut by 1024 — logged, no change) | l6 50f3a9d (local, awaiting ✅) | review/layer6_gallery | — |
| 9 | Layer 6 gallery (L6-O6) | K6.5 broken line state (DECISIONS 41) | 7 E4 (b) on lines | card / Vision facts "state n/a" for a BROKEN line | l6 50f3a9d (local, awaiting ✅) | review/layer6_gallery | — |
| 10 | Layer 6 gallery (L6-O7, O8) | L3-n visit / L3-c3 required set in the dossier vs the 5M trigger (DECISIONS 37) | 10 E1 (no visit seen), 1 E2 (required set) | the facts dossier reads 15M at the last closed bar; the engine reads the visit / required set on 5M | branch dossier5m (local, awaiting ✅): the dossier takes the engine's 5M decision (O-7 10 → 0, O-8 1 → 0) | review/layer6_gallery/dossier5m | — |
| 11 | Layer 6 gallery (L6-O9, O12) | E4 (b) objects (K6.5 / K4 broken) and K5 liquidity in the dossier (DECISIONS 51) | 10 E4 (b) entries; 43 area entries (liquidity window) | the dossier had no section for broken areas / lines being retested; its liquidity Levels were built without the Daily frame and without the visit's evidence window | branch dossier5m (local, awaiting ✅): `e4b_objects` section + liquidity on the engine's levels (O-9 10 → 0, O-12 43 → 0) | review/layer6_gallery/dossier5m | — |
