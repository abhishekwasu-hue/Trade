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
    "evidence_weights": ("verdict_rule = score", {"method.py"}),
    "conv_a": ("verdict_rule = score", {"method.py"}),
    "conv_b": ("verdict_rule = score", {"method.py"}),
    "conv_weak": ("verdict_rule = score", {"method.py"}),
    # ④ count: decision3 reads it only under verdict_rule = score. bots_common/level_reaction (the level bots — off in one-bot mode, not
    # rebuilt here: Abhi rebuilds them in ATP) still calls M.power_shift with these defaults; that file is outside this scan.
    "power_shift_min": ("verdict_rule = score", {"method.py"}),
    "power_overlap": ("verdict_rule = score", {"method.py"}),
    "power_fallback_bars": ("verdict_rule = score", {"method.py"}),
    "range_overlap_min": ("verdict_rule = score (§5.3 range state)", {"method.py"}),
    "range_state_n": ("verdict_rule = score", {"method.py"}),
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
PENDING = {                      # still a number in the reading path ⇒ removed in the named layer
    "daily_pivot_n": 1, "range_eq_sigma_d": 1, "maturity_sigma_d": 1, "level_degree": 1, "tl_degree": 1,
    "flip_pullback_inner_degree": 1, "k_reset_sigma": 1,
    # decision3 reads touch_window_bars only behind the legacy visit rules, but facts/dossier `_visits` still counts it (layer 6)
    "touch_window_bars": 6,
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


def test_layer_six_verdict_is_the_method_no_scores():
    """Layer 6 (method §4 / §5): enter on the required set; label A = + ≥ 1 confirming piece, B = the required set only; evidence listed,
    never scored — the score, its weights and the ④ / §5.3 counts are a legacy what-if (verdict_rule = score)."""
    import inspect
    from decision3 import engine as E3
    assert S3.DEFAULTS["verdict_rule"] == "method"
    src = inspect.getsource(E3.V22._level_eval)
    i = src.index('if vrule == "score":')
    for call in ("M.power_shift(", "M.range_state("):
        assert src.index(call) > i, f"{call} runs outside the legacy score rule"
    m = src.index('if vrule == "method":')                                # the method branch ends in its own returns, before the score
    end = src.index("return M_SETUP, chk, extra", m)
    assert "M.conviction(" not in src[m:end] and src.index("M.conviction(") > end
    assert src[end:src.index("M.conviction(")].strip().startswith("return M_SETUP, chk, extra")

def test_layer_five_rsi_divergence_is_logic():
    """Layer 5 (method §3 RSI divergence): consecutive swings of one degree, a new price extreme vs an RSI that does not exceed its previous
    extreme (equal counts), RSI at the swing's own span — no bar window, no minimum RSI / price difference, no RSI zones, hidden off."""
    import inspect
    from rsi2 import engine as RE
    from rsi2 import settings as RS
    assert RS.DEFAULTS["div_bar_window"] is False and RS.DEFAULTS["div_hidden"] is False
    src = inspect.getsource(RE.Divergence)
    for key in ("min_rsi", "min_price_sigma", '"gaps"', "bull_min", "bull_max", "bull_trough", "bear_max", "bear_min", "bear_peak",
                "window_15m", "window_1h", "pivot_k", "grade_os", "grade_ob", "onk_trough", "shift_trough", "shift_peak", "edge_recent"):
        assert key not in src, f"{key}: an RSI number in the divergence reading path"
    ev = inspect.getsource(RE.Divergence._eval)
    assert ev.index("div_bar_window") < ev.index("lo, hi = self.win"), "the bar window is compared only behind the legacy switch"


def test_layer_six_evidence_list_and_label_text():
    """The evidence list says the reading (required set) apart from the operational entry hours, absent ≠ NA; the chart / caption text
    shows the method label with its confirming pieces, never a score."""
    from decision3 import method as M
    from decision3 import setup_chart as SC
    conf = {"volume_growing": None, "rsi_divergence": False, "confluence": True, "correction_line_closed_through": None}
    el = M.evidence_list({"tl_confluence": False, "fresh": True}, conf, True, in_hours=False)
    assert el["required"] == "present" and el["entry_hours"].startswith("outside")
    assert el["confirming"] == {"volume_growing": "NA", "rsi_divergence": "absent", "confluence": "present",
                                "correction_line_closed_through": "NA"} and el["context"]["tl_confluence"] == "absent"
    assert M.method_label(conf) == "A" and M.method_label({**conf, "confluence": False}) == "B"
    assert SC.label_text({"conviction": "A", "confirming": conf, "verdict_rule": "method"}) == "Label A (confirming: confluence)"
    assert SC.label_text({"conviction": "B", "conv_score": 0.5, "verdict_rule": "score"}) == "Conviction B (score 0.5)"

