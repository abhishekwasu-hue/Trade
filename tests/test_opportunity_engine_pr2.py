"""tests/test_opportunity_engine_pr2.py -- PR-2: D6 HTF Zone Pullback, D10 Failed-breakout trap, futures-volume join/collector, नवीन analytics तक्ते. कृत्रिम, network-free."""
import numpy as np
import pandas as pd
import pytest

import collect_index_futures_volume as COL
import resolve_index_futures_instruments as RES
from opportunity_engine import backtest as BT
from opportunity_engine import sessions
from opportunity_engine import volume as VOL
from opportunity_engine.context import TFState
from opportunity_engine.detectors import range_box as RB
from opportunity_engine.detectors import zone_pullback as ZP
from opportunity_engine.detectors.gap import GapGo
from tests.test_opportunity_engine_backtest import CFG, DAY, bars, ctx_of, info_of, walk_1m, zone


def run(det, df5, ctx, df15=None, ev15=(), state=None, info=None, rr5=10.0, rr15=20.0, **extra):
    b = {"5m": df5, "15m": df15 if df15 is not None else df5.iloc[0:0], "info": info or info_of(), "state": state if state is not None else {},
         "rr5": rr5, "rr15": rr15, "ev15": list(ev15), **extra}
    return det.detect(ctx, b, None, df5["bar_end"].iloc[-1])


# ---- D6 -----------------------------------------------------------------------------------------------------------------------------------
def test_is_shift_long_and_short():
    assert ZP.is_shift({"type": "CHOCH", "to_state": "DOWNTREND_WEAK"}, 1) and ZP.is_shift({"type": "RECOVERY", "to_state": "UPTREND"}, 1)
    assert not ZP.is_shift({"type": "CHOCH", "to_state": "UPTREND_WEAK"}, 1) and ZP.is_shift({"type": "CHOCH", "to_state": "UPTREND_WEAK"}, -1)
    assert ZP.is_shift({"type": "RANGE_EXIT_DOWN", "to_state": "DOWNTREND"}, -1) and not ZP.is_shift({"type": "BOS", "to_state": "UPTREND"}, 1)


def test_d6_zones_fresh_demand_flip_and_retracement():
    dem = zone("DEMAND", 24000.0, 24030.0, tf="1h", freshness="FRESH")
    old = zone("DEMAND", 23900.0, 23920.0, tf="4h", freshness="TESTED_2+")                     # TESTED_2+ => नाही
    flip = dict(zone("SUPPLY", 24040.0, 24060.0, tf="4h"), status="BROKEN")
    daily = zone("DEMAND", 23950.0, 23970.0, tf="1d")                                            # Daily D6 zone TF नाही
    above = zone("DEMAND", 24200.0, 24220.0, tf="1h")                                            # किंमतीच्या वर => नाही
    ctx = ctx_of(levels=[dem, old, flip, daily, above], price=24100.0, extra={"4h": {"protected": 23800.0, "last_sh": 24200.0}})
    zs = ZP.candidate_zones(ctx, 1, CFG)
    types = {z["type"] for z in zs}
    assert types == {"DEMAND", "FLIP", "RETRACE"} and len(zs) == 3
    r = next(z for z in zs if z["type"] == "RETRACE")
    assert r["low"] == pytest.approx(24200 - 0.62 * 400) and r["high"] == pytest.approx(24200 - 0.5 * 400)
    assert zs[0]["type"] == "FLIP"                                                              # किंमतीच्या सर्वात जवळचा आधी
    short = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, levels=[zone("SUPPLY", 24150.0, 24170.0, tf="1h")], price=24100.0,
                   extra={"4h": {"protected": 24400.0, "last_sl": 24000.0}})
    zs2 = ZP.candidate_zones(short, -1, CFG)
    assert {z["type"] for z in zs2} == {"SUPPLY", "RETRACE"}
    rr = next(z for z in zs2 if z["type"] == "RETRACE")
    assert rr["low"] == pytest.approx(24000 + 0.5 * 400) and rr["high"] == pytest.approx(24000 + 0.62 * 400)


# pullback: demand 24000–24030 ला स्पर्श (low 24010), मग hammer आणि trigger-high break
D6_ROWS = [(24100, 24105, 24080, 24085), (24085, 24090, 24050, 24055), (24055, 24060, 24030, 24035), (24035, 24040, 24015, 24020),
           (24020, 24039.5, 24010, 24038), (24038, 24060, 24036, 24058)]


