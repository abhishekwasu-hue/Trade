"""gallery2/store.py — gallery marking ची साठवण, JSON export आणि sealed test split चा पहारा.

🎓 रचना (repo मधला Abhi-label pattern — `backtest_review/store.py` चे `backtest_review` / `golden_gallery` tables सारखाच):
  • **Primary = Supabase table `reader2_gallery`** (एक chart = एक row, JSON payload, `revision`). VPS वरचा dashboard आधीच
    `cloud_db.get_connection` (VPS `.env`) वापरतो ⇒ Abhi ने केलेली marking VPS rebuild / redeploy नंतरही टिकते, कोणत्याही device वरून
    दिसते. Writes फक्त या table मध्ये — bot / orders ला हात नाही.
  • **Optimistic lock:** `save(rec, expected_revision)` — नवा chart फक्त row नसेल तर insert; edit फक्त `revision` अजून तोच असेल तर
    (`UPDATE … WHERE chart_id AND revision AND split`) ⇒ दुसऱ्या tab / device ने मधेच जतन केलं ⇒ `ConflictError` (lost update नाही).
    Split कधीच बदलत नाही (test chart कधीच dev होत नाही). वाचन अपयश ⇒ `StoreError` (रिकामं {} नाही ⇒ page Save बंद ठेवतो).
  • **पर्याय = JSON folder** (`READER2_GALLERY_STORE=/path/to/dir`): DB नसताना / tests साठी — त्याच format मध्ये, तोच lock.
  • **Export** (`scripts/reader2_gallery_export.py`, VPS वर): DB ⇒ private trade-data `reader2_gallery/labels/<split>/<id>.json` (एक chart =
    एक साधी JSON file; env `READER2_GALLERY_LABELS` आधी). Repo public ⇒ labels repo मध्ये कधीच नाहीत (Abhi नियम: private storage).
    लिहिणं अपयशी ⇒ raise; manifest / DB मध्ये नसलेल्या charts च्या जुन्या files (फक्त labels folder मध्ये) काढतो.
  • **Sealed test split:** `load_labels(..., purpose="calibration")` फक्त `labels/dev/` उघडतो (आणि फक्त `calibration: true` charts);
    manifest मध्ये test असलेला chart dev folder मध्ये सापडला ⇒ `SealedTestError`. Test labels फक्त purpose="acceptance".
"""
import json
import os

import pandas as pd

