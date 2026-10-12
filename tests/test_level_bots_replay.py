"""tests/test_level_bots_replay.py — L6 replay (touch वि. confirmation): exits, position नियम, metrics, gate निकाल गट, n < 30, holdout पहारा,
एकच Daily fold, legacy = bot चीच functions (कृत्रिम data, network-free)."""
import dataclasses

import numpy as np
import pandas as pd
import pytest

import level_bots_replay as RP
from bots_common import level_reaction as LR
from elliott import data_policy as DP

BULL, BEAR = LR.BULL, LR.BEAR


@pytest.fixture(scope="module")
def specs():
    return RP.bot_specs()


def day_bars(day="2021-06-01", closes=None, n=375, start="09:15", spread=1.0):
    """एका दिवसाचे 1-मिनिट bars (timestamp, end, ohlc)."""
    d = pd.Timestamp(day)
    closes = list(closes) if closes is not None else [100.0] * n
    rows = []
    for k, c in enumerate(closes):
        t = d + pd.Timedelta(minutes=RP._hm(start) + k)
        o = closes[k - 1] if k else c
        rows.append({"timestamp": t, "end": t + pd.Timedelta(minutes=1), "open": o, "high": max(o, c) + spread, "low": min(o, c) - spread, "close": c})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ metrics
def test_metrics_drawdown_profit_factor_win_rate():
    m = RP.metrics([10, -5, -7, 20, -3])
    assert m["n"] == 5 and m["win_rate"] == pytest.approx(0.4) and m["expectancy"] == pytest.approx(3.0) and m["total"] == pytest.approx(15)
    assert m["max_dd"] == pytest.approx(12.0)                                 # शिखर 10 ⇒ तळ −2
    assert m["profit_factor"] == pytest.approx(30 / 15)
    assert RP.metrics([-4, 2])["max_dd"] == pytest.approx(4.0)                # सुरुवातीपासून (0) तोटा ⇒ drawdown
    assert RP.metrics([3, 4])["profit_factor"] == float("inf") and RP.metrics([3, 4])["max_dd"] == 0.0
    e = RP.metrics([])
    assert e["n"] == 0 and e["expectancy"] is None and e["profit_factor"] is None


# ------------------------------------------------------------------------------------------------ exits (आरसा: long / short)
@pytest.mark.parametrize("side,sl,tg,bar,why,px", [
    (BULL, 99.0, 103.0, (100, 104, 98, 101), "SL", 99.0),                     # एकाच bar मध्ये दोन्ही ⇒ SL आधी
    (BEAR, 101.0, 97.0, (100, 102, 96, 99), "SL", 101.0),
    (BULL, 99.0, 103.0, (101, 103.5, 100, 103), "TARGET", 103.0),
    (BEAR, 101.0, 97.0, (99, 100, 96.5, 97), "TARGET", 97.0),
    (BULL, 99.0, 103.0, (97, 98, 96, 97.5), "SL", 97.0),                      # gap SL पलीकडे ⇒ open
    (BEAR, 101.0, 97.0, (103, 104, 102, 102.5), "SL", 103.0),
])
def test_exit_on_bar_mirror(side, sl, tg, bar, why, px):
    pos = {"direction": side, "sl": sl, "target": tg}
    assert RP.exit_on_bar(pos, *bar, eod_hit=False) == (why, px)


def test_exit_eod_and_none():
    pos = {"direction": BULL, "sl": 90.0, "target": 110.0}
    assert RP.exit_on_bar(pos, 100, 101, 99, 100.5, eod_hit=False) == (None, None)
    assert RP.exit_on_bar(pos, 100, 101, 99, 100.5, eod_hit=True) == ("EOD", 100.5)


def test_legacy_stops_pct_and_points_mirror(specs):
    sl, tg = RP.legacy_stops(specs["instant"], 20000.0, BULL)
    assert sl == pytest.approx(20000 - 20000 * specs["instant"].sl[1] / 100) and tg == pytest.approx(20000 + 20000 * specs["instant"].target[1] / 100)
    sl2, tg2 = RP.legacy_stops(specs["instant"], 20000.0, BEAR)
    assert sl2 - 20000 == pytest.approx(20000 - sl) and 20000 - tg2 == pytest.approx(tg - 20000)
    m = specs["mcx"]
    assert m.sl[0] == "pts" and RP.legacy_stops(m, 1000.0, BULL) == (1000 - m.sl[1], 1000 + m.target[1])


# ------------------------------------------------------------------------------------------------ position नियम
def _cand(t, lv, side, entry, sl, tg, order=0):
    return {"time": pd.Timestamp(t), "order": order, "level": lv, "direction": side, "entry": entry, "sl": sl, "target": tg}