def d6_ctx(**kw):
    return ctx_of(levels=[zone("DEMAND", 24000.0, 24030.0, tf="1h", freshness="FRESH", grade="B")], price=24058.0,
                  extra={"4h": {"protected": 23500.0, "last_sh": 24400.0}, "1h": {"last_sh": 24150.0}}, **kw)


def test_d6_candle_trigger_long_with_sl_below_zone_hints_and_single_use():
    det, state = ZP.ZonePullback(CFG), {}
    df5 = bars(D6_ROWS, start="10:00")
    c = run(det, df5, d6_ctx(), state=state)
    assert len(c) == 1
    c = c[0]
    assert c.setup_id == "D6" and c.direction == "LONG" and c.kind == "PULLBACK_END" and c.entry == 24058.0
    assert c.sl_ref == pytest.approx(24000.0) and c.meta["trigger_type"] == "CANDLE_5M" and c.meta["zone_type"] == "DEMAND"
    assert sorted(c.targets_hint) == [24150.0, 24400.0] and c.zone["kind"] == "DEMAND" and c.trigger["prev_high"] == 24039.5
    assert run(det, df5, d6_ctx(), state=state) == []                                            # एक zone दिवसातून एकदाच


def test_d6_needs_zone_held_trigger_and_window_and_trend():
    det = ZP.ZonePullback(CFG)
    broke = [list(r) for r in D6_ROWS]
    broke[3] = (24035, 24040, 23985, 23990)                                                       # close zone low खाली => zone टिकला नाही
    assert run(det, bars(broke, start="10:00"), d6_ctx()) == []
    no_break = D6_ROWS[:-1] + [(24038, 24039, 24030, 24035)]                                       # trigger high तुटला नाही
    assert run(det, bars(no_break, start="10:00"), d6_ctx()) == []
    assert run(det, bars(D6_ROWS, start="09:00"), d6_ctx()) == []                                   # 09:45 आधी
    rng = ctx_of({"1d": "RANGE", "4h": "RANGE", "1h": "RANGE"}, levels=[zone("DEMAND", 24000.0, 24030.0, tf="1h")], price=24058.0)
    assert run(det, bars(D6_ROWS, start="10:00"), rng) == []                                        # primary RANGE => D6 नाही


def test_d6_choch_15m_trigger_uses_the_15m_bar():
    det = ZP.ZonePullback(CFG)
    rows = D6_ROWS[:-1] + [(24038, 24045, 24036, 24039)]                                           # 5M वर trigger-high break नाही
    df5 = bars(rows, start="10:00")
    now = df5["bar_end"].iloc[-1]
    df15 = bars([(24100, 24105, 24030, 24035), (24035, 24045, 24010, 24040)], start="10:00", freq=15)
    assert df15["bar_end"].iloc[-1] == now
    ev = [{"time": now, "type": "CHOCH", "to_state": "DOWNTREND_WEAK", "price": 24038.0}]
    c = run(det, df5, d6_ctx(), df15=df15, ev15=ev)
    assert len(c) == 1 and c[0].meta["trigger_type"] == "CHOCH_15M" and c[0].trigger_tf == "15m"
    assert c[0].trigger["low"] == 24010.0 and c[0].trigger["prev_high"] == 24105.0 and c[0].trigger["ref_range"] == 20.0
    old_ev = [{"time": now - pd.Timedelta(minutes=15), "type": "CHOCH", "to_state": "DOWNTREND_WEAK"}]
    assert run(det, df5, d6_ctx(), df15=df15, ev15=old_ev) == []                                  # event याच bar चा हवा


# ---- D10 ----------------------------------------------------------------------------------------------------------------------------------
def arrays(rows):
    a = np.array(rows, dtype=float)
    return a[:, 2], a[:, 1], a[:, 3]


