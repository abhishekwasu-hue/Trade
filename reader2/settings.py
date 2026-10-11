"""reader2/settings.py — Chart Reader v2 चे आकडे आणि register (आकडा, default, पर्याय, वर्ग, स्रोत).

सगळी मापं त्याच timeframe च्या median range (MR) units मध्ये किंवा unit-नसलेली गुणोत्तरं (body ÷ range, MR ÷ MR) — points / % नाहीत.
"अंदाज" आकडे फक्त dev gallery (Abhi च्या labels) वर calibrate करायचे (spec §5) — trade निकालांवर कधीच नाही. आत्ता tuning नाही.
"""
from legs2 import settings2 as LS2

# feature ⇒ (corrective टोक, impulsive टोक, बाजू). बाजू: "both" = [−1, +1]; "imp" = फक्त [0, +1] (नसणं ⇒ 0, सुधार नाही);
# "cor" = फक्त [−1, 0]. impulsive टोक < corrective टोक ⇒ उलटं माप (कमी ⇒ आवेगी).
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
    "pause_depth": (0.60, 0.30, "cor"),      # सर्वात खोल आतली उलट चाल (MR) ÷ leg आकार (MR); उथळ ⇒ 0 (choppy drift मध्येही उथळ)
    "stall": (0.50, 0.25, "cor"),            # नवीन टोकाशिवायचा सर्वात लांब काळ ÷ bars (sideways); लहान ⇒ 0
}

DEFAULTS = {
    "mr_bars": 20,                    # median range: शेवटचे इतके bars (त्या bar सकट)
    "mr_min_bars": 10,                # यापेक्षा कमी ⇒ MR = NaN (warm-up)
    "dc_k": (2.0, 4.0, 8.0),          # degree 0, 1, 2 चे directional-change threshold (× MR)
    "trend_degree": 2,                # trend / protected origin या degree च्या legs वरून
    "reread_k_mult": (0.5, 0.75, 1.5),  # re-read: एक degree खालच्या threshold चे पर्यायी गुणक (alternative pivots)
    "short_leg_bars": LS2.DEFAULTS["short_leg_bars"],   # ≤ इतके bars ⇒ anatomy NA (legs2 नियम)
    "min_features": 4,                # यापेक्षा कमी उपलब्ध features ⇒ anatomy NA
    "a_hi": 0.25, "a_lo": -0.25,      # anatomy ≥ a_hi ⇒ impulsive; ≤ a_lo ⇒ corrective
    "s_decisive": 0.5,                # |structure vote| ≥ इतका ⇒ निर्णायक
    "three_wave_vote": -0.5,          # read_counter "3-wave" (नाव नसलेली 3-wave) ⇒ कमकुवत correction
    "wick_both_min": 0.20,            # wick_both: दोन्ही wicks ≥ इतके × range
    "v_min_reliable": LS2.DEFAULTS["v_min_reliable"],   # volume: दोन्ही legs मध्ये किमान इतके volume bars
    "lower_weight": 0.5,              # खालच्या TF (उदा. 1H) च्या anatomy चं वजन
    "max_passes": 3,                  # self-check passes (spec §3)
    "weights": {k: 1.0 for k in FEATURES},
    "features": FEATURES,
}

REGISTER = {
    "mr_bars": (20, "14/20/30", "अंदाज", "legs2 rvol_sessions / σ_D सारखं; spec: MR units"),
    "mr_min_bars": (10, "—", "व्याख्या", "warm-up"),
    "dc_k": ("2/4/8", "1.5/3/6, 2.5/5/10", "अंदाज", "degree = पट; dev gallery वर calibrate"),
    "trend_degree": (2, "1/2", "अंदाज", "spec §2d: leg त्याच्या degree वर"),
    "reread_k_mult": ("0.5/0.75/1.5", "—", "अंदाज", "spec §3.1 alternative pivots one degree lower"),
    "short_leg_bars": (2, "—", "व्याख्या", "legs2 settings2"),
    "min_features": (4, "3/4/6", "अंदाज", "—"),
    "a_hi / a_lo": ("0.25/−0.25", "±0.15, ±0.35", "अंदाज", "spec §5: dev gallery वर calibrate"),
    "s_decisive": (0.5, "—", "व्याख्या", "3-wave (−0.5) निर्णायक correction"),
    "three_wave_vote": (-0.5, "0/−0.5/−1", "अंदाज", "read_counter चं नाव नसलेलं 3-wave वाचन"),
    "wick_both_min": (0.20, "0.15/0.2/0.3", "अंदाज", "—"),
    "v_min_reliable": (3, "—", "व्याख्या", "legs2 settings2"),
    "lower_weight": (0.5, "0.3/0.5", "अंदाज", "spec §2d: Daily + 1H candles"),
    "max_passes": (3, "—", "Abhi", "spec §3"),
    "features (thresholds)": ("FEATURES", "±1 पायरी", "अंदाज", "spec §2b; volume = legs2 v_lo / v_hi (NexusFi)"),
}


def load(overrides=None):
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k, v in (overrides or {}).items():
        if k in ("weights", "features") and isinstance(v, dict):
            s[k].update(v)
        else:
            s[k] = v
    l2 = LS2.load()                                       # trend / displacement व्याख्या swings2 मधून (legs2 features साठी)
    for k in ("trend_body", "trend_clv", "disp_rng_ratio", "disp_body", "disp_wick_opp", "climax_rng_ratio"):
        s.setdefault(k, l2[k])
    s["_loaded"] = True
    return s
