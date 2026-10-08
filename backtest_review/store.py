"""backtest_review/store.py — Abhi च्या review नोंदी (Supabase `backtest_review`). TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §3.

एक item = एक दिवस (`day:YYYY-MM-DD`) किंवा एक trade (`trade:YYYY-MM-DD HH:MM:<side>`). Upsert (शेवटचं उत्तर ग्राह्य); पुन्हा उघडल्यावर
`load_reviews` ने दिसतं. अपयश ⇒ False / {} (raise नाही; page वर कारण दाखवतो). Writes फक्त या table मध्ये — bot / orders ला हात नाही.
"""
import json

import pandas as pd

from opportunity_engine import store as S

TABLE = "backtest_review"
VERDICTS = ("OK", "WRONG", "UNCLEAR")          # ✔ / ✘ / ?
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
    if kind not in ("day", "trade"):
        raise ValueError("kind day / trade")
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
                        missed_trade = EXCLUDED.missed_trade, settings_hash = EXCLUDED.settings_hash, reviewed_at = EXCLUDED.reviewed_at""", row)
    return bool(S._run(conn_factory, work))


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
    """index = run_index.json चे दिवस/trades ⇒ {"days": (तपासले, एकूण), "trades": (तपासले, एकूण), "verdicts": {...}}."""
    days = [item_id("day", d["date"]) for d in index.get("days", [])]
    trades = [t["item_id"] for d in index.get("days", []) for t in d.get("trades", [])]
    cnt = pd.Series([r["verdict"] for r in reviews.values()]).value_counts().to_dict() if reviews else {}
    return {"days": (sum(i in reviews for i in days), len(days)), "trades": (sum(i in reviews for i in trades), len(trades)), "verdicts": cnt}


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
