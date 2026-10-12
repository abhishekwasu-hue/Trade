"""bots_common/plain_text.py — Telegram वर जाणाऱ्या प्रत्येक chart / सारांशाचा "साधा" वरचा भाग (Abhi, TELEGRAM_CLEANUP 3).

रचना (सगळे senders सारखेच):
  ओळ 1  = एक साधी English ओळ: Abhi ने chart वर काय पाहायचं (engine codes नाहीत).
  ओळ 2  = "Decision needed: approve / reject" किंवा "Decision needed: none — information" (किंवा review ✔ / ✘).
  SEP   = "── details ──" — याच्या खाली engine चे raw codes (K leg, a:D2+b, sweep, Q44, pb candle, ★ …), जसे आधी होते.
फक्त wording — कुठलाही निर्णय इथे बदलत नाही.
"""
import re

SEP = "── details ──"
DECISION_APPROVE = "Decision needed: approve / reject"
DECISION_NONE = "Decision needed: none — information"
DECISION_REVIEW = "Decision needed: reply ✔ (engine right) or ✘ + reason (engine wrong)"

# वरच्या (साध्या) भागात नसावेत असे engine codes — tests हेच वापरतात
RAW_CODES = re.compile(
    r"(\bK\s*(leg|line|रेघ)\b|\ba:D\d?|\bD\d\+|\+[abc]\b|\bsweeps?\b|\bQ\d{1,3}\b|\bpb candle\b|★|[①②③④⑤⑥⑦]|\bATR\b|\bc0\b|\bc1\b|\ba2\b"
    r"|\bCHoCH\b|\bno touch\b|\bL\d+\b|\bwxy\b|\bconf(?:idence)?\s*\d)", re.I)

TF_WORD = {"1M": "1-min", "5M": "5-min", "15M": "15-min", "30M": "30-min", "60M": "1H", "1H": "1H", "D": "daily", "1D": "daily"}


MARGIN = 8                                                                 # Telegram मर्यादेखाली थोडी जागा (entities / rounding)


def tg_len(s):
    """Telegram मर्यादा UTF-16 code units मध्ये मोजतो (emoji = 2) — Python len नाही."""
    return len(str(s or "").encode("utf-16-le")) // 2


def tg_cut(s, units):
    """UTF-16 units ≤ units इतका सर्वात लांब prefix (surrogate pair मधे कापत नाही)."""
    out, n = [], 0
    for ch in str(s or ""):
        w = 2 if ord(ch) > 0xFFFF else 1
        if n + w > units:
            break
        out.append(ch)
        n += w
    return "".join(out)


def compose(head, decision, details="", limit=None):
    """head + decision + SEP + details. limit (उदा. Telegram caption 1024, UTF-16 units) ⇒ MARGIN ठेवून फक्त details कापतो (वरचा भाग
    कधीच नाही, तो एकटाच मोठा असेल तरच)."""
    top = f"{head}\n{decision}"
    eff = None if not limit else int(limit) - MARGIN
    details = str(details or "").strip("\n")
    if not details:
        return tg_cut(top, eff) if eff and tg_len(top) > eff else top
    text = f"{top}\n{SEP}\n{details}"
    if eff and tg_len(text) > eff:
        room = eff - tg_len(top) - tg_len(SEP) - 3                            # दोन newlines + "…"
        if room <= 0:
            return tg_cut(top, eff)
        cut = tg_cut(details, room)
        if "<" in cut and cut.rfind("<") > cut.rfind(">"):                    # अर्धवट HTML tag नको
            cut = cut[:cut.rfind("<")]
        text = f"{top}\n{SEP}\n{cut.rstrip()}…"
    return text


def first_part(text):
    """SEP च्या आधीचा (साधा) भाग."""
    return str(text or "").split(SEP, 1)[0]


def has_raw_codes(text):
    return bool(RAW_CODES.search(str(text or "")))


def pts(x):
    """अंतर points मध्ये (≈, स्वल्पविरामासह)."""
    return f"≈{abs(float(x)):,.0f} pts"


def num(x):
    return f"{float(x):,.0f}"


def trend_words(ctx):
    """trend context (bots_common.level_reaction) ⇒ "Daily DOWN" / "Daily RANGE 22,400–22,900"."""
    tr = str((ctx or {}).get("trend") or "UNKNOWN")
    if tr == "RANGE" and ctx.get("band"):
        b = ctx["band"]
        return f"Daily RANGE {float(b[0]):,.0f}–{float(b[1]):,.0f}"
    return f"Daily {tr}"


def unclear_words(ctx):
    """trend नसताना (fail-closed) साधं कारण — engine चे शब्द (Q47, origin …) नाहीत."""
    ctx = ctx or {}
    tr = str(ctx.get("trend") or "UNKNOWN")
    if tr in ("UP", "DOWN"):
        if ctx.get("phase") == "origin_broken":
            return f"Daily {tr}, but the trend's starting point broke on a daily close"
        if ctx.get("origin_risk"):
            return f"Daily {tr}, but price is back at the trend's starting point"
        if ctx.get("counter") == "correction":
            return f"Daily {tr} is inside a bigger correction"
    if tr == "UNKNOWN":
        return "daily trend not available (no daily data)"
    return f"daily trend unclear ({trend_words(ctx)})"


def tf_word(zone_type):
    """"DYNAMIC_SR_RESISTANCE_60M" ⇒ "1H"; ओळखता नाही ⇒ ""."""
    tail = str(zone_type or "").rsplit("_", 1)[-1].upper()
    return TF_WORD.get(tail, "")
