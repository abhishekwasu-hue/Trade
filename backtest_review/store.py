"""backtest_review/store.py — Abhi च्या review नोंदी (Supabase `backtest_review`). TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §3.

एक item = एक दिवस (`day:YYYY-MM-DD`) किंवा एक trade (`trade:YYYY-MM-DD HH:MM:<side>`). Upsert (शेवटचं उत्तर ग्राह्य); पुन्हा उघडल्यावर
`load_reviews` ने दिसतं. अपयश ⇒ False / {} (raise नाही; page वर कारण दाखवतो). Writes फक्त या table मध्ये — bot / orders ला हात नाही.
"""
import json

import pandas as pd

from opportunity_engine import store as S

TABLE = "backtest_review"
VERDICTS = ("OK", "WRONG", "UNCLEAR")          # ✔ / ✘ / ?
KINDS = ("day", "trade", "vision_test", "test", "annotation_check")  # test = Abhi च्या चाचणी replies (खरे निकाल नाहीत) ⇒ मोजमापातून वगळ
CREATE_SQL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
    item_id TEXT PRIMARY KEY, review_date DATE NOT NULL, item_type TEXT NOT NULL, verdict TEXT NOT NULL, reason TEXT,
    missed_trade TEXT, settings_hash TEXT, reviewed_at TIMESTAMP NOT NULL DEFAULT NOW());"""


def item_id(kind, date, time=None, side=None):
    d = f"{pd.Timestamp(date):%Y-%m-%d}"
    return f"day:{d}" if kind == "day" else f"trade:{d} {time}:{side}"


def ensure_table(conn_factory=None):
    return S._run(conn_factory, lambda cur: cur.execute(CREATE_SQL))


def save_review(item, date, kind, verdict, reason="", missed=None, settings_hash=None, conn_factory=None, now=None):
    """missed = {"time": "14:00", "side": "bear_call"} (फक्त दिवसासाठी, "सुटलेला trade"). रिटर्न True / False."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict {verdict!r} — {VERDICTS} पैकी")
    if kind not in KINDS:
        raise ValueError(f"kind {KINDS} पैकी")
    if missed:
        if not str(missed.get("time") or "").strip() or missed.get("side") not in ("bull_put", "bear_call"):
            raise ValueError("सुटलेला trade: वेळ (HH:MM) आणि side (bull_put / bear_call) हवेत")
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now("UTC").tz_localize(None)
    row = (item, pd.Timestamp(date).date(), kind, verdict, reason or "", json.dumps(missed, ensure_ascii=False) if missed else None,
           settings_hash, now.to_pydatetime())

    def work(cur):
        cur.execute(CREATE_SQL)
        cur.execute(f"""INSERT INTO {TABLE} (item_id, review_date, item_type, verdict, reason, missed_trade, settings_hash, reviewed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (item_id) DO UPDATE SET verdict = EXCLUDED.verdict, reason = EXCLUDED.reason,
                        missed_trade = EXCLUDED.missed_trade, settings_hash = EXCLUDED.settings_hash, reviewed_at = EXCLUDED.reviewed_at,
                        item_type = EXCLUDED.item_type""", row)
    return bool(S._run(conn_factory, work))


NOT_MEASURED = ("test", "vision_test", "annotation_check")   # चाचणी replies / vision blind test / annotation तपासणी ⇒ code-review मोजमापात नाहीत


def measurable(reviews):
    """code review मोजमापासाठी नोंदी: test (Abhi च्या चाचणी replies) आणि vision_test वगळून."""
    return {k: v for k, v in (reviews or {}).items() if v.get("item_type") not in NOT_MEASURED}


def load_reviews(conn_factory=None):
    """{item_id: {verdict, reason, missed_trade (dict | None), settings_hash, reviewed_at, review_date, item_type}}."""
    out = {}

    def work(cur):
        cur.execute(CREATE_SQL)
        cur.execute(f"SELECT item_id, review_date, item_type, verdict, reason, missed_trade, settings_hash, reviewed_at FROM {TABLE}")
        for iid, d, kind, v, reason, missed, sh, at in cur.fetchall():
            out[iid] = {"review_date": str(d), "item_type": kind, "verdict": v, "reason": reason, "settings_hash": sh, "reviewed_at": str(at),
                        "missed_trade": json.loads(missed) if missed else None}
        return out
    res = S._run(conn_factory, work)
    return out if res else {}


