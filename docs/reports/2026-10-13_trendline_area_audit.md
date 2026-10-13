# Trendline and S/R area audit, NIFTY and BANKNIFTY, 15M and 1H (2026-10-13)

Abhi asked: "are we drawing childish trendlines everywhere?" **Short answer: mostly yes.** Of the 153 lines the current code produces at
the 20 session closes, **8 pass KB K6** (5%). The live V22 lines (K line, swing line) are built from **2 touches**, and the engine
labels them that way. The dashboard "Trendline Gate" fits a least-squares line through the last 4 swings, so it is almost never
anchored on wicks. The areas are not much better: **710 of 1,485 drawn areas (48%) pass KB K4**. SR V3 and the Vision approval
chart mostly draw a single price, not a zone. zones2 puts up to 17 zones on one 15M chart.

This is a **read-only audit**. No chart or engine code was changed. The script is `research/trendline_area_audit.py`, run once.
Charts and CSV are in private storage only (see the end of this report). Counts only here, no images.

## 1. What draws lines and areas (exact functions)

| item | drawn by (chart function) | produced by (engine function) | TF audited |
|---|---|---|---|
| **trendlines2** lines (primary / latest / fan; broken fans skipped) | `mtf/charts.py::draw_lines` → `draw_line`; `trendlines2/charts.py::_draw` / `figure` (scripts/trendline_check.py) | `trendlines2/layer.py::run` → `trendlines2/engine.py::Engine` (L5[t]["lines"]) via `mtf/adapter.py::build` | 15M, 1H |
| **d3_kline**: V22 "K line" | `decision3/setup_chart.py::m15_panel` (setup review chart, `scripts/v22_setup_charts.py`); `decision3/charts.py::m15_png` (debug only) | `decision3/trendline.py::k_line` (called in `decision3/engine.py::V22._level_eval`, ⑤) | 15M |
| **d3_swingline**: V22 sloping S/R (Abhi 12 Oct) | not drawn as a line; it creates the "+TL" confluence area | `decision3/trendline.py::swing_line` → `confluence_areas` (`V22.tl_areas`, step ②) | 15M bars, D2 pivots |
| **dash_tl**: dashboard "Trendline Gate" | text only in `page_dashboard.py` (no line on the chart) | `signals.py::detect_trendline` (polyfit through the last 4 `find_swings` points) | 15M, 1H |
| **d3_level**: V22 1H level bands (≤ 6) | `decision3/charts.py::h1_png` (Telegram trader view `decision3/telegram_view.py::build_run`, `scripts/v22_check.py`); the chosen level also appears in `m15_png` and `setup_chart.m15_panel` / `daily_panel` | `decision3/levels.py::Levels.snapshot` / `active` | 1H |
| **d3_tl_area**: "+TL" confluence area | same as d3_level when it is the chosen level | `decision3/trendline.py::confluence_areas` | 1H |
| **zones2** zones | `mtf/charts.py::draw_zones`; `zones2/charts.py::figure` (scripts/zone_check.py) | `zones2/engine.py::Zones` (`snap[t]`, status ≠ dead) via `mtf/adapter.py::build` | 15M, 1H |
| **srv3**: SR Levels V3 | dashboard "Bot view: SR Levels V3" and `page_sr_levels_v3.py` (`tradingview_chart` price lines) | `sr_v3_chart.py::v3_chart_lines` → `sr_levels_v3.py::compute_sr_v3` + `select_display_levels` + `to_chart_lines` | 15M, 1H chart TF |
| **vision_major**: approval chart major levels | `vision/chart.py::_overlays` / `_line_panel` (Vision approval image) | `vision/context.py::majors` → `price_action/major_levels.py::major_levels` (2 nearest per side) | 15M |

Not audited, with the reason:
- `price_action/trendlines.py` via `bot_view.mcx_trendline_overlay` draws only on the MCX page.
- The trendlines that `major_levels` returns are not drawn by Vision.
- `vision/chart.py` draws no sloping line at all.
- The old dense views (`decision2/charts7.py`, `backtest_review/charts.py`, `opportunity_engine/visual_audit`) are not the approval or setup charts.

## 2. Method

- **Data:** NIFTY 1m from `upstox/` (Jul–8 Oct) plus `live_export/2026-10-13`. BANKNIFTY 1m from `live_export/2026-10-13`, with the older
  `banknifty/BANKNIFTY_15M.csv.gz` for warm-up.
