"""थर v2.2 §7.3 — अडकलेले traders (b) late_counter / (c) engulfed_counter + SL trapped zone च्या पलीकडे (Q56).
Crafted candles; प्रत्येक case ला आरसा (UP ⇄ DOWN); known_at (pivots confirm_bar > t ⇒ नाहीत) आणि truncation (t नंतरचे bars निर्णय बदलत नाहीत)."""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import liquidity as LQ
from decision3 import method as M
from decision3 import settings as S3

S = S3.load()


def A_of(rows):
    a = np.array(rows, float)
    return {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}


def mirror(rows, c=200.0):
    """किंमत c भोवती उलटी: (o, h, l, c) ⇒ (2c−o, 2c−l, 2c−h, 2c−c)."""
    return [(2 * c - o, 2 * c - l, 2 * c - h, 2 * c - cl) for o, h, l, cl in rows]


# DOWN trend (bear call): K = वरचा pullback; counter = buyers. bars 0–2 = K चा पहिला पाय (H 110 confirmed), bar 3 खाली, bar 4 नवं टोक 114,
# bar 5 परत खाली close 108 (< 110) ⇒ उशिरा आलेले buyers [110, 114] मध्ये अडकले.
LATE = [(100, 108, 99, 107), (107, 110, 106, 109), (109, 109.5, 105, 106), (106, 107, 103, 104), (104, 114, 103.5, 113),
        (113, 113.5, 107, 108)]
K_LATE = {"open": True, "k_open_bar": 0, "k_ext": 114.0, "k_ext_bar": 4, "legs": 2, "i_end": 95.0, "i_end_bar": -1}
PIV_LATE = [NS(kind="H", price=110.0, bar=1, confirm_bar=3)]


def test_late_counter_trap_down_and_mirror():
    A = A_of(LATE)
    tr = LQ.counter_traps(A, 5, M.DOWN, K_LATE, S, PIV_LATE)
    late = [x for x in tr if x["kind"] == "late_counter"]
    assert late and late[0]["side"] == "buy" and (late[0]["lo"], late[0]["hi"]) == (110.0, 114.0) and late[0]["bar"] == 4
    # आरसा: UP trend, K खाली, counter = sellers
    Am = A_of(mirror(LATE))
    km = {**K_LATE, "k_ext": 2 * 200 - 114.0, "i_end": 2 * 200 - 95.0}
    pm = [NS(kind="L", price=2 * 200 - 110.0, bar=1, confirm_bar=3)]
    trm = [x for x in LQ.counter_traps(Am, 5, M.UP, km, S, pm) if x["kind"] == "late_counter"]
    assert trm and trm[0]["side"] == "sell" and (trm[0]["lo"], trm[0]["hi"]) == (286.0, 290.0)


def test_late_counter_needs_return_and_prior_confirmed_extreme():
    A = A_of(LATE)
    # bar 4 (नवं टोक, परत नाही ⇒ close 113 > 110) ⇒ trap नाही
    assert not [x for x in LQ.counter_traps(A, 4, M.DOWN, {**K_LATE, "k_ext_bar": 4}, S, PIV_LATE) if x["kind"] == "late_counter"]
    # known_at: आधीचं टोक अजून confirm नाही (confirm_bar 7 > t 5) ⇒ trap नाही
    assert not [x for x in LQ.counter_traps(A, 5, M.DOWN, K_LATE, S, [NS(kind="H", price=110.0, bar=1, confirm_bar=7)])
                if x["kind"] == "late_counter"]
    # आधीचं टोक I_end च्या आधीचं / I_end वरचं (bar ≤ i_end_bar) ⇒ मोजत नाही (Pullbacks.legs सारखंच: p.bar > i_end_bar)
    assert not [x for x in LQ.counter_traps(A, 5, M.DOWN, {**K_LATE, "i_end_bar": 1}, S, PIV_LATE) if x["kind"] == "late_counter"]
    # K उशिरा उघडली (k_open_bar 2) पण pivot I_end नंतरचा ⇒ मोजतो (पहिल्या पायाचं टोक K उघडण्याआधी confirm झालेलं)
    assert [x for x in LQ.counter_traps(A, 5, M.DOWN, {**K_LATE, "k_open_bar": 2}, S, PIV_LATE) if x["kind"] == "late_counter"]
    # K उघडी नाही ⇒ []
    assert LQ.counter_traps(A, 5, M.DOWN, {**K_LATE, "open": False}, S, PIV_LATE) == []
    assert LQ.counter_traps(A, 5, M.DOWN, None, S, PIV_LATE) == []


