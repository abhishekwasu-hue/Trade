"""Today's reading gallery (owner-orders DECISIONS 49; decision3/reading_gallery.py + scripts/reading_gallery_today.py).
Fake store rows / a fake V22 only — no network, no Upstox, no Telegram, no git remote outside tmp_path.
  • entries + visits are found from the store rows (an entered visit and a cluster member are not "visits without an entry");
  • no look-ahead: only bars closed at the decision are known on every panel (the 15M / 1H bar in progress is after the decision),
    no lifecycle event after the decision, the chart is drawn;
  • the Marathi line carries no internal code (status names, rule tags, model codes) — known phrases and unknown ones;
  • the display cap (never a reading rule) and the disarmed display switch;
  • OFF when the market was closed (weekend / NSE holiday) or `reading_gallery` = off;
  • the push helper (local bare repo), the silent Telegram line, the cron install / revert.
"""
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from decision3 import reading_gallery as RG  # noqa: E402

DAY = "2026-10-16"


# ------------------------------------------------------------------------------------------------------------------------ fakes
def armed(vid, aid=7, lo=100.0, hi=110.0, d=-1, models=None, disarmed=None, obj="area", vs="2026-10-16 10:00:00"):
    a = {"object": obj, "area_id": aid, "tf": "1H", "role": "resistance" if d < 0 else "support", "lo": lo, "hi": hi, "state": "ACTIVE",
         "direction": d, "side": "bear_call" if d < 0 else "bull_put", "visit_id": vid, "visit_start": vs,
         "models": models or {"E1": {"status": "passed", "waiting": "no refined base yet: no 15M turn of the area's side inside its band "
                                                                     "(RC2) — E1 waits"},
                              "E2": {"status": "waiting", "waiting": "commitment candle not dominant (a candle in this visit is as large "
                                                                     "or larger) (5M)"},
                              "E3": {"status": "waiting", "waiting": "no 5M CHoCH yet"},
                              "E4": {"status": "waiting", "waiting": "no 5M sweep yet (price has not gone beyond the area's far edge)"}}}
    if disarmed:
        a["disarmed"] = disarmed
        a["models"] = {m: {"status": "disarmed"} for m in RG.MODELS}
    return a


def entry(vid, model="E2", aid=7, d=-1, cluster=None, ts="2026-10-16 11:05:00"):
    return {"model": model, "name": RG.NAME_EN[model], "direction": d, "side": "bear_call", "object": "area",
            "area": {"id": aid, "tf": "1H", "role": "resistance", "lo": 100.0, "hi": 110.0, "state": "ACTIVE", "object": "area"},
            "visit_id": vid, "visit_start": "2026-10-16 10:00:00", "trigger_ts": ts, "trigger_bar_end": str(pd.Timestamp(ts) + pd.Timedelta(minutes=5)),
            "entry_ref": 104.5, "invalidation": {"price": 112.0, "rule": "price above the visit's extreme 112.00 (refined base 2026-10-15 14:00)"},
            "refined_base": {"lo": 104.0, "hi": 108.0, "ts": "2026-10-15 14:00:00"}, "cluster": cluster, "trigger_tf": "5M"}


def row(bar_ts, entries=(), arm=(), decision="wait", reason="waiting"):
    return {"symbol": "BANKNIFTY", "bar_ts": bar_ts, "decision": decision, "reason": reason,
            "payload": json.dumps({"engine": "decision3", "entries": list(entries), "armed": list(arm)})}


