"""bots_common/level_reaction (Abhi: TRADE_SESSION_LEVEL_BOTS_CONFIRMATION §7) — trend first, arrival ≠ entry, closed bars only."""
import json

import numpy as np
import pandas as pd
import pytest

from bots_common import level_reaction as LR

DAY0 = pd.Timestamp("2001-01-01 09:15")   # synthetic sessions (खरी तारीख नाही)
UP_CTX = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP"}
DOWN_CTX = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN"}
AREA = (990.0, 1000.0)                    # demand area


@pytest.fixture(autouse=True)
def _a2_c0_contract_without_c1(monkeypatch):
    """हा module a2 / c0 / state machine चा करार तपासतो (c1 आधीचा) ⇒ इथे c1 (LTF CHoCH) बंद — c1 सुरू असताना तेच वर्तन + CHoCH ची अट
    tests/test_level_reaction_c1.py मध्ये (प्रत्येक case आरशासह)."""
    monkeypatch.setitem(LR.DEFAULTS, "ltf_choch", False)
OTHERS = [(1090.0, 1100.0), (900.0, 910.0)]


def _bars(rows, warm=True):
    """rows = [(o, h, l, c)] आजच्या session चे 5M bars; warm = आदल्या दिवसाचे 30 शांत bars area च्या वर (median range ≈ 8)."""
    pre = [(1030.0, 1034.0, 1026.0, 1030.0)] * 30 if warm else []
    ts = [DAY0 - pd.Timedelta(days=1) + pd.Timedelta(minutes=5 * i) for i in range(len(pre))]
    ts += [DAY0 + pd.Timedelta(minutes=5 * i) for i in range(len(rows))]
    allr = pre + list(rows)
    df = pd.DataFrame(allr, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    return df, len(pre)


# corrective pullback from 1030 to the area (overlapping, small bars)
PULL = [(1030, 1031, 1024, 1025), (1025, 1027, 1018, 1019), (1019, 1021, 1012, 1013), (1013, 1015, 1006, 1007),
        (1007, 1009, 1001, 1002)]
TOUCH = (1002, 1003, 995, 999)                       # area ला स्पर्श, अजून प्रतिक्रिया नाही
SWEEP = (999, 1000, 987, 997)                        # far edge (990) खाली wick, close परत आत (sweep)
BULL_ENGULF = (996, 1009, 995, 1008)                 # bullish commitment, close area वर (inner edge 1000 पलीकडे)


def _run(rows, ctx=UP_CTX, others=OTHERS, s=None, area=AREA):
    df, k = _bars(rows)
    return LR.evaluate(df, area, ctx, others, session_start=k, s=s)


def test_touch_without_reaction_no_entry_then_timeout():
    r = _run(PULL + [TOUCH] + [(999, 1001, 996, 998)] * 3)
    assert r["state"] == LR.ARMED and not r["entry"] and r["reason"].startswith(LR.R_NO_COMMIT)
    r = _run(PULL + [TOUCH] + [(999, 1001, 996, 998)] * 10)
    assert r["state"] == LR.DISARMED and r["reason"] == LR.R_TIMEOUT and not r["entry"]


def test_sweep_plus_bullish_commitment_in_up_trend_is_entry():
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF])
    assert r["state"] == LR.CONFIRMED and r["entry"] and r["side"] == LR.BULL
    assert r["evidence"]["sweep"] and r["sl"] < 987 and r["target"] == 1090.0 and r["rr"] is None   # R:R gate default बंद ⇒ R:R नाही
    assert r["entry_price"] == 1008.0
    r_on = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], s={"rr_gate_enabled": True})                    # dashboard rr gate चालू ⇒ जुनं
    assert r_on["entry"] and r_on["rr"] >= 3


def test_same_candles_at_support_in_down_trend_are_ignored():
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], ctx=DOWN_CTX)
    assert not r["entry"] and any(e[2] == LR.R_AGAINST for e in r["events"])


def test_impulsive_drive_through_area_is_broken_no_trade():
    drive = [(1030, 1031, 1012, 1013), (1013, 1014, 994, 995), (995, 996, 970, 971), (971, 972, 960, 961), (961, 962, 955, 957)]
    r = _run(drive)
    assert r["broken"] and not r["entry"] and r["state"] in (LR.DISARMED, LR.IDLE)   # area सोडली ⇒ IDLE (flip retest शक्य)
    assert any(e[2] == LR.R_BROKEN for e in r["events"])


