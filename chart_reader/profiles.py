"""chart_reader/profiles.py — प्रत्येक bot चे timeframes (TRADE_BOTS_UPGRADE_PROMPT §2). फक्त TF वेगळे; बाकी engine एकच."""
PROFILES = {
    "srv2": {"areas_tfs": ["1h", "1d"], "trigger_tf": "15m", "break_tf": "15m", "elliott_degrees": [1, 2]},
    "classic": {"areas_tfs": ["1h", "4h"], "trigger_tf": "15m", "break_tf": "15m", "elliott_degrees": [1, 2]},
    "instant": {"areas_tfs": ["15m", "1h"], "trigger_tf": "5m", "break_tf": "15m", "elliott_degrees": [0, 1]},
    "mcx": {"areas_tfs": ["1h", "4h"], "trigger_tf": "15m", "break_tf": "15m", "elliott_degrees": [1, 2]},
}
TF_MINUTES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
