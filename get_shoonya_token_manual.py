"""
get_shoonya_token_manual.py
--------------------------------
get_upstox_token_manual.py/get_fyers_token_manual.py च्याच पॅटर्नने बांधलेला, Shoonya साठीचा
token-मिळवण्याचा script — पण Shoonya ला OAuth-redirect (ब्राउझर/auth_code) लागत नाही, थेट
credential-based login (userid + password + 2FA) एकाच API कॉलमध्ये होतो.

रोजची पद्धत (दर दिवशी, टोकन expire झाल्यावर):
    python3 get_shoonya_token_manual.py --userid <UID> --password <PWD> --vendor-code <VC> \\
        --api-secret <API_SECRET> --totp-secret <TOTP_SECRET> --account-id <नाव> --save-to-supabase

--totp-secret दिला तर (Shoonya/Finvasia च्या 2FA सेटअप वेळी एकदाच दाखवलेला, Base32 स्वरूपातला गुप्त
कोड — कुठल्याही Authenticator app मध्ये QR स्कॅन करताना जो वापरला तोच) सद्य ६-अंकी TOTP आपोआप तयार
होतो — GitHub Actions सारख्या पूर्णपणे स्वयंचलित (headless) cron मधूनही चालवता येतो, कारण इथे कुठलाही
मॅन्युअल ब्राउझर-क्लिक लागतच नाही (Upstox/Fyers च्या रोजच्या मॅन्युअल OAuth पायरीविरुद्ध, हा एक खरा
फायदा). --totp-secret दिला नाही, तर --factor2 द्वारे थेट (त्या क्षणीचा) कोड/जन्मतारीख द्यावी लागेल.

⚠️ --password/--totp-secret सारखे गुप्त parameters शेल history/process-list मध्ये उघडे राहू शकतात —
शक्य असल्यास environment variables (SHOONYA_PASSWORD, SHOONYA_TOTP_SECRET) वापरणे जास्त सुरक्षित.
"""
import argparse
import os

from shoonya_api import login


def generate_totp(totp_secret):
    """दिलेल्या Base32 TOTP secret वरून सद्य ६-अंकी कोड — pyotp उपलब्ध असेल तरच (ऐच्छिक dependency)."""
    try:
        import pyotp
    except ImportError:
        return None, "pyotp इंस्टॉल नाही — 'pip install pyotp' करा, किंवा --factor2 ने थेट कोड द्या."
    return pyotp.TOTP(totp_secret).now(), None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--userid", required=True, help="Shoonya User ID")
    parser.add_argument("--password", default=None, help="Shoonya Password (न दिल्यास SHOONYA_PASSWORD env var वरून)")
    parser.add_argument("--vendor-code", required=True, help="Shoonya API सेटअप वेळी मिळालेला Vendor Code")
    parser.add_argument("--api-secret", default=None, help="Shoonya API Secret (न दिल्यास SHOONYA_API_SECRET env var वरून)")
    parser.add_argument("--imei", default="abc1234", help="कुठलंही ठराविक ओळख-मूल्य (डीफॉल्ट पुरेसा आहे)")
    parser.add_argument("--totp-secret", default=None, help="2FA सेटअप वेळचा Base32 TOTP secret (दिल्यास सद्य कोड आपोआप तयार होतो, --factor2 ची गरज नाही)")
    parser.add_argument("--factor2", default=None, help="TOTP secret नसेल तेव्हा — सद्य ६-अंकी कोड, किंवा जन्मतारीख (DD-MM-YYYY)")
    parser.add_argument("--account-id", required=False, default=None, help="Multi-Account साठी (उदा. 'Abhi-Shoonya')")
    parser.add_argument("--save-to-supabase", action="store_true",
                         help="मिळालेला combined token Supabase (upstox_tokens table, account_id सह) मध्ये थेट साठवणे")
    args = parser.parse_args()

    password = args.password or os.environ.get("SHOONYA_PASSWORD")
    api_secret = args.api_secret or os.environ.get("SHOONYA_API_SECRET")
    if not password or not api_secret:
        print("❌ --password/--api-secret द्या, किंवा SHOONYA_PASSWORD/SHOONYA_API_SECRET environment variables सेट करा.")
        raise SystemExit(1)

    if args.totp_secret:
        factor2, totp_error = generate_totp(args.totp_secret)
        if totp_error:
            print(f"❌ {totp_error}")
            raise SystemExit(1)
        print(f"ℹ️ TOTP आपोआप तयार केला: {factor2}")
    elif args.factor2:
        factor2 = args.factor2
    else:
        print("❌ --totp-secret किंवा --factor2 यापैकी एक द्यावाच लागेल.")
        raise SystemExit(1)

    combined_token, error = login(args.userid, password, factor2, args.vendor_code, api_secret, args.imei)

    if error:
        print(f"\n❌ अयशस्वी: {error}")
        raise SystemExit(1)
    elif args.save_to_supabase:
        import cloud_db
        cloud_db.init_cloud_table()
        saved = cloud_db.save_upstox_token(combined_token, account_id=args.account_id)
        account_label = f"account '{args.account_id}'" if args.account_id else "एकमेव (single) खातं"
        if saved:
            print(f"\n✅ नवीन Shoonya token Supabase मध्ये ({account_label}) साठवला.")
        else:
            print(f"\n⚠️ token मिळाला, पण Supabase मध्ये साठवता आला नाही (SUPABASE_DB_URL तपासा). token: {combined_token}")
    else:
        print(f"\n✅ नवीन Shoonya Access Token (combined स्वरूप, userid:susertoken):\n\n{combined_token}\n")
