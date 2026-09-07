"""
check_token_freshness.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — रोजचा Upstox token refresh (get_upstox_token_manual.py)
अजूनही मॅन्युअल (लॉगिन + OTP) आहे, established Notifier Webhook अविश्वसनीय ठरल्यामुळे. हा एकच
मॅन्युअल स्टेप चुकला, तर दिवसभराचे सर्व cron jobs (oi_signal_auto_trader, srv2_momentum_reversal_strategy
इ.) token न मिळाल्याने शांतपणे थांबतात — कुठलाही alert न येता.

ही script दररोज बाजार उघडण्याआधी (established GitHub Actions schedule वरून) चालून established
Supabase (upstox_tokens table) मधला सर्वात अलीकडचा token किती जुना आहे ते तपासते — token नसेल किंवा
threshold पेक्षा जुना असेल, तरच established notifications.py मार्फत Telegram वर alert पाठवते
(established, ताजा token असेल तर शांत राहते — रोज उगाच "सर्व ठीक आहे" संदेश पाठवत नाही, फक्त
समस्या असेल तेव्हाच).

Multi-account: established --account-id दिला तर फक्त त्याच account चा token तपासला जातो;
न दिल्यास established, एकमेव (single) खात्याचा token तपासला जातो (backward-compatible).

चालवणे:
    python3 check_token_freshness.py [--account-id <ACCOUNT_ID>] [--max-age-hours 20]
"""
import argparse
import sys

import cloud_db
from notifications import send_telegram_message


def check_and_alert(account_id=None, max_age_hours=20.0):
    """
    रिटर्न: (is_stale_or_missing: bool, message: str) — CLI आणि टेस्ट्स दोन्हीसाठी उपयोगी.
    """
    account_label = f"account '{account_id}'" if account_id else "established, एकमेव (single) खातं"

    if not cloud_db.is_cloud_db_configured():
        # Cloud DB configured नसेल तर हा check अर्थहीन आहे (dashboard/cron आधीच secrets/manual token
        # वापरत असतील) — शांतपणे थांबणे, alert न पाठवणे.
        return False, "Cloud DB configured नाही — token freshness check वगळला."

    age_hours = cloud_db.get_token_age_hours(account_id)

    if age_hours is None:
        message = (
            f"⚠️ Upstox Token सापडला नाही ({account_label})!\n"
            f"आजचा manual OAuth login (get_upstox_token_manual.py) अजून केलेला दिसत नाही — "
            f"आजचे auto-trading cron jobs token न मिळाल्याने चालणार नाहीत."
        )
        send_telegram_message(message)
        return True, message

    if age_hours > max_age_hours:
        message = (
            f"⚠️ Upstox Token जुना झालाय ({account_label}) — शेवटचा {age_hours:.1f} तासांपूर्वी साठवला होता "
            f"(मर्यादा: {max_age_hours} तास).\n"
            f"आजचा manual OAuth login (get_upstox_token_manual.py) करा, नाहीतर auto-trading थांबेल."
        )
        send_telegram_message(message)
        return True, message

    return False, f"✅ Token ताजा आहे ({account_label}) — {age_hours:.1f} तासांपूर्वी साठवला."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", default=None,
                         help="🎓 'Multi-Broker Multi-Account' — established broker_accounts मधलं nickname; "
                              "न दिल्यास established, single-account token तपासला जातो.")
    parser.add_argument("--max-age-hours", type=float, default=20.0,
                         help="या तासांपेक्षा जुना token असेल तर alert (डीफॉल्ट: 20 तास — Upstox token रोज expire होतो).")
    args = parser.parse_args()

    is_stale, msg = check_and_alert(account_id=args.account_id, max_age_hours=args.max_age_hours)
    print(msg)
    sys.exit(1 if is_stale else 0)
