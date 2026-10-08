"""§11 — chart images कायमस्वरूपी: unique नावे / overwrite नाही, sha256 जुळतो, outcome chart vision कडे नाही, push आधी delete नाही, dashboard."""
import base64
import datetime as dt
import hashlib
import json
import os
import sqlite3
import subprocess

import pytest

from vision import images as IM
from vision import outcome as VO
from vision import store as VS
from vision import worker as VW

from tests.test_vision_v0 import GOOD, m1_frame, msg, queue, run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "vision.db")
    monkeypatch.setenv("VISION_DB_PATH", p)
    monkeypatch.setenv("VISION_IMAGE_DIR", str(tmp_path / "visual_audit"))
    return p


def sha(b):
    return hashlib.sha256(b).hexdigest()


def test_save_exclusive_never_overwrites(tmp_path):
    p = str(tmp_path / "2026-10-06" / "a_sent.png")
    p1, s1 = IM.save_exclusive(p, b"one")
    p2, s2 = IM.save_exclusive(p, b"two")
    assert p1 == p and p2.endswith("a_sent_2.png") and open(p1, "rb").read() == b"one" and open(p2, "rb").read() == b"two"
    assert s1 == sha(b"one")
    with pytest.raises(ValueError):
        IM.read_verified(p1, s2)


def test_sent_png_name_sha_and_same_bytes_to_vision_and_telegram(db, monkeypatch):
    queue(db)
    out, client, sent = run(db, [msg(GOOD)], monkeypatch)
    r = VS.list_signals()[0]
    name = os.path.basename(r["image_path"])
    assert r["image_path"].startswith(os.path.join(os.environ["VISION_IMAGE_DIR"], "2026-10-06"))
    assert name == f"dynamic_sr_instant_NIFTY_{r['signal_id']}_1042_sent.png"
    on_disk = open(r["image_path"], "rb").read()
    assert r["image_sha256"] == sha(on_disk)
    img = next(b for b in client.calls[0]["messages"][0]["content"] if b["type"] == "image")
    assert sha(base64.standard_b64decode(img["source"]["data"])) == r["image_sha256"]          # vision ला तीच image
    assert sha(sent.photos[0][0]) == r["image_sha256"]                                          # Telegram वर तीच image
    assert r["prompt_version"] == "signal_check_v2_1" and r["final_decision"] == "ENTER" and r["model"] == "test-sonnet-model"
    vj = json.loads(r["vision_json"])
    assert vj["usage"]["input_tokens"] > 0 and r["cost_usd"] > 0


