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
    """trend नसताना (fail-closed) साधं कारण — engine चे शब्द (Q47, origin …) नाहीत. क्रम level_reaction.context_from_state सारखाच
    (origin तुटला → रचना उलट (rev) → parent correction → unclear). Origin धोक्यात (origin_risk) = फक्त context (Abhi B1) ⇒ हे कधीच
    no-entry कारण नाही."""
    ctx = ctx or {}
    tr = str(ctx.get("trend") or "UNKNOWN")
    if tr in ("UP", "DOWN"):
        if ctx.get("phase") == "origin_broken":
            return f"Daily {tr}, but the trend's starting point broke on a daily close"
        if ctx.get("structure_against"):
            return f"Daily {tr}, but the daily structure since the trend's last {'high' if tr == 'UP' else 'low'} turned against it"
        if ctx.get("counter") == "correction":
            return f"Daily {tr} is inside a bigger correction"
    if tr == "UNKNOWN":
        return "daily trend not available (no daily data)"
    return f"daily trend unclear ({trend_words(ctx)})"


def tf_word(zone_type):
    """"DYNAMIC_SR_RESISTANCE_60M" ⇒ "1H"; ओळखता नाही ⇒ "". "|" नंतरचा भाग = label (`zone_note`)."""
    tail = str(zone_type or "").split("|", 1)[0].rsplit("_", 1)[-1].upper()
    return TF_WORD.get(tail, "")


def zone_note(zone_type):
    """engine zone row चा label ("ENGINE_LEVEL_1H|confluence: Daily 22,725–22,810" ⇒ "confluence: Daily 22,725–22,810"); नाही ⇒ ""."""
    parts = str(zone_type or "").split("|", 1)
    return parts[1].strip() if len(parts) == 2 else ""


# ------------------------------------------------------------------------------------------------ पट्ट्याची रुंदी (Abhi: merged band — check)
# Setting `approval_band_warn_pts` (15M SRv2 = `15m_dynamic_sr` पान, cloud_db defaults): पट्टा यापेक्षा रुंद (points) ⇒ approval / pre-open /
# 15:45 सारांशात "⚠️ merged band — check" ओळ. फक्त दाखवणं — कुठलाही निर्णय / gate / order बदलत नाही. Default 150 (Abhi; OPEN_QUESTIONS).
BAND_WARN_KEY = "approval_band_warn_pts"
BAND_WARN_PTS_DEFAULT = 150


def band_warn_pts(value=None):
    """Setting ची किंमत ⇒ float (> 0). नाही / चुकीची ⇒ BAND_WARN_PTS_DEFAULT. settings dict दिली ⇒ त्यातली BAND_WARN_KEY."""
    if isinstance(value, dict):
        value = value.get(BAND_WARN_KEY)
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(BAND_WARN_PTS_DEFAULT)
    return v if v > 0 and v == v else float(BAND_WARN_PTS_DEFAULT)


def band_width(lo, hi):
    """|hi − lo| points; lo / hi नाहीत / आकडा नाही ⇒ None (कधीच raise नाही)."""
    try:
        lo, hi = float(lo), float(hi)
    except (TypeError, ValueError):
        return None
    w = abs(hi - lo)
    return w if w == w else None


def band_range(lo, hi):
    """"22,544–22,622 (78 pts)" — पट्टा नाही ⇒ ""."""
    w = band_width(lo, hi)
    if w is None:
        return ""
    lo, hi = sorted((float(lo), float(hi)))
    return f"{lo:,.0f}–{hi:,.0f} ({w:,.0f} pts)"


def band_flag(lo, hi, warn_pts=None):
    """पट्टा setting पेक्षा रुंद ⇒ "⚠️ merged band — check (width 312 pts > 150)"; नाहीतर / पट्टा नाही ⇒ ""."""
    w, lim = band_width(lo, hi), band_warn_pts(warn_pts)
    return f"⚠️ merged band — check (width {w:,.0f} pts > {lim:,.0f})" if w is not None and w > lim else ""


def band_wide_words(lo, hi, warn_pts=None):
    """pre-open / सारांशाच्या ओळींसाठी: "61 pts wide" किंवा "312 pts wide ⚠️ merged band — check (over 150 pts)"; पट्टा नाही ⇒ "".
    ">" नाही ⇒ HTML संदेशात escape लागत नाही."""
    w, lim = band_width(lo, hi), band_warn_pts(warn_pts)
    if w is None:
        return ""
    return f"{w:,.0f} pts wide" + (f" ⚠️ merged band — check (over {lim:,.0f} pts)" if w > lim else "")