def rows_fixture():
    vA, vB, vC = "7@2026-10-16 10:00:00", "9@2026-10-16 12:00:00", "11@2026-10-16 13:00:00"
    cl = {"id": "C7", "anchor": 7, "visit_id": vA, "n": 2, "members": [{"area_id": 7}, {"area_id": 8}]}
    return [
        row("2026-10-15 15:00:00", arm=[armed("3@2026-10-15 14:00:00", aid=3)]),                    # another day: never read
        row("2026-10-16 10:05:00", arm=[armed(vA), armed("8@2026-10-16 10:00:00", aid=8)]),
        row("2026-10-16 11:10:00", entries=[entry(vA, cluster=cl)], arm=[armed(vA), armed("8@2026-10-16 10:00:00", aid=8)]),
        row("2026-10-16 11:15:00", entries=[entry(vA, cluster=cl)], arm=[armed(vA)]),               # the same entry again: once
        row("2026-10-16 12:05:00", arm=[armed(vB, aid=9, lo=90, hi=95, d=1)]),
        row("2026-10-16 12:30:00", arm=[armed(vB, aid=9, lo=90, hi=95, d=1)]),
        row("2026-10-16 12:35:00", decision="error", reason="EngineDataError: x"),
        row("2026-10-16 13:05:00", arm=[armed(vC, aid=11, disarmed="price came into the area from the trade side (not a pullback — H2)")]),
    ]


def test_collect_finds_entries_and_visits_without_entry():
    cons = [{"bot": "srv2_momentum_reversal", "symbol": "BANKNIFTY", "visit_id": "7@2026-10-16 10:00:00", "model": "E2", "status": "EXECUTED"}]
    c = RG.collect(rows_fixture(), cons, DAY)
    assert [(e["model"], e["bar_ts"]) for e in c["entries"]] == [("E2", "2026-10-16 11:10:00")]
    assert c["entries"][0]["used"] == [{"bot": "srv2_momentum_reversal", "status": "EXECUTED"}]
    vids = [v["visit_id"] for v in c["visits"]]
    assert vids == ["9@2026-10-16 12:00:00", "11@2026-10-16 13:00:00"]        # A entered, 8 = a member of A's cluster, 3 = other day
    vb = c["visits"][0]
    assert vb["first_ts"] == "2026-10-16 12:05:00" and vb["bar_ts"] == "2026-10-16 12:30:00" and vb["n_rows"] == 2   # the final status
    assert len(c["errors"]) == 1 and c["rows"] == 7


def test_marathi_line_has_no_internal_codes():
    c = RG.collect(rows_fixture(), [], DAY)
    lst = RG.plan(c)
    texts = [RG.marathi_line(x) for x in lst]
    odd = armed("x@1", models={"E1": {"status": "fired_earlier", "at": "2026-10-15 10:10:00"},
                               "E2": {"status": "blocked_data_problem", "note": "data problem: FUT 5M volume gaps 3/5 5M bars in the visit "
                                                                              "(> 50%, vol_gap_max_frac) — consumed, not an entry"},
                               "E3": {"status": "cluster_consumed", "note": "K4 sweep (DECISIONS 38, H2) TA4 c1 armed"},
                               "E4": {"status": "waiting", "waiting": "something new the reader says (RC3) with E4 and Z-1u inside"}})
    texts.append(RG.marathi_line({"kind": "visit", "armed": odd}))
    texts.append(RG.marathi_line({"kind": "visit", "armed": armed("y@1", obj="broken_line", aid="line:abc",
                                                                  models={"E4": {"status": "waiting", "waiting": "the revisit came from "
                                                                                 "above the broken object (DECISIONS 38, H2)"}})}))
    for t in texts:
        assert RG.code_free(t), t
        assert re.search(r"[ऀ-ॿ]", t), t                                     # Marathi
        assert "\n" not in t                                                   # ONE line
    assert "refined base" in texts[0] and "112.00" in texts[0]                 # the reader's own numbers kept
    for code in ("fired_earlier", "SKIPPED", "E2", "RC2", "H2", "K4", "disarmed", "armed", "vol_gap_max_frac"):
        assert all(code not in t for t in texts), code


def test_used_status_words_have_no_codes():
    for st in ("EXECUTED", "SKIPPED_MAX_HITS_PER_ZONE", "SKIPPED_CUTOFF", "OPEN_FAILED: X", "NOT_ENTERED_SKIP", None):
        w = RG.used_mr([{"bot": "b", "status": st}] if st else [])
        assert RG.code_free(w) and re.search(r"[ऀ-ॿ]", w)


