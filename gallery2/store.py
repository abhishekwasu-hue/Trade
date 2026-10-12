"""gallery2/store.py — gallery marking ची साठवण, JSON export आणि sealed test split चा पहारा.

🎓 रचना (repo मधला Abhi-label pattern — `backtest_review/store.py` चे `backtest_review` / `golden_gallery` tables सारखाच):
  • **Primary = Supabase table `reader2_gallery`** (एक chart = एक row, JSON payload, upsert, `revision` वाढतो). VPS वरचा dashboard
    आधीच `cloud_db.get_connection` (VPS `.env`) वापरतो ⇒ Abhi ने केलेली marking VPS rebuild / redeploy नंतरही टिकते, कोणत्याही device
    वरून दिसते. अपयश ⇒ False (raise नाही; page कारण दाखवतो). Writes फक्त या table मध्ये — bot / orders ला हात नाही.
  • **पर्याय = JSON folder** (`READER2_GALLERY_STORE=/path/to/dir`): DB नसताना / tests साठी — त्याच format मध्ये.
  • **Export** (`scripts/reader2_gallery_export.py`, VPS वर): DB ⇒ `gallery2/data/labels/<split>/<id>.json` (एक chart = एक साधी JSON
    file). CR4 चं CI हे files secrets शिवाय वाचतं (public repo मध्ये फक्त labels — candles नाहीत; golden_chart_cases सारखं).
  • **Sealed test split:** `load_labels(..., purpose="calibration")` फक्त `labels/dev/` उघडतो (आणि फक्त `calibration: true` charts);
    manifest मध्ये test असलेला chart dev folder मध्ये सापडला ⇒ `SealedTestError`. Test labels फक्त purpose="acceptance".
"""
import json
import os

import pandas as pd