def _trades_db(path, entry, exit_, status="CLOSED", pnl=1200.0, source="dynamic_sr_instant"):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE live_trades (trade_id TEXT, symbol TEXT, strategy TEXT, sl_pnl_level REAL, target_pnl_level REAL, entry_time TEXT, "
              "exit_time TEXT, exit_reason TEXT, realized_pnl REAL, status TEXT, mode TEXT, source TEXT, entry_spot_price REAL)")
    c.execute("INSERT INTO live_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("T1", "NIFTY", "Bull Put Spread", -3000, 2500, entry, exit_, "TARGET" if pnl > 0 else "SL", pnl, status, "PAPER", source, 25010.0))
    c.commit()
    c.close()


def test_outcome_png_post_hoc_saved_and_never_sent_to_vision(db, monkeypatch, tmp_path):
    queue(db)
    run(db, [msg(GOOD)], monkeypatch)
    tdb = str(tmp_path / "trades.db")
    _trades_db(tdb, "2026-10-06 10:43:05", "2026-10-06 11:30:00")
    import plotly.graph_objects as go
    monkeypatch.setattr(go.Figure, "to_image", lambda self, **k: b"\x89PNGoutcome")
    res = VO.run(fetch_fn=lambda s: m1_frame(), trades_db=tdb, now=dt.datetime(2026, 10, 6, 12, 0))
    assert [x[1] for x in res] == ["outcome"]
    r = VS.list_signals()[0]
    assert r["outcome_path"].endswith("_1042_outcome.png") and r["outcome_sha256"] == sha(b"\x89PNGoutcome")
    oj = json.loads(r["outcome_json"])
    assert oj["result"] == "win" and oj["trade_id"] == "T1" and r["trade_id"] == "T1"
    assert open(r["image_path"], "rb").read() != b"\x89PNGoutcome"                              # _sent.png जशीच्या तशी
    fig, meta = VO.build_outcome_figure(m1_frame(), r, {"entry_time": "2026-10-06 10:43:05", "exit_time": "2026-10-06 11:30:00",
                                                        "realized_pnl": -500, "entry_spot_price": 25010.0})
    assert "POST-HOC" in fig.layout.title.text and meta["win"] is False
    src = open(os.path.join(ROOT, "vision", "outcome.py"), encoding="utf-8").read()
    assert "signal_audit" not in src and "anthropic" not in src and "messages.create" not in src


def test_outcome_trade_not_double_credited_and_db_errors_not_no_trade(db, monkeypatch, tmp_path):
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 40, 10))
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 41, 10), level=25300.0)
    run(db, [msg(GOOD), msg(GOOD)], monkeypatch)
    tdb = str(tmp_path / "trades.db")
    _trades_db(tdb, "2026-10-06 10:41:40", "2026-10-06 11:30:00")                              # दुसऱ्या signal नंतरचा trade
    rows = VS.list_signals()
    assert VO.find_trade(rows[0], tdb) is None                                                  # मध्ये दुसरा signal ⇒ पहिल्याचा नाही
    assert VO.find_trade(rows[1], tdb)["trade_id"] == "T1"
    VS.set_outcome(rows[1]["signal_id"], trade_id="T1")
    assert VO.find_trade(rows[1], tdb)["trade_id"] == "T1" and VO.find_trade(rows[0], tdb) is None
    res = VO.run(trades_db=str(tmp_path / "missing.db"), now=dt.datetime(2026, 10, 8, 12, 0))   # DB नाही ⇒ error, no_trade नाही
    assert all(r[1].startswith("error") for r in res) and not os.path.exists(str(tmp_path / "missing.db"))
    assert all(r["outcome_json"] is None for r in VS.list_signals())


def test_outcome_open_trade_waits_and_missing_trade_marked_after_a_day(db, monkeypatch, tmp_path):
    queue(db)
    run(db, [msg(GOOD)], monkeypatch)
    tdb = str(tmp_path / "trades.db")
    _trades_db(tdb, "2026-10-06 10:43:05", None, status="OPEN")
    assert VO.run(fetch_fn=lambda s: m1_frame(), trades_db=tdb, now=dt.datetime(2026, 10, 6, 12, 0)) == [(VS.list_signals()[0]["signal_id"], "open")]
    empty = str(tmp_path / "none.db")
    _trades_db(empty, "2026-10-06 14:00:00", "2026-10-06 15:00:00")                             # वेळ जुळत नाही
    assert VO.run(trades_db=empty, now=dt.datetime(2026, 10, 6, 15, 0)) == []                    # 1 दिवस झाला नाही ⇒ वाट
    res = VO.run(trades_db=empty, now=dt.datetime(2026, 10, 7, 16, 0))
    assert res[0][1] == "no_trade" and json.loads(VS.list_signals()[0]["outcome_json"]) == {"no_trade": True}


# ------------------------------------------------------------------------------------------------ archive
def _git(*a, cwd=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *a], cwd=cwd, env=env, capture_output=True, text=True, check=True)


@pytest.fixture
def trade_data(tmp_path, monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)
    origin = str(tmp_path / "remote" / "trade-data.git")                         # check_repo: नाव trade-data हवं
    _git("init", "-q", "--bare", "-b", "main", origin)
    clone = str(tmp_path / "trade-data")
    _git("clone", "-q", origin, clone)
    open(os.path.join(clone, "README"), "w").write("x")
    _git("add", "README", cwd=clone)
    _git("commit", "-q", "-m", "init", cwd=clone)
    _git("push", "-q", "origin", "HEAD:main", cwd=clone)
    return origin, clone