def test_take_trades_one_position_hits_cooldown_and_costs(specs):
    sp = dataclasses.replace(specs["instant"], max_hits=1, level_sl_cooldown=15, symbol_sl_cooldown=0, level_trade_gap=0, last_entry="14:45", eod="15:00")
    closes = [100.0] * 10 + [98.0] * 10 + [100.0] * 355                      # 09:25 ला खाली ⇒ long SL
    b = day_bars(closes=closes, spread=0.0)
    d = "2021-06-01 "
    cands = [_cand(d + "09:20", 100.0, BULL, 100.0, 99.0, 105.0),
             _cand(d + "09:21", 100.0, BULL, 100.0, 99.0, 105.0, 1),           # position उघडी ⇒ नाही
             _cand(d + "09:35", 100.0, BULL, 100.0, 99.0, 105.0),             # (level, role) max hits 1 ⇒ नाही
             _cand(d + "09:36", 100.0, BEAR, 100.0, 101.0, 95.0),             # त्याच level वर SL नंतर 15 मिनिटं ⇒ नाही
             _cand(d + "09:41", 100.0, BEAR, 100.0, 101.0, 95.0),             # cooldown संपला ⇒ हो (EOD)
             _cand(d + "14:50", 120.0, BULL, 100.0, 99.0, 105.0)]             # 14:45 नंतर ⇒ नाही
    out = RP.take_trades(cands, b, sp, "NIFTY", cost=2.0)
    assert [(str(t["time"])[11:16], t["direction"], t["exit_reason"]) for t in out] == [("09:20", BULL, "SL"), ("09:41", BEAR, "EOD")]
    assert out[0]["gross_pts"] == pytest.approx(-1.0) and out[0]["net_pts"] == pytest.approx(-3.0) and out[0]["cost_pts"] == 2.0
    assert str(out[1]["exit_time"])[11:16] == "15:00"


def test_take_trades_symbol_cooldown_and_level_gap(specs):
    sp = dataclasses.replace(specs["srv2"], max_hits=5, level_sl_cooldown=0, symbol_sl_cooldown=30, level_trade_gap=0)
    closes = [100.0] * 10 + [98.0] * 10 + [100.0] * 355
    b = day_bars(closes=closes, spread=0.0)
    d = "2021-06-01 "
    cands = [_cand(d + "09:20", 100.0, BULL, 100.0, 99.0, 105.0), _cand(d + "09:40", 200.0, BULL, 100.0, 99.0, 105.0),
             _cand(d + "09:56", 300.0, BULL, 100.0, 90.0, 105.0)]
    assert [str(t["time"])[11:16] for t in RP.take_trades(cands, b, sp, "NIFTY", cost=0.0)] == ["09:20", "09:56"]   # SL 09:25 ⇒ 09:55 पर्यंत नाही
    sp2 = dataclasses.replace(specs["classic"], max_hits=5, level_sl_cooldown=0, symbol_sl_cooldown=0, level_trade_gap=30)
    c2 = [_cand(d + "09:30", 100.0, BULL, 100.0, 90.0, 100.5), _cand(d + "09:45", 100.0, BULL, 100.0, 90.0, 100.5),
          _cand(d + "10:01", 100.0, BULL, 100.0, 90.0, 100.5)]
    assert [str(t["time"])[11:16] for t in RP.take_trades(c2, day_bars(spread=1.0), sp2, "NIFTY", cost=0.0)] == ["09:30", "10:01"]


# ------------------------------------------------------------------------------------------------ gate निकाल (rejection grouping)
UP = {"ok": True, "trend": "UP", "sides": {BULL}}
DOWN = {"ok": True, "trend": "DOWN", "sides": {BEAR}}
AREA = (99.0, 101.0)


def _bars(closes, lows, highs):
    C = np.asarray(closes, float)
    return C.copy(), C, np.asarray(highs, float), np.asarray(lows, float)


def _visits(mirror=False):
    """bars: 0 वर (105) ⇒ 1 ला arrival (BULL), 1–3 area मध्ये, 4 बाहेर; 5 खाली (97) ⇒ 6 ला arrival (BEAR), 7 मध्ये, 8 बाहेर.
    mirror ⇒ किंमती 200 − x (बाजू उलट)."""
    cl = [105, 100, 100, 100, 104, 97, 100, 100, 96]
    lo = [104, 99.5, 99.5, 99.5, 102, 96, 99.5, 99.5, 95]
    hi = [106, 100.5, 100.5, 100.5, 105, 98, 100.5, 100.5, 97]
    if mirror:
        cl, lo, hi = [200 - x for x in cl], [200 - x for x in hi], [200 - x for x in lo]
    return _bars(cl, lo, hi)


