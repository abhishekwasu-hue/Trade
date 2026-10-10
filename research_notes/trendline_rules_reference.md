# Trendline drawing rules: sourced reference (for Layer 5)

Scope: how practitioners and the one large statistical study define, draw, validate and trade trendlines. Tags: **[RULE]** precise enough to code; **[STAT]** measured result; **[PRAC]** practitioner judgement.

## 1. Which points to connect

- **[RULE] Sperandeo (Trader Vic, via Penn / RoboForex):** one primary trend line per trend. Downtrend: connect the **highest high** of the trend to the **lowest minor high that precedes the lowest low**, "without the line passing through prices between those two points", then extend it. Uptrend: lowest low to the highest minor low preceding the highest high. If the line cuts through price, move the second point to the next closer minor high/low. — [Penn, Traders.com](https://technical.traders.com/tradersonline/display.asp?art=2456); [RoboForex summary](https://roboforex.com/blog/education/trading-like-sperandeo-1-2-3-reversal-and-2b-pattern/)
- **[RULE] DeMark TD lines:** connect the **two most recent TD points of the same level, right to left** (most recent first). A TD supply point = a high with lower highs/closes on both sides (level = number of bars each side); demand point mirrors. Lines update as new TD points form. — [LiteFinance: TD lines](https://www.litefinance.org/blog/for-professionals/td-lines-by-tom-demark/)
- **[PRAC] Murphy / StockCharts:** uptrend line along **successive reaction lows**; two points draw it, the third confirms; "the more points, the more validity"; evenly spaced touches are ideal; if the points don't line up, "it is best not to force the issue". — [Trend Lines (Murphy-style)](https://pgam.it.com/pages/academicinfo?id=11); [StockCharts: Murphy's 10 laws](https://chartschool.stockcharts.com/table-of-contents/overview/john-murphys-10-laws-of-technical-trading)
- **[PRAC] LuxAlgo:** "lower swing highs for a down trendline"; "prominent pivots beat minor wiggles"; decide once whether to draw on wicks, closes or bodies and keep it fixed; internal trendlines deliberately cut a few extremes to fit most of the action. — [LuxAlgo: Trendline](https://www.luxalgo.com/library/concept/trendline.md)
- **[STAT] Bulkowski:** draw the line along the minor lows (up) / minor highs (down) so a pierce signals a trend change; sample 3,172 up and 3,274 down trendlines, 1991–2021, bull markets. — [Bulkowski: up trendlines](https://thepatternsite.com/uptrendlines.html); [down trendlines](https://thepatternsite.com/trenddown.html)

## 2. What makes a line significant (quality)

- **[STAT] Bulkowski, up trendlines (break = first close below):**
  - Touch count: 3 touches −2.1%, 4 touches +2.0%, 7 touches +7.5% (n = 23) for the "buy 3rd touch, sell first close below" method, which overall "didn't work well" (win/loss 37%).
  - Length: longer than the 44-day median +2.9%; shorter −1.4%.
  - Slope: median 0.05; shallower +2%, steeper −0.7%. Ranking shallow > medium > steep.
  - Touch spacing: gaps over 12 days +2%; under 12 days −1%.
  - Inbound trend (slope of price into the line's start): best when nearly flat (−0.03 to +0.02).
  - After the break: average drop 13%; 30% of breaks fell ≤ 5%.
- **[STAT] Bulkowski, down trendlines (break = first close above):** median spacing 13 days, median length 48 days, median slope 0.05; shallow lines 56% vs steep 46%; flat inbound trend 56% vs 47%; falling volume along the line slightly better; the line's start was reached 77% of the time; **throwback 59% of the time** (5% in 9 days, then up 81% of the time after it completes). Measure rule: widest vertical gap between the last touch and the break × 56% (down) / 63% (up).
- **[PRAC] Murphy / Pring:** significance = length of time intact × number of tests; steep lines break easily and are redrawn flatter (**fan principle**); the break of the third fan line is the stronger trend-change signal; a broken line reverses role (support ⇄ resistance). — Murphy ch. 4 (summarised at [OptionsTradingIQ](https://optionstradingiq.com/john-murphy-technical-analysis/)); [LuxAlgo: Trendline](https://www.luxalgo.com/library/concept/trendline.md)
- **[PRAC] Scale:** Bulkowski and LuxAlgo recommend log scale for long lines; irrelevant for intraday NIFTY (daily range ≈ 1–2%), linear is fine.

## 3. Breaks and confirmation

- **[RULE] Bulkowski:** breakout = **first close** beyond the line. "Waiting to sell costs you money" (first close beat delayed exit).
- **[PRAC] Murphy:** filters against false breaks: 3% penetration (long-term), two-day rule (two consecutive closes beyond), or use closes when intraday extremes pierce. — Murphy ch. 4
- **[RULE] DeMark breakout qualifiers** (at least one must hold, else the break is ignored): (1) the bar before the break closed *against* the break direction (closed up before a downside break); (2) the break bar opens/closes beyond the line; (3) a projected value from the prior bar's close ± its range exceeds the line. Price target = perpendicular distance of the farthest extreme from the line, projected from the break. — [LiteFinance: TD lines](https://www.litefinance.org/blog/for-professionals/td-lines-by-tom-demark/)
- **[RULE] Sperandeo 1-2-3:** (1) trendline break; (2) failed retest of the trend extreme; (3) break of the point-2 swing. Only after (3) is the reversal "fully formed". The break alone is the first signal, not the entry. — [RoboForex](https://roboforex.com/blog/education/trading-like-sperandeo-1-2-3-reversal-and-2b-pattern/); [Penn](https://technical.traders.com/tradersonline/display.asp?art=2456)
- **[PRAC] LuxAlgo / Brooks:** "a break signals a change in pace, not necessarily a reversal"; the first trend-line break is usually followed by a test of the trend extreme. — [LuxAlgo: Trendline](https://www.luxalgo.com/library/concept/trendline.md); [Brooks forum: trend line vs channel line](https://brookstradingcourse.com/support-forum/16-channels/16a-s27-line-1-and-line-2-which-should-be-use-trend-line)

## 4. Channel lines and wedges

- **[PRAC] Brooks:** trend line = across the pullback extremes; **trend channel line** = parallel line through the intervening opposite extreme; an overshoot of the channel line followed by a reversal bar is a reversal setup; wedge = three pushes with converging lines. — [Brooks forum](https://brookstradingcourse.com/support-forum/16-channels/16a-s27-line-1-and-line-2-which-should-be-use-trend-line); [NexusFi: wedge reversals](https://nexusfi.com/a/strategies/wedge-reversals-price-action)
- **[PRAC] Elliott channeling (StockCharts):** impulse channels from wave starts/ends (0–2 parallel through 1, etc.); "no hard tendencies for corrective applications". — [StockCharts: EW guidelines](https://chartschool.stockcharts.com/table-of-contents/market-analysis/elliott-wave-analysis-articles/guidelines-for-applying-elliott-wave-theory)

## 5. What this means for the code (inferences, not source claims)

1. Two deterministic "named" lines per trend exist in the literature and should both be produced: the **Sperandeo primary line** (trend extreme → the correction top/bottom preceding the trend's latest extreme, not cutting price) and the **DeMark latest line** (two most recent same-degree correction tops/bottoms). Everything else is a fan line from the same origin.
2. Line quality is descriptive: shallower slope, wider touch spacing, longer life, flat inbound trend and more held touches all score up (Bulkowski). None of them is a gate; the third-touch-alone method had a 37% win/loss.
3. Breaks are judged on closes (Bulkowski, Murphy, DeMark); a throwback/retest happens ~59% of the time, so the first break is a note, not a decision. DeMark's qualifiers and Sperandeo's 1-2-3 are the structured "commitment" evidence the decision layer should read.
4. Internal lines (through bodies, ignoring one spike) are a legitimate variant when wicks distort; flag them as such.
