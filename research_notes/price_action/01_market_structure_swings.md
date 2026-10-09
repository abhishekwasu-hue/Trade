# 01 — Market structure and swing identification (human and algorithmic)

Scope: how discretionary price-action traders (Dow, Brooks, SMC/ICT, Wyckoff) define trend, swing and "degree", and how algorithms (ZigZag, Directional Change, fractals, pivot-N, PIP, nested fractals) reproduce it without lookahead. Written for a NIFTY 15M pullback seller with ~2-day holds.

This file **extends** two existing notes and does not repeat them:
- `Chart knowledge/structure_wyckoff_patterns_divergence.md` §1–2 already covers Dow's HH/HL rule, Rhea's 1/3–2/3 retracement band, Wyckoff A–E events (Spring/UTAD/SOS/LPS), the confirmed-fractal `k` rule and the `R` = median-TR unit.
- `advanced_analysis_tools.md` §1.1–1.4 already covers DC/intrinsic time basics, multi-scale zigzag, PIP, Keogh segmentation and their lookahead classes.

Tags: **[RULE]** = codable definition from the source · **[STAT]** = measured number · **[PRAC]** = practitioner heuristic, untested.

---

## 1. Takeaway

1. Every school ends up with the same two primitives: a **swing point** (a bar that sticks out beyond its neighbours) and a **structural break** (a close beyond the last swing point). Trend = the sequence of breaks in one direction. Everything else (always-in, BOS/CHoCH, failure swing, Phase D) is vocabulary on top of those two.
2. "Degree" is not a property of the market; it is a **parameter you choose** (pivot strength N, zigzag threshold, DC δ). Practitioners settle on two or three degrees: the one you trade plus one above for bias ([LuxAlgo Fractal Nesting](https://www.luxalgo.com/library/concept/fractal-nesting.md): "Three is the common ceiling"; "Most traders track the degree they trade plus one above it for context").
3. The cleanest way to make degrees consistent is **recursion** (Larry Williams / ICT): a degree-2 high is a degree-1 high flanked by lower degree-1 highs. Higher-degree pivots are "defined from lower-degree ones, not computed separately." This replaces three independent zigzags that contradict each other.
4. A **reversal needs two events**, never one: in Dow it is "failure to print a new high followed by a close below the prior swing low"; in SMC it is CHoCH *then* a lower high *then* a BOS in the new direction; in Brooks the first leg "will almost always break the trendline" and then there is a "test of the extreme" (HH, double top or LH). One break of a higher low is a pullback until proven otherwise, and Brooks' frame is that most reversal attempts fail.
5. All swing detectors are **lagged-safe only if stamped at the confirmation bar**. The pivot's price belongs to bar *i*; its *existence* belongs to bar *i+N* (fractal) or to the bar where the reversal clears the threshold (zigzag/DC). The last leg of a zigzag always repaints ([LuxAlgo Zigzag](https://www.luxalgo.com/library/concept/zigzag-structure.md): "Confirmed pivots never move, but the newest leg repaints until its reversal confirms").
6. Threshold-type detectors (zigzag %, ATR×k, DC δ) are statistically well behaved: Glattfelder et al. show the number of DC events scales as δ^(−2.03) and the average overshoot ≈ δ. That gives a principled way to pick δ for a target number of swings per day instead of eyeballing.
7. For the bot: run **pivot strength N on 15M for execution structure**, a **wider setting (or 1H pivots) for the external skeleton**, label strong/weak (protected) swings on the external skeleton, and gate entries so that an internal CHoCH against the 1H bias is read as "pullback starting", not "reversal".

---

## 2. Cited findings

### 2.1 Dow theory (beyond what §1 of the existing note covers)

- [RULE] Degrees with durations: "a primary trend lasting from under a year to several years", "secondary reactions lasting weeks to months that retrace part of the primary move", "minor day-to-day fluctuations". — [LuxAlgo Dow Theory](https://www.luxalgo.com/library/concept/dow-theory.md)
- [RULE] Reversal confirmation in an uptrend is a **failure swing**: "a failure to print a new high followed by a close below the prior swing low". Also: "failure swings and closes beyond prior swing points flag that the primary trend is in question." — [LuxAlgo Dow Theory](https://www.luxalgo.com/library/concept/dow-theory.md)
- [RULE] Trend persistence default: "a trend is assumed to continue until it gives definite signals of reversal". — [LuxAlgo Dow Theory](https://www.luxalgo.com/library/concept/dow-theory.md)
- [PRAC] Secondary-reaction identification is contested: "Probably no two students would agree on any rule for selecting and tabulating the important secondary reactions." Rhea's book asked for ~3 weeks; Schannep accepts "10 days and even less in very exceptional circumstances"; a commenter's rule is "higher than 6%, 10 trading days"; "Other practitioners drop the retracement requirement altogether (i.e. Martin Pring)." — [thedowtheory.com primer](https://thedowtheory.com/a-primer-on-secondary-reactions-under-dow-theory)
- [RULE] Rhea's **line** (sideways structure): "A 'line' is a price movement extending two to three weeks or longer, during which period the price variation of both averages move within a range of approximately five per cent." Resolution: "Simultaneous advances above the limits of the 'line' indicate accumulation and predict higher prices". — [thedowtheory.com, Lines](https://thedowtheory.com/dow-theory-special-issue-lines-classical-dow-theory-and-schannep/)
- [PRAC] Rhea: "we could always depend upon the breaking of a line as indicating a change of the general market direction" of "at least secondary" magnitude. Blay uses line breaks as a "surrogate secondary reaction" and says a counter-move of more than 3% confirms the surrogate reaction's extreme. — same source.
- [PRAC] Translation to 15M (inference): Rhea's "line" is the Dow name for Brooks' tight trading range and Wyckoff's Phase B. The structural idea that matters for code: *a range of ≥ N bars inside a band of ≈ x·R, resolved only by a close outside it, counts as one swing event of the next-higher degree.*

### 2.2 Al Brooks (price action)

- [RULE] Trend: "A series of price changes that are either mostly up (a bull trend) or down (a bear trend)." A chart "will show only one or two major trends." — [Brooks glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/), [forum "how do you define a trend"](https://www.brookstradingcourse.com/support-forum/general-trading-discussion/how-do-you-define-a-trend/)
- [RULE] Swing high: "A bar that looks like a spike up on the chart and extends up beyond the neighboring bars." Swing low is the mirror. This is a pivot-N definition with N unspecified (visually N≈1–3). — [Brooks glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/)
- [RULE] Swing / leg hierarchy: "A smaller trend that breaks a trend line of any size; the term is used only when there are at least two on the chart." The glossary gives "three loosely defined smaller versions: swings, legs, and pullbacks." Moderator: "we get intraday minor trends (legs and pullbacks) as well as swings that one usually associates more with an overall trend." — glossary + forum above.
- [RULE] Trading range minimum: "The minimum requirement is a single bar with a range that is largely overlapped by the bar before it." Tight trading range: "A trading range of two or more bars with lots of overlap in the bars". — [Brooks glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/)
- [RULE] Breakout: "The high or low of the current bar extends beyond some prior price of significance such as a swing high or low". Follow-through: "After the initial move, like a breakout, it is one or more bars that extend the move." — same.
- [RULE] Always In: "If you have to be in the market at all times, either long or short, this is whatever your current position is". Forum restatement: "a market is either AIL or AIS, and yes a market is either in a trend or a TR" and "everything, including the AI direction, trends and TRs, depends on the TF." — glossary + [forum "always in confusion"](https://www.brookstradingcourse.com/support-forum/13-always-in/always-in-confusion/)
- [RULE] Always-In flip conditions (forum member Khan summarising the course): "you see a major HL/LH getting broken with follow-through, in which case you are either in a TR or in the opposite trend"; or "you see 3-5+ consecutive strong trend bars against you"; or "If you have a successful BO from a TR in either direction, then AI is in the direction of it." — [forum](https://www.brookstradingcourse.com/support-forum/13-always-in/always-in-confusion/)
- [PRAC] Always-In starts with a breakout: "Always in always begins with a Breakout (Trend Bars: 1 Big, 2 Medium, 3+ Small)." and "Always in is a concept for strong trends only, and is useless in a TR. (Broad channel is sloped TR)". — same.
- [RULE] Pullback counting: "A high 1 is a bar with a high above the prior bar in a bull flag or near the bottom of a trading range." "the next bar in this correction whose high is above the prior bar's high is a high 2." Mirror for Low 1/Low 2. — [Brooks glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/)
- [RULE] Leg definition for counting (NexusFi): a leg needs "Directional momentum", "A clear swing extreme", "A pause or bounce between legs"; pitfall "Counting inside bars as legs (no directional movement)". Swing extreme "at least 2-3 bars where price stops making progress in the countertrend direction". — [NexusFi two-legged pullback](https://nexusfi.com/a/strategies/two-legged-pullback-trading)
- [PRAC] Two legs are the default: "all strong moves usually have at least two legs even if the second one falls short and reverses"; "Any time there is a trendline breakout, the chances are high that there will be a second leg."; "Most Reversal Patterns fail and become two-legged pullback continuation patterns." — [Brooks probabilities compilation](https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754)
- [PRAC] Reversal anatomy: "The first leg of the reversal will almost always break the trendline"; "Trends often end with a test of the extreme, and the test often has two legs"; after a trend-line break "the first pullback will almost always form a Lower High (and only rarely a Higher High)". The test of the extreme "can be one of three things (if bull trend)": higher high, double top, lower high; "Most reversals will fail." — [compilation](https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754), [TradingView MTR Part 1](https://www.tradingview.com/chart/EURUSD/YJrzJW6y-Major-Trend-Reversal-Trading-Part-1)
- [STAT][PRAC] Brooks' quoted probabilities (second-hand, from his course): "80% of breakouts will fail" and "the probability of getting a MTR swing as being 40%". A member paraphrase: "80% we'll stay in the current trend, 80% we'll stay in the current TR." These are Brooks' rules of thumb, not measured on NIFTY. — [Brooks forum, probability of BO vs MTR](https://brookstradingcourse.com/support-forum/22-major-trend-reversals/probability-of-breakout-vs-mtr), [NexusFi trading range](https://nexusfi.com/a/strategies/trading-range-price-action-strategies) ("a directional truth, not a precise statistic")
- [RULE] Range vs trend-pause (NexusFi, Brooks-derived): a range needs 2–3 touches of both boundaries; "A single test of support followed by a new high is not a range." "In a range, bars overlap extensively." — [NexusFi](https://nexusfi.com/a/strategies/trading-range-price-action-strategies)
- [PRAC] Pullback depth heuristics (NexusFi): strong trend "Pullbacks are shallow — typically less than 50% of the prior impulse"; weak trend "retracing 60-80% or more of prior impulse legs"; bounce between legs "brief (2-4 bars) and weak (small bodies)". — [NexusFi](https://nexusfi.com/a/strategies/two-legged-pullback-trading)
- [PRAC] Gaps: "Whenever you see a large gap opening, it is wise to assume that there will be a strong trend." and "On most days, either the high or low of the day is formed within the first hour or so." — [compilation](https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754)

### 2.3 Smart Money Concepts / ICT

- [RULE] BOS: "A break of structure (BOS) is a with-trend structural break." In an uptrend it is "price trading through the most recent significant swing high" — "the last swing high in an uptrend, the last swing low in a downtrend." — [LuxAlgo BOS](https://www.luxalgo.com/library/concept/break-of-structure.md)
- [RULE] Close vs wick: "Many traders require a candle body to close beyond the swing"; "Wick-based BOS reacts earliest but mislabels many liquidity sweeps as breaks"; "close-based BOS filters those at the cost of later entries"; sweep vs break: "The close is what separates them, and it only resolves after the fact." — same.
- [RULE] CHoCH: "A change of character (CHoCH) is the first structural break against the prevailing trend" — "in an uptrend, price breaking the most recent meaningful higher low". Filter: "A body close beyond it, ideally with displacement, is the usual filter against noise and stop runs." It is "evidence, not confirmation". Established reversal needs "a lower high forming after the break, then a with-trend break of structure in the new direction". Failure mode: "Strong trends regularly break a minor higher low during a deep pullback and then continue." — [LuxAlgo CHoCH](https://www.luxalgo.com/library/concept/change-of-character.md)
- [RULE] MSS vs CHoCH: "many traders use the terms interchangeably"; some reserve MSS for "a break that displaces through the swing right after a liquidity grab." — same.
- [RULE] Strong/weak (protected) swings: "A strong low is the low that launched a break of structure upward." "A weak high is a high that failed to exceed the previous high." Strong and protected are "used interchangeably"; protected means "the market should not trade back through it while the uptrend is intact." A weak high becomes strong when the decline it launches breaks the prior low. "every strong or weak assignment is a running hypothesis that the next structural event can revise." — [LuxAlgo Strong vs Weak Swings](https://www.luxalgo.com/library/concept/strong-vs-weak-swings.md)
- [RULE] Internal vs external: "External structure is the market's major swing skeleton"; "Internal structure is everything printed inside one external leg." Detection: "A wide pivot length or zigzag traces the external skeleton"; internal uses "a tight setting, sometimes as small as a five-bar Williams fractal". Rank: "breaking any swing between them is an internal event of lower rank"; an internal break against external bias is "treated as a pullback event, not a reversal". "an internal change of character against the trend usually marks the start of a pullback" and is "often the earliest evidence, but a weak predictor on its own." — [LuxAlgo Internal vs External](https://www.luxalgo.com/library/concept/internal-vs-external-structure.md)
- [RULE] Invalidation: protected swing = "the swing low whose failure breaks the sequence of higher lows"; criterion must be fixed beforehand: "wick beyond the level, close beyond it, or a close on a higher timeframe"; "displacement and acceptance beyond the level argue genuine invalidation, while an instant reclaim suggests a sweep." "a break of a minor internal pivot often reprices the entry, while a break of the external swing kills the whole idea." — [LuxAlgo Structure Invalidation](https://www.luxalgo.com/library/concept/structure-invalidation.md)
- [RULE] ICT swing recursion: "as long as three candles appear and the middle candle is higher than the candles on both sides, we can find a swing high" (STH). ITH: "the middle STH is higher than the STH on both sides." LTH: "the middle ITH is higher than the ITH on both sides." Hierarchy "LTH > ITH > STH". — [penchan.co ICT structure](https://penchan.co/en/market/ict-market-structure-concepts/)
- [RULE] Same recursion attributed to Larry Williams: short-term high "a high with lower highs on either side"; intermediate "a short-term high flanked by lower short-term highs"; long-term "an intermediate-term high flanked by lower intermediate-term highs". Containment: an up-leg "holds a complete lower-degree uptrend with its own breaks of structure." "The self-similarity is approximate, not exact." — [LuxAlgo Fractal Nesting](https://www.luxalgo.com/library/concept/fractal-nesting.md)
- [PRAC] Top-down ladder: adjacent timeframes spaced "by a factor of roughly four to six"; "a full trend on the 5-minute chart is often a single pullback on the 4-hour"; "the higher timeframe holds veto power rather than casting one vote among several"; "the timeframe you execute on is never the timeframe that decided the bias." Counter-bias trades only "after the higher timeframe itself prints a change of character". — [LuxAlgo Top-down](https://www.luxalgo.com/library/concept/top-down-analysis.md)

### 2.4 Wyckoff phases as structure (extends existing §2)

- [RULE] Phase A "will mainly be useful for position management" because a range is not known to exist "until the Secondary Test (ST) develops"; SC and AR "establish the range limits". — [tradingwyckoff.com phases](https://tradingwyckoff.com/en/phases-of-a-wyckoff-structure/)
- [PRAC] Phase B is "longer than Phases A and C" as a guideline; a shorter B "suggests urgency and a stronger subsequent move." — same.
- [RULE] Phase C = test beyond the boundary; Phase D = break of the range with "wide candles and rising volume"; confirmation "requires price to hold on the other side of the range without immediate re-entry"; Phase E = trend outside the range. — same.
- [PRAC] Structural mapping (inference): Phase C spring = SMC "liquidity sweep" of the range low (wick through, close back inside); Phase D SOS = close-based BOS of the range high; LPS = first higher low after the BOS = SMC "strong low". The three vocabularies describe one event sequence.

### 2.5 Algorithmic swing detection

- [RULE] Zigzag thresholds: percent T = (d/100)×E (E = running extreme), ATR T = k×ATR_t, fixed points, pivot-lookback (N lower highs each side), Gann swing (count of consecutive HH/LL bars). "Every move smaller than the threshold is discarded as noise." — [LuxAlgo Zigzag](https://www.luxalgo.com/library/concept/zigzag-structure.md)
- [STAT][PRAC] Typical values: percent "commonly 5 on daily charts"; ATR multiple k "commonly 2 to 3" on ATR(14); Gann count 2 or 3. "match the threshold to the swing scale you actually trade, then keep it consistent." — same.
- [RULE] Repaint/lookahead: "Confirmed pivots never move, but the newest leg repaints until its reversal confirms"; using pivots at their drawn location "injects lookahead bias" — shift each pivot to its confirmation bar before backtesting. — same.
- [RULE] Pivot strength: "a pivot high of strength N is a bar whose high exceeds the highs of the N bars to its left and the N bars to its right." "A pivot cannot be confirmed until every right-side bar has closed." "They do not repaint less, they confirm later." "Once confirmed, a correctly implemented pivot never changes." — [LuxAlgo Pivot Strength](https://www.luxalgo.com/library/concept/pivot-strength.md)
- [PRAC] Pivot-N values: common range 2–10; intraday "roughly two to five bars"; "ten and beyond isolates the legs swing traders care about." Asymmetric: large left/small right "demands a significant structure before the turn but confirms quickly." — same.
- [RULE] Williams fractal = pivot strength 2: up fractal at t requires H_t > H_(t±i) for i = 1..2; "the pattern cannot exist until the two right-hand bars have closed, so the marker always appears in the past." "The practical cost is not repainting but lag". Tie handling: "Strict inequality is the common default". — [LuxAlgo Williams Fractal](https://www.luxalgo.com/library/concept/williams-fractal.md)
- [RULE] MT4 ZigZag parameters: ExtDeviation = "The percentage or pip value used to filter out small swings"; ExtBackstep = "the number of bars/candles that must form after a high or low is formed"; ExtDepth = lookback window for the extreme. (Defaults 12/5/3 are platform defaults, not on this page.) — [MQL5 forum](https://www.mql5.com/en/forum/145449)
- [RULE] Directional change: "Intrinsic time is algorithmically derived from a selected threshold δ, describing a price move in percent." Mode flips when the move from the running extreme exceeds δ; continuation beyond that point is overshoot. "intrinsic time is a multi-scale concept, defined by a set of thresholds [δ1, …, δn]." — [Intrinsic Time Primer, arXiv 2406.07354](https://arxiv.org/pdf/2406.07354)
- [STAT] Scaling laws on 13 FX pairs, thresholds 0.01%–5.05%: number of DC events N(δ) ∝ δ^E with E ≈ −2.03 (s.d. 0.10); average overshoot ≈ δ (exponent 1.04, prefactor 1.06); total move ≈ 2δ ("making the total move double the size of the directional-change threshold"). Laws "hold for close to three orders of magnitude". — [Glattfelder, Dupuis & Olsen 2011](https://arxiv.org/abs/0809.1040)
- [STAT] But: "The individual instances of actually measured overshoot lengths reveal that the average value is never actually manifested." — [Primer](https://arxiv.org/pdf/2406.07354)
- [RULE] PIP: "the first two PIPs will be the first and last points of P"; "The next PIP will be the point in P with maximum distance to the first two PIPs"; repeat between adjacent PIPs. Distances: ED (sum of Euclidean to both neighbours, "biased towards the middle"), PD (perpendicular to the chord), VD (vertical to the chord, "to capture the fluctuation"). Reversal templates use 7 PIPs; rule example (H&S): sp4 > sp2, sp6; sp2 > sp1, sp3; sp6 > sp5, sp7; diff(sp2, sp6) < 15%; diff(sp3, sp5) < 15%. — [Fu, Chung, Luk & Ng](https://par.cse.nsysu.edu.tw/resource/paper/2011/111219/Stock%20time%20series%20pattern%20matching%20Template-based%20vs.%20rule-based%20approaches.pdf)
- [STAT] "PD has the highest accuracy", VD within 0.04 of it and fastest (PD ≈ 2× VD time, ED ≈ 3×); "VD is the best choice for the PIP identification process". — same.
- [RULE] Magnitude filters: "Many tools combine both so a swing must satisfy time and size." A larger threshold "produces fewer, more meaningful swings but confirms them later." "unfiltered pivots flip constantly on lower timeframes." "No threshold is objectively correct". — [LuxAlgo Swing Magnitude Filters](https://www.luxalgo.com/library/concept/swing-magnitude-filters.md)
- [PRAC] Repainting checklist: "Repainting means your trading script changes its past signals using future data." Red flags: `ta.pivothigh/ta.pivotlow` used at the pivot bar, `lookahead_on`; "Elliott Wave or Zigzag indicators often rely on future candles to confirm pivots". Test with bar replay. — [PickMyTrade](https://blog.pickmytrade.io/prop-trading-automation-repainting-check.md)
- [PRAC] Gaps distort volatility units: an "Optional toggle to ignore overnight/weekend gaps that distort volatility readings" is offered for "instruments with large overnight gaps (indices, forex, crypto)". — [ATR No Gap script](https://vn.tradingview.com/script/IVxuC8CW-ATR-No-Gap-Advanced-Volatility-Indicator)

---

## 3. Codable definitions (pseudo-rules; all stamped at confirmation bar)

Units: `R` = median true range of last 50 15M bars (see existing note). `N` = pivot strength. All comparisons on **bar high/low for pivots, bar close for breaks** unless stated.

```
# 3.1 Pivot of strength N (Williams fractal when N=2)
pivot_high(i, N)  := high[i] > high[i-j] and high[i] > high[i+j]  for j in 1..N   (strict)
pivot_low (i, N)  := low[i]  < low[i-j]  and low[i]  < low[i+j]   for j in 1..N
confirm_bar(i)    := i + N            # pivot exists only from here on
# Asymmetric variant for faster confirmation: left L >= 3..5, right Rt = 2.

# 3.2 Alternation + magnitude filter (zigzag grammar on confirmed pivots)
#   keep alternating H/L; if two highs in a row keep the higher, two lows keep the lower
#   drop a leg if |pivot_k - pivot_(k-1)| < m * R   (m ~ 1.5–3 on 15M; tune so that
#   confirmed swings per session ~ 2–4 for the "execution" degree)
#   last (open) leg is PROVISIONAL and must never feed a signal.

# 3.3 Degree by recursion (Williams/ICT), not by independent thresholds
D1_high := pivot_high(i, N)                                  # short-term
D2_high := D1_high flanked by lower D1_highs on both sides   # intermediate
D3_high := D2_high flanked by lower D2_highs on both sides   # long-term
confirm_bar(D2_high) := confirm_bar(of the right-flank D1_high)
# Invariant: every D(k+1) pivot is also a D(k) pivot (nesting). Use D2 as the
# external skeleton for a 15M chart; D1 as internal. D3 ≈ 1H/daily structure.

# 3.4 Directional Change with volatility-scaled thresholds (alternative to 3.2/3.3)
delta_k := c_k * R / price            # e.g. c = {2, 4, 8} for degrees 1..3
mode=UP: ext = max(ext, high); if (ext - low)/ext >= delta: DC_DOWN at this bar, pivot=ext
mode=DN: ext = min(ext, low);  if (high - ext)/ext >= delta: DC_UP  at this bar, pivot=ext
# Expected swings per day ∝ delta^-2 (Glattfelder): halving delta ≈ 4× more swings.
# Expected follow-through after confirmation ≈ delta (overshoot) ⇒ total leg ≈ 2*delta.
# Within-bar ambiguity: if a bar both triggers a DC and makes a new extreme, order the
# high/low by close direction (bull close ⇒ low first); flag the bar as ambiguous.

# 3.5 Trend state (Dow + SMC) on the external skeleton (D2)
last_H1, last_H2 := last two confirmed D2 highs; last_L1, last_L2 := last two D2 lows
UP   := last_H1 > last_H2 and last_L1 > last_L2
DOWN := last_H1 < last_H2 and last_L1 < last_L2
RANGE := otherwise, OR (Rhea line / Brooks TR): >= 8 bars whose highs and lows all lie
         inside a band of <= 3*R with >= 2 touches of each boundary.
# Brooks always-in direction = sign of the last confirmed BOS; undefined in RANGE.

# 3.6 Structural breaks (close basis, with displacement option)
BOS_up    := close > last_D2_high  while state==UP           (continuation)
CHOCH_dn  := close < protected_low while state==UP           (first counter-trend break)
protected_low := the D2 low that launched the most recent BOS_up  (SMC "strong low")
weak_high     := any D2 high that did not exceed the prior D2 high
displacement  := (close - level) >= 0.5*R and bar range >= 1.2*R   (optional strictness)
sweep         := low < level and close >= level                    (NOT a break; log it)
# Re-run strong/weak labelling after every BOS/CHoCH ("running hypothesis").

# 3.7 Reversal confirmed (two-step, all schools)
REVERSAL_dn := CHOCH_dn  →  next confirmed D2 high < last_H1 (lower high)  →  close < CHOCH bar's low (BOS in new direction)
# Until step 3 completes: state = "pullback with CHoCH warning". Expect it to fail most of
# the time in a strong trend (Brooks 80% heuristic; LuxAlgo "many CHoCHs are followed by deep pullbacks").

# 3.8 Always-in flip (Brooks, codable form)
flip := REVERSAL (3.7)  OR  k consecutive opposite trend bars with k>=3 and
        each body >= 0.5*range and cumulative move >= 3*R     (fast-flip clause)
        OR  close outside a RANGE band (3.5) followed by one follow-through bar.

# 3.9 Pullback leg counting (Brooks H1/H2 generalised to D1 legs)
# a counter-trend leg = D1 pivot-to-pivot move against the D2 trend with size >= 1*R
# inside bars and moves < 1*R do not count as legs
# H2 setup := second D1 low inside the same D2 pullback, with the second low formed
#             by a bar whose high exceeds the prior bar's high (Brooks "high 2")

# 3.10 Multi-timeframe veto
bias := state (3.5) computed on D3 (or on 1H bars with N=3)
allow_long_setup  := bias != DOWN  and  15M internal CHoCH_dn has printed (pullback started)
                     and  price > protected_low(D3)
# Internal CHoCH against the bias = "pullback event", never a reversal signal.

# 3.11 Opening-gap handling (NIFTY 09:15 bar)
gap := open[first] - close[prev_session_last]
if |gap| >= 2*R:
    # (a) R itself: compute TR excluding the gap component for the first bar (high-low only)
    # (b) pivots: the previous session's last pivot stays valid; the gap bar may not be a
    #     pivot by itself until N bars confirm, same as any bar
    # (c) DC/zigzag: a gap beyond delta counts as an immediate DC (price did move that far);
    #     mark the leg as "gap leg" so leg-speed/overlap stats are not polluted
    # (d) structure: a gap that closes beyond a D2 level is a BOS/CHoCH only if the first
    #     15M bar CLOSES beyond the level (Brooks: large gaps usually trend; a fade back
    #     inside within 2 bars is a failed breakout)
```

---

## 4. Pitfalls

- **Pivot stamped at its own bar** — the single most common leak. A strength-N pivot "cannot be confirmed until every right-side bar has closed". Backtests that read `ta.pivothigh` at bar i without an N-bar offset are using the future. ([Pivot Strength](https://www.luxalgo.com/library/concept/pivot-strength.md), [PickMyTrade](https://blog.pickmytrade.io/prop-trading-automation-repainting-check.md))
- **Using the open zigzag leg** — "The final segment can extend, move, or vanish as new bars arrive." Never feed it to ABC detection or divergence.
- **Three independent zigzags for three degrees** — thresholds set separately produce D2 pivots that are not D1 pivots, so "degrees contradict each other". Use recursion (3.3) or nested DC thresholds and enforce the nesting invariant.
- **Calling a reversal on one break** — every school requires a second event (LH after CHoCH, Dow failure swing, Brooks' test of the extreme). "Strong trends regularly break a minor higher low during a deep pullback and then continue."
- **Wick vs close inconsistency** — pick one convention per degree before trading; wick-based breaks "mislabel many liquidity sweeps as breaks". For a seller who wants pullback ends, the sweep (wick below protected low, close back above) is often the *entry*, so log sweeps as a separate event rather than discarding them.
- **Fixed % thresholds across volatility regimes** — "a fixed percentage behaves very differently on a calm large-cap than on a volatile crypto pair." Scale by R (or ATR). The same applies within the day: NIFTY's first and last 30 minutes have wider ranges, so a flat R over-detects swings at the open and under-detects midday.
- **Scaling-law averages are not forecasts** — DC overshoot ≈ δ holds on average; "the average value is never actually manifested" in individual cases. Use it for parameter sizing, not for targets.
- **Degree inflation** — "Fourth or fifth degrees update too rarely to guide decisions." For a 2-day hold on 15M, two degrees on 15M plus the 1H/daily bias is the ceiling.
- **Confusing Brooks' "trading range" minimum (one overlapping bar) with a tradable range** — the glossary minimum is a bar-level definition; for structure use the 2–3 touches rule and ≥ 8 bars.
- **Treating Brooks' 80% / 40% numbers as statistics** — they are his teaching heuristics ("a directional truth, not a precise statistic"). Measure the real rates on NIFTY 15M before encoding them as probabilities.
- **PIP end-point bias** — the last PIP is always the current bar; only interior PIPs older than N bars are usable (see existing §1.3). With VD distance the algorithm is fast enough to rerun every bar on a trailing window.
- **Gap bars as pivots** — a gap-up open bar often has the session's high or low within the first hour (Brooks). That bar will be a legitimate pivot only after N further bars; do not pre-label it.

---

## 5. Gaps (what the sources do not settle)

- **No published optimal N or δ for an index 15M chart.** Sources give ranges (N = 2–5 intraday, k = 2–3 ATR, 5% daily) but nothing calibrated to NIFTY. Needs a sweep: choose N/δ so that the D2 degree yields swings whose median duration ≈ 1–2 sessions (the holding horizon), then check the δ^−2 count law holds on NIFTY 15M as a sanity test.
- **Brooks' exact MTR rule text** is behind his course paywall; what is public is the sequence (trend-line break → test of extreme as HH/double top/LH → strong reversal) and the 40% heuristic. The "test must be within X of the old extreme" tolerance is not published.
- **No peer-reviewed evaluation of BOS/CHoCH or strong/weak swings** as predictors; everything SMC is [PRAC].
- **Dow's secondary-reaction duration/extent rule has no intraday analogue** in the literature; the 10-day/3-week and 3–6% figures are daily-chart rules. Our 15M equivalent (≥ 8 bars, ≥ 1.5–3 R) is an inference to be tuned.
- **Gap handling** in swing detection is almost undocumented; only volatility-indicator authors mention it. The rules in 3.11 are our own and need backtesting, especially the "gap as immediate DC" choice vs "ignore the gap component".
- **Within-bar ordering of high and low** (which came first) is unknown on 15M bars; it matters for DC and for whether a bar is both a sweep and a break. Options: use 1M data to resolve, or carry an "ambiguous" flag.
- **Ties in pivot comparison** (equal highs, common on NIFTY round numbers) — "Strict inequality is the common default", but SMC treats equal highs (EQH) as liquidity. Decide whether EQH within 0.1–0.2 R count as one pivot or as a separate "equal highs" event.
- **Degree consistency between recursion (3.3) and threshold (3.4)** — both are in use; whether they pick the same D2 pivots on NIFTY has not been checked. Run both and measure agreement before choosing.

---

## Sources

- Brooks glossary — https://www.brookstradingcourse.com/price-action-trading-terms-glossary/
- Brooks forum, how do you define a trend — https://www.brookstradingcourse.com/support-forum/general-trading-discussion/how-do-you-define-a-trend/
- Brooks forum, always in confusion — https://www.brookstradingcourse.com/support-forum/13-always-in/always-in-confusion/
- Brooks forum, probability of breakout vs MTR — https://brookstradingcourse.com/support-forum/22-major-trend-reversals/probability-of-breakout-vs-mtr
- Brooks probability compilation (Slideshare) — https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754
- TradingView, Major Trend Reversal Trading Part 1 — https://www.tradingview.com/chart/EURUSD/YJrzJW6y-Major-Trend-Reversal-Trading-Part-1
- NexusFi, two-legged pullback — https://nexusfi.com/a/strategies/two-legged-pullback-trading
- NexusFi, trading range strategies — https://nexusfi.com/a/strategies/trading-range-price-action-strategies
- LuxAlgo library: Dow Theory, Zigzag Structure, Pivot Strength, Williams Fractal, Break of Structure, Change of Character, Strong vs Weak Swings, Internal vs External Structure, Structure Invalidation, Fractal Nesting, Swing Magnitude Filters, Top-down Analysis — https://www.luxalgo.com/library/concept/
- thedowtheory.com, primer on secondary reactions — https://thedowtheory.com/a-primer-on-secondary-reactions-under-dow-theory
- thedowtheory.com, Lines — https://thedowtheory.com/dow-theory-special-issue-lines-classical-dow-theory-and-schannep/
- penchan.co, ICT market structure — https://penchan.co/en/market/ict-market-structure-concepts/
- tradingwyckoff.com, phases — https://tradingwyckoff.com/en/phases-of-a-wyckoff-structure/
- MQL5 forum, ZigZag parameters — https://www.mql5.com/en/forum/145449
- Glattfelder, Dupuis & Olsen 2011, 12 scaling laws — https://arxiv.org/abs/0809.1040
- Theory of Intrinsic Time: A Primer — https://arxiv.org/pdf/2406.07354
- Fu, Chung, Luk & Ng, PIP template vs rule matching — https://par.cse.nsysu.edu.tw/resource/paper/2011/111219/Stock%20time%20series%20pattern%20matching%20Template-based%20vs.%20rule-based%20approaches.pdf
- PickMyTrade, repainting check — https://blog.pickmytrade.io/prop-trading-automation-repainting-check.md
- ATR No Gap indicator — https://vn.tradingview.com/script/IVxuC8CW-ATR-No-Gap-Advanced-Volatility-Indicator
