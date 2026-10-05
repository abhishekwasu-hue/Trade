"""tests/test_price_action_candles.py -- LOGIC-BASED candle confirmation (composite rejection candle + rejection_score). synthetic only."""
import pandas as pd
import pytest

from price_action import candles as PA

L = 100.0


def _df(window, base_n=22, base=(105.0, 106.0, 104.0, 105.2)):
    """base: level पासून दूर, range 2 (median_range = 2) — मग window candles. timestamps 30M."""
    rows = [base] * base_n + list(window)
    ts = pd.date_range("2026-10-05 09:00", periods=len(rows), freq="30min")
    return pd.DataFrame([{"timestamp": t, "open": o, "high": h, "low": lo, "close": c} for t, (o, h, lo, c) in zip(ts, rows)])


def _mirror(df, axis=210.0):
    """bearish चाचणीसाठी आरसा: x -> axis − x (high/low अदलाबदल)."""
    return pd.DataFrame({"timestamp": df["timestamp"], "open": axis - df["open"], "high": axis - df["low"], "low": axis - df["high"],
                         "close": axis - df["close"]})


HAMMER = [(102.0, 103.2, 99.5, 103.0)]
ENGULF = [(103.0, 103.3, 100.5, 101.0), (100.8, 104.0, 99.8, 103.8)]
MSTAR = [(104.0, 104.2, 101.0, 101.2), (100.6, 101.0, 99.7, 100.4), (100.6, 103.9, 100.3, 103.7)]
SWEEP = [(101.5, 101.8, 99.0, 99.4), (99.4, 102.3, 99.2, 102.1)]


def test_hammer_shape_n1():
    r = PA.evaluate_rejection(_df(HAMMER), L, "BULLISH")
    assert r["ok"] and r["n"] == 1 and r["label"] == "≈ Hammer" and r["score"] >= 60 and r["components"]["speed"] == 15


def test_engulfing_shape_n2_composite_beats_n1():
    r = PA.evaluate_rejection(_df(ENGULF), L, "BULLISH")
    assert r["ok"] and r["n"] == 2 and r["label"] == "≈ Bullish Engulfing"
    assert r["composite"] == {**r["composite"], "open": 103.0, "high": 104.0, "low": 99.8, "close": 103.8}
    assert PA.evaluate_window(_df(ENGULF), 1, L, "BULLISH")["score"] < r["score"]


def test_morning_star_shape_n3():
    r = PA.evaluate_rejection(_df(MSTAR), L, "BULLISH")
    assert r["ok"] and r["n"] == 3 and r["label"] == "≈ Morning Star" and r["components"]["speed"] == 5


def test_failed_breakdown_sweep():
    r = PA.evaluate_rejection(_df(SWEEP), L, "BULLISH")
    assert r["ok"] and r["sweep"] and r["components"]["sweep"] == 15 and r["label"] == "≈ Failed Breakdown"


@pytest.mark.parametrize("window, reason", [
    ([(102.0, 104.0, 99.8, 102.1)], PA.INDECISIVE),                # मोठी doji, close_loc ≈ 0.55
    ([(101.0, 101.5, 98.5, 99.5)], PA.NO_RECLAIM),                  # support खाली close
    ([(101.5, 104.0, 100.6, 103.8)], PA.NO_TOUCH),                  # level पर्यंत आलीच नाही
    ([(106.0, 106.5, 94.0, 105.0)], PA.EXHAUSTION),                 # range > 2.5 × median
    ([(100.3, 101.5, 99.9, 101.4)], PA.WEAK),                       # range < 1.2 × median
])
def test_rejected_windows_report_reason(window, reason):
    r = PA.evaluate_rejection(_df(window), L, "BULLISH")
    assert not r["ok"] and r["reason"] == reason