def test_find_trap_wick_and_close_below_reclaim_and_limits():
    lvl = {"price": 100.0, "since": 0}
    lo, hi, cl = arrays([(105, 106, 101, 104), (104, 105, 99, 102)])                               # wick sweep, त्याच bar मध्ये परत वर
    assert RB.find_trap(lo, hi, cl, lvl, 1, 2) == 1
    lo, hi, cl = arrays([(105, 106, 101, 104), (104, 105, 98, 99), (99, 101, 97, 99.5), (99.5, 103, 99, 102)])     # 2 bars खाली close, 3रा परत वर
    assert RB.find_trap(lo, hi, cl, lvl, 1, 2) == 1
    lo, hi, cl = arrays([(105, 106, 101, 104), (104, 105, 98, 99), (99, 100, 97, 99), (99, 100, 96, 99.5), (99.5, 103, 99, 102)])
    assert RB.find_trap(lo, hi, cl, lvl, 1, 2) is None                                             # 3 bars खाली => trap नाही
    lo, hi, cl = arrays([(105, 106, 99, 104), (104, 105, 101, 103), (103, 104, 98, 102)])            # level आधीच (bar 0) तुटलेला
    assert RB.find_trap(lo, hi, cl, lvl, 1, 2) is None
    lo, hi, cl = arrays([(95, 99, 94, 96), (96, 102, 95, 101), (101, 102, 99.5, 98)])                # short: bar 1 वर close (sweep), bar 2 परत खाली
    assert RB.find_trap(lo, hi, cl, lvl, -1, 2) == 1


TRAP_ROWS = [(24100, 24110, 24095, 24105), (24105, 24108, 24090, 24095), (24095, 24100, 24070, 24075), (24075, 24090, 24072, 24088),
             (24088, 24092, 24080, 24086), (24086, 24100, 24085, 24098), (24098, 24102, 24060, 24064), (24064, 24085, 24062, 24083)]


def test_d10_long_trap_below_5m_swing_low_with_sweep_sl_and_targets():
    det, state = RB.FailedBreakoutTrap(CFG), {}
    df5 = bars(TRAP_ROWS, start="10:00")                                                          # swing low 24070 (bar 2, bar 4 ला confirm), bar 6 close खाली, bar 7 परत वर
    ctx = ctx_of(price=24083.0)
    info = info_of(pdl=23000.0)
    c = run(det, df5, ctx, state=state, info=info)
    assert len(c) == 1
    c = c[0]
    assert c.setup_id == "D10" and c.direction == "LONG" and c.kind == "REVERSAL" and c.meta["level_type"] == "SWING_5M"
    assert c.meta["swept_level"] == 24070.0 and c.meta["sweep_bars"] == 1 and c.sl_ref == 24060.0 and c.entry == 24083.0
    assert 24110.0 in c.targets_hint
    assert run(det, df5, ctx, state=state, info=info) == []                                       # एक level एकदाच


def test_d10_prefers_htf_zone_respects_trend_and_range_and_window():
    det = RB.FailedBreakoutTrap(CFG)
    df5 = bars(TRAP_ROWS, start="10:00")
    z = zone("DEMAND", 24068.0, 24090.0, tf="4h", grade="A")
    c = run(det, df5, ctx_of(levels=[z], price=24083.0), info=info_of(pdl=23000.0))
    assert c[0].meta["level_type"] == "ZONE" and c[0].meta["swept_level"] == 24068.0 and c[0].zone["kind"] == "DEMAND"
    down = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, price=24083.0)
    assert run(det, df5, down, info=info_of(pdl=23000.0)) == []                                    # downtrend मध्ये long trap नाही
    rng = ctx_of({"1d": "RANGE", "4h": "RANGE", "1h": "RANGE"}, price=24083.0)
    assert [x.direction for x in run(det, df5, rng, info=info_of(pdl=23000.0))] == ["LONG"]        # RANGE: दोन्ही दिशा तपासल्या
    init = ctx_of({"1d": "INIT", "4h": "INIT", "1h": "INIT"}, price=24083.0)
    assert run(det, df5, init, info=info_of(pdl=23000.0)) == []
    assert run(det, bars(TRAP_ROWS, start="14:30"), ctx_of(price=24083.0), info=info_of(pdl=23000.0)) == []      # 14:45 नंतर


# ---- volume ---------------------------------------------------------------------------------------------------------------------------------
def test_candles_to_df_tz_and_merge_store_keeps_first():
    c = [["2025-01-08T09:20:00+05:30", 1, 2, 0.5, 1.5, 100, 7], ["2025-01-08T09:15:00+05:30", 1, 2, 0.5, 1.5, 50, 7]]
    df = VOL.candles_to_df(c, contract="NIFTY FUT 30 JAN 25")
    assert list(df["timestamp"]) == [pd.Timestamp("2025-01-08 09:15"), pd.Timestamp("2025-01-08 09:20")] and df["contract"].iloc[0].startswith("NIFTY")
    newer = VOL.candles_to_df([["2025-01-08T09:20:00+05:30", 1, 2, 0.5, 1.5, 999, 7], ["2025-01-08T09:25:00+05:30", 1, 2, 0.5, 1.5, 70, 7]])
    m = VOL.merge_store(df, newer)
    assert len(m) == 3 and m.set_index("timestamp").loc["2025-01-08 09:20", "volume"] == 100
    assert VOL.candles_to_df([]).empty and len(VOL.merge_store(None, newer)) == 2


