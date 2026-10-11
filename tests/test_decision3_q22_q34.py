"""Abhi Q22–Q34 (batch): Q32 Daily legs adapter, Q28 trend सुरुवात फक्त impulse-स्वभावाच्या पायाने, Q22 रचनात्मक correction degree,
Q23 origin_broken ⇒ कमाल B, Q27 trend नंतर RANGE, Q34 mechanical leg क्रमांक फक्त debug. Synthetic fixtures (तारखा / किंमती code मध्ये
नाहीत; फक्त रचना)."""
import numpy as np
import pandas as pd

from decision3 import daily as DD
from decision3 import daily_legs as DL
from tests.test_decision3 import daily_from_path

S = {"daily_min_sessions": 3, "daily_sigma_sessions": 3, "range_eq_sigma_d": 0.25}


def bars(segments, start=100.0, day0="2030-01-01"):
    """segments = [(target, n_bars, style)]: style "line" (daily_from_path सारखी), "imp" (मोठी body, लहान wick, overlap कमी),
    "chop" (closes सरळ पण body लहान, रुंद overlap, अर्ध्या candles उलट रंगाच्या — corrective स्वभाव; highs / lows सरळ ⇒ जादा pivots नाहीत)."""
    rows, prev = [], float(start)
    for target, n, style in segments:
        for k, c in enumerate(np.linspace(prev, target, n + 1)[1:]):
            if style == "imp":
                o, h, lo = prev, max(prev, c) + 0.1, min(prev, c) - 0.1
            elif style == "chop":
                o = c - 0.3 if k % 2 == 0 else c + 0.3
                h, lo = c + 3.0, c - 3.0
            else:
                o, h, lo = prev, max(prev, c) + 0.5, min(prev, c) - 0.5
            rows.append((o, h, lo, c))
            prev = c
    days = pd.bdate_range(day0, periods=len(rows))
    return pd.DataFrame({"timestamp": days, "open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                         "close": [r[3] for r in rows], "bar_end": days + pd.Timedelta(hours=15, minutes=30)})


# ------------------------------------------------------------------------------------------------ Q32 adapter
def test_structure_impulse_corrective_single():
    assert DL.structure([0, 10, 5, 20, 15, 30])["structure"] == "impulse"                        # 5 waves, नियम पार
    assert DL.structure([0, 10, 4, 14])["structure"] == "corrective"                             # 3 waves (zigzag)
    assert DL.structure([0, 10, 4, 14])["form"] == "zigzag"
    assert DL.structure([0, 10, 1, 11])["form"] == "flat"                                         # B ≈ A
    assert DL.structure([0, 12, 3, 9, 7, 14])["structure"] == "corrective"                       # 3 < 1-टोक ⇒ impulse नाही
    assert DL.structure([0, 10])["structure"] == "single"


def test_reduce_keeps_extremes():
    red = DL.reduce_waves([0, 10, 8, 12, 3, 9, 7, 14])
    assert red[5] == [0, 12, 3, 9, 7, 14] and red[3] == [0, 12, 3, 14] and red[1] == [0, 14]
    for x in red.values():                                                                      # टोकं टोकच: शेवट सर्वात उंच
        assert x[0] == 0 and x[-1] == 14


def test_c_class_imp_and_cor_against_baseline():
    A = DL.arrays(bars([(130, 6, "imp"), (100, 6, "chop"), (130, 6, "line")]))
    imp = DL.metrics(A, 0, 5, 1)
    chop = DL.metrics(A, 5, 11, -1)
    line = DL.metrics(A, 11, 17, 1)
    base = [line] * 12
    assert DL.c_class(imp, base)[1] == DL.IMP and DL.c_class(chop, base)[1] == DL.COR
    assert DL.c_class(imp, base[:5]) == (None, "NA")                                            # baseline < 10 ⇒ NA (warm-up)


# ------------------------------------------------------------------------------------------------ Q28 सुरुवात
def _range_then(segs):
    pre = []
    for _ in range(6):                                                                          # 12 पाय RANGE (C baseline)
        pre += [(110, 4, "line"), (100, 4, "line")]
    return bars(pre + segs, start=100.0)


def test_q28_corrective_b_sets_no_trend_c_impulse_sets_down():
    """RANGE तुटून (A) low; (B) zigzag वर chop candles (corrective) ⇒ UP नाही; (C) चा (1) आवेगी ⇒ DOWN."""
    d = _range_then([(88, 4, "imp"),                                                             # (A): range खाली
                     (100, 5, "chop"), (95, 4, "chop"), (106, 6, "chop"),                        # (B) a-b-c
                     (96, 4, "imp"), (101, 4, "chop"), (84, 5, "imp")])                          # (C) (1) (2) (3)
    st = DD.fold(d, S)
    b_end = 12 * 4 + 4 + 5 + 4 + 6                                                              # (B) चं टोक (bar index)
    assert not any(x.trend == "UP" for x in st[48:b_end + 1])
    assert any("Q28" in x.why for x in st[48:b_end + 1])                                         # का नाही — नोंद
    assert st[-1].trend == "DOWN" and abs(st[-1].protected.price - 104.0) < 1e-6                 # origin = (2) high (chop wick 3)
    first = next(x for x in st if x.trend == "DOWN")
    assert "C IMP" in first.why                                                                  # आवेगी पाय ⇒ परवानगी
    off = DD.fold(d, {**S, "daily_start_nature_gate": False})                                  # gate बंद ⇒ जुना नियम: (B) UP
    assert any(x.trend == "UP" for x in off[48:b_end + 1])


def test_q28_gate_off_matches_old_behaviour_on_fixtures():
    from tests.test_decision3_daily_q15 import FLAT
    d = daily_from_path(FLAT)
    key = lambda x: (x.trend, getattr(x.protected, "price", None), x.phase)                      # noqa: E731
    assert [key(x) for x in DD.fold(d, S)] == [key(x) for x in DD.fold(d, {**S, "daily_start_nature_gate": False})]


# ------------------------------------------------------------------------------------------------ Q22 correction degree
def test_q22_internal_pullback_rule_and_ratio_whatif():
    """(3) मधले लहान bounces = आतले (पहिल्याला संदर्भ नाही ⇒ आतला; दुसरा त्याहून लहान); (4) त्या सगळ्यांपेक्षा मोठी ⇒ same degree."""
    from tests.test_decision3_daily_q15 import FLAT
    d = daily_from_path(FLAT)
    st = DD.fold(d, S)
    waves = [x.wave for x in st if x.wave]
    assert "L4" in waves and "L5" in waves and not any(w in waves for w in ("L6", "L7"))
    rt = DD.fold(d, {**S, "corr_degree_rule": "ratio"})                                        # जुना नियम what-if म्हणून चालतो
    assert [x.wave for x in rt if x.wave][-1] == "L5"
    import pytest
    with pytest.raises(ValueError):
        DD.fold(d, {**S, "corr_degree_rule": "fib"})


def test_q22_bigger_bounce_than_internal_is_correction():
    """(3) मध्ये आतला bounce 4; नंतरचा bounce 6 (> 4) ⇒ correction (L4) आणि नवं टोक ⇒ L5. Bounce 3 (< 4) ⇒ आतला."""
    base = [100, 60, 98, 85, 93, 80]
    big = DD.fold(daily_from_path(base + [84, 72, 78, 66]), S)
    small = DD.fold(daily_from_path(base + [84, 72, 75, 66]), S)
    assert big[-1].wave == "L5" and small[-1].wave == "L3"


# ------------------------------------------------------------------------------------------------ Q27 RANGE after trend
def test_q27_range_after_origin_break_with_equal_highs_lows():
    from tests.test_decision3_daily_q15 import FLAT
    path = FLAT[:12] + [96, 88, 96, 88, 96]                                                      # origin (93.5) तुटला, मग 96 / 88 बाजू
    st = DD.fold(daily_from_path(path), S)
    rng = [x for x in st if x.trend == "RANGE"]
    assert rng and rng[0].band[0] < 88 < 96 < rng[0].band[1]
    assert DD.trade_side("RANGE") == ("bull_put", "bear_call")
    off = DD.fold(daily_from_path(path), {**S, "range_after_trend": False})
    assert not any(x.trend == "RANGE" for x in off[24:])


def test_q27_band_limits_range_levels_to_edges():
    from decision3 import levels as LV
    L = LV.Levels.__new__(LV.Levels)
    L.s = {"active_levels_max": 2}
    snap = [{"role": LV.SUP, "lo": 99, "hi": 100, "dist": 1, "above": False, "below": True},          # वरच्या अर्ध्यात support ⇒ नाही
            {"role": LV.SUP, "lo": 89, "hi": 90, "dist": 11, "above": False, "below": True},
            {"role": LV.RES, "lo": 102, "hi": 103, "dist": 1, "above": True, "below": False}]
    L.snapshot = lambda t: snap
    act = L.active(0, "RANGE", band=(88, 104))
    assert [x["lo"] for x in act] == [89, 102]
    assert [x["lo"] for x in L.active(0, "RANGE")] == [99, 102]                                # पट्टा नाही ⇒ जुना नियम


# ------------------------------------------------------------------------------------------------ Q23 / Q34
def test_q34_describe_has_no_wave_numbers_and_leg_index_is_debug():
    from tests.test_decision3_daily_q15 import FLAT
    st = DD.fold(daily_from_path(FLAT), S)
    for x in st:
        txt = DD.describe(x)
        assert "(3)" not in txt and "(5)" not in txt and "L3" not in txt
        assert x.wave is None or (x.wave.startswith("L") and x.wave[1:].isdigit())


# ------------------------------------------------------------------------------------------------ Q33 engine output
def test_q33_engine_rows_mask_sealed_dates():
    """Engine output (rows) मध्ये sealed तारीख नाही: protected pivot ची तारीख sealed ⇒ "before window" (किंमत तशीच)."""
    import json
    from decision3 import engine as E3
    from tests.test_decision3_method import _synthetic_m15
    m15 = _synthetic_m15()
    open_ = E3.V22(m15)
    sealed = E3.V22(m15, sealed=lambda ts: True)
    a = [r for r in open_.run() if r.get("protected")]
    b = [r for r in sealed.run() if r.get("protected")]
    assert a and len(a) == len(b)
    assert all(r["protected"]["day"] != "before window" for r in a)
    assert all(r["protected"]["day"] == "before window" for r in b)
    assert [r["protected"]["price"] for r in a] == [r["protected"]["price"] for r in b] and json.dumps(b, default=str)


def test_q33_display_start_after_last_sealed():
    from decision3 import history as HI
    from elliott import data_policy as DP
    ts = list(pd.bdate_range(DP.HOLDOUT_START - pd.offsets.BDay(5), periods=10)) + list(pd.bdate_range(DP.CONTAMINATED_START, periods=30))
    s0 = HI.display_start(ts, None, HI.sealed_fn("NIFTY"), sessions=250)
    assert DP.period(ts[s0]) != "HOLDOUT" and all(DP.period(t) != "HOLDOUT" for t in ts[s0:])
    assert HI.display_start(ts, None, HI.sealed_fn("BANKNIFTY"), sessions=250) == 0
    assert HI.sealed_fn("BANKNIFTY") is None and HI.is_nifty("NSE:NIFTY 50")


def test_q28_structure_uses_lower_degree_inner_pivots_in_warmup():
    """Review 🔴3: त्याच degree चे pivots आलटून पालटून ⇒ (1) मध्ये आतले pivots नसतात; आतली रचना एक degree खालच्या (N − 1) pivots वरून.
    (1) = a-b-c (आतला 1-दिवसाचा dip) ⇒ corrective ⇒ C warm-up असला तरी trend नाही; पुढचा (1) सरळ ⇒ UP."""
    segs = [(60, 4, "line"), (70, 3, "line"), (66, 1, "line"), (75, 3, "line"), (69, 4, "line"), (82, 5, "line"), (78, 2, "line"),
            (90, 4, "line")]
    d = bars(segs, start=64.0)
    on = DD.fold(d, S)
    off = DD.fold(d, {**S, "daily_start_nature_gate": False})
    first_on = next(i for i, x in enumerate(on) if x.trend == "UP")
    first_off = next(i for i, x in enumerate(off) if x.trend == "UP")
    assert first_off < first_on
    assert any("(1) corrective (zigzag" in x.why and "Q28" in x.why for x in on[:first_on])


def test_short_legs_are_neutral_and_out_of_baseline():
    from types import SimpleNamespace as N
    d = bars([(130, 6, "imp"), (128, 1, "imp"), (140, 2, "imp")] + [(150 + 10 * (k % 2), 4, "line") for k in range(14)])
    A = DL.arrays(d)
    seq = [N(kind="H", price=130.0, bar=5, confirm_bar=6), N(kind="L", price=128.0, bar=6, confirm_bar=7)]
    c = DL.classify(A, seq, 6, 128.0, 8, 140.0, 9)                                           # 2-bar leg
    assert c["c_cls"] == "NEU" and c["C"] is None


def test_q33_load_inputs_accepts_holdout_daily_warmup(tmp_path):
    """Review 🔴1: v22_check ला Daily पूर्ण history (holdout rows सह) ⇒ HoldoutError नाही (Daily warm-up); 15M पहारा तसाच."""
    from types import SimpleNamespace as N
    from elliott import data_policy as DP
    from scripts import v22_check as VC
    from tests.test_decision3_method import _synthetic_m15
    m15 = _synthetic_m15()
    mp = tmp_path / "m15.csv"
    m15.to_csv(mp, index=False)
    hd = daily_from_path([100, 90, 95], start=str(DP.HOLDOUT_START.date()))
    dd = daily_from_path([22000, 21000], start=str(pd.Timestamp(m15["timestamp"].iloc[0]).normalize().date()))
    a1, a2 = tmp_path / "h.csv", tmp_path / "d.csv"
    hd[["timestamp", "open", "high", "low", "close"]].to_csv(a1, index=False)
    dd[["timestamp", "open", "high", "low", "close"]].to_csv(a2, index=False)
    _, _, daily = VC.load_inputs(N(data=None, m15=str(mp), daily=[str(a1), str(a2)]))
    assert len(daily) == len(hd) + len(dd) and any(DP.period(t) == "HOLDOUT" for t in daily["timestamp"])


def test_q33_telegram_daily_chart_skipped_when_last_daily_sealed():
    """Review 🔴2: 15M bar ला माहीत शेवटची Daily candle sealed ⇒ display_start > upto ⇒ Daily chart नाही (daily_png नकार देतो)."""
    import pytest
    from decision3 import charts as CH
    from decision3 import history as HI
    from elliott import data_policy as DP
    d = daily_from_path([100, 90, 95, 85], start=str((DP.CONTAMINATED_START - pd.offsets.BDay(12)).date()))
    st = DD.fold(d, S)
    up = int(max(i for i, t in enumerate(d["timestamp"]) if DP.period(t) == "HOLDOUT"))
    s0 = HI.display_start(d["timestamp"], up, HI.sealed_fn("NIFTY"))
    assert s0 > up
    with pytest.raises(ValueError):
        CH.daily_png(d, st, "NIFTY", upto=up, start=s0)


def test_q27_range_needs_close_inside_band():
    from tests.test_decision3_daily_q15 import FLAT
    path = FLAT[:12] + [96, 88, 96, 88, 96]
    st = DD.fold(daily_from_path(path), S)
    C = daily_from_path(path)["close"].to_numpy()
    for i, x in enumerate(st):
        if x.trend == "RANGE" and (i == 0 or st[i - 1].trend != "RANGE"):
            assert x.band[0] <= C[i] <= x.band[1]


# ------------------------------------------------------------------------------------------------ Q36 flip gate
def test_q36_flip_needs_impulse_leg_else_origin_broken():
    """origin close-through + उलट रचना पण (1) आतून 3-wave (corrective) ⇒ flip नाही, origin_broken (Q23 कमाल B); gate off ⇒ जुना flip."""
    segs = [(120, 4, "line"), (100, 4, "line"), (112, 4, "line"), (92, 5, "line"), (96, 2, "line"), (85, 4, "line"),
            (95, 3, "line"), (91, 1, "line"), (100, 3, "line"), (93, 4, "line"), (118, 6, "line")]
    d = bars(segs, start=100.0)
    on = DD.fold(d, S)
    off = DD.fold(d, {**S, "daily_start_nature_gate": False})
    assert on[-1].trend == "DOWN" and on[-1].phase == "origin_broken"
    assert any("Q36" in x.why for x in on)
    assert off[-1].trend == "UP"


# ------------------------------------------------------------------------------------------------ Q40 prior levels
def test_q40_prior_trend_degree_levels_within_atr_distance():
    """15M window आधीचे फक्त trend-degree Daily swings (+ Weekly) — किंमतीपासून prior_level_atr_mult × ATR_D आत; इतर जुने pivots नाहीत."""
    from decision3 import engine as E3
    from pivots import charts as PC
    from tests.test_decision3_method import _synthetic_m15
    m15 = _synthetic_m15()
    win = PC.daily_from_15m(m15, pd.to_datetime(m15["bar_end"]).max())
    start = pd.Timestamp(m15["timestamp"].iloc[0]).normalize()
    pre = daily_from_path([30000, 21500, 24000, 22500, 23500, 20800, 23000, 21900, 22600], legs=6,
                          start=str((start - pd.offsets.BDay(49)).date()))
    pre = pre[pre["timestamp"] < start]
    daily = pd.concat([pre[["timestamp", "open", "high", "low", "close", "bar_end"]], win[["timestamp", "open", "high", "low", "close",
                                                                                         "bar_end"]]], ignore_index=True)
    V = E3.V22(m15, daily_df=daily)
    pr = V.levels.prior
    assert pr and {x["src"] for x in pr} <= {"a:D-prior", "a:W-prior"}
    assert all(abs(x["price"] - float(m15["open"].iloc[0])) < 30000 - float(m15["open"].iloc[0]) for x in pr)   # 30k टोक दूर ⇒ नाही
    narrow = E3.V22(m15, daily_df=daily, s={"prior_level_atr_mult": 0.01}).levels.prior
    assert len(narrow) < len(pr)
    n_all = len({(p.kind, p.bar) for st in V.daily for p in st.pivots if p.day < start})
    assert len([x for x in pr if x["src"] == "a:D-prior"]) <= n_all


def test_q40_prior_impulse_end_is_leg_end_not_running_lows():
    """Review 🔴: impulse चालू असताना प्रत्येक नवा low ⇒ imp_end बदलतो; prior levels मध्ये फक्त leg चं अंतिम टोक (running lows नाहीत)."""
    from decision3 import engine as E3
    from pivots import charts as PC
    from tests.test_decision3_method import _synthetic_m15
    m15 = _synthetic_m15()
    win = PC.daily_from_15m(m15, pd.to_datetime(m15["bar_end"]).max())
    start = pd.Timestamp(m15["timestamp"].iloc[0]).normalize()
    pre = daily_from_path([30000, 21500, 24000, 22500, 23500, 20800, 23000, 21900, 22600], legs=6,
                          start=str((start - pd.offsets.BDay(49)).date()))
    pre = pre[pre["timestamp"] < start]
    cols = ["timestamp", "open", "high", "low", "close", "bar_end"]
    daily = pd.concat([pre[cols], win[cols]], ignore_index=True)
    V = E3.V22(m15, daily_df=daily)
    ends = {round(st.imp_end.price, 1) for st in V.daily if st.imp_end is not None and st.day < start}
    lows = sorted(x["price"] for x in V.levels.prior if x["src"] == "a:D-prior")
    finals = set()
    prev = None
    for st in [s for s in V.daily if s.day < start]:
        k = (st.trend, None if st.protected is None else st.protected.bar)
        if prev is not None and k != prev[0] and prev[1] is not None:
            finals.add(round(prev[1].price, 1))
        prev = (k, st.imp_end)
    running = ends - finals - {round(prev[1].price, 1)} if prev and prev[1] is not None else ends - finals
    assert not running & {round(x, 1) for x in lows}