def test_cap_is_display_only_and_lists_everything():
    vs = [armed(f"{i}@2026-10-16 1{i}:00:00", aid=i) for i in range(5)]
    rows = [row(f"2026-10-16 1{i}:05:00", arm=[vs[i]]) for i in range(5)] + [row("2026-10-16 12:20:00", entries=[entry("99@x", aid=99)])]
    rows.append(row("2026-10-16 15:00:00", arm=[armed("50@z", aid=50, disarmed="price came into the area from the trade side")]))
    c = RG.collect(rows, [], DAY)
    lst = RG.plan(c, {"reading_gallery_max_visit_charts": 2})
    assert [x["n"] for x in lst] == list(range(1, 8))                          # every case numbered
    assert all(x["draw"] for x in lst if x["kind"] == "entry")                 # entries are never capped
    drawn = [x for x in lst if x["kind"] == "visit" and x["draw"]]
    assert len(drawn) == 2 and all("display cap" in x["why_not_drawn"] for x in lst if x["kind"] == "visit" and not x["draw"])
    lst = RG.plan(c, {"reading_gallery_max_visit_charts": 40, "reading_gallery_disarmed_charts": "off"})
    dis = [x for x in lst if RG.is_disarmed(x)]
    assert dis and not any(x["draw"] for x in dis)
    assert all(x["draw"] for x in lst if not RG.is_disarmed(x))


# ------------------------------------------------------------------------------------------------------------------------ fake V22
class FakeLevel(SimpleNamespace):
    pass


class FakeLevels:
    def __init__(self, L, close):
        self.L, self.A = L, {"close": close}

    def snapshot(self, t):
        return [{"id": 1, "tf": "1H", "role": "support", "lo": 80.0, "hi": 85.0, "state": "ACTIVE", "trade_location": True},
                {"id": 2, "tf": "1H", "role": "support", "lo": 60.0, "hi": 62.0, "state": "BROKEN", "trade_location": True}]


def fake_v(days=("2026-10-14", "2026-10-15", "2026-10-16")):
    t15 = [pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * i) for d in days for i in range(25)]
    n = len(t15)
    rng = np.random.default_rng(3)
    c = 100 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]]
    m15 = pd.DataFrame({"timestamp": t15, "open": o, "high": np.maximum(o, c) + 1, "low": np.minimum(o, c) - 1, "close": c})
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    t5 = [t + pd.Timedelta(minutes=5 * k) for t in t15 for k in range(3)]
    c5 = np.repeat(c, 3) + rng.normal(0, 0.3, len(t5))
    o5 = np.r_[c5[0], c5[:-1]]
    ltf = {"start": np.array(t5, "datetime64[ns]"), "end": np.array([t + pd.Timedelta(minutes=5) for t in t5], "datetime64[ns]"),
           "open": o5, "high": np.maximum(o5, c5) + 0.5, "low": np.minimum(o5, c5) - 0.5, "close": c5}
    k_dec = 25 * 2 + 8                                                          # 16 Oct 11:15 bar
    L = [FakeLevel(id=0, tf="1H", role0="resistance", lo=100.0, hi=110.0, born_bar=10, births=["a"], dead_bar=None,
                   events=[(20, "test", ""), (30, "sweep", "x"), (k_dec - 2, "flip", "y"), (k_dec + 6, "broken", "after the decision")])]
    L += [FakeLevel(id=i, tf="1H", role0="support", lo=80.0, hi=85.0, born_bar=5, births=["a"], dead_bar=None, events=[]) for i in (1, 2)]
    V = SimpleNamespace(m15=m15[["timestamp", "bar_end", "open", "high", "low", "close"]], bar_end=m15["bar_end"], ltf=ltf)
    V.levels = FakeLevels(L, c)
    return V


