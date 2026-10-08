"""market_state (F1–F4) + V5: no-lookahead / truncation invariance. Synthetic data (CI); खरा data golden tests मध्ये."""
import numpy as np
import pandas as pd
import pytest

import market_state as MS
from market_state import core as C


def _path(waypoints, start="2026-09-01", noise=0.6, seed=1):
    """(सत्रातील 1m bars) waypoints [(n_minutes, price)] मधून linear path + लहान noise ⇒ 1m OHLC, फक्त 09:15–15:29."""
    rng = np.random.default_rng(seed)
    px = [waypoints[0][1]]
    for (n, p) in waypoints[1:]:
        px += list(np.linspace(px[-1], p, int(n) + 1)[1:])
    px = np.array(px, float)
    days = pd.bdate_range(start, periods=len(px) // 375 + 2)
    ts = np.concatenate([pd.date_range(f"{d:%Y-%m-%d} 09:15", periods=375, freq="1min") for d in days])[:len(px)]
    c = px + rng.normal(0, noise, len(px))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + np.abs(rng.normal(0, noise, len(px)))
    lo = np.minimum(o, c) - np.abs(rng.normal(0, noise, len(px)))
    return pd.DataFrame({"timestamp": pd.to_datetime(ts), "open": o, "high": h, "low": lo, "close": c, "volume": 0.0})


DOWN_THEN_DEEP_RALLY = [(0, 1300), (600, 1200), (300, 1260), (600, 1100), (300, 1160), (150, 1000),
                        (250, 1090), (250, 1045), (500, 1135), (150, 1100), (150, 1128)]


@pytest.fixture(scope="module")
def deep():
    return _path(DOWN_THEN_DEEP_RALLY)


def test_trend_down_protected_holds_through_deep_rally(deep):
    t = deep["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
    ms = MS.read(deep, t, run_elliott=False)
    assert ms["trend"]["dir"] == -1 and ms["trend"]["state"] == "trend"
    assert abs(ms["trend"]["protected"]["price"] - 1160) < 8                  # LL बनवणाऱ्या leg ची सुरुवात
    assert ms["impulse"]["dir"] == -1 and abs(ms["impulse"]["to"] - 1000) < 8
    corr = ms["correction"]
    assert corr["status"] == "correction" and 0.75 < corr["retrace"] < 1.0       # ~90% retrace, origin अबाधित ⇒ correction
    assert [x["label"] for x in corr["labels"]][:3] == ["A", "B", "C"]
    assert ms["side"] == "bear_call"


def test_real_break_then_hl_confirms_reversal():
    wp = DOWN_THEN_DEEP_RALLY[:-2] + [(300, 1230), (250, 1190), (500, 1290)]   # 1160 च्या पलीकडे real break, मग HL 1190
    df = _path(wp)
    t = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
    ms = MS.read(df, t, run_elliott=False)
    assert ms["trend"]["dir"] == 1
    assert any(e["event"] == "REAL_BREAK" for e in ms["trend"]["events"])
    assert any(e["event"] == "REVERSAL_CONFIRMED" for e in ms["trend"]["events"])


def test_break_without_confirmation_is_testing_and_side_unclear():
    wp = DOWN_THEN_DEEP_RALLY[:-2] + [(400, 1240)]                            # protected 1160 पलीकडे जोरात, HL अजून नाही
    df = _path(wp)
    t = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
    ms = MS.read(df, t, run_elliott=False)
    assert ms["trend"]["dir"] == -1 and ms["trend"]["state"] == "testing"
    assert ms["side"] == "unclear" and ms["side_reasons"]


def test_f3_leg_needs_displacement_overlap_and_bos(deep):
    fr = MS.frame(deep, "15m", deep["timestamp"].iloc[-1] + pd.Timedelta(minutes=1))
    pv = C.label(C.pivots(fr, 3.0))
    mr = C.BR.median_range(fr, 20)
    s = dict(C.DEFAULTS)
    legs = [C.leg_metrics(fr, pv, i, mr, s) for i in range(len(pv) - 1)]
    for lg in legs:
        if lg["impulse"]:
            assert lg["disp"] >= 1 and lg["bos"] is not None and lg["low_overlap"] and lg["size_mr"] >= 4
    assert any(not lg["impulse"] and lg["bos"] is None for lg in legs)         # BOS नसलेला leg impulse नाही


def test_decide_side_reasons():
    tr = {"dir": -1, "state": "trend", "protected": {"price": 1160.0}}
    imp = {"dir": -1, "from": 1160.0}
    assert C.decide_side(tr, imp, {"status": "correction"}, "DOWNTREND_WEAK", {1: {"dir": 0}}) == ("bear_call", [])
    side, why = C.decide_side(tr, imp, {"status": "correction"}, "UPTREND", {})
    assert side == "unclear" and "structure" in why[0]
    side, why = C.decide_side(tr, imp, {"status": "correction"}, "DOWNTREND", {1: {"dir": 1}})
    assert side == "unclear" and "Elliott" in why[0]
    side, why = C.decide_side(tr, imp, {"status": "origin_broken"}, "DOWNTREND", {})
    assert side == "unclear" and "origin" in why[0]
    assert C.decide_side(tr, None, None, "DOWNTREND", {})[0] == "unclear"


def _key(ms):
    imp, corr = ms["impulse"] or {}, ms["correction"] or {}
    return (ms["trend"]["dir"], ms["trend"]["state"], (ms["trend"]["protected"] or {}).get("price"), imp.get("from"), imp.get("to"),
            corr.get("status"), tuple((x["label"], x["from"], x["to"]) for x in corr.get("labels") or []), ms["side"], ms["structure_state"])


def test_v5_truncation_invariance(deep):
    """V5: t वरचं उत्तर t नंतरच्या data वर अवलंबून नाही (full data वि. t ला कापलेला data)."""
    ts = deep["timestamp"]
    for k in (0.55, 0.7, 0.85, 0.97):
        t = ts.iloc[int(len(ts) * k)].floor("15min")
        full = MS.read(deep, t, run_elliott=False)
        cut = MS.read(deep[ts + pd.Timedelta(minutes=1) <= t], t, run_elliott=False)
        assert _key(full) == _key(cut), t


def test_v5_future_bars_do_not_change_past(deep):
    """V5: नंतर bars जोडले (भविष्य) तरी आधीच्या asof चं उत्तर तेच — तसेच मधला अपूर्ण bar वापरला जात नाही."""
    ts = deep["timestamp"]
    t = ts.iloc[int(len(ts) * 0.8)].floor("15min")
    a = MS.read(deep[ts < t + pd.Timedelta(minutes=7)], t, run_elliott=False)       # t नंतरचे 7 मिनिटं (अपूर्ण 15M bar)
    b = MS.read(deep[ts + pd.Timedelta(minutes=1) <= t], t, run_elliott=False)
    assert _key(a) == _key(b)
    assert pd.Timestamp(a["swings"][-1]["ts"]) < t


def test_frames_exclude_cas_and_open_bars():
    df = _path([(0, 100), (3000, 140)], start="2026-10-05")
    t = pd.Timestamp("2026-10-06 15:31")
    fr = MS.frame(df, "15m", t)
    assert (fr["bar_end"] <= t).all()
    assert fr["timestamp"].dt.strftime("%H:%M").max() <= "15:00"                  # 15:15 CAS bin structure मध्ये नाही
    h1 = MS.frame(df, "1h", t)
    assert h1["timestamp"].dt.strftime("%H:%M").max() <= "14:15"
    m75 = MS.frame(df, "75m", t)
    assert set(m75["timestamp"].dt.strftime("%H:%M")) <= {"09:15", "10:30", "11:45", "13:00", "14:15"}


def test_precomputed_frames_give_same_answer(deep):
    """scan साठी full_frames(): asof ने कापलेले frames ⇒ df1m वरून काढल्यासारखंच उत्तर."""
    fr = MS.full_frames(deep)
    ts = deep["timestamp"]
    for k in (0.6, 0.8, 0.95):
        t = ts.iloc[int(len(ts) * k)].floor("15min")
        assert _key(MS.read(deep, t, run_elliott=False)) == _key(MS.read(deep, t, run_elliott=False, frames=fr)), t


def test_structure_with_market_state_counter_impulsive_is_danger_not_reversal():
    """F2: market_state दिला ⇒ counter-move impulsive / major acceptance फक्त धोक्याचे पुरावे; reversal फक्त origin real break."""
    from chart_reader import settings as CS
    from chart_reader import structure as ST
    df = _path(DOWN_THEN_DEEP_RALLY)
    t = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
    ms = MS.read(df, t, run_elliott=False)
    trig = MS.frame(df, "15m", t)
    s = CS.load()
    r = ST.read(trig, s, ms=ms)
    assert r["side"] == -1 and r["impulse"]["origin"] == round(ms["impulse"]["from"], 2)
    assert r["pullback"] != "reversal" or "impulse_origin_acceptance" in r["reversal_reasons"]
    assert [x["label"] for x in r.get("abc", [])][:3] == ["A", "B", "C"]
    no_imp = ST.read(trig, s, ms={**ms, "impulse": None})
    assert no_imp["impulse"] is None and "market_state" in no_imp["facts"][0]


def test_after_reversal_new_hh_moves_protected_and_later_break_is_testing():
    """V3 review (blocking): reversal नंतर trend चं टोक चुकीचं ठेवलं तर पुढचा BOS कधीच होत नव्हता. आता नवे HH ⇒ protected पुढे सरकतो,
    आणि त्या HL चा real break ⇒ "testing"."""
    wp = DOWN_THEN_DEEP_RALLY[:-2] + [(300, 1230), (250, 1190), (500, 1290), (200, 1250), (300, 1360), (200, 1320), (300, 1420), (400, 1270)]
    df = _path(wp)
    t = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
    tr = MS.read(df, t, run_elliott=False)["trend"]
    assert tr["dir"] == 1 and tr["state"] == "testing"
    assert abs(tr["protected"]["price"] - 1320) < 10                             # शेवटचा HL (1190 नाही)
    assert sum(e["event"] == "BOS" and e["dir"] == 1 for e in tr["events"]) >= 2
