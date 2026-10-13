"""scripts/build_method_pack.py — `docs/knowledge/method_pack.md` (English Method Pack) KB मधून बनवतो (design §12.1). API call नाही.

    python3 scripts/build_method_pack.py            # pack लिहा + version / token अंदाज छापा
    python3 scripts/build_method_pack.py --check    # फक्त तपासा: commit केलेला pack KB शी जुळतो का (stale ⇒ exit 1)

KB हाच एकमेव स्रोत: KB मधले `<!-- pack:N key -->` blocks (N = 0–7, Abhi चा क्रम) + `ABHI_METHOD_NOTES.md` चे Entries (section 8).
KB / notes बदलले ⇒ हा script चालवून pack commit करा (`tests/test_method_pack.py` stale pack ला fail करतो).
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vision import method_pack as MP  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Method Pack generator (KB ⇒ docs/knowledge/method_pack.md)")
    ap.add_argument("--check", action="store_true", help="लिहू नका; commit केलेला pack stale असेल तर exit 1")
    ap.add_argument("--out", default=MP.PACK_PATH)
    a = ap.parse_args(argv)
    text, ver = MP.build_from_repo()
    tok = MP.tokens_estimate(text)
    bad = MP.banned_hits(text)
    print(f"Method Pack version {ver} · {len(text):,} chars · ≈ {tok:,} tokens (chars / 4; target {MP.TOKENS_MIN:,}–{MP.TOKENS_MAX:,})")
    if bad:
        print(f"⛔ pack मध्ये नसावेत असे शब्द: {bad}")
        return 1
    if not MP.TOKENS_MIN <= tok <= MP.TOKENS_MAX:
        print("⚠️ pack आकार target बाहेर")
    if a.check:
        try:
            cur = open(a.out, encoding="utf-8").read()
        except OSError:
            cur = ""
        if cur != text:
            print("⛔ method_pack.md stale — `python3 scripts/build_method_pack.py` चालवून commit करा")
            return 1
        print("✅ method_pack.md KB शी जुळतो")
        return 0
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"लिहिलं: {os.path.relpath(a.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
