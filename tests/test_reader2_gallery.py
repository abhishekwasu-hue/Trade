"""Chart Reader v2 CR3 — gallery storage, candidate set, sealed test split, holdout guard, marking page (spec §5)."""
import ast
import builtins
import gzip
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from elliott.data_policy import HoldoutError
from gallery2 import candidates as GC
from gallery2 import data as GD
from gallery2 import schema as SC
from gallery2 import store as GS

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ helpers
def _daily(start, n, seed=1, base=1000.0):
    rng = np.random.default_rng(seed)
    ts = pd.bdate_range(start, periods=n)
    c = base + np.cumsum(rng.normal(0, 8, n)) + 60 * np.sin(np.arange(n) / 9.0)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(1, 6, n)
    lo = np.minimum(o, c) - rng.uniform(1, 6, n)
    return pd.DataFrame({"timestamp": ts, "open": o, "high": h, "low": lo, "close": c, "volume": 0.0})


def _cand(bars, cid=None, symbol="BANKNIFTY", tf="D", split="dev", source="banknifty_D", **kw):
    c = {"id": cid or SC.chart_id(symbol, tf, bars["timestamp"].iloc[0]), "symbol": symbol, "timeframe": tf, "source": source,
         "start": SC.ts_str(bars["timestamp"].iloc[0]), "end": SC.ts_str(bars["timestamp"].iloc[-1]), "n_bars": len(bars),
         "split": split, "calibration": True, "holdout_dates_exception": False, "origin": "auto", "n": 1}
    c.update(kw)
    return c


def _good(bars, cand):
    hi, lo = bars["high"].to_numpy(), bars["low"].to_numpy()
    a = int(np.argmin(lo[:40]))
    b = a + 5 + int(np.argmax(hi[a + 5:a + 40]))
    c = b + 3 + int(np.argmin(lo[b + 3:b + 30]))
    legs = SC.from_points(bars, [(a, "L"), (b, "H"), (c, "L")], ["impulse", "correction"])
    trend = [{"from_bar": 0, "from_ts": SC.ts_str(bars["timestamp"].iloc[0]), "state": "up"}]
    zones = [{"kind": "demand", "low": float(lo[c]), "high": float(lo[c]) + 5.0, "from_bar": c}]
    return SC.new_record(cand, legs, trend, zones, notes="t", now="2026-10-12 10:00")


class _Cur:
    def __init__(self, c):
        self.c = c.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?").replace("DEFAULT NOW()", "DEFAULT CURRENT_TIMESTAMP")
        return self.c.execute(sql, tuple(str(p) if not isinstance(p, (int, float, str, type(None))) else p for p in params))

    def fetchall(self):
        return self.c.fetchall()

    @property
    def rowcount(self):
        return self.c.rowcount


class _Conn:
    def __init__(self, c):
        self.c = c

    def cursor(self):
        return _Cur(self.c)

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()

    def close(self):
        pass


# ------------------------------------------------------------------ schema
def test_valid_record_passes_and_points_round_trip():
    bars = _daily("2018-01-01", 120)
    cand = _cand(bars)
    rec = _good(bars, cand)
    assert SC.validate(rec, cand, bars) == []
    pts, labels, broken = SC.to_points(rec["legs"])
    assert not broken and SC.from_points(bars, pts, labels) == rec["legs"]


@pytest.mark.parametrize("mutate,needle", [
    (lambda r: r["legs"][1].update(start_bar=r["legs"][0]["end_bar"] - 2), "overlap"),
    (lambda r: r["legs"][0].update(end_bar=r["legs"][0]["start_bar"]), "end_bar"),
    (lambda r: r["legs"][0].update(start_price=r["legs"][0]["start_price"] + 50.0), "नाही (tol"),
    (lambda r: r["legs"][1].update(label=None), "label"),
    (lambda r: r["legs"][0].update(end_bar=10_000), "window बाहेर"),
    (lambda r: r["trend"].append({"from_bar": 0, "state": "down"}), "वाढता"),
    (lambda r: r["trend"][0].update(state="bullish"), "state"),
    (lambda r: r["zones"][0].update(low=r["zones"][0]["high"] + 1), "low < high"),
    (lambda r: r["zones"][0].update(kind="pivot"), "kind"),
    (lambda r: r.update(split="test"), "split"),
    (lambda r: r["legs"][0].update(start_ts="2001-01-01"), "start_ts"),
    (lambda r: r.update(trend=[]), "किमान एक trend state"),
    (lambda r: r["zones"][0].update(from_bar=10_000), "zone 1: from_bar"),
])
def test_schema_rejects_bad_marking(mutate, needle):
    bars = _daily("2018-01-01", 120)
    cand = _cand(bars)
    rec = json.loads(json.dumps(_good(bars, cand)))
    mutate(rec)
    err = SC.validate(rec, cand, bars)
    assert err and any(needle in e for e in err), err


def test_price_tolerance_is_in_median_range_units():
    bars = _daily("2018-01-01", 120)
    cand = _cand(bars)
    rec = _good(bars, cand)
    tol = SC.PRICE_TOL_MR * SC.median_range(bars)
    rec["legs"][0]["start_price"] -= 0.9 * tol                           # low च्या थोडं खाली — चालतं
    assert SC.validate(rec, cand, bars) == []
    rec["legs"][0]["start_price"] -= 0.3 * tol
    assert SC.validate(rec, cand, bars)


# ------------------------------------------------------------------ holdout guard
def test_nifty_holdout_window_rejected_everywhere():
    with pytest.raises(HoldoutError):
        GD.window_allowed("NIFTY", "2024-03-20", "2024-04-10")
    with pytest.raises(HoldoutError):
        GD.window_allowed("NIFTY", "2026-06-01", "2026-06-20", exception=True)          # NIFTY ला अपवाद कधीच नाही
    with pytest.raises(HoldoutError):
        GD.window_allowed("NIFTY", "2026-10-09", "2026-10-12")                          # illustration ⇒ annotation फक्त
    assert GD.window_allowed("NIFTY", "2026-09-28", "2026-10-08")                       # golden (contaminated)
    with pytest.raises(HoldoutError):
        GD.window_allowed("BANKNIFTY", "2025-01-01", "2025-03-01")
    assert GD.window_allowed("BANKNIFTY", "2025-01-01", "2025-03-01", exception=True)
    bars = _daily("2025-01-01", 120)
    cand = _cand(bars, symbol="NIFTY", source="nifty_1m_golden")
    rec = _good(bars, cand)
    assert any("holdout" in e for e in SC.validate(rec, cand))


