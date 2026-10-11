"""zones2/settings.py — थर 4 चे आकडे आणि "अंदाज" register (थर 4 §8; आकडा, default, पर्याय, वर्ग, स्रोत)."""

DEFAULTS = {
    "width_min": 0.2, "width_max": 1.0,          # σ (जन्माचा)
    "linkage": 0.5,                               # overlap किंवा मध्यबिंदू ≤ 0.5 σ
    "split": 1.5,                                 # union > 1.5 σ ⇒ तोड
    "reaction": 1.0, "reaction_bars": 12,         # ≥ 1 σ दूर, पुढच्या भेटीपर्यंत किंवा 12 bars
    "sweep_lo": 0.1, "sweep_hi": 1.0,             # wick पलीकडे 0.1–1 σ
    "sweep_close_bars": 2,                        # close आत: त्याच / 2 candles
    "reclaim_bars": 3,
    "accept_sigma": 0.5, "accept_closes": 2,      # MASTER accept
    "breaker_bars": 20,
    "prune_d1_sessions": 20, "prune_far": 15.0,
    "departure_bars": 3, "departure_disp": 2, "departure_net": 2.0,
    "band_convention": "base",                    # base / ob
    "base_bars": 2, "base_range": 1.0,
    "k_tol": 0.1,                                 # PDH / PDL / PDC / PWH / PWL पट्टा ± 0.1 σ
    "range_edge_tol": 0.25,                       # d: zone पट्टा range कडेच्या इतक्या σ आत
    "w_liq": 3, "w_origin": 2, "w_degree": 2, "w_react": 1, "w_flip": 1, "w_k": 1, "w_age": 1,
    "star2": 0.4, "star3": 0.7,
    "age_full": 5, "age_half": 20,                # sessions
    "bin": 0.1, "va": 0.70, "profile_sessions": 5,
    "confluence": 0.25,
    "rounds": (100, 500, 1000),
    "fibs": (0.5, 0.618, 0.786),
    "next_trade": 4, "next_opp": 2,
    "open_noise_min": 30,                         # 09:15 पासून 30 मिनिटं
}

REGISTER = {
    "width_min / width_max": ("0.2 / 1 σ", "0.15/0.2/0.3, 0.8/1/1.2", "अंदाज", "थर 4 §2.1"),
    "linkage": ("0.5 σ", "0.3/0.5/0.7", "अंदाज", "थर 4 §3"),
    "split": ("1.5 σ", "1.25/1.5/2", "research (zone ≤ 1.5 σ)", "थर 4 §3"),
    "reaction / reaction_bars": ("1 σ / 12", "0.75/1/1.5, 8/12/16", "अंदाज", "थर 4 §4"),
    "sweep_lo / sweep_hi": ("0.1–1 σ", "±50%", "अंदाज", "थर 4 §4 zone_sweep"),
    "sweep_close_bars": ("2", "1/2/3", "अंदाज", "थर 4 §4"),
    "reclaim_bars": ("3", "2/3/4", "अंदाज", "थर 4 §4"),
    "accept_sigma / accept_closes": ("0.5 σ / 2", "—", "MASTER", "break पातळी 3"),
    "breaker_bars": ("20", "10/20/30", "अंदाज", "थर 4 §4"),
    "prune_d1_sessions / prune_far": ("20 / 15 σ", "15/20/30, 10/15/20", "अंदाज", "थर 4 §3"),
    "departure_bars / departure_disp / departure_net": ("3 / 2 / 2 σ", "2–4 / 1–3 / 1.5–3", "अंदाज", "थर 4 §2.2 c"),
    "band_convention / base_bars / base_range": ("base / 2 / 1 σ", "base / ob", "setting (Abhi: default base)", "थर 4 §2.2 c"),
    "k_tol": ("0.1 σ", "0.05/0.1/0.2", "अंदाज", "थर 4 §2.3"),
    "range_edge_tol": ("0.25 σ", "0.15/0.25/0.4", "Abhi ✔ (उत्तर 8; confluence tolerance शी जुळतं)", "d: zone ला range कड खूण"),
    "w_liq / w_origin / w_degree / w_react / w_flip / w_k / w_age": ("3/2/2/1/1/1/1", "±1", "अंदाज", "थर 4 §6"),
    "star2 / star3": ("0.4 / 0.7", "±0.05", "अंदाज", "थर 4 §6"),
    "age_full / age_half": ("5 / 20 sessions", "—", "अंदाज", "थर 4 §6"),
    "bin / va / profile_sessions": ("0.1 σ / 70% / 5", "0.05/0.1/0.2, 68/70/75%", "अंदाज / research; 5 पूर्ण sessions (Abhi)",
                                    "थर 4 §5: कमी sessions / volume नाही ⇒ NA"),
    "confluence": ("0.25 σ", "0.15/0.25/0.4", "अंदाज", "थर 4 §7"),
    "rounds": ("100/500/1000", "—", "व्याख्या", "थर 4 §2.4"),
    "fibs": ("50/61.8/78.6", "—", "व्याख्या", "थर 4 §0.2"),
    "next_trade / next_opp": ("4 / 2", "—", "व्याख्या", "थर 4 §7"),
    "open_noise_min": ("30", "—", "व्याख्या", "MASTER: 09:15–09:45 noise"),
}


def load(overrides=None):
    s = dict(DEFAULTS)
    s.update(overrides or {})
    return s
