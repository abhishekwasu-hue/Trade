"""
mcx_market_readiness_check.py
------------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (MCX LIVE करण्याआधी — "Resolver + Zones चं manual पडताळणी
स्क्रिप्ट" + "Pre-market sanity-check, रोज सकाळी आपोआप") — `PRE_LIVE_CHECKLIST.md` §5 च्या पायरी
1-2 (resolver आणि zones स्वतंत्रपणे कधीच पडताळलेले नाहीत) आता एकाच, पुन्हा-पुन्हा चालवता येण्याजोग्या
script मध्ये — पूर्णपणे **READ-ONLY** (कुठलाही order/trade टाकला जात नाही):

  1. प्रत्येक commodity साठी resolve_mcx_futures_instruments.resolve_symbol() खरा (sane)
     instrument_key/lot_size/tick_size/expiry देतोय का.
  2. प्रत्येक commodity साठी cloud_db.get_market_zones() मध्ये आजचे ACTIVE 30M/60M Dynamic S/R
     zones अस्तित्वात आहेत का (रिकामे नाहीत — रिकामे असतील तर bot "सुरक्षितच" पण पूर्णपणे निष्क्रिय
     राहतो, कुणालाच न कळता).
  3. Upstox token वैध आहे का (get_total_capital() कॉल — token expired/invalid असेल तर इथेच स्पष्ट
     कळतं, ऐन बाजार उघडताना नाही).

मॅन्युअली चालवलं (`python3 mcx_market_readiness_check.py`) तर माणसाला वाचता येईल असा तपशीलवार रिपोर्ट
प्रिंट होतो — नवीन commodity LIVE करण्याआधी हातानेही चालवता येतो. नवीन crontab एंट्रीने (रोज सकाळी,
बाजार उघडण्याआधी) रोज आपोआप चालवलं, तर एका छोट्या Telegram संदेशात सारांश पाठवला जातो (समस्या
सापडो अथवा न सापडो — रोजचा run झाल्याचीही खात्री मिळावी म्हणून मुद्दामच नेहमी, फक्त समस्या असतानाच नाही).
"""
import argparse

import cloud_db
import resolve_mcx_futures_instruments as mcx_resolver
from config import get_ist_today
from notifications import send_telegram_message
from upstox_api import get_total_capital

MCX_FUTURES_SYMBOLS = mcx_resolver.MCX_FUTURES_SYMBOLS
TIMEFRAME_SUFFIXES = ["30M", "60M"]


def check_resolver(access_token, symbols=None):
    """प्रत्येक commodity साठी resolve_mcx_futures_instruments.resolve_symbol() चा निकाल —
    {symbol: (ok: bool, detail_dict_किंवा_error_संदेश)}."""
    symbols = symbols or MCX_FUTURES_SYMBOLS
    return {sym: mcx_resolver.resolve_symbol(access_token, sym) for sym in symbols}


def check_zones(symbols=None, timeframe_suffixes=None):
    """प्रत्येक commodity साठी आजचे ACTIVE zones (30M/60M प्रत्येकी किती) —
    {symbol: {"ok": bool, "counts": {"30M": n, "60M": n}, "total": n}}. "ok"=False म्हणजे कुठलेही
    ACTIVE zones नाहीत (bot निष्क्रिय राहील — त्रुटी नाही, पण निरुपयोगी)."""
    symbols = symbols or MCX_FUTURES_SYMBOLS
    timeframe_suffixes = timeframe_suffixes or TIMEFRAME_SUFFIXES
    results = {}
    for sym in symbols:
        df = cloud_db.get_market_zones(sym, status="ACTIVE")
        counts = {tf: 0 for tf in timeframe_suffixes}
        if df is not None and not df.empty:
            for tf in timeframe_suffixes:
                counts[tf] = int(df["zone_type"].astype(str).str.endswith(f"_{tf}").sum())
        total = sum(counts.values())
        results[sym] = {"ok": total > 0, "counts": counts, "total": total}
    return results


