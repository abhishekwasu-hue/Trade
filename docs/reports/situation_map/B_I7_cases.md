# टप्पा B: नकाशा I7 उदाहरणं (PROVISIONAL)

**फक्त अहवाल.** टप्पा B engine (PAPER seed) — दिवसाचा 15M replay decision bar पर्यंत, फक्त त्या वेळेपर्यंतचा data. नकाशाचं उत्तर (KB I7) आधी, code चं उत्तर नंतर. FAIL ⇒ I6 प्रक्रिया: कोणता थर (वाचन / निर्णय / अंमलबजावणी) — constants बदलून pass करायचं नाही. Jul–Oct 2026 = illustration; 2018 / 2021 = IS.

| दिवस | bar | नकाशा | code (त्या bar ला / दिवसभर) | S# · gray | impulse | count | निकाल |
|---|---|---|---|---|---|---|---|
| 2026-08-12 | 10:15 | none | नाही (10:15): area वर commitment candle नाही | None · — | — | None | **जुळतं** |
| 2026-08-25 | 10:45 | none | नाही (10:45): TESTING_ONLY_FLIP_OR_EDGE — flip: commitment area पासून दूर (area ला ल | None · — | — | None | **जुळतं** |
| 2026-08-26 | दिवस | bear | SIGNAL bear G4 (10:00) | S2 · — | 24,405.2 → 24,025.7 | D3 flat/B | **जुळतं** |
| 2026-08-31 | दिवस | none | नाही (15:15): commitment (30.3) pause सरासरीच्या (58.6) 1.5× पेक्षा लहान | None · — | — | None | **जुळतं** |
| 2026-09-22 | 15:00 | bear | नाही (15:00): commitment area पासून दूर (area ला लागलेला नाही) — chase नाही | None · — | — | None | **FAIL (code signal नाही)** |
| 2026-09-28 | 14:15 | bear | नाही (14:15): commitment area पासून दूर (area ला लागलेला नाही) — chase नाही | None · — | — | None | **FAIL (code signal नाही)** |
| 2026-10-07 | 09:30 | none | नाही (09:30): area वर commitment candle नाही | None · — | — | None | **जुळतं** |
| 2026-10-07 | 12:15 | bear | SIGNAL bear  (12:15) | S8 · — | 22,809.3 → 22,217.3 | D3 flat/B | **जुळतं** |
| 2018-02-16 | 13:30 | none | नाही (13:30): Gray-2 (block): Gray-2: IMPULSE_NA: correction origin अजून confirmed p | S5 · Gray-2 | IMPULSE_NA: correction origin अजून confi | correction origin नाही | **जुळतं** |
| 2018-02-16 | 09:30 | check | नाही (09:30): commitment (24.8) pause सरासरीच्या (32.5) 1.5× पेक्षा लहान | None · — | — | None | **Abhi ✔/✘ (अट तपासून उत्तर)** |
| 2021-11-15 | 13:00 | check | SIGNAL bear G4 (13:00) | S1 · Gray-2 | IMPULSE_NA: correction origin अजून confi | correction origin नाही | **Abhi ✔/✘ (अट तपासून उत्तर)** |

## I6: FAIL केसेस (आणि I6 ने सुटलेले) — कोणता थर

### 2026-09-22 15:00 — S6: wave (4) end ⇒ G9 bear call · आता: **FAIL (code signal नाही)**
- थर = **निर्णय (Simple Core commitment gate)**, reading layer नाही: (4) चं टोक 23,489 (09:15) / area RN23500 flip; 10:15 ची bear commitment (range 34.6) `commitment_vs_pause` 1.5 × pause सरासरी 30.6 पेक्षा लहान ⇒ नाकारली. नंतरचे bars area पासून दूर (chase नियम).
- `commit_vs_impulse` (§2.1, फक्त report): impulse 23,592.8 (15 Sep 09:15) → 23,116.1 (16 Sep 09:45), 27 bars median range 33.3 ⇒ 10:15 ला 34.6 / 33.3 = **1.04** — [प्रस्ताव] ≥ 1.0 स्तंभात हा signal असता. G-MAP1 निर्णय 1 चा प्रश्न (Abhi), gate बदल नाही.
- bar-निहाय (शेवटचे):
  - 13:45: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 14:00: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 14:15: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 14:30: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 14:45: नाही · area वर pause नाही (indecision bars 0 < 1) — थेट entry नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 15:00: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None

### 2026-09-28 14:15 — S1 bear (flag 11 candles ⇒ G8 नाही) · आता: **FAIL (code signal नाही)**
- थर = **वाचन (area, P5)**: नकाशाचा S1 area = तुटलेला swing 23,021 (zones मध्ये PDL / PWL flip 23,014–23,028 म्हणून आहे, पण 6.9 MR दूर) आणि displacement base 22,856–22,912 — हा base **zones यादीत नाही** (tool c ने तयार केला नाही). Pause 13:15–14:00 (22,818–22,848) च्या जवळचा फक्त SWH-1523 liquidity (22,853–22,858, 0.99 MR) — commitment 14:15 त्याला लागलेली नाही ⇒ 'दूर'.
- पुढची पायरी (I6.3): 'displacement base' tool c चे IS look-alike संच; constants बदल नाही. Abhi ✔ (A3 MAP CHECK) बाकी.
- bar-निहाय (शेवटचे):
  - 13:00: नाही · area वर commitment candle नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 13:15: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 13:30: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 13:45: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 14:00: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 14:15: नाही · commitment area पासून दूर (area ला लागलेला नाही) — chase नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None

### 2026-10-07 12:15 — S10-B → S1: C-diagonal + seller zone ⇒ G5 bear call (Abhi ✔ 2026-10-09: 12:15 = C-end) · आता: **जुळतं**
- Abhi ✔ (2026-10-09, run2 review): 12:15 = C-end, bear call बरोबर ⇒ golden पक्का.
- थर = **वाचन (count ranking)**: impulse 22,809.35 → 22,217.3 आणि legs (A-B-C, C ने A गाठलं) नकाशाशी जुळतात; पालक खाली ✔. पण D3 वर beam मधले counts (flat/B, impulse/2, wxy/X, zigzag/B, flat/A) **सगळे score 0.5 — बरोबरी**; counts.py चा sort tie-break pattern च्या नावाने ⇒ 'preferred' = flat/B ⇒ S11. म्हणजे पसंती नव्हतीच.
- दुरुस्ती त्याच थरात (I6.2): score tie ⇒ count-आधारित S11 / G1 / G9 नाहीत ('count tie' नोंद). Constants बदल नाही. IS वर आधी / नंतर परिणाम: §4 अहवाल विभाग 10 (I6.3–4).
- bar-निहाय (शेवटचे):
  - 11:00: नाही · area वर commitment candle नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 11:15: नाही · area वर commitment candle नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 11:30: नाही · area वर commitment candle नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 11:45: नाही · area वर commitment candle नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 12:00: नाही · area वर commitment candle नाही · S None  · gray None · legs None · S3 None · count None · पालक ms -1 / count None
  - 12:15: SIGNAL · ENTRY SIGNAL · S S8 ['S8', 'S2', 'S6', 'S10'] · gray None · legs A-B-C: C ने A चं टोक गाठलं / ओलांडलं · S3 S3_NO_1H_PIVOT · count D3 flat/B · पालक ms -1 / count 0