def test_gate_visits_side_and_extent_mirror():
    ev = [(1, LR.ARMED, "price arrived"), (2, LR.ARMED, LR.R_ABSORPTION), (3, LR.DISARMED, LR.R_TIMEOUT), (6, LR.DISARMED, LR.R_AGAINST)]
    for mirror, (s1, s2) in ((False, (BULL, BEAR)), (True, (BEAR, BULL))):
        O, C, H, L = _visits(mirror)
        v = RP.gate_visits(ev, O, C, H, L, AREA, 9)
        assert [(x["start"], x["end"], x["side"]) for x in v] == [(1, 3, s1), (6, 7, s2)]
        assert v[0]["terminal"] == (3, LR.DISARMED, LR.R_TIMEOUT) and v[1]["terminal"][2] == LR.R_AGAINST


@pytest.mark.parametrize("mirror", [False, True])
def test_verdict_same_side_same_visit_mirror(mirror):
    O, C, H, L = _visits(mirror)
    side, other = (BULL, BEAR) if not mirror else (BEAR, BULL)
    ctx = {"ok": True, "trend": "RANGE", "sides": {BULL, BEAR}, "band": None}
    ev = [(1, LR.ARMED, "price arrived"), (2, LR.ARMED, LR.R_ABSORPTION), (3, LR.DISARMED, LR.R_TIMEOUT)]
    v = RP.gate_visits(ev, O, C, H, L, AREA, 9)
    assert RP.verdict(v, 2, side, ctx, AREA)[0] == "SKIPPED_GATE_TIMEOUT_ABSORPTION"
    assert RP.verdict(v, 0, side, ctx, AREA)[0] == "SKIPPED_GATE_TIMEOUT_ABSORPTION"        # touch एक bar आधी, arrival पुढच्या bar ला
    assert RP.verdict(v, 2, other, ctx, AREA)[0] == "SKIPPED_GATE_NOT_AT_AREA"              # उलट बाजू ⇒ त्या भेटीचं कारण नाही
    assert RP.verdict(v, 5, side, ctx, AREA)[0] == "SKIPPED_GATE_NOT_AT_AREA"               # भेट संपली (bar 4 ला area सोडली)
    v2 = RP.gate_visits([(1, LR.ARMED, "price arrived"), (2, LR.DISARMED, "R:R < min (1.2 < 3)")], O, C, H, L, AREA, 9)
    assert RP.verdict(v2, 1, side, ctx, AREA)[0] == "SKIPPED_GATE_RR"
    v3 = RP.gate_visits([(1, LR.ARMED, "price arrived")], O, C, H, L, AREA, 4)
    assert RP.verdict(v3, 2, side, ctx, AREA)[0] == "SKIPPED_GATE_WAITING_COMMITMENT"
    v4 = RP.gate_visits([(1, LR.ARMED, "price arrived"), (3, LR.CONFIRMED, "c")], O, C, H, L, AREA, 9)
    assert RP.verdict(v4, 2, side, ctx, AREA, sig_bars={3})[0] == "KEPT"
    assert RP.verdict(v4, 2, side, ctx, AREA, sig_bars={7})[0] != "KEPT"                     # signal दुसऱ्या भेटीत ⇒ kept नाही
    assert RP.verdict(v4, 2, side, ctx, AREA, sig_bars=set(), cutoff=3)[0] == "SKIPPED_GATE_AFTER_CUTOFF"
    assert RP.verdict(v4, 2, side, ctx, AREA, sig_bars=set(), cutoff=9)[0] == "GATE_HINDSIGHT"


@pytest.mark.parametrize("ctx,side", [(UP, BEAR), (DOWN, BULL)])
def test_verdict_against_trend_mirror(ctx, side):
    assert RP.verdict([], 0, side, ctx, AREA)[0] == "SKIPPED_GATE_AGAINST_TREND"


def test_verdict_no_trend_first():
    nt = {"ok": False, "trend": "UP", "phase": "impulse", "counter": "correction", "reason": LR.R_NO_TREND + " (x)"}
    code, _, det = RP.verdict([], 0, BULL, nt, AREA, sig_bars={1})
    assert code == "SKIPPED_GATE_NO_TREND" and det == "Daily UP: parent correction (A1)"
    assert RP.no_trend_detail({"trend": "NEUTRAL"}) == "Daily NEUTRAL" and "origin at risk" in RP.no_trend_detail({"trend": "DOWN", "origin_risk": True})


def _trades(rows):
    base = {c: None for c in RP.TRADE_COLS}
    return pd.DataFrame([{**base, **r} for r in rows])[RP.TRADE_COLS]


