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

# Z-1 (Abhi K4 flip नियम): या synthetic fixture चा supply = acceptance ने flip झालेला support, आणि त्याखाली आधीचा swing low नाही ⇒
# नव्या नियमाने BROKEN (trade location नाही). हे tests a2 / c0 / c1 / confluence चे ⇒ जुना flip नियम स्पष्ट pin (असर्ट तसेच);
# default नियमावर हाच fixture: tests/test_decision3_flip.py::test_oct12_synthetic_fixture_supply_flips_when_the_first_swing_after_the_break_is_confirmed.
S_ROLE = {"level_death_side": "role", "level_flip_rule": "acceptance", "a2_handover_required": False,   # Z-1m आधीचा fixture — pin
          "level_merge": True, "zone_visit_rule": "touch_window",
          "commit_volume_rule": "opposite", "line_rule": "sigma"}   # Abhi Z-1u / Z-1v आधीचा fixture — legacy pin, असर्ट तसेच
S_OLD = {**S_ROLE, "rr_step": True, "entry_first_bar": False}              # Abhi 13 Oct आधीचे नियम (⑦ R:R + 09:15 फक्त पुरावा) — जुने असर्ट pin


def _run(mirror, s=S_ROLE):
    m15, fut, ltf = F.build(mirror=mirror)
    V = E3.V22(m15, s=s, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last]
    return V, m15, fut, ltf, bars


@pytest.fixture(scope="module", params=[False, True], ids=["bear_call", "bull_put_mirror"])
def case(request):
    return request.param, _run(request.param)


@pytest.fixture(scope="module", params=[False, True], ids=["bear_call", "bull_put_mirror"])
def case_old(request):
    return request.param, _run(request.param, S_OLD)


