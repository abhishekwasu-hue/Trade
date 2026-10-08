"""verify_opportunity_data_availability.py  (Opportunity Engine — PR-0)
----------------------------------------------------------------------
🎓 वापरकर्त्याने मंजूर केलेल्या आराखड्यातला PR-0: Opportunity Engine चे backtest आणि volume-validation कोणत्या डेटावर शक्य आहेत हे
**अंदाजाने नाही, प्रत्यक्ष Upstox खात्यावरून** ठरवण्यासाठी. फक्त **वाचतं** (फक्त HTTP GET; कुठलाही order नाही, कुठलाही DB write नाही).
ज्या दाव्यांवर आराखडा अवलंबून आहे आणि जे sandbox मधून तपासता आले नाहीत (Upstox इथून blocked, token नाही):

  १. NIFTY/BANKNIFTY चा 1M/5M/15M/30M/Daily इतिहास Upstox कडून किती मागे मिळतो? (सार्वजनिकरीत्या "मिनिट-डेटा जानेवारी 2022 पासून" असं
     सांगितलं जातं — हे तुमच्या खात्यावर खरं आहे का, आणि अचूक कोणत्या तारखेपासून?)
  २. Index candles मध्ये volume असतो का? (offline डेटात नाही; spot index वर सहसा 0.)
  ३. सध्याच्या (front-month) NIFTY/BANKNIFTY futures च्या candles मध्ये volume आणि OI असतात का?
  ४. **Expired futures** चा ऐतिहासिक volume (आणि OI) मिळतो का, आणि किती वर्षं मागे? (Upstox चे "Expired Instruments" API — ते **Upstox Plus plan**
     चे आहेत असं सांगितलं जातं; plan नसेल तर इथे 401/403 दिसेल आणि तसंच सांगितलं जाईल.)

निकाल "डेटा नाही" वि. "परवानगी/चूक" असा वेगळा दाखवला जातो (HTTP status आणि Upstox चा error मजकूर सकट) — कारण दोन्ही चा अर्थ वेगळा आहे.
Token कधीही print होत नाही.

चालवणे (VPS वर; token Supabase मधून आपोआप):
    python3 verify_opportunity_data_availability.py
    python3 verify_opportunity_data_availability.py --quick                      # फक्त 5M/15M, कमी expiry नमुने (~1 मिनिट)
    python3 verify_opportunity_data_availability.py --symbols NIFTY --json /tmp/oe_data.json
    python3 verify_opportunity_data_availability.py --token <UPSTOX_TOKEN>
साधारण वेळ: 2–4 मिनिटं (rate-limit टाळण्यासाठी प्रत्येक कॉलमध्ये थोडा विराम). निकाल (संपूर्ण print) मला पाठवा.
"""
import argparse
import datetime
import json
import time
import urllib.parse

import requests

import cloud_db
from config import get_ist_today
from upstox_api import SYMBOL_INSTRUMENT_KEYS

BASE_V3 = "https://api.upstox.com/v3/historical-candle"
BASE_V2 = "https://api.upstox.com/v2"

REQUEST_PAUSE_SECONDS = 0.35           # प्रत्येक यशस्वी/अयशस्वी कॉलनंतर विराम (rate-limit साठी); tests मध्ये 0
PROBE_WINDOW_DAYS = 10                 # इतिहास-शोधात प्रत्येक प्रश्न: "या 10 दिवसांत काही candle आहे का?" (सुट्ट्यांमुळे रिकामं पडू नये; 1-15M साठी ≤1 महिना मर्यादा पाळली)
CHECKPOINT_MONTHS = (1, 3, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 72, 84, 96, 120)
HISTORY_INTERVALS = ("1minute", "5minute", "15minute", "30minute", "day")
QUICK_INTERVALS = ("5minute", "15minute")
DEFAULT_SYMBOLS = ("NIFTY", "BANKNIFTY")
EXPIRED_SAMPLE_MONTHS_BACK = (1, 2, 6, 12, 24, 36, 48, 60)
EXPIRED_SAMPLE_MONTHS_BACK_QUICK = (1, 12, 36)