- **Resampling:** 15M = `pivots.engine.bars_15m`; 1H = `decision3.levels.h1_frame`, the live engine's own resampler.
- **Sessions:** the last 20 sessions in the data, **11 Sep … 12 Oct 2026** (the data has no 14 Sep and no 2 Oct). Each is evaluated at its
  last closed bar.
- **Data policy:** `elliott.data_policy.filter_allowed(purpose="annotation")`, and the repo guards stay on. No holdout row is loaded.
  NIFTY Daily is built from 15M only (Jul–Oct), because holdout candles are sealed. BANKNIFTY Daily = `BANKNIFTY_D.csv.gz`, as in the live
  engine.
- **Caveat on the window:** it is CONTAMINATED (up to 8 Oct) plus ILLUSTRATION, so this is an illustration, not a test. No threshold was
  tuned. FUT volume was not needed.
- **MR** = median(H − L) of the last 20 closed bars of the chart TF at the session close (KB definition).
- **Line rules (K6):**
  - ≥ 3 touches (touch = a k=2 fractal pivot extreme within ±0.2 MR; anchors on wicks count);
  - touches spaced ≥ 6 bars and ≥ 8 bars (the KB says "6–8", so both are reported);
  - both anchors on the wick (±0.2 MR);
  - no close beyond the line between the anchors by > 0.3 MR;
  - |slope| ≤ 0.5 MR/bar;
  - **respected by recent price action**, which has two parts:
    - (a) no real break after anchor 2 (K5: close beyond by 0.25 MR, then acceptance (the next close also beyond) or a displacement
      bar ≥ 1.2 MR);
    - (b) ≥ 1 touch in the last 2 sessions (K6.4 a).
  - My touch counting is **lenient**: k=2 fractals find more touches than the engines' own pivots. The engine's own count is in the CSV
    (`engine_touches`).
- **Area rules:** the SR V3 audit (`docs/reports/leg_level_validation.md` + `_conclusions.md`) only measures bounce vs random levels.
  It notes that SR V3 zones are very narrow (median 0.02–0.03%) and break ~66% of the time. **It has no explicit validity rules**, so I
  used KB K4 (+ the K5 magnet rule):
  - a zone, not a line (width > 0), and width ≤ 1.5 MR;
  - an origin: displacement away within 3 bars of a visit (≥ 2 candles with body ≥ 0.6 range and range ≥ 1.5 MR, or 1 candle
    ≥ 2.5 MR) **with BOS**, or a flip (close ≥ 0.5 MR through, then a retest that closes back);
  - on the correct side of price;
  - not consumed: no acceptance through it after the origin;
  - not a magnet: < 4 close-crossings of its mid in the session (15M closes).
  - Range-edge origins (also valid in K4) are not detected, so validity is slightly under-counted.

## 3. Lines: drawn / valid / invalid by reason

Totals per symbol × TF (20 sessions):

| symbol | TF | lines drawn | K6-valid (6-bar) | K6-valid (8-bar) | sessions with > 2 lines | max lines in one session |
|---|---|---|---|---|---|---|
| NIFTY | 15M | 54 | 6 | 6 | 9 | 5 |
| NIFTY | 1H | 24 | 1 | 1 | 0 | 2 |
| BANKNIFTY | 15M | 42 | 1 | 1 | 7 | 4 |
| BANKNIFTY | 1H | 33 | 0 | 0 | 5 | 3 |
| **all** | | **153** | **8 (5%)** | **8** | | |

A line can fail for several reasons, so the counts below can add up to more than the lines drawn:

| symbol | TF | engine | drawn | valid (6) | valid (8) | touches < 3 | spacing < 6 | anchor off wick | close through between anchors | too steep | broken | no touch in last 2 sessions | spacing < 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 15M | trendlines2 | 8 | 0 | 0 | 4 | 3 | 0 | 0 | 0 | 3 | 5 | 3 |
| NIFTY | 15M | d3_kline | 9 | 2 | 2 | 4 | 1 | 0 | 0 | 0 | 4 | 0 | 1 |
| NIFTY | 15M | d3_swingline | 14 | 4 | 4 | 4 | 0 | 0 | 5 | 0 | 0 | 5 | 0 |
| NIFTY | 15M | dash_tl | 23 | 0 | 0 | 22 | 1 | 22 | 13 | 0 | 11 | 14 | 1 |
| NIFTY | 1H | trendlines2 | 0 | — | — | — | — | — | — | — | — | — | — |
| NIFTY | 1H | dash_tl | 24 | 1 | 1 | 22 | 0 | 22 | 18 | 0 | 10 | 20 | 0 |
| BANKNIFTY | 15M | trendlines2 | 13 | 1 | 1 | 6 | 2 | 0 | 0 | 0 | 3 | 7 | 2 |
| BANKNIFTY | 15M | d3_kline | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BANKNIFTY | 15M | d3_swingline | 8 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| BANKNIFTY | 15M | dash_tl | 20 | 0 | 0 | 17 | 0 | 19 | 13 | 1 | 11 | 12 | 1 |
| BANKNIFTY | 1H | trendlines2 | 14 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 13 | 13 |
| BANKNIFTY | 1H | dash_tl | 19 | 0 | 0 | 16 | 3 | 16 | 11 | 0 | 2 | 15 | 3 |

