"""थर v2.2 पायरी C — ③ breakout नाही, ④ power shift (2 of a–d; RSI एकटा नाही), ⑥ commitment (body, beyond prev, reclaim, कमकुवत ✘),
§5.3 range अवस्था, §6 conviction (H1–H3 बाहेर एकटा पुरावा trade नाकारत नाही; trap + commitment ⇒ A; NA पुरावे बेरजेत नाहीत)."""
import numpy as np

from decision3 import method as M
from decision3 import settings as S3

S = S3.load()


def A_of(rows):
    """rows = [(o, h, l, c)]"""
    a = np.array(rows, float)
    return {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}


LVL = {"lo": 100.0, "hi": 102.0, "sweeps": 0, "births": ["a:D2"], "fresh": True}


def test_at_level_from_above_ok_breakout_and_gap_rejected():
    ok, _ = M.at_level(A_of([(106, 107, 104, 105), (105, 105.5, 101, 103)]), 1, M.UP, LVL)
    assert ok
    assert not M.at_level(A_of([(106, 107, 104, 105), (105, 105.5, 98, 99)]), 1, M.UP, LVL)[0]       # close पार ⇒ ✘
    assert not M.at_level(A_of([(106, 107, 104, 105), (99, 101, 97, 100.5)]), 1, M.UP, LVL)[0]       # gap ने पार ⇒ ✘
    assert not M.at_level(A_of([(98, 99, 97, 98.5), (99, 101, 98.8, 100.5)]), 1, M.UP, LVL)[0]       # खालून आली ⇒ ✘


def test_power_shift_two_of_four_and_rsi_alone_not_enough():
    rows = [(110, 111, 106, 107), (107, 108, 104, 105), (105, 105.5, 103, 103.5), (103.5, 104, 102.8, 103.8)]
    A = A_of(rows)
    k = {"k_open_bar": 0, "k_ext": 102.8, "k_ext_bar": 3}
    ok, n, it = M.power_shift(A, 3, M.UP, k, S)
    assert it["a_shrinking"] and n >= 2 and ok
    A2 = A_of([(100, 110, 99, 109), (109, 120, 108, 119), (119, 130, 118, 129)])                    # trend-दिशेच्या मोठ्या candles
    ok2, n2, it2 = M.power_shift(A2, 2, M.UP, {"k_open_bar": 0, "k_ext": 99, "k_ext_bar": 0}, S)
    assert it2["e_rsi_div"] is None and n2 < 2 and not ok2


def test_range_state_gate():
    A = A_of([(100, 101, 99, 100.6), (100.6, 101, 99.2, 100.6), (100.6, 101.1, 99.1, 100.62)])
    assert M.range_state(A, 2)


def test_conviction_na_not_counted_trap_commit_gives_a_pattern_alone_not():
    ev = {"level_star": True, "fresh": True, "power_shift": True, "trap_sweep": True, "second_attempt": True, "commit_strong": True,
          "engulf": False, "rsi_div": None, "volume_low": None, "pattern": None, "against_bodies": False, "fourth_attempt": False}
    assert M.conviction(ev, S)[0] == "A"                                         # RSI / volume NA असूनही A
    only_pattern = {k: (True if k == "pattern" else (False if S["evidence_weights"][k] > 0 else False)) for k in S["evidence_weights"]}
    assert M.conviction(only_pattern, S)[0] in ("weak", "against")              # फक्त pattern-नाव ⇒ trade नाही