_V3_UNITS = {
    "1minute": ("minutes", "1"), "5minute": ("minutes", "5"), "15minute": ("minutes", "15"),
    "30minute": ("minutes", "30"), "day": ("days", "1"),
}


# ---------------------------------------------------------------------------------------------------------------------
# HTTP (फक्त GET)
# ---------------------------------------------------------------------------------------------------------------------
def _get(url, token, params=None, timeout=20, retries=3):
    """रिटर्न (status, json_body|None, error_text|None). 429/5xx वर backoff; इतर कुठल्याही status वर लगेच परत. network चूक => (None, None, text)."""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token.strip()}"}
    last_error = None
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(1.5 ** attempt, 10))
            continue
        if res.status_code in (429, 502, 503, 504) and attempt < retries:
            try:
                wait = float(res.headers.get("Retry-After", 1.5 ** attempt))
            except (TypeError, ValueError):
                wait = 1.5 ** attempt
            time.sleep(min(wait, 20))
            continue
        time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            body = res.json()
        except ValueError:
            body = None
        return res.status_code, body, (None if res.status_code == 200 else (res.text or "")[:300])
    return None, None, last_error


def fetch_candles_window(token, instrument_key, interval, from_date, to_date, expired=False):
    """एका तारीख-रेंजचे candles. रिटर्न {"status", "candles": [[ts,o,h,l,c,volume,oi], ...], "error"}."""
    key = urllib.parse.quote(instrument_key, safe="")
    to_s, from_s = to_date.strftime("%Y-%m-%d"), from_date.strftime("%Y-%m-%d")
    if expired:
        url = f"{BASE_V2}/expired-instruments/historical-candle/{key}/{interval}/{to_s}/{from_s}"
    else:
        unit, val = _V3_UNITS[interval]
        url = f"{BASE_V3}/{key}/{unit}/{val}/{to_s}/{from_s}"
    status, body, error = _get(url, token)
    candles = (((body or {}).get("data") or {}).get("candles") or []) if status == 200 else []
    return {"status": status, "candles": candles, "error": error}


def summarize_candles(candles):
    """rows, पहिली/शेवटची वेळ, आणि volume / OI > 0 असलेल्या rows चं %."""
    n = len(candles)
    if n == 0:
        return {"rows": 0}

    def _num(row, idx):
        try:
            return float(row[idx]) if len(row) > idx and row[idx] is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    stamps = sorted(str(c[0]) for c in candles)
    return {
        "rows": n, "first": stamps[0], "last": stamps[-1],
        "volume_nonzero_pct": round(100.0 * sum(1 for c in candles if _num(c, 5) > 0) / n, 1),
        "oi_nonzero_pct": round(100.0 * sum(1 for c in candles if _num(c, 6) > 0) / n, 1),
    }


# ---------------------------------------------------------------------------------------------------------------------
# १. इतिहास किती मागे? (coarse checkpoints + bisection)
# ---------------------------------------------------------------------------------------------------------------------
def find_earliest_data(probe, today, checkpoint_months=CHECKPOINT_MONTHS, window_days=PROBE_WINDOW_DAYS):
    """`probe(end_date) -> (has_data: bool, info)`. प्रथम वाढत्या महिन्यांवर तपासतो, पहिला "डेटा नाही" सापडल्यावर त्या आणि शेवटच्या "डेटा आहे" दरम्यान bisect.
    रिटर्न state: FOUND (पहिला डेटा-दिवस `earliest_between` मध्ये), AT_LEAST (सर्वात जुन्या checkpoint ला सुद्धा डेटा), NO_DATA (पहिल्याच checkpoint ला नाही)."""
    last_yes = first_no = None
    first_failure = None
    calls = 0
    for months in checkpoint_months:
        end = today - datetime.timedelta(days=round(months * 30.44))
        ok, info = probe(end)
        calls += 1
        if ok:
            last_yes = end
        else:
            first_no, first_failure = end, info
            break
    if first_no is None:
        return {"state": "AT_LEAST", "depth_months": checkpoint_months[-1], "calls": calls}
    if last_yes is None:
        return {"state": "NO_DATA", "first_failure": first_failure, "calls": calls}
    lo, hi = first_no, last_yes                # lo: डेटा नाही, hi: डेटा आहे
    while (hi - lo).days > window_days:
        mid = lo + (hi - lo) // 2
        ok, _ = probe(mid)
        calls += 1
        if ok:
            hi = mid
        else:
            lo = mid
    return {
        "state": "FOUND", "calls": calls,
        "earliest_between": [(lo + datetime.timedelta(days=1)).isoformat(), hi.isoformat()],
    }