def _m1(days):
    ts = np.concatenate([pd.date_range(f"{d:%Y-%m-%d} 09:15", periods=375, freq="1min") for d in days])
    c = 22000 + np.cumsum(np.random.default_rng(3).normal(0, 1.5, len(ts)))
    return pd.DataFrame({"timestamp": pd.to_datetime(ts), "open": c, "high": c + 2, "low": c - 2, "close": c})


def test_load_window_never_returns_nifty_holdout_bars_even_with_warmup(tmp_path, monkeypatch):
    days = list(pd.bdate_range("2026-06-22", "2026-07-10"))                              # 22–30 June = holdout
    p = tmp_path / "upstox"
    p.mkdir()
    with gzip.open(p / "NIFTY_1m_2026-07-01_2026-10-08.csv.gz", "wt") as fh:
        _m1(days).to_csv(fh, index=False)
    monkeypatch.setenv("TRADE_DATA_DIR", str(tmp_path))
    GD._RAW.clear()
    raw = GD.load_source("nifty_1m_golden")
    assert raw["timestamp"].min() >= pd.Timestamp("2026-07-01")
    cand = {"id": "x", "symbol": "NIFTY", "timeframe": "15M", "source": "nifty_1m_golden", "start": "2026-07-03 09:15",
            "end": "2026-07-09 15:15"}
    w = GD.load_window(cand, warmup_bars=300)
    assert len(w) and w["timestamp"].min() >= pd.Timestamp("2026-07-01")
    assert GD.load_window(cand)["timestamp"].min() == pd.Timestamp("2026-07-03 09:15")
    bad = dict(cand, start="2026-06-24 09:15")
    with pytest.raises(HoldoutError):
        GD.load_window(bad)
    GD._RAW.clear()


def test_banknifty_rows_in_nifty_holdout_dates_dropped_unless_exception():
    d = _daily("2024-03-01", 80)
    kept = GD.policy_filter("BANKNIFTY", d)
    assert kept["timestamp"].max() < pd.Timestamp("2024-04-01")
    assert len(GD.policy_filter("BANKNIFTY", d, exception=True)) == len(d)


# ------------------------------------------------------------------ storage
def test_dir_store_round_trip_lock_and_no_split_move(tmp_path):
    bars = _daily("2018-01-01", 120)
    cand = _cand(bars)
    rec = _good(bars, cand)
    st = GS.DirStore(str(tmp_path))
    assert GS.save_record(st, rec, cand, bars)
    assert st.load_all() == {cand["id"]: dict(rec, revision=1)}
    with pytest.raises(GS.ConflictError):                                  # नवा समजून पुन्हा (revision 0) ⇒ lost update नाही
        st.save(dict(rec, notes="stale tab"))
    assert st.save(dict(rec, notes="edit"), expected_revision=1)
    with pytest.raises(GS.ConflictError):                                  # जुन्या revision वरून (दुसरा tab)
        st.save(dict(rec, notes="stale"), expected_revision=1)
    assert st.load_all()[cand["id"]]["notes"] == "edit" and st.load_all()[cand["id"]]["revision"] == 2
    with pytest.raises(GS.ConflictError):                                  # split कधीच बदलत नाही (test ⇄ dev)
        st.save(dict(rec, split="test"), expected_revision=2)
    assert (tmp_path / "dev" / f"{cand['id']}.json").exists() and not (tmp_path / "test").exists()


def test_save_record_refuses_invalid(tmp_path):
    bars = _daily("2018-01-01", 120)
    cand = _cand(bars)
    rec = _good(bars, cand)
    rec["legs"][1]["label"] = "wave"
    with pytest.raises(ValueError):
        GS.save_record(GS.DirStore(str(tmp_path)), rec, cand, bars)
    assert not any(tmp_path.rglob("*.json"))


def test_db_store_optimistic_lock_and_export(tmp_path):
    db = sqlite3.connect(":memory:")
    store = GS.DbStore(conn_factory=lambda: _Conn(db))
    b1, b2 = _daily("2018-01-01", 120, seed=1), _daily("2019-01-01", 120, seed=2)
    c1, c2 = _cand(b1, split="dev"), _cand(b2, split="test")
    r1, r2 = _good(b1, c1), _good(b2, c2)
    assert store.save(r1) and store.save(r2) and store.save(dict(r1, notes="edited"), expected_revision=1)
    with pytest.raises(GS.ConflictError):
        store.save(dict(r1, notes="other tab"), expected_revision=1)       # मधेच revision 2 झाली
    with pytest.raises(GS.ConflictError):
        store.save(dict(r1, notes="new?"))                                 # row आहे ⇒ insert नाही
    with pytest.raises(GS.ConflictError):
        store.save(dict(r2, split="dev"), expected_revision=1)             # test chart कधीच dev होत नाही
    got = store.load_all()
    assert got[c1["id"]]["notes"] == "edited" and got[c1["id"]]["revision"] == 2 and got[c2["id"]]["revision"] == 1
    assert got[c2["id"]]["split"] == "test"
    manifest = {"charts": [c1, c2]}
    bars = {c1["id"]: b1, c2["id"]: b2}
    got["UNKNOWN"] = dict(r1, id="UNKNOWN")
    res = GS.export_json(got, manifest, str(tmp_path), bars_for=lambda c: bars[c["id"]])
    assert (res["dev"], res["test"], res["full_check"], res["unknown"]) == (1, 1, 2, ["UNKNOWN"])
    on_disk = json.loads((tmp_path / "dev" / f"{c1['id']}.json").read_text(encoding="utf-8"))
    assert "revision" not in on_disk and on_disk["notes"] == "edited" and on_disk["legs"] == r1["legs"]
    assert (tmp_path / "test" / f"{c2['id']}.json").exists()


def test_db_load_failure_raises_not_empty():
    with pytest.raises(GS.StoreError):
        GS.DbStore(conn_factory=lambda: None).load_all()
    with pytest.raises(GS.StoreError):
        GS.DbStore(conn_factory=lambda: None).save(_good(_daily("2018-01-01", 120), _cand(_daily("2018-01-01", 120))))


