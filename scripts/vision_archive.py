"""scripts/vision_archive.py — chart PNG + audit records private trade-data मध्ये (§11.5). रोज रात्री 23:45 नंतर.

    python3 scripts/vision_archive.py                       # marker नसलेले / अपूर्ण सगळे दिवस + मागचे 3 दिवस (records ताजे) → push → पडताळणी → marker
    python3 scripts/vision_archive.py --day 2026-10-08 --no-push
    python3 scripts/vision_archive.py --cleanup-only        # फक्त 90 दिवसांपेक्षा जुने local folders (पडताळलेला marker असेल तरच) + disk तपासणी

🎓 नियम:
  • Destination हा खरंच private trade-data checkout आहे याची आधी खात्री (`research/elliott_vps_data.check_repo`) — public repo मध्ये कधीच नाही.
  • स्रोत `data/visual_audit/YYYY-MM-DD/` (gitignored) → `trade-data/visual_audit/YYYY-MM/YYYY-MM-DD/`. PNG जशीच्या तशी (vision ला गेलेली मूळ),
    copy नंतर sha256 जुळतो याची खात्री; trade-data मध्ये त्या नावाची वेगळी फाईल असेल तर overwrite नाही (`_2`).
  • त्या दिवसाचे `vision_signals` records → `vision_records_<day>.jsonl` (path + sha256, prompt_version, model, JSON, tokens, cost, निर्णय, outcome).
  • कुठले दिवस: marker नसलेले किंवा marker नंतर बदललेले / नवीन फाईल असलेले (उदा. आधीचा push अयशस्वी, उशिरा आलेला outcome chart) + मागचे 3 दिवस
    (no_trade / outcome records ताजे करण्यासाठी).
  • Push: आधी `fetch origin main` + `rebase FETCH_HEAD` (मागच्या रात्रीचा न-push झालेला commit अडकू नये); नाकारला तर पुन्हा rebase करून retry.
    नंतर FETCH_HEAD मध्ये प्रत्येक फाईलचा blob id = local `hash-object` याची खात्री ⇒ तरच `.archived` marker ({नाव: sha256}).
  • Cleanup: 90 दिवसांपेक्षा जुना folder **फक्त** marker असेल आणि प्रत्येक local फाईलचा sha256 marker शी जुळत असेल तर delete.
  • Disk वापर > 80% ⇒ Telegram इशारा. PNG > 150 KB ⇒ यादी (इशारा; मूळ फाईल बदलत नाही).
  • trade-data clone: env `TRADE_DATA_DIR` (डीफॉल्ट /root/trade-data). Credentials कधीच print नाहीत (git चे स्वतःचे).
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research"))

from vision import images as IM  # noqa: E402
from vision import store as VS  # noqa: E402

MARKER = ".archived"
KEEP_DAYS = 90
RECENT_DAYS = 3
DISK_WARN_PCT = 80


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git(td, *args, check=True):
    r = subprocess.run(["git", "-C", td, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {args[0]} अयशस्वी: {r.stderr.strip()[:200]}")
    return r


def check_repo(td):
    from elliott_vps_data import check_repo as _check
    return _check(td)


def source_files(src):
    return {n: _sha(os.path.join(src, n)) for n in sorted(os.listdir(src))
            if n != MARKER and not n.startswith(".") and os.path.isfile(os.path.join(src, n))}


def read_marker(src):
    try:
        with open(os.path.join(src, MARKER), encoding="utf-8") as f:
            m = json.load(f)
        files = m.get("files") or {}
        return files if isinstance(files, dict) else {}
    except (OSError, ValueError):
        return None


def days_to_archive(src_base, today, explicit=None):
    """marker नसलेले / marker शी न जुळणारे दिवस + मागचे RECENT_DAYS दिवस (folder असेल तर)."""
    if explicit:
        return [str(explicit)]
    out = []
    for name in sorted(os.listdir(src_base)) if os.path.isdir(src_base) else []:
        try:
            d = datetime.date.fromisoformat(name)
        except ValueError:
            continue
        src = os.path.join(src_base, name)
        m = read_marker(src)
        if m is None or m != source_files(src) or (today - d).days < RECENT_DAYS:
            out.append(name)
    return out


def export_records(day, dst, path=None):
    rows = VS.list_signals(day, path)
    p = os.path.join(dst, f"vision_records_{day}.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return p, len(rows)


def copy_day(day, src_base, trade_data, db_path=None):
    """रिटर्न (dst, {repo-relative file: local src sha256 | None for records}, [मोठ्या PNG]) — src folder नसेल तर (None, {}, [])."""
    src = os.path.join(src_base, str(day))
    if not os.path.isdir(src):
        return None, {}, []
    dst = os.path.join(trade_data, "visual_audit", str(day)[:7], str(day))
    os.makedirs(dst, exist_ok=True)
    files, big = {}, []
    for name, s_sha in source_files(src).items():
        sp = os.path.join(src, name)
        if name.endswith(".png") and os.path.getsize(sp) > IM.MAX_KB * 1024:
            big.append(name)
        dp = os.path.join(dst, name)
        root, ext = os.path.splitext(name)
        n = 2
        while os.path.exists(dp) and _sha(dp) != s_sha:                 # वेगळी फाईल त्याच नावाने ⇒ overwrite नाही
            dp = os.path.join(dst, f"{root}_{n}{ext}")
            n += 1
        if not os.path.exists(dp):
            shutil.copy2(sp, dp)
        if _sha(dp) != s_sha:
            raise RuntimeError(f"copy नंतर sha256 जुळत नाही: {name}")
        files[os.path.relpath(dp, trade_data)] = (name, s_sha)
    rec, _ = export_records(day, dst, db_path)
    files[os.path.relpath(rec, trade_data)] = (None, None)
    return dst, files, big


def sync(trade_data):
    git(trade_data, "fetch", "-q", "origin", "main")
    git(trade_data, "rebase", "-q", "--autostash", "FETCH_HEAD")


def push_and_verify(trade_data, day, files, retries=4):
    rels = list(files)
    git(trade_data, "add", "--", *rels)
    if git(trade_data, "diff", "--cached", "--quiet", "--", *rels, check=False).returncode != 0:
        git(trade_data, "commit", "-q", "-m", f"visual_audit {day}: vision charts + records", "--", *rels)
    delay = 2
    for k in range(retries + 1):
        r = git(trade_data, "push", "-q", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            break
        if k == retries:
            raise RuntimeError(f"push अयशस्वी: {r.stderr.strip()[:200]}")
        time.sleep(delay)
        delay *= 2
        try:
            sync(trade_data)                                             # remote पुढे गेला असेल ⇒ rebase करून पुन्हा
        except RuntimeError:
            pass
    git(trade_data, "fetch", "-q", "origin", "main")
    out = git(trade_data, "ls-tree", "-r", "-z", "FETCH_HEAD", "--", os.path.join("visual_audit", str(day)[:7], str(day))).stdout
    remote = {}
    for ent in filter(None, out.split("\0")):
        meta, _, p = ent.partition("\t")
        remote[p] = meta.split()[2]
    bad = [f for f in rels if remote.get(f) != git(trade_data, "hash-object", "--", f).stdout.strip()]
    if bad:
        raise RuntimeError(f"push नंतर remote मध्ये नाहीत / वेगळ्या: {bad[:5]}")
    return git(trade_data, "rev-parse", "FETCH_HEAD").stdout.strip()


def write_marker(src_base, day, commit, files):
    """{local नाव: sha256} — फक्त पडताळलेल्या (remote मध्ये असलेल्या) फाईल्स."""
    m = {name: s for name, s in files.values() if name}
    with open(os.path.join(src_base, str(day), MARKER), "w", encoding="utf-8") as f:
        json.dump({"commit": commit, "files": m, "ts": str(VS.now_ist())}, f, ensure_ascii=False)


def cleanup(src_base, today, keep_days=KEEP_DAYS):
    """रिटर्न (deleted, skipped). Marker नसेल / कुठलीही local फाईल marker च्या sha256 शी जुळत नसेल ⇒ delete नाही."""
    deleted, skipped = [], []
    if not os.path.isdir(src_base):
        return deleted, skipped
    cutoff = today - datetime.timedelta(days=keep_days)
    for name in sorted(os.listdir(src_base)):
        try:
            d = datetime.date.fromisoformat(name)
        except ValueError:
            continue
        if d >= cutoff:
            continue
        folder = os.path.join(src_base, name)
        m = read_marker(folder)
        if m is None:
            skipped.append((name, "marker नाही (trade-data push पक्की नाही)"))
            continue
        local = source_files(folder)
        diff = [n for n, s in local.items() if m.get(n) != s]
        if diff:
            skipped.append((name, f"marker शी न जुळणाऱ्या फाईल्स: {diff[:3]}"))
            continue
        shutil.rmtree(folder)
        deleted.append(name)
    return deleted, skipped


def disk_pct(p):
    u = shutil.disk_usage(p if os.path.exists(p) else "/")
    return 100.0 * u.used / u.total


def main(argv=None, send_text=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None)
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA_DIR", "/root/trade-data"))
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--cleanup-only", action="store_true")
    ap.add_argument("--keep-days", type=int, default=KEEP_DAYS)
    a = ap.parse_args(argv)
    if send_text is None:
        from notifications import send_telegram_message as send_text
    src_base = IM.base_dir()
    today = VS.now_ist().date()
    rc = 0
    if not a.cleanup_only:
        try:
            check_repo(a.trade_data)
            if not a.no_push:
                sync(a.trade_data)
            for day in days_to_archive(src_base, today, a.day):
                dst, files, big = copy_day(day, src_base, a.trade_data)
                if dst is None:
                    continue
                print(f"{day}: {len(files)} फाईल्स → {dst}")
                if big:
                    print(f"⚠️ {len(big)} PNG > {IM.MAX_KB} KB: {big[:5]}")
                if not a.no_push:
                    commit = push_and_verify(a.trade_data, day, files)
                    write_marker(src_base, day, commit, files)
                    print(f"✅ {day}: trade-data push पक्की ({commit[:10]}), marker लिहिला")
        except Exception as exc:
            rc = 1
            print(f"❌ archive अयशस्वी: {exc}")
            send_text(f"⚠️ <b>Vision archive</b>: trade-data push अयशस्वी — local images ठेवल्या आहेत (delete नाही). {str(exc)[:200]}")
    deleted, skipped = cleanup(src_base, today, a.keep_days)
    print(f"cleanup: deleted {deleted}, skipped {len(skipped)}")
    pct = disk_pct(src_base)
    print(f"disk {pct:.1f}%")
    if pct > DISK_WARN_PCT:
        send_text(f"⚠️ <b>VPS disk {pct:.0f}%</b> (> {DISK_WARN_PCT}%) — visual_audit / logs तपासा.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