def history_depth(token, instrument_key, interval, today):
    def probe(end_date):
        r = fetch_candles_window(token, instrument_key, interval, end_date - datetime.timedelta(days=PROBE_WINDOW_DAYS - 1), end_date)
        return bool(r["candles"]), {"status": r["status"], "error": r["error"]}

    return find_earliest_data(probe, today)


# ---------------------------------------------------------------------------------------------------------------------
# ३. सध्याचं (front-month) futures
# ---------------------------------------------------------------------------------------------------------------------
def _expiry_str(value):
    """Upstox 'expiry' — 'YYYY-MM-DD' किंवा epoch-ms; दोन्हीला 'YYYY-MM-DD'."""
    if value is None or value == "":
        return ""
    try:
        number = float(value)
        if number > 1e11:
            number /= 1000.0
        return (datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=number, hours=5, minutes=30)).date().isoformat()
    except (TypeError, ValueError):
        return str(value)[:10]


def _name_before_fut(trading_symbol):
    return (trading_symbol or "").upper().split(" FUT")[0].strip()


def resolve_front_future(token, name, today):
    """NSE index futures चा सध्याचा front-month contract — trading_symbol चा ' FUT' आधीचा भाग **तंतोतंत** `name` असावा (FINNIFTY/NIFTYNXT50 वगैरे वगळले जातात).
    रिटर्न (info_dict|None, error|None)."""
    params = {"query": name, "exchanges": "NSE", "segments": "FO", "instrument_types": "FUT", "page_number": 1, "records": 30}
    status, body, error = _get(f"{BASE_V2}/instruments/search", token, params=params)
    if status != 200:
        return None, f"HTTP {status}: {error}"
    rows = (body or {}).get("data") or []
    today_s = today.isoformat()
    matches = [r for r in rows if _name_before_fut(r.get("trading_symbol")) == name.upper() and _expiry_str(r.get("expiry")) >= today_s]
    if not matches:
        loose = sorted({r.get("trading_symbol", "") for r in rows})[:8]
        return None, f"'{name}' चा कुठलाही अजून expire न झालेला exact futures contract सापडला नाही (raw rows {len(rows)}; जवळची नावं: {loose})"
    matches.sort(key=lambda r: _expiry_str(r.get("expiry")))
    nearest = matches[0]
    return {
        "trading_symbol": nearest.get("trading_symbol"), "instrument_key": nearest.get("instrument_key"),
        "expiry": _expiry_str(nearest.get("expiry")), "lot_size": nearest.get("lot_size"),
    }, None


def resolve_futures_chain(token, name, today, n=2):
    """Front + पुढचे (n) अजून expire न झालेले futures contracts, expiry क्रमाने (Chart Reader K10.3: volume roll साठी पुढचा contract
    सुद्धा साठवायचा). रिटर्न (list, error|None)."""
    params = {"query": name, "exchanges": "NSE", "segments": "FO", "instrument_types": "FUT", "page_number": 1, "records": 30}
    status, body, error = _get(f"{BASE_V2}/instruments/search", token, params=params)
    if status != 200:
        return [], f"HTTP {status}: {error}"
    today_s = today.isoformat()
    rows = [r for r in ((body or {}).get("data") or []) if _name_before_fut(r.get("trading_symbol")) == name.upper()
            and _expiry_str(r.get("expiry")) >= today_s]
    rows.sort(key=lambda r: _expiry_str(r.get("expiry")))
    return [{"trading_symbol": r.get("trading_symbol"), "instrument_key": r.get("instrument_key"), "expiry": _expiry_str(r.get("expiry")),
             "lot_size": r.get("lot_size")} for r in rows[:n]], None