# (c) engulf: DOWN trend; bars 0–4 लहान; bar 5 counter (buyers) मोठी body 104 → 111; bar 6 trend-दिशेची body 111.5 → 103 तिला गिळते.
ENG = [(100, 101, 99.5, 100.5), (100.5, 101.5, 100, 101), (101, 102, 100.5, 101.5), (101.5, 102.5, 101, 102), (102, 103, 101.5, 104),
       (104, 111.5, 103.5, 111), (111.5, 112, 102.5, 103)]
K_ENG = {"open": True, "k_open_bar": 1, "k_ext": 112.0, "k_ext_bar": 6, "legs": 1, "i_end": 90.0}


def test_engulfed_counter_trap_down_and_mirror():
    tr = [x for x in LQ.counter_traps(A_of(ENG), 6, M.DOWN, K_ENG, S, []) if x["kind"] == "engulfed_counter"]
    assert tr and tr[0]["side"] == "buy" and (tr[0]["lo"], tr[0]["hi"]) == (104.0, 111.0) and tr[0]["bar"] == 5
    km = {**K_ENG, "k_ext": 2 * 200 - 112.0, "i_end": 2 * 200 - 90.0}
    trm = [x for x in LQ.counter_traps(A_of(mirror(ENG)), 6, M.UP, km, S, []) if x["kind"] == "engulfed_counter"]
    assert trm and trm[0]["side"] == "sell" and (trm[0]["lo"], trm[0]["hi"]) == (289.0, 296.0)


def test_engulf_needs_big_counter_body_full_body_cover_and_k_window():
    # counter body लहान (सरासरीच्या आत) ⇒ नाही
    small = ENG[:5] + [(104, 105, 103.5, 104.6), (104.7, 105, 102.5, 103)]
    assert not LQ.counter_traps(A_of(small), 6, M.DOWN, K_ENG, S, [])
    # पुढची candle body पूर्ण गिळत नाही (close 105 > 104) ⇒ नाही
    part = ENG[:6] + [(111.5, 112, 104.5, 105)]
    assert not LQ.counter_traps(A_of(part), 6, M.DOWN, K_ENG, S, [])
    # engulf K उघडण्याआधी (k_open_bar 6 > i 5) ⇒ नाही
    assert not LQ.counter_traps(A_of(ENG), 6, M.DOWN, {**K_ENG, "k_open_bar": 6}, S, [])
    # truncation: t = 5 ला (engulf candle अजून नाही) ⇒ नाही; t = 6 ला आहे — नंतरचे bars जोडले तरी t = 6 चा निकाल तोच
    assert not LQ.counter_traps(A_of(ENG), 5, M.DOWN, K_ENG, S, [])
    more = ENG + [(103, 104, 100, 101), (101, 102, 98, 99)]
    assert LQ.counter_traps(A_of(more), 6, M.DOWN, K_ENG, S, []) == LQ.counter_traps(A_of(ENG), 6, M.DOWN, K_ENG, S, [])


