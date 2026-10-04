"""tests/test_opportunity_engine_backtest.py -- D1–D3 gap detectors, gap classification, backtest replay (entry/exit/virtual/limits), no-lookahead, analytics; कृत्रिम, network-free."""
import numpy as np
import pandas as pd
import pytest

from opportunity_engine import backtest as BT
from opportunity_engine import sessions
from opportunity_engine.bias import resolve_bias
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import Context, TFState
from opportunity_engine.detectors import gap as G
from opportunity_engine.detectors.base import Candidate, Detector

CFG = EngineConfig()
DAY = pd.Timestamp("2025-01-08")


def ctx_of(states=None, levels=(), price=24100.0, adr=200.0, extra=None):
    states = states or {"1d": "UPTREND", "4h": "UPTREND", "1h": "UPTREND"}
    extra = extra or {}
    tfs = {tf: TFState(tf=tf, state=st, updated_at=DAY, **extra.get(tf, {})) for tf, st in states.items()}
    return Context(time=DAY, price=price, states=tfs, levels=list(levels), adr=adr)


def info_of(open_=24100.0, pdc=24000.0, pdh=24050.0, pdl=23900.0, c3=23700.0, adr=200.0, **kw):
    return G.DayInfo(date=DAY, open=open_, pdc=pdc, pdh=pdh, pdl=pdl, close_3d_ago=c3, adr=adr, **kw)


def bars(rows, start="09:15", freq=5):
    """rows = [(o, h, l, c)] -> 5M DataFrame (bar_end सह)."""
    t0 = DAY + pd.Timedelta(hours=int(start[:2]), minutes=int(start[3:]))
    out = []
    for i, (o, h, l, c) in enumerate(rows):
        s = t0 + pd.Timedelta(minutes=freq * i)
        out.append({"timestamp": s, "bar_start": s, "bar_end": s + pd.Timedelta(minutes=freq), "open": float(o), "high": float(h), "low": float(l), "close": float(c)})
    return pd.DataFrame(out)


def zone(kind, low, high, tf="1d", grade="A", freshness="FRESH", source="", **kw):
    return {"kind": kind, "low": low, "high": high, "core_low": low, "core_high": high, "tf": tf, "quality_grade": grade, "freshness": freshness, "source": source,
            "status": "ACTIVE", "reject_reason": None, "level_id": f"{kind}{low}", **kw}


# ---- gap classification ----------------------------------------------------------------------------------------------------------------
def bias_of(ctx):
    return resolve_bias(ctx, CFG)


def test_gap_small_is_first_in_order():
    info = info_of(open_=24040.0)                                              # +0.17%
    kind, d = G.classify_gap(info, ctx_of(), bias_of(ctx_of()), CFG)
    assert kind == G.SMALL and info.gap_type == G.SMALL and d["gap_pct"] == pytest.approx(0.1667, abs=1e-3)


def test_gap_exhaustion_by_zone_or_by_three_day_overextension():
    z = zone("SUPPLY", 24090.0, 24130.0, tf="4h")                              # gap-up ने open strong supply मध्ये
    ctx = ctx_of(levels=[z])
    assert G.classify_gap(info_of(), ctx, bias_of(ctx), CFG)[0] == G.EXHAUSTION
    far = zone("SUPPLY", 24500.0, 24530.0)
    ctx2 = ctx_of(levels=[far])
    assert G.classify_gap(info_of(), ctx2, bias_of(ctx2), CFG)[0] != G.EXHAUSTION
    over = info_of(c3=23400.0)                                                 # 3 दिवसांत 600 pts = 3×ADR(200) ≥ 2.5×ADR
    assert G.classify_gap(over, ctx2, bias_of(ctx2), CFG)[0] == G.EXHAUSTION
    down = info_of(open_=23850.0, pdh=24050.0, pdl=23900.0, c3=24600.0)        # gap-down, तीन दिवस घसरण
    assert G.classify_gap(down, ctx2, bias_of(ctx2), CFG)[0] == G.EXHAUSTION


