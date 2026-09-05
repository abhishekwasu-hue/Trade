"""
trade_monitor.py
------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुधारणा — established SRv2/Dynamic-S/R (आणि इतर सर्व
established रणनीती) फक्त Entry (trade उघडणे) करत होत्या — SL/Target गाठल्यावर आपोआप Exit करणारी
कुठलीही यंत्रणा अस्तित्वातच नव्हती (established sl_pnl_level/target_pnl_level फक्त database मध्ये
साठवले जायचे, कधीच परत वाचून तपासले जायचे नाहीत).

ही script established `live_trades` table मधले सर्व "OPEN" trades (कुठल्याही established रणनीतीने
उघडलेले असोत — source काहीही असो) सतत तपासते, सद्य LTP वरून P&L काढून, established sl_pnl_level/
target_pnl_level गाठले का बघते, आणि गाठले असल्यास established close_trade_manually() (नवीन
exit_reason parameter सह) वापरून आपोआप बंद करते.

⚠️ VPS वर सतत (दर १ मिनिट) चालवण्यासाठी डिझाईन केलेली — GitHub Actions वर नाही (established ५-मिनिट
मर्यादा, SL/Target-निरीक्षणासाठी खूपच धीमी).

चालवणे:
    python3 trade_monitor.py --token <UPSTOX_TOKEN>
"""
import argparse
import json
import sqlite3

import cloud_db
from config import DB_PATH
from notifications import send_telegram_message
from trading_engine import close_trade_manually
from upstox_api import fetch_ltp_map


def get_all_open_trades():
    """established live_trades table कडून सर्व 'OPEN' status चे trades वाचणे (कुठल्याही source/symbol चे असोत)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """SELECT trade_id, symbol, legs_json, lots, lot_size, net_credit,
                  sl_pnl_level, target_pnl_level, mode, source
           FROM live_trades WHERE status='OPEN'"""
    )
    rows = cur.fetchall()
    conn.close()
    cols = ["trade_id", "symbol", "legs_json", "lots", "lot_size", "net_credit",
            "sl_pnl_level", "target_pnl_level", "mode", "source"]
    return [dict(zip(cols, row)) for row in rows]


def compute_current_trade_pnl(legs, ltp_map, net_credit, lots, lot_size):
    """established close_trade_manually() च्याच P&L-गणिताचा पुनर्वापर -- फक्त तपासण्यासाठी (बंद न करता)."""
    cost_to_close_now = sum(
        ltp_map[leg["instrument_key"]] * (1 if leg["transaction_type"] == "SELL" else -1)
        for leg in legs
    )
    return (net_credit - cost_to_close_now) * lots * lot_size


def check_trade_for_exit(current_pnl, sl_pnl_level, target_pnl_level):
    """सद्य P&L, established sl_pnl_level (ऋण, तोट्याची पातळी) आणि target_pnl_level (धन, नफ्याची
    पातळी) च्या तुलनेत -- कारण द्यायचं की नाही, आणि कारण काय, ते ठरवणे."""
    if sl_pnl_level is not None and current_pnl <= sl_pnl_level:
        return "SL_HIT"
    if target_pnl_level is not None and current_pnl >= target_pnl_level:
        return "TARGET_HIT"
    return None


def run_monitor_cycle(access_token, product_type="NRML"):
    """एका cycle मध्ये, सर्व OPEN trades तपासून, आवश्यक असल्यास बंद करणे."""
    open_trades = get_all_open_trades()
    if not open_trades:
        return "कुठलेही OPEN trades नाहीत."

    results = []
    for trade in open_trades:
        legs = json.loads(trade["legs_json"]) if trade["legs_json"] else []
        if not legs:
            continue
        instrument_keys = [leg["instrument_key"] for leg in legs]
        ltp_map = fetch_ltp_map(access_token, instrument_keys)
        if any(ltp_map.get(k) is None for k in instrument_keys):
            results.append(f"{trade['trade_id']}: सद्य LTP मिळाली नाही, वगळतोय")
            continue

        current_pnl = compute_current_trade_pnl(legs, ltp_map, trade["net_credit"], trade["lots"], trade["lot_size"])
        exit_reason = check_trade_for_exit(current_pnl, trade["sl_pnl_level"], trade["target_pnl_level"])

        if exit_reason is None:
            results.append(f"{trade['trade_id']} ({trade['symbol']}, {trade['source']}): P&L ₹{current_pnl:.0f} — अजून OPEN")
            continue

        ok, close_result = close_trade_manually(access_token, trade["trade_id"], trade["symbol"], product_type, exit_reason=exit_reason)
        if ok:
            emoji = "🔴" if exit_reason == "SL_HIT" else "🟢"
            message = (
                f"{emoji} <b>{trade['symbol']} Trade बंद झाला ({exit_reason})</b>\n"
                f"Trade ID: {trade['trade_id']} (source: {trade['source']})\n"
                f"Realized P&L: ₹{close_result:.0f}"
            )
            send_telegram_message(message)
            results.append(f"{trade['trade_id']}: {exit_reason} -> बंद झाला (P&L ₹{close_result:.0f})")
        else:
            results.append(f"{trade['trade_id']}: {exit_reason} आढळला, पण बंद करताना त्रुटी: {close_result}")

    return "\n".join(results) if results else "कुठलेही trades तपासण्यासारखे नाहीत."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=False, default=None, help="Upstox Access Token (न दिल्यास Supabase मधून आपोआप)")
    parser.add_argument("--product-type", default="NRML")
    args = parser.parse_args()

    token = cloud_db.get_effective_upstox_token(args.token)
    if not token:
        print("❌ कुठलाही Upstox token उपलब्ध नाही (--token दिलेला नाही, आणि Supabase मध्येही साठवलेला नाही).")
        exit(1)

    print(run_monitor_cycle(token, args.product_type))