What the table shows:
- **V22 lines are built on 2 touches by design.** `tl_min_touches` = 2 (decision3 settings: "Abhi rule: K ≥ 2 touches"), and every
  k_line / swing_line had an engine touch count of exactly 2. K6 says ≥ 3. The 6 V22 lines that pass here pass only under my lenient
  k=2 fractal count. The chart still labels them "2 touches".
- **The dashboard Trendline Gate (`signals.detect_trendline`) is the most "childish" one.** A polyfit through 4 swings has no wick
  anchors (79 of 86 fail), closes cross it between the anchors, and it is often broken already. It only shows as text, but it is a gate.
- **trendlines2 does K6-style checks inside**, but `draw_lines` still draws non-tradeable lines faintly ("primary · n/a",
  "latest · steep", provisional lines with 0–2 held touches). Most fail on staleness or < 3 touches. 13 of 14 BANKNIFTY 1H lines are stale; NIFTY 1H has none.
- No engine caps lines at 2 per TF. Up to 5 lines appeared on one NIFTY 15M session.

## 4. Areas: drawn / valid / invalid by reason

| symbol | TF | areas drawn | K4-valid | avg per session |
|---|---|---|---|---|
| NIFTY | 15M | 409 | 240 | 20.4 |
| NIFTY | 1H | 326 | 124 | 16.3 |
| BANKNIFTY | 15M | 400 | 201 | 20.0 |
| BANKNIFTY | 1H | 350 | 145 | 17.5 |
| **all** | | **1,485** | **710 (48%)** | |

The "per session" columns are summed over all engines that draw on that TF; each engine is a separate chart or view.

| symbol | TF | engine | drawn | valid | max per session | line, not zone | too wide (> 1.5 MR) | no displacement + BOS / flip | wrong side of price | consumed (acceptance through) | magnet |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 15M | zones2 | 265 | 213 | 17 | 0 | 1 | 17 | 0 | 31 | 3 |
| NIFTY | 15M | srv3 | 104 | 27 | 7 | 68 | 1 | 20 | 0 | 12 | 6 |
| NIFTY | 15M | vision_major | 40 | 0 | 2 | 40 | 0 | 6 | 0 | 0 | 1 |
| NIFTY | 1H | d3_level | 98 | 54 | 6 | 0 | 12 | 21 | 0 | 18 | 2 |
| NIFTY | 1H | d3_tl_area | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| NIFTY | 1H | zones2 | 64 | 28 | 5 | 0 | 0 | 9 | 0 | 27 | 0 |
| NIFTY | 1H | srv3 | 163 | 41 | 11 | 83 | 3 | 28 | 0 | 60 | 4 |
| BANKNIFTY | 15M | zones2 | 232 | 164 | 16 | 0 | 2 | 18 | 0 | 48 | 0 |
| BANKNIFTY | 15M | srv3 | 124 | 37 | 9 | 73 | 4 | 15 | 0 | 15 | 5 |
| BANKNIFTY | 15M | vision_major | 44 | 0 | 3 | 44 | 0 | 5 | 0 | 4 | 0 |
| BANKNIFTY | 1H | d3_level | 110 | 56 | 6 | 0 | 43 | 21 | 0 | 11 | 5 |
| BANKNIFTY | 1H | d3_tl_area | 7 | 4 | 1 | 0 | 0 | 3 | 0 | 0 | 0 |
| BANKNIFTY | 1H | zones2 | 82 | 32 | 6 | 0 | 0 | 30 | 1 | 19 | 0 |
| BANKNIFTY | 1H | srv3 | 151 | 53 | 10 | 55 | 0 | 54 | 0 | 21 | 4 |

What the table shows:
- **SR V3** draws a single price (low = high) for 53% of its levels (279 of 542), and many others are consumed.
- **Vision approval chart:** major levels are single-price lines by design, so 0 of 84 are zones.
- **V22 1H bands** are often too wide on BANKNIFTY (43 of 110 are > 1.5 MR). This is the Q19 merge issue already open as TL2.
- **zones2** has the best validity rate, but it draws 7–17 zones on every 15M chart (NIFTY 11–17): too many to read.

