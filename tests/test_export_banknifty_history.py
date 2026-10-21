"""scripts/export_banknifty_history.py on a tiny synthetic bot folder (no real data): BANKNIFTY only, read-only on the bot's files,
never overwrites, refuses market hours / a folder inside the repo / a non-data pickle / a non-BANKNIFTY FUT contract, reports gaps and
missing FUT-volume days, same rows ⇒ same sha256, and makes no network call."""
import gzip
import hashlib
import json
import os
import pickle
import socket
import sqlite3

import pandas as pd
import pytest

from scripts import export_banknifty_history as X

AFTER_CLOSE = "2026-10-21 18:00"
NIFTY_MARK = 11111.0                     # every NIFTY row carries this price ⇒ it must never appear in an output


def _bars(day, minutes, n, price, vol=1, tz=False):
    t0 = pd.Timestamp(f"{day} 09:15")
    rows = []
    for i in range(n):
        ts = t0 + pd.Timedelta(minutes=minutes * i)
        rows.append([ts.strftime("%Y-%m-%dT%H:%M:%S+05:30") if tz else ts, price, price + 1, price - 1, price, vol, 0])
    return rows


def _bot(tmp_path):
    root = tmp_path / "bot"
    (root / "data" / "engine3_cache").mkdir(parents=True)
    bn_1m = _bars("2026-10-15", 1, 375, 50000.0, tz=True) + _bars("2026-10-16", 1, 300, 50010.0, tz=True)   # 16 Oct incomplete
    with open(root / "data" / "engine3_cache" / "hist_NSE_INDEX_Nifty_Bank_1minute_90_2026-10-19_2026-10-16.pkl", "wb") as f:
        pickle.dump(bn_1m, f)
    with open(root / "data" / "engine3_cache" / "hist_NSE_INDEX_Nifty_50_1minute_90_2026-10-19_2026-10-16.pkl", "wb") as f:
        pickle.dump(_bars("2026-10-15", 1, 375, NIFTY_MARK, tz=True), f)
    cols = ["timestamp", "open", "high", "low", "close", "volume", "oi"]
    pd.DataFrame(_bars("2026-10-15", 5, 75, 50000.0) + _bars("2026-10-16", 5, 75, 50010.0), columns=cols) \
        .to_parquet(root / "data" / "oe_index_5min_BANKNIFTY.parquet", index=False)
    pd.DataFrame(_bars("2026-10-15", 5, 75, NIFTY_MARK), columns=cols).to_parquet(root / "data" / "oe_index_5min_NIFTY.parquet", index=False)
    fut = pd.DataFrame(_bars("2026-10-16", 5, 75, 50100.0, vol=500), columns=cols).assign(contract="BANKNIFTY FUT 27 OCT 26")
    fut.to_parquet(root / "data" / "oe_futures_5min_BANKNIFTY.parquet", index=False)              # 15 Oct ⇒ no FUT volume
    pd.DataFrame(_bars("2026-10-15", 5, 75, NIFTY_MARK, vol=9), columns=cols).assign(contract="NIFTY FUT 27 OCT 26") \
        .to_parquet(root / "data" / "oe_futures_5min_NIFTY.parquet", index=False)
    con = sqlite3.connect(root / "data" / "historical_data.db")
    con.execute("CREATE TABLE historical_candles (symbol TEXT, interval TEXT, timestamp TEXT, open REAL, high REAL, low REAL, close REAL,"
                " volume INTEGER, oi INTEGER, PRIMARY KEY (symbol, interval, timestamp))")
    rows = [("BANKNIFTY", "15minute", str(r[0]), *r[1:]) for r in _bars("2026-10-14", 15, 25, 49900.0)]
    rows += [("NIFTY", "15minute", str(r[0]), *r[1:]) for r in _bars("2026-10-14", 15, 25, NIFTY_MARK)]
    rows += [("BANKNIFTY", "day", "2026-10-13 00:00:00", 49800.0, 49900.0, 49700.0, 49850.0, 0, 0)]
    con.executemany("INSERT INTO historical_candles VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return root


def _hashes(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def _run(root, *args):
    return X.main(["--root", str(root), "--now", AFTER_CLOSE, *args])


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


def test_export_banknifty_only_read_only_with_gaps_and_checksums(tmp_path, no_network, capsys):
    root = _bot(tmp_path)
    before = _hashes(root)
    out = tmp_path / "trade-data" / "banknifty" / "vps_history" / "run1"
    assert _run(root, "--out-dir", str(out)) == 0
    assert _hashes(root) == before                                                  # bot files untouched (sqlite opened mode=ro)
    files = sorted(os.listdir(out))
    assert files == ["BANKNIFTY_15M.csv.gz", "BANKNIFTY_1M.csv.gz", "BANKNIFTY_5M.csv.gz", "BANKNIFTY_D.csv.gz",
                     "BANKNIFTY_FUT_5M.csv.gz", "README.md", "manifest.json"]
    for f in files:
        if f.endswith(".gz"):
            text = gzip.open(out / f, "rt").read()
            assert str(NIFTY_MARK) not in text and "NIFTY FUT" not in text.replace("BANKNIFTY FUT", "")
    m = json.load(open(out / "manifest.json"))
    f1 = m["files"]["BANKNIFTY_1M.csv.gz"]
    assert f1["rows"] == 675 and f1["first"] == "2026-10-15 09:15:00" and f1["days"] == 2
    assert f1["incomplete_sessions"] == {"2026-10-16": 300} and f1["missing_sessions"] == []
    assert m["files"]["BANKNIFTY_15M.csv.gz"]["sources"] == {"sqlite:historical_candles[BANKNIFTY|15minute]": 25}
    fut = m["files"]["BANKNIFTY_FUT_5M.csv.gz"]
    assert fut["contracts"] == ["BANKNIFTY FUT 27 OCT 26"] and fut["days_with_volume"] == 1
    assert m["missing_fut_volume_days_vs_spot"] == ["2026-10-14", "2026-10-15"]           # spot from 14 Oct (15M), FUT only 16 Oct
    for f, v in m["files"].items():
        assert v["sha256"] == hashlib.sha256(open(out / f, "rb").read()).hexdigest()
    df = pd.read_csv(out / "BANKNIFTY_FUT_5M.csv.gz")
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume", "oi", "contract", "source"]
    printed = capsys.readouterr().out
    assert f"{f1['sha256']}  BANKNIFTY_1M.csv.gz" in printed and "missing near-month FUT-volume days" in printed


def test_never_overwrites_and_same_rows_same_sha(tmp_path):
    root = _bot(tmp_path)
    a, b = tmp_path / "td" / "a", tmp_path / "td" / "b"
    assert _run(root, "--out-dir", str(a)) == 0
    first = _hashes(a)
    assert _run(root, "--out-dir", str(a)) == 2                                     # exists ⇒ refused, untouched
    assert _hashes(a) == first
    assert _run(root, "--out-dir", str(b)) == 0
    for f in os.listdir(a):
        if f.endswith(".gz"):
            assert first[str(a / f)] == _hashes(b)[str(b / f)]


def test_refuses_market_hours_and_repo_folder(tmp_path):
    root = _bot(tmp_path)
    out = tmp_path / "td" / "x"
    assert X.main(["--root", str(root), "--now", "2026-10-21 08:45", "--out-dir", str(out)]) == 2
    assert X.main(["--root", str(root), "--now", "2026-10-21 15:34", "--check"]) == 2
    assert not out.exists()
    assert X.main(["--root", str(root), "--now", "2026-10-20 11:00", "--check"]) == 0     # NSE holiday ⇒ allowed
    assert X.main(["--root", str(root), "--now", "2026-10-24 11:00", "--check"]) == 0     # Saturday
    assert _run(root, "--out-dir", os.path.join(X.ROOT, "data", "bn_export_test")) == 2
    assert not os.path.exists(os.path.join(X.ROOT, "data", "bn_export_test"))


def test_check_writes_nothing_and_empty_bot_is_an_error(tmp_path):
    root = _bot(tmp_path)
    before = set(os.listdir(tmp_path))
    assert _run(root, "--check") == 0
    assert set(os.listdir(tmp_path)) == before
    empty = tmp_path / "empty"
    (empty / "data").mkdir(parents=True)
    assert _run(empty, "--check") == 3


def test_refuses_code_pickle_and_non_banknifty_contract(tmp_path):
    root = _bot(tmp_path)
    with open(root / "data" / "engine3_cache" / "hist_NSE_INDEX_Nifty_Bank_1minute_90_x.pkl", "wb") as f:
        pickle.dump([os.getcwd], f)                                                # a function reference ⇒ never unpickled
    assert _run(root, "--check") == 1
    os.remove(root / "data" / "engine3_cache" / "hist_NSE_INDEX_Nifty_Bank_1minute_90_x.pkl")
    fut = pd.read_parquet(root / "data" / "oe_futures_5min_BANKNIFTY.parquet")
    fut.loc[0, "contract"] = "NIFTY FUT 27 OCT 26"
    fut.to_parquet(root / "data" / "oe_futures_5min_BANKNIFTY.parquet", index=False)
    assert _run(root, "--check") == 2


def test_names_match_the_bot():
    import instruments as INS
    assert X.INDEX_KEY == INS.get("BANKNIFTY")["key"]
    tag = "".join(ch if ch.isalnum() else "_" for ch in f"{X.INDEX_KEY}_1minute_{90}")   # engine3_live._history_cached
    assert tag.startswith(X.cache_tag_prefix())
    assert X.classify_symbol("BANKNIFTY") == "spot" and X.classify_symbol("BANKNIFTY FUT 27 OCT 26") == "fut"
    assert X.classify_symbol("NIFTY") is None and X.classify_symbol("NIFTY FUT 27 OCT 26") is None
    assert X.classify_symbol("SENSEX") is None


def test_guard_only_reads_nothing(tmp_path, no_network):
    assert X.main(["--guard-only", "--now", AFTER_CLOSE]) == 0
    assert X.main(["--guard-only", "--now", "2026-10-21 12:00"]) == 2


def test_written_aside_then_renamed_and_no_partial_left(tmp_path, monkeypatch):
    root = _bot(tmp_path)
    parent = tmp_path / "td" / "vps_history"
    assert _run(root, "--out-dir", str(parent / "ok")) == 0
    assert sorted(os.listdir(parent)) == ["ok"]                                    # no hidden partial sibling left
    real = X._write_files

    def half(built, d, meta):
        X.write_csv_gz(built["1M"][0], os.path.join(d, "BANKNIFTY_1M.csv.gz"))   # one file written, then a failure
        raise OSError("disk full")
    monkeypatch.setattr(X, "_write_files", half)
    assert _run(root, "--out-dir", str(parent / "bad")) == 1
    assert sorted(os.listdir(parent)) == ["ok"]                                    # neither the final folder nor the partial one
    monkeypatch.setattr(X, "_write_files", real)
