# Chart Reader G-E1a — Knowledge Base अहवाल (report-only)

> IS 2015–2021 (15m, NIFTY). MR = 20 बंद bars (चालू bar वगळून, KB भाग G). Weights / A ≥ 60 · B 45–59 · C < 45 — Abhi ने मंजूर, tuning नाही. VL (futures volume) आणि VX (VIX) ला IS मध्ये data नाही ⇒ 0 (त्यांचं मूल्य फक्त PAPER scorecard मधून).

## 1. MR-आधारित आकड्यांचं calibration (बदल नाही — Abhi चा निर्णय)

- MR20 ÷ ATR14 (p10 / p50 / p90): [0.716, 0.902, 1.087] · MR20 ÷ median-50: [0.829, 0.998, 1.216]

### (a) Equal highs / lows tolerance (सध्या 0.15 MR)

Same-kind pivot जोड्या: 7870 · जवळच्या जोडीचं अंतर (p10 / p25 / p50, MR): [0.101, 0.286, 0.771] · baseline (अंतर > 1 MR) retest वर reject: 68.0%

| tol (MR) | equal partner असलेले pivots % | pool retests | retest वर reject % |
|---|---|---|---|
| 0.1 | 9.8 | 685 | 64.7 |
| 0.15 | 14.0 | 973 | 64.5 |
| 0.2 | 18.3 | 1256 | 64.9 |
| 0.25 | 22.4 | 1533 | 65.5 |
| 0.35 | 29.5 | 2014 | 65.6 |
| 0.5 | 38.3 | 2612 | 65.5 |

### (b) Sweep खोली (सध्या 0.1–1.0 MR)

Confirmed swing pivot च्या पलीकडची पहिली wick. Reclaim = त्याच / पुढच्या 2 bars पैकी close परत आत. यश = reclaim नंतर 20 bars मध्ये pivot ± 1 MR आत, sweep चं टोक तुटण्याआधी.

| खोली (MR) | n | reclaim % | reclaim नंतर यश % |
|---|---|---|---|
| 0–0.1 | 787 | 95.9 | 47.3 |
| 0.1–0.25 | 984 | 89.6 | 48.1 |
| 0.25–0.5 | 1258 | 78.6 | 56.2 |
| 0.5–1.0 | 1442 | 58.1 | 65.5 |
| 1–1.5 | 772 | 44.8 | 74.0 |
| 1.5–∞ | 1432 | 20.3 | 85.5 |

### (c) Fibonacci band (सध्या ± 0.25 MR)

Impulse (≥ 4.0 MR) नंतरचे pullbacks: 1162. जवळच्या 38.2/50/61.8/78.6 पासून अंतर ≤ band, विरुद्ध uniform retrace (null).

| band (MR) | pullback टोकं band मध्ये % | uniform null % |
|---|---|---|
| ± 0.15 | 18.2 | 19.3 |
| ± 0.25 | 30.5 | 31.1 |
| ± 0.35 | 42.2 | 40.9 |
| ± 0.5 | 56.7 | 54.5 |

## 2. IS grade वितरण (pullback-end उमेदवार, पूर्ण evaluate, Elliott सह)

उमेदवार: 675 (scan 199.8 s) · नमुना 400 · grade %: {'A': 3.2, 'B': 8.2, 'C': 88.5} · entries 12 · व्हेटो 17 {'⛔ [K3]': 10, '⛔ S6a (B-end → C) setup ': 7}

Total (p10 / p25 / p50 / p75 / p90): [0.0, 0.0, 11.5, 29.0, 47.0]

| प्रकार | n | A % | B % | C % | entries |
|---|---|---|---|---|---|
| flat | 121 | 2.5 | 5.0 | 92.6 | 0 |
| triangle | 64 | 6.2 | 15.6 | 78.1 | 0 |
| zigzag | 215 | 2.8 | 7.9 | 89.3 | 12 |

सरासरी गुण: T +1.84 · PB +2 · CW +8.17 · AQ +4.62 · CF +4.36 · LQ +0.96 · RV -5.3 · VL +0 · DV -0.47 · PT -2.16 · GP -2.1 · EW -1.99 · RM +0.64 · TM -0.86 · VX +0 · EV +0

## 3. स्पष्ट reversal दिवस 2018-02-02 (अपेक्षित: bull put बाजूला C / entry नाही)

bull put बाजूचे bars 19 · grades {'A': 0, 'B': 0, 'C': 19} · entries 0

| वेळ | बाजू | grade | total | PB | entry | व्हेटो / कारण |
|---|---|---|---|---|---|---|
| 09:45 | +1 | C | 2 | 0 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, pullback) |
| 10:00 | +1 | C | 7 | 0 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, pullback) |
| 10:15 | +1 | C | 0 | 0 | नाही | pullback end नाही (correction complex, pullback); reversal: wait_followthrough |
| 10:30 | +1 | C | 0 | 0 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, pullback) |
| 10:45 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, unclear) |
| 11:00 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, unclear) |
| 11:15 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 11:30 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 11:45 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 12:00 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 12:15 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 12:30 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 12:45 | +1 | C | 0 | -10 | नाही | pullback end नाही (correction complex, reversal); grade C (0) |
| 13:00 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 13:15 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 13:30 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 13:45 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 14:00 | +1 | C | 0 | -10 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 14:15 | +1 | C | 0 | -15 | नाही | active area नाही (ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही); pullback end नाही (correction complex, reversal) |
| 14:30 | +0 | C | 0 | 0 | नाही | impulse / बाजू नाही; pullback end नाही (correction —, none) |
| 14:45 | +0 | C | 0 | 0 | नाही | impulse / बाजू नाही; pullback end नाही (correction —, none) |
| 15:00 | +0 | C | 0 | 0 | नाही | impulse / बाजू नाही; pullback end नाही (correction —, none) |
| 15:15 | +0 | C | 0 | 0 | नाही | impulse / बाजू नाही; pullback end नाही (correction —, none) |
| 15:30 | +0 | C | 0 | 0 | नाही | impulse / बाजू नाही; pullback end नाही (correction —, none) |

## 4. 7 Oct 2026 golden (contaminated, illustration only; अपेक्षित A)

**Data अजून नाही:** `trade-data/upstox/NIFTY_1m_2026-07-01_2026-10-08.csv.gz` — VPS export block चालल्यावर हा अहवाल पुन्हा.
