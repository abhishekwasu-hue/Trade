"""
engine_service.py
------------------------------------
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Phase 1 — Position Monitoring Decoupling) — established
`manage_open_trades()` (SL/Target/EOD/OI-reversal exits) आधी फक्त Streamlit Dashboard page उघडं
असताना, आणि established `st_autorefresh` साठी browser tab उघडं असतानाच चालायचं. ब्राउझर बंद केला की
थांबायचं — म्हणजे उघडे live positions रात्रभर SL/Target/EOD शिवाय राहण्याचा गंभीर धोका होता.

ही script आता तेच काम — पण Dashboard पासून पूर्णपणे स्वतंत्र — established codebase-convention प्रमाणे
"single-shot" स्वरूपात करते (srv2_momentum_reversal_strategy.py, oi_snapshot_collector.py सारखीच —
एकदा चालून थांबते, systemd timer/cron दर १ मिनिटाला पुन्हा चालवतो). हे established, कायम-चालणाऱ्या
"while True" daemon पेक्षा 1GB RAM droplet साठी सुरक्षित आहे (memory leak साचण्याचा प्रश्नच येत नाही —
प्रत्येक वेळी ताजी प्रोसेस, थोडक्यात आयुष्य).

Settings established Streamlit sidebar वरून established data/engine_settings.json मध्ये (dashboard
लिहितं) येतात — नसेल/वाचता आला नाही तर सुरक्षित डीफॉल्ट्स वापरले जातात (शांतपणे, क्रॅश न होता).
Token established cloud_db (Supabase, upstox_tokens table) मार्फत — तोच जो dashboard आणि इतर सर्व
cron scripts वापरतात.

चालवणे (systemd timer/cron मधून, दर १ मिनिटाला, बाजार तासांत):
    python3 engine_service.py
"""
import json
import os

import cloud_db
from config import is_market_open
from notifications import notify_error, notify_exit, write_heartbeat
from trading_engine import manage_open_trades
from upstox_api import fetch_candles

SCRIPT_NAME = "engine_service"
SETTINGS_PATH = os.path.join("data", "engine_settings.json")
MONITORED_SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]

DEFAULT_SETTINGS = {
    "trading_mode": "PAPER",
    "monitoring_enabled": False,
    "product_type": "D",
    "oi_reversal_exit_enabled": True,
    "trailing_sl_enabled": False,
    "atr_multiplier": 1.5,
    "eod_squareoff_hour": 15,
    "eod_squareoff_minute": 15,
}


def load_settings():
    """data/engine_settings.json वाचणे — नसेल/करप्ट असेल तर सुरक्षित डीफॉल्ट्स (monitoring_enabled=False,
    म्हणजे काहीतरी चुकलं तरी आपोआप कुठलाही exit-order जाणार नाही — fail-safe)."""
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        merged.update(settings)
        return merged
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def compute_atr_points(access_token, symbol, settings):
    """trailing_sl_enabled असेल तरच 15-मिनिट candles वरून ATR काढणे — नाहीतर None (मूळ स्थिर SL वापरला जाईल)."""
    if not settings.get("trailing_sl_enabled"):
        return None
    try:
        from signals import compute_atr
    except ImportError:
        return None
    try:
        df = fetch_candles(access_token, symbol, underlying_price=0, interval="15minute", lookback_days=5)
        return compute_atr(df, period=14) if not df.empty else None
    except Exception:
        return None  # ATR मिळालं नाही तर ट्रेलिंग बंद राहील, मूळ स्थिर SL तसाच लागू होईल — क्रॅश नाही


def run_once():
    if not is_market_open():
        return  # बाजार बंद असताना उगाच काहीही तपासायचं नाही

    settings = load_settings()
    if not settings.get("monitoring_enabled"):
        return  # Dashboard वरून Live Trading सक्रिय/पुष्टी केलेली नाही — काहीही करायचं नाही

    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        notify_error(SCRIPT_NAME, "Upstox token सापडला नाही (Supabase रिकामं) — Position Monitoring या cycle साठी वगळलं.")
        return

    for symbol in MONITORED_SYMBOLS:
        try:
            atr_points = compute_atr_points(token, symbol, settings)
            closed_now = manage_open_trades(
                token, symbol, settings["product_type"],
                eod_squareoff_hour=settings["eod_squareoff_hour"],
                eod_squareoff_minute=settings["eod_squareoff_minute"],
                oi_reversal_exit_enabled=settings["oi_reversal_exit_enabled"],
                trailing_sl_enabled=settings["trailing_sl_enabled"],
                atr_points=atr_points, atr_multiplier=settings["atr_multiplier"],
            )
            for c in closed_now:
                notify_exit(SCRIPT_NAME, symbol, c["trade_id"], c["reason"], pnl=c.get("pnl"))
        except Exception as exc:
            # एका symbol मध्ये अपयश आलं तरी बाकीच्या symbols चं monitoring थांबता कामा नये.
            notify_error(SCRIPT_NAME, f"{symbol} monitoring अयशस्वी: {exc}")

    write_heartbeat(SCRIPT_NAME)


if __name__ == "__main__":
    run_once()
