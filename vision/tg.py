"""vision/tg.py — Telegram (V1): बटणांसह chart, caption edit, callback उत्तर, getUpdates. Token `notifications` च्याच credentials मधून;
कधीच print / log नाही. सगळी functions कधीच raise करत नाहीत (network चूक ⇒ None / False).
"""
import json
import re

import requests

API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_LIMIT = 1024                                                    # photo caption (Telegram, UTF-16 units)
TEXT_LIMIT = 4096                                                       # text message (chart नसताना पाठवलेला card / ticket)


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
    """buttons = [(text, callback_data), …] ⇒ ≤ 3 असतील तर एका ओळीत, जास्त ⇒ दोन-दोनच्या ओळी (✅ ❌ / ✏️ 📝)."""
    b = [{"text": t, "callback_data": d} for t, d in buttons]
    rows = [b] if len(b) <= 3 else [b[i:i + 2] for i in range(0, len(b), 2)]
    return json.dumps({"inline_keyboard": rows})


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
    """Photo caption किंवा (chart नसताना पाठवलेला) text — दोन्ही प्रयत्न. ⚠️ हा पूर्ण caption **बदलतो** — Vision outcome साठी कधीच नाही
    (T-1: `append_outcome` वापरा)."""
    return edit_caption(message_id, caption, chat_id, True) or edit_caption(message_id, caption, chat_id, False)


def _cut_html_safe(s, units):
    """Tags काढलेला मजकूर ≤ units (UTF-16) — शेवटचा अर्धवट entity (&am…) काढतो ⇒ HTML parse चूक नाही."""
    from bots_common import plain_text as PT
    return re.sub(r"&[#\w]*$", "", PT.tg_cut(re.sub(r"<[^>]+>", "", str(s or "")), max(0, units)))


def compose_outcome(original, line, limit=CAPTION_LIMIT):
    """T-1 (Abhi, DECISIONS 29): मूळ caption + "\n" + outcome ओळ(ी) ≤ limit. Outcome ओळ कधीच कापत नाही — जागा लागली तर **जुना** भाग
    लहान: शेवटून पूर्ण ओळी गाळतो ("…" खूण, पहिली ओळ टिकते; HTML tag अर्धवट नाही); तरीही मोठं ⇒ tags काढून जुना भाग कापतो."""
    from bots_common import plain_text as PT
    line = str(line or "").strip()
    limit = limit - PT.MARGIN
    if PT.tg_len(line) >= limit:                                         # outcome एकटीच मर्यादेपेक्षा मोठी (प्रत्यक्षात होत नाही)
        return _cut_html_safe(line, limit)
    old = str(original or "").rstrip()
    if not old:
        return line
    room = limit - PT.tg_len(line) - 1
    if PT.tg_len(old) <= room:
        return f"{old}\n{line}"
    lines = old.split("\n")
    while len(lines) > 1 and PT.tg_len("\n".join(lines + ["…"])) > room:
        lines.pop()
    s = "\n".join(lines + ["…"])
    if PT.tg_len(s) > room:
        s = _cut_html_safe(old, room - 1) + "…"
    return f"{s}\n{line}"


def append_outcome(message_id, original_caption, line, chat_id=None):
    """T-1: card कधीच पुसत नाही — मूळ caption तसाच ठेवून outcome ओळ जोडतो (`compose_outcome`), आणि बटणं काढतो (हे फक्त निर्णयानंतरच
    बोलावलं जातं). Photo caption (1024) ⇒ नाही जमलं तर text message (4096) ⇒ HTML चूक असेल तर tags काढून एकदा. कधीच raise नाही."""
    if not message_id:
        return False
    try:
        if edit_caption(message_id, compose_outcome(original_caption, line, CAPTION_LIMIT), chat_id, True):
            return True
        if edit_caption(message_id, compose_outcome(original_caption, line, TEXT_LIMIT), chat_id, False):
            return True
        plain = re.sub(r"<[^>]+>", "", str(original_caption or ""))
        return bool(edit_caption(message_id, compose_outcome(plain, line, CAPTION_LIMIT), chat_id, True))
    except Exception:                                                    # noqa: BLE001 — display only
        return False


def reply(message_id, text, chat_id=None):
    """T-1: प्रत्येक outcome ला card ला उत्तर म्हणून **नवा** छोटा संदेश (edit ला Telegram notification देत नाही). message_id नाही ⇒ साधा
    संदेश. रिटर्न नव्या संदेशाचा id किंवा None; कधीच raise नाही."""
    try:
        cid = chat_id or _creds()[1]
        if not cid:
            return None
        data = {"chat_id": cid, "text": str(text)[:TEXT_LIMIT], "parse_mode": "HTML"}
        if message_id:
            data.update(reply_to_message_id=int(message_id), allow_sending_without_reply="true")
        j = _call("sendMessage", data)
        if j is None:                                                    # HTML चूक ⇒ साध्या मजकुराने एकदा
            data.pop("parse_mode", None)
            data["text"] = re.sub(r"<[^>]+>", "", str(text))[:TEXT_LIMIT]
            j = _call("sendMessage", data)
        return (j or {}).get("result", {}).get("message_id")
    except Exception:                                                    # noqa: BLE001
        return None


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