def test_gap_breakaway_runaway_common():
    ctx = ctx_of()                                                              # bias LONG_ONLY (direction +1)
    runaway = info_of(open_=24100.0, pdh=24050.0)                               # PDH पलीकडे, level ओलांडलेला नाही
    assert G.classify_gap(runaway, ctx, bias_of(ctx), CFG)[0] == G.RUNAWAY
    crossed = ctx_of(extra={"4h": {"last_sh": 24060.0}})                        # PDC→open दरम्यान HTF swing high
    assert G.classify_gap(info_of(), crossed, bias_of(crossed), CFG)[0] == G.BREAKAWAY
    zone_cross = ctx_of(levels=[zone("DEMAND", 24060.0, 24070.0, tf="1h", grade="B", freshness="TESTED_1")])
    assert G.classify_gap(info_of(), zone_cross, bias_of(zone_cross), CFG)[0] == G.BREAKAWAY
    inside = info_of(open_=24040.0 + 40.0, pdh=24200.0)                         # PDH च्या आत => COMMON
    assert G.classify_gap(inside, ctx, bias_of(ctx), CFG)[0] == G.COMMON
    counter = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"})
    assert G.classify_gap(info_of(), counter, bias_of(counter), CFG)[0] == G.COMMON     # bias विरुद्ध


# ---- D1 --------------------------------------------------------------------------------------------------------------------------------
def d1_bars(extra):
    return bars([(24100, 24130, 24095, 24120), (24120, 24140, 24110, 24135), (24135, 24150, 24125, 24140)] + extra)       # OR: 24095–24150


def info_go(**kw):
    i = info_of(**kw)
    G.classify_gap(i, ctx_of(), bias_of(ctx_of()), CFG)
    i.gap_type = G.BREAKAWAY
    return i


def run_detector(det, info, df5, ctx=None, df15=None, state=None, rr5=10.0, rr15=25.0):
    ctx = ctx or ctx_of()
    b = {"5m": df5, "15m": df15 if df15 is not None else df5.iloc[0:0], "info": info, "state": state if state is not None else {}, "rr5": rr5, "rr15": rr15}
    return det.detect(ctx, b, bias_of(ctx), df5["bar_end"].iloc[-1])


def test_d1_entry_after_or_with_mid_or_opposite_sl_and_window():
    det = G.GapGo(CFG)
    info = info_go()
    c = run_detector(det, info, d1_bars([(24140, 24165, 24138, 24160)]))
    assert len(c) == 1 and c[0].setup_id == "D1" and c[0].direction == "LONG" and c[0].kind == "BREAKOUT"
    assert c[0].trigger["level"] == 24150.0 and c[0].sl_ref == pytest.approx((24150 + 24095) / 2) and c[0].entry == 24160.0 and c[0].setup_quality == 80.0
    assert run_detector(det, info, d1_bars([(24140, 24148, 24130, 24145)])) == []              # OR high च्या आत close
    assert run_detector(det, info, bars([(24100, 24130, 24095, 24120)] * 3)) == []             # OR पूर्ण नाही (नंतरचा bar नाही)
    opp = G.GapGo(EngineConfig(d1_sl_mode="opposite"))
    assert run_detector(opp, info, d1_bars([(24140, 24165, 24138, 24160)]))[0].sl_ref == 24095.0
    late = bars([(24100, 24130, 24095, 24120)] * 3 + [(24140, 24165, 24138, 24160)], start="11:00")
    assert run_detector(det, info, late) == []                                                 # window (11:00) नंतर
    runaway = info_go()
    runaway.gap_type = G.RUNAWAY
    assert run_detector(det, runaway, d1_bars([(24140, 24165, 24138, 24160)]))[0].setup_quality == 65.0
    common = info_go()
    common.gap_type = G.COMMON
    assert run_detector(det, common, d1_bars([(24140, 24165, 24138, 24160)])) == []


def test_d1_short_for_gap_down():
    info = info_of(open_=23850.0, pdc=24000.0, pdh=24050.0, pdl=23900.0)
    info.gap_dir, info.gap_pct, info.gap_type = -1, -0.625, G.BREAKAWAY
    df = bars([(23850, 23860, 23820, 23830), (23830, 23840, 23800, 23810), (23810, 23830, 23790, 23800), (23800, 23805, 23770, 23775)])      # OR low 23790
    c = run_detector(G.GapGo(CFG), info, df, ctx=ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}))
    assert len(c) == 1 and c[0].direction == "SHORT" and c[0].trigger["level"] == 23790.0