# ------------------------------------------------------------------------------------------------ engine (synthetic, swings2 सकट)
def _synthetic_m15(seed=7, legs=None):
    """स्पष्ट zigzag downtrend (Daily LH + LL) — प्रत्येक leg काही दिवस; intraday रेषा + noise."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    pts = legs or [22000, 21300, 21700, 21000, 21450, 20700, 21150, 20400, 20850, 20100, 20550, 19800, 20250, 19500, 19950, 19200]
    per_leg_days = [4 if b < a else 3 for a, b in zip(pts[:-1], pts[1:])]
    closes = []
    for (a, b), nd in zip(zip(pts[:-1], pts[1:]), per_leg_days):
        closes += list(np.linspace(a, b, nd * 25 + 1)[1:])
    days = pd.bdate_range("2030-01-07", periods=len(closes) // 25 + 1)
    rows, px = [], pts[0]
    for i, c0 in enumerate(closes):
        d = days[i // 25]
        ts = d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % 25))
        o = px
        c = c0 + rng.normal(0, 8)
        h, l = max(o, c) + abs(rng.normal(0, 6)), min(o, c) - abs(rng.normal(0, 6))
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": o, "high": h, "low": l, "close": c})
        px = c
    return pd.DataFrame(rows)


# fixture चे impulse legs एकसारखे ⇒ Q15 maturity (equality target) प्रत्येक (5)+ ला लागते. Setup invariants maturity-स्वतंत्र ⇒ त्या tests
# मध्ये maturity बंद (near = −10⁶ σ ⇒ कधीच "जवळ" नाही); default वर्तन test_mature_cap_in_pipeline मध्ये.
NO_MATURE = {"maturity_sigma_d": -1e6}


def _abc_m15(seed=1, impulse=900, pb=0.7, n_cycles=8, start=22000):
    """Downtrend: जलद impulse (40 bars), मग ABC pullback (a / b / c) आणि c च्या टोकाला एक मोठी bearish commitment candle."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    path, px = [], start
    for _ in range(n_cycles):
        low = px - impulse
        a, cc = low + impulse * pb * 0.7, low + impulse * pb
        b = a - impulse * pb * 0.35
        path += [(low, 40, "imp"), (a, 25, "pb"), (b, 15, "pb"), (cc, 25, "pb"), (cc - impulse * 0.12, 1, "commit")]
        px = cc - impulse * 0.12
    closes, styles, cur = [], [], start
    for tgt, nb, st in path:
        for x in np.linspace(cur, tgt, nb + 1)[1:]:
            closes.append(x)
            styles.append(st)
        cur = tgt
    days = pd.bdate_range("2030-01-07", periods=len(closes) // 25 + 2)
    rows, prev = [], start
    for i, (c0, st) in enumerate(zip(closes, styles)):
        ts = days[i // 25] + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % 25))
        o = prev
        c = c0 + rng.normal(0, 6 if st == "pb" else 3)
        if st == "commit":
            h, lo = o + abs(rng.normal(0, 2)), c - 1
        else:
            h, lo = max(o, c) + abs(rng.normal(0, 5)), min(o, c) - abs(rng.normal(0, 5))
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": o, "high": h, "low": lo, "close": c})
        prev = c
    return pd.DataFrame(rows)


def _key(r):
    k = r["K"] or {}
    return (r["decision"], r["daily_trend"], r["mark"], r["conviction"],
            [(x["id"], round(x["lo"], 6), round(x["hi"], 6)) for x in r["active_levels"]],
            {c: v[0] for c, v in r["checklist"].items()}, (k.get("open"), k.get("i_end"), k.get("k_ext"), k.get("legs")),
            None if not r["risk"] else tuple(sorted(r["risk"].items())), repr(r.get("trendline")))


def test_engine_invariants_no_breakout_setups_direction_and_truncation():
    from decision3 import engine as E3
    m15 = _abc_m15()
    V = E3.V22(m15, s=NO_MATURE)
    rows = V.run()
    A = V.levels.A
    assert any(r["decision"] == "setup" for r in rows)                           # test vacuous नाही: setup invariants खरंच तपासले
    for r in rows:
        if r["decision"] == "setup":
            lv = r["level"]
            t = r["bar"]
            if lv["role"] == "support":
                assert r["daily_trend"] in ("UP", "RANGE") and A["close"][t] >= lv["lo"] and A["open"][t] >= lv["lo"]   # breakout नाही
            else:
                assert r["daily_trend"] in ("DOWN", "RANGE") and A["close"][t] <= lv["hi"] and A["open"][t] <= lv["hi"]
            assert r["risk"]["rr"] >= 3 and r["mark"] in ("✅", "🟡")
        if r["trend_used"] in ("NEUTRAL", "UNKNOWN"):
            assert r["decision"] == "no_trade"
    assert any(r["daily_trend"] == "DOWN" for r in rows)
    st = [r["bar"] for r in rows if r["decision"] == "setup"][0]
    k = st + 1                                                                    # setup bar वरच कापलेलं data ⇒ तोच निर्णय (lookahead नाही)
    Vt = E3.V22(m15.iloc[:k].reset_index(drop=True), s=NO_MATURE)
    for t in range(max(0, k - 200), k):
        a, b = rows[t], Vt.decide(t)
        assert _key(a) == _key(b), t                                             # K, risk, checklist, band सुद्धा
    for t in range(k - 200, k):
        sa = {(x["id"], round(x["lo"], 6), round(x["hi"], 6)) for x in V.levels.snapshot(t)}
        sb = {(x["id"], round(x["lo"], 6), round(x["hi"], 6)) for x in Vt.levels.snapshot(t)}
        assert sa == sb, t


def test_liquidity_sweep_vs_acceptance_and_trap():
    from types import SimpleNamespace as NS
    import pandas as pd
    from decision3 import liquidity as LQ
    S2 = {**S, "accept_closes": 3, "liquidity_eq_sigma": 0.15}

    def V_of(rows):
        A = A_of(rows)
        ts = pd.Series(pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min"))
        piv = [NS(kind="H", price=110.0, bar=0, confirm_bar=0)]
        lv = NS(A=A, ts=ts, sig1h=np.full(len(rows), 10.0), known_pivots=lambda t: piv)
        return NS(levels=lv, s=S2)
    sweep = [(105, 106, 104, 105)] * 3 + [(105, 112, 104, 108), (108, 109, 106, 107)]                       # wick वर, close आत
    sw, tr = LQ.sweeps_and_traps(V_of(sweep), 4, 4)
    assert any(x["src"] == "swing" for x in sw) and not tr
    acc = [(105, 106, 104, 105)] * 2 + [(105, 113, 104, 112), (112, 114, 111, 113), (113, 115, 112, 114)]   # 3 closes वर ⇒ acceptance
    assert not [x for x in LQ.sweeps_and_traps(V_of(acc), 4, 4)[0] if x["src"] == "swing"]
    trap = [(105, 106, 104, 105), (105, 112, 104, 111), (111, 111.5, 107, 108), (108, 109, 104, 105), (105, 106, 103, 104),
            (104, 105, 102, 103)]                                                                             # 1 close वर, मग 3+ आत
    assert any(x["kind"] == "failed_breakout" for x in LQ.sweeps_and_traps(V_of(trap), 5, 5)[1])


def test_chart_text_is_english_only():
    """Abhi: chart वर English font, मराठी नको (Telegram caption `story` वेगळा)."""
    import os
    import re
    src = open(os.path.join(os.path.dirname(M.__file__), "charts.py"), encoding="utf-8").read()
    plot = src[:src.index("def story(")] + src[src.index("def m15_png("):]
    bad = [ln for ln in plot.splitlines() if '"""' not in ln and re.search("[ऀ-ॿ]", ln.split("#")[0])]
    assert not bad, bad


def test_h1_candle_upto_bar_has_no_future_bars():
    """1H band / BOS base: अपूर्ण तासात t नंतरचे 15M bars वापरले जात नाहीत (lookahead नाही)."""
    from decision3 import engine as E3
    V = E3.V22(_synthetic_m15())
    lv = V.levels
    A = lv.A
    differs = 0
    for t in range(200, 400):
        j = int(lv.h1_of[t])
        ix = [i for i in range(t + 1) if lv.h1_of[i] == j]
        o, h, lo, c = lv._h1_upto(j, t)
        assert (o, h, lo, c) == (A["open"][ix[0]], max(A["high"][ix]), min(A["low"][ix]), A["close"][ix[-1]])
        full = [i for i in range(lv.n) if lv.h1_of[i] == j]
        differs += (h, lo, c) != (max(A["high"][full]), min(A["low"][full]), A["close"][full[-1]])
    assert differs > 0                                                           # test vacuous नाही: अपूर्ण तास आले


def test_first_leg_rule_section_5_1():
    assert M.first_leg_cap("A", 1, 0, True) == "weak"                            # ★ < 2 ⇒ पहिल्या पायावर trade नाही (वाट)
    assert M.first_leg_cap("B", 1, 2, False) == "weak"                           # signal-bar कमकुवत ⇒ वाट
    assert M.first_leg_cap("A", 1, 2, True) == "B"                               # ★ ≥ 2 + मजबूत ⇒ कमाल B
    assert M.first_leg_cap("A", 2, 0, False) == "A"                              # दुसरा पाय ⇒ A शक्य
    assert M.first_leg_cap("against", 1, 3, True) == "against"


def test_touch_window_level_adjacent_but_breakout_on_t_rejected():
    rows = [(106, 107, 104, 105), (105, 105.5, 101.5, 103), (103, 104.5, 102.5, 104.2)]       # स्पर्श bar 1 ला, commitment bar 2 लगत
    assert not M.at_level(A_of(rows), 2, M.UP, LVL, 1)[0]
    assert M.at_level(A_of(rows), 2, M.UP, LVL, 2)[0]
    gap = [(106, 107, 104, 105), (105, 105.5, 101.5, 103), (99, 100.5, 98, 99.5)]           # bar t ने पार ⇒ ✘
    assert not M.at_level(A_of(gap), 2, M.UP, LVL, 3)[0]


def test_bos_fires_once_per_pivot_retest_reclaim_keeps_impulse():
    from types import SimpleNamespace as NS
    from decision3 import levels as LV
    obj = LV.Levels.__new__(LV.Levels)
    obj.A = {"close": np.array([100.0, 105, 111, 108.5, 111.5, 112])}
    obj._broken = set()
    known = [NS(kind="L", price=100.0, bar=0), NS(kind="H", price=110.0, bar=1)]
    got = [obj._bos(t, known) for t in range(6)]
    assert got[2] is not None and got[2][0] == 1                                 # पहिला BOS
    assert got[4] is None                                                        # retest + reclaim ⇒ नवा BOS नाही (K रीसेट नाही)


def test_daily_protected_ignores_discarded_pivot_and_follows_replacement(monkeypatch):
    import pandas as pd
    from decision3 import daily as DD
    n = 30
    days = pd.bdate_range("2030-01-07", periods=n)
    closes = [125.0] * n
    closes[24] = 116.5                                                           # 118 खाली, 115 वर ⇒ trend UP राहायला हवा
    d = pd.DataFrame({"timestamp": days, "open": closes, "high": [x + 1 for x in closes], "low": [x - 1 for x in closes], "close": closes})
    kat = DD.known_at_of(d)
    spec = [("L", 100, 2), ("H", 120, 5), ("L", 110, 8), ("H", 130, 11), ("L", 115, 14), ("L", 118, 17)]
    piv = [DD.DPivot(k, float(p), b, days[b], b + 2, kat[b + 2]) for k, p, b in spec]
    monkeypatch.setattr(DD, "pivots_pivot", lambda *a, **k: piv)
    st = DD.fold(d, {"daily_min_sessions": 3, "daily_trend_mode": "minor"})   # minor (what-if) Dow चा protected नियम
    assert st[22].trend == "UP" and st[22].protected.price == 115.0               # टाकलेला 118 protected नाही
    assert st[24].trend == "UP"
    spec2 = [("L", 100, 2), ("H", 120, 5), ("L", 110, 8), ("H", 130, 11), ("L", 115, 14), ("L", 112, 17)]
    piv[:] = [DD.DPivot(k, float(p), b, days[b], b + 2, kat[b + 2]) for k, p, b in spec2]
    st2 = DD.fold(d, {"daily_min_sessions": 3, "daily_trend_mode": "minor"})
    assert st2[22].protected.price == 112.0                                       # सलग अधिक टोकाचा L ⇒ protected तो

def test_pool_marks_nearest_per_side_dedup_and_priority():
    from types import SimpleNamespace as NS
    import pandas as pd
    from decision3 import liquidity as LQ
    n = 60
    ts = pd.Series(pd.date_range("2030-01-07 09:15", periods=n, freq="15min"))
    c = np.full(n, 100.0)
    A = {"open": c, "high": c + 1, "low": c - 1, "close": c}
    piv = [NS(kind="H", price=103.0, bar=5, confirm_bar=6), NS(kind="H", price=103.05, bar=10, confirm_bar=11),
           NS(kind="H", price=106.0, bar=12, confirm_bar=13), NS(kind="L", price=97.0, bar=14, confirm_bar=15),
           NS(kind="H", price=180.0, bar=16, confirm_bar=17)]
    lv = NS(A=A, ts=ts, sig1h=np.full(n, 2.0), known_pivots=lambda t: piv)
    V = NS(levels=lv, s={**S, "liq_marks_per_side": 2, "show_distance_sigma": 12.0, "liquidity_eq_sigma": 0.15})
    mk = LQ.pool_marks(V, n - 1)
    buy = [m for m in mk if m["side"] == "buy"]
    assert len(buy) <= 2 and all(m["price"] >= 100 for m in buy)
    assert not any(abs(m["price"] - 180) < 1 for m in mk)                               # दूरचं (> 12 σ) chart वर नाही
    near103 = [m for m in buy if abs(m["price"] - 103) < 0.2]
    assert len(near103) == 1 and near103[0]["src"] == "equal"                          # 103 / 103.05 ⇒ एकच, EQ ला प्राधान्य
    assert all(m["label"].endswith("BSL") for m in buy) and any(m["side"] == "sell" for m in mk)


def test_charts_with_liquidity_layer_render_english_only():
    import warnings
    from decision3 import charts as CH
    from decision3 import engine as E3
    from decision3 import liquidity as LQ
    V = E3.V22(_abc_m15(), s=NO_MATURE)
    rows = V.run()
    r = next(x for x in rows if x["decision"] == "setup")
    r = {**r, "liquidity": {"sweeps": [{"price": r["level"]["hi"], "side": "buy", "src": "PDH", "bar": r["bar"] - 1,
                                        "extreme": r["level"]["hi"] + 5}],
                            "trapped": [{"lo": r["level"]["hi"], "hi": r["level"]["hi"] + 5, "side": "buy", "kind": "failed_breakout"}]}}
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message="Glyph")
        a = CH.h1_png(V.levels, r["bar"], r["daily_trend"], "NIFTY", liq=LQ.pool_marks(V, r["bar"]))
        b = CH.m15_png(V, r["bar"], "NIFTY", r=r)
    assert a[:4] == b[:4] == b"\x89PNG"


def test_mature_cap_in_pipeline():
    """Default settings: तोच fixture — maturity बंद असताना setup देणारा bar, default ला mature ⇒ कमाल weak ⇒ setup नाही (Q15 (5))."""
    from decision3 import engine as E3
    m15 = _abc_m15()
    off = [r for r in E3.V22(m15, s=NO_MATURE).run() if r["decision"] == "setup"]
    assert off
    V = E3.V22(m15)
    for r0 in off:
        r = V.decide(r0["bar"])
        if r["mature"]:
            assert r["decision"] != "setup" and r["trend_cap"] == "weak" and any("mature" in x for x in r["trend_notes"])
    assert any(V.decide(r0["bar"])["mature"] for r0 in off)
