"""c1 (Abhi, LEVEL_BOTS_CONFIRMATION §2 c1 — REQUIRED): level bots मध्ये lower-timeframe CHoCH by close, a2 + c0 सोबत — एकच shared
function (decision3.method.confirm). प्रत्येक case आरशासह (किंमत p ↦ 2000 − p ⇒ तोच निर्णय, उलट बाजू).

Scenario: 5M setup bars = खालच्या 1M bars चीच बेरीज (सुसंगत data). Demand 990–1000, UP trend. 1M: pullback, area मध्ये lower low 987
(09:47), higher low 992 (09:50), मग 1M candle चा close शेवटच्या LTF lower high (1002.5, 09:44) वर ⇒ CHoCH (09:53 ला बंद). 5M commitment
(09:50–09:55) = bullish engulf, window पेक्षा dominant."""
import pandas as pd
import pytest

from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from tests.ltf_fixtures import ltf_rows, split_bars

DAY0 = pd.Timestamp("2001-01-01 09:15")
MIR = 2000.0
UP_CTX = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP"}
DOWN_CTX = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN"}
AREA = (990.0, 1000.0)
OTHERS = [(1090.0, 1100.0), (900.0, 910.0)]
PULL5 = [(1030, 1031, 1024, 1025), (1025, 1027, 1018, 1019), (1019, 1021, 1012, 1013), (1013, 1015, 1006, 1007),
         (1007, 1009, 1001, 1002)]

BASE = [(1002, 1003, 1000, 1000.5), (1000.5, 1001, 997, 997.5), (997.5, 998, 995, 996), (996, 999, 995.5, 998.5),
        (998.5, 1002.5, 998, 999),                                         # 09:44 LTF lower high 1002.5
        (999, 999.5, 994, 994.5), (994.5, 995, 990, 991), (991, 991.5, 987, 988),   # 09:47 lower low 987
        (988, 994, 988, 993.5), (993.5, 997, 993, 996.5)]
HL = [(996.5, 997, 992, 993), (993, 996, 992.5, 995.5)]                    # 09:50 higher low 992
CHOCH = BASE + HL + [(995.5, 1003, 995, 1002.8), (1002.8, 1006, 1002, 1005.5), (1005.5, 1009, 1005, 1008)]   # 09:52 close > 1002.5
WICK = BASE + HL + [(995.5, 1004, 995, 1001.5), (1001.5, 1003.5, 1000.5, 1001), (1001, 1003, 1000.8, 1002.2)]  # wick वर, close नाही
LOWER = BASE + [(996.5, 997, 985, 985.5), (985.5, 992, 985.5, 991.5), (991.5, 998, 991.5, 997.5), (997.5, 1004, 997.5, 1003.5),
                (1003.5, 1009, 1003.5, 1008)]                              # 09:50 नवा lower low 985 (sweep नाही), मग V — higher low नाही


