"""
broker_factory.py
--------------------
🎓 established Multi-Broker Multi-Account आर्किटेक्चरचा गाभा — established broker_accounts (Supabase)
मधून account_id/broker_type वाचून, योग्य BrokerAdapter इन्स्टन्स तयार करणारं Factory.

established strategy-scripts (SRv2, Dynamic S/R, Trade Monitor इ.) यालाच वापरून, established
get_all_active_adapters() द्वारे सर्व सक्रिय accounts वर replicated पद्धतीने trade execute करतील.
"""
import cloud_db
from upstox_broker_adapter import UpstoxBrokerAdapter
from fyers_broker_adapter import FyersBrokerAdapter


def get_broker_adapter(account_id, broker_type):
    """
    established account_id/broker_type वरून, योग्य token मिळवून, संबंधित BrokerAdapter इन्स्टन्स
    तयार करणे. यशस्वी झाल्यास (adapter, None), अयशस्वी झाल्यास (None, error_message).

    🎓 प्रामाणिक, महत्त्वाची स्थिती -- established FyersBrokerAdapter code-स्तरावर तयार असला तरी,
    त्याच्या Option-Symbol निर्मितीची (विशेषतः NIFTY इंडेक्स-options साठी नेमकं नामकरण) पडताळणी अजून
    प्रत्यक्ष Fyers account सह झालेली नाही -- म्हणून इथे जाणीवपूर्वक सक्रिय केलेला नाही.
    """
    if broker_type == "upstox":
        token = cloud_db.get_effective_upstox_token(None, account_id=account_id)
        if not token:
            return None, f"{account_id}: Upstox token उपलब्ध नाही (Supabase मध्ये साठवलेला नाही)."
        return UpstoxBrokerAdapter(access_token=token, account_id=account_id), None

    if broker_type == "fyers":
        return None, f"{account_id}: Fyers integration अजून पूर्ण झालेला नाही (Option-Symbol पडताळणी बाकी आहे)."

    return None, f"{account_id}: अज्ञात broker_type '{broker_type}'."


def get_all_active_adapters():
    """
    established सर्व सक्रिय (is_active=True) broker_accounts साठी adapters तयार करणे.
    रिटर्न: ([(adapter, lot_multiplier), ...], [error_message, ...]) -- यशस्वी आणि अयशस्वी दोन्ही
    वेगळे परत करणे, जेणेकरून एका account चं अपयश इतरांना अडवत नाही (established, resilient design).
    """
    accounts_df = cloud_db.get_all_broker_accounts()
    if accounts_df is None or accounts_df.empty:
        return [], ["कुठलेही active broker accounts नोंदवलेले नाहीत (established broker_accounts table रिकामी)."]

    adapters = []
    errors = []
    for _, row in accounts_df.iterrows():
        adapter, error = get_broker_adapter(row["account_id"], row["broker_type"])
        if adapter is not None:
            adapters.append((adapter, row["lot_multiplier"]))
        else:
            errors.append(error)
    return adapters, errors