def test_panels_have_no_look_ahead():
    V = fake_v()
    dec = pd.Timestamp("2026-10-16 11:25")                                     # a 5M close inside the 11:15 15M bar
    B = RG.panel_bars(V, dec)
    for tf, b in B.items():
        assert len(b) and b["known"].any() and (~b["known"]).any(), tf
        assert (b.loc[b["known"], "end"] <= dec).all(), tf                    # every known bar closed at the decision
        assert (b.loc[~b["known"], "end"] > dec).all(), tf                    # everything else is "after the decision"
        assert list(b["known"]) == sorted(b["known"], reverse=True), tf      # known first, then only after
    m15 = B["15M"]
    assert not m15.loc[m15["timestamp"] == pd.Timestamp("2026-10-16 11:15"), "known"].any()   # the 15M bar in progress
    h = B["1H"]
    assert not h.loc[h["timestamp"] == pd.Timestamp("2026-10-16 11:15"), "known"].any()        # the 1H bar in progress


def test_render_case_draws_decision_and_only_known_events(tmp_path):
    V = fake_v()
    c = RG.collect([row("2026-10-16 11:25:00", entries=[entry("0@2026-10-16 10:00:00", aid=0, ts="2026-10-16 11:20:00")])], [], DAY)
    lst = RG.plan(c)
    g = RG.geometry(V, lst[0])
    assert g["k"] == 25 * 2 + 7                                                # the last 15M bar CLOSED at 11:25 = the 11:00 bar
    kinds = [k for _t, k, _w in g["events"]]
    assert "flip" in kinds and "broken" not in kinds and "test" not in kinds   # the break after the decision is not drawn
    assert all(pd.Timestamp(t) <= pd.Timestamp("2026-10-16 11:00") for t, _k, _w in g["events"])
    assert g["next"]["id"] == 1                                                # the broken support is never the next area
    assert g["approach"]["from"] in ("above", "below", "inside")
    meta = RG.render_case(V, "BANKNIFTY", lst[0], str(tmp_path / "x.png"), g=g)
    assert (tmp_path / "x.png").stat().st_size > 20000
    for tf, p in meta["panels"].items():
        assert pd.Timestamp(p["last_known_end"]) <= pd.Timestamp("2026-10-16 11:25"), tf
        assert p["first_after_ts"] is None or pd.Timestamp(p["first_after_ts"]) >= pd.Timestamp("2026-10-16 11:00"), tf


# ------------------------------------------------------------------------------------------------------------------------ the script
def make_store(p, rows):
    import engine_signal as ES
    with ES.connect(str(p)) as c:
        for r in rows:
            c.execute("INSERT INTO engine_signals (symbol, bar_ts, decision, reason, payload) VALUES (?,?,?,?,?)",
                      (r["symbol"], r["bar_ts"], r["decision"], r["reason"], r["payload"]))


def test_run_writes_numbered_gallery_from_fake_store(tmp_path):
    import reading_gallery_today as G
    st = tmp_path / "es.db"
    make_store(st, [row("2026-10-16 11:25:00", entries=[entry("0@2026-10-16 10:00:00", aid=0, ts="2026-10-16 11:20:00")]),
                    row("2026-10-16 12:00:00", arm=[armed("0@2026-10-16 11:45:00", aid=0, vs="2026-10-16 11:45:00")])])
    before = st.read_bytes()
    out = tmp_path / "g"
    sm = G.run(DAY, str(out), lambda s: None, str(st), settings={}, build=lambda *a, **k: (fake_v(), None), log=lambda *a: None)
    assert sm["entries"] == 1 and sm["visits"] == 1 and sm["symbols"] == ["BANKNIFTY"]
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "#1" in html and "#2" in html and "“#3: …”" in html and "after the decision" in html
    assert re.search(r"[ऀ-ॿ]", html)
    assert (out / "BANKNIFTY_01_entry.png").exists() and (out / "BANKNIFTY_02_visit.png").exists()
    assert st.read_bytes() == before                                           # the store is only read


@pytest.mark.parametrize("day", ["2026-10-24", "2026-10-20"])                  # a Saturday; Dussehra (NSE holiday)
def test_off_when_market_closed(monkeypatch, capsys, day):
    import reading_gallery_today as G
    monkeypatch.setattr(G, "settings_of", lambda get=None: {"reading_gallery": "on"})
    monkeypatch.setattr(G, "run", lambda *a, **k: pytest.fail("must not build on a closed day"))
    assert G.main(["--day", day, "--no-telegram", "--no-push"]) == 0
    assert "market closed" in capsys.readouterr().out


