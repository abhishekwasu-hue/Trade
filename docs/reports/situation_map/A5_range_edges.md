# नकाशा A5: range कडांचे tests (G10 / S9), IS 2015–2021

**फक्त अहवाल; threshold नाही.** Range = 15M StructureTracker RANGE (KB K1). Outcome फक्त गटांसाठी. R:R: entry = decision close, SL = sweep टोक / कड ∓ 0.25 MR, target = विरुद्ध कड.

एकूण tests: 496

| प्रकार | n | विरुद्ध कड आधी | कड तुटली आधी | दोन्ही नाही | R:R ≥ 3 शक्य | उंची ÷ risk (median) |
|---|---|---|---|---|---|---|
| sweep_reclaim | 162 | 49 | 113 | 0 | 99 | 4.4399999999999995 |
| rejection | 258 | 74 | 183 | 1 | 204 | 6.48 |
| real_break | 76 | 0 | 0 | 0 | 0 | — |

## S6 + S9: पालक (HTF) trend असताना

| कड | n | विरुद्ध कड आधी | कड तुटली आधी | R:R ≥ 3 शक्य |
|---|---|---|---|---|
| trend दिशेची कड | 183 | 49 | 133 | 133 |
| विरुद्ध कड | 231 | 71 | 160 | 166 |
| पालक trend नाही (शुद्ध S9) | 6 | 3 | 3 | 4 |

**मर्यादा:** market_state F2 trend दिशा ठरल्यावर range मध्ये जात नाही ⇒ "पालक trend नाही" गट जवळजवळ रिकामा राहतो.
Range ओळखीचे parameters (StructureTracker pivot_n / swing_k / N=4 swings) A1 register मध्ये.
