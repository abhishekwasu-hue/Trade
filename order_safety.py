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
     Review नंतर: (a) पाठवण्याआधीच "in-flight" नोंद (process मध्येच थांबली तरी पुढचा प्रयत्न अंधपणे सर्व legs पाठवत नाही); (b) प्रतिसादातून
     fill माहीत नसेल (timeout / order_ids नाहीत / in-flight) तर Upstox order book मध्ये त्या legs चे orders अजून live आहेत का; (c) दुसरा OPEN
     LIVE trade त्याच instrument वर ⇒ net qty संदिग्ध ⇒ थांबा; (d) state फाईल fcntl lock खाली, आणि प्रत्येक trade साठी exit-lock (monitor
     आणि manual close एकाच वेळी पाठवू नयेत); (e) मागच्या प्रयत्नाचा दिवस वेगळा ⇒ DAY orders संपलेले ⇒ pending/book तपासणी नाही;
     (f) आधीच्या प्रयत्नातले fills साठवून शेवटी realized P&L त्यावरून. अडकलेल्या trade साठी: `python3 clear_exit_state.py --trade-id …`.
"""
import calendar
import contextlib
import datetime
import html
import json
import os
import time
import uuid

try:
    import fcntl
except ImportError:                                                  # Windows (dev) — lock नाही, बाकी वर्तन तेच
    fcntl = None

EXIT_ALERT_EVERY = 5
# 🎓 review: trade_monitor/engine_service दर मिनिटाला नवी process ⇒ मोजणी फाईलमध्ये (process-पार टिकावी). फाईल वाचता/लिहिता आली नाही तर
# in-memory dict (इशारा तरीही जातो — फक्त throttle/recovery कमी अचूक).
FAIL_COUNTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "exit_fail_counts.json")
_FAIL_COUNTS = {}
TERMINAL_NOFILL = ("rejected", "cancelled")
TERMINAL_ALL = ("complete", "rejected", "cancelled")
EXIT_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "exit_state.json")
EXIT_LOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "exit_locks")
_EXIT_STATE = {}
BOOK_WINDOW_SEC = 180                                                  # order book मध्ये मागच्या प्रयत्नाचे orders शोधताना वेळेची सहनशीलता


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
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError):
        return dict(fallback)


class StateUnreadable(Exception):
    """exit_state.json आहे पण वाचता येत नाही — fail-closed (review): सर्व resend थांबवा, फाईल हाताने तपासा."""


def _load_state_strict():
    try:
        with open(EXIT_STATE_PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as e:
        raise StateUnreadable(f"{EXIT_STATE_PATH} वाचता येत नाही ({type(e).__name__}) — फाईल तपासा/हटवा") from e
    if not isinstance(data, dict):
        raise StateUnreadable(f"{EXIT_STATE_PATH} चं स्वरूप अनपेक्षित — फाईल तपासा/हटवा")
    return data


def _save_state_strict(data):
    """mark_inflight साठी: लिहिता आलं नाही तर OSError (caller ने order पाठवू नये)."""
    _EXIT_STATE.clear()
    _EXIT_STATE.update(data)
    os.makedirs(os.path.dirname(EXIT_STATE_PATH), exist_ok=True)
    tmp = f"{EXIT_STATE_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, EXIT_STATE_PATH)


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


@contextlib.contextmanager
def _state_lock():
    """exit_state.json चं load-modify-save एका वेळी एकाच process ने (monitor / Streamlit pages वेगळ्या processes)."""
    fh = None
    try:
        if fcntl is not None:
            os.makedirs(os.path.dirname(EXIT_STATE_PATH), exist_ok=True)
            fh = open(EXIT_STATE_PATH + ".lock", "a")
            fcntl.flock(fh, fcntl.LOCK_EX)
    except OSError:
        if fh is not None:
            fh.close()
        fh = None
    try:
        yield
    finally:
        if fh is not None:
            try:
                fcntl.flock(fh, fcntl.LOCK_UN)
            finally:
                fh.close()


@contextlib.contextmanager
def exit_lock(trade_id):
    """एका trade साठी exit पाठवण्याचा lock (non-blocking). दुसरी process आत्ता त्याच trade चा exit पाठवत असेल ⇒ False (या वेळी काही करू नका)."""
    if fcntl is None:
        yield True
        return
    fh = None
    try:
        os.makedirs(EXIT_LOCK_DIR, exist_ok=True)
        fh = open(os.path.join(EXIT_LOCK_DIR, "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(trade_id)) + ".lock"), "a")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if fh is not None:
            fh.close()
        yield False
        return
    except OSError:
        if fh is not None:
            fh.close()
        fh = None                                                      # lock फाईल बनवता आली नाही ⇒ lock शिवाय (जुनं वर्तन)
    try:
        yield True
    finally:
        if fh is not None:
            try:
                fcntl.flock(fh, fcntl.LOCK_UN)
            finally:
                fh.close()


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
    return {k: o.get(k) for k in ("instrument_token", "transaction_type", "quantity", "broker_quantity", "product", "tag", "correlation_id") if k in o}


def _ist_date(epoch):
    return (datetime.datetime.utcfromtimestamp(float(epoch)) + datetime.timedelta(hours=5, minutes=30)).date()


def _accumulate_fills(fills, resp):
    """verified_legs मधले प्रत्यक्ष भरलेले (qty, avg) — आधीच्यांत जोडून (weighted)."""
    fills = {k: list(v) for k, v in (fills or {}).items()}
    for lg in ((resp or {}).get("verified_legs") or []) if isinstance(resp, dict) else []:
        try:
            q, avg = float(lg.get("filled_quantity") or 0), float(lg.get("average_price") or 0)
        except (TypeError, ValueError):
            continue
        tok = lg.get("instrument_token")
        if tok and q > 0 and avg > 0:
            q0, a0 = fills.get(tok, [0.0, 0.0])
            fills[tok] = [q0 + q, (q0 * a0 + q * avg) / (q0 + q)]
    return fills


def mark_inflight(trade_id, sent_orders):
    """पाठवण्याच्या **आधी** नोंद: process मध्येच थांबली / प्रतिसाद हरवला तरी पुढचा प्रयत्न order book तपासल्याशिवाय पाठवणार नाही.
    आधीचे fills जपले जातात."""
    with _state_lock():
        st = _load_state_strict()                                        # वाचता आली नाही ⇒ StateUnreadable ⇒ caller पाठवत नाही
        prev = st.get(str(trade_id)) if isinstance(st.get(str(trade_id)), dict) else {}
        st[str(trade_id)] = {"last_sent": [_slim(o) for o in (sent_orders or [])], "nofill": False, "pending_ids": [], "inflight": True,
                             "needs_book": True, "at": time.time(), "fills": prev.get("fills") or {}}
        _save_state_strict(st)                                           # लिहिता आली नाही ⇒ OSError ⇒ caller पाठवत नाही


def save_exit_state(trade_id, sent_orders, status_code, resp):
    """अयशस्वी exit प्रयत्नाची स्थिती (पुढच्या प्रयत्नासाठी). needs_book = fill माहिती नाही (verified_legs नाहीत) आणि निश्चित no-fill नाही."""
    with _state_lock():
        st = _load_state_strict()                                        # खराब फाईल ओव्हरराइट करून इतर trades ची नोंद गमावू नये
        prev = st.get(str(trade_id)) if isinstance(st.get(str(trade_id)), dict) else {}
        nofill = bool(is_full_failure(resp, status_code))
        has_legs = bool((resp or {}).get("verified_legs")) if isinstance(resp, dict) else False
        st[str(trade_id)] = {"last_sent": [_slim(o) for o in (sent_orders or [])], "nofill": nofill, "pending_ids": pending_order_ids(resp),
                             "inflight": False, "needs_book": (not nofill) and not has_legs,
                             "at": prev.get("at") if prev.get("inflight") and prev.get("at") else time.time(),   # पाठवण्याची वेळ (book window)
                             "fills": _accumulate_fills(prev.get("fills"), resp)}
        _save_json(EXIT_STATE_PATH, st, _EXIT_STATE)


def load_exit_state(trade_id):
    try:
        v = _load_state_strict().get(str(trade_id))
    except StateUnreadable as e:
        return {"corrupt": True, "why": str(e)}                          # fail-closed: पहिला प्रयत्नही थांबतो
    if v is None:
        return None
    return v if isinstance(v, dict) else {"corrupt": True}            # खराब नोंद ⇒ unknown (plan मध्ये थांबा)


def clear_exit_state(trade_id):
    with _state_lock():
        try:
            st = _load_state_strict()
        except StateUnreadable:
            return                                                       # खराब फाईल तशीच ठेवा (operator तपासेल)
        if st.pop(str(trade_id), None) is not None:
            _save_json(EXIT_STATE_PATH, st, _EXIT_STATE)


def merged_exit_prices(trade_id, current_prices, sent_orders):
    """आधीच्या अयशस्वी प्रयत्नांतले fills + या प्रयत्नाचे भाव ⇒ प्रत्येक instrument चा सरासरी exit भाव (realized P&L साठी)."""
    prior = load_exit_state(trade_id) or {}
    fills = prior.get("fills") or {}
    out = dict(current_prices or {})
    sent_q = {o.get("instrument_token"): float(o.get("quantity") or 0) for o in (sent_orders or [])}
    for tok, (q0, a0) in fills.items():
        if tok in out and sent_q.get(tok):
            q1 = sent_q[tok]
            out[tok] = (q0 * a0 + q1 * out[tok]) / (q0 + q1)
        elif tok not in out:
            out[tok] = a0
    return out


def _net_qty(positions, token, product):
    """positions मधली त्या instrument (आणि product जुळत असल्यास) ची net qty बेरीज. एकही entry नाही ⇒ None (गहाळ ≠ flat)."""
    hits = [p for p in positions if p.get("instrument_token") == token and (not product or not p.get("product") or p.get("product") == product)]
    if not hits:
        return None
    try:
        return sum(int(round(float(p.get("quantity") or 0))) for p in hits)
    except (TypeError, ValueError):
        return None


def _live_in_book(book, prior):
    """order book मध्ये मागच्या प्रयत्नाशी जुळणारे (instrument + बाजू, वेळ ≥ प्रयत्न − सहनशीलता) आणि अजून terminal नसलेले orders.
    tag ने गाळत नाही (review: Upstox tag कापू/बदलू शकतो ⇒ live order सुटू नये; जास्त जुळणं ही सुरक्षित बाजू)."""
    sent = prior.get("last_sent") or []
    keys = {(o.get("instrument_token"), str(o.get("transaction_type", "")).upper()) for o in sent}
    t0 = float(prior.get("at") or 0) - BOOK_WINDOW_SEC
    live = []
    for od in book:
        if not isinstance(od, dict):
            continue
        if (od.get("instrument_token"), str(od.get("transaction_type", "")).upper()) not in keys:
            continue
        ts = od.get("order_timestamp")
        try:
            if ts and calendar.timegm(datetime.datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S").timetuple()) - 19800 < t0:
                continue                                                   # IST timestamp ⇒ epoch; मागच्या प्रयत्नाआधीचा order — संबंध नाही
        except ValueError:
            pass                                                       # वेळ वाचता आली नाही ⇒ जुळणारा मानतो (सुरक्षित बाजू)
        if str(od.get("status", "")).lower() not in TERMINAL_ALL:
            live.append(str(od.get("order_id") or "?"))
    return live


def plan_exit_resend(close_orders, positions, prior, order_status=None, order_book=None, shared_tokens=(), today=None):
    """पुढच्या exit प्रयत्नात काय पाठवायचं. रिटर्न (orders, None) किंवा (None, कारण) — कारण असेल तर काहीही पाठवू नका (unknown state).
    orders रिकामी list ⇒ broker कडे सर्व legs आधीच flat (पाठवायचं काही नाही; reconciliation पुढच्या cycle ला बंद करेल).
    prior None (आधी अपयश नाही) ⇒ close_orders जसेच्या तसे (जुनं वर्तन)."""
    if not prior:
        return close_orders, None
    if prior.get("corrupt"):
        return None, f"exit-state नोंद खराब — स्थिती अज्ञात{(' (' + str(prior.get('why')) + ')') if prior.get('why') else ''}"
    today = today or _ist_date(time.time())
    try:
        stale = bool(prior.get("at")) and _ist_date(prior["at"]) < today   # मागचा प्रयत्न आधीच्या दिवशी ⇒ DAY orders संपलेले; at नाही ⇒ आजचाच मानतो
    except (TypeError, ValueError, OverflowError, OSError):
        stale = False
    if not stale:
        pend = prior.get("pending_ids") or []
        if pend:
            if order_status is None:
                return None, f"मागच्या प्रयत्नाचे orders ({', '.join(map(str, pend))}) अजून pending/अज्ञात — त्यांची स्थिती तपासता येत नाही"
            for oid in pend:
                try:
                    d = order_status(oid)
                except Exception:
                    d = None
                if not isinstance(d, dict) or str(d.get("status", "")).lower() not in TERMINAL_ALL:
                    return None, f"मागचा order {oid} अजून terminal नाही (स्थिती: {(d or {}).get('status', 'माहीत नाही') if isinstance(d, dict) else 'माहीत नाही'})"
        if prior.get("needs_book") or prior.get("inflight"):
            if order_book is None:
                return None, "मागच्या प्रयत्नाचा निकाल अज्ञात (प्रतिसाद/fill माहिती नाही) आणि order book तपासता येत नाही"
            try:
                book = order_book()
            except Exception:
                book = None
            if not isinstance(book, list):
                return None, "मागच्या प्रयत्नाचा निकाल अज्ञात आणि order book मिळाला नाही"
            live = _live_in_book(book, prior)
            if live:
                return None, f"मागच्या प्रयत्नाचे orders अजून live: {', '.join(live)}"
    shared = sorted({o.get("instrument_token") for o in close_orders} & set(shared_tokens or ()))
    if shared:
        return None, f"दुसरा OPEN LIVE trade त्याच instrument वर ({', '.join(map(str, shared))}) — broker net qty कोणाची ते सांगता येत नाही"
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
    if not isinstance(positions, list) or not all(isinstance(p, dict) for p in positions):
        return None, "broker positions चा प्रतिसाद अनपेक्षित स्वरूपात"
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
        try:
            a, q = abs(net), int(o.get("quantity") or 0)
            bq = None if o.get("broker_quantity") is None else int(o.get("broker_quantity"))
        except (TypeError, ValueError):
            return None, f"{tok}: order quantity अवैध"
        p = dict(o)
        if a == q or (bq is not None and a == bq):
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
                      "Upstox app मध्ये positions आणि orders लगेच तपासा; गरज असल्यास हाताने बंद करा. स्थिती स्पष्ट झाल्यावर पुढचा cycle पुन्हा तपासेल.",
                      f"Broker वर हाताने बंद केलं असेल तर VPS वर: <code>python3 clear_exit_state.py --trade-id {trade_id} --mark-closed</code>"])


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
