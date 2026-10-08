"""tests/test_elliott_e0.py — Elliott E0: data धोरण (holdout/contaminated), NSE bhavcopy parser (दोन्ही formats), VPS data script
(public repo नकार, holdout नकार, resume, token न छापणं), golden expectations ची रचना. Network नाही."""
import datetime as dt
import io
import json
import os
import sys
import zipfile

import pandas as pd
import pytest

from elliott import bhavcopy as BC
from elliott import data_policy as DP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))
import elliott_vps_data as V  # noqa: E402

# ---------------------------------------------------------------- data_policy


def test_period_boundaries_are_consistent_with_check_range():
    assert DP.period("2024-03-31 23:59:59.9") == "VAL" and DP.period("2024-04-01 00:00") == "HOLDOUT"
    assert DP.period("2026-10-08 23:59:59.9") == "CONTAMINATED" and DP.period("2026-10-09") == "HOLDOUT"
    assert DP.period("2026-10-07 10:00") == "CONTAMINATED"                       # 7–8 Oct golden story (Abhi 2026-10-08, illustration only)
    assert DP.check_range("2026-07-01", "2026-10-08 23:59:59.9", "golden")
    with pytest.raises(DP.HoldoutError):
        DP.check_range("2026-07-01", "2026-10-09 00:00", "golden")


def test_periods_and_allowed():
    assert DP.period("2016-05-02") == "IS" and DP.period("2023-01-02") == "VAL"
    assert DP.period("2024-04-01") == "HOLDOUT" and DP.period("2026-09-29 10:00") == "CONTAMINATED"
    assert DP.period("2026-10-09") == "HOLDOUT"
    assert DP.allowed("2021-12-31 15:29") and not DP.allowed("2024-06-01")
    assert not DP.allowed("2026-09-29", "research") and DP.allowed("2026-09-29", "golden")
    assert not DP.allowed("2025-01-01", "golden")


def test_check_range_blocks_holdout_and_research_use_of_golden_window():
    assert DP.check_range("2019-01-01", "2024-03-31")
    assert DP.check_range("2026-07-01", "2026-10-08", "golden")
    for a, b, p in (("2024-03-01", "2024-04-02", "research"), ("2026-06-30", "2026-10-08", "golden"),
                    ("2026-07-01", "2026-10-09", "golden"), ("2026-07-01", "2026-10-06", "research")):
        with pytest.raises(DP.HoldoutError):
            DP.check_range(a, b, p)


def test_filter_and_final_holdout_mask():
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2024-03-28", "2024-05-02", "2026-08-03", "2026-10-07", "2026-10-09"])})
    assert list(DP.filter_allowed(df)["timestamp"].dt.date.astype(str)) == ["2024-03-28"]
    assert list(DP.filter_allowed(df, "golden")["timestamp"].dt.date.astype(str)) == ["2024-03-28", "2026-08-03", "2026-10-07"]
    assert list(DP.final_holdout_mask(df["timestamp"])) == [False, True, False, False, True]     # contaminated अंतिम holdout मधून वगळला


# ---------------------------------------------------------------- bhavcopy

