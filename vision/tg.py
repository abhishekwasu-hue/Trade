"""vision/tg.py — Telegram (V1): बटणांसह chart, caption edit, callback उत्तर, getUpdates. Token `notifications` च्याच credentials मधून;
कधीच print / log नाही. सगळी functions कधीच raise करत नाहीत (network चूक ⇒ None / False).
"""
import json

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def _creds():
    from notifications import _load_telegram_credentials
    return _load_telegram_credentials()


def _call(method, data=None, files=None, timeout=20, token=None):
    tok = token or _creds()[0]
    if not tok:
        return None
    try:
        r = requests.post(API.format(token=tok, method=method), data=data, files=files, timeout=timeout)
        j = r.json()
        return j if j.get("ok") else None
    except (requests.RequestException, ValueError):
        return None


def can_ask():
    """(ok, कारण). बटणं तेव्हाच: secret + approvers आहेत **आणि** बटणं जिथे जातात तो chat (notifications चा TELEGRAM_CHAT_ID) approvers मध्ये आहे
    — नाहीतर प्रत्येक दाब "परवानगी नाही" होऊन signal शांतपणे timeout नियमाने जाईल."""
    from . import decide as VD
    if not VD.secret() or not VD.approver_ids():
        return False, "VISION_CALLBACK_SECRET / TELEGRAM_APPROVER_IDS नाही"
    cid = _creds()[1]
    if not cid or str(cid).strip() not in VD.approver_ids():
        return False, "Telegram chat id TELEGRAM_APPROVER_IDS मध्ये नाही (group chat? त्याचा id पण जोडा)"
    return True, ""


def keyboard(buttons):
    """buttons = [(text, callback_data), …] ⇒ एका ओळीत."""
    return json.dumps({"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]})


def send_photo(png, caption, buttons=None, chat_id=None):
    """रिटर्न message_id किंवा None. HTML caption चूक ⇒ साध्या text ने एकदा."""
    cid = chat_id or _creds()[1]
    if not cid:
        return None
    data = {"chat_id": cid, "caption": caption[:1024], "parse_mode": "HTML"}
    if buttons:
        data["reply_markup"] = keyboard(buttons)
    files = {"photo": ("chart.png", png, "image/png")} if png else None
    method = "sendPhoto" if png else "sendMessage"
    if not png:
        data["text"] = data.pop("caption")
    j = _call(method, data, files)
    if j is None:
        import re
        plain = re.sub(r"<[^>]+>", "", caption)[:1024]
        data.pop("parse_mode", None)
        data["caption" if png else "text"] = plain
        j = _call(method, data, files)
    return (j or {}).get("result", {}).get("message_id")


def edit_caption(message_id, caption, chat_id=None, has_photo=True):
    """बटणं काढून caption बदल (निर्णय नोंद)."""
    cid = chat_id or _creds()[1]
    if not cid or not message_id:
        return False
    data = {"chat_id": cid, "message_id": message_id, "parse_mode": "HTML", "reply_markup": json.dumps({"inline_keyboard": []})}
    if has_photo:
        data["caption"] = caption[:1024]
        return _call("editMessageCaption", data) is not None
    data["text"] = caption[:4096]
    return _call("editMessageText", data) is not None


def edit_any(message_id, caption, chat_id=None):
    """Photo caption किंवा (chart नसताना पाठवलेला) text — दोन्ही प्रयत्न."""
    return edit_caption(message_id, caption, chat_id, True) or edit_caption(message_id, caption, chat_id, False)


def answer_callback(callback_id, text):
    return _call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:190]}) is not None


def send_text(text, chat_id=None):
    cid = chat_id or _creds()[1]
    if not cid:
        return False
    return _call("sendMessage", {"chat_id": cid, "text": text[:4096], "parse_mode": "HTML"}) is not None


def get_updates(offset, timeout=50):
    j = _call("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": json.dumps(["callback_query", "message"])},
              timeout=timeout + 15)
    return (j or {}).get("result") or []
