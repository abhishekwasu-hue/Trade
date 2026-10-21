"""थर v2.2 पायरी C — ③ breakout नाही, ④ power shift (2 of a–d; RSI एकटा नाही), ⑥ commitment (body, beyond prev, reclaim, कमकुवत ✘),
§5.3 range अवस्था, §6 conviction (H1–H3 बाहेर एकटा पुरावा trade नाकारत नाही; trap + commitment ⇒ A; NA पुरावे बेरजेत नाहीत)."""
import numpy as np
import pytest

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
    ok, n, it = M.power_shift(A, 3, M.UP, k, {**S, "power_a_rule": "strict3"})                     # जुना (what-if) नियम
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
# हा fixture 15M-only (5M LTF नाही) आणि त्याचा setup bar study window पेक्षा dominant नाही ⇒ ⑥ ची c0 dominance / c1 LTF CHoCH (Abhi,
# LEVEL_BOTS_CONFIRMATION) इथे बंद — हे tests त्या नियमांचे नाहीत (setup invariants / charts / captions); c0 + c1 चे tests (आरशासह)
# tests/test_decision3_confirm.py मध्ये.
# या fixture चा एकमेव setup acceptance-flip झालेल्या level च्या retest वर होता (जुना spec §5.4); Abhi च्या K4 नियमाने (Z-1) तो level
# far swing पार न झाल्याने BROKEN ⇒ trade location नाही. हे tests flip नियमाचे नाहीत (setup invariants / charts / captions) ⇒ जुना नियम
# स्पष्ट pin (`level_flip_rule` = "acceptance"); नवा नियम tests/test_decision3_flip.py मध्ये. असर्ट बदलले नाहीत.
# हे fixtures volume-नसलेले ⇒ Abhi Z-1c (volume नाही ⇒ data problem, entry नाही) इथे जुनी प्रथा pin (`c0_volume_required` False).
# Abhi Z-1u / Z-1v (bands never widened by merging; handover per visit) आधीचे fixtures ⇒ जुनं merge / touch-window visit pin
# (`level_merge`, `zone_visit_rule`); नवे नियम tests/test_decision3_zone_answers.py मध्ये. असर्ट बदलले नाहीत.
NO_MATURE = {"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_dominance": False, "level_flip_rule": "acceptance",
             "c0_volume_required": False, "a2_handover_required": False,   # Z-1m (handover अनिवार्य) आधीचे fixtures — pin
             "level_merge": True, "zone_visit_rule": "touch_window", "commit_volume_rule": "opposite"}
LEGACY_RR = {**NO_MATURE, "rr_step": True}                                       # Abhi 13 Oct: ⑦ default मधून काढला — जुने असर्ट याने


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
    V = E3.V22(m15, s=LEGACY_RR)                                                  # ⑦ R:R असर्ट ⇒ legacy rr_step (pin, Abhi 13 Oct)
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
    Vt = E3.V22(m15.iloc[:k].reset_index(drop=True), s=LEGACY_RR)
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
    S2 = {**S, "accept_closes": 3, "liquidity_eq_sigma": 0.15, "liquidity_rule": "sigma"}   # the legacy liquidity read (what-if)

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