def _archive():
    import importlib.util
    spec = importlib.util.spec_from_file_location("varch", os.path.join(ROOT, "scripts", "vision_archive.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_archive_pushes_verifies_then_marks(db, monkeypatch, trade_data):
    origin, clone = trade_data
    queue(db)
    run(db, [msg(GOOD)], monkeypatch)
    mod = _archive()
    texts = []
    assert mod.main(["--day", "2026-10-06", "--trade-data", clone], send_text=texts.append) == 0
    src = os.path.join(os.environ["VISION_IMAGE_DIR"], "2026-10-06")
    mk = json.load(open(os.path.join(src, mod.MARKER)))
    listed = _git("ls-tree", "-r", "--name-only", "main", cwd=origin).stdout.split()
    png = [f for f in listed if f.endswith("_sent.png")]
    assert png and png[0].startswith("visual_audit/2026-10/2026-10-06/") and "visual_audit/2026-10/2026-10-06/vision_records_2026-10-06.jsonl" in listed
    assert mk["files"] == {os.path.basename(png[0]): VS.list_signals()[0]["image_sha256"]}          # marker = local नाव → sha256
    rec = _git("show", "main:visual_audit/2026-10/2026-10-06/vision_records_2026-10-06.jsonl", cwd=origin).stdout
    assert json.loads(rec.splitlines()[0])["image_sha256"]


def test_archive_push_failure_keeps_files_and_no_marker(db, monkeypatch, trade_data, tmp_path):
    origin, clone = trade_data
    queue(db)
    run(db, [msg(GOOD)], monkeypatch)
    _git("remote", "set-url", "origin", str(tmp_path / "nope" / "trade-data.git"), cwd=clone)
    mod = _archive()
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    texts = []
    assert mod.main(["--day", "2026-10-06", "--trade-data", clone], send_text=texts.append) == 1
    src = os.path.join(os.environ["VISION_IMAGE_DIR"], "2026-10-06")
    assert not os.path.exists(os.path.join(src, mod.MARKER)) and any("archive" in t for t in texts)


def test_cleanup_deletes_only_marked_and_complete_folders(tmp_path):
    mod = _archive()
    base = str(tmp_path / "va")
    for day, marker, extra, changed in (("2026-01-01", True, False, False), ("2026-01-02", False, False, False),
                                        ("2026-01-03", True, True, False), ("2026-01-04", True, False, True), ("2026-10-01", True, False, False)):
        d = os.path.join(base, day)
        os.makedirs(d)
        open(os.path.join(d, "a_sent.png"), "wb").write(b"x")
        if marker:
            json.dump({"commit": "c", "files": {"a_sent.png": sha(b"x")}}, open(os.path.join(d, mod.MARKER), "w"))
        if extra:
            open(os.path.join(d, "b_outcome.png"), "wb").write(b"y")                           # marker नंतर आलेली ⇒ push झालेली नाही
        if changed:
            open(os.path.join(d, "a_sent.png"), "wb").write(b"x-truncated")                    # sha जुळत नाही
    deleted, skipped = mod.cleanup(base, dt.date(2026, 10, 7), keep_days=90)
    assert deleted == ["2026-01-01"]
    assert {s[0] for s in skipped} == {"2026-01-02", "2026-01-03", "2026-01-04"} and os.path.isdir(os.path.join(base, "2026-10-01"))


def test_failed_day_is_retried_next_night(db, monkeypatch, trade_data, tmp_path):
    origin, clone = trade_data
    queue(db)
    run(db, [msg(GOOD)], monkeypatch)
    mod = _archive()
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    good = _git("remote", "get-url", "origin", cwd=clone).stdout.strip()
    _git("remote", "set-url", "origin", str(tmp_path / "nope" / "trade-data.git"), cwd=clone)
    assert mod.main(["--trade-data", clone], send_text=lambda t: None) == 1
    _git("remote", "set-url", "origin", good, cwd=clone)
    monkeypatch.setattr(VS, "now_ist", lambda: dt.datetime(2026, 10, 20, 23, 50))               # 2 आठवड्यांनी, --day शिवाय
    assert mod.days_to_archive(os.environ["VISION_IMAGE_DIR"], dt.date(2026, 10, 20)) == ["2026-10-06"]
    assert mod.main(["--trade-data", clone], send_text=lambda t: None) == 0
    assert mod.days_to_archive(os.environ["VISION_IMAGE_DIR"], dt.date(2026, 10, 20)) == []


def test_archive_refuses_non_trade_data_destination(db, monkeypatch, trade_data, tmp_path):
    origin, clone = trade_data
    queue(db)
    run(db, [msg(GOOD)], monkeypatch)
    _git("remote", "set-url", "origin", "https://github.com/x/Trade.git", cwd=clone)
    mod = _archive()
    texts = []
    assert mod.main(["--day", "2026-10-06", "--trade-data", clone], send_text=texts.append) == 1
    assert not os.path.exists(os.path.join(clone, "visual_audit"))


# ------------------------------------------------------------------------------------------------ dashboard helpers
def test_dashboard_table_and_filters(db, monkeypatch, tmp_path):
    import page_vision_human_eye as P
    queue(db)
    queue(db, level=25300.0)
    run(db, [msg(GOOD), msg({**GOOD, "reversal_valid": "no"})], monkeypatch)
    df = P.flatten(VS.list_signals())
    assert len(df) == 2 and set(df["verdict"]) == {"agree", "disagree"} and df["reason"].notna().all()
    assert len(P.apply_filters(df, verdicts=["disagree"])) == 1
    assert len(P.apply_filters(df, results=["open"])) == 2 and len(P.apply_filters(df, results=["win"])) == 0
    assert len(P.apply_filters(df, start=dt.date(2026, 10, 7))) == 0
    pct, mb = P.disk_usage(os.environ["VISION_IMAGE_DIR"])
    assert 0 <= pct <= 100 and mb >= 0


def test_worker_only_sends_sent_png_to_vision():
    src = open(os.path.join(ROOT, "vision", "worker.py"), encoding="utf-8").read()
    assert "IM.SENT" in src and "IM.OUTCOME" not in src and "outcome" not in src.split("def process_row")[1].split("def run_once")[0].lower()
    _ = VW  # import ठेवतो


def test_outcome_label_marathi_only_with_font_and_strike_lines(monkeypatch):
    monkeypatch.setattr(VO, "_DEVA", True)
    assert VO.post_hoc_label().startswith("POST-HOC: vision ला पाठवलेली नाही")
    monkeypatch.setattr(VO, "_DEVA", False)
    assert VO.post_hoc_label() == VO.POST_HOC                                                   # font नाही ⇒ डबे नकोत, इंग्रजी
    legs = json.dumps([{"strike": 25050, "option_type": "PE", "transaction_type": "SELL"},
                       {"strike": 24900, "option_type": "PE", "transaction_type": "BUY"}, {"strike": "x"}])
    assert VO.strike_lines({"legs_json": legs}) == [(25050.0, "SELL 25,050 PE"), (24900.0, "BUY 24,900 PE")]
    assert VO.strike_lines({"legs_json": "not json"}) == [] and VO.strike_lines({}) == []
    assert VO.strike_lines({"legs_json": json.dumps([{"strike": 0, "transaction_type": "BUY"}, {"strike": float("nan")}])}) == []
    fly = json.dumps([{"strike": 25000, "option_type": "CE", "transaction_type": "SELL"}, {"strike": 25000, "option_type": "PE", "transaction_type": "SELL"}])
    assert VO.strike_lines({"legs_json": fly}) == [(25000.0, "SELL 25,000 CE / SELL 25,000 PE")]
    row = {"signal_id": "x", "bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "level": 25000.0,
           "signal_ts": "2026-10-06T10:42:20"}
    fig, _ = VO.build_outcome_figure(m1_frame(), row, {"entry_time": "2026-10-06 10:43:05", "exit_time": "2026-10-06 11:30:00",
                                                       "realized_pnl": 900, "legs_json": legs})
    ys = {round(s.y0) for s in fig.layout.shapes}
    assert {25050, 24900} <= ys and any("SELL 25,050 PE" == a.text for a in fig.layout.annotations)


def test_outcome_far_strike_does_not_squash_candles():
    row = {"signal_id": "x", "bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "level": 25000.0,
           "signal_ts": "2026-10-06T10:42:20"}
    legs = json.dumps([{"strike": 25000, "option_type": "PE", "transaction_type": "SELL"}, {"strike": 23000, "option_type": "PE", "transaction_type": "BUY"}])
    fig, _ = VO.build_outcome_figure(m1_frame(), row, {"entry_time": "2026-10-06 10:43:05", "exit_time": "2026-10-06 11:30:00", "legs_json": legs})
    lo, hi = fig.layout.yaxis.range
    assert lo > 24000 and hi < 25500                                                            # 23000 range मध्ये नाही
    assert any(a.text == "↓ BUY 23,000 PE" for a in fig.layout.annotations)
    assert not any(round(s.y0) == 23000 for s in fig.layout.shapes)