def test_first_hour_setup_with_a2_c0_c1_active(case_old):
    mirror, (V, m15, fut, ltf, bars) = case_old                                   # जुने नियम (⑦ R:R, 09:15 पुरावा) — inputs pin
    rows = [V.decide(t) for t in bars]
    st = [r for r in rows if r["decision"] == "setup"]
    assert st, [(r["ts"][11:16], r["checklist"]["⑥"][1][:60]) for r in rows[:4]]
    r = st[0]
    assert pd.Timestamp(r["ts"]) < V.levels.ts.iloc[bars[0]] + pd.Timedelta(hours=1)          # पहिल्या तासात
    assert r["trend_used"] == ("UP" if mirror else "DOWN")
    assert r["level"]["role"] == ("support" if mirror else "resistance")
    assert r["risk"]["rr"] >= 3
    cm = r["commit"]
    assert cm.get("vol_na") is False and cm.get("vol_vs") == "no opposite-side candle in this visit"   # FUT volume read; the visit has no
    assert cm["grade"] == "B" and cm.get("vol_mult") is None               # opposite-side candle ⇒ nothing compared ⇒ fail-safe grade cap B (Z-1z-d)
    assert "5M CHoCH" in r["checklist"]["⑥"][1]                                  # c1 LTF CHoCH
    assert rows[0]["decision"] != "setup" and "वेळ-खिडकी" in rows[0]["checklist"]["⑥"][1]   # 09:15 = entry नाही (फक्त पुरावा)
    k = r["bar"] + 1                                                              # setup bar वर कापलेलं data ⇒ तोच निर्णय
    end = V.bar_end[r["bar"]]
    Vt = E3.V22(m15.iloc[:k].reset_index(drop=True), s=S_OLD, ltf=ltf[pd.to_datetime(ltf["timestamp"]) < end],
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
    dflt = {t: V.decide(t) for t in bars[:6]}
    V.s["wave_gates"] = True                                                     # Abhi 12 Oct नियम (step-down) pin — B1 ने बदलला
    base = {t: V.decide(t) for t in bars[:6]}
    V.daily = [dataclasses.replace(x, mature=True) if x.trend in ("UP", "DOWN") else x for x in V.daily]
    try:
        for t, r0 in base.items():
            r = V.decide(t)
            assert r["mature"] and r["mature_step_down"] and r["decision"] == r0["decision"]
            if r0["decision"] == "setup":
                assert r["conviction"] == M.step_down_conv(r0["conviction"])
        V.s["wave_gates"] = False                                                # Abhi B1 (default): maturity = context, grade unchanged
        for t, r0 in dflt.items():
            r = V.decide(t)
            assert r["mature"] and not r["mature_step_down"] and (r["decision"], r["conviction"]) == (r0["decision"], r0["conviction"])
    finally:
        V.s["wave_gates"] = False
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
    assert M.reversal_form(A, 4, d, {**S, "evidence_start": S["entry_start"]}, tss) == ("engulf", 1)   # method P2: no session window
    L = {**S, "session_windows": True}                                     # legacy (what-if): the evidence window splits the session
    assert M.reversal_form(A, 4, d, {**L, "evidence_start": L["entry_start"]}, tss) != ("engulf", 1)
    lvl = {"lo": 100.0, "hi": 103.0} if d == M.DOWN else {"lo": 99.0, "hi": 102.0}
    assert M.commitment(A, 3, d, lvl, {**L, "entry_first_bar": False}, tss)[1] == "entry वेळ-खिडकीबाहेर"   # जुना नियम (pin)
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


def _fake_V(closes, piv, sig=10.0, s=None):
    from types import SimpleNamespace as NS
    c = np.asarray(closes, float)
    lv = NS(A={"open": c, "high": c + 1, "low": c - 1, "close": c}, sig1h=np.full(len(c), sig), known_pivots=lambda t: piv)
    return NS(levels=lv, s=S3.load({"line_rule": "sigma"} if s is None else s))   # default here: the legacy fixture rule


@pytest.mark.parametrize("mirror", [False, True])
def test_swing_line_dies_on_close_through_and_wrong_side_area_dropped(mirror):
    """Review: p2 नंतर (t − 1 पर्यंत) close रेघेपलीकडे ⇒ रेघ नाही (k_line सारखं); confluence area किंमतीच्या चुकीच्या बाजूला ⇒ नाही. आरसा."""
    from types import SimpleNamespace as NS
    sg = -1.0 if mirror else 1.0
    mid = 100.0
    f = (lambda x: 2 * mid - x) if mirror else (lambda x: x)                  # noqa: E731
    d = M.UP if mirror else M.DOWN
    kind = "L" if mirror else "H"
    piv = [NS(kind=kind, price=f(120.0), bar=0, confirm_bar=2), NS(kind=kind, price=f(110.0), bar=10, confirm_bar=12)]   # रेघ: 120 ⇒ 110, −1/bar
    closes = [f(100.0)] * 20                                                    # सगळे closes रेघेखाली (bear) ⇒ रेघ जिवंत
    ln = TL.swing_line(_fake_V(closes, piv), 15, d)
    assert ln is not None and abs(ln["value_t"] - f(105.0)) < 1e-6 and (ln["slope"] < 0) == (not mirror)
    broken = list(closes)
    broken[13] = f(108.0)                                                       # bar 13: रेघ 107 ⇒ close 108 पलीकडे
    assert TL.swing_line(_fake_V(broken, piv), 15, d) is None
    assert TL.swing_line(_fake_V(broken, piv), 13, d) is not None               # t चा स्वतःचा close मोजत नाही (③ breakout तपासणी)
    V = _fake_V(closes, piv)
    role = "support" if mirror else "resistance"
    near = {"id": 1, "role": role, "lo": min(f(103.0), f(108.0)), "hi": max(f(103.0), f(108.0)), "births": ["a:D2"], "sweeps": 1, "fresh": True}
    assert [a["id"] for a in TL.confluence_areas(V, 15, d, [near])] == ["1+TL"]
    V2 = _fake_V([f(112.0)] * 15 + [f(112.0)], piv)                              # किंमत area च्या पलीकडे (resistance खाली राहिला)
    V2.levels.A["close"][:15] = f(100.0)
    assert TL.confluence_areas(V2, 15, d, [near]) == []


def test_tl_birth_does_not_raise_grade_over_parent(case):
    """Review: "tl" जन्म grade वाढवत नाही — confluence area चा level ★ / conviction parent level इतकाच; confluence फक्त पुरावा-नोंद."""
    mirror, (V, m15, fut, ltf, bars) = case
    trend = "UP" if mirror else "DOWN"
    t = bars[2]
    ok1, _w, _st, ctx = V.step1(t)
    act = V.levels.active(t, trend)
    areas = V.tl_areas(t, trend, act)
    assert areas
    a = areas[0]
    par = next(x for x in act if x["id"] == a["parent_level"])
    _d1, _p1, e_par = V._level_eval(t, trend, par, ctx["cap"], ctx["notes"])
    _d2, _p2, e_tl = V._level_eval(t, trend, a, ctx["cap"], ctx["notes"])
    assert e_tl["evidence"]["tl_confluence"] is True and e_par["evidence"]["tl_confluence"] is None
    assert e_tl["evidence"]["level_star"] == e_par["evidence"]["level_star"]
    assert e_tl["conv_score"] == e_par["conv_score"]


def test_replay_loaders_drop_nifty_holdout_rows():
    """Review: replay चे 15M / 5M / FUT frames data_policy मधून — NIFTY holdout row कधीच नाही; इतर symbols तसेच."""
    from scripts import replay_day as RD
    ts = pd.to_datetime(["2023-05-02 09:15", "2025-01-06 09:15", "2026-10-09 09:15"])
    df = pd.DataFrame({"timestamp": ts, "volume": [1.0, 2.0, 3.0]})
    got = RD.allowed(df, "NIFTY")
    assert list(got["volume"]) == [1.0, 3.0]
    assert len(RD.allowed(df, "BANKNIFTY")) == 3 and RD.allowed(None, "NIFTY") is None


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


class FakeFeed:
    """engine3_live.UpstoxFeed सारखा (index / futures); `today` नोंदवतो. D नंतरचे rows (D+1 / intraday) मुद्दाम देतो ⇒ lookahead तपासणी."""

    def __init__(self, src, today, calls, fut=None):
        self.src, self.today, self.calls, self.fut = src, today, calls, fut

    def index(self, sym, interval, days):
        self.calls.append((sym, interval, self.today))
        df = self.src[interval][["timestamp", "open", "high", "low", "close"]].assign(volume=0.0, oi=0.0)
        later = df.tail(1).assign(timestamp=pd.Timestamp(self.today) + pd.Timedelta(hours=9, minutes=15), close=1e9)
        return pd.concat([df, later], ignore_index=True)

    def futures(self, sym, interval, days):
        import engine3_live as E3L
        if self.fut is None:
            raise E3L.EngineDataError("no FUT")
        self.calls.append((sym, "fut", self.today))
        return self.fut


def _feed_src(end_day):
    m15, fut, ltf = F.build(end_day=end_day)
    daily = m15.assign(d=m15["timestamp"].dt.normalize()).groupby("d").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index().rename(columns={"d": "timestamp"})
    return {"15minute": m15, "5minute": ltf, "day": daily}, fut


def test_replay_day_upstox_source_is_read_only_and_writes_json(monkeypatch, tmp_path):
    """VPS मार्ग (`--source upstox`): live engine चाच feed (engine3_live.UpstoxFeed — इथे fake) ⇒ per-bar निर्णय + dry-run approval
    संदेश + --json; engine_signal store ला लिहीत नाही; token कधीच छापत नाही."""
    import json
    import cloud_db
    import engine_signal as ES
    from scripts import replay_day as RD
    src, fut = _feed_src("2030-03-04")
    calls = []

    def no_write(*a, **k):
        raise AssertionError("store write")
    monkeypatch.setattr(RD, "_feed", lambda tok, today: FakeFeed(src, today, calls))
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *_a, **_k: "SECRET-TOKEN")
    monkeypatch.setattr(ES, "save", no_write)
    fpath = tmp_path / "fut.parquet"
    fut.to_parquet(fpath)
    out = tmp_path / "out.json"
    rc = RD.main(["--date", "2030-03-04", "--symbol", "NIFTY", "--source", "upstox", "--futures", str(fpath), "--dry-run",
                  "--json", str(out), "--out-dir", str(tmp_path), "--legacy-rr", "--no-first-bar-entry",
                  "--flip-rule", "acceptance", "--legacy-zone-gates", "--legacy-bands"])                          # rr असर्ट ⇒ जुने नियम (pin); Z-1 flip pin
    assert rc == 0 and {c[1] for c in calls} == {"15minute", "5minute", "day"}
    j = json.loads(out.read_text(encoding="utf-8"))
    assert j["setup"]["side"] == "bear call" and j["setup"]["rr"] >= 3 and j["bars"][0]["ts"].endswith("09:15:00")
    assert "Vision skipped: dry run" in j["approval"]["message"] and "SECRET" not in out.read_text(encoding="utf-8")


