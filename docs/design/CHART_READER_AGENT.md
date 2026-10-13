# Chart Reader agent and structure reset — design (APPROVED by Abhi, 13 Oct; build R0 → R5)

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

Per 1M tokens (in / out): Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20. Prompt caching: a cache read costs
≈ 0.1× input (Opus 5.5: $0.20 / 1M); a cache write costs 1.25× (5-minute TTL) or 2× (1-hour TTL). One chart image ≈ 1,600 input
tokens. Output includes thinking. Every call also carries the ≈ 8k-token Method Pack (§12) as its cached system prefix.

| Read | Fresh in / out (est.) | $ / call, pack cached | $ / call, pack uncached | Calls / day (2 symbols) | $ / day cached | $ / day uncached |
|---|---|---|---|---|---|---|
| Light, Haiku | 6k / 1.5k | 0.0014 | 0.0022 | 150 | 0.21 | 0.33 |
| Standard, Sonnet | 12k / 3k | 0.056 | 0.070 | 50 | 2.80 | 3.50 |
| Escalated standard, Sonnet | 12k / 3k | 0.056 | 0.070 | ≈ 10 | 0.56 | 0.70 |
| Deep + critic, Sonnet | 25k / 7k | 0.12 | 0.14 | 12 | 1.44 | 1.63 |
| EOD + critic, Sonnet | 25k / 7k | 0.12 | 0.14 | 2 | 0.24 | 0.27 |
| Pre-open + critic, Opus | 25k / 7k | 0.27 (one write) | 0.27 | 2 | 0.54 | 0.54 |
| Cache writes (1-hour TTL, Sonnet / Haiku) | | | | ≈ 2–3 | ≈ 0.10 | — |
| **Total** | | | | | **≈ 5.9** | **≈ 7.0** |

TTL by start-to-start gap (§12.3): Sonnet reads share the pack every ≤ 15 min ⇒ 1-hour TTL; Haiku every 5 min ⇒ 1-hour TTL (a 5-minute
TTL sits on the edge); the two pre-open Opus reads run minutes apart ⇒ 5-minute TTL. Measured and reported (cached vs uncached per
call), not assumed.

**Budget:** reader cap `reader_daily_budget_usd` = **10.0 per trading day** (Abhi, 13 Oct chat; no reads on non-trading days),
`reader_monthly_budget_usd` = **220.0** (Abhi confirmed both); Vision keeps its own $2 / day. Both are dashboard settings.
Every call logged (time, symbol, read type, model, pack version, tokens cached / uncached, $). Cap reached ⇒ no more reads that day +
one Telegram line. If the measured cost nears the cap, degrade and tell Abhi: (1) light reads → every other 5M bar; (2) standard
reads → only near an area. The 1H deep read and the pre-open read are never dropped.

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

**Re-run with Abhi's 2-touch rule (report §8; charts in `…/2026-10-13/rerun_2touch/`):** valid lines **24 / 153 (16%)**, of
which 8 established (≥ 3 touches); valid areas **310 / 1,485 (21%)** — single prices now fail as "not a band" (all 279 SR V3 and 84
Vision levels), and zones2 keeps 337 broken zones. Live-engine lines mostly pass (18 / 32); the dashboard Trendline Gate still fails
(3 / 86, least-squares fit). **Golden line found:** the 30 Sep → 6 Oct NIFTY 15M spot line is valid from the 6 Oct close (7 Oct high =
3rd touch); projected to 22,654 at 12 Oct 09:15 against a bar high of 22,651.10 (FUT: line 22,709.6, high 22,720, close back below) —
the opening spike hit the projected touch. 44 lines fail only on "a touch in the last 2 sessions", which conflicts with a line that
waits for its 3rd touch ⇒ open question **TA5** for Abhi.

First run (3-touch minimum): Main causes: decision3 lines need only 2 touches (K6: ≥ 3); the dashboard "Trendline Gate" (`signals.detect_trendline`) is a
least-squares fit, not wick-anchored (79 / 86 fail); trendlines2 still draws weak / provisional lines; no per-timeframe cap (up to 5
lines on one chart). Areas: SR V3 and the Vision chart draw single prices, not zones, and keep broken levels (SR V3 has no written
validity rules); some decision3 1H bands are 4–5 MR wide (TL2); zones2 shows 7–17 zones per 15M chart.

**Abhi's decisions (TA1–TA4, 13 Oct) — the rule built in R1:**
- **TA1:** charts show only valid lines (K6) and valid areas (K4); invalid ones only in the debug view. One shared line check and one
  shared area check used by every chart.
- **TA2:** touch spacing default 6 bars (setting).
- **TA3 (corrected):** a trendline is drawn from **2 touches**; the projected **3rd touch is the trade location** (candidate area,
  where the line acts as S/R; entry still needs handover + commitment candle). ≥ 3 touches = "established" (evidence +), not a
  different rule. The other K6 rules stay for 2-touch lines: wick anchors; no close beyond the line between anchors; spacing; slope
  not extreme. Labels show the touch count and mark the projected 3rd-touch zone. KB K6 updated in #317. The audit is re-run with
  this rule (the 8 / 153 figure used a 3-touch minimum).
- **TA3b:** horizontal S/R works the same way: two reaction touches at one price area define the band; the 3rd touch is the trade
  location; role flip after a break (touches then count on the new side). A band and a line meeting at one price = **confluence**,
  the strongest location. KB K4 updated in #317.
- **TA4:** every area drawn as a **band** (low–high from its base / reaction candles), never a single price; broken areas hidden
  except the most recent broken one (dashed, "broken"); at most 3 bands above and 3 below price per timeframe.