def test_off_by_dashboard_setting(monkeypatch, capsys):
    import reading_gallery_today as G
    monkeypatch.setattr(G, "settings_of", lambda get=None: {"reading_gallery": "off"})
    monkeypatch.setattr(G, "run", lambda *a, **k: pytest.fail("must not build when off"))
    assert G.main(["--day", DAY, "--no-telegram"]) == 0
    assert "reading_gallery = off" in capsys.readouterr().out


def test_dashboard_display_settings():
    import cloud_db
    s = cloud_db.get_chart_reading_settings(raw_fn=lambda *a: {})
    assert (s["reading_gallery"], s["reading_gallery_max_visit_charts"], s["reading_gallery_disarmed_charts"]) == ("on", 40, "on")
    assert cloud_db.clean_chart_reading_settings({"reading_gallery_max_visit_charts": "12"}) == {"reading_gallery_max_visit_charts": 12}
    for bad in ({"reading_gallery_max_visit_charts": "x"}, {"reading_gallery_max_visit_charts": -1}, {"reading_gallery": "maybe"}):
        with pytest.raises(ValueError):
            cloud_db.clean_chart_reading_settings(bad)


def test_push_and_verify_with_local_bare_remote(tmp_path):
    import reading_gallery_today as G
    bare, work = tmp_path / "remote.git", tmp_path / "td"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True, capture_output=True)
    (work / "keep.txt").write_text("x")
    G.git(str(work), "add", "keep.txt")
    G.git(str(work), "commit", "-q", "-m", "init")
    G.git(str(work), "push", "-q", "origin", "HEAD:main")
    rel = os.path.join(G.REL_BASE, DAY)
    (work / rel).mkdir(parents=True)
    (work / rel / "index.html").write_text("<html></html>")
    (work / rel / "a.png").write_bytes(b"\x89PNG fake")
    commit = G.push_and_verify(str(work), rel, "test gallery")
    assert commit
    ls = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main"], capture_output=True, text=True).stdout
    assert f"{rel}/index.html" in ls and f"{rel}/a.png" in ls and "keep.txt" in ls


def test_tarball_fallback_prints_sha(tmp_path):
    import reading_gallery_today as G
    f = tmp_path / DAY
    f.mkdir()
    (f / "index.html").write_text("x")
    t, sha = G.tarball(str(f), str(tmp_path / "tar"))
    assert os.path.exists(t) and len(sha) == 64


def test_silent_telegram_line(monkeypatch):
    import notifications as N
    sent = []
    monkeypatch.setattr(N, "_load_telegram_credentials", lambda: ("tok", "chat"))
    monkeypatch.setattr(N, "_log_locally", lambda m: None)
    monkeypatch.setattr(N.requests, "post", lambda url, json=None, timeout=None: sent.append(json) or SimpleNamespace(status_code=200))
    assert N.send_telegram_message("x", silent=True) and N.send_telegram_message("y")
    assert sent[0].get("disable_notification") is True and "disable_notification" not in sent[1]


def test_cron_install_is_idempotent_and_reverts(tmp_path):
    cron = tmp_path / "cron"
    cron.write_text("*/5 * * * * python3 trade_monitor.py\n")
    sh = ROOT / "scripts" / "install_reading_gallery_schedule.sh"
    env = {"CRONTAB_FILE": str(cron), "REPO_DIR": "/root/Trade", "PATH": "/usr/bin:/bin"}
    for _ in range(2):
        subprocess.run(["bash", str(sh)], env=env, check=True, capture_output=True)
    txt = cron.read_text()
    assert txt.count("# reading-gallery-close") == 1 and "40 10 * * 1-5" in txt and "trade_monitor.py" in txt
    subprocess.run(["bash", str(sh), "--revert"], env=env, check=True, capture_output=True)
    assert "reading-gallery" not in cron.read_text() and "trade_monitor.py" in cron.read_text()


