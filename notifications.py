"""
notifications.py
--------------------
Unattended scripts (credit_spread_auto_trader.py, oi_signal_auto_trader.py) साठी सुरक्षितता/देखरेख —
Telegram सूचना (Entry/Exit/Error) + Heartbeat फाईल (script खरंच धावतेय की थांबली आहे हे बाहेरून तपासता यावं).

⚙️ Setup (एकदाच):
  १. Telegram वर @BotFather शी बोलून नवीन बॉट तयार करा — 'TELEGRAM_BOT_TOKEN' मिळेल.
  २. आपल्या बॉटला एक मेसेज पाठवा, मग https://api.telegram.org/bot<TOKEN>/getUpdates उघडून
     'chat':{'id': ...} मधला आकडा — हाच 'TELEGRAM_CHAT_ID'.
  ३. दोन्ही data/notification_config.json मध्ये साठवा (खाली उदाहरण), किंवा पर्यावरण चलांमध्ये
     (environment variables) TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID म्हणून ठेवा.

Token/Chat ID सेट केलेले नसतील तर — सूचना फक्त local log मध्येच जातात (script थांबत नाही, तुटत नाही).
"""
import datetime
import json
import os

import requests

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "data", "notification_config.json")
HEARTBEAT_DIR = os.path.join(_BASE_DIR, "data", "heartbeats")
LOG_PATH = os.path.join(_BASE_DIR, "data", "notifications_log.txt")


def _load_telegram_credentials():
    """पर्यावरण चलं आधी तपासणे, नंतर config फाईल — दोन्हीपैकी काहीच नसेल तर (None, None)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return token, chat_id
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            return cfg.get("telegram_bot_token"), cfg.get("telegram_chat_id")
        except (json.JSONDecodeError, OSError):
            pass
    return None, None


def send_telegram_message(message, timeout=10):
    """
    Telegram वर संदेश पाठवणे. Credentials नसतील, किंवा पाठवताना काहीही चूक झाली, तर script
    थांबता कामा नये — म्हणून सर्व अपयश शांतपणे local log मध्ये नोंदवले जातात, कधीही raise होत नाही.
    रिटर्न: True (यशस्वी) / False (अयशस्वी किंवा credentials नाहीत).
    """
    token, chat_id = _load_telegram_credentials()
    _log_locally(message)
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=timeout,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _log_locally(message):
    """Telegram पाठवता आलं की नाही, याची पर्वा न करता — प्रत्येक सूचना स्थानिक फाईलमध्येही नोंदवली जाते."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(f"[{ts}] {message}\n")


def notify_entry(script_name, symbol, strategy, direction, strikes_summary, net_credit, trade_id):
    message = (
        f"🟢 <b>नवीन Entry — {script_name}</b>\n"
        f"{symbol} | {strategy} | {direction}\n"
        f"Strikes: {strikes_summary}\n"
        f"Net Credit: {net_credit} | Trade ID: {trade_id}"
    )
    return send_telegram_message(message)


def notify_exit(script_name, symbol, trade_id, reason, pnl=None):
    pnl_str = f"\nP&L: ₹{pnl:,.0f}" if pnl is not None else ""
    message = f"🔴 <b>Position बंद — {script_name}</b>\n{symbol} | Trade ID: {trade_id}\nकारण: {reason}{pnl_str}"
    return send_telegram_message(message)


def notify_error(script_name, error_detail):
    message = f"⚠️ <b>Error — {script_name}</b>\n{error_detail}"
    return send_telegram_message(message)


def ping_healthcheck(script_name, timeout=8):
    """
    🎓 Production-readiness सुधारणा — established `write_heartbeat()` फक्त *local* फाईलमध्ये नोंद
    करतं, जी फक्त त्याच होस्टवरून (उदा. established VPS) वाचता येते — established होस्टच स्वतः बंद
    पडला (वीज/नेट/क्रॅश), तर ते local फाईल कुणालाच दिसत नाही आणि कुणालाच कळत नाही. हे function
    त्याला पूरक — बाहेरच्या (external) uptime-monitoring सेवेला (उदा. healthchecks.io / UptimeRobot
    चा मोफत "push monitor" टियर — दोन्ही एक साधा GET URL देतात) एक "मी जिवंत आहे" ping पाठवतं.

    Setup (ऐच्छिक — नसेल तर हे function गप्प काहीच करत नाही, script वर परिणाम नाही):
      environment variable `HEALTHCHECK_PING_URL_<SCRIPT_NAME_UPPER>` (script-specific) असेल तर तो
      वापरला जातो, नाहीतर सर्वांसाठी समान `HEALTHCHECK_PING_URL`. उदा.:
        HEALTHCHECK_PING_URL_ENGINE_SERVICE=https://hc-ping.com/xxxx-xxxx-...
    """
    specific_key = f"HEALTHCHECK_PING_URL_{script_name.upper()}"
    url = os.environ.get(specific_key) or os.environ.get("HEALTHCHECK_PING_URL")
    if not url:
        return False
    try:
        requests.get(url, timeout=timeout)
        return True
    except Exception:
        return False  # बाह्य monitoring सेवा तात्पुरती अनुपलब्ध असली तरी script थांबता कामा नये


def write_heartbeat(script_name):
    """
    प्रत्येक cycle च्या शेवटी बोलावायचं — 'script शेवटची कधी यशस्वीरित्या धावली' याची नोंद, बाहेरून
    (उदा. दुसरी monitoring script, किंवा तुम्ही स्वतः) तपासता यावी म्हणून. सोबतच (configured असल्यास)
    बाह्य uptime-monitor लाही ping — जेणेकरून होस्टच बंद पडला तरी कळेल (local heartbeat फाईल तेव्हा
    उपयोगाची नसते).
    """
    os.makedirs(HEARTBEAT_DIR, exist_ok=True)
    path = os.path.join(HEARTBEAT_DIR, f"{script_name}.txt")
    with open(path, "w") as f:
        f.write(datetime.datetime.now().isoformat())
    ping_healthcheck(script_name)


def check_heartbeat_stale(script_name, max_age_minutes=30):
    """
    दिलेल्या script चा heartbeat किती जुना आहे ते तपासणे — max_age_minutes पेक्षा जुना (किंवा कधीच
    धावलीच नाही) असेल तर True (धोक्याचा इशारा — script अडकली/थांबली असू शकते).
    """
    path = os.path.join(HEARTBEAT_DIR, f"{script_name}.txt")
    if not os.path.exists(path):
        return True
    try:
        with open(path) as f:
            last_run = datetime.datetime.fromisoformat(f.read().strip())
    except (ValueError, OSError):
        return True
    age_minutes = (datetime.datetime.now() - last_run).total_seconds() / 60
    return age_minutes > max_age_minutes
