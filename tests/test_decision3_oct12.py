"""12-Oct reference case (Abhi, NIFTY bear call) — synthetic fixture (tests/oct12_fixture.py), आरशासह (bull put):
  • V22 (a2 + c0 + c1 चालू, futures volume + 5M LTF दिले) शेवटच्या दिवसाच्या पहिल्या तासात setup देतो; lookahead नाही.
  • (b) maturity = पुरावा फक्त: Daily mature केलं तरी setup राहतो, grade फक्त एक पायरी खाली.
  • (c) opening (09:15) candle पुरावा म्हणून मोजली जाते (2-candle form चा भाग), entry खिडकी तशीच.
  • (d) तिरकी रेघ + horizontal level ⇒ confluence area (overlap पट्टा), फक्त t ला माहीत swings.
  • (f) futures 5M volume ⇒ 15M = 09:15-anchored तीन 5M bins ची बेरीज, spot bar_start शी तंतोतंत.
"""
import dataclasses

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import method as M
from decision3 import settings as S3
from decision3 import trendline as TL
from tests import oct12_fixture as F

S_ROLE = {"level_death_side": "role"}                                      # claude/v22-touch-levels (TL1) — merge होईपर्यंत स्पष्ट


def _run(mirror):
    m15, fut, ltf = F.build(mirror=mirror)
    V = E3.V22(m15, s=S_ROLE, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last]
    return V, m15, fut, ltf, bars


@pytest.fixture(scope="module", params=[False, True], ids=["bear_call", "bull_put_mirror"])
def case(request):
    return request.param, _run(request.param)


def test_first_hour_setup_with_a2_c0_c1_active(case):
    mirror, (V, m15, fut, ltf, bars) = case
    rows = [V.decide(t) for t in bars]
    st = [r for r in rows if r["decision"] == "setup"]
    assert st, [(r["ts"][11:16], r["checklist"]["⑥"][1][:60]) for r in rows[:4]]
    r = st[0]
    assert pd.Timestamp(r["ts"]) < V.levels.ts.iloc[bars[0]] + pd.Timedelta(hours=1)          # पहिल्या तासात
    assert r["trend_used"] == ("UP" if mirror else "DOWN")
    assert r["level"]["role"] == ("support" if mirror else "resistance")
    assert r["risk"]["rr"] >= 3
    cm = r["commit"]
    assert cm.get("vol_mult") is not None and cm["vol_mult"] > 1.0                # c0 volume (futures) खरंच वापरला
    assert "5M CHoCH" in r["checklist"]["⑥"][1]                                  # c1 LTF CHoCH
    assert rows[0]["decision"] != "setup" and "वेळ-खिडकी" in rows[0]["checklist"]["⑥"][1]   # 09:15 = entry नाही (फक्त पुरावा)
    k = r["bar"] + 1                                                              # setup bar वर कापलेलं data ⇒ तोच निर्णय
    end = V.bar_end[r["bar"]]
    Vt = E3.V22(m15.iloc[:k].reset_index(drop=True), s=S_ROLE, ltf=ltf[pd.to_datetime(ltf["timestamp"]) < end],
                futures=fut[pd.to_datetime(fut["timestamp"]) < end])
    rt = Vt.decide(r["bar"])
    assert (rt["decision"], rt["conviction"], rt["risk"]) == (r["decision"], r["conviction"], r["risk"])


def test_mirror_gives_the_same_decisions():
    Vb, *_r, bb = _run(False)
    Vu, *_s, bu = _run(True)
    db = [Vb.decide(t)["decision"] for t in bb[:6]]
    du = [Vu.decide(t)["decision"] for t in bu[:6]]
    assert db == du and "setup" in db


