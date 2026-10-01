"""
monitor_timing.py
------------------------------
🎓 "Huge slippages" (Performance Report: SL threshold -0.07% असताना exit -0.12% वर, ~11 NIFTY पॉइंट पुढे) —
उशीर नेमका कुठे झाला (तपासणीच्या अंतरात की बाजाराच्या उडीत) हे आजपर्यंत साठवलेलंच नव्हतं. हा लहानसा module
प्रत्येक symbol साठी "मागची तपासणी केव्हा झाली आणि तेव्हा स्पॉट किती होता" हे local फाईलमध्ये (प्रोसेस बदलली तरी
टिकेल असं — trade_monitor.py दर मिनिटाला नवी प्रोसेस सुरू करतो) ठेवतो, आणि exit होताना वाचनीय एका-ओळीचा
"Monitor lag" तुकडा देतो (exit_reason_detail च्या शेवटी जोडण्यासाठी). फक्त निरीक्षण -- exit-निर्णयावर कुठलाही परिणाम नाही;
कुठलीही I/O त्रुटी शांतपणे गिळली जाते.
"""
import json
import os
import time

from config import DATA_DIR

_PATH = os.path.join(DATA_DIR, "monitor_timing.json")


def _load():
    try:
        with open(_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record_check(symbol, spot, now_epoch=None):
    """या symbol ची आताची तपासणी नोंदवून, मागची (epoch_वेळ, spot) परत देतो -- नसेल तर None."""
    now_epoch = time.time() if now_epoch is None else now_epoch
    data = _load()
    previous = data.get(symbol)
    data[symbol] = {"t": now_epoch, "spot": spot}
    try:
        tmp = _PATH + ".tmp"
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, _PATH)
    except Exception:
        pass
    if isinstance(previous, dict) and previous.get("t") is not None:
        return previous["t"], previous.get("spot")
    return None


def format_lag_note(previous, now_epoch, current_spot):
    """exit_reason_detail च्या शेवटी जोडायचा तुकडा. previous = record_check() चा निकाल (किंवा None)."""
    if previous is None:
        return " [Monitor lag: previous check not recorded]"
    prev_t, prev_spot = previous
    gap = max(0.0, now_epoch - prev_t)
    if prev_spot is not None and current_spot is not None:
        return (f" [Monitor lag: previous check {gap:.0f}s earlier (spot {prev_spot:.1f} -> {current_spot:.1f}, "
                f"{current_spot - prev_spot:+.1f} pts)]")
    return f" [Monitor lag: previous check {gap:.0f}s earlier]"
