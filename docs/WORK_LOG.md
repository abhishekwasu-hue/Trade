# WORK_LOG — TRADE_FULL_EXECUTION_PROMPT अंमलबजावणी

प्रत्येक टप्प्याची नोंद: तारीख · टप्पा · काय केलं · tests (आधी → नंतर) · निर्णय (कारणासह) · उघडे प्रश्न.
नियम (§0.2): एक टप्पा = एक PR; डीफॉल्ट वर्तन बदलत नाही; नवीन gate/engine डीफॉल्ट OFF; no-lookahead; IS = 2015–2021, VAL = 2022 → 2024-03,
sealed holdout = Upstox 2024-04 → (फक्त G4 ला, एकदाच).

## सामायिक निर्णय (सर्व टप्प्यांना लागू)

- **Branch नाव:** PDF `claude/<phase>-<slug>` सांगतो, पण या session ला push फक्त `claude/project-review-n8v42i` वर करण्याची परवानगी आहे.
  म्हणून प्रत्येक टप्पा त्याच branch वर क्रमाने (प्रत्येक merge नंतर branch `origin/main` वर reset) — "एक टप्पा = एक PR" नियम पाळला जातो.
- **`docs/ROADMAP.md` अस्तित्वात नाही** — PDF च हाच roadmap मानला.
- **Validation कालावधी:** offline डेटा (`data/nifty50_1min.parquet`) 2024-03-27 ला संपतो ⇒ VAL = 2022-01-01 → 2024-03-27 (OE चा जुना OOS विभाग तोच).
- **Sealed holdout:** sandbox मधून Upstox पोहोचत नाही ⇒ `cache_holdout_upstox.py` VPS वर चालवायचा; तो फक्त bars/दिवस संख्या आणि sha256 छापतो.
