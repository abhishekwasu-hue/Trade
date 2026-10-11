#!/usr/bin/env python3
"""🗓 PAPER दिवस-सारांश (Abhi §10e, 15:45 IST): approvals, ✏️ modifications, ❌ rejections (कारणानुसार), 📝 corrections, approved trades
चा net P&L वि. would-have नोंदी + level bots चा gate सारांश (L5 §5: armed / confirmed / ignored कारणानुसार) ⇒ एकच Telegram संदेश.
फक्त वाचन (vision.db + paper journal + signal_log) — order / settings ला हात नाही. Dry-run नोंदी वगळून.

VPS cron (VPS ची वेळ UTC ⇒ 15:45 IST = 10:15 UTC; crontab या script मधून बदलत नाही — Abhi स्वतः जोडतो):
  15 10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/paper_daily_summary.py >> paper_daily_summary.log 2>&1
"""
import argparse
import html
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TG_MAX = 4096                                                              # Telegram एका संदेशाची कमाल लांबी


def level_section(day):
    """L5 (Abhi §5): bot-निहाय level gate सारांश (armed / confirmed / ignored कारणानुसार + touch-legacy). कधीच raise नाही ⇒ "NA (कारण)"."""
    try:
        from bots_common import level_visibility as LV
        return LV.summary_text(day)
    except Exception as exc:                                               # noqa: BLE001 — approval सारांश तरी जावा
        return f"🎯 Level bots — confirmation gate: NA ({html.escape(type(exc).__name__)}: {html.escape(str(exc)[:80])})"


def combine(approvals, gate, limit=TG_MAX):
    """एकच संदेश ≤ limit: approvals भाग कधीच कापत नाही; जागा कमी ⇒ gate भाग ओळी-निहाय कापतो (HTML tag अर्धवट राहू नये) + "…"."""
    text = approvals + "\n\n" + gate
    if len(text) <= limit:
        return text
    room = limit - len(approvals) - 2 - len("\n…")
    keep = []
    for ln in gate.split("\n"):
        if len("\n".join(keep + [ln])) > room:
            break
        keep.append(ln)
    return approvals + ("\n\n" + "\n".join(keep) + "\n…" if keep else "")


def main(argv=None, send=None, level=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (default: आज, IST)")
    ap.add_argument("--print", dest="print_only", action="store_true", help="Telegram नाही, फक्त छाप")
    a = ap.parse_args(argv)
    from vision import approval as AP
    text = AP.daily_summary_text(a.day)
    day = a.day or AP.VS.now_ist().strftime("%Y-%m-%d")                     # daily_summary सारखाच दिवस (IST)
    text = combine(text, (level or level_section)(day))                    # एकाच Telegram संदेशात दोन्ही (≤ 4096)
    print(text)
    if a.print_only:
        return 0
    if send is None:
        from notifications import send_telegram_message as send
    try:
        ok = send(text)
    except Exception as exc:
        print(f"⚠️ सारांश Telegram वर गेला नाही: {type(exc).__name__}: {exc}")
        return 1
    if ok is False:                                                        # send_telegram_message raise करत नाही, False देतो
        print("⚠️ सारांश Telegram वर गेला नाही (send False)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