def _case(ltf_tail, vol_commit=200.0, mirror=False, vol=True):
    """1M (pullback = 5M PULL चे तुकडे + हाताने 09:40 नंतर) ⇒ 5M setup bars (बेरीज) + warm-up. रिटर्न (bars, k, ltf, area, ctx, others)."""
    pre = [(1030.0, 1034.0, 1026.0, 1030.0)] * 30
    warm = pd.DataFrame(pre, columns=["open", "high", "low", "close"])
    warm.insert(0, "timestamp", [DAY0 - pd.Timedelta(days=1) + pd.Timedelta(minutes=5 * i) for i in range(30)])
    p5 = pd.DataFrame([tuple(map(float, r)) for r in PULL5], columns=["open", "high", "low", "close"])
    p5.insert(0, "timestamp", [DAY0 + pd.Timedelta(minutes=5 * i) for i in range(len(PULL5))])
    m1 = pd.concat([split_bars(p5, 5, 5), ltf_rows(ltf_tail, DAY0 + pd.Timedelta(minutes=25), 1)], ignore_index=True)
    g = m1.assign(b=(m1["timestamp"] - DAY0) // pd.Timedelta(minutes=5)).groupby("b")
    today = pd.DataFrame({"timestamp": g["timestamp"].first(), "open": g["open"].first(), "high": g["high"].max(),
                          "low": g["low"].min(), "close": g["close"].last()}).reset_index(drop=True)
    bars = pd.concat([warm, today], ignore_index=True)
    k = len(warm)
    if vol:
        bars["volume"] = [100.0] * (len(bars) - 1) + [vol_commit]
    area, ctx, others = AREA, UP_CTX, OTHERS
    if mirror:
        for df in (bars, m1):
            o, h, lo, c = MIR - df["open"], MIR - df["low"], MIR - df["high"], MIR - df["close"]
            df["open"], df["high"], df["low"], df["close"] = o, h, lo, c
        area, ctx, others = (MIR - AREA[1], MIR - AREA[0]), DOWN_CTX, [(MIR - b, MIR - a) for a, b in OTHERS]
    return bars, k, m1, area, ctx, others


def _eval(ltf_tail, mirror=False, vol_commit=200.0, vol=True, ltf="same", s=None):
    bars, k, m1, area, ctx, others = _case(ltf_tail, vol_commit, mirror, vol)
    return LR.evaluate(bars, area, ctx, others, session_start=k, ltf=m1 if ltf == "same" else ltf, tf_minutes=5, s=s)


def test_setup_bars_are_the_ltf_aggregate():
    bars, k, m1, *_ = _case(CHOCH)
    assert tuple(bars.iloc[-1][["open", "high", "low", "close"]]) == (996.5, 1009.0, 992.0, 1008.0)    # bullish engulf 09:50
    assert tuple(bars.iloc[-3][["open", "high", "low", "close"]]) == (1002.0, 1003.0, 995.0, 999.0)    # arrival (TOUCH)


@pytest.mark.parametrize("mirror", [False, True])
def test_higher_low_close_above_lh_dominant_higher_volume_is_entry(mirror):
    r = _eval(CHOCH, mirror)
    assert r["state"] == LR.CONFIRMED and r["entry"] and r["side"] == (LR.BEAR if mirror else LR.BULL), r["events"]
    word = "1M CHoCH: lower high 1,008, close below HL" if mirror else "1M CHoCH: higher low 992, close above LH"
    assert r["ltf_line"].startswith(word) and r["ltf_line"].endswith("at 09:53")
    assert "volume 2.0× window avg" in r["commit_line"]


@pytest.mark.parametrize("mirror", [False, True])
def test_ltf_lower_lows_continuing_is_no_entry(mirror):
    r = _eval(LOWER, mirror)
    assert not r["entry"] and r["state"] == LR.ARMED and r["ltf_wait"] == LR.R_LTF_AGAINST, r["events"]
    assert any(e[2] == LR.R_LTF_AGAINST for e in r["events"])
    assert ("still making lower highs" if mirror else "still making lower lows") in r["ltf_line"]
    assert LGB.status_of(r) == "SKIPPED_GATE_LTF_AGAINST" and LR.R_LTF_AGAINST in LR.describe(r)


@pytest.mark.parametrize("mirror", [False, True])
def test_wick_above_lh_only_is_no_choch(mirror):
    r = _eval(WICK, mirror)
    assert not r["entry"] and r["ltf_wait"] == LR.R_LTF_PENDING and "(wick only)" in r["ltf_line"], r["events"]
    assert LGB.status_of(r) == "SKIPPED_GATE_LTF_NO_CHOCH"


@pytest.mark.parametrize("mirror", [False, True])
def test_dominant_candle_on_lower_volume_no_entry_this_candle(mirror):
    r = _eval(CHOCH, mirror, vol_commit=90.0)
    assert not r["entry"] and r["state"] == LR.ARMED and any(e[2] == LR.R_LOW_VOL for e in r["events"])


@pytest.mark.parametrize("mirror", [False, True])
def test_volume_na_entry_allowed_grade_cap_b(mirror):
    r = _eval(CHOCH, mirror, vol=False)
    assert r["entry"] and r["grade"] == "B" and "volume: NA" in r["commit_line"]


@pytest.mark.parametrize("mirror", [False, True])
def test_ltf_missing_fails_closed(mirror):
    r = _eval(CHOCH, mirror, ltf=None)
    assert not r["entry"] and r["ltf_wait"] == LR.R_LTF_MISSING and LGB.status_of(r) == "SKIPPED_GATE_LTF_MISSING"
    r = _eval(CHOCH, mirror, ltf=None, s={"ltf_choch": False})            # what-if: c1 बंद ⇒ a2 / c0 तसेच (entry)
    assert r["entry"]


@pytest.mark.parametrize("mirror", [False, True])
def test_absorption_is_no_entry_even_with_choch(mirror):
    """a2: area मध्ये उलट-बाजू volume वाढत मजबूत ⇒ commitment / CHoCH पाहतच नाही (test_level_reaction मधल्या absorption candles)."""
    from tests import test_level_reaction as T
    a1, a2, a3, a4 = (999, 1000, 997, 998), (998, 999, 997, 998.5), (998.5, 999.5, 991.5, 992.5), (992.5, 993.5, 990.2, 991)
    rows = T.PULL + [T.TOUCH, a1, a2, a3, a4, (991, 1004, 990.5, 1003)]
    df, k = T._vbars(rows, [100] * len(T.PULL) + [100, 80, 80, 150, 200, 300], mirror)
    area = (MIR - AREA[1], MIR - AREA[0]) if mirror else AREA
    oth = [(MIR - b, MIR - a) for a, b in OTHERS] if mirror else OTHERS
    r = LR.evaluate(df, area, DOWN_CTX if mirror else UP_CTX, oth, session_start=k, ltf=df.iloc[k:], tf_minutes=5)
    assert not r["entry"] and any(e[2] == LR.R_ABSORPTION for e in r["events"])


@pytest.mark.parametrize("mirror", [False, True])
def test_no_lookahead_ltf_after_setup_close_ignored_and_truncation_invariant(mirror):
    bars, k, m1, area, ctx, others = _case(CHOCH, mirror=mirror)
    later = ltf_rows([(1008, 1008.5, 960, 961)] * 3, DAY0 + pd.Timedelta(minutes=40), 1)   # setup close नंतर: नवा lower low
    if mirror:
        later = later.assign(open=MIR - later["open"], high=MIR - later["low"], low=MIR - later["high"], close=MIR - later["close"])
    full = pd.concat([m1, later], ignore_index=True)
    a = LR.evaluate(bars, area, ctx, others, session_start=k, ltf=m1, tf_minutes=5)
    b = LR.evaluate(bars, area, ctx, others, session_start=k, ltf=full, tf_minutes=5)
    assert a["entry"] and b["entry"] and a["events"] == b["events"] and a["ltf_line"] == b["ltf_line"]
    for m in range(k + 1, len(bars) + 1):                                  # setup bars कापले (पुढचे LTF दिले तरी) ⇒ तेच events
        part = LR.evaluate(bars.iloc[:m], area, ctx, others, session_start=k, ltf=full, tf_minutes=5)
        assert part["events"] == [e for e in b["events"] if e[0] < m]


def test_ltf_mapping_and_cycle_gate_fetch_per_bot(monkeypatch):
    """Abhi mapping: 5M setup ⇒ 1M (5M Instant, Classic), 15M ⇒ 5M (15M SRv2, MCX). LTF त्याच fetch मार्गाने, पहिल्या result ला एकदाच."""
    assert [LR.ltf_minutes_for(LGB.CONFIRM_TF[b]) for b in ("dynamic_sr_instant", "classic_sr", "srv2", "mcx")] == [1, 1, 5, 5]
    assert LR.ltf_minutes_for(15, {"ltf_minutes": 1}) == 1                 # dashboard override
    bars, k, m1, area, ctx, others = _case(CHOCH)
    now = bars["timestamp"].iloc[-1] + pd.Timedelta(minutes=6)
    monkeypatch.setattr(LR, "daily_trend", lambda *a, **k: UP_CTX)
    asked = []

    def fetch(tok, sym, minutes):
        asked.append(minutes)
        return bars.copy() if minutes == 5 else (m1.copy() if minutes == 1 else None)
    g = LGB.cycle_gate("classic_sr", "NIFTY", "tok", {}, [area] + others, now, fetch_bars=fetch,
                       fetch_volume=lambda *a: bars[["timestamp", "volume"]])
    assert asked == [5]                                                    # LTF lazy: area result लागेपर्यंत fetch नाही
    r = g.result(*area)
    assert asked == [5, 1] and r["entry"] and r["ltf_line"].startswith("1M CHoCH")
    g.result(*others[0])
    assert asked == [5, 1]                                                 # एका cycle मध्ये एकदाच
    g2 = LGB.cycle_gate("classic_sr", "NIFTY", "tok", {}, [area] + others, now, fetch_bars=lambda t, s, m: bars.copy() if m == 5 else None,
                        fetch_volume=lambda *a: bars[["timestamp", "volume"]])
    r2 = g2.result(*area)
    assert not r2["entry"] and r2["ltf_wait"] == LR.R_LTF_MISSING          # LTF नाही ⇒ fail-closed
    g3 = LGB.cycle_gate("dynamic_sr_instant", "NIFTY", "tok", {}, [area] + others, now,
                        fetch_bars=lambda t, s, m: bars.copy() if m == 5 else pytest.fail("Instant: 1M पुन्हा fetch नको"),
                        fetch_volume=lambda *a: bars[["timestamp", "volume"]])
    g3.use_ltf(m1, 1, now)                                                 # bot चे स्वतःचे 1-मिनिट candles
    assert g3.result(*area)["entry"]


def test_exits_never_wait_for_the_gate(monkeypatch):
    """Exit monitor (MCX) gate / LTF / confirm कधीच बोलावत नाही — ते तुटले तरी manage_open_trades चालतो."""
    from unittest.mock import patch

    import mcx_futures_trader as mft
    from decision3 import method as M
    from tests.test_mcx_futures_trader import _DEFAULT_SETTINGS, _fake_candles_df

    def boom(*a, **k):
        raise AssertionError("exit path ने gate बोलावू नये")
    for mod, name in ((LGB, "cycle_gate"), (LR, "evaluate"), (M, "confirm"), (M, "ltf_choch")):
        monkeypatch.setattr(mod, name, boom)
    settings = {**_DEFAULT_SETTINGS, "trailing_sl_enabled": True, "sl_target_mode": "PERCENT", "trailing_pct": 1.0}
    with patch.object(mft.cloud_db, "get_strategy_settings", return_value=settings), \
            patch.object(mft, "get_open_trade_contracts", return_value=["MCX_FO|OLD"]), \
            patch.object(mft, "fetch_mcx_candles", return_value=_fake_candles_df(last_close=6500.0)), \
            patch.object(mft, "manage_open_trades", return_value=[]) as manage:
        mft.monitor_symbol("fake_token", "CRUDEOIL")
    assert manage.called
