"""scripts/fetch_sensex_history.py — SENSEX Daily / 1H / 15M fetcher (VPS-only). नकली session / fixtures; network / token नाही."""
import ast
import datetime as dt
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import elliott_vps_data as EV

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fetch_sensex_history", ROOT / "scripts" / "fetch_sensex_history.py")
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)

TODAY = dt.date(2030, 6, 14)                       # शुक्रवार
FUT_KEY = "BSE_FO|1111"


def _rows():
    """Upstox instrument search / master चे fixture rows (BSE F&O + noise)."""
    ms = lambda d: int((pd.Timestamp(d) - pd.Timestamp("1970-01-01")).total_seconds() * 1000)   # noqa: E731
    return [
        {"trading_symbol": "SENSEX FUT 27 JUN 30", "instrument_key": FUT_KEY, "segment": "BSE_FO", "instrument_type": "FUT",
         "expiry": "2030-06-27"},
        {"trading_symbol": "SENSEX FUT 25 JUL 30", "instrument_key": "BSE_FO|2222", "segment": "BSE_FO", "instrument_type": "FUT",
         "expiry": ms("2030-07-25")},
        {"trading_symbol": "SENSEX FUT 30 MAY 30", "instrument_key": "BSE_FO|0000", "segment": "BSE_FO", "instrument_type": "FUT",
         "expiry": "2030-05-30"},                                                    # expired
        {"trading_symbol": "SENSEX50 FUT 27 JUN 30", "instrument_key": "BSE_FO|5050", "segment": "BSE_FO", "instrument_type": "FUT",
         "expiry": "2030-06-20"},
        {"trading_symbol": "BANKEX FUT 27 JUN 30", "instrument_key": "BSE_FO|3333", "segment": "BSE_FO", "instrument_type": "FUT",
         "expiry": "2030-06-18"},
        {"trading_symbol": "SENSEX 80000 CE 20 JUN 30", "instrument_key": "BSE_FO|4444", "segment": "BSE_FO", "instrument_type": "CE",
         "expiry": "2030-06-20"},
        {"trading_symbol": "SENSEX FUT 27 JUN 30", "instrument_key": "NSE_FO|9", "segment": "NSE_FO", "instrument_type": "FUT",
         "expiry": "2030-06-19"},
    ]


def _m15(day, base=100.0, n=25):
    ts = [pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * k) for k in range(n)]
    c = base + np.arange(n, dtype=float)
    return pd.DataFrame({"timestamp": ts, "open": c - 0.5, "high": c + 1, "low": c - 1, "close": c})


# ------------------------------------------------------------------ pure parts
def test_key_matches_upstox_api_registry():
    tree = ast.parse((ROOT / "upstox_api.py").read_text(encoding="utf-8"))
    reg = next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(getattr(t, "id", "") == "SYMBOL_INSTRUMENT_KEYS" for t in n.targets))
    assert F.KEY == reg["SENSEX"]


def test_resolve_futures_from_fixture_instrument_list():
    front, nxt = F.resolve_futures(_rows(), "SENSEX", TODAY)
    assert front["instrument_key"] == FUT_KEY and front["expiry"] == dt.date(2030, 6, 27)
    assert nxt["instrument_key"] == "BSE_FO|2222" and nxt["expiry"] == dt.date(2030, 7, 25)
    assert F.near_month_from(front, nxt) == dt.date(2030, 5, 30)
    assert F.near_month_from(front, None) == dt.date(2030, 6, 27) - dt.timedelta(days=F.DEFAULT_GAP_DAYS)
    assert F.resolve_futures([r for r in _rows() if "SENSEX FUT" not in r["trading_symbol"]], "SENSEX", TODAY) == (None, None)
    assert F.resolve_futures([], "SENSEX", TODAY) == (None, None)


def test_resample_15m_to_1h_is_0915_anchored():
    h = F.to_1h(_m15("2030-06-10"))
    assert [t.strftime("%H:%M") for t in h["timestamp"]] == ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"]
    m = _m15("2030-06-10")
    assert h.iloc[0]["open"] == m.iloc[0]["open"] and h.iloc[0]["close"] == m.iloc[3]["close"]
    assert h.iloc[0]["high"] == m.iloc[:4]["high"].max() and h.iloc[-1]["close"] == m.iloc[-1]["close"]
    assert list(h.columns) == F.COLS


def test_volume_bins_never_partial():
    m = pd.concat([_m15("2030-06-10"), _m15("2030-06-11")], ignore_index=True)
    vol = m[["timestamp"]].assign(volume=10.0)
    vol.loc[(vol["timestamp"] == pd.Timestamp("2030-06-11 10:30")), "volume"] = np.nan        # एक 15M bar futures शिवाय
    h = F.to_1h(m)
    hv = F.attach_volume(h, "1H", vol)
    got = dict(zip(hv["timestamp"].dt.strftime("%m-%d %H:%M"), hv["volume"]))
    assert got["06-10 09:15"] == 40.0 and got["06-10 15:15"] == 10.0 and np.isnan(got["06-11 10:15"]) and got["06-11 11:15"] == 40.0
    d = pd.DataFrame({"timestamp": pd.to_datetime(["2030-06-07", "2030-06-10", "2030-06-11"]), "open": 1.0, "high": 2.0, "low": 0.5,
                      "close": 1.5})
    dv = F.attach_volume(d, "D", vol)
    assert np.isnan(dv["volume"].iloc[0]) and dv["volume"].iloc[1] == 250.0 and np.isnan(dv["volume"].iloc[2])
    assert list(F.attach_volume(d, "D", None).columns) == F.COLS                                # futures नाहीत ⇒ BANKNIFTY schema


