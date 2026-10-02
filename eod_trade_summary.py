"""
eod_trade_summary.py
------------------------------
🎓 वापरकर्त्याची मागणी ("Market closed झाल्यानंतर एकूण trade, P&L, charges याचा सुद्धा short message यायला पाहिजे") —
बाजार बंद झाल्यावर, त्या दिवसाच्या बंद झालेल्या trades चा छोटा Telegram सारांश: ट्रेड्सची संख्या (जिंकले/हरले),
Gross P&L, Charges (charges.py वरून, STT/Exchange/GST सकट) आणि Net P&L — LIVE आणि PAPER स्वतंत्र ओळींत.
Shadow trades वगळलेले (pnl_reports.generate_pnl_report() आधीच वगळतं). अजून उघड्या (OPEN) positions असतील तर त्यांची संख्या.

दोन बाजार स्वतंत्र संदेश:
    python3 eod_trade_summary.py --market nse   # NIFTY/BANKNIFTY/SENSEX — NSE बंद झाल्यावर (15:30 IST नंतर)
    python3 eod_trade_summary.py --market mcx   # CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER — MCX बंद व्हायच्या वेळेला (23:58 IST)
    --date YYYY-MM-DD   # विशिष्ट दिवसासाठी (डीफॉल्ट: आजची IST तारीख)

हे फक्त वाचतं (कुठलाही order/trade बदलत नाही). Telegram credentials नसतील तर संदेश फक्त local log मध्ये जातो
(notifications.send_telegram_message()). NSE सुट्टीच्या दिवशी (शनि/रवि/NSE holiday) NSE संदेश पाठवला जात नाही.
"""
import argparse
import datetime

from charges import MCX_FUTURES_SYMBOLS
from config import get_ist_today, is_trading_day
from database import count_open_trades, get_closed_trades_for_report
from notifications import send_telegram_message, write_heartbeat
from pnl_reports import generate_pnl_report

NSE_SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]
MARKETS = {
    "nse": ("NSE", NSE_SYMBOLS),
    "mcx": ("MCX", list(MCX_FUTURES_SYMBOLS)),
}
MODES = ("LIVE", "PAPER")


def _money(value):
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    return f"{sign}₹{abs(value):,.0f}"


def summarize_mode(symbols, day, mode):
    """एका mode (LIVE/PAPER) साठी {'trades','wins','losses','gross','charges','net'} किंवा None (त्या दिवशी काहीच नाही)."""
    trades_df = get_closed_trades_for_report(symbols, day, day, mode_filter=mode)
    _report_df, totals = generate_pnl_report(symbols, "Daily", day, day, mode_filter=mode)
    if trades_df.empty and not totals["total_trades"] and not totals["total_orders"]:
        return None
    wins = int((trades_df["realized_pnl"] > 0).sum()) if not trades_df.empty else 0
    losses = int((trades_df["realized_pnl"] < 0).sum()) if not trades_df.empty else 0
    return {
        "trades": int(totals["total_trades"] or len(trades_df)),
        "wins": wins, "losses": losses,
        "gross": float(totals["gross_pnl"]), "charges": float(totals["total_charges"]), "net": float(totals["net_pnl"]),
    }


def build_message(market, day, summaries, open_count=0):
    """summaries: {mode: summarize_mode() निकाल या None}. सर्व None असतील तर 'आज कुठलाही trade नाही' ची ओळ."""
    label = MARKETS[market][0]
    lines = [f"📊 <b>{label} दिवसाचा सारांश — {day.strftime('%Y-%m-%d')}</b>"]
    any_traded = False
    for mode in MODES:
        s = summaries.get(mode)
        if s is None:
            continue
        any_traded = True
        lines.append(
            f"<b>{mode}</b>: {s['trades']} trade (जिंक {s['wins']} / हर {s['losses']}) | "
            f"Gross {_money(s['gross'])} | Charges ₹{s['charges']:,.0f} | <b>Net {_money(s['net'])}</b>"
        )
    if not any_traded:
        lines.append("आज कुठलाही trade बंद झाला नाही.")
    if open_count:
        lines.append(f"⚠️ अजून {open_count} trade OPEN आहे.")
    return "\n".join(lines)


def run_summary(market, day=None, send_fn=send_telegram_message):
    """संदेश बनवून पाठवतो. रिटर्न: पाठवलेला मजकूर, किंवा None (NSE सुट्टीचा दिवस)."""
    day = day or get_ist_today()
    if market == "nse" and not is_trading_day(datetime.datetime.combine(day, datetime.time(12, 0))):
        return None
    symbols = MARKETS[market][1]
    summaries = {mode: summarize_mode(symbols, day, mode) for mode in MODES}
    message = build_message(market, day, summaries, open_count=count_open_trades(symbols))
    send_fn(message)
    return message


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", required=True, choices=sorted(MARKETS))
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (डीफॉल्ट: आजची IST तारीख)")
    args = parser.parse_args()
    target_day = datetime.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    sent = run_summary(args.market, target_day)
    print(sent if sent else f"{args.market.upper()}: सुट्टीचा दिवस, सारांश पाठवला नाही.")
    write_heartbeat(f"eod_trade_summary_{args.market}")
