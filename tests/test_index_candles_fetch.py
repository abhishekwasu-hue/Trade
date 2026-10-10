"""research/index_candles_fetch.py — generic index candles downloader (नकली session; network / token नाही)."""
import datetime as dt
import json

import pandas as pd
import pytest

import instruments as INS
from research import elliott_vps_data as EV
from research import index_candles_fetch as F


class Resp:
    def __init__(self, candles, code=200):
        self.status_code, self._c = code, candles

    def json(self):
        return {"data": {"candles": self._c}}


class Sess:
    def __init__(self, fail_tf=None):
        self.urls, self.fail_tf = [], fail_tf

    def get(self, url, headers=None, params=None, timeout=None):
        self.urls.append(url)
        assert headers["Authorization"].startswith("Bearer ")
        if self.fail_tf and f"/{self.fail_tf}/" in url:
            return Resp([], 500)
        end = url.rstrip("/").split("/")[-2]
        ts = pd.Timestamp(end) + pd.Timedelta(hours=9, minutes=15)
        return Resp([[ts.strftime("%Y-%m-%dT%H:%M:%S+05:30"), 100.0, 101.0, 99.0, 100.5, 0, 0]])


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(EV, "check_repo", lambda p, remote_urls=None: True)
    monkeypatch.setattr(F, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    return tmp_path


def test_banknifty_all_tf_manifest_and_chunks(repo, capsys):
    s = Sess()
    today = dt.date(2030, 6, 15)
    rc = F.main(["--repo", str(repo), "--instrument", "BANKNIFTY"], session=s, token="SECRET-TOKEN", today=today)
    out = capsys.readouterr().out
    assert rc == 0 and "SECRET-TOKEN" not in out
    m = json.load(open(repo / "banknifty" / "manifest.json", encoding="utf-8"))
    assert m["instrument"] == "BANKNIFTY" and m["key"] == INS.get("BANKNIFTY")["key"] and m["volume"] == "NA"
    assert set(m["files"]) == {"W", "D", "1H", "15M"} and all(v["rows"] > 0 for v in m["files"].values())
    assert sum("/minutes/15/" in u for u in s.urls) >= 3                         # 3 महिने ⇒ ≥ 3 chunks (28 दिवस)
    df = pd.read_csv(repo / "banknifty" / "BANKNIFTY_15M.csv.gz")
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close"]


def test_failed_chunk_is_reported_nonzero(repo):
    rc = F.main(["--repo", str(repo), "--instrument", "BANKNIFTY", "--tf", "1H"], session=Sess(fail_tf="hours"), token="t",
                today=dt.date(2030, 6, 15))
    m = json.load(open(repo / "banknifty" / "manifest.json", encoding="utf-8"))
    assert rc == 1 and m["files"]["1H"]["chunks_failed"]


def test_nifty_never_writes_sealed_holdout_rows(repo, monkeypatch):
    monkeypatch.setattr(F.DP, "period", lambda x: "HOLDOUT")
    F.main(["--repo", str(repo), "--instrument", "NIFTY", "--tf", "D"], session=Sess(), token="t", today=dt.date(2030, 6, 15))
    m = json.load(open(repo / "upstox" / "manifest.json", encoding="utf-8"))
    assert m["files"]["D"]["rows"] == 0 and m["files"]["D"]["holdout_rows_dropped"] > 0


def test_chunks_cover_span_without_gaps():
    cs = F.chunks(dt.date(2030, 1, 1), dt.date(2030, 4, 1), 28)
    assert cs[-1][0] == dt.date(2030, 1, 1) and cs[0][1] == dt.date(2030, 4, 1)
    assert all(cs[i + 1][1] == cs[i][0] - dt.timedelta(days=1) for i in range(len(cs) - 1))