# ---------------------------------------------------------------------------------------------------------------------
# ४. Expired futures (Upstox Plus plan चे Expired Instruments API)
# ---------------------------------------------------------------------------------------------------------------------
def list_expiries(token, underlying_key):
    """रिटर्न (dates_sorted_asc|None, status, error)."""
    status, body, error = _get(f"{BASE_V2}/expired-instruments/expiries", token, params={"instrument_key": underlying_key})
    if status != 200:
        return None, status, error
    out = set()
    for item in ((body or {}).get("data") or []):
        value = item.get("expiry") if isinstance(item, dict) else item
        text = _expiry_str(value)
        if text:
            out.add(text)
    return sorted(out), status, None


def pick_sample_expiries(expiries, today, months_back):
    """महिन्याचा **शेवटचा** expiry (= monthly futures expiry; weekly नाही) प्रत्येक महिन्यासाठी; मग `months_back` मधल्या प्रत्येक अंतराच्या सर्वात जवळचा, + सर्वात जुना.
    फक्त आजच्या आधीचे (expired). रिटर्न तारखा, नवीन -> जुना."""
    today_s = today.isoformat()
    by_month = {}
    for d in expiries:
        if d < today_s:
            by_month[d[:7]] = max(by_month.get(d[:7], ""), d)
    monthly = sorted(by_month.values())
    if not monthly:
        return []
    chosen = {monthly[0]}
    for back in months_back:
        target = today - datetime.timedelta(days=round(back * 30.44))
        chosen.add(min(monthly, key=lambda d: abs((datetime.date.fromisoformat(d) - target).days)))
    return sorted(chosen, reverse=True)


def get_expired_future_key(token, underlying_key, underlying_name, expiry_date):
    """रिटर्न (row|None, status, error). row मध्ये `expired_instrument_key`; weekly तारखेला futures नसतो => row None."""
    status, body, error = _get(f"{BASE_V2}/expired-instruments/future/contract", token,
                               params={"instrument_key": underlying_key, "expiry_date": expiry_date})
    if status != 200:
        return None, status, error
    rows = [r for r in ((body or {}).get("data") or []) if isinstance(r, dict) and r.get("expired_instrument_key")]
    exact = [r for r in rows if _name_before_fut(r.get("trading_symbol")) == underlying_name.upper()]
    pick = exact[0] if exact else (rows[0] if len(rows) == 1 else None)
    return pick, status, None


def expired_future_sample(token, underlying_key, underlying_name, expiry_date, intervals=("5minute",)):
    sample = {"expiry": expiry_date}
    row, status, error = get_expired_future_key(token, underlying_key, underlying_name, expiry_date)
    if row is None:
        sample.update({"ok": False, "stage": "contract", "status": status, "error": error or "या expiry ला futures contract सापडला नाही"})
        return sample
    sample["expired_instrument_key"] = row["expired_instrument_key"]
    expiry = datetime.date.fromisoformat(expiry_date)
    for interval in intervals:
        r = fetch_candles_window(token, row["expired_instrument_key"], interval, expiry - datetime.timedelta(days=4), expiry, expired=True)
        sample[interval] = {"status": r["status"], "error": r["error"], **summarize_candles(r["candles"])}
    first = sample[intervals[0]]
    sample["ok"] = first.get("rows", 0) > 0
    if not sample["ok"]:
        sample.update({"stage": "candles", "status": first["status"], "error": first["error"] or "candles रिकामे"})
    return sample


