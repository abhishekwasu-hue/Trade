"""paper/pause.py — PAPER-scope pause (Abhi): Telegram /pause, /resume फक्त हा flag बदलतात. Dashboard / LIVE चा global trading pause
(cloud_db.set_trading_pause) Telegram वरून कधीच बदलत नाही. VPS local JSON (`PAPER_DATA_DIR`) — bots (cron) आणि Telegram service दोघे वाचतात.
Pause फक्त **नवे PAPER entries** थांबवतो (bot_hooks.own_signal_ok, engine मार्ग, ✋ /paper); exits / updates कधीच नाहीत.
"""
import datetime as dt
import json
import os

from . import config as PC


def _path(path=None):
    return path or os.path.join(PC.data_dir(), "paper_pause.json")


def get(path=None):
    """{"paused": bool, "reason", "by", "ts"}. वाचता आला नाही ⇒ paused False (फाइल नाही = pause नाही)."""
    p = _path(path)
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("JSON object नाही")
        return {"paused": bool(d.get("paused")), "reason": d.get("reason"), "by": d.get("by"), "ts": d.get("ts")}
    except FileNotFoundError:
        return {"paused": False, "reason": None, "by": None, "ts": None}
    except (OSError, ValueError) as exc:
        print(f"⚠️ paper_pause वाचता आला नाही ({exc}) ⇒ सुरक्षिततेसाठी pause मानतो")
        return {"paused": True, "reason": f"paper_pause फाइल वाचता आली नाही: {exc}", "by": None, "ts": None}


def set_pause(paused, by, reason=None, path=None):
    p = _path(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    d = {"paused": bool(paused), "reason": reason, "by": by, "ts": dt.datetime.now().isoformat(timespec="seconds")}
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)
    return d


def paused(path=None):
    return get(path)["paused"]
