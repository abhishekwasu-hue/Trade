"""vision_led/telegram.py — नमुना (V-L0) संदेश: एकाच Telegram संदेशात दोन images (album) — (a) entry-वेळचा annotated chart, (b) hindsight chart.
Approve बटण नाही. Token / chat `notifications` च्याच credentials मधून (vision/tg.py); कधीच print नाही."""
import json


def send_album(pngs, caption, call=None, chat_id=None):
    """pngs = [bytes, …] (None वगळले). 1 image ⇒ sendPhoto; 2+ ⇒ sendMediaGroup (caption पहिल्या image वर). रिटर्न True/False."""
    from vision import tg as TG
    call = call or TG._call
    imgs = [p for p in pngs if p]
    cid = chat_id or TG._creds()[1]
    if not cid:
        return False
    if not imgs:
        return bool(call("sendMessage", {"chat_id": cid, "text": caption[:4000]}))
    if len(imgs) == 1:
        return bool(call("sendPhoto", {"chat_id": cid, "caption": caption[:1024]}, {"photo": ("a.png", imgs[0], "image/png")}, timeout=60))
    media = [{"type": "photo", "media": f"attach://img{i}"} for i in range(len(imgs))]
    media[0]["caption"] = caption[:1024]
    files = {f"img{i}": (f"img{i}.png", b, "image/png") for i, b in enumerate(imgs)}
    return bool(call("sendMediaGroup", {"chat_id": cid, "media": json.dumps(media)}, files, timeout=60))
