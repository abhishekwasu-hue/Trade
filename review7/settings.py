"""review7/settings.py — review दृश्याचे आकडे (निर्णय नाही; फक्त chart वरच्या खुणा) आणि "अंदाज" register."""

DEFAULTS = {
    "touch_window": 3,           # ② area स्पर्श: शेवटच्या इतक्या 15M bars मध्ये (commitment merge_max इतकं)
    "episode_gap": 3,            # एकच चाचणी: ①②③ मध्ये इतक्या bars पर्यंतचा खंड चालतो; पुढे ⇒ चाचणी बंद
    "shrink_n": 3,               # ④ candle-size shrink: शेवटच्या n candles चा सरासरी range
    "shrink_prior": 6,           #    त्याआधीच्या इतक्या candles च्या सरासरीच्या
    "shrink_ratio": 0.75,        #    ≤ या पटीत ⇒ shrink
    "line_tol_sigma": 0.25,      # ② तिरकी रेघ: रेघ ± इतके σ = पट्टा
    "sl_buffer_sigma": 0.1,      # SL = area / swing पलीकडे + इतके σ
    "plan_areas": 3,             # B2: जवळचे इतके trade-बाजूचे areas
}

REGISTER = {
    "touch_window / episode_gap": ("3 / 3 bars", "2–4", "अंदाज (review दृश्य)", "B1 ② / एका चाचणीला एक बाण"),
    "shrink_n / shrink_prior / shrink_ratio": ("3 / 6 / 0.75", "—", "अंदाज (review दृश्य)", "B1 ④ candle-size shrink"),
    "line_tol_sigma": ("0.25 σ", "0.15–0.35", "थर 5 τ शी जुळतं", "B1 ② तिरकी रेघ"),
    "sl_buffer_sigma": ("0.1 σ", "—", "अंदाज (review दृश्य)", "B1 ✅ / B2 SL"),
    "plan_areas": ("3", "2–3", "Abhi (B2)", "B2 जवळचे areas"),
}


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
