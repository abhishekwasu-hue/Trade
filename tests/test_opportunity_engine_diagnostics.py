"""tests/test_opportunity_engine_diagnostics.py -- निदान (exit breakdown, MAE/MFE, counterfactual, मोठे losses, funnel, D2) — कृत्रिम, network-free.
निदान फक्त अहवाल: actual mode ने मूळ backtest चा R हुबेहूब परत आला पाहिजे."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from opportunity_engine import backtest as BT
from opportunity_engine import diagnostics as DG
from opportunity_engine import sessions
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import TFState
from opportunity_engine.risk import TradePlan

from tests.test_opportunity_engine_backtest import ScriptedDetector, long_cand, short_cand, walk_1m

DAY = pd.Timestamp("2025-01-08")


# ---- resimulate: actual / counterfactual ----------------------------------------------------------------------------------------------
def fake_day(rows, start="09:30"):
    t0 = DAY + pd.Timedelta(hours=int(start[:2]), minutes=int(start[3:]))
    be = [t0 + pd.Timedelta(minutes=5 * (i + 1)) for i in range(len(rows))]
    a = np.array(rows, dtype=float)
    return SimpleNamespace(be=be, o=a[:, 0], h=a[:, 1], l=a[:, 2], c=a[:, 3], adr=200.0, date=DAY)


class FlatTL:
    def htf_state(self, tf, t):
        return TFState(tf=tf, state="UPTREND")


def plan_long(slip=0.0):
    return TradePlan(direction="LONG", entry=100.0, sl=90.0, t1=110.0, t2=120.0, risk=10.0, slippage=slip)


# entry bar (k=0) नंतर: T1 (111), परत BE (99), मग T2 (121)
PATH = [(100, 100, 100, 100), (100, 111, 101, 108), (108, 109, 99, 100), (100, 115, 95, 114), (114, 121, 113, 120), (120, 120, 119, 119)]


def test_resimulate_actual_vs_no_be_vs_full_position():
    day, cfg = fake_day(PATH), replace(EngineConfig(), primary_htf="4h")
    pos, j = DG.resimulate(FlatTL(), day, 0, plan_long(), "REVERSAL", None, cfg, "actual")
    assert pos.exit_reason == "BE" and j == 2 and pos.r_multiple == pytest.approx(0.5)              # T1 वर अर्धं (0.5R) + BE (0)
    nb, j2 = DG.resimulate(FlatTL(), day, 0, plan_long(), "REVERSAL", None, cfg, "no_be")
    assert nb.exit_reason == "T2" and j2 == 4 and nb.r_multiple == pytest.approx(0.5 * 1 + 0.5 * 2)   # SL मूळ जागी (90) => 95 ला टिकला, T2 गाठलं
    full, _ = DG.resimulate(FlatTL(), day, 0, plan_long(), "REVERSAL", None, cfg, "no_partial_no_be")
    assert full.exit_reason == "T2" and full.r_multiple == pytest.approx(2.0)
    # slippage: प्रत्येक fill वर 1 pt विरुद्ध => SL = −1 − 2/10
    sl_path = [(100, 100, 100, 100), (100, 102, 89, 92)]
    p, _ = DG.resimulate(FlatTL(), fake_day(sl_path), 0, plan_long(slip=1.0), "REVERSAL", None, cfg, "actual")
    assert p.exit_reason == "SL" and p.r_multiple == pytest.approx(-1.2)


def test_excursions_first_touch_and_exit_category():
    day = fake_day(PATH)
    mfe, mae = DG._excursions(day, 1, 2, 100.0, 1, 10.0)
    assert mfe == pytest.approx(1.1) and mae == pytest.approx(0.1)
    assert DG._first_touch(day, 1, 5, 90.0, 120.0, 1) == "TARGET" and DG._first_touch(day, 1, 5, 99.5, 120.0, 1) == "SL"
    assert DG._first_touch(day, 1, 1, 90.0, 130.0, 1) == "NEITHER"
    cat = lambda **kw: DG.exit_category({"exit_reason": "SL", "t1_hit": False, "exit_at_entry": False, **kw})    # noqa: E731
    assert cat() == "SL" and cat(exit_at_entry=True) == "HTF_WEAK→BE" and cat(exit_reason="BE", t1_hit=True) == "T1→BE"
    assert cat(exit_reason="TRAIL_SL", t1_hit=True) == "T1→TRAIL" and cat(exit_reason="T2", t1_hit=True) == "T1→T2"
    assert cat(exit_reason="EOD") == "EOD" and cat(exit_reason="EOD", t1_hit=True) == "T1→EOD" and cat(exit_reason="TIME_STOP") == "TIME_STOP"


# ---- पूर्ण replay वर: actual resim = मूळ trade ----------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def timeline():
    frames = sessions.build_frames(walk_1m(days=70, seed=3))
    bcfg = BT.BacktestConfig(levels_every_day=False, variants=("V1",))
    tl = BT.prepare_timeline(frames, bcfg)
    for tf in BT.HTF:
        tl.states[tf] = [TFState(tf=tf, state="UPTREND", updated_at=t) for t in tl.times[tf]]
    for d in tl.days:
        d.adr = 200.0
    return tl, bcfg


def test_enrich_trades_reproduces_backtest_r_exactly_and_adds_columns(timeline):
    tl, bcfg = timeline
    plan = {(d.date, k): [long_cand] for d in tl.days[15:45] for k in (8, 30)}
    plan.update({(d.date, 9): [short_cand] for d in tl.days[15:45]})
    res = BT.run_variant(tl, "V1", bcfg, detector_factory=lambda e: [ScriptedDetector(plan)])
    assert len(res["trades"]) >= 10 and len(res["virtual"]) >= 10
    x = DG.enrich_trades(tl, res["trades"], "V1", bcfg)
    assert x["resim_match"].all()
    assert {"exit_cat", "mfe_hold_r", "mae_eod_r", "cf_no_be_r", "cf_full_r", "t2_r", "after_be_exit", "bracket_t2", "slip_r"} <= set(x.columns)
    assert (x["mfe_eod_r"] >= x["mfe_hold_r"] - 1e-9).all() and (x["mae_eod_r"] >= x["mae_hold_r"] - 1e-9).all()
    sl = x[x["exit_reason"] == "SL"]
    assert ((sl["r"] - sl["slip_r"] + 1.0).abs() < 1e-6).all()                                       # SL loss = −1R + slippage वाटा, बाकी काही नाही
    v = DG.enrich_trades(tl, res["virtual"], "V1", bcfg)
    assert v["resim_match"].all()


def test_run_diagnostics_end_to_end_and_all_tables_split_is_oos(timeline):
    tl, bcfg = timeline
    plan = {(d.date, k): [long_cand] for d in tl.days[15:40] for k in (8, 30)}
    res = BT.run_variant(tl, "V1", bcfg, detector_factory=lambda e: [ScriptedDetector(plan)])
    out = DG.run_diagnostics(tl, res, "V1", replace(bcfg, detectors=("D1", "D2", "D3")))
    for key in ("A_exit_breakdown", "A_win_composition", "B_mae_mfe", "B_counterfactual", "B_be_followup", "C_loss_size", "C_big_losses", "D_funnel",
                "D_gate_codes", "D_by_year", "E_d2_by_gap_type", "E_d2_time_to_sl", "check_resim"):
        assert key in out
    assert out["check_resim"].iloc[0]["न जुळलेले"] == 0
    for key in ("A_exit_breakdown", "A_win_composition", "B_mae_mfe", "B_counterfactual", "C_loss_size", "D_funnel"):
        assert set(out[key]["period"]) <= set(BT.PERIODS)
    cf = out["B_counterfactual"]
    assert set(cf["नियम"]) == {"actual (सध्याचे नियम)", "BE/trail न हलवता (T1 partial तसाच)", "partial नाही + BE नाही (SL/T2/EOD)"}
    comp = out["A_win_composition"]
    assert (comp["wins"] == comp[["wins_T1→BE", "wins_T1→TRAIL", "wins_T1→T2", "wins_इतर"]].sum(axis=1)).all()


def test_shadow_detection_matches_real_raw_candidates_with_real_detectors():
    """खरे detectors (D1–D3): मूळ-खिडकीतल्या shadow (RR फिल्टर लावून) दिवसांचा संच = backtest मध्ये evaluate ला गेलेल्या candidates चे दिवस."""
    frames = sessions.build_frames(walk_1m(days=60, seed=8))
    bcfg = BT.BacktestConfig(variants=("V1",))
    tl = BT.prepare_timeline(frames, bcfg)
    res = BT.run_variant(tl, "V1", bcfg)
    days, shadow = DG.shadow_detect(tl, "V1", bcfg)
    assert len(days) == len(tl.days)
    f = DG.funnel(res["decisions"], days, shadow, bcfg, "V1")
    notes = f[f["टप्पा"].str.startswith("5.")]["टीप"]
    assert notes.str.contains("तफावत: 0 दिवस").all()
    if len(shadow):
        o = shadow[(shadow["source"] == "orig") & shadow["in_window"] & shadow["passes_filter"]]
        assert set(zip(o["date"], o["setup"])) == set(zip(res["decisions"]["date"], res["decisions"]["setup"])) if len(res["decisions"]) else o.empty


# ---- funnel / तक्ते (हाताने बनवलेला डेटा) ---------------------------------------------------------------------------------------------
def test_funnel_counts_furthest_stage_per_day_and_reasons():
    d1, d2, d3 = pd.Timestamp("2018-01-02"), pd.Timestamp("2018-01-03"), pd.Timestamp("2023-01-04")
    days = pd.DataFrame([{"date": d, "gap_type": "COMMON", "gap_dir": 1, "gap_pct": 0.3, "has_gap_zone": False, "gap_fill_time": None} for d in (d1, d2, d3)])
    t = lambda d, hm: d + pd.Timedelta(hours=int(hm[:2]), minutes=int(hm[3:]))   # noqa: E731
    shadow = pd.DataFrame([
        {"source": "orig", "date": d1, "time": t(d1, "10:00"), "setup": "D2", "in_window": True, "passes_filter": True},
        {"source": "orig", "date": d2, "time": t(d2, "10:00"), "setup": "D2", "in_window": True, "passes_filter": True},
        {"source": "wide", "date": d1, "time": t(d1, "10:00"), "setup": "D2", "in_window": True, "passes_filter": True},
        {"source": "wide", "date": d2, "time": t(d2, "10:00"), "setup": "D2", "in_window": True, "passes_filter": True},
        {"source": "wide", "date": d2, "time": t(d2, "13:00"), "setup": "D2", "in_window": False, "passes_filter": True},
        {"source": "wide", "date": d3, "time": t(d3, "13:00"), "setup": "D2", "in_window": False, "passes_filter": True}])
    dec = pd.DataFrame([
        {"date": d1, "time": t(d1, "10:00"), "setup": "D2", "status": "REJECTED_GATE", "gate_codes": "NO_TRADE", "reasons": "x"},
        {"date": d1, "time": t(d1, "10:05"), "setup": "D2", "status": "TAKEN", "gate_codes": "", "reasons": ""},
        {"date": d2, "time": t(d2, "10:00"), "setup": "D2", "status": "REJECTED_GATE", "gate_codes": "HTF_MISALIGNED,DAILY_VETO_A", "reasons": "x"}])
    bcfg = BT.BacktestConfig(detectors=("D2",))
    f = DG.funnel(dec, days, shadow, bcfg, "V1").set_index(["period", "setup", "टप्पा"])
    IS, OOS = BT.PERIODS
    assert f.loc[(IS, "D2", "2. पूर्वअट"), "दिवस"] == 2 and f.loc[(OOS, "D2", "3. trigger (कधीही, shadow)"), "दिवस"] == 1
    assert f.loc[(OOS, "D2", "4. trigger वेळ-खिडकीत"), "दिवस"] == 0
    assert f.loc[(IS, "D2", "6. शेवटचा टप्पा: घेतलेले"), "दिवस"] == 1 and f.loc[(IS, "D2", "6. शेवटचा टप्पा: Gate reject"), "दिवस"] == 1
    assert f.loc[(IS, "D2", "6. शेवटचा टप्पा: Gate reject"), "candidates"] == 2 and f.loc[(IS, "D2", "   └ HTF_MISALIGNED"), "दिवस"] == 1
    g = DG.gate_code_counts(dec).set_index("code")
    assert g.loc["HTF_MISALIGNED", "candidates"] == 1 and g.loc["DAILY_VETO_A", "candidates"] == 1 and g.loc["NO_TRADE", "candidates"] == 1
    y = DG.funnel_by_year(dec, days, pd.DataFrame([{"date": d1, "setup": "D2"}]), bcfg).set_index("वर्ष")
    assert y.loc[2018, "raw-candidate दिवस"] == 2 and y.loc[2018, "घेतलेले trades"] == 1 and y.loc[2023, "period"] == OOS


def enriched(rows):
    base = {"variant": "V1", "direction": "LONG", "entry": 100.0, "sl": 90.0, "risk": 10.0, "risk_pts": 10.0, "risk_adr": 0.05, "t1_hit": False, "t2_r": 2.0,
            "bars": 3, "gap_type": "COMMON", "bias": "LONG_ONLY", "exit_at_entry": False, "gap_through": False, "exit_price": 90.0, "slip_r": -0.2, "r_no_slip": -1.0,
            "mfe_hold_r": 0.5, "mae_hold_r": 1.0, "mfe_eod_r": 0.5, "mae_eod_r": 1.0, "bracket_t1": "SL", "bracket_t2": "SL", "after_be_exit": "—",
            "cf_no_be_r": -1.2, "cf_full_r": -1.2}
    out = []
    for d, setup, reason, r, mins, extra in rows:
        e = pd.Timestamp(d) + pd.Timedelta(hours=10)
        out.append({**base, "date": pd.Timestamp(d), "setup": setup, "exit_reason": reason, "r": r, "entry_time": e, "exit_time": e + pd.Timedelta(minutes=mins), "minutes_held": mins, **extra})
    df = pd.DataFrame(out)
    df["exit_cat"] = df.apply(DG.exit_category, axis=1)
    return df


def test_big_losses_causes_and_d2_report_time_to_sl():
    x = enriched([("2019-01-02", "D2", "SL", -1.2, 5, {}), ("2019-02-04", "D2", "SL", -1.2, 40, {"gap_through": True}),
                  ("2023-03-01", "D2", "BE", 0.4, 30, {"t1_hit": True, "after_be_exit": "T2 गाठलं"}), ("2023-03-02", "D2", "SL", -1.3, 200, {"r_no_slip": -1.1})])
    b = DG.big_losses(x)
    assert len(b) == 3 and b.iloc[0]["कारण"].startswith("फक्त slippage") and "पलीकडे उघडला" in b.iloc[1]["कारण"] and "तपासा" in b.iloc[2]["कारण"]
    rep = DG.d2_report(x)
    tts = rep["time_to_sl"].set_index("period")
    assert tts.loc[BT.PERIODS[0], "SL_trades"] == 2 and tts.loc[BT.PERIODS[0], "≤5 मि"] == 1 and tts.loc[BT.PERIODS[0], "31–60 मि"] == 1
    assert tts.loc[BT.PERIODS[1], ">120 मि"] == 1
    assert set(rep["by_gap_type"]["period"]) == set(BT.PERIODS)
    fu = DG.be_followup(x)
    assert fu.iloc[0]["नंतर T2 गाठलं"] == 1 and fu.iloc[0]["period"] == BT.PERIODS[1]
    ls = DG.loss_size_summary(x).set_index("period")
    assert ls.loc[BT.PERIODS[0], "<-1R_losses"] == 2 and ls.loc[BT.PERIODS[0], "gap_through"] == 1
    assert DG.big_losses(pd.DataFrame()).empty and DG.d2_report(pd.DataFrame())["time_to_sl"].empty


def test_breakdown_split_is_oos_in_backtest_tables():
    t = enriched([("2018-01-02", "D1", "SL", -1.2, 5, {}), ("2022-05-02", "D1", "T2", 1.8, 50, {"t1_hit": True})])
    t["r_weighted"] = t["r"]
    b = BT.breakdown_split(t, "setup")
    assert list(b["period"]) == list(BT.PERIODS) and list(b.columns[:2]) == ["period", "setup"]
    assert BT.breakdown_split(pd.DataFrame(), "setup").empty
