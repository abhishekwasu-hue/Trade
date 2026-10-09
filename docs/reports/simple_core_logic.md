# Simple Core + टप्पा B: entry logic (audit साठी)

> थर 1 prompt §8 (Abhi): हे फक्त सध्याच्या code चं वर्णन आहे; बदल नाही. Live / PAPER मध्ये जे चालतं ते `simple_core/engine.py::signal_at` → `_detect` (किंवा `g10`) → `apply_reading` या क्रमाने. Order / broker भाग `simple_core/execution.py` (PAPER फक्त).

## 1. Entry gates चा क्रम (प्रत्येक बंद 15M bar वर)
| # | Gate | कुठे | नकार ⇒ `why` |
|---|---|---|---|
| 0 | 15M bars ≥ 40 | `signal_at` | "data अपुरा" |
| 1 | बाजू (side): `market_state` HTF (1H) trend. Down ⇒ seller area, up ⇒ buyer area. HTF range ⇒ `market_state.side` (impulse). Trend "testing" (protected चा real break, पुष्टी नाही) ⇒ फक्त A2 मार्ग (तुटलेल्या protected / PDH / PDL चा flip retest किंवा range कडा) | `context_from`, `_testing` | "trend / बाजू स्पष्ट नाही", `TESTING_ONLY_FLIP_OR_EDGE` |
| 2 | Opening window: 09:15 + `opening_block_min` (15) मिनिटांत बंद होणारे bars नाहीत | `_detect` | "opening window" |
| 3 | Trade बाजूचा area: `chart_reader` zones (12 साधनं ⇒ solid zones; BROKEN / DEAD / MAGNET नाहीत; अवैध trendline नाही), `area_merge_mr` (0.5 MR) अंतरातले एकत्र | `areas()` | "seller / buyer area नाही" |
| 4 | G8 flag channel असेल तर commitment close रेषेबाहेर | `flags.breakout_ok` | — (तो area वगळला) |
| 5 | Commitment: हा bar एकटा, किंवा आधीचा touch bar + हा bar. Range `commit_strength_min_mr`–`commit_strength_max_mr` (1.2–2.5 MR), body ≥ `commit_body_min` (0.5), close टोकाजवळ (`commit_close_max` 0.3). मालिकेतला कोणताही candle area ला ± `area_tol_mr` (0.3 MR) लागलेला पुरे (B1) | `_commit_ok`, `_touch` | "area वर commitment candle नाही" / "commitment area पासून दूर — chase नाही" |
| 6 | चालू episode मध्ये area पलीकडे सलग `accept_closes` closes (time acceptance) ⇒ setup रद्द | `elliott.breaks.time_accepted` | "area … पलीकडे acceptance (सलग … closes)" |
| 7 | Area च्या कडेचा real break (`breaks.break_from`, buffer `accept_buf_mr` 0.25 MR) ⇒ setup रद्द | `elliott/breaks.py` | "… acceptance — real break …" |
| 8 | Pause: commitment आधी area वर indecision bars ≥ `pause_min_bars` (1) | `pause_run`, `_is_pause` | "area वर pause नाही" |
| 9 | Commitment range ≥ `commitment_vs_pause` (1.5) × pause bars ची सरासरी range | `_detect` | "commitment … pause सरासरीच्या 1.5× पेक्षा लहान" |
| 10 | DUP_SETUP: त्याच area वर आधीच signal | `Tracker` | "DUP_SETUP …" |
| ⇒ | **ENTRY SIGNAL** (ref levels: structural invalidation, commitment extreme, next opposite area, impulse end) | | |
| G10 | Signal नसेल, `g10_enabled`, testing नाही ⇒ 15M StructureTracker RANGE च्या कडेवर तोच pause + commitment (shadow mode default) | `g10()` | "G10: RANGE नाही" |
| R | **Reading layer (टप्पा B)** candidate signal वर: S# (S1–S12), Gray-1 / Gray-2 / S4, एकच count स्रोत (G1 / G9 labels, S11), पालक दिशा, gray धोरण, eod recheck | `apply_reading` | खाली |
| R1 | `parent_source = preferred_count` आणि count नाही ⇒ `PARENT_UNKNOWN` | | "PARENT_UNKNOWN …" |
| R2 | पालक दिशा (default `market_state`) trade दिशेविरुद्ध (G4 / range_edge / G10 / G7 सोडून) | | "पालक दिशा … विरुद्ध" |
| R3 | S11: preferred count नुसार B च्या आत | | "S11 …" |
| R4 | S4 (testing) | | gray_why |
| R5 | Gray-1 / Gray-2 ⇒ gray धोरण (`get_gray_policy`, Evening Plan येईपर्यंत नेहमी **block**) | | "Gray-… (block)" |
| R6 | 15:15 चा signal ⇒ `eod_signal_carry = recheck` (दुसऱ्या दिवशी आपोआप entry नाही) | | — |

