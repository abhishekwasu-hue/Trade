"""
trade_monitor.py
------------------------------------
🎓 वापरकर्त्याने सापडवलेली, अत्यंत महत्त्वाची bug — ही script आधी `trading_engine.manage_open_trades()`
ला कधीच बोलावतच नव्हती! स्वतःचंच, खूप जुनं, वेगळं exit-logic (फक्त sl_pnl_level/target_pnl_level —
निश्चित रुपये-रकमा, entry-वेळीच साठवलेल्या) वापरत होती — त्यामुळे नंतर बांधलेलं संपूर्ण नवीन
exit-तंत्रज्ञान (ITM strikes, Spot%+Premium-Points, TSL-to-Breakeven, Next-Level-Exit,
Carry-Forward, PCR Gate — trading_engine.py मधलं सर्वकाही) **प्रत्यक्षात कधीच वापरलंच जात नव्हतं**.

🎓 वापरकर्त्याशी चर्चा करून सापडलेली आणि सोडवलेली Duplicate-Exit Bug — याआधी `engine_service.py`
(वेगळा systemd timer) आणि हीच script दोघेही `manage_open_trades()` द्वारे **त्याच** live_trades
वर, **त्याच वेळी**, स्वतंत्रपणे SL/Target/EOD तपासत होते — म्हणजे एकच trade दोनदा बंद होण्याचा
धोका होता. आता सर्व logic इथेच एकत्र — तीच एकमेव, अधिकृत जागा (crontab, दर १ मिनिटाला).
`load_settings`/`compute_atr_points`/`MONITORED_SYMBOLS` — engine_service.py मधूनच import
(कोड दोनदा लिहू नये म्हणून, तीच फाईल आता फक्त या shared helpers साठी टिकवून ठेवलेली आहे).

`monitoring_enabled` (Dashboard "Live Trading" टिक) इथे गेट म्हणून वापरलेला नाही — SRv2/
Dynamic-S/R चे trades Dashboard च्या स्थितीपासून पूर्णपणे स्वतंत्र आहेत.

⚠️ VPS वर सतत (crontab, दर १ मिनिटाला नव्याने invoke) चालवण्यासाठी डिझाईन केलेली — GitHub Actions वर
नाही (५-मिनिट मर्यादा, SL/Target-निरीक्षणासाठी खूपच धीमी).

🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("SL slippage कमी करा — polling interval कमी करा") —
Performance Report मध्ये आढळलं की SL प्रत्यक्षात threshold च्या बऱ्याच पुढे जाऊन लागत होता (उदा.
-0.05% थ्रेशोल्ड असताना -0.11% वर exit) — कारण cron दर 60 सेकंदांनीच नव्याने ही script सुरू करतो,
मध्ये किंमत किती पुढे गेली हे कळतच नाही. आता cron अजूनही दर 60 सेकंदांनीच invoke करतो (तेच crontab,
बदललेलं नाही), पण प्रत्येक invocation आता स्वतःच आतून `--interval-seconds` (डीफॉल्ट सुरुवातीला 20,
वापरकर्त्याने पुढे आणखी घट्ट करून **15** केलेलं) च्या अंतराने `--loop-seconds` (डीफॉल्ट 50, 60-सेकंद
cron window च्या आत बसावं म्हणून बफर ठेवलेला) पर्यंत पुन्हा-पुन्हा तपासत राहते — म्हणजे प्रत्यक्षात
दर ~15 सेकंदांनी SL/Target तपासलं जातं, overshoot/slippage आणखी कमी होतो. ⚠️ हे अजूनही तिखट
tick-by-tick निरीक्षण नाही — फक्त interval कमी केलेला — पूर्ण उपाय (broker-side resting SL order)
स्वतंत्रपणे, नंतरच्या टप्प्यात (बघा trading_engine.py चं Phase 2 broker-side SL).

🎓 वापरकर्त्याशी चर्चा करून ठरवलेली पुढची सुधारणा (TSL-only fast check) — Performance Report च्या
SL/TSL Overshoot Tracker मध्ये आढळलं की स्पॉट%-आधारित सामान्य SL exits मध्ये slippage जवळपास शून्य
आहे (~0.00-0.01%), पण Trailing-SL (Entry/Breakeven-locked) exits मध्येच खरी slippage आहे (उदा. एका
trade मध्ये पूर्ण 1.0 premium point overshoot — त्या trade च्या संपूर्ण तोट्याइतकाच). त्यामुळे नुसता
`--interval-seconds` आणखी घट्ट करणं (सगळ्या symbols/trades साठी blanket) योग्य उपाय नाही — त्याऐवजी
आता प्रत्येक cycle नंतर `database.has_active_tsl_trades()` (हलकी, स्थानिक SQLite query — कुठलाही
Upstox API कॉल नाही) तपासून, कुठल्याही monitored symbol वर सध्या TSL-locked (tsl_activated=1) असा
trade असेल **तरच** पुढचा sleep `--tsl-interval-seconds` (डीफॉल्ट 5) इतका घट्ट केला जातो — नाहीतर
नेहमीचाच `--interval-seconds` (डीफॉल्ट 15) वापरला जातो. exit-निर्णयाचं संपूर्ण logic अजूनही तेच,
एकमेव अधिकृत `manage_open_trades()` — इथे फक्त *cadence* बदलतो, कुठलंही वेगळं/डुप्लिकेट TSL-तपासणी
function नाही (त्यामुळे trading_engine.py च्या नाजूक, history-laden exit-logic ला धक्का लागण्याचा
धोका शून्य). परिणाम: TSL सक्रिय नसताना नेहमीचाच API load, पण TSL सक्रिय झाल्यावर लगेच ~3x जास्त
वारंवार तपासलं जातं (तेवढ्यापुरतंच).

⚠️ प्रत्येक cycle मध्ये प्रत्येक monitored symbol साठी API कॉल्स होतात (ATR candles + open trades ची
LTP) — सामान्य स्थितीत 60 सेकंदांत ~4x जास्त वेळा (पूर्वी 1, नंतर ~3, आता ~4), आणि TSL सक्रिय
असलेल्या window मध्ये आणखी जास्त (~10x) — Upstox rate-limit च्या आत राहण्यासाठी `--interval-seconds`/
`--tsl-interval-seconds` गरज पडल्यास वाढवता येतात (कमी frequent, पण कमी API load).

चालवणे:
    python3 trade_monitor.py --token <UPSTOX_TOKEN>
    python3 trade_monitor.py --token <UPSTOX_TOKEN> --interval-seconds 30 --loop-seconds 50  # हळू
    python3 trade_monitor.py --token <UPSTOX_TOKEN> --tsl-interval-seconds 3  # TSL सक्रिय असताना आणखी घट्ट
"""
import argparse
import time