from . import data as GD
from . import schema as SC

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "data", "manifest.json")
TABLE = "reader2_gallery"
CREATE_SQL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
    chart_id TEXT PRIMARY KEY, split TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, payload TEXT NOT NULL,
    marker TEXT, marked_at TIMESTAMP NOT NULL, revision INTEGER NOT NULL DEFAULT 1);"""
PURPOSES = ("calibration", "dev_report", "acceptance")


class SealedTestError(RuntimeError):
    """Test split चे labels calibration / dev मार्गात आले (spec §5: test sealed, फक्त acceptance)."""


class ConflictError(RuntimeError):
    """जतन करताना साठवलेली revision / split वेगळी (दुसऱ्या tab / device ने बदललं) — पुन्हा उघडून मग जतन."""


class StoreError(RuntimeError):
    """साठवण वाचता / लिहिता आली नाही (DB connection / folder)."""


class LabelsMissing(FileNotFoundError):
    """Export केलेल्या labels चा folder नाही."""


def labels_dir():
    """Labels folder (call वेळी): env `READER2_GALLERY_LABELS`, नाहीतर `<trade-data>/reader2_gallery/labels` (private)."""
    return os.environ.get("READER2_GALLERY_LABELS") or os.path.join(GD.trade_data_dir(), "reader2_gallery", "labels")


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


def _payload(rec):
    return {k: v for k, v in rec.items() if k != "revision"}


class DbStore:
    """Supabase `reader2_gallery` (cloud_db). `conn_factory` फक्त tests साठी. CREATE TABLE एका process मध्ये एकदाच."""
    kind = "db"
    _ready_default = False                                          # खऱ्या DB साठी process-wide

    def __init__(self, conn_factory=None):
        self.cf = conn_factory
        self._ready = False

    def describe(self):
        return f"Supabase table `{TABLE}`"

    def _ensure(self, cur):
        if self.cf is None:
            if not DbStore._ready_default:
                cur.execute(CREATE_SQL)
                DbStore._ready_default = True
        elif not self._ready:
            cur.execute(CREATE_SQL)
            self._ready = True

    def _run(self, work):
        from opportunity_engine import store as OS             # lazy: import वर DB नाही
        return OS._run(self.cf, work)

    def save(self, rec, expected_revision=0):
        """True = जतन; ConflictError = revision / split बदललेली; StoreError = DB अपयश."""
        exp = int(expected_revision or 0)
        row = (rec["id"], rec["split"], rec["symbol"], rec["timeframe"], _dumps(_payload(rec)), rec.get("marker"),
               pd.Timestamp(rec["marked_at"]).to_pydatetime())

        def work(cur):
            self._ensure(cur)
            if exp == 0:
                cur.execute(f"""INSERT INTO {TABLE} (chart_id, split, symbol, timeframe, payload, marker, marked_at, revision)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, 1) ON CONFLICT (chart_id) DO NOTHING""", row)
            else:
                cur.execute(f"""UPDATE {TABLE} SET payload = %s, marker = %s, marked_at = %s, revision = revision + 1
                                WHERE chart_id = %s AND revision = %s AND split = %s""",
                            (row[4], row[5], row[6], rec["id"], exp, rec["split"]))
            return "ok" if cur.rowcount == 1 else "conflict"
        res = self._run(work)
        if res == "conflict":
            raise ConflictError(f"{rec['id']}: साठवलेली marking बदलली आहे (अपेक्षित revision {exp}) किंवा split वेगळा — पुन्हा उघडा")
        if res != "ok":
            raise StoreError(f"{rec['id']}: Supabase मध्ये जतन झालं नाही (connection / log पाहा)")
        return True

    def load_all(self):
        """{chart_id: record (+ revision)} — marking page / export साठी (calibration इथून कधीच वाचत नाही). अपयश ⇒ StoreError."""
        out = {}

        def work(cur):
            self._ensure(cur)
            cur.execute(f"SELECT chart_id, payload, revision FROM {TABLE}")
            for cid, payload, rev in cur.fetchall():
                rec = json.loads(payload)
                rec["revision"] = int(rev)
                out[cid] = rec
            return out
        if self._run(work) is False:
            raise StoreError("Supabase `reader2_gallery` वाचता आलं नाही (connection नाही / चूक — log पाहा)")
        return out


def _write(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(_dumps(rec) + "\n")
    os.replace(tmp, path)


class DirStore:
    """`<root>/<split>/<id>.json` — export चाच format (+ `revision`)."""
    kind = "dir"

    def __init__(self, root):
        self.root = root

    def describe(self):
        return f"JSON folder `{self.root}`"

    def path(self, rec):
        return os.path.join(self.root, rec["split"], f"{rec['id']}.json")

    def _current(self, cid):
        for sp in SC.SPLITS:
            p = os.path.join(self.root, sp, f"{cid}.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as fh:
                    return sp, int(json.load(fh).get("revision", 1))
        return None, 0

    def save(self, rec, expected_revision=0):
        exp = int(expected_revision or 0)
        try:
            sp, cur = self._current(rec["id"])
            if cur != exp or (sp is not None and sp != rec["split"]):
                raise ConflictError(f"{rec['id']}: साठवलेली revision {cur} ({sp}) ≠ अपेक्षित {exp} ({rec['split']}) — पुन्हा उघडा")
            _write(self.path(rec), {**_payload(rec), "revision": exp + 1})
        except (OSError, ValueError) as exc:
            raise StoreError(f"{rec['id']}: folder मध्ये जतन झालं नाही: {exc}") from exc
        return True

    def load_all(self):
        out = {}
        try:
            for sp in SC.SPLITS:
                d = os.path.join(self.root, sp)
                if not os.path.isdir(d):
                    continue
                for f in sorted(os.listdir(d)):
                    if f.endswith(".json"):
                        with open(os.path.join(d, f), encoding="utf-8") as fh:
                            rec = json.load(fh)
                        rec.setdefault("revision", 1)
                        out[rec["id"]] = rec
        except (OSError, ValueError) as exc:
            raise StoreError(f"{self.root} वाचता आलं नाही: {exc}") from exc
        return out


_DEFAULT = {}


def default_store():
    """env `READER2_GALLERY_STORE`: रिकामं / "db" ⇒ Supabase; बाकी ⇒ JSON folder path. (एका process मध्ये एकच DbStore.)"""
    v = (os.environ.get("READER2_GALLERY_STORE") or "db").strip()
    if v.lower() == "db":
        return _DEFAULT.setdefault("db", DbStore())
    return DirStore(v)


def split_mismatch(rec, cand):
    """साठवलेल्या नोंदीचा split manifest पेक्षा वेगळा ⇒ कारण (str), नाहीतर None. अशी नोंद पुन्हा जतन होत नाही."""
    if rec and cand and rec.get("split") != cand.get("split"):
        return (f"{cand['id']}: साठवलेली marking split '{rec.get('split')}' पण manifest '{cand.get('split')}' — manifest बदललं? "
                "ही नोंद नव्या split खाली जतन होणार नाही (Abhi / lead ने ठरवावं)")
    return None


def save_record(store, rec, cand, bars=None, expected_revision=0):
    """तपासून जतन. चुका ⇒ ValueError (सगळ्या एका संदेशात); revision / split बदल ⇒ ConflictError; साठवण अपयश ⇒ StoreError."""
    err = SC.validate(rec, cand, bars)
    if err:
        raise ValueError("; ".join(err))
    return store.save(rec, expected_revision)


def seeds_dir():
    """Abhi-provided seed labels (उदा. निर्णय-फाइलमधले legs) — private `<trade-data>/reader2_gallery/seeds/<split>/<id>.json`
    (DirStore format). env `READER2_GALLERY_SEEDS` आधी. Labels export च्या folder पासून वेगळा (export जुन्या files काढतो)."""
    return os.environ.get("READER2_GALLERY_SEEDS") or os.path.join(GD.trade_data_dir(), "reader2_gallery", "seeds")


def import_seeds(store, manifest, seeds_root=None, bars_for=None, dry_run=False):
    """Seed नोंदी ⇒ `store` (VPS वर DB). फक्त ज्या chart ला अजून नोंद **नाही** तिथे (expected_revision 0 ⇒ Abhi ची आधीची marking कधीच
    overwrite होत नाही). प्रत्येक seed `save_record` ने तपासला जातो (manifest id / split / window, bars असतील तर किंमती). रिटर्न
    {"imported": [ids], "skipped_existing": [ids], "unknown": [ids], "invalid": {id: [चुका]}, "failed": {id: कारण}} — किंमती नाहीत.
    एका chart चं जतन अपयशी (ConflictError — मधेच दुसरी नोंद / StoreError) ⇒ `failed` मध्ये नोंद, बाकी seeds चालू राहतात."""
    root = seeds_root or seeds_dir()
    seeds = DirStore(root).load_all() if os.path.isdir(root) else {}
    have = store.load_all()
    cs = charts(manifest)
    out = {"imported": [], "skipped_existing": [], "unknown": [], "invalid": {}, "failed": {}}
    for cid, rec in sorted(seeds.items()):
        cand = cs.get(cid)
        if cand is None:
            out["unknown"].append(cid)
            continue
        if cid in have:
            out["skipped_existing"].append(cid)
            continue
        rec = _payload(rec)
        bars = None
        if bars_for is not None:
            try:
                bars = bars_for(cand)
            except Exception:                                       # data नाही ⇒ रचना-तपासणी
                bars = None
        err = SC.validate(rec, cand, bars)
        if err:
            out["invalid"][cid] = err
            continue
        if not dry_run:
            try:
                store.save(rec, 0)
            except (ConflictError, StoreError) as exc:
                out["failed"][cid] = f"{type(exc).__name__}: {exc}"
                continue
        out["imported"].append(cid)
    return out


def progress(manifest, records):
    """{"marked": n, "total": N, "dev": (n, N), "test": (n, N)} — manifest मधले charts ज्यांना ≥ 1 leg आहे."""
    cs = charts(manifest)
    done = {k for k, r in records.items() if k in cs and r.get("legs")}
    by = {sp: (sum(1 for k in done if cs[k]["split"] == sp), sum(1 for c in cs.values() if c["split"] == sp)) for sp in SC.SPLITS}
    return {"marked": len(done), "total": len(cs), **by}


# ---------------------------------------------------------------------------------------------------------------- export / sealed load
def export_json(records, manifest, out_dir=None, bars_for=None):
    """records (DB मधून) ⇒ `<out_dir>/<split>/<id>.json`; split नेहमी **manifest** मधला. `bars_for(cand)` (ऐच्छिक) ⇒ पूर्ण तपासणी;
    bars मिळाले नाहीत ⇒ रचना-तपासणी. लिहिणं अपयशी ⇒ StoreError. Manifest / DB मध्ये नसलेल्या किंवा चुकीच्या split folder मधल्या जुन्या
    `<split>/*.json` files काढतो — फक्त out_dir च्या आत (अवैध नोंदीची आधीची export तशीच राहते). रिटर्न सारांश (ids / आकडे — किंमती नाहीत)."""
    out_dir = out_dir or labels_dir()
    cs = charts(manifest)
    out = {"dev": 0, "test": 0, "invalid": {}, "unknown": [], "full_check": 0, "removed": []}
    written = set()
    for cid, rec in sorted(records.items()):
        cand = cs.get(cid)
        if cand is None:
            out["unknown"].append(cid)
            continue
        rec = _payload(rec)
        bars = None
        if bars_for is not None:
            try:
                bars = bars_for(cand)
                out["full_check"] += 1
            except Exception:                                       # data नाही ⇒ रचना-तपासणी पुरे
                bars = None
        p = os.path.join(out_dir, cand["split"], f"{cid}.json")
        err = SC.validate(rec, cand, bars)
        if err:
            out["invalid"][cid] = err
            written.add(os.path.abspath(p))                         # आधीची वैध export तशीच (DB मधली चूक दुरुस्त होईपर्यंत)
            continue
        try:
            _write(p, rec)
        except OSError as exc:
            raise StoreError(f"{cid}: export लिहिता आला नाही ({p}): {exc}") from exc
        written.add(os.path.abspath(p))
        out[cand["split"]] += 1
    for sp in SC.SPLITS:
        d = os.path.join(out_dir, sp)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.abspath(os.path.join(d, f))
            if f.endswith(".json") and p not in written:
                os.remove(p)
                out["removed"].append(f"{sp}/{f}")
    return out


def load_labels(manifest, purpose, labels_dir_=None):
    """Export केलेले labels. purpose:
      calibration ⇒ फक्त dev + `calibration: true` (Abhi चे आधीचे / contaminated charts वगळून) — test folder कधीच उघडत नाही;
      dev_report  ⇒ सगळे dev (regression / अहवाल);
      acceptance  ⇒ फक्त test (sealed — शेवटच्या acceptance साठीच).
    Labels folder नाही ⇒ `LabelsMissing` (शांत {} नाही)."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} — {PURPOSES} पैकी")
    root = labels_dir_ or labels_dir()
    if not os.path.isdir(root):
        raise LabelsMissing(f"gallery labels folder नाही: {root} — VPS वर `scripts/reader2_gallery_export.py` चालवा किंवा "
                            "READER2_GALLERY_LABELS द्या")
    split = "test" if purpose == "acceptance" else "dev"
    cs = charts(manifest)
    d = os.path.join(root, split)
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


def calibration_labels(manifest, labels_dir_=None):
    """Calibration (CR4+) चा **एकमेव** मार्ग: dev labels फक्त. Test split कधीच नाही."""
    return load_labels(manifest, "calibration", labels_dir_)
