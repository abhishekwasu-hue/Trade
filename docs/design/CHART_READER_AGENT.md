# Chart Reader agent and structure reset — design (for Abhi's approval, nothing is built yet)

Sources: Abhi's GO note, STRUCTURE RESET, R:R CORRECTION and the §9 answers (all 13 Oct). Status: **design only**. Abhi approves
this whole document once; the build then follows it phase by phase (§12) with no side changes. Built in the Trade repo first and
ported to ATP (N6) only after the shadow proves it.

## 1. Why

About 18 packages each re-implement a slice of the same method, so every fix lands in one engine and is missing from the others.
`decision3` is a checklist that decides on the last candle; adding candle rules one day at a time (the parked 09:15 branch) does not
fix that. The reset: **one KB, one facts layer (one module per concept), one reader, one rule checker, one executor.**

```
 KB (K1–K14) ─ defines ─► FACTS (one module per concept; facts + evidence, no votes)
                               │
 OHLC + FUT volume ───────────►┴─► dossier ─► READER (LLM) ─► CRITIC (LLM) ─► RULE CHECKER (code) ─► proposal ─► Abhi ✅ ─► EXECUTOR (PAPER)
                                                  ▲                │
                                                  └ working memory ┘
```

## 2. KB change control (one source of truth)

`docs/knowledge/KNOWLEDGE_BASE.md` is the only place a trading concept is defined. Every concept entry uses one format: definition;
market psychology (who is trapped, who is in control); identification rules (relative units only); validity conditions;
invalidation; how Abhi's method uses it (context / area / evidence / trigger — never a breakout entry); reliability evidence;
common mistakes; fixtures.

Sequence for any rule change: **KB diff → Abhi approves → code → test → traceability row.** No rule changes in code without a KB
change first. No one-day patches. When a golden day fails, the question is "which KB concept was missed or misread", never "which new
rule catches this day".

K11 (chart patterns) is expanded to the full set in a separate KB PR (linked in the PR description of this doc): trend / correction
shapes, reversal shapes and liquidity shapes, each in the format above and each with its role (inside a pullback / inside an area /
at the end of a trend). A pattern is named only after its confirming condition.

## 3. Facts layer — one owner module per concept

Every owner function returns facts with evidence (prices, bar times, counts), never a vote, score or grade. "Merge" = the logic
moves into the owner; "retire" = no longer called (archived after promotion); "frozen" = no new work (§4).

