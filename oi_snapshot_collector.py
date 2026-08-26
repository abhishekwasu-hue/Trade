"""
oi_snapshot_collector.py
----------------------------
पूर्णपणे स्वयंचलित (unattended), local machine वर cron/scheduler द्वारे दर १० मिनिटांनी चालवायची
script — वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा:

⚠️ आधी समस्या: OI Diff Snapshot फक्त Dashboard browser मध्ये उघडं असतानाच (आणि auto-refresh चालू
असतानाच) साठवला जायचा — browser बंद केल्यास त्या काळातले snapshots कधीच रेकॉर्ड होत नव्हते, इतिहासात
पोकळी (gaps) राहायची.

✅ आता: हीच स्वतंत्र script cron ने दर १० मिनिटांनी चालवली, तर ती Option Chain fetch करून, OI/Premium
गणना करून, त्याच database (oi_diff_snapshots table) मध्ये साठवते — Dashboard सोबतच वापरलेल्याच,
पुनर्वापर केलेल्या (oi_analysis.fetch_and_save_oi_snapshot) function द्वारे — त्यामुळे Dashboard आणि ही
script नेहमी सुसंगत निकाल देतात. Browser नंतर कधीही उघडलं, तरी मधल्या काळातले सर्व snapshots आधीच
टेबलमध्ये साठवलेले दिसतील.

⚙️ चालवणे (cron उदाहरण, दर १० मिनिटांनी बाजार-वेळेत):
  */10 9-15 * * 1-5  python3 oi_snapshot_collector.py --token YOUR_UPSTOX_TOKEN
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, get_ist_now
from upstox_api import fetch_upstox_option_chain
from oi_analysis import fetch_and_save_oi_snapshot
from notifications import notify_error, write_heartbeat

KILL_SWITCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "KILL_SWITCH")


SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]  # 🎓 वापरकर्त्याशी चर्चा करून जोडलेला SENSEX


def is_kill_switch_active():
    return os.path.exists(KILL_SWITCH_PATH)


def run_cycle(access_token, symbols=None):
    """एक चक्र — दिलेल्या (डीफॉल्ट: तिन्ही) symbols साठी snapshot fetch+save (कुठलाही trade घेत नाही)."""
    symbols = symbols or SYMBOLS
    if is_kill_switch_active():
        write_heartbeat("oi_snapshot_collector")
        return "🛑 KILL SWITCH सक्रिय — कुठलाही snapshot घेतला जाणार नाही."

    results = []
    try:
        for symbol in symbols:
            snapshot, status = fetch_and_save_oi_snapshot(access_token, symbol, fetch_upstox_option_chain, get_ist_now, DB_PATH, atm_range=6)
            if snapshot is None:
                results.append(f"[{symbol}] ❌ अयशस्वी: {status}")
            else:
                results.append(f"[{symbol}] ✅ [{snapshot['snapshot_time']}] Diff={snapshot['diff']}, Signal={snapshot['signal']} ({status})")
        write_heartbeat("oi_snapshot_collector")
        return "\n".join(results)
    except Exception as exc:
        notify_error("oi_snapshot_collector", f"चक्रादरम्यान अनपेक्षित चूक: {exc}")
        raise


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX", help="स्वल्पविरामाने वेगळे केलेले symbols")
    args = parser.parse_args()

    result = run_cycle(args.token, args.symbols.split(","))
    print(f"[{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}]\n{result}")