OLD = """INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP,
FUTIDX,NIFTY,27-Jul-2023,0,XX,19400,19500,19350,19480,19480,1000,1,500,10,07-JUL-2023,
OPTIDX,NIFTY,13-Jul-2023,19500,CE,80,95,60,70.5,70.5,2000,1,3000,50,07-JUL-2023,
OPTIDX,NIFTY,13-Jul-2023,19300,PE,40,50,30,35,35,1500,1,2500,20,07-JUL-2023,
OPTIDX,NIFTY,27-Jul-2023,19300,PE,90,99,80,85,85,100,1,200,5,07-JUL-2023,
OPTIDX,BANKNIFTY,13-Jul-2023,45000,CE,1,1,1,1,1,1,1,1,1,07-JUL-2023,
OPTSTK,NIFTY,27-Jul-2023,100,CE,1,1,1,1,1,1,1,1,1,07-JUL-2023,
"""
UDIFF = """TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
2026-09-29,2026-09-29,FO,NSE,IDO,1,,NIFTY,,2026-10-06,2026-10-06,22500,PE,NIFTY26O0622500PE,20,25,15,18.5,18.5,22,22610.5,18.5,100000,5,90000,1,1,F1,65,,,,,
2026-09-29,2026-09-29,FO,NSE,IDF,2,,NIFTY,,2026-10-27,2026-10-27,,,NIFTY26OCTFUT,22600,22700,22550,22650,22650,22600,22610.5,22650,9000,1,500,1,1,F1,65,,,,,
2026-09-29,2026-09-29,FO,NSE,STO,3,,RELIANCE,,2026-10-27,2026-10-27,3000,CE,X,1,1,1,1,1,1,1,1,1,1,1,1,1,F1,500,,,,,
"""


def _zip(text, name="x.csv"):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(name, text)
    return b.getvalue()


def test_normalize_old_format():
    n = BC.normalize(BC.read_zip_csv(_zip(OLD)))
    assert list(n.columns) == BC.COLUMNS and len(n) == 4                       # BANKNIFTY, OPTSTK वगळले
    ce = n[(n["opt_type"] == "CE")].iloc[0]
    assert ce["date"] == dt.date(2023, 7, 7) and ce["expiry"] == dt.date(2023, 7, 13) and ce["strike"] == 19500 and ce["close"] == 70.5
    fut = n[n["instrument"] == "FUT"].iloc[0]
    assert pd.isna(fut["strike"]) and fut["opt_type"] == "" and pd.isna(fut["lot_size"])


def test_normalize_udiff_format_has_lot_and_underlying():
    n = BC.normalize(BC.read_zip_csv(UDIFF.encode()))
    assert len(n) == 2 and set(n["instrument"]) == {"OPT", "FUT"}
    o = n[n["instrument"] == "OPT"].iloc[0]
    assert o["expiry"] == dt.date(2026, 10, 6) and o["lot_size"] == 65 and o["underlying"] == 22610.5 and o["settle"] == 18.5


def test_unknown_format_is_loud():
    with pytest.raises(BC.BhavcopyFormatError):
        BC.normalize(pd.DataFrame({"a": [1]}))


def test_expiry_calendar_weekly_monthly_and_first_weekly():
    n = BC.normalize(BC.read_zip_csv(_zip(OLD)))
    cal = BC.expiry_calendar(n)
    assert dict(zip(cal["expiry"], cal["kind"])) == {dt.date(2023, 7, 13): "weekly", dt.date(2023, 7, 27): "monthly"}
    assert set(cal["weekday"]) == {"Thursday"} and BC.first_weekly_listing(n) == dt.date(2023, 7, 7)


def test_urls_switch_to_udiff():
    assert "fo07JUL2023bhav.csv.zip" in BC.urls_for("2023-07-07")[0] and "/2023/JUL/" in BC.urls_for("2023-07-07")[0]
    assert BC.urls_for("2026-09-29")[0].endswith("BhavCopy_NSE_FO_0_0_0_20260929_F_0000.csv.zip")


# ---------------------------------------------------------------- VPS script


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    return str(tmp_path)


def test_check_repo_refuses_public_trade_repo(repo):
    for u in ("https://github.com/abhishekwasu-hue/Trade.git", "git@github.com:abhishekwasu-hue/Trade", "https://x/trade-data-public"):
        with pytest.raises(ValueError):
            V.check_repo(repo, u)
    assert V.check_repo(repo, "https://github.com/abhishekwasu-hue/trade-data.git\n")
    assert V.check_repo(repo, "git@github-trade-data:abhishekwasu-hue/trade-data.git")          # deploy-key ssh alias
    with pytest.raises(ValueError):                                                       # push URL public repo कडे ⇒ नकार
        V.check_repo(repo, ["git@github.com:abhishekwasu-hue/trade-data.git", "git@github.com:abhishekwasu-hue/Trade.git"])
    with pytest.raises(ValueError):
        V.check_repo(repo, [])
    with pytest.raises(ValueError):
        V.check_repo(os.path.dirname(repo) + "/nope", "https://github.com/a/trade-data")