def test_replay_upstox_loader_uses_feed_with_today_d_plus_1_and_no_lookahead(monkeypatch, tmp_path):
    """Past day D: feed today = D+1 (history मध्ये D समाविष्ट), D च्या close नंतरचा एकही row नाही (fake feed D+1 चे rows देतो);
    FUT file मध्ये D नाही ⇒ feed.futures (≤ D); NIFTY holdout filter कायम."""
    import argparse
    import datetime
    import cloud_db
    from scripts import replay_day as RD
    src, fut = _feed_src("2030-03-04")
    fut_late = pd.concat([fut, fut.tail(1).assign(timestamp=pd.Timestamp("2030-03-05 09:15"))], ignore_index=True)
    calls = []
    monkeypatch.setattr(RD, "_feed", lambda tok, today: FakeFeed(src, today, calls, fut=fut_late))
    monkeypatch.setattr(RD, "_front_on", lambda tok, sym, d: None)
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *_a, **_k: "tok")
    a = argparse.Namespace(symbol="NIFTY", m15_days=90, ltf_days=10, daily_days=3650, futures=str(tmp_path / "missing.parquet"))
    day = pd.Timestamp("2030-03-04")
    m15, m1, ltf, f5, daily = RD.load_upstox(a, day)
    assert {c[2] for c in calls} == {datetime.date(2030, 3, 5)} and any(c[1] == "fut" for c in calls)
    for df in (m15, ltf, f5, daily):
        assert pd.to_datetime(df["timestamp"]).max() < day + pd.Timedelta(hours=15, minutes=30)
    assert (pd.to_datetime(m15["timestamp"]).dt.normalize() == day).sum() == 25 and m15["close"].max() < 1e9
    assert pd.to_datetime(daily["timestamp"]).max() == day
    # holdout: NIFTY sealed rows feed मधून आले तरी 15M input मध्ये नाहीत
    from elliott import data_policy as DP
    sealed = pd.Timestamp("2025-01-06 09:15")
    assert DP.period(sealed) == "HOLDOUT"
    src2 = dict(src)
    src2["15minute"] = pd.concat([src["15minute"].head(1).assign(timestamp=sealed), src["15minute"]], ignore_index=True)
    monkeypatch.setattr(RD, "_feed", lambda tok, today: FakeFeed(src2, today, [], fut=fut))
    m15b = RD.load_upstox(a, day)[0]
    assert sealed not in set(pd.to_datetime(m15b["timestamp"]))


