# Elliott Wave Corrective Patterns: Sourced Reference for a Codable Spec

Context: NIFTY index pullbacks on 15M/1H. Entry at the END of a correction, in the direction of the prior impulse, only after a closed reversal candle at a real area. R:R ≥ 3. No breakout entries.

**Labels used**
- **RULE**: inviolable per Frost & Prechter, *Elliott Wave Principle* (EWP), or Elliott. If the rule is broken, the count is wrong.
- **GUIDELINE**: an EWP/EWI tendency.
- **NEOWAVE**: Glenn Neely (Mastering Elliott Wave, MEW; neowave.com Q&A).
- **PRACTITIONER**: a named third party.
- **INFERENCE**: my own synthesis for coding.

**Source caveat.** I could not fetch the full EWP book text (EWI gates it). EWP quotes below come from EWI's Waveopedia pages, which reproduce EWP text, and from one verbatim EWP excerpt (depth of corrections). Items marked *(EWP, recalled, verify)* are from my knowledge of EWP Chapter 4 and should be checked against the book before they are hard-coded.

---

## A. Corrective vs impulsive character

### A1. Structural differences

| Feature | Impulse (motive) | Correction | Label / source |
|---|---|---|---|
| Wave count | 5 (or a 5-wave diagonal) | 3, or a combination of threes (7, 11) | RULE. EWI: "corrections are never fives" ([Corrective Waves](https://www.elliottwave.com/waveopedia/corrective-waves/)) |
| Count heuristic | 5, 9, 13 | "A count of 7, 11 or 15 with numerous overlaps is likely corrective" | GUIDELINE ([Combinations](https://www.elliottwave.com/waveopedia/combinations/)) |
| Overlap | Wave 4 never enters wave 1's territory, except in diagonals | Overlap is normal; in triangles it is required | RULE for impulses ([MTPredictor](https://www.mtpredictor.com/elliott-wave-rules)); PRACTITIONER for triangles (Wavetraders) |
| Ease of movement | Motive waves "flow with comparative ease" | "Markets move *against* the trend of one greater degree only with a seeming struggle" | GUIDELINE ([Corrective Waves](https://www.elliottwave.com/waveopedia/corrective-waves/)) |
| Slope | Steep, persistent | Either "Sharp corrections angle steeply against the larger trend" (zigzag family) or sideways ones that "carry back to or beyond their starting level" (flats, triangles, combinations) | GUIDELINE (same page) |
| Volume | Wave 3 usually has the "greatest volume" | "Second waves often end on very low volume and volatility"; B waves often show "a diminution of volume" | GUIDELINE ([Wave Personality](https://www.elliottwave.com/waveopedia/wave-personality/)) |
| Momentum | Peaks in wave 3 | C waves often end with momentum divergence | PRACTITIONER (elliottwave-forecast via [TradingView post](https://in.tradingview.com/chart/NQ1%21/1zbhGq2y-Let-s-learn-about-flats); [EWF corrective waves](https://elliottwave-forecast.com/trading/elliott-wave-corrective-waves/)) |

### A2. Time (NEoWave)

- **Wave 2 and wave 4 timing.** In a *standard* (trending) impulse, "wave-2 CANNOT take less time than wave-1" and "wave-4 CANNOT take less time than wave-3". In *terminal* impulses (diagonals), wave 2 may take less time than wave 1 and usually does. NEOWAVE ([QOW 17](https://www.neowave.com/qow/qow-archive-17.asp))
  - **Coding consequence (INFERENCE):** a pullback that is faster than the impulse leg it corrects is suspect as a same-degree correction. It is more likely a smaller-degree wave, such as only wave a of the correction.
- **Flats and zigzags.** "Wave-b can NEVER take less time than wave-a in a Flat or Zigzag." Also, "c always takes more time than a."
  - If a ≈ b in time, then c ≈ a + b.
  - If b ≫ a in time, then c ≈ (a + b)/2.
  - NEOWAVE ([QOW 411](https://www.neowave.com/qow/qow-archive-411.asp))
- **Triangle exception.** In triangles, wave b may take less time than wave a only if b is also smaller than a in price. NEOWAVE (same page)
- **Telling ABC from 1-2-3 by time.** Compare the times of the first two segments. NEOWAVE ([QOW 262](https://www.neowave.com/qow/qow-archive-262.asp))
  - If the 2nd segment takes 100–261.8% of the 1st's time, "a Zigzag or Impulsion is possible".
  - If it takes more than 300%, "a Zigzag is forming".
  - If the 1st segment takes longer than the 2nd, a triangle is forming.
  - Neely gives no answer for 261.8–300%.
- **Rule of Similarity & Balance.** Two adjacent waves count as the same degree only if one of these holds. NEOWAVE ([QOW 78](https://www.neowave.com/qow/qow-archive-78.asp))
  - Price: "the smaller of two adjacent waves should be no less than 1/3 the vertical price coverage of the larger wave".
  - Time: "the shorter time pattern should be no less than 1/3 that consumed by the larger, adjacent wave".
  - If neither holds, "the likelihood two adjacent waves are of the same Degree is very slim."
  - **Coding consequence (INFERENCE):** reject a pullback as "the correction of impulse X" when it covers less than 1/3 of X's price *and* less than 1/3 of X's time. It belongs to a lower degree, so the real correction has not happened yet.

### A3. Evidence that a counter-move is a reversal, not a correction (real time)

1. **The counter-move is a clean 5-wave structure.** RULE-derived: corrections are never fives, so an initial five against the trend "is only part of a correction" ([EWI](https://www.elliottwave.com/waveopedia/corrective-waves/)) or the start of a new trend.
   - For a pullback trader, a 5-wave first leg means at best a zigzag (5-3-5), so a further C leg is still due. **Do not enter after only the A leg.** (INFERENCE)
2. **Speed and size versus prior counter-moves.** Neely's "Type 2" confirmation: a move "larger and faster than any previous rally" during the trend suggests the trend ended. NEOWAVE ([QOW 1109](https://www.neowave.com/qow/qow-archive-1109.asp))
   - **Mirror for the spec (INFERENCE):** if the pullback is the largest and fastest counter-move of the whole impulse, and it is impulsive in character, treat it as a possible reversal.
3. **A rule is violated.** Price moves beyond the start of the impulse (the wave 2 rule), or an invalidation level from §D is breached.
4. **The impulse fails confirmation.** Neely: an impulse is confirmed only when "the 2-4 trendline is violated in less time than wave-5 took to form", then wave 5 is "completely retraced in less time than it took to form" ([QOW 18](https://www.neowave.com/qow/qow-archive-18.asp)).
   - **Applied to the pullback's own C wave (INFERENCE):** a fast break of C's internal 2-4 line, back toward the trend, supports "correction over". If C's 2-4 line holds and C keeps extending impulsively, it may be a new trend.

---

## B. Pattern catalogue

### B1. Zigzag (5-3-5): "sharp"

- **Structure** (RULE): A is a 5 (impulse or leading diagonal), B is a 3 (any correction), C is a 5 (impulse or ending diagonal) ([EWI Zigzags](https://www.elliottwave.com/waveopedia/zigzags/)).
- **Wave B**:
  - EWP: "the top of wave B is noticeably lower than the start of wave A" (EWI Zigzags).
  - "Wave B must never move beyond the starting point of Wave A" is RULE as stated by practitioners ([Wavetraders](https://wavetraders.com/?p=20047)). It is implied by EWP's description.
  - B retrace: "typically 38.2% to 50%", and above 61.8% "lowers the probability of a sharp zigzag". PRACTITIONER (Wavetraders).
  - Classification threshold: B < 61.8% of A means zigzag; otherwise flat. NEOWAVE ([QOW 98](https://www.neowave.com/qow/qow-archive-98.asp))
  - The closer B is to 61.8% of A, the more likely C < A. A smaller B raises the odds of C reaching 161.8% of A. NEOWAVE ([QOW 309](https://www.neowave.com/qow/qow-archive-309.asp))
- **Wave C**:
  - C must move beyond the end of A. Practitioner RULE (Wavetraders); otherwise it is truncated or another pattern.
  - C length: "usually about equal to that of wave A, although it is not uncommonly 1.618 or .618 times" A. GUIDELINE *(EWP Ch.4, recalled, verify)*. A practitioner echo says C equals A, or 1.618 or 0.618 ([TradingView guide](https://www.tradingview.com/chart/BTCUSD/YaMxVSes-Elliot-Waves-Complete-Guide-Chapter-4-6-ABC-Fib-Lengths/)).
  - C far beyond 161.8% A "may signal an impulse rather than a correction". PRACTITIONER (Wavetraders)
  - An anonymous rule set says C ≥ 70% of B. Unverified PRACTITIONER ([Eleven Patterns PDF](https://c.mql5.com/forextsd/forum/12/the_eleven_elliott_wave_patterns.pdf))
- **Channel** (GUIDELINE, EWI): "One line connects the starting point of wave A and then end of wave B." A parallel line from the end of A "is an excellent tool" for spotting C's end ([Channeling](https://www.elliottwave.com/waveopedia/channeling/)).
- **Where it occurs** (GUIDELINE): "second waves frequently sport zigzags, while fourth waves rarely do" (EWI Zigzags). Zigzags also form A of a flat or triangle legs, W/Y, and so on.

### B2. Double / triple zigzag (W-X-Y[-X-Z])

- **When**: these form "when the first zigzag falls short of a normal target". Each X is "always a corrective wave, typically another zigzag" (EWI Zigzags). GUIDELINE / RULE (X is corrective).
- **Practitioner constraints** (unverified PRACTITIONER, Eleven Patterns PDF):
  - W is a zigzag.
  - X is smaller than W in price, and is any correction except an expanding triangle.
  - Y is a zigzag, with Y ≥ X.
- **X-wave rules** (NEOWAVE, [QOW 7](https://www.neowave.com/qow/qow-archive-7.asp)):
  - X "CANNOT consume more time than the correction before it or the correction after it". It normally takes 1/3–2/3 of the adjacent correction's time.
  - X "CANNOT be more complex" than its neighbours.
  - In complex corrective rallies or declines, X retraces "61.8% or less of the correction right before it".
- **Fibonacci**: Y vs W follows the same C:A ratios. PRACTITIONER (TradingView guide)

### B3. Flat (3-3-5): "sideways"

- **Structure** (RULE): A is a 3, B is a 3, C is a 5 (impulse or ending diagonal) ([EWI Flats](https://www.elliottwave.com/waveopedia/flats/)). A three-wave A "indicates a flat or triangle" (EWI Wave Personality).
- **Wave B depth**:
  - "At least 90%" of A is the widely used EWI-school minimum. It is quoted by Wavetraders ("Wave B must retrace at least 90% of Wave A"), but I could **not** locate it on an EWI page. Treat it as PRACTITIONER and flag it.
  - Jeremy Wagner (CEWA-M) uses 78–138% ([DailyFX](https://www.dailyfx.com/forex/education/trading_tips/daily_trading_lesson/2017/09/04/3-Types-of-Elliott-Wave-Flat-Patterns-to-Know-JWedu.html)).
  - NEoWave uses B ≥ 61.8% (QOW 98).
  - **Spec choice (INFERENCE):** use 61.8% as the zigzag/flat boundary, and keep 90% as an "orthodox flat" confidence tier.
- **Regular flat** (GUIDELINE, EWI): "wave B terminates about at the level of the beginning of wave A", and C ends slightly beyond A's end. Waves A, B and C are roughly equal *(EWP Ch.4, recalled)*.
- **Expanded flat** (GUIDELINE, EWI): this is "Far more common". B "terminates beyond the starting level of wave A", and C "ends more substantially beyond the ending level of wave A".
  - B is typically 1.236–1.382 × A (Wavetraders; *EWP Ch.4 states 1.236 or 1.382, recalled*).
  - C is usually 1.618 × A, or ends beyond A's end by 0.618 × A *(EWP Ch.4, recalled, verify)*.
  - Above 138%, the flat probability "decreases significantly". PRACTITIONER (Wavetraders; Wagner caps B at 138%)
- **Running flat** (GUIDELINE, EWI): B goes beyond A's start, and C "fails to travel its full distance, falling short of the level at which wave A ended".
  - Running flats "tend to occur only in strong and fast markets", and "There are hardly any examples". EWI warns against labelling one prematurely.
  - Neely's limit: b should not exceed 61.8% of the prior wave added beyond its end, or "it is nearly certain a running correction is not unfolding" ([QOW 342](https://www.neowave.com/qow/qow-archive-342.asp)).
  - C after a running B should be ≥ 161.8% of b of B. NEOWAVE ([QOW 21](https://www.neowave.com/qow/qow-archive-21.asp))
- **Depth and placement** (GUIDELINE, EWI):
  - A flat "usually retraces less of the preceding impulse wave than does a zigzag".
  - It occurs "when the larger trend is strong".
  - "the fourth wave frequently sports a flat, while the second wave rarely does."
- **Post-flat strength**: "the larger wave-b, the larger the post-Flat trend". If b > a, the next trend is at least equal to the prior trend and "frequently 161.8% or more". NEOWAVE (QOW 309)

### B4. Triangles (3-3-3-3-3, A-B-C-D-E)

- **Structure** (RULE): five overlapping waves, each a three. They are drawn by "connecting the termination points of waves A and C, and B and D". Most subwaves are zigzags, and C is usually the most complex ([EWI Triangles](https://www.elliottwave.com/waveopedia/triangles/)). Any leg that subdivides into five breaks the pattern ([LuxAlgo](https://www.luxalgo.com/library/concept/triangle/); Wavetraders).
- **Types**:
  - *Contracting*: successive legs shrink. The commonly stated rule is that C never exceeds A's end, D never exceeds B's end, and E never exceeds C's end. This is widely stated but I did not verify it on an EWI page, so treat it as PRACTITIONER.
  - *Barrier*: the horizontal line "always occurs on the side that the next wave will exceed" (EWI).
  - *Running*: B exceeds A's start. This is "extremely common" (EWI).
  - *Expanding*: legs grow. It is rare and hard to trade (LuxAlgo).
  - "all triangles, including running triangles, effect a net retracement of the preceding wave at wave E's end" (EWI).
- **Wave E**:
  - "Wave E can undershoot or overshoot the A-C line" (EWI). Some E waves "stage a false breakdown through the triangle boundary line" (EWI Wave Personality).
  - In the anonymous rule set, E must end within A's price territory (unverified PRACTITIONER).
  - NEoWave contracting triangle: E is "at least 38.2% of wave-C but no more than 99% of wave-C", and C is usually about 61.8% of A.
  - NEoWave expanding triangle: C is 101–161.8% of A ([QOW 24](https://www.neowave.com/qow/qow-archive-24.asp)).
- **Placement**:
  - A triangle typically comes before the final actionary wave: wave 4, wave B, or wave X. It can also be the final component (Y/Z) of a combination ([EWI Combinations](https://www.elliottwave.com/waveopedia/combinations/)).
  - **Wave 2**: EWI does *not* say never. It says "extremely rare occasions", usually a triangle inside a double three. Practitioners (Wavetraders, LuxAlgo) state never.
  - **Spec (INFERENCE):** disallow a triangle as a standalone wave 2.
- **Thrust**:
  - Wave 5 after a wave-4 triangle "is sometimes swift", covering roughly the widest part of the triangle (EWI).
  - "In powerful markets, there is no thrust, but instead a prolonged fifth wave" (EWI).
  - The apex time often "coincides with a turning point" (EWI).
- **Time**: "Give triangles time to develop" (EWI). The NEoWave time tests are in A2.
- **Trader relevance (INFERENCE):**
  - A triangle in wave 4 or B means the next move is the *last* leg of its degree: shorter targets and lower R:R.
  - Entering on the E-end reversal candle is a pullback-end entry, consistent with the user's rules.
  - Entering on a break of the B-D line would be a breakout, which the user does not trade.

### B5. Diagonals

- **Ending diagonal** (EWI, [Diagonals](https://www.elliottwave.com/waveopedia/elliott-wave-pattern-diagonals/)):
  - It subdivides "3-3-3-3-3". Wave 4 "almost always moves into the price territory of" wave 1.
  - The common form is a wedge "within two converging lines".
  - It occurs "primarily in the fifth wave position" and is rarely a C wave. In double or triple threes it appears "only as the final C wave".
  - Throw-over: wave 5 "often ends in a 'throw-over'", a brief break of the 1-3 line, followed by "a spike of relatively high volume". Volume fades during the pattern.
  - What follows is usually "a sharp decline retracing at least back to the level where it began".
  - Labels: GUIDELINE; the 3-3-3-3-3 structure is RULE.
- **Contracting-diagonal length rules**: wave 3 < wave 1, wave 5 < wave 3, wave 4 < wave 2 *(EWP, recalled, verify)*.
  - The practitioner set adds: wave 3 is not the shortest; wave 5 is never the longest of 1, 3, 5; wave 5 > 50% of wave 4 (Eleven Patterns PDF).
- **Leading diagonal** (EWI):
  - It appears in wave 1 or in wave A of a zigzag.
  - Structure is usually 3-3-3-3-3, but possibly 5-3-5-3-5: "the jury is out on a strict definition".
  - It is "typically followed by a deep retracement".
- **Trader relevance (INFERENCE):** an ending diagonal as wave C of a pullback is a strong end-of-correction signal. The throw-over plus a close back inside the wedge is a reversal-candle-at-area event.

### B6. Combinations: double / triple three (sideways)

- "Sideways combinations of corrective patterns are called 'double threes'." Triples "may exist only in theory." Components "more commonly alternate in form". "there never appears to be more than one zigzag in a combination." X "can take the shape of any corrective pattern but is most commonly a zigzag." A triangle is allowable only as the final component. GUIDELINE ([EWI Combinations](https://www.elliottwave.com/waveopedia/combinations/))
- **X depth**: X retraces at least 50% of W (unverified PRACTITIONER, Eleven Patterns PDF). Neely gives X ≤ 61.8% of the prior correction for *complex corrective rallies or declines* (QOW 7). These two numbers conflict because they refer to different contexts (sideways vs directional). Flag this.
- **Typical placement**: wave 4, wave B, and extended sideways ranges. INFERENCE from "horizontal in character".

### B7. Where each pattern occurs (summary)

| Position | Typical | Rare / disallowed |
|---|---|---|
| Wave 2 | Zigzag family (sharp, deep) | Flat rare; triangle "extremely rare" (EWI), never as standalone (practitioners) |
| Wave 4 | Flat, triangle, combination (sideways) | Zigzag rare |
| Wave B | Any; triangles common | — |
| Wave X | Usually a zigzag; a triangle is possible | Expanding triangle disallowed (practitioner) |
| Wave C / 5 | Impulse or ending diagonal (never a correction) | — |

- **Alternation** (GUIDELINE): "If wave two of an impulse is a sharp correction, expect wave four to be a sideways correction, and vice versa" ([EWI Alternation](https://www.elliottwave.com/waveopedia/alternation/)).
- **Alternation inside corrections**: a flat A suggests a zigzag B (same source).

---

## C. Completion: deciding at the time

No source gives a single deterministic "correction complete" test. Neely states plainly that confirmation comes only "shortly after the fact" (QOW 18). The practical approach is a **confluence score**.

### Evidence checklist

| # | Evidence | Source / label |
|---|---|---|
| 1 | **Final leg complete internally**: C (or Y/Z, or E) has completed 5 subwaves (C) or 3 (E), and the pattern has satisfied its rules | RULE-derived |
| 2 | **Minimum time met**: B ≥ A in time (flat/zigzag), C > A in time, and the whole correction ≥ 1/3 of the impulse's time (Similarity & Balance) | NEOWAVE |
| 3 | **Correction channel touch**: C reaches the line through A's end that is parallel to the 0–B line | GUIDELINE (EWI Channeling) |
| 4 | **Price ratio**: C = A (zigzag); C ≈ 1.618 A or A's end + 0.618 A (expanded flat); E within the triangle; Y ≈ W | GUIDELINE (EWP recalled) / PRACTITIONER |
| 5 | **Retracement zone of the impulse**: 38.2 / 50 / 61.8% are the "frequent" relationships | GUIDELINE ([EWI Fibonacci](https://www.elliottwave.com/waveopedia/fibonacci-relationships/)) |
| 6 | **Previous 4th-wave zone**: corrections, "especially when they themselves are fourth waves, tend to register their maximum retracement within the span of travel of the previous fourth wave of one lesser degree, most commonly near the level of its terminus" | GUIDELINE (EWP Ch.2 verbatim, via [reproduction](https://cdn14.thrinacia.com/articles/160-elliott-wave-principle-and-depth-of-corrective-waves)) |
| 7 | **Momentum divergence at C's end** (C vs A, or C wave 5 vs C wave 3). This matches the user's RSI-divergence rule | PRACTITIONER (EWF) |
| 8 | **Volume dry-up**: wave 2 ends on "very low volume and volatility". Triangles contract in volume. Exception: an ending-diagonal throw-over ends on a volume spike | GUIDELINE (EWI) |
| 9 | **Break of C's own 2-4 line**, ideally faster than C's wave 5 took to form | NEOWAVE (QOW 18, adapted) |
| 10 | **Break of the correction's structure line**: the B–D line in triangles; for a zigzag, a return through the 0–B line. These are *confirmation*, not entry, because entering on them is a breakout | INFERENCE |

**Typical depth**

- **Wave 2**:
  - EWI: second waves "often erase most of the gains from wave 1".
  - NEoWave: in a trending impulse, wave 2's c-leg "must conclude at 61.8% or less of wave-1". In terminal patterns up to 99%, "never 100% or more" ([QOW 1079](https://www.neowave.com/qow/qow-archive-1079.asp)).
  - Orthodox RULE: wave 2 never retraces past wave 1's start.
- **Wave 4**: shallower; a flat or triangle; the previous-fourth-wave zone. RULE: no overlap with wave 1 (outside diagonals). MTPredictor allows a "slight" practical dip.
- **B (of zigzag)**: 38.2–50% typical; < 61.8% (NEoWave).
- **B (of flat)**: ≥ 61.8% (NEoWave) or ≥ 90% (EWI-school), up to about 138%.
- **General**: corrections often retrace 38.2–61.8% of the prior impulse. PRACTITIONER ([EWF](https://elliottwave-forecast.com/trading/elliott-wave-corrective-waves/))

**Truncation**

- A running flat C is truncated relative to A (EWI Flats). A wave-5 truncation ("failure") is an EWP concept that typically follows a very strong 3rd wave *(EWP, recalled)*.
- **Spec (INFERENCE):** allow C to fall short of A's end only when B > 100% of A (running flat context) *and* the market is "strong and fast". Otherwise, require C to exceed A's end before calling the correction complete.

---

## D. Invalidation (stop placement)

The stop sits beyond the level that proves the count wrong. Pullback-long example; mirror for shorts.

| Pattern being traded | Count is wrong if… | Label |
|---|---|---|
| Wave 2 pullback | Price goes below wave 1's start | RULE |
| Wave 4 pullback | Price enters wave 1's territory (non-diagonal) | RULE (MTPredictor allows a "slight" dip in practice) |
| Zigzag (as the correction) | During B: B exceeds A's start. After C ends: price makes a new extreme beyond C's end (C extending or more complex) | Practitioner RULE; INFERENCE |
| Flat | B > ~138% of A makes a flat unlikely (PRACTITIONER). Under NEoWave, a running-B limit applies (QOW 342) | PRACTITIONER / NEOWAVE |
| Contracting triangle | A leg exceeds the prior same-side extreme; E goes beyond C's end; any leg is a 5 | PRACTITIONER / RULE |
| Ending diagonal (C or 5) | The throw-over keeps extending, or wave 5 becomes longer than wave 3 in a contracting diagonal | EWP recalled / PRACTITIONER |
| Combination | X exceeds W's start (it would then be a new trend or a different count) | INFERENCE |
| Any correction | It is exceeded by a clean impulsive 5 in the counter-trend direction | RULE-derived |

**Spec stop (INFERENCE):** place the stop just beyond the correction's terminal extreme (C, E or Y end), plus a buffer. Use the hard invalidation level (the wave 1 start for a wave 2; the wave 1 end for a wave 4) only as the "count dead" level. The R:R ≥ 3 check must use the actual stop distance. Because a stop beyond C's extreme can be tight, the alternate count, "C is extending", is the main risk. Neely's minimum-time rules (A2) are the filter against entering an unfinished C.

---

## E. Algorithmic and academic work; pitfalls

**Academic and algorithmic work**

- **Kotyrba, Volná, Bražina, Jarušek (2012)**, "Elliott Waves Recognition Via Neural Networks", ECMS 2012, pp. 361–366 ([DOI](https://unpaywall.org/10.7148%2F2012-0361-0366)).
  - A backpropagation network learns pattern templates.
  - The authors note that recognition error is hard to estimate and that the learned behaviour is opaque.
  - A 2018 IGI chapter compiles this line of work ([IGI](https://www.igi-global.com/chapter/recognition-of-patterns-with-fractal-structure-in-time-series/196961)).
- **WASP (Wave Analysis Stock Prediction)**: a neuro-fuzzy system built on EW, available online 4 Feb 2011 ([abstract](https://www.datalearner.com/academic/journal-papers/0957-4174/volumes-and-issues/165/paper-detail/82391); [TUC repository](https://dias.library.tuc.gr/view/57611?locale=en)). Authors and venue are from memory, not confirmed by the page: Atsalakis, Dimitrakakis & Zopounidis, *Expert Systems with Applications* (ISSN 0957-4174, which matches). Results are described only as "very encouraging", with no robust out-of-sample metrics in the abstract.
- **ElliottAgents** (Chudziak & Wawer, PACLIC 2024, [arXiv 2507.03435](https://arxiv.org/html/2507.03435v1)) and Wawer et al. 2024, *Applied Sciences*, DOI 10.3390/app142411897.
  - An LLM multi-agent system with a tool that "finds all possible impulsive and corrective wave patterns". Only ABC corrections are implemented; flats, triangles and truncations are left as future work.
  - Only 8–28 patterns were detected per series, so the reported accuracies (e.g. 53.6% → 67.9%) rest on tiny samples, with no baselines.
- **Practitioner software**: zigzag-pivot scanners such as LuxAlgo and TradingView "Elliott Wave" scripts. MTPredictor's position is that "Corrections and corrective waves do not have a set of rules associated with them", and it focuses on the ideal 5-wave pattern instead ([MTPredictor](https://www.mtpredictor.com/elliott-wave-rules)).
- **Neely's NEoWave** is the most quantified framework (monowave rules, the price/time ratios above). It is still applied manually. I found no published, validated automation of full NEoWave.

**Pitfalls (for the spec)**

1. **Multiple valid counts.** Corrections "are more varied and harder to label until they're complete" (EWI). Always carry a primary count plus alternates. For example, zigzag A → still needs C; flat → C can expand; "triangle" may turn into a combination. Neely: the "B" you see may be "wave-a of wave-B" (QOW 98/509).
2. **Pivot-detection sensitivity.** Zigzag-threshold choice changes the counts. Use Similarity & Balance (the 1/3 price-or-time rule) to decide which swings are the same degree. (INFERENCE)
3. **Premature completion.** EWI warns: "Give triangles time to develop". Running flats should not be labelled prematurely. NEoWave minimum-time rules are the codable antidote.
4. **Thin evidence base.** Published studies use small samples and lack baselines. Critics argue that EW is subjective and hard to test ([TurtleTrader critique](https://www.turtletrader.com/wavejunk/)).
   - **Spec consequence (INFERENCE):** use EW structure only as a *context filter*. Make the actual trigger the user's objective, closed reversal candle at a confluence area with R:R ≥ 3.
5. **Number provenance.** Several commonly repeated numbers lack a primary EWI citation here and should be tunable, not hard-coded "rules": flat B ≥ 90%, B ≤ 138%, C ≥ 70% of B, X ≥ 50% of W, and the contracting-triangle leg rules.

---

## F. Distilled codable logic (INFERENCE, built from the above)

1. **Context.** Identify the prior impulse I (5 waves, or a strong one-directional leg). The candidate correction K must have the same degree as I: K's price ≥ 1/3 of I's price, or K's time ≥ 1/3 of I's time (NEOWAVE).
2. **Classify K from its first two legs A and B.**
   - A is a 5 → zigzag family; expect B < 61.8% A, B time ≥ A time, then a 5-wave C beyond A's end.
   - A is a 3 and B ≥ 61.8% A → flat; expect a 5-wave C to around A's end (regular), beyond it (expanded, 1.0–1.618 A), or short of it (running, only if B > A).
   - B shorter in time than A, with B < A in price → triangle candidate; wait for E.
3. **Completion zone.** Require at least 3 of: C:A ratio hit, channel line touch, 38.2–61.8% retracement of I or the prior-4th-wave zone, momentum divergence, volume dry-up, minimum time met (C time > A time).
4. **Trigger.** A closed reversal candle in the zone (the user's rule). Optional confirmation: a fast break of C's internal 2-4 line.
5. **Stop.** Beyond the C/E/Y extreme. Kill the count at the hard invalidation (D). Skip the trade if R:R < 3.
6. **Position filter.**
   - Prefer wave 2 / zigzag, and wave 4 / flat-triangle consistent with alternation.
   - Downgrade triangles and wave-B contexts, because the next leg is terminal.
   - Reject when the counter-move is a clean 5 that is "larger and faster" than every prior counter-move (reversal risk).

---

### Sources

- [EWI Corrective Waves](https://www.elliottwave.com/waveopedia/corrective-waves/)
- [EWI Zigzags](https://www.elliottwave.com/waveopedia/zigzags/)
- [EWI Flats](https://www.elliottwave.com/waveopedia/flats/)
- [EWI Triangles](https://www.elliottwave.com/waveopedia/triangles/)
- [EWI Diagonals](https://www.elliottwave.com/waveopedia/elliott-wave-pattern-diagonals/)
- [EWI Combinations](https://www.elliottwave.com/waveopedia/combinations/)
- [EWI Alternation](https://www.elliottwave.com/waveopedia/alternation/)
- [EWI Wave Personality](https://www.elliottwave.com/waveopedia/wave-personality/)
- [EWI Channeling](https://www.elliottwave.com/waveopedia/channeling/)
- [EWI Fibonacci](https://www.elliottwave.com/waveopedia/fibonacci-relationships/)
- [EWP depth-of-corrections excerpt](https://cdn14.thrinacia.com/articles/160-elliott-wave-principle-and-depth-of-corrective-waves)
- NEoWave QOW: [7](https://www.neowave.com/qow/qow-archive-7.asp), [17](https://www.neowave.com/qow/qow-archive-17.asp), [18](https://www.neowave.com/qow/qow-archive-18.asp), [21](https://www.neowave.com/qow/qow-archive-21.asp), [24](https://www.neowave.com/qow/qow-archive-24.asp), [78](https://www.neowave.com/qow/qow-archive-78.asp), [98](https://www.neowave.com/qow/qow-archive-98.asp), [262](https://www.neowave.com/qow/qow-archive-262.asp), [309](https://www.neowave.com/qow/qow-archive-309.asp), [342](https://www.neowave.com/qow/qow-archive-342.asp), [411](https://www.neowave.com/qow/qow-archive-411.asp), [509](https://www.neowave.com/qow/qow-archive-509.asp), [1079](https://www.neowave.com/qow/qow-archive-1079.asp), [1109](https://www.neowave.com/qow/qow-archive-1109.asp)
- [MTPredictor rules](https://www.mtpredictor.com/elliott-wave-rules)
- [Wavetraders zigzag](https://wavetraders.com/?p=20047)
- [Wavetraders flats](https://wavetraders.com/?p=20185)
- [Wavetraders triangles](https://wavetraders.com/?p=20071)
- [J. Wagner / DailyFX flats](https://www.dailyfx.com/forex/education/trading_tips/daily_trading_lesson/2017/09/04/3-Types-of-Elliott-Wave-Flat-Patterns-to-Know-JWedu.html)
- [Elliottwave-Forecast](https://elliottwave-forecast.com/trading/elliott-wave-corrective-waves/)
- [LuxAlgo triangle](https://www.luxalgo.com/library/concept/triangle/)
- [LuxAlgo flat](https://www.luxalgo.com/library/concept/flat/)
- [LuxAlgo diagonals](https://www.luxalgo.com/library/concept/diagonals/)
- [Eleven Patterns PDF (anonymous)](https://c.mql5.com/forextsd/forum/12/the_eleven_elliott_wave_patterns.pdf)
- [Kotyrba et al. 2012](https://unpaywall.org/10.7148%2F2012-0361-0366)
- [WASP 2011](https://www.datalearner.com/academic/journal-papers/0957-4174/volumes-and-issues/165/paper-detail/82391)
- [ElliottAgents](https://arxiv.org/html/2507.03435v1)
- [TurtleTrader critique](https://www.turtletrader.com/wavejunk/)
