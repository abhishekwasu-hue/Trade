"""
order_safety.py
---------------
🎓 G3 (वापरकर्त्याचा निर्णय, 2026-10-06) — order मार्गासाठी सुरक्षित, डीफॉल्ट-न-बदलणारे helpers:

  1. `market_protection` (Upstox MARKET / SL-M) — setting `order_market_protection_pct` (data/engine_settings.json).
     डीफॉल्ट None ⇒ field पाठवलाच जात नाही (सध्याचं वर्तन; Upstox चा डीफॉल्ट −1 auto protection — VPS वर 2026-09-10 ला LIVE spread entry COMPLETE झाली).
     1–25 दिल्यास entry आणि exit (SL/Target/TSL, manual close, auto-reverse) सर्व MARKET/SL-M orders मध्ये तो % भरतो. इतर कोणतीही किंमत ⇒ दुर्लक्ष (field नाही).
  2. Exit अयशस्वी झाल्यास इशारा (डीफॉल्ट ON — फक्त सूचना, order बदलत नाही): leg-निहाय स्थिती (भरले / नाही), "position अजून उघडी आहे" स्पष्ट,
     partial failure असेल तर पुढच्या प्रयत्नातला धोका स्पष्ट. Spam टाळण्यासाठी पहिल्या अपयशाला आणि नंतर दर `EXIT_ALERT_EVERY` व्या अपयशाला; अखेर बंद झाल्यावर ✅ संदेश.
  3. त्याच cycle मध्ये एक retry — फक्त **निश्चित** पूर्ण अपयश (सर्व legs rejected/cancelled, किंवा order_ids शिवाय स्पष्ट 4xx) असताना, setting
     `exit_retry_on_fail` (डीफॉल्ट **OFF** — हा order पाठवणारा बदल आहे). Timeout / open / unknown / partial ⇒ retry नाही (दुहेरी exit टाळण्यासाठी).
     Retry आधी trade अजून OPEN आहे का पुन्हा तपासतो, आणि नवीन correlation ids वापरतो.
  4. Partial-exit safety fix (वापरकर्त्याचा निर्णय, 2026-10-06, flag शिवाय): एखादा exit प्रयत्न अयशस्वी झाला की त्या प्रयत्नाची स्थिती
     (`data/exit_state.json`: काय पाठवलं, निश्चित no-fill होता का, कोणते orders अजून pending होते) नोंदवली जाते. त्या trade साठी पुढचा
     **कोणताही** प्रयत्न (पुढचा cycle, same-cycle retry, manual close) `plan_exit_resend` मधून जातो:
       • pending orders अजून terminal नाहीत / तपासता आले नाहीत ⇒ थांबा (unknown state) + इशारा;
       • broker positions मधून प्रत्येक leg ची खरी उघडी qty ⇒ फक्त उरलेले legs, उरलेल्या qty ने;
       • leg positions मध्ये नाही / उलटी बाजू / अपेक्षेपेक्षा जास्त qty / MCX मध्ये अंशतः qty ⇒ broker-mismatch ⇒ थांबा + इशारा;
       • positions मिळाल्या नाहीत (उदा. Fyers/Shoonya adapters ला positions API नाही) ⇒ मागचा प्रयत्न निश्चित no-fill असेल तरच
         **तेच** orders पुन्हा, नाहीतर थांबा + इशारा.
     पहिला प्रयत्न (आधी कुठलंही अपयश नाही) आणि PAPER — जुनंच वर्तन (सर्व legs).
"""
import html
import json
import os
import time
import uuid

EXIT_ALERT_EVERY = 5
# 🎓 review: trade_monitor/engine_service दर मिनिटाला नवी process ⇒ मोजणी फाईलमध्ये (process-पार टिकावी). फाईल वाचता/लिहिता आली नाही तर
# in-memory dict (इशारा तरीही जातो — फक्त throttle/recovery कमी अचूक).
FAIL_COUNTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "exit_fail_counts.json")
_FAIL_COUNTS = {}
TERMINAL_NOFILL = ("rejected", "cancelled")
TERMINAL_ALL = ("complete", "rejected", "cancelled")
EXIT_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "exit_state.json")
_EXIT_STATE = {}


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