def test_attach_futures_volume_5m_and_15m_and_coverage_and_without():
    one = walk_1m(days=3, seed=2, start="2025-01-06")
    frames = sessions.build_frames(one)
    f5 = frames["5m"]
    fut = pd.DataFrame({"timestamp": f5["bar_start"].iloc[:6], "volume": [10.0, 20, 30, 40, 50, 60]})
    out, cov = VOL.attach_futures_volume(frames, fut)
    assert cov["with_volume"] == 6 and cov["from"] == f5["bar_start"].iloc[0]
    assert list(out["5m"]["volume"].iloc[:7]) == [10, 20, 30, 40, 50, 60, 0]
    assert list(out["15m"]["volume"].iloc[:3]) == [60, 150, 0] and frames["5m"]["volume"].sum() == 0          # मूळ frames बदलले नाहीत
    nv = VOL.without_volume(out)
    assert nv["5m"]["volume"].sum() == 0 and out["5m"]["volume"].sum() == 210
    empty, cov0 = VOL.attach_futures_volume(frames, pd.DataFrame())
    assert cov0["with_volume"] == 0


def test_timeline_volume_median_and_d1_passes_volume_to_validation():
    frames = sessions.build_frames(walk_1m(days=40, seed=4))
    fut = pd.DataFrame({"timestamp": frames["5m"]["bar_start"], "volume": np.arange(1, len(frames["5m"]) + 1, dtype=float)})
    frames, _ = VOL.attach_futures_volume(frames, fut)
    tl = BT.prepare_timeline(frames, BT.BacktestConfig(levels_every_day=False, variants=("V1",)))
    v, med = tl.volume(100)
    assert v == 101.0 and med == pytest.approx(np.median(np.arange(81, 101)))
    tl.v5 = np.zeros_like(tl.v5)
    assert tl.volume(100) == (None, None)
    info = info_of()
    info.gap_type, info.gap_dir = "BREAKAWAY", 1
    df5 = bars([(24100, 24130, 24095, 24120), (24120, 24140, 24110, 24135), (24135, 24150, 24125, 24140), (24140, 24165, 24138, 24160)])
    c = run(GapGo(CFG), df5, ctx_of(), info=info, vol5=500.0, vol_med5=200.0)
    assert c[0].trigger["volume"] == 500.0 and c[0].trigger["volume_median"] == 200.0


def test_prepare_timeline_attaches_15m_shift_events_per_day():
    frames = sessions.build_frames(walk_1m(days=60, seed=7))
    tl = BT.prepare_timeline(frames, BT.BacktestConfig(levels_every_day=False, variants=("V1",)))
    evs = [e for d in tl.days for e in d.ev15]
    assert evs and all(e["type"] in BT.SHIFT_EVENTS for e in evs)
    for d in tl.days:
        assert all(pd.Timestamp(e["time"]).normalize() == d.date for e in d.ev15)


# ---- collector / resolver --------------------------------------------------------------------------------------------------------------------
def test_collector_stores_futures_and_index_and_is_idempotent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(COL.V, "resolve_front_future", lambda tok, s, today: ({"trading_symbol": f"{s} FUT 30 OCT 26", "instrument_key": f"NSE_FO|{s}",
                                                                              "expiry": "2026-10-30", "lot_size": 75}, None))
    monkeypatch.setattr(COL.V, "resolve_futures_chain", lambda tok, s, today, n=2: ([], None))

    def fetch(tok, key, interval, start, end, expired=False):
        calls.append(key)
        vol = 100 if key.startswith("NSE_FO") else 0
        return {"status": 200, "candles": [["2026-10-01T09:15:00+05:30", 1, 2, 0.5, 1.5, vol, 9], ["2026-10-01T09:20:00+05:30", 1, 2, 0.5, 1.5, vol, 9]], "error": None}
    monkeypatch.setattr(COL.V, "fetch_candles_window", fetch)
    import datetime
    r = COL.collect_symbol("tok", "NIFTY", 5, datetime.date(2026, 10, 2), data_dir=str(tmp_path), log=lambda s: None)
    assert r["futures_added"] == 2 and r["index_added"] == 2 and r["volume_nonzero_pct"] == 100.0 and "error" not in r
    r2 = COL.collect_symbol("tok", "NIFTY", 5, datetime.date(2026, 10, 2), data_dir=str(tmp_path), log=lambda s: None)
    assert r2["futures_added"] == 0 and r2["futures_total"] == 2
    stored = pd.read_parquet(COL.store_path("futures", "NIFTY", str(tmp_path)))
    assert stored["contract"].iloc[0] == "NIFTY FUT 30 OCT 26" and stored["volume"].sum() == 200
    monkeypatch.setattr(COL.V, "resolve_front_future", lambda tok, s, today: (None, "HTTP 401"))
    assert "error" in COL.collect_symbol("tok", "NIFTY", 5, datetime.date(2026, 10, 2), data_dir=str(tmp_path), log=lambda s: None)