class _Resp:
    def __init__(self, code, content=b"", js=None):
        self.status_code, self.content, self._js, self.text = code, content, js, ""

    def json(self):
        return self._js


class _Sess:
    def __init__(self, router):
        self.router, self.calls, self.headers = router, [], {}

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, params))
        return self.router(url, params)


NO_SESS = {"days": set(), "lo": None, "hi": None, "hol2026": {dt.date(2026, 10, 2)}}
TODAY = dt.date(2026, 10, 7)
GOLDEN_RANGE = [(dt.date(2026, 9, 26), dt.date(2026, 10, 6), "golden")]


def _router(ok_days, err_days=(), html_days=()):
    def r(url, params):
        if any(d in url for d in html_days) and "BhavCopy" in url:
            return _Resp(200, b"<html>blocked</html>")
        if any(d in url for d in ok_days) and "BhavCopy" in url:
            return _Resp(200, _zip(UDIFF))
        if any(d in url for d in err_days):
            return _Resp(403)
        return _Resp(404)
    return r


def _bhav(repo, router, **k):
    s = _Sess(router)
    r = V.bhavcopy(repo, ranges=GOLDEN_RANGE, session=s, sleep=0, log=lambda *_: None, today=TODAY, sess=NO_SESS, **k)
    return r, s


def test_bhavcopy_status_resume_and_separate_golden_dir(repo):
    r, _ = _bhav(repo, _router(["20260929"], ["20260930"], ["20261001"]))
    # 26/27 sat-sun, 3/4 sat-sun, 2 = 2026 सुट्टी ⇒ missing (5); 30 = 403, 1 = HTML ⇒ चूक (2);
    # 28, 5 weekday 404 पण सुट्टी माहीत नाही ⇒ पुन्हा; 6 (= आजच्या आदला दिवस) ⇒ pending (3)
    assert r == {"ok": 1, "missing": 5, "error": 2, "pending": 3}
    base = os.path.join(repo, "nse_fo_bhavcopy", "NIFTY_golden")
    assert not os.path.exists(os.path.join(repo, "nse_fo_bhavcopy", "NIFTY"))            # golden डेटा research folder मध्ये नाही
    man = pd.read_csv(os.path.join(base, "manifest.csv"), dtype=str).set_index("date")["status"]
    assert man["2026-09-29"] == "ok" and man["2026-09-27"] == "missing" and man["2026-10-02"] == "missing"
    assert man["2026-09-30"].startswith("error_http_403") and man["2026-10-01"].startswith("error_parse")
    assert man["2026-09-28"] == "missing_weekday" and man["2026-10-06"] == "pending"
    p1 = pd.read_parquet(os.path.join(base, "2026-09.parquet"))
    assert len(p1) == 2 and all(str(p1[c].dtype) == "float64" for c in ("open", "strike", "lot_size", "volume"))
    r2, s2 = _bhav(repo, _router(["20260929", "20260930", "20261006"]))
    fetched = {u for u, _ in s2.calls if "archives" in u}
    assert fetched and not any("20260929" in u or "20260927" in u or "20261002" in u for u in fetched)    # ok/missing पुन्हा नाहीत
    assert r2["ok"] == 2                                                                   # 30 आणि 6 आता मिळाले
    p2 = pd.read_parquet(os.path.join(base, "2026-09.parquet"))
    assert len(p2) == len(p1)                                                              # दुबार ओळी नाहीत (UDIFF fixture ची तारीख तीच)


