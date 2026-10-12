"""scripts/reader2_gallery_export.py — Abhi ची gallery marking (Supabase `reader2_gallery`) ⇒ साध्या JSON files (एक chart = एक file).

🎓 VPS वर चालवा (DB connection VPS `.env` मधून; key कधीच print होत नाही). Output private trade-data `reader2_gallery/labels/<split>/<id>.json` — split
नेहमी manifest मधला. Bars असतील तर पूर्ण तपासणी (किंमत = bar चे टोक, holdout नाही), नाहीतर रचना-तपासणी. चुकीच्या नोंदी लिहिल्या जात
नाहीत (ids + कारण छापतो; किंमती नाहीत). CR4 चं CI हे files secrets शिवाय वाचतं; test folder फक्त acceptance साठी (sealed).

    python3 scripts/reader2_gallery_export.py [--out /root/trade-data/reader2_gallery/labels] [--from-dir <JSON store>]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gallery2 import data as GD            # noqa: E402
from gallery2 import store as GS           # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="default: READER2_GALLERY_LABELS किंवा <trade-data>/reader2_gallery/labels")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--from-dir", default=None, help="DB ऐवजी JSON store (READER2_GALLERY_STORE folder)")
    a = ap.parse_args(argv)
    m = GS.load_manifest(a.manifest)
    src = GS.DirStore(a.from_dir) if a.from_dir else GS.default_store()
    recs = src.load_all()
    out = a.out or GS.labels_dir()
    res = GS.export_json(recs, m, out, bars_for=GD.load_window)
    print(json.dumps({"store": src.describe(), "out": out, "read": len(recs), "dev": res["dev"], "test": res["test"],
                      "full_check": res["full_check"], "invalid": res["invalid"], "unknown": res["unknown"], "removed": res["removed"]},
                     ensure_ascii=False, indent=1))
    return 1 if res["invalid"] else 0


if __name__ == "__main__":
    sys.exit(main())
