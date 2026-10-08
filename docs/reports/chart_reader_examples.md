# Chart Reader G-E1a — उदाहरणं (report-only)

> Code pre-grade (vision शिवाय), KB भाग D चा तक्ता (16 पुरावे) + A3 व्हेटो. Weights / A ≥ 60 · B 45–59 · C < 45 — Abhi ने मंजूर, tuning नाही. IS मध्ये futures volume / VIX नाही ⇒ VL, VX = 0. Charts gitignored.

IS scan: {'flat': 174, 'triangle': 87} उमेदवार (206.6 s).

### 7 Oct 2026 — golden story

**Data नाही:** `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz` (VPS export block चालायचा आहे).

### IS flat C-end

- वेळ (bar close): **2019-05-09 11:30:00** · बाजू: **bear call** · grade **A** (66.77) · entry: **नाही** — spot R:R 1:0.4 < 1:3
- correction: flat · entry point: C-end · pullback: pullback
- R:R: 1:0.4 · invalidation: 11454.65625 · targets: 11291.2 (IMPULSE-END), 10610.95 (1d-L1902190000)

| पुरावा | गुण | ओळ |
|---|---|---|
| T | 15 | HTF down आणि मजबूत — trend दिशेने entry |
| PB | 0 | 3 waves ✓, overlap ✗, origin अबाधित ✓, खोली 38.2–80% ✗ (overlap 0.562) |
| CW | 9 | correction कमकुवत होण्याचे पुरावे 0.60 |
| AQ | 10 | area गुणवत्ता 0.50 |
| CF | 10 | confluence अतिरिक्त प्रकार 2 (मोजपट्टी फक्त ठोस area सोबत) |
| LQ | 0 | sweep + reclaim नाही |
| RV | 12.77 | reversal s = 0.56 (medium) |
| VL | 0 | futures volume data नाही ⇒ 0 (trade अडत नाही) |
| DV | 0 | divergence नाही |
| PT | 0 | pattern नाही |
| GP | 10 | gap confirms |
| EW | 0 | Elliott none |
| RM | 0 | spot R:R 0.4 |
| TM | 0 | वेळ 11:30 — ठीक |
| VX | 0 | VIX data नाही |
| EV | 0 | event दिवस नाही |

Story (code narrative):

- [K1] HTF trend down (strong) · 1h DOWNTREND_PULLBACK, 1d UPTREND_WEAK · [K3] Elliott: —
- [K2] impulse खाली 11,634.9 → 11,388.3 (11.51× MR, 27 bars)
- [K2] correction flat (3 legs): 11,388.3 → 11,449.3 → 11,291.2 → 11,357.4; retrace 25%, वेळ impulse च्या 0.63× · pullback उथळ (< 38.2%)
- [K4/K6/K8] active area PDL (साधन k, ACTIVE) 11,342.2–11,353.0 · गुणवत्ता 0.50 · [K7] confluence: i, l · तपासलेली साधनं: a2, b1, d3, e4, f2, g2, h4, i3, j2, k5, l3
- [K9] close खालच्या भागात — sellers पुढे · आकार 0.65× MR (लहान) · [K10] correction कमकुवत 0.60
- [K5] sweep + reclaim नाही · [K10.3] futures volume data नाही ⇒ 0 (trade अडत नाही) · [K10.2] divergence नाही · [K11] pattern नाही
- [K13] gap: G3 gap down -0.32× ATR · undecided · fill 89.3% ⇒ trade दिशेची पुष्टी · [K14] वेळ 11:30 — ठीक · VIX data नाही
- [K9] reversal: N=3 s=0.56 (medium) · mods N=3 −0.05 · candles 0–100: wick 18.5 / close_loc 16.9 / bounce 10.4 / sweep 0 / speed 5
- [A3] risk: invalidation 11,454.7 · target 11,291.2 (IMPULSE-END) · spot R:R 1:0.4 · मधले areas (target नाहीत): RN11300 11,305.4, SWL-1442 11,293.3
- [भाग D] grade A (66.77) · मी चुकीचा ठरेन: 11,454.7 च्या पलीकडे close