def test_bhavcopy_empty_file_is_error_not_ok(repo):
    empty = UDIFF.splitlines()[0] + "\n"
    r, _ = _bhav(repo, lambda u, p: _Resp(200, empty.encode()) if "20260929" in u and "BhavCopy" in u else _Resp(404))
    man = pd.read_csv(os.path.join(repo, "nse_fo_bhavcopy", "NIFTY_golden", "manifest.csv"), dtype=str).set_index("date")["status"]
    assert man["2026-09-29"] == "error_empty" and r["ok"] == 0


def test_classify_404_uses_known_sessions():
    sess = {"days": {dt.date(2023, 7, 6)}, "lo": dt.date(2015, 1, 9), "hi": dt.date(2024, 3, 27), "hol2026": set()}
    assert V.classify_404(dt.date(2023, 7, 6), TODAY, sess) == "error_404_session"       # बाजार चालू होता ⇒ फाईल हवीच
    assert V.classify_404(dt.date(2023, 8, 15), TODAY, sess) == "missing"                # offline डेटानुसार सुट्टी
    assert V.classify_404(dt.date(2024, 3, 28), TODAY, sess) == "missing_weekday"        # offline श्रेणीबाहेर ⇒ माहीत नाही
    assert V.classify_404(dt.date(2026, 10, 6), TODAY, sess) == "pending"


def test_bhavcopy_refuses_holdout(repo):
    with pytest.raises(DP.HoldoutError):
        V.bhavcopy(repo, ranges=[(dt.date(2024, 5, 1), dt.date(2024, 5, 3), "research")], session=_Sess(lambda u, p: _Resp(404)),
                   sleep=0, sess=NO_SESS)


def test_probe_never_fetches_holdout_candles_and_hides_token(repo, capsys):
    tok = "SECRET_TOKEN_123"
    seen = []

    def router(url, params):
        seen.append(url)
        if url.endswith("/expiries"):
            return _Resp(200, js={"data": ["2023-03-29", "2024-03-28", "2025-06-26", "2026-09-29"]})
        if url.endswith("/option/contract"):
            return _Resp(200, js={"data": [{"instrument_key": None}, {"instrument_key": "NSE_FO|NIFTY24MAR22000CE"}]})
        return _Resp(200, js={"data": {"candles": [[1, 2, 3, 4, 5]] * 10}})
    out = V.probe_expired(repo, token=tok, session=_Sess(router))
    assert out["ok"] and out["sample_candles"] == 10 and out["n_expiries"] == 4 and out["sample_expiry"] == "2024-03-28"
    candle = [u for u in seen if "/historical-candle/" in u]
    assert len(candle) == 1 and candle[0].endswith("/1minute/2024-03-28/2024-03-25")
    saved = open(os.path.join(repo, "probes", "upstox_expired_probe.json"), encoding="utf-8").read()
    assert tok not in saved and tok not in capsys.readouterr().out


def test_probe_golden_fallback_window_stays_in_golden(repo):
    seen = []

    def router(url, params):
        seen.append(url)
        if url.endswith("/expiries"):
            return _Resp(200, js={"data": ["2025-06-26", "2026-07-02"]})
        if url.endswith("/option/contract"):
            return _Resp(200, js={"data": [{"instrument_key": "NSE_FO|X"}]})
        return _Resp(200, js={"data": {"candles": []}})
    V.probe_expired(repo, token="t", session=_Sess(router))
    candle = [u for u in seen if "/historical-candle/" in u]
    assert candle and candle[0].endswith("/2026-07-02/2026-07-01")                       # from = golden सुरुवात, sealed जून नाही


def _golden_fetch(seen, extra_ts=()):
    def fetch(tok, key, interval, a, b):
        seen.update(key=key, interval=interval, a=a, b=b)
        days = V.expected_golden_days()
        ts = [pd.Timestamp(f"{d} 09:15") + pd.Timedelta(minutes=m) for d in days for m in range(375)]
        ts = pd.DatetimeIndex(ts + [pd.Timestamp(x) for x in extra_ts]).tz_localize("Asia/Kolkata")
        return pd.DataFrame({"timestamp": ts, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 0, "oi": 0})
    return fetch