# ---------------------------------------------------------------------------------------------------------------------
# एकत्रित
# ---------------------------------------------------------------------------------------------------------------------
def collect_results(token, symbols, quick, today, log=lambda s: None):
    intervals = QUICK_INTERVALS if quick else HISTORY_INTERVALS
    months_back = EXPIRED_SAMPLE_MONTHS_BACK_QUICK if quick else EXPIRED_SAMPLE_MONTHS_BACK
    results = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "today": today.isoformat(), "quick": quick,
               "history": {}, "index_volume": {}, "live_future": {}, "expired_futures": {}}
    for symbol in symbols:
        key = SYMBOL_INSTRUMENT_KEYS.get(symbol)
        if not key:
            results["history"][symbol] = {"error": "अज्ञात symbol"}
            continue
        log(f"▶ {symbol}: इतिहास-खोली ({', '.join(intervals)})…")
        results["history"][symbol] = {iv: history_depth(token, key, iv, today) for iv in intervals}

        log(f"▶ {symbol}: index candles मध्ये volume?")
        r = fetch_candles_window(token, key, "5minute", today - datetime.timedelta(days=9), today)
        results["index_volume"][symbol] = {"status": r["status"], "error": r["error"], **summarize_candles(r["candles"])}

        log(f"▶ {symbol}: सध्याचा front-month futures + volume/OI")
        info, error = resolve_front_future(token, symbol, today)
        if info is None:
            results["live_future"][symbol] = {"error": error}
        else:
            r = fetch_candles_window(token, info["instrument_key"], "5minute", today - datetime.timedelta(days=9), today)
            results["live_future"][symbol] = {**info, "status": r["status"], "error": r["error"], **summarize_candles(r["candles"])}

        log(f"▶ {symbol}: expired futures (Expired Instruments API)")
        expiries, status, error = list_expiries(token, key)
        if expiries is None:
            results["expired_futures"][symbol] = {"error": f"expiries मिळाले नाहीत — HTTP {status}: {error}", "status": status}
            continue
        samples = [expired_future_sample(token, key, symbol, d) for d in pick_sample_expiries(expiries, today, months_back)]
        results["expired_futures"][symbol] = {
            "expiries_total": len(expiries), "first_expiry": expiries[0] if expiries else None,
            "last_expiry": expiries[-1] if expiries else None, "samples": samples,
        }
    return results


# ---------------------------------------------------------------------------------------------------------------------
# अहवाल
# ---------------------------------------------------------------------------------------------------------------------
def _depth_text(r):
    if r["state"] == "FOUND":
        lo, hi = r["earliest_between"]
        return f"✅ पहिला डेटा-दिवस {lo} … {hi} दरम्यान"
    if r["state"] == "AT_LEAST":
        return f"✅ किमान {r['depth_months']} महिने (≈{r['depth_months'] // 12} वर्षं) — सर्वात जुन्या तपासणीलाही डेटा"
    f = r.get("first_failure") or {}
    return f"❌ डेटा नाही (HTTP {f.get('status')}: {f.get('error')})"