def test_merge_and_resume_plan():
    a = _m15("2030-06-10")
    b = _m15("2030-06-10", base=200.0).iloc[20:]
    m = F.merge(a, b)
    assert len(m) == 25 and m["close"].iloc[-1] == b["close"].iloc[-1]                        # नवा row जिंकतो (index)
    assert F.merge(a, b, keep="first")["close"].iloc[-1] == a["close"].iloc[-1]               # futures: आधीचा जिंकतो
    s, e = dt.date(2026, 1, 1), dt.date(2030, 6, 14)
    assert F.plan_ranges(s, e, None) == [(s, e)]
    ex = pd.concat([_m15("2028-01-03"), _m15("2030-06-10")], ignore_index=True)
    assert F.plan_ranges(s, e, ex) == [(s, dt.date(2028, 1, 2)), (dt.date(2030, 6, 10), e)]
    assert F.plan_ranges(s, e, ex, checked_from=s) == [(dt.date(2030, 6, 10), e)]           # आधी तपासलेला जुना काळ पुन्हा नाही


# ------------------------------------------------------------------ main (fake session)
class Resp:
    def __init__(self, data, code=200):
        self.status_code, self._d = code, data

    def json(self):
        return {"data": self._d}


class Sess:
    def __init__(self, futures=True):
        self.urls, self.futures = [], futures

    def get(self, url, headers=None, params=None, timeout=None):
        self.urls.append(url)
        assert headers["Authorization"].startswith("Bearer ")
        if url.endswith("/instruments/search"):
            assert params["exchanges"] == "BSE" and params["instrument_types"] == "FUT"
            return Resp(_rows() if self.futures else [])
        parts = url.rstrip("/").split("/")
        unit, to, frm = parts[-3], pd.Timestamp(parts[-2]), pd.Timestamp(parts[-1])
        fut = "BSE_FO" in url
        out = []
        for d in pd.bdate_range(frm, to):
            if unit == "days":
                out.append([f"{d:%Y-%m-%d}T00:00:00+05:30", 100.0, 101.0, 99.0, 100.5, 0, 0])
            else:
                for k in range(25):
                    t = d + pd.Timedelta(hours=9, minutes=15 + 15 * k)
                    out.append([t.strftime("%Y-%m-%dT%H:%M:%S+05:30"), 100.0, 101.0, 99.0, 100.5, 7 if fut else 0, 3])
        return Resp({"candles": out})


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(EV, "check_repo", lambda p, remote_urls=None: True)
    return tmp_path


def _run(repo, sess, *extra):
    return F.main(["--repo", str(repo), "--daily-years", "1", "--intraday-years", "0.1", "--futures-days", "20", *extra],
                  session=sess, token="SECRET-TOKEN", today=TODAY, sleep=lambda s: None)


def test_fetch_writes_banknifty_schema_and_futures_volume(repo, capsys):
    s = Sess()
    assert _run(repo, s) == 0
    out = capsys.readouterr().out
    assert "SECRET-TOKEN" not in out and "100.5" not in out                                    # token / किंमती छापत नाही
    d = repo / "sensex"
    for tf in ("D", "1H", "15M"):
        df = pd.read_csv(d / f"SENSEX_{tf}.csv.gz")
        assert list(df.columns) == F.COLS + ["volume"] and len(df)
    m15 = pd.read_csv(d / "SENSEX_15M.csv.gz", parse_dates=["timestamp"])
    covered = m15[m15["timestamp"].dt.date > dt.date(2030, 5, 30)]
    assert (covered["volume"] == 7).all() and m15.loc[m15["timestamp"].dt.date <= dt.date(2030, 5, 30), "volume"].isna().all()
    h1 = pd.read_csv(d / "SENSEX_1H.csv.gz", parse_dates=["timestamp"])
    assert set(h1["timestamp"].dt.strftime("%H:%M")) == {"09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"}
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert man["key"] == "BSE_INDEX|SENSEX" and man["futures"]["status"] == "ok" and man["futures"]["contract"].startswith("SENSEX FUT")
    assert man["files"]["15M"]["checked_from"] and "B" in man["grade_cap"]
    assert all(FUT_KEY.replace("|", "%7C") in u for u in s.urls if "BSE_FO" in u)            # near-month फक्त
    # re-run ⇒ फक्त शेवटचा दिवस पुढे (resume), जुना काळ पुन्हा नाही
    s2 = Sess()
    assert _run(repo, s2) == 0
    idx = [u for u in s2.urls if "BSE_INDEX" in u]
    assert idx and all(u.rstrip("/").split("/")[-1] >= str(TODAY - dt.timedelta(days=4)) for u in idx)
    assert len(pd.read_csv(d / "SENSEX_15M.csv.gz")) == len(m15)


def test_fetch_without_futures_is_volume_na_grade_cap_b(repo):
    assert _run(repo, Sess(futures=False)) == 0
    d = repo / "sensex"
    assert list(pd.read_csv(d / "SENSEX_D.csv.gz").columns) == F.COLS
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert man["volume"] == "NA" and man["futures"]["status"] == "not_found" and man["grade_cap"].startswith("B")


def test_dry_run_needs_no_token_and_writes_nothing(repo, capsys):
    assert F.main(["--repo", str(repo), "--dry-run"], session=None, token=None, today=TODAY) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "days/1" in out and "minutes/15" in out and not (repo / "sensex").exists()


def test_no_token_fetches_nothing(repo, monkeypatch, capsys):
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(EV, "_token", lambda t=None: None)
    s = Sess()
    assert F.main(["--repo", str(repo)], session=s, token=None, today=TODAY) == 3 and s.urls == []