def is_full_failure(resp, status_code=None):
    """**निश्चित** पूर्ण अपयश असेल तरच True (review BLOCKER): (1) प्रत्येक verified leg rejected/cancelled (open/unknown नाही — poll timeout
    म्हणजे order अजून pending असू शकतो), किंवा (2) leg-माहिती नाही, broker चा स्पष्ट 4xx, आणि order_ids नाहीत. बाकी सर्व (timeout,
    network error, 5xx, unknown) ⇒ False ⇒ retry नाही (दुहेरी exit / उलटी position टाळण्यासाठी)."""
    legs = (resp or {}).get("verified_legs") if isinstance(resp, dict) else None
    if legs:
        def _nofill(lg):
            try:
                fq = float(lg.get("filled_quantity") or 0)
            except (TypeError, ValueError):
                return False                                   # अनिश्चित ⇒ भरलेला असू शकतो
            return str(lg.get("status", "")).lower() in TERMINAL_NOFILL and fq == 0   # cancelled पण अंशतः भरलेला ⇒ नाही
        return all(_nofill(lg) for lg in legs)
    if not isinstance(resp, dict) or not isinstance(status_code, int) or not 400 <= status_code < 500:
        return False
    if resp.get("partial_order_ids"):
        return False
    data = resp.get("data")
    has_ids = bool(data.get("order_ids")) if isinstance(data, dict) else bool(data)
    return not has_ids


