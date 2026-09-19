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

⚠️ VPS वर सतत (दर १ मिनिट) चालवण्यासाठी डिझाईन केलेली — GitHub Actions वर नाही (५-मिनिट मर्यादा,
SL/Target-निरीक्षणासाठी खूपच धीमी).

चालवणे:
    python3 trade_monitor.py --token <UPSTOX_TOKEN>
"""
import argparse

import cloud_db
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--product-type", default="D")
    args = parser.parse_args()

    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)

    print(run_monitor_cycle(token, args.product_type))
