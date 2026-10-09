"""simple_core/settings.py — (1) engine detection आकडे (MR च्या पटीत; dashboard वर) आणि (2) execution settings store.

Execution settings ला **default नाही**: profile मध्ये जे निवडलं तेच; काही निवडलं नसेल तर trade नाही (execution.plan स्पष्ट संदेश देतो).
Store = JSON (`SIMPLE_CORE_EXEC_PATH`, default data/simple_core_exec.json) — {profile: {settings…}}; प्रत्येक trade मध्ये settings hash.
"""
import copy
import hashlib
import json
import os

ENGINE_DEFAULTS = {
    # टप्पा B (Abhi G-MAP1, 2026-10-09) — dashboard / paper_core profile मधूनही (ENGINE_FROM_PROFILE)
    "parent_source": "market_state",   # market_state (default) / preferred_count (count_source; नसेल ⇒ PARENT_UNKNOWN ⇒ trade नाही)
    "g10_enabled": True,           # G10 range कड signals तयार करायचे का
    "g10_mode": "shadow",          # shadow ⇒ PAPER trade नाही, फक्त नोंद + Telegram माहिती (Approve नाही) / paper
    "eod_signal_carry": "recheck",  # 15:15 चा signal ⇒ दुसऱ्या दिवशी आपोआप entry नाही (नकाशा S12)
    "g10_range_bars": 400,         # G10: 15M StructureTracker मागचे इतके bars (zones.zone_lookback_bars सारखंच, ~16 sessions) [व्याख्या]
    "area_tol_mr": 0.3,            # area ला "लागला" = candle चं टोक area च्या ± हे × MR
    "area_merge_mr": 0.5,          # trade बाजूचे zones इतक्या × MR अंतरात ⇒ एकच area (उदा. TL + swing high = "TL3+H 22,700–22,730")
    "pause_body_max": 0.5,         # pause (indecision): body ≤ range च्या हे …
    "pause_range_max_mr": 1.0,     # … किंवा range ≤ हे × MR (median पेक्षा लहान) …
    "pause_wick_min": 0.2,         # … किंवा दोन्ही बाजूंचे wicks ≥ range च्या हे
    "pause_min_bars": 1,           # commitment आधी area वर किमान इतके pause bars
    "pause_lookback": 12,          # pause शोध: commitment आधीचे कमाल इतके bars
    "commit_strength_min_mr": 1.2,  # commitment (1 किंवा touch-pause + 1 bars) range ≥ हे × MR (elliott strength_min सारखं) …
    "commit_strength_max_mr": 2.5,  # … ≤ हे × MR (news spike नाही)
    "commit_body_min": 0.5,        # body ≥ range च्या हे
    "commit_close_max": 0.3,       # close टोकाजवळ: bear close location ≤ हे (bull ≥ 1 − हे)
    "commitment_vs_pause": 1.5,    # commitment range ≥ हे × pause bars ची सरासरी range [अनुमान, Evening plan §5 — K-10 / IS वर तपासायचं]
    "accept_buf_mr": 0.25,         # area कडेपलीकडचा close (break तपासणी सुरू); real break = elliott/breaks.py (accept_bars काढला — G-MAP1 निर्णय 8)
    "opening_block_min": 15,       # 09:15 + हे मिनिटं पर्यंत बंद होणाऱ्या bars वर signal नाही
    # Motive wave context (waves.py, KB भाग H G1 / G8 / G9) — label व reference levels फक्त; entry चे 4 टप्पे तसेच
    "wave_lookback_pivots": 12,    # trade-degree swings पैकी मागचे इतके (origin शोध)
    "g8_retrace_max": 0.382,       # G8: wave 3 मधला pullback ≤ हे (KB 23.6–38.2%) …
    "g8_retrace_tol": 0.05,        # … + हे सहनशीलता
    "g8_max_bars": 6,              # … आणि ≤ इतके bars (KB "जलद, 2–6 candles")
    "w3_proj": 1.618,              # wave3_projection = wave 2 end + हे × wave 1 [guideline, K7]
    "w3_proj_alts": (1.0, 2.618),
    "w5_proj_w1": 1.0,             # wave5_projection = wave 4 end + हे × wave 1 …
    "w5_proj_w13": 0.618,          # … पर्याय: + हे × (wave 1 start → wave 3 end)
    "wave1_zone_mr": 0.15,         # wave 1 टोकाचा flip area = टोक ± हे × MR
    # G8 flag channel (flags.py, Abhi 28 Sep) [अनुमान — K-10 / IS वर तपासायचं]
    "flag_min_bars": 2,            # G8 flag: 2–6 candles (KB H, Abhi; नकाशा S5) — कमाल g8_max_bars. 1 candle ⇒ setup नाही
    "flag_retrace_max": 0.5,       # flag ची खोली ≤ हे × impulse (उथळ)
    "flag_overlap_min": 0.6,       # overlapping (K10.1 correction overlap)
    "flag_min_touches": 2,         # प्रत्येक रेषेला किमान touches
    "flag_slope_tol_mr": 0.05,     # trend दिशेने slope ≤ हे × MR प्रति bar (सपाट चालतो)
}

