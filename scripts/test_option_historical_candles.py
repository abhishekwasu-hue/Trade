"""
scripts/test_option_historical_candles.py
------------------------------------------
🎓 वापरकर्त्याने विचारलेला प्रश्न ("प्रत्येक trade सोबत NIFTY चा चार्टच नाही तर त्या trade मध्ये
प्रत्यक्ष घेतलेल्या CE/PE option strike चाही चार्ट (एन्ट्री/एक्झिट मार्क करून) PDF Report मध्ये
हवाय") — हे बांधण्याआधी एक मूलभूत प्रश्न पडताळणे आवश्यक आहे: Upstox चं historical-candle API
(जे सध्या फक्त NIFTY/BANKNIFTY सारख्या index साठी वापरलं जातं) एखाद्या specific option
contract (instrument_key) साठीही डेटा देतं का — विशेषतः तो contract आधीच expire झालेला
असला तरी.

वापर:
  python3 scripts/test_option_historical_candles.py <access_token> <instrument_key> <from_date> <to_date> [interval]

उदा:
  python3 scripts/test_option_historical_candles.py "eyJhbG..." "NSE_FO|44444" 2026-09-20 2026-09-20 5minute

instrument_key कुठून मिळेल:
  तुमच्या live trades.db मध्ये (VPS वर) असा query चालवा -- अलीकडेच बंद झालेल्या एखाद्या
  credit-spread trade चा एक leg निवडून:

    sqlite3 trades.db "SELECT order_id, trade_id, instrument_key, strike, option_type, placed_at
                        FROM order_log WHERE trade_id = '<तुमचा एखादा trade_id>' ORDER BY placed_at;"

  यातून मिळालेला instrument_key (उदा. "NSE_FO|44444") आणि त्या trade चा entry/exit दिवस
  (from_date/to_date -- दोन्ही सारखेच द्या, बहुतेक सर्व trades त्याच दिवशी बंद होतात) इथे वापरा.

हा script फक्त वाचन (GET, historical data) करतो -- कुठलाही ऑर्डर placement किंवा database
बदल करत नाही, त्यामुळे production वर सुरक्षितपणे चालवता येतो.
"""
import sys
import urllib.parse

import requests


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)

    access_token, instrument_key, from_date, to_date = sys.argv[1:5]
    interval = sys.argv[5] if len(sys.argv) > 5 else "5minute"

    interval_map = {
        "1minute": ("minutes", "1"), "5minute": ("minutes", "5"), "15minute": ("minutes", "15"),
        "30minute": ("minutes", "30"), "1hour": ("hours", "1"), "day": ("days", "1"),
    }
    unit, val = interval_map.get(interval, ("minutes", "5"))

    encoded_key = urllib.parse.quote(instrument_key, safe="")
    url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/{unit}/{val}/{to_date}/{from_date}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}"}

    print(f"GET {url}")
    res = requests.get(url, headers=headers, timeout=20)
    print(f"Status: {res.status_code}")

    if res.status_code != 200:
        print("Response body:", res.text[:2000])
        print("\n[निष्कर्ष] हा status code 200 नाही -- या instrument_key साठी Upstox कडून historical "
              "candles मिळत नाहीयेत (कदाचित expired contract चा डेटा ठेवलेला नसेल, किंवा instrument_key "
              "चुकीचा असेल). हे feature सध्याच्या स्वरूपात बांधता येणार नाही.")
        sys.exit(1)

    data = res.json()
    candles = data.get("data", {}).get("candles", [])
    print(f"मिळालेले candles: {len(candles)}")
    if candles:
        print("पहिला candle:", candles[0])
        print("शेवटचा candle:", candles[-1])
        print("\n[निष्कर्ष] ✅ या instrument_key साठी historical candles मिळाले -- फीचर बांधण्यायोग्य आहे.")
    else:
        print("\n[निष्कर्ष] ⚠️ Status 200 आला पण candles रिकामे आहेत -- या तारीख-रेंजसाठी डेटा नाही "
              "(कदाचित वेगळी तारीख-रेंज वापरून बघा, किंवा हा contract त्या दिवशी अजून सुरूच झाला नव्हता).")


if __name__ == "__main__":
    main()