from . import schema as SC

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "data", "manifest.json")
LABELS_DIR = os.path.join(HERE, "data", "labels")
TABLE = "reader2_gallery"
CREATE_SQL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
    chart_id TEXT PRIMARY KEY, split TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, payload TEXT NOT NULL,
    marker TEXT, marked_at TIMESTAMP NOT NULL, revision INTEGER NOT NULL DEFAULT 1);"""
PURPOSES = ("calibration", "dev_report", "acceptance")


class SealedTestError(RuntimeError):
    """Test split चे labels calibration / dev मार्गात आले (spec §5: test sealed, फक्त acceptance)."""


# ---------------------------------------------------------------------------------------------------------------- manifest
def manifest_path():
    return os.environ.get("READER2_GALLERY_MANIFEST") or MANIFEST


def load_manifest(path=None):
    with open(path or manifest_path(), encoding="utf-8") as fh:
        return json.load(fh)


def charts(manifest):
    return {c["id"]: c for c in manifest.get("charts", [])}


# ---------------------------------------------------------------------------------------------------------------- stores
def _dumps(rec):
    return json.dumps(rec, ensure_ascii=False, indent=1)


class DbStore:
    """Supabase `reader2_gallery` (cloud_db). `conn_factory` फक्त tests साठी."""
    kind = "db"

    def __init__(self, conn_factory=None):
        self.cf = conn_factory

    def describe(self):
        return f"Supabase table `{TABLE}`"

    def _run(self, work):
        from opportunity_engine import store as OS             # lazy: import वर DB नाही
        return OS._run(self.cf, work)

    def save(self, rec):
        row = (rec["id"], rec["split"], rec["symbol"], rec["timeframe"], _dumps(rec), rec.get("marker"),
               pd.Timestamp(rec["marked_at"]).to_pydatetime())

        def work(cur):
            cur.execute(CREATE_SQL)
            cur.execute(f"""INSERT INTO {TABLE} (chart_id, split, symbol, timeframe, payload, marker, marked_at, revision)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                            ON CONFLICT (chart_id) DO UPDATE SET split = EXCLUDED.split, payload = EXCLUDED.payload,
                            marker = EXCLUDED.marker, marked_at = EXCLUDED.marked_at, revision = {TABLE}.revision + 1""", row)
        return bool(self._run(work))

    def load_all(self):
        """{chart_id: record} — marking page / export साठी (calibration इथून कधीच वाचत नाही)."""
        out = {}

        def work(cur):
            cur.execute(CREATE_SQL)
            cur.execute(f"SELECT chart_id, payload, revision FROM {TABLE}")
            for cid, payload, rev in cur.fetchall():
                rec = json.loads(payload)
                rec["revision"] = int(rev)
                out[cid] = rec
            return out
        return out if self._run(work) else {}


class DirStore:
    """`<root>/<split>/<id>.json` — export चाच format."""
    kind = "dir"

    def __init__(self, root):
        self.root = root

    def describe(self):
        return f"JSON folder `{self.root}`"

    def path(self, rec):
        return os.path.join(self.root, rec["split"], f"{rec['id']}.json")

    def save(self, rec):
        try:
            for sp in SC.SPLITS:                                    # split बदलला (manifest पुन्हा बनवला) ⇒ जुनी प्रत काढा
                old = os.path.join(self.root, sp, f"{rec['id']}.json")
                if sp != rec["split"] and os.path.exists(old):
                    os.remove(old)
            p = self.path(rec)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(_dumps(rec) + "\n")
            os.replace(tmp, p)
            return True
        except OSError:
            return False

    def load_all(self):
        out = {}
        for sp in SC.SPLITS:
            d = os.path.join(self.root, sp)
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.endswith(".json"):
                    with open(os.path.join(d, f), encoding="utf-8") as fh:
                        rec = json.load(fh)
                    out[rec["id"]] = rec
        return out


def default_store():
    """env `READER2_GALLERY_STORE`: रिकामं / "db" ⇒ Supabase; बाकी ⇒ JSON folder path."""
    v = (os.environ.get("READER2_GALLERY_STORE") or "db").strip()
    return DbStore() if v.lower() == "db" else DirStore(v)


def save_record(store, rec, cand, bars=None):
    """तपासून जतन. चुका ⇒ ValueError (सगळ्या चुका एका संदेशात); साठवण अपयश ⇒ False."""
    err = SC.validate(rec, cand, bars)
    if err:
        raise ValueError("; ".join(err))
    return store.save(rec)


def progress(manifest, records):
    """{"marked": n, "total": N, "dev": (n, N), "test": (n, N)} — manifest मधले charts ज्यांना ≥ 1 leg आहे."""
    cs = charts(manifest)
    done = {k for k, r in records.items() if k in cs and r.get("legs")}
    by = {sp: (sum(1 for k in done if cs[k]["split"] == sp), sum(1 for c in cs.values() if c["split"] == sp)) for sp in SC.SPLITS}
    return {"marked": len(done), "total": len(cs), **by}


# ---------------------------------------------------------------------------------------------------------------- export / sealed load
def export_json(records, manifest, out_dir=LABELS_DIR, bars_for=None):
    """records (DB मधून) ⇒ `<out_dir>/<split>/<id>.json`; split नेहमी **manifest** मधला. `bars_for(cand)` (ऐच्छिक) ⇒ पूर्ण तपासणी;
    bars मिळाले नाहीत ⇒ रचना-तपासणी. रिटर्न सारांश (फक्त आकडे / ids — किंमती नाहीत)."""
    cs = charts(manifest)
    out = {"dev": 0, "test": 0, "invalid": {}, "unknown": [], "full_check": 0}
    target = DirStore(out_dir)
    for cid, rec in sorted(records.items()):
        cand = cs.get(cid)
        if cand is None:
            out["unknown"].append(cid)
            continue
        rec = {k: v for k, v in rec.items() if k != "revision"}
        bars = None
        if bars_for is not None:
            try:
                bars = bars_for(cand)
                out["full_check"] += 1
            except Exception:                                       # data नाही ⇒ रचना-तपासणी पुरे
                bars = None
        err = SC.validate(rec, cand, bars)
        if err:
            out["invalid"][cid] = err
            continue
        target.save(rec)
        out[cand["split"]] += 1
    return out


def load_labels(manifest, purpose, labels_dir=LABELS_DIR):
    """Export केलेले labels. purpose:
      calibration ⇒ फक्त dev + `calibration: true` (Abhi चे आधीचे / contaminated charts वगळून) — test folder कधीच उघडत नाही;
      dev_report  ⇒ सगळे dev (regression / अहवाल);
      acceptance  ⇒ फक्त test (sealed — शेवटच्या acceptance साठीच)."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} — {PURPOSES} पैकी")
    split = "test" if purpose == "acceptance" else "dev"
    cs = charts(manifest)
    d = os.path.join(labels_dir, split)
    out = {}
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        cid = f[:-5]
        cand = cs.get(cid)
        if cand is None:
            continue
        if cand["split"] != split:
            raise SealedTestError(f"{cid}: manifest split {cand['split']} पण {split}/ folder मध्ये — test labels sealed")
        if purpose == "calibration" and not cand.get("calibration", True):
            continue
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            rec = json.load(fh)
        if rec.get("split") != split or rec.get("id") != cid:
            raise SealedTestError(f"{cid}: file मधला split / id ({rec.get('split')}, {rec.get('id')}) folder शी जुळत नाही")
        out[cid] = rec
    return out


def calibration_labels(manifest, labels_dir=LABELS_DIR):
    """Calibration (CR4+) चा **एकमेव** मार्ग: dev labels फक्त. Test split कधीच नाही."""
    return load_labels(manifest, "calibration", labels_dir)
