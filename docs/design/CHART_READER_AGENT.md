# Chart Reader agent — design (for Abhi's approval, nothing is built yet)

Source: Abhi's GO note (13 Oct). Status: **design only**. No code is written until Abhi approves this file. Built in the Trade repo first
and ported to ATP (N6) only after the shadow proves it.

## 1. Why

`decision3` is a checklist: every step passes or fails on the last candle, so a trader's reading of the last 7–8 days (channel,
tired counter side, confluence, sweep) never becomes one picture. Adding candle rules one day at a time (the parked 09:15 branch)
does not fix that. The modules stay; they stop voting. They measure, and one reader reads.

```
 OHLC + FUT volume ──► TOOLS (facts + evidence, no votes) ──► dossier ──► READER (LLM) ──► CRITIC (LLM) ──► HARD RULES (code) ──► proposal ──► Abhi ✅
                                                     ▲                         │
                                                     └──── working memory ◄────┘
```

## 2. Tools — measured facts only

Every tool returns facts with their evidence (prices, bar times, counts). No tool returns a score, grade or vote.

| Fact | Per timeframe | Module (existing) |
|---|---|---|
| Trend + protected swing | W / D / 1H / 15M | `swings2` market structure, `market_state` |
| Swing map (BOS / CHoCH / sweeps) | all | `swings2` |
| Impulse / correction legs (anatomy + structure) | D / 1H / 15M | `reader2` (anatomy + structure), `legs2` |
| Demand / supply areas, flipped levels | D / 1H | `zones2`, decision3 `levels` |
| Trendlines / channels | D / 1H / 15M | `trendlines2` |
| Patterns | 1H / 15M | `patterns2` |
| FUT volume: trend side vs counter side | 15M / 5M | `opportunity_engine.volume` + collector parquet |
| Lower-timeframe structure / CHoCH near an area | 5M | decision3 `method.ltf_choch` |
| RSI divergence only | 1H / 15M | `rsi2` |
| Context lines (FII / DII, VIX, global cues) — context only, never a trigger | — | existing market report |

A new thin package `reader_agent/` adds only: `facts.py` (calls the modules, returns one JSON dossier), `charts.py` (renders the
images, reusing `vision/chart.py`), `memory.py`, `reader.py`, `critic.py`, `rules.py`, `budget.py`, `store.py`.

## 3. Inputs (top-down, Abhi's method)

| Timeframe | Window | Used for |
|---|---|---|
| Weekly | ≈ 2 years | overall market state |
| Daily | ≈ 6 months | trend (decided here at least), protected swings, daily areas |
| 1H | ≈ 15 trading days | buyer / seller areas |
| 15M | ≈ 8 trading days | the pullback / correction pattern and the setup |
| 5M | current + previous session | lower-timeframe CHoCH near an area only |

Price from spot; volume from FUT (15M and 5M). Only closed bars. Symbols: NIFTY and BANKNIFTY.

## 4. Reader → critic → hard rules

**Reader** (LLM) gets the dossier (+ images on standard / deep reads) and the working memory, and writes JSON:
1. market story; 2. areas to watch (ids from the facts); 3. scenario "if price does X at area A, then trade Y";
4. what invalidates the read; 5. when triggered: `enter` / `wait` / `skip` + reasons.

**Critic** (second pass, same tier) checks the read against the facts and lists contradictions. The reader revises once. Anything
still contradicted ⇒ no proposal (logged).

**Hard rules** (code, after the reader; the LLM cannot override them):
- trend side only, no breakout trades;
- R:R ≥ 3 against the nearest opposite area on 15M / 1H / Daily (see §9 Q1);
- every price in the output must exist in the facts / OHLC, else the whole output is rejected;
- SL / target / lots from the dashboard; PAPER only; Abhi's ✅ before any entry; exits never blocked; LIVE untouched;
- AI never places an order — the proposal goes into the existing approval path (`signal_source`, Telegram ✅ / ❌).

## 5. Cadence and working memory

The reader is active 09:15–15:30 and keeps a **working memory** (story, plan, watched areas, what changed). Each read updates it
incrementally; it is never rebuilt from scratch.