def check_token(access_token):
    """Upstox token वैध आहे का — get_total_capital() खरा आकडा देतो का यावरून (token expired/invalid
    असेल तर None/0 येतं). रिटर्न: (ok: bool, capital_किंवा_error_संदेश)."""
    if not access_token:
        return False, "कुठलाही Upstox token उपलब्ध नाही"
    try:
        capital = get_total_capital(access_token)
    except Exception as exc:
        return False, f"capital मिळवताना चूक: {exc}"
    if not capital or capital <= 0:
        return False, "capital मिळालं नाही (token expired/invalid असू शकतो, किंवा नेटवर्क समस्या)"
    return True, capital


def build_report(resolver_results, zone_results, token_result):
    """वरच्या तिन्ही तपासण्यांचा एकत्रित, माणसाला वाचता येईल असा मजकूर + कुठलीही समस्या सापडली का
    (bool) — रिटर्न: (report_text, any_problem)."""
    lines = [f"MCX Market Readiness Check — {get_ist_today().strftime('%d-%b-%Y')}\n"]
    any_problem = False

    token_ok, token_detail = token_result
    if token_ok:
        lines.append(f"✅ Upstox Token — वैध (एकूण capital ₹{token_detail:,.0f})")
    else:
        lines.append(f"❌ Upstox Token — {token_detail}")
        any_problem = True

    lines.append("")
    for sym in resolver_results:
        r_ok, r_detail = resolver_results[sym]
        z = zone_results.get(sym, {"ok": False, "counts": {}, "total": 0})
        if r_ok:
            lines.append(
                f"✅ {sym} — resolver: {r_detail['trading_symbol']} (lot_size={r_detail['lot_size']}, "
                f"tick_size={r_detail['tick_size']}, expiry={r_detail['expiry']})"
            )
        else:
            lines.append(f"❌ {sym} — resolver: {r_detail}")
            any_problem = True

        if z["ok"]:
            counts_str = ", ".join(f"{tf}={n}" for tf, n in z["counts"].items())
            lines.append(f"   ✅ zones — एकूण {z['total']} ACTIVE ({counts_str})")
        else:
            lines.append(f"   ❌ zones — आजचे कुठलेही ACTIVE zones सापडले नाहीत (bot निष्क्रिय राहील, refresh_market_zones_mcx.py चालवा/तपासा)")
            any_problem = True

    return "\n".join(lines), any_problem


def run_readiness_check(access_token, symbols=None, print_fn=print, send_alert=True):
    """सर्व तपासण्या चालवून रिपोर्ट प्रिंट करणे + (send_alert=True असेल तर) Telegram वर सारांश
    पाठवणे — समस्या सापडो अथवा न सापडो, नेहमीच (रोजचा run न चुकता झाल्याची खात्री देण्यासाठी).
    रिटर्न: any_problem (bool)."""
    symbols = symbols or MCX_FUTURES_SYMBOLS
    token_result = check_token(access_token)
    resolver_results = check_resolver(access_token, symbols) if token_result[0] else {
        sym: (False, "token अवैध असल्याने तपासलंच नाही") for sym in symbols
    }
    zone_results = check_zones(symbols)

    report_text, any_problem = build_report(resolver_results, zone_results, token_result)
    print_fn(report_text)

    if send_alert:
        try:
            emoji = "🟢" if not any_problem else "🔴"
            telegram_summary = f"{emoji} <b>MCX Market Readiness Check</b>\n<pre>{report_text}</pre>"
            send_telegram_message(telegram_summary)
        except Exception:
            print_fn("⚠️ Telegram अलर्ट पाठवताना चूक (रिपोर्ट वरती प्रिंट झालेलाच आहे).")

    return any_problem


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--symbols", default=",".join(MCX_FUTURES_SYMBOLS))
    parser.add_argument("--no-alert", action="store_true", help="Telegram अलर्ट पाठवू नका (फक्त स्क्रीनवर रिपोर्ट)")
    args = parser.parse_args()

    resolved_token = cloud_db.get_effective_upstox_token(args.token)
    symbols_list = args.symbols.split(",")
    problem_found = run_readiness_check(resolved_token, symbols_list, send_alert=not args.no_alert)
    raise SystemExit(1 if problem_found else 0)