# ---- D2 --------------------------------------------------------------------------------------------------------------------------------
def d2_info():
    i = info_of(open_=24100.0, pdc=24000.0, pdh=24300.0, pdl=23900.0)
    i.gap_dir, i.gap_pct, i.gap_type = 1, 0.4167, G.COMMON
    return i


FADE_BASE = [(24100, 24120, 24095, 24115), (24115, 24130, 24105, 24125), (24125, 24135, 24110, 24130), (24130, 24140, 24120, 24128)]


def test_d2_fade_trigger_target_pdc_and_rr_filter():
    det = G.GapFade(CFG)
    info = d2_info()
    engulf = FADE_BASE + [(24132, 24135, 24100, 24102)]                                        # bearish engulfing (prev bullish? prev close 24128 < open 24130 => bearish) 
    prev_bull = FADE_BASE[:3] + [(24128, 24140, 24125, 24138)] + [(24140, 24141, 24105, 24110)]
    c = run_detector(det, info, bars(prev_bull))
    assert len(c) == 1 and c[0].direction == "SHORT" and c[0].kind == "REVERSAL" and c[0].targets_hint == [24000.0]
    assert c[0].sl_ref == 24141.0 and c[0].meta["pattern"] in ("BEARISH_ENGULFING", "EVENING_STAR", "SHOOTING_STAR")
    # RR < 1.5: entry 24110, SL 24141 (risk 31) => PDC 24000 पर्यंत 110/31=3.5 ठीक; SL खूप दूर केल्यास वगळा
    far = FADE_BASE[:3] + [(24128, 24300, 24125, 24138)] + [(24140, 24301, 24105, 24110)]
    assert run_detector(det, info, bars(far)) == []
    assert run_detector(det, info, bars(FADE_BASE)) == []                                      # pattern नाही
    assert run_detector(G.GapFade(CFG), info_go(), bars(prev_bull)) == []                      # BREAKAWAY gap वर fade नाही


def test_d2_cancelled_once_gap_is_filled_and_window():
    det, info, state = G.GapFade(CFG), d2_info(), {}
    filled = FADE_BASE[:3] + [(24128, 24140, 23990, 24138)] + [(24140, 24141, 24105, 24110)]    # low ≤ PDC => gap भरला
    assert run_detector(det, info, bars(filled), state=state) == [] and state.get("d2_cancelled")
    later = FADE_BASE[:3] + [(24128, 24140, 24125, 24138)] + [(24140, 24141, 24105, 24110)]
    assert run_detector(det, info, bars(later), state=state) == []                             # एकदा रद्द => पुढेही नाही
    assert run_detector(det, d2_info(), bars(later, start="12:00")) == []                      # window नंतर


def test_d2_long_fade_for_gap_down():
    info = info_of(open_=23900.0, pdc=24000.0, pdh=24100.0, pdl=23800.0)
    info.gap_dir, info.gap_pct, info.gap_type = -1, -0.4167, G.SMALL
    rows = [(23900, 23905, 23880, 23885), (23885, 23890, 23870, 23875), (23875, 23880, 23860, 23865), (23865, 23870, 23850, 23860), (23858, 23880, 23820, 23860 - 0.5), (23856, 23885, 23815, 23880)]
    c = run_detector(G.GapFade(CFG), info, bars(rows))
    assert all(x.direction == "LONG" for x in c)


# ---- D3 --------------------------------------------------------------------------------------------------------------------------------
GAP_UP = {"kind": "GAP", "source": "GAP_UP", "low": 24000.0, "high": 24050.0, "gap_status": "UNFILLED", "level_id": "g1", "tf": "1d", "formed_at": DAY - pd.Timedelta(days=3),
          "quality_grade": "B", "mtf_count": 2, "freshness": "FRESH", "status": "ACTIVE", "core_low": 24000.0, "core_high": 24050.0, "reject_reason": None}


def d3_frames(break_close=24072.0):
    d5 = bars([(24090, 24095, 24085, 24088), (24088, 24090, 24070, 24075), (24075, 24078, 24055, 24060),
               (24060, 24061.4, 24040, 24061), (24061, 24080, 24060, break_close)], start="10:00")                  # hammer (24040) + तोड
    d15 = bars([(24110, 24115, 24080, 24090), (24090, 24095, 24040, 24060)], start="09:30", freq=15)                # retest: low 24040 ≤ zone.high; close ≥ 24000
    return d5, d15