# ------------------------------------------------------------------------------------------------------------------------ review fixes
def _clone(tmp_path):
    import reading_gallery_today as G
    bare, work = tmp_path / "remote.git", tmp_path / "td"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True, capture_output=True)
    rel = os.path.join(G.REL_BASE, DAY)
    (work / rel).mkdir(parents=True)
    (work / rel / "old.png").write_bytes(b"old")
    (work / "keep.txt").write_text("x")
    G.git(str(work), "add", ".")
    G.git(str(work), "commit", "-q", "-m", "init")
    G.git(str(work), "push", "-q", "origin", "HEAD:main")
    return G, bare, work, rel


def _remote_files(bare):
    return subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main"], capture_output=True, text=True).stdout


def test_push_never_records_a_working_tree_deletion(tmp_path):
    G, bare, work, rel = _clone(tmp_path)
    (work / rel / "old.png").unlink()                                          # a file gone from the working tree (a re-run)
    (work / rel / "index.html").write_text("<html></html>")
    G.push_and_verify(str(work), rel, "gallery")
    ls = _remote_files(bare)
    assert f"{rel}/old.png" in ls and f"{rel}/index.html" in ls               # trade-data never loses a file


def test_push_refuses_a_staged_deletion(tmp_path):
    G, bare, work, rel = _clone(tmp_path)
    G.git(str(work), "rm", "-q", "keep.txt")                                   # someone else's staged deletion
    (work / rel / "index.html").write_text("<html></html>")
    with pytest.raises(RuntimeError, match="deletion"):
        G.push_and_verify(str(work), rel, "gallery")
    assert "keep.txt" in _remote_files(bare)


def test_push_refuses_on_index_lock(tmp_path):
    G, bare, work, rel = _clone(tmp_path)
    (work / ".git" / "index.lock").write_text("")
    with pytest.raises(RuntimeError, match="index.lock"):
        G.push_and_verify(str(work), rel, "gallery")
    assert (work / ".git" / "index.lock").exists()                            # never deleted


def test_failed_rebase_is_aborted(tmp_path):
    G, bare, work, rel = _clone(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True, capture_output=True)
    (other / rel / "index.html").write_text("theirs")
    G.git(str(other), "add", ".")
    G.git(str(other), "commit", "-q", "-m", "theirs")
    G.git(str(other), "push", "-q", "origin", "HEAD:main")
    (work / rel / "index.html").write_text("ours")                             # the same new file ⇒ a rebase conflict
    with pytest.raises(G.PushPending):
        G.push_and_verify(str(work), rel, "gallery")
    assert not (work / ".git" / "rebase-merge").exists() and not (work / ".git" / "rebase-apply").exists()
    assert G.git(str(work), "status", "--porcelain").stdout.strip() == ""      # clean, our commit kept
    assert "gallery" in G.git(str(work), "log", "-1", "--format=%s").stdout


def test_marathi_fallback_strips_setting_names_and_variant_tags():
    for raw in ("max_hits_per_zone reached for this place", "entry_area_refine = setup_tf keeps the models waiting",
                "never an E4 (b) on this candle", "E1 and E3 wait"):
        t = RG.to_mr(raw)
        assert RG.code_free(t), (raw, t)
    assert "retest" in RG.to_mr("never an E4 (b) on this candle")
    assert not RG.code_free("max_hits_per_zone") and not RG.code_free("an (b) tag")


def test_line_never_taken_from_after_the_decision(monkeypatch):
    from decision3 import trendline as TL
    seen = []

    def lines(V, t, degree=None):
        seen.append(t)
        return [{"id": "L1", "p1": [0, 100.0], "slope": 0.0}] if t == 99 else []
    monkeypatch.setattr(TL, "channel_lines", lines)
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    V = SimpleNamespace(m15=pd.DataFrame({"timestamp": range(100)}))
    assert RG.find_line(V, "L1", 40) is None and seen == [40]                  # only listed later ⇒ not drawn
