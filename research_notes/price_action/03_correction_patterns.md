# 03. Correction / Pullback Patterns: Classical, Brooks, Elliott — Statistics and Codable Rules

Context: NIFTY/BANKNIFTY/SENSEX option seller, 15M chart, enters in the impulse direction only at the END of a confirmed pullback (no breakout entries), R:R ≥ 3, trades last ~2 days. This note extends `/home/claude/research_notes/correction_patterns_reference.md` (Elliott corrective catalogue, NEoWave time rules) and `/home/claude/research_notes/Leg and level strength research/elliott_wave.md` (EW hard rules, automation failure modes). Elliott internals are **not** repeated here; this file adds the classical-pattern statistics (Bulkowski), the Al Brooks pullback taxonomy, the mapping between the three vocabularies, and completion/failure signals.

Tags: **[RULE]** identification rule from a named source · **[STAT]** a published number · **[PRAC]** practitioner heuristic · **[INF]** my synthesis for the spec.

Data caveat on all Bulkowski numbers: US stocks, daily bars, mostly bull-market samples, "perfect trades" (entry at breakout, exit at ultimate high/low), no costs. They describe *tendencies of shape*, not NIFTY 15M edge. Use them to rank patterns and set expectations, never as hard-coded probabilities.

---

## 1. Takeaway

1. Every classical continuation pattern is a *pause whose shape tells you how the pause is likely to end*. Across Bulkowski's database the important numbers are not "breakout direction" (mostly 55–68% with the trend) but **failure rate, throwback/pullback rate (~58–74%), and bust rate (median 24% up / 40% down)**. For a pullback-end trader these say: a with-trend reversal inside the pattern is the higher-probability event, and the "breakout" is where most people lose.
2. Flags/pennants (< 3 weeks daily, i.e. short on any timeframe) are the weakest patterns statistically (break-even failure 44–54%, target hit 35–46%) *unless tight with a near-vertical pole*. Rectangles and ascending triangles with up-breakouts are the strongest (failure 15–17%, target 70–78%). Rising wedges with down-breakouts are the worst in the whole database (failure 51%, bust 63%).
3. Bulkowski's measured-move study (31,000+ MMU samples) is the single most useful statistic for this trader: **the deeper the corrective phase retrace (≥ 70%, cluster 76–95%), the more often the second leg equals the first**. Shallow (36–50%) retraces are where misses cluster. This contradicts the "shallow pullback = strong trend" folk rule for *target attainment* (not for continuation probability).
4. Al Brooks supplies the real-time grammar the statistics lack: most pullbacks have **two legs** (High 2 / Low 2), a three-push sloping pullback is a **wedge flag** and trades like one, a horizontal pullback late in a trend near a magnet is a **final flag** (reversal that starts as continuation), and a **failed breakout** of a pullback's own line is the entry trigger, not the breakout itself.
5. Mapping: Brooks' two-legged pullback ≈ Elliott zigzag/flat (ABC) ≈ classical flag; Brooks' wedge flag / three-push ≈ EW ending diagonal (as C) or triangle ≈ classical wedge/pennant; Brooks' trading-range pullback ≈ EW flat/combination ≈ rectangle. The three vocabularies describe one object.
6. Completion is a *confluence*, never a single rule: far-line touch + leg count satisfied (2 legs or 3 pushes) + minimum-time (NEoWave, prior note) + reversal bar + (optionally) throw-over/failed breakout of the far line. Failure is cleaner: a *close* beyond the far line that is **not** reclaimed within 1–3 bars, or a counter-move that is larger and faster than every prior counter-move in the impulse.

---

## 2. Cited findings per pattern

All Bulkowski numbers are from thepatternsite.com, bull-market samples unless noted. "Fail" = break-even failure rate (price moves < 5% after breakout). "Hit" = % meeting measure-rule target. "TB/PB" = throwback (after up-break) / pullback (after down-break) rate.

