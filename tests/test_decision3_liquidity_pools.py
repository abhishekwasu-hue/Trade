"""थर v2.2 §7.1 / §7.7 — liquidity नकाशा: equal highs / lows ⇒ pool, PDH / PDL / PWH / PWL फक्त **आधीच्या** दिवसाचे / आठवड्याचे (known_at),
swing pools फक्त confirmed pivots (confirm_bar ≤ t), `pool_marks` ची निवड (trade-बाजू, अंतर, duplicate एक, प्राधान्य). Crafted bars; आरसा."""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd

from decision3 import liquidity as LQ
from decision3 import settings as S3

S = S3.load()


def _V(rows, ts, pivots, sig=10.0, s=None):
    a = np.array(rows, float)
    A = {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}
    lv = NS(A=A, ts=pd.Series(pd.to_datetime(ts)), sig1h=np.full(len(rows), sig),
            known_pivots=lambda t: [p for p in pivots if p.confirm_bar <= t])
    return NS(levels=lv, s=s or S)


def _days(n_days, per_day=3, start="2030-01-06 09:15"):
    """n_days × per_day bars (15M), दिवस सोमवार 2030-01-06 पासून (सलग कामाचे दिवस, weekend वगळून)."""
    out = []
    d = pd.Timestamp(start)
    while len(out) < n_days * per_day:
        if d.weekday() < 5:
            for i in range(per_day):
                out.append(d + pd.Timedelta(minutes=15 * i))
        d = d + pd.Timedelta(days=1)
    return out[: n_days * per_day]


def test_equal_highs_lows_become_pools_within_sigma_fraction():
    rows = [(100, 101, 99, 100)] * 4
    ts = _days(1, 4)
    tol = float(S["liquidity_eq_sigma"]) * 10.0                              # 1.5
    piv = [NS(kind="H", price=120.0, bar=0, confirm_bar=0), NS(kind="H", price=121.0, bar=1, confirm_bar=1),      # 1.0 आत ⇒ EQ
           NS(kind="L", price=80.0, bar=0, confirm_bar=0), NS(kind="L", price=80.0 - tol - 0.5, bar=1, confirm_bar=1)]   # tol बाहेर ⇒ नाही
    ps = LQ.pools(_V(rows, ts, piv), 3)
    eq = [p for p in ps if p["src"] == "equal"]
    assert len(eq) == 1 and eq[0]["side"] == "buy" and eq[0]["price"] == 120.5
    assert {p["side"] for p in ps if p["src"] == "swing"} == {"buy", "sell"}
    # आरसा: equal lows
    piv_m = [NS(kind="L", price=80.0, bar=0, confirm_bar=0), NS(kind="L", price=79.0, bar=1, confirm_bar=1)]
    eq_m = [p for p in LQ.pools(_V(rows, ts, piv_m), 3) if p["src"] == "equal"]
    assert len(eq_m) == 1 and eq_m[0]["side"] == "sell" and eq_m[0]["price"] == 79.5


def test_swing_pools_only_confirmed_pivots_known_at():
    rows = [(100, 101, 99, 100)] * 4
    piv = [NS(kind="H", price=120.0, bar=1, confirm_bar=3)]
    V = _V(rows, _days(1, 4), piv)
    assert not [p for p in LQ.pools(V, 2) if p["src"] == "swing"]            # t = 2 ला confirm नाही
    assert [p for p in LQ.pools(V, 3) if p["src"] == "swing"]


def test_pdh_pdl_from_previous_day_only_and_none_on_first_day():
    # दिवस 1: high 110 / low 90; दिवस 2: high 130 / low 70 (आजचा, pool मध्ये नाही); दिवस 3 ला PDH = दिवस 2 चा
    rows = [(100, 105, 95, 100), (100, 110, 90, 100), (100, 102, 98, 100),
            (100, 130, 70, 100), (100, 101, 99, 100), (100, 101, 99, 100),
            (100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)]
    V = _V(rows, _days(3, 3), [])
    assert not [p for p in LQ.pools(V, 2) if p["src"] in ("PDH", "PDL")]      # पहिला दिवस ⇒ आधीचा दिवस नाही
    d2 = {p["src"]: p["price"] for p in LQ.pools(V, 4)}
    assert d2["PDH"] == 110.0 and d2["PDL"] == 90.0                           # दिवस 2 मधून दिवस 1 चे — आजचा 130 / 70 नाही (known_at)
    d3 = {p["src"]: p["price"] for p in LQ.pools(V, 7)}
    assert d3["PDH"] == 130.0 and d3["PDL"] == 70.0
    assert {p["side"] for p in LQ.pools(V, 7) if p["src"] == "PDH"} == {"buy"} and \
        {p["side"] for p in LQ.pools(V, 7) if p["src"] == "PDL"} == {"sell"}