def test_replay_futures_all_file_picks_days_front_month_not_alphabetical():
    """`_all` file (timestamp + contract): प्रत्येक दिवशी त्या दिवसाचा front month (near_month नियम) — alphabetical पहिला ("24 NOV" <
    "27 OCT") नाही; expiry नंतर पुढचा contract."""
    from scripts import replay_day as RD
    rows = []
    for d in ("2026-10-13", "2026-10-28"):
        for c, v in (("NIFTY FUT 24 NOV 26", 40.0), ("NIFTY FUT 27 OCT 26", 100.0)):
            rows.append({"timestamp": pd.Timestamp(f"{d} 09:15"), "volume": v, "contract": c})
    allf = pd.DataFrame(rows)
    got = RD.until_close(allf, pd.Timestamp("2026-10-13"))
    assert list(got["contract"]) == ["NIFTY FUT 27 OCT 26"] and list(got["volume"]) == [100.0]
    got = RD.until_close(allf, pd.Timestamp("2026-10-28"))
    assert list(got["contract"]) == ["NIFTY FUT 27 OCT 26", "NIFTY FUT 24 NOV 26"] and list(got["volume"]) == [100.0, 40.0]
    one = pd.DataFrame({"timestamp": [pd.Timestamp("2026-10-13 09:15")] * 2, "volume": [1.0, 2.0]})
    assert len(RD.until_close(one, pd.Timestamp("2026-10-13"))) == 1