## 5. Worst examples (date = session close)

| date | symbol TF | engine | item | reasons |
|---|---|---|---|---|
| 2026-09-24 | BANKNIFTY 15M | dash_tl | descending resistance (polyfit, anchors 23 Sep 13:00 → 24 Sep 13:15) | anchors 1.47 MR off the wicks, a close 2.7 MR through between the anchors, slope 0.58 MR/bar (> 0.5), 0 touches, broken at 14:00 the same day |
| 2026-09-21 | NIFTY 1H | dash_tl | descending resistance (4 Sep → 17 Sep) | anchor 1.3 MR off the wick, a close 0.69 MR through between the anchors, broken 18 Sep, 0 touches, stale |
| 2026-09-17 | NIFTY 15M | d3_swingline | resistance 24,025 (3 Sep) → 23,593 (15 Sep) | 2 touches, a close 1.48 MR through between the anchors, no touch in the last 2 sessions |
| 2026-09-16 | NIFTY 15M | trendlines2 | "latest" (steep) 15 Sep 09:15 → 16 Sep 09:15 | 2 touches (engine: 0 held), broken 10:30 the same session; still drawn faint |
| 2026-10-07 | NIFTY 15M | d3_kline | K line 22,217 → 22,397 (5 → 7 Oct) | 2 touches, broken by close at 13:00 the same session |
| 2026-10-08 | BANKNIFTY 1H | trendlines2 | "latest" 22 Sep → 7 Oct | engine: 0 held touches; a close 0.66 MR through between the anchors; spacing < 6 |
| 2026-09-21 … 09-25 | BANKNIFTY 1H | d3_level | resistance 56,823–57,585 | 4.3–4.7 MR wide (K4 max 1.5), already consumed by acceptance; shown 5 sessions in a row |
| 2026-10-07 | BANKNIFTY 1H | d3_level | support 54,636–55,201 | 1.8 MR wide, no displacement + BOS / flip, magnet (5 close-crossings that day) |
| 2026-09-30 | NIFTY 15M | srv3 | A69 resistance 22,753 (15M+PDH+REJ×4) | single price, consumed by acceptance, magnet (4 crossings), yet grade A |
| 2026-10-07 | NIFTY 15M | srv3 | B60 resistance 22,622 (15M+30M+FLIP) | single price, consumed, magnet (5 crossings) |
| 2026-09-22 / 23 | NIFTY 15M | vision_major | M1↓ support 23,116 | single price, no displacement + BOS / flip |

## 6. What a fix would need (proposal only, no code changed)

1. **Draw only K6-valid lines.** A line needs:
   - ≥ 3 touches on wick-anchored confirmed pivots, spaced ≥ 6 bars (Abhi: 6 or 8?);
   - no close > 0.3 MR through it between the anchors;
   - |slope| ≤ 0.5 MR/bar;
   - not really broken (K5);
   - ≥ 1 touch in the last 2 sessions.

   In practice:
   - V22 `tl_min_touches` 2 → 3 for anything drawn (decision effect separate);
   - trendlines2 `draw_lines` would draw only `trade-योग्य` lines (no faint n/a, steep, provisional or 0-held lines);
   - dashboard `detect_trendline` would be replaced by a wick-anchored builder (or removed from the gate).
2. **At most 2 lines per timeframe:** the 2 best by K6.4 recency score (recent touches, last reaction, reaction strength), each labelled
   with its touch count ("3 touches", "4 touches").
3. **Draw only K4-valid areas:**
   - zones, not lines, with width ≤ 1.5 MR;
   - with an origin (displacement + BOS, or a flip, or a range edge);
   - on the correct side;
   - not consumed;
   - not a magnet.

   In practice:
   - SR V3 and Vision majors need a band (e.g. wick–body or ± a fraction of MR) instead of one price;
   - V22 merged bands need a width cap (open question TL2);
   - zones2 needs a nearest-N cap.
4. Shared validators (one K6 line check and one K4 area check) used by all chart drawers, so every chart shows the same thing. Golden
   tests must not be edited to pass; thresholds come from the KB, not from these results.

## 7. Where the charts are (private)

`trade-data/reports/trendline_audit/2026-10-13/`:
- `charts/<SYMBOL>/<TF>/<SYMBOL>_<TF>_<YYYYMMDD>.png`: 80 charts. The left panel shows lines, the right panel areas. Solid or filled =
  valid; dashed or hatched = invalid, with a short reason on the label. English only.
