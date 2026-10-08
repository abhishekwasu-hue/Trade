# Chart Reader (G-E1a) — रचना

> आधार: `TRADE_BOTS_UPGRADE_PROMPT.md` (Chart Reader) + `docs/knowledge/KNOWLEDGE_BASE.md` (Abhi, 2026-10-08). **Report-only:** order नाही,
> bot ला जोडलेलं नाही (G-E1b मध्ये SRv2). किंमती फक्त OHLC / code areas मधून, vision कडून कधीच नाही.

## प्रवाह — KB भाग B चे 8 टप्पे (`chart_reader/evaluate.py`)

| टप्पा | काय | Module | Chapter |
|---|---|---|---|
| 0 | फक्त asof पर्यंतचे **बंद** bars; MR = 20 बंद bars (चालू वगळून) | `evaluate.frame`, `measures.py` | भाग G |
| 1 | HTF trend · Elliott (शक्यता) | `trend.py`, `elliott_ctx.py` | K1, K3 |
| 2 | Impulse ⇒ बाजू (फक्त impulse दिशेने) · correction प्रकार · entry point (zigzag/flat C-end, triangle E-end) · pullback की reversal | `structure.py` | K2, K3 |
| 3 | **सगळी 12 साधनं (a–l)** उमेदवार ⇒ active area (K6.4) + confluence | `areas.py`, `price_action/levels_v2.py` | K4–K8, K13 |
| 4 | Candles · correction कमकुवत · sweep · futures volume · RSI divergence · patterns | `candles.py`, `evidence.py`, `volume.py` | K5, K9–K12 |
| 5 | Gap · वेळ / expiry · VIX · event | `vision/gap_context.py`, `evidence.py` | K13, K14 |
| 6 | Logical reversal (elliott composite, soft = पुरावा) | `reversal.py` | K9 |
| 7 | Invalidation · target = impulse चं टोक, मग पलीकडचे ठोस HTF areas (a/b/c/d/k); मधले लहान areas = obstacles · R:R ≥ 3 · पक्के नियम | `areas.trade_targets`, `risk.py`, `rules.py` | A3 |
| 8 | गोष्ट ([K#] tags) + grade + व्हेटो | `narrative.py`, `grade.py` | भाग D |

Entry फक्त: पक्के नियम पास + entry point + reversal "ok" + grade A/B + व्हेटो नाही.

## पुरावे — KB भाग D (weights Abhi ने मंजूर; tuning नाही)

| # | गुण | कुठे |
|---|---|---|
| T | −20 / +5 / +8 / +15 | `grade._trend` |
| ✚ PB | +10 healthy (3 waves, overlap ≥ 0.6, origin अबाधित, खोली 38.2–80%) · −10 धोका · −15 origin जवळ / probe | `evidence.pullback` |
| CW | 0…15 | `structure` |
| AQ | 0…20 (ठोस साधनं; horizontal ∩ sloping = 1.0) | `areas.active` |
| CF | +5 / प्रकार, कमाल 10; मोजपट्टी (g/h/i) फक्त ठोस area सोबत | `areas.active` |
| ✚ LQ | +5 sweep + reclaim, +3 wick ≥ 50% | `evidence.liquidity` |
| RV | 50 × (s − 0.30), −10…+25 | `reversal.py`, `grade.rv_points` |
| ✚ VL | +3 dry-up · +2 spike / reversal volume · −5 वाढता · data नाही 0 | `volume.evidence` |
| ✚ DV | +5 regular (C-end) · +3 hidden · −3 impulse टोकावर विरुद्ध | `evidence.divergence` |
| ✚ PT | +5 flag · +3 opposite wedge · −10 double top/bottom, H&S, impulse wedge | `evidence.patterns` |
| GP | ±10 | `evaluate._gap_evidence` |
| EW | +10 end · 0 gray · −15 A-end / B (count स्पष्ट ⇒ व्हेटो) | `elliott_ctx.py` |
| RM | +5 (R:R ≥ 5) | `grade` |
| ✚ TM | −5 09:15–09:45 · −3 expiry सकाळ | `evidence.time_of_day` |
| ✚ VX | −5 VIX उडी · +2 VIX घटतोय | `evidence.vix` |
| EV | −5 event दिवस | `grade` |

**Grade:** A ≥ 60 · B 45–59 · C < 45. Size = full × `tier_mult`. **A3 व्हेटो** (`evidence.vetoes`) ⇒ C: count स्पष्ट असताना A-end / B च्या
आत · impulse origin पलीकडे acceptance (real break, `elliott/breaks.py`) · MAGNET level · gap setup B मध्ये pullback नाही. S6a / S13
(B-end → C) setting `c_wave_setups_enabled`, default OFF.

## एकच व्याख्या (KB भाग G)

- Real break = `elliott/breaks.py` (0.25 MR buffer + displacement / acceptance / failed retest).
- MR = 20 बंद bars, चालू bar वगळून (`measures.py`; `levels_v2` सुद्धा).
- Swings = `elliott/swings.py` (`measures.pivots`).
- Displacement: break साठी `strength_min` (elliott settings); zone origin साठी `disp_body_mr` / `disp_body_frac` / `disp_single_mr`.
- Pullback valid खोली 38.2–80% (`retrace_lo`, `retrace_max`); `price_action/legs.py` चा `r_warn` 0.80.

## Futures volume (K10.3)

- `collect_index_futures_volume.py` आता front **आणि** पुढचा contract `data/oe_futures_5min_<SYM>_all.parquet` मध्ये (key = timestamp +
  contract) साठवतो; जुनी front-only file तशीच.
- `volume.continuous`: causal roll (दिवस D ला पुढच्या contract चा volume जास्त ⇒ D+1 पासून; मागे परत नाही; roll दिवस तुलनेतून वगळला).
- `rel_vol` = त्याच वेळेच्या slot चा मागच्या 20 दिवसांचा median (चालू दिवस वगळून).
- **मर्यादा:** expired futures चा जुना volume नाही ⇒ IS / VAL मध्ये VL तपासता येत नाही; फक्त PAPER scorecard.
- Data trade-data मध्ये सुद्धा (`futures_volume/`, VPS block).

## अहवाल

- `research/chart_reader_ge1a_report.py` ⇒ `docs/reports/chart_reader_ge1a_kb.md`: MR-आधारित आकड्यांचं calibration, IS grade वितरण,
  reversal दिवस, 7 Oct golden.
- `research/chart_reader_examples.py` ⇒ `docs/reports/chart_reader_examples.md`: golden + IS flat C-end + IS triangle E-end (charts gitignored).
