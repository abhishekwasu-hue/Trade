"""
check_vix_spike_halt.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — "India VIX ने पहिल्या पाच मिनिटांत ठराविक% level
क्रॉस केली तर त्या दिवशी NIFTY साठी automatic bot ने trading थांबवावी" (चर्चेअंती ठरलेलं: % move
आदल्या दिवसाच्या VIX close च्या तुलनेत मोजायचा, डीफॉल्ट threshold 5%).

बाजार उघडून (9:15 IST) ~5 मिनिटांनी (9:20 IST) एकदाच चालणारं, पूर्णपणे **READ-ONLY** script (कुठलाही
order/trade टाकला जात नाही) — India VIX चा सध्याचा LTP आणि आदल्या ट्रेडिंग दिवसाचा close मागवून %
बदल मोजतं, आणि तो cloud_db.save_vix_spike_halt_status() मध्ये साठवतं — trading_engine.
check_vix_spike_halt() (फक्त NIFTY, फक्त LIVE — established Kill Switch पॅटर्नप्रमाणेच PAPER
trades कधीच अडत नाहीत) हाच आधीच साठवलेला निकाल वाचून नवीन trade अडवतं/परवानगी देतं — त्यामुळे
प्रत्येक trade attempt ला नवीन VIX API कॉल करावा लागत नाही.

मॅन्युअली चालवलं (`python3 check_vix_spike_halt.py`) तरी काम करतं — नवीन threshold ठरवण्याआधी
हातानेही चालवता येतं. नवीन crontab एंट्रीने (रोज सकाळी 9:20 IST) रोज आपोआप चालवलं, तर एका छोट्या
Telegram संदेशात निकाल पाठवला जातो (halt झालं किंवा नाही — दोन्ही स्थितीत, रोजचा run झाल्याचीही
खात्री मिळावी म्हणून मुद्दामच नेहमी).
"""
import argparse

import cloud_db
from config import get_ist_today
from notifications import send_telegram_message
from upstox_api import fetch_india_vix, fetch_india_vix_prev_close


def run_vix_spike_check(access_token, print_fn=print, send_alert=True):
    """VIX चा % बदल मोजून आजचा निकाल cloud_db मध्ये साठवणे + (send_alert=True असेल तर) Telegram वर
    कळवणे. रिटर्न: halted (bool) — आजच्यापुरतं NIFTY LIVE trading थांबवलं की नाही."""
    settings = cloud_db.get_vix_spike_halt_settings()
    trade_date = get_ist_today().strftime("%Y-%m-%d")

    if not settings.get("enabled", True):
        print_fn("VIX Spike Halt बंद आहे (settings मधून) — तपासणी वगळली.")
        return False

    current_vix = fetch_india_vix(access_token)
    prev_close = fetch_india_vix_prev_close(access_token)
    threshold_pct = settings.get("threshold_pct", 5.0)

    if current_vix is None or prev_close is None or prev_close <= 0:
        # 🎓 established Kill Switch च्या "unverified PnL"/"capital unknown" fail-safe पॅटर्नप्रमाणेच —
        # सुरक्षा-निर्णायक डेटाच मिळाला नाही, तर धोका पत्करण्यापेक्षा त्या दिवसापुरतं थांबवणंच सुरक्षित.
        report = (
            f"⚠️ VIX Spike Check — India VIX किंमत मिळाली नाही (सध्याचा: {current_vix}, आदल्या दिवसाचा: "
            f"{prev_close}) — token/नेटवर्क तपासा. सुरक्षिततेसाठी आजचे नवीन NIFTY LIVE trades थांबवले."
        )
        cloud_db.save_vix_spike_halt_status(trade_date, True, prev_close, current_vix, None)
        print_fn(report)
        if send_alert:
            try:
                send_telegram_message(f"🔴 {report}")
            except Exception:
                print_fn("⚠️ Telegram अलर्ट पाठवताना चूक (रिपोर्ट वरती प्रिंट झालेलाच आहे).")
        return True

    pct_change = (current_vix - prev_close) / prev_close * 100
    halted = pct_change >= threshold_pct
    cloud_db.save_vix_spike_halt_status(trade_date, halted, prev_close, current_vix, pct_change)

    emoji = "🔴" if halted else "🟢"
    report = (
        f"{emoji} VIX Spike Check — आदल्या दिवसाचा close {prev_close:.2f}, आत्ताचा VIX {current_vix:.2f} "
        f"({pct_change:+.1f}%, मर्यादा {threshold_pct:.0f}%)"
        + (
            " — NIFTY साठी आजचे नवीन LIVE trades थांबवले (PAPER trades नेहमीप्रमाणेच चालू राहतील)."
            if halted else " — मर्यादेच्या आत, NIFTY LIVE trading नेहमीप्रमाणे चालू."
        )
    )
    print_fn(report)
    if send_alert:
        try:
            send_telegram_message(report)
        except Exception:
            print_fn("⚠️ Telegram अलर्ट पाठवताना चूक (रिपोर्ट वरती प्रिंट झालेलाच आहे).")
    return halted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--no-alert", action="store_true", help="Telegram अलर्ट पाठवू नका (फक्त स्क्रीनवर रिपोर्ट)")
    args = parser.parse_args()

    resolved_token = cloud_db.get_effective_upstox_token(args.token)
    halted_today = run_vix_spike_check(resolved_token, send_alert=not args.no_alert)
    raise SystemExit(1 if halted_today else 0)