def test_maturity_is_evidence_only_on_the_oct12_case(case):
    mirror, (V, m15, fut, ltf, bars) = case
    base = {t: V.decide(t) for t in bars[:6]}
    V.daily = [dataclasses.replace(x, mature=True) if x.trend in ("UP", "DOWN") else x for x in V.daily]
    try:
        for t, r0 in base.items():
            r = V.decide(t)
            assert r["mature"] and r["mature_step_down"] and r["decision"] == r0["decision"]
            if r0["decision"] == "setup":
                assert r["conviction"] == M.step_down_conv(r0["conviction"])
    finally:
        V.daily = E3.DD.fold(V.daily_df, V.s)


@pytest.mark.parametrize("d", [M.DOWN, M.UP])
def test_opening_candle_counts_as_evidence_entry_window_unchanged(d):
    """09:15 candle (pullback-दिशेची) + 09:30 ने तिला गिळलं ⇒ engulf (opening candle पुरावा); evidence_start = entry_start (जुनं) ⇒ engulf
    नाही. 09:15 candle स्वतः कधीच entry नाही."""
    base = [(100, 101, 99, 100.5), (100.5, 101.5, 100, 101), (101, 101.4, 100.6, 101.2)]   # आदला दिवस
    if d == M.DOWN:
        today = [(101.0, 102.4, 100.9, 102.2), (102.3, 102.5, 100.2, 100.4)]               # 09:15 हिरवी, 09:30 लाल engulf
    else:
        today = [(101.0, 101.1, 99.6, 99.8), (99.7, 101.8, 99.5, 101.6)]
    rows = base + today
    a = np.array(rows, float)
    A = {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}
    tss = np.array([pd.Timestamp("2030-01-07 14:45"), pd.Timestamp("2030-01-07 15:00"), pd.Timestamp("2030-01-07 15:15"),
                    pd.Timestamp("2030-01-08 09:15"), pd.Timestamp("2030-01-08 09:30")], dtype="datetime64[ns]")
    S = S3.load()
    assert M.reversal_form(A, 4, d, S, tss) == ("engulf", 1)
    assert M.reversal_form(A, 4, d, {**S, "evidence_start": S["entry_start"]}, tss) != ("engulf", 1)
    lvl = {"lo": 100.0, "hi": 103.0} if d == M.DOWN else {"lo": 99.0, "hi": 102.0}
    assert M.commitment(A, 3, d, lvl, S, tss)[1] == "entry वेळ-खिडकीबाहेर"                     # 09:15 = entry नाही
    ok, why, cm = M.commitment(A, 4, d, lvl, S, tss)
    assert ok and cm["form"] == "engulf"


def test_trendline_confluence_area_known_at_and_mirror(case):
    mirror, (V, m15, fut, ltf, bars) = case
    d = M.UP if mirror else M.DOWN
    trend = "UP" if mirror else "DOWN"
    t = bars[1]
    areas = V.tl_areas(t, trend)
    assert areas, "confluence area नाही"
    a = areas[0]
    par = next(x for x in V.levels.snapshot(t) if x["id"] == a["parent_level"])
    assert "tl" in a["births"] and a["hi"] >= par["lo"] and a["lo"] <= par["hi"]                 # overlap पट्टा (parent level शी)
    assert a["hi"] - a["lo"] < par["hi"] - par["lo"]                                             # रेघेचा पट्टा ⇒ अरुंद confluence
    assert a["lo"] - a["tl"]["tol"] - 1 <= a["tl"]["value_t"] <= a["hi"] + a["tl"]["tol"] + 1
    ln = a["tl"]
    assert ln["touches"] >= int(V.s["tl_min_touches"]) and (ln["slope"] < 0 if d == M.DOWN else ln["slope"] > 0)
    assert all(p.confirm_bar <= t for p in V.levels.known_pivots(t))
    Vt = E3.V22(m15.iloc[:t + 1].reset_index(drop=True), s=S_ROLE, ltf=ltf, futures=fut)   # कापलेलं data ⇒ तीच रेघ (lookahead नाही)
    assert TL.swing_line(Vt, t, d) == TL.swing_line(V, t, d)
    assert [x["id"] for x in Vt.tl_areas(t, trend)] == [x["id"] for x in areas]
    assert V.tl_areas(t, "RANGE") == []


