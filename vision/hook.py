"""vision/hook.py — bots कडून signal नोंदवणे (V0). **Trading वर कुठलाच परिणाम नाही.**

🎓 `submit_signal(...)` नेहमी None परत करतो आणि कधीच raise करत नाही — bot च्या निर्णयाला (order / size / skip) काहीच देत नाही. तो फक्त
`vision_signals` मध्ये QUEUED row टाकतो (SQLite insert, मिलिसेकंद); render + vision + Telegram हे वेगळा worker (`python3 -m vision.worker`) करतो.
LIVE bot ⇒ काहीच नाही. Mode off / symbol यादीत नाही ⇒ काहीच नाही.
"""
from . import config as VC
from . import store as VS


HOOK_DB_TIMEOUT = 2                                                     # DB lock असेल तर bot जास्तीत जास्त ~2 s × 2 थांबतो, मग hook सोडून देतो


def submit_signal(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot=None, algo_decision="ENTER", tags=None,
                  invalidation=None, last_bar=None, path=None):
    """रिटर्न नेहमी None. (signal_id हवा असेल तर tests साठी `_submit` वापरा.)
    last_bar = bot ने signal च्या क्षणी पाहिलेली शेवटची 1m candle (चालू minute असू शकते) — chart वर शेवटचा अर्धवट bar म्हणून; ही bot कडची
    त्या क्षणीची माहिती आहे, भविष्य नाही."""
    try:
        _submit(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot, algo_decision, tags, invalidation, path,
                last_bar)
    except Exception as exc:                                             # vision ची कुठलीही चूक bot ला थांबवत नाही
        print(f"⚠️ vision hook त्रुटी (trade वर परिणाम नाही): {type(exc).__name__}: {exc}")
    return None


def _submit(bot, symbol, trading_mode, direction, level, role, setup_tf, signal_ts, spot=None, algo_decision="ENTER", tags=None,
            invalidation=None, path=None, last_bar=None):
    s = VC.load(bot, path, HOOK_DB_TIMEOUT)
    mode = VC.effective_mode(s, trading_mode)
    if mode == "off" or str(symbol).upper() not in [x.upper() for x in s.get("symbols") or []]:
        return None
    setup = {"tags": dict(tags or {}), "invalidation": invalidation, "bot_label": VC.BOTS.get(bot, (bot,))[0], "last_bar": _bar(last_bar)}
    return VS.insert_signal({"bot": bot, "symbol": str(symbol).upper(), "trading_mode": "PAPER", "mode": mode, "signal_ts": signal_ts,
                             "direction": direction, "level": float(level) if level is not None else None, "role": role,
                             "setup_tf": setup_tf, "spot": float(spot) if spot is not None else None, "setup": setup,
                             "algo_decision": algo_decision}, path, HOOK_DB_TIMEOUT)


def _bar(b):
    if not b:
        return None
    try:
        return {"timestamp": str(b["timestamp"]), **{k: float(b[k]) for k in ("open", "high", "low", "close")}}
    except (KeyError, TypeError, ValueError):
        return None
