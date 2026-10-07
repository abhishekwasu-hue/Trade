"""tests/test_elliott_c1.py — Elliott + candle merge C1 (addendum §2–§6, §9): सगळे नवीन features default OFF ⇒ signals byte-for-byte
तसेच; profile reduce-only (own_correction अपवाद tag); A-end नेहमी reject; candle सुधारणा (path, n3, body/reclaim, dragonfly, climax
logic, reclaim depth, overlap, follow-through addendum); blended label फक्त log; ARMED state machine; opposite candle ⇒ exit नाही."""
import collections
import json
import os
import types

import numpy as np
import pandas as pd
import pytest

from elliott import backtest as BT
from elliott import reversal as RV
from elliott import settings as S
from elliott import trigger as TR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T0 = pd.Timestamp("2019-01-02 09:15")


def _cfg(**k):
    c, e = S.validate(k)
    assert not e, e
    return c


S0 = _cfg()


def frame(rows, base=30):
    bars = [(100.0, 105.0, 95.0, 100.0)] * base + [tuple(map(float, r)) for r in rows]
    ts = [T0 + pd.Timedelta(minutes=5 * i) for i in range(len(bars))]
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    df.insert(1, "bar_end", [t + pd.Timedelta(minutes=5) for t in ts])
    return df


def bars_of(df):
    from elliott import breaks as B
    return RV.Bars(df, B.median_range(df, 20))


def _rows(sc):
    return [[str(x.t), x.degree, x.setup, x.tier, x.direction, x.ttf, round(x.hard_inv, 4), round(x.touched, 4), x.n,
             round(x.score, 9), round(x.soft_stop, 4), round(x.sub_origin, 4)] for x in sc.signals]


@pytest.fixture(scope="module")
def data_h1():
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    return d[(d["timestamp"] >= "2019-01-01") & (d["timestamp"] <= "2019-06-30 23:59")].reset_index(drop=True)


@pytest.fixture(scope="module")
def default_run(data_h1):
    sc = TR.Scanner(data_h1, S0)
    sc.run()
    return sc


def test_defaults_off_byte_identical_to_e2_snapshot(default_run):
    snap = json.load(open(os.path.join(ROOT, "tests", "data", "elliott_e2_signals_2019h1.json")))
    reasons = collections.Counter(f"{r[1]}|{r[2]}|{r[3]}" for r in default_run.reasons)
    assert _rows(default_run) == snap["signals"]
    assert dict(sorted(reasons.items())) == snap["reasons"]


def test_contexts_and_no_repaint(default_run):
    for x in default_run.signals:
        assert x.wave_ctx["zone_known_at"] is None or x.wave_ctx["zone_known_at"] <= x.t   # zone/inv trigger आधी ठरलेले
        assert x.candle_ctx["n"] == x.n and x.candle_ctx["label"] in {
            "hammer-like", "shooting-star-like", "marubozu-like", "engulfing-like", "piercing-like", "dark-cloud-like", "star-like", "other"}
        assert set(x.candle_ctx["parts"]) >= {"wick", "close_loc", "body"}
    tr = collections.Counter((a, b) for _, _, a, b, _ in default_run.transitions)
    allowed = {("IDLE", "ARMED"), ("EXPIRED", "ARMED"), ("ARMED", "WAIT_FOLLOWTHROUGH"), ("WAIT_FOLLOWTHROUGH", "ARMED"),
               ("ARMED", "TRIGGERED"), ("WAIT_FOLLOWTHROUGH", "TRIGGERED"), ("ARMED", "EXPIRED"), ("WAIT_FOLLOWTHROUGH", "EXPIRED"),
               ("TRIGGERED", "EXPIRED")}
    assert set(tr) <= allowed, set(tr) - allowed                                   # IDLE/EXPIRED → TRIGGERED कधीच नाही
    trig = {k for _, k, _, b, _ in default_run.transitions if b == "TRIGGERED"}
    assert all(x.key in trig for x in default_run.signals)