Chart: `is_flat.png` (gitignored)

### IS triangle E-end

- वेळ (bar close): **2018-03-08 14:30:00** · बाजू: **bear call** · grade **A** (79.45) · entry: **नाही** — spot R:R 1:2.8 < 1:3
- correction: triangle · entry point: E-end · pullback: pullback
- R:R: 1:2.8 · invalidation: 10246.074999999999 · targets: 10141.55 (IMPULSE-END), 10086.03 (1h-L1712180915)

| पुरावा | गुण | ओळ |
|---|---|---|
| T | 15 | HTF down आणि मजबूत — trend दिशेने entry |
| PB | 10 | healthy pullback — 3 waves ✓, overlap ✓, origin अबाधित ✓, खोली 38.2–80% ✓ (overlap 0.619) |
| CW | 12 | correction कमकुवत होण्याचे पुरावे 0.80 |
| AQ | 8 | area गुणवत्ता 0.40 |
| CF | 10 | confluence अतिरिक्त प्रकार 2 (मोजपट्टी फक्त ठोस area सोबत) |
| LQ | 0 | sweep + reclaim नाही |
| RV | 7.45 | reversal s = 0.45 (weak) |
| VL | 0 | futures volume data नाही ⇒ 0 (trade अडत नाही) |
| DV | -3 | impulse च्या टोकावर विरुद्ध regular divergence (RSI 21 → 28) |
| PT | 0 | pattern नाही |
| GP | 10 | gap confirms |
| EW | 10 | Elliott end (S2) |
| RM | 0 | spot R:R 2.8 |
| TM | 0 | वेळ 14:30 — ठीक |
| VX | 0 | VIX data नाही |
| EV | 0 | event दिवस नाही |

Story (code narrative):

- [K1] HTF trend down (strong) · 1h DOWNTREND_PULLBACK, 1d DOWNTREND · [K3] Elliott D2: S2 (Tier A) — impulse 2 चा शेवट, invalidation 10,441.1
- [K2] impulse खाली 10,441.1 → 10,141.5 (15.21× MR, 48 bars)
- [K2] correction triangle (5 legs): 10,141.5 → 10,241.1 → 10,146.6 → 10,227.4 → 10,182.0 → 10,233.0; retrace 33%, वेळ impulse च्या 0.46× · pullback उथळ (< 38.2%)
- [K4/K6/K8] active area SWH-1492 (साधन e, ACTIVE) 10,225.4–10,229.4 · गुणवत्ता 0.40 · [K7] confluence: k, l · तपासलेली साधनं: a2, c1, d3, e4, f2, g2, h4, i3, j2, k5, l3
- [K9] लांब upper wick, close खाली — वर buyers नाकारले, sellers नी परत ढकललं · आकार 1.01× MR (लहान) · [K10] correction कमकुवत 0.80
- [K5] sweep + reclaim नाही · [K10.3] futures volume data नाही ⇒ 0 (trade अडत नाही) · [K10.2] impulse च्या टोकावर विरुद्ध regular divergence (RSI 21 → 28) · [K11] pattern नाही
- [K13] gap: G1 gap up 0.443× ATR · rejection · fill 100.0% ⇒ trade विरुद्ध gap अपयशी (setup A) · [K14] वेळ 14:30 — ठीक · VIX data नाही
- [K9] reversal: N=1 s=0.45 (weak) · mods weak ×0.84
- [A3] risk: invalidation 10,246.1 · target 10,141.5 (IMPULSE-END) · spot R:R 1:2.8 · मधले areas (target नाहीत): GAP0 10,216.2, RN10200 10,204.9, SWL-1495 10,184.0
- [भाग D] grade A (79.45) · मी चुकीचा ठरेन: 10,246.1 च्या पलीकडे close

Chart: `is_triangle.png` (gitignored)
