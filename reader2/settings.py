"""reader2/settings.py — Chart Reader v2 चे आकडे आणि register (आकडा, default, पर्याय, वर्ग, स्रोत). REGISTER च्या keys = DEFAULTS च्या keys.

सगळी मापं त्याच timeframe च्या median range (MR) units मध्ये किंवा unit-नसलेली गुणोत्तरं (body ÷ range, MR ÷ MR) — points / % नाहीत.
"अंदाज" आकडे फक्त dev gallery (Abhi च्या labels) वर calibrate करायचे (spec §5) — trade निकालांवर कधीच नाही. आत्ता tuning नाही.
"""
from legs2 import settings2 as LS2

# candle feature (फक्त lowest degree) ⇒ (corrective टोक, impulsive टोक, बाजू). बाजू: "both" = [−1, +1]; "imp" = फक्त [0, +1];
# "cor" = फक्त [−1, 0]. एकतर्फी feature चा 0 (पुरावा नाही) सरासरीत मोजत नाही. impulsive टोक < corrective टोक ⇒ उलटं माप.
FEATURES = {
    "body": (0.35, 0.55, "both"),            # सरासरी body ÷ range
    "close_loc": (0.50, 0.68, "both"),       # सरासरी CLV_d (leg दिशेच्या टोकाजवळ close)
    "overlap": (0.60, 0.35, "both"),         # आधीच्या candle शी overlap ÷ range (कमी ⇒ आवेगी)
    "displacement": (0.0, 0.25, "imp"),      # (displacement + FVG candles) ÷ bars
    "range": (0.85, 1.30, "both"),           # सरासरी range ÷ MR (leg सुरुवातीचा)
    "contraction": (0.70, 1.00, "cor"),      # उत्तरार्धाची सरासरी range ÷ पूर्वार्धाची (आकुंचन ⇒ सुधार)
    "er": (0.30, 0.60, "both"),              # efficiency ratio (legs2 व्याख्या)
    "wick_opp": (0.30, 0.15, "both"),        # leg-दिशेच्या टोकाकडची wick ÷ range (कमी ⇒ आवेगी)
    "wick_both": (0.50, 0.20, "both"),       # दोन्ही बाजूंना ≥ wick_both_min wick असलेल्या candles चं प्रमाण
    "volume": (0.83, 1.20, "both"),          # leg volume / bar ÷ आधीच्या counter-move चा (legs2 v_lo / v_hi)
    "effort_result": (1.50, 1.00, "cor"),    # volume गुणोत्तर ÷ वेग (MR / bar) गुणोत्तर — effort without result
    "pause_depth": (0.60, 0.30, "cor"),      # एका swing मधली सर्वात खोल उलट चाल ÷ leg आकार (उथळ ⇒ पुरावा नाही: choppy drift सुद्धा उथळ)
    "stall": (0.50, 0.25, "cor"),            # नवीन टोकाशिवायचा सर्वात लांब काळ ÷ bars (sideways)
}

# वरच्या degree चा anatomy = sub-legs (एक degree खाली) चा roll-up (spec §2d). "motive" / "counter" आधीच [−1, +1] scores.
ROLLUP = {
    "pause_time": (0.55, 0.35, "both"),      # counter sub-legs चे bars ÷ leg चे bars (थोडक्यात थांबा ⇒ आवेगी)
    "pause_depth": (0.80, 0.50, "both"),     # counter sub-legs ची एकूण चाल ÷ motive sub-legs ची एकूण चाल (उथळ ⇒ आवेगी; choppy ⇒ सुधार)
    "c_like_a": (0.85, 0.60, "cor"),         # शेवटचा push vs आधीचा सर्वात मजबूत push: साम्यता (candle score × वेग × आकार): c ≈ a ⇒ सुधार
    "b_brief": (1.50, 0.60, "both"),         # counter sub-leg चे bars ÷ आधीच्या push चे bars (wave 2/4 थोडके ⇒ आवेग; zigzag b लांब ⇒ सुधार)
}

_L2 = LS2.load()                                          # MASTER trend / displacement / climax व्याख्या (swings2 मार्गे legs2)

DEFAULTS = {
    "mr_bars": 20,                    # median range: शेवटचे इतके bars (त्या bar सकट)
    "mr_min_bars": 10,                # यापेक्षा कमी ⇒ MR = NaN (warm-up)
    "intraday_max_spacing_hours": 20,  # bars मधलं median अंतर यापेक्षा कमी ⇒ intraday (session पहिला bar ⇒ overnight gap वगळा)
    "dc_k": (2.0, 4.0, 8.0),          # degree 0, 1, 2 चे directional-change threshold (× MR)
    "trend_degree": 2,                # trend / protected origin या degree च्या legs वरून
    "reread_k_mult": (0.9, 0.75, 0.6),  # re-read: sub-leg degree च्या dc_k चे गुणक — फक्त एक degree खाली (त्याखालच्या dc_k च्या वर); बहुमत (2 / 3)
    "short_leg_bars": LS2.DEFAULTS["short_leg_bars"],   # ≤ इतके bars ⇒ candle anatomy NA (legs2 नियम)
    "min_features": 4,                # यापेक्षा कमी पुरावा देणारे features ⇒ candle anatomy NA
    "contraction_min_half": 2,        # contraction: प्रत्येक अर्ध्यात किमान इतके bars
    "a_hi": 0.25,                     # anatomy ≥ a_hi ⇒ impulsive
    "a_lo": -0.25,                    # anatomy ≤ a_lo ⇒ corrective
    "s_decisive": 0.5,                # |structure vote| ≥ इतका ⇒ निर्णायक
    "three_wave_vote": -0.25,         # read_counter "3-wave" (न वाचलेली मोजणी, 5 / 9 सकट) ⇒ कमकुवत, निर्णायक नाही (< s_decisive)
    "wick_both_min": 0.20,            # wick_both: दोन्ही wicks ≥ इतके × range
    "v_min_reliable": LS2.DEFAULTS["v_min_reliable"],   # volume: दोन्ही legs मध्ये किमान इतके volume bars
    "lower_weight": 0.5,              # खालच्या TF (उदा. 1H) च्या candle anatomy चं वजन (lowest degree)
    "max_passes": 3,                  # self-check passes (spec §3)
    "weights": {k: 1.0 for k in FEATURES},
    "features": FEATURES,
    "rollup": ROLLUP,
    "rollup_weights": {"motive": 2.0, "counter": 1.0, "pause_time": 1.0, "pause_depth": 1.0, "c_like_a": 1.0, "b_brief": 1.0,
                       "middle_push": 1.0},
    "rollup_pause_min_counters": 2,   # थांब्यांचा पुरावा फक्त ≥ इतके counter sub-legs असताना (waves 2 आणि 4); एक थांबा = zigzag चा b सुद्धा
    "rollup_veto_share": 0.25,        # motive चालीचा ≥ इतका वाटा असलेला सुधारात्मक motive sub-leg ⇒ leg आवेगी वाचत नाही (big-c zigzag चा a)
    "trend_body": _L2["trend_body"],
    "trend_clv": _L2["trend_clv"],
    "disp_rng_ratio": _L2["disp_rng_ratio"],
    "disp_body": _L2["disp_body"],
    "disp_wick_opp": _L2["disp_wick_opp"],
    "climax_rng_ratio": _L2["climax_rng_ratio"],
}