def test_rejection_summary_groups_and_saved():
    t0 = pd.Timestamp("2021-06-01 10:00")
    rows = [{"bot": "B", "symbol": "NIFTY", "mode": RP.TOUCH, "period": "IS", "trend": "bull", "time": t0 + pd.Timedelta(minutes=i),
             "net_pts": x, "gate_code": c} for i, (x, c) in enumerate([(-10, "SKIPPED_GATE_BROKEN"), (-5, "SKIPPED_GATE_BROKEN"),
                                                                       (8, "SKIPPED_GATE_RR"), (3, "KEPT")])]
    rows.append({"bot": "B", "symbol": "NIFTY", "mode": RP.CONF, "period": "IS", "trend": "bull", "time": t0, "net_pts": 1.0, "gate_code": None})
    rs = RP.rejection_summary(_trades(rows)).set_index("gate_code")
    assert rs.loc["SKIPPED_GATE_BROKEN", "n"] == 2 and rs.loc["SKIPPED_GATE_BROKEN", "saved"] == pytest.approx(15.0)
    assert rs.loc["SKIPPED_GATE_RR", "saved"] == pytest.approx(-8.0) and rs.loc["SKIPPED_GATE_RR", "wins"] == 1
    assert pd.isna(rs.loc["KEPT", "saved"]) and "B" in set(rs["bot"])


# ------------------------------------------------------------------------------------------------ n < 30 ⇒ निष्कर्ष नाही
def _mode_rows(mode, n, trend="bull", pts=1.0):
    t0 = pd.Timestamp("2021-06-01 10:00")
    return [{"bot": "B", "symbol": "NIFTY", "mode": mode, "period": "IS", "trend": trend, "day": t0.normalize(), "time": t0 + pd.Timedelta(minutes=i),
             "level": 100.0, "direction": BULL, "exit_reason": "TARGET", "net_pts": pts, "gate_code": "KEPT" if mode == RP.TOUCH else None,
             "gate_reason": "", "gate_detail": "", "gate_kept_taken": False} for i in range(n)]


def test_no_conclusion_below_30_and_sample_banner():
    small = _trades(_mode_rows(RP.TOUCH, 29) + _mode_rows(RP.CONF, 40))
    assert RP.conclusion_lines(RP.summary(small)) == []
    md = RP.render_report(small, {"assumptions": ["x"]}, sample=True)
    assert "SAMPLE — full run pending" in md and "n < 30 — no conclusion" in md and "None — no cell reaches n ≥ 30" in md
    big = _trades(_mode_rows(RP.TOUCH, 30, pts=-1.0) + _mode_rows(RP.CONF, 31, pts=2.0))
    lines = RP.conclusion_lines(RP.summary(big))
    assert any("· bull · confirmation:" in x and "+3.00 pts/trade" in x for x in lines) and not any("· bear ·" in x for x in lines)
    assert "SAMPLE" not in RP.render_report(big, {"assumptions": []}, sample=False)
    assert RP.cell_note(30, 30) == "" and RP.cell_note(30, 29) == "n < 30 — no conclusion"


# ------------------------------------------------------------------------------------------------ holdout पहारा
def test_holdout_guard_nifty_only():
    df = pd.DataFrame({"timestamp": [DP.VAL_END - pd.Timedelta(days=1), DP.HOLDOUT_START + pd.Timedelta(hours=10)]})
    with pytest.raises(DP.HoldoutError):
        RP.assert_research_only(df, "NIFTY")
    assert RP.assert_research_only(df.iloc[:1], "NIFTY") and RP.assert_research_only(df, "BANKNIFTY")
    with pytest.raises(DP.HoldoutError):
        RP.period_of("NIFTY", DP.HOLDOUT_START)
    assert RP.period_of("NIFTY", DP.IS_START) == "IS" and RP.period_of("NIFTY", DP.VAL_START) == "VAL" and RP.period_of("GOLD", DP.HOLDOUT_START) == "HOLDOUT"


def test_prepare_market_refuses_holdout_rows():
    d = day_bars(day=str(DP.HOLDOUT_START.date()), n=30)
    with pytest.raises(DP.HoldoutError):
        RP.prepare_market("NIFTY", d, 1, fold=lambda x: [])


