"""Chart Reader — reversal evidence (Abhi 2026-10-08): elliott/reversal.py मुख्य; 0.60 cutoff पक्का नाही.

पक्क्या अटी: बंद candle (caller), touch + reclaim, invalidation, indecision band (CL 0.40–0.60 ⇒ follow-through ची वाट).
बाकी (strength, climax, शेवटची candle विरुद्ध, N = 3) ⇒ s वर modifiers. candles.py 0–100 फक्त breakdown (log / vision).
"""
import numpy as np
import pandas as pd

from chart_reader import reversal as CRV
from chart_reader import settings as CS
from elliott import breaks as BR
from elliott import reversal as RV
from elliott import settings as ES

ES_S = dict(ES.DEFAULTS)
S = dict(CS.DEFAULTS)


def frame(rows, base_rng=10.0, n_hist=25):
    """n_hist सपाट bars (range = base_rng) आणि मग दिलेले (o, h, l, c)."""
    hist = [(100.0, 100.0 + base_rng / 2, 100.0 - base_rng / 2, 100.0)] * n_hist
    allr = hist + list(rows)
    ts = pd.date_range("2021-03-01 09:15", periods=len(allr), freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": [r[0] for r in allr], "high": [r[1] for r in allr], "low": [r[2] for r in allr],
                         "close": [r[3] for r in allr]})


def ev(rows, level=95.0, dirn=1, **kw):
    f = frame(rows)
    b = RV.Bars(f, BR.median_range(f, ES_S["median_range_n"]))
    return CRV.evaluate(b, len(f) - 1, dirn, [level], 2.0, ES_S, S, frame=f, **kw)


def test_soft_mode_keeps_elliott_default_unchanged():
    f = frame([(100, 101, 92, 99)])                                                         # range 9 < 1.2 × 10 ⇒ elliott: weak
    b = RV.Bars(f, BR.median_range(f, 20))
    hard = RV.evaluate_window(b, len(f) - 1, 1, 1, [95.0], 2.0, ES_S)
    soft = RV.evaluate_window(b, len(f) - 1, 1, 1, [95.0], 2.0, ES_S, soft=True)
    assert hard["reason"] == RV.WEAK and not hard["ok"]
    assert soft["ok"] and "weak" in soft["flags"] and soft["score"] > 0


def test_strong_hammer_scores_high_without_modifiers():
    r = ev([(98, 101, 88, 100.5)])                                                          # range 13 ≥ 12, close high, long wick
    assert r["status"] == "ok" and r["n"] == 1 and r["s"] == r["raw"] and r["label"] in ("strong", "medium")
    assert set(r["candles"]["components"]) >= {"wick", "close_loc", "bounce", "sweep", "speed"}       # 0–100 breakdown (log)


def test_weak_candle_scaled_not_rejected():
    r = ev([(98, 100.5, 91, 100)])                                                          # range 9.5 < 12
    assert r["status"] == "ok" and "weak" in r["flags"]
    assert np.isclose(r["s"], r["raw"] * max(S["rev_weak_floor"], 9.5 / 12.0), atol=1e-3)


def test_climax_extension_penalised_wide_reclaim_not():
    climax = ev([(99, 100, 70, 96)])                                                        # range 30 > 25, CL 0.87 ⇒ wide reclaim
    assert climax["status"] == "ok" and "wide_reclaim" in climax["flags"] and climax["s"] == climax["raw"]
    r = ev([(99, 100, 70, 87)], level=80.0)                                                 # CL 0.57 — indecision band ⇒ wait
    assert r["status"] == "wait_followthrough"


def test_firm_conditions_no_touch_no_reclaim_indecision():
    assert ev([(100, 103, 98, 101)], level=90.0)["status"] == "no_touch"
    assert ev([(98, 99, 90, 93)])["status"] == "no_reclaim"                                # close level खाली
    assert ev([(97, 103, 91, 97)])["status"] == "wait_followthrough"                       # CL 0.5


def test_last_candle_against_penalty_n2():
    r = ev([(99, 99.5, 88, 96), (97, 102, 96.5, 96.6)], n_max=2)                           # N=2, शेवटची candle bearish
    if r["status"] == "ok" and r["n"] == 2:
        assert "last_against" in r["flags"] and np.isclose(r["s"], max(0.0, r["raw"] - S["rev_last_against_penalty"]), atol=1e-3)


def test_bearish_mirror():
    r = ev([(102, 112, 99, 99.5)], level=105.0, dirn=-1)                                  # shooting star resistance वर
    assert r["status"] == "ok" and r["n"] == 1


def test_truncation_invariance_only_closed_bars_used():
    rows = [(98, 101, 88, 100.5), (100.5, 104, 100, 103), (103, 104, 96, 97)]
    f = frame(rows)
    b_full = RV.Bars(f, BR.median_range(f, 20))
    j = len(f) - 3
    full = CRV.evaluate(b_full, j, 1, [95.0], 2.0, ES_S, S, frame=f)
    cut = f.iloc[: j + 1].reset_index(drop=True)
    b_cut = RV.Bars(cut, BR.median_range(cut, 20))
    part = CRV.evaluate(b_cut, j, 1, [95.0], 2.0, ES_S, S, frame=cut)
    assert (full["status"], full["s"], full["n"]) == (part["status"], part["s"], part["n"])


def test_close_against_trade_direction_is_not_a_reversal():
    """Bear call साठी मोठी bullish candle (close वर) ⇒ mirrored CL < 0.40 ⇒ reversal नाही (G-E1a examples मधला bug)."""
    r = ev([(96.0, 105.5, 95.0, 104.9)], level=105.0, dirn=-1)                            # level खाली close, पण range च्या वरच्या टोकाला
    assert r["status"] == "against" and r["s"] is None
