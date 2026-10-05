"""tests/test_price_action_legs.py — swings (fractal/ZigZag) no-lookahead, leg features, लेबल नियम, चालू leg, chart overlay, calibration; कृत्रिम डेटा."""
import json

import numpy as np
import pandas as pd
import pytest

from price_action import leg_eval as E
from price_action import legs as L


def frame(closes, spread=1.0, start="2019-01-01 09:15", freq="15min", opens=None):
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]] if opens is None else np.asarray(opens, float)
    return pd.DataFrame({"timestamp": pd.date_range(start, periods=len(c), freq=freq), "open": o,
                         "high": np.maximum(o, c) + spread, "low": np.minimum(o, c) - spread, "close": c})


def zig(points, step=1.0):
    """[(price), ...] टोकांमधून रेषीय path (प्रत्येक bar step)."""
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        n = max(int(abs(b - a) / step), 1)
        out += list(np.linspace(a, b, n + 1)[1:])
    return out


def test_median_range_uses_only_past_bars():
    df = frame(np.arange(40.0))
    mr = L.median_range(df, 10)
    df2 = df.copy()
    df2.loc[30:, "high"] += 100
    mr2 = L.median_range(df2, 10)
    assert np.allclose(mr[:30], mr2[:30], equal_nan=True) and np.isnan(mr[3]) and mr[10] == pytest.approx(3.0)


def test_zigzag_pivots_alternate_and_confirm_after_pivot():
    df = frame(zig([100, 130, 115, 150, 120, 140]))
    piv = L.zigzag_pivots(df, k=3.0, n_median=10)
    kinds = [p.kind for p in piv]
    assert all(a != b for a, b in zip(kinds, kinds[1:]))
    assert all(p.confirm_bar > p.pivot_bar for p in piv)
    highs = [p.price for p in piv if p.kind == "H"]
    assert max(highs) == pytest.approx(151.0)


def test_pivots_do_not_change_when_future_bars_change():
    base = zig([100, 130, 115, 150, 120, 140, 110])
    df = frame(base)
    full = L.zigzag_pivots(df, k=3.0, n_median=10)
    cut = 60
    alt = frame(base[:cut] + list(np.array(base[cut:]) * 0 + base[cut - 1] + 50))
    a = [(p.kind, p.pivot_bar, p.confirm_bar) for p in L.zigzag_pivots(alt, k=3.0, n_median=10) if p.confirm_bar < cut]
    b = [(p.kind, p.pivot_bar, p.confirm_bar) for p in full if p.confirm_bar < cut]
    assert a == b


def test_fractal_pivots_confirm_r_bars_later():
    df = frame([1, 2, 3, 9, 3, 2, 1, 2, 3], spread=0.1)
    piv = L.fractal_pivots(df, r=2)
    h = [p for p in piv if p.kind == "H"]
    assert h and h[0].pivot_bar == 3 and h[0].confirm_bar == 5


def test_leg_features_efficiency_overlap_fvg_displacement():
    up = frame([100, 104, 108, 112, 116], spread=0.5)                              # सरळ, gap सह candles
    f = L.leg_features(up, 0, 4, 1, 99.5, 116.5, 2.0)
    assert f["dir_pct"] == pytest.approx(0.8) and f["fvg_n"] >= 2 and f["disp_n"] >= 3 and f["overlap"] <= 0.25 and f["eff_range"] > 0.8
    chop = frame([100, 101, 100, 101, 100, 101, 100], spread=0.5)
    g = L.leg_features(chop, 0, 6, 1, 100, 101, 2.0)
    assert g["overlap"] > 0.5 and g["alternation"] >= 0.8 and g["fvg_n"] == 0 and g["eff_range"] < 0.2
    assert 0 <= g["eff_range"] <= 1 and 0 <= f["eff_range"] <= 1


def test_efficiency_capped_with_overnight_gap():
    df = frame([100, 101, 130, 131], spread=0.2)
    f = L.leg_features(df, 0, 3, 1, 99.8, 131.2, 1.0)
    assert f["eff_range"] <= 1.0