def test_trendline_alone_is_not_an_area():
    """रेघ आहे पण horizontal level रेघेजवळ नाही ⇒ confluence area नाही (रेघ एकटी area नाही — OPEN_QUESTIONS)."""
    V, *_ = _run(False)
    t = len(V.levels.ts) - 1
    far = [{"id": 99, "role": "resistance", "lo": 1e6, "hi": 1e6 + 10, "births": ["a:D2"], "sweeps": 0, "fresh": True}]
    assert TL.confluence_areas(V, t, M.DOWN, far) == []


def test_futures_volume_15m_is_sum_of_0915_anchored_5m_bins():
    from legs2 import volume as LVOL
    day = pd.Timestamp("2030-01-07")
    m15 = pd.DataFrame({"timestamp": [day + pd.Timedelta(hours=9, minutes=15 + 15 * i) for i in range(4)]})
    t5 = [day + pd.Timedelta(hours=9, minutes=15 + 5 * i) for i in range(11)]                # 10:10 पर्यंत (शेवटचा 15M अपूर्ण)
    fut = pd.DataFrame({"timestamp": t5, "volume": [float(10 ** (i % 3)) * (i + 1) for i in range(11)],
                        "expiry": day + pd.Timedelta(days=10)})
    v = LVOL.bar_volume(m15, fut)
    exp0 = fut["volume"].iloc[0:3].sum()                                                     # 09:15 bar = 09:15 + 09:20 + 09:25
    assert v[0] == exp0 and v[1] == fut["volume"].iloc[3:6].sum() and v[2] == fut["volume"].iloc[6:9].sum()
    assert v[3] == fut["volume"].iloc[9:11].sum()                                             # live: फक्त आलेले bins (spot bar बंद नसेल तर वापर नाही)


def test_replay_day_upstox_source_is_read_only_and_writes_json(monkeypatch, tmp_path):
    """VPS मार्ग (`--source upstox`): Upstox fetch (mock — इथे fixture) ⇒ per-bar निर्णय + dry-run approval संदेश + --json; engine_signal
    store ला लिहीत नाही; token कधीच छापत नाही."""
    import json
    import cloud_db
    import engine_signal as ES
    import upstox_api as UA
    from scripts import replay_day as RD
    m15, fut, ltf = F.build(end_day="2030-03-04")
    daily = m15.assign(d=m15["timestamp"].dt.normalize()).groupby("d").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index().rename(columns={"d": "timestamp"})
    src = {"15minute": m15, "5minute": ltf, "day": daily}
    calls = []

    def fake_fetch(tok, sym, interval, frm, to):
        calls.append((sym, interval))
        return src[interval][["timestamp", "open", "high", "low", "close"]].assign(volume=0.0, oi=0.0)

    def no_write(*a, **k):
        raise AssertionError("store write")
    monkeypatch.setattr(UA, "fetch_candles_date_range", fake_fetch)
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *_a, **_k: "SECRET-TOKEN")
    monkeypatch.setattr(ES, "save", no_write)
    fpath = tmp_path / "fut.parquet"
    fut.to_parquet(fpath)
    out = tmp_path / "out.json"
    rc = RD.main(["--date", "2030-03-04", "--symbol", "NIFTY", "--source", "upstox", "--futures", str(fpath), "--dry-run",
                  "--json", str(out), "--out-dir", str(tmp_path)])
    assert rc == 0 and {c[1] for c in calls} == {"15minute", "5minute", "day"}
    j = json.loads(out.read_text(encoding="utf-8"))
    assert j["setup"]["side"] == "bear call" and j["setup"]["rr"] >= 3 and j["bars"][0]["ts"].endswith("09:15:00")
    assert "Vision skipped: dry run" in j["approval"]["message"] and "SECRET" not in out.read_text(encoding="utf-8")