def test_replay_feed_fallback_warns_with_contract_and_flags_expiry_day(monkeypatch, tmp_path, capsys):
    """Collector file मध्ये दिवस D नाही ⇒ feed चा contract: ⚠️ ओळ त्याचं नाव सांगते; D = त्या दिवसाच्या front month चा expiry (feed ने
    D+1 चा पुढचा contract घेतला) ⇒ "different contract … c0 volume unreliable"."""
    import argparse
    import cloud_db
    from scripts import replay_day as RD
    src, fut = _feed_src("2030-03-04")
    nxt = fut.assign(contract="NIFTY FUT 25 APR 30", expiry=pd.Timestamp("2030-04-25"))
    monkeypatch.setattr(RD, "_feed", lambda tok, today: FakeFeed(src, today, [], fut=nxt))
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda *_a, **_k: "tok")
    a = argparse.Namespace(symbol="NIFTY", m15_days=90, ltf_days=10, daily_days=3650, futures=str(tmp_path / "missing.parquet"))
    day = pd.Timestamp("2030-03-04")
    monkeypatch.setattr(RD, "_front_on", lambda tok, sym, d: {"trading_symbol": "NIFTY FUT 25 APR 30", "expiry": "2030-04-25"})
    RD.load_upstox(a, day)
    out = capsys.readouterr().out
    assert "⚠️ FUT 5M volume" in out and "contract NIFTY FUT 25 APR 30" in out and "unreliable" not in out
    monkeypatch.setattr(RD, "_front_on", lambda tok, sym, d: {"trading_symbol": "NIFTY FUT 04 MAR 30", "expiry": "2030-03-04"})
    RD.load_upstox(a, day)
    out = capsys.readouterr().out
    assert ("contract NIFTY FUT 25 APR 30" in out and "volume from a different contract than the day's front month (NIFTY FUT 04 MAR 30)"
            in out and "c0 volume unreliable" in out)