def test_cli_refuses_holdout_range(tmp_path):
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("lbr_cli", os.path.join(os.path.dirname(RP.__file__), "scripts", "level_bots_replay.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    with pytest.raises(DP.HoldoutError):
        cli.main(["--symbols", "NIFTY", "--start", str(DP.VAL_START.date()), "--end", str((DP.HOLDOUT_START + pd.Timedelta(days=30)).date()),
                  "--out", str(tmp_path), "--report", str(tmp_path / "r.md")])
    assert cli.per_symbol("NIFTY=2021-01-01,gold=2026-09-01") == (None, {"NIFTY": "2021-01-01", "GOLD": "2026-09-01"})
    assert cli.per_symbol("2021-01-01") == ("2021-01-01", {})


# ------------------------------------------------------------------------------------------------ data / trend / legacy = bot functions
def minutes(days=4, start="2021-06-01", seed=3, px=22000.0):
    rng = np.random.default_rng(seed)
    out = []
    for d in pd.bdate_range(start, periods=days):
        for m in range(375):
            t = d + pd.Timedelta(hours=9, minutes=15 + m)
            c = px + rng.normal(0, 3)
            out.append({"timestamp": t, "open": px, "high": max(px, c) + 1, "low": min(px, c) - 1, "close": c})
            px = c
    return pd.DataFrame(out)


def test_one_daily_fold_per_symbol(monkeypatch, specs):
    calls = []
    from decision3 import daily as DD

    def fold(d, s=None):
        calls.append(len(d))
        return []
    monkeypatch.setattr(DD, "fold", fold)
    mk = RP.prepare_market("NIFTY", minutes(days=4), 1)
    monkeypatch.setattr(RP, "levels_at", lambda *a, **k: [])
    RP.replay(mk, specs["instant"], mk.days)
    RP.replay(mk, specs["srv2"], mk.days)
    assert len(calls) == 1                                                   # एकदाच fold, दिवसागणिक state_at
    assert RP.trend_ctx(mk, mk.days[1])["trend"] == "UNKNOWN" and RP.trend_bucket(RP.trend_ctx(mk, mk.days[1])) == "no trend"


def test_legacy_uses_the_bots_own_functions(specs):
    import classic_sr_reversal_trader as CSR
    import dynamic_sr_instant_trader as DSI
    import mcx_futures_trader as MCX
    import srv2_momentum_reversal_strategy as SRV2
    from cloud_db import STRATEGY_SETTINGS_DEFAULTS as SSD
    i, v, c = specs["instant"], specs["srv2"], specs["classic"]
    assert i.touch_fn is DSI.check_level_crossed and i.dir_fn is DSI.determine_direction_with_hysteresis and i.touch_tol_pct == DSI.TOUCH_TOLERANCE_PCT
    assert v.touch_fn is SRV2.check_level_crossed and v.dir_fn is SRV2.determine_direction_with_hysteresis and v.touch_tol_pct == SRV2.TOUCH_TOLERANCE_PCT
    assert c.touch_fn is CSR.check_level_crossed and c.touch_tol_pct == CSR.TOUCH_TOLERANCE_PCT and specs["mcx"].dir_fn is MCX.determine_direction_with_hysteresis
    assert i.sl == ("pct", SSD["1m_instant"]["naked_sl_spot_pct"]) and v.target == ("pct", SSD["15m_dynamic_sr"]["naked_target_spot_pct"])
    assert v.level_tfs == tuple(SSD["15m_dynamic_sr"]["active_timeframes"]) and c.level_tfs == ("5M", "15M")
    assert (c.rsi_bull_max, c.rsi_bear_min) == (SSD["classic_sr_reversal"]["rsi_neutral_level"],) * 2


def test_position_rules_match_live(specs):
    """review 🟡2 / 🟡3: Instant — (level, role) 30 मिनिटं; SRv2 — symbol-व्यापी cooldown नाही (live मध्ये कधीच लागत नाही); Classic —
    (level, role) 30; TSL = naked_tsl_spot_pct; MCX — symbol-व्यापी SL cooldown + level-दिशा block, live च structural (L4)."""
    from cloud_db import STRATEGY_SETTINGS_DEFAULTS as SSD
    i, v, c, m = specs["instant"], specs["srv2"], specs["classic"], specs["mcx"]
    assert (i.level_trade_gap, i.symbol_sl_cooldown, i.level_sl_cooldown) == (30, 0, SSD["1m_instant"]["sl_tsl_cooldown_minutes"])
    assert (v.level_trade_gap, v.symbol_sl_cooldown) == (0, 0) and (c.level_trade_gap, c.symbol_sl_cooldown) == (30, 0)
    assert i.tsl_pct == SSD["1m_instant"]["naked_tsl_spot_pct"] and v.tsl_pct == SSD["15m_dynamic_sr"]["naked_tsl_spot_pct"]
    assert c.tsl_pct == SSD["classic_sr_reversal"]["naked_tsl_spot_pct"] and m.tsl_pct is None
    assert m.symbol_sl_cooldown == SSD["mcx_futures"]["sl_cooldown_minutes"] and m.level_dir_sl_block and m.live_structural
    assert "ILLUSTRATION" in m.illustration and not i.live_structural


def _touch_market(monkeypatch, closes_today, level, rsi):
    """दिवस 1–2 सपाट, दिवस 3 = closes_today; level एकच; RSI स्थिर."""
    d0 = minutes(days=2, px=level + 50)
    d0["open"] = d0["high"] = d0["low"] = d0["close"] = level + 50
    day = pd.bdate_range("2021-06-01", periods=3)[-1]
    rows = []
    prev = closes_today[0]
    for k, c in enumerate(closes_today):
        t = day + pd.Timedelta(hours=9, minutes=15 + k)
        rows.append({"timestamp": t, "open": prev, "high": max(prev, c) + 0.5, "low": min(prev, c) - 0.5, "close": c})
        prev = c
    mk = RP.prepare_market("NIFTY", pd.concat([d0, pd.DataFrame(rows)], ignore_index=True), 1, fold=lambda x: [])
    for m in mk.rsi:
        mk.rsi[m][:] = rsi
    monkeypatch.setattr(RP, "levels_at", lambda *a, **k: [("5M", float(level))])
    return mk, day


@pytest.mark.parametrize("side,path,rsi", [
    (BULL, [22030.0 - 2 * k for k in range(15)] + [22002.0 + 3 * k for k in range(360)], 30.0),   # वरून येऊन support ⇒ long ⇒ target
    (BEAR, [21970.0 + 2 * k for k in range(15)] + [21998.0 - 3 * k for k in range(360)], 70.0),   # खालून येऊन resistance ⇒ short ⇒ target
])
def test_legacy_touch_day_mirror(monkeypatch, specs, side, path, rsi):
    mk, day = _touch_market(monkeypatch, path, 22000.0, rsi)
    out = RP.replay_day(mk, specs["instant"], day, cost=0.0)
    t = out["touch"][0]
    assert t["direction"] == side and t["exit_reason"] == "TARGET" and t["level"] == 22000.0
    assert t["gross_pts"] == pytest.approx(t["entry"] * specs["instant"].target[1] / 100)
    assert t["gate_code"] == "SKIPPED_GATE_NO_TREND"                         # fold [] ⇒ trend UNKNOWN ⇒ gate entry नाही
    assert out["conf"] == []
    mk2, _ = _touch_market(monkeypatch, path, 22000.0, 50.0)                  # RSI gate अपयशी ⇒ legacy entry नाही
    assert RP.replay_day(mk2, specs["instant"], day, cost=0.0)["touch"] == []


@pytest.mark.parametrize("side", [BULL, BEAR])
def test_confirmation_arm_takes_the_gate_plan_mirror(monkeypatch, specs, side):
    """gate (LR.safe_evaluate) ने commitment candle वर entry दिला ⇒ confirmation arm: त्याच entry ला **bot चेच exits** (live: exits ला हात
    नाही); structural arm (not live): gate चा SL / target."""
    sg = 1 if side == BULL else -1
    path = [22000.0 + sg * 0.5 * k for k in range(375)]
    mk, day = _touch_market(monkeypatch, path, 22000.0, 50.0)
    ctx = {"ok": True, "trend": "UP" if side == BULL else "DOWN", "sides": {side}, "reason": "Daily"}
    monkeypatch.setattr(RP, "trend_ctx", lambda *a, **k: ctx)
    cf = mk.frames[5]
    t_conf = int(mk.day_rows[5][day][2])                                      # दिवसाचा 3रा 5m candle
    seen = []

    def fake_eval(bars, area, ctx_, others, k0, s=None, **_ltf):
        t = len(bars) - 1
        seen.append(t)
        if bars["timestamp"].iloc[-1] == cf["timestamp"].iat[t_conf]:
            c = float(bars["close"].iloc[-1])
            return {"state": LR.CONFIRMED, "entry": True, "side": side, "entry_price": c, "sl": c - sg * 5, "target": c + sg * 20,
                    "events": [(t, LR.CONFIRMED, "x")], "grade": "B", "form": "engulf", "rr": 4.0}
        return {"state": LR.ARMED, "entry": False, "side": side, "events": []}
    monkeypatch.setattr(RP.LR, "safe_evaluate", fake_eval)
    out = RP.replay_day(mk, specs["instant"], day, cost=0.0)
    assert len(out["conf"]) == 1 and len(out["struct"]) == 1
    c, st = out["conf"][0], out["struct"][0]
    assert c["direction"] == side and c["time"] == cf["end"].iat[t_conf] and c["exit_reason"] == "TARGET"
    plan = RP.legacy_plan(specs["instant"], c["entry"], side)
    assert (c["sl"], c["target"]) == (plan["sl"], plan["target"]) and c["gross_pts"] == pytest.approx(c["entry"] * specs["instant"].target[1] / 100)
    assert st["exit_reason"] == "TARGET" and st["gross_pts"] == pytest.approx(20.0) and st["sl"] == pytest.approx(st["entry"] - sg * 5)
    assert c["grade"] == "B" and seen                                          # gate फक्त area जवळच्या candles वर विचारला


def test_levels_at_uses_only_closed_bars(monkeypatch, specs):
    mk = RP.prepare_market("NIFTY", minutes(days=12), 1, fold=lambda x: [])
    seen = {}
    import sr_dynamic

    def fake(df, **k):
        seen["end"] = df["end"].max()
        seen["n"] = len(df)
        return {"support": [{"level": 1.0}], "resistance": [{"level": 2.0}, {"level": 1.0}]}
    monkeypatch.setattr(sr_dynamic, "compute_dynamic_sr", fake)
    T = mk.days[-1] + pd.Timedelta(hours=10, minutes=17)
    assert RP.levels_at(mk, specs["instant"], T) == [("5M", 1.0), ("5M", 2.0)]
    assert seen["end"] <= T and seen["end"] == mk.days[-1] + pd.Timedelta(hours=10, minutes=15)
    assert RP.refresh_times(mk.days[0], "09:15", "14:45", 60)[-1] == mk.days[0] + pd.Timedelta(hours=14, minutes=15)


def test_gate_area_matches_bots_pad(specs):
    import classic_sr_reversal_trader as CSR
    assert RP.gate_area(22000.0) == CSR._gate_area(22000.0, {})


def test_cost_points_from_charges():
    import charges as CH
    c = RP.COST_DEFAULTS["NIFTY"]
    rupees = sum(CH._accurate_row_charges({"quantity": c["lot"], "price": c["premium"], "symbol": "NIFTY", "transaction_type": t}, "upstox")["charge"]
                 for t in ("BUY", "SELL"))
    assert RP.cost_points("NIFTY", 22000.0) == pytest.approx(rupees / (c["lot"] * c["delta"]) + 2 * c["slip_prem"] / c["delta"])
    assert RP.cost_points("GOLD", 150000.0) > RP.cost_points("GOLD", 100000.0) > 2 * RP.COST_DEFAULTS["GOLD"]["slip_pts"]
    assert RP.cost_points("UNKNOWN", 1.0) == 0.0


def test_replay_is_deterministic(monkeypatch, specs):
    mk = RP.prepare_market("NIFTY", minutes(days=12, seed=9), 1, fold=lambda x: [])
    a = RP.replay(mk, specs["classic"], mk.days[-3:], cost=0.0)
    b = RP.replay(mk, specs["classic"], mk.days[-3:], cost=0.0)
    assert a.to_csv(index=False) == b.to_csv(index=False)


def test_supported_markets(specs):
    mk = RP.prepare_market("BANKNIFTY", minutes(days=2).iloc[::15].reset_index(drop=True), 15, fold=lambda x: [])
    assert RP.supported(mk, specs["srv2"]) and not RP.supported(mk, specs["instant"]) and not RP.supported(mk, specs["mcx"])
    assert RP.confirm_tf(mk, specs["srv2"]) == 15


# ------------------------------------------------------------------------------------------------ review fixes: TSL, dropped, MCX L4, काळ, is_nifty
@pytest.mark.parametrize("side", [BULL, BEAR])
def test_tsl_to_breakeven_sticky_mirror(specs, side):
    """spot TSL उंबरठा गाठला ⇒ पुढच्या bar पासून SL = entry ("TSL_SL"); आधीचा SL (−) आता लागत नाही."""
    sg = 1 if side == BULL else -1
    sp = dataclasses.replace(specs["instant"], level_trade_gap=0)
    closes = [100.0] * 5 + [100.0 + sg * 0.15] * 3 + [100.0 - sg * 0.02] * 367    # +0.15% ⇒ TSL (0.10%), target (0.20%) नाही; मग खाली ⇒ breakeven
    b = day_bars(closes=closes, spread=0.0)
    cd = {"time": pd.Timestamp("2021-06-01 09:20"), "level": 100.0, "direction": side, "entry": 100.0, **RP.legacy_plan(sp, 100.0, side)}
    t = RP.take_trades([cd], b, sp, "NIFTY", cost=0.0)[0]
    assert t["exit_reason"] == "TSL_SL" and t["exit"] == pytest.approx(100.0) and t["gross_pts"] == pytest.approx(0.0)
    no_tsl = dataclasses.replace(sp, tsl_pct=None)
    cd2 = {**cd, **RP.legacy_plan(no_tsl, 100.0, side)}
    assert RP.take_trades([cd2], b, no_tsl, "NIFTY", cost=0.0)[0]["exit_reason"] == "EOD"   # TSL नाही ⇒ SL (0.05%) दूर ⇒ EOD


def test_tsl_same_bar_trigger_does_not_exit_at_breakeven(specs):
    pos = {"direction": BULL, "entry": 100.0, "sl": 99.0, "target": 105.0, "tsl": 100.1, "tsl_on": False}
    assert RP.exit_on_bar(pos, 100, 100.2, 99.95, 100.1, False) == (None, None) and RP.tsl_reached(pos, 100.2, 99.95)
    pos["tsl_on"] = True
    assert RP.exit_on_bar(pos, 100.1, 100.2, 99.95, 100.0, False) == ("TSL_SL", 100.0)


def test_last_bar_entry_is_dropped_and_logged(specs):
    sp = dataclasses.replace(specs["mcx"], last_entry="23:59", eod="23:59")
    b = day_bars(n=10)
    last = b["end"].iloc[-1]
    dropped = []
    cd = {"time": last, "level": 100.0, "direction": BULL, "entry": 100.0, "sl": 90.0, "target": 110.0, "tsl": None}
    assert RP.take_trades([cd], b, sp, "NIFTY", cost=0.0, dropped=dropped) == []
    assert len(dropped) == 1 and dropped[0]["exit_reason"] == "entry on the session's last bar"


@pytest.mark.parametrize("side", [BULL, BEAR])
def test_mcx_l4_plan_mirror(specs, side):
    """L4: structural SL settings SL पेक्षा रुंद ⇒ SL_TOO_WIDE; entry भावावर R:R < min ⇒ RR; नाहीतर structural SL / target."""
    sg = 1 if side == BULL else -1
    m = specs["mcx"]
    cap = m.sl[1]
    ok, why = RP.l4_plan({"direction": side, "entry": 1000.0, "plan_sl": 1000.0 - sg * cap * 0.5, "plan_target": 1000.0 + sg * cap * 2}, m, 3)
    assert why is None and ok["sl"] == 1000.0 - sg * cap * 0.5 and ok["tsl"] is None
    assert RP.l4_plan({"direction": side, "entry": 1000.0, "plan_sl": 1000.0 - sg * cap * 1.5, "plan_target": 1000.0 + sg * cap * 9}, m, 3)[1] == \
        "SKIPPED_GATE_SL_TOO_WIDE"
    assert RP.l4_plan({"direction": side, "entry": 1000.0, "plan_sl": 1000.0 - sg * cap * 0.5, "plan_target": 1000.0 + sg * cap}, m, 3)[1] == \
        "SKIPPED_GATE_RR"
    assert RP.l4_plan({"direction": side, "entry": 1000.0, "plan_sl": 1000.0 + sg, "plan_target": 1000.0 + sg * 50}, m, 3)[1] == \
        "SKIPPED_GATE_INVALIDATED"


def test_period_labels_and_is_nifty_seal():
    assert RP.period_of("BANKNIFTY", DP.CONTAMINATED_START) == "CONTAMINATED" and RP.period_of("GOLD", DP.ILLUSTRATION_START) == "ILLUSTRATION"
    assert RP.period_of("BANKNIFTY", DP.HOLDOUT_START) == "HOLDOUT"           # BANKNIFTY sealed नाही, पण काळ नाव दिसतं
    df = pd.DataFrame({"timestamp": [DP.HOLDOUT_START]})
    for name in ("NIFTY 50", "NIFTY50", "nifty"):
        with pytest.raises(DP.HoldoutError):
            RP.assert_research_only(df, name)
        with pytest.raises(DP.HoldoutError):
            RP.period_of(name, DP.HOLDOUT_START)
    assert RP.assert_research_only(df, "BANKNIFTY") and RP.assert_research_only(df, "FINNIFTY")


def test_summary_struct_arm_only_for_nse_bots(specs):
    rows = _mode_rows(RP.TOUCH, 3) + _mode_rows(RP.CONF, 2)
    t = _trades([{**r, "bot": "MCX"} for r in rows] + [{**r, "bot": "Classic"} for r in rows])
    sm = RP.summary(t)
    assert RP.STRUCT not in set(sm[sm["bot"] == "MCX"]["mode"]) and RP.STRUCT in set(sm[sm["bot"] == "Classic"]["mode"])
    skip = _trades([{**rows[0], "mode": RP.SKIPPED, "gate_code": "SKIPPED_GATE_SL_TOO_WIDE", "gate_reason": RP.CONF, "bot": "MCX"}])
    assert len(RP.summary(skip)) == 0 or RP.summary(skip)["n"].sum() == 0     # skipped नोंदी metrics मध्ये नाहीत

