"""Abhi's method (docs/knowledge/CHART_READER_METHOD.md §1 P1, §6, §7): no numeric thresholds in the reading path.

Every numeric default of the decision3 reading engine must be classified. Numbers allowed to stay are legacy what-if switches that are
off by default, operational / display settings, data-quality checks, or Abhi's swing calibration (layer 1 ✅: significance against the
market's own normal movement at the scale he chose from his charts). Every other number is `PENDING` with the layer PR that removes
it (docs/reports/v22/METHOD_MAP.md). A new unclassified number fails this test; at the end of layer 6 `PENDING` must be empty.
Scope: the decision3 settings (S3.DEFAULTS). Numbers written directly in code are reviewed per layer (METHOD_MAP), not scanned here.
"""
import pathlib
import re

from decision3 import settings as S3

D3 = pathlib.Path(S3.__file__).parent

LEGACY = {                       # used only by a non-default rule / gate (what-if): {setting: (switch, the only decision3 files that read it)}
    "corr_degree_frac": ("corr_degree_rule = ratio", {"daily.py"}),
    "daily_dc_k": ("daily_swing_method = dc", {"daily.py"}),
    "level_min_width_sigma": ("0 by default; > 0 = the old minimum width", {"levels.py", "trendline.py"}),
    "prior_level_atr_mult": ("prior_level_rule = atr", {"levels.py"}),
    "prior_level_atr_n": ("prior_level_rule = atr", {"levels.py"}),
    "sl_buffer_sigma": ("rr_step = True", {"method.py"}),
    "min_rr": ("rr_step = True", {"method.py"}),
    "max_attempts": ("wave_gates = True", {"engine.py"}),
    "accept_closes": ("break_rule = closes / liquidity_rule = sigma", {"levels.py", "liquidity.py"}),
    "liquidity_eq_sigma": ("liquidity_rule = sigma", {"levels.py", "liquidity.py"}),
    "liquidity_lookback": ("liquidity_rule = sigma (method: the pullback's / leg's own window)", {"engine.py", "dossier.py"}),
    "candle_avg_n": ("candle_rule = ratio", {"method.py"}),
    "commit_body": ("candle_rule = ratio", {"method.py"}),
    "commit_close_frac": ("candle_rule = ratio", {"method.py"}),
    "pin_wick_min": ("candle_rule = ratio", {"method.py"}),
    "star_body_max": ("candle_rule = ratio", {"method.py"}),
    "tweezer_tol": ("candle_rule = ratio", {"method.py"}),
    "doji_body_max": ("candle_rule = ratio", {"method.py"}),
    "pattern_eq_mr": ("candle_rule = ratio", {"method.py"}),
    "flip_pullback_vol_ratio": ("candle_rule = ratio (G4 context)", {"flip.py"}),
    "tl_touch_sigma": ("line_rule = sigma", {"trendline.py"}),
    "tl_min_touches": ("line_rule = sigma", {"trendline.py"}),
    "commit_merge_max": ("registered only (≤ 2 merged is the form list itself); read nowhere", set()),
    "vol_slot_sessions": ("volume_baseline = slot", {"engine.py"}),
    "vol_slot_min_sessions": ("volume_baseline = slot", {"engine.py"}),
    "active_levels_max": ("no longer caps the watch list (method §4); kept for old callers", set()),
    "watch_levels_max": ("no longer caps the watch list (method §4); kept for old callers", set()),
}
OPERATIONAL = {                  # display / chart / ticket formatting, never a reading decision
    "show_distance_sigma", "chart_old_box_sessions", "chart_leg_path_points", "chart_atr_n", "liq_marks_per_side", "entry_tick",
    "score_daily_bonus", "score_fresh_bonus", "score_test_penalty",
}
DATA_QUALITY = {                 # is there enough / complete data (method §1 P1 allows data-quality checks)
    "weekly_min_bars", "daily_min_sessions", "daily_sigma_sessions", "vol_gap_max_frac", "flip_vol_min_coverage",
}
CALIBRATION = {                  # Abhi (layer 1 ✅): a swing's significance is judged against the market's own normal movement (σ) at
                                 # the scale he chose from his own charts — his visual calibration, not a fixed point value: {setting: source}
    "level_degree": "the zone's structure = the approved D2 (1H trend degree)",
    "tl_degree": "one degree below the zone's structure = the approved D1 (the pullback's legs)",
    "flip_pullback_inner_degree": "one degree below the zone's structure = the approved D1",
    "daily_pivot_n": "Abhi's daily spec (N = 2)",
    "k_reset_sigma": "Abhi's rule (a new extreme moved less than this × σ_1H is the same extreme)",
    "range_eq_sigma_d": "assumed on the same σ scale, not picked by Abhi from charts (OPEN_QUESTIONS L1-b)",
    "maturity_sigma_d": "assumed on the same σ scale, evidence only (OPEN_QUESTIONS L1-b)",
}
PENDING = {                      # still a number in the reading path ⇒ removed in the named layer
    "evidence_weights": 6, "conv_a": 6, "conv_b": 6, "conv_weak": 6,
    # ④ power shift: its count still DECIDES verdicts through the evidence score (`ev["power_shift"]` ⇒ `conviction` weights ⇒ A / B /
    # weak / against) until layer 6 removes the score (method §4 / §5: evidence listed, never scored); §5.3 range state = context only
    # (`range_state_gate` off). Both go with the evidence in layer 6.
    "power_shift_min": 6, "power_overlap": 6, "power_fallback_bars": 6, "range_overlap_min": 6, "range_state_n": 6,
    # decision3 reads touch_window_bars only behind the legacy visit rules, but facts/dossier `_visits` still counts it (layer 6)
    "touch_window_bars": 6,
}


