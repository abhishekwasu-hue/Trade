# 06 — RSI Divergence (Wilder → Cardwell → Brown) and Top-Down Context for a NIFTY 15m Pullback Seller

Scope: extends `Chart knowledge/structure_wyckoff_patterns_divergence.md` §4 (basic divergence rules, Bulkowski 1995–2010 test) and `Chart knowledge/session_expiry_mtf_theta.md` (U-shape session volatility, Elder triple screen, SEBI expiry rules, VIX-σ maths). Those facts are **not repeated**; this file adds the Cardwell/Brown framework, objective detection details, newer backtests, regime detection and how view/sentiment is layered on technicals.

Tags: **[RULE]** = definition/rule from a named source; **[STAT]** = empirical number; **[PRAC]** = practitioner convention, untested; **[INF]** = our inference for this system. Units: `R` = median true range of last 50 bars (15m); pivots = confirmed fractals (k bars each side), as in the earlier notes.

---

## Part 1 — RSI divergence

### 1.1 Takeaway
RSI divergence is a *condition* that momentum is thinning, not a trade signal. Wilder read it as a warning of a turn; Cardwell inverted the emphasis: inside a trend, **regular divergence is a continuation feature that usually produces only a correction**, while his positive/negative reversals (= "hidden divergence") point to **trend resumption**. The only large tests (Bulkowski, 19k samples daily; Backtrex DAX 4h, 10 years) show standalone divergence has a roughly 39–55% hit rate and a thin, regime-dependent edge. For this system the correct use is exactly what Cardwell describes: trend defined first (RSI range + price structure), then **hidden/positive-reversal divergence inside the pullback = evidence the correction is ending**, confirmed by a price trigger. Regular counter-trend divergence at the impulse extreme is a *risk flag* for the next pullback, never a fade.

### 1.2 Cited findings

