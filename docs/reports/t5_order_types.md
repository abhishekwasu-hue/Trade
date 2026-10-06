# T5 — Order type तपासणी (SEBI retail-algo framework) → **G3 वर थांबलो**

**हा अहवाल + default-off code फक्त.** LIVE order मार्गात कोणताही बदल केलेला नाही. `order_execution.py` कुठूनही कॉल होत नाही.

## 1. नियम काय सांगतात (सार्वजनिक स्रोत, 2026-10-06 ला शोधलेले)

> Sandbox मधून upstox.com / community.upstox.com थेट उघडता आलं नाही (network egress block). खालील माहिती search-result सारांशांवरून घेतली आहे — **VPS वर/Upstox docs मध्ये प्रत्यक्ष पडताळणी आवश्यक.**

- NSE/BSE/MCX च्या algo नियमांनुसार **API मधून शुद्ध MARKET orders ला परवानगी नाही**. Upstox: "1 Oct 2025 पासून API मधले market orders process होणार नाहीत" (नंतर SEBI ची पूर्ण अंमलबजावणी 1 Apr 2026).
  हे निर्बंध फक्त API/Algo साठी आहेत; app/web वरून market orders चालतात.
- Upstox ने Place Order / Multi Order (v2) आणि v3 मध्ये **`market_protection`** parameter दिला आहे. तो MARKET आणि SL-M orders ला लागू होतो:
  - `-1` (डीफॉल्ट) = नियमांनुसार **आपोआप** market protection;
  - `1–25` = स्वतःचा %;
  - `0` = protection नाही ⇒ exchange निर्बंधामुळे **order नाकारला जातो**.
- **MCX orders API मधून "तात्पुरते बंद"** असल्याचा उल्लेख Upstox community मध्ये आहे (तारीख/सद्यस्थिती अस्पष्ट).
- Angel One (PDF मधला संदर्भ): algo साठी MARKET आणि IOC निषिद्ध.
- 10 orders/second पेक्षा जास्त ⇒ exchange registration; प्रत्येक algo order वर exchange चा unique identifier — आपले bots यापेक्षा खूप कमी OPS वर चालतात.

