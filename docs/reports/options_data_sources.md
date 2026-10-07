# Options premium डेटा: स्रोत आणि क्रम (Elliott E0, 2026-10-06)

**प्रश्न:** Elliott Pullback Credit Spread च्या backtest मध्ये options P&L कशावरून मोजायचा?

**आजची स्थिती:** Offline फक्त NIFTY spot 1m आहे (2015-01-09 → 2024-03-27). Options चा एकही historical premium repo मध्ये नाही.

**Abhi ने ठरवलेला क्रम (2026-10-06):**
1. Upstox expired API.
2. NSE bhavcopy (IV काढून त्याने BS).
3. शुद्ध BS, शेवटचा पर्याय म्हणून.

Paid vendors समांतर तपासायचे, पण विकत घेणं Abhi च्या निर्णयानंतरच (G-PAID).

| # | स्रोत | काय मिळतं | मर्यादा | स्थिती |
|---|---|---|---|---|
| 1 | **Upstox Expired Instruments API**: Get Expiries, Get Expired Option Contracts, Get Expired Historical Candle Data | Expire झालेल्या contracts चे 1m / 3m / 5m / 15m / 30m / day OHLC | **Upstox Plus plan वरच** चालतो. किती जुना इतिहास मिळतो हे अज्ञात | VPS probe (`research/elliott_vps_data.py probe-expired`) निकाल सांगेल |
| 2 | **NSE F&O bhavcopy** (अधिकृत, मोफत) | प्रत्येक strike चा दैनिक OHLC, close, settlement, OI. Expiry तारखा (= ऐतिहासिक contract master). UDiFF format मध्ये (8 Jul 2024 पासून) lot size आणि underlying सुद्धा | Intraday नाही ⇒ त्या दिवसाच्या close वरून strike-निहाय IV काढून intraday entry/exit साठी BS वापरावं लागेल (premium **अंदाज**) | VPS वर download (`... bhavcopy`) होऊन private `trade-data` repo मध्ये जाईल |
| 3 | **शुद्ध Black-Scholes** (IV ≈ realised vol) | सगळीकडे वापरता येतो | Smile/skew नाही, आणि 1 DTE वर चूक मोठी | शेवटचा पर्याय. अहवालात ठळक "model premium" |
| 4 | **TrueData** (NSE authorized vendor) | त्यांच्या दाव्यानुसार: NSE futures contract-wise 1m data June 2015 पासून, tick 10 Nov 2018 पासून. Expired options साठी त्यांच्याकडे विचारणा करण्याचा सल्ला forums मध्ये | **किंमत सापडली नाही.** truedata.in sandbox मधून उघडत नाही | Quote मागवावा लागेल |
| 5 | **Global Datafeeds (GDFL)** (authorized vendor) | Historical API: tick, minute, day. Options contract-wise | **किंमत सापडली नाही.** API pricing पान sandbox मधून उघडत नाही | Quote मागवावा लागेल |
| — | Third-party resellers (moneyticks, optionsdata.shop इ.) | Expired NIFTY options 1m CSV | Licensing आणि गुणवत्ता अपडताळलेली ⇒ **शिफारस नाही** | — |

**Quote मागवताना नेमकी मागणी:**
- NIFTY index options, सर्व strikes, expired contracts.
- 1-minute OHLC + OI.
- काळ: Feb 2019 → Mar 2024. पर्यायाने 2026-07-01 → 2026-10-06 (golden).
- Format: CSV/parquet.
- एक-वेळ खरेदी, पुनर्वितरण नाही.

**निर्णय-नियम (E4 अहवालात लागू):**
- जो स्रोत वापरला तो प्रत्येक trade सोबत नोंदवायचा: `premium_source` = upstox_1m / bhavcopy_iv_bs / pure_bs.
- निकाल स्रोतानुसार वेगळे दाखवायचे.
- BS-आधारित निकालांवर "premium अंदाज" असा ठळक इशारा द्यायचा.

**स्रोत:**
- [Upstox: Expired Instruments](https://upstox.com/developer/api-documentation/expired-instruments/)
- [Upstox: Expired Historical Candle Data](https://upstox.com/developer/api-documentation/get-expired-historical-candle-data/)
- [Upstox: Expired Instruments API launch](https://upstox.com/developer/api-documentation/announcements/expired-instruments-api/)
- [TrueData pricing](https://www.truedata.in/price)
- [TrueData feedback forum: historical data plan](https://feedback.truedata.in/topic/38617-best-plan-for-historical-data-for-nifty-fn)
- [GDFL: API pricing](https://globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/pricing-sales/api-pricing/)
- [GDFL: type of data](https://globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/introduction/type-of-data-available/)
- [Kite forum: expired options candles](https://kite.trade/forum/discussion/14374/how-to-fetch-candlestick-data-for-expired-options)