def test_profile_reduce_only_and_a_end(data_h1, default_run):
    base = {(str(x.t), x.degree, x.setup, x.direction) for x in default_run.signals}
    for mode in ("shadow", "on"):
        sc = TR.Scanner(data_h1, _cfg(candle_profile_mode=mode))
        sc.run()
        keys = {(str(x.t), x.degree, x.setup, x.direction) for x in sc.signals}
        if mode == "shadow":
            assert keys == base                                                     # shadow ⇒ निर्णय तेच, फक्त log
            assert all(x.candle_ctx["profile"] is not None for x in sc.signals)
        else:
            extra = [x for x in sc.signals if (str(x.t), x.degree, x.setup, x.direction) not in base]
            assert all(x.candle_ctx["profile"]["admitted"] and x.candle_ctx["profile"]["ref"] == "own_correction"
                       and x.candle_ctx["profile"]["name"] in ("w4", "tri_e") for x in extra)
        assert not any(x.current_wave == "A" for x in sc.signals)                  # A-end कधीच नाही
        assert sc.profile_log                                                       # shadow/on: नकारही log


def test_path_check_n3_penalty_and_cap_logic():
    rows = [(100, 101, 88, 95), (95, 104, 94, 103.5)]                               # N=2 composite
    b = bars_of(frame(rows))
    j = 31
    base = RV.evaluate_window(b, j, 2, 1, [94.0], 0.0, S0)
    assert base["reason"] not in (RV.PATH,)
    retr = frame([(100, 101, 88, 95), (95, 110, 94, 97)])                           # शेवटच्या candle ने अर्ध्यापेक्षा जास्त परत दिलं
    r = RV.evaluate_window(bars_of(retr), j, 2, 1, [94.0], 0.0, _cfg(path_checks=True))
    assert r["reason"] == RV.PATH
    early = frame([(90, 112, 88, 98), (98, 99.5, 97.5, 98.8)])                     # CL 0.45 — पण तो पहिल्या candle ने परत दिला
    e = RV.evaluate_window(bars_of(early), j, 2, 1, [94.0], 0.0, _cfg(path_checks=True))
    assert 0.4 < e["close_loc"] < 0.5 and e["reason"] == RV.INDECISIVE
    give = frame([(90, 104, 88, 100), (99, 113, 98.5, 99.5)])                       # शेवटच्या candle ने स्वतः 13.5 / 25 परत
    g = RV.evaluate_window(bars_of(give), j, 2, 1, [94.0], 0.0, _cfg(path_checks=True))
    assert 0.4 < g["close_loc"] < 0.5 and g["reason"] == RV.PATH
    assert RV.evaluate_window(bars_of(give), j, 2, 1, [94.0], 0.0, S0)["reason"] == RV.INDECISIVE
    three = frame([(100, 101, 88, 92), (92, 95, 90, 93), (93, 104, 92, 103.5)])
    a = RV.evaluate_window(bars_of(three), 32, 3, 1, [94.0], 0.0, S0)
    p = RV.evaluate_window(bars_of(three), 32, 3, 1, [94.0], 0.0, _cfg(n3_penalty=0.05))
    assert p["score"] == pytest.approx(a["score"] - 0.05)
    wide = frame([(101, 135, 80, 133)])                                             # range 55 > 2.5 × 10, close टोकाला
    assert RV.evaluate_window(bars_of(wide), 30, 1, 1, [100.0], 0.0, S0)["reason"] == RV.EXHAUSTION
    assert RV.evaluate_window(bars_of(wide), 30, 1, 1, [100.0], 0.0, _cfg(strength_cap_mode="logic"))["reason"] != RV.EXHAUSTION
    assert RV.evaluate_window(bars_of(wide), 30, 1, 1, [100.0], 0.0,
                              _cfg(strength_cap_mode="logic", strength_risk_guard_mult=4.0))["reason"] == RV.EXHAUSTION
    climax = frame([(130, 135, 80, 85)])                                            # रुंद, pullback दिशेने close ⇒ logic मध्येही reject
    assert RV.evaluate_window(bars_of(climax), 30, 1, 1, [100.0], 0.0, _cfg(strength_cap_mode="logic"))["reason"] in (
        RV.EXHAUSTION, RV.NO_RECLAIM)