def _load_counts():
    try:
        with open(FAIL_COUNTS_PATH) as f:
            data = json.load(f)
        return {str(k): int(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return dict(_FAIL_COUNTS)


def _save_counts(counts):
    _FAIL_COUNTS.clear()
    _FAIL_COUNTS.update(counts)
    try:
        os.makedirs(os.path.dirname(FAIL_COUNTS_PATH), exist_ok=True)
        tmp = f"{FAIL_COUNTS_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(counts, f)
        os.replace(tmp, FAIL_COUNTS_PATH)
    except OSError:
        pass


def blocked_key(trade_id):
    """"थांबवलं (unknown state)" इशाऱ्यांची वेगळी मोजणी — पहिल्याच blocked प्रसंगाला इशारा जावा (exit-अपयश मोजणीपासून स्वतंत्र)."""
    return f"{trade_id}#blocked"


def record_failure(trade_id):
    counts = _load_counts()
    key = str(trade_id)
    counts[key] = counts.get(key, 0) + 1
    _save_counts(counts)
    return counts[key]


def record_success(trade_id):
    """आधी किती वेळा अपयश आलं होतं ते परत देतो (0 = नव्हतं) आणि मोजणी + exit-state साफ करतो."""
    counts = _load_counts()
    prev = counts.pop(str(trade_id), 0)
    blocked = counts.pop(blocked_key(trade_id), 0)
    if prev or blocked:
        _save_counts(counts)
    clear_exit_state(trade_id)
    return prev


# ---------------------------------------------------------------------------------------------------------------------
# Partial-exit safety: exit-state + resend plan
# ---------------------------------------------------------------------------------------------------------------------
def _load_json(path, fallback):
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return dict(fallback)


def _save_json(path, data, mirror):
    mirror.clear()
    mirror.update(data)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        pass


def _order_ids(resp):
    if not isinstance(resp, dict):
        return []
    data = resp.get("data")
    if isinstance(data, dict):
        return [str(x) for x in (data.get("order_ids") or []) if x]
    if isinstance(data, list):
        return [str(x.get("order_id")) for x in data if isinstance(x, dict) and x.get("order_id")]
    return []


def pending_order_ids(resp):
    """अजून terminal नसलेले (किंवा स्थिती माहीत नसलेले) order ids. verified_legs असतील तर त्यांतले non-terminal; नसतील तर प्रतिसादातले
    सर्व order ids (broker ने order घेतला पण fill माहीत नाही ⇒ pending मानतो)."""
    legs = (resp or {}).get("verified_legs") if isinstance(resp, dict) else None
    if legs:
        return [str(lg.get("order_id")) for lg in legs if lg.get("order_id") and str(lg.get("status", "")).lower() not in TERMINAL_ALL]
    return _order_ids(resp)


def _slim(o):
    return {k: o.get(k) for k in ("instrument_token", "transaction_type", "quantity", "broker_quantity", "product") if k in o}


def save_exit_state(trade_id, sent_orders, status_code, resp):
    """अयशस्वी exit प्रयत्नाची स्थिती (पुढच्या प्रयत्नासाठी). blocked (काहीच पाठवलं नाही) असेल तर आधीची स्थिती तशीच ठेवतो."""
    st = _load_json(EXIT_STATE_PATH, _EXIT_STATE)
    st[str(trade_id)] = {"last_sent": [_slim(o) for o in (sent_orders or [])], "nofill": bool(is_full_failure(resp, status_code)),
                         "pending_ids": pending_order_ids(resp), "at": time.time()}
    _save_json(EXIT_STATE_PATH, st, _EXIT_STATE)


def load_exit_state(trade_id):
    return _load_json(EXIT_STATE_PATH, _EXIT_STATE).get(str(trade_id))


def clear_exit_state(trade_id):
    st = _load_json(EXIT_STATE_PATH, _EXIT_STATE)
    if st.pop(str(trade_id), None) is not None:
        _save_json(EXIT_STATE_PATH, st, _EXIT_STATE)


def _net_qty(positions, token, product):
    """positions मधली त्या instrument (आणि product जुळत असल्यास) ची net qty बेरीज. एकही entry नाही ⇒ None (गहाळ ≠ flat)."""
    hits = [p for p in positions if p.get("instrument_token") == token and (not product or not p.get("product") or p.get("product") == product)]
    if not hits:
        return None
    try:
        return sum(int(round(float(p.get("quantity") or 0))) for p in hits)
    except (TypeError, ValueError):
        return None


def plan_exit_resend(close_orders, positions, prior, order_status=None):
    """पुढच्या exit प्रयत्नात काय पाठवायचं. रिटर्न (orders, None) किंवा (None, कारण) — कारण असेल तर काहीही पाठवू नका (unknown state).
    orders रिकामी list ⇒ broker कडे सर्व legs आधीच flat (पाठवायचं काही नाही; reconciliation पुढच्या cycle ला बंद करेल).
    prior None (आधी अपयश नाही) ⇒ close_orders जसेच्या तसे (जुनं वर्तन)."""
    if not prior:
        return close_orders, None
    pend = prior.get("pending_ids") or []
    if pend:
        if order_status is None:
            return None, f"मागच्या प्रयत्नाचे orders ({', '.join(pend)}) अजून pending/अज्ञात — त्यांची स्थिती तपासता येत नाही"
        for oid in pend:
            try:
                d = order_status(oid)
            except Exception:
                d = None
            if not isinstance(d, dict) or str(d.get("status", "")).lower() not in TERMINAL_ALL:
                return None, f"मागचा order {oid} अजून terminal नाही (स्थिती: {(d or {}).get('status', 'माहीत नाही')})"
    if positions is None:
        if not prior.get("nofill"):
            return None, "broker positions मिळाल्या नाहीत आणि मागच्या प्रयत्नात काही legs भरले असू शकतात"
        last = {(o.get("instrument_token"), o.get("transaction_type")): o for o in prior.get("last_sent") or []}
        out = []
        for o in close_orders:
            ls = last.get((o.get("instrument_token"), o.get("transaction_type")))
            if ls is not None:
                p = dict(o)
                p["quantity"] = ls.get("quantity", o.get("quantity"))
                if "broker_quantity" in ls:
                    p["broker_quantity"] = ls["broker_quantity"]
                out.append(p)
        return (out, None) if out else (None, "मागचे पाठवलेले legs सध्याच्या trade legs शी जुळत नाहीत")
    out = []
    for o in close_orders:
        tok, side = o.get("instrument_token"), str(o.get("transaction_type", "")).upper()
        net = _net_qty(positions, tok, o.get("product"))
        if net is None:
            return None, f"{tok}: broker positions मध्ये नाही (गहाळ ≠ बंद)"
        if net == 0:
            continue                                                          # हा leg आधीच बंद झाला
        open_side_sign = -1 if side == "BUY" else 1                           # BUY ने बंद ⇒ मूळ position short (net < 0)
        if (net > 0) != (open_side_sign > 0):
            return None, f"{tok}: broker net qty {net} उलट्या बाजूची (अपेक्षित {'short' if open_side_sign < 0 else 'long'})"
        a, q = abs(net), int(o.get("quantity") or 0)
        bq = o.get("broker_quantity")
        p = dict(o)
        if a == q or (bq is not None and a == int(bq)):
            out.append(p)                                                     # leg पूर्ण उघडा
        elif bq is not None:
            return None, f"{tok}: MCX leg अंशतः ({a}) — units/lots अस्पष्ट"
        elif a < q:
            p["quantity"] = a                                                 # leg अंशतः भरला ⇒ फक्त उरलेली qty
            out.append(p)
        else:
            return None, f"{tok}: broker net qty {a} > अपेक्षित {q} (दुसरा trade त्याच instrument वर?)"
    return out, None


def blocked_message(symbol, trade_id, exit_reason, count, reason):
    symbol, trade_id, exit_reason, reason = _e(symbol), _e(trade_id), _e(exit_reason), _e(reason)
    return "\n".join([f"🛑 <b>{symbol} — EXIT थांबवला: स्थिती अनिश्चित (प्रयत्न #{count})</b>",
                      f"Trade {trade_id} · कारण: {exit_reason}",
                      f"का: {reason}",
                      "⚠️ <b>POSITION उघडी असू शकते.</b> दुहेरी/उलटी position टाळण्यासाठी bot ने order पाठवला नाही.",
                      "Upstox app मध्ये positions आणि orders लगेच तपासा; गरज असल्यास हाताने बंद करा. स्थिती स्पष्ट झाल्यावर पुढचा cycle पुन्हा तपासेल."])


def should_alert(count):
    return count == 1 or (count > 1 and count % EXIT_ALERT_EVERY == 0)


def _e(x):
    return html.escape(str(x), quote=False)


def failure_message(symbol, trade_id, exit_reason, count, status_code, resp):
    """Telegram (parse_mode=HTML) साठी — broker मजकूर / symbol / tokens escape केलेले."""
    symbol, trade_id, exit_reason, status_code = _e(symbol), _e(trade_id), _e(exit_reason), _e(status_code)
    filled, unfilled = leg_breakdown(resp)
    filled = None if filled is None else [_e(x) for x in filled]
    unfilled = None if unfilled is None else [_e(x) for x in unfilled]
    lines = [f"🔴 <b>{symbol} — EXIT ORDER अयशस्वी (प्रयत्न #{count})</b>",
             f"Trade {trade_id} · कारण: {exit_reason} · broker status: {status_code}",
             "⚠️ <b>POSITION अजून उघडी आहे.</b> पुढच्या monitor cycle ला पुन्हा प्रयत्न होईल."]
    if filled:
        lines.append(f"भरलेले legs: {', '.join(map(str, filled))}")
        lines.append(f"न भरलेले legs: {', '.join(map(str, unfilled or []))}")
        lines.append("🚨 <b>PARTIAL EXIT</b> — पुढच्या प्रयत्नाआधी broker positions तपासून फक्त उरलेले legs पाठवले जातील; स्थिती अनिश्चित असेल "
                     "तर bot थांबेल आणि इशारा देईल. Upstox app मध्ये positions तपासा.")
    else:
        lines.append("एकही leg भरलेला दिसत नाही (किंवा broker कडून leg-माहिती नाही).")
    msg = (resp or {}).get("errors") or (resp or {}).get("message") or (resp or {}).get("reason") if isinstance(resp, dict) else resp
    if msg:
        lines.append(f"broker संदेश: {_e(str(msg)[:300])}")
    lines.append("कृपया Dashboard / Upstox app मध्ये प्रत्यक्ष स्थिती तपासा.")
    return "\n".join(lines)


def recovered_message(symbol, trade_id, exit_reason, prev_failures):
    symbol, trade_id, exit_reason = _e(symbol), _e(trade_id), _e(exit_reason)
    return f"✅ <b>{symbol} — position अखेर बंद झाली</b>\nTrade {trade_id} ({exit_reason}) — आधी {prev_failures} वेळा exit अयशस्वी झाला होता."


def send_alert(text, sender=None):
    try:
        if sender is None:
            from notifications import send_telegram_message as sender
        sender(text)
    except Exception:
        pass                                        # सूचना पाठवताना चूक झाली तरी exit loop थांबू नये


def with_fresh_correlation_ids(orders):
    """retry साठी orders च्या प्रती — नवीन correlation_id (Upstox duplicate नाकारू नये; fill-verification correlation_id ने जुळवतं)."""
    return [{**o, "correlation_id": uuid.uuid4().hex[:20]} if "correlation_id" in o else dict(o) for o in orders]


def retry_full_failure_once(send_fn, status_code, resp, settings=None, delay_sec=2.0, sleep=time.sleep, still_open=None):
    """exit_retry_on_fail ON आणि **निश्चित** पूर्ण अपयश ⇒ `delay_sec` नंतर, trade अजून OPEN असेल (`still_open()`) तरच, एकदा `send_fn(fresh=True)`
    (नवीन correlation ids). रिटर्न (status_code, resp, retried)."""
    if status_code == 200 and isinstance(resp, dict) and resp.get("status") == "success":
        return status_code, resp, False
    if not exit_retry_enabled(settings) or not is_full_failure(resp, status_code):
        return status_code, resp, False
    sleep(delay_sec)
    if still_open is not None and not still_open():
        return status_code, resp, False
    sc, rs = send_fn(fresh=True)
    return sc, rs, True
