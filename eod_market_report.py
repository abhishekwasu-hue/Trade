"""
eod_market_report.py
------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — दररोज दुपारी ४ वाजता (बाजार बंद झाल्यानंतर), NIFTY,
BANKNIFTY, SENSEX तिन्हींसाठी दुसऱ्या दिवसाच्या Intraday + Positional Option Selling साठी संक्षिप्त,
कृतीयोग्य EOD Market Report — PDF (Dashboard Reports tab मध्ये साठवलेला) + Telegram (त्वरित पूष्ट)
दोन्हीकडे.

⚙️ Windows Task Scheduler: दररोज दुपारी ४ वाजता एकदाच चालवा (run_eod_market_report.bat वापरून).
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_ist_now, is_trading_day
from upstox_api import fetch_candles, fetch_india_vix, fetch_upstox_option_chain
from signals import resample_to_1h
from market_report import generate_symbol_outlook, format_telegram_summary
from pdf_reports import generate_eod_market_report_pdf
from notifications import send_telegram_message, notify_error, write_heartbeat

SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reports")


def run_report(access_token, trading_mode="PAPER"):
    """
    एका दिवसाचा EOD Market Report — तिन्ही symbols साठी generate_symbol_outlook() चालवून, एकत्र PDF
    तयार करणे व Dashboard Reports tab साठी साठवणे, आणि Telegram वर संक्षिप्त सारांश पाठवणे.
    """
    if not is_trading_day():
        write_heartbeat("eod_market_report")
        return "⏸️ आज व्यापार-दिवस नाही (सुट्टी/शनि-रवि) — Report तयार केला जाणार नाही."
    try:
        result = _run_report_inner(access_token, trading_mode)
        write_heartbeat("eod_market_report")
        return result
    except Exception as exc:
        notify_error("eod_market_report", f"Report तयार करताना अनपेक्षित चूक: {exc}")
        raise


def _run_report_inner(access_token, trading_mode):
    outlooks = []
    for symbol in SYMBOLS:
        try:
            raw_chain, _ = fetch_upstox_option_chain(access_token, symbol)
            underlying_price = raw_chain[len(raw_chain) // 2].get("underlying_spot_price", 0) if raw_chain else 0

            df_15m = fetch_candles(access_token, symbol, underlying_price, interval="15minute")
            df_1h = resample_to_1h(fetch_candles(access_token, symbol, underlying_price, interval="30minute"))
            df_1d = fetch_candles(access_token, symbol, underlying_price, interval="day")
            india_vix = fetch_india_vix(access_token)

            outlook = generate_symbol_outlook(
                access_token, symbol, df_15m=df_15m, df_1h=df_1h, df_1d=df_1d,
                india_vix=india_vix, trading_mode=trading_mode,
            )
            outlooks.append(outlook)
        except Exception as exc:
            outlooks.append({
                "symbol": symbol,
                "multi_tf_outlook": {"outlook": "डेटा त्रुटी", "daily_dir": None, "hourly_dir": None, "min15_dir": None},
                "sr_levels": None, "chart_patterns": [], "oi_summary": None,
                "india_vix": None, "recommendation": f"डेटा मिळवताना चूक: {exc}",
                "open_positions_greeks": [],
            })

    # --- PDF तयार करून साठवणे (Dashboard Reports tab साठी) ---
    os.makedirs(REPORTS_DIR, exist_ok=True)
    pdf_bytes = generate_eod_market_report_pdf(outlooks)
    today_str = get_ist_now().strftime("%Y-%m-%d")
    pdf_path = os.path.join(REPORTS_DIR, f"eod_report_{today_str}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    # --- Telegram वर संक्षिप्त सारांश पाठवणे ---
    telegram_text = format_telegram_summary(outlooks)
    send_telegram_message(telegram_text)

    return f"✅ EOD Market Report तयार झाला — {pdf_path}, Telegram वर सारांश पाठवला."


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Upstox Access Token")
    parser.add_argument("--mode", default="PAPER", choices=["PAPER", "LIVE"])
    args = parser.parse_args()

    result = run_report(args.token, args.mode)
    print(f"[{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}] {result}")