import cloud_db
import database
from engine_service import load_settings, compute_atr_points, MONITORED_SYMBOLS
from notifications import notify_exit, notify_error, write_heartbeat
from process_lock import ProcessLock, ProcessLockHeld
from trading_engine import manage_open_trades

SCRIPT_NAME = "trade_monitor"


def run_monitor_cycle(access_token, product_type="D"):
    """प्रत्येक symbol साठी, manage_open_trades() मार्फत सर्व OPEN trades तपासून, आवश्यक असल्यास
    बंद करणे (SL/TSL/Target/EOD/Carry-Forward/Next-Level-Exit/OI-reversal-exit/Trailing-SL —
    सर्व एकाच, अधिकृत ठिकाणाहून). एका symbol मध्ये त्रुटी आली तरी बाकीचे symbols तपासले जातच राहतात.

    🎓 वापरकर्त्याने पडताळणीत सापडवलेली, गंभीर bug (live trading आधी) — वर सांगितलेलं "duplicate-exit
    bug सुटलेली आहे" (हीच script आता एकमेव अधिकृत जागा) हे फक्त कोड-पातळीवर खरं आहे; deploy/README.md
    आणि deploy/engine_service.timer/.service अजूनही फक्त engine_service.py साठीच आहेत (या script
    साठी कुठलाही systemd unit जोडलेलाच नाही) — त्यामुळे प्रत्यक्ष VPS वर कोणती script (किंवा
    चुकून दोन्ही) चालू आहे हे repo वरून खात्रीने सांगता येत नाही. म्हणून इथे + engine_service.py
    दोन्हीकडे एकाच नावाचा ProcessLock — कुठलीही किंवा दोन्ही समांतर चालल्या तरी एकाच वेळी फक्त एकच
    प्रत्यक्षात manage_open_trades() चालवेल."""
    settings = load_settings()
    effective_product_type = settings.get("product_type", product_type)

    try:
        with ProcessLock("position_exit_monitor"):
            results = []
            any_symbol_succeeded = False
            for symbol in MONITORED_SYMBOLS:
                try:
                    atr_points = compute_atr_points(access_token, symbol, settings)
                    closed = manage_open_trades(
                        access_token, symbol, effective_product_type,
                        eod_squareoff_hour=settings.get("eod_squareoff_hour", 15),
                        eod_squareoff_minute=settings.get("eod_squareoff_minute", 15),
                        oi_reversal_exit_enabled=settings.get("oi_reversal_exit_enabled", False),
                        trailing_sl_enabled=settings.get("trailing_sl_enabled", False),
                        atr_points=atr_points,
                        atr_multiplier=settings.get("atr_multiplier", 1.5),
                    )
                    any_symbol_succeeded = True
                    for c in closed:
                        notify_exit(SCRIPT_NAME, symbol, c["trade_id"], c["reason"], c.get("pnl"))
                        results.append(f"{c['trade_id']} ({symbol}): {c['reason']} -> बंद झाला (P&L ₹{c['pnl']:.0f})")
                except Exception as e:
                    notify_error(SCRIPT_NAME, f"{symbol}: {e}")
                    results.append(f"{symbol}: त्रुटी — {e}")

            if any_symbol_succeeded:
                write_heartbeat(SCRIPT_NAME)

            return "\n".join(results) if results else "कुठलेही OPEN trades नाहीत / काहीच OPEN नाही."
    except ProcessLockHeld:
        return "⏭️ दुसरी exit-monitor invocation (हीच script किंवा engine_service.py) अजून चालू आहे — डुप्लिकेट-एक्झिट टाळण्यासाठी वगळलं."