**Wilder (1978)**
- [RULE] Wilder: divergence between RSI and price is "a very strong indication that a market turning point is imminent"; bearish = price new high, RSI lower high (fails to confirm). Failure swings are defined on RSI alone: above 70 or below 30, RSI makes an interim peak/trough ("fail point"), then breaks it. Example 76→72→77→<72. [Wikipedia RSI](https://en.wikipedia.org/wiki/Relative_strength_index); [LuxAlgo failure swing](https://www.luxalgo.com/library/concept/rsi-failure-swing.md)
- [RULE] Wilder's default length 14 with Wilder (RMA) smoothing; range rules assume this smoothing — SMA/EMA variants shift effective levels. [LuxAlgo range rules](https://www.luxalgo.com/library/concept/rsi-range-rules.md)

**Cardwell (range rules, reversals, divergence-as-continuation)**
- [RULE] Range rules: uptrend RSI ~40–80 (40 = support, 70 = strength not overbought); downtrend ~20–60 (60 = resistance, 30 not a buy). 40–60 cycling = transition/consolidation. A trend change shows as a **range shift**. [NexusFi Cardwell framework](https://nexusfi.com/a/concepts/cardwell-rsi-framework); [Wikipedia](https://en.wikipedia.org/wiki/Relative_strength_index)
- [RULE] Positive reversal (uptrend only): price higher low, RSI lower low → trend resumes. Negative reversal (downtrend only): price lower high, RSI higher high. Both are "evidence the main trend is about to resume". Cardwell: bearish divergence "is a sign confirming an uptrend"; divergence mostly produces a brief correction, not reversal. [Wikipedia](https://en.wikipedia.org/wiki/Relative_strength_index); [LuxAlgo Cardwell reversals](https://www.luxalgo.com/library/concept/cardwell-positive-negative-reversals.md)
- [RULE] Reversals typically form from mid-range (RSI 40–55 in bull), not from deep oversold. Price projection (heuristic): second higher low + (intervening swing high − price at first RSI low) = minimum objective. [LuxAlgo Cardwell reversals](https://www.luxalgo.com/library/concept/cardwell-positive-negative-reversals.md)
- [RULE] Trigger per NexusFi write-up: positive reversal is actionable when price breaks the swing high between the two lows; stop below second low; target prior swing high then new highs. Mirror for negative. [NexusFi](https://nexusfi.com/a/concepts/cardwell-rsi-framework)
- [RULE] Conflict rule: when a regular divergence and a Cardwell reversal both exist on the same chart, weight the reversal (aligns with trend). [LuxAlgo](https://www.luxalgo.com/library/concept/cardwell-positive-negative-reversals.md)
- [PRAC] Cardwell favoured RSI 9 for active intraday, 14 for swing; NexusFi notes a close below 40 (not a wick) is the bull-range warning. [NexusFi](https://nexusfi.com/a/concepts/cardwell-rsi-framework)
- [PRAC] Bull range: treat bearish divergence as a "continuation trap"; bear range: treat bullish divergence likewise; neutral zone (40–60 cycling): classic 70/30 range fades are valid. [NexusFi](https://nexusfi.com/a/concepts/cardwell-rsi-framework)
- [STAT] Weekly DXY example: RSI contained in 20–60 through a multi-year decline; shift to 40–80 range accompanied the bull phase. [Traders.com](https://technical.traders.com/tradersonline/display.asp?art=4866)

**Constance Brown (1999)**
- [RULE] Brown widened the zones: bull 40–90 (40–50 = pullback support), bear 10–60 (50–60 = rally resistance); 50 midline is the coarse divider. Range shift = RSI breaks and *holds* outside its prior containing range, then price structure gives way too. If neither side is clean → treat as rangebound, use 70/30. [LuxAlgo range rules](https://www.luxalgo.com/library/concept/rsi-range-rules.md)
- [PRAC] In a bull range "bearish divergences against the 40–50 support often fail. Hidden divergence, which points with the regime, tends to age better." Counter-regime divergence needs price confirmation. [LuxAlgo](https://www.luxalgo.com/library/concept/rsi-range-rules.md)

**Regular vs hidden, objective detection**
- [RULE] TradingView-style detector: pivots on **price** with left=5/right=5 bars; compare only pivot pairs 5–60 bars apart; RSI read at the price pivot bars; regular bull = lower low price / higher low RSI, hidden bull = higher low price / lower low RSI (mirror for bear). "Line-of-sight" validation: RSI must stay above (bull) / below (bear) the straight line joining the two RSI pivot values, else cancel. Signal only after `right` bars close → lag = right bars; live bars show tentative pivots that vanish. [TradingView divergence script](https://www.tradingview.com/script/nEZAp6ys/)
- [RULE] LuxAlgo optimizer: RSI pivots with left/right lookbacks, `Max Divergence Bars` window, entry the bar after confirmation; RSI period is the only parameter it optimises in-sample/out-of-sample. [LuxAlgo OOS optimizer](https://www.luxalgo.com/library/indicator/rsi-divergence-out-of-sample-optimizer/)
- [PRAC] Checklist: compare lows to lows / highs to highs; one price basis (closes *or* wicks); swings 5–30 bars apart; first swing stretched (<30 / >70) for regular divergence; must form at a meaningful level. Anchoring error (matching a price pivot to a mid-move RSI wiggle) is the main reason detectors disagree. [ChartingLens](https://chartinglens.com/blog/rsi-divergence-trading-guide); [LuxAlgo blog](https://www.luxalgo.com/blog/rsi-divergence-bullish-vs-bearish-signals/)
- [PRAC] Multi-timeframe: find divergence on the higher frame, wait for structure break on the lower one. [ChartingLens](https://chartinglens.com/blog/rsi-divergence-trading-guide)

**Empirical evidence**
- [STAT] Bulkowski (994 US stocks, 1995–2010, 19,294 extremes, daily): swings ≥8 days apart, pairs 3 weeks–2.5 months apart (1–2 months best). Only bullish divergence in bull markets beat the index (≈50–55% beat-rate from 2000; 45–48% from 1995). Bearish divergence did not produce larger drops. Including first-pivot RSI in 30–70 "hurts performance in nearly all categories". [Bulkowski test](https://www.thepatternsite.com/DivergenceTest.html); guidelines page: "reliable but not timely… price can take months to follow". [Bulkowski divergence](https://thepatternsite.com/divergence.html)
- [STAT] Backtrex, DAX 4h, Oct 2016–Oct 2026, RSI14, divergence within last 10 bars + location filter (longs only in lower half of 100-bar range, shorts upper half), 1.5% SL / 3% TP, closed-bar signals: 106 trades, **win rate 38.7%, PF 1.16, +16.5% total vs +136% B&H**, max DD −14% vs −42%, 8-trade losing streak, 2018 alone +14.7%. Edge concentrated in one regime; shorts against trend were the drag. [Backtrex](https://backtrex.com/en/backtests/rsi-divergence-dax)
- [STAT] Trading Heroes, EURUSD daily, ~16 yrs: RSI divergence 26 trades, 73% win, +12.8% total (low frequency, rules undisclosed). [Trading Heroes](https://www.tradingheroes.com/rsi-trading-strategy-results/)
- [STAT] Academic: no peer-reviewed test of divergence found. Ekman (Lund 2017) tested RSI thresholds (70/30, 60/40, 50) on 14 series incl. India 2000–16: "all indicators performed poorly"; developing-market equities had the best but inconclusive relative returns. Cites Schulmeister (2009): daily-data RSI/MA profitability declined over time, 30-minute data did not. [Ekman thesis](https://lup.lub.lu.se/luur/download?func=downloadFile&recordOId=8905915&fileOId=8905916)
- [PRAC] Failure mode consensus: "RSI can stay divergent for weeks while price keeps running"; shorting bearish divergence in bull markets is "the single most expensive signal"; "divergence cascades" (serial failed divergences before the real turn). Divergence on very short timeframes is mostly noise. [ChartingLens](https://chartinglens.com/blog/rsi-divergence-trading-guide); [LuxAlgo blog](https://www.luxalgo.com/blog/rsi-divergence-bullish-vs-bearish-signals/)
- [PRAC] RSI period: shorter (2–9) → more extremes/noise, longer (21+) → hugs 50; consistency matters more than exact number. Intraday guides suggest 7–9 for speed. [Macroption](https://macroption.com/rsi-period); [Bajaj Finserv](https://www.bajajfinserv.in/rsi-period-for-intraday)

### 1.3 Codable definitions

**A. Divergence detector on confirmed pivots (no repaint)** [INF, built from TradingView/LuxAlgo/Bulkowski rules]
```
params: k=3 (fractal strength, 15m), minGap=5, maxGap=60 bars, minPriceDiff=0.25R, minRsiDiff=3,
        basis='close' for RSI pivots, price pivot uses high/low of the bar
1. P_low[i] confirmed at bar i+k if low[i] < low[i±1..k]. Mirror for P_high.
2. rsi_at_pivot = RSI14 at bar i (same bar; do NOT search separate RSI pivots).
3. For latest confirmed low L2 and previous confirmed low L1 with minGap ≤ gap ≤ maxGap:
   regular_bull : price L2 < L1 − minPriceDiff  AND rsi L2 > rsi L1 + minRsiDiff
   hidden_bull  : price L2 > L1 + minPriceDiff  AND rsi L2 < rsi L1 − minRsiDiff   (= Cardwell positive reversal)
   (mirror for highs → regular_bear, hidden_bear/negative reversal)
4. line_clear: for every bar between L1 and L2, RSI must be ≥ the straight line joining rsi L1→L2 (bull); else reject.
5. Also reject if any intervening price bar closes below the line joining price L1→L2 (bull).
6. Emit at bar i+k with fields {type, L1, L2, gap, rsi1, rsi2, strength = |Δrsi|/|Δprice_R|}.
7. Grade (not trade): regular_* needs rsi1 ≤ 30 (bull) / ≥ 70 (bear) [Bulkowski]; hidden_* needs regime from B below.
```
**B. Cardwell/Brown range classifier** [INF from Cardwell/Brown rules]
```
window W = last 40 bars (≈ 1.5 sessions on 15m); use closes of RSI14.
bull_range  : min(RSI) ≥ 38 AND max(RSI) ≥ 65 AND every RSI trough ≥ 40 on a closing basis (allow 1 wick)
bear_range  : max(RSI) ≤ 62 AND min(RSI) ≤ 35 AND every RSI peak ≤ 60 on closing basis
neutral     : otherwise (RSI cycling 40–60, or mixed)
range_shift_warn (bull→bear): an RSI trough closes < 40 AND the following RSI peak < 60
range_shift_confirmed: warn AND price structure breaks (close below last confirmed HL)
Use: hidden_bull counts only in bull_range; regular_bull at range extreme counts only in neutral.
```
**C. Decision mapping for the pullback-seller** [INF]
- bull_range + hidden_bull (RSI trough 40–50 on wave C) + reversal candle → highest-grade bull-put context (Cardwell positive reversal; projection = minimum target for the impulse).
- bull_range + regular_bear at impulse high → do **not** fade; downgrade next bull-put (risk flag); require deeper pullback evidence.
- neutral + regular divergence at range edge → range-fade regime (bull put at lower edge / bear call at upper edge), see Part 2.
- bear_range + regular_bull → "continuation trap"; no bull put.

### 1.4 Pitfalls
- RSI pivot ≠ price pivot: picking the nearest RSI wiggle manufactures divergences; always read RSI at the price pivot bar (or require both pivots within ±1 bar).
- Unconfirmed pivots repaint; a detector that fires before `k` right bars close will show vanishing signals.
- Divergence persists in strong trends (serial/triple divergence); Cardwell's reading is that this *confirms* the trend.
- 30/70 filter from Bulkowski is daily-chart evidence; on 15m, regular divergence from inside 30–70 is even less informative.
- Bulkowski's optimal spacing (1–2 months daily) does not translate to bars; the 5–60 bar window is convention, untested on NIFTY.
- Mixed price basis (wick lows vs close lows) flips many borderline cases; fix one basis.

### 1.5 Gaps
- No NIFTY/intraday test of hidden divergence or Cardwell reversals exists; all evidence is daily US/EU or 4h DAX.
- No published optimal (k, minGap, maxGap, minRsiDiff) for 15m; must be fitted on NIFTY 15m with walk-forward.
- Cardwell's projection heuristic has no public accuracy study.
- Whether RSI9 vs RSI14 changes range boundaries on 15m is unmeasured.

---

## Part 2 — Context: top-down, regime, session, sentiment

### 2.1 Takeaway
Discretionary frameworks agree on a three-layer stack spaced 4–6×: the **higher frame vetoes** (bias, governing range, levels), the **middle frame confirms** the pullback path and the must-hold level, the **execution frame only triggers**. Brooks-type reading says markets are in some range 70–80% of the time and ~80% of range breakouts fail, so the first question is *range or trend*; in a range you fade edges (bull put at lower third, bear call at upper third), in a trend you buy pullbacks. Indian session structure (U-shape, 15:00–15:30 VWAP close, Tuesday expiry pin/manipulation) sets *when* a 15m signal is trustworthy. Sentiment (VIX, PCR, FII, breadth) has little short-horizon predictive power in the literature; its proper role for a seller is **premium/risk regime and sizing**, not direction.

### 2.2 Cited findings

**Top-down roles and ratios**
- [RULE] HTF (context): bias, trend, governing range boundaries, where price sits in it, prior-period highs/lows, untested zones. MTF: does trend agree / correct / contradict. LTF: trigger only when price is at an HTF level, stop behind local invalidation. HTF has **veto**, not one vote. Spacing 4–6× ("closer is redundant, wider leaves gaps"). [LuxAlgo top-down](https://www.luxalgo.com/library/concept/top-down-analysis.md)
- [RULE] NexusFi three-gate filter: Gate 1 daily bias = trade direction; Gate 2 pullback in a valid MTF zone and must-hold intact; Gate 3 structural reversal on LTF inside the zone. Stop goes beyond the **MTF must-hold**, not the LTF trigger low. Closing-basis rule: LTF wick through a level = noise, LTF close beyond = warning, MTF close beyond = exit. S/R is drawn on a chart 5–10× the trading timeframe. [NexusFi MTF workflow](https://nexusfi.com/a/platforms/multi-timeframe-analysis-workflow)
- [RULE] Mid-trade: LTF breaks but MTF intact → partial/tighten; MTF must-hold breaks → exit regardless of P&L; HTF trend breaks → flip bias. Sweep (fast reclaim) ≠ break (multiple closes beyond). Wait 30–45 min after major releases. [NexusFi](https://nexusfi.com/a/platforms/multi-timeframe-analysis-workflow)
- [PRAC] Common mistakes: fixing bias once in the morning and trading every signal; managing on a lower frame than entry; redrawing levels intraday; overriding Gate 1. [NexusFi](https://nexusfi.com/a/platforms/multi-timeframe-analysis-workflow)
- [INF] Mapping for this system: **Weekly** = market state and major areas only (does not change within a 2-day trade); **Daily** = bias + governing range + levels that define the short-strike "room"; **1H/75m** = impulse direction, must-hold (last HL/LH), pullback zone; **15m** = ABC completion, divergence, commitment candle. Hidden divergence on 1H inside a daily trend outranks a 15m divergence.

**Range vs trend regime**
- [RULE] Range = at least 2 swing highs in one zone and 2 swing lows in another; boundaries are zones; detection window ~20 bars; compression test `RH−RL ≤ k·ATR` or ≥p of n bars closing inside; `Mid=(RH+RL)/2`; range ends on a close beyond an edge (optionally a retest that holds outside). While active: fade edges toward mid/opposite edge, disable trend entries. [LuxAlgo trading range](https://www.luxalgo.com/library/concept/trading-range.md)
- [RULE/PRAC] Brooks-style: range = reversal more likely than continuation; identify by 2–3 touches per edge, heavy overlap, balanced bull/bear bars, no net HTF progress. Barb wire: 75–90% bar overlap with bar ranges < 0.25–0.5 ATR. Broad ranges 10–20 ATR. Buy lower third / sell upper third, avoid midpoint; failed-breakout entry after ≥5 bars in range. Second entries ≈80% vs ≈50% first test (anecdotal). [NexusFi trading-range strategies](https://nexusfi.com/a/strategies/trading-range-price-action-strategies)
- [STAT/PRAC] Brooks estimates ~80% of breakout attempts from ranges fail and markets are in some range 70–80% of time (directional, not measured). Range→trend transition: >5 bars held beyond old edge, first pullback holds above old range high, two consecutive closes beyond; cut size 50% during transition. [NexusFi](https://nexusfi.com/a/strategies/trading-range-price-action-strategies); [Brooks webinar](https://www.brookstradingcourse.com/es/?p=52424)
- [RULE] RSI-based regime cross-check (Brown): if RSI is neither in bull nor bear range, classify rangebound and use 70/30 at edges. [LuxAlgo range rules](https://www.luxalgo.com/library/concept/rsi-range-rules.md)

**Indian session structure (adds to session_expiry note)**
- [RULE] NSE closing price = VWAP of 15:00–15:30 trades (fallback: LTP); index close/F&O settlement follow the same last-30-min weighted logic, so premiums in the final 30 min on expiry track the running average rather than LTP (FINNIFTY example: index +40 pts 15:25–15:29, ATM CE moved ₹0.15→0.05). [EquitiesIndia](https://equitiesindia.com/glossary/closing-price-weighted-average); [TradingQnA](https://tradingqna.com/t/behaviour-of-options-on-the-day-of-expiry/164198)
- [PRAC] Expiry-day illustrative ATM decay (retail guide, unsourced): 09:15 ₹80–120 → 11:00 ₹50–80 → 13:00 ₹25–40 → 14:30 ₹5–15 → 15:15 ₹0–5; "70–80% of remaining value lost 13:00–15:00"; thin liquidity and sharp swings in the afternoon; +2% ELM on expiry shorts. [Sahi](https://www.sahi.com/blogs/how-to-trade-options-on-expiry-day)
- [STAT] Intraday time-series momentum (first 30 min predicts last 30 min) replicated in 12/16 developed indices 2005–17 (pooled coef 2.86, t=7.5), stronger in crises; **India excluded** as too illiquid for the dataset. [Li, Sakkas, Urquhart JFM 2022](https://reading-9.eprints-hosting.org/95566/1/Accepted-Version.pdf)
- [INF] For a 15m pullback seller: 09:15–09:45 bars set the day's early extreme but are noise-rich; 11:00–13:30 pullbacks are "quiet" (LPS-like) but low-information; 13:30+ (Europe open) and 14:30+ decide the day; a commitment candle at 14:30–15:00 that holds into the 15:00–15:30 VWAP window is the cleanest overnight entry (cf. overnight premium evidence in the session note).

**VIX, breadth, PCR, flows — "view + sentiment"**
- [STAT] India VIX (NVIX) vs NIFTY 2009–15: strong negative *contemporaneous* correlation, asymmetric (reacts more to negative returns), stronger when VIX already high; predictive power not established. [Investors' fear and stock returns, KTU](https://inzeko.ktu.lt/index.php/EE/article/view/14966)
- [PRAC] India VIX spends most time in 10–18 with sharp spikes (86 in Mar-2020, ~27–30 on 4 Jun 2024); IV Percentile (share of last 252 days with lower IV) preferred over IV Rank because one spike distorts rank. Seller thresholds: IVP > 60–70 rich (defined-risk spreads), 30–60 directional, < 20–30 cheap. [OneTradeJournal](https://onetradejournal.com/glossary/iv-percentile)
- [PRAC] VIX regime table for sellers: <11 thin premium; 11–14 theta-selling attractive, small ranges; 14–18 normal; 18–22 rich/higher risk; 22–30 stressed; >30 panic. Expected 1-day move ≈ VIX/16 %. Check implied vs realised; plan for post-event IV crush. [Multibagg](https://www.multibagg.ai/market-pulse/articles/india-vix-surge-nifty-premiums-cmshymh2m7mrh0zp7jv9mwx15)
- [PRAC] NIFTY PCR (OI-based preferred): <0.7 over-optimistic, 0.7–1.0 balanced, >1.0 cautious, >1.3 potentially oversold/contrarian bullish if price holds support; distorted near expiry; strike-level OI matters more than headline. [5paisa PCR](https://www.5paisa.com/blog/how-pcr-ratio-affects-nifty-movement)
- [STAT] US evidence: put-call ratios explain <1% of forward SPY return variance (best R² 0.006; trading rule 19% vs 50% B&H); survey of sentiment metrics (surveys, volume, breadth, Baker-Wurgler) finds "none to small" 1-month predictive power (R² 0.000–0.026; breadth 0.014 combined). [CXO put-call](https://www.cxoadvisory.com/sentiment-indicators/predictive-power-of-put-call-ratios); [CXO sentiment survey](https://www.cxoadvisory.com/sentiment-indicators/survey-of-research-on-investor-sentiment-metrics)
- [PRAC] Indian F&O desks read FII index-futures long/short ratio and OI shifts as positioning context (e.g. "FIIs least bullish since June", "long-short 5:2; retail building shorts") alongside price levels, i.e. as confirmation/size inputs, not triggers. [Business Standard](https://www.business-standard.com/markets/news/fiis-least-bullish-since-june-oi-in-nifty-futures-down-at-3-lakh-contracts-124101700137_1.html); [Business Standard](https://www.business-standard.com/amp/markets/news/f-o-insights-fiis-long-short-ratio-at-5-2-retail-traders-build-shorts-124083000108_1.html)
- [PRAC] Market internals as pullback evidence: positive TICK/breadth divergence during a pullback = selling exhausting; weak breadth on the structural shift lowers confidence; trend-day flag (TICK persistently beyond ±600) means pullbacks won't develop normally. [NexusFi MTF](https://nexusfi.com/a/platforms/multi-timeframe-analysis-workflow)

### 2.3 Codable definitions

**D. Regime detection (price-only, swing-based; RSI as cross-check)** [INF from LuxAlgo/Brooks/Brown]
```
on 1H (or 75m) confirmed pivots, window n=20 bars (≈3 sessions):
RH = max(high[n]), RL = min(low[n]), H = RH−RL in R_1H units
trend_up   : last 2 confirmed highs rising AND last 2 lows rising AND H ≥ 6R AND net progress (close−close[n])/H ≥ 0.5
trend_down : mirror
range      : ≥2 pivot highs within 0.5R of RH AND ≥2 pivot lows within 0.5R of RL AND |net progress|/H < 0.3
             AND ≥ 0.7·n bars close inside [RL,RH]
barbwire   : range AND median bar range < 0.5R  → no trade
transition : range ended by a close beyond edge; stays 'transition' until >5 bars held outside AND first pullback holds
             beyond old edge (then becomes trend). Size ×0.5 in transition.
rsi_check  : trend_up expects bull_range (B); range expects neutral; disagreement → downgrade one notch.
```
**E. Range-edge mapping for this system** [INF]
- `range` + price in lower third + regular_bull (RSI neutral regime) + 15m commitment candle → bull put, short strike ≤ RL − 1σ(2d) and below RL by ≥1R.
- `range` + upper third + regular_bear → bear call, mirror. Midpoint zone (±1R of Mid): no entry.
- `trend_up` + pullback into 1H zone + hidden_bull (bull_range) → bull put per Part 1.

**F. Context gates and sentiment weights** [INF; sentiment has weak evidence so it adjusts *size/width*, never direction]
```
Gate1 (daily bias) == trade direction, else skip.
Gate2 (1H must-hold intact: last HL (up) / LH (down) not closed through), else skip.
Gate3 (15m: ABC complete + divergence grade + commitment candle), else wait.
Weights (multiplicative on size, cap 0.5–1.0):
  VIX regime 11–18 → 1.0; 18–22 → 0.75 (widen strike +0.5σ); >22 → 0.5 or skip new entries; <11 → require Gate1&2 full + IVP check.
  VIX rising > +10% day-over-day during a bull-put pullback → ×0.75 (trend-day risk).
  Event within hold window (RBI, Budget, FOMC, US CPI) → ×0.5 or defer.
  Breadth/FII/PCR: only ±0.1 confidence nudges; PCR>1.3 with price at support supports bull put; never a gate.
Session: entries 09:15–09:45 ×0.5 (noise); 13:30–15:15 ×1.0; expiry-day (Tue) morning signals ×0.5, roll to next weekly.
```

### 2.4 Pitfalls
- Treating the weekly chart as a trade input; it only vets the regime and the farthest level.
- Confusing a pullback inside an HTF trend with a range (Brooks: flags are not ranges); check HTF net progress before fading.
- Taking fixed VIX/PCR thresholds as rules; they are retail conventions — the literature finds near-zero short-horizon predictive power for sentiment.
- Reading the last 30 minutes' LTP on expiry as the settlement reference; settlement follows the 15:00–15:30 weighted average.
- Ignoring that Indian weekly-expiry retail data (SEBI 91–93% losers) says the edge is structural (overnight VRP, discipline), not in sentiment reads.

### 2.5 Gaps
- No NIFTY-specific study of range-breakout failure rates or range duration on 1H/15m.
- Intraday momentum (first→last half hour) untested for NIFTY in peer-reviewed work; Indian retail write-ups are anecdotal.
- No quantified India VIX → pullback-depth or → divergence-reliability relationship; needs in-house measurement.
- FII flow / long-short ratio as a confidence input has no published out-of-sample test.
- Expiry-day ATM decay table is illustrative; real decay curve should be measured from Upstox tick data per VIX bucket.

---

## Sources (all accessed Oct 2026)
- Wikipedia, Relative strength index — https://en.wikipedia.org/wiki/Relative_strength_index
- LuxAlgo, RSI Failure Swing — https://www.luxalgo.com/library/concept/rsi-failure-swing.md
- LuxAlgo, RSI Range Rules — https://www.luxalgo.com/library/concept/rsi-range-rules.md
- LuxAlgo, Cardwell Positive/Negative Reversals — https://www.luxalgo.com/library/concept/cardwell-positive-negative-reversals.md
- NexusFi, The Cardwell RSI Framework — https://nexusfi.com/a/concepts/cardwell-rsi-framework
- Traders.com, RSI range rules on DXY — https://technical.traders.com/tradersonline/display.asp?art=4866
- TradingView, RSI Divergence (pivot-based, line-of-sight) — https://www.tradingview.com/script/nEZAp6ys/
- LuxAlgo, RSI Divergence Out-of-Sample Optimizer — https://www.luxalgo.com/library/indicator/rsi-divergence-out-of-sample-optimizer/
- LuxAlgo blog, RSI divergence bullish vs bearish — https://www.luxalgo.com/blog/rsi-divergence-bullish-vs-bearish-signals/
- ChartingLens, RSI Divergence Trading Guide — https://chartinglens.com/blog/rsi-divergence-trading-guide
- Bulkowski, Divergence Test — https://www.thepatternsite.com/DivergenceTest.html ; Divergence guidelines — https://thepatternsite.com/divergence.html
- Backtrex, RSI Divergence on DAX 4h (2016–2026) — https://backtrex.com/en/backtests/rsi-divergence-dax
- Trading Heroes, 3 RSI strategies backtested — https://www.tradingheroes.com/rsi-trading-strategy-results/
- Ekman (Lund 2017), Profitability of Technical Analysis Across Global Markets — https://lup.lub.lu.se/luur/download?func=downloadFile&recordOId=8905915&fileOId=8905916
- Macroption, RSI period — https://macroption.com/rsi-period ; Bajaj Finserv, RSI period for intraday — https://www.bajajfinserv.in/rsi-period-for-intraday
- LuxAlgo, Top-down Analysis — https://www.luxalgo.com/library/concept/top-down-analysis.md
- NexusFi, Multi-Timeframe Analysis Workflow — https://nexusfi.com/a/platforms/multi-timeframe-analysis-workflow
- LuxAlgo, Trading Range — https://www.luxalgo.com/library/concept/trading-range.md
- NexusFi, Trading Range Price Action Strategies — https://nexusfi.com/a/strategies/trading-range-price-action-strategies
- Brooks Trading Course, Strong legs in trading range vs trend — https://www.brookstradingcourse.com/es/?p=52424
- EquitiesIndia, Closing price weighted average — https://equitiesindia.com/glossary/closing-price-weighted-average
- TradingQnA, Behaviour of options on expiry day — https://tradingqna.com/t/behaviour-of-options-on-the-day-of-expiry/164198
- Sahi, How to trade options on expiry day — https://www.sahi.com/blogs/how-to-trade-options-on-expiry-day
- Li, Sakkas & Urquhart (JFM 2022), Intraday Time Series Momentum: Global Evidence — https://reading-9.eprints-hosting.org/95566/1/Accepted-Version.pdf
- Investors' fear and stock returns: NSE India (Engineering Economics, KTU) — https://inzeko.ktu.lt/index.php/EE/article/view/14966
- OneTradeJournal, Nifty IV Percentile — https://onetradejournal.com/glossary/iv-percentile
- Multibagg, India VIX surge and Nifty premiums — https://www.multibagg.ai/market-pulse/articles/india-vix-surge-nifty-premiums-cmshymh2m7mrh0zp7jv9mwx15
- 5paisa, How PCR affects Nifty — https://www.5paisa.com/blog/how-pcr-ratio-affects-nifty-movement
- CXO Advisory, Predictive power of put-call ratios — https://www.cxoadvisory.com/sentiment-indicators/predictive-power-of-put-call-ratios ; Survey of sentiment metrics — https://www.cxoadvisory.com/sentiment-indicators/survey-of-research-on-investor-sentiment-metrics
- Business Standard F&O insights — https://www.business-standard.com/markets/news/fiis-least-bullish-since-june-oi-in-nifty-futures-down-at-3-lakh-contracts-124101700137_1.html ; https://www.business-standard.com/amp/markets/news/f-o-insights-fiis-long-short-ratio-at-5-2-retail-traders-build-shorts-124083000108_1.html
