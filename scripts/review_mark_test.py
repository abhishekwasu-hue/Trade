"""scripts/review_mark_test.py — Abhi च्या चाचणी replies (खरे निकाल नाहीत) backtest_review मध्ये "test" म्हणून चिन्हांकित (delete नाही).

Default: आज (2026-10-09) 12:30–13:00 IST मधले replies, review_date 2026-10-06 / 07 / 08 (Abhi: 12:44 ला 08 OK, 07 OK, 06 WRONG).
आधी फक्त यादी (बदल नाही); --apply दिलं तरच बदल. Progress / मोजमाप item_type test वगळतं.

    python3 scripts/review_mark_test.py            # यादी
    python3 scripts/review_mark_test.py --apply    # चिन्हांकित
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backtest_review import store as BS       # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-10-06,2026-10-07,2026-10-08")
    ap.add_argument("--from-utc", default="2026-10-09 07:00", help="12:30 IST")
    ap.add_argument("--to-utc", default="2026-10-09 07:30", help="13:00 IST")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    rv = BS.load_reviews()
    ids = BS.test_candidates(rv, a.dates.split(","), a.from_utc, a.to_utc)
    for i in ids:
        print(f"  {i} · {rv[i]['review_date']} · {rv[i]['verdict']} · {rv[i]['reviewed_at']} UTC · {rv[i]['item_type']}")
    print(f"सापडले {len(ids)} (अपेक्षित 3)")
    if a.apply and ids:
        print("चिन्हांकित ✓" if BS.mark_test(ids) else "⚠️ DB update अयशस्वी")
    elif ids:
        print("बदल नाही — बरोबर असल्यास --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