def test_impulsive_approach_without_break_is_disarmed():
    drive = [(1030, 1031, 1016, 1017), (1017, 1018, 1003, 1004), (1004, 1005, 991, 992)]
    r = _run(drive + [BULL_ENGULF])
    assert not r["entry"] and any(e[2] == LR.R_IMPULSIVE for e in r["events"])


def test_range_both_edges_tradable():
    ctx = {"ok": True, "trend": "RANGE", "sides": {LR.BULL, LR.BEAR}, "band": (980.0, 1080.0), "reason": "RANGE"}
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], ctx=ctx)
    assert r["entry"] and r["side"] == LR.BULL
    # upper edge: supply 1060–1070, price rallies into it from below and rejects
    up = [(1030, 1036, 1029, 1035), (1035, 1042, 1034, 1041), (1041, 1048, 1040, 1047), (1047, 1054, 1046, 1053),
          (1053, 1058, 1052, 1057), (1057, 1065, 1056, 1062), (1062, 1063, 1048, 1049)]
    df, k = _bars(up)
    r2 = LR.evaluate(df, (1060.0, 1070.0), ctx, [(990.0, 1000.0)], session_start=k, s={"min_rr": 1.0})
    assert r2["side"] == LR.BEAR and r2["state"] == LR.CONFIRMED and r2["entry"]
    # RANGE: bullish only in the lower half
    assert not LR.side_allowed(ctx, LR.BULL, (1060.0, 1070.0)) and not LR.side_allowed(ctx, LR.BEAR, (990.0, 1000.0))


def test_rr_below_min_is_skipped_with_reason():
    """Abhi (rr-correction): R:R entry ची अट नाही ⇒ default (gate_rr_gate_enabled बंद) skip / disarm / R:R नाही; चालू ⇒ जुना नियम."""
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], others=[(1015.0, 1020.0)])
    assert r["entry"] and r["state"] == LR.CONFIRMED and r["rr"] is None
    assert not any(str(e[2]).startswith(LR.R_RR) for e in r["events"]) and "R:R" not in LR.describe(r)
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], others=[(1015.0, 1020.0)], s={"rr_gate_enabled": True})
    assert not r["entry"] and r["state"] == LR.DISARMED and r["reason"].startswith(LR.R_RR)


def test_no_target_area_is_skipped():
    """Abhi (RR3): "no target area" = स्वतंत्र dashboard setting `gate_no_target_disarm_enabled` (default बंद) — rr gate पासून स्वतंत्र."""
    rows = PULL + [TOUCH, SWEEP, BULL_ENGULF]
    r = _run(rows, others=[])                                                                  # दोन्ही बंद (default)
    assert r["entry"] and r["state"] == LR.CONFIRMED and r["target"] is None and r["rr"] is None
    r = _run(rows, others=[], s={"rr_gate_enabled": True})                                     # फक्त rr gate: target नाही ⇒ R:R मोजता येत नाही ⇒ skip नाही
    assert r["entry"] and r["state"] == LR.CONFIRMED
    r = _run(rows, others=[], s={"no_target_disarm_enabled": True})                            # फक्त no-target setting ⇒ जुनं "no target area"
    assert not r["entry"] and r["state"] == LR.DISARMED and r["reason"] == LR.R_NO_TARGET
    r = _run(rows, others=[(1015.0, 1020.0)], s={"no_target_disarm_enabled": True})            # target आहे ⇒ no-target setting लागू नाही, R:R नाही
    assert r["entry"] and r["rr"] is None


def test_invalid_sl_disarms_independent_of_rr_gate():
    """review: R:R-निरपेक्ष guard — structural SL entry च्या चुकीच्या बाजूला (rk ≤ 0) ⇒ DISARMED, rr gate बंद असतानाही."""
    from bots_common import level_gate_bot as LGB
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], s={"sl_buffer_mr": -100.0})          # SL = area खाली − (−100 × mr) ⇒ entry वर
    assert not r["entry"] and r["state"] == LR.DISARMED and r["reason"] == LR.R_BAD_SL
    assert LGB.status_of(r) == "SKIPPED_GATE_INVALID_SL"