def _legs_with(net_seq, feats=None):
    out = []
    for i, n in enumerate(net_seq):
        d = 1 if i % 2 == 0 else -1
        f = {"bars": 5, "net_mr": n, "eff_close": 0.5, "eff_range": 0.5, "dir_pct": 0.6, "max_consec": 2, "alternation": 0.4, "body_pct": 0.5, "clv": 0.2,
             "overlap": 0.4, "fvg_n": 1, "fvg_mr": 0.5, "fvg_against": 0, "body_gaps": 0, "disp_n": 1, "disp_against": 0, "speed": n / 5, "spread": 1.0, "mr": 1.0}
        f.update((feats or {}).get(i, {}))
        out.append(L.Leg(i * 5, i * 5 + 5, i * 5 + 6, d, 0.0, 0.0, f))
    return out


def test_roles_and_reversal_rule():
    legs = L.classify(_legs_with([10, 4, 12, 15]))
    assert [lg.role for lg in legs] == ["IMPULSE", "PULLBACK", "IMPULSE", "IMPULSE"]
    assert legs[1].features["depth"] == pytest.approx(0.4) and legs[3].label == L.REVERSAL       # impulse (12) चा 125% retrace


def test_strong_vs_weak_impulse_and_pullback_labels():
    cfg = L.LegConfig()
    legs = L.classify(_legs_with([10, 3, 12], {0: {"eff_range": 0.6, "overlap": 0.2}, 1: {"fvg_n": 0, "disp_n": 0, "speed": 0.3, "spread": 0.5, "dir_pct": 0.6},
                                               2: {"eff_range": 0.3, "overlap": 0.6, "fvg_n": 0, "disp_n": 0}}), cfg=cfg)
    assert legs[0].label == L.STRONG_IMPULSE and legs[1].label == L.HEALTHY_PULLBACK and legs[2].label == L.WEAK_IMPULSE
    deep = L.classify(_legs_with([10, 9], {1: {"fvg_n": 0, "disp_n": 0, "speed": 0.3}}), cfg=cfg)
    assert deep[1].label == L.DANGEROUS_PULLBACK and any("खोल" in r for r in deep[1].reasons)
    fast = L.classify(_legs_with([10, 3], {1: {"fvg_n": 0, "disp_n": 0, "speed": 5.0}}), cfg=cfg)
    assert fast[1].label == L.DANGEROUS_PULLBACK
    mid = L.classify(_legs_with([10, 6], {1: {"fvg_n": 0, "disp_n": 0, "speed": 0.3, "spread": 0.5}}), cfg=cfg)
    assert mid[1].label == L.MIXED_PULLBACK


def test_range_label_overrides():
    legs = L.classify(_legs_with([10, 3], {1: {"eff_range": 0.1, "overlap": 0.7, "alternation": 0.8}}))
    assert legs[1].label == L.RANGE


def test_build_legs_known_at_is_confirm_and_upto_hides_unconfirmed():
    df = frame(zig([100, 130, 115, 150, 120, 140, 110]))
    legs, swing, _ = L.build_legs(df)
    assert legs and all(lg.known_at >= lg.end_bar for lg in legs)
    cut = legs[1].known_at - 1
    early, _, _ = L.build_legs(df, upto=cut)
    assert all(lg.known_at <= cut for lg in early) and len(early) < len(legs)
    assert [lg.label for lg in early] == [lg.label for lg in legs[:len(early)]]                  # नंतरचे bars जुनी लेबल्स बदलत नाहीत


def test_current_leg_is_provisional_and_does_not_mutate_legs():
    df = frame(zig([100, 130, 115, 150, 120, 140, 125]))
    legs, swing, internal = L.build_legs(df)
    before = [(lg.label, lg.role) for lg in legs]
    cur = L.current_leg(df, None, legs, swing, internal)
    assert cur is not None and cur.provisional and cur.end_bar == len(df) - 1 and cur.start_bar == swing[-1].pivot_bar
    assert [(lg.label, lg.role) for lg in legs] == before


