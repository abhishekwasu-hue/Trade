"""
order_safety.py
---------------
🎓 G3 (वापरकर्त्याचा निर्णय, 2026-10-06) — order मार्गासाठी सुरक्षित, डीफॉल्ट-न-बदलणारे helpers:

  1. `market_protection` (Upstox MARKET / SL-M) — setting `order_market_protection_pct` (data/engine_settings.json).
     डीफॉल्ट None ⇒ field पाठवलाच जात नाही (सध्याचं वर्तन; Upstox चा डीफॉल्ट −1 auto protection — VPS वर 2026-09-10 ला LIVE spread entry COMPLETE झाली).
     1–25 दिल्यास entry आणि exit (SL/Target/TSL, manual close, auto-reverse) सर्व MARKET/SL-M orders मध्ये तो % भरतो. इतर कोणतीही किंमत ⇒ दुर्लक्ष (field नाही).
  2. Exit अयशस्वी झाल्यास इशारा (डीफॉल्ट ON — फक्त सूचना, order बदलत नाही): leg-निहाय स्थिती (भरले / नाही), "position अजून उघडी आहे" स्पष्ट,
     partial failure असेल तर पुढच्या प्रयत्नातला धोका स्पष्ट. Spam टाळण्यासाठी पहिल्या अपयशाला आणि नंतर दर `EXIT_ALERT_EVERY` व्या अपयशाला; अखेर बंद झाल्यावर ✅ संदेश.
  3. त्याच cycle मध्ये एक retry — फक्त **पूर्ण** अपयश (एकही leg भरला नाही) असताना, setting `exit_retry_on_fail` (डीफॉल्ट **OFF** — हा order पाठवणारा बदल आहे).
     Partial failure वर retry नाही (आधी भरलेले legs पुन्हा पाठवल्यास उलटी position होऊ शकते).
"""
import time

EXIT_ALERT_EVERY = 5
_FAIL_COUNTS = {}


def _settings():
    try:
        from engine_service import load_settings
        return load_settings()
    except Exception:
        return {}


def market_protection_pct(settings=None):
    """setting -> 1..25 (int) किंवा None (डीफॉल्ट / अवैध ⇒ field पाठवायचा नाही)."""
    s = _settings() if settings is None else settings
    v = s.get("order_market_protection_pct")
    if v is None or isinstance(v, bool):
        return None
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v if 1 <= v <= 25 else None


def apply_market_protection(orders, settings=None):
    """pct नसेल तर **तीच list** परत (अगदी जुनं वर्तन). असेल तर MARKET/SL-M orders च्या प्रतींमध्ये `market_protection`."""
    pct = market_protection_pct(settings)
    if pct is None:
        return orders
    from order_execution import with_market_protection
    return with_market_protection(orders, pct)


def exit_retry_enabled(settings=None):
    s = _settings() if settings is None else settings
    return bool(s.get("exit_retry_on_fail", False))


def exit_alert_enabled(settings=None):
    s = _settings() if settings is None else settings
    return bool(s.get("exit_fail_alert", True))


def leg_breakdown(resp):
    """Upstox `verified_legs` वरून (भरलेले, न भरलेले) instrument_token lists. माहिती नसेल तर (None, None)."""
    legs = (resp or {}).get("verified_legs") if isinstance(resp, dict) else None
    if not legs:
        return None, None
    filled = [lg.get("instrument_token") for lg in legs if str(lg.get("status", "")).lower() == "complete"]
    unfilled = [lg.get("instrument_token") for lg in legs if str(lg.get("status", "")).lower() != "complete"]
    return filled, unfilled


def is_full_failure(resp):
    """एकही leg भरला नाही याची खात्री असेल तरच True (verified_legs नसतील तर status != success हेच पूर्ण अपयश मानतो — order गेलाच नाही)."""
    filled, _ = leg_breakdown(resp)
    if filled is None:
        return True
    return len(filled) == 0


def record_failure(trade_id):
    _FAIL_COUNTS[trade_id] = _FAIL_COUNTS.get(trade_id, 0) + 1
    return _FAIL_COUNTS[trade_id]


def record_success(trade_id):
    """आधी किती वेळा अपयश आलं होतं ते परत देतो (0 = नव्हतं) आणि मोजणी साफ करतो."""
    return _FAIL_COUNTS.pop(trade_id, 0)


def should_alert(count):
    return count == 1 or (count > 1 and count % EXIT_ALERT_EVERY == 0)


def failure_message(symbol, trade_id, exit_reason, count, status_code, resp):
    filled, unfilled = leg_breakdown(resp)
    lines = [f"🔴 <b>{symbol} — EXIT ORDER अयशस्वी (प्रयत्न #{count})</b>",
             f"Trade {trade_id} · कारण: {exit_reason} · broker status: {status_code}",
             "⚠️ <b>POSITION अजून उघडी आहे.</b> पुढच्या monitor cycle ला पुन्हा प्रयत्न होईल."]
    if filled:
        lines.append(f"भरलेले legs: {', '.join(map(str, filled))}")
        lines.append(f"न भरलेले legs: {', '.join(map(str, unfilled or []))}")
        lines.append("🚨 <b>PARTIAL EXIT</b> — पुढच्या प्रयत्नात सर्व legs पुन्हा पाठवले जातात; आधीच बंद झालेल्या leg वर उलटी position उघडू शकते. "
                     "Upstox app मध्ये लगेच positions तपासा आणि गरज असल्यास हाताने बंद करा.")
    else:
        lines.append("एकही leg भरलेला दिसत नाही (किंवा broker कडून leg-माहिती नाही).")
    msg = (resp or {}).get("errors") or (resp or {}).get("message") or (resp or {}).get("reason") if isinstance(resp, dict) else resp
    if msg:
        lines.append(f"broker संदेश: {str(msg)[:300]}")
    lines.append("कृपया Dashboard / Upstox app मध्ये प्रत्यक्ष स्थिती तपासा.")
    return "\n".join(lines)


def recovered_message(symbol, trade_id, exit_reason, prev_failures):
    return f"✅ <b>{symbol} — position अखेर बंद झाली</b>\nTrade {trade_id} ({exit_reason}) — आधी {prev_failures} वेळा exit अयशस्वी झाला होता."


def send_alert(text, sender=None):
    try:
        if sender is None:
            from notifications import send_telegram_message as sender
        sender(text)
    except Exception:
        pass                                        # सूचना पाठवताना चूक झाली तरी exit loop थांबू नये


def retry_full_failure_once(send_fn, status_code, resp, settings=None, delay_sec=2.0, sleep=time.sleep):
    """exit_retry_on_fail ON आणि पूर्ण अपयश ⇒ `delay_sec` नंतर एकदाच `send_fn()` (तेच close orders). रिटर्न (status_code, resp, retried)."""
    if status_code == 200 and isinstance(resp, dict) and resp.get("status") == "success":
        return status_code, resp, False
    if not exit_retry_enabled(settings) or not is_full_failure(resp):
        return status_code, resp, False
    sleep(delay_sec)
    sc, rs = send_fn()
    return sc, rs, True