def test_rr_gate_is_a_dashboard_setting_default_off():
    from bots_common import level_gate_bot as LGB
    assert LR.DEFAULTS["rr_gate_enabled"] is False and LGB.gate_settings({})["rr_gate_enabled"] is False
    assert LR.DEFAULTS["no_target_disarm_enabled"] is False and LGB.gate_settings({})["no_target_disarm_enabled"] is False
    assert LGB.gate_settings({"gate_rr_gate_enabled": True, "gate_min_rr": 2.0, "gate_no_target_disarm_enabled": True}) == {
        **LR.DEFAULTS, "rr_gate_enabled": True, "min_rr": 2.0, "no_target_disarm_enabled": True}


def test_unclear_trend_fails_closed():
    ctx = {"ok": False, "trend": "NEUTRAL", "sides": set(), "reason": "no entry: trend unclear (Daily NEUTRAL)"}
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], ctx=ctx)
    assert not r["entry"]
    r = LR.safe_evaluate(None, AREA, UP_CTX)
    assert r["state"] == "ERROR" and not r["entry"]


def test_closed_bars_only_and_no_lookahead():
    rows = PULL + [TOUCH, SWEEP, BULL_ENGULF, (1008, 1012, 1006, 1011), (1011, 1013, 1009, 1012)]
    df, k = _bars(rows)
    full = LR.evaluate(df, AREA, UP_CTX, OTHERS, session_start=k)
    assert not full["entry"]                                               # confirmation was 2 bars ago ⇒ no new entry now
    for m in range(k + 1, len(df) + 1):
        part = LR.evaluate(df.iloc[:m].reset_index(drop=True), AREA, UP_CTX, OTHERS, session_start=k)
        assert part["events"] == [e for e in full["events"] if e[0] < m]   # truncation invariant (bars ≤ T only)
        assert part["entry"] == (m - 1 == k + len(PULL) + 2)               # entry flagged only on the commitment bar itself
    now = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=2)              # last bar still forming
    assert len(LR.closed_bars(df, 5, now)) == len(df) - 1


def test_wait_next_candle_option():
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF], s={"wait_next_candle": True})
    assert r["state"] == LR.ARMED and not r["entry"]
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF, (1008, 1013, 1005, 1012)], s={"wait_next_candle": True})
    assert r["state"] == LR.CONFIRMED and r["entry"]
    r = _run(PULL + [TOUCH, SWEEP, BULL_ENGULF, (1008, 1009, 996, 998)], s={"wait_next_candle": True})
    assert not r["entry"] and r["state"] == LR.DISARMED


