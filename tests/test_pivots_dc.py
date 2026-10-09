"""थर 1 (एकच swing engine, DC) — synthetic data फक्त, कुठलीही तारीख नाही (prompt §6). सुरुवात data-policy च्या IS सीमेवरून काढली जाते."""
import dataclasses
import json
import os
import re

import numpy as np
import pandas as pd
import pytest

from elliott import data_policy as DP
from pivots import charts as PC
from pivots import engine as PE
from pivots.dc import D0, Pivot, Upper

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SLOTS = [pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * i) for i in range(25)]


def _monday(offset_days=400):
    b = DP.IS_START + pd.Timedelta(days=offset_days)
    return b - pd.Timedelta(days=b.dayofweek)


def m15_from(closes, start=None, wick=1.0, gaps=None):
    """प्रत्येक session 25 bars (09:15 → 15:15). closes = bar closes; open = मागचा close (gaps ⇒ session च्या पहिल्या bar ला उडी)."""
    days = pd.bdate_range(start or _monday(), periods=int(np.ceil(len(closes) / 25)))
    rows, prev = [], float(closes[0])
    for i, c in enumerate(closes):
        d = days[i // 25]
        t = d + SLOTS[i % 25]
        o = prev + ((gaps or {}).get(i // 25, 0.0) if i % 25 == 0 else 0.0)
        rows.append((t, t + pd.Timedelta(minutes=15), o, max(o, c) + wick, min(o, c) - wick, float(c)))
        prev = float(c)
    return pd.DataFrame(rows, columns=["timestamp", "bar_end", "open", "high", "low", "close"])


def walk(n, seed, step=3.0):
    rng = np.random.default_rng(seed)
    return 20000 + np.cumsum(rng.normal(0, step, n))


def run_d0(bars, theta, rows=None):
    """D0 थेट (ठरलेला θ). bars = [(high, low)]; रिटर्न pivots."""
    d = D0()
    t0 = _monday() + SLOTS[0]
    ts_of = (lambda i: t0 + pd.Timedelta(minutes=15 * i))                      # noqa: E731
    for b, (h, lo) in enumerate(bars):
        d.step(b, h, lo, theta, theta, ts_of(b) + pd.Timedelta(minutes=15), 0, ts_of, (rows or {}).get(b))
    return d.out


def one_m(b, highs, lows):
    t0 = _monday() + SLOTS[0] + pd.Timedelta(minutes=15 * b)
    return pd.DataFrame({"timestamp": [t0 + pd.Timedelta(minutes=i) for i in range(len(highs))], "high": highs, "low": lows})


# ---------------------------------------------------------------------------------------------------------------- 1. DC नियम
def test_dc_rule_pivots_confirmation_and_known_at_close():
    bars = [(101, 99), (106, 100), (110, 105), (108, 103), (104, 99), (103, 98), (109, 100), (112, 108)]
    out = run_d0(bars, theta=10)
    assert [(p.kind, p.price, p.bar, p.confirm_bar) for p in out] == [("L", 99, 0, 2), ("H", 110, 2, 4), ("L", 98, 5, 6)]
    t0 = _monday() + SLOTS[0]
    assert out[1].known_at == t0 + pd.Timedelta(minutes=15 * 5)                # confirmation candle (4) चा close
    assert all(p.rule == "normal" for p in out)


def test_equal_high_later_candle_wins():
    out = run_d0([(100, 95), (110, 100), (110, 104), (108, 99)], theta=10)
    assert out[-1].kind == "H" and out[-1].bar == 2                              # '>=' ⇒ बरोबरीत नंतरची candle


# ---------------------------------------------------------------------------------------------------------------- 5. same-bar
PRE = [(100, 90), (108, 99), (110, 104)]                                     # L(90) confirm (bar 1), UP mode, ext 110 (bar 2)


def _upmode_then(bar, rows=None):
    return run_d0(PRE + [bar], theta=10, rows=rows)


def test_same_bar_high_first_by_1m_confirms_h():
    hs = [112, 118, 120] + [115] * 12
    ls = [109, 112, 113] + [107] * 11 + [108]
    out = _upmode_then((120, 107), rows={3: one_m(3, hs, ls)})
    assert out[-1].kind == "H" and out[-1].price == 120 and out[-1].bar == 3 and out[-1].rule == "1m"


def test_same_bar_low_first_by_1m_does_not_confirm_new_high():
    hs = [109] * 12 + [115, 118, 120]
    ls = [107] + [108] * 14
    out = _upmode_then((120, 107), rows={3: one_m(3, hs, ls)})
    assert [p.kind for p in out] == ["L"]                                      # आधी low ⇒ नवं high confirm नाही


@pytest.mark.parametrize("rows", [None, "same_minute", "incomplete", "mismatch"])
def test_same_bar_without_reliable_1m_is_conservative(rows):
    r = {None: None,
         "same_minute": one_m(3, [120] + [115] * 14, [107] + [110] * 14),
         "incomplete": one_m(3, [112, 120, 115], [109, 112, 107]),
         "mismatch": one_m(3, [119] + [115] * 14, [110] * 14 + [107])}[rows]
    out = _upmode_then((120, 107), rows=None if r is None else {3: r})
    assert [p.kind for p in out] == ["L"]                                      # फक्त extend
    out2 = run_d0(PRE + [(120, 107), (115, 112), (113, 109)], theta=10, rows=None if r is None else {3: r})
    assert [p.kind for p in out2] == ["L", "H"] and out2[-1].confirm_bar == 5 and out2[-1].rule == "conservative"
    assert out2[-1].price == 120                                               # पुढच्या candle ने स्वतः θ पूर्ण केला


def test_both_directions_in_one_bar_never_two_pivots():
    out = run_d0([(105, 100), (115, 90)], theta=10)
    assert len(out) <= 1
    out = run_d0([(100, 90), (110, 100), (125, 95), (118, 112)], theta=10)
    bars = [p.bar for p in out]
    assert len(bars) == len(set(bars))


# ---------------------------------------------------------------------------------------------------------------- 6. gap bar
def test_gap_bar_confirms_pivot_and_makes_new_extreme():
    out = run_d0([(100, 90), (110, 100), (112, 104), (98, 85), (92, 88)], theta=10)
    assert out[-1].kind == "H" and out[-1].price == 112 and out[-1].confirm_bar == 3
    d = D0()
    t0 = _monday() + SLOTS[0]
    for b, (h, lo) in enumerate([(100, 90), (110, 100), (112, 104), (98, 85)]):
        d.step(b, h, lo, 10, 10, t0, 0, lambda i: t0)
    assert d.ext == (85, 3)                                                    # gap candle ने नवं टोक


# ---------------------------------------------------------------------------------------------------------------- 3. immutability + backfill
def test_confirmed_pivot_is_frozen_and_1m_backfill_does_not_change_it():
    p = run_d0([(100, 90), (110, 100), (98, 95)], theta=10)[-1]
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.price = 1.0
    closes = walk(25 * 26, 3)
    m15 = m15_from(closes)
    late = []
    for _, r in m15.iterrows():                                                # 1m सगळे candle बंद झाल्यानंतर उशिरा आले (backfill)
        for i in range(15):
            late.append((r["timestamp"] + pd.Timedelta(minutes=i), r["high"], r["low"], r["bar_end"] + pd.Timedelta(days=1)))
    m1 = pd.DataFrame(late, columns=["timestamp", "high", "low", "received_at"])
    a = PE.build(m15)
    b = PE.build(m15, m1)
    assert [PE.pivot_json(p) for p in a["pivots"][0]] == [PE.pivot_json(p) for p in b["pivots"][0]]


# ---------------------------------------------------------------------------------------------------------------- 7. σ
def test_sigma_excludes_0915_and_is_frozen_and_gap_safe():
    closes = walk(25 * 24, 5)
    base = m15_from(closes)
    gap = m15_from(closes, gaps={22: 400.0})                                   # session 22 ला मोठी gap (09:15 candle)
    sb, sg = PE.sigma_by_session(base), PE.sigma_by_session(gap)
    days = sorted(sb)
    assert all(np.isnan(sb[d]) for d in days[:20]) and np.isfinite(sb[days[20]])
    assert sb[days[23]] == sg[days[23]]                                        # 09:15 gap candle σ मध्ये नाही
    m = base.copy()
    m.loc[m.index[-1], ["high", "low"]] = (m["high"].iloc[-1] + 500, m["low"].iloc[-1] - 500)
    assert PE.sigma_by_session(m)[days[-1]] == sb[days[-1]]                    # चालू session चा data त्याच्या σ मध्ये नाही


def test_theta_change_alone_does_not_confirm():
    d = D0()
    t0 = _monday() + SLOTS[0]
    ts_of = (lambda i: t0)                                                     # noqa: E731
    for b, (h, lo, th) in enumerate([(100, 90, 10), (108, 99, 10), (110, 104, 10), (109, 103, 10), (106, 103.5, 5)]):
        d.step(b, h, lo, th, th, t0, 0, ts_of)
    assert [p.kind for p in d.out] == ["L"]                                    # θ लहान झाला, पण भाव नव्याने खाली गेला नाही
    d.step(5, 105, 102, 5, 5, t0, 0, ts_of)
    assert [p.kind for p in d.out] == ["L", "H"]


# ---------------------------------------------------------------------------------------------------------------- 2. no-lookahead + 4. nesting
@pytest.mark.parametrize("seed", [1, 2, 7])
def test_no_lookahead_truncation(seed):
    m15 = m15_from(walk(25 * 40, seed, 4.0))
    full = PE.build(m15)
    for cut in (25 * 30 + 7, 25 * 35 + 13, 25 * 39 + 24):
        part = PE.build(m15.iloc[:cut])
        t = pd.Timestamp(m15["bar_end"].iloc[cut - 1])
        for d in PE.DEGREES:
            a = [PE.pivot_json(p) for p in full["pivots"][d] if p.known_at <= t]
            b = [PE.pivot_json(p) for p in part["pivots"][d]]
            assert a == b


@pytest.mark.parametrize("seed", range(6))
def test_nesting_property_random_and_adversarial(seed):
    rng = np.random.default_rng(seed)
    closes = walk(25 * 45, seed, 5.0)
    if seed % 2:                                                               # adversarial: झिगझॅग उड्या, बरोबरीचे टोक
        closes = closes + np.where(np.arange(len(closes)) % 7 == 0, rng.choice([-60, 60], len(closes)), 0)
        closes = np.round(closes / 20) * 20
    res = PE.build(m15_from(closes))
    for d in PE.DEGREES[1:]:
        lower = {(p.bar, p.kind, p.price) for p in res["pivots"][d - 1]}
        assert all((p.bar, p.kind, p.price) in lower for p in res["pivots"][d])
    for d in PE.DEGREES:
        ps = res["pivots"][d]
        assert all(a.kind != b.kind for a, b in zip(ps, ps[1:]))
        assert all(a.known_at <= b.known_at for a, b in zip(ps, ps[1:]))
        assert len({p.bar for p in ps}) == len(ps)


def test_upper_known_at_is_max_of_lower_known_ats():
    t0 = _monday()
    mk = lambda k, pr, b, h: Pivot(0, k, pr, b, t0 + pd.Timedelta(hours=b), b, t0 + pd.Timedelta(hours=h), 1, 1, "normal")  # noqa: E731
    u = Upper(1)
    seq = [mk("L", 100, 0, 1), mk("H", 130, 1, 2), mk("L", 112, 2, 3), mk("H", 125, 3, 4), mk("L", 105, 4, 9)]
    out = [u.step(q, 20, 5, 0) for q in seq]
    got = [p for p in out if p]
    assert [(p.kind, p.price) for p in got] == [("L", 100), ("H", 130)]
    assert got[-1].known_at == seq[-1].known_at and got[-1].bar == 1


# ---------------------------------------------------------------------------------------------------------------- 8. warm-up
def test_warmup_flags_and_determinism_after_warmup():
    closes = walk(25 * 60, 11, 5.0)
    m15 = m15_from(closes)
    a = PE.build(m15)
    b = PE.build(m15.iloc[25 * 6:].reset_index(drop=True))                      # 6 sessions नंतरची वेगळी सुरुवात
    assert any(p.warmup for p in a["pivots"][0]) and not all(p.warmup for p in a["pivots"][0])
    t = pd.Timestamp(m15["timestamp"].iloc[25 * 40])
    for d in (0, 1):
        pa = [(p.kind, p.price, str(p.ts)) for p in a["pivots"][d] if p.known_at >= t]
        pb = [(p.kind, p.price, str(p.ts)) for p in b["pivots"][d] if p.known_at >= t]
        assert pa == pb and pa


# ---------------------------------------------------------------------------------------------------------------- 9–10. EQ, trend
def _p(kind, price, i, eq=False):
    t = _monday() + pd.Timedelta(hours=i)
    return Pivot(1, kind, price, i, t, i, t, 10.0, 40.0, "normal", eq=eq)


@pytest.mark.parametrize("seq,want", [
    ([("L", 100), ("H", 120), ("L", 110), ("H", 130)], "वर"),
    ([("H", 130), ("L", 110), ("H", 120), ("L", 100)], "खाली"),
    ([("L", 100), ("H", 120), ("L", 95), ("H", 130)], "range"),
])
def test_trend_and_protected(seq, want):
    ps = [_p(k, v, i) for i, (k, v) in enumerate(seq)]
    tr = PE.trend(ps)
    assert tr["name"] == want
    if want == "वर":
        assert tr["protected"]["kind"] == "L" and tr["protected"]["price"] == 110
    elif want == "खाली":
        assert tr["protected"]["kind"] == "H" and tr["protected"]["price"] == 120
    else:
        assert tr["protected"] is None


def test_equal_highs_flag_and_trend_range():
    closes = np.concatenate([np.linspace(20000, 20300, 120), np.linspace(20300, 20100, 100), np.linspace(20100, 20300, 100),
                             np.linspace(20300, 20150, 80), walk(25 * 22, 9)])
    res = PE.build(m15_from(closes))
    for d in PE.DEGREES:
        last = {}
        for p in res["pivots"][d]:
            q = last.get(p.kind)
            if p.eq:
                assert q is not None and abs(p.price - q.price) <= 0.1 * p.sigma + 1e-9
            last[p.kind] = p
    ps = [_p("L", 100, 0), _p("H", 120, 1), _p("L", 110, 2), _p("H", 120.5, 3, eq=True)]
    assert PE.trend(ps)["name"] == "range" and PE.labels(ps)[id(ps[-1])] == "EQH"


# ---------------------------------------------------------------------------------------------------------------- 11. अपूर्ण दिवस
def test_incomplete_day_does_not_change_htf_and_daily_candle_waits():
    m15 = m15_from(walk(25 * 40, 4, 6.0))
    full = PE.build(m15.iloc[:25 * 39])
    part = PE.build(m15.iloc[:25 * 39 + 10])                                   # शेवटचा दिवस अर्धवट
    t = pd.Timestamp(m15["bar_end"].iloc[25 * 39 - 1])
    for d in (3, 4):
        assert [PE.pivot_json(p) for p in full["pivots"][d]] == [PE.pivot_json(p) for p in part["pivots"][d] if p.known_at <= t]
    daily = PC.daily_from_15m(m15.iloc[:25 * 39 + 10], pd.Timestamp(m15["bar_end"].iloc[25 * 39 + 9]))
    assert len(daily) == 39                                                    # अर्धवट दिवसाची daily candle नाही


# ---------------------------------------------------------------------------------------------------------------- 12. holdout guard
def test_holdout_rows_never_reach_engine_but_display_only_can_be_drawn():
    h = m15_from(walk(25 * 3, 1), start=DP.HOLDOUT_START + pd.Timedelta(days=10))
    with pytest.raises(DP.HoldoutError):
        PE.build(h)
    with pytest.raises(DP.HoldoutError):
        PE.sigma_by_session(PE.guard(h))
    ok = m15_from(walk(25 * 25, 2))
    flagged = ok.assign(display_only=False)
    flagged.loc[flagged.index[:5], "display_only"] = True
    with pytest.raises(DP.HoldoutError):
        PE.build(flagged)
    disp = PC.display_only(h)                                                  # chart-drawing path चा नाव दिलेला अपवाद
    assert disp["display_only"].all()
    with pytest.raises(DP.HoldoutError):
        PE.guard(disp)


# ---------------------------------------------------------------------------------------------------------------- 13–14. output, caption
def test_output_deterministic_and_caption_limits(tmp_path):
    m15 = m15_from(walk(25 * 30, 6, 5.0))
    res = PE.build(m15)
    asof = pd.Timestamp(m15["bar_end"].iloc[-1])
    j1 = json.dumps(PE.snapshot(res, asof), ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(PE.snapshot(PE.build(m15), asof), ensure_ascii=False, sort_keys=True)
    assert j1 == j2
    cap = PC.caption(2, 22, PE.snapshot(res, asof), asof)
    assert len(cap.encode("utf-16-le")) // 2 <= 1024 and len(cap.splitlines()) <= 8
    assert cap.startswith("🧭 SWING CHECK 2/22") and "Reply" in cap
    for key in ("_", "{", "}", "D0", "warmup", "known"):
        assert key not in cap
    for f in ("pivots/engine.py", "pivots/dc.py", "pivots/charts.py", "scripts/swing_check.py"):
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert not re.search(r"^\s*(?:from|import)\s+(?:broker|order|upstox_api|kite|shoonya|stocko)", src, re.M)


# ---------------------------------------------------------------------------------------------------------------- 15. shadow
def test_shadow_old_pivot_sets_and_live_signal_unchanged():
    """Branch आधी नोंदवलेला fixture: जुने pivot संच (market_state, elliott multi_degree) आणि Simple Core signal — byte-for-byte."""
    fx = json.load(open(os.path.join(HERE, "fixtures", "pivots_shadow_baseline.json"), encoding="utf-8"))
    assert shadow_fingerprint() == fx


def shadow_fingerprint():
    import market_state.core as MC
    from elliott import settings as ES
    from elliott import swings as W
    from simple_core import engine as SE
    m1 = synthetic_1m()
    asof = pd.Timestamp(m1["timestamp"].iloc[-1]) + pd.Timedelta(minutes=1)
    tr = MC.frame(m1, "15m", asof)
    ms = [(str(p["ts"]), round(float(p["price"]), 2), p["kind"]) for p in MC.label(MC.pivots(tr, 3.0, "15m"))]
    md = W.multi_degree(m1, dict(ES.DEFAULTS), now=asof)
    el = {str(d): [(str(p.ts), round(float(p.price), 2), p.kind) for p in md[d]["confirmed"]] for d in sorted(md)}
    sg = SE.signal_at(m1, asof)
    return json.loads(json.dumps({"market_state": ms, "elliott": el, "signal": sg.get("signal"), "why": sg.get("why")}, default=str))


def synthetic_1m(days=30, seed=21):
    rng = np.random.default_rng(seed)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(800), periods=days):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0, 2.5) + (0.3 if (t.day % 6) < 3 else -0.3)
            rows.append((t, o, max(o, px) + 0.8, min(o, px) - 0.8, px))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).assign(volume=0.0)


# ---------------------------------------------------------------------------------------------------------------- 16. तारीख नाही
DATE_RX = [re.compile(r"\b(?:19|20)\d\d[-/.](?:0[1-9]|1[0-2])\b"),
           re.compile(r"\b(?:19|20)\d\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\b"),
           re.compile(r"\bdate(?:time)?\(\s*(?:19|20)\d\d\s*,"),
           re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b"),
           re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:0?[1-9]|[12]\d|3[01]|(?:19|20)\d\d)\b")]


def test_no_date_literals_in_new_code():
    paths = [os.path.join(ROOT, "pivots", f) for f in os.listdir(os.path.join(ROOT, "pivots")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "swing_check.py"), os.path.abspath(__file__)]
    paths += [os.path.join(HERE, "fixtures", "pivots_shadow_baseline.json")]
    hits = []
    for p in paths:
        assert not any(rx.search(os.path.basename(p)) for rx in DATE_RX)
        if p.endswith(".json"):
            continue                                                           # fixture मधले timestamps = synthetic data (नाव तारीख-मुक्त)
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if any(rx.search(line) for rx in DATE_RX):
                hits.append(f"{os.path.basename(p)}:{i}: {line.strip()[:80]}")
    assert not hits, hits


def test_swing_check_review_kind_not_measured():
    from backtest_review import store as BS
    assert "swing_check" in BS.KINDS and "swing_check" in BS.NOT_MEASURED


# ---------------------------------------------------------------------------------------------------------------- review नंतरचे tests
def test_1m_order_uses_exact_prices_not_relative_tolerance():
    hs = [119.99] + [110] * 9 + [120] + [111] * 4                           # 119.99 हा high नाही (20000 च्या 1e-5 पेक्षा कमी अंतर)
    ls = [111] * 5 + [107] + [110] * 9                                       # low आधी, खरा high नंतर ⇒ H confirm नाही
    out = _upmode_then((120, 107), rows={3: one_m(3, hs, ls)})
    assert [p.kind for p in out] == ["L"]


def test_conservative_label_only_for_the_held_candle():
    bars = PRE + [(120, 107), (130, 121), (128, 125), (127, 118)]           # bar 3 held; bar 4 नवं टोक; bar 6 normal confirm
    out = run_d0(bars, theta=10)
    assert out[-1].kind == "H" and out[-1].bar == 4 and out[-1].rule == "normal"


def test_undecided_confirms_the_unambiguous_side_at_once():
    out = run_d0([(95, 90), (98, 93), (108, 97)], theta=10)
    assert [(p.kind, p.price, p.confirm_bar, p.rule) for p in out] == [("L", 90, 2, "normal")]


def test_daily_candle_complete_on_cas_days_and_markers_not_clamped():
    from opportunity_engine import cas as CAS
    start = pd.Timestamp(CAS.load_cas_window()["effective_from"]) + pd.Timedelta(days=7)
    m15 = m15_from(walk(25 * 8, 3), start=start - pd.Timedelta(days=start.dayofweek))
    m15 = m15[~CAS.cas_mask(m15["timestamp"]).to_numpy()].reset_index(drop=True)   # CAS candle नाही (engine सारखं)
    asof = pd.Timestamp(m15["bar_end"].iloc[-1])                                    # शेवटचा bar 15:15 ला संपतो
    daily = PC.daily_from_15m(m15, asof)
    assert len(daily) == 8                                                          # चालू दिवस पूर्ण धरला
    assert len(PC.weekly_from_daily(daily, asof)) == 2
    assert PC._x_of(daily, asof + pd.Timedelta(days=1)) is None                     # शेवटच्या candle नंतरची खूण मागे दाबत नाही


def test_display_only_history_drawn_but_never_in_engine(tmp_path):
    m15 = m15_from(walk(25 * 30, 6, 5.0))
    res = PE.build(m15)
    asof = pd.Timestamp(m15["bar_end"].iloc[-1])
    hist = m15_from(walk(25 * 40, 9), start=DP.HOLDOUT_START + pd.Timedelta(days=30))
    hd = PC.daily_from_15m(hist, pd.Timestamp(hist["bar_end"].iloc[-1]))[["timestamp", "open", "high", "low", "close"]]
    hd["timestamp"] = hd["timestamp"] - pd.Timedelta(days=4000)                    # chart च्या आधीचा जुना इतिहास
    pngs, snap = PC.charts(res, asof, PC.display_only(hd))
    assert set(pngs) == {"15M", "1H", "D", "W"}
    assert json.dumps(snap, default=str) == json.dumps(PE.snapshot(res, asof), default=str)   # history मोजमापात नाही


def test_script_writes_only_out_dir_and_rerun_is_byte_identical(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("swc", os.path.join(ROOT, "scripts", "swing_check.py"))
    SC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(SC)
    rng = np.random.default_rng(4)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=24):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    before = set(os.listdir(tmp_path))
    outs = []
    for k in ("a", "b"):
        od = tmp_path / k
        assert SC.main(["--data", str(data), "--out-dir", str(od), "--run-id", "swings/t", "--days", "2"]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert set(os.listdir(tmp_path)) - before == {"a", "b"}                            # फक्त out-dir
    assert outs[0] == outs[1] and outs[0]
