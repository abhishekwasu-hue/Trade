"""
clear_exit_state.py
-------------------
🎓 Partial-exit safety fix चा "operator escape". Bot ने exit थांबवला (स्थिती अनिश्चित) आणि तुम्ही Upstox / broker app मध्ये स्वतः
positions आणि orders तपासले असतील, तेव्हाच वापरा.

  python3 clear_exit_state.py --trade-id T123                  # फक्त नोंद दाखवतो (काहीही बदलत नाही)
  python3 clear_exit_state.py --trade-id T123 --clear          # exit-state साफ ⇒ पुढचा cycle पहिल्या प्रयत्नासारखा सर्व legs पाठवेल
  python3 clear_exit_state.py --trade-id T123 --mark-closed    # broker वर हाताने बंद केलं ⇒ DB मध्ये CLOSED (MANUAL_BROKER_CLOSE) + state साफ
  python3 clear_exit_state.py --reset-file                     # data/exit_state.json वाचता येत नाही (सर्व exits blocked) ⇒ फाईल बाजूला

⚠️ --clear नंतर bot **सर्व legs** पुन्हा पाठवतो. broker वर काही legs आधीच बंद असतील तर --clear वापरू नका; --mark-closed वापरा
(आणि उरलेले legs हाताने बंद करा).
"""
import argparse
import json
import os
import sqlite3
import sys
import time

import order_safety


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trade-id")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--clear", action="store_true")
    g.add_argument("--mark-closed", action="store_true")
    g.add_argument("--reset-file", action="store_true")
    a = ap.parse_args(argv)
    if a.reset_file:
        path = order_safety.EXIT_STATE_PATH
        if not os.path.exists(path):
            print(f"{path} नाही — काही करायचं नाही.")
            return 0
        try:
            order_safety._load_state_strict()
            print(f"{path} वाचता येतो — reset ची गरज नाही (एका trade साठी --trade-id … --clear/--mark-closed वापरा).")
            return 0
        except order_safety.StateUnreadable:
            pass
        dest = f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
        os.replace(path, dest)
        print(f"खराब फाईल बाजूला ठेवली: {dest}. पुढचा cycle exits पुन्हा पाठवेल (आधी broker positions तपासले असतील याची खात्री करा).")
        return 0
    if not a.trade_id:
        ap.error("--trade-id लागतो (किंवा --reset-file)")
    st = order_safety.load_exit_state(a.trade_id)
    print("exit-state:", json.dumps(st, ensure_ascii=False, indent=1) if st else "नाही")
    if a.clear:
        order_safety.record_success(a.trade_id)
        print("साफ केलं. पुढचा monitor cycle (SL/Target लागू असल्यास) सर्व legs पाठवेल.")
    elif a.mark_closed:
        from config import DB_PATH, get_ist_now
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("UPDATE live_trades SET status='CLOSED', exit_time=?, exit_reason='MANUAL_BROKER_CLOSE', "
                           "exit_reason_detail=COALESCE(exit_reason_detail, 'broker वर हाताने बंद (clear_exit_state.py)') "
                           "WHERE trade_id=? AND status='OPEN'", (get_ist_now().strftime("%Y-%m-%d %H:%M:%S"), a.trade_id))
        conn.commit()
        n = cur.rowcount
        conn.close()
        order_safety.record_success(a.trade_id)
        print(f"DB: {n} trade CLOSED (MANUAL_BROKER_CLOSE); exit-state साफ." if n else "DB मध्ये OPEN trade सापडला नाही; exit-state साफ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