| Read | When | Model (proposal, §6) | Input |
|---|---|---|---|
| Light | every closed 5M bar | Haiku 5.5 | facts as text, no images: what changed, price near / in an area, counter side weaker / stronger, LTF CHoCH |
| Standard | every closed 15M bar, or a light read escalates | Haiku 5.5 (option B) / Sonnet 5.5 (option A) | 15M image + facts; may say enter / wait / skip |
| Deep | every closed 1H bar + EOD 15:45 | Sonnet 5.5 + critic | W / D / 1H / 15M images + facts; re-checks the big picture |
| Pre-open | 09:00 | Opus 5.5 + critic | same as deep |

Escalation: a light read that sees a trigger (price in an area + dominant candle / CHoCH / sweep) calls a standard read at once.
A proposal only ever comes from a standard or deep read.

## 6. Cost (estimate — to be measured on the golden days and reported before the shadow)

Prices per 1M tokens (input / output): Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20; cached input is about
one tenth. One chart image ≈ 1,600 input tokens. Output includes the model's thinking.

| Read | Tokens in / out (est.) | $ per call | Calls / day (2 symbols) | $ / day |
|---|---|---|---|---|
| Light, Haiku | 6k / 1.5k | 0.0014 | 150 | 0.21 |
| Standard, Haiku | 12k / 3k | 0.003 | 50 | 0.15 |
| Standard, Sonnet (option A) | 12k / 3k | 0.054 | 50 | 2.70 |
| Deep + critic, Sonnet | 25k / 7k | 0.12 | 12 | 1.44 |
| EOD + critic, Sonnet | 25k / 7k | 0.12 | 2 | 0.24 |
| Pre-open + critic, Opus | 25k / 7k | 0.24 | 2 | 0.48 |

- **Option B (recommended start):** Haiku for light + standard ≈ **$2.5 / day** — inside the $5 cap with room for escalations.
- **Option A:** Sonnet for standard ≈ **$5.1 / day** — at the cap; only if the golden-day test shows Haiku misreads the 15M chart.
- Caching the fixed part (system prompt + method notes + older dossier) lowers these further; measured, not assumed.

**Budget** (dashboard settings, next to Vision's separate $2 / day): `reader_daily_budget_usd` = 5.0, `reader_monthly_budget_usd`
= 100.0. Every call is logged (time, symbol, read type, model, tokens, $). Cap reached ⇒ no more reads that day + one Telegram line.
If the measured cost runs over, degrade in this order and tell Abhi: (1) light reads → every other 5M bar; (2) standard reads →
only near an area. The 1H deep read and the pre-open read are never dropped.

## 7. Learning (no auto-tuning)

Abhi's ❌ reasons, 📝 corrections and gallery labels are compiled into `docs/knowledge/ABHI_METHOD_NOTES.md`; Abhi reviews each
change; the file is part of the reader's prompt. No threshold is tuned automatically.

## 8. Testing and promotion

1. **Golden days** (anonymised: symbol hidden, dates shifted, prices rescaled, so the model cannot recall the outcome):
   - 12 Oct NIFTY: bear call found at the 09:30–09:45 commitment;
   - 29 Sep: "valid read, skipped on R:R".
   NIFTY holdout (2024-04 … 2026-06) stays sealed.
2. **Shadow, 2 weeks:** reads go to Telegram as "SHADOW — no trade" (one line per standard / deep read that changes the plan, not every
   light read), logged beside decision3's proposals and Abhi's own ✅ / ❌ / trades.
3. **Promotion report.** Abhi decides whether `signal_source` switches to `reader_agent`. decision3 keeps running PAPER until then.

## 9. Questions for Abhi

1. **R:R:** #314 removed R:R from decision3 ("R:R is Abhi's call"). This design puts R:R ≥ 3 back as a hard rule **only for the
   reader's proposals**, as the GO note says. Confirm.
2. **Model for standard reads:** start with option B (Haiku) and switch to Sonnet only if the golden test fails?
3. **Shadow Telegram volume:** only reads that change the plan (as in §8.2), or every standard read?

## 10. Build order (after approval)

R1 facts dossier + tests (no AI calls) → R2 charts + anonymiser → R3 reader / critic / rules + budget log (golden days, measured
cost reported) → R4 live loop + working memory + shadow Telegram (VPS command from Abhi) → R5 promotion report.
