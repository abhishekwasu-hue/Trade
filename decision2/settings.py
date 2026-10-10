"""decision2/settings.py — थर 7 चे आकडे, settings आणि "अंदाज" register (थर 7 §6a). Dashboard settings (sl_buffer, tier, gray_policy …)
इथे default; बदल फक्त Abhi-मंजूर batch PR / dashboard."""
from elliott import settings as ES

DEFAULTS = {
    # regime (§2)
    "h1_window": 20, "trend_h": 6.0, "trend_net": 0.5, "range_net": 0.3, "barbwire": 0.5, "transition_bars": 5,
    "htf_unknown_action": "grade",               # grade (−1) / block
    "gray_policy": "block",                      # block / reduce (+ Abhi दिशा data row)
    # commitment candle (§4)
    "tier": 1,                                   # 1: G1–G6 + G8 hard, G7 grade (Abhi); 2 = पुढची candle confirm (setting)
    "g3_clv": 0.67, "g4_wick": 0.5, "g4_body": 0.6, "g5_rng": 1.0, "g6_overlap3": 0.6,
    "merge_max": 3, "entry_start": "09:30", "entry_end": "15:15",
    "break_entry_mode": "break_candle",          # break_candle (Abhi) / retest
    "tl_break_n": 6,
    # risk (§5)
    "invalidation_mode": "auto",                 # auto (structural जेव्हा candle लहान / overlap3 ≥ 0.6) / candle / structural / farther
    "sl_buffer": 0.0,                            # dashboard setting (अंक)
    "target_mode": "I_end",                      # I_end / opposite_edge / measured_move / opposite_zone
    "min_rr": 3.0,
    "room_mode": "vix",                          # vix (VIX/16 × √2 %) / realised (20-session 2-day move)
    "premium_lo": 0.60, "premium_hi": 0.80,
    "expiry_exit_time": "13:00",
    "min_sessions_to_expiry": 2,
    # risk regime (§3 G-I, §6)
    "vix_extreme": 22.0, "vix_lo": 11.0, "vix_hi": 18.0, "vix_jump": 0.10,      # VIX = फक्त size (gate नाही, Abhi उत्तर 14)
    "macro_against": 0.5, "macro_size": 0.75,    # macro row trade-विरुद्ध ⇒ size
    "macro_max_age_h": 24,                       # macro row इतक्या तासांपेक्षा जुनी ⇒ NA (VIX: फक्त त्याच session ची)
    "size_floor": 0.5, "vix_size": 0.75, "reduce_size": 0.5,
    # grade (§6)
    "grade_a": 6.0, "grade_b": 4.0,
    "w_cap": 1.0, "w_onk": 1.0, "w_rik": 0.5, "w_trap": -1.0, "w_cascade": -1.0, "w_flavour": 1.0, "w_g7": 1.0, "w_q": 0.5,
    "w_g4both": 0.5, "w_quiet": 0.5, "w_heavy": -1.0, "w_flag": -1.0, "w_s5": -1.0, "w_disagree": -1.0, "w_d2d3": 0.5,
    "w_open": -0.5, "w_steep": -0.5, "w_htf_unknown": -1.0, "retrace_flavour": 0.80,
    "signal_approval_required": True,
    # vision (§8)
    "vision_evidence_penalty": 0.5, "vision_fail_action": "keep_code",
}

# D2 must-hold real break (MASTER पातळी 2; हा थर मोजतो) — elliott/breaks.py, गोठवलेली प्रत, नाव register मध्ये
MUST_HOLD_BREAK = dict(ES.DEFAULTS)

REGISTER = {
    "h1_window / trend_h / trend_net": ("20 / 6 σ_1H / 0.5", "4–8 / 0.4–0.6", "अंदाज", "थर 7 §2"),
    "range_net / barbwire": ("0.3 / 0.5 σ_1H", "±0.1", "अंदाज (Brooks)", "थर 7 §2"),
    "transition_bars": ("5", "3/5/8", "अंदाज", "थर 7 §2"),
    "htf_unknown_action": ("grade −1", "grade / block", "setting", "थर 7 §2"),
    "gray_policy": ("block", "block / reduce", "Abhi (review loop data row)", "थर 7 G-A"),
    "tier": ("1", "0/1/2", "Abhi (default 1; 2 = setting — पुढच्या candle ची वाट theta खातो)", "थर 7 §4"),
    "g3_clv / g4_wick / g4_body / g5_rng / g6_overlap3": ("0.67 / 0.5 / 0.6 / 1.0 / 0.6", "±0.1", "research / अंदाज", "थर 7 §4"),
    "merge_max / entry_start / entry_end": ("3 / 09:30 / 15:15", "—", "MASTER / NSE", "merged candle, वेळ"),
    "break_entry_mode / tl_break_n": ("break_candle / 6", "retest; 4/6/8", "Abhi ✔", "थर 7 §4 trendline-break: area ≤ N candles आधी"),
    "invalidation_mode / sl_buffer": ("auto / dashboard", "candle / structural / farther", "setting", "थर 7 §5"),
    "target_mode / min_rr": ("I_end / 3", "—", "Abhi", "थर 7 §5 R:R ≥ 3"),
    "room_mode / premium_lo / premium_hi": ("vix / 60–80%", "realised", "Abhi / research", "थर 7 §5"),
    "expiry_exit_time / min_sessions_to_expiry": ("13:00 / 2", "12:30–14:00 / 1–3", "अंदाज", "थर 7 §5, G-H"),
    "vix_extreme / vix_lo / vix_hi / vix_jump": ("22 / 11 / 18 / +10%", "±2", "अंदाज", "VIX फक्त size (Abhi उत्तर 14; gate नाही)"),
    "macro_against / macro_size": ("0.5 / ×0.75", "0.3–0.7", "अंदाज", "macro row फक्त size / नोंद (Abhi उत्तर 14)"),
    "macro_max_age_h": ("24 तास", "12/24/48", "अंदाज", "जुनी macro row ⇒ NA; VIX फक्त त्याच session चा (staleness)"),
    "size_floor": ("0.5", "0.4/0.5/0.6", "अंदाज", "थर 7 §6"),
    "vix_size / reduce_size": ("0.75 / 0.5", "—", "Abhi (prompt)", "थर 7 §6: VIX > 18 ×0.75, > 22 ⇒ floor; transition / gray / event ×0.5"),
    "grade_a / grade_b": ("6 / 4", "±1", "अंदाज", "थर 7 §6"),
    "w_cap w_onk w_rik w_trap w_cascade w_flavour w_g7 w_q w_g4both w_quiet w_heavy w_flag w_s5 w_disagree w_d2d3 w_open "
    "w_htf_unknown": ("§6 यादी", "±0.5", "अंदाज", "थर 7 §6 grade वजनं"),
    "w_steep": ("−0.5", "—", "Abhi (उत्तर 11)", "तीव्र trade-योग्य रेघ ⇒ grade कमी"),
    "retrace_flavour": ("0.80", "0.786/0.80/0.85", "MASTER", "retrace खूण ⇒ फक्त sweep-reclaim / throw-over"),
    "signal_approval_required": ("True", "—", "setting", "📌 SETUP Approve / Reject"),
    "vision_evidence_penalty / vision_fail_action": ("0.5 / keep_code", "—", "अंदाज / setting", "थर 7 §8"),
    "must_hold_break (breaks.py settings)": ("elliott.settings DEFAULTS", "±1 पायरी", "code (MR ≠ σ)", "MASTER: D2 must-hold थर 7"),
}


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