def test_d3_retest_reversal_long_with_sl_beyond_far_edge_and_single_use():
    det, state = G.GapRetestReversal(CFG), {}
    d5, d15 = d3_frames()
    ctx = ctx_of(levels=[GAP_UP], price=24072.0)
    c = run_detector(det, info_of(), d5, ctx=ctx, df15=d15, state=state, rr5=10.0, rr15=25.0)
    assert len(c) == 1 and c[0].setup_id == "D3" and c[0].direction == "LONG" and c[0].zone["level_id"] == "g1"
    assert c[0].sl_ref == pytest.approx(24000.0 - 0.1 * 25.0) and c[0].entry == 24072.0 and c[0].setup_quality >= 70
    assert run_detector(det, info_of(), d5, ctx=ctx, df15=d15, state=state) == []              # एका gap साठी दिवसातून एकदाच


def test_d3_needs_retest_trigger_break_and_dies_on_15m_close_through_far_edge():
    det = G.GapRetestReversal(CFG)
    d5, d15 = d3_frames()
    ctx = ctx_of(levels=[GAP_UP], price=24072.0)
    no_break = d3_frames(break_close=24058.0)
    assert run_detector(det, info_of(), no_break[0], ctx=ctx, df15=no_break[1]) == []
    no_touch = bars([(24110, 24115, 24100, 24112), (24112, 24120, 24105, 24118)], start="09:30", freq=15)
    assert run_detector(det, info_of(), d5, ctx=ctx, df15=no_touch) == []
    state = {}
    through = bars([(24110, 24115, 24080, 24090), (24090, 24095, 23980, 23990)], start="09:30", freq=15)         # 15M close 23990 < 24000
    assert run_detector(det, info_of(), d5, ctx=ctx, df15=through, state=state) == [] and "g1" in state["d3_dead"]
    filled = dict(GAP_UP, gap_status="FILLED")
    assert run_detector(det, info_of(), d5, ctx=ctx_of(levels=[filled], price=24072.0), df15=d15) == []
    early = bars([(24090, 24095, 24085, 24088)] * 5, start="09:15")
    assert run_detector(det, info_of(), early, ctx=ctx, df15=d15) == []                        # 09:45 आधी नाही


def test_d3_short_for_down_gap_resistance():
    gap_dn = dict(GAP_UP, source="GAP_DOWN", level_id="g2", low=24100.0, high=24150.0)
    d5 = bars([(24060, 24065, 24052, 24058), (24058, 24075, 24055, 24072), (24072, 24095, 24070, 24092),
               (24090, 24112, 24090, 24090.8), (24090.8, 24092, 24066, 24068)], start="10:00")                 # shooting star (24112) नंतर तोड (close 24068 < 24090)
    d15 = bars([(24060, 24070, 24055, 24068), (24068, 24112, 24066, 24090)], start="09:30", freq=15)
    ctx = ctx_of({"1d": "DOWNTREND", "4h": "DOWNTREND", "1h": "DOWNTREND"}, levels=[gap_dn], price=24068.0)
    c = run_detector(G.GapRetestReversal(CFG), info_of(), d5, ctx=ctx, df15=d15, rr15=20.0)
    assert len(c) == 1 and c[0].direction == "SHORT" and c[0].sl_ref == pytest.approx(24150.0 + 0.1 * 20.0)


# ---- backtest replay ------------------------------------------------------------------------------------------------------------------------
def walk_1m(days=70, seed=3, start="2024-01-01"):
    rng = np.random.default_rng(seed)
    ds = pd.bdate_range(start, periods=days)
    ts = pd.DatetimeIndex([d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=m) for d in ds for m in range(375)])
    close = 22000 + np.cumsum(rng.normal(0, 3.0, len(ts))) + 150 * np.sin(np.arange(len(ts)) / 800.0)
    return pd.DataFrame({"timestamp": ts, "open": close - 0.5, "high": close + 2.0, "low": close - 2.0, "close": close, "volume": 0})


class ScriptedDetector(Detector):
    """ठराविक दिवशी/bar वर ठरवलेले candidates (फक्त मागच्या डेटावरून — no-lookahead)."""
    def __init__(self, plan):
        super().__init__()
        self.plan = plan                                            # {(date, k): [Candidate factory]}

    def detect(self, ctx, bars_by_tf, bias, now):
        k = len(bars_by_tf["5m"]) - 1
        day = bars_by_tf["info"].date
        out = []
        for make in self.plan.get((day, k), []):
            out.append(make(bars_by_tf["5m"].iloc[-1], now))
        return out


