# 04 — Supply/Demand Zones, S/R Areas and Liquidity: how discretionary traders find and rank them, and what the evidence says

Scope: NIFTY 15m pullback-end trading (credit spreads sold at the end of an ABC correction, in the impulse direction). This note **extends** two earlier notes and does not repeat them:
- `Leg and level strength research/sr_level_validity.md` — academic S/R evidence (Osler 2000/2003, Garzarelli 2014, Chung & Bellotti 2021, STW 1999, round-number barrier studies), Seiden odds-enhancer point scores, Bulkowski throwback/pullback stats, OHLC proxies for volume.
- `Chart knowledge/areas_liquidity_fib_channels.md` — codable MR-based rules for zones, sweeps, Fib, channels, round numbers; Kavajecz & Odders-White (2004) depth-peak finding.

New here: SMC/ICT order blocks, breaker blocks, FVGs and the only numbers anyone has published on them; Wyckoff spring/upthrust/test; Turtle Soup; Market/Volume Profile (POC, VA, HVN/LVN, naked POC, IB, open types, 80% rule); PDH/PDL continuation stats; ORB evidence (Zarattini-Aziz and its net-of-cost replication); NIFTY session facts (volatility by hour, gap-fill odds, expiry effects); a zone taxonomy table; a confluence-ranking scheme with evidence grades.

Tags: **[STAT]** = measured result (peer-reviewed, working paper, or a disclosed-method backtest); **[RULE]** = a definition/identification rule from a named practitioner source; **[PRAC]** = practitioner claim with no disclosed measurement. Units: **MR** = median true range of the last 50 closed 15m bars (as in the earlier notes). All rules use closed bars; a pivot is known only k bars after it prints.

---

## Takeaway

1. Every zone school (Seiden supply/demand, Wyckoff, SMC/ICT, Market Profile) is describing the same two things: (a) **a price where orders rested and price left fast** (base → departure; order block → displacement; LVN/single prints; spring low), and (b) **a price just beyond an obvious extreme where stops rest** (liquidity pool; equal highs/lows; PDH/PDL; round numbers). The only mechanism with hard evidence is (b): Osler's order data shows take-profits *at* round numbers and stops *just beyond* them, which produces both the bounce and the sweep-then-cascade behaviour. (a) is supported indirectly by Kavajecz & Odders-White (S/R coincides with limit-order depth peaks) and by nothing else peer-reviewed.
2. **No peer-reviewed test of order blocks, breaker blocks, FVGs, Seiden zones, springs or naked POCs exists.** The best available numbers are vendor backtests (Backtrex, FXNX, edgeful) with undisclosed costs and post-hoc filter selection. They all agree on one thing: the **raw zone/level gives ~40–50% win rates; a confirmation (sweep, displacement candle, close-back) plus session filter lifts it to ~53–59%**, and the edge comes from R:R, not hit rate.
3. The "fresh beats tested" rule (Seiden, SMC) and the "more touches = stronger" finding (Garzarelli, Chung & Bellotti) are both real on their own horizons. Reconcile by scoring **reaction quality per touch**, not raw count (detail in Ranking evidence).
4. For a 15m NIFTY pullback seller the practically codable, defensible stack is: **origin zone (base + displacement + BOS) ∩ liquidity pool (swing/equal lows, PDL, round number) ∩ Profile reference (prior VAL/VAH, naked POC, IB edge)**, then a **sweep-and-reclaim or rejection close** as trigger. Zone width should be derived from the base candles and capped at ~1–1.5 MR; a wider zone destroys the 1:3 R:R the trader needs.
5. PDH/PDL and ORB levels on index futures behave as **continuation** levels more often than reversal levels (edgeful 56–67%; Zarattini-Aziz gross edge), so treat a *clean break with acceptance* of PDH/PDL as trend information and only *fade* them on a sweep-and-reclaim.

---

## Cited findings