| Concept (KB) | Owner module | Currently also implemented in | Keep / merge / retire |
|---|---|---|---|
| Swings / structure, degree-aware: trend, protected swing, BOS / CHoCH (K1) | `swings2` (+ `pivots` as its pivot engine) | `decision3/daily_swings`, `decision3/daily` (Daily Dow), `market_state/core`, `chart_reader/structure`, `chart_reader/trend`, `opportunity_engine/structure`, `elliott/swings`, `price_action/legs` | keep swings2 + pivots; merge the Daily Dow / weekly parent logic of decision3 into swings2; `market_state.core` keeps only its bar-frame helper; retire the rest |
| Legs: impulse vs correction (K2, K3) | `reader2` (structure vote + anatomy vote + fusion) | `legs2`, `decision3/daily_legs`, `decision3/accepted_legs`, `chart_reader/structure`, `correction/reader`, `simple_core/waves`, `price_action/leg_eval`, `elliott/counts` | keep reader2; merge legs2 features and `decision3.daily_legs.read_counter` into reader2 (it already calls them); Elliott counts stay advisory evidence inside reader2; retire the rest |
| Areas: demand / supply, flips, lifecycle, sharp-fall / sharp-rise points (K4) | `decision3/levels.py` (to move to the facts package) | `zones2`, `sr_levels_v3.py`, `market_zones` (bot DB levels), `chart_reader/areas`, `chart_reader/zones`, `opportunity_engine/zones`, `opportunity_engine/level_quality`, `price_action/levels_v2`, `major_levels`, `level_strength`, `level_validation` | keep decision3 levels; merge the zones2 profiles and the SR V3 validity rules into it; the executor's area source switches to it at promotion; retire the rest |
| Trendlines and channels (K6) | `trendlines2` | `decision3/trendline.py`, `price_action/trendlines.py`, `mtf` channel, `chart_reader/areas` (sloping) | keep trendlines2, fixed to the K6 validity audit (§10); merge decision3/trendline; retire the rest |
| Chart patterns (K11, expanded) | `patterns2` | `opportunity_engine/detectors` (box / triangle / flag / double), `chart_reader/evidence.patterns`, `elliott/patterns`, `vision_led/situation_map` | keep patterns2, aligned to the new K11; retire the rest |
| Candles: K9 logical reversal, dominant commitment, handover (K9) | `decision3/method.py` (reversal_form, commitment, zone_study) | `chart_reader/candles`, `swings2/candles`, `price_action/candles`, `legs2/features` (anatomy input) | keep decision3 method functions (move to the facts package); retire the rest |
| Volume: FUT, trend side vs counter side (K10) | `opportunity_engine/volume.py` (data path, not a decision path) + the collector | `decision3/volume_pane`, `legs2/volume`, `chart_reader/volume`, `decision3.method._vol` | keep (move to the facts package); merge the summaries; retire the rest |
| Lower-timeframe structure / CHoCH (K1 at LTF) | `decision3/method.ltf_choch` | `swings2` structure on 5M, `mtf` | keep; re-check against swings2 at 5M degree, then one implementation |
| Liquidity / sweeps (K5) | `decision3/liquidity.py` | `chart_reader/evidence.liquidity`, `swings2` sweep flag | keep; retire the rest |
| Gaps (K13) | `vision/gap_context.py` | `chart_reader/gap.py`, `opportunity_engine/detectors/gap.py` | keep; retire the rest |
| Context: PDH / PDL / PDC, week H-L, opening range, VIX, FII / DII, global cues (K8, K14) | `vision/context.py` | `chart_reader/evidence` (VIX), `vision_led/situation_map` (FII / DII, cues), `decision3/liquidity` (PDH / PWH pools) | keep; move the FII / DII / cues reader in from vision_led; context only, never a trigger |
| RSI divergence only (K10) | `rsi2` | `chart_reader/evidence.divergence` | keep; retire the rest |

Shared infrastructure, not a concept (kept): `elliott/data_policy` (holdout guard), contracts / strikes / costs, `paper`, `cloud_db`,
`vision` store / Telegram / approval, `bots_common` (executor plumbing).

**One reader:** the Chart Reader agent (§5). **One rule checker:** decision3's hard rules only (H1–H3: trend side, no breakout,
known prices); decision3 ⑦ R:R stays OFF (§6). **One executor:** the 15M SRv2 bot with its PAPER / approval path.

## 4. Frozen engines (no new work; kept for comparison until the agent is promoted, then archived)

`decision2` · `simple_core` · `mtf` · `opportunity_engine` decision paths (detectors, bias, gate, scoring, selector, engine) ·
the old `chart_reader` grading (grade, rules, risk, evaluate, narrative, checklist) · `vision_led`.
Proposed additions for Abhi to confirm: `correction/` (annotation reader) and `price_action/` except what `vision/context.py` still
imports until the areas merge is done.

## 5. The reader (LLM), critic and working memory

Inputs, top-down (Abhi's method): Weekly ≈ 2 years (market state) · Daily ≈ 6 months (trend decided here at least, protected
swings, daily areas) · 1H ≈ 15 trading days (buyer / seller areas) · 15M ≈ 8 trading days (pullback / correction pattern, setup) ·
5M current + previous session (LTF CHoCH near an area only). Price from spot, volume from FUT (15M, 5M). Closed bars only.
Symbols: NIFTY and BANKNIFTY.