- `trendline_area_audit.csv`: one row per drawn item, with metrics and reasons.
- `summary.json`

Rerun:

```
python3 research/trendline_area_audit.py --nifty-1m <trade-data>/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz \
  <trade-data>/live_export/2026-10-13/NIFTY_1minute.parquet --banknifty-1m <trade-data>/live_export/2026-10-13/BANKNIFTY_1minute.parquet \
  --banknifty-15m <trade-data>/banknifty/BANKNIFTY_15M.csv.gz --banknifty-daily <trade-data>/banknifty/BANKNIFTY_D.csv.gz \
  --out <trade-data>/reports/trendline_audit/2026-10-13 --end 2026-10-12 --sessions 20
```

---

## 8. Re-run with Abhi's 2-touch rule (TA1–TA4, decided 2026-10-13)

Same data, same 20 sessions, same drawers, one run (`--rule 2touch`). Read-only; no chart or engine code changed. Sections 1–7 above
are kept unchanged as the first run.

**Rules used in this re-run**

| item | rule |
|---|---|
| line valid (TA3, corrected) | **2 touches** spaced ≥ 6 bars (TA2: 6 only). The projected next touch is the trade location; in the CSV it is `value_t`, the line value at the session close. |
| line "established" | valid, and ≥ 3 touches spaced ≥ 6 bars (reported separately) |
| other line rules (K6, unchanged) | both anchors on wicks (±0.2 MR); no close > 0.3 MR beyond the line between the anchors; \|slope\| ≤ 0.5 MR/bar; **respected by recent price**, as defined in the first run: no real break after anchor 2 (K5) and a touch in the last 2 sessions. Lines that fail only on that last rule are counted separately. |
| area valid (TA3b + TA4) | a **band** (low < high; a single price is invalid as "not a band"); **≥ 2 reaction touches**: a swing high or low (k=2) whose extreme is in the band ±0.2 MR, spaced ≥ 6 bars, with price fully leaving the band between them. The role comes from price, so a flip is allowed. **Broken** means acceptance through the band from one side to the other (2 closes beyond it by 0.25 MR) after the first touch. Broken areas are invalid except the most recently broken one on each engine's chart. |
| kept from the first run | K4 width ≤ 1.5 MR and the K5 magnet rule (≥ 4 close-crossings of the band mid in the session); neither was part of TA1–TA4 |

**New summary per symbol × TF**

| symbol | TF | lines drawn | valid (2 touches) | of which established (≥ 3) | fail only on recent-price rule | areas drawn | areas valid |
|---|---|---|---|---|---|---|---|
| NIFTY | 15M | 54 | 10 | 6 | 17 | 409 | 108 |
| NIFTY | 1H | 24 | 1 | 1 | 1 | 326 | 61 |
| BANKNIFTY | 15M | 42 | 11 | 1 | 12 | 400 | 41 |
| BANKNIFTY | 1H | 33 | 2 | 0 | 14 | 350 | 100 |
| **all** | | **153** | **24 (16%)** | **8** | **44** (31 no touch in the last 2 sessions, 13 broken) | **1,485** | **310 (21%)** |

**Lines: invalid by reason** (one line can fail for several reasons):

| symbol | TF | engine | drawn | valid | established | fail only recent | < 2 touches spaced 6 | anchor off wick | close through between anchors | too steep | broken | no touch in last 2 sessions |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 15M | trendlines2 | 8 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 3 | 5 |
| NIFTY | 15M | d3_kline | 9 | 5 | 2 | 4 | 0 | 0 | 0 | 0 | 4 | 0 |
| NIFTY | 15M | d3_swingline | 14 | 5 | 4 | 4 | 0 | 0 | 5 | 0 | 0 | 5 |
| NIFTY | 15M | dash_tl | 23 | 0 | 0 | 1 | 19 | 22 | 13 | 0 | 11 | 14 |
| NIFTY | 1H | dash_tl | 24 | 1 | 1 | 1 | 22 | 22 | 18 | 0 | 10 | 20 |
| BANKNIFTY | 15M | trendlines2 | 13 | 3 | 1 | 10 | 0 | 0 | 0 | 0 | 3 | 7 |
| BANKNIFTY | 15M | d3_kline | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BANKNIFTY | 15M | d3_swingline | 8 | 7 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| BANKNIFTY | 15M | dash_tl | 20 | 0 | 0 | 1 | 17 | 19 | 13 | 1 | 11 | 12 |
| BANKNIFTY | 1H | trendlines2 | 14 | 0 | 0 | 13 | 0 | 0 | 1 | 0 | 0 | 13 |
| BANKNIFTY | 1H | dash_tl | 19 | 2 | 0 | 1 | 15 | 16 | 11 | 0 | 2 | 15 |