@pytest.mark.parametrize("mirror", [False, True])
def test_method_lines_touch_by_candle_and_confluence_labels_the_area_itself(mirror):
    """Method §3 Lines: a line from two separate reactions on the structure's swings; a later swing candle touches it when its wick
    reaches the line with the body on its side (no σ tolerance, no touch count); a close through between the reactions kills it; where
    the line passes through an area that area is the confluence — the same band, labelled (never a new, narrowed band). Mirror."""
    from types import SimpleNamespace as NS
    f = (lambda x: 200.0 - x) if mirror else (lambda x: x)                    # noqa: E731
    d = M.UP if mirror else M.DOWN
    kind = "L" if mirror else "H"
    opp = "H" if mirror else "L"                                                 # price left the line between the reactions
    piv = [NS(kind=kind, price=f(120.0), bar=0, confirm_bar=2), NS(kind=opp, price=f(98.0), bar=3, confirm_bar=5),
           NS(kind=kind, price=f(110.0), bar=10, confirm_bar=12)]
    V = _fake_V([f(100.0)] * 20, piv, s={})
    assert V.s["line_rule"] == "logic"
    ln = TL.swing_line(V, 15, d)
    assert ln is not None and ln["touches"] == 2 and abs(ln["value_t"] - f(105.0)) < 1e-6
    role = "support" if mirror else "resistance"
    near = {"id": 1, "role": role, "lo": min(f(103.0), f(108.0)), "hi": max(f(103.0), f(108.0)), "births": ["a:D2"], "sweeps": 1, "fresh": True}
    far = {**near, "id": 2, "lo": min(f(90.0), f(95.0)), "hi": max(f(90.0), f(95.0))}
    got = TL.confluence_areas(V, 15, d, [near, far])
    assert [a["id"] for a in got] == [1] and (got[0]["lo"], got[0]["hi"]) == (near["lo"], near["hi"]) and "tl" in got[0]["births"]
    mid = NS(kind=kind, price=f(117.0), bar=5, confirm_bar=7)                  # a swing between the reactions whose candle closes through
    V2 = _fake_V([f(100.0)] * 20, [piv[0], mid, piv[1], piv[2]], s={})
    V2.levels.A["close"][5] = f(116.5)                                          # line at bar 5 = 115 ⇒ close 116.5 beyond it
    assert TL.swing_line(V2, 15, d) is None                                     # (117 ⇒ 110 has no opposite swing between: one reaction)
    V3 = _fake_V([f(100.0)] * 20, piv, s={})
    V3.levels.A["close"][5] = f(116.5)                                          # NOT a swing: any candle between the reactions that
    assert TL.swing_line(V3, 15, d) is None                                     # closes through the line kills the pair
    V4 = _fake_V([f(100.0)] * 20, piv, s={})
    V4.levels.A["close"][13] = f(108.0)                                         # after p2: line 107 ⇒ a close beyond, back at bar 14,
    assert TL.swing_line(V4, 15, d) is not None                                 # no swing beyond ⇒ a throw-over, the line stands (K6.5)
    A = {"open": np.array([f(114.0)]), "close": np.array([f(114.2)]), "high": np.array([max(f(115.5), f(113.8))]),
         "low": np.array([min(f(115.5), f(113.8))])}
    assert TL.touches(A, 0, f(115.0), kind) is True                       # wick reaches the line, body stays on its side ⇒ a touch
    assert TL.touches(A, 0, f(116.0), kind) is False                      # the wick does not reach it
    assert TL.touches(A, 0, f(114.1), kind) is False                      # the line runs through the body ⇒ not a touch


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put_mirror"])
def test_step2_confluence_labels_the_area_in_place_no_new_band(mirror):
    """Method §3 (line_rule = logic): where the trade-side line passes through an active area, step2 returns the SAME areas (count,
    ids, bands) with that one labelled "tl" — the legacy rule appended a separate, narrowed "+TL" area instead. Mirror."""
    d, trend = (M.UP, "UP") if mirror else (M.DOWN, "DOWN")
    V, _, _, _, bars = _run(mirror, {**S_ROLE, "line_rule": "logic"})
    Vs, _, _, _, _ = _run(mirror)
    t = next(b for b in bars if TL.swing_line(V, b, d) is not None and TL.confluence_areas(V, b, d, V.levels.active(b, trend)))
    plain = V.levels.active(t, trend)
    _, _, act = V.step2(t, trend)
    assert [(x["id"], x["lo"], x["hi"]) for x in act] == [(x["id"], x["lo"], x["hi"]) for x in plain]
    lab = [x for x in act if "tl" in x["births"]]
    assert len(lab) == 1 and lab[0].get("confluence_line") is True and lab[0]["tl"]["value_t"] is not None
    assert lab[0]["lo"] <= lab[0]["tl"]["value_t"] <= lab[0]["hi"]
    _, _, act_s = Vs.step2(t, trend)
    assert len(act_s) == len(plain) + 1 and any(str(x["id"]).endswith("+TL") for x in act_s)   # legacy: a separate narrowed area