def progress(index, reviews):
    """index = run_index.json चे दिवस/trades ⇒ {"days": (तपासले, एकूण), "trades": (तपासले, एकूण), "verdicts": {...}}.
    test / vision_test नोंदी मोजत नाही (measurable)."""
    reviews = measurable(reviews)
    days = [item_id("day", d["date"]) for d in index.get("days", [])]
    trades = [t["item_id"] for d in index.get("days", []) for t in d.get("trades", [])]
    cnt = pd.Series([r["verdict"] for r in reviews.values()]).value_counts().to_dict() if reviews else {}
    return {"days": (sum(i in reviews for i in days), len(days)), "trades": (sum(i in reviews for i in trades), len(trades)), "verdicts": cnt}


def test_candidates(reviews, dates, start_utc, end_utc):
    """Abhi च्या चाचणी replies शोधा: review_date ∈ dates आणि reviewed_at (UTC) [start, end] मध्ये. रिटर्न item_id यादी (फक्त वाचन)."""
    ds = {f"{pd.Timestamp(d):%Y-%m-%d}" for d in dates}
    a, b = pd.Timestamp(start_utc), pd.Timestamp(end_utc)
    return sorted(k for k, v in reviews.items() if str(v.get("review_date"))[:10] in ds and v.get("item_type") != "test"
                  and a <= pd.Timestamp(v.get("reviewed_at")) <= b)


def mark_test(item_ids, conn_factory=None):
    """नोंदी 'test' म्हणून चिन्हांकित (item_type = test; reason मध्ये मूळ प्रकार) — delete नाही, मोजमापात वगळल्या जातात."""
    ids = list(item_ids or [])
    if not ids:
        return True

    def work(cur):
        cur.execute(CREATE_SQL)
        for i in ids:
            cur.execute(f"UPDATE {TABLE} SET reason = CONCAT('[test; was ', item_type, '] ', COALESCE(reason, '')), item_type = 'test' "
                        f"WHERE item_id = %s AND item_type <> 'test'", (i,))
    return bool(S._run(conn_factory, work))


# ---------------------------------------------------------------------------------------------------------------- Golden Gallery
GALLERY = "golden_gallery"
GALLERY_VERDICTS = ("GOLDEN", "OK", "WRONG")      # ⭐ / ✔ / ✘
GALLERY_SQL = f"""CREATE TABLE IF NOT EXISTS {GALLERY} (
    id TEXT PRIMARY KEY, setup TEXT NOT NULL, bar_time TIMESTAMP NOT NULL, side TEXT NOT NULL, verdict TEXT NOT NULL,
    corrected_setup TEXT, reason TEXT, reviewed_at TIMESTAMP NOT NULL DEFAULT NOW());"""


def gallery_id(setup, bar_time, side):
    return f"{setup}:{pd.Timestamp(bar_time):%Y-%m-%d %H:%M}:{side}"


def save_gallery(gid, setup, bar_time, side, verdict, corrected_setup=None, reason="", conn_factory=None, now=None):
    """⭐ golden / ✔ ठीक / ✘ चुकीचं ओळखलं; corrected_setup = "हा वेगळा G आहे" (G1–G9 किंवा none)."""
    if verdict not in GALLERY_VERDICTS:
        raise ValueError(f"verdict {verdict!r} — {GALLERY_VERDICTS} पैकी")
    if corrected_setup not in (None, "", "none") + tuple(f"G{i}" for i in range(1, 10)):
        raise ValueError("corrected_setup: G1–G9 / none")
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now("UTC").tz_localize(None)
    row = (gid, setup, pd.Timestamp(bar_time).to_pydatetime(), side, verdict, corrected_setup or None, reason or "", now.to_pydatetime())

    def work(cur):
        cur.execute(GALLERY_SQL)
        cur.execute(f"""INSERT INTO {GALLERY} (id, setup, bar_time, side, verdict, corrected_setup, reason, reviewed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET verdict = EXCLUDED.verdict, corrected_setup = EXCLUDED.corrected_setup,
                        reason = EXCLUDED.reason, reviewed_at = EXCLUDED.reviewed_at""", row)
    return bool(S._run(conn_factory, work))


def load_gallery(conn_factory=None):
    out = {}

    def work(cur):
        cur.execute(GALLERY_SQL)
        cur.execute(f"SELECT id, setup, bar_time, side, verdict, corrected_setup, reason, reviewed_at FROM {GALLERY}")
        for gid, setup, bt, side, v, cs, reason, at in cur.fetchall():
            out[gid] = {"setup": setup, "bar_time": str(bt), "side": side, "verdict": v, "corrected_setup": cs, "reason": reason,
                        "reviewed_at": str(at)}
        return out
    return out if S._run(conn_factory, work) else {}