(NIFTY 1H: trendlines2 drew no lines in the 20 sessions.)

**Areas: invalid by reason**

| symbol | TF | engine | drawn | valid | not a band | too wide | < 2 reaction touches | broken (not the latest) | magnet |
|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 15M | zones2 | 265 | 92 | 0 | 1 | 53 | 130 | 3 |
| NIFTY | 15M | srv3 | 104 | 16 | 68 | 1 | 47 | 43 | 6 |
| NIFTY | 15M | vision_major | 40 | 0 | 40 | 0 | 19 | 12 | 1 |
| NIFTY | 1H | d3_level | 98 | 20 | 0 | 12 | 50 | 43 | 2 |
| NIFTY | 1H | d3_tl_area | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| NIFTY | 1H | zones2 | 64 | 25 | 0 | 0 | 22 | 20 | 0 |
| NIFTY | 1H | srv3 | 163 | 15 | 83 | 3 | 56 | 97 | 4 |
| BANKNIFTY | 15M | zones2 | 232 | 30 | 0 | 2 | 49 | 171 | 0 |
| BANKNIFTY | 15M | srv3 | 124 | 11 | 73 | 4 | 42 | 69 | 5 |
| BANKNIFTY | 15M | vision_major | 44 | 0 | 44 | 0 | 17 | 10 | 0 |
| BANKNIFTY | 1H | d3_level | 110 | 22 | 0 | 43 | 29 | 42 | 5 |
| BANKNIFTY | 1H | d3_tl_area | 7 | 2 | 0 | 0 | 5 | 0 | 0 |
| BANKNIFTY | 1H | zones2 | 82 | 33 | 0 | 0 | 33 | 16 | 0 |
| BANKNIFTY | 1H | srv3 | 151 | 43 | 55 | 0 | 40 | 75 | 4 |

**What changed versus the first run**

- **Lines:** valid lines went from 8 to 24 (16%).
  - The V22 lines now mostly pass. K line + swing line: 18 of 32 valid.
  - The dashboard polyfit gate still fails: 3 of 86 valid, because its anchors are not on wicks.
  - **44 lines fail only on the recent-price rule.** 31 of them fail only because there was no touch in the last 2 sessions. A 2-touch line waiting for its projected 3rd touch will often have had no touch for 2 sessions, so this rule conflicts with the new idea; see open question TA5.
  - Valid lines per TF per session: at most 2 on NIFTY and 3 on BANKNIFTY 15M (7 Oct). The 2-per-TF cap would bind only once.
- **Areas:** valid areas fell from 710 to 310 (21%).
  - The two-reaction rule and the "broken except the latest" rule are stricter than K4's origin and side checks.
  - zones2 keeps many flipped or broken zones alive, so 337 of its zones are "broken, not the latest".
  - Single-price levels (SR V3 279, Vision 84) are all invalid by TA4.
  - After the rule, the valid areas per engine chart average about 1–2, except NIFTY 15M zones2 (up to 8).

### The 30 Sep → 6/7 Oct NIFTY 15M line (the KB golden example)

**Spot 15M:**
- **Anchors:** 30 Sep 12:45 high **22,809.35** → 6 Oct 14:00 high **22,731.85**. Slope −1.0 pt/bar.
- **When the 2-touch rule finds it:** it is valid at the **6 Oct close**. At the 7 Oct close it is established: the 7 Oct 12:00 high of 22,717.65 is the 3rd touch, 4 touches with k=2 pivots. It is still valid at the 8 Oct close.
- **Which engine draws it:** the live V22 engine (`decision3.trendline.swing_line`) produces this exact line from the **7 Oct close** onward (7, 8, 9 and 12 Oct). Its engine count is 2 touches. No other drawer finds it.
- **Before 12 Oct:** it is found. The only catch: at the **9 Oct close** it fails the "touch in the last 2 sessions" rule (no touch on 8 or 9 Oct), so with that rule kept it would be hidden for that one close. It is valid again at the 12 Oct close.
- **Projected touch on 12 Oct:** the line is at **22,654 at 09:15**. The 09:15 bar's high was **22,651.10**, 0.09 MR below the line, so it is a touch. The bar closed at 22,581.8, and price fell to 22,317 by 15:00. The line drifts from 22,654 (09:15) to 22,631 (15:00); no later bar came back to it.
- **Anchor on 7 Oct instead:** using 7 Oct 12:00 (22,717.65) as anchor 2 gives the same picture: 22,657.5 at 09:15, high 0.18 MR below the line, which is a touch.