@pytest.mark.parametrize("mirror", [False, True], ids=["buy-side", "sell-side"])
def test_liquidity_by_the_method_equal_by_comparison_sweep_and_trap_by_structure(mirror):
    """Abhi's method §3 (default `liquidity_rule = equal`): equal = the later swing reaches the earlier swing candle's own band and does
    not go beyond it; sweep = beyond and back inside before any swing formed beyond; a close beyond and back = trapped (failed breakout);
    a swing formed beyond = accepted. No σ tolerance, no close count, no day / week pools."""
    import pandas as pd
    from types import SimpleNamespace as NS
    from decision3 import liquidity as LQ
    f = (lambda x: 220.0 - x) if mirror else (lambda x: float(x))
    k = (lambda q: "L" if q == "H" else "H") if mirror else (lambda q: q)

    def V_of(rows, piv, known0=()):
        rows = [(f(o), max(f(h), f(lo)), min(f(h), f(lo)), f(c)) for o, h, lo, c in rows]
        A = A_of(rows)
        ts = pd.Series(pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min"))
        lv = NS(A=A, ts=ts, sig1h=np.full(len(rows), 10.0), known_pivots=lambda t: piv, _known0=list(known0))
        return NS(levels=lv, s=S3.load())
    base = [(108.0, 110.0, 107.5, 108.5)] + [(105, 106, 104, 105)] * 3
    p0 = NS(kind=k("H"), price=f(110.0), bar=0, confirm_bar=0)
    sweep = base + [(105, 112, 104, 108), (108, 109, 106, 107)]                                     # wick above, close back inside
    sw, tr = LQ.sweeps_and_traps(V_of(sweep, [p0]), 5, start=1)
    assert [x["src"] for x in sw] == ["swing"] and not tr
    trap = base + [(105, 112, 104, 111), (111, 111.5, 107, 108), (108, 109, 104, 105)]                # a close above, then back
    sw, tr = LQ.sweeps_and_traps(V_of(trap, [p0]), 6, start=1)
    assert sw and [x["kind"] for x in tr] == ["failed_breakout"]
    held = base + [(105, 112, 104, 111), (111, 113, 110.5, 112.5), (112.5, 112.6, 110.2, 110.5), (110.5, 110.8, 108.5, 109)]
    acc = V_of(held, [p0], known0=[NS(kind=k("H"), price=f(113.0), bar=5, confirm_bar=6)])            # a swing formed above while
    assert LQ.sweeps_and_traps(acc, 7, start=1) == ([], [])                                          # price held beyond ⇒ accepted
    poke = V_of(sweep + [(107, 107.5, 104, 104.5)], [p0], known0=[NS(kind=k("H"), price=f(112.0), bar=4, confirm_bar=6)])
    sw, tr = LQ.sweeps_and_traps(poke, 6, start=1)                         # the poke's own wick confirmed as a swing AFTER the close back
    assert [x["src"] for x in sw] == ["swing"] and sw[0]["back_at"] == 4   # inside ⇒ still a sweep (decided at the first close back)
    eq = V_of(base + [(105, 109.2, 104.8, 106)], [p0, NS(kind=k("H"), price=f(109.2), bar=4, confirm_bar=4)])
    assert [x["src"] for x in LQ.pools(eq, 4) if x["src"] != "swing"] == ["equal"]              # 109.2 inside 108.5–110 (wick to body)
    far = V_of(base + [(105, 108.0, 104.8, 106)], [p0, NS(kind=k("H"), price=f(108.0), bar=4, confirm_bar=4)])
    assert [x for x in LQ.pools(far, 4) if x["src"] != "swing"] == []                          # below the band ⇒ not equal
    assert not [x for x in LQ.pools(eq, 4) if x["src"] in ("PDH", "PDL", "PWH", "PWL")]        # P2: no day / week pools


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
    V = NS(levels=lv, s={**S, "liq_marks_per_side": 2, "show_distance_sigma": 12.0, "liquidity_eq_sigma": 0.15, "liquidity_rule": "sigma"})
    mk = LQ.pool_marks(V, n - 1)                                          # the legacy σ read (what-if); the method read below
    buy = [m for m in mk if m["side"] == "buy"]
    assert len(buy) <= 2 and all(m["price"] >= 100 for m in buy)
    assert not any(abs(m["price"] - 180) < 1 for m in mk)                               # दूरचं (> 12 σ) chart वर नाही
    near103 = [m for m in buy if abs(m["price"] - 103) < 0.2]
    assert len(near103) == 1 and near103[0]["src"] == "equal"                          # 103 / 103.05 ⇒ एकच, EQ ला प्राधान्य
    assert all(m["label"].endswith("BSL") for m in buy) and any(m["side"] == "sell" for m in mk)
    Vm = NS(levels=lv, s={**S, "liq_marks_per_side": 2, "show_distance_sigma": 12.0})   # method: 103.05 goes beyond 103 ⇒ not equal
    assert not [m for m in LQ.pool_marks(Vm, n - 1) if m["src"] == "equal"]
    piv[1] = NS(kind="H", price=102.9, bar=10, confirm_bar=11)               # reaches 103's own band (body 100 … high 103), not beyond
    near = [m for m in LQ.pool_marks(Vm, n - 1) if abs(m["price"] - 103) < 0.2]
    assert len(near) == 1 and near[0]["src"] == "equal"                      # one mark, EQ first


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
        a2 = CH.h1_png(V.levels, r["bar"], r["daily_trend"], "NIFTY", liq=LQ.pool_marks(V, r["bar"]), debug=True)   # C1 debug
        b2 = CH.m15_png(V, r["bar"], "NIFTY", r=r, debug=True)
    assert a[:4] == b[:4] == a2[:4] == b2[:4] == b"\x89PNG"


def test_review_charts_default_at_most_six_level_bands(monkeypatch):
    """C1 (Abhi) → TA1 / TA4 (Abhi, design §10): 1H default chart वर फक्त shared band check pass होणारे पट्टे, किंमतीच्या वर कमाल 3 आणि
    खाली कमाल 3 (+ trigger candle); invalid फक्त debug मध्ये (debug मध्ये सगळी जवळची levels)."""
    import matplotlib.axes
    from decision3 import charts as CH
    from decision3 import engine as E3
    from decision3 import levels as LVM
    V = E3.V22(_abc_m15(), s=NO_MATURE)
    rows = V.run()
    r = next(x for x in rows if x["decision"] == "setup")
    t = r["bar"]
    c = float(V.levels._h1_upto(int(V.levels.h1_of[t]), t)[3])
    spans = []
    real = matplotlib.axes.Axes.axhspan
    monkeypatch.setattr(matplotlib.axes.Axes, "axhspan", lambda self, *a, **k: spans.append(a) or real(self, *a, **k))
    lv = [{"id": f"L{i}", "lo": c - 10.25 + 2 * i, "hi": c - 9.75 + 2 * i, "role": "support" if i < 5 else "resistance",
           "births": ["a"], "sweeps": 0, "tests": i % 2, "dist": float(i)} for i in range(10)]
    monkeypatch.setattr(V.levels, "snapshot", lambda t: lv)
    monkeypatch.setattr(V.levels, "active", lambda t, trend, band=None: [])

    def fake_check(df, t, items, s=None, start=0, magnet_df=None):                    # shared check stubbed: even ids valid
        return [(x, {"lo": x["lo"], "hi": x["hi"], "role": x["role"], "valid": int(x["id"][1:]) % 2 == 0, "broken": False,
                     "reasons": [] if int(x["id"][1:]) % 2 == 0 else ["lt2_reaction_touches"], "touch_count": 2, "touches": [{"bar": 1}],
                     "established": False, "last_break_bar": None}) for x in items]
    monkeypatch.setattr(LVM, "check_bands", fake_check)
    CH.h1_png(V.levels, t, r["daily_trend"], "NIFTY", max_sigma=1e9, finder="validity")   # the R1a legacy view (layer 6b: method)
    drawn = {round(a[0], 2) for a in spans}
    assert drawn == {round(x["lo"], 2) for x in lv if int(x["id"][1:]) % 2 == 0}      # 5 valid (3 below + 2 above), invalid hidden
    assert len(spans) <= CH.MAX_LEVEL_BANDS
    assert sum(1 for a in spans if a[0] > c) <= 3 and sum(1 for a in spans if a[1] < c) <= 3
    spans.clear()
    CH.h1_png(V.levels, t, r["daily_trend"], "NIFTY", max_sigma=1e9, debug=True, finder="validity")
    assert len(spans) == 10


def test_review_charts_real_band_check_no_stub(monkeypatch):
    """Review 🟡7: h1_png with the real shared band check (no stub) — every drawn band is one band_view picked, each non-active one
    passes the check (or is the latest broken one), ≤ 3 per side of price, and a valid active level outside the 3 + 3 view is not
    labelled as failing."""
    import matplotlib.axes
    from decision3 import charts as CH
    from decision3 import engine as E3
    from decision3 import levels as LVM
    from facts import validity as FV
    V = E3.V22(_abc_m15(), s=NO_MATURE)
    rows = V.run()
    r = next(x for x in rows if x["decision"] == "setup")
    t = r["bar"]
    lv = V.levels
    act = {x["id"] for x in lv.active(t, r["daily_trend"], None)}
    shown = list(lv.snapshot(t))
    view = CH.band_view(lv, t, shown, act)
    j = int(lv.h1_of[t])
    fr = lv.h1.iloc[:j + 1].reset_index(drop=True)
    fr.loc[len(fr) - 1, ["open", "high", "low", "close"]] = list(lv._h1_upto(j, t))
    real = {x["id"]: f for x, f in LVM.check_bands(fr, len(fr) - 1, shown, FV.lookback("1H"), magnet_df=lv.m15.iloc[:t + 1])}
    c = float(fr["close"].iloc[-1])
    for x, f, style in view:
        assert real[x["id"]]["valid"] == f["valid"] and real[x["id"]]["reasons"] == f["reasons"]
        assert style in ("valid", "broken", "active", "decision")
        if style == "active":
            assert f["valid"] and x["id"] in act
        if style == "decision":
            assert not f["valid"] and f["reasons"] and x["id"] in act
    picked = [f for _, f, st in view if st in ("valid", "broken")]
    assert sum(1 for f in picked if f["valid"] and f["lo"] > c) <= 3 and sum(1 for f in picked if f["valid"] and f["hi"] < c) <= 3
    spans = []
    orig = matplotlib.axes.Axes.axhspan
    monkeypatch.setattr(matplotlib.axes.Axes, "axhspan", lambda self, *a, **k: spans.append(a) or orig(self, *a, **k))
    CH.h1_png(lv, t, r["daily_trend"], "NIFTY", max_sigma=1e9, finder="validity")
    assert len(spans) == len(view)


def test_review_1h_chart_draws_the_decisions_areas_layer_6b(monkeypatch):
    """Layer 6b (method P8 / §5): the 1H review chart draws the decision's own areas with their K4 state — every armed area, of the
    rest ≤ 3 above / ≤ 3 below price and the most recently broken one — and no display band check is called."""
    import matplotlib.axes
    from decision3 import charts as CH
    from decision3 import engine as E3
    from decision3 import levels as LVM
    V = E3.V22(_abc_m15(), s=NO_MATURE)
    rows = V.run()
    r = next(x for x in rows if x["decision"] == "setup")
    t = r["bar"]
    lv = V.levels
    act = {x["id"] for x in lv.active(t, r["daily_trend"], None)}
    shown = list(lv.snapshot(t))
    view = CH.method_band_view(lv, t, shown, act)
    assert {x["id"] for x, st in view if st == "armed"} == act
    others = [x for x, st in view if st == "area"]
    assert sum(1 for x in others if x["above"]) <= 3 and sum(1 for x in others if x["below"]) <= 3
    assert sum(1 for _, st in view if st == "broken") <= 1
    monkeypatch.setattr(LVM, "check_bands", lambda *a, **k: (_ for _ in ()).throw(AssertionError("display band check called")))
    spans = []
    orig = matplotlib.axes.Axes.axhspan
    monkeypatch.setattr(matplotlib.axes.Axes, "axhspan", lambda self, *a, **k: spans.append(a) or orig(self, *a, **k))
    png = CH.h1_png(lv, t, r["daily_trend"], "NIFTY", max_sigma=1e9)
    assert png[:4] == b"\x89PNG" and len(spans) == len(view)
    lab = CH.area_label({**shown[0], "state": "FLIPPED", "tests": 2, "sweeps": 1}, armed=True)
    assert lab.startswith("> ") and "flipped, 2 tests, swept" in lab


def test_mature_cap_in_pipeline():
    """Abhi (12 Oct, owner नियम — जुना Q15 (5) "mature ⇒ कमाल weak" बदलला): maturity = पुरावा फक्त. Trend रचना अखंड (protected अखंड,
    उलट impulse नाही) ⇒ mature setup अडवत नाही; grade फक्त एक पायरी खाली (A ⇒ B; B तसाच). रचना अखंड नाही (same-degree correction) ⇒
    जुना cap (weak) तसाच. Mature नसताना setup देणारे bars हेच तपासले."""
    import dataclasses
    from decision3 import engine as E3
    from decision3 import method as M3
    m15 = _abc_m15()
    s = {k: v for k, v in NO_MATURE.items() if k != "maturity_sigma_d"}          # c0 / c1 बंद (हा test त्यांचा नाही), maturity default
    s["wave_gates"] = True                                                       # Abhi 12 Oct नियम pin — B1 (default) test खाली
    s["verdict_rule"] = "score"                                                  # caps / step-down = the legacy score rule (layer 6)
    V = E3.V22(m15, s=s)
    # Q44: या fixture ला trend-degree (A1) correction नाही ⇒ structural target नाही ⇒ default मध्ये mature नाही ⇒ Daily states mature केले.
    assert not any(x.mature for x in V.daily)
    base = {r["bar"]: r for r in V.run() if r["decision"] == "setup"}
    assert base
    V.daily = [dataclasses.replace(x, mature=True) if x.trend in ("UP", "DOWN") else x for x in V.daily]
    for b, r0 in base.items():
        r = V.decide(b)
        assert r["mature"] and r["mature_step_down"] and r["trend_cap"] != "weak" and any("mature" in x for x in r["trend_notes"])
        assert r["decision"] == "setup" and r["conviction"] == M3.step_down_conv(r0["conviction"])      # entry अडत नाही, एक पायरी खाली
    V.daily = [dataclasses.replace(x, counter="correction") if x.trend in ("UP", "DOWN") else x for x in V.daily]   # रचना अखंड नाही
    for b in base:
        r = V.decide(b)
        assert r["trend_cap"] == "weak" and not r["mature_step_down"] and r["decision"] != "setup"
    assert M3.step_down_conv("A") == "B" and M3.step_down_conv("B") == "B" and M3.step_down_conv("weak") == "weak"


def test_power_shift_a_relative_contraction_both_directions():
    """Abhi (level bots spec): (a) = area मधल्या pullback candles चा सरासरी range < pullback च्या आधीच्या आणि impulse च्या candles पेक्षा; नेमके 3 नाहीत.
    आरसा (DOWN) तसाच निर्णय देतो."""
    up = [(90, 99, 89, 98), (98, 107, 97, 106), (106, 110, 105, 109),                          # impulse (मोठ्या हिरव्या)
          (109, 109.5, 103, 104), (104, 104.5, 99, 100),                                       # pullback आधीचा भाग (मोठ्या लाल)
          (100, 100.4, 98.8, 99), (99.2, 99.6, 98.4, 98.6), (98.6, 99.0, 98.0, 98.2)]          # area मध्ये (लहान लाल; 3 सलग लहान नाहीत तरी)
    lvl = {"lo": 97.5, "hi": 100.5}
    k = {"k_open_bar": 3, "origin_bar": 0, "i_end_bar": 2, "k_ext": 98.0, "k_ext_bar": 7}
    assert M.contraction(A_of(up), 7, M.UP, k, S, lvl)
    dn = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in up]
    lvl_dn = {"lo": 200 - lvl["hi"], "hi": 200 - lvl["lo"]}
    assert M.contraction(A_of(dn), 7, M.DOWN, k, S, lvl_dn)
    big = up[:5] + [(100, 101, 93, 94), (94, 95, 87, 88), (88, 89, 81, 82)]                    # area मध्ये मोठ्या ⇒ contraction नाही
    assert not M.contraction(A_of(big), 7, M.UP, k, S, {"lo": 80, "hi": 100.5})