def test_body_or_reclaim_piercing_and_dragonfly():
    pierce = frame([(104, 104.5, 92, 93), (92, 101.5, 89, 100.5)])                   # काळी पहिली, दुसरी body च्या 60%+ आत
    j = 31
    a = RV.evaluate_window(bars_of(pierce), j, 2, 1, [95.0], 0.0, S0)
    b2 = RV.evaluate_window(bars_of(pierce), j, 2, 1, [95.0], 0.0, _cfg(body_term_mode="body_or_reclaim"))
    assert a["parts"]["body"] == 0.0 and b2["parts"]["body"] > 0.5 and b2["label"] in ("piercing-like", "engulfing-like")
    dragon = frame([(103, 103.2, 89, 103.2)])                                        # body ≈ 0, close = high
    assert RV.evaluate_window(bars_of(dragon), 30, 1, 1, [100.0], 0.0, _cfg(min_body_or_reclaim=True))["reason"] == RV.NO_BODY
    assert RV.evaluate_window(bars_of(dragon), 30, 1, 1, [100.0], 0.0, S0)["reason"] != RV.NO_BODY


def test_reclaim_depth_and_overlap_weights_enter_score_only_when_on():
    df = frame([(101, 103, 88, 102)])
    b = bars_of(df)
    a = RV.evaluate_window(b, 30, 1, 1, [100.0], 0.0, S0)
    assert "reclaim_depth" not in a["parts"] and "low_overlap" not in a["parts"]
    r = RV.evaluate_window(b, 30, 1, 1, [100.0], 0.0, _cfg(w_reclaim_depth=0.1, w_overlap=0.1))
    assert "reclaim_depth" in r["parts"] and "low_overlap" in r["parts"] and r["score"] != a["score"]


def test_followthrough_addendum_needs_close_beyond_composite():
    rows = [(100, 101, 88, 95), (95, 97, 93, 94), (94, 98, 93, 95.5)]               # N=3 अनिर्णयी
    s = _cfg(followthrough_mode="addendum")
    up = frame(rows + [(95.5, 104, 95, 103)])
    r = RV.evaluate(bars_of(up), 33, 1, [94.0], 0.0, s)
    assert r["ok"] and r.get("followthrough") and r["n"] == 4
    assert r["score"] == pytest.approx(RV.evaluate_window(bars_of(up), 32, 3, 1, [94.0], 0.0, s)["score"])   # अनिर्णयी composite चा score
    assert r["comp"][3] == 103 and r["comp"][2] == 88                               # soft stop composite j पर्यंत
    flat = frame(rows + [(95.5, 104, 95, 95.0)])                                    # close composite close पलीकडे नाही
    f = RV.evaluate(bars_of(flat), 33, 1, [94.0], 0.0, s)
    assert not f.get("followthrough")
    gap = frame(rows + [(99, 99.5, 96.5, 97.0)])                                    # gap-up, स्वतःची body उलट, पण close composite पलीकडे
    gr = RV.evaluate(bars_of(gap), 33, 1, [94.0], 0.0, s)
    assert gr["ok"] and gr.get("followthrough")
    legacy = RV.evaluate(bars_of(gap), 33, 1, [94.0], 0.0, S0)
    assert not legacy.get("followthrough")
    two = frame(rows + [(95.5, 96, 94.6, 95.2), (95.2, 104, 95, 103)])              # max_bars 2: दोन bars नंतर
    assert not RV.evaluate(bars_of(two), 34, 1, [94.0], 0.0, s).get("followthrough")
    t2 = RV.evaluate(bars_of(two), 34, 1, [94.0], 0.0, _cfg(followthrough_mode="addendum", followthrough_max_bars=2))
    assert t2["ok"]


def test_blended_labels():
    assert RV.evaluate_window(bars_of(frame([(101, 103, 88, 102)])), 30, 1, 1, [100.0], 0.0, S0)["label"] == "hammer-like"
    eng = frame([(104, 104.5, 96, 97), (96.5, 106, 96, 105)])
    assert RV.evaluate_window(bars_of(eng), 31, 2, 1, [97.0], 0.0, S0)["label"] == "engulfing-like"
    bear = RV.evaluate_window(bars_of(frame([(99, 112, 97, 98)])), 30, 1, -1, [100.0], 0.0, S0)
    assert bear["label"] == "shooting-star-like"


