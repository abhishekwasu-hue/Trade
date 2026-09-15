"""
get_stocko_token_manual.py
--------------------------------
get_upstox_token_manual.py/get_fyers_token_manual.py च्याच OAuth2 पॅटर्नने बांधलेला, Stocko साठीचा
token-मिळवण्याचा script — वापरकर्त्याने दिलेल्या अधिकृत Stocko API PDF वरून.

रोजची पद्धत:
  १. ही script चालवा — ती एक Login URL दाखवेल.
  २. तो URL ब्राउझरमध्ये उघडून, नेहमीप्रमाणे (Login ID/पासवर्ड/2FA सह) लॉगिन करा.
  ३. लॉगिन यशस्वी झाल्यावर, Redirect URL कडे redirect होईल — त्या URL मधला "?code=..." भाग
     (पहिल्या "&" पर्यंतच) कॉपी करून, इथे परत येऊन पेस्ट करा.
  ४. script combined token ("api_client_id:access_token") तयार करून, --save-to-supabase दिलं
     असेल तर account_id सह Supabase मध्ये आपोआप साठवेल.

⚠️ यासाठी STOCKO_BASE_URL environment variable आधी सेट करावा लागेल (PDF मध्ये फक्त <base_url>
placeholder आहे — प्रत्यक्ष मूल्य SAS Online/Stocko कडून मिळतं):
    export STOCKO_BASE_URL="https://xxxxx"

चालवणे:
    python3 get_stocko_token_manual.py --oauth-client-id <oauthID> --oauth-client-secret <SECRET> \\
        --redirect-uri <REDIRECT_URI> --api-client-id <तुमचा Login ID, उदा. XYZ> \\
        --account-id <नाव> --save-to-supabase
"""
import argparse

from stocko_api import build_login_url, exchange_auth_code_for_token


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--oauth-client-id", required=True, help="Stocko Developer Console मधला OAuth2 Client ID")
    parser.add_argument("--oauth-client-secret", required=True, help="Stocko Developer Console मधला OAuth2 Client Secret")
    parser.add_argument("--redirect-uri", required=True, help="तुमच्या Stocko App मध्ये नोंदवलेलाच Redirect URL (डीफॉल्ट: http://127.0.0.1)")
    parser.add_argument("--api-client-id", required=True, help="तुमचा Stocko ट्रेडिंग Login ID (PDF च्या उदाहरणांत 'XYZ') — जवळजवळ प्रत्येक API कॉलला लागतो")
    parser.add_argument("--account-id", required=False, default=None, help="Multi-Account साठी (उदा. 'Abhi-Stocko')")
    parser.add_argument("--save-to-supabase", action="store_true",
                         help="मिळालेला combined token Supabase (upstox_tokens table, account_id सह) मध्ये थेट साठवणे")
    args = parser.parse_args()

    login_url = build_login_url(args.oauth_client_id, args.redirect_uri)
    print("\n१. हा URL ब्राउझरमध्ये उघडा आणि लॉगिन करा:\n")
    print(login_url)
    print("\n२. लॉगिन नंतर redirect झालेल्या URL मधला 'code=' नंतरचा (पहिल्या '&' पर्यंतच) मजकूर इथे पेस्ट करा:\n")
    auth_code = input("Code: ").strip()

    combined_token, error = exchange_auth_code_for_token(
        args.oauth_client_id, args.oauth_client_secret, auth_code, args.redirect_uri, args.api_client_id,
    )
    if error:
        print(f"\n❌ अयशस्वी: {error}")
    elif args.save_to_supabase:
        import cloud_db
        cloud_db.init_cloud_table()
        saved = cloud_db.save_upstox_token(combined_token, account_id=args.account_id)
        account_label = f"account '{args.account_id}'" if args.account_id else "एकमेव (single) खातं"
        if saved:
            print(f"\n✅ नवीन Stocko token Supabase मध्ये ({account_label}) साठवला.")
        else:
            print(f"\n⚠️ token मिळाला, पण Supabase मध्ये साठवता आला नाही (SUPABASE_DB_URL तपासा). token: {combined_token}")
    else:
        print(f"\n✅ नवीन Stocko Access Token (combined स्वरूप, api_client_id:access_token):\n\n{combined_token}\n")