def test_last_candle_must_close_in_direction_for_n2():
    r = PA.evaluate_window(_df([(103.0, 103.3, 99.6, 101.0), (101.0, 103.5, 100.6, 100.9)]), 2, L, "BULLISH")
    assert r["reason"] == PA.LAST_AGAINST


def test_k_controls_strength():
    weak = _df([(100.6, 102.6, 99.9, 102.5)])                           # range 2.7 ≈ 1.35 × median
    assert PA.evaluate_window(weak, 1, L, "BULLISH", k=1.5)["reason"] == PA.WEAK
    assert PA.evaluate_window(weak, 1, L, "BULLISH", k=1.2)["reason"] != PA.WEAK


def test_indecision_follow_through_allows_n4_only_then():
    win = [(103.0, 103.2, 99.6, 100.5), (100.5, 101.6, 100.2, 101.4), (101.4, 101.8, 101.0, 101.5)]
    assert PA.evaluate_window(_df(win), 3, L, "BULLISH")["reason"] == PA.INDECISIVE
    r = PA.evaluate_rejection(_df(win + [(101.5, 103.6, 101.4, 103.5)]), L, "BULLISH")
    assert r["ok"] and r["n"] == 4 and r["components"]["speed"] == 0
    r_red = PA.evaluate_rejection(_df(win + [(101.5, 101.6, 100.9, 101.0)]), L, "BULLISH")    # पुढची candle उलट ⇒ N=4 नाही
    assert not r_red["ok"] and r_red["n"] != 4


def test_bearish_is_exact_mirror():
    bull = PA.evaluate_rejection(_df(HAMMER), L, "BULLISH")
    bear = PA.evaluate_rejection(_mirror(_df(HAMMER)), 210.0 - L, "BEARISH")
    assert bear["ok"] and bear["score"] == bull["score"] and bear["n"] == 1 and bear["label"] == "≈ Shooting Star"


def test_structure_sl_never_above_support_and_chase_rule():
    r = PA.evaluate_rejection(_df([(100.4, 103.0, 100.08, 102.9)]), L, "BULLISH", min_score=0)    # low support च्या वर (touch band मध्ये)
    assert r["ok"] and PA.structure_sl(r) <= L * (1 - 0.0005)
    r2 = PA.evaluate_rejection(_df(HAMMER), L, "BULLISH")
    sl = PA.structure_sl(r2)
    assert sl == pytest.approx(99.5 * 0.9995) and sl < L
    assert PA.chase_ok(100.5, L, sl, "BULLISH") and not PA.chase_ok(100.6, L, sl, "BULLISH")     # 0.5 ≤ 0.5×1.05; 0.6 > 0.5×1.15
    bear = PA.evaluate_rejection(_mirror(_df(HAMMER)), 110.0, "BEARISH")
    assert PA.structure_sl(bear) >= 110.0 * 1.0005


def test_completed_only_drops_forming_candle():
    df = _df(HAMMER)
    last_start = df["timestamp"].iloc[-1]
    assert len(PA.completed_only(df, 30, last_start + pd.Timedelta(minutes=10))) == len(df) - 1
    assert len(PA.completed_only(df, 30, last_start + pd.Timedelta(minutes=30))) == len(df)


def test_scan_markers_no_lookahead():
    df = _df(SWEEP + [(102.1, 103.0, 101.8, 102.8)] * 3)
    full = dict(PA.scan_markers(df, [L]))
    for j in range(len(df)):
        part = dict(PA.scan_markers(df.iloc[: j + 1].reset_index(drop=True), [L]))
        assert {i: m for i, m in full.items() if i <= j} == part                    # भविष्यातले candles मागचे markers बदलत नाहीत
    assert any(m["bullish"] for m in full.values())


def test_label_never_used_in_decision():
    r = PA.evaluate_rejection(_df(HAMMER), L, "BULLISH", min_score=99)
    assert not r["ok"] and r["reason"] == PA.LOW_SCORE and r["label"] == "≈ Hammer"