def test_golden_export_only_golden_window_and_completeness(repo, capsys):
    seen = {}
    after = dt.datetime(2026, 10, 8, 15, 40)
    p = V.golden(repo, token="t", fetch=_golden_fetch(seen, ["2026-06-30 15:29", "2026-10-09 09:15"]), now=after)
    assert seen == {"key": "NSE_INDEX|Nifty 50", "interval": "1minute", "a": dt.date(2026, 7, 1), "b": dt.date(2026, 10, 8)}
    assert p.endswith("NIFTY_1m_2026-07-01_2026-10-08.csv.gz")
    d = pd.read_csv(p, parse_dates=["timestamp"])
    assert d["timestamp"].min() == pd.Timestamp("2026-07-01 09:15") and d["timestamp"].max() == pd.Timestamp("2026-10-08 15:29")
    assert "✅ golden" in capsys.readouterr().out

    def gappy(tok, key, interval, a, b):                                                   # एक 28-दिवसांचा chunk गहाळ
        df = _golden_fetch({})(tok, key, interval, a, b)
        ts = df["timestamp"].dt.tz_localize(None)
        return df[(ts < "2026-08-01") | (ts >= "2026-08-29")]
    assert V.golden(repo, token="t", fetch=gappy, now=after) is False
    assert "गहाळ दिवस" in capsys.readouterr().out
    assert V.golden(repo, token="t", fetch=_golden_fetch({}), now=dt.datetime(2026, 10, 8, 14, 0)) is None   # बाजार बंद होण्याआधी


def test_major_levels_index_fetch_drops_holdout():
    def fetch(*a, **k):
        ts = pd.to_datetime(["2026-07-28 09:15", "2026-10-06 15:15", "2026-10-09 09:15"]).tz_localize("Asia/Kolkata")
        return pd.DataFrame({"timestamp": ts, "open": 1, "high": 1, "low": 1, "close": 1})
    d = V.golden_filtered_fetch(fetch)("tok", "NIFTY", None, interval="15minute", lookback_days=70)
    assert list(d["timestamp"].astype(str)) == ["2026-07-28 09:15:00", "2026-10-06 15:15:00"]


def test_main_returns_nonzero_on_failure(repo, monkeypatch):
    monkeypatch.setattr(V, "check_repo", lambda p: True)
    monkeypatch.setattr(V, "golden", lambda r: False)
    assert V.main(["--repo", repo, "golden"]) == 1
    monkeypatch.setattr(V, "golden", lambda r: "x.csv.gz")
    assert V.main(["--repo", repo, "golden"]) == 0
    monkeypatch.setattr(V, "check_repo", lambda p: (_ for _ in ()).throw(ValueError("public")))
    assert V.main(["--repo", repo, "golden"]) == 2


# ---------------------------------------------------------------- golden expectations


def test_golden_expectations_structure():
    g = json.load(open(os.path.join(ROOT, "docs", "reports", "elliott_golden_expectations.json"), encoding="utf-8"))
    lv = {t["id"]: t["level"] for t in g["trades"]}
    assert lv["T6"] == lv["T5"] == "must_not" and lv["T9"] == "report" and lv["T1"] == "verify"   # T5: review F9 (sizing स्तर)
    assert {k for k, v in lv.items() if v == "must"} == {"T2", "T3", "T4", "T7", "T8"}
    for t in g["trades"] + g["rejections"]:
        assert DP.allowed(t["date"], "golden") and not DP.allowed(t["date"], "research")
        if t.get("expiry"):
            e = pd.Timestamp(t["expiry"])
            assert e.day_name() == "Tuesday" and e.date() > pd.Timestamp(t["date"]).date()   # आज expiry ⇒ पुढची weekly
    assert any(r["id"] == "R-1006-0940" and r["level"] == "must_not" for r in g["rejections"])
