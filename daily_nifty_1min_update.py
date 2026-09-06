"""
daily_nifty_1min_update.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — Supabase मधल्या nifty_1min_ohlc table मध्ये आधीच
साठवलेल्या **शेवटच्या** timestamp पासून, आजपर्यंतचा 1-मिनिट NIFTY डेटा Upstox कडून मिळवून भरणे.

एकच, एकत्रित (unified) script — दोन्ही उद्देशांसाठी वापरता येते:
  १. **एक-वेळचं Gap-Fill**: पहिल्यांदा चालवली की, established parquet (2024-03-27 पर्यंतचा)
     migrate केल्यानंतर उरलेला मोठा गॅप (2024-03-28 पासून आजपर्यंत) एकाच वेळी भरते.
  २. **रोजचं अद्ययावतीकरण**: दररोज बाजार बंद झाल्यावर चालवली की, फक्त कालच्या/आजच्या नवीन candles
     भरते (established ON CONFLICT DO NOTHING मुळे पुन्हा चालवलं तरी सुरक्षित/idempotent).

established `fetch_candles()` "1minute" interval साठी आधीच अंतर्गतरित्या २८-दिवसांच्या तुकड्यांत
(chunked calls) संपूर्ण मागितलेला कालावधी मिळवतं — इथे फक्त योग्य `lookback_days` द्यायचा आहे.

चालवणे:
    python3 daily_nifty_1min_update.py --token <UPSTOX_TOKEN>
"""
import argparse
import datetime

import cloud_db
from upstox_api import fetch_candles

# 🎓 Upstox कडून प्रत्यक्षात किती जुना 1-मिनिट डेटा मिळू शकतो याची खात्री नाही (अनेक ब्रोकर्स मर्यादित
# इतिहासच देतात) -- वापरकर्त्याने स्पष्ट सांगितल्याप्रमाणे संपूर्ण गॅप भरण्याचा प्रयत्न करणे, आणि
# प्रत्यक्षात किती दिवस भरले गेले ते स्पष्टपणे अहवालात दाखवणे (गृहीत न धरता).
MAX_GAP_FILL_DAYS = 900  # established parquet 2024-03-27 ला संपतो -- आजपर्यंत (~दीड-पावणे दोन वर्षं)


def update_nifty_1min(access_token):
    """Supabase मधल्या शेवटच्या timestamp पासून आजपर्यंतचा गॅप भरणे."""
    cloud_db.init_cloud_table()
    latest_ts = cloud_db.get_nifty_1min_latest_timestamp()
    now = datetime.datetime.now()

    if latest_ts is None:
        return False, "Supabase मध्ये अजून कुठलाही डेटा नाही -- आधी migrate_nifty_1min_to_supabase.py चालवा."

    days_behind = (now.date() - latest_ts.date()).days
    if days_behind <= 0:
        return True, f"आधीच अद्ययावत आहे (शेवटचा candle: {latest_ts})."

    lookback_days = min(days_behind + 2, MAX_GAP_FILL_DAYS)  # +2 दिवसांचं मार्जिन (weekend/holiday सुरक्षिततेसाठी)
    df_new = fetch_candles(access_token, "NIFTY", current_spot=0, interval="1minute", lookback_days=lookback_days)
    if df_new is None or df_new.empty:
        return False, f"Upstox कडून 1-मिनिट डेटा मिळाला नाही (मागितलेले {lookback_days} दिवस)."

    # 🎓 established ON CONFLICT DO NOTHING मुळे, latest_ts च्याही आधीचा डेटा पुन्हा आला तरी सुरक्षित --
    # तरीही, अनावश्यक मोठा payload टाळण्यासाठी फक्त नवीनच रांगा फिल्टर करून पाठवणे.
    df_new_only = df_new[df_new["timestamp"] > latest_ts]
    if df_new_only.empty:
        return True, f"नवीन candles सापडले नाहीत (शेवटचा साठवलेला: {latest_ts})."

    rows = df_new_only.to_dict("records")
    ok = cloud_db.save_nifty_1min_batch(rows)
    if not ok:
        return False, "Supabase मध्ये साठवता आलं नाही (जोडणी तपासा)."
    return True, f"{len(rows):,} नवीन candles साठवले ({df_new_only['timestamp'].min()} ते {df_new_only['timestamp'].max()})."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    args = parser.parse_args()

    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)

    ok, message = update_nifty_1min(token)
    print(("✅ " if ok else "❌ ") + message)
