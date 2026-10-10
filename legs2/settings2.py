"""legs2/settings2.py — थर 2 v2.1 चे आकडे आणि "अंदाज" register (थर 2 §6; MASTER §2: आकडा, default, पर्याय, वर्ग, स्रोत).
Test: register मध्ये नसलेला अंदाज-आकडा code मध्ये नाही. MASTER व्याख्या (trend / displacement / climax candle) swings2 settings मधून."""
from elliott import settings as ES

DEFAULTS = {
    "baseline_legs": 40,
    "baseline_min": 10,
    "c_hi": 0.60, "c_lo": 0.40,
    "v_hi": 1.20, "v_lo": 0.83,
    "v_min_reliable": 3,
    "gap_in_leg_sigma": 0.5,
    "short_leg_bars": 2,
    "rvol_sessions": 20,
    "rvol_min_sessions": 10,
    "roll_sessions_before": 2,
    "climax_rng_ratio": 2.0,
    "spike_trend_pct": 0.7, "spike_max_run": 5, "spike_overlap": 0.4, "spike_er": 0.6, "spike_fvg": 1,
    "climax_last_candles": 3,
    "sot_pushes": 3,
    "quiet_rvol": 1.2, "heavy_rvol": 1.5,
    "nature_degrees": (0, 1, 2),
    "label_degrees": (1, 2),
    "degrees": (0, 1, 2, 3),
    "ik_degrees": (1, 2),
}

# I_origin real break (MASTER break पातळी 2): elliott/breaks.first_real_break, retest_fn=None, cache नाही, MR = याच settings चा
# rolling median (σ नाही). गोठवलेली प्रत, नाव register मध्ये.
I_ORIGIN_BREAK = dict(ES.DEFAULTS)

REGISTER = {
    "baseline_legs": (40, "30/40/60", "अंदाज", "थर 2 §3 C baseline"),
    "baseline_min": (10, "—", "अंदाज", "थर 2 §3: 10–39 ⇒ warmup; < 10 ⇒ NA"),
    "c_hi / c_lo": ("0.6/0.4", "0.55/0.45, 0.65/0.35", "अंदाज", "थर 2 §6"),
    "v_hi / v_lo": ("1.2/0.83", "1.15/0.87, 1.3/0.77", "NexusFi practitioner", "थर 2 §6"),
    "v_min_reliable": (3, "—", "व्याख्या", "थर 2 §3: कोणत्याही leg ला < 3 reliable bars ⇒ V तटस्थ"),
    "gap_in_leg_sigma": (0.5, "0.3/0.5/0.8", "अंदाज", "थर 2 §1 gap_in_leg"),
    "short_leg_bars": (2, "—", "व्याख्या", "थर 2 §3: 1–2 bars ⇒ तटस्थ, baseline बाहेर"),
    "rvol_sessions": (20, "—", "व्याख्या", "MASTER §3 RVOL"),
    "rvol_min_sessions": (10, "5/10/15", "अंदाज", "सुरुवातीला 20 पात्र sessions नसतील तेव्हा किमान"),
    "roll_sessions_before": (2, "—", "व्याख्या", "MASTER §3 RVOL: monthly expiry + 2 sessions आधी"),
    "climax_rng_ratio": (2.0, "—", "व्याख्या", "MASTER §3 climax candle"),
    "spike (0.7, 5, 0.4, 0.6, 1)": ("0.7/5/0.4/0.6/1", "±20%", "Brooks / NexusFi", "थर 2 §5.1.3"),
    "climax_last_candles": (3, "—", "व्याख्या", "थर 2 §5.1.3: I च्या शेवटच्या 3 candles"),
    "sot_pushes": (3, "—", "व्याख्या", "थर 2 §5.1.3: शेवटचे 3 with-trend pushes"),
    "quiet / heavy": ("1.2/1.5", "±0.1", "NexusFi", "थर 2 §5.3"),
    "I_origin_break (breaks.py settings)": ("elliott.settings DEFAULTS", "±1 पायरी", "code (MR ≠ σ नोंद)", "MASTER break पातळी 2"),
    # व्याख्या-फरक (थर 2 §1: सध्याच्या code शी फरक)
    "overlap (फरक)": ("नोंद", "—", "नोंद", "market_state.overlap_ratio = >50% overlap bars चं प्रमाण; थर 2 = overlap ÷ range ची सरासरी"),
    "RVOL (फरक)": ("नोंद", "—", "नोंद", "chart_reader.volume.rel_vol = जास्त-volume contract; थर 2 = near-month, expiry + 2 sessions unreliable"),
}


def load(overrides=None, layer1=None):
    """layer1 = swings2 settings (trend / displacement व्याख्या तिथूनच)."""
    from swings2 import settings as SS
    s = dict(DEFAULTS)
    l1 = SS.load(layer1)
    for k in ("trend_body", "trend_clv", "disp_rng_ratio", "disp_body", "disp_wick_opp"):
        s[k] = l1[k]
    s.update(overrides or {})
    return s