def long_cand(row, now, setup="D6", quality=100.0):
    c = float(row["close"])
    return Candidate(setup_id=setup, direction="LONG", time=now, entry=c, sl_ref=c - 25.0, kind="PULLBACK_END", tf="15m", setup_quality=quality,
                     trigger={"open": 100.0, "high": 110.0, "low": 80.0, "close": 108.0, "prev_high": 105.0, "prev_low": 90.0, "ref_range": 10.0})


def short_cand(row, now):
    c = float(row["close"])
    return Candidate(setup_id="D6", direction="SHORT", time=now, entry=c, sl_ref=c + 25.0, kind="PULLBACK_END", tf="15m", setup_quality=100.0,
                     trigger={"open": 100.0, "high": 120.0, "low": 92.0, "close": 94.0, "prev_high": 110.0, "prev_low": 95.0, "ref_range": 10.0})


@pytest.fixture(scope="module")
def timeline():
    frames = sessions.build_frames(walk_1m())
    bcfg = BT.BacktestConfig(levels_every_day=False, variants=("V1",))
    tl = BT.prepare_timeline(frames, bcfg)
    for tf in BT.HTF:                                              # gate पास व्हावं म्हणून सर्व HTF UPTREND (बनावट, फक्त replay यंत्रणा तपासायला)
        tl.states[tf] = [TFState(tf=tf, state="UPTREND", updated_at=t) for t in tl.times[tf]]
    for d in tl.days:
        d.adr = 200.0
    return tl, bcfg


def test_replay_enters_at_trigger_close_manages_exit_and_drops_second_candidate(timeline):
    tl, bcfg = timeline
    day = tl.days[20]
    plan = {(day.date, 10): [long_cand, short_cand], (day.date, 12): [long_cand]}
    res = BT.run_variant(tl, "V1", bcfg, detector_factory=lambda ecfg: [ScriptedDetector(plan)])
    tr, virt, dec = res["trades"], res["virtual"], res["decisions"]
    assert len(tr) == 1 and tr.iloc[0]["setup"] == "D6" and tr.iloc[0]["date"] == day.date
    t = tr.iloc[0]
    assert t["entry"] == pytest.approx(day.c[10]) and t["exit_time"] >= t["entry_time"] and t["exit_reason"] in ("SL", "BE", "T2", "TIME_STOP", "EOD", "EOD_DATA", "FAILED_BREAKOUT", "HTF_WEAK")
    assert t["size_factor"] in (0.5, 1.0) and t["r_weighted"] == pytest.approx(t["r"] * t["size_factor"]) and t["state_1d"] == "UPTREND" and t["bias"] == "LONG_ONLY"
    statuses = dec.groupby(["setup", "direction", "status"]).size().to_dict() if len(dec) else {}
    assert ("D6", "SHORT", "REJECTED_GATE") in statuses and statuses.get(("D6", "LONG", "DROPPED"), 0) + statuses.get(("D6", "LONG", "TAKEN"), 0) == 2
    # counter-trend SHORT => virtual (size 0)
    assert len(virt) == 1 and virt.iloc[0]["virtual"] and virt.iloc[0]["size_factor"] == 0.0 and "HTF_MISALIGNED" in virt.iloc[0]["gate_codes"] and virt.iloc[0]["r_weighted"] == 0.0


def test_replay_day_limits_two_trades_cooldown_and_eod(timeline):
    tl, bcfg = timeline
    day = tl.days[25]
    plan = {(day.date, k): [long_cand] for k in (5, 40, 60, 70)}
    res = BT.run_variant(tl, "V1", bcfg, detector_factory=lambda ecfg: [ScriptedDetector(plan)])
    tr = res["trades"]
    assert len(tr) <= 2 and (tr["date"] == day.date).all()
    assert (pd.to_datetime(tr["exit_time"]).dt.strftime("%H:%M") <= "15:30").all()


def test_no_trade_when_detectors_are_empty_and_schema_is_stable(timeline):
    tl, bcfg = timeline
    res = BT.run_variant(tl, "V1", bcfg, detector_factory=lambda e: [])
    assert res["trades"].empty and res["virtual"].empty and res["decisions"].empty