def _numeric(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)) or isinstance(v, dict)


def test_every_reading_number_is_classified():
    nums = {k for k, v in S3.DEFAULTS.items() if _numeric(v)}
    classified = set(LEGACY) | OPERATIONAL | DATA_QUALITY | set(CALIBRATION) | set(PENDING)
    assert not (nums - classified), f"unclassified numbers in the reading path (method P1): {sorted(nums - classified)}"
    groups = [set(LEGACY), OPERATIONAL, DATA_QUALITY, set(CALIBRATION), set(PENDING)]
    assert all(not (a & b) for i, a in enumerate(groups) for b in groups[i + 1:]), "a setting is in two classes"
    assert not (classified - nums - {"level_min_width_sigma"}), f"stale entries: {sorted(classified - nums)}"


def test_legacy_numbers_are_read_only_where_their_switch_lives():
    """A LEGACY number must not leak into the default path: only the files named with its switch may read it (source scan)."""
    src = {f.name: f.read_text(encoding="utf-8") for f in D3.glob("*.py") if f.name != "settings.py"}
    src["dossier.py"] = (D3.parent / "facts" / "dossier.py").read_text(encoding="utf-8")   # the vision facts read the same owners
    for k, (_, allowed) in LEGACY.items():
        readers = {n for n, txt in src.items() if re.search(rf"[\"']{k}[\"']", txt)}
        assert readers <= allowed, f"{k} ({LEGACY[k][0]}) is read outside its switch: {sorted(readers - allowed)} — classify it PENDING"


def test_layer_two_reading_rules_are_logic():
    """Layer 2 (areas + lifecycle) defaults: structure / comparison rules; their old numbers are legacy what-ifs (or, where another
    module still reads them on the default path, pending with that module's layer)."""
    d = S3.DEFAULTS
    assert (d["break_rule"], d["liquidity_rule"], d["prior_level_rule"], d["level_merge"], d["trade_band_max_sigma"]) == \
        ("structure", "equal", "all", False, None)
    assert d["level_min_width_sigma"] == 0.0
    for k in ("prior_level_atr_mult", "prior_level_atr_n", "active_levels_max", "watch_levels_max", "level_min_width_sigma"):
        assert k in LEGACY
    assert "accept_closes" in LEGACY and "liquidity_eq_sigma" in LEGACY and not [k for k, layer in PENDING.items() if layer == 2]


def test_layer_three_reading_rules_are_logic():
    """Layer 3 (zone study, commitment, LTF): visit / handover / absorption / commitment / candle forms / volume / liquidity by structure
    and comparison; session windows out of the reading (P2); no layer-3 number left pending."""
    d = S3.DEFAULTS
    assert (d["zone_visit_rule"], d["fast_form_rule"], d["slow_form_rule"], d["absorption_rule"], d["commit_volume_rule"],
            d["volume_baseline"], d["candle_rule"], d["session_windows"]) == \
        ("structure", "push_body", "method", "method", "approach_and_opposite", "raw", "compare", False)
    assert not [k for k, layer in PENDING.items() if layer == 3]


def test_layer_four_lines_are_logic():
    """Layer 4 (lines + confluence): touch by the candle, two separate reactions, confluence labels the area — no σ tolerance or count."""
    assert S3.DEFAULTS["line_rule"] == "logic" and not [k for k, layer in PENDING.items() if layer == 4]


def test_layer_one_swings_are_abhis_calibration():
    """Abhi (layer 1 ✅): the approved swings2 D1 / D2 ARE the swing definition — significance against the market's own normal movement
    at his calibrated scale. Nothing of layer 1 stays PENDING; the scale is a registered calibration setting (advanced dashboard)."""
    from swings2 import settings as SS
    assert not [k for k, layer in PENDING.items() if layer == 1]
    assert SS.DEFAULTS["k"][1] == 4.0 and SS.DEFAULTS["k"][2] == 6.0 and "calibration" in SS.REGISTER["k"][2]
    assert S3.DEFAULTS["swing_k"] is None and "calibration" in S3.REGISTER["swing_k"][2]



def test_v22_hands_the_calibrated_scale_to_swings2(monkeypatch):
    """`swing_k` (advanced dashboard) reaches swings2.build as its `k`; None ⇒ swings2's own approved scale."""
    import pandas as pd
    import pytest
    from swings2 import engine as SE
    from decision3 import engine as E3
    seen = []

    class Stop(Exception):
        pass

    def build(m15, df1m=None, s=None, m1_status_map=None):
        seen.append(s)
        raise Stop
    monkeypatch.setattr(SE, "build", build)
    m15 = pd.DataFrame({"timestamp": pd.to_datetime(["2030-01-01 09:15"]), "bar_end": pd.to_datetime(["2030-01-01 09:30"]),
                        "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})
    for s, want in ((None, None), ({"swing_k": {1: 5.0, 2: 8.0}}, {"k": {1: 5.0, 2: 8.0}})):
        with pytest.raises(Stop):
            E3.V22(m15, s=s)
        assert seen[-1] == want