def test_trend_context_mapping(monkeypatch):
    from decision3 import daily as DD

    def fake(trend, **kw):
        return DD.DState(0, pd.Timestamp("2001-01-01"), pd.Timestamp("2001-01-01 15:30"), trend, **kw)
    d = pd.DataFrame({"timestamp": pd.date_range("2000-01-01", periods=40), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    cases = [(fake("UP", phase="impulse"), True, {LR.BULL}), (fake("DOWN", phase="correction", counter="pullback"), True, {LR.BEAR}),
             (fake("DOWN", phase="origin_broken"), False, set()),
             (fake("UP", phase="impulse", origin_risk=True), True, {LR.BULL}),     # Abhi B1: origin near = context only (was: no entries)
             (fake("DOWN", phase="correction", counter="correction"), False, set()), (fake("NEUTRAL"), False, set()),
             (fake("RANGE", band=(1.0, 2.0)), True, {LR.BULL, LR.BEAR})]
    for st, ok, sides in cases:
        monkeypatch.setattr(DD, "fold", lambda *_a, _st=st, **_k: [_st])
        c = LR.trend_context(d)
        assert c["ok"] == ok and c["sides"] == sides, (st.trend, st.phase, c)


def test_daily_trend_fails_closed_and_caches(tmp_path):
    def bad(*_):
        raise RuntimeError("network")
    c = LR.daily_trend("NIFTY", "tok", today="2001-01-10", fetch=bad, cache_dir=str(tmp_path))
    assert not c["ok"] and "fail-closed" in c["reason"]
    d = pd.DataFrame({"timestamp": pd.date_range("2000-01-01", periods=10), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    c = LR.daily_trend("NIFTY", "tok", today="2001-01-10", fetch=lambda *_: d, cache_dir=str(tmp_path), s={"trend_retry_min": 0})
    assert not c["ok"] and "अपुरा" in c["reason"]


def test_daily_trend_negative_cache_stays_fail_closed_then_retries(tmp_path, monkeypatch):
    """review 🟡6: अपयश / < 30 bars ⇒ trend_retry_min (default 15) मिनिटं पुन्हा fetch नाही (दर cycle 25 s नाही), तरीही ok False (entry नाही);
    मुदतीनंतर पुन्हा प्रयत्न, आणि पूर्ण fetch ⇒ दिवसाचा cache."""
    t = [1000.0]
    monkeypatch.setattr(LR, "_clock", lambda: t[0])
    calls = []

    def bad(*_):
        calls.append(1)
        raise RuntimeError("network")
    c = LR.daily_trend("CRUDEOIL", "tok", today="2001-01-10", fetch=bad, cache_dir=str(tmp_path))
    assert not c["ok"] and len(calls) == 1
    t[0] += 14 * 60
    c = LR.daily_trend("CRUDEOIL", "tok", today="2001-01-10", fetch=bad, cache_dir=str(tmp_path))
    assert not c["ok"] and not c["sides"] and "fail-closed" in c["reason"] and len(calls) == 1      # negative cache: fetch नाही
    short = pd.DataFrame({"timestamp": pd.date_range("2000-01-01", periods=10), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    t[0] += 2 * 60                                                         # 16 मिनिटं ⇒ मुदत संपली ⇒ पुन्हा fetch
    c = LR.daily_trend("CRUDEOIL", "tok", today="2001-01-10", fetch=lambda *_: calls.append(2) or short, cache_dir=str(tmp_path))
    assert not c["ok"] and "अपुरा" in c["reason"] and calls == [1, 2]
    c = LR.daily_trend("CRUDEOIL", "tok", today="2001-01-10", fetch=lambda *_: calls.append(3) or short, cache_dir=str(tmp_path))
    assert not c["ok"] and calls == [1, 2]                                 # < 30 bars सुद्धा negative cache
    assert not (tmp_path / "trend_CRUDEOIL_2001-01-10.json").exists() and (tmp_path / "trend_CRUDEOIL_2001-01-10_fail.json").exists()
    c = LR.daily_trend("CRUDEOIL", "tok", today="2001-01-10", fetch=bad, cache_dir=str(tmp_path), s={"allow_parent_correction": True})
    assert len(calls) == 3                                                 # वेगळी key (_a1) ⇒ वेगळा negative cache


def test_daily_trend_cache_from_older_code_is_not_reused(tmp_path):
    """PR #305 review 🟡: a cache written today by the code before a Daily-gate change (no / old `engine` tag, ok True) must not be
    reused after deploy ⇒ recomputed (here the fetch fails ⇒ fail-closed, not the stale ok True); a current-version cache is reused."""
    p = tmp_path / "trend_NIFTY_2001-01-10.json"
    p.write_text(json.dumps({"ok": True, "trend": "DOWN", "sides": [LR.BEAR], "reason": "Daily DOWN"}), encoding="utf-8")
    calls = []

    def bad(*_):
        calls.append(1)
        raise RuntimeError("network")
    c = LR.daily_trend("NIFTY", "tok", today="2001-01-10", fetch=bad, cache_dir=str(tmp_path))
    assert calls == [1] and not c["ok"] and not c["sides"]
    p.write_text(json.dumps({"ok": True, "trend": "DOWN", "sides": [LR.BEAR], "reason": "Daily DOWN", "engine": LR.TREND_CTX_VERSION}),
                 encoding="utf-8")
    c = LR.daily_trend("NIFTY", "tok", today="2001-01-10", fetch=bad, cache_dir=str(tmp_path), s={"trend_retry_min": 0})
    assert c["ok"] and c["sides"] == {LR.BEAR} and calls == [1]


def test_today_daily_bar_is_dropped():
    d = pd.DataFrame({"timestamp": pd.date_range("2000-01-01", periods=5), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    assert len(LR.prepare_daily(d, today="2000-01-05")) == 4


def test_describe_line():
    r = _run(PULL + [TOUCH] + [(999, 1001, 996, 998)] * 2)
    line = LR.describe(r)
    assert line.startswith("Watching demand 990–1,000 · price arrived · waiting for a bullish commitment · 3/8 bars")


def test_preopen_report_lists_trade_side_areas_and_fail_closed():
    import importlib.util
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "level_gate_preopen.py")
    spec = importlib.util.spec_from_file_location("level_gate_preopen", p)
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    zones = pd.DataFrame([
        {"zone_type": "SUPPORT_5M", "zone_low": 990.0, "zone_high": 1000.0, "status": "ACTIVE"},
        {"zone_type": "RESISTANCE_5M", "zone_low": 1060.0, "zone_high": 1070.0, "status": "ACTIVE"},
        {"zone_type": "SUPPORT_15M", "zone_low": 950.0, "zone_high": 955.0, "status": "BROKEN"}])
    ctxs = {"NIFTY": UP_CTX, "BANKNIFTY": {"ok": False, "trend": "NEUTRAL", "sides": set(), "reason": "no entry: trend unclear"}}
    msg = P.build_report(["NIFTY", "BANKNIFTY"], "tok", lambda s: zones, lambda s: 1030.0, trend_fn=lambda s: ctxs[s])
    assert "watching demand 990–1,000" in msg and "supply 1,060" not in msg          # UP ⇒ फक्त खालचे demand
    assert "NO NEW ENTRIES" in msg.split("<b>BANKNIFTY</b>")[1]
    assert "LIVE MCX stays on touch" in msg                                  # review nit: LIVE MCX चा mode बदलत नाही


def test_vision_chart_draws_gate_area_entry_sl_target():
    from tests.test_vision_v0 import m1_frame, sig
    from vision import chart as CH
    from bots_common import level_gate_bot as LGB
    r = {"area": (24990.0, 25000.0), "side": LR.BULL, "form": "engulf", "grade": "B", "entry_price": 25012.0, "sl": 24980.0,
         "target": 25120.0, "rr": 3.4, "evidence": {"sweep": True}}
    tags = LGB.gate_tags(r, UP_CTX, "5M")
    s_ = sig(tags=tags)
    setup, higher, tfs = CH.panels(m1_frame(), s_["signal_ts"], s_["setup_tf"])
    fig = CH.build_figure(setup, higher, s_, tfs)
    texts = [a.text for a in fig.layout.annotations]
    # Abhi (RR2): engine SL / target = "engine reference" (माहिती); trade चे SL / target dashboard चे
    assert any(t.startswith("ENGINE REF SL 24,980") for t in texts) and any(t.startswith("ENGINE REF TARGET 25,120") for t in texts)
    assert "R:R 3.4" in fig.layout.title.text
    lines = LGB.gate_caption_lines(tags)
    assert "demand 24,990–25,000" in lines[0] and "R:R 3.4" in lines[1] and "engine reference (info): SL 24980.0" in lines[1]
    assert lines[-1] == "Trade SL / target: dashboard settings"
    fig0 = CH.build_figure(setup, higher, sig(), tfs)                    # gate नसेल ⇒ आधीसारखंच
    assert not any(str(a.text).startswith(("SL ", "ENGINE REF")) for a in fig0.layout.annotations)


def test_dry_run_confirmed_replay_picks_last_confirmed_area(monkeypatch):
    import importlib.util
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "paper_dry_run.py")
    spec = importlib.util.spec_from_file_location("paper_dry_run_t", p)
    DR = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(DR)
    monkeypatch.setattr(DR, "last_day_levels", lambda *a, **k: (pd.Timestamp("2001-01-01"), 0, 0, 0, None))
    zones = pd.DataFrame([{"zone_type": "SUPPORT_5M", "zone_low": 990.0, "zone_high": 1000.0, "status": "ACTIVE"},
                          {"zone_type": "RESISTANCE_5M", "zone_low": 1090.0, "zone_high": 1100.0, "status": "ACTIVE"}])
    df, k = _bars(PULL + [TOUCH, SWEEP, BULL_ENGULF])
    from bots_common import level_gate_bot as LGB
    seen = {}

    def cyc(key, sym, tok, st, areas, now):
        seen["key"], seen["now"] = key, now
        return LGB.CycleGate(UP_CTX, df, k, areas, LR.settings())
    area, r = DR.confirmed_replay("dynamic_sr_instant", "tok", "NIFTY", {}, zones_fn=lambda s: zones, cycle_fn=cyc)
    assert area == (990.0, 1000.0) and r["side"] == LR.BULL and seen["key"] == "dynamic_sr_instant"
    area, ctx = DR.confirmed_replay("srv2_momentum_reversal", "tok", "NIFTY", {}, zones_fn=lambda s: zones, cycle_fn=cyc)
    assert area is None                                                     # srv2 areas = 15M/30M/60M ⇒ इथे नाहीत


# ------------------------------------------------------------------------------------------------ a2 / c0 (spec revision) — आरसा जोडी
MIR = 2000.0


def _vbars(rows, vols=None, mirror=False):
    """rows (o, h, l, c) + volumes; mirror ⇒ किंमत p ↦ MIR − p (high / low अदलाबदल) — त्याच निर्णयाची उलट बाजू."""
    df, k = _bars(rows)
    if vols is not None:
        df["volume"] = [100.0] * k + list(vols)
    if mirror:
        o, h, l, c = (MIR - df["open"], MIR - df["low"], MIR - df["high"], MIR - df["close"])
        df["open"], df["high"], df["low"], df["close"] = o, h, l, c
    return df, k


def _mrun(rows, vols=None, mirror=False, others=OTHERS):
    df, k = _vbars(rows, vols, mirror)
    area = (MIR - AREA[1], MIR - AREA[0]) if mirror else AREA
    oth = [(MIR - b, MIR - a) for a, b in others] if mirror else others
    return LR.evaluate(df, area, DOWN_CTX if mirror else UP_CTX, oth, session_start=k)


C1, T1, C2, T2 = (999, 1000, 993, 994), (994, 996, 993, 995), (995, 996, 992, 993.5), (993.5, 998, 993, 997.5)
COMMIT = (997, 1010, 996, 1009)
HAND = PULL + [TOUCH, C1, T1, C2, T2, COMMIT]
HAND_V = [100] * len(PULL) + [120, 150, 80, 60, 110, 250]


@pytest.mark.parametrize("mirror", [False, True])
def test_handover_with_volume_gives_grade_a_and_ticket_lines(mirror):
    r = _mrun(HAND, HAND_V, mirror)
    assert r["state"] == LR.CONFIRMED and r["entry"] and r["side"] == (LR.BEAR if mirror else LR.BULL)
    assert r["grade"] == "A" and r["evidence"]["handover"]
    tw, cw = ("selling", "buying") if mirror else ("buying", "selling")
    assert f"{tw} candles growing" in r["study"] and f"{cw} candles weakening" in r["study"]
    assert r["study"].startswith("inside supply:" if mirror else "inside demand:")
    assert "body" in r["commit_line"] and "× window avg" in r["commit_line"] and "volume 2.4× window avg" in r["commit_line"]
    assert ("bearish" if mirror else "bullish") in r["commit_line"]


@pytest.mark.parametrize("mirror", [False, True])
def test_commitment_on_low_volume_waits(mirror):
    r = _mrun(HAND, HAND_V[:-1] + [90], mirror)
    assert not r["entry"] and r["state"] == LR.ARMED and any(e[2] == LR.R_LOW_VOL for e in r["events"])


@pytest.mark.parametrize("mirror", [False, True])
def test_volume_na_allowed_but_grade_capped_b(mirror):
    r = _mrun(HAND, None, mirror)
    assert r["entry"] and r["grade"] == "B" and "volume: NA" in r["commit_line"] and r["evidence"]["volume_na"]


@pytest.mark.parametrize("mirror", [False, True])
def test_commitment_must_be_dominant(mirror):
    weak = (997, 1001.5, 996.5, 1001.2)                                    # strong close पण body window सरासरी इतकीच ⇒ dominant नाही
    r = _mrun(HAND[:-1] + [weak], HAND_V[:-1] + [250], mirror)
    assert not r["entry"]


@pytest.mark.parametrize("mirror", [False, True])
def test_absorption_blocks_entry_while_it_lasts(mirror):
    a1, a2, a3, a4 = (999, 1000, 997, 998), (998, 999, 997, 998.5), (998.5, 999.5, 991.5, 992.5), (992.5, 993.5, 990.2, 991)
    com = (991, 1004, 990.5, 1003)
    rows = PULL + [TOUCH, a1, a2, a3, a4, com]
    vols = [100] * len(PULL) + [100, 80, 80, 150, 200, 300]
    r = _mrun(rows, vols, mirror)
    assert not r["entry"] and any(e[2] == LR.R_ABSORPTION for e in r["events"])


@pytest.mark.parametrize("mirror", [False, True])
def test_double_bottom_top_named_on_ticket(mirror):
    b1, b2, b3, b4 = (999, 1001, 994, 995), (995.5, 999, 995.3, 997), (997, 998, 994.5, 995.5), (995.5, 999, 995.2, 998)
    com = (998, 1012, 997.5, 1011)
    rows = PULL + [TOUCH, b1, b2, b3, b4, com]
    r = _mrun(rows, [100] * len(PULL) + [100, 100, 90, 90, 90, 300], mirror)
    assert r["entry"], r["events"]
    assert ("double top" if mirror else "double bottom") in r["study"]


def test_futures_volume_attached_by_timestamp_and_na_on_failure():
    from bots_common import level_gate_bot as LGB
    df, k = _bars(PULL)
    df["volume"] = 0.0                                                      # spot volume (0) कधीच वापरत नाही
    fut = pd.DataFrame({"timestamp": df["timestamp"].iloc[-3:].dt.tz_localize("Asia/Kolkata"), "volume": [10.0, 20.0, 30.0]})
    out = LGB.attach_futures_volume(df, "NIFTY", "tok", 5, None, fetch_volume=lambda *a: fut)
    assert list(out["volume"].iloc[-3:]) == [10.0, 20.0, 30.0] and out["volume"].iloc[:-3].isna().all()
    bad = LGB.attach_futures_volume(df, "SENSEX", "tok", 5, None, fetch_volume=lambda *a: None)
    assert bad["volume"].isna().all()

    def boom(*a):
        raise RuntimeError("x")
    assert LGB.attach_futures_volume(df, "NIFTY", "tok", 5, None, fetch_volume=boom)["volume"].isna().all()


@pytest.mark.parametrize("mirror", [False, True])
def test_broken_support_retested_as_resistance_in_down_trend(mirror):
    """review 🟡8 (spec §2 "role may flip"): DOWN trend मध्ये support displacement ने तुटला ⇒ खालून retest = resistance ⇒ bearish चालतो;
    तीच (तुटलेली) bullish भूमिका पुन्हा नाही. आरसा: UP trend मध्ये resistance तुटून support."""
    drive = [(1030, 1031, 1012, 1013), (1013, 1014, 994, 995), (995, 996, 970, 971), (971, 972, 960, 961), (961, 962, 955, 957)]
    rally = [(957, 966, 956, 965), (965, 974, 964, 973), (973, 982, 972, 981), (981, 989, 980, 988)]   # खालून area कडे (शांत)
    rt = [(988, 996, 987, 993), (993, 995, 989, 990), (990, 996, 989, 991), (991, 993, 986.5, 987.2), (987.2, 990, 984, 985)]
    com = (985, 986, 970, 971)                                            # dominant bearish close area खाली
    rows = drive + rally + rt + [com]
    vols = [100] * len(rows)
    vols[-1] = 300
    df, k = _vbars(rows, vols, mirror)
    area = (MIR - AREA[1], MIR - AREA[0]) if mirror else AREA
    others = [(850.0, 860.0)] if not mirror else [(MIR - 860.0, MIR - 850.0)]
    r = LR.evaluate(df, area, UP_CTX if mirror else DOWN_CTX, others, session_start=k)
    assert r["broken"] and any(e[2] == LR.R_BROKEN for e in r["events"])
    assert r["side"] == (LR.BULL if mirror else LR.BEAR) and r["state"] == LR.CONFIRMED and r["entry"], r["events"]
