"""vision/images.py — chart PNG कायमस्वरूपी जतन (§11). **Overwrite कधीच नाही**, sha256 audit record मध्ये.

    data/visual_audit/YYYY-MM-DD/<bot>_<symbol>_<signal_id>_<HHMM>_sent.png      ← vision ला गेलेली (आणि Telegram वरची) हीच image
    data/visual_audit/YYYY-MM-DD/<bot>_<symbol>_<signal_id>_<HHMM>_outcome.png   ← trade बंद झाल्यावर, POST-HOC (vision कडे कधीच नाही)
    data/visual_audit/YYYY-MM-DD/morning_<symbol>_<tf>.png                        ← (V2) सकाळचा level audit

`data/visual_audit/` gitignored (public repo). रात्री `scripts/vision_archive.py` → private trade-data.
"""
import hashlib
import os

import pandas as pd

SENT, OUTCOME = "sent", "outcome"
MAX_KB = 150


def base_dir():
    if os.environ.get("VISION_IMAGE_DIR"):
        return os.environ["VISION_IMAGE_DIR"]
    from config import DATA_DIR
    return os.path.join(DATA_DIR, "visual_audit")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def _safe(x):
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(x))


def signal_path(row, kind, base=None):
    ts = pd.Timestamp(row["signal_ts"])
    d = os.path.join(base or base_dir(), ts.strftime("%Y-%m-%d"))
    return os.path.join(d, f"{_safe(row['bot'])}_{_safe(row['symbol'])}_{_safe(row['signal_id'])}_{ts:%H%M}_{kind}.png")


def morning_path(symbol, tf, day, base=None):
    return os.path.join(base or base_dir(), str(day), f"morning_{_safe(symbol)}_{_safe(tf)}.png")


def save_exclusive(path, data):
    """नवीन फाईल फक्त: आधी temp फाईल पूर्ण लिहून fsync, मग `os.link` (नाव आधीच असेल तर FileExistsError ⇒ `_2`, `_3`…) — अर्धवट लिहिलेली
    फाईल अंतिम नावाने कधीच दिसत नाही, आणि जुनी फाईल कधीच overwrite नाही. रिटर्न (path, sha256)."""
    import tempfile
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        root, ext = os.path.splitext(path)
        p, n = path, 1
        while True:
            try:
                os.link(tmp, p)
                return p, sha256(data)
            except FileExistsError:
                n += 1
                p = f"{root}_{n}{ext}"
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def read_verified(path, expected_sha):
    """फाईल वाचून sha256 जुळतो याची खात्री (vision / Telegram ला तेच bytes). न जुळल्यास ValueError."""
    with open(path, "rb") as f:
        b = f.read()
    if sha256(b) != expected_sha:
        raise ValueError(f"sha256 जुळत नाही: {path}")
    return b