REGISTER = {
    "mr_bars": (20, "14/20/30", "अंदाज", "legs2 rvol_sessions / σ_D सारखं; spec: MR units"),
    "mr_min_bars": (10, "—", "व्याख्या", "warm-up"),
    "intraday_max_spacing_hours": (20, "—", "व्याख्या", "Daily (24 h) आणि intraday वेगळं करण्यासाठी"),
    "dc_k": ("2/4/8", "1.5/3/6, 2.5/5/10", "अंदाज", "degree = पट; dev gallery वर calibrate"),
    "trend_degree": (2, "1/2", "अंदाज", "spec §2d: leg त्याच्या degree वर"),
    "reread_k_mult": ("0.9/0.75/0.6", "—", "व्याख्या", "spec §3.1 alternative pivots one degree lower; तीन पर्याय, निर्णय बहुमताने 2 / 3"),
    "short_leg_bars": (2, "—", "व्याख्या", "legs2 settings2"),
    "min_features": (4, "3/4/6", "अंदाज", "—"),
    "contraction_min_half": (2, "—", "व्याख्या", "अर्ध्यात 1 bar ⇒ गुणोत्तर अर्थहीन"),
    "a_hi": (0.25, "0.15/0.35", "अंदाज", "spec §5: dev gallery वर calibrate"),
    "a_lo": (-0.25, "−0.15/−0.35", "अंदाज", "spec §5: dev gallery वर calibrate"),
    "s_decisive": (0.5, "—", "व्याख्या", "named pattern (±1) निर्णायक"),
    "three_wave_vote": (-0.25, "0/−0.25", "व्याख्या", "न वाचलेली मोजणी निर्णायक नाही (|vote| < s_decisive)"),
    "wick_both_min": (0.20, "0.15/0.2/0.3", "अंदाज", "—"),
    "v_min_reliable": (3, "—", "व्याख्या", "legs2 settings2"),
    "lower_weight": (0.5, "0.3/0.5", "अंदाज", "spec §2d: Daily + 1H candles"),
    "max_passes": (3, "—", "Abhi", "spec §3"),
    "weights": ("सगळे 1", "—", "अंदाज", "candle features समान वजन"),
    "features": ("FEATURES", "±1 पायरी", "अंदाज", "spec §2b; volume = legs2 v_lo / v_hi (NexusFi)"),
    "rollup": ("ROLLUP", "±1 पायरी", "अंदाज", "spec §2b pause (shallow, brief) — sub-leg पातळीवर"),
    "rollup_weights": ("2/1/1/1/1/1/1", "—", "अंदाज", "motive sub-legs मुख्य; बाकी candle पुरावे समान"),
    "rollup_pause_min_counters": (2, "—", "व्याख्या", "एका थांब्यावरून impulse आणि zigzag (a-b-c) वेगळे होत नाहीत"),
    "rollup_veto_share": (0.25, "0.2/0.25/0.33", "अंदाज", "एक लहान आळशी push (उदा. टोकाजवळचा wave 1) impulse रद्द करत नाही; मोठा करतो"),
    "trend_body": (_L2["trend_body"], "—", "व्याख्या", "swings2 / MASTER §3 trend candle"),
    "trend_clv": (_L2["trend_clv"], "—", "व्याख्या", "swings2 / MASTER §3 trend candle"),
    "disp_rng_ratio": (_L2["disp_rng_ratio"], "—", "research-practitioner", "swings2 / MASTER §3 displacement"),
    "disp_body": (_L2["disp_body"], "—", "research-practitioner", "swings2 / MASTER §3 displacement"),
    "disp_wick_opp": (_L2["disp_wick_opp"], "—", "research-practitioner", "swings2 / MASTER §3 displacement"),
    "climax_rng_ratio": (_L2["climax_rng_ratio"], "—", "व्याख्या", "legs2 settings2 / MASTER §3 climax"),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k, v in (overrides or {}).items():
        if k in s and isinstance(s[k], dict) and isinstance(v, dict):
            s[k].update(v)
        else:
            s[k] = v
    return s


def is_loaded(s):
    return bool(s) and set(DEFAULTS) <= set(s)
