"""tests/test_opportunity_engine_pr4.py -- PR-4: trendline/flag/double geometry, D4 trendline 3rd touch, D5 break-retest, D9 flag/double,
positional mode (सूचना + backtest), Timeline.hist no-lookahead. कृत्रिम, network-free."""
import numpy as np
import pandas as pd
import pytest

from opportunity_engine import backtest as BT
from opportunity_engine import positional as POS
from opportunity_engine import sessions
from opportunity_engine.detectors import chart_pattern as CP
from opportunity_engine.detectors import patterns as P
from opportunity_engine.detectors import trendline as TL
from tests.test_opportunity_engine_backtest import CFG, DAY, bars, ctx_of, walk_1m, zone
from tests.test_opportunity_engine_pr2 import D6_ROWS, run

PAT = [0, 0.5, 1, 0.5, 0, -0.5, -1, -0.5]


def frame(closes, half=10.0, start="2025-01-01 09:15", freq="60min"):
    """closes -> 1H-सारखा df (high/low = close ± half, bar_end सह)."""
    t = pd.date_range(start, periods=len(closes), freq=freq)
    c = np.asarray(closes, float)
    return pd.DataFrame({"bar_start": t, "bar_end": t + pd.Timedelta(freq), "open": c, "high": c + half, "low": c - half, "close": c})


def rising(n=24, base=23990.0, slope=3.0, amp=40.0):
    return frame([base + slope * i + amp * PAT[i % 8] for i in range(n)])


def falling(n=24, base=24100.0, slope=3.0, amp=40.0):
    return frame([base - slope * i + amp * PAT[(i + 6) % 8] for i in range(n)])          # peaks 4, 12, 20


def hist_of(dfs):
    return lambda tf, n: (dfs[tf].iloc[-n:] if tf in dfs else None)


# ---- geometry ------------------------------------------------------------------------------------------------------------------------------
def test_find_trendline_support_and_resistance():
    df = rising()
    ln = P.find_trendline(df, 20.0, "support", 1, order=3, min_gap=5)
    assert ln is not None and (ln.a, ln.b_idx) == (6, 14) and ln.m == pytest.approx(3.0) and ln.touches == 2 and ln.after_b == 0
    assert ln.at(24) == pytest.approx(24012.0) and ln.between_ext == pytest.approx(24070.0)
    rs = P.find_trendline(falling(), 20.0, "resistance", -1, order=3, min_gap=5, min_touches=3)
    assert rs is not None and rs.touches == 3 and rs.m == pytest.approx(-3.0) and rs.at(24) == pytest.approx(24078.0)
    assert P.find_trendline(df, 4.0, "support", 1) is None                                  # slope 3 > 0.5 × 4
    broken = df.copy()
    broken.loc[18, "close"] = 23900.0                                                        # A नंतर line खाली close ⇒ line नाही
    assert P.find_trendline(broken, 20.0, "support", 1) is None
    assert P.find_trendline(falling(), 20.0, "resistance", -1, min_touches=4) is None


def flag_df():
    closes = [24000.0] * 20 + [24030.0, 24060.0, 24090.0, 24115.0] + [24104.0 - 2 * j for j in range(8)]
    df = frame(closes, half=5.0)
    df.loc[20:23, "high"] = df.loc[20:23, "close"] + 5
    df.loc[20:23, "low"] = df.loc[20:23, "close"] - 25
    df.loc[24:, "high"] = df.loc[24:, "close"] + 10
    df.loc[24:, "low"] = df.loc[24:, "close"] - 10
    return df


def double_df():
    pts = [(0, 24100), (10, 23900), (17, 24000), (24, 23902), (30, 23960)]
    closes = np.interp(np.arange(31), [p[0] for p in pts], [p[1] for p in pts])
    return frame(closes, half=5.0)


def test_find_flag_and_double():
    f = P.find_flag(flag_df(), 20.0, 1)
    assert f is not None and f.sign == 1 and f.pole_len > 0 and f.m <= 0 and f.flag_ext < f.at(32)
    assert P.find_flag(flag_df(), 20.0, -1) is None
    flat = frame([24000.0] * 30, half=5.0)
    assert P.find_flag(flat, 10.0, 1) is None
    d = P.find_double(double_df(), 10.0, 1)
    assert d is not None and (d.first, d.second) == (10, 24) and d.level == pytest.approx(23895.0) and d.neckline == pytest.approx(24005.0)
    assert P.find_double(double_df(), 80.0, 1) is None                                       # मधला peak < 1.5 × rr
    far = double_df()
    far.loc[24:, ["close", "low", "high"]] -= 150                                            # दुसरा low खूप खाली
    assert P.find_double(far, 10.0, 1) is None


