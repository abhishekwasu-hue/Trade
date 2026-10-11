"""paper/lots.py — lot size Upstox instrument master (instruments search, front-month FUT) मधून; config फक्त fallback. Upstox आणि config
जुळले नाहीत ⇒ Telegram इशारा (दिवसातून एकदा). दिवसभराचा cache (VPS local JSON)."""
import datetime as dt
import json
import os

from . import config as PC

ROOT = PC.ROOT


def _cache_path(path=None):
    return path or os.path.join(PC.data_dir(), "lot_size_cache.json")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(path, d):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def _default_resolve():
    from verify_opportunity_data_availability import resolve_front_future
    return resolve_front_future


def from_master(access_token, symbol, today=None, resolve=None):
    """Upstox instrument master ⇒ lot size (int) किंवा None."""
    if not access_token:
        return None
    resolve = resolve or _default_resolve()
    info, _err = resolve(access_token, str(symbol).upper(), today or dt.date.today())
    try:
        return int((info or {}).get("lot_size")) or None
    except (TypeError, ValueError):
        return None


def lot_size(access_token, symbol, today=None, resolve=None, send=None, cache_path=None, cfg=None):
    """रिटर्न (lot_size, स्रोत). स्रोत: "upstox" / "upstox (cache)" / "config fallback". दोन्ही नाहीत ⇒ (None, कारण)."""
    today = today or dt.date.today()
    cp = _cache_path(cache_path)
    cache = _read(cp)
    key = f"{str(symbol).upper()}|{today.isoformat()}"
    fb = PC.lot_fallback(symbol, cfg)
    if key in cache and cache[key].get("lot"):
        return int(cache[key]["lot"]), "upstox (cache)"
    lot = None
    try:
        lot = from_master(access_token, symbol, today, resolve)
    except Exception as exc:
        print(f"⚠️ lot size master: {type(exc).__name__}: {exc}")
    if lot:
        cache[key] = {"lot": lot}
        if fb and fb != lot and not cache.get(f"{key}|warned"):
            cache[f"{key}|warned"] = True
            _say(send, f"⚠️ {symbol} lot size: Upstox master {lot} ≠ config fallback {fb} — Upstox चा वापरला; config.yaml दुरुस्त करा")
        _write(cp, cache)
        return lot, "upstox"
    if fb:
        if not cache.get(f"{key}|fb_warned"):
            cache[f"{key}|fb_warned"] = True
            _write(cp, cache)
            _say(send, f"⚠️ {symbol} lot size Upstox master मधून मिळाला नाही — config fallback {fb} वापरला")
        return fb, "config fallback"
    return None, "lot size नाही (Upstox master / config दोन्ही नाहीत)"


def _say(send, text):
    try:
        if send is None:
            from notifications import send_telegram_message as send
        send(text)
    except Exception:
        print(text)