def format_report(results):
    lines = ["=" * 78, f"Opportunity Engine — डेटा उपलब्धता (आज {results['today']}{', quick' if results['quick'] else ''})", "=" * 78]
    try:
        import real_nifty_data as rn
        lines.append(f"Offline (साठवलेला) NIFTY 1M: {rn.DATA_START.date()} → {rn.DATA_END.date()} (volume नाही); Daily → {rn.DAILY_DATA_END.date()}")
    except Exception:
        pass
    lines.append("")
    lines.append("१. Upstox historical-candle: इतिहास किती मागे (v3)")
    for symbol, per in results["history"].items():
        for interval, r in per.items() if "error" not in per else []:
            lines.append(f"   {symbol:9s} {interval:9s} {_depth_text(r)}   [{r['calls']} कॉल]")
        if "error" in per:
            lines.append(f"   {symbol}: {per['error']}")
    lines.append("")
    lines.append("२. Index (spot) candles मध्ये volume?  (शेवटचे 10 दिवस, 5M)")
    for symbol, r in results["index_volume"].items():
        if r.get("rows"):
            lines.append(f"   {symbol:9s} rows={r['rows']}  volume>0: {r['volume_nonzero_pct']}%  OI>0: {r['oi_nonzero_pct']}%")
        else:
            lines.append(f"   {symbol:9s} ⚠️ candles मिळाले नाहीत (HTTP {r.get('status')}: {r.get('error')})")
    lines.append("")
    lines.append("३. सध्याचा (front-month) futures — volume/OI?")
    for symbol, r in results["live_future"].items():
        if "instrument_key" not in r:
            lines.append(f"   {symbol:9s} ❌ {r.get('error')}")
            continue
        icon = "✅" if r.get("rows") and r.get("volume_nonzero_pct", 0) > 0 else "⚠️"
        lines.append(f"   {symbol:9s} {icon} {r['trading_symbol']} ({r['instrument_key']}) expiry {r['expiry']} | rows={r.get('rows', 0)}"
                     f" volume>0: {r.get('volume_nonzero_pct', '—')}% OI>0: {r.get('oi_nonzero_pct', '—')}%")
    lines.append("")
    lines.append("४. Expired futures (Expired Instruments API; Upstox Plus plan चा असल्याचं सांगितलं जातं)")
    verdicts = []
    for symbol, r in results["expired_futures"].items():
        if "samples" not in r:
            lines.append(f"   {symbol:9s} ❌ {r['error']}")
            if r.get("status") in (401, 403):
                lines.append("             → plan/परवानगी नसू शकते (Upstox Plus plan?). Expired futures चा volume या खात्यावर उपलब्ध नाही असं समजा, जोवर वेगळं सिद्ध होत नाही.")
            verdicts.append((symbol, None))
            continue
        lines.append(f"   {symbol:9s} expiries एकूण {r['expiries_total']}  ({r['first_expiry']} … {r['last_expiry']})")
        ok_dates = []
        for s in r["samples"]:
            if s.get("ok"):
                m = s["5minute"]
                lines.append(f"             ✅ {s['expiry']}  {s['expired_instrument_key']}  rows={m['rows']} volume>0: {m['volume_nonzero_pct']}% OI>0: {m['oi_nonzero_pct']}%")
                ok_dates.append((s["expiry"], m["volume_nonzero_pct"]))
            else:
                lines.append(f"             ❌ {s['expiry']}  [{s.get('stage')}] HTTP {s.get('status')}: {s.get('error')}")
        verdicts.append((symbol, ok_dates))
    lines.append("")
    lines.append("निष्कर्ष (सूचक; अंतिम निर्णय तुम्ही/मी निकाल वाचून):")
    for symbol, per in results["history"].items():
        r = per.get("5minute") if isinstance(per, dict) else None
        if r and r["state"] == "FOUND":
            lines.append(f"   • {symbol} 5M backtest Upstox वरून शक्य: ≈ {r['earliest_between'][0]} पासून.")
        elif r and r["state"] == "AT_LEAST":
            lines.append(f"   • {symbol} 5M इतिहास ≥ {r['depth_months']} महिने.")
        elif r:
            lines.append(f"   • {symbol} 5M: डेटा मिळाला नाही — backtest शक्य नाही.")
    for symbol, ok_dates in verdicts:
        if ok_dates:
            has_vol = [d for d, v in ok_dates if v > 0]
            oldest = min(has_vol) if has_vol else None
            lines.append(f"   • {symbol} expired-futures volume: " + (f"✅ सर्वात जुना नमुना {oldest} पर्यंत volume सकट." if oldest else "candles आहेत पण volume 0."))
        else:
            lines.append(f"   • {symbol} expired-futures volume: ❌ (वर पाहा) — volume सकट backtest ला आणखी स्रोत लागेल.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="कॉमा-विभक्त (डीफॉल्ट NIFTY,BANKNIFTY)")
    parser.add_argument("--quick", action="store_true", help="फक्त 5M/15M इतिहास आणि कमी expiry नमुने")
    parser.add_argument("--json", default=None, help="संपूर्ण निकाल या JSON फाईलमध्येही साठवा")
    args = parser.parse_args(argv)
    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        raise SystemExit(1)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    results = collect_results(token, symbols, args.quick, get_ist_today(), log=lambda s: print(s, flush=True))
    print()
    print(format_report(results))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n(संपूर्ण निकाल {args.json} मध्येही साठवला)")


if __name__ == "__main__":
    main()
