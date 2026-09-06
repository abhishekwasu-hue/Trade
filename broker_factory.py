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

    🎓 वापरकर्त्याने प्रत्यक्ष, खऱ्या Fyers account सह LTP + Option Chain (४१ strikes, बरोबर
    स्वरूपात) पडताळल्यानंतर सक्रिय केलेलं. ⚠️ प्रामाणिक टीप — फक्त data-fetch (LTP/Option Chain)
    पडताळलेलं आहे, established प्रत्यक्ष order-placement (LIVE mode) अजून पडताळलेलं नाही — established
    सर्व रणनींती डीफॉल्टने PAPER mode वापरतात (established, फक्त LTP वरूनच सिम्युलेटेड fill, खरा
    order-placement API कॉल करत नाही), त्यामुळे established PAPER साठी हे सुरक्षित आहे.
    """
    if broker_type == "upstox":
        token = cloud_db.get_effective_upstox_token(None, account_id=account_id)
        if not token:
            return None, f"{account_id}: Upstox token उपलब्ध नाही (Supabase मध्ये साठवलेला नाही)."
        return UpstoxBrokerAdapter(access_token=token, account_id=account_id), None

    if broker_type == "fyers":
        token = cloud_db.get_effective_upstox_token(None, account_id=account_id)
        if not token:
            return None, f"{account_id}: Fyers token उपलब्ध नाही (Supabase मध्ये साठवलेला नाही)."
        return FyersBrokerAdapter(access_token=token, account_id=account_id), None

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