### 2.1 Flags (parallel or near-parallel lines, tilted against trend)
- [RULE] Prior move: "unusually steep" flagpole lasting several days; "without a straight-line or quick price run, there is no flag". Duration < 3 weeks; longer = rectangle/channel. Price between two parallel lines. — [Bulkowski, Flags](https://thepatternsite.com/flags.html)
- [STAT] Breakout up 60%. Fail 44% (up) / 45% (down). Avg move 9% / 8%. Hit 46% / 46%. Volume trend down 74–77%. "Not ranked" because measured by the short-term swing. — same.
- [STAT] Measure rule: pole height A→B × 46%, added to flag low (up) / subtracted from flag high (down). Half-staff (post-move = pre-move) is the ideal, not the norm. — same.
- [PRAC] Best: inbound trend up with flag tilting down; tight (no white space, no pokes outside lines) beats loose; flag sitting on a flat base; within a third of yearly low. — same.
- [STAT] High-and-tight flag (prior rise ≥ 90% in ≤ 2 months, then consolidation): fail 15%, avg rise 39%, TB 67%, hit 82% (half-height target), 1,028 trades. — [Bulkowski, HTF](https://thepatternsite.com/htf.html). Secondary summary: loose bull flags 45% success / +9%, tight 85% / +39% — [LiberatedStockTrader](https://www.liberatedstocktrader.com/bull-flag-pattern/) (affiliate site; treat as a restatement).
- [PRAC] The 3-week limit is "arbitrary"; flags "most often slope against the prevailing trend". — [Bulkowski, FlagDay](https://thepatternsite.com/FlagDay.html)

### 2.2 Pennants (converging lines, short)
- [RULE] Looks like a short symmetrical triangle; ≤ 3 weeks (longer = sym. triangle or wedge); steep pole of several days. — [Bulkowski, Pennants](https://thepatternsite.com/pennants.html)
- [STAT] Breakout up 57%. Fail 54% / 54%. Avg move 7% / 6%. Hit 35% / 32%. Volume down 86%. Marks the midpoint of the move only ~30% of the time (inbound 11 days/19%, outbound 10 days/14%). 1,600+ trades. — same.
- [PRAC] Performance suffers when the pennant slopes *with* the trend; tight beats loose; flat base below helps. — same.

### 2.3 Symmetrical triangle
- [RULE] Two converging lines (lower rising, upper falling); price must cross side to side and "fill" the triangle; ≥ 3 touches on one line and ≥ 2 on the other, as distinct peaks/valleys. Confirmed only on a close outside a line. — [Bulkowski, ST](https://www.thepatternsite.com/st.html)
- [STAT] Breakout up 60%; occurs at 74% of the distance to the apex. Fail 25% (up) / 37% (down). Avg move 34% / 12%. TB/PB 62% / 65%. Hit 58% / 36%. Rank 36/39 up, 34/36 down. Price turns at the apex 60% of the time. Inbound trend down 84–86%. 3,000+ trades. — same.
- [STAT] Busted down-breakouts: 48%; sym. triangles "tend to double bust". Bust definition: close outside, move < 10%, then close beyond the *opposite side of the pattern* (top/bottom, not the line). — [Bulkowski, BustSymTriangles](https://thepatternsite.com/BustSymTriangles.html)
- [PRAC] Edwards & Magee (recalled, not fetched): a valid breakout should come between ~2/3 and 3/4 of the way to the apex; later breaks are weak. LuxAlgo restates as "middle-to-late thirds; a drift into the apex usually dissolves the setup". — [LuxAlgo triangles](https://www.luxalgo.com/library/concept/ascending-descending-symmetrical-triangle.md); another guide: "between halfway and three quarters"; a break *at* the apex "doesn't count". — [ChartingLens](https://chartinglens.com/blog/triangle-chart-patterns-guide)

### 2.4 Ascending triangle (flat top, rising lows)
- [RULE] Same touch/crossing rules; top horizontal, bottom rising. — [Bulkowski, AT](https://www.thepatternsite.com/at.html)
- [STAT] Breakout up 63%, at 64% of way to apex. Fail 17% / 38%. Avg 43% / 13%. TB/PB 64% / 63%. Hit 70% / 44%. Rank 16/39 up, 30/36 down. Volume down ≥ 78%. Busted down-breakouts 46% (then avg rise 36%; 67% single busts). Busted up-break definition: rise < 10% then close *below pattern bottom*. 1,400+ trades. — same.

### 2.5 Descending triangle (flat bottom, falling highs)
- [RULE] Horizontal bottom, down-sloping top; same touch rules; "nearly fill the space, avoid white space". — [Bulkowski, DT](https://thepatternsite.com/dt.html)
- [STAT] Breakout up 53% (up 63% if price *rose into* the pattern). Median breakout 61–65% to apex. Fail 22% / 23%. Avg 38% / 15%. TB/PB 60% / 58%. Hit 64% / 50%. Rank 33/39 up, 15/36 down. Volume recedes 78%. Performance "almost halved since the 1990s". — same.
- [PRAC] Triangles far up a trend fail faster; up-sloping volume inside the pattern "dramatically improves" median performance (the one exception to the volume-contraction rule). — same.

### 2.6 Rising wedge (both lines slope up, converging)
- [RULE] ≥ 5 touches (3 one side, 2 other); minimum 3 weeks (shorter = pennant); confirm on close outside. — [Bulkowski, Rising wedge](https://thepatternsite.com/risewedge.html)
- [STAT] Breakout down 60%. Fail 19% (up) / **51% (down)**. Avg 38% / 9%. TB/PB 72% / 72%. Hit 63% / 32%. Rank 32/39 up, **36/36 (last)** down. Up-breaks at ~67% to apex. Volume down 79%. Bust rate after down-break **63%**, the highest in the database. — same; [BustPerformance](https://thepatternsite.com/BustPerformance.html)
- [PRAC] Measure rule for down-break = the wedge's lowest valley (i.e. full retrace of the wedge), alternative height × 32%. "Some of the worst performing chart patterns." — same.

### 2.7 Falling wedge (both lines slope down, converging)
- [RULE] Same 5-touch / 3-week / close-outside rules. — [Bulkowski, Falling wedge](https://thepatternsite.com/fallwedge.html)
- [STAT] Breakout up 68%, at 61–62% to apex. Fail 26% / 29%. Avg 38% / 14%. TB/PB 62% / **74%**. Hit 62% / 29%. Rank 31/39 up, 27/36 down. Volume down 72–75%. 800+ trades. — same.
- [PRAC] Up-break target = highest peak of wedge (full retrace). Tall > short; gap or heavy volume on breakout day helps. After a down-break, price "sometimes curls around the front of the wedge and rises sharply". Author "avoids wedges". — same.

### 2.8 Rectangle (two horizontal parallel lines)
- [RULE] ≥ 3 touches on one line, 2 on the other, distinct peaks/valleys, "be flexible". — [Bulkowski, Rect tops](https://thepatternsite.com/recttops.html)
- [STAT] (tops, prior trend up) Breakout up 63%. Fail **15%** / 34%. Avg **51%** / 13%. TB/PB 66% / 64%. Hit **78%** / 54%. Rank **4/39** up, 32/36 down. Volume down 70%. 1,000+ trades. — same.
- [STAT] **Partial rise predicts a down-break 75%; partial decline predicts an up-break 79%.** Across 1,831 rectangles/broadening patterns, partial rise occurred in 28%, partial decline in 24%; a throwback/pullback is *less* likely after a partial rise/decline. — same; [PartialRises…](https://thepatternsite.com/PartialRisesDeclinesThrowsPulls.html)
- [STAT] Rectangle width is unrelated to the length of the inbound rise (1,070 rectangles, 1995–2023). — [TsversusWidth](https://thepatternsite.com/TsversusWidth.html)

### 2.9 Measured move (two-leg move with corrective phase) — the pullback trader's own pattern
- [RULE] MMU: minor low → minor high (leg 1), corrective phase, minor high (leg 2). Algorithm requires corrective retrace ≥ 70%. Buy "once the second leg begins (point C)"; exit if price drops below C. — [Bulkowski, MMU](https://thepatternsite.com/mmu.html); MMD mirror — [MMD](https://thepatternsite.com/mmd.html)
- [STAT] MMU: leg 1 avg 36% / 38 days; corrective phase 48% retrace / 27 days; leg 2 31% / 33 days; hit 60%. MMD: 20%/26d, 48%/21d, 21%/27d; hit 43%. — same.
- [STAT] Retrace study (497 stocks, 1980–2018, 31,000+ MMU, 21,000+ MMD): MMU hits cluster at **76–95% retrace**, misses at 36–50%; 9% of successful MMUs retraced 100% of leg 1 and still hit. MMD hits cluster at 71–100%, misses at 41–60%. Slope of legs and angle of turns had **no** influence; only retrace size mattered. — [MMRetrace](https://thepatternsite.com/MMRetrace.html)
- [STAT] Simple ABC correction (MMD nested in MMU): 36% of the time price reverses at the prior high E (double top). Entry variants: close above E→B trendline, close above A, close above B/E. — [Bulkowski, ABC](https://thepatternsite.com/abc.html); [S&C 2005 article](https://store.traders.com/stcov235siab.html)
- [INF] For an intraday option seller the "corrective phase" of an MMU *is* the tradable pullback; Bulkowski's finding that deep retraces (≥ 70%) produce the fullest second legs is the quantitative backing for the user's "pullback into a real buyer area" rule, but note it also raises the odds that the pullback is a reversal — hence the reversal-candle requirement.

### 2.10 Throwbacks / pullbacks / busts (behaviour *after* a pattern line is crossed)
- [STAT] Throwback: by convention within 30 days; 58% of 10,305 up-breakouts since 2000; price climbs ~6 days, avg 8% (most 4–10%), returns to breakout in ~10 days total; after return, 65% resume up, 35% keep falling below the pattern. High-volume breakouts throw back ~70%. — [Throwbacks](https://www.thepatternsite.com/throwbacks.html)
- [STAT] Pullback: 58% of 8,765 down-breakouts; ~6 days down, avg 9%, return in ~11 days; after return only **53% resume down**, 47% keep rising. — [Pullbacks](https://thepatternsite.com/pullbacks.html)
- [STAT] Performance with vs without full retrace: throwback that stays above breakout-day low → avg rise 41.3% (1,717), that drops below → 26.7% (3,311). Pullback partial 25.1% vs full 17.3%. 30 pattern types, 9,372 samples. — [ThrowPull](https://thepatternsite.com/ThrowPull.html)
- [STAT] Bust rates: median 24% (up-breaks) / 40% (down-breaks); highest down = rising wedge 63%; of busted patterns, median split single 53% / double 31% / triple+ 16% (up), 67/4/28 (down). Single-busted patterns outperform non-busted (median 23% vs 15% down→up; 53% vs 42% up→down). Price "typically moves no more than 10%" before busting. — [BustPerformance](https://thepatternsite.com/BustPerformance.html)
- [INF] Translated to the user's rule set: the move *out* of a pullback pattern is retraced ~58% of the time, and resumes after the retrace only 53–65% of the time; a close beyond the far line that reverses within a few bars (bust) is followed by a *bigger* move than a clean breakout. This is the statistical case for entering on the failed breakout / reversal at the far line rather than on the breakout.

### 2.11 Al Brooks pullback taxonomy (qualitative, with his stated odds)
- [RULE] Pullback: "a temporary countertrend pause within a trend… that does not retrace past the start of that move"; "a small trading range where traders expect the trend to resume soon". — [Brooks glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/)
- [RULE] High 1 / High 2 (bull flag): High 1 = first bar whose high exceeds the prior bar's high in a pullback; High 2 = the next such bar after a *lower high* forms, i.e. the second leg. Low 1/Low 2 mirror. "Every small double bottom is a High 2 bull flag." "A triangle is a sideways High 3 or Low 3 flag, and a wedge is a sloped triangle." — glossary; [MoneyShow summary](https://www.moneyshow.com/articles/tebiwkly08-56291/)
- [PRAC] Two legs: "all strong moves usually have at least two legs even if the second one falls short"; "any time there is a trendline breakout, the chances are high that there will be a second leg"; a climax "is usually followed by a two-legged correction"; "wedges usually don't fail before having at least a two-legged correction". — [Brooks excerpts](https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754); [Brooks micro-trendlines](https://www.brookstradingcourse.com/futures-market/trading-strategies-microtrendlines-microchannels/) ("that is why so many pullbacks have two legs… a second attempt that fails"). One-legged pullbacks dominate only in the strongest trends. — [TradingSetupsReview](https://www.tradingsetupsreview.com/4-price-action-trading-strategies-pullback-traders/)
- [RULE] Wedge / three pushes: "any pattern with three (sometimes four or five) pushes that is sloped up or down. It need not converge, and the third push need not exceed the second." "Any three-push move should be treated exactly like a wedge." Wedge pullback (High 3 / Low 3) is a with-trend setup: "enter on the first signal". — glossary; MoneyShow
- [RULE] Final flag: "a trend-reversal pattern that begins as a continuation pattern": trend + mostly horizontal pullback (possibly one bar) + nearby magnet (measured-move target, channel line) + other reversal signs. Swing probability ~40%, ~60% after a strong breakout. After a failed final-flag breakout expect a countertrend move of "at least two legs". — MoneyShow; Brooks excerpts
- [RULE] Failed breakout: "reverses within a bar or a few bars of the breakout". Failed failure ("failed failed breakout") = original trend resumes and becomes a breakout pullback. Breakout pullback: 1–5 bar pullback shortly after a breakout; "a very reliable signal" (with-trend second attempt). Breakout test: pullback to the original entry price, possibly 20+ bars later. — glossary; micro-trendlines page
- [STAT-ish] Brooks' odds: minor reversal grows into an opposite trend ~20%; bull channel breaks *below* its trendline ~75% (so "any bull channel is a bear flag"); breakout above a bull channel succeeds ~25%; "in a trend most reversal patterns fail and most continuation patterns succeed"; the longer a trading range lasts the more likely it becomes a reversal; 5–20 sideways bars = tight balance where breakouts "can be costly". — glossary; MoneyShow; excerpts
- [RULE] Trend channel line overshoot + reversal = "effectively wedge climaxes", should have ≥ 2 legs. After a trendline break, the first pullback "will almost always form a lower high" (bear case) and tests the old extreme. — micro-trendlines page; excerpts

### 2.12 Elliott-to-classical links found in sources
- [PRAC] "The Ending Diagonal Pattern of Elliott Wave Theory = The Wedge Pattern in classic chart patterns"; rising wedge in uptrend = reversal, in downtrend = continuation (mirror for falling). — [TradingView, ZqcHIsuf](https://de.tradingview.com/chart/BTCUSDT/ZqcHIsuf-Wedge-Pattern-Reversal-Continuation-Pattern)
- [PRAC] Elliott triangles "are the same triangles that chartists have been working with for years", but "the breakout is dependent upon the succeeding wave, not the shape of the pattern": a descending triangle in a bull wave 4 breaks *up*. — [Traders.com working-money](https://technical.traders.com/wm/display.asp?art=297)
- [PRAC] Bulkowski's own EW page: corrections are three waves, "an initial five wave move against the prevailing trend is not the end of a correction"; ABC "can be deceptive and difficult to identify". No statistics. — [Bulkowski, EWCorrective](https://www.thepatternsite.com/EWCorrective.html)
- [PRAC] LuxAlgo: form tests — sharp deep A + partial B → zigzag; B returning near A's origin → flat; converging shrinking swings → triangle; completion "confirmed after the fact, by a new five-wave move… that breaks the correction's boundary". — [LuxAlgo corrective wave](https://www.luxalgo.com/library/concept/corrective-wave.md)
- Gap: no source gives an explicit flag↔zigzag or rectangle↔flat equivalence; the table below is [INF].

---

## 3. Mapping table (classical ↔ Elliott ↔ Brooks) [INF unless noted]

| Classical pattern (Bulkowski/E&M) | Elliott corrective form | Brooks name | Pullback-end signature | Statistical note |
|---|---|---|---|---|
| Flag (parallel, counter-trend tilt, short) | Zigzag (5-3-5) or regular flat when near-horizontal; sometimes only wave A–B of a bigger correction | Two-legged pullback → **High 2 / Low 2**; "small double bottom/top bull flag" | 2nd leg touches lower channel line + reversal bar; failed break of the flag's far line | Fail 44%, hit 46%; tight pole-flags far better (fail 15%) |
| Pennant (converging, short) | Small contracting triangle, or ending-diagonal C of a shallow zigzag | **Wedge flag / High 3** when sloped; tight trading range when flat | 3rd push into far line, overshoot and close back inside | Weakest classical pattern: fail 54%, hit 35% |
| Falling wedge in uptrend (continuation) | Ending diagonal as wave C (3-3-3-3-3), or double zigzag W-X-Y | **Wedge bull flag** (three pushes down, sloped) | Throw-over of lower line + reversal bar; "curls around the front of the wedge" | Up-break 68%, TB 62%, fail 26% |
| Rising wedge in downtrend (continuation) | Ending diagonal C of an upward correction | **Wedge bear flag** | Throw-over of upper line, then bear bar closing near low | Down-break 60%, PB 72%, fail 19% up / 51% down |
| Rising wedge in uptrend (reversal) | Ending diagonal as wave 5 | **Wedge top / three pushes up / parabolic wedge climax** | Trend-channel overshoot and reversal; expect ≥ 2 legs down | Bust rate after down-break 63%: reversals from these often fail first |
| Symmetrical triangle (longer) | Contracting triangle (A-B-C-D-E) in wave 4 / B / X | Triangle = "sideways High 3 / Low 3 flag"; **tight trading range** | Wave E undershoots/overshoots A-C line, reversal bar; apex-time turn (60%) | Fail 25% up / 37% down, TB/PB 62–65%, double-busts common |
| Ascending triangle in uptrend | Barrier triangle (flat B-D on the side the next wave will exceed) | Bull flag with higher lows; breakout pullback after flat line breaks | 3rd higher low at rising line + reversal bar (pre-breakout entry) | Fail 17%, hit 70%, TB 64% |
| Descending triangle in downtrend | Barrier triangle, flat side down | Bear flag with lower highs | 3rd lower high at falling line | Fail 23%, hit 50% |
| Rectangle (horizontal, longer) | Flat (3-3-5), running flat, or double-three combination W-X-Y | **Trading range** ("often a pullback that lasts long enough to lose its certainty"); final flag if late in trend near a magnet | Partial rise/decline (75–79% directional predictor), then reversal bar at the range edge | Up-break fail 15%, hit 78%; longer range → higher reversal odds (Brooks) |
| Measured move corrective phase | Whole ABC (any form) between two same-degree impulses | "Leg 1 = Leg 2", **breakout pullback** when it retests the prior high/low | Retrace ≥ 70% cluster gives best leg-2 completion | Hit 60% (MMU) / 43% (MMD) |
| Failed breakout of any of the above | Throw-over / false break at wave E or diagonal wave 5 | **Failed breakout**, **failed final flag**, **breakout test** | Close back inside line within 1–3 bars | Busted patterns outperform clean breakouts |

---

## 4. Codable identification rules (synthesis; sources as tagged)

Work on confirmed swing pivots (ZigZag with an ATR-scaled threshold; see elliott_wave.md Q3 on repainting). Let I = the prior impulse leg (price range `H_I`, bars `T_I`); let K = the candidate pullback with pivots p0 (impulse end), p1, p2, … .

1. **Pole / impulse qualification** [RULE Bulkowski flags/pennants; INF]: I must be "unusually steep": slope of I ≥ k × median slope of the last N legs (k≈1.5), and I ≥ 1/3 of the prior swing in price (NEoWave similarity, prior note). No qualifying I → no flag/pennant; treat as a range.
2. **Same-degree test** [NEoWave, prior note]: K price ≥ 1/3 H_I **or** K time ≥ 1/3 T_I. Otherwise K is a lower-degree wiggle; keep waiting.
3. **Leg counting** [Brooks High 2 / Low 2]: in a bull pullback, count a leg each time a bar's high exceeds the prior bar's high *after* a lower high has formed. Pullback legs = 1 (High 1), 2 (High 2), 3 (High 3 = wedge flag). Mirror for bears. Default expectation: ≥ 2 legs [PRAC Brooks]; accept a 1-leg pullback only when I is a tight/micro channel (Brooks: strongest trends) — otherwise wait for leg 2.
4. **Shape classification** on the pivots of K (needs ≥ 4 pivots for lines, ≥ 2 touches per line, ≥ 3 on one side) [RULE Bulkowski touches]:
   - Fit upper line U through K's highs, lower line L through K's lows (least-squares on pivots, tolerance ≤ 0.1–0.2 ATR).
   - **Flag**: slopes(U) ≈ slopes(L) (|Δslope| < 20% of mean |slope|), tilt against I, duration short relative to I (T_K ≤ ~1.5 T_I; Bulkowski's < 3 weeks is daily-specific). Tight if ≤ 10% of bars poke outside and little white space.
   - **Pennant / symmetrical triangle**: slopes opposite sign, converging; successive swing ranges shrinking (each < prior, NEoWave ~0.618–0.85 per leg, prior notes); price "fills" the shape (bars touch both lines alternately). Pennant if T_K short vs I, triangle otherwise.
   - **Rising / falling wedge**: both slopes same sign and converging; ≥ 5 touches (3/2) [RULE Bulkowski]; counter-trend wedge = wedge flag (Brooks High 3). Brooks relaxation: three pushes suffice even if lines do not converge — flag it as "three-push" with lower confidence.
   - **Ascending / descending triangle**: one line slope ≈ 0 (|slope| < 0.1 ATR per bar), other converging.
   - **Rectangle / trading range**: both slopes ≈ 0; ≥ 3/2 touches. Record partial rise/decline: a swing that reaches ≥ ~70% but < 100% of the range height from one edge and turns back [Bulkowski definition recalled] → directional predictor (75–79%).
   - **Measured-move corrective phase**: K retrace of I in [0.38, 1.0]; log retrace depth; ≥ 0.70 enters Bulkowski's "best leg-2 completion" cluster.
5. **Volume filter** [STAT Bulkowski 70–86% volume-down; user's own rule]: NIFTY futures volume regression slope over K must be negative; exception: descending-triangle context tolerates rising volume. Positive-slope volume during K → downgrade to "possible reversal".
6. **Time filter** [NEoWave, prior note; Bulkowski durations]: reject completion before T_K ≥ T_I × 1/3 and before leg 2 (or C) has lasted ≥ leg 1 (or A). Flag/pennant-type K that exceeds ~1.5–2 × T_I re-classifies as triangle/rectangle (lower continuation odds, more reversal risk per Brooks).
7. **Apex / expiry rule** for converging shapes [PRAC E&M recalled; STAT Bulkowski 61–74% of way to apex]: compute apex bar index; if price is still inside at > 85% of the way to apex, mark the pattern "expired" (no directional edge, apex turn 60%).
8. **Far-line definition**: far line = L in a bull pullback (U in bear). Entry zone = far line ∩ pre-existing buyer/seller area ∩ (optional) 38–80% retrace of I. Without a pre-existing area the pattern alone is **not** an entry (user's rule).

---

## 5. Completion / failure signals (real-time)

**Completed (pullback over, impulse resuming)** — require ≥ 3 of a–e, with (f) as the mandatory trigger:
- a. Leg count satisfied: ≥ 2 legs (High 2 / Low 2) or 3 pushes for a wedge; for triangles, 5 swings (E). [Brooks; EW]
- b. Far-line reached: pivot within tolerance of L (bull), or a throw-over (intrabar break of L, close back inside). Throw-over on the final push is itself a positive sign for wedges/diagonals (EWI throw-over, prior note; Brooks "overshoot and reversal"). [RULE/PRAC]
- c. Minimum time (rule 6) satisfied. [NEoWave]
- d. Momentum/volume: RSI divergence between leg 1 low and leg 2 low (user's indicator); volume lower on leg 2 than leg 1. [PRAC EWF; STAT Bulkowski]
- e. Failed breakout of the pattern's own far line: a bar closes beyond L and the next 1–3 bars close back inside (Brooks "failed breakout… within a bar or a few bars"; Bulkowski "bust" at < 10% follow-through). Statistically the strongest signal: busted patterns outperform clean breaks. [PRAC/STAT]
- f. **Trigger**: closed reversal candle at the far line in the impulse direction (user's rule). Brooks: a bull signal bar closing near its high; second-entry preferred when the pullback leg was strong.
- Confirmation (post-entry, not entry): close back above the pullback's U line / Brooks "breakout pullback" holding above the prior swing high; EW: break of C's 2-4 line faster than C's wave 5 formed (prior note).

**Failed / not a pullback (stand aside or treat as reversal)**:
- Close beyond the far line that is **not** reclaimed within 3 bars, especially with a wide-range bar closing near its extreme and expanding volume. [LuxAlgo breakout confirmation; Bulkowski "confirmation = close outside"]
- Price exceeds the start of I (retrace > 100%): the move is no longer a pullback by definition. [Brooks glossary; EW wave-2 rule]
- Counter-move larger **and faster** than every prior counter-move in the trend, with clean 5-wave internal structure. [NEoWave, prior note]
- Pattern "expired" at the apex, or a flag/pennant that has stretched to ≥ 2 × T_I and become a trading range (Brooks: longer range → higher reversal odds; Bulkowski: rectangles/triangles have different odds than flags).
- **Final-flag context**: horizontal pullback late in a mature trend (≥ 3 pushes already, or at a measured-move target / channel line magnet). Treat the with-trend breakout as ~40% and expect a 2-leg counter-move if it fails. [Brooks]
- Partial rise inside a rectangle in a *bull* pullback (price fails to reach the top edge) predicts a **down**-break 75%: the "pullback" is likely to extend. [Bulkowski]
- Pullback that is still only one leg after a trendline break: expect a second leg before completion ("chances are high that there will be a second leg"). [Brooks]

**Incomplete (keep waiting; the commonest error)**:
- Only leg A of a zigzag (clean 5 down) — never the end of a correction. [EW; Bulkowski EW page]
- Leg 2 shorter in time than leg 1. [NEoWave]
- Fewer than 3/2 touches so lines are not yet defined; pattern has not been "filled" side to side. [Bulkowski]
- Shallow retrace (< 38%) and small vs I (< 1/3 price and time): likely a lower-degree pause; wait for the real correction.

---

## 6. Pitfalls

1. **Daily-stock statistics ≠ 15M index behaviour.** Bulkowski's durations (3 weeks), % moves (8–51%) and throwback windows (30 days) are daily-bar US-equity numbers. Only the *ordinal* findings transfer with any confidence: tight > loose; rectangles/ascending triangles > flags/pennants > wedges; deep MM retraces complete more often; busted patterns outperform; down-breaks bust more. Descending-triangle performance "almost halved since the 1990s" — all pattern edges decay.
2. **Breakout direction is the least useful number.** 53–68% with-trend is barely better than a coin; the user's edge is in the far-line reversal, where Bulkowski's TB/PB (58–74%) and bust (24–63%) rates say the crowd's breakout trade is frequently reversed.
3. **Deep retrace is double-edged.** ≥ 70% retrace gives the fullest second legs *conditional on continuation*, but Bulkowski's ABC page notes 36% of nested ABCs reverse at the prior high (double top), and Brooks puts minor-reversal-becomes-trend at ~20%. Depth must be paired with a real buyer/seller area and a reversal bar, never used alone.
4. **Rising wedge as bearish signal is weak.** 51% fail / 63% bust after down-breaks. A rising-wedge *pullback in a downtrend* (bear wedge flag) is fine; a rising wedge *at a top* should be treated as reversal-attempt-likely-to-fail-first.
5. **Pattern naming drift.** Flag → rectangle → trading range → final flag is the same object ageing. Code must re-classify as T_K grows rather than keep the first label.
6. **Line fitting on wicks vs closes.** Guides insist on swing points not intrabar wicks (ChartingLens); Bulkowski's touch rule uses distinct peaks/valleys. Fit on pivot highs/lows with ATR tolerance and never force a line.
7. **Repainting.** The last pivot of K is provisional; a "High 2" can become "High 3". Enter only on the closed trigger bar and accept that the label may change (elliott_wave.md Q3).
8. **Volume.** Index has no volume; futures volume on expiry-week 15M bars is noisy. Use the regression slope over the whole K, not bar-to-bar.
9. **Edwards & Magee 3% penetration rule** was calibrated for mid-century daily stocks; for 15M NIFTY use an ATR fraction and a 1–3 bar close-back test instead. [LuxAlgo]
10. **Over-fitting to Brooks' "two legs".** He also says one-legged pullbacks dominate the strongest trends; a tight/micro-channel impulse justifies a High 1 entry, otherwise the two-leg default applies.

---

## 7. Gaps

- No source quantifies flag/pennant/wedge statistics on intraday index data, let alone NIFTY 15M. Bulkowski's numbers need an in-house replication on NIFTY/BANKNIFTY futures 15M before any threshold is trusted.
- Bulkowski's flag/pennant pages give no throwback/pullback rate and no bear-market numbers; wedge pages give no busted statistics.
- Brooks' probabilities are stated, not measured (40%, 60%, 75%, 20%); no published test of High 2 / wedge-flag / final-flag hit rates exists.
- No source gives an explicit, tested flag↔zigzag or rectangle↔flat equivalence; the mapping table is inference from shape definitions.
- Edwards & Magee's 2/3–3/4 apex rule and 3% rule were not fetched from the primary text (recalled; secondary sources paraphrase them as "middle-to-late thirds").
- The "partial rise/decline" exact definition (how far across the range counts) was not on the fetched page; the ~2/3-to-3/4-of-height convention is recalled from Bulkowski's book and should be verified.
- Neither Bulkowski nor Brooks addresses options-premium decay interaction (expiry-day proximity) with pattern duration; this must come from the user's own trade logs.

---

### Sources
Bulkowski / thepatternsite.com: [Flags](https://thepatternsite.com/flags.html) · [FlagDay](https://thepatternsite.com/FlagDay.html) · [High-tight flag](https://thepatternsite.com/htf.html) · [Pennants](https://thepatternsite.com/pennants.html) · [Symmetrical triangles](https://www.thepatternsite.com/st.html) · [Busted sym. triangles](https://thepatternsite.com/BustSymTriangles.html) · [Ascending triangles](https://www.thepatternsite.com/at.html) · [Descending triangles](https://thepatternsite.com/dt.html) · [Rising wedge](https://thepatternsite.com/risewedge.html) · [Falling wedge](https://thepatternsite.com/fallwedge.html) · [Rectangle tops](https://thepatternsite.com/recttops.html) · [Rectangle width study](https://thepatternsite.com/TsversusWidth.html) · [Measured move up](https://thepatternsite.com/mmu.html) · [Measured move down](https://thepatternsite.com/mmd.html) · [MM retrace study](https://thepatternsite.com/MMRetrace.html) · [Simple ABC correction](https://thepatternsite.com/abc.html) · [EW corrective](https://www.thepatternsite.com/EWCorrective.html) · [Throwbacks](https://www.thepatternsite.com/throwbacks.html) · [Pullbacks](https://thepatternsite.com/pullbacks.html) · [Throwback/pullback performance](https://thepatternsite.com/ThrowPull.html) · [Partial rises/declines](https://thepatternsite.com/PartialRisesDeclinesThrowsPulls.html) · [Bust performance](https://thepatternsite.com/BustPerformance.html) · [Traps](https://thepatternsite.com/Traps.html)
Al Brooks: [Glossary](https://www.brookstradingcourse.com/price-action-trading-terms-glossary/) · [Micro trendlines / failed breakouts](https://www.brookstradingcourse.com/futures-market/trading-strategies-microtrendlines-microchannels/) · [MoneyShow: 10 best patterns](https://www.moneyshow.com/articles/tebiwkly08-56291/) · [Book excerpts (SlideShare)](https://www.slideshare.net/slideshow/brooksprobabilitiesdoc/258643754) · [Two-legged pullback example](https://www.brookstradingcourse.com/analysis/crude-oil-two-legged-pullback/) · [TradingSetupsReview](https://www.tradingsetupsreview.com/4-price-action-trading-strategies-pullback-traders/)
Other: [LuxAlgo breakout confirmation](https://www.luxalgo.com/library/concept/breakout-confirmation.md) · [LuxAlgo triangles](https://www.luxalgo.com/library/concept/ascending-descending-symmetrical-triangle.md) · [LuxAlgo corrective wave](https://www.luxalgo.com/library/concept/corrective-wave.md) · [ChartingLens triangles](https://chartinglens.com/blog/triangle-chart-patterns-guide) · [Traders.com EW triangles](https://technical.traders.com/wm/display.asp?art=297) · [TradingView: ending diagonal = wedge](https://de.tradingview.com/chart/BTCUSDT/ZqcHIsuf-Wedge-Pattern-Reversal-Continuation-Pattern) · [LiberatedStockTrader bull flag](https://www.liberatedstocktrader.com/bull-flag-pattern/) · [EWF common chart patterns](https://elliottwave-forecast.com/trading/common-chart-patterns/)