स्रोत:
- [Upstox Community — Pausing Market orders via APIs](https://community.upstox.com/t/regulatory-update-pausing-market-orders-via-apis/11306)
- [Upstox Community — New SEBI & Exchange mandates (1 Apr 2026)](https://community.upstox.com/t/important-new-sebi-exchange-mandates-for-api-trading-effective-1st-april-2026/14822)
- [Upstox Place Order API](https://upstox.com/developer/api-documentation/place-order/)
- [Upstox Place Multi Order API](https://upstox.com/developer/api-documentation/place-multi-order/)
- [Upstox Place Order V3](https://upstox.com/developer/api-documentation/v3/place-order/)
- [Upstox — SEBI retail algo deadline](https://upstox.com/news/market-news/financial-regulations/sebi-extends-timeline-for-retail-algo-trading-framework-sets-glide-path-for-brokers/article-182285/)

## 2. आपल्या code मध्ये MARKET / SL-M कुठे वापरला जातो

| # | ठिकाण | काय | धोका (MARKET नाकारला तर) |
|---|---|---|---|
| 1 | `trading_engine.py:1029` `open_multi_leg_trade` | सर्व bots ची **entry** (multi-leg, Upstox `/v2/order/multi/place`) | entry होत नाही — सुरक्षित बाजू, पण hedge-आधी-SELL क्रम बिघडल्यास partial (auto-reverse आहे) |
| 2 | `trading_engine.py:2114` `manage_open_trades` | **SL / Target / TSL exit** | **सर्वात गंभीर**: exit न झाल्यास position उघडी राहते |
| 3 | `trading_engine.py:2370` manual close | Positions पानावरचं Manual Close | exit अयशस्वी — वापरकर्त्याला संदेश मिळतो |
| 4 | `trading_engine.py:220` `_auto_reverse_filled_legs` | partial fill नंतर भरलेले legs उलटवणे | unhedged leg उघडा राहू शकतो |
| 5 | `trading_engine.py:820/822` → `upstox_api.place_stop_loss_order` | broker-side **SL-M** (resting) | SL-M ही market_protection खाली येतो; नाकारला तर broker-side SL नाही (polling exit तरी चालू) |
| 6 | `page_dashboard.py:637` | मॅन्युअल order फॉर्म (MARKET/LIMIT/SL/SL-M) | वापरकर्ता स्वतः निवडतो |
| 7 | `stocko_api.py:139` | `market_protection_percentage: 0` | Stocko साठी 0 ⇒ नियमांनुसार नाकारला जाण्याची शक्यता |
| 8 | `shoonya_api.py:236` | MARKET ⇒ `prctyp: MKT` | broker-निहाय नियम लागू |

**Upstox payload मध्ये `market_protection` पाठवला जात नाही** (`upstox_api._broker_payload_orders`). Docs नुसार तो न दिल्यास डीफॉल्ट −1 (auto protection) लागतो.
म्हणून सध्याचे Upstox MARKET orders "auto protection" ने स्वीकारले जात **असावेत**. पण v2 multi-order endpoint वर डीफॉल्ट नक्की लागू होतो का हे इथून सिद्ध करता येत नाही.

## 3. VPS वर पडताळणी (read-only — फक्त मोजणी)

1 Oct 2025 नंतरचे LIVE orders: order_type × status. FAILED/REJECTED जास्त असतील तर MARKET निर्बंधाचा परिणाम.

```bash
cd /root/Trade && python3 - <<'EOF'
import sqlite3
from config import DB_PATH
c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)   # फक्त वाचन; चुकीचा path असल्यास नवी फाईल तयार होत नाही
for r in c.execute("SELECT mode, order_type, status, COUNT(*) FROM order_log WHERE placed_at >= '2025-10-01' GROUP BY 1,2,3 ORDER BY 1,2,3"):
    print(r)
EOF
```

## 4. काय तयार केलं (डीफॉल्ट OFF, जोडलेलं नाही)

`order_execution.py` + `tests/test_order_execution.py` (8 tests):
- `apply_order_style(orders, style)`:
  - `"MARKET"` (डीफॉल्ट) ⇒ अगदी तेच orders;
  - `"MARKET_PROTECTION"` ⇒ MARKET/SL-M ला `market_protection` = 1–25 (0 नाकारतो);
  - `"MARKETABLE_LIMIT"` ⇒ LIMIT @ LTP ± buffer, tick ला marketable बाजूने गोल.
- `run_marketable_limit(...)`: एका leg साठी partial fill सांभाळतो.
  - ठराविक वेळेत न भरल्यास उरलेलं cancel करतो, नवीन LTP ± वाढीव buffer ने पुन्हा पाठवतो (कमाल retries).
  - शेवटी filled / remaining / सरासरी किंमत / log परत देतो.
  - Broker functions injectable आहेत (network नाही).
  - Cancel निश्चित न झाल्यास पुढे retry करत नाही आणि `unresolved_order_id` देतो (दुहेरी position टाळण्यासाठी). Over-fill वेगळा नोंदवतो. BUY/SELL व्यतिरिक्त side नाकारतो.

## 5. G3 — तुमचा निर्णय हवा

1. आधी §3 ची VPS मोजणी पाठवा. MARKET orders नाकारले जात आहेत का, ते त्यावरून कळेल.
2. **माझी शिफारस (कमी धोका):**
   - (a) Upstox entry/exit orders मध्ये `market_protection` स्पष्ट भरावा (उदा. 2–3%) — एक ओळीचा, सर्वात कमी बदल; डीफॉल्टवर अवलंबून राहणं टळतं.
   - (b) exits (SL/Target) साठी marketable-LIMIT **नको** — partial fill / retry मुळे exit उशिरा होण्याचा धोका.
   - (c) entries साठी marketable-LIMIT हा पर्याय (setting, डीफॉल्ट MARKET) PAPER मध्ये आधी तपासावा.
3. Stocko चा `market_protection_percentage: 0` बदलायचा का? (Stocko वापरत असाल तरच.)
4. MCX API orders चालू आहेत का, हे Upstox कडून/VPS logs मधून पडताळावं.


## 6. G3 नंतर (2026-10-06) — काय लागू केलं

वापरकर्त्याचा VPS पुरावा: 2026-09-10 ची NIFTY LIVE spread entry (MARKET, `market_protection` शिवाय) Upstox API वर COMPLETE ⇒ Upstox चा डीफॉल्ट auto protection काम करतो.

- **`order_market_protection_pct`** (Dashboard sidebar → "🧾 Order सुरक्षा"):
  - डीफॉल्ट बंद ⇒ field पाठवत नाही, सध्याचं वर्तन.
  - चालू केल्यास (1–25%) entry आणि सर्व exits (SL/Target/TSL, manual close, auto-reverse) मध्ये लागू.
  - LIVE वर चालू करण्याचा निर्णय वापरकर्त्याचा.
- **Exit अपयश इशारा** (डीफॉल्ट ON, फक्त सूचना): leg-निहाय स्थिती, "POSITION अजून उघडी", partial-exit धोका, throttle, recovery संदेश.
- **Exit retry** (डीफॉल्ट OFF): फक्त पूर्ण अपयशावर, त्याच cycle मध्ये एकदा. Partial exit वर नाही.
- **MARKETABLE_LIMIT:** फक्त entries; अजूनही जोडलेला नाही.
- **उघडा धोका:** partial exit नंतर पुढच्या cycle ला सर्व legs पुन्हा पाठवले जातात — `docs/WORK_LOG.md` मधला प्रस्ताव पाहा.