def test_replay_is_deterministic_and_variants_use_different_config(timeline):
    tl, bcfg = timeline
    day = tl.days[22]
    plan = {(day.date, 10): [long_cand]}
    fac = lambda e: [ScriptedDetector(plan)]
    a = BT.run_variant(tl, "V1", bcfg, detector_factory=fac)
    b = BT.run_variant(tl, "V1", bcfg, detector_factory=fac)
    pd.testing.assert_frame_equal(a["trades"], b["trades"])
    v2 = BT.run_variant(tl, "V2", bcfg, detector_factory=fac)
    assert BT.VARIANTS["V2"]["primary_htf"] == "1d" and len(v2["decisions"]) == len(a["decisions"])


def test_future_data_never_changes_past_decisions_real_detectors():
    """अर्धा डेटा कापून चालवला तरी, कापलेल्या दिवसाआधीचे decisions/trades पूर्ण-डेटा चालवल्यासारखेच (timeline + levels + HTF states no-lookahead)."""
    one_m = walk_1m(days=90, seed=11)
    cut_day = pd.bdate_range("2024-01-01", periods=90)[60]
    full = sessions.build_frames(one_m)
    part = sessions.build_frames(one_m[one_m["timestamp"] < cut_day])
    bcfg = BT.BacktestConfig(variants=("V1",))

    def decisions(frames):
        tl = BT.prepare_timeline(frames, bcfg)
        for d in tl.days:
            d.adr = 200.0
        # असे detector जे रोज bar 10 वर LONG candidate देतात (फक्त मागच्या bars वरून) => gate/score/validation वर HTF context आणि levels चा परिणाम दिसतो
        plan = {(d.date, 10): [long_cand] for d in tl.days}
        return BT.run_variant(tl, "V1", bcfg, detector_factory=lambda e: [ScriptedDetector(plan)])

    a, b = decisions(full), decisions(part)
    lim = cut_day - pd.Timedelta(days=2)
    for key in ("decisions", "trades"):
        x = a[key][pd.to_datetime(a[key]["date"]) < lim].reset_index(drop=True) if len(a[key]) else a[key]
        y = b[key][pd.to_datetime(b[key]["date"]) < lim].reset_index(drop=True) if len(b[key]) else b[key]
        cols = [c for c in ("date", "setup", "status", "score", "gate_codes", "bias", "entry", "r", "exit_reason") if c in x.columns]
        pd.testing.assert_frame_equal(x[cols], y[cols], check_dtype=False)
    assert len(a["decisions"]) > 20


# ---- analytics --------------------------------------------------------------------------------------------------------------------------------
def trades_df():
    rows = []
    for i, (d, setup, r, w, bias, st) in enumerate([
        ("2018-03-01", "D1", 1.0, 1.0, "LONG_ONLY", "UPTREND"), ("2019-05-01", "D1", -1.0, 0.5, "LONG_ONLY", "UPTREND"), ("2020-02-01", "D2", 0.5, 1.0, "SHORT_ONLY", "DOWNTREND"),
        ("2022-02-01", "D3", 2.0, 1.0, "LONG_ONLY", "UPTREND"), ("2022-06-01", "D3", -1.0, 1.0, "LONG_ONLY", "RANGE"), ("2023-01-01", "D3", 1.5, 0.5, "LONG_ONLY", "UPTREND")]):
        rows.append({"date": pd.Timestamp(d), "entry_time": pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=45 + 20 * i), "exit_time": pd.Timestamp(d) + pd.Timedelta(hours=11), "setup": setup,
                     "r": r, "size_factor": w, "r_weighted": r * w, "score": 62.0 + 4 * i, "bias": bias, "state_1d": st, "gap_type": "COMMON", "exit_reason": "T2" if r > 0 else "SL", "variant": "V1", "direction": "LONG"})
    return pd.DataFrame(rows)


def test_summarize_metrics_and_empty_cases():
    s = BT.summarize(trades_df(), "r")
    assert s["trades"] == 6 and s["win_pct"] == pytest.approx(66.7, abs=0.1) and s["expectancy_r"] == pytest.approx(0.5) and s["total_r"] == 3.0
    assert s["profit_factor"] == pytest.approx(5.0 / 2.0) and s["max_dd_r"] == 1.0
    assert BT.summarize(pd.DataFrame())["trades"] == 0 and BT.summarize(None)["expectancy_r"] is None
    assert BT.summarize(trades_df().iloc[[0]], "r")["profit_factor"] is None