def test_maturity_and_leg_count_never_block_or_downgrade_by_default():
    """Abhi B1 (trader's patience, 13 Oct final): wave count, maturity and projections are context only — with the Daily made mature (and
    the structure not intact) every default decision, conviction and cap is exactly the same; the facts are in `wave_context`."""
    import dataclasses
    from decision3 import engine as E3
    m15 = _abc_m15()
    s = {k: v for k, v in NO_MATURE.items() if k != "maturity_sigma_d"}
    V = E3.V22(m15, s=s)
    assert V.s["wave_gates"] is False
    bars = range(700, len(m15))
    base = {t: V.decide(t) for t in bars}
    assert any(r["decision"] == "setup" for r in base.values())
    for patch in ({"mature": True}, {"mature": True, "origin_risk": True}, {"mature": True, "counter": "correction", "origin_risk": True}):
        V.daily = [dataclasses.replace(x, **patch) if x.trend in ("UP", "DOWN") else x for x in V.daily]
        for t, r0 in base.items():
            r = V.decide(t)
            assert r["decision"] == r0["decision"]                         # maturity / origin_risk / leg count never block
            if "counter" not in patch:
                assert r["conviction"] == r0["conviction"]                 # … and never downgrade
            else:                                                          # the Q23 same-degree-correction cap (structure, not maturity)
                assert r["conviction"] == r0["conviction"] or (r0["conviction"] == "A" and r["conviction"] == "B")
            assert not r["mature_step_down"] and r["wave_context"].get("mature")
            if "counter" not in patch:
                assert r["trend_cap"] == r0["trend_cap"]
            else:
                assert r["trend_cap"] in (None, "B")                         # same-degree correction (Q23, structure) — never "weak"
        V.daily = E3.DD.fold(V.daily_df, V.s)
    for r in base.values():                                                       # leg count = context: never a no_trade / downgrade
        assert r["evidence"] is None or (r["evidence"]["second_attempt"] is None and r["evidence"]["fourth_attempt"] is None)
        assert "चौथा" not in str(r.get("why")) and "पहिला पाय" not in str(r.get("missing"))


def test_method_label_is_required_set_plus_confirming_never_a_score():
    """Method §5: A = the required set plus at least one confirming piece; B = the required set only. Present / absent / NA listed."""
    zr = {"summary": {"vol_rising_trade_side": False}}
    lvl = {"births": ["a:D2"], "confluence": []}
    c = M.confirming_evidence(zr, {"found": False}, lvl, None)
    assert c == {"volume_growing": False, "rsi_divergence": False, "confluence": False, "correction_line_closed_through": None}
    assert M.method_label(c) == "B"
    for one in ({**c, "volume_growing": True}, {**c, "rsi_divergence": True}, {**c, "correction_line_closed_through": True}):
        assert M.method_label(one) == "A"
    assert M.confirming_evidence(zr, None, {"births": ["a:D2", "tl"]}, None)["confluence"] is True
    assert M.confirming_evidence(zr, None, {"births": [], "confluence": [{"tf": "D"}]}, None)["confluence"] is True
    ev = M.evidence_list({"trap_sweep": True, "fresh": None}, c, True)
    assert ev["required"] == "present" and ev["confirming"]["volume_growing"] == "absent" and ev["context"]["trap_sweep"] == "present"
    assert ev["context"]["fresh"] == "NA"