def test_c_leg_displacement_option(data_h1, default_run):
    sc = TR.Scanner(data_h1, _cfg(c_leg_exhaustion_required=True))
    sc.run()
    assert len(sc.signals) <= len(default_run.signals) and any(r[3] == "C_leg_displacement" for r in sc.reasons)
    blocked = [r for r in sc.reasons if r[3] == "C_leg_displacement"]
    assert len(blocked) < len([r for r in sc.reasons if r[3] and r[3].startswith("T_")]) // 2   # फक्त extreme जवळचे bars


def test_opposite_candle_watch_never_exits(data_h1, default_run, monkeypatch):
    times = default_run.times()
    sigs = {}
    for x in default_run.signals:
        sigs.setdefault(x.t, []).append(x)
    st = _cfg(c_min_by_dte=[0.0] * 5, min_credit_pts=0.0)

    def run(s, always_opp):
        if always_opp:                                                              # backtest चं opposite-candle evaluate नेहमी ok
            monkeypatch.setattr(BT, "RV", types.SimpleNamespace(evaluate=lambda *a, **k: {"ok": True}))
        bt = BT.Backtest(data_h1, s, scanner=default_run, replay=sigs)
        bt.run(times)
        monkeypatch.undo()
        return bt
    base = run(st, False)
    watch = run(st, True)                                                           # प्रत्येक bar वर उलट candle — तरी exits तसेच
    assert base.closed and [(t.exit_ts, t.exit_reason, round(t.realized, 6)) for t in watch.closed] == \
        [(t.exit_ts, t.exit_reason, round(t.realized, 6)) for t in base.closed]
    assert all(len(t.notes) <= 1 for t in watch.closed) and any(t.notes == [(t.notes[0][0], "opposite_candle")] for t in watch.closed
                                                                 if t.notes)
    tight = run({**st, "opposite_candle_action": "tighten_profit_target"}, True)
    assert any(t.tp_tight for t in tight.closed) and not any(t.exit_reason == "opposite_candle" for t in tight.closed)


def test_time_slot_and_own_correction_are_causal(data_h1):
    """चालू दिवसाच्या पुढच्या bars बदलले तरी आधीच्या bar चा strength संदर्भ तोच (no-repaint)."""
    s = _cfg(strength_ref="time_slot", slot_median_sessions=5)
    sc = TR.Scanner(data_h1, s)
    tf = "5m"
    fr = sc.frames[tf]
    j = int(np.searchsorted(fr["timestamp"].to_numpy("datetime64[ns]"), np.datetime64("2019-03-15 11:00"), "left"))
    f = sc._strength_mr(tf, "time_slot", 0, 0)
    v = f(j)
    cut = data_h1[data_h1["timestamp"] < pd.Timestamp("2019-03-15 11:05")]
    noisy = pd.concat([cut, data_h1[data_h1["timestamp"] >= pd.Timestamp("2019-03-15 11:05")].assign(
        high=lambda x: x["high"] + 500.0, low=lambda x: x["low"] - 500.0)])
    sc2 = TR.Scanner(noisy.reset_index(drop=True), s)
    assert sc2._strength_mr(tf, "time_slot", 0, 0)(j) == pytest.approx(v)
    assert sc._strength_mr(tf, "own_correction", j - 10, j) == pytest.approx(sc2._strength_mr(tf, "own_correction", j - 10, j))


def test_profile_families_and_reduce_only_helpers(data_h1):
    sc = TR.Scanner(data_h1, _cfg(candle_profile_mode="on", strength_ref="time_slot"))

    class N:
        pattern, subtype = "flat", "flat_exp"

    class St:
        code, node = "S7", N()
    assert sc._profile(St())[:2] == ("flat_c", "own_correction")
    St.code = "S6a"
    fam, ref, rmin = sc._profile(St())
    assert fam == "counter" and ref == "time_slot" and rmin == pytest.approx(S0["rejection_min"] + 0.05)
    St.code = "S3"
    assert sc._profile(St())[:2] == ("w4", "own_correction")


def test_core_candle_strips_c1_for_breaks_and_exits():
    s = _cfg(path_checks=True, w_overlap=0.2, candle_profile_mode="on")
    core = S.core_candle(s)
    assert all(core[k] == S.DEFAULTS[k] for k in S.CANDLE_KEYS) and S.core_candle(S0) is S0
    assert not any(x["calibrate"] for x in S.SCHEMA if x["section"] == "candle")
