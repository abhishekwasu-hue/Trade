"""
get_upstox_token_manual.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — established "Notifier Webhook" व्यवस्था Upstox च्याच
बाजूने अविश्वसनीय ठरल्यामुळे (established, Upstox Community वर नोंदवलेली, अनुत्तरित समस्या), याऐवजी
established, प्रमाणित, विश्वासार्ह OAuth v2 login-flow वापरून, रोज सकाळी १ मिनिटात नवीन token
मिळवण्यासाठी — कुठल्याही webhook/server-delivery वर अवलंबून न राहता (browser-आधारित, direct).

🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — VPS (established, आधीच सेटअप केलेला) फक्त token-webhook
साठी न वापरता, खऱ्या (दर-१-मिनिटाच्या) auto-trading साठी वापरायचं ठरलं — त्यासाठी हा token established
Supabase मध्येही थेट साठवता येतो (--save-to-supabase), जेणेकरून established get_effective_upstox_token()
मार्फत, GitHub Actions आणि VPS वरचे cron jobs दोन्ही आपोआप, कुठलाही मॅन्युअल GitHub-Secret बदल न करता,
हाच ताजा token वापरतील.

रोजची पद्धत (established, दर दिवशी ~१ मिनिट):
  १. ही script चालवा -- ती एक Login URL दाखवेल.
  २. तो URL browser मध्ये उघडून, नेहमीप्रमाणे (User ID/पासवर्ड/TOTP सह) लॉगिन करा.
  ३. लॉगिन यशस्वी झाल्यावर, ब्राउझर तुम्हाला redirect_uri कडे घेऊन जाईल -- त्या नवीन URL मधला
     "?code=..." भाग (पूर्ण, लांब मजकूर) कॉपी करून, इथे परत येऊन पेस्ट करा.
  ४. script त्या code चं access_token मध्ये रूपांतर करून दाखवेल -- --save-to-supabase दिलं असेल तर
     आपोआप Supabase मध्ये साठवेल (established get_effective_upstox_token() मार्फत सर्वत्र वापरण्यायोग्य),
     नाहीतर तोच GitHub Secrets मधल्या UPSTOX_TOKEN मध्ये मॅन्युअली पेस्ट करा.

चालवणे:
    python3 get_upstox_token_manual.py --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET> --redirect-uri <REDIRECT_URI> [--save-to-supabase]
"""
import argparse

import requests


def build_login_url(client_id, redirect_uri):
    """established Upstox OAuth v2 login-dialog URL तयार करणे."""
    return f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"


def exchange_code_for_token(client_id, client_secret, redirect_uri, auth_code):
    """established Upstox OAuth v2 token-exchange API — auth_code चं access_token मध्ये रूपांतर."""
    try:
        res = requests.post(
            "https://api.upstox.com/v2/login/authorization/token",
            headers={"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "code": auth_code, "client_id": client_id, "client_secret": client_secret,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if res.status_code == 200:
            return res.json().get("access_token"), None
        return None, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return None, str(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--redirect-uri", required=True, help="तुमच्या Upstox App मध्ये नोंदवलेलाच Redirect URL")
    parser.add_argument("--save-to-supabase", action="store_true",
                         help="मिळालेला token established Supabase (upstox_tokens table) मध्ये थेट साठवणे -- "
                              "जेणेकरून GitHub Actions आणि VPS वरचे cron jobs दोन्ही आपोआप वापरतील (established get_effective_upstox_token())")
    parser.add_argument("--account-id", default=None,
                         help="🎓 'Multi-Broker Multi-Account' -- established broker_accounts मधलं nickname दिलं, तर हा token "
                              "फक्त त्याच account साठी साठवला जातो (established, single-account वापरासाठी न दिला तरी चालतं)")
    args = parser.parse_args()

    login_url = build_login_url(args.client_id, args.redirect_uri)
    print("\n१. हा URL browser मध्ये उघडा आणि लॉगिन करा:\n")
    print(login_url)
    print("\n२. लॉगिन नंतर redirect झालेल्या URL मधला 'code=' नंतरचा संपूर्ण मजकूर इथे पेस्ट करा:\n")
    auth_code = input("Code: ").strip()

    access_token, error = exchange_code_for_token(args.client_id, args.client_secret, args.redirect_uri, auth_code)
    if error:
        print(f"\n❌ अयशस्वी: {error}")
    elif args.save_to_supabase:
        import cloud_db
        cloud_db.init_cloud_table()
        saved = cloud_db.save_upstox_token(access_token, account_id=args.account_id)
        account_label = f"account '{args.account_id}'" if args.account_id else "established, एकमेव (single) खातं"
        if saved:
            print(f"\n✅ नवीन token established Supabase मध्ये ({account_label}) साठवला — GitHub Actions आणि VPS दोन्ही आपोआप वापरतील (कुठलाही मॅन्युअल बदल लागणार नाही).")
        else:
            print(f"\n⚠️ token मिळाला, पण Supabase मध्ये साठवता आला नाही (SUPABASE_DB_URL तपासा). token: {access_token}")
    else:
        print(f"\n✅ नवीन Access Token (हाच GitHub Secrets मधल्या UPSTOX_TOKEN मध्ये पेस्ट करा):\n\n{access_token}\n")
