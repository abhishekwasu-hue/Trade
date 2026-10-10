"""paper/bot_hooks.py — तिन्ही bots (5-Min Instant, 15M Dynamic SR, SR V3) साठी एकच hook (Abhi P0 #1, #3, #9 + token error).

  pre_cycle(...)  ⇒ cycle सुरू होताना: PAPER साठी instrument enabled (config.yaml paper.instruments), Upstox token (नाही ⇒ स्पष्ट error +
                    दिवसातून एकदा Telegram), lot size (Upstox instrument master; config फक्त fallback), signal_source = engine ⇒ engine मार्ग.
  own_signal_ok() ⇒ bot चा स्वतःचा signal वापरायचा का (own / both).
LIVE / LIVE_PAPER ⇒ lot size, enabled-तपासणी, engine मार्ग यातलं काहीच नाही (जुनं वर्तन; lot size आधीचाच default — config / master नाही).
"""
import json
import os
from dataclasses import dataclass

import engine_signal as ES

from . import config as PC
from . import lots as PL


LIVE_LEGACY_LOT_SIZE = 65   # LIVE मार्गाचा आधीचा default (process_symbol(lot_size=65)) — बदल नाही; PAPER ला Upstox master


@dataclass
class Pre:
    stop: bool
    msg: str = ""
    lot_size: int = None
    lot_src: str = ""


def _paper(settings):
    return str((settings or {}).get("trading_mode", "PAPER")).upper() == "PAPER"


def token_error(symbol, bot, send=None, state_path=None, today=None):
    """Token नाही ⇒ स्पष्ट संदेश; Telegram दिवसातून एकदा (प्रत्येक cycle ला spam नाही)."""
    import datetime as dt
    msg = f"❌ {symbol} {bot}: Upstox token नाही — आज सकाळचा daily login (Upstox app approve) करा; तोपर्यंत कुठलाही signal / entry नाही"
    p = state_path or os.path.join(PC.data_dir(), "paper_token_alert.json")
    day = (today or dt.date.today()).isoformat()
    try:
        st = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    except (OSError, ValueError):
        st = {}
    if st.get("day") != day:
        try:
            if send is None:
                from notifications import send_telegram_message as send
            send(msg)
        except Exception:
            print(msg)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            json.dump({"day": day}, open(p, "w", encoding="utf-8"))
        except OSError:
            pass
    return msg


def pre_cycle(bot, access_token, symbol, settings, lot_size=None, cfg=None, resolve=None, send=None, engine_fn=None, source=None, now=None,
              ss_key="signal_source"):
    """रिटर्न Pre. stop = True ⇒ bot ने हा cycle इथेच संपवावा (msg परत करावा)."""
    if not _paper(settings):                                             # LIVE / LIVE_PAPER ⇒ आधीचं वर्तन तंतोतंत (lot size सुद्धा) — LIVE ला हात नाही
        return Pre(False, lot_size=lot_size if lot_size is not None else LIVE_LEGACY_LOT_SIZE, lot_src="legacy (non-PAPER)")
    cfg = cfg or PC.load()
    if not PC.enabled(symbol, cfg):
        return Pre(True, f"{symbol}: PAPER साठी config.yaml मध्ये enabled: false ⇒ signal / entry नाही")
    if not access_token:
        return Pre(True, token_error(symbol, bot, send))
    if lot_size is None:
        lot_size, src = PL.lot_size(access_token, symbol, resolve=resolve, send=send, cfg=cfg)
        if lot_size is None:
            return Pre(True, f"{symbol}: {src} ⇒ entry नाही")
    else:
        src = "caller"
    if ES.source_of(settings, ss_key) == "engine":
        sts = dict(settings, signal_source="engine")
        if engine_fn is None:
            from . import engine_entry as EE
            engine_fn = EE.process
        return Pre(True, engine_fn(bot, access_token, symbol, sts, lot_size, source or bot, now=now) or f"{symbol}: engine — काही नाही",
                   lot_size, src)
    return Pre(False, lot_size=lot_size, lot_src=src)


def own_signal_ok(symbol, direction, settings, now=None, ss_key="signal_source"):
    """own ⇒ True; both ⇒ engine चा ताजा setup त्याच दिशेला; engine ⇒ False. रिटर्न (ok, कारण)."""
    if not _paper(settings):
        return True, "non-PAPER ⇒ जुनं वर्तन"
    return ES.own_allowed(symbol, direction, settings, now, key=ss_key)
