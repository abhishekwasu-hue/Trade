"""Abhi's method (docs/knowledge/CHART_READER_METHOD.md §1 P1, §6, §7): no numeric thresholds in the reading path.

Every numeric default of the decision3 reading engine must be classified. Numbers allowed to stay are legacy what-if switches that are
off by default, operational / display settings, or data-quality checks. Every other number is `PENDING` with the layer PR that removes
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
    "active_levels_max": ("no longer caps the watch list (method §4); kept for old callers", set()),
    "watch_levels_max": ("no longer caps the watch list (method §4); kept for old callers", set()),
}
OPERATIONAL = {                  # display / chart / ticket formatting, never a reading decision
    "show_distance_sigma", "chart_old_box_sessions", "chart_leg_path_points", "chart_atr_n", "liq_marks_per_side", "entry_tick",
    "score_daily_bonus", "score_fresh_bonus", "score_test_penalty",
}
DATA_QUALITY = {                 # is there enough / complete data (method §1 P1 allows data-quality checks)
    "weekly_min_bars", "daily_min_sessions", "daily_sigma_sessions", "vol_gap_max_frac",
}
PENDING = {                      # still a number in the reading path ⇒ removed in the named layer
    "daily_pivot_n": 1, "range_eq_sigma_d": 1, "maturity_sigma_d": 1, "level_degree": 1, "tl_degree": 1,
    "flip_pullback_inner_degree": 1, "k_reset_sigma": 1,
    "power_shift_min": 3, "power_overlap": 3, "power_fallback_bars": 3, "pattern_eq_mr": 3, "commit_body": 3, "commit_merge_max": 3,
    "pin_wick_min": 3, "star_body_max": 3, "tweezer_tol": 3, "commit_close_frac": 3, "touch_window_bars": 3, "candle_avg_n": 3,
    "doji_body_max": 3, "range_overlap_min": 3, "range_state_n": 3, "liquidity_lookback": 3, "flip_pullback_vol_ratio": 3,
    "flip_vol_min_coverage": 3, "vol_slot_sessions": 3, "vol_slot_min_sessions": 3,
    "accept_closes": 3, "liquidity_eq_sigma": 3,  # legacy in levels (break_rule / liquidity_rule), still read by liquidity.sweeps_and_traps
    "tl_touch_sigma": 4, "tl_min_touches": 4,
    "evidence_weights": 6, "conv_a": 6, "conv_b": 6, "conv_weak": 6,
}


def _numeric(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)) or isinstance(v, dict)


def test_every_reading_number_is_classified():
    nums = {k for k, v in S3.DEFAULTS.items() if _numeric(v)}
    classified = set(LEGACY) | OPERATIONAL | DATA_QUALITY | set(PENDING)
    assert not (nums - classified), f"unclassified numbers in the reading path (method P1): {sorted(nums - classified)}"
    groups = [set(LEGACY), OPERATIONAL, DATA_QUALITY, set(PENDING)]
    assert all(not (a & b) for i, a in enumerate(groups) for b in groups[i + 1:]), "a setting is in two classes"
    assert not (classified - nums - {"level_min_width_sigma"}), f"stale entries: {sorted(classified - nums)}"


def test_legacy_numbers_are_read_only_where_their_switch_lives():
    """A LEGACY number must not leak into the default path: only the files named with its switch may read it (source scan)."""
    src = {f.name: f.read_text(encoding="utf-8") for f in D3.glob("*.py") if f.name != "settings.py"}
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
    assert PENDING["accept_closes"] == PENDING["liquidity_eq_sigma"] == 3 and not [k for k, layer in PENDING.items() if layer == 2]