def test_collector_also_stores_next_contract_keyed_by_contract(tmp_path, monkeypatch):
    """Chart Reader K10.3: volume roll साठी पुढचा contract सुद्धा `_all` store मध्ये (timestamp + contract); front file बदलत नाही."""
    import datetime
    front = {"trading_symbol": "NIFTY FUT 27 OCT 26", "instrument_key": "NSE_FO|A", "expiry": "2026-10-27", "lot_size": 65}
    nxt = {"trading_symbol": "NIFTY FUT 24 NOV 26", "instrument_key": "NSE_FO|B", "expiry": "2026-11-24", "lot_size": 65}
    monkeypatch.setattr(COL.V, "resolve_front_future", lambda tok, s, today: (front, None))
    monkeypatch.setattr(COL.V, "resolve_futures_chain", lambda tok, s, today, n=2: ([front, nxt], None))

    def fetch(tok, key, interval, start, end, expired=False):
        vol = {"NSE_FO|A": 100, "NSE_FO|B": 40}.get(key, 0)
        return {"status": 200, "candles": [["2026-10-01T09:15:00+05:30", 1, 2, 0.5, 1.5, vol, 9]], "error": None}
    monkeypatch.setattr(COL.V, "fetch_candles_window", fetch)
    r = COL.collect_symbol("tok", "NIFTY", 5, datetime.date(2026, 10, 2), data_dir=str(tmp_path), log=lambda s: None)
    assert r["next_contract"] == "NIFTY FUT 24 NOV 26" and r["all_total"] == 2
    allf = pd.read_parquet(tmp_path / "oe_futures_5min_NIFTY_all.parquet")
    assert sorted(allf["contract"]) == ["NIFTY FUT 24 NOV 26", "NIFTY FUT 27 OCT 26"]
    assert pd.read_parquet(COL.store_path("futures", "NIFTY", str(tmp_path)))["volume"].sum() == 100
    r2 = COL.collect_symbol("tok", "NIFTY", 5, datetime.date(2026, 10, 2), data_dir=str(tmp_path), log=lambda s: None)
    assert r2["all_added"] == 0


def test_resolver_returns_front_future_per_symbol(monkeypatch):
    monkeypatch.setattr(RES.V, "resolve_front_future", lambda tok, s, today: ({"trading_symbol": f"{s} FUT", "instrument_key": "k", "expiry": "x", "lot_size": 1}, None))
    out = RES.resolve_index_futures_instruments("tok", today=pd.Timestamp("2026-10-01").date())
    assert set(out) == {"NIFTY", "BANKNIFTY"} and out["NIFTY"][0]["trading_symbol"] == "NIFTY FUT"
    monkeypatch.setattr(RES.cloud_db, "get_effective_upstox_token", lambda t: None)
    assert RES.main([]) == 1


# ---- analytics ---------------------------------------------------------------------------------------------------------------------------------
def tr_rows(spec):
    rows = []
    for d, setup, r, bias, gate in spec:
        e = pd.Timestamp(d) + pd.Timedelta(hours=10, minutes=5)
        rows.append({"date": pd.Timestamp(d), "entry_time": e, "exit_time": e + pd.Timedelta(hours=1), "setup": setup, "r": r, "size_factor": 1.0, "r_weighted": r,
                     "bias": bias, "gate_codes": gate, "exit_reason": "T2" if r > 0 else "SL", "score": 70.0, "direction": "LONG"})
    return pd.DataFrame(rows)