def run_monitor_loop(token, product_type="D", interval_seconds=15, loop_seconds=50, tsl_interval_seconds=5,
                      cycle_fn=run_monitor_cycle, sleep_fn=time.sleep, now_fn=time.monotonic, print_fn=print,
                      has_active_tsl_fn=None):
    """एका cron invocation च्या आत, `interval_seconds`च्या अंतराने `loop_seconds` पर्यंत
    run_monitor_cycle() पुन्हा-पुन्हा चालवणे (SL slippage कमी करण्यासाठी — बघा वरची फाईल-टिप्पणी).
    प्रत्येक cycle चा वेळ वजा करूनच पुढचा sleep काढला जातो, जेणेकरून एकूण वेळ loop_seconds च्या आसपासच
    राहील (cycle ला जास्त वेळ लागला, तर पुढचा sleep कमी/शून्य होतो, ओलांडत नाही).

    🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (TSL-only fast check — बघा वरची फाईल-टिप्पणी) —
    प्रत्येक cycle नंतर `has_active_tsl_fn()` (डीफॉल्ट `database.has_active_tsl_trades(MONITORED_SYMBOLS)`)
    तपासून, कुठल्याही monitored symbol वर सध्या TSL-locked trade असेल तर पुढचा sleep `interval_seconds`
    ऐवजी घट्ट `tsl_interval_seconds` इतका ठेवला जातो — exit-logic (manage_open_trades()) तेच, फक्त
    cadence बदलतो."""
    has_active_tsl_fn = has_active_tsl_fn or (lambda: database.has_active_tsl_trades(MONITORED_SYMBOLS))
    start = now_fn()
    cycles = 0
    while True:
        cycle_start = now_fn()
        print_fn(cycle_fn(token, product_type))
        cycles += 1
        elapsed = now_fn() - start
        remaining_in_budget = loop_seconds - elapsed
        if remaining_in_budget <= 0:
            break
        cycle_duration = now_fn() - cycle_start
        effective_interval = tsl_interval_seconds if has_active_tsl_fn() else interval_seconds
        sleep_time = min(effective_interval - cycle_duration, remaining_in_budget)
        if sleep_time > 0:
            sleep_fn(sleep_time)
    return cycles


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--product-type", default="D")
    parser.add_argument("--interval-seconds", type=float, default=15,
                         help="किती सेकंदांच्या अंतराने पुन्हा तपासायचं (डीफॉल्ट 15 — पूर्वीच्या दर-60-सेकंदांऐवजी, वापरकर्त्याने 20 वरून आणखी घट्ट केलेलं)")
    parser.add_argument("--loop-seconds", type=float, default=50,
                         help="एका cron invocation मध्ये किती सेकंद पुन्हा-पुन्हा तपासत राहायचं (डीफॉल्ट 50 — 60-सेकंद cron window च्या आत बसावं म्हणून बफर)")
    parser.add_argument("--tsl-interval-seconds", type=float, default=5,
                         help="कुठल्याही monitored symbol वर TSL-locked (Entry/Breakeven) trade सक्रिय असेल तेव्हा किती घट्ट अंतराने तपासायचं (डीफॉल्ट 5 — नेहमीच्या --interval-seconds पेक्षा घट्ट, कारण TSL exits मध्येच खरी slippage आढळली)")
    args = parser.parse_args()

    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)

    run_monitor_loop(
        token, args.product_type, interval_seconds=args.interval_seconds,
        loop_seconds=args.loop_seconds, tsl_interval_seconds=args.tsl_interval_seconds,
    )
