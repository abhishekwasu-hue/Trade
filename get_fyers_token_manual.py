"""
get_fyers_token_manual.py
------------------------------
🎓 established get_upstox_token_manual.py च्याच established, विश्वासार्ह OAuth-पॅटर्नने बांधलेला,
Fyers साठीचा token-मिळवण्याचा script — established, प्रत्यक्ष Fyers Developer App मध्ये दिसणाऱ्या
"Not Connected" स्थितीचं established, पहिलं (आणि रोजचं) निराकरण.

रोजची पद्धत (established, दर दिवशी ~१ मिनिट):
  १. ही script चालवा -- ती एक Login URL दाखवेल.
  २. तो URL browser मध्ये उघडून, नेहमीप्रमाणे (User ID/पासवर्ड/TOTP सह) लॉगिन करा.
  ३. लॉगिन यशस्वी झाल्यावर, established Redirect URL कडे redirect होईल -- established URL मधला
     "?auth_code=..." भाग (established, पहिल्या "&" पर्यंतच) कॉपी करून, इथे परत येऊन पेस्ट करा.
  ४. script established combined token ("app_id:access_token") तयार करून, established
     --save-to-supabase दिलं असेल तर established account_id सह Supabase मध्ये आपोआप साठवेल.

चालवणे:
    python3 get_fyers_token_manual.py --app-id <APP_ID> --app-secret <APP_SECRET> --redirect-uri <REDIRECT_URI> --account-id <नाव> --save-to-supabase
"""
import argparse

from fyers_api import exchange_auth_code_for_token


def build_login_url(app_id, redirect_uri, state="sample_state"):
    """established Fyers OAuth v3 login-dialog URL तयार करणे."""
    return (
        f"https://api-t1.fyers.in/api/v3/generate-authcode?"
        f"client_id={app_id}&redirect_uri={redirect_uri}&response_type=code&state={state}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", required=True, help="established Fyers Developer Console मधला App ID")
    parser.add_argument("--app-secret", required=True, help="established Fyers Developer Console मधला App Secret")
    parser.add_argument("--redirect-uri", required=True, help="established तुमच्या Fyers App मध्ये नोंदवलेलाच Redirect URL")
    parser.add_argument("--account-id", required=False, default=None, help="established Multi-Account साठी (उदा. 'Abhi-Fyers')")
    parser.add_argument("--save-to-supabase", action="store_true",
                         help="established मिळालेला combined token Supabase (upstox_tokens table, account_id सह) मध्ये थेट साठवणे")
    args = parser.parse_args()

    login_url = build_login_url(args.app_id, args.redirect_uri)
    print("\n१. हा URL browser मध्ये उघडा आणि लॉगिन करा:\n")
    print(login_url)
    print("\n२. लॉगिन नंतर redirect झालेल्या URL मधला 'auth_code=' नंतरचा (पहिल्या '&' पर्यंतच) मजकूर इथे पेस्ट करा:\n")
    auth_code = input("Auth Code: ").strip()

    combined_token, error = exchange_auth_code_for_token(args.app_id, args.app_secret, auth_code)
    if error:
        print(f"\n❌ अयशस्वी: {error}")
    elif args.save_to_supabase:
        import cloud_db
        cloud_db.init_cloud_table()
        saved = cloud_db.save_upstox_token(combined_token, account_id=args.account_id)
        account_label = f"account '{args.account_id}'" if args.account_id else "established, एकमेव (single) खातं"
        if saved:
            print(f"\n✅ नवीन Fyers token established Supabase मध्ये ({account_label}) साठवला.")
        else:
            print(f"\n⚠️ token मिळाला, पण Supabase मध्ये साठवता आला नाही (SUPABASE_DB_URL तपासा). token: {combined_token}")
    else:
        print(f"\n✅ नवीन Fyers Access Token (combined स्वरूप, established app_id:token):\n\n{combined_token}\n")