SL_MODES = ("structural_invalidation", "commitment_extreme", "wave1_origin", "subwave_origin", "wave1_extreme", "fixed_points", "percent",
            "none")
TARGET_MODES = ("next_opposite_area", "impulse_end", "wave3_projection", "wave5_projection", "r_multiple", "premium_pct", "none")
G9_TIERS = ("full", "half", "C", "skip")
ENGINE_FROM_PROFILE = ("parent_source", "g10_enabled", "g10_mode", "eod_signal_carry")   # profile ⇒ engine overrides    # full ⇒ lots · half ⇒ lots ÷ 2 · C ⇒ g9_lots · skip ⇒ trade नाही
INSTRUMENTS = ("credit_spread", "futures", "naked_buy", "naked_sell")
STRIKE_MODES = ("offset_points", "beyond_sl_points", "sigma")
EXEC_FIELDS = {
    "sl_mode": SL_MODES, "sl_buffer": "number", "sl_buffer_unit": ("points", "mr"), "sl_value": "number",
    "target_mode": TARGET_MODES, "target_value": "number", "rr_filter": "bool", "min_rr": "number",
    "instrument": INSTRUMENTS, "strike_mode": STRIKE_MODES, "strike_value": "number", "strike_step": "number", "width": "number",
    "lots": "number",
    "g9_tier": G9_TIERS, "g9_lots": "number",        # G9 (wave 5, KB Tier C): full / half / C (g9_lots) / skip
    "expiry_rule": "text",
    "gray_size": ("half", "full"),   # gray reduce ⇒ lots (half = floor(lots / 2); 0 ⇒ trade नाही) — Abhi 2026-10-09
    "parent_source": ("market_state", "preferred_count"), "g10_enabled": "bool", "g10_mode": ("shadow", "paper"),
    "eod_signal_carry": ("recheck",),
}


def engine_settings(overrides=None):
    s = copy.deepcopy(ENGINE_DEFAULTS)
    s.update(overrides or {})
    return s


def settings_hash(ex):
    return hashlib.sha1(json.dumps(ex or {}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]


def _path():
    return os.environ.get("SIMPLE_CORE_EXEC_PATH") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                                                                   "simple_core_exec.json")


def load_profiles(path=None):
    p = path or _path()
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


# PAPER profile (Abhi निर्णय 2026-10-08 23:48): store मध्ये "paper_core" नसेल तर हीच मूल्यं. K-10 round 2 (SL structural + 0.25 MR,
# rr_filter on, min_rr 3) + target_mode impulse_end + g9_tier full. Instrument / strike / lots इथे नाहीत ⇒ order साठी dashboard वर
# निवडायलाच हवेत. फक्त PAPER profile; दुसऱ्या कोणत्याही profile ला (LIVE सह) default नाही.
PAPER_PROFILE = "paper_core"
PAPER_SEED = {"rr_filter": True, "min_rr": 3.0, "sl_mode": "structural_invalidation", "sl_buffer": 0.25, "sl_buffer_unit": "mr",
              "target_mode": "impulse_end", "g9_tier": "full", "gray_size": "half", "eod_signal_carry": "recheck",
              "g10_enabled": True, "g10_mode": "shadow", "parent_source": "market_state"}   # Phase B §3.5


def load_profile(name, path=None):
    """profile नसेल ⇒ {} (default भरत नाही — execution.plan "निवडलेले नाही" सांगेल). अपवाद: PAPER_PROFILE ⇒ PAPER_SEED."""
    allp = load_profiles(path)
    if name not in allp and name == PAPER_PROFILE:
        return dict(PAPER_SEED)
    return dict(allp.get(name) or {})


def validate(ex):
    """अज्ञात key / अवैध पर्याय ⇒ ValueError. रिकामे / नसलेले चालतात (default भरत नाही)."""
    bad = [k for k in ex if k not in EXEC_FIELDS]
    if bad:
        raise ValueError(f"अज्ञात settings: {bad}")
    for k, allowed in EXEC_FIELDS.items():
        v = ex.get(k)
        if v is not None and isinstance(allowed, tuple) and v not in allowed:
            raise ValueError(f"{k} = {v!r} — {allowed} पैकी हवा")
    return ex


def save_profile(name, ex, path=None):
    validate(ex)
    p = path or _path()
    allp = load_profiles(p)
    allp[name] = ex
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(allp, f, ensure_ascii=False, indent=1, sort_keys=True)
    return settings_hash(ex)