नंतर execution (PAPER): `rr_filter` (min R:R 3), SL / target modes, size — `simple_core/execution.py` + dashboard profile.

## 2. प्रत्येक gate कोणता pivot संच वापरतो
| वापर | Pivot संच | TF / आकार |
|---|---|---|
| Gate 1: HTF trend, protected swing, testing | `market_state.core.trend` ⇐ `elliott/swings.degree_pivots` | 1H, ATR14 × `trend_swing_atr_mult` (1.5) |
| Gate 1: impulse / side (range मध्ये), `impulse_end` | `market_state` trade pivots | 15M, ATR14 × `trade_swing_atr_mult` (3.0) |
| Gate 3: areas — horizontal levels | `price_action/levels_v2` चे स्वतःचे swings | 1H आणि 1D (profile `srv2`) |
| Gate 3: base / liquidity / sloping trendlines | `chart_reader/measures.pivots` | 15M, ATR14 × `swing_atr_mult` (3.0) आणि `internal_atr_mult` (1.5) |
| Gate 3: zone lifecycle (BROKEN / DEAD / MAGNET / FLIPPED) | `chart_reader/zones.annotate` (levels_v2 चे break / chop नियम) | 15M |
| Gate 4: G8 flag channel | `simple_core/flags.py` (impulse नंतरचे bars) | 15M |
| Gate 6–7: acceptance / real break | `elliott/breaks.py` (median range, buffer) | 15M |
| G10: range कडा | `opportunity_engine/structure.StructureTracker` | 15M, स्वतःचे swings |
| R: S#, Gray, correction legs, `commit_vs_impulse` | `simple_core/reading.trade_pivots` (= market_state trade pivots) | 15M, ATR14 × 3.0 |
| R: S3 trigger | `market_state` HTF pivots | 1H, ATR14 × 1.5 |
| R: एकच count स्रोत (G1 / G9, S11, पालक `preferred_count`) | `elliott/swings.multi_degree` + `CountEngine` | D0–D3 सगळे 5M pivots (auto_by_bars) |
| G1 / G8 / G9 labels (तुलना) | `simple_core/waves.py` | 15M |

**Audit चं मुख्य निरीक्षण (थर 1 prompt):** हे वेगवेगळे संच एकमेकांशी जुळवलेले नाहीत. थर 1 चा DC engine (`pivots/`) shadow म्हणून बांधला आहे. जुने modules त्यावर आणणं Abhi चा ✔ मिळाल्यानंतर, वेगळ्या टप्प्यात.

## 3. Settings
- **Engine (`simple_core/settings.py::ENGINE_DEFAULTS`):**
  - `parent_source` market_state; `g10_enabled` True; `g10_mode` shadow; `eod_signal_carry` recheck; `g10_range_bars` 400;
  - `area_tol_mr` 0.3; `area_merge_mr` 0.5;
  - `pause_body_max` 0.5; `pause_range_max_mr` 1.0; `pause_wick_min` 0.2; `pause_min_bars` 1; `pause_lookback` 12;
  - `commit_strength_min_mr` 1.2; `commit_strength_max_mr` 2.5; `commit_body_min` 0.5; `commit_close_max` 0.3; `commitment_vs_pause` 1.5;
  - `accept_buf_mr` 0.25; `opening_block_min` 15;
  - wave / G8 / flag settings (`wave_lookback_pivots` 12, `g8_retrace_max` 0.382, `w3_proj` 1.618, `flag_*`).
- **PAPER profile seed (`PAPER_SEED`):** `rr_filter` on, `min_rr` 3, `sl_mode` structural_invalidation, `sl_buffer` 0.25 MR, `target_mode` impulse_end, `g9_tier` full, `gray_size` half, `eod_signal_carry` recheck, `g10_enabled` True, `g10_mode` shadow, `parent_source` market_state.
- **Execution fields (`EXEC_FIELDS`):** SL modes, target modes, G9 tiers, instruments (credit_spread / futures / naked_buy / naked_sell), strike modes. Order फक्त dashboard ने निवडलेल्या instrument / lots वर; LIVE ला हात नाही.
- **इतर:** `market_state/core.py::DEFAULTS` (trend / trade swing mult, impulse / correction नियम), `chart_reader/settings.py` (12 साधनं, trendline `tl_*`), `elliott/settings.py` (breaks, counts, `entry_start` 09:30).