- **Golden (R1):** Abhi's own trade, NIFTY FUT 15M — touch 1 = 30 Sep high, touch 2 = 6 / 7 Oct highs; the projected line meets the
  ≈ 22,667 FUT supply on 12 Oct; 3rd touch = the 12 Oct opening spike into the confluence → bear call. The line module must find it
  from the 2 touches alone and mark the 12 Oct 3rd-touch zone before 12 Oct (no look-ahead); plus the band + line confluence golden.

Related PRs: R:R correction #316; KB K11 expansion #317.

## 11. Testing and promotion

1. **Golden days**, anonymised (symbol hidden, dates shifted, prices rescaled): 12 Oct NIFTY — bear call found at the 09:30–09:45
   commitment; 29 Sep — a valid bear-call read (no R:R skip). NIFTY holdout (2024-04 … 2026-06) stays sealed.
2. **Shadow, 2 weeks**, logged beside decision3's proposals and Abhi's own ✅ / ❌ / trades.
3. **Promotion report.** Abhi decides whether `signal_source` switches to `reader_agent`. decision3 keeps running PAPER until then.

## 12. Method Pack — the KB as the AI's fixed method text (Vision and the reader)

Knowledge files in a claude.ai "Project" are not visible to API calls; the API equivalent is a fixed method text sent as the system
prompt on every call, prompt-cached.

1. **`docs/knowledge/method_pack.md` (English), generated from `KNOWLEDGE_BASE.md`** by `scripts/build_method_pack.py`; the KB stays the
   single source. A CI test fails when the pack is stale against the KB. Target ≈ 6–10k tokens. Contents, in Abhi's method order:
   1) top-down: weekly state → daily trend (degree-aware Dow, protected origin, a correction does not change the trend) → 1H buyer /
      seller areas → 15M pullback → 5M CHoCH;
   2) areas: demand / supply, flips, sharp-fall / sharp-rise points, validity rules, "a zone is dead only beyond the far swing";
   3) trendlines / channels: K6 validity (TA3: a line is drawn from 2 touches, the projected 3rd touch is the trade location with
      handover + commitment candle there, ≥ 3 touches = established / evidence +; wick anchors, close breaks, spacing, slope),
      horizontal vs sloping (TA3b: a horizontal band is drawn from 2 reaction touches the same way), confluence;
   4) corrections: zigzag / flat (incl. expanded / running) / triangle / combinations; impulse vs correction from structure + anatomy;
   5) zone study: handover (trend-side candles growing, counter side weakening, volume), patterns inside the area (K11), sweeps /
      traps (K5);
   6) trigger: lower-timeframe CHoCH by close + a dominant commitment candle (any reversal form) on higher FUT volume;
   7) never: breakout entries, counter-trend entries, a minor-swing break alone as confirmation, prices not present in the facts;
   8) Abhi method notes: reviewed lessons from ❌ reasons and 📝 corrections, added only after Abhi approves them.
   **Not in the pack:** R:R / SL / target / lots / exits (dashboard settings).
2. **Checklist output.** Vision and the reader return JSON with one entry per checklist item 1–7: `pass` / `fail` / `NA` + one line of
   evidence citing a fact or a visible chart feature; overall verdict `agree` / `partly` / `disagree`. Telegram shows failed / NA items
   first, at most 12 lines. Vision stays audit-only: it never blocks or changes orders or decisions.

   **Item mapping (Abhi R0-1, fixed; `vision/checklist.py` `DECISION3_MAP`, written into every V4 result / log row):**

   | Checklist item (Method Pack section) | decision3 step |
   |---|---|
   | 1 Top-down trend | ① Daily trend (Dow, Weekly parent) |
   | 2 Area | ② 1H levels / areas (incl. sloping-line areas) |
   | 3 Trendline / channel | ⑤ K inner trendline |
   | 4 Correction | ③ K open (pullback / correction) |
   | 5 Zone study | ④ power shift + ⑥ a2 zone study |
   | 6 Trigger | ⑥ commitment c0 + LTF CHoCH c1 |
   | 7 Never-list | hard rules H1–H3 (trend side, no breakout, known prices) |
3. **Caching.** Method Pack + fixed output schema = the cached system prefix (explicit breakpoint at its end); chart images and the
   facts of the moment come after it. TTL per §8; cached vs uncached cost per call reported in the cost table.
4. **One pack for both.** Vision (V4 prompt) and the reader use the same pack version; every log line records the pack version
   (content hash), so any read traces to the exact method text.
5. **Tests:** golden days (12 Oct, 29 Sep, BANKNIFTY a-b-c) through Vision with the pack — the checklist items must come out as Abhi
   reads them; the stale-pack CI test; a test that the output contains no price missing from the facts.

## 13. Build order (after approval; no side changes)

- **R0** KB: K11 expansion merged (Abhi-approved); R:R-correction PR merged; Method Pack generator + stale-pack CI test (§12);
  Vision V4 prompt with the pack and the 1–7 checklist JSON (audit-only), golden days through Vision.
- **R1** facts package: one owner per concept (§3) with a single dossier function + tests (no AI calls); trendlines / areas fixed to
  the audit rule (§10).
- **R2** charts (valid lines / areas only) + anonymiser.
- **R3** light (Haiku) + reader / critic / rule checker + prompt caching + budget log; golden days; measured cost reported.
- **R4** live loop + working memory + shadow Telegram + Reader timeline page (VPS command from Abhi).
- **R5** promotion report; frozen engines archived only after Abhi's decision.

Each step is reported to Abhi with its golden-day results before the next one starts.
