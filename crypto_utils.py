"""crypto_utils.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Plaintext Broker Credentials, महत्त्वाच्या
🟠 यादीतला मुद्दा) — Upstox/Fyers/Shoonya/Stocko या चारही brokers चे session access tokens (सर्व
एकाच `upstox_tokens` टेबलमध्ये, account_id ने वेगळे केलेले — cloud_db.save_upstox_token()/
get_latest_upstox_token()) आतापर्यंत Supabase मध्ये साधा मजकूर (plaintext) म्हणून साठवले जायचे.
हे tokens पूर्ण ट्रेडिंग-अधिकार देतात (खरे पैसे हलवू शकतात) — त्यामुळे password इतकेच संवेदनशील,
पण कुठलंही encryption नव्हतं. Supabase प्रोजेक्ट/DB access मिळालेल्या कुणालाही (चुकीने shared
गेलेली connection string, leaked screenshot, इ.) हे थेट वाचता येत होते.

`TOKEN_ENCRYPTION_KEY` पर्यावरण चल (किंवा data/notification_config.json मधला
"token_encryption_key") दिला असेल, तर हे मॉड्यूल Fernet (symmetric AES + HMAC, `cryptography`
पॅकेज) वापरून प्रत्येक नवीन token साठवण्याआधी encrypt करतं, आणि वाचताना आपोआप, पारदर्शकपणे decrypt
करतं (caller ला — cloud_db.py, बाकी कुठल्याही फाईलला — काहीच बदलावं लागत नाही). की सेट केलेली
नसेल, तर आधीसारखंच (plaintext) वर्तन — जुन्या वापरकर्त्यांचं काहीही तुटत नाही, कुणालाही सक्तीने
key सेटअप करावी लागत नाही, फक्त जोरदार शिफारस.

नवीन key तयार करण्यासाठी (एकदाच, टर्मिनलवर):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
मिळालेली string TOKEN_ENCRYPTION_KEY म्हणून environment मध्ये (किंवा Streamlit Cloud Secrets
मध्ये) ठेवा — हरवली तर आधी encrypt केलेले जुने tokens परत मिळवता येणार नाहीत (पण tokens रोजच
expire होत असल्याने, फक्त पुढचा दिवस नव्याने login करावा लागेल इतकाच परिणाम).
"""
import json
import os

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover -- requirements.txt मध्ये pinned, पण defensive fallback
    Fernet = None
    InvalidToken = Exception

from log_setup import get_logger

_logger = get_logger("crypto_utils.py")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "data", "notification_config.json")

_ENC_PREFIX = "enc:v1:"


def _get_fernet():
    """TOKEN_ENCRYPTION_KEY सेट नसेल (किंवा `cryptography` उपलब्ध नसेल), तर None -- caller ने
    plaintext fallback वापरावा."""
    if Fernet is None:
        return None
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not key and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                key = json.load(f).get("token_encryption_key")
        except (json.JSONDecodeError, OSError):
            key = None
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError):
        _logger.error("TOKEN_ENCRYPTION_KEY अवैध आहे (Fernet-सुसंगत नाही) -- encryption बंद, plaintext वापरलं जाईल")
        return None


def encrypt_token(plaintext):
    """की सेट असेल तर encrypt करून (उपसर्गासकट) परत, नसेल तर तसंच (plaintext) परत -- backward-compatible."""
    if plaintext is None:
        return plaintext
    fernet = _get_fernet()
    if fernet is None:
        return plaintext
    return _ENC_PREFIX + fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(stored):
    """उपसर्ग असेल तरच प्रत्यक्ष decrypt होतो (जुने plaintext rows, किंवा encryption कधीच सक्रिय न
    केलेले rows, जसेच्या तसे परत). की उपलब्ध नसेल/चुकीची असेल, किंवा data corrupted असेल, तर None
    (caller — get_latest_upstox_token() — आधीपासूनच None ला "token उपलब्ध नाही" मानतो, त्यामुळे
    cron सुरक्षितपणे थांबतो, चुकीचा token वापरत नाही)."""
    if stored is None or not stored.startswith(_ENC_PREFIX):
        return stored
    fernet = _get_fernet()
    if fernet is None:
        _logger.error("Encrypted token सापडला, पण TOKEN_ENCRYPTION_KEY उपलब्ध नाही/चुकीची आहे -- decrypt करता आलं नाही")
        return None
    try:
        return fernet.decrypt(stored[len(_ENC_PREFIX):].encode()).decode()
    except InvalidToken:
        _logger.error("Encrypted token decrypt करता आला नाही (चुकीची key किंवा corrupted data)")
        return None