def test_variant_tables_setup_tod_and_wait_pullback():
    trades = tr_rows([("2018-01-02", "D6", 1.5, "LONG_ONLY_WAIT_PULLBACK_END", ""), ("2023-01-02", "D6", -1.0, "LONG_ONLY", ""),
                      ("2019-03-04", "D10", 0.5, "LONG_ONLY_WAIT_PULLBACK_END", "")])
    virtual = tr_rows([("2018-02-02", "D1", -1.0, "LONG_ONLY_WAIT_PULLBACK_END", "HTF_WAIT_PULLBACK"), ("2023-02-02", "D6", 2.0, "LONG_ONLY_WAIT_PULLBACK_END", "NO_ROOM")])
    dec = pd.DataFrame([{"date": pd.Timestamp("2018-01-02"), "setup": "D6", "status": "TAKEN", "bias": "LONG_ONLY_WAIT_PULLBACK_END"},
                        {"date": pd.Timestamp("2018-01-02"), "setup": "D6", "status": "REJECTED_SCORE", "bias": "LONG_ONLY_WAIT_PULLBACK_END"},
                        {"date": pd.Timestamp("2023-02-02"), "setup": "D6", "status": "REJECTED_GATE", "bias": "LONG_ONLY_WAIT_PULLBACK_END"},
                        {"date": pd.Timestamp("2023-01-02"), "setup": "D6", "status": "TAKEN", "bias": "LONG_ONLY"}])
    res = {"V1": {"trades": trades, "virtual": virtual, "decisions": dec}, "V2": {"trades": trades.iloc[:1], "virtual": virtual.iloc[:0], "decisions": dec}}
    vio = BT.variants_is_oos(res)
    assert list(vio["period"]) == list(BT.PERIODS) * 2 and vio.iloc[0]["trades"] == 2 and vio.iloc[1]["trades"] == 1
    yw = BT.variants_yearwise(res).set_index("वर्ष")
    assert yw.loc[2018, "V1"] == "+1.500 (1)" and yw.loc[2023, "V2"] == "—" and yw.loc[2023, "period"] == BT.PERIODS[1]
    st = BT.breakdown_split(trades, ["setup", "tod"], col="r")
    assert {"period", "setup", "tod"} <= set(st.columns) and len(st) == 3 and set(st["tod"]) == {"10:00"}
    w = BT.wait_pullback_table(res["V1"]).set_index(["period", "setup"])
    IS, OOS = BT.PERIODS
    assert w.loc[(IS, "D6"), "candidates"] == 2 and w.loc[(IS, "D6"), "taken"] == 1 and w.loc[(IS, "D6"), "score_reject"] == 1
    assert w.loc[(IS, "D6"), "घेतलेले_trades"] == 1 and w.loc[(IS, "D6"), "घेतलेले_expectancy_r"] == 1.5
    assert w.loc[(OOS, "D6"), "gate_reject"] == 1 and w.loc[(OOS, "D6"), "नाकारलेले_virtual_trades"] == 1 and w.loc[(OOS, "D6"), "घेतलेले_trades"] == 0
    wb = BT.wait_pullback_breakouts(res["V1"]).set_index(["setup", "period"])
    assert wb.loc[("D1", IS), "trades"] == 1 and wb.loc[("D1", OOS), "trades"] == 0
    avc = BT.aligned_vs_counter_split(trades, virtual)
    assert set(avc["period"]) == set(BT.PERIODS) and avc.columns[0] == "period"
    assert BT.wait_pullback_table({"trades": trades, "virtual": virtual, "decisions": pd.DataFrame()}).empty


def test_default_detectors_include_d6_d10_and_registry():
    assert {"D6", "D10"} <= set(BT.BacktestConfig().detectors)
    ds = BT.make_detectors(("D6", "D10", "D99"), CFG)
    assert [d.setup_id for d in ds] == ["D6", "D10"]


def test_full_replay_with_d6_d10_runs_and_tables_exist():
    frames = sessions.build_frames(walk_1m(days=50, seed=9))
    res = BT.run_backtest(frames, BT.BacktestConfig(variants=("V1",)))
    t = res.tables("V1")
    assert {"by_setup_tod", "wait_pullback", "wait_pullback_breakouts"} <= set(t)
    vt = res.variant_tables()
    assert set(vt) == {"variants_is_oos", "variants_yearwise"}
    dec = res.results["V1"]["decisions"]
    if len(dec):
        assert "setup_detail" in dec.columns
