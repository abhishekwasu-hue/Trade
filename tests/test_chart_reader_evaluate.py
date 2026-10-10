"""Chart Reader evaluate (G-E1a, KB भाग B): सगळे 16 पुरावे, सगळी साधनं (a–l) उमेदवार, गोष्ट [K#] tags सह, no-lookahead."""
import numpy as np
import pandas as pd

from chart_reader import evaluate as EV
from chart_reader import grade as G
from chart_reader import settings as CS


def synth_1m(days=18, seed=7):
    rng = np.random.default_rng(seed)
    out, p = [], 17000.0
    for d in pd.bdate_range("2021-02-01", periods=days):
        ts = pd.date_range(d + pd.Timedelta(hours=9, minutes=15), periods=375, freq="1min")
        drift = 0.25 if d.day % 6 < 4 else -0.35                                         # तेजी, मग pullback — लाटा
        for t in ts:
            o = p
            p = p + drift + rng.normal(0, 2.0)
            out.append((t, o, max(o, p) + abs(rng.normal(0, 1.0)), min(o, p) - abs(rng.normal(0, 1.0)), p))
    return pd.DataFrame(out, columns=["timestamp", "open", "high", "low", "close"])


def test_evaluate_reports_all_evidence_tools_and_tagged_story():
    m1 = synth_1m()
    asof = pd.Timestamp("2021-02-23 13:30")
    r = EV.evaluate(m1, "srv2", asof, s=CS.load(), run_elliott=False)
    assert set(r["points"]) == set(G.KEYS) and len(r["lines"]) >= 16
    assert all(("[K" in x or "[A3]" in x or x.startswith("⛔")) for x in r["lines"])
    assert 1 <= len(r["story"]) <= 12 and all("[" in x for x in r["story"])
    by = r["areas"]["by_tool"]
    assert by["j"] >= 2                                                                  # round numbers नेहमी उमेदवार
    assert by["k"] >= 3                                                                  # PDH / PDL / PDC
    assert r["grade"] in ("A", "B", "C") and isinstance(r["entry"], bool) and r["kb"]["VL"]["pts"] == 0   # futures data नाही ⇒ 0


def test_evaluate_is_causal_future_bars_change_nothing():
    m1 = synth_1m()
    asof = pd.Timestamp("2021-02-22 14:00")
    a = EV.evaluate(m1, "srv2", asof, s=CS.load(), run_elliott=False)
    b = EV.evaluate(m1[m1["timestamp"] < asof].reset_index(drop=True), "srv2", asof, s=CS.load(), run_elliott=False)
    assert (a["grade"], a["total"], a["points"], a["story"], a["side"]) == (b["grade"], b["total"], b["points"], b["story"], b["side"])


def test_target_extreme_covers_expanded_flat_b_beyond_impulse_end():
    """Expanded flat (bear call): B impulse च्या टोकापलीकडे ⇒ target = B चं टोक, दूरचा HTF area नाही."""
    trig = pd.DataFrame({"high": [120, 119, 112, 105, 104, 110, 108, 100, 103, 109], "low": [118, 110, 104, 101, 100, 104, 99, 95, 99, 104]})
    st = {"impulse": {"start_bar": 0, "end_bar": 4, "end": 100.0}}
    assert EV.trend_extreme(trig, st, -1) == 95.0 and EV.trend_extreme(trig, st, 1) == 120.0
    assert EV.trend_extreme(trig, {"impulse": None}, -1) is None


def test_major_zones_only_degree2_inside_impulse_and_not_bad():
    st = {"impulse": {"origin": 100.0, "end": 160.0}}
    horiz = [{"low": 120, "high": 122, "degree": 2, "state": "ACTIVE"}, {"low": 130, "high": 132, "degree": 1, "state": "ACTIVE"},
             {"low": 140, "high": 142, "degree": 3, "state": "MAGNET"}, {"low": 170, "high": 172, "degree": 2, "state": "ACTIVE"}]
    assert EV.major_zones(horiz, st) == [(120.0, 122.0)] and EV.major_zones(horiz, {"impulse": None}) == []


def _first_sided(m1):
    for asof in pd.date_range("2021-02-22 10:00", "2021-02-24 15:00", freq="15min"):
        if asof.hour < 9 or asof.hour > 15:
            continue
        r = EV.evaluate(m1, "srv2", asof, s=CS.load(), run_elliott=False)
        if r["side"]:
            return asof, r
    return None, None


def test_f4_side_unclear_is_a_code_mode_gate(monkeypatch):
    """Abhi 2026-10-08 (c): F4 विरोध (market_state side "unclear") ⇒ code-mode entry नाही (SIDE_UNCLEAR); f4_gate OFF ⇒ फक्त नोंद."""
    import market_state as MSM
    m1 = synth_1m()
    real = MSM.read

    def unclear(*a, **k):
        ms = real(*a, **k)
        return {**ms, "side": "unclear", "side_reasons": ["HTF trend विरुद्ध (test)"]}
    monkeypatch.setattr(EV.MS, "read", unclear)
    asof, r = _first_sided(m1)
    assert asof is not None
    assert any(w.startswith("SIDE_UNCLEAR") for w in r["why_no_entry"]) and not r["entry"]
    r2 = EV.evaluate(m1, "srv2", asof, s={**CS.load(), "f4_gate": False}, run_elliott=False)
    assert not any(w.startswith("SIDE_UNCLEAR") for w in r2["why_no_entry"]) and r2.get("side_unclear")


def test_shadow_engine_fills_23_item_checklist():
    """जड chart_reader (shadow): प्रत्येक बाजू असलेल्या candidate वर 23 बाबी भरलेल्या (context; entry ठरवत नाहीत)."""
    m1 = synth_1m()
    for asof in pd.date_range("2021-02-23 10:00", "2021-02-23 15:00", freq="30min"):
        r = EV.evaluate(m1, "srv2", asof, s=CS.load(), run_elliott=False)
        if r["side"]:
            assert len(r["checklist"]) == 23 and all(x["value"] for x in r["checklist"])
