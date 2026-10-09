# 02 — Impulse vs correction legs, and detecting weakening momentum in a pullback

Scope: for a NIFTY options seller entering credit spreads at the end of a 15M pullback (ABC correction) in the direction of the prior impulse. Inputs available: OHLC of the index + NIFTY futures volume. This note **extends** `Leg and level strength research/impulse_vs_pullback.md` (Brooks glossary bar definitions, Wyckoff ChartSchool, LuxAlgo SMC/FVG code thresholds, Fibonacci study, Kaufman ER) and `Chart knowledge/structure_wyckoff_patterns_divergence.md` (Dow/Wyckoff/pattern/RSI rules with R-units). Material already covered there is referenced, not repeated.

Tags: **[RULE]** = a practitioner's stated definition or rule; **[STAT]** = a number from a study or a large-sample tabulation; **[PRAC]** = practitioner heuristic / rule of thumb without test evidence.

---

## Takeaway

1. Every school says the same thing in different words: an **impulse** is fast, one-sided, non-overlapping, closes near extremes and leaves gaps/imbalances; a **correction** is slow, overlapping, mixed-colour, narrow-range and (usually) lighter in volume. Brooks calls it spike vs channel/flag, Wyckoff calls it SOS vs LPS/reaction, Elliott calls it motive vs corrective (3s overlap, 5s don't), ICT calls it displacement vs retracement.
2. **Weakening momentum of the pullback itself** (what the trader wants before selling premium against it) is read as: shrinking counter-trend pushes (shortening of thrust), shrinking bar bodies/ranges, closes drifting away from the pullback extreme, counter-trend bars losing to with-trend bars, no counter-displacement/no new FVGs against the trend, volume fading on each counter push, and failure to make a meaningfully new pullback extreme on the last push (three-push / wedge-flag geometry).
3. **Weakening of the trend** (danger: the "pullback" may be a reversal) is the mirror: the pullback leg shows impulse character (displacement, consecutive strong closes, speed ≥ impulse speed, expanding volume), it retraces > ~62–79% or breaks the impulse origin, or it produces a CHoCH *with displacement*. Shortening of thrust on the *impulse* pushes before the pullback is the Wyckoff early warning that the next pullback may not hold.
4. Nearly every measurable here is **relative** (to the impulse, to the last few dozen bars, to the same time-of-day baseline). Sources are explicit that there are no canonical constants ("the threshold is a lens rather than a parameter with a correct setting"). Calibrate on NIFTY 15M.
5. Evidence base: "pullback volume is lower" is universal practitioner doctrine (Dow/Rhea, Wyckoff, Elliott, RVOL practice) but I found no peer-reviewed test of it; the hard volume facts are only that |return| and volume are positively related (Karpoff) and intraday volume/volatility are U-shaped, including NIFTY futures. Bulkowski's measured-move tabulation is the only large-sample statistic on retracement depth vs continuation, and it cuts against the "shallow = healthy" heuristic for *target completion*.

---

## Cited findings

### A. Al Brooks — spike vs channel, strength signs, two legs, wedges, climaxes

- [RULE] Spike definition (NexusFi/Brooks framework): "a run of at least five consecutive trend bars with small wicks, closes near the bar extreme, and each close at or beyond the prior close"; "strong spikes often run 7-12 bars"; a lone big bar or a 2–3 bar surge "is not a spike". Warning inside a spike: "A bull-bar close in the bottom half during a spike is a warning sign. Overlapping bodies signal that a transition is beginning." A true spike "cuts through" prior resistance rather than stalling. — [NexusFi: Spike and Channel](https://nexusfi.com/a/strategies/spike-and-channel-price-action)
- [RULE] Channel = trend continuing after spike momentum fades: "there are trend bars and counter-trend bars; the market is not a one-way street"; "the average body is visibly smaller"; consecutive bars overlap; pullbacks are regular enough that "you can draw a trendline that multiple pullbacks respect". — [NexusFi](https://nexusfi.com/a/strategies/spike-and-channel-price-action)
- [RULE] Spike-to-channel transition sequence: "the spike's largest bar, wicks appearing at the extreme, a first pullback of about 2-3 bars, a second push at a reduced angle, and a second pullback that confirms the channel." The channel start "often acts as a significant support level for days", and "A successful test of the channel start in a bull channel is often itself a high-quality pullback entry." — [NexusFi](https://nexusfi.com/a/strategies/spike-and-channel-price-action)
- [PRAC] Pullback-quality deterioration inside a channel: "When pullback bars are larger than trend bars, the internal balance has shifted." Channel pullback marker: counter-move of "2-3+ bars" with "at least two counter-trend bars", signal bar closing in upper half. Early channel → prefer H2; late channel → "only the clearest H2 at reduced size". — [NexusFi](https://nexusfi.com/a/strategies/spike-and-channel-price-action)
- [PRAC] Spike exception: do not enter during the spike unless the first pullback is "less than 30% of spike height" with a quality signal bar. Measured move: spike height H projected from the first pullback low; channel-width projection "most reliable when the channel has 4+ boundary touches"; in trading-range context measured moves "often fail". — [NexusFi](https://nexusfi.com/a/strategies/spike-and-channel-price-action)
- [RULE] Brooks glossary: Climax = "A move that has gone too far too fast and has now reversed direction to either a trading range or an opposite trend." Exhaustion gap (bull) = "Unusually big bull bar or bars late in a bull trend." Three pushes = "Three swing highs where each swing high is usually higher or three swing lows where each swing low is usually lower." Wedge flag = "A wedge-shaped or three-push pullback in a trend, such as a high 3 in a bull trend (a type of bull flag)". Micro channel = "A very tight channel where most of the bars have their highs and lows touching the trend line". Tight trading range = "two or more bars with lots of overlap in the bars and in which most reversals are too small". Reversal bar = "A trend bar in the opposite direction of the trend." — [Brooks glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/)
- [PRAC] Brooks (Reading Price Charts Bar by Bar, via summary) signs of a strong trend: "No Climaxes and not many large bars (not even large trend bars)"; "Bars with no tails or small tails in either direction"; "No significant trend channel line overshoots, and the minor ones result in only sideways corrections"; "The first minor pullback in a strong trend is a one- or two-bar pullback". Tendencies: "A climax is usually followed by a two-legged correction"; "All strong moves usually have at least two legs even if the second one falls short and reverses"; "Any time there is a trendline breakout, the chances are high that there will be a second leg"; strong trend bars followed by a pullback "almost always has a test of its extreme"; "Small bars after a climax almost always lead to a protracted move"; "In a trend, most reversal patterns fail and most continuation patterns succeed." Strength of a trendline break: "The move covers many points", "It lasts many bars (10 to 20 or so)". — [Brooks probabilities summary (SlideShare)](https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754)
- [PRAC] Wedge / three pushes (NexusFi, Brooks framework): "The first push is often the largest, with push two and three slightly smaller as momentum fades"; "The third push should show less momentum than the first" (smaller bars, contracting range, more overlap); exhaustion on push 3 = tails rejecting the extreme, overlapping bars, opposite-colour closes, "A bar that makes a new extreme but closes in the opposite half"; the third push "signals exhaustion through what it fails to do more than what it does." Wedge *flag* (a three-push pullback mid-trend) vs wedge *reversal* (at a trend extreme) is separated by context only. Failed wedge: price moves in the reversal direction "1-3 bars, then re-enters the wedge". — [NexusFi: Wedge Reversals](https://nexusfi.com/a/strategies/wedge-reversals-price-action)
- [RULE] Final flag (Brooks, quoted in forum): "A protracted trend often forms a horizontal flag that extends sideways for several bars, breaks a trendline"; "This Failed Final Flag breakout often marks the end of the trend and sometimes leads to a reversal"; the countertrend move "will have at least two legs"; the flag "often can be as simple as an ii pattern." — [NexusFi thread: final flag](https://nexusfi.com/traders-hideout/20752-al-brooks-definition-final-flag.html)
- [PRAC] Brooks-forum reading of a *dangerous* pullback (bear leg that flips always-in): "5 bear bars, 3 of which are decent, closing near their lows and 2 pretty big" → "The bear leg is strong enough to warrant a second leg sideways to down"; vs a harmless one whose follow-through was "mostly doji bars with tails" and "The market never clearly became AIS." "It is always about pressure and FT [follow-through]." — [Brooks forum: comparing pullbacks](https://www.brookstradingcourse.com/support-forum/13-always-in/comparing-pullbacks-in-bull-trend/)
- [PRAC] Open-source Brooks "trend bar" coding: "Bull trend bars (green body ≥50%, close ≥60% up range, larger than 1.5x average)"; bear mirror "body ≥50%, close ≤40%". — [TradingView: Price Action Trend Bar](https://jp.tradingview.com/script/yNsVp5rI-Price-Action-Trend-Bar)

### B. Wyckoff — effort vs result, shortening of thrust, wave volume, LPS/LPSY

- [RULE] Shortening of the Thrust (SOT): "each successive push to a new high or low gains less ground than the one before." Measure: at least three consecutive pushes to new extremes; "Measure each push's gain beyond the prior extreme: new high minus previous high, or previous low minus new low"; gains must shrink in order with the latest smallest. "SOT describes deceleration, not reversal." Reading depends on volume: "shortening on heavy volume is read as effort buying little progress because the other side is absorbing it"; "shortening on light volume is read as the trend's own participants withdrawing." Confirmation needs a change of character "such as a forceful move the other way on expanding volume". — [LuxAlgo: Shortening of the Thrust](https://www.luxalgo.com/library/concept/shortening-of-the-thrust/)
- [RULE] Effort vs result: "Volume is the effort; the price movement it produces is the result." Bar level: "heavy volume that yields only a narrow spread or little net progress means the effort is being met." Swing level: "Legs needing ever more volume to cover ever less ground mark a trend meeting opposition"; "easy travel on modest volume marks an unopposed one." Low-volume pullbacks that give back little = continuation. Without volume the law works "partially" — bar range and progress are a rough proxy, but absorption/climax reads need volume. Pitfalls: "Effort without result matters at a level and means little in the middle of nowhere"; "Result without effort can be bullish when it means the path is empty"; divergences "can persist". — [LuxAlgo: Effort vs Result](https://www.luxalgo.com/library/concept/effort-vs-result.md)
- [RULE] Wave (Weis) volume: accumulate volume per swing; compare each wave with earlier waves in the same direction on "price progress, time taken, and cumulative volume". "in a healthy uptrend, buying waves run longer and heavier than the selling waves between them." Pullback waves shrinking in volume = opposing side weakening; "enormous volume in a wave that covers little ground is the classic signature" of absorption. Swing threshold: "the threshold is a lens rather than a parameter with a correct setting"; "if columns flip on every minor wiggle the threshold is too small"; keep it fixed. — [LuxAlgo: Wyckoff Wave & Volume Studies](https://www.luxalgo.com/library/concept/wyckoff-wave-and-volume-studies.md)
- [RULE] LPS = "a quiet, shallow pullback after the strength shows"; spring/upthrust invalidated "when the break extends instead of snapping back into the range." (LPS/LPSY spread-volume signatures are already in the earlier note.) — [LuxAlgo: Wyckoff Method](https://www.luxalgo.com/library/concept/wyckoff-method.md)

### C. Elliott — wave personality, overlap, depth

- [PRAC] "Third waves tend to be strong and broad"; wave 3 "usually generates the most volume and price movement, and they are the most likely wave to extend." "Fifth waves tend to be less dynamic and display slower speed of price change than the previous waves", with lesser volume/breadth; in extended fifths divergence appears. Wave 2 "usually end on low volume and low volatility." Wave B: "It performs the task of enticing the suckers to jump into the market"; "B Waves tend to show lower volume." Wave C "tends to break the illusions of Wave A and Wave B"; in a decline "it can be devastating and fear takes over with broad participation." Depth guideline: corrections "often will correct to the territory of the previous Wave 4 of lesser degree." Alternation: "the forms for Wave 2 and Wave 4 will alternate" and "the forms for Wave A and Wave B will alternate". — [StockCharts: Guidelines for Applying Elliott Wave](https://chartschool.stockcharts.com/table-of-contents/market-analysis/elliott-wave-analysis-articles/guidelines-for-applying-elliott-wave-theory)
- [PRAC] "wave 3 usually the strongest, broadest move, wave 5 often narrower with fading momentum"; wave 5 "often advances on fading momentum with oscillator divergence"; "B waves within corrections prone to unconvincing rallies". Hard rules (not guidelines): wave 2 cannot retrace >100% of wave 1; wave 3 never shortest of 1/3/5; wave 4 does not enter wave 1 territory (diagonals excepted). — [LuxAlgo: Elliott Guidelines](https://www.luxalgo.com/library/concept/elliott-guidelines.md)
- [RULE] "corrective price action is typically overlapping and choppy" and swings "subdivide in threes"; zigzag = "sharp, subdividing 5-3-5", flat = "sideways, 3-3-5", triangle = "usually contracting, five legs of three each". Depth bands "roughly 0.382 to 0.618 of the prior wave, deeper for wave 2s and zigzags, shallower for wave 4s and flats"; wave 2 ≈ 0.5–0.618 of wave 1, wave 4 ≈ 0.236–0.382 of wave 3. Key reversal tell: a countertrend move that subdivides in five "forces the count to change" — "often the earliest structural warning that a trend is ending." "Confirm completion in hindsight, not in advance." — [LuxAlgo: Corrective Wave](https://www.luxalgo.com/library/concept/corrective-wave.md)
- [PRAC] Ending diagonals: wedge-shaped wave 5 (or C) with "internal ABC structure throughout", overlapping; a break against the wedge targets "where the wedge originated, or start of wave 4." Truncated fifth "is likely to follow an exhaustive wave 3." — [Nasdaq: Variations in Motive Waves](https://www.nasdaq.com/articles/ellliott-wave-basics-variations-motive-waves-2011-06-28)

### D. ICT / SMC — displacement, CISD, CHoCH

- [RULE] Displacement = "fast, one-sided move" of large bodies, "conspicuously larger-bodied than the last few dozen bars", that "cover in a handful of candles what the prior tape needed dozens to travel"; "long wicks say contested auction, not repricing"; FVGs are "the classic displacement residue". A break of structure with displacement is high-conviction; a slow drift through the same level is not. Reversal evidence = "Displacement in the opposite direction right after a liquidity sweep". FVGs/OBs created inside a displacement leg become pullback zones for continuation. Loose magnitude: a single large body or "a run of three to five strong closes". "If you have to squint, it probably is not displacement." Off-hours bursts "graded skeptically". — [LuxAlgo: Displacement](https://www.luxalgo.com/library/concept/displacement.md)
- [PRAC] Numeric displacement heuristics (educator site): body "at least 60% of the total range" (often "60 to 80 percent or more"); "Wicks should be under 20% of the candle's total range"; move "clearly faster than the average of the preceding candles"; FVG must "remain open"; a "Regular Impulse" has a 40–60% body and no meaningful FVG; "A valid MSS always requires a displacement" while a BOS "can form without pronounced displacement." — [Backtrex: ICT Displacement](https://backtrex.com/en/blog/ict-displacement-candle-market-concept)
- [RULE] CISD (change in state of delivery): "the opening price of the first candle in the last unbroken run of down-closing" candles into a low is the level; confirmation requires "a full body close through that level" — "a wick through the level does not count". It needs no swing break, so it "typically fires earlier and closer to the extreme" than an MSS; "a close delivered with displacement that leaves a fair value gap carries more weight than a drift through the level." — [LuxAlgo: Change in State of Delivery](https://www.luxalgo.com/library/concept/change-in-state-of-delivery.md)
- [RULE] CHoCH: "the earliest structural evidence that the trend's character is shifting"; strict convention breaks "the higher low that produced the trend's final high", looser conventions accept "any recent higher low, including internal ones". Filter: "A body close beyond it, ideally with displacement". Pullback-vs-reversal reality: "many CHoCHs resolve as deep pullbacks that never reverse the trend"; "Strong trends regularly break a minor higher low during a deep pullback and then continue, so a lone CHoCH fails often." Confirmation = a lower high after the break, then a with-trend BOS in the new direction. — [LuxAlgo: Change of Character](https://www.luxalgo.com/library/concept/change-of-character.md)

### E. Generic pullback heuristics and volume evidence

- [PRAC] Pullback holds "above the prior higher low"; "once price closes below the prior higher low, the move stops being a pullback and becomes a potential reversal." Depth heuristic 38.2–61.8% "normal", deeper "suspect" (explicitly a heuristic). "shallow, slow, quiet dips lean toward continuation"; expanding counter-move volume is "a warning of distribution"; pullback ranges "smaller ... than the move being corrected"; pullback and reversal are "indistinguishable in their early bars"; "none of them is decisive in real time". A pullback is confirmed when price closes back in trend direction or breaks the small counter-trend swing. — [LuxAlgo: Pullback](https://www.luxalgo.com/library/concept/pullback.md)
- [PRAC] Dow/Rhea: "Volume should expand in the direction of the trend"; "volume tends to expand on advances and contract on pullbacks"; secondary reactions "often described as retracing one-third to two-thirds of the prior leg"; reversal signal = "a failure to print a new high followed by a close below the prior swing low." — [LuxAlgo: Dow Theory](https://www.luxalgo.com/library/concept/dow-theory.md)
- [PRAC] Relative volume by time of day: RVOL(t) = Volume(t) / AvgVolume(t) where AvgVolume(t) is "the average volume for that same time bucket across the last 10-30 sessions"; "the lunch lull drops below 1.0x while the open and close push above 1.5x". Impulse ≥1.5x; pullback "RVOL drops back toward 1.0-1.2x"; resumption "≥1.3-1.5x"; reversal = pullback volume stays heavy. "High RVOL at trend extremes can signal exhaustion, not continuation." RVOL "measures participation, not direction." — [NexusFi: RVOL](https://nexusfi.com/a/concepts/relative-volume-rvol-futures-trading)
- [STAT] Karpoff (1987) survey: "volume is positively related to the magnitude of the price change" and, in equity markets, "to the price change per se". — [Karpoff, JFQA 1987](https://ideas.repec.org/a/cup/jfinqa/v22y1987i01p109-126_01.html)
- [STAT] LIFFE futures, 15-minute data: volume "shows a strong U-shaped intraday pattern, but returns show no such pattern"; volume higher on negative-return intervals. — [Puri & Philippatos, EFM 2008](https://ideas.repec.org/a/bla/eufman/v14y2008i3p528-563.html)
- [STAT] NIFTY futures 1-min data, Jan 2011–Aug 2018: "U-shaped pattern of intraday volatility", elevated at open and close. — [Singh & Gangwar 2018, MPRA 89689](https://ideas.repec.org/p/pra/mprapa/89689.html)
- [STAT] Bulkowski measured-move retrace tabulation (>31,000 up, >21,000 down samples, retrace = (3−2)/(1−2)): among patterns that *failed* to complete the second leg, retraces cluster at 36–50% (up) / 41–60% (down); among those that *did*, retraces cluster at 76–95% (up) / 71–100% (down). "the higher the retrace, the more likely leg 34 would meet or exceed the drop of leg 12"; "Only the size of the retrace mattered" (slope/turn angle did not). — [Bulkowski: Measured Move Retrace](https://www.thepatternsite.com/MMRetrace.html)
- [STAT] Intraday reversals after large opening moves in US index futures (1987–2002) are "highly significant", stronger after large positive opens, but profitability after spread costs "remains open". — [Montclair: intraday price reversals](https://researchwith.montclair.edu/en/publications/intraday-price-reversals-in-the-us-stock-index-futures-market-a-1/)
- [RULE] Range contraction/expansion: ratio = bar range / baseline (SMA 7–20 of range or ATR 14); expansion if ≥ k_e (1.5–2.0), contraction if ≤ k_c (0.5–0.7); NR4/NR7 = narrowest of last 4/7; count consecutive contraction/inside bars for coiling. "Intraday compression readings are only meaningful against the same time of day." "A coil can keep coiling, and the first break out of one is often the false one." — [LuxAlgo: Range Expansion/Contraction](https://www.luxalgo.com/library/concept/range-expansion-contraction.md)
- [RULE] Kaufman ER = |net change over period| / Σ|bar-to-bar changes|, bounded 0–1 (1 = perfectly efficient). The intrabar variant keeps sign to work as a momentum oscillator; "Both CMO and ER essentially measure the same relationship between trend and noise." — [TradingView: Intrabar Efficiency Ratio](https://www.tradingview.com/script/o8tRZCzT-Intrabar-Efficiency-Ratio/)

---

## Codable definitions

Units: `R` = median true range of last 50 bars (as in the earlier note); `rvol(t)` = futures volume / same-15M-slot mean over last 20 sessions. Legs run between confirmed pivots (k=2–3); the *current* leg is pivot → last closed bar.

```
Bar features
  body%     = |C-O| / (H-L)
  clv       = (C-L) / (H-L)                      # 1 = close on high
  wick_opp  = tail against the bar's direction / (H-L)
  overlap   = max(0, min(H,H1) - max(L,L1)) / (H-L)
  rng_ratio = (H-L) / median(H-L, last 20 bars same slot-of-day)   # time-of-day normalised
  trend_bar(dir) = body% >= 0.5 and (clv >= 0.6 if up else clv <= 0.4)        # TV script defaults
  displacement_bar(dir) = body% >= 0.6 and wick_opp <= 0.2 and (H-L) >= 1.5*ATR14   # ICT educator heuristics
  fvg(dir)  = up: L[0] > H[2];  down: H[0] < L[2]

Leg features (over bars i..j of a leg of direction d)
  size        = |P_end - P_start| / R
  bars        = j - i + 1
  speed       = size / bars
  ER          = |C_j - C_i| / sum |C_t - C_{t-1}|          # Kaufman, 0..1
  trendbar%   = share of bars that are trend_bar(d)
  max_run     = longest run of consecutive trend_bar(d)
  avg_overlap = mean overlap
  avg_clv_d   = mean clv in direction d (use 1-clv for down legs)
  n_fvg       = count of fvg(d) inside leg
  n_disp      = count of displacement_bar(d) inside leg
  wave_vol    = sum of futures volume over leg
  wave_rvol   = mean rvol over leg
  effort_result = wave_vol / size                          # Wyckoff: volume per R of progress

Impulse (spike) label   : trendbar% >= 0.7, max_run >= 5 (NexusFi/Brooks "at least five"), avg_overlap <= 0.4,
                          ER >= 0.6, n_fvg >= 1 or n_disp >= 1
Channel label           : direction intact (HH/HL) but trendbar% 0.4-0.7, avg_overlap > 0.4, body sizes smaller
                          than spike bars, counter bars present, pullbacks touch a drawable line (>=2 touches)
Correction (pullback)   : opposite direction to impulse, size/impulse_size in (0, 1.0),
                          speed <= 0.6 * impulse speed, avg_overlap >= 0.6, trendbar%(counter) <= 0.5,
                          n_disp(counter) == 0, wave_rvol < impulse wave_rvol
Hard pullback bound     : retrace > 1.0 of impulse  -> not a pullback (Brooks); close below impulse origin / last HL -> CHoCH

Shortening of thrust (apply to the LAST THREE counter pushes inside the pullback, i.e. A, C and any extra push)
  gain_k = extreme_k - extreme_{k-1} in the pullback direction (points, in R)
  SOT_pullback = gain_1 > gain_2 > gain_3 >= 0  with gain_3 the smallest   (LuxAlgo: >= 3 pushes, latest smallest)
  Apply the same to the impulse's own pushes before the pullback -> SOT_trend (trend-ageing warning)

Three-push / wedge-flag geometry (counter-trend pushes inside the pullback)
  push sizes s1 >= s2 >= s3 (first largest, NexusFi) ; |s_a - s_b| <= 0.25*max for at least two of three ("approximately equal")
  push 3 bars: mean rng_ratio and body% lower than push 1; >= 1 bar makes new pullback extreme but closes in opposite half

CISD at pullback end (ICT)
  level = open of first bar of the last unbroken run of counter-direction closes
  cisd  = close (not wick) through level in impulse direction; weight up if that bar is displacement_bar and leaves an fvg

CHoCH (danger)
  strict: close beyond the HL/LH that produced the impulse extreme; flag "reversal candidate" only if the breaking bar is
  displacement_bar(counter) ; otherwise treat as deep pullback until a LH/HL + BOS in the new direction confirm.

Volume checks (futures volume)
  pullback_quiet   = wave_rvol(pullback) <= 1.2 and wave_rvol(pullback) < wave_rvol(impulse)   (NexusFi 1.0-1.2x)
  pullback_heavy   = wave_rvol(pullback) >= 1.5  -> distribution warning (reversal risk)
  resumption       = first with-trend bar after pullback with rvol >= 1.3 and trend_bar(d)
  absorption       = effort_result(pullback) >> effort_result(impulse) with pullback size small (heavy volume, little ground) -> bullish for impulse side if at a level
```

---

## Momentum-weakening checklist (pullback is dying → ready to sell premium against it)

Each line: what the trader looks at → measurable. "Counter" = the pullback's direction.

| # | Trader's read | Source school | Measurable |
|---|---|---|---|
| 1 | Each counter push gains less than the last ("shortening of thrust") | Wyckoff | `SOT_pullback` true over last 3 pushes; gain_3 ≤ 0.5·gain_1 |
| 2 | Three pushes / wedge flag: third push smaller, overlapping, with rejection tails | Brooks | push sizes s1≥s2≥s3; push-3 mean body% < push-1; wick_opp at extreme ≥ 0.5 |
| 3 | Counter bars shrinking; pullback bars smaller than trend bars | Brooks, Wyckoff LPS | rolling mean rng_ratio of last 3 counter bars < 0.7× pullback's first 3 bars; pullback median range < impulse median range |
| 4 | Closes moving off the pullback extreme (mixed colours, dojis) | Brooks, Elliott B/4 | avg_clv_d(counter) of last 3 bars ≤ 0.5; trendbar%(counter) in last 5 bars ≤ 0.4 |
| 5 | No counter-displacement, no new counter FVGs | ICT | `n_disp(counter)` = 0 in last 5 bars; last counter FVG filled |
| 6 | Pullback slower than impulse, took longer per unit distance | all | speed(pullback) ≤ 0.6·speed(impulse); bars(pullback) ≥ 0.8·bars(impulse) |
| 7 | Counter push fails to make a meaningful new extreme (marginal new low then close inside) | Brooks, Wyckoff spring | new extreme by < 0.5 R and bar closes in opposite half (clv ≥ 0.5 for bull case) |
| 8 | Volume fades on each counter push; last push lightest | Wyckoff waves, RVOL | wave_rvol push3 < push2 < push1; `pullback_quiet` true |
| 9 | Heavy volume but no progress at a level (absorption / spring) | Wyckoff effort-vs-result | `absorption` true AND pullback low within 0.5 R of a prior demand level |
| 10 | Depth still inside the "normal" band, origin intact | Dow, Elliott, LuxAlgo | retrace 0.33–0.66 (Dow) / 0.382–0.618 (Elliott); never > 1.0; strict HL unbroken (no CHoCH) |
| 11 | Correction subdivides in 3s, not 5s | Elliott | pullback has ≤ 3 confirmed internal legs (A-B-C); a 5-leg counter move → re-label as reversal candidate |
| 12 | Trigger: first with-trend close through the counter run's origin, with body | ICT CISD, Brooks H2 | `cisd` true on a trend_bar(d), ideally `resumption` volume ≥ 1.3× |
| — | Trend-side health (pre-conditions): impulse was a spike (≥5 trend bars, FVG), no SOT_trend on impulse pushes, no climax bar (rng_ratio ≥ 2 late in trend) | Brooks, Wyckoff | `Impulse label` true; SOT_trend false; last 3 impulse bars none with rng_ratio ≥ 2.0 |

Danger flags that override (treat as reversal candidate, no premium sale): counter leg shows `Impulse label` traits; `pullback_heavy`; CHoCH with displacement; retrace > 0.786; 5-leg counter structure; counter speed ≥ impulse speed; exhaustion/climax bar at the impulse extreme followed by "two-legged correction" (Brooks) that is still in its first leg.

---

## Pitfalls

- **Everything is relative, nothing is canonical.** LuxAlgo: "There are no fixed numeric thresholds" (displacement); wave threshold is "a lens rather than a parameter with a correct setting". Body ≥ 50/60%, RVOL 1.2/1.5, k_c 0.5–0.7 are defaults from educators/scripts, not tested constants. Sweep them on NIFTY 15M and check stability.
- **Time-of-day bias.** Volume and volatility are U-shaped (LIFFE 15-min, NIFTY futures 1-min). A pullback into the 11:30–13:30 lull will *look* quiet and narrow by construction; the 09:15 and 15:00 bars will look like displacement. Normalise range and volume by slot-of-day baseline (RVOL style, 10–30 sessions) or the checklist mis-fires every midday.
- **Deep retrace ≠ failure for continuation targets.** Bulkowski's >50k-sample tabulation: measured moves that *completed* had retraces clustering 71–100%, failures clustered 36–60%. Shallow = strong trend is a Brooks/Dow heuristic about *trend strength*, not about whether the next leg equals the last. Do not use depth alone to grade the setup; it also conflicts with the Fibonacci null result already in the earlier note.
- **SOT and divergence are deceleration, not reversal.** LuxAlgo: "SOT describes deceleration, not reversal"; effort-result divergences "can persist". Brooks: in a trend "most reversal patterns fail". Need the trigger bar (CISD/H2) after the weakening signs.
- **CHoCH false positives.** "a lone CHoCH fails often"; strong trends "regularly break a minor higher low during a deep pullback and then continue." Use the strict HL (the one that produced the extreme) and require displacement on the breaking bar.
- **Early bars are indistinguishable.** LuxAlgo Pullback: pullback and reversal are "indistinguishable in their early bars"; Elliott: "Confirm completion in hindsight". The checklist only becomes informative after ≥ 2 counter pushes; a one-push pullback has no SOT reading.
- **Context over geometry for wedges.** Wedge flag vs wedge reversal differ only by location (mid-trend vs extreme). Same three-push shape; opposite trade.
- **Volume asymmetry.** Puri & Philippatos found futures volume higher on down intervals; Karpoff found volume tied to |return| and sign in equities. Compare pullback volume to *the preceding impulse's* volume and to the slot-of-day baseline, never to an all-day mean, and expect bear pullbacks in up-trends to carry somewhat more volume than bull pullbacks in down-trends.
- **Climax looks like strength.** Brooks' exhaustion gap = "Unusually big bull bar or bars late in a bull trend"; RVOL: "High RVOL at trend extremes can signal exhaustion". A displacement bar late in an already extended spike/channel is a reason to *skip* the next pullback, not to sell against it.
- **Lookahead.** All leg stats above use confirmed pivots; the *current* pullback's extreme is unconfirmed until k bars pass. Compute SOT/push sizes on closed bars only and act at bar close.

---

## Gaps

- No peer-reviewed test found of "pullback volume is lower than impulse volume" or of volume fading predicting continuation on intraday index futures; the doctrine rests on Dow/Rhea, Wyckoff, Elliott and RVOL practice. Only indirect facts: volume ∝ |return| (Karpoff), U-shaped intraday volume (LIFFE) and volatility (NIFTY futures). Needs an in-house test on NIFTY futures 15M.
- Brooks' primary book text (Trading Price Action Trends ch. 21 spike-and-channel; ch. 16 micro channels) was not retrievable (O'Reilly 404); spike/channel rules above are the NexusFi restatement plus the Brooks glossary. The "five consecutive trend bars" spike minimum is NexusFi's (its own workflow says 3+).
- Frost & Prechter's statement that wave C has the personality of a third wave ("C waves ... as destructive as third waves") was not found in a fetchable source; only StockCharts' paraphrase ("can be devastating"). Treat the C-vs-5 comparison as unverified.
- No source gives a tested ratio for "how much" successive thrusts must shorten, or for pullback speed vs impulse speed (the 0.6× in the earlier note is our parameter).
- Bulkowski's retrace table is daily US stocks; no intraday/index equivalent found.
- ICT's own (video) definitions of displacement/CISD are not in text; all ICT material here is via LuxAlgo and an educator site, which disagree on whether displacement is mandatory for a CISD.