The reader gets the dossier (+ images on standard / deep reads) and the working memory and writes JSON: (1) market story;
(2) areas to watch (ids from the facts); (3) scenario "if price does X at area A, then trade Y"; (4) what invalidates the read;
(5) when triggered: enter / wait / skip with reasons. The **critic** checks the read against the facts and lists contradictions;
the reader revises once; anything still contradicted ⇒ no proposal (logged). The **working memory** (story, plan, watched areas,
what changed) is updated incrementally on every read, never rebuilt from scratch.

The prompt includes `docs/knowledge/ABHI_METHOD_NOTES.md`: Abhi's ❌ reasons, 📝 corrections and gallery labels, compiled and
reviewed by Abhi. No automatic threshold tuning.

## 6. Rule checker (code, after the reader)

- trend side only; no breakout trades;
- every price in the output must exist in the facts / OHLC, else the whole output is rejected;
- SL / target / lots from the dashboard settings — the ticket shows them; exits never blocked; PAPER only; Abhi's ✅ before entry;
  LIVE untouched; AI never places an order (the proposal enters the existing `signal_source` / Telegram approval path).
- **No R:R rule.** The reader and the checker never filter, score or skip on R:R; no "skipped on R:R" reason anywhere. R:R is
  Abhi's own decision at approval. If Abhi later wants an R:R filter, it is a dashboard setting, default OFF; nothing hard-wires
  one. (The separate R:R-correction PR removes the remaining R:R gates from the live path.)
- Information only, never pass / fail: "a higher-timeframe opposite area lies between entry and the dashboard target at X".

## 7. Cadence and models (Abhi: Haiku for the 5M light read; chart images only to Sonnet and Opus)

Active 09:15–15:30 on trading days.

| Read | When | Model | Input |
|---|---|---|---|
| Light | every closed 5M bar | Haiku 5.5 | facts as text only, no images: what changed since the last read, price near / inside a watched area, counter side weaker / stronger (FUT volume), LTF CHoCH, sweep; updates the working memory and decides whether to escalate |
| Standard | every closed 15M bar | Sonnet 5.5 | 15M image + facts + working memory; may say enter / wait / skip |
| Escalated standard | at once, when a light read sees a trigger (price in an area + dominant candle / CHoCH / sweep) | Sonnet 5.5 | same as standard |
| Deep + critic | every closed 1H bar; EOD 15:45 | Sonnet 5.5 | W / D / 1H / 15M images + facts |
| Pre-open + critic | 09:00 | Opus 5.5 | same as deep |

A proposal only comes from a standard or deep read, never from a light read.

## 8. Cost (estimate; measured on the golden days and reported before the shadow)

Per 1M tokens (in / out): Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20; cached input ≈ one tenth. One chart
image ≈ 1,600 input tokens. Output includes thinking.

| Read | Tokens in / out (est.) | $ / call | Calls / day (2 symbols) | $ / day |
|---|---|---|---|---|
| Light, Haiku | 6k / 1.5k | 0.0014 | 150 | 0.21 |
| Standard, Sonnet | 12k / 3k | 0.054 | 50 | 2.70 |
| Escalated standard, Sonnet | 12k / 3k | 0.054 | ≈ 10 | 0.54 |
| Deep + critic, Sonnet | 25k / 7k | 0.12 | 12 | 1.44 |
| EOD + critic, Sonnet | 25k / 7k | 0.12 | 2 | 0.24 |
| Pre-open + critic, Opus | 25k / 7k | 0.24 | 2 | 0.48 |
| **Total** | | | | **≈ 5.6 → ≈ 4.6 with prompt caching** |

Prompt caching (fixed system prompt + method notes + the unchanged part of the dossier) is part of R3 and is measured, not assumed.

**Budget (Abhi):** `reader_daily_budget_usd` = **10.0 per trading day** (no reads on non-trading days); `reader_monthly_budget_usd`
= **220.0** (≈ 22 trading days × $10 — Abhi to confirm). Both are dashboard settings, separate from Vision's $2 / day. Every call is
logged (time, symbol, read type, model, tokens, $). Cap reached ⇒ no more reads that day + one Telegram line. If the measured cost
ever nears the cap, degrade in this order and tell Abhi: (1) light reads → every other 5M bar; (2) standard reads → only near an
area. The 1H deep read and the pre-open read are never dropped.