# ---- D4 ------------------------------------------------------------------------------------------------------------------------------------
def test_d4_third_touch_long_with_sl_target_and_single_use():
    det, state = TL.TrendlineThirdTouch(CFG), {}
    df5 = bars(D6_ROWS, start="10:00")                                                       # touch low 24010 ≈ line 24012, hammer + trigger break
    c = run(det, df5, ctx_of(price=24058.0), state=state, hist=hist_of({"1h": rising()}))
    assert len(c) == 1
    c = c[0]
    assert c.setup_id == "D4" and c.direction == "LONG" and c.kind == "PULLBACK_END" and c.meta["touch_no"] == 3
    assert c.meta["line_value"] == pytest.approx(24012.0) and c.sl_ref == pytest.approx(24007.0) and c.targets_hint == [pytest.approx(24070.0)]
    assert c.zone["kind"] == "TRENDLINE" and not c.meta["trendline_overlap"]
    assert run(det, df5, ctx_of(price=24058.0), state=state, hist=hist_of({"1h": rising()})) == []


def test_d4_confluence_needs_touch_trend_and_history():
    dz = zone("DEMAND", 23995.0, 24015.0, tf="4h", grade="B")
    c = run(TL.TrendlineThirdTouch(CFG), bars(D6_ROWS, start="10:00"), ctx_of(levels=[dz], price=24058.0), hist=hist_of({"1h": rising()}))
    assert c[0].meta["trendline_overlap"] and c[0].zone["kind"] == "DEMAND"
    far = rising(base=23900.0)                                                                # line 23922 — touch नाही
    assert run(TL.TrendlineThirdTouch(CFG), bars(D6_ROWS, start="10:00"), ctx_of(), hist=hist_of({"1h": far})) == []
    down = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"})
    assert run(TL.TrendlineThirdTouch(CFG), bars(D6_ROWS, start="10:00"), down, hist=hist_of({"1h": rising()})) == []
    assert run(TL.TrendlineThirdTouch(CFG), bars(D6_ROWS, start="10:00"), ctx_of()) == []           # hist नाही
    long_line = rising(n=40)                                                                  # 4 touches आधीच ⇒ पाचवा ⇒ नाही
    assert run(TL.TrendlineThirdTouch(CFG), bars(D6_ROWS, start="10:00"), ctx_of(), hist=hist_of({"1h": long_line})) == []


# ---- D5 ------------------------------------------------------------------------------------------------------------------------------------
D5_PREV, D5_BREAK, D5_RETEST = (24060, 24070, 24055, 24065), (24065, 24092, 24063, 24090), (24082, 24095, 24075, 24093)


def d5_call(det, rows, state):
    df15 = bars(rows, start="10:00", freq=15)
    b = {"5m": df15, "15m": df15, "info": None, "state": state, "rr5": 10.0, "rr15": 20.0, "ev15": [], "hist": hist_of({"1h": falling()})}
    return det.detect(ctx_of(price=float(rows[-1][3])), b, None, df15["bar_end"].iloc[-1])


def test_d5_break_then_retest_entry():
    det, state = TL.TrendlineBreakRetest(CFG), {}
    assert d5_call(det, [D5_PREV, D5_BREAK], state) == [] and len(state["d5_pending"]) == 1          # break = फक्त नोंद
    c = d5_call(det, [D5_PREV, D5_BREAK, D5_RETEST], state)
    assert len(c) == 1
    c = c[0]
    assert c.setup_id == "D5" and c.direction == "LONG" and c.kind == "REVERSAL" and c.trigger_tf == "15m" and c.meta["touches"] == 3
    assert c.meta["line_value"] == pytest.approx(24078.0) and c.sl_ref == 24075.0 and c.entry == 24093.0 and c.meta["retest_bars"] == 1
    assert c.targets_hint == [pytest.approx(24114.0)] and state["d5_pending"] == []
    assert d5_call(det, [D5_PREV, D5_BREAK], state) == [] and state["d5_pending"] == []              # तीच line पुन्हा नाही