### Supply/demand (Seiden school) and zone scoring
- [RULE] Zone = the **base** (1–3 tight bars) immediately before an **impulsive departure** (≈3+ consecutive same-direction bars). Four shapes: RBR/DBD (continuation bases), RBD/DBR (reversal bases). Draw from base top to base bottom, or base top to the highest opposite-colour body. — [crosstrade.io supply & demand](https://crosstrade.io/learn/price-action/supply-and-demand-zones)
- [PRAC] Strength = strong departure, tight base, untested, higher-timeframe alignment. Zones "weaken after 1–2 tests and are treated as broken after 3+"; "fresh zones with rejection confirmation" claimed 60–70% win rate — **no sample or source given**. — [crosstrade.io](https://crosstrade.io/learn/price-action/supply-and-demand-zones)
- [RULE] Scoring dimensions (Seiden checklist as restated by LuxAlgo): base quality (short, tight > long, choppy), departure strength (full-bodied consecutive candles or a gap), freshness (untested best; each retest consumes orders), time at level, room to the next opposing level ("profit zone"), confluence with an independent level, and a **context gate** (skip demand sitting directly under HTF supply). Automated proxies: candle count for base, candle range / average range for departure, retest counter for freshness. No thresholds published. — [LuxAlgo zone scoring & refinement](https://www.luxalgo.com/library/concept/zone-scoring-and-refinement.md)
- [RULE] Proximal/distal line convention: pick wicks or bodies and keep it constant. Wick-drawn = wider, fewer stop-outs, worse R:R; body-drawn = tighter, better entry, more wick pierces. A "deeply penetrated" zone is discarded. Overlapping zones: merge, or keep the freshest best-formed one; nest a LTF zone inside the HTF zone for entry. — [LuxAlgo](https://www.luxalgo.com/library/concept/zone-scoring-and-refinement.md)
- [PRAC] Zone width: "should scale with timeframe and volatility… many traders sanity-check width against ATR so the zone stays small relative to the moves they are trading"; no ATR length or multiple is given anywhere in the sources found. Edges commonly from the extreme wick of the defining touches to the nearest cluster of bodies. — [LuxAlgo ATR-based S/R zones](https://www.luxalgo.com/library/indicator/oY7rfzuc-atr-based-support-and-resistance-zones/)

### SMC / ICT: order blocks, breakers, FVGs, liquidity
- [RULE] Order block = "the last opposite candle before a structure break"; prefer blocks formed with displacement, HTF alignment and a contained FVG; textbook entry on return ("mitigation"), ideally after a liquidity sweep, stop beyond the block, target the next opposing liquidity pool. — [AlphaEx Capital, order blocks explained](https://www.alphaexcapital.com/smart-money-concepts/order-blocks-explained)
- [STAT-grade commentary] The same source states plainly: no peer-reviewed study shows the last opposite candle marks institutional orders; no tier-1 study or verified backtest tests ICT order blocks; the "80%/90% fill rate" claims circulating online are unsourced; Osler's "Support for Resistance" is "the closest honest anchor" for why zones persist; published examples suffer survivorship bias. — [AlphaEx Capital](https://www.alphaexcapital.com/smart-money-concepts/order-blocks-explained)
- [RULE] Breaker block = an order block invalidated by a BOS/CHoCH that moved through its **entire body**; traded in the direction *opposite* to the original impulse (former demand becomes supply). Three validity conditions: (1) a real liquidity sweep of a meaningful prior swing, (2) displacement through the opposing swing ("a slow grind back above the high is a range, not a shift"), (3) first, fresh retest. A plain S/R flip (no sweep, no displacement) is "the weakest of the three setups". — [MQL5 breaker blocks](https://www.mql5.com/en/blogs/post/773691); [Backtrex breaker guide](https://backtrex.com/en/blog/ict-breaker-block-trading-guide)
- [STAT, vendor] Breaker backtest (Backtrex, 4H/D bias + 5/15m confirmation, 2022–24): EURUSD 87 setups, 54% WR, PF 1.62; NAS100 64 setups, 57% WR, PF 1.74. "PF drops below 1.2 without an aligned FVG." Costs undisclosed, period labelled inconsistently (12 vs 36 months), tiny n. — [Backtrex](https://backtrex.com/en/blog/ict-breaker-block-trading-guide)
- [RULE] FVG (3-candle imbalance): bullish when candle-1 high < candle-3 low; bearish when candle-1 low > candle-3 high. edgeful's report measures mitigation rate by instrument, session, lookback and gap size (six size buckets from 0–0.024% to >0.25%) but publishes no headline figure. — [edgeful FVG report](https://www.edgeful.com/blog/posts/fair-value-gaps-report)
- [STAT, vendor] FXNX "1,000 mechanical trades", EUR/GBP/JPY, 15m BOS + OB with imbalance + 50% limit: raw SMC WR 38–48%; standalone OB (no adjacent FVG) **failed 56.9%**; FVG mitigation within 48h on EURUSD **64.8%**; liquidity-sweep directional follow-through **58.2%**; blind limit at swing high 42.3% WR vs **sweep-confirmed (5m) 58.7%**; killzone + 4H bias filter moved expectancy from −0.22R to +0.64R. Period, data resolution, costs and per-model n undisclosed; filters chosen post hoc; broker source. — [FXNX SMC backtest](https://fxnx.com/en/blog/smart-money-concepts-work-backtest-evidence)
- [STAT, vendor] Liquidity-sweep strategy (Backtrex, H1 EURUSD+XAUUSD 2019–24, 1,247 trades): sweep = exceed an equal high/low by ≥3 pips; displacement = opposite-direction candle with body ≥70% of range within 2 candles; entry at FVG midpoint; SL 5 pips beyond swept level; TP next opposite liquidity, min 1:1.5. Result 53.2% WR, PF 1.68, max DD −14.3%, 2022 a losing year (46.5%). Kill-zone filter alone: 47.1%→53.2% WR, PF 1.21→1.68. 70%-body rule cut false signals 23%. Walk-forward single split, IS PF 1.66 / OOS 1.71 (n=291). No spread/slippage stated; 12 variants tested. — [Backtrex liquidity sweep](https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results)
- [RULE] Buy-side liquidity = buy stops resting above prior highs; sell-side liquidity = sell stops below prior lows. A sweep "looks like a breakout that quickly reverts"; wait for the book to refill before trusting direction. — [B2Broker ICT liquidity](https://b2broker.com/news/buy-side-liquidity-and-sell-side-liquidity-in-ict-trading-how-does-it-work)
- [RULE] Turtle Soup (Connors & Raschke 1995), the pre-ICT formalisation of sweep-and-reclaim: new 20-day low whose prior 20-day low is ≥4 sessions old; buy-stop back above the prior low (trade exists only on reclaim); stop below the new extreme. "Plus One" allows the reclaim the next session. No stats published. — [LuxAlgo Turtle Soup](https://www.luxalgo.com/library/concept/turtle-soup.md)

### Wyckoff spring / upthrust / test
- [RULE] Spring = undercut of range support that finds little follow-through selling and re-enters the range "within a few bars"; it runs stops under the lows; final phase-C test before SOS. Terminal shakeout = deeper, more violent undercut on heavier volume. **Test** = quiet pullback holding above the spring low on lighter volume than the spring; "a close back below the spring low cancels the read." Spring vs breakdown is decided by recovery: an undercut that keeps falling "was simply a breakdown." Upthrust = mirror at distribution tops. No numeric penetration or volume thresholds published. — [LuxAlgo spring](https://www.luxalgo.com/library/concept/spring.md); [LuxAlgo Wyckoff method](https://www.luxalgo.com/library/concept/wyckoff-method.md)
- [RULE] SOS requires widening spread and expanding volume out of the range; a range break on narrow spread and shrinking volume is a trap. Secondary tests come on progressively lighter volume. — [LuxAlgo Wyckoff method](https://www.luxalgo.com/library/concept/wyckoff-method.md)

### Market / Volume Profile
- [RULE] Value Area = band enclosing 70% of volume/TPOs, grown outward from the POC by adding the heavier adjacent side; 70% approximates one SD (68%). VAH/VAL can differ slightly between tools (single vs paired steps, tie-breaks). Fade VAH/VAL toward POC only while balanced; stop fading once accepted beyond. — [LuxAlgo value area](https://www.luxalgo.com/library/concept/value-area.md)
- [RULE] HVN = acceptance; price slows/consolidates; support from above, resistance from below; pullback to HVN in a trend may precede continuation. LVN = rejection; price moves through quickly; "weaker S/R than HVNs"; a continued move through an LVN tends to run to the next HVN. — [TradeZella volume profile](https://www.tradezella.com/learning-items/volume-profile)
- [PRAC] Naked (virgin) POC = untouched POC of a finished session; "documented tendency, though not an obligation, to return"; no reliable timetable, no dependable fill rate; weight high-volume sessions and move-origin sessions most; a trade-through "retires" it. — [LuxAlgo naked POC as level](https://www.luxalgo.com/library/concept/naked-poc-as-level.md)
- [RULE] Initial Balance = first hour (two 30-min TPO periods); IBR = IBH − IBL; extension targets at IBH + k·IBR, k ∈ {0.5, 1, 1.5, 2}. Day types: normal ≈ barely extends; normal variation ≈ doubles IB; trend day keeps extending. Narrow IB → easier to extend; wide IB → tends to hold. "No dependable universal statistics exist." — [LuxAlgo initial balance](https://www.luxalgo.com/library/concept/initial-balance.md)
- [RULE] Open types (Dalton/Steidlmayer): Open-Drive (one-sided from first prints, never back through the open; highest conviction; the open becomes a level that must not be revisited), Open-Test-Drive (probes a reference, fails, drives the other way; the probe extreme is a strong level), Open-Rejection-Reverse (early drive fails and returns through the open; two-sided day), Open-Auction (rotates around the open; lowest conviction; in-range = balance day). Open location: inside prior VA → rotation; outside prior range → must gain acceptance or snap back; out-of-range drive = strongest continuation read. Classify ~30 min after open. — [LuxAlgo open types](https://www.luxalgo.com/library/concept/open-types.md); [Marketcalls open type & confidence (NIFTY trader)](https://www.marketcalls.in/market-profile/market-profile-open-type-and-confidence.html)
- [PRAC/STAT-caveat] 80% rule: open outside prior VA, re-enter and hold two consecutive 30-min periods → target opposite VA edge, prior POC as interim. "A rule-of-thumb label rather than a rigorously audited statistic"; published tests show completion rates that "differ widely… and are often below 80%"; stalls at prior POC are common. — [LuxAlgo 80% rule](https://www.luxalgo.com/library/concept/80-percent-rule.md)

### Prior day/week levels, opening range, gaps
- [STAT, vendor, 6-month window, YM] When the previous day's high is broken, the session closes green 67% (open-to-close) / 81% (prev-close-to-close); PDL broken → red 62% / 66%; closes *beyond* the broken level 56% both sides; Friday 89%/77%. Author's conclusion: PDH/PDL breaks are **continuation/bias** information, not reversal levels. No n or method beyond the window. — [edgeful PD range mistake](https://www.edgeful.com/blog/posts/previous-days-range-trading-mistake); [edgeful PD range report](https://www.edgeful.com/blog/posts/previous-days-range-report)
- [STAT, peer-review-track WP] Zarattini & Aziz (SSRN 4416622), QQQ 2016–Feb 2023: 5-min ORB, direction of first candle, stop at the other side, 10R target or close, 4x leverage, 1% risk. Reported high returns but with **no spread or slippage**. — [SSRN](https://papers.ssrn.com/abstract=4416622); [CXO summary](https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy)
- [STAT] Replication on NQ/SPX/Dow/DAX/FTSE CFDs 2015–Jun 2026 (~2,900 sessions each): gross +0.05 to +0.13 R/trade, hit rate 20–23%, 10R hits 2–4%; **net of spread+slippage no market distinguishable from zero** (NQ +0.002R, others negative). First-candle direction beats a random direction by ~0.1R, about the size of the round-trip cost. 2015–17 negative everywhere. — [MQL5 ORB replication](https://www.mql5.com/en/blogs/post/776235)
- [PRAC] NIFTY/BANKNIFTY 15-min ORB as taught locally: 09:15–09:30 range, enter on a 15m/5m *close* beyond it ("not a fleeting wick poke"), stop other side, target 1.5–2× range or trail to 15:15, one trade per direction; skip abnormally narrow/wide ranges, RBI/Budget/Fed days; expiry-day pinning chops the index. No stats. — [onetradejournal 15-min ORB](https://onetradejournal.com/strategies/fifteen-minute-orb-strategy)
- [PRAC, "illustrative ranges"] NIFTY same-day gap fill: <0.3% gap ≈ 80–90% (usually first hour); 0.3–0.6% ≈ 65–75%; 0.6–1.2% ≈ 45–60%; >1.2% ≈ 25–40%; gap-downs fill slightly more often. Source, years and n not given. — [onetradejournal gap fill](https://onetradejournal.com/strategies/gap-fill-strategy)
- [STAT, retail, 13 yrs] A TradingQnA user's NIFTY count for gaps **>0.8%**: 44% of gap-ups and 24% of gap-downs filled the same day (contradicts the direction claim above; spreadsheet private). — [TradingQnA](https://tradingqna.com/t/gap-filling-statistics/151053)
- [PRAC] Bulkowski: a rising-window gap "will support price just 20% of the time" (i.e., gaps usually get filled through). — [ThePatternSite S&R](https://thepatternsite.com/SAR.html)

### NIFTY session facts
- [STAT] NIFTY futures 1-min data 2011–Aug 2018 (Singh & Gangwar, MPRA 89689): hourly-scaled volatility highest 09:15–10:00 (0.350%), lowest 11:00–12:00 (0.225%), 14:00–15:00 (0.285%) above 15:00–15:30 (0.280%); Friday most volatile; volatility halved 2011→2018. — [MPRA 89689](https://mpra.ub.uni-muenchen.de/89689/1/MPRA_paper_89689.pdf)
- [STAT] IIM Bangalore (2010), NIFTY 2006–10: significantly higher volume and volatility on expiry days; stock pinning near strikes exists in India (81–91% confidence), with intraday drift toward the strike near the close; **no max-pain effect found**. — [IIMB repository](https://repository.iimb.ac.in/handle/2074/21032?mode=full)

---

## Zone taxonomy table

| Type | How to draw (15m, closed bars) | Width | What makes it strong | Evidence grade & source |
|---|---|---|---|---|
| Seiden demand/supply (origin zone) | Base of 1–3 tight bars before ≥3-bar departure that breaks structure; proximal = base body edge nearest price, distal = base extreme | Base range, cap ≤1.5 MR (use bodies if wider) | Short tight base, fast one-sided departure, 0–1 prior tests, HTF agreement, room to next opposing zone | [RULE] crosstrade, LuxAlgo; [PRAC] 60–70% claim unsourced |
| ICT order block | Last opposite-colour candle before a displacement leg that breaks structure; prefer with FVG inside | That candle's range (often ≈1 MR) | Displacement (body ≥70% of range), BOS, contained FVG, first mitigation, HTF bias | [RULE] AlphaEx; [STAT-vendor] standalone OB fails 56.9% (FXNX) |
| Breaker block | A failed OB: price swept a prior swing, then displaced through the *opposite* swing, closing through the OB's whole body; trade the return from the other side | Original OB range | Real sweep + displacement + first retest; plain S/R flip without these is weakest | [RULE] MQL5/Backtrex; [STAT-vendor] 54–57% WR, n=64–87 |
| Fair value gap | 3-candle imbalance: c1.high < c3.low (bullish) / c1.low > c3.high (bearish); midpoint ("CE") as entry | Gap height | Formed by displacement off a sweep; unmitigated; aligned with HTF | [RULE] edgeful; [STAT-vendor] 64.8% mitigated within 48h EURUSD (FXNX) |
| Liquidity pool (swing / equal H-L) | Confirmed pivot; "equal" = ≥2 pivots within ≤0.15 MR, ≥5 bars apart; pool sits just beyond | Band from extreme to +0.5 MR beyond | Obviousness (many watchers), HTF pivot, round number or PDH/PDL co-located | [STAT] Osler stops cluster beyond levels; [STAT-vendor] sweep follow-through 58.2% |
| Sweep-and-reclaim (spring/upthrust/Turtle Soup) | Bar trades 0.1–1 MR beyond the pool, closes back inside (or next 1–2 bars do); test holds above sweep low | Sweep extreme to reclaim level | Fast recovery (few bars), low follow-through, quiet test, prior pool was ≥4 sessions old (Raschke) | [RULE] Wyckoff/LuxAlgo, Connors-Raschke; [STAT-vendor] confirmation lifts WR 42→59% |
| Role-reversal (polarity) level | Prior swing broken by a close ≥0.5 MR beyond, retested from the other side within ~2 sessions | ±0.25 MR line | Shallow retest that holds (Bulkowski throwback data in note 1) | [PRAC-large-sample] Bulkowski; ranked weakest flip type by SMC authors |
| PDH / PDL / PDC, PWH / PWL | From completed sessions only | ±0.25 MR | A sweep-and-reclaim at it; or clean acceptance beyond (then it is trend info, not a fade) | [STAT-vendor] break → continuation 56–67% (edgeful, YM) |
| Opening range (09:15–09:30 / IB 09:15–10:15) | High/low of first 15m bar or first hour | Range itself; extensions at ±0.5/1/1.5/2 × IBR | Narrow IB extends more; open type (drive vs auction); open location vs prior VA | [STAT] ORB gross edge, ~0 net (MQL5 replication); [RULE] open types |
| Volume/TPO profile: POC, VAH/VAL | Build from prior session(s); VA = 70% around POC | POC ±0.25 MR; VA edges as lines | Naked POC from a high-volume or move-origin session; VA edge agreeing with a Seiden zone | [RULE/PRAC] LuxAlgo, TradeZella; 80% rule "often below 80%" |
| HVN / LVN | Histogram peaks / troughs of composite profile (≥3–5 sessions) | HVN = node width; LVN = trough | HVN = acceptance/magnet (pullback target); LVN = fast transit, weak S/R | [PRAC] TradeZella; [RULE] Market Profile single prints |
| Round numbers (100 / 500 / 1000) | Fixed grid | ±0.2–0.3 MR | 1000s > 500s > 100s; TP reaction *at*, stop cascade *beyond* | [STAT] Osler (note 1); index evidence mixed |

---

## Codable definitions (additions to the earlier MR rule set)

```
# Displacement candle (SMC) — reused as Seiden "departure strength"
displacement(bar) := body/range >= 0.70 and range >= 1.5*MR and closes in outer 25%
departure(base)   := within 3 bars after base: >= 2 displacement bars OR net move >= 2*MR, AND nearest prior swing broken (BOS)

# Order block / origin zone
OB := last bar of opposite colour immediately before the departure leg
zone_hi/lo := OB high/low (wick convention) or OB body (body convention) — fix one convention
fvg_inside := exists i in departure leg with bar[i-1].high < bar[i+1].low (bullish)  # strength flag

# Breaker (role-reversal with sweep + displacement)
breaker := OB whose entire body was closed through by a leg that (a) first swept a prior swing
           (low[t] < swing_low - 0.1*MR then close back above within 2 bars) and
           (b) displaced through the opposite swing (BOS). Trade side = opposite of OB's original side.

# Liquidity pool & sweep
pool     := confirmed pivot (k=2..3) | equal pivots (|p1-p2| <= 0.15*MR, >= 5 bars apart) | PDH/PDL | round number
sweep    := extreme beyond pool by 0.1..1.0*MR and close back inside (same bar or within 2 bars)
reclaim  := close past sweep bar midpoint within 3 bars; micro-BOS on 5m is the strong version
accept   := >= 2 consecutive closes >= 0.5*MR beyond pool  -> NOT a sweep; treat as trend info
spring_test := after sweep, a pullback low >= sweep_low and (if futures vol available) vol < sweep vol

# Freshness / touch quality
touch_i      := bar whose extreme enters [zone_lo, zone_hi]
reaction_i   := max excursion away from zone within 3 bars after touch_i, in MR
touch_score  := sum over touches of (+1 if reaction_i >= 1 MR else -1); fresh zone starts at +1
mitigated    := any close beyond distal edge by >= 0.25*MR  -> retire zone (becomes breaker candidate)

# Profile references (from 1-5m bars, TPO or futures volume)
POC_prev, VAH_prev, VAL_prev := prior RTH session 70% area; naked_POC := POC_prev not touched since
IB := high/low 09:15–10:15; IBR := IBH - IBL; ext_k := IBH + k*IBR, IBL - k*IBR, k in {0.5,1,1.5,2}
open_location := inside_VA | outside_VA_inside_range | outside_range
open_type (classify at 09:45 close) := drive | test_drive | rejection_reverse | auction

# Zone width guard (R:R protection)
if (zone_hi - zone_lo) > 1.5*MR: shrink to body range; if still > 1.5*MR: reject zone
```

---

## Ranking evidence (confluence scoring, with what each weight rests on)

| Factor | Direction | Evidence | Suggested weight |
|---|---|---|---|
| Co-located stop pool (swing/equal lows, PDL, round number) **and** a sweep-and-reclaim has already printed | + | [STAT] Osler order clustering; [STAT-vendor] sweep confirmation 42→59% WR, follow-through 58% | 3 (the only mechanism-backed factor) |
| Origin zone formed by displacement + BOS (not a mere pause) | + | [RULE] all schools; [STAT-vendor] OB without FVG/displacement fails 57% | 2 |
| Confluence with independent level type (Profile VAL/POC, PWH/PWL, channel) | + | [PRAC] Seiden/LuxAlgo; [STAT-vendor] breaker PF <1.2 without aligned FVG | 2 |
| HTF (60m/daily) trend and zone agreement; context gate (no demand just under HTF supply) | + / veto | [PRAC] Seiden "big picture"; [STAT-vendor] HTF bias +12–18pp WR (FXNX) | 2, veto if opposed |
| Freshness: 0–1 prior tests | + | [PRAC] Seiden/SMC; **conflicts** with [STAT] touch-count findings at seconds-minutes scale | 1, but use touch_score (reaction-weighted) not count |
| Recency: zone/level age ≤ ~5 sessions | + | [STAT] Chung & Bellotti time decay; Osler 5-day persistence | 1 |
| Room to next opposing zone ≥ 3× distance to invalidation ("profit zone") | + / veto | [PRAC] Seiden; trader's own 1:3 rule | veto below 1:3 |
| Session timing: avoid first 30 min for *entries* (highest volatility, open-type unknown); 11:00–12:00 is calmest | context | [STAT] MPRA 89689; [STAT-vendor] killzone filters +6pp WR in FX | 0–1 |
| Expiry day of the traded index | − | [STAT] IIMB expiry volume/volatility; [PRAC] pinning chop | −1 or skip |
| Analyst/vendor "strength" labels, Fib ratio alone | 0 | [STAT] Osler: firm strength ratings not predictive; Fib not special (note 2) | 0 |

Scoring guidance: require ≥6 of a possible ~11 and no veto; a sweep-and-reclaim or rejection **close** is a trigger, not a score item. Fit the sign and size of the freshness weight on NIFTY data before trusting it (see Gaps).

Why "fresh vs tested" conflicts and how to code around it: Garzarelli/Chung-Bellotti count *bounces* (price entered the zone and left the same side) at 45 s–1 min scales — each counted touch is by construction a successful reaction, so more touches = more proven. Seiden/SMC count *visits* at swing scale regardless of outcome and argue orders get consumed. Both are consistent with: **a zone that keeps producing ≥1 MR reactions is strengthening; a zone whose reactions shrink on successive visits is being absorbed.** Hence `touch_score` above.

---

## Pitfalls

- **Vendor backtests are the only numbers for SMC concepts.** Backtrex, FXNX and edgeful all: sell a product, omit spread/slippage, pick filters after testing, and report small or undisclosed n. Treat their 53–59% as an upper bound for confirmed setups, and their 38–48% raw figures as the honest base rate for "touch the zone and enter".
- **ORB and PDH/PDL are continuation levels on index futures.** Fading them without a sweep-and-reclaim fights the measured bias (edgeful 56–67% continuation; ORB gross edge in the break direction). For a pullback seller this means: a clean break of PDL during an uptrend's correction is a reversal warning, not a dip to sell puts into.
- **Gross-vs-net.** The ORB edge of ~0.1 R/trade disappears under realistic costs; NIFTY option spreads carry wider effective costs than index CFDs. Any zone edge of similar size will not survive as a standalone rule; it must improve strike placement, not generate the trade.
- **Lookahead in every SMC definition.** OBs, FVGs, BOS and pivots are all known only after later bars close; a "fresh" label must be computed as of the evaluation bar. Backtrex explicitly uses `close[1]` and claims current-bar evaluation inflates WR 15–30 pp (unverified, but the direction is certain).
- **Width inflation.** Wick-drawn zones plus merged overlapping zones can exceed 2 MR on NIFTY 15m, which makes a 1:3 R:R arithmetically impossible with a stop beyond the distal edge. Cap at 1.5 MR or reject.
- **Profile conventions move the levels.** VAH/VAL/POC differ by tool (step rule, TPO vs volume, RTH vs all-hours). NIFTY spot has no volume: build TPO from 5m bars, or use NIFTY futures volume consistently; never mix.
- **Gap-fill folklore is contradictory.** Local sources quote 80–90% same-day fills for small gaps; a 13-year retail count found 44%/24% for gaps >0.8%. Neither is verifiable; the size-dependence is the only robust part.
- **Expiry days.** Higher volume/volatility and strike drift are measured; max-pain is not. Do not model the index as pinning to max pain.
- **Role-reversal without sweep/displacement is the weakest flip** per the SMC authors themselves; Bulkowski's throwback data (note 1) says a *deep* retest through the level weakens follow-through. Require a shallow hold.
- **Analyst and indicator "strength" labels have zero measured value** (Osler); do not let a vision LLM's verbal confidence substitute for the scoring table.

---

## Gaps

- No peer-reviewed or independently audited test exists for: order blocks, breaker blocks, FVG mitigation as a trading edge, Seiden odds enhancers, Wyckoff springs, naked POC revisits, the 80% rule, IB-multiple day types, or "fresh vs tested" zone performance. Everything above the [STAT] line for these is vendor or practitioner material.
- No NIFTY-specific measurement found for: PDH/PDL continuation rates, sweep-and-reclaim outcomes, zone-touch reaction statistics, value-area completion rates, or FVG fill rates. edgeful covers US futures/FX only; the IIMB and MPRA papers cover expiry effects and hourly volatility, not levels.
- No source gives an empirically derived zone width (ATR multiple) or an optimal displacement threshold; the 70%-body and 1.5 MR figures are practitioner conventions carried over from the earlier notes.
- Primary texts not retrieved: Dalton *Mind over Markets* / CBOT Market Profile handbook (only secondary glossaries), Pruden's three spring types (only the two-label spring/terminal-shakeout version was found), ICT's own definitions (only third-party restatements).
- Gap-fill statistics for NIFTY remain unverified and mutually inconsistent; the earlier `Gap trading/` notes should be checked before any gap rule is coded.
- Zarattini & Aziz's full results (returns, Sharpe) sit behind a paywall summary; only the replication's gross/net R figures were readable.

---

## Sources (all accessed 2026-10-09)
- crosstrade.io — Supply and demand zones — https://crosstrade.io/learn/price-action/supply-and-demand-zones
- LuxAlgo — Zone scoring & refinement — https://www.luxalgo.com/library/concept/zone-scoring-and-refinement.md
- LuxAlgo — ATR-based S/R zones — https://www.luxalgo.com/library/indicator/oY7rfzuc-atr-based-support-and-resistance-zones/
- AlphaEx Capital — Order blocks explained: what is actually proven — https://www.alphaexcapital.com/smart-money-concepts/order-blocks-explained
- MQL5 blog — Breaker blocks: three conditions — https://www.mql5.com/en/blogs/post/773691
- Backtrex — ICT breaker block guide & backtest — https://backtrex.com/en/blog/ict-breaker-block-trading-guide
- Backtrex — Liquidity sweep strategy 5-year backtest — https://backtrex.com/en/blog/liquidity-sweep-strategy-backtest-results
- FXNX — Do Smart Money Concepts work? backtest evidence — https://fxnx.com/en/blog/smart-money-concepts-work-backtest-evidence
- edgeful — Fair value gaps report — https://www.edgeful.com/blog/posts/fair-value-gaps-report
- edgeful — Previous day's range report — https://www.edgeful.com/blog/posts/previous-days-range-report
- edgeful — Previous day's range trading mistake (stats) — https://www.edgeful.com/blog/posts/previous-days-range-trading-mistake
- B2Broker — Buy-side / sell-side liquidity in ICT — https://b2broker.com/news/buy-side-liquidity-and-sell-side-liquidity-in-ict-trading-how-does-it-work
- LuxAlgo — Turtle Soup — https://www.luxalgo.com/library/concept/turtle-soup.md
- LuxAlgo — Spring — https://www.luxalgo.com/library/concept/spring.md
- LuxAlgo — Wyckoff method — https://www.luxalgo.com/library/concept/wyckoff-method.md
- LuxAlgo — Value area — https://www.luxalgo.com/library/concept/value-area.md
- LuxAlgo — Naked POC as level — https://www.luxalgo.com/library/concept/naked-poc-as-level.md
- LuxAlgo — Initial balance — https://www.luxalgo.com/library/concept/initial-balance.md
- LuxAlgo — Open types — https://www.luxalgo.com/library/concept/open-types.md
- LuxAlgo — 80% rule — https://www.luxalgo.com/library/concept/80-percent-rule.md
- TradeZella — Volume profile — https://www.tradezella.com/learning-items/volume-profile
- Marketcalls — Market Profile open type and confidence — https://www.marketcalls.in/market-profile/market-profile-open-type-and-confidence.html
- Zarattini & Aziz — Can Day Trading Really Be Profitable? (SSRN 4416622) — https://papers.ssrn.com/abstract=4416622
- CXO Advisory — ORB study summary — https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy
- MQL5 blog — ORB replicated on five indices: gross reproduced, net zero — https://www.mql5.com/en/blogs/post/776235
- onetradejournal — 15-minute ORB for Nifty/Bank Nifty — https://onetradejournal.com/strategies/fifteen-minute-orb-strategy
- onetradejournal — Gap fill strategy odds — https://onetradejournal.com/strategies/gap-fill-strategy
- TradingQnA — Gap filling statistics thread — https://tradingqna.com/t/gap-filling-statistics/151053
- Bulkowski — Support and resistance — https://thepatternsite.com/SAR.html
- Singh & Gangwar (2018) — Temporal analysis of intraday volatility of Nifty futures, MPRA 89689 — https://mpra.ub.uni-muenchen.de/89689/1/MPRA_paper_89689.pdf
- IIM Bangalore (2010) — Expiration day effect on stock pinning and market volatility — https://repository.iimb.ac.in/handle/2074/21032?mode=full
- Earlier notes relied on for Osler, Garzarelli, Chung & Bellotti, Kavajecz & Odders-White, Seiden PDF, Bulkowski throwbacks: see the two files named in Scope.