**FUT 15M** (front month NIFTY FUT 27 OCT 26, from 5M; the data starts 30 Sep 09:15):
- **Anchors:** 30 Sep 12:45 high **22,935.0** → 6 Oct 12:45 high **22,830.0**.
- **When the 2-touch rule finds it:** valid at the 6 Oct close (3 touches); established at the 7 Oct close. At the 8 and 9 Oct closes it fails only the recent-touch rule.
- **Projected touch on 12 Oct:** **22,709.6 at 09:15**. The FUT high was 22,720.0, 0.25 MR above the line (just outside the ±0.2 MR touch band, so it is a poke through). The bar closed at 22,639.5, back below the line.
- **Anchor on 7 Oct instead:** the line is 22,681 at 09:15; the high is 0.95 MR above it and the close is below.

### Files (private)

`trade-data/reports/trendline_audit/2026-10-13/rerun_2touch/`:
- `charts/<SYMBOL>/<TF>/*.png`: 80 charts, English only. Valid lines carry "(3rd touch now <price>)", the projected next touch at the session close.
- `trendline_area_audit.csv`: adds the columns `established`, `fail_only_recent`, `reaction_touches`, `touch_ts`, `break_ts` and `price_side`.
- `summary.json`
- `golden_line.json`: spot and FUT validity and the projection on every 12 Oct bar.

Rerun: the command in section 7, plus:

```
--rule 2touch --nifty-fut-5m <trade-data>/live_export/2026-10-13/oe_futures_5min_NIFTY.parquet \
--golden 2026-09-30 2026-10-06,2026-10-07 2026-10-12 --out <trade-data>/reports/trendline_audit/2026-10-13/rerun_2touch
```

---

## 9. Re-run with the R1 shared checks (`facts/validity.py`, branch `claude/r1a-lines-bands`)

Same data, same 20 sessions, same drawers, one run (`--rule shared`). The 2-touch checks of §8 are replaced by the shared checks that
every chart now uses: `facts.validity.check_line` (lines) and `facts.validity.check_band` + `latest_broken_only` (areas). Read-only for
the engines; nothing tuned.

**Rule differences versus §8 (by design, not tuning):**
- Lines: no "touch in the last 2 sessions" rule (TA5 is still open, so it is not applied). Everything else is the same (2 wick-anchored
  touches spaced ≥ 6 bars, no close > 0.3 MR beyond between the anchors, slope ≤ 0.5 MR/bar, no K5 real break after anchor 2, ≥ 3 =
  established). New: a falling line through lows / rising line through highs is a channel edge, not a trendline (K6 definition,
  `trend_direction_only`); no engine line hit this rule.
- Areas: touches are counted on the band's current side only. A K5 real break (0.25 MR + acceptance or displacement) flips the role and
  the count restarts on the new side (TA3b). "Broken" now means "the last event is a break and there are < 2 touches on the new side":
  such a band is invalid and only the most recent one is drawn, dashed. A flipped band with 2 new-side touches is valid again. In §8 any
  band with an acceptance through it after its first touch stayed broken, and the latest broken band per chart stayed valid.

**Summary per symbol × TF**

| symbol | TF | lines drawn | valid §8 | valid shared | established §8 → shared | areas drawn | valid §8 | valid shared | latest broken (dashed) |
|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 15M | 54 | 10 | 19 | 6 → 10 | 409 | 108 | 91 | 53 |
| NIFTY | 1H | 24 | 1 | 1 | 1 → 1 | 326 | 61 | 44 | 61 |
| BANKNIFTY | 15M | 42 | 11 | 19 | 1 → 4 | 400 | 41 | 100 | 49 |
| BANKNIFTY | 1H | 33 | 2 | 16 | 0 → 12 | 350 | 100 | 101 | 59 |
| **all** | | **153** | **24** | **55 (36%)** | **8 → 27** | **1,485** | **310** | **336 (23%)** | **222** |

**Lines: the counts match §8 exactly once TA5 is removed.** 31 lines change from invalid to valid. In §8 each of them failed only on
"no touch in the last 2 sessions". 24 + 31 = 55, and no other line changed its verdict. The 13 lines that failed "only on the recent
rule" because they were broken stay invalid. Per engine: trendlines2 3 → 28, d3_swingline 12 → 17, d3_kline 6 → 6, dashboard Trendline
Gate (polyfit) 3 → 4. The gate is still the worst: 79 of 86 anchors are not on wicks. At most 2 valid lines per chart on NIFTY and 3 on
BANKNIFTY 15M (one session), so the TA1 cap of 2 binds once.