def test_create_table_runs_once_per_store():
    db = sqlite3.connect(":memory:")
    seen = []

    class Spy(_Conn):
        def cursor(self):
            cur = _Cur(self.c)
            real = cur.execute

            def ex(sql, params=()):
                seen.append(sql.strip().split()[0])
                return real(sql, params)
            cur.execute = ex
            return cur
    store = GS.DbStore(conn_factory=lambda: Spy(db))
    b = _daily("2018-01-01", 120)
    c = _cand(b)
    store.save(_good(b, c))
    store.load_all()
    store.load_all()
    assert seen.count("CREATE") == 1


def test_export_removes_stale_files_and_fails_loudly(tmp_path, monkeypatch):
    b1, b2 = _daily("2018-01-01", 120, seed=1), _daily("2019-01-01", 120, seed=2)
    c1, c2 = _cand(b1, split="dev"), _cand(b2, split="test")
    m = {"charts": [c1, c2]}
    GS.export_json({c1["id"]: _good(b1, c1), c2["id"]: _good(b2, c2)}, m, str(tmp_path))
    (tmp_path / "dev" / "OLD_CHART.json").write_text("{}", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    res = GS.export_json({c1["id"]: _good(b1, c1)}, m, str(tmp_path))     # c2 DB मधून गेला, OLD_CHART manifest मध्ये नाही
    assert sorted(res["removed"]) == ["dev/OLD_CHART.json", f"test/{c2['id']}.json"]
    assert (tmp_path / "dev" / f"{c1['id']}.json").exists() and (tmp_path / "keep.txt").exists()
    bad = dict(_good(b1, c1), legs=[])
    bad["trend"] = []
    res = GS.export_json({c1["id"]: bad}, m, str(tmp_path))                # अवैध ⇒ आधीची वैध export तशीच
    assert c1["id"] in res["invalid"] and (tmp_path / "dev" / f"{c1['id']}.json").exists()

    def boom(path, rec):
        raise OSError("disk full")
    monkeypatch.setattr(GS, "_write", boom)
    with pytest.raises(GS.StoreError):
        GS.export_json({c1["id"]: _good(b1, c1)}, m, str(tmp_path))


def test_labels_dir_resolved_at_call_time_and_missing_folder_is_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("READER2_GALLERY_LABELS", raising=False)
    monkeypatch.setenv("TRADE_DATA_DIR", str(tmp_path / "td"))
    assert GS.labels_dir() == str(tmp_path / "td" / "reader2_gallery" / "labels")
    monkeypatch.setenv("READER2_GALLERY_LABELS", str(tmp_path / "lbl"))
    assert GS.labels_dir() == str(tmp_path / "lbl")
    with pytest.raises(GS.LabelsMissing):
        GS.calibration_labels({"charts": []})
    (tmp_path / "lbl").mkdir()
    assert GS.calibration_labels({"charts": []}) == {}


def test_export_skips_invalid_and_uses_manifest_split(tmp_path):
    b1 = _daily("2018-01-01", 120)
    c1 = _cand(b1, split="test")
    r1 = dict(_good(b1, c1), split="dev")                                  # नोंदीतला split manifest शी जुळत नाही
    res = GS.export_json({c1["id"]: r1}, {"charts": [c1]}, str(tmp_path))
    assert c1["id"] in res["invalid"] and not any(tmp_path.rglob("*.json"))


def test_progress_counts_marked_charts():
    b1, b2 = _daily("2018-01-01", 120, seed=1), _daily("2019-01-01", 120, seed=2)
    c1, c2 = _cand(b1, split="dev"), _cand(b2, split="test")
    pr = GS.progress({"charts": [c1, c2]}, {c1["id"]: _good(b1, c1), c2["id"]: dict(_good(b2, c2), legs=[])})
    assert pr == {"marked": 1, "total": 2, "dev": (1, 1), "test": (0, 1)}


# ------------------------------------------------------------------ sealed test split
def _exported(tmp_path):
    b = [_daily(f"{2016 + i}-01-01", 120, seed=i) for i in range(4)]
    cs = [_cand(b[0], split="dev"), _cand(b[1], split="dev", calibration=False), _cand(b[2], split="test"), _cand(b[3], split="test")]
    m = {"charts": cs}
    GS.export_json({c["id"]: _good(bb, c) for c, bb in zip(cs, b)}, m, str(tmp_path))
    return m, cs


def test_calibration_never_loads_test_labels(tmp_path, monkeypatch):
    m, cs = _exported(tmp_path)
    opened = []
    real_open = builtins.open

    def spy(f, *a, **k):
        opened.append(str(f))
        return real_open(f, *a, **k)
    monkeypatch.setattr(builtins, "open", spy)
    cal = GS.calibration_labels(m, str(tmp_path))
    monkeypatch.setattr(builtins, "open", real_open)
    assert set(cal) == {cs[0]["id"]}                                       # calibration: false (Abhi case) वगळला
    assert opened and not any(os.sep + "test" + os.sep in f for f in opened)
    assert set(GS.load_labels(m, "dev_report", str(tmp_path))) == {cs[0]["id"], cs[1]["id"]}
    assert set(GS.load_labels(m, "acceptance", str(tmp_path))) == {cs[2]["id"], cs[3]["id"]}
    with pytest.raises(ValueError):
        GS.load_labels(m, "tuning", str(tmp_path))


def test_test_label_smuggled_into_dev_folder_raises(tmp_path):
    m, cs = _exported(tmp_path)
    src = tmp_path / "test" / f"{cs[2]['id']}.json"
    (tmp_path / "dev" / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(GS.SealedTestError):
        GS.calibration_labels(m, str(tmp_path))


def test_no_calibration_code_reads_acceptance_labels():
    """reader2 (calibration इथेच होईल) acceptance / test labels कधीच मागत नाही."""
    for p in list((ROOT / "reader2").glob("*.py")):
        src = p.read_text(encoding="utf-8")
        assert "acceptance" not in src and "labels/test" not in src and "load_labels" not in src, p.name


def test_gallery_does_not_import_reader_or_engine():
    banned = {"reader2", "decision3", "decision2", "vision", "vision2", "vision_led", "bots_common", "order_execution", "broker_factory"}
    for p in list((ROOT / "gallery2").glob("*.py")) + [ROOT / "page_reader2_gallery.py", ROOT / "scripts" / "reader2_gallery_candidates.py",
                                                       ROOT / "scripts" / "reader2_gallery_export.py"]:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
        assert not mods & banned, (p.name, mods & banned)


# ------------------------------------------------------------------ candidate builder
def _slots():
    out = []
    for i, (sym, tf, src, start, n) in enumerate([("NIFTY", "D", "nifty_1m_repo", "2015-01-01", 1700),
                                                  ("NIFTY", "1H", "nifty_1m_repo", "2016-01-01", 4200),
                                                  ("BANKNIFTY", "D", "banknifty_D", "2016-10-10", 2600)]):
        b = _daily(start, n, seed=10 + i)
        if tf == "1H":
            b["timestamp"] = [pd.Timestamp("2016-01-04 09:15") + pd.Timedelta(days=k // 7, hours=k % 7) for k in range(n)]
        out.append({"symbol": sym, "timeframe": tf, "source": src, "bars": b, "rule": "synthetic"})
    return out


def _cases():
    b = _daily("2025-11-03", 200, seed=99)
    return [{"key": "bn_case", "symbol": "BANKNIFTY", "timeframe": "D", "source": "banknifty_D", "bars": b, "note": "n",
             "holdout_dates_exception": True}]


def test_builder_is_deterministic_and_splits_28_12():
    a = GC.build(_slots(), _cases(), seed=7, missing=[{"symbol": "SENSEX", "timeframe": "D", "why": "none"}])
    b = GC.build(_slots(), _cases(), seed=7, missing=[{"symbol": "SENSEX", "timeframe": "D", "why": "none"}])
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    assert (a["n_total"], a["n_dev"], a["n_test"], a["seed"]) == (40, 28, 12, 7)
    c = GC.build(_slots(), _cases(), seed=8)
    assert {x["id"] for x in c["charts"] if x["split"] == "test"} != {x["id"] for x in a["charts"] if x["split"] == "test"}
    case = [x for x in a["charts"] if x["origin"] == "abhi_case"]
    assert len(case) == 1 and case[0]["split"] == "dev" and case[0]["calibration"] is False and case[0]["holdout_dates_exception"]
    assert a["missing"][0]["symbol"] == "SENSEX"


def test_builder_windows_respect_policy_and_never_overlap_within_tf():
    m = GC.build(_slots(), _cases(), seed=3)
    for c in m["charts"]:
        GD.window_allowed(c["symbol"], c["start"], c["end"], exception=c["holdout_dates_exception"])
        if c["origin"] == "auto":
            assert not c["holdout_dates_exception"] and c["calibration"]
            assert not (pd.Timestamp(c["start"]) < GD.DP.CONTAMINATED_START and pd.Timestamp(c["end"]) >= GD.DP.HOLDOUT_START)
    by = {}
    for c in m["charts"]:
        by.setdefault((c["symbol"], c["timeframe"]), []).append(c)
    for cs in by.values():
        cs.sort(key=lambda c: c["start"])
        assert all(pd.Timestamp(x["end"]) < pd.Timestamp(y["start"]) for x, y in zip(cs, cs[1:]))


def test_shape_tags_are_descriptive_only():
    n = 120
    up = np.linspace(100, 200, n)
    b = pd.DataFrame({"timestamp": pd.bdate_range("2017-01-02", periods=n), "open": up - 0.5, "high": up + 1, "low": up - 1, "close": up + 0.5})
    tags, stats = GC.shape(b)
    assert "up" in tags and "impulse" in tags and stats["net_over_span"] > 0.9
    flat = 100 + 5 * np.sin(2 * np.pi * np.arange(n) / 20.0)               # 6 पूर्ण फेरे ⇒ net ≈ 0
    tags, stats = GC.shape(b.assign(open=flat, high=flat + 1, low=flat - 1, close=flat))
    assert tags == ["range"] and stats["max_counter_depth"] is None


# ------------------------------------------------------------------ committed manifest
def test_committed_manifest_is_sound():
    m = GS.load_manifest(GS.MANIFEST)
    cs = m["charts"]
    old = [c for c in cs if c["symbol"] in ("NIFTY", "BANKNIFTY")]
    assert len(old) == 40 and sum(c["split"] == "test" for c in old) == 12 and "seed" in m
    assert (m["n_total"], m["n_dev"], m["n_test"]) == (len(cs), sum(c["split"] == "dev" for c in cs), sum(c["split"] == "test" for c in cs))
    assert len({c["id"] for c in cs}) == len(cs) and [c["n"] for c in cs] == list(range(1, len(cs) + 1))
    for c in cs:
        GD.window_allowed(c["symbol"], c["start"], c["end"], exception=c["holdout_dates_exception"])
        if c["symbol"] == "NIFTY":
            assert not c["holdout_dates_exception"]
            assert GD.DP.period(c["start"]) in ("IS", "CONTAMINATED") and GD.DP.period(c["end"]) in ("IS", "CONTAMINATED")
    cases = {c.get("case") for c in cs if c["origin"] == "abhi_case"}
    assert cases == {"banknifty_sharp_fall_abc_down", "nifty_flat_c_wave"}
    assert all(c["split"] == "dev" and not c["calibration"] for c in cs if c["origin"] == "abhi_case")
    sx = [c for c in cs if c["symbol"] == "SENSEX"]
    if sx:                                                                  # VPS additive step नंतर: SENSEX चा स्वतःचा 70/30 stratum
        assert 10 <= len(sx) <= 13 and m["strata"]["SENSEX"]["assignment"] == "stratified_70_30"
        assert sum(c["split"] == "test" for c in sx) == GC.stratum_test_count(len(sx)) == m["strata"]["SENSEX"]["test"]
        assert all(c["origin"] == "auto" and c["calibration"] for c in sx)
    else:
        assert {x["symbol"] for x in m["missing"]} == {"SENSEX"}
    for a in cs:
        for b in cs:
            if a["split"] == "test" and b["split"] == "dev" and (a["symbol"], a["timeframe"]) == (b["symbol"], b["timeframe"]):
                assert pd.Timestamp(a["end"]) < pd.Timestamp(b["start"]) or pd.Timestamp(b["end"]) < pd.Timestamp(a["start"])


def test_manifest_windows_load_and_accept_a_marking():
    """Data असेल तिथे (NIFTY IS repo मध्ये; बाकी trade-data) प्रत्येk chart चे bars = n_bars आणि साधी marking validate होते."""
    m = GS.load_manifest(GS.MANIFEST)
    done = 0
    for c in m["charts"]:
        try:
            bars = GD.load_window(c)
        except GD.DataMissing:
            continue
        assert len(bars) == c["n_bars"] and SC.ts_str(bars["timestamp"].iloc[0]) == c["start"]
        if c["symbol"] == "NIFTY":
            assert not ((bars["timestamp"] >= GD.DP.HOLDOUT_START) & (bars["timestamp"] < GD.DP.CONTAMINATED_START)).any()
        legs = [SC.leg(bars, 0, len(bars) - 1, "uncertain")]
        rec = SC.new_record(c, legs, [{"from_bar": 0, "from_ts": SC.ts_str(bars["timestamp"].iloc[0]), "state": "range"}])
        assert SC.validate(rec, c, bars) == [], c["id"]
        done += 1
    if not done:
        pytest.skip("gallery data नाही")


# ------------------------------------------------------------------ marking page (headless)
def _page_app():
    import page_reader2_gallery as page
    page.render()


def _page_setup(tmp_path, monkeypatch, store="dir", extra=()):
    """BANKNIFTY Daily synthetic CSV (240 bars) ⇒ chart A = bars 0–119, B = 120–239 (+ `extra` cands)."""
    from streamlit.testing.v1 import AppTest
    allb = _daily("2018-01-01", 240, seed=5)
    (tmp_path / "td" / "banknifty").mkdir(parents=True)
    with gzip.open(tmp_path / "td" / "banknifty" / "BANKNIFTY_D.csv.gz", "wt") as fh:
        allb.drop(columns=["volume"]).to_csv(fh, index=False)
    bars = allb.iloc[:120].reset_index(drop=True)
    cand = _cand(bars)
    cand_b = _cand(allb.iloc[120:].reset_index(drop=True), split="test")
    cands = [cand, cand_b] + list(extra)
    (tmp_path / "manifest.json").write_text(json.dumps({"charts": cands, "missing": [{"symbol": "SENSEX", "timeframe": "D"}]}),
                                            encoding="utf-8")
    monkeypatch.setenv("TRADE_DATA_DIR", str(tmp_path / "td"))
    monkeypatch.setenv("READER2_GALLERY_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("READER2_GALLERY_STORE", str(tmp_path / "store") if store == "dir" else store)
    GD._RAW.clear()
    return AppTest.from_function(_page_app, default_timeout=60), bars, cand


def _add(at, cid, bar, kind):
    at.number_input(key=f"g2_bar_{cid}").set_value(int(bar)).run()
    at.radio(key=f"g2_hl_{cid}").set_value(kind).run()
    at.button(key=f"g2_add_{cid}").click().run()


def _edit(at, cid, **kw):
    """Tables (data_editor) AppTest मधून भरता येत नाहीत ⇒ state थेट + nonce / rev वाढवून तक्ते त्यातून पुन्हा बनवतो."""
    s = at.session_state["g2_state"][cid]
    s.update(kw)
    s["nonce"] += 1
    s["rev"] += 1


def _pivots(bars):
    lo, hi = bars["low"].to_numpy(), bars["high"].to_numpy()
    a = int(np.argmin(lo[:40]))
    b = a + 5 + int(np.argmax(hi[a + 5:a + 40]))
    return a, b


def test_page_renders_and_adds_points_without_error(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    at.run()
    assert not at.exception, at.exception
    assert any(mt.value == "0/2" for mt in at.metric)
    lo = int(np.argmin(bars["low"].to_numpy()[:40]))
    at.number_input(key=f"g2_bar_{cand['id']}").set_value(lo).run()
    at.radio(key=f"g2_hl_{cand['id']}").set_value("L").run()
    at.button(key=f"g2_add_{cand['id']}").click().run()
    hi = lo + 5 + int(np.argmax(bars["high"].to_numpy()[lo + 5:lo + 40]))
    at.number_input(key=f"g2_bar_{cand['id']}").set_value(hi).run()
    at.radio(key=f"g2_hl_{cand['id']}").set_value("H").run()
    at.button(key=f"g2_add_{cand['id']}").click().run()
    assert not at.exception, at.exception
    assert at.session_state["g2_state"][cand["id"]]["points"] == [(lo, "L"), (hi, "H")]
    at.button(key=f"g2_save_{cand['id']}").click().run()                  # label नाही ⇒ जतन नाही
    assert at.error and not list((tmp_path / "store").rglob("*.json"))
    GD._RAW.clear()


def test_page_shows_saved_marking(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    GS.DirStore(str(tmp_path / "store")).save(_good(bars, cand))
    at.run()
    assert not at.exception, at.exception
    assert any(mt.value == "1/2" for mt in at.metric)
    assert len(at.session_state["g2_state"][cand["id"]]["points"]) == 3
    GD._RAW.clear()


def test_page_labels_trend_save_and_reload_round_trip(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    cid = cand["id"]
    at.run()
    a, b = _pivots(bars)
    _add(at, cid, a, "L")
    _add(at, cid, b, "H")
    zl = float(bars["low"].iloc[a])
    _edit(at, cid, labels=["impulse"], notes="round trip",
          trend=[{"from_bar": 30, "state": "up"}, {"from_bar": 0, "state": "down"}],          # क्रम उलटा ⇒ save वेळी क्रमाने
          zones=[{"kind": "demand", "low": zl, "high": zl + 5.0, "from_bar": None}])
    at.run()
    at.button(key=f"g2_save_{cid}").click().run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert at.success
    saved = GS.DirStore(str(tmp_path / "store")).load_all()[cid]
    assert saved["revision"] == 1 and saved["notes"] == "round trip"
    assert saved["legs"] == SC.from_points(bars, [(a, "L"), (b, "H")], ["impulse"])
    assert [(t["from_bar"], t["state"]) for t in saved["trend"]] == [(0, "down"), (30, "up")]
    assert saved["zones"] == [{"kind": "demand", "low": zl, "high": zl + 5.0}]
    at.button(key=f"g2_reload_{cid}").click().run()                        # पुन्हा उघडलं ⇒ तेच
    s = at.session_state["g2_state"][cid]
    assert s["points"] == [(a, "L"), (b, "H")] and s["labels"] == ["impulse"] and s["revision"] == 1
    assert [(t["from_bar"], t["state"]) for t in s["trend"]] == [(0, "down"), (30, "up")]
    _edit(at, cid, notes="second")
    at.run()
    at.button(key=f"g2_save_{cid}").click().run()                          # edit ⇒ revision 2
    assert not at.error, [e.value for e in at.error]
    again = GS.DirStore(str(tmp_path / "store")).load_all()[cid]
    assert again["revision"] == 2 and again["notes"] == "second" and again["legs"] == saved["legs"]
    GD._RAW.clear()


def test_page_placeholder_trend_needs_state_then_saves(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    cid = cand["id"]
    at.run()
    a, b = _pivots(bars)
    _add(at, cid, a, "L")
    _add(at, cid, b, "H")
    _edit(at, cid, labels=["impulse"])                                     # trend = default placeholder (state नाही)
    at.run()
    at.button(key=f"g2_save_{cid}").click().run()
    assert any("किमान एक trend state" in e.value for e in at.error)
    _edit(at, cid, trend=[{"from_bar": 0, "state": "up"}])                 # placeholder ला state दिला ⇒ चालतं
    at.run()
    at.button(key=f"g2_save_{cid}").click().run()
    assert not at.error and at.success
    GD._RAW.clear()


def test_page_save_conflict_is_reported(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    cid = cand["id"]
    store = GS.DirStore(str(tmp_path / "store"))
    store.save(_good(bars, cand))
    at.run()
    store.save(dict(_good(bars, cand), notes="other device"), expected_revision=1)   # मधेच दुसरीकडे जतन (revision 2)
    _edit(at, cid, notes="mine")
    at.run()
    at.button(key=f"g2_save_{cid}").click().run()
    assert any("दुसरीकडे" in e.value for e in at.error)
    assert store.load_all()[cid]["notes"] == "other device"
    GD._RAW.clear()


def test_page_switching_charts_rebuilds_tables_from_state(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    a_id = cand["id"]
    at.run()
    _edit(at, a_id, trend=[{"from_bar": 3, "state": "up"}], zones=[{"kind": "supply", "low": 1.0, "high": 2.0, "from_bar": None}])
    at.run()
    rev_a = at.session_state["g2_state"][a_id]["rev"]
    ids = list(GS.charts(GS.load_manifest()))
    at.selectbox(key="g2_chart").set_value(ids[1]).run()
    at.selectbox(key="g2_chart").set_value(a_id).run()
    assert not at.exception
    s = at.session_state["g2_state"][a_id]
    assert s["rev"] > rev_a                                                # नवे तक्ते (जुने widget deltas नाहीत)
    assert s["trend"] == [{"from_bar": 3, "state": "up"}] and s["zones"][0]["kind"] == "supply"
    GD._RAW.clear()


def test_page_load_failure_disables_saving(tmp_path, monkeypatch):
    def fail(self):
        raise GS.StoreError("db down")
    monkeypatch.setattr(GS.DbStore, "load_all", fail)
    at, bars, cand = _page_setup(tmp_path, monkeypatch, store="db")
    at.run()
    assert not at.exception and any("Save बंद" in e.value for e in at.error)
    assert not [b for b in at.button if b.key and b.key.startswith("g2_save_")]
    GD._RAW.clear()


def test_page_empty_window_shows_error(tmp_path, monkeypatch):
    empty = {**_cand(_daily("2010-01-04", 30)), "n": 3}                       # CSV 2018 पासून ⇒ 2010 window मध्ये candles नाहीत
    at, bars, cand = _page_setup(tmp_path, monkeypatch, extra=[empty])
    at.run()
    at.selectbox(key="g2_chart").set_value(empty["id"]).run()
    assert not at.exception and any("एकही candle नाही" in e.value for e in at.error)
    assert not at.number_input
    GD._RAW.clear()


def test_page_split_mismatch_blocks_save(tmp_path, monkeypatch):
    at, bars, cand = _page_setup(tmp_path, monkeypatch)
    rec = dict(_good(bars, cand), split="test")                            # manifest म्हणतो dev
    (tmp_path / "store" / "test").mkdir(parents=True)
    (tmp_path / "store" / "test" / f"{cand['id']}.json").write_text(json.dumps(dict(rec, revision=1)), encoding="utf-8")
    at.run()
    assert any("split" in e.value and "Save बंद" in e.value for e in at.error)
    assert at.button(key=f"g2_save_{cand['id']}").disabled
    assert any("split 'test'" in e for e in SC.validate(rec, cand, bars))
    GD._RAW.clear()


def test_candidates_script_refuses_to_overwrite_manifest(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("r2gc", ROOT / "scripts" / "reader2_gallery_candidates.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / "manifest.json"
    out.write_text('{"charts": []}', encoding="utf-8")
    assert mod.main(["--out", str(out)]) == 2
    assert out.read_text(encoding="utf-8") == '{"charts": []}'


def test_golden_nifty_file_is_discovered_by_pattern(tmp_path, monkeypatch):
    up = tmp_path / "upstox"
    up.mkdir()
    for f in ("NIFTY_1m_2026-07-01_2026-10-06.csv.gz", "NIFTY_1m_2026-07-01_2026-10-08.csv.gz",
              "NIFTY_1m_illustration_2026-10-09_2026-10-09.csv.gz", "BANKNIFTY_1m_2026-07-01_2026-12-31.csv.gz"):
        (up / f).write_bytes(b"")
    monkeypatch.setenv("TRADE_DATA_DIR", str(tmp_path))
    assert GD.source_path("nifty_1m_golden").endswith("NIFTY_1m_2026-07-01_2026-10-08.csv.gz")


def test_golden_file_picker_prefers_full_coverage_and_skips_holdout_start(tmp_path, monkeypatch):
    """Verify review 🟡: same end date ⇒ the file with the EARLIEST start wins (an incremental file never hides older bars);
    a NIFTY file starting inside the holdout is never picked."""
    from gallery2 import data as GD
    from elliott import data_policy as DP
    up = tmp_path / "upstox"
    up.mkdir()
    hs = DP.HOLDOUT_START
    late = (DP.CONTAMINATED_START + pd.Timedelta(days=95)).date()
    mid = (DP.CONTAMINATED_START + pd.Timedelta(days=30)).date()
    full = f"NIFTY_1m_{DP.CONTAMINATED_START.date()}_{late}.csv.gz"
    incr = f"NIFTY_1m_{mid}_{late}.csv.gz"
    held = f"NIFTY_1m_{(hs + pd.Timedelta(days=5)).date()}_{(DP.CONTAMINATED_START + pd.Timedelta(days=200)).date()}.csv.gz"
    for f in (full, incr, held):
        (up / f).write_bytes(b"")
    monkeypatch.setattr(GD, "trade_data_dir", lambda: str(tmp_path))
    assert os.path.basename(GD.source_path("nifty_1m_golden")) == full


# ------------------------------------------------------------------ symbol strata (Abhi 2026-10-12: SENSEX, stratified 70/30)
NB_DIGEST = "be1c32269c958cbbc3278ca9ed7465fa9146cbc24340ef08199023c399437e38"   # CR3 NIFTY / BANKNIFTY entries (Abhi marking चालू)


def _intraday(start_day, n_days, minutes, seed):
    per = {15: 25, 60: 7}[minutes]
    days = pd.bdate_range(start_day, periods=n_days)
    ts = [d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=minutes * k) for d in days for k in range(per)]
    b = _daily("2022-01-03", len(ts), seed=seed, base=60000.0)
    b["timestamp"] = ts
    return b


def _sensex_slots():
    return [{"symbol": "SENSEX", "timeframe": "D", "source": "sensex_D", "bars": _daily("2012-01-02", 1000, seed=41, base=60000.0),
             "rule": "synthetic"},
            {"symbol": "SENSEX", "timeframe": "1H", "source": "sensex_1H", "bars": _intraday("2022-01-03", 250, 60, 42), "rule": "synthetic"},
            {"symbol": "SENSEX", "timeframe": "15M", "source": "sensex_15M", "bars": _intraday("2022-01-03", 60, 15, 43), "rule": "synthetic"}]


def _nb_bytes(m):
    return [GC.entry_bytes(c) for c in m["charts"] if c["symbol"] in ("NIFTY", "BANKNIFTY")]


def test_regenerating_with_extra_symbol_leaves_existing_entries_byte_identical():
    base = GC.build(_slots(), _cases(), seed=7, missing=[{"symbol": "SENSEX", "timeframe": t, "why": "none"} for t in GD.TIMEFRAMES])
    before = json.dumps(base, ensure_ascii=False, sort_keys=True)
    m = GC.add_symbol(base, "SENSEX", _sensex_slots(), missing=[])
    assert json.dumps(base, ensure_ascii=False, sort_keys=True) == before                     # base dict बदलला नाही
    assert _nb_bytes(m) == _nb_bytes(base) and len(_nb_bytes(m)) == 40
    sx = [c for c in m["charts"] if c["symbol"] == "SENSEX"]
    assert len(sx) == 13 and {c["timeframe"] for c in sx} == {"D", "1H", "15M"}
    assert sum(c["split"] == "test" for c in sx) == 4 and m["strata"]["SENSEX"] == {
        "seed": GC.symbol_seed(7, "SENSEX"), "dev": 9, "test": 4, "assignment": "stratified_70_30"}
    assert m["strata"]["NIFTY"]["assignment"] == "global_split" and not [x for x in m["missing"] if x["symbol"] == "SENSEX"]
    assert GC.strata_of(GS.load_manifest(GS.MANIFEST))["NIFTY"]["assignment"] == "cr3_global_frozen"
    assert [c["n"] for c in m["charts"]] == list(range(1, len(m["charts"]) + 1))
    assert (m["n_total"], m["n_test"]) == (53, 16) and m["counts"]["SENSEX"] == {"D": 5, "1H": 4, "15M": 4}
    again = GC.add_symbol(base, "SENSEX", _sensex_slots(), missing=[])                       # deterministic
    assert [GC.entry_bytes(c) for c in again["charts"]] == [GC.entry_bytes(c) for c in m["charts"]]
    for c in sx:                                                                               # policy: NIFTY-holdout तारखा नाहीत
        GD.window_allowed("SENSEX", c["start"], c["end"])
    with pytest.raises(ValueError):
        GC.add_symbol(m, "SENSEX", _sensex_slots())


def test_add_symbol_to_committed_manifest_keeps_nifty_banknifty_bytes():
    base = GS.load_manifest(GS.MANIFEST)
    assert hashlib.sha256("\n".join(_nb_bytes(base)).encode("utf-8")).hexdigest() == NB_DIGEST
    assert {s: (v["dev"], v["test"]) for s, v in base["strata"].items() if s != "SENSEX"} == {"NIFTY": (16, 7), "BANKNIFTY": (12, 5)}
    if any(c["symbol"] == "SENSEX" for c in base["charts"]):
        pytest.skip("SENSEX आधीच manifest मध्ये")
    m = GC.add_symbol(base, "SENSEX", _sensex_slots(), missing=[])
    assert _nb_bytes(m) == _nb_bytes(base)
    assert [GC.entry_bytes(c) for c in m["charts"][:len(base["charts"])]] == [GC.entry_bytes(c) for c in base["charts"]]
    assert {s: (v["dev"], v["test"]) for s, v in m["strata"].items()} == {"NIFTY": (16, 7), "BANKNIFTY": (12, 5), "SENSEX": (9, 4)}


def test_stratum_split_counts_and_new_charts_stay_in_their_stratum():
    assert [GC.stratum_test_count(n) for n in (10, 11, 12, 13, 17, 23)] == [3, 3, 4, 4, 5, 7]
    m = GC.build(_slots(), _cases(), seed=7)
    bn = [c for c in m["charts"] if c["symbol"] == "BANKNIFTY"]
    new = [dict(c, id=c["id"] + "X", split=None) for c in bn[-4:]]
    test = GC.stratum_split(bn, new, GC.symbol_seed(7, "BANKNIFTY"))
    assert test <= {c["id"] for c in new}
    assert len(test) == GC.stratum_test_count(len(bn) + 4) - sum(c["split"] == "test" for c in bn)


def test_add_symbol_script_writes_out_or_leaves_manifest_unchanged(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("r2gc2", ROOT / "scripts" / "reader2_gallery_candidates.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    base = tmp_path / "manifest.json"
    base.write_bytes(Path(GS.MANIFEST).read_bytes())
    raw = base.read_bytes()
    out = tmp_path / "td" / "reader2_gallery" / "manifest_sensex_add.json"
    miss = [{"symbol": "SENSEX", "timeframe": t, "why": "sensex/SENSEX_D.csv.gz नाही"} for t in GD.TIMEFRAMES]
    rc = mod.main(["--add-symbol", "SENSEX", "--base", str(base), "--out", str(out)], inputs=([], [], miss))
    assert rc == 3 and not out.exists() and base.read_bytes() == raw and "बदलला नाही" in capsys.readouterr().out
    if any(c["symbol"] == "SENSEX" for c in GS.load_manifest(str(base))["charts"]):
        return
    rc = mod.main(["--add-symbol", "SENSEX", "--base", str(base), "--out", str(out)], inputs=(_sensex_slots(), [], []))
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0 and base.read_bytes() == raw and printed["new_charts"] == 13 and printed["test"] == 4
    assert _nb_bytes(GS.load_manifest(str(out))) == _nb_bytes(GS.load_manifest(str(base)))


def test_real_inputs_without_sensex_files_reports_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADE_DATA_DIR", str(tmp_path))
    GD._RAW.clear()
    slots, cases, missing = GC.real_inputs(symbols=["SENSEX"])
    assert slots == [] and cases == [] and {(x["symbol"], x["timeframe"]) for x in missing} == {("SENSEX", t) for t in GD.TIMEFRAMES}
    assert GD.source_path("sensex_15M") == str(tmp_path / "sensex" / "SENSEX_15M.csv.gz")


# ------------------------------------------------------------------ Abhi seed labels (CD14) ⇒ store
def test_import_seeds_validates_and_never_overwrites(tmp_path):
    bars = _daily("2018-01-01", 120, seed=5)
    c1 = _cand(bars, split="dev")
    c2 = _cand(bars, cid="BANKNIFTY_D_OTHER", split="test")
    manifest = {"charts": [c1, c2]}
    seeds = GS.DirStore(str(tmp_path / "seeds"))
    GS.save_record(seeds, _good(bars, c1), c1, bars)
    GS.save_record(seeds, _good(bars, c2), c2, bars)
    GS._write(str(tmp_path / "seeds" / "dev" / "UNKNOWN_CHART.json"), dict(_good(bars, c1), id="UNKNOWN_CHART"))
    target = GS.DirStore(str(tmp_path / "store"))
    GS.save_record(target, dict(_good(bars, c2), notes="Abhi"), c2, bars)                 # Abhi ची आधीची marking
    res = GS.import_seeds(target, manifest, str(tmp_path / "seeds"), bars_for=lambda c: bars)
    assert res["imported"] == [c1["id"]] and res["skipped_existing"] == [c2["id"]] and res["unknown"] == ["UNKNOWN_CHART"]
    got = target.load_all()
    assert got[c2["id"]]["notes"] == "Abhi" and got[c2["id"]]["revision"] == 1 and got[c1["id"]]["revision"] == 1
    again = GS.import_seeds(target, manifest, str(tmp_path / "seeds"), bars_for=lambda c: bars)
    assert again["imported"] == [] and sorted(again["skipped_existing"]) == sorted([c1["id"], c2["id"]])
    wrong = GS.DirStore(str(tmp_path / "seeds2"))
    rec = dict(_good(bars, c1), split="test")                                             # manifest म्हणतो dev
    GS._write(wrong.path(rec), rec)
    res = GS.import_seeds(GS.DirStore(str(tmp_path / "s3")), manifest, str(tmp_path / "seeds2"), bars_for=lambda c: bars)
    assert res["imported"] == [] and c1["id"] in res["invalid"]


def test_seed_script_dry_run_writes_nothing(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("r2seed", ROOT / "scripts" / "reader2_gallery_seed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    target = GS.DirStore(str(tmp_path / "store"))
    assert mod.main(["--seeds", str(tmp_path / "none")], store=target) == 3
    (tmp_path / "seeds" / "dev").mkdir(parents=True)
    assert mod.main(["--seeds", str(tmp_path / "seeds"), "--dry-run"], store=target) == 0
    assert target.load_all() == {}


def test_cd14_seed_record_validates_when_trade_data_present():
    """Private seed (trade-data, repo मध्ये नाही): Abhi चा CD14 leg = एकच DOWN impulse, dev chart, manifest शी जुळतो."""
    p = Path(GS.seeds_dir()) / "dev" / "BANKNIFTY_D_20251215.json"
    if not p.exists():
        pytest.skip("trade-data seed नाही")
    rec = json.loads(p.read_text(encoding="utf-8"))
    cand = GS.charts(GS.load_manifest(GS.MANIFEST))[rec["id"]]
    try:
        bars = GD.load_window(cand)
    except GD.DataMissing:
        bars = None
    assert SC.validate({k: v for k, v in rec.items() if k != "revision"}, cand, bars) == []
    lg = rec["legs"]
    assert len(lg) == 1 and lg[0]["label"] == "impulse" and lg[0]["end_price"] < lg[0]["start_price"]
    assert cand["split"] == "dev" and cand["calibration"] is False and "CD14" in rec["source"]


def test_import_seeds_continues_after_a_conflict(tmp_path):
    bars = _daily("2018-01-01", 120, seed=5)
    c1, c2 = _cand(bars, cid="BANKNIFTY_D_A"), _cand(bars, cid="BANKNIFTY_D_B")
    seeds = GS.DirStore(str(tmp_path / "seeds"))
    for c in (c1, c2):
        GS.save_record(seeds, _good(bars, c), c, bars)

    class Racy(GS.DirStore):                                                           # load नंतर, save आधी दुसऱ्या tab ने जतन
        def save(self, rec, expected_revision=0):
            if rec["id"] == c1["id"]:
                raise GS.ConflictError("मधेच जतन")
            return super().save(rec, expected_revision)

    target = Racy(str(tmp_path / "store"))
    res = GS.import_seeds(target, {"charts": [c1, c2]}, str(tmp_path / "seeds"), bars_for=lambda c: bars)
    assert res["imported"] == [c2["id"]] and list(res["failed"]) == [c1["id"]] and "ConflictError" in res["failed"][c1["id"]]
    assert set(target.load_all()) == {c2["id"]}
    import importlib.util
    spec = importlib.util.spec_from_file_location("r2seed2", ROOT / "scripts" / "reader2_gallery_seed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mpath = tmp_path / "m.json"
    mpath.write_text(json.dumps({"charts": [c1, c2]}), encoding="utf-8")
    GD._RAW.clear()
    rc = mod.main(["--seeds", str(tmp_path / "seeds"), "--manifest", str(mpath)], store=Racy(str(tmp_path / "store2")))
    assert rc == 1