def test_d5_failed_break_and_weak_break_and_timeout():
    st = {}
    d5_call(TL.TrendlineBreakRetest(CFG), [D5_PREV, D5_BREAK], st)
    assert d5_call(TL.TrendlineBreakRetest(CFG), [D5_PREV, D5_BREAK, (24070, 24072, 24030, 24035)], st) == [] and st["d5_pending"] == []
    st2 = {}
    weak = (24076, 24090, 24068, 24080)                                                       # validation अपयशी (लहान candle)
    assert d5_call(TL.TrendlineBreakRetest(CFG), [D5_PREV, weak], st2) == [] and st2.get("d5_pending") == []
    st3 = {}
    d5_call(TL.TrendlineBreakRetest(CFG), [D5_PREV, D5_BREAK], st3)
    drift = [(24095, 24110, 24092, 24105)] * 11
    assert d5_call(TL.TrendlineBreakRetest(CFG), [D5_PREV, D5_BREAK] + drift + [D5_RETEST], st3) == [] and st3["d5_pending"] == []


# ---- D9 ------------------------------------------------------------------------------------------------------------------------------------
def d9_call(df1h, prev_close, close, state=None, ctx=None):
    rows = [(prev_close - 5, prev_close + 2, prev_close - 8, prev_close), (prev_close, close + 2, prev_close - 2, close)]
    df15 = bars(rows, start="10:00", freq=15)
    b = {"5m": df15, "15m": df15, "info": None, "state": state if state is not None else {}, "rr5": 10.0, "rr15": 20.0, "ev15": [],
         "hist": hist_of({"1h": df1h})}
    return CP.ChartPatternBreakout(CFG).detect(ctx or ctx_of(), b, None, df15["bar_end"].iloc[-1])


def test_d9_bull_flag_breakout():
    df = flag_df()
    f = P.find_flag(df, BT.ref_range_from_ranges((df["high"] - df["low"]).to_numpy(float), 20, 10), 1)
    L = f.at(len(df))
    state = {}
    c = [x for x in d9_call(df, L - 3, L + 15, state) if x.meta["pattern"] == "FLAG"]
    assert len(c) == 1 and c[0].direction == "LONG" and c[0].kind == "BREAKOUT" and c[0].trigger["level"] == pytest.approx(L)
    assert c[0].sl_ref == pytest.approx(f.flag_ext) and c[0].targets_hint[0] == pytest.approx(L + f.pole_len)
    assert [x for x in d9_call(df, L - 3, L + 15, state) if x.meta["pattern"] == "FLAG"] == []               # एकदाच
    assert [x for x in d9_call(df, L + 5, L + 15) if x.meta["pattern"] == "FLAG"] == []                    # आधीच बाहेर ⇒ ताजा break नाही
    down = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"})
    assert [x for x in d9_call(df, L - 3, L + 15, ctx=down) if x.meta["pattern"] == "FLAG"] == []         # trend विरुद्ध flag नाही


def test_d9_double_bottom_neckline_breakout():
    c = [x for x in d9_call(double_df(), 23995.0, 24015.0) if x.meta["pattern"] == "DOUBLE_BOTTOM"]
    assert len(c) == 1 and c[0].direction == "LONG" and c[0].sl_ref == pytest.approx(23895.0) and c[0].trigger["level"] == pytest.approx(24005.0)
    assert c[0].targets_hint[0] == pytest.approx(24005.0 + 110.0)
    dz = zone("DEMAND", 23880.0, 23910.0, tf="1d", grade="A")
    c2 = [x for x in d9_call(double_df(), 23995.0, 24015.0, ctx=ctx_of(levels=[dz])) if x.meta["pattern"] == "DOUBLE_BOTTOM"]
    assert c2[0].setup_quality == pytest.approx(c[0].setup_quality + 10.0) and c2[0].zone["kind"] == "DEMAND"


# ---- positional ----------------------------------------------------------------------------------------------------------------------------
def test_positional_bull_put_anchor_and_rounding():
    ctx = ctx_of(price=24100.0, extra={"1d": {"protected": 23500.0}, "4h": {"protected": 23800.0}})
    s = POS.suggest(ctx, 24100.0, CFG, "NIFTY", adr=200.0, step=50)
    assert s["strategy"] == "BULL_PUT" and s["put"]["short"] == 23750 and s["put"]["long"] == 23550 and s["call"] is None
    assert s["put"]["distance_adr"] == 1.75 and "4H protected" in s["put"]["anchor_reason"]
    dz = zone("DEMAND", 23950.0, 23980.0, tf="1h", freshness="FRESH")
    s2 = POS.suggest(ctx_of(levels=[dz], price=24100.0, extra={"4h": {"protected": 23800.0}}), 24100.0, CFG, "NIFTY", adr=200.0, step=50)
    assert s2["put"]["short"] == 23900 and "FRESH DEMAND" in s2["put"]["anchor_reason"]
    assert "PE" in POS.suggestion_text(s2)