**Areas: 336 valid instead of 310; 272 single verdicts differ.** The differences come from the broken / flip semantics above:
- 149 areas that §8 called "broken, not the latest" are valid now. They were broken once and then touched twice from the new side, so
  they are flipped bands (TA3b).
- 123 areas that §8 kept valid are not valid now:
  - 84 are "broken": the last event is a break with < 2 new-side touches. §8 kept the latest broken band valid; now it is drawn dashed
    as "broken", not as a valid area.
  - 39 are "broken, not the latest".
- Unchanged: all 279 SR V3 and 84 Vision single prices fail as "not a band". Per engine, valid areas went:
  - d3_level 42 → 40;
  - d3_tl_area 3 → 2;
  - zones2 180 → 200;
  - srv3 85 → 94;
  - vision_major 0 → 0.

**Goldens with the shared checks** (tests/test_r1_golden_lines.py; data truncated at the decision bar, no 12 Oct bar read):

| | spot 15M | FUT 15M (from 5M) |
|---|---|---|
| line found at the 6 Oct close from 2 touches | 30 Sep 12:45 22,809.35 → 6 Oct 14:00 22,731.85 (valid from 14:30) | 30 Sep 12:45 22,935.0 → 6 Oct 12:45 22,830.0 (valid from 13:15) |
| valid at the 6 / 7 / 8 / 9 Oct closes | yes; established (3 spaced touches, 7 Oct 12:00 = 3rd) from the 7 Oct close | yes; established from the 7 Oct close |
| drawn at the 9 Oct close (TA1, ≤ 2 lines) | yes, second (first: 6 Oct 14:00 → 9 Oct 14:15, 3 touches, more recent last touch) | yes, second (first: 6 Oct 12:45 → 7 Oct 12:00, 3 touches) |
| projected zone at 12 Oct 09:15 (± 0.2 MR) | 22,654.35 (22,647.22–22,661.48); high 22,651.10 **inside**; close 22,581.8 | 22,709.6 (22,701.75–22,717.45); high 22,720.0 = 0.27 MR above the line, **outside the zone**, close 22,639.5 back below = a K5 sweep of the projected touch |
| supply band near ≈ 22,667 | the same two reactions on spot: 22,534–22,574 (9 Oct 11:15, 14:15); no confluence with the spot line inside one session | **22,620–22,665**, 2 touches (9 Oct 11:15 22,620; 14:15 22,665), a flipped band (it was demand until the 8 Oct 09:15 break) |
| band + line confluence | 22,667–22,711 (4 touches, established): line 22,655.4 at the 9 Oct close, 0.34 MR from it, **confluence at 09:15** | ≈ 22,667 band: the line reaches it at 12 Oct 13:45 (offset 19, line 22,684.4, 0.49 MR), **not at 09:15** (1.14 MR apart). At 09:15 the line is in confluence with supply 22,729–22,761 (7 Oct 11:00, 14:15; 0.46–0.49 MR) |

So the line golden holds on both feeds. The FUT opening spike is a sweep through the zone, not a touch inside ± 0.2 MR. The zone was not
widened. The ≈ 22,667 FUT band is found, but by the rule it meets the projected line only later on 12 Oct. The band that is in confluence at
09:15 is the one above it. Both points are open questions for Abhi (R1a-7, R1a-8).

After the independent review fixes (acceptance on a sloped line compared with the line at the next bar; magnet closes clipped to the
end of bar t; twin pivot before anchor 2 no longer drops a line), the same run (`rerun_shared_review/`, no charts) gives the identical
valid / established / latest-broken counts above; only a few magnet counts moved (d3_level 5 → 7, srv3 18 → 19 reasons, no verdict
changed). With the twin-pivot fix the display finder now also finds a newer 3-touch line, so at the 9 Oct close the golden line is
drawn second on both feeds (first = the newer line with the more recent last touch, R1a-1).

Files (private): `trade-data/reports/trendline_audit/2026-10-13/rerun_shared/` (80 charts, CSV with `latest_broken`, `summary.json`);
golden display charts: `trade-data/reports/r1_lines_bands/2026-10-13/`. Rerun: the command in section 7 plus `--rule shared --out
<trade-data>/reports/trendline_audit/2026-10-13/rerun_shared`.
