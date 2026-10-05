"""tests/test_cache_holdout_upstox.py — sealed holdout cache: तुकडे, फक्त संख्या, manifest; बनावट fetch, network-free."""
import datetime
import json

import pandas as pd

import cache_holdout_upstox as H


def test_chunks_cover_range_without_overlap():
    a, b = datetime.date(2024, 4, 1), datetime.date(2024, 6, 15)
    ch = H.chunks(a, b)
    assert ch[0][0] == a and ch[-1][1] == b
    for (s1, e1), (s2, _) in zip(ch, ch[1:]):
        assert s2 == e1 + datetime.timedelta(days=1) and (e1 - s1).days <= H.CHUNK_DAYS - 1


def _fake_fetch(calls):
    def fetch(token, key, interval, a, b):
        calls.append((a, b))
        if a == datetime.date(2024, 4, 29):
            return {"status": 500, "candles": [], "error": "boom"}
        day = pd.Timestamp(a) + pd.Timedelta(hours=9, minutes=15)
        return {"status": 200, "candles": [[(day + pd.Timedelta(minutes=5 * i)).isoformat() + "+05:30", 1, 2, 0.5, 1.5, 0, 0] for i in range(3)], "error": None}
    return fetch


def test_cache_writes_parquet_and_manifest_with_counts_only(tmp_path):
    calls, logs = [], []
    man, bad = H.cache(["NIFTY", "XYZ"], "tok", datetime.date(2024, 6, 1), _fake_fetch(calls), {"NIFTY": "NSE_INDEX|Nifty 50"}, str(tmp_path), log=logs.append)
    assert bad == 2                                                                 # एक तुकडा अयशस्वी + XYZ key नाही
    n = man["symbols"]["NIFTY"]
    assert n["bars"] == 6 and n["days"] == 2 and n["errors"] == 1 and len(n["sha256"]) == 64
    disk = json.loads((tmp_path / "MANIFEST.json").read_text(encoding="utf-8"))
    assert disk["sealed_until"] == "G4" and disk["start"] == "2024-04-01"
    assert pd.read_parquet(H.holdout_path("NIFTY", str(tmp_path)))["timestamp"].min() >= pd.Timestamp("2024-04-01")
    assert not any("1.5" in m or "tok" in m for m in logs)                         # किंमत/token छापत नाही


def test_counts_only_empty():
    assert H.counts_only(pd.DataFrame()) == {"bars": 0, "days": 0}