def test_positional_bear_call_condor_weak_and_conflict():
    dn = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, extra={"4h": {"protected": 24420.0}})
    s = POS.suggest(dn, 24100.0, CFG, "BANKNIFTY", adr=400.0, step=100)
    assert s["strategy"] == "BEAR_CALL" and s["call"]["short"] == 24600 and s["call"]["long"] == 25000
    rg = ctx_of({"1d": "RANGE", "4h": "RANGE", "1h": "RANGE"}, extra={"1d": {"range_low": 23700.0, "range_high": 24500.0}})
    ic = POS.suggest(rg, 24100.0, CFG, "NIFTY", adr=200.0, step=50)
    assert ic["strategy"] == "IRON_CONDOR" and ic["put"]["short"] == 23650 and ic["call"]["short"] == 24550
    weak = POS.suggest(ctx_of({"1d": "UPTREND", "4h": "UPTREND_WEAK", "1h": "UPTREND"}), 24100.0, CFG, adr=200.0, step=50)
    assert weak["strategy"] is None and "WEAK" in weak["alert"] and "⚠️" in POS.suggestion_text(weak)
    mixed = POS.suggest(ctx_of({"1d": "UPTREND", "4h": "DOWNTREND", "1h": "UPTREND"}), 24100.0, CFG, adr=200.0, step=50)
    assert mixed["strategy"] is None and "मतभेद" in mixed["reasons"][0]
    none_anchor = POS.suggest(ctx_of(), 24100.0, CFG, adr=200.0, step=50)                    # protected/zone नाही
    assert none_anchor["strategy"] is None
    init = POS.suggest(ctx_of({"1d": "INIT", "4h": "UPTREND", "1h": "UPTREND"}), 24100.0, CFG, adr=200.0, step=50)
    assert init["strategy"] is None


def test_positional_backtest_and_summary_split():
    frames = sessions.build_frames(walk_1m(days=60, seed=6))
    tl = BT.prepare_timeline(frames, BT.BacktestConfig(variants=("V1",)))
    df = POS.backtest(tl, CFG)
    s = POS.summary(df)
    assert list(s.columns) == ["period", "strategy", "n", "win_pct", "touch_pct"]
    if len(df):
        assert set(df["strategy"]) <= {"BULL_PUT", "BEAR_CALL", "IRON_CONDOR"} and df["touch"].dtype == bool
        assert (pd.to_datetime(df["exit_date"]) > pd.to_datetime(df["date"])).all()
    fake = pd.DataFrame([{"date": pd.Timestamp("2020-01-01"), "strategy": "BULL_PUT", "win": True, "touch": False},
                         {"date": pd.Timestamp("2023-01-01"), "strategy": "BULL_PUT", "win": False, "touch": True}])
    sf = POS.summary(fake)
    assert list(sf["period"]) == ["IS 2015→2021", "OOS 2022→"] and list(sf["win_pct"]) == [100.0, 0.0] and list(sf["touch_pct"]) == [0.0, 100.0]


# ---- timeline hist / registry / replay ---------------------------------------------------------------------------------------------------
def test_timeline_hist_is_as_of_and_registry():
    frames = sessions.build_frames(walk_1m(days=30, seed=3))
    tl = BT.prepare_timeline(frames, BT.BacktestConfig(variants=("V1",)))
    day = tl.days[-1]
    t = day.be[20]
    h = tl.hist("1h", t, 7)
    assert len(h) == 7 and (h["bar_end"] <= t).all() and tl.hist("15m", t, 5) is None
    nxt = tl.htf["1h"][0]
    assert (nxt["bar_end"] > t).any() and h.index[-1] + 1 < len(nxt) and nxt["bar_end"].iloc[h.index[-1] + 1] > t
    assert {"D4", "D5", "D9"} <= set(BT.DETECTORS) and BT.BacktestConfig().detectors[3:5] == ("D4", "D5")


def test_full_replay_with_pr4_detectors_runs():
    frames = sessions.build_frames(walk_1m(days=45, seed=11))
    res = BT.run_backtest(frames, BT.BacktestConfig(variants=("V1",), detectors=("D4", "D5", "D9")))
    dec = res.results["V1"]["decisions"]
    if len(dec):
        assert set(dec["setup"]) <= {"D4", "D5", "D9"}


def test_strike_step_matches_cloud_db():
    import cloud_db
    for sym, step in cloud_db.STRIKE_STEP.items():
        assert POS.strike_step(sym) == step