def test_sl_edge_picks_far_edge_per_direction_and_only_k_zones():
    tz = [{"lo": 110.0, "hi": 114.0, "bar": 2}, {"lo": 112.0, "hi": 118.0, "bar": 6}]
    assert LQ.sl_edge(tz, M.DOWN) == 118.0 and LQ.sl_edge(tz, M.UP) == 110.0 and LQ.sl_edge([], M.UP) is None
    assert LQ.sl_edge(tz, M.DOWN, k0=3) == 118.0 and LQ.sl_edge(tz, M.UP, k0=3) == 112.0 and LQ.sl_edge(tz, M.DOWN, k0=7) is None
    assert LQ.sl_edge(tz, M.DOWN, k0=6) == 118.0 and LQ.sl_edge(tz, M.UP, k0=6) == 112.0                 # bar == k0 ⇒ K मधला


def test_failed_breakout_needs_price_inside_before_sweep():
    """Review 🔴: impulse pool ओलांडून खाली गेला (window सुरुवातीलाच pool पलीकडे) ⇒ sweep / failed_breakout नाही — आधी K-पलीकडचं
    खोटं 'trapped' टोक SL ला लागलं असतं."""
    S2 = {**S, "accept_closes": 3}
    rows = [(130, 131, 125, 126), (126, 127, 118, 119), (119, 120, 112, 113), (113, 114, 108, 109), (109, 110, 106, 107),
            (107, 108.5, 105, 108), (108, 109, 106, 107)]                                                  # pool (swing H) 110: आधीच वर, मग खाली
    ts = pd.Series(pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min"))
    piv = [NS(kind="H", price=110.0, bar=0, confirm_bar=0)]
    V = NS(levels=NS(A=A_of(rows), ts=ts, sig1h=np.full(len(rows), 10.0), known_pivots=lambda t: piv), s=S2)
    sw, tr = LQ.sweeps_and_traps(V, 6, 5)                                                                 # window bar 1 पासून; bar 0 आधीच वर
    assert not [x for x in sw if x["src"] == "swing"] and not tr
    sw2, tr2 = LQ.sweeps_and_traps(V, 6, 6)                                                               # window bar 1 पासून, आधीचा bar 0 वर ⇒ तसंच
    assert not [x for x in sw2 if x["src"] == "swing"] and not tr2
    # खरा sweep (आत ⇒ पलीकडे wick ⇒ परत) अजूनही ओळखतो
    sweep = [(105, 106, 104, 105)] * 3 + [(105, 112, 104, 108), (108, 109, 106, 107)]
    V2 = NS(levels=NS(A=A_of(sweep), ts=ts[:5], sig1h=np.full(5, 10.0), known_pivots=lambda t: piv), s=S2)
    assert [x for x in LQ.sweeps_and_traps(V2, 4, 4)[0] if x["src"] == "swing"]


def _V(rows, sigma15=2.0):
    A = A_of(rows)
    ts = pd.Series(pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min"))
    lv = NS(A=A, ts=ts, snapshot=lambda t: [])
    return NS(levels=lv, res={"sigma": {ts[0].normalize(): sigma15}}, s=S)


def test_risk_sl_beyond_trapped_zone_and_setting_off():
    """bear call: level 104–106, K टोक 114; failed-breakout trapped zone [114, 118] (lookback मधला, K आधीचा sweep) ⇒ SL 118 + buffer."""
    rows = LATE + [(108, 108.5, 104, 105)]
    V = _V(rows)
    lvl = {"lo": 104.0, "hi": 106.0, "sweeps": 0, "births": ["a:D2"], "fresh": True}
    k = {**K_LATE, "i_end": 80.0}
    buf = 0.25 * 2.0
    ok0, r0 = M.risk(V, 6, M.DOWN, lvl, k, S, traps=None)
    assert r0["sl"] == round(114.0 + buf, 2) and r0["sl_src"] == "K"
    traps = [{"lo": 114.0, "hi": 118.0, "kind": "failed_breakout", "side": "buy", "bar": 2}]
    ok1, r1 = M.risk(V, 6, M.DOWN, lvl, k, S, traps=traps)
    assert r1["sl"] == round(118.0 + buf, 2) and r1["sl_src"] == "trapped"
    assert r1["rr"] < r0["rr"]                                                            # SL रुंद ⇒ R:R कमी (target तोच)
    # K आधी (bar < k_open_bar) बनलेला zone SL ला लागत नाही (review 🔴: impulse मधला pool-cross)
    _, r1b = M.risk(V, 6, M.DOWN, lvl, {**k, "k_open_bar": 3}, S, traps=traps)
    assert r1b["sl"] == r0["sl"] and r1b["sl_src"] == "K"
    # विरुद्ध बाजूचा (sell-side) trapped zone bear call च्या SL ला लागत नाही
    _, r2 = M.risk(V, 6, M.DOWN, lvl, k, S, traps=[{**traps[0], "side": "sell", "lo": 90.0, "hi": 95.0}])
    assert r2["sl"] == r0["sl"] and r2["sl_src"] == "K"
    # K टोकाच्या आत असलेला trapped zone SL बदलत नाही (K जिंकतो)
    _, r3 = M.risk(V, 6, M.DOWN, lvl, k, S, traps=[{**traps[0], "lo": 110.0, "hi": 112.0}])
    assert r3["sl"] == r0["sl"] and r3["sl_src"] == "K"
    # setting बंद ⇒ जुना SL
    _, r4 = M.risk(V, 6, M.DOWN, lvl, k, {**S, "sl_beyond_trapped": False}, traps=traps)
    assert r4["sl"] == r0["sl"] and r4["sl_src"] == "K"
    # आरसा (bull put): level 294–296, K टोक 286, trapped [282, 286] ⇒ SL 282 − buffer
    Vm = _V(mirror(rows))
    lm = {"lo": 294.0, "hi": 296.0, "sweeps": 0, "births": ["a:D2"], "fresh": True}
    km = {**K_LATE, "k_ext": 286.0, "i_end": 320.0}
    _, m1 = M.risk(Vm, 6, M.UP, lm, km, S, traps=[{"lo": 282.0, "hi": 286.0, "kind": "failed_breakout", "side": "sell", "bar": 2}])
    assert m1["sl"] == round(282.0 - buf, 2) and m1["sl_src"] == "trapped"
    assert abs((r1["entry"] - r1["sl"]) - (m1["sl"] - m1["entry"])) < 1e-9                  # आरशात SL अंतर समान


def test_risk_sl_src_level_when_k_inside_level():
    V = _V(LATE + [(105, 105.5, 103.5, 104)])
    lvl = {"lo": 104.0, "hi": 120.0, "sweeps": 0, "births": ["a:D2"], "fresh": True}
    _, r = M.risk(V, 6, M.DOWN, lvl, {**K_LATE, "i_end": 80.0}, S, traps=[{"lo": 110.0, "hi": 115.0, "kind": "late_counter", "side": "buy", "bar": 4}])
    assert r["sl_src"] == "level" and r["sl"] == round(120.0 + 0.5, 2)


def test_story_mentions_trapped_zone_without_sweep_and_sl_source():
    from decision3 import charts as CH
    r = {"daily_trend": "DOWN", "protected": {"price": 24000.0}, "level": None, "K": None,
         "liquidity": {"sweeps": [], "trapped": [{"lo": 23800.0, "hi": 23850.0, "kind": "late_counter", "side": "buy", "bar": 4}]},
         "checklist": {"⑥": [True, "commitment engulf"]}, "conviction": "A",
         "risk": {"entry": 23790.0, "sl": 23860.0, "target": 23500.0, "rr": 4.1, "sl_src": "trapped"}}
    txt = CH.story(r)
    assert "buyers अडकले" in txt and "उशिरा counter push" in txt and "trapped पलीकडे" in txt
    r2 = {**r, "liquidity": {"sweeps": [], "trapped": []}, "risk": {**r["risk"], "sl_src": "K"}}
    t2 = CH.story(r2)
    assert "अडकले" not in t2 and "trapped पलीकडे" not in t2


def test_settings_register_has_sl_beyond_trapped():
    assert S["sl_beyond_trapped"] is True and "sl_beyond_trapped" in S3.REGISTER