def test_pwh_pwl_previous_week_only():
    # आठवडा 1 (सोम–शुक्र, 5 दिवस × 1 bar): highs 110..114, low 90; आठवडा 2 सोमवार: PWH = 114, PWL = 90; आठवड्या 1 मध्ये PWH नाही
    rows = [(100, 110 + i, 90 + (0 if i else -5), 100) for i in range(5)] + [(100, 150, 50, 100), (100, 101, 99, 100)]
    V = _V(rows, _days(7, 1), [])
    assert not [p for p in LQ.pools(V, 4) if p["src"] in ("PWH", "PWL")]
    w2 = {p["src"]: p["price"] for p in LQ.pools(V, 5)}
    assert w2["PWH"] == 114.0 and w2["PWL"] == 85.0
    w2b = {p["src"]: p["price"] for p in LQ.pools(V, 6)}                      # आठवडा 2 चा मंगळवार: तोच आधीचा आठवडा (सोमवारचा 150 / 50 नाही)
    assert w2b["PWH"] == 114.0 and w2b["PWL"] == 85.0 and w2b["PDH"] == 150.0 and w2b["PDL"] == 50.0


def test_pool_marks_trade_side_distance_dedupe_priority_and_mirror():
    rows = [(100, 101, 99, 100)] * 3 + [(100, 101, 99, 100.0)]
    ts = _days(2, 2)                                                           # दिवस 1: bars 0–1 (high 101 / low 99), दिवस 2: bars 2–3
    s2 = {**S, "liq_marks_per_side": 2, "show_distance_sigma": 2.0, "liquidity_eq_sigma": 0.15}
    piv = [NS(kind="H", price=101.2, bar=0, confirm_bar=0),                   # PDH 101 च्या 0.2 आत ⇒ duplicate ⇒ PDH जिंकतो (प्राधान्य)
           NS(kind="H", price=108.0, bar=0, confirm_bar=0),                   # वर, 8 < 2σ = 20 ⇒ दाखव
           NS(kind="H", price=125.0, bar=0, confirm_bar=0),                   # 25 > 20 ⇒ दूर
           NS(kind="H", price=95.0, bar=0, confirm_bar=0),                    # buy-side pool किंमतीखाली ⇒ नाही (trade-बाजू)
           NS(kind="L", price=92.0, bar=0, confirm_bar=0), NS(kind="L", price=90.0, bar=0, confirm_bar=0),
           NS(kind="L", price=88.0, bar=0, confirm_bar=0)]
    V = _V(rows, ts, piv, s=s2)
    mk = LQ.pool_marks(V, 3)
    buy = [m for m in mk if m["side"] == "buy"]
    sell = [m for m in mk if m["side"] == "sell"]
    assert [m["src"] for m in buy] == ["PDH", "swing"] and [m["price"] for m in buy] == [101.0, 108.0]
    assert all("BSL" in m["label"] for m in buy) and all("SSL" in m["label"] for m in sell)
    assert len(sell) == 2 and [m["price"] for m in sell] == [99.0, 92.0] and sell[0]["src"] == "PDL"   # per_side 2, जवळचे आधी
    assert all(abs(m["price"] - 100.0) <= 20.0 for m in mk)
    # आरसा (किंमत 100 भोवती): buy ⇄ sell, किंमती 200 − p
    rows_m = [(2 * 100 - o, 2 * 100 - l, 2 * 100 - h, 2 * 100 - c) for o, h, l, c in rows]
    piv_m = [NS(kind="L" if p.kind == "H" else "H", price=2 * 100 - p.price, bar=p.bar, confirm_bar=p.confirm_bar) for p in piv]
    mk_m = LQ.pool_marks(_V(rows_m, ts, piv_m, s=s2), 3)
    assert sorted(2 * 100 - m["price"] for m in mk_m if m["side"] == "sell") == sorted(m["price"] for m in buy)
    assert sorted(2 * 100 - m["price"] for m in mk_m if m["side"] == "buy") == sorted(m["price"] for m in sell)


def test_pools_truncation_no_lookahead():
    """t ला pools = त्या bar पर्यंतच्या data वरच — नंतरचे bars जोडले तरी तेच."""
    rows = [(100, 105, 95, 100), (100, 110, 90, 100), (100, 102, 98, 100), (100, 130, 70, 100), (100, 101, 99, 100), (100, 101, 99, 100)]
    piv = [NS(kind="H", price=120.0, bar=1, confirm_bar=2), NS(kind="H", price=121.0, bar=4, confirm_bar=5)]
    ts = _days(2, 3)
    full = LQ.pools(_V(rows, ts, piv), 3)
    cut = LQ.pools(_V(rows[:4], ts[:4], piv), 3)
    assert sorted((p["src"], p["side"], round(p["price"], 6)) for p in full) == sorted((p["src"], p["side"], round(p["price"], 6)) for p in cut)
    assert not [p for p in full if p["src"] == "equal"]                       # दुसरा H (confirm 5) t = 3 ला नाही ⇒ EQ नाही