## 9. Output: Telegram and dashboard

Every shadow message is labelled **"SHADOW — no trade"**. Telegram gets only: the pre-open plan; reads that CHANGE the plan (new
watched area, invalidation hit, scenario switched); every enter / skip-with-reason at an area; the 15:45 EOD review. Every read
(all types) goes to the log and to a dashboard **"Reader timeline"** page, not to Telegram.

## 10. Trendline / area validity audit (done, read-only)

Report: `docs/reports/2026-10-13_trendline_area_audit.md` (in this PR); script `research/trendline_area_audit.py`; 80 charts + CSV
in private storage (`trade-data/reports/trendline_audit/2026-10-13/`). 20 session closes (11 Sep … 12 Oct 2026), NIFTY / BANKNIFTY,
15M / 1H. Illustration, not a test (mostly the contaminated period); nothing tuned; holdout never loaded.

| Symbol | TF | Lines drawn | K6-valid | Areas drawn | K4-valid |
|---|---|---|---|---|---|
| NIFTY | 15M | 54 | 6 | 409 | 240 |
| NIFTY | 1H | 24 | 1 | 326 | 124 |
| BANKNIFTY | 15M | 42 | 1 | 400 | 201 |
| BANKNIFTY | 1H | 33 | 0 | 350 | 145 |
| **All** | | **153** | **8 (5%)** | **1,485** | **710 (48%)** |

Main causes: decision3 lines need only 2 touches (K6: ≥ 3); the dashboard "Trendline Gate" (`signals.detect_trendline`) is a
least-squares fit, not wick-anchored (79 / 86 fail); trendlines2 still draws weak / provisional lines; no per-timeframe cap (up to 5
lines on one chart). Areas: SR V3 and the Vision chart draw single prices, not zones, and keep broken levels (SR V3 has no written
validity rules); some decision3 1H bands are 4–5 MR wide (TL2); zones2 shows 7–17 zones per 15M chart.

Rule after the fix (built in R1, not before approval): charts show **only K6-valid lines, at most 2 per timeframe, each labelled
with its touch count**, and only K4-valid areas (real bands, width cap), through one shared line check and one shared area check used
by every chart. Abhi's decisions: TA1–TA4 in `docs/reports/v22/OPEN_QUESTIONS.md` (show only valid; 6 or 8 bars between touches;
touch minimum 2 → 3; band drawing for SR V3 / Vision).

Related PRs: R:R correction #316; KB K11 expansion #317.

## 11. Testing and promotion

1. **Golden days**, anonymised (symbol hidden, dates shifted, prices rescaled): 12 Oct NIFTY — bear call found at the 09:30–09:45
   commitment; 29 Sep — a valid bear-call read (no R:R skip). NIFTY holdout (2024-04 … 2026-06) stays sealed.
2. **Shadow, 2 weeks**, logged beside decision3's proposals and Abhi's own ✅ / ❌ / trades.
3. **Promotion report.** Abhi decides whether `signal_source` switches to `reader_agent`. decision3 keeps running PAPER until then.

## 12. Build order (after approval; no side changes)

- **R0** KB: K11 expansion merged (Abhi-approved); R:R-correction PR merged.
- **R1** facts package: one owner per concept (§3) with a single dossier function + tests (no AI calls); trendlines / areas fixed to
  the audit rule (§10).
- **R2** charts (valid lines / areas only) + anonymiser.
- **R3** light (Haiku) + reader / critic / rule checker + prompt caching + budget log; golden days; measured cost reported.
- **R4** live loop + working memory + shadow Telegram + Reader timeline page (VPS command from Abhi).
- **R5** promotion report; frozen engines archived only after Abhi's decision.