def test_ew_tier_a():
    def mk(pts):
        return [L.Leg(i, i + 1, i + 1, 1 if b > a else -1, a, b, {}) for i, (a, b) in enumerate(zip(pts, pts[1:]))]
    assert L.ew_tier_a(mk([100, 110, 104, 130, 115, 135])) is True
    assert L.ew_tier_a(mk([100, 110, 98, 130, 115, 135])) is False                                   # wave 2 सुरुवातीपलीकडे
    assert L.ew_tier_a(mk([100, 110, 104, 130, 108, 135])) is False                                  # wave 4 overlap
    assert L.ew_tier_a(mk([100, 110, 104])) is None


def test_chart_legs_and_info():
    df = frame(zig([100, 130, 115, 150, 120, 140, 125]))
    legs, swing, internal = L.build_legs(df)
    cur = L.current_leg(df, None, legs, swing, internal)
    segs = L.chart_legs(df, legs, cur)
    assert len(segs) == len(legs) + 1 and segs[-1]["dashed"] and all(s["end"] > s["start"] for s in segs)
    assert all(s["info"] and s["color"] for s in segs) and "eff" in segs[0]["info"]


def test_outcomes_and_stats_use_only_post_known_bars():
    df = frame(zig([100, 130, 115, 150, 120, 140, 110, 135]))
    legs, _, _ = L.build_legs(df)
    out = E.outcomes(df, legs, horizon=4)
    assert len(out) == len(legs) and set(out["role"]) <= {"IMPULSE", "PULLBACK"}
    pb = out[out["role"] == "PULLBACK"]
    assert pb["resume"].dropna().isin([0.0, 1.0]).all()
    assert np.isnan(E.welch_t([1, 2], [3, 4])) and E.prop_z([1] * 10, [0] * 10) > 3


def test_calibrate_runs_both_grids_on_is_only(monkeypatch):
    monkeypatch.setattr(E, "IMPULSE_GRID", {"e_hi": (0.35, 0.45), "o_lo": (0.55,), "d_k": (1.5,), "d_body": (0.6,)})
    monkeypatch.setattr(E, "PULLBACK_GRID", {"r_ok": (0.5,), "r_warn": (0.75, 0.4), "s_ratio": (0.8,), "fvg_min": (0.1,)})
    rng = np.random.default_rng(1)
    c = 100 + np.cumsum(rng.normal(0, 1, 1500))
    df = frame(c, spread=0.6, start="2021-10-01 09:15")
    cal = E.calibrate(df)
    tr = cal["trials"]
    assert set(tr["grid"]) == {"impulse", "pullback"} and len(tr[tr["grid"] == "pullback"]) == 1                  # r_warn ≤ r_ok वगळला
    assert isinstance(cal["cfg"], L.LegConfig)
    ev = E.evaluate(df, cal["cfg"])
    assert set(ev["summary"]["period"]) == {"IS 2015→2021", "VAL 2022→2024-03"}
    days = E.sample_days(ev["outcomes"], n=5)
    assert len(days) <= 5 and all(d <= E.IS_END for d in days)


def test_chart_html_renders_legs_only_when_given_and_overlay_skips_forming_bar():
    from bot_view import leg_overlay
    from tradingview_chart import build_lightweight_chart_html
    df = frame(zig([100, 130, 115, 150, 120, 140, 125]))
    df["volume"] = 0
    plain = build_lightweight_chart_html(df)
    assert "const legsData = [];" in plain
    now = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=5)                             # शेवटची 15M candle अजून चालू
    segs, cap = leg_overlay(df, "15minute", now)
    assert segs and cap and max(s["end"] for s in segs) <= df["timestamp"].iloc[-2]
    html = build_lightweight_chart_html(df, legs=segs)
    assert "legInfoAt" in html and json.dumps(segs[0]["info"])[1:30] in html            # JSON मराठी \\u escape करतो
    assert leg_overlay(df.head(10), "15minute", now) == ([], None)