def test_is_oos_split_breakdowns_and_verdicts():
    is_t, oos_t = BT.split_is_oos(trades_df())
    assert len(is_t) == 3 and len(oos_t) == 3
    by_year = BT.breakdown(trades_df(), "year")
    assert list(by_year["year"]) == [2018, 2019, 2020, 2022, 2023]
    assert set(BT.breakdown(trades_df(), "setup")["setup"]) == {"D1", "D2", "D3"} and len(BT.breakdown(trades_df(), "tod")) >= 2
    assert set(BT.breakdown(trades_df(), "score_bucket")["score_bucket"]) <= {"<60", "60-74", "75+"}
    v = BT.verdicts(trades_df(), min_oos=3).set_index("setup")
    assert v.loc["D3", "verdict"] == "KEEP" and v.loc["D1", "verdict"] == "REVIEW" and v.loc["D2", "oos_trades"] == 0
    assert BT.verdicts(trades_df()).set_index("setup").loc["D3", "verdict"] == "REVIEW"           # डीफॉल्ट: OOS < 30 trades
    assert BT.breakdown(pd.DataFrame(), "setup").empty and BT.verdicts(pd.DataFrame()).empty


def test_aligned_vs_counter_and_variant_comparison():
    virtual = trades_df().iloc[:3].assign(gate_codes=["HTF_MISALIGNED", "HTF_MISALIGNED,DAILY_VETO_A", "NO_ROOM"], virtual=True, size_factor=0.0)
    table = BT.aligned_vs_counter(trades_df(), virtual).set_index("गट")
    assert table.loc["aligned (घेतलेले)", "trades"] == 6
    assert table.loc["counter-trend (HTF_MISALIGNED, नाकारलेले)", "trades"] == 2 and table.loc["इतर gate-rejected (veto/room/protected…)", "trades"] == 1
    assert len(BT.aligned_vs_counter(trades_df(), pd.DataFrame())) == 1
    r1 = {"trades": trades_df(), "virtual": virtual, "decisions": pd.DataFrame()}
    r2 = {"trades": trades_df().iloc[:4], "virtual": pd.DataFrame(), "decisions": pd.DataFrame()}
    comp = BT.compare_variants({"V1": r1, "V3": r2}).set_index("variant")
    assert comp.loc["V1", "trades"] == 6 and comp.loc["V3", "trades"] == 4
    assert comp.loc["V3", "इतर variants ने घेतलेले (हिने नाही) trades"] == 2 and comp.loc["V1", "इतर variants ने घेतलेले (हिने नाही) trades"] == 0
    assert pd.notna(comp.loc["V3", "त्यांचा expectancy_r"]) and pd.isna(comp.loc["V1", "त्यांचा expectancy_r"])
    assert set(comp.columns) >= {"IS_trades", "OOS_trades", "OOS_expectancy_r", "वर्णन"}


def test_run_backtest_end_to_end_on_synthetic_data_returns_all_tables():
    frames = sessions.build_frames(walk_1m(days=45, seed=5))
    res = BT.run_backtest(frames, BT.BacktestConfig(variants=("V1", "V3"), levels_every_day=False))
    assert set(res.results) == {"V1", "V3"} and set(res.comparison["variant"]) == {"V1", "V3"}
    t = res.tables("V1")
    assert {"summary", "verdicts", "aligned_vs_counter", "by_setup", "by_year", "by_exit_reason"} <= set(t) and len(t["summary"]) == 3
    for r in res.results.values():
        assert set(r) == {"trades", "virtual", "decisions"}


def test_counterfactual_keeps_only_the_first_gate_rejected_signal_per_setup_and_direction(timeline):
    tl, bcfg = timeline
    day = tl.days[30]
    plan = {(day.date, k): [short_cand] for k in (10, 11, 12, 14)}                    # counter-trend SHORT वारंवार (सलग bars)
    res = BT.run_variant(tl, "V1", bcfg, detector_factory=lambda ecfg: [ScriptedDetector(plan)])
    assert (res["decisions"]["status"] == "REJECTED_GATE").sum() == 4 and len(res["virtual"]) == 1 and res["trades"].empty
